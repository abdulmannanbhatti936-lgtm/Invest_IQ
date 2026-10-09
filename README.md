# InvestIQ

**AI-Based Portfolio Management System for PSX Investors**

InvestIQ is an AI-powered investment advisory platform — web and mobile — built exclusively for retail investors on the **Pakistan Stock Exchange (PSX)**. It combines LSTM/BiLSTM price prediction, FinBERT financial sentiment analysis, and a bilingual (English/Urdu) LLM chatbot to turn raw, technical market data into personalized, plain-language investment guidance.

> **Advisory only.** InvestIQ never executes trades or holds user funds. All recommendations are executed by the user through their own licensed PSX broker. Predictions are probabilistic and never guaranteed.

**Final Year Project** — BSCS, Department of Computer Science, National University of Modern Languages (NUML), Islamabad.

---

## 🚀 Features

- **Risk Profiling** — guided onboarding classifies users as Conservative, Moderate, or Aggressive
- **AI Price Prediction** — LSTM/BiLSTM deep learning models, supported by SVM/Random Forest buy-sell-hold signals
- **Sentiment Analysis** — FinBERT-powered financial news sentiment (VADER fallback)
- **Personalized Portfolios** — risk-based allocations with fully transparent brokerage fee, Capital Gains Tax, and Withholding Tax breakdowns
- **Backtesting** — simulate portfolio performance against 3+ years of historical PSX data
- **Autonomous Agent** — background monitoring with real-time buy/sell/roll push notifications
- **Bilingual LLM Chatbot** — conversational advisor in English and Urdu, grounded in the user's real portfolio data
- **Admin Panel** — user management, system health monitoring, model retraining

## 🧱 Tech Stack

| Layer           | Technology                                                |
| --------------- | --------------------------------------------------------- |
| Web             | React.js, Vite, Tailwind CSS                              |
| Mobile          | React Native (Expo)                                       |
| Backend         | Python, FastAPI                                           |
| AI/ML           | PyTorch, Scikit-learn, HuggingFace Transformers (FinBERT) |
| LLM             | Claude API                                                |
| Database        | PostgreSQL, Redis                                         |
| Background Jobs | Celery                                                    |
| Notifications   | Firebase Cloud Messaging                                  |
| Data Sources    | Yahoo Finance API, PSX Data API                           |

## 📁 Project Structure

```
investiq/
├── apps/
│   ├── web/          # React web app
│   └── mobile/        # React Native (Expo) app
├── services/
│   ├── api/            # FastAPI backend
│   ├── ml-engine/        # LSTM/SVM/Random Forest prediction pipeline
│   ├── sentiment-engine/  # FinBERT + VADER sentiment pipeline
│   └── chatbot-service/    # LLM orchestration layer
├── packages/
│   ├── shared-types/        # Shared TypeScript types
│   ├── api-client/            # Typed API client
│   ├── i18n/                    # English/Urdu translations
│   └── design-tokens/             # Shared design tokens
├── infra/                            # Docker, deployment configs
└── docs/                                # Project documentation (see below)
```

## 📄 Documentation

Full project documentation lives in [`/docs`](./docs):

| Doc               | Purpose                                                       |
| ----------------- | ------------------------------------------------------------- |
| `PRD.md`          | Product requirements — full functional & non-functional spec  |
| `Architecture.md` | System architecture, tech stack, database schema, API design  |
| `Rules.md`        | Coding standards and conventions                              |
| `Phases.md`       | Development roadmap with phase dependencies and exit criteria |
| `Design.md`       | UI/UX design system                                           |
| `Memory.md`       | Living project state, decisions log, open questions           |
| `Workflow.md`     | Step-by-step execution playbook                               |

## 🛠️ Local Setup

Monorepo: npm workspaces for the frontends and `packages/*`, Python for the backend.

**Prerequisites:** Docker Desktop, Python 3.13, Node.js 24 (npm 11), and Git. For mobile, also install the Expo Go app on an Android phone, or an Android emulator.

Run each block from the repo root unless it says otherwise.

### 1. Infrastructure (Postgres + Redis)

```bash
cd infra
docker compose up -d --wait
docker ps        # both containers should show "(healthy)"
```

Postgres is exposed on host port **5435**, so it won't clash with a local Postgres install. Redis is on **6379**.

### 2. Backend API

```bash
cd services/api
python -m venv venv
# Windows:      .\venv\Scripts\activate
# Mac/Linux:    source venv/bin/activate
pip install -r requirements.txt
```

Create `services/api/.env` from the example. Then set `JWT_SECRET` and `JWT_REFRESH_SECRET` to two **different** long random strings (at least 32 characters). Outside `ENVIRONMENT=development` the API refuses to start with placeholder or short secrets; in development it starts but logs a loud warning.

```bash
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"   # run twice, paste one into each secret
```

Apply the migrations, which also seed the PSX company list, then start the API:

```bash
alembic upgrade head
uvicorn main:app --reload
```

- Health check: `http://127.0.0.1:8000/health` → `{"status":"ok"}`
- Interactive API docs: `http://127.0.0.1:8000/docs`

