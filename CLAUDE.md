# SESSION RULES — InvestIQ (read fully before doing anything)

You are working on InvestIQ, a Final Year Project. The docs in /docs are the
single source of truth: PRD.md (what), Architecture.md (how), Rules.md (coding
rules), Phases.md (order), Design.md (UI), Workflow.md (step-by-step run sheet),
Memory.md (current state). Code must match the docs, not the other way around.

## Start of session
1. Read docs/Memory.md §2 (Current Status), §4 (Open Questions), §11 (Pitfalls).
2. Read ONLY the Workflow.md section for the current step. Open other docs only
   at the specific section you need (e.g. "Architecture.md §7"). Do not read all
   docs in full — this wastes context.
3. Tell me in 3–5 lines: which step you are on, what you will do, which doc
   sections you'll follow. Then WAIT for my "go".

## Hard rules (never break these)
- ONE checkpoint at a time. After finishing a step, STOP and wait for my approval
  before starting the next one. Never chain steps together, even small ones.
- Never build anything not described in PRD.md / Workflow.md. No "bonus"
  features, no extra endpoints, no extra libraries, no refactors outside the
  current step. If you think something is missing, PROPOSE it and wait.
- Never add a dependency not listed in Architecture.md §3 without asking me.
- Never invent specifications. If any of these are undefined, STOP and ask:
  portfolio allocation logic, fee/tax/CGT/WHT rates, risk questionnaire
  questions or thresholds, notification/rolling trigger rules, confidence score
  method, data sources. Never guess numbers.
- Never use non-PSX data (e.g. AAPL) for training, testing, or demos. Mock data
  must be clearly labelled (MOCK_ prefix / is_mock_data flag) and never reach a demo.
- Never mark a checkpoint passed without running it. "It should work" is a fail.
- Never delete files, drop tables, rewrite git history, or change working code
  outside the current step without asking first.
- If code you find differs from the docs, do NOT silently "fix" either side.
  Report the mismatch and ask which one is correct.
- If a step is blocked (dependency down, test fails you can't fix, spec missing),
  stop and report. Do not work around it with fake data or skipped tests.

## Checkpoint report (required after EVERY step, exactly this format)
**Step:** X.Y — <name>
**Status:** PASSED / FAILED / PARTIAL
**What I changed:** files created/modified (paths only, one line each)
**Evidence:** exact commands run + real output (trimmed to the relevant lines)
**Could NOT verify:** anything needing a human (UI look, mobile device, Urdu
  quality, real data correctness) — tell me exactly how to check it
**Deviations from docs:** anything different from Workflow/Architecture/Rules,
  and whether you updated the doc
**Assumptions made:** any decision not specified in the docs
**Next step:** X.Y+1 — <one-line plan>
**Waiting for your approval to continue.**

Then STOP. Do not start the next step until I reply "go" or "approved".

## End of session (when I say "wrap up")
Update Memory.md §2 and append a §7 entry using the §17 template. Update §9 /
§10 / §15 trackers if anything changed. Keep entries short and truthful —
record failures and gaps honestly.