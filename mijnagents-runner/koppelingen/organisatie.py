"""Wie werkt hier, bij welke afdeling en firma: de centrale gebruikersdatabase van de groep
(schema `kern` in de appportal-Postgres; dezelfde bron als organisatie.globaal.be en
namen.globaal.be). Alleen lezen. De runners draaien op de host en lezen via
`docker exec` in de Postgres-container; het resultaat wordt een dag bewaard in
mijnagents-data/organisatie.json. Geen wachtwoord nodig (de containergebruiker mag lezen).

Gebruik:
    organisatie.collegas()            -> [{"naam","voornaam","email","afdeling","firma","diensten_voor",...}]
    "firma" is de werkgever; "diensten_voor" zijn de firma's waarvoor die persoon werkt,
    en dat laatste bepaalt onder welke firma een interne afspraak valt. Zo staat het ook
    op organisatie.globaal.be, kolom "diensten voor".
    organisatie.herken(naam_of_mail)  -> collega-dict of None (voornaam, volledige naam of e-mail)
    organisatie.samenvatting()        -> korte tekst voor in een prompt (naam, afdeling, firma)
"""
import json
import os
import subprocess
import time

CACHE = os.path.expanduser("~/appportal/mijnagents-data/organisatie.json")
CACHE_FIRMA = os.path.expanduser("~/appportal/mijnagents-data/firmas.json")
CONTAINER = os.environ.get("KERN_POSTGRES_CONTAINER", "appportal-postgresql-1")
DB = os.environ.get("KERN_DB", "appportal")
SQL = ("select json_agg(json_build_object("
       "'naam', coalesce(p.weergavenaam, p.voornaam||' '||coalesce(p.achternaam,'')), 'voornaam', p.voornaam, 'achternaam', coalesce(p.achternaam,''), "
       "'email', coalesce(p.email,''), 'afdeling', coalesce(a.naam,''), 'firma', coalesce(f.naam,''), 'firma_code', coalesce(f.code,''), "
       "'rol', coalesce(p.rol,''), 'functie', coalesce(p.functie,''), 'locatie', coalesce(p.locatie,''), 'in_dienst', p.in_dienst, 'diensten_voor', coalesce((select json_agg(df.code order by df.code) from kern.persoon_dienstfirma pd join kern.firma df on df.id = pd.firma_id where pd.persoon_id = p.id), '[]'::json))) "
       "from kern.persoon p left join kern.afdeling a on a.id=p.afdeling_id left join kern.firma f on f.id=p.werkgever_firma_id")


def _lees():
    return _psql(SQL) or []


# Twee afkortingen per firma (migratie 175, 29-09-2026): code is de agendacode (ook
# firmacode genoemd) van vier letters (HARC), die sinds 21-09-2026 in de titel van een
# afspraak staat; code_contact de contactcode van twee letters (HA) voor de naamregel van
# een contact. Land is een ISO-code (BE, SR, IN). De tweede query is voor een database zonder
# migratie 175: dan ontbreekt code_contact.
SQL_FIRMA = ("select json_agg(json_build_object('code', f.code, 'code_contact', f.code_contact, 'naam', f.naam, "
             "'land', coalesce(f.land,''), 'actief', coalesce(f.actief, false))) from kern.firma f")
SQL_FIRMA_VOOR_175 = ("select json_agg(json_build_object('code', f.code, 'naam', f.naam, "
                      "'land', coalesce(f.land,''), 'actief', coalesce(f.actief, false))) from kern.firma f")


def _psql(sql):
    gebruiker = subprocess.run(["docker", "exec", CONTAINER, "sh", "-c", "echo $POSTGRES_USER"],
                               capture_output=True, text=True, timeout=30).stdout.strip() or "postgres"
    uit = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", gebruiker, "-d", DB, "-At", "-c", sql],
                         capture_output=True, text=True, timeout=60)
    if uit.returncode != 0:
        raise RuntimeError(uit.stderr.strip()[:200])
    return json.loads(uit.stdout.strip() or "null")


def _lees_firmas():
    try:
        return _psql(SQL_FIRMA) or []
    except RuntimeError as e:
        if "code_contact" not in str(e):
            raise
        return _psql(SQL_FIRMA_VOOR_175) or []


