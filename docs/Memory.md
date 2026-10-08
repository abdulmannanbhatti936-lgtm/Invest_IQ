# Memory.md — InvestIQ

### Persistent Project Context & State

**Purpose:** This is the file an AI coding agent (Antigravity AI) should read **first, every session**, before touching code. PRD.md / Architecture.md / Rules.md / Phases.md / Design.md are the stable reference docs — this file is the living state: what's actually true right now, what's been decided, what's still open, and what happened recently. Update this file at the end of every significant work session.

---

## 1. Project Identity

- **Project:** InvestIQ — AI-Based Portfolio Management System for PSX Investors
- **Type:** Final Year Project (BSCS), NUML Islamabad, Dept. of Computer Science
- **Team:** Muhammad Ali Khaliq (CGPA 3.08) & Abdul Mannan Bhatti / "Manam" (CGPA 2.58)
- **Supervisor:** Mr. Zain-ul-Abideen
- **One-line pitch:** A bilingual (English/Urdu) AI advisor that turns raw PSX data into a personalized, fully-costed, jargon-free investment portfolio for novice Pakistani retail investors — advisory only, no trade execution.

## 2. Current Status (update this section every session)

**Active:** re-verification of Phases 0–3 against the docs (branch `fix/phase-0-3-completion`, pushed; CI green). The earlier "COMPLETED" marks for Phases 2–3 were not backed by checkpoint evidence, so each phase is being re-checked step by step.

- **Phase 0 — Foundation:** all checkpoints re-run on 2026-10-09 and passing locally (Docker healthchecks, `/health`, all web routes with no console errors, mobile bundle + Metro, shared-package imports, lint/format/CI commands). CI green on GitHub (run 37837093050, commit 8d4779d) after pinning backend requirements. **Still open:** the README hasn't been tested from a fresh clone by a second person.
- **Phase 1 — Auth & Risk Profiling:** re-verification in progress, one step at a time. Step 1.1 PASSED (2026-10-09; fixed a downgrade that left the `riskcategory` enum behind). 60 pytest pass. Risk scoring + safety caps approved by the team on 2026-10-09 (§3) and implemented with tests. **Open:** full Phase 1 step-by-step re-verification (browser end-to-end, Urdu text review by a native speaker).
- **Phase 2 — Stock Data:** backend, web screens and Celery jobs exist; worker and beat start cleanly. Mobile screens (Step 2.9) are not built.
- **Phase 3 — Prediction Engine:** models trained on 12 PSX tickers (5 years of Yahoo `.KA` data). Honest result: the models do **not** beat the naive baselines yet (see §10); all live predictions are flagged low-confidence.

> _Update instructions: replace this section's content each session with (a) which phase is active, (b) what was completed since the last update, (c) what's in progress, (d) what's blocked/waiting on a decision._

## 3. Key Decisions Log

Decisions made so far, with the reasoning, so they're never silently re-litigated or reversed by accident:

| Decision                                                    | Reasoning                                                                                                             | Where documented                                                                 |
| ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| Fresh rebuild, old demo discarded                           | Team chose to start clean rather than extend prior demo                                                               | Memory.md (this entry)                                                           |
| Web + Mobile both in Phase 1 scope                          | Explicit team choice, not deferred                                                                                    | PRD.md §6.1                                                                      |
| Mobile framework: **React Native (Expo)**, not Flutter      | Team's existing stack is React/JS; enables shared TS types/API client with web; lower ramp-up for a 2-person FYP team | Architecture.md §4                                                               |
| Monorepo structure                                          | Keeps API contract, shared types, and both frontends in sync across a small team                                      | Architecture.md §5                                                               |
| Database: Postgres recommended over MySQL                   | Better JSONB support for risk-profile answers                                                                         | Architecture.md §21 (still technically "open" — confirm before Phase 1 DB setup) |
| Admin panel: route within `apps/web`, not a separate app    | Simplicity for FYP scale                                                                                              | Architecture.md §21                                                              |
| LLM chatbot always grounded in real DB data, never freeform | Prevents hallucinated financial advice — named as a top risk in PRD.md §15                                            | Architecture.md §12, Rules.md §1                                                 |
| Color palette: **left as placeholder**                      | Manam will decide and provide later                                                                                   | Design.md §2                                                                     |
| Financial math uses `Decimal`, never float                  | Rounding errors unacceptable when showing real prices                                                                 | Rules.md §3.4                                                                    |
| Risk scoring (2026-10-09): 7 questions × 3/2/1 pts (7–21); 7–11 Conservative, 12–16 Moderate, 17–21 Aggressive; safety caps after scoring: need money within 1 yr → max Conservative; would sell on a drop OR emergency savings < 3 months → max Moderate | Team decision. PRD FR2/FR3 only named the topics; the caps stop a high scorer with a short horizon, panic-selling tendency or no safety cushion from being pushed into aggressive picks | `services/api/services/risk_scoring.py`, DetailedReport.md Step 1.3 |
| `users.role` added early (planned for Step 9.1) because the admin route guard needed it; `users.onboarding_progress` (JSONB) added for FR6 resume (2026-10-09) | Removing `role` until Phase 9 would only create churn; FR6 needs partial answers stored server-side | Architecture.md §7 |

