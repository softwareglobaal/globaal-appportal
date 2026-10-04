"""Bronbeleid van het Locatielogboek: welke metingen meetellen, op één plek.

Besluit van Mehdi (opdracht v1.2, 04-10-2026). De telefoonmetingen zijn bewust
gestopt. Alleen de tracker in de auto meet, sinds 3 oktober 2026, en alleen die
reeks telt: voor de kaart, het dagboek, de projectherkenning, de export, de
bewaking en wat een agent te lezen krijgt. Oude bewegingsdata (de telefoon van
9-9 tot 3-10, de afgeleide dagboeken en de uit die metingen geleerde plekken)
wordt nergens ingelezen, vergeleken, gevalideerd of herberekend. Die bestanden
blijven bewaard, buiten de actieve verwerking. Later komt er een draagbare
tracker bij, met een eigen ingangsdatum.

Twee voorwaarden, allebei nodig, voor een punt meetelt:

1. **De meettijd** (tst, het moment van de meting volgens het toestel) ligt op of
   na de ingang van zijn bron. Nooit de ontvangsttijd: een oude meting die later
   binnenkomt wordt daardoor geen nieuwe meting.
2. **Het toestel** is het toestel dat voor die bron is vastgelegd. Een vrije
   bronnaam is niet genoeg: wie morgen een ander toestel "auto" noemt in
   ATRACK_IMEIS, krijgt het niet in de reeks zonder dat het hier staat.

Het IMEI zelf staat hier niet. De poort van de ontvanger staat open op het
internet en het IMEI is het enige dat een bericht toelaat; het staat alleen in
ATRACK_IMEIS in `~/appportal/.env`. Hier staat een vingerafdruk (sha256, eerste
16 tekens), genoeg om het toestel te herkennen, niet om het na te bootsen.

Projectadressen en projectkennis vallen hier niet onder: die volgen hun eigen
bron, ongeacht hoe oud het project is. Deze grens gaat over bewegingsmetingen.

Werkt ook onder Python 3.9 (het Mac-script draait op /usr/bin/python3).
"""
import hashlib
import os
from datetime import date, datetime, time as dtijd, timedelta
from zoneinfo import ZoneInfo

VERSIE = "1.0"
BRUSSEL = ZoneInfo("Europe/Brussels")

# De operationele start: 3 oktober 2026, 00:00 Belgische tijd (= 2 oktober 22:00 UTC).
STARTGRENS = "2026-10-03T00:00:00+02:00"

# status: actief | uit_gebruik | niet_aangesloten. Alleen actief telt mee en kan alarm geven.
BRONNEN = {
    "auto": {
        "rol": "auto",
        "status": "actief",
        "label": "Tracker in de auto",
        "toestel": "Queclink GV500CG in de diagnosepoort van de Opel Astra 2HHE117",
        "protocol": "@Track over TCP, container app-locatie-tracker, buiten poort 5000",
        "ingang": STARTGRENS,
        "toestel_sha256": "6362aeefb2d74833",
        # Wat het toestel doet, zoals ingesteld per sms op 03-10-2026 (zie
        # 'Data uit Mehdi/Locatie/04 Tracker in de auto, instellen'). De bewaking
        # leest dit: een lange stilte na 'motor uit' is hier verwacht, geen uitval.
        "meetmodus": {
            "rijden": "elke 30 seconden een punt (AT+GTFRI)",
            "motor_uit": ("niets tot de motor weer aanslaat: Power Saving Mode staat op de fabriekswaarde 1 "
                          "(AT+GTCFG nooit gestuurd); het interval van 900 s werkt pas in stand 2"),
            "levensteken": "geen hartslag: rapportagemodus 2 opent per bericht een korte verbinding",
            "buffer": "aan (buffermodus 1); wat zonder netwerk gemeten is komt na met kop +BUFF en zijn eigen meettijd",
            "teruggelezen": False,   # AT+GTRTO is nog niet gestuurd; de tabel toestelbericht is leeg
        },
        # Hoe lang na de laatste meting zonder 'motor uit' er iets mis is. Rijdend komt er elke
        # 30 s een punt; een netwerkgat wordt nagestuurd, dus pas na een uur alarm.
        "stil_rijdend_minuten": 60,
        # Na 'motor uit' kan het toestel niets laten horen (spaarstand 1). Pas na zoveel uur
        # zeggen we dat we niet weten of het nog leeft; dat is een vraag, geen storing.
        "geparkeerd_onbekend_uren": 72,
    },
    "iphone": {
        "rol": "persoon",
        "status": "uit_gebruik",
        "label": "Telefoon (OwnTracks)",
        "toestel": "OwnTracks op Mehdi's iPhone",
        "protocol": "HTTPS POST /pub",
        "ingang": None,
        "sinds": "2026-10-03",
        "reden": "bewust gestopt door Mehdi; ontbreken is normaal en geeft geen alarm",
    },
    "draagbaar": {
        "rol": "persoon",
        "status": "niet_aangesloten",
        "label": "Draagbare tracker",
        "toestel": "nog te kopen; ontvangstprotocol pas vast te leggen na de keuze van het toestel",
        "protocol": None,
        "ingang": None,
        "reden": "nog niet aangesloten; krijgt een eigen ingangsdatum en de rol persoon",
    },
}

