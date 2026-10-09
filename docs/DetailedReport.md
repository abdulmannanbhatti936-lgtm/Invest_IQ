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
│  news_sentiments     │◄────────────│  Celery Worker         │
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

## Phase 2: Stock Data & Market Analysis (⚠️ Needs re-audit)

> **Needs re-audit:** marked complete earlier without checkpoint evidence; an offline test on 2026-10-09 showed the history/quote endpoints do not degrade gracefully (Memory.md §4), and the mobile screens (Step 2.9) were never built. The text below is the original record, kept as history.

### Step 2.1 — Database Models

**Files:** `services/api/models/stock.py`

**Stock model:**

- `id` — UUID
- `ticker` — unique string (e.g. "AAPL", "OGDC.KA")
- `name` — company name
- `exchange` — string

**PricePoint model:**

- `id` — UUID
- `stock_id` — FK → stocks.id
- `timestamp` — datetime (indexed)
- `open`, `high`, `low`, `close`, `volume` — Float/BigInt OHLCV data

---

### Step 2.2 — External Data Client

**File:** `services/api/integrations/market_data.py`

**Class:** `MarketDataClient`

**Methods:**

- `get_quote(ticker)` → current price, company name, volume, market cap
- `get_history(ticker, period)` → OHLCV DataFrame for the given period (1mo, 3mo, 1y, etc.)

**Library:** `yfinance` — scrapes Yahoo Finance under the hood

**Design principle:** Single class wrapping all external data. If Yahoo Finance breaks or we switch to an official PSX API, only this file changes.

---

### Step 2.3 — Redis Caching Layer

**File:** `services/api/services/stock_service.py`

**Cache flow:**

```
Request comes in for ticker "AAPL"
    ↓
Check Redis key "quote:AAPL"
    ↓
Cache HIT? → Return instantly (< 5ms)
Cache MISS? → Call yfinance → Store in Redis with 15-min TTL → Return
```

**Serialization:** Python `datetime` objects serialized to ISO strings for JSON storage in Redis, deserialized on retrieval.

