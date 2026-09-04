"""Het prijsmodel op één plek.

De kostenstructuur van dit product is ongebruikelijk en de prijs hoort dat te
volgen. Er is precies één betaalde stap -- de OCR van een gescand document, en
die is eenmalig. Alles daarna is gratis: het embedden draait lokaal en zoeken
kost per vraag niets.

Daarom wordt er afgerekend in BLADZIJDEN en niet in vragen, tokens of opslag. Een
klant kan vooraf uitrekenen wat iets kost door zijn document open te slaan en
naar het laatste paginanummer te kijken. Dat is het hele model.

De inkoopprijs is gemeten, niet geschat: $0,0156 per bladzijde op claude-sonnet-5,
vastgesteld op een gescande proeffolder waarvan de tekstlaagversie de grondwaarheid
was. Bij een wisselkoers rond 0,92 is dat ongeveer 1,4 eurocent. De verkoopprijs
staat op 5 cent: ruim drie keer de inkoop, en nog steeds minder dan twintig euro
voor een boek van vierhonderd bladzijden.
"""
from __future__ import annotations

from dataclasses import dataclass

# Wat een gescande bladzijde ons kost (gemeten) en wat hij de klant kost.
INKOOP_PER_BLAD_USD = 0.0156
PRIJS_PER_BLAD_EUR = 0.05
# Een PDF die zijn eigen tekst draagt kost ons niets, dus die is gratis. Dat is
# geen weggevertje maar sturing: het maakt de goedkope route ook de makkelijke.
PRIJS_TEKSTLAAG_EUR = 0.0
# Gemeten op het proefboek: 383 bladzijden in 140 minuten, sequentieel.
SECONDEN_PER_GESCANDE_BLAD = 22
BLADEN_PER_SECONDE_TEKSTLAAG = 8


@dataclass(frozen=True)
class Pakket:
    naam: str
    prijs_maand: int
    bladzijden: int
    gebruikers: str
    kern: str
    kenmerken: tuple[str, ...]
    uitgelicht: bool = False


PAKKETTEN = (
    Pakket(
        naam="Start",
        prijs_maand=49,
        bladzijden=500,
        gebruikers="3 gebruikers",
        kern="Voor wie een handvol naslagwerken doorzoekbaar wil maken.",
        kenmerken=(
            "500 gescande bladzijden per maand inbegrepen",
            "PDF's met tekstlaag onbeperkt en gratis",
            "onbeperkt zoeken, geen kosten per vraag",
            "elke kennisbank in een eigen bestand",
        ),
    ),
    Pakket(
        naam="Kantoor",
        prijs_maand=149,
        bladzijden=2500,
        gebruikers="15 gebruikers",
        kern="Voor een kantoor dat zijn hele dossierkast ontsluit.",
        kenmerken=(
            "2.500 gescande bladzijden per maand inbegrepen",
            "onbeperkt PDF's met tekstlaag",
            "onbeperkt zoeken voor het hele kantoor",
            "API om vanuit je eigen software te zoeken",
            "verwerkingsverslag per document, om te bewaren",
        ),
        uitgelicht=True,
    ),
    Pakket(
        naam="Op maat",
        prijs_maand=0,
        bladzijden=0,
        gebruikers="onbeperkt",
        kern="Op je eigen server, of met bronnen die het pand niet uit mogen.",
        kenmerken=(
            "installatie op eigen infrastructuur",
            "geen enkele bron verlaat je netwerk",
            "eigen afspraken over bewaartermijn en verwijdering",
            "ondersteuning met reactietijd op maat",
        ),
    ),
)

MEERVERBRUIK = f"€ {PRIJS_PER_BLAD_EUR:.2f}".replace(".", ",") + " per extra gescande bladzijde"

# Waarmee een nieuw kantoor begint, zodat ze kunnen proberen voordat ze betalen.
PROEFTEGOED = 500


@dataclass(frozen=True)
class Bundel:
    """Tegoed dat je bijkoopt.

    Bladzijden vervallen niet. Het inlezen van een archief is een piek en het
    zoeken erna is doorlopend; een tegoed dat aan het eind van de maand verdampt
    straft precies het gebruikspatroon dat we willen.
    """
    bladzijden: int
    prijs: int

    @property
    def per_blad(self) -> float:
        return self.prijs / self.bladzijden


BUNDELS = (
    Bundel(250, 15),
    Bundel(1000, 45),
    Bundel(5000, 195),
)


def prijs_van(bladzijden: int, route: str) -> float:
    """Wat deze verwerking de klant kost."""
    if route != "ocr":
        return PRIJS_TEKSTLAAG_EUR
    return round(bladzijden * PRIJS_PER_BLAD_EUR, 2)


def duur_van(bladzijden: int, route: str) -> str:
    """Een eerlijke schatting van de wachttijd, in mensentaal."""
    if route != "ocr":
        seconden = max(2, bladzijden / BLADEN_PER_SECONDE_TEKSTLAAG)
        return "een paar seconden" if seconden < 30 else f"ongeveer {int(seconden / 60) + 1} minuten"
    minuten = bladzijden * SECONDEN_PER_GESCANDE_BLAD / 60
    if minuten < 60:
        return f"ongeveer {int(minuten)} minuten"
    uren = minuten / 60
    heel = int(uren)
    rest = int((uren - heel) * 60)
    if rest < 10:
        return f"ongeveer {heel} uur"
    return f"ongeveer {heel} uur en {rest} minuten"
