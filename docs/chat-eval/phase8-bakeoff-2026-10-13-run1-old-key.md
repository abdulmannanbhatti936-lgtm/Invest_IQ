# Phase 8 model bake-off: (d), (f), (g)

Run 2026-10-13 on the dev database (real PSX data).

- model_version: `lstm-rf-20261009T233529Z`
- portfolio_id: `2540df20-d2d5-4a95-b88b-d11ea105480e`
- prompt_version: `prompt-v1`
- context_version: `ctx-v1`
- Account: temporary, Moderate (middle answer to every question), Rs 100,000 filer portfolio and a 3-year backtest; deleted after the run.
- Automatic verdicts check the figure check, guarantee and scope wording, the reply's script and the follow-up's referent. A person reads every transcript.

## (d_en) Portfolio question in English — `gemini:gemini-3.8-flash`, run 1

**Question (en):** What does my portfolio look like?

**Reply:**

> [no reply: provider_error: HTTP 403]

Figure check: unavailable · sources: [] · 2050 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']

## (d) The same question in Urdu — `gemini:gemini-3.8-flash`, run 1

**Question (ur):** میرا پورٹ فولیو کیسا ہے؟

**Reply:**

> [no reply: provider_error: HTTP 403]

Figure check: unavailable · sources: [] · 4721 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; only 0% of letters are Urdu script

## (f) Roman Urdu — `gemini:gemini-3.8-flash`, run 1

**Question (ur-latn):** mera portfolio kaisa hai? kitne paise lage?

**Reply:**

> [no reply: provider_error: HTTP 403]

Figure check: unavailable · sources: [] · 4496 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; reply is not Roman Urdu

## (g) Follow-up that depends on the previous answer — `gemini:gemini-3.8-flash`, run 1

**Question (en):** Which of my holdings has the lowest forecast confidence?

**Reply:**

> [no reply: provider_error: HTTP 403]

Figure check: unavailable · sources: [] · 1653 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; the follow-up was not answered

## (d_en) Portfolio question in English — `gemini:gemini-3.1-pro-preview`, run 1

**Question (en):** What does my portfolio look like?

**Reply:**

> [no reply: provider_busy: provider rate limit]

Figure check: unavailable · sources: [] · 5376 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']

## (d) The same question in Urdu — `gemini:gemini-3.1-pro-preview`, run 1

**Question (ur):** میرا پورٹ فولیو کیسا ہے؟

**Reply:**

> [no reply: provider_busy: provider rate limit]

Figure check: unavailable · sources: [] · 6326 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; only 0% of letters are Urdu script

## (f) Roman Urdu — `gemini:gemini-3.1-pro-preview`, run 1

**Question (ur-latn):** mera portfolio kaisa hai? kitne paise lage?

**Reply:**

> [no reply: provider_busy: provider rate limit]

Figure check: unavailable · sources: [] · 5284 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; reply is not Roman Urdu

## (g) Follow-up that depends on the previous answer — `gemini:gemini-3.1-pro-preview`, run 1

**Question (en):** Which of my holdings has the lowest forecast confidence?

**Reply:**

> [no reply: provider_busy: provider rate limit]

Figure check: unavailable · sources: [] · 5437 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; the follow-up was not answered

## (d_en) Portfolio question in English — `groq:openai/gpt-oss-120b`, run 1

**Question (en):** What does my portfolio look like?

**Reply:**

> [no reply: provider_busy: provider rate limit]

Figure check: unavailable · sources: [] · 9959 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']

## (d) The same question in Urdu — `groq:openai/gpt-oss-120b`, run 1

**Question (ur):** میرا پورٹ فولیو کیسا ہے؟

**Reply:**

> آپ کا پورٹ فولیو  Rs. 100,000.00 سرمایہ سے شروع ہوا تھا۔  
> کل لاگت Rs. 99,994.88 ہے اور ابھی Rs. 5.12 نقدی بچی ہے۔
>
> **خطرہ:** آپ کا رسک پروفائل moderate ہے۔
>
> **ہولڈنگز (۸ سٹاک):**
>
> - **MARI** – 23 شیئر، قیمت Rs. 639.22، سیکٹر Oil & Gas Exploration Companies، سرمایہ کا 14.73 %۔ بریک‑ایون قیمت Rs. 641.55 (0.36 % تبدیلی)۔ اگر forecast Rs. 639.10 پر بیچیں تو نیٹ ریٹرن ‑0.38 % (Rs. ‑56.08)۔
> - **EFERT** – 74 شیئر، قیمت Rs. 192.02، سیکٹر Fertilizer، سرمایہ کا 14.24 %۔ بریک‑ایون Rs. 192.72 (0.36 % تبدیلی)۔ forecast Rs. 191.99 پر بیچیں تو نیٹ ریٹرن ‑0.38 % (Rs. ‑53.76)۔
> - **FFC** – 24 شیئر، قیمت Rs. 534.86، سیکٹر Fertilizer، سرمایہ کا 12.86 %۔ بریک‑ایون Rs. 536.81 (0.36 % تبدیلی)۔ forecast Rs. 534.16 پر نیٹ ریٹرن ‑0.49 % (Rs. ‑63.31)۔
> - **OGDC** – 41 شیئر، قیمت Rs. 306.12، سیکٹر Oil & Gas Exploration Companies، سرمایہ کا 12.57 %۔ بریک‑ایون Rs.

Figure check: passed · sources: ['portfolio', 'backtest', 'prediction:MARI', 'prediction:EFERT', 'prediction:FFC', 'prediction:OGDC'] · 3149 ms · tokens 6736/700

Automatic verdict: **pass**

## (f) Roman Urdu — `groq:openai/gpt-oss-120b`, run 1

**Question (ur-latn):** mera portfolio kaisa hai? kitne paise lage?

**Reply:**

> [no reply: provider_busy: provider rate limit]

Figure check: unavailable · sources: [] · 9763 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['unavailable']; reply is not Roman Urdu

## (g) Follow-up that depends on the previous answer — `groq:openai/gpt-oss-120b`, run 1

**Question (en):** Which of my holdings has the lowest forecast confidence?

**Reply:**

> The forecast confidence that InvestIQ shows as the lowest is **49 %**.  
> Your holdings that have this 49 % confidence are:
>
> - **MARI** – Mari Energies Limited
> - **EFERT** – Engro Fertilizers Limited
> - **FFC** – Fauji Fertilizer Company Limited
> - **HUBC** – The Hub Power Company Limited
> - **MEBL** – Meezan Bank Limited
>
> All of these forecasts are marked as low‑confidence. The reasons given are:
>
> - The model’s confidence is below the 60 % threshold the app requires.
> - On past data the model did not perform better than simply assuming tomorrow’s price will be the same as today’s.
>
> Remember, forecasts are probabilistic and may be wrong. If you’d like more detail on any of these stocks (e.g., the forecast price, expected change, or recent news sentiment), just let me know!

Figure check: passed · sources: ['portfolio', 'portfolio', 'portfolio', 'portfolio', 'portfolio', 'prediction:MARI', 'prediction:EFERT', 'prediction:FFC', 'prediction:HUBC', 'prediction:MEBL'] · 2410 ms · tokens 6732/356

**Question (en):** and the second lowest one?

**Reply:**

> [no reply: provider_busy: provider rate limit]

Figure check: unavailable · sources: [] · 8664 ms · tokens None/None

Automatic verdict: **fail** — figure check: ['passed', 'unavailable']; follow-up does not name ['OGDC']; confidence groups, lowest first: [['EFERT', 'FFC', 'HUBC', 'MARI', 'MEBL'], ['OGDC'], ['HBL']]
