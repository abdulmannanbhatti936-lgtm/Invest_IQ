"""The FinBERT evaluation runs on its own once the team fills in the PSX labels."""

import csv

import numpy as np
import pytest

from ml.sentiment_eval import bootstrap_accuracy, cohen_kappa, psx_set, write_report

COLUMNS = [
    "id",
    "matched_ticker",
    "source",
    "published_date",
    "headline",
    "url",
    "about_company",
    "label_A",
    "label_B",
    "final_label",
    "notes",
]


class KeywordFinBERT:
    """Fake FinBERT: confident 'positive' for 'up', 'negative' for 'down', else neutral."""

    def probabilities(self, texts):
        out = []
        for text in texts:
            label = "positive" if "up" in text else "negative" if "down" in text else "neutral"
            probs = {"positive": 0.05, "negative": 0.05, "neutral": 0.05}
            probs[label] = 0.9
            out.append(probs)
        return out


class ZeroVader:
    version = "vaderSentiment==test"

    def compound(self, text):
        return 0.0


def _sheet(tmp_path, rows):
    path = tmp_path / "sheet.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for i, (headline, about, a, b, final) in enumerate(rows, 1):
            writer.writerow(
                {
                    "id": f"H{i:03d}",
                    "matched_ticker": "MOCKA",
                    "source": "Profit",
                    "published_date": "2026-01-01",
                    "headline": headline,
                    "url": f"https://example.com/MOCK/{i}",
                    "about_company": about,
                    "label_A": a,
                    "label_B": b,
                    "final_label": final,
                    "notes": "",
                }
            )
    return path


def test_unlabelled_sheet_is_reported_as_pending(tmp_path):
    sheet = _sheet(
        tmp_path,
        [
            ("MOCK_ profit up strongly", "", "", "", ""),
            ("MOCK_ sales down", "Y", "x", "x", "negative"),
        ],
    )
    result = psx_set(sheet, KeywordFinBERT(), ZeroVader())
    assert result == {"status": "pending team labels", "rows": 2, "rows_with_final_label": 1}


def test_labelled_sheet_is_scored_on_headlines_about_the_company(tmp_path):
    sheet = _sheet(
        tmp_path,
        [
            ("MOCK_ profit up strongly this year", "Y", "positive", "positive", "positive"),
            ("MOCK_ sales down sharply this year", "Y", "negative", "neutral", "negative"),
            ("MOCK_ annual meeting held in Karachi", "Y", "neutral", "neutral", "positive"),
            ("MOCK_ sponsor of the cricket league", "N", "neutral", "neutral", "neutral"),
        ],
    )
    result = psx_set(sheet, KeywordFinBERT(), ZeroVader())
    assert result["status"] == "labelled"
    assert result["ticker_match_precision"] == pytest.approx(0.75)
    assert result["rows"] == 3
    assert result["finbert"]["accuracy"] == pytest.approx(2 / 3)
    assert result["vader"]["accuracy"] == pytest.approx(0.0)
    write_report(
        {
            "finbert": "MOCK",
            "vader": "MOCK",
            "fallback_rule": "MOCK",
            "prd_target_accuracy": 0.85,
            "financial_phrasebank": {
                subset: {**result, "vader_changed_label_share": 0.0}
                for subset in ("all_agree", "50_agree")
            },
            "psx_headlines": result,
        },
        tmp_path / "out",
    )
    assert "Labeller agreement" in (tmp_path / "out" / "finbert_evaluation.md").read_text()


def test_kappa():
    assert cohen_kappa(["positive", "negative"], ["positive", "negative"]) == pytest.approx(1.0)
    # Agreement no better than chance
    a = ["positive", "positive", "negative", "negative"]
    b = ["positive", "negative", "positive", "negative"]
    assert cohen_kappa(a, b) == pytest.approx(0.0)


def test_bootstrap_interval_brackets_the_accuracy():
    hits = np.array([1.0] * 80 + [0.0] * 20)
    low, high = bootstrap_accuracy(hits)
    assert low < 0.8 < high
    assert 0.7 < low and high < 0.9
