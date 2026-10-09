# How InvestIQ's prediction engine works

A plain-language walkthrough of Phase 3 for the viva: what data goes in, what the models do, how we tested them, what the confidence score means and how a forecast reaches the screen. The numbers are from model `lstm-rf-20261009T222331Z`, trained on 2026-10-10. The full evaluation report is `services/api/ml/reports/evaluation_lstm-rf-20261009T222331Z.md`.

## 1. Data

**Where it comes from.** Daily open, high, low, close and volume for PSX stocks from Yahoo Finance (`.KA` symbols), pulled by a background job into our database (`price_points`). The app never calls Yahoo while a user is waiting; it shows what is stored, with an "as of" date, because Yahoo runs one or two trading days behind PSX.

**Which stocks.** 18 of the most traded KSE-100 stocks across 11 sectors (oil and gas, banks, fertilizer, cement, power, refinery, technology, cables, autos). We ranked by median daily traded value over the last year and left out every stock whose history had an unexplained one-day jump of more than 10% (13 stocks), plus NCPL until a suspicious price is checked against PSX.

**Cleaning.** Two problems in Yahoo's PSX data had to be fixed before any model saw it:

- **Stock splits** are applied inconsistently by Yahoo. Our method `split-v1` (Phase 2) puts every bar on today's share basis and leaves out bars that match neither price level.
- **Dividends.** On the day a dividend is paid out, the share price drops by about the dividend, even though shareholders lost nothing: they received the cash. A model trained on raw prices would learn false losses. For training we use the standard "total return" adjustment (the same method Yahoo and CRSP use): every price before an ex-dividend date is scaled down by `1 - dividend / previous close`. Displayed prices are never adjusted. If the price drop on the ex-date is more than twice the dividend or less than half of it, the data may be wrong, so that adjustment is held back for review (73 of 195 dividends; mostly small ones where the normal daily move hides the dividend).

**Result:** dataset `psx18-2026-10-07`, 22,037 daily bars from 8 Oct 2021 to 7 Oct 2026, committed to the repository with a fingerprint (SHA-256) per file, so any training run can prove what it used.

## 2. Features (what the models look at)

For each stock and day we compute standard technical indicators: RSI (14 days), MACD (12/26/9), Bollinger Bands (20 days, 2 standard deviations) and 20- and 50-day moving averages, plus 1-, 5- and 20-day returns, 20-day volatility, the day's range and volume relative to its 20-day average.

Two rules make the features trustworthy:

- **Correct formulas.** We wrote the indicators ourselves (the TA-Lib library is hard to install on Windows and in CI), so we test them against numbers produced by TA-Lib itself on real OGDC prices, and against the published worked example of Wilder's RSI. They match.
- **No peeking at the future.** Every feature on day t uses only days up to t. A test rebuilds the features with the data cut off at day t and checks that nothing changes; it catches a "centered" moving average or a whole-history average if anyone adds one. Model inputs are ratios and returns, not prices, so the dividend adjustment (which rescales old prices) cannot leak information either.

## 3. Models

**LSTM (the forecast).** A recurrent neural network reads the last 60 trading days of features and predicts tomorrow's return. Layers: LSTM with 64 units, LSTM with 32 units, 20% dropout, one output. Forecast price = today's close x (1 + predicted return).

**Random Forest (the second opinion).** 300 decision trees vote on tomorrow: BUY (rise of more than 1%), SELL (fall of more than 1%) or HOLD. It also tells us which features mattered most (here: the day's high-low range, 20-day volatility and the last day's return).

**One model for all 18 stocks.** Because the inputs are scale-free, one model can learn from every stock at once: about 15,000 training examples instead of about 850 per stock. The SVM classifier named in the PRD was dropped so that one classifier could be evaluated properly.

**Reproducible.** Fixed random seed (42), and every saved file carries the model version. The training run logs the data range, every setting, every metric and how long it took (about 2 minutes for the LSTM and 8 minutes including the robustness check, on a laptop CPU).

## 4. Evaluation

