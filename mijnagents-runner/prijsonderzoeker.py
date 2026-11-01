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
Met de hand op de VM: ~/agents/.venv/bin/python prijsonderzoeker.py --vraag "..." (zoals De Regisseur; die python
heeft pypdf voor handleidingen in PDF).

Werkt met Mehdi's Claude-abonnement via claude -p, nooit met de API (overleg 14, 01-11-2026): geen API-kost. Het token
staat in ~/.config/prijsonderzoeker/claude-token (rechten 600), het bestand dat ook de bouwagents lezen; zetten met
mijnagents-runner/mac/abonnement_aanmelden.command (dubbelklikken, aanmelden, niets plakken).
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


# Voor het bord, zoals de andere agents. Een API-sleutel daarin bereikt claude -p nooit: onderzoek.omgeving() geeft
# het subproces alleen een witte lijst en het abonnementstoken (overleg 14, K1).
laad_env("~/appportal/.env")
laad_env("~/agents/.env")


def open_vragen():
    """De klaargezette prijsvragen voor mij, oudste eerst."""
    items = bord.klaargezet_voor(NAAM, status="klaar")
    vragen = [it for it in items if it.get("soort") == "vraag" and (it.get("inhoud") or it.get("titel"))]
    return sorted(vragen, key=lambda it: it.get("id") or 0)


class VraagBlijft(Exception):
    """De vraag gaf geen verslag (fout, limiet of geen leesbaar antwoord): ze blijft klaarstaan, de nood is al gemeld
    (Codex controle 22, punt 3)."""


def vingerafdruk(vraag, vandaag):
    """Wat het logboek van een vraag bewaart: nooit de vraag zelf (Codex X3), alleen een vingerafdruk."""
    return hashlib.sha256(f"{vandaag}:{vraag}".encode()).hexdigest()[:12]


