"""De grendel van De Deontologiewacht: de stempel per stuk (opdrachtkaart v0.3, stap 5 van de bouw).

Voorwaarde 3 van de ontwerplezing (driehoeksoverleg 27-10-2026, 3-0): de grendel staat buiten de agent. De Wacht geeft
een stempel; de verzend- en exportfunctie van de Contractmaker en van de werfverslag-agents controleert die stempel zelf
met `controleer()`. Geen stempel, een gewijzigd bestand, een vervallen stempel of een stilgevallen Wacht: niets vertrekt.

- De stempel draagt de sha256 van het exacte bestand, de kleur en de rode punten van het verslag, een vervaldatum en een
  HMAC-handtekening met een sleutel buiten git (`DEONTOLOGIE_STEMPELSLEUTEL`). Zonder sleutel is de grendel dicht.
- Groen vertrekt. Oranje vertrekt pas na een zichtbare bevestiging van Mehdi. Rood vertrekt alleen als Mehdi elk rood
  punt apart bevestigt, met een reden die in de stempel bewaard blijft (beslissing van Mehdi, 27-10-2026). Het rode
  punt blijft in het verslag staan; er is geen andere weg langs de grendel.
- Een stempel vervalt na GELDIG_DAGEN. Een Wacht die stilvalt, maakt geen nieuwe stempels, dus na de vervaldatum
  vertrekt niets meer.

Dit bestand gebruikt alleen de standaardbibliotheek, zodat de Contractmaker en de werfverslag-apps het letterlijk
kunnen overnemen (met dezelfde VERSIE) zonder de rest van de agent.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone

VERSIE = 1
GELDIG_DAGEN = 7
SLEUTEL_ENV = "DEONTOLOGIE_STEMPELSLEUTEL"
BEVESTIGERS = ("mehdi",)  # alleen Mehdi laat oranje of rood vertrekken
KLEUREN = ("groen", "oranje", "rood")
ORANJE_BEVESTIGING = "oranje"  # sleutel in `bevestigd` voor het hele stuk; rode punten staan onder hun code


class GrendelDicht(Exception):
    """De grendel kan niet veilig beslissen en laat niets vertrekken."""


def _sleutel(sleutel=None):
    sleutel = sleutel if sleutel is not None else os.environ.get(SLEUTEL_ENV, "")
    if isinstance(sleutel, str):
        sleutel = sleutel.encode("utf-8")
    if len(sleutel) < 32:
        raise GrendelDicht(f"{SLEUTEL_ENV} ontbreekt of is te kort (minstens 32 tekens)")
    return sleutel


def _nu(nu=None):
    return (nu or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _handtekening(gegevens, sleutel):
    zonder = {k: v for k, v in gegevens.items() if k != "handtekening"}
    tekst = json.dumps(zonder, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hmac.new(sleutel, tekst, hashlib.sha256).hexdigest()


def vingerafdruk(inhoud):
    return hashlib.sha256(inhoud).hexdigest()


def maak(inhoud, verslag, sleutel=None, nu=None, geldig_dagen=GELDIG_DAGEN):
    """Een nieuwe stempel voor de exacte bytes van een stuk en het verslag van de Wacht daarover."""
    if verslag.kleur not in KLEUREN:
        raise GrendelDicht(f"onbekende kleur {verslag.kleur!r}")
    sleutel = _sleutel(sleutel)
    nu = _nu(nu)
    gegevens = {
        "versie": VERSIE,
        "sha256": vingerafdruk(inhoud),
        "documentsoort": verslag.documentsoort,
        "kleur": verslag.kleur,
        "rood": sorted(p.code for p in verslag.punten if p.kleur == "rood"),
        "bron": verslag.bron,
        "gemaakt": nu.isoformat(),
        "vervalt": (nu + timedelta(days=geldig_dagen)).isoformat(),
        "bevestigd": {},
    }
    gegevens["handtekening"] = _handtekening(gegevens, sleutel)
    return gegevens


def bevestig(stempel, wat, door, reden="", sleutel=None, nu=None):
    """Mehdi laat een oranje stuk (`wat` = "oranje") of een rood punt (`wat` = de regelcode) toch vertrekken.

    Geeft een nieuwe, opnieuw ondertekende stempel; de oude blijft ongewijzigd. Een rood punt vraagt een reden."""
    sleutel = _sleutel(sleutel)
    if not hmac.compare_digest(str(stempel.get("handtekening", "")), _handtekening(stempel, sleutel)):
        raise GrendelDicht("de stempel is niet echt of gewijzigd")
    if door not in BEVESTIGERS:
        raise GrendelDicht("alleen Mehdi kan een oranje stuk of een rood punt laten vertrekken")
    if wat == ORANJE_BEVESTIGING:
        if stempel["kleur"] != "oranje":
            raise GrendelDicht("dit stuk is niet oranje")
    elif wat not in stempel["rood"]:
        raise GrendelDicht(f"{wat} is geen rood punt van dit stuk")
    elif not reden.strip():
        raise GrendelDicht("een rood punt laten vertrekken vraagt een reden")
    nieuw = json.loads(json.dumps(stempel))
    nieuw["bevestigd"][wat] = {"door": door, "reden": reden.strip(), "ts": _nu(nu).isoformat()}
    nieuw["handtekening"] = _handtekening(nieuw, sleutel)
    return nieuw


def controleer(inhoud, stempel, sleutel=None, nu=None):
    """(True, "") als dit exacte stuk mag vertrekken, anders (False, reden). Twijfel is altijd False."""
    try:
        sleutel = _sleutel(sleutel)
    except GrendelDicht as e:
        return False, str(e)
    if not isinstance(stempel, dict) or not stempel:
        return False, "geen stempel van De Deontologiewacht"
    try:
        if not hmac.compare_digest(str(stempel.get("handtekening", "")), _handtekening(stempel, sleutel)):
            return False, "de stempel is niet echt of gewijzigd"
        if stempel.get("versie") != VERSIE:
            return False, "onbekende versie van de stempel"
        if not hmac.compare_digest(str(stempel.get("sha256", "")), vingerafdruk(inhoud)):
            return False, "het stuk is gewijzigd sinds de toets"
        nu = _nu(nu)
        if nu < datetime.fromisoformat(stempel["gemaakt"]) - timedelta(minutes=5):
            return False, "de stempel is in de toekomst gemaakt"
        if nu >= datetime.fromisoformat(stempel["vervalt"]):
            return False, "de stempel is vervallen, de Wacht moet opnieuw toetsen"
        kleur, bevestigd = stempel.get("kleur"), stempel.get("bevestigd") or {}
        if kleur not in KLEUREN:
            return False, "onbekende kleur"
        if kleur == "oranje" and ORANJE_BEVESTIGING not in bevestigd:
            return False, "oranje: wacht op de bevestiging van Mehdi"
        if kleur == "rood":
            if not stempel.get("rood"):
                return False, "rood zonder rode punten"
            open_ = [c for c in stempel["rood"] if not (bevestigd.get(c) or {}).get("reden")]
            if open_:
                return False, f"rood: {', '.join(open_)} wacht op Mehdi"
        if any((b or {}).get("door") not in BEVESTIGERS for b in bevestigd.values()):
            return False, "een bevestiging komt niet van Mehdi"
    except (KeyError, TypeError, ValueError):
        return False, "de stempel is onleesbaar"
    return True, ""
