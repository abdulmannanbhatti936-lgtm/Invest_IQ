# Model evaluation: lstm-rf-20261009T222331Z

Dataset `psx18-2026-10-07`: 18 KSE-100 stocks (ATRL, DGKC, EFERT, FFC, HBL, HUBC, LUCK, MARI, MEBL, MLCF, NBP, OGDC, PAEL, PPL, PSO, SAZEW, SYS, UBL), served Yahoo `.KA` daily bars, split-adjusted (`split-v1`) and dividend-adjusted for the model (`div-v1`).

Chronological split with the same cut dates for every stock (the row at each boundary is purged):

| Period | From | To | Rows | LSTM windows |
|---|---:|---:|---:|---:|
| train | 2021-12-17 | 2025-04-25 | 14808 | 13746 |
| val | 2025-04-29 | 2026-01-12 | 3142 | 3142 |
| test | 2026-01-14 | 2026-10-06 | 3151 | 3151 |

## Results against the PRD targets

PRD §11 targets are quoted unchanged. Each result is shown next to a simple baseline measured on the same test rows.

| Metric | PRD target | LSTM | Baseline |
|---|---:|---:|---:|
| RMSE, % of price | < 5% | 2.70% | 2.65% (tomorrow = today) |
| Directional accuracy | > 80% | 48.9% (95% CI 47.2%-50.7%) | 55.0% (always 'down') |
| Theil's U (RMSE / naive RMSE) | not in PRD | 1.019 | 1.000 |

**In plain words:**

- The LSTM's price forecast is **not** more accurate than simply assuming tomorrow's close equals today's (Theil's U 1.019; 1.000 = same as naive, Diebold-Mariano p = 0.084). Its 2.70% RMSE meets the PRD's < 5% target only because next-day prices rarely move more than a few percent: the naive guess meets it too (2.65%).
- The LSTM gets the next-day direction right 48.9% of the time (95% CI 47.2%-50.7%). That is not reliably better than always guessing 'down' (55.0%), and far from the PRD's 80% target. Day-to-day moves of liquid stocks are close to unpredictable from past prices alone (weak-form market efficiency); published next-day results are typically 50-60%.
- The Random Forest's balanced accuracy (40.9%) is above the majority-class baseline (33.3%): it does tell BUY, HOLD and SELL days apart a little. Its plain accuracy (42.8%) is still below always answering HOLD (44.0%), so the signal is weak and is shown only as a secondary indicator.
- 2.5% of test forecasts reach the 60% confidence threshold; the app flags every other forecast as low-confidence, and every forecast for a stock where the LSTM did not beat the naive guess.
- The confidence score did not hold up on the test period: its Brier score (0.2536) is no better than always saying 53.0% (0.2515). Higher scores did not mean more correct directions, which is consistent with the model having no reliable edge; the score is shown, but so is the low-confidence flag.

## LSTM price forecast (test period)

| Model | RMSE % | MAPE % | Theil's U | Direction | p vs majority |
|---|---:|---:|---:|---:|---:|
| LSTM | 2.702 | 1.859 | 1.019 | 48.9% | 1.000 |
| Naive (tomorrow = today) | 2.653 | 1.798 | 1.000 | n/a (no move) |  |
| 5-day moving average | 3.543 | 2.551 | 1.335 | 51.8% | 1.000 |
| 20-day trend rule |  |  |  | 50.9% | 1.000 |
| Majority direction ('down') |  |  |  | 55.0% |  |

Diebold-Mariano test vs naive (squared relative error, averaged across stocks per day, 176 days): statistic 1.728, p = 0.084 (negative = LSTM better). Directional accuracy counts only days where both the forecast and the price moved. Pooled rows are not independent (stocks move together), so intervals and p-values are optimistic.

## Confidence score (MC dropout + isotonic calibration)

Calibrated on the validation period, checked here on the test period. Brier score 0.2536 vs 0.2515 for a constant (validation hit rate); lower is better. 2.5% of test forecasts reach the 60% threshold; their direction was right 44.9% of the time (95% CI 34.3%-55.9%).

| Confidence band | Forecasts | Mean confidence | Direction right |
|---|---:|---:|---:|
| below 50% | 872 | 48.9% | 50.1% |
| 50% to 55% | 1736 | 53.4% | 50.3% |
| 55% to 60% | 463 | 55.4% | 42.3% |
| 60% to 65% | 76 | 62.9% | 44.7% |
| 65% and above | 2 | 79.4% | 50.0% |

## Random Forest buy/sell/hold signal (test period)

Labels: BUY if the next-day return is above +1%, SELL if below -1%, otherwise HOLD.

