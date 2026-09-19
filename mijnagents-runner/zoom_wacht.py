#!/usr/bin/env python3
"""De Zoomwacht (Privé · Communicatie) — Mehdi's Zoom-chat en -meetings in het logboek.

Werkwijze op het bord (werkwijze/zoom-wacht.md is het zaad). Twee keer per dag:
1. Chat: per gesprek (1:1 of kanaal) per dag tellen hoeveel berichten er waren,
   hoeveel van Mehdi, en wanneer het begon en eindigde. Nooit de inhoud.
2. Meetings: elke afgelopen meeting met duur en deelnemers.
3. Rijen in de gesprekkentabel (bron zoom) en één dagregel voor De Dagbundelaar.
Privé (1:1 met Angela, familie, of een onbekende) is alleen voor Mehdi.

Koppeling: de Server-to-Server-app van de stack (ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID,
ZOOM_CLIENT_SECRET in ~/pipedrive-won-deals/.env). Mehdi is de accounteigenaar,
dus de gebruiker is "me" (ZOOM_MEHDI_USER om dat te veranderen). Scopes: team_chat
en meeting lezen, user lezen (gezet 10-09-2026).
Staat: mijnagents-data/zoom-wacht.json (laatste ronde). Eerste ronde: 14 dagen.
"""
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import fathom_wacht as fw  # noqa: E402  (personen_uit_werkwijze, belgisch, AFDELINGEN)

NAAM = "zoom-wacht"
ag = bord.Agent(NAAM)
STAAT = os.path.expanduser("~/appportal/mijnagents-data/zoom-wacht.json")
ZOOM_ENV = os.path.expanduser("~/pipedrive-won-deals/.env")
GEBRUIKER = os.environ.get("ZOOM_MEHDI_USER", "me")
DAGEN_EERST = int(os.environ.get("ZOOM_WACHT_DAGEN", "14"))
DROOG = "--droog" in sys.argv
API = "https://api.zoom.us/v2"
PRIVE_NAMEN = ("angela", "lara")


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env(ZOOM_ENV)
_tok = {"waarde": ""}


def beschikbaar():
    return all(os.environ.get(n, "").strip() for n in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"))


def token():
    if _tok["waarde"]:
        return _tok["waarde"]
    basis = base64.b64encode(f"{os.environ['ZOOM_CLIENT_ID']}:{os.environ['ZOOM_CLIENT_SECRET']}".encode()).decode()
    url = "https://zoom.us/oauth/token?" + urllib.parse.urlencode({"grant_type": "account_credentials", "account_id": os.environ["ZOOM_ACCOUNT_ID"]})
    with urllib.request.urlopen(urllib.request.Request(url, method="POST", headers={"Authorization": "Basic " + basis}), timeout=20) as r:
        _tok["waarde"] = json.load(r)["access_token"]
    return _tok["waarde"]


def get(pad, params=None):
    url = f"{API}{pad}" + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token()})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise


def get_alles(pad, params, sleutel):
    """Alle pagina's (next_page_token) van een lijst-endpoint."""
    uit, p = [], dict(params)
    while True:
        d = get(pad, p)
        uit += d.get(sleutel) or []
        if not d.get("next_page_token"):
            return uit
        p["next_page_token"] = d["next_page_token"]


def uuid_pad(uuid):
    """Zoom eist dubbele codering als een uuid met / begint of // bevat."""
    q = urllib.parse.quote(uuid, safe="")
    return urllib.parse.quote(q, safe="") if uuid.startswith("/") or "//" in uuid else q


# ------------------------------------------------------------ herkenning ---
def _tokens(naam):
    return {t for t in re.split(r"[^a-zà-ÿ]+", (naam or "").lower()) if len(t) > 2}


def herken_persoon(personen, email="", naam=""):
    """Rij uit de tabel Betrokken personen: op e-mail, anders op naamdelen (de tabel
    kan 'Voornaam Naam' of 'Naam Voornaam' bevatten, Zoom geeft weergavenamen)."""
    email = (email or "").lower()
    for p in personen:
        if email and email in p["mails"]:
            return p
    zt = _tokens(naam)
    if not zt:
        return None
    beste, score = None, 0
    for p in personen:
        pt = _tokens(p["naam"])
        s = len(zt & pt)
        if s > score or (s == score and s and len(pt) < len(_tokens(beste["naam"]))):
            beste, score = p, s
    return beste if score >= 1 else None


