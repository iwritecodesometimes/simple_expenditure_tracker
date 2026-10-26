import os

import numpy as np
import torch
from sentence_transformers import SentenceTransformer, util

from config import load_categories
from train import EMBEDDINGS_PATH, MODEL_NAME

model = SentenceTransformer(MODEL_NAME)


def _load_embeddings():
    categories = load_categories()
    if os.path.exists(EMBEDDINGS_PATH):
        data = np.load(EMBEDDINGS_PATH)
        saved_cats = list(data["categories"])
        saved_embeddings = data["embeddings"]
        if saved_cats == categories:
            return categories, torch.tensor(saved_embeddings, dtype=torch.float32)
        # Trained embeddings are stale (categories changed) — rebuild for known, encode new ones
        emb_list = []
        for cat in categories:
            if cat in saved_cats:
                emb_list.append(saved_embeddings[saved_cats.index(cat)])
            else:
                emb_list.append(model.encode(cat))
        return categories, torch.tensor(np.array(emb_list), dtype=torch.float32)
    return categories, model.encode(categories, convert_to_tensor=True)


def suggest_categories(item_name: str, top_k: int = 3) -> list[str]:
    categories, embeddings = _load_embeddings()
    item_embedding = model.encode(item_name, convert_to_tensor=True)
    scores = util.cos_sim(item_embedding, embeddings)[0]
    top_indices = scores.argsort(descending=True)[:top_k]
    return [categories[i] for i in top_indices]
