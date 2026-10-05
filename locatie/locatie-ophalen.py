#!/usr/bin/env python3
"""
locatie-ophalen.py - haalt het locatielogboek van de Globaal-VM en zet het in
Dropbox privé (private/0 Chegini Mehdi/Prive met Claude/Locatielogboek).

Sinds 04-10-2026 (opdracht v1.2) maakt dit script geen eigen dagboek meer. De
tegel maakt het dagboek (locatie/dagboek.py), De Locatiewacht zet de vergelijking
met de agenda eronder, en dit script kopieert het resultaat. Eén generator voor
VM, bord en export; tot dan schreven twee scripts elk hun eigen versie.

Wat hier vastligt:
  - Alleen de actieve meetreeks: nooit een dag voor de startgrens (bronbeleid.py,
    3 oktober 2026). Oude dagboeken en oude databasekopieën blijven staan, buiten
    de verwerking; er wordt niets gewist.
  - Een dag met metingen wordt altijd weggeschreven, ook zonder indeling (een los
    punt). Tot 04-10-2026 werd zo'n dag overgeslagen.
  - Verandert een dagboek (late punten, een correctie), dan gaat de vorige versie
    naar dagen/revisies/.
  - Gemiste dagen worden ingehaald: vanaf de laatst afgesloten dag tot vandaag.
    Vandaag is voorlopig; een dag is afgesloten zes uur na middernacht.
  - De databasekopie krijgt de datum in de naam (ruwe-database/locatie-JJJJ-MM-DD.db);
    tot 04-10-2026 werd steeds dezelfde kopie overschreven.

De tegel zit achter Authentik; daarom gaat alles via SSH naar 127.0.0.1:3031.

Gebruik:
    locatie-ophalen.py                    inhalen tot en met vandaag
    locatie-ophalen.py --dagen 7          de afgelopen week (niet voor de grens)
    locatie-ophalen.py --dag 2026-10-04
Werkt onder /usr/bin/python3 (3.9), zoals launchd het start.
"""
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
import bronbeleid as B  # noqa: E402

VM = "globaal"
POORT = 3031
WACHT_DAGEN = "~/appportal/mijnagents-data/locatielogboek/dagen"
DOEL = os.path.expanduser(
    "~/TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude/Locatielogboek")
DAGEN = os.path.join(DOEL, "dagen")
RUWE_KOPIE = os.path.join(DOEL, "ruwe-database")
STAND = os.path.join(DOEL, "werkbestanden", "export-stand.json")
INHAAL_MAX = 31


# ------------------------------------------------------------------ ophalen

def over_ssh(opdracht, pogingen=3, wacht=20):
    """Voert iets uit op de VM en probeert opnieuw bij een netwerkhapering.

    De avondtaak van 11-09-2026 viel stil op "Connection reset by peer" en heeft
    daarna twee dagen niets meer geschreven. Een taak die om kwart voor elf in
    zijn eentje draait mag niet op de eerste hapering opgeven.
    """
    laatste = ""
    for poging in range(1, pogingen + 1):
        uit = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=5", VM, opdracht],
            capture_output=True, text=True, timeout=300)
        if uit.returncode == 0:
            return uit.stdout
        laatste = uit.stderr.strip()
        if poging < pogingen:
            print("   (poging %d mislukt: %s; opnieuw over %ds)" % (poging, laatste[:80], wacht), file=sys.stderr)
            time.sleep(wacht)
    raise SystemExit("SSH naar %s mislukt na %d pogingen: %s" % (VM, pogingen, laatste))


def haal_api(pad):
    uit = over_ssh("curl -s -m 240 'http://127.0.0.1:%d%s'" % (POORT, pad))
    if not uit.strip():
        raise SystemExit("Geen antwoord van de tegel op %s. Draait app-locatie?" % pad)
    return json.loads(uit)


def haal_dagboek(datum):
    """Het dagboek van de tegel (één generator). Alleen lezend: adressen komen uit de cache die
    De Locatiewacht laat vullen."""
    uit = over_ssh("curl -s -m 240 'http://127.0.0.1:%d/api/dagboek/%s'" % (POORT, datum))
    if not uit.strip():
        raise SystemExit("Geen antwoord van de tegel voor %s. Draait app-locatie?" % datum)
    return json.loads(uit)


