#!/usr/bin/env python3
"""De iCloud-wacht (Privé) — draait op Mehdi's Mac, niet op de VM: alleen daar staat
de fotobibliotheek. Elke avond leest hij Photos.sqlite (alleen lezen) en zet de
foto's van de dag klaar op het bord Mehdi Agents: tijd, plaats, bestand, uuid,
gegroepeerd per plek. De Dagbundelaar legt ze naast de locatie en de agenda; Mehdi
valideert op het bord; pas dan gaan ze via een runbook naar de projectmap.

Token: ~/.config/mijnagents/token (AGENTS_TOKEN van het bord). Bord:
https://mijnagents.globaal.be (de routes /agent-status, /api/klaarzet en
/api/logboek passeren de forward-auth en toetsen het token).
Gebruik: icloud_wacht.py [--dag JJJJ-MM-DD] | icloud_wacht.py --taken
  --taken: de foto-taken van de Werfverslag voorbereider uitvoeren (klaarzet soort taak, voor icloud-wacht):
  foto's van de bezoekdag binnen de straal van het werfadres exporteren naar <bezoekmap>/fotos/ in Dropbox.
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
ADRESSEN = os.path.expanduser("~/.config/mijnagents/adressen.json")
STRAAL_M = int(os.environ.get("FOTO_STRAAL_M", "300"))
VOOR_MIN, NA_MIN = 30, 90  # venster rond de afspraak waarin foto's bij het bezoek horen
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
    werk = [f for f in fotos if f.get("werk")]
    for f in fotos:
        f["export"] = ""
        f["geexporteerd"] = False
    for f in werk:
        ext = os.path.splitext(f["bestand"] or "")[1] or ".jpg"
        submap = os.path.join(doel, veilige_naam(f["werk"]))
        os.makedirs(submap, exist_ok=True)
        f["export"] = os.path.join(veilige_naam(f["werk"]), f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}")
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
                            f["export"] = os.path.join(veilige_naam(f["werk"]), f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}")
                            shutil.move(os.path.join(tmp, naam), os.path.join(doel, f["export"]))
                            f["geexporteerd"] = True
                            via_photos += 1
                            break
            else:
                print("Photos-export mislukt:", r.stderr.strip()[:200], file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print("Photos-export niet gelukt:", e, file=sys.stderr)
        shutil.rmtree(tmp, ignore_errors=True)
    nog = [f for f in werk if not f.get("geexporteerd")]
    json.dump({"datum": dag, "geschreven": datetime.now().astimezone().isoformat(), "aantal": len(fotos), "werk": len(werk),
               "geexporteerd": len(werk) - len(nog), "ontbrekend": len(nog), "regel": f"alleen foto's binnen {STRAAL_M} m en het tijdvenster van een werkafspraak worden geexporteerd; de rest blijft in Photos", "fotos": fotos,
               "groepen": [{"van": g["van"], "tot": g["tot"], "lat": g["lat"], "lon": g["lon"], "aantal": len(g["fotos"])} for g in groepen]},
              open(os.path.join(doel, "metadata.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    regels = [f"# Foto's {dag}", "", f"{len(fotos)} foto's/video's op de telefoon, {len(groepen)} plekken. {len(werk)} horen bij een werkafspraak en zijn geexporteerd "
              f"({len(nog)} daarvan nog niet uit iCloud). De andere {len(fotos) - len(werk)} blijven in Photos; hier alleen tijd en plek.", "",
              "| van | tot | aantal | plaats (lat, lon) | werkafspraak | bestanden |", "|---|---|---|---|---|---|"]
    for g in groepen:
        w = sorted({f["werk"] for f in g["fotos"] if f.get("werk")})
        regels.append(f"| {g['van']} | {g['tot']} | {len(g['fotos'])} | {g['lat']}, {g['lon']} | {'; '.join(w)[:60] or 'geen (niet geexporteerd)'} | "
                      + ", ".join(os.path.basename(f["export"]) for f in g["fotos"] if f.get("export"))[:200] + " |")
    if nog:
        regels += ["", "## Nog in iCloud (niet lokaal, Photos-export niet gelukt)", ""] + [f"- {f['tijd']} {f['bestand']}" for f in nog]
    open(os.path.join(doel, "overzicht.md"), "w", encoding="utf-8").write("\n".join(regels) + "\n")
    return gekopieerd, via_photos, len(nog)


def werkafspraken(dag):
    """Afspraken van die dag met een fysiek adres, uit de bak van De Agendawacht (alleen lezen)."""
    req = urllib.request.Request(f"{BORD}/api/klaarzet?status=alle&n=500", headers={"X-Agents-Token": TOKEN})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            items = json.loads(r.read().decode() or "{}").get("items", [])
    except Exception as e:  # noqa: BLE001
        print("afspraken niet gelezen:", e, file=sys.stderr)
        return []
    uit = []
    for it in items:
        if it.get("soort") != "afspraak":
            continue
        try:
            d = json.loads(it.get("inhoud") or "{}")
        except ValueError:
            continue
        adres = (d.get("locatie") or "").strip()
        if d.get("datum") != dag or not adres or adres.lower().startswith("http"):
            continue
        uit.append({"titel": d.get("titel") or it.get("titel", ""), "start": (d.get("start") or "")[11:16], "einde": (d.get("einde") or "")[11:16],
                    "adres": adres, "firma": d.get("firma", ""), "soort": d.get("soort", ""), "nummer": d.get("nummer", "")})
    return uit


def coord(adres):
    """Coördinaten van een adres via Nominatim, met cache van geslaagde antwoorden; probeert varianten
    (met 'België', zonder huisnummer, alleen straat en gemeente) vóór hij opgeeft. Mislukking wordt nooit gecachet."""
    import re
    import time
    import urllib.parse
    try:
        cache = json.load(open(ADRESSEN))
    except (OSError, ValueError):
        cache = {}
    k = adres.strip().lower()
    if cache.get(k):
        return cache[k]
    zonder_nr = re.sub(r"\b\d+[a-zA-Z]?\b\s*,?", "", adres, count=1).strip(" ,")
    zonder_post = re.sub(r"\b\d{4}\b", "", zonder_nr).strip(" ,")
    # Nominatim kent deelgemeenten (Kessel-Lo, Wijgmaal) vaak niet: straat + postcode werkt dan wel
    m_post = re.search(r"\b(\d{4})\b", adres)
    straat = re.split(r",|\b\d", adres, maxsplit=1)[0].strip()
    straat_post = f"{straat}, {m_post.group(1)}" if m_post and straat else ""
    varianten = [v for v in (adres, adres + ", België", straat_post, zonder_nr, zonder_post) if v]
    uit = None
    for q in varianten:
        time.sleep(1.1)
        url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": 1, "countrycodes": "be,nl"})
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "MehdiAgents-icloudwacht/1.0"}), timeout=20))
        except Exception:  # noqa: BLE001
            d = []
        if d:
            uit = [float(d[0]["lat"]), float(d[0]["lon"])]
            break
    if uit:
        cache[k] = uit
        os.makedirs(os.path.dirname(ADRESSEN), exist_ok=True)
        json.dump(cache, open(ADRESSEN, "w"))
    return uit


def afstand_m(lat1, lon1, lat2, lon2):
    import math
    p = math.pi / 180
    a = 0.5 - math.cos((lat2 - lat1) * p) / 2 + math.cos(lat1 * p) * math.cos(lat2 * p) * (1 - math.cos((lon2 - lon1) * p)) / 2
    return 12742000 * math.asin(math.sqrt(a))


def koppel_werk(fotos, afspraken):
    """Zet per foto 'werk' (afspraaktitel) als ze binnen het venster en binnen STRAAL_M van het adres valt."""
    from datetime import datetime as dt
    for a in afspraken:
        a["coord"] = coord(a["adres"])
    n = 0
    for f in fotos:
        f["werk"] = ""
        if f["lat"] is None:
            continue
        for a in afspraken:
            if not a.get("coord") or not a["start"]:
                continue
            t0 = dt.strptime(a["start"], "%H:%M") - timedelta(minutes=VOOR_MIN)
            t1 = dt.strptime(a["einde"] or a["start"], "%H:%M") + timedelta(minutes=NA_MIN)
            tf = dt.strptime(f["tijd"], "%H:%M")
            if t0 <= tf <= t1 and afstand_m(f["lat"], f["lon"], a["coord"][0], a["coord"][1]) <= STRAAL_M:
                f["werk"] = a["titel"]
                n += 1
                break
    return n


def veilige_naam(s):
    import re
    return re.sub(r"[^\w\- .,()]+", "", s or "").strip()[:60] or "afspraak"


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


DROPBOX_LOKAAL = os.path.expanduser(os.environ.get("DROPBOX_LOKAAL", "~/TKN-buro Dropbox"))


def taken_lezen():
    import urllib.parse
    req = urllib.request.Request(f"{BORD}/api/klaarzet?" + urllib.parse.urlencode({"voor": NAAM, "status": "klaar", "n": 50}),
                                 headers={"X-Agents-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return [it for it in json.loads(r.read().decode() or "{}").get("items", []) if it.get("soort") == "taak"]


def taak_opgepakt(kid):
    bord(f"/api/klaarzet/{kid}/opgepakt", {"door": NAAM})


def exporteer_naar(fotos, doel):
    """Originelen van de gegeven foto's naar de map doel (lokaal in Dropbox): lokaal kopiëren, anders via Photos."""
    import shutil
    import subprocess
    import tempfile
    os.makedirs(doel, exist_ok=True)
    klaar, ontbrekend = 0, []
    for f in fotos:
        ext = os.path.splitext(f["bestand"] or "")[1] or ".jpg"
        f["export"] = f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}"
        uit = os.path.join(doel, f["export"])
        if os.path.exists(uit) and os.path.getsize(uit) > 0:
            klaar += 1
            continue
        bron = os.path.join(LIB, f["uuid"][0], f"{f['uuid']}{ext}")
        if os.path.exists(bron) and os.path.getsize(bron) > 0:
            shutil.copy2(bron, uit)
            klaar += 1
        else:
            ontbrekend.append(f)
    for f in ontbrekend[:80]:
        # per foto een eigen tijdelijke map: Photos exporteert onder de originele bestandsnaam (IMG_9681.HEIC),
        # dus zo weet ik zeker welk bestand bij welke foto hoort
        tmp = tempfile.mkdtemp(prefix="foto-")
        script = f'tell application "Photos" to export {{media item id "{f["uuid"]}"}} to POSIX file "{tmp}" as alias with using originals'
        r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
        namen = [n for n in os.listdir(tmp) if not n.startswith(".")] if r.returncode == 0 else []
        if namen:
            naam = sorted(namen, key=lambda n: os.path.getsize(os.path.join(tmp, n)), reverse=True)[0]
            ext = os.path.splitext(naam)[1] or ".jpg"
            f["export"] = f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}"
            shutil.move(os.path.join(tmp, naam), os.path.join(doel, f["export"]))
            klaar += 1
        else:
            print("Photos-export mislukt voor", f["uuid"][:8], (r.stderr or "").strip()[:120], file=sys.stderr)
        shutil.rmtree(tmp, ignore_errors=True)
    return klaar


