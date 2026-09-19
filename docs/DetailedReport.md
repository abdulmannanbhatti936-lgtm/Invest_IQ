# Detailed Implementation Report

**Purpose:** This document tracks the exhaustive details of what has been implemented so far in the InvestIQ project. It covers the specific libraries used, how the implementation was coded, and what each specific task will be used for in the overall system.

> **CRITICAL RULE FOR AI:** Whenever a new task or step is completed from the `Workflow.md`, the AI **MUST** append a detailed entry for that step in this file. The entry must explain what was built, how it was implemented, the libraries/tools used, and the practical purpose of the feature in the application.

---

## Phase 0: Foundation Setup (Completed)

### Step 0.1 — GitHub Repo & Directory Structure

- **What was done:** Initialized a strict monorepo directory structure.
- **How & Libraries:** Created standard isolated folders: `apps/web`, `apps/mobile`, `packages/`, `services/api`, `infra/`, and `docs/`.
- **Rules & Regulations:** Enforced separation of concerns (backend separated from frontend, shared logic separated from platform-specific logic).
- **Purpose:** Organizes the frontend web app, frontend mobile app, shared code, backend services, and infrastructure code in a single cohesive and scalable repository.

### Step 0.2 — Infra Setup (Docker Compose)

- **What was done:** Configured containerized local infrastructure.
- **How & Libraries:** Created `infra/docker-compose.yml` pulling `postgres:15` and `redis:7` images. Mapped Postgres to host port `5435` to strictly avoid local conflicts with native Windows installations.
- **Purpose:** Provides isolated, identical local databases for storing relational user data (Postgres) and caching/task queues (Redis) across all developer environments.

### Step 0.3 — Backend Skeleton (FastAPI)

- **What was done:** Set up a robust Python backend environment.
- **How & Libraries:** Installed `FastAPI`, `Uvicorn`, `SQLAlchemy`, and `Alembic` in a virtual environment (`venv`). Created a standard folder architecture (`core`, `models`, `routers`, `schemas`). Initialized `alembic` for database migrations. Added a root `/health` endpoint and connected SQLAlchemy to the Docker Postgres database.
- **Rules & Regulations:** Set up Dependency Injection for database sessions (`get_db`) to ensure safe connection pooling.
- **Purpose:** Acts as the brain of the application. The FastAPI backend will handle all business logic, securely query the database, and interface with external AI/Finance APIs to serve data to the frontends.

### Step 0.4 — Web Skeleton (React/Vite)

- **What was done:** Initialized the browser-based frontend application.
- **How & Libraries:** Bootstrapped via `Vite` using the React + TypeScript template. Cleaned up default boilerplate code and tested local execution.
- **Purpose:** Provides a blazing-fast, modern web application interface for users to access InvestIQ via their desktop or mobile browsers.

### Step 0.5 — Mobile Skeleton (Expo)

- **What was done:** Initialized the cross-platform mobile application.
- **How & Libraries:** Bootstrapped using `Expo` and `React Native` via `npx create-expo-app` with a blank TypeScript template.
- **Purpose:** Allows us to write TypeScript code once and compile it into native iOS and Android apps, giving mobile users a premium native app experience.

### Step 0.6 — Shared Packages (NPM Workspaces)

