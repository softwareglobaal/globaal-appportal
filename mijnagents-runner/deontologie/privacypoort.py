"""De privacypoort van De Deontologiewacht (opdrachtkaart v0.3, stap 2 van de bouw).

Voorwaarde 4 van de ontwerplezing (driehoeksoverleg 27-10-2026, 3-0) en keuze 3 van Mehdi: de bibliotheek (wetten,
reglement, uitspraken) mag naar Codex en Gemini, het tuchtdossier, de mails met de Orde en de advocaat en namen van
klagers niet. Deze module is de enige uitgaande weg naar die twee. Ze moet er staan voor het dossier aangesloten wordt.

- Alles zonder label is privé. Alleen een `Stuk` met label exact `PUBLIEK` gaat door; een gewone tekst, een dict, een
  ander label of een tikfout ("publiek", "PUBLIC") houdt de poort tegen.
- De bronnen uit het regelregister zijn publiek via `uit_bibliotheek()`, en alleen als hun sha256 klopt.
- Een publiek stuk met een verboden term (de namen uit het dossier) gaat ook niet door. De lijst staat buiten git, in
  het bestand waar `DEONTOLOGIE_VERBODEN` naar wijst. Is die variabele gezet maar het bestand niet leesbaar, dan blijft
  de poort dicht.
- Wat de poort tegenhoudt, verschijnt nergens: niet in de doorgang, niet in een foutmelding, niet in een log. De
  doorgang telt alleen hoeveel stukken om welke reden achterbleven.

Gebruik: `stuur(stukken, "codex", verzender)`. De verzender krijgt alleen wat door de poort ging, en wordt niet
aangeroepen als er niets doorging.
"""
import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import register as R

PUBLIEK = "PUBLIEK"
ONTVANGERS = ("codex", "gemini")
VERBODEN_ENV = "DEONTOLOGIE_VERBODEN"

REDEN_GEEN_STUK = "geen stuk met label"
REDEN_PRIVE = "zonder label of privé"
REDEN_VERBODEN = "bevat een verboden term"


class PoortGesloten(Exception):
    """De poort kan niet veilig beslissen en laat niets door."""


@dataclass(frozen=True)
class Stuk:
    tekst: str
    label: str = ""
    soort: str = ""  # wat voor stuk het is (reglement, verzonnen contract), nooit een naam


@dataclass
class Doorgang:
    ontvanger: str
    tekst: str
    doorgelaten: int
    tegengehouden: dict = field(default_factory=dict)  # reden: aantal, nooit inhoud


def uit_bibliotheek(code, register=None, basis=R.HIER):
    """Een bron uit het regelregister als publiek stuk, alleen als de sha256 nog klopt."""
    register = register or R.laad()
    bron = register["bronnen"].get(code)
    if not bron:
        raise PoortGesloten(f"bron {code} staat niet in het regelregister")
    inhoud = (Path(basis) / bron["bestand"]).read_bytes()
    if hashlib.sha256(inhoud).hexdigest() != bron["sha256"]:
        raise PoortGesloten(f"bron {code}: sha256 klopt niet, niet als publiek doorgeven")
    return Stuk(inhoud.decode("utf-8"), PUBLIEK, f"bibliotheek {code}")


def _normaal(tekst):
    return re.sub(r"\s+", " ", tekst).strip().casefold()


def verboden_termen():
    """De verboden termen uit het bestand buiten git. Geen variabele: geen extra termen. Variabele zonder leesbaar
    bestand: de poort blijft dicht."""
    pad = os.environ.get(VERBODEN_ENV, "").strip()
    if not pad:
        return []
    try:
        regels = Path(pad).read_text(encoding="utf-8").splitlines()
    except OSError:
        raise PoortGesloten(f"{VERBODEN_ENV} is gezet maar het bestand is niet leesbaar") from None
    return [t for t in (_normaal(r) for r in regels) if t and not t.startswith("#")]


def poort(stukken, ontvanger, verboden=None):
    """Laat alleen publieke stukken zonder verboden term door, voor Codex of Gemini."""
    if ontvanger not in ONTVANGERS:
        raise PoortGesloten("onbekende ontvanger, alleen codex of gemini")
    termen = verboden_termen() if verboden is None else [t for t in (_normaal(v) for v in verboden) if t]
    door, tegen = [], {}
    for stuk in stukken:
        if not isinstance(stuk, Stuk):
            reden = REDEN_GEEN_STUK
        elif stuk.label != PUBLIEK or not isinstance(stuk.tekst, str):
            reden = REDEN_PRIVE
        elif any(t in _normaal(stuk.tekst) for t in termen):
            reden = REDEN_VERBODEN
        else:
            door.append(stuk.tekst)
            continue
        tegen[reden] = tegen.get(reden, 0) + 1
    return Doorgang(ontvanger, "\n\n".join(door), len(door), tegen)


def stuur(stukken, ontvanger, verzender, verboden=None):
    """De enige uitgaande weg: `verzender(ontvanger, tekst)` krijgt alleen wat door de poort ging."""
    doorgang = poort(stukken, ontvanger, verboden)
    if doorgang.doorgelaten:
        verzender(ontvanger, doorgang.tekst)
    return doorgang
