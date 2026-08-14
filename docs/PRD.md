# PRD — InvestIQ
### AI-Based Portfolio Management System for PSX Investors

**Document owner:** Abdul Mannan Bhatti (Manam) & Muhammad Ali Khaliq
**Supervisor:** Mr. Zain-ul-Abideen — Dept. of Computer Science, NUML Islamabad
**Project type:** Final Year Project (BSCS), 2025-2026
**Status:** Fresh build — a demo was previously made but is not being carried forward
**Platform scope:** Web app + Mobile app (both in Phase 1)
**Document version:** 2.0 (expanded)

---

## 1. Executive Summary

InvestIQ is an AI-powered investment advisory platform — delivered as both a web app and a mobile app — purpose-built for retail investors on the **Pakistan Stock Exchange (PSX)**. It fuses three AI layers (LSTM/BiLSTM price prediction, FinBERT financial sentiment analysis, and an LLM conversational layer) into one product that takes a novice, zero-knowledge user from sign-up to a personalized, risk-appropriate, fully-costed portfolio recommendation — explained to them in plain English or Urdu.

InvestIQ is **advisory-only**. It never touches the user's money and never places trades. Every recommendation ends with "go execute this through your licensed broker."

The core insight the product is built around: **raw data ≠ guidance**. PSX already has data (PSX website, brokerage terminals). What it doesn't have is a system that turns that data into a personalized, honest, jargon-free answer to "what should I actually do with my money, and what will it really cost me."

## 2. Background & Market Context

The Pakistan Stock Exchange is one of South Asia's most dynamic emerging markets, yet the vast majority of the Pakistani population remains excluded from equity wealth generation. Globally, AI/ML has proven itself in financial forecasting and robo-advisory (BlackRock Systematic has run ML in production for ~20 years; studies estimate AI could contribute ~$7 trillion to global economic output over the next decade in portfolio management alone). None of this has been meaningfully localized for PSX retail investors.

### 2.1 Why This Gap Exists
- **Data without insight** — PSX and brokerage platforms provide raw prices, charts, and ratios but no plain-language translation of what any of it means for a beginner.
- **Hidden overheads** — Brokerage fees, Capital Gains Tax (CGT), and Withholding Tax are rarely factored transparently into advice, so investors misjudge real returns.
- **The advisory void** — No tool combines individual risk tolerance with real-time, sentiment-aware guidance. Advice is either generic or requires paying for a human advisor few retail investors can access.
- **Language barrier** — Financial tools are English-only and jargon-heavy; a large segment of potential investors are more comfortable reasoning about money in Urdu.

### 2.2 Academic / Literature Grounding
Reviewed literature validates each piece of InvestIQ's approach but shows no one has combined them for PSX specifically:

| Study | Contribution | Gap InvestIQ fills |
|---|---|---|
| Raza & Akhtar (2024) — SVM/LSTM/RF on KSE-100, 27 technical indicators | 85% accuracy (ANN/SVM), PSX-specific | Purely academic — no UI, no advisory, no portfolio layer |
| Iyyappan et al. (2022) — Holt-Winters + Neural Net (Wiley) | Safer investment environment via rating system | Not PSX-specific, no real-time sentiment |
| Zahid & Saleem (2025) — ML during COVID-19 on PSX (SAGE) | Crisis-period PSX-specific comparison | No portfolio recommendation, no chatbot |
| Romanko, Narayan & Kwon (2023) — ChatGPT portfolio selection (arXiv) | Proves LLMs are effective for stock selection when paired with quant optimization | Not Pakistan/PSX-specific |
| Ahmed et al. (2022) — RF + Genetic Algorithm, 170 PSX companies | PSX-specific diversified portfolio construction | Research-only, no user-facing app |
| Hassan et al. (2024) — robo-advisor survey, 350 Pakistani retail investors | Empirically proves AI advisory improves returns/reduces risk for Pakistani investors | Survey-based only — no working system was built |
| Xiao & Ihnaini (2023); Ahmed et al. MDPI (2024) — FinBERT/GPT-4 sentiment | Advanced NLP sentiment techniques validated | Not localized to PSX news/language context |
| FolioSync (competitor app) | Clean UI, real-time portfolio tracking | No AI prediction, no sentiment, no advisory logic at all |

