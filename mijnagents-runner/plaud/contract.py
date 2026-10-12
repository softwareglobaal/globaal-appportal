"""Het opnamecontract van Plaud: één versieerbare vorm voor wat de ophaler op de Mac schrijft en
wat De Plaudwacht op de VM leest (verbeteropdracht v1.0, 12-10-2026, sectie 2).

Een opname is altijd:

    plaud_id          "of_<hex>", de enige sleutel
    start_utc         opnametijd in UTC, ISO met Z
    start_brussel     dezelfde tijd in Europe/Brussels, ISO met offset (weergave)
    duur_minuten      getal
    naam_in_plaud     zoals Plaud hem toont
    transcript        {staat: aanwezig | wacht | onbekend, uitingen, laatste_controle,
                       volgende_controle, pogingen, bron}
    audio             {staat: aanwezig | online_only | ontbreekt, bestand}
    archief           {plaats: "mac-dropbox", map: "<mapnaam>"}
    account           het Plaud-account; "onbekend" als het niet bewezen is
    toestel           serienummer van het toestel; "onbekend" als Plaud het niet meegaf
    opgenomen_door    persoon; "onbekend" tot een label of een bewijs het zegt
    bronbewijs        [{soort, waarde}], waar elk veld vandaan komt
    herstel           null, of de reden waarom de opname niet verwerkt mag worden

Account, toestel en opgenomen_door zijn afzonderlijke velden: één centraal Plaud-account met vier
toestellen bewijst niet wie opnam, en ook niet dat Mehdi erbij was.

Python 3.9-compatibel: de ophaler op de Mac draait met /usr/bin/python3.
"""
import re
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

CONTRACT = "plaud-opname"
VERSIE = 1
BRUSSEL = ZoneInfo("Europe/Brussels")
UTC = timezone.utc
ID = re.compile(r"^(?:of_)?([0-9a-f]{32})$")

# backoff voor een transcript dat (nog) niet bestaat: na 1 u, 6 u, 1 dag, 3 dagen, daarna wekelijks
WACHT_STAPPEN_UUR = (1, 6, 24, 72, 168)


class Herstel(ValueError):
    """De opname mist iets wezenlijks (geen id, geen of ongeldige opnametijd)."""


def canon_id(waarde):
    """Altijd de vorm 'of_<32 hex>'. Een ander formaat is geen Plaud-id."""
    m = ID.match((waarde or "").strip().lower())
    if not m:
        raise Herstel(f"geen geldig Plaud-id: {waarde!r}")
    return "of_" + m.group(1)


def _parse(waarde, naive_zone):
    t = datetime.fromisoformat(str(waarde).strip().replace("Z", "+00:00").replace(" ", "T", 1))
    return t if t.tzinfo else t.replace(tzinfo=naive_zone)


def normaliseer_start(meta):
    """(start_utc, start_brussel) als ISO-strings, uit de velden die de bronnen gebruiken.

    Volgorde: start_utc, start_at (Plaud-API: UTC zonder zone), start_brussel/start_belgisch
    (Brussel; zonder zone betekent Brussel), start (de kop van de oude claude.ai-routine: Brussel).
    Ontbreekt alles of is het ongeldig, dan Herstel. Nooit de wijzigingsdatum van een bestand:
    die gaf een opname van 6 oktober de datum 12 oktober."""
    kandidaten = (("start_utc", UTC), ("start_at", UTC), ("start_brussel", BRUSSEL),
                  ("start_belgisch", BRUSSEL), ("start", BRUSSEL))
    for veld, zone in kandidaten:
        w = meta.get(veld)
        if not w:
            continue
        try:
            t = _parse(w, zone)
        except (TypeError, ValueError):
            raise Herstel(f"ongeldige opnametijd in {veld}: {w!r}")
        if t.year < 2020 or t > datetime.now(UTC) + timedelta(days=2):
            raise Herstel(f"onwaarschijnlijke opnametijd in {veld}: {w!r}")
        u = t.astimezone(UTC)
        return u.strftime("%Y-%m-%dT%H:%M:%SZ"), u.astimezone(BRUSSEL).isoformat(timespec="seconds")
    raise Herstel("geen opnametijd (start_utc, start_at, start_brussel of start ontbreekt)")


def volgende_controle(pogingen, nu=None):
    nu = nu or datetime.now(UTC)
    uur = WACHT_STAPPEN_UUR[min(max(int(pogingen) - 1, 0), len(WACHT_STAPPEN_UUR) - 1)]   # na poging 1: 1 uur
    return (nu + timedelta(hours=uur)).strftime("%Y-%m-%dT%H:%M:%SZ")


def opname(meta, archiefmap="", transcript=None, audio=None, bron="onbekend"):
    """Het contract voor één opname. meta: wat de bron gaf (API, MCP, oude inbox, gesprek.json).
    Gooit Herstel als id of opnametijd ontbreekt; de aanroeper zet de opname dan op herstel."""
    pid = canon_id(meta.get("plaud_id") or meta.get("id") or "")
    start_utc, start_brussel = normaliseer_start(meta)
    duur = meta.get("duur_minuten")
    if duur is None and meta.get("duration") is not None:
        duur = round(float(meta["duration"]) / 60000, 1)
    toestel = meta.get("toestel") or meta.get("serial_number") or "onbekend"
    return {
        "contract": CONTRACT, "versie": VERSIE,
        "plaud_id": pid, "start_utc": start_utc, "start_brussel": start_brussel,
        "duur_minuten": float(duur) if duur not in (None, "") else None,
        "naam_in_plaud": meta.get("naam_in_plaud") or meta.get("name") or "",
        "transcript": transcript or {"staat": "onbekend"},
        "audio": audio or {"staat": "onbekend"},
        "archief": {"plaats": "mac-dropbox", "map": archiefmap},
        "account": meta.get("account") if meta.get("account") not in (None, "", "mehdi") else "onbekend",
        "toestel": toestel,
        "opgenomen_door": meta.get("opgenomen_door") or "onbekend",
        "bronbewijs": [{"soort": bron, "velden": sorted(k for k in meta if not k.endswith("_url") and k != "transcript_link")}],
        "herstel": None,
    }


def brussel(start_utc):
    return _parse(start_utc, UTC).astimezone(BRUSSEL)
