# PSX headline labeling (FinBERT evaluation, Phase 4)

`psx_headlines_labeling.csv` holds real headlines about the 18 stocks the model covers, drawn at random (fixed seed) from Profit (Pakistan Today) and Mettis Global, October 2021 to October 2026: 162 headlines, nine per stock. Only the headline, source, date and link are kept. They measure how well FinBERT scores PSX news, which a public benchmark cannot show (PRD target: accuracy above 85%).

## How this sheet was labelled (2026-10-11)

- label_A: human annotator (team member).
- label_B: an AI assistant (Claude), labelled independently before seeing A.
- 37 disagreements (agreement 77.2%, Cohen's kappa 0.62) were resolved by the human annotator with a written rule: completed actions (acquisitions, launches, signed stakes) = positive; announcements/MoUs/talks/requests = neutral. The human approved every final_label.
- The 7 rows with about_company = N are reported separately and excluded from sentiment accuracy.

The labels are never to be described as two human annotators. Results: `services/api/ml/reports/finbert_evaluation.md` (FinBERT 67.7% on the 155 headlines about the company, below the 85% target).

## Labelling guide

Do not edit `id`, `matched_ticker`, `source`, `published_date`, `headline` or `url`.

1. **`about_company`**: `Y` if the headline is mainly about the company in `matched_ticker`; `N` if it only mentions it (for example an index or event the company sponsors, a fund run by its asset-management arm, or a list of many companies).
2. **`label_A` / `label_B`**: `positive`, `negative` or `neutral`, judged **from the headline alone** (do not open the article: the model only sees the headline). Ask: would a shareholder of this company read this as good news, bad news, or neither?
   - **positive**: profit or sales up, dividend declared or raised, new discovery, rating upgrade, large order or contract, cost cut, approval received.
   - **negative**: profit or sales down, loss, fine or penalty, rating downgrade, plant shutdown, unpaid receivables or circular debt hurting the company, legal action against it.
   - **neutral**: appointments, meeting dates, routine notices, CSR or sponsorship, product launches with no performance information, mixed news (one good and one bad fact), or a headline that is unclear.
   - If you are unsure, choose `neutral` and write why in `notes`.
3. Label every row, including rows you marked `about_company = N`.

## What is reported

- Agreement between label_A and label_B (share and Cohen's kappa), before resolution.
- On rows with `about_company = Y`: accuracy and macro-F1 with 95% bootstrap intervals, per-class recall and the confusion matrix, for FinBERT alone, VADER alone, and FinBERT with the VADER fallback (the deployed setup).
- Share of `about_company = Y`: how often the ticker matching picks the right company (155 of 162). The `N` rows are listed separately.

With 162 headlines the accuracy interval is roughly plus or minus 6 points, so this set shows whether FinBERT is near the 85% target on PSX news, not a precise figure.