def agenda_deel(datum, versie=None):
    """Het deel 'Naast de agenda' uit het dagboek van De Locatiewacht, alleen als het op dezelfde
    versie van het dagboek rust als wat de export nu ophaalt (controle 05-10-2026: dagboek en
    agendadeel konden uit verschillende revisies komen). Anders een korte melding."""
    try:
        tekst = over_ssh("cat %s/%s.md 2>/dev/null || true" % (WACHT_DAGEN, datum), pogingen=2, wacht=5)
    except SystemExit:
        return ""
    kop = "## Naast de agenda"
    if kop not in tekst:
        return ""
    if versie and ("dagboekversie %s" % versie) not in tekst:
        return kop + "\n\nVolgt na de volgende ronde van De Locatiewacht (het dagboek is intussen herzien).\n"
    return tekst[tekst.index(kop):].rstrip() + "\n"


def taak_melden(gelukt, detail):
    try:
        over_ssh("docker exec app-locatie python3 beheer.py taak export %s %s"
                 % ("ok" if gelukt else "fout", shlex.quote(detail[:300])), pogingen=2, wacht=5)
    except SystemExit:
        pass


# ------------------------------------------------------------------ schrijven

def schrijf_met_revisie(pad, tekst):
    """'nieuw', 'herzien' (vorige versie naar revisies/) of 'gelijk'."""
    if os.path.exists(pad):
        with open(pad, encoding="utf-8") as f:
            if f.read() == tekst:
                return "gelijk"
        rev = os.path.join(os.path.dirname(pad), "revisies")
        os.makedirs(rev, exist_ok=True)
        stam, ext = os.path.splitext(os.path.basename(pad))
        shutil.copy2(pad, os.path.join(rev, "%s.%s%s" % (stam, datetime.now().strftime("%Y%m%dT%H%M%S"), ext)))
        uitkomst = "herzien"
    else:
        os.makedirs(os.path.dirname(pad), exist_ok=True)
        uitkomst = "nieuw"
    with open(pad, "w", encoding="utf-8") as f:
        f.write(tekst)
    return uitkomst


