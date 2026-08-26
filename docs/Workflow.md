# Workflow.md — InvestIQ

### Execution Playbook for Antigravity AI

**Purpose:** PRD.md / Architecture.md / Rules.md / Phases.md / Design.md / Memory.md tell Antigravity AI _what_ to build and _why_. This document tells it _exactly how to proceed, in what order, with what to check at each step_ — a literal, step-by-step run sheet it can follow with minimal ambiguity, checkpoint by checkpoint.

**How to use this with Antigravity:**

1. Give it all 7 docs (the 6 planning docs + this Workflow.md) at the start of the project, in this order: Memory.md → PRD.md → Architecture.md → Rules.md → Phases.md → Design.md → Workflow.md.
2. Tell it: "Start at Workflow Step 0.1 and proceed sequentially. Do not skip a checkpoint. Update Memory.md at every checkpoint marked ✅."
3. At the start of every new session, tell it: "Read Memory.md Section 2 first, then resume from the last incomplete step in Workflow.md."

**Golden rule for the agent:** every step below ends in a **Checkpoint** — a concrete, verifiable thing that must be true before moving to the next step. If a checkpoint fails, stop and fix it before proceeding. Never mark a checkpoint done because the code "should" work — verify it actually runs.

---

## PHASE 0 — Foundation & Project Setup

### Step 0.1 — Repository & Monorepo Skeleton

**Do:**

- Initialize git repo, create `.gitignore` (node_modules, `__pycache__`, `.env`, `venv`, build outputs, `*.h5`/`*.pt`/`*.pkl` model files)
- Create folder structure exactly per Architecture.md §5: `apps/web`, `apps/mobile`, `services/api`, `services/ml-engine`, `services/sentiment-engine`, `services/chatbot-service`, `packages/shared-types`, `packages/api-client`, `packages/i18n`, `packages/design-tokens`, `infra/`, `docs/`
- Move all 7 markdown docs into `docs/`
- Write root `README.md`: project name, one-line pitch (Memory.md §1), local setup instructions (filled in as later steps complete)

**Checkpoint ✅:** `git log` shows an initial commit; folder structure matches Architecture.md §5 exactly; `docs/` contains all 7 files.

### Step 0.2 — Local Infrastructure (Docker)

**Do:**

- Write `infra/docker-compose.yml`: Postgres service, Redis service, with named volumes and exposed ports
- Write `.env.example` at repo root and in `services/api/` per Architecture.md §17

**Checkpoint ✅:** `docker-compose up` (from `infra/`) starts Postgres and Redis without errors; `docker ps` shows both containers healthy.

### Step 0.3 — Backend Skeleton

**Do:**

- Scaffold FastAPI app in `services/api`: `main.py`, `routers/`, `services/`, `crud/`, `models/`, `schemas/` (Pydantic), `core/config.py` (env var loading), `core/database.py` (SQLAlchemy engine/session)
- Add a `/health` endpoint returning `{"status": "ok"}`
- Add `requirements.txt`/`pyproject.toml` with: fastapi, uvicorn, sqlalchemy, pydantic, python-jose (JWT), passlib[bcrypt], alembic (migrations), redis, celery, pytest, black, ruff
- Set up Alembic for migrations

**Checkpoint ✅:** `uvicorn main:app --reload` runs locally; `GET /health` returns 200; `alembic init` completed and configured to point at the Postgres from Step 0.2.

### Step 0.4 — Web App Skeleton

**Do:**

- Scaffold `apps/web` with Vite + React + TypeScript
- Install and configure Tailwind CSS
- Set up React Router with placeholder routes matching Design.md §14.1 nav: `/`, `/login`, `/register`, `/onboarding`, `/dashboard`, `/stocks`, `/portfolio`, `/backtest`, `/chat`, `/notifications`, `/admin`
- Install React Query, set up a query client provider
- Create placeholder pages that just render the route name

**Checkpoint ✅:** `npm run dev` serves the web app; navigating to each route above renders without a console error.

### Step 0.5 — Mobile App Skeleton

**Do:**

- Scaffold `apps/mobile` with Expo + React Native + TypeScript
- Set up React Navigation with a bottom tab bar matching Design.md §14.2: Home, Stocks, Portfolio, Chat, Notifications
- Install React Query

**Checkpoint ✅:** `npx expo start` runs; app opens in Expo Go or an emulator; all 5 tabs are navigable and render placeholder content.

### Step 0.6 — Shared Packages

**Do:**

- `packages/shared-types`: empty TypeScript project, exports a placeholder type
- `packages/api-client`: a thin wrapper (e.g., using `axios` or `fetch`) with a placeholder `healthCheck()` function calling the backend `/health`
- `packages/i18n`: set up `i18next` (or equivalent) with `en.json` and `ur.json`, each containing one test key
- `packages/design-tokens`: create the file structure from Design.md §20 (`colors.ts`, `typography.ts`, `spacing.ts`, `shadows.ts`, `motion.ts`, `index.ts`) with placeholder token values per Design.md §2

