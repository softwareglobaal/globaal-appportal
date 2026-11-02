#!/usr/bin/env python3
"""De Browserwacht (Privé, alleen voor Mehdi) - draait op de Mac, niet op de VM: alleen daar staat de geschiedenis van
de browsers. Mehdi, 31-10-2026: "alle websites dat ik bekeken heb" in het Dagboek.

Mehdi, 02-11-2026 (beslissing): alleen Chrome, en alleen het profiel dat is aangemeld met zijn Google-account voor de
werkagenda; geen Firefox, geen Safari, geen andere Chrome-profielen. Het account staat niet in de repo maar in
~/.config/mijnagents/browser_account (een regel, het e-mailadres); de wacht zoekt het profiel op in Chrome's Local State.

Leest per dag (Brusselse tijd) uit een kopie van de geschiedenis van dat ene Chrome-profiel: het aantal bezoeken, het
aantal verschillende sites en de sites met de meeste bezoeken. Alleen de naam van de site (bijvoorbeeld monday.com),
nooit het volledige adres, nooit een zoekopdracht, nooit de paginatitel. Een privaat venster laat geen geschiedenis na en
telt dus nooit mee.

Zet een item 'websites:<dag>' klaar voor Mehdi met de tellingen van de laatste DAGEN dagen; De Dagbundelaar neemt ze
op in het dagbestand. Is het profiel niet te lezen, dan staat het bij 'onleesbaar' en zet de wacht niets klaar: onbekend
is geen 0 (T-0077, 02-11-2026). macOS 27 beschermt de map van Chrome; onder launchd heeft alleen een programma met
Full Disk Access toegang.
Token: ~/.config/mijnagents/token. Gebruik: browser_wacht.py [--dag JJJJ-MM-DD] [--dagen N] [--droog | --proef]
--proef (de uitrol, via de starter) zegt alleen of het profiel leesbaar is: nooit tellingen of sitenamen.
"""
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
ACCOUNT_BESTAND = os.path.expanduser("~/.config/mijnagents/browser_account")
CHROME = "Library/Application Support/Google/Chrome"
TOP = 10
DAGEN = 14
DAG = None
DROOG = "--droog" in sys.argv
PROEF = "--proef" in sys.argv
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
    if a == "--dagen" and i + 1 < len(sys.argv):
        DAGEN = int(sys.argv[i + 1])
DAG = DAG or datetime.now(BRUSSEL).date().isoformat()

CHROME_EPOCH = 11644473600      # Chrome: microseconden sinds 1601-01-01
CHROME_QUERY = f"SELECT v.visit_time / 1000000.0 - {CHROME_EPOCH}, u.url FROM visits v JOIN urls u ON u.id = v.url"


def account():
    """Het Google-account van het ene Chrome-profiel dat telt, uit ~/.config/mijnagents/browser_account; leeg = geen."""
    try:
        return open(ACCOUNT_BESTAND).read().strip().lower()
    except OSError:
        return ""


def profiel_van(local_state, acc):
    """De profielmap (Default, Profile 1 ...) die in Chrome's Local State is aangemeld met acc; None als die er niet is.
    local_state: de geladen JSON. Alleen 'user_name' telt (het aangemelde account), nooit de profielnaam."""
    cache = (local_state.get("profile") or {}).get("info_cache") or {}
    for d, p in cache.items():
        if isinstance(p, dict) and str(p.get("user_name") or "").strip().lower() == acc:
            return d
    return None


