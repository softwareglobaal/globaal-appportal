"""De dagvaststelling van De Dagbundelaar: een vast overzicht van een Brusselse dag (ontwerp docs/ontwerp-dagvaststelling.md
v1.9, opdracht van Mehdi 26-10-2026). Wat gepland stond en wat er echt gebeurde, wat er gebeurde zonder gepland te zijn,
en de communicatie langs mail, Zoom, WhatsApp en telefoon.

Pure functies: de runner (dagbundelaar.py) haalt de bronnen op en geeft ze als gewone lijsten door. Geen netwerk, geen
bord, geen schijf; zo dekken de tests (tests/test_dagvaststelling.py) elke regel.

Bewijs per afspraak (D6, E3): 'bevestigd' alleen met een gesprek op dat uur waarin een persoon van de afspraak zit (de
klant of een gast van buiten, nooit Mehdi, een firma of de eigenaar van de agenda); 'aanwijzing' bij de auto ter plaatse
(die bewijst geen gesprek) of bij alleen overlap in tijd voor een afspraak die niet ter plaatse is; anders 'geen spoor',
met de vraag of het doorging. Nooit 'niet doorgegaan' als feit. Een gesprek hoort alleen bij een afspraak via die
persoon; al de rest staat onder niet gepland, ook als het op hetzelfde uur viel.
Dubbels (D7, E1): alleen leidende rijen van de gesprekkentabel (geen dubbel_van), alleen gespreksbronnen; chats en mail
tellen nooit als gesprek, en een Plaud-opname die grotendeels samenvalt met een Zoom- of Fathom-gesprek telt niet apart.
Privé (D5, RZ2-01, RZ3-01): een rij is privé als de bron ze zo markeert, en alles van WhatsApp en telefoon is privé.
Van privé staat er alleen 'privé' met aantal en minuten; de namen staan in de gesprekkentabel (alleen beheer). Mehdi weet
niet wie 'Data uit Mehdi' ziet (26-10-2026), dus ook het bestand in Dropbox draagt geen privénamen.
Een bron die onbekend of onvolledig is, staat er zo; nooit als nul.
"""
import hashlib
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import privegrens

BRUSSEL = ZoneInfo("Europe/Brussels")
MARGE = timedelta(minutes=15)          # een gesprek dat zo dicht bij een afspraak ligt, hoort er mogelijk bij
MIN_GESPREK = 2                        # kortere oproepen of sessies zijn geen ongepland gesprek
MAX_NAAR = 5                           # zoveel ontvangers per postvak staan er bij naam; de rest als aantal
MAX_SITES = 5                          # zoveel sites staan bij naam in het blok Eigen werk en gezondheid
PLAUD_SAMEN = 0.5                      # zoveel van een Plaud-opname valt in een Zoom- of Fathom-gesprek: een dubbel
# Woorden die in titels en namen staan maar geen persoon aanwijzen: Mehdi zelf, firma's, soorten afspraken.
STOP = {"mehdi", "chegini", "zoom", "meeting", "impromptu", "fathom", "overleg", "intern", "interne", "bespreking",
        "plaatsbezoek", "bezoek", "klant", "buiten", "online", "prospect", "architects", "architecture", "invest",
        "unabo", "harmoniebouw", "melodie", "reistijd", "rijden", "afspraak", "call", "gesprek", "team", "automation",
        "privé", "prive", "groep", "oproep", "vooroverleg", "werf", "werfbezoek", "stad", "huis", "thuis", "info",
        "noreply", "admin", "kantoor", "office", "mail", "gmail", "hotmail", "outlook"}
# 31-10-2026: sms en iMessage (De Sms-wacht, sms:<sha1 gesprek>:<dag>, een chat) en Xelion (De Belwacht Xelion,
# xelion:<oid>, een oproep) erbij.
GESPREKSBRONNEN = ("zoom", "fathom", "plaud", "whatsapp", "telefoon", "sms", "xelion")
CHAT_VOORVOEGSELS = ("zoom:chat:", "whatsapp:", "sms:")
OPROEP_VOORVOEGSELS = ("whatsapp-oproep:", "telefoon:", "xelion:")
SECTIES = ("Gepland", "Niet gepland", "Werkgesprekken", "Communicatie", "Gemist zonder terugbellen", "Mail wacht op antwoord",
           "Morgen", "Eigen werk en gezondheid")
# T-0120 (ANGEL-2, DB-6): de blokken van de bundel voor Ai Angel. Een kop begint met zijn naam (Morgen draagt de datum).
BUNDELKOPPEN = ("Werkgesprekken", "Gemist zonder terugbellen", "Mail wacht op antwoord", "Morgen")
WERKBRONNEN = ("fathom", "plaud", "zoom")  # de opgenomen gesprekken met een samenvatting en actiepunten (ANGEL-2)
GEMIST = "buiten:gemist"               # dubbel_van van een oproep zonder gesprek (mac_gesprekken.GEMIST, xelion_wacht)
MAX_PUNTEN = 30                        # zoveel actiepunten per gesprek staan er bij naam; de rest als aantal
MAX_TEKST = 300                        # tekens per titel, samenvatting, actiepunt of onderwerp in de bundel
MAX_LIJST = 40                         # zoveel gemiste oproepen of mails per dag staan er; de rest als aantal
# Het begin van een actiepuntregel in het blok Werkgesprekken (contract met mehdi_agent.actiepunten, ANGEL-2):
#   "  - actiepunt [<uniek>; <dossier>; wie: ...; tegen: ...; voor: ...; op UU:MM:SS; klaar in Fathom]: <wat>"
ACTIEPUNT = "actiepunt ["
ONBEKENDE_BELLER = {"", "onbekend", "onbekend nummer", "nummer verborgen"}


# ------------------------------------------------------------------------------------------------- dagen ---
def gisteren(nu):
    """De Brusselse kalenderdag voor die van nu. De VM loopt in UTC: om 23:30 UTC is het in Brussel al de volgende dag."""
    if nu.tzinfo is None:
        raise ValueError("nu zonder tijdzone")
    return (nu.astimezone(BRUSSEL).date() - timedelta(days=1)).isoformat()


def venster(nu, dagen):
    """De dagen die een ronde vaststelt: gisteren en de dagen ervoor, nieuwste eerst (D10, E5). Geen watermerk op
    tijdstempels: elke dag van het venster wordt opnieuw berekend en alleen een andere inhoud geeft een nieuwe versie."""
    g = datetime.fromisoformat(gisteren(nu)).date()
    return [(g - timedelta(days=i)).isoformat() for i in range(max(int(dagen), 1))]


# ------------------------------------------------------------------------------------------------ tijden ---
def _tijd(iso):
    t = datetime.fromisoformat(str(iso))
    return t if t.tzinfo else t.replace(tzinfo=BRUSSEL)


def uur_van(epoch):
    return datetime.fromtimestamp(epoch, BRUSSEL).strftime("%H:%M")


def brusselse_dag(iso):
    return _tijd(iso).astimezone(BRUSSEL).date().isoformat()


def afspraak_venster(a):
    return _tijd(a["start"]), _tijd(a.get("einde") or a["start"])


