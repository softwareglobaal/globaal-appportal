#!/usr/bin/env python3
"""Export van het bord naar één map per agent, voor Data uit Mehdi (regel van Mehdi, 12-09-2026:
elke agent zijn eigen map, zodat hij en later de collega's alles kunnen lezen).

Leest de bord-database alleen en schrijft markdown en json naar mijnagents-data/export/<Agent>/:
  - werkwijze.md                          de werkwijze zoals ze op het bord staat
  - werkverslag/JJJJ-MM-DD.md             wat de agent die dag las, vond, besliste, schreef
  - klaargezet/JJJJ-MM-DD.md              wat hij die dag klaarzette (afspraken, dagplan, signalen, ...)
  - noden.md, voorstellen.md              wat hij mist, wat hij voorstelde
  - <extra>                               per agent: Agendawacht belrooster.json, Ontwikkelaar verslagen/, Regisseur gesprekken.md
Werkwijzen van alle agents samen in export/_Werkwijzen/. Nooit wissen; alleen (over)schrijven.
De Mac-synctaak kopieert export/ naar Data uit Mehdi. Cron: elk half uur.
"""
import json
import os
import re
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DB = os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db")
DATA = os.path.expanduser("~/appportal/mijnagents-data")
UIT = os.path.join(DATA, "export")
BE = ZoneInfo("Europe/Brussels")
DAGEN = int(os.environ.get("EXPORT_DAGEN", "14"))
# mapnaam per agent (label zonder lidwoord); niet-genoemde agents krijgen hun label
MAP = {"agenda-wacht": "Agendawacht", "archivaris": "Archivaris", "bode": "Bode", "contracten-agent": "Contractmaker",
       "dagbundelaar": "Dagbundelaar", "ontwikkelaar": "Ontwikkelaar", "regisseur": "Regisseur", "levenscoach": "Levenscoach",
       "fathom-wacht": "Fathom", "plaud-wacht": "Plaud", "locatie-wacht": "Locatie", "icloud-wacht": "Fotos",
       "gezondheid-wacht": "Gezondheidswacht", "mail-mch": "Mailwacht mch", "mail-prive": "Mailwacht prive",
       "zoom-wacht": "Zoomwacht", "whatsapp-wacht": "WhatsApp-wacht", "belwacht": "Belwacht",
       "communicatie-bundelaar": "Communicatiebundelaar"}


def veilig(s):
    return re.sub(r"[^\w\- .,()]+", "", s or "").strip()[:60] or "agent"


def be(ts):
    try:
        d = datetime.fromisoformat(ts)
        return d.astimezone(BE) if d.tzinfo else d
    except (ValueError, TypeError):
        return None


def schrijf(pad, tekst):
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    oud = open(pad, encoding="utf-8").read() if os.path.exists(pad) else None
    if oud != tekst:
        open(pad, "w", encoding="utf-8").write(tekst)
        return 1
    return 0


def inhoud_tekst(inhoud):
    """Klaarzet-inhoud leesbaar: json wordt een lijstje, tekst blijft tekst."""
    s = (inhoud or "").strip()
    if s.startswith("{"):
        try:
            d = json.loads(s)
            regels = []
            for k, v in d.items():
                if k in ("fotos", "deelnemers") and isinstance(v, list):
                    regels.append(f"  - {k}: {len(v)} stuks")
                elif isinstance(v, (dict, list)):
                    regels.append(f"  - {k}: {json.dumps(v, ensure_ascii=False)[:300]}")
                elif v not in ("", None):
                    regels.append(f"  - {k}: {str(v)[:400]}")
            return "\n".join(regels)
        except ValueError:
            pass
    return "\n".join("  " + r for r in s.splitlines()[:80])


