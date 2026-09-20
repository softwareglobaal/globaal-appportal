"""Vaste plaatsen van Mehdi, uit werkwijze/adressen.json.

De Agendawacht gebruikt dit als een afspraak geen adres in de agenda heeft: staat er
"zwemles" of "oma" in de titel, dan weet hij toch waar dat is. Alleen lezen.

    adresboek.zoek("Mehdi: Zwemles Lara")  -> ("Kerkstraat 1, 3000 Leuven", "zwemschool Lara")
"""
import json
import os

BESTAND = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "werkwijze", "adressen.json")


def plaatsen():
    try:
        with open(BESTAND, encoding="utf-8") as f:
            return json.load(f).get("plaatsen", [])
    except (OSError, ValueError):
        return []


def zoek(tekst):
    """Geeft (adres, naam) van de eerste plaats die in de tekst voorkomt, of (None, None).
    Plaatsen zonder ingevuld adres slaat hij over; die meldt de wacht als ontbrekend."""
    t = (tekst or "").lower()
    if not t:
        return None, None
    for p in plaatsen():
        if not (p.get("adres") or "").strip():
            continue
        namen = [p["naam"]] + list(p.get("ook") or [])
        for n in namen:
            if n and n.lower() in t:
                return p["adres"], p["naam"]
    return None, None


def onvolledig():
    """Plaatsen die nog geen adres hebben."""
    return [p["naam"] for p in plaatsen() if not (p.get("adres") or "").strip()]
