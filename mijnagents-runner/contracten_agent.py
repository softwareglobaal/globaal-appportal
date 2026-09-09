#!/usr/bin/env python3
"""Contracten-agent (De Contractmaker) — Mehdi's eerste agent op mijnagents.globaal.be.

Wat hij doet, precies zoals de Werkinstructie AI op het contract-dashboard het
voorschrijft (tabblad `werkinstructie`, dat hij live leest):

  1. Pipedrive H-Architects: deals in fase "Gegevens ontvangen" (stage 34).
  2. Per deal: voorbereiding_starten -> voorbereiding lezen -> dossiercontrole.
  3. Een taalmodel maakt op basis daarvan (plus de Pipedrive-notities) een plan:
     welke gegevens met welke bron, welke keuzes, de projectbeschrijving, en de
     melding voor Mehdi. Het model rekent niets zelf uit dat het systeem levert
     (perceel, CaPaKey, rijksregister) en overschrijft niets wat bevestigd is.
  4. Het plan wordt deterministisch toegepast: gegeven_invullen (met bron),
     keuze_maken, dan proef_maken.
  5. Melding als notitie op de Pipedrive-deal, in de vaste vijfdelige vorm.
  6. Ontbreekt het projectnummer in de dealtitel, dan komt een voorstel op het
     agentbord (runbook pipedrive-dealtitel); Mehdi keurt goed, de uitvoerder zet het.

Grenzen: nooit een definitief contract (Onderteken is Mehdi's klik), nooit
versturen, nooit een bestand opladen. Op het agentbord alleen werkstatus.
Draait op de host via cron. Staat in mijnagents-data/contracten-agent.json.
"""
import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import contracten_mcp as mcp  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "contracten-agent"
FIRMA = "harchitects"
STARTFASE = int(os.environ.get("CONTRACTEN_AGENT_FASE", "34"))       # Gegevens ontvangen
PIJPLIJN = int(os.environ.get("CONTRACTEN_AGENT_PIJPLIJN", "1"))     # B2C: H-Architects prospecties
MODEL = os.environ.get("CONTRACTEN_AGENT_MODEL", "claude-opus-5")
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3022")
STAAT_PAD = os.path.expanduser("~/appportal/mijnagents-data/contracten-agent.json")
HERRONDE_UREN = 24
DROOG = "--droog" in sys.argv          # alleen plannen, niets schrijven
ALLEEN = None                          # --deal 14474: alleen die deal
for i, a in enumerate(sys.argv):
    if a == "--deal" and i + 1 < len(sys.argv):
        ALLEEN = int(sys.argv[i + 1])


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/agents/.env")                        # ANTHROPIC_API_KEY


def _token_van_dit_bord():
    """AGENTS_TOKEN expliciet uit mijnagents-data/.env. Niet via setdefault: de
    gedeelde ~/appportal/.env (al geladen door de koppelingen) draagt het token
    van de operations-tegel onder dezelfde naam, en dat is een ander bord."""
    try:
        for regel in open(os.path.expanduser("~/appportal/mijnagents-data/.env")):
            if regel.startswith("AGENTS_TOKEN="):
                return regel.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return os.environ.get("AGENTS_TOKEN", "")


TOKEN = _token_van_dit_bord()


# ------------------------------------------------------------- agentbord ---
def hartslag(status, taak="", detail="", voorstel=None):
    payload = {"naam": NAAM, "status": status, "taak": taak, "detail": detail}
    if voorstel:
        payload["voorstel"] = voorstel
    req = urllib.request.Request(f"{PLATFORM}/agent-status", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json", "X-Agents-Token": TOKEN},
                                 method="POST")
    try:
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:  # noqa: BLE001
        print("hartslag mislukt:", e, file=sys.stderr)


# ----------------------------------------------------------------- staat ---
def laad_staat():
    try:
        return json.load(open(STAAT_PAD))
    except (OSError, ValueError):
        return {}


def bewaar_staat(s):
    os.makedirs(os.path.dirname(STAAT_PAD), exist_ok=True)
    json.dump(s, open(STAAT_PAD, "w"), indent=1, ensure_ascii=False)


