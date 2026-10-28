"""Afgeschermde proef van De Deontologiewacht op echte stukken (akkoord van Mehdi, 28-10-2026).

De proef leest een map met stukken (.docx, .pdf of .txt), toetst elk stuk, maakt een stempel met een proefsleutel en
vraagt de grendel of het stuk zou vertrekken. Er vertrekt niets: geen mail, geen Codex of Gemini, geen bord. De uitvoer
noemt per stuk alleen de bestandsnaam, de kleur, de regelcodes per kleur en het antwoord van de grendel, nooit de tekst
van het stuk, zodat het overzicht geen namen of bedragen van klanten bevat.

    cd mijnagents-runner && python3 -m deontologie.proef MAP --soort contract
    cd mijnagents-runner && python3 -m deontologie.proef MAP --soort werfverslag [--uitleg]

Met `--uitleg` komt per oranje of rood punt ook de reden uit het verslag erbij, zonder de plaats in het stuk en met elk
getal vervangen door #, zodat er geen bedrag of oppervlakte in staat. Gebruik ook dat alleen lokaal.
"""
import argparse
import re
import secrets
import subprocess
import sys
from pathlib import Path

from . import masters as M
from . import stempel as S
from . import verslag as V
from . import werfverslagen as W

SOORTEN = ("contract", "werfverslag")


def lees(pad):
    pad = Path(pad)
    if pad.suffix.lower() == ".pdf":
        return subprocess.run(["pdftotext", "-layout", str(pad), "-"], capture_output=True, text=True,
                              check=True).stdout
    return M.lees(pad)


def toets(soort, tekst):
    if soort == "contract":
        return V.maak("contract", M.toets_contract(tekst))
    return V.maak("werfverslag", W.toets_werfverslag(W.Werfverslag(tekst, eerste=eerste_verslag(tekst))),
                  elders=W.ELDERS)


def eerste_verslag(tekst):
    """True voor "werfverslag 01", False voor een later nummer, None als het nummer er niet staat."""
    m = re.search(r"werfverslag\s*(nr\.?|n°)?\s*0*(\d+)\b", tekst, re.I)
    return None if not m else m.group(2) == "1"


def grendel(inhoud, verslag):
    """Wat de grendel zou zeggen, met wegwerpsleutels die na de proef verdwijnen."""
    sleutel = secrets.token_hex(32)
    st = S.maak(inhoud, verslag, sleutel=sleutel)
    return S.controleer(inhoud, st, sleutel=sleutel, bevestigsleutel=secrets.token_hex(32))


def regel(naam, verslag, mag, uitleg=False):
    per = {k: sorted(p.code for p in verslag.punten if p.kleur == k) for k in (V.ROOD, V.ORANJE, V.GROEN)}
    uit = [f"| {naam} | {verslag.kleur} | {', '.join(per[V.ROOD]) or '-'} | {', '.join(per[V.ORANJE]) or '-'} | "
           f"{', '.join(per[V.GROEN]) or '-'} | {'ja' if mag[0] else 'nee: ' + mag[1]} |"]
    if uitleg:
        for p in sorted(verslag.punten, key=lambda p: (-V.ERNST[p.kleur], p.code)):
            if p.kleur != V.GROEN:
                uit.append(f"|  | {p.kleur} {p.code} | {re.sub(r'[0-9][0-9.,]*', '#', p.waarom)} |  |  |  |")
    return uit


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    a.add_argument("map")
    a.add_argument("--soort", choices=SOORTEN, required=True)
    a.add_argument("--uitleg", action="store_true")
    args = a.parse_args(argv)
    stukken = sorted(p for p in Path(args.map).iterdir() if p.suffix.lower() in (".docx", ".pdf", ".txt"))
    print("| Stuk | Kleur | Rood | Oranje | Groen | Zou vertrekken |")
    print("|---|---|---|---|---|---|")
    for pad in stukken:
        try:
            tekst = lees(pad)
            verslag = toets(args.soort, tekst)
            mag = grendel(pad.read_bytes(), verslag)
        except Exception as e:  # een stuk dat niet te lezen is, is een bevinding van de proef, geen stop
            print(f"| {pad.name} | fout | {type(e).__name__} |  |  |  |")
            continue
        print("\n".join(regel(pad.name, verslag, mag, args.uitleg)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
