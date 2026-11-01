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
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
import uuid
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

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
SELECTIE_RUST_MIN = 45
# Hetzelfde vangnet als verslag_basis.ZONDER_TAKEN_UUR; de geïsoleerde Mac-starter kan de VM-module niet importeren.
ZONDER_TAKEN_UUR = 6
SELECTIE_STAAT = os.path.expanduser("~/.config/mijnagents/icloud_selecties")
MELDING_STAAT = os.path.expanduser("~/.config/mijnagents/icloud_meldingen.json")
# Redenen waarbij de wacht zelf faalde (export of omzetting); al de rest is een taak die op gegevens wacht.
WACHTFOUTEN = frozenset({"exportresultaat_ongeldig", "omzetting_mislukt", "fotolevering_gedeeltelijk"})
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
        versie = Path(__file__).with_name("VERSIE").read_text(encoding="utf-8").strip() or "onbekend"
    except OSError:
        versie = "onbekend"
    try:
        bord("/agent-status", {"naam": NAAM, "status": status, "taak": taak,
                               "detail": f"VERSIE {versie}" + (f"; {detail}" if detail else "")})
    except Exception as e:  # noqa: BLE001
        print("hartslag mislukt:", e, file=sys.stderr)


def fotos_van(dag):
    d0 = datetime.fromisoformat(dag).replace(tzinfo=ZoneInfo("Europe/Brussels"))
    van = d0.timestamp() - APPLE_EPOCH
    tot = (d0 + timedelta(days=1)).timestamp() - APPLE_EPOCH
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    basis = ("SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZLATITUDE, a.ZLONGITUDE, a.ZKIND "
             "FROM ZASSET a WHERE a.ZDATECREATED >= ? AND a.ZDATECREATED < ? "
             "AND a.ZTRASHEDSTATE = 0 ORDER BY a.ZDATECREATED")
    try:
        try:
            rijen = con.execute(
                "SELECT a.ZUUID, a.ZFILENAME, a.ZDATECREATED, a.ZLATITUDE, a.ZLONGITUDE, a.ZKIND, "
                "aa.ZORIGINALFILENAME FROM ZASSET a LEFT JOIN ZADDITIONALASSETATTRIBUTES aa ON aa.ZASSET = a.Z_PK "
                "WHERE a.ZDATECREATED >= ? AND a.ZDATECREATED < ? AND a.ZTRASHEDSTATE = 0 "
                "ORDER BY a.ZDATECREATED", (van, tot)).fetchall()
        except sqlite3.OperationalError:
            rijen = [(*rij, None) for rij in con.execute(basis, (van, tot)).fetchall()]
    finally:
        con.close()
    uit = []
    for uuid, naam, t, lat, lon, kind, origineel in rijen:
        gps = lat is not None and lon is not None and lat > -180 and lon > -180
        uit.append({"uuid": uuid, "bestand": naam, "origineel": origineel,
                    "tijd": datetime.fromtimestamp(t + APPLE_EPOCH).strftime("%H:%M"),
                    "vastgelegd_utc": datetime.fromtimestamp(t + APPLE_EPOCH, timezone.utc).isoformat(),
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
        f["geexporteerd"] = False
        ext = os.path.splitext(f["bestand"] or "")[1] or ".jpg"
        f["export"] = f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}"
        uit = os.path.join(doel, f["export"])
        if os.path.exists(uit) and os.path.getsize(uit) > 0:
            f["geexporteerd"] = True
            klaar += 1
            continue
        bron = os.path.join(LIB, f["uuid"][0], f"{f['uuid']}{ext}")
        if os.path.exists(bron) and os.path.getsize(bron) > 0:
            shutil.copy2(bron, uit)
            f["geexporteerd"] = True
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
        if namen and max(os.path.getsize(os.path.join(tmp, n)) for n in namen) > 0:
            naam = sorted(namen, key=lambda n: os.path.getsize(os.path.join(tmp, n)), reverse=True)[0]
            ext = os.path.splitext(naam)[1] or ".jpg"
            f["export"] = f"{f['tijd'].replace(':', '')} {f['uuid'][:8]}{ext}"
            shutil.move(os.path.join(tmp, naam), os.path.join(doel, f["export"]))
            f["geexporteerd"] = True
            klaar += 1
        else:
            print("Photos-export mislukt voor", f["uuid"][:8], (r.stderr or "").strip()[:120], file=sys.stderr)
        shutil.rmtree(tmp, ignore_errors=True)
    return klaar


def exporteer_jpg_naar(fotos, doel):
    """TKN-foto's als JPG in de bestaande fotomap; lever nooit video of HEIC af.

    Een bestaande niet-lege doelnaam is al geleverd. Alle bewerkingen gebeuren in
    een eigen tijdelijke map, zodat een mislukte omzetting geen halve JPG achterlaat.
    """
    import shutil
    import subprocess
    import tempfile

    os.makedirs(doel, exist_ok=True)
    klaar = 0
    geziene_doelen = set()
    beeld_ext = {".heic", ".heif", ".jpg", ".jpeg", ".png"}
    for f in fotos:
        f["geexporteerd"] = False
        f.pop("export_fout", None)
        origineel = os.path.basename(str(f.get("origineel") or ""))
        stam = os.path.splitext(origineel)[0] or f"{str(f.get('tijd') or '').replace(':', '')} {str(f.get('uuid') or '')[:8]}"
        # Een Photos-naam mag nooit een pad of een gereserveerde doelnaam leveren.
        if stam in ("", ".", "..") or "/" in stam or "\\" in stam:
            f["export_fout"] = "bestandsnaam_ongeldig"
            continue
        f["export"] = stam + ".jpg"
        uit = os.path.join(doel, f["export"])
        if uit.casefold() in geziene_doelen:
            f["export_fout"] = "bestandsnaam_dubbel"
            continue
        geziene_doelen.add(uit.casefold())
        if os.path.lexists(uit):
            if not os.path.islink(uit) and os.path.isfile(uit) and os.path.getsize(uit) > 0:
                f["geexporteerd"] = True
                klaar += 1
            else:
                f["export_fout"] = "doelbestand_ongeldig"
            continue

        ext_echt = os.path.splitext(str(f.get("bestand") or ""))[1]
        ext = ext_echt.lower()
        uid = str(f.get("uuid") or "")
        # De echte extensie uit Photos: op een hoofdlettergevoelig bestandssysteem vindt '.heic' geen '.HEIC'.
        bron = os.path.join(LIB, uid[:1], uid + ext_echt) if uid and ext in beeld_ext else ""
        with tempfile.TemporaryDirectory(prefix="icloud-jpg-") as tmp:
            if not bron or not os.path.isfile(bron) or os.path.getsize(bron) == 0:
                if not uid or '"' in uid or "\\" in uid:
                    f["export_fout"] = "photos_bron_ongeldig"
                    continue
                script = (f'tell application "Photos" to export {{media item id "{uid}"}} '
                          f'to POSIX file "{tmp}" as alias with using originals')
                try:
                    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=300)
                except (OSError, subprocess.TimeoutExpired):
                    f["export_fout"] = "photos_export_mislukt"
                    continue
                if r.returncode != 0:
                    f["export_fout"] = "photos_export_mislukt"
                    continue
                kandidaten = [os.path.join(tmp, naam) for naam in os.listdir(tmp)
                              if os.path.splitext(naam)[1].lower() in beeld_ext
                              and os.path.isfile(os.path.join(tmp, naam))
                              and os.path.getsize(os.path.join(tmp, naam)) > 0]
                if not kandidaten:
                    f["export_fout"] = "photos_export_mislukt"
                    continue
                gewenste_stammen = {stam.casefold(), os.path.splitext(str(f.get("bestand") or ""))[0].casefold()}
                bron = sorted(kandidaten, key=lambda p: (
                    os.path.splitext(os.path.basename(p))[0].casefold() not in gewenste_stammen,
                    -os.path.getsize(p), os.path.basename(p)))[0]

            conversie = os.path.join(tmp, "conversie")
            os.mkdir(conversie)
            tijdelijk_jpg = os.path.join(conversie, "uitvoer.jpg")
            if os.path.splitext(bron)[1].lower() in (".jpg", ".jpeg"):
                shutil.copy2(bron, tijdelijk_jpg)
            else:
                try:
                    r = subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "90",
                                        bron, "--out", tijdelijk_jpg], capture_output=True, text=True, timeout=300)
                except (OSError, subprocess.TimeoutExpired):
                    f["export_fout"] = "omzetting_mislukt"
                    continue
                if r.returncode != 0:
                    f["export_fout"] = "omzetting_mislukt"
                    continue
            if not os.path.isfile(tijdelijk_jpg) or os.path.getsize(tijdelijk_jpg) == 0:
                f["export_fout"] = "omzetting_mislukt"
                continue
            if os.path.lexists(uit):
                if not os.path.islink(uit) and os.path.isfile(uit) and os.path.getsize(uit) > 0:
                    f["geexporteerd"] = True
                    klaar += 1
                else:
                    f["export_fout"] = "doelbestand_ongeldig"
                continue
            shutil.move(tijdelijk_jpg, uit)
            f["geexporteerd"] = True
            klaar += 1
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


