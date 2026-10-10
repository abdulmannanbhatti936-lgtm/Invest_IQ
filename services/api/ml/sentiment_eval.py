"""
FinBERT accuracy (PRD.md §11 target: above 85%), reported on two sets and never averaged:

1. Financial PhraseBank (Malo et al. 2014; CC BY-NC-SA 3.0), the "all annotators agree"
   and "50% agree" subsets. OPTIMISTIC: ProsusAI/finbert was fine-tuned on this dataset and
   its test split was never published, so most of these sentences were probably seen in
   training. Downloaded at run time from a pinned revision and never committed.
2. The PSX headline set in docs/sentiment-eval/ (162 real headlines labelled by the team).
   Until every `final_label` is filled in, it is reported as "pending team labels".

For each set: FinBERT alone, VADER alone, and FinBERT with the VADER fallback (the setup
the app uses), with a 95% bootstrap interval on accuracy.

    python -m ml.sentiment_eval      # writes ml/reports/finbert_evaluation.{json,md}
"""

import csv
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import requests

from core.config import API_ROOT, settings
from ml.metrics import classification_summary
from ml.sentiment import (
    FINBERT_VERSION,
    LABELS,
    VADER_BELOW_CONFIDENCE,
    FinBERT,
    Vader,
    needs_fallback,
    vader_label,
)

PHRASEBANK_REVISION = "8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964"
PHRASEBANK_URL = (
    "https://huggingface.co/datasets/takala/financial_phrasebank/resolve/"
    f"{PHRASEBANK_REVISION}/data/FinancialPhraseBank-v1.0.zip"
)
PHRASEBANK_SUBSETS = {"all_agree": "Sentences_AllAgree.txt", "50_agree": "Sentences_50Agree.txt"}
PSX_SHEET = API_ROOT.parent.parent / "docs" / "sentiment-eval" / "psx_headlines_labeling.csv"
BOOTSTRAP_SAMPLES = 2000
SEED = 42
PRD_TARGET = 0.85


def phrasebank(subset: str, cache_dir: Path) -> tuple[list[str], list[str]]:
    archive = cache_dir / "FinancialPhraseBank-v1.0.zip"
    if not archive.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        response = requests.get(PHRASEBANK_URL, timeout=60)
        response.raise_for_status()
        archive.write_bytes(response.content)
    with zipfile.ZipFile(archive) as zf:
        name = next(n for n in zf.namelist() if n.endswith(PHRASEBANK_SUBSETS[subset]))
        lines = io.TextIOWrapper(zf.open(name), encoding="latin-1").read().splitlines()
    texts, labels = [], []
    for line in lines:
        text, _, label = line.rpartition("@")
        if text and label.strip() in LABELS:
            texts.append(text.strip())
            labels.append(label.strip())
    return texts, labels


def bootstrap_accuracy(hits: np.ndarray, samples: int = BOOTSTRAP_SAMPLES) -> list[float]:
    """95% percentile interval of the accuracy, resampling rows with replacement."""
    rng = np.random.default_rng(SEED)
    means = rng.choice(hits, size=(samples, len(hits)), replace=True).mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def cohen_kappa(a: list[str], b: list[str]) -> float:
    a, b = np.asarray(a), np.asarray(b)
    observed = float(np.mean(a == b))
    expected = sum(float(np.mean(a == label) * np.mean(b == label)) for label in LABELS)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def predictions(texts: list[str], finbert: FinBERT, vader: Vader) -> dict[str, list[str]]:
    """Labels from FinBERT alone, VADER alone and the deployed FinBERT + VADER fallback."""
    finbert_only, vader_only, deployed = [], [], []
    for text, probs in zip(texts, finbert.probabilities(texts), strict=True):
        best = max(LABELS, key=lambda name: probs.get(name, 0.0))
        by_vader = vader_label(vader.compound(text))
        finbert_only.append(best)
        vader_only.append(by_vader)
        deployed.append(by_vader if needs_fallback(text, probs[best]) else best)
    return {"finbert": finbert_only, "vader": vader_only, "finbert_with_vader_fallback": deployed}


def score_set(truth: list[str], predicted: dict[str, list[str]]) -> dict:
    out = {"rows": len(truth)}
    for name, labels in predicted.items():
        hits = (np.asarray(labels) == np.asarray(truth)).astype(float)
        out[name] = {
            **classification_summary(np.asarray(truth), np.asarray(labels), list(LABELS), None),
            "accuracy_ci95": bootstrap_accuracy(hits),
        }
    if "finbert_with_vader_fallback" in predicted:
        fallback = np.asarray(predicted["finbert_with_vader_fallback"]) != np.asarray(
            predicted["finbert"]
        )
        out["vader_changed_label_share"] = float(fallback.mean())
    return out


