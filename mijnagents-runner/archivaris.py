#!/usr/bin/env python3
"""De Archivaris (Regie): geeft elk opgenomen gesprek (Fathom, Plaud) een definitief label
op inhoud, getoetst aan agenda en locatie, en bepaalt waar het hoort. Verplaatst niets
(beslissing 3 en 4 van Mehdi zijn nog open). Werkwijze op het bord is de bron van de
regels; de sectie "Correcties van Mehdi" daar gaat boven alles.

Gebruik: archivaris.py [--van JJJJ-MM-DD --tot JJJJ-MM-DD]   (standaard: de laatste drie dagen)
"""
import glob
import json
import os
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import organisatie  # noqa: E402
import organisatie  # noqa: E402
import projectadressen  # noqa: E402

DB = os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db")
BORDMAP = os.path.expanduser("~/appportal/mijnagents-data/bord")
MODEL = os.environ.get("ARCHIVARIS_MODEL", "claude-sonnet-5")
LABELS = ["HA project", "HA sales", "UNABO sales", "UNABO project", "TKN sales", "TKN project", "Harmoniebouw", "Contrax", "Elevait", "Regie intern", "Prive", "Onbekend"]
FIRMA = {"HA": "HA", "UNABO": "UNABO", "HB": "Harmoniebouw", "HARMONIEBOUW": "Harmoniebouw", "CONTRAX": "Contrax", "TKN": "TKN", "ELEVAIT": "Elevait", "PRIVE": "Prive"}
DOEL = {"HA project": "projectmap H-A, map 0 Fathom", "HA sales": "salesmap onder o01. Sales", "UNABO sales": "salesmap onder o01. Sales",
        "UNABO project": "projectmap UNABO", "TKN sales": "salesmap onder o01. Sales (TKN-Buro)", "TKN project": "projectmap TKN-Buro",
        "Harmoniebouw": "Harmoniebouw", "Contrax": "Contrax", "Elevait": "Elevait NV (map Elevait in Data uit Mehdi)",
        "Regie intern": "blijft in Data uit Mehdi/Fathom", "Prive": "Fathom/Prive", "Onbekend": "vraag aan Mehdi"}
ag = bord.Agent("archivaris")


def _env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env("~/appportal/.env")
_env("~/appportal/mijnagents-data/.env")


def db():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def afspraken(van, tot):
    uit = []
    for r in db().execute("select inhoud, titel from klaarzet where soort='afspraak'"):
        try:
            d = json.loads(r["inhoud"]) if (r["inhoud"] or "").strip().startswith("{") else {}
        except ValueError:
            continue
        if not d.get("start") or "T" not in d["start"] or not (van <= d["start"][:10] <= tot):
            continue
        d["_s"] = datetime.fromisoformat(d["start"]).replace(tzinfo=None)
        d["_e"] = datetime.fromisoformat(d["einde"]).replace(tzinfo=None) if d.get("einde") and "T" in d["einde"] else d["_s"] + timedelta(minutes=30)
        uit.append(d)
    return uit


def afspraak_op(g, lijst):
    s = datetime.fromisoformat(f"{g['datum']}T{g['start']}")
    e = s + timedelta(minutes=max(int(g.get("minuten") or 0), 5))
    beste, overlap = None, timedelta(0)
    for a in lijst:
        o = min(e, a["_e"] + timedelta(minutes=15)) - max(s, a["_s"] - timedelta(minutes=15))
        if o > overlap:
            beste, overlap = a, o
    return beste


def locatie_op(datum, uur):
    """Waar was Mehdi rond dat uur volgens het locatiedagboek: tekst of ''."""
    pad = os.path.expanduser(f"~/appportal/mijnagents-data/locatielogboek/dagen/{datum}.md")
    try:
        regels = open(pad, encoding="utf-8").read().splitlines()
    except OSError:
        return ""
    for r in regels:
        d = [x.strip() for x in r.split("|")]
        if len(d) >= 6 and re.match(r"^\d\d:\d\d$", d[1]) and re.match(r"^\d\d:\d\d$", d[2]):
            van, tot = d[1], d[2]
            if (van <= uur <= tot) or (tot < van and (uur >= van or uur <= tot)):
                return f"{d[4]}: {d[5]}"
    return ""