**Conclusion InvestIQ is built on:** every individual capability (PSX prediction, sentiment scoring, LLM portfolio advice) has been proven separately in isolated research or non-Pakistani products. Nobody has shipped a single, real, bilingual, user-facing product that combines all three for PSX. That white space is InvestIQ.

## 3. Problem Statement

Novice investors in Pakistan lack access to an intelligent, data-driven, and accessible advisory system that can guide them through the complexities of the Pakistan Stock Exchange. Existing systems do not offer personalized portfolio recommendations, real-time market analysis, sentiment-driven insights, or transparent cost calculations — all of which are essential for informed investment decision-making.

## 4. Goals & Objectives

| Goal | Description | How it's measured |
|---|---|---|
| Build intelligent advisory | AI-powered system tailored to the behavioral profile of PSX retail investors | User can complete onboarding → get a personalized portfolio in one sitting |
| Integrate real-time ML | LSTM/BiLSTM deep learning for PSX price forecasting, enhanced with technical indicators | LSTM RMSE < 5%, directional accuracy > 80% |
| Clarify financial reality | 100% transparent cost engine — every quote includes brokerage fees + CGT + WHT | Every recommendation screen shows a "before fees" vs "after fees" figure |
| Empower via language | Bilingual (English/Urdu) LLM interface that explains everything jargon-free | Chatbot can hold a full advisory conversation in Urdu |
| Remove manual monitoring | Autonomous background agent that pushes buy/sell/roll alerts | Notification latency < 5 seconds from trigger |
| Build trust before capital commitment | Backtesting engine simulates strategy performance on historical PSX data | Backtest report covers 3+ years, shows Sharpe ratio, drawdown, win rate |
| Demonstrate academic rigor | Defensible FYP against supervisor/panel scrutiny | Clear literature gap analysis + working end-to-end demo |

## 5. Target Users / Personas

### 5.1 Primary — "Ahmed", the Novice Investor
- 24–35 years old, salaried professional (engineer, teacher, small business owner) in Karachi/Lahore/Islamabad
- Has disposable savings but has never invested in PSX
- Finds PSX intimidating: doesn't know what RSI, MACD, or P/E ratio mean
- Wants to be told, simply, "what should I buy, why, and what will it actually cost me" — ideally in Urdu
- Primary fear: losing money because he didn't understand what he was doing
- Primary need from InvestIQ: **confidence and clarity**, not raw data

### 5.2 Secondary — "Sara", the Cautious Beginner (Conservative risk profile)
- Wants safety over growth, is scared of volatility
- Needs the system to actively protect her from aggressive recommendations
- Will lean heavily on the backtesting module before trusting any suggestion

### 5.3 Tertiary — Admin (you/Ali during FYP demo & defense)
- Manages users, monitors model health and data source uptime
- Updates/retrains models
- Views platform-wide analytics to demonstrate system maturity to the panel

