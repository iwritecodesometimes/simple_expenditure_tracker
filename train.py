"""
Training script: reads item-category pairs from the Google Sheet
and builds a lookup of averaged embeddings per category, so the categoriser
improves over time based on your actual spending patterns.

The bot runs this automatically every week, and you can trigger it with /train.
It can also be run by hand: python train.py
"""

import os

import numpy as np
from sentence_transformers import SentenceTransformer

from config import DATA_DIR, load_categories
from sheets import get_expenses

MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDINGS_PATH = os.path.join(DATA_DIR, "trained_embeddings.npz")


def fetch_training_data(categories: list[str]) -> list[tuple[str, list[str]]]:
    pairs = []
    for expense in get_expenses():
        cats = [c for c in expense.categories if c in categories]
        if expense.item and cats:
            pairs.append((expense.item, cats))
    return pairs


def train(model: SentenceTransformer | None = None) -> str:
    """Retrain category embeddings. Returns a short human-readable report."""
    categories = load_categories()
    pairs = fetch_training_data(categories)
    if not pairs:
        return "No training data found in sheet."

    model = model or SentenceTransformer(MODEL_NAME)

    category_items: dict[str, list[str]] = {cat: [] for cat in categories}
    for item, cats in pairs:
        for cat in cats:
            category_items[cat].append(item)

    category_embeddings = {}
    base_embeddings = model.encode(categories)

    for i, cat in enumerate(categories):
        items = category_items[cat]
        if items:
            item_embeddings = model.encode(items)
            avg_item_embedding = np.mean(item_embeddings, axis=0)
            blended = 0.3 * base_embeddings[i] + 0.7 * avg_item_embedding
            category_embeddings[cat] = blended / np.linalg.norm(blended)
        else:
            category_embeddings[cat] = base_embeddings[i] / np.linalg.norm(base_embeddings[i])

    ordered = [category_embeddings[cat] for cat in categories]
    np.savez(EMBEDDINGS_PATH, embeddings=np.array(ordered), categories=categories)

    trained = [c for c in categories if category_items[c]]
    return f"Learned from {len(pairs)} expenses across {len(trained)} of {len(categories)} categories."


if __name__ == "__main__":
    print(train())