ROLLEN = {"auto": "bewijst waar de auto stond, niet waar Mehdi was",
          "persoon": "het gedragen toestel; volgt de persoon"}


# ------------------------------------------------------------------ tijd

def moment(iso):
    """ISO-tijd met zone naar epoch."""
    return int(datetime.fromisoformat(iso).timestamp())


def lokaal(tst):
    return datetime.fromtimestamp(int(tst), BRUSSEL)


def vandaag():
    return datetime.now(BRUSSEL).date()


def dagranden(datum):
    """(begin, eind) van een Belgische kalenderdag in epoch.

    Een dag is niet altijd 24 uur. Op de laatste zondag van oktober duurt hij 25
    uur, eind maart 23. Tot 04-10-2026 rekende de tegel begin + 24 uur, waardoor
    op 25-10 het laatste uur in geen enkele dag viel en in maart een uur in twee.
    """
    d = date.fromisoformat(str(datum)[:10])
    begin = datetime.combine(d, dtijd(0), tzinfo=BRUSSEL)
    eind = datetime.combine(d + timedelta(days=1), dtijd(0), tzinfo=BRUSSEL)
    return int(begin.timestamp()), int(eind.timestamp())


def eerste_dag():
    """De eerste kalenderdag van de actieve reeks, als 'JJJJ-MM-DD'."""
    return lokaal(moment(STARTGRENS)).date().isoformat()


def dag_toegestaan(datum):
    """Valt deze dag (deels) in de actieve reeks? Dagen ervoor bestaan niet voor de verwerking."""
    return str(datum)[:10] >= eerste_dag()


def dagen_vanaf_grens(tot=None):
    """Alle dagen van de eerste dag van de reeks tot en met `tot` (standaard vandaag)."""
    tot = date.fromisoformat(str(tot)[:10]) if tot else vandaag()
    d = date.fromisoformat(eerste_dag())
    uit = []
    while d <= tot:
        uit.append(d.isoformat())
        d += timedelta(days=1)
    return uit


# --------------------------------------------------------------- toestellen

def vingerafdruk(toestel):
    return hashlib.sha256(str(toestel or "").strip().encode()).hexdigest()[:16]


def toestellen_uit_env(waarde=None):
    """ATRACK_IMEIS ('imei:naam,imei:naam') naar {imei: naam}."""
    uit = {}
    for stuk in (os.environ.get("ATRACK_IMEIS", "") if waarde is None else waarde).split(","):
        if ":" in stuk:
            imei, naam = stuk.split(":", 1)
            if imei.strip():
                uit[imei.strip()] = naam.strip() or "auto"
    return uit


def toestel_kort(toestel):
    """Voor op een scherm: alleen de laatste vier cijfers."""
    t = str(toestel or "")
    return ("…" + t[-4:]) if len(t) > 4 else t


def toestel_klopt(bron, toestel):
    beleid = BRONNEN.get(bron) or {}
    verwacht = beleid.get("toestel_sha256")
    return bool(verwacht) and bool(toestel) and vingerafdruk(toestel) == verwacht


def ingang(bron):
    """Epoch vanaf wanneer deze bron meetelt, of None als hij niet meetelt."""
    beleid = BRONNEN.get(bron) or {}
    if beleid.get("status") != "actief" or not beleid.get("ingang"):
        return None
    return max(moment(beleid["ingang"]), moment(STARTGRENS))


def actieve_bronnen():
    return [b for b in BRONNEN if ingang(b) is not None]


def rol(bron):
    return (BRONNEN.get(bron) or {}).get("rol") or "onbekend"


