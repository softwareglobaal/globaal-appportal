#!/usr/bin/env python3
"""Ai Angel, technisch mehdi-agent (Regie, alleen voor Mehdi): leest de dagbundel en zet zijn taken klaar.
Naam Ai Angel: keuze van Mehdi op 31-10-2026. De technische naam (bord, runner, sleutels, planning) blijft mehdi-agent.

Opdracht van Mehdi (31-10-2026): De Dagbundelaar bundelt, de Mehdi-agent leest wat er binnenkwam en zet taken en to-do's
klaar, doet wat hij kan (concepten), zegt voor wie een taak is (dispatchen, en leert van Mehdi's correcties) en coacht hem
om zijn dagen beter te organiseren, tot zes keer per dag. Keuze van Mehdi dezelfde dag: de agent leest alleen de
dagbundel, en gaat alleen via de verwijzing in de bundel naar de bron. Ontwerp: docs/ontwerp-mehdi-agent.md.

Wat ik lees:
  1. de dagbundel: het dagbestand van vandaag en de twee dagen ervoor, zoals De Dagbundelaar het schrijft
     (mijnagents-data/dagboek/JJJJ/JJJJ-MM-DD.md en .json; de Dropbox-map Dagbundelaar is daar een kopie van);
  2. om te dispatchen en te leren: wat Mehdi tegen mij zei (tabel gesprek, aan mehdi-agent, alleen lezend), de collega's
     uit kern (naam, functie, afdeling, firma) en de agents op het bord (r.collegas).
Ik lees nooit zelf een wacht, een mailbox, WhatsApp of een transcript.

Wat ik doe, op de uren van UREN (Brussel; de cron draait elk uur op :20, planning/mehdi-agent.cron):
  1. veranderde de bundel niet, zei Mehdi niets nieuws en is het geen ochtend of avond, dan stop ik;
  2. Claude leest de bundel, mijn open taken en wat Mehdi zei, met mijn werkwijze van het bord als regelboek, en geeft
     taken terug: wat, voor wie (Mehdi, een collega of een agent), waarom, de bron, prioriteit en waar nuttig een concept;
  3. ik controleer elke taak zonder model: een nieuwe taak zonder bron die letterlijk in de bundel of in Mehdi's woorden
     staat, valt weg; een collega die niet in kern staat of een agent die niet op het bord staat, wordt Mehdi; wat privé
     is, blijft bij Mehdi;
  4. ik bewaar de taken (mijnagents-data/mehdi-agent/staat.json) en zet ze klaar voor Mehdi: de lijst van de dag (soort
     taken), 's ochtends "Te doen vandaag" en 's avonds "Avondoverzicht" (soort verslag; De Bode bundelt die), en lees
     elk item terug van het bord.
Lukt Claude niet, dan blijft de lijst van de vorige ronde staan, met een nood.
Claude via de API (standaard) of, met MEHDI_AGENT_ROUTE=abonnement, op het Claude-abonnement van Mehdi zonder
API-sleutel (koppelingen/claude_abonnement.py, ANGEL-3); die keuze is van Mehdi (werkstand T-0122).

Ik verstuur nooit zelf iets: een concept blijft een concept tot Mehdi het zelf stuurt. Met MEHDI_AGENT_DOORGEVEN=aan
zet ik een taak voor een agent op de witte lijst ONTVANGERS ook bij die agent klaar, als voorstel (De Doorgever,
ANGEL-9); de vlag staat uit en de lijst is leeg tot Mehdi per soort taak kiest.

Draaien: python3 mehdi_agent.py                         (een ronde, als het uur in UREN valt)
         python3 mehdi_agent.py --nu                    (een ronde, ook buiten UREN)
         python3 mehdi_agent.py --droog                 (geen ronde, geen klaarzet, geen staat: toont het resultaat)
         python3 mehdi_agent.py --droog --zaad          (idem, met de werkwijze uit werkwijze/)
         python3 mehdi_agent.py --droog --werkwijze PAD (idem, met de werkwijze uit PAD)
         --moment ochtend|tussendoor|avond              (met --droog: dit moment in plaats van het uur)
         --stil                                         (met --droog: alleen de vorm, geen namen of inhoud)
         --uit PAD                                      (met --droog: het volledige resultaat in PAD, rechten 600)
"""
import hashlib
import json
import os
import re
import sys
import tempfile
import unicodedata
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import organisatie  # noqa: E402
import claude_abonnement  # noqa: E402  alleen met MEHDI_AGENT_ROUTE=abonnement (ANGEL-3); start niets bij import

NAAM = "mehdi-agent"
ag = bord.Agent(NAAM)
BRUSSEL = ZoneInfo("Europe/Brussels")
DATA = os.path.expanduser("~/appportal/mijnagents-data")
DAGBOEK = os.environ.get("MEHDI_AGENT_DAGBOEK", os.path.join(DATA, "dagboek"))
STAAT = os.environ.get("MEHDI_AGENT_STAAT", os.path.join(DATA, "mehdi-agent", "staat.json"))
MODEL = os.environ.get("MEHDI_AGENT_MODEL", "claude-opus-5-5")
# "api" (wat nu draait) of "abonnement": Claude op het abonnement van Mehdi, zoals De Prijsonderzoeker (ANGEL-3 en VOL-17
# van T-0120). De standaard blijft de API tot Mehdi kiest (werkstand T-0122); het model op het abonnement kiest
# ABONNEMENT_MODEL (koppelingen/claude_abonnement.py).
ROUTE = os.environ.get("MEHDI_AGENT_ROUTE", "api")
# Twintig minuten na de rondes van De Dagbundelaar (driehoeksoverleg Dagboek compleet, P5). De VM loopt in UTC en
# Debian-cron kent geen tijdzone: de cron draait elk uur en ik kijk zelf of het een van deze uren is in Brussel.
UREN = tuple(int(u) for u in os.environ.get("MEHDI_AGENT_UREN", "7,10,13,16,19,22").split(",") if u.strip())
MAX_TOKENS = 32000      # het denken telt mee; weekconsolidatie viel met 16000 bij effort high vier keer weg
TERUG = 3               # vandaag en de twee dagen ervoor
DAGBESTAND_MAX = 60000  # tekens per dagbestand naar het model
GESPREK_DAGEN = 14      # zo ver terug lees ik wat Mehdi tegen mij zei
MAX_NIEUW = 12          # nieuwe taken per ronde
MAX_OPEN = 40           # open taken die ik bijhoud
OUD_DAGEN = 14          # een open taak die zo lang niet bijgewerkt werd, vervalt
MAX_AFGEROND = 100
MAX_GELEERD = 30
OCHTEND = (7, 12)       # de eerste ronde tussen 07:00 en 12:00 (Brussel) is de ochtend
AVOND = 16              # de eerste ronde vanaf 16:00 is de avond: zo zit het avondoverzicht in de avondbundel
                        # van De Bode om 17:00 (bode.py, AVOND_VANAF; ANGEL-4)
