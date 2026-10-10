"""
Headline sentiment (Workflow.md Steps 4.3-4.4, Architecture.md §15.3).

FinBERT (ProsusAI/finbert, pinned to one revision so a score never changes under us) gives
P(positive), P(negative) and P(neutral); a headline's score is P(positive) - P(negative)
and its label the most likely class. VADER scores the headline instead when FinBERT's top
probability is below 0.50 or the text has 3 words or fewer; VADER's label is positive at
compound >= +0.05, negative at <= -0.05, otherwise neutral, and its score is the compound
score (all decided 2026-10-11, Memory.md §3).

If FinBERT cannot be loaded, scoring fails loudly (SentimentModelUnavailable) and headlines
stay unscored; nothing is ever given a made-up neutral score.
"""

import logging
from dataclasses import dataclass
from importlib.metadata import version

logger = logging.getLogger(__name__)

FINBERT_MODEL = "ProsusAI/finbert"
FINBERT_REVISION = "4556d13015211d73dccd3fdd39d39232506f3e43"
FINBERT_VERSION = f"{FINBERT_MODEL}@{FINBERT_REVISION[:7]}"
VADER_BELOW_CONFIDENCE = 0.50
SHORT_TEXT_WORDS = 3
VADER_CUTOFF = 0.05
LABELS = ("positive", "negative", "neutral")
FINBERT = "finbert"
VADER = "vader"


class SentimentModelUnavailable(RuntimeError):
    """FinBERT could not be loaded or run; headlines are left unscored."""


@dataclass(frozen=True)
class HeadlineScore:
    score: float  # -1 (negative) .. +1 (positive)
    label: str
    scorer: str
    scorer_version: str
    finbert_confidence: float  # FinBERT's top class probability, also when VADER scored


def build_pipeline():
    from transformers import pipeline

    return pipeline(
        "text-classification",
        model=FINBERT_MODEL,
        revision=FINBERT_REVISION,
        top_k=None,
        device=-1,
        # The repository has only pytorch_model.bin; without this, transformers loads an
        # automatic safetensors conversion from a pull-request branch instead of the pinned
        # revision
        model_kwargs={"use_safetensors": False},
    )


class FinBERT:
    """Lazily loaded FinBERT text classifier returning all three class probabilities."""

    def __init__(self, batch_size: int = 32):
        self.batch_size = batch_size
        self._pipeline = None

    def _load(self):
        if self._pipeline is None:
            try:
                self._pipeline = build_pipeline()
            except Exception as e:
                raise SentimentModelUnavailable(f"FinBERT could not be loaded: {e}") from e
        return self._pipeline

    def probabilities(self, texts: list[str]) -> list[dict[str, float]]:
        classifier = self._load()
        try:
            outputs = classifier(texts, batch_size=self.batch_size, truncation=True)
        except Exception as e:
            raise SentimentModelUnavailable(f"FinBERT failed: {e}") from e
        return [{item["label"].lower(): float(item["score"]) for item in row} for row in outputs]


class Vader:
    def __init__(self):
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._analyzer = SentimentIntensityAnalyzer()
        self.version = f"vaderSentiment=={version('vaderSentiment')}"

    def compound(self, text: str) -> float:
        return float(self._analyzer.polarity_scores(text)["compound"])


def vader_label(compound: float) -> str:
    if compound >= VADER_CUTOFF:
        return "positive"
    if compound <= -VADER_CUTOFF:
        return "negative"
    return "neutral"


def needs_fallback(text: str, finbert_top_probability: float) -> bool:
    return finbert_top_probability < VADER_BELOW_CONFIDENCE or len(text.split()) <= SHORT_TEXT_WORDS


class HeadlineScorer:
    def __init__(self, finbert: FinBERT | None = None, vader: Vader | None = None):
        self.finbert = finbert or FinBERT()
        self._vader = vader

    @property
    def vader(self) -> Vader:
        if self._vader is None:
            self._vader = Vader()
        return self._vader

    def score(self, texts: list[str]) -> list[HeadlineScore]:
        if not texts:
            return []
        results = []
        for text, probs in zip(texts, self.finbert.probabilities(texts), strict=True):
            label = max(LABELS, key=lambda name: probs.get(name, 0.0))
            top = probs.get(label, 0.0)
            if needs_fallback(text, top):
                compound = self.vader.compound(text)
                results.append(
                    HeadlineScore(compound, vader_label(compound), VADER, self.vader.version, top)
                )
            else:
                results.append(
                    HeadlineScore(
                        probs.get("positive", 0.0) - probs.get("negative", 0.0),
                        label,
                        FINBERT,
                        FINBERT_VERSION,
                        top,
                    )
                )
        return results
