# Architecture — InvestIQ

### AI-Based Portfolio Management System for PSX Investors

**Companion doc to:** PRD.md
**Scope:** Web app + Mobile app, shared backend
**Status:** Fresh build, greenfield architecture

---

## 1. Architecture Philosophy

One backend, multiple clients. The web app and mobile app are both thin clients over a single FastAPI backend and a single set of AI/ML services. No business logic, prediction logic, or fee/tax calculation should ever live in the frontend or mobile app — those are display layers only. This keeps the ML pipeline, portfolio logic, and cost engine as a single source of truth, which also matters for the FYP defense (one demonstrable, coherent system, not two divergent implementations).

## 2. High-Level System Architecture (5-Tier)

```
┌─────────────────────────────────────────────────────────────────┐
│ TIER 1 — Presentation Layer                                     │
│ React.js (Web) │ React Native (Mobile) │ LLM Chatbot UI │ Push  │
└───────────────────────────────┬───────────────────────────────────┘
                                 │ REST/HTTPS (JSON) + WebSocket (chat)
┌───────────────────────────────▼───────────────────────────────────┐
│ TIER 2 — Application Layer (FastAPI)                             │
│ Auth & Users │ Portfolio Mgr │ Notification Agent │ Backtest API │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│ TIER 3 — AI & ML Layer                                           │
│ LSTM/BiLSTM Engine │ SVM/RF Signals │ FinBERT Sentiment │ LLM    │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│ TIER 4 — Data Layer                                               │
│ PostgreSQL/MySQL (primary DB) │ Redis (cache + job queue)        │
└───────────────────────────────┬───────────────────────────────────┘
                                 │
┌───────────────────────────────▼───────────────────────────────────┐
│ TIER 5 — External Services                                        │
│ Yahoo Finance API │ PSX Data Source │ News Scrapers │ Claude API │
│ Firebase Cloud Messaging (push notifications)                     │
└─────────────────────────────────────────────────────────────────┘
```

## 3. Tech Stack (final)

