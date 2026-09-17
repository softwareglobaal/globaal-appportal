#!/usr/bin/env python3
"""Mapnaam voor een Plaud-opname: JJJJ-MM-DD UUMM <titel>, Belgische tijd.

Afspraak 17-09-2026 (Mehdi): geen jaarmap meer, de datum rangschikt zichzelf;
de naam die Plaud aan de opname geeft blijft staan. Plaud zet er zelf een
"MM-DD " voor; dat is dubbel met de datum en gaat eraf. Een opname zonder
eigen titel heet in Plaud alleen een tijdstempel; die krijgt "zonder titel".
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
MAX = 110  # ruim onder de padgrens van Dropbox

# Plaud-tijdstempel als naam: "2026-09-10 14:18:13" of "20260910 141813"
ALLEEN_TIJD = re.compile(r"^\s*\d{4}[-/ ]?\d{2}[-/ ]?\d{2}[ T]\d{2}[:.]?\d{2}([:.]?\d{2})?\s*$")
VOORVOEGSEL = re.compile(r"^\s*\d{1,2}-\d{1,2}\s+")          # "09-17 "
VERBODEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')               # Dropbox en macOS


def belgisch(start_at_utc: str) -> datetime:
    """start_at van Plaud is UTC zonder zone-achtervoegsel."""
    t = datetime.fromisoformat(start_at_utc.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    return t.astimezone(BRUSSEL)


def titel_van(naam: str) -> str:
    n = (naam or "").strip()
    if not n or ALLEEN_TIJD.match(n):
        return "zonder titel"
    n = VOORVOEGSEL.sub("", n)
    n = VERBODEN.sub(" ", n).replace("–", "-")
    n = re.sub(r"\s+", " ", n).strip(" .-")
    return n or "zonder titel"


def mapnaam(opname: dict) -> str:
    t = belgisch(opname["start_at"])
    naam = f"{t:%Y-%m-%d %H%M} {titel_van(opname.get('name'))}"
    if len(naam) > MAX:
        naam = naam[:MAX].rstrip(" ,;-") + "…"
    return naam


if __name__ == "__main__":
    proef = [
        {"start_at": "2026-09-17T12:14:41", "name": "09-17 Vergadering: Operationele en Financiële Bespreking"},
        {"start_at": "2026-09-10T17:18:13", "name": "2026-09-10 14:18:13"},
        {"start_at": "2026-09-12T11:00:36", "name": "09-12 Vergadering: Restauratiemaatregelen woning – buitenruimte, constructieve ingrepen, ramen en vergunningen"},
        {"start_at": "2026-01-15T08:16:14", "name": "01-15 Telefoon met KBC"},
    ]
    for p in proef:
        print(mapnaam(p))
