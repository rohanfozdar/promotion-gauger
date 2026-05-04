from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from promotion_gauger.config import BRAND_LEXICON, PRICE_LEXICON, URGENCY_LEXICON, AxisLexicon

# Import transformers at module level so Streamlit's watcher
# cannot cause a partial-init race condition
try:
    from transformers import AutoTokenizer
    from transformers import pipeline as hf_pipeline

    _TRANSFORMERS_AVAILABLE = True
except Exception:
    _TRANSFORMERS_AVAILABLE = False


TOKEN_RE = re.compile(r"[a-zA-Z']+")
MODEL_NAME = "cardiffnlp/twitter-roberta-base-sentiment-latest"


@dataclass(slots=True)
class SentimentScores:
    price: float
    brand: float
    urgency: float
    overall: float


class PromotionSentimentScorer:
    def __init__(self, model_path: Path | None = None) -> None:
        self.fallback_analyzer = SentimentIntensityAnalyzer()
        self.classifier = None
        self.tokenizer = None
        self._load_model(model_path=model_path)

    def score(self, text: str) -> SentimentScores:
        tokens = [token.lower() for token in TOKEN_RE.findall(text)]
        overall = self._score_overall(text)
        return SentimentScores(
            price=self._axis_score(tokens, PRICE_LEXICON, overall),
            brand=self._axis_score(tokens, BRAND_LEXICON, overall),
            urgency=self._axis_score(tokens, URGENCY_LEXICON, overall),
            overall=overall,
        )

    def _load_model(self, model_path: Path | None = None) -> None:
        if not _TRANSFORMERS_AVAILABLE:
            print("Warning: transformers not importable. Falling back to VADER.")
            return
        model_source = str(model_path) if model_path is not None and model_path.exists() else MODEL_NAME
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_source)
            self.classifier = hf_pipeline(
                "text-classification",
                model=model_source,
                tokenizer=self.tokenizer,
            )
        except Exception as exc:
            self.classifier = None
            self.tokenizer = None
            print(
                f"Warning: failed to load transformer model '{model_source}'. "
                f"Falling back to VADER. Details: {exc}"
            )

    def _score_overall(self, text: str) -> float:
        if self.classifier is None or self.tokenizer is None:
            return round(self.fallback_analyzer.polarity_scores(text)["compound"], 3)

        encoded = self.tokenizer(
            text,
            truncation=True,
            max_length=512,
            return_tensors=None,
        )
        truncated_text = self.tokenizer.decode(
            encoded["input_ids"],
            skip_special_tokens=True,
            clean_up_tokenization_spaces=True,
        )
        result = self.classifier(truncated_text, truncation=True, max_length=512)[0]
        return self._map_label_to_score(result)

    def _map_label_to_score(self, result: dict[str, Any]) -> float:
        label = result["label"].lower()
        confidence = float(result["score"])
        if label in ("positive", "label_2"):
            score = confidence
        elif label in ("negative", "label_0"):
            score = -confidence
        else:
            score = 0.0
        return round(score, 3)

    def _axis_score(self, tokens: list[str], lexicon: AxisLexicon, overall: float) -> float:
        positive_hits = sum(token in lexicon.positive for token in tokens)
        negative_hits = sum(token in lexicon.negative for token in tokens)
        lexical_score = (positive_hits - negative_hits) / max(len(tokens), 1)
        score = (0.40 * overall) + (0.60 * lexical_score * 4)
        return max(-1.0, min(1.0, round(score, 3)))