def bronnen():
    """[(browser, pad naar History)] voor precies het ene profiel; [] met een reden als dat niet kan."""
    acc = account()
    if not acc:
        return [], "geen account in " + ACCOUNT_BESTAND
    try:
        with open(os.path.join(THUIS, CHROME, "Local State")) as f:
            local_state = json.load(f)
    except (OSError, ValueError) as e:
        return [], f"Local State van Chrome niet te lezen ({type(e).__name__})"
    d = profiel_van(local_state, acc)
    if d is None:
        return [], "geen Chrome-profiel aangemeld met het account"
    return [("Chrome", os.path.join(THUIS, CHROME, d, "History"))], ""


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
    paden, reden = bronnen()
    for browser, pad in paden:
        try:
            rijen = lees_bestand(pad, CHROME_QUERY, sinds)
        except (OSError, sqlite3.Error) as e:
            onleesbaar[browser] = type(e).__name__
            continue
        gelezen[browser] += 1
        bezoeken += [(browser, t, s) for t, s in rijen]
    if PROEF:
        print(json.dumps({"proef": "ok" if gelezen else "mislukt", "browsers": dict(gelezen), "onleesbaar": onleesbaar,
                          "reden": "" if gelezen else (reden or "geen toegang (Full Disk Access)")}))
        return
    per_dag = tel(bezoeken, dagen)
    nood = []
    if not gelezen:
        # Overleg 02-11-2026 K2: geen verzoek om Python Full Disk Access te geven; de toestemming hoort bij een eigen
        # vast programma (de starter van de Browserwacht), niet bij Python.
        nood.append({"tekst": "Chrome-profiel niet gelezen: " + (reden or "geen toegang (Full Disk Access)"),
                     "wie": "claude-code"})
    inhoud = {"stand": DAG, "gemaakt": datetime.now(BRUSSEL).isoformat(timespec="minutes"),
              "browsers": dict(gelezen), "onleesbaar": onleesbaar, "per_dag": per_dag}
    if not gelezen:
        inhoud["reden"] = reden or "geen toegang (Full Disk Access)"   # ook in --droog: de proef van de uitrol leest dit
    v = per_dag[DAG]
    titel = f"Websites {DAG}: {v['bezoeken']} bezoeken op {v['sites']} sites"
    if DROOG:
        print(json.dumps(inhoud, ensure_ascii=False, indent=1))
        return
    if not gelezen:
        # 02-11-2026 (T-0077): geen enkele browser gelezen (launchd zonder Full Disk Access) is onbekend, geen 0.
        # Dan geen klaarzet: het Dagboek houdt de dag op "onbekend" in plaats van "0 bezoeken op 0 sites".
        try:
            bord("/api/logboek", {"regels": [
                {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "bron",
                 "tekst": "gelezen: niets; niets klaargezet"
                          + ("; onleesbaar: " + ", ".join(onleesbaar) if onleesbaar else "")}]})
        except Exception as e:  # noqa: BLE001  Codex 02-11: een mislukt logboek houdt de foutstatus niet tegen
            print("logboek mislukt:", e, file=sys.stderr)
        hartslag("fout", taak="geen browser gelezen", detail="niets klaargezet; geen Full Disk Access?", nood=nood)
        print(f"Websites {DAG}: geen browser gelezen, niets klaargezet")
        return
    uit = bord("/api/klaarzet", {"items": [{"van": NAAM, "voor": "mehdi", "soort": "websites", "sleutel": DAG,
                                            "titel": titel, "uniek": f"websites:{DAG}", "inhoud": inhoud}]})
    bord("/api/logboek", {"regels": [
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "bron",
         "tekst": "gelezen: " + (", ".join(f"{b} ({n})" for b, n in gelezen.items()) or "niets")
                  + ("; onleesbaar: " + ", ".join(onleesbaar) if onleesbaar else "")},
        {"naam": NAAM, "onderwerp": f"dag {DAG}", "stap": "schrijf",
         "tekst": f"{titel}; {DAGEN} dagen klaargezet ({uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt)"}]})
    hartslag("klaar" if gelezen else "fout", taak=f"websites {DAG} klaargezet",
             detail=f"privé; {v['bezoeken']} bezoeken vandaag; browsers: {', '.join(gelezen) or 'geen'}", nood=nood)
    print(titel)


if __name__ == "__main__":
    main()
