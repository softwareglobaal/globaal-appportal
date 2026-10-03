#!/usr/bin/env python3
"""De Regisseur — Mehdi's hoofdagent op mijnagents.globaal.be.

Mehdi zegt iets op het bord (aan de Regisseur of aan een agent); deze runner
haalt elke minuut de open berichten op, laat het model antwoorden met
gereedschap dat alleen leest of voorstelt, en zet het antwoord terug op het
bord. Praten met een agent = de Regisseur antwoordt in de rol van die agent,
met diens werkwijze, kennis en werkverslag.

Wat hij kan: alle agents lezen (werkwijze, kennis, status, werkverslag,
voorstellen), het contract-dashboard lezen (alleen leestools), Pipedrive lezen,
een agent een ronde laten draaien, en een voorstel op het bord zetten voor
alles wat iets verandert (ook een wijziging van een werkwijze). Hij voert zelf
niets muterends uit; dat doet de uitvoerder na Mehdi's goedkeuring.
"""
import fcntl
import json
import os
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import contracten_mcp as mcp  # noqa: E402
import pipedrive  # noqa: E402
import taken  # noqa: E402

NAAM = "regisseur"
MODEL = os.environ.get("REGISSEUR_MODEL", "claude-opus-5")
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3022")
MAX_RONDES = 10
DASHBOARD_LEES = {"overzicht", "dossiers", "dossier", "openstaand", "dossiercontrole", "voorbereidingen",
                  "voorbereiding", "veldenschema", "masters", "documenten", "kantoorgegevens", "zoek",
                  "dashboard_documenten", "dashboard_document"}
RUNNERS = {n: os.path.join(HIER, s) for n, s in {
    "contracten-agent": "contracten_agent.py", "agenda-wacht": "agenda_wacht.py", "fathom-wacht": "fathom_wacht.py",
    "plaud-wacht": "plaud_wacht.py", "dagbundelaar": "dagbundelaar.py", "locatie-wacht": "locatie_wacht.py",
    "ontwikkelaar": "ontwikkelaar.py", "levenscoach": "levenscoach.py", "bode": "bode.py"}.items()}
# icloud-wacht draait op de Mac (launchd), niet hier.
# De database van het bord, alleen gelezen: zo leest de Regisseur een voorstel terug voor hij succes meldt (A10)
BORD_DB = os.environ.get("BORD_DB", os.path.expanduser("~/appportal/mijnagents-data/mijnagents.db"))
TAKEN_SLOT = os.path.expanduser("~/appportal/mijnagents-data/taken.slot")


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


def _token():
    try:
        for regel in open(os.path.expanduser("~/appportal/mijnagents-data/.env")):
            if regel.startswith("AGENTS_TOKEN="):
                return regel.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


TOKEN = _token()


