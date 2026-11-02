#!/usr/bin/env python3
"""De Browserwacht (Privé, alleen voor Mehdi) - draait op de Mac, niet op de VM: alleen daar staat de geschiedenis van
de browsers. Mehdi, 31-10-2026: "alle websites dat ik bekeken heb" in het Dagboek.

Leest per dag (Brusselse tijd) de geschiedenis van Chrome en Edge (alle profielen), Firefox (alle profielen) en
Safari: het aantal bezoeken, het aantal verschillende sites en de sites met de meeste bezoeken. Alleen de naam van de
site (bijvoorbeeld monday.com), nooit het volledige adres, nooit een zoekopdracht, nooit de paginatitel. Een privaat
venster laat geen geschiedenis na en telt dus nooit mee.

Sinds 01-11-2026 (WEB-1, T-0120 VOL-11): onder launchd mag Python de browsers niet lezen. De geschiedenis zelf leest
alleen MacGesprekkenKopie (set browser, Full Disk Access); hij geeft alleen tijd en sitenaam door (site() hieronder is
dezelfde regel), en deze wacht leest zijn kopie (koppelingen/mac_gesprekken.browser_kopie). Nooit Full Disk Access voor
Python zelf: dat gaf elk python-script volledige toegang.

Zet een item 'websites:<dag>' klaar voor Mehdi met de tellingen van de laatste DAGEN dagen; De Dagbundelaar neemt ze
op in het dagbestand. Safari telt alleen wat op deze Mac bekeken werd, niet wat iCloud van de gsm meebrengt (WEB-3,
01-11-2026: de filter op history_visits.origin staat in de Safari-vraag van de helper). Een browser die niet te lezen
is, staat bij 'onleesbaar'.
Token: ~/.config/mijnagents/token. Gebruik: browser_wacht.py [--dag JJJJ-MM-DD] [--dagen N] [--droog]
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "koppelingen"))
import mac_gesprekken as M  # noqa: E402

NAAM = "browser-wacht"
BORD = os.environ.get("MIJNAGENTS_URL", "https://mijnagents.globaal.be")
BRUSSEL = ZoneInfo("Europe/Brussels")
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
    """Waarom geen enkele browser gelezen is, zoals in youtube_wacht.py (YT-2): PermissionError (of de uitkomst
    "geweigerd" van de helper van YT-1) is een weigering van macOS; een andere fout een onleesbaar bestand."""
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
    """Een mislukte ronde staat ook in het werkverslag: anders zegt de wachtenpagina "geen ronde"."""
    if DROOG:
        print("werkverslag fout", tekst)
        return
    try:
        bord("/api/logboek", {"regels": [{"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "fout", "tekst": tekst}]})
    except Exception as e:  # noqa: BLE001
        print("werkverslag mislukt:", e, file=sys.stderr)


def site(adres):
    """'https://www.monday.com/boards/1?x=2' -> 'monday.com'; geen web-adres (file:, chrome:, about:) -> None. De helper
    rekent precies zo (site() in mac/kopie/macgesprekken_kopie.c; test_vol11_site_en_video_zoals_de_wachten)."""
    try:
        u = urllib.parse.urlsplit(adres or "")
    except ValueError:
        return None
    if u.scheme not in ("http", "https") or not u.hostname:
        return None
    h = u.hostname.lower()
    return h[4:] if h.startswith("www.") else h


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


def main(vragen=None):
    eind = datetime.fromisoformat(DAG).date()
    dagen = [(eind - timedelta(days=i)).isoformat() for i in range(DAGEN)]
    sinds = datetime.combine(eind - timedelta(days=DAGEN), datetime.min.time(), BRUSSEL).timestamp()
    hartslag("actief", taak=f"geschiedenis van {DAGEN} dagen lezen")
    try:
        rijen, gelezen, onleesbaar = M.browser_kopie(sinds, vragen)
    except M.MacFout as e:
        fout_in_werkverslag(f"geen kopie van de browsergeschiedenis: {e.nood}")
        hartslag("fout", taak="geen kopie van de browsergeschiedenis", nood=[{"tekst": e.nood, "wie": e.wie}])
        print(f"ronde mislukt: {e}", file=sys.stderr)
        return 1
    bezoeken = [(browser, t, s) for browser, t, s, *_ in rijen]
    if not gelezen or onleesbaar:
        # Codex 01-11 (onbekend is nooit 0) en WEB-2: zonder alle browsers geen telling klaarzetten; de vorige blijft
        # staan. YT-2: de reden noemt geweigerd of onleesbaar, en de mislukte ronde staat in het werkverslag. Precies
        # zoals youtube_wacht.py (nazorg-mac, test_computer_wachten.py C05).
        tekst = niet_gelezen(onleesbaar, deels=bool(gelezen))
        nood = ([{"tekst": tekst, "wie": "claude-code"}] + [n for n in M.browser_nood(onleesbaar) if n["wie"] == "mehdi"]
                if not gelezen else M.browser_nood(onleesbaar))
        fout_in_werkverslag(tekst)
        hartslag("fout", taak="browsergeschiedenis niet " + ("volledig " if gelezen else "") + "gelezen", detail=tekst,
                 nood=nood)
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
             detail=f"privé; {v['bezoeken']} bezoeken vandaag; browsers: {', '.join(gelezen)}")
    print(titel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