# De Doorgever (ANGEL-9, M10 van T-0120): een taak voor een agent zet ik zelf bij die agent klaar, als voorstel, maar alleen
# met MEHDI_AGENT_DOORGEVEN=aan en bij een ontvanger op de witte lijst. Beide kiest Mehdi per soort taak (werkwijze, Wat
# Mehdi beslist); tot dan staat de vlag uit en is de lijst leeg. Een ontvanger komt er pas op als zijn eigen code een taak
# van mehdi-agent aanneemt: De Agendawacht neemt nu alleen taken van De Werfverslag voorbereider aan (agenda_wacht.py,
# terugkijktaken), en De Plaudwacht leest elke taak als een eigen opdracht.
DOORGEVEN = os.environ.get("MEHDI_AGENT_DOORGEVEN", "uit") == "aan"
ONTVANGERS = {}         # naam van de agent op het bord: wat hij van mij aanneemt, bv. "agenda-wacht": "zet bezoek in agenda"
MAX_DOORGEVEN = 5       # nieuwe doorgaven per ronde
STIL_DAGEN = 3          # zo lang mag een doorgegeven taak onopgepakt liggen; dan gaat ze terug naar Mehdi
VOOR = ("mehdi", "collega", "agent")
PRIORITEIT = ("hoog", "normaal", "laag")
STATUS = ("open", "gedaan", "vervallen")
VELDEN = ("id", "tekst", "voor", "wie", "waarom", "bron", "dag", "prioriteit", "status", "concept")
PRIVE = re.compile(r"priv[eé]", re.I)
DAGNAMEN = ("maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag")

_TEKST = {"type": "string"}
SCHEMA = {
    "type": "object",
    "properties": {
        "taken": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": _TEKST, "tekst": _TEKST, "voor": {"type": "string", "enum": list(VOOR)}, "wie": _TEKST,
                           "waarom": _TEKST, "bron": _TEKST, "dag": _TEKST,
                           "prioriteit": {"type": "string", "enum": list(PRIORITEIT)},
                           "status": {"type": "string", "enum": list(STATUS)}, "concept": _TEKST},
            "required": list(VELDEN), "additionalProperties": False}},
        "overzicht": _TEKST,
        "tip": _TEKST,
        "geleerd": {"type": "array", "items": _TEKST},
        "ontbreekt": {"type": "array", "items": _TEKST},
    },
    "required": ["taken", "overzicht", "tip", "geleerd", "ontbreekt"],
    "additionalProperties": False,
}

OPDRACHT = {
    "ochtend": "Het is ochtend. Werk de takenlijst bij en schrijf in overzicht het plan voor vandaag: hoogstens vijf "
               "punten, het belangrijkste eerst, rond de afspraken van de dag. Laat tip leeg.",
    "avond": "Het is avond. Werk de takenlijst bij en schrijf in overzicht wat vandaag gedaan is, wat bleef liggen en wat "
             "morgen eerst moet. Schrijf in tip een tip om zijn dag of werk beter te organiseren, uit wat je deze dagen zag.",
    "tussendoor": "Werk alleen de takenlijst bij. Laat overzicht en tip leeg.",
}
UITVOER = ("Geef in taken elke taak die nieuw is of verandert (status, prioriteit, voor wie, reden of concept). Een open "
           "taak die niet verandert, mag je weglaten. Een bestaande taak krijgt haar id uit open_taken; noemt Mehdi een "
           "nummer, gebruik dan het id van dat nummer. Een nieuwe taak heeft een leeg id en status open. bron: letterlijk "
           "een stuk van de regel uit de dagbundel, of van Mehdi's woorden. wie: bij een collega de naam zoals in "
           "collegas, bij een agent de naam van de agent, bij Mehdi leeg. Maak een taak uit onlangs_afgerond niet "
           "opnieuw. geleerd: alleen nieuwe regels uit wat Mehdi zei, anders leeg. ontbreekt: wat je in de dagbundel "
           "miste om goed werk te doen, kort.")


class Weigering(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------ tijd ---
def brussel(nu=None):
    return (nu or datetime.now(timezone.utc)).astimezone(BRUSSEL)


def aan_de_beurt(nu=None, uren=UREN):
    """Een ronde alleen op de uren van UREN in Brussel: zo volgt het ritme de zomer- en wintertijd zonder twee cronregels."""
    return brussel(nu).hour in uren


def dagen_terug(nu, terug=TERUG):
    """Vandaag en de dagen ervoor, als Brusselse datums, nieuwste eerst."""
    vandaag = brussel(nu).date()
    return [(vandaag - timedelta(days=i)).isoformat() for i in range(terug)]


def moment(nu, staat):
    """ochtend, avond of tussendoor. De ochtend en de avond komen elk een keer per dag: de eerste ronde in dat venster."""
    b = brussel(nu)
    vandaag = b.date().isoformat()
    if b.hour >= AVOND and staat.get("avond") != vandaag:
        return "avond"
    if OCHTEND[0] <= b.hour < OCHTEND[1] and staat.get("ochtend") != vandaag:
        return "ochtend"
    return "tussendoor"


# ----------------------------------------------------------------------------------------------- lezen ---
def _lees(pad):
    try:
        with open(pad, encoding="utf-8") as f:
            return f.read()
    except (OSError, UnicodeDecodeError):
        return None


def lees_bundels(dagen, map_=None):
    """De dagbestanden van deze dagen (.md en .json), zoals De Dagbundelaar ze schrijft. Een dag zonder bestand ontbreekt
    gewoon: vandaag bestaat pas na de eerste ronde van de dag. Geeft [{dag, dagbestand, telling}], in de volgorde van
    dagen."""
    map_ = map_ or DAGBOEK
    uit = []
    for dag in dagen:
        md = _lees(os.path.join(map_, dag[:4], f"{dag}.md"))
        js = _lees(os.path.join(map_, dag[:4], f"{dag}.json"))
        if md is None and js is None:
            continue
        try:
            telling = json.loads(js) if js else None
        except ValueError:
            telling = None
        uit.append({"dag": dag, "dagbestand": (md or "")[:DAGBESTAND_MAX], "telling": telling})
    return uit


def wat_mehdi_zei(nu, lees=bord.db_lees):
    """Wat Mehdi de laatste veertien dagen tegen mij zei (op het bord of via De Bode), met het antwoord. None als het bord
    niet te lezen is: onbekend is niet leeg (L29)."""
    grens = (nu - timedelta(days=GESPREK_DAGEN)).astimezone(timezone.utc).isoformat()
    try:
        rijen = lees("SELECT id, tekst, antwoord, ts FROM gesprek WHERE aan = ? AND ts >= ? ORDER BY id", (NAAM, grens))
    except bord.BordOnbekend:
        return None
    return [{"id": r["id"], "ts": str(r.get("ts") or "")[:16], "tekst": str(r.get("tekst") or "")[:1500],
             "antwoord": str(r.get("antwoord") or "")[:800]} for r in rijen]


def collegas_kern(lees=organisatie.collegas):
    """De collega's in dienst uit kern: naam, voornaam, functie, afdeling, firma. None als kern niet te lezen is."""
    try:
        lijst = lees()
    except Exception:  # noqa: BLE001  kern via docker exec: elke fout is onbekend
        return None
    uit = []
    for c in lijst or []:
        naam = str(c.get("naam") or "").strip()
        if not naam or c.get("in_dienst") is False:
            continue
        uit.append({"naam": naam, "voornaam": str(c.get("voornaam") or "").strip(),
                    "functie": str(c.get("functie") or c.get("rol") or "").strip()[:80],
                    "afdeling": str(c.get("afdeling") or "").strip(), "firma": str(c.get("firma") or "").strip()})
    return uit


def vingerafdruk(bundels, gezegd):
    h = hashlib.sha256()
    for b in bundels:
        h.update(f"{b['dag']}\n{b['dagbestand']}\n{json.dumps(b['telling'], sort_keys=True)}\n".encode())
    for g in gezegd or []:
        h.update(f"{g['id']}:{g['antwoord']}\n".encode())
    return h.hexdigest()[:16]


# ----------------------------------------------------------------------------------------------- staat ---
def laad_staat(pad=None):
    try:
        staat = json.loads(_lees(pad or STAAT) or "{}")
    except ValueError:
        staat = {}
    if not isinstance(staat, dict):
        staat = {}
    staat.setdefault("taken", {})
    staat.setdefault("afgerond", [])
    staat.setdefault("geleerd", [])
    staat.setdefault("nummers", {})
    return staat


def bewaar_staat(staat, pad=None):
    """Atomair: eerst een tijdelijk bestand in dezelfde map, dan vervangen, en teruglezen."""
    pad = pad or STAAT
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    tekst = json.dumps(staat, ensure_ascii=False, indent=1, sort_keys=True) + "\n"
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(pad), prefix=".staat-")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(tekst)
    os.replace(tmp, pad)
    if _lees(pad) != tekst:
        raise RuntimeError("staat niet goed teruggelezen")


