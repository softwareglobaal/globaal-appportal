#!/usr/bin/env python3
"""De Zoomwacht (Privé · Communicatie): telt elk Zoom-gesprek van Mehdi, koppelt het aan Fathom en bewaart de
Zoom-tekst als Fathom een gesprek mist. Werkwijze op het bord (werkwijze/zoom-wacht.md is het zaad, versie 2.3).

Ontwerp regie-zoom v1.2 (Z3 tot Z9, met 13.2 en 13.5). In de gesprekkenketen na De Fathomwacht (keten.py, 07:00 en
13:00 UTC onder /tmp/gesprekken.lock; 09:00 en 15:00 Brussel tot en met 24-10-2026, daarna 08:00 en 14:00):
1. Zoom, met de uuid van de sessie als sleutel, ook in de vaste vergaderruimte. Vijf bronnen, elk met een eigen
   toestand (ok, geen recht: <recht>, fout, niet ingesteld): het rapport (past, pastOne, pastJoined), de instanties van
   de vaste vergaderruimte, de geplande meetings, de cloudopnames en de laatste sessie in de vaste vergaderruimte. Een
   sessie die een eerdere ronde zag, blijft meetellen zolang ze in het venster valt, ook als geen bron ze nog geeft
   (ZOO-01). Een sessie met minder dan twee mensen is alleen Mehdi in de ruimte: geen gesprek, alleen een teller (J10);
   een rij die er toch al stond, krijgt dubbel_van buiten:alleen-mehdi en een lege link (ZOO-04).
2. Fathom: het archief van De Fathomwacht (fathom-data/<map>/gesprek.json) en de API zonder transcript. Koppelen per
   meetingnummer met een maximale gewogen een-op-een-toewijzing (X2): eerst het aantal koppelingen, dan het eigen
   Fathom-account, dan de overlap. Een opname van een ander account telt alleen als Mehdi volgens Zoom in die sessie zat
   (13.1); een uit een andere ruimte krijgt dubbel_van buiten:andere-ruimte, alleen als het rapport gelezen is (ZOO-03),
   een zonder Zoom-nummer buiten:zonder-zoom (BAS-03), en dat alleen als ze in het Zoom-venster begint (ZOO-02). Een rij
   die bij een sessie buiten deze ronde hoort, krijgt nooit buiten.
3. Vangnet (Z6): een afgeronde sessie zonder Fathom, 30 minuten na het einde, met alle opnames klaar. De Zoom-tekst (VTT)
   gaat naar mijnagents-data/zoom-data/<map>/ (transcript.vtt, transcript.json in de vorm van Fathom, als laatste
   zoom.json), altijd privé (X1), met een klaarzet-item zoom-tekst voor De Regisseur. Een opname zonder tekst meld ik na
   24 uur; uitschrijven doe ik nooit.
4. De gesprekkentabel (Z7): per sessie een rij zoom:meeting:<uuid> (bron zoom, link altijd leeg). De koppeling op de
   Fathom-rijen gaat via /api/gesprekken/koppel en telt pas als bord.db_lees ze teruggeeft (L32).
5. Per afgelopen Brusselse dag een dagregel zoom:dag:<dag> voor Mehdi, met lege sleutel (Z8). Verandert de kern na het
   oppakken (ook het aantal bewezen chatgesprekken, RZ13), dan met revisie, tot zes dagen terug; nooit naar
   onbekend en, als een bron faalde, nooit naar een lagere telling (ZOO-01, ZOO-05). Zag alleen Fathom een gesprek, dan
   is die dag een ondergrens (ZOO-09). Het chatcijfer komt uit de gesprekkentabel na het schrijven (RZ10, chat_tellen).
6. Fase 4b: alleen met ACCOUNTSCAN: aan op het bord een wekelijkse accountscan en een wijzigingscontrole per ronde.
   Alle accountvragen zijn GET via de eigen leesapp; adviezen worden voorstellen zonder uitvoerbaar runbook.

De koppeling met Zoom is koppelingen/zoom.py (een koppeling, Z1). De alleen-lezende app "Zoomwacht lezen" zet Mehdi
met zoom_leesapp.py --zet; zonder die app, of als haar sleutels geen token geven (ZOO-10), lees ik met de app van de
stack en is de telling een ondergrens ("minstens N"), met een nood voor Mehdi; zo ook als het token van de leesapp een
recht heeft dat ze nooit mag hebben (13.6: zoom.py weigert het). De chat lees ik altijd met de app van de stack: de
leesapp krijgt het recht op chatberichten bewust niet (EIGEN-1). Het chatcijfer is altijd een ondergrens uit de
gesprekkentabel (RZ13), ook als de sessielijst deze ronde leesbaar was. Zonder bewezen chatrij verdwijnt het chatdeel
uit de titel. Is de gesprekkentabel onleesbaar, dan is de chat onbekend; een eerder chatdeel blijft als "laatst gezien"
staan. Onbekend is nooit een zekere nul (L29, L38). Elke ronde gaat door
de gedeelde ronde (N12). Is de Zoom-gebruiker niet de eigenaar van de vaste vergaderruimte (de pmi is niet het meest
voorkomende nummer in Mehdi's eigen Fathom-opnames), dan schrijf ik niets, ook niet met --koppel-sinds: alleen een nood
voor Mehdi en een hartslag die zegt dat er niets geschreven is (RZ4-02).

    zoom_wacht.py                              een ronde
    zoom_wacht.py --droog                      alleen lezen; een rapport per dag zonder namen of onderwerpen
    zoom_wacht.py --inhaal 14                  het venster op 14 dagen in plaats van 7 (hoogstens 35)
    zoom_wacht.py --inhaal 35 --oud-herzien    eenmalig: ook een opgepakte dagregel ouder dan zes dagen herzien
    zoom_wacht.py --koppel-sinds 2026-09-07    oude zoom:meeting-rijen koppelen en daarna hun joinlink leegmaken, en de
                                               andere ruimtes voor het venster opnieuw beoordelen met het rapport
Staat: mijnagents-data/zoom-wacht.json (laatste ronde en een cache van afgeronde sessies).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import sys
import tempfile
import urllib.parse
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import fathom  # noqa: E402  (de API zonder transcript, en MEHDI_FATHOM_ADRESSEN: Mehdi's eigen account, EIGEN-3)
import fathom_wacht as fw  # noqa: E402  (personen_uit_werkwijze, belgisch, AFDELINGEN, ARCHIEF)
import zoom as Z  # noqa: E402
import zoom_account as ZA  # noqa: E402  (accountscan, alleen via het leestoken)

NAAM = "zoom-wacht"
ag = bord.Agent(NAAM)
DATA = os.path.expanduser("~/appportal/mijnagents-data")
STAAT = os.path.join(DATA, "zoom-wacht.json")
ZOOM_DATA = os.path.join(DATA, "zoom-data")
FATHOM_DATA = fw.ARCHIEF
VENSTER_DAGEN = 7
INHAAL_MAX = 35      # WACHT-1 (meting 01-11-2026): 01-10 tot 15-10 opnieuw tellen; de grens schuift elke dag een dag op
STUK_DAGEN = 28      # Zoom geeft het rapport, de opnames en de chat voor hoogstens een maand per vraag
WACHT_NA_EINDE = timedelta(minutes=30)
TEKST_WACHT = timedelta(hours=24)
TERUGBLIK = 6
BE = ZoneInfo("Europe/Brussels")
NUMMER = re.compile(r"/j/(\d{9,11})")
PRIVE_NAMEN = ("angela", "lara")
NIET_ALS_DEELNEMER = ("notetaker", "fathom", "otter", "read.ai", "fireflies")
RAPPORT_SOORTEN = ("past", "pastOne", "pastJoined")
ZOOM_BRONNEN = ("rapport", "vaste vergaderruimte", "gepland", "opnames", "laatste sessie")
PMR_THEMA = "Zoom-gesprek in de vaste vergaderruimte"
# De kern van een dagregel: verandert die na het oppakken, dan gaat de regel met revisie opnieuw naar Mehdi (Z8). De chat
# hoort er ook bij, uitsluitend met het aantal bewezen chatgesprekken (RZ13, chat_kern en kern_anders).
KERN = ("gesprekken", "met_fathom", "alleen_zoom_tekst", "opname_zonder_tekst", "telling", "stand")
# Het begin van het thema van een chatrij (chat_rijen schrijft het, chat_tellen leest er het aantal berichten uit)
CHAT_THEMA = re.compile(r"Zoom-chat: (\d+) bericht\(en\)")
VERVALLEN = "vervallen: Fathom heeft het gesprek"
# RZ4-02: de nood als de Zoom-gebruiker niet de eigenaar van de vaste vergaderruimte is; dan schrijf ik niets
IDENTITEIT_NOOD = "De Zoom-gebruiker van de leesapp is niet de eigenaar van de vaste vergaderruimte"
IDENTITEIT_ONBEKEND_NOOD = "De Zoom-gebruiker is niet bewezen: geen eigen Fathom-opname in het venster; ik schrijf niets"
IDENTITEIT_NIET_GELEZEN_NOOD = "De Zoom-gebruiker is niet gelezen; ik schrijf niets"
BEWIJS_GELDIG = 90   # dagen dat een bewijs op Fathom geldt voor dezelfde gebruiker en ruimte (RZ6-01)
GEWICHT_KOPPELING, GEWICHT_EIGEN = 10 ** 9, 10 ** 6
# De vaste woorden van mijn titels, standen en noden. Een weergavenaam die zo'n woord is, maskeer ik niet (ZOO-06).
VASTE_WOORDEN = frozenset(("zoom", "gesprek", "gesprekken", "chat", "chatgesprekken", "opname", "opnames", "meeting", "fathom",
                           "tekst", "telling", "minuten", "vergaderruimte", "leesapp", "vangnet", "koppeling", "verwerking",
                           "onvolledig", "voorlopig", "definitief", "minstens", "onbekend", "alleen", "privé"))


def nu():
    """De klok van de ronde, in UTC. De test vervangt hem: de Brusselse dag en de wachttijden hangen ervan af."""
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ tijd ---
def tijd(iso):
    """Een ISO-tijd van Zoom of Fathom als UTC-tijd, of None."""
    if not iso:
        return None
    if isinstance(iso, datetime):
        t = iso
    else:
        try:
            t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        except ValueError:
            return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def brussel(t):
    return t.astimezone(BE)


def dag_van(t):
    """De Brusselse dag van een UTC-tijd. De VM draait op UTC; 25-10-2026 duurt 25 uur, 28-03-2027 23 uur."""
    return brussel(t).date().isoformat()


def zoom_tijd(t):
    """Een tijdstip zoals de chat-API van Zoom het in from en to verwacht: UTC, met tijd en Z."""
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def dag_grenzen(dag):
    """Begin en einde van een Brusselse dag, in UTC."""
    d = date.fromisoformat(dag)
    begin = datetime.combine(d, time(0), tzinfo=BE)
    einde = datetime.combine(d + timedelta(days=1), time(0), tzinfo=BE)
    return begin.astimezone(timezone.utc), einde.astimezone(timezone.utc)


def stukken(van_dag, tot_dag, dagen=STUK_DAGEN):
    """[van_dag, tot_dag] (JJJJ-MM-DD, beide inbegrepen) als aansluitende stukken (van, tot) van hoogstens DAGEN dagen,
    zonder overlap: Zoom geeft het rapport, de opnames en de chat voor hoogstens een maand per vraag (WACHT-1). Een
    gewoon venster is een stuk."""
    d, einde, uit = date.fromisoformat(van_dag), date.fromisoformat(tot_dag), []
    while d <= einde:
        tot = min(d + timedelta(days=dagen - 1), einde)
        uit.append((d.isoformat(), tot.isoformat()))
        d = tot + timedelta(days=1)
    return uit


def utc_tijden(dag, uur):
    """Een Brusselse datum en tijd zonder UTC-bron ('2026-10-25', '02:30') als UTC: een tijd, of twee als de Brusselse tijd
    dubbelzinnig is (RZ2-05). Op 25-10-2026 gaat de klok terug en bestaat 02:30 twee keer, om 00:30 en 01:30 UTC; een
    tijd die niet bestaat (28-03-2027, 02:30) geeft er ook twee. Gesorteerd, het eerste uur eerst."""
    lokaal = datetime.strptime(f"{dag} {uur}", "%Y-%m-%d %H:%M")
    return sorted({lokaal.replace(tzinfo=BE, fold=f).astimezone(timezone.utc) for f in (0, 1)})


def overlap(a_start, a_einde, b_start, b_einde):
    """Overlap in seconden, 0 als ze elkaar niet raken."""
    return max(0.0, (min(a_einde, b_einde) - max(a_start, b_start)).total_seconds())


def minuten(s):
    if s.get("duur") is not None:
        return int(s["duur"])
    if s.get("einde"):
        return max(0, round((s["einde"] - s["start"]).total_seconds() / 60))
    return 0


# ------------------------------------------------------------ herkenning ---
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


def vast_woord(tekst):
    """Een weergavenaam die een vast woord van De Zoomwacht is ('Zoom', 'Opname'), gaat niet naar het masker van het
    bord: dat kent geen woordgrens en verminkte anders elke titel en nood (ZOO-06), en zo'n naam zegt niemand iets. Een
    echte naam blijft gemaskeerd, ook als hij in een vast woord zit (Leen in alleen): privé gaat voor leesbaar."""
    return (tekst or "").strip().lower() in VASTE_WOORDEN


def teamdomeinen(werkwijze):
    """H2: de vaste lijst teamdomeinen uit mijn werkwijze ("Teamdomeinen ...: a.be, b.be"). Geen lijst: niemand is bekend
    op domein, en bij twijfel is een gesprek privé."""
    m = re.search(r"^(?:[-*]\s+)?Teamdomeinen[^:\n]*:\s*(.+)$", werkwijze or "", re.M)
    if not m:
        return ()
    return tuple(d.strip().strip(".").lower() for d in m.group(1).split(",") if "." in d)


def bekend(personen, email, domeinen):
    """H2: bekend alleen op exact e-mailadres uit de personentabel, of op een teamdomein. Nooit op naam: een
    weergavenaam kiest de deelnemer zelf, en een naamgenoot is geen bekende. Geeft (persoon of None, bekend)."""
    email = (email or "").strip().lower()
    if "@" not in email:
        return None, False
    for p in personen or []:
        if email in p["mails"]:
            return p, True
    return None, email.rsplit("@", 1)[1] in domeinen


def is_mehdi(d, ik):
    """Mehdi herken ik op zijn Zoom-gebruikers-id of zijn exacte Zoom-adres, nooit op naam (H2)."""
    return bool(ik and ((d.get("id") and d["id"] == ik["id"]) or (d.get("email") and d["email"] == ik["email"])))


def deelnemers_uit(lijst):
    """De mensen in een sessie: zonder opnamebots en zonder dubbele records (herverbinden). None blijft None: een
    deelnemerslijst die niet te lezen was, is onbekend, niet leeg."""
    if lijst is None:
        return None
    uit, gezien = [], set()
    for d in lijst:
        naam = (d.get("name") or "").strip()
        email = (d.get("user_email") or "").strip().lower()
        if any(x in f"{naam} {email}".lower() for x in NIET_ALS_DEELNEMER):
            continue
        sleutels = {k for k in (d.get("id") or "", email, naam.lower()) if k}
        if not sleutels or sleutels & gezien:
            gezien |= sleutels
            continue
        gezien |= sleutels
        uit.append({"naam": naam or email.split("@")[0], "email": email, "id": d.get("id") or ""})
    return uit


def mensen(s):
    return len(s["deelnemers"]) if s["deelnemers"] is not None else s.get("aantal")


def is_gesprek(s):
    """Een gesprek heeft minstens twee mensen. Onbekend aantal: het telt, want onbekend is niet 'alleen Mehdi'."""
    n = mensen(s)
    return n is None or n >= 2


def mehdi_erbij(s, ik):
    """Zat Mehdi volgens Zoom in de sessie: in de deelnemerslijst, of zonder lijst als host of deelnemer (13.1)."""
    if not ik:
        return False
    if s["deelnemers"] is not None:
        return any(is_mehdi(d, ik) for d in s["deelnemers"])
    return bool(s.get("host_id") and s["host_id"] == ik["id"]) or bool(s.get("deelname"))


def zoom_prive(s, ik, personen, domeinen):
    """H2: een sessie is werk als elke andere deelnemer bekend is op exact e-mailadres of teamdomein; anders privé, en
    bij twijfel privé (onbekende deelnemers, een deelnemer zonder e-mail, een naamgenoot). Zonder personentabel telt
    alleen het teamdomein (T26). Dit geldt voor de telling en de titel; vangnettekst is altijd privé (X1)."""
    if s["deelnemers"] is None:
        return True
    anderen = [d for d in s["deelnemers"] if not is_mehdi(d, ik)]
    if not anderen:
        return True
    for d in anderen:
        p, ok = bekend(personen, d["email"], domeinen)
        if not ok or is_prive_naam(d["naam"]):
            return True
        if p and ("priv" in (p.get("afdeling") or "").lower() or is_prive_naam(p["naam"])):
            return True
    return False


def ruimte_van(s, ik):
    if ik and s.get("nummer") and s["nummer"] == ik["pmi"]:
        return "vaste vergaderruimte"
    if ik and s.get("host_id") and s["host_id"] != ik["id"]:
        return "meeting van een ander"
    return "eigen meeting"


# ------------------------------------------------------------------ zoom ---
def toestand_van(fout):
    """De toestand van een bron die faalde, zonder url of sleutel."""
    if isinstance(fout, Z.GeenRecht):
        return f"geen recht: {fout.scope}"
    if isinstance(fout, Z.ZoomFout):
        return f"fout: {str(fout)[:80]}"
    return f"fout: {type(fout).__name__}"


def _lijst(pad, params, sleutel, profiel="lees"):
    lijst = Z.lees_alles(pad, params, sleutel, profiel)
    if lijst is None:
        raise Z.ZoomFout("lijst niet gevonden")
    return lijst


def _bewaar(s):
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in s.items() if k != "bronnen"}


def _herstel(c):
    s = dict(c)
    s["start"], s["einde"] = tijd(c.get("start")), tijd(c.get("einde"))
    return s


def zoom_lezen(van, tot, staat, klok):
    """Z4: elke Zoom-sessie die in [van, tot) begint, uit vijf bronnen, samengevoegd op uuid. Geeft een dict met ik
    ({id, email, pmi} of None), sessies (per uuid), bronnen (toestand per bron), opnamen (per uuid, zonder links) en
    laatste ('ok', 'ontbreekt' of 'niet gelezen'). Een bron die faalt, maakt de telling een ondergrens, nooit een 0."""
    bronnen = {b: "niet gelezen" for b in ZOOM_BRONNEN}
    leeg = {"ik": None, "sessies": {}, "bronnen": bronnen, "opnamen": {}, "laatste": "niet gelezen"}
    Z.vastzetten(None)
    if not Z.beschikbaar("lees"):
        leeg["bronnen"] = {b: "niet ingesteld" for b in ZOOM_BRONNEN}
        return leeg
    try:
        me = Z.lees(f"/users/{Z.ingang()}") or {}
    except Exception as e:  # noqa: BLE001
        leeg["bronnen"] = {b: toestand_van(e) for b in ZOOM_BRONNEN}
        return leeg
    ik = {"id": me.get("id") or "", "email": (me.get("email") or "").lower(), "pmi": str(me.get("pmi") or "")}
    if not ik["id"]:
        leeg["bronnen"] = {b: "fout: gebruiker onbekend" for b in ZOOM_BRONNEN}
        return leeg
    Z.vastzetten(ik["id"], [ik["pmi"]])
    d0, d1 = (van - timedelta(days=1)).date().isoformat(), (tot + timedelta(days=1)).date().isoformat()
    sessies, opnamen = {}, {}

    def voeg(m, bron, deelname=False):
        uuid, start = m.get("uuid"), tijd(m.get("start_time"))
        if not uuid or not start or not (van <= start < tot):
            return
        s = sessies.setdefault(uuid, {"uuid": uuid, "nummer": "", "onderwerp": "", "start": start, "einde": None,
                                      "duur": None, "host_id": "", "deelname": False, "aantal": None,
                                      "deelnemers": None, "bronnen": []})
        s["nummer"] = s["nummer"] or str(m.get("id") or "")
        s["onderwerp"] = s["onderwerp"] or m.get("topic") or ""
        s["einde"] = s["einde"] or tijd(m.get("end_time"))
        if s["duur"] is None and m.get("duration") is not None:
            s["duur"] = int(m["duration"])
        s["host_id"] = s["host_id"] or m.get("host_id") or ""
        if s["aantal"] is None and m.get("participants_count") is not None:
            s["aantal"] = int(m["participants_count"])
        s["deelname"] = s["deelname"] or deelname
        if bron not in s["bronnen"]:
            s["bronnen"].append(bron)

    fout = None
    for soort in RAPPORT_SOORTEN:
        try:
            for a, b in stukken(d0, d1):
                for m in _lijst(f"/report/users/{ik['id']}/meetings", {"type": soort, "from": a, "to": b, "page_size": 300}, "meetings"):
                    voeg(m, "rapport", deelname=soort == "pastJoined")
        except Exception as e:  # noqa: BLE001
            fout = fout or e
    bronnen["rapport"] = toestand_van(fout) if fout else "ok"

    if ik["pmi"]:
        try:
            d = Z.lees(f"/past_meetings/{ik['pmi']}/instances")
            if d is None:
                raise Z.ZoomFout("instanties niet gevonden")
            for m in d.get("meetings") or []:
                voeg({"uuid": m.get("uuid"), "start_time": m.get("start_time"), "id": ik["pmi"]}, "vaste vergaderruimte")
            bronnen["vaste vergaderruimte"] = "ok"
        except Exception as e:  # noqa: BLE001
            bronnen["vaste vergaderruimte"] = toestand_van(e)
    else:
        bronnen["vaste vergaderruimte"] = "niet ingesteld"

    cache = staat.setdefault("cache", {})
    try:
        for m in (m for a, b in stukken(d0, d1) for m in
                  _lijst(f"/users/{ik['id']}/meetings", {"type": "previous_meetings", "from": a, "to": b, "page_size": 50}, "meetings")):
            Z.nummer_erbij(m.get("id"))
            uuid = m.get("uuid") or ""
            if uuid in sessies or uuid in cache:
                bekend_al = sessies.get(uuid) or cache[uuid]
                voeg({"uuid": uuid, "start_time": bekend_al["start"] if isinstance(bekend_al["start"], str) else bekend_al["start"].isoformat(),
                      "id": m.get("id")}, "gepland")
                continue
            # Een geplande meeting die nooit startte, heeft geen sessie: geen gesprek. Op het nummer krijg je de
            # laatste sessie van die meeting; alleen een sessie in het venster telt.
            detail = None
            for ref in (Z.uuid_pad(uuid) if uuid else "", str(m.get("id") or "")):
                if ref:
                    detail = Z.lees(f"/past_meetings/{ref}")
                    if detail:
                        break
            if detail:
                voeg(detail, "gepland")
        bronnen["gepland"] = "ok"
    except Exception as e:  # noqa: BLE001
        bronnen["gepland"] = toestand_van(e)

    try:
        for m in (m for a, b in stukken(d0, d1) for m in Z.opnames(a, b)):
            st = tijd(m["start"])
            if m["uuid"] and st and van <= st < tot:
                opnamen[m["uuid"]] = m
                voeg({"uuid": m["uuid"], "id": m["nummer"], "topic": m["onderwerp"], "start_time": m["start"]}, "opnames")
        bronnen["opnames"] = "ok"
    except Exception as e:  # noqa: BLE001
        bronnen["opnames"] = toestand_van(e)

    laatste = "niet gelezen"
    if ik["pmi"]:
        try:
            d = Z.lees(f"/past_meetings/{ik['pmi']}") or {}
            st = tijd(d.get("start_time"))
            laatste = "ok"
            if d.get("uuid") and st and van <= st < tot:
                laatste = "ok" if d["uuid"] in sessies else "ontbreekt"
                voeg(d, "laatste sessie")
            bronnen["laatste sessie"] = "ok"
        except Exception as e:  # noqa: BLE001
            bronnen["laatste sessie"] = toestand_van(e)
    else:
        bronnen["laatste sessie"] = "niet ingesteld"

    # ZOO-01: een sessie die een eerdere ronde zag, telt mee zolang ze in het venster valt, ook als geen bron ze nu nog
    # geeft. Van de vaste vergaderruimte is zonder leesapp alleen de laatste sessie zichtbaar: begon Mehdi een nieuwe,
    # dan viel de vorige weg en daalde een ondergrens. Na de bronnen, zodat 'laatste sessie ontbreekt' over de bronnen
    # blijft gaan.
    for uuid, c in sorted(cache.items()):
        st = tijd(c.get("start"))
        if uuid not in sessies and st and van <= st < tot:
            voeg({"uuid": uuid, "start_time": c["start"], "id": c.get("nummer"), "topic": c.get("onderwerp"),
                  "end_time": c.get("einde"), "duration": c.get("duur"), "host_id": c.get("host_id"),
                  "participants_count": c.get("aantal")}, "eerder gezien", deelname=bool(c.get("deelname")))

    # Eindtijd en deelnemers per sessie. Elke sessie met een einde komt in de cache (ZOO-01); vast (niet meer opnieuw
    # gelezen) wordt ze pas als ze meer dan een dag afgelopen is en haar deelnemers bekend zijn. Een oudere cache kende
    # alleen vaste sessies, daarom is een sessie zonder die vlag vast.
    for uuid, s in sessies.items():
        c = cache.get(uuid)
        if c and c.get("vast", True):
            for k, v in _herstel(c).items():
                if k not in ("bronnen", "deelname", "vast") and v not in (None, ""):
                    s[k] = v
            continue
        if s["einde"] is None or s["duur"] is None or not s["host_id"]:
            try:
                d = Z.lees(f"/past_meetings/{Z.uuid_pad(uuid)}")
            except Exception:  # noqa: BLE001
                d = None
            if d:
                s["einde"] = s["einde"] or tijd(d.get("end_time"))
                s["duur"] = s["duur"] if s["duur"] is not None else (int(d["duration"]) if d.get("duration") is not None else None)
                s["host_id"] = s["host_id"] or d.get("host_id") or ""
                s["nummer"] = s["nummer"] or str(d.get("id") or "")
                s["onderwerp"] = s["onderwerp"] or d.get("topic") or ""
                if s["aantal"] is None and d.get("participants_count") is not None:
                    s["aantal"] = int(d["participants_count"])
        try:
            s["deelnemers"] = deelnemers_uit(Z.lees_alles(f"/past_meetings/{Z.uuid_pad(uuid)}/participants", {"page_size": 300}, "participants"))
        except Exception:  # noqa: BLE001
            s["deelnemers"] = None
        if c:
            # wat een eerdere ronde wel las en deze niet, is beter dan onbekend
            for k, v in _herstel(c).items():
                if k not in ("bronnen", "deelname", "vast") and s.get(k) in (None, "") and v not in (None, ""):
                    s[k] = v
        if s["einde"] is None and s["duur"]:
            s["einde"] = s["start"] + timedelta(minutes=s["duur"])
        if s["einde"]:
            cache[uuid] = dict(_bewaar(s), vast=klok - s["einde"] > timedelta(days=1) and s["deelnemers"] is not None)
    grens = (van - timedelta(days=2)).isoformat()
    for uuid in [u for u, c in cache.items() if (c.get("start") or "") < grens]:
        del cache[uuid]
    return {"ik": ik, "sessies": sessies, "bronnen": bronnen, "opnamen": opnamen, "laatste": laatste}


# ------------------------------------------------------------------ chat ---
def chat_sleutel(s):
    """De sleutel van een chatgesprek in zijn rijen zoom:chat:<sleutel>:<dag>: het adres van de ander, anders het kanaal,
    anders de naam."""
    naam = s.get("name") or ("gesprek" if s.get("type") == "1:1" else "kanaal")
    return re.sub(r"[^a-z0-9@._-]+", "-", (s.get("peer_contact_email") or s.get("channel_id") or naam).lower())[:80]


OUDERDOM_GROEPEN = ("jonger dan 2 dagen", "2 tot 7 dagen", "ouder dan 7 dagen", "zonder tijd")


def ouderdom_groep(tijd, tot):
    """Overleg 26-10-2026 X3: hoe oud het laatste bericht van een onleesbaar chatgesprek is (last_message_sent_time,
    gemeten 26-10-2026 op elke sessie), zonder naam. Zo is te zien of de 404's oude of nieuwe gesprekken zijn; een
    oorzaak leid ik er niet uit af."""
    try:
        t = datetime.fromisoformat(str(tijd).replace("Z", "+00:00"))
        dagen = (tot - t).total_seconds() / 86400
    except (TypeError, ValueError):
        return "zonder tijd"
    return "jonger dan 2 dagen" if dagen < 2 else "2 tot 7 dagen" if dagen <= 7 else "ouder dan 7 dagen"


def kanaal_soort(naam):
    """Overleg 26-10-2026 X1: (afdeling, privé) van een groepskanaal. Werk alleen als de naam een werkafdeling noemt en
    niets van privé; een kanaal zonder afdeling, met de afdeling prive of met 'priv' in de naam is privé."""
    afd = afdeling_uit_naam(naam) or ("regie" if "automation" in (naam or "").lower() else "onbekend")
    return afd, afd in ("onbekend", "prive") or is_prive_naam(naam) or "priv" in (naam or "").casefold()


def chat_rijen(ik, van_dag, tot_dag, personen, domeinen, ouderdom=None, soorten=None):
    """Eén rij per chatgesprek per dag: aantallen en tijden, nooit de inhoud. Een 1:1 is werk als de ander bekend is op
    e-mailadres of teamdomein (H2), anders privé, bij twijfel privé; zonder personentabel is elke 1:1 privé (T26). De
    naam van een privé-1:1 gaat naar het masker van het bord.
    Altijd met de app van de stack, nooit met de leesapp (EIGEN-1, 13.6): de leesapp krijgt het recht op chatberichten
    bewust niet, en zoom.py weigert /messages met de leesapp.
    RZ10: dit leest alleen wat de ronde schrijft; de telling komt daarna uit de gesprekkentabel (chat_tellen). Geeft
    (rijen, redenen): waarom deze ronde niet elk gesprek van de sessielijst las, zonder namen. 'N chatgesprek(ken) niet
    leesbaar' is een 404 op de berichten: een verlaten kanaal, een contact dat weg is, of iets anders, dat zegt Zoom niet
    (live 22-10-2026 maakte zo een enkel oud gesprek de hele chat onbekend). 'N chatgesprek(ken) zonder bestemming' is
    een sessie zonder adres of kanaal (RZ10-01: die werd stil overgeslagen). Een fout van de sessielijst, of een andere
    fout dan 404, gaat door: dan las deze ronde de chat niet.
    Het venster gaat in stukken van hoogstens STUK_DAGEN - 1 Brusselse dagen, die op een Brusselse dag aansluiten
    (WACHT-1): zo komt elke dag uit een stuk, en blijft een stuk ook over de overgang naar wintertijd (een dag van 25 uur)
    korter dan STUK_DAGEN dagen in UTC (Codex, toets 1). Een gesprek dat in twee stukken staat, telt een keer als niet
    leesbaar of zonder bestemming; binnen een stuk telt elke sessie.
    soorten (WACHT-6, een Counter): per (reden, soort) hoeveel gesprekken, met soort 1:1 of kanaal, nooit een naam: zo is
    te zien wat voor gesprekken Zoom niet geeft, voor iemand een oorzaak zoekt."""
    rijen, weg, zonder, weg_tijden = [], Counter(), Counter(), defaultdict(list)
    laatste = (date.fromisoformat(tot_dag) - timedelta(days=1)).isoformat()
    for a, b in stukken(van_dag, laatste, STUK_DAGEN - 1):
        # Zoom leest from en to van de chat alleen als datum met tijd in UTC: met alleen een datum negeert hij ze en geeft
        # /messages enkel de laatste dag terug (gemeten 22-10-2026: voor 20-10 36 berichten met tijd, 0 zonder).
        tot = (date.fromisoformat(b) + timedelta(days=1)).isoformat()
        venster = {"from": zoom_tijd(dag_grenzen(a)[0]), "to": zoom_tijd(dag_grenzen(tot)[0] - timedelta(seconds=1))}
        rijen += _chat_stuk(ik, venster, personen, domeinen, weg, zonder, weg_tijden)
    if ouderdom is not None:
        for k, n in sorted(weg.items()):
            ouderdom.extend(weg_tijden[k][:n])
    if soorten is not None:
        for (soort, *_), n in weg.items():
            soorten[("niet leesbaar", soort)] += n
        for (soort, *_), n in zonder.items():
            soorten[("zonder bestemming", soort)] += n
    return rijen, [f"{n} chatgesprek(ken) {wat}" for n, wat in ((sum(weg.values()), "niet leesbaar"), (sum(zonder.values()), "zonder bestemming")) if n]


def _chat_stuk(ik, venster, personen, domeinen, weg, zonder, weg_tijden):
    """De chatrijen van een stuk van het venster (chat_rijen). weg en zonder: per sessie (soort, sleutel, naam en tijd
    van het laatste bericht, wat Zoom over een sessie geeft, los van het venster) het hoogste aantal met een 404 of
    zonder bestemming in een stuk, over de stukken heen: zo telt elke sessie in een stuk, een sessie die in twee
    stukken staat een keer, en twee sessies met dezelfde sleutel in twee stukken twee keer (Codex, toets 1 en 2).
    weg_tijden: per sessie het laatste bericht van elke onleesbare, voor de ouderdom."""
    sessies = _lijst(f"/chat/users/{ik['id']}/sessions", dict(venster, page_size=50), "sessions", "stack")
    rijen, zonder_hier, weg_hier, tijd_hier = [], Counter(), Counter(), defaultdict(list)
    for s in sessies:
        p = dict(venster, page_size=50)
        een_op_een = s.get("type") == "1:1"
        soort = "1:1" if een_op_een else "kanaal"
        if een_op_een:
            p["to_contact"] = s.get("peer_contact_email", "")
        else:
            p["to_channel"] = s.get("channel_id", "")
        sessie = (soort, chat_sleutel(s), s.get("name") or "", str(s.get("last_message_sent_time") or ""))
        if not (p.get("to_contact") or p.get("to_channel")):
            zonder_hier[sessie] += 1
            continue
        berichten = Z.lees_alles(f"/chat/users/{ik['id']}/messages", p, "messages", "stack")
        if berichten is None:
            weg_hier[sessie] += 1
            tijd_hier[sessie].append(s.get("last_message_sent_time"))
            continue
        if not berichten:
            continue
        naam = s.get("name") or ("gesprek" if een_op_een else "kanaal")
        per_dag = defaultdict(list)
        for m in berichten:
            per_dag[fw.belgisch(m.get("date_time", ""))[:10]].append(m)
        if een_op_een:
            peer = (s.get("peer_contact_email") or "").lower()
            persoon, ok = bekend(personen, peer, domeinen)
            if persoon:
                naam = persoon["naam"]
            elif "@" in naam:
                naam = naam.split("@")[0].replace(".", " ").replace("-", " ").title()
            afd = (persoon or {}).get("afdeling", "") or "onbekend"
            prive = personen is None or not ok or is_prive_naam(naam) or "priv" in afd.lower()
            zeker = "hoog" if persoon else ("middel" if ok else "laag")
            waarom = ("1:1; personentabel niet gelezen: privé" if personen is None else
                      "1:1; bekend op e-mailadres uit de personentabel" if persoon else
                      "1:1; teamadres, niet in de personentabel" if ok else
                      "1:1; niet bekend op e-mailadres of teamdomein: bij twijfel privé")
            if prive and not vast_woord(naam):
                ag.prive([naam])         # een 1:1 zonder naam heet 'gesprek': dat woord nooit in het masker (ZOO-06)
        else:
            # Overleg 26-10-2026 X1: een kanaal zonder afdeling in de naam (een familiegroep) is niet bewezen werk: privé.
            afd, prive = kanaal_soort(naam)
            zeker = "middel" if prive else "hoog"
            waarom = (KANAAL_ONBEKEND + ": bij twijfel privé" if prive else
                      "kanaal; afdeling uit de kanaalnaam")
            if prive and not vast_woord(naam):
                ag.prive([naam])
        sleutel = chat_sleutel(s)
        for dag, lijst in sorted(per_dag.items()):
            if not dag:
                continue
            tijden = sorted(fw.belgisch(m.get("date_time", ""))[11:16] for m in lijst)
            van_mehdi = sum(1 for m in lijst if (m.get("sender") or "").lower() == ik["email"])
            rijen.append({"uniek": f"zoom:chat:{sleutel}:{dag}", "datum": dag, "start": tijden[0] if tijden else "", "minuten": 0,
                          "personen": naam, "bedrijf": "", "afdeling": afd,
                          "thema": f"Zoom-chat: {len(lijst)} bericht(en), {van_mehdi} van Mehdi, {tijden[0] if tijden else ''} tot {tijden[-1] if tijden else ''}",
                          "project": "", "prive": prive, "zekerheid": zeker, "waarom": waarom, "archief": "", "link": "",
                          "opgenomen_door": "Zoom-chat", "bron": "zoom"})
    for k, n in zonder_hier.items():
        zonder[k] = max(zonder[k], n)
    for k, n in weg_hier.items():
        if n > weg[k]:
            weg[k], weg_tijden[k] = n, tijd_hier[k]
    return rijen


def chat_tellen(w):
    """RZ10 (22-10-2026), een bron voor de chattelling: de gesprekkentabel, na het schrijven. Per Brusselse dag van het
    venster de rijen zoom:chat:<sleutel>:<dag>, langs bord.db_lees, met de regels van De Regisseur (gesprekken_lees):
    bron fathom, zoom of plaud (een oude chatrij kan bron fathom hebben: de upsert zet de bron niet opnieuw), geen
    dubbel_van buiten:..., en privé is de kolom prive of afdeling prive (RZ3-01). Het aantal berichten komt uit het thema.
    Een rij wordt nooit verwijderd of leeggemaakt, dus het cijfer van een dag daalt niet door een slechtere ronde: een
    gesprek dat Zoom nu niet geeft of dat uit de sessielijst verdween, telt met zijn rijen van eerdere rondes mee.
    Elke leesbare telling is een ondergrens van geziene rijen, met de leesredenen als informatie. Een rij zonder
    herkenbaar berichtenaantal maakt berichten_gezien onbekend in plaats van nul. Alleen een onleesbare gesprekkentabel
    maakt de chat onbekend. Zet w['chat_dag'] en w['chat_stand']."""
    dagtel = defaultdict(lambda: {"berichten_gezien": 0, "gesprekken": 0, "prive_gezien": 0})
    try:
        rijen = bord.db_lees("SELECT uniek, datum, thema, prive, COALESCE(afdeling, '') AS afdeling, "
                             "COALESCE(dubbel_van, '') AS dubbel_van FROM gesprek_log WHERE datum BETWEEN ? AND ? "
                             "AND uniek LIKE 'zoom:chat:%' AND bron IN ('fathom', 'zoom', 'plaud')", (w["eerste"], w["vandaag"]))
    except bord.BordOnbekend:
        w["chat_dag"], w["chat_stand"] = {}, {"telling": "onbekend", "redenen": w["chat_redenen"] + ["gesprekkentabel niet gelezen"]}
        return
    for r in rijen:
        if not r["uniek"].startswith("zoom:chat:") or r["dubbel_van"].startswith("buiten:"):
            continue
        m, c = CHAT_THEMA.match(r["thema"] or ""), dagtel[r["datum"]]
        if m and c["berichten_gezien"] is not None:
            c["berichten_gezien"] += int(m.group(1))
        elif not m:
            c["berichten_gezien"] = None
        c["gesprekken"] += 1
        c["prive_gezien"] += 1 if r["prive"] or str(r["afdeling"]).strip().casefold() in ("prive", "privé") else 0
    w["chat_dag"] = dict(dagtel)
    w["chat_stand"] = {"telling": "ondergrens", "redenen": list(w["chat_redenen"])}


# ---------------------------------------------------------------- fathom ---
def opname_uit(g, map_=""):
    """Een opname van Fathom: recording_id, het meetingnummer uit meeting_url (geen Zoom-link: geen nummer), begin en
    einde, of ze van Mehdi's eigen account is (exact adres uit fathom.MEHDI_FATHOM_ADRESSEN), en de privévlag van De
    Fathomwacht (onbekend telt als privé). RZ3-01: ook afdeling prive in de herkenning is privé, met de regel van De
    Fathomwacht (fw.is_prive), ook bij prive=false; tot 22-10-2026 las ik alleen herkenning.prive, en dan kwamen naam en
    onderwerp van zo'n gesprek in de dagregel (inhoud.werk) en in de export."""
    rid = str(g.get("recording_id") or "")
    start, einde = tijd(g.get("recording_start_time")), tijd(g.get("recording_end_time"))
    if not rid or not start or not einde:
        return None
    m = NUMMER.search(str(g.get("meeting_url") or ""))
    door = g.get("recorded_by") if isinstance(g.get("recorded_by"), dict) else {}
    email = (door.get("email") or "").strip().lower()
    herk = g.get("herkenning") if isinstance(g.get("herkenning"), dict) else {}
    # EIGEN-3: alleen op een exact adres. Een deelstuk ('h-architects', 'mch@') maakte de opname van een collega eigen.
    return {"rid": rid, "uniek": f"fathom:{rid}", "nummer": m.group(1) if m else "", "start": start, "einde": einde,
            "eigen": email in fathom.MEHDI_FATHOM_ADRESSEN,
            "prive": herk.get("prive") is not False or fw.is_prive(herk), "thema": str(herk.get("thema") or "")[:80],
            "map": map_, "archief": bool(map_)}


