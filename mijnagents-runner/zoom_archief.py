#!/usr/bin/env python3
"""De Zoomarchivaris: elke Zoom-cloudopname van Mehdi als bewezen kopie in zijn eigen Dropbox.

Mehdi, 27-10-2026: "ik wil dat alle mijn opnames in mijn eigen dropbox komen zodat ik de data niet verlies". Zoom geeft
20 GB gratis cloudopslag en die zat vol; de wisregel (advies ZA-01 van De Zoomwacht) zet Mehdi pas aan als alles een
bewezen kopie heeft. Deze agent maakt en bewijst die kopie, en wist zelf nooit iets. Ontwerp: driehoeksoverleg
docs/overleg/2026-10-27 Zoomarchief driehoeksoverleg.md (K1 tot K8), hersteld na Codex-controle 1.

Elke ronde (cron elk uur, onder een eigen slot, nooit tijdens de gesprekkenketen):
1. nagaan dat de Dropbox-koppeling nog naar hetzelfde account wijst als bij de eerste ronde (toen moest daar het
   Fathom-archief staan, het teken dat het Mehdi's eigen privé-Dropbox is);
2. de opnamelijst van Mehdi's Zoom lezen met de leesapp (koppelingen/zoom.py, grendels L1 en L5), in vensters van 30
   dagen, en de prullenbak van Zoom in haar twee soorten (een hele gewiste meeting, een los gewist bestand). Elke
   ronde leest alles vanaf EERSTE_DAG, zodat niets buiten een venster valt. Een antwoord zonder lijst is een fout, geen
   lege lijst. Downloadlinks gaan nooit in de staat;
3. elk afgerond bestand dat nog niet bewezen in Dropbox staat, een voor een: eerst de prullenbak (die wist Zoom na 30
   dagen), dan de oudste. Downloaden in brokken naar een tijdelijk bestand op de VM, de grootte vergelijken met wat Zoom
   opgeeft en met Content-Length, de content_hash van Dropbox berekenen. Staat er al iets op het pad: met dezelfde
   grootte en hash is het bewezen, anders een nood en niets overschreven. Staat er niets: uploaden met mode add
   (koppelingen/dropbox_prive.py). Na een onduidelijk antwoord van Dropbox meteen terugkijken wat er staat;
4. bewezen is een bestand pas als Dropbox dezelfde grootte en content_hash geeft; dan pas komt het in de staat
   (mijnagents-data/zoom-archief/staat.json, atomisch geschreven). Het tijdelijke bestand gaat altijd weg, ook bij een
   stopsignaal. Elke ronde kijkt ook alle eerdere bewijzen na tegen wat nu in Dropbox staat;
5. per meeting een opname.json zodra al haar bestanden bewezen zijn;
6. de dekking in mijnagents-data/zoom-archief/dekking.json, elke ronde opnieuw uit wat die ronde zelf zag: ja pas als
   alles wat Zoom heeft al bewezen was voor de ronde begon, niets in verwerking is, elk bewijs klopte, en niets
   verdwenen (tenzij Mehdi dat ene verlies aanvaardde), onvolledig of geblokkeerd is. Daarnaast wisregel_veilig: niets
   ouder dan 30 dagen zonder bewijs. Een ronde die niet alles kon nakijken, trekt ja in. De Zoomwacht leest beide
   voor ZA-01.
Op het bord en in het werkverslag alleen aantallen, GB en datums, nooit een onderwerp, naam of pad. Een normale
achterstand is geen nood; een nood is een blokkade en blijft staan tot ze opgelost is, ook in een ronde die het
bestand niet probeerde: de fouten per bestand staan in de staat.

Met de hand op de VM (het slot weigert een tweede ronde):
    ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/zoom_archief.py            een ronde
    ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/zoom_archief.py --droog    alleen tellen, niets kopiëren
    ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/zoom_archief.py --proef 3  alleen de drie kleinste bestanden
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import dropbox_prive as D  # noqa: E402
import zoom as Z  # noqa: E402

NAAM = "zoom-archief"
TAAK = "opnames naar Dropbox"     # de taak van een echte ronde op het bord; De Zoomwacht koppelt de dekking eraan
ag = bord.Agent(NAAM)
DATA = os.path.expanduser("~/appportal/mijnagents-data/zoom-archief")
DOEL = "/Zoom"
EIGEN_TEKEN = "/Fathom data"      # bij de eerste ronde moet dit in de gekoppelde Dropbox staan (Mehdi's privé-archief)
BRUSSEL = ZoneInfo("Europe/Brussels")
VENSTER = 30                      # dagen per vraag aan Zoom
EERSTE_DAG = date(2018, 1, 1)     # elke ronde leest alles vanaf hier (Codex controle 4); oudste opname: 10-08-2021
BUDGET = 45 * 60                  # na zoveel seconden begint de ronde geen nieuw bestand meer
NA_BUDGET = 10 * 60               # zoveel later breekt ze ook een lopend bestand af (geen bewijs, volgende ronde opnieuw)
KETEN_UTC = ((7, 0), (13, 0), (23, 30))   # de gesprekkenketen (planning/gesprekken.cron)
KETEN_MARGE = 10 * 60             # zoveel seconden voor de keten begint er geen nieuw bestand meer
KETEN_HARD = 5 * 60               # zoveel seconden voor de keten breekt alles af, ook de inventaris
VRIJ_MARGE = 2 * 1024 ** 3        # zoveel schijf moet er naast het bestand vrij blijven op de VM
POGINGEN = 3                      # een tijdelijke fout wordt pas een nood na zoveel rondes op hetzelfde bestand
WISREGEL_DAGEN = 30               # de wisregel van ZA-01: wat ouder is, moet bewezen in Dropbox staan
RECHT = re.compile(r"[a-z_][a-z0-9_]*(?::[a-z0-9_]+){1,3}")
GEMIST_ACTIE = "Zoom-opname zonder kopie als gemist aanvaarden"
# Het groene sein (dekking ja, wisregel_veilig) staat uit tot Codex de dekkingsregel goedkeurt (Codex controle 5): het
# kopiëren mag dan al live, want dat wist en overschrijft nooit iets; zonder sein komt er geen advies om te wissen.
SEIN_AAN = False
AANVAARD = {"goedgekeurd", "uitgevoerd", "overgeslagen"}   # wat de uitvoerder van een goedgekeurd signaal maakt
EXT = {"MP4": "mp4", "M4A": "m4a", "TRANSCRIPT": "vtt", "CC": "vtt", "CHAT": "txt", "TIMELINE": "json", "CSV": "csv",
       "SUMMARY": "json"}
SOORT = {"shared_screen_with_speaker_view": "scherm en spreker", "shared_screen_with_speaker_view(CC)": "scherm en spreker",
         "shared_screen_with_gallery_view": "scherm en galerij", "speaker_view": "spreker", "gallery_view": "galerij",
         "shared_screen": "scherm", "active_speaker": "spreker", "audio_only": "geluid", "audio_transcript": "transcript",
         "chat_file": "chat", "timeline": "tijdlijn", "closed_caption": "ondertitels", "poll": "peiling",
         "host_video": "video host", "thumbnail": "miniatuur", "summary": "samenvatting"}


def nu():
    return datetime.now(timezone.utc)


class Afwijking(RuntimeError):
    """Wat in Dropbox staat of wat Zoom gaf, klopt niet met wat Zoom opgeeft. Altijd een nood, nooit overschrijven."""


class Stop(RuntimeError):
    """De ronde stopt (schijf vol, tijd op, de keten begint); wat bezig was, krijgt geen bewijs en komt later."""


# ------------------------------------------------------------------ staat ---
LEGE_STAAT = {"bestanden": {}, "meetings": {}, "gezien": {}, "verdwenen": {}, "gemist": {}, "fouten": {},
              "voorstellen": {}, "onvolledig": {}, "blokkades": {}, "beschrijvingen": {}, "inventaris": "",
              "dekking": False, "dropbox": ""}


def staat_pad():
    return os.path.join(DATA, "staat.json")


def lees_staat():
    """De staat, of een lege bij de eerste ronde. Een onleesbare staat is een fout, nooit een lege: dan zou alles
    opnieuw gekopieerd lijken en zou de dekking op nul vallen."""
    try:
        with open(staat_pad(), encoding="utf-8") as f:
            s = json.load(f)
    except FileNotFoundError:
        if os.path.exists(os.path.join(DATA, ".in_gebruik")):
            # Codex controle 9, punt 40: na eerdere rondes is een ontbrekende staat een fout; anders vergeet ik wat ik zag
            raise ValueError("staat.json ontbreekt na eerdere rondes") from None
        s = {}
    if not isinstance(s, dict) or not isinstance(s.get("bestanden", {}), dict):
        raise ValueError("staat.json onleesbaar")
    for k, v in LEGE_STAAT.items():
        s.setdefault(k, json.loads(json.dumps(v)))
    return s


def _schrijf_json(pad, inhoud):
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    tmp = f"{pad}.{os.getpid()}.nieuw"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(inhoud, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, pad)


def schrijf_staat(s):
    _schrijf_json(staat_pad(), s)
    teken = os.path.join(DATA, ".in_gebruik")
    if not os.path.exists(teken):
        open(teken, "w").close()


# --------------------------------------------------------------- namen ---
def kort(tekst, n=8):
    """Een korte, vaste vingerafdruk (hex) van een uuid of bestandsid: tegen botsingen in de namen (K2)."""
    return hashlib.sha256((tekst or "").encode()).hexdigest()[:n]


def _veilig(tekst, max_lengte=80):
    """Een naam die Dropbox aanvaardt: geen / \\ < > : " | ? * of stuurtekens, geen punt of spatie op het einde."""
    t = re.sub(r'[\\/<>:"|?*\x00-\x1f\x7f]+', " ", tekst or "")
    t = re.sub(r"\s+", " ", t).strip()[:max_lengte].rstrip(" .")
    return t or "zonder onderwerp"