def open_taken(staat):
    rang = {p: i for i, p in enumerate(PRIORITEIT)}
    return sorted(staat.get("taken", {}).values(), key=lambda t: (rang.get(t.get("prioriteit"), 1), t.get("sinds", "")))


# ------------------------------------------------------------------------------------------------ model ---
def systeem(werkwijze, collegas_bord, lessen):
    """Het regelboek letterlijk in de opdracht (N12), met de collega's op het bord (N14) en de gedeelde lessen (N13)."""
    delen = [
        "Je bent Ai Angel, de assistent van Mehdi Chegini, architect en CEO van een groep bedrijven in België, "
        "Suriname en India. Hij heeft weinig tijd en leest niet graag: schrijf kort, in gewone Nederlandse taal, zonder "
        "emoji en zonder gedachtestreepjes. Je volgt je werkwijze hieronder; die is de waarheid.",
        "=== JOUW WERKWIJZE ===\n" + (werkwijze or "").strip(),
        bord.collega_tekst(collegas_bord or []),
    ]
    les = [f"- {x.get('id') or ''}: {x.get('les') or ''}" for x in lessen or [] if isinstance(x, dict) and x.get("les")]
    if les:
        delen.append("=== GEDEELDE LESSEN VAN ALLE AGENTS ===\n" + "\n".join(les[:60]))
    return "\n\n".join(delen)


def invoer(nu, m, bundels, staat, gezegd, kern):
    """Alles wat het model ziet, compact. Pure functie (test zonder netwerk)."""
    b = brussel(nu)
    nummer = {tid: nr for nr, tid in (staat.get("nummers") or {}).items()}
    open_ = [{"id": t["id"], "nummer": nummer.get(t["id"], ""), "tekst": t["tekst"], "voor": t["voor"], "wie": t["wie"],
              "waarom": t["waarom"], "bron": t["bron"], "dag": t["dag"], "prioriteit": t["prioriteit"],
              "concept": t.get("concept", ""), "sinds": t.get("sinds", "")[:10]} for t in open_taken(staat)]
    grens = (b.date() - timedelta(days=TERUG)).isoformat()
    afgerond = [{"tekst": t["tekst"], "status": t["status"], "dag": t["dag"]}
                for t in staat.get("afgerond", []) if str(t.get("afgerond", ""))[:10] >= grens][-20:]
    return {
        "nu": f"{DAGNAMEN[b.weekday()]} {b:%d-%m-%Y %H:%M} (Brussel)",
        "vandaag": b.date().isoformat(),
        "moment": m,
        "opdracht": OPDRACHT[m] + " " + UITVOER,
        "dagbundel": [{"dag": x["dag"], "dagbestand": x["dagbestand"], "telling": x["telling"]} for x in bundels],
        "open_taken": open_,
        "onlangs_afgerond": afgerond,
        "wat_mehdi_zei": gezegd,
        "geleerde_regels": staat.get("geleerd", []),
        "collegas": [{k: c[k] for k in ("naam", "functie", "afdeling", "firma")} for c in kern],
    }


def vraag_claude(system, inhoud, client=None, route=None, vraag=None):
    """Een aanroep met een gestructureerd antwoord (json_schema), zoals weekconsolidatie.py. Een weigering of een afgekapt
    antwoord is een gewoon antwoord met status 200: dat vang ik apart op, anders lijkt een leeg antwoord een rustige dag.
    route (standaard ROUTE): "abonnement" gaat naar vraag_abonnement en raakt de API-sleutel nooit aan."""
    if (route or ROUTE) == "abonnement":
        return vraag_abonnement(system, inhoud, vraag)
    if client is None:
        import sleutelbron  # de Anthropic-sleutel alleen uit ~/appportal/.env (T-0064), alleen op de API-weg
        sleutelbron.zet_anthropic()
        from anthropic import Anthropic
        client = Anthropic()
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=MAX_TOKENS,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=system,
        messages=[{"role": "user", "content": json.dumps(inhoud, ensure_ascii=False)}],
        timeout=900)
    gebruik = getattr(resp, "usage", None)
    meta = {"model": getattr(resp, "model", MODEL), "stop_reason": getattr(resp, "stop_reason", ""),
            "tokens_in": getattr(gebruik, "input_tokens", 0) or 0, "tokens_uit": getattr(gebruik, "output_tokens", 0) or 0}
    if meta["stop_reason"] == "refusal":
        raise Weigering(f"model weigerde ({meta['tokens_in']} tokens in)")
    if meta["stop_reason"] == "max_tokens":
        raise RuntimeError(f"antwoord afgekapt ({meta['tokens_uit']} tokens uit)")
    tekst = next((x.text for x in resp.content if getattr(x, "type", "") == "text"), "")
    return json.loads(tekst), meta


