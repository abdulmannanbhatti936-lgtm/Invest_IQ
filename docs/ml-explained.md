# How InvestIQ's prediction engine works

A plain-language walkthrough of Phase 3 for the viva: what data goes in, what the models do, how we tested them, what the confidence score means and how a forecast reaches the screen. The numbers are from model `lstm-rf-20261009T233529Z`, trained on 2026-10-10. The full evaluation report is `services/api/ml/reports/evaluation_lstm-rf-20261009T233529Z.md`.

## 1. Data

**Where it comes from.** Daily open, high, low, close and volume for PSX stocks from Yahoo Finance (`.KA` symbols), pulled by a background job into our database (`price_points`). The app never calls Yahoo while a user is waiting; it shows what is stored, with an "as of" date, because Yahoo runs one or two trading days behind PSX.

**Which stocks.** 18 of the most traded KSE-100 stocks across 10 sectors (oil and gas exploration, oil marketing, banks, fertilizer, cement, power, refinery, technology, cables, autos). We ranked by median daily traded value over the last year and left out every stock whose history had an unexplained one-day jump of more than 10% (13 stocks), plus NCPL until a suspicious price is checked against PSX.

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

**Random Forest (the second opinion).** 300 decision trees vote on tomorrow: BUY (rise of more than 1%), SELL (fall of more than 1%) or HOLD. It also tells us which features mattered most (here: the day's high-low range, 20-day volatility and the last day's return). One setting, the smallest number of examples a leaf may hold, was chosen from a list fixed before training (5, 10, 20 or 40) by how well each did on the validation period; 5 won (balanced accuracy 43.2%, against 42.5%, 42.7% and 42.8%). The test period played no part in the choice.

**One model for all 18 stocks.** Because the inputs are scale-free, one model can learn from every stock at once: 14,808 training examples instead of about 823 per stock. The SVM classifier named in the PRD was dropped so that one classifier could be evaluated properly.

**Reproducible.** Fixed random seed (42), and every saved file carries the model version. The training run logs the data range, every setting, every metric and how long it took (about 3 minutes for the LSTM and 11 minutes including the robustness check, on a laptop CPU). The LSTM settings are the starting point in the architecture document and were not tuned; only the stopping point is chosen, on the validation period.

## 4. Evaluation

**Split by time, never shuffled.** The first 70% of trading days (Dec 2021 to Apr 2025) train the models, the next 15% (Apr 2025 to Jan 2026) are for choosing when to stop training, choosing the Random Forest's leaf size and calibrating the confidence score, and the last 15% (Jan to Oct 2026, 3,151 forecasts) are a test the models never saw. All stocks use the same cut dates. The one day at each boundary is dropped, because its answer (tomorrow's price) lies in the next period.

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

**Retraining** is scheduled weekly (PRD FR15), but it never replaces the live model by itself. The job builds a new dataset and trains a _candidate_ with its full evaluation report, kept outside the repository. A person promotes a candidate with `python -m ml.promote <version>`; the command refuses a candidate without a complete report, keeps the earlier models next to the new one and logs every promotion. Older forecasts are kept, but only the current model's are shown.

## 8. News sentiment (Phase 4)

**What it is.** InvestIQ reads the headlines Pakistani business news sites publish about each of the 18 stocks the models cover, scores each headline as positive, negative or neutral, and shows the result on the stock page next to the forecast. Only the headline, the source, the link and the time are kept; the article text is never stored, and the page shows the headline with a link to the source.

**Where the headlines come from.** Profit (Pakistan Today) and Mettis Global give the history back to September 2021 and the live feed. Business Recorder was also tried, but its public feeds carry almost only international wire news and never produced a single headline about one of our 18 stocks, so it is switched off (the code is kept in case a better feed turns up). The scraper identifies itself, obeys each site's robots.txt (also for any page a link redirects to), waits three seconds between requests and retries politely when a site is busy, waiting at least as long as the site asks. A headline is attached to a stock only when the stock's name or ticker appears in the article's link; a stock named only in the headline is not attached, so a passing mention does not count. Routine items that carry a company's name, such as NBP's daily exchange-rate notice, are left out, and a headline that clearly belongs to a different article than its link is not kept.

**How a headline is scored.** FinBERT is a language model trained on financial text. For each headline it gives the probability of positive, negative and neutral. The headline's label is the most likely of the three. What the forecasting model reads is a different number, the score: the probability of positive minus the probability of negative, from -1 to +1. The two can look different: a headline FinBERT thinks is 61% likely neutral, 31% positive and 8% negative is labelled neutral but has a score of +0.23, because it leans positive. That is why the stock page shows the label with its probability and keeps the score out of sight. When FinBERT is unsure (its top probability is below 50%) or the headline is three words or fewer, a simple word-list scorer called VADER is used instead (31 of 2,143 headlines). On Financial PhraseBank sentences that all annotators agreed on, FinBERT labels 97.2% correctly and VADER 57.1%. That figure is an upper bound, not a measure on unseen text, because FinBERT was fine-tuned on that data.

