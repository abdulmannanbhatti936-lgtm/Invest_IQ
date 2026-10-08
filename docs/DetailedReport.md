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

**Key principle:** Advisory only — no trade execution. The system tells users *what to consider*, never places orders.

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

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Backend Framework | FastAPI | latest | High-performance async REST API |
| ASGI Server | Uvicorn | latest | Runs FastAPI in production/dev |
| ORM | SQLAlchemy | latest | Database models & queries |
| Migrations | Alembic | latest | Database schema version control |
| Database | PostgreSQL 15 | Docker | Persistent relational data storage |
| Cache / Queue | Redis 7 | Docker | Response caching + Celery broker |
| Task Queue | Celery | latest | Async background jobs |
| Auth | python-jose + passlib | latest | JWT tokens + bcrypt password hashing |
| Validation | Pydantic v2 | latest | Request/response schema validation |
| Market Data | yfinance | latest | Yahoo Finance OHLCV data |
| News Scraping | BeautifulSoup4 + requests | latest | Financial news RSS parsing |
| AI Sentiment | HuggingFace Transformers + FinBERT | latest | NLP-based news sentiment scoring |
| ML Prediction | scikit-learn | latest | Random Forest BUY/SELL/HOLD signal |
| Technical Indicators | pandas-ta | latest | RSI, MACD, Bollinger Bands, SMA |
| Deep Learning | PyTorch + LSTM | latest | Advanced time-series price prediction |
| Frontend | React 19 + TypeScript | latest | Web UI |
| Build Tool | Vite 8 | latest | Ultra-fast frontend dev server |
| Routing | react-router-dom v7 | latest | SPA page routing |
| Forms | react-hook-form + zod | latest | Type-safe form validation |
| Charts | recharts | latest | Stock price charts |
| HTTP Client | axios | latest | API calls from frontend |
| i18n | i18next + react-i18next | latest | English/Urdu bilingual support |
| Testing | pytest | latest | Backend integration tests |
| CI/CD | GitHub Actions | - | Auto-run tests on every push |
| Containerization | Docker + docker-compose | - | Postgres + Redis local infra |

---

## Phase 0: Foundation Setup (✅ Completed)

### Step 0.1 — GitHub Repo & Directory Structure

**What was done:** Initialized a strict monorepo directory structure.

**Structure created:**
```
Invest_IQ/
├── apps/
│   ├── web/          ← React web app
│   └── mobile/       ← Expo React Native app
├── packages/
│   ├── api-client/   ← Shared HTTP client (axios wrappers)
│   ├── design-tokens/← Shared colors, spacing, typography
│   ├── shared-types/ ← Shared TypeScript interfaces
│   └── i18n/         ← English/Urdu translations
├── services/
│   └── api/          ← FastAPI Python backend
├── infra/
│   └── docker-compose.yml ← Postgres + Redis containers
├── docs/             ← All project documentation
└── .github/
    └── workflows/ci.yml ← GitHub Actions CI pipeline
```

**Purpose:** Keeps all related code in one repository while enforcing strict separation of concerns — backend never imports from frontend and vice versa.

---

### Step 0.2 — Infrastructure Setup (Docker Compose)

**What was done:** Containerized local database and cache infrastructure.

**File:** `infra/docker-compose.yml`

**Services configured:**
- **PostgreSQL 15** — mapped to `localhost:5435` (offset from default 5432 to avoid conflicts with any native PostgreSQL installations on Windows)
- **Redis 7** — mapped to `localhost:6379` (standard port)

**How to start:** `docker-compose up -d` (from `infra/` directory)

**Purpose:** Every developer gets identical database environments without manual installation. Docker containers are destroyed and recreated cleanly without affecting the host machine.

---

### Step 0.3 — Backend Skeleton (FastAPI)

**What was done:** Established the Python backend environment and folder structure.

**File structure inside `services/api/`:**
```
services/api/
├── main.py           ← FastAPI app entry point, router registration
├── core/
│   ├── database.py   ← SQLAlchemy engine + session factory
│   ├── config.py     ← Pydantic Settings (reads .env)
│   ├── redis.py      ← Redis connection pool
│   └── celery_app.py ← Celery + beat schedule
├── models/           ← SQLAlchemy ORM table definitions
├── schemas/          ← Pydantic request/response models
├── routers/          ← FastAPI route handlers
├── services/         ← Business logic layer
├── integrations/     ← External API clients
├── ml/               ← Machine learning modules
├── worker/           ← Celery background tasks
├── alembic/          ← Database migration scripts
├── tests/            ← pytest test suite
├── .env              ← Environment variables (not committed)
└── requirements.txt  ← Python dependencies
```

