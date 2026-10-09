"""
The evaluation report written next to every trained model (`report.md`). It is rendered from
the model's metadata only, so the same file can be regenerated from a saved artifact. A
candidate without this report cannot be promoted (ml/promote.py).
"""

from pathlib import Path

from ml.features import CLASS_ORDER, SIGNAL_LABELS

REPORT_FILE = "report.md"

# PRD.md §11 targets, quoted unchanged; the report states what each is measured against
PRD_RMSE_TARGET_PCT = 5.0
PRD_DIRECTION_TARGET = 0.80


def _pct(x: float | None, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def _with_ci(summary: dict) -> str:
    low, high = _pct(summary["ci95_low"]), _pct(summary["ci95_high"])
    return f"{_pct(summary['directional_accuracy'])} (95% CI {low}-{high})"


def _band(band: list) -> str:
    low, high = band
    if low is None:
        return f"below {_pct(high, 0)}"
    if high is None:
        return f"{_pct(low, 0)} and above"
    return f"{_pct(low, 0)} to {_pct(high, 0)}"


def _mean_std(wf: dict, key: str) -> str:
    return f"{_pct(wf['mean'][key])} ({_pct(wf['std'][key])})"


def _verdicts(ev: dict, constant_confidence: float) -> list[str]:
    lstm, base = ev["lstm"], ev["baselines"]
    direction = lstm["direction"]
    dm = lstm["diebold_mariano_vs_naive"]
    majority = base["majority_direction"]["directional_accuracy"]
    rf, majority_class = ev["random_forest"], base["majority_class"]
    lines = []
    if lstm["theil_u"] < 1 and dm["p_value"] < 0.05:
        lines.append(
            f"The LSTM's price forecast is more accurate than 'tomorrow = today' "
            f"(Theil's U {lstm['theil_u']:.3f}, Diebold-Mariano p = {dm['p_value']:.3f})."
        )
    else:
        lines.append(
            f"The LSTM's price forecast is **not** more accurate than simply assuming tomorrow's "
            f"close equals today's (Theil's U {lstm['theil_u']:.3f}; 1.000 = same as naive, "
            f"Diebold-Mariano p = {dm['p_value']:.3f}). Its {lstm['rmse_pct']:.2f}% RMSE meets the "
            f"PRD's < {PRD_RMSE_TARGET_PCT:.0f}% target only because next-day prices rarely move "
            f"more than a few percent: the naive guess meets it too "
            f"({base['naive']['rmse_pct']:.2f}%)."
        )
    if direction["ci95_low"] > majority:
        lines.append(
            f"The LSTM gets the direction right {_pct(direction['directional_accuracy'])} of the "
            f"time (95% CI {_pct(direction['ci95_low'])}-{_pct(direction['ci95_high'])}), above "
            f"always guessing '{base['majority_direction']['direction']}' ({_pct(majority)})."
        )
    else:
        lines.append(
            f"The LSTM gets the next-day direction right {_pct(direction['directional_accuracy'])} "
            f"of the time (95% CI {_pct(direction['ci95_low'])}-{_pct(direction['ci95_high'])}). "
            f"That is not reliably better than always guessing "
            f"'{base['majority_direction']['direction']}' ({_pct(majority)}), and far from the "
            f"PRD's {PRD_DIRECTION_TARGET:.0%} target. Day-to-day moves of liquid stocks are "
            f"close to unpredictable from past prices alone (weak-form market efficiency); "
            f"published next-day results are typically 50-60%."
        )
    if rf["balanced_accuracy"] > majority_class["balanced_accuracy"] + 0.02:
        lines.append(
            f"The Random Forest's balanced accuracy ({_pct(rf['balanced_accuracy'])}) is above "
            f"the majority-class baseline ({_pct(majority_class['balanced_accuracy'])}): it does "
            f"tell BUY, HOLD and SELL days apart a little. "
            + (
                f"Its plain accuracy ({_pct(rf['accuracy'])}) is still below always answering "
                f"{majority_class['label']} ({_pct(majority_class['accuracy'])}), so the signal is "
                f"weak and is shown only as a secondary indicator."
                if rf["accuracy"] < majority_class["accuracy"]
                else f"Its plain accuracy ({_pct(rf['accuracy'])}) vs "
                f"{_pct(majority_class['accuracy'])} for always answering "
                f"{majority_class['label']} shows how small the edge is."
            )
        )
    else:
        lines.append(
            f"The Random Forest's buy/sell/hold signal is not better than always answering "
            f"{majority_class['label']} (balanced accuracy {_pct(rf['balanced_accuracy'])} vs "
            f"{_pct(majority_class['balanced_accuracy'])})."
        )
    conf = ev["confidence"]
    lines.append(
        f"{_pct(conf['share_at_or_above_threshold'])} of test forecasts reach the "
        f"{conf['threshold']:.0%} confidence threshold; the app flags every other forecast as "
        f"low-confidence, and every forecast for a stock where the LSTM did not beat the naive "
        f"guess."
    )
    if conf["brier"] >= conf["brier_constant_baseline"]:
        lines.append(
            f"The confidence score did not hold up on the test period: its Brier score "
            f"({conf['brier']:.4f}) is no better than always saying "
            f"{_pct(constant_confidence)} ({conf['brier_constant_baseline']:.4f}). Higher "
            f"scores did not mean more correct directions, which is consistent with the model "
            f"having no reliable edge; the score is shown, but so is the low-confidence flag."
        )
    return lines


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" if i == 0 else "---:" for i in range(len(header))) + "|",
        *["| " + " | ".join(row) + " |" for row in rows],
    ]


