#!/usr/bin/env python3
"""De Gespreksanalist: De Archivaris versie 3 (T-0120, ANGEL-1 per bron gesplitst volgens X9, met VOL-5).

Per opgenomen gesprek twee zinnen samenvatting en de actiepunten: wat, wie, tegen wanneer, voor wie (mehdi, collega,
klant, agent of onbekend) en een letterlijk citaat van hoogstens 200 tekens. Met het firmalabel van De Archivaris
(archivaris.py LABELS) als firma en soort, en het dossier, zodat De Dagbundelaar en Ai Angel ze per dossier dragen.

Per bron (X9):
- Privé gaat voor alles: alleen "privégesprek, N min". Geen transcript lezen, geen model, geen samenvatting. Privé is
  de privévlag of de afdeling privé van de wacht, het label Prive van De Archivaris, of Zoom-tekst: de vangnettekst van
  De Zoomwacht is altijd privé (zoom_wacht.py:266, X1). Zoom-tekst komt dus pas bij het model als die regel in De
  Zoomwacht zelf verandert, en dan ook hier.
- Fathom: de eigen samenvatting en actiepunten van Fathom (samenvatting.md en actiepunten.md van De Fathomwacht,
  FATHOM-1). Een gesprek met een samenvatting van Fathom gaat nooit naar het model; zonder samenvatting wacht het
  (Fathom heeft het model niet nodig, overleg T-0120 K3).
- Plaud en Zoom-tekst: het model op het abonnement van Mehdi (koppelingen/claude_abonnement.vraag), nooit de API en
  nooit een betaalde uitwijking (X3, keuze 1 van T-0122). Alleen als MODEL_AAN True is (uit tot het ja van Mehdi),
  hoogstens MAX_PER_DAG gesprekken per dag, en alleen met een meting van het weekvenster van hoogstens MAX_OUDERDOM
  oud die onder WEEKGRENS ligt (Budget).

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
import sys
import tempfile
import time
import unicodedata
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import claude_abonnement  # noqa: E402  het abonnement van Mehdi; nooit de API
import nummerlezer  # noqa: E402

VERSIE = 3
# De stap in de ronde van De Archivaris (Fathom zonder model en privé). Uit tot FATHOM-1 live is en De Fathomwacht
# samenvatting.md en actiepunten.md echt schrijft; aanzetten is een commit, geen omgevingsvariabele (X6: per onderdeel).
ANALYSE_AAN = False
# Plaud en Zoom-tekst via het model. Uit tot Mehdi ja zegt (X3, keuze 1 van T-0122: hoogstens vijf per nacht, nadat
# Extra usage in zijn Claude-account uit staat); ook aanzetten is een commit.
MODEL_AAN = False
MAX_PER_DAG = 5          # "hoogstens 5 per nacht": een teller per kalenderdag, hoe vaak de cron ook draait
WEEKGRENS = 0.60         # geen nieuwe vraag als het weekvenster (seven_day) op 60 procent of hoger staat (X3, Codex)
MAX_OUDERDOM = 12 * 3600  # een oudere of geen meting van het weekvenster: geen vraag (onbekend is geen ruimte)
MAX_TRANSCRIPT = 200000  # tekens transcript naar het model
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
# VOL-5 zonder label van De Archivaris (Plaud op de VM heeft geen gesprek.json): de afdeling van de wacht als firma
# (fathom_wacht.AFDELINGEN, die De Plaudwacht via fw.herken ook gebruikt)
AFDELING_FIRMA = {"h-architects": "HA", "unabo": "UNABO", "harmoniebouw": "Harmoniebouw", "contrax": "Contrax",
                  "tkn": "TKN", "elevait": "Elevait"}


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
    """Privé volgens de wacht (vlag of afdeling), het label Prive van De Archivaris, of Zoom-tekst: de vangnettekst is
    altijd privé (zoom_wacht.py:266), ook als zoom.json iets anders zou zeggen. Bij twijfel privé."""
    afdeling = str(geval.get("afdeling") or "").strip().lower()
    return bool(geval.get("prive") or afdeling in ("prive", "privé") or geval.get("bron") == "zoom"
                or str(geval.get("label") or "").lower() in ("prive", "privé"))


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
    # nummerlezer leest alleen het eerste nummer na de agendacode: staan er meer nummers in de titel, dan niets
    if not code or not titel or len(set(re.findall(r"(?<!\d)\d{4,6}(?!\d)", titel))) != 1:
        return "", ""
    k = nummerlezer.enig([k for k in nummerlezer.lees(titel, "vergadertitel") if k.rol == "agendafirma"], code)
    return (k.nummer, "agendatitel, niet bevestigd") if k else ("", "")


def herkomst(geval):
    """VOL-5: label, firma, soort, dossier, dossier_bewijs en label_van van een werkgesprek. Het label van De Archivaris
    gaat voor. Zonder label (Plaud op de VM) de afdeling van de wacht als firma, en het dossier dat de wacht besliste
    ('FIRMA:NUMMER' in gesprek_log.project, plaud/dossier.beslis), alleen bij dezelfde firma en zekerheid hoog of middel."""
    label = str(geval.get("label") or "")
    if label:
        firma, soort = firma_en_soort(label)
        dossier, bewijs = dossier_van(label, geval.get("ha_nummer", ""), geval.get("titel", ""))
        van = "archivaris"
    else:
        afdeling = str(geval.get("afdeling") or "").strip().lower()
        firma, soort = AFDELING_FIRMA.get(afdeling, ""), ("intern" if afdeling == "regie" else "")
        m = re.fullmatch(r"([A-Z]{4}):(\d{3,6})", str(geval.get("project") or "").strip())
        zeker = str(geval.get("zekerheid") or "")
        dossier, bewijs = ((m.group(2), f"dossier van de wacht, zekerheid {zeker}")
                           if m and firma and FIRMACODE.get(firma) == m.group(1) and zeker in ("hoog", "middel") else ("", ""))
        van = "afdeling van de wacht" if firma or soort else ""
    return {"label": label, "firma": firma, "soort": soort, "dossier": dossier, "dossier_bewijs": bewijs, "label_van": van}


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
    """De letterlijke woorden op een tijdstip: de uiting die hoogstens een minuut ervoor begon (of anders binnen 15
    seconden erna), aangevuld met de volgende tot ongeveer 60 tekens, ingekort tot MAX_CITAAT op een woordgrens. ''
    zonder tijdstip of zonder uiting in de buurt: nooit een uiting van veel eerder."""
    if sec is None:
        return ""
    i = max((n for n, (s, _, _) in enumerate(uit) if s is not None and sec - 60 <= s <= sec), default=None)
    if i is None:
        i = min((n for n, (s, _, _) in enumerate(uit) if s is not None and sec < s <= sec + 15), default=None)
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


# ------------------------------------------------------------------------------- het model (Plaud, Zoom) ---
SYSTEEM = """Je bent De Gespreksanalist, een assistent van Mehdi. Je leest het transcript van een opgenomen werkgesprek
en geeft alleen een JSON-object terug, tussen ```json en ```, in deze vorm:
{"samenvatting": "...", "actiepunten": [{"wat": "...", "wie": "...", "tegen_wanneer": "...", "voor_wie": "...",
"citaat": "..."}]}
Regels:
- samenvatting: precies twee zinnen in het Nederlands: waarover het gesprek ging en wat er besloten werd.
- actiepunten: alleen wat in het gesprek echt afgesproken of toegezegd werd: iemand gaat iets doen. Geen raad, geen
  wens, niets wat je zelf bedenkt. Is er geen actiepunt, geef dan een lege lijst.
