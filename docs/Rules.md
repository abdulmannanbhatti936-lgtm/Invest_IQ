# Rules.md — InvestIQ

### Coding Standards, Conventions & Guardrails

**Audience:** This document is written for an AI coding agent (e.g., Antigravity AI) working autonomously or semi-autonomously on this codebase, as well as human contributors (Manam, Ali).
**Companion docs:** PRD.md, Architecture.md, Phases.md, Design.md, Memory.md
**Principle:** These are not suggestions. If a rule here conflicts with a shortcut that seems faster, the rule wins. Consistency across a two-person FYP team (and an AI agent working alongside them) matters more than any individual clever solution.

---

## 1. General Principles

1. **Never invent scope.** Only build what PRD.md's functional requirements describe. If something seems missing or ambiguous, flag it in a comment or ask — don't silently expand scope.
2. **Business logic never lives in the frontend.** Fee/tax calculations, portfolio allocation logic, and prediction logic live only in the backend (`services/api`, `services/ml-engine`). The frontend/mobile app only displays what the backend returns.
3. **No hallucinated financial output.** The LLM chatbot must never generate a price, prediction, or recommendation from its own reasoning — it only explains data that was fetched from the database. See Architecture.md Section 12.
4. **No guaranteed-return language anywhere** — in UI copy, chatbot prompts, code comments, or commit messages. Predictions are always framed as probabilistic (per PRD.md Section 8.5).
5. **Advisory-only, always.** No code path should ever place, simulate placing, or imply placing a real trade. This boundary is absolute (PRD.md Section 6.2).
6. **Match Architecture.md exactly.** Don't introduce a new database, new state management library, or new folder structure without updating Architecture.md first — the docs and the code must never drift apart.

## 2. Repository & Git Conventions

### 2.1 Branching

- `main` — always in a demoable state. Never push directly to `main`.
- Feature branches: `feature/<short-description>` (e.g., `feature/risk-profiling`, `feature/lstm-pipeline`, `feature/portfolio-fee-calc`)
- Bugfix branches: `fix/<short-description>`
- One feature branch = one module/functional requirement group where possible, to keep PRs reviewable

### 2.2 Commit Messages