**Fallback:** If Redis is unavailable → falls through to direct yfinance call (app doesn't crash)

---

### Step 2.4 — Stock Endpoints

**File:** `services/api/routers/stocks.py`

| Method | Path                          | Description                                   |
| ------ | ----------------------------- | --------------------------------------------- |
| GET    | `/stocks/search?q={query}`    | Search stocks by ticker or name               |
| GET    | `/stocks/{ticker}`            | Get latest quote for a specific stock         |
| GET    | `/stocks/{ticker}/history`    | Get OHLCV history (passed to charts)          |
| GET    | `/stocks/{ticker}/prediction` | Get ML prediction: BUY/SELL/HOLD + confidence |

All routes protected by `Depends(get_current_user)`.

**Tests:** `tests/test_stocks.py` — 3 passing tests

---

### Step 2.5 — Automated Market Data Fetch (Celery)

**File:** `services/api/worker/tasks.py`

**Task:** `fetch_market_data_for_tickers`

- Accepts a list of ticker symbols
- Calls `MarketDataClient.get_history()` for each
- Bulk-inserts OHLCV rows into `price_points` table
- Auto-creates `Stock` parent record if it doesn't exist

**Scheduled:** `celery_app.conf.beat_schedule` → runs at 18:00 daily (end-of-trading-day)

---

### Step 2.6 — Sentiment Database Model

**File:** `services/api/models/sentiment.py`

**NewsSentiment model:**

- `id` — UUID
- `stock_id` — FK → stocks.id (cascade delete)
- `headline` — text of the news article title
- `sentiment_score` — Float (-1.0 = very bearish, 0.0 = neutral, +1.0 = very bullish)
- `timestamp` — when scraped

---

### Step 2.7 — News Scraper

**File:** `services/api/integrations/news_scraper.py`

**How it works:**

1. Builds Yahoo Finance RSS URL: `https://finance.yahoo.com/rss/headline?s={ticker}`
2. Parses XML with `BeautifulSoup` using `lxml-xml` parser
3. Extracts `<title>` tags (news headlines)
4. Checks DB for existing headlines (deduplication)
5. Bulk-inserts new headlines with `sentiment_score=0.0` (pending AI analysis)

**Library:** `requests` + `beautifulsoup4` + `lxml`

**Scheduled:** Every hour via Celery Beat

---

### Step 2.8 — Celery Beat Schedule

**File:** `services/api/core/celery_app.py`

```python
beat_schedule = {
    'fetch-eod-market-data': {
        'task': 'worker.tasks.fetch_market_data_for_tickers',
        'schedule': crontab(hour=18, minute=0),  # 6 PM daily
    },
    'fetch-hourly-news': {
        'task': 'worker.tasks.scrape_news_for_stocks',
        'schedule': crontab(minute=0),  # Every hour
    },
    'analyze-hourly-news': {
        'task': 'worker.tasks.analyze_news_sentiment',
        'schedule': crontab(minute=5),  # 5 min after news scrape
    },
}
```

---

## Phase 3: Machine Learning (⚠️ Needs re-audit)

> **Needs re-audit:** the original models were trained on **AAPL (non-PSX)**, and Step 3.1 (3+ years of KSE-100 data) was never done. A 12-ticker PSX retrain exists (`services/api/ml/reports/`), but it has not been audited step by step and does not beat its naive baselines (Memory.md §10). The text below is the original record, kept as history; several files it names (`ml/predictor.py`, `ml/lstm_predictor.py`, `pandas-ta`) have since been replaced.

### Step 3.1 — FinBERT Sentiment Analysis

**File:** `services/api/ml/sentiment.py`

**Model:** `ProsusAI/finbert` from HuggingFace — a BERT model fine-tuned specifically on financial news (10,000+ financial articles)

**How it works:**

```python
pipeline("sentiment-analysis", model="ProsusAI/finbert")
→ Output: {"label": "positive", "score": 0.92}
→ Normalized: +0.92 (bullish)
```

**Score normalization:**

- `positive` → `+score` (bullish)
- `negative` → `-score` (bearish)
- `neutral` → `0.0`

**Architecture:** Singleton instance loaded once at server start to avoid loading 400MB+ weights on every request.

---

### Step 3.2 — Sentiment Background Job

**File:** `services/api/worker/tasks.py`

**Task:** `analyze_news_sentiment`

1. Queries DB for `news_sentiments` rows where `sentiment_score == 0.0`
2. Runs each headline through `FinBERTSentimentModel.analyze_headline()`
3. Updates the row with the real score
4. Commits to DB

**Scheduled:** 5 minutes past every hour (after news scraper runs at minute 0)

---

### Step 3.3 — Price Prediction (Random Forest Baseline)

**Files:** `services/api/ml/features.py`, `ml/predictor.py`

**Feature Engineering** (`features.py`):

- Pulls historical `PricePoint` records from DB
- Computes technical indicators using `pandas-ta`:
  - **RSI(14)** — momentum oscillator (overbought/oversold)
  - **MACD** — trend-following momentum indicator
  - **SMA(20)** & **SMA(50)** — short and medium moving averages
  - **Bollinger Bands** — volatility measure
- Joins the latest `sentiment_score` from `news_sentiments`
- Returns a clean Pandas DataFrame ready for ML

**Prediction** (`predictor.py`):

- `RandomForestClassifier` from scikit-learn
- Target variable: next day's price direction (UP=BUY, DOWN=SELL, FLAT=HOLD)
- Outputs: `signal` (BUY/SELL/HOLD) + `confidence` (0.0–1.0) + `accuracy` (test set accuracy)

**Why Random Forest first:** Fast to train on-the-fly, interpretable, works well with tabular data. Used as a prototype baseline before LSTM.

---

### Step 3.4 — LSTM Price Prediction (Advanced)

**File:** `services/api/ml/lstm_predictor.py`

**Architecture:** PyTorch LSTM neural network

- Input: sequence of last 60 days of OHLCV + technical indicators
- Hidden layers: 2 LSTM layers, 128 hidden units each
- Output: next day's closing price prediction
- Loss function: MSE (Mean Squared Error)
- Optimizer: Adam

**Advantage over Random Forest:** Captures long-range temporal dependencies in time-series data that tree-based models miss (e.g. a pattern that takes 30 days to unfold).

---

### Step 3.5 — Prediction UI (Frontend)

**File:** `apps/web/src/pages/StockDetail.tsx`

**What it shows:**

- Real-time stock quote (price, change %, volume)
- Historical price chart using `recharts` (LineChart)
- ML Prediction panel:
  - Signal badge: **BUY** (green) / **SELL** (red) / **HOLD** (yellow)
  - Confidence percentage
  - Model accuracy percentage
- Sentiment score bar (-1.0 to +1.0 visual gauge)

---

## Frontend Pages Summary

Code is organised by feature (Rules.md §4.2) under `apps/web/src/features/`.

| Route                                                | Component                                     | Access                                                         |
| ---------------------------------------------------- | --------------------------------------------- | -------------------------------------------------------------- |
| `/`                                                  | redirect                                      | → `/dashboard`                                                 |
| `/login`, `/register`                                | `auth/LoginPage`, `auth/RegisterPage`         | Logged-out only                                                |
| `/onboarding`                                        | `onboarding/OnboardingPage`                   | Logged in; with a completed profile only as `?retake=1`        |
| `/dashboard`                                         | `dashboard/DashboardPage`                     | Logged in + completed risk profile                             |
| `/stocks`, `/stocks/:ticker`                         | `stocks/StocksPage`, `stocks/StockDetailPage` | Logged in + completed risk profile (Phase 2/3, needs re-audit) |
| `/portfolio`, `/backtest`, `/chat`, `/notifications` | `common/ComingSoonPage`                       | Logged in + completed risk profile (Phases 5–8)                |
| `/admin`                                             | `common/ComingSoonPage`                       | Admin role only (Phase 9)                                      |

---

## Database Schema (current, Alembic head `f7a2c4e81b90`)

```sql
users
  id UUID PK | email UNIQUE | password_hash | full_name | role ENUM('user','admin')
  | onboarding_progress JSONB NULL | created_at TIMESTAMP (UTC)

risk_profiles
  id UUID PK | user_id UUID UNIQUE FK(users) | category ENUM('conservative','moderate','aggressive')
  | answers JSONB | updated_at TIMESTAMP (UTC)

stocks
  id UUID PK | ticker UNIQUE | name | sector

price_points
  id BIGSERIAL PK | stock_id FK(stocks) | timestamp TIMESTAMPTZ | open | high | low | close | volume
  UNIQUE (stock_id, timestamp)

news_sentiments
  id SERIAL PK | stock_id FK(stocks) | headline | sentiment_score FLOAT NULL (= not yet scored) | timestamp (UTC)

predictions
  id UUID PK | stock_id FK(stocks) | model_version | forecast_price NUMERIC(14,4) | last_close NUMERIC(14,4)
  | signal | confidence_score NUMERIC(5,4) | generated_at TIMESTAMP (UTC)
```

The four naive `TIMESTAMP` columns hold UTC; migrating them to `TIMESTAMPTZ` is proposed and awaiting approval (Memory.md §4).

---

## Automated Tests

| Suite                  | File                               | Tests                                                        |
| ---------------------- | ---------------------------------- | ------------------------------------------------------------ |
| Backend (pytest)       | `tests/test_auth.py`               | 15                                                           |
|                        | `tests/test_admin_guard.py`        | 4                                                            |
|                        | `tests/test_risk_profile.py`       | 33                                                           |
|                        | `tests/test_datetimes.py`          | 4                                                            |
|                        | `tests/test_health.py`             | 1                                                            |
|                        | `tests/test_stocks.py`             | 14 (Phase 2, needs re-audit)                                 |
|                        | `tests/test_predictions.py`        | 7 (Phase 3, needs re-audit)                                  |
|                        | `tests/test_ml_pipeline.py`        | 13 (Phase 3, needs re-audit)                                 |
| Web (Node test runner) | `apps/web/src/**/*.test.ts`        | 13 (draft-save ordering, route-guard rules, date formatting) |
| i18n                   | `packages/i18n/scripts/*.test.mjs` | 3 (parity checker)                                           |

Backend total: **91**. All run in CI on every push.

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

| Phase    | Item                                                                     | Status                                                                            |
| -------- | ------------------------------------------------------------------------ | --------------------------------------------------------------------------------- |
| Phase 2  | Stock data & market analysis                                             | ⚠️ Needs re-audit (graceful degradation gaps; mobile screens not built)           |
| Phase 3  | Prediction engine                                                        | ⚠️ Needs re-audit (KSE-100 data never acquired; PSX models below naive baselines) |
| Phase 4  | FinBERT sentiment endpoint + "what's driving this" panel                 | Not started                                                                       |
| Phase 5  | Portfolio generation + cost engine (server must require a risk profile)  | Not started                                                                       |
| Phase 6  | Backtesting vs KSE-100                                                   | Not started                                                                       |
| Phase 7  | Autonomous agent & notifications                                         | Not started                                                                       |
| Phase 8  | LLM chatbot (bilingual)                                                  | Not started                                                                       |
| Phase 9  | Admin panel                                                              | Not started                                                                       |
| Phase 10 | Mobile app parity                                                        | Not started                                                                       |
| Phase 11 | Testing, polish, defense prep (incl. hardening backlog in Memory.md §11) | Not started                                                                       |

---

## GitHub Repository

**URL:** https://github.com/abdulmannanbhatti936-lgtm/Invest_IQ
**Working branch:** `fix/phase-0-3-completion` (Phase 0 and 1 re-verification)
**CI:** GitHub Actions on every push — backend (ruff, black, migrations, pytest) and frontend (ESLint, i18n parity, type-checks for web/mobile/packages, web unit tests).

---

_Last updated: 2026-10-09_
