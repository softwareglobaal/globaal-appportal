"""Per wacht wat er op een dag binnenkwam (Mehdi, 01-11-2026: "ik wil alle wachten zien, zodat ik weet per wacht wat
binnengekomen is en dat ik het kan controleren ... ik wil het als mens zien en begrijpen dat het werkt").

Alleen lezen uit de databank van het bord. Per wacht uit de groep Dagbundelaar: hoeveel items, de items zelf (tijd, van
wie of wat, kort), de rondes van die dag uit het werkverslag, en of er een fout was. Een wacht die die dag niets meldde,
staat als "niets binnen", nooit als nul. Nooit de tekst van een bericht: de wachten bewaren die ook niet.

Per item ook alles wat de wacht erover weet (detail: wie, firma, afdeling, thema, waarom dit oordeel, zekerheid, link
naar opname of archief), zodat Mehdi het oordeel kan nakijken (02-11-2026: "ik wil de tekst lezen en zien hoe we het
kunnen verbeteren"). Een privégesprek draagt het label "privé" en blijft leesbaar: deze pagina is alleen voor Mehdi, en
hij wil juist zien wat er op privé staat (02-11-2026: "te veel staat op privé, zo begrijp ik de agent niet").

Sinds de eerste feedback van Mehdi (Fathom-gesprek 01-11-2026, T-0154) ligt elk item in drie lagen: dicht alleen tijd,
wie, de essentie en een label; open de kern (bij Fathom de samenvatting: doel, conclusies, volgende stappen), de taken
(actiepunten: voor jou, voor anderen) en het oordeel van de wacht (firma, afdeling, project, zekerheid, waarom); en
achter een knop het technische (nummer, bron, archief). Twijfel is geen privé: twijfelt de wacht zelf, dan staat er
"twijfel" met de reden ("als hij twijfelt zet hij privé, hij moet juist een check geven: hier twijfel ik"). Zoom staat
in twee rijen (gesprekken en chat: "dat zou echt handig zijn"), en bovenaan de dag staat wat voor Mehdi is.
"""
import glob
import hashlib
import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
# De gegevensmap van het bord (op de VM /data = ~/appportal/mijnagents-data): daar staan de teksten van de gesprekken
# (zoom-data, fathom-data, plaud-invoer), naast de databank.
DATA = os.environ.get("MIJNAGENTS_DATA") or os.path.dirname(os.path.abspath(os.environ.get("AGENTS_DB", "mijnagents.db")))
# Mehdi leest de wacht per dag in het Dagboek: niets wegkappen wat hij daar wil zien (Codex 01-11). Een dag heeft hoogstens
# enkele honderden rondes (de Fotowacht 435 op 30-10).
MAX_ITEMS = 2000
MAX_LOG = 1000
KORT = 160
# Welke wacht schrijft welke bron in de gesprekkentabel (gesprek_log.bron).
GESPREK_BRON = {"whatsapp-wacht": "whatsapp", "belwacht": "telefoon", "sms-wacht": "sms", "xelion-wacht": "xelion",
                "fathom-wacht": "fathom", "plaud-wacht": "plaud", "zoom-wacht": "zoom"}
MAIL_WACHTEN = ("mail-prive", "mail-mch", "mail-info-harc", "mail-hinv", "mail-melo")
# De dagpagina splitst De Zoomwacht in twee rijen (Mehdi 01-11-2026): zoom-chat is geen agent op het bord, maar de
# chatrijen (zoom:chat:) van zoom-wacht; werkverslag, hartslag en noden staan bij de echte agent.
GESPREK_BRON["zoom-chat"] = "zoom"
ECHTE_AGENT = {"zoom-chat": "zoom-wacht"}
UNIEK_VOORVOEGSEL = {"zoom-wacht": "zoom:meeting:", "zoom-chat": "zoom:chat:"}
# Alles van Mehdi's telefoon is privé door een vaste regel (beslissing Mehdi 26-10-2026, privé-communicatie), niet door
# een oordeel: dat zegt de pagina er ook bij, zodat hij weet waar het label vandaan komt.
VASTE_PRIVE_BRON = ("whatsapp", "telefoon", "sms", "xelion")
VASTE_REGEL = ("vaste regel: berichten en oproepen van je telefoon tellen als privé tot je anders beslist (keuze T-0141); "
               "de wacht las nooit de tekst")
