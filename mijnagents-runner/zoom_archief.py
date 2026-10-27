#!/usr/bin/env python3
"""De Zoomarchivaris: elke Zoom-cloudopname van Mehdi als bewezen kopie in zijn eigen Dropbox.

Mehdi, 27-10-2026: "ik wil dat alle mijn opnames in mijn eigen dropbox komen zodat ik de data niet verlies". Zoom geeft
20 GB gratis cloudopslag en die zat vol; de wisregel (advies ZA-01 van De Zoomwacht) zet Mehdi pas aan als alles een
bewezen kopie heeft. Deze agent maakt en bewijst die kopie, en wist zelf nooit iets. Ontwerp: driehoeksoverleg
docs/overleg/2026-10-27 Zoomarchief driehoeksoverleg.md (K1 tot K8).

Elke ronde (cron elk uur, onder een eigen slot, nooit tijdens de gesprekkenketen):
1. de opnamelijst van Mehdi's Zoom lezen met de leesapp (koppelingen/zoom.py, grendels L1 en L5), in vensters van 30
   dagen, met de prullenbak van Zoom erbij. Een volledige inventaris (vanaf EERSTE_DAG) een keer per Brusselse dag en
   na elke ronde die iets kopieerde; anders de laatste KORT dagen. Downloadlinks gaan nooit in de staat;
2. elk afgerond bestand dat nog niet bewezen in Dropbox staat, een voor een: eerst de prullenbak (die wist Zoom na 30
   dagen), dan de oudste. Downloaden in brokken naar een tijdelijk bestand op de VM, de grootte vergelijken met wat Zoom
   opgeeft, de content_hash van Dropbox berekenen. Staat er al iets op het pad: met dezelfde grootte en hash is het
   bewezen, anders een nood en niets overschreven. Staat er niets: uploaden met mode add (koppelingen/dropbox_prive.py);
3. bewezen is een bestand pas als Dropbox dezelfde grootte en content_hash geeft; dan pas komt het in de staat
   (mijnagents-data/zoom-archief/staat.json, atomisch geschreven). Het tijdelijke bestand gaat altijd weg, ook bij een
   stopsignaal;
4. per meeting een opname.json zodra al haar bestanden bewezen zijn;
5. de dekking in mijnagents-data/zoom-archief/dekking.json: ja pas als een volledige inventaris niets meer te
   kopiëren vond en geen opname verdween voor ze bewezen was. De Zoomwacht leest dat voor ZA-01.
Op het bord en in het werkverslag alleen aantallen en GB, nooit een onderwerp, naam of pad. Een normale achterstand is
geen nood; een nood is een blokkade.

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
BRUSSEL = ZoneInfo("Europe/Brussels")
VENSTER = 30                      # dagen per vraag aan Zoom
KORT = 90                         # dagen die een gewone ronde leest
EERSTE_DAG = date(2018, 1, 1)     # de volledige inventaris begint hier; Mehdi's oudste opname is van 10-08-2021
BUDGET = 45 * 60                  # na zoveel seconden begint de ronde geen nieuw bestand meer
KETEN_UTC = ((7, 0), (13, 0), (23, 30))   # de gesprekkenketen (planning/gesprekken.cron); ervoor stoppen
KETEN_MARGE = 10 * 60             # zoveel seconden voor de keten begint er geen nieuw bestand meer
VRIJ_MARGE = 2 * 1024 ** 3        # zoveel schijf moet er naast het bestand vrij blijven op de VM
POGINGEN = 3                      # een tijdelijke fout wordt pas een nood na zoveel rondes op hetzelfde bestand
WISREGEL_DAGEN = 30               # de wisregel van ZA-01: wat ouder is, moet bewezen in Dropbox staan
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
    """De ronde stopt met kopiëren (schijf vol, Zoom vraagt rust); de rest komt een volgende ronde."""


# ------------------------------------------------------------------ staat ---
def staat_pad():
    return os.path.join(DATA, "staat.json")


def lees_staat():
    """De staat, of een lege bij de eerste ronde. Een onleesbare staat is een fout, nooit een lege: dan zou alles
    opnieuw gekopieerd lijken (en mode add het weigeren), en zou de dekking op nul vallen."""
    try:
        with open(staat_pad(), encoding="utf-8") as f:
            s = json.load(f)
    except FileNotFoundError:
        s = {}
    if not isinstance(s, dict) or not isinstance(s.get("bestanden", {}), dict):
        raise ValueError("staat.json onleesbaar")
    for k, v in (("bestanden", {}), ("meetings", {}), ("gezien", {}), ("verdwenen", {}), ("pogingen", {}),
                 ("inventaris", ""), ("gekopieerd", 0)):
        s.setdefault(k, v)
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
def opnamelijst(van, tot, pauze=0.2):
    """Alle meetings met opnames tussen van en tot (datums), uit de lijst en de prullenbak, samengevoegd op uuid. Elk
    bestand draagt of het in de prullenbak zit."""
    meetings = {}
    eind = tot
    while eind > van:
        begin = max(van, eind - timedelta(days=VENSTER))
        for prullenbak in (False, True):
            for m in Z.opnames(begin.isoformat(), eind.isoformat(), prullenbak=prullenbak):
                if not m.get("uuid") or not m.get("start"):
                    continue
                oud = meetings.setdefault(m["uuid"], {**m, "bestanden": []})
                bekend = {f["id"] for f in oud["bestanden"]}
                oud["bestanden"] += [{**f, "prullenbak": prullenbak} for f in m["bestanden"]
                                     if f.get("id") and f["id"] not in bekend]
            time.sleep(pauze)
        eind = begin
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


# ------------------------------------------------------------ kopiëren ---
def kopieer(f, pad, werkmap):
    """Een bestand van Zoom naar Dropbox, met bewijs (K3). Geeft de regel voor de staat."""
    nodig = int(f.get("grootte") or 0) + VRIJ_MARGE
    os.makedirs(werkmap, exist_ok=True)
    if shutil.disk_usage(werkmap).free < nodig:
        raise Stop("te weinig vrije schijf op de VM")
    tmp = os.path.join(werkmap, kort(f["id"], 16) + ".deel")
    try:
        n = Z.download_naar(f["id"], tmp)
        if f.get("grootte") and n != f["grootte"]:  # zonder opgegeven grootte bewijst alleen de hash van Dropbox
            raise Afwijking("download niet zo groot als Zoom opgeeft")
        h = D.inhoud_hash(tmp)
        m = D.metadata(pad)  # eerst kijken: een vorige ronde kan het er al gezet hebben (verloren antwoord)
        if m is None:
            try:
                m = D.upload_bestand(tmp, pad)
            except D.Bestaat:
                m = D.metadata(pad)
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
    """(noodtekst, tijdelijk) voor een fout bij een bestand. De tekst draagt geen url, onderwerp of aantal (N10)."""
    if isinstance(e, Afwijking):
        return f"Zoom-opname niet naar Dropbox gekopieerd: {e}", False
    if isinstance(e, Z.GeenRecht):
        return f"Zoom-opname niet naar Dropbox gekopieerd: Zoom weigert de download ({e.scope})", False
    if isinstance(e, Z.ZoomFout):
        return "Zoom-opname niet naar Dropbox gekopieerd: Zoom gaf het bestand niet", True
    return f"Zoom-opname niet naar Dropbox gekopieerd: Dropbox of de VM weigerde ({type(e).__name__})", True


def gb(bestanden):
    return sum(int(f.get("grootte") or 0) for f in bestanden) / 1024 ** 3


def werk(r, droog=False, budget=BUDGET, proef=0, klok=time.monotonic, nu_utc=nu):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return None
    if not D.beschikbaar():
        for n in D.nood(wat="de kopie van de Zoom-opnames"):
            r.nood(n["tekst"], wie=n["wie"])
        r.detail = "geen privé-Dropbox-token, niets gekopieerd"
        return None
    if keten_draait():
        r.noden_onbekend = True  # deze ronde keek niets na: de open noden blijven staan
        r.detail = "de gesprekkenketen draait, deze ronde overgeslagen"
        return None
    begin = klok()
    staat = lees_staat()
    r.bron("zoom-archief staat", {"bewezen": len(staat["bestanden"]), "inventaris": staat["inventaris"]})
    try:
        mehdi = mehdi_vastzetten()
    except Z.ZoomFout as e:
        r.nood("Zoom-opnamelijst niet leesbaar", wie="claude-code")
        r.detail = f"Zoom-gebruiker niet te lezen ({str(e)[:60]})"
        return None
    if not mehdi:
        r.nood("Zoom-gebruiker van Mehdi niet bewezen", wie="claude-code")
        r.detail = "geen bewezen Zoom-gebruiker, niets gelezen"
        return None
    vandaag = nu_utc().astimezone(BRUSSEL).date()
    volledig = staat["inventaris"] != vandaag.isoformat() or staat["gekopieerd"] > 0
    try:
        meetings = opnamelijst(EERSTE_DAG if volledig else vandaag - timedelta(days=KORT), vandaag + timedelta(days=1))
    except Z.GeenRecht as e:
        r.nood(f"Zoom-opnamelijst niet leesbaar: geen recht {e.scope}", wie="mehdi")
        r.detail = "opnamelijst niet leesbaar"
        return None
    except Z.ZoomFout as e:
        r.nood("Zoom-opnamelijst niet leesbaar", wie="claude-code")
        r.detail = f"opnamelijst niet leesbaar ({str(e)[:60]})"
        return None

    per_id = {f["id"]: (m, f) for m in meetings for f in m["bestanden"]}
    klaar = [f for _, f in per_id.values() if f.get("status") == "completed"]
    te_doen = [f for f in klaar if f["id"] not in staat["bestanden"]]
    if volledig:
        # Een opname die ik zag en die nu uit Zoom (lijst en prullenbak) weg is voor ze bewezen was: verdwenen (K8).
        for fid, oud in list(staat["gezien"].items()):
            if fid not in per_id and fid not in staat["bestanden"]:
                staat["verdwenen"][fid] = {**oud, "sinds": nu_utc().isoformat(timespec="seconds")}
                del staat["gezien"][fid]
    for f in te_doen:
        staat["gezien"][f["id"]] = {"start": f.get("start", ""), "grootte": f.get("grootte", 0)}
    volgorde = sorted(te_doen, key=lambda f: (not f.get("prullenbak"), f.get("start") or ""))
    if proef:
        volgorde = sorted(te_doen, key=lambda f: int(f.get("grootte") or 0))[:proef]

    gedaan, fouten, gestopt = [], {}, ""
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
                staat["bestanden"][f["id"]] = kopieer(f, pad_van(m, f), werkmap)
                staat["gezien"].pop(f["id"], None)
                staat["pogingen"].pop(f["id"], None)
                gedaan.append(f)
                schrijf_staat(staat)
            except Stop as e:
                gestopt = str(e)
                r.nood("Te weinig vrije schijf op de VM voor de kopie van de Zoom-opnames", wie="claude-code")
                break
            except Exception as e:  # noqa: BLE001
                tekst, tijdelijk = soort_fout(e)
                staat["pogingen"][f["id"]] = staat["pogingen"].get(f["id"], 0) + 1
                if "HTTP 429" in str(e):
                    gestopt = "Zoom vraagt rust"
                    break
                if not tijdelijk or staat["pogingen"][f["id"]] >= POGINGEN:
                    fouten[tekst] = fouten.get(tekst, 0) + 1
        for m in meetings:
            ids = [f["id"] for f in m["bestanden"]]
            if (ids and m["uuid"] not in staat["meetings"] and all(f.get("status") == "completed" for f in m["bestanden"])
                    and all(i in staat["bestanden"] for i in ids)):
                try:
                    schrijf_opname_json(m, staat["bestanden"], werkmap)
                    staat["meetings"][m["uuid"]] = staat["bestanden"][ids[0]]["pad"].rsplit("/", 1)[0]
                except Exception as e:  # noqa: BLE001
                    tekst, _ = soort_fout(e)
                    fouten[tekst] = fouten.get(tekst, 0) + 1
        if volledig:
            staat["inventaris"] = vandaag.isoformat()
            staat["gekopieerd"] = len(gedaan)
        else:
            staat["gekopieerd"] += len(gedaan)
        schrijf_staat(staat)
    for tekst in fouten:
        r.nood(tekst, wie="claude-code")
    if staat["verdwenen"]:
        r.nood("Zoom-opname verdwenen voor ze in Dropbox stond", wie="mehdi")

    rest = [f for f in klaar if f["id"] not in staat["bestanden"]]
    grens = (nu_utc() - timedelta(days=WISREGEL_DAGEN)).strftime("%Y-%m-%dT%H:%M:%SZ")
    oud_open = [f for f in rest if (f.get("start") or "") < grens]
    # Dekking ja: een volledige inventaris vond niets meer te kopiëren, en niets verdween voor het bewezen was (K6).
    dekking = volledig and not te_doen and not staat["verdwenen"] and not droog
    if not droog:
        _schrijf_json(os.path.join(DATA, "dekking.json"), {
            "ts": nu_utc().isoformat(timespec="seconds"), "dekking": dekking, "inventaris": staat["inventaris"],
            "volledig_gelezen": volledig, "bestanden": len(klaar), "bewezen": len(klaar) - len(rest), "open": len(rest),
            "open_ouder_dan_30_dagen": len(oud_open), "verdwenen": len(staat["verdwenen"])})
    r.detail = (f"{'droog: ' if droog else ''}{'proef: ' if proef else ''}{len(klaar)} bestanden ({gb(klaar):.1f} GB) "
                f"in Zoom {'(alles gelezen)' if volledig else f'(laatste {KORT} dagen)'}; {len(gedaan)} gekopieerd "
                f"({gb(gedaan):.1f} GB); nog {len(rest)} ({gb(rest):.1f} GB); ouder dan {WISREGEL_DAGEN} dagen allemaal "
                f"in Dropbox: {'ja' if not oud_open else 'nee'}; dekking: {'ja' if dekking else 'nee'}"
                + (f"; verdwenen {len(staat['verdwenen'])}" if staat["verdwenen"] else "")
                + (f"; fouten {sum(fouten.values())}" if fouten else "") + (f"; gestopt: {gestopt}" if gestopt else ""))
    ag.log("archief", "ronde", r.detail)
    return {"klaar": len(klaar), "gedaan": len(gedaan), "rest": len(rest), "oud_open": len(oud_open), "fouten": fouten,
            "gestopt": gestopt, "dekking": dekking, "volledig": volledig}


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
