"""Structuur uit de inhoudsopgave en de paginaindeling.

Dit is het hart van de applicatie. Een boek vertelt zelf hoe het is ingedeeld,
op drie plekken die elkaar controleren:

  inhoudsopgave   titel + GEDRUKT paginanummer
  voettekst       het gedrukte nummer van de bladzijde waar je nu bent
  koptekst        de herhaalde hoofdstuk- of auteursnaam bovenaan
  titelblokken    de koppen zoals ze in de lopende tekst staan

Het gedrukte nummer is niet het fysieke: een boek begint met romeins genummerd
voorwerk en de arabische telling start pas bij het eerste hoofdstuk. Zonder die
ijking wijst elke verwijzing uit de inhoudsopgave naar de verkeerde scan.

Daarom deze volgorde: eerst ijken op de voetteksten, dan de inhoudsopgave lezen,
en dan VERIFIEREN of de titel uit de inhoudsopgave ook echt staat waar hij hoort.
Dat laatste levert een percentage op, en dat percentage is de poort. Geen oordeel
van een model over een ander model, maar een meting die je kunt narekenen.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from .ocrbron import Blad

# Een regel uit een inhoudsopgave: tekst, opvulling, en precies een getal.
# De opvulling is meestal een puntjeslijn, maar soms alleen witruimte.
INHOUDSREGEL = re.compile(r"^(.{4,}?)[\s.·…]{3,}(\d{1,4})\s*$")
# Sommige inhoudsopgaven zetten het nummer zonder opvulling er direct achter.
INHOUDSREGEL_KAAL = re.compile(r"^(.{6,}?)\s+(\d{1,4})\s*$")
ROMEINS = re.compile(r"^[ivxlcdm]+$", re.I)
ARABISCH = re.compile(r"^\d{1,4}$")
ROMEINSE_WAARDE = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}

# Titels die navigatie zijn en nooit een eigen sectie mogen worden.
NAVIGATIE = re.compile(
    r"^\s*(inhoud|inhoudsopgave|contents|index|register|"
    r"list of figures|lijst van afkortingen|bibliografie)\s*$", re.I)


def romeins_naar_getal(s: str) -> int | None:
    s = s.strip().lower()
    if not s or not ROMEINS.match(s):
        return None
    totaal, vorige = 0, 0
    for teken in reversed(s):
        w = ROMEINSE_WAARDE[teken]
        totaal = totaal - w if w < vorige else totaal + w
        vorige = max(vorige, w)
    return totaal or None


def _normaliseer(t: str) -> str:
    """Voor het vergelijken van titels: accenten weg, kleine letters, alleen woorden.

    Een afbreekstreepje aan het eind van een regel is geen streepje maar een
    woord dat doorloopt. Laat je dat staan, dan wordt "stedenbouw-\\nkundig" twee
    woorden terwijl de inhoudsopgave er een van maakte, en dan vindt de
    verificatie de titel niet terwijl hij er gewoon staat.
    """
    t = re.sub(r"-\s*\n\s*", "", t)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", t.lower()))


# ---------------------------------------------------------------- ijking

@dataclass
class Meting:
    fysiek: int
    soort: str          # 'romeins' of 'arabisch'
    gedrukt: int


@dataclass
class IJking:
    """Hoe gedrukte nummers zich verhouden tot fysieke bladzijden."""
    verschuiving: int | None            # fysiek = gedrukt + verschuiving
    metingen: int
    eensgezind: int                     # metingen die deze verschuiving steunen
    voorwerk_tot: int = 0               # laatste fysieke bladzijde met romeinse telling

    @property
    def betrouwbaarheid(self) -> float:
        return self.eensgezind / self.metingen if self.metingen else 0.0

    def naar_fysiek(self, gedrukt: int) -> int | None:
        if self.verschuiving is None:
            return None
        return gedrukt + self.verschuiving


def metingen_uit_voet(bladen: list[Blad]) -> list[Meting]:
    """Leest de gedrukte paginanummers uit de kop- en voetteksten.

    Per REGEL en niet per blok. Het ene boek zet het nummer als losse voettekst
    ("x", "Intersentia"), het andere plakt het aan de titel vast:

        4
        User Manual WMF 1200 S

    Dat is een blok, maar het nummer staat op zijn eigen regel. Wie hele blokken
    toetst vindt bij zo'n document niets, kan niet ijken, en verliest daarmee de
    hele inhoudsopgave.

    Een voetnoot die met een cijfer begint levert geen meting op: die regel bevat
    ook tekst. Wat er wel doorheen glipt zijn losse cijfers uit een figuurlegenda
    onderaan de bladzijde. Daarom wordt er gestemd in plaats van gerekend: een
    handvol verdwaalde getallen verliest het van zeventig eensluidende metingen.
    """
    grens = len(bladen) + 100
    uit: list[Meting] = []
    for blad in bladen:
        for soort in ("voet", "kop"):
            for tekst in blad.van_soort(soort):
                for regel in tekst.splitlines():
                    r = regel.strip()
                    if not r or len(r) > 12:
                        continue
                    if ARABISCH.match(r):
                        waarde, soortnaam = int(r), "arabisch"
                    elif (w := romeins_naar_getal(r)) is not None:
                        waarde, soortnaam = w, "romeins"
                    else:
                        continue
                    if 1 <= waarde <= grens:
                        uit.append(Meting(blad.fysiek, soortnaam, waarde))
    return uit


def ijk(bladen: list[Blad]) -> IJking:
    """Bepaalt de verschuiving tussen gedrukte en fysieke nummering.

    De verschuiving is per definitie constant binnen een genummerd blok, dus de
    juiste waarde is degene waar de meeste metingen het over eens zijn. Een enkele
    verkeerd gelezen voettekst schuift de uitkomst zo niet op.
    """
    metingen = metingen_uit_voet(bladen)
    arabisch = [m for m in metingen if m.soort == "arabisch"]
    romeins = [m for m in metingen if m.soort == "romeins"]

    if not arabisch:
        return IJking(None, len(metingen), 0,
                      voorwerk_tot=max((m.fysiek for m in romeins), default=0))

    tel = Counter(m.fysiek - m.gedrukt for m in arabisch)
    verschuiving, eens = tel.most_common(1)[0]
    return IJking(
        verschuiving=verschuiving,
        metingen=len(arabisch),
        eensgezind=eens,
        voorwerk_tot=max((m.fysiek for m in romeins), default=0),
    )


# ---------------------------------------------------------------- inhoudsopgave

@dataclass
class Ingang:
    titel: str
    gedrukt: int
    niveau: int = 1
    fysiek: int | None = None
    gevonden: bool = False          # staat de titel echt op die bladzijde?
    afwijking: int | None = None    # zo niet: hoeveel bladzijden ernaast


def _is_inhoudsregel(regel: str) -> tuple[str, int] | None:
    for patroon in (INHOUDSREGEL, INHOUDSREGEL_KAAL):
        m = patroon.match(regel)
        if m:
            titel = m.group(1).strip(" .·…\t")
            if len(titel) >= 4 and not titel.isdigit():
                return titel, int(m.group(2))
    return None


def vind_inhoudsopgave(bladen: list[Blad], drempel: float = 0.3) -> list[int]:
    """Welke fysieke bladzijden zijn inhoudsopgave.

    Twee aanwijzingen: de koptekst zegt het zelf, of het merendeel van de regels
    is 'tekst, opvulling, precies een getal'. Dat laatste is de toets die een
    gegevenstabel overleeft: een tabelrij heeft meer dan een getal per regel.
    """
    kandidaat: list[int] = []
    for blad in bladen:
        if NAVIGATIE.match(blad.koptekst or ""):
            kandidaat.append(blad.fysiek)
            continue
        regels = [r.strip() for r in blad.markdown.splitlines() if len(r.strip()) > 3]
        if len(regels) < 5:
            continue
        treffers = sum(1 for r in regels if _is_inhoudsregel(r))
        if treffers / len(regels) >= drempel and treffers >= 4:
            kandidaat.append(blad.fysiek)
    return sorted(set(kandidaat))


def _plak(*stukken: str) -> str:
    """Voegt regels van een titel samen, met de afbreekstreepjes eruit.

    Een inhoudsopgave breekt lange woorden af: "de vaststelling van de
    vrijwillige uitvoering van de herstel-" / "maatregelen". Met een spatie
    ertussen wordt dat "herstel- maatregelen", en die tekst staat nergens in het
    boek. Eindigt een stuk op een streepje, dan hoort het volgende er direct
    tegenaan.
    """
    uit = ""
    for stuk in (s.strip() for s in stukken if s and s.strip()):
        if not uit:
            uit = stuk
        elif uit.endswith("-"):
            uit = uit[:-1] + stuk
        else:
            uit = f"{uit} {stuk}"
    return uit.strip()


def _niveau(titel: str) -> int:
    """Ruwe diepte uit de nummering van de titel zelf."""
    t = titel.strip()
    if re.match(r"^(deel|hoofdstuk|afdeling)\b", t, re.I):
        return 1
    if re.match(r"^§", t):
        return 2
    if re.match(r"^[A-Z]\.", t):
        return 3
    if re.match(r"^\d+\.", t):
        return 4
    return 2


MAX_VERVOLGREGELS = 3
# Onder deze lengte zoeken we een titel alleen in de titelblokken en niet in de
# lopende tekst: korte titels als "1. Historiek" komen overal voor.
MIN_TEKST_TREFFER = 18


def lees_ingangen(bladen: list[Blad], paginas: list[int]) -> list[Ingang]:
    """Alle 'titel + gedrukt nummer'-regels van de inhoudsopgavebladzijden.

    Een titel loopt vaak over meer dan een regel; alleen de laatste draagt het
    paginanummer. Bij dit boek staat er:

        Afdeling 2. Informatieverplichtingen voor de instrumenterende ambtenaar
        bij overdrachten (art. 5.2.1 VCRO) . . . . . . . . . . . . . . . . .  2

    Wie alleen de genummerde regel pakt houdt "bij overdrachten (art. 5.2.1
    VCRO)" over, en die tekst staat nergens in het boek als kop. De verificatie
    zakt daar terecht op. Regels zonder nummer worden daarom bewaard en voor de
    volgende genummerde regel geplakt; een lege regel scheidt twee ingangen en
    gooit de voorraad weg.
    """
    op_nummer = {b.fysiek: b for b in bladen}
    uit: list[Ingang] = []
    for p in paginas:
        blad = op_nummer.get(p)
        if not blad:
            continue
        vervolg: list[str] = []
        for regel in blad.markdown.splitlines():
            kaal = regel.strip()
            if not kaal:
                vervolg.clear()
                continue
            gevonden = _is_inhoudsregel(kaal)
            if not gevonden:
                # Geen nummer: mogelijk het eerste stuk van een titel. Opvulling
                # eraf, want een regel die alleen doorloopt eindigt vaak in punten.
                stuk = kaal.strip(" .·…\t")
                if stuk and not NAVIGATIE.match(stuk):
                    vervolg.append(stuk)
                    del vervolg[:-MAX_VERVOLGREGELS]
                continue
            titel, nr = gevonden
            if NAVIGATIE.match(titel):
                vervolg.clear()
                continue
            volledig = _plak(*vervolg, titel)
            vervolg.clear()
            uit.append(Ingang(titel=volledig, gedrukt=nr, niveau=_niveau(volledig)))

    # Een inhoudsopgave loopt op. Ingangen die terugspringen zijn misleeswerk
    # (een jaartal of een randnummer dat als paginanummer is aangezien).
    opgeschoond: list[Ingang] = []
    hoogste = 0
    for ingang in uit:
        if ingang.gedrukt >= hoogste:
            opgeschoond.append(ingang)
            hoogste = ingang.gedrukt
    return opgeschoond


# ---------------------------------------------------------------- verificatie

def verifieer(ingangen: list[Ingang], bladen: list[Blad], ijking: IJking,
              speling: int = 2) -> float:
    """Staat elke titel uit de inhoudsopgave ook echt op de bladzijde waar hij hoort?

    Dit is de poort van de hele applicatie. Hij vergelijkt de genormaliseerde
    titel met de titelblokken die de OCR op die bladzijde aanwees, met een kleine
    speling omdat een kop bovenaan de volgende bladzijde kan staan.

    Geeft het aandeel teruggevonden ingangen terug en vult per ingang in wat er
    gevonden is, zodat het correctiescherm kan tonen waar het misging.

    De vergelijking gaat tegen de HELE paginatekst en niet alleen tegen de
    titelblokken. De OCR markeert lang niet elke kop als titel: op bladzijde 17
    staat "§ 1. ALGEMEEN" gewoon in de lopende tekst terwijl alleen de afdeling
    een titelblok kreeg. Toetsen op titelblokken alleen gaf 31 procent, en dat
    zegt iets over de OCR-markering en niets over de inhoudsopgave.

    Korte titels worden alleen tegen de titelblokken gelegd. "1. Historiek" komt
    als losse woorden overal voor; die in een bladzijde vol tekst zoeken levert
    treffers op die niets bewijzen.
    """
    titels_per_blad: dict[int, list[str]] = {}
    tekst_per_blad: dict[int, str] = {}
    for blad in bladen:
        genormaliseerd = [_normaliseer(t) for t in blad.van_soort("titel")]
        if genormaliseerd:
            titels_per_blad[blad.fysiek] = genormaliseerd
        tekst_per_blad[blad.fysiek] = _normaliseer(blad.markdown)

    def _raakt(doel: str, blz: int) -> bool:
        for kandidaat in titels_per_blad.get(blz, []):
            if doel == kandidaat or doel in kandidaat or kandidaat in doel:
                return True
        if len(doel) >= MIN_TEKST_TREFFER:
            return doel in tekst_per_blad.get(blz, "")
        return False

    raak = 0
    for ingang in ingangen:
        ingang.fysiek = ijking.naar_fysiek(ingang.gedrukt)
        ingang.gevonden = False
        ingang.afwijking = None
        if ingang.fysiek is None:
            continue
        doel = _normaliseer(ingang.titel)
        if not doel:
            continue
        for delta in range(0, speling + 1):
            for kant in ((0,) if delta == 0 else (-delta, delta)):
                if _raakt(doel, ingang.fysiek + kant):
                    ingang.gevonden = True
                    ingang.afwijking = kant
                    break
            if ingang.gevonden:
                break
        raak += ingang.gevonden

    return raak / len(ingangen) if ingangen else 0.0


# ---------------------------------------------------------------- hoofdstukken

@dataclass
class Sectie:
    titel: str
    van: int                 # fysieke bladzijde, inclusief
    tot: int                 # fysieke bladzijde, inclusief
    niveau: int = 1
    hoofdstuk: str = ""      # uit de koptekst: waar hoort dit bij


def hoofdstuk_per_blad(bladen: list[Blad]) -> dict[int, str]:
    """De hoofdstuktitel per bladzijde, uit de herhaalde koptekst.

    Bij een bundel met meerdere auteurs staat op de ene bladzijde de auteur en op
    de andere de hoofdstuktitel. De titel is de langste van de twee die op die
    dubbele bladzijde voorkomen, en de auteursnaam de kortste; door naar de
    omgeving te kijken vullen we de bladzijden aan waar alleen de auteur staat.
    """
    kop = {b.fysiek: (b.koptekst or "").strip() for b in bladen}
    tel = Counter(k for k in kop.values() if k)
    # Kopteksten die vaak voorkomen zijn hoofdstuk- of auteursnamen; een die
    # maar een of twee keer voorkomt is ruis.
    vast = {k for k, n in tel.items() if n >= 3}

    uit: dict[int, str] = {}
    laatste = ""
    for blad in bladen:
        k = kop.get(blad.fysiek, "")
        if k in vast and not NAVIGATIE.match(k):
            # De langste van de kopteksten in dit blok is de hoofdstuktitel.
            buren = [kop.get(blad.fysiek + d, "") for d in (-1, 0, 1)]
            keuze = max((b for b in buren if b in vast), key=len, default=k)
            laatste = keuze
        uit[blad.fysiek] = laatste
    return uit


def secties(ingangen: list[Ingang], bladen: list[Blad],
            alleen_gevonden: bool = True) -> list[Sectie]:
    """Zet geverifieerde inhoudsopgave-ingangen om in secties met een bereik."""
    hoofdstukken = hoofdstuk_per_blad(bladen)
    laatste_blad = bladen[-1].fysiek if bladen else 0

    bruikbaar = [i for i in ingangen
                 if i.fysiek and (i.gevonden or not alleen_gevonden)]
    bruikbaar.sort(key=lambda i: i.fysiek or 0)

    uit: list[Sectie] = []
    for n, ingang in enumerate(bruikbaar):
        begin = ingang.fysiek or 0
        eind = (bruikbaar[n + 1].fysiek - 1) if n + 1 < len(bruikbaar) else laatste_blad
        uit.append(Sectie(titel=ingang.titel, van=begin, tot=max(begin, eind),
                          niveau=ingang.niveau,
                          hoofdstuk=hoofdstukken.get(begin, "")))
    return uit


@dataclass
class Structuur:
    """Het volledige structuurbeeld van een document, klaar voor het scherm."""
    ijking: IJking
    inhoudsopgave_paginas: list[int]
    ingangen: list[Ingang]
    trefkans: float
    secties: list[Sectie] = field(default_factory=list)

    @property
    def bruikbaar(self) -> bool:
        return self.trefkans >= 0.6 and len(self.secties) >= 3


def analyseer(bladen: list[Blad]) -> Structuur:
    ijking = ijk(bladen)
    paginas = vind_inhoudsopgave(bladen)
    ingangen = lees_ingangen(bladen, paginas)
    trefkans = verifieer(ingangen, bladen, ijking)
    return Structuur(
        ijking=ijking,
        inhoudsopgave_paginas=paginas,
        ingangen=ingangen,
        trefkans=trefkans,
        secties=secties(ingangen, bladen),
    )
