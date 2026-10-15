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
                                 │ REST/HTTPS (JSON); chat is plain REST too (§12)
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

| Layer                    | Technology                                                                                                                                                                                                                                                                                                                 | Notes                                                                                                                                                                                                                                                                      |
| ------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Web Frontend             | React.js + Vite, Tailwind CSS                                                                                                                                                                                                                                                                                              | Matches Manam's existing core stack                                                                                                                                                                                                                                        |
| Mobile App               | **React Native** (Expo)                                                                                                                                                                                                                                                                                                    | Chosen over Flutter — team already works in React/JS; enables shared TypeScript types/utils between web and mobile via a shared package                                                                                                                                    |
| Backend                  | Python, FastAPI                                                                                                                                                                                                                                                                                                            | Async-first, auto-generates OpenAPI docs (useful for Antigravity AI to reference the API contract directly)                                                                                                                                                                |
| AI/ML                    | TensorFlow or PyTorch (LSTM/BiLSTM), Scikit-learn (SVM, Random Forest), HuggingFace Transformers (FinBERT)                                                                                                                                                                                                                 | Served via a dedicated internal ML service                                                                                                                                                                                                                                 |
| NLP fallback             | VADER (via `nltk`/`vaderSentiment`)                                                                                                                                                                                                                                                                                        | Lightweight fallback when FinBERT confidence is low                                                                                                                                                                                                                        |
| LLM Chatbot              | Provider set in configuration only (`LLM_PROVIDER`, `LLM_MODEL`, key): **Google Gemini free tier (primary) or Groq free tier (backup)**, whichever wins the Phase 8 bake-off; Mistral and Claude API adapters kept as config switches (deviation, 2026-10-13)                                                              | Bilingual EN/UR (and Roman Urdu) layer grounded in the user's own data (§12); every provider called over plain HTTPS with `httpx`, no SDK                                                                                                                                  |
| Database                 | PostgreSQL (recommended) or MySQL                                                                                                                                                                                                                                                                                          | Relational — the domain (users, portfolios, predictions) is inherently relational                                                                                                                                                                                          |
| Cache / Queue            | Redis                                                                                                                                                                                                                                                                                                                      | Response caching + Celery broker                                                                                                                                                                                                                                           |
| Background Jobs          | Celery + Redis                                                                                                                                                                                                                                                                                                             | Market monitoring agent, model retraining jobs, notification dispatch                                                                                                                                                                                                      |
| Notifications            | Firebase Cloud Messaging (FCM)                                                                                                                                                                                                                                                                                             | Cross-platform push (web + mobile)                                                                                                                                                                                                                                         |
| Technical Indicators     | Hand-written in pandas (`services/api/ml/features.py`) with TA-Lib's exact definitions; **TA-Lib is not a dependency** (decided 2026-10-10)                                                                                                                                                                                | RSI, MACD, Bollinger Bands, SMA. Verified against TA-Lib 0.8.1 reference values and the published Wilder RSI example (`tests/test_indicators.py`); TA-Lib's native C build is painful on Windows and CI. One deliberate difference: RSI of a flat window is 50 (TA-Lib: 0) |
| Backtesting              | Own Decimal engine and metrics (`services/backtest.py`, `services/backtest_metrics.py`); QuantStats as a test-only cross-check (decided 2026-10-12)                                                                                                                                                                        | Buy-and-hold simulation; every charge from the Phase 5 cost engine. Backtrader not used: last release 19 Apr 2023 and a float commission model that would duplicate the cost engine                                                                                        |
| Data Sources             | Yahoo Finance API, PSX Data API/website                                                                                                                                                                                                                                                                                    | Price + fundamentals                                                                                                                                                                                                                                                       |
| News/Sentiment Ingestion | Custom scrapers (`requests`/`BeautifulSoup` or `Scrapy`), optional Tweepy for Twitter/X                                                                                                                                                                                                                                    | Feeds FinBERT pipeline. As built: `requests` + `BeautifulSoup`/`lxml` over sitemaps, RSS and Mettis's JSON feed (no Scrapy, no Tweepy); `vaderSentiment==3.3.2` for the fallback                                                                                           |
| Auth                     | JWT (access + refresh tokens), bcrypt/argon2 password hashing                                                                                                                                                                                                                                                              | Stateless auth across web + mobile                                                                                                                                                                                                                                         |
| Deployment               | Backend: Railway or AWS/GCP; Web: Vercel; Mobile: Expo EAS Build                                                                                                                                                                                                                                                           | Matches Manam's existing deployment patterns (Vercel + Railway)                                                                                                                                                                                                            |
| Version Control          | Git / GitHub, monorepo                                                                                                                                                                                                                                                                                                     | See Section 5                                                                                                                                                                                                                                                              |
| Web libraries (as built) | TanStack Query, React Router, axios (in `packages/api-client`), react-hook-form + zod (`@hookform/resolvers`), lucide-react (icons), recharts (charts), i18next + react-i18next (`packages/i18n`)                                                                                                                          | Forms validate client-side with zod; the server re-validates everything with Pydantic                                                                                                                                                                                      |
| Urdu font                | Nastaleeq (decided 2026-10-13): Jameel Noori Nastaleeq if installed locally (not shipped), else Noto Nastaliq Urdu from `@fontsource/noto-nastaliq-urdu` 5.3.0 (SIL OFL 1.1, weights 400 and 700, self-hosted by the build); Noto Naskh Arabic (`apps/web/public/fonts/`, OFL) as fallback and for the text inside selects | Design §3; self-hosted so the demo works offline; Urdu line height 2.0                                                                                                                                                                                                     |
| Design tokens            | `packages/design-tokens` (Indus Night, decided 2026-10-15): colours for a dark default and a light theme, spacing, type scale, elevation, motion; inlined as `--iq-*` CSS variables by `apps/web/vite.config.ts` and mapped to Tailwind classes in `apps/web/src/index.css` (Tailwind's stock palette is off)              | Design.md §2, §20; AA contrast tested in `colors.test.ts`; theme toggle in the web header                                                                                                                                                                                  |
| 3D (landing page only)   | `three` 0.186.1 (MIT), with `@types/three` 0.186.0 (dev); plain three.js, no react-three-fiber (decided 2026-10-15)                                                                                                                                                                                                        | Lazy chunk (132.7 KB gzip) fetched after the landing page's first paint; never on app screens                                                                                                                                                                              |
| Display font (landing)   | Bricolage Grotesque from `@fontsource-variable/bricolage-grotesque` 5.3.0 (SIL OFL 1.1), Latin only, 40 KB woff2                                                                                                                                                                                                           | Landing page and auth panel headings only; Urdu falls through to Nastaleeq                                                                                                                                                                                                 |

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

> **As built (Phase 8, 2026-10-13):** the chatbot runs inside `services/api` (§6.5): `services/chat_context.py` (grounding context), `services/chat_figure_check.py` (every number in a reply checked against the context), `services/chat_language.py` (Roman Urdu detection), `services/chat_prompt.py` (system prompt `prompt-v1`), `services/chat_service.py` (one turn: limits, memory, regeneration, storage) and `integrations/llm/` (provider adapters). **Deviation:** the provider is Google Gemini's free tier (primary) or Groq's free tier (backup), whichever wins the bake-off (`docs/chat-eval/`), not the Claude API, while the project has no paid key. Adapters: `gemini.py` (`models.generateContent`; Gemini 3 thinking tokens count against `maxOutputTokens`, so a fixed 2,048-token thinking allowance is added to the 700-token reply budget), `groq.py` and `mistral.py` (shared OpenAI-style `openai_compat.py`), `claude.py` (Messages API). Switching is a `.env` change only (`LLM_PROVIDER`, `LLM_MODEL`, the provider's key). The Mistral free tier was planned first (2026-10-13) and dropped the same day because it was no longer available to the team. Only test accounts are used while on free tiers (Memory.md §4).

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

stocks                                       -- seeded from a versioned KSE-100 snapshot file
  id UUID PK
  ticker VARCHAR UNIQUE
  name VARCHAR
  sector VARCHAR
  shares_outstanding BIGINT NULL             -- market cap = latest close x shares (P/E not stored)

price_points
  id BIGSERIAL PK
  stock_id UUID FK -> stocks.id
  timestamp TIMESTAMPTZ
  open NUMERIC, high NUMERIC, low NUMERIC, close NUMERIC, volume BIGINT   -- raw provider values
  split_factor NUMERIC DEFAULT 1             -- served price = raw / factor, volume x factor
  quality_flag VARCHAR NULL                  -- 'no_trades' / 'mixed_split_level': not served
  adjustment_version VARCHAR NULL            -- e.g. 'split-v1'

stock_splits                                 -- provider split events + adjustment decision
  id BIGSERIAL PK
  stock_id UUID FK -> stocks.id
  split_date DATE, ratio NUMERIC
  history_adjusted BOOLEAN NULL, decision_note VARCHAR NULL, method_version VARCHAR NULL

stock_dividends                              -- provider dividend events + div-v1 decision
  id BIGSERIAL PK
  stock_id UUID FK -> stocks.id
  ex_date DATE, amount NUMERIC, source VARCHAR
  previous_close NUMERIC NULL, ex_close NUMERIC NULL
  adjustment_factor NUMERIC NULL             -- NULL = not applied (review_flag says why)
  review_flag VARCHAR NULL, method_version VARCHAR NULL

predictions
  id UUID PK
  stock_id UUID FK -> stocks.id
  model_version VARCHAR
  forecast_price NUMERIC, last_close NUMERIC
  confidence_score NUMERIC                   -- calibrated chance the LSTM direction is right
  signal VARCHAR, signal_probability NUMERIC NULL   -- Random Forest BUY/SELL/HOLD
  as_of_date DATE NULL                       -- trading date of the close it starts from
  sentiment_status VARCHAR NULL              -- 'used' / 'unavailable' (news stale, FR22) / NULL
  generated_at TIMESTAMPTZ

sentiment_scores                             -- one headline matched to one stock (Phase 4)
  id UUID PK
  stock_id UUID FK -> stocks.id
  source VARCHAR                             -- 'profit' / 'mettis' / 'brecorder'
  url VARCHAR                                -- UNIQUE (stock_id, url)
  headline TEXT                              -- the headline only; article text is never stored
  published_at TIMESTAMPTZ, fetched_at TIMESTAMPTZ
  score NUMERIC NULL                         -- P(pos) - P(neg), or VADER compound; NULL = unscored
  label VARCHAR NULL                         -- CHECK positive / negative / neutral
  scorer VARCHAR NULL                        -- CHECK finbert / vader
  scorer_version VARCHAR NULL, finbert_confidence NUMERIC NULL

news_source_status                           -- last attempt / success per source (FR22, §18)
  source VARCHAR PK
  last_attempt_at TIMESTAMPTZ NULL, last_success_at TIMESTAMPTZ NULL
  last_error TEXT NULL, last_new_headlines INT NULL

portfolios                                   -- Phase 5 (as built 2026-10-11; replaces the draft, see note below)
  id UUID PK
  user_id UUID FK -> users.id ON DELETE CASCADE
  status VARCHAR CHECK ('active','archived')   -- partial unique index: one active per user
  generated_at TIMESTAMPTZ
  risk_category VARCHAR                        -- the profile used
  capital NUMERIC(16,2)
  filer_status VARCHAR CHECK ('filer','non_filer')
  shariah_only BOOLEAN, shariah_list_version VARCHAR NULL
  excluded_tickers JSONB
  commission_rate NUMERIC(6,5)                 -- PSX floor unless the user entered their broker's rate
  rates_version VARCHAR                        -- integrations/data/psx_costs_*.json
  model_version VARCHAR, prices_as_of DATE
  input_snapshot JSONB                         -- per-stock volatility, forecast, signal, news, tilt, rank, reason
  gross_total, charges_total, cost_total, idle_cash NUMERIC(16,2)

portfolio_holdings
  id UUID PK
  portfolio_id UUID FK -> portfolios.id ON DELETE CASCADE
  stock_id UUID FK -> stocks.id
  prediction_id UUID FK -> predictions.id NULL -- the forecast the generator used
  position INT, shares INT
  reference_price NUMERIC(14,2)
  target_weight, allocation_pct NUMERIC(7,4)   -- percent
  gross_value, commission, sales_tax, cdc_fee, psx_trading_fee, psx_regulatory_fee,
  secp_levy, nccpl_trade_fee, nccpl_secp_fee, buy_charges, total_cost NUMERIC(16,2)
  projection JSONB                             -- break-even, one-day forecast exit (CGT), dividends (WHT): estimates

backtest_results                             -- Phase 6 (as built 2026-10-12; extends the draft, see note below)
  id UUID PK
  user_id UUID FK -> users.id ON DELETE CASCADE      -- a custom mix has no portfolio
  portfolio_id UUID FK -> portfolios.id NULL ON DELETE CASCADE
  kind VARCHAR CHECK ('portfolio','custom')
  created_at TIMESTAMPTZ
  years INT, period_start DATE, period_end DATE, trading_days INT, carried_forward_days INT
  capital NUMERIC(16,2), filer_status, commission_rate NUMERIC(6,5)
  rates_version, risk_free_version, price_adjustment, dividends_source, prices_as_of DATE, method_version
  inputs JSONB                                 -- tickers and weights as requested
  buy_charges, dividends_gross, wht, sell_charges, cgt, idle_cash,
  end_value_before_sale, end_value_net NUMERIC(16,2)
  total_return, total_return_before_sale, annualised_return, sharpe_ratio NULL,
  max_drawdown, win_rate NULL NUMERIC(12,6)    -- fractions
  drawdown_peak_date, drawdown_trough_date DATE, months_won INT, months_total INT
  holdings, start_date_rules, benchmark, kse100, risk_free, series JSONB

index_points                                 -- licensed daily index closes (KSE-100 once PSX permits)
  id BIGSERIAL PK
  index_code VARCHAR                           -- 'KSE100' / 'KSE100PR'
  dataset_version VARCHAR, trade_date DATE, close NUMERIC(14,4), source VARCHAR, loaded_at TIMESTAMPTZ
  UNIQUE (index_code, dataset_version, trade_date)   -- a new version is added, readers use the newest

notifications
  id UUID PK
  user_id UUID FK -> users.id
  type ENUM('buy','sell','roll')
  reasoning TEXT
  sent_at TIMESTAMP
  read BOOLEAN DEFAULT FALSE

chat_messages
  id UUID PK
  user_id UUID FK -> users.id ON DELETE CASCADE
  role VARCHAR CHECK IN ('user','assistant')
  content TEXT
  language VARCHAR CHECK IN ('en','ur','ur-latn')   -- ur-latn: Roman Urdu
  created_at TIMESTAMPTZ
  -- assistant rows only: what the reply was grounded on and how it was checked
  context_version VARCHAR, context_hash CHAR(64), context_refs JSONB
  prompt_version VARCHAR, provider VARCHAR, model VARCHAR
  input_tokens INT, output_tokens INT, latency_ms INT
  figure_check VARCHAR CHECK IN ('passed','regenerated','fallback'), figure_check_detail JSONB
  sources JSONB                                     -- the reply's data-source tags
  INDEX (user_id, created_at)

admin_action_logs
  id UUID PK
  admin_id UUID FK -> users.id
  action VARCHAR
  target VARCHAR
  created_at TIMESTAMP
```

> **Phase 5 schema deviation (2026-10-11):** the draft `portfolio_holdings` had one `brokerage_fee` and `gross_price` / `net_price` columns and `TIMESTAMP`. As built, every charge line on a contract note has its own column (so the API figures can be checked line by line against the cost engine's tests), timestamps are `TIMESTAMPTZ` like every other table, and each portfolio stores its inputs, rates version and per-stock calculation so it can be explained later. CGT and WHT are projections and live in `projection`. All money math is in `services/api/services/cost_engine.py` (Decimal); the portfolio code calls it and never repeats it.

> **Phase 8 schema deviation (2026-10-13):** the draft `chat_messages` had six columns, PG enums and `TIMESTAMP`. As built, timestamps are `TIMESTAMPTZ`, role and language are CHECK-constrained strings like the Phase 5-6 tables, language adds `ur-latn` (Roman Urdu replies), and every assistant row records the context version and hash, the ids of the rows its context was built from (portfolio, predictions, backtest), the prompt version, provider, model, token counts, latency, the figure-check result and its source tags, so any reply can be re-checked later against exactly the data it was given (migration `fdddb7608c7c`).

> **Phase 6 schema deviation (2026-10-12):** the draft `backtest_results` had only the period and four metrics. As built, each result stores who ran it (`user_id`, since a custom mix has no portfolio), every input and data version, the money lines as NUMERIC(16,2), the headline ratios as NUMERIC(12,6) fractions, and the start-date variant, both benchmarks, the risk-free summary and the daily series as JSONB, so any result can be explained later exactly as it was run. `index_points` is new: no KSE-100 source may be scraped, so a licensed file is loaded by `python -m services.index_data load` with validation (Memory.md §4).

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

GET    /stocks/search?q=                # + optional last_close, last_close_date, forecast_covered (UI round)
GET    /stocks/{ticker}
GET    /stocks/{ticker}/history
GET    /stocks/{ticker}/prediction
GET    /stocks/{ticker}/sentiment

POST   /portfolio/generate              # 201; archives the previous portfolio; 422 capital_below_minimum with minimum_capital
GET    /portfolio/current               # 404 no_active_portfolio before the first one; + optional latest_backtest (UI round)
POST   /portfolio/{id}/roll-check       # changes nothing; benchmark = forecast stocks' equal-weight average
PATCH  /portfolio/{id}/exclude-stock    # returns the regenerated portfolio without that stock
                                        # every /portfolio endpoint: 409 risk_profile_required without a profile

POST   /backtest/run                    # {years, portfolio_id} or {years, custom: {capital, filer_status, holdings}}; 201
GET    /backtest/{id}                   # 404 for another user's result
GET    /backtest/universe               # stocks a custom mix may use, with whole years of history
                                        # every /backtest endpoint: 409 risk_profile_required without a profile

GET    /notifications
PATCH  /notifications/preferences

POST   /chat/message                    # {content: 1-1000 chars, language: en|ur}; 201 {user_message, reply}
GET    /chat/history?before=&limit=     # newest first, cursor paging; chat_available, unavailable_reason
DELETE /chat/history                    # 204; the caller's messages only (Phase 8 addition, not in the PRD)
                                        # every /chat endpoint: 409 risk_profile_required without a profile;
                                        # 429 rate_limited (Retry-After); 503 chat_unavailable with reason
                                        # not_configured / provider_error / provider_busy

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

| Job                     | Trigger                                                                                    | Purpose                                                                                                                                                                                                                                                                                                                                        |
| ----------------------- | ------------------------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `refresh_stock_prices`  | Scheduled: Mon-Fri 18:00 PKT (last month); Sunday 06:00 PKT (5 years + shares outstanding) | Pull end-of-day PSX prices and splits into `price_points`/`stock_splits`, recompute split factors, invalidate cached responses. The API never calls the provider (Memory.md §3)                                                                                                                                                                |
| `scrape_news_sentiment` | Scheduled: every 3 hours (decided 2026-10-11)                                              | Collect the last 7 days from Profit and Mettis Global (Business Recorder disabled 2026-10-11) (`services/news_ingestion.py`), score new headlines with FinBERT/VADER, write `sentiment_scores`; record each source's status in `news_source_status`. A failing source is skipped, never fatal; if FinBERT cannot load, headlines stay unscored |
| `refresh_dividends`     | Scheduled: Mon-Fri 18:15 PKT                                                               | Store dividend events in `stock_dividends` and re-assess each against the served closes (`div-v1`)                                                                                                                                                                                                                                             |
| `run_predictions`       | Scheduled: Mon-Fri 18:30 PKT, or on-demand                                                 | Run the current pooled LSTM + Random Forest for every stock the model covers, write `predictions`                                                                                                                                                                                                                                              |
| `train_models`          | Scheduled: Saturday 22:00 PKT (FR15), or `python -m ml.train`                              | Build a new dataset version from `price_points` and train a **candidate** with its full evaluation report, both in the git-ignored `ml/candidates/`; never changes the live model (promotion: `python -m ml.promote <version>`)                                                                                                                |
| `monitor_portfolios`    | Scheduled (e.g., every few min)                                                            | Check active portfolios against fresh predictions, trigger notifications                                                                                                                                                                                                                                                                       |
| `send_notification`     | Triggered by `monitor_portfolios`                                                          | Dispatch via FCM, target latency < 5s                                                                                                                                                                                                                                                                                                          |

## 10. Caching Strategy (Redis)

- Cache stock quote and history responses (15 min TTL), built from `price_points`; the refresh job invalidates a stock's entries when it stores new prices. The provider is only called by the refresh job, so rate limits and outages never reach a request (decided 2026-10-10)
- Cache latest prediction + sentiment per stock (invalidated on `run_predictions`/`scrape_news_sentiment` completion). **As built (2026-10-11):** neither the prediction nor the sentiment endpoint is cached yet: both read a few indexed rows written by the background jobs, so a request never reaches a model or a news site
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

**As built (Phase 8, 2026-10-13):**

1. **Context, rebuilt on every message** (`services/chat_context.py`, `ctx-v3`): risk category and safety caps (never the answers); the active portfolio with every stored cost-engine line, projection and the forecast it was generated from; the latest forecast (confidence, low-confidence reasons in plain words, whether it beats the naive baseline) and news sentiment (label, counted headlines, up to 3 headline **titles** marked untrusted) for every held stock and any stock named in this or the previous two user messages; the latest backtest of the active portfolio (custom mixes ignored); the latest close of any other named stock; and what is missing, with the screen to use. Every figure is the stored value **formatted as the web shows it** (Rs. with 2 decimals, percentages rounded half up to the screen's decimals, backtest fractions as percent strings), dated in Pakistan time, and recorded with its source. Urdu replies also get an `urdu_glossary`: 31 terms (risk categories, signals, sentiment labels, break-even price, CGT, WHT, Sharpe ratio, cost lines and so on) taken from `packages/i18n` (with new `terms.*` strings for forecast, confidence, the baseline and the 10 sectors) so the chat and the screens use the same Urdu words, and only the entries whose field or label the message's context holds; sector names have no Urdu strings and stay in English. **Budget per provider** (`CHAT_CONTEXT_TOKENS`, context plus history): 12,000 tokens for Gemini, Mistral and Claude; about 4,000 for Groq, whose free tier allows 8,000 tokens a minute. Over the budget, headline titles go first, then per-holding charge lines, then the oldest history; portfolio totals, the forecasts of named stocks and the last exchange (the previous question and answer) are never dropped. The context is fitted separately for each provider, so a failover to Groq re-fits it from the full context.
2. **Memory:** the last 6 messages (each cut to 1,500 characters), oldest dropped first if over budget.
3. **Language:** the toggle decides English or Urdu; a message in Roman Urdu is answered in Roman Urdu (`services/chat_language.py`): marker words with their common spellings, as a share of the message (30%, at least two never-English markers), so Roman Urdu mixed with English finance words is recognised; words that are also English (main, he, k, to) count only next to them.
4. **Prompt** (`services/chat_prompt.py`, `prompt-v3.2`): PSX-only scope, beginner language, uncertainty on every forecast, only figures copied from the context, no orders or guarantees, out-of-scope questions declined with what the app can do, and rules the user's text cannot change. prompt-v3 (after the bake-off) adds: backtest figures always called a past test that used information from after its start date and never a return or profit; no figures in quotation marks; tickers in Latin letters; no English in brackets after Urdu words; about 120 words in English and 150 in Urdu with at most 3 holdings unless asked; follow-ups keep the previous answer's measure and name ties as ties. prompt-v3.1 adds a polite refusal of override attempts that offers what the assistant can do, in two or three sentences. prompt-v3.2 (2026-10-15, after a live test): the portfolio is always a recommendation, called by the context's `portfolio_name` ("your InvestIQ recommended portfolio" in the reply's language, from i18n), its stocks "recommended stocks", never the user's holdings, and its money figures what following it would cost; asked what to invest in, the assistant names up to 3 recommended stocks with their share of the money, says the recommendation comes from the risk profile with only a small low-confidence forecast tilt and that forecasts cover only the next trading day, and points to the Portfolio and Backtest screens, without a buy instruction or a guarantee; it never writes the context's field names. Rules and context travel in the system message; the user's text is only ever a user turn. The PRD §8.5 disclaimer is shown by the web app, not written by the model. Urdu replies use the glossary's words and translate nothing else; Roman Urdu replies keep the app's English finance terms (there are no Roman Urdu strings to take them from). Reply limits: 700 tokens for English, 1,200 for Urdu and Roman Urdu (Urdu needs more tokens for the same text); the prompt still asks for about 180 words.
5. **Figure check** (`services/chat_figure_check.py`): every number in a reply must equal a context figure at the precision written (a rounding fails); formatting, Urdu and Arabic-Indic digits and lakh-style commas are ignored; dates must be context dates; a number written in words next to a unit or magnitude fails (English, Urdu, Roman Urdu). Exempt: numbers in the user's own message, list numbering, "KSE-100". Markdown markers (bold, headings, code ticks, fences) are stripped on the server before the check and before storage, since the web app shows plain text. A draft is rejected if a figure fails the check **or if it stopped at the token limit** (a cut-off reply is never shown); the second draft is told why (the failed figures, or to be shorter) and a second rejection sends a fixed fallback. Known limitation: a wrong direction stated in words ("rose" for a fall) is not caught.
6. **Source tags** are built by the server from the figures the check matched, never from the model's claims; a figure several stocks share is credited only to a stock the reply names.
7. **No streaming:** the figure check needs the whole reply before the user sees any of it (deviation from §2's "WebSocket (chat)").
8. **Limits and failures:** 10 messages per 5 minutes and 100 per day per user (Redis, fail-open like the auth limiter); provider timeouts 5 s connect / 25 s read, one retry after Retry-After (at most 5 s), 45 s per message, one provider call per second app-wide, and every 429 counted per day. Groq's request is capped to its 8,000 tokens a minute (input plus `max_tokens`, sized at its measured 3.40 characters per token) and gets a 512-token reasoning allowance; every 429 logs the limit it names. **Failover:** with `LLM_BACKUP_PROVIDER` / `LLM_BACKUP_MODEL` set, a 429, 5xx, timeout or Groq 413 (request larger than its per-minute limit) from the primary moves the same message to the backup once, inside the same 45 s (the primary then gets a single attempt so the backup has time); a refused request or an unusable reply does not fail over. A regeneration stays on the provider that answered. `chat_messages.provider` and `model` record the one that actually answered; the failover is in `figure_check_detail`. A missing key leaves the API running with a "Chat disabled" warning and the screen's "unavailable" state; nothing is stored unless a reply exists. Chat is exempt from PRD §8.1's 2-second target (decided 2026-10-13); the target is a p95 under 15 seconds, measured from `chat_messages.latency_ms`.
9. **Privacy:** what leaves the server is the context above, the message and the last 6 messages; never the email, name, user id, password hash, tokens, questionnaire answers or another user's data. Message text is never written to the logs.

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
- **As built (2026-10-10):** one LSTM trained on 18 KSE-100 stocks together (scale-free inputs: returns, indicator ratios), 60-day windows, next-day return of the dividend-adjusted close. Confidence = Monte-Carlo dropout spread (30 fixed seeded masks) turned into a certainty (forecast / spread) and mapped to "chance the direction is right" by isotonic regression fitted on the validation period (`ml/confidence.py`). Settings are this section's starting point (64 → 32 units, dropout 0.2, 60-day window) plus Adam lr 1e-3, batch 64, at most 60 epochs; they were not tuned. Only the stopping epoch is chosen, by validation loss (early stopping, patience 8). Sentiment is not an input yet (Phase 4)
- **Training data split:** chronological train/validation/test split (never randomly shuffled — this is time-series data, shuffling would leak future information into training)

### 15.2 SVM / Random Forest (buy/sell/hold classifier)

- **As built:** Random Forest only (SVM skipped, Memory.md §3), one model for all 18 stocks; labels BUY / SELL for a next-day move beyond +/-1%, otherwise HOLD. Fixed: 300 trees, depth 6, balanced class weights, seed 42. `min_samples_leaf` is chosen from a grid declared before training, {5, 10, 20, 40}, by balanced accuracy on the validation period (each value fitted on the training period; a tie goes to the larger value); the chosen value is refitted on train + validation and scored on the test period once. The same selection runs inside every walk-forward fold

- Same engineered feature set as LSTM, framed as classification instead of regression
- Output: buy / sell / hold label + probability, used as a secondary signal alongside the LSTM forecast
- Random Forest additionally provides feature importance — useful in the chatbot's "what's driving this" explanations and in the FYP defense

### 15.3 FinBERT Sentiment Pipeline

- Pre-trained FinBERT (HuggingFace `ProsusAI/finbert` or equivalent) run on scraped headlines/article text
- Output: positive/negative/neutral label + confidence
- VADER fallback triggers when FinBERT confidence < defined threshold or input text is very short (e.g., tweet-length)
- Sentiment scores aggregated (e.g., time-decayed average) per stock per day, merged as an LSTM input feature
- **As built (2026-10-11, Phase 4):** sources Profit and Mettis Global (history and live) and Business Recorder (disabled 2026-10-11: its feeds never yielded a headline about a tracked stock; the scraper is kept); polite scraping (identifying user agent, robots.txt for every URL and redirect target, 1 request / 3 s per site, retries with backoff that honour `Retry-After`) in `services/api/integrations/news/`; only headline, source, URL and publish time are stored. An article's stocks are the ones its URL slug names (never a stock named only in the headline); exclusions are checked against the headline and slug together; a headline that does not match its URL is not stored (`integrations/news/matching.py`). FinBERT is `ProsusAI/finbert` pinned to revision `4556d13`; a headline's score is P(positive) - P(negative), used only as the model input; the stock page shows FinBERT's label with its probability. Measured accuracy: 97.2% on Financial PhraseBank (upper bound) and 67.7% on 155 labelled PSX headlines (`ml/reports/finbert_evaluation.md`). VADER scores a headline when FinBERT's top probability is below 0.50 or it has 3 words or fewer (label cut-offs ±0.05). The model inputs are `news_weight` (decayed headline count, half-life 3 trading days, 10-day window; 0 = no news) and `sentiment` (decayed mean score); a headline after the PSX close counts for the next trading day: 15:30 PKT, or the earlier Ramadan close from PSX notices (2022: 14:00 Mon-Thu / 13:00 Fri; 2023-2026: 13:30 / 12:30) (`ml/features.py`). Sentiment is stale when either Profit or Mettis has gone more than 24 hours without a successful scrape (one missing source would bias the news feature); a model that reads news then falls back to its price-only model and the forecast is flagged (FR22); if that fallback model is missing, the prediction run stops with status `fallback_model_missing` and the stored forecasts stay as they are. Evaluation: `ml/reports/finbert_evaluation.md`; with vs without: `ml/reports/sentiment_experiment_*.md`

### 15.4 Model Versioning

- Every trained model artifact tagged with a `model_version` (timestamp or semantic version)
- `predictions` table stores which `model_version` generated each forecast — enables comparing model performance over time and rolling back if a retrain underperforms
- **As built:** `services/api/ml/artifacts/<model_version>/` holds `lstm.pt`, `preprocess.joblib`, `random_forest.joblib`, `calibrator.joblib` and `metadata.json` (dataset version and hashes, cut dates, hyperparameters, metrics, walk-forward, training time); every joblib file carries the version and the loader refuses a mismatch. `latest.json` names the current version, and the API serves only that version's predictions. Artifacts are not in git; the evaluation report (`ml/reports/`) and the dataset (`ml/data/<dataset_version>/`) are
- **Candidates and promotion (FR15, Workflow.md Appendix E, decided 2026-10-10):** every training run (the `ml.train` CLI and the weekly `train_models` job) writes only a candidate: `ml/candidates/data/<dataset_version>/` and `ml/candidates/models/<model_version>/` with `report.md` (git-ignored). `latest.json` changes only through `python -m ml.promote <model_version>` (the Phase 9 admin button will call the same function), which refuses a candidate whose artifacts or report are missing, whose report does not match its metadata, or that lacks the walk-forward check or the Random Forest grid record. Promotion copies the candidate next to the earlier models (a version is never overwritten), copies its report to `ml/reports/evaluation_<model_version>.md/.json` to be committed, switches `latest.json` and appends a line to `ml/artifacts/promotions.jsonl`

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
LLM_PROVIDER=gemini|groq|mistral|claude   # Phase 8, default gemini; `mock` only for the Playwright run
LLM_MODEL=                                # the provider's pinned model id
LLM_BACKUP_PROVIDER=                      # optional: the failover provider (e.g. groq)
LLM_BACKUP_MODEL=
GEMINI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=                          # optional
CLAUDE_API_KEY=                           # optional
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

| Layer             | Approach                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Backend (FastAPI) | Pytest — unit tests for portfolio/fee-tax calculation logic (these must be exact, not approximate), integration tests for key endpoints. Tests never touch the dev DB: `pytest` creates and migrates a separate `<db>_test` database and rolls every test back. A backend test also checks that every questionnaire id/option, safety cap and risk category the API returns has an English and an Urdu label                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| ML models         | Offline evaluation notebooks/scripts reporting RMSE, directional accuracy, Sharpe ratio against held-out test data before any model is promoted to "active"                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| Frontend (web)    | Node's built-in test runner (`node --test`, no extra dependency) for logic kept in pure modules: route-guard rules, date/number formatting, ordered draft saves (`apps/web`), and the token-refresh coordinator (`packages/api-client`). `en`/`ur` key parity is checked in CI. There are no React component tests; screens are covered by the Playwright smoke tests and the manual walkthrough                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| Mobile            | Manual QA on Android emulator/device each phase; automated testing is a stretch goal given FYP time constraints                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |
| End-to-end        | Playwright (Chromium only) smoke tests in `apps/web/e2e`, run locally with `npm run e2e` (not in CI yet): the Phase 1 flow (register → partial onboarding → reload and resume → finish → dashboard → logout → login) an Urdu right-to-left run, and the backtest flow (generate a portfolio, 3-year report with headline, metrics table and legend, custom mix refused unless it totals 100%) on a MOCK market seeded by `tests/e2e_market.py`, and the chat flow (starter question, grounded reply with its source tag, Roman Urdu disclaimer, reload, clear history, Urdu right-to-left) against the MOCK LLM provider (`--mock-llm`), so no real model is ever called. The run starts its own API on the `<db>_test` database and its own web server, and deletes every account it created and the MOCK market. Plus at least one manual full-flow walkthrough (register → prediction → portfolio → backtest → chat → notification) before each phase demo |

## 20. CI/CD (lightweight, FYP-appropriate)

- GitHub Actions: on every push/PR — run backend Pytest suite + frontend lint/type-check
- No auto-deploy required for FYP; manual deploy to Vercel/Railway once a phase is stable and demo-ready
- Branch strategy: `main` (always demoable), feature branches per module (e.g., `feature/risk-profiling`, `feature/lstm-pipeline`) — see Rules.md for full Git conventions

## 21. Open Architectural Decisions

- Final choice of Postgres vs MySQL — Postgres recommended (better JSONB support for `risk_profiles.answers`), confirm with team before Phase 1 setup
- Object storage for ML model artifacts — only needed if models grow large; start with local/filesystem storage in Phase 1
- Whether `admin` is a separate app or a protected route set within the web app — recommend a protected route set within `apps/web` for FYP simplicity, split out only if genuinely needed
- Exact LSTM hyperparameters (layers, units, window size) — starting point given in Section 15.1, to be tuned empirically once real PSX data is in hand
