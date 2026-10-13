# Model evaluation: MOCK-e2e-v1

Dataset `MOCK synthetic random walk (tests/synthetic.py)`: 6 KSE-100 stocks (MOCKE2EA, MOCKE2EB, MOCKE2EC, MOCKE2ED, MOCKE2EE, MOCKE2EF), served Yahoo `.KA` daily bars, split-adjusted (`split-v1`) and dividend-adjusted for the model (`div-v1`).

Chronological split with the same cut dates for every stock (the row at each boundary is purged):

| Period | From | To | Rows | LSTM windows |
|---|---:|---:|---:|---:|
| train | 2022-03-11 | 2023-12-06 | 2724 | 2370 |
| val | 2023-12-08 | 2024-04-22 | 582 | 582 |
| test | 2024-04-24 | 2024-09-05 | 582 | 582 |

## Results against the PRD targets

PRD §11 targets are quoted unchanged. Each result is shown next to a simple baseline measured on the same test rows.

| Metric | PRD target | LSTM | Baseline |
|---|---:|---:|---:|
| RMSE, % of price | < 5% | 1.51% | 1.50% (tomorrow = today) |
| Directional accuracy | > 80% | 50.7% (95% CI 46.6%-54.7%) | 50.7% (always 'up') |
| Theil's U (RMSE / naive RMSE) | not in PRD | 1.004 | 1.000 |

**In plain words:**

- The LSTM's price forecast is **not** more accurate than simply assuming tomorrow's close equals today's (Theil's U 1.004; 1.000 = same as naive, Diebold-Mariano p = 0.131). Its 1.51% RMSE meets the PRD's < 5% target only because next-day prices rarely move more than a few percent: the naive guess meets it too (1.50%).
- The LSTM gets the next-day direction right 50.7% of the time (95% CI 46.6%-54.7%). That is not reliably better than always guessing 'up' (50.7%), and far from the PRD's 80% target. Day-to-day moves of liquid stocks are close to unpredictable from past prices alone (weak-form market efficiency); published next-day results are typically 50-60%.
- The Random Forest's buy/sell/hold signal is not better than always answering HOLD (balanced accuracy 31.9% vs 33.3%).
- 1.0% of test forecasts reach the 60% confidence threshold; the app flags every other forecast as low-confidence, and every forecast for a stock where the LSTM did not beat the naive guess.
- The confidence score did not hold up on the test period: its Brier score (0.2523) is no better than always saying 49.7% (0.2501). Higher scores did not mean more correct directions, which is consistent with the model having no reliable edge; the score is shown, but so is the low-confidence flag.

## LSTM price forecast (test period)

| Model | RMSE % | MAPE % | Theil's U | Direction | p vs majority |
|---|---:|---:|---:|---:|---:|
| LSTM | 1.507 | 1.201 | 1.004 | 50.7% | 0.500 |
| Naive (tomorrow = today) | 1.501 | 1.200 | 1.000 | n/a (no move) |  |
| 5-day moving average | 2.325 | 1.899 | 1.549 | 45.9% | 0.990 |
| 20-day trend rule |  |  |  | 51.9% | 0.281 |
| Majority direction ('up') |  |  |  | 50.7% |  |

Diebold-Mariano test vs naive (squared relative error, averaged across stocks per day, 97 days): statistic 1.511, p = 0.131 (negative = LSTM better). Directional accuracy counts only days where both the forecast and the price moved. Pooled rows are not independent (stocks move together), so intervals and p-values are optimistic.

## Confidence score (MC dropout + isotonic calibration)

Calibrated on the validation period, checked here on the test period. Brier score 0.2523 vs 0.2501 for a constant (validation hit rate); lower is better. 1.0% of test forecasts reach the 60% threshold; their direction was right 66.7% of the time (95% CI 30.0%-90.3%).

| Confidence band | Forecasts | Mean confidence | Direction right |
|---|---:|---:|---:|
| below 50% | 337 | 48.0% | 51.0% |
| 50% to 55% | 239 | 51.5% | 49.8% |
| 55% to 60% | 0 | n/a | n/a |
| 60% to 65% | 0 | n/a | n/a |
| 65% and above | 6 | 100.0% | 66.7% |

## Random Forest buy/sell/hold signal (test period)

Labels: BUY if the next-day return is above +1%, SELL if below -1%, otherwise HOLD.

`min_samples_leaf` was chosen from the grid declared before training, by balanced_accuracy on the validation period (each value fitted on the training period). The chosen value was then refitted on training + validation and scored on the test period once.

| min_samples_leaf | Validation balanced accuracy | Chosen |
|---|---:|---:|
| 5 | 35.7% | yes |
| 20 | 30.3% |  |

| Model | Accuracy | Balanced accuracy | Macro-F1 | Brier |
|---|---:|---:|---:|---:|
| Random Forest | 33.8% | 31.9% | 0.315 | 0.6678 |
| Majority class (HOLD) | 50.2% | 33.3% | 0.223 | 0.6238 |
| 20-day trend rule | 26.3% | 35.2% | 0.234 | n/a |

| Class | Precision | Recall | Test rows |
|---|---:|---:|---:|
| SELL | 22.6% | 31.6% | 136 |
| HOLD | 46.6% | 40.1% | 292 |
| BUY | 26.2% | 24.0% | 154 |

Confusion matrix (rows = actual, columns = predicted):

| Actual \ Predicted | SELL | HOLD | BUY |
|---|---:|---:|---:|
| SELL | 43 | 58 | 35 |
| HOLD | 106 | 117 | 69 |
| BUY | 41 | 76 | 37 |

## Per stock (test period)

| Stock | Rows | LSTM RMSE % | Naive RMSE % | Theil's U | Beats naive | Direction | Majority dir. | RF acc. | Majority class |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| MOCKE2EA | 97 | 1.48 | 1.49 | 0.999 | yes | 53.6% | 53.6% | 37.1% | 49.5% |
| MOCKE2EB | 97 | 1.55 | 1.55 | 1.001 | no | 55.7% | 55.7% | 34.0% | 48.5% |
| MOCKE2EC | 97 | 1.73 | 1.71 | 1.013 | no | 40.2% | 40.2% | 35.1% | 43.3% |
| MOCKE2ED | 97 | 1.46 | 1.45 | 1.005 | no | 49.5% | 49.5% | 29.9% | 53.6% |
| MOCKE2EE | 97 | 1.31 | 1.31 | 1.000 | no | 46.4% | 46.4% | 32.0% | 53.6% |
| MOCKE2EF | 97 | 1.47 | 1.47 | 1.000 | no | 58.8% | 58.8% | 35.1% | 52.6% |

## Training run

CPU only. LSTM: 13.5 s, best epoch 1 of at most 2 (early stopping, patience 8). Random Forest: 0.7 s. Whole run including walk-forward: 15.8 s. Seed 42; library versions torch 2.14.0+cpu, sklearn 1.9.1, pandas 3.0.6, numpy 2.2.6.
