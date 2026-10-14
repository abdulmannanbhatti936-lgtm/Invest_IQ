# Phase 8 model bake-off: (d), (f), (g)

Run 2026-10-13 on the dev database (real PSX data).

- model_version: `lstm-rf-20261009T233529Z`
- portfolio_id: `31bf57d8-7cd9-4e66-88a3-d2cfbbf5a5d1`
- prompt_version: `prompt-v2`
- context_version: `ctx-v2`
- Account: temporary, Moderate (middle answer to every question), Rs 100,000 filer portfolio and a 3-year backtest; deleted after the run.
- Automatic verdicts check the figure check, guarantee and scope wording, the reply's script and the follow-up's referent. A person reads every transcript.

## (d_en) Portfolio question in English — `gemini:gemini-3.5-flash`, run 1

**Question (en):** What does my portfolio look like?

**Reply:**

> [no reply: provider_error: HTTP 503]

Figure check: **unavailable** · sources: [] · 12124 ms (after 0.0 s waiting for Groq's token window) · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']

## (d) The same question in Urdu — `gemini:gemini-3.5-flash`, run 1

**Question (ur):** میرا پورٹ فولیو کیسا ہے؟

**Reply:**

> [no reply: provider_error: HTTP 503]

Figure check: **unavailable** · sources: [] · 30137 ms (after 0.0 s waiting for Groq's token window) · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; only 0% of letters are Urdu script

## (f) Roman Urdu — `gemini:gemini-3.5-flash`, run 1

**Question (ur-latn):** mera portfolio kaisa hai? kitne paise lage?

**Reply:**

> [no reply: provider_error: HTTP 503]

Figure check: **unavailable** · sources: [] · 12679 ms (after 0.0 s waiting for Groq's token window) · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; reply is not Roman Urdu

## (g) Follow-up that depends on the previous answer — `gemini:gemini-3.5-flash`, run 1

**Question (en):** Which of my holdings has the lowest forecast confidence?

**Reply:**

> [no reply: provider_error: HTTP 503]

Figure check: **unavailable** · sources: [] · 10662 ms (after 0.0 s waiting for Groq's token window) · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; the follow-up was not answered

## (d_en) Portfolio question in English — `groq:openai/gpt-oss-120b`, run 1

**Question (en):** What does my portfolio look like?

**Reply:**

> I couldn't answer that using only figures I can check against your InvestIQ data. Your exact figures are on the Portfolio, Stocks and Backtest screens.

Figure check: **fallback** · sources: [] · 52764 ms (after 49.7 s waiting for Groq's token window) · tokens 5793/700

- Draft 1: `groq:openai/gpt-oss-120b` · cut off at the token limit: True · figures not in the context: ['09', '09'] · numbers in words: []
- Draft 2: `groq:openai/gpt-oss-120b` · cut off at the token limit: - · figures not in the context: [] · numbers in words: [] · no reply (provider error)

Automatic verdict: **fail** — figure check: ['fallback']

## (d) The same question in Urdu — `groq:openai/gpt-oss-120b`, run 1

**Question (ur):** میرا پورٹ فولیو کیسا ہے؟

**Reply:**

> [no reply: provider_error: no attempt made]

Figure check: **unavailable** · sources: [] · 49712 ms (after 0.0 s waiting for Groq's token window) · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; only 0% of letters are Urdu script

## (f) Roman Urdu — `groq:openai/gpt-oss-120b`, run 1

**Question (ur-latn):** mera portfolio kaisa hai? kitne paise lage?

**Reply:**

> [no reply: provider_error: no attempt made]

Figure check: **unavailable** · sources: [] · 49709 ms (after 0.0 s waiting for Groq's token window) · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; reply is not Roman Urdu

## (g) Follow-up that depends on the previous answer — `groq:openai/gpt-oss-120b`, run 1

**Question (en):** Which of my holdings has the lowest forecast confidence?

**Reply:**

> [no reply: provider_error: no attempt made]

Figure check: **unavailable** · sources: [] · 49710 ms (after 0.0 s waiting for Groq's token window) · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; the follow-up was not answered
