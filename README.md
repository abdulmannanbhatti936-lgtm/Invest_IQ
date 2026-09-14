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

| Layer           | Technology                                                   |
| --------------- | ------------------------------------------------------------ |
| Web             | React.js, Vite, Tailwind CSS                                 |
| Mobile          | React Native (Expo)                                          |
| Backend         | Python, FastAPI                                              |
| AI/ML           | TensorFlow, Scikit-learn, HuggingFace Transformers (FinBERT) |
| LLM             | Claude API                                                   |
| Database        | PostgreSQL, Redis                                            |
| Background Jobs | Celery                                                       |
| Notifications   | Firebase Cloud Messaging                                     |
| Data Sources    | Yahoo Finance API, PSX Data API                              |

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

This project uses a monorepo structure with npm workspaces for the frontends/packages, and Python for the backend services.

### 1. Infrastructure (Database & Cache)

Ensure you have Docker installed.

```bash
cd infra
docker-compose up -d
```

_Note: Postgres is exposed on port 5435 to avoid conflicts with local installations._

### 2. Backend API

```bash
cd services/api
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
# source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload
```

The API will be available at `http://127.0.0.1:8000`. Test the health endpoint at `http://127.0.0.1:8000/health`.

### 3. Web & Mobile Apps (Frontends)

From the root directory, install the npm workspaces:

```bash
npm install
```

**To run the Web App:**

```bash
cd apps/web
npm run dev
```

Open `http://localhost:5173`.

**To run the Mobile App:**

```bash
cd apps/mobile
npx expo start
```

Use the Expo Go app or press `a`/`i` to launch an emulator.

### Code Quality (CI / CD)

Run the following commands from the project root to check linting and formatting:

```bash
npm run format
npm run lint
```

For the Python backend (from `services/api` inside the venv):

```bash
ruff check .
black --check .
python -m pytest
```

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