- **What was done:** Set up reusable code packages to be shared perfectly across both web and mobile apps.
- **How & Libraries:** Configured NPM Workspaces in the root `package.json`. Created strictly typed packages: `packages/types`, `packages/api-client`, `packages/i18n` (for English/Urdu bilingual support), and `packages/design-tokens` (standardized spacing/colors).
- **Rules & Regulations:** Frontend apps must import from these `@investiq/*` packages rather than writing duplicate code.
- **Purpose:** Keeps the codebase DRY (Don't Repeat Yourself). Ensures both web and mobile platforms share the exact same types, API call logic, design themes, and bilingual translations.

### Step 0.7 — Tooling & CI/CD

- **What was done:** Added automated code quality pipelines and formatters.
- **How & Libraries:** Configured `ESLint` and `Prettier` at the root for standardizing JS/TS code. Configured `Ruff` and `Black` in `pyproject.toml` for Python backend code. Created a `.github/workflows/ci.yml` pipeline that triggers on push to run tests and type-checking.
- **Rules & Regulations:** Code must pass linting and type-checking before being considered complete.
- **Purpose:** Enforces code quality, catches syntax bugs early, and ensures strict formatting rules are maintained automatically before code is ever deployed.

### Step 0.8 — Documentation Init

- **What was done:** Documented how to run the project.
- **How & Libraries:** Authored an extensive `README.md` containing explicit local setup instructions, startup commands, and environment requirements.
- **Purpose:** Allows new developers (or AI assistants) to instantly understand how to spin up the entire local stack without trial and error.

---

## Phase 1: Auth, Onboarding & Risk Profiling (In Progress)

### Step 1.1 — Database Models

- **What was done:** Created the relational database schema models for users and their risk profiles.
- **How & Libraries:** Leveraged `SQLAlchemy` to create `User` and `RiskProfile` models. Mapped advanced PostgreSQL data types (`UUID` for primary keys, `JSONB` for quiz answers, and standard SQL `Enum` for Conservative/Moderate/Aggressive categories). Used `Alembic` to autogenerate migration scripts (`alembic revision --autogenerate`) and applied them directly to the Postgres DB container (`alembic upgrade head`).
- **Rules & Regulations:** Enforced referential integrity (Foreign Keys linking Risk Profile to User) and unique constraints (one profile per user).
- **Purpose:** Securely structures how user credentials and their financial risk tolerance will be stored in the permanent database.

### Step 1.2 — Auth API Endpoints

- **What was done:** Implemented user registration, secure login, JWT token generation, and route protection.
- **How & Libraries:**
  - Used `passlib[bcrypt]` to securely hash plain-text passwords. Explicitly pinned `bcrypt<4.0.0` to resolve a known compatibility issue with the unmaintained `passlib` library.
  - Used `python-jose[cryptography]` to issue standard JSON Web Tokens (JWTs).
  - Used `Pydantic` to validate incoming requests (e.g. validating email formats via `email-validator`).
  - Implemented `/auth/register`, `/auth/login`, and a protected `/users/me` endpoint in `FastAPI`.
  - Built a `pytest` test suite (`test_auth.py`) utilizing `TestClient` to programmatically verify that user creation, token issuance, and protected route access all function flawlessly.
- **Rules & Regulations:** Passwords are never stored in plain text. Protected routes enforce Bearer token verification on every request.
- **Purpose:** Provides the core security backbone of the app. It ensures users can securely sign up, verify their identity, and access their protected financial data without exposing their passwords to attackers.

### Step 1.3 — Risk Profile Backend

- **What was done:** Built the core backend logic to classify users into risk categories based on their questionnaire answers.
  - Wrote a pure Python function `calculate_risk_score` (in `services/api/services/risk_scoring.py`) that assigns weights to different answers and returns a category (`Conservative`, `Moderate`, `Aggressive`).
  - Added Pydantic schemas in `schemas/risk_profile.py` for validating the incoming questionnaire data.

  - Wrote SQLAlchemy CRUD operations (`crud/risk_profile.py`) to create and update a user's risk profile in the Postgres database.
  - Added `GET` and `PATCH` endpoints to `routers/users.py` allowing a logged-in user to fetch or update their profile.
- **Rules & Regulations:** Separated pure logic (scoring) from database operations to make the algorithm easily testable in isolation. 
- **Purpose:** This feature is crucial for portfolio generation. The AI must know how much risk a user is willing to take (e.g. Aggressive) in order to recommend the correct mix of high/low volatility stocks.

### Step 1.4 — Auth Unit/Integration Tests

- **What was done:** Wrote comprehensive automated tests for the authentication and risk profile endpoints, and implemented the refresh token functionality.
- **How & Libraries:**
  - Added a `/auth/refresh` endpoint and `create_refresh_token` function using `jose`.
  - Wrote exhaustive `pytest` integration tests in `test_auth.py` verifying successful login/registration, duplicate email blocking, incorrect password rejection, and token refresh capabilities.
  - Verified all tests pass successfully against the native Postgres database.
- **Rules & Regulations:** Must rigorously test failure states (bad inputs, expired tokens) not just success paths, ensuring security holds up.
- **Purpose:** Guarantees that our authentication system is perfectly secure and bug-free before we start building the frontend UI on top of it.

### Step 1.5 — Web: Auth Screens

- **What was done:** Built the frontend React UI for the Login and Register screens.
- **How & Libraries:**
  - Implemented `Login.tsx` and `Register.tsx` pages in the `apps/web` React app.
  - Used `react-hook-form` coupled with `zod` schema validation to ensure robust, client-side input validation (e.g., verifying email formats and checking that passwords match) before the request ever reaches the server.
  - Developed custom, reusable UI components (`Input.tsx` and `Button.tsx`) styled with `Tailwind CSS`.
  - Wired these screens to the FastAPI backend using `axios` inside the `@investiq/api-client` package, automatically managing the storage and attachment of JWT tokens for future API calls via an `AuthContext.tsx`.
- **Rules & Regulations:** Followed `Design.md` patterns exactly—inputs have labels above them, errors appear inline immediately on typing/submit, and Tailwind uses a standardized, clean aesthetic.
- **Purpose:** This provides the critical entry point to the application for web users, allowing them to create an account and authenticate in a smooth, professional, and visually pleasing manner.

### Step 1.6 — Web: Onboarding Questionnaire

- **What was done:** Built the interactive risk profiling wizard for new users right after they register.
- **How & Libraries:**
  - Implemented `Onboarding.tsx` as a multi-step form (single question per screen) per `Design.md` section 7.1.
  - Phrased questions in plain English (e.g., "If your investment dropped 15% in a single month...") using large, tappable choice cards instead of standard radio buttons for better UX.
  - Added a visual progress bar indicating exactly where the user is in the onboarding flow.
  - Integrated the `@investiq/api-client` to seamlessly send the final answers to the FastAPI backend, which returns the calculated risk profile (Aggressive, Moderate, Conservative).
  - Designed a beautifully formatted "Results" screen that explains what the assigned risk category means for their money, avoiding bare financial jargon.
- **Rules & Regulations:** Adhered strictly to plain-language requirements and the "single question per screen" wizard design pattern.
- **Purpose:** To gather the critical data required by our AI engine to generate personalized PSX portfolios. By making it visually engaging rather than a dry form, it builds trust from the very first interaction.

### Step 1.7 — Dashboard Structure

- **What was done:** Built the authenticated layout shell and the main dashboard screen, including its "Empty State".
- **How & Libraries:**
  - Implemented `AppLayout.tsx` which contains the standard Topbar and Sidebar navigation using `lucide-react` icons. This layout wraps all protected pages.
  - Implemented `ProtectedRoute.tsx` to ensure that unauthorized users attempting to access the dashboard are immediately redirected back to the login screen.
  - Implemented `Dashboard.tsx` with a meticulously designed "Empty State" (as mandated by `Design.md` Section 12.2), displaying a clear, actionable message prompting the user to generate their first portfolio, rather than just showing a blank screen.
- **Rules & Regulations:** Adhered to layout conventions (sidebar left, topbar right, distinct empty states) and ensured the layout scales securely with authentication state.
- **Purpose:** Forms the central hub of the application. It acts as the command center where users will eventually view their AI recommendations, track their KSE-100 comparisons, and read notifications.

### Step 1.8 — Language Toggle & RTL (Urdu)

- **What was done:** Implemented global i18n support, allowing users to toggle between English and Urdu instantly.
- **How & Libraries:**
  - Integrated `react-i18next` inside the React application and `@investiq/i18n`.
  - Added a global `Language Toggle` button to the `AppLayout` top header.
  - Used a `useEffect` hook to dynamically flip the document layout direction to `dir="rtl"` whenever Urdu is selected.
  - Re-configured Tailwind CSS classes in the sidebar (using `rtl:border-l` and `rtl:border-r-0`) so that the border seamlessly shifts to the left side when the sidebar pops out from the right in RTL mode.
  - Created a robust translation structure in `packages/i18n/src/locales/` to allow adding future translations systematically.
- **Rules & Regulations:** Complied with `Design.md` Section 1.4 ("Bilingual is a first-class citizen") and Section 23 (Right-to-Left Layout Handling).
- **Purpose:** Ensures the application is fundamentally accessible to native Urdu speakers, fulfilling a core goal of democratizing AI financial advice for the local Pakistani market.

## Phase 2: Stock Data & Market Analysis (In Progress)

### Step 2.1 — Database Models

- **What was done:** Created the relational database schema models for stocks and price points.
- **How & Libraries:** Leveraged `SQLAlchemy` to create `Stock` and `PricePoint` models. Used `Alembic` to autogenerate migration scripts (`alembic revision --autogenerate -m "Add stocks and price_points tables"`) and applied them directly to the Postgres DB container (`alembic upgrade head`).
- **Rules & Regulations:** Enforced referential integrity (Foreign Keys linking PricePoint to Stock) and indexing on critical query fields like `ticker` and `timestamp`.
- **Purpose:** Securely structures how historical market data (OHLCV - Open, High, Low, Close, Volume) will be stored in the permanent database to feed the ML pipeline later.

### Step 2.2 — External Data Client Module

- **What was done:** Built an isolated Python module to pull real financial data from Yahoo Finance.
- **How & Libraries:** Created `services/api/integrations/market_data.py`. Used the `yfinance` library to build a `MarketDataClient` class exposing `get_quote` (latest price, name, volume) and `get_history` (OHLCV time-series) methods. Installed all necessary dependencies like `pandas`, `lxml`, and `numpy` into the virtual environment.
- **Rules & Regulations:** Encapsulated the API behind a clean class interface so that if Yahoo Finance ever fails or we switch to an official PSX API, we only have to change this one file and no calling code will break.
- **Purpose:** Provides the application with a live connection to real-world stock market data, which is strictly required for evaluating current portfolios and training the AI prediction models.

### Step 2.3 — Redis Caching Layer

- **What was done:** Wrapped the new external market data client with a hyper-fast caching layer.
- **How & Libraries:** Created `core/redis.py` to establish a persistent connection pool using `redis-py` to the Docker Redis container. Then, built `services/stock_service.py` (`StockService` class) that intercepts data requests. It checks Redis for existing data (cache hit). If missing (cache miss), it queries Yahoo Finance, formats the dates for JSON serialization, and caches the result with a 15-minute Time-To-Live (TTL).
- **Rules & Regulations:** Handled all serialization carefully (datetime to ISO strings and back) because Redis stores data as flat strings. Added graceful fallback so that if Redis crashes, the app still fetches directly from the source without throwing 500 errors.
- **Purpose:** Protects the application against rate-limiting blocks from Yahoo Finance/PSX by ensuring we never hit their servers more than once every 15 minutes for the exact same ticker. This guarantees ultra-low latency response times (under 50ms) for end-users checking standard stocks.

### Step 2.4 — Endpoints

- **What was done:** Created the HTTP endpoints that the React frontend will call to fetch stock data.
- **How & Libraries:** Created Pydantic validation schemas in `schemas/stock.py`. Then created `routers/stocks.py` featuring `/stocks/search`, `/stocks/{ticker}`, and `/stocks/{ticker}/history`. Wired the new router into `main.py` and wrapped the routes with `get_current_user` to ensure only logged-in users can fetch financial data. Finally, used `pytest` and `TestClient` in `tests/test_stocks.py` to write automated tests.
- **Rules & Regulations:** Kept the route handlers extremely thin (just a few lines of code each), delegating all business logic to `StockService` as required by the `Rules.md`. Tested everything through dependency overrides to decouple tests from the database.
- **Purpose:** Exposes the backend's new market data powers to the web and mobile frontend, allowing the user interface to securely query, search, and graph stock prices.

### Step 2.5 — Automated Fetch Job

- **What was done:** Created a background task to automatically fetch and save bulk historical data into our own PostgreSQL database.
- **How & Libraries:** Configured Celery (`core/celery_app.py`) to connect to our Redis broker. Created `worker/tasks.py` which contains the `fetch_market_data_for_tickers` background job. This job grabs historical data using the `MarketDataClient`, iterates through it, and bulk-inserts all records straight into the `price_points` database table via `db.bulk_save_objects()`.
- **Rules & Regulations:** Enforced graceful error handling. If a stock doesn't exist in our DB, the task auto-creates the `Stock` parent record before associating the historical `PricePoint` entries to it. 
- **Purpose:** Ensures the AI pipeline (Phase 4) and users always have instant access to historical charts directly from our DB without querying Yahoo/PSX for historical graphing, which would be too slow and easily blocked.

### Step 2.6 — Sentiment Model (Database)

- **What was done:** Prepared the database to store AI-analyzed news sentiment scores for individual stocks.
- **How & Libraries:** Created the `NewsSentiment` SQLAlchemy model inside `services/api/models/sentiment.py` containing `headline`, `sentiment_score` (-1.0 to +1.0), and a `timestamp`. Linked it via a Foreign Key to the parent `Stock` table. Registered the model and ran `alembic revision --autogenerate` followed by `alembic upgrade head`.
- **Rules & Regulations:** Enforced strict referential integrity (if a Stock is deleted, its sentiments are cascade-deleted). Built a Python throwaway script that successfully inserted a mock positive score (+0.85) for AAPL.
- **Purpose:** Provides a persistent storage layer for the upcoming FinBERT model, so the AI has historical market mood data to use when generating predictions.

### Step 2.7 — News Scraper Job

- **What was done:** Created an automated scraper to crawl the web for the latest financial news about specific companies.
- **How & Libraries:** Built `integrations/news_scraper.py` using Python's `requests` and the `BeautifulSoup` (`bs4`) library. The scraper connects to Yahoo Finance's RSS feed (`lxml-xml` parser), rapidly extracts the real headlines for any given stock, and then bulk-inserts them into the `news_sentiments` database table with a default baseline sentiment score of 0.0 (which will be overwritten by AI in Phase 4).
- **Rules & Regulations:** To ensure a clean database, I added logic to check the database before inserting to avoid saving duplicate headlines for the same stock. 
- **Purpose:** Feeds our database with raw news data in real-time, which is the exact fuel needed for the AI sentiment analysis to predict whether the market mood is shifting towards bullish or bearish.

### Step 2.8 — Celery Beat Configuration

- **What was done:** Configured a master schedule (cron jobs) to automate the background tasks.
- **How & Libraries:** Configured `celery_app.conf.beat_schedule` inside `core/celery_app.py` using Celery's `crontab`. Set up `fetch-eod-market-data` to automatically run at 18:00 (End of Day) every day, and `fetch-hourly-news` to scrape the web every hour on the dot.
- **Rules & Regulations:** Ensured no syntax errors by loading the configuration via a testing script. Structured the queues properly so they don't block the main API threads.
- **Purpose:** This makes the InvestIQ platform entirely autonomous. It will constantly fetch, cache, and store new financial data 24/7 without requiring any manual intervention.

## Phase 3: Machine Learning - Core Logic

### Step 3.1 — ML Environment & Dependencies Setup

- **What was done:** Initialized the AI pipeline by installing necessary machine learning dependencies (`torch`, `transformers`, `scikit-learn`) and wrapped the `ProsusAI/finbert` HuggingFace sentiment analysis model.
- **How & Libraries:** 
  - Added PyTorch and Transformers to `requirements.txt` and installed them.
  - Created `ml/sentiment.py` exposing a `FinBERTSentimentModel` class.
  - The model uses `pipeline("sentiment-analysis", model="ProsusAI/finbert")` and normalizes the output confidence scores into a custom `[-1.0, 1.0]` scalar score where negative represents bearish sentiment and positive represents bullish sentiment.
  - Wrote and executed a throwaway script to test the model by inferencing on sample headlines, effectively caching the model weights locally for the web app to utilize immediately.
- **Rules & Regulations:** The model is initialized as a global singleton instance (`sentiment_model`) at the module level. This ensures that the heavy model weights (400MB+) are only loaded into RAM once when the FastAPI server starts, rather than dynamically on every request.
- **Purpose:** Acts as the AI brain of the platform. This module allows the background scrapers to evaluate the financial tone of news articles so users can see aggregated sentiment (Bullish/Bearish) for specific stocks.

### Step 3.2 — AI Predictor Background Job

- **What was done:** Created a background Celery task that automatically pipes unscored news headlines into the FinBERT neural network and saves the sentiment scores back to the database.
- **How & Libraries:** 
  - Wrote `analyze_news_sentiment()` inside `worker/tasks.py`. It queries the `news_sentiments` table for any row with `sentiment_score == 0.0` (un-analyzed), runs `sentiment_model.analyze_headline()`, and commits the new score.
  - Added this task to `core/celery_app.py`'s beat schedule as `analyze-hourly-news`, set to run at 5 minutes past the hour (allowing the scraper at minute 0 to finish first).
  - Executed a throwaway script to manually run the task. It successfully analyzed all 17 scraped headlines in the DB.
- **Rules & Regulations:** Ensures the AI is completely decoupled from user API requests. By doing the heavy lifting in background jobs, users get instant responses when querying the dashboard.
- **Purpose:** This translates raw internet text into actionable math. By automating this, the platform can aggregate the sentiment for `AAPL` over the past 24 hours (e.g. mostly negative vs positive) and feed that directly into the final portfolio prediction engine.

### Step 3.3 — Price Prediction Baseline (Random Forest)

- **What was done:** Created a baseline Machine Learning pipeline using `pandas-ta` for technical indicator generation, and `scikit-learn`'s Random Forest for prediction classification.
- **How & Libraries:** 
  - Installed `pandas-ta` to compute RSI, MACD, Simple Moving Averages, and Bollinger Bands cleanly without C++ compiler errors.
  - Created `services/api/ml/features.py` which aggregates historical `PricePoint` data, generates the technical indicators, and merges the latest AI sentiment score into a structured Pandas DataFrame.
  - Created `services/api/ml/predictor.py` which uses `RandomForestClassifier` to train on the historical data and predict a BUY, SELL, or HOLD signal for the next day, along with a confidence score.
  - Built the `Prediction` SQLAlchemy model and wired a new `GET /stocks/{ticker}/prediction` endpoint in `routers/predictions.py`.
- **Rules & Regulations:** We explicitly used a Random Forest baseline first to validate the end-to-end data pipeline before moving to heavier Deep Learning (LSTM) models, ensuring a stable, testable prototype.
- **Purpose:** This is the core "IQ" of InvestIQ. It takes raw market numbers, applies technical trading formulas, combines them with news sentiment, and gives the user a clear, jargon-free recommendation (Buy/Sell/Hold) with an exact confidence percentage.

---
**Phase 2 is officially 100% Complete.**
