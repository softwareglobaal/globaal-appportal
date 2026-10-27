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
   dagen, en de prullenbak van Zoom in haar twee soorten (een hele gewiste meeting, een los gewist bestand). Een
   volledige inventaris (vanaf EERSTE_DAG) een keer per Brusselse dag en na elke ronde die iets kopieerde; anders de
   laatste KORT dagen. Een antwoord zonder lijst is een fout, geen lege lijst. Downloadlinks gaan nooit in de staat;
3. elk afgerond bestand dat nog niet bewezen in Dropbox staat, een voor een: eerst de prullenbak (die wist Zoom na 30
   dagen), dan de oudste. Downloaden in brokken naar een tijdelijk bestand op de VM, de grootte vergelijken met wat Zoom
   opgeeft en met Content-Length, de content_hash van Dropbox berekenen. Staat er al iets op het pad: met dezelfde
   grootte en hash is het bewezen, anders een nood en niets overschreven. Staat er niets: uploaden met mode add
   (koppelingen/dropbox_prive.py). Na een onduidelijk antwoord van Dropbox meteen terugkijken wat er staat;
4. bewezen is een bestand pas als Dropbox dezelfde grootte en content_hash geeft; dan pas komt het in de staat
   (mijnagents-data/zoom-archief/staat.json, atomisch geschreven). Het tijdelijke bestand gaat altijd weg, ook bij een
   stopsignaal. Een volledige inventaris kijkt ook alle eerdere bewijzen na tegen wat nu in Dropbox staat;
5. per meeting een opname.json zodra al haar bestanden bewezen zijn;
6. de dekking in mijnagents-data/zoom-archief/dekking.json: ja pas als een volledige inventaris niets meer te
   kopiëren vond, elk eerder bewijs nog klopt, en geen opname verdween voor ze bewezen was (tenzij Mehdi die als gemist
   aanvaardde). Een korte ronde houdt dat oordeel, tenzij ze iets nieuws te kopiëren vindt. De Zoomwacht leest het
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
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import dropbox_prive as D  # noqa: E402
import zoom as Z  # noqa: E402

NAAM = "zoom-archief"
ag = bord.Agent(NAAM)
DATA = os.path.expanduser("~/appportal/mijnagents-data/zoom-archief")
DOEL = "/Zoom"
EIGEN_TEKEN = "/Fathom data"      # bij de eerste ronde moet dit in de gekoppelde Dropbox staan (Mehdi's privé-archief)
BRUSSEL = ZoneInfo("Europe/Brussels")
VENSTER = 30                      # dagen per vraag aan Zoom
KORT = 90                         # dagen die een gewone ronde leest
EERSTE_DAG = date(2018, 1, 1)     # de volledige inventaris begint hier; Mehdi's oudste opname is van 10-08-2021
BUDGET = 45 * 60                  # na zoveel seconden begint de ronde geen nieuw bestand meer
NA_BUDGET = 10 * 60               # zoveel later breekt ze ook een lopend bestand af (geen bewijs, volgende ronde opnieuw)
KETEN_UTC = ((7, 0), (13, 0), (23, 30))   # de gesprekkenketen (planning/gesprekken.cron)
KETEN_MARGE = 10 * 60             # zoveel seconden voor de keten begint er geen nieuw bestand meer
KETEN_HARD = 2 * 60               # zoveel seconden voor de keten breekt alles af, ook de inventaris
VRIJ_MARGE = 2 * 1024 ** 3        # zoveel schijf moet er naast het bestand vrij blijven op de VM
POGINGEN = 3                      # een tijdelijke fout wordt pas een nood na zoveel rondes op hetzelfde bestand
WISREGEL_DAGEN = 30               # de wisregel van ZA-01: wat ouder is, moet bewezen in Dropbox staan
RECHT = re.compile(r"[a-z_][a-z0-9_]*(?::[a-z0-9_]+){1,3}")
GEMIST_ACTIE = "Zoom-opname zonder kopie als gemist aanvaarden"
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
              "voorstellen": {}, "inventaris": "", "gekopieerd": 0, "dekking": False, "dropbox": ""}