VORM = ("=== VORM VAN JE ANTWOORD ===\nAntwoord met precies een JSON-object volgens dit JSON-schema, zonder tekst ervoor of "
        "erna. Elk veld is verplicht; een veld zonder inhoud is een lege tekst of een lege lijst.\n")


def vraag_abonnement(system, inhoud, vraag=None):
    """Dezelfde vraag op het abonnement van Mehdi (koppelingen/claude_abonnement.py), zonder gereedschap, zoals De
    Prijsonderzoeker: het schema staat in de opdracht, het antwoord gaat door json.loads en schema_fout. Een
    claude_abonnement.Fout (aanmelden, limiet) gaat ongewijzigd naar werk(): de lijst van de vorige ronde blijft staan.
    vraag is te vervangen in een test."""
    vraag = vraag or claude_abonnement.vraag
    uit = vraag(system + "\n\n" + VORM + json.dumps(SCHEMA, ensure_ascii=False), json.dumps(inhoud, ensure_ascii=False),
                tools=(), timeout=900, max_beurten=2)
    meta = {"model": uit.get("model") or claude_abonnement.MODEL, "stop_reason": uit.get("stop") or "",
            "tokens_in": int(uit.get("tokens") or 0), "tokens_uit": 0}
    tekst = str(uit.get("tekst") or "").strip()
    blok = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", tekst, re.S)     # een codeblok rond het object mag
    try:
        obj = json.loads(blok.group(1) if blok else tekst)
    except ValueError:
        raise RuntimeError(f"antwoord van het abonnement is geen JSON ({len(tekst)} tekens)") from None
    fout = schema_fout(obj, SCHEMA)
    if fout:
        raise RuntimeError(f"antwoord van het abonnement past niet in het schema: {fout}")
    return obj, meta


def schema_fout(w, s, pad="antwoord"):
    """De eerste plek waar w niet in het strikte schema s past (object, array, string en enum, zoals SCHEMA), of "".
    Zonder de waarde zelf: die kan een naam dragen, en de melding komt in het werkverslag."""
    soort = s.get("type")
    if soort == "object":
        if not isinstance(w, dict):
            return f"{pad}: geen object"
        velden = s.get("properties") or {}
        for k in s.get("required") or ():
            if k not in w:
                return f"{pad}.{k}: ontbreekt"
        if s.get("additionalProperties") is False and set(w) - set(velden):
            return f"{pad}: {len(set(w) - set(velden))} velden die het schema niet kent"
        return next((f for k, sub in velden.items() if k in w for f in [schema_fout(w[k], sub, f"{pad}.{k}")] if f), "")
    if soort == "array":
        if not isinstance(w, list):
            return f"{pad}: geen lijst"
        return next((f for i, x in enumerate(w) for f in [schema_fout(x, s.get("items") or {}, f"{pad}[{i}]")] if f), "")
    if soort == "string":
        if not isinstance(w, str):
            return f"{pad}: geen tekst"
        return f"{pad}: geen toegelaten waarde" if "enum" in s and w not in s["enum"] else ""
    return f"{pad}: soort {soort} kent de controle niet"


# ----------------------------------------------------------------------------------------- controleren ---
def normaal(t):
    """Voor het vergelijken: kleine letters, zonder opmaak- en aanhalingstekens, een spatie tussen woorden."""
    t = unicodedata.normalize("NFKC", str(t or "")).casefold()
    t = re.sub(r"[*_`\"'“”‘’«»]", "", t)
    return re.sub(r"\s+", " ", t).strip()


def bron_in(bron, corpus):
    """Staat de bron letterlijk in de bundel of in Mehdi's woorden? Een datum vooraan (de dag staat al apart) en een
    lijstteken tellen niet mee. Een weglating (... of het teken voor drie puntjes) mag: dan moet elk stuk van minstens
    zes tekens erin staan."""
    bron = re.sub(r"^\s*\d{4}-\d{2}-\d{2}\s*[,:;-]?\s*", "", str(bron or ""))
    stukken = [normaal(s).strip(" .,:;-") for s in re.split(r"\.\.\.|…", bron)]
    stukken = [s[2:] if s.startswith("- ") else s for s in stukken]
    stukken = [s for s in stukken if len(s) >= 6]
    return bool(stukken) and all(s in corpus for s in stukken)


def zoek_collega(wie, kern):
    """De naam zoals in kern, op de volledige naam of een voornaam die maar een collega draagt; anders None."""
    w = normaal(wie)
    if not w:
        return None
    for c in kern:
        if normaal(c["naam"]) == w:
            return c["naam"]
    voornaam = [c for c in kern if c.get("voornaam") and normaal(c["voornaam"]) == w]
    return voornaam[0]["naam"] if len(voornaam) == 1 else None


def _zonder_lidwoord(t):
    return normaal(re.sub(r"^\s*(de|het)\s+", "", str(t or ""), flags=re.I))


def zoek_agent(wie, agents):
    """Het label van een actieve agent op het bord, op naam of label (De en Het vooraan tellen niet); anders None."""
    w = _zonder_lidwoord(wie)
    if not w:
        return None
    for a in agents or []:
        if w in (_zonder_lidwoord(a.get("naam")), _zonder_lidwoord(a.get("label"))):
            return a.get("label") or a.get("naam")
    return None


def agent_naam(wie, agents):
    """De naam op het bord (voor klaarzet) van de agent die zoek_agent herkent, op naam of label; anders None."""
    w = _zonder_lidwoord(wie)
    if not w:
        return None
    for a in agents or []:
        if w in (_zonder_lidwoord(a.get("naam")), _zonder_lidwoord(a.get("label"))):
            return a.get("naam") or None
    return None


def _datum(s, standaard):
    s = str(s or "").strip()[:10]
    return s if re.match(r"^\d{4}-\d{2}-\d{2}$", s) else standaard


