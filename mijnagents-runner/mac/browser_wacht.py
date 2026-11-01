#!/usr/bin/env python3
"""De Browserwacht (Privé, alleen voor Mehdi) - draait op de Mac, niet op de VM: alleen daar staat de geschiedenis van
de browsers. Mehdi, 31-10-2026: "alle websites dat ik bekeken heb" in het Dagboek.

Leest per dag (Brusselse tijd) uit een kopie van de geschiedenis van Chrome (alle profielen), Firefox (alle profielen)
en Safari: het aantal bezoeken, het aantal verschillende sites en de sites met de meeste bezoeken. Alleen de naam van
de site (bijvoorbeeld monday.com), nooit het volledige adres, nooit een zoekopdracht, nooit de paginatitel. Een privaat
venster laat geen geschiedenis na en telt dus nooit mee.

Zet een item 'websites:<dag>' klaar voor Mehdi met de tellingen van de laatste DAGEN dagen; De Dagbundelaar neemt ze
op in het dagbestand. Een browser die niet te lezen is (Safari zonder Full Disk Access), staat bij 'onleesbaar'.
Token: ~/.config/mijnagents/token. Gebruik: browser_wacht.py [--dag JJJJ-MM-DD] [--dagen N] [--droog]
"""
import glob
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

NAAM = "browser-wacht"
BORD = os.environ.get("MIJNAGENTS_URL", "https://mijnagents.globaal.be")
BRUSSEL = ZoneInfo("Europe/Brussels")
THUIS = os.path.expanduser(os.environ.get("BROWSER_THUIS", "~"))
TOP = 10
DAGEN = 14
DAG = None
DROOG = "--droog" in sys.argv
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
    if a == "--dagen" and i + 1 < len(sys.argv):
        DAGEN = int(sys.argv[i + 1])
DAG = DAG or datetime.now(BRUSSEL).date().isoformat()

# (browser, glob van de databank, query die (epoch-seconden, adres) geeft)
CHROME_EPOCH = 11644473600      # Chrome: microseconden sinds 1601-01-01
SAFARI_EPOCH = 978307200        # Safari: seconden sinds 2001-01-01
BRONNEN = (
    ("Chrome", "Library/Application Support/Google/Chrome/*/History",
     f"SELECT v.visit_time / 1000000.0 - {CHROME_EPOCH}, u.url FROM visits v JOIN urls u ON u.id = v.url"),
    ("Edge", "Library/Application Support/Microsoft Edge/*/History",
     f"SELECT v.visit_time / 1000000.0 - {CHROME_EPOCH}, u.url FROM visits v JOIN urls u ON u.id = v.url"),
    ("Firefox", "Library/Application Support/Firefox/Profiles/*/places.sqlite",
     "SELECT v.visit_date / 1000000.0, p.url FROM moz_historyvisits v JOIN moz_places p ON p.id = v.place_id"),
    ("Safari", "Library/Safari/History.db",
     f"SELECT v.visit_time + {SAFARI_EPOCH}, i.url FROM history_visits v JOIN history_items i ON i.id = v.history_item"),
)


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


def niet_gelezen(onleesbaar):
    """Waarom geen enkele browser gelezen is, zoals in youtube_wacht.py (YT-2): PermissionError is een weigering van
    macOS; een andere fout een onleesbaar bestand."""
    geweigerd = [b for b, f in onleesbaar.items() if f == "PermissionError"]
    anders = [b for b in onleesbaar if b not in geweigerd]
    delen = (["geweigerd: " + ", ".join(geweigerd)] if geweigerd else []) + (
        ["onleesbaar: " + ", ".join(anders)] if anders else [])
    if not delen:
        return "Geen browsergeschiedenis gevonden op deze Mac"
    return "Browsergeschiedenis niet te lezen op deze Mac (" + "; ".join(delen) + ")"