def staat_pad():
    return os.path.join(DATA, "staat.json")


def lees_staat():
    """De staat, of een lege bij de eerste ronde. Een onleesbare staat is een fout, nooit een lege: dan zou alles
    opnieuw gekopieerd lijken en zou de dekking op nul vallen."""
    try:
        with open(staat_pad(), encoding="utf-8") as f:
            s = json.load(f)
    except FileNotFoundError:
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
        _samenvoegen(meetings, Z.opnames(begin.isoformat(), eind.isoformat(), streng=True), False)
        time.sleep(pauze)
        eind = begin
    for soort in Z.PRULLENBAK:
        if bewaker:
            bewaker()
        _samenvoegen(meetings, Z.opnames(None, None, prullenbak=soort, streng=True), True)
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
    """'' als de koppeling naar hetzelfde Dropbox-account wijst als bij de eerste ronde, anders de reden. Bij de
    eerste ronde moet daar het Fathom-archief staan: het teken dat het Mehdi's eigen privé-Dropbox is (Codex 6)."""
    acc = D.account()
    if not acc.get("id"):
        return "Dropbox-account niet te lezen"
    if staat["dropbox"]:
        return "" if staat["dropbox"] == acc["id"] else "andere Dropbox gekoppeld dan bij de eerste ronde"
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
            except Stop:
                raise
            except Exception:
                # Codex 10: na een onduidelijk antwoord (finish zonder antwoord, verlopen sessie, 401) meteen kijken
                m = D.metadata(pad)
                if not m or m.get("grootte") != n or m.get("content_hash") != h:
                    raise
        if not m or m.get("grootte") != n or m.get("content_hash") != h:
            raise Afwijking("ander bestand op dat pad in Dropbox")
        return {"pad": pad, "grootte": n, "hash": h, "ts": nu().isoformat(timespec="seconds")}
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


def schrijf_opname_json(m, bewezen, werkmap):
    os.makedirs(werkmap, exist_ok=True)
    tmp = os.path.join(werkmap, kort(m["uuid"], 16) + ".json.deel")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(opname_json(m, bewezen), fh, ensure_ascii=False, indent=1)
    try:
        try:
            D.upload_bestand(tmp, f"{mapnaam(m)}/opname.json")
        except D.Bestaat:
            pass  # er staat er al een: een opname.json overschrijven we nooit
    finally:
        os.remove(tmp)


def bewijzen_nakijken(staat):
    """Codex 4: klopt elk eerder bewijs nog met wat nu in Dropbox staat? Een bestand dat weg is of anders is, gaat uit de
    bewezen bestanden (en komt in de volgende ronden opnieuw, of als afwijking). Geeft het aantal dat niet meer klopte."""
    in_dropbox = D.lijst_map(DOEL) or {}
    weg = 0
    for fid, b in list(staat["bestanden"].items()):
        x = in_dropbox.get((D.basis() + b["pad"]).lower())
        if x is None:
            x = D.metadata(b["pad"])  # Dropbox maakt paden anders klein dan Python: eerst rechtstreeks kijken
        if not x or x.get("grootte") != b["grootte"] or x.get("content_hash") != b["hash"]:
            del staat["bestanden"][fid]
            weg += 1
    return weg