def verwerk(uit, staat, bundels, gezegd, kern, agents, nu):
    """Het antwoord van het model, gecontroleerd zonder model, in een nieuwe staat. Geeft (staat, telling, ontbreekt)."""
    staat = json.loads(json.dumps(staat))
    taken, afgerond = staat["taken"], staat["afgerond"]
    nummers = staat.get("nummers") or {}
    corpus = normaal(" \n ".join([b["dagbestand"] + " " + json.dumps(b["telling"], ensure_ascii=False) for b in bundels]
                                 + [g["tekst"] for g in gezegd or []]))
    nu_s = nu.astimezone(timezone.utc).isoformat(timespec="seconds")
    laatste_dag = bundels[0]["dag"] if bundels else brussel(nu).date().isoformat()
    al_af = {t.get("id") for t in afgerond}
    telling = Counter()
    for x in uit.get("taken") or []:
        t = {k: str(x.get(k) or "").strip() for k in VELDEN}
        if not t["tekst"]:
            telling["leeg"] += 1
            continue
        tid = t["id"]
        if tid not in taken and tid in nummers:          # Mehdi noemde het nummer uit de lijst
            tid = nummers[tid]
        if tid not in taken:
            if t["status"] != "open":
                telling["nieuw_al_af"] += 1
                continue
            if not bron_in(t["bron"], corpus):
                telling["zonder_bron"] += 1                 # geen bron in de bundel: geen taak (werkwijze, stap 4)
                continue
            tid = "t-" + hashlib.sha1(f"{normaal(t['tekst'])}|{t['dag']}".encode()).hexdigest()[:8]
            if tid in al_af:
                telling["al_afgerond"] += 1
                continue
            if tid not in taken:
                if telling["nieuw"] >= MAX_NIEUW:
                    telling["te_veel"] += 1
                    continue
                taken[tid] = {"id": tid, "bron": t["bron"][:300], "dag": _datum(t["dag"], laatste_dag), "sinds": nu_s,
                              "status": "open"}
                telling["nieuw"] += 1
            else:
                telling["bijgewerkt"] += 1
        else:
            telling["bijgewerkt"] += 1
        oud = taken[tid]
        if t["status"] in ("gedaan", "vervallen"):
            afgerond.append(dict(oud, status=t["status"], afgerond=nu_s, reden=t["waarom"][:200]))
            del taken[tid]
            telling["bijgewerkt"] -= 1
            telling[t["status"]] += 1
            continue
        voor, wie = (t["voor"] if t["voor"] in VOOR else "mehdi"), ""
        if voor == "collega":
            wie = zoek_collega(t["wie"], kern) or ""
        elif voor == "agent":
            wie = zoek_agent(t["wie"], agents) or ""
        if voor != "mehdi" and not wie:
            telling["onbekend_wie"] += 1                    # bestaat niet in kern of op het bord: dan is het voor Mehdi
            voor = "mehdi"
        if voor != "mehdi" and PRIVE.search(" ".join((oud.get("bron", ""), t["bron"], t["tekst"], t["waarom"]))):
            telling["prive_bij_mehdi"] += 1                 # privé gaat nooit naar een ander
            voor, wie = "mehdi", ""
        oud.update(tekst=t["tekst"][:300], voor=voor, wie=wie, waarom=t["waarom"][:300],
                   prioriteit=t["prioriteit"] if t["prioriteit"] in PRIORITEIT else "normaal",
                   concept=t["concept"][:1500] or oud.get("concept", ""), bijgewerkt=nu_s)
    # Wat te lang blijft liggen of de lijst te lang maakt, vervalt: zo blijft de lijst te lezen (oudste en laagste eerst).
    grens = (nu - timedelta(days=OUD_DAGEN)).astimezone(timezone.utc).isoformat(timespec="seconds")
    for tid, t in list(taken.items()):
        if (t.get("bijgewerkt") or t.get("sinds") or "") < grens:
            afgerond.append(dict(t, status="vervallen", afgerond=nu_s, reden="te lang open zonder nieuws"))
            del taken[tid]
            telling["vervallen"] += 1
    teveel = open_taken(staat)[MAX_OPEN:]
    for t in teveel:
        afgerond.append(dict(t, status="vervallen", afgerond=nu_s, reden="lijst te lang"))
        del taken[t["id"]]
        telling["vervallen"] += 1
    staat["afgerond"] = afgerond[-MAX_AFGEROND:]
    if gezegd:                                            # regels leer ik alleen uit wat Mehdi zelf zei
        bekend = {normaal(g) for g in staat["geleerd"]}
        for g in uit.get("geleerd") or []:
            g = str(g or "").strip()[:300]
            if g and normaal(g) not in bekend:
                staat["geleerd"].append(g)
                bekend.add(normaal(g))
                telling["geleerd"] += 1
        staat["geleerd"] = staat["geleerd"][-MAX_GELEERD:]
    ontbreekt = [str(o).strip()[:200] for o in uit.get("ontbreekt") or [] if str(o).strip()][:5]
    return staat, telling, ontbreekt


# ----------------------------------------------------------------------------------------------- tonen ---
def _inspring(t):
    return str(t).strip().replace("\n", "\n   ")


def _brusselse_dag(ts):
    try:
        t = datetime.fromisoformat(str(ts or ""))
    except ValueError:
        return ""
    return brussel(t if t.tzinfo else t.replace(tzinfo=timezone.utc)).date().isoformat()


def lijst(staat, nu, ontbreekt=()):
    """De takenlijst als markdown, genummerd over alle groepen. Geeft (tekst, nummers): nummers {"1": id, ...}, zodat Mehdi
    in de volgende ronde een nummer kan noemen."""
    b = brussel(nu)
    regels = [f"Bijgewerkt {b:%d-%m-%Y %H:%M}. Bijsturen kan op het bord (vak Zeg iets tegen Ai Angel) of via "
              "WhatsApp, bijvoorbeeld: \"Ai Angel, 2 is gedaan\" of \"Ai Angel, 3 gaat naar\" en dan de naam."]
    nummers, nr = {}, 0
    open_ = open_taken(staat)
    for voor, kop in (("mehdi", "Voor jou"), ("collega", "Voor een collega"), ("agent", "Voor een agent")):
        groep = [t for t in open_ if t.get("voor") == voor]
        if not groep:
            continue
        regels += ["", f"## {kop}", ""]
        for t in groep:
            nr += 1
            nummers[str(nr)] = t["id"]
            wie = f"{t['wie']}: " if voor != "mehdi" and t.get("wie") else ""
            regels.append(f"{nr}. {wie}{t['tekst']} ({t.get('prioriteit', 'normaal')})")
            if t.get("waarom"):
                regels.append(f"   Waarom: {_inspring(t['waarom'])}")
            regels.append(f"   Bron: {t.get('dag', '')}, {_inspring(t.get('bron', ''))}")
            if t.get("concept"):
                regels.append(f"   Concept: {_inspring(t['concept'])}")
            if t.get("doorgegeven"):
                weg = t["doorgegeven"]
                regels.append(f"   Doorgegeven aan {weg['naar']} op {_brusselse_dag(weg.get('ts'))}, als voorstel ("
                              + ("opgepakt" if weg.get("status") == "opgepakt" else "wacht") + ")")
    if not nr:
        regels += ["", "Geen open taken."]
    af = [t for t in staat.get("afgerond", []) if t.get("reden") not in ("te lang open zonder nieuws", "lijst te lang")
          and _brusselse_dag(t.get("afgerond")) == b.date().isoformat()]
    if af:
        regels += ["", "## Afgerond vandaag", ""] + [f"- {t['tekst']} ({t['status']})" for t in af]
    if ontbreekt:
        regels += ["", "## Wat ik miste in de dagbundel", ""] + [f"- {o}" for o in ontbreekt]
    return "\n".join(regels) + "\n", nummers


def titel_lijst(staat, nu):
    """Zonder namen: een titel staat op plekken waar dat niet mag (lijst van de bak, werkverslag)."""
    open_ = open_taken(staat)
    hoog = sum(1 for t in open_ if t.get("prioriteit") == "hoog")
    return f"Te doen {brussel(nu):%d-%m}: {len(open_)} open" + (f", {hoog} hoog" if hoog else "")