**Key setup:**
- Virtual environment: `python -m venv venv`
- Dependencies: `pip install -r requirements.txt`
- Database connection: SQLAlchemy reads `DATABASE_URL` from `.env`
- Dependency Injection: `get_db()` generator yields a scoped DB session per request and always closes it afterward

---

### Step 0.4 — Web Skeleton (React/Vite)

**What was done:** Initialized the browser-based frontend.

**Tech:** Vite + React + TypeScript template

**Key config fix applied:** The `vite.config.ts` was updated to alias all `@investiq/*` workspace packages directly to their TypeScript source files (bypassing the stale CommonJS dist builds), and added React `dedupe` to handle npm workspace hoisting in Vite 8:

```typescript
resolve: {
  alias: {
    '@investiq/api-client': path.resolve(__dirname, '../../packages/api-client/src/index.ts'),
    '@investiq/design-tokens': path.resolve(__dirname, '../../packages/design-tokens/src/index.ts'),
    '@investiq/shared-types': path.resolve(__dirname, '../../packages/shared-types/src/index.ts'),
    '@investiq/i18n': path.resolve(__dirname, '../../packages/i18n/src/index.ts'),
  },
  dedupe: ['react', 'react-dom'],
},
```

---

### Step 0.5 — Mobile Skeleton (Expo)

**What was done:** Initialized the cross-platform mobile app using Expo + React Native with a blank TypeScript template.

**Purpose:** Allows writing TypeScript once and compiling to native Android/iOS.

---

### Step 0.6 — Shared Packages (NPM Workspaces)

**Root `package.json` workspaces:**
```json
{ "workspaces": ["apps/*", "packages/*"] }
```

**Packages created:**

| Package | Purpose |
|---------|---------|
| `@investiq/api-client` | Axios-based HTTP client for all API calls |
| `@investiq/design-tokens` | Standardized colors, spacing, typography constants |
| `@investiq/shared-types` | TypeScript interfaces shared between web & mobile |
| `@investiq/i18n` | i18next configuration + English/Urdu translation files |

---

### Step 0.7 — Tooling & CI/CD

**Python linting:** `ruff` (fast linter) + `black` (formatter) configured in `pyproject.toml`

**JS/TS linting:** `ESLint` + `Prettier` at root level

**CI Pipeline** (`.github/workflows/ci.yml`):
- Triggers on every push to `main`
- **Backend job:** Spins up Postgres 15 + Redis 7 service containers, installs Python dependencies, runs `alembic upgrade head`, then runs `pytest tests/ -v`
- **Frontend job:** Installs npm deps, runs ESLint, runs TypeScript type-check

---

### Step 0.8 — Documentation

**Files maintained:**
- `README.md` — setup and run instructions
- `docs/Workflow.md` — step-by-step implementation plan
- `docs/Memory.md` — living project state for AI agents
- `docs/DetailedReport.md` — this file

---

## Phase 1: Auth, Onboarding & Risk Profiling (✅ Completed)

### Step 1.1 — Database Models

**File:** `services/api/models/` — `user.py`, `risk_profile.py`

**User model fields:**
- `id` — UUID primary key (cryptographically random, never guessable)
- `email` — unique string, indexed
- `hashed_password` — bcrypt hash (never the plain password)
- `created_at` — timestamp

**RiskProfile model fields:**
- `id` — UUID primary key
- `user_id` — Foreign Key → users.id (one-to-one)
- `category` — Enum: `Conservative | Moderate | Aggressive`
- `answers` — JSONB (stores raw questionnaire answers for audit)
- `score` — Integer (raw calculated score)

**Migration:** `alembic revision --autogenerate` → `alembic upgrade head`

---

### Step 1.2 — Auth API Endpoints

**File:** `services/api/routers/auth.py`

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Create new user, hash password, return JWT |
| POST | `/auth/login` | Verify credentials, return access + refresh tokens |
| POST | `/auth/refresh` | Exchange refresh token for new access token |