Format: `<type>(<scope>): <short description>`

Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`

Examples:

```
feat(risk-profiling): add onboarding questionnaire endpoint
fix(portfolio): correct CGT calculation rounding error
docs(architecture): update DB schema for sentiment_scores
```

### 2.3 Pull Requests

- Every PR references the FR number(s) it implements (e.g., "Implements FR23–FR26")
- No PR merges into `main` with failing tests or lint errors (see Section 8, CI/CD)
- Keep PRs scoped to one module — a PR that touches onboarding, portfolio, and chatbot at once is a sign the work should have been split

### 2.4 What never gets committed

- `.env` files with real values (only `.env.example` with placeholders)
- API keys, database credentials, Firebase service account JSON
- Trained model artifacts above a reasonable size — use `.gitignore` for `*.h5`, `*.pt`, `*.pkl` model files; document how to regenerate them instead
- `node_modules/`, `__pycache__/`, `venv/`, build output directories

## 3. Backend Rules (Python / FastAPI)

### 3.1 Style

- Follow PEP 8; format with `black`, lint with `ruff` or `flake8`
- Type hints required on all function signatures — FastAPI's value comes from this, don't skip it
- Pydantic models for every request/response body — never accept or return raw untyped dicts at an API boundary

### 3.2 Structure

- One router per resource (`routers/auth.py`, `routers/portfolio.py`, `routers/stocks.py`, etc.)
- Business logic lives in `services/`, not inline in route handlers — route handlers should be thin: validate input → call service → return response
- Database access via a repository/CRUD layer (`crud/`), not raw queries scattered through route handlers

### 3.3 Error Handling

- Use FastAPI's `HTTPException` with meaningful status codes (400 for bad input, 401/403 for auth, 404 for missing resources, 422 for validation, 500 only for genuine unexpected failures)
- Every external API call (Yahoo Finance, PSX data, Claude API, FCM) wrapped in try/except with a graceful fallback per Architecture.md Section 8.3 — a third-party outage must never crash an endpoint
- Never swallow exceptions silently — log them (structured logging per Architecture.md Section 18)

### 3.4 Financial Calculations

- All fee/tax/price math done with `Decimal`, never raw floats — floating point rounding errors are unacceptable in anything showing a price to a user
- Every fee/tax calculation function must have a corresponding unit test with known input → expected output pairs (per Architecture.md Section 19)

### 3.5 ML Code

- Training scripts and inference code are separated — training is not run inside the request/response cycle, ever (use Celery jobs per Architecture.md Section 9)
- Every model file logs its training data date range, hyperparameters, and evaluation metrics alongside the saved artifact (for reproducibility and for the FYP report)
- Random seeds fixed during development for reproducible results; documented if intentionally varied for final evaluation

## 4. Frontend Rules (React / React Native)

### 4.1 Style

- TypeScript everywhere — no `.js`/`.jsx` files in new code
- Format with Prettier, lint with ESLint (shared config across `apps/web` and `apps/mobile`)
- Functional components + hooks only — no class components

### 4.2 Structure

- Components organized by feature, not by type (`features/portfolio/`, `features/onboarding/`, `features/chat/` — not one giant `components/` dump)
- Shared, truly generic UI pieces (buttons, cards, inputs) live in a `components/ui/` folder
- No component should directly call `fetch`/`axios` — all API calls go through the shared `packages/api-client`

### 4.3 State

- Server state (predictions, portfolio, stock data) via React Query — no manual `useEffect` + `useState` data-fetching patterns
- Never store server data that React Query already owns in local component state — this causes stale-data bugs
- Language (English/Urdu) and theme are global state, accessible app-wide, persisted locally

### 4.4 Copy & Language

- All user-facing text goes through `packages/i18n` — no hardcoded English strings in components, even during early development. Retrofitting i18n later is expensive; doing it from day one is not.
- Every screen that shows a prediction, recommendation, or return figure must include the disclaimer language from PRD.md Section 8.5, in the active language

## 5. API Contract Rules

- Every new/changed endpoint must be reflected in FastAPI's OpenAPI schema (automatic if types/Pydantic models are correct)
- `packages/api-client` is regenerated (or manually updated) whenever the backend contract changes — the frontend must never hand-write duplicate types that can drift from the backend
- Breaking changes to an existing endpoint require updating every caller (web + mobile) in the same PR, not "later"

## 6. Security Rules

- Never log passwords, tokens, or full financial details (Architecture.md Section 18)
- Every admin-only endpoint must have an explicit role check — don't rely on the frontend hiding a button as the only protection
- All user input validated server-side via Pydantic, even if also validated client-side
- Dependencies kept current — no known-vulnerable package versions pinned indefinitely; if a vulnerability is flagged (e.g., via `pip-audit`/`npm audit`), it gets addressed, not ignored
- Rate limit auth endpoints (register/login) to reduce brute-force risk

## 7. Documentation Rules

- Every module's README (or a docstring block at the top of its main file) states: what it does, what FRs it implements (reference PRD.md), and how to run/test it locally
- Any deviation from Architecture.md must update Architecture.md in the same PR — the docs are the source of truth, not tribal knowledge
- Complex logic (fee/tax calculation, portfolio rolling thresholds, LSTM feature engineering) gets inline comments explaining _why_, not just _what_

## 8. Testing & CI Rules (expands on Architecture.md Section 19–20)

- No PR merges with failing tests
- New backend logic (especially anything touching money math or portfolio generation) ships with tests in the same PR, not as a follow-up
- ML model changes are evaluated against the same held-out test set before being called "improved" — no informal "it feels better" promotions

## 9. Rules Specific to the AI Coding Agent (Antigravity AI)

1. **Always check PRD.md → Architecture.md → Phases.md, in that order, before starting new work.** Don't build ahead of the current phase (see Phases.md) even if it seems efficient — half-built future-phase code creates merge conflicts and confuses the human teammates.
2. **When a requirement is ambiguous, state the assumption made and proceed** — don't block on a question that has a reasonable default, but do make the assumption visible (in a PR description or code comment) so a human can correct it.
3. **Never fabricate PSX data, stock tickers, or financial figures for "placeholder" purposes in a way that could be mistaken for real data later.** If sample/mock data is needed for development, label it unmistakably (e.g., a `MOCK_` prefix or a `is_mock_data` flag) and never let it silently reach a demo.
4. **Don't introduce new dependencies without checking Architecture.md's tech stack first.** If a task seems to need a library not already listed, prefer the closest existing tool before adding a new one.
5. **Every generated file respects the folder structure in Architecture.md Section 5** — don't create new top-level folders without updating that doc.
6. **When generating tests, test the actual business rule** (e.g., "CGT is calculated correctly for a gain over the taxable threshold"), not just that a function runs without throwing.
7. **Flag scope creep back to the user** rather than silently implementing something PRD.md doesn't describe, even if it seems like a natural improvement.

## 10. Definition of Done (per feature/module)

A feature is not "done" until:

- [ ] It matches its functional requirement(s) in PRD.md exactly
- [ ] Backend logic has unit tests (especially any money/fee/tax math)
- [ ] API contract is reflected in OpenAPI schema and `packages/api-client`
- [ ] Frontend copy goes through `packages/i18n` (English + Urdu both present, even if Urdu is a rough first pass)
- [ ] No secrets/hardcoded credentials introduced
- [ ] Lint and tests pass in CI
- [ ] Disclaimer/uncertainty language present on any prediction/recommendation-facing screen
- [ ] Manually walked through once end-to-end (per Architecture.md Section 19)