## 4. Open Questions / Not Yet Decided

Carried over from PRD.md §17 and Architecture.md §21 — resolve these before/during the relevant phase, don't let the agent guess silently:

- [ ] Final color palette (Design.md §2) — pending Manam
- [ ] Exact PSX data source for production: official PSX API access vs scraping — needs testing/confirmation before Phase 2
- [ ] Postgres vs MySQL — leaning Postgres, not yet formally locked
- [ ] OAuth (Google login) — in scope for v1 onboarding or deferred?
- [ ] Specific financial news sources for the sentiment scraper — to be finalized before Phase 4
- [ ] iOS support for mobile — Android is the committed target; iOS is a stretch goal only
- [ ] **Phase 2 re-audit — graceful degradation gaps (found 2026-10-09 while offline):** with Yahoo unreachable, `GET /stocks/{ticker}/history` returned **200 with 0 points** instead of serving the stored `price_points` (15k+ rows) or a 503, and `GET /stocks/{ticker}` returned **404 "No market data found"** instead of 503 because yfinance reports a network failure as "no data" (Architecture §8.3, Workflow Step 2.6). Fix during the Phase 2 audit.
- [ ] **Migrate naive timestamps to `TIMESTAMPTZ`?** `users.created_at`, `risk_profiles.updated_at`, `predictions.generated_at` and `news_sentiments.timestamp` are `timestamp without time zone` (all written with `utcnow()`, so they hold UTC); only `price_points.timestamp` is `timestamptz`. Since 2026-10-09 the API marks every datetime as UTC (`schemas/types.py`, trailing `Z`) and the web shows Asia/Karachi time, so behaviour is already correct. Recommended: migrate those 4 columns to `TIMESTAMPTZ` (`USING col AT TIME ZONE 'UTC'`) so the database itself is unambiguous — awaiting team approval.
- [ ] **Phase 5 must enforce the risk profile on the server:** the Phase 1 route guard is screen-only (PRD §7.1 acceptance criteria are about screens). Every Phase 5 portfolio endpoint (`/portfolio/*`) must reject a user without a completed risk profile server-side (e.g. a `require_risk_profile` dependency → 403/409), since recommendations depend on the profile (FR4). Decided 2026-10-09, not built yet.
- [ ] **Admin endpoints (Phase 9):** `require_admin` (`core/deps.py`) exists and was probed on 2026-10-09 (admin 200, non-admin 403, no token 401), and is covered by `tests/test_admin_guard.py` on a test-only route (admin 200, non-admin 403, no token 401). No real endpoint uses it yet — Step 9.4 must still test every real admin endpoint.

## 5. Known Constraints

- **Two-person team.** Every phase's owner-split suggestion in Phases.md assumes this — don't plan work as if more people are available.
- **FYP timeline**, not a commercial product timeline. Phases.md sequencing exists specifically to prevent scope creep that would jeopardize submission — respect it strictly.
- **CGPA/workload context**: both team members are full-time students; don't assume unlimited daily development bandwidth when estimating what's reasonable per session.
- Advisory-only boundary (no trade execution) is not a v1 limitation to work around — it's a permanent product boundary (PRD.md §6.2).