def _tijd_met_zone(value):
    if not isinstance(value, str):
        raise ValueError("bezoekvenster_ontbreekt")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("bezoekvenster_ongeldig") from None
    if result.tzinfo is None:
        raise ValueError("bezoekvenster_tijdzone_ontbreekt")
    return result.astimezone(timezone.utc)


def taakvenster(d):
    """Alleen expliciete tijden, ook bij E4; zonder venster blijft de taak open."""
    start, einde = _tijd_met_zone(d.get("start") or d.get("van_tijd")), _tijd_met_zone(d.get("einde") or d.get("tot_tijd"))
    e4 = d.get("reden") == "E4, geen afspraak"
    if einde <= start or einde - start > timedelta(days=1, minutes=75 if e4 else 0):
        raise ValueError("bezoekvenster_ongeldig")
    eerste = start + timedelta(minutes=15) if e4 else start
    laatste = einde - timedelta(minutes=60) if e4 else start
    if (laatste < eerste or eerste.astimezone(ZoneInfo("Europe/Brussels")).date().isoformat() != d.get("datum")
            or laatste.astimezone(ZoneInfo("Europe/Brussels")).date().isoformat() != d.get("datum")):
        raise ValueError("bezoekvenster_andere_dag")
    return start, einde


def taakdoel(d):
    """Bind identiteit en schrijflocatie aan één H-Architects-bezoek."""
    if str(d.get("project_ref") or "").startswith("tkn:"):
        return _tkn_doel(d)
    dossier = str(d.get("dossier", ""))
    if not re.fullmatch(r"[0-9]{4}", dossier) or d.get("project_ref") != "h-architects:" + dossier:
        raise ValueError("projectidentiteit_ontbreekt")
    bid = d.get("bezoek_id")
    try:
        if not isinstance(bid, str) or str(uuid.UUID(bid)) != bid:
            raise ValueError
    except ValueError:
        raise ValueError("bronregistratie_ontbreekt") from None
    project, bezoek = d.get("projectmap"), d.get("bezoekmap")
    if not isinstance(project, str) or not isinstance(bezoek, str):
        raise ValueError("bezoekmap_ontbreekt")
    pp, bp = PurePosixPath(project), PurePosixPath(bezoek)
    if (not pp.is_absolute() or not bp.is_absolute() or ".." in pp.parts or ".." in bp.parts
            or pp.parts[1:3] != ("Work All", "01. H-A WORK")
            or not re.search(r"\b" + dossier + r"\b", pp.name.replace("_", " "))
            or bp == pp or pp not in bp.parents):
        raise ValueError("bezoekmap_buiten_project")
    root = Path(DROPBOX_LOKAAL).resolve()
    projectpad = root.joinpath(*pp.parts[1:]).resolve()
    doel = root.joinpath(*bp.parts[1:], "fotos").resolve()
    if root not in projectpad.parents or projectpad not in doel.parents:
        raise ValueError("bezoekmap_buiten_project")
    return str(doel)


