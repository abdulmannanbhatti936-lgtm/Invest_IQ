"""
Training and evaluation of the pooled LSTM forecaster and Random Forest signal classifier
(Workflow.md Steps 3.4-3.5, Architecture.md §15). Training never runs inside an HTTP
request (Rules.md §3.5): it runs from the `ml.train` CLI or the weekly Celery job.

One model of each kind is trained on all tickers together ("pooled"): the inputs are
scale-free, and pooling gives ~15,000 training rows instead of ~850 per stock. Evaluation:
- chronological 70/15/15 split with the same cut dates for every ticker; the row at each
  boundary is purged (ml/splits.py); the scaler and the target scale are fitted on the
  training period only;
- the LSTM is compared with "tomorrow = today" (naive) and a 5-day moving average, and its
  direction with the training-period majority direction and a 20-day trend rule;
- the Random Forest is compared with the majority class and the same trend rule;
- a 3-fold expanding walk-forward repeats the whole fit to show how stable the result is.
The SVM classifier was dropped (decision 2026-10-10): one well-evaluated classifier.
"""

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from core.config import settings
from ml import lstm_model, metrics
from ml.confidence import MC_PASSES, MC_SEED, DirectionCalibrator, certainty
from ml.dataset import dividend_adjusted
from ml.features import FEATURE_COLUMNS, SIGNAL_LABELS, SIGNAL_THRESHOLD, build_feature_frame
from ml.splits import CutDates, assign_periods, shared_cut_dates, walk_forward_folds

logger = logging.getLogger(__name__)

SEED = 42
SEQ_LENGTH = 60
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
WALK_FORWARD_FOLDS = 3
WALK_FORWARD_TEST_FRAC = 0.30
MIN_TRAINING_ROWS = 400  # per ticker, ~1.6 trading years after indicator warm-up
CONFIDENCE_BANDS = (0.50, 0.55, 0.60, 0.65)
CLASS_ORDER = [-1, 0, 1]  # SELL, HOLD, BUY

LSTM_HYPERPARAMS = {
    "seq_length": SEQ_LENGTH,
    "layers": "LSTM(64) -> LSTM(32) -> Dropout(0.2) -> Dense(1)",
    "target": "next-day return of the dividend-adjusted close, divided by its training std",
    "optimizer": "Adam",
    "lr": 1e-3,
    "batch_size": 64,
    "max_epochs": 60,
    "early_stopping_patience": 8,
    "mc_dropout_passes": MC_PASSES,
    "mc_dropout_seed": MC_SEED,
}
RF_PARAMS = {
    "n_estimators": 300,
    "max_depth": 6,
    "min_samples_leaf": 20,
    "class_weight": "balanced_subsample",
    "random_state": SEED,
}


class InsufficientDataError(ValueError):
    pass


def new_model_version() -> str:
    return "lstm-rf-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def prepare_frames(raw: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Served bars with dividend factors -> the model's feature frame per ticker."""
    frames = {}
    for ticker, frame in raw.items():
        features = build_feature_frame(dividend_adjusted(frame))
        if features["target_return"].notna().sum() < MIN_TRAINING_ROWS:
            raise InsufficientDataError(
                f"{ticker}: {len(features)} usable rows, need at least {MIN_TRAINING_ROWS}"
            )
        # Baseline input only (5-day moving-average forecast); never a model feature
        features["sma_5"] = features["close"].rolling(5).mean()
        frames[ticker] = features
    return frames


def _samples(frames: dict[str, pd.DataFrame], cuts: CutDates) -> pd.DataFrame:
    """Every labelled row of every ticker with its period, ticker and row position."""
    parts = []
    for ticker, frame in frames.items():
        labelled = frame[frame["target_return"].notna()].copy()
        labelled["period"] = assign_periods(labelled["date"], cuts)
        labelled["ticker"] = ticker
        labelled["row"] = labelled.index
        parts.append(labelled)
    samples = pd.concat(parts, ignore_index=True)
    return samples[samples["period"].notna()].reset_index(drop=True)


def _windows(scaled: dict[str, np.ndarray], rows: pd.DataFrame) -> np.ndarray:
    return np.concatenate(
        [
            lstm_model.make_sequences(scaled[ticker], SEQ_LENGTH, group["row"].to_numpy())
            for ticker, group in rows.groupby("ticker", sort=False)
        ]
    )


