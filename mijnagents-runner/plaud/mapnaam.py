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


def mapnaam(opname: dict, uniek: bool = False) -> str:
    """Met uniek=True komt het korte Plaud-id erachter. Nodig omdat naamloze
    opnames in dezelfde minuut anders dezelfde map zouden krijgen: op
    17-09-2026 botsten 24 opnames op 10 namen."""
    t = belgisch(opname["start_at"])
    naam = f"{t:%Y-%m-%d %H%M} {titel_van(opname.get('name'))}"
    staart = f" [{(opname.get('id') or '').replace('of_', '')[:6]}]" if uniek else ""
    if len(naam) + len(staart) > MAX:
        naam = naam[:MAX - len(staart)].rstrip(" ,;-") + "…"
    return naam + staart


def map_van(opname: dict, doel) -> "Path":
    """De map van deze opname: de gewone naam, of de variant met het korte id
    als de gewone map van een andere opname blijkt te zijn."""
    from pathlib import Path
    import json as _json
    doel = Path(doel)
    m = doel / mapnaam(opname)
    g = m / "gesprek.json"
    if g.exists():
        try:
            if _json.loads(g.read_text(encoding="utf-8")).get("plaud_id") not in (None, opname.get("id")):
                return doel / mapnaam(opname, uniek=True)
        except Exception:  # noqa: BLE001
            pass
    return m


def compleet(opname: dict, doel) -> bool:
    """Compleet = de map van deze opname heeft een geluidsopname en een
    transcript (of het merkbestand dat Plaud er geen heeft)."""
    m = map_van(opname, doel)
    if not m.is_dir():
        return False
    audio = [p for p in m.glob("opname.*") if p.stat().st_size > 1000]
    return bool(audio) and ((m / "transcript.json").exists() or (m / "geen-transcript.txt").exists())


if __name__ == "__main__":
    proef = [
        {"start_at": "2026-09-17T12:14:41", "name": "09-17 Vergadering: Operationele en Financiële Bespreking"},
        {"start_at": "2026-09-10T17:18:13", "name": "2026-09-10 14:18:13"},
        {"start_at": "2026-09-12T11:00:36", "name": "09-12 Vergadering: Restauratiemaatregelen woning – buitenruimte, constructieve ingrepen, ramen en vergunningen"},
        {"start_at": "2026-01-15T08:16:14", "name": "01-15 Telefoon met KBC"},
    ]
    for p in proef:
        print(mapnaam(p))
