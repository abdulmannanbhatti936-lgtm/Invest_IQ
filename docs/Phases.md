# Phases.md — InvestIQ
### Development Roadmap, Sequencing & Exit Criteria

**Companion docs:** PRD.md, Architecture.md, Rules.md
**Purpose of this document:** This is the single source of truth for **what to build right now** vs **what comes later**. An AI coding agent (or a human) reading this should never build ahead of the current phase, never skip a phase's exit criteria, and never assume a future phase's work is already available.

**Current status: Phase 0 — not yet started.** A previous demo was made but is explicitly not being carried forward (see PRD.md, Memory.md). Treat this as a greenfield build.

---

## How to use this document

- Each phase lists: **Goal**, **Tasks**, **Owner split**, **Depends on**, **Exit criteria (Definition of Done for the phase)**.
- **Do not start a phase's tasks until the previous phase's exit criteria are fully met.** If asked to build something from a later phase early, flag it rather than silently doing it — this prevents half-finished, undocumented features piling up.
- If a task within a phase turns out to depend on something not yet built, stop and flag it — don't invent a workaround that violates Architecture.md.
- "Owner split" is a suggestion for the two-person team (Manam / Ali), not a hard rule — adjust based on actual availability, but keep one clear owner per task to avoid duplicated work.

---

## Phase 0 — Foundation & Project Setup

**Goal:** A working, empty skeleton that both teammates (and the AI agent) can build on without setup friction.

**Tasks:**
- Initialize monorepo per Architecture.md Section 5 (`apps/`, `services/`, `packages/`, `infra/`, `docs/`)
- Set up `docker-compose.yml` for local Postgres + Redis
- Scaffold FastAPI backend (`services/api`) with health-check endpoint, base folder structure (`routers/`, `services/`, `crud/`, `models/`)
- Scaffold React + Vite web app (`apps/web`) with routing skeleton and Tailwind configured
- Scaffold React Native (Expo) app (`apps/mobile`)
- Set up `packages/shared-types`, `packages/api-client`, `packages/i18n` as empty/minimal workspaces
- Configure linting/formatting (ESLint, Prettier, black, ruff) per Rules.md
- Set up GitHub Actions CI (lint + test on PR) per Architecture.md Section 20
- Commit `.env.example` files for backend and frontend per Architecture.md Section 17
- Write root `README.md` with local dev setup instructions

**Owner split:** Both — pair on initial scaffolding to agree on conventions before splitting off.

**Depends on:** Nothing (first phase).

**Exit criteria:**
- [ ] `docker-compose up` starts Postgres + Redis locally
- [ ] FastAPI backend runs locally and `/health` returns 200
- [ ] Web app runs locally and renders a placeholder home page
- [ ] Mobile app runs on Expo Go / emulator and renders a placeholder screen
- [ ] CI pipeline passes on an empty/skeleton commit
- [ ] Both teammates can clone the repo and get everything running from README instructions alone

---

## Phase 1 — Auth, Onboarding & Risk Profiling

**Goal:** A user can register, log in, and complete risk profiling on web. Implements PRD.md FR1–FR6.

**Tasks:**
- Backend: `users`, `risk_profiles` tables/models (per Architecture.md Section 7)
- Backend: `/auth/register`, `/auth/login`, `/auth/refresh` endpoints, JWT issuance, password hashing
- Backend: `/users/me`, `/users/me/risk-profile` endpoints
- Frontend (web): registration/login screens, onboarding questionnaire flow, risk profile result screen
- Frontend: route guard — user cannot reach any dashboard/portfolio screen without a completed risk profile (FR per Section 7.1 acceptance criteria in PRD.md)
- i18n: onboarding + auth screens in English and Urdu

**Owner split:** Backend auth/DB → one teammate; frontend onboarding flow → the other.

**Depends on:** Phase 0 complete.

**Exit criteria:**
- [ ] New user can register, log in, complete the risk questionnaire, and land on a (placeholder) dashboard
- [ ] Risk profile persists across logout/login
- [ ] Partial-onboarding resume works (FR6 edge case)
- [ ] Auth endpoints have passing unit/integration tests
- [ ] Disclaimer language (PRD.md Section 8.5) shown at onboarding

---

## Phase 2 — Stock Data & Market Analysis