## 6. Document Map (what lives where — check before asking or duplicating)

| Question                                                                  | Go to                                 |
| ------------------------------------------------------------------------- | ------------------------------------- |
| What should this feature do exactly?                                      | PRD.md (functional requirements, FR#) |
| What's the tech stack / how do services talk to each other?               | Architecture.md                       |
| What's the DB schema / API endpoint shape?                                | Architecture.md §7–8                  |
| How should this code be written/formatted/committed?                      | Rules.md                              |
| Can I build this now, or does it depend on something else first?          | Phases.md                             |
| What should this look like / what color-blind-safe pattern applies?       | Design.md                             |
| What's already been decided, what's still open, what's the current state? | Memory.md (this file)                 |

## 7. Session Log

_(Append a new dated entry each significant session — keep entries short. This is a changelog, not a diary.)_

[Date TBD] — Initial planning phase complete. PRD.md, Architecture.md, Rules.md,
Phases.md, Design.md, Memory.md created. No code written yet. Next: Phase 0
(Foundation & Project Setup) per Phases.md.

[2026-08-14] — Phase 0
Completed: Step 0.1 (Repository skeleton, docs sync).
Completed: Step 0.2 (Local Infrastructure - Docker).
Completed: Step 0.3 (Backend Skeleton - FastAPI, Alembic).
Completed: Step 0.4 (Web App Skeleton - Vite, React Router, Tailwind, React Query).
Completed: Step 0.5 (Mobile App Skeleton - Expo, React Navigation, React Query).
Completed: Step 0.6 (Shared Packages - Types, API client, i18n, Tokens).
Blocked: None.
Decisions made:

- Changed Postgres port to 5435 in docker-compose.yml to avoid conflicts with native Windows Postgres on 5432.
- Configured npm workspaces in root package.json for sharing packages between mobile and web.
  Next session should: Proceed to Step 0.7 (Linting, Formatting, CI).

[2026-08-15] — Phase 0 Completion
Completed: Step 0.5 through Step 0.8.
Completed: Step 0.7 (Linting, Formatting, CI - ESLint, Prettier, Ruff, Black, Pytest in GitHub Actions).
Completed: Step 0.8 (Documentation Sync - README.md updated, Phase 0 complete).
Blocked: None.
Decisions made:

- Added `CORSMiddleware` directly to the FastAPI skeleton to ensure smooth frontend-backend connection in local dev.
  [2026-08-16] — Phase 1, Step 1.2 Complete
  Completed: Step 1.2 (Auth API Endpoints) - Implemented FastAPI endpoints for register, login, and `/users/me`. Verified via tests.
  Blocked: None.
  Next session should: Proceed to Step 1.3 (Auth Frontend Web) or Step 1.4 (Auth Mobile).

[2026-09-14] — Phase 1, Steps 1.3 and 1.4 Complete
Completed: Step 1.3 (Risk Profile Backend) - Implemented risk scoring logic and API endpoints. Completed: Step 1.4 (Auth Unit/Integration Tests) - Implemented exhaustive pytest coverage for auth endpoints including refresh tokens.
Blocked: None. (Previously blocked by Docker, but resolved by switching to native Postgres on port 5435).
Next session should: Proceed to Step 1.5 (Web: Auth Screens).

[2026-09-19] — Phase 2, Step 2.1 Complete
Completed: Step 2.1 (Database Models) - Created SQLAlchemy models for `stocks` and `price_points` per Architecture.md §7. Generated and applied Alembic migration successfully to Postgres.
Blocked: None.
Next session should: Proceed to Step 2.2 (External Data Client Module).

[2026-09-19] — Phase 2, Step 2.2 Complete
Completed: Step 2.2 (External Data Client Module) - Built `integrations/market_data.py` wrapping Yahoo Finance (`yfinance`) with a clean interface (`get_quote`, `get_history`).
Blocked: Yahoo Finance coverage of PSX is poor (e.g., `ENGRO.KA` not found, but `SYS.KA` works). Noted in Known Pitfalls. We will use available `.KA` tickers for the pipeline tests or use an alternate scraper later.
Decisions made: The client will not auto-append `.KA` so it can be flexible.
Next session should: Proceed to Step 2.3 (Redis Caching Layer).

[2026-09-19] — Phase 2, Step 2.3 Complete
Completed: Step 2.3 (Redis Caching Layer) - Implemented `StockService` with `get_quote_cached` and `get_history_cached`. Connected to the local Redis container via `redis-py` and verified 15-minute TTL caching works.
Blocked: None.
Next session should: Proceed to Step 2.4 (Endpoints).

[2026-09-19] — Phase 2, Step 2.4 Complete
Completed: Step 2.4 (Endpoints) - Created Pydantic schemas and FastAPI router `routers/stocks.py` for `/stocks/search`, `/stocks/{ticker}`, and `/stocks/{ticker}/history`. Wired it into `main.py` and wrote full integration tests via `TestClient`. Tests passed beautifully.
Blocked: None.
Next session should: Proceed to Step 2.5 (Automated Fetch Job).

[2026-09-19] — Phase 2, Step 2.5 Complete
Completed: Step 2.5 (Automated Fetch Job) - Implemented `core/celery_app.py` and `worker/tasks.py`. Created a Celery background task `fetch_market_data_for_tickers` that bulk-fetches and bulk-inserts `PricePoint` history into Postgres.
Blocked: None.
Next session should: Proceed to Step 2.6 (Sentiment Model DB setup).

[2026-09-19] — Phase 2, Step 2.6 Complete
Completed: Step 2.6 (Sentiment Model) - Created `NewsSentiment` SQLAlchemy model inside `models/sentiment.py`. Added one-to-many relationship in `Stock`. Generated and applied Alembic migration. Validated via throwaway script.
Blocked: None.
Next session should: Proceed to Step 2.7 (News Scraper Job).

[2026-09-19] — Phase 2, Step 2.7 Complete
Completed: Step 2.7 (News Scraper Job) - Built `integrations/news_scraper.py` using `requests` and `BeautifulSoup`. Scraped Yahoo Finance RSS XML feed for a ticker, parsed the titles, and bulk-inserted 17 real headlines into the `news_sentiments` table with mock 0.0 scores.
Blocked: None.
Next session should: Proceed to Step 2.8 (Celery Beat configuration).

[2026-09-19] — Phase 2 COMPLETE! (Step 2.8)
Completed: Step 2.8 (Celery Beat Configuration) - Defined cron schedules inside `core/celery_app.py`. Configured `fetch-eod-market-data` to run daily at 18:00 (End of Day) and `fetch-hourly-news` to run every hour at minute 0. Validated config via script. Phase 2 is officially 100% complete!
Blocked: None.
Next session should: Proceed to Phase 3 (Machine Learning - Core Logic).

[2026-09-27] — Phase 3 (Backend) COMPLETE! (Step 3.4)
Completed: Step 3.4 (LSTM Price Prediction Logic) - Created `lstm_predictor.py` using PyTorch. The model incorporates historical prices, TA-Lib indicators, and FinBERT sentiment scores. Added `run_predictions` Celery task in `worker/tasks.py` and a `/stocks/{ticker}/prediction` endpoint in `routers/stocks.py` using the `Prediction` model.
Blocked: Phase 2 and 3 frontend screens are pending. The web UI needs to catch up before we can fully call the frontend complete.
Next session should: Either build the UI for Phase 2/3 (Stock details and Prediction screens) or proceed to Phase 4 (Sentiment Analysis - Core Logic).

[2026-09-27] — Phase 2 & Phase 3 (Frontend UI) COMPLETE!
Completed: Built `Stocks.tsx` (market overview and search) and `StockDetail.tsx` (price chart, key stats, and AI prediction forecast). Implemented `recharts` for the price chart with a distinct visual forecast line and confidence indicators per the `Design.md` guidelines. Added new `Card` and `Badge` UI components. Phase 3 is now 100% complete across the stack.
Blocked: None.
Next session should: Proceed to Phase 4 (Sentiment Analysis - Core Logic).

[2026-10-09] — Phase 0 re-verification
Completed: Re-ran every Phase 0 checkpoint. Fixed: .gitignore (joblib/artifacts/caches), missing services/ml-engine, sentiment-engine, chatbot-service and infra/deploy folders (README stubs, per Architecture §5/§6.5), wrong DB port in .env.example (5432→5435), Docker healthchecks, react-is peer dependency (the web build was failing), mobile import of a removed type, CI env vars (SECRET_KEY → JWT_SECRET/JWT_REFRESH_SECRET), and a no-op web type-check (tsc --noEmit → tsc -b; mobile + packages type-checks added; black --check added). README setup rewritten (.env creation, Celery, ML training).
In progress: Phase 1 re-verification.
Blocked: CI green on GitHub needs a push. Risk-questionnaire scoring thresholds need team sign-off (§4).
Decisions made: Ignore trained artifacts in git (regenerated by python -m ml.train); keep the CSV dataset committed.
Next session should: Push the branch, confirm CI is green, then start Phase 1 re-verification.

## 8. Team & Responsibilities

| Person                      | Role (suggested per Phases.md owner-splits)                                                                                                                               | Notes                                                         |
| --------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Muhammad Ali Khaliq         | ML/backend-leaning (adjust as work actually splits)                                                                                                                       | CGPA 3.08                                                     |
| Abdul Mannan Bhatti (Manam) | Frontend/full-stack-leaning; also runs Buildora (web agency) and freelances — brings existing React/Next.js/FastAPI/Claude-API experience directly relevant to this stack | CGPA 2.58                                                     |
| Mr. Zain-ul-Abideen         | Academic supervisor                                                                                                                                                       | Approves scope changes, evaluates progress at each phase gate |

> _Update instructions: as actual task ownership solidifies (vs. the suggested splits in Phases.md), record who actually owns which module here so the agent knows who to flag questions toward in commit/PR descriptions._

## 9. External Dependencies — Status Tracker

| Dependency               | Status                    | Notes                                                                 |
| ------------------------ | ------------------------- | --------------------------------------------------------------------- |
| Yahoo Finance API        | Not yet integrated        | Confirm rate limits before Phase 2                                    |
| PSX Data API / website   | Not yet integrated        | Official API access vs scraping — open question (§4)                  |
| Claude API               | Not yet integrated        | Needed for chatbot (Phase 8) — key budgeted per PRD.md §14 assumption |
| Firebase Cloud Messaging | Not yet integrated        | Needed for Phase 7 (notifications)                                    |
| Financial news sources   | Not yet selected          | Specific outlets TBD before Phase 4                                   |
| Twitter/X (Tweepy)       | Optional, not yet decided | Supplementary sentiment only — not a hard dependency                  |

> _Update instructions: flip each row to "Integrated ✅" with the date once working, or "Blocked ⚠️" with the reason if something's not accessible — this is the first place to check if a phase seems stuck on an external factor rather than internal work._

## 10. Model Performance Tracker

_(Fill in once Phase 3/4 training actually happens — this table becomes primary evidence for the FYP report and defense.)_

| Model                          | Version | Trained on | RMSE | Directional Accuracy | Notes                                           |
| ------------------------------ | ------- | ---------- | ---- | -------------------- | ----------------------------------------------- |
| LSTM/BiLSTM (price prediction) | v1.0    | AAPL (1y)  | 9.06 | ~65%                 | Target: RMSE < 5% (Met, price is ~330), acc > 80% (needs more data) |
| SVM (buy/sell/hold)            | —       | —          | —    | —                    | Skipped in favor of Random Forest baseline      |
| Random Forest (buy/sell/hold)  | v1.0    | AAPL (1y)  | —    | 40-60%               | Baseline prototype                              |
| FinBERT (sentiment)            | pre-trn | News       | —    | >85%                 | HuggingFace Pretrained, proven on financial text|

**Backtest results (once available):**

| Portfolio/strategy | Period tested | Total return | Sharpe ratio | Max drawdown | Win rate |
| ------------------ | ------------- | ------------ | ------------ | ------------ | -------- |
| —                  | —             | —            | —            | —            | —        |

## 11. Known Pitfalls / Gotchas (append as discovered — saves re-learning the same lesson twice)

- Time-series data must use chronological train/val/test splits, never random shuffling (Architecture.md §15.1) — a shuffled split will look great and be meaningless.
- PSX/news scraping is likely to hit rate limits under real use — build the Redis caching layer (Architecture.md §10) early, don't treat it as a later optimization.
- Floating-point math on fees/tax will produce off-by-a-paisa errors that look fine in testing and embarrassing in a live demo — `Decimal` is mandatory, not a nice-to-have (Rules.md §3.4).
- Urdu UI text tends to overflow components sized for English string lengths — see Design.md §24, test with real Urdu strings early, not lorem-ipsum placeholders.
- **Auth rate limiter fails open when Redis is down** (`core/rate_limit.py`): login/register keep working but are NOT rate-limited while Redis is unavailable. Deliberate for the FYP (availability over strictness); every skipped check logs a WARNING "Auth rate limit SKIPPED".
- **Auth rate limiter limits by direct client IP:** behind Railway's proxy all users may share one IP (one user's failed logins could lock everyone out), so `X-Forwarded-For` handling (trusting only the platform proxy) is needed at deployment. Not implemented yet.
- **Passwords are capped at 72 bytes** because bcrypt ignores everything after byte 72 (Urdu letters are 2 bytes each, so ~36 Urdu characters). The register screens need an en/ur message for the API's "Password is too long" 422.
- **Registration reveals whether an email is already registered** ("already exists", 400). Accepted known limitation (2026-10-09): standard sign-up behaviour, slowed by the register rate limit; hiding it would need an email-verification flow, which is out of PRD scope. Login does NOT leak this: same message and same bcrypt cost for unknown emails (dummy-hash check, `routers/auth.py`).
- **Web tokens live in `localStorage`** (`apps/web/src/lib/tokenStorage.ts`, keys `investiq.access_token` / `investiq.refresh_token`). XSS trade-off accepted for the FYP (2026-10-09): any script on the page could read them, and a stolen refresh token mints access tokens for up to 7 days. Mitigations: React escapes all rendered text, no `dangerouslySetInnerHTML`, 30-minute access tokens.
- **Phase 11 hardening backlog** (decided, not yet built): (1) move the refresh token to an `httpOnly`, `Secure`, `SameSite=Strict` cookie and keep the access token in memory only (needs CSRF protection on `/auth/refresh` and cookie-aware CORS; mobile keeps secure storage); (2) `X-Forwarded-For` handling for the auth rate limiter behind the hosting proxy.
- **Dev-only account:** `phase0.check@example.com` (role `admin`, local DB only) was created on 2026-10-09 for automated browser checks. It is for local testing only — never seed it into staging/production and never use or show it in a demo or the defense.
- A previous demo of this project existed and is _not_ the baseline — if any old code, screenshots, or decisions surface from that demo, verify against these docs before trusting them (§2).

