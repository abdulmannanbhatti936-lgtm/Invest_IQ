# Phase 8 model bake-off: (d), (f), (g)

Run 2026-10-13 on the dev database (real PSX data).

- model_version: `lstm-rf-20261009T233529Z`
- portfolio_id: `67e995ba-919d-48c1-8a90-1c138a9de33e`
- prompt_version: `prompt-v2`
- context_version: `ctx-v2`
- Account: temporary, Moderate (middle answer to every question), Rs 100,000 filer portfolio and a 3-year backtest; deleted after the run.
- Automatic verdicts check the figure check, guarantee and scope wording, the reply's script and the follow-up's referent. A person reads every transcript.

## (d_en) Portfolio question in English — `groq:openai/gpt-oss-120b`, run 1

**Question (en):** What does my portfolio look like?

**Reply:**

> Here’s a quick snapshot of your InvestIQ portfolio (as of 2026‑10‑09):
>
> - Total capital: Rs. 100,000.00
> - Cash left: Rs. 5.12
> - Number of stocks: 8
> - Risk category: moderate
>
> Holdings
>
> 1. Mari Energies Limited (MARI) – 23 shares
>    - Current price: Rs. 639.22
>    - Total cost: Rs. 14,728.72 (includes Rs. 26.66 charges)
>    - Break‑even price: Rs. 641.55 (needs a 0.36 % rise to cover cost)
>    - Forecast (next trading day): Rs. 639.10, signal HOLD, confidence 49 % (low confidence)
> 2. Engro Fertilizers Limited (EFERT) – 74 shares
>    - Current price: Rs. 192.02
>    - Total cost: Rs. 14,235.25 (charges Rs. 25.77)
>    - Break‑even price: Rs. 192.72 (0.36 % above current)
>    - Forecast: Rs. 191.99, signal HOLD, confidence 49 % (low confidence)
> 3. Fauji Fertilizer Company Limited (FFC) – 24 shares
>    - Current price: Rs. 534.86
>    - Total cost: Rs. 12,859.91 (charges Rs. 23.27)
>    - Break‑even price: Rs. 536.81 (0.36 % above)
>    - Forecast: Rs. 534.16, signal HOLD, confidence 49 % (low confidence)
> 4. Oil & Gas Development Company Limited (OGDC) – 41 shares
>    - Current price: Rs. 306.12
>    - Total cost: Rs. 12,573.68 (charges Rs. 22.76)
>    - Break‑even price: Rs. 307.24 (0.37 % above)
>    - Forecast: Rs. 305.51, signal HOLD, confidence 53 % (low confidence)
> 5. The Hub Power Company Limited (HUBC) – 59 shares
>    - Current price: Rs. 200.15
>    - Total cost: Rs. 11,830.28 (charges Rs. 21.43)
>    - Break‑even price: Rs. 200.88 (0.36 % above)
>    - Forecast: Rs. 200.25, signal HOLD, confidence 49 % (low confidence)
> 6. Pakistan State Oil Company Limited (PSO) – 32 shares
>    - Current price: Rs. 360.66
>    - Total cost: Rs. 11,562.05 (charges Rs. 20.93)
>    - Break‑even price: Rs. 361.98 (0.37 % above)
>    - Forecast: Rs. 362.40, signal HOLD, confidence 55 % (low confidence)
> 7. Meezan Bank Limited (MEBL) – 21 shares
>    - Current price: Rs. 548.45
>    - Total cost: Rs. 11,538.32 (charges Rs. 20.87)
>    - Break‑even price: Rs. 550.45 (0.36 % above)
>    - Forecast: Rs. 548.04, signal HOLD, confidence 49 % (low confidence)
> 8. Habib Bank Limited (HBL) – 36 shares
>    - Current price: Rs. 295.76
>    - Total cost: Rs. 10,666.67 (charges Rs. 19.31)
>    - Break‑even price: Rs. 296.84 (0.37 % above)
>    - Forecast: Rs. 294.83, signal HOLD, confidence 54 % (low confidence)
>
> Overall totals
>
> - Bought value (price before charges): Rs. 99,813.88
> - Buying charges: Rs. 181.00
> - Total cost (including charges): Rs. 99,994.88
>
> All forecasts are probabilistic and may be wrong; each is marked low confidence because the model’s confidence is below the 60 % threshold and it did not outperform a simple “price stays the same” baseline.