def firmas(maximum_uren=24):
    """De firma's van de groep met hun officiele codes, uit kern.firma.
    Dit is de enige bron voor afkortingen; nergens anders een lijst bijhouden.
    Elk item: code, code_contact, naam, land, actief. Een bewaarde lijst zonder
    code_contact (van voor migratie 175) telt als verouderd."""
    data = None
    try:
        c = json.load(open(CACHE_FIRMA, encoding="utf-8"))
        if (time.time() - c.get("ts", 0) < maximum_uren * 3600
                and all("code_contact" in f for f in c["firmas"])):
            data = c["firmas"]
    except (OSError, ValueError, KeyError):
        pass
    if data is None:
        try:
            data = _lees_firmas()
            os.makedirs(os.path.dirname(CACHE_FIRMA), exist_ok=True)
            json.dump({"ts": time.time(), "firmas": data}, open(CACHE_FIRMA, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=0)
        except Exception:  # noqa: BLE001
            try:
                data = json.load(open(CACHE_FIRMA, encoding="utf-8"))["firmas"]
            except (OSError, ValueError, KeyError):
                return []
    return sorted(data, key=lambda f: f.get("code") or "")


def firmacodes(maximum_uren=24):
    """code -> naam, alleen de codes die echt bestaan."""
    return {f["code"]: f["naam"] for f in firmas(maximum_uren) if f.get("code")}


def contactcodes(maximum_uren=24):
    """contactcode -> firmacode (HA -> HARC), voor de naamregel van een contact.
    Leeg als migratie 175 nog niet gedraaid is of de database niet bereikbaar is."""
    return {f["code_contact"]: f["code"] for f in firmas(maximum_uren) if f.get("code_contact")}


def bronregel(sleutel):
    """De regel van de pagina Bron van de waarheid (kern.bron_regel): status, beslisser,
    besloten_door, besloten_op. None als de regel of de tabel niet bestaat. Niet bewaard:
    een agent die hierop wacht, moet de klik van de beslisser meteen zien."""
    if not sleutel.replace("_", "").isalnum():
        raise ValueError("sleutel")
    try:
        return _psql("select row_to_json(r) from (select status, beslisser, besloten_door, besloten_op "
                     f"from kern.bron_regel where sleutel = '{sleutel}') r")
    except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired):
        return None


def collegas(maximum_uren=24, alleen_in_dienst=True):
    data = None
    try:
        c = json.load(open(CACHE, encoding="utf-8"))
        if time.time() - c.get("ts", 0) < maximum_uren * 3600:
            data = c["collegas"]
    except (OSError, ValueError, KeyError):
        pass
    if data is None:
        try:
            data = _lees()
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            json.dump({"ts": time.time(), "collegas": data}, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        except Exception:  # noqa: BLE001
            try:
                data = json.load(open(CACHE, encoding="utf-8"))["collegas"]
            except (OSError, ValueError, KeyError):
                return []
    return [p for p in data if p.get("in_dienst")] if alleen_in_dienst else data


def herken(tekst):
    """Collega bij voornaam, volledige naam of e-mail (hoofdletterongevoelig). Voornaam alleen als hij uniek is."""
    t = (tekst or "").strip().lower()
    if not t:
        return None
    lijst = collegas()
    for p in lijst:
        if t in (p["naam"].lower(), p["email"].lower()) and t:
            return p
    kandidaten = [p for p in lijst if p["voornaam"].lower() == t.split()[0]]
    return kandidaten[0] if len(kandidaten) == 1 else None


def firma_van(namen):
    """De firma waarvoor een groep mensen werkt, uit 'diensten voor' op
    organisatie.globaal.be. Werken ze allemaal voor dezelfde firma, dan is dat de firma
    van de afspraak. Anders geeft hij de firma's die ze gemeen hebben, of niets."""
    gemeen = None
    for n in namen:
        p = herken(n)
        if not p:
            continue
        dv = set(p.get("diensten_voor") or [])
        gemeen = dv if gemeen is None else (gemeen & dv)
    return sorted(gemeen) if gemeen else []


def samenvatting():
    per = {}
    for p in collegas():
        per.setdefault(p["afdeling"] or "zonder afdeling", []).append(
            f"{p['naam']} ({p['firma'] or '?'}" + (f", {p['rol']}" if p.get("rol") else "") + (f", {p['functie']}" if p.get("functie") else "") + ")")
    return "\n".join(f"- {afd}: " + "; ".join(sorted(namen)) for afd, namen in sorted(per.items()))


if __name__ == "__main__":
    lijst = collegas(maximum_uren=0)
    print(len(lijst), "collega's in dienst")
    print(samenvatting())
