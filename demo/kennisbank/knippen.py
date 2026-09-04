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

# De maat van een fragment, in woorden. Afgesproken op 31-08-2026: minstens
# 150, hoogstens 400, en in de meeste gevallen dichter bij de bovengrens.
# Woorden en niet tekens, omdat dat de eenheid is waarin over de maat gesproken
# wordt; een omrekening in de code levert alleen verwarring op bij de volgende
# die hem wil bijstellen.
MIN_WOORDEN = 150
MAX_WOORDEN = 400
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


ZINSEINDE = re.compile(r"(?<=[.!?;:])\s+")


def _tel(tekst: str) -> int:
    return len(tekst.split())


def _hak_lange_alinea(alinea: str, max_woorden: int) -> list[str]:
    """Splitst een alinea die zelf al te lang is, op zinsgrens.

    Zonder dit bestaat de maat alleen op papier: een enkele alinea van
    zeshonderd woorden zou er ongesplitst doorheen glippen en de band die we
    net hebben afgesproken meteen weer stukmaken.
    """
    if _tel(alinea) <= max_woorden:
        return [alinea]
    stukken, buffer, lengte = [], [], 0
    for zin in ZINSEINDE.split(alinea):
        w = _tel(zin)
        if buffer and lengte + w > max_woorden:
            stukken.append(" ".join(buffer))
            buffer, lengte = [], 0
        buffer.append(zin)
        lengte += w
    if buffer:
        stukken.append(" ".join(buffer))
    return stukken


def _herverdeel_staart(stukken: list[list[str]], min_woorden: int,
                       max_woorden: int) -> list[list[str]]:
    """Trekt de laatste twee stukken recht als de staart te dun uitvalt.

    Vullen tot de bovengrens laat aan het eind vanzelf een restje over: een
    eenheid van 450 woorden wordt anders 400 plus 50, en dat laatste stuk is
    als antwoord te mager. We schuiven daarom alinea's terug tot beide stukken
    binnen de band vallen, en lukt dat niet, dan gaan ze samen.
    """
    if len(stukken) < 2:
        return stukken
    staart = sum(_tel(s) for s in stukken[-1])
    if staart >= min_woorden:
        return stukken

    vorige = stukken[-2]
    while staart < min_woorden and len(vorige) > 1:
        w = _tel(vorige[-1])
        if sum(_tel(s) for s in vorige) - w < min_woorden:
            break                      # de buur zou zelf onder de maat zakken
        if staart + w > max_woorden:
            break
        stukken[-1].insert(0, vorige.pop())
        staart += w

    if staart < min_woorden and sum(_tel(s) for s in vorige) + staart <= max_woorden:
        vorige.extend(stukken.pop())
    return stukken


def knip_op_woorden(alineas: list[str],
                    min_woorden: int = MIN_WOORDEN,
                    max_woorden: int = MAX_WOORDEN) -> list[list[str]]:
    """Verdeelt alinea's over stukken van min_woorden tot max_woorden.

    Een stuk wordt gevuld tot de volgende alinea er niet meer bij past. Zo
    komen de meeste stukken in de bovenste helft van de band uit, wat de
    afspraak is: minstens 150 woorden, meestal meer, nooit boven 400.

    Een alinea blijft heel zolang dat kan. Hem middenin doorknippen kost meer
    aan begrijpelijkheid dan de maat oplevert, dus de grens valt bij voorkeur
    op een alineagrens en pas bij nood op een zinsgrens.
    """
    fijn: list[str] = []
    for a in alineas:
        if a.strip():
            fijn.extend(_hak_lange_alinea(a.strip(), max_woorden))

    stukken: list[list[str]] = []
    buffer: list[str] = []
    lengte = 0
    for a in fijn:
        w = _tel(a)
        if buffer and lengte + w > max_woorden:
            stukken.append(buffer)
            buffer, lengte = [], 0
        buffer.append(a)
        lengte += w
    if buffer:
        stukken.append(buffer)
    return _herverdeel_staart(stukken, min_woorden, max_woorden)


def knip(bladen: list[Blad], secties: list[Sectie],
         overslaan: set[int] | None = None,
         gedrukt_van: dict[int, int] | None = None) -> list[Fragment]:
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

        loop: list[str] = []

        def spoel() -> None:
            for stuk in knip_op_woorden(loop):
                nieuw(stuk, "tekst")
            loop.clear()

        for soort, tekst in _alineas(blad):
            if soort != "tekst":
                # Een tabel of een voetnotenblok is een eenheid en gaat nooit
                # samen met lopende tekst in een fragment. De lopende tekst die
                # eraan voorafging wordt eerst afgesloten, anders zou hij over
                # de tabel heen aan de tekst erna vastgroeien.
                spoel()
                nieuw([tekst], soort)
                continue
            loop.append(tekst)
        spoel()

    # Te dunne tekstfragmenten samenvoegen met hun buur op dezelfde bladzijde:
    # een losse regel zonder context wordt nooit een bruikbaar antwoord.
    # De buur wordt gezocht voorbij tabellen en voetnoten: die staan er tussen
    # zonder de lopende tekst te onderbreken, en anders zou een kort stukje
    # tekst vlak voor een tabel nooit meer een maat krijgen.
    samengevoegd: list[Fragment] = []
    for f in fragmenten:
        vorige = next((v for v in reversed(samengevoegd)
                       if v.soort == "tekst" and v.fysiek == f.fysiek), None)
        if (vorige and f.soort == "tekst"
                and _tel(vorige.tekst) < MIN_WOORDEN):
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
