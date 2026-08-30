"""Fragmenten maken uit bladzijden en secties.

Drie regels, en alle drie zijn ze een keus die je later niet meer kunt herstellen.

1. Een fragment blijft binnen een bladzijde. Anders kun je niet zeggen waar een
   antwoord vandaan komt, en bij een juridisch werk is een antwoord zonder
   vindplaats waardeloos.
2. Ruis gaat eruit op TYPE, niet op herhaling. De OCR merkt zelf aan wat koptekst
   en wat voettekst is; dat is betrouwbaarder dan tellen hoe vaak een regel
   voorkomt. Een productnaam die toevallig op elke bladzijde staat overleeft dat.
3. Voetnoten zijn inhoud, geen ruis. In een rechtswetenschappelijk werk staat de
   halve bewijsvoering eronder. Ze krijgen een eigen soort zodat het ophalen ze
   apart kan wegen, maar ze gaan mee.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ocrbron import Blad
from .structuur import Sectie

DOEL_TEKENS = 1800
MIN_TEKENS = 200
# Korter dan dit is een voettekst geen voetnoot maar een paginanummer of het
# impressum van de uitgever.
MIN_VOETNOOT = 80
# Regels die als losse voettekst voorkomen en nooit inhoud zijn.
IMPRESSUM = re.compile(r"^(intersentia|crow|\d{1,4}|[ivxlcdm]{1,7})$", re.I)


@dataclass
class Fragment:
    volgnummer: int
    tekst: str
    soort: str                     # tekst | tabel | voetnoot
    fysiek: int
    gedrukt: int | None
    hoofdstuk: str = ""
    sectie: str = ""
    kop_pad: list[str] = field(default_factory=list)
    # Het randnummer waarmee dit fragment citeerbaar is (verwerking v2,
    # randnummer-strategie). None bij voorwerk, tabellen zonder eenheid en de
    # bladzijde-strategie van v1.
    randnummer: int | None = None
    # Hoeveel tekens brontekst hier in zitten. Niet hetzelfde als len(tekst):
    # samenvoegen zet er lege regels tussen, en die zijn geen inhoud. Wie dat
    # verschil niet bijhoudt rapporteert een dekking van boven de honderd
    # procent, en een getal dat niet kan is erger dan geen getal.
    bron_tekens: int = 0

    @property
    def met_context(self) -> str:
        """De tekst met zijn kop-keten ervoor.

        Zonder die keten weet een losse alinea niet meer waar hij bij hoort, en
        dan levert het ophalen een juist fragment op waar niemand iets aan heeft.
        """
        pad = " > ".join(p for p in self.kop_pad if p)
        return f"{pad}\n\n{self.tekst}" if pad else self.tekst


def _is_ruis(soort: str, tekst: str) -> bool:
    t = tekst.strip()
    if not t:
        return True
    if soort == "kop":
        return True                       # de herhaalde kop bovenaan de bladzijde
    if soort == "voet":
        return len(t) < MIN_VOETNOOT or bool(IMPRESSUM.match(t))
    return False


def _sectie_van(fysiek: int, secties: list[Sectie]) -> Sectie | None:
    gekozen = None
    for s in secties:
        if s.van <= fysiek <= s.tot:
            # De diepste sectie die deze bladzijde bevat wint: een paragraaf zegt
            # meer over waar je bent dan het hoofdstuk eromheen.
            if gekozen is None or s.niveau >= gekozen.niveau:
                gekozen = s
    return gekozen


def _alineas(blad: Blad) -> list[tuple[str, str]]:
    """De inhoudelijke blokken van een bladzijde, op volgorde, met hun soort."""
    uit: list[tuple[str, str]] = []
    for blok in blad.blokken:
        if _is_ruis(blok.soort, blok.tekst):
            continue
        soort = {"tabel": "tabel", "voet": "voetnoot"}.get(blok.soort, "tekst")
        uit.append((soort, blok.tekst.strip()))
    return uit


def knip(bladen: list[Blad], secties: list[Sectie],
         overslaan: set[int] | None = None,
         gedrukt_van: dict[int, int] | None = None,
         doel_tekens: int = DOEL_TEKENS) -> list[Fragment]:
    """Maakt de fragmenten. Bladzijden in `overslaan` (navigatie) doen niet mee."""
    overslaan = overslaan or set()
    gedrukt_van = gedrukt_van or {}
    fragmenten: list[Fragment] = []

    for blad in bladen:
        if blad.fysiek in overslaan:
            continue
        sectie = _sectie_van(blad.fysiek, secties)
        kop_pad = [p for p in ((sectie.hoofdstuk if sectie else ""),
                               (sectie.titel if sectie else "")) if p]

        def nieuw(stukken: list[str], soort: str) -> None:
            tekst = "\n\n".join(stukken).strip()
            if len(tekst) < 2:
                return
            fragmenten.append(Fragment(
                volgnummer=0, tekst=tekst, soort=soort,
                fysiek=blad.fysiek, gedrukt=gedrukt_van.get(blad.fysiek),
                hoofdstuk=sectie.hoofdstuk if sectie else "",
                sectie=sectie.titel if sectie else "",
                kop_pad=list(kop_pad),
                bron_tekens=sum(len(s) for s in stukken)))

        buffer: list[str] = []
        lengte = 0
        for soort, tekst in _alineas(blad):
            if soort != "tekst":
                # Een tabel of een voetnotenblok is een eenheid en gaat nooit
                # samen met lopende tekst in een fragment.
                nieuw([tekst], soort)
                continue
            if buffer and lengte + len(tekst) > doel_tekens:
                nieuw(buffer, "tekst")
                buffer, lengte = [], 0
            buffer.append(tekst)
            lengte += len(tekst)
        if buffer:
            nieuw(buffer, "tekst")

    # Te dunne tekstfragmenten samenvoegen met hun buur op dezelfde bladzijde:
    # een losse regel zonder context wordt nooit een bruikbaar antwoord.
    samengevoegd: list[Fragment] = []
    for f in fragmenten:
        vorige = samengevoegd[-1] if samengevoegd else None
        if (vorige and f.soort == "tekst" and vorige.soort == "tekst"
                and vorige.fysiek == f.fysiek and len(vorige.tekst) < MIN_TEKENS):
            vorige.tekst = f"{vorige.tekst}\n\n{f.tekst}"
            vorige.bron_tekens += f.bron_tekens
            continue
        samengevoegd.append(f)

    for n, f in enumerate(samengevoegd, start=1):
        f.volgnummer = n
    return samengevoegd


def dekking(bladen: list[Blad], fragmenten: list[Fragment],
            overslaan: set[int] | None = None) -> dict:
    """Hoeveel van de inhoudelijke brontekst is in een fragment beland?

    Geen steekproef maar een telling. Wat hier wegvalt kan niemand ooit
    terugvinden, en dat hoort geen verrassing te zijn.
    """
    overslaan = overslaan or set()
    bron = 0
    for blad in bladen:
        if blad.fysiek in overslaan:
            continue
        bron += sum(len(t) for _, t in _alineas(blad))
    gevangen = sum(f.bron_tekens for f in fragmenten)
    return {
        "brontekens": bron,
        "fragmenttekens": gevangen,
        "aandeel": (gevangen / bron) if bron else 0.0,
        "fragmenten": len(fragmenten),
        "overgeslagen_bladzijden": len(overslaan),
    }
