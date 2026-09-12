#!/usr/bin/env python3
"""De Ontwikkelaar (Regie) — kijkt boven alle agents: hun code, hun gedrag, hun
verslagen en de wereld buiten, en brengt Mehdi wekelijks op de hoogte met
concrete verbeteringen.

Elke maandag 06:00 (of op verzoek via De Regisseur):
  1. Gedrag: per agent de status, stilte, fouten en het werkverslag van de laatste
     zeven dagen; wat er klaargezet is en niet opgepakt; open voorstellen.
  2. Code: de runners en koppelingen in mijnagents-runner en de app; de commits
     van de laatste week in de twee repo's (globaal-appportal, contract-systeem).
  3. Buiten: wat er nieuw is rond agents en gereedschap (webzoektocht; onder meer
     de Claude Agent SDK, OpenClaw en vergelijkbare projecten op GitHub).
  4. Een verslag voor Mehdi (klaargezet, soort 'verslag'): per agent wat goed
     gaat, wat fout gaat en de verbetering; wat van buiten de moeite is; wat hij
     moet beslissen. Verbeteringen aan een werkwijze zet hij als voorstel op het
     bord (runbook werkwijze-bijwerken); codewijzigingen als signaal voor Claude Code.
Leest alles, verandert niets zelf.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

NAAM = "ontwikkelaar"
ag = bord.Agent(NAAM)
MODEL = os.environ.get("ONTWIKKELAAR_MODEL", "claude-opus-5")
REPOS = {"globaal-appportal": os.path.expanduser("~/appportal"), "contract-systeem": os.path.expanduser("~/appportal/contracten")}
CODE_PADEN = [HIER, os.path.expanduser("~/appportal/mijnagents")]
MAX_CODE = 260000


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/agents/.env")


def code_bundel():
    delen, totaal = [], 0
    for basis in CODE_PADEN:
        for wortel, mappen, bestanden in os.walk(basis):
            mappen[:] = [m for m in mappen if m not in ("__pycache__", ".git", "werkwijze")]
            for b in sorted(bestanden):
                if not b.endswith((".py", ".html")):
                    continue
                pad = os.path.join(wortel, b)
                try:
                    t = open(pad, encoding="utf-8").read()
                except OSError:
                    continue
                stuk = f"\n\n===== {os.path.relpath(pad, os.path.expanduser('~/appportal'))} =====\n{t}"
                if totaal + len(stuk) > MAX_CODE:
                    delen.append(f"\n\n===== {b}: overgeslagen (te groot) =====")
                    continue
                delen.append(stuk)
                totaal += len(stuk)
    return "".join(delen)


def git_log(pad, dagen=7):
    try:
        uit = subprocess.run(["git", "-C", pad, "log", f"--since={dagen} days ago", "--format=%h %ad %s", "--date=short", "--stat=100,80"],
                             capture_output=True, text=True, timeout=60)
        return uit.stdout[-12000:]
    except Exception as e:  # noqa: BLE001
        return f"(git log mislukt: {e})"


def gedrag():
    o = bord.call("/api/overzicht").get("agents", [])
    sinds = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    per_agent = []
    for a in o:
        verslag = bord.call(f"/api/logboek/{a['naam']}?n=200").get("regels", [])
        verslag = [r for r in verslag if r.get("ts", "") >= sinds]
        fouten = [r for r in verslag if r.get("stap") == "fout"]
        per_agent.append({"naam": a["naam"], "label": a["label"], "afdeling": a["type"], "cadans": a["cadans"],
                          "status": a.get("status"), "open_voorstellen": a.get("open_voorstellen", 0),
                          "verslagregels_7d": len(verslag), "fouten_7d": len(fouten),
                          "fouten": [f"{r['ts'][:16]} {r['tekst'][:160]}" for r in fouten[-15:]],
                          "laatste_regels": [f"{r['ts'][:16]} [{r['stap']}] {r['tekst'][:160]}" for r in verslag[-25:]],
                          "werkwijze": a.get("werkwijze") or ""})
    klaar = bord.call("/api/klaarzet?voor=h-architects&status=klaar&n=200").get("items", [])
    return per_agent, {"niet_opgepakt_h-architects": len(klaar)}


VRAAG = ""
for _i, _a in enumerate(__import__("sys").argv):
    if _a == "--vraag" and _i + 1 < len(__import__("sys").argv):
        VRAAG = __import__("sys").argv[_i + 1].strip()


def verslag_met_model(per_agent, bak, code, logs):
    from anthropic import Anthropic
    client = Anthropic()
    system = (
        "Je bent De Ontwikkelaar, de agent die boven alle agents van Mehdi Chegini (H-Architects) staat. "
        "Nederlands, geen emoji, geen kastlijntjes; beslissing eerst; elk punt een volgende stap. "
        "Je beoordeelt gedrag (verslagen, fouten, stilte, wat blijft liggen), code (runners, koppelingen, app) "
        "en de buitenwereld (wat agents elders kunnen). Je bent concreet en eerlijk: noem het bestand en de "
        "functie bij een codepunt, de agent en de datum bij een gedragspunt, de bron met url bij nieuws. "
        "Beweer niets dat je niet in het materiaal of de zoekresultaten zag.\n\n"
        "Lever een markdown-verslag met precies deze koppen: "
        "'## Stand van het team' (één regel per agent: goed, fout, verbetering), "
        "'## Verbeteringen die ik voorstel' (genummerd; per punt: wat, waarom, waar (bestand/werkwijze), moeite klein/middel/groot), "
        "'## Van buiten' (drie tot vijf ontwikkelingen die voor dit team tellen, met url en wat we ermee kunnen), "
        "'## Wat Mehdi beslist' (korte lijst). Maximaal 900 woorden."
        + (" Gerichte ronde: Mehdi stelt een vraag. Zet dan als EERSTE kop '## Antwoord op de vraag van Mehdi' met een "
           "concreet, onderbouwd antwoord (bronnen met url, wat het voor dit team betekent, wat het kost aan werk), "
           "en hou de andere koppen kort; maximaal 1400 woorden." if VRAAG else "")
    )
    user = json.dumps({"agents": per_agent, "bak": bak, "git_laatste_week": logs}, ensure_ascii=False)[:150000]
    user += "\n\n===== CODE =====\n" + code
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}]
    zoek = ("\n\nVRAAG VAN MEHDI (beantwoord deze eerst, zoek gericht op het web, minstens vier bronnen): " + VRAAG) if VRAAG else \
        ("\n\nZoek ook op het web naar wat er deze week nieuw is rond: Claude Agent SDK, "
         "Anthropic agents, 'OpenClaw' agents GitHub, open-source agent frameworks voor kleine bedrijven.")
    berichten = [{"role": "user", "content": user + zoek}]
    teksten, tokens = [], 0
    for _ in range(6):
        resp = client.messages.create(model=MODEL, max_tokens=6000, system=system, messages=berichten, tools=tools)
        tokens += (getattr(resp.usage, "input_tokens", 0) or 0) + (getattr(resp.usage, "output_tokens", 0) or 0)
        teksten += [getattr(b, "text", "") for b in resp.content if getattr(b, "type", None) == "text"]
        if resp.stop_reason == "pause_turn":
            berichten.append({"role": "assistant", "content": resp.content})
            continue
        break
    return "".join(teksten).strip(), tokens


def main():
    ag.hartslag("actief", taak="weekcontrole van het team")
    try:
        per_agent, bak = gedrag()
        code = code_bundel() if not VRAAG else "(gerichte ronde: codebundel overgeslagen om tokens te sparen)"
        logs = {naam: git_log(pad) for naam, pad in REPOS.items()}
        ag.log("week", "bron", f"{len(per_agent)} agents bekeken, {sum(a['fouten_7d'] for a in per_agent)} fouten in 7 dagen, "
                               f"{bak['niet_opgepakt_h-architects']} items niet opgepakt; code {len(code)} tekens; git van 2 repo's")
        tekst, tokens = verslag_met_model(per_agent, bak, code, logs)
        week = datetime.now().strftime("%G-W%V")
        uit = ag.klaarzet([{"voor": "mehdi", "soort": "verslag", "sleutel": week, "titel": f"Ontwikkelverslag {week}",
                            "uniek": f"ontwikkelverslag:{week}:{datetime.now().strftime('%d%H%M')}", "inhoud": tekst}])
        if VRAAG:
            ag.log("week", "bron", "gerichte ronde op vraag van Mehdi", VRAAG)
        ag.log("week", "melding", f"ontwikkelverslag {week} klaargezet voor Mehdi ({tokens} tokens)", tekst)
        ag.log_verstuur()
        ag.hartslag("klaar", taak=f"ontwikkelverslag {week} klaar", detail=f"{len(per_agent)} agents, {sum(a['fouten_7d'] for a in per_agent)} fouten in 7 dagen",
                    voorstel={"actie": f"Lees het ontwikkelverslag {week}", "reden": "wekelijkse controle van code, gedrag en buitenwereld",
                              "doel": "bord: klaargezet voor Mehdi"})
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="weekcontrole mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()
