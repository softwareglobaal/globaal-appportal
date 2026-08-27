"""Laden van OCR-uitvoer tot een lijst bladzijden.

De cache van de ingestie-agent bewaart per deel de bladen zoals het model ze
teruggaf. De nummering daarin is NIET betrouwbaar: het model telt binnen het deel
en slaat een lege bladzijde weleens over. `herken()` in de agent lost dat op door
op volgorde te nummeren met de verschuiving van het deel erbij, en dat doen wij
hier ook. Wie op het veld `nummer` vertrouwt krijgt 383 bladzijden die allemaal
tussen 1 en 20 genummerd zijn.

Bloksoorten uit de OCR, en wat ze werkelijk betekenen:

  titel   een kop in de lopende tekst. Dit is de structuur waar we op chunken.
  kop     de KOPTEKST bovenaan de bladzijde: bij dit boek de auteursnaam of de
          hoofdstuktitel, op elke bladzijde herhaald. Geen structuur maar wel
          goud: het zegt bij welk hoofdstuk een bladzijde hoort.
  voet    de voettekst, meestal het gedrukte paginanummer.
  tekst   lopende tekst.
  tabel   een tabel.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEELNAAM = re.compile(r"deel-(\d{4})-(\d{4})")


@dataclass
class Blok:
    soort: str
    tekst: str


@dataclass
class Blad:
    """Een fysieke bladzijde, genummerd vanaf 1 in de volgorde van het document."""
    fysiek: int
    markdown: str
    blokken: list[Blok] = field(default_factory=list)
    figuren: list[str] = field(default_factory=list)
    gedrukt: int | None = None          # het nummer dat op de bladzijde staat

    def van_soort(self, soort: str) -> list[str]:
        return [b.tekst.strip() for b in self.blokken
                if b.soort == soort and b.tekst.strip()]

    @property
    def koptekst(self) -> str:
        """De herhaalde kop bovenaan; bij een bundel de hoofdstuk- of auteursnaam."""
        k = self.van_soort("kop")
        return k[0] if k else ""


def _verschuiving(pad: Path) -> int:
    """Het bladzijdenummer waarop dit deel begint, uit de bestandsnaam."""
    m = DEELNAAM.search(pad.name)
    if not m:
        raise ValueError(f"kan de bladzijderange niet uit {pad.name} lezen")
    return int(m.group(1)) - 1


def laad_uit_cache(map_: Path) -> list[Blad]:
    """Alle delen uit een OCR-cachemap, op volgorde en correct genummerd."""
    delen = sorted(map_.glob("*.json"), key=lambda p: _verschuiving(p))
    if not delen:
        raise FileNotFoundError(f"geen OCR-delen in {map_}")

    bladen: list[Blad] = []
    for pad in delen:
        d = json.loads(pad.read_text(encoding="utf-8"))
        begin = _verschuiving(pad)
        for i, blad in enumerate(d["bladen"]):
            bladen.append(Blad(
                fysiek=begin + i + 1,
                markdown=blad.get("markdown") or "",
                blokken=[Blok(b.get("soort", "tekst"), b.get("tekst", ""))
                         for b in (blad.get("blokken") or [])],
                figuren=list(blad.get("figuren") or []),
            ))

    # Controle op gaten en dubbelingen: bij een cache die half gevuld is of een
    # deel dat zichzelf gehalveerd heeft, klopt de doorlopende nummering niet
    # meer en dan is elke paginaverwijzing daarna verkeerd.
    verwacht = list(range(1, len(bladen) + 1))
    gevonden = [b.fysiek for b in bladen]
    if gevonden != verwacht:
        ontbreekt = sorted(set(verwacht) - set(gevonden))[:5]
        raise ValueError(
            f"de bladzijden lopen niet door: {len(bladen)} bladen, "
            f"eerste gaten/afwijkingen bij {ontbreekt or gevonden[:5]}")
    return bladen


def hele_tekst(bladen: list[Blad]) -> str:
    """De markdown met paginamarkeringen, zoals de rest van de keten hem leest."""
    return "\n".join(f"<!-- page: {b.fysiek} -->\n{b.markdown}" for b in bladen)
