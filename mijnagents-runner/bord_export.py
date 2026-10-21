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
Geen gespreksinhoud buiten de VM (H1, ontwerp regie-zoom v1.2): van een gesprek met een agent gaan alleen id, aan,
status, tijd en lengtes mee, nooit de vraag of het antwoord; in het werkverslag van De Bode en De Regisseur staat bij
een bericht alleen hoe lang vraag en antwoord waren.
Van een privé-item in klaargezet/ alleen tijd, soort, voor wie en status, nooit titel, verwijzing of inhoud; in een
Dagverslag, in de inhoud van elk ander klaarzet-item en in het werkverslag wordt een regel met PRIVÉ, of een bevinding van
De Plaudwacht in de oude vorm met ' · privé', "(privé)" (RZ2-01, voor wat van voor 22-10-2026 nog in het venster staat).
Privé is ook een item met afdeling prive in de inhoud, en een regel met de titel of de verwijzing van zo'n item (RZ3-01).
Wat buiten het venster valt, schrijft de export niet opnieuw en wist ze ook niet: een bestand van voor RZ2-01 en RZ3-01
blijft zoals het was, hier en in Data uit Mehdi, tot een afzonderlijk goedgekeurde opruiming.
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


# H1: een werkverslagregel over een bericht van Mehdi (onderwerp "bericht <id> ...", zo schrijven De Bode en De
# Regisseur het) draagt de vraag in de tekst en het antwoord in het detail. Tot 21-10-2026 schreven ze die voluit; de
# export houdt alleen de lengte, ook voor die oude regels.
GESPREK_ONDERWERP = re.compile(r"^bericht \d+")
VRAAG_IN_TEKST = re.compile(r"^((?:uit (?:WhatsApp|Telegram) aan|vraag van) [^:\n]*?):\s*(.*)$", re.S)


def zonder_gesprekstekst(onderwerp, tekst, detail):
    """(tekst, detail) van een werkverslagregel zoals ze naar de export gaan (H1): bij een bericht van Mehdi de lengte
    van vraag en antwoord in plaats van de tekst. Andere regels blijven zoals ze zijn."""
    if not GESPREK_ONDERWERP.match(onderwerp or ""):
        return tekst, detail
    m = VRAAG_IN_TEKST.match(tekst or "")
    if m:
        tekst = f"{m.group(1)}, {len(m.group(2))} tekens (vraag niet in de export)"
    if (detail or "").strip():
        detail = f"({len(detail)} tekens, niet in de export)"
    return tekst, detail


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


def is_prive(titel, inhoud):
    """RZ2-01: een klaarzet-item is privé als zijn inhoud prive draagt of zijn titel PRIVÉ, zoals De Fathomwacht, De
    Plaudwacht en De Zoomwacht het zetten. Tot 21-10-2026 schreef de export van zo'n item de titel (met wie en waarover)
    en de hele inhoud uit, en die gaat naar Data uit Mehdi.
    RZ3-01 (besluit van de regie, 22-10-2026: de veilige kant): ook een inhoud met afdeling prive is privé, zoals de
    dossierbeslissing (plaud/dossier.py) het zegt, ook bij prive=false. Tot 22-10-2026 zetten De Fathomwacht en De
    Plaudwacht zo'n gesprek klaar met naam en onderwerp in titel en inhoud, zonder PRIVÉ."""
    if "PRIVÉ" in (titel or ""):
        return True
    s = (inhoud or "").strip()
    try:
        d = json.loads(s) if s.startswith("{") else {}
    except ValueError:
        d = {}
    return isinstance(d, dict) and (bool(d.get("prive")) or str(d.get("afdeling") or "").strip().lower() in ("prive", "privé"))


def prive_regel(r):
    """Een regel die een privé-item bij naam noemt (RZ2-01): de titel met PRIVÉ (De Fathomwacht, De Plaudwacht, De
    Zoomwacht); een bevinding in de oude vorm met ' · privé', van De Plaudwacht tot 22-10-2026 ('<hoofdpersoon> · dossier
    ... · privé · voor mehdi') en van De Fathomwacht tot 21-10-2026 ('<hoofdpersoon> · <afdeling> · <thema> · privé');
    of een oude bronregel van De Fathomwacht met afdeling prive ('<personen> | prive | <thema>'). Sindsdien schrijven ze
    van een privégesprek alleen wanneer en hoe lang.
    RZ3-01: ook de bevinding van De Fathomwacht tot 22-10-2026 voor een gesprek met afdeling prive en prive=false
    ('<hoofdpersoon> · prive · <thema> · zekerheid ...'): die was nog niet privé."""
    return "PRIVÉ" in r or " · privé" in r or " | prive | " in r or " · prive · " in r


def prive_kenmerken(c):
    """RZ3-01: de titels en verwijzingen van de privé-items op het bord, ook van voor het venster. Een bundel, een
    Dagverslag of een werkverslagregel van voor 22-10-2026 noemt zo'n item bij zijn titel, met de archiefmap (die naar de
    titel in Fathom of de naam in Plaud heet) als verwijzing, en dat herkent prive_regel niet als het item zonder PRIVÉ
    klaarstond (afdeling prive, prive=false). Alleen kenmerken van minstens twaalf tekens, zodat een korte titel geen
    gewone regel wegneemt."""
    kenmerken = set()
    for r in c.execute("select titel, inhoud, verwijzing from klaarzet where soort != 'dagbundel'"):
        if is_prive(r["titel"], r["inhoud"]):
            kenmerken |= {k.strip() for k in (r["titel"], r["verwijzing"]) if k and len(k.strip()) >= 12}
    return frozenset(kenmerken)


