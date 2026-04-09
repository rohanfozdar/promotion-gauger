from __future__ import annotations

import re
from dataclasses import dataclass

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from promotion_gauger.config import BRAND_LEXICON, PRICE_LEXICON, URGENCY_LEXICON, AxisLexicon


TOKEN_RE = re.compile(r"[a-zA-Z']+")


@dataclass(slots=True)
class SentimentScores:
    price: float
    brand: float
    urgency: float
    overall: float


class PromotionSentimentScorer:
    def __init__(self) -> None:
        self.analyzer = SentimentIntensityAnalyzer()

    def score(self, text: str) -> SentimentScores:
        tokens = [token.lower() for token in TOKEN_RE.findall(text)]
        overall = self.analyzer.polarity_scores(text)["compound"]
        return SentimentScores(
            price=self._axis_score(tokens, PRICE_LEXICON, overall),
            brand=self._axis_score(tokens, BRAND_LEXICON, overall),
            urgency=self._axis_score(tokens, URGENCY_LEXICON, overall),
            overall=overall,
        )

    def _axis_score(self, tokens: list[str], lexicon: AxisLexicon, overall: float) -> float:
        positive_hits = sum(token in lexicon.positive for token in tokens)
        negative_hits = sum(token in lexicon.negative for token in tokens)
        lexical_score = (positive_hits - negative_hits) / max(len(tokens), 1)
        score = (0.65 * overall) + (0.35 * lexical_score * 4)
        return max(-1.0, min(1.0, round(score, 3)))
