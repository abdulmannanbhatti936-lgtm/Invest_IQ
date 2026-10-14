# UI round: progress note (2026-10-15, end of session)

Branch `feat/ui-design`, 10 local commits on top of `main` (`7884e1f`). Nothing pushed.

## Done (committed)

- **Step 0 and Step 1:** CI green on main (673 pytest, 5 Playwright); audit, three directions,
  prototype and recording in `docs/design-directions/` (not yet slimmed, see next steps).
- **API (optional read-only fields only):** `GET /stocks/search` adds `last_close`,
  `last_close_date`, `forecast_covered`; `GET /portfolio/current` adds `latest_backtest`.
  `services.landing_examples` writes the landing data (engine output per risk profile, bloom
  companies, each with a sector-only variant). `plan_allocation` extracted from
  `generate_portfolio`. Tests added and passing.
- **Design tokens:** Indus Night light + dark in `packages/design-tokens` (AA contrast test,
  9 passing), 8 px spacing, Design §3 type scale, §21 elevation with a dark set, motion ≤ 400 ms.
  The web app consumes them (CSS variables inlined by `vite.config.ts`, Tailwind's stock palette
  switched off).
- **Web:** theme toggle (dark default, remembered); route-level code splitting; landing page at
  `/` (plain three.js bloom, scroll zoom, risk demo, cost flow, how it works, honesty strip,
  `VITE_LANDING_TICKERS=false` sector-only flag); redesigned dashboard, stock table, portfolio
  (donut + compact rows), price and backtest charts, onboarding choice cards, auth shell;
  ▲/▼ on headline figures; RTL-safe company names (`CompanyName`); spacing on the 8 px scale.
- **Chat bugs:** low hyphen in English replies and the Urdu "1000 / 0" counter, both fixed with
  tests.
- **Checks at the last commit:** web type-check clean, 76 web unit tests and 9 token tests pass,
  i18n parity 608 keys, ESLint clean.

## In progress (committed, not yet verified)

- **Chat wording, prompt-v3.3 / ctx-v4** (commit `a9951ec`): one Urdu risk term, short portfolio
  name after the first mention, no advice-like phrasing, firmer no-brackets rule, Roman Urdu
  glossary from i18n (`terms.romanUrdu.*`, for team review). **The chat test files have not been
  run since this change.** Version pins in `test_chat_api.py` and `test_chat_failover.py` were
  updated (prompt-v3.2 → v3.3, ctx-v3 → v4); list them as changed tests in the report.
- **Temporary dev-DB accounts still exist** (`ui_design_tmp_*@example.com`, 3 accounts) for the
  screenshots; delete them at the end as before (all user tables cascade).

## Next steps, in order

1. Run `python -m pytest -q tests/test_chat_failover.py tests/test_chat_api.py tests/test_chat_context.py tests/test_chat_eval.py`; fix anything failing.
2. Add the design-tokens test to CI (`npm test -w @investiq/design-tokens` in `.github/workflows/ci.yml`).
3. Finish the remaining screens visually in both themes and both languages: stock detail
   panels (prediction, sentiment, key stats), backtest pages and custom mix form, chat page
   header, register/login forms, roll-check panel, ComingSoon; check light theme everywhere
   (charts, chat bubbles, Nastaleeq).
4. Add the spacing test (no off-scale p/m/gap/space classes in `apps/web/src`) and remove i18n
   keys no longer used (e.g. `dashboard.portfolioReadyBody`, `backtest.report.benchmarkLine`) if
   nothing else uses them.
5. Landing assets: capture `public/landing/bloom-{dark,light}.webp` (static fallback, also used by
   the auth shell) and `public/landing/portfolio-{dark,light}-{en,ur}[-m390].webp` from the new
   portfolio screen.
6. Tests: Playwright landing check (loads, CTAs go to `/register` and `/login`, language toggle,
   logged-in redirect to the dashboard, reduced-motion shows the static image, RTL names not cut
   at 1024 px); keep all existing E2E passing.
7. Chat verification with at most 3 live messages (Urdu "what should I invest in", Roman Urdu,
   English); record transcripts in `docs/chat-eval/`.
8. Measure: build sizes before/after (before: one 1,099.90 KB / 329.92 KB gzip chunk), the
   three.js chunk size, LCP for `/` (Lighthouse desktop; Playwright 4x CPU for mobile).
9. Before/after screenshots of every screen, both themes and both languages, as WebP in
   `docs/screenshots/ui-design/`; a landing recording ≤ 2 MB.
10. Slim `docs/design-directions/`: WebP, keep only audit images the README references,
    recording ≤ 2 MB; report the final docs size.
11. Docs: Design.md §2 (light + dark) and deviations (display font, landing headline size,
    landing-only decorative motion, colour-blind-tuned gain/loss pair, theme toggle);
    Architecture.md §3 (three, @types/three, Bricolage font); Memory §2, §3, §4 (ticker flag,
    Roman Urdu review), §7; DetailedReport.
12. Full local CI (ruff, black, pytest, ESLint, Prettier, type-checks, unit tests, i18n parity,
    web build, Playwright), delete the temporary accounts, one push, compare link, PR
    description in the Phase 8 style with the hero copy (en + ur) for team review.
