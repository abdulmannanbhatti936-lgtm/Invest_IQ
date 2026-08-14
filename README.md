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

| Layer | Technology |
|---|---|
| Web | React.js, Vite, Tailwind CSS |
| Mobile | React Native (Expo) |
| Backend | Python, FastAPI |
| AI/ML | TensorFlow, Scikit-learn, HuggingFace Transformers (FinBERT) |
| LLM | Claude API |
| Database | PostgreSQL, Redis |
| Background Jobs | Celery |
| Notifications | Firebase Cloud Messaging |
| Data Sources | Yahoo Finance API, PSX Data API |

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

| Doc | Purpose |
|---|---|
| `PRD.md` | Product requirements — full functional & non-functional spec |
| `Architecture.md` | System architecture, tech stack, database schema, API design |
| `Rules.md` | Coding standards and conventions |
| `Phases.md` | Development roadmap with phase dependencies and exit criteria |
| `Design.md` | UI/UX design system |
| `Memory.md` | Living project state, decisions log, open questions |
| `Workflow.md` | Step-by-step execution playbook |

## 🛠️ Local Setup

```bash
# 1. Start local infrastructure (Postgres + Redis)
cd infra && docker-compose up -d

# 2. Backend
cd services/api
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --reload

# 3. Web app
cd apps/web
npm install
npm run dev

# 4. Mobile app
cd apps/mobile
npm install
npx expo start
```

## 👥 Team

| Name | Role |
|---|---|
| Muhammad Ali Khaliq | Co-developer |
| Abdul Mannan Bhatti | Co-developer |
| Mr. Zain-ul-Abideen | Supervisor |

## ⚠️ Disclaimer

InvestIQ is an academic Final Year Project and is **not a licensed financial advisory service**. All predictions and recommendations are probabilistic in nature and should not be treated as guaranteed financial advice. Always consult a licensed broker before making investment decisions.

## 📜 License

TBD
