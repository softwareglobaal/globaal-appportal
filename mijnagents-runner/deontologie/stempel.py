"""De grendel van De Deontologiewacht: de stempel per stuk (opdrachtkaart v0.3, stap 5 van de bouw).

Voorwaarde 3 van de ontwerplezing (driehoeksoverleg 27-10-2026, 3-0): de grendel staat buiten de agent. De Wacht geeft
een stempel; de verzend- en exportfunctie van de Contractmaker en van de werfverslag-agents controleert die stempel zelf
met `controleer()`. Geen stempel, een gewijzigd bestand, een vervallen stempel of een stilgevallen Wacht: niets vertrekt.

- De stempel draagt de sha256 van het exacte bestand, de kleur en de rode punten van het verslag, een vervaldatum en een
  HMAC-handtekening met een sleutel buiten git (`DEONTOLOGIE_STEMPELSLEUTEL`). Zonder sleutel is de grendel dicht.
- Groen vertrekt. Oranje vertrekt pas na een zichtbare bevestiging van Mehdi. Rood vertrekt alleen als Mehdi elk rood
  punt apart bevestigt, met een reden die in de stempel bewaard blijft (beslissing van Mehdi, 27-10-2026). Het rode
  punt blijft in het verslag staan; er is geen andere weg langs de grendel.
- De kleur van de stempel wordt uit de punten van het verslag nagerekend: een verslag dat groen zegt met een rood punt
  erin, krijgt geen stempel (laatste toets 28-10-2026).
- Een bevestiging van Mehdi draagt een eigen handtekening met een tweede sleutel (`DEONTOLOGIE_BEVESTIGSLEUTEL`). Die
  staat alleen in het bevestigscherm achter de login van Mehdi en in de apps die controleren, nooit bij de Wacht zelf:
  de Wacht kan dus een stempel maken, maar geen oranje of rood stuk laten vertrekken (laatste toets 28-10-2026).
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

VERSIE = 2  # 2: kleur nagerekend, bevestiging met eigen sleutel (28-10-2026)
GELDIG_DAGEN = 7
SLEUTEL_ENV = "DEONTOLOGIE_STEMPELSLEUTEL"
BEVESTIG_ENV = "DEONTOLOGIE_BEVESTIGSLEUTEL"
BEVESTIGERS = ("mehdi",)  # alleen Mehdi laat oranje of rood vertrekken
KLEUREN = ("groen", "oranje", "rood")
ERNST = {k: i for i, k in enumerate(KLEUREN)}
ORANJE_BEVESTIGING = "oranje"  # sleutel in `bevestigd` voor het hele stuk; rode punten staan onder hun code


class GrendelDicht(Exception):
    """De grendel kan niet veilig beslissen en laat niets vertrekken."""


def _sleutel(sleutel=None, env=SLEUTEL_ENV):
    sleutel = sleutel if sleutel is not None else os.environ.get(env, "")
    if isinstance(sleutel, str):
        sleutel = sleutel.encode("utf-8")
    if len(sleutel) < 32:
        raise GrendelDicht(f"{env} ontbreekt of is te kort (minstens 32 tekens)")
    return sleutel


def _bevestigsleutel(bevestigsleutel, sleutel):
    b = _sleutel(bevestigsleutel, BEVESTIG_ENV)
    if hmac.compare_digest(b, sleutel):
        raise GrendelDicht(f"{BEVESTIG_ENV} moet een andere sleutel zijn dan {SLEUTEL_ENV}")
    return b


def _teken_bevestiging(stempel, wat, b, bevestigsleutel):
    gegevens = {"sha256": stempel["sha256"], "gemaakt": stempel["gemaakt"], "wat": wat,
                "door": b["door"], "reden": b["reden"], "ts": b["ts"]}
    tekst = json.dumps(gegevens, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hmac.new(bevestigsleutel, tekst, hashlib.sha256).hexdigest()


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
    if verslag.kleur not in KLEUREN or any(p.kleur not in KLEUREN for p in verslag.punten):
        raise GrendelDicht(f"onbekende kleur {verslag.kleur!r}")
    nagerekend = max((p.kleur for p in verslag.punten), key=ERNST.get, default="oranje")
    if verslag.kleur != nagerekend:
        raise GrendelDicht(f"het verslag zegt {verslag.kleur}, maar de punten geven {nagerekend}")
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


def bevestig(stempel, wat, door, reden="", sleutel=None, nu=None, bevestigsleutel=None):
    """Mehdi laat een oranje stuk (`wat` = "oranje") of een rood punt (`wat` = de regelcode) toch vertrekken.

    Geeft een nieuwe, opnieuw ondertekende stempel; de oude blijft ongewijzigd. Een rood punt vraagt een reden. Alleen
    het bevestigscherm achter de login van Mehdi heeft de bevestigsleutel."""
    sleutel = _sleutel(sleutel)
    bevestigsleutel = _bevestigsleutel(bevestigsleutel, sleutel)
    if not hmac.compare_digest(str(stempel.get("handtekening", "")).encode("utf-8"),
                               _handtekening(stempel, sleutel).encode("utf-8")):
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
    b = {"door": door, "reden": reden.strip(), "ts": _nu(nu).isoformat()}
    b["teken"] = _teken_bevestiging(stempel, wat, b, bevestigsleutel)
    nieuw["bevestigd"][wat] = b
    nieuw["handtekening"] = _handtekening(nieuw, sleutel)
    return nieuw


def controleer(inhoud, stempel, sleutel=None, nu=None, bevestigsleutel=None):
    """(True, "") als dit exacte stuk mag vertrekken, anders (False, reden). Twijfel is altijd False. Een stempel met een
    bevestiging vraagt ook de bevestigsleutel."""
    try:
        sleutel = _sleutel(sleutel)
    except GrendelDicht as e:
        return False, str(e)
    if not isinstance(stempel, dict) or not stempel:
        return False, "geen stempel van De Deontologiewacht"
    try:
        if not hmac.compare_digest(str(stempel.get("handtekening", "")).encode("utf-8"),
                                   _handtekening(stempel, sleutel).encode("utf-8")):
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
        if stempel.get("rood") and kleur != "rood":
            return False, "rode punten in een stempel die niet rood is"
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
        if bevestigd:
            try:
                b_sleutel = _bevestigsleutel(bevestigsleutel, sleutel)
            except GrendelDicht as e:
                return False, str(e)
            for wat, b in bevestigd.items():
                if not hmac.compare_digest(str(b.get("teken", "")).encode("utf-8"),
                                           _teken_bevestiging(stempel, wat, b, b_sleutel).encode("utf-8")):
                    return False, "een bevestiging is niet door Mehdi ondertekend"
    except (AttributeError, KeyError, TypeError, ValueError):
        return False, "de stempel is onleesbaar"
    return True, ""