def bestanden_voor(datum, gegevens, agenda=""):
    """(json-tekst, markdown) voor een dag. Een dag in de reeks wordt altijd geschreven,
    ook met een enkel punt of helemaal zonder meting: ontbreken is ook een gegeven."""
    if gegevens.get("buiten_reeks"):
        return None, None
    md = (gegevens.get("markdown") or "").rstrip() + "\n"
    if agenda:
        md += "\n" + agenda
    js = json.dumps(gegevens, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    return js, md


def kopieer_database():
    """Een consistente kopie van de SQLite, met de datum in de naam.

    Via `.backup` van sqlite3 zelf: een gewone cp levert bij WAL een halve database.
    Eén kopie per dag; een tweede ronde op dezelfde dag vervangt alleen die dag.
    Oudere kopieën blijven staan (opruimen is een beslissing van Mehdi)."""
    os.makedirs(RUWE_KOPIE, exist_ok=True)
    doel = os.path.join(RUWE_KOPIE, "locatie-%s.db" % date.today().isoformat())
    tijdelijk = "/tmp/locatie-kopie-%d.db" % os.getpid()
    opdracht = (
        "docker exec app-locatie python3 -c \"import sqlite3;"
        "b=sqlite3.connect('%s');"
        "sqlite3.connect('/data/locatie.db').backup(b);b.close()\" "
        "&& docker cp app-locatie:%s %s "
        "&& docker exec app-locatie rm -f %s"
    ) % (tijdelijk, tijdelijk, tijdelijk, tijdelijk)
    try:
        over_ssh(opdracht)
    except SystemExit as fout:
        print("   (kopie van de database mislukt: %s)" % str(fout)[:200], file=sys.stderr)
        return None
    haal = subprocess.run(["scp", "-q", "%s:%s" % (VM, tijdelijk), doel + ".deel"],
                          capture_output=True, text=True, timeout=300)
    subprocess.run(["ssh", "-o", "ConnectTimeout=15", VM, "rm -f %s" % tijdelijk], capture_output=True)
    if haal.returncode != 0:
        print("   (ophalen van de kopie mislukt)", file=sys.stderr)
        return None
    os.replace(doel + ".deel", doel)
    return doel


# ------------------------------------------------------------------ dagen

def lees_volledige_stand():
    try:
        with open(STAND, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    return {"afgesloten_tot": d.get("afgesloten_tot") or "", "versies": d.get("versies") or {}}


def lees_stand():
    return lees_volledige_stand()["afgesloten_tot"]


def te_doen(a, vandaag=None, revisies=None):
    """De dagen voor deze ronde, nooit voor de startgrens:
      - de open dagen na de laatst afgesloten dag, de OUDSTE eerst (hoogstens INHAAL_MAX per ronde);
        tot 05-10-2026 koos dit de nieuwste, en de launchd-taak gaf --dagen 2 mee;
      - een al afgesloten dag waarvan het dagboek sindsdien herzien is (revisies van /api/revisies)."""
    vandaag = vandaag or B.vandaag().isoformat()
    if a.dag:
        return [a.dag] if B.dag_toegestaan(a.dag) else []
    if a.dagen:
        start = (date.fromisoformat(vandaag) - timedelta(days=a.dagen - 1)).isoformat()
        return [d for d in B.dagen_vanaf_grens(vandaag) if d >= start]
    laatst, versies = lees_stand(), lees_volledige_stand()["versies"]
    open_ = [d for d in B.dagen_vanaf_grens(vandaag) if d > laatst][:INHAAL_MAX]
    herzien = [d for d, r in (revisies or {}).items()
               if d <= laatst and B.dag_toegestaan(d) and versies.get(d) != r.get("versie")]
    return sorted(set(open_) | set(herzien))


def bewaar_stand(afgesloten, versies=None):
    """Alleen aanroepen met dagen die echt weggeschreven zijn."""
    stand = lees_volledige_stand()
    oud = nieuw = stand["afgesloten_tot"]
    for d in B.dagen_vanaf_grens(max(afgesloten) if afgesloten else B.eerste_dag()):
        if d <= oud:
            continue
        if d in afgesloten:
            nieuw = d
        else:
            break
    stand["versies"].update(versies or {})
    os.makedirs(os.path.dirname(STAND), exist_ok=True)
    with open(STAND, "w", encoding="utf-8") as f:
        json.dump({"afgesloten_tot": nieuw, "versies": stand["versies"], "bijgewerkt": datetime.now().isoformat()}, f)
    return nieuw


# -------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description="Locatielogboek van de VM naar Dropbox privé")
    p.add_argument("--dag", help="een enkele dag, JJJJ-MM-DD (niet voor %s)" % B.eerste_dag())
    p.add_argument("--dagen", type=int, help="aantal dagen terug, nooit voor de startgrens")
    p.add_argument("--geen-kopie", action="store_true", help="sla de databasekopie over")
    a = p.parse_args()

    if a.dag and not B.dag_toegestaan(a.dag):
        print("%s valt voor de start van de meetreeks (%s): niets te doen." % (a.dag, B.eerste_dag()))
        return 0
    revisies, fouten = {}, []
    if not a.dag and not a.dagen:
        try:
            revisies = haal_api("/api/revisies").get("revisies") or {}
        except (SystemExit, ValueError) as e:
            # Nacontrole v1.5: dit stond alleen op stderr en de taak meldde 'gelukt', terwijl een
            # herziene afgesloten dag niet opgehaald werd. De open dagen gaan wel door; de versie van
            # een gemiste herziening blijft staan, dus de volgende gezonde ronde haalt ze alsnog.
            fouten.append("revisie-index niet op te halen, herziene afgesloten dagen niet nagekeken: %s"
                          % str(e)[:120])
    datums = te_doen(a, revisies=revisies)
    afgesloten, versies, regels = [], {}, []
    for datum in datums:
        try:
            gegevens = haal_dagboek(datum)
            js, md = bestanden_voor(datum, gegevens, agenda_deel(datum, gegevens.get("versie")))
            if js is None:
                continue
            h1 = schrijf_met_revisie(os.path.join(DAGEN, "%s.json" % datum), js)
            h2 = schrijf_met_revisie(os.path.join(DAGEN, "%s.md" % datum), md)
        except (SystemExit, ValueError, OSError) as e:
            fouten.append("%s: %s" % (datum, str(e)[:120]))
            continue
        punten = len(gegevens.get("punten") or [])
        regels.append("%s: %s, %d punten, %s/%s" % (datum, gegevens.get("status"), punten, h1, h2))
        print(regels[-1])
        versies[datum] = gegevens.get("versie")
        # Alleen een opgeslagen dag met een ingestelde tracker telt als afgesloten.
        if gegevens.get("status") == "afgesloten":
            afgesloten.append(datum)
    if not a.dag and not a.dagen:
        print("afgesloten tot", bewaar_stand(afgesloten, versies))
    kopie = None if a.geen_kopie else kopieer_database()
    if kopie:
        print("Kopie van de ruwe database: %s (%.1f MB)" % (os.path.basename(kopie), os.path.getsize(kopie) / 1048576))
    print("Doel:", DOEL)
    detail = "; ".join(regels) or "geen dagen te doen"
    if fouten:
        print("Fouten:", "; ".join(fouten), file=sys.stderr)
    taak_melden(not fouten and (kopie is not None or a.geen_kopie), (detail + ("; fouten: " + "; ".join(fouten) if fouten else ""))[:300])
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
