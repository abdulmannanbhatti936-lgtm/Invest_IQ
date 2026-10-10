"""
Evaluation metrics and baselines for the prediction models (Workflow.md Steps 3.4-3.5).

Forecast errors are relative ((forecast - actual) / actual), so tickers priced at Rs.20 and
Rs.2,000 can be pooled. Tests use the normal approximation, written out here instead of
importing scipy. Pooled rows are not independent (stocks move together on the same day), so
confidence intervals and p-values on pooled rows are optimistic; the Diebold-Mariano test
therefore averages the loss difference across tickers per day first.
"""

import math

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)

Z_95 = 1.959964


def _normal_sf(z: float) -> float:
    """P(Z > z) for a standard normal Z."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def wilson_interval(hits: int, n: int, z: float = Z_95) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = hits / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (centre - half, centre + half)


def proportion_above_p_value(hits: int, n: int, p0: float) -> float:
    """One-sided test that the hit rate exceeds p0 (normal approximation to the binomial)."""
    if n == 0 or p0 <= 0 or p0 >= 1:
        return math.nan
    z = (hits - n * p0) / math.sqrt(n * p0 * (1 - p0))
    return _normal_sf(z)


def diebold_mariano(loss_model: np.ndarray, loss_baseline: np.ndarray, lag: int = 0) -> dict:
    """
    Diebold-Mariano test on a daily loss-difference series (model minus baseline; negative
    mean = model better). Two-sided p-value. For forecasts h days ahead the daily
    differences overlap, so `lag` = h - 1 adds the Newey-West autocovariance terms.
    """
    d = np.asarray(loss_model) - np.asarray(loss_baseline)
    n = len(d)
    if n < 2 or np.std(d, ddof=1) == 0:
        return {"statistic": math.nan, "p_value": math.nan, "days": n, "lag": lag}
    centred = d - np.mean(d)
    variance = np.var(d, ddof=1) + 2 * sum(
        (1 - k / (lag + 1)) * float(np.dot(centred[k:], centred[:-k])) / n
        for k in range(1, min(lag, n - 1) + 1)
    )
    if variance <= 0:
        return {"statistic": math.nan, "p_value": math.nan, "days": n, "lag": lag}
    stat = float(np.mean(d) / math.sqrt(variance / n))
    return {"statistic": stat, "p_value": 2 * _normal_sf(abs(stat)), "days": n, "lag": lag}


def direction_hits(predicted: np.ndarray, actual: np.ndarray) -> tuple[int, int]:
    """Hits and count over rows where both the prediction and the outcome moved."""
    mask = (np.sign(predicted) != 0) & (np.sign(actual) != 0)
    return int(np.sum(np.sign(predicted[mask]) == np.sign(actual[mask]))), int(mask.sum())


def direction_summary(predicted: np.ndarray, actual: np.ndarray, baseline_rate: float) -> dict:
    hits, n = direction_hits(predicted, actual)
    low, high = wilson_interval(hits, n)
    return {
        "directional_accuracy": hits / n if n else math.nan,
        "ci95_low": low,
        "ci95_high": high,
        "rows": n,
        "p_value_vs_baseline": proportion_above_p_value(hits, n, baseline_rate),
    }


def relative_errors(forecast: np.ndarray, actual: np.ndarray) -> np.ndarray:
    return (np.asarray(forecast) - np.asarray(actual)) / np.asarray(actual)


def price_error_summary(forecast: np.ndarray, actual: np.ndarray) -> dict:
    """RMSE as % of price (root mean squared relative error), MAPE, plus Rs. MAE/RMSE."""
    rel = relative_errors(forecast, actual)
    abs_err = np.abs(np.asarray(forecast) - np.asarray(actual))
    return {
        "rmse_pct": float(np.sqrt(np.mean(rel**2)) * 100),
        "mape_pct": float(np.mean(np.abs(rel)) * 100),
        "mae_rs": float(np.mean(abs_err)),
        "rmse_rs": float(np.sqrt(np.mean(abs_err**2))),
    }


def classification_summary(
    y_true: np.ndarray, y_pred: np.ndarray, labels: list[int], probabilities: np.ndarray | None
) -> dict:
    """Accuracy, balanced accuracy, macro-F1, per-class precision/recall, confusion matrix,
    and the multi-class Brier score when class probabilities (columns = labels) are given."""
    precision, recall, _, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    out = {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y_true, y_pred)),
        "f1_macro": float(
            f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)
        ),
        "per_class": {
            str(label): {"precision": float(p), "recall": float(r), "support": int(s)}
            for label, p, r, s in zip(labels, precision, recall, support, strict=True)
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }
    if probabilities is not None:
        onehot = (np.asarray(y_true)[:, None] == np.asarray(labels)[None, :]).astype(float)
        out["brier"] = float(np.mean(np.sum((probabilities - onehot) ** 2, axis=1)))
    return out


def reliability_table(
    confidence: np.ndarray, hit: np.ndarray, edges: tuple[float, ...]
) -> list[dict]:
    """Per confidence band: how many predictions, their mean confidence, how often right."""
    rows = []
    bounds = [-math.inf, *edges, math.inf]
    for low, high in zip(bounds, bounds[1:], strict=False):
        mask = (confidence >= low) & (confidence < high)
        n = int(mask.sum())
        rows.append(
            {
                "band": [None if math.isinf(low) else low, None if math.isinf(high) else high],
                "rows": n,
                "mean_confidence": float(np.mean(confidence[mask])) if n else None,
                "observed_hit_rate": float(np.mean(hit[mask])) if n else None,
            }
        )
    return rows


def brier(confidence: np.ndarray, hit: np.ndarray) -> float:
    return float(np.mean((np.asarray(confidence) - np.asarray(hit)) ** 2))