### 3. Background jobs (Celery)

Run these in two more terminals from `services/api`, with the venv active. On Windows the worker needs `--pool=solo`.

```bash
celery -A core.celery_app worker --pool=solo --loglevel=info
celery -A core.celery_app beat --loglevel=info
```

Beat runs on Asia/Karachi time. It schedules:

| Job                      | When                                                               |
| ------------------------ | ------------------------------------------------------------------ |
| Price refresh            | Every 15 min during market hours, plus an end-of-day pull at 18:00 |
| News fetch and sentiment | Hourly                                                             |
| Predictions              | 18:30                                                              |
| Model retraining         | Saturdays at 22:00                                                 |

### 4. ML models (first run only)

Predictions need trained models. Train them once from the committed PSX dataset, which is in `services/api/ml/data/raw`:

```bash
cd services/api
python -m ml.train                 # all tracked tickers; add --download to refresh the CSVs first
```

This takes a few minutes on CPU. Models are written to `ml/artifacts/`, which is gitignored, and the evaluation report goes to `ml/reports/`.

### 5. Web app

```bash
npm install                        # from the repo root: installs every workspace
cd apps/web
cp .env.example .env               # optional: VITE_API_URL, defaults to http://127.0.0.1:8000
npm run dev
```

Open `http://localhost:5173`, register, and complete the risk questionnaire.

### 6. Mobile app

```bash
cd apps/mobile
npx expo start
```

Scan the QR code with Expo Go, or press `a` to open an Android emulator.

On a phone or emulator, `127.0.0.1` points at the device itself, not your PC. So the API base URL must use your PC's LAN IP; on the Android emulator, use `10.0.2.2`.

### Code quality (same checks as CI)

From the repo root:

```bash
npm run lint                       # ESLint + Prettier rules across apps/* and packages/*
npm run format                     # rewrites files with Prettier
npm test -w @investiq/web          # web unit tests (Node's built-in test runner, no extra install)
npm run check -w @investiq/i18n    # en.json / ur.json parity: missing keys, empty values, {{placeholders}}
npx tsc -b apps/web                # web type-check
```

The Urdu font (Noto Naskh Arabic) is self-hosted in `apps/web/public/fonts/`, so nothing extra needs installing and the app works offline.

From `services/api`, with the venv active:

```bash
ruff check .
black --check .
python -m pytest
```

Tests never touch the dev database: `pytest` creates and migrates a separate `<db>_test` database (e.g. `investiq_test`, or `TEST_DATABASE_URL`) and rolls every test back afterwards.

### End-to-end tests (Playwright, local only)

Browser smoke tests of the Phase 1 flow (register → onboarding with resume → dashboard → logout → login) and an Urdu right-to-left run. They are not part of CI yet.

One-time setup, from the repo root:

```bash
npm install                                      # installs @playwright/test
npm exec -w @investiq/web -- playwright install chromium   # Chromium only
```

Each run:

1. Start Postgres and Redis (`docker compose -f infra/docker-compose.yml up -d`).
2. Make sure the backend venv exists in `services/api/venv` with `requirements.txt` installed (step 2 above).
3. From the repo root: `npm run e2e`

`npm run e2e` starts its **own** API on port 8001 (pointed at the `<db>_test` database; it refuses any database not named `*_test`) and its own web dev server on port 5174, so it never touches your dev servers or the dev database. Ports 8001 and 5174 must be free. Every account the tests create (`e2e_…@example.com`) is deleted before and after the run; the last line of output reports how many users are left in the test database.

On failure, screenshots and traces are saved to `apps/web/e2e-results/` and an HTML report to `apps/web/e2e-report/` (both git-ignored). Open a trace with `npx playwright show-trace <path-to-trace.zip>`.

## 👥 Team

| Name                | Role         |
| ------------------- | ------------ |
| Abdul Mannan Bhatti | Developer    |
| Muhammad Ali Khaliq | Co-developer |
| Mr. Zain-ul-Abideen | Supervisor   |

## ⚠️ Disclaimer

InvestIQ is an academic Final Year Project and is **not a licensed financial advisory service**. All predictions and recommendations are probabilistic in nature and should not be treated as guaranteed financial advice. Always consult a licensed broker before making investment decisions.

## 📜 License

TBD

---

Steps to run this project completly:
Terminal 1 — Docker + Backend
Ek ek line alag alag run karo:

---

powershell

cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ\infra"

---

powershell

docker-compose up -d

---

powershell

cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ\services\api"

---

powershell

.\venv\Scripts\activate

---

powershell

alembic upgrade head

---

powershell

uvicorn main:app --reload

---

---

---

Terminal 2 — Frontend (naya PowerShell window kholo)

powershell

cd "C:\Users\Abdul Mannan\Desktop\Invest_IQ\apps\web"

---

powershell

npx vite --force

---

⚠️ Important: Multiple commands ek saath paste mat karo — har line alag alag Enter karo. Space wale paths hamesha "quotes" mein likhna zaroori hai PowerShell mein.

for n8n

n8n start
