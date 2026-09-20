#!/usr/bin/env python3
"""De Normwacht: toetst elke agent aan AGENTNORM.md en komt terug tot het klopt.

Hij doet zelf niets aan een andere agent. Hij meet, schrijft het logboek, en zet
per gezakte norm een nood op het bord met een stabiele tekst, zodat dezelfde
nood morgen dezelfde nood is en de lus kan sluiten (dat is norm N10).

    normwacht.py              een ronde: meten, logboek bijwerken, noden zetten
    normwacht.py --droog      meten en tonen, niets naar het bord schrijven

Cron (dagelijks 06:10, voor de meeste agents aan hun ronde beginnen):
    10 6 * * * cd ~/appportal/mijnagents-runner && ~/agents/.venv/bin/python normwacht.py
"""
import argparse
import os
import sqlite3
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))

import bord  # noqa: E402
import controle_agenten as ca  # noqa: E402

NAAM = "normwacht"
DATA = os.environ.get("AGENTS_DATA", os.path.expanduser("~/appportal/mijnagents-data"))
JSONL = os.path.join(DATA, "agentnorm", "logboek.jsonl")
MD = os.path.join(DATA, "agentnorm", "logboek.md")

# Wie een gezakte norm oplost. Wat een mens moet beslissen gaat naar mehdi,
# wat code is gaat naar claude-code.
EIGENAAR = {
    "N1": "claude-code", "N2": "mehdi", "N3": "mehdi", "N4": "claude-code",
    "N5": "claude-code", "N6": "claude-code", "N7": "mehdi", "N8": "mehdi",
    "N9": "claude-code", "N10": "claude-code", "S1": "claude-code",
}


def noodtekst(norm, eis, agents):
    """Stabiel: geen aantal en geen datum in de tekst, anders is elke ronde een
    nieuwe nood (N10). Het aantal hoort in het detail thuis, niet hier.
    """
    if len(agents) <= 3:
        return f"{norm} {eis}: {', '.join(sorted(agents))}"
    return f"{norm} {eis}: bij meerdere agents"


def stilte_signalen(uitslag):
    """Een agent die stilstaat of in fout hangt is acuut: dat gaat apart naar
    Telegram, met de agentnaam in `uniek` zodat het per agent één keer komt en
    vanzelf verdwijnt zodra hij weer draait.
    """
    uit = []
    for u in uitslag:
        for t in u["toetsen"]:
            if t["norm"] == "N11" and t["ok"] is False:
                # De sleutel draagt alleen de soort storing, nooit het aantal
                # uren: anders is elke ronde een nieuw signaal (norm N10).
                uitleg = t["uitleg"]
                soort = ("fout" if "op fout" in uitleg else
                         "vastgelopen" if "vastgelopen" in uitleg else "stil")
                uit.append({
                    "voor": "mehdi", "soort": "signaal",
                    "titel": f"{u['agent']} draait niet: {uitleg}",
                    "uniek": f"normwacht-stilte-{u['agent']}-{soort}",
                    "inhoud": "Deze agent geeft geen verse hartslag. Draait hij op de Mac, "
                              "dan kan een slapende laptop de reden zijn; draait hij op de VM, "
                              "kijk dan in zijn log.",
                })
    return uit


def norm_signaal(gezakt, uitslag, schoon):
    """Eén samenvatting per dag. `uniek` bevat alleen welke normen zakken, niet
    hoeveel: zo komt hetzelfde bericht niet elke ochtend opnieuw (norm N10).
    """
    normen = sorted({norm for (norm, _) in gezakt})
    regels = [f"{norm} {eis}: {len(agents)} agent(s) ({', '.join(sorted(agents)[:4])}"
              f"{' en meer' if len(agents) > 4 else ''})"
              for (norm, eis), agents in sorted(gezakt.items())]
    return {
        "voor": "mehdi", "soort": "signaal",
        "titel": f"Agentnorm: {len(normen)} norm(en) open, {len(schoon)} van {len(uitslag)} agents zonder fout",
        "uniek": "normwacht-stand-" + "-".join(normen),
        "inhoud": "\n".join(regels) + "\n\nHet logboek staat in Data uit Mehdi/agentnorm/logboek.md.",
    }


