"""Fase 4b van De Zoomwacht: alleen-lezen accountscan met veilige borduitvoer.

Alle ruwe Zoom-antwoorden blijven in de aanroep die ze samenvat. De staat en het
bord krijgen uitsluitend de hieronder benoemde tellingen, keuzes en booleans.
"""
import copy
import hashlib
import json
import math
import os
import re
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import bord
import zoom as Z

BUDGET = 240
BRUSSEL = ZoneInfo("Europe/Brussels")
SECTIES = ("beveiliging", "opnames", "ai", "licenties", "apps", "gebruik")
ERNST = {"hoog": 0, "middel": 1, "laag": 2}
SCOPE_PATROON = re.compile(r"[a-z_][a-z0-9_]*(?::[a-z0-9_]+){1,3}")
OPENID_RECHTEN = {"openid", "profile", "email"}
NOOD_OPSLAG_VOL = "Zoom-cloudopslag vol: het vangnet kan geen Zoom-tekst meer halen"
NOOD_PAKKET = "Zoom-pakket veranderd: het dashboard opnieuw meten"
KLIKPADEN = {
    "ZA-01": "Admin > Account Management > Account Settings > Recording & Transcript > Delete cloud recordings after a specified number of days > Enable > 30 dagen > Save > lock icon > Lock.\nZoom Web (te bevestigen): profielfoto > Admin Center > Settings > Recording & Transcript > dezelfde schakelaar",
    "ZA-02": "Admin > Account Management > Account Settings > Recording & Transcript > Cloud recording: Record active speaker with shared screen, Record gallery view with shared screen en Record active speaker, gallery view and shared screen separately (drie deelopties) uit; Record audio-only files > Record one audio file for all participants aan; Create audio transcript aan; Save. Per gebruiker Settings > Recording nakijken (te bevestigen).\nZoom Web: Admin Center > Settings > Recording & Transcript > General > Cloud recording (te bevestigen)",
    "ZA-03": "Admin > Account Management > Account Settings > Recording & Transcript > Cloud recording > Advanced cloud recording settings > Create audio transcript > lock icon > Lock > Save (te bevestigen).\nZoom Web: profielfoto > Admin Center > Settings > Recording & Transcript > General > Cloud recording > Advanced cloud recording settings > Create audio transcript > lock icon > Lock > Save",
    "ZA-04": "profielfoto > Admin Center > Security and trust > General > Security > Sign in with two-step verification > Enable > All users in your account of Users with specific roles (Owner en Admin) > Authentication methods > Save",
    "ZA-05": "profielfoto > Admin Center > Settings > Meeting > Security > Enable waiting room > Enable > lock icon > Lock",
    "ZA-06": "Meetings > Personal Room > Edit > Security > Waiting Room > Save",
    "ZA-07": "profielfoto > Admin Center > Settings > General > Data & Storage > Recordings and content location > Germany",
    "ZA-08": "",
    "ZA-09": "profielfoto > Admin Center > Settings > Zoom AI > Meeting > Auto-delete meeting summaries > Enable > 30 dagen > Save",
    "ZA-10": "marketplace.zoom.us > Manage > Admin App Management > Apps on Account > Added Apps > app > Manage app (te bevestigen).\nNieuwere Marketplace (te bevestigen): Marketplace admin > Marketplace Management > App on the account. Een eigen app kan een van je koppelingen zijn: niet verwijderen of uitzetten voor vaststaat welke koppeling erop draait",
    "ZA-11": "Admin > User Management > Groups.\nZoom Web: profielfoto > Admin Center > Users > Groups",
    "ZA-12": "Admin Center > Security and trust > General > Security > Users need to sign in again after a period of inactivity",
    "ZA-13": "Admin > Account Management > Reports > User Activity Reports > Admin Activity Logs (te bevestigen).\nZoom Web: profielfoto > Admin Center > Reports > User activity reports > Admin Activity Logs",
    "ZA-14": "Admin > Account Management > Recording and Transcript Management > Recordings > opname > Audio transcript; daarna Admin > Account Management > Account Settings > Recording & Transcript > Cloud recording > Advanced cloud recording settings > Create audio transcript > lock icon > Lock > Save (te bevestigen).\nZoom Web: profielfoto > Admin Center > Content management > Recording & Transcript > Topic; daarna Admin Center > Settings > Recording & Transcript > General > Cloud recording > Advanced cloud recording settings > Create audio transcript > lock icon > Lock > Save",
    "ZA-15": "Admin Center > Security and trust > General > Sign-in Methods > Facebook aanmelden (te bevestigen). Passkeys ingeschakeld laten",
}
ONZEKERE_PADEN = {"ZA-02", "ZA-10", "ZA-13", "ZA-15"}
ACTIES = {
    "ZA-01": "Zoom: wisregel voor cloudopnames aanzetten",
    "ZA-02": "Zoom: alleen geluid en transcript opnemen in de cloud",
    "ZA-03": "Zoom: audiotranscript aanzetten voor het vangnet",
    "ZA-04": "Zoom: tweestapsverificatie aanzetten voor beheerders",
    "ZA-05": "Zoom: wachtkamer vergrendelen voor alle gebruikers",
    "ZA-06": "Zoom: wachtkamer aanzetten in je vaste vergaderruimte",
    "ZA-07": "Zoom: opnames in de EU bewaren",
    "ZA-08": "Zoom: ticket bij Zoom Support voor alleen Zoom modellen",
    "ZA-09": "Zoom: bewaartermijn voor AI-samenvattingen aanzetten",
    "ZA-10": "Zoom: apps met veel schrijfrechten nakijken",
    "ZA-11": "Zoom: lege rollen en groepen opruimen",
    "ZA-12": "Zoom: automatisch afmelden na inactiviteit aanzetten",
    "ZA-13": "Zoom: nakijken welke app gebruikersinstellingen verandert",
    "ZA-14": "Zoom: opnames komen zonder transcript",
    "ZA-15": "Zoom: ongebruikte aanmeldwijzen uitzetten",
}
REGELS = {code: {"actie": actie, "klikpad": KLIKPADEN[code]} for code, actie in ACTIES.items()}


class PrivacyFout(ValueError):
    pass


class ScanFout(RuntimeError):
    pass


def week_van(klok):
    d = klok.astimezone(BRUSSEL).isocalendar()
    return f"{d.year}-W{d.week:02d}"


def dag_van(klok):
    return klok.astimezone(BRUSSEL).date().isoformat()


def scan_aan(werkwijze):
    """Alleen de enkelvoudige regel onder de kop zet de scan aan; eindspaties tellen niet."""
    tekst = (werkwijze or "").replace("\r\n", "\n")
    regels = [regel.rstrip() for regel in tekst.split("\n")]
    koppen = [i for i, s in enumerate(regels) if s == "## Accountscan"]
    if len(koppen) != 1:
        return False
    grens = next((j for j in range(koppen[0] + 1, len(regels)) if regels[j].startswith("#")), len(regels))
    return regels[koppen[0] + 1:grens].count("ACCOUNTSCAN: aan") == 1 and \
        not any("ACCOUNTSCAN:" in s and s != "ACCOUNTSCAN: aan" for s in regels[koppen[0] + 1:grens])


def aan_de_beurt(staat_acc, klok):
    return staat_acc.get("laatste_volledig") != week_van(klok)


def _get(d, *pad):
    for k in pad:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _keuze(v, toegestaan):
    return v if isinstance(v, str) and v in toegestaan else None


def _bool(v):
    return v if type(v) is bool else None


def _tel(v):
    return v if type(v) is int and v >= 0 else None


def _ident(v):
    """Een stabiele opaque code zonder cijfers; nooit een app-id of persoon bewaren."""
    h = hashlib.sha256(str(v).encode()).digest()
    return "".join(chr(ord("a") + int(x, 16)) for x in h.hex()[:16])


def _naam(v):
    # Een vrij appnaamveld kan ook een persoonsnaam of link zijn.
    return "externe app"


def veilig_plat(d):
    """Alleen vooraf gekozen, inhoudsarme instellingsvelden. Geen kale teksthash van een code."""
    velden = {
        "recording.auto_recording": {"none", "cloud", "local"},
        "recording.cloud_recording": {True, False},
        "recording.record_audio_file": {True, False},
        "recording.record_speaker_view": {True, False},
        "recording.record_gallery_view": {True, False},
        "recording.record_files_separately.active_speaker": {True, False},
        "recording.record_files_separately.gallery_view": {True, False},
        "recording.record_files_separately.shared_screen": {True, False},
        "recording.recording_audio_transcript": {True, False},
        "recording.auto_delete_cmr": {True, False},
        "schedule_meeting.require_password_for_pmi_meetings": {"none"},
        "in_meeting.waiting_room": {True, False},
        "schedule_meeting.join_before_host": {True, False},
        "meeting_security.meeting_password": {True, False},
        "meeting_security.pmi_password": {True, False},
        "security.sign_in_with_two_factor_auth": {"all", "role", "group", "none"},
        "ai.ai_model_type": {"Federated", "ZMO"},
        "ai.meeting_summary.enable": {True, False},
        "ai.meeting_summary.auto_enable": {True, False},
        "ai.meeting_summary_retention.enable": {True, False},
        "ai.meeting_questions.enable": {True, False},
        "ai.meeting_coach.enable": {True, False},
    }
    uit = {}
    for naam, waarden in velden.items():
        v = _get(d, *naam.split("."))
        if type(v) in (str, bool) and v in waarden:
            uit[naam] = v
    return uit


def instellingen(d):
    plat = veilig_plat(d)
    loc = _get(d, "profile", "recording_storage_location")
    waarde = loc.get("value") if isinstance(loc, dict) else loc
    toegestaan = loc.get("allowed_values") if isinstance(loc, dict) else None
    landen = sorted(set(x for x in toegestaan if isinstance(x, str) and re.fullmatch(r"[A-Z]{2}", x))) \
        if isinstance(toegestaan, list) else None
    plat["opslaglocatie"] = waarde if isinstance(waarde, str) and re.fullmatch(r"[A-Z]{2}", waarde) else None
    plat["landen"] = landen
    if not any(k in plat for k in ("recording.auto_recording", "recording.cloud_recording",
                                   "in_meeting.waiting_room", "ai.ai_model_type")):
        return {"stand": "onbekend: instellingen ontbreken"}
    return plat


def beveiliging(d):
    stand = _keuze(d.get("sign_in_with_two_factor_auth"), {"all", "role", "group", "none"})
    rollen = d.get("two_factor_authentication_roles")
    if rollen is None:
        rollen = d.get("sign_in_with_two_factor_auth_roles")
    rollen = [str(x) for x in rollen] if isinstance(rollen, list) and all(type(x) in (str, int) for x in rollen) else None
    perioden = (d.get("sign_again_period_for_inactivity_on_client"),
                d.get("sign_again_period_for_inactivity_on_web"))
    afmelden = ("uit" if any(v in (-1, 0) for v in perioden) else "aan") \
        if all(type(v) is int for v in perioden) else None
    if stand is None and afmelden is None:
        return {"stand": "onbekend: beveiligingsvelden ontbreken"}
    return {"tweestaps": stand, "rollen": rollen, "afmelden": afmelden,
            "facebook": _bool(d.get("sign_in_with_fb")),
            "sms": _bool(d.get("sign_in_with_sms_code"))}