def gesprek_venster(g):
    """Begin en einde van een rij uit de gesprekkentabel: datum en start (HH:MM) in Brussel, minuten (minstens een).
    In het uur dat bij de wintertijd twee keer voorkomt, draagt start de UTC-afstand ('02:30+01:00', De WhatsApp-wacht
    en De Belwacht, Codex P5 bij fase 2); zonder afstand geldt het eerste van de twee."""
    start = str(g.get("start") or "00:00")
    uur, minuut = (int(x) for x in start[:5].split(":"))
    begin = datetime.fromisoformat(str(g["datum"])[:10]).replace(hour=uur, minute=minuut, tzinfo=BRUSSEL)
    afstand = re.fullmatch(r"([+-])(\d{2}):(\d{2})", start[5:])
    if afstand:
        teken = 1 if afstand.group(1) == "+" else -1
        zone = timezone(teken * timedelta(hours=int(afstand.group(2)), minutes=int(afstand.group(3))))
        begin = begin.replace(tzinfo=zone)
    # In UTC: twee tijden in dezelfde zone vergelijkt Python op de klok, zonder fold; zo telt het juiste uur.
    begin = begin.astimezone(timezone.utc)
    return begin, begin + timedelta(minutes=max(int(g.get("minuten") or 0), 1))


def overlapt(a, b, marge=MARGE):
    (s1, e1), (s2, e2) = a, b
    return s1 - marge < e2 and s2 < e1 + marge


def _samen(a, b):
    """Welk deel van a in b valt (0 tot 1)."""
    (s1, e1), (s2, e2) = a, b
    deel = (min(e1, e2) - max(s1, s2)).total_seconds()
    return max(deel, 0) / max((e1 - s1).total_seconds(), 60)


# ----------------------------------------------------------------------------------------------- soorten ---
def is_leidend(g):
    """Telregel Z10: een rij met dubbel_van telt niet (een gesprek in Zoom en Fathom is een gesprek)."""
    return not str(g.get("dubbel_van") or "").strip()


def soort(g):
    """'mail', 'chat', 'oproep', 'gesprek' of 'anders' voor een rij uit de gesprekkentabel (E1: alleen gespreksbronnen)."""
    u, bron = str(g.get("uniek") or ""), str(g.get("bron") or "")
    if bron == "mail" or u.startswith("mail:"):
        return "mail"
    if bron not in GESPREKSBRONNEN:
        return "anders"
    if u.startswith(OPROEP_VOORVOEGSELS):
        return "oproep"
    if u.startswith(CHAT_VOORVOEGSELS):
        return "chat"
    return "gesprek"


def is_prive(g):
    """RZ3-01 en D5: de privévlag of afdeling privé; alles van WhatsApp, telefoon, sms en Xelion is privé. De regel staat
    op één plek, in privegrens.py (T-0120 VOL-2), voor De Communicatiebundelaar en de wachtenpagina ook."""
    return privegrens.is_prive(g)


PARTIKELS = {"de", "den", "der", "van", "von", "la", "le", "du", "del", "da", "di", "ten", "ter", "het", "en"}
MIN_GEDEELD = 2                        # zoveel naamdelen deelt een persoon van de afspraak met een gesprekspersoon (F3)


def naamdelen(tekst):
    """De naamdelen van een naam (minstens drie letters), zonder Mehdi, firma's, soortwoorden en partikels. Een
    e-mailadres geeft zijn lokale deel ('jan.peeters@x.be' wordt 'jan peeters')."""
    tekst = re.sub(r"([\w.+-]+)@[\w.-]+", lambda m: m.group(1).replace(".", " ").replace("_", " "), str(tekst or ""))
    # zonder accenten: 'Céline' en 'Celine' zijn dezelfde naam
    tekst = "".join(c for c in unicodedata.normalize("NFKD", tekst) if not unicodedata.combining(c))
    return {w for w in (x.casefold() for x in re.findall(r"[^\W\d_]{3,}", tekst)) if w not in STOP and w not in PARTIKELS}


def namen(tekst):
    """De afzonderlijke namen in een tekst, elk als verzameling naamdelen: de stukken tussen komma's, streepjes en haakjes.
    Wat tussen haakjes staat (een afdeling, '(H-AI & ICT)') telt niet."""
    zonder = re.sub(r"\([^)]*\)|\[[^\]]*\]", ",", str(tekst or ""))
    stukken = re.split(r"[,;/+&]|\s[-\u2013]\s|:|\s(?:en|and|met|und|et)\s", zonder, flags=re.I)
    return [d for d in (naamdelen(x) for x in stukken) if d]


def personen_van_afspraak(a):
    """E3 en F3: de namen die de afspraak aanwijst: het stuk na de code tussen haken en de gasten van buiten, nooit wat
    voor de code staat ('Mehdi: Collega: [HA-KB] ...' is de eigenaar van de agenda). Een lijst van namen."""
    titel = str(a.get("titel") or "")
    rest = titel.split("]", 1)[1] if "]" in titel else titel.split(":")[-1]
    uit = namen(rest)
    for d in a.get("deelnemers") or []:
        uit += namen(d)
    return uit


def zelfde_persoon(afspraak_namen, personen):
    """F3: alleen aantoonbaar dezelfde persoon: een naam van de afspraak en een gesprekspersoon delen minstens
    MIN_GEDEELD naamdelen (voornaam en familienaam). Een gedeelde voornaam of een plaatsnaam alleen volstaat niet."""
    return any(len(a & g) >= MIN_GEDEELD for a in afspraak_namen for g in namen(personen))


def bron_label(g):
    u, bron = str(g.get("uniek") or ""), str(g.get("bron") or "")
    if u.startswith("whatsapp-oproep:"):
        return "WhatsApp-oproep"
    if u.startswith("telefoon:"):
        return "telefoon"
    if u.startswith("xelion:"):
        return "Xelion"
    return {"zoom": "Zoom", "fathom": "Fathom", "plaud": "Plaud"}.get(bron, bron or "gesprek")


def gesprek_tekst(g):
    begin, _ = gesprek_venster(g)
    wie = "privé" if is_prive(g) else (g.get("personen") or "onbekend")
    return f"{begin.astimezone(BRUSSEL):%H:%M} {bron_label(g)}, {int(g.get('minuten') or 0)} min, {wie}"


def gesprekken_van_dag(dag, rijen):
    """De leidende gesprekken en oproepen van de dag, zonder Plaud-dubbels van een Zoom- of Fathom-gesprek. Een Zoom-rij
    met zo'n Plaud-dubbel krijgt 'opname': 'plaud' (F6): het gesprek telt een keer, en wel als gesprek met opname."""
    praat = [dict(g) for g in rijen if str(g.get("datum") or "")[:10] == dag and is_leidend(g)
             and soort(g) in ("gesprek", "oproep")]
    vast = [g for g in praat if g.get("bron") in ("zoom", "fathom")]
    uit = []
    for g in praat:
        if g.get("bron") == "plaud":
            z = next((z for z in vast if _samen(gesprek_venster(g), gesprek_venster(z)) >= PLAUD_SAMEN), None)
            if z is not None:
                z["opname"] = "plaud"
                continue
        uit.append(g)
    return uit


