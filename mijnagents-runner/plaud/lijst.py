"""Eén actuele lijst van alle Plaud-opnames (verbeteropdracht v1.0, §9).

De lijst staat bij het archief zelf, niet in de repo: `<archief>/00 plaud_lijst.json`, met

    {"meta": {"versie", "opgehaald", "bron", "volledig", "aantal", "nieuwste_start"},
     "opnames": [{id, name, start_at, duration, serial_number, ...}]}

Ophaler, bouwer, controle, pakketten en De Plaudwacht lezen alleen deze lijst. Ze wordt atomair
vervangen. Een volledige ophaling (alle pagina's van de API) vervangt de lijst; een gedeeltelijke
(bv. via de koppeling) voegt samen, waarbij de verse waarden winnen. Aanvullen vanuit de lijst
vult alleen wat ontbreekt en vervangt nooit verse metadata.

Python 3.9-compatibel.
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import archief  # noqa: E402

VERSIE = 1
NAAM = "00 plaud_lijst.json"
OUDE_REPO_LIJST = Path(__file__).parent / "plaud_lijst.json"


def pad(doel):
    return Path(doel) / NAAM


def lees(doel):
    """{"meta": ..., "opnames": [...]}; leest ook de oude vorm (een kale lijst) en, zolang de lijst
    nog niet bij het archief staat, de oude kopie in de repo."""
    for p in (pad(doel), OUDE_REPO_LIJST):
        data = archief.lees_json(p)
        if isinstance(data, list):
            return {"meta": {"versie": 0, "opgehaald": None, "bron": str(p), "volledig": False, "aantal": len(data)},
                    "opnames": data}
        if isinstance(data, dict) and isinstance(data.get("opnames"), list):
            return data
    return {"meta": {"versie": VERSIE, "opgehaald": None, "bron": "leeg", "volledig": False, "aantal": 0}, "opnames": []}


def per_id(doel):
    return {o.get("id"): o for o in lees(doel)["opnames"] if o.get("id")}


def schrijf(doel, opnames, bron, volledig):
    """Volledig: de nieuwe momentopname vervangt de oude. Anders samenvoegen; verse waarden winnen."""
    if not volledig:
        bestaand = per_id(doel)
        for o in opnames:
            bestaand[o["id"]] = {**bestaand.get(o["id"], {}), **{k: v for k, v in o.items() if v is not None}}
        opnames = list(bestaand.values())
    opnames = sorted(opnames, key=lambda o: o.get("start_at") or "", reverse=True)
    meta = {"versie": VERSIE, "opgehaald": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bron": bron,
            "volledig": bool(volledig), "aantal": len(opnames),
            "nieuwste_start": opnames[0].get("start_at") if opnames else None}
    archief.schrijf_json(pad(doel), {"meta": meta, "opnames": opnames})
    return meta


def aanvul(op, doel):
    """Vul ontbrekende velden van een opname aan uit de lijst. Wat er al staat, blijft staan."""
    rec = per_id(doel).get(op.get("id") or op.get("plaud_id"))
    if not rec:
        return op
    uit = dict(op)
    for k, v in rec.items():
        if uit.get(k) in (None, ""):
            uit[k] = v
    return uit