MEHDI_NAMEN = ("mehdi",)


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


DETAIL_MAX = 600
# klaarzet.inhoud mag 60.000 tekens zijn (Codex 02-11): die staat er helemaal en letterlijk (regeleinden blijven), de
# rest van het detail kort.
DETAIL_LANG = ("inhoud",)


def _paren(paren):
    """Een lijst (naam, waarde) zonder lege waarden; inhoud letterlijk, de rest kort."""
    return [(k, str(v) if k in DETAIL_LANG else kort(v, DETAIL_MAX)) for k, v in (paren or [])
            if v not in (None, "", 0, False)]


def _item(tijd, wie, wat, fout=False, label="", reden="", soort="item", kern=None, kern_ontbreekt="", taken=None,
          oordeel=None, technisch=None, tekst=""):
    """Eén item in drie lagen (Mehdi 01-11-2026: "nummer en dat soort dingen heb je niet nodig; de essentie, is er een
    opdracht uit voortgevloeid, zijn er afspraken gemaakt"). Dicht: tijd, wie, wat (de essentie), label (privé of
    twijfel). Open: kern (secties met een kop en regels, bij Fathom doel, conclusies en volgende stappen), taken
    (actiepunten met wie en of ze voor Mehdi zijn), oordeel (firma, afdeling, project, zekerheid, waarom) en tekst: de
    sleutel waarmee de volledige tekst te lezen is (/api/wachten/tekst), of leeg. Achter een knop: technisch (nummer,
    bron, archief). reden zegt waar het label vandaan komt; kern_ontbreekt waarom er geen kern is."""
    return {"tijd": tijd, "wie": kort(wie, 80), "wat": kort(wat), "fout": bool(fout), "label": label, "reden": kort(reden, 400),
            "soort": soort, "kern": kern or [], "kern_ontbreekt": kern_ontbreekt, "taken": taken or [],
            "oordeel": _paren(oordeel), "technisch": _paren(technisch), "tekst": tekst}


def is_prive_gesprek(r):
    """Privé zoals De Dagbundelaar het telt (dagvaststelling, prive_gezien): de vlag prive of de afdeling prive/privé.
    Hier alleen een label, geen masker: de pagina is alleen voor Mehdi en hij kijkt juist na of dat oordeel klopt
    (02-11-2026: "te veel staat op privé")."""
    return bool(r.get("prive")) or str(r.get("afdeling") or "").strip().casefold() in ("prive", "privé")


def twijfelt(r):
    """De wacht wist het zelf niet zeker: ze zegt 'bij twijfel', haar zekerheid is laag of middel, of de afdeling is
    onbekend of leeg (een Plaud-opname zonder herkende sprekers)."""
    waarom = str(r.get("waarom") or "").casefold()
    zeker = str(r.get("zekerheid") or "").strip().casefold()
    afd = str(r.get("afdeling") or "").strip().casefold()
    return "twijfel" in waarom or zeker in ("laag", "middel") or afd in ("", "onbekend")


def label_en_reden(r):
    """(label, reden) van een gesprek. Mehdi 01-11-2026: "als hij twijfelt zet hij altijd privé; hij moet juist een
    check geven: hier twijfel ik, zeg maar wat het moet zijn". Dus: twijfelt de wacht, dan 'twijfel' met haar reden,
    ook als ze het op privé zette; 'privé' alleen bij een bewuste privé (hoge zekerheid) of de vaste regel van de
    telefoon. De Dagbundelaar telt nog steeds op de vlag; dit is alleen hoe de pagina het Mehdi laat zien."""
    waarom = str(r.get("waarom") or "").strip()
    prive = is_prive_gesprek(r)
    if prive and str(r.get("bron") or "") in VASTE_PRIVE_BRON:
        return "privé", VASTE_REGEL
    if prive:
        if twijfelt(r):
            return "twijfel", "de wacht zette het op privé omdat ze twijfelde: " + (waarom or "zonder reden") + ". Wat moet het zijn?"
        return "privé", waarom
    zeker = str(r.get("zekerheid") or "").strip().casefold()
    afd = str(r.get("afdeling") or "").strip().casefold()
    if zeker == "laag" or afd == "onbekend":
        return "twijfel", "de wacht wist niet bij wie of wat dit hoort: " + (waarom or "zonder reden") + ". Wat moet het zijn?"
    return "", ""


