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


TELLER = re.compile(r"\b\d+\s+(toekomstige\s+)?\w+\s*\(?en\)?\b|^\d+\s", re.I)


def n10_noden_hebben_sleutel(rij, con):
    """N10 een nood draagt geen teller in zijn tekst.

    Noden zijn declaratief: elke ronde stuurt de agent de hele lijst en wat er
    niet meer in staat geldt als opgelost. Staat er een aantal in de tekst
    ("11 afspraken zonder code"), dan is elke ronde formeel een nieuwe nood en
    sluit de lus nooit. De Agendawacht verzamelde zo dertig identieke regels.
    Zet het aantal in het detail, niet in de tekst.
    """
    try:
        rijen = con.execute("select tekst from nood where naam=? and open=1", (rij["naam"],)).fetchall()
    except sqlite3.Error:
        return None, "geen nood-tabel"
    met_teller = [t for (t,) in rijen if re.match(r"^\s*\d+\s+\w", t or "")]
    if met_teller:
        return False, f"{len(met_teller)} nood(en) met een aantal in de tekst: {met_teller[0][:60]}"
    return True, f"{len(rijen)} open nood(en), geen teller in de tekst"


def _drempel_uren(cadans):
    """Hoe lang mag het stil blijven voor het stil te lang is. De cadans is
    vrije tekst, dus we lezen alleen de orde van grootte."""
    c = (cadans or "").lower()
    if "maand" in c:
        return 32 * 24
    if "week" in c or "maandag" in c:
        return 8 * 24
    return 25


def n11_hartslag(rij, con):
    """N11 hij heeft nog een hartslag gegeven, en staat niet stil in fout.

    Zes agents draaien op de Mac van Mehdi. Slaapt die laptop, dan gaat hun
    ronde gewoon niet door en merkt niemand het. Een agent die stil valt of in
    fout blijft staan hoort op te vallen, niet te verdwijnen.
    """
    try:
        r = con.execute("select status, ts, taak from status where naam=?", (rij["naam"],)).fetchone()
    except sqlite3.Error:
        return None, "geen status-tabel"
    if not r:
        return False, "nooit een hartslag gegeven"
    status, ts, taak = r[0], r[1], (r[2] or "")
    d = _ouderdom_dagen(ts)
    if d is None:
        return None, f"tijdstempel onleesbaar: {ts}"
    uren = d * 24
    grens = _drempel_uren(_tekst(rij, "cadans"))
    if status == "fout":
        return False, f"staat op fout sinds {uren:.0f} uur: {taak[:60]}"
    if status == "actief" and uren > 3:
        return False, f"staat al {uren:.0f} uur op actief, ronde vastgelopen: {taak[:60]}"
    if uren > grens:
        waar = _tekst(rij, "draait_op") or "?"
        return False, f"{uren:.0f} uur stil (mag {grens} uur, draait op {waar})"
    return True, f"{uren:.0f} uur geleden, {status}"


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
    ("N10", "noden hebben een sleutel", n10_noden_hebben_sleutel),
    ("N11", "hartslag vers", n11_hartslag),
]


def systeemtoetsen():
    """Toetsen die niet over een agent gaan maar over de omgeving. S1 is de
    meest gemaakte fout: werk dat alleen op de VM bestaat.
    """
    uit = []
    repo = os.path.dirname(os.path.abspath(RUNNER)) if RUNNER != HIER else os.path.dirname(HIER)

    def git(*args):
        import subprocess
        try:
            r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=60)
            return r.stdout.strip() if r.returncode == 0 else None
        except Exception:
            return None

    if git("rev-parse", "--is-inside-work-tree") != "true":
        uit.append({"norm": "S1", "eis": "repo synchroon", "ok": None, "uitleg": f"geen git-repo: {repo}"})
        return uit

    git("fetch", "origin")
    telling = git("rev-list", "--left-right", "--count", "HEAD...origin/main")
    if not telling:
        uit.append({"norm": "S1", "eis": "repo synchroon", "ok": None, "uitleg": "kon origin niet lezen"})
        return uit
    voor, achter = (telling.split() + ["0", "0"])[:2]
    if voor != "0" or achter != "0":
        uit.append({"norm": "S1", "eis": "repo synchroon", "ok": False,
                    "uitleg": f"{voor} commit(s) alleen hier, {achter} alleen op GitHub. "
                              f"Werk dat alleen hier staat is een schijffout verwijderd van weg."})
    else:
        uit.append({"norm": "S1", "eis": "repo synchroon", "ok": True, "uitleg": "gelijk met GitHub"})
    return uit


