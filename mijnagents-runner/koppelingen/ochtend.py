"""Het ochtendbericht van De Regisseur: wanneer het aan de beurt is, welke beslissingen erin komen en hoe het eruitziet
(ontwerp regie-zoom v1.2, R8 en het contract in 4.2, met 13.5 X3).

Zuivere functies. regisseur.py leest de bronnen (bord.db_lees, /api/nood, /api/mail/open) en geeft ze hier door; deze
module beslist en maakt de tekst, zonder bord en zonder taalmodel. Een storing van het taalmodel houdt het bericht dus
nooit tegen: mooier() in regisseur.py mag alleen zinnen herschrijven, en aanvaard() zegt of dat mocht.

Het contract met De Bode (I1, I2, B5): een klaarzet-item van regisseur voor mehdi, soort ochtendbericht, sleutel '' en
uniek ochtendbericht:<datum in Brussel>. inhoud = {tekst, punten: [{nr, soort, ref, agent, link, vingerafdruk}], verder,
bronnen, onbekend}, zonder de sleutels datum en start: dagbundelaar.py:45 en levenscoach.py:52 halen de dag uit
inhoud.datum, inhoud.start of de sleutel, en dan werd het ochtendbericht een dagbron. De datum staat in uniek.
len(whatsapp.plat(tekst)) is hoogstens 720, zodat De Bode er tot 180 tekens bij kan zetten binnen de 900 van het
sjabloon. De kop (titel) is hoogstens 60 tekens: de eerste parameter van het sjabloon agent_melding.

Onbekend is nooit 0 (L29, L38): een bron die niet te lezen was, staat onder "Onbekend" en levert geen punt en geen getal.

Een tweede contract met De Bode: whatsapp_kort() kort een antwoord van De Regisseur in tot de 800 tekens die naar WhatsApp
gaan (R6). Het volle antwoord blijft in gesprek.antwoord op het bord (H1, REG-03).
"""
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import whatsapp

BRUSSEL = ZoneInfo("Europe/Brussels")
UTC = timezone.utc
RUNNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Het startmoment van de gesprekkenketen staat op een plek: de cronregel in planning/gesprekken.cron (Z16, X3).
CRON = os.path.join(RUNNER, "planning", "gesprekken.cron")
UITERLIJK = time(10, 30)      # dan komt het toch, met wat ontbreekt onder Onbekend; De Bode valt pas om 11:00 terug (I9)
TOT = time(21, 0)             # daarna niet meer, wel een nood
MAX_PUNTEN = 5
BUDGET = 720                  # len(whatsapp.plat(tekst)); De Bode houdt zo 180 tekens over binnen 900 (I1)
KOP_MAX = 60
PUNT_MAX = 150
BORD = "mijnagents.globaal.be"
DAGNAMEN = ("ma", "di", "wo", "do", "vr", "za", "zo")
NOOD_LAAT = "Geen ochtendbericht vandaag; na 21:00 maak ik het niet meer"
LINK = re.compile(r"mijnagents\.globaal\.be[^\s,;)]*")
PUNTREGEL = re.compile(r"^\d+\. ", re.M)
STREEPJES = (chr(0x2014), chr(0x2013))      # lang en half kastlijntje (N9); als code, zodat ze nergens in de tekst staan


