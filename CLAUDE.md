# SESSION RULES — InvestIQ (read fully before doing anything)

You are working on InvestIQ, a Final Year Project. The docs in /docs are the
single source of truth: PRD.md (what), Architecture.md (how), Rules.md (coding
rules), Phases.md (order), Design.md (UI), Workflow.md (step-by-step run sheet),
Memory.md (current state). Code must match the docs, not the other way around.

## Start of session
1. Read docs/Memory.md §2 (Current Status), §4 (Open Questions), §11 (Pitfalls).
2. Read ONLY the Workflow.md section for the current phase/step. Open other docs
   only at the specific section you need (e.g. "Architecture.md §7"). Do not
   read all docs in full — this wastes context.
3. Tell me in 3–5 lines which phase you are on, what you will do and which doc
   sections you'll follow, then continue (see Pace).

## Scope for this semester (evaluation in ~20 days, target ~70%)
- Order: Phase 2 → 3 → 4 → 5 → 6 → 8 (Chatbot). Next semester: Phases 7, 9,
  10, 11 and Tasks 3B/3D (Memory.md §4).
- Random Forest is the only classifier (SVM skipped, documented).
- The web app must be demoable end-to-end: register → onboarding → stock
  detail with prediction and sentiment → portfolio → backtest → chatbot
  (English and Urdu).
- Phases 2 and 3 are re-audits: the old code was built on AAPL. All training,
  testing and demos use real PSX (KSE-100) data.

## Pace
- Work through a WHOLE phase without stopping after each step. Fix issues
  immediately, within the phase. Stop ONLY when:
  (a) a spec/decision is missing (data source, rates, thresholds, algorithm),
  (b) something fails that you can't fix within scope,
  (c) data would be deleted or a migration could lose data, or
  (d) the phase is complete.
- Use Sonnet for routine work; say when something really needs Opus.

## Git
- Commit locally after each step (conventional commits, Rules §2.2).
- Push only when the phase is complete, after running the FULL CI checks
  locally: ruff, black, pytest, eslint, prettier, all type-checks,
  web/api-client/i18n unit tests, i18n parity, web build, Playwright E2E.
  Then give me ONE PR link per phase. I merge via the GitHub web UI.
- Never push to main, never force-push, never rewrite history.

## Hard rules (never break these)
- Never build anything not described in PRD.md / Workflow.md. No "bonus"
  features, no extra endpoints, no extra libraries, no refactors outside the
  current phase. If you think something is missing, PROPOSE it.
- Never add a dependency not listed in Architecture.md §3 without asking me.
- Never invent specifications. If any of these are undefined, STOP and ask:
  portfolio allocation logic, fee/tax/CGT/WHT rates, risk questionnaire
  questions or thresholds, notification/rolling trigger rules, confidence score
  method, data sources. Never guess numbers.
- Never use non-PSX data (e.g. AAPL) for training, testing, or demos. Mock data
  must be clearly labelled (MOCK_ prefix / is_mock_data flag) and never reach a demo.
- Never mark a step passed without running it. "It should work" is a fail.
- Never delete files, drop tables, rewrite git history, or change working code
  outside the current phase without asking first.
- If code you find differs from the docs, do NOT silently "fix" either side.
  Report the mismatch and ask which one is correct.
- If a step is blocked (dependency down, test fails you can't fix, spec missing),
  stop and report. Do not work around it with fake data or skipped tests.

## Quality (never compromised)
The product must look professionally hand-built, not like generic AI output.

Code:
- Tests for all business logic; en + ur i18n for all UI text; docs updated
  with any deviation.
- No commented-out code, no TODOs left behind, no placeholder or "lorem"
  text, no console.log/print debugging left in.
- Comments only where they explain WHY (business rules, formulas, edge
  cases), never narrating obvious code.
- One consistent pattern per concern (one way to fetch data, one way to show
  errors, one card component). Reuse before creating anything new.
- Meaningful names, small focused functions, no duplicated logic.
- No emojis in UI, code or commits.

UI:
- Follow Design.md strictly: 8px spacing scale, the type scale, tabular
  numbers with Rs./PKR for all financial figures, one icon set (lucide),
  consistent cards, buttons and badges.
- No hype copy, no generic "Welcome to our amazing app" text. Calm,
  specific, plain-language copy (Design §10).
- Every screen has designed loading (skeleton), empty and error states.
- Color palette: deferred (Design.md §2 stays a placeholder); keep neutral
  design tokens until we design it together.
- Charts: clean axes, Rs./PKR labels, forecast visibly distinct from
  history, no default library styling left untouched.

## Phase report (once per phase, then STOP and wait for my "go")
- Per-step PASS/FAIL table with evidence (exact commands + real output).
- Issues found and how they were fixed.
- Deviations from docs (and whether the doc was updated); assumptions made.
- Manual checks for me (UI look, mobile device, Urdu quality, real data
  correctness) — say exactly how to check each.
- 3–4 screenshots of the new screens.
- The PR link.

## End of session (when I say "wrap up")
Update Memory.md §2 and append a §7 entry using the §17 template. Update §9 /
§10 / §15 trackers if anything changed. Keep entries short and truthful —
record failures and gaps honestly.
