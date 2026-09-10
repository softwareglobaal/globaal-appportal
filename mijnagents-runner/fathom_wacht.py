#!/usr/bin/env python3
"""De Fathomwacht (Privé) — haalt alles uit Fathom naar onze eigen plek, herkent
wie erbij was en waarover het ging, houdt een dagelijks logboek en een
gesprekkentabel bij, en zet klaar voor de afdelingen. Werkwijze v2 (10-09-2026):
het volledige proces staat op het bord (werkwijze/fathom-wacht.md is het zaad).

Twee keer per dag (07:00, 13:00) en op verzoek via De Regisseur (agent_ronde).
Archief: FATHOM_ARCHIEF_PAD (standaard mijnagents-data/fathom op de VM; later de
privé-Dropbox van Mehdi). Nooit overschrijven, nooit verwijderen.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import bronnen  # noqa: E402
import dropbox_prive  # noqa: E402
import fathom  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "fathom-wacht"
ag = bord.Agent(NAAM)
DAGEN = int(os.environ.get("FATHOM_WACHT_DAGEN", "14"))
ARCHIEF = os.path.expanduser(os.environ.get("FATHOM_ARCHIEF_PAD", "~/appportal/mijnagents-data/fathom"))
MODEL = os.environ.get("FATHOM_WACHT_MODEL", "claude-sonnet-5")
AFDELINGEN = ("h-architects", "unabo", "harmoniebouw", "contrax", "regie", "prive")
# Kenmerken in het e-mailadres van de opnemer waaraan we Mehdi's eigen Fathom-sleutel herkennen
MEHDI_FATHOM_EIGENAARS = tuple(k.strip() for k in os.environ.get(
    "FATHOM_MEHDI_EIGENAARS", "h-architects,mch@,zoomafspraken@gmail.com").split(",") if k.strip())


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


# ----------------------------------------------------------- personen ---
def personen_uit_werkwijze(werkwijze):
    """De tabel 'Betrokken personen' uit de werkwijze op het bord: één plek."""
    uit = []
    blok = werkwijze.split("## Betrokken personen", 1)
    if len(blok) < 2:
        return uit
    for regel in blok[1].split("\n## ", 1)[0].splitlines():
        if not regel.startswith("|") or regel.startswith("|---") or regel.startswith("| Naam"):
            continue
        cellen = [c.strip() for c in regel.strip("|").split("|")]
        if len(cellen) >= 4 and cellen[0]:
            mails = [m.strip().lower() for m in re.split(r"[,;]", cellen[1]) if "@" in m]
            uit.append({"naam": cellen[0], "mails": mails, "afdeling": cellen[2], "rol": cellen[3],
                        "bijzonder": cellen[4] if len(cellen) > 4 else ""})
    return uit


def deals_index():
    d = pipedrive.get("harchitects", "/deals", {"status": "open", "limit": 500})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    uit = []
    for x in items:
        titel = x.get("title", "")
        m = re.match(r"^\s*((?:26|56)\d\d)\b", titel)
        p = x.get("person_id") if isinstance(x.get("person_id"), dict) else {}
        mails = {e.get("value", "").lower() for e in (p.get("email") or []) if isinstance(e, dict) and e.get("value")}
        uit.append({"id": x.get("id"), "titel": titel, "nummer": m.group(1) if m else "", "mails": mails,
                    "delen": {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()}})
    return uit


def koppel_deal(g, deals):
    titel = g.get("title") or g.get("meeting_title") or ""
    m = re.search(r"\b((?:26|56)\d\d)\b", titel)
    if m:
        for d in deals:
            if d["nummer"] == m.group(1):
                return d, "projectnummer in de titel"
    mails = {(i.get("email") or "").lower() for i in (g.get("calendar_invitees") or []) if isinstance(i, dict)}
    for d in deals:
        if d["mails"] & mails:
            return d, "e-mail van een deelnemer"
    delen = {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2}
    beste, score = None, 0
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score = d, s
    return (beste, f"naam in de titel ({score} woorden)") if beste and score >= 2 else (None, "")


# ------------------------------------------------------------- archief ---
def veilige_naam(t):
    return re.sub(r"[^\w\- .,()]+", "", t or "").strip()[:70] or "gesprek"


def bewaar(g, tekst, herkenning):
    start = (g.get("recording_start_time") or g.get("created_at") or "")[:16].replace("T", " ").replace(":", "")
    hoofd = herkenning.get("hoofdpersoon") or (g.get("title") or g.get("meeting_title") or "")
    map_ = os.path.join(ARCHIEF, start[:4] or "onbekend", f"{start} {veilige_naam(hoofd)}")
    if os.path.exists(os.path.join(map_, "gesprek.json")):
        return map_, False
    os.makedirs(map_, exist_ok=True)
    kop = (f"# {g.get('title') or g.get('meeting_title') or ''}\n\nFathom {g.get('recording_start_time', '')} tot "
           f"{g.get('recording_end_time', '')} · {g.get('url', '')}\nDeellink: {g.get('share_url', '')}\n"
           f"Opgenomen door: {(g.get('recorded_by') or {}).get('name', '')}\nDeelnemers: "
           + ", ".join(f"{i.get('name', '')} <{i.get('email', '')}>" for i in (g.get("calendar_invitees") or []))
           + f"\n\nHerkenning: {json.dumps(herkenning, ensure_ascii=False)}\n\n")
    open(os.path.join(map_, "transcript.md"), "w", encoding="utf-8").write(kop + tekst)
    if g.get("default_summary"):
        open(os.path.join(map_, "samenvatting.md"), "w", encoding="utf-8").write(
            "# Samenvatting van Fathom (niet als bron voor contract of verslag; het transcript telt)\n\n" + str(g["default_summary"]))
    if g.get("action_items"):
        open(os.path.join(map_, "actiepunten.md"), "w", encoding="utf-8").write(json.dumps(g["action_items"], ensure_ascii=False, indent=1))
    if g.get("highlights"):
        open(os.path.join(map_, "hoogtepunten.md"), "w", encoding="utf-8").write(json.dumps(g["highlights"], ensure_ascii=False, indent=1))
    meta = {k: v for k, v in g.items() if k != "transcript"}
    meta["herkenning"] = herkenning
    open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8").write(json.dumps(meta, ensure_ascii=False, indent=1))
    return map_, True


# ---------------------------------------------------------- herkennen ---
def herken(g, tekst, personen, deal, hoe):
    """Met het model: personen, bedrijf, afdeling, thema, project, privé. Deterministische
    voorkennis (personentabel, Pipedrive) gaat mee; het model vult aan en motiveert."""
    from anthropic import Anthropic
    deelnemers = [{"naam": i.get("name"), "email": i.get("email"), "extern": i.get("is_external")} for i in (g.get("calendar_invitees") or [])]
    bekend = []
    for d in deelnemers:
        for p in personen:
            if (d.get("email") or "").lower() in p["mails"] or (d.get("naam") and p["naam"].lower().split()[0] in (d.get("naam") or "").lower()):
                bekend.append({"deelnemer": d.get("naam") or d.get("email"), "is": p["naam"], "afdeling": p["afdeling"], "rol": p["rol"], "bijzonder": p["bijzonder"]})
    schema = {"name": "herkenning", "description": "Herkenning van het gesprek", "input_schema": {"type": "object", "properties": {
        "personen": {"type": "array", "items": {"type": "string"}}, "hoofdpersoon": {"type": "string"},
        "bedrijf": {"type": "string"}, "afdeling": {"type": "string", "enum": list(AFDELINGEN) + ["onbekend"]},
        "thema": {"type": "string"}, "project": {"type": "string"}, "prive": {"type": "boolean"},
        "zekerheid": {"type": "string", "enum": ["hoog", "middel", "laag"]}, "waarom": {"type": "string"}},
        "required": ["personen", "hoofdpersoon", "bedrijf", "afdeling", "thema", "project", "prive", "zekerheid", "waarom"]}}
    system = ("Je herkent voor Mehdi Chegini (H-Architects) een Fathom-gesprek: wie erbij was, welk bedrijf, welke afdeling "
              "(h-architects, unabo, harmoniebouw, contrax, regie, prive), thema, project of dossier, en of het privé is. "
              "Privé: alleen Mehdi en Angela (zijn partner), Mehdi alleen, of een duidelijk persoonlijk onderwerp; bij twijfel privé. "
              "Raad geen afdeling voor een onbekende externe deelnemer: dan 'onbekend' en zekerheid laag. Nederlands, kort. "
              "Motiveer in 'waarom' waarop je je baseert (deelnemer, e-mail, titel, wat er gezegd werd), zodat Mehdi je redenering kan nalezen.")
    user = json.dumps({"titel": g.get("title") or g.get("meeting_title"), "start": g.get("recording_start_time"),
                       "opgenomen_door": g.get("recorded_by"), "deelnemers": deelnemers, "herkend_uit_tabel": bekend,
                       "pipedrive_deal": ({"id": deal["id"], "titel": deal["titel"], "hoe": hoe} if deal else None),
                       "personentabel": personen, "transcript_begin": tekst[:6000]}, ensure_ascii=False)
    resp = Anthropic().messages.create(model=MODEL, max_tokens=1200, system=system, messages=[{"role": "user", "content": user}],
                                       tools=[schema], tool_choice={"type": "tool", "name": "herkenning"})
    for b in resp.content:
        if getattr(b, "type", "") == "tool_use":
            h = dict(b.input)
            h["deal_id"] = deal["id"] if deal else None
            h["koppeling"] = hoe
            return h
    return {"personen": [], "hoofdpersoon": "", "bedrijf": "", "afdeling": "onbekend", "thema": "", "project": "", "prive": True,
            "zekerheid": "laag", "waarom": "model gaf geen herkenning", "deal_id": deal["id"] if deal else None, "koppeling": hoe}


# ----------------------------------------------------------------- main ---
def main():
    ag.hartslag("actief", taak="Fathom ophalen")
    try:
        if not fathom.beschikbaar():
            ag.hartslag("fout", taak="geen Fathom-sleutel", detail="FATHOM_API_KEYS ontbreekt")
            return
        werkwijze = ag.werkwijze()
        personen = personen_uit_werkwijze(werkwijze)
        sinds = (datetime.now(timezone.utc) - timedelta(days=DAGEN)).strftime("%Y-%m-%dT%H:%M:%SZ")
        gesprekken = fathom.gesprekken(sinds, met_transcript=True)
        deals = deals_index()
        klaar, rijen, nieuw_archief, prive_n, logdag = [], [], 0, 0, {}
        for g in gesprekken:
            gid = str(g.get("recording_id") or g.get("url", "").rsplit("/", 1)[-1])
            tekst = fathom.transcript_tekst(g)
            deal, hoe = koppel_deal(g, deals)
            # herkenning alleen voor wat nog niet in het archief zit (kosten)
            al = [p for p in (os.listdir(os.path.join(ARCHIEF, (g.get("recording_start_time") or "x")[:4])) if os.path.isdir(os.path.join(ARCHIEF, (g.get("recording_start_time") or "x")[:4])) else [])
                  if os.path.exists(os.path.join(ARCHIEF, (g.get("recording_start_time") or "x")[:4], p, "gesprek.json"))
                  and json.load(open(os.path.join(ARCHIEF, (g.get("recording_start_time") or "x")[:4], p, "gesprek.json"))).get("recording_id") == g.get("recording_id")]
            if al:
                herk = json.load(open(os.path.join(ARCHIEF, (g.get("recording_start_time") or "x")[:4], al[0], "gesprek.json"))).get("herkenning", {})
                map_, nieuw = os.path.join(ARCHIEF, (g.get("recording_start_time") or "x")[:4], al[0]), False
            else:
                herk = herken(g, tekst, personen, deal, hoe)
                map_, nieuw = bewaar(g, tekst, herk)
            nieuw_archief += 1 if nieuw else 0
            start = (g.get("recording_start_time") or "")[:16]
            duur = 0
            try:
                duur = int((datetime.fromisoformat(g["recording_end_time"].replace("Z", "+00:00")) - datetime.fromisoformat(g["recording_start_time"].replace("Z", "+00:00"))).total_seconds() / 60)
            except Exception:  # noqa: BLE001
                pass
            prive = bool(herk.get("prive"))
            prive_n += 1 if prive else 0
            rij = {"uniek": f"fathom:{gid}", "datum": start[:10], "start": start[11:16], "minuten": duur,
                   "personen": ", ".join(herk.get("personen") or []), "bedrijf": herk.get("bedrijf", ""), "afdeling": herk.get("afdeling", ""),
                   "thema": herk.get("thema", ""), "project": herk.get("project", "") or (deal["titel"] if deal else ""),
                   "prive": prive, "zekerheid": herk.get("zekerheid", ""), "waarom": herk.get("waarom", ""), "archief": map_,
                   "link": g.get("url", ""), "opgenomen_door": (g.get("recorded_by") or {}).get("name", "")}
            rijen.append(rij)
            logdag.setdefault(start[:10], []).append(rij)
            # kopie naar de salesmap bij een H-A-dossier (nooit overschrijven), niet als privé
            pad = ""
            if deal and tekst and not prive:
                salesmap = bronnen.zoek_salesmap(re.sub(r"^\s*\d{4}\s+", "", deal["titel"]), deal["nummer"])
                if salesmap:
                    naam = f"{start[:10]} Fathom transcript - {veilige_naam(g.get('title') or g.get('meeting_title') or hoofd_van(herk))}.md"
                    if not any(e.get("name") == naam for e in (bronnen.lijst(f"{salesmap}/0 Fathom", recursief=False) or [])):
                        pad = bronnen.upload(f"{salesmap}/0 Fathom/{naam}", open(os.path.join(map_, "transcript.md"), "rb").read())
                        ag.log(f"gesprek {start}", "schrijf", f"kopie naar {pad} (origineel: {map_})")
                    else:
                        pad = f"{salesmap}/0 Fathom/{naam}"
            voor = "mehdi" if prive or herk.get("afdeling") in ("onbekend", "prive", "regie", "") else herk["afdeling"]
            klaar.append({"voor": voor, "soort": "transcript", "sleutel": str(deal["id"]) if deal else (herk.get("project") or ""),
                          "titel": f"{start} Fathom: {herk.get('hoofdpersoon') or g.get('title')} · {herk.get('thema', '')[:60]}" + (" · PRIVÉ" if prive else ""),
                          "uniek": f"fathom:{gid}", "verwijzing": pad or map_,
                          "inhoud": {**{k: v for k, v in rij.items() if k != "waarom"}, "waarom": herk.get("waarom", ""), "transcript_pad": pad or os.path.join(map_, "transcript.md")}})
            ag.log(f"gesprek {start}", "bevinding",
                   f"{herk.get('hoofdpersoon') or g.get('title')} · {herk.get('afdeling')} · {herk.get('thema', '')[:60]}" + (" · privé" if prive else "") + f" · zekerheid {herk.get('zekerheid')}",
                   herk.get("waarom", ""))
        # logboek per dag in het archief
        os.makedirs(os.path.join(ARCHIEF, "logboek"), exist_ok=True)
        for dag, lijst in logdag.items():
            regels = [f"# Fathom-logboek {dag}", "", f"{len(lijst)} gesprek(ken), {sum(r['minuten'] for r in lijst)} minuten", "",
                      "| start | min | personen | bedrijf | afdeling | thema | project | privé |", "|---|---|---|---|---|---|---|---|"]
            regels += [f"| {r['start']} | {r['minuten']} | {r['personen']} | {r['bedrijf']} | {r['afdeling']} | {r['thema'][:50]} | {r['project'][:40]} | {'ja' if r['prive'] else ''} |" for r in sorted(lijst, key=lambda x: x["start"])]
            open(os.path.join(ARCHIEF, "logboek", f"{dag}.md"), "w", encoding="utf-8").write("\n".join(regels) + "\n")
        # kopie van het archief naar Mehdi's eigen Dropbox (alleen wat nieuw is)
        sp = dropbox_prive.spiegel_map(ARCHIEF, "/Fathom")
        if sp["verstuurd"] or sp["fout"]:
            ag.log("Fathom", "schrijf", f"Dropbox privé: {sp['verstuurd']} bestand(en) verstuurd, {sp['rest']} nog te gaan"
                   + (f"; fout: {sp['fout']}" if sp["fout"] else ""))
        bord.call("/api/gesprekken", {"rijen": rijen})
        uit = ag.klaarzet(klaar)
        ag.log("Fathom", "bron", f"{len(gesprekken)} gesprekken sinds {sinds[:10]} van {len(fathom.sleutels())} sleutel(s); {nieuw_archief} nieuw in het archief; {prive_n} privé; {len(personen)} personen in de tabel",
               "\n".join(f"{r['datum']} {r['start']} {r['personen'][:40]} | {r['afdeling']} | {r['thema'][:50]}" for r in rijen))
        ag.log("Fathom", "schrijf", f"gesprekkentabel bijgewerkt ({len(rijen)} rijen); klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend; logboek voor {len(logdag)} dag(en)")
        ag.log_verstuur()
        nood = []
        eigenaars = {(g.get("recorded_by") or {}).get("email", "") for g in gesprekken}
        # Mehdi's Fathom-account neemt op als zoomafspraken@gmail.com (sleutel MEHDI_FATHOM_API_KEY, ook in ~/elevait/.env)
        if not any(any(kenmerk in e for kenmerk in MEHDI_FATHOM_EIGENAARS) for e in eigenaars):
            nood.append({"tekst": "Mehdi's eigen Fathom-sleutel ontbreekt op de VM (FATHOM_API_KEYS is nu van Shaniel); ik zie zijn gesprekken niet", "wie": "mehdi"})
        nood += dropbox_prive.nood(wat="het Fathom-archief")
        if any(len(p["mails"]) == 0 and "aan te vullen" in p.get("mails", []) for p in personen) or len([p for p in personen if p["mails"]]) < 6:
            nood.append({"tekst": "De tabel Betrokken personen mist e-mailadressen van collega's (dashboard van Mehdi)", "wie": "mehdi"})
        ag.hartslag("waakt", taak="wacht op nieuwe gesprekken", detail=f"laatste ronde: {len(gesprekken)} gesprekken, {nieuw_archief} nieuw, {prive_n} privé", nood=nood)
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


def hoofd_van(herk):
    return herk.get("hoofdpersoon") or "gesprek"


if __name__ == "__main__":
    main()