def bord(pad, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{PLATFORM}{pad}", data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json", "X-Agents-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def hartslag(status, taak="", detail="", voorstel=None):
    p = {"naam": NAAM, "status": status, "taak": taak, "detail": detail}
    if voorstel:
        p["voorstel"] = voorstel
    try:
        bord("/agent-status", p)
    except Exception as e:  # noqa: BLE001
        print("hartslag mislukt:", e, file=sys.stderr)


# ------------------------------------------------------------ gereedschap ---
TOOLS = [
    {"name": "agents_overzicht", "description": "ALLE agents op het bord (kort): afdeling, rol, cadans, status met taak, detail en tijdstip, "
                                                "en aantal open voorstellen. Volledig, dus dit is de lijst waarop je je uitspraken over de "
                                                "toestand baseert. Mandaat, grenzen, gereedschap en werkwijze staan er niet in: haal die per "
                                                "agent op met agent_werkwijze.",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "agent_werkwijze", "description": "De volledige werkwijze (het proces) van een agent, zoals Mehdi hem op het bord vastlegde.",
     "input_schema": {"type": "object", "properties": {"naam": {"type": "string"}}, "required": ["naam"]}},
    {"name": "agent_verslag", "description": "Het werkverslag van een agent: wat hij las, vond, besliste en schreef. Optioneel gefilterd op onderwerp (bv. een dealnummer).",
     "input_schema": {"type": "object", "properties": {"naam": {"type": "string"}, "onderwerp": {"type": "string"}, "n": {"type": "integer"}}, "required": ["naam"]}},
    {"name": "dashboard", "description": f"Een LEESTOOL van het contract-dashboard aanroepen. Toegelaten: {', '.join(sorted(DASHBOARD_LEES))}.",
     "input_schema": {"type": "object", "properties": {"tool": {"type": "string"}, "argumenten": {"type": "object"}}, "required": ["tool"]}},
    {"name": "pipedrive_lees", "description": "GET op de Pipedrive-API van H-Architects, bv. pad '/deals/14474' of '/deals' met params {'status':'open','stage_id':34}. Alleen lezen.",
     "input_schema": {"type": "object", "properties": {"pad": {"type": "string"}, "params": {"type": "object"}}, "required": ["pad"]}},
    {"name": "agent_ronde", "description": "Laat een agent nu een ronde draaien, optioneel voor één deal (contracten-agent: deal_id). Duurt tot enkele minuten; geeft de laatste regels van zijn uitvoer terug.",
     "input_schema": {"type": "object", "properties": {"naam": {"type": "string"}, "deal_id": {"type": "integer"}, "dag": {"type": "string"}, "droog": {"type": "boolean"}}, "required": ["naam"]}},
    {"name": "voorstel", "description": "Zet een voorstel op het bord dat Mehdi moet goedkeuren vóór het uitgevoerd wordt. Runbooks: 'werkwijze-bijwerken' (parameters: agent, werkwijze = de volledige nieuwe tekst), 'pipedrive-dealtitel' (deal_id, titel), 'notitie' (tekst). Zonder runbook is het een signaal. Geeft het voorstel-ID terug zoals het bord het bewaarde; zonder ID staat er niets.",
     "input_schema": {"type": "object", "properties": {"actie": {"type": "string"}, "reden": {"type": "string"}, "runbook": {"type": "string"}, "parameters": {"type": "object"}}, "required": ["actie", "reden"]}},
    {"name": "taak_plannen", "description": "Leg een toezegging voor later vast als taak: een agent een ronde laten draaien op een moment in de toekomst "
                                            "(bv. agenda-wacht met dag, acht dagen voor een afspraak). Geeft het taak-ID terug zoals het opgeslagen "
                                            "is. Hangt de taak aan een afspraak, geef dan kalender en afspraak-id mee: verplaatst de afspraak, dan "
                                            "volgt de taak; geschrapt, dan vervalt ze. 'wanneer' in Brusselse tijd (JJJJ-MM-DDTHH:MM) of met tijdzone.",
     "input_schema": {"type": "object", "properties": {"agent": {"type": "string"}, "wanneer": {"type": "string"}, "reden": {"type": "string"},
                                                       "dag": {"type": "string"}, "deal_id": {"type": "integer"}, "droog": {"type": "boolean"},
                                                       "afspraak_kalender": {"type": "string"}, "afspraak_id": {"type": "string"},
                                                       "afspraak_dag": {"type": "string"}, "toestemming": {"type": "string"}},
                      "required": ["agent", "wanneer", "reden"]}},
    {"name": "taken_lijst", "description": "De opgeslagen taken (open en recent), met ID, uitvoertijd, status, pogingen en bewijs. Alleen lezen.",
     "input_schema": {"type": "object", "properties": {"agent": {"type": "string"}, "alleen_open": {"type": "boolean"}}}},
]


# Het volledige overzicht is ~190 KB (werkwijze, mandaat en gereedschap per agent) en werd
# afgekapt op de 60 KB van een toolresultaat: de Regisseur zag dan maar de eerste vier agents
# en sprak over "de andere drie". Daarom dunnen we het hier uit tot wat een overzicht nodig
# heeft; het zware werk per agent haalt hij met agent_werkwijze en agent_verslag.
OVERZICHT_VELDEN = ("naam", "label", "type", "cadans", "rol", "status", "open_voorstellen", "nood")


def voer_tool_uit(naam, inp):
    if naam == "agents_overzicht":
        uit = bord("/api/overzicht")
        agents = [{k: a.get(k) for k in OVERZICHT_VELDEN if a.get(k) not in (None, "", [])}
                  for a in uit.get("agents") or []]
        return {"agents": agents, "aantal": len(agents)}
    if naam == "agent_werkwijze":
        return bord(f"/api/agent/{inp['naam']}/werkwijze")
    if naam == "agent_verslag":
        q = f"?n={int(inp.get('n') or 60)}" + (f"&onderwerp={urllib.request.quote(inp['onderwerp'])}" if inp.get("onderwerp") else "")
        return bord(f"/api/logboek/{inp['naam']}{q}")
    if naam == "dashboard":
        if inp["tool"] not in DASHBOARD_LEES:
            return {"fout": f"'{inp['tool']}' is geen leestool; alleen {sorted(DASHBOARD_LEES)}"}
        try:
            return mcp.call(inp["tool"], **(inp.get("argumenten") or {}))
        except mcp.ToolFout as e:
            return {"fout": str(e)[:500]}
    if naam == "pipedrive_lees":
        return pipedrive.get("harchitects", inp["pad"], inp.get("params") or {})
    if naam == "agent_ronde":
        script = RUNNERS.get(inp["naam"])
        if not script:
            return {"fout": f"geen runner bekend voor '{inp['naam']}'"}
        cmd = [os.path.expanduser("~/agents/.venv/bin/python"), script]
        if inp.get("deal_id"):
            cmd += ["--deal", str(int(inp["deal_id"]))]
        if inp.get("dag"):
            cmd += ["--dag", str(inp["dag"])[:10]]
        if inp.get("droog"):
            cmd.append("--droog")
        uit = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        return {"exit": uit.returncode, "uitvoer": (uit.stdout + uit.stderr)[-3000:]}
    if naam == "voorstel":
        v = {"actie": inp["actie"][:200], "reden": inp.get("reden", "")[:400], "doel": "",
             "runbook": inp.get("runbook", ""), "parameters": inp.get("parameters") or None}
        # Niet via hartslag(): die slikt een fout in, en dan meldde deze tool toch 'staat op het bord' (audit A10)
        try:
            bord("/agent-status", {"naam": NAAM, "status": "waakt", "taak": "voorstel voor Mehdi",
                                   "detail": inp["actie"][:100], "voorstel": v})
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "fout": f"het bord nam het voorstel niet aan ({type(e).__name__}); er staat niets"}
        terug = voorstel_terug(v)
        if not terug:
            return {"ok": False, "fout": "het voorstel is niet terug te vinden op het bord; er staat niets"}
        return {"ok": True, "voorstel_id": terug["id"], "status": terug["status"],
                "boodschap": f"voorstel {terug['id']} staat op het bord ({terug['status']})"}
    if naam == "taak_plannen":
        params = {"naam": inp["agent"]}
        for k in ("dag", "deal_id", "droog"):
            if inp.get(k) not in (None, ""):
                params[k] = inp[k]
        if inp["agent"] not in RUNNERS:
            return {"ok": False, "fout": f"geen runner bekend voor '{inp['agent']}'"}
        try:
            t = taken.plannen("agent_ronde", inp["agent"], params, inp["wanneer"], reden=inp.get("reden", ""),
                              toestemming=inp.get("toestemming", ""), bron="regisseur",
                              afspraak_kalender=inp.get("afspraak_kalender", ""), afspraak_id=inp.get("afspraak_id", ""),
                              afspraak_dag=inp.get("afspraak_dag", "") or inp.get("dag", ""))
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "fout": f"taak niet opgeslagen ({type(e).__name__}: {str(e)[:200]})"}
        return {"ok": True, "taak_id": t["id"], "uitvoeren_op": t["brussel"], "status": t["status"]}
    if naam == "taken_lijst":
        rijen = taken.lijst(status=taken.OPEN if inp.get("alleen_open") else None, agent=inp.get("agent"))
        return {"taken": [{k: r[k] for k in ("id", "agent", "soort", "parameters", "reden", "brussel", "status", "pogingen", "bewijs")}
                          for r in rijen]}
    return {"fout": f"onbekend gereedschap {naam}"}