**Goal:** Any PSX-listed stock can be looked up with real historical/current data. Implements FR7–FR10.

**Tasks:**
- Backend: `stocks`, `price_points` tables
- Backend: integration with Yahoo Finance API + PSX data source, with Redis caching (Architecture.md Section 10)
- Backend: `/stocks/search`, `/stocks/{ticker}`, `/stocks/{ticker}/history` endpoints
- Backend: `refresh_stock_prices` Celery job (Architecture.md Section 9)
- Frontend: stock search/browse screen, stock detail screen with price chart, volume, key stats
- Handle FR10 edge case: insufficient-data message when a stock lacks history

**Owner split:** Data integration/backend → one teammate; charting UI → the other.

**Depends on:** Phase 0 complete. (Independent of Phase 1's user features, but auth should exist if endpoints are protected.)

**Exit criteria:**
- [ ] Searching any real PSX ticker returns live/cached data
- [ ] Price chart renders correctly with real historical data
- [ ] Rate-limit/outage on the data source degrades gracefully, doesn't crash the app
- [ ] Redis cache verified to reduce redundant external API calls

---

## Phase 3 — AI Prediction Engine (LSTM + SVM/Random Forest)

**Goal:** Real, trained models produce a price forecast + buy/sell/hold signal for a selected stock. Implements FR11–FR16.

**Tasks:**
- Data pipeline: historical PSX data ingestion for model training (min. 3+ years per PRD.md backtesting requirement)
- Feature engineering: TA-Lib indicators (RSI, MACD, Bollinger Bands, Moving Averages)
- Train LSTM/BiLSTM model per Architecture.md Section 15.1; evaluate against RMSE/directional accuracy targets
- Train SVM/Random Forest classifiers per Architecture.md Section 15.2
- Backend: `predictions` table, `/stocks/{ticker}/prediction` endpoint
- Backend: `run_predictions` Celery job
- Frontend: prediction display on stock detail screen — forecast + confidence score, low-confidence flag (FR16)
- Document model evaluation results (for FYP report + Memory.md updates)

**Owner split:** ML training/pipeline → whichever teammate is stronger in ML (or split: one trains LSTM, other handles SVM/RF + integration); API/frontend integration → the other.

**Depends on:** Phase 2 complete (needs real stock data flowing).

**Exit criteria:**
- [ ] LSTM model trained and evaluated; RMSE and directional accuracy documented (target: RMSE < 5%, accuracy > 80% — if not met, documented and explained, not hidden)
- [ ] Prediction endpoint returns real model output, not a placeholder
- [ ] Confidence score displayed and low-confidence predictions visibly flagged in UI
- [ ] `model_version` tracked per Architecture.md Section 15.4

---

## Phase 4 — Sentiment Analysis (FinBERT)

**Goal:** Real news sentiment feeds into the prediction pipeline and is visible to the user. Implements FR17–FR22.

**Tasks:**
- News scraper implementation for configured sources (Architecture.md Section 6.3)
- FinBERT inference pipeline + VADER fallback
- Backend: `sentiment_scores` table, `/stocks/{ticker}/sentiment` endpoint
- Backend: `scrape_news_sentiment` Celery job
- Re-train/update LSTM to include sentiment as an input feature (extends Phase 3's model)
- Frontend: sentiment display on stock detail screen, with "what's driving this" headline view (FR21)
- Handle FR22 edge case: scraper/source failure degrades gracefully

**Owner split:** Scraper + FinBERT pipeline → ML-focused teammate; sentiment UI → the other.

**Depends on:** Phase 3 complete (sentiment feeds into the existing prediction pipeline, doesn't replace it).

**Exit criteria:**
- [ ] Real news scraped and scored for at least a meaningful set of PSX-listed companies
- [ ] Sentiment score visibly influences prediction output (documented, testable)
- [ ] FinBERT accuracy evaluated against target (>85%) and documented
- [ ] Graceful fallback verified when a news source is deliberately blocked/unavailable in testing

---

## Phase 5 — Portfolio Management & Cost Engine

**Goal:** A logged-in user with a risk profile gets a real, personalized, fully-costed portfolio. Implements FR23–FR28.

**Tasks:**
- Backend: `portfolios`, `portfolio_holdings` tables
- Backend: portfolio generation logic — combines risk profile + predictions + sentiment into allocations
- Backend: fee/tax calculation engine (brokerage fee, CGT, WHT) using `Decimal` per Rules.md Section 3.4, with unit tests
- Backend: "No Money Hold" policy logic (FR24), Portfolio Rolling logic (FR25)
- Backend: `/portfolio/generate`, `/portfolio/current`, `/portfolio/{id}/roll-check`, `/portfolio/{id}/exclude-stock` endpoints
- Frontend: portfolio recommendation screen — allocations, gross→net price breakdown, exclude/override option (FR27)
- Handle FR28 edge case: capital too low for diversification

**Owner split:** Portfolio/cost-engine backend logic → one teammate (this is the most FYP-defense-critical logic, treat carefully); portfolio UI → the other.

**Depends on:** Phase 1 (auth/risk profile), Phase 3 (predictions), Phase 4 (sentiment) all complete.

**Exit criteria:**
- [ ] A real user with a real risk profile receives a portfolio built from real prediction + sentiment data
- [ ] Every holding shows accurate gross→net price after fee/CGT/WHT
- [ ] Fee/tax calculation has passing unit tests with known input/output pairs
- [ ] Portfolio Rolling and No Money Hold logic demonstrably work (test cases, not just "looks right")

---

## Phase 6 — Backtesting

**Goal:** A user can validate a portfolio's historical performance before trusting it. Implements FR29–FR32.

**Tasks:**
- Backend: `backtest_results` table
- Backend: Backtrader/QuantStats integration, `/backtest/run`, `/backtest/{id}` endpoints
- Frontend: backtest report screen — total return, Sharpe ratio, max drawdown, win rate, KSE-100 benchmark comparison (FR32)

**Owner split:** Backtesting logic → ML-focused teammate; report UI → the other.

**Depends on:** Phase 5 complete (backtests run against real generated portfolios).

**Exit criteria:**
- [ ] Backtest runs against 3+ years of real historical PSX data
- [ ] Report metrics match manual spot-check calculations
- [ ] Sharpe ratio target (>1.0) documented as met or explained if not

---

## Phase 7 — Autonomous Agent & Notifications

**Goal:** Users get real, timely push alerts without checking the app manually. Implements FR33–FR36.

**Tasks:**
- Backend: `notifications` table, `monitor_portfolios` and `send_notification` Celery jobs
- Firebase Cloud Messaging integration (web + mobile)
- Backend: `/notifications`, `/notifications/preferences` endpoints
- Frontend (web + mobile): notification permission flow, notification list/inbox, preference settings (FR36)

**Owner split:** Backend job/FCM integration → one teammate; frontend notification UX (both platforms) → the other.

**Depends on:** Phase 5 complete (needs real active portfolios to monitor).

**Exit criteria:**
- [ ] A simulated buy/sell/roll trigger produces a real push notification on both web and mobile within the 5-second latency target
- [ ] Notification includes real reasoning text, not a placeholder
- [ ] User can adjust notification sensitivity and see the effect

---

## Phase 8 — LLM Chatbot (Bilingual Advisor)

**Goal:** A user can have a real, grounded conversation about their portfolio/predictions in English or Urdu. Implements FR37–FR41.

**Tasks:**
- Backend: `chat_messages` table, `/chat/message`, `/chat/history` endpoints
- Backend: context-grounding pipeline per Architecture.md Section 12 (fetch real user data → build context → call Claude API)
- System prompt engineering: PSX-only scope enforcement, jargon-free tone, mandatory uncertainty disclosure, bilingual capability
- Frontend (web + mobile): chat UI, language toggle/detection
- Handle FR41 edge case: out-of-scope questions handled gracefully, not improvised

**Owner split:** Backend grounding pipeline + prompt engineering → whoever is most comfortable with the Claude API; chat UI → the other.

**Depends on:** Phase 5 (portfolio) and Phase 3/4 (predictions/sentiment) complete — the chatbot has nothing real to ground itself in otherwise.

**Exit criteria:**
- [ ] Chatbot correctly explains a real user's actual current portfolio and predictions, in both English and Urdu
- [ ] Chatbot never states a figure that doesn't match the database
- [ ] Chatbot declines out-of-scope questions (e.g., crypto) instead of improvising
- [ ] Manual adversarial testing done — try to get it to hallucinate a guarantee or a fake number, confirm it doesn't

---

## Phase 9 — Admin Panel

**Goal:** Admin can manage users, monitor system health, and control models/news sources. Implements FR42–FR46.

**Tasks:**
- Backend: role-based access control (admin vs user), `admin_action_logs` table
- Backend: `/admin/users`, `/admin/system-health`, `/admin/models/retrain`, `/admin/news-sources` endpoints
- Frontend: admin route set within `apps/web` (per Architecture.md Section 21 recommendation) — user management, system health dashboard, model retrain trigger, news source management, analytics view

**Owner split:** Either teammate — this is lower-risk, well-isolated work, good candidate for whoever has bandwidth after their earlier phase work.

**Depends on:** All prior phases (admin panel surfaces status/data from everything built so far).

**Exit criteria:**
- [ ] Admin can view/suspend a user
- [ ] System health dashboard shows real last-refresh timestamps for prices, sentiment, and models
- [ ] Admin can trigger a model retrain and see it reflected in `model_version`
- [ ] Non-admin users cannot access any admin endpoint (verified with a test, not just UI hiding)

---

## Phase 10 — Mobile App Parity

**Goal:** Everything built for web (Phases 1–9) is also usable on the React Native mobile app.

**Tasks:**
- Port each web screen's equivalent to `apps/mobile` using shared `packages/shared-types`, `packages/api-client`, `packages/i18n`
- Mobile-specific: push notification permission flow, offline/stale-data handling (Architecture.md Section 16)
- QA pass on Android emulator/device

**Owner split:** Whoever owned the frontend on web is the natural owner here, given shared code/patterns — but this is a good place for the other teammate to contribute directly to mobile if their earlier phase work is done.

**Depends on:** Phases 1–9 substantially complete on web (mobile should not be the first place a feature is built, per Architecture.md's "one backend, multiple clients" philosophy).

**Exit criteria:**
- [ ] Every core user flow (onboarding → prediction → portfolio → backtest → chat → notification) works end-to-end on Android
- [ ] No feature exists on mobile that doesn't also exist on web (and vice versa, ideally)

---

## Phase 11 — Testing, Polish & Defense Prep

**Goal:** A submission-ready, defensible FYP.

**Tasks:**
- Full end-to-end QA pass across web + mobile (Rules.md Section 10, Definition of Done, applied project-wide)
- Fill any i18n gaps (rough Urdu → polished Urdu)
- Prepare model evaluation writeups (RMSE, accuracy, Sharpe ratio results) for the FYP report
- Prepare live-demo script and fallback (cached data path) in case of live API/network issues during defense (PRD.md Section 8.7)
- Update Memory.md with final state, known limitations, and anything the panel might ask about

**Owner split:** Both, together.

**Depends on:** All prior phases.

**Exit criteria:**
- [ ] Full demo flow (per PRD.md Section 13, Success Metrics) runs live without failure
- [ ] Documented, honest model metrics ready to present (met targets, or explained gaps)
- [ ] Defense narrative ready: problem → literature gap → solution → live demo → limitations → future work

---

## Sequencing Summary

```
Phase 0  Foundation
Phase 1  Auth & Risk Profiling ──┐
Phase 2  Stock Data ─────────────┼──> Phase 3 Prediction (LSTM) ──> Phase 4 Sentiment (FinBERT)
                                  │                                        │
                                  └──────────────> Phase 5 Portfolio & Cost Engine <──┘
                                                          │
                                        ┌─────────────────┼─────────────────┐
                                        ▼                 ▼                 ▼
                                  Phase 6            Phase 7           Phase 8
                                  Backtesting         Notifications      Chatbot
                                        │                 │                 │
                                        └─────────────────┴─────────────────┘
                                                          │
                                                    Phase 9 Admin Panel
                                                          │
                                                Phase 10 Mobile Parity
                                                          │
                                            Phase 11 Testing & Defense Prep
```

**Hard rule for the AI agent:** never implement Phase 5 (Portfolio) logic before Phase 3 (Prediction) and Phase 4 (Sentiment) are done — it would have nothing real to build a portfolio from. Never implement Phase 8 (Chatbot) before Phase 5 — it would have nothing real to ground itself in. If asked to jump ahead, say so explicitly rather than building on top of placeholder/mocked data that could get mistaken for real integration later.
