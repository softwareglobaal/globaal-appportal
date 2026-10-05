"""Beheer van het Locatielogboek vanaf de VM, zonder wachtwoord en zonder webroute.

Draait in de container (docker exec app-locatie python3 beheer.py ...), dus alleen
wie op de VM zit kan het. De Locatiewacht en het Mac-script melden hiermee hun
taakstatus; Mehdi (of Claude op zijn vraag) zet er een correctie of een override mee.

    beheer.py taak <dagboek|export|controle> <ok|fout> [detail]
    beheer.py correctie <bron> <van ISO> <tot ISO> <project|geen_project|niet_mehdi> [sleutel] --reden ... --door ...
    beheer.py intrekken <id> --door ...
    beheer.py override <FIRMA:nummer> --lat .. --lon .. [--straal ..] [--min ..] [--uitsluiten] --reden .. --door ..
    beheer.py thuis --adres "<straat nr, postcode gemeente>" --bron "<waar het adres vandaan komt>" --door ...
    beheer.py verrijk <dag>          adressen opzoeken en bezoekdagen tellen (netwerk eerst, dan kort schrijven)
    beheer.py status

Er wordt niets gewist: intrekken zet een tijdstip, een override vervangt alleen de vorige override.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bronbeleid as B  # noqa: E402
import projectsync  # noqa: E402
import schema  # noqa: E402


def _epoch(t):
    try:
        return int(float(t))
    except ValueError:
        d = datetime.fromisoformat(t)
        if d.tzinfo is None:
            d = d.replace(tzinfo=B.BRUSSEL)
        return int(d.timestamp())


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="wat", required=True)
    t = sub.add_parser("taak")
    t.add_argument("taak", choices=["dagboek", "export", "controle"])
    t.add_argument("uitkomst", choices=["ok", "fout"])
    t.add_argument("detail", nargs="?", default="")
    c = sub.add_parser("correctie")
    c.add_argument("bron", choices=sorted(B.BRONNEN))
    c.add_argument("van")
    c.add_argument("tot")
    c.add_argument("soort", choices=["project", "geen_project", "niet_mehdi"])
    c.add_argument("sleutel", nargs="?")
    c.add_argument("--reden", default="")
    c.add_argument("--door", required=True)
    i = sub.add_parser("intrekken")
    i.add_argument("id", type=int)
    i.add_argument("--door", required=True)
    o = sub.add_parser("override")
    o.add_argument("sleutel")
    o.add_argument("--lat", type=float)
    o.add_argument("--lon", type=float)
    o.add_argument("--straal", type=int)
    o.add_argument("--min", type=int, dest="min_minuten")
    o.add_argument("--uitsluiten", action="store_true")
    o.add_argument("--reden", required=True)
    o.add_argument("--door", required=True)
    th = sub.add_parser("thuis")
    th.add_argument("--adres", required=True)
    th.add_argument("--bron", required=True)
    th.add_argument("--door", required=True)
    v = sub.add_parser("verrijk")
    v.add_argument("dag")
    sub.add_parser("status")
    a = p.parse_args(argv)

    conn = schema.verbind(os.environ.get("LOCATIE_DB", "/data/locatie.db"))
    if a.wat == "taak":
        if a.uitkomst == "ok":
            projectsync.zet_taak(conn, a.taak, True, a.detail[:2000])
        else:
            projectsync.zet_taak(conn, a.taak, False, None, a.detail[:500] or "mislukt")
        print("taak", a.taak, a.uitkomst)
    elif a.wat == "correctie":
        if a.soort == "project" and not a.sleutel:
            p.error("een correctie 'project' heeft een sleutel nodig, bv. HARC:2604")
        cur = conn.execute("""INSERT INTO bezoekcorrectie (bron, van, tot, wat, sleutel, reden, door, wanneer)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                           (a.bron, _epoch(a.van), _epoch(a.tot), a.soort, a.sleutel, a.reden or None, a.door,
                            int(time.time())))
        conn.commit()
        print("correctie", cur.lastrowid, "bewaard")
    elif a.wat == "intrekken":
        conn.execute("UPDATE bezoekcorrectie SET ingetrokken = ?, reden = COALESCE(reden, '') || ? "
                     "WHERE id = ? AND ingetrokken IS NULL", (int(time.time()), " (ingetrokken door %s)" % a.door, a.id))
        conn.commit()
        print("correctie", a.id, "ingetrokken")
    elif a.wat == "override":
        conn.execute("""INSERT INTO projectplek_override (sleutel, lat, lon, straal, min_minuten, uitsluiten, reden,
                                                          door, wanneer)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(sleutel) DO UPDATE SET lat=excluded.lat, lon=excluded.lon,
                          straal=excluded.straal, min_minuten=excluded.min_minuten, uitsluiten=excluded.uitsluiten,
                          reden=excluded.reden, door=excluded.door, wanneer=excluded.wanneer""",
                     (a.sleutel, a.lat, a.lon, a.straal, a.min_minuten, 1 if a.uitsluiten else 0, a.reden, a.door,
                      int(time.time())))
        conn.commit()
        print("override", a.sleutel, "bewaard")
    elif a.wat == "thuis":
        # Thuis opnieuw bevestigen uit een toegestane adresbron (Geopunt), nooit uit oude metingen.
        # De vorige waarden gaan eerst naar plek_historiek; wifi-namen uit de telefoontijd vallen weg.
        import geocode  # noqa: PLC0415
        g = geocode.geocodeer(a.adres)
        if g.get("kwaliteit") != "adres":
            print("adres niet op huisnummer gevonden (%s): niets veranderd" % g.get("kwaliteit"))
            return 1
        conn.execute("""INSERT INTO plek_historiek (naam, lat, lon, straal, wifi, soort, notitie, dossier, firma, herkomst,
                                                    bewaard, reden)
                        SELECT naam, lat, lon, straal, wifi, soort, notitie, dossier, firma, herkomst, ?, ?
                        FROM plek WHERE naam = 'Thuis'""", (int(time.time()), "vervangen door bevestigd adres (%s)" % a.door))
        conn.execute("""INSERT INTO plek (naam, lat, lon, straal, wifi, soort, notitie, dossier, herkomst, actief)
                        VALUES ('Thuis', ?, ?, 150, NULL, 'thuis', ?, NULL, ?, 1)
                        ON CONFLICT(naam) DO UPDATE SET lat=excluded.lat, lon=excluded.lon, straal=150, wifi=NULL,
                          soort='thuis', notitie=excluded.notitie, herkomst=excluded.herkomst, actief=1""",
                     (g["lat"], g["lon"], a.adres, "adres uit %s, %s (%s, %s)" % (a.bron, g["bron"], a.door,
                                                                             time.strftime("%Y-%m-%d"))))
        conn.commit()
        print("Thuis bevestigd uit het adres (bron: %s, %s)" % (a.bron, g["bron"]))
    elif a.wat == "verrijk":
        if not B.dag_toegestaan(a.dag):
            print("%s valt voor de start van de meetreeks: niets te verrijken" % a.dag)
            return 0
        import app      # noqa: PLC0415
        import dagboek  # noqa: PLC0415
        g = app.dag_gegevens(a.dag)
        verblijven = [s for sp in (g.get("sporen") or {}).values() for s in sp["indeling"] if s["soort"] == "bezoek"]
        n = dagboek.verrijk_adressen(conn, a.dag, verblijven)
        print("verrijkt", a.dag, "-", n, "nieuwe adressen,", len(verblijven), "verblijven")
    else:
        import status  # noqa: PLC0415
        print(json.dumps(status.overzicht(conn), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