def main():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    sinds = (datetime.now(BE) - timedelta(days=DAGEN)).isoformat()
    agents = {r["naam"]: dict(r) for r in c.execute("select naam, label, type, rol, cadans, werkwijze, actief from agent")}
    geschreven = 0
    # werkwijzen: per agent en verzameld
    for naam, a in agents.items():
        m = MAP.get(naam) or veilig(re.sub(r"^De ", "", a["label"] or naam))
        ww = a.get("werkwijze") or f"# {a['label']}\n\n(nog geen werkwijze op het bord)\n"
        geschreven += schrijf(os.path.join(UIT, m, "werkwijze.md"), ww)
        geschreven += schrijf(os.path.join(UIT, "_Werkwijzen", f"{m}.md"), ww)
    # werkverslag per agent per dag
    per = defaultdict(lambda: defaultdict(list))
    for r in c.execute("select naam, onderwerp, stap, tekst, detail, ts from logboek where ts >= ? order by ts", (sinds,)):
        d = be(r["ts"])
        if d:
            per[r["naam"]][d.strftime("%Y-%m-%d")].append((d.strftime("%H:%M"), r["stap"], r["onderwerp"], r["tekst"], r["detail"] or ""))
    for naam, dagen in per.items():
        m = MAP.get(naam) or veilig(re.sub(r"^De ", "", (agents.get(naam) or {}).get("label") or naam))
        for dag, regels in dagen.items():
            uit = [f"# Werkverslag {m} {dag}", "", f"{len(regels)} stappen (Belgische tijd).", ""]
            for uur, stap, ond, tekst, detail in regels:
                uit.append(f"## {uur} [{stap}] {ond}".rstrip())
                uit.append("")
                uit.append(tekst)
                if detail.strip():
                    uit += ["", "```", detail.strip()[:6000], "```"]
                uit.append("")
            geschreven += schrijf(os.path.join(UIT, m, "werkverslag", f"{dag}.md"), "\n".join(uit))
    # klaargezet per agent per dag
    kz = defaultdict(lambda: defaultdict(list))
    for r in c.execute("select van, voor, soort, sleutel, titel, inhoud, verwijzing, status, ts from klaarzet where ts >= ? order by ts", (sinds,)):
        d = be(r["ts"])
        if d:
            kz[r["van"]][d.strftime("%Y-%m-%d")].append(dict(r))
    for naam, dagen in kz.items():
        m = MAP.get(naam) or veilig(re.sub(r"^De ", "", (agents.get(naam) or {}).get("label") or naam))
        for dag, items in dagen.items():
            uit = [f"# Klaargezet door {m} op {dag}", "", f"{len(items)} items.", ""]
            for it in items:
                uit.append(f"## {be(it['ts']).strftime('%H:%M')} {it['soort']} voor {it['voor']} ({it['status']}): {it['titel']}")
                if it.get("verwijzing"):
                    uit.append(f"  - verwijzing: {it['verwijzing']}")
                uit.append(inhoud_tekst(it["inhoud"]))
                uit.append("")
            geschreven += schrijf(os.path.join(UIT, m, "klaargezet", f"{dag}.md"), "\n".join(uit))
    # noden en voorstellen per agent
    noden = defaultdict(list)
    for r in c.execute("select naam, tekst, wie, open, ts, opgelost_ts from nood order by open desc, ts desc"):
        noden[r["naam"]].append(r)
    for naam, lijst in noden.items():
        m = MAP.get(naam) or veilig(re.sub(r"^De ", "", (agents.get(naam) or {}).get("label") or naam))
        uit = [f"# Noden van {m}", "", "| open | sinds | wie | wat |", "|---|---|---|---|"]
        for r in lijst:
            d = be(r["ts"])
            uit.append(f"| {'ja' if r['open'] else 'opgelost'} | {d.strftime('%d-%m %H:%M') if d else ''} | {r['wie']} | {r['tekst'][:200]} |")
        geschreven += schrijf(os.path.join(UIT, m, "noden.md"), "\n".join(uit) + "\n")
    vs = defaultdict(list)
    for r in c.execute("select naam, actie, doel, reden, runbook, status, besluit_door, ts from voorstel order by ts desc limit 500"):
        vs[r["naam"]].append(r)
    for naam, lijst in vs.items():
        m = MAP.get(naam) or veilig(re.sub(r"^De ", "", (agents.get(naam) or {}).get("label") or naam))
        uit = [f"# Voorstellen van {m}", "", "| wanneer | status | actie | doel | reden | runbook | besluit door |", "|---|---|---|---|---|---|---|"]
        for r in lijst:
            d = be(r["ts"])
            uit.append(f"| {d.strftime('%d-%m %H:%M') if d else ''} | {r['status']} | {r['actie'][:80]} | {(r['doel'] or '')[:60]} | {(r['reden'] or '')[:80]} | {r['runbook'] or ''} | {r['besluit_door'] or ''} |")
        geschreven += schrijf(os.path.join(UIT, m, "voorstellen.md"), "\n".join(uit) + "\n")
    # Regisseur: gesprekken met Mehdi
    uit = ["# Gesprekken via het bord en Telegram", "", "| wanneer | van | aan | vraag | antwoord | status |", "|---|---|---|---|---|---|"]
    for r in c.execute("select aan, van, tekst, antwoord, status, ts from gesprek order by ts desc limit 300"):
        d = be(r["ts"])
        uit.append(f"| {d.strftime('%d-%m %H:%M') if d else ''} | {r['van']} | {r['aan']} | {(r['tekst'] or '')[:120].replace(chr(10), ' ')} | {(r['antwoord'] or '')[:160].replace(chr(10), ' ')} | {r['status']} |")
    geschreven += schrijf(os.path.join(UIT, "Regisseur", "gesprekken.md"), "\n".join(uit) + "\n")
    # Ontwikkelaar: verslagen voluit
    for r in c.execute("select titel, inhoud, ts from klaarzet where soort='verslag' order by ts"):
        d = be(r["ts"])
        geschreven += schrijf(os.path.join(UIT, "Ontwikkelaar", "verslagen", f"{d.strftime('%Y-%m-%d %H%M')} {veilig(r['titel'])}.md"), r["inhoud"] or "")
    # Levenscoach: coaching voluit; Dagbundelaar: dagverslagen voluit
    for soort, m, sub in (("coaching", "Levenscoach", "coaching"), ("dagbundel", "Dagbundelaar", "dagverslagen"), ("dagplan", "Agendawacht", "dagplan")):
        for r in c.execute("select titel, inhoud, sleutel, ts from klaarzet where soort=? and ts >= ? order by ts", (soort, sinds)):
            d = be(r["ts"])
            geschreven += schrijf(os.path.join(UIT, m, sub, f"{d.strftime('%Y-%m-%d %H%M')} {veilig(r['titel'])}.md"), (r["inhoud"] or "") + "\n")
    # Agendawacht: belrooster en adressen (kopie); Bord-map bestaat al voor weekoverzichten
    for bron, doel in (("belrooster.json", os.path.join("Agendawacht", "belrooster.json")), ("agenda-adressen.json", os.path.join("Agendawacht", "adressen.json"))):
        p = os.path.join(DATA, bron)
        if os.path.exists(p):
            os.makedirs(os.path.dirname(os.path.join(UIT, doel)), exist_ok=True)
            shutil.copy2(p, os.path.join(UIT, doel))
    # stand van het team
    uit = ["# Stand van het team", "", f"Gemaakt {datetime.now(BE).strftime('%Y-%m-%d %H:%M')} (Belgische tijd).", "", "| agent | status | taak | detail | laatste hartslag |", "|---|---|---|---|---|"]
    for r in c.execute("select s.naam, a.label, s.status, s.taak, s.detail, s.ts from status s join agent a on a.naam=s.naam order by a.label"):
        d = be(r["ts"])
        uit.append(f"| {r['label']} | {r['status']} | {(r['taak'] or '')[:60]} | {(r['detail'] or '')[:100]} | {d.strftime('%d-%m %H:%M') if d else ''} |")
    geschreven += schrijf(os.path.join(UIT, "_Werkwijzen", "stand van het team.md"), "\n".join(uit) + "\n")
    print(f"export: {geschreven} bestanden geschreven of bijgewerkt in {UIT}")


if __name__ == "__main__":
    main()