Figure check: **passed** · sources: ['portfolio', 'backtest', 'prediction:MARI', 'prediction:EFERT', 'prediction:FFC', 'prediction:HUBC', 'prediction:MEBL', 'prediction:OGDC', 'prediction:PSO', 'prediction:HBL', 'sentiment:OGDC'] · 6165 ms (after 0.0 s waiting for Groq's token window) · tokens 5793/1016

- Draft 1: `groq:openai/gpt-oss-120b` · cut off at the token limit: False · figures not in the context: [] · numbers in words: []

Automatic verdict: **pass**

## (d) The same question in Urdu — `groq:openai/gpt-oss-120b`, run 1

**Question (ur):** میرا پورٹ فولیو کیسا ہے؟

**Reply:**

> آپ کا پورٹ فولیو 8 اسٹاک پر مشتمل ہے اور کل سرمایہ "Rs. 100,000.00" ہے۔
>
> - کل لاگت "Rs. 99,994.88" ہے (خریداری کے اخراجات "Rs. 181.00" شامل) اور ابھی نقد بچت "Rs. 5.12" باقی ہے۔
> - ریسک کیٹیگری متوازن (moderate) ہے۔
> - پورٹ فولیو کا سالانہ منافع "+52.53%" (بیک ٹیسٹ کے مطابق) اور شارپ ریشو "1.47" ہے۔
>
> اہم ہولڈنگز (ہر اسٹاک کی قیمت 2026‑10‑09 کے مطابق):
>
> - MARI (مارِی انرجیز) "Rs. 639.22" پر 23 شیئر، بریک ایون قیمت "Rs. 641.55"۔
> - EFERT (انگرو فرٹیلائزر) "Rs. 192.02" پر 74 شیئر، بریک ایون قیمت "Rs. 192.72"۔
> - FFC (فوجی فرٹیلائزر) "Rs. 534.86" پر 24 شیئر، بریک ایون قیمت "Rs. 536.81"۔
> - OGDC (آئی جی ڈی سی) "Rs. 306.12" پر 41 شیئر، بریک ایون قیمت "Rs. 307.24"۔
> - HUBC (ہب پاور) "Rs. 200.15" پر 59 شیئر، بریک ایون قیمت "Rs. 200.88"۔
> - PSO (پی ایس او) "Rs. 360.66" پر 32 شیئر، بریک ایون قیمت "Rs. 361.98"۔
> - MEBL (میزان بینک) "Rs. 548.45" پر 21 شیئر، بریک ایون قیمت "Rs. 550.45"۔
> - HBL (حبیب بینک) "Rs. 295.76" پر 36 شیئر، بریک ایون قیمت "Rs. 296.84"۔
>
> ہر اسٹاک کے لیے forecast (اگلے ٹریڈنگ دن) کم اعتماد والی ہے (low confidence) اور ماڈل نے naive baseline سے بہتر کارکردگی نہیں دکھائی؛ اس لیے یہ پیش گوئیاں صرف امکان پر مبنی ہیں اور غلط بھی ہو سکتی ہیں۔
>
> مختصراً، آپ کا پورٹ فولیو متوازن رسک کے ساتھ اچھا سالانہ منافع دکھا رہا ہے، لیکن موجودہ پیش گوئیاں کم اعتماد والی ہیں۔ اگر مزید تفصیل یا کسی خاص اسٹاک کی معلومات چاہیں تو بتائیں۔

Figure check: **passed** · sources: ['portfolio', 'backtest', 'prediction:MARI', 'prediction:EFERT', 'prediction:FFC', 'prediction:OGDC', 'prediction:HUBC', 'prediction:PSO', 'prediction:MEBL', 'prediction:HBL'] · 53129 ms (after 50.3 s waiting for Groq's token window) · tokens 6086/685

- Draft 1: `groq:openai/gpt-oss-120b` · cut off at the token limit: False · figures not in the context: [] · numbers in words: []

Automatic verdict: **pass**

## (f) Roman Urdu — `groq:openai/gpt-oss-120b`, run 1

**Question (ur-latn):** mera portfolio kaisa hai? kitne paise lage?

**Reply:**

> Aap ka portfolio moderate risk category ka hai. Aap ne total Rs. 100,000.00 ka capital allocate kiya tha.
>
> - Jo stocks aap ne kharide hain unka bought value Rs. 99,813.88 hai.
> - Iske upar buying charges Rs. 181.00 lagti hain, isliye total cost Rs. 99,994.88 ho gaya.
>
> Ab portfolio me Rs. 5.12 cash left hai.
>
> Har holding ka break‑even price, charges aur dividend details aap ke portfolio screen par milenge agar aap detail dekhna chahein.

Figure check: **passed** · sources: ['portfolio', 'backtest'] · 58018 ms (after 55.7 s waiting for Groq's token window) · tokens 5818/206

- Draft 1: `groq:openai/gpt-oss-120b` · cut off at the token limit: False · figures not in the context: [] · numbers in words: []

Automatic verdict: **pass**

## (g) Follow-up that depends on the previous answer — `groq:openai/gpt-oss-120b`, run 1

**Question (en):** Which of my holdings has the lowest forecast confidence?

**Reply:**

> The holdings with the lowest forecast confidence are the ones where the model gave a 49 % confidence level:
>
> - Mari Energies Limited (ticker MARI) – forecast confidence 49 %
> - Engro Fertilizers Limited (ticker EFERT) – forecast confidence 49 %
> - Fauji Fertilizer Company Limited (ticker FFC) – forecast confidence 49 %
> - The Hub Power Company Limited (ticker HUBC) – forecast confidence 49 %
> - Meezan Bank Limited (ticker MEBL) – forecast confidence 49 %
>
> All of these forecasts are marked as low‑confidence, meaning the model’s confidence is below the 60 % threshold and it did not outperform a simple “tomorrow’s price equals today’s” baseline. Forecasts are probabilistic and may be wrong.

Figure check: **passed** · sources: ['portfolio', 'prediction:MARI', 'prediction:EFERT', 'prediction:FFC', 'prediction:HUBC', 'prediction:MEBL'] · 54678 ms (after 52.3 s waiting for Groq's token window) · tokens 5796/267

- Draft 1: `groq:openai/gpt-oss-120b` · cut off at the token limit: False · figures not in the context: [] · numbers in words: []

**Question (en):** and the second lowest one?

**Reply:**

> The next‑to‑worst position in your portfolio, based on the forecast‑sale net return, is Fauji Fertilizer Company Limited (FFC).
>
> - Current price (as of 2026‑10‑09): Rs. 534.86
> - Forecast price for the next trading day: Rs. 534.16 (forecast used when the portfolio was generated)
> - If you sold at that forecast price, the net return would be Rs. ‑63.31, which is a ‑0.49% net‑return‑pct after charges.
>
> Remember, this forecast is low‑confidence (49 % confidence) and did not beat a naïve “tomorrow = today” baseline, so the prediction is probabilistic and may be wrong.

Figure check: **passed** · sources: ['portfolio', 'prediction:FFC'] · 51682 ms (after 49.6 s waiting for Groq's token window) · tokens 5792/329

- Draft 1: `groq:openai/gpt-oss-120b` · cut off at the token limit: False · figures not in the context: [] · numbers in words: []

Automatic verdict: **fail** — follow-up does not name ['OGDC']; confidence groups, lowest first: [['EFERT', 'FFC', 'HUBC', 'MARI', 'MEBL'], ['OGDC'], ['HBL']]
