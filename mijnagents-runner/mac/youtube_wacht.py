#!/usr/bin/env python3
"""De YouTube-wacht (Privé, alleen voor Mehdi) - draait op de laptop, naast De Websitewacht (browser_wacht.py). Mehdi,
31-10-2026: de kijkgeschiedenis van zijn YouTube-account: welke video, wanneer, hoe lang.

YouTube geeft de kijkgeschiedenis niet via een API (alleen via Google Takeout, met de hand). Wat Mehdi op de laptop kijkt,
staat wel in de geschiedenis van zijn browser: elke video is een adres youtube.com/watch?v=... met de titel van de video.
Deze wacht leest daaruit per dag (Brusselse tijd): het aantal verschillende video's, het aantal keer bekeken, de minuten
(alleen Chrome en Edge houden bij hoe lang een tabblad open stond; geschat, hoogstens 3 uur per keer) en de titels met de
meeste keren. Nooit een zoekopdracht, nooit een reactie, nooit iets anders dan de titel. Een privaat venster laat geen
geschiedenis na. Wat op de iPhone of de tv bekeken werd, ziet deze wacht niet.

Sinds 01-11-2026 (YT-1, T-0120 VOL-11, weg a): onder launchd mag Python de browsers niet lezen (vroeger: 'geen
browsergeschiedenis gevonden'). De geschiedenis leest alleen MacGesprekkenKopie (set browser, Full Disk Access): van een
YouTube-video alleen tijd, video-ID, titel en duur. Deze wacht leest zijn kopie (mac_gesprekken.browser_kopie). Nooit
Full Disk Access voor Python.app: dat gaf elk python-script volledige toegang.

Zet een item 'youtube:<gebruiker>:<dag>' klaar voor Mehdi met de tellingen van de laatste DAGEN dagen (per_dag); De
Dagbundelaar neemt ze op in het blok Eigen werk en gezondheid. Een dag zonder video is 0, alleen als de wacht keek.
Token: ~/.config/mijnagents/token. Gebruik: youtube_wacht.py [--dag JJJJ-MM-DD] [--dagen N] [--droog]
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "koppelingen"))
import mac_gesprekken as M  # noqa: E402

NAAM = "youtube-wacht"
GEBRUIKER = os.environ.get("YOUTUBE_GEBRUIKER", "Mehdi")
BORD = os.environ.get("MIJNAGENTS_URL", "https://mijnagents.globaal.be")
BRUSSEL = ZoneInfo("Europe/Brussels")
TOP = 10
DAGEN = 14
MAX_MIN = 180                  # een tabblad dat de hele nacht openstond, telt niet als 10 uur kijken
DAG = None
DROOG = "--droog" in sys.argv
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
    if a == "--dagen" and i + 1 < len(sys.argv):
        DAGEN = int(sys.argv[i + 1])
DAG = DAG or datetime.now(BRUSSEL).date().isoformat()


def token():
    try:
        return open(os.path.expanduser("~/.config/mijnagents/token")).read().strip()
    except OSError:
        return ""


def bord(pad, payload):
    req = urllib.request.Request(f"{BORD}{pad}", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Agents-Token": token()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def hartslag(status, taak="", detail="", nood=None):
    if DROOG:
        print("hartslag", status, taak, detail, nood or "")
        return
    try:
        bord("/agent-status", {"naam": NAAM, "status": status, "taak": taak, "detail": detail, "nood": nood or []})
    except Exception as e:  # noqa: BLE001
        print("hartslag mislukt:", e, file=sys.stderr)


def niet_gelezen(onleesbaar, deels=False):
    """Waarom geen enkele browser gelezen is (YT-2, 01-11-2026: onder launchd weigerde macOS Chrome en Firefox, en de
    melding zei "niet gevonden"). PermissionError (of de uitkomst "geweigerd" van de helper van YT-1) is een weigering van
    macOS; een andere fout een onleesbaar bestand."""
    geweigerd = [b for b, f in onleesbaar.items() if f in ("PermissionError", "geweigerd")]
    anders = [b for b in onleesbaar if b not in geweigerd]
    delen = (["geweigerd: " + ", ".join(geweigerd)] if geweigerd else []) + (
        ["onleesbaar: " + ", ".join(anders)] if anders else [])
    if not delen:
        return "Geen browsergeschiedenis gevonden op deze Mac"
    # deels: andere browsers zijn wel gelezen, maar de telling is onvolledig en wordt niet klaargezet (Codex 01-11)
    return ("Browsergeschiedenis niet volledig gelezen op deze Mac (" if deels
            else "Browsergeschiedenis niet te lezen op deze Mac (") + "; ".join(delen) + ")"


def fout_in_werkverslag(tekst):
    """Een mislukte ronde staat ook in het werkverslag: anders zegt de wachtenpagina "geen ronde" (YT-2)."""
    if DROOG:
        print("werkverslag fout", tekst)
        return
    try:
        bord("/api/logboek", {"regels": [{"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "fout", "tekst": tekst}]})
    except Exception as e:  # noqa: BLE001
        print("werkverslag mislukt:", e, file=sys.stderr)


def video(adres):
    """De video-ID van een YouTube-adres (watch?v=, youtu.be/, shorts/, live/), anders None. Zoeken, kanalen, de
    startpagina en reacties tellen niet. De helper rekent precies zo (video() in mac/kopie/macgesprekken_kopie.c)."""
    try:
        u = urllib.parse.urlsplit(adres or "")
    except ValueError:
        return None
    h = (u.hostname or "").lower()
    if h.startswith("www.") or h.startswith("m."):
        h = h.split(".", 1)[1]
    if h == "youtu.be":
        vid = u.path.strip("/").split("/")[0]
    elif h in ("youtube.com", "music.youtube.com"):
        if u.path == "/watch":
            vid = (urllib.parse.parse_qs(u.query).get("v") or [""])[0]
        else:
            m = re.match(r"^/(?:shorts|live)/([^/?#]+)", u.path)
            vid = m.group(1) if m else ""
    else:
        return None
    return vid if re.fullmatch(r"[A-Za-z0-9_-]{6,20}", vid or "") else None


def titel_schoon(t):
    t = re.sub(r"^\(\d+\)\s*", "", str(t or "")).strip()          # "(3) Titel - YouTube": meldingen ervoor
    t = re.sub(r"\s*-\s*YouTube( Music)?$", "", t).strip()
    return re.sub(r"\s+", " ", t)[:120] or "zonder titel"


def tel(bekeken, dagen):
    """bekeken: [(browser, epoch, video, titel, seconden)] -> {dag: {videos, keer, minuten, top}} voor elke dag, ook 0.
    minuten None als geen enkele browser die dag bijhield hoe lang (Firefox, Safari): onbekend, nooit nul."""
    per = {d: {"keer": 0, "videos": set(), "titels": Counter(), "sec": 0.0, "met_duur": False} for d in dagen}
    for _browser, t, vid, titel, sec in bekeken:
        d = datetime.fromtimestamp(t, BRUSSEL).date().isoformat()
        if d not in per:
            continue
        x = per[d]
        x["keer"] += 1
        x["videos"].add(vid)
        x["titels"][titel] += 1
        if sec is not None:
            x["met_duur"] = True
            x["sec"] += min(max(float(sec), 0.0), MAX_MIN * 60)
    return {d: {"videos": len(x["videos"]), "keer": x["keer"],
                "minuten": round(x["sec"] / 60) if x["met_duur"] or not x["keer"] else None,
                "top": [[t, n] for t, n in x["titels"].most_common(TOP)]} for d, x in per.items()}


def main(vragen=None):
    eind = datetime.fromisoformat(DAG).date()
    dagen = [(eind - timedelta(days=i)).isoformat() for i in range(DAGEN)]
    sinds = datetime.combine(eind - timedelta(days=DAGEN), datetime.min.time(), BRUSSEL).timestamp()
    hartslag("actief", taak=f"YouTube in de browsergeschiedenis van {DAGEN} dagen lezen")
    try:
        rijen, gelezen, onleesbaar = M.browser_kopie(sinds, vragen)
    except M.MacFout as e:
        fout_in_werkverslag(f"geen kopie van de browsergeschiedenis: {e.nood}")
        hartslag("fout", taak="geen kopie van de browsergeschiedenis", nood=[{"tekst": e.nood, "wie": e.wie}])
        print(f"ronde mislukt: {e}", file=sys.stderr)
        return 1
    bekeken = [(browser, t, vid, titel_schoon(titel), sec) for browser, t, _site, vid, titel, sec in rijen if vid]
    if not gelezen:
        tekst = niet_gelezen(onleesbaar)
        fout_in_werkverslag(tekst)
        hartslag("fout", taak="browsergeschiedenis niet gelezen", detail=tekst,
                 nood=[{"tekst": tekst, "wie": "claude-code"}])
        print(tekst, file=sys.stderr)
        return 1
    if onleesbaar:
        # Codex 01-11 (onbekend is nooit 0): een onleesbare browser maakt de telling onvolledig: niets klaarzetten
        tekst = niet_gelezen(onleesbaar, deels=True)
        fout_in_werkverslag(tekst)
        hartslag("fout", taak="browsergeschiedenis niet volledig gelezen", detail=tekst,
                 nood=M.browser_nood(onleesbaar))
        print(tekst, file=sys.stderr)
        return 1
    per_dag = tel(bekeken, dagen)
    inhoud = {"stand": DAG, "gemaakt": datetime.now(BRUSSEL).isoformat(timespec="minutes"), "gebruiker": GEBRUIKER,
              "browsers": dict(gelezen), "onleesbaar": onleesbaar, "per_dag": per_dag,
              "let_op": "alleen wat in een browser op deze laptop bekeken werd; niet de iPhone of de tv"}
    v = per_dag[DAG]
    titel = f"YouTube {DAG}: {v['videos']} video's" + (f", {v['minuten']} min" if v["minuten"] is not None else "")
    if DROOG:
        print(json.dumps(inhoud, ensure_ascii=False, indent=1))
        return 0
    uit = bord("/api/klaarzet", {"items": [{"van": NAAM, "voor": "mehdi", "soort": "youtube", "sleutel": DAG,
                                            "titel": titel, "uniek": f"youtube:{GEBRUIKER}:{DAG}", "inhoud": inhoud}]})
    bord("/api/logboek", {"regels": [
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "bron",
         "tekst": "gelezen: " + ", ".join(f"{b} ({n})" for b, n in gelezen.items())
                  + ("; onleesbaar: " + ", ".join(onleesbaar) if onleesbaar else "")},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf",
         "tekst": f"{titel}; {DAGEN} dagen klaargezet ({uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt)"}]})
    hartslag("klaar", taak=f"YouTube {DAG} klaargezet",
             detail=f"privé; {v['videos']} video's vandaag; browsers: {', '.join(gelezen)}")
    print(titel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