| Layer                    | Technology                                                                                                                                                                                        | Notes                                                                                                                                   |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| Web Frontend             | React.js + Vite, Tailwind CSS                                                                                                                                                                     | Matches Manam's existing core stack                                                                                                     |
| Mobile App               | **React Native** (Expo)                                                                                                                                                                           | Chosen over Flutter — team already works in React/JS; enables shared TypeScript types/utils between web and mobile via a shared package |
| Backend                  | Python, FastAPI                                                                                                                                                                                   | Async-first, auto-generates OpenAPI docs (useful for Antigravity AI to reference the API contract directly)                             |
| AI/ML                    | TensorFlow or PyTorch (LSTM/BiLSTM), Scikit-learn (SVM, Random Forest), HuggingFace Transformers (FinBERT)                                                                                        | Served via a dedicated internal ML service                                                                                              |
| NLP fallback             | VADER (via `nltk`/`vaderSentiment`)                                                                                                                                                               | Lightweight fallback when FinBERT confidence is low                                                                                     |
| LLM Chatbot              | Claude API (primary)                                                                                                                                                                              | Bilingual EN/UR conversational layer, grounded via RAG-style context injection (user's live data)                                       |
| Database                 | PostgreSQL (recommended) or MySQL                                                                                                                                                                 | Relational — the domain (users, portfolios, predictions) is inherently relational                                                       |
| Cache / Queue            | Redis                                                                                                                                                                                             | Response caching + Celery broker                                                                                                        |
| Background Jobs          | Celery + Redis                                                                                                                                                                                    | Market monitoring agent, model retraining jobs, notification dispatch                                                                   |
| Notifications            | Firebase Cloud Messaging (FCM)                                                                                                                                                                    | Cross-platform push (web + mobile)                                                                                                      |
| Technical Indicators     | TA-Lib                                                                                                                                                                                            | RSI, MACD, Bollinger Bands, Moving Averages                                                                                             |
| Backtesting              | Backtrader or QuantStats                                                                                                                                                                          | Historical strategy simulation                                                                                                          |
| Data Sources             | Yahoo Finance API, PSX Data API/website                                                                                                                                                           | Price + fundamentals                                                                                                                    |
| News/Sentiment Ingestion | Custom scrapers (`requests`/`BeautifulSoup` or `Scrapy`), optional Tweepy for Twitter/X                                                                                                           | Feeds FinBERT pipeline                                                                                                                  |
| Auth                     | JWT (access + refresh tokens), bcrypt/argon2 password hashing                                                                                                                                     | Stateless auth across web + mobile                                                                                                      |
| Deployment               | Backend: Railway or AWS/GCP; Web: Vercel; Mobile: Expo EAS Build                                                                                                                                  | Matches Manam's existing deployment patterns (Vercel + Railway)                                                                         |
| Version Control          | Git / GitHub, monorepo                                                                                                                                                                            | See Section 5                                                                                                                           |
| Web libraries (as built) | TanStack Query, React Router, axios (in `packages/api-client`), react-hook-form + zod (`@hookform/resolvers`), lucide-react (icons), recharts (charts), i18next + react-i18next (`packages/i18n`) | Forms validate client-side with zod; the server re-validates everything with Pydantic                                                   |
| Urdu font                | Noto Naskh Arabic, self-hosted in `apps/web/public/fonts/` (SIL Open Font License)                                                                                                                | No Nastaliq (Design §3 readability); self-hosted so the demo works offline                                                              |

## 4. Why React Native over Flutter (decision rationale)

- Team's core stack is already React/JavaScript/TypeScript (web, Node.js) — no new language (Dart) to learn under FYP time pressure
- Enables a shared `packages/shared` workspace (types, API client, validation schemas, i18n strings) reused by both web and mobile
- Expo simplifies build/deploy for a two-person team without dedicated native mobile experience
- _(If a supervisor/panel specifically prefers Flutter for the defense, this is the one architectural decision easiest to swap — noted as a risk-flagged assumption, not a hard dependency of the rest of the system.)_

## 5. Repository Structure (Monorepo)

```
investiq/
├── apps/
│   ├── web/                  # React + Vite web app
│   ├── mobile/                # React Native (Expo) app
│   └── admin/                 # (optional) separate admin panel, or a route within web/
├── services/
│   ├── api/                   # FastAPI backend — auth, users, portfolio, backtest, notifications
│   │   ├── ml/                 # ML code lives HERE (internal module, §6.5): features, training, inference, sentiment
│   │   ├── integrations/       # market data + news scraper clients
│   │   └── worker/             # Celery tasks
│   ├── ml-engine/              # placeholder README → code is in services/api/ml/ (§6.5)
│   ├── sentiment-engine/       # placeholder README → runs inside services/api (§6.5), Phase 4
│   └── chatbot-service/        # placeholder README → runs inside services/api (§6.5), Phase 8
├── packages/
│   ├── shared-types/           # TypeScript types shared by web + mobile
│   ├── api-client/             # Typed API client (generated from FastAPI OpenAPI schema)
│   ├── i18n/                   # English/Urdu translation strings
│   └── design-tokens/          # Shared design tokens (Design.md §20)
├── infra/
│   ├── docker-compose.yml      # Local dev: Postgres, Redis, API, ML services
│   └── deploy/                 # Deployment configs (Railway/AWS, Vercel, EAS)
├── docs/                       # PRD.md, Architecture.md, Rules.md, Phases.md, Design.md, Memory.md
└── README.md
```

**Code location (decided 2026-10-09):** per §6.5, the ML, sentiment and chatbot code runs as internal Python modules of `services/api` (ML is in `services/api/ml/`). The `services/ml-engine`, `services/sentiment-engine` and `services/chatbot-service` folders hold only pointer READMEs until/unless they are split into real services.

**Rationale:** a monorepo keeps the FastAPI OpenAPI contract, the shared types, and both frontends in sync — critical when one person is likely doing more backend/ML and the other more frontend/mobile, and both need to move without breaking each other's work.

## 6. Backend Service Breakdown

### 6.1 `services/api` (FastAPI — core application layer)

Responsible for: auth, user/risk-profile CRUD, portfolio generation orchestration, backtest requests, notification preferences, admin endpoints. Calls into `ml-engine`, `sentiment-engine`, and `chatbot-service` as internal service calls (or, for FYP simplicity, as importable Python modules within the same deployment — see Section 6.5).

### 6.2 `services/ml-engine`

- Training pipeline: ingest historical PSX data → feature engineering (TA-Lib indicators) → train LSTM/BiLSTM → evaluate (RMSE, directional accuracy) → save model artifact
- Inference pipeline: load latest trained model → given a stock, return forecast + confidence score
- SVM/Random Forest: buy/sell/hold classifiers trained on the same feature set

### 6.3 `services/sentiment-engine`

- Scraper jobs (scheduled via Celery) pull financial news per PSX-listed company
- FinBERT inference scores each article; VADER as fallback
- Aggregated sentiment score per stock, refreshed on a schedule (e.g., every few hours)

### 6.4 `services/chatbot-service`

- Receives user message + language
- Builds a grounded context payload: user's risk profile, current portfolio, latest predictions/sentiment for relevant stocks
- Calls Claude API with that context + system prompt enforcing: PSX-only scope, jargon-free explanation, bilingual capability, mandatory uncertainty disclosure
- Returns response to `services/api`, which relays it to the client

### 6.5 Deployment simplification note (FYP-scale)

For a two-person FYP team, running 4 separate microservices in production is unnecessary overhead. Recommended approach: **one FastAPI deployment** with `ml-engine`, `sentiment-engine`, and `chatbot-service` as internal Python packages/modules (not separate network services) for now. The folder separation above still applies — it keeps code organized and would allow splitting into real microservices later without a rewrite, but Phase 1–3 should NOT deploy them separately. Heavy/slow jobs (training, scraping, notification checks) go through Celery background workers, not the request/response cycle.

## 7. Database Schema (initial draft)

```sql
users
  id UUID PK
  email VARCHAR UNIQUE                       -- stored trimmed + lowercase; unique index on lower(email)
  password_hash VARCHAR
  full_name VARCHAR
  role ENUM('user','admin') DEFAULT 'user'   -- added early (planned for Step 9.1): admin route guard needs it
  onboarding_progress JSONB NULL             -- partial questionnaire answers + step, for resume (PRD FR6)
  created_at TIMESTAMPTZ

risk_profiles
  id UUID PK
  user_id UUID FK -> users.id ON DELETE CASCADE
  category ENUM('conservative','moderate','aggressive')
  answers JSONB
  updated_at TIMESTAMPTZ

refresh_tokens                               -- one row per issued refresh token (rotation + revocation)
  jti UUID PK                                -- the JWT's jti claim
  user_id UUID FK -> users.id ON DELETE CASCADE
  expires_at TIMESTAMPTZ
  revoked_at TIMESTAMPTZ NULL                -- set on use (rotation), logout, or reuse detection

stocks
  id UUID PK
  ticker VARCHAR UNIQUE
  name VARCHAR
  sector VARCHAR

price_points
  id BIGSERIAL PK
  stock_id UUID FK -> stocks.id
  timestamp TIMESTAMPTZ
  open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC, volume BIGINT

predictions
  id UUID PK
  stock_id UUID FK -> stocks.id
  model_version VARCHAR
  forecast_price NUMERIC
  confidence_score NUMERIC
  generated_at TIMESTAMPTZ

sentiment_scores
  id UUID PK
  stock_id UUID FK -> stocks.id
  source VARCHAR
  score NUMERIC
  label ENUM('positive','negative','neutral')
  headline TEXT
  timestamp TIMESTAMP

portfolios
  id UUID PK
  user_id UUID FK -> users.id
  status ENUM('active','archived')
  generated_at TIMESTAMP

portfolio_holdings
  id UUID PK
  portfolio_id UUID FK -> portfolios.id
  stock_id UUID FK -> stocks.id
  allocation_pct NUMERIC
  gross_price NUMERIC
  brokerage_fee NUMERIC
  cgt NUMERIC
  wht NUMERIC
  net_price NUMERIC

backtest_results
  id UUID PK
  portfolio_id UUID FK -> portfolios.id
  period_start DATE, period_end DATE
  total_return NUMERIC
  sharpe_ratio NUMERIC
  max_drawdown NUMERIC
  win_rate NUMERIC

notifications
  id UUID PK
  user_id UUID FK -> users.id
  type ENUM('buy','sell','roll')
  reasoning TEXT
  sent_at TIMESTAMP
  read BOOLEAN DEFAULT FALSE

chat_messages
  id UUID PK
  user_id UUID FK -> users.id
  role ENUM('user','assistant')
  content TEXT
  language ENUM('en','ur')
  created_at TIMESTAMP

admin_action_logs
  id UUID PK
  admin_id UUID FK -> users.id
  action VARCHAR
  target VARCHAR
  created_at TIMESTAMP
```

## 8. API Surface (representative, not exhaustive)

```
POST   /auth/register
POST   /auth/login
POST   /auth/refresh                    # rotates: the old refresh token is revoked, a new pair is returned
POST   /auth/logout                     # revokes the given refresh token (always 204)

GET    /users/me
GET    /users/risk-questionnaire        # public: question ids + option values only (scoring stays server-side)
GET    /users/me/risk-profile
PATCH  /users/me/risk-profile           # create or retake (FR5); returns category, score, caps_applied
GET    /users/me/onboarding-progress    # partial answers + step, for resume (FR6)
PUT    /users/me/onboarding-progress

GET    /stocks/search?q=
GET    /stocks/{ticker}
GET    /stocks/{ticker}/history
GET    /stocks/{ticker}/prediction
GET    /stocks/{ticker}/sentiment

POST   /portfolio/generate
GET    /portfolio/current
POST   /portfolio/{id}/roll-check
PATCH  /portfolio/{id}/exclude-stock

POST   /backtest/run
GET    /backtest/{id}

GET    /notifications
PATCH  /notifications/preferences

POST   /chat/message           # returns chatbot response
GET    /chat/history

# Admin (role-protected)
GET    /admin/users
PATCH  /admin/users/{id}/suspend
GET    /admin/system-health
POST   /admin/models/retrain
GET    /admin/news-sources
POST   /admin/news-sources
```

All endpoints documented automatically via FastAPI's built-in OpenAPI/Swagger — this becomes the contract `packages/api-client` is generated from.

## 9. Background Jobs (Celery + Redis)

| Job                     | Trigger                                            | Purpose                                                                  |
| ----------------------- | -------------------------------------------------- | ------------------------------------------------------------------------ |
| `refresh_stock_prices`  | Scheduled (e.g., every 15 min during market hours) | Pull latest PSX prices into `price_points`                               |
| `scrape_news_sentiment` | Scheduled (e.g., every few hours)                  | Pull news, run FinBERT/VADER, write `sentiment_scores`                   |
| `run_predictions`       | Scheduled (e.g., daily) or on-demand               | Run LSTM/SVM/RF inference, write `predictions`                           |
| `retrain_models`        | Scheduled (e.g., weekly) or admin-triggered        | Retrain LSTM/SVM/RF on latest data                                       |
| `monitor_portfolios`    | Scheduled (e.g., every few min)                    | Check active portfolios against fresh predictions, trigger notifications |
| `send_notification`     | Triggered by `monitor_portfolios`                  | Dispatch via FCM, target latency < 5s                                    |

## 10. Caching Strategy (Redis)

- Cache Yahoo Finance/PSX API responses (short TTL, e.g., 5–15 min) to stay under rate limits and hit the < 2s API response target
- Cache latest prediction + sentiment per stock (invalidated on `run_predictions`/`scrape_news_sentiment` completion)
- Celery uses Redis as its message broker/result backend

## 11. Security Architecture

- JWT access tokens (short-lived) + refresh tokens (longer-lived, stored securely on client)
- Refresh tokens are single-use and recorded in Postgres (`refresh_tokens`, never Redis, so revocation can't fail open): each refresh revokes the old token; presenting a revoked token again revokes all of that user's refresh tokens (reuse detection); `/auth/logout` revokes the current one
- Outside `ENVIRONMENT=development` the API refuses to start with placeholder JWT secrets or secrets shorter than 32 characters; `/docs`, `/redoc` and `/openapi.json` are served only in development
- Passwords hashed with bcrypt/argon2, never logged
- Role-based access control: `user` vs `admin` roles enforced at the API layer (FastAPI dependency injection)
- Input validation via Pydantic models on every endpoint
- Rate limiting on auth endpoints (prevent brute force)
- CORS locked to known frontend origins (web + mobile app schemes)
- Secrets (API keys: Claude, Firebase, DB credentials) via environment variables / `.env`, never committed — see Rules.md

## 12. Chatbot Grounding Architecture (detail)

To avoid hallucinated financial advice (a named risk in PRD.md), the chatbot service follows this pattern for every message:

1. Fetch user's current risk profile, active portfolio, and latest predictions/sentiment for any stock mentioned or in-portfolio
2. Construct a system + context prompt: system rules (PSX-only scope, jargon-free, bilingual, must disclose uncertainty) + the fetched real data as structured context
3. Send to Claude API
4. Response is returned as-is to the user, logged to `chat_messages`

No portfolio or price figures are ever generated freeform by the LLM — they're always injected from the database as ground truth; the LLM's job is explanation/translation, not computation.

## 13. Deployment Architecture

| Component                    | Platform                                                                         |
| ---------------------------- | -------------------------------------------------------------------------------- |
| Web app                      | Vercel                                                                           |
| Backend API + Celery workers | Railway (or AWS/GCP if free-tier/student credits available)                      |
| Database                     | Railway Postgres, or managed Postgres/MySQL                                      |
| Redis                        | Railway Redis add-on                                                             |
| Mobile app                   | Expo EAS Build → APK for Android testing/demo; TestFlight only if iOS is pursued |
| ML model artifacts           | Stored alongside backend (or object storage — S3/GCS — if size becomes an issue) |

## 14. Scalability Notes (for defense credibility, not required at FYP scale)

- Stateless FastAPI instances behind a load balancer would allow horizontal scaling
- ML inference could be split into its own service with a task queue if load increased
- Read replicas for Postgres if query load grows
- These are explicitly **not required for the FYP submission** — noted here so the architecture doesn't paint itself into a corner, and to have a credible answer if a panel member asks "how would this scale."

## 15. ML Model Architecture (detail)

### 15.1 LSTM/BiLSTM Prediction Model

- **Input:** sequence window of past N days (e.g., 60 trading days) of OHLCV data + technical indicators (RSI, MACD, Bollinger Bands, Moving Averages) + sentiment score for that day
- **Architecture (starting point):** 2 stacked LSTM/BiLSTM layers (e.g., 64 → 32 units) → Dropout (0.2) → Dense output layer predicting next N-day price/return
- **Loss/metric:** MSE for training; RMSE and directional accuracy reported for evaluation (per PRD targets: RMSE < 5%, directional accuracy > 80%)
- **Output:** predicted price/return + a confidence score derived from prediction variance or an auxiliary classifier's probability
- **Training data split:** chronological train/validation/test split (never randomly shuffled — this is time-series data, shuffling would leak future information into training)

### 15.2 SVM / Random Forest (buy/sell/hold classifier)

- Same engineered feature set as LSTM, framed as classification instead of regression
- Output: buy / sell / hold label + probability, used as a secondary signal alongside the LSTM forecast
- Random Forest additionally provides feature importance — useful in the chatbot's "what's driving this" explanations and in the FYP defense

### 15.3 FinBERT Sentiment Pipeline

- Pre-trained FinBERT (HuggingFace `ProsusAI/finbert` or equivalent) run on scraped headlines/article text
- Output: positive/negative/neutral label + confidence
- VADER fallback triggers when FinBERT confidence < defined threshold or input text is very short (e.g., tweet-length)
- Sentiment scores aggregated (e.g., time-decayed average) per stock per day, merged as an LSTM input feature

### 15.4 Model Versioning

- Every trained model artifact tagged with a `model_version` (timestamp or semantic version)
- `predictions` table stores which `model_version` generated each forecast — enables comparing model performance over time and rolling back if a retrain underperforms

## 16. Frontend Architecture (Web + Mobile)

- **State management:** React Query (TanStack Query) for server state (predictions, portfolio, stock data) — avoids manual cache invalidation bugs; lightweight local state (React Context or Zustand) for UI-only state (theme, language toggle, onboarding step)
- **Routing:** React Router (web), React Navigation (mobile)
- **Shared logic:** API calls, validation schemas, and TypeScript types live in `packages/api-client` and `packages/shared-types`, imported by both `apps/web` and `apps/mobile` — a change to the API contract only needs updating in one place
- **i18n:** `packages/i18n` holds English/Urdu strings; both apps use the same translation keys so the chatbot and UI never drift out of sync in phrasing
- **Offline/error handling (mobile):** cached last-known portfolio/prediction data shown with a "stale data" indicator if the device is offline; no silent failures — a failed fetch always shows a retry state, never a blank screen

## 17. Environment Configuration & Secrets

All secrets loaded from environment variables, never hardcoded or committed (enforced in Rules.md). Baseline `.env` variables each environment needs:

```
DATABASE_URL=
REDIS_URL=
JWT_SECRET=
JWT_REFRESH_SECRET=
CLAUDE_API_KEY=
FIREBASE_SERVICE_ACCOUNT_JSON=
YAHOO_FINANCE_API_KEY=        # if applicable
PSX_DATA_SOURCE_URL=
NEWS_SCRAPER_SOURCES=          # comma-separated list of configured sources
ENVIRONMENT=development|staging|production
```

Separate `.env` files (or platform secret managers — Railway/Vercel env vars) per environment. `.env.example` committed to the repo with placeholder values so Antigravity AI (or any teammate) knows exactly what to configure without ever seeing real secrets.

## 18. Logging & Monitoring

- Structured logging (JSON logs) from the FastAPI backend — request id, endpoint, latency, status code
- Celery job logs: job name, duration, success/failure, retry count
- Admin panel's "system health" view (FR43 in PRD.md) reads from: last successful price refresh timestamp, last successful sentiment scrape timestamp, last model retrain timestamp, and current API error rate
- No sensitive data (passwords, tokens, full financial details) ever written to logs

## 19. Testing Strategy (high-level)

| Layer             | Approach                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend (FastAPI) | Pytest — unit tests for portfolio/fee-tax calculation logic (these must be exact, not approximate), integration tests for key endpoints. Tests never touch the dev DB: `pytest` creates and migrates a separate `<db>_test` database and rolls every test back. A backend test also checks that every questionnaire id/option, safety cap and risk category the API returns has an English and an Urdu label                                                                                                        |
| ML models         | Offline evaluation notebooks/scripts reporting RMSE, directional accuracy, Sharpe ratio against held-out test data before any model is promoted to "active"                                                                                                                                                                                                                                                                                                                                                         |
| Frontend (web)    | Node's built-in test runner (`node --test`, no extra dependency) for logic kept in pure modules: route-guard rules, date/number formatting, ordered draft saves (`apps/web`), and the token-refresh coordinator (`packages/api-client`). `en`/`ur` key parity is checked in CI. There are no React component tests; screens are covered by the Playwright smoke tests and the manual walkthrough                                                                                                                    |
| Mobile            | Manual QA on Android emulator/device each phase; automated testing is a stretch goal given FYP time constraints                                                                                                                                                                                                                                                                                                                                                                                                     |
| End-to-end        | Playwright (Chromium only) smoke tests in `apps/web/e2e`, run locally with `npm run e2e` (not in CI yet): the Phase 1 flow (register → partial onboarding → reload and resume → finish → dashboard → logout → login) and an Urdu right-to-left run. The run starts its own API on the `<db>_test` database and its own web server, and deletes every account it created. Plus at least one manual full-flow walkthrough (register → prediction → portfolio → backtest → chat → notification) before each phase demo |

## 20. CI/CD (lightweight, FYP-appropriate)

- GitHub Actions: on every push/PR — run backend Pytest suite + frontend lint/type-check
- No auto-deploy required for FYP; manual deploy to Vercel/Railway once a phase is stable and demo-ready
- Branch strategy: `main` (always demoable), feature branches per module (e.g., `feature/risk-profiling`, `feature/lstm-pipeline`) — see Rules.md for full Git conventions

## 21. Open Architectural Decisions

- Final choice of Postgres vs MySQL — Postgres recommended (better JSONB support for `risk_profiles.answers`), confirm with team before Phase 1 setup
- Object storage for ML model artifacts — only needed if models grow large; start with local/filesystem storage in Phase 1
- Whether `admin` is a separate app or a protected route set within the web app — recommend a protected route set within `apps/web` for FYP simplicity, split out only if genuinely needed
- Exact LSTM hyperparameters (layers, units, window size) — starting point given in Section 15.1, to be tuned empirically once real PSX data is in hand