def per_eis(rij, eisen):
    """Per eis wat het model zei en wat de code ervan hield, voor het werkverslag. Een eis van het model heet "eis N"
    zoals in de lijst Eisen van het verslag: nooit de eis in haar woorden (Codex X3). Het citaat komt van een
    winkelpagina."""
    compat = rij.get("compatibiliteit") if isinstance(rij.get("compatibiliteit"), dict) else {}
    uit = []
    for i, (eis, code) in enumerate(zip(eisen, rij.get("per_eis") or []), 1):
        o = compat.get(eis)
        o = o if isinstance(o, dict) else {"oordeel": o}
        uit.append({"eis": eis if A._EIS_BEWIJS.match(eis) else f"eis {i}", "model": o.get("oordeel"),
                    "citaat": o.get("citaat"), "bewijs_url": o.get("bewijs_url"), "code": code})
    return uit


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
    geslaagd, mislukt = uit.get("leesbeurten", (len(uit["gelezen"]), 0))
    ag.log("prijsvraag", "bron", f"vraag {va}: {uit['zoekopdrachten']} zoekopdrachten, {geslaagd} pagina's gelezen en "
                                 f"{mislukt} niet leesbaar, {uit['tokens']} tokens via het abonnement (bron "
                                 f"{uit.get('bron')}), model {uit['model']}, {uit.get('beurten')} beurten, einde {uit['stop']}",
           uit.get("tellers"))
    if uit["stop"] == "plafond":
        r.nood(f"Prijsvraag gestopt op een grens ({uit.get('reden')})", wie="claude-code")
    elif uit["stop"] == "limiet":
        r.nood("Prijsvraag gestopt: limiet van het Claude-abonnement bereikt, niets via de API", wie="claude-code")
    elif uit["stop"] == "fout":
        ag.log("prijsvraag", "fout", f"vraag {va}: claude -p eindigde met een fout", uit.get("fout"))
        r.nood("Prijsvraag: claude -p eindigde met een fout", wie="claude-code")
    g = uit["gegevens"]
    if uit["stop"] != "klaar":
        # Alleen een vraag die gewoon eindigde, bewees dat ze binnen het abonnement bleef (Codex controle 23).
        raise VraagBlijft(uit["stop"])
    if g is None:
        ag.log("prijsvraag", "fout", f"vraag {va}: het model gaf geen leesbare gegevens", uit["tekst"][:3000])
        r.nood("Prijsvraag zonder leesbaar antwoord van het model; de vraag blijft klaarstaan", wie="claude-code")
        raise VraagBlijft("geen antwoord")
    aanbiedingen = g.get("aanbiedingen") if isinstance(g.get("aanbiedingen"), list) else []
    for a in aanbiedingen:
        if isinstance(a, dict):
            a["gezien_op"] = vandaag.isoformat()     # gelezen in deze ronde; de datum zet de code, niet het model
    gelezen, niet_gelezen = O.alleen_gelezen(aanbiedingen, uit["gelezen"])
    eisen = list(dict.fromkeys(vaste_eisen + [str(e) for e in g.get("eisen") or [] if str(e).strip()]))
    g["eisen"] = eisen
    res = A.verwerk(gelezen, vandaag, koersen, eisen, paginas=uit["gelezen"])
    res["afgewezen"] = niet_gelezen + res["afgewezen"]
    opgenomen = [x["url"] for x in res["goed"] + res["niet_compatibel"]]
    gezien = O.alleen_gezien(g.get("niet_nagekeken") if isinstance(g.get("niet_nagekeken"), list) else [],
                             uit.get("zoekresultaten") or {}, opgenomen)
    tekst = V.maak(vraag, g, res, koersdatum, vandaag.isoformat(), gezien, {"tokens": uit["tokens"]})
    zet_klaar(vraag, V.titel(g, res), tekst, vandaag)
    ag.log("prijsvraag", "beslissing",
           f"vraag {va}: {len(res['goed'])} aanbiedingen in het verslag, {len(res['niet_compatibel'])} niet compatibel, "
           f"{len(gezien)} gezien maar niet nagekeken, {len(res['afgewezen'])} afgewezen",
           [{"url": x["aanbod"].get("url"), "redenen": x["redenen"]} for x in res["afgewezen"]])
    # Per aanbod in het verslag de citaten en wat ontbreekt, zodat een volgende fout meetbaar is (overleg 33, F). Alleen
    # gegevens van de winkelpagina's en de netwaarden, nooit de vraag of eisen in haar woorden (Codex X3).
    ag.log("prijsvraag", "bron", f"vraag {va}: bewijs per aanbod in het verslag",
           [{"url": x.get("url"), "ontbreekt": x.get("ontbreekt"), "compatibel": x.get("compatibel"),
             "btw": [x.get("btw_inbegrepen"), x.get("verzending_btw_inbegrepen")], "verzending": x.get("verzending"),
             "bewijs": x.get("bewijs"), "eisen": per_eis(x, eisen)}
            for x in res["goed"] + res["niet_compatibel"]])
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
        except O.GeenAbonnement as e:
            # Nooit terug naar de API (overleg 14, K1). De vraag blijft klaarstaan tot het abonnement werkt, en de
            # volgende vragen ook: niets wordt als opgepakt gemarkeerd zonder verslag (Codex controle 20, punt 3).
            ag.log("prijsvraag", "fout", f"vraag {vingerafdruk(tekst, vandaag)}: geen abonnement: {str(e)[:300]}")
            r.nood(f"Prijsvraag niet gedaan, niets via de API: het Claude-abonnement werkt niet op de VM ({str(e)[:160]})",
                   wie="claude-code")
            break
        except VraagBlijft:
            break                                   # de nood staat er al; de vraag blijft klaarstaan
        except Exception as e:  # noqa: BLE001  de vraag blijft klaarstaan, met een nood (Codex controle 21, punt 3)
            ag.log("prijsvraag", "fout", f"vraag {vingerafdruk(tekst, vandaag)}: {type(e).__name__}: {str(e)[:300]}")
            r.nood("Prijsvraag mislukt bij het zoeken; de vraag blijft klaarstaan", wie="claude-code")
            break
        gedaan += 1
        if v.get("id"):
            bord.opgepakt(v["id"], NAAM)
    rest = len(vragen) - gedaan
    r.detail = f"{gedaan} prijsvragen afgewerkt, {aanbod} aanbiedingen in de verslagen" + (f", {rest} wachten" if rest else "")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="De Prijsonderzoeker")
    p.add_argument("--vraag", help="een prijsvraag met de hand, zonder het bord")
    p.add_argument("--droog", action="store_true", help="niet zoeken; zeggen wat klaarstaat")
    p.add_argument("--proef-abonnement", action="store_true",
                   help="alleen nagaan of het Claude-abonnement op deze machine werkt (geen ronde, geen bord)")
    a = p.parse_args()
    if a.proef_abonnement:
        gelukt, melding = O.proef_abonnement()
        print(melding)
        sys.exit(0 if gelukt else 1)
    begin = time.monotonic()
    with ag.ronde("prijsvraag" if a.vraag else "prijsvragen afwerken") as r:
        werk(r, a.vraag, a.droog, begin)
