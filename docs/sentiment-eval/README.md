# PSX headline labeling (FinBERT evaluation, Phase 4)

`psx_headlines_labeling.csv` holds real headlines about the 18 stocks the model covers, drawn at random (fixed seed) from Profit (Pakistan Today) and Mettis Global, October 2021 to October 2026: 162 headlines, nine per stock. Only the headline, source, date and link are kept. They measure how well FinBERT scores PSX news, which a public benchmark cannot show (PRD target: accuracy above 85%).

## Who labels

Both team members label **every row, separately**. Do not look at each other's labels until both are done. Person A fills `label_A`, person B fills `label_B`. It takes about 30 to 40 minutes each.

## What to fill in

Do not edit `id`, `matched_ticker`, `source`, `published_date`, `headline` or `url`.

1. **`about_company`**: `Y` if the headline is mainly about the company in `matched_ticker`; `N` if it only mentions it (for example an index or event the company sponsors, a fund run by its asset-management arm, or a list of many companies).
2. **`label_A` / `label_B`**: `positive`, `negative` or `neutral`, judged **from the headline alone** (do not open the article: the model only sees the headline). Ask: would a shareholder of this company read this as good news, bad news, or neither?
   - **positive**: profit or sales up, dividend declared or raised, new discovery, rating upgrade, large order or contract, cost cut, approval received.
   - **negative**: profit or sales down, loss, fine or penalty, rating downgrade, plant shutdown, unpaid receivables or circular debt hurting the company, legal action against it.
   - **neutral**: appointments, meeting dates, routine notices, CSR or sponsorship, product launches with no performance information, mixed news (one good and one bad fact), or a headline that is unclear.
   - If you are unsure, choose `neutral` and write why in `notes`.
3. Label every row, including rows you marked `about_company = N`.

## After both of you finish

1. Put both columns in one file.
2. Go through every row where `label_A` and `label_B` differ, agree on one answer, and write it in `final_label`. Where they match, copy the label into `final_label`. Do not use the FinBERT output to settle a disagreement.
3. Return the file. Do not relabel anything after the FinBERT results have been shown.

## What will be reported

- Agreement between the two of you (Cohen's kappa), before discussion.
- On rows with `about_company = Y`: accuracy, macro-F1, per-class recall and the confusion matrix with a 95% bootstrap interval, for FinBERT alone, VADER alone, and FinBERT with the VADER fallback (the deployed setup).
- Share of `about_company = Y`: how often the ticker matching picks the right company.

With 162 headlines the accuracy interval is roughly plus or minus 6 points, so this set shows whether FinBERT is near the 85% target on PSX news, not a precise figure.