# ------------------------------------------------------------------------------------------------- bewijs ---
def bewijs(a, gesprekken, locatie=None):
    """Het bewijs voor een afspraak. gesprekken: van gesprekken_van_dag. locatie: de uitkomst van
    locatie_wacht.vergelijk_agenda voor deze afspraak ({'uitkomst': 'doorgegaan'|'niet_gezien'|'zonder_adres'|'onbekend',
    'tekst': ...}), of None als het geen afspraak ter plaatse is (online, intern).
    Geeft {'uitkomst', 'grond', 'gesprekken': [uniek]}; alleen die gesprekken horen bij de afspraak (E3)."""
    venster_a = afspraak_venster(a)
    wie = personen_van_afspraak(a)
    op_uur = sorted((g for g in gesprekken if overlapt(venster_a, gesprek_venster(g))), key=lambda g: gesprek_venster(g)[0])
    met_persoon = [g for g in op_uur if zelfde_persoon(wie, g.get("personen"))]
    if met_persoon:
        return {"uitkomst": "bevestigd", "grond": "; ".join(gesprek_tekst(g) for g in met_persoon),
                "gesprekken": [g["uniek"] for g in met_persoon]}
    ter_plaatse = locatie is not None
    locatie = locatie or {}
    if locatie.get("uitkomst") == "doorgegaan":
        return {"uitkomst": "aanwijzing", "grond": f"{locatie.get('tekst') or 'auto ter plaatse'}; geen gesprek als bewijs",
                "gesprekken": []}
    if op_uur and not ter_plaatse:
        return {"uitkomst": "aanwijzing", "grond": "op dat uur een gesprek zonder persoon van de afspraak: "
                + "; ".join(gesprek_tekst(g) for g in op_uur[:3]) + (f" en {len(op_uur) - 3} meer" if len(op_uur) > 3 else ""),
                "gesprekken": []}
    grond = {"niet_gezien": locatie.get("tekst") or "auto niet gezien op de plek",
             "zonder_adres": "geen bruikbaar adres om de locatie te toetsen",
             "onbekend": locatie.get("tekst") or "locatie niet gelezen"}.get(locatie.get("uitkomst"),
                                                                        "geen gesprek, oproep of locatie")
    return {"uitkomst": "geen spoor", "grond": grond + ". Ging dit door?", "gesprekken": []}


# ------------------------------------------------------------------------------------------- vaststelling ---
def vaststellen(dag, afspraken, ongelezen, gesprekken, locatie_per_id, bezoeken, zoomstand, mail, kanalen,
                prive_afspraak, locatiestand="", chatstand=None, eigen=None, fotos=None, bundel=None):
    """De vaststelling van een dag als gewone gegevens.

    afspraken: de afspraken van die dag, met de archiefagenda's (zonder fout, hele dag of rit); ongelezen: de agenda's die
    niet gelezen konden worden (ook 'archief'), of None als de agenda helemaal niet gelezen werd.
    gesprekken: rijen uit de gesprekkentabel voor die datum (alle; hier worden de leidende gekozen).
    locatie_per_id: {afspraak-id: uitkomst} voor elke afspraak ter plaatse ({'uitkomst': 'onbekend'} als de locatie niet
    gelezen werd). bezoeken: projectbezoeken en verblijven zonder afspraak ({'van', 'tot', 'minuten', 'waar', 'soort'}
    met soort project, twijfel of elders), of None (locatie niet gelezen); locatiestand: de stand van het dagboek
    (afgesloten, voorlopig, ...).
    zoomstand: 'volledig', 'ondergrens' of 'onbekend'. mail: van mail_telling, of None. kanalen: {'whatsapp': stand,
    'telefoon': stand} voor deze dag, met stand 'aangesloten', 'niet aangesloten' of een andere tekst ('stil sinds ...',
    'onbekend voor deze dag'): D2 en F5, de hartslag van de wacht en haar dekking van die dag, niet het bestaan van rijen.
    prive_afspraak: functie afspraak -> bool (agenda_wacht.is_prive).
    eigen (31-10-2026, Mehdi: Wispr, websites en Apple Watch): {'wispr': {dictaten, woorden, seconden} of None,
    'websites': {bezoeken, sites, top} of None, 'gezondheid': [regels] of None}; None is onbekend, nooit nul. Zonder
    eigen (oude aanroep) blijft het blok weg.
    kanalen kent sinds 31-10-2026 ook 'sms' (De Sms-wacht) en 'xelion' (De Belwacht Xelion). fotos: {'aantal', 'plekken'}
    van De Fotowacht voor die dag, of None als ze die dag niet las (onbekend, nooit nul).
    bundel (T-0120, ANGEL-2 en DB-6, de inhoud voor Ai Angel): {'inhoud_van': rij -> inhoud (zie werkgesprekken),
    'morgen': de afspraken van de dag erna (zoals afspraken), 'mail_open': de open mailpunten van /api/mail/open of None
    (niet gelezen)}. gesprekken draagt dan ook de rijen van de dagen erna, tot vandaag (voor het terugbellen). Zonder
    bundel (oude aanroep) blijven de blokken Werkgesprekken, Gemist zonder terugbellen, Mail wacht op antwoord en Morgen
    weg."""
    alle_rijen = gesprekken                # 'gesprekken' wordt hieronder de telling
    praat = gesprekken_van_dag(dag, gesprekken)
    agenda_stand = "onbekend" if ongelezen is None else ("onvolledig" if ongelezen else "volledig")
    gepland, gebruikt = [], set()
    for a in sorted(afspraken, key=lambda x: x.get("start") or ""):
        loc = (locatie_per_id or {}).get(a.get("id"))
        b = bewijs(a, praat, loc)
        gebruikt.update(b["gesprekken"])
        gepland.append({"id": a.get("id"), "tijd": str(a.get("start") or "")[11:16], "titel": a.get("titel") or "",
                        "prive": bool(prive_afspraak(a)), "uitkomst": b["uitkomst"], "grond": b["grond"]})
    ongepland = [g for g in sorted(praat, key=lambda g: gesprek_venster(g)[0])
                 if g["uniek"] not in gebruikt and int(g.get("minuten") or 0) >= MIN_GESPREK]
    leidend = [g for g in gesprekken if str(g.get("datum") or "")[:10] == dag and is_leidend(g)]
    xel_gemist = [g for g in gesprekken if str(g.get("datum") or "")[:10] == dag and g.get("bron") == "xelion"
                  and str(g.get("dubbel_van") or "") == "buiten:gemist"]
    # TEL-5: ook de gemiste en niet beantwoorde iPhone-oproepen, zoals bij Xelion (ze tellen niet als gesprek)
    tel_gemist = [g for g in gesprekken if str(g.get("datum") or "")[:10] == dag and g.get("bron") == "telefoon"
                  and str(g.get("dubbel_van") or "") == "buiten:gemist"]
    # Een Zoom-gesprek met een Fathom-opname staat in de tabel als leidende Fathom-rij (de Zoom-rij is dubbel_van):
    # daarom een totaal over Zoom, Fathom en Plaud, elk gesprek een keer, en geen aparte telling per bron als 'Zoom'.
    vergaderd = [g for g in praat if g.get("bron") in ("zoom", "fathom", "plaud")]
    met_opname = [g for g in vergaderd if g.get("bron") in ("fathom", "plaud") or g.get("opname")]
    gesprekken = {"aantal": len(vergaderd), "minuten": sum(int(g.get("minuten") or 0) for g in vergaderd),
                  "alleen_zoom": len(vergaderd) - len(met_opname), "met_opname": len(met_opname)}
    kanalen = kanalen or {}
    wa = [g for g in leidend if g.get("bron") == "whatsapp"]
    extra = {}
    if bundel is not None:
        volgende = (datetime.fromisoformat(dag).date() + timedelta(days=1)).isoformat()
        extra = {"werkgesprekken": werkgesprekken(dag, alle_rijen, bundel.get("inhoud_van") or (lambda g: None)),
                 "gemist_open": gemist_open(dag, alle_rijen),
                 "mail_open": mail_open(dag, bundel.get("mail_open"), bundel.get("prive_postvakken") or ()),
                 "morgen": {"dag": volgende, "stand": agenda_stand,
                            "afspraken": [{"tijd": str(a.get("start") or "")[11:16], "titel": a.get("titel") or "",
                                           "prive": bool(prive_afspraak(a))}
                                          for a in sorted(bundel.get("morgen") or [], key=lambda x: x.get("start") or "")]}}
    tel = [g for g in praat if g.get("bron") == "telefoon"]
    sms = [g for g in leidend if g.get("bron") == "sms" and soort(g) == "chat"]
    xel = [g for g in praat if g.get("bron") == "xelion"]
    return {
        "dag": dag,
        "agenda": {"stand": agenda_stand, "ongelezen": sorted(ongelezen or []), "afspraken": gepland},
        "niet_gepland": {"voorbehoud": agenda_stand != "volledig", "gesprekken": ongepland, "bezoeken": bezoeken,
                         "locatiestand": locatiestand},
        "gesprekken": gesprekken,
        "zoom": {"stand": zoomstand or "onbekend", "chatstand": chatstand or zoomstand or "onbekend",
                 "chats": len([g for g in leidend if str(g.get("uniek")).startswith("zoom:chat:")])},
        "whatsapp": {"stand": kanalen.get("whatsapp") or "niet aangesloten",
                     "gesprekken": len([g for g in wa if soort(g) == "chat"]),
                     "berichten": sum(_berichten(g) for g in wa if soort(g) == "chat"),
                     "oproepen": len([g for g in wa if soort(g) == "oproep"]),
                     # WA-3: een inkomende oproep die WhatsApp niet gemist noemt, maar zonder duur (op de gsm opgenomen)
                     "zonder_duur": len([g for g in wa if soort(g) == "oproep" and "duur onbekend" in str(g.get("thema") or "")]),
                     "minuten": sum(int(g.get("minuten") or 0) for g in wa if soort(g) == "oproep")},
        "telefoon": {"stand": kanalen.get("telefoon") or "niet aangesloten", "oproepen": len(tel),
                     "minuten": sum(int(g.get("minuten") or 0) for g in tel), "gemist": len(tel_gemist)},
        "sms": {"stand": kanalen.get("sms") or "niet aangesloten", "gesprekken": len(sms),
                "berichten": sum(_berichten(g) for g in sms)},
        "xelion": {"stand": kanalen.get("xelion") or "niet aangesloten", "oproepen": len(xel),
                   "minuten": sum(int(g.get("minuten") or 0) for g in xel), "gemist": len(xel_gemist)},
        "fotos": fotos,
        "mail": mail,
        **extra,
        **({"eigen": eigen} if eigen is not None else {}),
    }