def items(staat, nu, m, uit, ontbreekt):
    """De klaarzet-items van deze ronde. De lijst van de dag volgt de staat; ochtend en avond alleen als Claude ze schreef."""
    vandaag = brussel(nu).date().isoformat()
    tekst, nummers = lijst(staat, nu, ontbreekt)
    uitvoer = [{"voor": "mehdi", "soort": "taken", "sleutel": vandaag, "uniek": f"{NAAM}:taken:{vandaag}",
                "titel": titel_lijst(staat, nu), "inhoud": tekst}]
    if uit is not None and m in ("ochtend", "avond") and str(uit.get("overzicht") or "").strip():
        delen = [str(uit["overzicht"]).strip()]
        if m == "avond" and str(uit.get("tip") or "").strip():
            delen.append("Tip: " + str(uit["tip"]).strip())
        delen.append("## Alle open taken\n\n" + tekst)
        uitvoer.append({"voor": "mehdi", "soort": "verslag", "sleutel": vandaag, "uniek": f"{NAAM}:{m}:{vandaag}",
                        "titel": (f"Te doen vandaag {brussel(nu):%d-%m}" if m == "ochtend"
                                  else f"Avondoverzicht {brussel(nu):%d-%m}"),
                        "inhoud": "\n\n".join(delen)})
    return uitvoer, nummers


def klaarzetten(te_zetten, nu, zet=None, lees=None):
    """Zetten en teruglezen (zoals De Communicatiebundelaar, Codex CB09). Een item dat al opgepakt was, volgt de bron niet
    meer op het bord; dan zet ik deze versie als een nieuw item ernaast, met het uur erbij. Geeft (antwoord, fout)."""
    zet = zet or ag.klaarzet
    lees = lees or (lambda uniek: bord.call("/api/klaarzet?" + urllib.parse.urlencode({"uniek": uniek, "status": "alle"}))
                    .get("items") or [])
    antwoord = zet(te_zetten)
    opnieuw, fout = [], []
    for it in ag.maskeer(te_zetten):
        terug = lees(it["uniek"])
        if any(x.get("inhoud") == it["inhoud"] and x.get("titel") == it["titel"] for x in terug):
            continue
        if terug and all(x.get("status") != "klaar" for x in terug):
            opnieuw.append(dict(it, uniek=f"{it['uniek']}:{brussel(nu):%H%M}"))
        else:
            fout.append(it["uniek"])
    if opnieuw:
        zet(opnieuw)
        for it in opnieuw:
            if not any(x.get("inhoud") == it["inhoud"] for x in lees(it["uniek"])):
                fout.append(it["uniek"])
    return antwoord, fout


# ------------------------------------------------------------------------------------------- doorgeven ---
def doorgeef_besluiten(staat, agents, ontvangers=None, aan=None):
    """Per open taak voor een agent die nog niet weg is, wat De Doorgever ermee doet: [{id, naar, besluit}]. naar is de
    agent als de taak deze ronde weggaat (met de vlag uit: zou weggaan), anders leeg. Zet niets (droog en test)."""
    ontvangers = ONTVANGERS if ontvangers is None else ontvangers
    aan = DOORGEVEN if aan is None else aan
    uit, n = [], 0
    for t in open_taken(staat):
        if t.get("voor") != "agent" or t.get("doorgegeven"):
            continue
        naam = agent_naam(t.get("wie"), agents)
        if PRIVE.search(" ".join(str(t.get(k) or "") for k in ("tekst", "bron", "waarom", "concept"))):
            reden = "privé"                              # privé gaat nooit naar een ander
        elif t.get("teruggekomen"):
            reden = "ging al eens terug"                 # een agent liet ze liggen: nu is ze van Mehdi
        elif not naam:
            reden = "de agent staat niet op het bord"
        elif naam not in ontvangers:
            reden = f"{naam} staat niet op de witte lijst"
        elif n >= MAX_DOORGEVEN:
            reden = f"hoogstens {MAX_DOORGEVEN} per ronde"
        else:
            n += 1
            uit.append({"id": t["id"], "naar": naam,
                        "besluit": f"gaat naar {naam}" if aan else f"zou naar {naam} (doorgeven staat uit)"})
            continue
        uit.append({"id": t["id"], "naar": "", "besluit": f"blijft bij Mehdi: {reden}"})
    return uit


def doorgeven(staat, nu, agents, zet=None, lees=None, pak=None, ontvangers=None, aan=None):
    """De Doorgever (ANGEL-9). Eerst wat al weg is teruglezen: opgepakt is beweging. Ligt het na STIL_DAGEN nog klaar, of
    staat het niet meer klaar, dan neem ik het item terug (opgepakt door mij, zodat het niet dubbel gebeurt) en is de taak
    weer voor Mehdi. Is de taak intussen afgerond of niet meer voor die agent (Mehdi of het model veranderde ze), dan
    neem ik het item meteen terug. Dan, met de vlag aan, de nieuwe: soort taak, uniek mehdi-agent:taak:<id>, als voorstel,
    en teruglezen. Een bord dat niet antwoordt, beslist niets (onbekend is niet leeg). Verandert de staat ter plaatse;
    geeft (besluiten, telling)."""
    ontvangers = ONTVANGERS if ontvangers is None else ontvangers
    aan = DOORGEVEN if aan is None else aan
    zet = zet or ag.klaarzet
    lees = lees or (lambda uniek: bord.call("/api/klaarzet?" + urllib.parse.urlencode({"uniek": uniek, "status": "alle"}))
                    .get("items") or [])
    pak = pak or (lambda kid: bord.opgepakt(kid, NAAM))
    nu_s = nu.astimezone(timezone.utc).isoformat(timespec="seconds")
    grens = (nu - timedelta(days=STIL_DAGEN)).astimezone(timezone.utc).isoformat(timespec="seconds")
    telling = Counter()
    taken = staat.get("taken", {})
    for t in list(taken.values()) + list(staat.get("afgerond") or []):
        weg = t.get("doorgegeven")
        if not weg or weg.get("status") in ("opgepakt", "ingetrokken"):
            continue
        open_ = taken.get(t.get("id")) is t
        nog_voor = open_ and t.get("voor") == "agent" and agent_naam(t.get("wie"), agents) == weg["naar"]
        try:
            terug = lees(weg["uniek"])
            if any(x.get("status") == "opgepakt" for x in terug):
                weg["status"] = "opgepakt"
                telling["opgepakt_door_agent"] += 1
                continue
            klaar = [x for x in terug if x.get("status") == "klaar"]
            if klaar and nog_voor and weg.get("ts", "") > grens:
                continue                                 # ligt nog klaar, binnen de termijn
            for x in klaar:
                pak(x["id"])
        except Exception:  # noqa: BLE001  bord onbekend: volgende ronde opnieuw
            telling["niet_gelezen"] += 1
            continue
        if not nog_voor:                                 # afgerond of niet meer voor die agent: alleen terugnemen
            if open_:
                del t["doorgegeven"]
            else:
                weg["status"] = "ingetrokken"
            telling["ingetrokken"] += 1
            continue
        t.update(voor="mehdi", wie="", bijgewerkt=nu_s,
                 waarom=(f"{weg['naar']} pakte ze niet op binnen {STIL_DAGEN} dagen. " + str(t.get("waarom") or ""))[:300])
        t["teruggekomen"] = sorted(set(t.get("teruggekomen") or []) | {weg["naar"]})
        del t["doorgegeven"]
        telling["terug_naar_mehdi"] += 1
    besluiten = doorgeef_besluiten(staat, agents, ontvangers, aan)
    nieuw = []
    for b in besluiten if aan else []:
        t = staat["taken"].get(b["id"]) if b["naar"] else None
        if t:
            nieuw.append({"voor": b["naar"], "soort": "taak", "sleutel": t["id"], "uniek": f"{NAAM}:taak:{t['id']}",
                          "titel": f"Voorstel van Ai Angel, taak {t['id']}",
                          "inhoud": json.dumps({"voorstel": True, "wat": ontvangers[b["naar"]], "taak": t["tekst"],
                                                "waarom": t.get("waarom", ""), "bron": t.get("bron", ""),
                                                "dag": t.get("dag", ""), "concept": t.get("concept", "")},
                                               ensure_ascii=False)})
    if nieuw:
        try:
            zet(nieuw)
            for it in ag.maskeer(nieuw):
                if any(x.get("inhoud") == it["inhoud"] and x.get("voor") == it["voor"] for x in lees(it["uniek"])):
                    staat["taken"][it["sleutel"]]["doorgegeven"] = {"naar": it["voor"], "uniek": it["uniek"], "ts": nu_s}
                    telling["doorgegeven"] += 1
                else:
                    telling["niet_gezet"] += 1
        except Exception:  # noqa: BLE001  de taak blijft bij Mehdi in de lijst; de volgende ronde probeert opnieuw
            telling["niet_gezet"] += len(nieuw) - telling["doorgegeven"]
    return besluiten, telling


