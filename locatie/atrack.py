"""Ontleden van @Track-berichten (Queclink), het protocol van de trackers.

Waarom een eigen ontleder en geen bestaande: het formaat is leesbare ASCII over
TCP, de velden staan in de handleiding, en zo blijft de ruwe regel van ons.

**De valkuil die dit bestand ontwijkt.** De veldvolgorde verschilt per
berichtsoort en per protocolversie. Een ontleder die velden op een vaste plaats
verwacht, breekt zodra de fabrikant er een veld bij zet; dat is precies het
restrisico dat in `01 Toestelkeuze` staat. Daarom zoeken we het **positieblok**
op zijn vorm: elk positiebericht bevat de reeks

    <accuracy>,<snelheid>,<azimut>,<hoogte>,<lengte>,<breedte>,<JJJJMMDDUUMMSS>

en het laatste 14-cijferige veld van de regel is de verzendtijd. Zo maakt het
niet uit hoeveel velden er vooraan of achteraan bijkomen.

Drie dingen die de rest van het systeem van hier moet overnemen:
  - `hdop` is **geen onzekerheid in meter**. 0 betekent "geen fix, oude positie
    herhaald" (`fix_geldig` is dan False) en zo'n punt mag nooit bewijzen dat
    iemand ergens nog aanwezig was.
  - `tst` is het moment van de **meting**, `verzonden` het moment van versturen.
    Bij een nagestuurd bericht liggen die ver uit elkaar.
  - `gebufferd` is True bij de kop `+BUFF`: dat is een meting die het toestel
    bewaarde toen er geen netwerk was. De inhoud is verder onveranderd.
  - Een bericht kan **meer dan één positie** dragen. FRI en ERI hebben vóór het
    eerste blok een veld `<Number>`; staat dat hoger dan 1, dan volgen de blokken
    elkaar op. Tot 04-10-2026 werd alleen het eerste gelezen. `posities` geeft ze
    nu allemaal; vinden we er minder dan gemeld, dan zegt `posities_volledig` dat,
    zodat de ontvanger het ruwe bericht bewaart en het onvolledig meldt.
  - Bij een bericht **zonder fix** (hdop 0) is `tst` de tijd van de laatste fix,
    niet van de gebeurtenis. Gemeten 03-10-2026: elk "motor aan" kwam binnen met
    de meettijd van het "motor uit" ervoor, en een vertraging gelijk aan de
    parkeerduur. Het werkelijke moment is de verzendtijd: `moment`.
"""
import re
from datetime import datetime, timezone

# Berichten waarin een positie zit en die wij als meetpunt bewaren.
# VGN/VGF zijn virtuele ontsteking aan en uit: het exacte moment van vertrekken
# en aankomen, en dus belangrijker dan welk vast interval ook.
GEBEURTENIS = {
    "FRI": "vast interval", "ERI": "vast interval (uitgebreid)",
    "VGN": "motor aan", "VGF": "motor uit",
    "STR": "begint te rijden", "STP": "stopt met rijden", "LSP": "lang stil",
    "GIN": "zone binnen", "GOT": "zone buiten", "GES": "zone (stil)",
    "RTL": "op verzoek", "DIS": "los", "IDN": "stationair", "IDF": "einde stationair",
    "BID": "baken gezien", "BIE": "baken weg", "BCS": "bluetooth verbonden",
    "TOW": "wegsleep", "HBM": "hard rijgedrag", "SPD": "snelheid", "DOG": "waakhond",
    "BPL": "batterij laag", "STT": "beweging", "MPN": "stroom aan", "MPF": "stroom uit",
    "PNA": "aan", "PFA": "uit", "SOS": "noodknop", "RMD": "roaming",
}
KOP = re.compile(r"^\+(RESP|BUFF|ACK):GT([A-Z]{3}),(.*)\$$", re.S)
TIJD14 = re.compile(r"^\d{14}$")
# Berichten die nooit een positie bevatten, wat de vorm ook doet vermoeden. ALM
# zijn teruggelezen instellingen: eindigen die op twee getallen voor de
# verzendtijd, dan zag de vormherkenning er een meting op breedte 0, lengte 0 in.
GEEN_POSITIE = {"ALM", "VER", "CID", "CSQ"}
# Berichten met een veld <Number> (aantal posities) vlak voor het eerste blok.
MET_AANTAL = {"FRI", "ERI"}
# De bewegingsstand in GTSTT (veld na de naam). Eerste cijfer: 1 = motor uit,
# 2 = motor aan, 4 = alleen de bewegingssensor; tweede: 1 = stil, 2 = in beweging.
# Gemeten 03-10-2026: 22 bij het wegrijden, 21 bij het stoppen, ook op snelheid 0.
TOESTAND = {"11": "motor uit, stil", "12": "motor uit, in beweging", "21": "motor aan, stil",
            "22": "motor aan, rijdt", "41": "stil", "42": "in beweging", "16": "wegsleep",
            "1A": "wegsleep (vals alarm)"}

