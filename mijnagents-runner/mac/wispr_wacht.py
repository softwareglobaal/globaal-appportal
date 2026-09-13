#!/usr/bin/env python3
"""De Wispr-wacht (Organisatie) — draait op de computer van de gebruiker, niet op de VM: alleen daar
staat de lokale databank van de Wispr Flow-app. Elke avond leest hij de TELLINGEN van de dag
(dictaten, woorden, minuten, per app) en zet ze op het bord Mehdi Agents. Nooit de tekst van
een dictaat: alleen aantallen. Regel van Mehdi, 13-09-2026: hij wil zien of een betaald account
gebruikt wordt; niets meer.

Werkt op macOS en Windows (dezelfde app, dezelfde databank):
  macOS:   ~/Library/Application Support/Wispr Flow/flow.sqlite
  Windows: %APPDATA%\\Wispr Flow\\flow.sqlite
Token: ~/.config/mijnagents/token (AGENTS_TOKEN van het bord). Gebruiker: WISPR_GEBRUIKER of de
loginnaam. Gebruik: wispr_wacht.py [--dag JJJJ-MM-DD] [--dagen N]  (standaard: gisteren tot vandaag, 14 dagen terug in het rapport)
"""
import getpass
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

NAAM = "wispr-wacht"
BORD = os.environ.get("MIJNAGENTS_URL", "https://mijnagents.globaal.be")
GEBRUIKER = os.environ.get("WISPR_GEBRUIKER") or getpass.getuser()
if sys.platform == "win32":
    DB = os.path.join(os.environ.get("APPDATA", ""), "Wispr Flow", "flow.sqlite")
    RAPPORT = os.path.expanduser(os.environ.get("WISPR_RAPPORT", "~/Dropbox/Data uit Mehdi/Wispr-wacht"))
else:
    DB = os.path.expanduser("~/Library/Application Support/Wispr Flow/flow.sqlite")
    RAPPORT = os.path.expanduser(os.environ.get("WISPR_RAPPORT", "~/TKN-buro Dropbox/Data uit Mehdi/Wispr-wacht"))
APPNAMEN = {"com.openai.chat": "ChatGPT", "com.anthropic.claudefordesktop": "Claude", "com.google.Chrome": "Chrome", "ru.keepcoder.Telegram": "Telegram",
            "net.whatsapp.WhatsApp": "WhatsApp", "com.openai.codex": "Codex", "com.microsoft.Word": "Word", "com.apple.finder": "Finder",
            "com.apple.mail": "Mail", "com.microsoft.Outlook": "Outlook", "com.tinyspeck.slackmacgap": "Slack", "us.zoom.xos": "Zoom",
            "com.apple.Safari": "Safari", "com.microsoft.VSCode": "VS Code", "com.apple.Notes": "Notes", "com.apple.MobileSMS": "Berichten"}
DAGEN = 14
DAG = None
for i, a in enumerate(sys.argv):
    if a == "--dag" and i + 1 < len(sys.argv):
        DAG = sys.argv[i + 1]
    if a == "--dagen" and i + 1 < len(sys.argv):
        DAGEN = int(sys.argv[i + 1])
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


def hartslag(status, taak="", detail="", nood=None):
    try:
        bord("/agent-status", {"naam": NAAM, "status": status, "taak": taak, "detail": detail, "nood": nood or []})
    except Exception as e:  # noqa: BLE001
        print("hartslag mislukt:", e, file=sys.stderr)


def lees(dagen):
    """Tellingen per dag en per app uit een kopie van de databank (de app houdt ze open)."""
    tmp = tempfile.mkdtemp(prefix="wispr-")
    for ext in ("", "-wal", "-shm"):
        if os.path.exists(DB + ext):
            shutil.copy2(DB + ext, os.path.join(tmp, "flow.sqlite" + ext))
    c = sqlite3.connect(f"file:{os.path.join(tmp, 'flow.sqlite')}?mode=ro", uri=True)
    sinds = (datetime.fromisoformat(DAG) - timedelta(days=dagen)).strftime("%Y-%m-%d")
    per_dag = defaultdict(lambda: {"dictaten": 0, "woorden": 0, "seconden": 0.0, "apps": defaultdict(int)})
    # timestamp is UTC-tekst; Belgische dag = +2 (zomer) / +1: we nemen de lokale tijd van deze computer
    for ts, woorden, duur, app in c.execute("select timestamp, numWords, duration, app from History where substr(timestamp,1,10) >= ? order by timestamp", (sinds,)):
        try:
            d = datetime.fromisoformat(ts.replace(" +00:00", "+00:00").replace(" ", "T", 1)).astimezone().strftime("%Y-%m-%d")
        except ValueError:
            d = ts[:10]
        r = per_dag[d]
        r["dictaten"] += 1
        r["woorden"] += int(woorden or 0)
        r["seconden"] += float(duur or 0)
        r["apps"][APPNAMEN.get(app, (app or "onbekend").split(".")[-1])] += int(woorden or 0)
    totaal = c.execute("select count(*), coalesce(sum(numWords),0), min(substr(timestamp,1,10)) from History").fetchone()
    c.close()
    shutil.rmtree(tmp, ignore_errors=True)
    return per_dag, totaal