AFDELING_ALIAS = {"ha-": "h-architects", "[ha]": "h-architects", "h-a ": "h-architects", "hb-": "harmoniebouw", "ctx-": "contrax", "tkn-": "tkn"}


def afdeling_uit_naam(tekst):
    t = (tekst or "").lower()
    for a in fw.AFDELINGEN:
        if a in t or a.replace("-", "") in t.replace("-", "").replace(" ", ""):
            return a
    for k, a in AFDELING_ALIAS.items():
        if k in t:
            return a
    return ""


def is_prive_naam(naam):
    return any(n in (naam or "").lower() for n in PRIVE_NAMEN)


# ------------------------------------------------------------------ chat ---
def chat_rijen(van_dag, tot_dag, personen, mijn_email):
    """Eén rij per gesprek per dag: aantallen, geen inhoud."""
    sessies = get_alles(f"/chat/users/{GEBRUIKER}/sessions", {"from": van_dag, "to": tot_dag, "page_size": 50}, "sessions")
    rijen, dagtel = [], defaultdict(lambda: {"berichten": 0, "gesprekken": 0, "prive": 0})
    for s in sessies:
        p = {"from": van_dag, "to": tot_dag, "page_size": 50}
        een_op_een = s.get("type") == "1:1"
        if een_op_een:
            p["to_contact"] = s.get("peer_contact_email", "")
        else:
            p["to_channel"] = s.get("channel_id", "")
        if not (p.get("to_contact") or p.get("to_channel")):
            continue
        berichten = get_alles(f"/chat/users/{GEBRUIKER}/messages", p, "messages")
        if not berichten:
            continue
        naam = s.get("name") or ("gesprek" if een_op_een else "kanaal")
        per_dag = defaultdict(list)
        for m in berichten:
            per_dag[fw.belgisch(m.get("date_time", ""))[:10]].append(m)
        persoon = herken_persoon(personen, s.get("peer_contact_email", ""), naam) if een_op_een else None
        if een_op_een:
            afd = (persoon or {}).get("afdeling", "") or "onbekend"
            prive = is_prive_naam(naam) or "priv" in afd.lower() or persoon is None
            zeker = "hoog" if persoon else "laag"
            waarom = f"1:1 met {naam}; " + ("bekend uit de personentabel" if persoon else "niet in de personentabel: bij twijfel privé")
        else:
            afd = afdeling_uit_naam(naam) or "onbekend"
            prive = False
            zeker = "hoog" if afd != "onbekend" else "middel"
            waarom = f"kanaal {naam}; afdeling uit de kanaalnaam" if afd != "onbekend" else f"kanaal {naam}; afdeling niet uit de naam af te leiden"
        sleutel = re.sub(r"[^a-z0-9@._-]+", "-", (s.get("peer_contact_email") or s.get("channel_id") or naam).lower())[:80]
        for dag, lijst in sorted(per_dag.items()):
            if not dag:
                continue
            tijden = sorted(fw.belgisch(m.get("date_time", ""))[11:16] for m in lijst)
            van_mehdi = sum(1 for m in lijst if (m.get("sender") or "").lower() == mijn_email)
            rijen.append({"uniek": f"zoom:chat:{sleutel}:{dag}", "datum": dag, "start": tijden[0] if tijden else "", "minuten": 0,
                          "personen": naam, "bedrijf": "", "afdeling": afd,
                          "thema": f"Zoom-chat: {len(lijst)} bericht(en), {van_mehdi} van Mehdi, {tijden[0] if tijden else ''} tot {tijden[-1] if tijden else ''}",
                          "project": "", "prive": prive, "zekerheid": zeker, "waarom": waarom, "archief": "", "link": "",
                          "opgenomen_door": "Zoom-chat", "bron": "zoom"})
            dagtel[dag]["berichten"] += len(lijst)
            dagtel[dag]["gesprekken"] += 1
            dagtel[dag]["prive"] += 1 if prive else 0
    return rijen, dagtel