def _tkn_doel(d):
    """Alleen de ene bestaande, eigen fotomap onder een TKN-project is een doel."""
    import unicodedata
    nummer = d.get("mapnummer")
    if not isinstance(nummer, str) or not re.fullmatch(r"[0-9]{4,6}", nummer) or d.get("project_ref") != "tkn:" + nummer:
        raise ValueError("projectidentiteit_ontbreekt")
    if not re.fullmatch(r"verslagopdracht:\d+", str(d.get("bezoek_ref") or "")):
        raise ValueError("bronregistratie_ontbreekt")
    project = d.get("projectmap")
    if not isinstance(project, str):
        raise ValueError("bezoekmap_ontbreekt")
    pp = PurePosixPath(project)
    delen = pp.parts
    if ("\x00" in project or pp.as_posix() != project or not pp.is_absolute() or ".." in delen or len(delen) != 6
            or delen[1:4] != ("Work", "TKN BURO WORK", "1 Projects")
            or not re.fullmatch(r"[0-9]{4}", delen[4])
            or not re.match(r"^" + re.escape(nummer) + r"(?:_| )", delen[5])):
        raise ValueError("bezoekmap_buiten_project")
    datum = d.get("datum")
    try:
        if not isinstance(datum, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", datum):
            raise ValueError
        datetime.fromisoformat(datum)
    except ValueError:
        raise ValueError("taakgegevens_ongeldig") from None
    root = Path(DROPBOX_LOKAAL).resolve()
    projectpad = root.joinpath(*delen[1:]).resolve()
    if root not in projectpad.parents:
        raise ValueError("bezoekmap_buiten_project")
    if not projectpad.is_dir():
        raise ValueError("fotomap_ontbreekt")

    def is_fotomap(naam):
        # Dezelfde herkenning als verslagsoorten.submap_sleutel('fotos'), zonder
        # import van runner-modules: de geïsoleerde Mac-starter draait met -I.
        plat = "".join(c for c in unicodedata.normalize("NFKD", naam) if not unicodedata.combining(c)).lower()
        return re.match(r"^1 ?foto", " ".join(re.findall(r"[a-z0-9]+", plat))) is not None

    fotomappen = [p for p in projectpad.iterdir() if p.is_dir() and is_fotomap(p.name)]
    if len(fotomappen) != 1:
        raise ValueError("fotomap_ontbreekt")
    verklaard = d.get("doelmap")
    if not isinstance(verklaard, str):
        raise ValueError("bezoekmap_ontbreekt")
    dp = PurePosixPath(verklaard)
    if "\x00" in verklaard or verklaard != project + "/" + fotomappen[0].name + "/" + datum + " iPhone" or \
            ".." in dp.parts or dp.parts != delen + (fotomappen[0].name, datum + " iPhone"):
        raise ValueError("bezoekmap_buiten_project")
    fotomap = fotomappen[0].resolve()
    doel = (fotomap / (datum + " iPhone")).resolve()
    if fotomap.parent != projectpad or fotomap not in doel.parents or projectpad not in doel.parents:
        raise ValueError("bezoekmap_buiten_project")
    return str(doel)


def selecteer(fotos, start, einde, c, straal):
    """Selectie op [start, einde) en GPS; onbekende tijd/GPS blijft onbeslist."""
    binnen, onbeslist = [], 0
    for f in fotos:
        try:
            tijd = _tijd_met_zone(f.get("vastgelegd_utc"))
        except ValueError:
            onbeslist += 1
            continue
        if not start <= tijd < einde:
            continue
        lat, lon = f.get("lat"), f.get("lon")
        if type(lat) not in (int, float) or type(lon) not in (int, float) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
            onbeslist += 1
            continue
        if afstand_m(lat, lon, c[0], c[1]) <= straal:
            binnen.append(f)
    return binnen, onbeslist


def selectie_stabiel(it, d, fotos, nu):
    """Bewaar alleen een hash en het begin van de huidige, ongewijzigde selectie op de Mac.

    Een nieuwe foto reset de klok, ook wanneer de zesuursgrens al is verstreken.
    Een eerste meting na die grens mag wel meteen sluiten.
    """
    sleutel = it.get("id")
    if type(sleutel) is not int or sleutel <= 0:
        raise ValueError("taakidentiteit_ongeldig")
    inhoud = json.dumps({"taak": d, "fotos": sorted((str(f.get("uuid")), str(f.get("vastgelegd_utc"))) for f in fotos)},
                        ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    selectiehash = hashlib.sha256(inhoud.encode("utf-8")).hexdigest()
    pad = Path(SELECTIE_STAAT) / f"{sleutel}.json"
    eerder_gemeten = pad.exists()
    try:
        oud = json.loads(pad.read_text(encoding="utf-8"))
        eerste = _tijd_met_zone(oud.get("eerste_meting"))
    except (OSError, ValueError, AttributeError, TypeError):
        oud, eerste = {}, None
    einde_bezoek = _tijd_met_zone(d.get("tot_tijd"))
    na_vangnet = nu >= einde_bezoek + timedelta(hours=ZONDER_TAKEN_UUR)
    if oud.get("selectiehash") == selectiehash and eerste and eerste <= nu:
        return nu - eerste >= timedelta(minutes=SELECTIE_RUST_MIN) or na_vangnet
    pad.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tijdelijk_pad = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=pad.parent, prefix=".selectie-",
                                         suffix=".json", delete=False) as tijdelijk:
            tijdelijk_pad = tijdelijk.name
            os.chmod(tijdelijk_pad, 0o600)
            json.dump({"selectiehash": selectiehash, "eerste_meting": nu.isoformat()}, tijdelijk)
        os.replace(tijdelijk_pad, pad)
    finally:
        if tijdelijk_pad and os.path.exists(tijdelijk_pad):
            os.unlink(tijdelijk_pad)
    return not eerder_gemeten and na_vangnet


class MeldingenVandaag:
    """Welke taak met welke reden vandaag al gemeld is (T-0120 FOTO-1), alleen op deze Mac. Een onleesbare staat geeft
    hoogstens een melding te veel, nooit een te weinig; een nieuwe dag begint leeg."""

    def __init__(self):
        self.dag = datetime.now(ZoneInfo("Europe/Brussels")).date().isoformat()
        try:
            oud = json.loads(Path(MELDING_STAAT).read_text(encoding="utf-8"))
            self.gemeld = set(oud.get("gemeld") or []) if oud.get("dag") == self.dag else set()
        except (OSError, ValueError, AttributeError, TypeError):
            self.gemeld = set()
        self.nieuw = False

    def eerste(self, kid, code):
        sleutel = f"{kid}:{code}"
        if sleutel in self.gemeld:
            return False
        self.gemeld.add(sleutel)
        self.nieuw = True
        return True

    def bewaar(self):
        if not self.nieuw:
            return
        pad = Path(MELDING_STAAT)
        try:
            pad.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            tijdelijk = pad.with_name(f".{pad.name}.{os.getpid()}")
            tijdelijk.write_text(json.dumps({"dag": self.dag, "gemeld": sorted(self.gemeld)}), encoding="utf-8")
            os.chmod(tijdelijk, 0o600)
            os.replace(tijdelijk, pad)
        except OSError as e:
            print("meldingstaat niet bewaard:", type(e).__name__, file=sys.stderr)


def taken():
    """Geen afvinkactie zonder volledige levering voor het bevestigde bezoek."""
    lijst = taken_lezen()
    if not lijst:
        return {"gedaan": 0, "open": 0}
    hartslag("actief", taak=f"{len(lijst)} foto-taak/taken van de voorbereider")
    regels, gedaan, open_, redenen = [], 0, 0, {}
    gemeld = MeldingenVandaag()

    def blokkeer(it, code):
        # T-0120 FOTO-1: alleen een fout van de wacht zelf (WACHTFOUTEN) is stap 'fout'. Een taak die op gegevens van de
        # voorbereider wacht, is een 'melding', hoogstens één keer per taak en reden per dag: tot 01-11 schreef elke ronde
        # (elke 30 minuten) een rode regel, en stond De Fotowacht elke dag rood zonder dat ze zelf faalde.
        nonlocal open_
        open_ += 1
        redenen[code] = redenen.get(code, 0) + 1
        detail = json.dumps({"regel": code, "klaarzet_id": it.get("id")})
        if code in WACHTFOUTEN:
            regels.append({"naam": NAAM, "onderwerp": "fotoaanvoer", "stap": "fout", "tekst": "fototaak blijft open", "detail": detail})
        elif gemeld.eerste(it.get("id"), code):
            regels.append({"naam": NAAM, "onderwerp": "fotoaanvoer", "stap": "melding",
                           "tekst": "fototaak wacht op gegevens van de voorbereider", "detail": detail})

    for it in lijst:
        try:
            d = it.get("inhoud")
            d = json.loads(d) if isinstance(d, str) else d
            if not isinstance(d, dict):
                raise ValueError("taakgegevens_ongeldig")
            tkn = str(d.get("project_ref") or "").startswith("tkn:")
            start, einde = taakvenster(d)
            doel = taakdoel(d)
            straal = d.get("straal_m", min(STRAAL_M, 300))
            if type(straal) is not int or not 0 < straal <= min(STRAAL_M, 300):
                raise ValueError("fotostraal_ongeldig")
            if not isinstance(d.get("adres"), str) or not d["adres"].strip():
                raise ValueError("werfadres_ontbreekt")
            if tkn:
                _tijd_met_zone(d.get("tot_tijd"))
        except ValueError as exc:
            codes = {"bezoekvenster_ontbreekt", "bezoekvenster_ongeldig", "bezoekvenster_tijdzone_ontbreekt", "bezoekvenster_andere_dag",
                     "projectidentiteit_ontbreekt", "bronregistratie_ontbreekt", "bezoekmap_ontbreekt", "bezoekmap_buiten_project",
                     "fotomap_ontbreekt", "fotostraal_ongeldig", "werfadres_ontbreekt"}
            blokkeer(it, str(exc) if str(exc) in codes else "taakgegevens_ongeldig")
            continue
        c = (d.get("lat"), d.get("lon")) if isinstance(d.get("lat"), (int, float)) and isinstance(d.get("lon"), (int, float)) else coord(d["adres"])
        if not c:
            blokkeer(it, "werfcoordinaten_ontbreken")
            continue
        dag = start.astimezone(ZoneInfo("Europe/Brussels")).date()
        laatste_dag = (einde - timedelta(microseconds=1)).astimezone(ZoneInfo("Europe/Brussels")).date()
        fotos = []
        while dag <= laatste_dag:
            fotos.extend(fotos_van(dag.isoformat()))
            dag += timedelta(days=1)
        if tkn:
            fotos = [f for f in fotos if not f.get("video") and not re.match(
                r"(?i)^(?:screenshot|screen shot|schermafbeelding)(?:[\s_.-]|$)",
                os.path.basename(str(f.get("origineel") or f.get("bestand") or "")))]
        binnen, onbeslist = selecteer(fotos, start, einde, c, straal)
        if not binnen:
            blokkeer(it, "fotoselectie_onbeslist" if onbeslist else "fotoselectie_leeg")
            continue
        n = exporteer_jpg_naar(binnen, doel) if tkn else exporteer_naar(binnen, doel)
        volledig = type(n) is int and n == len(binnen) and (tkn or not onbeslist)
        if type(n) is not int or not 0 <= n <= len(binnen):
            blokkeer(it, "exportresultaat_ongeldig")
            continue
        stabiel = selectie_stabiel(it, d, binnen, datetime.now(timezone.utc)) if tkn and volledig else True
        md = ["# Fotoaanvoer " + ("volledig" if volledig else "onvolledig"), "",
              f"Bezoek {d.get('bezoek_id') or d.get('bezoek_ref')}; {n} van {len(binnen)} geselecteerde foto's geleverd; {onbeslist} foto's niet toewijsbaar.",
              f"Venster: {d.get('start') or d.get('van_tijd')} tot {d.get('einde') or d.get('tot_tijd')}; vaste straal {straal} m. Geen automatische verruiming.",
              f"Reden venster: {d.get('reden') or ('TKN-afspraak van de Agendawacht' if tkn else 'H-A-afspraak van de Agendawacht')}.", "",
              "## Geleverde foto's en opnametijden"]
        md.extend(f"- {f['vastgelegd_utc']} | {f.get('export') or f.get('bestand')}" for f in binnen if f.get("geexporteerd"))
        if not tkn:
            manifest = os.path.join(doel, "00 fotos.md")
            if os.path.exists(manifest):
                stempel = datetime.now(ZoneInfo("Europe/Brussels")).strftime("%Y%m%dT%H%M%S%f")
                manifest = os.path.join(doel, f"00 fotos {stempel}.md")
            with open(manifest, "x", encoding="utf-8") as f:
                f.write("\n".join(md) + "\n")
        elif volledig and stabiel:
            manifest = os.path.join(doel, "00 fotos.md")
            if not os.path.exists(manifest):
                with open(manifest, "x", encoding="utf-8") as f:
                    f.write("\n".join(md) + "\n")
        regels.append({"naam": NAAM, "onderwerp": "fotoaanvoer", "stap": "schrijf",
                       "tekst": f"{n} van {len(binnen)} geselecteerde foto's geleverd; {onbeslist} onbeslist"})
        if not volledig:
            blokkeer(it, ("omzetting_mislukt" if tkn and any(f.get("export_fout") == "omzetting_mislukt" for f in binnen)
                          else "fotoselectie_onbeslist" if onbeslist and not tkn else "fotolevering_gedeeltelijk"))
            continue
        if tkn and not stabiel:
            blokkeer(it, "fotoselectie_wacht_op_stabiliteit")
            continue
        if not tkn:
            jpeg_kopieen(doel)
            # Afvinken pas als elke geleverde HEIC een JPG heeft: de voorbereider maakt een hersteltaak maar één keer aan
            # (overleg W4 P3, 30-10-2026, Codex X4), dus een mislukte omzetting moet de taak open houden.
            if any(not os.path.isfile(jpg) or os.path.getsize(jpg) == 0 for jpg in (
                    os.path.join(doel, os.path.splitext(f["export"])[0] + ".jpg") for f in binnen
                    if str(f.get("export") or "").lower().endswith(".heic"))):
                blokkeer(it, "omzetting_mislukt")
                continue
        taak_opgepakt(it["id"])
        gedaan += 1
    if regels:
        bord("/api/logboek", {"regels": regels})
    gemeld.bewaar()
    # 31-10-2026: alleen een fout van de wacht zelf (export of omzetting) zet hem op fout. Een taak zonder venster, zonder
    # foto's op die plek of die nog rust nodig heeft, wacht op gegevens van de voorbereider: de taak blijft open en staat
    # in het detail, maar de Fotowacht leverde wel (anders stond hij weken rood door oude werfverslagtaken).
    eigen = sorted(r for r in redenen if r in WACHTFOUTEN)
    taak = ("fotoaanvoer mislukt: " + ", ".join(eigen) if eigen
            else f"{open_} fototaak/taken wachten op gegevens van de voorbereider" if open_ else "fototaken volledig geleverd")
    hartslag("fout" if eigen else "klaar", taak=taak,
             detail=json.dumps({"gedaan": gedaan, "open": open_, "redenen": redenen}, sort_keys=True))
    return {"gedaan": gedaan, "open": open_, "redenen": redenen}


def _werk():
    if "--jpeg" in sys.argv:
        print("jpeg-kopieën:", jpeg_kopieen(sys.argv[sys.argv.index("--jpeg") + 1]))
        return
    if "--taken" in sys.argv:
        if not TOKEN:
            sys.exit("geen token")
        uit = taken()
        print("taken:", json.dumps(uit, sort_keys=True))
        # T-0120 FOTO-1: exit 1 alleen bij een eigen fout; een uitzondering geeft main() al 1.
        return 1 if any(r in WACHTFOUTEN for r in uit.get("redenen", {})) else 0
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


def main():
    """Meld een bron-/rechtenfout als fout; geen blijvend actieve hartslag.

    Er wordt bij een exception geen nieuwe export of afvinkactie gestart.
    Meld alleen foutklasse en vaste diagnose, geen foto's, adres of token.
    """
    try:
        uit = _werk()
        return uit if isinstance(uit, int) else 0
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:  # noqa: BLE001
        soort = type(exc).__name__
        geweigerd = isinstance(exc, PermissionError) or (
            isinstance(exc, sqlite3.Error) and str(exc).strip().lower() in ("authorization denied", "not authorized"))
        uitleg = "macOS weigert leestoegang tot de fotobibliotheek; controleer de rechten van de vaste runner" if geweigerd else "bronverwerking niet afgerond; taak blijft open"
        hartslag("fout", taak="fotoaanvoer geblokkeerd" if geweigerd else "fotoaanvoer mislukt", detail=soort + ": " + uitleg)
        print("iCloud-wacht: " + soort + "; " + uitleg, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
