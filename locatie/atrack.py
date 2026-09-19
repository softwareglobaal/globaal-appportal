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


def _positieblok(velden):
    """Geeft de index van het veld met de meettijd, of None.

    Herkend aan de vorm: een tijd van 14 cijfers met daarvoor een breedte- en
    lengtegraad die in het bereik van de aarde liggen. De eerste treffer is de
    meting; het laatste 14-cijferige veld van de regel is de verzendtijd.
    """
    for i, v in enumerate(velden):
        if i < 6 or not TIJD14.match(v):
            continue
        breedte, lengte = _getal(velden[i - 1], True), _getal(velden[i - 2], True)
        if breedte is None or lengte is None:
            continue
        if -90 <= breedte <= 90 and -180 <= lengte <= 180 and _epoch(v):
            # Een lege hoogte of snelheid mag, maar het blok moet wel bestaan.
            return i
    return None


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

    i = _positieblok(velden)
    if i is None:
        bericht["positie"] = False
        return bericht

    hdop = _getal(velden[i - 6])
    bericht.update({
        "positie": True,
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
    })
    # Na het celblok staat het positiemasker en, als dat bit aanstaat, het aantal
    # gebruikte satellieten. Alleen overnemen als het er als zodanig uitziet.
    sat = _getal(velden[i + 6]) if len(velden) > i + 6 else None
    bericht["satellieten"] = sat if sat is not None and 0 <= sat <= 72 else None
    return bericht