def _rf_selection(meta: dict) -> list[str]:
    """The pre-declared grid with every validation score, so the choice can be checked."""
    selection = meta["lstm"]["training"]["rf_selection"]
    (name,) = meta["random_forest"]["grid"]
    chosen = meta["random_forest"]["hyperparameters"][name]
    score_key = next(k for k in selection["grid"][0] if k != name)
    return [
        f"`{name}` was chosen from the grid declared before training, by {selection['metric']} "
        f"(each value fitted on the training period). The chosen value was then refitted on "
        f"training + validation and scored on the test period once.",
        "",
        *_table(
            [name, "Validation balanced accuracy", "Chosen"],
            [
                [str(s[name]), _pct(s[score_key]), "yes" if s[name] == chosen else ""]
                for s in selection["grid"]
            ],
        ),
        "",
    ]


def write_report(meta: dict, path: Path) -> Path:
    version = meta["model_version"]
    ev, data = meta["evaluation"], meta["data"]
    lstm, base, rf, conf = ev["lstm"], ev["baselines"], ev["random_forest"], ev["confidence"]
    majority = base["majority_direction"]
    periods = data["periods"]
    labels = [SIGNAL_LABELS[c] for c in CLASS_ORDER]

    out = [
        f"# Model evaluation: {version}",
        "",
        f"Dataset `{meta['dataset']['version']}`: {len(meta['tickers'])} KSE-100 stocks "
        f"({', '.join(meta['tickers'])}), served Yahoo `.KA` daily bars, split-adjusted "
        f"(`split-v1`) and dividend-adjusted for the model (`div-v1`).",
        "",
        "Chronological split with the same cut dates for every stock "
        "(the row at each boundary is purged):",
        "",
        *_table(
            ["Period", "From", "To", "Rows", "LSTM windows"],
            [
                [
                    p,
                    periods[p]["first_date"],
                    periods[p]["last_date"],
                    str(periods[p]["rows"]),
                    str(periods[p]["lstm_windows"]),
                ]
                for p in ("train", "val", "test")
            ],
        ),
        "",
        "## Results against the PRD targets",
        "",
        "PRD §11 targets are quoted unchanged. Each result is shown next to a simple baseline "
        "measured on the same test rows.",
        "",
        *_table(
            ["Metric", "PRD target", "LSTM", "Baseline"],
            [
                [
                    "RMSE, % of price",
                    f"< {PRD_RMSE_TARGET_PCT:.0f}%",
                    f"{lstm['rmse_pct']:.2f}%",
                    f"{base['naive']['rmse_pct']:.2f}% (tomorrow = today)",
                ],
                [
                    "Directional accuracy",
                    f"> {PRD_DIRECTION_TARGET:.0%}",
                    _with_ci(lstm["direction"]),
                    f"{_pct(majority['directional_accuracy'])} (always '{majority['direction']}')",
                ],
                ["Theil's U (RMSE / naive RMSE)", "not in PRD", f"{lstm['theil_u']:.3f}", "1.000"],
            ],
        ),
        "",
        "**In plain words:**",
        "",
        *[
            f"- {line}"
            for line in _verdicts(ev, meta["lstm"]["training"]["val_direction_hit_rate"])
        ],
        "",
        "## LSTM price forecast (test period)",
        "",
        *_table(
            ["Model", "RMSE %", "MAPE %", "Theil's U", "Direction", "p vs majority"],
            [
                [
                    "LSTM",
                    f"{lstm['rmse_pct']:.3f}",
                    f"{lstm['mape_pct']:.3f}",
                    f"{lstm['theil_u']:.3f}",
                    _pct(lstm["direction"]["directional_accuracy"]),
                    f"{lstm['direction']['p_value_vs_baseline']:.3f}",
                ],
                [
                    "Naive (tomorrow = today)",
                    f"{base['naive']['rmse_pct']:.3f}",
                    f"{base['naive']['mape_pct']:.3f}",
                    "1.000",
                    "n/a (no move)",
                    "",
                ],
                [
                    "5-day moving average",
                    f"{base['sma_5']['rmse_pct']:.3f}",
                    f"{base['sma_5']['mape_pct']:.3f}",
                    f"{base['sma_5']['theil_u']:.3f}",
                    _pct(base["sma_5"]["direction"]["directional_accuracy"]),
                    f"{base['sma_5']['direction']['p_value_vs_baseline']:.3f}",
                ],
                [
                    "20-day trend rule",
                    "",
                    "",
                    "",
                    _pct(base["sma_20_trend"]["direction"]["directional_accuracy"]),
                    f"{base['sma_20_trend']['direction']['p_value_vs_baseline']:.3f}",
                ],
                [
                    f"Majority direction ('{base['majority_direction']['direction']}')",
                    "",
                    "",
                    "",
                    _pct(base["majority_direction"]["directional_accuracy"]),
                    "",
                ],
            ],
        ),
        "",
        f"Diebold-Mariano test vs naive (squared relative error, averaged across stocks per day, "
        f"{lstm['diebold_mariano_vs_naive']['days']} days): statistic "
        f"{lstm['diebold_mariano_vs_naive']['statistic']:.3f}, p = "
        f"{lstm['diebold_mariano_vs_naive']['p_value']:.3f} (negative = LSTM better). "
        "Directional accuracy counts only days where both the forecast and the price moved. "
        "Pooled rows are not independent (stocks move together), so intervals and p-values "
        "are optimistic.",
        "",
        "## Confidence score (MC dropout + isotonic calibration)",
        "",
        f"Calibrated on the validation period, checked here on the test period. Brier score "
        f"{conf['brier']:.4f} vs {conf['brier_constant_baseline']:.4f} for a constant "
        f"(validation hit rate); lower is better. "
        f"{_pct(conf['share_at_or_above_threshold'])} of test forecasts reach the "
        f"{conf['threshold']:.0%} threshold"
        + (
            "; their direction was right "
            f"{_pct(conf['directional_accuracy_at_or_above_threshold'])}"
            f" of the time (95% CI {_pct(conf['ci95_at_or_above_threshold'][0])}-"
            f"{_pct(conf['ci95_at_or_above_threshold'][1])})."
            if conf["directional_accuracy_at_or_above_threshold"] is not None
            else "."
        ),
        "",
        *_table(
            ["Confidence band", "Forecasts", "Mean confidence", "Direction right"],
            [
                [
                    _band(r["band"]),
                    str(r["rows"]),
                    _pct(r["mean_confidence"]),
                    _pct(r["observed_hit_rate"]),
                ]
                for r in conf["reliability"]
            ],
        ),
        "",
        "## Random Forest buy/sell/hold signal (test period)",
        "",
        f"Labels: BUY if the next-day return is above +{data['label_threshold']:.0%}, SELL if "
        f"below -{data['label_threshold']:.0%}, otherwise HOLD.",
        "",
        *_rf_selection(meta),
        *_table(
            ["Model", "Accuracy", "Balanced accuracy", "Macro-F1", "Brier"],
            [
                [
                    "Random Forest",
                    _pct(rf["accuracy"]),
                    _pct(rf["balanced_accuracy"]),
                    f"{rf['f1_macro']:.3f}",
                    f"{rf['brier']:.4f}",
                ],
                [
                    f"Majority class ({base['majority_class']['label']})",
                    _pct(base["majority_class"]["accuracy"]),
                    _pct(base["majority_class"]["balanced_accuracy"]),
                    f"{base['majority_class']['f1_macro']:.3f}",
                    f"{base['majority_class']['brier']:.4f}",
                ],
                [
                    "20-day trend rule",
                    _pct(base["sma_20_trend"]["classifier"]["accuracy"]),
                    _pct(base["sma_20_trend"]["classifier"]["balanced_accuracy"]),
                    f"{base['sma_20_trend']['classifier']['f1_macro']:.3f}",
                    "n/a",
                ],
            ],
        ),
        "",
        *_table(
            ["Class", "Precision", "Recall", "Test rows"],
            [
                [SIGNAL_LABELS[int(k)], _pct(v["precision"]), _pct(v["recall"]), str(v["support"])]
                for k, v in rf["per_class"].items()
            ],
        ),
        "",
        "Confusion matrix (rows = actual, columns = predicted):",
        "",
        *_table(
            ["Actual \\ Predicted", *labels],
            [[labels[i], *map(str, row)] for i, row in enumerate(rf["confusion_matrix"])],
        ),
        "",
        "## Per stock (test period)",
        "",
        *_table(
            [
                "Stock",
                "Rows",
                "LSTM RMSE %",
                "Naive RMSE %",
                "Theil's U",
                "Beats naive",
                "Direction",
                "Majority dir.",
                "RF acc.",
                "Majority class",
            ],
            [
                [
                    t,
                    str(m["test_rows"]),
                    f"{m['lstm_rmse_pct']:.2f}",
                    f"{m['naive_rmse_pct']:.2f}",
                    f"{m['theil_u']:.3f}",
                    "yes" if m["beats_naive"] else "no",
                    _pct(m["directional_accuracy"]),
                    _pct(m["majority_direction_accuracy"]),
                    _pct(m["rf_accuracy"]),
                    _pct(m["rf_majority_class_accuracy"]),
                ]
                for t, m in ev["per_ticker"].items()
            ],
        ),
        "",
    ]
    wf = meta.get("walk_forward")
    if wf:
        out += [
            "## Walk-forward check (3 expanding folds)",
            "",
            *_table(
                [
                    "Fold test period",
                    "Rows",
                    "Theil's U",
                    "Direction",
                    "Majority dir.",
                    "DM p",
                    "RF bal. acc.",
                    "Majority class acc.",
                    "RF acc.",
                    "RF leaf",
                    "Share >= threshold",
                ],
                [
                    [
                        f"{f['test_first_date']} to {f['test_last_date']}",
                        str(f["test_rows"]),
                        f"{f['lstm_theil_u']:.3f}",
                        _pct(f["lstm_directional_accuracy"]),
                        _pct(f["majority_direction_accuracy"]),
                        f"{f['dm_p_value']:.3f}",
                        _pct(f["rf_balanced_accuracy"]),
                        _pct(f["majority_class_accuracy"]),
                        _pct(f["rf_accuracy"]),
                        str(f["rf_params"]["min_samples_leaf"]),
                        _pct(f["share_at_or_above_threshold"]),
                    ]
                    for f in wf["folds"]
                ]
                + [
                    [
                        "Mean (std)",
                        "",
                        f"{wf['mean']['lstm_theil_u']:.3f} ({wf['std']['lstm_theil_u']:.3f})",
                        _mean_std(wf, "lstm_directional_accuracy"),
                        _pct(wf["mean"]["majority_direction_accuracy"]),
                        "",
                        _mean_std(wf, "rf_balanced_accuracy"),
                        _pct(wf["mean"]["majority_class_accuracy"]),
                        _pct(wf["mean"]["rf_accuracy"]),
                        "",
                        _pct(wf["mean"]["share_at_or_above_threshold"]),
                    ]
                ],
            ),
            "",
        ]
    training = meta["lstm"]["training"]
    out += [
        "## Training run",
        "",
        f"CPU only. LSTM: {training['lstm_seconds']} s, best epoch {training['best_epoch']} of at "
        f"most {meta['lstm']['hyperparameters']['max_epochs']} (early stopping, patience "
        f"{meta['lstm']['hyperparameters']['early_stopping_patience']}). Random Forest: "
        f"{training['random_forest_seconds']} s. "
        f"Whole run including walk-forward: {meta['training_seconds_total']} s. "
        f"Seed {meta['seed']}; "
        f"library versions {', '.join(f'{k} {v}' for k, v in meta['library_versions'].items())}.",
        "",
    ]
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")
    return path