def voorstel_terug(v):
    """Leest het voorstel terug uit de database van het bord (alleen lezen): id en status, of None."""
    try:
        c = sqlite3.connect(f"file:{BORD_DB}?mode=ro", uri=True, timeout=10)
        r = c.execute("SELECT id, status FROM voorstel WHERE naam=? AND actie=? AND runbook=? AND COALESCE(parameters,'')=? "
                      "ORDER BY id DESC LIMIT 1", (NAAM, v["actie"], v.get("runbook", ""),
                                                   json.dumps(v["parameters"]) if v.get("parameters") else "")).fetchone()
        c.close()
        return {"id": r[0], "status": r[1]} if r else None
    except sqlite3.Error:
        return None


def afspraak_nu(kalender, aid):
    """De afspraak zoals Google ze nu kent: ('weg', None), ('er', 'JJJJ-MM-DD') of ('onbekend', fout)."""
    import agenda  # noqa: PLC0415
    url = f"{agenda.API}/calendars/{urllib.parse.quote(kalender, safe='')}/events/{urllib.parse.quote(aid, safe='')}"
    try:
        req = urllib.request.Request(url, headers={"Authorization": "Bearer " + agenda._toegang()})
        ev = json.load(urllib.request.urlopen(req, timeout=30))
    except urllib.error.HTTPError as e:
        return ("weg", None) if e.code in (404, 410) else ("onbekend", f"HTTP {e.code}")
    except Exception as e:  # noqa: BLE001
        return ("onbekend", type(e).__name__)
    if ev.get("status") == "cancelled":
        return ("weg", None)
    s = ev.get("start") or {}
    return ("er", (s.get("dateTime") or s.get("date") or "")[:10])