**Checkpoint ✅:** Both `apps/web` and `apps/mobile` can import from all four `packages/*` without module-resolution errors; calling the placeholder `healthCheck()` from the web app successfully hits the backend `/health` endpoint.

### Step 0.7 — Linting, Formatting, CI

**Do:**

- Configure ESLint + Prettier for `apps/web`, `apps/mobile`, and `packages/*` (shared config)
- Configure `black` + `ruff` for `services/api` and other Python services
- Write `.github/workflows/ci.yml`: on push/PR — install deps, run lint, run backend Pytest (even if empty), run frontend type-check

**Checkpoint ✅:** CI passes on a fresh push of the skeleton; a deliberately broken lint rule locally causes `npm run lint` / `ruff check` to fail (confirms the tooling is actually active, not a no-op).

### Step 0.8 — Documentation Sync

**Do:**

- Update root `README.md` with actual working setup instructions (docker-compose up → backend → web → mobile)
- Update Memory.md §2 (Current Status): Phase 0 complete, list what was set up
- Add a Memory.md §7 session log entry using the template in Memory.md §17

**Checkpoint ✅ (Phase 0 exit criteria, per Phases.md):** A teammate with zero prior context can clone the repo and get everything running using only the README.

---

## PHASE 1 — Auth, Onboarding & Risk Profiling

### Step 1.1 — Database Models

**Do:** Create SQLAlchemy models for `users` and `risk_profiles` per Architecture.md §7. Generate and run Alembic migration.
**Checkpoint ✅:** Migration applies cleanly to the Postgres container; tables visible via `psql`/a DB client with correct columns/types.

### Step 1.2 — Auth Backend

**Do:** Implement `/auth/register`, `/auth/login`, `/auth/refresh` per Architecture.md §8. Password hashing via bcrypt/argon2 (Rules.md §6). JWT access + refresh token issuance.
**Checkpoint ✅:** Via API client (curl/Postman/pytest) — register a user, log in, receive valid tokens, call a protected endpoint with the token successfully, confirm it's rejected without a token.

### Step 1.3 — Risk Profile Backend

**Do:** Implement `/users/me`, `/users/me/risk-profile` (GET + PATCH). Define the questionnaire → category classification logic (Conservative/Moderate/Aggressive) as a pure, unit-testable function per Rules.md §3.2.
**Checkpoint ✅:** Unit tests cover at least one input set per risk category, confirming correct classification; endpoint persists and returns the profile correctly.

### Step 1.4 — Auth Unit/Integration Tests

**Do:** Pytest coverage for register/login/refresh, including failure cases (duplicate email, wrong password, expired/invalid token).
**Checkpoint ✅:** `pytest` passes; test suite included in CI (Step 0.7) and passing there too.

### Step 1.5 — Web: Auth Screens

**Do:** Build login/register screens using Design.md §13 form patterns (label-above-input, inline validation errors). Wire to `packages/api-client`.
**Checkpoint ✅:** Can register and log in through the actual UI (not just API calls); invalid input shows inline errors per Design.md §12.3.

### Step 1.6 — Web: Onboarding Questionnaire

**Do:** Build the single-question-per-screen wizard per Design.md §7.1 (choice cards, progress indicator, back button). Implement partial-progress resume (FR6).
**Checkpoint ✅:** Completing the questionnaire produces a correct risk profile end-to-end through the UI; closing mid-way and returning resumes correctly.

### Step 1.7 — Route Guard

**Do:** Implement a route guard so no dashboard/portfolio/etc. screen is reachable without a completed risk profile.
**Checkpoint ✅:** A logged-in user with no risk profile is redirected to onboarding when attempting to visit `/dashboard` directly via URL.

### Step 1.8 — i18n Pass

**Do:** All auth + onboarding copy routed through `packages/i18n`, both `en.json` and `ur.json` populated (rough Urdu acceptable at this stage per Rules.md — polish later in Phase 11).
**Checkpoint ✅:** Toggling language on the auth/onboarding screens shows Urdu text with correct RTL layout (Design.md §23) and no obviously broken/overflowing labels.

### Step 1.9 — Documentation Sync

**Do:** Update Memory.md §2 and §3 (if any decisions were made, e.g., final questionnaire question set), add session log entry.
**Checkpoint ✅ (Phase 1 exit criteria, per Phases.md):** All Phase 1 exit criteria in Phases.md are individually verified true.

_(Repeat this same discipline — DB models → backend logic → tests → frontend → i18n → docs sync — for every subsequent phase. From here, steps are listed at a slightly higher level since the pattern is now established; expand each into the same granularity as Phase 1 when actually executing.)_

---

## PHASE 2 — Stock Data & Market Analysis

### Step 2.1 — Database Models

**Do:** Create SQLAlchemy models for `stocks` and `price_points` per Architecture.md §7. Generate and run Alembic migration.
**Checkpoint ✅:** Migration applies cleanly; both tables visible with correct columns/types/foreign keys.

