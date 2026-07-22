#!/usr/bin/env python3
"""Gezondheidssonde voor de AppPortal-apps (wens Shaniel 2026-07-22: onderhoud
moet autonoom, niet op prompt).

Deterministisch en goedkoop: geen AI, alleen feiten verzamelen die per app
tellen. De uitkomst (JSON) is de invoer voor de onderhoudsagent, die pas
daarna oordeelt en binnen de veilige klasse ingrijpt (zie
docs/ONDERHOUDSAGENT.md).

Draaien op de VM:  python3 ~/appportal/scripts/gezondheid.py
Schrijft een leesbaar rapport naar stdout en de ruwe bevindingen naar
~/gezondheid-laatste.json.
"""
import json
import subprocess
import sys

PG = "appportal-postgresql-1"          # postgres-container van de stack
LOG_VENSTER = "24h"                     # hoe ver terug we in de logs kijken
FOUT_PATROON = "error|traceback|exception|critical|timeout|worker timeout"

# Dataverse-checks per app. Elke check levert 1 waarde op; de sonde vlagt
# alleen, ze oordeelt niet (dat doet de agent). soort: "leeftijd_uur" verwacht
# een timestamp en rekent de leeftijd uit; "vlag" verwacht true/false.
DB_CHECKS = [
    {"app": "kosten", "naam": "desktime-sync gelukt", "soort": "vlag",
     "sql": "SELECT ok FROM kosten.desktime_sync ORDER BY laatste_run DESC LIMIT 1",
     "drempel": True},
    {"app": "kosten", "naam": "desktime-sync leeftijd", "soort": "leeftijd_uur",
     "sql": "SELECT max(laatste_run) FROM kosten.desktime_sync",
     "drempel": 12},
    {"app": "kosten", "naam": "laatste banktransactie", "soort": "leeftijd_uur",
     "sql": "SELECT max(datum)::timestamptz FROM kosten.bank_transactie",
     "drempel": 24 * 45},
    {"app": "ontwikkeling", "naam": "git-collector leeftijd", "soort": "leeftijd_uur",
     "sql": "SELECT max(datum)::timestamptz FROM ontwikkeling.dag",
     "drempel": 24 * 3},
    {"app": "hr", "naam": "hr-dag versheid", "soort": "leeftijd_uur",
     "sql": "SELECT max(detail_op) FROM hr.dag",
     "drempel": 24 * 4},
]


def sh(args, timeout=30):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except Exception as e:
        return f"__fout__ {e}"


def psql(sql):
    return sh(["docker", "exec", PG, "psql", "-U", "authentik", "-d",
               "appportal", "-tAc", sql])


def containers():
    namen = sh(["docker", "ps", "--format", "{{.Names}}"]).splitlines()
    return sorted(n for n in namen if n and not n.startswith("__fout__"))


def container_beeld(naam):
    fmt = "{{.RestartCount}}|{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}-{{end}}"
    ruw = sh(["docker", "inspect", naam, "--format", fmt])
    herstart, status, health = (ruw.split("|") + ["", "", ""])[:3]
    logs = sh(["docker", "logs", "--since", LOG_VENSTER, naam], timeout=25)
    fouten = 0
    if not logs.startswith("__fout__"):
        laag = logs.lower()
        for regel in laag.splitlines():
            if any(w in regel for w in FOUT_PATROON.split("|")):
                fouten += 1
    return {"container": naam, "herstarts": _int(herstart), "status": status,
            "health": health or "-", "fouten_24h": fouten}


def _int(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def db_check(c):
    ruw = psql(c["sql"])
    if ruw.startswith("__fout__") or "ERROR" in ruw:
        return {**_meta(c), "waarde": None, "oordeel": "n.v.t.",
                "detail": "tabel/query niet beschikbaar"}
    if not ruw:
        return {**_meta(c), "waarde": None, "oordeel": "leeg", "detail": "geen rijen"}
    if c["soort"] == "vlag":
        ok = ruw.lower() in ("t", "true")
        return {**_meta(c), "waarde": ruw,
                "oordeel": "ok" if ok == c["drempel"] else "afwijkend"}
    # leeftijd_uur
    uur = psql(f"SELECT round(extract(epoch FROM now() - ({c['sql']}))/3600)::int")
    u = _int(uur)
    if u is None:
        return {**_meta(c), "waarde": ruw, "oordeel": "onbekend"}
    return {**_meta(c), "waarde": ruw, "leeftijd_uur": u,
            "oordeel": "ok" if u <= c["drempel"] else "verouderd"}


def _meta(c):
    return {"app": c["app"], "naam": c["naam"], "drempel": c["drempel"]}


def main():
    conts = [container_beeld(n) for n in containers()]
    checks = [db_check(c) for c in DB_CHECKS]

    # Samenvatting: wat vraagt aandacht?
    aandacht = []
    for c in conts:
        if c["health"] == "unhealthy" or c["status"] != "running":
            aandacht.append(f"container {c['container']}: {c['status']}/{c['health']}")
        elif c["herstarts"] and c["herstarts"] > 0:
            aandacht.append(f"container {c['container']}: {c['herstarts']} herstart(s)")
        if c["fouten_24h"] >= 20:
            aandacht.append(f"container {c['container']}: {c['fouten_24h']} foutregels (24u)")
    for c in checks:
        if c["oordeel"] in ("afwijkend", "verouderd", "leeg"):
            aandacht.append(f"{c['app']}/{c['naam']}: {c['oordeel']} ({c.get('waarde')})")

    rapport = {"containers": conts, "db_checks": checks, "aandacht": aandacht}
    with open("/home/ubuntu/gezondheid-laatste.json", "w") as f:
        json.dump(rapport, f, indent=2, default=str)

    print("=== Gezondheid AppPortal ===")
    print(f"{len(conts)} containers, {len(checks)} dataverse-checks\n")
    if aandacht:
        print(f"AANDACHT ({len(aandacht)}):")
        for a in aandacht:
            print("  - " + a)
    else:
        print("Alles gezond.")
    print("\nDetail per container:")
    for c in conts:
        print(f"  {c['container']:38} {c['status']:8} health={c['health']:9}"
              f" herstart={c['herstarts']} fouten24u={c['fouten_24h']}")
    print("\nDataverse-checks:")
    for c in checks:
        extra = f" leeftijd={c.get('leeftijd_uur')}u" if "leeftijd_uur" in c else ""
        print(f"  {c['app']:14} {c['naam']:28} {c['oordeel']:10}"
              f" waarde={c.get('waarde')}{extra}")
    return 0 if not aandacht else 1


if __name__ == "__main__":
    sys.exit(main())