def jpeg_kopieen(doel, max_px=1800):
    """Naast elke HEIC een JPEG (sips, max 1800 px): Word en de bezoekpagina kunnen geen HEIC tonen; het origineel blijft."""
    import subprocess
    n = 0
    for naam in sorted(os.listdir(doel)):
        if not naam.lower().endswith(".heic"):
            continue
        jpg = os.path.join(doel, os.path.splitext(naam)[0] + ".jpg")
        if os.path.exists(jpg) and os.path.getsize(jpg) > 0:
            continue
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", "-Z", str(max_px), os.path.join(doel, naam), "--out", jpg],
                           capture_output=True, text=True)
        if r.returncode == 0:
            n += 1
    return n


def taken():
    """Foto-taken van de Werfverslag voorbereider: {dossier, datum, adres, bezoekmap}. Regel: alleen foto's van die dag
    binnen STRAAL_M van het werfadres; vindt de geocoder het huisnummer niet (straatmidden), dan 600 m en dat wordt gemeld.
    Nooit privéfoto's: wat buiten de straal valt blijft in Photos."""
    lijst = taken_lezen()
    if not lijst:
        return 0
    hartslag("actief", taak=f"{len(lijst)} foto-taak/taken van de voorbereider")
    regels, gedaan = [], 0
    for it in lijst:
        try:
            d = json.loads(it.get("inhoud") or "{}")
        except ValueError:
            d = {}
        dag, adres, bezoekmap, dossier = d.get("datum", ""), d.get("adres", ""), d.get("bezoekmap", ""), d.get("dossier", "?")
        if not (dag and adres and bezoekmap):
            regels.append({"naam": NAAM, "onderwerp": str(dossier), "stap": "fout", "tekst": f"taak {it['id']} onvolledig (datum, adres of bezoekmap ontbreekt)"})
            taak_opgepakt(it["id"]); continue
        c = coord(adres)
        if not c:
            regels.append({"naam": NAAM, "onderwerp": str(dossier), "stap": "fout", "tekst": f"{dag}: adres niet gevonden door de geocoder: {adres}", "detail": "Mehdi of de voorbereider geeft coördinaten (00 DOSSIER.md, regel C1)"})
            taak_opgepakt(it["id"]); continue
        fotos = [f for f in fotos_van(dag) if f["lat"] is not None]
        straal = STRAAL_M
        binnen = [f for f in fotos if afstand_m(f["lat"], f["lon"], c[0], c[1]) <= straal]
        if not binnen:
            straal = 600
            binnen = [f for f in fotos if afstand_m(f["lat"], f["lon"], c[0], c[1]) <= straal]
        if not binnen:
            regels.append({"naam": NAAM, "onderwerp": str(dossier), "stap": "bevinding", "tekst": f"{dag}: geen foto's binnen 600 m van {adres} ({len(fotos)} foto's met GPS die dag); niets geëxporteerd"})
            taak_opgepakt(it["id"]); continue
        doel = os.path.join(DROPBOX_LOKAAL, bezoekmap.lstrip("/"), "fotos")
        n = exporteer_naar(binnen, doel)
        jpeg_kopieen(doel)
        clat = round(sum(f["lat"] for f in binnen) / len(binnen), 5); clon = round(sum(f["lon"] for f in binnen) / len(binnen), 5)
        md = [f"# Foto's {dossier} {dag}", "", f"{len(binnen)} foto's van de iPhone binnen {straal} m van {adres} (zwaartepunt {clat}, {clon}); "
              f"geëxporteerd door de iCloud-wacht op {datetime.now().date().isoformat()}. Bron: iCloud-fotobibliotheek van Mehdi; foto's buiten de straal bleven in Photos.", "",
              "| tijd | bestand | lat, lon | afstand |", "|---|---|---|---|"]
        for f in sorted(binnen, key=lambda x: x["tijd"]):
            md.append(f"| {f['tijd']} | {f.get('export','')} | {f['lat']}, {f['lon']} | {int(afstand_m(f['lat'], f['lon'], c[0], c[1]))} m |")
        open(os.path.join(doel, "00 fotos.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
        regels.append({"naam": NAAM, "onderwerp": str(dossier), "stap": "schrijf",
                       "tekst": f"{dag}: {n} van {len(binnen)} foto's binnen {straal} m van {adres} geëxporteerd naar {bezoekmap}/fotos (zwaartepunt {clat}, {clon}"
                               + ("; straal verruimd tot 600 m omdat de geocoder geen huisnummer vond" if straal != STRAAL_M else "") + ")",
                       "detail": "\n".join(f"{f['tijd']} {f.get('export','')}" for f in binnen)})
        taak_opgepakt(it["id"]); gedaan += 1
    if regels:
        bord("/api/logboek", {"regels": regels})
    hartslag("klaar", taak=f"{gedaan} foto-taak/taken uitgevoerd", detail="foto's in de bezoekmap; de voorbereider ziet ze bij zijn volgende ronde")
    return gedaan


def main():
    if "--jpeg" in sys.argv:
        print("jpeg-kopieën:", jpeg_kopieen(sys.argv[sys.argv.index("--jpeg") + 1]))
        return
    if "--taken" in sys.argv:
        if not TOKEN:
            sys.exit("geen token")
        print("taken:", taken())
        return
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
    afspraken = werkafspraken(DAG)
    n_werk = koppel_werk(fotos, afspraken)
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
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf", "tekst": f"{len(afspraken)} werkafspraken met adres; {n_werk} foto's horen erbij (binnen {STRAAL_M} m en venster) en zijn geexporteerd naar {os.path.join(EXPORT, DAG)}: {gek} lokaal, {via} via Photos, {nog} nog niet; {len(fotos) - n_werk} foto's blijven in Photos (metadata alleen)",
         "detail": "\n".join(f"{a['start']}-{a['einde']} {a['titel'][:50]} @ {a['adres'][:40]} -> {'coord' if a.get('coord') else 'adres niet gevonden'}" for a in afspraken)},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf", "tekst": f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend"}]})
    hartslag("klaar", taak=f"foto's van {DAG} klaargezet", detail=f"{len(fotos)} foto's in {len(groepen)} plekken, {zonder_gps} zonder GPS; export {len(fotos) - nog} van {len(fotos)}")
    print(f"{DAG}: {len(fotos)} foto's, {len(groepen)} groepen, {len(afspraken)} werkafspraken, {n_werk} werkfoto's; export {gek} lokaal + {via} via Photos, {nog} ontbrekend; klaargezet {uit.get('nieuw', 0)} nieuw")


if __name__ == "__main__":
    main()