def is_mehdi(naam):
    return any(n in str(naam or "").casefold() for n in MEHDI_NAMEN)


MD_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")


def samenvatting_secties(md):
    """De samenvatting van Fathom (markdown_formatted: '## Doel van de Vergadering', '## Belangrijkste Conclusies',
    '## Volgende Stappen', elke zin als link naar het moment in de opname) als secties [{kop, regels:[{tekst, link}]}]
    zonder opmaak: Mehdi leest de zin, de link is het moment."""
    secties, huidig = [], None
    for regel in str(md or "").splitlines():
        t = regel.strip()
        if not t:
            continue
        if t.startswith("#"):
            huidig = {"kop": t.lstrip("#").strip(), "regels": []}
            secties.append(huidig)
            continue
        if huidig is None:
            huidig = {"kop": "", "regels": []}
            secties.append(huidig)
        m = MD_LINK.search(t)
        link = m.group(2) if m else ""
        t = MD_LINK.sub(lambda x: x.group(1), t)
        t = re.sub(r"^[-*]\s+", "", t).replace("**", "").strip()
        if t:
            huidig["regels"].append({"tekst": kort(t, 600), "link": link})
    return [x for x in secties if x["regels"]]


def taken_uit(actiepunten, bron_wie=""):
    """De actiepunten van Fathom ([{description, assignee{name}, completed, recording_playback_url}]) als taken
    [{wat, wie, mij, klaar, link}]; mij: de naam van wie het moet doen is Mehdi."""
    uit = []
    for a in actiepunten if isinstance(actiepunten, list) else []:
        if not isinstance(a, dict):
            continue
        wie = (a.get("assignee") or {}).get("name") if isinstance(a.get("assignee"), dict) else a.get("assignee")
        wat = str(a.get("description") or "").strip()
        if wat:
            uit.append({"wat": kort(wat, 400), "wie": kort(wie or "", 60), "mij": is_mehdi(wie), "klaar": bool(a.get("completed")),
                        "link": str(a.get("recording_playback_url") or "")})
    return uit


def fathom_map(r):
    """De archiefmap van een Fathom-gesprek op de schijf van het bord, of ''."""
    archief = str(r.get("archief") or "")
    if str(r.get("bron") or "") != "fathom" or "mijnagents-data/" not in archief:
        return ""
    return os.path.join(DATA, archief.split("mijnagents-data/", 1)[1].rstrip("/"))


def fathom_kern(r):
    """(kern, taken, kern_ontbreekt) van een Fathom-gesprek: de samenvatting en de actiepunten die De Fathomwacht
    bewaarde (samenvatting.md en actiepunten.md naast gesprek.json, of de velden default_summary en action_items in
    gesprek.json). Zonder samenvatting zegt kern_ontbreekt dat."""
    map_ = fathom_map(r)
    if not map_ or not os.path.isdir(map_):
        return [], [], "geen archiefmap op het bord"
    md, punten = "", None
    gj = _json(_lees_bestand(os.path.join(map_, "gesprek.json")))
    if isinstance(gj, dict):
        ds = gj.get("default_summary")
        md = ds.get("markdown_formatted") if isinstance(ds, dict) else (ds if isinstance(ds, str) else "")
        punten = gj.get("action_items")
    sm = _lees_bestand(os.path.join(map_, "samenvatting.md"))
    if sm and "markdown_formatted" not in sm[:200]:
        md = sm
    ap = _json(_lees_bestand(os.path.join(map_, "actiepunten.md")))
    if isinstance(ap, list):
        punten = ap
    kern = samenvatting_secties(md)
    # De eerste kop van samenvatting.md is onze eigen kop, niet die van Fathom.
    kern = [k for k in kern if not k["kop"].startswith("Samenvatting van Fathom")]
    taken = taken_uit(punten)
    ontbreekt = "" if kern else "Fathom gaf geen samenvatting voor dit gesprek (of ze is nog niet opgehaald)"
    return kern, taken, ontbreekt


