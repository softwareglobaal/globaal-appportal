"""Per wacht wat er op een dag binnenkwam (Mehdi, 01-11-2026: "ik wil alle wachten zien, zodat ik weet per wacht wat
binnengekomen is en dat ik het kan controleren ... ik wil het als mens zien en begrijpen dat het werkt").

Alleen lezen uit de databank van het bord. Per wacht uit de groep Dagbundelaar: hoeveel items, de items zelf (tijd, van
wie of wat, kort), de rondes van die dag uit het werkverslag, en of er een fout was. Een wacht die die dag niets meldde,
staat als "niets binnen", nooit als nul. Nooit de tekst van een bericht: de wachten bewaren die ook niet.
"""
import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

import privegrens

BRUSSEL = ZoneInfo("Europe/Brussels")
# Mehdi leest de wacht per dag in het Dagboek: niets wegkappen wat hij daar wil zien (Codex 01-11). Een dag heeft hoogstens
# enkele honderden rondes (de Fotowacht 435 op 30-10).
MAX_ITEMS = 2000
MAX_LOG = 1000                          # regels per blad van het werkverslag (T-0120 AG-9: 23-10 had er 4.445)
KORT = 160
# Welke wacht schrijft welke bron in de gesprekkentabel (gesprek_log.bron).
GESPREK_BRON = {"whatsapp-wacht": "whatsapp", "belwacht": "telefoon", "sms-wacht": "sms", "xelion-wacht": "xelion",
                "fathom-wacht": "fathom", "plaud-wacht": "plaud", "zoom-wacht": "zoom"}
MAIL_WACHTEN = ("mail-prive", "mail-mch", "mail-info-harc", "mail-hinv", "mail-melo")
# De bronnen in de dagregel van De Zoomwacht (zoom_wacht.dag_inhoud: ZOOM_BRONNEN, de twee van Fathom en de chat)
ZOOM_DAG_BRONNEN = ("rapport", "vaste vergaderruimte", "gepland", "opnames", "laatste sessie", "fathom-archief",
                    "fathom-api", "chat")
# T-0120 AG-2: van een signaal of dagplan van deze wachten ook de regels van de inhoud, niet alleen de titel (welke
# afspraak, welke boeking). Hun inhoud is bij het klaarzetten gemaskeerd zoals op het bord (bord.Agent.maskeer geeft
# '(privé)'); ik toon ze zoals ze daar staan. Andere wachten niet: nooit de tekst van een bericht.
REGELS_VAN = ("agenda-wacht", "calendly-wacht")
MAX_REGELS = 200

# T-0120 VOL-19 en DB-5 (groep pagina): elke link op de wachtenpagina loopt via een route van het Dagboek achter
# Authentik, nooit rechtstreeks naar een gedeelde Dropbox-link of een andere site. Een item draagt daarom alleen wat
# voor link het is ({"soort": dag | fotos | fathom | transcript | bord, ...}); het Dagboek maakt er zijn eigen route van.
# Nooit een link bij een privé-item, en nooit bij de berichten en oproepen van de Mac en Xelion.
GEEN_LINK = ("whatsapp-wacht", "sms-wacht", "belwacht", "xelion-wacht")
# FATHOM-3: gesprek_log.link bij Fathom is de deellink of de gewone url van fathom.video; iets anders is geen link.
FATHOM_LINK = re.compile(r"https://fathom\.video/[A-Za-z0-9/_.~%?=&+-]{1,400}")
# De dagbestanden van De Dagbundelaar en de dag van De Communicatiebundelaar staan op /dag/<dag> in het Dagboek.
DAG_LINK = {"dagbundelaar": ("dagvaststelling", "dagbundel"), "communicatie-bundelaar": ("communicatie",)}
DAG_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
# Oude foto-items (van voor de indeling van FOTO-5) hadden coördinaten in de titel; ook privéfoto's (FOTO-8: privé en
# mensen alleen een telling zonder plaats). Op de pagina komt er geen plaats meer van.
COORD_RE = re.compile(r"-?\d{1,3}\.\d{3,}\s*,\s*-?\d{1,3}\.\d{3,}")
# ANGEL-6: de takenlijst van Ai Angel (mehdi_agent.lijst: 'N. tekst (prioriteit)' met ingesprongen Waarom/Bron/Concept)
ANGEL_STAAT = os.environ.get("WACHTEN_ANGEL_STAAT", "/data/mehdi-agent/staat.json")
ANGEL_MAX = 12
ANGEL_BORD = "/agent/mehdi-agent"
TAAK_RE = re.compile(r"(\d{1,3})\.\s+(.+)")
PRIVE_RE = re.compile(r"priv[eé]", re.I)            # zoals mehdi_agent.PRIVE
# ARCH-2 (contract van de groep zoom): het overzicht van De Zoomarchivaris, op het bord alleen lezend
ZOOM_ARCHIEF = os.environ.get("WACHTEN_ZOOM_ARCHIEF", "/data/zoom-archief/wachten.json")
ZOOM_MAP_RE = re.compile(r"Zoom/\d{4}-\d{2}-\d{2} \d{4}")
MAX_TRANSCRIPT = 5000                               # uitingen op de transcriptpagina


def grenzen(dag):
    """De Brusselse dag als UTC-tekst [van, tot), zoals de ts in de databank staat (isoformat in UTC)."""
    d = date.fromisoformat(dag)
    van = datetime.combine(d, time(0), BRUSSEL).astimezone(timezone.utc)
    tot = datetime.combine(d + timedelta(days=1), time(0), BRUSSEL).astimezone(timezone.utc)
    return van.isoformat(), tot.isoformat()


def uur(waarde):
    """Een tijdstip uit de databank als HH:MM in Brussel; een losse HH:MM blijft staan; onleesbaar is leeg."""
    t = str(waarde or "").strip()
    if not t:
        return ""
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t):
        return t[:5].rjust(5, "0")
    try:
        x = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        try:
            x = parsedate_to_datetime(t)
        except (TypeError, ValueError, IndexError):
            return ""
    if x.tzinfo is None:
        return x.strftime("%H:%M")
    return x.astimezone(BRUSSEL).strftime("%H:%M")


def kort(tekst, n=KORT):
    t = re.sub(r"\s+", " ", str(tekst or "")).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


# De slotregel van een ronde in het werkverslag (De Plaudwacht: ag.log("Plaud", "bron", "ronde: ...")); PLAUD-8.
RONDE_REGEL = "ronde:"