def rapport(per_dag, totaal):
    dagen = sorted(per_dag)
    week = [d for d in dagen if d > (datetime.fromisoformat(DAG) - timedelta(days=7)).strftime("%Y-%m-%d")]
    w_dict = sum(per_dag[d]["dictaten"] for d in week)
    w_woord = sum(per_dag[d]["woorden"] for d in week)
    w_min = round(sum(per_dag[d]["seconden"] for d in week) / 60)
    apps = defaultdict(int)
    for d in week:
        for a, n in per_dag[d]["apps"].items():
            apps[a] += n
    regels = [f"# Wispr Flow, gebruik van {GEBRUIKER}", "", f"Stand {DAG}. Alleen tellingen; de tekst van dictaten blijft op de computer.", "",
              f"**Laatste 7 dagen:** {w_dict} dictaten, {w_woord} woorden, {w_min} minuten spreken. "
              f"**Sinds {totaal[2]}:** {totaal[0]} dictaten, {totaal[1]} woorden.", "",
              "| dag | dictaten | woorden | minuten | vooral in |", "|---|---|---|---|---|"]
    for d in reversed(dagen):
        r = per_dag[d]
        top = ", ".join(f"{a} {n}" for a, n in sorted(r["apps"].items(), key=lambda x: -x[1])[:3])
        regels.append(f"| {d} | {r['dictaten']} | {r['woorden']} | {round(r['seconden'] / 60)} | {top} |")
    regels += ["", "## Per app, laatste 7 dagen", "", "| app | woorden |", "|---|---|"] + [f"| {a} | {n} |" for a, n in sorted(apps.items(), key=lambda x: -x[1])]
    oordeel = "gebruikt" if w_woord >= 1000 else ("weinig gebruikt" if w_woord > 0 else "niet gebruikt")
    regels += ["", f"**Oordeel voor de Licentiewacht:** {oordeel} (grens: 1.000 woorden per week)."]
    return "\n".join(regels) + "\n", {"week_dictaten": w_dict, "week_woorden": w_woord, "week_minuten": w_min, "oordeel": oordeel,
                                        "totaal_dictaten": totaal[0], "totaal_woorden": totaal[1], "sinds": totaal[2],
                                        "apps_week": dict(sorted(apps.items(), key=lambda x: -x[1])[:10])}


def main():
    if not TOKEN:
        print("geen token in ~/.config/mijnagents/token", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(DB):
        hartslag("fout", taak="Wispr Flow-databank niet gevonden", detail=DB, nood=[{"tekst": f"Geen Wispr Flow-app op de computer van {GEBRUIKER} ({DB})", "wie": "mehdi"}])
        sys.exit(1)
    hartslag("actief", taak=f"gebruik van {GEBRUIKER} lezen")
    per_dag, totaal = lees(DAGEN)
    tekst, kern = rapport(per_dag, totaal)
    os.makedirs(RAPPORT, exist_ok=True)
    open(os.path.join(RAPPORT, f"{GEBRUIKER}.md"), "w", encoding="utf-8").write(tekst)
    json.dump({"gebruiker": GEBRUIKER, "stand": DAG, **kern, "per_dag": {d: {k: (v if k != "apps" else dict(v)) for k, v in r.items()} for d, r in per_dag.items()}},
              open(os.path.join(RAPPORT, f"{GEBRUIKER}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    vandaag = per_dag.get(DAG, {"dictaten": 0, "woorden": 0, "seconden": 0})
    uit = bord("/api/klaarzet", {"items": [{"van": NAAM, "voor": "licentiewacht", "soort": "gebruik", "sleutel": GEBRUIKER,
                                            "titel": f"Wispr Flow {GEBRUIKER} {DAG}: {vandaag['dictaten']} dictaten, {vandaag['woorden']} woorden; week {kern['week_woorden']} woorden ({kern['oordeel']})",
                                            "uniek": f"wispr:{GEBRUIKER}:{DAG}", "inhoud": {"dienst": "Wispr Flow", "gebruiker": GEBRUIKER, "dag": DAG, "vandaag": {k: v for k, v in vandaag.items() if k != "apps"}, **kern}}]})
    bord("/api/logboek", {"regels": [
        {"naam": NAAM, "onderwerp": f"{GEBRUIKER} {DAG}", "stap": "bron", "tekst": f"{vandaag['dictaten']} dictaten, {vandaag['woorden']} woorden vandaag; laatste 7 dagen {kern['week_dictaten']} dictaten, {kern['week_woorden']} woorden, {kern['week_minuten']} min",
         "detail": "\n".join(f"{a}: {n} woorden" for a, n in kern["apps_week"].items())},
        {"naam": NAAM, "onderwerp": f"{GEBRUIKER} {DAG}", "stap": "schrijf", "tekst": f"rapport {os.path.join(RAPPORT, GEBRUIKER + '.md')}; klaargezet {uit.get('nieuw', 0)} nieuw, {uit.get('bijgewerkt', 0)} bijgewerkt; oordeel: {kern['oordeel']}"}]})
    hartslag("klaar", taak=f"gebruik van {GEBRUIKER} gemeld", detail=f"week {kern['week_woorden']} woorden, {kern['week_dictaten']} dictaten: {kern['oordeel']}")
    print(f"{GEBRUIKER} {DAG}: vandaag {vandaag['dictaten']} dictaten / {vandaag['woorden']} woorden; week {kern['week_woorden']} woorden ({kern['oordeel']}); rapport in {RAPPORT}")


if __name__ == "__main__":
    main()
