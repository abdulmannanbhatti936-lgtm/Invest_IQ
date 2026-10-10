"""FinBERT scoring and the VADER fallback (Workflow.md Steps 4.3-4.4, Memory.md §3)."""

import pytest

from ml import sentiment
from ml.sentiment import (
    FINBERT,
    VADER,
    VADER_BELOW_CONFIDENCE,
    FinBERT,
    HeadlineScorer,
    SentimentModelUnavailable,
    vader_label,
)


class FixedFinBERT:
    """Stands in for FinBERT and returns the same probabilities for every headline."""

    def __init__(self, positive, negative, neutral):
        self.probs = {"positive": positive, "negative": negative, "neutral": neutral}
        self.calls = 0

    def probabilities(self, texts):
        self.calls += 1
        return [dict(self.probs) for _ in texts]


class RecordingVader:
    version = "vaderSentiment==test"

    def __init__(self, compound):
        self.value = compound
        self.texts = []

    def compound(self, text):
        self.texts.append(text)
        return self.value


HEADLINE = "Systems Limited posts strong profit growth in the first half"


def test_confident_finbert_is_used_and_vader_is_not_called():
    vader = RecordingVader(0.9)
    (result,) = HeadlineScorer(FixedFinBERT(0.85, 0.05, 0.10), vader).score([HEADLINE])
    assert result.scorer == FINBERT
    assert result.label == "positive"
    assert result.score == pytest.approx(0.80)
    assert vader.texts == []


def test_vader_takes_over_when_finbert_is_forced_below_the_threshold():
    # Top probability 0.45 < 0.50: FinBERT is not confident enough
    vader = RecordingVader(-0.6)
    (result,) = HeadlineScorer(FixedFinBERT(0.45, 0.30, 0.25), vader).score([HEADLINE])
    assert VADER_BELOW_CONFIDENCE == 0.50
    assert vader.texts == [HEADLINE]
    assert result.scorer == VADER
    assert result.label == "negative"
    assert result.score == -0.6
    assert result.finbert_confidence == pytest.approx(0.45)


def test_vader_scores_very_short_text_even_when_finbert_is_confident():
    vader = RecordingVader(0.44)
    (result,) = HeadlineScorer(FixedFinBERT(0.9, 0.05, 0.05), vader).score(["Profit up"])
    assert result.scorer == VADER and result.label == "positive"


def test_vader_cut_offs():
    assert vader_label(0.05) == "positive"
    assert vader_label(-0.05) == "negative"
    assert vader_label(0.049) == "neutral"


def test_finbert_load_failure_raises_instead_of_a_neutral_score(monkeypatch):
    def broken():
        raise OSError("weights not found")

    monkeypatch.setattr(sentiment, "build_pipeline", broken)
    with pytest.raises(SentimentModelUnavailable):
        HeadlineScorer(FinBERT(), RecordingVader(0.0)).score([HEADLINE])
