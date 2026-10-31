#!/usr/bin/env python3
"""De Prijsonderzoeker (afdeling aankoop): zoekt op verzoek waar iets het best te koop is, in Europa of de wereld,
nieuw, refurbished, tweedehands of op een veiling, en zet een prijsverslag klaar voor Mehdi.

Een vraag komt op twee manieren binnen:
  - als klaargezet item voor deze agent (voor: prijsonderzoeker, soort: vraag), door De Regisseur of een collega;
    de cron kijkt elke tien minuten en neemt er hoogstens MAX_VRAGEN per ronde;
  - met de hand: prijsonderzoeker.py --vraag "tekst".

Per vraag: het taalmodel zoekt en leest de pagina's (aankoop/onderzoek.py), de code keurt elk aanbod en rekent het
totaal in euro met de ECB-koersen (aankoop/aanbod.py), en het verslag gaat naar Mehdi (aankoop/verslag.py). Een
aanbod zonder gelezen pagina, link, prijs of datum komt er nooit in.

Leest het web, verandert niets: geen aankoop, geen bod, geen contact met een verkoper, geen account.
--droog: zegt welke vragen klaarstaan en roept het model niet aan.
"""
import argparse
import hashlib
import os
import sys
import time
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)
import bord  # noqa: E402
import sleutelbron  # noqa: E402  de Anthropic-sleutel alleen uit ~/appportal/.env (T-0064)
from aankoop import aanbod as A  # noqa: E402
from aankoop import koersen as K  # noqa: E402
from aankoop import onderzoek as O  # noqa: E402
from aankoop import privacy as P  # noqa: E402
from aankoop import verslag as V  # noqa: E402

NAAM = "prijsonderzoeker"
ag = bord.Agent(NAAM)
MAX_VRAGEN = 2
RONDE_SECONDEN = 480            # binnen de 600 s die De Regisseur op een ronde wacht
MIN_SECONDEN_PER_VRAAG = 150    # minder tijd over: de vraag wacht op de volgende ronde
# Niet 'verslag' of 'signaal': die stuurt De Bode vanzelf door. Het antwoord komt via De Regisseur (overleg X2).
SOORT = "prijsverslag"


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


# Eerst ~/appportal/.env, zoals De Archivaris: de sleutel in ~/agents/.env gaf op 30-10-2026 een 401 (ongeldig),
# die in ~/appportal/.env werkt. setdefault: het eerste bestand dat een waarde heeft, wint.
laad_env("~/appportal/.env")
laad_env("~/agents/.env")
sleutelbron.zet_anthropic()                      # ANTHROPIC_API_KEY alleen uit ~/appportal/.env (T-0064)


def open_vragen():
    """De klaargezette prijsvragen voor mij, oudste eerst."""
    items = bord.klaargezet_voor(NAAM, status="klaar")
    vragen = [it for it in items if it.get("soort") == "vraag" and (it.get("inhoud") or it.get("titel"))]
    return sorted(vragen, key=lambda it: it.get("id") or 0)


def vingerafdruk(vraag, vandaag):
    """Wat het logboek van een vraag bewaart: nooit de vraag zelf (Codex X3), alleen een vingerafdruk."""
    return hashlib.sha256(f"{vandaag}:{vraag}".encode()).hexdigest()[:12]


def zet_klaar(vraag, titel, tekst, vandaag):
    ag.klaarzet([{"voor": "mehdi", "soort": SOORT, "sleutel": vandaag.isoformat(), "titel": titel,
                  "uniek": f"prijsonderzoek:{vingerafdruk(vraag, vandaag)}", "inhoud": tekst}])


