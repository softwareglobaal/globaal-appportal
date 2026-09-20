#!/usr/bin/env python3
"""De Agentnorm, getoetst. Een agent is niet "goed" omdat iemand dat vindt,
maar omdat hij door elke toets komt. Zie AGENTNORM.md voor wat elke norm eist
en waarom hij bestaat.

    controle_agenten.py                  alle agents, korte uitslag
    controle_agenten.py --agent agenda-wacht --uitleg
    controle_agenten.py --norm N6        alleen die norm, over alle agents
    controle_agenten.py --json           machineleesbaar, voor een test of het bord

Exitcode 0 als alles slaagt, 1 als er een norm faalt. Zo kan dit in een test of
in de cron: een agent die afzakt valt op voor iemand het merkt.

Nooit een mening, altijd een meting. Wie een norm te streng vindt, past de norm
aan in AGENTNORM.md en hier, niet het geval dat toevallig faalt.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("AGENTS_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))
RUNNER = os.environ.get("AGENTS_RUNNER", HIER)
DATA = os.environ.get("AGENTS_DATA", os.path.expanduser("~/appportal/mijnagents-data"))

# Norm: (code, korte eis, functie). De functie geeft (geslaagd, uitleg) terug.
# Een norm die niet van toepassing is geeft (None, reden): dat telt niet mee.

GEHEIM = re.compile(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,}"
                    r"|AIza[A-Za-z0-9_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
                    r"|\b(wachtwoord|password|api[_-]?key|token|secret)\s*[=:]\s*[\"']?[A-Za-z0-9/_+-]{12,})",
                    re.I)
VERPLICHTE_VELDEN = ("rol", "cadans", "mandaat", "mag", "grenzen")


def _tekst(rij, veld):
    return (rij[veld] or "").strip() if veld in rij.keys() else ""


def _zaadpad(naam):
    return os.path.join(RUNNER, "werkwijze", f"{naam}.md")


def _runnerpad(naam):
    return os.path.join(RUNNER, naam.replace("-", "_") + ".py")


def _genormaliseerd(s):
    """Vergelijking zonder ruis: de export schrijft geen afsluitende newline."""
    return "\n".join(r.rstrip() for r in (s or "").strip().splitlines())


def _ouderdom_dagen(ts):
    if not ts:
        return None
    for vorm in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f",
                 "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            d = datetime.strptime(str(ts)[:26], vorm)
            if d.tzinfo:
                d = d.astimezone(timezone.utc).replace(tzinfo=None)
            nu = datetime.now(timezone.utc).replace(tzinfo=None)
            return (nu - d).total_seconds() / 86400
        except ValueError:
            continue
    return None


def n1_werkwijze(rij, con):
    """N1 werkwijze op het bord, minstens 500 tekens."""
    ww = _tekst(rij, "werkwijze")
    if not ww:
        return False, "geen werkwijze op het bord"
    if len(ww) < 500:
        return False, f"werkwijze is maar {len(ww)} tekens"
    return True, f"{len(ww)} tekens"


def n2_grenzen_in_werkwijze(rij, con):
    """N2 de werkwijze zegt wat hij nooit doet en wat Mehdi beslist."""
    ww = _tekst(rij, "werkwijze").lower()
    if not ww:
        return None, "geen werkwijze (zie N1)"
    mist = []
    if "nooit" not in ww:
        mist.append("wat hij nooit doet")
    if "beslist" not in ww and "beslissing" not in ww and "mehdi bepaalt" not in ww:
        mist.append("wat Mehdi beslist")
    return (False, "mist: " + ", ".join(mist)) if mist else (True, "beide aanwezig")


def n3_kaart_compleet(rij, con):
    """N3 rol, cadans, mandaat, mag en grenzen staan ingevuld op het bord."""
    leeg = [v for v in VERPLICHTE_VELDEN if not _tekst(rij, v)]
    return (False, "leeg: " + ", ".join(leeg)) if leeg else (True, "compleet")


def n4_kennis_gemeld(rij, con):
    """N4 hij heeft de laatste zeven dagen gemeld welk regelboek hij las."""
    d = _ouderdom_dagen(_tekst(rij, "kennis_ts"))
    if d is None:
        return False, "nooit kennis gemeld"
    if d > 7:
        return False, f"laatst {d:.0f} dagen geleden"
    return True, f"{d:.1f} dagen geleden"


def n5_runner_bestaat(rij, con):
    """N5 er is een runner-bestand met de naam van de agent."""
    p = _runnerpad(rij["naam"])
    if os.path.exists(p):
        return True, os.path.basename(p)
    if _tekst(rij, "draait_op").lower().startswith("mac"):
        return None, "draait op de Mac, niet in deze repo"
    return False, f"{os.path.basename(p)} ontbreekt"


def n6_zaad_gelijk_aan_bord(rij, con):
    """N6 het zaad in werkwijze/ is gelijk aan het bord, of het ontbreekt bewust.

    Het bord is de waarheid. Een zaad dat afwijkt is een tweede waarheid, en die
    leest iemand vroeg of laat per ongeluk.
    """
    p = _zaadpad(rij["naam"])
    if not os.path.exists(p):
        return None, "geen zaad in de repo"
    bord = _genormaliseerd(_tekst(rij, "werkwijze"))
    with open(p, encoding="utf-8") as f:
        zaad = _genormaliseerd(f.read())
    if bord == zaad:
        return True, "gelijk aan het bord"
    return False, f"wijkt af van het bord ({len(zaad.splitlines())} regels hier, {len(bord.splitlines())} daar)"


def n7_noden_sluiten(rij, con):
    """N7 geen nood die langer dan drie dagen open staat.

    Een nood die blijft terugkomen is geen melding meer maar ruis; hij hoort
    een besluit te krijgen of te verdwijnen.
    """
    try:
        rijen = con.execute("select tekst, ts from nood where naam=? and open=1", (rij["naam"],)).fetchall()
    except sqlite3.Error:
        return None, "geen nood-tabel"
    oud = [(t, _ouderdom_dagen(ts)) for t, ts in rijen]
    oud = [(t, d) for t, d in oud if d is not None and d > 3]
    if not oud:
        return True, f"{len(rijen)} open, geen ouder dan 3 dagen"
    oudste = max(oud, key=lambda x: x[1])
    return False, f"{len(oud)} nood(en) ouder dan 3 dagen, oudste {oudste[1]:.0f} dagen: {oudste[0][:60]}"


def n8_geen_geheim(rij, con):
    """N8 geen sleutel, token of wachtwoord in de werkwijze."""
    m = GEHEIM.search(_tekst(rij, "werkwijze"))
    if m:
        return False, f"lijkt een geheim te bevatten rond positie {m.start()}"
    return True, "schoon"


def n9_stijl(rij, con):
    """N9 geen gedachtestreepjes in de werkwijze (afspraak 2026-07-04)."""
    ww = _tekst(rij, "werkwijze")
    n = ww.count("—") + ww.count("–")
    if n:
        return False, f"{n} gedachtestreepje(s)"
    return True, "schoon"


NORMEN = [
    ("N1", "werkwijze op het bord", n1_werkwijze),
    ("N2", "grenzen staan erin", n2_grenzen_in_werkwijze),
    ("N3", "kaart compleet", n3_kaart_compleet),
    ("N4", "kennis gemeld", n4_kennis_gemeld),
    ("N5", "runner bestaat", n5_runner_bestaat),
    ("N6", "zaad gelijk aan bord", n6_zaad_gelijk_aan_bord),
    ("N7", "noden sluiten", n7_noden_sluiten),
    ("N8", "geen geheim", n8_geen_geheim),
    ("N9", "stijl", n9_stijl),
]


def toets(con, alleen_agent=None, alleen_norm=None):
    con.row_factory = sqlite3.Row
    waar = "where actief=1 and naam=?" if alleen_agent else "where actief=1"
    args = (alleen_agent,) if alleen_agent else ()
    rijen = con.execute(f"select * from agent {waar} order by naam", args).fetchall()
    uitslag = []
    for rij in rijen:
        per = []
        for code, eis, fn in NORMEN:
            if alleen_norm and code != alleen_norm:
                continue
            try:
                ok, uitleg = fn(rij, con)
            except Exception as e:  # een kapotte toets is zelf een fout
                ok, uitleg = False, f"toets brak: {type(e).__name__}: {e}"
            per.append({"norm": code, "eis": eis, "ok": ok, "uitleg": uitleg})
        uitslag.append({"agent": rij["naam"], "toetsen": per})
    return uitslag


def main():
    p = argparse.ArgumentParser(description="Toetst elke agent aan de Agentnorm.")
    p.add_argument("--db", default=DB)
    p.add_argument("--agent")
    p.add_argument("--norm")
    p.add_argument("--uitleg", action="store_true", help="ook tonen wat wel slaagde")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    if not os.path.exists(a.db):
        print(f"bord niet gevonden: {a.db}", file=sys.stderr)
        return 2
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    uitslag = toets(con, a.agent, a.norm.upper() if a.norm else None)

    if a.json:
        print(json.dumps(uitslag, ensure_ascii=False, indent=2))
        return 0 if all(t["ok"] is not False for u in uitslag for t in u["toetsen"]) else 1

    gezakt_totaal = 0
    for u in uitslag:
        gezakt = [t for t in u["toetsen"] if t["ok"] is False]
        nvt = [t for t in u["toetsen"] if t["ok"] is None]
        gezakt_totaal += len(gezakt)
        geslaagd = len([t for t in u["toetsen"] if t["ok"] is True])
        merk = "ok " if not gezakt else "ZAK"
        print(f"{merk} {u['agent']:<32} {geslaagd} geslaagd, {len(gezakt)} gezakt"
              + (f", {len(nvt)} n.v.t." if nvt else ""))
        for t in gezakt:
            print(f"      {t['norm']} {t['eis']}: {t['uitleg']}")
        if a.uitleg:
            for t in u["toetsen"]:
                if t["ok"] is not False:
                    merk2 = "  ok" if t["ok"] else " nvt"
                    print(f"    {merk2} {t['norm']} {t['eis']}: {t['uitleg']}")

    print(f"\n{len(uitslag)} agents getoetst, {gezakt_totaal} gezakte norm(en).")
    return 0 if gezakt_totaal == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