def fathom_lezen(eerste_dag, laatste_dag):
    """Z5: de opnames uit het archief van De Fathomwacht (fathom-data/<JJJJ-MM-DD UUMM titel>/gesprek.json; de mapnaam
    is Brusselse tijd), voor de dagen [eerste - 1, laatste + 1]. Geeft (opnames, onleesbaar, toestand). Een gesprek.json
    die niet te lezen is, is onbekend, nooit 'geen Fathom' (T17); ze komt als laatste (fathom_wacht.bewaar)."""
    lo = (date.fromisoformat(eerste_dag) - timedelta(days=1)).isoformat()
    hi = (date.fromisoformat(laatste_dag) + timedelta(days=1)).isoformat()
    try:
        namen = os.listdir(FATHOM_DATA)
    except OSError as e:
        return [], [], f"fout: archief niet leesbaar ({type(e).__name__})"
    opnames, onleesbaar = [], []
    for naam in sorted(namen):
        m = re.match(r"^(\d{4}-\d{2}-\d{2})(?: (\d{4}))?", naam)
        if not m or not (lo <= m.group(1) <= hi):
            continue
        map_ = os.path.join(FATHOM_DATA, naam)
        gj = os.path.join(map_, "gesprek.json")
        if not os.path.exists(gj):
            continue
        try:
            with open(gj, encoding="utf-8") as f:
                g = json.load(f)
            o = opname_uit(g, map_) if isinstance(g, dict) else None
        except (OSError, ValueError):
            o = None
        if o:
            opnames.append(o)
        else:
            onleesbaar.append({"map": map_, "dag": m.group(1), "tijd": m.group(2) or ""})
    return opnames, onleesbaar, "ok"