# ------------------------------------------------------------------------- de bundel voor Ai Angel (T-0120) ---
def _een_regel(t, n=MAX_TEKST):
    """Een tekst op een regel van hoogstens n tekens, op een woordgrens ingekort."""
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " (ingekort)"


def _veld(t, n=120):
    """Een waarde in de haken van een actiepuntregel: zonder [, ] of ; (die scheiden de velden)."""
    return _een_regel(re.sub(r"[\[\];]", " ", str(t or "")), n)


def prive_regel(minuten):
    """Het enige wat een privégesprek in de bundel geeft (zoals De Gespreksanalist en De Plaudwacht)."""
    try:
        m = int(float(minuten or 0))
    except (TypeError, ValueError):
        m = 0
    return f"privégesprek, {m} min" if m > 0 else "privégesprek, duur onbekend"


def werkgesprekken(dag, rijen, inhoud_van):
    """ANGEL-2 en VOL-5 (T-0120): per opgenomen gesprek van de dag (de leidende Fathom-, Plaud- en Zoom-rijen, zonder de
    Plaud-dubbel van een Zoom- of Fathom-gesprek, minstens MIN_GESPREK minuten) de titel, firma en dossier, samenvatting,
    actiepunten en de verwijzing (de uniek: fathom:<id>, plaud:<id>, zoom:meeting:<uuid>).
    Privé (is_prive van de rij) geeft alleen 'privégesprek, N min'; dan wordt inhoud_van niet gevraagd, zodat er niets
    gelezen wordt. inhoud_van(rij) geeft (de runner leest, dagbundelaar.gespreksinhoud) een dict:
      prive: True als De Gespreksanalist of het label van De Archivaris het gesprek privé noemt (dan ook alleen de regel);
      firma, soort, dossier, dossier_bewijs: zoals De Gespreksanalist (herkomst), '' als onbekend;
      samenvatting: tekst, of None (onbekend); van: 'Fathom' of 'De Gespreksanalist';
      actiepunten: lijst van {wat, wie, tegen, voor, tijd, klaar}, [] (er is er geen), of None (onbekend);
      reden: waarom samenvatting of actiepunten onbekend zijn ('nog niet geanalyseerd', ...).
    Onbekend is nooit 'geen actiepunten'."""
    uit = []
    for g in sorted((g for g in gesprekken_van_dag(dag, rijen) if g.get("bron") in WERKBRONNEN),
                    key=lambda g: gesprek_venster(g)[0]):
        tijd, minuten = f"{gesprek_venster(g)[0].astimezone(BRUSSEL):%H:%M}", int(g.get("minuten") or 0)
        if minuten < MIN_GESPREK:
            continue
        if is_prive(g):
            uit.append({"uniek": g["uniek"], "tijd": tijd, "prive": True, "minuten": minuten})
            continue
        i = inhoud_van(g) or {}
        if i.get("prive"):
            uit.append({"uniek": g["uniek"], "tijd": tijd, "prive": True, "minuten": minuten})
            continue
        uit.append({"uniek": g["uniek"], "tijd": tijd, "prive": False, "minuten": minuten, "bron": bron_label(g),
                    "titel": g.get("thema") or "", "personen": g.get("personen") or "", "opname": g.get("opname") or "",
                    **{k: i.get(k) or "" for k in ("firma", "soort", "dossier", "dossier_bewijs", "van", "reden")},
                    "samenvatting": i.get("samenvatting"), "actiepunten": i.get("actiepunten")})
    return uit


def dossier_label(w):
    """Het dossier van een werkgesprek zoals het bij elk actiepunt staat: 'UNABO 2405', 'HA, zonder dossier', 'zonder
    dossier'."""
    firma = _veld(w.get("firma"), 40)
    if w.get("dossier"):
        return _veld(f"{firma} {w['dossier']}".strip(), 60)
    return f"{firma}, zonder dossier" if firma else "zonder dossier"