### 5.4 Explicitly NOT target users (v1)
- Day traders / high-frequency traders (need speed InvestIQ doesn't provide)
- Institutional investors / fund managers
- Investors trading non-PSX instruments (crypto, forex, international equities, mutual funds)
- Brokers themselves (InvestIQ is not a brokerage-side tool)

## 6. Scope

### 6.1 In Scope (v1 / FYP submission)
- Target audience: novice retail investors in Pakistan
- Market focus: exclusively PSX-listed companies
- Historical + real-time data analysis
- AI price prediction (LSTM/BiLSTM + SVM/Random Forest signals)
- FinBERT-based sentiment analysis on financial news (VADER fallback)
- Risk-based personalized portfolio construction (Conservative/Moderate/Aggressive)
- Transparent fee/tax-inclusive pricing (brokerage fee, CGT, WHT)
- Portfolio Rolling (switch out of underperforming holdings)
- "No Money Hold" policy (idle capital gets flagged/reallocated)
- Backtesting on 3+ years of historical PSX data
- Autonomous monitoring + push notifications (buy/sell/roll, with reasoning)
- Bilingual (English/Urdu) LLM chatbot advisor, grounded in the user's real portfolio/prediction data
- Admin panel (user mgmt, model monitoring, news source management, analytics)
- Web app (React.js + Tailwind) + Mobile app (React Native or Flutter — decision in Architecture.md)

### 6.2 Out of Scope (v1)
- **Direct trade execution** — no brokerage API integration, no order placement. This is a hard boundary, not a "later" feature to blur.
- Non-PSX markets: crypto, commodities, mutual funds, international equities
- Guaranteed-accuracy predictions — stock market predictions are inherently probabilistic; 100% accuracy is explicitly never promised, in the UI or in the defense
- Real payment processing / holding user funds
- Multi-currency support
- Social/community features (copy-trading, leaderboards, forums)
- Tax filing / FBR integration

### 6.3 Future Enhancements (explicitly post-FYP, mentioned for completeness/roadmap credibility)
- Direct brokerage API integration for one-click trade execution
- Asset class expansion: commodities, mutual funds
- Reinforcement Learning for self-improving, adaptive portfolio strategies
- Dedicated Urdu-native NLP model (rather than translation layer)

## 7. Functional Requirements (by module)

### 7.1 User Onboarding & Risk Profiling
- **FR1** — User can register via email/password (OAuth optional, stretch goal)
- **FR2** — User completes a guided questionnaire (5–10 questions: age, income stability, investment horizon, loss tolerance, prior market experience, etc.)
- **FR3** — System classifies user into **Conservative**, **Moderate**, or **Aggressive**
- **FR4** — Risk profile persists in the user's account and drives every downstream recommendation
- **FR5** — User can retake the questionnaire at any time to update their profile
- **FR6** — Edge case: user abandons onboarding mid-questionnaire → system saves partial progress and resumes on next login

**Acceptance criteria:** A new user cannot reach the dashboard/portfolio screen without a completed risk profile.

### 7.2 Stock Data & Market Analysis
- **FR7** — Fetch historical + real-time data for any PSX-listed company via Yahoo Finance API + PSX data source
- **FR8** — Display price charts (candlestick/line), volume trends, and key statistics (52-week high/low, P/E, market cap) per stock
- **FR9** — Search/browse PSX-listed companies by name, ticker, or sector
- **FR10** — Edge case: requested stock has no/insufficient historical data → show a clear "insufficient data for reliable prediction" message rather than a low-confidence guess presented as fact

### 7.3 AI Prediction Engine (LSTM)
- **FR11** — LSTM/BiLSTM model trained on historical PSX price data forecasts future price trend for a selected stock
- **FR12** — Supporting SVM/Random Forest classifiers generate buy/sell/hold signals
- **FR13** — Technical indicators computed via TA-Lib (RSI, MACD, Bollinger Bands, Moving Averages) are used as input features
- **FR14** — Every prediction displays a confidence/probability score — never presented as a guarantee
- **FR15** — Model retraining is schedulable (e.g., weekly) via the admin panel
- **FR16** — Edge case: model confidence below a defined threshold (e.g., <60%) → UI must visibly flag the prediction as low-confidence

### 7.4 Sentiment Analysis Module (FinBERT)
- **FR17** — Scrape/ingest financial news related to PSX-listed companies from configured sources
- **FR18** — Score sentiment (positive/negative/neutral) using FinBERT
- **FR19** — VADER used as a lightweight fallback when FinBERT confidence is low or text is very short (e.g., tweets)
- **FR20** — Sentiment score is merged into the prediction pipeline as an additional input feature
- **FR21** — User can view "what's driving this sentiment" — i.e., the underlying headlines/snippets that fed the score
- **FR22** — Edge case: news scraper hits rate limits or a source goes down → system degrades gracefully (falls back to price/technical-only prediction, flags reduced confidence) rather than failing the whole prediction

### 7.5 Portfolio Management Module
- **FR23** — Generate a personalized portfolio (companies + allocation %) based on risk profile + AI predictions
- **FR24** — Apply "No Money Hold" policy — any idle/unallocated capital is flagged with a reallocation suggestion
- **FR25** — Portfolio Rolling — detect underperforming holdings against thresholds and recommend switching to better opportunities
- **FR26** — Every recommendation shows: gross price → brokerage fee → CGT → WHT → **final net price/return**
- **FR27** — User can manually override/exclude specific recommended stocks (e.g., ethical/Shariah preference) and get a re-generated portfolio
- **FR28** — Edge case: user's available capital is below the minimum viable allocation for diversification → system explains the constraint rather than silently producing an unbalanced portfolio

### 7.6 Backtesting Module
- **FR29** — User can run any recommended (or custom) portfolio against historical PSX data
- **FR30** — Minimum 3 years of historical coverage required
- **FR31** — Report includes: total return, Sharpe ratio, maximum drawdown, win rate
- **FR32** — User can compare backtested InvestIQ portfolio performance against a simple KSE-100 buy-and-hold benchmark

### 7.7 Autonomous Agent & Notification Module
- **FR33** — Background job continuously monitors market conditions relevant to each user's active portfolio
- **FR34** — Push notification triggered on buy/sell/roll recommendation, including a short reasoning summary
- **FR35** — Notification latency target: < 5 seconds from trigger event to delivery
- **FR36** — User can configure notification frequency/sensitivity (e.g., only high-confidence alerts)

### 7.8 LLM Chatbot Interface
- **FR37** — Conversational interface accepts English or Urdu (mixed/Roman Urdu tolerated where feasible)
- **FR38** — Chatbot explains predictions, portfolio decisions, sentiment drivers, and market conditions in plain, jargon-free language
- **FR39** — Chatbot responses are **grounded** in the user's actual live portfolio/prediction/sentiment data — never generic, unsourced financial advice
- **FR40** — Chatbot clearly discloses uncertainty/probabilistic nature when discussing predictions
- **FR41** — Edge case: user asks something outside system scope (e.g., "should I buy Bitcoin") → chatbot states this is outside InvestIQ's PSX-only scope rather than improvising

### 7.9 Admin Module
- **FR42** — View/manage registered users (view, suspend, remove)
- **FR43** — Monitor system health: API latency, model status, data source uptime
- **FR44** — Trigger/schedule model retraining and update model parameters
- **FR45** — Manage news data source list (add/remove/prioritize sources)
- **FR46** — View platform analytics: active users, aggregate portfolio performance, notification delivery stats

## 8. Non-Functional Requirements

### 8.1 Performance
| Metric | Target |
|---|---|
| API response time | < 2 seconds (real-time data fetch) |
| Notification latency | < 5 seconds |
| Mobile app load time | < 3 seconds |
| Backtesting data coverage | 3+ years of PSX history |

### 8.2 Model Quality
| Metric | Target |
|---|---|
| LSTM RMSE | < 5% |
| Directional accuracy | > 80% |
| FinBERT sentiment accuracy | > 85% |
| Portfolio Sharpe ratio (backtested) | > 1.0 |

### 8.3 Reliability & Resilience
- Graceful degradation if a data source (news, PSX API, Yahoo Finance) is unavailable — never a hard crash; system falls back and flags reduced confidence
- Redis caching layer to reduce load on external APIs and improve response time under rate limits

### 8.4 Security & Privacy
- Passwords hashed (bcrypt/argon2), never stored in plaintext
- JWT-based session/auth tokens for API access
- User financial inputs (capital amount, risk answers) treated as sensitive — not exposed in logs
- No real payment or banking credentials are ever collected (InvestIQ does not process money)
- Admin panel access restricted by role-based auth

### 8.5 Compliance / Legal Disclaimers
- InvestIQ must display a clear disclaimer: **"Advisory only. Not a licensed financial advisor. Predictions are probabilistic. Execute trades only through a licensed PSX broker."** — shown at onboarding and on every recommendation screen
- No guarantee-of-return language permitted anywhere in the product copy

### 8.6 Localization
- Full UI + chatbot support for English and Urdu
- Currency always displayed in PKR

### 8.7 Availability
- Best-effort uptime for FYP demo purposes; no formal SLA required
- System must be demoable live during the FYP defense without external dependency failures blocking the demo (fallback/cached data path required)

## 9. Data Sources

| Source | Purpose |
|---|---|
| Yahoo Finance API | Historical + real-time PSX stock price data |
| PSX Data API / PSX website | Official PSX-listed company data |
| Financial news scrapers | Sentiment analysis input (headlines, articles) |
| Twitter/X (via Tweepy, optional) | Supplementary short-form sentiment signal (VADER) |

## 10. High-Level Data Model (entities, not final schema — see Architecture.md)

- **User** — id, email, password hash, risk profile, created_at
- **RiskProfile** — user_id, category (Conservative/Moderate/Aggressive), questionnaire answers, updated_at
- **Stock** — ticker, name, sector, listing data
- **PricePoint** — stock_id, timestamp, OHLCV data
- **Prediction** — stock_id, model_version, forecast, confidence_score, generated_at
- **SentimentScore** — stock_id, source, score, label, timestamp
- **Portfolio** — user_id, holdings[], allocations[], generated_at
- **BacktestResult** — portfolio_id, period, total_return, sharpe_ratio, max_drawdown, win_rate
- **Notification** — user_id, type (buy/sell/roll), reasoning, sent_at
- **ChatMessage** — user_id, role, content, language, timestamp
- **AdminActionLog** — admin_id, action, target, timestamp

## 11. Competitive Analysis

| Feature | InvestIQ | Existing Research Tools | FolioSync (competitor app) |
|---|---|---|---|
| PSX-specific focus | ✅ | ✅ | ❌ |
| Bilingual English/Urdu interface | ✅ | ❌ | ❌ |
| Transparent cost calculation | ✅ | ❌ | Partial |
| Autonomous AI agent | ✅ | Partial | ❌ |
| Backtesting feature | ✅ | ✅ | ❌ |

**Positioning statement:** InvestIQ is the only end-to-end AI investment advisory system built exclusively for Pakistani retail investors — combining PSX-specific data, real-time sentiment, a user-facing UI, portfolio construction, and a bilingual chatbot in one product.

## 12. Alignment with UN Sustainable Development Goals

| SDG | How InvestIQ contributes |
|---|---|
| SDG 1 — No Poverty | Enables small-scale retail investors to build wealth through informed, AI-guided decisions |
| SDG 4 — Quality Education | Promotes financial literacy via the bilingual, jargon-free LLM chatbot acting as a personal tutor |
| SDG 8 — Decent Work & Economic Growth | Encourages retail participation in PSX, contributing to national economic development |
| SDG 10 — Reduced Inequalities | Democratizes access to investment advisory previously exclusive to wealthy/institutional investors |
| SDG 17 — Partnerships for the Goals | Leverages cross-disciplinary AI + FinTech collaboration for financial inclusion |

## 13. Success Metrics (FYP Evaluation Criteria)

- Fully working end-to-end demo: registration → risk profiling → stock lookup → AI prediction → sentiment view → portfolio recommendation → backtesting → chatbot conversation → live alert
- Model metrics meet or credibly approach the targets in Section 8.2
- Supervisor/panel can hold a live bilingual (Urdu) chatbot session during defense
- Clear, defensible answer to "why is this better than an academic-only ML model or a plain tracker app like FolioSync" (see Section 11)
- Admin panel demonstrably shows system health/monitoring, not just user-facing features

## 14. Assumptions

- Yahoo Finance API and/or PSX data sources remain accessible and rate-limit-tolerant throughout development
- A Claude/GPT API key is available and budgeted for the chatbot + bilingual translation layer
- Team has access to sufficient historical PSX data (3+ years) for model training and backtesting
- Mobile app targets Android first; iOS support is a stretch goal, not guaranteed for FYP submission
- Development team (2 members) can realistically split web/backend and ML/mobile responsibilities

## 15. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| PSX data/news scraping gets rate-limited or blocked | High — breaks prediction/sentiment pipeline | Aggressive Redis caching, multiple fallback data sources, respectful scraping intervals |
| LSTM accuracy falls short of targets on real PSX volatility | Medium — weakens defense credibility | Ensemble with SVM/RF signals; be transparent about probabilistic nature in UI and defense narrative |
| Scope too large for FYP timeline (web + mobile + full ML pipeline) | High — risk of incomplete submission | Sequence phases strictly (see Phases.md); build core web app + prediction pipeline first, mobile app reuses the same backend/API |
| LLM chatbot gives financially inaccurate or hallucinated explanations | High — credibility/safety risk | Always ground chatbot responses in actual system output (real predictions/sentiment/portfolio data) rather than free-form generation |
| Two-person team, CGPA/time constraints | Medium | Strict phase discipline (Phases.md), clear module ownership split between the two members |
| Supervisor/panel questions model validity | Medium | Backtesting module + documented literature gap analysis (Section 2.2) as defense evidence |

## 16. Glossary

- **PSX** — Pakistan Stock Exchange
- **LSTM / BiLSTM** — Long Short-Term Memory / Bidirectional LSTM, deep learning models for sequential/time-series data
- **FinBERT** — A BERT-based transformer model pre-trained specifically on financial text for sentiment analysis
- **VADER** — Lexicon/rule-based sentiment analysis tool, used here as a lightweight fallback
- **RSI, MACD, Bollinger Bands** — Common technical indicators derived from price/volume data
- **CGT** — Capital Gains Tax
- **WHT** — Withholding Tax
- **No Money Hold policy** — InvestIQ's rule that idle/unallocated user capital should always be flagged for reallocation rather than sitting unused
- **Portfolio Rolling** — Strategy of switching out underperforming holdings for better opportunities based on updated predictions
- **Sharpe Ratio** — Risk-adjusted return metric used to evaluate portfolio/backtest quality

## 17. Open Questions (to resolve before/during build)

- Final decision: React Native vs Flutter for mobile (tracked in Architecture.md)
- Exact PSX data source for production use — official PSX API access vs scraping (needs confirmation/testing)
- Final UI theme/branding direction (tracked in Design.md — pending your input)
- OAuth (Google login) — in scope for v1 or deferred?
- Which financial news sources are used for scraping (specific outlets to be finalized)

## 18. References (IEEE format, from FYP proposal literature review)

[1] H. Raza and Z. Akhtar, "Predicting Stock Prices in the Pakistan Market Using Machine Learning and Technical Indicators," Modern Finance, 2024.
[2] M. Iyyappan, S. Ahmad et al., "A Novel AI-Based Stock Market Prediction Using Machine Learning Algorithm," Scientific Programming, Wiley, 2022.
[3] S. Zahid and H. M. N. Saleem, "A Comparison of Machine Learning Algorithms to Predict Stock Price During COVID-19 Outbreaks: An Empirical Investigation of Pakistan Stock Exchange," SAGE Journals, 2025.
[4] O. Romanko, A. Narayan, and R. H. Kwon, "ChatGPT-Based Investment Portfolio Selection," arXiv, Cornell University, 2023.
[5] Q. Xiao and B. Ihnaini, "Stock Trend Prediction Using Sentiment Analysis," PeerJ Computer Science, 2023.
[6] A. Ahmed et al., "Innovative Sentiment Analysis and Prediction of Stock Price Using FinBERT, GPT-4 and Logistic Regression," Big Data and Cognitive Computing, MDPI, vol. 8, no. 11, 2024.
[7] A. Khan et al., "Artificial Intelligence in Financial Market Prediction," Frontiers in Artificial Intelligence, 2025.
[8] R. Singh et al., "Comparative Analysis of LSTM, GRU, and Transformer Models for Stock Price Prediction," arXiv, 2024.
[9] F. Ahmed et al., "Effect of Machine Learning in Better Portfolio Management: Evidence From PSX," 2022.
[10] N. Hassan et al., "Influence of AI-Driven Investment Advisory Services on Portfolio Performance of Retail Investors," Journal of Financial Technology, 2024.
