"""De keten van bron tot doorzoekbare kennisbank.

Alles hier is deterministisch. Er zit geen model in dat mag beslissen of het werk
doorgaat: waar de bestaande agent een wachter liet oordelen, staat hier een
meting. Het enige oordeel dat telt komt van de mens die het document aanleverde,
en dat gebeurt op een scherm tussen stap twee en stap drie.

    bron        bladzijden met getypeerde blokken
    structuur   inhoudsopgave lezen, ijken, verifieren  -> trefkans
    (mens)      klopt deze indeling?
    knippen     fragmenten binnen de bladzijdegrens     -> dekking
    embedden    lokaal model
    opslaan     een SQLite-bestand per document
    rookproef   vindt hij zijn eigen inhoud terug?      -> aandeel
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

from . import knippen, rookproef, structuur, vectoren
from .ocrbron import Blad
from .opslag import Kennisbank
from .structuur import Sectie, Structuur


def nu() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def gedrukte_nummers(bladen: list[Blad], ijking: structuur.IJking) -> dict[int, int]:
    """Welk nummer staat er op elke bladzijde gedrukt.

    Alleen na het voorwerk: daarvoor is de telling romeins en zou de arabische
    verschuiving een nummer opleveren dat nergens op de bladzijde staat.
    """
    if ijking.verschuiving is None:
        return {}
    return {b.fysiek: b.fysiek - ijking.verschuiving
            for b in bladen if b.fysiek > ijking.voorwerk_tot}


@dataclass
class Rapport:
    doc_id: str
    titel: str
    bladzijden: int
    trefkans: float
    ingangen: int
    secties: int
    verschuiving: int | None
    fragmenten: int = 0
    dekking: dict = field(default_factory=dict)
    rookproef: dict = field(default_factory=dict)
    per_soort: dict = field(default_factory=dict)


def bouw(bladen: list[Blad], secties: list[Sectie], *, doc_id: str, titel: str,
         bestandsnaam: str, st: Structuur, pad: Path,
         voortgang=None) -> tuple[Kennisbank, Rapport]:
    """Knipt, embedt, slaat op en toetst. Geeft de gevulde kennisbank terug."""
    def melden(stap: str) -> None:
        if voortgang:
            voortgang(stap)

    overslaan = set(st.inhoudsopgave_paginas)
    gedrukt = gedrukte_nummers(bladen, st.ijking)

    melden("knippen")
    fragmenten = knippen.knip(bladen, secties, overslaan=overslaan,
                              gedrukt_van=gedrukt)
    dek = knippen.dekking(bladen, fragmenten, overslaan=overslaan)

    melden(f"embedden van {len(fragmenten)} fragmenten")
    vecs = vectoren.embed([f.met_context for f in fragmenten])

    melden("opslaan")
    bank = Kennisbank(pad)
    bank.leg_vast(doc_id=doc_id, titel=titel, bestandsnaam=bestandsnaam,
                  bladzijden=len(bladen), aangemaakt=nu(),
                  trefkans=st.trefkans, verschuiving=st.ijking.verschuiving,
                  dekking=dek["aandeel"],
                  meta={"inhoudsopgave_paginas": st.inhoudsopgave_paginas,
                        "ingangen": len(st.ingangen),
                        "voorwerk_tot": st.ijking.voorwerk_tot})
    bank.schrijf_secties(secties)
    bank.schrijf_fragmenten(fragmenten, vecs)

    melden("rookproef")
    uitslag = rookproef.draai(bank)

    per_soort: dict[str, int] = {}
    for f in fragmenten:
        per_soort[f.soort] = per_soort.get(f.soort, 0) + 1

    rapport = Rapport(
        doc_id=doc_id, titel=titel, bladzijden=len(bladen),
        trefkans=st.trefkans, ingangen=len(st.ingangen), secties=len(secties),
        verschuiving=st.ijking.verschuiving, fragmenten=len(fragmenten),
        dekking=dek, per_soort=per_soort,
        rookproef={"gevraagd": uitslag.gevraagd, "geslaagd": uitslag.geslaagd,
                   "aandeel": uitslag.aandeel, "proeven": uitslag.proeven},
    )
    melden("klaar")
    return bank, rapport
