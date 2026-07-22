#!/usr/bin/env python3
"""Gezondheidssonde voor de AppPortal-apps (wens Shaniel 2026-07-22: onderhoud
moet autonoom, niet op prompt).

Deterministisch en goedkoop: geen AI, alleen feiten verzamelen die per app
tellen. De uitkomst (JSON) is de invoer voor de onderhoudsagent, die pas
daarna oordeelt en binnen de veilige klasse ingrijpt (zie
docs/ONDERHOUDSAGENT.md).

Naast de app-checks (containers, dataverse) meet de sonde ook de VM zelf
(schijf met trend, RAM, swap, load) en de proces-liveness van de geplande
jobs. Zo dekt hij de drie dingen die stuk kunnen zonder dat een container het
laat zien: storage, geheugen en de dagelijkse processen.

Draaien op de VM:  python3 ~/appportal/scripts/gezondheid.py
Schrijft een leesbaar rapport naar stdout en de ruwe bevindingen naar
~/gezondheid-laatste.json (overschrijfbaar via GEZONDHEID_UITVOER, handig om
te testen zonder het live bestand te raken).
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

PG = "appportal-postgresql-1"          # postgres-container van de stack
LOG_VENSTER = "24h"                     # hoe ver terug we in de logs kijken
FOUT_PATROON = "error|traceback|exception|critical|timeout|worker timeout"

# Waar de ruwe bevindingen heen gaan. De vorige uitvoer is tevens de bron voor
# de schijf-trend, dus lezen en schrijven gaan naar hetzelfde pad.
UITVOER = os.environ.get("GEZONDHEID_UITVOER", "/home/ubuntu/gezondheid-laatste.json")

# VM-drempels. De sonde vlagt alleen; de agent oordeelt. Bewust ruim gekozen
# zodat we alleen echte problemen melden en geen dagelijkse ruis.
SCHIJF_WAARSCHUW = 75       # % gebruikt op /
SCHIJF_ALARM = 90
SCHIJF_SNELLE_GROEI = 5     # procentpunt per uur; pas vlaggen bij TWEE metingen
                            # op rij boven deze drempel (een losse piek is meestal
                            # docker-bouwruis, geen lek; twee op rij is een klim)
RAM_WAARSCHUW_MB = 800      # vrij geheugen (MemAvailable)
RAM_ALARM_MB = 400
LOAD_FACTOR = 1.5           # load1 boven cores * factor = overbelast

# Proces-liveness: draaide een geplande job recent? Signaal = de mtime van zijn
# logbestand (elke run schrijft ernaartoe). De drempels tolereren het weekend
# voor jobs die alleen op weekdagen draaien, zodat een normale weekendpauze
# geen vals alarm geeft; we vlaggen dus pas bij een echte stilstand.
PROCES_CHECKS = [
    {"naam": "ontwikkeling-verzamel (uurlijks)",
     "log": "/home/ubuntu/ontwikkeling-verzamel.log", "max_uur": 3},
    {"naam": "db-backup (dagelijks 03:15)",
     "log": "/home/ubuntu/backups/backup.log", "max_uur": 27},
    {"naam": "hr-ververs (weekdagen 05:20)",
     "log": "/home/ubuntu/hr-ververs.log", "max_uur": 75},
    {"naam": "sync-sales (weekdagen 06:45)",
     "log": "/home/ubuntu/sync-sales.log", "max_uur": 75},
]

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


def _lees_vorige(pad):
    """De vorige uitvoer, voor de schijf-trend. Leeg bij eerste run of fout."""
    try:
        with open(pad) as f:
            return json.load(f)
    except Exception:
        return {}


def _meminfo():
    """/proc/meminfo als dict in kB. Leeg als het niet leesbaar is."""
    velden = {}
    try:
        with open("/proc/meminfo") as f:
            for regel in f:
                sleutel, _, rest = regel.partition(":")
                deel = rest.strip().split()
                if deel:
                    velden[sleutel] = _int(deel[0])
    except Exception:
        pass
    return velden


def vm_beeld(nu, vorige):
    """VM-vitals: schijf (met trend t.o.v. de vorige meting), RAM, swap, load.
    Alleen lezen; geen nieuwe rechten nodig."""
    try:
        du = shutil.disk_usage("/")
        schijf_pct = round(du.used / du.total * 100, 1)
        schijf_vrij_gb = round(du.free / 1024 ** 3, 1)
    except Exception:
        schijf_pct = schijf_vrij_gb = None

    # Stijging in procentpunt per uur, afgeleid uit de vorige uitvoer.
    stijging = None
    v_pct = (vorige.get("vm") or {}).get("schijf_pct")
    v_tijd = vorige.get("tijd")
    if schijf_pct is not None and isinstance(v_pct, (int, float)) and v_tijd:
        try:
            dt = (nu - datetime.fromisoformat(v_tijd)).total_seconds() / 3600
            if dt >= 0.1:
                stijging = round((schijf_pct - v_pct) / dt, 1)
        except Exception:
            pass

    mi = _meminfo()
    ram_vrij_mb = round(mi["MemAvailable"] / 1024) if mi.get("MemAvailable") else None
    swap_mb = round(mi["SwapTotal"] / 1024) if mi.get("SwapTotal") is not None else None

    try:
        load1, load5, load15 = os.getloadavg()
    except Exception:
        load1 = load5 = load15 = None
    cores = os.cpu_count() or 1

    return {
        "schijf_pct": schijf_pct,
        "schijf_vrij_gb": schijf_vrij_gb,
        "schijf_stijging_ppu": stijging,   # procentpunt/uur, None = onbekend
        "ram_vrij_mb": ram_vrij_mb,
        "swap_mb": swap_mb,
        "swap_afwezig": (swap_mb == 0) if swap_mb is not None else None,
        "load1": round(load1, 2) if load1 is not None else None,
        "load5": round(load5, 2) if load5 is not None else None,
        "load15": round(load15, 2) if load15 is not None else None,
        "cores": cores,
    }


def proces_beeld(c, nu):
    """Draaide een geplande job recent? Leeftijd = ouderdom van zijn log."""
    pad = c["log"]
    try:
        leeftijd = round((nu.timestamp() - os.path.getmtime(pad)) / 3600, 1)
    except FileNotFoundError:
        return {"naam": c["naam"], "log": pad, "leeftijd_uur": None,
                "max_uur": c["max_uur"], "oordeel": "geen log"}
    except Exception:
        return {"naam": c["naam"], "log": pad, "leeftijd_uur": None,
                "max_uur": c["max_uur"], "oordeel": "onbekend"}
    return {"naam": c["naam"], "log": pad, "leeftijd_uur": leeftijd,
            "max_uur": c["max_uur"],
            "oordeel": "ok" if leeftijd <= c["max_uur"] else "stil"}


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
    nu = datetime.now(timezone.utc)
    vorige = _lees_vorige(UITVOER)

    vm = vm_beeld(nu, vorige)
    conts = [container_beeld(n) for n in containers()]
    checks = [db_check(c) for c in DB_CHECKS]
    processen = [proces_beeld(c, nu) for c in PROCES_CHECKS]

    # Samenvatting: wat vraagt aandacht?
    aandacht = []

    # VM-vitals.
    if vm.get("schijf_pct") is not None:
        if vm["schijf_pct"] >= SCHIJF_ALARM:
            aandacht.append(f"schijf: {vm['schijf_pct']}% gebruikt (alarm boven {SCHIJF_ALARM})")
        elif vm["schijf_pct"] >= SCHIJF_WAARSCHUW:
            aandacht.append(f"schijf: {vm['schijf_pct']}% gebruikt (waarschuwing boven {SCHIJF_WAARSCHUW})")
    # Alleen vlaggen bij een aanhoudende klim: deze meting EN de vorige beide
    # boven de drempel. Zo vangt een losse docker-bouwpiek geen vals alarm.
    vorige_stijging = (vorige.get("vm") or {}).get("schijf_stijging_ppu")
    if (vm.get("schijf_stijging_ppu") is not None
            and vm["schijf_stijging_ppu"] >= SCHIJF_SNELLE_GROEI
            and isinstance(vorige_stijging, (int, float))
            and vorige_stijging >= SCHIJF_SNELLE_GROEI):
        aandacht.append(f"schijf groeit aanhoudend: +{vm['schijf_stijging_ppu']}"
                        f" procentpunt/uur (tweede meting op rij boven {SCHIJF_SNELLE_GROEI})")
    if vm.get("ram_vrij_mb") is not None:
        geen_swap = " en geen swap" if vm.get("swap_afwezig") else ""
        if vm["ram_vrij_mb"] <= RAM_ALARM_MB:
            aandacht.append(f"RAM: nog {vm['ram_vrij_mb']} MB vrij (alarm onder {RAM_ALARM_MB}{geen_swap})")
        elif vm["ram_vrij_mb"] <= RAM_WAARSCHUW_MB:
            aandacht.append(f"RAM: nog {vm['ram_vrij_mb']} MB vrij (waarschuwing onder {RAM_WAARSCHUW_MB}{geen_swap})")
    if vm.get("load1") is not None and vm["load1"] > vm["cores"] * LOAD_FACTOR:
        aandacht.append(f"load: {vm['load1']} op {vm['cores']} core(s) (boven {LOAD_FACTOR}x)")

    # Containers.
    for c in conts:
        if c["health"] == "unhealthy" or c["status"] != "running":
            aandacht.append(f"container {c['container']}: {c['status']}/{c['health']}")
        elif c["herstarts"] and c["herstarts"] > 0:
            aandacht.append(f"container {c['container']}: {c['herstarts']} herstart(s)")
        if c["fouten_24h"] >= 20:
            aandacht.append(f"container {c['container']}: {c['fouten_24h']} foutregels (24u)")

    # Dataverse.
    for c in checks:
        if c["oordeel"] in ("afwijkend", "verouderd", "leeg"):
            aandacht.append(f"{c['app']}/{c['naam']}: {c['oordeel']} ({c.get('waarde')})")

    # Proces-liveness.
    for p in processen:
        if p["oordeel"] in ("stil", "geen log"):
            det = f"{p['leeftijd_uur']}u geleden" if p.get("leeftijd_uur") is not None else p["oordeel"]
            aandacht.append(f"proces {p['naam']}: {p['oordeel']} ({det})")

    rapport = {"tijd": nu.isoformat(), "vm": vm, "containers": conts,
               "db_checks": checks, "processen": processen, "aandacht": aandacht}
    with open(UITVOER, "w") as f:
        json.dump(rapport, f, indent=2, default=str)

    print("=== Gezondheid AppPortal ===")
    print(f"{len(conts)} containers, {len(checks)} dataverse-checks,"
          f" {len(processen)} proces-checks\n")
    if aandacht:
        print(f"AANDACHT ({len(aandacht)}):")
        for a in aandacht:
            print("  - " + a)
    else:
        print("Alles gezond.")
    print("\nVM:")
    print(f"  schijf {vm.get('schijf_pct')}% ({vm.get('schijf_vrij_gb')} GB vrij)"
          f" trend={vm.get('schijf_stijging_ppu')} ppu"
          f" | RAM {vm.get('ram_vrij_mb')} MB vrij | swap {vm.get('swap_mb')} MB"
          f" | load {vm.get('load1')}/{vm.get('cores')}")
    print("\nDetail per container:")
    for c in conts:
        print(f"  {c['container']:38} {c['status']:8} health={c['health']:9}"
              f" herstart={c['herstarts']} fouten24u={c['fouten_24h']}")
    print("\nDataverse-checks:")
    for c in checks:
        extra = f" leeftijd={c.get('leeftijd_uur')}u" if "leeftijd_uur" in c else ""
        print(f"  {c['app']:14} {c['naam']:28} {c['oordeel']:10}"
              f" waarde={c.get('waarde')}{extra}")
    print("\nProcessen:")
    for p in processen:
        print(f"  {p['naam']:34} {p['oordeel']:9} leeftijd={p.get('leeftijd_uur')}u"
              f" (max {p.get('max_uur')}u)")
    return 0 if not aandacht else 1


if __name__ == "__main__":
    sys.exit(main())
