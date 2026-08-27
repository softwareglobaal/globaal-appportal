"""Zet de vectoren van een kennisbank om naar OpenAI-embeddings.

De kennisbank is lokaal gebouwd met een lokaal model (384 dimensies). Op de
server draait dat model niet; daar zoekt de vitrine via de OpenAI-API. Corpus en
zoekvraag moeten door dezelfde rug, dus worden hier alle fragmenten opnieuw
ingelezen met text-embedding-3-small.

Eenmalig, bij het uitrollen. Draaien met OPENAI_API_KEY gezet en
EMBED_BACKEND=openai:

    EMBED_BACKEND=openai python converteer_openai.py --db /data/kennisbank.db
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

os.environ.setdefault("EMBED_BACKEND", "openai")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kennisbank import vectoren  # noqa: E402


def met_context(tekst: str, kop_pad_json: str) -> str:
    """Reproduceert exact wat bij het bouwen is geëmbed (Fragment.met_context)."""
    kop_pad = json.loads(kop_pad_json or "[]")
    pad = " > ".join(p for p in kop_pad if p)
    return f"{pad}\n\n{tekst}" if pad else tekst


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", required=True, type=Path)
    args = p.parse_args()

    if vectoren.BACKEND != "openai":
        sys.exit("zet EMBED_BACKEND=openai voordat je dit draait")

    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rijen = db.execute(
        "SELECT id, tekst, kop_pad FROM fragment ORDER BY id").fetchall()
    print(f"{len(rijen)} fragmenten opnieuw inlezen met {vectoren.MODEL}…",
          flush=True)

    teksten = [met_context(r["tekst"], r["kop_pad"]) for r in rijen]
    vecs = vectoren.embed(teksten)          # genormaliseerd, 1536-dim
    if len(vecs) != len(rijen):
        sys.exit(f"kreeg {len(vecs)} vectoren voor {len(rijen)} fragmenten")

    db.execute("DELETE FROM vector")
    for r, v in zip(rijen, vecs):
        db.execute("INSERT INTO vector (fragment_id, waarden) VALUES (?,?)",
                   (r["id"], vectoren.naar_blob(v)))
    db.execute("UPDATE document SET embedmodel=?, dim=?",
               (vectoren.MODEL, vectoren.DIM))
    db.commit()
    db.close()
    print(f"klaar: {len(vecs)} vectoren van {vectoren.DIM} dimensies weggeschreven.",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