def schrijf_logboek(uitslag, systeem, pad):
    """Eén regel per meting, append-only. Zo zie je waar we gestart zijn en
    waar we staan. JSON voor de machine; maak_logboek_md maakt de leesbare kant.
    """
    per_norm = {}
    for u in uitslag:
        for t in u["toetsen"]:
            if t["ok"] is False:
                per_norm[t["norm"]] = per_norm.get(t["norm"], 0) + 1
    regel = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "agents": len(uitslag),
        "gezakt": sum(per_norm.values()),
        "per_norm": per_norm,
        "geslaagde_agents": sorted(u["agent"] for u in uitslag
                                   if not any(t["ok"] is False for t in u["toetsen"])),
        "systeem": {s["norm"]: s["ok"] for s in systeem},
    }
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    with open(pad, "a", encoding="utf-8") as f:
        f.write(json.dumps(regel, ensure_ascii=False) + "\n")
    return regel


def maak_logboek_md(jsonl, md):
    """De leesbare kant van het logboek: waar we begonnen, waar we staan."""
    if not os.path.exists(jsonl):
        return None
    regels = [json.loads(r) for r in open(jsonl, encoding="utf-8") if r.strip()]
    if not regels:
        return None
    eerste, laatste = regels[0], regels[-1]
    normen = sorted({n for r in regels for n in r["per_norm"]}, key=lambda x: (len(x), x))
    uit = ["# Logboek van de Agentnorm", "",
           f"Eerste meting {eerste['ts'][:16].replace('T', ' ')}, laatste "
           f"{laatste['ts'][:16].replace('T', ' ')}. "
           f"{len(regels)} meting{'en' if len(regels) != 1 else ''}.", "",
           f"**Gestart op {eerste['gezakt']} gezakte normen over {eerste['agents']} agents. "
           f"Nu {laatste['gezakt']} over {laatste['agents']}.**", "",
           "| meting | agents | gezakt | " + " | ".join(normen) + " | agents zonder fout |",
           "|---|---:|---:|" + "---:|" * len(normen) + "---:|"]
    for r in regels[-30:]:
        cellen = [str(r["per_norm"].get(n, 0)) for n in normen]
        uit.append(f"| {r['ts'][:16].replace('T', ' ')} | {r['agents']} | {r['gezakt']} | "
                   + " | ".join(cellen) + f" | {len(r['geslaagde_agents'])} |")
    uit += ["", "## Agents die vandaag door alles komen", "",
            ", ".join(laatste["geslaagde_agents"]) or "(nog geen)", ""]
    os.makedirs(os.path.dirname(md), exist_ok=True)
    with open(md, "w", encoding="utf-8") as f:
        f.write("\n".join(uit))
    return md


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
    p.add_argument("--logboek", action="store_true",
                   help="de meting wegschrijven naar mijnagents-data/agentnorm/")
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

    systeem = [] if (a.agent or a.norm) else systeemtoetsen()
    for s in systeem:
        merk = "ok " if s["ok"] else ("ZAK" if s["ok"] is False else "nvt")
        print(f"{merk} {'omgeving: ' + s['eis']:<32} {s['norm']}: {s['uitleg']}")
        if s["ok"] is False:
            gezakt_totaal += 1

    print(f"\n{len(uitslag)} agents getoetst, {gezakt_totaal} gezakte norm(en).")

    if a.logboek and not (a.agent or a.norm):
        jsonl = os.path.join(DATA, "agentnorm", "logboek.jsonl")
        md = os.path.join(DATA, "agentnorm", "logboek.md")
        r = schrijf_logboek(uitslag, systeem, jsonl)
        maak_logboek_md(jsonl, md)
        print(f"logboek bijgewerkt: {r['gezakt']} gezakt over {r['agents']} agents -> {md}")

    return 0 if gezakt_totaal == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