**Libraries:**
- `passlib[bcrypt]` — hashes passwords with bcrypt (deliberately slow, rainbow-table resistant)
- `python-jose[cryptography]` — creates and verifies HS256 JWT tokens
- `email-validator` — validates email format in Pydantic schema
- `bcrypt<4.0.0` — pinned because passlib is unmaintained and breaks with bcrypt>=4

**Token flow:**
1. User registers → password hashed → stored in DB → 24hr access token returned
2. User logs in → password verified against hash → new token pair returned
3. Protected routes: extract Bearer token from Authorization header → decode JWT → inject user into route handler via `Depends(get_current_user)`

---

### Step 1.3 — Risk Profile Backend

**File:** `services/api/services/risk_scoring.py`

**Scoring algorithm** (team-approved 2026-10-09; pure function `assess_risk()`):
- 7 questions, each option scores 3 / 2 / 1 (higher = more risk capacity) → total 7–21

| Question (id) | 3 points | 2 points | 1 point |
|---|---|---|---|
| Age (`age_band`) | Under 30 | 30 to 50 | Over 50 |
| Income stability (`income_stability`) | Very steady | Mostly steady | Irregular |
| When money is needed (`investment_horizon`) | More than 5 years | 1–5 years | Within 1 year |
| Reaction to a 15% drop (`loss_tolerance`) | Buy more | Wait | Sell |
| Share-market experience (`market_experience`) | Several years | A little / mutual fund | None |
| Goal (`investment_goal`) | Growth | Steady income | Preserve value |
| Emergency savings (`emergency_savings`) | More than 6 months | 3–6 months | Less than 3 months |

- Score → category: **7–11 Conservative, 12–16 Moderate, 17–21 Aggressive**
- Safety caps, applied after scoring (a cap can only lower the category, never raise it):
  - Needs the money within 1 year → capped at **Conservative**
  - Would sell after a drop, OR emergency savings under 3 months → capped at **Moderate**
- The API returns `score` and `caps_applied`; the onboarding result screen explains each applied cap in plain language (EN/UR)

**Endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| POST | `/users/me/risk-profile` | Submit questionnaire, calculate & save profile |
| GET | `/users/me/risk-profile` | Retrieve stored risk profile |
| PATCH | `/users/me/risk-profile` | Update profile if user retakes quiz |

---

### Step 1.4 — Auth Tests

**File:** `services/api/tests/test_auth.py`

Tests written:
- Register a new user → 201 response, token returned
- Register duplicate email → 400 conflict error
- Login with correct password → token returned
- Login with wrong password → 401 error
- Access protected route with valid token → 200
- Access protected route without token → 401
- Token refresh → new access token returned

Run: `pytest tests/test_auth.py -v`

---

### Step 1.5 — Web: Auth Screens

**Files:** `apps/web/src/pages/Login.tsx`, `Register.tsx`

**Libraries used:**
- `react-hook-form` — manages form state efficiently (no re-render per keypress)
- `zod` — defines TypeScript-safe validation schemas
- `@hookform/resolvers/zod` — connects zod to react-hook-form

**Features:**
- Real-time inline validation errors (email format, password minimum length, password match)
- JWT token stored in `AuthContext.tsx` (React Context API)
- Automatic redirect to `/onboarding` after first login, `/dashboard` on subsequent logins

---

### Step 1.6 — Web: Onboarding Questionnaire

**File:** `apps/web/src/pages/Onboarding.tsx`

**Design:** One question per screen, large tappable cards (not radio buttons), visual progress bar

**Questions cover:**
- Investment horizon (short vs long term)
- Reaction to portfolio losses (panic sell vs hold)
- Income stability
- Existing financial knowledge

**Flow:** Submit → API call → backend scores answers → returns category → shows "Results" screen explaining what Conservative/Moderate/Aggressive means in plain language

---

### Step 1.7 — Dashboard Structure

**Files:** `apps/web/src/components/layout/AppLayout.tsx`, `pages/Dashboard.tsx`, `components/auth/ProtectedRoute.tsx`

**AppLayout:** Sidebar (left) + Topbar (top-right), wraps all authenticated pages

**ProtectedRoute:** Checks `AuthContext` → if no token → redirects to `/login`