# -------------------------------------------------------------- meetings ---
def meeting_rijen(van_dag, tot_dag, personen, mijn_email):
    lijst = get_alles(f"/users/{GEBRUIKER}/meetings", {"type": "previous_meetings", "from": van_dag, "to": tot_dag, "page_size": 50}, "meetings")
    rijen, dagtel, gezien = [], defaultdict(lambda: {"meetings": 0, "minuten": 0}), set()
    for m in lijst:
        uuid = m.get("uuid") or str(m.get("id"))
        if uuid in gezien:
            continue
        gezien.add(uuid)
        # past_meetings op uuid; lukt dat niet (oude of dubbel gecodeerde uuid), dan op het nummer
        # (dat geeft de laatste keer dat de meeting liep). Geen van beide: nooit gestart, geen gesprek.
        detail, ref = {}, ""
        for kandidaat in (uuid_pad(uuid), str(m.get("id") or "")):
            if kandidaat:
                detail = get(f"/past_meetings/{kandidaat}") or {}
                if detail:
                    ref = kandidaat
                    break
        if not detail:
            if DROOG:
                print(f"   meeting {fw.belgisch(m.get('start_time', ''))}: niet gestart of geen gegevens, overgeslagen ({(m.get('topic') or '')[:50]})")
            continue
        deelnemers = get_alles(f"/past_meetings/{ref}/participants", {"page_size": 300}, "participants")
        start = fw.belgisch(detail.get("start_time") or m.get("start_time") or "")
        if not start:
            continue
        dag = start[:10]
        namen, afdelingen, bekend = [], defaultdict(int), 0
        for d in deelnemers:
            n = d.get("name") or d.get("user_email") or "?"
            if n not in namen:
                namen.append(n)
            p = herken_persoon(personen, d.get("user_email", ""), n)
            if p:
                bekend += 1
                if p["afdeling"] and "priv" not in p["afdeling"].lower():
                    afdelingen[p["afdeling"].split(" ")[0].lower()] += 1
        anderen = [n for n in namen if "mehdi" not in n.lower()]
        prive = bool(anderen) and all(is_prive_naam(n) for n in anderen)
        afd = max(afdelingen, key=afdelingen.get) if afdelingen else (afdeling_uit_naam(m.get("topic", "")) or ("prive" if prive else "onbekend"))
        duur = int(detail.get("duration") or m.get("duration") or 0)
        rijen.append({"uniek": f"zoom:meeting:{uuid}", "datum": dag, "start": start[11:16], "minuten": duur,
                      "personen": ", ".join(namen)[:300], "bedrijf": "", "afdeling": afd, "thema": (m.get("topic") or "Zoom-meeting")[:120],
                      "project": "", "prive": prive, "zekerheid": "hoog" if bekend == len(namen) and namen else ("middel" if bekend else "laag"),
                      "waarom": f"{len(namen)} deelnemer(s), {bekend} bekend uit de personentabel; afdeling uit de deelnemers" if afdelingen else f"{len(namen)} deelnemer(s); afdeling uit de titel of onbekend",
                      "archief": "", "link": m.get("join_url", ""), "opgenomen_door": detail.get("user_name") or "Mehdi", "bron": "zoom"})
        dagtel[dag]["meetings"] += 1
        dagtel[dag]["minuten"] += duur
        if DROOG:
            print(f"   meeting {dag} {start[11:16]}: {len(deelnemers)} deelnemerrecords, {len(namen)} namen, {bekend} bekend, detail {'ja' if detail else 'nee'}, afd {afd}")
    return rijen, dagtel