# ------------------------------------------------------------------------------------------------- werk ---
def werkverslag(m, bundels, telling, staat, meta, overgeslagen=False):
    """Alleen aantallen, nooit een naam of inhoud."""
    open_ = open_taken(staat)
    per = Counter(t.get("voor") for t in open_)
    dagen = ", ".join(b["dag"] for b in bundels) or "geen"
    if overgeslagen:
        return f"{m}: niets nieuw in de dagbundel ({dagen}); {len(open_)} taken open"
    doorgegeven = (f"; {telling.get('doorgegeven', 0)} doorgegeven, {telling.get('terug_naar_mehdi', 0)} terug naar Mehdi"
                   if telling.get("doorgegeven") or telling.get("terug_naar_mehdi") else "")
    return (f"{m}: dagbundel {dagen}; {telling.get('nieuw', 0)} nieuw, {telling.get('bijgewerkt', 0)} bijgewerkt, "
            f"{telling.get('gedaan', 0)} gedaan, {telling.get('vervallen', 0)} vervallen, {telling.get('zonder_bron', 0)} "
            f"zonder bron geweigerd, {telling.get('onbekend_wie', 0)} naar Mehdi omdat de ontvanger onbekend was; "
            f"{len(open_)} open ({per.get('mehdi', 0)} voor Mehdi, {per.get('collega', 0)} voor een collega, "
            f"{per.get('agent', 0)} voor een agent){doorgegeven}; "
            f"{meta.get('tokens_in', 0) + meta.get('tokens_uit', 0)} tokens")


def werk(r, nu=None, map_=None, gezegd=None, kern=None, claude=None, zet=None, lees=None, staatpad=None, kies_moment=None,
         bewaar=True, doorgeef=None):
    nooit, mehdi_beslist = bord.grenzen(r.werkwijze)
    if not nooit or not mehdi_beslist:
        # N2: zonder grenzen geen werk. De vaste vorm staat in bord.grenzen.
        r.nood("Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist", wie="mehdi")
        r.detail = "geen werk gedaan, grenzen ontbreken in de werkwijze"
        return None
    nu = nu or datetime.now(timezone.utc)
    staat = laad_staat(staatpad)
    vandaag = brussel(nu).date()
    bundels = lees_bundels(dagen_terug(nu), map_)
    r.bron("dagbundel", "; ".join(f"{b['dag']}: {len(b['dagbestand'])} tekens, "
                                  f"{hashlib.sha256(b['dagbestand'].encode()).hexdigest()[:8]}" for b in bundels) or "geen")
    if not bundels:
        # Onbekend is niet leeg: zonder bundel geen lijst, want een lege lijst zou zeggen dat er niets te doen is.
        r.nood("Geen dagbundel gevonden van vandaag of de twee dagen ervoor", wie="claude-code")
        r.detail = "geen dagbundel, niets klaargezet"
        return None
    if bundels[0]["dag"] < (vandaag - timedelta(days=1)).isoformat():
        r.nood("Dagbundel van gisteren ontbreekt", wie="claude-code")
    gezegd_lijst = (gezegd or wat_mehdi_zei)(nu)
    if gezegd_lijst is None:
        r.nood("Wat Mehdi tegen mij zei is niet leesbaar op het bord", wie="claude-code")
        gezegd_lijst = []
    kern_lijst = (kern or collegas_kern)()
    if kern_lijst is None:
        r.nood("Collega's uit kern niet leesbaar", wie="claude-code")
        kern_lijst = []
    m = kies_moment or moment(nu, staat)
    vinger = vingerafdruk(bundels, gezegd_lijst)
    if m == "tussendoor" and vinger == staat.get("vingerafdruk"):
        ag.log("ronde", "melding", "overgeslagen: niets nieuw in de dagbundel")   # anders alleen een hartslag (ANGEL-10)
        r.detail = werkverslag(m, bundels, Counter(), staat, {}, overgeslagen=True)
        return staat
    inhoud = invoer(nu, m, bundels, staat, gezegd_lijst, kern_lijst)
    uit, meta, telling, ontbreekt = None, {}, Counter(), []
    try:
        uit, meta = (claude or vraag_claude)(systeem(r.werkwijze, r.collegas, r.lessen), inhoud)
    except Weigering as e:
        ag.log("claude", "fout", str(e)[:200])
        r.nood("Claude weigerde de takenlijst te maken", wie="claude-code")
    except claude_abonnement.Fout as e:  # het abonnement (ANGEL-3): wacht tot het weer kan, zonder extra verbruik
        if e.soort:                      # een vaste tekst van de koppeling: mag in het werkverslag
            ag.log("claude", "fout", f"abonnement, {e.soort}: {str(e)[:200]}")
        else:                            # kan een stuk antwoord dragen: alleen in het cronlog op de VM, nooit op het bord
            ag.log("claude", "fout", "abonnement: geen bruikbaar antwoord (de reden staat in het cronlog)")
            print(f"abonnement: {str(e)[:300]}", file=sys.stderr)
        tekst, wie = {"aanmelden": (claude_abonnement.AANMELDEN_NOOD, "mehdi"),
                      "limiet": (claude_abonnement.LIMIET_NOOD, "mehdi"),
                      "bron": (claude_abonnement.BRON_NOOD, "claude-code")}.get(
                          e.soort, ("Claude niet bereikbaar voor de takenlijst", "claude-code"))
        r.nood(tekst, wie=wie)
    except Exception as e:  # noqa: BLE001  netwerk, sleutel, limiet, onleesbaar antwoord: de lijst van gisteren blijft
        ag.log("claude", "fout", f"{type(e).__name__}: {str(e)[:200]}")
        r.nood("Claude niet bereikbaar voor de takenlijst", wie="claude-code")
    if uit is not None:
        staat, telling, ontbreekt = verwerk(uit, staat, bundels, gezegd_lijst, kern_lijst, r.collegas, nu)
        staat["vingerafdruk"] = vinger
        if m in ("ochtend", "avond"):
            staat[m] = vandaag.isoformat()
        if ontbreekt:
            # alleen het aantal: de tekst kan een naam dragen, en die hoort niet in het werkverslag (werkwijze, nooit)
            ag.log("dagbundel", "bron", f"{len(ontbreekt)} punten gemist in de dagbundel; ze staan onderaan de takenlijst")
    _, door = (doorgeef or doorgeven)(staat, nu, r.collegas)       # De Doorgever (ANGEL-9); met de vlag uit zet hij niets
    telling.update(door)
    if door.get("niet_gelezen") or door.get("niet_gezet"):
        r.nood("Een doorgegeven taak staat niet zo op het bord", wie="claude-code")
    te_zetten, nummers = items(staat, nu, m, uit, ontbreekt)
    antwoord, fout = klaarzetten(te_zetten, nu, zet=zet, lees=lees)
    if fout:
        r.nood("Een item van de takenlijst staat niet zo op het bord", wie="claude-code")
    staat["nummers"] = nummers
    staat["laatste_ronde"] = nu.astimezone(timezone.utc).isoformat(timespec="seconds")
    if bewaar:
        bewaar_staat(staat, staatpad)
    ag.log("ronde", "melding", f"klaargezet: {antwoord.get('nieuw', 0)} nieuw, {antwoord.get('bijgewerkt', 0)} bijgewerkt")
    r.detail = werkverslag(m, bundels, telling, staat, meta)
    return staat