def ronde(droog=False):
    ag = bord.Agent(NAAM)
    if not droog:
        ag.hartslag("actief", taak="ronde gestart")

    if not os.path.exists(ca.DB):
        if not droog:
            ag.hartslag("fout", taak="bord niet gevonden", detail=ca.DB)
        print(f"bord niet gevonden: {ca.DB}", file=sys.stderr)
        return 2

    con = sqlite3.connect(f"file:{ca.DB}?mode=ro", uri=True)
    uitslag = ca.toets(con)
    systeem = ca.systeemtoetsen()

    # per norm: welke agents zakken
    gezakt = {}
    for u in uitslag:
        for t in u["toetsen"]:
            if t["ok"] is False:
                gezakt.setdefault((t["norm"], t["eis"]), []).append(u["agent"])
    for s in systeem:
        if s["ok"] is False:
            gezakt.setdefault((s["norm"], s["eis"]), []).append("omgeving")

    regel = ca.schrijf_logboek(uitslag, systeem, JSONL) if not droog else None
    if not droog:
        ca.maak_logboek_md(JSONL, MD)

    totaal = sum(len(v) for v in gezakt.values())
    schoon = [u["agent"] for u in uitslag if not any(t["ok"] is False for t in u["toetsen"])]

    ag.log("norm", "meting", f"{len(uitslag)} agents getoetst, {totaal} gezakte norm(en)",
           detail=f"zonder fout: {', '.join(schoon) or 'geen'}")
    for (norm, eis), agents in sorted(gezakt.items()):
        ag.log("norm", norm, f"{eis}: {len(agents)} agent(s)", detail=", ".join(sorted(agents)))

    noden = [{"tekst": noodtekst(norm, eis, agents), "wie": EIGENAAR.get(norm, "mehdi")}
             for (norm, eis), agents in sorted(gezakt.items())]

    if droog:
        print(f"{len(uitslag)} agents, {totaal} gezakte norm(en). Zou {len(noden)} nood(en) zetten:")
        for n in noden:
            print(f"  [{n['wie']}] {n['tekst']}")
        signalen = stilte_signalen(uitslag) + [norm_signaal(gezakt, uitslag, schoon)]
        print(f"\nEn {len(signalen)} signaal/signalen naar Telegram (via De Bode):")
        for s in signalen:
            print(f"  {s['titel']}")
        return 0 if totaal == 0 else 1

    ag.log_verstuur()
    ag.hartslag("klaar" if totaal == 0 else "waakt",
                taak=f"{len(uitslag)} agents getoetst",
                detail=f"{totaal} gezakte norm(en), {len(schoon)} agent(s) zonder fout",
                nood=noden)

    # Een nood blijft op het bord staan; De Bode stuurt alleen klaarzet en
    # voorstellen door. Mehdi's laptop slaapt 's ochtends, dus wat hij moet
    # weten gaat als signaal naar Telegram, niet naar een scherm dat uit staat.
    gezet = ag.klaarzet(stilte_signalen(uitslag) + [norm_signaal(gezakt, uitslag, schoon)])
    print(f"{len(uitslag)} agents, {totaal} gezakte norm(en), {len(noden)} nood(en) op het bord, "
          f"{gezet.get('nieuw', 0)} signaal/signalen naar De Bode.")
    if regel:
        print(f"logboek: {MD}")
    return 0 if totaal == 0 else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Toetst elke agent aan de Agentnorm.")
    p.add_argument("--droog", action="store_true", help="meten en tonen, niets schrijven")
    sys.exit(ronde(p.parse_args().droog))