- wat: kort, met een werkwoord. wie: wie het doet, zoals in het gesprek; leeg als het niet gezegd werd.
  tegen_wanneer: een datum (JJJJ-MM-DD) of de woorden uit het gesprek; leeg als niets gezegd werd.
  voor_wie: voor wie de taak is: mehdi, collega, klant, agent of onbekend.
- citaat: de letterlijke woorden uit het transcript waarop het actiepunt steunt, hoogstens 200 tekens, in een stuk,
  zonder spreker en zonder weglating. Een actiepunt zonder letterlijk citaat wordt weggegooid.
- Nooit iets versturen of voorstellen om iets te versturen. Geen emoji."""


def json_uit(tekst):
    from aankoop import onderzoek as O      # zoals bouw/offertes.py: het laatste ```json-blok, anders { ... }
    return O.json_uit(tekst)


def modelvraag(geval, uit, vraag):
    """(samenvatting, actiepunten, weg, tokens) van het model op het abonnement, zonder gereedschap; een ValueError
    zonder geldig antwoord. De samenvatting wordt twee zinnen, de actiepunten gaan door keur()."""
    regels = "\n".join(f"{wie or 'spreker'}: {t}" for _, wie, t in uit)
    gebruiker = json.dumps({"gesprek": {"bron": geval["bron"], "datum": geval.get("datum", ""),
                                        "minuten": geval.get("minuten") or 0, "label": geval.get("label") or ""},
                            "transcript_ingekort": len(regels) > MAX_TRANSCRIPT, "transcript": regels[:MAX_TRANSCRIPT]},
                           ensure_ascii=False)
    antwoord = vraag(SYSTEEM, gebruiker, tools=(), max_beurten=2, timeout=600)
    d = json_uit((antwoord or {}).get("tekst"))
    if not isinstance(d, dict) or not isinstance(d.get("actiepunten", []), list):
        raise ValueError("geen geldig JSON-antwoord")
    samenvatting = twee_zinnen(d.get("samenvatting"))
    if not samenvatting:
        raise ValueError("antwoord zonder samenvatting")
    goed, weg = keur(d.get("actiepunten") or [], corpus(uit))
    return samenvatting, goed, weg, int((antwoord or {}).get("tokens") or 0)


def weekbenutting(bestand=None, nu=None):
    """(benutting of None, gezien): de laatst gemeten benutting van het weekvenster (seven_day) uit het limietbestand
    van claude_abonnement ({"info": rate_limit_info, "gezien": tijd}, onthoud_limiet; elke agent op het abonnement
    schrijft het bij elke vraag met een limietmelding), en wanneer dat gemeten is. None zonder meting, of als het venster
    sindsdien herstart is."""
    try:
        with open(bestand or claude_abonnement.LIMIET_BESTAND, encoding="utf-8") as f:
            d = json.load(f) or {}
        info, gezien = d.get("info") or {}, float(d.get("gezien") or 0)
        vensters = dict(info.get("unifiedWindows") or {})
    except (OSError, ValueError, AttributeError, TypeError):
        return None, 0.0
    if info.get("rateLimitType") and info.get("utilization") is not None:
        vensters.setdefault(str(info["rateLimitType"]), {"utilization": info["utilization"], "resetsAt": info.get("resetsAt")})
    nu = time.time() if nu is None else nu
    waarden = []
    for naam, v in vensters.items():
        if not (str(naam).startswith("seven_day") and isinstance(v, dict)):
            continue
        try:
            benut, herstart = float(v.get("utilization")), float(v.get("resetsAt") or 0) or gezien + 7 * 86400
        except (TypeError, ValueError):
            continue
        if herstart > nu:
            waarden.append(benut)
    return (max(waarden) if waarden else None), gezien


def proefvragen(dag, proefmap):
    """Hoeveel modelvragen de proeven van die dag deden (veld modelvragen in hun proefbestand, gespreksanalist_proef.py).
    Een onleesbaar proefbestand telt niet mee."""
    n = 0
    try:
        namen = os.listdir(proefmap)
    except OSError:
        return 0
    for naam in namen:
        if not (naam.startswith("proef-") and naam.endswith(".json")):
            continue
        try:
            with open(os.path.join(proefmap, naam), encoding="utf-8") as f:
                d = json.load(f)
            n += int(d.get("modelvragen") or 0) if str(d.get("ts") or "")[:10] == dag else 0
        except (OSError, ValueError, AttributeError, TypeError):
            continue
    return n


class Budget:
    """Mag er nog een gesprek naar het model? Hoogstens MAX_PER_DAG per dag (teller.json in UITVOER; een mislukte vraag
    telt mee), en alleen met een meting van het weekvenster die hoogstens MAX_OUDERDOM oud is en onder WEEKGRENS ligt.
    Na elke vraag moet er een nieuwe meting zijn. Anders stopt het model voor de rest van de ronde: onbekend of oud is
    geen ruimte (Codex T-0120 toets 1). De meting komt van elke agent op het abonnement (Ai Angel, ANGEL-3). Een fout van
    het abonnement stopt het ook (stop, fout). De stand van de dag is de dagteller van de nachtronde plus de
    modelvragen van de proeven van die dag (hun proefbestand, veld modelvragen): zo telt elk de ander mee (Codex T-0120
    toets 2). teller=None: alleen in het geheugen (de proef)."""

    def __init__(self, dag, teller="", limiet=None, klok=time.time, proefmap=None):
        self.dag, self.limiet, self.klok = dag, limiet, klok
        self.bestand = os.path.join(UITVOER, "teller.json")
        self.proefmap = proefmap or os.path.join(UITVOER, "proef")
        self.teller = self.bestand if teller == "" else teller
        self.vandaag, self.sinds, self.stop, self.fout = self._stand() + proefvragen(self.dag, self.proefmap), None, None, None

    def _stand(self):
        try:
            with open(self.bestand, encoding="utf-8") as f:
                d = json.load(f) or {}
            return int(d.get("vragen") or 0) if d.get("dag") == self.dag else 0
        except (OSError, ValueError, AttributeError, TypeError):
            return 0

    def reden(self):
        """None als de volgende vraag mag, anders waarom niet."""
        if self.stop:
            return self.stop
        if self.vandaag >= MAX_PER_DAG:
            return f"al {MAX_PER_DAG} gesprekken naar het model vandaag"
        nu = self.klok()
        benutting, gezien = weekbenutting(self.limiet, nu)
        if self.sinds is not None and (gezien < self.sinds or benutting is None):
            self.stop = "weekvenster na de vorige vraag niet gemeten"
        elif benutting is None or nu - gezien > MAX_OUDERDOM:
            self.stop = f"weekvenster onbekend of ouder dan {MAX_OUDERDOM // 3600} uur"
        elif benutting >= WEEKGRENS:
            self.stop = f"weekvenster op {int(benutting * 100)} procent (grens {int(WEEKGRENS * 100)})"
        return self.stop

    def tel(self):
        self.vandaag, self.sinds = self.vandaag + 1, self.klok()
        if self.teller:
            schrijf_600(self.teller, {"dag": self.dag, "vragen": self.vandaag})


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
    werk = {**_kop(geval), "prive": False, **herkomst(geval)}
    if geval["bron"] == "fathom":
        eigen = fathom_eigen(geval["map"], uit)
        if eigen is None:
            return None, "wacht op de samenvatting van Fathom"
        samenvatting, punten, weg = eigen
        return {**werk, "samenvatting": samenvatting, "samenvatting_van": "fathom", "actiepunten": punten,
                "weggegooid": weg, "tokens": 0, "ts": stempel}, "fathom"
    reden = "model staat uit" if not MODEL_AAN else (budget.reden() if budget else "geen budget")
    if reden:
        return None, reden
    budget.tel()
    try:
        samenvatting, punten, weg, tokens = modelvraag(geval, uit, vraag or claude_abonnement.vraag)
    except claude_abonnement.Fout as e:     # aanmelden, limiet, bron of mislukt: nooit een uitwijking naar de API
        budget.stop, budget.fout = f"abonnement: {e.soort or 'mislukt'}", e
        return None, budget.stop
    except ValueError as e:
        return None, f"mislukt: {e}"
    return {**werk, "samenvatting": samenvatting, "samenvatting_van": "model", "actiepunten": punten,
            "weggegooid": weg, "tokens": tokens, "ts": stempel}, "model"


def stap(geval, budget=None, vraag=None, map_=None, nu=None):
    """(record om te bewaren of None, toestand). Een gesprek gaat een keer door versie 3. Opnieuw alleen als het nu
    privé is en toen niet (of omgekeerd): dan verdwijnt de samenvatting en blijft alleen de privéregel. Een nieuw label
    of dossier (een correctie van Mehdi) zet alleen de herkomst opnieuw, zonder model."""
    oud, prive = lees(geval["uniek"], map_), is_prive(geval)
    if oud and int(oud.get("versie") or 0) >= VERSIE and bool(oud.get("prive")) == prive:
        nieuw = {} if prive else herkomst(geval)
        if all(oud.get(k, "") == v for k, v in nieuw.items()):
            return None, "al gedaan"
        return {**oud, **nieuw, "ts": (nu or datetime.now().astimezone()).isoformat()}, "nieuw label"
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