# PLAUD-7 (T-0120): De Plaudwacht zet alleen een opname met transcript in de gesprekkentabel; de opnames zonder transcript
# waren hier onzichtbaar (oktober: 6), en of de audio er was, stond nergens (oktober: 5 zonder). Het bord heeft
# mijnagents-data op /data; daar zet de Mac het manifest (plaud/plaud_invoer_push.sh). Alleen tijd, duur en toestand,
# nooit de naam in Plaud of een pad. Een eigen naam voor de variabele: PLAUD_INVOER van de runner is een pad op de VM.
PLAUD_INVOER = os.environ.get("WACHTEN_PLAUD_INVOER", "/data/plaud-invoer")
PLAUD_KORT_MINUTEN = 1                          # zoals KORT_MINUTEN in plaud/manifest.py (PLAUD-9)


def _duur(minuten):
    try:
        m = float(minuten)
    except (TypeError, ValueError):
        return "duur onbekend"
    return f"{round(m * 60)} s" if m < 1 else f"{int(m)} min"


def _kort_wachtend(o):
    try:
        return o.get("toestand") == "wacht_op_transcript" and float(o.get("duur_minuten")) < PLAUD_KORT_MINUTEN
    except (TypeError, ValueError):
        return False


def lees_plaud(conn, dag):
    """(items, stand) van De Plaudwacht uit het manifest van de Mac. items: de opnames van die dag zonder rij in de
    gesprekkentabel; een opname met een rij staat er al, met de privéregel (is_prive_gesprek). stand: de telling van die
    dag, of None als het manifest niet te lezen is (onbekend, nooit 0).

    Contract voor een link (VOL-19: één route achter Authentik, de weergave doet de groep pagina): het Dagboek vraagt het
    bord om het transcript van plaud:<id>, en het bord leest /data/plaud-invoer/<archief.map>/transcript.json. Nooit bij
    een privégesprek, nooit een Dropboxpad of gedeelde link. De audio staat alleen op de Mac: geen audiolink, wel de
    telling zonder_audio."""
    try:
        with open(os.path.join(PLAUD_INVOER, "00 manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        opnames = [o for o in m["opnames"] if isinstance(o, dict) and str(o.get("start_brussel") or "")[:10] == dag]
        gemaakt = str((m.get("meta") or {}).get("gemaakt") or "")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return [], None
    # Codex-toets 1: een manifest van voor die dag kent die dag niet; dat is onbekend, geen nul. Van tijdens de dag
    # (vandaag) is de telling nog niet af: na_de_dag zegt het.
    van, tot = (datetime.fromisoformat(x) for x in grenzen(dag))
    try:
        gemaakt_t = datetime.fromisoformat(gemaakt.replace("Z", "+00:00"))
        gemaakt_t = gemaakt_t if gemaakt_t.tzinfo else gemaakt_t.replace(tzinfo=timezone.utc)
    except ValueError:
        return [], None
    if gemaakt_t < van:
        return [], None
    unieken = [f"plaud:{o.get('plaud_id')}" for o in opnames]
    in_tabel = {r["uniek"] for r in conn.execute(
        f"SELECT uniek FROM gesprek_log WHERE bron='plaud' AND uniek IN ({','.join('?' * len(unieken))})", unieken)} \
        if unieken else set()
    items = []
    for o in opnames:
        if f"plaud:{o.get('plaud_id')}" in in_tabel:
            continue
        toestand = o.get("toestand")
        zonder_audio = (o.get("audio") or {}).get("staat") == "ontbreekt"
        if toestand == "wacht_op_transcript":
            wat = "kort, na te kijken" if _kort_wachtend(o) else "wacht op transcript"
        elif toestand == "onvolledig":
            wat = "onvolledig, audio ontbreekt" if zonder_audio else "onvolledig"
        elif toestand == "compleet":
            wat = "transcript binnen, nog niet verwerkt"
        elif toestand == "conflict":
            wat = "staat in meer dan één map, Mehdi kiest"
        else:
            wat = str(toestand or "toestand onbekend")
        items.append(_item(uur(o.get("start_brussel")), "Plaud-opname", f"{_duur(o.get('duur_minuten'))}, {wat}"))
    stand = {"opnames": len(opnames), "in_tabel": len(in_tabel),
             "wacht_op_transcript": sum(1 for o in opnames if o.get("toestand") == "wacht_op_transcript"),
             "kort": sum(1 for o in opnames if _kort_wachtend(o)),
             "onvolledig": sum(1 for o in opnames if o.get("toestand") == "onvolledig"),
             "zonder_audio": sum(1 for o in opnames if (o.get("audio") or {}).get("staat") == "ontbreekt"),
             "manifest_van": gemaakt, "na_de_dag": gemaakt_t >= tot}
    return items, stand


def plaud_mappen():
    """{plaud_id: archief.map} uit het manifest van de Mac; leeg als het niet te lezen is."""
    try:
        with open(os.path.join(PLAUD_INVOER, "00 manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        return {str(o.get("plaud_id")): str((o.get("archief") or {}).get("map") or "") for o in m["opnames"]
                if isinstance(o, dict) and isinstance(o.get("archief"), dict) and (o.get("archief") or {}).get("map")}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def plaud_transcript_pad(r, mappen=None):
    """PLAUD-7 (contract van de groep plaud): waar het transcript van een Plaud-rij op het bord staat,
    /data/plaud-invoer/<archief.map>/transcript.json, of leeg. De map komt uit het manifest (op plaud_id), anders uit
    gesprek_log.archief ('Data uit Mehdi/Plaud/<map>/transcript.md', een pad in Dropbox: dat wordt nooit een link).
    Alleen een map direct onder de invoer; een naam met een schuine streep of '..' telt niet."""
    uniek = str(privegrens._veld(r, "uniek") or "")
    if not uniek.startswith("plaud:"):
        return ""
    map_ = (mappen if mappen is not None else plaud_mappen()).get(uniek[len("plaud:"):], "")
    if not map_:
        m = re.fullmatch(r"Data uit Mehdi/Plaud/([^/]+)/transcript\.(?:md|json)", str(privegrens._veld(r, "archief") or ""))
        map_ = m.group(1) if m else ""
    if not map_ or "/" in map_ or "\\" in map_ or "\x00" in map_ or map_.strip(".") == "":
        return ""
    basis = os.path.realpath(PLAUD_INVOER)
    pad = os.path.realpath(os.path.join(basis, map_, "transcript.json"))
    return pad if os.path.dirname(os.path.dirname(pad)) == basis and os.path.isfile(pad) else ""


def _klok(ms):
    """Milliseconden in de opname als UU:MM:SS (zoals plaud/archief._klok)."""
    try:
        s = int(float(ms or 0)) // 1000
    except (TypeError, ValueError):
        return ""
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def gesprek_open(conn, uniek, wat):
    """T-0120 VOL-19: wat het Dagboek achter zijn eigen route (Authentik) van één gesprek mag openen, of None.
    wat 'fathom': {'link'}, de link van de rij (FATHOM-3: de deellink bij een werkgesprek), alleen naar fathom.video.
    wat 'transcript': de uitingen van een Plaud-opname uit transcript.json (PLAUD-7), met wanneer en met wie.
    Nooit bij een privégesprek (is_prive_gesprek), nooit bij een andere bron (WhatsApp, sms, telefoon, Xelion hebben
    geen link), nooit een pad of een Dropbox-link. Er is geen audiolink: de audio staat alleen op de Mac."""
    r = conn.execute("SELECT * FROM gesprek_log WHERE uniek=?", (str(uniek or ""),)).fetchone()
    if r is None:
        return None
    r = _gesprek_rij(r)
    if is_prive_gesprek(r):
        return None
    bron = privegrens.bron(r)
    if wat == "fathom" and bron == "fathom" and FATHOM_LINK.fullmatch(r["link"] or ""):
        return {"uniek": r["uniek"], "link": r["link"]}
    if wat != "transcript" or bron != "plaud":
        return None
    pad = plaud_transcript_pad(r)
    if not pad:
        return None
    try:
        with open(pad, encoding="utf-8") as f:
            uitingen = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(uitingen, list):
        return None
    regels = [{"tijd": _klok(u.get("start_time")), "wie": kort(u.get("speaker") or "spreker onbekend", 80),
               "tekst": str(u.get("content") or "").strip()} for u in uitingen if isinstance(u, dict)]
    return {"uniek": r["uniek"], "dag": r["datum"], "tijd": uur(r["start"]), "minuten": r["minuten"],
            "wie": kort(r["personen"] or "onbekend", 120), "thema": kort(r["thema"], 200),
            "regels": regels[:MAX_TRANSCRIPT], "meer": max(0, len(regels) - MAX_TRANSCRIPT)}


def _hhmm(x):
    t = str(x or "")
    return t if re.fullmatch(r"[0-2]\d:[0-5]\d", t) else ""


def _mb(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return "grootte onbekend"
    return f"{v:.1f} MB".replace(".", ",")


def lees_zoom_archief(dag):
    """ARCH-2 (contract van de groep zoom): (items, stand) van De Zoomarchivaris uit zoom-archief/wachten.json. Per
    Brusselse dag van de kopie elk bewezen bestand: uur van het gesprek, soort, MB en 'bewezen in je Dropbox, map
    Zoom/<datum uur>'; verdwenen gevallen apart, als fout. Nooit een onderwerp, id, pad of link: het overzicht heeft ze
    niet, en een map die niet de vorm Zoom/<datum uur> heeft, wordt 'Zoom'. stand None: het overzicht ontbreekt, is
    onleesbaar of van voor die dag (onbekend, nooit 0); na_de_dag: de telling van die dag is af."""
    try:
        with open(ZOOM_ARCHIEF, encoding="utf-8") as f:
            d = json.load(f)
        dagen = d["dagen"]
        moment = datetime.fromisoformat(str(d.get("ts") or "").replace("Z", "+00:00"))
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return [], None
    moment = moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)
    van, tot = (datetime.fromisoformat(x) for x in grenzen(dag))
    if not isinstance(dagen, dict) or moment < van:
        return [], None
    x = dagen.get(dag) if isinstance(dagen.get(dag), dict) else {}
    gek = [f for f in x.get("gekopieerd") or [] if isinstance(f, dict)]
    weg = [f for f in x.get("verdwenen") or [] if isinstance(f, dict)]
    items = []
    for f in gek:
        kaart = str(f.get("map") or "")
        kaart = kaart if ZOOM_MAP_RE.fullmatch(kaart) else "Zoom"
        soort = re.sub(r"[^a-z0-9 ()-]", "", str(f.get("soort") or "").lower())[:40] or "bestand"
        items.append(_item(_hhmm(f.get("uur")), soort, f"{_mb(f.get('mb'))}, bewezen in je Dropbox, map {kaart}"))
    for f in weg:
        items.append(_item(_hhmm(f.get("uur")), "verdwenen in Zoom", f"{_mb(f.get('mb'))}, niet gekopieerd", fout=True))
    return items, {"gekopieerd": len(gek), "verdwenen": len(weg), "overzicht_van": moment.isoformat(),
                   "na_de_dag": moment >= tot}


def _json(tekst):
    try:
        x = json.loads(tekst or "")
    except (TypeError, ValueError):
        return None
    return x


def _telling_tekst(t):
    """Een telling (dict) als korte regel: 'dictaten 12, woorden 840'. Lijsten en dieper blijven weg."""
    if not isinstance(t, dict):
        return kort(t)
    delen = [f"{k.replace('_', ' ')} {v}" for k, v in t.items() if isinstance(v, (int, float, str)) and str(v) != ""]
    return kort(", ".join(delen))


def _item(tijd, wie, wat, fout=False):
    return {"tijd": tijd, "wie": kort(wie, 80), "wat": kort(wat), "fout": bool(fout)}


def is_prive_gesprek(r):
    """De privéregel van de gesprekkentabel, dezelfde als bij De Dagbundelaar en De Communicatiebundelaar
    (privegrens.py, T-0120 VOL-2): de vlag prive of afdeling privé. De bewuste uitzondering: bij een Mac-kanaal
    (WhatsApp, telefoon, sms, Xelion) betekent prive=1 alleen "van de Mac van Mehdi, alleen voor Mehdi"; die rijen
    dragen naam en aantal, nooit tekst, en deze pagina is alleen voor Mehdi: die blijven leesbaar. Tot 01-11-2026 keek
    ik alleen naar de afdeling, en toonde ik van een Zoom-, Fathom- of Plaud-rij met prive=1 en afdeling onbekend naam
    en onderwerp (DB-8). De vlag geldt ook bij een andere afdeling: in oktober 2 Fathom-gesprekken met de vlag en een
    andere afdeling (FATHOM-3)."""
    return privegrens.is_prive(r, voor_mehdi=True)


def dubbel_tekst(dubbel_van, thema=""):
    """TEL-4 (WA-7): wat dubbel_van zegt, in woorden. Een gemiste of niet beantwoorde oproep (buiten:gemist) is geen
    dubbel: hij telt niet als gesprek. Een rij die de bron niet meer toont, is vervallen. Alleen een verwijzing naar een
    andere rij is een echte dubbel."""
    d = str(dubbel_van or "")
    if not d:
        return ""
    if d == "buiten:gemist":
        return ("" if re.search(r"gemist|niet beantwoord", str(thema or "")) else "gemist, ") + "telt niet als gesprek"
    if d == "buiten:vervallen":
        return "niet meer in de bron"
    return "dubbel, telt niet"


GESPREK_STANDAARD = (("dubbel_van", ""), ("afdeling", ""), ("prive", 0), ("link", ""), ("archief", ""), ("thema", ""),
                     ("personen", ""), ("start", ""), ("minuten", None), ("bron", ""), ("uniek", ""), ("datum", ""))


def _gesprek_rij(r):
    """Een rij van gesprek_log als dict, met de kolommen die deze pagina leest; NULL of ontbrekend wordt de standaard
    (zoals de COALESCE van voordien)."""
    d = dict(r)
    for k, standaard in GESPREK_STANDAARD:
        if d.get(k) is None:
            d[k] = standaard
    return d


def gesprek_link(r, mappen=None):
    """VOL-19: de link van een gesprek dat niet privé is, als soort (het Dagboek maakt er zijn route van), of None.
    Fathom: 'open in Fathom' als de rij een link van fathom.video heeft (FATHOM-3). Plaud: 'transcript lezen' als het
    transcript op het bord staat (PLAUD-7). Andere bronnen geen link."""
    b = privegrens.bron(r)
    if b == "fathom" and FATHOM_LINK.fullmatch(str(privegrens._veld(r, "link") or "")):
        return {"soort": "fathom", "uniek": r["uniek"], "tekst": "open in Fathom"}
    if b == "plaud" and plaud_transcript_pad(r, mappen):
        return {"soort": "transcript", "uniek": r["uniek"], "tekst": "transcript lezen"}
    return None


def lees_gesprekken(conn, bron, dag):
    # SELECT *: link en archief (VOL-19) en de andere kolommen met hun standaard, ook bij een oudere tabel zonder ze
    rijen = [_gesprek_rij(r) for r in conn.execute("SELECT * FROM gesprek_log WHERE datum=? AND bron IN (?, 'dekking') "
                                                   "ORDER BY start", (dag, bron)).fetchall()]
    items, gedekt = [], False
    mappen = plaud_mappen() if bron == "plaud" else {}
    for r in rijen:
        if r["bron"] == "dekking":
            # een vervallen dekkingsrij (de bron toont de dag niet meer) bewijst niets (Codex V1, TEL-8)
            if str(r["uniek"] or "").startswith(f"dekking:{bron}:") and r["dubbel_van"] != "buiten:vervallen":
                gedekt = True
            continue
        if is_prive_gesprek(r):
            # RZ2-01: van een privégesprek alleen "privégesprek, N min", zonder naam of onderwerp.
            wat = ", ".join(x for x in (f"{r['minuten']} min" if r["minuten"] else "",
                                        dubbel_tekst(r["dubbel_van"])) if x)
            items.append(_item(uur(r["start"]), "privégesprek", wat))
            continue
        wat = ", ".join(x for x in (f"{r['minuten']} min" if r["minuten"] else "", kort(r["thema"], 100),
                                    dubbel_tekst(r["dubbel_van"], r["thema"])) if x)
        it = _item(uur(r["start"]), r["personen"] or "onbekend", wat)
        link = gesprek_link(r, mappen) if bron in ("fathom", "plaud") else None
        if link:
            it["link"] = link
        items.append(it)
    return items, gedekt


# MAIL-6 (T-0120): per mail of ze opgevolgd is en waar ze heen ging. Het besluit van Mehdi op /mail gaat voor de wacht.
OPVOLGING = {"open": "op te volgen", "onzeker": "nakijken", "wacht": "wacht een werkdag", "verlopen": "verlopen",
             "beantwoord": "beantwoord", "doorgezet": "doorgezet", "verdwenen": "niet meer in het postvak"}


def _map_kort(m):
    return re.sub(r"^INBOX[./]", "", str(m or ""))


def zoom_gedekt(conn, dag):
    """T-0120 WACHT-2: De Zoomwacht schrijft geen dekkingsrij; haar dekking staat in de dagregel zoom:dag:<dag>. Helemaal
    gelezen (True) alleen als die telling volledig is, de stand definitief en elk van de acht bronnen er staat met ok
    (een ontbrekende bron is niet gelezen, Codex); anders nog niet (False). Een dag die nog niet af is (vandaag of
    later), toont niets (None)."""
    if dag >= datetime.now(BRUSSEL).date().isoformat():
        return None
    r = conn.execute("SELECT inhoud FROM klaarzet WHERE van='zoom-wacht' AND uniek=? AND status!='vervallen'",
                     (f"zoom:dag:{dag}",)).fetchone()
    inhoud = _json(r["inhoud"]) if r else None
    bronnen = inhoud.get("bronnen") if isinstance(inhoud, dict) else None
    return bool(isinstance(bronnen, dict) and all(bronnen.get(b) == "ok" for b in ZOOM_DAG_BRONNEN)
                and all(v == "ok" for v in bronnen.values())
                and inhoud.get("telling") == "volledig" and inhoud.get("stand") == "definitief")


def _grootte(n):
    return f"{max(1, round(n / 1024))} kB" if n < 1024 ** 2 else f"{n / 1024 ** 2:.1f} MB".replace(".", ",")


def bijlagen_tekst(aantal, info):
    """VOL-9 (contract van de groep mail): '2 bijlagen (pdf, dwg), 1,3 MB'. Alleen aantal, soort en grootte, zoals de
    wacht ze uit de BODYSTRUCTURE las; nooit een bestandsnaam, er wordt niets gedownload. Bij NULL (onbekend) of 0
    niets, nooit '0 bijlagen'. Een soort die vaker voorkomt, staat een keer met haar aantal ('3 bijlagen (2 pdf, dwg)'),
    in de volgorde van de mail."""
    if not isinstance(aantal, int) or isinstance(aantal, bool) or aantal <= 0:
        return ""
    lijst = _json(info) if isinstance(info, str) else info
    lijst = [x for x in lijst if isinstance(x, dict)][:20] if isinstance(lijst, list) else []
    soorten = {}
    for x in lijst:
        s = re.sub(r"[^a-z0-9-]", "", str(x.get("soort") or "").lower())[:12] or "bestand"
        soorten[s] = soorten.get(s, 0) + 1
    deel = [s if n == 1 else f"{n} {s}" for s, n in soorten.items()]
    if deel and aantal > len(lijst):
        deel[-1] += f" en nog {aantal - len(lijst)}"
    groot = sum(x["bytes"] for x in lijst if isinstance(x.get("bytes"), int) and not isinstance(x.get("bytes"), bool)
                and x["bytes"] > 0)
    return (f"{aantal} bijlage{'n' if aantal != 1 else ''}" + (f" ({', '.join(deel)})" if deel else "")
            + (f", {_grootte(groot)}" if groot else ""))


def lees_mail(conn, wacht, dag):
    # SELECT *: de kolommen bijlagen en bijlagen_info (VOL-9) komen er pas bij met _mail_tabellen; een oudere tabel
    # zonder die kolommen geeft gewoon geen bijlagen, geen leesfout.
    rijen = conn.execute("SELECT * FROM mailbericht WHERE wacht=? AND dag=? ORDER BY datum LIMIT ?",
                         (wacht, dag, MAX_ITEMS)).fetchall()
    items = []
    for r in rijen:
        r = dict(r)
        opv = r.get("besluit") or OPVOLGING.get(r.get("opvolging") or "", "")
        waar = ("naar Opgeruimd" if r.get("opgeruimd") else f"naar {_map_kort(r['naar'])}" if r.get("naar")
                else f"in {_map_kort(r['map'])}" if r.get("map") and r["map"] != "INBOX" else "")
        # de bijlagen direct na het onderwerp: zo vallen ze niet weg als de regel te lang is
        bij = bijlagen_tekst(r.get("bijlagen"), r.get("bijlagen_info"))
        items.append(_item(uur(r.get("datum")), r.get("van_naam") or r.get("van") or "onbekend",
                           " · ".join(x for x in (r.get("onderwerp") or "(geen onderwerp)", bij, r.get("soort") or "",
                                                  opv, waar) if x)))
    return items


def lees_klaarzet(conn, wacht, dag, van, tot, zonder_gesprekken=False):
    """Wat de wacht die dag klaarzette, of wat over die dag gaat (sleutel, uniek of titel met de dag).

    FATHOM-3 (T-0120): bij een gesprekswacht valt een item weg waarvan de uniek als gesprek in de tabel staat; dat
    gesprek staat al op zijn eigen dag, en het item stond er dubbel bij, ook op de dag waarop het klaargezet werd (oktober:
    477 extra regels naast 292 Fathom-gesprekken). Op uniek, dus voor de privémaskering."""
    rijen = conn.execute(
        "SELECT ts, soort, titel, inhoud, uniek, sleutel FROM klaarzet WHERE van=? AND status!='vervallen' AND "
        "((ts>=? AND ts<?) OR sleutel=? OR uniek LIKE ? OR uniek LIKE ? OR titel LIKE ?) "
        + ("AND NOT EXISTS (SELECT 1 FROM gesprek_log g WHERE g.uniek = klaarzet.uniek) " if zonder_gesprekken else "")
        + "ORDER BY ts LIMIT ?",
        (wacht, van, tot, dag, f"%:{dag}", f"%:{dag}:%", f"{dag} %", MAX_ITEMS)).fetchall()
    items = []
    angel_prive = angel_prive_teksten() if wacht == "mehdi-agent" else ()
    for r in rijen:
        inhoud = _json(r["inhoud"])
        wat = r["titel"] or ""
        if isinstance(inhoud, dict):
            pd = inhoud.get("per_dag")
            t = pd.get(dag) if isinstance(pd, dict) else inhoud.get("vandaag")
            if isinstance(t, dict) and t:
                wat = f"{wat}: {_telling_tekst(t)}"
        if wacht == "icloud-wacht":
            wat = foto_zonder_plaats(wat)
        titel = foto_zonder_plaats(r["titel"]) if wacht == "icloud-wacht" else str(r["titel"] or "")
        tijd = uur(r["ts"])
        if titel.startswith(dag + " "):
            # "2026-10-31 20:25-20:56: 22 foto's bij ...": de eerste tijd is de tijd, de rest is wat; een bereik komt erachter.
            wat = titel[len(dag) + 1:]
            m = re.match(r"([01]\d:[0-5]\d|2[0-3]:[0-5]\d)(?:-([01]\d:[0-5]\d|2[0-3]:[0-5]\d))?(?::\s*|\s+|$)", wat)
            if m:
                tijd, wat = m.group(1), wat[m.end():].strip()
                if m.group(2) and m.group(2) != m.group(1):
                    wat = f"{wat} ({m.group(1)} tot {m.group(2)})"
        it = _item(tijd, r["soort"] or "item", wat)
        if wacht in REGELS_VAN and r["soort"] in ("signaal", "dagplan") and inhoud is None and r["inhoud"]:
            it["regels"] = inhoud_regels(r["inhoud"])
        if wacht == "mehdi-agent" and r["soort"] == "taken":
            # ANGEL-6: de genummerde taken, niet alleen de titel; een privétaak alleen 'privé'
            it["regels"] = angel_taken(r["inhoud"], angel_prive)
        link = klaarzet_link(wacht, r, inhoud, dag)
        if link:
            it["link"] = link
        items.append(it)
    return items


def foto_zonder_plaats(tekst):
    """Een foto-item zonder plaats: de coördinaten van een oud item worden 'een plek (plaats niet getoond)'."""
    return COORD_RE.sub("een plek (plaats niet getoond)", str(tekst or ""))


def klaarzet_link(wacht, r, inhoud, dag):
    """VOL-19 en DB-5: de link van een klaargezet item, als soort, of None. Nooit bij een privé-item (inhoud.prive of
    PRIVÉ in de titel) en nooit bij een wacht uit GEEN_LINK.
    - De Dagbundelaar (dagvaststelling, dagbundel) en De Communicatiebundelaar: de dag op /dag/<dag>.
    - De Fotowacht: een werfgroep of kandidaat (FOTO-5) naar de foto's per project op /fotos/<dag>; de telling van wat
      geen werk is, krijgt geen link.
    - Ai Angel: zijn takenlijst en verslag naar zijn pagina op het bord."""
    if wacht in GEEN_LINK or (isinstance(inhoud, dict) and inhoud.get("prive")) or "PRIVÉ" in str(r["titel"] or ""):
        return None
    soort = r["soort"] or ""
    if soort in DAG_LINK.get(wacht, ()):
        m = DAG_RE.search(str(r["uniek"] or "")) or DAG_RE.fullmatch(str(r["sleutel"] or ""))
        return {"soort": "dag", "dag": m.group(0) if m else dag, "tekst": "de dag openen"}
    if wacht == "icloud-wacht" and soort == "foto" and isinstance(inhoud, dict) \
            and inhoud.get("soort") in ("zeker", "kandidaat") and not inhoud.get("vervallen"):
        d = str(inhoud.get("datum") or "")
        return {"soort": "fotos", "dag": d if DAG_RE.fullmatch(d) else dag, "tekst": "foto's per project"}
    if wacht == "mehdi-agent" and soort in ("taken", "verslag"):
        return {"soort": "bord", "pad": ANGEL_BORD, "tekst": "de volledige lijst op het bord"}
    return None


def angel_prive_teksten():
    """De teksten van de privétaken van Ai Angel uit zijn staat (mehdi-agent/staat.json, op het bord /data): ook een
    taak die alleen door haar herkomst privé is (mehdi_agent.bron_prive), zonder het woord privé. Onleesbaar: leeg, dan
    telt alleen het woord."""
    try:
        with open(ANGEL_STAAT, encoding="utf-8") as f:
            staat = json.load(f)
        taken = list((staat.get("taken") or {}).values()) + list(staat.get("afgerond") or [])
    except (OSError, ValueError, AttributeError, TypeError):
        return ()
    return tuple({str(t.get("tekst") or "").strip()[:300] for t in taken
                  if isinstance(t, dict) and t.get("prive") and len(str(t.get("tekst") or "").strip()) >= 4})


def angel_taken(inhoud, prive_teksten=()):
    """ANGEL-6: de genummerde taken uit de takenlijst van Ai Angel, kort en hoogstens ANGEL_MAX, met hun nummer (zo
    noemt Mehdi ze: 'Ai Angel, 2 is gedaan'). Een taak is privé als het woord privé in haar blok staat (tekst, waarom,
    bron, concept, zoals mehdi_agent) of als ze in de staat privé is: dan alleen 'N. privé'."""
    taken, huidig = [], None
    for regel in str(inhoud or "").splitlines():
        m = TAAK_RE.fullmatch(regel.strip()) if not regel.startswith(" ") else None
        if m:
            huidig = {"nr": m.group(1), "tekst": m.group(2), "blok": [m.group(2)]}
            taken.append(huidig)
        elif huidig is not None and regel.startswith("   ") and regel.strip():
            huidig["blok"].append(regel.strip())
        elif regel.startswith("#") or regel.startswith("- "):
            huidig = None
    uit = []
    for t in taken[:ANGEL_MAX]:
        prive = PRIVE_RE.search(" ".join(t["blok"])) or any(p in t["tekst"] for p in prive_teksten)
        uit.append(f"{t['nr']}. privé" if prive else f"{t['nr']}. {kort(t['tekst'], 140)}")
    if len(taken) > ANGEL_MAX:
        uit.append(f"en nog {len(taken) - ANGEL_MAX} op het bord")
    return uit


def inhoud_regels(inhoud):
    """De regels van een tekstinhoud als lijst, zonder het streepje vooraan; lege regels vallen weg. Boven MAX_REGELS een
    slotregel met het aantal."""
    uit = [kort(re.sub(r"^\s*-\s+", "", x), 220) for x in str(inhoud or "").splitlines() if x.strip()]
    return uit[:MAX_REGELS] + ([f"en nog {len(uit) - MAX_REGELS} regel(s)"] if len(uit) > MAX_REGELS else [])


def lees_log(conn, wacht, van, tot):
    rijen = conn.execute("SELECT ts, stap, onderwerp, tekst FROM logboek WHERE naam=? AND ts>=? AND ts<? ORDER BY id",
                         (wacht, van, tot)).fetchall()
    return [{"tijd": uur(r["ts"]), "stap": r["stap"], "tekst": kort(f"{r['onderwerp']}: {r['tekst']}" if r["onderwerp"]
                                                                       else r["tekst"], 220),
             "fout": r["stap"] == "fout"} for r in rijen]


def _utc(ts):
    """Een ts uit de databank als UTC-tekst zoals grenzen() ze geeft, om te vergelijken; onleesbaar is leeg."""
    try:
        x = datetime.fromisoformat(str(ts or "").replace("Z", "+00:00"))
    except ValueError:
        return ""
    return (x if x.tzinfo else x.replace(tzinfo=timezone.utc)).astimezone(timezone.utc).isoformat()


# CL-4: de schrijfwijzen van 'alleen op werkdagen' in de vrije cadans van de tabel agent, en wat dat tegenspreekt (het
# weekend, of rondes door de dag: De Agendawacht draait op werkdagen, maar haar signaalwacht elke dag om de 12 minuten).
WERKDAGEN_RE = re.compile(r"werkdag|\bma\s*(?:-|tot)\s*vr\b|\bmaandag\s*(?:-|tot)\s*vrijdag\b|\b1-5\b")
NIET_ALLEEN_WERKDAGEN_RE = re.compile(r"weekend|zaterdag|zondag|\bza\b|\bzo\b|elke dag|dagelijks|minuut|minuten|kwartier"
                                      r"|\buur\b|\*/")


def alleen_werkdagen(cadans):
    """Of de cadans uit de tabel agent zegt dat de wacht alleen op werkdagen draait ('Elke werkdag 07:15', 'ma-vr 08:15').
    Vrije tekst, dus streng: twijfel is geen werkdagwacht, en die blijft in het weekend grijs (T-0120 CL-4)."""
    c = str(cadans or "").casefold()
    return bool(WERKDAGEN_RE.search(c)) and not NIET_ALLEEN_WERKDAGEN_RE.search(c)


def _moment(ts):
    """Een tijdstip als 'dd-mm HH:MM' in Brussel; onleesbaar is leeg."""
    try:
        x = datetime.fromisoformat(str(ts or "").replace("Z", "+00:00"))
    except ValueError:
        return ""
    return (x if x.tzinfo else x.replace(tzinfo=timezone.utc)).astimezone(BRUSSEL).strftime("%d-%m %H:%M")


def gelezen_tot(conn, wacht, dag, items, log, gedekt, leesfout, cadans, rondes_geteld=None, plaud=None, archief=None):
    """T-0120 VOL-13, de laag van de wachtenpagina: tot waar deze wacht de dag las, uit haar eigen bewijs, in één
    ontwerp voor alle wachten. Wat de groepen al bouwden, blijft de bron: de dekkingsrij (TEL-8, FATHOM-4), de dagregel
    van De Zoomwacht (WACHT-2), de rondes in het werkverslag (MAIL-6, CB-3, LOC-6, YT-2) en de cadans uit de tabel agent
    (CL-4). Daarbij: het manifest van de Mac (PLAUD-7), het overzicht van De Zoomarchivaris (ARCH-2) en de dagvaststelling
    van De Dagbundelaar. Alleen lezen: deze pagina schrijft nooit een dekkingsrij (elke dekkingsrij laat De Dagbundelaar
    inhalen, dagbundelaar.py). Onbekend is nooit 0.
    stand: gelezen (de hele dag), deels (nog niet helemaal), tot (rondes op die dag), items (iets binnen zonder ronde
    op die dag), rust (geen ronde gepland), niet (niet gelezen), onbekend (het bord kon het niet lezen)."""
    def uit(stand, tekst, bewijs=""):
        return {"stand": stand, "tekst": tekst, "bewijs": bewijs}
    if leesfout:
        return uit("onbekend", "onbekend: het bord kon deze wacht niet lezen")
    rondes = sorted(x["tijd"] for x in log if not x["fout"] and x["tijd"])
    laatste = rondes[-1] if rondes else ""
    geteld = f", {rondes_geteld} rondes" if rondes_geteld else ""
    leeg = "" if items else ", niets gebeurd"
    if gedekt:
        return uit("gelezen", "helemaal gelezen" + leeg,
                   "de dagregel van De Zoomwacht" if wacht == "zoom-wacht" else "de dekkingsrij van de wacht")
    if isinstance(plaud, dict) and plaud.get("na_de_dag"):
        return uit("gelezen", "alle opnames van deze dag bekend" + leeg,
                   f"het manifest van de Mac van {_moment(plaud.get('manifest_van'))}")
    if isinstance(archief, dict) and archief.get("na_de_dag"):
        return uit("gelezen", "alle kopieën van deze dag bekend" + leeg,
                   f"het overzicht van De Zoomarchivaris van {_moment(archief.get('overzicht_van'))}")
    if wacht == "dagbundelaar":
        try:
            r = conn.execute("SELECT ts FROM klaarzet WHERE van='dagbundelaar' AND uniek=? AND status!='vervallen' "
                             "ORDER BY id DESC LIMIT 1", (f"vaststelling:{dag}",)).fetchone()
        except Exception:  # noqa: BLE001  dan zonder dit bewijs
            r = None
        if r:
            return uit("gelezen", "dag vastgesteld", f"de dagvaststelling van {_moment(r['ts'])}")
    if gedekt is False and (laatste or items):
        # een gesprekswacht zonder dekkingsrij (of De Zoomwacht zonder volledige dagregel) die wel iets las
        return uit("deels", "nog niet helemaal gelezen" + (f", laatste ronde {laatste}" if laatste else ""),
                   "de dagregel van De Zoomwacht is nog niet volledig" if wacht == "zoom-wacht"
                   else "geen dekkingsrij voor deze dag")
    if laatste:
        return uit("tot", f"gelezen tot {laatste}", f"de laatste ronde in het werkverslag van deze dag{geteld}")
    if items:
        return uit("items", "items binnen, geen ronde op deze dag zelf", "klaargezet in een ronde van een andere dag")
    if alleen_werkdagen(cadans) and date.fromisoformat(dag).weekday() >= 5:
        return uit("rust", "geen ronde gepland", f"cadans: {kort(cadans, 120)}")
    return uit("niet", "niet gelezen", "geen ronde, geen dekking en geen item van deze dag")


def per_wacht(conn, wacht, label, dag, status=None, noden=(), blad=None, cadans="", rol=""):
    """blad: welk blad van het werkverslag (1 is het begin); zonder blad het laatste, zoals voordien de laatste MAX_LOG
    regels. Een blad buiten het bereik wordt het dichtstbijzijnde (T-0120 AG-9). rol en cadans: uit de tabel agent, als
    uitleg bij de wacht (DB-5)."""
    van, tot = grenzen(dag)
    items, gedekt, leesfout, logfout = [], None, "", ""
    # Items en werkverslag apart gelezen en apart gemeld (Codex 01-11): faalt het een, dan blijft het ander staan.
    try:
        if wacht in GESPREK_BRON:
            items, gedekt = lees_gesprekken(conn, GESPREK_BRON[wacht], dag)
            if wacht == "zoom-wacht":
                gedekt = zoom_gedekt(conn, dag)
        elif wacht in MAIL_WACHTEN:
            items = lees_mail(conn, wacht, dag)
        items += lees_klaarzet(conn, wacht, dag, van, tot, zonder_gesprekken=wacht in GESPREK_BRON)
    except Exception as e:  # noqa: BLE001  een kapotte tabel mag de rest van de pagina niet tegenhouden
        leesfout = f"niet gelezen ({type(e).__name__})"
    try:
        log = lees_log(conn, wacht, van, tot)
    except Exception as e:  # noqa: BLE001
        log, logfout = [], f"werkverslag niet gelezen ({type(e).__name__})"
    # PLAUD-8 (T-0120): 'rondes' is het aantal regels in het werkverslag (zo toont de pagina het: '408 regels'), niet het
    # aantal rondes (29-10 bij De Plaudwacht 24). rondes_geteld telt de slotregels 'ronde:'; een wacht die er geen
    # schrijft, heeft geen meetbare rondes: None, nooit 0.
    try:
        rondes_geteld = conn.execute("SELECT COUNT(*) FROM logboek WHERE naam=? AND ts>=? AND ts<? AND tekst LIKE ?",
                                     (wacht, van, tot, RONDE_REGEL + "%")).fetchone()[0] or None
    except Exception:  # noqa: BLE001  dan onbekend; het werkverslag zelf staat hierboven al apart
        rondes_geteld = None
    plaud = None
    if wacht == "plaud-wacht" and not leesfout:
        try:
            extra, plaud = lees_plaud(conn, dag)
            items += extra
        except Exception as e:  # noqa: BLE001  zoals hierboven: de rest van de pagina blijft staan
            leesfout = f"niet gelezen ({type(e).__name__})"
    archief = None
    if wacht == "zoom-archief" and not leesfout:
        try:                                    # ARCH-2: de gekopieerde bestanden van die dag
            extra, archief = lees_zoom_archief(dag)
            items += extra
        except Exception as e:  # noqa: BLE001
            leesfout = f"niet gelezen ({type(e).__name__})"
    # VOL-19, tweede slot: wat een lezer hierboven ook gaf, nooit een link bij privé of bij de Mac-kanalen en Xelion
    for it in items:
        if wacht in GEEN_LINK or it.get("wie") == "privégesprek" or it.get("label") == "privé":
            it.pop("link", None)
    items.sort(key=lambda x: x["tijd"] or "99")
    fouten = [x for x in log if x["fout"]]
    st = dict(status) if status else None
    # De hartslag is alleen de stand van nu: hij telt alleen mee voor vandaag, en alleen als hij van vandaag is
    # (WISPR-3: de fout-hartslag van gisteren 22:45 maakte vandaag rood). De stand zelf blijft in "status" staan.
    status_fout = bool(st and dag == datetime.now(BRUSSEL).date().isoformat()
                       and str(st.get("status")) in ("fout", "error") and van <= _utc(st.get("ts")) < tot)
    if leesfout or logfout or fouten or status_fout:
        oordeel, kleur = "fout", "rood"
    elif items:
        oordeel, kleur = "binnen", "groen"
    elif log and wacht in MAIL_WACHTEN and any(x["stap"] == "ronde" for x in log) and not any(x["stap"] == "bron" for x in log):
        # MAIL-6: een mailwacht die zijn rondes deed zonder leesprobleem, las het postvak (een leesprobleem staat als bron)
        oordeel, kleur = "postvak gelezen, 0 nieuwe mails", "oranje"
    elif gedekt:
        # TEL-8: de wacht las de dag helemaal en er was niets (een lijn met een oproep per maand): geen grijs of oranje
        oordeel, kleur = "gelezen, niets gebeurd", "groen"
    elif log:
        oordeel, kleur = "draaide, niets binnen", "oranje"
    elif alleen_werkdagen(cadans) and date.fromisoformat(dag).weekday() >= 5:
        # T-0120 CL-4: in het weekend heeft een werkdagwacht geen ronde gepland; dat is het schema, geen grijs gat en
        # ook geen groen (dat telt als 'kwam binnen', Codex-toets 1): een eigen kleur 'rust'
        oordeel, kleur = "geen ronde gepland", "rust"
    else:
        oordeel, kleur = "niets binnen, geen ronde", "grijs"
    bladen = max(1, -(-len(log) // MAX_LOG))
    blad = bladen if blad is None else min(max(1, int(blad)), bladen)
    gelezen = gelezen_tot(conn, wacht, dag, items, log, gedekt, leesfout or logfout, cadans, rondes_geteld, plaud, archief)
    return {"naam": wacht, "label": label, "oordeel": oordeel, "kleur": kleur, "aantal": len(items),
            "items": items[:MAX_ITEMS], "rondes": len(log), "fouten": fouten,
            "log": log[(blad - 1) * MAX_LOG:blad * MAX_LOG], "log_blad": blad, "log_bladen": bladen,
            "gedekt": gedekt, "leesfout": leesfout, "logfout": logfout, "noden": list(noden),
            "status": None if not st else {"status": st.get("status"), "detail": kort(st.get("detail"), 200),
                                            "laatste": uur(st.get("ts")), "laatste_ts": st.get("ts")},
            "rondes_geteld": rondes_geteld,
            # PLAUD-7: bij De Plaudwacht de opnames van die dag volgens het manifest, of None (onbekend)
            **({"plaud": plaud} if wacht == "plaud-wacht" else {}),
            # ARCH-2: bij De Zoomarchivaris de telling van die dag uit haar overzicht, of None (onbekend)
            **({"archief": archief} if wacht == "zoom-archief" else {}),
            # VOL-13: tot waar de wacht deze dag las, uit haar eigen bewijs; DB-5: wat ze doet en wanneer
            "gelezen": gelezen,
            "uitleg": {"rol": kort(rol, 300), "cadans": kort(cadans, 200)} if (rol or cadans) else None}


def dag(conn, dag_, agents, vakken, boven, wacht=None, blad=None):
    """Alle wachten van de groep Dagbundelaar voor één dag, in hun vakken. agents: naam -> label. wacht en blad: dat blad
    van het werkverslag voor die ene wacht (T-0120 AG-9); de andere wachten krijgen hun laatste blad."""
    date.fromisoformat(dag_)
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    nood = {}
    for r in conn.execute("SELECT naam, tekst FROM nood WHERE open=1 ORDER BY id").fetchall():
        nood.setdefault(r["naam"], []).append(kort(r["tekst"], 200))
    try:                                        # CL-4: de cadans uit de tabel agent; zonder tabel blijft grijs grijs
        agenttabel = {r["naam"]: r for r in conn.execute("SELECT naam, rol, cadans FROM agent").fetchall()}
    except Exception:  # noqa: BLE001
        agenttabel = {}
    cadans = {n: r["cadans"] or "" for n, r in agenttabel.items()}
    rol = {n: r["rol"] or "" for n, r in agenttabel.items()}      # DB-5: de uitleg per wacht
    groepen = [("De Dagbundelaar en Ai Angel", tuple(boven))] + [(v, tuple(w)) for v, w in vakken]
    uit = []
    for vak, namen in groepen:
        uit.append({"vak": vak, "wachten": [per_wacht(conn, n, agents.get(n, n), dag_, st.get(n), nood.get(n, ()),
                                                      blad=blad if n == wacht else None, cadans=cadans.get(n, ""),
                                                      rol=rol.get(n, ""))
                                            for n in namen]})
    alle = [w for v in uit for w in v["wachten"]]
    return {"dag": dag_, "vakken": uit,
            "telling": {k: sum(1 for w in alle if w["kleur"] == k) for k in ("groen", "oranje", "rood", "grijs", "rust")},
            "items": sum(w["aantal"] for w in alle)}