def actiepunt_regel(w, p):
    """Een actiepunt op een regel, met de verwijzing en het dossier vooraan (contract met mehdi_agent.actiepunten)."""
    velden = [_veld(w["uniek"], 160), dossier_label(w)]
    for sleutel, kop in (("wie", "wie: "), ("tegen", "tegen: "), ("voor", "voor: ")):
        waarde = _veld(p.get(sleutel), 80)
        if waarde and not (sleutel == "voor" and waarde == "onbekend"):
            velden.append(kop + waarde)
    if _veld(p.get("tijd"), 12):
        velden.append(f"op {_veld(p.get('tijd'), 12)}")
    if p.get("klaar"):
        velden.append("klaar in Fathom")
    return f"  - {ACTIEPUNT}{'; '.join(velden)}]: {_een_regel(p.get('wat'))}"


def werkgesprek_regels(w):
    """De regels van een werkgesprek in het blok Werkgesprekken."""
    if w["prive"]:
        return [f"- {w['tijd']} {prive_regel(w['minuten'])}"]
    titel = _een_regel(w.get("titel") or "zonder onderwerp", 120)
    wie = _een_regel(w.get("personen"), 120)
    r = [f"- {w['tijd']} {w['bron']}, {w['minuten']} min: {titel}" + (f", met {wie}" if wie else "")
         + (" (ook opgenomen met Plaud)" if w.get("opname") == "plaud" else "") + f" [{_veld(w['uniek'], 160)}]"]
    firma = " ".join(x for x in (w.get("firma"), w.get("soort")) if x) or "onbekend"
    dossier = (f"{w['dossier']}" + (f" ({w['dossier_bewijs']})" if w.get("dossier_bewijs") else "")) if w.get("dossier") \
        else "onbekend"
    r.append(f"  - firma: {_een_regel(firma, 60)}; dossier: {_een_regel(dossier, 80)}")
    van = w.get("van") or "Fathom"
    reden = w.get("reden") or "onbekend"
    if w["samenvatting"] is None and w["actiepunten"] is None:
        r.append(f"  - samenvatting en actiepunten: {reden}")
        return r
    r.append(f"  - samenvatting ({van}): {_een_regel(w['samenvatting'], 2 * MAX_TEKST)}" if w["samenvatting"]
             else f"  - samenvatting: {reden if w['samenvatting'] is None else 'geen'}")
    punten = w["actiepunten"]
    if punten is None:
        r.append(f"  - actiepunten: {reden}")
    elif not punten:
        r.append(f"  - actiepunten: geen ({van} vond er geen)")
    else:
        r += [actiepunt_regel(w, p) for p in punten[:MAX_PUNTEN]]
        if len(punten) > MAX_PUNTEN:
            r.append(f"  - en {len(punten) - MAX_PUNTEN} actiepunten meer (zie de bron)")
    return r


def _beller(g):
    return re.sub(r"\s+", " ", str(g.get("personen") or "")).strip().casefold()


def gemist_open(dag, rijen):
    """DB-6 (T-0081): de gemiste inkomende oproepen van de dag (telefoon, WhatsApp en Xelion: dubbel_van buiten:gemist,
    inkomend) zonder een latere oproep met dezelfde persoon: geen uitgaande oproep (ook een die niet beantwoord werd telt
    als poging) en geen gesprek. rijen: ook de dagen erna, tot vandaag. Alles van die kanalen is privé: alleen het uur en
    het kanaal, nooit een naam of een bericht (X8). Een verborgen of onbekend nummer: terugbellen onbekend."""
    oproepen = [g for g in rijen if str(g.get("uniek") or "").startswith(OPROEP_VOORVOEGSELS)]
    uit = []
    for g in sorted(oproepen, key=lambda g: gesprek_venster(g)[0]):
        thema = str(g.get("thema") or "")
        if str(g.get("datum") or "")[:10] != dag or str(g.get("dubbel_van") or "") != GEMIST \
                or "inkomend" not in thema or "gemist" not in thema or "niet gemist" in thema:
            continue
        wie, begin = _beller(g), gesprek_venster(g)[0]
        if wie in ONBEKENDE_BELLER:
            stand = "terugbellen onbekend (nummer onbekend of verborgen)"
        else:
            def contact(x):
                dv = str(x.get("dubbel_van") or "")
                return "uitgaand" in str(x.get("thema") or "") or not dv or not dv.startswith("buiten:")
            if any(gesprek_venster(x)[0] > begin and _beller(x) == wie and contact(x) for x in oproepen):
                continue
            stand = "geen terugbelpoging gezien"
        uit.append({"tijd": f"{begin.astimezone(BRUSSEL):%H:%M}", "kanaal": bron_label(g), "stand": stand})
    return uit


def mail_open(dag, punten, prive_postvakken=()):
    """DB-6 (T-0081): de mails van die dag die nog op opvolging wachten, uit /api/mail/open: dezelfde lijst als De
    Mailregisseur, /mail en het werkverslag van de mailwachten. None: niet gelezen (onbekend, nooit 'niets'). Alleen wat
    gelijk blijft tot de mail beantwoord is: postvak, soort, afzender en onderwerp; nooit het aantal werkdagen (dat
    verandert elke dag en gaf elke nacht een nieuwe versie van elke dag) en nooit de tekst. Een privépostvak alleen als
    aantal."""
    if punten is None:
        return None
    van_dag = []
    for p in punten:
        try:
            if brusselse_dag(p.get("datum_iso") or p.get("datum") or "") == dag:
                van_dag.append(p)
        except (TypeError, ValueError):
            continue
    uit, prive = [], {}
    def orde(p):
        o = p.get("orde")
        return o if isinstance(o, int) and not isinstance(o, bool) else 9
    for p in sorted(van_dag, key=lambda p: (str(p.get("postvak") or ""), orde(p), str(p.get("datum_iso") or ""))):
        pv = str(p.get("postvak") or "")
        if pv in prive_postvakken:
            prive[pv] = prive.get(pv, 0) + 1
            continue
        uit.append({"postvak": pv, "soort": str(p.get("soort_label") or p.get("soort") or ""),
                    "van": str(p.get("van_naam") or p.get("van") or ""), "onderwerp": str(p.get("onderwerp") or ""),
                    "onzeker": p.get("opvolging") == "onzeker"})
    return {"mails": uit, "prive": prive}


def eigen_regels(e):
    """Het blok 'Eigen werk en gezondheid': alleen aantallen en sitenamen, nooit de tekst van een dictaat of een adres."""
    r = []
    w = e.get("wispr")
    if w is None:
        r.append("- Wispr Flow: onbekend (de Wispr-wacht las deze dag niet)")
    else:
        r.append(f"- Wispr Flow: {int(w.get('dictaten') or 0)} dictaten, {int(w.get('woorden') or 0)} woorden, "
                 f"{round(float(w.get('seconden') or 0) / 60)} min ingesproken")
    s = e.get("websites")
    if s is None:
        r.append("- websites: nog niet aangesloten (Browserwacht op de laptop)")
    else:
        top = ", ".join(f"{x[0]} ({x[1]})" for x in (s.get("top") or [])[:MAX_SITES])
        r.append(f"- websites: {int(s.get('bezoeken') or 0)} bezoeken op {int(s.get('sites') or 0)} sites"
                 + (f"; meest: {top}" if top else ""))
    if "youtube" in e:
        y = e.get("youtube")
        if y is None:
            r.append("- YouTube: onbekend (YouTube-wacht las deze dag niet)")
        else:
            m = y.get("minuten")
            titels = "; ".join(f"{str(x[0])[:80]} ({x[1]})" for x in (y.get("top") or [])[:MAX_SITES])
            r.append(f"- YouTube: {int(y.get('videos') or 0)} video's" + (f", {int(m)} min" if m is not None else "")
                     + (f"; meest: {titels}" if titels else ""))
    g = e.get("gezondheid")
    if not g:
        r.append("- gezondheid: geen Apple Watch-gegevens (Health Auto Export stuurt nog niets)")
    else:
        r.append("- gezondheid (Apple Watch):")
        r += [f"  - {x}" for x in g]
    return r