# ------------------------------------------------------------ Mehdi beslist ---
def gemist_voorstellen(staat):
    """Een verdwenen opname zonder kopie: Mehdi beslist of ze gemist mag worden (werkwijze, Wat Mehdi beslist). Per
    opname een signaal op het bord, met alleen datum, uur en grootte; zijn goedkeuring lees ik terug uit het bord. Geeft
    de voorstellen om te versturen."""
    try:
        rijen = bord.db_lees("SELECT actie, status FROM voorstel WHERE naam=?", (NAAM,))
    except bord.BordOnbekend:
        rijen = None
    uit = []
    for fid, v in list(staat["verdwenen"].items()):
        sleutel = kort(fid)
        actie = f"{GEMIST_ACTIE} ({sleutel})"
        if rijen is not None and any(r["actie"] == actie and r["status"] in AANVAARD for r in rijen):
            staat["gemist"][fid] = {**v, "aanvaard": nu().isoformat(timespec="seconds")}
            del staat["verdwenen"][fid]
            continue
        if sleutel in staat["voorstellen"] or (rijen is not None and any(r["actie"] == actie for r in rijen)):
            continue
        wanneer = brussel(v["start"]).strftime("%d-%m-%Y %H:%M") if v.get("start") else "onbekende dag"
        uit.append((sleutel, {"actie": actie, "doel": "Beslissen of een Zoom-opname zonder kopie gemist mag worden.",
                              "reden": (f"Een Zoom-opname van {wanneer} ({int(v.get('grootte') or 0) / 1024 ** 2:.0f} MB) "
                                        "verdween uit Zoom en uit de prullenbak voor ze bewezen in je Dropbox stond. "
                                        "Goedkeuren: je aanvaardt dat ze gemist is, de dekking telt ze dan niet meer. "
                                        "Weigeren: de dekking blijft nee."),
                              "parameters": None, "runbook": ""}))
    return uit