def _lees_bestand(pad):
    try:
        with open(pad, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def tekst_pad(r):
    """Waar de tekst van dit gesprek op de schijf van het bord staat, of leeg. Zoom: zoom-data/<dag uur Zoom ...>
    [sha1(uuid)[:8]]/transcript.json (de mapnaam van de Zoomwacht); Fathom: het archief van de Fathomwacht
    (fathom-data/<map>/transcript.md); Plaud: plaud-invoer/<map>/transcript.json (het archief wijst naar Dropbox)."""
    uniek, bron, archief = str(r.get("uniek") or ""), str(r.get("bron") or ""), str(r.get("archief") or "")
    paden = []
    if bron == "zoom" and uniek.startswith("zoom:meeting:"):
        kenmerk = hashlib.sha1(uniek[len("zoom:meeting:"):].encode()).hexdigest()[:8]
        # De haken in de mapnaam zijn letters, geen glob-klasse: escape.
        paden = sorted(glob.glob(os.path.join(glob.escape(DATA), "zoom-data", "* " + glob.escape(f"[{kenmerk}]"),
                                              "transcript.json")))
    elif bron == "fathom" and "mijnagents-data/" in archief:
        rest = archief.split("mijnagents-data/", 1)[1].rstrip("/")
        # Zonder transcript schrijft de Fathomwacht toch een transcript.md met alleen een kop, en daarnaast
        # geen-transcript.txt (fathom_wacht.bewaar): dan is er geen tekst (Codex 02-11).
        if os.path.isfile(os.path.join(DATA, rest, "geen-transcript.txt")):
            return ""
        paden = [os.path.join(DATA, rest, "transcript.md"), os.path.join(DATA, rest, "transcript.json")]
    elif bron == "plaud" and "/Plaud/" in archief:
        mapnaam = archief.split("/Plaud/", 1)[1].split("/", 1)[0]
        paden = [os.path.join(DATA, "plaud-invoer", mapnaam, "transcript.json")]
    for pad in paden:
        if os.path.isfile(pad):
            return pad
    return ""


def _tijd_ms(ms):
    try:
        s_ = int(ms) // 1000
    except (TypeError, ValueError):
        return ""
    return f"{s_ // 3600:02d}:{s_ % 3600 // 60:02d}:{s_ % 60:02d}"


def tekst(conn, uniek):
    """De volledige tekst van één gesprek voor Mehdi (02-11-2026: "als Zoom privé staat, wil ik de tekst lezen"):
    {'wie','wat','bron','md'} (Fathom, de tekst van de Fathomwacht met kop) of {'regels':[{tijd, wie, tekst}]}
    (Zoom en Plaud uit transcript.json), of {'fout': ...} als er geen tekst bewaard is."""
    r = conn.execute("SELECT * FROM gesprek_log WHERE uniek=?", (uniek,)).fetchone()
    if r is None:
        return {"fout": "onbekend gesprek"}
    r = dict(r)
    kop = {"uniek": uniek, "wie": r.get("personen") or "onbekend", "wat": kort(r.get("thema"), 200), "bron": r.get("bron"),
           "datum": r.get("datum"), "tijd": uur(r.get("start")), "label": "privé" if is_prive_gesprek(r) else ""}
    pad = tekst_pad(r)
    if not pad:
        return dict(kop, fout="geen tekst bewaard: dit gesprek heeft geen opname of transcript op het bord")
    try:
        with open(pad, encoding="utf-8", errors="replace") as f:
            inhoud = f.read()
    except OSError as e:
        return dict(kop, fout=f"tekst niet leesbaar ({type(e).__name__})")
    if pad.endswith(".md"):
        return dict(kop, md=inhoud)
    data = _json(inhoud)
    if not isinstance(data, list):
        return dict(kop, fout="tekst niet leesbaar (geen lijst)")
    regels = []
    for x in data:
        if not isinstance(x, dict):
            continue
        spreker = x.get("speaker")
        wie = spreker.get("display_name") if isinstance(spreker, dict) else (x.get("speaker") or x.get("original_speaker"))
        regels.append({"tijd": x.get("timestamp") or _tijd_ms(x.get("start_time")), "wie": str(wie or ""),
                       "tekst": str(x.get("text") or x.get("content") or "")})
    return dict(kop, regels=regels)


OORDEEL_VELDEN = (("bedrijf", "firma"), ("afdeling", "afdeling"), ("project", "project"), ("zekerheid", "zekerheid"),
                  ("waarom", "waarom dit oordeel"))
TECHNISCH_VELDEN = (("minuten", "minuten"), ("opgenomen_door", "opgenomen door"), ("bron", "bron"), ("link", "link"),
                    ("archief", "archief"), ("dubbel_van", "dubbel van"), ("uniek", "nummer"))
CHAT = re.compile(r"Zoom-chat: (\d+) bericht\(en\), (\d+) van Mehdi, (\S*) tot (\S*)")
BERICHTEN = re.compile(r"(\d+) berichten \((\d+) in, (\d+) uit\)")


def chat_wat(r):
    """Een chatrij als wat Mehdi erin moet lezen: aantallen, niet een gesprek met een duur (hij las '09:59 tot 15:54'
    als een gesprek van zes uur): '7 berichten, 0 van jou, tussen 07:40 en 21:46 · kanaal'."""
    m = CHAT.search(str(r.get("thema") or ""))
    soort = "1:1" if str(r.get("waarom") or "").startswith("1:1") else "kanaal"
    if not m:
        return kort(r.get("thema"), 100) + " · " + soort
    n, van_mehdi, a, b = m.groups()
    tijd = f"tussen {a} en {b}" if a and b and a != b else f"om {a}" if a else ""
    return ", ".join(x for x in (f"{n} bericht{'' if n == '1' else 'en'}", f"{van_mehdi} van jou", tijd) if x) + " · " + soort


def lees_gesprekken(conn, wacht, bron, dag):
    rijen = conn.execute("SELECT * FROM gesprek_log WHERE datum=? AND bron IN (?, 'dekking') ORDER BY start",
                         (dag, bron)).fetchall()
    voorvoegsel = UNIEK_VOORVOEGSEL.get(wacht, "")
    items, gedekt = [], False
    for r in rijen:
        if r["bron"] == "dekking":
            if str(r["uniek"] or "").startswith(f"dekking:{bron}:"):
                gedekt = True
            continue
        r = dict(r)
        uniek = str(r.get("uniek") or "")
        if voorvoegsel and not uniek.startswith(voorvoegsel):
            continue
        dubbel = r.get("dubbel_van")
        chat = uniek.startswith("zoom:chat:")
        if chat:
            wat = chat_wat(r) + (", dubbel, telt niet" if dubbel else "")
        else:
            wat = ", ".join(x for x in (f"{r['minuten']} min" if r.get("minuten") else "", kort(r.get("thema"), 160),
                                        "dubbel, telt niet" if dubbel else "") if x)
        label, reden = label_en_reden(r)
        pad = tekst_pad(r)
        kern, taken, ontbreekt = [], [], ""
        if r.get("bron") == "fathom":
            kern, taken, ontbreekt = fathom_kern(r)
        elif pad:
            # Plaud en Zoom-tekst krijgen pas een samenvatting en taken met De Gespreksanalist (keuze T-0122 van Mehdi).
            ontbreekt = "nog geen samenvatting en taken: dat komt met De Gespreksanalist, na jouw keuze (T-0122); de tekst staat er wel"
        items.append(_item(uur(r.get("start")), r.get("personen") or "onbekend", wat, label=label, reden=reden,
                           soort="chat" if chat else "gesprek", kern=kern, kern_ontbreekt=ontbreekt, taken=taken,
                           oordeel=[(label_, r.get(k)) for k, label_ in OORDEEL_VELDEN],
                           technisch=[(label_, r.get(k)) for k, label_ in TECHNISCH_VELDEN], tekst=uniek if pad else ""))
    return items, gedekt


MAIL_OORDEEL = (("soort", "soort"), ("waarom", "waarom dit oordeel"), ("opvolging", "opvolging"), ("stap", "stap"),
                ("besluit", "besluit"), ("besluit_door", "besluit door"), ("antwoord_door", "beantwoord door"),
                ("antwoord_ts", "beantwoord op"), ("antwoord_naar", "beantwoord naar"))
MAIL_TECHNISCH = (("van", "adres"), ("naar", "gesorteerd naar"), ("postvak", "postvak"), ("map", "map"), ("datum", "datum"),
                  ("uniek", "nummer"))


def lees_mail(conn, wacht, dag):
    rijen = conn.execute("SELECT * FROM mailbericht WHERE wacht=? AND dag=? ORDER BY datum LIMIT ?",
                         (wacht, dag, MAX_ITEMS)).fetchall()
    uit = []
    for r in rijen:
        r = dict(r)
        oordeel = [(label, r.get(k)) for k, label in MAIL_OORDEEL]
        oordeel += [("dringend", "ja" if r.get("dringend") else ""), ("mailinglijst", "ja" if r.get("mailinglijst") else ""),
                    ("beantwoord", "ja" if r.get("beantwoord") else ""), ("opgeruimd", "ja" if r.get("opgeruimd") else "")]
        label = "dringend" if r.get("dringend") else ""
        uit.append(_item(uur(r.get("datum")), r.get("van_naam") or r.get("van") or "onbekend",
                         " · ".join(x for x in (r.get("onderwerp") or "(geen onderwerp)", r.get("soort") or "") if x),
                         label=label, reden="De Mailregisseur zette deze mail op dringend" if label else "", soort="mail",
                         oordeel=oordeel, technisch=[(label_, r.get(k)) for k, label_ in MAIL_TECHNISCH]))
    return uit


def lees_klaarzet(conn, wacht, dag, van, tot):
    """Wat de wacht die dag klaarzette, of wat over die dag gaat (sleutel, uniek of titel met de dag)."""
    rijen = conn.execute(
        "SELECT ts, soort, titel, inhoud, uniek, sleutel, status, voor, verwijzing, opgepakt_door, opgepakt_ts "
        "FROM klaarzet WHERE van=? AND status!='vervallen' AND "
        "((ts>=? AND ts<?) OR sleutel=? OR uniek LIKE ? OR uniek LIKE ? OR titel LIKE ?) ORDER BY ts LIMIT ?",
        (wacht, van, tot, dag, f"%:{dag}", f"%:{dag}:%", f"{dag} %", MAX_ITEMS)).fetchall()
    items = []
    for r in rijen:
        inhoud = _json(r["inhoud"])
        wat = r["titel"] or ""
        if isinstance(inhoud, dict):
            pd = inhoud.get("per_dag")
            t = pd.get(dag) if isinstance(pd, dict) else inhoud.get("vandaag")
            if isinstance(t, dict) and t:
                wat = f"{wat}: {_telling_tekst(t)}"
        titel = str(r["titel"] or "")
        tijd = uur(r["ts"])
        if titel.startswith(dag + " "):
            # "2026-10-31 20:25-20:56: 22 foto's bij ...": de eerste tijd is de tijd, de rest is wat; een bereik komt erachter.
            wat = titel[len(dag) + 1:]
            m = re.match(r"([01]\d:[0-5]\d|2[0-3]:[0-5]\d)(?:-([01]\d:[0-5]\d|2[0-3]:[0-5]\d))?(?::\s*|\s+|$)", wat)
            if m:
                tijd, wat = m.group(1), wat[m.end():].strip()
                if m.group(2) and m.group(2) != m.group(1):
                    wat = f"{wat} ({m.group(1)} tot {m.group(2)})"
        inhoud_tekst = r["inhoud"] or ""   # letterlijk zoals bewaard, nooit opnieuw opgemaakt of afgekapt
        # Leesbare inhoud (een dagplan, een signaal) is de kern; een telling of lijst (json) hoort bij het technische.
        kern = [] if inhoud is not None or not inhoud_tekst.strip() else [{"kop": "", "tekst": inhoud_tekst}]
        oordeel = [("soort", r["soort"]), ("voor", r["voor"]), ("status", r["status"]), ("opgepakt door", r["opgepakt_door"]),
                   ("opgepakt op", uur(r["opgepakt_ts"]))]
        technisch = [("titel", r["titel"]), ("sleutel", r["sleutel"]), ("verwijzing", r["verwijzing"]), ("nummer", r["uniek"]),
                     ("klaargezet", uur(r["ts"])), ("inhoud", inhoud_tekst if inhoud is not None else "")]
        # Een klaargezet item dat zichzelf privé noemt (inhoud.prive) draagt hetzelfde label als een gesprek.
        prive = isinstance(inhoud, dict) and bool(inhoud.get("prive"))
        items.append(_item(tijd, r["soort"] or "item", wat, label="privé" if prive else "",
                           reden="het item noemt zichzelf privé" if prive else "", soort="klaarzet", kern=kern,
                           oordeel=oordeel, technisch=technisch))
    return items


def lees_log(conn, wacht, van, tot):
    rijen = conn.execute("SELECT ts, stap, onderwerp, tekst FROM logboek WHERE naam=? AND ts>=? AND ts<? ORDER BY id",
                         (wacht, van, tot)).fetchall()
    return [{"tijd": uur(r["ts"]), "stap": r["stap"], "tekst": kort(f"{r['onderwerp']}: {r['tekst']}" if r["onderwerp"]
                                                                       else r["tekst"], 220),
             "fout": r["stap"] == "fout"} for r in rijen]


def samen(wacht, items):
    """Eén telregel per wacht voor de rij (Mehdi 01-11-2026: "ik wil weten hoeveel berichten ik krijg", "je zit in te
    veel groepen"): WhatsApp en sms per gesprek en groep, telefoon met gemist en minuten, Zoom en Fathom met minuten
    en taken, mail met dringend. Leeg als er niets te tellen is."""
    n = len(items)
    if not n:
        return ""
    if wacht in ("whatsapp-wacht", "sms-wacht"):
        tot = inn = uit = 0
        for it in items:
            m = BERICHTEN.search(it["wat"])
            if m:
                tot += int(m.group(1))
                inn += int(m.group(2))
                uit += int(m.group(3))
        groepen = sum(1 for it in items if it["wie"].startswith("groep:"))
        return ", ".join(x for x in (f"{tot} berichten ({inn} in, {uit} uit)" if tot else "", f"{n} gesprekken",
                                     f"{groepen} groepen" if groepen else "") if x)
    if wacht in ("belwacht", "xelion-wacht"):
        gemist = sum(1 for it in items if "gemist" in it["wat"])
        minuten = sum(int(dict(it["technisch"]).get("minuten") or 0) for it in items)
        return f"{n} oproepen, {gemist} gemist, {minuten} min"
    if wacht == "zoom-chat":
        tot = sum(int(m.group(1)) for it in items for m in [re.match(r"(\d+) bericht", it["wat"])] if m)
        kanalen = sum(1 for it in items if it["wat"].endswith("kanaal"))
        return f"{tot} berichten in {n} gesprekken, {kanalen} kanalen"
    if wacht in ("zoom-wacht", "fathom-wacht", "plaud-wacht"):
        minuten = sum(int(dict(it["technisch"]).get("minuten") or 0) for it in items)
        mij = sum(1 for it in items for t in it["taken"] if t["mij"])
        met_tekst = sum(1 for it in items if it["tekst"])
        return ", ".join(x for x in (f"{n} gesprekken", f"{minuten} min", f"{mij} taken voor jou" if mij else "",
                                     f"{met_tekst} met tekst" if met_tekst and wacht != "fathom-wacht" else "") if x)
    if wacht in MAIL_WACHTEN:
        dringend = sum(1 for it in items if it["label"] == "dringend")
        return f"{n} mails" + (f", {dringend} dringend" if dringend else "")
    return ""


def per_wacht(conn, wacht, label, dag, status=None, noden=()):
    van, tot = grenzen(dag)
    echte = ECHTE_AGENT.get(wacht, wacht)
    items, gedekt, leesfout, logfout = [], None, "", ""
    # Items en werkverslag apart gelezen en apart gemeld (Codex 01-11): faalt het een, dan blijft het ander staan.
    try:
        if wacht in GESPREK_BRON:
            items, gedekt = lees_gesprekken(conn, wacht, GESPREK_BRON[wacht], dag)
        elif wacht in MAIL_WACHTEN:
            items = lees_mail(conn, wacht, dag)
        if echte == wacht:
            items += lees_klaarzet(conn, wacht, dag, van, tot)
    except Exception as e:  # noqa: BLE001  een kapotte tabel mag de rest van de pagina niet tegenhouden
        leesfout = f"niet gelezen ({type(e).__name__})"
    try:
        # Een afgesplitste rij (zoom-chat) heeft geen eigen werkverslag: dat staat bij de echte agent.
        log = lees_log(conn, wacht, van, tot) if echte == wacht else []
    except Exception as e:  # noqa: BLE001
        log, logfout = [], f"werkverslag niet gelezen ({type(e).__name__})"
    items.sort(key=lambda x: x["tijd"] or "99")
    fouten = [x for x in log if x["fout"]]
    st = dict(status) if status else None
    # De hartslag is alleen de stand van nu: hij telt alleen mee voor vandaag.
    status_fout = bool(st and dag == datetime.now(BRUSSEL).date().isoformat()
                       and str(st.get("status")) in ("fout", "error"))
    if leesfout or logfout or fouten or status_fout:
        oordeel, kleur = "fout", "rood"
    elif items:
        oordeel, kleur = "binnen", "groen"
    elif log:
        oordeel, kleur = "draaide, niets binnen", "oranje"
    else:
        oordeel, kleur = "niets binnen, geen ronde", "grijs"
    return {"naam": wacht, "agent": echte, "label": label, "oordeel": oordeel, "kleur": kleur, "aantal": len(items),
            "items": items[:MAX_ITEMS], "samen": samen(wacht, items), "rondes": len(log), "fouten": fouten,
            "log": log[-MAX_LOG:], "gedekt": gedekt, "leesfout": leesfout, "logfout": logfout, "noden": list(noden),
            "status": None if not st else {"status": st.get("status"), "detail": kort(st.get("detail"), 200),
                                            "laatste": uur(st.get("ts")), "laatste_ts": st.get("ts")}}


def voor_jou(conn, dag, van, tot, alle):
    """Bovenaan de dag wat voor Mehdi is (01-11-2026: "ik wil mijn to-do's krijgen, voor mij en voor collega's, en
    van waar en van wie"): de taken uit de gesprekken van die dag (voor jou en voor anderen, met wie en uit welk
    gesprek), en de signalen die de agents die dag voor hem klaarzetten (klaarzet voor=mehdi, nog open), per agent."""
    mij, anderen = [], []
    for w in alle:
        for it in w["items"]:
            for t in it["taken"]:
                (mij if t["mij"] else anderen).append(dict(t, gesprek=it["wie"], tijd=it["tijd"], wacht=w["naam"]))
    signalen, per = [], {}
    try:
        rijen = conn.execute(
            "SELECT van, soort, titel, ts FROM klaarzet WHERE voor='mehdi' AND status='klaar' AND "
            "((ts>=? AND ts<?) OR sleutel=?) ORDER BY van, ts LIMIT ?", (van, tot, dag, MAX_ITEMS)).fetchall()
    except Exception:  # noqa: BLE001
        rijen = []
    for r in rijen:
        p = per.get(r["van"])
        if p is None:
            p = per[r["van"]] = {"van": r["van"], "aantal": 0, "titels": []}
            signalen.append(p)
        p["aantal"] += 1
        if len(p["titels"]) < 50:
            p["titels"].append({"tijd": uur(r["ts"]), "soort": r["soort"], "titel": kort(r["titel"], 200)})
    return {"taken_mij": mij, "taken_anderen": anderen, "signalen": signalen}


def dag(conn, dag_, agents, vakken, boven):
    """Alle wachten van de groep Dagbundelaar voor één dag, in hun vakken. agents: naam -> label."""
    date.fromisoformat(dag_)
    van, tot = grenzen(dag_)
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    nood = {}
    for r in conn.execute("SELECT naam, tekst FROM nood WHERE open=1 ORDER BY id").fetchall():
        nood.setdefault(r["naam"], []).append(kort(r["tekst"], 200))
    groepen = [("De Dagbundelaar en Ai Angel", tuple(boven))] + [(v, tuple(w)) for v, w in vakken]
    uit = []
    for vak, namen in groepen:
        uit.append({"vak": vak, "wachten": [per_wacht(conn, n, agents.get(n, n), dag_, st.get(ECHTE_AGENT.get(n, n)),
                                                      nood.get(ECHTE_AGENT.get(n, n), ()) if n == ECHTE_AGENT.get(n, n) else ())
                                            for n in namen]})
    alle = [w for v in uit for w in v["wachten"]]
    return {"dag": dag_, "vakken": uit,
            "telling": {k: sum(1 for w in alle if w["kleur"] == k) for k in ("groen", "oranje", "rood", "grijs")},
            "items": sum(w["aantal"] for w in alle), "voor_jou": voor_jou(conn, dag_, van, tot, alle)}