def taken_uitvoeren(nu=None):
    """Voert de taken uit waarvan het moment gekomen is, een tegelijk (slot). Hangt een taak aan een afspraak, dan eerst
    herbeoordelen: geschrapt -> vervallen; verplaatst -> de dag volgt. Geslaagd heet pas 'geverifieerd' met exitcode 0
    en de uitvoer als bewijs; anders een nieuwe poging later, tot het maximum (audit A9)."""
    try:
        slot = open(TAKEN_SLOT, "w")
        fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return []
    gedaan = []
    for t in taken.te_doen(nu):
        p = dict(t["parameters"])
        if t["afspraak_kalender"] and t["afspraak_id"]:
            staat, dag = afspraak_nu(t["afspraak_kalender"], t["afspraak_id"])
            if staat == "weg":
                taken.zet(t["id"], "vervallen", "de afspraak is geschrapt; niets uitgevoerd", nu=nu)
                gedaan.append((t["id"], "vervallen"))
                continue
            if staat == "onbekend":
                taken.zet(t["id"], "wacht-op-bron", f"afspraak niet te lezen ({dag}); later opnieuw", poging=True, nu=nu)
                gedaan.append((t["id"], "wacht-op-bron"))
                continue
            if dag and dag != t["afspraak_dag"]:
                if p.get("dag"):
                    p["dag"] = dag
                taken.zet(t["id"], "gepland", f"afspraak verplaatst van {t['afspraak_dag']} naar {dag}; de taak volgt",
                          parameters=p, afspraak_dag=dag, nu=nu)
        taken.zet(t["id"], "bezig", "gestart", nu=nu)
        try:
            uit = voer_tool_uit("agent_ronde", p)
        except Exception as e:  # noqa: BLE001
            uit = {"exit": -1, "uitvoer": f"{type(e).__name__}: {str(e)[:300]}"}
        if uit.get("exit") == 0:
            taken.zet(t["id"], "geverifieerd", f"exit 0\n{uit.get('uitvoer', '')[-1500:]}", nu=nu)
            gedaan.append((t["id"], "geverifieerd"))
        else:
            n = taken.zet(t["id"], "gepland", f"exit {uit.get('exit')}\n{(uit.get('uitvoer') or uit.get('fout') or '')[-1500:]}", poging=True, nu=nu)
            gedaan.append((t["id"], n["status"]))
    return gedaan


