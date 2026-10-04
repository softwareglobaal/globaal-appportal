"""Beheer van het Locatielogboek vanaf de VM, zonder wachtwoord en zonder webroute.

Draait in de container (docker exec app-locatie python3 beheer.py ...), dus alleen
wie op de VM zit kan het. De Locatiewacht en het Mac-script melden hiermee hun
taakstatus; Mehdi (of Claude op zijn vraag) zet er een correctie of een override mee.

    beheer.py taak <dagboek|export|controle> <ok|fout> [detail]
    beheer.py correctie <bron> <van ISO> <tot ISO> <project|geen_project|niet_mehdi> [sleutel] --reden ... --door ...
    beheer.py intrekken <id> --door ...
    beheer.py override <FIRMA:nummer> --lat .. --lon .. [--straal ..] [--min ..] [--uitsluiten] --reden .. --door ..
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
    else:
        import status  # noqa: PLC0415
        print(json.dumps(status.overzicht(conn), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
