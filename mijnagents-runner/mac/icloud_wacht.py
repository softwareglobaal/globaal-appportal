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
# Waar de foto's van de dag landen (regel van Mehdi, 12-09-2026): bron én metadata samen in één map,
# in zijn eigen Dropbox-app-map (leesbaar voor de agents op de VM); de Mac-synctaak kopieert ze
# ook naar Data uit Mehdi/Fotos. Na validatie kopieert een runbook ze naar de projectmap; het
# origineel blijft hier staan, zodat de agents er later uit kunnen leren.
EXPORT = os.path.expanduser(os.environ.get("FOTO_EXPORT", "~/TKN-buro Dropbox/H-Architects bvba/Apps/Mehdi Agents/Fotos"))
LIB = os.path.expanduser("~/Pictures/Photos Library.photoslibrary/originals")
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


def exporteer(fotos, dag, groepen):
    """Schrijft <EXPORT>/<dag>/: metadata.json, overzicht.md en de originelen als
    '<UUMM> <uuid8>.<ext>'. Lokale originelen kopieert hij uit de bibliotheek; wat alleen in
    iCloud staat vraagt hij in één keer aan Photos (osascript export 'with using originals').
    Geeft (gekopieerd, via_photos, ontbrekend)."""
    import shutil
    import subprocess
    import tempfile
    doel = os.path.join(EXPORT, dag)
    os.makedirs(doel, exist_ok=True)
    gekopieerd, ontbrekend = 0, []
    for f in fotos:
        ext = os.path.splitext(f["bestand"] or "")[1] or ".jpg"
        f["export"] = f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}"
        uit = os.path.join(doel, f["export"])
        if os.path.exists(uit) and os.path.getsize(uit) > 0:
            f["geexporteerd"] = True
            continue
        bron = os.path.join(LIB, f["uuid"][0], f"{f['uuid']}{ext}")
        if os.path.exists(bron) and os.path.getsize(bron) > 0:
            shutil.copy2(bron, uit)
            f["geexporteerd"] = True
            gekopieerd += 1
        else:
            f["geexporteerd"] = False
            ontbrekend.append(f)
    via_photos = 0
    if ontbrekend:
        tmp = tempfile.mkdtemp(prefix="fotos-")
        items = ", ".join(f'media item id "{f["uuid"]}"' for f in ontbrekend[:150])
        script = f'tell application "Photos" to export {{{items}}} to POSIX file "{tmp}" as alias with using originals'
        try:
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=1200)
            if r.returncode == 0:
                for naam in os.listdir(tmp):
                    stam = os.path.splitext(naam)[0].upper()
                    for f in ontbrekend:
                        if not f["geexporteerd"] and (stam == f["uuid"].upper() or stam == os.path.splitext(f["bestand"] or "")[0].upper()):
                            ext = os.path.splitext(naam)[1]
                            f["export"] = f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}"
                            shutil.move(os.path.join(tmp, naam), os.path.join(doel, f["export"]))
                            f["geexporteerd"] = True
                            via_photos += 1
                            break
            else:
                print("Photos-export mislukt:", r.stderr.strip()[:200], file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print("Photos-export niet gelukt:", e, file=sys.stderr)
        shutil.rmtree(tmp, ignore_errors=True)
    nog = [f for f in fotos if not f.get("geexporteerd")]
    json.dump({"datum": dag, "geschreven": datetime.now().astimezone().isoformat(), "aantal": len(fotos),
               "geexporteerd": len(fotos) - len(nog), "ontbrekend": len(nog), "fotos": fotos,
               "groepen": [{"van": g["van"], "tot": g["tot"], "lat": g["lat"], "lon": g["lon"], "aantal": len(g["fotos"])} for g in groepen]},
              open(os.path.join(doel, "metadata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    regels = [f"# Foto's {dag}", "", f"{len(fotos)} foto's/video's, {len(groepen)} plekken, {len(nog)} nog niet uit iCloud gehaald.", "",
              "| van | tot | aantal | plaats (lat, lon) | bestanden |", "|---|---|---|---|---|"]
    for g in groepen:
        regels.append(f"| {g['van']} | {g['tot']} | {len(g['fotos'])} | {g['lat']}, {g['lon']} | " + ", ".join(f["export"] for f in g["fotos"][:8]) + (" ..." if len(g["fotos"]) > 8 else "") + " |")
    if nog:
        regels += ["", "## Nog in iCloud (niet lokaal, Photos-export niet gelukt)", ""] + [f"- {f['tijd']} {f['bestand']}" for f in nog]
    open(os.path.join(doel, "overzicht.md"), "w", encoding="utf-8").write("\n".join(regels) + "\n")
    return gekopieerd, via_photos, len(nog)


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
    gek, via, nog = exporteer(fotos, DAG, groepen) if fotos else (0, 0, 0)
    items = []
    for i, g in enumerate(groepen, 1):
        items.append({"van": NAAM, "voor": "mehdi", "soort": "foto", "sleutel": DAG,
                      "titel": f"{DAG} {g['van']}-{g['tot']}: {len(g['fotos'])} foto's" + (f" bij {g['lat']},{g['lon']}" if g["lat"] is not None else " zonder plaats"),
                      "uniek": f"fotos:{DAG}:{i}:{g['fotos'][0]['uuid'][:8]}",
                      "inhoud": {"datum": DAG, "van": g["van"], "tot": g["tot"], "lat": g["lat"], "lon": g["lon"], "aantal": len(g["fotos"]),
                                 "fotos": g["fotos"][:200], "export_map": os.path.join(EXPORT, DAG),
                                 "naar_projectmap": "pas na validatie op het bord (runbook); het origineel blijft in de export-map"}})
    uit = bord("/api/klaarzet", {"items": items}) if items else {"nieuw": 0, "bestaand": 0}
    bord("/api/logboek", {"regels": [
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "bron", "tekst": f"{len(fotos)} foto's/video's op {DAG}, {len(groepen)} plekken, {zonder_gps} zonder GPS",
         "detail": "\n".join(f"{g['van']}-{g['tot']} {len(g['fotos'])} foto's {g['lat']},{g['lon']}" for g in groepen)},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf", "tekst": f"export naar {os.path.join(EXPORT, DAG)}: {gek} originelen gekopieerd, {via} via Photos uit iCloud, {nog} nog niet beschikbaar"},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf", "tekst": f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend"}]})
    hartslag("klaar", taak=f"foto's van {DAG} klaargezet", detail=f"{len(fotos)} foto's in {len(groepen)} plekken, {zonder_gps} zonder GPS; export {len(fotos) - nog} van {len(fotos)}")
    print(f"{DAG}: {len(fotos)} foto's, {len(groepen)} groepen, klaargezet {uit.get('nieuw', 0)} nieuw; export {gek} lokaal + {via} via Photos, {nog} ontbrekend")


if __name__ == "__main__":
    main()