def uren_sinds(iso):
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(iso)).total_seconds() / 3600
    except Exception:  # noqa: BLE001
        return 1e9


# -------------------------------------------------------------- bronnen ---
def deals_in_startfase():
    d = pipedrive.get(FIRMA, "/deals", {"status": "open", "stage_id": STARTFASE, "limit": 100})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    return [x for x in items if int(x.get("pipeline_id") or PIJPLIJN) == PIJPLIJN]


def notities(deal_id):
    d = pipedrive.get(FIRMA, "/notes", {"deal_id": deal_id, "limit": 100})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    uit = []
    for n in sorted(items, key=lambda x: x.get("add_time", "")):
        tekst = re.sub(r"<[^>]+>", " ", n.get("content") or "")
        tekst = re.sub(r"\s+", " ", tekst).strip()
        if tekst:
            uit.append(f"[{(n.get('add_time') or '')[:10]}] {tekst}")
    return uit


def nummer_uit_titel(titel):
    m = re.match(r"^\s*((?:26|56)\d\d)\b", titel or "")
    return m.group(1) if m else ""


def volgend_vrij_nummer(reeks="26"):
    gebruikt = set()
    try:
        for d in (mcp.call("dossiers", limiet=500) or {}).get("dossiers", []):
            n = str(d.get("project_nummer") or d.get("nummer") or "")
            if n.startswith(reeks):
                gebruikt.add(n)
    except Exception:  # noqa: BLE001
        pass
    try:
        for d in (mcp.call("voorbereidingen") or {}).get("dossiers", []):
            n = str(d.get("nummer") or "")
            if n.startswith(reeks):
                gebruikt.add(n)
    except Exception:  # noqa: BLE001
        pass
    for status in ("open", "won", "lost"):
        d = pipedrive.get(FIRMA, "/deals", {"status": status, "limit": 500})
        for x in (d if isinstance(d, list) else (d or {}).get("data") or []):
            n = nummer_uit_titel(x.get("title", ""))
            if n.startswith(reeks):
                gebruikt.add(n)
    hoogste = max((int(n) for n in gebruikt), default=int(reeks + "00"))
    return str(hoogste + 1)


# ------------------------------------------------------------ taalmodel ---
SCHEMA_UITLEG = """Antwoord met UITSLUITEND een JSON-object met deze sleutels:
{
 "gegevens": [ {"velden": {"veldnaam": "waarde", ...}, "bron": "bv. 'Pipedrive-notitie 14-10-2023' of 'mail van de klant 02-09-2026'"} ],
 "keuzes": {"veld": "waarde", ...},
 "nummer_voorstel": "26xx of null",
 "melding": {
   "vastligt": ["... (met bron)"],
   "nakijken": ["... (afgeleid, waarom)"],
   "keuzes_vastgelegd": ["..."],
   "ontbreekt": ["... en wie het moet leveren"],
   "volgende_stap": "één zin voor Mehdi"
 }
}
Regels die je nooit breekt:
- Vul alleen velden in die in 'voorbereiding' bestaan (velden, vrije velden, keuzes met hun toegelaten waarden).
- Bereken of schat NOOIT capa_key_code, project_capakey, oppervlakte_m2, project_oppervlakte_terrein of een rijksregisternummer; laat die leeg als ze ontbreken en zet ze bij 'ontbreekt'.
- Overschrijf nooit een veld dat als bevestigd door de klant of vastgelegd door Mehdi staat.
- Elke 'gegevens'-post heeft een concrete bron met datum. Geen bron = niet invullen, wel melden.
- Bedragen als '50.000,00'; percentages als getal ('14').
- project_beschrijving volgens de vaste opbouw uit de Werkinstructie (per ruimte, chronologisch, wat de architect doet en wat de klant zelf doet, 'Het project omvat niet'), alleen uit de gesprekken en notities die je kreeg.
- Geef 'nummer_voorstel' alleen als de dealtitel géén 26xx/56xx-nummer heeft; gebruik dan het aangereikte volgende vrije nummer.
- Is er niets te doen, geef lege lijsten/objecten en zeg dat in 'volgende_stap'.
"""