# ------------------------------------------------------------------ main ---
def main():
    ag.hartslag("actief", taak="Zoom ophalen")
    try:
        if not beschikbaar():
            ag.hartslag("fout", taak="geen Zoom-koppeling", detail="ZOOM_* ontbreekt in pipedrive-won-deals/.env",
                        nood=[{"tekst": "Zoom-koppeling: ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID en ZOOM_CLIENT_SECRET ontbreken", "wie": "shaniel"}])
            return
        try:
            staat = json.load(open(STAAT))
        except (OSError, ValueError):
            staat = {}
        nu = datetime.now(timezone.utc)
        laatste = staat.get("laatste")
        van = (datetime.fromisoformat(laatste) - timedelta(days=1)) if laatste else (nu - timedelta(days=DAGEN_EERST))
        van_dag, tot_dag = van.strftime("%Y-%m-%d"), (nu + timedelta(days=1)).strftime("%Y-%m-%d")  # 'to' is exclusief: morgen
        personen = fw.personen_uit_werkwijze(bord.call("/api/agent/fathom-wacht/werkwijze").get("werkwijze") or "")
        ik = get(f"/users/{GEBRUIKER}") or {}
        mijn_email = (ik.get("email") or "").lower()
        chat, chat_dag = chat_rijen(van_dag, tot_dag, personen, mijn_email)
        meet, meet_dag = meeting_rijen(van_dag, tot_dag, personen, mijn_email)
        rijen = chat + meet
        # één dagregel per dag voor De Dagbundelaar (alleen voor Mehdi; privé blijft telling zonder naam)
        klaar = []
        for dag in sorted(set(chat_dag) | set(meet_dag)):
            c, mt = chat_dag.get(dag, {}), meet_dag.get(dag, {})
            titel = (f"Zoom {dag}: {c.get('berichten', 0)} berichten in {c.get('gesprekken', 0)} gesprek(ken)"
                     + (f" ({c['prive']} privé)" if c.get("prive") else "")
                     + f", {mt.get('meetings', 0)} meeting(s), {mt.get('minuten', 0)} min")
            inhoud = {"datum": dag, "berichten": c.get("berichten", 0), "gesprekken": c.get("gesprekken", 0), "prive_gesprekken": c.get("prive", 0),
                      "meetings": mt.get("meetings", 0), "meeting_minuten": mt.get("minuten", 0),
                      "werk": [r["personen"] + " (" + r["thema"][:40] + ")" for r in rijen if r["datum"] == dag and not r["prive"]][:12]}
            klaar.append({"voor": "mehdi", "soort": "zoom", "sleutel": dag, "titel": titel, "uniek": f"zoom:dag:{dag}", "inhoud": inhoud})
        if DROOG:
            print(f"(droog) {len(chat)} chatrijen, {len(meet)} meetingrijen, {len(klaar)} dagregels; venster {van_dag} tot {tot_dag}; gebruiker {ik.get('first_name', '')} ({'e-mail bekend' if mijn_email else 'geen e-mail'})")
            print("   personentabel:", len(personen), "rijen")
            for r in rijen[:10]:
                print("  ", r["datum"], r["start"], r["afdeling"], "privé" if r["prive"] else "werk", "|", r["personen"][:40], "|", r["thema"][:60])
            return
        if rijen:
            bord.call("/api/gesprekken", {"rijen": rijen})
        uit = ag.klaarzet(klaar)
        staat["laatste"] = nu.isoformat()
        json.dump(staat, open(STAAT, "w"))
        prive_n = sum(1 for r in rijen if r["prive"])
        ag.log("Zoom", "bron", f"venster {van_dag} tot {tot_dag}: {len(chat)} chat-dagrijen, {len(meet)} meetings; {prive_n} privé; {len(personen)} personen in de tabel")
        ag.log("Zoom", "schrijf", f"gesprekkentabel +{len(rijen)} (bron zoom); dagregels: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend")
        ag.log_verstuur()
        ag.hartslag("waakt", taak="wacht op nieuwe chat en meetings",
                    detail=f"laatste ronde: {len(chat)} chat-dagrijen, {len(meet)} meetings, {prive_n} privé", nood=[])
    except Exception as e:  # noqa: BLE001
        ag.log("Zoom", "fout", f"{type(e).__name__}: {str(e)[:200]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}",
                    nood=[{"tekst": f"Zoomwacht: ronde mislukt met {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"}])
        raise


if __name__ == "__main__":
    main()