| Model | Accuracy | Balanced accuracy | Macro-F1 | Brier |
|---|---:|---:|---:|---:|
| Random Forest | 42.8% | 40.9% | 0.410 | 0.6392 |
| Majority class (HOLD) | 44.0% | 33.3% | 0.204 | 0.6564 |
| 20-day trend rule | 28.6% | 33.6% | 0.241 | n/a |

| Class | Precision | Recall | Test rows |
|---|---:|---:|---:|
| SELL | 31.3% | 34.8% | 952 |
| HOLD | 57.1% | 53.1% | 1385 |
| BUY | 35.1% | 34.8% | 814 |

Confusion matrix (rows = actual, columns = predicted):

| Actual \ Predicted | SELL | HOLD | BUY |
|---|---:|---:|---:|
| SELL | 331 | 322 | 299 |
| HOLD | 425 | 736 | 224 |
| BUY | 300 | 231 | 283 |

## Per stock (test period)

| Stock | Rows | LSTM RMSE % | Naive RMSE % | Theil's U | Beats naive | Direction | Majority dir. | RF acc. | Majority class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ATRL | 173 | 2.83 | 2.76 | 1.024 | no | 57.2% | 48.0% | 36.4% | 38.2% |
| DGKC | 175 | 3.25 | 3.22 | 1.010 | no | 51.4% | 54.3% | 37.7% | 32.0% |
| EFERT | 175 | 1.84 | 1.81 | 1.020 | no | 48.0% | 58.3% | 50.3% | 57.7% |
| FFC | 176 | 2.34 | 2.30 | 1.017 | no | 47.4% | 52.6% | 54.0% | 59.7% |
| HBL | 175 | 2.54 | 2.47 | 1.027 | no | 49.1% | 53.7% | 38.3% | 46.9% |
| HUBC | 175 | 2.44 | 2.36 | 1.034 | no | 41.7% | 57.1% | 41.1% | 52.0% |
| LUCK | 175 | 2.77 | 2.71 | 1.020 | no | 48.0% | 52.6% | 43.4% | 40.0% |
| MARI | 175 | 1.85 | 1.80 | 1.025 | no | 46.9% | 57.1% | 52.6% | 58.9% |
| MEBL | 175 | 2.31 | 2.24 | 1.032 | no | 44.0% | 53.7% | 44.0% | 46.9% |
| MLCF | 175 | 3.39 | 3.34 | 1.017 | no | 52.0% | 56.0% | 34.3% | 27.4% |
| NBP | 176 | 3.37 | 3.30 | 1.021 | no | 48.9% | 56.8% | 38.1% | 42.0% |
| OGDC | 176 | 2.27 | 2.22 | 1.022 | no | 44.9% | 50.0% | 44.9% | 47.2% |
| PAEL | 176 | 3.25 | 3.19 | 1.016 | no | 53.4% | 56.8% | 40.3% | 31.2% |
| PPL | 175 | 2.77 | 2.72 | 1.019 | no | 51.1% | 53.4% | 38.3% | 36.6% |
| PSO | 175 | 2.49 | 2.45 | 1.020 | no | 46.9% | 56.0% | 41.7% | 48.6% |
| SAZEW | 175 | 2.85 | 2.85 | 0.999 | yes | 52.0% | 62.3% | 49.7% | 44.6% |
| SYS | 174 | 2.53 | 2.47 | 1.024 | no | 47.7% | 55.7% | 43.1% | 44.3% |
| UBL | 175 | 2.87 | 2.85 | 1.007 | no | 50.3% | 56.0% | 42.9% | 37.1% |

## Walk-forward check (3 expanding folds)

| Fold test period | Rows | Theil's U | Direction | Majority dir. | DM p | RF bal. acc. | Majority class acc. | RF acc. | Share >= threshold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025-04-29 to 2025-10-21 | 2114 | 0.992 | 51.9% | 49.6% | 0.354 | 41.8% | 47.3% | 43.3% | 6.8% |
| 2025-10-22 to 2026-04-09 | 2108 | 1.017 | 50.5% | 54.1% | 0.211 | 42.6% | 41.2% | 43.5% | 3.2% |
| 2026-04-10 to 2026-10-06 | 2089 | 1.007 | 48.0% | 54.5% | 0.342 | 39.0% | 50.9% | 45.7% | 0.6% |
| Mean (std) |  | 1.006 (0.010) | 50.1% (1.6%) | 52.7% |  | 41.1% (1.5%) | 46.5% | 44.2% | 3.5% |

## Training run

CPU only. LSTM: 123.9 s, best epoch 8 of at most 60 (early stopping, patience 8). Random Forest: 3.6 s. Whole run including walk-forward: 480.1 s. Seed 42; library versions torch 2.14.0+cpu, sklearn 1.9.1, pandas 3.0.6, numpy 2.2.6.