> _Update instructions: every time something wastes more than an hour because a lesson wasn't written down, add it here._

## 12. Frequently Anticipated Panel/Defense Questions

_(Pre-loaded from the literature gap analysis and known limitations — useful context for anyone, human or AI, drafting defense materials or a report.)_

- **"Why not just use an existing tool like FolioSync?"** → FolioSync has no AI prediction, no sentiment analysis, no PSX-specific advisory (PRD.md §11 competitive table).
- **"How is this different from the academic papers you cited?"** → Every cited study is either not PSX-specific, not real-time, or has no user-facing product — InvestIQ is the first to combine all three for Pakistani retail investors (PRD.md §2.2).
- **"What happens if your prediction is wrong?"** → Predictions are always shown as probabilistic with a confidence score (PRD.md §7.3, FR14); the disclaimer (PRD.md §8.5) and backtesting module (§7.6) exist specifically to set honest expectations rather than overpromise.
- **"Is this giving real financial advice? Is that legal/safe?"** → Advisory-only, explicitly out-of-scope for trade execution (PRD.md §6.2); disclaimer language displayed throughout (§8.5).
- **"Why store login tokens in localStorage? Isn't that vulnerable to XSS?"** → It's a deliberate, documented trade-off: React escapes everything it renders and the app never uses `dangerouslySetInnerHTML`, so there is no known XSS path; access tokens expire after 30 minutes; passwords are never stored client-side. Moving the refresh token to an `httpOnly` cookie is a planned Phase 11 hardening step (Memory.md §11).
- **"How does the chatbot avoid making things up?"** → Grounding architecture — every response is built from real database records, never generated freeform (Architecture.md §12).