def _berichten(g):
    m = re.match(r"\s*(\d+)\s+bericht", str(g.get("thema") or ""))
    return int(m.group(1)) if m else 0


# --------------------------------------------------------------------------------------------------- mail ---
def mail_sleutel(postvak, k):
    """MAIL-4 (T-0120): de vaste sleutel van een bericht, gelijk voor een kop uit de postbus en een rij uit mailbericht. De
    Message-ID; anders de Message-ID uit uniek (postvak:Message-ID, de sleutel van de wacht sinds 26-09-2026; de kolom
    message_id bestaat pas sinds 19-10-2026 en een oudere rij wordt niet aangevuld); anders, voor een bericht zonder
    Message-ID, een sleutel uit postvak, tijdstip, afzender en onderwerp. Niet de uid: die is alleen uniek binnen een map
    en verandert als een wacht het bericht naar een andere map sorteert (Codex-toets 1 en 2). None: geen sleutel."""
    mid = (k.get("message_id") or "").strip()
    if mid:
        return mid
    rest = str(k.get("uniek") or "")
    if rest.lower().startswith(str(postvak).lower() + ":") and "@" in rest[len(postvak) + 1:]:
        return rest[len(postvak) + 1:].strip()
    try:
        t = _tijd(k["datum"]).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (KeyError, TypeError, ValueError):
        return None
    van = str(k.get("van") or "").strip().lower()
    onderwerp = re.sub(r"\s+", " ", str(k.get("onderwerp") or "")).strip()[:300]      # zoals postvak.schoon
    return "zonder-id:" + hashlib.sha1(f"{str(postvak).lower()}|{t}|{van}|{onderwerp}".encode()).hexdigest()


def mail_telling(dag, ontvangen, verzonden, soorten=None):
    """ontvangen en verzonden: {postvak: {'berichten': [koppen], 'onvolledig': [reden]}}, met koppen zoals de postbus ze
    geeft (datum, message_id, aan). De runner leest zelf de mappen, dus de leesdekking van deze ronde is gekend (E4).
    soorten: {message_id: soort} uit mailbericht, alleen om de soort te tonen. Geeft per postvak het aantal voor precies
    die Brusselse dag (binnen een postvak ontdubbeld), en een totaal ontdubbeld per Message-ID over alle postvakken (D8):
    een mail aan twee adressen van Mehdi telt in elk postvak, maar een keer in het totaal. Een postvak met een reden is
    onvolledig, en dan ook het totaal. 'dekking' {'vanaf', 'gemaakt'} (een kopie in een bestand) toetst deze dag: begint
    de kopie na de dag ervoor (de kopie zoekt op UTC-datum, de dag is Brussels), of werd ze gemaakt voor het einde van de
    dag, dan is het postvak voor deze dag onvolledig (overleg 26-10-2026, X2, lenzen 5 en 9). MAIL-3 (T-0120): een richting
    die voor een postvak niet gelezen werd (een adres waaruit een wacht alleen antwoordt), is None, nooit 0."""
    per, totaal = {}, {"in": set(), "uit": set()}
    soorten = soorten or {}
    einde = datetime.combine(datetime.fromisoformat(dag).date() + timedelta(days=1), datetime.min.time(), BRUSSEL)
    for richting, bron in (("in", ontvangen), ("uit", verzonden)):
        for postvak, v in sorted((bron or {}).items()):
            p = per.setdefault(postvak, {"binnen": None, "soorten": {}, "verzonden": None, "naar": [], "onvolledig": []})
            sleutel = "binnen" if richting == "in" else "verzonden"
            p[sleutel] = p[sleutel] or 0                       # MAIL-3: deze richting is gelezen
            redenen = list(v.get("onvolledig") or [])
            dek = v.get("dekking") or {}
            if dek.get("vanaf") and dek["vanaf"] > (einde.date() - timedelta(days=2)).isoformat():
                redenen.append("kopie dekt deze dag niet")
            try:
                gemaakt = datetime.fromisoformat(dek["gemaakt"]) if dek.get("gemaakt") else None
            except ValueError:
                gemaakt = None
            if gemaakt is not None and gemaakt.tzinfo is not None and gemaakt < einde:
                redenen.append("kopie van voor het einde van de dag")
            p["onvolledig"] += [r for r in redenen if r not in p["onvolledig"]]
            hier = set()
            for k in v.get("berichten") or []:
                if not k.get("datum") or brusselse_dag(k["datum"]) != dag:
                    continue
                mid = mail_sleutel(postvak, k) or hashlib.sha1(
                    f"{k.get('datum')}{k.get('onderwerp')}{k.get('aan')}".encode()).hexdigest()
                if mid in hier:
                    continue
                hier.add(mid)
                totaal[richting].add(mid)
                if richting == "in":
                    p["binnen"] += 1
                    s = soorten.get(mid)
                    if s:
                        p["soorten"][s] = p["soorten"].get(s, 0) + 1
                else:
                    p["verzonden"] += 1
                    p["naar"] += [_naam(x) for x in (k.get("aan") or [])[:3]]
    return {"postvakken": per, "binnen": len(totaal["in"]), "verzonden": len(totaal["uit"]),
            "onvolledig": any(p["onvolledig"] for p in per.values())}


def _naam(adresregel):
    naam = re.sub(r"\s*<[^>]*>\s*", "", str(adresregel)).strip().strip('"')
    return naam or re.sub(r".*<([^>]*)>.*", r"\1", str(adresregel)).strip()


# ----------------------------------------------------------------------------------------------- tekst ---
def _en(delen):
    return delen[0] if len(delen) == 1 else ", ".join(delen[:-1]) + " en " + delen[-1]


def kanaalregel(naam, stand, delen):
    """Een regel van een Mac- of belkanaal. delen: [(getal, tekst, naam als het onbekend is)]. Onbekend is nooit 0 (WA-6,
    T-0120): op een dag die de wacht niet als gelezen meldt, is een nul onbekend, en wat wel gezien is, blijft een
    ondergrens. Een gelezen dag ('aangesloten') toont elk getal, ook 0."""
    if stand == "aangesloten":
        return f"- {naam}: " + ", ".join(t for _, t, _ in delen) + " gezien"
    gezien = [t for n, t, _ in delen if n]
    if not gezien:
        return f"- {naam}: onbekend ({stand})"
    onbekend = [o for n, _, o in delen if not n]
    return f"- {naam}: gezien " + ", ".join(gezien) + (f"; {_en(onbekend)} onbekend" if onbekend else "") + f" ({stand})"