def vergrendelingen(d):
    plat = {}
    def loop(x, prefix=""):
        if not isinstance(x, dict):
            return
        for k, v in x.items():
            if not isinstance(k, str) or not re.fullmatch(r"[a-z_]{1,50}", k):
                continue
            naam = f"{prefix}.{k}" if prefix else k
            if type(v) is bool:
                plat[naam] = v
            elif isinstance(v, dict):
                loop(v, naam)
    loop(d)
    if not plat:
        return {"stand": "onbekend: vergrendelingen ontbreken"}
    return {"aantal": sum(v is True for v in plat.values()),
            "wachtkamer": plat.get("in_meeting.waiting_room", plat.get("meeting_security.waiting_room")),
            "toegangscode": plat.get("meeting_security.meeting_password"),
            "velden": {k: v for k, v in plat.items() if k in {
                "in_meeting.waiting_room", "meeting_security.waiting_room", "meeting_security.meeting_password",
                "meeting_security.pmi_password", "recording.cloud_recording"}}}


def ruimte(d, pmi_codebeleid=None):
    # Het gemeten PMI-eindpunt nestelt instellingen onder settings; ook platte antwoorden worden gelezen.
    s = d.get("settings") if isinstance(d.get("settings"), dict) else d
    # Geen enkel id, URL, wachtwoord of onderwerp gaat door deze samenvatter.
    code = s.get("password") if "password" in s else d.get("password")
    if not s or not any(k in s for k in ("waiting_room", "join_before_host", "auto_recording")):
        return {"stand": "onbekend: ruimte-instellingen ontbreken"}
    return {"wachtkamer": _bool(s.get("waiting_room")), "voor_host": _bool(s.get("join_before_host")),
            "toegangscode": bool(code) if code is not None else False if pmi_codebeleid == "none" else None,
            "aanmelding": _bool(s.get("meeting_authentication")),
            "auto_opname": _keuze(s.get("auto_recording"), {"none", "cloud", "local"})}


def rollen(rows):
    standaard = {"Owner": None, "Admin": None, "Member": None}
    ids = {}
    eigen_leeg = eigen_met = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        naam = row.get("name") or row.get("role_name")
        n = _tel(row.get("total_members"))
        if n is None:
            return {"stand": "onbekend: ledentelling ontbreekt"}
        if naam in standaard:
            standaard[naam] = n
            ids[naam] = str(row.get("id") or "")
        elif n is not None:
            eigen_leeg += n == 0
            eigen_met += n > 0
    return {"standaard": standaard, "eigen_leeg": eigen_leeg, "eigen_met": eigen_met,
            "beheer_ids": ids}


def groepen(rows):
    aantallen = [_tel(x.get("total_members", x.get("member_count"))) for x in rows if isinstance(x, dict)]
    return {"aantal": len(rows), "leeg": sum(x == 0 for x in aantallen) if None not in aantallen else None,
            "leden": sum(aantallen) if None not in aantallen else None}


def gb(v):
    if v == "0" or v == 0:
        return 0.0
    if not isinstance(v, str):
        return None
    m = re.fullmatch(r"(\d+(?:\.\d{1,3})?) (GB|MB|TB)", v)
    if not m:
        return None
    return round(float(m.group(1)) * {"MB": 1 / 1024, "GB": 1, "TB": 1024}[m.group(2)], 3)


def opslag(d, trend=None, klok=None):
    opnameplan = d.get("plan_recording") if isinstance(d, dict) else None
    if not isinstance(opnameplan, dict):
        return {"stand": "onbekend: opslagvelden onleesbaar"}
    gratis, betaald, gebruikt = (gb(opnameplan.get("free_storage")), gb(opnameplan.get("plan_storage")),
                                 gb(opnameplan.get("free_storage_usage")))
    capaciteit = gratis + betaald if gratis is not None and betaald is not None else None
    if capaciteit is None or capaciteit <= 0 or gebruikt is None:
        return {"stand": "onbekend: opslagvelden onleesbaar"}
    pct = round(100 * gebruikt / capaciteit)
    groei = None
    if isinstance(trend, list):
        punten = sorted((str(x.get("date") or x.get("report_date") or ""), gb(x.get("usage")))
                        for x in trend if isinstance(x, dict))
        punten = [(dag, waarde) for dag, waarde in punten if re.fullmatch(r"\d{4}-\d{2}-\d{2}", dag) and waarde is not None]
        punten = punten[-14:]
        if len(punten) >= 2:
            dagen = (datetime.fromisoformat(punten[-1][0]) - datetime.fromisoformat(punten[0][0])).days
            if dagen > 0:
                groei = round((punten[-1][1] - punten[0][1]) / dagen, 3)
    vol_dagen = math.ceil((capaciteit - gebruikt) / groei) if groei and groei > 0 else None
    vol = (klok.astimezone(BRUSSEL).date() + timedelta(days=max(0, vol_dagen))).isoformat() \
        if klok and vol_dagen is not None else None
    return {"stand": "ok", "gratis_gb": gratis, "betaald_gb": betaald, "gebruikt_gb": gebruikt,
            "pct": pct, "groei_gb_per_dag": groei, "vol_rond": vol, "vol_dagen": vol_dagen}


def opnames(rows, klok):
    soorten = Counter()
    klaar = met_tekst = kort = 0
    for m in rows:
        if not isinstance(m, dict):
            continue
        duur = m.get("duration")
        kort += type(duur) in (int, float) and duur <= 2
        bestanden = m.get("recording_files")
        if not isinstance(bestanden, list):
            return {"stand": "onbekend: bestanden ontbreken"}
        typen = set()
        for f in bestanden:
            if not isinstance(f, dict):
                continue
            soort = f.get("file_type")
            maat = f.get("file_size")
            if soort in {"MP4", "M4A", "TRANSCRIPT", "TIMELINE"} and not (type(maat) in (int, float) and maat >= 0):
                return {"stand": "onbekend: bestandsgrootte ontbreekt"}
            if soort in {"MP4", "M4A", "TRANSCRIPT", "TIMELINE"}:
                soorten[soort] += maat
                typen.add(soort)
        try:
            oud = datetime.fromisoformat(str(m.get("start_time", "")).replace("Z", "+00:00")) <= klok - timedelta(hours=24)
        except ValueError:
            oud = False
        if oud and type(duur) in (int, float) and duur > 2:
            klaar += 1
            met_tekst += "TRANSCRIPT" in typen
    totaal = sum(soorten.values())
    video = round(100 * soorten["MP4"] / totaal) if totaal else None
    return {"stand": "ok", "aantal": len(rows), "bestanden": sum(1 for m in rows for f in m.get("recording_files", []) if isinstance(f, dict)),
            "mb": round(totaal / 1_000_000), "mb_per_soort": {k: round(v / 1_000_000) for k, v in soorten.items()},
            "video_pct": video, "klaar": klaar, "met_transcript": met_tekst,
            "transcript_pct": round(100 * met_tekst / klaar) if klaar else None, "kort_2min": kort}


def _rechten_detail(d):
    if not isinstance(d, dict) or not isinstance(d.get("app_scopes"), list):
        raise Z.AccountFout(reden="onleesbaar")
    gevonden = set()
    for rij in d["app_scopes"]:
        # Gemeten op 22-10: app_scopes is een lijst rechtennamen als tekst; een dict met scope_name kan ook.
        code = rij.get("scope_name") if isinstance(rij, dict) else rij
        # Gemeten op 22-10: twee apps vragen de standaard OpenID-rechten; die lezen alleen het eigen profiel.
        if not isinstance(code, str):
            raise Z.AccountFout(reden="onleesbaar")
        if code in OPENID_RECHTEN:
            gevonden.add(code)
            continue
        if not SCOPE_PATROON.fullmatch(code):
            raise Z.AccountFout(reden="onleesbaar")
        gevonden.add(code)
    return len(gevonden), sum(bool(re.search(r":(?:write|update|delete)(?::|$)", s)) for s in gevonden)


def apps(rows, details):
    uit = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("app_id"):
            return {"stand": "onbekend: app-id ontbreekt"}
        appid = str(row["app_id"])
        if appid not in details or details[appid] is None:
            return {"stand": "onbekend: appdetail ontbreekt"}
        try:
            n, schrijf = _rechten_detail(details[appid])
        except Z.AccountFout:
            n, schrijf = None, None
        gepubliceerd = row.get("app_status") == "PUBLISHED"
        uit.append({"code": _ident(appid), "naam": _naam(row.get("app_name")) if gepubliceerd else "eigen app",
                    "gepubliceerd": gepubliceerd, "rechten": n, "schrijf": schrijf})
    return {"stand": "ok", "aantal": len(uit), "eigen": sum(not x["gepubliceerd"] for x in uit),
            "onbekende_rechten": sum(x["rechten"] is None for x in uit),
            "overzicht": sorted(uit, key=lambda x: x["code"]),
            "met_schrijfrechten": sorted((x for x in uit if x["schrijf"] is not None and x["schrijf"] >= 5),
                                         key=lambda x: x["code"])}


def pakket(d):
    basis = d.get("plan_base")
    if not isinstance(basis, dict):
        return {"stand": "onbekend: pakket ontbreekt"}
    if _keuze(basis.get("type"), {"monthly", "yearly"}) is None or _tel(basis.get("hosts")) is None:
        return {"stand": "onbekend: pakketvelden ontbreken"}
    return {"stand": "ok", "periode": _keuze(basis.get("type"), {"monthly", "yearly"}),
            "hosts": _tel(basis.get("hosts")), "sinds": _datum(basis.get("service_effective_date")),
            "volgende_factuur": _datum(basis.get("next_invoice_date"))}


def _datum(v):
    return v if isinstance(v, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) else None


def activiteiten(rows):
    toestellen = Counter()
    aan = af = 0
    for x in rows:
        if not isinstance(x, dict):
            continue
        actie = str(x.get("action") or x.get("type") or "").lower()
        aan += actie in {"sign in", "signin", "login"}
        af += actie in {"sign out", "signout", "logout"}
        client = str(x.get("client_type") or "").lower()
        client = client if client in {"iphone", "android", "win", "mac", "browser", "ipad", "watchos"} else "overig"
        toestellen[client] += 1
    return {"aanmelden": aan, "afmelden": af, "per_toestel": dict(toestellen)}