def plan_met_model(werkinstructie, deal, voorbereiding, controle, notitielijst, vrij_nummer):
    from anthropic import Anthropic
    client = Anthropic()
    system = ("Je bent de contracten-agent van H-Architects. Je werkt volgens de Werkinstructie "
              "hieronder (het tabblad op contracten.globaal.be) en levert een plan dat een "
              "deterministisch script uitvoert via de dashboard-tools.\n\n=== WERKINSTRUCTIE ===\n"
              + werkinstructie + "\n\n=== UITVOERFORMAAT ===\n" + SCHEMA_UITLEG)
    user = json.dumps({
        "deal": {"id": deal.get("id"), "titel": deal.get("title"), "waarde": deal.get("value"),
                 "persoon": (deal.get("person_id") or {}).get("name") if isinstance(deal.get("person_id"), dict) else deal.get("person_name"),
                 "organisatie": (deal.get("org_id") or {}).get("name") if isinstance(deal.get("org_id"), dict) else deal.get("org_name")},
        "volgend_vrij_nummer": vrij_nummer,
        "voorbereiding": voorbereiding,
        "dossiercontrole": controle,
        "pipedrive_notities": notitielijst,
    }, ensure_ascii=False)
    # Gedwongen tool-aanroep: het plan komt als gevalideerde JSON binnen, nooit
    # als vrije tekst (een lange projectbeschrijving brak het los parsen).
    plan_tool = {
        "name": "plan",
        "description": "Het plan voor dit dossier, in het uitvoerformaat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "gegevens": {"type": "array", "items": {"type": "object", "properties": {
                    "velden": {"type": "object"}, "bron": {"type": "string"}},
                    "required": ["velden", "bron"]}},
                "keuzes": {"type": "object"},
                "nummer_voorstel": {"type": ["string", "null"]},
                "melding": {"type": "object", "properties": {
                    "vastligt": {"type": "array", "items": {"type": "string"}},
                    "nakijken": {"type": "array", "items": {"type": "string"}},
                    "keuzes_vastgelegd": {"type": "array", "items": {"type": "string"}},
                    "ontbreekt": {"type": "array", "items": {"type": "string"}},
                    "volgende_stap": {"type": "string"}},
                    "required": ["vastligt", "nakijken", "keuzes_vastgelegd", "ontbreekt", "volgende_stap"]},
            },
            "required": ["gegevens", "keuzes", "nummer_voorstel", "melding"],
        },
    }
    resp = client.messages.create(model=MODEL, max_tokens=8000, system=system,
                                  messages=[{"role": "user", "content": user}],
                                  tools=[plan_tool], tool_choice={"type": "tool", "name": "plan"})
    plan = None
    for b in resp.content:
        if getattr(b, "type", "") == "tool_use" and b.name == "plan":
            plan = dict(b.input)
    if plan is None:
        raise RuntimeError("model gaf geen plan terug")
    # Soms verpakt het model het hele plan in één extra sleutel (bv. "velden");
    # dan uitpakken. Een plan zonder melding is onbruikbaar: liever een fout op
    # het bord dan een lege notitie op de deal.
    if "melding" not in plan and len(plan) == 1 and isinstance(next(iter(plan.values())), dict):
        plan = dict(next(iter(plan.values())))
    if not isinstance(plan.get("melding"), dict) or not plan["melding"].get("vastligt", None) and not plan["melding"].get("volgende_stap"):
        raise RuntimeError("plan zonder bruikbare melding; niets geschreven")
    tokens = (getattr(resp.usage, "input_tokens", 0) or 0) + (getattr(resp.usage, "output_tokens", 0) or 0)
    return plan, tokens


