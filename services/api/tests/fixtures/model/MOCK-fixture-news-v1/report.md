# Model evaluation: MOCK-fixture-news-v1

Dataset `MOCK synthetic random walk (tests/synthetic.py)`: 3 KSE-100 stocks (MOCKA, MOCKB, MOCKC), served Yahoo `.KA` daily bars, split-adjusted (`split-v1`) and dividend-adjusted for the model (`div-v1`).

Chronological split with the same cut dates for every stock (the row at each boundary is purged):

| Period | From | To | Rows | LSTM windows |
|---|---:|---:|---:|---:|
| train | 2022-03-11 | 2023-12-06 | 1362 | 1185 |
| val | 2023-12-08 | 2024-04-22 | 291 | 291 |
| test | 2024-04-24 | 2024-09-05 | 291 | 291 |

## Results against the PRD targets

PRD §11 targets are quoted unchanged. Each result is shown next to a simple baseline measured on the same test rows.

| Metric | PRD target | LSTM | Baseline |
|---|---:|---:|---:|
| RMSE, % of price | < 5% | 1.55% | 1.54% (tomorrow = today) |
| Directional accuracy | > 80% | 50.9% (95% CI 45.1%-56.6%) | 49.8% (always 'up') |
| Theil's U (RMSE / naive RMSE) | not in PRD | 1.002 | 1.000 |

**In plain words:**

- The LSTM's price forecast is **not** more accurate than simply assuming tomorrow's close equals today's (Theil's U 1.002; 1.000 = same as naive, Diebold-Mariano p = 0.381). Its 1.55% RMSE meets the PRD's < 5% target only because next-day prices rarely move more than a few percent: the naive guess meets it too (1.54%).
- The LSTM gets the next-day direction right 50.9% of the time (95% CI 45.1%-56.6%). That is not reliably better than always guessing 'up' (49.8%), and far from the PRD's 80% target. Day-to-day moves of liquid stocks are close to unpredictable from past prices alone (weak-form market efficiency); published next-day results are typically 50-60%.
- The Random Forest's buy/sell/hold signal is not better than always answering HOLD (balanced accuracy 31.9% vs 33.3%).
- 0.0% of test forecasts reach the 60% confidence threshold; the app flags every other forecast as low-confidence, and every forecast for a stock where the LSTM did not beat the naive guess.
- The confidence score did not hold up on the test period: its Brier score (0.2505) is no better than always saying 49.5% (0.2501). Higher scores did not mean more correct directions, which is consistent with the model having no reliable edge; the score is shown, but so is the low-confidence flag.

## LSTM price forecast (test period)

| Model | RMSE % | MAPE % | Theil's U | Direction | p vs majority |
|---|---:|---:|---:|---:|---:|
| LSTM | 1.546 | 1.228 | 1.002 | 50.9% | 0.363 |
| Naive (tomorrow = today) | 1.543 | 1.226 | 1.000 | n/a (no move) |  |
| 5-day moving average | 2.335 | 1.851 | 1.513 | 50.5% | 0.407 |
| 20-day trend rule |  |  |  | 46.4% | 0.879 |
| Majority direction ('up') |  |  |  | 49.8% |  |

Diebold-Mariano test vs naive (squared relative error, averaged across stocks per day, 97 days): statistic 0.876, p = 0.381 (negative = LSTM better). Directional accuracy counts only days where both the forecast and the price moved. Pooled rows are not independent (stocks move together), so intervals and p-values are optimistic.

## Confidence score (MC dropout + isotonic calibration)

Calibrated on the validation period, checked here on the test period. Brier score 0.2505 vs 0.2501 for a constant (validation hit rate); lower is better. 0.0% of test forecasts reach the 60% threshold.

| Confidence band | Forecasts | Mean confidence | Direction right |
|---|---:|---:|---:|
| below 50% | 290 | 48.6% | 51.0% |
| 50% to 55% | 1 | 50.0% | 0.0% |
| 55% to 60% | 0 | n/a | n/a |
| 60% to 65% | 0 | n/a | n/a |
| 65% and above | 0 | n/a | n/a |

## Random Forest buy/sell/hold signal (test period)

Labels: BUY if the next-day return is above +1%, SELL if below -1%, otherwise HOLD.

`min_samples_leaf` was chosen from the grid declared before training, by balanced_accuracy on the validation period (each value fitted on the training period). The chosen value was then refitted on training + validation and scored on the test period once.

| min_samples_leaf | Validation balanced accuracy | Chosen |
|---|---:|---:|
| 5 | 36.3% | yes |
| 20 | 32.4% |  |

| Model | Accuracy | Balanced accuracy | Macro-F1 | Brier |
|---|---:|---:|---:|---:|
| Random Forest | 30.2% | 31.9% | 0.296 | 0.6713 |
| Majority class (HOLD) | 49.1% | 33.3% | 0.220 | 0.6289 |
| 20-day trend rule | 24.4% | 31.5% | 0.213 | n/a |

| Class | Precision | Recall | Test rows |
|---|---:|---:|---:|
| SELL | 25.0% | 46.4% | 69 |
| HOLD | 44.2% | 26.6% | 143 |
| BUY | 23.4% | 22.8% | 79 |

Confusion matrix (rows = actual, columns = predicted):

| Actual \ Predicted | SELL | HOLD | BUY |
|---|---:|---:|---:|
| SELL | 32 | 19 | 18 |
| HOLD | 64 | 38 | 41 |
| BUY | 32 | 29 | 18 |

## Per stock (test period)

| Stock | Rows | LSTM RMSE % | Naive RMSE % | Theil's U | Beats naive | Direction | Majority dir. | RF acc. | Majority class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MOCKA | 97 | 1.63 | 1.63 | 1.002 | no | 52.6% | 47.4% | 38.1% | 46.4% |
| MOCKB | 97 | 1.48 | 1.48 | 1.002 | no | 47.4% | 51.5% | 26.8% | 54.6% |
| MOCKC | 97 | 1.53 | 1.52 | 1.002 | no | 52.6% | 50.5% | 25.8% | 46.4% |

## Training run

CPU only. LSTM: 18.1 s, best epoch 2 of at most 2 (early stopping, patience 8). Random Forest: 1.3 s. Whole run including walk-forward: 22.0 s. Seed 42; library versions torch 2.14.0+cpu, sklearn 1.9.1, pandas 3.0.6, numpy 2.2.6.