def bundel_regels(v, prive_postvakken=()):
    """T-0120: de blokken voor Ai Angel, per kop: Werkgesprekken (ANGEL-2) gaat voor Communicatie, de andere (DB-6)
    erna. Alleen als vaststellen ze kreeg (bundel)."""
    blokken = {}
    if "werkgesprekken" in v:
        r = ["## Werkgesprekken", "",
             "Samenvatting en actiepunten van Fathom of De Gespreksanalist, niet als bron voor contract of verslag (het "
             "transcript telt); tussen haken de verwijzing naar het gesprek.", ""]
        for w in v["werkgesprekken"]:
            r += werkgesprek_regels(w)
        if not v["werkgesprekken"]:
            r.append("- geen opgenomen gesprek van minstens 2 min gezien")
        blokken["Werkgesprekken"] = r
    if "gemist_open" in v:
        r = ["## Gemist zonder terugbellen", ""]
        ongelezen = [naam for naam, k in (("telefoon", "telefoon"), ("WhatsApp", "whatsapp"), ("Xelion", "xelion"))
                     if (v.get(k) or {}).get("stand") != "aangesloten"]
        for x in v["gemist_open"][:MAX_LIJST]:
            r.append(f"- {x['tijd']} {x['kanaal']} (privé): {x['stand']}")
        if len(v["gemist_open"]) > MAX_LIJST:
            r.append(f"- en {len(v['gemist_open']) - MAX_LIJST} meer")
        if not v["gemist_open"]:
            r.append("- onbekend (telefoon, WhatsApp en Xelion niet gelezen voor deze dag)" if len(ongelezen) == 3
                     else "- geen gezien" + (f" ({_en(ongelezen)} niet gelezen voor deze dag)" if ongelezen else ""))
        elif ongelezen:
            r.append(f"- onvolledig: {_en(ongelezen)} niet gelezen voor deze dag")
        blokken["Gemist zonder terugbellen"] = r
    if "mail_open" in v:
        r = ["## Mail wacht op antwoord", ""]
        m = v["mail_open"]
        if m is None:
            r.append("- niet gelezen (de lijst van de mailwachten was niet te lezen)")
        else:
            for x in m["mails"][:MAX_LIJST]:
                r.append(f"- {x['postvak']}: {_een_regel(x['soort'], 30) or 'open'}, van {_een_regel(x['van'], 80) or 'onbekend'}: "
                         f"{_een_regel(x['onderwerp'], 160) or 'zonder onderwerp'}" + (" (mogelijk al beantwoord)" if x["onzeker"] else ""))
            if len(m["mails"]) > MAX_LIJST:
                r.append(f"- en {len(m['mails']) - MAX_LIJST} meer")
            for pv, n in sorted(m["prive"].items()):
                r.append(f"- {pv}: {n} {'mail' if n == 1 else 'mails'} (privé)")
            if not m["mails"] and not m["prive"]:
                r.append("- geen mail van deze dag wacht nog")
        blokken["Mail wacht op antwoord"] = r
    if "morgen" in v:
        mo = v["morgen"]
        kop = f"## Morgen, {mo['dag']}"
        if mo["stand"] == "onbekend":
            kop += " (agenda niet gelezen: onbekend)"
        elif mo["stand"] == "onvolledig":
            kop += " (agenda onvolledig)"
        r = [kop, ""]
        for a in mo["afspraken"]:
            r.append(f"- {a['tijd']} (privé)" if a["prive"] else f"- {a['tijd']} {_een_regel(a['titel'], 200)}")
        if not mo["afspraken"]:
            r.append("- geen afspraken" if mo["stand"] == "volledig" else "- geen afspraken gelezen")
        blokken["Morgen"] = r
    return blokken