# -------------------------------------------------------------- melding ---
def melding_tekst(plan, proef, nummer_voorstel):
    m = plan.get("melding") or {}
    def blok(kop, items):
        items = [str(x) for x in (items or []) if str(x).strip()]
        return f"<b>{kop}</b><br>" + ("<br>".join("- " + x for x in items) if items else "- (niets)") + "<br><br>"
    uit = "<b>Contracten-agent</b> — " + datetime.now().strftime("%d-%m-%Y %H:%M") + "<br><br>"
    uit += blok("1. Vastgelegd, met bron", m.get("vastligt"))
    uit += blok("2. Afgeleid, na te kijken", m.get("nakijken"))
    uit += blok("3. Keuzes die ik voor je vastlegde", m.get("keuzes_vastgelegd"))
    ontbreekt = list(m.get("ontbreekt") or [])
    if nummer_voorstel:
        ontbreekt.append(f"Projectnummer: voorstel {nummer_voorstel} staat op het agentbord ter goedkeuring")
    uit += blok("4. Ontbreekt, en wie het levert", ontbreekt)
    proeftekst = f"Proef gemaakt: {proef}" if proef else "Nog geen proef: het dossier is niet volledig (zie 4)."
    uit += f"<b>5. Proef en volgende klik</b><br>- {proeftekst}<br>- {m.get('volgende_stap', '')}<br>"
    uit += "<br><i>Nakijken en ondertekenen op contracten.globaal.be (In voorbereiding).</i>"
    return uit


# ---------------------------------------------------------------- werk ---
def verwerk(deal, werkinstructie, staat):
    deal_id = int(deal["id"])
    titel = deal.get("title", "")
    nummer = nummer_uit_titel(titel)
    print(f"--- deal {deal_id} '{titel}'")

    start = mcp.call("voorbereiding_starten", deal_id=deal_id) if not DROOG else {"droog": True}
    voorb = mcp.call("voorbereiding", deal_id=deal_id) if not DROOG else None
    if voorb is None:
        # droog: alleen lezen als hij al bestaat
        try:
            voorb = mcp.call("voorbereiding", deal_id=deal_id)
        except mcp.ToolFout as e:
            print("  (droog) niet in voorbereiding:", str(e)[:100])
            voorb = {"deal_id": deal_id, "let_op": "nog niet in voorbereiding"}
    controle = mcp.call("dossiercontrole", deal_id=deal_id)
    vrij = "" if nummer else volgend_vrij_nummer("26")
    plan, tokens = plan_met_model(werkinstructie, deal, voorb, controle, notities(deal_id), vrij)
    print("  plan:", json.dumps(plan, ensure_ascii=False)[:1200])
    if DROOG:
        return {"droog": True, "plan": plan}

    # toepassen, deterministisch
    fouten = []
    for post in plan.get("gegevens") or []:
        velden, bron = post.get("velden") or {}, (post.get("bron") or "").strip()
        verboden = {"capa_key_code", "project_capakey", "oppervlakte_m2", "project_oppervlakte_terrein",
                    "opdrachtgever_1_rijksregister", "opdrachtgever_2_rijksregister", "vertegenwoordiger_rijksregister"}
        velden = {k: v for k, v in velden.items() if k not in verboden and str(v).strip()}
        if not velden or not bron:
            continue
        try:
            mcp.call("gegeven_invullen", deal_id=deal_id, velden=velden, bron=bron)
        except mcp.ToolFout as e:
            fouten.append(f"gegeven_invullen {list(velden)}: {str(e)[:160]}")
    keuzes = {k: v for k, v in (plan.get("keuzes") or {}).items() if str(v).strip()}
    if keuzes:
        try:
            mcp.call("keuze_maken", deal_id=deal_id, keuzes=keuzes)
        except mcp.ToolFout as e:
            fouten.append(f"keuze_maken: {str(e)[:200]}")
    proef = ""
    try:
        p = mcp.call("proef_maken", deal_id=deal_id)
        proef = p.get("docx", "") if isinstance(p, dict) else ""
    except mcp.ToolFout as e:
        fouten.append(f"proef: {str(e)[:200]}")

    nummer_voorstel = plan.get("nummer_voorstel") if not nummer else None
    if nummer_voorstel and str(nummer_voorstel).lower() != "null":
        klant = re.sub(r"^\s*\d{4}\s+", "", titel).strip() or "klant"
        hartslag("waakt", taak="projectnummer ter goedkeuring", detail=f"deal {deal_id}",
                 voorstel={"actie": f"Projectnummer {nummer_voorstel} toekennen aan deal {deal_id}",
                           "doel": f"deal {deal_id}", "reden": "dealtitel zonder 26xx-nummer (D9)",
                           "runbook": "pipedrive-dealtitel",
                           "parameters": {"deal_id": deal_id, "titel": f"{nummer_voorstel} {klant}"}})
    else:
        nummer_voorstel = None

    if fouten:
        m = plan.setdefault("melding", {})
        m.setdefault("ontbreekt", []).extend(fouten)
    tekst = melding_tekst(plan, proef, nummer_voorstel)
    pipedrive.schrijf(FIRMA, "POST", "/notes", body={"deal_id": deal_id, "content": tekst})

    # Stempel van het dossier ná onze eigen schrijfacties: wijzigt Mehdi daarna
    # iets op het dashboard (bv. de scope kiezen), dan verschilt de stempel en
    # pakt de volgende ronde de deal meteen opnieuw op, ook binnen de 24 uur.
    try:
        stempel = vingerafdruk(mcp.call("voorbereiding", deal_id=deal_id))
    except Exception:  # noqa: BLE001
        stempel = ""
    staat[str(deal_id)] = {"laatst": datetime.now(timezone.utc).isoformat(), "proef": proef,
                           "fouten": len(fouten), "tokens": tokens, "nummer_voorstel": nummer_voorstel,
                           "stempel": stempel}
    return {"proef": proef, "fouten": fouten}