# ----------------------------------------------------------------- ronde ---
def keten_draait():
    """Draait de gesprekkenketen nu? Alleen kijken, nooit het slot van de keten nemen (dan zou de keten overslaan)."""
    try:
        return subprocess.run(["pgrep", "-f", "mijnagents-runner/keten.py"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


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


def gb(bestanden):
    return sum(int(f.get("grootte") or 0) for f in bestanden) / 1024 ** 3


def _meld_blijvend(r, staat):
    """De noden die uit de staat volgen, elke ronde opnieuw, ook als deze ronde het bestand niet probeerde of niet
    las (een korte ronde leest alleen de laatste KORT dagen) (K5)."""
    for fout in staat["fouten"].values():
        if not fout.get("tijdelijk") or fout.get("pogingen", 0) >= POGINGEN:
            r.nood(fout["tekst"], wie="claude-code")
    if staat["verdwenen"]:
        r.nood("Zoom-opname verdwenen voor ze in Dropbox stond", wie="mehdi")


def werk(r, droog=False, budget=BUDGET, proef=0, klok=time.monotonic, nu_utc=nu):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.noden_onbekend = True
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return None
    if not D.beschikbaar():
        for n in D.nood(wat="de kopie van de Zoom-opnames"):
            r.nood(n["tekst"], wie=n["wie"])
        r.noden_onbekend = True
        r.detail = "geen privé-Dropbox-token, niets gekopieerd"
        return None
    if keten_draait():
        r.noden_onbekend = True  # deze ronde keek niets na: de open noden blijven staan
        r.detail = "de gesprekkenketen draait, deze ronde overgeslagen"
        return None
    begin = klok()
    hard = min(begin + budget + NA_BUDGET, begin + tot_keten(nu_utc()) - KETEN_HARD)

    def bewaker():
        if klok() > hard:
            raise Stop("tijd op of de gesprekkenketen begint")

    staat = lees_staat()
    r.bron("zoom-archief staat", {"bewezen": len(staat["bestanden"]), "inventaris": staat["inventaris"],
                                  "dekking": staat["dekking"]})
    # Stopt de ronde hierna vroeg, dan zet ze noden_onbekend: het bord sluit dan niets, wat open stond blijft open.
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
        r.nood(vroeg[0], wie=vroeg[1])
        r.noden_onbekend = True
        r.detail = "niets gelezen of gekopieerd: " + vroeg[0]
        return None

    vandaag = nu_utc().astimezone(BRUSSEL).date()
    volledig = staat["inventaris"] != vandaag.isoformat() or staat["gekopieerd"] > 0
    try:
        meetings = opnamelijst(EERSTE_DAG if volledig else vandaag - timedelta(days=KORT), vandaag + timedelta(days=1),
                               bewaker=bewaker)
    except Stop as e:
        r.noden_onbekend = True
        r.detail = f"inventaris niet af: {e}"
        return None
    except Z.GeenRecht as e:
        recht = e.scope if RECHT.fullmatch(e.scope or "") else "onbekend recht"
        r.nood(f"Zoom-opnamelijst niet leesbaar: geen recht {recht}", wie="mehdi")
        r.noden_onbekend = True
        r.detail = "opnamelijst niet leesbaar"
        return None
    except Z.ZoomFout as e:
        r.nood("Zoom-opnamelijst niet leesbaar", wie="claude-code")
        r.noden_onbekend = True
        r.detail = f"opnamelijst niet leesbaar ({str(e)[:60]})"
        return None

    alle = [(m, f) for m in meetings for f in m["bestanden"]]
    zonder_id = [f for _, f in alle if f.get("status") == "completed" and (not f.get("id") or not f.get("link"))]
    per_id = {f["id"]: (m, f) for m, f in alle if f.get("id")}
    klaar = [f for _, f in per_id.values() if f.get("status") == "completed" and f.get("link")]
    for fid in list(staat["verdwenen"]):  # Codex 8: wat terugkwam, is niet meer verdwenen
        if fid in per_id or fid in staat["bestanden"]:
            del staat["verdwenen"][fid]
    nagekeken_weg = 0
    if volledig and not droog:
        try:
            nagekeken_weg = bewijzen_nakijken(staat)
        except Exception as e:  # noqa: BLE001  zonder nakijken geen dekking ja
            nagekeken_weg = -1
            r.nood(f"Dropbox niet nagekeken ({type(e).__name__})", wie="claude-code")
    te_doen = [f for f in klaar if f["id"] not in staat["bestanden"]]
    if volledig:
        # Een opname die ik zag en die nu uit Zoom (lijst en prullenbak) weg is voor ze bewezen was: verdwenen (K8).
        for fid, oud in list(staat["gezien"].items()):
            if fid not in per_id and fid not in staat["bestanden"]:
                staat["verdwenen"][fid] = {**oud, "sinds": nu_utc().isoformat(timespec="seconds")}
                del staat["gezien"][fid]
                staat["fouten"].pop(fid, None)
    for f in te_doen:
        staat["gezien"][f["id"]] = {"start": f.get("start", ""), "grootte": f.get("grootte", 0)}
    volgorde = sorted(te_doen, key=lambda f: (not f.get("prullenbak"), f.get("start") or ""))
    if proef:
        volgorde = sorted(te_doen, key=lambda f: int(f.get("grootte") or 0))[:proef]

    gedaan, gestopt = [], ""
    werkmap = os.path.join(DATA, "werk")
    if not droog:
        for f in volgorde:
            if klok() - begin > budget:
                gestopt = "tijdsbudget op"
                break
            if tot_keten(nu_utc()) < KETEN_MARGE or keten_draait():
                gestopt = "de gesprekkenketen begint"
                break
            m, _ = per_id[f["id"]]
            try:
                staat["bestanden"][f["id"]] = kopieer(f, pad_van(m, f), werkmap, bewaker=bewaker)
                for k in ("gezien", "fouten"):
                    staat[k].pop(f["id"], None)
                gedaan.append(f)
                schrijf_staat(staat)
            except Stop as e:
                gestopt = str(e)
                if "schijf" in gestopt:
                    r.nood("Te weinig vrije schijf op de VM voor de kopie van de Zoom-opnames", wie="claude-code")
                break
            except Exception as e:  # noqa: BLE001
                tekst, tijdelijk = soort_fout(e)
                oud = staat["fouten"].get(f["id"], {})
                staat["fouten"][f["id"]] = {"tekst": tekst, "tijdelijk": tijdelijk,
                                            "pogingen": oud.get("pogingen", 0) + 1}
                if "HTTP 429" in str(e):
                    gestopt = "Zoom vraagt rust"
                    break
        for m in meetings:
            ids = [f.get("id") for f in m["bestanden"]]
            if (ids and all(ids) and m["uuid"] not in staat["meetings"]
                    and all(f.get("status") == "completed" for f in m["bestanden"])
                    and all(i in staat["bestanden"] for i in ids)):
                try:
                    schrijf_opname_json(m, staat["bestanden"], werkmap)
                    staat["meetings"][m["uuid"]] = staat["bestanden"][ids[0]]["pad"].rsplit("/", 1)[0]
                except Exception as e:  # noqa: BLE001
                    r.nood(soort_fout(e)[0], wie="claude-code")
        for v in gemist_voorstellen(staat):
            try:
                ag.hartslag("actief", taak="Zoom-opname zonder kopie", voorstel=v[1])
                staat["voorstellen"][v[0]] = nu_utc().isoformat(timespec="seconds")
            except Exception as e:  # noqa: BLE001
                print(f"voorstel niet verstuurd: {type(e).__name__}", file=sys.stderr)

    rest = [f for f in klaar if f["id"] not in staat["bestanden"]]
    for fid in list(staat["fouten"]):
        # een fout geldt niet meer als het bestand bewezen is, of als een volledige inventaris het niet meer zag; een
        # korte ronde die het bestand niet las, weet dat niet en laat de fout staan
        if fid in staat["bestanden"] or (volledig and fid not in per_id):
            del staat["fouten"][fid]
    _meld_blijvend(r, staat)
    if zonder_id:
        r.nood("Zoom gaf een opnamebestand zonder id of downloadlink", wie="claude-code")
    grens = (nu_utc() - timedelta(days=WISREGEL_DAGEN)).strftime("%Y-%m-%dT%H:%M:%SZ")
    oud_open = [f for f in rest if (f.get("start") or "") < grens]
    blokkade = bool(staat["verdwenen"] or zonder_id or nagekeken_weg)
    # Dekking ja: een volledige inventaris vond niets meer te kopiëren, elk bewijs klopte nog, niets verdween (K6). Een
    # korte ronde houdt het oordeel van de laatste volledige, tenzij ze nieuw werk of een blokkade vindt.
    if volledig:
        dekking = not te_doen and not blokkade
    else:
        dekking = staat["dekking"] and not te_doen and not blokkade
    if not droog:
        staat["dekking"] = dekking
        if volledig:
            staat["inventaris"] = vandaag.isoformat()
            staat["gekopieerd"] = len(gedaan)
        else:
            staat["gekopieerd"] += len(gedaan)
        schrijf_staat(staat)
        _schrijf_json(os.path.join(DATA, "dekking.json"), {
            "ts": nu_utc().isoformat(timespec="seconds"), "dekking": dekking, "inventaris": staat["inventaris"],
            "volledig_gelezen": volledig, "bestanden": len(klaar), "bewezen": len(klaar) - len(rest), "open": len(rest),
            "open_ouder_dan_30_dagen": len(oud_open), "verdwenen": len(staat["verdwenen"]),
            "gemist_aanvaard": len(staat["gemist"]), "zonder_id": len(zonder_id)})
    else:
        dekking = False
    r.detail = (f"{'droog: ' if droog else ''}{'proef: ' if proef else ''}{len(klaar)} bestanden ({gb(klaar):.1f} GB) "
                f"in Zoom {'(alles gelezen)' if volledig else f'(laatste {KORT} dagen)'}; {len(gedaan)} gekopieerd "
                f"({gb(gedaan):.1f} GB); nog {len(rest)} ({gb(rest):.1f} GB); ouder dan {WISREGEL_DAGEN} dagen allemaal "
                f"in Dropbox: {'ja' if not oud_open else 'nee'}; dekking: {'ja' if dekking else 'nee'}"
                + (f"; verdwenen {len(staat['verdwenen'])}" if staat["verdwenen"] else "")
                + (f"; bewijs niet meer in Dropbox {nagekeken_weg}" if nagekeken_weg > 0 else "")
                + (f"; fouten {len(staat['fouten'])}" if staat["fouten"] else "") + (f"; gestopt: {gestopt}" if gestopt else ""))
    ag.log("archief", "ronde", r.detail)
    return {"klaar": len(klaar), "gedaan": len(gedaan), "rest": len(rest), "oud_open": len(oud_open),
            "fouten": dict(staat["fouten"]), "gestopt": gestopt, "dekking": dekking, "volledig": volledig}


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
    taak = "opnames naar Dropbox" + (" (droog)" if a.droog else "") + (" (proef)" if a.proef else "")
    with ag.ronde(taak) as r:
        werk(r, droog=a.droog, budget=a.budget, proef=a.proef)
    return 0


if __name__ == "__main__":
    sys.exit(main())