# ------------------------------------------------------------------------------------------------ droog ---
def droog(argv):
    """Geen ronde: geen hartslag, kennis, klaarzet of staat. Toont wat ik zou klaarzetten. Met --stil alleen aantallen,
    voor een logboek dat anderen kunnen zien (GitHub Actions)."""
    stil = "--stil" in argv

    class Droog:
        werkwijze, detail, lessen = "", "", []
        collegas = []

        def nood(self, tekst, wie="mehdi"):
            print(f"(droog) nood voor {wie}: {tekst}")

        def bron(self, naam, inhoud):
            pass

    d = Droog()
    pad = argv[argv.index("--werkwijze") + 1] if "--werkwijze" in argv else (
        os.path.join(HIER, "werkwijze", f"{NAAM}.md") if "--zaad" in argv else None)
    try:
        d.werkwijze = _lees(pad) if pad else ag.werkwijze_lezen()
    except bord.RondeGestopt as e:
        print(f"(droog) werkwijze niet gelezen: {e}")
        return 1
    if not d.werkwijze:
        print(f"(droog) werkwijze niet gelezen: {pad}")
        return 1
    d.collegas = bord.collegas(zonder=NAAM)
    try:
        d.lessen = json.loads(_lees(os.path.join(HIER, "werkwijze", "lessen.json")) or "{}").get("lessen") or []
    except ValueError:
        d.lessen = []
    m = argv[argv.index("--moment") + 1] if "--moment" in argv else None
    gezet = []

    def zet(its):
        gezet.extend(its)
        return {"nieuw": len(its)}

    besluiten = {}

    def doorgeef(staat, nu, agents):
        # droog: niets doorgeven of terugnemen, alleen zeggen wat er zou gebeuren (ANGEL-9)
        besluiten.update({b["id"]: b["besluit"] for b in doorgeef_besluiten(staat, agents)})
        return [], Counter()

    staat = werk(d, zet=zet, lees=lambda uniek: [x for x in ag.maskeer(gezet) if x["uniek"] == uniek],
                 kies_moment=m, bewaar=False, doorgeef=doorgeef)

    def besluit(t):
        if t["id"] in besluiten:
            return besluiten[t["id"]]
        if t.get("doorgegeven"):
            return f"al doorgegeven aan {t['doorgegeven']['naar']}"
        return "blijft bij Mehdi: " + ("voor een collega, Mehdi stuurt het zelf" if t.get("voor") == "collega"
                                       else "eigen taak")

    if staat is None:
        print(f"(droog) {d.detail}")
        return 1
    volledig = "\n\n".join(f"=== {it['soort']}: {it['titel']}\n{it['inhoud']}" for it in gezet)
    if "--uit" in argv:
        # het volledige resultaat, met namen, alleen in een bestand voor beheer (600), nooit in het logboek
        pad = argv[argv.index("--uit") + 1]
        os.makedirs(os.path.dirname(os.path.abspath(pad)), exist_ok=True)
        fd = os.open(pad, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(volledig + "\n")
        print(f"(droog) volledig resultaat in {pad}")
    if stil:
        # de vorm zonder inhoud: per taak voor wie, prioriteit, het eerste woord en of er een concept bij is
        print(f"(droog) {len(gezet)} items, titels: " + "; ".join(it["titel"] for it in gezet))
        for nr, tid in sorted(staat.get("nummers", {}).items(), key=lambda x: int(x[0])):
            t = staat["taken"][tid]
            print(f"(droog) {nr}. {t['voor']}, {t['prioriteit']}, begint met '{t['tekst'].split()[0]}', "
                  f"concept {'ja' if t.get('concept') else 'nee'}, bron {len(t.get('bron', ''))} tekens, {besluit(t)}")
    else:
        print(volledig)
        for nr, tid in sorted(staat.get("nummers", {}).items(), key=lambda x: int(x[0])):
            print(f"(droog) doorgeven {nr}: {besluit(staat['taken'][tid])}")
    print(f"(droog) {d.detail}")
    return 0


if __name__ == "__main__":
    if "--droog" in sys.argv:
        sys.exit(droog(sys.argv))
    if "--nu" not in sys.argv and not aan_de_beurt():
        sys.exit(0)                    # niet mijn uur: geen ronde, geen hartslag (de cron draait elk uur)
    with ag.ronde("taken klaarzetten") as r:
        werk(r)