def vingerafdruk(voorb):
    """Stabiele vingerafdruk van de inhoud van het dossier in voorbereiding:
    de velden (zonder de dagdatum) en de gekozen keuzes. Geen tijdstempel, want
    'voorbereiding' levert die niet en onze eigen ronde mag niet tellen."""
    if not isinstance(voorb, dict):
        return ""
    velden = {k: v for k, v in (voorb.get("velden") or {}).items() if k != "datum_vandaag"}
    keuzes = {k.get("veld"): k.get("gekozen") for k in (voorb.get("keuzes") or []) if isinstance(k, dict)}
    return hashlib.sha256(json.dumps([velden, keuzes, voorb.get("soort")], sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()[:16]


def dossier_gewijzigd(deal_id, s):
    """True als het dossier in voorbereiding sinds onze laatste ronde veranderde.
    Zonder bruikbare stempel: NIET opnieuw doen (de 24-uursregel geldt dan),
    anders zou elke ronde dezelfde deal opnieuw verwerken en een notitie zetten."""
    if not s or not s.get("stempel"):
        return False
    try:
        return vingerafdruk(mcp.call("voorbereiding", deal_id=deal_id)) != s["stempel"]
    except Exception:  # noqa: BLE001
        return False


def main():
    if not TOKEN:
        print("FOUT: geen AGENTS_TOKEN", file=sys.stderr)
        return
    hartslag("actief", taak="ronde gestart", detail="Pipedrive fase Gegevens ontvangen nakijken")
    try:
        werk = mcp.call("dashboard_document", sleutel="werkinstructie")
        werkinstructie = werk.get("markdown", "") if isinstance(werk, dict) else str(werk)
        deals = deals_in_startfase()
        if ALLEEN:
            deals = [d for d in deals if int(d["id"]) == ALLEEN] or [pipedrive.get(FIRMA, f"/deals/{ALLEEN}")]
            deals = [d.get("data", d) if isinstance(d, dict) else d for d in deals]
        staat = laad_staat()
        gedaan, overgeslagen, proeven = 0, 0, 0
        for deal in deals:
            s = staat.get(str(deal["id"]))
            if (s and uren_sinds(s.get("laatst", "")) < HERRONDE_UREN and not ALLEEN
                    and not dossier_gewijzigd(int(deal["id"]), s)):
                overgeslagen += 1
                continue
            uit = verwerk(deal, werkinstructie, staat)
            gedaan += 1
            proeven += 1 if uit.get("proef") else 0
            if not DROOG:
                bewaar_staat(staat)
        hartslag("waakt", taak="wacht op nieuwe dossiers",
                 detail=f"laatste ronde: {len(deals)} in fase, {gedaan} verwerkt, {proeven} proef/proeven, {overgeslagen} recent al gedaan")
        print(f"klaar: {gedaan} verwerkt, {proeven} proeven, {overgeslagen} overgeslagen")
    except Exception as e:  # noqa: BLE001
        hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:150]}")
        raise


if __name__ == "__main__":
    main()