def tekst(v, prive_postvakken=(), over=None, voorlopig=None):
    """Het overzicht als markdown, zonder privénamen of privétitels: dezelfde tekst gaat naar het bord, het bestand en
    Dropbox (E6). over: regels voor het blok 'Over deze vaststelling' (versie, tijd, bronnen); dat blok telt niet mee in
    de hash. voorlopig (ANGEL-7): het uur van een voorlopige bundel van vandaag ('10:00'); die gaat nooit naar Dropbox."""
    d = v["dag"]
    r = [f"# Dag {d} voorlopig (stand {voorlopig})" if voorlopig else f"# Dag {d} vastgesteld", ""]
    blokken = bundel_regels(v, prive_postvakken)
    ag = v["agenda"]
    kop = "## Gepland"
    if ag["stand"] == "onbekend":
        kop += " (agenda niet gelezen: onbekend)"
    elif ag["stand"] == "onvolledig":
        kop += " (agenda onvolledig, niet gelezen: " + ", ".join(ag["ongelezen"]) + ")"
    r += [kop, ""]
    if not ag["afspraken"]:
        r.append("- geen afspraken" if ag["stand"] == "volledig" else "- geen afspraken gelezen")
    for x in ag["afspraken"]:
        if x["prive"]:
            r.append(f"- {x['tijd']} (privé): {x['uitkomst']}" + (". Ging dit door?" if x["uitkomst"] == "geen spoor" else ""))
        else:
            r.append(f"- {x['tijd']} {x['titel']}: {x['uitkomst']} ({x['grond']})")
    ng = v["niet_gepland"]
    r += ["", "## Niet gepland" + (" (onder voorbehoud: agenda niet volledig gelezen)" if ng["voorbehoud"] else ""), ""]
    for g in ng["gesprekken"]:
        r.append(f"- {gesprek_tekst(g)}")
    if ng["bezoeken"] is None:
        r.append("- locatie: niet gelezen")
    else:
        if ng.get("locatiestand") and ng["locatiestand"] != "afgesloten":
            r.append(f"- locatie {ng['locatiestand']}: bezoeken kunnen nog veranderen")
        for b in ng["bezoeken"]:
            r.append(f"- {b.get('van')} tot {b.get('tot')} ({b.get('minuten')} min) {_plek(b)}")
    if not ng["gesprekken"] and ng["bezoeken"] == []:
        r.append("- niets gevonden")
    if "Werkgesprekken" in blokken:
        r += [""] + blokken["Werkgesprekken"]
    r += ["", "## Communicatie", ""]
    z, g = v["zoom"], v["gesprekken"]
    # L1 en L2 (ontwerp v1.9): een volledig aantal is met deze bronnen niet te bewijzen: De Fathomwacht schrijft tot
    # veertien dagen terug, en een dagregel die nog klaarstaat blijft herzienbaar. Het overzicht telt dus wat gezien is (per
    # definitie een ondergrens) en zegt apart wat De Zoomwacht over haar eigen lezing zegt. Komt er later iets bij, dan
    # volgt een nieuwe versie (de nachtronde herberekent veertien dagen). Onbekend blijft onbekend, nooit nul.
    zoomwacht = {"volledig": "volledig gelezen", "voorlopig": "nog niet afgesloten", "ondergrens": "onvolledig gelezen",
                 "onbekend": "stand onbekend"}.get(z["stand"], z["stand"])
    if z["stand"] == "onbekend" and not g["aantal"]:
        r.append("- gesprekken in Zoom, Fathom en Plaud: onbekend (De Zoomwacht: stand onbekend)")
    else:
        r.append(f"- gesprekken gezien in Zoom, Fathom en Plaud: {g['aantal']}, {g['minuten']} min ({g['met_opname']} met "
                 f"opname, {g['alleen_zoom']} alleen in Zoom); De Zoomwacht: {zoomwacht}")
    cs = z.get("chatstand") or z["stand"]
    if cs == "onbekend" and not z["chats"]:
        r.append("- Zoom-chat: onbekend")
    else:
        r.append(f"- Zoom-chat: {z['chats']} chatgesprek(ken) gezien")
    w = v["whatsapp"]
    if w["stand"] == "niet aangesloten":
        r.append("- WhatsApp: nog niet aangesloten")
    else:
        # WA-3: de oproepen die WhatsApp niet gemist noemt maar zonder duur, staan apart (ze tellen als oproep, 0 min)
        k = int(w.get("zonder_duur") or 0)
        r.append(kanaalregel("WhatsApp", w["stand"], [
            (w["gesprekken"], f"{w['berichten']} berichten in {w['gesprekken']} gesprekken", "berichten"),
            (w["oproepen"], f"{w['oproepen']} oproepen" + (f" (waarvan {k} zonder gekende duur)" if k else ""), "oproepen"),
            (w["minuten"], f"{w['minuten']} min", "minuten")]))
    t = v["telefoon"]
    if t["stand"] == "niet aangesloten":
        r.append("- telefoon: nog niet aangesloten")
    else:
        r.append(kanaalregel("telefoon", t["stand"], [(t["oproepen"], f"{t['oproepen']} oproepen", "oproepen"),
                                                      (t["minuten"], f"{t['minuten']} min", "minuten"),
                                                      (t.get("gemist", 0), f"{t.get('gemist', 0)} gemist", "gemiste oproepen")]))
    sm = v.get("sms") or {"stand": "niet aangesloten", "gesprekken": 0, "berichten": 0}
    if sm["stand"] == "niet aangesloten":
        r.append("- sms en iMessage: nog niet aangesloten")
    elif sm["stand"] != "aangesloten" and not sm["gesprekken"]:
        r.append(f"- sms en iMessage: onbekend ({sm['stand']})")
    else:
        r.append(f"- sms en iMessage: {sm['berichten']} berichten in {sm['gesprekken']} gesprekken gezien"
                 + ("" if sm["stand"] == "aangesloten" else f" ({sm['stand']})"))
    x = v.get("xelion") or {"stand": "niet aangesloten", "oproepen": 0, "minuten": 0, "gemist": 0}
    if x["stand"] == "niet aangesloten":
        r.append("- Xelion: nog niet aangesloten")
    else:
        r.append(kanaalregel("Xelion", x["stand"], [(x["oproepen"], f"{x['oproepen']} oproepen", "oproepen"),
                                                    (x["minuten"], f"{x['minuten']} min", "minuten"),
                                                    (x["gemist"], f"{x['gemist']} gemist", "gemiste oproepen")]))
    f = v.get("fotos")
    if f is None:
        r.append("- foto's: onbekend (De Fotowacht las deze dag niet)")
    else:
        r.append(f"- foto's: {int(f.get('aantal') or 0)} foto's op {int(f.get('plekken') or 0)} plekken"
                 + (f", {int(f['zonder_plaats'])} zonder plaats" if f.get("zonder_plaats") else ""))
    if v["mail"] is None:
        r.append("- mail: niet gelezen")
    else:
        m = v["mail"]
        r.append(f"- mail: {m['binnen']} binnen, {m['verzonden']} verzonden (uniek over alle postvakken"
                 + ("; onvolledig)" if m["onvolledig"] else ")"))
        for postvak, p in sorted(m["postvakken"].items()):
            soorten = ", ".join(f"{n} {s}" for s, n in sorted(p["soorten"].items()))
            # MAIL-3: een richting die niet gelezen werd, is geen nul
            regel = (f"  - {postvak}: " + ("binnen: niet gelezen" if p["binnen"] is None else f"{p['binnen']} binnen"
                                            + (f" ({soorten})" if soorten else "")) + ", "
                     + ("verzonden: niet gelezen" if p["verzonden"] is None else f"{p['verzonden']} verzonden"))
            if p["onvolledig"]:
                regel += " (onvolledig: " + "; ".join(p["onvolledig"]) + ")"
            if p["naar"] and postvak not in prive_postvakken:
                naar = list(dict.fromkeys(p["naar"]))
                regel += "; naar " + ", ".join(naar[:MAX_NAAR]) + (f" en {len(naar) - MAX_NAAR} meer" if len(naar) > MAX_NAAR else "")
            r.append(regel)
    for kop in ("Gemist zonder terugbellen", "Mail wacht op antwoord", "Morgen"):
        if kop in blokken:
            r += [""] + blokken[kop]
    if "eigen" in v:
        r += ["", "## Eigen werk en gezondheid", ""] + eigen_regels(v["eigen"])
    r += ["", "## Over deze vaststelling", ""]
    r += [f"- {x}" for x in over or []]
    return "\n".join(r).rstrip() + "\n"


def _plek(b):
    """F2: alleen een bevestigd of waarschijnlijk werkproject bij naam; een twijfelgeval of een andere plek niet (die kan
    privé zijn). De plek zelf staat in het locatielogboek."""
    if b.get("soort") == "project":
        return str(b.get("waar") or "projectbezoek")
    if b.get("soort") == "twijfel":
        return "projectbezoek, project onzeker (kies op het locatiedashboard)"
    return "verblijf zonder afspraak (plek in het locatielogboek)"


def versie_van(t):
    """Het versienummer uit het blok 'Over deze vaststelling' van een bestand, of None (F8: de versie volgt het bestand)."""
    t = t or ""
    if "\n## Over deze vaststelling" not in t:
        return None
    m = re.search(r"^- versie (\d+),", t.split("\n## Over deze vaststelling", 1)[1], re.M)
    return int(m.group(1)) if m else None


def kern(t):
    """De vaste inhoud: alles voor het blok 'Over deze vaststelling'."""
    return t.split("\n## Over deze vaststelling")[0]


def inhoud_hash(t):
    """De hash van de vaste inhoud (E6): gelijk bij bord, bestand en Dropbox-kopie van dezelfde versie."""
    return hashlib.sha256(kern(t).encode()).hexdigest()[:16]


def wijzigingen(oud, nieuw):
    """Welke secties van de vaste inhoud veranderden tegenover de vorige versie."""
    def secties(t):
        uit, naam = {}, ""
        for regel in kern(t or "").split("\n"):
            if regel.startswith("## "):
                # 'Niet gepland' eerst: anders valt het onder 'Gepland' niet, maar wel een kop als 'Gepland (agenda ...)'
                naam = next((s for s in ("Niet gepland", "Gepland", "Communicatie") + BUNDELKOPPEN
                             if regel[3:].startswith(s)), regel[3:])
            uit[naam] = uit.get(naam, "") + regel + "\n"
        return uit
    a, b = secties(oud), secties(nieuw)
    return [s for s in SECTIES if a.get(s) != b.get(s)]