### Step 2.2 — External Data Client Module

**Do:** Build an isolated client module (`services/api/integrations/market_data.py` or similar) wrapping Yahoo Finance API and the chosen PSX data source. Isolate it behind a clean interface (e.g., `get_history(ticker, start, end)`, `get_quote(ticker)`) so the underlying provider can be swapped or mocked without touching calling code.
**Checkpoint ✅:** Calling the module directly (e.g., in a Python shell or a throwaway script) returns real data for a known ticker (e.g., a major KSE-100 company).

### Step 2.3 — Redis Caching Layer

**Do:** Wrap the Step 2.2 client with a caching decorator/layer (5–15 min TTL per Architecture.md §10). Cache key includes ticker + query params.
**Checkpoint ✅:** Calling the same query twice in quick succession shows the second call is served from Redis (verify via logging or Redis `MONITOR`), not a new external API hit.

### Step 2.4 — Endpoints

**Do:** Implement `/stocks/search`, `/stocks/{ticker}`, `/stocks/{ticker}/history` in `routers/stocks.py`, calling into the cached client via a `services/stock_service.py` layer (per Rules.md §3.2 — thin route handlers).
**Checkpoint ✅:** All three endpoints return correct, real data via curl/Postman/pytest; response shapes match the Pydantic schemas.

### Step 2.5 — Celery + Background Job Wiring (first job in the project)

**Do:** Set up Celery app config (`services/api/core/celery_app.py`), connect to Redis as broker. Implement `refresh_stock_prices` task. Set up Celery Beat schedule (e.g., every 15 min during market hours).
**Checkpoint ✅:** `celery -A core.celery_app worker` and `celery -A core.celery_app beat` both start without error; manually triggering the task once populates/updates `price_points` for a test ticker.

### Step 2.6 — Graceful Degradation Test

**Do:** Add explicit handling: if the external API call fails/times out, catch it, log it, and return a clear "data temporarily unavailable" response rather than a 500 (Architecture.md §8.3).
**Checkpoint ✅:** Manually simulate a failure (e.g., temporarily point the client at a bad URL) and confirm the endpoint fails gracefully, not with an unhandled exception.

### Step 2.7 — Backend Tests

**Do:** Pytest with the external client mocked — test search/detail/history endpoints, cache-hit behavior, and the graceful-degradation path from Step 2.6.
**Checkpoint ✅:** All tests pass; included and passing in CI.

### Step 2.8 — Web Frontend

**Do:** Build stock search/browse screen and stock detail screen (chart via Recharts or similar, key stats panel, plain-language trend summary line per Design.md §7.2). Wire through `packages/api-client`.
**Checkpoint ✅:** Can search a real ticker in the UI and see a correctly rendered chart and stats matching what Step 2.4's endpoint returns.

### Step 2.9 — Mobile Frontend

**Do:** Equivalent screens in `apps/mobile` using the same shared packages.
**Checkpoint ✅:** Same search/detail flow works on Android emulator, hitting the same backend.

### Step 2.10 — i18n Pass

**Do:** Route all new copy through `packages/i18n`.
**Checkpoint ✅:** Urdu toggle shows correctly on both new screens, no overflow (Design.md §24).

### Step 2.11 — Documentation Sync

**Do:** Update Memory.md §2, §9 (Yahoo Finance / PSX Data API rows → "Integrated ✅" with date), append §7 session log entry.
**Checkpoint ✅ (Phase 2 exit):** Manually cross-check one real stock's returned numbers against the actual PSX/Yahoo Finance site to confirm data correctness, not just "it renders something."

---

## PHASE 3 — AI Prediction Engine (LSTM + SVM/Random Forest)

### Step 3.1 — Data Acquisition

**Do:** Pull 3+ years of historical price data for an initial set of 10–20 KSE-100 constituent companies (not the full PSX listing yet). Store as versioned dataset files (e.g., `services/ml-engine/data/raw/`).
**Checkpoint ✅:** Dataset documented in Memory.md §15 (source, date range, tickers, row count).

### Step 3.2 — Feature Engineering Module

**Do:** Build a reusable module (`services/ml-engine/features.py`) computing RSI, MACD, Bollinger Bands, Moving Averages via TA-Lib, designed generically so a sentiment-score column can be merged in later (Phase 4) without restructuring.
**Checkpoint ✅:** Running the module on a sample ticker's data produces a feature dataframe with no NaN-handling bugs at the edges (first N rows where indicators need warm-up).

### Step 3.3 — Train/Val/Test Split Utility

**Do:** Implement a strictly chronological split function (never random shuffle) — e.g., 70/15/15 by date.
**Checkpoint ✅:** Unit test confirms no date in the validation/test set precedes any date in the training set.

### Step 3.4 — LSTM/BiLSTM Training Script

