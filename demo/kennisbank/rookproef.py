"""Rookproef: vindt de kennisbank zijn eigen inhoud terug?

Geen model nodig, en dat is met opzet. De vraag "werkt het ophalen" is een
positiecontrole en geen mening: neem een fragment, stel een vraag met de woorden
die juist in dat fragment zeldzaam zijn, en kijk of het fragment terugkomt.

Dat is de ondergrens. Haalt een kennisbank die niet, dan is er iets stuk aan de
opslag of het ophalen en heeft verder meten geen zin. Een kennisbank die hem wel
haalt is nog niet goed -- daarvoor moet je met andere woorden zoeken dan er staan,
en daar heb je wel een model voor nodig -- maar hij is in elk geval niet kapot.

De onderscheidende woorden komen uit de omgekeerde documentfrequentie: een woord
dat in dit fragment staat en bijna nergens anders wijst er als enige naar terug.
Dat is precies wat een mens ook zou intypen als hij deze passage zocht.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .opslag import Kennisbank

STOPWOORDEN = {
    "de", "het", "een", "van", "in", "op", "te", "en", "dat", "die", "voor",
    "met", "als", "aan", "is", "zijn", "wordt", "worden", "niet", "ook", "bij",
    "door", "uit", "naar", "over", "maar", "dan", "heeft", "kan", "deze", "dit",
    "er", "om", "of", "wel", "geen", "haar", "hun", "zij", "hij", "men", "was",
    "waarin", "waarbij", "daarbij", "aldus", "zie", "art", "nr", "blz",
}
WOORD = re.compile(r"[a-zA-ZÀ-ÿ]{4,}")


@dataclass
class Uitslag:
    gevraagd: int
    geslaagd: int
    proeven: list[dict]

    @property
    def aandeel(self) -> float:
        return self.geslaagd / self.gevraagd if self.gevraagd else 0.0


def _woorden(tekst: str) -> list[str]:
    return [w.lower() for w in WOORD.findall(tekst)
            if w.lower() not in STOPWOORDEN]


def _idf(bank: Kennisbank) -> tuple[dict[str, float], int]:
    """Hoe zeldzaam is elk woord in deze kennisbank."""
    documenten = 0
    voorkomen: Counter[str] = Counter()
    for r in bank.db.execute("SELECT tekst FROM fragment"):
        documenten += 1
        voorkomen.update(set(_woorden(r["tekst"])))
    idf = {w: math.log(documenten / n) for w, n in voorkomen.items() if n}
    return idf, documenten


def maak_vraag(tekst: str, idf: dict[str, float], hoeveel: int = 7) -> str:
    """De zeldzaamste woorden uit dit fragment, in de volgorde van de tekst."""
    telling = Counter(_woorden(tekst))
    gescoord = sorted(telling, key=lambda w: -(idf.get(w, 0.0) * min(telling[w], 3)))
    gekozen = set(gescoord[:hoeveel])
    volgorde = [w for w in dict.fromkeys(_woorden(tekst)) if w in gekozen]
    return " ".join(volgorde)


def draai(bank: Kennisbank, hoeveel: int = 12, k: int = 5) -> Uitslag:
    idf, _ = _idf(bank)
    monsters = bank.steekproef(hoeveel)
    proeven: list[dict] = []
    geslaagd = 0

    for m in monsters:
        vraag = maak_vraag(m["tekst"], idf)
        if not vraag:
            continue
        treffers = bank.zoek(vraag, k=k)
        posities = [t.fragment_id for t in treffers]
        plek = posities.index(m["id"]) + 1 if m["id"] in posities else None
        geslaagd += plek is not None
        proeven.append({
            "fragment_id": m["id"],
            # Gedrukt en fysiek apart houden. Voorwerk heeft geen gedrukt nummer,
            # en dan een scannummer onder de kop "bladzijde" zetten is een getal
            # tonen dat nergens op die bladzijde staat.
            "gedrukt": m["gedrukt"],
            "fysiek": m["fysiek"],
            "sectie": m["sectie"],
            "vraag": vraag,
            "plek": plek,
            "fragment": m["tekst"][:240],
        })

    return Uitslag(gevraagd=len(proeven), geslaagd=geslaagd, proeven=proeven)