def correcties(werkwijze):
    """'- 2026-09-11 13:47 Siyan = HA sales (reden)' -> {(datum, uur): (label, reden)}"""
    uit = {}
    sectie = werkwijze.split("## Correcties van Mehdi", 1)[-1] if "## Correcties van Mehdi" in werkwijze else ""
    for m in re.finditer(r"^-\s*(\d{4}-\d\d-\d\d)\s+(\d\d:\d\d)\s+(.+?)\s*=\s*([^\n(]+)(?:\((.*?)\))?", sectie, re.M):
        lab = m.group(4).strip()
        for L in LABELS:
            if lab.lower() == L.lower():
                uit[(m.group(1), m.group(2))] = (L, (m.group(5) or "").strip(), m.group(3).strip())
    return uit


def label_met_model(g, tekst, afspraak, locatie, project, regels_mehdi):
    from anthropic import Anthropic
    schema = {"name": "label", "description": "Definitief label van het gesprek", "input_schema": {"type": "object", "properties": {
        "label": {"type": "string", "enum": LABELS}, "zekerheid": {"type": "string", "enum": ["hoog", "middel", "laag"]},
        "reden": {"type": "string"}, "agenda_toets": {"type": "string"}, "locatie_toets": {"type": "string"},
        "projectnummer": {"type": "string"}, "vraag_aan_mehdi": {"type": "string"}},
        "required": ["label", "zekerheid", "reden", "agenda_toets", "locatie_toets", "projectnummer", "vraag_aan_mehdi"]}}
    system = ("Je bent De Archivaris van Mehdi Chegini. Zijn firma's: H-Architects (HA, architectuur), UNABO (EPB, plaatsbeschrijving, "
              "3D-scan, stabiliteit als dienst), TKN-Buro (TKN, engineering en stabiliteitsstudies; eigen sales), Harmoniebouw (aannemer), "
              "Contrax, en Elevait NV (opgericht door Mehdi met zijn partners Shaniel, Angela en Siyan: AI-trainingen, AI-toepassingen, "
              "sollicitaties en opbouw van dat bedrijf horen bij het label Elevait, niet bij Regie intern). Je geeft een opgenomen gesprek één label uit de vaste lijst. Regels: inhoud eerst; de agenda-afspraak op dat uur is "
              "een zware toets (code PO/PB = sales, KO/KB = project, IN = intern; de firma in de code is de firma: [TKN-PO] is TKN sales, "
              "nooit HA sales); de locatie is een toets voor gesprekken buiten; een "
              "dossiernummer (26xx, 56xx) maakt het een project, geen sales. 'Regie intern' = Mehdi met collega's (zie de lijst 'collegas': naam, afdeling, firma; uit organisatie.globaal.be) "
              "over organisatie, AI, IT, HR, planning; een collega van TKN-Buro of Harmoniebouw over een klantdossier is wel die firma. "
              "'Prive' = Mehdi alleen, met Angela (partner) of persoonlijk; bij twijfel tussen werk en privé kies Prive. "
              "Spreekt de inhoud de agenda tegen, zeg dat in agenda_toets en kies zekerheid middel. Onbekende externe zonder "
              "aanwijzing: 'Onbekend', zekerheid laag, en formuleer één korte vraag aan Mehdi. Nederlands, kort, geen emoji. "
              "Regels die Mehdi zelf gaf gaan boven alles.")
    user = json.dumps({"gesprek": {"datum": g["datum"], "start": g["start"], "minuten": g["minuten"], "bron": g["bron"], "personen": g["personen"],
                                   "bedrijf": g["bedrijf"], "afdeling_herkend": g["afdeling"], "thema": g["thema"], "project": g["project"],
                                   "prive_herkend": bool(g["prive"]), "opgenomen_door": g["opgenomen_door"]},
                       "agenda_afspraak_op_dat_uur": ({"titel": afspraak.get("titel"), "firma": afspraak.get("firma"), "soort": afspraak.get("soort"),
                                                       "nummer": afspraak.get("nummer"), "klant": afspraak.get("klant"), "locatie": afspraak.get("locatie"),
                                                       "buiten": afspraak.get("buiten")} if afspraak else None),
                       "locatie_van_mehdi_op_dat_uur": locatie or "onbekend",
                       "projectmap_bij_nummer": project, "regels_van_mehdi": regels_mehdi, "collegas": organisatie.samenvatting(),
                       "transcript_begin": tekst[:5000]}, ensure_ascii=False)
    resp = Anthropic().messages.create(model=MODEL, max_tokens=900, system=system, messages=[{"role": "user", "content": user}],
                                       tools=[schema], tool_choice={"type": "tool", "name": "label"})
    for b in resp.content:
        if getattr(b, "type", "") == "tool_use":
            return dict(b.input), (resp.usage.input_tokens + resp.usage.output_tokens)
    return {"label": "Onbekend", "zekerheid": "laag", "reden": "model gaf geen label", "agenda_toets": "", "locatie_toets": "",
            "projectnummer": "", "vraag_aan_mehdi": "Welk label hoort bij dit gesprek?"}, 0


