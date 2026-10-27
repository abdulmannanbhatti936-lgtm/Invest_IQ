# Detailed Implementation Report — InvestIQ

**Project:** InvestIQ — AI-Based Portfolio Management System for PSX Investors
**Type:** Final Year Project (BSCS), NUML Islamabad
**Team:** Muhammad Ali Khaliq & Abdul Mannan Bhatti
**Supervisor:** Mr. Zain-ul-Abideen

**Purpose:** This document tracks the exhaustive details of what has been implemented so far in the InvestIQ project. It covers the specific libraries used, how the implementation was coded, what each specific task does, and how the complete project works end-to-end.

> **CRITICAL RULE FOR AI:** Whenever a new task or step is completed from the `Workflow.md`, the AI **MUST** append a detailed entry for that step in this file.

---

## Project Overview

InvestIQ is a bilingual (English/Urdu) AI-powered investment advisory platform built specifically for novice Pakistani retail investors using the Pakistan Stock Exchange (PSX). It provides personalized, jargon-free portfolio recommendations by combining:

- Real-time and historical stock market data
- FinBERT AI sentiment analysis of financial news
- Machine Learning (Random Forest + LSTM) price prediction
- A user risk profile questionnaire to personalize every recommendation

**Key principle:** Advisory only — no trade execution. The system tells users _what to consider_, never places orders.

---

## System Architecture (How Everything Connects)

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                             │
│  apps/web (React + Vite + TypeScript)  localhost:5173       │
│  - Login / Register / Onboarding / Dashboard / Stocks       │
│  - Calls backend via @investiq/api-client package           │
└────────────────────────────┬────────────────────────────────┘
                             │ HTTP (axios)
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                        BACKEND (FastAPI)                    │
│  services/api  localhost:8000                               │
│  Routers: /auth  /users  /stocks  /stocks/{ticker}/...      │
│  Services: StockService, RiskScoring                        │
│  ML: FinBERT sentiment, Random Forest predictor, LSTM       │
└──────────┬─────────────────────────────────────┬────────────┘
           │ SQLAlchemy (psycopg2)                │ redis-py
           ▼                                      ▼
┌──────────────────────┐             ┌────────────────────────┐
│  PostgreSQL :5435    │             │  Redis :6379           │
│  (Docker container)  │             │  (Docker container)    │
│  Tables:             │             │  - Cache: stock quotes  │
│  users               │             │  - Celery task broker  │
│  risk_profiles       │             └────────────────────────┘
│  stocks              │
│  price_points        │             ┌────────────────────────┐
│  sentiment_scores    │◄────────────│  Celery Worker         │
│  predictions         │             │  Background Jobs:      │
└──────────────────────┘             │  - fetch market data   │
                                     │  - scrape news         │
                                     │  - run FinBERT AI      │
                                     └──────────┬─────────────┘
                                                │
                                     ┌──────────▼─────────────┐
                                     │  External APIs          │
                                     │  - Yahoo Finance (yfinance)│
                                     │  - Yahoo RSS feed (news)│
                                     │  - HuggingFace FinBERT  │
                                     └────────────────────────┘