def brussel(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(BRUSSEL)


def mapnaam(m):
    """/Zoom/<JJJJ-MM-DD HHMM> <onderwerp> <uuid8>, in Brusselse tijd, zoals /Fathom data. De vingerafdruk van de uuid
    houdt twee meetings met hetzelfde uur en onderwerp uit elkaar (K2)."""
    return f"{DOEL}/{brussel(m['start']).strftime('%Y-%m-%d %H%M')} {_veilig(m.get('onderwerp'))} {kort(m['uuid'])}"


def bestandsnaam(f):
    """<HHMMSS> <soort> <id6>.<ext>: het begin van het deel (een opname die stopte en herbegon heeft er meer), wat het
    is, en een vingerafdruk van het bestandsid."""
    tijd = brussel(f["start"]).strftime("%H%M%S") if f.get("start") else "000000"
    soort = SOORT.get(f.get("opnametype") or "") or (f.get("opnametype") or f.get("soort") or "bestand").lower()
    ext = EXT.get(f.get("soort") or "") or re.sub(r"[^a-z0-9]", "", (f.get("extensie") or "").lower()) or "bin"
    return f"{tijd} {_veilig(soort, 40)} {kort(f['id'], 6)}.{ext}"


def pad_van(m, f):
    return f"{mapnaam(m)}/{bestandsnaam(f)}"


# --------------------------------------------------------------- lezen ---
def _samenvoegen(meetings, lijst, prullenbak):
    for m in lijst:
        if not m.get("uuid") or not m.get("start"):
            raise Z.ZoomFout("onvolledig antwoord van Zoom (meeting zonder uuid of start)")
        oud = meetings.setdefault(m["uuid"], {**m, "bestanden": []})
        bekend = {f["id"] for f in oud["bestanden"] if f.get("id")}
        for f in m["bestanden"]:
            if not f.get("id") or f["id"] not in bekend:
                oud["bestanden"].append({**f, "prullenbak": bool(prullenbak)})
                bekend.add(f.get("id"))


def opnamelijst(van, tot, bewaker=None, pauze=0.2):
    """Alle meetings met opnames tussen van en tot (datums) en de hele prullenbak (beide soorten, zonder datum),
    samengevoegd op uuid en bestandsid. Elk bestand draagt of het in de prullenbak zit. Strikt: een pagina zonder lijst
    of een meeting zonder uuid is een fout, nooit een stille lege inventaris."""
    meetings = {}
    eind = tot
    while eind > van:
        if bewaker:
            bewaker()
        begin = max(van, eind - timedelta(days=VENSTER))
        _samenvoegen(meetings, Z.opnames(begin.isoformat(), eind.isoformat(), streng=True, bewaker=bewaker), False)
        time.sleep(pauze)
        eind = begin
    for soort in Z.PRULLENBAK:
        if bewaker:
            bewaker()
        _samenvoegen(meetings, Z.opnames(None, None, prullenbak=soort, streng=True, bewaker=bewaker), True)
    return list(meetings.values())


def mehdi_vastzetten():
    """De gebruiker van de leesapp, alleen als die ZOOM_MEHDI_USER is (zoom_leesapp.py zet die pas na de
    eigenaarscontrole, RZ6-01). Geeft het id, of leeg als het niet bewezen is."""
    vast = Z._lees_sleutel("ZOOM_MEHDI_USER")
    Z.vastzetten(None)
    if not vast:
        return ""
    ik = Z.lees(f"/users/{Z.ingang()}") or {}
    if ik.get("id") != vast:
        return ""
    Z.vastzetten(vast)
    return vast


def dropbox_controle(staat):
    """'' als de koppeling naar het vastgelegde Dropbox-account wijst, anders de reden (Codex 6 en controle 2, 16). Het
    account-id staat in ~/appportal/.env als DROPBOX_PRIVE_ACCOUNT_ID, vastgelegd bij de uitrol na een controle van
    het account (naam en e-mail), nooit door de agent zelf. Daar moet ook het Fathom-archief staan, het teken dat het
    Mehdi's eigen privé-Dropbox is."""
    vast = os.environ.get("DROPBOX_PRIVE_ACCOUNT_ID", "").strip()
    if not vast:
        return "Dropbox-account voor de kopie niet vastgelegd"
    acc = D.account()
    if not acc.get("id"):
        return "Dropbox-account niet te lezen"
    if acc["id"] != vast:
        return "andere Dropbox gekoppeld dan vastgelegd"
    teken = D.metadata(EIGEN_TEKEN)
    if not teken or teken.get("soort") != "folder":
        return "gekoppelde Dropbox is niet Mehdi's privé-archief"
    staat["dropbox"] = acc["id"]
    return ""


# ------------------------------------------------------------ kopiëren ---
def kopieer(f, pad, werkmap, bewaker=None):
    """Een bestand van Zoom naar Dropbox, met bewijs (K3). Geeft de regel voor de staat."""
    if not f.get("grootte"):
        raise Afwijking("Zoom geeft geen grootte op")  # zonder grootte van Zoom is een kort bestand niet te herkennen
    os.makedirs(werkmap, exist_ok=True)
    if shutil.disk_usage(werkmap).free < f["grootte"] + VRIJ_MARGE:
        raise Stop("te weinig vrije schijf op de VM")
    tmp = os.path.join(werkmap, kort(f["id"], 16) + ".deel")
    try:
        n = Z.download_naar(f["id"], tmp, bewaker=bewaker)
        if n != f["grootte"]:
            raise Afwijking("download niet zo groot als Zoom opgeeft")
        h = D.inhoud_hash(tmp)
        m = D.metadata(pad)  # eerst kijken: een vorige ronde kan het er al gezet hebben (verloren antwoord)
        if m is None:
            try:
                m = D.upload_bestand(tmp, pad, bewaker=bewaker)
            except D.Bestaat:
                m = D.metadata(pad)
            except (Stop, D.TijdOp):
                raise
            except Exception:
                # Codex 10: na een onduidelijk antwoord (finish zonder antwoord, verlopen sessie, 401) meteen kijken
                m = D.metadata(pad)
                if not m or m.get("grootte") != n or m.get("content_hash") != h:
                    raise
        if not m or m.get("grootte") != n or m.get("content_hash") != h:
            raise Afwijking("ander bestand op dat pad in Dropbox")
        return {"pad": pad, "grootte": n, "hash": h, "start": f.get("start", ""),
                "ts": nu().isoformat(timespec="seconds")}
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def opname_json(m, bewezen):
    """De beschrijving van een meeting voor naast de bestanden, zonder een enkele link of toegangscode."""
    return {"uuid": m["uuid"], "nummer": m.get("nummer", ""), "onderwerp": m.get("onderwerp", ""), "start": m["start"],
            "duur_min": m.get("duur", 0),
            "bestanden": [{"id": f["id"], "soort": f.get("soort", ""), "opnametype": f.get("opnametype", ""),
                           "start": f.get("start", ""), "einde": f.get("einde", ""),
                           "grootte": bewezen[f["id"]]["grootte"], "content_hash": bewezen[f["id"]]["hash"],
                           "naam": bewezen[f["id"]]["pad"].rsplit("/", 1)[-1]} for f in m["bestanden"]]}


def schrijf_beschrijving(inhoud, pad, werkmap, bewaker=None):
    """Een opname.json naar Dropbox; staat er al een, dan blijft die (nooit overschrijven)."""
    os.makedirs(werkmap, exist_ok=True)
    tmp = os.path.join(werkmap, kort(pad, 16) + ".json.deel")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(inhoud, fh, ensure_ascii=False, indent=1)
    try:
        try:
            D.upload_bestand(tmp, pad, bewaker=bewaker)
        except D.Bestaat:
            pass
    finally:
        os.remove(tmp)


def schrijf_opname_json(m, bewezen, werkmap, bewaker=None):
    schrijf_beschrijving(opname_json(m, bewezen), f"{mapnaam(m)}/opname.json", werkmap, bewaker)


def bewijzen_nakijken(staat, bewaker=None, aanwezig=()):
    """Codex 4 en controle 2, punt 11: klopt elk eerder bewijs nog met wat nu in Dropbox staat? Een bestand dat weg is
    of anders is, gaat uit de bewezen bestanden en terug naar 'gezien': staat het nog in Zoom, dan kopieer ik het
    opnieuw; is het ook uit Zoom weg, dan maakt de volgende volledige inventaris het 'verdwenen', tot Mehdi beslist.
    Zo kan een verlies nooit stil uit de telling vallen. Geeft het aantal dat niet meer klopte."""
    in_dropbox = D.lijst_map(DOEL, bewaker=bewaker) or {}
    weg = 0
    for fid, b in list(staat["bestanden"].items()):
        x = in_dropbox.get((D.basis() + b["pad"]).lower())
        if x is None:
            if bewaker:
                bewaker()
            x = D.metadata(b["pad"])  # Dropbox maakt paden anders klein dan Python: eerst rechtstreeks kijken
        if not x or x.get("grootte") != b["grootte"] or x.get("content_hash") != b["hash"]:
            del staat["bestanden"][fid]
            staat["gezien"][fid] = {"start": b.get("start", ""), "grootte": b.get("grootte", 0), "was_bewezen": True}
            weg += 1
    # Codex controle 9, punt 43: een opname.json die weg is, wordt opnieuw gezet: met de bewaarde inhoud, of zoals de
    # meeting nu in Zoom staat; kan geen van beide, dan blijft het een blokkade
    for uuid, e in list(staat["meetings"].items()):
        map_ = e if isinstance(e, str) else e.get("map", "")
        pad = f"{map_}/opname.json"
        x = in_dropbox.get((D.basis() + pad).lower())
        if x is None:
            if bewaker:
                bewaker()
            x = D.metadata(pad)
        if x:
            continue
        del staat["meetings"][uuid]
        weg += 1
        if isinstance(e, dict) and e.get("inhoud"):
            staat["beschrijvingen"][uuid] = {"inhoud": e["inhoud"], "pad": pad}
            staat["blokkades"][f"opname:{uuid}"] = OPNAME_JSON
        elif uuid not in aanwezig:
            staat["blokkades"][f"opname:{uuid}"] = OPNAME_JSON
    return weg


def problemen(m):
    """Wat aan een meeting niet te kopiëren of niet te bewijzen is: {sleutel: (reden, bestandsid of leeg)}. Een sleutel per geval, ook per
    bestand zonder id, zodat een geval nooit stil opgaat in een meeting die verder goed is (Codex controle 4, punt 18).
    Een bestand dat Zoom nog verwerkt, is geen probleem; het houdt alleen de dekking tegen tot het gekopieerd is."""
    if not m["bestanden"]:
        return {f"meeting:{m['uuid']}": ("meeting zonder opnamebestanden", "")}
    uit, tel = {}, {}
    for f in m["bestanden"]:
        if not f.get("id") or f.get("status") not in ("completed", "processing") or \
                (f.get("status") == "completed" and not f.get("link")):
            kenmerk = json.dumps([f.get("id", ""), f.get("soort", ""), f.get("opnametype", ""), f.get("start", "")])
            # Codex controle 5, punt 25: twee gelijke bestanden zonder id zijn twee gevallen, elk met een eigen besluit
            tel[kenmerk] = tel.get(kenmerk, 0) + 1
            uit[f"bestand:{m['uuid']}:{kort(kenmerk, 16)}:{tel[kenmerk]}"] = (
                "bestand zonder id, downloadlink of bekende status", f.get("id", ""))
    return uit


# ------------------------------------------------------------ Mehdi beslist ---
def _gemist_sleutel(fid, v):
    """Een sleutel per verliesgeval, niet per bestand: komt een aanvaarde opname terug en verdwijnt ze opnieuw, dan
    geldt de oude goedkeuring niet (Codex controle 3, punten 11 en 14)."""
    return kort(f"{fid}|{v.get('sinds', '')}", 16)


def gemist_voorstellen(staat):
    """Een verdwenen opname zonder kopie: Mehdi beslist of ze gemist mag worden (werkwijze, Wat Mehdi beslist). Per
    verliesgeval een signaal op het bord, met alleen datum, uur en grootte; zijn goedkeuring lees ik terug uit het
    bord, alleen voor het geval waarvoor ik het voorstel zette. Kan ik het bord niet lezen, dan zet ik niets (anders
    kunnen er elk uur dubbele voorstellen komen). Geeft de voorstellen om te versturen."""
    try:
        rijen = bord.db_lees("SELECT actie, status FROM voorstel WHERE naam=?", (NAAM,))
    except bord.BordOnbekend:
        return []
    uit = []
    sleutels = {}
    for fid, v in staat["verdwenen"].items():
        sleutels.setdefault(_gemist_sleutel(fid, v), []).append(fid)
    for fid, v in list(staat["verdwenen"].items()):
        sleutel = _gemist_sleutel(fid, v)
        if len(sleutels[sleutel]) > 1:
            continue  # twee gevallen met dezelfde sleutel: geen voorstel, de dekking blijft nee
        actie = f"{GEMIST_ACTIE} ({sleutel})"
        eigen = (staat["voorstellen"].get(sleutel) or {}).get("fid") == fid
        if eigen and any(r["actie"] == actie and r["status"] in AANVAARD for r in rijen):
            staat["gemist"][fid] = {**v, "aanvaard": nu().isoformat(timespec="seconds"), "sleutel": sleutel}
            del staat["verdwenen"][fid]
            continue
        if eigen or any(r["actie"] == actie for r in rijen):
            continue
        wanneer = brussel(v["start"]).strftime("%d-%m-%Y %H:%M") if v.get("start") else "onbekende dag"
        wat = "Een Zoom-meeting zonder bruikbare bestanden" if fid.startswith("meeting:") else "Een Zoom-opname"
        uit.append((sleutel, fid, {
            "actie": actie, "doel": "Beslissen of een Zoom-opname zonder kopie gemist mag worden.",
            "reden": (f"{wat} van {wanneer} ({int(v.get('grootte') or 0) / 1024 ** 2:.0f} MB) verdween uit Zoom en uit "
                      "de prullenbak voor ze bewezen in je Dropbox stond. Goedkeuren: je aanvaardt dat ze gemist is, de "
                      "dekking telt ze dan niet meer. Weigeren: de dekking blijft nee."),
            "parameters": None, "runbook": ""}))
    return uit


# ----------------------------------------------------------------- ronde ---
def keten_draait():
    """Draait de gesprekkenketen nu? True, False, of None als ik het niet kan nagaan (Codex controle 6, punt 30: dat
    is geen "nee"). Alleen kijken, nooit het slot van de keten nemen (dan zou de keten overslaan)."""
    try:
        code = subprocess.run(["pgrep", "-f", "mijnagents-runner/keten.py"], capture_output=True, timeout=10).returncode
    except (OSError, subprocess.SubprocessError):
        return None
    return True if code == 0 else False if code == 1 else None


def tot_keten(klok_utc):
    """Seconden tot de volgende start van de gesprekkenketen (K4)."""
    kandidaten = []
    for dag in (0, 1):
        for uur, minuut in KETEN_UTC:
            t = (klok_utc + timedelta(days=dag)).replace(hour=uur, minute=minuut, second=0, microsecond=0)
            if t > klok_utc:
                kandidaten.append((t - klok_utc).total_seconds())
    return min(kandidaten)


def soort_fout(e):
    """(noodtekst, tijdelijk) voor een fout bij een bestand. De tekst draagt geen url, onderwerp of aantal (N10); een
    recht van Zoom alleen als het de vorm van een recht heeft (Codex 9)."""
    if isinstance(e, Afwijking):
        return f"Zoom-opname niet naar Dropbox gekopieerd: {e}", False
    if isinstance(e, Z.GeenRecht):
        recht = e.scope if RECHT.fullmatch(e.scope or "") else "onbekend recht"
        return f"Zoom-opname niet naar Dropbox gekopieerd: Zoom weigert de download ({recht})", False
    if isinstance(e, Z.ZoomFout):
        return "Zoom-opname niet naar Dropbox gekopieerd: Zoom gaf het bestand niet", True
    return f"Zoom-opname niet naar Dropbox gekopieerd: Dropbox of de VM weigerde ({type(e).__name__})", True


def _utc(iso):
    """Een tijdstip van Zoom als datetime in UTC, of None (Codex controle 6, punt 35: tekst vergelijkt +02:00 verkeerd)."""
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.astimezone(timezone.utc) if d.tzinfo else d.replace(tzinfo=timezone.utc)


def gb(bestanden):
    return sum(int(f.get("grootte") or 0) for f in bestanden) / 1024 ** 3


def _meld_blijvend(r, staat):
    """De noden die uit de staat volgen, elke ronde opnieuw, tot ze opgelost zijn (K5, Codex controle 4, punt 23)."""
    for fout in staat["fouten"].values():
        if not fout.get("tijdelijk") or fout.get("pogingen", 0) >= POGINGEN:
            r.nood(fout["tekst"], wie="claude-code")
    if staat["verdwenen"]:
        r.nood("Zoom-opname verdwenen voor ze in Dropbox stond", wie="mehdi")
    for o in sorted({v["reden"] for v in staat["onvolledig"].values()}):
        r.nood(f"Zoom gaf een onvolledige opname: {o}", wie="claude-code")
    for tekst in sorted(set(staat["blokkades"].values())):
        r.nood(tekst, wie="claude-code")


def intrekken(reden, nu_utc=nu, staat=None):
    """Codex controle 3, punt 5: een ronde die niet alles kon nakijken, trekt een eerdere dekking ja meteen in, in het
    bestand voor De Zoomwacht en in de staat; alleen een nieuwe, volledige ronde geeft weer ja."""
    try:
        if staat is None:
            staat = lees_staat()
        staat["dekking"] = False
        schrijf_staat(staat)
    except (OSError, ValueError):
        pass
    try:
        _schrijf_json(os.path.join(DATA, "dekking.json"), {"ts": nu_utc().isoformat(timespec="seconds"),
                                                           "dekking": False, "wisregel_veilig": False, "reden": reden})
    except OSError:
        pass


SCHIJF_VOL = "Te weinig vrije schijf op de VM voor de kopie van de Zoom-opnames"
OPNAME_JSON = "Beschrijving van een Zoom-opname niet in Dropbox gezet"


def werk(r, droog=False, budget=BUDGET, proef=0, klok=time.monotonic, nu_utc=nu):
    """Een ronde. Elke ronde leest de hele opnamelijst (Codex controle 4, punt 19: een korte ronde ziet niet wat buiten
    haar venster opduikt), kijkt elk bewijs na, kopieert wat ontbreekt, en berekent de dekking uit wat ze zelf zag."""
    def stop(tekst, wie, detail, staat=None):
        if tekst:
            r.nood(tekst, wie=wie)
        if staat is not None:
            _meld_blijvend(r, staat)
        r.noden_onbekend = True  # deze ronde keek niet alles na: het bord sluit niets, wat open stond blijft open
        r.detail = detail
        if not droog:
            intrekken(detail, nu_utc, staat)
        return None

    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        return stop("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", "mehdi",
                    "geen werk gedaan, grenzen ontbreken in de werkwijze")
    if not D.beschikbaar():
        for n in D.nood(wat="de kopie van de Zoom-opnames"):
            r.nood(n["tekst"], wie=n["wie"])
        return stop("", "", "geen privé-Dropbox-token, niets gekopieerd")
    keten = keten_draait()
    if keten is None:
        return stop("Kan niet nagaan of de gesprekkenketen draait", "claude-code",
                    "niets gedaan: de stand van de gesprekkenketen is onbekend")
    if keten:
        # Codex controle 6 en 7 (punten 33 en 36): tijdens de keten geen enkele vraag aan Zoom of Dropbox, en het sein
        # ingetrokken, zodat De Zoomwacht in de keten nooit een oude ja leest.
        return stop("", "", "de gesprekkenketen draait: niets gedaan")
    alleen_tellen = False
    begin = klok()
    hard = min(begin + budget + NA_BUDGET, begin + tot_keten(nu_utc()) - KETEN_HARD)

    def bewaker():
        if klok() > hard:
            raise Stop("tijd op of de gesprekkenketen begint")

    if not droog:
        # Een ronde die hard stopt (stopsignaal, onleesbare staat, een fout buiten stop()) laat zo nooit een oude ja
        # staan: alleen het slot van een geslaagde ronde schrijft ja (aanval op 8075c96, punt 3).
        intrekken("ronde bezig", nu_utc)
    else:
        r.noden_onbekend = True  # een droge ronde kijkt niet alles na: ze sluit geen nood
    staat = lees_staat()
    r.bron("zoom-archief staat", {"bewezen": len(staat["bestanden"]), "inventaris": staat["inventaris"],
                                  "dekking": staat["dekking"]})
    D.GRENS["tot"] = Z.GRENS["tot"] = time.monotonic() + max(0.0, hard - klok())
    try:
        return _ronde(r, staat, droog, budget, proef, klok, nu_utc, begin, hard, bewaker, stop, alleen_tellen)
    except (Stop, D.TijdOp, Z.TijdOp, SystemExit, KeyboardInterrupt):
        raise
    except Exception as e:  # noqa: BLE001
        # Codex controle 6, punt 32: een onverwachte fout gaat met een vaste tekst naar het bord, nooit met haar inhoud
        # (die kan een link dragen). Op de VM alleen waar ze gebeurde.
        plek = traceback.extract_tb(e.__traceback__)[-1]
        print(f"onverwachte fout {type(e).__name__} in {os.path.basename(plek.filename)}:{plek.lineno}", file=sys.stderr)
        raise RuntimeError(f"onverwachte fout ({type(e).__name__})") from None
    finally:
        D.GRENS["tot"] = Z.GRENS["tot"] = None


def _ronde(r, staat, droog, budget, proef, klok, nu_utc, begin, hard, bewaker, stop, alleen_tellen=False):
    vroeg = None
    try:
        reden = dropbox_controle(staat)
        if reden:
            vroeg = (f"Dropbox niet gebruikt: {reden}", "mehdi")
        elif not mehdi_vastzetten():
            vroeg = ("Zoom-gebruiker van Mehdi niet bewezen", "claude-code")
    except Z.ZoomFout:
        vroeg = ("Zoom-opnamelijst niet leesbaar", "claude-code")
    except Exception as e:  # noqa: BLE001  Dropbox onbereikbaar
        vroeg = (f"Dropbox niet bereikbaar ({type(e).__name__})", "claude-code")
    if vroeg:
        return stop(vroeg[0], vroeg[1], "niets gelezen of gekopieerd: " + vroeg[0], staat)

    vandaag = nu_utc().astimezone(BRUSSEL).date()
    try:
        meetings = opnamelijst(EERSTE_DAG, vandaag + timedelta(days=1), bewaker=bewaker)
    except (Stop, D.TijdOp, Z.TijdOp) as e:
        return stop("", "", f"inventaris niet af: {e}", staat)
    except Z.GeenRecht as e:
        recht = e.scope if RECHT.fullmatch(e.scope or "") else "onbekend recht"
        return stop(f"Zoom-opnamelijst niet leesbaar: geen recht {recht}", "mehdi", "opnamelijst niet leesbaar", staat)
    except Z.ZoomFout as e:
        return stop("Zoom-opnamelijst niet leesbaar", "claude-code", f"opnamelijst niet leesbaar ({str(e)[:60]})", staat)

    moment = nu_utc().isoformat(timespec="seconds")
    alle = [(m, f) for m in meetings for f in m["bestanden"]]
    per_id = {f["id"]: (m, f) for m, f in alle if f.get("id")}
    klaar = [f for _, f in per_id.values() if f.get("status") == "completed" and f.get("link")]
    bezig = [f for _, f in per_id.values() if f.get("status") == "processing"]
    uuids = {m["uuid"] for m in meetings}
    # Onvolledig, per geval (Codex controle 4, punt 18): wat ik zie, komt erbij of blijft. Een meeting zonder bestanden
    # die nu wel bestanden heeft, volgt de gewone weg. Elk ander geval dat ik niet meer zie (de meeting of het bestand is
    # weg, of het kreeg een id waarvan ik niet kan bewijzen dat het hetzelfde bestand is) is een verlies tot Mehdi beslist.
    nu_problemen = {}
    for m in meetings:
        for sleutel, (reden, fid) in problemen(m).items():
            nu_problemen[sleutel] = {"reden": reden, "start": m.get("start", ""), "fid": fid}
    for sleutel, o in list(staat["onvolledig"].items()):
        if sleutel in nu_problemen:
            continue
        del staat["onvolledig"][sleutel]
        if sleutel.startswith("meeting:") and sleutel[8:] in uuids:
            continue  # de meeting heeft nu bestanden: die volgen de gewone weg
        if o.get("fid") and o["fid"] in per_id:
            continue  # hetzelfde bestand (zelfde id) is er nog en nu in orde: het volgt de gewone weg
        staat["verdwenen"][sleutel] = {"start": o.get("start", ""), "grootte": 0, "sinds": moment}
    staat["onvolledig"].update(nu_problemen)
    for fid in list(staat["verdwenen"]):  # Codex 8: wat terugkwam, is niet meer verdwenen
        if fid in per_id or fid in staat["bestanden"] or fid in nu_problemen or \
                (fid.startswith("meeting:") and fid[8:] in uuids):
            del staat["verdwenen"][fid]
    for fid in list(staat["gemist"]):  # een aanvaard gemis dat terugkomt, volgt weer de gewone weg
        if fid in per_id:
            del staat["gemist"][fid]
    nagekeken_weg = 0
    if not droog:  # elke ronde: een dekking ja steunt nooit op een bewijs dat niet nagekeken is
        try:
            nagekeken_weg = bewijzen_nakijken(staat, bewaker=bewaker, aanwezig=uuids)
        except (Stop, D.TijdOp, Z.TijdOp) as e:
            return stop("", "", f"nakijken niet af: {e}", staat)
        except Exception as e:  # noqa: BLE001  zonder nakijken geen dekking ja, en de nood blijft tot het lukt
            nagekeken_weg = -1
            staat["blokkades"]["nakijken"] = f"Dropbox niet nagekeken ({type(e).__name__})"
        else:
            staat["blokkades"].pop("nakijken", None)
    for f in klaar:
        b = staat["bestanden"].get(f["id"])
        if b and (not f.get("grootte") or b["grootte"] != f["grootte"]):
            # Codex controle 5, punt 26: Zoom geeft voor dit bestand nu een andere grootte dan de bewezen kopie. Het
            # bewijs vervalt; herkopiëren botst op het bestaande bestand (nooit overschrijven) en blijft een nood.
            del staat["bestanden"][f["id"]]
            staat["fouten"][f["id"]] = {"tekst": "Zoom-opname niet naar Dropbox gekopieerd: Zoom geeft geen of een "
                                                 "andere grootte dan de kopie in Dropbox", "tijdelijk": False,
                                        "pogingen": 1}
    te_doen = [f for f in klaar if f["id"] not in staat["bestanden"]]
    # Een opname die ik zag en die nu uit Zoom (lijst en prullenbak) weg is voor ze bewezen was: verdwenen (K8).
    for fid, oud in list(staat["gezien"].items()):
        if fid not in per_id and fid not in staat["bestanden"]:
            staat["verdwenen"][fid] = {**oud, "sinds": moment}
            del staat["gezien"][fid]
            staat["fouten"].pop(fid, None)
    for f in te_doen + bezig:  # Codex controle 4, punt 20: elk onbewezen bestand, ook in verwerking, wordt bijgehouden
        staat["gezien"][f["id"]] = {"start": f.get("start", ""), "grootte": f.get("grootte", 0)}
    volgorde = sorted(te_doen, key=lambda f: (not f.get("prullenbak"), _utc(f.get("start")) or datetime.min.replace(
        tzinfo=timezone.utc)))
    if proef:
        volgorde = sorted(te_doen, key=lambda f: int(f.get("grootte") or 0))[:proef]

    gedaan, gestopt = [], "de gesprekkenketen draait: alleen geteld en nagekeken" if alleen_tellen else ""
    werkmap = os.path.join(DATA, "werk")
    if not droog and not alleen_tellen:
        if not te_doen:
            staat["blokkades"].pop("schijf", None)  # niets meer te kopiëren: de schijf houdt niets tegen
        for f in volgorde:
            if klok() - begin > budget:
                gestopt = "tijdsbudget op"
                break
            if tot_keten(nu_utc()) < KETEN_MARGE or keten_draait() is not False:
                gestopt = "de gesprekkenketen begint"
                break
            m, _ = per_id[f["id"]]
            try:
                staat["bestanden"][f["id"]] = kopieer(f, pad_van(m, f), werkmap, bewaker=bewaker)
                for k in ("gezien", "fouten"):
                    staat[k].pop(f["id"], None)
                staat["blokkades"].pop("schijf", None)
                gedaan.append(f)
                schrijf_staat(staat)
            except (Stop, D.TijdOp, Z.TijdOp) as e:
                gestopt = str(e)
                if "schijf" in gestopt:
                    staat["blokkades"]["schijf"] = SCHIJF_VOL
                break
            except Exception as e:  # noqa: BLE001
                tekst, tijdelijk = soort_fout(e)
                oud = staat["fouten"].get(f["id"], {})
                if oud and not oud.get("tijdelijk") and tijdelijk:
                    oud["pogingen"] = oud.get("pogingen", 0) + 1  # de blijvende fout blijft staan en gemeld
                else:
                    zelfde = oud.get("tekst") == tekst
                    staat["fouten"][f["id"]] = {"tekst": tekst, "tijdelijk": tijdelijk,
                                                "pogingen": (oud.get("pogingen", 0) if zelfde else 0) + 1}
                if "HTTP 429" in str(e):
                    gestopt = "Zoom vraagt rust"
                    break
        for m in meetings:
            if gestopt:
                break
            ids = [f.get("id") for f in m["bestanden"]]
            if (ids and all(ids) and m["uuid"] not in staat["meetings"]
                    and all(f.get("status") == "completed" for f in m["bestanden"])
                    and all(i in staat["bestanden"] for i in ids)):
                inhoud, pad = opname_json(m, staat["bestanden"]), f"{mapnaam(m)}/opname.json"
                try:
                    bewaker()
                    schrijf_beschrijving(inhoud, pad, werkmap, bewaker=bewaker)
                    staat["meetings"][m["uuid"]] = {"map": pad.rsplit("/", 1)[0], "inhoud": inhoud}
                    staat["blokkades"].pop(f"opname:{m['uuid']}", None)
                    staat["beschrijvingen"].pop(m["uuid"], None)
                except (Stop, D.TijdOp) as e:
                    gestopt = str(e)
                except Exception:  # noqa: BLE001  blijft gemeld tot het lukt (Codex controle 4, punt 23)
                    staat["blokkades"][f"opname:{m['uuid']}"] = OPNAME_JSON
                    staat["beschrijvingen"][m["uuid"]] = {"inhoud": inhoud, "pad": pad}
        # Codex controle 5, punt 28: een beschrijving die niet lukte, probeer ik opnieuw met de bewaarde gegevens, ook als
        # de meeting intussen uit Zoom weg is; de nood blijft tot het lukt
        for uuid, b in list(staat["beschrijvingen"].items()):
            if gestopt or uuid in uuids:
                continue  # een meeting die nog in Zoom staat, schrijft de gewone stap hierboven opnieuw
            try:
                bewaker()
                schrijf_beschrijving(b["inhoud"], b["pad"], werkmap, bewaker=bewaker)
                staat["meetings"][uuid] = {"map": b["pad"].rsplit("/", 1)[0], "inhoud": b["inhoud"]}
                staat["blokkades"].pop(f"opname:{uuid}", None)
                del staat["beschrijvingen"][uuid]
            except (Stop, D.TijdOp) as e:
                gestopt = str(e)
            except Exception:  # noqa: BLE001
                pass
        for sleutel, fid, v in gemist_voorstellen(staat):
            # Codex controle 2, punt 13: hartslag slikt een bordfout in; pas als het bord het voorstel teruggeeft,
            # geldt het als verstuurd, anders probeert de volgende ronde het opnieuw
            ag.hartslag("actief", taak="Zoom-opname zonder kopie", voorstel=v)
            try:
                if bord.db_lees("SELECT id FROM voorstel WHERE naam=? AND actie=?", (NAAM, v["actie"])):
                    staat["voorstellen"][sleutel] = {"fid": fid, "ts": moment}
            except bord.BordOnbekend:
                pass

    rest = [f for f in klaar if f["id"] not in staat["bestanden"]]
    onbewezen = rest + bezig
    for fid in list(staat["fouten"]):
        if fid in staat["bestanden"] or fid not in per_id:
            del staat["fouten"][fid]
    _meld_blijvend(r, staat)
    grens = nu_utc() - timedelta(days=WISREGEL_DAGEN)
    # een onbekend tijdstip telt als oud: dan weet ik niet dat de wisregel het spaart
    oud_open = [f for f in onbewezen if (_utc(f.get("start")) or grens) <= grens]
    binnen = klok() <= hard
    gaaf = (not droog and nagekeken_weg == 0 and not staat["verdwenen"] and not staat["onvolledig"]
            and not staat["blokkades"] and binnen)
    # Dekking ja (K6, Codex controle 3 en 4): uit wat deze ronde zelf zag en nakeek. Alles wat Zoom nu heeft, was al
    # bewezen voor de ronde begon (dus een tweede inventaris), niets wordt nog verwerkt, elk bewijs klopte, niets is
    # verdwenen, onvolledig of geblokkeerd, en de ronde bleef binnen haar tijd.
    dekking = gaaf and not te_doen and not bezig
    # Veilig voor de wisregel: niets ouder dan WISREGEL_DAGEN zonder bewijs, ook niet in verwerking.
    veilig = gaaf and not oud_open
    if not SEIN_AAN:
        dekking = veilig = False
    if (dekking or veilig) and not droog:
        # Codex controle 7, punt 37: een opname kan opduiken in een venster dat al gelezen was. Voor groen lees ik de lijst
        # daarom opnieuw; wat er dan bij is en niet bewezen, of in verwerking, of onvolledig, maakt het nee.
        try:
            tweede = opnamelijst(EERSTE_DAG, vandaag + timedelta(days=1), bewaker=bewaker)
        except Exception:  # noqa: BLE001  geen tweede lezing, geen groen
            tweede = None
        if tweede is None:
            dekking = veilig = False
        else:
            # Codex controle 8, punt 39: een bekend id telt alleen als bewezen als Zoom nu dezelfde, niet-nul grootte
            # opgeeft als de kopie in Dropbox, en het bestand afgerond is
            bewezen = staat["bestanden"]
            nieuw_open = [f for m in tweede for f in m["bestanden"]
                          if not (f.get("id") in bewezen and f.get("status") == "completed" and f.get("grootte")
                                  and bewezen[f["id"]]["grootte"] == f["grootte"])]
            if any(problemen(m) for m in tweede) or nieuw_open:
                dekking = False
                if any(problemen(m) for m in tweede) or any((_utc(f.get("start")) or grens) <= grens for f in nieuw_open):
                    veilig = False
        binnen = klok() <= hard
        dekking, veilig = dekking and binnen, veilig and binnen
    if not droog:
        staat["dekking"] = dekking
        staat["inventaris"] = moment
        schrijf_staat(staat)
        _schrijf_json(os.path.join(DATA, "dekking.json"), {
            "ts": moment, "dekking": dekking, "wisregel_veilig": veilig, "bestanden": len(klaar),
            "bewezen": len(klaar) - len(rest), "open": len(rest), "in_verwerking": len(bezig),
            "open_ouder_dan_30_dagen": len(oud_open), "verdwenen": len(staat["verdwenen"]),
            "gemist_aanvaard": len(staat["gemist"]), "onvolledig": len(staat["onvolledig"]),
            "blokkades": len(staat["blokkades"])})
    else:
        dekking = veilig = False
    r.detail = (f"{'droog: ' if droog else ''}{'proef: ' if proef else ''}{len(klaar)} bestanden ({gb(klaar):.1f} GB) "
                f"in Zoom; {len(gedaan)} gekopieerd ({gb(gedaan):.1f} GB); nog {len(rest)} ({gb(rest):.1f} GB); ouder "
                f"dan {WISREGEL_DAGEN} dagen allemaal in Dropbox: {'ja' if not oud_open else 'nee'}; dekking: "
                f"{'ja' if dekking else 'nee'}"
                + (f"; verdwenen {len(staat['verdwenen'])}" if staat["verdwenen"] else "")
                + (f"; bewijs niet meer in Dropbox {nagekeken_weg}" if nagekeken_weg > 0 else "")
                + (f"; fouten {len(staat['fouten'])}" if staat["fouten"] else "") + (f"; gestopt: {gestopt}" if gestopt else ""))
    ag.log("archief", "ronde", r.detail)
    return {"klaar": len(klaar), "gedaan": len(gedaan), "rest": len(rest), "oud_open": len(oud_open),
            "fouten": dict(staat["fouten"]), "gestopt": gestopt, "dekking": dekking, "veilig": veilig, "volledig": True}


def _stopsignaal(nummer, _frame):
    raise SystemExit(128 + nummer)  # zodat finally het tijdelijke bestand weghaalt en de ronde "fout" meldt (N11)


def main(argv=None):
    p = argparse.ArgumentParser(description="De Zoomarchivaris: Zoom-opnames als bewezen kopie in Mehdi's Dropbox")
    p.add_argument("--droog", action="store_true", help="alleen tellen, niets kopiëren")
    p.add_argument("--budget", type=int, default=BUDGET, help="seconden voor er geen nieuw bestand meer begint")
    p.add_argument("--proef", type=int, default=0, help="alleen de N kleinste bestanden (de proefronde, K8)")
    a = p.parse_args(argv)
    os.makedirs(DATA, exist_ok=True)
    slot = open(os.path.join(DATA, ".slot"), "w")
    try:
        fcntl.flock(slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("een andere ronde van De Zoomarchivaris loopt nog; niets gedaan")
        return 0
    signal.signal(signal.SIGTERM, _stopsignaal)
    werkmap = os.path.join(DATA, "werk")
    if os.path.isdir(werkmap):
        for naam in os.listdir(werkmap):  # resten van een ronde die hard stopte
            if naam.endswith(".deel"):
                os.remove(os.path.join(werkmap, naam))
    taak = TAAK + (" (droog)" if a.droog else "") + (" (proef)" if a.proef else "")
    with ag.ronde(taak) as r:
        werk(r, droog=a.droog, budget=a.budget, proef=a.proef)
    return 0


if __name__ == "__main__":
    sys.exit(main())