def _by_ticker_order(rows: pd.DataFrame) -> pd.DataFrame:
    """Rows reordered the way `_windows` emits them (grouped by ticker, original order)."""
    return pd.concat([group for _, group in rows.groupby("ticker", sort=False)])


@dataclass
class FittedModels:
    scaler: StandardScaler
    y_std: float
    lstm: lstm_model.LSTMForecaster
    calibrator: DirectionCalibrator
    forest: RandomForestClassifier
    training: dict


def lstm_outputs(
    lstm: lstm_model.LSTMForecaster, y_std: float, windows: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Forecast return and its MC-dropout spread, in return units."""
    forecast = lstm_model.predict(lstm, windows) * y_std
    spread = lstm_model.mc_dropout_std(lstm, windows, MC_PASSES, MC_SEED) * y_std
    return forecast, spread


def fit_and_evaluate(
    frames: dict[str, pd.DataFrame],
    cuts: CutDates,
    *,
    lstm_epochs: int = LSTM_HYPERPARAMS["max_epochs"],
    rf_params: dict | None = None,
) -> tuple[FittedModels, dict, pd.DataFrame]:
    """Fit everything for one set of cut dates; return the models, metrics, test rows."""
    samples = _samples(frames, cuts)
    train = samples[samples["period"] == "train"]

    scaler = StandardScaler().fit(train[FEATURE_COLUMNS])
    y_std = float(train["target_return"].std())
    scaled = {
        ticker: scaler.transform(frame[FEATURE_COLUMNS]).astype(np.float32)
        for ticker, frame in frames.items()
    }

    # A window needs SEQ_LENGTH rows of history; earlier rows only feed the classifier
    windowed = _by_ticker_order(samples[samples["row"] >= SEQ_LENGTH - 1])
    lstm_rows = {p: windowed[windowed["period"] == p] for p in ("train", "val", "test")}
    X = {p: _windows(scaled, rows) for p, rows in lstm_rows.items()}
    y = {
        p: (rows["target_return"].to_numpy() / y_std).astype(np.float32)
        for p, rows in lstm_rows.items()
    }

    started = time.perf_counter()
    lstm, fit_info = lstm_model.train_lstm(
        X["train"],
        y["train"],
        X["val"],
        y["val"],
        epochs=lstm_epochs,
        batch_size=LSTM_HYPERPARAMS["batch_size"],
        lr=LSTM_HYPERPARAMS["lr"],
        patience=LSTM_HYPERPARAMS["early_stopping_patience"],
        seed=SEED,
    )
    lstm_seconds = time.perf_counter() - started

    val_forecast, val_spread = lstm_outputs(lstm, y_std, X["val"])
    val_actual = lstm_rows["val"]["target_return"].to_numpy()
    moved = (np.sign(val_forecast) != 0) & (np.sign(val_actual) != 0)
    calibrator = DirectionCalibrator().fit(
        certainty(val_forecast[moved], val_spread[moved]),
        np.sign(val_forecast[moved]) == np.sign(val_actual[moved]),
    )

    started = time.perf_counter()
    fit_rows = samples[samples["period"].isin(["train", "val"])]
    forest = RandomForestClassifier(**(rf_params or RF_PARAMS), n_jobs=-1).fit(
        fit_rows[FEATURE_COLUMNS].to_numpy(), fit_rows["target_signal"].astype(int).to_numpy()
    )
    forest_seconds = time.perf_counter() - started

    test = lstm_rows["test"].copy()
    test["forecast_return"], test["spread"] = lstm_outputs(lstm, y_std, X["test"])
    test["confidence"] = calibrator.predict(certainty(test["forecast_return"], test["spread"]))
    probabilities = forest.predict_proba(test[FEATURE_COLUMNS].to_numpy())
    classes = [int(c) for c in forest.classes_]
    for label in CLASS_ORDER:
        test[f"p_{label}"] = probabilities[:, classes.index(label)] if label in classes else 0.0
    test["rf_signal"] = np.array(classes)[np.argmax(probabilities, axis=1)]

    period_summary = {
        p: {
            "rows": int((samples["period"] == p).sum()),
            "lstm_windows": int(len(lstm_rows[p])),
            "first_date": samples.loc[samples["period"] == p, "date"].min().date().isoformat(),
            "last_date": samples.loc[samples["period"] == p, "date"].max().date().isoformat(),
        }
        for p in ("train", "val", "test")
    }
    training = {
        **fit_info,
        "lstm_seconds": round(lstm_seconds, 1),
        "random_forest_seconds": round(forest_seconds, 1),
        "y_std": y_std,
        "val_direction_hit_rate": float(
            np.mean(np.sign(val_forecast[moved]) == np.sign(val_actual[moved]))
        ),
    }
    models = FittedModels(scaler, y_std, lstm, calibrator, forest, training)
    evaluation = evaluate(test, train, training["val_direction_hit_rate"])
    evaluation["periods"] = period_summary
    return models, evaluation, test


def _majority_direction(train: pd.DataFrame) -> int:
    moved = train.loc[train["target_return"] != 0, "target_return"]
    return 1 if (moved > 0).mean() >= 0.5 else -1


def _ticker_lstm_summary(rows: pd.DataFrame, majority_direction: int) -> dict:
    actual = rows["next_close"].to_numpy()
    close = rows["close"].to_numpy()
    model = metrics.price_error_summary(close * (1 + rows["forecast_return"].to_numpy()), actual)
    naive = metrics.price_error_summary(close, actual)
    hits, n = metrics.direction_hits(
        rows["forecast_return"].to_numpy(), rows["target_return"].to_numpy()
    )
    base_hits, base_n = metrics.direction_hits(
        np.full(len(rows), majority_direction), rows["target_return"].to_numpy()
    )
    theil_u = model["rmse_pct"] / naive["rmse_pct"]
    return {
        "test_rows": int(len(rows)),
        **{f"lstm_{k}": v for k, v in model.items()},
        "naive_rmse_pct": naive["rmse_pct"],
        "theil_u": theil_u,
        "beats_naive": bool(theil_u < 1),
        "directional_accuracy": hits / n if n else None,
        "majority_direction_accuracy": base_hits / base_n if base_n else None,
        "rf_accuracy": float(np.mean(rows["rf_signal"] == rows["target_signal"])),
    }


def evaluate(test: pd.DataFrame, train: pd.DataFrame, val_hit_rate: float) -> dict:
    """Test-period metrics for both models and every baseline."""
    actual = test["next_close"].to_numpy()
    close = test["close"].to_numpy()
    target = test["target_return"].to_numpy()
    forecast = close * (1 + test["forecast_return"].to_numpy())

    lstm_err = metrics.price_error_summary(forecast, actual)
    naive_err = metrics.price_error_summary(close, actual)
    sma_err = metrics.price_error_summary(test["sma_5"].to_numpy(), actual)

    daily = (
        pd.DataFrame(
            {
                "date": test["date"].to_numpy(),
                "model": metrics.relative_errors(forecast, actual) ** 2,
                "naive": metrics.relative_errors(close, actual) ** 2,
            }
        )
        .groupby("date")[["model", "naive"]]
        .mean()
    )

    majority_direction = _majority_direction(train)
    base_hits, base_n = metrics.direction_hits(np.full(len(test), majority_direction), target)
    majority_rate = base_hits / base_n
    trend = np.where(close > test["SMA_20"].to_numpy(), 1, -1)
    sma_direction = np.sign(test["sma_5"].to_numpy() - close)

    hit = (np.sign(test["forecast_return"]) == np.sign(target)).to_numpy()
    moved = (np.sign(test["forecast_return"]) != 0).to_numpy() & (np.sign(target) != 0)
    confidence = test["confidence"].to_numpy()
    threshold = settings.LOW_CONFIDENCE_THRESHOLD
    confident = moved & (confidence >= threshold)
    confident_hits = int(hit[confident].sum())
    confident_ci = metrics.wilson_interval(confident_hits, int(confident.sum()))

    y_true = test["target_signal"].astype(int).to_numpy()
    probabilities = test[[f"p_{label}" for label in CLASS_ORDER]].to_numpy()
    class_freq = train["target_signal"].astype(int).value_counts(normalize=True)
    majority_class = int(class_freq.idxmax())
    majority_probs = np.tile([class_freq.get(label, 0.0) for label in CLASS_ORDER], (len(test), 1))

    per_ticker = {
        ticker: _ticker_lstm_summary(rows, majority_direction)
        for ticker, rows in test.groupby("ticker", sort=True)
    }
    for ticker, rows in test.groupby("ticker"):
        per_ticker[ticker]["rf_majority_class_accuracy"] = float(
            np.mean(rows["target_signal"].astype(int) == majority_class)
        )

    return {
        "lstm": {
            **lstm_err,
            "theil_u": lstm_err["rmse_pct"] / naive_err["rmse_pct"],
            "diebold_mariano_vs_naive": metrics.diebold_mariano(
                daily["model"].to_numpy(), daily["naive"].to_numpy()
            ),
            "direction": metrics.direction_summary(
                test["forecast_return"].to_numpy(), target, majority_rate
            ),
        },
        "baselines": {
            "naive": {**naive_err, "theil_u": 1.0},
            "sma_5": {
                **sma_err,
                "theil_u": sma_err["rmse_pct"] / naive_err["rmse_pct"],
                "direction": metrics.direction_summary(sma_direction, target, majority_rate),
            },
            "majority_direction": {
                "direction": "up" if majority_direction > 0 else "down",
                "directional_accuracy": majority_rate,
                "rows": base_n,
            },
            "sma_20_trend": {
                "direction": metrics.direction_summary(trend, target, majority_rate),
                "classifier": metrics.classification_summary(
                    y_true, trend, CLASS_ORDER, probabilities=None
                ),
            },
            "majority_class": {
                "label": SIGNAL_LABELS[majority_class],
                **metrics.classification_summary(
                    y_true, np.full(len(test), majority_class), CLASS_ORDER, majority_probs
                ),
            },
        },
        "confidence": {
            "threshold": threshold,
            "brier": metrics.brier(confidence[moved], hit[moved]),
            "brier_constant_baseline": metrics.brier(
                np.full(int(moved.sum()), val_hit_rate), hit[moved]
            ),
            "reliability": metrics.reliability_table(
                confidence[moved], hit[moved].astype(float), CONFIDENCE_BANDS
            ),
            "share_at_or_above_threshold": float(confident.sum() / max(moved.sum(), 1)),
            "directional_accuracy_at_or_above_threshold": (
                confident_hits / int(confident.sum()) if confident.sum() else None
            ),
            "ci95_at_or_above_threshold": list(confident_ci) if confident.sum() else None,
        },
        "random_forest": metrics.classification_summary(
            y_true, test["rf_signal"].to_numpy(), CLASS_ORDER, probabilities
        ),
        "per_ticker": per_ticker,
    }


def _fold_summary(evaluation: dict) -> dict:
    return {
        "test_first_date": evaluation["periods"]["test"]["first_date"],
        "test_last_date": evaluation["periods"]["test"]["last_date"],
        "test_rows": evaluation["periods"]["test"]["lstm_windows"],
        "lstm_theil_u": evaluation["lstm"]["theil_u"],
        "lstm_directional_accuracy": evaluation["lstm"]["direction"]["directional_accuracy"],
        "majority_direction_accuracy": evaluation["baselines"]["majority_direction"][
            "directional_accuracy"
        ],
        "dm_p_value": evaluation["lstm"]["diebold_mariano_vs_naive"]["p_value"],
        "confidence_brier": evaluation["confidence"]["brier"],
        "confidence_brier_baseline": evaluation["confidence"]["brier_constant_baseline"],
        "share_at_or_above_threshold": evaluation["confidence"]["share_at_or_above_threshold"],
        "rf_accuracy": evaluation["random_forest"]["accuracy"],
        "rf_balanced_accuracy": evaluation["random_forest"]["balanced_accuracy"],
        "majority_class_accuracy": evaluation["baselines"]["majority_class"]["accuracy"],
    }


def walk_forward(frames: dict[str, pd.DataFrame], **fit_kwargs) -> dict:
    dates = pd.concat([f["date"] for f in frames.values()])
    folds = []
    for cuts in walk_forward_folds(dates, WALK_FORWARD_FOLDS, WALK_FORWARD_TEST_FRAC):
        models, evaluation, _ = fit_and_evaluate(frames, cuts, **fit_kwargs)
        folds.append(
            {
                **_fold_summary(evaluation),
                "lstm_seconds": models.training["lstm_seconds"],
                "random_forest_seconds": models.training["random_forest_seconds"],
            }
        )
    keys = [k for k, v in folds[0].items() if isinstance(v, float)]
    return {
        "folds": folds,
        "mean": {k: float(np.mean([f[k] for f in folds])) for k in keys},
        "std": {k: float(np.std([f[k] for f in folds])) for k in keys},
    }


def train_and_save(
    raw: dict[str, pd.DataFrame],
    dataset: dict,
    model_dir: str | Path,
    *,
    version: str | None = None,
    run_walk_forward: bool = True,
    lstm_epochs: int = LSTM_HYPERPARAMS["max_epochs"],
    rf_params: dict | None = None,
) -> dict:
    """
    Fit the final 70/15/15 models, optionally the walk-forward folds, save the artifacts
    under <model_dir>/<version>/ and point <model_dir>/latest.json at them.
    `dataset` describes the input (name and per-file hashes) and is stored with the model.
    """
    version = version or new_model_version()
    started = time.perf_counter()
    frames = prepare_frames(raw)
    cuts = shared_cut_dates(pd.concat([f["date"] for f in frames.values()]), TRAIN_FRAC, VAL_FRAC)
    models, evaluation, _ = fit_and_evaluate(
        frames, cuts, lstm_epochs=lstm_epochs, rf_params=rf_params
    )
    folds = (
        walk_forward(frames, lstm_epochs=lstm_epochs, rf_params=rf_params)
        if run_walk_forward
        else None
    )

    importances = sorted(
        zip(FEATURE_COLUMNS, models.forest.feature_importances_, strict=True), key=lambda kv: -kv[1]
    )
    metadata = {
        "model_version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "tickers": sorted(frames),
        "dataset": dataset,
        "data": {
            "split": {
                "train": TRAIN_FRAC,
                "val": VAL_FRAC,
                "test": round(1 - TRAIN_FRAC - VAL_FRAC, 2),
            },
            "cut_dates": {
                "val_start": cuts.val_start.date().isoformat(),
                "test_start": cuts.test_start.date().isoformat(),
                "test_end": cuts.test_end.date().isoformat(),
            },
            "periods": evaluation.pop("periods"),
            "label_threshold": SIGNAL_THRESHOLD,
        },
        "features": FEATURE_COLUMNS,
        "seed": SEED,
        "lstm": {
            "hyperparameters": {**LSTM_HYPERPARAMS, "max_epochs": lstm_epochs},
            "training": models.training,
        },
        "random_forest": {
            "hyperparameters": rf_params or RF_PARAMS,
            "feature_importance": [{"feature": f, "importance": float(i)} for f, i in importances],
        },
        "evaluation": evaluation,
        "walk_forward": folds,
        "training_seconds_total": round(time.perf_counter() - started, 1),
        "library_versions": {
            "torch": torch.__version__,
            "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
        },
    }
    save_artifacts(models, metadata, Path(model_dir), version)
    lstm_eval = evaluation["lstm"]
    logger.info(
        f"{version}: LSTM Theil U {lstm_eval['theil_u']:.3f}, direction "
        f"{lstm_eval['direction']['directional_accuracy']:.3f}; "
        f"RF accuracy {evaluation['random_forest']['accuracy']:.3f}"
    )
    return metadata


def save_artifacts(models: FittedModels, metadata: dict, model_dir: Path, version: str) -> None:
    out = model_dir / version
    out.mkdir(parents=True, exist_ok=True)
    torch.save(models.lstm.state_dict(), out / "lstm.pt")
    joblib.dump(
        {
            "model_version": version,
            "scaler": models.scaler,
            "y_std": models.y_std,
            "seq_length": SEQ_LENGTH,
            "features": FEATURE_COLUMNS,
        },
        out / "preprocess.joblib",
    )
    joblib.dump({"model_version": version, "model": models.forest}, out / "random_forest.joblib")
    joblib.dump({"model_version": version, "model": models.calibrator}, out / "calibrator.joblib")
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    (model_dir / "latest.json").write_text(json.dumps({"model_version": version}) + "\n")