def beheerlogboek(rows):
    tellen = Counter()
    regels = Counter()
    gevoelig = Counter()
    veilig = re.compile(r"[A-Za-z /&-]{1,40}")
    for x in rows:
        if not isinstance(x, dict):
            continue
        cat, actie = x.get("category_type"), x.get("action")
        tijdstip = x.get("time")
        if not (isinstance(cat, str) and veilig.fullmatch(cat) and isinstance(actie, str) and veilig.fullmatch(actie)
                and isinstance(tijdstip, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}T[\d:.+-]+Z?", tijdstip)):
            return {"stand": "onbekend: beheerregel onleesbaar"}
        tellen[f"{cat} / {actie}"] += 1
        code = _ident((tijdstip, cat, actie))
        regels[code] += 1
        if cat in {"Account", "Role", "Billing", "Security", "Sign In"} or \
                (cat == "User" and actie in {"Add", "Delete", "Remove"}):
            gevoelig[code] += 1
    return {"aantal": len(rows), "tellingen": dict(tellen), "regels": dict(regels),
            "gevoelig": dict(gevoelig)}


def _fout(e):
    if isinstance(e, Z.GeenRecht):
        return "geen recht " + (e.scope if e.scope == "download" or SCOPE_PATROON.fullmatch(e.scope) else "onbekend")
    if isinstance(e, Z.AccountFout):
        return e.reden or (f"HTTP {e.http}" if isinstance(e.http, int) else "antwoord onleesbaar")
    return type(e).__name__


class Lezer:
    def __init__(self, budget=BUDGET):
        self.begin = time.monotonic()
        self.budget = budget
        self.laatst = None
        self.vragen = 0
        self.stop = ""

    def vraag(self, pad, params=None):
        if self.stop:
            raise ScanFout(self.stop)
        nu = time.monotonic()
        if nu - self.begin >= self.budget:
            self.stop = "tijd op"
            raise ScanFout(self.stop)
        if self.laatst is not None:
            time.sleep(max(0, Z.PAUZE - (nu - self.laatst)))
        if time.monotonic() - self.begin >= self.budget:
            self.stop = "tijd op"
            raise ScanFout(self.stop)
        self.laatst = time.monotonic()
        self.vragen += 1
        try:
            return Z.lees_account(pad, params)
        except Z.AccountFout as e:
            if e.http == 429:
                self.stop = "limiet van Zoom"
            raise

    def lijst(self, pad, params, sleutel, max_paginas=10):
        p, uit = dict(params or {}), []
        for _ in range(max_paginas):
            d = self.vraag(pad, p)
            if sleutel not in d or not isinstance(d[sleutel], list):
                raise Z.AccountFout(reden="onleesbaar")
            uit.extend(d[sleutel])
            if not d.get("next_page_token"):
                return uit
            p["next_page_token"] = d["next_page_token"]
        raise Z.AccountFout(reden="afgekapt")


def _deel(lezer, doel, naam, f, groep, fouten):
    try:
        doel[naam] = f()
        if isinstance(doel[naam], dict) and str(doel[naam].get("stand", "")).startswith("onbekend"):
            fouten.append((groep, naam, doel[naam]["stand"].removeprefix("onbekend: ")))
    except Exception as e:  # noqa: BLE001 - per eindpunt onbekend, nooit nul
        doel[naam] = {"stand": "onbekend: " + _fout(e)}
        fouten.append((groep, naam, _fout(e)))


def _lijst_een(lezer, pad, params, sleutels):
    # De sleutel is vast per eindpunt; een ontbrekende sleutel wordt niet als lege lijst gelezen.
    return lezer.lijst(pad, params, sleutels)


def lees_week(ik, pmi, klok, budget=BUDGET):
    """Alle geplande eindpunten; elk antwoord wordt meteen veilig samengevat."""
    l = Lezer(budget)
    d, fouten = {}, []
    vandaag = klok.date().isoformat()
    maand = (klok - timedelta(days=30)).date().isoformat()
    week = (klok - timedelta(days=7)).date().isoformat()
    def lees_opslag():
        gebruik = l.vraag("/accounts/me/plans/usage")
        try:
            trend = _lijst_een(l, "/report/cloud_recording", {"from": maand, "to": vandaag},
                               "cloud_recording_storage")
            d["opslagtrend"] = {"stand": "ok"}
        except Exception as e:  # noqa: BLE001 - de trend mag de gemeten capaciteit niet verbergen
            reden = _fout(e)
            fouten.append(("opnames", "opslagtrend", reden))
            d["opslagtrend"] = {"stand": "onbekend: " + reden}
            trend = None
        return opslag(gebruik, trend, klok)
    _deel(l, d, "account", lambda: instellingen(l.vraag("/accounts/me/settings")), "beveiliging", fouten)
    _deel(l, d, "security", lambda: beveiliging(l.vraag("/accounts/me/settings", {"option": "security"})), "beveiliging", fouten)
    _deel(l, d, "meeting_security", lambda: veilig_plat(l.vraag("/accounts/me/settings", {"option": "meeting_security"}))
          or {"stand": "onbekend: meetingbeveiliging ontbreekt"}, "beveiliging", fouten)
    _deel(l, d, "locks", lambda: vergrendelingen(l.vraag("/accounts/me/lock_settings")), "beveiliging", fouten)
    _deel(l, d, "user", lambda: instellingen(l.vraag(f"/users/{ik}/settings")), "opnames", fouten)
    _deel(l, d, "ruimte", lambda: ruimte(l.vraag(f"/meetings/{pmi}"),
                                        _bekend(d, "user", "schedule_meeting.require_password_for_pmi_meetings")),
          "beveiliging", fouten)
    _deel(l, d, "rollen", lambda: rollen(_lijst_een(l, "/roles", {}, "roles")), "beveiliging", fouten)
    _deel(l, d, "groepen", lambda: groepen(_lijst_een(l, "/groups", {"page_size": 300}, "groups")), "beveiliging", fouten)
    _deel(l, d, "gebruikers", lambda: gebruikers(_lijst_een(l, "/users", {"status": "active", "page_size": 300}, "users")), "licenties", fouten)
    _deel(l, d, "samenvatting", lambda: gebruikers_samenvatting(l.vraag("/users/summary")), "licenties", fouten)
    _deel(l, d, "pakket", lambda: pakket(l.vraag("/accounts/me/plans")), "licenties", fouten)
    _deel(l, d, "opslag", lees_opslag, "opnames", fouten)
    _deel(l, d, "opnames", lambda: opnames(_lijst_een(l, "/accounts/me/recordings", {"from": maand, "to": vandaag,
                                                                                        "page_size": 300}, "meetings"), klok), "opnames", fouten)
    _deel(l, d, "samenvattingen", lambda: {"aantal": len(_lijst_een(l, "/meetings/meeting_summaries",
                                                                     {"from": maand, "to": vandaag}, "summaries"))}, "ai", fouten)
    _deel(l, d, "activiteiten", lambda: activiteiten(_lijst_een(l, "/report/activities", {"from": week, "to": vandaag,
                                                                                           "page_size": 300}, "activity_logs")),
          "beveiliging", fouten)
    _deel(l, d, "logboek", lambda: beheerlogboek(_lijst_een(l, "/report/operationlogs", {"from": maand, "to": vandaag,
                                                                                          "page_size": 300}, "operation_logs")),
          "beveiliging", fouten)
    _deel(l, d, "rapport_actief", lambda: rapport_users(_lijst_een(l, "/report/users", {"type": "active", "from": maand,
                                                                                           "to": vandaag}, "users")), "gebruik", fouten)
    _deel(l, d, "rapport_inactief", lambda: rapport_users(_lijst_een(l, "/report/users", {"type": "inactive", "from": maand,
                                                                                             "to": vandaag}, "users")), "gebruik", fouten)
    _deel(l, d, "daggebruik", lambda: daggebruik(l.vraag("/report/daily", {"year": klok.year, "month": klok.month})), "gebruik", fouten)
    _deel(l, d, "facturen", lambda: facturen(_lijst_een(l, "/accounts/me/billing/invoices", {}, "invoices")), "licenties", fouten)
    _deel(l, d, "apps", lambda: _lees_apps(l), "apps", fouten)
    def hulptelling(soort):
        try:
            return {"aantal": len(_lijst_een(l, "/marketplace/apps", {"type": soort, "page_size": 100}, "apps"))}
        except Exception:  # noqa: BLE001 - deze lijsten zijn informatief, ook bij een API-fout
            return {"stand": "onbekend: niet beschikbaar"}
    for soort, naam in (("account_created", "gemaakt"), ("active_requests", "aanvragen"),
                        ("restricted_apps", "geblokkeerd"), ("approved_apps", "goedgekeurd")):
        _deel(l, d, naam, lambda soort=soort: hulptelling(soort), "apps", fouten)
    # Optionele, op dit pakket niet beschikbare delen bepalen niet of een week gelukt is.
    verplicht_fout = [x for x in fouten if x[1] not in {"facturen", "opslagtrend", "gemaakt", "aanvragen",
                                                     "geblokkeerd", "goedgekeurd"}]
    return d, fouten, not verplicht_fout, l.vragen


def gebruikers(rows):
    typen, versies, login = Counter(), Counter(), Counter()
    login_bekend = bool(rows)
    for x in rows:
        if not isinstance(x, dict):
            return {"stand": "onbekend: gebruiker onleesbaar"}
        t = x.get("type")
        if t in (1, 2):
            typen["licensed" if t == 2 else "basic"] += 1
        versie = str(x.get("last_client_version") or "")
        m = re.match(r"^(\d+\.\d+)", versie)
        versies[m.group(1) if m else "onbekend"] += 1
        codes = x.get("login_types")
        if isinstance(codes, list):
            for code in codes:
                if type(code) is int and 0 <= code <= 20:
                    login[str(code)] += 1
        else:
            login_bekend = False
    return {"aantal": len(rows), "typen": dict(typen), "versies": dict(versies),
            "login_types": dict(login) if login_bekend else None}


def gebruikers_samenvatting(d):
    uit = {k: _tel(d.get(k + "_users_count")) for k in ("licensed", "basic", "room", "pending", "on_prem", "join_only")}
    return {"stand": "onbekend: licentietelling ontbreekt"} if None in uit.values() else uit


def rapport_users(rows):
    typen = Counter("licensed" if x.get("type") == 2 else "basic" if x.get("type") == 1 else "onbekend"
                    for x in rows if isinstance(x, dict))
    return {"aantal": len(rows), "typen": dict(typen)}


def daggebruik(d):
    rows = d.get("dates")
    if not isinstance(rows, list):
        return {"stand": "onbekend: daglijst ontbreekt"}
    sleutels = ("meetings", "participants", "meeting_minutes", "new_users")
    if any(_tel(x.get(k)) is None for x in rows if isinstance(x, dict) for k in sleutels):
        return {"stand": "onbekend: dagtelling ontbreekt"}
    return {"stand": "ok", **{k: sum(x[k] for x in rows if isinstance(x, dict)) for k in sleutels}}


def facturen(rows):
    # Een lege API-lijst bij een lopend pakket bewijst niet dat er geen facturen bestaan.
    return {"stand": "onbekend: factuurlijst leeg bij lopend pakket"} if not rows else {"stand": "ok", "aantal": len(rows)}


def _lees_apps(l):
    rows = _lijst_een(l, "/marketplace/apps", {"type": "account_added", "page_size": 100}, "apps")
    details = {}
    for row in rows:
        appid = row.get("app_id") if isinstance(row, dict) else None
        if not isinstance(appid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", appid):
            raise Z.AccountFout(reden="onleesbaar")
        details[appid] = l.vraag(f"/marketplace/apps/{appid}")
    return apps(rows, details)


def _bekend(d, naam, *pad):
    x = d.get(naam)
    if not isinstance(x, dict) or str(x.get("stand", "")).startswith("onbekend"):
        return None
    return _get(x, *pad) if pad else x


def _waarde(d, k, reden="veld ontbreekt"):
    v = d.get(k) if isinstance(d, dict) else None
    return v if v is not None else "onbekend: " + reden


ARCHIEF_DEKKING = "~/appportal/mijnagents-data/zoom-archief/dekking.json"
ARCHIEF_GELDIG = timedelta(hours=3)    # De Zoomarchivaris draait elk uur en slaat hoogstens een ronde over voor de
                                       # keten; een ouder bestand zegt niets meer (Codex, Zoomarchief controle 4)
NOOD_WISREGEL_WACHT = "Wacht met de wisregel: niet elke Zoom-opname staat bewezen in je Dropbox"


def _archief(sleutel, pad=None, nu=None):
    """'ja', 'nee' of 'onbekend' voor een veld uit het bestand van De Zoomarchivaris (zoom_archief.py): onbekend
    zonder bestand, onleesbaar of ouder dan ARCHIEF_GELDIG."""
    try:
        with open(os.path.expanduser(pad or ARCHIEF_DEKKING), encoding="utf-8") as f:
            d = json.load(f)
        ts = datetime.fromisoformat(d["ts"])
        oud = (nu or datetime.now(timezone.utc)) - ts > ARCHIEF_GELDIG
    except (OSError, ValueError, KeyError, TypeError):
        return "onbekend"
    if oud or not isinstance(d.get(sleutel), bool):
        return "onbekend"
    if d[sleutel] and not archief_ronde_geslaagd(d["ts"]):
        return "onbekend"  # Codex controle 5, punt 27: een ja telt alleen als de ronde die haar schreef geslaagd is
    return "ja" if d[sleutel] else "nee"


def archief_ronde_geslaagd(ts):
    """Staat De Zoomarchivaris op het bord op klaar of waakt, met een hartslag van na het moment ts? Zo telt een ja
    niet als de ronde erna begon en niet afliep (een volle schijf kan zelfs het intrekken beletten), of brak. Onbekend
    bord: nee."""
    try:
        rij = bord.db_lees("SELECT status, taak, ts FROM status WHERE naam='zoom-archief'")
        sinds = datetime.fromisoformat(str(ts))
        hart = datetime.fromisoformat(str(rij[0]["ts"]).replace("Z", "+00:00")) if rij else None
    except (bord.BordOnbekend, ValueError, KeyError, TypeError):
        return False
    if hart is None or rij[0].get("status") not in ("klaar", "waakt"):
        return False
    if rij[0].get("taak") != "opnames naar Dropbox":
        return False  # Codex controle 7, punt 38: alleen een echte ronde, geen droge of proefronde, bevestigt een ja
    hart = hart if hart.tzinfo else hart.replace(tzinfo=timezone.utc)
    return hart >= sinds


def archief_dekking(pad=None, nu=None):
    """Driehoeksoverleg Zoomarchief K6 (27-10-2026): staat alles wat Zoom nu heeft bewezen in Mehdi's Dropbox? Mehdi:
    eerst een kopie, dan pas wissen. Hierop opent ZA-01."""
    return _archief("dekking", pad, nu)


def archief_veilig(pad=None, nu=None):
    """Staat alles wat ouder is dan 30 dagen bewezen in Dropbox, zonder verlies of onvolledige opname? Dat is wat de
    wisregel van 30 dagen nodig heeft (Codex, Zoomarchief controle 3, punt 12)."""
    return _archief("wisregel_veilig", pad, nu)


def wisregel_wacht(r):
    """Codex, Zoomarchief controle 3, punt 12: staat er een ZA-01-voorstel open of goedgekeurd terwijl de kopie niet
    veilig is voor de wisregel, dan een nood voor Mehdi, elke ronde opnieuw tot het weer veilig is. De besluitknop op het
    bord voert zelf niets uit; dit is de waarschuwing bij het besluit."""
    try:
        rijen = voorstellen_lezen()
    except bord.BordOnbekend:
        # Codex controle 4, punt 22: zonder de voorstellen weet ik niet of de waarschuwing nog geldt; niets sluiten
        r.nood("Zoom-advies niet terug te lezen op het bord", "claude-code")
        r.noden_onbekend = True
        return
    if any(x.get("status") in ("open", "goedgekeurd") and _params(x).get("zoom_advies") == "ZA-01" for x in rijen) \
            and archief_veilig() != "ja":
        r.nood(NOOD_WISREGEL_WACHT, "mehdi")


def adviezen(d, gesprekken=0, staat_acc=None):
    """Elke regel is open, goed of onbekend. Ontbrekende invoer opent niets."""
    uit = []
    def voeg(code, ernst, waarde, stand=None, reden="", doel=""):
        toestand = "onbekend" if waarde is None else "open" if waarde else "goed"
        uit.append({"code": code, "ernst": ernst, "toestand": toestand,
                    "stand": stand if toestand == "open" else None,
                    "reden": reden if toestand == "open" else "gegevens ontbreken" if toestand == "onbekend" else "",
                    "doel": doel})

    account = _bekend(d, "account")
    gebruiker = _bekend(d, "user")
    sec = _bekend(d, "security")
    lock = _bekend(d, "locks")
    room = _bekend(d, "ruimte")
    rec = _bekend(d, "opnames")
    store = _bekend(d, "opslag")
    role = _bekend(d, "rollen")
    group = _bekend(d, "groepen")
    app = _bekend(d, "apps")
    logs = _bekend(d, "logboek")
    ai_n = _bekend(d, "samenvattingen", "aantal")

    wis = account.get("recording.auto_delete_cmr") if account else None
    pct = store.get("pct") if store else None
    dagen = store.get("vol_dagen") if store else None
    trend_gelezen = _bekend(d, "opslagtrend") is not None
    if wis is None or pct is None:
        open01 = None
    elif pct >= 80 and wis is False:
        open01 = True
    elif not trend_gelezen:
        open01 = None
    else:
        open01 = wis is False and dagen is not None and dagen <= 30
    hoog01 = pct is not None and pct >= 90 or dagen is not None and dagen <= 14
    band = 100 if pct is not None and pct >= 100 else 90 if pct is not None and pct >= 90 else \
        80 if pct is not None and pct >= 80 else "trend_14" if dagen is not None and dagen <= 14 else "trend_30"
    reden01 = f"Opslag {pct}% gebruikt"
    if store and store.get("vol_rond"):
        reden01 += f"; vermoedelijk vol rond {store['vol_rond']}"
    # Driehoeksoverleg Zoomarchief K6 en Codex-controle 1 (27-10-2026): Mehdi wil eerst een volledige kopie, dan pas
    # wissen. Zolang De Zoomarchivaris geen dekking ja meldt, is ZA-01 geen open advies maar onbekend, zodat er geen
    # voorstel "zet de wisregel aan" komt. De stand draagt de kopie: een voorstel van voor de kopie (zonder die sleutel)
    # houdt het advies na de kopie dus niet tegen als het geweigerd werd.
    dekking = archief_dekking()
    reden01 += "; alle opnames staan bewezen in je Dropbox"
    voeg("ZA-01", "hoog" if hoog01 else "middel", open01 if dekking == "ja" or open01 is not True else None,
         {"wisregel": False, "band": band, "kopie": "ja"}, reden01 + "." if open01 else "",
         "Zet een wisregel van 30 dagen aan; houd transcript en cloudopname aan.")
    if dekking != "ja" and open01:
        uit[-1]["reden"] = ("wacht op de volledige kopie in je Dropbox (De Zoomarchivaris): " +
                            ("nog niet alle opnames bewezen" if dekking == "nee" else "dekking onbekend"))

    uop = gebruiker.get("recording.auto_recording") if gebruiker else None
    utr = gebruiker.get("recording.recording_audio_transcript") if gebruiker else None
    ua = gebruiker.get("recording.record_audio_file") if gebruiker else None
    video = rec.get("video_pct") if rec else None
    video_opties = ("recording.record_speaker_view", "recording.record_gallery_view",
                   "recording.record_files_separately.active_speaker", "recording.record_files_separately.gallery_view",
                   "recording.record_files_separately.shared_screen")
    opties = [bron.get(k) if bron else None for bron in (account, gebruiker) for k in video_opties]
    bekend02 = all(x is not None for x in (uop, utr, ua, video, *opties))
    voeg("ZA-02", "middel", (uop == "cloud" and utr is True and ua is False and video >= 80
                              and any(opties)) if bekend02 else None,
         {"cloud": True, "geluid": False, "transcript": True, "video": True},
         f"Video is {video}% van de opnamebytes; Fathom miste {gesprekken} gesprekken. Het transcript is het vangnet.",
         "Zet video-opties op account- en gebruikersniveau uit; test daarna dat geluid en transcript zonder video werken.")
    voeg("ZA-03", "hoog", uop == "cloud" and utr is False if uop is not None and utr is not None else None,
         {"transcript": False}, "Cloudopname staat aan zonder audiotranscript.", "Zet audiotranscript aan voor het vangnet.")

    twee = sec.get("tweestaps") if sec else None
    role_ids = role.get("beheer_ids") if role else None
    gekozen = sec.get("rollen") if sec else None
    if twee in ("none", "all") and role_ids is not None:
        open04, stand04 = twee == "none", "none"
    elif twee == "role" and isinstance(gekozen, list) and role_ids and all(role_ids.get(x) for x in ("Owner", "Admin")):
        open04 = not {role_ids["Owner"], role_ids["Admin"]}.issubset(set(gekozen))
        stand04 = "role_zonder_beheer"
    else:
        open04, stand04 = None, None
    voeg("ZA-04", "hoog", open04, {"tweestaps": stand04},
         "De accountschakelaar voor tweestapsverificatie staat niet verplicht. Of hij Owner en Admin beschermt, hangt af van hun aanmelding.",
         "Controleer eerst of Owner en Admin met werk-e-mail en wachtwoord aanmelden. Alleen dan werkt deze Zoom-schakelaar; bij Google of SSO moet de bescherming daar worden nagekeken.")

    kamer = account.get("in_meeting.waiting_room") if account else None
    kamer_slot = lock.get("wachtkamer") if lock else None
    code_slot = lock.get("toegangscode") if lock else None
    code_aan = _bekend(d, "meeting_security", "meeting_security.meeting_password")
    known05 = all(x is not None for x in (kamer, kamer_slot, code_slot, code_aan))
    voeg("ZA-05", "laag", (kamer and not kamer_slot and code_slot and not code_aan) if known05 else None,
         {"wachtkamer": True, "vergrendeld": False, "codes_vergrendeld_uit": True},
         "De accountwachtkamer staat aan maar is niet vergrendeld. Zoom kan vergaderingen afhankelijk van het pakket automatisch beveiligen.",
         "Controleer de pakketregel voor verplichte vergaderbeveiliging en vergrendel desgewenst de wachtkamer.")

    wk = room.get("wachtkamer") if room else None
    rc = room.get("toegangscode") if room else None
    vh = room.get("voor_host") if room else None
    if wk is True:
        open06 = False
    elif wk is False and rc is not None and vh is not None:
        open06 = not rc or vh
    else:
        open06 = None
    voeg("ZA-06", "hoog", open06,
         {"wachtkamer": wk, "code": rc, "voor_host": vh},
         "De vaste vergaderruimte is zonder wachtkamer onvoldoende afgeschermd.",
         "Zet de wachtkamer aan in de vaste vergaderruimte.")

    land = gebruiker.get("opslaglocatie") if gebruiker else None
    landen = gebruiker.get("landen") if gebruiker else None
    voeg("ZA-07", "middel", land != "DE" and "DE" in landen if land and isinstance(landen, list) else None,
         {"locatie": land}, "Nieuwe opnames staan buiten Duitsland.", "Bewaar nieuwe opnames in Duitsland.")
    model = account.get("ai.ai_model_type") if account else None
    voeg("ZA-08", "laag", model == "Federated" and ai_n <= 20 if model and ai_n is not None else None,
         {"model": "Federated", "weinig_gebruik": True}, "AI Companion gebruikt externe modellen bij beperkt gebruik.",
         "Overweeg alleen modellen die Zoom zelf host.")
    summary = account.get("ai.meeting_summary.enable") if account else None
    retention = account.get("ai.meeting_summary_retention.enable") if account else None
    voeg("ZA-09", "laag", summary and not retention if summary is not None and retention is not None else None,
         {"bewaartermijn": False}, "AI-samenvattingen hebben geen actieve bewaartermijn.",
         "Zet een bewaartermijn van 30 dagen aan.")

    zwaar = (app.get("met_schrijfrechten") if app else None)
    aantal_zwaar = len(zwaar) if zwaar is not None else None
    onbekende_rechten = app.get("onbekende_rechten") if app else None
    if onbekende_rechten is None and app and isinstance(app.get("overzicht"), list) and \
            app.get("aantal") == len(app["overzicht"]) and all(isinstance(x, dict) for x in app["overzicht"]):
        onbekende_rechten = sum(x.get("rechten") is None or x.get("schrijf") is None
                                 for x in app["overzicht"])
    vaste_banden = sorted((x["code"], 50 if x["schrijf"] >= 50 else 10 if x["schrijf"] >= 10 else 5)
                          for x in (zwaar or []))
    if zwaar:
        open10 = True
    elif zwaar is None or onbekende_rechten is None or onbekende_rechten:
        open10 = None
    else:
        open10 = False
    zwaar_tekst = "app heeft" if aantal_zwaar == 1 else "apps hebben"
    reden10 = f"{aantal_zwaar} {zwaar_tekst} vijf of meer schrijfrechten."
    if onbekende_rechten:
        onbekend_tekst = "app" if onbekende_rechten == 1 else "apps"
        reden10 = (f"Minstens {aantal_zwaar} {zwaar_tekst} vijf of meer schrijfrechten; "
                   f"bij {onbekende_rechten} {onbekend_tekst} zijn de rechten onbekend.")
    voeg("ZA-10", "middel", open10,
         {"apps": [code for code, _ in vaste_banden], "banden": [band for _, band in vaste_banden]},
         reden10,
         "Kijk op de accountbrede apppagina na of deze rechten nog nodig zijn.")
    leeg_r = role.get("eigen_leeg") if role else None
    leeg_g = group.get("leeg") if group else None
    voeg("ZA-11", "laag", (leeg_r > 0 or leeg_g > 0) if leeg_r is not None and leeg_g is not None else None,
         {"lege_eigen_rollen": bool(leeg_r), "lege_groepen": bool(leeg_g)},
         f"Er zijn {leeg_r} lege eigen rollen en {leeg_g} lege groepen.", "Kijk lege rollen en groepen na.")
    afmelden = sec.get("afmelden") if sec else None
    voeg("ZA-12", "laag", afmelden == "uit" if afmelden is not None else None, {"afmelden": "uit"},
         "Automatisch afmelden na inactiviteit staat uit.", "Zet automatisch afmelden aan.")
    api_wijzig = sum(n for k, n in (logs.get("tellingen") or {}).items()
                     if k.startswith("User Settings / REST API") and isinstance(n, int)) if logs else None
    voeg("ZA-13", "laag", api_wijzig >= 10 if api_wijzig is not None else None, {"api_wijzigingen": True},
         f"Het beheerlogboek telt {api_wijzig} API-wijzigingen van gebruikersinstellingen in 30 dagen.",
         "Kijk in Zoom na welke app deze instellingen verandert.")
    klaar = rec.get("klaar") if rec else None
    tr_pct = rec.get("transcript_pct") if rec else None
    voeg("ZA-14", "hoog", uop == "cloud" and utr is True and klaar >= 5 and tr_pct < 80
         if klaar is not None and (tr_pct is not None or klaar < 5)
         and uop is not None and utr is not None else None,
         {"transcript_band": "onder_80"}, "Afgewerkte cloudopnames missen vaak een transcript.",
         "Kijk het Zoom-vangnet en de transcriptinstelling na.")
    users = _bekend(d, "gebruikers")
    login = users.get("login_types") if users else None
    fb = sec.get("facebook") if sec else None
    sms = sec.get("sms") if sec else None
    # Alleen de bevestigde code 0 voor Facebook. Voor sms is de code nog niet bevestigd.
    voeg("ZA-15", "laag", fb and login.get("0") is None if fb is not None and isinstance(login, dict) else None,
         {"facebook_ongebruikt": True}, "Facebook staat aan maar geen actieve gebruiker gebruikt die aanmeldwijze.",
         "Overweeg de ongebruikte aanmeldwijze uit te zetten.")

    if staat_acc is not None:
        regels = staat_acc.setdefault("regels", {})
        for a in uit:
            code = a["code"]
            oud = regels.get(code) or {}
            cyclus = int(oud.get("cyclus") or 0)
            if oud.get("toestand") == "goed" and a["toestand"] == "open":
                cyclus += 1
            if a["toestand"] != "onbekend":
                regels[code] = {"toestand": a["toestand"], "cyclus": cyclus}
            a["cyclus"] = cyclus
    return uit


def voorstellen_lezen():
    return bord.db_lees("SELECT id, actie, parameters, status, besluit_ts, ts FROM voorstel "
                        "WHERE naam='zoom-wacht' AND runbook='' ORDER BY id")


def _params(r):
    try:
        return json.loads(r.get("parameters") or "{}")
    except (ValueError, TypeError):
        return {}


def _zelfde(a, r):
    p = _params(r)
    return p.get("zoom_advies") == a["code"] and p.get("cyclus", 0) == a.get("cyclus", 0) and \
        p.get("stand") == a["stand"] and r.get("status") != "vervallen"


def _verouderd(a, r):
    """Een open ZA-01-voorstel van voor De Zoomarchivaris: zijn stand kent de kopie niet. Het houdt het advies met een
    bewezen kopie niet tegen (Codex, Zoomarchief controle 2); Mehdi weigert het oude zelf."""
    stand = _params(r).get("stand")
    return a["code"] == "ZA-01" and isinstance(stand, dict) and "kopie" not in stand


def te_versturen(adviezen_lijst, voorstellen, klok, max_nieuw=3):
    week = week_van(klok)
    deze_week = sum(1 for r in voorstellen if _week_ts(r.get("ts")) == week and _params(r).get("zoom_advies"))
    kandidaten = []
    for a in adviezen_lijst:
        if a["toestand"] != "open":
            continue
        bij_regel = [r for r in voorstellen if _params(r).get("zoom_advies") == a["code"]]
        if any(_zelfde(a, r) for r in bij_regel) or any(r.get("status") == "open" and not _verouderd(a, r)
                                                         for r in bij_regel):
            continue
        kandidaten.append(a)
    kandidaten.sort(key=lambda a: (ERNST[a["ernst"]], a["code"]))
    geselecteerd = [a for a in kandidaten if a["ernst"] == "hoog"]
    resterend = max(0, max_nieuw - deze_week - len(geselecteerd))
    geselecteerd += [a for a in kandidaten if a["ernst"] != "hoog"][:resterend]
    wachtrij = [a["code"] for a in kandidaten if a not in geselecteerd]
    # ochtend.py toont de laatste twee voorstel-id's apart: hoog wordt daarom als laatste gezet.
    return sorted(geselecteerd, key=lambda a: (-ERNST[a["ernst"]], a["code"],)), wachtrij


def _week_ts(ts):
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return week_van(t if t.tzinfo else t.replace(tzinfo=timezone.utc))
    except ValueError:
        return ""


def voorstel_van(a, week):
    params = {"cyclus": a.get("cyclus", 0), "regelversie": 1, "stand": a["stand"], "zoom_advies": a["code"]}
    params = json.loads(json.dumps(params, sort_keys=True))
    code = a["code"]
    if code == "ZA-08":
        handeling = ("Aanpak: vraag met een ticket bij Zoom Support om Zoom-Hosted Models Only (ZMO). "
                    "Tickettekst: 'Please switch our account's Zoom AI deployment to Zoom-Hosted Models Only (ZMO).' "
                    "Vraag of Nederlandse samenvattingen blijven werken. Goedkeuren: jij beslist over het ticket; "
                    "ik verstuur niets en controleer de stand later.")
    elif code in ONZEKERE_PADEN:
        handeling = (f"Pad (te bevestigen): {KLIKPADEN[code]}. Controleer de werking in je account. "
                    "Goedkeuren: jij wijzigt zelf; ik lees later terug.")
    else:
        handeling = (f"Klikpad: {KLIKPADEN[code]}. "
                    "Goedkeuren: jij zet dit zelf in Zoom; ik controleer de stand later.")
    reden = (f"Nu: {a['reden']} Waarom: {a['doel']} {handeling} "
             f"Ernst: {a['ernst']}. Gemeten in {week}. "
             "Weigeren: ik vraag het bij dezelfde stand niet opnieuw.")
    return {"actie": REGELS[a["code"]]["actie"], "doel": a["doel"], "reden": reden[:1000],
            "parameters": params, "runbook": ""}


def basis_van(d, vorige_basis=None, week=None):
    """Bewaar de laatst bewezen apprechten en hun meetweek voor de vergelijking."""
    a = _bekend(d, "account") or {}
    s = _bekend(d, "security") or {}
    u = _bekend(d, "user") or {}
    locks = _bekend(d, "locks") or {}
    ap = _bekend(d, "apps") or {}
    log = _bekend(d, "logboek") or {}
    inst = {k: a[k] for k in ("in_meeting.waiting_room", "recording.cloud_recording",
                               "recording.auto_delete_cmr") if k in a}
    if s.get("tweestaps"):
        inst["security.sign_in_with_two_factor_auth"] = s["tweestaps"]
    vorige_apps = vorige_basis.get("apps") if isinstance(vorige_basis, dict) else None
    app_basis = {}
    for x in ap.get("overzicht", []):
        oud = vorige_apps.get(x["code"]) if isinstance(vorige_apps, dict) else None
        app = {"naam": x["naam"], "gepubliceerd": x["gepubliceerd"]}
        if _tel(x["rechten"]) is not None and _tel(x["schrijf"]) is not None:
            app.update(rechten=x["rechten"], schrijf=x["schrijf"], gemeten_week=week)
        elif isinstance(oud, dict) and _tel(oud.get("rechten")) is not None and \
                _tel(oud.get("schrijf")) is not None:
            # Oudere staat had geen meetweek. Bewaar de telling, maar verzin geen datum.
            bewijsweek = oud.get("gemeten_week")
            app.update(rechten=oud["rechten"], schrijf=oud["schrijf"],
                       gemeten_week=bewijsweek if isinstance(bewijsweek, str) and
                       re.fullmatch(r"\d{4}-W\d{2}", bewijsweek) else None)
        else:
            app.update(rechten=None, schrijf=None, gemeten_week=None)
        app_basis[x["code"]] = app
    return {"instellingen": inst,
            "opname": {k: u[k] for k in ("recording.auto_recording", "recording.recording_audio_transcript") if k in u},
            "vergrendelingen": locks.get("velden") or {},
            "beheerlogboek": log.get("gevoelig") or {},
            "apps": app_basis}


def actuele_appmeting(d, week):
    """De lezing van deze ronde, ook als een wijzigingsmelding de basis vasthoudt."""
    ap = _bekend(d, "apps")
    overzicht = ap.get("overzicht") if ap else None
    if not isinstance(overzicht, list):
        return {"week": week, "stand": "onbekend: appslijst ontbreekt",
                "onbekende_rechten": None, "apps": {}}
    onbekend = _tel(ap.get("onbekende_rechten"))
    if onbekend is None:
        onbekend = sum(x.get("rechten") is None or x.get("schrijf") is None for x in overzicht)
    return {"week": week, "stand": "ok", "onbekende_rechten": onbekend,
            "apps": {x["code"]: {"rechten": x["rechten"], "schrijf": x["schrijf"]}
                     for x in overzicht}}


def laatst_bewezen_apprechten(vorige, actueel):
    """Werk echt gemeten rechten bij, onafhankelijk van de meldingsbasis."""
    vorige = vorige if isinstance(vorige, dict) else {}
    if actueel["stand"] != "ok":
        return copy.deepcopy(vorige)
    bewijs = {}
    for code, meting in actueel["apps"].items():
        if _tel(meting["rechten"]) is not None and _tel(meting["schrijf"]) is not None:
            bewijs[code] = {"rechten": meting["rechten"], "schrijf": meting["schrijf"],
                            "gemeten_week": actueel["week"]}
        elif code in vorige:
            bewijs[code] = copy.deepcopy(vorige[code])
    return bewijs


def apprechten_veranderd(vorige_basis, huidige_apps, laatste_bewijs=None):
    """Vergelijk alleen gemeten aantallen; meld ook niet vergelijkbare apps."""
    vorig = (vorige_basis or {}).get("apps")
    bewijs = laatste_bewijs if isinstance(laatste_bewijs, dict) else {}
    huidige_lijst = huidige_apps.get("overzicht") if isinstance(huidige_apps, dict) and \
        not str(huidige_apps.get("stand", "")).startswith("onbekend") else None
    if not isinstance(huidige_lijst, list):
        return {"stand": "onbekend: huidige appmeting ontbreekt", "overzicht": [],
                "onbekende_vergelijkingen": None}
    if not isinstance(vorig, dict) and not bewijs:
        return {"stand": "onbekend: vorige of huidige appmeting ontbreekt", "overzicht": [],
                "onbekende_vergelijkingen": len(huidige_lijst)}
    nu = {x["code"]: x for x in huidige_lijst}
    vorig = dict(vorig) if isinstance(vorig, dict) else {}
    for code, meting in bewijs.items():
        oud = vorig.get(code)
        if code not in vorig or isinstance(oud, dict) and any(
                _tel(oud.get(k)) is None for k in ("rechten", "schrijf")):
            vorig[code] = meting
    veranderd = []
    # Nieuwe en verdwenen apps hebben geen meting aan beide kanten van de vergelijking.
    onbekend = len(vorig.keys() ^ nu.keys())
    for code in sorted(vorig.keys() & nu.keys()):
        oud, nieuw = vorig[code], nu[code]
        if any(_tel(oud.get(k)) is None or _tel(nieuw.get(k)) is None for k in ("rechten", "schrijf")):
            onbekend += 1
            continue
        if any(oud.get(k) != nieuw.get(k) for k in ("rechten", "schrijf")):
            veranderd.append({"naam": nieuw["naam"], "rechten_van": oud.get("rechten"),
                              "rechten_naar": nieuw["rechten"], "schrijf_van": oud.get("schrijf"),
                              "schrijf_naar": nieuw["schrijf"]})
    return {"stand": "onbekend: niet alle apprechten zijn vergelijkbaar" if onbekend else "ok",
            "overzicht": veranderd, "onbekende_vergelijkingen": onbekend}


def verschil(oud, nieuw):
    velden = []
    for blok in ("instellingen", "opname", "vergrendelingen"):
        a, b = oud.get(blok) or {}, nieuw.get(blok) or {}
        for k in sorted(set(a) & set(b)):
            if a[k] != b[k]:
                velden.append({"veld": k, "van": a[k], "naar": b[k]})
    apps_oud, apps_nieuw = oud.get("apps") or {}, nieuw.get("apps") or {}
    nieuw_apps = [apps_nieuw[k] for k in sorted(apps_nieuw.keys() - apps_oud.keys())]
    weg = [apps_oud[k] for k in sorted(apps_oud.keys() - apps_nieuw.keys())]
    log_oud, log_nieuw = oud.get("beheerlogboek") or {}, nieuw.get("beheerlogboek") or {}
    handelingen = sum(max(0, n - log_oud.get(k, 0)) for k, n in log_nieuw.items())
    return {"instellingen": velden, "apps_nieuw": nieuw_apps, "apps_weg": weg,
            "beheerhandelingen": handelingen}


def vingerafdruk(obj):
    return _ident(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


UITVOER_SLEUTELS = frozenset((
    "naam status taak detail voorstel actie doel reden parameters runbook regelversie stand cyclus zoom_advies "
    "wisregel kopie band cloud geluid transcript video tweestaps wachtkamer vergrendeld codes_vergrendeld_uit "
    "code voor_host locatie model weinig_gebruik bewaartermijn apps banden lege_eigen_rollen lege_groepen "
    "afmelden api_wijzigingen transcript_band facebook_ongebruikt voor soort sleutel uniek titel inhoud "
    "week gemeten scan delen beveiliging opnames ai licenties gebruik adviezen wachtrij tekst rollen "
    "doorgevoerd goedgekeurd_niet_doorgevoerd afmelden vergrendelingen groepen leeg leden eigen_leeg "
    "vaste_vergaderruimte voor_host toegangscode auto_opname aanmeldingen_7d aanmelden "
    "afmelden_7d beheerlogboek_30d laatste_30d bestanden mb transcript_pct kort_2min "
    "instellingen auto_opname_gebruiker cloud_opname transcript_aan opslaglocatie samenvattingen_30d "
    "bewaartermijn_aan gemaakte_apps aanvragen geblokkeerd goedgekeurd maand_tot_nu meetings deelnemers minuten "
    "nieuw goed onbekend ernst toestand opslag pct gebruikt_gb gratis_gb betaald_gb groei_gb_per_dag "
    "vol_rond aantal eigen onbekende_rechten met_schrijfrechten rechten schrijf gepubliceerd Owner Admin Member "
    "pakket periode hosts sinds volgende_factuur licensed basic room pending in_gebruik actief inactief "
    "hosts_30d facturen kenmerken gebruiker dienst oordeel aanvragen geblokkeerd goedgekeurd "
    "wijziging tot instellingen apps_nieuw apps_weg beheerhandelingen veld van naar "
    "rechten_veranderd onbekende_vergelijkingen rechten_van rechten_naar schrijf_van schrijf_naar onderwerp stap"
).split())
_VERBODEN_SLEUTELS = re.compile(r"(?:email|ip_address|operator|operation_detail|topic|host_email|user_name|first_name|last_name|phone|pmi|password|passcode|pwd|token|secret|download_url|play_url|share_url|meeting_id)", re.I)
_PATRONEN = (re.compile(r"@"), re.compile(r"\d{9,}"), re.compile(r"(?:\d{1,3}\.){3}\d{1,3}"),
             re.compile(r"(?<![\w-])(?:\+\s?\d{1,3}|0\d{1,3})[\s().-]+(?:\d[\s().-]*){6,12}(?![\w-])"),
             re.compile(r"\b(?:[0-9A-Fa-f]*[a-fA-F][0-9A-Fa-f]*:){2,}[0-9A-Fa-f:]+\b|\b[0-9A-Fa-f]{0,4}::[0-9A-Fa-f:]*\b"),
             re.compile(r"(?<![\w:])::[0-9A-Fa-f]{1,4}(?![\w:])"),
             re.compile(r"https?://|zoom\.us/(?:j/|my(?:/|-|$))", re.I))


def schoon(item):
    """Uitgaande payload: vaste sleutels en geen herkenbaar persoonsgegeven of URL."""
    def loop(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if not isinstance(k, str) or k not in UITVOER_SLEUTELS or _VERBODEN_SLEUTELS.search(k):
                    raise PrivacyFout("veld buiten witte lijst")
                loop(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                loop(v)
        elif isinstance(x, str) and any(p.search(x) for p in _PATRONEN):
            raise PrivacyFout("privéwaarde in accountuitvoer")
    loop(item)
    return item


def weekoverzicht(d, adv, wachtrij, week, klok, volledig):
    delen = {k: "ok" for k in SECTIES}
    koppeling = {"security": "beveiliging", "meeting_security": "beveiliging", "locks": "beveiliging",
                "ruimte": "beveiliging", "rollen": "beveiliging", "groepen": "beveiliging",
                "activiteiten": "beveiliging", "logboek": "beveiliging", "account": "beveiliging",
                "user": "opnames", "opslag": "opnames", "opslagtrend": "opnames", "opnames": "opnames", "samenvattingen": "ai",
                "pakket": "licenties", "samenvatting": "licenties", "gebruikers": "licenties",
                "facturen": "licenties", "apps": "apps", "daggebruik": "gebruik",
                "rapport_actief": "gebruik", "rapport_inactief": "gebruik"}
    for bron, deel in koppeling.items():
        if bron == "opslagtrend" and bron not in d:
            continue
        if _bekend(d, bron) is None:
            bronwaarde = d.get(bron)
            reden = bronwaarde.get("stand", "bron ontbreekt") if isinstance(bronwaarde, dict) else "bron ontbreekt"
            delen[deel] = "onbekend: " + reden.removeprefix("onbekend: ")
    opslag_d = _bekend(d, "opslag")
    opn_d = _bekend(d, "opnames")
    apps_d = _bekend(d, "apps")
    rollen_d = _bekend(d, "rollen")
    account_d = _bekend(d, "account")
    user_d = _bekend(d, "user")
    lock_d = _bekend(d, "locks")
    room_d = _bekend(d, "ruimte")
    groepen_d = _bekend(d, "groepen")
    security_d = _bekend(d, "security")
    act_d = _bekend(d, "activiteiten")
    daily_d = _bekend(d, "daggebruik")
    app_rechten = d.get("app_rechten") if isinstance(d.get("app_rechten"), dict) else None
    wijzigingen = app_rechten.get("overzicht") if app_rechten else None
    onbekende_vergelijkingen = app_rechten.get("onbekende_vergelijkingen") if app_rechten else None
    rechten_veranderd = wijzigingen if isinstance(wijzigingen, list) and \
        (wijzigingen or app_rechten.get("stand") == "ok" and onbekende_vergelijkingen == 0) else \
        "onbekend: appvergelijking ontbreekt"
    content = {"soort": "weekoverzicht", "week": week, "gemeten": klok.isoformat(),
               "scan": "volledig" if volledig else "gedeeltelijk", "delen": delen,
               "beveiliging": {"tweestaps": _waarde(security_d, "tweestaps"),
                                "afmelden": _waarde(security_d, "afmelden"),
                                "wachtkamer": _waarde(account_d, "in_meeting.waiting_room"),
                                "vergrendelingen": _waarde(lock_d, "aantal"),
                                "rollen": {**{k: _waarde(rollen_d.get("standaard") if rollen_d else None, k)
                                              for k in ("Owner", "Admin", "Member")},
                                           "eigen_leeg": _waarde(rollen_d, "eigen_leeg")},
                                "groepen": {k: _waarde(groepen_d, k) for k in ("aantal", "leeg", "leden")},
                                "vaste_vergaderruimte": {k: _waarde(room_d, k) for k in
                                                         ("wachtkamer", "voor_host", "toegangscode", "auto_opname")},
                                "aanmeldingen_7d": {"aanmelden": _waarde(act_d, "aanmelden"),
                                                    "afmelden_7d": _waarde(act_d, "afmelden")},
                                "beheerlogboek_30d": _waarde(_bekend(d, "logboek"), "aantal")},
               "opnames": {"opslag": {k: _waarde(opslag_d, k, "trend of opslagveld ontbreekt") for k in
                                        ("gebruikt_gb", "gratis_gb", "betaald_gb", "pct", "groei_gb_per_dag", "vol_rond")},
                            "laatste_30d": {k: _waarde(opn_d, k) for k in
                                           ("aantal", "bestanden", "mb", "transcript_pct", "kort_2min")},
                            "instellingen": {"auto_opname_gebruiker": _waarde(user_d, "recording.auto_recording"),
                                             "cloud_opname": _waarde(account_d, "recording.cloud_recording"),
                                             "transcript_aan": _waarde(user_d, "recording.recording_audio_transcript"),
                                             "wisregel": _waarde(account_d, "recording.auto_delete_cmr"),
                                             "opslaglocatie": _waarde(user_d, "opslaglocatie")}},
               "ai": {"model": _waarde(_bekend(d, "account"), "ai.ai_model_type"),
                      "samenvattingen_30d": _waarde(_bekend(d, "samenvattingen"), "aantal"),
                      "bewaartermijn_aan": _waarde(account_d, "ai.meeting_summary_retention.enable")},
               "licenties": {**{k: _waarde(_bekend(d, "samenvatting"), k) for k in ("licensed", "basic", "room", "pending")},
                             "pakket": {k: _waarde(_bekend(d, "pakket"), k) for k in ("periode", "hosts")}},
               "apps": {"aantal": _waarde(apps_d, "aantal"), "eigen": _waarde(apps_d, "eigen"),
                        "onbekende_rechten": _waarde(apps_d, "onbekende_rechten"),
                        "gemaakte_apps": _waarde(_bekend(d, "gemaakt"), "aantal", "niet beschikbaar"),
                        "aanvragen": _waarde(_bekend(d, "aanvragen"), "aantal", "niet beschikbaar"),
                        "geblokkeerd": _waarde(_bekend(d, "geblokkeerd"), "aantal", "niet beschikbaar"),
                        "goedgekeurd": _waarde(_bekend(d, "goedgekeurd"), "aantal", "niet beschikbaar"),
                        "met_schrijfrechten": [{"naam": x["naam"], "rechten": x["rechten"], "schrijf": x["schrijf"]}
                                                for x in (apps_d.get("met_schrijfrechten", []) if apps_d else [])[:6]],
                        "rechten_veranderd": rechten_veranderd,
                        "onbekende_vergelijkingen": _waarde(app_rechten, "onbekende_vergelijkingen",
                                                          "eerste scan of appdetail ontbreekt")},
               "gebruik": {"actief": _waarde(_bekend(d, "rapport_actief"), "aantal"),
                           "inactief": _waarde(_bekend(d, "rapport_inactief"), "aantal"),
                           "maand_tot_nu": {"meetings": _waarde(daily_d, "meetings"),
                                             "deelnemers": _waarde(daily_d, "participants"),
                                             "minuten": _waarde(daily_d, "meeting_minutes")}},
               "adviezen": [{k: a[k] for k in ("code", "ernst", "toestand", "voorstel", "status") if k in a}
                            for a in adv], "wachtrij": wachtrij,
               "doorgevoerd": [a["code"] for a in adv if a.get("status") == "doorgevoerd"],
               "goedgekeurd_niet_doorgevoerd": [a["code"] for a in adv if a.get("status") == "goedgekeurd, nog niet doorgevoerd"],
               "tekst": f"Zoom-account week {week}: {sum(a['toestand']=='open' for a in adv)} open adviezen; "
                       f"{sum(a['toestand']=='onbekend' for a in adv)} onbekend. Beslis over voorstellen op het bord."}
    item = {"voor": "mehdi", "soort": "zoom-account", "sleutel": "", "uniek": f"zoom-account:{week}",
            "titel": f"Zoom-account {week}: {sum(a['toestand']=='open' for a in adv)} open adviezen",
            "inhoud": content}
    return schoon(item)


def gebruiksmelding(d, week, klok):
    s = _bekend(d, "samenvatting")
    p = _bekend(d, "pakket")
    opslag_d = _bekend(d, "opslag")
    factuur = d.get("facturen")
    factuurstand = factuur.get("stand", "onbekend: factuurlijst ontbreekt") if isinstance(factuur, dict) \
        else "onbekend: factuurlijst ontbreekt"
    c = {"dienst": "Zoom", "gebruiker": "account", "stand": dag_van(klok),
         "week": f"{_waarde(s, 'licensed')} licenties; opslag {_waarde(opslag_d, 'gebruikt_gb')} GB",
         "oordeel": "", "pakket": {k: _waarde(p, k) for k in ("periode", "hosts", "sinds", "volgende_factuur")},
         "licenties": {k: _waarde(s, k) for k in ("licensed", "basic", "room", "pending")},
         "hosts_30d": {"actief": _waarde(_bekend(d, "rapport_actief"), "aantal"),
                       "inactief": _waarde(_bekend(d, "rapport_inactief"), "aantal")},
         "opslag": {k: _waarde(opslag_d, k, "trend of opslagveld ontbreekt") for k in ("gratis_gb", "betaald_gb", "gebruikt_gb", "pct", "groei_gb_per_dag", "vol_rond")},
         "facturen": factuurstand}
    return schoon({"voor": "licentiewacht", "soort": "gebruik", "sleutel": "account",
                  "uniek": f"zoom-gebruik:{week}", "titel": f"Zoom-account {week}: gebruik voor De Licentiewacht", "inhoud": c})


def wijzigingsmelding(v, oud, week, klok, volgnummer=0):
    # Het bord ontdubbelt op uniek. Een monotone teller maakt A-B-A-B opnieuw
    # zichtbaar; bij een mislukte klaarzet blijft het nummer gelijk.
    hashdeel = vingerafdruk({"volgnummer": volgnummer, "oud": vingerafdruk(oud), "verschil": v})
    c = {"soort": "wijziging", "week": week, "gemeten": klok.isoformat(),
         "instellingen": v["instellingen"],
         "beheerhandelingen": v["beheerhandelingen"],
         "apps_nieuw": [{k: x[k] for k in ("naam", "rechten", "schrijf")} for x in v["apps_nieuw"]],
         "apps_weg": [{k: x[k] for k in ("naam", "rechten", "schrijf")} for x in v["apps_weg"]]}
    return schoon({"voor": "mehdi", "soort": "zoom-account", "sleutel": "",
                  "uniek": f"zoom-account:wijziging:{hashdeel}",
                  "titel": "Zoom-account gewijzigd: instellingen of apps", "inhoud": c})


def _aanvaard(antwoord):
    return isinstance(antwoord, dict) and sum(int(antwoord.get(k) or 0) for k in ("nieuw", "bijgewerkt", "bestaand")) >= 1


def _adviesstatus(adv, voorstellen, klok):
    for a in adv:
        passend = [x for x in voorstellen if _params(x).get("zoom_advies") == a["code"]]
        if not passend:
            continue
        rij = passend[-1]
        if type(rij.get("id")) is int:
            a["voorstel"] = rij["id"]
        status = rij.get("status")
        if a["toestand"] == "goed" and status == "goedgekeurd":
            a["status"] = "doorgevoerd"
        elif a["toestand"] == "open" and status == "goedgekeurd":
            try:
                besluit = datetime.fromisoformat(str(rij.get("besluit_ts") or "").replace("Z", "+00:00"))
                if besluit.tzinfo and klok - besluit >= timedelta(days=14):
                    a["status"] = "goedgekeurd, nog niet doorgevoerd"
                else:
                    a["status"] = "goedgekeurd"
            except ValueError:
                a["status"] = "goedgekeurd"
        elif status in {"open", "geweigerd", "vervallen"}:
            a["status"] = status


def _schrijf_item(acc, item):
    schoon(item)
    return _aanvaard(acc.klaarzet([item]))


def _noden(r, fouten, volledig, opslag_d):
    if not volledig:
        r.nood("Zoom-accountscan van deze week nog niet gelukt", "claude-code")
    for _groep, _bron, reden in fouten:
        if reden.startswith("geen recht "):
            r.nood(f"Zoom-leesapp mist het recht {reden[len('geen recht '):]} voor de accountscan", "mehdi")
    if isinstance(opslag_d, dict) and type(opslag_d.get("pct")) in (int, float) and opslag_d["pct"] >= 100:
        r.nood(NOOD_OPSLAG_VOL, "mehdi")


def _herhaal_scannoden(r, scannoden):
    """Een hartslag noemt alle nog actieve scannoden, ook zonder nieuwe weekscan."""
    if scannoden.get("opslag_vol") is True:
        r.nood(NOOD_OPSLAG_VOL, "mehdi")
    if scannoden.get("pakket_veranderd") is True:
        r.nood(NOOD_PAKKET, "claude-code")
    gemeld = set()
    for melding in scannoden.get("rechten", []):
        recht = melding.get("recht") if isinstance(melding, dict) else melding
        if isinstance(recht, str) and (recht in {"onbekend", "download"} or SCOPE_PATROON.fullmatch(recht)):
            if recht not in gemeld:
                r.nood(f"Zoom-leesapp mist het recht {recht} voor de accountscan", "mehdi")
                gemeld.add(recht)


def herhaal_bewaarde_scannoden(r, staat):
    """Herhaal de bekende scannoden bij een Zoom-ronde die de accountscan niet kan bereiken."""
    if not scan_aan(r.werkwijze):
        return
    wisregel_wacht(r)
    account = staat.get("account") if isinstance(staat, dict) else None
    scannoden = account.get("scannoden") if isinstance(account, dict) else None
    if isinstance(scannoden, dict):
        _herhaal_scannoden(r, scannoden)


def ronde(r, w, staat, klok, gesprekken=0, forceer=False):
    """Een accountdeel binnen de bestaande Zoom-ronde; schrijft staat pas na geslaagde bordstappen."""
    if not scan_aan(r.werkwijze):
        return ""
    wisregel_wacht(r)
    oud = copy.deepcopy(staat.get("account") or {})
    vorige_noden = oud.get("scannoden") if isinstance(oud.get("scannoden"), dict) else {}
    scannoden = copy.deepcopy(vorige_noden)
    if not w.get("identiteit_ok") or not w.get("ik") or not Z.leesapp() or Z.leesapp_fout() or Z.leesapp_verboden():
        r.nood("Zoom-accountscan van deze week nog niet gelukt", "claude-code")
        _herhaal_scannoden(r, scannoden)
        return "accountscan niet mogelijk"
    acc = bord.Agent("zoom-wacht")  # leeg privé-masker; uitsluitend schoon() mag deze instantie gebruiken
    nieuw = copy.deepcopy(oud)
    week = week_van(klok)
    volledig = False
    d = {}
    fouten = []
    vragen = 0
    weekscan = forceer or aan_de_beurt(oud, klok)
    overzicht_ok = False
    if weekscan:
        d, fouten, volledig, vragen = lees_week(w["ik"]["id"], str(w["ik"]["pmi"]), klok)
        weekbasis = oud.get("rechten_weekbasis")
        if not isinstance(weekbasis, dict) or weekbasis.get("week") != week:
            vorige_basis = oud.get("basis") if isinstance(oud.get("basis"), dict) else {}
            weekbasis = {"week": week, "apps": copy.deepcopy(vorige_basis.get("apps"))}
        nieuw["rechten_weekbasis"] = weekbasis
        d["app_rechten"] = apprechten_veranderd(weekbasis, _bekend(d, "apps"),
                                               oud.get("laatst_bewezen_apprechten"))
        adv = adviezen(d, gesprekken, nieuw)
        try:
            voorstellen = voorstellen_lezen()
        except bord.BordOnbekend:
            voorstellen = None
            r.nood("Zoom-advies niet terug te lezen op het bord", "claude-code")
            volledig = False
        wachtrij = []
        if voorstellen is not None:
            gekozen, wachtrij = te_versturen(adv, voorstellen, klok)
            for a in gekozen:
                voorstel = voorstel_van(a, week)
                try:
                    schoon({"naam": "zoom-wacht", "status": "actief", "taak": "Zoom-account: advies", "voorstel": voorstel})
                except PrivacyFout:
                    r.nood("Zoom-accountuitvoer geweigerd door de privacygrendel", "claude-code")
                    volledig = False
                    continue
                acc.hartslag("actief", taak="Zoom-account: advies", voorstel=voorstel)
                try:
                    terug = voorstellen_lezen()
                except bord.BordOnbekend:
                    terug = []
                if not any(_zelfde(a, x) and x.get("id") for x in terug):
                    r.nood("Zoom-advies niet terug te lezen op het bord", "claude-code")
                    volledig = False
                else:
                    voorstellen = terug
                    nieuw.setdefault("adviezen", {})[a["code"]] = next(x["id"] for x in terug if _zelfde(a, x) and x.get("id"))
            _adviesstatus(adv, voorstellen, klok)
        try:
            overzicht_ok = _schrijf_item(acc, weekoverzicht(d, adv, wachtrij, week, klok, volledig))
            gebruik_ok = _schrijf_item(acc, gebruiksmelding(d, week, klok))
            volledig = volledig and overzicht_ok and gebruik_ok
        except PrivacyFout:
            r.nood("Zoom-accountuitvoer geweigerd door de privacygrendel", "claude-code")
            volledig = False
        except Exception:  # noqa: BLE001
            volledig = False
        _noden(r, [], volledig, None)
        opslag_d = _bekend(d, "opslag")
        pct = opslag_d.get("pct") if opslag_d else None
        if type(pct) in (int, float):
            if pct >= 100:
                scannoden["opslag_vol"] = True
            else:
                scannoden["opslag_vol"] = False
        foute_bronnen = {bron for _, bron, _ in fouten}
        rechten = set()
        for melding in scannoden.get("rechten", []):
            bron = melding.get("bron") if isinstance(melding, dict) else ""
            recht = melding.get("recht") if isinstance(melding, dict) else melding
            if not isinstance(bron, str) or not isinstance(recht, str):
                continue
            # Oude staat bevatte alleen een recht. Zonder bron kan dat pas weg als alle delen leesbaar zijn.
            if bron == "":
                if not (volledig and all(_bekend(d, naam) is not None for naam in d)):
                    rechten.add((bron, recht))
            elif bron in foute_bronnen or _bekend(d, bron) is None:
                rechten.add((bron, recht))
        rechten.update((bron, reden[len("geen recht "):]) for _, bron, reden in fouten
                       if reden.startswith("geen recht "))
        scannoden["rechten"] = [{"bron": bron, "recht": recht} for bron, recht in sorted(rechten)]
        nieuw_pakket = _bekend(d, "pakket")
        if nieuw_pakket:
            vorig_pakket = oud.get("pakket")
            if vorig_pakket and any(vorig_pakket.get(k) != nieuw_pakket.get(k) for k in ("periode", "hosts")):
                scannoden["pakket_veranderd"] = True
            elif volledig:
                scannoden["pakket_veranderd"] = False
            nieuw["pakket"] = {k: nieuw_pakket.get(k) for k in ("periode", "hosts")}
        if volledig:
            nieuw["laatste_volledig"] = week
    # De kleine wijzigingscontrole gebruikt de samenvatting van de weekscan of een eigen beperkte lezing.
    if not d:
        d, fouten_w, vragen_w = lees_wijziging(w["ik"]["id"], klok, oud.get("basis") or {})
        vragen += vragen_w
        if fouten_w:
            nieuw["wijziging_fouten"] = int(oud.get("wijziging_fouten") or 0) + 1
            if nieuw["wijziging_fouten"] >= 2:
                r.nood("Zoom-wijzigingscontrole twee rondes na elkaar niet gelezen", "claude-code")
        else:
            nieuw["wijziging_fouten"] = 0
    nieuw["actuele_appmeting"] = actuele_appmeting(d, week)
    vorig_bewijs = oud.get("laatst_bewezen_apprechten")
    if not isinstance(vorig_bewijs, dict):
        vorige_apps = (oud.get("basis") or {}).get("apps") or {}
        vorig_bewijs = {code: {"rechten": app["rechten"], "schrijf": app["schrijf"],
                               "gemeten_week": app.get("gemeten_week")}
                        for code, app in vorige_apps.items() if isinstance(app, dict) and
                        _tel(app.get("rechten")) is not None and _tel(app.get("schrijf")) is not None}
    nieuw["laatst_bewezen_apprechten"] = laatst_bewezen_apprechten(
        vorig_bewijs, nieuw["actuele_appmeting"])
    basis = basis_van(d, oud.get("basis"), week)
    if weekscan and volledig and nieuw["rechten_weekbasis"].get("apps") is None:
        # De eerste geslaagde scan legt de referentie voor latere scans in dezelfde week vast.
        nieuw["rechten_weekbasis"]["apps"] = copy.deepcopy(basis["apps"])
    if (not weekscan or volledig) and all(_bekend(d, k) is not None for k in
                                              ("account", "security", "user", "locks", "apps", "logboek")):
        vorige = oud.get("basis")
        if not vorige:
            nieuw["basis"] = basis
        else:
            v = verschil(vorige, basis)
            if v["instellingen"] or v["apps_nieuw"] or v["apps_weg"] or v["beheerhandelingen"]:
                if oud.get("laatste_melding_dag") != dag_van(klok):
                    try:
                        volgnummer = int(oud.get("wijziging_volgnummer") or 0) + 1
                        if _schrijf_item(acc, wijzigingsmelding(v, vorige, week, klok, volgnummer)):
                            nieuw["basis"] = basis
                            nieuw["laatste_melding_dag"] = dag_van(klok)
                            nieuw["wijziging_volgnummer"] = volgnummer
                    except PrivacyFout:
                        r.nood("Zoom-accountuitvoer geweigerd door de privacygrendel", "claude-code")
                    except Exception:  # noqa: BLE001 - een bordfout mag scannoden en de staat niet verbergen
                        nieuw["wijziging_fouten"] = int(oud.get("wijziging_fouten") or 0) + 1
                        if nieuw["wijziging_fouten"] >= 2:
                            r.nood("Zoom-wijzigingscontrole twee rondes na elkaar niet gelezen", "claude-code")
            else:
                nieuw["basis"] = basis
    # De accountstaat is een kopie: een fout in de scan bewaart geen half bijgewerkte basis.
    nieuw["scannoden"] = scannoden
    staat["account"] = nieuw
    _herhaal_scannoden(r, scannoden)
    r.bron("zoom-account", {"week": week, "vragen": vragen, "volledig": volledig,
                            "delen": {k: "onbekend" if _bekend(d, k) is None else "ok" for k in d}})
    logtekst = f"week {week}; {vragen} vragen; " + \
        ("volledige scan" if volledig else "wijzigingscontrole of gedeeltelijke scan")
    schoon({"naam": "zoom-wacht", "onderwerp": "Zoom-account", "stap": "bevinding", "tekst": logtekst})
    r.agent.log("Zoom-account", "bevinding", logtekst)
    return f"account: {vragen} vragen, {'volledig' if volledig else 'gedeeltelijk'}"


def lees_wijziging(ik, klok, oude_basis):
    l, d, fouten = Lezer(), {}, []
    _deel(l, d, "account", lambda: instellingen(l.vraag("/accounts/me/settings")), "beveiliging", fouten)
    _deel(l, d, "security", lambda: beveiliging(l.vraag("/accounts/me/settings", {"option": "security"})), "beveiliging", fouten)
    _deel(l, d, "locks", lambda: vergrendelingen(l.vraag("/accounts/me/lock_settings")), "beveiliging", fouten)
    _deel(l, d, "user", lambda: instellingen(l.vraag(f"/users/{ik}/settings")), "opnames", fouten)
    maand = (klok - timedelta(days=30)).date().isoformat()
    vandaag = klok.date().isoformat()
    _deel(l, d, "logboek", lambda: beheerlogboek(l.lijst("/report/operationlogs",
                                                           {"from": maand, "to": vandaag, "page_size": 300},
                                                           "operation_logs")), "beveiliging", fouten)
    def app_lijst():
        rows = l.lijst("/marketplace/apps", {"type": "account_added", "page_size": 100}, "apps")
        details = {}
        vorig = oude_basis.get("apps") or {}
        for row in rows:
            appid = row.get("app_id") if isinstance(row, dict) else None
            if not isinstance(appid, str) or not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", appid):
                raise Z.AccountFout(reden="onleesbaar")
            code = _ident(appid)
            if code in vorig:
                # Bestaande apps krijgen hier geen detailvraag: de huidige rechten zijn onbekend.
                details[appid] = {}
            else:
                details[appid] = l.vraag(f"/marketplace/apps/{appid}")
        return apps(rows, details)
    _deel(l, d, "apps", app_lijst, "apps", fouten)
    return d, fouten, l.vragen


def droog(w, klok):
    if not w.get("identiteit_ok") or not Z.leesapp() or Z.leesapp_fout() or Z.leesapp_verboden():
        print("(droog) accountscan onbekend: identiteit of leesapp niet beschikbaar")
        return
    d, fouten, volledig, vragen = lees_week(w["ik"]["id"], str(w["ik"]["pmi"]), klok)
    adv = adviezen(d)
    print(f"(droog) Zoom-account {week_van(klok)}: {vragen} vragen, "
          f"{'volledig' if volledig else 'gedeeltelijk'}, {len(fouten)} onbekende delen")
    slot = (_bekend(d, "locks") or {}).get("wachtkamer")
    print(f"   wachtkamervergrendeling: {slot if slot is not None else 'onbekend'}")
    for a in adv:
        print(f"   {a['code']}: {a['toestand']} ({a['ernst']})")
