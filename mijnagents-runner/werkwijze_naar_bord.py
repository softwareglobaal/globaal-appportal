#!/usr/bin/env python3
"""Een werkwijze uit werkwijze/<naam>.md naar het bord zetten.

Het bord is de waarheid (norm N6). Het bestand in werkwijze/ is het zaad: de
eerste versie, en daarna een kopie die kan verouderen. Dit is het gereedschap om
ze weer gelijk te zetten wanneer de repo de nieuwere tekst heeft, bijvoorbeeld
nadat Claude Code een werkwijze heeft uitgebreid.

    werkwijze_naar_bord.py ontwikkelaar            toont het verschil, schrijft niets
    werkwijze_naar_bord.py ontwikkelaar --zet      zet het zaad op het bord
    werkwijze_naar_bord.py bode --voorstel         zet het zaad als voorstel op het bord
    werkwijze_naar_bord.py --verschillen           welke agents lopen uit elkaar

Schrijft nooit zonder --zet of --voorstel. Wie het bord overschrijft, gooit weg wat
Mehdi daar misschien zelf heeft bijgewerkt: kijk dus altijd eerst naar het verschil.

De werkwijzen van De Bode, De Regisseur en De Zoomwacht zet het nooit (RZ4-07,
herstelcontrole van Codex, 22-10-2026; ontwerp regie-zoom 13.5, vraag 6): die gaan
alleen als voorstel met het runbook werkwijze-bijwerken naar het bord, en Mehdi
keurt elk goed met een klik. Tot dan kon --zet zo BUNDELEN aanzetten zonder die
klik. Het verschil tonen blijft voor hen werken; --zet geeft exit 2.
--voorstel (uitrol van release 1, 22-10-2026) zet dat voorstel klaar: van De
Regisseur, zoals zijn eigen tool voorstel, met als parameters de agent, de
volledige tekst van het zaad en het mandaat (de kaarttekst, zoals --zet die zet;
het runbook neemt het mee). Het bord zelf verandert pas na de klik; daarna zegt
werkwijze_naar_bord.py <naam> "zaad en bord zijn al gelijk". Zijn ze al gelijk,
dan komt er geen voorstel.
"""
import argparse
import difflib
import os
import re
from pathlib import Path
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

# RZ4-07: alleen via een voorstel met het runbook werkwijze-bijwerken en een klik van Mehdi
ALLEEN_VIA_VOORSTEL = frozenset({"bode", "regisseur", "zoom-wacht"})
VIA_VOORSTEL = ("alleen via een voorstel met het runbook werkwijze-bijwerken en een klik van Mehdi "
                "(ontwerp regie-zoom 13.5, vraag 6; RZ4-07)")


def zaadpad(naam):
    return os.path.join(HIER, "werkwijze", f"{naam}.md")


def genormaliseerd(s):
    return "\n".join(r.rstrip() for r in (s or "").strip().splitlines())


def mandaat_uit(tekst):
    """De eerste alinea onder ## Mandaat is ook de kaarttekst op het bord."""
    m = re.search(r"(?ms)^## Mandaat\s*\n\s*(.+?)(?=\n\s*\n|\n## |\Z)", tekst)
    if not m:
        return ""
    return " ".join(m.group(1).split())


def haal_bord(naam):
    return bord.call(f"/api/agent/{naam}/werkwijze")


def agents():
    return [a["naam"] for a in bord.call("/api/overzicht").get("agents", [])]


def verschil(naam, toon=True):
    p = zaadpad(naam)
    if not os.path.exists(p):
        return None
    zaad = genormaliseerd(Path(p).read_text(encoding="utf-8"))
    kaart = haal_bord(naam)
    opbord = genormaliseerd(kaart.get("werkwijze"))
    mandaat = mandaat_uit(zaad)
    if zaad == opbord and (not mandaat or mandaat == genormaliseerd(kaart.get("mandaat"))):
        return False
    if toon:
        for regel in difflib.unified_diff(opbord.splitlines(), zaad.splitlines(),
                                          fromfile=f"{naam} op het bord", tofile=f"{naam} in de repo",
                                          lineterm="", n=1):
            print(regel)
    return True