def fathom_api(sinds):
    """De Fathom-API zonder transcript, over alle sleutels: (opnames, toestand). Mislukt ze, dan is ze onbekend."""
    if not fathom.beschikbaar():
        return [], "niet ingesteld"
    try:
        items = fathom.gesprekken(sinds.strftime("%Y-%m-%dT%H:%M:%SZ"), met_transcript=False)
    except Exception as e:  # noqa: BLE001
        return [], f"fout: {type(e).__name__}"
    return [o for o in (opname_uit(g) for g in items or [] if isinstance(g, dict)) if o], "ok"


# ------------------------------------------------------------- koppelen ---
def _groepen(paren):
    """Samenhangende groepen uit paren (a, b): wie elkaar via een paar raakt, zit in dezelfde groep."""
    ouder = {}

    def wortel(x):
        while ouder.setdefault(x, x) != x:
            ouder[x] = ouder[ouder[x]]
            x = ouder[x]
        return x
    for a, b in paren:
        ouder[wortel(a)] = wortel(b)
    uit = defaultdict(list)
    for x in list(ouder):
        uit[wortel(x)].append(x)
    return list(uit.values())


def _hongaars(kost):
    """De Hongaarse methode: de toewijzing met de laagste totale kost in een vierkante matrix (per rij de kolom)."""
    n = len(kost)
    oneindig = float("inf")
    u, v, p, weg = [0] * (n + 1), [0] * (n + 1), [0] * (n + 1), [0] * (n + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minv, gebruikt = [oneindig] * (n + 1), [False] * (n + 1)
        while True:
            gebruikt[j0] = True
            i0, delta, j1 = p[j0], oneindig, 0
            for j in range(1, n + 1):
                if not gebruikt[j]:
                    cur = kost[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], weg[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(n + 1):
                if gebruikt[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = weg[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    uit = [0] * n
    for j in range(1, n + 1):
        if p[j]:
            uit[p[j] - 1] = j - 1
    return uit


def koppel(sessies, opnames, ik, klok, van=None, rapport_ok=False):
    """X2: per meetingnummer een maximale gewogen een-op-een-toewijzing tussen sessies en opnames die elkaar meer dan 0
    seconden overlappen. Gewicht: 10^9 per koppeling, plus 10^6 als de opname van Mehdi's eigen Fathom-account is, plus
    de overlap in seconden. Zo wint eerst het grootste aantal koppelingen, dan het eigen account, dan de totale overlap;
    exact, met de Hongaarse methode per groep sessies en opnames die elkaar raken (die groepen zijn klein). Een opname
    van een ander account komt alleen in aanmerking als Mehdi volgens Zoom in die sessie zat (13.1).

    Daarna: een opname die nog een gekoppelde sessie overlapt, is een dubbel van de leidende opname van die sessie. Een
    opname van een ander account uit een andere ruimte telt niet voor Mehdi (buiten: andere-ruimte), maar alleen als het
    rapport gelezen is (rapport_ok): pastJoined is de enige bron voor meetings van anderen waar hij aan deelnam, dus
    zonder rapport is 'een andere ruimte' onbekend en blijft de opname ongemoeid (ZOO-03). In zijn eigen ruimte telt ze
    ook niet als Zoom zeker zegt dat hij er niet bij was (buiten: zonder-mehdi). Zonder Zoom-nummer (een ander platform,
    of geen link) kan Zoom niet zeggen dat hij erbij was, dus telt ze ook niet (buiten: zonder-zoom, BAS-03); dat hangt
    niet af van het rapport. Een eigen opname met zijn nummer zonder Zoom-sessie is een gesprek dat alleen Fathom zag:
    een teller, geen rij (J10, M10); een eigen opname zonder nummer blijft ongemoeid en telt.
    Buiten en gezien alleen voor opnames die in het Zoom-venster beginnen (start >= van): het Fathom-venster heeft een
    dag marge, en die dient alleen om te koppelen. Een opname op die randdag heeft haar sessie niet meer in het venster
    en kreeg anders buiten, terwijl ze dat gesprek droeg (ZOO-02).
    Geeft {"leidend": {uuid: opname}, "dubbel": {rid: (uuid, leidende rid)}, "buiten": {rid: reden},
    "gezien": [[leider, ...], ...]}."""
    per_nummer = defaultdict(lambda: ([], []))
    for s in sessies:
        if s.get("nummer"):
            per_nummer[s["nummer"]][0].append(s)
    for o in opnames:
        if o.get("nummer"):
            per_nummer[o["nummer"]][1].append(o)
    per_uuid = {s["uuid"]: s for s in sessies}
    per_rid = {o["rid"]: o for o in opnames}
    randen = {}
    for ss, oo in per_nummer.values():
        for s in ss:
            for o in oo:
                ov = overlap(s["start"], s["einde"] or klok, o["start"], o["einde"])
                if ov > 0 and (o["eigen"] or mehdi_erbij(s, ik)):
                    randen[(s["uuid"], o["rid"])] = GEWICHT_KOPPELING + (GEWICHT_EIGEN if o["eigen"] else 0) + int(ov)
    leidend = {}
    for groep in _groepen((("s", u), ("o", r)) for u, r in randen):
        rij = sorted((per_uuid[k[1]] for k in groep if k[0] == "s"), key=lambda s: (s["start"], s["uuid"]))
        kol = sorted((per_rid[k[1]] for k in groep if k[0] == "o"), key=lambda o: (o["start"], o["rid"]))
        n = max(len(rij), len(kol))
        gewicht = [[randen.get((rij[i]["uuid"], kol[j]["rid"]), 0) if i < len(rij) and j < len(kol) else 0
                    for j in range(n)] for i in range(n)]
        for i, j in enumerate(_hongaars([[-g for g in regel] for regel in gewicht])):
            if i < len(rij) and j < len(kol) and gewicht[i][j] > 0:
                leidend[rij[i]["uuid"]] = kol[j]
    gekoppeld = {o["rid"] for o in leidend.values()}
    dubbel = {}
    for ss, oo in per_nummer.values():
        for o in oo:
            if o["rid"] in gekoppeld:
                continue
            raak = [(overlap(s["start"], s["einde"] or klok, o["start"], o["einde"]), s["uuid"]) for s in ss if s["uuid"] in leidend]
            raak = [x for x in raak if x[0] > 0]
            if raak:
                uuid = max(raak)[1]
                dubbel[o["rid"]] = (uuid, leidend[uuid]["rid"])
    buiten, rest = {}, []
    mijn = ({ik["pmi"]} if ik and ik["pmi"] else set()) | {s["nummer"] for s in sessies if s.get("nummer")}
    for o in opnames:
        if o["rid"] in gekoppeld or o["rid"] in dubbel or not (ik and ik["pmi"]):
            continue
        if van is not None and o["start"] < van:
            continue
        if not o["eigen"]:
            if o["nummer"] and o["nummer"] not in mijn:
                if rapport_ok:
                    buiten[o["rid"]] = "andere-ruimte"
            elif o["nummer"]:
                raak = [s for s in per_nummer[o["nummer"]][0] if overlap(s["start"], s["einde"] or klok, o["start"], o["einde"]) > 0]
                if raak and all(s["deelnemers"] is not None and not mehdi_erbij(s, ik) for s in raak):
                    buiten[o["rid"]] = "zonder-mehdi"
            else:
                buiten[o["rid"]] = "zonder-zoom"
        elif o["nummer"] in mijn:
            rest.append(o)
    paren = [(a["rid"], b["rid"]) for a in rest for b in rest
             if a["rid"] <= b["rid"] and a["nummer"] == b["nummer"] and (a is b or overlap(a["start"], a["einde"], b["start"], b["einde"]) > 0)]
    gezien = []
    for groep in _groepen(paren):
        leden = sorted((per_rid[r] for r in groep), key=lambda o: (-(o["einde"] - o["start"]).total_seconds(), o["rid"]))
        gezien.append(leden)
    gezien.sort(key=lambda g: g[0]["start"])
    return {"leidend": leidend, "dubbel": dubbel, "buiten": buiten, "gezien": gezien}


def koppel_wensen(k):
    """Wat er na de koppeling op de Fathom-rijen hoort te staan. Alleen opnames in het archief: hun rij bestaat, want
    De Fathomwacht schrijft eerst het archief en dan de rij. Velden van De Fathomwacht raak ik niet aan."""
    wens = {}
    for uuid, o in k["leidend"].items():
        if o["archief"]:
            wens[o["uniek"]] = {"sessie": f"zoom:meeting:{uuid}", "dubbel_van": ""}
    leiders = {o["rid"]: o for o in k["leidend"].values()}
    for rid, (uuid, leider) in k["dubbel"].items():
        o = k["_opnames"][rid]
        if o["archief"] and leiders[leider]["archief"]:
            wens[o["uniek"]] = {"sessie": f"zoom:meeting:{uuid}", "dubbel_van": f"fathom:{leider}"}
    for rid, reden in k["buiten"].items():
        if k["_opnames"][rid]["archief"]:
            wens[f"fathom:{rid}"] = {"dubbel_van": f"buiten:{reden}"}
    for groep in k["gezien"]:
        if not groep[0]["archief"]:
            continue
        wens[groep[0]["uniek"]] = {"dubbel_van": ""}
        for o in groep[1:]:
            if o["archief"]:
                wens[o["uniek"]] = {"dubbel_van": groep[0]["uniek"]}
    return wens


def rijen_lezen(unieks, velden="uniek, sessie, dubbel_van"):
    """Rijen van de gesprekkentabel langs de alleen-lezende weg (bord.db_lees). BordOnbekend gaat door: onbekend is
    niet 'staat er niet'."""
    uit = {}
    unieks = list(unieks)
    for i in range(0, len(unieks), 400):
        deel = unieks[i:i + 400]
        for rij in bord.db_lees(f"SELECT {velden} FROM gesprek_log WHERE uniek IN ({','.join('?' * len(deel))})", tuple(deel)):
            uit[rij["uniek"]] = rij
    return uit


def klopt(rij, wens):
    return rij is not None and all((rij.get(k) or "") == v for k, v in wens.items())


def koppel_schrijven(wens, ronde=frozenset()):
    """Z7: de koppeling op de Fathom-rijen via /api/gesprekken/koppel, alleen wat verandert. Daarna terug langs een
    andere weg (bord.db_lees): wat daar niet staat, telt niet als gekoppeld (L32).
    Grendel (ZOO-02): nooit buiten:... op een rij die al bij een sessie hoort die deze ronde niet zag (ronde: de unieks
    zoom:meeting:<uuid> van deze ronde). Die rij draagt een gesprek dat buiten het venster valt; met buiten telde geen
    enkele rij van dat gesprek nog. Is het teruglezen vooraf onbekend, dan gaat geen enkele buiten mee.
    Geeft (bevestigd, gestuurd, gehouden): bevestigd is de set unieks die staan zoals gewenst, of None als het
    teruglezen onbekend is; gehouden de buiten-wensen die de grendel tegenhield (die rijen blijven zoals ze waren)."""
    if not wens:
        return set(), 0, set()
    try:
        huidig = rijen_lezen(wens)
    except bord.BordOnbekend:
        huidig = None
    gehouden = {u for u, v in wens.items() if (v.get("dubbel_van") or "").startswith("buiten:")
                and (huidig is None or (huidig.get(u) or {}).get("sessie") not in ("", None, *ronde))}
    wens = {u: v for u, v in wens.items() if u not in gehouden}
    te_sturen = [dict(uniek=u, **v) for u, v in sorted(wens.items()) if huidig is None or not klopt(huidig.get(u), v)]
    if te_sturen:
        bord.call("/api/gesprekken/koppel", {"koppelingen": te_sturen})
    try:
        na = rijen_lezen(wens) if wens else {}
    except bord.BordOnbekend:
        return None, len(te_sturen), gehouden
    return {u for u, v in wens.items() if klopt(na.get(u), v)}, len(te_sturen), gehouden


# ------------------------------------------------------------- vangnet ---
def achtervoegsel(uuid):
    return hashlib.sha1(uuid.encode()).hexdigest()[:8]


def vangnet_mappen():
    """M11: de vangnetmappen per achtervoegsel [sha1(uuid)[:8]], niet op de volle naam: een andere starttijd of een nieuw
    onderwerp geeft zo nooit een tweede map voor dezelfde sessie."""
    uit = {}
    try:
        namen = os.listdir(ZOOM_DATA)
    except OSError:
        return uit
    for naam in namen:
        m = re.search(r" \[([0-9a-f]{8})\]$", naam)
        if m and not naam.startswith("."):
            uit[m.group(1)] = os.path.join(ZOOM_DATA, naam)
    return uit


def schoon_onderwerp(s):
    """Het onderwerp zoals het in de mapnaam staat: zonder tekens die een pad breken, hoogstens 60 tekens."""
    onderwerp = fw.VERBODEN_TEKEN.sub(" ", s.get("onderwerp") or "").replace("\N{EN DASH}", "-").replace("\N{EM DASH}", "-")
    return re.sub(r"\s+", " ", onderwerp).strip(" .-")[:60]


def mapnaam(s, ik):
    """'JJJJ-MM-DD UUMM Zoom vaste vergaderruimte [abcd1234]' of 'JJJJ-MM-DD UUMM Zoom <onderwerp> [abcd1234]'."""
    start = brussel(s["start"]).strftime("%Y-%m-%d %H%M")
    if ruimte_van(s, ik) == "vaste vergaderruimte":
        midden = "Zoom vaste vergaderruimte"
    else:
        midden = ("Zoom " + schoon_onderwerp(s)).strip()
    return f"{start} {midden} [{achtervoegsel(s['uuid'])}]"


def vtt_naar_fathom(vtt):
    """WEBVTT van Zoom naar de vorm van Fathom (transcript.json): [{speaker: {display_name}, text, timestamp}], met
    timestamp 'UU:MM:SS' de afstand tot het begin van de opname. Zoom zet de spreker voor de tekst ('Naam: tekst')."""
    uit = []
    for blok in re.split(r"\r?\n\s*\r?\n", (vtt or "").replace("\N{ZERO WIDTH NO-BREAK SPACE}", "")):
        regels = [r.strip() for r in blok.splitlines() if r.strip()]
        i = next((k for k, r in enumerate(regels) if "-->" in r), None)
        if i is None or i + 1 >= len(regels):
            continue
        m = re.match(r"(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,]\d+)?\s*-->", regels[i])
        if not m:
            continue
        uur, minuut, seconde = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
        tekst = " ".join(regels[i + 1:])
        spreker, zin = "", tekst
        kop = re.match(r"^([^:]{1,60}):\s+(.*)$", tekst)
        if kop:
            spreker, zin = kop.group(1).strip(), kop.group(2).strip()
        uit.append({"speaker": {"display_name": spreker}, "text": zin,
                    "timestamp": f"{uur:02d}:{minuut:02d}:{seconde:02d}"})
    return uit


def _schrijf(pad, data):
    with open(pad, "wb") as f:
        f.write(data)


def vangnet_schrijven(s, bestand, ik, klok):
    """Z6, I4: de Zoom-tekst naar zoom-data/<map>/: transcript.vtt (de bron), transcript.json (vorm van Fathom) en als
    laatste zoom.json, eerst in een tijdelijke map en dan in een keer op zijn plaats (os.replace). zoom.json is altijd
    privé (X1) en draagt nooit een link, toegangscode of Fathom-id. Nooit gesprek.json: De Archivaris leest elke
    gesprek.json onder mijnagents-data. Geeft het pad van de map."""
    vtt = Z.download(bestand["id"])
    start_opname = tijd(bestand.get("start")) or s["start"]
    meta = {"uuid": s["uuid"], "nummer": s.get("nummer") or "", "ruimte": ruimte_van(s, ik),
            "start_utc": s["start"].isoformat(), "einde_utc": s["einde"].isoformat() if s["einde"] else "",
            "start_brussel": brussel(s["start"]).isoformat(), "einde_brussel": brussel(s["einde"]).isoformat() if s["einde"] else "",
            "recording_start": start_opname.isoformat(), "minuten": minuten(s), "prive": True, "stand": "tekst bewaard",
            "bestandsid": bestand["id"], "opgehaald_ts": klok.isoformat()}
    os.makedirs(ZOOM_DATA, mode=0o700, exist_ok=True)
    tijdelijk = tempfile.mkdtemp(prefix=".bezig-", dir=ZOOM_DATA)
    try:
        _schrijf(os.path.join(tijdelijk, "transcript.vtt"), vtt)
        _schrijf(os.path.join(tijdelijk, "transcript.json"),
                 json.dumps(vtt_naar_fathom(vtt.decode("utf-8", "replace")), ensure_ascii=False, indent=1).encode())
        _schrijf(os.path.join(tijdelijk, "zoom.json"), json.dumps(meta, ensure_ascii=False, indent=1).encode())
        doel = os.path.join(ZOOM_DATA, mapnaam(s, ik))
        os.replace(tijdelijk, doel)
    except BaseException:
        shutil.rmtree(tijdelijk, ignore_errors=True)
        raise
    return doel


def kandidaat(s, x, klok):
    """Kan een onleesbare gesprek.json bij deze sessie horen? De mapnaam geeft de Brusselse start van de opname, op de
    minuut; Fathom start na het begin van de sessie en voor haar einde. Bestaat die Brusselse tijd twee keer (de klok
    gaat terug), dan is het een kandidaat als een van beide uren past: bij twijfel onbekend (RZ2-05)."""
    if x["dag"] != dag_van(s["start"]):
        return False
    if not x["tijd"]:
        return True
    return any(s["start"] - timedelta(minutes=1) <= t <= (s["einde"] or klok)
               for t in utc_tijden(x["dag"], f"{x['tijd'][:2]}:{x['tijd'][2:]}"))


def fathom_stand(s, w, k, bevestigd, klok):
    """Heeft Fathom deze sessie: ('ja' | 'api' | 'onbekend' | 'nee', reden). 'nee' alleen als API en archief gelezen zijn
    en ze niet hebben, of als de API 24 uur na het einde nog onbekend is (Z6). Onbekend is nooit 'geen Fathom'."""
    o = k["leidend"].get(s["uuid"])
    if o:
        if not o["archief"]:
            return "api", "Fathom-archief volgt"
        if bevestigd is None:
            return "onbekend", "koppeling niet terug te lezen"
        return ("ja", "") if o["uniek"] in bevestigd else ("onbekend", "koppeling niet bevestigd")
    if any(kandidaat(s, x, klok) for x in w["onleesbaar"]):
        return "onbekend", "Fathom-archief onleesbaar"
    if w["bronnen"]["fathom-archief"] != "ok":
        return "onbekend", "Fathom-archief niet leesbaar"
    if w["bronnen"]["fathom-api"] != "ok":
        if s["einde"] and klok >= s["einde"] + TEKST_WACHT:
            return "nee", "Fathom-API na 24 uur onbekend"
        return "onbekend", "Fathom onbekend"
    return "nee", ""


def toestand(s, fs, w, klok, mappen):
    """De toestand van een sessie (Z5, Z6), zonder iets te schrijven: (toestand, reden, transcriptbestand of None)."""
    stand, reden = fs
    if stand == "ja":
        return "fathom", "", None
    if stand == "api":
        return "wacht: Fathom-archief volgt", reden, None
    if achtervoegsel(s["uuid"]) in mappen:
        return "vangnet: tekst bewaard", "", None
    if stand == "onbekend":
        return "onbekend", reden, None
    if w["bronnen"]["opnames"] != "ok":
        return "onbekend", "opnames niet leesbaar", None
    if not s["einde"] or klok < s["einde"] + WACHT_NA_EINDE:
        return "wacht: opname in verwerking", "opname in verwerking", None
    rec = w["opnamen"].get(s["uuid"])
    if rec is None:
        return "zonder opname", "", None
    if not rec["bestanden"] or any(b["status"] != "completed" for b in rec["bestanden"]):
        return "wacht: opname in verwerking", "opname in verwerking", None
    tekst = next((b for b in rec["bestanden"] if b["soort"] == "TRANSCRIPT"), None)
    if tekst:
        return "vangnet: tekst op te halen", "", tekst
    if klok < s["einde"] + TEKST_WACHT:
        return "wacht: Zoom-tekst nog niet klaar", "Zoom-tekst nog niet klaar", None
    return "vangnet: opname zonder tekst", "", None


# ------------------------------------------------------------ de ronde ---
def personentabel(r=None):
    """De tabel Betrokken personen van De Fathomwacht, van het bord (een plek, N6). Onbekend is niet leeg: dan None,
    een nood, en elke 1:1 en elke sessie met een onbekende is privé (Z9, T26)."""
    try:
        tekst = bord.Agent("fathom-wacht").werkwijze_lezen()
    except bord.WerkwijzeOnbekend:
        if r is not None:
            r.nood("Personentabel van De Fathomwacht niet gelezen", "claude-code")
        return None
    if r is not None:
        r.bron("werkwijze fathom-wacht (personentabel)", tekst)
    return fw.personen_uit_werkwijze(tekst)


def staat_lezen():
    try:
        with open(STAAT, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def staat_schrijven(staat):
    """Atomisch: een tijdelijk bestand naast de staat, dan os.replace (Z9)."""
    os.makedirs(os.path.dirname(STAAT), exist_ok=True)
    fd, tijdelijk = tempfile.mkstemp(prefix=".zoom-wacht-", dir=os.path.dirname(STAAT))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(staat, f, ensure_ascii=False)
        os.replace(tijdelijk, STAAT)
    except BaseException:
        if os.path.exists(tijdelijk):
            os.unlink(tijdelijk)
        raise


def lezen(a, klok, staat, personen, domeinen):
    """Alles wat de ronde nodig heeft, alleen lezend: Zoom (Z4), de chat, Fathom (Z5) en de koppeling (X2)."""
    vandaag = dag_van(klok)
    eerste = (date.fromisoformat(vandaag) - timedelta(days=a.inhaal)).isoformat()
    van, _ = dag_grenzen(eerste)
    w = zoom_lezen(van, klok, staat, klok)
    # de chat: in chat de rijen die deze ronde schrijft, in chat_redenen waarom ze niet alles las; de telling (chat_dag en
    # chat_stand) komt pas na het schrijven uit de gesprekkentabel (chat_tellen, RZ10)
    w.update(vandaag=vandaag, eerste=eerste, chat=[], chat_redenen=[], chat_dag={}, chat_stand=None,
             chat_ouderdom=Counter(), chat_soorten=Counter())
    if w["ik"]:
        try:
            tijden = []
            w["chat"], w["chat_redenen"] = chat_rijen(w["ik"], eerste, (date.fromisoformat(vandaag) + timedelta(days=1)).isoformat(),
                                                      personen, domeinen, tijden, w["chat_soorten"])
            w["chat_ouderdom"] = Counter(ouderdom_groep(t, klok) for t in tijden)   # gemeten vanaf de rondetijd
            w["bronnen"]["chat"] = "ok"
        except Exception as e:  # noqa: BLE001
            w["bronnen"]["chat"] = toestand_van(e)
    else:
        w["bronnen"]["chat"] = w["bronnen"]["rapport"]
    if w["bronnen"]["chat"] != "ok":
        w["chat_redenen"] = [f"chat niet gelezen ({w['bronnen']['chat']})"]
    archief, onleesbaar, w["bronnen"]["fathom-archief"] = fathom_lezen(eerste, vandaag)
    api, w["bronnen"]["fathom-api"] = fathom_api(van - timedelta(days=1))
    rids = {o["rid"] for o in archief}
    w["fathom"] = archief + [o for o in api if o["rid"] not in rids]
    w["onleesbaar"] = onleesbaar
    eigen = Counter(o["nummer"] for o in archief if o["eigen"] and o["nummer"])
    meest = eigen.most_common(1)[0][0] if eigen else ""
    w["identiteit"], w["identiteit_bron"] = identiteit(w["ik"], meest, staat, klok)
    w["identiteit_ok"] = w["identiteit"] == "ok"
    k = koppel(list(w["sessies"].values()), w["fathom"], w["ik"], klok, van=van, rapport_ok=w["bronnen"]["rapport"] == "ok")
    k["_opnames"] = {o["rid"]: o for o in w["fathom"]}
    w["koppeling"] = k
    return w


def identiteit(ik, meest, staat, klok):
    """RZ6-01 (22-10-2026): schrijven mag alleen met een bewezen Zoom-gebruiker; tot dan gold een gebruiker die ik niet
    kon controleren als goed. Bewezen ('ok') is een van drie:
    - fathom: de vaste vergaderruimte van de gebruiker is het nummer dat het vaakst in Mehdi's eigen Fathom-opnames staat;
    - instelling: ZOOM_MEHDI_USER staat en is deze gebruiker (zoom_leesapp.py zet die pas na de eigenaarscontrole);
    - staat: dezelfde gebruiker en ruimte waren in de laatste BEWIJS_GELDIG dagen op Fathom bewezen.
    'anders' is een aangetoond verschil, 'onbekend' kan ik niet bewijzen. Geeft (stand, bron)."""
    if not ik or not ik.get("pmi"):
        return "onbekend", ""
    if meest:
        return ("ok", "fathom") if ik["pmi"] == meest else ("anders", "fathom")
    vast = os.environ.get("ZOOM_MEHDI_USER", "").strip()
    if vast and vast == ik.get("id"):
        return "ok", "instelling"
    vorig = staat.get("identiteit") or {}
    try:
        recent = klok - datetime.fromisoformat(vorig.get("bewezen") or "") <= timedelta(days=BEWIJS_GELDIG)
    except (TypeError, ValueError):
        recent = False
    if recent and vorig.get("id") == ik.get("id") and vorig.get("pmi") == ik["pmi"]:
        return "ok", "staat"
    return "onbekend", ""


def telling(w):
    """Volledig alleen als het rapport ok is, de laatste sessie in de vaste vergaderruimte erin zit en de gebruiker
    de eigenaar van die ruimte is (J9, T20, T21). Geen enkele Zoom-bron leesbaar: onbekend, nooit 0. Anders een
    ondergrens. Geeft (telling, redenen)."""
    if not any(w["bronnen"][b] == "ok" for b in ZOOM_BRONNEN):
        return "onbekend", ["geen bron leesbaar"]
    redenen = []
    if w["bronnen"]["rapport"] != "ok":
        redenen.append("deelnames aan meetings van anderen niet gelezen")
    if w["laatste"] == "ontbreekt":
        redenen.append("laatste PMR-sessie ontbreekt")
    elif w["laatste"] != "ok":
        redenen.append("laatste PMR-sessie niet gelezen")
    if w["identiteit"] == "anders":
        redenen.append("de Zoom-gebruiker is niet de eigenaar van de vaste vergaderruimte")
    elif not w["identiteit_ok"]:
        redenen.append("de Zoom-gebruiker is niet bewezen")
    return ("ondergrens" if redenen else "volledig"), redenen


def beoordelen(w, klok, bevestigd, schrijven, droog, r=None):
    """Per sessie de toestand, het vangnet en privé. Schrijft alleen als dat mag (schrijven en niet droog): dan haalt
    het vangnet de Zoom-tekst op. Geeft een lijst van dicts per sessie."""
    k, ik = w["koppeling"], w["ik"]
    mappen = vangnet_mappen()
    per_sessie = defaultdict(list)
    for uuid, o in k["leidend"].items():
        per_sessie[uuid].append(o)
    for rid, (uuid, _) in k["dubbel"].items():
        per_sessie[uuid].append(k["_opnames"][rid])
    info, timeout_gebruikt = [], False
    for s in sorted(w["sessies"].values(), key=lambda s: (s["start"], s["uuid"])):
        fs = fathom_stand(s, w, k, bevestigd, klok)
        timeout_gebruikt |= fs[1] == "Fathom-API na 24 uur onbekend"
        prive = zoom_prive(s, ik, w["personen"], w["domeinen"]) or any(o["prive"] for o in per_sessie[s["uuid"]])
        if prive:
            # De namen naar het masker van het bord. Het onderwerp niet (ZOO-06): het masker kent geen woordgrens, en een
            # onderwerp als 'Gesprek' of 'Zoom' verminkte zo elke vaste tekst. Het onderwerp staat alleen in de mapnaam,
            # en tekst_item laat het daar weg.
            ag.prive([d["naam"] for d in s["deelnemers"] or [] if not is_mehdi(d, ik) and not vast_woord(d["naam"])])
        t, reden, bestand = toestand(s, fs, w, klok, mappen)
        archief = mappen.get(achtervoegsel(s["uuid"]), "")
        if t == "vangnet: tekst op te halen" and not droog:
            if not schrijven:
                t, reden = "onbekend", "alleen lezen: werkwijze mist de vaste grenzen"
            elif not is_gesprek(s):
                t, reden = "alleen Mehdi", ""      # geen gesprek: geen rij en geen tekst (J10)
            else:
                try:
                    archief = vangnet_schrijven(s, bestand, ik, klok)
                    t = "vangnet: tekst bewaard"
                except Z.GeenRecht:
                    if r is not None:
                        r.nood("Zoom-tekst niet op te halen: de leesapp mist het downloadrecht voor opnames", "mehdi")
                    t, reden = "onbekend", "Zoom-tekst niet op te halen"
                except (Z.ZoomFout, OSError) as e:
                    ag.log("Zoom", "fout", f"Zoom-tekst niet opgehaald: {type(e).__name__}")
                    t, reden = "onbekend", "Zoom-tekst niet opgehaald"
        info.append({"s": s, "fathom": fs[0], "toestand": t, "reden": reden, "prive": prive, "archief": archief,
                     "leider": k["leidend"].get(s["uuid"]), "gesprek": is_gesprek(s)})
    w["timeout_gebruikt"] = timeout_gebruikt
    return info


def sessie_rij(x, ik, personen, domeinen, dubbel_van):
    """Z7: de rij zoom:meeting:<uuid> in de gesprekkentabel. Link altijd leeg; bron altijd zoom."""
    s = x["s"]
    deelnemers = s["deelnemers"] or []
    anderen = [d for d in deelnemers if not is_mehdi(d, ik)]
    afdelingen, bekend_n = defaultdict(int), 0
    for d in anderen:
        p, ok = bekend(personen, d["email"], domeinen)
        bekend_n += 1 if ok else 0
        a = ((p or {}).get("afdeling") or "").split(" ")[0].lower()
        if a and a not in ("alle", "onbekend") and "priv" not in a:
            afdelingen[a] += 1
    pmr = ruimte_van(s, ik) == "vaste vergaderruimte"
    afd = max(afdelingen, key=afdelingen.get) if afdelingen else (
        ("" if pmr else afdeling_uit_naam(s.get("onderwerp"))) or ("prive" if x["prive"] else "onbekend"))
    rij = {"uniek": f"zoom:meeting:{s['uuid']}", "datum": dag_van(s["start"]), "start": brussel(s["start"]).strftime("%H:%M"),
           "minuten": minuten(s), "personen": ", ".join(d["naam"] for d in deelnemers)[:300], "bedrijf": "", "afdeling": afd,
           "thema": PMR_THEMA if pmr else (s.get("onderwerp") or "Zoom-meeting")[:120], "project": "", "prive": x["prive"],
           "zekerheid": "hoog" if anderen and bekend_n == len(anderen) else ("middel" if bekend_n else "laag"),
           "waarom": f"{len(anderen)} andere deelnemer(s), {bekend_n} bekend op e-mailadres of teamdomein"
                     + ("" if s["deelnemers"] is not None else "; deelnemers niet gelezen: privé"),
           "archief": x["archief"] if x["toestand"] == "vangnet: tekst bewaard" else "", "link": "",
           "opgenomen_door": "Zoom", "bron": "zoom", "sessie": f"zoom:meeting:{s['uuid']}"}
    if dubbel_van is not None:
        rij["dubbel_van"] = dubbel_van
    return rij


def verwijzing_van(x):
    """De verwijzing van het zoom-tekst-item: het mappad. Die gaat met de export van het bord naar Dropbox, dus bij een
    privégesprek staat het onderwerp van een geplande meeting er niet in, maar '(privé)'. De map op de VM houdt haar
    naam (ZOO-06; tot dan via het masker van het bord, dat de vaste woorden mee verminkte)."""
    if not x["prive"]:
        return x["archief"]
    map_, naam = os.path.split(x["archief"])
    m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{4} Zoom )(.*)( \[[0-9a-f]{8}\])$", naam)
    if not m or m.group(2) == "vaste vergaderruimte":
        return x["archief"]
    return os.path.join(map_, m.group(1) + "(privé)" + m.group(3))


def tekst_item(x, ik):
    """Z6: het klaarzet-item zoom-tekst voor De Regisseur. Een titel zonder namen; de inhoud zonder tekst of link."""
    s = x["s"]
    stand = "tekst bewaard" if x["toestand"] == "vangnet: tekst bewaard" else "opname zonder tekst"
    return {"voor": "regisseur", "soort": "zoom-tekst", "sleutel": "", "uniek": f"zoom-tekst:{s['uuid']}",
            "verwijzing": verwijzing_van(x) if stand == "tekst bewaard" else "",
            "titel": f"{dag_van(s['start'])} {brussel(s['start']).strftime('%H:%M')} Zoom-gesprek, {minuten(s)} min, alleen in Zoom"
                     + (" · PRIVÉ" if x["prive"] else ""),
            "inhoud": {"datum": dag_van(s["start"]), "start": brussel(s["start"]).strftime("%H:%M"), "minuten": minuten(s),
                       "ruimte": ruimte_van(s, ik), "prive": x["prive"], "stand": stand, "deelnemers": mensen(s)}}


def klaarzet_lezen(**q):
    q.setdefault("status", "alle")
    return bord.call("/api/klaarzet?" + urllib.parse.urlencode(q)).get("items") or []


def _inhoud(item):
    try:
        d = json.loads(item.get("inhoud") or "")
    except ValueError:
        return {}
    return d if isinstance(d, dict) else {}


def bestaande_tekst_items(nodig):
    """Mijn bestaande zoom-tekst-items, bladerend met tot_id tot elk gezocht uniek gevonden is of de bak op is.
    Overleg 26-10-2026 X2: het bord geeft hoogstens 500 per keer; een ouder item bleef onzichtbaar, zodat een vangnet
    dat Fathom later toch had nooit 'vervallen' werd."""
    bestaand, tot_id = {}, None
    while True:
        q = {"soort": "zoom-tekst", "n": 500}
        if tot_id:
            q["tot_id"] = tot_id
        blad = klaarzet_lezen(**q)
        for it in blad:
            if it.get("van") == NAAM:
                bestaand.setdefault(it["uniek"], it)
        if len(blad) < 500 or nodig <= bestaand.keys():
            return bestaand
        laagste = min(it["id"] for it in blad)
        if tot_id is not None and laagste >= tot_id:
            return bestaand                # het bord bladert niet verder: stoppen, nooit eindeloos lezen
        tot_id = laagste


def tekst_items(info, ik):
    """De zoom-tekst-items van deze ronde, plus 'vervallen' voor een vangnet dat Fathom later toch heeft (Z6, T14): nog op
    klaar gewoon bijgewerkt, al opgepakt met revisie. De map blijft staan."""
    bestaand = bestaande_tekst_items({f"zoom-tekst:{x['s']['uuid']}" for x in info})
    items = []
    for x in info:
        uniek = f"zoom-tekst:{x['s']['uuid']}"
        oud = bestaand.get(uniek)
        if x["toestand"] in ("vangnet: tekst bewaard", "vangnet: opname zonder tekst") and x["gesprek"]:
            it = tekst_item(x, ik)
            if oud and oud.get("status") != "klaar" and _inhoud(oud).get("stand") != it["inhoud"]["stand"]:
                it["revisie"] = True
            items.append(it)
        elif x["toestand"] == "fathom" and oud and _inhoud(oud).get("stand") != VERVALLEN:
            inhoud = dict(_inhoud(oud), stand=VERVALLEN)
            it = {"voor": oud["voor"], "soort": "zoom-tekst", "sleutel": "", "uniek": uniek, "verwijzing": oud.get("verwijzing") or "",
                  "titel": oud["titel"], "inhoud": inhoud}
            if oud.get("status") != "klaar":
                it["revisie"] = True
            items.append(it)
    return items


def dag_inhoud(dag, w, info, tel, redenen):
    """Z8: de vaste inhoud van de dagregel van een dag. Onbekend is nooit 0: dan staan de tellingen op null. Een gesprek
    dat alleen Fathom zag (een eigen opname met Mehdi's nummer zonder Zoom-sessie) bewijst dat Zoom die dag iets miste:
    dan is de telling van die dag een ondergrens, met die reden erbij (Z5, ZOO-09)."""
    eigen = [x for x in info if dag_van(x["s"]["start"]) == dag]
    gesprekken = [x for x in eigen if x["gesprek"]]
    gezien = [g for g in w["koppeling"]["gezien"] if dag_van(g[0]["start"]) == dag]
    if gezien and tel != "onbekend":
        tel, redenen = "ondergrens", list(redenen) + ["gesprek alleen via Fathom gezien"]
    bronnen = {b: w["bronnen"][b] for b in ZOOM_BRONNEN + ("fathom-archief", "fathom-api", "chat")}
    if tel != "volledig":
        bronnen["onvolledig"] = redenen
    chat, stand = None, w.get("chat_stand")
    if stand and stand["telling"] == "onbekend":
        chat = {"telling": "onbekend", "redenen": list(stand["redenen"])}
    elif stand:
        # RZ13: elk cijfer komt uit geziene rijen van de gesprekkentabel. De redenen melden wat deze ronde niet las;
        # ook zonder redenen is het cijfer een ondergrens. Zonder getelde tabel is de chat onbekend, nooit zeker nul.
        c = w["chat_dag"].get(dag) or {}
        chat = {"berichten_gezien": c.get("berichten_gezien", 0), "gesprekken": c.get("gesprekken", 0),
                "prive_gezien": c.get("prive_gezien", 0), "telling": "ondergrens"}
        if stand["redenen"]:
            chat["redenen"] = list(stand["redenen"])
    if tel == "onbekend":
        return {"datum": dag, "stand": "voorlopig: geen bron leesbaar", "telling": tel, "bronnen": bronnen,
                "gesprekken": None, "minuten": None, "met_fathom": None, "alleen_zoom_tekst": None, "opname_zonder_tekst": None,
                "zonder_opname": None, "wacht": None, "alleen_mehdi": None, "chat": chat, "werk": []}
    wacht = [x for x in gesprekken if x["toestand"].startswith("wacht") or x["toestand"] == "onbekend"]
    stand_redenen = sorted({x["reden"] for x in wacht if x["reden"]}
                           | ({"Fathom-archief onleesbaar"} if any(o["dag"] == dag for o in w["onleesbaar"]) else set()))
    werklijst = []
    for x in gesprekken:
        if not x["prive"] and len(werklijst) < 12:
            thema = (x["leider"] or {}).get("thema") or sessie_thema(x["s"], w["ik"])
            werklijst.append(f"{', '.join(d['naam'] for d in x['s']['deelnemers'] or [])} ({thema[:40]})")
    return {"datum": dag, "stand": ("voorlopig: " + ", ".join(stand_redenen)) if stand_redenen else "definitief",
            "telling": tel, "bronnen": bronnen,
            "gesprekken": len(gesprekken) + len(gezien),
            "minuten": sum(minuten(x["s"]) for x in gesprekken) + sum(round((g[0]["einde"] - g[0]["start"]).total_seconds() / 60) for g in gezien),
            "met_fathom": sum(1 for x in gesprekken if x["toestand"] == "fathom") + len(gezien),
            "alleen_zoom_tekst": sum(1 for x in gesprekken if x["toestand"] == "vangnet: tekst bewaard"),
            "opname_zonder_tekst": sum(1 for x in gesprekken if x["toestand"] == "vangnet: opname zonder tekst"),
            "zonder_opname": sum(1 for x in gesprekken if x["toestand"] == "zonder opname"),
            "wacht": len(wacht), "alleen_mehdi": len(eigen) - len(gesprekken), "chat": chat, "werk": werklijst,
            # Overleg 26-10-2026 X5: waar de gesprekken zonder Fathom waren, alleen wat Zoom zelf zegt, geen oorzaak.
            "zonder_fathom_waar": zonder_fathom_waar(gesprekken, w["ik"])}


def zonder_fathom_waar(gesprekken, ik):
    """Overleg 26-10-2026 X5 en de controle van Codex: per soort ruimte de gesprekken die Fathom zeker niet heeft (vangnet
    of zonder opname); wat nog wacht of onbekend is, apart als 'nog onbekend'. Zonder host_id buiten de vaste ruimte zegt
    Zoom niet wiens meeting het was: 'ruimte onbekend', nooit 'eigen meeting'."""
    tel = Counter()
    for x in gesprekken:
        t = x["toestand"]
        if t == "fathom":
            continue
        if t.startswith("wacht") or t == "onbekend" or t == "api":
            tel["nog onbekend"] += 1
            continue
        ruimte = ruimte_van(x["s"], ik)
        tel["ruimte onbekend" if ruimte == "eigen meeting" and not x["s"].get("host_id") else ruimte] += 1
    return dict(tel)


def sessie_thema(s, ik):
    return PMR_THEMA if ruimte_van(s, ik) == "vaste vergaderruimte" else (s.get("onderwerp") or "Zoom-meeting")


def dag_titel(inhoud):
    dag = inhoud["datum"]
    kort = f"{dag[8:10]}-{dag[5:7]}"
    chat = inhoud["chat"]
    if chat is None or chat.get("telling") == "onbekend":
        staart = "; chat onbekend"
    elif chat.get("telling") == "laatst gezien":
        n = chat.get("gesprekken")
        staart = f"; chat laatst gezien: minstens {n} chatgesprekken" if isinstance(n, int) and n > 0 else "; chat onbekend"
    elif chat.get("gesprekken", 0) > 0:
        staart = f"; minstens {chat['gesprekken']} chatgesprekken"
    else:
        staart = ""
    if inhoud["telling"] == "onbekend":
        return f"Zoom {kort}: gesprekken onbekend (geen bron leesbaar)" + staart
    n, mf = inhoud["gesprekken"], inhoud["met_fathom"]
    if inhoud["telling"] == "ondergrens":
        return f"Zoom {kort}: minstens {n} gesprekken (telling onvolledig), {inhoud['minuten']} min" + staart
    return f"Zoom {kort}: {n} gesprekken ({mf} met Fathom, {n - mf} alleen in Zoom), {inhoud['minuten']} min" + staart


def oude_telling(inhoud):
    """De telling van een dagregel die er al staat: 'volledig', 'ondergrens' of 'onbekend' in de nieuwe vorm, 'oude vorm'
    voor een regel van de Zoomwacht van voor 21-10-2026 (met meetings en zonder telling: een bekend getal, ZOO-05), of
    None als er geen regel is."""
    if not inhoud:
        return None
    if "telling" not in inhoud and "meetings" in inhoud:
        return "oude vorm"
    return inhoud.get("telling")


def lager(oud_inhoud, inhoud):
    """Is de nieuwe telling lager dan de opgepakte (ZOO-01): minder gesprekken, of van volledig naar een ondergrens
    zonder meer gesprekken. 'Minstens 3' na '2 gesprekken' is nieuws naar boven en gaat wel door."""
    oud_n, n = oud_inhoud.get("gesprekken"), inhoud["gesprekken"]
    if not (isinstance(oud_n, int) and isinstance(n, int)):
        return oud_inhoud.get("telling") == "volledig" and inhoud["telling"] != "volledig"
    return n < oud_n or (n == oud_n and oud_inhoud.get("telling") == "volledig" and inhoud["telling"] != "volledig")


def chat_kern(chat):
    """RZ13/RZ15: alleen een positief bewezen chataantal hoort bij de kern. Nul en onbekend doen allebei geen
    aantalsbewering; een veranderde stand of leesreden stuurt dan geen herziening naar Mehdi."""
    n = chat.get("gesprekken") if isinstance(chat, dict) and chat.get("telling") != "onbekend" else None
    return n or None


def kern_anders(oud_inhoud, inhoud):
    """Verandert de kern van een dagregel (Z8): KERN, of het aantal chatgesprekken (RZ9-02; tot dan bleef een
    opgepakte regel met '0 chatgesprekken' staan als een latere ronde er 2 telde). Het chatcijfer komt uit de
    gesprekkentabel. Een daling kan door een gegevenscorrectie met buiten: en wordt ook herzien."""
    return any(oud_inhoud.get(k) != inhoud[k] for k in KERN) or chat_kern(oud_inhoud.get("chat")) != chat_kern(inhoud["chat"])


def oude_nul_chattitel(titel):
    """RZ13 X3: een oude opgepakte titel met een zekere of minimale nul moet eenmalig rechtgezet worden."""
    return bool(re.search(r"(?<!\d)(?:minstens\s+)?0 chatgesprekken\b", titel or ""))


def oude_chatvorm(titel, inhoud):
    """RZ15: ook een vaste chatstaart of de oude stand 'volledig' krijgt eenmalig een eerlijke ondergrenstitel."""
    chat = inhoud.get("chat")
    return (oude_nul_chattitel(titel)
            or bool(re.search(r";\s*(?!minstens\b)\d+ chatgesprekken\b", titel or ""))
            or isinstance(chat, dict) and chat.get("telling") == "volledig")


def chat_laatst_gezien(chat, redenen):
    """Behoud de vorige bewezen aantallen bij een onleesbare tabel, met een eerlijke stand en veldnamen."""
    oud = dict(chat)
    if "berichten" in oud:
        oud["berichten_gezien"] = oud.pop("berichten")
    if "prive" in oud:
        oud["prive_gezien"] = oud.pop("prive")
    oud["telling"] = "laatst gezien"
    oud["redenen"] = list(dict.fromkeys(list(oud.pop("onvolledig", []) or []) + list(oud.get("redenen") or []) + list(redenen)))
    return oud


def dagregels(w, info, klok, tel, redenen, oud_herzien=False):
    """Z8: een dagregel per afgelopen Brusselse dag in het venster, uniek zoom:dag:<dag>, sleutel leeg. Staat ze al op
    opgepakt en verandert de kern, dan met revisie; ouder dan TERUGBLIK nooit, dan alleen een regel in het werkverslag.
    Twee grendels, elk met een regel in het werkverslag:
    - een bekende telling (ook een regel in de oude vorm, ZOO-05) wordt nooit overschreven met onbekend;
    - een ondergrens daalt niet (ZOO-01): faalde deze ronde een Zoom-bron, dan gaat een opgepakte regel niet terug naar
      Mehdi met een lagere telling (van volledig naar minstens, of minder gesprekken). Wat een bron deze ronde niet gaf,
      is onbekend, niet weg.
    Alleen het aantal chatgesprekken hoort bij de kern (RZ13); een daling door buiten: is een gegevenscorrectie. Is de
    gesprekkentabel onleesbaar, dan blijft het vorige chatdeel met stand 'laatst gezien' staan, zonder herziening daarom.
    Een oude opgepakte titel met een zekere nul of een vaste chatstaart, of oude chatinhoud met 'volledig', wordt
    eenmalig herzien zodra de gesprekkentabel weer leesbaar is (RZ13 X3, RZ15).
    De overgang van een opgepakte regel in de oude vorm naar de nieuwe gaat bewust met herziening, een keer: de oude
    getallen telden alleen geplande meetings (1 tegen 16 op 20-10), en met de oude vorm op het bord zegt De Regisseur
    'onbekend' voor die dag (ZOO-05).
    oud_herzien (WACHT-1, eenmalig met --inhaal): de grens TERUGBLIK geldt niet; een oude opgepakte regel waarvan de kern
    veranderde, gaat dan ook met herziening naar het bord, met een regel in het werkverslag. De andere grendels blijven.
    Geeft (items, regels voor het werkverslag)."""
    items, notities = [], []
    vandaag = date.fromisoformat(w["vandaag"])
    dag = date.fromisoformat(w["eerste"])
    bron_faalde = any(w["bronnen"][b] != "ok" for b in ZOOM_BRONNEN)
    while dag < vandaag:
        d = dag.isoformat()
        dag += timedelta(days=1)
        inhoud = dag_inhoud(d, w, info, tel, redenen)
        oud = next(iter(klaarzet_lezen(uniek=f"zoom:dag:{d}")), None)
        oud_inhoud = _inhoud(oud) if oud else {}
        if inhoud["chat"] is None or inhoud["chat"].get("telling") == "onbekend":
            if isinstance(oud_inhoud.get("chat"), dict) and isinstance(oud_inhoud["chat"].get("gesprekken"), int):
                inhoud["chat"] = chat_laatst_gezien(oud_inhoud["chat"], (w.get("chat_stand") or {}).get("redenen", []))
        it = {"voor": "mehdi", "soort": "zoom", "sleutel": "", "titel": dag_titel(inhoud), "uniek": f"zoom:dag:{d}", "inhoud": inhoud}
        oud_tel = oude_telling(oud_inhoud)
        if oud and tel == "onbekend" and oud_tel in ("volledig", "ondergrens", "oude vorm"):
            notities.append((d, "dagregel niet overschreven: deze ronde kon Zoom niet lezen"))
            continue
        opgepakt = oud and oud.get("status") != "klaar"
        if opgepakt and bron_faalde and oud_tel in ("volledig", "ondergrens") and lager(oud_inhoud, inhoud):
            notities.append((d, "dagregel niet herzien naar een lagere telling: deze ronde faalde een Zoom-bron"))
            continue
        formaat_oud = bool(opgepakt and (w.get("chat_stand") or {}).get("telling") == "ondergrens"
                          and oude_chatvorm(oud.get("titel"), oud_inhoud))
        if opgepakt and (kern_anders(oud_inhoud, inhoud) or formaat_oud):
            if (vandaag - date.fromisoformat(d)).days > TERUGBLIK:
                if not oud_herzien:
                    notities.append((d, "dagregel niet herzien: ouder dan zes dagen"))
                    continue
                notities.append((d, "dagregel ouder dan zes dagen eenmalig herzien (--oud-herzien)"))
            it["revisie"] = True
            if oud_tel == "oude vorm":
                notities.append((d, "dagregel van de oude vorm naar de nieuwe telling, eenmalig met herziening"))
            elif formaat_oud:
                notities.append((d, "oude chatvorm eenmalig herzien naar de ondergrens"))
        items.append(it)
    return items, notities


def schrijf_rijen(rijen):
    for i in range(0, len(rijen), 200):
        bord.call("/api/gesprekken", {"rijen": rijen[i:i + 200]})


KANAAL_ONBEKEND = "kanaal; afdeling niet uit de naam af te leiden"


def kanalen_herzien():
    """Overleg 26-10-2026 X1: een kanaalrij van voor die dag die volgens kanaal_soort privé is, staat nog als werk, ook
    buiten het venster en als Zoom het gesprek nu niet meer laat lezen. Ik beoordeel elke kanaalrij die werk is opnieuw
    op haar naam en zet ze zo nodig op privé, met dezelfde inhoud; ik verwijder niets. Geeft het aantal herziene rijen,
    of None als de tabel niet te lezen was."""
    try:
        oud = bord.db_lees("SELECT * FROM gesprek_log WHERE uniek LIKE 'zoom:chat:%' AND COALESCE(prive, 0)=0 "
                           "AND waarom LIKE 'kanaal;%'")
    except bord.BordOnbekend:
        return None
    rijen = []
    for r in oud:
        if not kanaal_soort(r.get("personen"))[1]:
            continue
        rij = {k: r.get(k) for k in ("uniek", "datum", "start", "minuten", "personen", "bedrijf", "afdeling", "thema", "project",
                                     "zekerheid", "archief", "link", "opgenomen_door", "bron")}
        if rij["personen"] and not vast_woord(rij["personen"]):
            ag.prive([rij["personen"]])
        rijen.append(dict(rij, prive=True, zekerheid="middel", waarom=KANAAL_ONBEKEND + ": bij twijfel privé"))
    schrijf_rijen(rijen)
    return len(rijen)


def zonder_link(rij):
    """Dezelfde volledige rij zoals db_lees ze gaf, met alleen link leeg (J12)."""
    return {**{k: v for k, v in rij.items() if k != "ts"}, "link": "", "prive": bool(rij.get("prive")), "bron": rij.get("bron") or "zoom"}


def alleen_mehdi_rijen(unieks, ronde):
    """J10, ZOO-04: een sessie met alleen Mehdi krijgt geen rij. Staat er toch een (van de oude Zoomwacht, die elke
    geplande meeting schreef, met joinlink; of van een ronde waarin de deelnemers onbekend waren), dan telt ze daarna
    niet meer: eerst dezelfde volledige rij opnieuw met link leeg, dan dubbel_van buiten:alleen-mehdi via
    /api/gesprekken/koppel, en terug langs db_lees. Alleen een rij die telt (dubbel_van leeg); een dubbel blijft een
    dubbel. Er wordt niets verwijderd. Geeft (aantal gemarkeerd, bevestigd): bevestigd False als iets niet terugkwam of
    het lezen onbekend was."""
    if not unieks:
        return 0, True
    try:
        bestaand = rijen_lezen(unieks, "*")
    except bord.BordOnbekend:
        return 0, False
    met_link = [zonder_link(rij) for rij in bestaand.values() if rij.get("link")]
    if met_link:
        schrijf_rijen(met_link)
    wens = {u: {"dubbel_van": "buiten:alleen-mehdi"} for u, rij in sorted(bestaand.items()) if not rij.get("dubbel_van")}
    bevestigd, _, gehouden = koppel_schrijven(wens, ronde)
    return len(wens), bevestigd is not None and not (set(wens) - bevestigd - gehouden)


def werk(r, a, klok):
    """De ronde zelf (Z9), binnen ag.ronde."""
    nooit, beslist = bord.grenzen(r.werkwijze)
    schrijven = bool(nooit) and bool(beslist)
    if not schrijven:
        # 13.5, vraag 6: tot Mehdi de werkwijze met de grenzen goedkeurt, lees ik alleen
        r.nood("Werkwijze mist de vaste grenzen", "claude-code")
    domeinen = teamdomeinen(r.werkwijze)
    personen = personentabel(r)
    staat = staat_lezen()
    w = lezen(a, klok, staat, personen, domeinen)
    w.update(personen=personen, domeinen=domeinen)
    r.bron("zoom-bronnen", w["bronnen"])
    k = w["koppeling"]
    if not schrijven or not w["identiteit_ok"] or w["identiteit"] == "anders":
        ZA.herhaal_bewaarde_scannoden(r, staat)
    if not Z.leesapp():
        r.nood("Zoom-leesapp ontbreekt: telling en vangnet zijn onvolledig", "mehdi")
    elif Z.leesapp_verboden():
        # EIGEN-2: het token van de leesapp heeft een recht uit 'Nooit aanvinken'; zoom.py weigerde het en deze ronde las
        # ik met de app van de stack. De naam van het recht staat in het werkverslag (de bronregel).
        r.nood("Zoom-leesapp geweigerd: ze heeft een recht dat ze nooit mag hebben; telling en vangnet zijn onvolledig", "mehdi")
    elif Z.leesapp_fout():
        # ZOO-10: de sleutels staan er maar geven geen token; deze ronde las ik met de app van de stack
        r.nood("Zoom-leesapp geeft geen token: telling en vangnet zijn onvolledig", "mehdi")
    for b in ZOOM_BRONNEN:
        if w["bronnen"][b].startswith("geen recht: "):
            r.nood(f"Zoom-telling onvolledig: de leesapp mist het recht {w['bronnen'][b][len('geen recht: '):]}", "mehdi")
    if w["bronnen"]["chat"].startswith("geen recht: "):
        # EIGEN-1: de chat leest altijd met de app van de stack
        r.nood(f"Zoom-chat niet gelezen: de app van de stack mist het recht {w['bronnen']['chat'][len('geen recht: '):]}", "mehdi")
    if w["ik"] and w["identiteit"] == "anders":
        # RZ4-02 (22-10-2026): tot dan meldde ik het verschil en schreef ik toch de gesprekken, de koppelingen, de
        # dagregels en de Zoom-tekst van die vreemde gebruiker weg. Nu schrijf ik niets: geen rij, geen koppeling, geen
        # klaarzet, geen vangnetmap, geen download, geen staat en geen --koppel-sinds. Alleen de nood en de hartslag.
        r.nood(IDENTITEIT_NOOD, "mehdi")
        r.detail = "niets geschreven: de Zoom-gebruiker van de leesapp is niet de eigenaar van de vaste vergaderruimte"
        return
    if not w["identiteit_ok"]:
        # RZ6-01 (22-10-2026): een gebruiker die ik niet kan bewijzen, behandel ik als een vreemde: niets schrijven.
        # RZ7-01: ook als ik de gebruiker niet eens kon lezen; tot dan schreef zo'n ronde nog een dagregel en de staat.
        if w["ik"]:
            r.nood(IDENTITEIT_ONBEKEND_NOOD, "mehdi")
            r.detail = "niets geschreven: de Zoom-gebruiker is niet bewezen"
        else:
            r.detail = "niets geschreven: de Zoom-gebruiker is niet gelezen"
        if telling(w)[0] == "onbekend":
            # J13: geen enkele bron leesbaar. De ronde breekt, zodat de hartslag fout is en de open noden openblijven (N11).
            r.nood("Zoom niet leesbaar: geen enkele bron gaf antwoord", "claude-code")
            raise RuntimeError("geen enkele Zoom-bron leesbaar")
        if not w["ik"]:
            r.nood(IDENTITEIT_NIET_GELEZEN_NOOD, "claude-code")
        return
    if schrijven and w["identiteit_bron"] == "fathom":
        # het bewijs van deze ronde onthouden, zodat een week zonder eigen Fathom-opname de wacht niet stillegt
        staat["identiteit"] = {"id": w["ik"]["id"], "pmi": w["ik"]["pmi"], "bewezen": klok.isoformat()}

    wens = koppel_wensen(k)
    gestuurd, gehouden = 0, set()
    if schrijven:
        bevestigd, gestuurd, gehouden = koppel_schrijven(wens, {f"zoom:meeting:{u}" for u in w["sessies"]})
        if bevestigd is None or set(wens) - bevestigd - gehouden:
            r.nood("Koppeling met Fathom niet bevestigd", "claude-code")
    else:
        bevestigd = set(wens)
    info = beoordelen(w, klok, bevestigd, schrijven, False, r)
    tel, redenen = telling(w)

    if w["bronnen"]["fathom-api"] != "ok":
        sinds = tijd(staat.get("fathom_onbekend_sinds")) or klok
        staat["fathom_onbekend_sinds"] = sinds.isoformat()
        if w["timeout_gebruikt"] or klok - sinds >= TEKST_WACHT:
            r.nood("Fathom niet leesbaar voor de koppeling", "claude-code")
    else:
        staat.pop("fathom_onbekend_sinds", None)

    uit_items, uit_dag, notities, n_rijen, n_alleen = {}, {}, [], 0, 0
    if schrijven:
        rijen = []
        for x in info:
            if not x["gesprek"]:
                continue
            leider = x["leider"]
            if x["toestand"] == "fathom":
                dubbel_van = f"fathom:{leider['rid']}"
            elif bevestigd is None and leider and leider["archief"]:
                dubbel_van = None          # onbekend: de vorige stand blijft
            else:
                dubbel_van = ""
            rijen.append(sessie_rij(x, w["ik"], personen, domeinen, dubbel_van))
        n_rijen = len(rijen)
        schrijf_rijen(rijen + w["chat"])
        n_kanalen = kanalen_herzien()
        chat_tellen(w)                     # RZ10: het chatcijfer uit de gesprekkentabel, na het schrijven
        n_alleen, alleen_ok = alleen_mehdi_rijen([f"zoom:meeting:{x['s']['uuid']}" for x in info if not x["gesprek"]],
                                                 {f"zoom:meeting:{u}" for u in w["sessies"]})
        if not alleen_ok:
            r.nood("Markering alleen Mehdi niet bevestigd", "claude-code")
        items = tekst_items(info, w["ik"])
        uit_items = ag.klaarzet(items) if items else {}
        dag_items, notities = dagregels(w, info, klok, tel, redenen, oud_herzien=getattr(a, "oud_herzien", False))
        uit_dag = ag.klaarzet(dag_items) if dag_items else {}
        for d, tekst in notities:
            ag.log(f"dag {d}", "besluit", tekst)

    if a.koppel_sinds:
        koppel_sinds(r, a.koppel_sinds, klok, w["ik"], schrijven)
        buiten_herzien(r, a.koppel_sinds, w["eerste"], w["ik"], schrijven)

    gekoppeld = sum(1 for x in info if x["toestand"] == "fathom")
    vangnet = sum(1 for x in info if x["toestand"].startswith("vangnet"))
    wachten = sum(1 for x in info if x["toestand"].startswith("wacht") or x["toestand"] == "onbekend")
    alleen = sum(1 for x in info if not x["gesprek"])
    ok = sum(1 for b in ZOOM_BRONNEN if w["bronnen"][b] == "ok")
    ag.log("Zoom", "bron", f"venster {w['eerste']} tot {w['vandaag']}: {len(info)} sessies uit {ok} van {len(ZOOM_BRONNEN)} bronnen; "
           f"leesapp {leesapp_stand()}; Fathom: {sum(1 for o in w['fathom'] if o['archief'])} opnames in het archief, "
           f"{len(w['onleesbaar'])} onleesbaar, API {w['bronnen']['fathom-api']}" + chat_verslag(w),
           json.dumps(w["bronnen"], ensure_ascii=False))
    ag.log("Zoom", "bevinding", f"{gekoppeld} met Fathom, {vangnet} in het vangnet, {wachten} wachten of onbekend, "
           f"{len(k['gezien'])} alleen via Fathom gezien, {alleen} alleen Mehdi; telling {tel}")
    account_detail = ""
    if schrijven:
        try:
            account_detail = ZA.ronde(r, w, staat, klok, vangnet, forceer=getattr(a, "account", False))
        except Exception as e:  # noqa: BLE001 - de gesprekkenronde blijft werken
            r.nood("Zoom-accountscan van deze week nog niet gelukt", "claude-code")
            ZA.herhaal_bewaarde_scannoden(r, staat)
            account_detail = "accountscan mislukt"
            ag.log("Zoom-account", "fout", f"accountscan mislukt ({type(e).__name__})")
    if schrijven:
        ag.log("Zoom", "schrijf", f"gesprekkentabel: {n_rijen} sessierijen en {len(w['chat'])} chatrijen (bron zoom), "
               f"{n_alleen} bestaande rij(en) met alleen Mehdi gemarkeerd, "
               f"{n_kanalen if n_kanalen is not None else 'onbekend'} oude kanaalrij(en) naar privé; "
               f"koppelingen: {gestuurd} gestuurd, {len(bevestigd) if bevestigd is not None else 'onbekend'} van {len(wens)} bevestigd"
               + (f", {len(gehouden)} buiten niet gezet (rij hoort bij een sessie buiten deze ronde)" if gehouden else "")
               + f"; zoom-tekst: {_tel(uit_items)}; dagregels: {_tel(uit_dag)}")
        staat["laatste"] = klok.isoformat()
        staat_schrijven(staat)
    r.detail = (f"{len(info)} sessies, {gekoppeld} met Fathom, {vangnet} vangnet, {wachten} wachten; telling {tel}"
                + ("" if schrijven else "; alleen gelezen") + (f"; {account_detail}" if account_detail else ""))
    if tel == "onbekend":
        # J13: geen enkele bron leesbaar. De ronde breekt, zodat de hartslag fout is en de open noden openblijven (N11).
        r.nood("Zoom niet leesbaar: geen enkele bron gaf antwoord", "claude-code")
        raise RuntimeError("geen enkele Zoom-bron leesbaar")


def _tel(uit):
    return ", ".join(f"{uit.get(k, 0)} {k}" for k in ("nieuw", "bijgewerkt", "herzien", "bestaand")) if uit else "geen"


def chat_verslag(w):
    """De stand van de chat in de bronregel, zonder namen (RZ13). Een ronde die alleen leest, telt de chat niet."""
    stand = w.get("chat_stand")
    if stand is None:
        return "; chat niet geteld" + (f" ({', '.join(w['chat_redenen'])})" if w["chat_redenen"] else "")
    oud = w.get("chat_ouderdom") or {}
    leeftijd = ", ".join(f"{oud[g]} {g}" for g in OUDERDOM_GROEPEN if oud.get(g))
    return (f"; chat {stand['telling']}" + (f": {', '.join(stand['redenen'])}" if stand["redenen"] else "")
            + (f" (laatste bericht van de onleesbare: {leeftijd})" if leeftijd else "") + chat_soorten_tekst(w))


def chat_soorten_tekst(w):
    """WACHT-6: ' (per soort: niet leesbaar 2 1:1 en 1 kanaal; zonder bestemming 1 1:1)', of leeg. Alleen soorten en
    aantallen, nooit een naam of adres."""
    tel = w.get("chat_soorten") or {}
    delen = []
    for reden in ("niet leesbaar", "zonder bestemming"):
        per = [f"{tel[(reden, soort)]} {soort}" for soort in ("1:1", "kanaal") if tel.get((reden, soort))]
        if per:
            delen.append(f"{reden} {' en '.join(per)}")
    return f" (per soort: {'; '.join(delen)})" if delen else ""


def leesapp_stand():
    """Voor het werkverslag en --droog: 'ja', 'nee', 'ja, maar geen token (gelezen met de app van de stack)' of, met een
    verboden recht (EIGEN-2), 'ja, maar geweigerd om een verboden recht: <namen> (gelezen met de app van de stack)'."""
    if not Z.leesapp():
        return "nee"
    if Z.leesapp_verboden():
        return f"ja, maar geweigerd om een verboden recht: {', '.join(Z.leesapp_verboden())} (gelezen met de app van de stack)"
    return "ja, maar geen token (gelezen met de app van de stack)" if Z.leesapp_fout() else "ja"


# -------------------------------------------------------- koppel-sinds ---
def koppel_sinds(r, datum, klok, ik, schrijven, droog=False):
    """Z9, J12, L4: de oude zoom:meeting-rijen sinds DATUM met een joinlink aan Fathom koppelen en daarna die link
    leegmaken: eerst koppelen en teruglezen, dan dezelfde volledige rij opnieuw met alleen link leeg. Er wordt niets
    verwijderd; een rij zonder Fathom-tegenhanger blijft tellen. Een rij waarvan het archief rond die tijd onleesbaar
    is, of waarvan de koppeling niet terugkomt, houdt haar link (het nummer is nog nodig). RZ2-05: de rij kent alleen
    de Brusselse tijd; bestaat die twee keer (25-10-2026, 02:00 tot 03:00), dan beslist eerst de UTC-start van de sessie
    bij Zoom, dan de UTC-tijd van Fathom, maar die alleen als de keuze uitsluitend is (tegenproef 22-10-2026); kan geen
    van beide het, dan blijft de rij ongekoppeld met haar link en een regel in het werkverslag."""
    try:
        oud = bord.db_lees("SELECT * FROM gesprek_log WHERE uniek LIKE 'zoom:meeting:%' AND datum >= ? AND link <> '' ORDER BY datum, start", (datum,))
    except bord.BordOnbekend as e:
        if r is not None:
            r.nood("Oude Zoom-rijen niet te lezen voor de koppeling", "claude-code")
        ag.log("koppel-sinds", "fout", f"oude rijen niet gelezen: {e.reden}")
        return
    opnames, onleesbaar, toestand_archief = fathom_lezen(min([x["datum"] for x in oud] or [datum]), dag_van(klok))
    if toestand_archief != "ok":
        if r is not None:
            r.nood("Fathom-archief niet leesbaar voor de oude koppeling", "claude-code")
        return
    sessies, dubbelzinnig = [], []
    for rij in oud:
        m = NUMMER.search(rij.get("link") or "")
        nummer = m.group(1) if m else ""
        try:
            tijden = utc_tijden(rij["datum"], rij["start"])
            duur = timedelta(minutes=max(1, int(rij.get("minuten") or 0)))
        except (TypeError, ValueError):
            continue
        s = {"uuid": rij["uniek"][len("zoom:meeting:"):], "nummer": nummer, "start": tijden[0], "einde": tijden[0] + duur,
             "duur": rij.get("minuten"), "deelnemers": None, "host_id": ik["id"] if ik else "", "deelname": False, "rij": rij}
        if len(tijden) > 1:
            # RZ2-05: de rij kent alleen de Brusselse tijd, en die bestaat twee keer. Eerst de UTC-bron van Zoom: de start
            # van deze sessie (/past_meetings/<uuid>), op de minuut gelijk aan een van de twee uren.
            try:
                d = Z.lees(f"/past_meetings/{Z.uuid_pad(s['uuid'])}")
            except Exception:  # noqa: BLE001  geen antwoord: dan Fathom
                d = None
            bij_zoom = tijd((d or {}).get("start_time"))
            bij_zoom = bij_zoom.replace(second=0, microsecond=0) if bij_zoom else None
            if bij_zoom in tijden:
                s["start"], s["einde"] = bij_zoom, bij_zoom + duur
                sessies.append(s)
                continue
            # Dan de UTC-tijd van Fathom (recording_start_time): raakt maar een van de twee uren een opname met dit nummer
            # of een onleesbaar archief, dan is dat het uur, als die keuze uitsluitend is (hieronder). Raakt geen van
            # beide iets, dan maakt het uur niets uit. Raken ze allebei, dan koppel ik niet: de rij houdt haar link en
            # krijgt een regel in het werkverslag.
            raak = [t for t in tijden
                    if any(nummer and o["nummer"] == nummer and overlap(t, t + duur, o["start"], o["einde"]) > 0 for o in opnames)
                    or any(kandidaat({"start": t, "einde": t + duur}, x, klok) for x in onleesbaar)]
            if len(raak) > 1:
                dubbelzinnig.append(s)
                continue
            if raak:
                s["start"], s["einde"] = raak[0], raak[0] + duur
                s["via_fathom"] = {o["uniek"] for o in opnames
                                   if nummer and o["nummer"] == nummer and overlap(s["start"], s["einde"], o["start"], o["einde"]) > 0}
            else:
                s["uur_onbepaald"] = True
        sessies.append(s)
    # Tegenproef RZ2-05 (22-10-2026): wat Fathom aanwijst, bewijst alleen iets als het uitsluitend is. 83% van de meetings
    # zit in de vaste ruimte, dus rijen delen vaak een nummer. Een opname die voor twee rijen het uur kiest, of een uur dat
    # in dezelfde ruimte overlapt met een andere rij (twee meetings tegelijk in een ruimte kan niet), maakt de keuze
    # willekeurig: alle betrokken rijen blijven dan ongekoppeld, met hun link. Een rij waarvan het uur niets uitmaakt, telt
    # hier niet mee: geen van haar twee uren raakt een opname.
    gekozen = [s for s in sessies if "via_fathom" in s]
    twijfel = set()
    for i, s in enumerate(gekozen):
        if any(s["via_fathom"] & t["via_fathom"] for t in gekozen[i + 1:]):
            twijfel |= {id(s)} | {id(t) for t in gekozen[i + 1:] if s["via_fathom"] & t["via_fathom"]}
        if s["nummer"] and any(t is not s and t["nummer"] == s["nummer"] and not t.get("uur_onbepaald")
               and overlap(s["start"], s["einde"], t["start"], t["einde"]) > 0 for t in sessies):
            twijfel.add(id(s))
    dubbelzinnig += [s for s in sessies if id(s) in twijfel]
    sessies = [s for s in sessies if id(s) not in twijfel]
    k = koppel(sessies, opnames, ik, klok)
    wens = {}
    for uuid, o in k["leidend"].items():
        wens[o["uniek"]] = {"sessie": f"zoom:meeting:{uuid}", "dubbel_van": ""}
        wens[f"zoom:meeting:{uuid}"] = {"sessie": f"zoom:meeting:{uuid}", "dubbel_van": o["uniek"]}
    for rid, (uuid, leider) in k["dubbel"].items():
        wens[f"fathom:{rid}"] = {"sessie": f"zoom:meeting:{uuid}", "dubbel_van": f"fathom:{leider}"}
    met_code = [s for s in sessies + dubbelzinnig if "pwd=" in (s["rij"].get("link") or "")]
    if droog:
        print(f"(droog) koppel-sinds {datum}: {len(oud)} oude rijen met een link, {len(k['leidend'])} met een Fathom-opname, "
              f"{len(met_code)} met een toegangscode"
              + (f", {len(dubbelzinnig)} niet te koppelen (die Brusselse tijd bestaat twee keer)" if dubbelzinnig else "")
              + "; niets geschreven")
        return
    if not schrijven:
        return
    for s in dubbelzinnig:
        ag.log("koppel-sinds", "besluit", f"{s['rij']['datum']} {s['rij']['start']}: niet gekoppeld, die tijd bestaat twee keer in "
               "Brussel en Fathom zegt niet welk uur; de rij houdt haar link")
    bevestigd, _, _ = koppel_schrijven(wens)
    try:
        na = rijen_lezen([f"zoom:meeting:{s['uuid']}" for s in sessies], "*")
    except bord.BordOnbekend:
        na = None
    gewist, gehouden = [], 0
    for s in sessies:
        uniek = f"zoom:meeting:{s['uuid']}"
        leider = k["leidend"].get(s["uuid"])
        if leider:
            vast = bevestigd is not None and uniek in bevestigd and leider["uniek"] in bevestigd
        else:
            vast = not any(kandidaat(s, x, klok) for x in onleesbaar)
        rij = (na or {}).get(uniek)
        if not vast or rij is None:
            gehouden += 1
            continue
        gewist.append(zonder_link(rij))
    if gewist:
        schrijf_rijen(gewist)
    if gehouden and r is not None:
        r.nood("Koppeling met Fathom niet bevestigd", "claude-code")
    # L4: wissen is niet intrekken. Hoort een link met toegangscode bij een terugkerende meeting, dan blijft die code
    # geldig tot Mehdi ze in Zoom verandert.
    terugkerend, onbekend_l4 = 0, 0
    for s in met_code:
        if not s["nummer"]:
            continue
        Z.nummer_erbij(s["nummer"])
        try:
            m = Z.lees(f"/meetings/{s['nummer']}")
            terugkerend += 1 if m and m.get("type") in (3, 8) else 0
        except Exception:  # noqa: BLE001
            onbekend_l4 += 1
    if r is not None and terugkerend:
        r.nood("Een oude Zoom-link met toegangscode hoort bij een terugkerende meeting: de code geldt tot ze in Zoom verandert", "mehdi")
    if r is not None and onbekend_l4:
        r.nood("Niet nagekeken of een oude Zoom-link met toegangscode bij een terugkerende meeting hoort", "claude-code")
    ag.log("koppel-sinds", "schrijf", f"sinds {datum}: {len(oud)} oude rijen met een link, {len(k['leidend'])} gekoppeld aan Fathom, "
           f"{len(gewist)} links leeggemaakt, {gehouden} gehouden"
           + (f", {len(dubbelzinnig)} niet gekoppeld (die Brusselse tijd bestaat twee keer)" if dubbelzinnig else "")
           + f"; {len(met_code)} met toegangscode, {terugkerend} terugkerend")


def rapport_nummers(ik, van_dag, tot_dag):
    """De meetingnummers uit het rapport (past, pastOne en pastJoined) van de vaste gebruiker tussen twee datums, in
    stukken van hoogstens 28 dagen: Zoom geeft het rapport voor hoogstens een maand per vraag. Faalt een stuk, dan gaat
    de fout door: het geheel is dan onbekend, nooit een kortere lijst."""
    nummers = set()
    for d, tot in stukken(van_dag, tot_dag):
        for soort in RAPPORT_SOORTEN:
            for m in _lijst(f"/report/users/{ik['id']}/meetings", {"type": soort, "from": d, "to": tot, "page_size": 300},
                            "meetings"):
                if m.get("id"):
                    nummers.add(str(m["id"]))
    return nummers


def buiten_herzien(r, datum, eerste, ik, schrijven, droog=False):
    """ZOO-03, met --koppel-sinds: buiten:andere-ruimte opnieuw beoordelen voor de Fathom-rijen van DATUM tot het venster
    (in het venster doet de gewone ronde dat elke keer). Zonder rapport is 'een andere ruimte' onbekend: een opname van
    een ander account bleef ongemoeid en telde, ook als ze daarna uit het venster schoof; en een markering van voor
    21-10-2026 kon gezet zijn zonder rapport. Dezelfde regel als in koppel(): een opname van een ander account met een
    nummer dat niet de vaste vergaderruimte is en niet in het rapport staat, krijgt buiten:andere-ruimte; staat het
    nummer er wel in, dan telt ze. Alleen een rij zonder sessie krijgt buiten (de grendel van koppel_schrijven). Een eigen
    opname en een opname zonder nummer blijven ongemoeid. Is het rapport niet te lezen, dan verandert er niets."""
    if not (ik and ik["pmi"]) or datum >= eerste:
        return
    try:
        rijen = bord.db_lees("SELECT uniek, sessie, dubbel_van FROM gesprek_log WHERE uniek LIKE 'fathom:%' AND datum >= ? AND datum < ? "
                             "AND (dubbel_van = 'buiten:andere-ruimte' OR (COALESCE(dubbel_van, '') = '' AND COALESCE(sessie, '') = ''))",
                             (datum, eerste))
    except bord.BordOnbekend as e:
        if r is not None:
            r.nood("Oude Fathom-rijen niet te lezen voor de herbeoordeling van andere ruimtes", "claude-code")
        ag.log("koppel-sinds", "fout", f"oude Fathom-rijen niet gelezen: {e.reden}")
        return
    opnames, _, toestand_archief = fathom_lezen(datum, eerste)
    if toestand_archief != "ok":
        if r is not None:
            r.nood("Fathom-archief niet leesbaar voor de oude koppeling", "claude-code")
        return
    per_uniek = {o["uniek"]: o for o in opnames}
    kandidaten = [(rij, per_uniek[rij["uniek"]]) for rij in rijen if rij["uniek"] in per_uniek
                  and not per_uniek[rij["uniek"]]["eigen"] and per_uniek[rij["uniek"]]["nummer"] not in ("", ik["pmi"])]
    if not kandidaten:
        return
    try:
        nummers = rapport_nummers(ik, (date.fromisoformat(datum) - timedelta(days=1)).isoformat(),
                                  (date.fromisoformat(eerste) + timedelta(days=1)).isoformat())
    except Exception as e:  # noqa: BLE001
        ag.log("koppel-sinds", "besluit", f"andere ruimtes niet herbeoordeeld: rapport {toestand_van(e)}; niets veranderd")
        return
    wens = {}
    for rij, o in kandidaten:
        if o["nummer"] in nummers and rij.get("dubbel_van") == "buiten:andere-ruimte":
            wens[rij["uniek"]] = {"dubbel_van": ""}
        elif o["nummer"] not in nummers and not rij.get("dubbel_van") and not rij.get("sessie"):
            wens[rij["uniek"]] = {"dubbel_van": "buiten:andere-ruimte"}
    terug = sum(1 for v in wens.values() if not v["dubbel_van"])
    if droog:
        print(f"(droog) andere ruimtes sinds {datum}: {len(kandidaten)} opnames van een ander account, {terug} tellen weer, "
              f"{len(wens) - terug} krijgen buiten; niets geschreven")
        return
    if not schrijven or not wens:
        return
    bevestigd, _, gehouden = koppel_schrijven(wens)
    if bevestigd is None or set(wens) - bevestigd - gehouden:
        r.nood("Koppeling met Fathom niet bevestigd", "claude-code")
    ag.log("koppel-sinds", "schrijf", f"andere ruimtes sinds {datum}: {len(kandidaten)} opnames van een ander account beoordeeld met het "
           f"rapport, {terug} tellen weer, {len(wens) - terug} buiten:andere-ruimte")


# ----------------------------------------------------------------- droog ---
def droog(a, klok):
    """--droog: geen ronde, dus geen hartslag, kennis, rijen, klaarzet, downloads, mappen of staat (Z9, T27). Een
    rapport per dag met tellingen en tijden, zonder namen of onderwerpen."""
    try:
        eigen = ag.werkwijze_lezen()
    except bord.WerkwijzeOnbekend as e:
        print(f"(droog) mijn werkwijze niet gelezen: {e.soort}")
        eigen = ""
    personen = personentabel()
    domeinen = teamdomeinen(eigen)
    w = lezen(a, klok, staat_lezen(), personen, domeinen)
    w.update(personen=personen, domeinen=domeinen)
    info = beoordelen(w, klok, set(koppel_wensen(w["koppeling"])), False, True)
    tel, redenen = telling(w)
    print(f"(droog) venster {w['eerste']} tot {w['vandaag']} (Brussel); leesapp {leesapp_stand()}; "
          f"personentabel {'gelezen' if personen is not None else 'niet gelezen'}; telling {tel}"
          + (f" ({'; '.join(redenen)})" if redenen and tel != 'onbekend' else ""))
    print("   bronnen: " + "; ".join(f"{b} {t}" for b, t in w["bronnen"].items()))
    dag = date.fromisoformat(w["eerste"])
    while dag <= date.fromisoformat(w["vandaag"]):
        d = dag.isoformat()
        dag += timedelta(days=1)
        inhoud = dag_inhoud(d, w, info, tel, redenen)
        if tel == "onbekend":
            print(f"   {d}: gesprekken onbekend")
            continue
        print(f"   {d}{' (vandaag, geen dagregel)' if d == w['vandaag'] else ''}: {inhoud['gesprekken']} gesprekken, "
              f"{inhoud['met_fathom']} met Fathom, {inhoud['alleen_zoom_tekst']} Zoom-tekst, {inhoud['opname_zonder_tekst']} zonder tekst, "
              f"{inhoud['zonder_opname']} zonder opname, {inhoud['wacht']} wachten, {inhoud['minuten']} min, "
              f"{inhoud['alleen_mehdi']} alleen Mehdi; stand {inhoud['stand']}")
        for x in info:
            if dag_van(x["s"]["start"]) == d:
                print(f"      {brussel(x['s']['start']).strftime('%H:%M')} {minuten(x['s'])} min, {ruimte_van(x['s'], w['ik'])}: "
                      f"{x['toestand'] if x['gesprek'] else 'alleen Mehdi'}")
    vroegst = {}
    for s in w["sessies"].values():
        for b in s.get("bronnen") or []:
            vroegst[b] = min(vroegst.get(b, dag_van(s["start"])), dag_van(s["start"]))
    # WACHT-1: hoe ver Zoom teruggaat, per bron de vroegste dag met een sessie in het venster
    print("   vroegste sessie per bron: " + ("; ".join(f"{b} {vroegst[b]}" for b in sorted(vroegst)) or "geen"))
    rijen_meten(w, info)
    if a.koppel_sinds:
        koppel_sinds(None, a.koppel_sinds, klok, w["ik"], False, droog=True)
        buiten_herzien(None, a.koppel_sinds, w["eerste"], w["ik"], False, droog=True)
    if getattr(a, "account", False) and ZA.scan_aan(eigen):
        ZA.droog(w, klok)
    return 0


RIJ_SOORTEN = ("alleen Zoom", "met Fathom", "alleen Mehdi", "niet in deze ronde")


def rijen_meten(w, info):
    """WACHT-4 (meting 01-11-2026: de dagbundel telde 16 tot 21 oktober 9 gesprekken 'alleen in Zoom' meer dan de
    dagregel; de oorzaak is niet gemeten). Alleen in --droog en alleen lezend (bord.db_lees): per afgelopen dag van het
    venster de leidende rijen zoom:meeting (dubbel_van leeg) naast de sessies van deze ronde en de dagregel op het bord.
    Een leidende rij hoort bij een gesprek zonder Fathom ('alleen Zoom'); elke andere (met Fathom, alleen Mehdi, of een
    sessie die deze ronde niet zag) staat er met haar uuid, nooit met een naam of onderwerp. Het verschil is het aantal
    leidende rijen min de gesprekken zonder Fathom van de dagregel. Herstellen komt pas na deze meting."""
    try:
        rijen = bord.db_lees("SELECT uniek, datum, COALESCE(dubbel_van, '') AS dubbel_van FROM gesprek_log "
                             "WHERE uniek LIKE 'zoom:meeting:%' AND datum BETWEEN ? AND ?", (w["eerste"], w["vandaag"]))
        regels = {r["uniek"]: _inhoud(r) for r in bord.db_lees(
            "SELECT uniek, inhoud FROM klaarzet WHERE van=? AND uniek LIKE 'zoom:dag:%'", (NAAM,))}
    except bord.BordOnbekend as e:
        print(f"   rijen tegen de dagregel: niet gelezen ({e.reden})")
        return
    sessie = {x["s"]["uuid"]: x for x in info}
    per_dag, afwijkend = defaultdict(Counter), defaultdict(list)
    for r in rijen:
        if r["dubbel_van"]:
            continue
        x = sessie.get(r["uniek"][len("zoom:meeting:"):])
        soort = ("niet in deze ronde" if x is None else "alleen Mehdi" if not x["gesprek"]
                 else "met Fathom" if x["toestand"] == "fathom" else "alleen Zoom")
        per_dag[r["datum"]][soort] += 1
        if soort != "alleen Zoom":
            afwijkend[r["datum"]].append(f"{r['uniek']} ({soort})")
    print("   rijen tegen de dagregel (WACHT-4), per dag:")
    dag = date.fromisoformat(w["eerste"])
    while dag < date.fromisoformat(w["vandaag"]):
        d = dag.isoformat()
        dag += timedelta(days=1)
        tel, inhoud = per_dag.get(d, Counter()), regels.get(f"zoom:dag:{d}")
        n = sum(tel.values())
        if not n and inhoud is None:
            continue
        g, f = (inhoud or {}).get("gesprekken"), (inhoud or {}).get("met_fathom")
        if not isinstance(g, int) or not isinstance(f, int):
            regel = "dagregel ontbreekt" if inhoud is None else "dagregel zonder telling (oude vorm of onbekend)"
            verschil = ""
        else:
            regel, verschil = f"dagregel {g} gesprekken, {f} met Fathom ({g - f} zonder)", f"; verschil {n - (g - f):+d}"
        soorten = ", ".join(f"{tel[k]} {k}" for k in RIJ_SOORTEN if tel.get(k))
        print(f"   {d}: {regel}; leidende rijen {n}" + (f": {soorten}" if soorten else "") + verschil)
        for x in sorted(afwijkend.get(d, [])):
            print(f"      {x}")


# ------------------------------------------------------------------ main ---
def argumenten(argv):
    p = argparse.ArgumentParser(description="De Zoomwacht: telt elk Zoom-gesprek en koppelt het aan Fathom.")
    p.add_argument("--droog", action="store_true", help="alleen lezen; een rapport per dag zonder namen of onderwerpen")
    p.add_argument("--account", action="store_true", help="de accountscan in deze ronde volledig proberen")
    p.add_argument("--inhaal", type=int, default=VENSTER_DAGEN, help=f"het venster in dagen (standaard 7, hoogstens {INHAAL_MAX})")
    p.add_argument("--oud-herzien", dest="oud_herzien", action="store_true",
                   help="eenmalig, bij een inhaal: ook een opgepakte dagregel ouder dan zes dagen herzien")
    p.add_argument("--koppel-sinds", dest="koppel_sinds",
                   help="oude zoom:meeting-rijen sinds JJJJ-MM-DD koppelen en hun link leegmaken, en andere ruimtes opnieuw beoordelen")
    a = p.parse_args(argv)
    if a.inhaal < 1 or a.inhaal > INHAAL_MAX:
        # WACHT-1: de vragen aan Zoom gaan in stukken van een maand (stukken), dus het venster mag langer dan een maand
        p.error(f"--inhaal tussen 1 en {INHAAL_MAX} dagen")
    if a.koppel_sinds:
        try:
            date.fromisoformat(a.koppel_sinds)
        except ValueError:
            p.error("--koppel-sinds als JJJJ-MM-DD")
    return a


def main(argv=None):
    a = argumenten(sys.argv[1:] if argv is None else argv)
    klok = nu()
    if a.droog:
        return droog(a, klok)
    with ag.ronde("Zoom-gesprekken tellen en koppelen") as r:
        werk(r, a, klok)
    return 0


if __name__ == "__main__":
    # J1, N11: keten.py (na 1200 s) en De Regisseur (timeout 540) stoppen een te lange ronde met SIGTERM. Zonder handler
    # stierf het proces zonder dat de ronde afsloot, en bleef de hartslag op actief. Zo gaat het als SystemExit door
    # de ronde, die dan fout meldt. Alleen hier, niet bij een import.
    signal.signal(signal.SIGTERM, fw.stop_bij_sigterm)
    sys.exit(main())