# Wat een toestandsmelding over de motor zegt. Eén regel voor de tegel (status.py) en de
# dagindeling (app.py). Bij GTSTT beslist de stand zelf: eerste cijfer 1 = motor uit, 2 = aan,
# 4 = alleen de bewegingssensor, en dat zegt niets over de motor.
# Rit van 05-10-2026: om 03:45:48 kwamen GTVGF en GTSTT 11 op dezelfde seconde. Elke STT telde
# als 'in gebruik', dus zag de tegel motor uit en aan tegelijk ('onbekend') en liet het dagboek
# het parkeren daarna weg. GTVGL (ligging bij ontsteking) kwam op 03:43:38 als uit (71) en aan
# (70) op hetzelfde moment en blijft daarom buiten de toestand.
MOTOR_AAN = ("FRI", "ERI", "VGN", "STR", "IDN", "IDF")


def motorstand(berichtsoort, ruw=None):
    """'uit', 'aan', of None als de melding niets over de motor zegt."""
    if berichtsoort == "VGF":
        return "uit"
    if berichtsoort in MOTOR_AAN:
        return "aan"
    if berichtsoort == "STT" and ruw:
        code = ((ontleed(ruw) or {}).get("toestand_code") or "").upper()
        return {"1": "uit", "2": "aan"}.get(code[:1])
    return None


