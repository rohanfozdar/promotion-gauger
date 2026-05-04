from __future__ import annotations

import sqlite3
from collections import Counter
from pathlib import Path

import torch
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from torch.utils.data import Dataset
from transformers import AutoModelForSequenceClassification, AutoTokenizer, Trainer, TrainingArguments


LABEL_NAMES = {
    0: "negative",
    1: "neutral",
    2: "positive",
}


def build_training_data(db_path: Path) -> tuple[list[str], list[int]]:
    """
    Load Amazon review mentions from DB and convert to
    (text, label) pairs where label is 0=negative, 1=neutral, 2=positive
    based on overall_sentiment score.
    Threshold: score > 0.15 -> positive, score < -0.15 -> negative, else neutral.
    Only use platform='review' rows with non-zero overall_sentiment.
    Minimum 30 records required - raise ValueError if fewer found.
    """
    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT text, overall_sentiment
            FROM mentions
            WHERE platform = 'review'
              AND overall_sentiment != 0
              AND TRIM(text) != ''
            ORDER BY timestamp ASC
            """
        ).fetchall()

    if len(rows) < 30:
        raise ValueError(f"Need at least 30 labeled Amazon review records, found {len(rows)}.")

    texts: list[str] = []
    labels: list[int] = []
    for text, score in rows:
        sentiment = float(score)
        if sentiment > 0.15:
            label = 2
        elif sentiment < -0.15:
            label = 0
        else:
            label = 1
        texts.append(str(text))
        labels.append(label)

    return texts, labels


class ReviewDataset(Dataset):
    def __init__(self, encodings: dict[str, list[list[int]]], labels: list[int]) -> None:
        self.encodings = encodings
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict[str, torch.Tensor]:
        item = {key: torch.tensor(value[idx]) for key, value in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


def finetune_model(
    db_path: Path,
    output_dir: Path,
    base_model: str = "cardiffnlp/twitter-roberta-base-sentiment-latest",
    epochs: int = 3,
    batch_size: int = 8,
    max_length: int = 128,
) -> None:
    texts, labels = build_training_data(db_path)
    train_texts, eval_texts, train_labels, eval_labels = train_test_split(
        texts,
        labels,
        test_size=0.2,
        random_state=42,
        stratify=labels,
    )

    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(
        base_model,
        num_labels=3,
        ignore_mismatched_sizes=True,
    )

    train_encodings = tokenizer(
        train_texts,
        truncation=True,
        max_length=max_length,
        padding="max_length",
    )
    eval_encodings = tokenizer(
        eval_texts,
        truncation=True,
        max_length=max_length,
        padding="max_length",
    )

    train_dataset = ReviewDataset(train_encodings, train_labels)
    eval_dataset = ReviewDataset(eval_encodings, eval_labels)

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        logging_steps=10,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
    )
    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(output_dir)
    print(f"Fine-tuned model saved to {output_dir}")

    saved_tokenizer = AutoTokenizer.from_pretrained(output_dir)
    saved_model = AutoModelForSequenceClassification.from_pretrained(output_dir)
    saved_model.eval()
    eval_inputs = saved_tokenizer(
        eval_texts,
        truncation=True,
        max_length=max_length,
        padding="max_length",
        return_tensors="pt",
    )
    with torch.no_grad():
        predictions = saved_model(**eval_inputs).logits.argmax(dim=-1).tolist()

    accuracy = accuracy_score(eval_labels, predictions)
    counts = Counter(eval_labels)
    print(f"Eval accuracy: {accuracy:.2f}")
    print(
        "Per-class counts: "
        f"negative={counts[0]}, neutral={counts[1]}, positive={counts[2]}"
    )