def zet(naam):
    if naam in ALLEEN_VIA_VOORSTEL:
        return False, VIA_VOORSTEL
    tekst = Path(zaadpad(naam)).read_text(encoding="utf-8")
    inhoud = {"werkwijze": tekst, "overschrijf": True}
    if mandaat_uit(tekst):
        inhoud["mandaat"] = mandaat_uit(tekst)
    uit = bord.call(f"/api/agent/{naam}/werkwijze", inhoud)
    return uit.get("ok"), uit.get("reden", "")


def voorstel(naam):
    """Het zaad als voorstel met het runbook werkwijze-bijwerken (RZ4-07, de route van ontwerp 13.5 vraag 6). Het komt
    van De Regisseur, zoals zijn eigen tool voorstel: een hartslag met het voorstel erbij, zonder noodlijst, zodat zijn
    noden blijven zoals ze zijn. Het bord houdt hetzelfde voorstel dat al open staat geen tweede keer bij. Geeft (ok,
    uitleg); de uitleg noemt nooit de tekst zelf."""
    tekst = Path(zaadpad(naam)).read_text(encoding="utf-8")
    versie = re.search(r"(?m)^Versie\s+([0-9][0-9.]*)", tekst)
    actie = f"Werkwijze van {naam} bijwerken naar het zaad uit de repo" + (f" (versie {versie.group(1)})" if versie else "")
    parameters = {"agent": naam, "werkwijze": tekst}
    if mandaat_uit(tekst):
        parameters["mandaat"] = mandaat_uit(tekst)      # de kaarttekst, zoals --zet die zet; het runbook neemt ze mee
    v = {"actie": actie, "reden": "nieuwe werkwijze; geldt pas na je klik (ontwerp regie-zoom 13.5, vraag 6; RZ4-07)",
         "doel": "", "runbook": "werkwijze-bijwerken", "parameters": parameters}
    uit = bord.call("/agent-status", {"naam": "regisseur", "status": "waakt", "taak": "voorstel voor Mehdi",
                                      "detail": actie[:100], "voorstel": v})
    return bool((uit or {}).get("ok")), actie


def main(argv=None):
    p = argparse.ArgumentParser(description="Zet een werkwijze uit de repo op het bord.")
    p.add_argument("naam", nargs="?")
    doe = p.add_mutually_exclusive_group()
    doe.add_argument("--zet", action="store_true", help="schrijven; zonder dit toont hij alleen het verschil")
    doe.add_argument("--voorstel", action="store_true",
                     help="het zaad als voorstel met het runbook werkwijze-bijwerken; geldt pas na de klik van Mehdi")
    p.add_argument("--verschillen", action="store_true", help="welke agents lopen uit elkaar")
    a = p.parse_args(argv)

    if a.verschillen:
        uit_elkaar = [n for n in agents() if verschil(n, toon=False)]
        print("\n".join(uit_elkaar) if uit_elkaar else "Alle werkwijzen zijn gelijk aan het bord.")
        return 0 if not uit_elkaar else 1

    if not a.naam:
        p.error("geef een agentnaam, of gebruik --verschillen")
    if not os.path.exists(zaadpad(a.naam)):
        print(f"geen zaad gevonden: {zaadpad(a.naam)}", file=sys.stderr)
        return 2

    anders = verschil(a.naam)
    if not anders:
        print(f"{a.naam}: zaad en bord zijn al gelijk.")
        return 0
    if a.voorstel:
        ok, actie = voorstel(a.naam)
        print(f"\n{a.naam}: voorstel op het bord ({actie}); het bord verandert pas na de klik, wacht op de klik van Mehdi."
              if ok else f"\n{a.naam}: het bord nam het voorstel niet aan; er staat niets")
        return 0 if ok else 1
    if a.naam in ALLEEN_VIA_VOORSTEL:
        # RZ4-07: het verschil staat hierboven; zetten gaat niet met dit gereedschap
        if a.zet:
            print(f"\n{a.naam}: niet gezet, {VIA_VOORSTEL}.", file=sys.stderr)
            return 2
        print(f"\n{a.naam}: het bovenstaande is het verschil; op het bord {VIA_VOORSTEL}.")
        return 1
    if not a.zet:
        print(f"\n{a.naam}: het bovenstaande zou naar het bord gaan. Draai met --zet om het te doen.")
        return 1
    ok, reden = zet(a.naam)
    print(f"{a.naam}: op het bord gezet." if ok else f"{a.naam}: niet gezet, {reden}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