**Split by time, never shuffled.** The first 70% of trading days (Dec 2021 to Apr 2025) train the models, the next 15% (Apr 2025 to Jan 2026) are for choosing when to stop training and for calibrating the confidence score, and the last 15% (Jan to Oct 2026, 3,151 forecasts) are a test the models never saw. All stocks use the same cut dates. The one day at each boundary is dropped, because its answer (tomorrow's price) lies in the next period.

**Compared with simple baselines,** on the same days:

- "Tomorrow's close = today's close" (naive)
- a 5-day moving average
- "up if above the 20-day average" (trend rule)
- always predicting the most common direction or class

**Walk-forward check.** The whole training is repeated three times with a growing history, each tested on a different later period, to see whether one lucky split explains the result.

**Results:**

| Metric                                                 | PRD target | Our model                    | Simple baseline          |
| ------------------------------------------------------ | ---------- | ---------------------------- | ------------------------ |
| Price error (RMSE, % of price)                         | < 5%       | 2.70%                        | 2.65% (tomorrow = today) |
| Theil's U (our error / naive error; below 1 is better) | —          | 1.019                        | 1.000                    |
| Next-day direction right                               | > 80%      | 48.9% (95% range 47.2-50.7%) | 55.0% (always "down")    |
| Buy/sell/hold accuracy                                 | —          | 42.8%                        | 44.0% (always HOLD)      |
| Buy/sell/hold balanced accuracy                        | —          | 40.9%                        | 33.3%                    |
| Walk-forward (3 periods)                               | —          | U 1.006, direction 50.1%     | direction 52.7%          |

**What this means.** The models do not beat simple baselines. The price error meets the PRD target, but only because a stock rarely moves more than a few percent in a day: guessing "no change" meets it too. Direction is right about half the time. The Random Forest separates the three classes a little better than chance, but is less accurate than always answering HOLD. A statistical test (Diebold-Mariano) finds no real difference from the naive forecast (p = 0.084).

## 5. Confidence score

The PRD asks for a confidence on every prediction and a visible flag below 60%. Ours answers one question: **"how likely is the forecast direction to be right?"**

1. The model is run 30 times with different neurons switched off at random ("Monte-Carlo dropout", always the same 30 patterns). If the 30 answers agree, the model is certain; if they scatter, it is not. Certainty = forecast / spread.
2. On the validation period we measured how often forecasts at each certainty level got the direction right, and fitted a rising curve through those rates (isotonic regression). Confidence = that curve's value.

On the test period this score did **not** separate good forecasts from bad ones: its Brier score (0.2536) was no better than always saying 53% (0.2515), and the 2.5% of forecasts above 60% were right only 44.9% of the time.

A forecast is shown as **low-confidence** if any of these hold:

- its confidence is below 60%;
- the Random Forest points the other way;
- the LSTM did not beat the naive forecast for that stock on the test period.

Today every forecast is flagged, and the screen lists the reasons.

## 6. From model to screen

1. **18:00** — the price job stores the day's bars.
2. **18:15** — the dividend job updates dividend events.
3. **18:30** — `run_predictions` loads the current model and computes tomorrow's forecast for each of the 18 stocks. Each forecast is stored with its confidence, signal, as-of date and model version.
4. **API.** `GET /stocks/{ticker}/prediction` reads the stored forecast. It never trains or runs a model, so it is fast. It returns the low-confidence reasons and the stock's test-period results. A stock outside the 18 gets "not covered".
5. **Screen.** The stock page shows:
   - the forecast as a dashed line with a shaded band of the model's typical error on that stock;
   - the forecast price and a plain sentence;
   - the confidence meter;
   - the low-confidence warning with its reasons;
   - the buy/sell/hold signal as a second opinion;
   - "How accurate has this model been for this stock?" with the baseline comparison;
   - the advisory disclaimer.

   All of it is in English and Urdu.

**Retraining** is scheduled weekly (PRD FR15): the job builds a new dataset version and trains a new model version; older forecasts are kept but only the current model's are shown.

## 7. Five questions an examiner is likely to ask

**1. Your PRD promised over 80% directional accuracy. You got 48.9%. Did the project fail?**
The model did not reach that target, and we report that directly instead of hiding it. The 80% figure was set before we had data; for next-day moves of liquid stocks, published studies usually report 50-60%, because prices already reflect public information (weak-form market efficiency). What the project does deliver is the system around the model: clean PSX data, a leak-free evaluation against baselines, and an app that tells the user honestly when a forecast should not be trusted. A strong result with no baseline would have been the real failure.

**2. Then why show a forecast at all?**
The PRD requires a forecast with a confidence score (FR11, FR14), and the stock page is where users expect it. We show it with every caution the PRD asks for: a low-confidence flag that lists its reasons, the model's own track record for that stock next to a simple baseline, a typical-error band on the chart, and the disclaimer. It is never presented as advice. Phase 4 adds news sentiment, which is the input most likely to add information that past prices do not have.

**3. How do you know there is no data leakage? Your 2.70% RMSE could be suspiciously good.**
Four safeguards, each tested:

- time-ordered splits with the same cut dates for all stocks, and the boundary rows dropped;
- the scaler fitted on the training period only (a test checks its stored means against the training rows);
- features that only look backwards (a test rebuilds them with future data removed);
- scale-free inputs, so the backward dividend adjustment cannot leak a future price level.

The 2.70% is not suspicious: the naive baseline gets 2.65%, and the low error simply reflects that daily moves are small.

**4. Why pool all 18 stocks into one model instead of one model per stock?**
Each stock has about 1,200 trading days, which leaves about 850 training examples: too few for an LSTM. The inputs are returns and ratios, so a pattern like "a high RSI after a sharp rise" means the same for a Rs.30 stock and a Rs.1,600 stock. Pooling gives about 15,000 examples. We still report every metric per stock, and one rule ("the model did not beat naive for this stock") flags forecasts per stock.

**5. Your confidence score did not work on the test set. Why keep it?**
Because it is built the right way and is checked honestly: Monte-Carlo dropout gives each forecast its own uncertainty, and the calibration is fitted on data the test never touches. That it shows no skill is a finding about the model, not a defect in the method: a model with no edge cannot have a meaningful "more sure" and "less sure". The app does not rely on the score alone; the other two low-confidence rules flag every current forecast. If a later model (for example with sentiment) gains real skill, the same calibration will show it on the reliability table.