def _epoch(veld):
    """JJJJMMDDUUMMSS in UTC naar epoch. Het toestel meldt altijd in UTC."""
    try:
        d = datetime.strptime(veld, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return int(d.timestamp())


def _getal(v, komma=False):
    try:
        return float(v) if komma else int(v)
    except (TypeError, ValueError):
        return None


def _positieblok(velden, vanaf=6, tot=None):
    """Geeft de index van het veld met de meettijd, of None.

    Herkend aan de vorm: een tijd van 14 cijfers met daarvoor een breedte- en
    lengtegraad die in het bereik van de aarde liggen. De eerste treffer is de
    meting; het laatste 14-cijferige veld van de regel is de verzendtijd.
    """
    tot = len(velden) if tot is None else tot
    for i in range(max(vanaf, 6), tot):
        v = velden[i]
        if not TIJD14.match(v):
            continue
        breedte, lengte = _getal(velden[i - 1], True), _getal(velden[i - 2], True)
        if breedte is None or lengte is None:
            continue
        if -90 <= breedte <= 90 and -180 <= lengte <= 180 and _epoch(v):
            # Een lege hoogte of snelheid mag, maar het blok moet wel bestaan.
            return i
    return None


def _positie(velden, i):
    """Het positieblok waarvan de meettijd op index i staat."""
    hdop = _getal(velden[i - 6])
    uit = {
        "tst": _epoch(velden[i]),
        "lat": _getal(velden[i - 1], True),
        "lon": _getal(velden[i - 2], True),
        "hoogte": _getal(velden[i - 3], True),
        "azimut": _getal(velden[i - 4]),
        "snelheid": _getal(velden[i - 5], True),
        "hdop": hdop,
        # 0 betekent: de fix mislukte en het toestel herhaalt de laatst bekende
        # positie. Zo'n punt zegt niets over waar iemand nu is.
        "fix_geldig": bool(hdop),
        "mcc": velden[i + 1] if len(velden) > i + 1 else None,
        "mnc": velden[i + 2] if len(velden) > i + 2 else None,
        "lac": velden[i + 3] if len(velden) > i + 3 else None,
        "cel": velden[i + 4] if len(velden) > i + 4 else None,
        "satellieten": None,
    }
    # Na het celblok staat het positiemasker; bit 0 betekent dat het aantal gebruikte
    # satellieten volgt. Zonder dat bit is het volgende veld iets anders (bij FRI de
    # kilometerstand) en mag het nooit als satellieten gelezen worden.
    masker = velden[i + 5] if len(velden) > i + 5 else ""
    try:
        bit0 = bool(int(masker, 16) & 1)
    except ValueError:
        bit0 = False
    if bit0 and len(velden) > i + 6:
        sat = _getal(velden[i + 6])
        uit["satellieten"] = sat if sat is not None and 0 <= sat <= 72 else None
    return uit


def beweging(bericht, positie=None):
    """'automotive' of 'stationary', zoals de telefoon het in motion meestuurde.

    De dagindeling breekt een verblijf op 'automotive'. Voor de tracker leiden we
    het af: de bewegingsstand van GTSTT wint (die zegt het zelf), dan de gebeurtenis
    motor uit/aan, dan de snelheid.
    """
    positie = positie or bericht
    toestand = bericht.get("toestand") or ""
    if toestand.endswith("rijdt") or toestand.endswith("in beweging") or toestand.startswith("wegsleep"):
        return "automotive"
    if toestand:
        return "stationary"
    if bericht.get("gebeurtenis") == "motor uit":
        return "stationary"
    if (positie.get("snelheid") or 0) >= 5 or bericht.get("gebeurtenis") == "motor aan":
        return "automotive"
    return "stationary"


def ontleed(regel):
    """Eén @Track-regel naar een dict, of None als het geen bruikbaar bericht is.

    Geeft altijd de ruwe regel mee terug, zodat een veld dat wij vandaag nog niet
    uitpakken later alsnog te lezen is. Dezelfde afspraak als bij de telefoon.
    """
    regel = regel.strip()
    m = KOP.match(regel)
    if not m:
        return None
    kop, soort, rest = m.group(1), m.group(2), m.group(3)
    velden = rest.split(",")
    if len(velden) < 3:
        return None

    bericht = {
        "kop": kop, "soort": soort, "gebufferd": kop == "BUFF",
        "gebeurtenis": GEBEURTENIS.get(soort),
        "protocol": velden[0] or None,
        "imei": velden[1] or None,
        "naam": velden[2] or None,
        "ruw": regel,
        "teller": velden[-1] or None,
    }
    # Het laatste 14-cijferige veld is de verzendtijd van het toestel zelf.
    bericht["verzonden"] = next((_epoch(v) for v in reversed(velden) if TIJD14.match(v)), None)

    if soort == "STT" and len(velden) > 3:
        bericht["toestand"] = TOESTAND.get(velden[3].upper())
        bericht["toestand_code"] = velden[3] or None

    # Een bevestiging (+ACK) of een bericht uit GEEN_POSITIE is nooit een meting.
    i = None if kop == "ACK" or soort in GEEN_POSITIE else _positieblok(velden)
    if i is None:
        bericht.update(positie=False, posities=[], posities_gemeld=0, posities_volledig=True)
        return bericht

    gemeld = 1
    if soort in MET_AANTAL:
        n = _getal(velden[i - 7])
        if n is not None and n >= 1:
            gemeld = n
    # Volgende blokken op hun vorm zoeken, nooit voorbij de verzendtijd (het laatste
    # 14-cijferige veld). Een blok telt minstens zeven velden (nauwkeurigheid tot tijd),
    # dus de volgende meettijd ligt minstens zes velden verder.
    laatste = max((k for k, v in enumerate(velden) if TIJD14.match(v)), default=len(velden))
    indexen = [i]
    while len(indexen) < gemeld:
        k = _positieblok(velden, vanaf=indexen[-1] + 7, tot=laatste)
        if k is None:
            break
        indexen.append(k)
    posities = [_positie(velden, k) for k in indexen]
    for p in posities:
        p["motion"] = beweging(bericht, p)
    eerste = posities[0]
    bericht.update(eerste)
    bericht.update({
        "positie": True,
        "posities": posities,
        "posities_gemeld": gemeld,
        "posities_volledig": len(posities) == gemeld,
        # Het moment van de gebeurtenis. Zonder fix is tst de tijd van de laatste fix
        # (03-10-2026: "motor aan" met de meettijd van het "motor uit" ervoor).
        "moment": eerste["tst"] if eerste["fix_geldig"] else (bericht.get("verzonden") or eerste["tst"]),
    })
    return bericht
