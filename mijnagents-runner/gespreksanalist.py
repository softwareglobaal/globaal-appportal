#!/usr/bin/env python3
"""De Gespreksanalist: De Archivaris versie 3 (T-0120, ANGEL-1 per bron gesplitst volgens X9, met VOL-5).

Per opgenomen gesprek twee zinnen samenvatting en de actiepunten: wat, wie, tegen wanneer, voor wie (mehdi, collega,
klant, agent of onbekend) en een letterlijk citaat van hoogstens 200 tekens. Met het firmalabel van De Archivaris
(archivaris.py LABELS) als firma en soort, en het dossier, zodat De Dagbundelaar en Ai Angel ze per dossier dragen.

Per bron (X9):
- Privé gaat voor alles: alleen "privégesprek, N min". Geen transcript lezen, geen model, geen samenvatting. Privé is
  de privévlag of de afdeling privé van de wacht, het label Prive van De Archivaris, of Zoom-tekst zonder uitdrukkelijk
  prive=false: de vangnettekst van De Zoomwacht is altijd privé (zoom_wacht.py:266, X1).
- Fathom: de eigen samenvatting en actiepunten van Fathom (samenvatting.md en actiepunten.md van De Fathomwacht,
  FATHOM-1). Een gesprek met een samenvatting van Fathom gaat nooit naar het model; zonder samenvatting wacht het
  (Fathom heeft het model niet nodig, overleg T-0120 K3).
- Plaud en Zoom-tekst: het model, zie modelvraag().

Een controle zonder model (citaat_in) gooit elk actiepunt weg waarvan het citaat niet letterlijk in het transcript
staat. Ook een actiepunt van Fathom krijgt zo een citaat: de uiting op het tijdstip dat Fathom noemt.

Uitvoer: een bestand per gesprek in ~/appportal/mijnagents-data/gespreksanalist/<bron>/<id>.json (map 700, bestand 600),
op de VM. Niet in gesprek.json: dat gaat elke 30 minuten naar Dropbox (planning/mac/data_uit_mehdi_sync.sh, map
fathom-data), en Plaud en Zoom-tekst hebben op de VM geen gesprek.json (plaud/plaud_invoer_push.sh stuurt alleen
transcript.json; zoom_wacht.vangnet_schrijven schrijft er bewust geen). Nooit iets op het bord: het werkverslag van De
Archivaris krijgt alleen aantallen.
"""
import ast
import hashlib
import json
import os
import re
import tempfile
import sys
import unicodedata
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import nummerlezer  # noqa: E402

VERSIE = 3
# De stap in de ronde van De Archivaris (Fathom zonder model en privé). Uit tot FATHOM-1 live is en De Fathomwacht
# samenvatting.md en actiepunten.md echt schrijft; aanzetten is een commit, geen omgevingsvariabele (X6: per onderdeel).
ANALYSE_AAN = False
MAX_CITAAT = 200
MIN_CITAAT = 12          # tekens na normaal(), en minstens drie woorden: "ja" of "ok" staat in elk transcript
VOOR_WIE = ("mehdi", "collega", "klant", "agent", "onbekend")
DATA = os.path.expanduser(os.environ.get("MIJNAGENTS_DATA", "~/appportal/mijnagents-data"))
UITVOER = os.path.join(DATA, "gespreksanalist")
FATHOM_DATA = os.path.join(DATA, "fathom-data")
PLAUD_INVOER = os.path.join(DATA, "plaud-invoer")
ZOOM_DATA = os.path.join(DATA, "zoom-data")
PLAUD_OP_MAC = "Data uit Mehdi/Plaud/"   # zo begint gesprek_log.archief van De Plaudwacht (plaud_wacht.py ARCHIEF_OP_MAC)
# VOL-5: de firma van het label als interne code, voor het dossier uit de agendatitel (koppelingen/nummerlezer.py)
FIRMACODE = {"HA": "HARC", "UNABO": "UNAB", "TKN": "TKNB", "Harmoniebouw": "HARM", "Contrax": "CONT", "Elevait": "ELEV"}


