"""Eén lezer van de locatiecontext voor alle agents (opdracht v1.4, 05-10-2026).

Waarom: De Plaudwacht, De Archivaris en het bord lazen elk het markdown-dagboek van het bord
en zochten daarin naar woorden als "bezoek". Dat las de oude telefoondagboeken van voor de
startgrens, miste het nieuwe formaat, en gaf "geparkeerd: Thuis" door als plaats van Mehdi.

Wat hier vastligt:
  - Alleen dagen uit de actieve meetreeks (locatie/bronbeleid.py). Een dag van voor
    3 oktober 2026 geeft niets, ook als er nog iets op het bord staat.
  - Alleen gestructureerde context uit /api/context van de tegel, nooit markdown.
  - Alleen positieve projectverblijven: 'auto bij project' met zekerheid waarschijnlijk of
    bevestigd. Thuis, ritten, meetgaten en wat Mehdi rechtzette (geen project, auto niet bij
    mij) leveren geen projectbezoek. Onzekere kandidaten staan apart en heten zo.
  - De rol staat erbij: de tracker in de auto bewijst waar de auto stond, niet waar Mehdi was.

Gebruik:
    import locatiecontext as LC
    v = LC.verblijf_op("2026-10-03T17:30")   # dict of None
    LC.beschrijf(v)                          # "auto bij project HARC 2443 (waarschijnlijk; bewijs: ...)"
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "..", "locatie"))
import bronbeleid  # noqa: E402

LOCATIE = os.environ.get("LOCATIE_URL", "http://127.0.0.1:3031")
BRUSSEL = ZoneInfo("Europe/Brussels")
_cache = {}


def _haal(pad):
    with urllib.request.urlopen(f"{LOCATIE}{pad}", timeout=30) as r:
        return json.load(r)


def context(dag):
    """De gestructureerde context van een dag, of None (voor de grens, of tegel onbereikbaar)."""
    dag = str(dag or "")[:10]
    if len(dag) != 10 or not bronbeleid.dag_toegestaan(dag):
        return None
    if dag not in _cache:
        try:
            d = _haal(f"/api/context?dag={dag}")
        except Exception:  # noqa: BLE001
            return None
        # Een antwoord zonder bronbeleid of van een andere dag vertrouwen we niet.
        if d.get("dag") != dag or not d.get("bronbeleid"):
            return None
        _cache[dag] = d
    return _cache[dag]


def _tijd(moment):
    if isinstance(moment, (int, float)):
        return datetime.fromtimestamp(moment, BRUSSEL)
    t = datetime.fromisoformat(str(moment))
    return t if t.tzinfo else t.replace(tzinfo=BRUSSEL)


def verblijf_op(moment, ook_kandidaten=False):
    """Het positieve projectverblijf waarin dit moment valt, of None.

    moment: ISO-tijd (Brussel als er geen zone bij staat) of epoch. Met ook_kandidaten=True
    komt ook een onzekere kandidaat terug, met positief=False; nooit als vastgesteld bezoek."""
    try:
        t = _tijd(moment)
    except (TypeError, ValueError):
        return None
    d = context(t.astimezone(BRUSSEL).date().isoformat())
    if not d:
        return None
    lijsten = d.get("verblijven") or []
    if ook_kandidaten:
        lijsten = lijsten + (d.get("kandidaten") or [])
    for v in lijsten:
        van = _tijd(v["aankomst"])
        tot = _tijd(v["vertrek"]) if v.get("vertrek") else datetime.now(BRUSSEL)
        if van <= t <= tot and (v.get("positief") or ook_kandidaten):
            return v
    return None


def beschrijf(v):
    """Een korte, eerlijke zin voor een prompt of verslag; '' als er niets is."""
    if not v:
        return ""
    wie = "auto" if v.get("rol") == "auto" else "draagbare tracker"
    if v.get("positief") and v.get("project"):
        p = v["project"]
        zin = "%s bij project %s %s" % (wie, p.get("firma") or "", p.get("nummer"))
    else:
        kand = ", ".join("%s %s" % (k.get("firma") or "?", k.get("nummer")) for k in v.get("kandidaten") or [])
        zin = "%s mogelijk bij een van: %s (niet bewezen)" % (wie, kand or "onbekend")
    return "%s (zekerheid %s; bewijs: %s; %s tot %s)%s" % (
        zin, v.get("zekerheid"), v.get("bewijs"), str(v.get("aankomst"))[11:16],
        str(v.get("vertrek") or "nu")[11:16] if v.get("vertrek") else "nu",
        "; auto is geen bewijs van persoonlijke aanwezigheid" if wie == "auto" else "")


def gestructureerd(v):
    """Wat een agent bewaart: rol, project (firma, nummer, uuid, link), zekerheid, reden, bewijs, tijd."""
    if not v:
        return None
    p = v.get("project") or {}
    return {"bron": v.get("bron"), "rol": v.get("rol"), "positief": bool(v.get("positief")),
            "firma": p.get("firma"), "nummer": p.get("nummer"), "project_id": p.get("project_id"),
            "link": p.get("link"), "zekerheid": v.get("zekerheid"), "reden": v.get("reden"),
            "bewijs": v.get("bewijs"), "aankomst": v.get("aankomst"), "vertrek": v.get("vertrek"),
            "kandidaten": [{"firma": k.get("firma"), "nummer": k.get("nummer")} for k in v.get("kandidaten") or []],
            "betekenis": "plaats van de auto, geen bewijs van persoonlijke aanwezigheid"
            if v.get("rol") == "auto" else "plaats van de gedragen tracker"}


def dag_heeft_dagboek(dag, items):
    """Staat er op het bord een locatiedagboek voor precies deze dag, uit de actieve reeks?"""
    dag = str(dag or "")[:10]
    if not bronbeleid.dag_toegestaan(dag):
        return False
    for it in items or []:
        if (it.get("soort") == "locatie" or it.get("van") == "locatie-wacht") and (it.get("sleutel") or "")[:10] == dag \
                and (it.get("titel") or "").startswith("Locatielogboek %s" % dag):
            return True
    return False