## 13. Quick Terminology Reference

_(Duplicate of PRD.md §16 glossary, kept here too since Memory.md is the first-read file — avoids a context-switch mid-session just to look up a term.)_

- **PSX** — Pakistan Stock Exchange
- **LSTM/BiLSTM** — deep learning models for time-series prediction
- **FinBERT** — transformer model pre-trained on financial text, used for sentiment
- **VADER** — lightweight rule-based sentiment fallback
- **CGT / WHT** — Capital Gains Tax / Withholding Tax
- **No Money Hold** — policy ensuring idle capital always gets a reallocation suggestion
- **Portfolio Rolling** — switching out underperforming holdings
- **Sharpe Ratio** — risk-adjusted return metric

## 14. Resource Links (fill in as they're set up)

| Resource                                   | Link |
| ------------------------------------------ | ---- |
| GitHub repo                                | —    |
| Deployed web app (staging)                 | —    |
| Deployed web app (production/demo)         | —    |
| Figma/design file (if used)                | —    |
| Shared drive (datasets, FYP report drafts) | —    |
| Model training notebooks                   | —    |

## 15. Dataset Tracker

_(Fill in as historical data is acquired — critical for both model training and the FYP report's methodology section.)_

| Dataset                                        | Source              | Date range covered | Companies/tickers included | Rows/size | Status           |
| ---------------------------------------------- | ------------------- | ------------------ | -------------------------- | --------- | ---------------- |
| PSX historical prices                          | Yahoo Finance / PSX | —                  | —                          | —         | Not yet acquired |
| PSX company fundamentals                       | —                   | —                  | —                          | —         | Not yet acquired |
| Financial news corpus (for sentiment)          | —                   | —                  | —                          | —         | Not yet acquired |
| KSE-100 index history (for backtest benchmark) | —                   | —                  | N/A                        | —         | Not yet acquired |

> _Update instructions: record exactly where each dataset came from and when it was pulled — PSX data providers change/rate-limit over time, and being able to say precisely what was used (for reproducibility and for answering panel questions) matters more than it seems early on._

## 16. Quick-Resume Checklist (for starting any new session)

1. Read Section 2 (Current Status) — what phase, what's in progress
2. Skim Section 3 (Decisions Log) — don't re-decide something already settled
3. Check Section 4 (Open Questions) — is today's task blocked on one of these?
4. Check Section 9 (External Dependencies) — is a needed integration still "Not yet integrated"?
5. Check Section 11 (Known Pitfalls) — avoid repeating a documented mistake
6. Cross-reference Phases.md for the active phase's task list and exit criteria
7. Do the work
8. Before finishing: update Section 2, append a Section 7 log entry, update any tracker (Section 9/10/15) that changed, add to Section 3 or 11 if a decision or a hard-won lesson happened this session

## 17. Session Log Entry Template

_(Copy this format for every new Section 7 entry — keeps the log scannable instead of freeform.)_

```
[YYYY-MM-DD] — <Phase name/number>
Completed: <what got finished this session>
In progress: <what's partway done>
Blocked: <anything waiting on a decision/dependency — reference §4 or §9>
Decisions made: <anything new for §3, or "none">
Next session should: <the single most useful next action>
```

## 18. Instructions for the AI Agent Reading This File

1. Read this file fully before starting any session's work.
2. Check Section 2 (Current Status) to know which phase is active — cross-reference with Phases.md for that phase's tasks and exit criteria.
3. Check Section 4 (Open Questions) — if the task at hand touches one of these, flag it rather than silently deciding.
4. Do the work, following PRD.md/Architecture.md/Rules.md/Design.md as applicable.
5. **Before ending the session, update Section 2 and append a Section 7 log entry** — future sessions (yours or a human's) depend on this being current. An out-of-date Memory.md is worse than no Memory.md, because it will be trusted.
6. If a decision was made during the session that isn't already in Section 3, add it there with brief reasoning.