def zonder_prive_regels(tekst, kenmerken=()):
    """Een Dagverslag, een bundel of een werkverslagregel van voor 21-10-2026 noemt een privé-item met zijn titel: die regel
    wordt '(privé)' (RZ2-01). Sinds dan zet De Dagbundelaar er zelf 'privégesprek, N min' van. Tot 22-10-2026 ging alleen
    dagverslagen/ hierdoor; een oude bundel in klaargezet/ en het detail van De Dagbundelaar in werkverslag/ (met 'Toe te
    wijzen') droegen nog de naam en het onderwerp. RZ3-01: ook een regel met de titel of de verwijzing van een privé-item
    (kenmerken, zie prive_kenmerken) wordt '(privé)'."""
    return "\n".join("(privé)" if prive_regel(r) or any(k in r for k in kenmerken) else r for r in (tekst or "").split("\n"))


def main():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    sinds = (datetime.now(BE) - timedelta(days=DAGEN)).isoformat()
    kenmerken = prive_kenmerken(c)     # RZ3-01: titels en verwijzingen van privé-items, voor oude bundels en werkverslagregels
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
            tekst, detail = zonder_gesprekstekst(r["onderwerp"], r["tekst"], r["detail"] or "")
            # RZ2-01: een regel die een privé-item bij naam noemt, ook in een oude regel die nog in het venster staat. Noemt
            # de tekst een privégesprek in de oude vorm, dan valt ook het detail weg: daar stond de reden (met wie en waarom).
            if any(prive_regel(t) for t in (tekst or "").split("\n")):
                detail = "(privé, niet in de export)" if detail.strip() else detail
            ond, tekst, detail = (zonder_prive_regels(t, kenmerken) for t in (r["onderwerp"] or "", tekst or "", detail))
            per[r["naam"]][d.strftime("%Y-%m-%d")].append((d.strftime("%H:%M"), r["stap"], ond, tekst, detail))
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
                if is_prive(it["titel"], it["inhoud"]):
                    uit += [f"## {be(it['ts']).strftime('%H:%M')} {it['soort']} voor {it['voor']} ({it['status']}): (privé)", ""]
                    continue
                uit.append(f"## {be(it['ts']).strftime('%H:%M')} {it['soort']} voor {it['voor']} ({it['status']}): {it['titel']}")
                if it.get("verwijzing"):
                    uit.append(f"  - verwijzing: {it['verwijzing']}")
                # RZ2-01: een bundel of Dagverslag van voor 21-10-2026 noemt een privé-item met zijn titel
                uit.append(zonder_prive_regels(inhoud_tekst(it["inhoud"]), kenmerken))
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
    # Regisseur: gesprekken met Mehdi, zonder vraag- of antwoordtekst (H1): die blijven op het bord, op de VM
    uit = ["# Gesprekken via het bord, WhatsApp en Telegram", "",
           "Alleen id, aan, status, tijd en lengtes; de vraag en het antwoord blijven op het bord (H1, 21-10-2026).", "",
           "| id | gevraagd | aan | status | beantwoord | vraag | antwoord |", "|---|---|---|---|---|---|---|"]
    for r in c.execute("select id, aan, tekst, antwoord, status, ts, beantwoord_ts from gesprek order by ts desc limit 300"):
        d, b = be(r["ts"]), be(r["beantwoord_ts"] or "")
        uit.append(f"| {r['id']} | {d.strftime('%d-%m %H:%M') if d else ''} | {r['aan']} | {r['status']} | "
                   f"{b.strftime('%d-%m %H:%M') if b else ''} | {len(r['tekst'] or '')} tekens | {len(r['antwoord'] or '')} tekens |")
    geschreven += schrijf(os.path.join(UIT, "Regisseur", "gesprekken.md"), "\n".join(uit) + "\n")
    # Ontwikkelaar: verslagen voluit
    for r in c.execute("select titel, inhoud, ts from klaarzet where soort='verslag' order by ts"):
        d = be(r["ts"])
        geschreven += schrijf(os.path.join(UIT, "Ontwikkelaar", "verslagen", f"{d.strftime('%Y-%m-%d %H%M')} {veilig(r['titel'])}.md"), r["inhoud"] or "")
    # Levenscoach: coaching voluit; Dagbundelaar: dagverslagen voluit
    for soort, m, sub in (("coaching", "Levenscoach", "coaching"), ("dagbundel", "Dagbundelaar", "dagverslagen"), ("dagplan", "Agendawacht", "dagplan")):
        for r in c.execute("select titel, inhoud, sleutel, ts from klaarzet where soort=? and ts >= ? order by ts", (soort, sinds)):
            d = be(r["ts"])
            tekst = zonder_prive_regels(r["inhoud"], kenmerken) if soort == "dagbundel" else (r["inhoud"] or "")
            geschreven += schrijf(os.path.join(UIT, m, sub, f"{d.strftime('%Y-%m-%d %H%M')} {veilig(r['titel'])}.md"), tekst + "\n")
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