**Do:** Build and run the training script per Architecture.md §15.1 (2 stacked LSTM/BiLSTM layers, Dropout, Dense output). Save the trained artifact with a `model_version` tag (timestamp-based) to `services/ml-engine/models/`.
**Checkpoint ✅:** Training completes without error; RMSE and directional accuracy computed on the held-out test set and logged (whether or not they hit target).

### Step 3.5 — SVM / Random Forest Training Script

**Do:** Train buy/sell/hold classifiers on the same feature set (Architecture.md §15.2).
**Checkpoint ✅:** Classifiers trained, evaluated (accuracy/precision/recall), and artifact saved with matching `model_version`.

### Step 3.6 — Record Results

**Do:** Fill in Memory.md §10 (Model Performance Tracker) with real numbers from Steps 3.4–3.5.
**Checkpoint ✅:** Table populated, honestly, even if targets aren't yet met.

### Step 3.7 — Inference Module

**Do:** Build `services/ml-engine/inference.py` — loads the latest model artifact, takes a ticker, returns forecast + confidence score (derived from prediction variance or classifier probability).
**Checkpoint ✅:** Calling the inference module directly on a test ticker returns a validly-shaped, deterministic (given a fixed model) output.

### Step 3.8 — Database & Endpoint

**Do:** `predictions` table + migration; `/stocks/{ticker}/prediction` endpoint calling the inference module; `run_predictions` Celery task (daily schedule or on-demand trigger).
**Checkpoint ✅:** Endpoint returns real model output (not a stub); `predictions` rows correctly store `model_version`.

### Step 3.9 — Backend Tests

