"""Randnummer-strategie: knippen op de citeereenheid van een juridisch vakboek.

Een rechtswetenschappelijk werk denkt in randnummers: doorlopend genummerde
alinea's waarmee het vak citeert ("Palmans/Jansen 2020, nr. 21"). De eerste
verwerking van het boek knipte op bladzijden en blokgrootte; technisch gezond,
maar de verkeerde eenheid, met de twee bekende gevolgen: alinea's die over een
paginagrens doormidden gaan, en voetnoten die los van hun alinea hangen.

Deze strategie knipt op het randnummer zelf. Drie regels:

1.  Een eenheid begint bij een alinea die met een randnummer opent en loopt
    door tot het volgende randnummer, ook over een paginagrens heen. De
    beginbladzijde blijft het adres: "nr. 21, blz 187".
2.  De reeks is de meetlat. Randnummers lopen monotoon op en herstarten per
    bijdrage (dit is een bundel). Elke sprong is een meetbaar gat, elke
    herstart wordt geboekt, en een kandidaat die nergens in de reeks past is
    geen randnummer maar gewone tekst. Zo bewaakt de reeks zichzelf, zonder
    model.
3.  Voetnoten horen bij hun alinea. Elke voetnoot wordt via zijn verwijzing in
    de lopende tekst aan de eenheid gekoppeld (gemeten: 81 procent direct);
    lukt dat niet, dan aan de eenheid die op die bladzijde actief is, en dat
    onderscheid wordt geboekt.

Alles hier is deterministisch: patronen en boekhouding, geen model.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .knippen import Fragment, MAX_WOORDEN, knip_op_woorden
from .ocrbron import Blad
from .structuur import Sectie

# Een randnummer-start: getal, punt, spatie, hoofdletter of aanhalingsteken.
# MULTILINE: een randnummer kan ook midden in een OCR-blok beginnen wanneer de
# OCR twee alinea's aan elkaar plakt; alleen op blokbegin toetsen miste er
# tientallen.
START = re.compile(r"^(\d{1,3})\.\s+[A-ZÀ-Ž\"'‘“(]", re.M)


def _segmenten(tekst: str) -> list[tuple[int | None, str]]:
    """Splitst een blok op regelbegin-randnummers.

    Geeft (nummer, stuk) terug; het eerste stuk kan nummerloos zijn (vervolg
    van de vorige alinea). Of een nummer echt een randnummer is beslist de
    reeks, niet dit patroon.
    """
    treffers = list(START.finditer(tekst))
    if not treffers:
        return [(None, tekst)]
    uit: list[tuple[int | None, str]] = []
    if treffers[0].start() > 0:
        uit.append((None, tekst[:treffers[0].start()]))
    for i, m in enumerate(treffers):
        eind = treffers[i + 1].start() if i + 1 < len(treffers) else len(tekst)
        uit.append((int(m.group(1)), tekst[m.start():eind]))
    return uit
VOETNOOT_REGEL = re.compile(r"^(\d{1,3})\s+\S")
# Hoe ver een sprong mag gaan voordat we de kandidaat wantrouwen. Een echt gat
# van twee, drie nummers komt voor (OCR-mist); een sprong van vijftig is vrijwel
# zeker een jaartal of een opsomming die op een randnummer lijkt.
MAX_SPRONG = 15
# Tekst buiten de randnummers (voorwerk, inleidingen) heeft geen eenheid om
# op te knippen en volgt daarom gewoon de woordband.
DOEL_WOORDEN_LOS = MAX_WOORDEN


@dataclass
class Reeksverslag:
    """De boekhouding van de reeks; dit is de nieuwe kwaliteitsmeting."""
    eenheden: int = 0
    opeenvolgend: int = 0
    herstarts: int = 0
    gaten: list[dict] = field(default_factory=list)        # {na, naar, bladzijde}
    verworpen: list[dict] = field(default_factory=list)    # {getal, bladzijde}
    voetnoten_via_verwijzing: int = 0
    voetnoten_via_bladzijde: int = 0

    def als_dict(self) -> dict:
        return {
            "eenheden": self.eenheden,
            "opeenvolgend": self.opeenvolgend,
            "herstarts": self.herstarts,
            "gaten": self.gaten,
            "verworpen_kandidaten": len(self.verworpen),
            "voetnoten_via_verwijzing": self.voetnoten_via_verwijzing,
            "voetnoten_via_bladzijde": self.voetnoten_via_bladzijde,
        }


def _sectie_van(fysiek: int, secties: list[Sectie]) -> Sectie | None:
    gekozen = None
    for s in secties:
        if s.van <= fysiek <= s.tot:
            if gekozen is None or s.niveau >= gekozen.niveau:
                gekozen = s
    return gekozen


def _past_in_reeks(n: int, vorige: int | None,
                   verslag: Reeksverslag, bladzijde: int | None) -> bool:
    """Beslist of kandidaat n een randnummer is, en boekt wat er gebeurt."""
    if vorige is None or n == vorige + 1:
        verslag.opeenvolgend += 1
        return True
    if vorige + 2 <= n <= vorige + MAX_SPRONG:
        verslag.gaten.append({"na": vorige, "naar": n, "bladzijde": bladzijde})
        return True
    # Geen herstart binnen een bijdrage: paragraaf-kopjes ("2. Het
    # bewijsprobleem") zien er precies zo uit en kaapten de reeks, waarna het
    # echte vervolgnummer werd verworpen. De hoofdstukwissel reset de reeks al.
    verslag.verworpen.append({"getal": n, "bladzijde": bladzijde})
    return False


def knip_op_randnummer(bladen: list[Blad], secties: list[Sectie],
                       hoofdstukken: dict[int, str],
                       overslaan: set[int] | None = None,
                       gedrukt_van: dict[int, int] | None = None,
                       ) -> tuple[list[Fragment], Reeksverslag]:
    overslaan = overslaan or set()
    gedrukt_van = gedrukt_van or {}
    verslag = Reeksverslag()
    fragmenten: list[Fragment] = []

    # De OCR noemt twee dingen 'kop': de paginakop die op elke bladzijde
    # terugkeert (ruis) en een vetgedrukt tussenkopje in de tekst (inhoud, en
    # vaak de drager van het randnummer). Herhaling is het onderscheid.
    kop_telling = Counter(
        blok.tekst.strip()
        for blad in bladen for blok in blad.blokken
        if blok.soort == "kop" and blok.tekst.strip())
    paginakoppen = {tekst for tekst, n in kop_telling.items() if n >= 3}

    def maak(stukken: list[str], soort: str, fysiek: int,
             randnummer: int | None) -> Fragment | None:
        tekst = "\n\n".join(s.strip() for s in stukken if s.strip()).strip()
        if len(tekst) < 2:
            return None
        sectie = _sectie_van(fysiek, secties)
        f = Fragment(
            volgnummer=0, tekst=tekst, soort=soort, fysiek=fysiek,
            gedrukt=gedrukt_van.get(fysiek),
            hoofdstuk=hoofdstukken.get(fysiek, ""),
            sectie=sectie.titel if sectie else "",
            kop_pad=[p for p in (hoofdstukken.get(fysiek, ""),
                                 sectie.titel if sectie else "") if p],
            bron_tekens=sum(len(s.strip()) for s in stukken))
        f.randnummer = randnummer
        fragmenten.append(f)
        return f

    # ---- fase 1: de lopende tekst in eenheden
    eenheid: list[str] = []
    eenheid_start: int | None = None
    eenheid_nr: int | None = None
    eenheid_hoofdstuk: str = ""
    vorige_nr: int | None = None
    # titels tussen twee eenheden horen bij wat VOLGT, niet bij wat voorafging
    kop_wacht: list[str] = []
    los: list[str] = []               # tekst buiten een eenheid (voorwerk, intro)
    los_start: int | None = None
    los_lengte = 0
    # tabellen die binnen een eenheid vallen erven straks het randnummer
    tabel_wacht: list[tuple[int, str]] = []

    def sluit_eenheid() -> None:
        nonlocal eenheid, eenheid_start, eenheid_nr, eenheid_hoofdstuk
        if eenheid and eenheid_start is not None:
            # Een randnummer blijft de citeereenheid, ook als het over drie
            # bladzijden doorloopt. Maar een fragment van duizend woorden is
            # als antwoord onbruikbaar en als vector nog erger, dus een lange
            # eenheid wordt opgedeeld en elk deel houdt hetzelfde nummer als
            # adres. Voor het tellen blijft het een eenheid.
            for deel in knip_op_woorden(eenheid):
                maak(deel, "tekst", eenheid_start, eenheid_nr)
            verslag.eenheden += 1
        eenheid, eenheid_start, eenheid_nr = [], None, None
        eenheid_hoofdstuk = ""

    def sluit_los() -> None:
        nonlocal los, los_start, los_lengte
        if los and los_start is not None:
            for deel in knip_op_woorden(los):
                maak(deel, "tekst", los_start, None)
        los, los_start, los_lengte = [], None, 0

    for blad in bladen:
        if blad.fysiek in overslaan:
            continue
        # losse tekst blijft, zoals in v1, binnen zijn bladzijde
        if los and los_start != blad.fysiek:
            sluit_los()
        # Een hoofdstukwissel sluit de lopende eenheid: het laatste randnummer
        # van een bijdrage mag de ongenummerde intro van de volgende bijdrage
        # niet opslokken, en de nummering herstart daar toch.
        h = hoofdstukken.get(blad.fysiek, "")
        if eenheid and eenheid_hoofdstuk and h and h != eenheid_hoofdstuk:
            sluit_eenheid()
            if vorige_nr is not None:
                verslag.herstarts += 1
            vorige_nr = None
        for blok in blad.blokken:
            if blok.soort == "tabel":
                tabel_wacht.append((blad.fysiek, blok.tekst))
                continue
            if blok.soort == "kop" and blok.tekst.strip() in paginakoppen:
                continue                      # de herhaalde paginakop is ruis
            if blok.soort in ("titel", "kop"):
                # Een tussenkopje dat zelf met een randnummer begint start de
                # eenheid; anders bufferen tot de volgende eenheid of de losse
                # tekst, want een titel hoort bij wat volgt.
                m = START.match(blok.tekst.strip())
                if not (m and _past_in_reeks(int(m.group(1)), vorige_nr,
                                             verslag,
                                             gedrukt_van.get(blad.fysiek))):
                    kop_wacht.append(blok.tekst.strip())
                    continue
                sluit_los()
                sluit_eenheid()
                eenheid = kop_wacht + [blok.tekst.strip()]
                kop_wacht = []
                eenheid_start = blad.fysiek
                eenheid_nr = int(m.group(1))
                eenheid_hoofdstuk = hoofdstukken.get(blad.fysiek, "")
                vorige_nr = eenheid_nr
                continue
            if blok.soort != "tekst":
                continue
            for kandidaat_nr, stuk in _segmenten(blok.tekst.strip()):
                if (kandidaat_nr is not None
                        and _past_in_reeks(kandidaat_nr, vorige_nr, verslag,
                                           gedrukt_van.get(blad.fysiek))):
                    sluit_los()
                    sluit_eenheid()
                    eenheid = kop_wacht + [stuk]
                    kop_wacht = []
                    eenheid_start = blad.fysiek
                    eenheid_nr = kandidaat_nr
                    eenheid_hoofdstuk = hoofdstukken.get(blad.fysiek, "")
                    vorige_nr = eenheid_nr
                elif eenheid:
                    eenheid.append(stuk)
                else:
                    if los_start is None:
                        los_start = blad.fysiek
                    if kop_wacht:
                        los = kop_wacht + los
                        kop_wacht = []
                    los.append(stuk)
                    los_lengte += len(stuk.split())
                    if los_lengte > DOEL_WOORDEN_LOS:
                        sluit_los()
        # tabellen: eigen fragment, met het randnummer van de actieve eenheid
        for fysiek, tekst in tabel_wacht:
            maak([tekst], "tabel", fysiek, eenheid_nr)
        tabel_wacht = []
    if kop_wacht:
        los.extend(kop_wacht)
        if los_start is None and bladen:
            los_start = bladen[-1].fysiek
        kop_wacht = []
    sluit_los()
    sluit_eenheid()

    # ---- fase 2: voetnoten aan hun eenheid hechten
    # eenheden per bladzijde-bereik, om de verwijzing te kunnen zoeken
    eenheden = [f for f in fragmenten if f.soort == "tekst"
                and getattr(f, "randnummer", None) is not None]
    # welke eenheid is 'actief' op een fysieke bladzijde (de laatst gestarte)
    actief_op: dict[int, Fragment] = {}
    for f in eenheden:
        actief_op[f.fysiek] = f
    laatste = None
    actief_lopend: dict[int, Fragment] = {}
    for blad in bladen:
        if blad.fysiek in actief_op:
            laatste = actief_op[blad.fysiek]
        if laatste is not None:
            actief_lopend[blad.fysiek] = laatste

    for blad in bladen:
        if blad.fysiek in overslaan:
            continue
        # voetnoten van deze bladzijde, per nummer gesplitst
        noten: list[tuple[str, str]] = []
        for blok in blad.blokken:
            if blok.soort != "voet":
                continue
            huidig_nr, huidig = None, []
            vervolg: list[str] = []
            for regel in blok.tekst.splitlines():
                m = VOETNOOT_REGEL.match(regel.strip())
                if m:
                    if huidig_nr is not None:
                        noten.append((huidig_nr, "\n".join(huidig)))
                    huidig_nr, huidig = m.group(1), [regel.strip()]
                elif huidig_nr is not None:
                    huidig.append(regel.strip())
                elif regel.strip():
                    # nummerloze kopregels: het vervolg van de voetnoot die op
                    # de vorige bladzijde begon, geen afval
                    vervolg.append(regel.strip())
            if huidig_nr is not None:
                noten.append((huidig_nr, "\n".join(huidig)))
            if vervolg:
                noten.insert(0, ("vervolg", "\n".join(vervolg)))
        if not noten:
            continue
        # kandidaten: eenheden die deze bladzijde raken
        # kandidaten: eenheden die op deze bladzijde beginnen, plus de eenheid
        # die er nog doorloopt; ontdubbeld op identiteit want een dataclass is
        # niet hashbaar
        raakt = []
        doorloper = actief_lopend.get(blad.fysiek - 1)
        for f in ([*[f for f in eenheden if f.fysiek == blad.fysiek]]
                  + ([actief_lopend[blad.fysiek]]
                     if blad.fysiek in actief_lopend else [])
                  + ([doorloper] if doorloper is not None else [])):
            if not any(f is r for r in raakt):
                raakt.append(f)
        for nr, tekst in noten:
            # Ruis op vorm, zoals v1: een paginanummer, de uitgever of een
            # spatieveld is geen voetnoot. Eerst spatieruns platslaan, dan
            # meten wat er werkelijk staat.
            tekst = re.sub(r"[ \t]{3,}", " ", tekst).strip()
            kaal = re.sub(r"\s", "", tekst)
            if len(kaal) < 40 or re.fullmatch(
                    r"(?i)\d{0,4}(intersentia|crow)?\d{0,4}", kaal):
                continue
            doelwit = None
            if nr != "vervolg":
                for f in raakt:
                    if re.search(rf"[a-zà-ž\)\.,;”’\"]({nr})(?!\d)", f.tekst):
                        doelwit = f
                        verslag.voetnoten_via_verwijzing += 1
                        break
            if doelwit is None and blad.fysiek in actief_lopend:
                doelwit = actief_lopend[blad.fysiek]
                verslag.voetnoten_via_bladzijde += 1
            f = maak([tekst], "voetnoot", blad.fysiek,
                     getattr(doelwit, "randnummer", None) if doelwit else None)
            if f is not None and doelwit is not None:
                f.kop_pad = list(doelwit.kop_pad) + [f"voetnoot bij nr. {doelwit.randnummer}"]

    for n, f in enumerate(fragmenten, start=1):
        f.volgnummer = n
    return fragmenten, verslag