def telt_mee(punt):
    """(True, '') als dit punt in de actieve reeks hoort, anders (False, reden).

    punt is een dict met minstens bron, toestel en tst. Dit is dé regel; de SQL in
    sql_actief() doet hetzelfde en de tests houden ze gelijk.
    """
    bron = punt.get("bron")
    beleid = BRONNEN.get(bron)
    if not beleid:
        return False, f"onbekende bron {bron!r}"
    if beleid.get("status") != "actief":
        return False, f"bron {bron} is {beleid.get('status')}"
    if not toestel_klopt(bron, punt.get("toestel")):
        return False, f"toestel hoort niet bij bron {bron}"
    grens = ingang(bron)
    try:
        tst = int(punt.get("tst"))
    except (TypeError, ValueError):
        return False, "onbekende meettijd"
    if tst < grens:
        return False, "meettijd voor de ingang van de bron"
    return True, ""


def sql_actief(toestellen=None, alias=""):
    """(WHERE-deel, parameters) dat alleen punten van de actieve reeks doorlaat.

    toestellen: {imei: naam} (standaard uit ATRACK_IMEIS). Een IMEI telt alleen als
    zijn naam de bron is en zijn vingerafdruk in het beleid staat.
    """
    toestellen = toestellen_uit_env() if toestellen is None else toestellen
    p = (alias + ".") if alias else ""
    delen, waarden = [], []
    for bron in actieve_bronnen():
        imeis = sorted(i for i, naam in toestellen.items() if naam == bron and toestel_klopt(bron, i))
        if not imeis:
            continue
        delen.append(f"({p}bron = ? AND {p}toestel IN ({','.join('?' * len(imeis))}) AND {p}tst >= ?)")
        waarden += [bron] + imeis + [ingang(bron)]
    if not delen:
        return "0", []
    return "(" + " OR ".join(delen) + ")", waarden


# ---------------------------------------------------------------- planning

# De vaste tijden in Belgische tijd. De VM draait in UTC en zijn cron kent geen eigen
# tijdzone (Debian-cron negeert CRON_TZ), dus staat elke taak er op beide mogelijke
# UTC-uren en kijkt het script zelf of het nu het juiste Belgische uur is
# (--om HH:MM). Zie mijnagents-runner/planning/locatie.cron; een test houdt beide gelijk.
PLANNING = {
    "dagboek": {"wat": "dagboek van vandaag (voorlopig) en de vorige dagen afsluiten", "waar": "VM, locatie_wacht.py",
                "tijden": ["21:30"]},
    "controle": {"wat": "bronbewaking per actieve tracker", "waar": "VM, locatie_wacht.py --controle",
                 "tijden": ["%02d:05" % u for u in range(7, 23)]},
    "projectsync": {"wat": "projectadressen uit H-A Projecten en de projectmappen", "waar": "VM, app-locatie projectsync.py",
                    "tijden": ["02:15", "08:15", "11:15", "14:15", "17:15", "20:15"]},
    "export": {"wat": "kopie naar Dropbox privé en databasekopie met datum", "waar": "Mac, launchd 22:45 (klok van de Mac)",
               "tijden": ["22:45"]},
}


def _om(hhmm, d):
    u, m = (int(x) for x in hhmm.split(":"))
    return datetime.combine(d, dtijd(u, m), tzinfo=BRUSSEL)


def volgende_uitvoering(taak, nu=None):
    nu = nu or datetime.now(BRUSSEL)
    nu = nu.astimezone(BRUSSEL)
    for extra in range(0, 3):
        d = nu.date() + timedelta(days=extra)
        for hhmm in sorted(PLANNING[taak]["tijden"]):
            t = _om(hhmm, d)
            if t > nu:
                return t
    return None


def binnen_venster(hhmm, nu=None, marge_minuten=20):
    """Is het nu (Belgische tijd) tussen hhmm en hhmm + marge? De klokgrendel van een cronregel."""
    nu = (nu or datetime.now(BRUSSEL)).astimezone(BRUSSEL)
    t = _om(hhmm, nu.date())
    return t <= nu < t + timedelta(minutes=marge_minuten)


def samenvatting():
    """Het beleid als dict, voor de API en voor wie het moet kunnen nalezen."""
    return {
        "versie": VERSIE,
        "startgrens": STARTGRENS,
        "eerste_dag": eerste_dag(),
        "regel": ("een punt telt alleen als zijn meettijd op of na de ingang van zijn bron ligt en het toestel "
                  "het vastgelegde toestel van die bron is; de ontvangsttijd telt niet"),
        "bronnen": {b: {k: v for k, v in d.items() if k != "toestel_sha256"} for b, d in BRONNEN.items()},
        "rollen": ROLLEN,
        "planning": PLANNING,
    }
