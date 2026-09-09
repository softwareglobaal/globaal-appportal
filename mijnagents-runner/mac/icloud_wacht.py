#!/usr/bin/env python3
"""De iCloud-wacht (Privé) — draait op Mehdi's Mac, niet op de VM: alleen daar staat
de fotobibliotheek. Elke avond leest hij Photos.sqlite (alleen lezen) en zet de
foto's van de dag klaar op het bord Mehdi Agents: tijd, plaats, bestand, uuid,
gegroepeerd per plek. De Dagbundelaar legt ze naast de locatie en de agenda; Mehdi
valideert op het bord; pas dan gaan ze via een runbook naar de projectmap.

Token: ~/.config/mijnagents/token (AGENTS_TOKEN van het bord). Bord:
https://mijnagents.globaal.be (de routes /agent-status, /api/klaarzet en
/api/logboek passeren de forward-auth en toetsen het token).
Gebruik: icloud_wacht.py [--dag JJJJ-MM-DD]
"""
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta

NAAM = "icloud-wacht"
BORD = os.environ.get("MIJNAGENTS_URL", "https://mijnagents.globaal.be")
DB = os.path.expanduser("~/Pictures/Photos Library.photoslibrary/database/Photos.sqlite")
APPLE_EPOCH = 978307200
DAG = None
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
DAG = DAG or datetime.now().date().isoformat()


def token():
    try:
        return open(os.path.expanduser("~/.config/mijnagents/token")).read().strip()
    except OSError:
        return ""


TOKEN = token()


def bord(pad, payload):
    req = urllib.request.Request(f"{BORD}{pad}", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Agents-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def hartslag(status, taak="", detail=""):
    try:
        bord("/agent-status", {"naam": NAAM, "status": status, "taak": taak, "detail": detail})
    except Exception as e:  # noqa: BLE001
        print("hartslag mislukt:", e, file=sys.stderr)


def fotos_van(dag):
    d0 = datetime.fromisoformat(dag)
    van = d0.timestamp() - APPLE_EPOCH
    tot = (d0 + timedelta(days=1)).timestamp() - APPLE_EPOCH
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rijen = con.execute(
        "SELECT ZUUID, ZFILENAME, ZDATECREATED, ZLATITUDE, ZLONGITUDE, ZKIND FROM ZASSET "
        "WHERE ZDATECREATED >= ? AND ZDATECREATED < ? AND ZTRASHEDSTATE = 0 ORDER BY ZDATECREATED", (van, tot)).fetchall()
    con.close()
    uit = []
    for uuid, naam, t, lat, lon, kind in rijen:
        gps = lat is not None and lon is not None and lat > -180 and lon > -180
        uit.append({"uuid": uuid, "bestand": naam, "tijd": datetime.fromtimestamp(t + APPLE_EPOCH).strftime("%H:%M"),
                    "lat": round(lat, 5) if gps else None, "lon": round(lon, 5) if gps else None, "video": kind == 1})
    return uit


def groepeer(fotos):
    """Groepen: opeenvolgende foto's binnen ~300 m en 45 minuten van elkaar."""
    groepen = []
    for f in fotos:
        g = groepen[-1] if groepen else None
        if g and f["lat"] is not None and g["lat"] is not None:
            dt = (datetime.strptime(f["tijd"], "%H:%M") - datetime.strptime(g["tot"], "%H:%M")).total_seconds() / 60
            dicht = abs(f["lat"] - g["lat"]) < 0.003 and abs(f["lon"] - g["lon"]) < 0.004
            if dicht and 0 <= dt <= 45:
                g["fotos"].append(f); g["tot"] = f["tijd"]; continue
        groepen.append({"van": f["tijd"], "tot": f["tijd"], "lat": f["lat"], "lon": f["lon"], "fotos": [f]})
    return groepen


def main():
    if not TOKEN:
        print("geen token in ~/.config/mijnagents/token", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(DB):
        hartslag("fout", taak="fotobibliotheek niet gevonden", detail=DB)
        sys.exit(1)
    hartslag("actief", taak=f"foto's van {DAG} lezen")
    fotos = fotos_van(DAG)
    groepen = groepeer(fotos)
    zonder_gps = sum(1 for f in fotos if f["lat"] is None)
    items = []
    for i, g in enumerate(groepen, 1):
        items.append({"van": NAAM, "voor": "mehdi", "soort": "foto", "sleutel": DAG,
                      "titel": f"{DAG} {g['van']}-{g['tot']}: {len(g['fotos'])} foto's" + (f" bij {g['lat']},{g['lon']}" if g["lat"] is not None else " zonder plaats"),
                      "uniek": f"fotos:{DAG}:{i}:{g['fotos'][0]['uuid'][:8]}",
                      "inhoud": {"datum": DAG, "van": g["van"], "tot": g["tot"], "lat": g["lat"], "lon": g["lon"], "aantal": len(g["fotos"]),
                                 "fotos": g["fotos"][:200], "export": "osascript Photos.app met de uuid, alleen na validatie op het bord"}})
    uit = bord("/api/klaarzet", {"items": items}) if items else {"nieuw": 0, "bestaand": 0}
    bord("/api/logboek", {"regels": [
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "bron", "tekst": f"{len(fotos)} foto's/video's op {DAG}, {len(groepen)} plekken, {zonder_gps} zonder GPS",
         "detail": "\n".join(f"{g['van']}-{g['tot']} {len(g['fotos'])} foto's {g['lat']},{g['lon']}" for g in groepen)},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf", "tekst": f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend"}]})
    hartslag("klaar", taak=f"foto's van {DAG} klaargezet", detail=f"{len(fotos)} foto's in {len(groepen)} plekken, {zonder_gps} zonder GPS")
    print(f"{DAG}: {len(fotos)} foto's, {len(groepen)} groepen, klaargezet {uit.get('nieuw', 0)} nieuw")


if __name__ == "__main__":
    main()
