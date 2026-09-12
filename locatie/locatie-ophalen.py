#!/usr/bin/env python3
"""
locatie-ophalen.py - haalt het locatielogboek van de Globaal-VM en schrijft het
als leesbaar dagboek naar Dropbox.

De tegel locatie.globaal.be zit achter Authentik en is dus niet zomaar te
bevragen. Daarom halen we de gegevens via SSH rechtstreeks bij de container
(127.0.0.1:3031), langs de login om.

Coordinaten worden hier omgezet naar adressen. Dat gebeurt bewust pas in dit
script en niet in de tegel: zo blijft de ruwe meting op de server onaangetast
en kunnen we de adressen later opnieuw opbouwen met een andere bron.

Gebruik:
    locatie-ophalen.py                    gisteren en vandaag
    locatie-ophalen.py --dagen 7          de afgelopen week
    locatie-ophalen.py --dag 2026-09-09
    locatie-ophalen.py --geen-adressen    sneller, alleen coordinaten
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
from datetime import date, datetime, timedelta

VM = "globaal"
POORT = 3031
DOEL = os.path.expanduser(
    "~/TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude/Locatielogboek")
# Bewust in Application Support en niet in ~/Documents: macOS weigert
# achtergrondtaken (launchd) toegang tot Documents, Bureaublad en Downloads,
# zonder dat de gebruiker daar iets van merkt behalve een PermissionError.
ADRESCACHE = os.path.join(DOEL, "werkbestanden", "adressen.json")
RUWE_KOPIE = os.path.join(DOEL, "ruwe-database")

DAGEN_NL = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag",
            "zaterdag", "zondag"]
MAANDEN_NL = ["", "januari", "februari", "maart", "april", "mei", "juni",
              "juli", "augustus", "september", "oktober", "november", "december"]


def nl_datum(d):
    return f"{DAGEN_NL[d.weekday()]} {d.day} {MAANDEN_NL[d.month]} {d.year}"


# ------------------------------------------------------------------ ophalen

def over_ssh(opdracht, pogingen=3, wacht=20):
    """Voert iets uit op de VM en probeert opnieuw bij een netwerkhapering.

    De avondtaak van 11-09-2026 viel stil op "Connection reset by peer" en heeft
    daarna twee dagen niets meer geschreven. Een taak die om kwart voor elf in
    zijn eentje draait mag niet op de eerste hapering opgeven; niemand ziet dat.
    """
    laatste = ""
    for poging in range(1, pogingen + 1):
        uit = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=5",
             VM, opdracht],
            capture_output=True, text=True, timeout=180)
        if uit.returncode == 0:
            return uit.stdout
        laatste = uit.stderr.strip()
        if poging < pogingen:
            print(f"   (poging {poging} mislukt: {laatste[:80]}; opnieuw over {wacht}s)",
                  file=sys.stderr)
            time.sleep(wacht)
    raise SystemExit(f"SSH naar {VM} mislukt na {pogingen} pogingen: {laatste}")


def haal_dag(datum):
    """Vraagt de tegel om een dag, via SSH langs de login om."""
    uit = over_ssh(f"curl -s -m 20 http://127.0.0.1:{POORT}/api/dag/{datum}")
    if not uit.strip():
        raise SystemExit(f"Geen antwoord van de tegel voor {datum}. Draait app-locatie?")
    return json.loads(uit)


# ----------------------------------------------------------------- adressen

def laad_cache():
    try:
        with open(ADRESCACHE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def bewaar_cache(cache):
    os.makedirs(os.path.dirname(ADRESCACHE), exist_ok=True)
    with open(ADRESCACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)


def adres_van(lat, lon, cache):
    """Coordinaat naar adres via Nominatim (OpenStreetMap).

    Afgerond op vier decimalen (ongeveer 10 meter) zodat twee bezoeken aan
    dezelfde plek dezelfde cachesleutel krijgen. Nominatim staat maximaal een
    bevraging per seconde toe en eist een herkenbare user-agent.
    """
    sleutel = f"{lat:.4f},{lon:.4f}"
    if sleutel in cache:
        return cache[sleutel]

    vraag = urllib.parse.urlencode({
        "lat": lat, "lon": lon, "format": "json", "zoom": 18,
        "accept-language": "nl"})
    # Bewust curl en niet urllib: de Python van python.org op deze Mac heeft geen
    # koppeling met de systeemcertificaten en weigert elke https-verbinding met
    # CERTIFICATE_VERIFY_FAILED. Curl gebruikt de sleutelhanger wel.
    try:
        uit = subprocess.run(
            ["curl", "-s", "-m", "20",
             "-A", "locatielogboek-mehdi/1.0 (mch@h-architects.be)",
             "https://nominatim.openstreetmap.org/reverse?" + vraag],
            capture_output=True, text=True, timeout=30)
        d = json.loads(uit.stdout)
    except Exception as fout:
        print(f"   (adres opzoeken mislukt voor {sleutel}: {fout})", file=sys.stderr)
        return None
    finally:
        time.sleep(1.1)   # nooit sneller dan een bevraging per seconde

    a = d.get("address", {})
    straat = " ".join(x for x in (a.get("road"), a.get("house_number")) if x)
    plaats = (a.get("city") or a.get("town") or a.get("village")
              or a.get("municipality") or a.get("suburb") or "")
    kort = ", ".join(x for x in (straat, plaats) if x) or d.get("display_name", "")
    cache[sleutel] = {"kort": kort, "volledig": d.get("display_name", "")}
    return cache[sleutel]


def kopieer_database():
    """Haalt een consistente kopie van de SQLite naar Dropbox.

    Het bestand zelf kan niet in Dropbox staan: de container schrijft er live
    in en synchronisatie tijdens een schrijfactie beschadigt een SQLite-bestand.
    Daarom een kopie, en wel via `.backup` van sqlite3 zelf. Dat is de enige
    manier die een lopende schrijfactie correct afhandelt; een gewone cp levert
    bij WAL-journaling een halve database op.
    """
    os.makedirs(RUWE_KOPIE, exist_ok=True)
    doel = os.path.join(RUWE_KOPIE, "locatie.db")
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
    haal = subprocess.run(["scp", "-q", "%s:%s" % (VM, tijdelijk), doel],
                          capture_output=True, text=True, timeout=120)
    subprocess.run(["ssh", "-o", "ConnectTimeout=15", VM, "rm -f %s" % tijdelijk],
                   capture_output=True)
    if haal.returncode != 0:
        print("   (ophalen van de kopie mislukt)", file=sys.stderr)
        return None
    return doel


# ------------------------------------------------------------------ opmaak

def uur(iso_of_epoch):
    if isinstance(iso_of_epoch, (int, float)):
        return datetime.fromtimestamp(iso_of_epoch).strftime("%H:%M")
    return datetime.fromisoformat(iso_of_epoch).strftime("%H:%M")


def duur(minuten):
    u, m = divmod(int(minuten), 60)
    return f"{u}u{m:02d}" if u else f"{m} min"


def markdown(datum, gegevens, cache, adressen=True):
    d = date.fromisoformat(datum)
    indeling = gegevens.get("indeling", [])
    punten = gegevens.get("punten", [])
    bezoeken = [s for s in indeling if s["soort"] == "bezoek"]
    ritten = [s for s in indeling if s["soort"] == "verplaatsing"]
    gaten = [s for s in indeling if s["soort"] == "gat"]
    km = sum(s.get("meter", 0) for s in ritten) / 1000

    r = [f"# {nl_datum(d)}", ""]
    if not indeling:
        r.append("Geen gegevens. De telefoon heeft die dag niets doorgestuurd.")
        return "\n".join(r) + "\n"

    r.append(f"{len(bezoeken)} bezoeken, {len(ritten)} verplaatsingen, "
             f"{km:.1f} km, {len(punten)} meetpunten")
    if gaten:
        zonder = sum(s["minuten"] for s in gaten)
        r.append("")
        r.append(f"Let op: {len(gaten)} keer zweeg de telefoon, samen {duur(zonder)} zonder meting.")
    r.append("")
    r.append("| van | tot | duur | wat | waar | wifi |")
    r.append("|---|---|---|---|---|---|")
    for s in indeling:
        if s["soort"] == "bezoek":
            waar = f"{s['lat']:.5f}, {s['lon']:.5f}"
            if adressen:
                a = adres_van(s["lat"], s["lon"], cache)
                if a and a["kort"]:
                    waar = f"{a['kort']} ([kaart](https://maps.google.com/?q={s['lat']},{s['lon']}))"
            # Een vastgelegde naam gaat voor het opgezochte adres: "Thuis" zegt
            # meer dan "Herfstlaan 65", en blijft kloppen als de GPS afdrijft.
            if s.get("plek"):
                merk = f"**{s['plek']}**"
                if s.get("dossier"):
                    merk += f" `{s['dossier']}`"
                waar = f"{merk} ({waar})"
            if (s.get("langste_stilte") or 0) > 30:
                waar += f" (stilte {s['langste_stilte']} min)"
            r.append(f"| {uur(s['van'])} | {uur(s['tot'])} | {duur(s['minuten'])} "
                     f"| bezoek | {waar} | {s.get('wifi') or ''} |")
        elif s["soort"] == "gat":
            r.append(f"| {uur(s['van'])} | {uur(s['tot'])} | {duur(s['minuten'])} "
                     f"| *geen meting* | *{s['meter'] / 1000:.1f} km hemelsbreed* | |")
        else:
            wijze = {"automotive": "auto", "cycling": "fiets", "walking": "te voet",
                     "running": "lopend"}.get(s.get("wijze"), s.get("wijze") or "")
            r.append(f"| {uur(s['van'])} | {uur(s['tot'])} | {duur(s['minuten'])} "
                     f"| onderweg {wijze} | {s['meter'] / 1000:.1f} km | |")

    if bezoeken and adressen:
        r += ["", "## Bezoeken op een rij", ""]
        for s in bezoeken:
            a = cache.get(f"{s['lat']:.4f},{s['lon']:.4f}")
            naam = a["volledig"] if a else f"{s['lat']:.5f}, {s['lon']:.5f}"
            if s.get("plek"):
                naam = f"{s['plek']} - {naam}"
            r.append(f"- **{uur(s['van'])}-{uur(s['tot'])}** ({duur(s['minuten'])}) {naam}")

    r += ["", "---", "",
          "Een bezoek is minstens 8 minuten binnen 150 meter; een gat is een stilte "
          "van meer dan 30 minuten waarna je elders was. Bron: "
          "locatie.globaal.be, verzameld met OwnTracks. Adressen via OpenStreetMap."]
    return "\n".join(r) + "\n"


# -------------------------------------------------------------------- main

def main():
    p = argparse.ArgumentParser(description="Locatielogboek van de VM naar Dropbox")
    p.add_argument("--dag", help="een enkele dag, JJJJ-MM-DD")
    p.add_argument("--dagen", type=int, default=2, help="aantal dagen terug (standaard 2)")
    p.add_argument("--geen-adressen", action="store_true",
                   help="sla het opzoeken van adressen over")
    a = p.parse_args()

    if a.dag:
        datums = [a.dag]
    else:
        vandaag = date.today()
        datums = [(vandaag - timedelta(days=i)).isoformat()
                  for i in range(a.dagen - 1, -1, -1)]

    os.makedirs(os.path.join(DOEL, "dagen"), exist_ok=True)
    os.makedirs(os.path.join(DOEL, "werkbestanden"), exist_ok=True)
    cache = laad_cache()
    geschreven = leeg = 0

    for datum in datums:
        gegevens = haal_dag(datum)
        indeling = gegevens.get("indeling", [])
        if not indeling:
            print(f"{datum}: geen gegevens")
            leeg += 1
            continue

        with open(os.path.join(DOEL, "dagen", f"{datum}.json"), "w",
                  encoding="utf-8") as f:
            json.dump(gegevens, f, ensure_ascii=False, indent=1)
        with open(os.path.join(DOEL, "dagen", f"{datum}.md"), "w",
                  encoding="utf-8") as f:
            f.write(markdown(datum, gegevens, cache, not a.geen_adressen))

        bez = len([s for s in indeling if s["soort"] == "bezoek"])
        km = sum(s.get("meter", 0) for s in indeling
                 if s["soort"] == "verplaatsing") / 1000
        print(f"{datum}: {bez} bezoeken, {km:.1f} km")
        geschreven += 1

    bewaar_cache(cache)
    print(f"\n{geschreven} dagen weggeschreven, {leeg} leeg.")

    kopie = kopieer_database()
    if kopie:
        mb = os.path.getsize(kopie) / 1024 / 1024
        print(f"Kopie van de ruwe database: {mb:.1f} MB")
    print(f"Doel: {DOEL}")


if __name__ == "__main__":
    main()
