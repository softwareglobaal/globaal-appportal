"""Embedden, met twee ruggen om uit te kiezen.

Standaard draait een lokaal model op de processor: geen sleutel, geen kosten per
document, en meertalig omdat de bronnen Nederlands zijn. Dat is de goede keuze bij
het bouwen van een kennisbank op een machine die het aankan.

Op een krappe server is dat model te zwaar (241 MB plus onnxruntime plus het
geheugen tijdens het rekenen). Daar staat de rug op `openai`: het corpus is dan
met OpenAI ingelezen en een zoekvraag kost alleen een lichte API-aanroep. Welke
rug het is bepaalt de omgevingsvariabele EMBED_BACKEND; corpus en vraag moeten
altijd door dezelfde rug, want vectoren van twee modellen zijn onvergelijkbaar.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

BACKEND = os.environ.get("EMBED_BACKEND", "fastembed").lower()

if BACKEND == "openai":
    MODEL = "text-embedding-3-small"
    DIM = 1536
else:
    MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    DIM = 384

CACHE = Path(__file__).resolve().parent.parent / ".modelcache"
_model = None
_client = None


def _fastembed():
    global _model
    if _model is None:
        CACHE.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("FASTEMBED_CACHE_PATH", str(CACHE))
        os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
        from fastembed import TextEmbedding
        _model = TextEmbedding(MODEL, cache_dir=str(CACHE))
    return _model


def _openai():
    global _client
    if _client is None:
        from openai import OpenAI
        _client = OpenAI()      # sleutel uit OPENAI_API_KEY
    return _client


def _ruw(teksten: list[str]) -> np.ndarray:
    if BACKEND == "openai":
        # In stukken, want de API neemt niet onbeperkt veel invoer per aanroep.
        uit = []
        for i in range(0, len(teksten), 256):
            deel = _openai().embeddings.create(
                model=MODEL, input=teksten[i:i + 256])
            uit.extend(r.embedding for r in deel.data)
        return np.asarray(uit, dtype=np.float32)
    return np.asarray(list(_fastembed().embed(teksten)), dtype=np.float32)


def embed(teksten: list[str]) -> np.ndarray:
    """Genormaliseerde vectoren, een rij per tekst.

    Normaliseren gebeurt hier en niet bij het zoeken: dan is het inproduct de
    cosinus en hoeft er bij elke vraag niets meer te worden gedeeld.
    """
    if not teksten:
        return np.zeros((0, DIM), dtype=np.float32)
    v = _ruw(teksten)
    normen = np.linalg.norm(v, axis=1, keepdims=True)
    normen[normen == 0] = 1.0
    return v / normen


def embed_een(tekst: str) -> np.ndarray:
    return embed([tekst])[0]


def naar_blob(v: np.ndarray) -> bytes:
    return np.asarray(v, dtype=np.float32).tobytes()


def uit_blob(b: bytes) -> np.ndarray:
    return np.frombuffer(b, dtype=np.float32)