def een_vraag(r, vraag, koersdatum, koersen, vandaag, deadline):
    """Een prijsvraag uitvoeren en het verslag klaarzetten. Geeft het aantal aanbiedingen in het verslag."""
    va = vingerafdruk(vraag, vandaag)
    soorten = P.gevonden(vraag)
    if soorten:
        # Niets naar het model: alleen de productvraag mag weg (X4, K6).
        ag.log("prijsvraag", "beslissing", f"vraag {va} niet verstuurd: persoonsgegevens", ", ".join(soorten))
        zet_klaar(vraag, "Prijsvraag niet verstuurd: persoonsgegevens", V.tegengehouden(soorten), vandaag)
        return 0
    vaste_eisen = A.eisen_uit_vraag(vraag)
    uit = O.onderzoek(vraag, r.werkwijze, vandaag.isoformat(), vaste_eisen, deadline)
    ag.log("prijsvraag", "bron", f"vraag {va}: {uit['zoekopdrachten']} zoekopdrachten, {len(uit['gelezen'])} pagina's "
                                 f"gelezen, {uit['tokens']} tokens (per beurt {uit.get('beurten')}), model {uit['model']}, "
                                 f"einde {uit['stop']}")
    if uit["stop"] == "plafond":
        r.nood("Prijsvraag gestopt op het plafond van tokens of tijd", wie="claude-code")
    g = uit["gegevens"]
    if g is None:
        ag.log("prijsvraag", "fout", f"vraag {va}: het model gaf geen leesbare gegevens", uit["tekst"][:3000])
        r.nood("Prijsvraag zonder leesbaar antwoord van het model", wie="claude-code")
        zet_klaar(vraag, "Prijsvraag zonder antwoord", "**Geen antwoord:** het zoeken gaf geen bruikbare gegevens. "
                  "Ik kocht, bood en contacteerde niets.", vandaag)
        return 0
    aanbiedingen = g.get("aanbiedingen") if isinstance(g.get("aanbiedingen"), list) else []
    for a in aanbiedingen:
        if isinstance(a, dict):
            a["gezien_op"] = vandaag.isoformat()     # gelezen in deze ronde; de datum zet de code, niet het model
    gelezen, niet_gelezen = O.alleen_gelezen(aanbiedingen, uit["gelezen"])
    eisen = list(dict.fromkeys(vaste_eisen + [str(e) for e in g.get("eisen") or [] if str(e).strip()]))
    g["eisen"] = eisen
    res = A.verwerk(gelezen, vandaag, koersen, eisen, paginas=uit["gelezen"])
    res["afgewezen"] = niet_gelezen + res["afgewezen"]
    tekst = V.maak(vraag, g, res, koersdatum, vandaag.isoformat())
    zet_klaar(vraag, V.titel(g, res), tekst, vandaag)
    ag.log("prijsvraag", "beslissing",
           f"vraag {va}: {len(res['goed'])} aanbiedingen in het verslag, {len(res['niet_compatibel'])} niet compatibel, "
           f"{len(res['afgewezen'])} afgewezen",
           [{"url": x["aanbod"].get("url"), "redenen": x["redenen"]} for x in res["afgewezen"]])
    # Het verslag zelf noemt de vraag; het staat in het klaargezette item, niet in het logboek (Codex X3, ronde 2).
    ag.log("prijsvraag", "melding", f"prijsverslag {va} klaargezet voor Mehdi (soort {SOORT})")
    return len(res["goed"])


def werk(r, hand_vraag=None, droog=False, begin=None):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return
    vragen = [{"id": None, "inhoud": hand_vraag}] if hand_vraag else open_vragen()
    if not vragen:
        r.detail = "geen open prijsvraag"
        return
    if droog:
        r.detail = f"droog: {len(vragen)} prijsvragen klaar, model niet aangeroepen"
        return
    # Een deadline voor de hele ronde: De Regisseur wacht hoogstens 600 seconden op mij (Codex X6).
    deadline = (begin or time.monotonic()) + RONDE_SECONDEN
    koersdatum, koersen = K.haal()
    r.bron("ECB-koersen", f"{koersdatum}: " + ", ".join(f"{m} {k}" for m, k in sorted(koersen.items())))
    if not koersen:
        r.nood("Wisselkoersen van de ECB niet gelezen", wie="claude-code")
    vandaag = date.today()
    gedaan = aanbod = 0
    for v in vragen[:MAX_VRAGEN]:
        if deadline - time.monotonic() < MIN_SECONDEN_PER_VRAAG:
            break                                   # blijft klaarstaan voor de volgende ronde
        tekst = str(v.get("inhoud") or v.get("titel")).strip()
        try:
            aanbod += een_vraag(r, tekst, koersdatum, koersen, vandaag, deadline)
        except Exception as e:  # noqa: BLE001  een mislukte vraag komt niet vanzelf terug (kosten)
            ag.log("prijsvraag", "fout", f"vraag {vingerafdruk(tekst, vandaag)}: {type(e).__name__}: {str(e)[:300]}")
            r.nood("Prijsvraag mislukt bij het zoeken", wie="claude-code")
        gedaan += 1
        if v.get("id"):
            bord.opgepakt(v["id"], NAAM)
    rest = len(vragen) - gedaan
    r.detail = f"{gedaan} prijsvragen afgewerkt, {aanbod} aanbiedingen in de verslagen" + (f", {rest} wachten" if rest else "")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="De Prijsonderzoeker")
    p.add_argument("--vraag", help="een prijsvraag met de hand, zonder het bord")
    p.add_argument("--droog", action="store_true", help="niet zoeken; zeggen wat klaarstaat")
    a = p.parse_args()
    begin = time.monotonic()
    with ag.ronde("prijsvraag" if a.vraag else "prijsvragen afwerken") as r:
        werk(r, a.vraag, a.droog, begin)