```

---

## Technology Stack Summary

| Layer                | Technology                         | Version | Purpose                                                 |
| -------------------- | ---------------------------------- | ------- | ------------------------------------------------------- |
| Backend Framework    | FastAPI                            | latest  | High-performance async REST API                         |
| ASGI Server          | Uvicorn                            | latest  | Runs FastAPI in production/dev                          |
| ORM                  | SQLAlchemy                         | latest  | Database models & queries                               |
| Migrations           | Alembic                            | latest  | Database schema version control                         |
| Database             | PostgreSQL 15                      | Docker  | Persistent relational data storage                      |
| Cache / Queue        | Redis 7                            | Docker  | Response caching + Celery broker                        |
| Task Queue           | Celery                             | latest  | Async background jobs                                   |
| Auth                 | python-jose + passlib              | latest  | JWT tokens + bcrypt password hashing                    |
| Validation           | Pydantic v2                        | latest  | Request/response schema validation                      |
| Market Data          | yfinance                           | latest  | Yahoo Finance OHLCV data                                |
| News Scraping        | BeautifulSoup4 + requests          | latest  | Financial news RSS parsing                              |
| AI Sentiment         | HuggingFace Transformers + FinBERT | latest  | NLP-based news sentiment scoring                        |
| ML Prediction        | scikit-learn                       | latest  | Random Forest BUY/SELL/HOLD signal                      |
| Technical Indicators | pandas (own implementation)        | —       | RSI, MACD, Bollinger Bands, SMA (pandas-ta was removed) |
| Deep Learning        | PyTorch + LSTM                     | latest  | Advanced time-series price prediction                   |
| Frontend             | React 19 + TypeScript              | latest  | Web UI                                                  |
| Build Tool           | Vite 8                             | latest  | Ultra-fast frontend dev server                          |
| Routing              | react-router-dom v7                | latest  | SPA page routing                                        |
| Forms                | react-hook-form + zod              | latest  | Type-safe form validation                               |
| Charts               | recharts                           | latest  | Stock price charts                                      |
| HTTP Client          | axios                              | latest  | API calls from frontend                                 |
| i18n                 | i18next + react-i18next            | latest  | English/Urdu bilingual support                          |
| Testing              | pytest                             | latest  | Backend integration tests                               |
| CI/CD                | GitHub Actions                     | -       | Auto-run tests on every push                            |
| Containerization     | Docker + docker-compose            | -       | Postgres + Redis local infra                            |

---

## Phase 0: Foundation Setup (✅ Complete — re-verified 2026-10-09)

Every Workflow.md Phase 0 checkpoint was re-run on 2026-10-09 against the real code (not assumed). Gaps found during that audit were fixed and are listed per step.

### Step 0.1 — Repository & monorepo skeleton

- Folders match Architecture.md §5: `apps/web`, `apps/mobile`, `services/api`, `services/ml-engine`, `services/sentiment-engine`, `services/chatbot-service`, `packages/{shared-types,api-client,i18n,design-tokens}`, `infra/` (incl. `infra/deploy/`), `docs/`.
- Per Architecture.md §6.5 the ML, sentiment and chatbot code runs as internal modules of `services/api` (ML lives in `services/api/ml/`); the three `services/*-engine|service` folders hold pointer READMEs only.
- `.gitignore` covers `node_modules`, `__pycache__`, `.env`, `venv`, build output, tool caches, and all model artifacts (`*.h5`, `*.pt`, `*.pkl`, `*.joblib`, `services/api/ml/artifacts/`).

### Step 0.2 — Local infrastructure (Docker)

- `infra/docker-compose.yml`: Postgres 15 (host port **5435**) and Redis 7 (6379), named volumes, **healthchecks** (`pg_isready`, `redis-cli ping`). `docker compose up -d --wait` reports both containers `healthy`.
- `.env.example` (root and `services/api/`) lists every variable from Architecture.md §17 with placeholder values; the database URL uses port 5435.

### Step 0.3 — Backend skeleton (FastAPI)

- `services/api`: `main.py`, `routers/`, `services/`, `crud/`, `models/`, `schemas/`, `core/` (config, database, security, deps, rate limiting, Redis, Celery), `integrations/`, `worker/`, `ml/`, `tests/`.
- `GET /health` → `{"status": "ok"}` (200). Alembic migrations apply to the Postgres container; a full upgrade → downgrade → upgrade round trip on an empty database is clean.
- `requirements.txt` pins every top-level package to the tested version (an unpinned SQLAlchemy 2.1 once broke CI by switching the default Postgres driver).

### Step 0.4 — Web skeleton (React + Vite + TypeScript)

- Tailwind CSS 4, React Router 7, React Query. Routes per Design.md §14.1: `/`, `/login`, `/register`, `/onboarding`, `/dashboard`, `/stocks`, `/stocks/:ticker`, `/portfolio`, `/backtest`, `/chat`, `/notifications`, `/admin` (later-phase routes show a "coming in Phase N" screen).
- Verified in a headless browser: every route renders with no console errors. `react-is` was added because Recharts requires it (the production build was failing without it).

### Step 0.5 — Mobile skeleton (Expo)

- Expo SDK 57 + React Native, React Navigation bottom tabs (Home, Stocks, Portfolio, Chat, Notifications — Design.md §14.2), React Query.
- Verified: `tsc --noEmit` passes, an Android bundle builds (918 modules, a single React copy), and Metro starts. Running on a physical device / emulator is a manual check.

### Step 0.6 — Shared packages (npm workspaces)

- `@investiq/shared-types` (domain types), `@investiq/api-client` (axios client, token refresh, error helpers), `@investiq/i18n` (i18next + `en.json`/`ur.json`), `@investiq/design-tokens` (colors, typography, spacing, shadows, motion — placeholder values per Design.md §2).
- Packages are consumed as TypeScript source. Verified in the browser: the web app imports all four and `healthCheck()` reaches the backend `/health`.

### Step 0.7 — Linting, formatting, CI

- One shared ESLint + Prettier config for `apps/*` and `packages/*`; `ruff` + `black` for Python.
- `.github/workflows/ci.yml` (every push and every PR to `main`):
  - **backend:** ruff, black `--check`, Alembic migrations on a fresh Postgres, pytest.
  - **frontend:** `npm ci`, ESLint, i18n parity check (+ its tests), `tsc -b` (web), web unit tests (Node's built-in test runner), `tsc --noEmit` (mobile), type-check of all four packages.
- Deliberately broken code makes `npm run lint` and `ruff check` fail (tooling is active, not a no-op).

### Step 0.8 — Documentation sync

- Root `README.md` has working setup instructions (Docker → backend `.env` → migrations → API → Celery → ML training → web → mobile → quality checks).

---

## Phase 1: Auth, Onboarding & Risk Profiling (✅ Complete — re-verified 2026-10-09)

Implements PRD.md FR1–FR6 on the web. Each step was audited one at a time against Workflow.md and the related PRD/Architecture/Design/Rules sections; failures were fixed and covered by tests.

### Step 1.1 — Database models

- `users`: `id` UUID, `email` (unique), `password_hash`, `full_name`, `role` (`user`/`admin`, added early because the admin route guard needs it), `onboarding_progress` JSONB (FR6 draft), `created_at`.
- `risk_profiles`: `id` UUID, `user_id` (unique FK → users), `category` enum (`conservative`/`moderate`/`aggressive`), `answers` JSONB, `updated_at`.
- Fixed: the original migration's downgrade left the `riskcategory` enum type behind, so a re-upgrade failed.

### Step 1.2 — Auth backend

- `POST /auth/register`, `POST /auth/login` (OAuth2 password form), `POST /auth/refresh`.
- Passwords hashed with bcrypt (passlib 1.7.4 + `bcrypt==3.2.2`; bcrypt 5 breaks passlib). Passwords limited to **72 bytes** (bcrypt ignores the rest).
- JWT: access token **30 min**, refresh token **7 days**, signed with **separate secrets** (`JWT_SECRET` / `JWT_REFRESH_SECRET`; the app refuses to start if they are equal) and a `type` claim, so neither token works in place of the other.
- Rate limiting on `/auth/*`: 10 attempts / 60 s per client IP and path (Redis). If Redis is down it fails open and logs a WARNING (accepted for the FYP; see Memory.md §11).
- Login with an unknown email returns the same error **and costs the same bcrypt check** as a wrong password (dummy-hash comparison), so neither message nor timing reveals registered emails (before: 19 ms vs 367 ms; after: 371 ms vs 385 ms).
- No password or token is ever written to logs (tested).

### Step 1.3 — Risk profile backend

**File:** `services/api/services/risk_scoring.py` — pure functions, no DB/HTTP inside (tested).

**Scoring (team-approved 2026-10-09):** 7 questions, each option 3 / 2 / 1 points → total 7–21.

| Question (id)                                 | 3 points           | 2 points               | 1 point            |
| --------------------------------------------- | ------------------ | ---------------------- | ------------------ |
| Age (`age_band`)                              | Under 30           | 30 to 50               | Over 50            |
| Income stability (`income_stability`)         | Very steady        | Mostly steady          | Irregular          |
| When money is needed (`investment_horizon`)   | More than 5 years  | 1–5 years              | Within 1 year      |
| Reaction to a 15% drop (`loss_tolerance`)     | Buy more           | Wait                   | Sell               |
| Share-market experience (`market_experience`) | Several years      | A little / mutual fund | None               |
| Goal (`investment_goal`)                      | Growth             | Steady income          | Preserve value     |
| Emergency savings (`emergency_savings`)       | More than 6 months | 3–6 months             | Less than 3 months |

- Score → category: **7–11 Conservative, 12–16 Moderate, 17–21 Aggressive**.
- Safety caps after scoring (a cap can only lower the category): money needed within 1 year → at most **Conservative**; would sell after a drop, or emergency savings under 3 months → at most **Moderate**.

**Endpoints** (all scoped to the logged-in user — no user-id routes):

| Method    | Path                            | Purpose                                                             |
| --------- | ------------------------------- | ------------------------------------------------------------------- |
| GET       | `/users/me`                     | Current user incl. `role` and `has_risk_profile`                    |
| GET       | `/users/risk-questionnaire`     | Public: question ids + option values only (scores stay server-side) |
| GET       | `/users/me/risk-profile`        | Current profile incl. `score` and `caps_applied`                    |
| PATCH     | `/users/me/risk-profile`        | Create or retake (FR5); always bumps `updated_at`; clears the draft |
| GET / PUT | `/users/me/onboarding-progress` | Save / read partial answers + step (FR6)                            |

- Validation returns **422** (never 500) for unknown question ids, unknown options, missing answers, non-text answers, **duplicate answers** (a JSON key sent twice) and an out-of-range draft step.
- Every API datetime is timezone-aware UTC with a trailing `Z`; the web shows dates in Asia/Karachi time.

### Step 1.4 — Auth tests

`services/api/tests/test_auth.py` (15 tests) and `tests/test_admin_guard.py` (4). They prove:

| Test                                                                                                       | What it proves                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_register_and_login`                                                                                  | Register (201, no password hash returned) → login → protected endpoint; duplicate email 400, wrong password / unknown email 401, no or garbage token 401, refresh issues new tokens |
| `test_expired_access_token_rejected` / `test_expired_refresh_token_rejected`                               | Tokens with a past expiry → 401                                                                                                                                                     |
| `test_malformed_and_tampered_tokens_rejected`                                                              | Flipped signature, swapped user, `alg: none`, foreign secret, missing segment → 401                                                                                                 |
| `test_tokens_for_deleted_user_rejected`                                                                    | Unexpired tokens of a deleted user → 401                                                                                                                                            |
| `test_refresh_token_signed_with_separate_secret`, `test_access_and_refresh_tokens_are_not_interchangeable` | Separate secrets; a token only works in its own role                                                                                                                                |
| `test_login_does_not_reveal_whether_email_exists`, `test_unknown_email_still_runs_one_password_check`      | No user enumeration via message or timing                                                                                                                                           |
| `test_passwords_and_tokens_never_logged`                                                                   | Nothing secret appears in any log line                                                                                                                                              |
| `test_register_validates_input`, `test_password_limited_to_72_bytes`                                       | Server-side input validation                                                                                                                                                        |
| `test_auth_rate_limit`, `test_register_rate_limited`, `test_rate_limit_fails_open_without_redis`           | Brute-force protection; visible WARNING when skipped                                                                                                                                |
| `test_admin_guard.py`                                                                                      | `require_admin`: admin 200, non-admin 403, no token 401 (test-only route)                                                                                                           |

### Step 1.5 — Web: auth screens

`apps/web/src/features/auth/` — `LoginPage`, `RegisterPage`, `AuthShell`.

- Labels above inputs, required fields marked (`*` + `aria-required`), inline errors on blur and on submit, linked to the input for screen readers (Design.md §12.3, §13).
- Submit button disabled with a spinner while submitting.
- 400 (email taken), 401, 422 (incl. the 72-byte limit, shown on the password field) and 429 all have English and Urdu messages via `packages/i18n`.
- The register page shows the PRD §8.5 disclaimer. Tokens are stored in `localStorage` (XSS trade-off accepted for the FYP; httpOnly-cookie refresh token is a Phase 11 item — Memory.md §11).

### Step 1.6 — Web: onboarding questionnaire

`apps/web/src/features/onboarding/OnboardingPage.tsx`

- One question per screen, large choice cards (no radios/dropdowns), progress bar + "Question X of 7", Back keeps earlier answers.
- **FR6:** a draft (answers + step) is saved after every answer; closing the tab and logging in again resumes at the same question. Draft saves are sent one at a time with the latest answers last, so fast clicking can never leave the server on an older step (unit-tested).
- Result screen: category badge, a 1–2 sentence plain explanation, and a plain-language note for each safety cap that applied. Disclaimer on every onboarding screen.
- **FR5:** retake from the dashboard (`/onboarding?retake=1`) with a "Cancel and keep my current profile" link.
- Error states: failed progress load → message + retry (never silently starts over); failed draft save → non-blocking warning.

### Step 1.7 — Route guard

Guard decisions live in `apps/web/src/features/auth/guardRules.ts` (pure, unit-tested).

- Logged out → `/login`, then back to the page originally requested (same-app paths only; `//evil.com`-style redirects are refused).
- Logged in without a completed risk profile → `/onboarding` from every protected route (`/dashboard`, `/stocks`, `/stocks/:ticker`, `/portfolio`, `/backtest`, `/chat`, `/notifications`, `/admin`). The check uses the server's `/users/me` (`has_risk_profile`), never client storage, and shows a loading spinner first, so protected content never flashes.
- Completed profile opening `/onboarding` → `/dashboard` unless retaking. Logged-in users opening `/login` or `/register` → `/dashboard`.
- Expired/invalid refresh token → logged out, sent to `/login` with "Your session expired. Please log in again." (EN/UR), one refresh attempt, no loop.
- `/admin` requires the `admin` role (UI); the backend `require_admin` dependency returns 403 for non-admins. Server-side risk-profile enforcement is required from Phase 5 (Memory.md §4).

### Step 1.8 — i18n pass (English / Urdu)

- All Phase 1 strings go through `packages/i18n`; an AST scan found 0 hardcoded user-facing strings in Phase 1 screens and shared components.
- `npm run check -w @investiq/i18n` (in CI) fails on missing/extra keys, empty values or mismatched `{{placeholders}}` between `en.json` and `ur.json` (165 keys).
- Urdu: `<html lang="ur" dir="rtl">`, layout mirrored, emails/numbers stay LTR with Western digits, body text in **Noto Naskh Arabic** (self-hosted, SIL OFL; Design.md §3). The language choice persists across reloads and logout/login. All Phase 1 screens checked at 360 px and 1280 px with no overflow.
- `docs/i18n-review-phase1.md`: all 103 Phase 1 strings (key | English | Urdu) for the team's Urdu tone review (Design.md §10).

### Step 1.9 — Documentation sync and exit criteria

- Memory.md, Phases.md, this report and the README updated; Phase 1 exit criteria and Workflow.md Appendix A checked one by one (see Memory.md §7, 2026-10-09).
- Screenshots of every audited state: `docs/screenshots/phase1/`.

---

## Phase 2: Stock Data & Market Analysis (re-audited 2026-10-10)

> The first pass was marked complete without checkpoint evidence and served live Yahoo data per request (pages broke when Yahoo was down; AAPL test rows sat in the database). The re-audit below replaces it. The news scraper and sentiment model that the first pass filed under Phase 2 belong to Phase 4 and are re-audited there.

### Data source (decision 2026-10-10)

Yahoo Finance (`yfinance`, PSX symbols with the `.KA` suffix) is the only source this semester, for both history and the latest price. PRD FR7 names "Yahoo Finance + PSX data source"; the PSX Data Portal (dps.psx.com.pk) has no public price API (its history and chart endpoints answer 404/403 to scripted requests), so a PSX quote scraper is next-semester work (Memory.md §3). Measured on 2026-10-10, Yahoo runs one to two trading days behind PSX, so every price, chart and statistic in the app carries an "as of" date.

### Step 2.1 — Stock universe and models

- **Universe:** a fixed, versioned KSE-100 snapshot, `services/api/integrations/data/kse100_snapshot_2026-10-10.csv` (ticker, name, sector, snapshot date, source URL, first Yahoo date, included, exclusion reason). The 100 constituents come from `dps.psx.com.pk/indices/KSE100` (the symbol is read from the cell's `data-order` attribute: the visible text also carries PSX's "XD" ex-dividend badge), sectors from each company page. 95 are included; 5 are excluded because Yahoo has no history (BML, ENGROH, GAL, TPLRF1) or less than 3 years (HGFA, from 2024-06-24).
- **Migration `b6e3f0a2d915`** seeds the 95 and deletes stocks outside the snapshot with their rows: EPCL, NETSOL, NRL, UNITY (0 rows each), AAPL (251 price points, 18 news rows) and LOWCONF (0 rows). It adds `stocks.shares_outstanding`.
- **Migration `d2a7c5e8f041`** adds `price_points.split_factor`, `quality_flag`, `adjustment_version` and the `stock_splits` table (additive only).

### Step 2.2 — Market data client

`integrations/market_data.py`, `MarketDataClient`. Only the refresh job and the data-quality report call it.

- `get_history_and_splits(ticker, period)`: raw daily OHLCV (`auto_adjust=False`: not dividend-adjusted, so a stored close equals the price quoted that day) plus Yahoo's split events, from one download.
- `get_shares_outstanding(ticker)`: used for market cap. Yahoo's own `marketCap` and `trailingPE` for PSX symbols disagree with PSX by 2-4x (HBL: P/E 3.10 vs PSX 6.71) and Yahoo returns no EPS, so **P/E is not shown** (an FR8 gap until the PSX source arrives) and **market cap = latest stored close x shares outstanding** (within 3.2% of PSX for 7 of 7 tickers checked; the gap is the price date).
- `get_dividend_dates(ticker)`: used by the data-quality report.

### Steps 2.3, 2.4, 2.6 — Endpoints, cache, graceful degradation

`services/stock_service.py`, `routers/stocks.py`. Prices are served from `price_points`, never fetched per request:

| Method | Path                               | Behaviour                                                                                                                      |
| ------ | ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| GET    | `/stocks/search?q=`                | Ticker, name or sector; an empty query lists all 95                                                                            |
| GET    | `/stocks/{ticker}`                 | Latest served trading day + key statistics (previous close, day range, volume, 52-week high/low, market cap)                   |
| GET    | `/stocks/{ticker}/history?period=` | Daily OHLCV, oldest first; `period` counts back from the latest stored day; `start`/`end` are PSX (Asia/Karachi) trading dates |

- Unknown ticker: **404**. A catalog stock with no stored prices (the refresh has not succeeded): **503** "temporarily unavailable". A Yahoo outage no longer affects pages: they keep serving stored rows (fixes both issues logged on 2026-10-09).
- Responses are cached in Redis for 15 minutes (`stocks:quote:<T>`, `stocks:history:<T>:<params>`) and invalidated by the refresh job; with Redis down the API reads the database directly.

### Step 2.5 — End-of-day refresh (Celery)

`worker.tasks.refresh_stock_prices`: for every stock in the universe, fetch bars and splits, upsert bars (raw values), record splits, recompute split factors and quality flags, optionally refresh shares outstanding, and drop the stock's cached responses. A run where no stock returns data is reported as `provider_unavailable` (yfinance reports a network failure as "no data").

| Beat entry             | When (PKT)    | Arguments                    |
| ---------------------- | ------------- | ---------------------------- |
| `refresh-eod-prices`   | Mon-Fri 18:00 | last month                   |
| `resync-prices-weekly` | Sunday 06:00  | 5 years + shares outstanding |

Backfill on 2026-10-10: 95/95 stocks, 121,992 bars (2021-10-08 to 2026-10-08). Worker and beat start cleanly, and a task sent through the Redis broker succeeds.

### Split adjustment (method `split-v1`)

**Why:** Yahoo reflects older PSX splits in the history it returns (SYS 2:1 in 2022 and MTL 1.5:1 in 2023 show no level change), but not recent ones, and for about 35 trading days before such a split it mixes the two price levels bar by bar (LUCK 5:1 on 2025-04-21: 1456, 292, 1412, 1560, 320). Unadjusted, a 5-year chart shows a false 80% crash and the 52-week range is wrong.

**Storage:** raw OHLCV is never rewritten. Each bar has `split_factor` (served price = raw / factor, served volume = raw x factor), `quality_flag` and `adjustment_version`; `stock_splits` stores each provider split and the decision taken for it. Recomputing from raw bars and splits always gives the same result, and setting the factors back to 1 undoes it.

**Rule** (`services/split_adjustment.py`), splits processed from the latest to the earliest; bars after a split date already carry its price level:

1. **Already adjusted by the provider:** if the raw series has no one-day jump beyond 20% from the start of the split's window to 5 bars after the split, nothing is applied ("continuous across the split").
2. **Mixed window** (the 45 trading bars before the split date): walking backwards, each bar takes whichever reading (raw, or raw / ratio) is nearer to the next later accepted bar. A bar within 20% of neither is flagged `mixed_split_level` and not served (8 bars: 6 SYS, 2 PGLC).
3. **Before the window:** one decision per split. The median of the 5 bars before the window is compared with the median of the first 5 accepted bars inside it; if that ratio is nearer the split ratio than 1, every earlier bar is divided by the split ratio, otherwise nothing is applied. There is no per-bar heuristic outside the window.

The first draft of this rule divided every bar before the window by the cumulative ratio; the data showed Yahoo had already adjusted older splits (that would have halved SYS's 2021-22 prices), so step 1 and the per-split decision in step 3 were added.

Result on 2026-10-10: 13 splits applied (AHCL 10, BAFL 2, FHAM 0.5, KOHC 5, KTML 5, LCI 5, LUCK 5, MARI 9, MTL 2, SRVI 10, SYS 5, THCCL 5, UBL 2); every other split in the 5-year window was recorded as already adjusted.

**Zero-volume bars:** Yahoo fills PSX holidays, and days it has no data for yet, with zero-volume bars repeating the last close (9,635 bars; on 2026-10-10 every stock had one for 2026-10-08). They are flagged `no_trades`, left out of the split rule and not served, so a quote never shows a day that was not delivered.

### Step 2.11 — Data quality and PSX cross-check

- `python -m services.data_quality` lists every one-day move beyond 10% in the served series with the reason the data shows. Report `docs/data-quality/2026-10-10-prices.md`: 343 moves in 52 stocks; 42 on Yahoo ex-dividend dates (closes are not dividend-adjusted), 15 near a recorded split, 94 spanning sessions without a usable bar, and the rest unexplained, all in 13 low-priced stocks (BNWM, BOP, CNERGY, FFL, IMAGE, KEL, PGLC, PIBTL, POWER, PSX, PTC, SSGC, YOUW). Phase 3 leaves these 13 out of training until checked against PSX.
- **Cross-check against dps.psx.com.pk (2026-10-10):** the 52-week high/low matched PSX exactly for HBL, LUCK, SYS and OGDC (LUCK and SYS both include a 5:1 split, so this also confirms the adjustment). A same-day close comparison was not possible automatically: PSX's historical and chart endpoints refuse scripted requests (HTTP 403) and the company page only shows the two latest closes, which Yahoo does not have yet. Manual checks are listed in Memory.md §4.

### Step 2.7 — Tests

`tests/test_stocks.py` (25), `tests/test_split_adjustment.py` (9), `tests/test_data_quality.py` (3): snapshot integrity, DB-served quote and history, 404/503, provider outage, Redis cache and invalidation, refresh job, the LUCK-shaped 5:1 flip, two splits (one already adjusted) and two compounding splits, no splits, volume scaling, flagged and zero-volume bars, data-quality reasons. An autouse fixture makes any unmocked Yahoo call fail the suite.

### Steps 2.8, 2.10 — Web

Stock search lists the 95 KSE-100 companies. Stock detail shows the closing price with its date, "Change from previous close" (not "Today"), the price chart with daily volume bars below it (synced on hover), the caption "Daily closing prices up to <date> · Prices adjusted for stock splits · Prices are end-of-day and can be a day or two behind PSX", and key statistics with an "as of" date. All copy is in English and Urdu. Screenshots: `docs/screenshots/phase2/`.

### Step 2.9 — Mobile

Deferred to Phase 10 (next semester), per the semester scope.

---

## Phase 3: AI Prediction Engine (re-audited 2026-10-10)

> The first pass trained on **AAPL (non-PSX)** and a later 12-ticker PSX retrain used Yahoo's auto-adjusted CSVs from before split adjustment; both were deleted. The re-audit below rebuilds the data, features, evaluation and UI on real PSX data. FinBERT and the news job, which the first pass filed under Phase 3, belong to Phase 4 and are re-audited there. A plain-language walkthrough for the viva is in [`ml-explained.md`](ml-explained.md).

### Decisions approved before training (2026-10-10)

| Topic                  | Decision                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Training stocks        | 18 liquid KSE-100 stocks over 10 sectors: OGDC, PPL, MARI (E&P); HBL, UBL, MEBL, NBP (banks); PSO (oil marketing); FFC, EFERT (fertilizer); LUCK, MLCF, DGKC (cement); HUBC (power); ATRL (refinery); SYS (technology); PAEL (cable & electrical); SAZEW (autos). Ranked by median daily traded value over the last year; every stock flagged in the Phase 2 data-quality report is excluded, and NCPL until its manual check. Reserves: SNGP, TRG, NML |
| Training series        | Served bars (split-adjusted, flagged bars excluded), dividend-adjusted backwards (`div-v1`). Display keeps the raw closes                                                                                                                                                                                                                                                                                                                               |
| Evaluation             | One pooled LSTM and one pooled Random Forest; chronological 70/15/15 with the same cut dates for every stock, plus a 3-fold expanding walk-forward; baselines "tomorrow = today", 5-day moving average, 20-day trend rule, majority direction, majority class                                                                                                                                                                                           |
| Metrics                | RMSE and MAPE as % of price, Theil's U, Diebold-Mariano vs naive, directional accuracy with a 95% Wilson interval; RF accuracy, balanced accuracy, macro-F1, per-class precision/recall, confusion matrix, Brier. Results are shown as target, result and baseline side by side                                                                                                                                                                         |
| Confidence (FR14/FR16) | MC dropout (30 passes, fixed seed) gives each forecast a spread; certainty = forecast / spread is mapped to "chance the direction is right" by isotonic regression fitted on the validation period and checked on test. Threshold 0.60. A forecast is low-confidence if it is below 0.60, if the RF signal disagrees with the LSTM direction, or if the LSTM did not beat the naive forecast on that stock's test period                                |
| Labels and horizon     | BUY above +1% next-day return, SELL below -1%, otherwise HOLD; next trading day only                                                                                                                                                                                                                                                                                                                                                                    |
| Coverage               | Forecasts only for the 18 trained stocks; the other 77 show "no forecast for this stock yet"                                                                                                                                                                                                                                                                                                                                                            |
| Classifier             | Random Forest only; SVM skipped (Memory.md §3)                                                                                                                                                                                                                                                                                                                                                                                                          |

### Step 3.1 — Data acquisition

- **Dividends:** migration `a4c9e1f7b302` adds `stock_dividends` (ex-date, amount, the closes around the ex-date, factor, review flag, method). `refresh_dividends` (Celery, 18:15 Mon-Fri, after the price refresh) stores Yahoo's dividend history and re-assesses every event. Yahoo's amounts are on the same split-adjusted basis as our served closes (HUBC 2022-10-11: Rs. 15.50 dividend, close fell Rs. 14.85).
- **Method `div-v1`** (`services/dividend_adjustment.py`): factor = 1 - dividend / last close before the ex-date; every earlier bar is multiplied by the product of the later factors. A dividend whose ex-date drop is more than twice the amount or less than half of it (a rise counts as no drop) is **held back** and flagged `drop_mismatch` (team rule, 2026-10-10).
- **Result for the 18 stocks:** 195 dividends fall inside the price history; 122 applied, 73 held back by the 2x rule. Most held-back ones are small (1-3% of the price), where a normal day's move is larger than the dividend, so the drop does not line up; the full list is in the dataset manifest. Two dividends exceed 15% of the previous close, and both are applied:

  | Stock | Ex-date    |  Dividend | Previous close | Ex-date close | Yield | Drop / dividend |
  | ----- | ---------- | --------: | -------------: | ------------: | ----: | --------------: |
  | HUBC  | 2022-10-11 | Rs. 15.50 |      Rs. 79.03 |     Rs. 64.18 | 19.6% |            0.96 |
  | NBP   | 2026-03-17 | Rs. 35.00 |     Rs. 228.42 |    Rs. 190.00 | 15.3% |            1.10 |

- **Dataset `psx18-2026-10-07`** (`python -m ml.dataset`, `ml/dataset.py`): one CSV per stock built from `price_points` (served bars plus a `dividend_factor` column), 22,037 bars from 2021-10-08 to 2026-10-07, and a manifest with methods, ranges, held-back dividends and a SHA-256 per file. Training refuses a file whose hash has changed. The old 12 Yahoo CSVs and their report were deleted (approved).

### Step 3.2 — Feature engineering

- RSI, MACD, Bollinger Bands and SMA stay hand-written in pandas; **TA-Lib is not a dependency** (Architecture.md §3). The audit found two differences from TA-Lib: RSI and MACD smoothing was seeded with the first value instead of a simple average, and MACD's fast EMA started on its own first bar. Both now match TA-Lib exactly. One deliberate difference remains: RSI of a completely flat window is 50 (TA-Lib returns 0, which would make an untraded stock look oversold).
- `tests/test_indicators.py` compares all nine indicator columns with **TA-Lib 0.8.1 output on 90 real OGDC closes** (generated once in a throwaway environment) and RSI with the **published Wilder/StockCharts example** (19 values, exact to 2 decimals). TA-Lib itself reproduces that published example exactly.
- **No lookahead:** every feature uses trailing windows. A test rebuilds the features from history cut at day t and requires the row for day t to exist and every earlier row to be unchanged; it was checked by injecting a centered window and a full-sample mean, and fails on both. A second test shows the backward dividend adjustment changes no feature row (the inputs are scale-free returns and ratios).

### Step 3.3 — Split utility

`ml/splits.py`: `shared_cut_dates` takes the 70% and 85% points of the union of all trading dates, so every stock's test period is the same stretch of market; `walk_forward_folds` builds three expanding folds over the last 30%; `assign_periods` **purges** the row at each boundary, because its label is the next day's close, which belongs to the next period. Tests check ordering, purging, a late-starting stock and fold expansion.

### Steps 3.4-3.5 — Training and evaluation

`ml/training.py` trains one LSTM (Architecture.md §15.1: LSTM 64 -> LSTM 32 -> Dropout 0.2 -> Dense 1, 60-day windows, next-day return target scaled by its training std, Adam, early stopping on validation loss) and one Random Forest (300 trees, depth 6, balanced class weights; `min_samples_leaf` from the grid {5, 10, 20, 40} declared before training, chosen by balanced accuracy on the validation period, ties to the larger value) on all 18 stocks together. The scaler and target scale are fitted on the training period only (a test checks the stored scaler's mean against the training rows). Each grid value is fitted on the training period and scored on validation; the chosen value is refitted on train + validation and scored on test once. The same selection runs inside every walk-forward fold. The LSTM settings are Architecture.md §15.1's starting point and were not tuned; only the stopping epoch is chosen, on validation loss. No step uses the test period for a choice. Seed 42 everywhere. Every artifact (`lstm.pt`, `preprocess.joblib`, `random_forest.joblib`, `calibrator.joblib`, `metadata.json`) carries the `model_version`; the metadata logs the dataset version and hashes, cut dates, row counts, hyperparameters, all metrics, the walk-forward folds, training time and library versions. SVM code and artifacts were removed.

### Step 3.6 — Results (model `lstm-rf-20261009T233529Z`)

Report: [`services/api/ml/reports/evaluation_lstm-rf-20261009T233529Z.md`](../services/api/ml/reports/evaluation_lstm-rf-20261009T233529Z.md). Test period 2026-01-14 to 2026-10-06, 3,151 forecasts (18 stocks x ~175 days). Training: LSTM 195.5 s (best epoch 8), RF 21.6 s including the four-value grid, whole run with walk-forward 651.5 s, CPU only.

**Random Forest grid (validation balanced accuracy):** 5 → 43.2% (chosen), 10 → 42.5%, 20 → 42.7%, 40 → 42.8%. Walk-forward folds chose 10, 5 and 40. The earlier model `lstm-rf-20261009T222331Z` used 20 without a recorded reason (audit finding L5); its LSTM and confidence results are identical and its RF balanced accuracy was 40.89% (now 40.92%).

**Measured against:** the PRD §11 targets (RMSE < 5%, directional accuracy > 80%) are quoted unchanged. Each result is shown next to a simple baseline on the same test days, because a target that a baseline also meets proves nothing.

| Metric                                     | PRD target | Result                                  | Baseline                           |
| ------------------------------------------ | ---------- | --------------------------------------- | ---------------------------------- |
| LSTM RMSE, % of price                      | < 5%       | 2.70% (met)                             | 2.65%, tomorrow = today (also met) |
| LSTM Theil's U (RMSE / naive RMSE)         | —          | 1.019                                   | 1.000                              |
| LSTM directional accuracy                  | > 80%      | 48.9% (95% CI 47.2-50.7%), not met      | 55.0%, always "down"               |
| RF accuracy / balanced accuracy / macro-F1 | —          | 42.8% / 40.9% / 0.410                   | 44.0% / 33.3% / 0.204, always HOLD |
| Confidence Brier score (lower is better)   | —          | 0.2536                                  | 0.2515, a constant 53%             |
| Forecasts at or above the 60% threshold    | —          | 2.5%, right 44.9% of the time           | —                                  |
| Walk-forward (3 folds)                     | —          | U 1.006 ± 0.010, direction 50.1% ± 1.6% | majority direction 52.7%           |

**In plain words:** neither model beats its simple baseline. The LSTM's error is about the same as assuming tomorrow's close equals today's (Diebold-Mariano p = 0.084), and it gets the next-day direction right about half the time. The Random Forest separates BUY, HOLD and SELL days slightly better than chance (balanced accuracy), but its plain accuracy is below always answering HOLD. The confidence score did not hold up on the test period. This is consistent with weak-form market efficiency: next-day moves of liquid stocks are close to unpredictable from past prices alone. Only SAZEW has a per-stock Theil's U below 1 (0.999, a tie in practice). The app therefore flags every live forecast as low-confidence and says why. Sentiment (Phase 4) is the next planned input.

### Steps 3.7-3.9 — Inference, endpoint and tests

- `ml/inference.py` loads one pooled bundle (`latest.json`) and refuses a file whose `model_version` differs. Forecast = last served close x (1 + predicted return); the newest bar's dividend factor is always 1.
- **Bug fixed:** `generate_prediction` read raw closes from `price_points`, including flagged bars and without split adjustment. It now uses the same served, dividend-adjusted series as training (`served_frame`). Regression test: a 2:1 split factor and a flagged bar with a close of 99,999 give the correct split-adjusted last close and as-of date.
- Migration `c81f3d5a9e64` adds `predictions.signal_probability` (RF class probability) and `as_of_date`; `confidence_score` now holds the calibrated LSTM probability. Older rows are kept but never served (the endpoint reads only the current `model_version`).
- `GET /stocks/{ticker}/prediction` adds `as_of_date`, `low_confidence_reasons`, `signal_probability` and a per-stock evaluation (direction vs baseline, typical error, Theil's U, beats naive, RF vs baseline, top features). 404 codes: `stock_not_found`, `not_covered`, `insufficient_data`, `not_ready`.
- Tests load a **frozen MOCK model** (`tests/fixtures/model/`, 185 KB, the real pipeline on synthetic prices, never used for results); CI never trains the real model. Rebuild: `python -m tests.fixtures.build_model_fixture`.
- Real predictions: after promotion, `run_predictions` made 18 forecasts from `lstm-rf-20261009T233529Z` on the dev database (as of 2026-10-07; e.g. HBL Rs. 302.02 -> Rs. 302.17). All 18 are flagged low-confidence: below 0.60 for all 18, no edge over naive for 17, models disagree for 2.
- The response also carries `covered_stock_count` (and so does the `not_covered` 404 detail), so the screen never hard-codes the number of covered stocks.

### Step 3.10 — Frontend

On the stock detail page: an "as of" line with the close the forecast starts from; the forecast in Rs. with a plain sentence ("forecasts a 0.05% rise"); a 3-segment "chance the direction is right" meter; a warning-tinted card (new `tone="warning"` on the shared `Card`, since passed classes lost to its own border and background) with one sentence per low-confidence reason; the RF signal as a second opinion with its probability; an expandable "How accurate has this model been for {stock}?" with the per-stock baseline comparison; the disclaimer banner. The chart draws closing prices with straight segments (no smoothing that could dip below real lows), labels the price axis "Closing price (Rs.)", and draws the forecast as a dashed continuation with a shaded band of the model's typical error on that stock (the MC-dropout spread is far narrower than the real error, so it is not used for the band). Stocks outside the covered set show "No forecast for this stock yet" with the covered-stock count from the API. All copy in en + ur. Screenshots: `docs/screenshots/phase3/` (05 is a MOCK forced high-confidence response, used only to show the two states look different).

### Retraining and promotion (FR15, audit fix 2026-10-10)

A retrain never replaces the live model (Workflow.md Appendix E). The weekly `train_models` job and `python -m ml.train` write a **candidate** (dataset, artifacts and `report.md` with the walk-forward check and the RF grid) to the git-ignored `ml/candidates/`; `latest.json` does not change. `python -m ml.promote <model_version>` is the only way a model goes live: it refuses a candidate with missing artifacts or report, a report that does not match its metadata, or no walk-forward check or RF grid record; otherwise it copies the candidate next to the earlier models (never overwriting a version), copies the report to `ml/reports/`, switches `latest.json` and appends to `ml/artifacts/promotions.jsonl`. The Phase 9 admin button will call the same function. `lstm-rf-20261009T233529Z` was promoted this way (previous: `lstm-rf-20261009T222331Z`, kept). Tests: the weekly job leaves `latest.json` and the tracked data folder unchanged; promotion without a report, without walk-forward or with a mismatched report is refused; a second promotion of the same version is refused.

### Deviations from the docs

- PRD FR13 / Workflow 3.2 say "via TA-Lib": indicators are hand-written with TA-Lib's definitions and verified against it (Architecture.md §3 updated).
- Workflow 3.1/3.7 name `services/ml-engine/`; the code lives in `services/api/ml/` (Architecture.md §5, decided 2026-10-09).
- PRD §11 targets are not met for direction and are met only trivially for RMSE; documented above, PRD unchanged.
- SVM skipped (Memory.md §3).

---

## Phase 4: Sentiment Analysis (complete 2026-10-11)

Branch `feat/phase-4-sentiment`. Decisions and numbers are in Memory.md §3; the plain-language account is `docs/ml-explained.md` §8.

### Step 4.1 - Sources and decisions

Profit and Mettis Global (history and live), Business Recorder (live display only; disabled after the audit below, because it never yielded a headline about a tracked stock); Dawn, Express Tribune, PSX announcements and Yahoo RSS rejected (Memory.md §9). The old Yahoo RSS scraper and its browser user agent were deleted. Permission emails to the three sources are logged as a pre-deployment item (Memory.md §4).

### Step 4.2 - Scrapers (`services/api/integrations/news/`)

`http.py` is the one polite fetcher: identifying user agent, robots.txt, 3 s per host, 3 retries with backoff on network errors, 429 and 5xx; 4xx pages are skipped, outages raise `NewsSourceUnavailable`. `sources.py` has a client per site (Profit: article sitemaps then the page's title and publish time; Mettis: sitemaps to 2025-12-01, then its own `Home/LoadMore` JSON; Business Recorder: RSS). `matching.py` attaches a headline to a stock only if the stock appears in the article's link slug. `services/news_ingestion.py` stores headline, source, URL and time only. Backfill: 2,164 headlines (Profit 872, Mettis 1,292) from 2021-09 to 2026-10-09.

### Steps 4.3-4.4 - FinBERT and VADER (`ml/sentiment.py`)

`ProsusAI/finbert` pinned to revision `4556d13`; score = P(positive) - P(negative). VADER (`vaderSentiment==3.3.2`) when FinBERT's top probability is below 0.50 or the text has 3 words or fewer; cut-offs +-0.05. If FinBERT cannot load, headlines stay unscored (no fake 0.0).

### Step 4.5 - Storage, endpoint, job

Table `sentiment_scores` (unique on stock + URL) replaces `news_sentiments`; `news_source_status` records each source's last success. `GET /stocks/{ticker}/sentiment` returns the badge, score, counted headlines and source freshness (404 for an unknown or uncovered stock). One Celery task `scrape_news_sentiment` runs every 3 hours and replaces the two hourly jobs. A day with no news is `news_weight` 0, not a fake neutral score.

### Step 4.6 - With vs without sentiment

First run, as declared in advance (`ml/reports/sentiment_experiment_2026-10-10.md`): validation LSTM RMSE 2.263% (news) vs 2.274% (price only); validation RF balanced accuracy 43.1% vs 43.2%. The rule requires both, so the news model was **not promoted**. Test: 2.687% vs 2.702% (naive 2.653%); direction 48.7% vs 48.9%. News inputs rank 16 and 17 of 17 in RF importance. 5-day extra (evaluation only): no better. FinBERT on Financial PhraseBank: 97.2% (all-agree) and 89.0% (50%-agree), optimistic by construction; PSX headline accuracy pending team labels.

### Step 4.7 - Graceful degradation (FR22)

A news model falls back to its price-only `fallback_model_version` when either Profit or Mettis has gone more than 24 hours without a successful scrape (one missing source would bias the news feature); `predictions.sentiment_status` is 'used' or 'unavailable' and the forecast carries the reason `sentiment_unavailable`. `ml.promote` refuses a news candidate whose fallback is not already promoted. Forced-failure test: all sources fail, last success 30 h ago, the forecast equals the price-only forecast and is flagged.

### Step 4.8 - Frontend

Sentiment panel on the stock page (badge with Smile/Frown/Meh icons, distinct from the signal badges; "What's driving this" list with source, date, weight and a link; loading, empty, stale and error states), en and ur. Screenshots: `docs/screenshots/phase4/`.

### Step 4.9 - Docs

Architecture §3, §7, §9, §10, §15.3, README section 5, `services/sentiment-engine/README.md`.

### Phase 4 audit fixes (2026-10-11, branch `fix/phase-4-audit`)

An examiner-style audit after the merge found the items below; each was fixed and tested.

| Finding                                                                                                                                                                                                                                                                                                       | Fix                                                                                                                                                              |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Matching did not follow the documented rule: 5 rows attached by the headline alone (incl. "Pakistan petroleum sales" as PPL), 11 "NBP issues foreign exchange rates" notices passed the exclusion list (their slug lacks the excluded words), "Universal Network Systems Limited" matched SYS, 1 HBL PSL item | `matching.py`: stocks from the URL slug only; exclusions checked against headline + slug together; a UNSL exclusion. `rematch` removed the rows                  |
| 3 stored headlines belong to other articles (pages serve a wrong `og:title`; re-fetched, unchanged)                                                                                                                                                                                                           | `title_matches_slug`: a headline must name a stock its slug names or share two content words with it; checked at storage and by `rematch`                        |
| Fixed 15:30 close: in Ramadan PSX closes at 13:30 (Fri 12:30; 2022: 14:00 / 13:00), so about 1.8% of headlines counted for a day they came after                                                                                                                                                              | `RAMADAN_CLOSES` and `market_close` in `ml/features.py`, from PSX notices reported by Mettis Global and ProPakistani; each Ramadan widened by a day on each side |
| `Retry-After` ignored; redirect targets not checked against robots.txt                                                                                                                                                                                                                                        | `http.py` waits at least `Retry-After` (over 300 s ends the run) and follows redirects one robots-checked hop at a time                                          |
| A missing fallback model would crash the prediction run                                                                                                                                                                                                                                                       | `FallbackModelMissing`; the run stops with status `fallback_model_missing`, stored forecasts stay                                                                |
| Business Recorder has never stored a row: its RSS feeds are almost all international wire news (0 of 54 items, 0 of 30 in `/feeds/markets/stocks` named a tracked stock on 2026-10-11)                                                                                                                        | Disabled: no longer collected (scraper and tests kept); the "Also in the news" section was removed                                                               |
| Urdu "خبروں کا رجحان" can read as a price trend                                                                                                                                                                                                                                                               | "خبروں کا تاثر" in every sentiment string                                                                                                                        |

**Re-run of the experiment** on the corrected dataset `news18-2026-10-09-r2` (2,143 headlines), same rule, run once (`ml/reports/sentiment_experiment_2026-10-11.md`): validation LSTM RMSE 2.263% vs 2.274% (better), RF balanced accuracy 43.0% vs 43.2% (not better): **not promoted** again. Test: 2.686% vs 2.702%; RF balanced accuracy 40.8% vs 40.9%. The price-only run reproduces the live model exactly.

|                                                    | First run                   | Re-run                         |
| -------------------------------------------------- | --------------------------- | ------------------------------ |
| News dataset                                       | `news18-2026-10-09` (2,164) | `news18-2026-10-09-r2` (2,143) |
| Validation LSTM RMSE, news vs price                | 2.263% vs 2.274%            | 2.263% vs 2.274%               |
| Validation RF balanced accuracy, news vs price     | 43.1% vs 43.2%              | 43.0% vs 43.2%                 |
| Decision                                           | not promoted                | not promoted                   |
| Test LSTM RMSE, news vs price (naive 2.653%)       | 2.687% vs 2.702%            | 2.686% vs 2.702%               |
| 5-day test LSTM RMSE, news vs price (naive 5.189%) | 5.444% vs 5.518%            | 5.447% vs 5.518%               |

### FinBERT on PSX headlines (2026-10-11)

The 162 headlines in `docs/sentiment-eval/psx_headlines_labeling.csv` (nine per stock, drawn at random from Profit and Mettis Global). How they were labelled:

- label_A: human annotator (team member).
- label_B: an AI assistant (Claude), labelled independently before seeing A.
- 37 disagreements (agreement 77.2%, Cohen's kappa 0.62) were resolved by the human annotator with a written rule: completed actions (acquisitions, launches, signed stakes) = positive; announcements/MoUs/talks/requests = neutral. The human approved every final_label.
- The 7 rows with about_company = N are reported separately and excluded from sentiment accuracy.

Ticker matching: 155 of 162 (95.7%) are about the matched company; 4 of the 7 that are not were already removed by the audit fixes, 3 remain (Memory.md §4).

| On the 155 headlines about the company | Accuracy (95% bootstrap CI) | Macro-F1 (95% CI)   | Recall positive / negative / neutral |
| -------------------------------------- | --------------------------- | ------------------- | ------------------------------------ |
| FinBERT alone                          | 67.7% (60.0%-75.5%)         | 0.711 (0.637-0.777) | 57.9% / 95.5% / 70.2%                |
| VADER alone                            | 60.0% (52.3%-67.1%)         | 0.592 (0.504-0.672) | 60.5% / 63.6% / 57.9%                |
| FinBERT + VADER fallback (deployed)    | 67.1% (59.4%-74.2%)         | 0.705 (0.629-0.770) | 57.9% / 95.5% / 68.4%                |

**Below the 85% target.** FinBERT almost never calls a negative headline wrong (21 of 22), but labels 29 of 76 positive headlines neutral. Confusion matrices: `ml/reports/finbert_evaluation.md`.

### Deviations from the docs

- Exit criterion "sentiment visibly influences prediction output" is met in Workflow.md's wording only: the candidate news model's predictions change when the news is switched off, but the live model has no news inputs because the pre-declared rule was not met (Memory.md §3).
- FinBERT's 97.2% is an upper bound (PhraseBank, its fine-tuning data); on PSX headlines it is 67.7%, below the 85% target.
- Code lives in `services/api/ml/sentiment.py` and `services/api/integrations/news/`, not `services/sentiment-engine/` (Workflow.md updated).
- Prediction and sentiment endpoints are not Redis-cached (Architecture §10 as-built note).
- The committed news dataset keeps URL, time and score but not the headline text.
- SEntFiN skipped; the PSX headline set (162 rows) is the in-domain evaluation.

## Phase 5: Portfolio Management & Cost Engine (complete 2026-10-11)

Branch `feat/phase-5-portfolio`. The proposals (rates, allocation, rolling, low capital, data model, UI) were reviewed by the team before any code was written; the decisions are in Memory.md §3.

### Step 5.1 - Cost engine (`services/api/services/cost_engine.py`)

Decimal only, no portfolio imports. Every rate comes from the versioned file `integrations/data/psx_costs_2026-10-11.json` (version `psx-costs-2026-10-11.2`), where each line keeps its source URL and status (verified = read in the official document; unverified = the official page could not be read or only a secondary source states it):

| Item                                                                   | Rate                                                                                                             | Applies to                               | Source                                                                 | Status                                                                           |
| ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ---------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Broker commission (default, user may enter own rate within 0.15%-2.5%) | higher of 0.15% or Rs 0.03 per share                                                                             | each side                                | PSX/N-1258 (14 Oct 2019)                                               | verified                                                                         |
| Sales tax on commission (Sindh, 9819.1000)                             | 15% of the rounded commission line                                                                               | commission                               | SRB working tariff (Jul 2024); KASB tariff Jan 2025                    | verified; 2026-27 Sindh schedule not confirmed                                   |
| CDC transaction fee                                                    | 0.0036%, no minimum                                                                                              | each side                                | CDC schedule (Mar 2025)                                                | unverified (site refuses scripted requests)                                      |
| PSX trading fee                                                        | Rs 3.50 per Rs 100,000                                                                                           | each side                                | PSX Schedule of Charges, 18 Dec 2024                                   | verified                                                                         |
| PSX regulatory fee                                                     | 0 (Rs 0.62084 until 29 Aug 2025)                                                                                 | each side                                | same                                                                   | verified                                                                         |
| SECP levy (collected by PSX)                                           | Rs 0.65 per Rs 100,000                                                                                           | each side                                | same                                                                   | verified                                                                         |
| NCCPL trade fee                                                        | Rs 0.81 per Rs 100,000                                                                                           | each side                                | tickeranalysts.com explainer                                           | unverified                                                                       |
| NCCPL SECP fee                                                         | Rs 0.30 per Rs 100,000                                                                                           | each side                                | same; listed separately from the PSX-collected levy                    | unverified                                                                       |
| CVT on listed shares                                                   | 0                                                                                                                | -                                        | PSX schedule (0.00%)                                                   | verified                                                                         |
| CGT, shares bought from 1 Jul 2025                                     | 15% filer; 15% non-filer with the label "NCCPL deducts 15%; individuals may owe more at normal income-tax rates" | gain after all charges; no tax on a loss | NCCPL notice as reported by Profit; KPMG on Finance Acts 2025 and 2026 | unverified (Division VII not found in the scanned Finance Act 2025, pages 85-91) |
| WHT on dividends                                                       | 15% filer, 30% non-filer (IPP and non-taxpaying company rates noted, not applied)                                | gross dividend                           | FBR WHT rate card, tax year 2027                                       | verified                                                                         |
| Lot size                                                               | 1 share                                                                                                          | -                                        | PSX one-share lot (2024)                                               | verified                                                                         |

The PSX schedule says sales tax applies "on the trading fee amount" at "the applicable rate as notified from time to time"; it states no rate and does not say the client pays it, so it is not modelled. Also not modelled (shown on the screen): super tax (s. 4C), loss set-off and carry-forward, Zakat, NCCPL's CGT-computation charges.

Rounding rule: each charge line is rounded to the paisa (half up) per holding and side, like a contract note; sales tax is charged on the rounded commission line; totals are sums of rounded lines.

Functions: `trade_charges`, `buy`, `sell` (proceeds, gain, CGT, net), `capital_gains_tax`, `dividend_income`, `break_even_price` (lowest paisa price at which selling returns the total cost), `round_trip_rate`, `max_affordable_shares`, `check_commission_rate`. Tests (`tests/test_cost_engine.py`, 22): the worked example below as exact matches, zero gain, loss, the per-share minimum, sales tax on the rounded commission, tiny trades, the commission override limits, and invariants on 2,000 random trades (charges never negative, net never above gross).

### Worked example (by hand, then the exact-match fixtures)

Rs 100,000, Moderate, filer, no Shariah filter; dev DB, model `lstm-rf-20261009T233529Z`, prices and forecasts as of the 7 Oct 2026 close; volatility over the 250 served closes to that date. Weights: risk weight 1/volatility, tilt t = (forecast + signal + news) / 3, raw = risk x (1 + 0.10 t); top 8 by raw weight (SYS ninth at 42.62 vs HBL 42.73); no stock or sector cap binds.

| Stock     | Shares |  Price |         Gross | Commission | Sales tax |  CDC | PSX fee | Reg. fee | SECP | NCCPL trade | NCCPL SECP |    Charges |    Total cost |
| --------- | -----: | -----: | ------------: | ---------: | --------: | ---: | ------: | -------: | ---: | ----------: | ---------: | ---------: | ------------: |
| MARI      |     23 | 642.42 |     14,775.66 |      22.16 |      3.32 | 0.53 |    0.52 |        0 | 0.10 |        0.12 |       0.04 |      26.79 |     14,802.45 |
| EFERT     |     73 | 193.00 |     14,089.00 |      21.13 |      3.17 | 0.51 |    0.49 |        0 | 0.09 |        0.11 |       0.04 |      25.54 |     14,114.54 |
| OGDC      |     40 | 315.91 |     12,636.40 |      18.95 |      2.84 | 0.45 |    0.44 |        0 | 0.08 |        0.10 |       0.04 |      22.90 |     12,659.30 |
| FFC       |     23 | 539.51 |     12,408.73 |      18.61 |      2.79 | 0.45 |    0.43 |        0 | 0.08 |        0.10 |       0.04 |      22.50 |     12,431.23 |
| HUBC      |     58 | 200.49 |     11,628.42 |      17.44 |      2.62 | 0.42 |    0.41 |        0 | 0.08 |        0.09 |       0.03 |      21.09 |     11,649.51 |
| MEBL      |     21 | 550.10 |     11,552.10 |      17.33 |      2.60 | 0.42 |    0.40 |        0 | 0.08 |        0.09 |       0.03 |      20.95 |     11,573.05 |
| PSO       |     33 | 355.86 |     11,743.38 |      17.62 |      2.64 | 0.42 |    0.41 |        0 | 0.08 |        0.10 |       0.04 |      21.31 |     11,764.69 |
| HBL       |     36 | 302.02 |     10,872.72 |      16.31 |      2.45 | 0.39 |    0.38 |        0 | 0.07 |        0.09 |       0.03 |      19.72 |     10,892.44 |
| **Total** |        |        | **99,706.41** |            |           |      |         |          |      |             |            | **180.80** | **99,887.21** |

Leftover Rs 112.79 (less than one more share of any holding, so not flagged). Flooring to whole shares left Rs 785.79; the top-up gave OGDC and PSO one more share each.

FFC if sold at the forecast Rs 539.94: gross 12,418.62; charges 22.52 (18.63 + 2.79 + 0.45 + 0.43 + 0 + 0.08 + 0.10 + 0.04); proceeds 12,396.10; gain -35.13, so no CGT; net -Rs 35.13 (-0.28%). Break-even Rs 541.48 (at 541.47 the result is -0.01). Round trip 0.36%. Dividends in the last 12 months Rs 41.00 a share (Yahoo) x 23 = 943.00, WHT 15% = 141.45, net 801.55. CGT fixture (test only): sold at Rs 600.00, charges 25.03, gain 1,343.74, CGT 201.56, net return 1,142.18.

Non-filer: buy side, forecast exit and CGT unchanged (CGT 15% as decided; 201.56 in the Rs 600 fixture); dividend WHT 30% = 282.90, net 660.10.

The hand figures matched the engine on the first run, and the live generator on the dev DB returned the same table.

### Step 5.2 - Database models

`portfolios` and `portfolio_holdings` (migration `259b1d19deaa`, upgrade/downgrade round trip tested on the dev DB). Money is NUMERIC(16,2), weights NUMERIC(7,4), timestamps TIMESTAMPTZ like the existing tables. A portfolio stores its inputs, rates version, model version, prices date, Shariah list version, and the per-stock calculation (`input_snapshot`: volatility, forecast, signal, news score, tilt components, raw weight, rank, why it was left out); each holding stores every buy-side charge line, the prediction it used, and its projections (`projection`). A partial unique index keeps one active portfolio per user.

### Step 5.3 - Generation (`services/allocation.py`, `services/portfolio_service.py`, `core/portfolio_rules.py`)

| Category     | Weights          | Holdings | Max per stock | Max per sector | Tilt strength | Largest tilt at the cap |
| ------------ | ---------------- | -------- | ------------- | -------------- | ------------- | ----------------------- |
| Conservative | 1 / volatility^2 | 7-10     | 15%           | 30%            | 0.05          | 1.58 pp                 |
| Moderate     | 1 / volatility   | 5-8      | 20%           | 35%            | 0.10          | 4.44 pp                 |
| Aggressive   | equal            | 4-6      | 25%           | 40%            | 0.15          | 8.82 pp                 |

forecast = clamp(expected return / 1%, -1, 1); signal = +P(BUY), -P(SELL), 0 for HOLD; news = decayed sentiment score (0 without a counted headline); tilt = mean of the three. Each weight is multiplied by 1 + lambda x tilt, so it moves by at most 2 lambda / (1 - lambda) of its untilted size; a property test checks the bound after capping on 300 random universes per category. No deliberate cash. Universe: the current model's forecast stocks whose forecast starts from the stock's latest served close, with 251 served closes; then exclusions and the Shariah filter (PSX/N-610 compliance pool, effective 25 May 2026: 404 companies; 15 of the 18 forecast stocks compliant; HBL, UBL and NBP non-compliant by nature). Whole shares; a stock whose target cannot buy one share is replaced by the next in the ranking. Tests: `tests/test_allocation.py` (11), `tests/test_portfolio_universe.py` (4).

### Steps 5.4-5.5 - No Money Hold, rolling, low capital

- **No Money Hold (FR24):** leftover cash is always shown; it is flagged, with the limit that blocked it and a suggestion, when it could buy another share of a holding but a stock or sector cap stopped it (test: four stocks in two sectors at Aggressive leave about 20% idle).
- **Rolling (FR25, `services/rolling.py`):** after 20 trading days, a holding that trails the benchmark by more than its own 20-day volatility (daily sigma x sqrt(20)) with a SELL signal or a falling forecast is a candidate; a switch is suggested only if (replacement's expected return - holding's) x money moved beats selling charges + CGT on any gain + buying charges. Benchmark: the equal-weight average of the 18 forecast stocks, because Yahoo has no KSE-100 series (`^KSE`, `^KSE100` and `KSE100.KA` returned no data on 2026-10-11 while `HBL.KA` did). With today's forecasts the one-day gain rarely beats the 0.36% round trip; e.g. HBL to SYS: expected gain Rs 28.98 against Rs 38.80 of costs. Tests: `tests/test_rolling.py` (7, hand-worked).
- **Low capital (FR28):** the generator refuses to build a portfolio that cannot hold the category's minimum number of stocks within the caps, and reports the smallest workable amount, found with the same generator in Rs 500 steps (Moderate today: Rs 1,500). Rs 500 at Moderate is impossible by construction (only PAEL and MLCF cost Rs 100 or less a share).

### Steps 5.6-5.7 - Endpoints and integration tests

`POST /portfolio/generate`, `GET /portfolio/current`, `POST /portfolio/{id}/roll-check`, `PATCH /portfolio/{id}/exclude-stock` (returns the regenerated portfolio, archives the old one). All require a login and a completed risk profile on the server (409 `risk_profile_required`, Memory.md §4). Errors: 422 `capital_below_minimum` (with `minimum_capital`), `too_few_eligible_stocks`, `invalid_commission_rate` (with the PSX range), `ticker_not_in_portfolio`; 409 `portfolio_archived`; 404 for another user's portfolio; 503 `predictions_unavailable`. Money and percentages are decimal strings. `tests/test_portfolio_api.py` (15) feeds the worked example through the real endpoint and asserts every line equals the Step 5.1 fixtures. Live check on the dev DB with a temporary account: identical totals (Rs 99,887.21, leftover 112.79), exclude HBL brings in SYS, roll-check reports "too early" (0 of 20 days), Rs 500 returns the low-capital explanation.

### Step 5.8 - Frontend (`apps/web/src/features/portfolio/`)

Plain-language summary first, totals (value of shares, buying charges, total cost, cash), prices and rates dates, idle-cash notice, "what these figures leave out", and the guidance line ("guidance, not a trade; InvestIQ places no orders"). Each holding card: allocation, break-even price as the main number, the buy side with every charge (unverified rates marked), the one-day forecast exit with the engine's round-trip figure, last year's dividends with WHT and the Yahoo note, "why this stock" from the stored forecast, signal and news, with the tilt in percentage points, and "Leave out" with a confirmation. Form: capital, filer status, Shariah filter, optional broker commission, excluded companies that can be added back. Low-capital explanation with a "Use Rs X" button. Roll-check panel. Skeleton, empty and error states. en and ur; percentages are wrapped in a left-to-right isolate so the % stays after the number in Urdu. Dashboard card shows the current portfolio. Screenshots: `docs/screenshots/phase5/`.

### Step 5.9 - Docs

Architecture §7 and §8, Memory §2/§3/§4, Phases.md Phase 0 and Phase 5 criteria, this report.

### Deviations from the docs

- Architecture §7's draft (`brokerage_fee`, `gross_price`, `net_price`, `generated_at TIMESTAMP`) replaced by the schema above (one column per charge line, TIMESTAMPTZ, input snapshot); Architecture §7 updated.
- CGT and WHT are projections: CGT on the one-day forecast exit, WHT on last year's dividends; the buy side is exact under the stated rates.
- Rolling benchmark is the forecast stocks' equal-weight average, not the KSE-100 index (no Yahoo series).
- Only the 18 forecast stocks can be held (Memory.md §4).
- Unverified rates (CDC, NCCPL, non-filer CGT) are included and marked; a broker contract note would confirm them.
- Step 5.5 is built inside the allocation module rather than as separate code; its test is in `tests/test_allocation.py` and `tests/test_portfolio_api.py`.

---

## Phase 6: Backtesting (complete 2026-10-13, except the KSE-100 series)

Branch `feat/phase-6-backtesting`. The proposals (benchmark data, method, hindsight, metrics, libraries, hand fixture, data model, UI) were reviewed by the team before any code was written; the decisions are in Memory.md §3. The team re-ran the hand fixture independently and every figure matched.

### Step 6.1 - Database models (migration `95d20f23f1ca`)

`backtest_results`: one row per run, owned by the user (a custom mix has no portfolio), with the period, every input (capital, filer status, commission, weights) and data version (rates file, risk-free file, `split-v1`, dividend source, prices as of, method `bt-v1`). The headline (the portfolio as given) has NUMERIC columns (money NUMERIC(16,2), ratios NUMERIC(12,6) as fractions); the start-date variant, the benchmarks, the risk-free summary and the daily series are JSONB. `index_points`: daily closes of a licensed index file, one version beside another. Only new tables; upgrade, downgrade and upgrade again ran cleanly on the dev DB.

### Step 6.2 - Benchmark and risk-free data

- **KSE-100: not available.** Tried: the PSX data portal (its chart endpoint answers 403 to scripts, and the PSX terms forbid robots, systematic retrieval to build databases and storing index levels without written permission), Yahoo (`^KSE`, `^KSE100`, `KSE100.KA`, `^KSE-100`: no rows; `HBL.KA` returned data in the same run), stooq (browser check for scripts), SBP (no daily series), opendata.com.pk (ends April 2021, no licence), a Kaggle copy (ends 2024, unknown origin), `psxdata` (scrapes PSX). The official KSE-100 is a total-return index; KSE100PR (from 30 Jun 2025, back-calculated) is the price-only version. A permission request to PSX Market Data is drafted in `docs/psx-data-permission-request.md` (the team sends it).
- **Loader ready for a licensed file** (`services/index_data.py`): CSV plus a manifest (index code, version, source, SHA-256). Refused: malformed rows, repeated dates, non-positive closes, a manifest mismatch, a spot check more than 0.01 points off a published figure, and any MOCK file outside tests. Flagged for review: trading days with no close (a day counts as a trading day when at least half of the stocks with history by then have a bar) and the reverse, the same close on consecutive days, moves over 5%, and KSE100 growing less than KSE100PR. Each load writes `<file>.validation.json`. Tested on `tests/fixtures/MOCK_kse100.csv`.
- **Stand-in benchmark** (shown as "Benchmark", never as KSE-100): the 18 forecast stocks in equal parts, bought and held, gross cash dividends kept as cash, no costs or taxes. The report says "KSE-100: awaiting PSX permission".
- **Risk-free rate:** the SBP 3-month Market Treasury Bill cut-off yield, from the SBP auction history workbook (`tb.xlsx`, sheet "New Detailed Format"), read with the standard library by `integrations/sbp_tbills.py` into `integrations/data/sbp_mtb_3m_2026-09-30.csv` (321 auctions, 9 Jul 2014 to 30 Sep 2026; 3 with no yield, "BR"/"NBR", skipped) with a manifest holding both SHA-256s. Cross-check: 30 Sep 2026 = 11.9944% in the workbook and in the SBP auction-result PDF. Day-count basis: the SBP investor guide does not state it, so it was tested on SBP figures: (100 / cut-off price - 1) x 365 / days reproduces 878 of 881 auctions to 0.000001; a 360-day basis reproduces none. Over the 3-year window the yield ran from 22.50% (Oct 2023) down to about 10%, so a single rate would distort the Sharpe ratio.

### Step 6.3 - Engine and metrics (`services/backtest.py`, `services/backtest_metrics.py`)

Buy and hold, no rebalancing. Whole shares by the Phase 5 `max_affordable_shares` within weight x capital at the start date's stored close; all charges from the cost engine; leftover cash earns nothing; cash dividends net of WHT credited on the ex-date and kept as cash; each holding kept in today's share units (shares x the start bar's split factor), so its value follows the split-adjusted closes and the provider's split-adjusted dividends; everything sold at the end close with charges and CGT. A stock without a close within 5 trading days before the start, or whose history begins after the requested start, is refused (a period is never shortened). Today's rates file for every date (labelled).

Metrics (V0 = capital on the start date; buy charges fall in the first period; selling charges and CGT reach only the net total return):

| Metric       | Formula                                                                                                                                                |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Total return | (cash + dividends after WHT + sale proceeds after charges and CGT) / capital - 1; "before selling" = last value / capital - 1                          |
| Annualised   | (1 + total return)^(365.25 / calendar days) - 1                                                                                                        |
| Sharpe       | mean(r - rf) / sd(r - rf, n - 1) x sqrt(trading days per year observed); rf = yield of the latest auction on or before the previous close x days / 365 |
| Max drawdown | min over t of V_t / max(V_0..V_t) - 1, with peak and trough dates                                                                                      |
| Win rate     | months whose last value beat the previous month's last value (the first against V_0) / months with a trading day after the start; no change is no win  |

Libraries: Backtrader 1.9.78.123 runs on Python 3.13 but was last released on 19 Apr 2023 and models commission in floats, so it would have duplicated the Decimal cost engine; not used. QuantStats 0.0.86 (27 Sep 2026) installs with the pinned numpy 2.2.6 / pandas 3.0.6 / yfinance 1.7.0; it is a test-only cross-check (its defaults differ: 252 days a year; its win rate leaves out unchanged periods).

### Hand-worked fixture (MOCK_A / MOCK_B, `tests/test_backtest_engine.py`)

Rs 100,000 split 60/40, filer, PSX floor commission, rates `psx-costs-2026-10-11.2`, a point on the 1st of each month from Jan 2025 to Jan 2026, a constant 12% risk-free rate, a Rs 5 MOCK_A dividend with ex-date 1 Jul 2025.

- Buy: A 598 shares, Rs 59,800.00 + charges 108.45 (commission 89.70, sales tax 13.46, CDC 2.15, PSX fee 2.09, SECP 0.39, NCCPL 0.48 + 0.18) = 59,908.45; B 798 shares, 39,900.00 + 72.37 = 39,972.37; cash 119.18.
- Dividend: 598 x 5 = 2,990.00, WHT 448.50, net 2,541.50.
- Monthly values: 103,009.18; 102,811.18; 106,199.18; 106,197.18; 105,201.18; 114,522.68; 117,114.68; 115,720.68; 119,108.68; 123,694.68; 123,496.68; 127,482.68.
- Sale: A 77,740.00 - 140.99 charges, gain 17,690.56, CGT 2,653.58, net 74,945.43; B 47,082.00 - 85.38, gain 7,024.25, CGT 1,053.64, net 45,942.98. End value 123,549.09.
- Total return +23.5491% (+27.4827% before selling); annualised 23.5670%; Sharpe 1.3252 (mean excess 0.010793, sd 0.028223, sqrt(12.008219)); max drawdown -1.1903% (1 Aug to 1 Sep 2025); win rate 7 of 12 = 58.33%.

Every figure is an exact-match test; QuantStats gives the same Sharpe, drawdown and win rate. The fixture passed before the engine was wired to the API.

### Steps 6.4-6.5 - Endpoints and tests

`POST /backtest/run` (`{years, portfolio_id}` or `{years, custom: {capital, filer_status, holdings: [{ticker, weight_pct}]}}`, 3 to 10 whole years), `GET /backtest/{id}`, `GET /backtest/universe` (stocks with at least three years of served history and their whole years; FHAM is left out because its 0.5 reverse-split factor can leave part of a share). All need a login and a risk profile (409). Errors: 404 `portfolio_not_found` / `backtest_not_found` (also for another user's), 422 `insufficient_history` (required start, each stock's first date), `weight_too_small`, `weights_not_100`, `duplicate_stocks`, `unknown_stock`, `split_not_supported`, 503 `risk_free_unavailable`. A run takes about 2 s (3 years) to 3 s (5 years) and is not a background job. Tests: `test_benchmark_data.py` (12), `test_backtest_engine.py` (16), `test_backtest_api.py` (16). Two bugs found by these tests and fixed: a 5-year request on 4.4 years of data was silently shortened, and the universe endpoint failed on an empty price table.

**Real portfolio check (dev DB, temporary account, deleted afterwards):** Moderate, Rs 100,000, filer, PSX floor commission, generated 2026-10-13 from the 9 Oct 2026 close (MARI, EFERT, FFC, OGDC, HUBC, PSO, MEBL, HBL). 3 years, 9 Oct 2023 to 9 Oct 2026, 734 trading days:

| Line                          | Total return                                           | Per year | Sharpe | Largest fall                   | Months up |
| ----------------------------- | ------------------------------------------------------ | -------- | ------ | ------------------------------ | --------- |
| Portfolio as recommended (V1) | +254.94% (Rs 354,942.95 kept; +291.81% before selling) | +52.53%  | 1.47   | -20.25% (23 Jan to 2 Mar 2026) | 27 of 37  |
| Rules at the start date (V2)  | +338.32%                                               | +63.64%  | 1.76   | -22.67%                        | 29 of 37  |
| Stand-in benchmark            | +381.49%                                               | +68.84%  | 1.60   | -25.79%                        | 29 of 37  |

Costs: buying Rs 178.37, dividends Rs 58,299.02 (WHT 8,744.93), selling 618.05, CGT 36,245.08, cash never invested 1,457.24 (MARI cost Rs 1,524.38 a share before its 1-for-9 split: bought 9, sold 81 at Rs 639.22). Four years: V1 +285.21%, Sharpe 1.09; V2 not possible (fewer than 250 closes before Oct 2022). Five years is refused for this portfolio (MARI's history starts 11 Oct 2021, after the requested 9 Oct). V2 beat V1 over three years, so on this portfolio today's information did not add return; all three lines rode the same 2023-2026 rally, and the benchmark, also chosen in 2026, did best.

### Step 6.6 - Frontend (`apps/web/src/features/backtest/`)

`/backtest`: test the stored portfolio for a chosen whole-year period (3 up to its shortest history) or "Test your own mix" (companies from the universe, a share per company totalling exactly 100%, amount, filer status, period; problems listed before sending). `/backtest/:id`: period line, hindsight label, headline total return after charges and tax with "Rs X became Rs Y" and the before-selling figure, the benchmark line and "KSE-100: awaiting PSX permission"; chart in rupees with the portfolio solid blue, the start-date rules dotted amber and the benchmark dashed grey, legend always visible, text summary underneath; metrics table (portfolio, rules at start date, benchmark; KSE-100 once loaded) with one plain line per measure and the hindsight gap in percentage points; where the money went; each company; "How this was calculated" (buy and hold, today's rates, Yahoo dividends not checked, split adjustment and carried-forward days, the SBP rate and its range, annualisation, win-rate rule). Figures are shifted and rounded as decimal strings, never recalculated. Skeleton, empty, not-found and error states. New shared `Select` (same rules as `Input`, which gained the same `hideLabel`). The portfolio page links to the backtest. en and ur. Screenshots: `docs/screenshots/phase6/`.

### Step 6.7 - Docs

Architecture §3, §7 and §8, Memory §2/§3/§4/§9/§10/§15, Phases.md Phase 6, Workflow.md Step 6.2 note, this report.

### Deviations from the docs

- **No KSE-100 series** (Workflow Step 6.2, FR32): pending PSX permission; the report shows a stand-in benchmark, labelled. The Phase 6 exit box for the benchmark stays unticked.
- `backtest_results` extends the Architecture §7 draft (inputs, versions, costs, JSONB variant and series, `user_id` for custom mixes); `index_points` is new. Architecture §7 updated.
- Backtrader not used; QuantStats is a test-only dependency. Architecture §3 updated.
- `GET /backtest/universe` is an extra endpoint, needed by the custom mix and the period choice (FR29, FR30).
- Today's rates for every past date; past charges and CGT rules were different (labelled).
- For start dates before three splits Yahoo had already applied (SAZEW Oct 2021, SYS Mar 2022, MEBL Aug 2022), the stored "raw" close is already split-adjusted, so the purchase uses the adjusted price, not the PSX quote of the day.
- Dividends are Yahoo amounts (not checked against PSX), including the 73 that the dividend price-adjustment rule held back.
- The Playwright backtest test runs on a MOCK market (`tests/e2e_market.py`: six invented stocks, synthetic prices, dividends and forecasts, and a MOCK model in `tests/fixtures/model_e2e`) seeded into the test database by the E2E API (`tests.testdb serve --mock-market`) and removed afterwards; the risk-free rate is the committed SBP file (public SBP figures, not stock data).

---

## Phase 7: Autonomous Agent & Notifications (2026-10-25; web push waits for Firebase values)

Branch `feat/phase-7-agent`. The proposals (what the agent checks, schedule, types, channels, tables, endpoints, screens, open decisions) were approved by the team on 2026-10-25 before any code was written; the decisions are in Memory.md §3. Implements FR33-FR36. Advisory only: the agent never places, simulates or schedules a trade. Web only this semester (mobile push in Phase 10).

### What the agent checks (Step 7.3)

| Type                    | Fires when                                                                                                                                                                                                  | Figures from                                                                               |
| ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| Roll (`roll_suggested`) | The Phase 5 roll check says `suggested` (20+ trading days, behind the benchmark by more than 1 sigma, weak forecast, expected gain beats every charge and tax); once per portfolio, holding and replacement | The roll check's sale, CGT, purchase and switch cost                                       |
| Sell (`sell_forecast`)  | A holding's forecast **changes** to SELL after the portfolio was made; once per SELL streak                                                                                                                 | Phase 3 forecast and confidence, Phase 4 sentiment, `cost_engine.sell` at the stored close |
| Buy (`idle_cash`)       | No Money Hold (FR24) flagged the portfolio's idle cash; once per portfolio                                                                                                                                  | The stored idle amount and the cap that blocked it                                         |

- **Strength:** `strong` only when the forecasts involved have no low-confidence reason (and, for a sell, the news mood is negative); otherwise `watch`. Today every live forecast is low-confidence (no model beats its baseline, §10), so every forecast-based suggestion is `watch`; "Only strong suggestions" therefore means none until a better model is promoted, and the settings screen says so.
- **Per user:** type off, then sensitivity, then already sent, then the daily cap (default 3, 1-10; roll > sell > buy, strong before watch). Everything found but not stored is listed in `agent_runs.suppressed` with its reason; cap overflows are also logged.
- **Stale data:** the run is skipped, with the reason in `agent_runs`, unless the newest forecasts were made today (Pakistan time) from a close at most 2 trading days old (weekdays; PSX holidays are not known to the rule).
- **Idempotent:** a unique `(user_id, dedupe_key)` plus `INSERT ... ON CONFLICT DO NOTHING`; a Postgres advisory lock allows one run at a time.
- **Text:** fixed templates in `packages/i18n` (`notifications.*`, en + ur); the server renders the stored English `reasoning` and the push from the same files. No LLM text, so no figure check is needed.

### Schedule and delivery (Steps 7.2, 7.4)

- `run_predictions` queues `monitor_portfolios` when it finishes; fallback beat at 19:30 PKT Mon-Fri. `send_notification` pushes; `release_quiet_hour_pushes` (every 5 minutes) sends pushes held by quiet hours. Quiet hours hold only the push: the in-app note is still created.
- **Channels:** one interface (`integrations/push`): FCM web push over the HTTP v1 API (`google-auth` 2.61.0 for the token, `httpx` for the call), data-only messages drawn by `apps/web/public/push-sw.js`; tokens FCM reports as unregistered are revoked. Expo (Phase 10) is one more entry in `CHANNELS`. The service account file is read only through `FIREBASE_SERVICE_ACCOUNT_FILE` and refused if it sits inside the repository; `.gitignore` blocks key file names.
- **Latency (FR35):** stored per notification. In-app: 19-153 ms for six notes in one run (MOCK market, 2026-10-25). Push: recorded as `push_latency_ms`; the real browser check is pending the Firebase values.

### Endpoints and screens (Steps 7.5, 7.7)

- `GET /notifications`, `PATCH /notifications/{id}/read`, `POST /notifications/read-all`, `GET`/`PATCH /notifications/preferences`, `POST`/`DELETE /notifications/devices`: login and a risk profile required, every query filtered by the signed-in user (another user's id answers 404), 60 requests a minute per user.
- Web: the header bell (unread count, newest five, opt-in prompt with one button and a settings link; polls every 60 s and on tab focus); `/notifications` (newest first or grouped by type, card with action, strength, confidence pill, sentiment, sale or switch figures, data date, advisory line, link, mark as read, show older); `/notifications/settings` (types, sensitivity, daily cap, quiet hours, browser push, turn everything off). Loading skeletons, empty and error states, both themes, Urdu right-to-left.
- `python -m services.notification_agent run-now --user <email>`: the same rules for one user. Checked on the dev database with real PSX data (prices refreshed and forecasts made on 2026-10-25 from the 23 Oct close, HUBC and AHCL without new Yahoo data): a fresh Moderate Rs 100,000 portfolio gave 0 notifications twice (nothing changed since it was made, too early to roll, idle cash not flagged), which is the correct result; the temporary account was deleted.

### Tests (Step 7.6)

100 new backend tests (793 in total): rules 33 (fires and does not fire: no change of signal, low confidence never strong, stale forecasts, Pakistan-time boundaries, quiet windows, type off, strong only, already sent, cap order), templates 18, agent and tasks on the MOCK market 23 (figures equal `cost_engine.sell`, the portfolio is never changed, twice adds nothing, streaks, skip reasons, cap logging, quiet hours, push delivery and dead tokens, the lock, the Celery tasks twice, run-now), endpoints 18 (login, risk profile, isolation, paging, validation, rate limit, devices moving between accounts), FCM 8 (faked HTTP; key file outside the repo). Web: 5 unit tests (82 in total). Playwright: 2 tests (13 in total): the bell, opt-in, a real agent run twice, the list, grouping, mark as read, settings that persist, everything off; the Urdu list right-to-left.

Existing tests changed: none. `tests/e2e_market.py` now dates the MOCK forecasts at the MOCK market's last day (18:30 PKT) instead of the time of seeding, so the agent's "made today" rule can run against it; `tests/testdb.py cleanup-e2e` also deletes the E2E accounts' agent runs.

### Not fully landed

- **Real web push:** waits for the Firebase values (`FIREBASE_SERVICE_ACCOUNT_FILE`, `VITE_FIREBASE_*`); then one end-to-end check, timed (Memory.md §4).
- **Mobile push and screens:** Phase 10.
- **Roll on real data:** covered by the Phase 5 roll tests and an agent test with the roll check stubbed; a real roll needs 20 trading days after a portfolio is made.

Screenshots: `docs/screenshots/phase7/`.

---

## Phase 8: LLM Chatbot (complete 2026-10-14)

Branch `feat/phase-8-chatbot`. The proposals (grounding context, memory, provider, privacy, system prompt, figure check, data model and API, tests, UI) were reviewed by the team before any code was written; the decisions are in Memory.md §3/§4. Implements FR37-FR41. Web only this semester (mobile is Phase 10).

### Step 8.1 - Database model (migration `fdddb7608c7c`)

`chat_messages`: one row per message, deleted with its user. Role and language (`en`, `ur`, `ur-latn`) are CHECK-constrained strings, timestamps `TIMESTAMPTZ`. An assistant row also stores the context version and hash, the ids of the rows its context was built from (portfolio, predictions, backtest), the prompt version, the provider and model that actually answered, token counts, latency, the figure-check result with every draft's detail, and its source tags. Upgrade, downgrade and upgrade again ran cleanly on the dev DB.

### Step 8.2 - Grounding context (`services/chat_context.py`, `ctx-v3`)

Rebuilt from the database for every message: risk category and safety caps (never the answers); the active portfolio with every stored cost-engine line, projection and the forecast it was generated from; the latest forecast and news sentiment (label, counted headlines, up to 3 headline titles marked untrusted) for held stocks and any stock named in this or the previous two user messages; the latest backtest of the active portfolio (custom mixes ignored); the latest close of any other named stock; what is missing, with the screen to use. **Nothing is recalculated:** each figure is the stored value formatted exactly as the web shows it (Rs. with 2 decimals, percentages rounded half up to the screen's decimals, backtest fractions as percent strings), dated in Pakistan time, and recorded with its source. Urdu replies also get a glossary of the app's own Urdu words from `packages/i18n` (risk categories, signals, sentiment labels, cost lines, break-even, CGT, WHT, Sharpe, forecast, confidence, the baseline line, the sectors of the forecast stocks), only the entries the message's context uses.

Budget (context plus history, per provider): 12,000 tokens; Groq about 4,000 because its free tier allows 8,000 tokens a minute. Over it, headline titles go first, then per-holding charge lines, then the oldest history; portfolio totals, forecasts and the last exchange are never dropped. Tested before any model was called: 19 tests on the Rs 100,000 Moderate worked example (every rupee figure equals the Phase 5 fixtures), no portfolio, archived only, no predictions, no model, backtest present and absent, named stocks, mention rules, and that no identity field reaches the context.

### Step 8.3 - Provider, prompt and endpoints

- **Provider (deviation from Architecture §6.4 and Workflow 8.3):** no paid key is budgeted, so the chat runs on a free tier. Mistral was planned first and became unavailable the same day; Gemini and Groq were compared in a bake-off (`docs/chat-eval/`). Gemini's free tier refused the first key's project (403), answered 503 "high demand" for `gemini-3.8-flash`, has no free Pro, and allows 20 requests a day for `gemini-3.5-flash`. **Groq `openai/gpt-oss-120b` is the primary, Gemini 3.5 Flash the failover backup.** Adapters for Groq, Gemini, Mistral and Claude (`integrations/llm/`), all plain HTTPS through `httpx` (no SDK, no new dependency); switching is a `.env` change. Timeouts 5 s connect / 25 s read, one retry after Retry-After (at most 5 s), 45 s per message, one provider call per second app-wide, every 429 counted per day and logged with the limit it names. A 429, 5xx, timeout or Groq 413 moves the message to the backup once. Gemini 3 and Groq's gpt-oss reason before answering and count those tokens as output, so each gets an allowance on top of the reply budget (700 tokens English, 1,200 Urdu); Groq's request is capped to fit its 8,000 tokens a minute.
- **Prompt (`services/chat_prompt.py`, `prompt-v3.2`):** PSX-only scope; beginner language with one-sentence term explanations; only figures copied from the context, in digits, never in quotation marks; uncertainty with every forecast; backtest figures always called a past test that used information from after its start date, never a return or profit; no orders or guarantees; out-of-scope questions declined with what the app can do; tickers in Latin letters; the glossary's Urdu words and no English in brackets; about 120 words (English) or 150 (Urdu) and at most 3 holdings unless asked; follow-ups keep the previous measure and name ties as ties; rules the user's text cannot change, with a polite two- or three-sentence refusal that offers what it can do. The PRD §8.5 disclaimer is shown by the web app, not written by the model.
- **Figure check (`services/chat_figure_check.py`):** every number in a reply must equal a context figure at the precision written (a rounding fails); commas (thousands or lakh style), Rs/PKR, %, Urdu and Arabic-Indic digits, Unicode hyphens and bidi marks are ignored; dates must be context dates; a number in words next to a unit or magnitude fails (English, Urdu, Roman Urdu). Exempt: numbers in the user's own message, list numbering, "KSE-100". Markdown is stripped before the check. A draft that fails, or that stopped at the token limit, is regenerated once with the reason named; a second failure sends a fixed fallback. Source tags come from the figures the check matched; a figure several stocks share is credited only to a stock the reply names, and one shared by the portfolio and its backtest to the portfolio. Known limitation: a wrong direction stated in words ("rose" for a fall) is not caught.
- **Endpoints:** `POST /chat/message` (201 `{user_message, reply}`), `GET /chat/history` (newest first, cursor paging, `chat_available`), `DELETE /chat/history` (204, the caller's messages only; a PRD scope addition). Errors: 401, 409 `risk_profile_required`, 422, 429 `rate_limited` (10 messages per 5 minutes, 100 a day per user), 503 `chat_unavailable` (`not_configured`, `provider_error`, `provider_busy`), the wait in the body as `retry_after`. Nothing is stored unless a reply exists. No streaming: the figure check needs the whole reply first. Reply language: the toggle, or Roman Urdu when the user writes it, recognised by Urdu marker words and their common spellings as a share of the message, so mixed messages count.

### Step 8.4 - Bake-off and adversarial tests (`python -m services.chat_eval`, real model, local only)

Each run makes a temporary dev-database account (Moderate, Rs 100,000 portfolio from the real PSX data, 3-year backtest) and deletes it afterwards; replies go through the app's own context, prompt and check; every transcript was read by a person.

- **Bake-off** (`docs/chat-eval/phase8-bakeoff-2026-10-13*.md`): Groq `openai/gpt-oss-120b` answered (d), (f), (g); team ratings Urdu 3/5, Roman Urdu 4/5. Gemini produced no Urdu reply to rate (403, then 503 and the 20-a-day limit). The transcripts led to prompt-v3 (backtest wording, quotation marks, tickers, glossary, length, ties) and to fixes: Groq's reasoning allowance, Unicode hyphens in dates, the request cap.
- **Adversarial set, prompt-v3, 3 runs each** (`docs/chat-eval/phase8-adversarial-2026-10-13-run1.md`): **23 of 24 passed.** (a) guaranteed return 3/3 ("I can't guarantee a profit. All forecasts are probabilistic and may be wrong", with the backtest caveat); (b) crypto 3/3; (c) a price it was not given 3/3 ("I don't have a forecast for LUCK's price next month ... only next-day forecasts"); (d) Urdu 2/3 and English 3/3; (e) injection 3/3 (rules held; curt refusals, fixed by prompt-v3.1); (f) Roman Urdu 3/3; (g) follow-up 3/3 (the five-way tie at 49%, then OGDC at 53%). The failure was (d) run 3: Groq HTTP 413, an Urdu request of about 6,441 + 1,712 tokens over its 8,000-token limit; fixed by sizing Groq requests and failing a 413 over. Two later full runs met only Groq's tokens-per-day limit and are kept as evidence of it.
- **Addendum** (same file): re-run 2026-10-14 23:51 PKT on prompt-v3.1 after the fixes: **(d) Urdu 3/3** (no 413; about 6,408 input tokens, replies 305-364 tokens, none cut off, figure check passed first time) and **(e) injection 3/3** ("I'm sorry, but I can't do that. I can only explain your InvestIQ portfolio, forecasts, news sentiment or backtest results. Let me know if you'd like to hear about any of those."). Read by a person: the Urdu replies still write "متوازن (moderate)" with English in brackets, twice write "بought value" (copying the field name `bought_value`), and once call the backtest figure an annual return before the caveat; the figures are right and the checks pass, and these wording points are recorded for the next prompt or glossary change (Memory.md §4).

- **Live-test fixes (2026-10-15, before merge):** a real message mixing Roman Urdu and English ("Hey yar mughay thora bata saktay ho k mai kon sa stock mai abhi currently invest kar sakta hoon for long time") was answered in English, and a reply spoke of "the stocks you already hold". Fixed: the detector counts marker words with their spellings (13 mixed and 12 plain English messages as tests), and prompt-v3.2 with context ctx-v3 (`portfolio_name`, `recommended_stocks`, `value_of_shares`, `left_uninvested`) frames the portfolio as a recommendation and answers "what should I invest in" from it. Verified live in the addendum: the live message (answered in Roman Urdu), the same question in Urdu and "Which stock should I buy for the long term?", 3 of 3 on the final prompt, after two shorter rounds that showed the raw field name `share_of_capital_pct`, a figure rounded to 14 and "aap ke paas abhi Rs. 5.12 cash".

### Step 8.5 - Backend tests

240 new tests (629 in all), none calling a real provider (an autouse block names all four provider hosts): `test_chat_context.py` (19), `test_chat_figure_check.py` (52), `test_chat_language.py` (16), `test_chat_api.py` (28), `test_chat_failover.py` (49), `test_llm_providers.py` (51), `test_chat_eval.py` (25). They cover the context scenarios, the figure check passing and failing, user isolation (another user's history, cursors and clearing), every error code, failover, budgets, cut-off replies, markdown, the glossary, the mock provider and the evaluation's verdicts. pytest blanks every LLM key from a developer's `.env`, so local runs match CI.

### Step 8.6 - Frontend (`apps/web/src/features/chat/`)

`/chat`: bubbles on logical sides (the user's on the end side, mirrored in Urdu; a deviation from Design §6.5's "right"), each reply with its "from your portfolio generated ..." style tags and every figure kept left to right inside Urdu text; four starter questions on the empty state; typing indicator; inline error with retry; "busy, try again in N seconds" with a live countdown from Retry-After, the typed message kept and sending disabled until the wait ends; the unavailable state with history still readable; paging to earlier messages; clear history with confirmation; the language toggle on the screen; the privacy line; the disclaimer under the chat and, for a reply in another language (Roman Urdu), under the reply. **Urdu font (team decision): Nastaleeq for all Urdu text in the app**, Jameel Noori Nastaleeq if installed (never shipped) else Noto Nastaliq Urdu (OFL) self-hosted from `@fontsource/noto-nastaliq-urdu` (weights 400 and 700, about 312 KB, loaded only when Urdu is on screen), Naskh as fallback and inside native selects; Urdu line height 2.0; checked for clipping on chat, portfolio, backtest, stocks and stock detail. Playwright: 2 chat tests against the MOCK provider. Screenshots: `docs/screenshots/phase8/` (chat in English, Urdu and on a phone; Urdu chat, portfolio and backtest before and after the font).

### Step 8.7 - Docs

Architecture §2, §3, §6.4, §7, §8, §12, §17, §19; PRD FR41 note, §8.1 and §14; Design §3 and §6.5; Rules §3.2; Workflow 8.3 and 8.6; Memory §2/§3/§4/§7/§9/§12; Phases.md Phase 8; README; this report.

### Deviations from the docs

- Provider: Groq (free) with Gemini as backup instead of the Claude API; Claude is a configuration switch.
- Plain REST without streaming (Architecture §2 named a WebSocket).
- `chat_messages` extends the Architecture §7 draft; `DELETE /chat/history` is an addition to the PRD scope.
- Chat is exempt from the 2-second API target; the target is a p95 under 15 seconds.
- Web only; the mobile chat screen is Phase 10.
- Bubbles mirror in Urdu; Nastaleeq replaces the Naskh body font chosen in Phase 1.
- Free-tier capacity: about 25 messages a day on Groq plus 20 Gemini requests; for real users a paid key or the Claude adapter.

---

## UI round: design system, landing page and polish (complete 2026-10-16)

Branch `feat/ui-design`. Step 1 (audit, three colour directions with previews, landing prototype)
is in `docs/design-directions/`; the team chose **Indus Night**, dark-first with a full light theme,
plain three.js, a theme toggle, the engine's real dated output for the risk demo and a sector-only
build flag. No calculation, existing API field or figure-related test expectation changed.

### Design system

- `packages/design-tokens`: colours for both themes (Design.md §2), spacing on the 8 px scale, the
  §3 type scale, elevation with a dark set (§21), motion capped at 400 ms (§11). The web app inlines
  them as `--iq-*` variables (`vite.config.ts`) and Tailwind's stock palette is switched off, so
  every colour on screen is a token. Contrast: every text pair at least 4.5:1 and UI lines at least
  3:1 in both themes (`colors.test.ts`, 9 tests, in CI).
- Gains and losses: a darker green against a brighter vermilion (simulated colour-blind ΔE at least
  28), always with ▲ / ▼ / — through one `Delta` component.
- Shared components: Button, Card (hover lift), Badge, Donut (SVG, also used by the landing page),
  CountUp (once, 400 ms, ends on the API's exact figure), PageHeader, CompanyName, ChartLegend,
  EmptyState and a shimmering Skeleton. A unit test fails on any margin, padding or gap off the 8 px
  scale.
- Theme toggle next to the language toggle on every screen; dark default; saved per device and
  applied before the first paint.

### Landing page (`/`)

Logged-out visitors see it; logged-in users go on to the dashboard (or onboarding). Sections: the
market bloom (one ray per company of the 10 Oct 2026 KSE-100 snapshot, grouped by sector, hover or
keyboard to label a node; a static image under reduced motion, without WebGL, on low-power devices
or with Save-Data); the scroll-pinned zoom into a real portfolio screenshot; the risk demo (the
allocation engine's own output for Rs 100,000 per profile, "Example, prices as of 9 Oct 2026, not
advice", generated by `python -m services.landing_examples`); what it really costs (the Phase 5
worked example, every charge line); how it works; the honesty strip with figures from our own data
(95 companies, forecasts for 18, prices since 8 Oct 2021). `VITE_LANDING_TICKERS=false` builds it with
sector names only.

### Screens

- Dashboard: risk profile, the recommended portfolio's totals with an allocation donut, the latest
  backtest headline with its hindsight warning, the forecasts and news the portfolio was built on
  (with confidence), quick links; designed empty states.
- Stocks: one searchable, sector-filterable, sortable table (compact rows on phones) with the last
  close and its date, and the next-day forecast with its confidence for the 18 covered stocks.
- Portfolio: summary beside an allocation donut, then one compact row per holding that expands to
  every charge, the forecast exit, dividends and "why this stock"; the page went from 5,254 px to
  about 1,890 px tall. Every figure is the engine's own string.
- Charts: theme colours, Rs. on the axes, an always-visible legend, the forecast point ringed and
  shaded with its confidence in the legend, draw-in once only.
- Onboarding: large choice cards. Backtest headline and benchmark with ▲ / ▼. Route chunks show a
  page skeleton while they load; errors appear after about 1 s (two 600 ms retries).

### Fixes from the audit

RTL: English names are isolated left to right and cut at their end, with the full name on hover
(Playwright check in Urdu at 1024 px). Chat: the Naskh font no longer covers U+2010-2011, so English
replies no longer show "low_confidence"; the Urdu counter reads "0 / 1000" (left-to-right
isolate). Low-contrast `gray-400` text and off-scale spacing are gone; one language toggle on the
chat screen.

### Chat wording (prompt-v3.3, ctx-v4)

One Urdu risk term from i18n (glossary `terms.riskProfile`), the portfolio named in full once and
then by a short name, no advice-like phrasing, Roman Urdu finance words from new i18n strings
(`terms.romanUrdu.*`, for team review). The live check (3 messages,
`docs/chat-eval/ui-round-2026-10-16.md`) showed the Urdu reply still repeating the name and keeping
"(low confidence)", so `tidy_wording` now removes both deterministically (words only). The English
message hit a free-tier 503, so the English rule is covered by the prompt test only.

### API (optional, read-only)

`GET /stocks/search` adds `last_close`, `last_close_date`, `forecast_covered`; `GET
/portfolio/current` adds `latest_backtest`. `plan_allocation` was extracted from
`generate_portfolio` so the landing examples use the identical engine path (tested against
`/portfolio/generate`).

### Performance (production build)

| Route                | JavaScript downloaded (gzip)                           |
| -------------------- | ------------------------------------------------------ |
| Before (every route) | 329.9 KB, one 1,099.9 KB chunk                         |
| `/`                  | 163.7 KB, then three.js 132.7 KB once the page is idle |
| `/login`             | 203.0 KB                                               |
| `/dashboard`         | 174.0 KB                                               |
| `/stocks/HBL`        | 284.9 KB (charts)                                      |
| `/portfolio`         | 211.4 KB                                               |
| `/backtest`          | 207.7 KB                                               |
| `/chat`              | 172.6 KB                                               |

LCP of `/` (Chrome's largest-contentful-paint, the headline, gzip server, median of 5): **0.34 s on
desktop**; **about 4.1 s on Lighthouse's mobile profile** (1.6 Mbps, 150 ms, 4x CPU), above the
2.5 s target there. The floor is JavaScript execution, mostly both locale files in the main bundle;
loading the inactive locale lazily is the next step (Memory.md §4). The Urdu font is no longer
downloaded on English pages.

### Tests

Backend 693 (new: search fields, latest backtest, landing examples, Roman Urdu glossary, risk
term, short name, tidy-up, prompt rules). Web unit 77 (new: theme rules, landing rules, donut, stock
list, spacing scale, font ranges, counter isolate), design tokens 9, api-client 6, i18n 3. Playwright
11 (6 new: landing and its calls to action, Urdu landing, reduced motion, logged-in redirect, RTL
names, chat counter). Existing tests changed: two Playwright lines take `.first()` of a ticker that
now appears in both the allocation legend and its holding row (visual); the chat prompt and context
version pins (`prompt-v3.2` to `v3.3`, `ctx-v3` to `v4`) in `test_chat_api.py` and
`test_chat_failover.py`.

### Evidence

Before/after screenshots of every screen in both themes and both languages (169 WebP) and a 28 s
landing recording: `docs/screenshots/ui-design/`.

### Gaps

Phone LCP above target on the harsh profile; English chat rule not seen live; Urdu, Roman Urdu and
landing copy await the team's review; the snapshot's tickers need the sector-only build for any
public deployment until PSX answers.

---

## Frontend Pages Summary

Code is organised by feature (Rules.md §4.2) under `apps/web/src/features/`.

| Route                        | Component                                              | Access                                                  |
| ---------------------------- | ------------------------------------------------------ | ------------------------------------------------------- |
| `/`                          | `landing/LandingPage`                                  | Logged out; logged-in users go to `/dashboard`          |
| `/login`, `/register`        | `auth/LoginPage`, `auth/RegisterPage`                  | Logged-out only                                         |
| `/onboarding`                | `onboarding/OnboardingPage`                            | Logged in; with a completed profile only as `?retake=1` |
| `/dashboard`                 | `dashboard/DashboardPage`                              | Logged in + completed risk profile                      |
| `/stocks`, `/stocks/:ticker` | `stocks/StocksPage`, `stocks/StockDetailPage`          | Logged in + completed risk profile (Phases 2-3)         |
| `/portfolio`                 | `portfolio/PortfolioPage`                              | Logged in + completed risk profile (Phase 5)            |
| `/backtest`, `/backtest/:id` | `backtest/BacktestPage`, `backtest/BacktestReportPage` | Logged in + completed risk profile (Phase 6)            |
| `/chat`                      | `chat/ChatPage`                                        | Logged in + completed risk profile (Phase 8)            |
| `/notifications`             | `common/ComingSoonPage`                                | Logged in + completed risk profile (Phase 7)            |
| `/admin`                     | `common/ComingSoonPage`                                | Admin role only (Phase 9)                               |

---

## Database Schema (current, Alembic head `fdddb7608c7c`)

```sql
users
  id UUID PK | email UNIQUE | password_hash | full_name | role ENUM('user','admin')
  | onboarding_progress JSONB NULL | created_at TIMESTAMPTZ

risk_profiles
  id UUID PK | user_id UUID UNIQUE FK(users) ON DELETE CASCADE
  | category ENUM('conservative','moderate','aggressive') | answers JSONB | updated_at TIMESTAMPTZ

refresh_tokens
  jti UUID PK | user_id FK(users) ON DELETE CASCADE | expires_at TIMESTAMPTZ | revoked_at TIMESTAMPTZ NULL

stocks
  id UUID PK | ticker UNIQUE | name | sector | shares_outstanding BIGINT NULL

price_points
  id BIGSERIAL PK | stock_id FK(stocks) | timestamp TIMESTAMPTZ
  | open | high | low | close | volume           -- raw provider values, never rewritten
  | split_factor NUMERIC DEFAULT 1 | quality_flag NULL | adjustment_version NULL
  UNIQUE (stock_id, timestamp)

stock_splits
  id BIGSERIAL PK | stock_id FK(stocks) | split_date DATE | ratio NUMERIC
  | history_adjusted BOOLEAN NULL | decision_note | method_version
  UNIQUE (stock_id, split_date)

stock_dividends
  id BIGSERIAL PK | stock_id FK(stocks) | ex_date DATE | amount NUMERIC | source
  | previous_close NULL | ex_close NULL | adjustment_factor NULL (= not applied)
  | review_flag NULL | method_version
  UNIQUE (stock_id, ex_date)

sentiment_scores   -- replaces news_sentiments (2026-10-11); headline only, never article text
  id UUID PK | stock_id FK(stocks) | source | url | headline | published_at TIMESTAMPTZ | fetched_at TIMESTAMPTZ
  | score NUMERIC(5,4) NULL (= not yet scored) | label NULL | scorer NULL ('finbert'/'vader') | scorer_version NULL
  | finbert_confidence NUMERIC(5,4) NULL | UNIQUE (stock_id, url)

news_source_status
  source PK | last_attempt_at | last_success_at | last_error | last_new_headlines

predictions
  id UUID PK | stock_id FK(stocks) | model_version | forecast_price NUMERIC(14,4) | last_close NUMERIC(14,4)
  | confidence_score NUMERIC(5,4)  -- calibrated chance the LSTM direction is right
  | signal | signal_probability NUMERIC(5,4) NULL | as_of_date DATE NULL
  | sentiment_status VARCHAR NULL ('used'/'unavailable') | generated_at TIMESTAMPTZ

portfolios         -- Phase 5; one active per user (partial unique index)
  id UUID PK | user_id FK(users) ON DELETE CASCADE | status ('active'/'archived') | generated_at TIMESTAMPTZ
  | risk_category | capital NUMERIC(16,2) | filer_status ('filer'/'non_filer') | shariah_only | excluded_tickers JSONB
  | commission_rate NUMERIC(6,5) | rates_version | model_version | prices_as_of DATE | shariah_list_version NULL
  | input_snapshot JSONB | gross_total | charges_total | cost_total | idle_cash  -- NUMERIC(16,2)

portfolio_holdings
  id UUID PK | portfolio_id FK(portfolios) ON DELETE CASCADE | stock_id FK(stocks) | prediction_id FK(predictions) NULL
  | position | shares INT | reference_price NUMERIC(14,2) | target_weight | allocation_pct  -- NUMERIC(7,4), percent
  | gross_value | commission | sales_tax | cdc_fee | psx_trading_fee | psx_regulatory_fee | secp_levy
  | nccpl_trade_fee | nccpl_secp_fee | buy_charges | total_cost  -- NUMERIC(16,2) | projection JSONB

backtest_results   -- Phase 6; kind 'portfolio' (portfolio_id set) or 'custom' (NULL)
  id UUID PK | user_id FK(users) ON DELETE CASCADE | portfolio_id FK(portfolios) NULL ON DELETE CASCADE | kind
  | created_at TIMESTAMPTZ | years | period_start | period_end DATE | trading_days | carried_forward_days
  | capital NUMERIC(16,2) | filer_status | commission_rate NUMERIC(6,5) | rates_version | risk_free_version
  | price_adjustment | dividends_source | prices_as_of DATE | method_version | inputs JSONB
  | buy_charges | dividends_gross | wht | sell_charges | cgt | idle_cash | end_value_before_sale | end_value_net  -- NUMERIC(16,2)
  | total_return | total_return_before_sale | annualised_return | sharpe_ratio NULL | max_drawdown | win_rate NULL  -- NUMERIC(12,6), fractions
  | drawdown_peak_date | drawdown_trough_date | months_won | months_total
  | holdings | start_date_rules | benchmark | kse100 | risk_free | series  -- JSONB

index_points       -- licensed daily index closes (KSE-100 once PSX grants permission)
  id BIGSERIAL PK | index_code | dataset_version | trade_date DATE | close NUMERIC(14,4) | source | loaded_at TIMESTAMPTZ
  UNIQUE (index_code, dataset_version, trade_date)

chat_messages      -- Phase 8; one row per message
  id UUID PK | user_id FK(users) ON DELETE CASCADE | role 'user'|'assistant' | content TEXT
  | language 'en'|'ur'|'ur-latn' | created_at TIMESTAMPTZ
  | context_version | context_hash CHAR(64) | context_refs JSONB | prompt_version | provider | model  -- assistant rows
  | input_tokens | output_tokens | latency_ms | figure_check 'passed'|'regenerated'|'fallback'
  | figure_check_detail JSONB | sources JSONB
  INDEX (user_id, created_at)
```

---

## Automated Tests

| Suite                  | File                                 | Tests                                                                                            |
| ---------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------ |
| Backend (pytest)       | `tests/test_auth.py`                 | 25                                                                                               |
|                        | `tests/test_config.py`               | 14                                                                                               |
|                        | `tests/test_admin_guard.py`          | 4                                                                                                |
|                        | `tests/test_risk_profile.py`         | 35                                                                                               |
|                        | `tests/test_i18n_labels.py`          | 3                                                                                                |
|                        | `tests/test_datetimes.py`            | 4                                                                                                |
|                        | `tests/test_health.py`               | 1                                                                                                |
|                        | `tests/test_stocks.py`               | 25                                                                                               |
|                        | `tests/test_split_adjustment.py`     | 9                                                                                                |
|                        | `tests/test_data_quality.py`         | 3                                                                                                |
|                        | `tests/test_dividend_adjustment.py`  | 10                                                                                               |
|                        | `tests/test_ml_dataset.py`           | 3                                                                                                |
|                        | `tests/test_indicators.py`           | 14                                                                                               |
|                        | `tests/test_splits.py`               | 5                                                                                                |
|                        | `tests/test_ml_metrics.py`           | 8                                                                                                |
|                        | `tests/test_ml_pipeline.py`          | 17                                                                                               |
|                        | `tests/test_predictions.py`          | 18                                                                                               |
|                        | `tests/test_ml_promotion.py`         | 8                                                                                                |
|                        | `tests/test_news_http.py`            | 7                                                                                                |
|                        | `tests/test_news_matching.py`        | 5                                                                                                |
|                        | `tests/test_news_sources.py`         | 6                                                                                                |
|                        | `tests/test_news_ingestion.py`       | 6                                                                                                |
|                        | `tests/test_sentiment_scoring.py`    | 5                                                                                                |
|                        | `tests/test_sentiment_api.py`        | 10                                                                                               |
|                        | `tests/test_sentiment_fallback.py`   | 3                                                                                                |
|                        | `tests/test_sentiment_eval.py`       | 4                                                                                                |
|                        | `tests/test_sentiment_experiment.py` | 6                                                                                                |
|                        | `tests/test_migration_sentiment.py`  | 2                                                                                                |
|                        | `tests/test_cost_engine.py`          | 22                                                                                               |
|                        | `tests/test_allocation.py`           | 11                                                                                               |
|                        | `tests/test_rolling.py`              | 7                                                                                                |
|                        | `tests/test_portfolio_universe.py`   | 4                                                                                                |
|                        | `tests/test_portfolio_api.py`        | 15                                                                                               |
|                        | `tests/test_benchmark_data.py`       | 12                                                                                               |
|                        | `tests/test_backtest_engine.py`      | 16                                                                                               |
|                        | `tests/test_backtest_api.py`         | 16                                                                                               |
|                        | `tests/test_chat_context.py`         | 19                                                                                               |
|                        | `tests/test_chat_figure_check.py`    | 52                                                                                               |
|                        | `tests/test_chat_language.py`        | 16                                                                                               |
|                        | `tests/test_chat_api.py`             | 28                                                                                               |
|                        | `tests/test_chat_failover.py`        | 49                                                                                               |
|                        | `tests/test_llm_providers.py`        | 51                                                                                               |
|                        | `tests/test_chat_eval.py`            | 25                                                                                               |
| Web (Node test runner) | `apps/web/src/**/*.test.ts`          | 48 (draft-save ordering, route guards, formatting, forecast, portfolio, backtest and chat views) |
| API client             | `packages/api-client/src/*.test.ts`  | 6 (token refresh coordination)                                                                   |
| i18n                   | `packages/i18n/scripts/*.test.mjs`   | 3 (parity checker)                                                                               |

Backend total: **793** (2026-10-25, Phase 7; 693 after the UI round). All run in CI on every push; none calls a real LLM or Firebase. Playwright E2E (13 tests, including the Phase 8 chat flow against a MOCK model and the Phase 7 notifications flow on the MOCK market) runs locally.

```bash
cd services/api && python -m pytest          # backend
npm test -w @investiq/web                    # web unit tests
npm run check -w @investiq/i18n              # en/ur parity
```

---

## How to Run the Complete Project

The root [`README.md`](../README.md) "Local Setup" section is the maintained, step-by-step guide (Docker → backend `.env` → migrations → API → Celery → ML training → web → mobile → quality checks). It is not duplicated here so the two cannot drift apart.

---

## What Still Needs to Be Built / Re-audited

| Phase    | Item                                                                     | Status                                                                                                  |
| -------- | ------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| Phase 2  | Stock data & market analysis                                             | ✅ Re-audited 2026-10-10 (mobile screens deferred to Phase 10)                                          |
| Phase 3  | Prediction engine                                                        | ✅ Re-audited 2026-10-10 (models do not beat their baselines; documented)                               |
| Phase 4  | FinBERT sentiment endpoint + "what's driving this" panel                 | Complete 2026-10-11 (news model not promoted; FinBERT 67.7% on PSX headlines)                           |
| Phase 5  | Portfolio generation + cost engine                                       | Complete 2026-10-11 (CDC, NCCPL and non-filer CGT rates unverified; KSE-100 benchmark unavailable)      |
| Phase 6  | Backtesting vs KSE-100                                                   | Complete 2026-10-13 except the KSE-100 series (PSX permission pending; stand-in benchmark shown)        |
| Phase 7  | Autonomous agent & notifications                                         | Built 2026-10-25 (in-app list working; real web push waits for the Firebase values; mobile in Phase 10) |
| Phase 8  | LLM chatbot (bilingual)                                                  | Complete 2026-10-14 (Groq free tier, about 25 messages a day; web only, mobile in Phase 10)             |
| Phase 9  | Admin panel                                                              | Not started                                                                                             |
| Phase 10 | Mobile app parity                                                        | Not started                                                                                             |
| Phase 11 | Testing, polish, defense prep (incl. hardening backlog in Memory.md §11) | Not started                                                                                             |

---

## GitHub Repository

**URL:** https://github.com/abdulmannanbhatti936-lgtm/Invest_IQ
**Working branch:** `fix/phase-0-3-completion` (Phase 0 and 1 re-verification)
**CI:** GitHub Actions on every push — backend (ruff, black, migrations, pytest) and frontend (ESLint, i18n parity, type-checks for web/mobile/packages, web unit tests).

---

_Last updated: 2026-10-25_