# ------------------------------------------------------------------------------------------------- tijd ---
def tijdstip(t):
    """Een tijdstip met zone uit een datetime of een ISO-tekst (ook met Z). Zonder zone telt het als UTC, zoals het bord
    zijn tijden schrijft (app.py nu()). None als het niet te lezen is."""
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=UTC)
    if not isinstance(t, str) or not t.strip():
        return None
    try:
        d = datetime.fromisoformat(t.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def brussel(t):
    d = tijdstip(t)
    return d.astimezone(BRUSSEL) if d else None


def kort(t):
    """'21-10 15:15' in Brusselse tijd, of 'onbekend'."""
    d = brussel(t)
    return d.strftime("%d-%m %H:%M") if d else "onbekend"


# ---------------------------------------------------------------------------------------------- moment ---
def lees_cron(pad=None):
    """De tekst van planning/gesprekken.cron, of None als het bestand er niet is of niet te lezen is."""
    try:
        with open(pad or CRON, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def lees_keten(pad):
    """De inhoud van keten.json (alleen keten.py schrijft het, atomisch), of None."""
    try:
        with open(pad, encoding="utf-8") as f:
            inhoud = json.load(f)
    except (OSError, ValueError):
        return None
    return inhoud if isinstance(inhoud, dict) else None


def ketenstart(cron_tekst):
    """(uur, minuut) in UTC van de eerste start van de gesprekkenketen: de regel met keten.py (13.5 X3), of zolang die er
    niet is de regel met fathom_wacht.py (R8). None als het niet te lezen is; dan is het startmoment onbekend."""
    if not isinstance(cron_tekst, str):
        return None
    regels = [r.strip() for r in cron_tekst.splitlines() if r.strip() and not r.strip().startswith("#")]
    for script in ("keten.py", "fathom_wacht.py"):
        for regel in regels:
            if script not in regel:
                continue
            velden = regel.split()
            minuut = re.match(r"^(\d{1,2})(?:[,-]|$)", velden[0]) if len(velden) >= 5 else None
            uur = re.match(r"^(\d{1,2})(?:[,-]|$)", velden[1]) if len(velden) >= 5 else None
            if not (minuut and uur) or int(uur.group(1)) > 23 or int(minuut.group(1)) > 59:
                return None
            return int(uur.group(1)), int(minuut.group(1))
    return None


def keten_geslaagd(keten, start_utc):
    """(geslaagd, reden) voor keten.json (X3): alleen een keten die na het geplande startmoment van vandaag begon en
    geslaagd true draagt. Een ronde die De Regisseur zelf start, schrijft geen keten.json en telt dus nooit."""
    if start_utc is None:
        return False, "startmoment van de gesprekkenketen onbekend"
    if not isinstance(keten, dict):
        return False, "gesprekkenketen niet geslaagd (geen keten.json)"
    begin = tijdstip(keten.get("start")) or tijdstip(keten.get("keten_id"))
    if begin is None or begin < start_utc:
        return False, "gesprekkenketen van vandaag nog niet klaar"
    if not keten.get("einde"):
        return False, "gesprekkenketen loopt nog"         # keten.py schrijft einde pas als de laatste stap klaar is
    if keten.get("geslaagd") is not True:
        return False, "gesprekkenketen niet geslaagd"
    return True, ""


def _klaar_na(rij, grens):
    """Een hartslag die niet op actief staat en niet ouder is dan de grens."""
    if not isinstance(rij, dict) or grens is None or rij.get("status") in (None, "", "actief"):
        return False
    ts = tijdstip(rij.get("ts"))
    return ts is not None and ts >= grens


def aan_de_beurt(nu, statussen=None, keten=None, cron_tekst=None, bestaat=False):
    """Is het ochtendbericht nu aan de beurt? Geeft {beurt, datum, onbekend, nood, reden}; datum is de Brusselse datum.

    - bestaat: of ochtendbericht:<datum> al op het bord staat; None is onbekend en dan niet (een tweede maken kan niet
      ongedaan, wachten wel).
    - Vanaf 21:00 Brussel niet meer, met een nood.
    - Aan de beurt als keten.json van vandaag geslaagd is (X3) en, op werkdagen, de dagbundelaar na het einde van die
      geslaagde keten een afgeronde hartslag heeft (statussen: {naam: {status, ts}} uit de tabel status, None als
      onbekend). Tot 21-10-2026 volstond een hartslag na het startmoment, ook een van een ronde die liep terwijl de keten
      nog bezig was (RZ2-03). Slaagde de keten niet, dan staat zij onder wat ontbreekt, en De Dagbundelaar ook als die
      niet na het einde van die keten klaar was (tegenproef RZ2-03, 22-10-2026). De grens is het einde van de keten van
      vandaag; loopt ze nog, dan telt geen ronde; zonder keten van vandaag het geplande startmoment, nooit het einde van
      een keten van gisteren. In het weekend draait de dagbundelaar niet (J19).
    - Om 10:30 Brussel komt het toch, met wat ontbreekt onder Onbekend.
    ontbreekt: wat er nu nog niet klaar is (ook voor --nu in regisseur.py, dat het moment negeert)."""
    lokaal = brussel(nu)
    datum = lokaal.date()
    uit = {"beurt": False, "datum": datum.isoformat(), "onbekend": [], "ontbreekt": [], "nood": None, "reden": ""}
    if bestaat is None:
        uit["reden"] = "onbekend of het ochtendbericht al op het bord staat"
        return uit
    if bestaat:
        uit["reden"] = "het ochtendbericht van vandaag staat al op het bord"
        return uit
    if lokaal.time() >= TOT:
        uit["nood"], uit["reden"] = NOOD_LAAT, "na 21:00 Brussel"
        return uit
    start = ketenstart(cron_tekst)
    start_utc = datetime.combine(datum, time(*start), tzinfo=UTC) if start else None
    klaar, reden = keten_geslaagd(keten, start_utc)
    ontbreekt = [] if klaar else [reden]
    if datum.weekday() < 5:
        begin = (tijdstip(keten.get("start")) or tijdstip(keten.get("keten_id"))) if isinstance(keten, dict) else None
        van_vandaag = start_utc is not None and begin is not None and begin >= start_utc
        grens = tijdstip(keten.get("einde")) if van_vandaag else start_utc
        if statussen is None:
            ontbreekt.append("hartslag van De Dagbundelaar onbekend")
        elif not _klaar_na(statussen.get("dagbundelaar"), grens):
            ontbreekt.append("De Dagbundelaar had na de gesprekkenketen nog geen afgeronde ronde")
    uit["ontbreekt"] = ontbreekt
    if not ontbreekt:
        uit["beurt"], uit["reden"] = True, "gesprekkenketen klaar"
    elif lokaal.time() >= UITERLIJK:
        uit["beurt"], uit["onbekend"], uit["reden"] = True, ontbreekt, "10:30 Brussel, met wat ontbreekt onder Onbekend"
    else:
        uit["reden"] = "; ".join(ontbreekt)
    return uit


# ------------------------------------------------------------------------------------------ onderdelen ---
def vingerafdruk(v):
    """sha256(id + actie + parameters)[:12] van een voorstel (13.5 X5): een eigen formule, los van fase 5. parameters
    zoals ze in de tabel voorstel staan (json-tekst of leeg)."""
    tekst = f"{v.get('id')}{v.get('actie') or ''}{v.get('parameters') or ''}"
    return hashlib.sha256(tekst.encode()).hexdigest()[:12]


def _getal(x):
    return isinstance(x, int) and not isinstance(x, bool)


def zoom_telling(regel):
    """De Zoom-telling van een dag uit de inhoud van de dagregel zoom:dag:{dag} van De Zoomwacht (M5): 'N gesprekken,
    M alleen in Zoom', 'minstens N ...' bij een ondergrens, en 'onbekend' zonder regel of zonder leesbare bron. Nooit
    een getal dat De Zoomwacht niet gaf."""
    if not isinstance(regel, dict):
        return "onbekend"
    telling, n = regel.get("telling"), regel.get("gesprekken")
    if telling not in ("volledig", "ondergrens") or not _getal(n):
        return "onbekend"
    tekst = f"{'minstens ' if telling == 'ondergrens' else ''}{n} {'gesprek' if n == 1 else 'gesprekken'}"
    met = regel.get("met_fathom")
    if _getal(met) and 0 <= met <= n:
        tekst += f", {n - met} alleen in Zoom"
    stand = regel.get("stand")
    if str(stand.get("stand") if isinstance(stand, dict) else stand or "").startswith("voorlopig"):
        tekst += " (voorlopig)"
    return tekst


def _inkorten(tekst, ruimte):
    """Tekst tot ruimte tekens, op een woordgrens, met een beletselteken als er iets wegviel."""
    tekst = " ".join((tekst or "").split())
    if len(tekst) <= ruimte:
        return tekst
    if ruimte <= 1:
        return ""
    stuk = tekst[:ruimte - 1].rsplit(" ", 1)[0] if " " in tekst[:ruimte - 1] else tekst[:ruimte - 1]
    return stuk.rstrip(" ,.;:") + "…"


def _meervoud(n, een, meer):
    return f"{n} {een if n == 1 else meer}"


def _wie(rij):
    """De label van een agent als die kort is, anders zijn naam: een label van 60 tekens zou de rest van het punt
    verdringen (T55)."""
    label = str(rij.get("label") or "")
    return label if label and len(label) <= 25 else str(rij.get("naam") or label)


def _is_nieuw(v, b):
    """Nieuw sinds het vorige ochtendbericht: een id boven het hoogste dat toen open stond. Zonder vorig bericht: in de
    laatste 24 uur gezet."""
    hoogste = (b.get("vorig") or {}).get("hoogste_voorstel")
    if _getal(hoogste):
        return _getal(v.get("id")) and v["id"] > hoogste
    ts = tijdstip(v.get("ts"))
    return ts is not None and ts >= b["nu"] - timedelta(hours=24)


def _sinds_vorig(ts, b):
    grens = tijdstip((b.get("vorig") or {}).get("ts")) or b["nu"] - timedelta(hours=24)
    t = tijdstip(ts)
    return t is not None and t >= grens


def kandidaten(b):
    """De kandidaat-punten in de vaste volgorde van 4.2: dringende mail (samen), nieuwe voorstellen (elk apart, hoogstens
    twee), toe te wijzen bronnen van gisteren, de andere voorstellen (samen, per agent geteld), noden voor Mehdi (samen,
    oudste eerst, met hoeveel nieuw). Een onbekende bron levert geen punt (L29)."""
    uit = []
    mail = b.get("mail")
    if isinstance(mail, dict) and mail.get("dringend"):
        n = mail["dringend"]
        uit.append({"soort": "mail", "wat": f"{_meervoud(n, 'dringende mail', 'dringende mails')} zonder antwoord.",
                    "stap": "antwoorden op", "link": f"{BORD}/mail", "ref": "mail:dringend", "agent": "mail-regisseur"})
    voorstellen = b.get("voorstellen")
    apart = []
    if voorstellen:
        nieuw = [v for v in voorstellen if _is_nieuw(v, b)]
        apart = sorted(nieuw, key=lambda v: v["id"])[-2:]
        for v in apart:
            uit.append({"soort": "voorstel", "wat": f"Voorstel {v['id']} van {_wie(v)}: {v.get('actie') or ''}.",
                        "stap": "beslissen op", "link": f"{BORD}/agent/{v['naam']}", "ref": f"voorstel:{v['id']}",
                        "agent": v["naam"], "vingerafdruk": vingerafdruk(v)})
    dv = b.get("dagverslag")
    if isinstance(dv, dict) and dv.get("zonder_dossier"):
        n = dv["zonder_dossier"]
        uit.append({"soort": "toewijzen", "wat": f"{_meervoud(n, 'bron', 'bronnen')} van gisteren zonder dossier.",
                    "stap": "toewijzen op", "link": f"{BORD}/dag/{b['gisteren']}", "ref": f"bundel:{b['gisteren']}:(zonder dossier)",
                    "agent": "dagbundelaar"})
    rest = [v for v in voorstellen or [] if v not in apart]
    if rest:
        per = Counter(v["naam"] for v in rest).most_common()
        delen = ", ".join(f"{naam} {n}" for naam, n in per[:3]) + (f" en {len(per) - 3} andere" if len(per) > 3 else "")
        soort = "oudere" if not any(_is_nieuw(v, b) for v in rest) else "andere"
        uit.append({"soort": "voorstellen", "wat": f"{len(rest)} {soort} {'voorstel' if len(rest) == 1 else 'voorstellen'} ({delen}).",
                    "stap": "beslissen op", "link": BORD, "ref": "voorstel:" + ",".join(str(v["id"]) for v in rest), "agent": ""})
    noden = b.get("noden")
    if noden:
        oudste = min(noden, key=lambda n: tijdstip(n.get("ts")) or b["nu"])
        nieuw = sum(1 for n in noden if _sinds_vorig(n.get("ts"), b))
        agents = len({n.get("naam") for n in noden})
        uit.append({"soort": "noden", "wat": f"{_meervoud(len(noden), 'nood', 'noden')} voor jou bij {_meervoud(agents, 'agent', 'agents')}, "
                                             f"{nieuw} nieuw, oudste bij {_wie(oudste)}.",
                    "stap": "nakijken op", "link": f"{BORD}/agent/{oudste.get('naam')}",
                    "ref": "nood:" + ",".join(str(n.get("id")) for n in noden if n.get("id") is not None), "agent": oudste.get("naam") or ""})
    return uit


def punt_regel(nr, k):
    """'2. Voorstel 900 van ...: actie. Volgende stap: beslissen op <link>', hoogstens 150 tekens. Wat inkort, is de
    omschrijving; de stap en de link blijven altijd heel."""
    staart = f" Volgende stap: {k['stap']} {k['link']}"
    kop = f"{nr}. "
    return kop + _inkorten(k["wat"], PUNT_MAX - len(kop) - len(staart)) + staart


def kop(datum, n):
    """'Ochtendbericht do 22-10, 5 beslissingen', hoogstens 60 tekens."""
    d = datetime.fromisoformat(datum)
    aantal = "geen beslissingen" if not n else _meervoud(n, "beslissing", "beslissingen")
    return f"Ochtendbericht {DAGNAMEN[d.weekday()]} {d.strftime('%d-%m')}, {aantal}"[:KOP_MAX]


def gesprekken_tekst(per_bron):
    """'fathom 5 (privé 1), plaud 2' uit {bron: {tellend, prive, zonder_transcript}}; alleen aantallen, nooit namen."""
    delen = []
    for bron in sorted(per_bron):
        t = per_bron[bron]
        extra = [f"privé {t['prive']}"] if t.get("prive") else []
        if t.get("zonder_transcript"):
            extra.append(f"{t['zonder_transcript']} zonder tekst")
        delen.append(f"{bron} {t['tellend']}" + (f" ({', '.join(extra)})" if extra else ""))
    return ", ".join(delen) or "geen in de gesprekkentabel"


def verder_delen(b, onbekend):
    """De regel Verder in stukken: (verplicht, extra). Verplicht blijft altijd: de open aantallen, de Zoom-telling (M5),
    het weekend (J19), wat onbekend is (L29) en de verwijzing naar het bord. Extra valt eerst weg als het budget krap is."""
    open_ = []
    if b.get("voorstellen") is not None:
        open_.append(_meervoud(len(b["voorstellen"]), "voorstel", "voorstellen"))
    if b.get("noden") is not None:
        open_.append(_meervoud(len(b["noden"]), "nood", "noden"))
    verplicht = ["Verder: " + (" en ".join(open_) + " open" if open_ else "geen aantallen bekend")]
    extra = []
    if b.get("gesprekken") is not None:
        extra.append("Gesprekken gisteren: " + gesprekken_tekst(b["gesprekken"]))
    verplicht.append("Zoom gisteren: " + zoom_telling(b.get("zoom")))
    if b.get("zoom_teksten"):
        extra.append(f"{_meervoud(len(b['zoom_teksten']), 'Zoom-tekst', 'Zoom-teksten')} bewaard")
    if b.get("dagverslag") == "weekend":
        verplicht.append("Geen dagverslag in het weekend")
    if onbekend:
        verplicht.append("Onbekend: " + ", ".join(onbekend))
    verplicht.append(f"Alles op {BORD}")
    return verplicht, extra


def _verder(verplicht, extra):
    # de verwijzing naar het bord staat altijd laatst
    return ". ".join(verplicht[:-1] + extra + verplicht[-1:])


def opmaak(kandidaat, b, onbekend):
    """(tekst, gehouden punten, aantal weggevallen, verder). Hoogstens vijf punten. Past het niet binnen 720 na plat(),
    dan vallen eerst de extra stukken van Verder weg, daarna het laatste punt met '+n op het bord'."""
    gehouden = list(kandidaat[:MAX_PUNTEN])
    weg = len(kandidaat) - len(gehouden)
    verplicht, extra = verder_delen(b, onbekend)

    def bouw():
        regels = [punt_regel(i + 1, k) for i, k in enumerate(gehouden)]
        if weg:
            regels.append(f"+{weg} op het bord")
        return "\n".join(regels + [_verder(verplicht, extra)])

    tekst = bouw()
    while len(whatsapp.plat(tekst)) > BUDGET and extra:
        extra.pop()
        tekst = bouw()
    while len(whatsapp.plat(tekst)) > BUDGET and gehouden:
        gehouden.pop()
        weg += 1
        tekst = bouw()
    while len(whatsapp.plat(tekst)) > BUDGET and len(verplicht) > 2:
        # uiterste geval: ook zonder punten te lang (bv. een lange lijst onbekend); de verwijzing blijft
        verplicht.pop(-2)
        tekst = bouw()
    if len(whatsapp.plat(tekst)) > BUDGET:
        tekst = tekst[:BUDGET]
    return tekst, gehouden, weg, _verder(verplicht, extra)


def maak(b):
    """Van de gelezen bronnen naar het bericht. b komt uit regisseur.ochtend_bronnen(): datum, gisteren, nu, voorstellen,
    vorig, noden, dagverslag, mail, gesprekken, zoom, zoom_teksten, gelezen en onbekend (lijsten van bronnamen), plus
    keten_onbekend uit aan_de_beurt(). Geeft {kop, tekst, punten, verder, onbekend, bronnen, afgevallen}."""
    onbekend = list(dict.fromkeys(list(b.get("onbekend") or []) + list(b.get("keten_onbekend") or [])))
    kandidaat = kandidaten(b)
    tekst, gehouden, weg, verder = opmaak(kandidaat, b, onbekend)
    punten = [{"nr": i + 1, "soort": k["soort"], "ref": k["ref"], "agent": k["agent"], "link": k["link"],
               "vingerafdruk": k.get("vingerafdruk", "")} for i, k in enumerate(gehouden)]
    bronnen = {naam: {"stand": "ok", "gelezen": ts} for naam, ts in (b.get("gelezen") or {}).items()}
    for naam in b.get("onbekend") or []:
        bronnen[naam] = {"stand": "onbekend", "reden": (b.get("redenen") or {}).get(naam, "")}
    if b.get("voorstellen") is not None:
        bronnen.setdefault("voorstellen", {})["hoogste_voorstel"] = max((v["id"] for v in b["voorstellen"]), default=0)
    if b.get("gesprekken") is not None:
        bronnen.setdefault("gesprekken", {})["per_bron"] = b["gesprekken"]
    if b.get("dagverslag") == "weekend":
        bronnen["dagverslag"] = {"stand": "geen dagverslag in het weekend"}
    bronnen["zoom"] = dict(bronnen.get("zoom") or {}, telling=zoom_telling(b.get("zoom")))
    return {"kop": kop(b["datum"], len(gehouden)), "tekst": tekst, "punten": punten, "verder": verder,
            "onbekend": onbekend, "bronnen": bronnen,
            "afgevallen": [k["soort"] + ":" + k["ref"] for k in kandidaat[len(gehouden):]]}


def item(datum, bericht):
    """Het klaarzet-item (4.2). van zet bord.Agent.klaarzet zelf (regisseur). Geen datum of start in de inhoud (I2)."""
    return {"voor": "mehdi", "soort": "ochtendbericht", "sleutel": "", "titel": bericht["kop"], "uniek": f"ochtendbericht:{datum}",
            "inhoud": {"tekst": bericht["tekst"], "punten": bericht["punten"], "verder": bericht["verder"],
                       "bronnen": bericht["bronnen"], "onbekend": bericht["onbekend"]}}


# ------------------------------------------------------------------------------------------- taalmodel ---
NUL_WOORDEN = re.compile(r"\b(geen|niets|nul)\b", re.I)    # wat onbekend van leeg maakt (L29)


def _links(tekst):
    return Counter(x.rstrip(".") for x in LINK.findall(tekst or ""))


def _regels(tekst):
    return [r.rstrip() for r in (tekst or "").splitlines() if r.strip()]


def aanvaard(vast, nieuw):
    """Mag de herschrijving van het taalmodel de vaste tekst vervangen? Alleen de omschrijving van de punten mag anders
    (REG-04): regel N blijft punt N, met hetzelfde nummer vooraan, dezelfde cijferreeksen in dezelfde volgorde, dezelfde
    links en evenveel 'Volgende stap:', want vast_antwoord koppelt een nummer aan inhoud.punten. Elke andere regel (Verder
    met de aantallen, wat onbekend is, '+n op het bord') blijft woordelijk staan. 'onbekend' valt nergens weg en 'geen',
    'niets' of 'nul' komt er niet bij (L29). Geen gedachtestreepje, en de grens van 720 past."""
    if not isinstance(nieuw, str) or not nieuw.strip():
        return False
    if any(s in nieuw for s in STREEPJES):
        return False
    oud, nw = _regels(vast), _regels(nieuw)
    if len(oud) != len(nw):
        return False
    for a, b in zip(oud, nw):
        kop = PUNTREGEL.match(a)
        if not kop:
            if a != b:
                return False
            continue
        if not b.startswith(kop.group(0)):
            return False
        if re.findall(r"\d+", a) != re.findall(r"\d+", b) or _links(a) != _links(b):
            return False
        if a.count("Volgende stap:") != b.count("Volgende stap:"):
            return False
    if len(re.findall("onbekend", nieuw, re.I)) != len(re.findall("onbekend", vast, re.I)):
        return False
    if len(NUL_WOORDEN.findall(nieuw)) > len(NUL_WOORDEN.findall(vast)):
        return False
    return len(whatsapp.plat(nieuw)) <= BUDGET


# ------------------------------------------------------------------------------------ antwoord via WhatsApp ---
WA_MAX = 800                  # een antwoord via WhatsApp (R6); past in de sjabloonparameter van 900
GELEZEN = "\n\nGelezen: "


def whatsapp_kort(antwoord, aan):
    """Een antwoord van De Regisseur zoals het naar WhatsApp gaat: hoogstens 800 tekens (R6). Het volle antwoord staat in
    gesprek.antwoord op het bord (H1, REG-03); wie het naar WhatsApp stuurt (De Bode, antwoorden_terug), kort het hiermee
    in. Past het, dan ongewijzigd. Anders ingekort op een zinsgrens, dan de verwijzing naar de pagina van de agent en de
    regel Gelezen als laatste. antwoord: de tekst met de regel 'Gelezen: ...' aan het einde, zoals regisseur.py hem bewaart."""
    antwoord = antwoord or ""
    if len(antwoord) <= WA_MAX:
        return antwoord
    tekst, _, rest = antwoord.rpartition(GELEZEN)
    gelezen = "Gelezen: " + rest if tekst else ""
    tekst = tekst or antwoord
    verwijzing = f"Volledig op het bord: {BORD}/agent/{aan}"
    if len(gelezen) > 300:
        gelezen = gelezen[:296].rsplit("; ", 1)[0] + "; …"
    ruimte = WA_MAX - len(verwijzing) - len(gelezen) - 2
    romp = tekst[:ruimte]
    grenzen_ = [m.end() for m in re.finditer(r"[.!?](\s|$)|\n", romp)]
    if grenzen_:
        romp = romp[:grenzen_[-1]]
    elif " " in romp:
        romp = romp.rsplit(" ", 1)[0]
    return "\n".join(x for x in (romp.rstrip(), verwijzing, gelezen) if x)