# ------------------------------------------------------------------------------------------- transcript ---
def seconden(stempel):
    """'UU:MM:SS' of 'MM:SS' naar seconden; None als het niet te lezen is."""
    m = re.fullmatch(r"\s*(?:(\d+):)?(\d{1,2}):(\d{2})(?:[.,]\d+)?\s*", str(stempel or ""))
    return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3)) if m else None


def uitingen(pad):
    """[(seconden of None, spreker, tekst)] uit transcript.json, in de vorm van Fathom en Zoom ({speaker:
    {display_name}, text, timestamp 'UU:MM:SS'}) of van Plaud ({speaker, content, start_time in ms}). [] als er niets
    leesbaars is."""
    try:
        with open(pad, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    uit = []
    for u in data if isinstance(data, list) else []:
        if not isinstance(u, dict):
            continue
        if "content" in u:                                  # Plaud
            tekst, wie = u.get("content"), u.get("speaker")
            try:
                sec = int(float(u.get("start_time") or 0)) // 1000
            except (TypeError, ValueError):
                sec = None
        else:                                               # Fathom en de Zoom-tekst van De Zoomwacht
            s = u.get("speaker")
            tekst, wie, sec = u.get("text"), (s.get("display_name") if isinstance(s, dict) else s), seconden(u.get("timestamp"))
        tekst = str(tekst or "").strip()
        if tekst:
            uit.append((sec, str(wie or "").strip(), tekst))
    return uit


def normaal(t):
    """Voor het vergelijken (zoals mehdi_agent.normaal): kleine letters, zonder opmaak- en aanhalingstekens, een spatie
    tussen woorden."""
    t = unicodedata.normalize("NFKC", str(t or "")).casefold()
    t = re.sub(r"[*_`\"'“”‘’«»]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def corpus(uit):
    """Alle uitingen achter elkaar, genormaliseerd: daarin moet een citaat letterlijk staan."""
    return normaal(" ".join(t for _, _, t in uit))


def citaat_in(citaat, tekst):
    """Staat het citaat letterlijk in het transcript (tekst = corpus())? Hoogstens MAX_CITAAT tekens, en na normaal()
    minstens MIN_CITAAT tekens en drie woorden. Een weglating of een eigen verwoording staat er niet letterlijk in."""
    c = str(citaat or "").strip()
    if not c or len(c) > MAX_CITAAT:
        return False
    n = normaal(c).strip(" .,:;!?-")
    return len(n) >= MIN_CITAAT and len(n.split()) >= 3 and n in tekst


def keur(punten, tekst):
    """(goed, weg): de actiepunten met de vijf velden en een letterlijk citaat; weg telt wat de controle weggooide.
    De controle hangt niet van het model af: een verzonnen of verwoord citaat valt weg."""
    goed, weg = [], 0
    for p in punten if isinstance(punten, list) else []:
        if not isinstance(p, dict):
            weg += 1
            continue
        punt = {k: str(p.get(k) or "").strip() for k in ("wat", "wie", "tegen_wanneer", "voor_wie", "citaat")}
        if punt["voor_wie"] not in VOOR_WIE:
            punt["voor_wie"] = "onbekend"
        if not punt["wat"] or not citaat_in(punt["citaat"], tekst):
            weg += 1
            continue
        punt.update(wat=punt["wat"][:300], wie=punt["wie"][:80], tegen_wanneer=punt["tegen_wanneer"][:40])
        goed.append(punt)
    return goed, weg


def twee_zinnen(tekst):
    """De eerste twee zinnen, zonder opmaak (koppen, lijsttekens, vet, links), hoogstens 400 tekens. Een regel zonder
    leesteken aan het eind (een lijstpunt) telt als een zin."""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(tekst or ""))
    zinnen = []
    for regel in t.splitlines():
        regel = regel.strip()
        if not regel or regel.startswith("#"):
            continue
        regel = re.sub(r"^(?:[-*•]|\d+[.)])\s+", "", regel).replace("**", "").replace("__", "").strip()
        if regel:
            zinnen += [z.strip() for z in re.split(r"(?<=[.!?])\s+", regel if regel[-1] in ".!?" else regel + ".") if z.strip()]
        if len(zinnen) >= 2:
            break
    return " ".join(zinnen[:2])[:400]


# ------------------------------------------------------------------------------------------------- privé ---
def prive_regel(minuten):
    """Het enige wat een privégesprek geeft (zoals De Plaudwacht: zonder duur 'duur onbekend')."""
    try:
        m = int(float(minuten or 0))
    except (TypeError, ValueError):
        m = 0
    return f"privégesprek, {m} min" if m > 0 else "privégesprek, duur onbekend"


def is_prive(geval):
    """Privé volgens de wacht (vlag of afdeling), het label Prive van De Archivaris, of Zoom-tekst die niet
    uitdrukkelijk werk is (vangnettekst is altijd privé, zoom_wacht.py:266). Bij twijfel privé."""
    afdeling = str(geval.get("afdeling") or "").strip().lower()
    if geval.get("prive") or afdeling in ("prive", "privé") or str(geval.get("label") or "").lower() in ("prive", "privé"):
        return True
    return geval.get("bron") == "zoom" and geval.get("zoom_prive") is not False


# -------------------------------------------------------------------------------- firma en dossier (VOL-5) ---
def firma_en_soort(label):
    """Het label van De Archivaris als (firma, soort): 'UNABO project' -> ('UNABO', 'project'), 'Harmoniebouw' ->
    ('Harmoniebouw', ''), 'Regie intern' -> ('', 'intern'), 'Onbekend' of leeg -> ('', '')."""
    label = str(label or "").strip()
    if label in ("", "Onbekend", "Prive"):
        return "", ""
    if label == "Regie intern":
        return "", "intern"
    deel = label.rsplit(" ", 1)
    if len(deel) == 2 and deel[1] in ("project", "sales"):
        return deel[0], deel[1]
    return label, ""


def dossier_van(label, ha_nummer="", titel=""):
    """(nummer, bewijs). H-A: het nummer dat De Archivaris bewees (ha_projectnummer, de bevestigde regel van
    nummerlezer). Een andere firma heeft geen bevestigde nummerregel (nummerlezer.NUMMERREGEL_BEVESTIGD): dan alleen het
    enige nummer van die firma in de agendatitel van dat uur, met bewijs 'agendatitel, niet bevestigd'."""
    firma, _ = firma_en_soort(label)
    if firma == "HA":
        return (ha_nummer, "bevestigd") if ha_nummer else ("", "")
    code = FIRMACODE.get(firma)
    if not code or not titel:
        return "", ""
    k = nummerlezer.enig([k for k in nummerlezer.lees(titel, "vergadertitel") if k.rol == "agendafirma"], code)
    return (k.nummer, "agendatitel, niet bevestigd") if k else ("", "")


# ------------------------------------------------------------------------------------------------ Fathom ---
def _markdown(lichaam):
    """De tekst van een samenvatting van Fathom. Tot FATHOM-1 schreef De Fathomwacht str() van het hele object
    (fathom_wacht.py:252): dan de markdown_formatted daaruit."""
    lichaam = lichaam.strip()
    if lichaam.startswith("{"):
        for lees in (json.loads, ast.literal_eval):
            try:
                d = lees(lichaam)
            except (ValueError, SyntaxError):
                continue
            if isinstance(d, dict):
                return str(d.get("markdown_formatted") or "")
    return lichaam


def citaat_bij(uit, sec):
    """De letterlijke woorden op een tijdstip: de uiting die daar loopt, aangevuld met de volgende tot ongeveer 60
    tekens, ingekort tot MAX_CITAAT op een woordgrens. '' zonder tijdstip of uiting."""
    if sec is None:
        return ""
    i = max((n for n, (s, _, _) in enumerate(uit) if s is not None and s <= sec), default=None)
    if i is None:
        return ""
    tekst = uit[i][2]
    for _, _, t in uit[i + 1:]:
        if len(tekst) >= 60:
            break
        tekst += " " + t
    return tekst if len(tekst) <= MAX_CITAAT else tekst[:MAX_CITAAT].rsplit(" ", 1)[0]


def fathom_eigen(map_, uit):
    """(samenvatting, actiepunten, weg) uit samenvatting.md en actiepunten.md van De Fathomwacht, of None zonder
    samenvatting van Fathom. Een actiepunt van Fathom: wat = description, wie = assignee.name, citaat = de uiting op
    recording_timestamp; zonder citaat valt het weg, zoals elk actiepunt."""
    try:
        with open(os.path.join(map_, "samenvatting.md"), encoding="utf-8") as f:
            ruw = f.read()
    except OSError:
        return None
    lichaam = ruw.split("\n", 1)[1] if ruw.startswith("# Samenvatting van Fathom") and "\n" in ruw else ruw
    samenvatting = twee_zinnen(_markdown(lichaam))
    if not samenvatting:
        return None
    try:
        with open(os.path.join(map_, "actiepunten.md"), encoding="utf-8") as f:
            items = json.load(f)
    except OSError:
        items = []
    except ValueError:
        items = None
    punten = []
    for it in items if isinstance(items, list) else []:
        if isinstance(it, dict):
            wie = it.get("assignee") if isinstance(it.get("assignee"), dict) else {}
            punten.append({"wat": it.get("description"), "wie": wie.get("name"), "tegen_wanneer": "",
                           "voor_wie": "onbekend", "citaat": citaat_bij(uit, seconden(it.get("recording_timestamp")))})
        else:
            punten.append(it)
    goed, weg = keur(punten, corpus(uit))
    return samenvatting, goed, weg + (1 if items is None else 0)


# ----------------------------------------------------------------------------------------------- uitvoer ---
def pad_van(uniek, map_=None):
    """<UITVOER>/<bron>/<sleutel>.json voor gesprek_log.uniek ('fathom:123', 'plaud:ab12', 'zoom:meeting:<uuid>'). Een
    sleutel met andere tekens krijgt er een stukje hash bij, zodat twee gesprekken nooit hetzelfde bestand delen."""
    bron, _, sleutel = str(uniek).partition(":")
    schoon = re.sub(r"[^A-Za-z0-9_.-]+", "_", sleutel).strip("._")[:100] or "leeg"
    if schoon != sleutel:
        schoon += "-" + hashlib.sha1(sleutel.encode()).hexdigest()[:10]
    return os.path.join(map_ or UITVOER, re.sub(r"[^a-z]+", "", bron) or "onbekend", f"{schoon}.json")


def lees(uniek, map_=None):
    """Het bewaarde record van dit gesprek, of None (ook als het onleesbaar is)."""
    try:
        with open(pad_van(uniek, map_), encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def schrijf_600(pad, data):
    """Een bestand met rechten 600 in een map met 700, in een keer op zijn plaats (os.replace)."""
    os.makedirs(os.path.dirname(pad), mode=0o700, exist_ok=True)
    fd, tijdelijk = tempfile.mkstemp(prefix=".bezig-", dir=os.path.dirname(pad))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        os.chmod(tijdelijk, 0o600)
        os.replace(tijdelijk, pad)
    except BaseException:
        try:
            os.remove(tijdelijk)
        except OSError:
            pass
        raise
    return pad


def bewaar(rec, map_=None):
    return schrijf_600(pad_van(rec["uniek"], map_), rec)


# ------------------------------------------------------------------------------------------------ verwerk ---
def _kop(geval):
    return {"versie": VERSIE, "uniek": geval["uniek"], "bron": geval["bron"], "datum": geval.get("datum", ""),
            "start": geval.get("start", ""), "minuten": int(float(geval.get("minuten") or 0))}


def verwerk(geval, budget=None, vraag=None, nu=None):
    """(record of None, toestand) voor een gesprek. geval: uniek, bron (fathom, plaud of zoom), datum, start, minuten,
    prive en afdeling van de wacht, label van De Archivaris, ha_nummer (bewezen H-A-nummer), titel (agenda van dat uur),
    map (met transcript.json, en voor Fathom samenvatting.md en actiepunten.md), zoom_prive (zoom.json).
    Privé eerst, zonder iets te lezen."""
    stempel = (nu or datetime.now().astimezone()).isoformat()
    if is_prive(geval):
        return {**_kop(geval), "prive": True, "regel": prive_regel(geval.get("minuten")), "ts": stempel}, "privé"
    uit = uitingen(os.path.join(geval.get("map") or "-", "transcript.json"))
    if not uit:
        return None, "geen transcript"
    firma, soort = firma_en_soort(geval.get("label"))
    dossier, bewijs = dossier_van(geval.get("label"), geval.get("ha_nummer", ""), geval.get("titel", ""))
    werk = {**_kop(geval), "prive": False, "label": geval.get("label") or "", "firma": firma, "soort": soort,
            "dossier": dossier, "dossier_bewijs": bewijs}
    if geval["bron"] == "fathom":
        eigen = fathom_eigen(geval["map"], uit)
        if eigen is None:
            return None, "wacht op de samenvatting van Fathom"
        samenvatting, punten, weg = eigen
        return {**werk, "samenvatting": samenvatting, "samenvatting_van": "fathom", "actiepunten": punten,
                "weggegooid": weg, "tokens": 0, "ts": stempel}, "fathom"
    return None, "model staat uit"


def stap(geval, budget=None, vraag=None, map_=None, nu=None):
    """(record om te bewaren of None, toestand). Een gesprek gaat een keer door versie 3. Opnieuw alleen als het nu
    privé is en toen niet (of omgekeerd): dan verdwijnt de samenvatting en blijft alleen de privéregel. Een nieuw label
    (een correctie van Mehdi) zet alleen firma, soort en dossier opnieuw, zonder model."""
    oud, prive = lees(geval["uniek"], map_), is_prive(geval)
    if oud and int(oud.get("versie") or 0) >= VERSIE and bool(oud.get("prive")) == prive:
        if prive or oud.get("label", "") == (geval.get("label") or ""):
            return None, "al gedaan"
        firma, soort = firma_en_soort(geval.get("label"))
        dossier, bewijs = dossier_van(geval.get("label"), geval.get("ha_nummer", ""), geval.get("titel", ""))
        return {**oud, "label": geval.get("label") or "", "firma": firma, "soort": soort, "dossier": dossier,
                "dossier_bewijs": bewijs, "ts": (nu or datetime.now().astimezone()).isoformat()}, "nieuw label"
    return verwerk(geval, budget, vraag, nu)


def zoom_gevallen(van, tot, map_=None):
    """De Zoom-tekst van het vangnet van De Zoomwacht (zoom-data/<map>/zoom.json), van van tot en met tot (Brusselse
    dag), als gevallen; uniek zoals De Zoomwacht het in de gesprekkentabel zet (zoom:meeting:<uuid>). zoom.json zonder
    prive telt als privé."""
    map_ = map_ or ZOOM_DATA
    try:
        namen = sorted(os.listdir(map_))
    except OSError:
        return []
    uit = []
    for naam in namen:
        if naam.startswith("."):
            continue
        try:
            with open(os.path.join(map_, naam, "zoom.json"), encoding="utf-8") as f:
                meta = json.load(f)
        except (OSError, ValueError):
            continue
        start = str((meta or {}).get("start_brussel") or "") if isinstance(meta, dict) else ""
        if not meta.get("uuid") or not (van <= start[:10] <= tot):
            continue
        uit.append({"uniek": f"zoom:meeting:{meta['uuid']}", "bron": "zoom", "datum": start[:10], "start": start[11:16],
                    "minuten": meta.get("minuten") or 0, "map": os.path.join(map_, naam),
                    "zoom_prive": meta.get("prive", True), "label": ""})
    return uit