def psx_set(sheet: Path, finbert: FinBERT, vader: Vader) -> dict:
    with sheet.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    labelled = [r for r in rows if r["final_label"].strip().lower() in LABELS]
    if len(labelled) < len(rows):
        return {
            "status": "pending team labels",
            "rows": len(rows),
            "rows_with_final_label": len(labelled),
        }
    about = [r for r in rows if r["about_company"].strip().upper() == "Y"]
    truth = [r["final_label"].strip().lower() for r in about]
    return {
        "status": "labelled",
        "rows": len(rows),
        "labeller_agreement_kappa": cohen_kappa(
            [r["label_A"].strip().lower() for r in rows],
            [r["label_B"].strip().lower() for r in rows],
        ),
        "ticker_match_precision": len(about) / len(rows),
        **score_set(truth, predictions([r["headline"] for r in about], finbert, vader)),
    }


def evaluate(cache_dir: Path, sheet: Path = PSX_SHEET) -> dict:
    finbert, vader = FinBERT(), Vader()
    bank = {}
    for subset in PHRASEBANK_SUBSETS:
        texts, labels = phrasebank(subset, cache_dir)
        bank[subset] = score_set(labels, predictions(texts, finbert, vader))
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "finbert": FINBERT_VERSION,
        "vader": vader.version,
        "fallback_rule": f"VADER when FinBERT top probability < {VADER_BELOW_CONFIDENCE} "
        "or the text has 3 words or fewer",
        "prd_target_accuracy": PRD_TARGET,
        "financial_phrasebank": {
            "revision": PHRASEBANK_REVISION,
            "caveat": "optimistic: FinBERT was fine-tuned on Financial PhraseBank",
            **bank,
        },
        "psx_headlines": psx_set(sheet, finbert, vader),
    }


def _pct(value: float) -> str:
    return f"{100 * value:.1f}%"


def _method_rows(result: dict) -> list[str]:
    rows = []
    for name, title in (
        ("finbert", "FinBERT alone"),
        ("vader", "VADER alone"),
        ("finbert_with_vader_fallback", "FinBERT + VADER fallback (deployed)"),
    ):
        m = result[name]
        low, high = m["accuracy_ci95"]
        recall = " / ".join(_pct(m["per_class"][label]["recall"]) for label in LABELS)
        rows.append(
            f"| {title} | {_pct(m['accuracy'])} ({_pct(low)}-{_pct(high)}) | "
            f"{m['f1_macro']:.3f} | {recall} |"
        )
    return rows


def write_report(result: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "finbert_evaluation.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    header = [
        "| Method | Accuracy (95% CI) | Macro-F1 | Recall positive / negative / neutral |",
        "| --- | --- | --- | --- |",
    ]
    lines = [
        "# FinBERT evaluation",
        "",
        f"Model `{result['finbert']}`, {result['vader']}. Fallback: {result['fallback_rule']}. "
        f"PRD target: accuracy above {_pct(result['prd_target_accuracy'])}. Generated by "
        "`python -m ml.sentiment_eval`.",
        "",
        "## Financial PhraseBank (optimistic: FinBERT was fine-tuned on it)",
        "",
        "ProsusAI/finbert was fine-tuned on this dataset and its test split was never "
        "published, so these figures are an upper bound, not a measure on unseen text.",
    ]
    for subset, title in (
        ("all_agree", "All annotators agree"),
        ("50_agree", "At least 50% agree"),
    ):
        block = result["financial_phrasebank"][subset]
        lines += ["", f"### {title} ({block['rows']} sentences)", "", *header]
        lines += _method_rows(block)
        lines += [
            "",
            f"VADER replaced FinBERT's label on {_pct(block['vader_changed_label_share'])} "
            "of sentences.",
        ]
    psx = result["psx_headlines"]
    lines += ["", "## PSX headlines (docs/sentiment-eval)", ""]
    if psx["status"] != "labelled":
        lines.append(
            f"**Pending team labels**: {psx['rows_with_final_label']} of {psx['rows']} rows "
            "have a final label. This section fills in when the sheet is complete."
        )
    else:
        lines += [
            f"Labeller agreement (Cohen's kappa, before discussion): "
            f"{psx['labeller_agreement_kappa']:.2f}. Ticker matching was right for "
            f"{_pct(psx['ticker_match_precision'])} of headlines; accuracy is measured on the "
            f"{psx['rows']} headlines about the matched company.",
            "",
            *header,
            *_method_rows(psx),
        ]
    (out_dir / "finbert_evaluation.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def main() -> None:
    result = evaluate(Path(settings.CANDIDATE_DIR) / "external")
    write_report(result, Path(settings.REPORTS_DIR))
    print(json.dumps({k: v for k, v in result.items() if k != "financial_phrasebank"}, indent=2))


if __name__ == "__main__":
    main()