**How well FinBERT reads Pakistani headlines.** To measure it on our own news we labelled 162 real Profit and Mettis Global headlines (nine per stock, picked at random). The labels were made like this: label_A by a human annotator (a team member); label_B by an AI assistant (Claude), labelled independently before seeing A. The two disagreed on 37 headlines (agreement 77.2%, Cohen's kappa 0.62); the human annotator resolved each one with a written rule (completed actions such as acquisitions, launches and signed stakes count as positive; announcements, MoUs, talks and requests as neutral) and approved every final label. Seven headlines turned out not to be about the matched company, so they are reported separately and left out of the accuracy: the stock matching was right for 155 of 162 (95.7%). On those 155, FinBERT gets **67.7%** right (95% interval 60.0%-75.5%; macro-F1 0.711), VADER alone 60.0%, and the setup the app uses (FinBERT with the VADER fallback) 67.1%. That is **well below the 85% target**. FinBERT is very good at spotting bad news (21 of 22 negative headlines) but calls 29 of 76 positive headlines neutral: it is cautious about headlines that report an action, such as a stake bought or a product launched, which our rule counts as good news. Full tables, including the confusion matrices, are in `ml/reports/finbert_evaluation.md`.

**What the stock page shows.** A badge (positive, negative, neutral, or "no news") and a "What's driving this" list of the headlines counted, each with its source, date, weight and FinBERT's label with how sure FinBERT is of it, for example "Neutral, 61%". A headline that VADER scored shows its label and says so. The -1 to +1 score is not shown. Headlines from the last 10 trading days count, and a headline's weight halves every 3 trading days. A headline published after the market closes counts for the next trading day: after 15:30, or after the earlier close PSX uses in Ramadan (13:30 Monday to Thursday and 12:30 on Friday in 2023-2026; 14:00 and 13:00 in 2022). If either Profit or Mettis has not been read successfully for 24 hours, the page says the sentiment may be out of date.

**Does it help the forecast? (the with and without test).** Before running anything we wrote down the test: train the same models twice, once with the two news inputs (how much recent news there is, and its average tone) and once without, using the same data, dates and settings, and promote the news version only if it is better on the validation period for both the price model and the buy/sell/hold model. We ran it twice with that same rule: first on 2,164 headlines, then, after an audit corrected the matching and the Ramadan close times, on the corrected 2,143.

|                                                                | First run (`news18-2026-10-09`) | Re-run (`news18-2026-10-09-r2`) |
| -------------------------------------------------------------- | ------------------------------- | ------------------------------- |
| Validation price error, news vs price only                     | 2.263% vs 2.274% (better)       | 2.263% vs 2.274% (better)       |
| Validation buy/sell/hold balanced accuracy, news vs price only | 43.1% vs 43.2% (not better)     | 43.0% vs 43.2% (not better)     |
| Decision                                                       | not promoted                    | not promoted                    |
| Test price error, news vs price only (no change: 2.653%)       | 2.687% vs 2.702%                | 2.686% vs 2.702%                |
| Test balanced accuracy, news vs price only                     | 40.9% vs 40.9%                  | 40.8% vs 40.9%                  |

Both times the news version predicted the next day's price slightly better on validation but the buy/sell/hold model was not better, so the news version was **not promoted** and the live model is unchanged. On the test period the differences are tiny, neither version beats simply assuming no change, and the news inputs are the two least used by the Random Forest. Switching the news off does change some of the news model's test forecasts (in the re-run, 34 buy/sell/hold signals and 215 price directions out of 1,708 days with news), which is how sentiment measurably changes a prediction, but only in the candidate model, not in the forecast users see. We also did the same at a five-trading-day horizon as a pre-declared extra: on validation the news version was again not better on both measures; on the test period it was slightly better on both (price error 5.447% against 5.518%, balanced accuracy 38.5% against 38.0% in the re-run), but neither version beats assuming no change (5.189%), and the five-day models are never served. Plain reading: in this data, headline tone adds almost nothing to the forecast. About 54% of stock-days in the test period had any news in the window, and for the stocks with few headlines (for example PAEL and DGKC) there is little to learn from.

**If the news sources are down.** A model that uses news falls back to its price-only twin when either source has not been read for 24 hours (one missing source would make the news input look quieter than it is), and the forecast is flagged with the reason "sentiment unavailable". If that price-only model is missing, the daily prediction run stops and says so, and the page keeps the last forecast with its date. The live model does not read news, so today this only matters if a news model is promoted later; the fallback and its tests are in place.

**Why show sentiment if it does not help the forecast.** It is context for the reader, labelled as such: the forecast panel says it uses prices only, and the sentiment panel says it describes the tone of recent news, not where the price will go.

## 9. Five questions an examiner is likely to ask

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
Each stock has about 1,200 trading days, which leaves about 823 training examples: too few for an LSTM. The inputs are returns and ratios, so a pattern like "a high RSI after a sharp rise" means the same for a Rs.30 stock and a Rs.1,600 stock. Pooling gives 14,808 examples. We still report every metric per stock, and one rule ("the model did not beat naive for this stock") flags forecasts per stock.

**5. Your confidence score did not work on the test set. Why keep it?**
Because it is built the right way and is checked honestly: Monte-Carlo dropout gives each forecast its own uncertainty, and the calibration is fitted on data the test never touches. That it shows no skill is a finding about the model, not a defect in the method: a model with no edge cannot have a meaningful "more sure" and "less sure". The app does not rely on the score alone: two other rules can flag a forecast. Today the "did not beat the naive forecast" rule flags 17 of the 18 stocks and the disagreement rule flags 2; SAZEW, the one stock where the LSTM narrowly beat naive, is flagged only because its confidence is below 60%. If a later model (for example with sentiment) gains real skill, the same calibration will show it on the reliability table.