def fout_in_werkverslag(tekst):
    """Een mislukte ronde staat ook in het werkverslag: anders zegt de wachtenpagina "geen ronde"."""
    if DROOG:
        print("werkverslag fout", tekst)
        return
    try:
        bord("/api/logboek", {"regels": [{"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "fout", "tekst": tekst}]})
    except Exception as e:  # noqa: BLE001
        print("werkverslag mislukt:", e, file=sys.stderr)


def site(adres):
    """'https://www.monday.com/boards/1?x=2' -> 'monday.com'; geen web-adres (file:, chrome:, about:) -> None."""
    try:
        u = urllib.parse.urlsplit(adres or "")
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not u.hostname:
        return None
    h = u.hostname.lower()
    return h[4:] if h.startswith("www.") else h


def lees_bestand(pad, query, sinds):
    """(epoch, site) uit een kopie van de databank (de browser houdt hem open en vergrendeld)."""
    tmp = tempfile.mkdtemp(prefix="browser-")
    try:
        doel = os.path.join(tmp, "h.sqlite")
        shutil.copy2(pad, doel)
        for ext in ("-wal", "-shm"):
            if os.path.exists(pad + ext):
                shutil.copy2(pad + ext, doel + ext)
        c = sqlite3.connect(f"file:{doel}?mode=ro", uri=True)
        try:
            return [(t, site(a)) for t, a in c.execute(query) if t and t >= sinds]
        finally:
            c.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def tel(bezoeken, dagen):
    """bezoeken: [(browser, epoch, site)] -> {dag: {bezoeken, sites, per_browser, top}} voor elke dag in dagen, ook 0."""
    per = {d: {"n": 0, "sites": Counter(), "browsers": Counter()} for d in dagen}
    for browser, t, s in bezoeken:
        if not s:
            continue
        d = datetime.fromtimestamp(t, BRUSSEL).date().isoformat()
        if d in per:
            per[d]["n"] += 1
            per[d]["sites"][s] += 1
            per[d]["browsers"][browser] += 1
    return {d: {"bezoeken": x["n"], "sites": len(x["sites"]), "per_browser": dict(x["browsers"]),
                "top": [[s, n] for s, n in x["sites"].most_common(TOP)]} for d, x in per.items()}


def main():
    eind = datetime.fromisoformat(DAG).date()
    dagen = [(eind - timedelta(days=i)).isoformat() for i in range(DAGEN)]
    sinds = datetime.combine(eind - timedelta(days=DAGEN), datetime.min.time(), BRUSSEL).timestamp()
    hartslag("actief", taak=f"geschiedenis van {DAGEN} dagen lezen")
    bezoeken, gelezen, onleesbaar = [], defaultdict(int), {}
    for browser, patroon, query in BRONNEN:
        for pad in glob.glob(os.path.join(THUIS, patroon)):
            try:
                rijen = lees_bestand(pad, query, sinds)
            except (OSError, sqlite3.Error) as e:
                onleesbaar[browser] = type(e).__name__
                continue
            gelezen[browser] += 1
            bezoeken += [(browser, t, s) for t, s in rijen]
    nood = []
    if "Safari" in onleesbaar:
        nood.append({"tekst": "Safari is niet te lezen: geef Python Full Disk Access (System Settings, Privacy & Security)",
                     "wie": "mehdi"})
    if not gelezen:
        # WEB-2 (01-11-2026): niets gelezen is onbekend, nooit 0 bezoeken. Geen item klaarzetten: De Dagbundelaar zou de
        # nullen overnemen (dagbundelaar.py, per_dag_uit) en het Dagboek "0 bezoeken" tonen.
        tekst = niet_gelezen(onleesbaar)
        fout_in_werkverslag(tekst)
        hartslag("fout", taak="browsergeschiedenis niet gelezen", detail=tekst,
                 nood=nood + [{"tekst": tekst, "wie": "claude-code"}])
        print(tekst, file=sys.stderr)
        return 1
    per_dag = tel(bezoeken, dagen)
    inhoud = {"stand": DAG, "gemaakt": datetime.now(BRUSSEL).isoformat(timespec="minutes"),
              "browsers": dict(gelezen), "onleesbaar": onleesbaar, "per_dag": per_dag}
    v = per_dag[DAG]
    titel = f"Websites {DAG}: {v['bezoeken']} bezoeken op {v['sites']} sites"
    if DROOG:
        print(json.dumps(inhoud, ensure_ascii=False, indent=1))
        return 0
    uit = bord("/api/klaarzet", {"items": [{"van": NAAM, "voor": "mehdi", "soort": "websites", "sleutel": DAG,
                                            "titel": titel, "uniek": f"websites:{DAG}", "inhoud": inhoud}]})
    bord("/api/logboek", {"regels": [
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "bron",
         "tekst": "gelezen: " + (", ".join(f"{b} ({n})" for b, n in gelezen.items()) or "niets")
                  + ("; onleesbaar: " + ", ".join(onleesbaar) if onleesbaar else "")},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf",
         "tekst": f"{titel}; {DAGEN} dagen klaargezet ({uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt)"}]})
    hartslag("klaar", taak=f"websites {DAG} klaargezet",
             detail=f"privé; {v['bezoeken']} bezoeken vandaag; browsers: {', '.join(gelezen)}", nood=nood)
    print(titel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