# ------------------------------------------------------------- antwoorden ---
def antwoord(gesprek, eerder, werkwijze_regisseur):
    from anthropic import Anthropic
    client = Anthropic()
    aan = gesprek["aan"]
    rol = ("Je antwoordt als De Regisseur, de hoofdagent." if aan == "regisseur" else
           f"Mehdi spreekt de agent '{aan}' aan. Die naam staat vast: het bord kent hem en weigert "
           f"onbekende namen, dus corrigeer of vervang '{aan}' nooit, ook niet als een andere agent erop "
           f"lijkt. Antwoord in de ik-vorm namens die agent, op basis van "
           f"zijn werkwijze, kennis en werkverslag (haal die eerst op met agent_werkwijze en agent_verslag).")
    system = (
        "Je bent De Regisseur, de hoofdagent op het agentbord van Mehdi Chegini (H-Architects). "
        "Nederlands, geen emoji, geen kastlijntjes; beslissing eerst, dan de uitleg; elk punt krijgt een "
        "volgende stap. Mehdi dicteert met spraakherkenning: namen in zijn tekst kunnen vervormd zijn, "
        "neem dan de dichtstbijzijnde bekende naam en meld de correctie kort. Dat geldt alleen voor namen "
        "in zijn tekst, nooit voor de agent die wordt aangesproken.\n"
        f"{rol}\n"
        "Je gereedschap leest of stelt voor; je voert zelf niets muterends uit. Wil Mehdi dat iets verandert "
        "(een werkwijze, een dealtitel, een handeling), dan zet je een voorstel op het bord met het juiste "
        "runbook en zeg je dat het op zijn goedkeuring wacht. Wil hij dat een agent nu iets doet, gebruik "
        "agent_ronde. Beweer niets dat je niet uit het gereedschap haalde; zeg wat je niet kunt en wat "
        "daarvoor nodig is. Een toezegging voor later bestaat alleen als je ze met taak_plannen opslaat en het taak-ID "
        "noemt; een voorstel staat pas op het bord als de tool een voorstel-ID teruggeeft. Zonder ID beloof of bevestig je "
        "niets. Vraagt Mehdi naar de toestand van de agents, loop dan elke agent uit "
        "agents_overzicht na en noem ze allemaal die op fout of stil staan; vat nooit samen uit je hoofd. "
        "Antwoord in markdown, kort.\n\n"
        "=== JOUW WERKWIJZE (van het bord) ===\n" + (werkwijze_regisseur or "(nog niet uitgeschreven)")
    )
    berichten = []
    for e in eerder:
        berichten.append({"role": "user", "content": e["tekst"]})
        berichten.append({"role": "assistant", "content": e["antwoord"] or "(geen antwoord)"})
    berichten.append({"role": "user", "content": gesprek["tekst"]})
    gedaan = []
    for _ in range(MAX_RONDES):
        resp = client.messages.create(model=MODEL, max_tokens=4000, system=system, messages=berichten, tools=TOOLS)
        berichten.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            tekst = "".join(getattr(b, "text", "") for b in resp.content).strip()
            return tekst or "(geen antwoord)", gedaan
        resultaten = []
        for b in resp.content:
            if getattr(b, "type", "") == "tool_use":
                try:
                    uit = voer_tool_uit(b.name, dict(b.input))
                except Exception as e:  # noqa: BLE001
                    uit = {"fout": f"{type(e).__name__}: {str(e)[:300]}"}
                gedaan.append(f"{b.name}({json.dumps(b.input, ensure_ascii=False)[:160]})")
                resultaten.append({"type": "tool_result", "tool_use_id": b.id,
                                   "content": json.dumps(uit, ensure_ascii=False)[:60000]})
        berichten.append({"role": "user", "content": resultaten})
    return "Ik ben gestopt na tien stappen zonder eindantwoord; stel de vraag kleiner.", gedaan


def main():
    if not TOKEN:
        print("FOUT: geen AGENTS_TOKEN", file=sys.stderr)
        return
    # eerst de taken waarvan het moment gekomen is (toezeggingen voor later, A9)
    for tid, st in taken_uitvoeren():
        print(f"taak {tid}: {st}")
    open_ = bord("/api/gesprek/open").get("open") or []
    if not open_:
        hartslag("waakt", taak="luistert", detail="geen open berichten")
        return
    werkwijze = (bord(f"/api/agent/{NAAM}/werkwijze").get("werkwijze") or "")
    for g in open_:
        gid = g["id"]
        bord(f"/api/gesprek/{gid}/status", {"status": "bezig"})
        hartslag("actief", taak="antwoordt", detail=f"bericht {gid} aan {g['aan']}")
        try:
            volledig = bord(f"/api/gesprek/{gid}")
            tekst, gedaan = antwoord(volledig["gesprek"], volledig.get("eerder") or [], werkwijze)
            bord(f"/api/gesprek/{gid}/status", {"status": "beantwoord", "antwoord": tekst,
                                                 "detail": "\n".join(gedaan) or "(alleen nagedacht, geen gereedschap)"})
            bord("/api/logboek", {"regels": [
                {"naam": NAAM, "onderwerp": f"bericht {gid} aan {g['aan']}", "stap": "bron", "tekst": f"vraag van {g['van']}: {g['tekst'][:160]}"},
                {"naam": NAAM, "onderwerp": f"bericht {gid} aan {g['aan']}", "stap": "besluit", "tekst": f"gereedschap: {', '.join(x.split('(')[0] for x in gedaan) or 'geen'}", "detail": "\n".join(gedaan)},
                {"naam": NAAM, "onderwerp": f"bericht {gid} aan {g['aan']}", "stap": "melding", "tekst": "beantwoord op het bord", "detail": tekst}]})
            print(f"bericht {gid} beantwoord ({len(gedaan)} stappen)")
        except Exception as e:  # noqa: BLE001
            bord(f"/api/gesprek/{gid}/status", {"status": "mislukt", "antwoord": f"Mislukt: {type(e).__name__}: {str(e)[:300]}"})
            bord("/api/logboek", {"regels": [{"naam": NAAM, "onderwerp": f"bericht {gid} aan {g['aan']}", "stap": "fout", "tekst": f"{type(e).__name__}: {str(e)[:300]}"}]})
            print(f"bericht {gid} mislukt: {e}", file=sys.stderr)
    hartslag("waakt", taak="luistert", detail=f"laatste ronde: {len(open_)} bericht(en) beantwoord")


if __name__ == "__main__":
    main()
