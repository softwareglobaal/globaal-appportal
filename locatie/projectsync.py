"""Projectplekken uit hun bron halen en geocoderen, voor de herkenning.

Het adres blijft van de bron. Hier staat alleen de afgeleide geocode, met waar
het adres vandaan komt, een vingerafdruk van het adres, de datum, de geocodedienst
en de kwaliteit. Verandert het adres in de bron, dan verandert de vingerafdruk en
wordt de geocode vernieuwd. Een correctie hoort in de bron (de projectmap, H-A
Projecten); een plek die Mehdi met de hand bevestigt staat apart in
projectplek_override en wordt hier nooit overschreven.

De bronnen, in deze volgorde:
  1. **H-A Projecten** (ha-projecten.globaal.be, /api/projecten): H-Architects,
     de projecten 2025 en 2026 (de afbakening van het dashboard, v0.3). Elk project
     met zijn uuid, firma en nummer.
  2. **De projectmappen** (regel A13, projectadressen.json van De Agendawacht): het
     adres van een H-A-project uit zijn mapnaam, voor de H-A-nummers die buiten de
     afbakening van H-A Projecten vallen. Dezelfde bron die H-A Projecten zelf voor
     het adres gebruikt (A12); geen eigen register. Zonder deze laag zou de lopende
     werf 2145 (jaar 2021) niet herkend worden.
Andere firma's: hun eigen projectbron, nog aan te sluiten. Pipedrive is hier
bewust niet aangesproken.

Een project dat uit de bron verdwijnt wordt niet gewist maar op actief = 0 gezet.
Is een bron onbereikbaar, dan blijft de laatste goede index staan en zegt de
taakstatus dat, met de ouderdom erbij.

Draaien (op de VM): docker exec app-locatie python3 projectsync.py [--droog] [--om] [--opnieuw]
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import geocode  # noqa: E402

HA_URL = os.environ.get("HA_PROJECTEN_URL", "http://app-ha-projecten:3140")
HA_TOKEN = os.environ.get("HA_PROJECTEN_TOKEN", "")
PROJECTMAPPEN = os.environ.get("PROJECTMAPPEN_INDEX", "/bron/projectadressen.json")
HA_LINK = "https://ha-projecten.globaal.be/project/{nummer}"
DROPBOX = "https://www.dropbox.com/home"
HA_FIRMA = "HARC"


class BronFout(Exception):
    pass


def adres_vingerafdruk(adres):
    norm = re.sub(r"\s+", " ", (adres or "").strip().lower())
    return hashlib.sha256(norm.encode()).hexdigest()[:16] if norm else ""


# ------------------------------------------------------------ bronnen

def lees_ha_projecten(url=None, token=None):
    """De projecten uit H-A Projecten, met firma en adresherkomst expliciet."""
    url, token = url or HA_URL, HA_TOKEN if token is None else token
    if not token:
        raise BronFout("HA_PROJECTEN_TOKEN ontbreekt in de omgeving van app-locatie")
    verzoek = urllib.request.Request(url.rstrip("/") + "/api/projecten", headers={"X-Agents-Token": token})
    try:
        with urllib.request.urlopen(verzoek, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise BronFout(f"H-A Projecten niet bereikbaar: {type(e).__name__} {str(e)[:120]}")
    uit = []
    for p in d.get("projecten") or []:
        firma = p.get("firma") or d.get("firma")
        if not firma:
            raise BronFout("H-A Projecten levert geen firma per project; koppelen op nummer alleen mag niet")
        nr = str(p.get("nummer") or "")
        if not re.match(r"^\d{4}$", nr):
            continue
        uit.append({"firma": firma, "firma_id": p.get("firma_id"), "nummer": nr,
                    "project_id": p.get("project_id") or p.get("id"),
                    "naam": p.get("mapnaam") or p.get("adres") or nr,
                    "adres": (p.get("adres") or "").strip(),
                    "adres_bron": p.get("adres_bron") or ("projectmap (A13)" if p.get("map") else ""),
                    "status": p.get("status"), "bron": "ha-projecten",
                    "link": HA_LINK.format(nummer=nr)})
    return uit, {"versie": d.get("versie"), "afbakening": d.get("afbakening")}


def lees_projectmappen(pad=None):
    """{nummer: {adres, map, gemeente}} uit de index van de projectmappen (A13)."""
    pad = pad or PROJECTMAPPEN
    try:
        with open(pad, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError) as e:
        raise BronFout(f"projectmappen-index niet leesbaar: {type(e).__name__}")
    return d.get("projecten") or {}, {"gemaakt": d.get("ts")}


# ------------------------------------------------------------ synchroniseren

def verzamel(ha, mappen):
    """Eén lijst projectplekken uit beide bronnen. H-A Projecten gaat voor."""
    uit = {}
    for p in ha or []:
        uit["%s:%s" % (p["firma"], p["nummer"])] = dict(p)
    for nr, m in (mappen or {}).items():
        sleutel = "%s:%s" % (HA_FIRMA, nr)
        if sleutel in uit:
            continue
        uit[sleutel] = {"firma": HA_FIRMA, "firma_id": None, "nummer": str(nr), "project_id": None,
                        "naam": (m.get("map") or "").rsplit("/", 1)[-1] or m.get("adres"),
                        "adres": (m.get("adres") or "").strip(), "adres_bron": "projectmap (A13)",
                        "status": None, "bron": "projectmap",
                        "link": DROPBOX + urllib.request.quote(m.get("map") or "")}
    return uit


def synchroniseer(conn, ha=None, mappen=None, ha_fout=None, mappen_fout=None, geocodeer=None, nu=None,
                  opnieuw=False):
    """Werkt de tabel projectplek bij. Geeft het rapport (dict).

    In twee fasen (controle 05-10-2026: de vorige versie hield tijdens het geocoderen, tot 13 s
    per adres, een schrijftransactie open, zodat de ontvanger van de tracker 'database is locked'
    kreeg):
      1. lezen en geocoderen, zonder dat er een schrijftransactie openstaat;
      2. de volledige index in één korte transactie publiceren.
    ha/mappen: wat de bron gaf, of None als ze onbereikbaar was (dan ha_fout/mappen_fout). Een
    onbereikbare bron verandert niets aan de projecten die van haar kwamen. Kan de geocodedienst
    niet bereikt worden, dan blijft de vorige coördinaat van dat project staan.
    """
    geocodeer = geocodeer or geocode.geocodeer
    nu = int(nu or time.time())
    if ha is None and mappen is None:
        raise BronFout("geen enkele bron bereikbaar: " + "; ".join(x for x in (ha_fout, mappen_fout) if x))
    nieuw = verzamel(ha, mappen)
    gelezen = {b for b, lijst in (("ha-projecten", ha), ("projectmap", mappen)) if lijst is not None}
    if conn.in_transaction:
        conn.commit()
    bestaand = {r["sleutel"]: dict(r) for r in conn.execute("SELECT * FROM projectplek")}
    rapport = {"geocodeerd": 0, "ongewijzigd": 0, "uit_bron": 0, "fouten": [], "dienst_onbereikbaar": []}

    # Fase 1: alles uitrekenen, met het netwerk, zonder slot op de database.
    plan = []
    for sleutel, p in sorted(nieuw.items()):
        oud = bestaand.get(sleutel) or {}
        if ha is None and oud.get("bron") == "ha-projecten":
            continue    # H-A Projecten onbereikbaar: zijn laatste goede gegevens blijven staan
        afdruk = adres_vingerafdruk(p["adres"])
        # Een geocode op huisnummer blijft tot het adres verandert. Een grove of mislukte wordt
        # hoogstens eens per dag opnieuw geprobeerd (of meteen met opnieuw=True); een geocode die
        # mislukte omdat de dienst onbereikbaar was, bij elke ronde.
        oud_genoeg = opnieuw or (nu - (oud.get("geocode_datum") or 0)) > 20 * 3600
        kw = oud.get("geocode_kwaliteit")
        if oud and oud.get("adres_vingerafdruk") == afdruk and (
                kw == "adres" or (kw in ("straat", "gemeente", "geen_adres", "niet_gevonden") and not oud_genoeg)):
            geo = {"lat": oud["lat"], "lon": oud["lon"], "kwaliteit": kw, "bron": oud["geocode_bron"],
                   "datum": oud["geocode_datum"]}
            rapport["ongewijzigd"] += 1
        else:
            g = geocodeer(p["adres"])
            if g.get("kwaliteit") == "fout" and oud.get("lat") is not None:
                # De dienst was onbereikbaar: de vorige coördinaat blijft zichtbaar, de fout staat in het
                # rapport. Hoort ze bij een ander adres (het bronadres veranderde), dan heet ze
                # 'verouderd': ze herkent niet en wordt elke ronde opnieuw geprobeerd. Nacontrole v1.5:
                # anders gold coördinaat A blijvend als 'adres' voor het nieuwe adres B.
                zelfde = oud.get("adres_vingerafdruk") == afdruk
                geo = {"lat": oud["lat"], "lon": oud["lon"], "kwaliteit": kw if zelfde else "verouderd",
                       "bron": oud["geocode_bron"], "datum": oud["geocode_datum"]}
                rapport["dienst_onbereikbaar"].append(sleutel)
            else:
                geo = {"lat": g.get("lat"), "lon": g.get("lon"), "kwaliteit": g.get("kwaliteit"),
                       "bron": g.get("bron"), "datum": nu}
                rapport["geocodeerd"] += 1
                if g.get("kwaliteit") == "fout":
                    rapport["dienst_onbereikbaar"].append(sleutel)
        plan.append((sleutel, p, afdruk, geo, oud))

    # Fase 2: de volledige index in één korte transactie.
    conn.execute("BEGIN IMMEDIATE")
    try:
        for sleutel, p, afdruk, geo, oud in plan:
            conn.execute(
                """INSERT INTO projectplek (sleutel, firma, firma_id, nummer, project_id, naam, adres, adres_bron, bron,
                                            status, link, adres_vingerafdruk, lat, lon, geocode_bron, geocode_kwaliteit,
                                            geocode_datum, actief, eerst_gezien, laatst_gezien, bijgewerkt)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                   ON CONFLICT(sleutel) DO UPDATE SET
                     firma=excluded.firma, firma_id=excluded.firma_id, nummer=excluded.nummer,
                     project_id=excluded.project_id, naam=excluded.naam, adres=excluded.adres,
                     adres_bron=excluded.adres_bron, bron=excluded.bron, status=excluded.status, link=excluded.link,
                     adres_vingerafdruk=excluded.adres_vingerafdruk, lat=excluded.lat, lon=excluded.lon,
                     geocode_bron=excluded.geocode_bron, geocode_kwaliteit=excluded.geocode_kwaliteit,
                     geocode_datum=excluded.geocode_datum, actief=1, laatst_gezien=excluded.laatst_gezien,
                     bijgewerkt=excluded.bijgewerkt""",
                (sleutel, p["firma"], p.get("firma_id"), p["nummer"], p.get("project_id"), p.get("naam"), p["adres"],
                 p.get("adres_bron"), p["bron"], p.get("status"), p.get("link"), afdruk, geo["lat"], geo["lon"],
                 geo["bron"], geo["kwaliteit"], geo["datum"], oud.get("eerst_gezien") or nu, nu, nu))
        # Wat niet meer in een gelezen bron staat: niet wissen, wel uitzetten.
        for sleutel, oud in bestaand.items():
            if sleutel not in nieuw and oud.get("actief") and oud.get("bron") in gelezen:
                conn.execute("UPDATE projectplek SET actief = 0, bijgewerkt = ? WHERE sleutel = ?", (nu, sleutel))
                rapport["uit_bron"] += 1
        conn.execute("COMMIT")
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    rapport.update(dekking(conn))
    rapport["bronnen"] = {"ha-projecten": "gelezen" if ha is not None else ("onbereikbaar: " + (ha_fout or "")),
                          "projectmap": "gelezen" if mappen is not None else ("onbereikbaar: " + (mappen_fout or ""))}
    return rapport


def dekking(conn):
    """Hoeveel projectplekken er zijn, hoeveel kunnen herkennen, en wat ontbreekt of dubbelzinnig is."""
    rijen = [dict(r) for r in conn.execute("SELECT * FROM projectplek WHERE actief = 1")]
    over = {r[0] for r in conn.execute("SELECT sleutel FROM projectplek_override WHERE lat IS NOT NULL")}
    bruikbaar = [r for r in rijen if r["geocode_kwaliteit"] == "adres" or r["sleutel"] in over]
    geen_adres = sorted(r["sleutel"] for r in rijen if r["geocode_kwaliteit"] == "geen_adres")
    niet_gevonden = sorted(r["sleutel"] for r in rijen if r["geocode_kwaliteit"] == "niet_gevonden"
                           and r["sleutel"] not in over)
    grof = sorted(r["sleutel"] for r in rijen if r["geocode_kwaliteit"] in ("straat", "gemeente")
                  and r["sleutel"] not in over)
    storing = sorted(r["sleutel"] for r in rijen if r["geocode_kwaliteit"] in ("fout", "verouderd")
                     and r["sleutel"] not in over)
    per_adres = {}
    for r in rijen:
        if r.get("adres_vingerafdruk") and r["geocode_kwaliteit"] != "geen_adres":
            per_adres.setdefault(r["adres_vingerafdruk"], []).append(r["sleutel"])
    # Twee projecten op hetzelfde adres (2603 en 5603 op Provinciebaan 20): de herkenning
    # geeft daar altijd een kandidatenlijst, nooit een gekozen dossier.
    dubbel = sorted(sorted(v) for v in per_adres.values() if len(v) > 1)
    return {"projecten": len(rijen), "bruikbaar": len(bruikbaar), "per_bron": {
                b: sum(1 for r in rijen if r["bron"] == b) for b in sorted({r["bron"] for r in rijen})},
            "geen_adres": geen_adres, "niet_gevonden": niet_gevonden, "te_grof": grof, "geocode_storing": storing,
            "zelfde_adres": dubbel}


def zet_taak(conn, taak, gelukt, detail, fout=None, nu=None):
    nu = int(nu or time.time())
    if gelukt:
        conn.execute("""INSERT INTO taakstatus (taak, laatst_geprobeerd, laatst_geslaagd, fout, detail)
                        VALUES (?, ?, ?, NULL, ?)
                        ON CONFLICT(taak) DO UPDATE SET laatst_geprobeerd=excluded.laatst_geprobeerd,
                          laatst_geslaagd=excluded.laatst_geslaagd, fout=NULL, detail=excluded.detail""",
                     (taak, nu, nu, detail))
    else:
        conn.execute("""INSERT INTO taakstatus (taak, laatst_geprobeerd, fout, detail) VALUES (?, ?, ?, ?)
                        ON CONFLICT(taak) DO UPDATE SET laatst_geprobeerd=excluded.laatst_geprobeerd,
                          fout=excluded.fout""", (taak, nu, fout or "onbekende fout", detail))
    conn.commit()


def main():
    import bronbeleid  # noqa: PLC0415
    import schema  # noqa: PLC0415
    # Klokgrendel: de cron op de VM (UTC) start op beide mogelijke UTC-uren; alleen op het
    # Belgische uur uit bronbeleid.PLANNING gaat het door.
    if "--om" in sys.argv and not any(bronbeleid.binnen_venster(t) for t in bronbeleid.PLANNING["projectsync"]["tijden"]):
        return 0
    droog = "--droog" in sys.argv
    conn = schema.verbind(os.environ.get("LOCATIE_DB", "/data/locatie.db"))
    ha = mappen = None
    ha_fout = mappen_fout = None
    try:
        ha, _ = lees_ha_projecten()
    except BronFout as e:
        ha_fout = str(e)
    try:
        mappen, _ = lees_projectmappen()
    except BronFout as e:
        mappen_fout = str(e)
    if droog:
        lijst = verzamel(ha, mappen)
        print(json.dumps({"projecten": len(lijst), "ha_fout": ha_fout, "mappen_fout": mappen_fout,
                          "voorbeeld": list(lijst.values())[:3]}, ensure_ascii=False, indent=1))
        return 0
    try:
        rapport = synchroniseer(conn, ha, mappen, ha_fout, mappen_fout, opnieuw="--opnieuw" in sys.argv)
    except BronFout as e:
        zet_taak(conn, "projectsync", False, None, str(e))
        print("mislukt:", e)
        return 1
    fout = "; ".join(x for x in (ha_fout, mappen_fout) if x) or None
    detail = json.dumps(rapport, ensure_ascii=False)
    if rapport.get("dienst_onbereikbaar"):
        fout = "; ".join(x for x in (fout, "geocodedienst onbereikbaar voor %d adres(sen)"
                                      % len(rapport["dienst_onbereikbaar"])) if x)
    if fout:
        # Deels gelukt: wat bereikbaar was is bijgewerkt, maar de status zegt wat ontbrak.
        zet_taak(conn, "projectsync", False, detail, "deels: " + fout)
    else:
        zet_taak(conn, "projectsync", True, detail)
    print("%(projecten)d projectplekken, %(bruikbaar)d bruikbaar, %(geocodeerd)d opnieuw gegeocodeerd, "
          "%(uit_bron)d niet meer in de bron" % rapport)
    for soort in ("geen_adres", "niet_gevonden", "te_grof", "zelfde_adres"):
        if rapport.get(soort):
            print(f"  {soort}: {rapport[soort]}")
    if fout:
        print("  let op:", fout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