**Dashboard Empty State:** Shows actionable "Generate your first portfolio" prompt instead of a blank screen

---

### Step 1.8 — Language Toggle & RTL (Urdu)

**Files:** `packages/i18n/src/`, `apps/web/src/components/layout/AppLayout.tsx`

- Language toggle button in topbar
- `useEffect` flips `document.documentElement.dir` between `ltr` and `rtl`
- Tailwind uses `rtl:` prefix for mirrored layouts
- Translation keys in `packages/i18n/src/locales/en.json` and `ur.json`

---

## Phase 2: Stock Data & Market Analysis (✅ Completed)

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

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stocks/search?q={query}` | Search stocks by ticker or name |
| GET | `/stocks/{ticker}` | Get latest quote for a specific stock |
| GET | `/stocks/{ticker}/history` | Get OHLCV history (passed to charts) |
| GET | `/stocks/{ticker}/prediction` | Get ML prediction: BUY/SELL/HOLD + confidence |

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

## Phase 3: Machine Learning (✅ Completed)

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

| Route | Page | Description |
|-------|------|-------------|
| `/` | Home (placeholder) | Landing/status screen |
| `/login` | Login.tsx | Email + password login |
| `/register` | Register.tsx | New account creation |
| `/onboarding` | Onboarding.tsx | Risk profile quiz (protected) |
| `/dashboard` | Dashboard.tsx | Main hub (protected) |
| `/stocks` | Stocks.tsx | Search and browse stocks (protected) |
| `/stocks/:ticker` | StockDetail.tsx | Price chart + ML prediction (protected) |

---

## Database Schema (Final)

```sql
users
  id UUID PK | email UNIQUE | hashed_password | created_at

risk_profiles
  id UUID PK | user_id FK(users) | category ENUM | answers JSONB | score INT

stocks
  id UUID PK | ticker UNIQUE | name | exchange

price_points
  id UUID PK | stock_id FK(stocks) | timestamp | open | high | low | close | volume

news_sentiments
  id UUID PK | stock_id FK(stocks) | headline | sentiment_score FLOAT | timestamp

predictions
  id UUID PK | stock_id FK(stocks) | predicted_price | signal | confidence_score | model_version | timestamp
```

---

## Backend Tests (All Passing ✅)

| File | Tests | Status |
|------|-------|--------|
| `tests/test_stocks.py` | 3 (search, quote, history) | ✅ PASS |
| `tests/test_predictions.py` | 3 (prediction endpoint) | ✅ PASS |

Run all: `pytest tests/ -v` (from `services/api/` with venv active)

---

## How to Run the Complete Project

### Prerequisites
- Docker Desktop (running)
- Python 3.11+
- Node.js 20+
- Git

### Step 1 — Start Infrastructure (once per session)
```powershell
cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ\infra"
docker-compose up -d
```
Starts PostgreSQL on port 5435 and Redis on port 6379.

### Step 2 — Start Backend API
```powershell
cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ\services\api"
.\venv\Scripts\activate
alembic upgrade head
uvicorn main:app --reload
```
API available at: http://127.0.0.1:8000
API docs (Swagger): http://127.0.0.1:8000/docs

### Step 3 — Start Frontend (new terminal)
```powershell
cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ\apps\web"
npm run dev
```
Web app available at: http://localhost:5173

### First-Time Setup Only
```powershell
# Backend venv setup
cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ\services\api"
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Frontend deps
cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ"
npm install
```

---

## What Still Needs to Be Built

| Phase | Feature | Status |
|-------|---------|--------|
| Phase 4 | Sentiment API endpoint `/stocks/{ticker}/sentiment` | Not Started |
| Phase 4 | "What's Driving This" news sentiment UI panel | Not Started |
| Phase 5 | Portfolio generation using ML + risk profile | Not Started |
| Phase 5 | KSE-100 comparison chart | Not Started |
| Phase 6 | LLM Chatbot integration | Not Started |
| Phase 7 | Alerts & Notifications | Not Started |

---

## GitHub Repository

**URL:** https://github.com/abdulmannanbhatti936-lgtm/Invest_IQ
**Branch:** `main`
**CI Status:** GitHub Actions pipeline runs on every push — runs backend tests + frontend type-check

---

*Last updated: 2026-09-27*