**Do:** Test the inference module against a fixture/frozen model artifact so tests are deterministic and fast (don't retrain in CI). Test the endpoint's low-confidence flagging logic (FR16).
**Checkpoint ✅:** Tests pass in CI.

### Step 3.10 — Frontend: Prediction Display

**Do:** On the stock detail screen — forecast line rendered visually distinct (dashed/lighter) from historical data, confidence indicator (Design.md §6.4), low-confidence visual flag when below threshold.
**Checkpoint ✅:** A manually-forced low-confidence test case visibly looks different in the UI than a high-confidence one.

### Step 3.11 — i18n + Docs Sync

**Do:** Route new copy through i18n; update Memory.md §2, §10, §7.
**Checkpoint ✅ (Phase 3 exit):** Real trained model drives predictions through the full API→UI path; results documented honestly in Memory.md.

---

## PHASE 4 — Sentiment Analysis (FinBERT)

### Step 4.1 — Finalize News Sources

**Do:** Resolve the open question in Memory.md §4 — pick an initial small, reliable set of financial news sources for PSX-listed companies.
**Checkpoint ✅:** Source list documented in Memory.md §9.

### Step 4.2 — Scraper Module

**Do:** Build scraper(s) with respectful request intervals, retries, and explicit error handling from the start (Rules.md §3.3). Store raw scraped articles/headlines with timestamps.
**Checkpoint ✅:** Running the scraper once against a live source returns real, correctly-parsed headlines for at least one test company.

### Step 4.3 — FinBERT Inference Module

**Do:** Load a pre-trained FinBERT model (HuggingFace), build `services/sentiment-engine/finbert_infer.py` — takes text, returns label + confidence.
**Checkpoint ✅:** Running on a known clearly-positive and clearly-negative headline returns the expected label.

### Step 4.4 — VADER Fallback Logic

**Do:** Implement the confidence-threshold fallback per Architecture.md §15.3.
**Checkpoint ✅:** Unit test confirms VADER is invoked when FinBERT confidence is artificially forced below threshold.

### Step 4.5 — Database, Endpoint, Job

**Do:** `sentiment_scores` table + migration; `/stocks/{ticker}/sentiment` endpoint; `scrape_news_sentiment` Celery task (scheduled every few hours).
**Checkpoint ✅:** Running the job populates real sentiment rows for the test company set.

### Step 4.6 — Merge Sentiment into Prediction Pipeline

**Do:** Extend the Step 3.2 feature module to include a (time-decayed average) sentiment feature; retrain the LSTM (repeat Step 3.4); compare new RMSE/accuracy against the pre-sentiment baseline.
**Checkpoint ✅:** Comparison numbers recorded in Memory.md §10 — clearly labeled "with sentiment" vs "without sentiment" baseline.

### Step 4.7 — Graceful Degradation Test

**Do:** Simulate a scraper/source failure; confirm prediction pipeline falls back to price/technical-only with a flagged reduced confidence, not a crash (FR22).
**Checkpoint ✅:** Manually verified via a forced-failure test.

### Step 4.8 — Frontend: Sentiment Display

**Do:** Sentiment badge (Design.md §17) on stock detail screen; expandable "what's driving this" headline view (FR21).
**Checkpoint ✅:** Real headlines visible and correctly attributed to their sentiment score in the UI.

### Step 4.9 — i18n + Docs Sync

**Checkpoint ✅ (Phase 4 exit):** Real news scraped/scored for the initial company set; sentiment measurably changes at least one test prediction; FinBERT accuracy documented.

---

## PHASE 5 — Portfolio Management & Cost Engine

### Step 5.1 — Cost Engine (build and test in complete isolation first)

**Do:** Implement brokerage fee, CGT, and WHT calculation functions using Python `Decimal` exclusively (Rules.md §3.4) in a standalone module (`services/api/services/cost_engine.py`) with zero dependency on portfolio logic yet.
**Checkpoint ✅:** Unit tests with hand-calculated known input→output pairs (e.g., "gross Rs. 100,000, expect exactly Rs. X net after fee/CGT/WHT") all pass — do this before writing a single line of portfolio-generation code.

### Step 5.2 — Database Models

**Do:** `portfolios`, `portfolio_holdings` models + migration.
**Checkpoint ✅:** Migration applies cleanly.

### Step 5.3 — Portfolio Generation Logic

**Do:** Combine risk profile (Phase 1) + latest predictions (Phase 3) + sentiment (Phase 4) into allocation percentages per company. Call the Step 5.1 cost engine functions directly (never re-implement the math inline) to compute gross→net per holding.
**Checkpoint ✅:** Given a fixture user with a known risk profile and fixture prediction data, output allocations are deterministic and match manual expectations.

### Step 5.4 — No Money Hold & Portfolio Rolling Logic

**Do:** Implement idle-capital detection/reallocation flagging (FR24) and underperformance-threshold-based rolling suggestions (FR25).
**Checkpoint ✅:** Fixture test cases: one with intentionally idle capital triggers a flag; one with an intentionally underperforming holding triggers a roll suggestion.

### Step 5.5 — Low-Capital Edge Case

**Do:** Explicitly handle and test the case where available capital is below the minimum for reasonable diversification (FR28) — return a clear explanatory message, not a broken/unbalanced portfolio.
**Checkpoint ✅:** Test with an artificially small capital amount confirms the explanatory path, not a crash or nonsensical output.

### Step 5.6 — Endpoints

**Do:** `/portfolio/generate`, `/portfolio/current`, `/portfolio/{id}/roll-check`, `/portfolio/{id}/exclude-stock`.
**Checkpoint ✅:** All four endpoints work correctly against a real logged-in test user with real Phase 3/4 data.

### Step 5.7 — Backend Tests

**Do:** Integration tests confirming the portfolio endpoint's fee/tax figures exactly match Step 5.1's isolated cost-engine test results (i.e., no drifted duplicate math).
**Checkpoint ✅:** Tests pass in CI.

### Step 5.8 — Frontend: Portfolio Recommendation Screen

**Do:** Build per Design.md §7.3 — plain-language summary first, holding cards (gross→net breakdown), "why this stock" expandable detail pulling real prediction/sentiment data, exclude/override flow (FR27).
**Checkpoint ✅:** A real test user can view a real portfolio, see correct fee/tax breakdowns, and exclude a stock to get a regenerated portfolio.

### Step 5.9 — i18n + Docs Sync

**Checkpoint ✅ (Phase 5 exit):** Real user + real risk profile + real predictions/sentiment → a real, correctly-costed portfolio, end-to-end through the UI.

---

## PHASE 6 — Backtesting

### Step 6.1 — Database Model

**Do:** `backtest_results` table + migration.
**Checkpoint ✅:** Migration applies cleanly.

### Step 6.2 — Benchmark Data

**Do:** Acquire KSE-100 historical index data covering the same date range as backtest inputs (FR32).
**Checkpoint ✅:** Data documented in Memory.md §15.

### Step 6.3 — Backtrader/QuantStats Integration

**Do:** Build the backtest runner — takes a portfolio (real or hypothetical), runs it against historical data, computes total return, Sharpe ratio, max drawdown, win rate.
**Checkpoint ✅:** Spot-check the output against a manual calculation on a small, simple fixture dataset (e.g., a 2-stock portfolio over 1 year) to confirm correctness, not just "it runs."

### Step 6.4 — Endpoints

**Do:** `/backtest/run`, `/backtest/{id}`.
**Checkpoint ✅:** Running a backtest on a real generated Phase 5 portfolio returns real, correctly-computed metrics.

### Step 6.5 — Backend Tests

**Checkpoint ✅:** Fixture-based tests pass in CI.

### Step 6.6 — Frontend: Backtest Report Screen

**Do:** Build per Design.md §7.4/§18 — headline total return, secondary metrics, benchmark comparison chart with always-visible legend.
**Checkpoint ✅:** Real backtest results render correctly, benchmark line visibly distinct from portfolio line.

### Step 6.7 — i18n + Docs Sync

**Checkpoint ✅ (Phase 6 exit):** Backtest runs against 3+ years of real data on a real portfolio; results recorded in Memory.md §10.

---

## PHASE 7 — Autonomous Agent & Notifications

### Step 7.1 — Database Model

**Do:** `notifications` table + migration.
**Checkpoint ✅:** Migration applies cleanly.

### Step 7.2 — Firebase Cloud Messaging Setup

**Do:** Configure FCM project; add web push config (`apps/web`) and mobile push config (`apps/mobile`, via Expo notifications).
**Checkpoint ✅:** A manually-sent test push notification is received on both a web browser and the Android app.

### Step 7.3 — Monitoring Job

**Do:** `monitor_portfolios` Celery Beat-scheduled task — checks active portfolios against fresh Phase 3/4 predictions/sentiment, determines if a buy/sell/roll trigger condition is met.
**Checkpoint ✅:** Manually forcing a trigger condition in test data causes the job to correctly identify it.

### Step 7.4 — Dispatch Job

**Do:** `send_notification` task — writes a `notifications` row and dispatches via FCM. Instrument timing (trigger → delivery) explicitly.
**Checkpoint ✅:** Measured latency is under the 5-second target (PRD.md §8.1); if not, this blocks phase completion — investigate and fix before moving on.

### Step 7.5 — Endpoints

**Do:** `/notifications` (list/inbox), `/notifications/preferences` (sensitivity settings, FR36).
**Checkpoint ✅:** Endpoints work correctly against real test data.

### Step 7.6 — Backend Tests

**Checkpoint ✅:** Tests for trigger-detection logic and notification creation pass in CI.

### Step 7.7 — Frontend (Web + Mobile)

**Do:** Notification permission flow, inbox/list UI (Design.md §7.5, grouped/chronological toggle), preference settings screen.
**Checkpoint ✅:** A real triggered notification appears correctly in both the OS-level push and the in-app inbox on both platforms.

### Step 7.8 — i18n + Docs Sync

**Checkpoint ✅ (Phase 7 exit):** Simulated trigger produces a real push notification on web and mobile within the 5-second target, with real reasoning text.

---

## PHASE 8 — LLM Chatbot (Bilingual Advisor)

### Step 8.1 — Database Model

**Do:** `chat_messages` table + migration.
**Checkpoint ✅:** Migration applies cleanly.

### Step 8.2 — Grounding Context Builder (isolated, tested before any LLM call)

**Do:** Build a function that, given a `user_id`, assembles a structured context object: risk profile, active portfolio holdings with current fee/tax figures, latest predictions/sentiment for any relevant stock.
**Checkpoint ✅:** Unit test confirms the context object is complete and correct for a fixture user — verify this thoroughly before Step 8.3, since everything downstream depends on this being right.

### Step 8.3 — Claude API Integration & System Prompt

**Do:** Write the system prompt enforcing: PSX-only scope, jargon-free explanation, bilingual (EN/UR) response capability, mandatory uncertainty disclosure on any prediction discussion, and an explicit instruction to only state figures present in the injected context (never compute or invent new ones). Build `/chat/message`, `/chat/history` endpoints.
**Checkpoint ✅:** A basic real conversation ("what's my portfolio look like?") returns a response that correctly reflects the fixture/real data from Step 8.2.

### Step 8.4 — Adversarial Testing (mandatory, don't skip)

**Do:** Deliberately test: (a) asking about a guaranteed return, (b) asking about crypto/out-of-scope assets, (c) asking it to state a specific price it wasn't given, (d) asking the same financial question in Urdu.
**Checkpoint ✅:** All four cases handled correctly (declines guarantee language, declines out-of-scope, never invents a figure, responds correctly in Urdu) — document each test case and result in Memory.md §7/§12.

### Step 8.5 — Backend Tests

**Do:** Test the grounding context builder (Step 8.2) with multiple fixture scenarios (empty portfolio, active portfolio, no predictions available yet).
**Checkpoint ✅:** Tests pass in CI.

### Step 8.6 — Frontend (Web + Mobile)

**Do:** Chat UI per Design.md §6.5 — bubble styling, inline "from your current portfolio" data-source tags, always-visible language toggle.
**Checkpoint ✅:** A real conversation flows correctly in the UI on both platforms, in both languages.

### Step 8.7 — i18n + Docs Sync

**Checkpoint ✅ (Phase 8 exit):** Chatbot correctly explains real portfolio/prediction data in both languages; all Step 8.4 adversarial tests pass; documented in Memory.md.

---

## PHASE 9 — Admin Panel

### Step 9.1 — Role Infrastructure

**Do:** Add a `role` field to `users` (`user` | `admin`) or a separate roles table; build a FastAPI dependency that enforces admin-only access.
**Checkpoint ✅:** Unit test confirms a `user`-role token is rejected (403) on a role-protected test endpoint, and an `admin`-role token succeeds.

### Step 9.2 — Database Model

**Do:** `admin_action_logs` table + migration.
**Checkpoint ✅:** Migration applies cleanly.

### Step 9.3 — Endpoints

**Do:** `/admin/users` (list/suspend), `/admin/system-health`, `/admin/models/retrain`, `/admin/news-sources` (list/add).
**Checkpoint ✅:** Each endpoint works correctly for an admin test account.

### Step 9.4 — Security Test (explicit, automated — not a manual UI check)

**Do:** Write an automated test hitting every single admin endpoint with a non-admin token, asserting 403 on all of them.
**Checkpoint ✅:** Test passes for every admin endpoint listed in Architecture.md §8; if any endpoint was missed, add it.

### Step 9.5 — System Health Data Wiring

**Do:** Wire `/admin/system-health` to real data: last successful `refresh_stock_prices` run, last `scrape_news_sentiment` run, last model retrain timestamp, recent API error rate (Architecture.md §18).
**Checkpoint ✅:** Health dashboard reflects real, current timestamps — not hardcoded placeholders.

### Step 9.6 — Frontend

**Do:** Admin route set within `apps/web` (Design.md §14.1 — visually distinct admin mode) — user management table, health dashboard, retrain trigger, news source management, analytics view.
**Checkpoint ✅:** Admin can view/suspend a user and trigger a retrain through the actual UI, reflected in a new `model_version`.

### Step 9.7 — Docs Sync

**Checkpoint ✅ (Phase 9 exit):** All Step 9.4 security tests pass; admin functions work correctly end-to-end through the UI.

---

## PHASE 10 — Mobile App Parity

### Step 10.1 — Gap Audit

**Do:** Go through Phases 1–9 screen-by-screen; list every web screen and its mobile equivalent status (done/partial/missing) in a working checklist.
**Checkpoint ✅:** Complete, accurate gap list produced.

### Step 10.2 — Close Gaps

**Do:** Implement any missing/partial mobile screens using `packages/shared-types`, `packages/api-client`, `packages/i18n`, `packages/design-tokens` — never diverging from the shared contract.
**Checkpoint ✅:** Every item from Step 10.1's list is now "done."

### Step 10.3 — Mobile-Specific Concerns

**Do:** Native push notification permission prompts; offline/stale-data handling (cached last-known portfolio/prediction shown with a "stale" indicator per Design.md §16, Architecture.md §16).
**Checkpoint ✅:** Turning off device network mid-use shows cached data with a visible stale indicator, not a blank/broken screen.

### Step 10.4 — Android QA Pass

**Do:** Full manual walkthrough of every core flow on an Android emulator/device.
**Checkpoint ✅:** No crashes, no broken navigation, no missing translations across a full onboarding→chat→notification walkthrough.

### Step 10.5 — Docs Sync

**Checkpoint ✅ (Phase 10 exit):** Every core flow completes successfully on Android against the real backend.

---

## PHASE 11 — Testing, Polish & Defense Prep

### Step 11.1 — Full Regression Pass

**Do:** Walk every screen on web and mobile against Rules.md §10 (Definition of Done) and Design.md §12 (loading/empty/error states).
**Checkpoint ✅:** Checklist completed with no unresolved gaps.

### Step 11.2 — i18n/Urdu Polish

**Do:** Review every Urdu string for tone (Design.md §10), ideally with a native-Urdu reviewer — not just literal-translation correctness.
**Checkpoint ✅:** Urdu copy reviewed and revised where it reads as stiff/machine-translated.

### Step 11.3 — Final Model Writeups

**Do:** Finalize Memory.md §10 with final, real numbers for the FYP report.
**Checkpoint ✅:** Table complete, ready to paste into the report's results section.

### Step 11.4 — Demo Resilience Test

**Do:** Simulate a network drop mid-demo; confirm the cached-data fallback path (Architecture.md §8.7) keeps the demo usable.
**Checkpoint ✅:** A full demo walkthrough survives a deliberately induced network interruption without visibly breaking.

### Step 11.5 — Defense Narrative Prep

**Do:** Using Memory.md §12 as a starting checklist, draft honest, specific answers to each anticipated question — especially anywhere a target metric wasn't fully met.
**Checkpoint ✅:** Written answers exist for every question in Memory.md §12.

### Step 11.6 — Final Documentation Sync

**Do:** Memory.md fully updated: final current state, known limitations, future work.
**Checkpoint ✅ (Phase 11 exit / PROJECT COMPLETE):** Full end-to-end demo (PRD.md §13) runs live, without failure, on both web and mobile, with a rehearsed fallback ready.

---

## Appendix A — Per-Phase Checklist Template (for the agent to self-verify before declaring a phase done)

```
Phase: ____
[ ] All DB migrations applied cleanly
[ ] All new endpoints covered by at least one passing test
[ ] No hardcoded secrets introduced (grep for obvious leaks before finishing)
[ ] All new user-facing strings routed through packages/i18n (en + ur both present)
[ ] Loading / empty / error states designed for every new screen (Design.md §12)
[ ] Disclaimer present on any new prediction/recommendation screen (PRD.md §8.5)
[ ] CI passing on the branch
[ ] Memory.md §2 (Current Status) updated
[ ] Memory.md §7 session log entry appended (template in Memory.md §17)
[ ] Any new decision logged in Memory.md §3
[ ] Any new pitfall/lesson logged in Memory.md §11
[ ] Phases.md exit criteria for this phase individually re-checked, not assumed
```

## Appendix B — If Something Goes Wrong Mid-Phase

- **A dependency (data source, API) is unavailable/blocked:** log it in Memory.md §9 as "Blocked ⚠️" with the reason, implement the graceful-degradation fallback path if not already present, flag it back to the human team rather than silently working around it with fabricated data.
- **A requirement is ambiguous:** state the assumption made, proceed, and flag it clearly in the PR description and Memory.md §4 — don't block indefinitely on something with a reasonable default (Rules.md §9.2).
- **A phase's work reveals that an earlier phase's decision needs to change:** update the relevant doc (Architecture.md, Design.md, etc.) _and_ log the change with reasoning in Memory.md §3 — never let code silently diverge from the docs.
- **Time pressure forces a scope cut:** cut from Phase 10 (Mobile Parity) or deep Phase 11 polish before ever cutting core web functionality (Phases 1–9) — a fully working web app with a partial mobile app is a stronger FYP submission than a rushed, broken version of both.

## Appendix C — CLI Command Cheat Sheet

```bash
# Local infra
cd infra && docker-compose up -d
docker-compose down

# Backend
cd services/api
python -m venv venv && source venv/bin/activate     # (or venv\Scripts\activate on Windows)
pip install -r requirements.txt
uvicorn main:app --reload
alembic revision --autogenerate -m "description"
alembic upgrade head
pytest
black . && ruff check .

# Celery
celery -A core.celery_app worker --loglevel=info
celery -A core.celery_app beat --loglevel=info

# Web
cd apps/web
npm install
npm run dev
npm run build
npm run lint
npm run type-check

# Mobile
cd apps/mobile
npm install
npx expo start
npx expo start --android

# ML training (example)
cd services/ml-engine
python train_lstm.py --tickers config/initial_tickers.txt --start 2021-01-01
python evaluate.py --model-version <version>

# Git
git checkout -b feature/<name>
git add . && git commit -m "feat(<scope>): <description>"
git push origin feature/<name>
```

## Appendix D — Example Prompts to Give Antigravity Per Phase

_(Use these as starting instructions when handing a specific phase to the agent — adjust wording as needed, but keep the structure: reference the docs, name the phase, name the checkpoint.)_

**Starting the whole project:**

> "Read Memory.md, PRD.md, Architecture.md, Rules.md, Phases.md, Design.md, and Workflow.md in that order. Start at Workflow.md Step 0.1 and proceed sequentially through Phase 0. Do not skip a checkpoint — verify each one is actually true before moving to the next step. Update Memory.md at the end of the session."

**Resuming a session:**

> "Read Memory.md Section 2 (Current Status) to see where we left off. Resume from the next incomplete step in Workflow.md. Check Memory.md Section 4 (Open Questions) and Section 11 (Known Pitfalls) before starting."

**Starting a specific phase (e.g., Phase 5):**

> "We're starting Phase 5 (Portfolio Management & Cost Engine) from Workflow.md. Confirm Phase 3 and Phase 4 exit criteria are actually met first (check Memory.md Section 2) — do not start Phase 5 if they aren't. Follow Workflow.md Steps 5.1 through 5.9 in order, verifying each checkpoint. Pay special attention to Step 5.1 — the cost engine must be built and unit-tested in complete isolation before any portfolio-generation code touches it."

**Asking for a review/audit:**

> "Go through Workflow.md Appendix A (Per-Phase Checklist Template) for the phase we just finished. Check each item honestly against the actual current codebase — don't mark anything done that wasn't actually verified. Report back anything that fails."

## Appendix E — Rollback & Recovery Procedures

- **A migration breaks the database:** `alembic downgrade -1` to revert one migration; never manually edit the database schema outside of Alembic migrations — this breaks reproducibility for the whole team.
- **A model retrain performs worse than the previous version:** keep the previous `model_version` artifact until the new one is confirmed better on the held-out test set (Memory.md §10) — never overwrite the last known-good model artifact in place; version them side by side and only switch the "active" pointer once confirmed.
- **A phase's work is discovered to conflict with an earlier architectural decision:** stop, don't patch around it silently. Update the relevant doc (Architecture.md/Design.md/etc.) with the new decision and reasoning in Memory.md §3, get it acknowledged, then proceed.
- **CI is broken on `main`:** treat as the highest priority — no new feature branches should build on top of a broken `main`. Fix or revert the breaking commit before continuing other work.
- **An external API/data source changes its response format or becomes unavailable long-term:** don't hack around it in the calling code — update the isolated integration client module (Step 2.2 pattern — this is exactly why that isolation exists) and note the change in Memory.md §9/§11.
