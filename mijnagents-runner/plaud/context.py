"""Gestructureerde context bij een opname (verbeteropdracht v1.0, §7).

Tot 12-10-2026 plakte De Plaudwacht agenda en locatie achter tekst[:6000], en knipte de herkenner
de som opnieuw op 6000 tekens: bij een lang transcript verdween alle context, de regel over de
openingszin inbegrepen. Nu gaan transcriptbegin, agenda, locatie, openingszinregel en bronbewijzen
als afzonderlijke velden mee; alleen de transcripttekst wordt begrensd.

Afspraken tellen alleen als ze het opnametijdstip overlappen. Dezelfde dag op een ander uur is geen
bevestiging.
"""
import json
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

BRUSSEL = ZoneInfo("Europe/Brussels")
MARGE = timedelta(minutes=10)
OPENINGSZIN_REGEL = ("Lees de eerste minuut op Mehdi's openingszin (waar, met wie, wat). Sprekers heten 'Speaker N'; "
                     "herleid ze uit wat ze zeggen. Een opname uit het gedeelde Plaud-account bewijst niet wie opnam "
                     "of dat Mehdi erbij was.")


def _tijd(w):
    if not w:
        return None
    try:
        t = datetime.fromisoformat(str(w).replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(str(w)) <= 10:
        return None                       # hele-dagafspraak: geen tijdstip, geen bewijs
    return t if t.tzinfo else t.replace(tzinfo=BRUSSEL)


def venster(start_utc, duur_minuten):
    s = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    return s, s + timedelta(minutes=float(duur_minuten or 0) or 1)


def afspraken_op(items, start_utc, duur_minuten):
    """Agenda-items (klaarzet soort=afspraak) die het opnamevenster overlappen, met marge."""
    s, e = venster(start_utc, duur_minuten)
    uit = []
    for it in items or []:
        if it.get("soort") != "afspraak":
            continue
        inhoud = it.get("inhoud") or {}
        if isinstance(inhoud, str):
            try:
                inhoud = json.loads(inhoud) if inhoud.startswith("{") else {}
            except ValueError:
                inhoud = {}
        a, b = _tijd(inhoud.get("start")), _tijd(inhoud.get("einde"))
        if not a or not b:
            continue
        if a < e + MARGE and b > s - MARGE:
            uit.append({"titel": inhoud.get("titel") or it.get("titel", ""), "start": inhoud.get("start"), "einde": inhoud.get("einde"),
                        "firma": inhoud.get("firma") or "", "nummer": inhoud.get("nummer") or "", "agenda": inhoud.get("agenda") or ""})
    return uit


def voor_herkenning(afspraken, locatie, bronbewijzen, toestel="onbekend", account="onbekend"):
    return {"agenda_overlappend": afspraken, "locatie": locatie, "openingszin_regel": OPENINGSZIN_REGEL,
            "bronbewijzen": bronbewijzen, "toestel": toestel, "account": account,
            "let_op": "gedeeld Plaud-account: opnemer en aanwezigheid van Mehdi zijn niet bewezen"}