def transcript_van(map_):
    try:
        t = open(os.path.join(map_, "transcript.md"), encoding="utf-8").read()
    except OSError:
        return ""
    i = t.find("\n[")  # eerste tijdsregel; alles ervoor is kop
    return t[i:] if i > 0 else t


def weekoverzicht(week):
    rijen = []
    for gj in glob.glob(os.path.expanduser("~/appportal/mijnagents-data/*/**/gesprek.json"), recursive=True):
        try:
            d = json.load(open(gj, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        a = d.get("archivaris")
        if not a or a.get("week") != week:
            continue
        rijen.append((a["datum"], a["start"], os.path.basename(os.path.dirname(gj)), a))
    rijen.sort()
    regels = [f"# Labels {week}: gesprekken volgens De Archivaris", "",
              "Label op inhoud, getoetst aan agenda en locatie. Correcties: werkwijze van De Archivaris op het bord, sectie Correcties van Mehdi.", "",
              "| datum | uur | map | label | zekerheid | agenda | locatie | doelmap (nog niet actief) |", "|---|---|---|---|---|---|---|---|"]
    for datum, start, naam, a in rijen:
        regels.append(f"| {datum} | {start} | {naam[:45]} | **{a['label']}** | {a['zekerheid']} | {a.get('agenda_toets', '')[:60]} | {a.get('locatie_toets', '')[:40]} | {a.get('doelmap', '')} |")
    tel = Counter(a["label"] for *_, a in rijen)
    regels += ["", "## Telling", "", "| label | aantal |", "|---|---|"] + [f"| {k} | {v} |" for k, v in tel.most_common()] + [""]
    os.makedirs(BORDMAP, exist_ok=True)
    open(os.path.join(BORDMAP, f"Labels {week}.md"), "w", encoding="utf-8").write("\n".join(regels))
    return len(rijen)


def main():
    van = tot = None
    if "--van" in sys.argv:
        van = sys.argv[sys.argv.index("--van") + 1]
    if "--tot" in sys.argv:
        tot = sys.argv[sys.argv.index("--tot") + 1]
    vandaag = datetime.now().astimezone().strftime("%Y-%m-%d")
    tot = tot or vandaag
    van = van or (datetime.fromisoformat(tot) - timedelta(days=3)).strftime("%Y-%m-%d")
    ag.hartslag("actief", taak=f"gesprekken labelen {van} tot {tot}")
    nood = []
    try:
        ww = ag.werkwijze() or ""
        corr = correcties(ww)
        regels_mehdi = [f"{d} {u} {n} = {l}" + (f" ({r})" if r else "") for (d, u), (l, r, n) in corr.items()]
        lijst = afspraken(van, tot)
        projecten = projectadressen.index()
        gesprekken = [dict(r) for r in db().execute("select * from gesprek_log where bron in ('fathom','plaud') and datum between ? and ? order by datum, start", (van, tot))]
        gelabeld = overgeslagen = tokens = 0
        twijfel, tel, weken = [], Counter(), set()
        for g in gesprekken:
            map_ = g.get("archief") or ""
            gj = os.path.join(map_, "gesprek.json")
            if not (map_ and os.path.exists(gj)):
                # map kan hernoemd zijn (Belgische tijd, Prive): zoek op uniek
                kandidaten = [p for p in glob.glob(os.path.expanduser("~/appportal/mijnagents-data/*/**/gesprek.json"), recursive=True)
                              if g["uniek"].split(":", 1)[-1] in open(p, encoding="utf-8", errors="ignore").read()]
                if not kandidaten:
                    overgeslagen += 1
                    continue
                gj = kandidaten[0]
                map_ = os.path.dirname(gj)
            d = json.load(open(gj, encoding="utf-8"))
            sleutel = (g["datum"], g["start"])
            c = corr.get(sleutel)
            if d.get("archivaris") and not (c and d["archivaris"].get("label") != c[0]):
                overgeslagen += 1
                weken.add(d["archivaris"].get("week"))
                continue
            a = afspraak_op(g, lijst)
            loc = locatie_op(g["datum"], g["start"])
            nummer = ""
            m = re.search(r"\b((?:26|56)\d\d)\b", f"{g.get('project') or ''} {(a or {}).get('titel') or ''} {(a or {}).get('nummer') or ''}")
            if m:
                nummer = m.group(1)
            project = projecten.get(nummer, {}).get("map", "").split("/")[-1] if nummer else ""
            if c:
                uit = {"label": c[0], "zekerheid": "hoog", "reden": f"correctie van Mehdi: {c[1] or 'zonder reden'}", "agenda_toets": (a or {}).get("titel", "geen afspraak"),
                       "locatie_toets": loc or "onbekend", "projectnummer": nummer, "vraag_aan_mehdi": ""}
            else:
                uit, t_ = label_met_model(g, transcript_van(map_), a, loc, project, regels_mehdi)
                tokens += t_
            week = datetime.fromisoformat(g["datum"]).strftime("%G-W%V")
            d["archivaris"] = {**uit, "doelmap": DOEL.get(uit["label"], ""), "datum": g["datum"], "start": g["start"], "week": week,
                               "agenda_afspraak": (a or {}).get("titel", ""), "locatie": loc, "ts": datetime.now().astimezone().isoformat(), "versie": 1}
            json.dump(d, open(gj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            gelabeld += 1
            tel[uit["label"]] += 1
            weken.add(week)
            ag.log(f"{g['datum']} {g['start']}", "bevinding", f"{uit['label']} ({uit['zekerheid']}) · {(g.get('personen') or '')[:40]}",
                   f"reden: {uit['reden']}\nagenda: {uit.get('agenda_toets', '')}\nlocatie: {uit.get('locatie_toets', '')}")
            if uit["zekerheid"] == "laag" or uit["label"] == "Onbekend":
                twijfel.append(f"{g['datum']} {g['start']} {(g.get('personen') or '')[:35]} · voorstel {uit['label']} · {uit.get('vraag_aan_mehdi') or uit['reden'][:80]}")
        n_week = sum(weekoverzicht(w) for w in weken if w)
        if twijfel:
            ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"Archivaris: {len(twijfel)} gesprek(ken) waar ik twijfel",
                          "uniek": f"archivaris-twijfel:{vandaag}:{len(twijfel)}",
                          "inhoud": "Antwoord met één regel per gesprek onder 'Correcties van Mehdi' in mijn werkwijze: `- datum uur naam = label`.\n" + "\n".join("- " + t for t in twijfel)}])
        ag.log(f"{van} tot {tot}", "schrijf", f"{gelabeld} gesprekken gelabeld, {overgeslagen} al gelabeld of zonder archief, {len(twijfel)} twijfel; weekoverzicht {n_week} rijen; {tokens} tokens",
               "\n".join(f"{k}: {v}" for k, v in tel.most_common()))
        if not os.environ.get("ANTHROPIC_API_KEY"):
            nood.append({"tekst": "Geen ANTHROPIC_API_KEY in de omgeving: ik kan niet labelen", "wie": "claude-code"})
        ag.log_verstuur()
        ag.hartslag("waakt", taak="wacht op nieuwe gesprekken", detail=f"{gelabeld} gelabeld, {len(twijfel)} twijfel ({van} tot {tot})", nood=nood)
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()
