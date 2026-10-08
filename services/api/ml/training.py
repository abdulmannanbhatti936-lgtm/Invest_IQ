"""
Per-ticker training of the LSTM forecaster and the RF/SVM signal classifiers
(Workflow.md Steps 3.4-3.5). Training never runs inside an HTTP request
(Rules.md §3.5): it is invoked from the `ml.train` CLI or the weekly Celery job.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, precision_recall_fscore_support
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from ml import lstm_model
from ml.features import (
    FEATURE_COLUMNS,
    SIGNAL_LABELS,
    SIGNAL_THRESHOLD,
    build_feature_frame,
    training_rows,
)
from ml.splits import split_boundaries

logger = logging.getLogger(__name__)

SEQ_LENGTH = 60
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
MIN_TRAINING_ROWS = 400  # ~1.6 trading years after indicator warm-up
SEED = 42

LSTM_HYPERPARAMS = {
    "seq_length": SEQ_LENGTH,
    "layers": "LSTM(64) -> LSTM(32) -> Dropout(0.2) -> Dense(1)",
    "target": "next-day return, standardised by train std",
    "optimizer": "Adam",
    "lr": 1e-3,
    "batch_size": 64,
    "max_epochs": 60,
    "early_stopping_patience": 8,
}
RF_PARAMS = {
    "n_estimators": 300,
    "max_depth": 6,
    "min_samples_leaf": 5,
    "class_weight": "balanced_subsample",
    "random_state": SEED,
    "n_jobs": -1,
}
SVM_PARAMS = {"C": 1.0, "kernel": "rbf", "class_weight": "balanced", "random_state": SEED}


class InsufficientDataError(ValueError):
    pass


def new_model_version() -> str:
    return "lstm-rf-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _regression_metrics(
    close_t: np.ndarray, actual_next: np.ndarray, pred_return: np.ndarray
) -> dict:
    forecast = close_t * (1 + pred_return)
    actual_return = actual_next / close_t - 1
    rmse = float(np.sqrt(np.mean((forecast - actual_next) ** 2)))
    naive_rmse = float(np.sqrt(np.mean((close_t - actual_next) ** 2)))
    moved = actual_return != 0
    direction_hits = np.sign(pred_return[moved]) == np.sign(actual_return[moved])
    share_up = float(np.mean(actual_return[moved] > 0))
    return {
        "test_samples": int(len(actual_next)),
        "rmse": rmse,
        "rmse_pct_of_price": rmse / float(np.mean(actual_next)) * 100,
        "mape_pct": float(np.mean(np.abs(forecast - actual_next) / actual_next) * 100),
        "directional_accuracy": float(np.mean(direction_hits)),
        "baseline_naive_rmse": naive_rmse,
        "baseline_naive_rmse_pct_of_price": naive_rmse / float(np.mean(actual_next)) * 100,
        "baseline_majority_direction_accuracy": max(share_up, 1 - share_up),
    }


def _classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )
    majority = pd.Series(y_true).value_counts(normalize=True).iloc[0]
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision_macro": float(precision),
        "recall_macro": float(recall),
        "f1_macro": float(f1),
        "baseline_majority_class_accuracy": float(majority),
    }


def train_ticker(
    ticker: str,
    ohlcv: pd.DataFrame,
    model_dir: str | Path,
    sentiments=None,
    version: str | None = None,
    lstm_epochs: int = 60,
) -> dict:
    """
    Train and evaluate all models for one ticker, save artifacts under
    <model_dir>/<TICKER>/<version>/ and point <model_dir>/<TICKER>/latest.json at it.
    Returns the metadata dict (also written as metadata.json).
    """
    ticker = ticker.upper()
    version = version or new_model_version()
    feat = build_feature_frame(ohlcv, sentiments)
    rows = training_rows(feat)
    if len(rows) < MIN_TRAINING_ROWS:
        raise InsufficientDataError(
            f"{ticker}: {len(rows)} usable rows, need at least {MIN_TRAINING_ROWS}"
        )
    # Only the final row (no next-day outcome) is excluded from `rows`
    assert (feat["date"].iloc[: len(rows)].to_numpy() == rows["date"].to_numpy()).all()

    n = len(rows)
    train_end, val_end = split_boundaries(n, TRAIN_FRAC, VAL_FRAC)

    # ---- Preprocessing: fitted on the training rows only (no leakage)
    scaler = StandardScaler().fit(rows.loc[: train_end - 1, FEATURE_COLUMNS])
    scaled = scaler.transform(feat[FEATURE_COLUMNS]).astype(np.float32)
    y_std = float(rows.loc[: train_end - 1, "target_return"].std())
    y_scaled = (rows["target_return"].to_numpy() / y_std).astype(np.float32)

    # ---- LSTM. Windows may reach back into earlier splits (past features only).
    first = SEQ_LENGTH - 1
    train_idx = np.arange(first, train_end)
    val_idx = np.arange(train_end, val_end)
    test_idx = np.arange(val_end, n)
    X_train = lstm_model.make_sequences(scaled, SEQ_LENGTH, train_idx)
    X_val = lstm_model.make_sequences(scaled, SEQ_LENGTH, val_idx)
    X_test = lstm_model.make_sequences(scaled, SEQ_LENGTH, test_idx)

    model, fit_info = lstm_model.train_lstm(
        X_train, y_scaled[train_idx], X_val, y_scaled[val_idx], epochs=lstm_epochs, seed=SEED
    )
    pred_return = lstm_model.predict(model, X_test) * y_std
    lstm_metrics = _regression_metrics(
        rows["close"].to_numpy()[test_idx],
        rows["next_close"].to_numpy()[test_idx],
        pred_return,
    )
    lstm_metrics.update(fit_info)

    # ---- Classifiers: fit on train+val, evaluate on the held-out test period
    X_fit = rows.loc[: val_end - 1, FEATURE_COLUMNS].to_numpy()
    y_fit = rows.loc[: val_end - 1, "target_signal"].astype(int).to_numpy()
    X_eval = rows.loc[val_end:, FEATURE_COLUMNS].to_numpy()
    y_eval = rows.loc[val_end:, "target_signal"].astype(int).to_numpy()

    rf = RandomForestClassifier(**RF_PARAMS).fit(X_fit, y_fit)
    svm = make_pipeline(StandardScaler(), SVC(**SVM_PARAMS)).fit(X_fit, y_fit)
    rf_metrics = _classification_metrics(y_eval, rf.predict(X_eval))
    svm_metrics = _classification_metrics(y_eval, svm.predict(X_eval))
    importances = sorted(
        zip(FEATURE_COLUMNS, rf.feature_importances_, strict=True), key=lambda kv: -kv[1]
    )

    metadata = {
        "ticker": ticker,
        "model_version": version,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data": {
            "rows_after_warmup": n,
            "date_start": rows["date"].iloc[0].date().isoformat(),
            "date_end": rows["date"].iloc[-1].date().isoformat(),
            "train_end_date": rows["date"].iloc[train_end - 1].date().isoformat(),
            "val_end_date": rows["date"].iloc[val_end - 1].date().isoformat(),
            "split": {
                "train": TRAIN_FRAC,
                "val": VAL_FRAC,
                "test": round(1 - TRAIN_FRAC - VAL_FRAC, 2),
            },
            "label_counts_test": {
                SIGNAL_LABELS[k]: int(v) for k, v in pd.Series(y_eval).value_counts().items()
            },
        },
        "features": FEATURE_COLUMNS,
        "signal_threshold": SIGNAL_THRESHOLD,
        "lstm": {"hyperparameters": LSTM_HYPERPARAMS, "test_metrics": lstm_metrics},
        "random_forest": {
            "hyperparameters": {k: v for k, v in RF_PARAMS.items() if k != "n_jobs"},
            "test_metrics": rf_metrics,
            "feature_importance": [{"feature": f, "importance": float(i)} for f, i in importances],
        },
        "svm": {"hyperparameters": SVM_PARAMS, "test_metrics": svm_metrics},
        "signal_model": "random_forest",
        "library_versions": {"torch": torch.__version__, "sklearn": sklearn.__version__},
    }

    out = Path(model_dir) / ticker / version
    out.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out / "lstm.pt")
    joblib.dump(
        {"scaler": scaler, "y_std": y_std, "seq_length": SEQ_LENGTH, "features": FEATURE_COLUMNS},
        out / "preprocess.joblib",
    )
    joblib.dump(rf, out / "random_forest.joblib")
    joblib.dump(svm, out / "svm.joblib")
    (out / "metadata.json").write_text(json.dumps(metadata, indent=2))
    (Path(model_dir) / ticker / "latest.json").write_text(json.dumps({"model_version": version}))

    logger.info(
        f"{ticker} {version}: LSTM RMSE {lstm_metrics['rmse_pct_of_price']:.2f}% "
        f"dir-acc {lstm_metrics['directional_accuracy']:.3f}; RF acc {rf_metrics['accuracy']:.3f}"
    )
    return metadata
