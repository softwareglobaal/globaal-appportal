#!/usr/bin/env python3
"""Mapnaam voor een Plaud-opname: JJJJ-MM-DD UUMM <titel>, Belgische tijd.

Afspraak 17-09-2026 (Mehdi): geen jaarmap meer, de datum rangschikt zichzelf;
de naam die Plaud aan de opname geeft blijft staan. Plaud zet er zelf een
"MM-DD " voor; dat is dubbel met de datum en gaat eraf. Een opname zonder
eigen titel heet in Plaud alleen een tijdstempel; die krijgt "zonder titel".

Waar een opname staat en of ze compleet is, beslist archief.py (één resolver op
Plaud-id, verbeteropdracht v1.0 §5). map_van en compleet hieronder zijn alleen nog
doorgeefluiken voor oudere aanroepers.

Python 3.9-compatibel.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import contract  # noqa: E402

MAX = 110  # ruim onder de padgrens van Dropbox

# Plaud-tijdstempel als naam: "2026-09-10 14:18:13" of "20260910 141813"
ALLEEN_TIJD = re.compile(r"^\s*\d{4}[-/ ]?\d{2}[-/ ]?\d{2}[ T]\d{2}[:.]?\d{2}([:.]?\d{2})?\s*$")
VOORVOEGSEL = re.compile(r"^\s*\d{1,2}-\d{1,2}\s+")          # "09-17 "
VERBODEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')               # Dropbox en macOS


def belgisch(start_at_utc):
    """Plaud-tijd (UTC, met of zonder zone) naar Brussel."""
    return contract.brussel(start_at_utc)


def titel_van(naam):
    n = (naam or "").strip()
    if not n or ALLEEN_TIJD.match(n):
        return "zonder titel"
    n = VOORVOEGSEL.sub("", n)
    n = VERBODEN.sub(" ", n).replace("–", "-")
    n = re.sub(r"\s+", " ", n).strip(" .-")
    return n or "zonder titel"


def mapnaam(opname, uniek=False):
    """Met uniek=True komt het korte Plaud-id erachter. Nodig omdat naamloze
    opnames in dezelfde minuut anders dezelfde map zouden krijgen: op
    17-09-2026 botsten 24 opnames op 10 namen. Accepteert de Plaud-vorm
    (start_at, name, id) en de contractvorm (start_utc, naam_in_plaud, plaud_id)."""
    start = opname.get("start_utc") or opname.get("start_at")
    t = belgisch(start)
    titel = titel_van(opname.get("name") if opname.get("name") is not None else opname.get("naam_in_plaud"))
    naam = "%s %s" % (t.strftime("%Y-%m-%d %H%M"), titel)
    pid = (opname.get("plaud_id") or opname.get("id") or "").replace("of_", "")
    staart = " [%s]" % pid[:6] if uniek else ""
    if len(naam) + len(staart) > MAX:
        naam = naam[:MAX - len(staart)].rstrip(" ,;-") + "…"
    return naam + staart


def map_van(opname, doel):
    import archief
    return archief.resolve(opname, doel)


def _index(doel):
    """plaud_id (met en zonder 'of_') -> map. Voor benaming_toepassen.py."""
    import archief
    ids, _ = archief.index(doel)
    uit = {}
    for pid, m in ids.items():
        uit[pid] = m
        uit[pid[3:]] = m
    return uit


def compleet(opname, doel):
    """Strikt: alleen een opname met metadata, transcript, markdown en definitieve audio.
    Een opname die op haar transcript wacht is níet compleet (zie archief.toestand)."""
    import archief
    try:
        m = archief.resolve(opname, doel)
    except contract.Herstel:
        return False
    return archief.toestand(m, opname.get("plaud_id") or opname.get("id"))["staat"] == "compleet"


if __name__ == "__main__":
    proef = [
        {"start_at": "2026-09-17T12:14:41", "name": "09-17 Vergadering: Operationele en Financiële Bespreking"},
        {"start_at": "2026-09-10T17:18:13", "name": "2026-09-10 14:18:13"},
        {"start_at": "2026-01-15T08:16:14", "name": "01-15 Telefoon met KBC"},
    ]
    for p in proef:
        print(mapnaam(p))
