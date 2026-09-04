"""Waarom is deze treffer gevonden? Per treffer een uitleg die niets beweert
wat niet na te rekenen is.

Aanleiding (1 september 2026): de demo voelde als ctrl-F. Het verschil met
ctrl-F is dat Vindplaats ook vindt wat er met andere woorden staat, maar dat
verschil was onzichtbaar. Dit laat het zien, in twee lagen, allebei hard:

  letterlijk  welke woorden uit de vraag staan er echt in de tekst, ook als
              begin van een langer woord ("ziek" in "ziekteverlof"). Exact en
              deterministisch. Dit is wat ctrl-F ook kan.
  manier      is de treffer gevonden op woorden, op betekenis, of op beide?
              Rechtstreeks uit de twee ranglijsten van de hybride zoekopdracht
              (FTS5 en vectoren), plus de plek in de betekenisranglijst.

Wat er met opzet NIET in zit: een "lijkt op"-hint per woord (het vraagwoord
dat er niet staat, naast het tekstwoord dat er qua vector het dichtst bij
ligt). Dat is geprobeerd op 1 september en de losse woordvectoren van het
embedmodel zijn daar te ruw voor: "ziek" kwam uit op "beklaagde", "krijg" op
"waarop", "staat" op "algemeen". Een uitleg die soms onzin zegt is erger dan
geen uitleg. De betekenislaag werkt op de hele vraag tegen het hele fragment,
en dat is dan ook het enige wat we erover zeggen.

Geen taalmodel, geen kosten per zoekopdracht, geen opwarmen.
"""
from __future__ import annotations

import re

from markupsafe import Markup, escape

from kennisbank.opslag import Kennisbank

MAX_KNIPSEL = 600       # zelfde lengte als de tekst die de demo al toonde
MIN_PREFIX = 4          # "ziek" mag "ziekteverlof" aanwijzen; "is" niet "isolatie"

# Woorden die in een vraag vaak voorkomen maar als "letterlijke treffer" niets
# zeggen. Alleen voor de uitleg; het zoeken zelf gebruikt Kennisbank.STOPWOORDEN.
EXTRA_STOP = frozenset("""
    hebben heb hebt heeft had hadden krijg krijgt krijgen kreeg kregen
    staat staan stond stonden gaat gaan ging gingen komt komen kwam kwamen
    weet weten wist wisten word wordt worden werd werden zijn ben bent
    waren doen doet deed deden maken maakt maakte geval iemand iets
    veel meer minder erg heel echt gewoon eigenlijk dus dan als
""".split())

_woord = re.compile(r"\w+", re.UNICODE)


def vraagwoorden(vraag: str) -> list[str]:
    stop = Kennisbank.STOPWOORDEN | EXTRA_STOP
    uit: list[str] = []
    for w in _woord.findall(vraag.lower()):
        if len(w) > 1 and w not in stop and w not in uit:
            uit.append(w)
    return uit


def _letterlijk(vraagwoord: str, tekstwoorden: list[str]) -> str | None:
    """Het tekstwoord dat het vraagwoord letterlijk bevat, als begin.
    Een exact gelijk woord wint van een langer woord."""
    beste = None
    for tw in tekstwoorden:
        if tw == vraagwoord:
            return tw
        if beste is None and len(vraagwoord) >= MIN_PREFIX and tw.startswith(vraagwoord):
            beste = tw
    return beste


def _markeer(tekst: str, gevonden: set[str]) -> Markup:
    """Knipsel met de letterlijk gevonden woorden gemarkeerd. Eerst escapen,
    dan pas opmaak toevoegen, zodat documenttekst nooit als HTML landt."""
    knipsel = tekst[:MAX_KNIPSEL]
    stukken: list[str] = []
    pos = 0
    for m in _woord.finditer(knipsel):
        if m.group(0).lower() in gevonden:
            stukken.append(str(escape(knipsel[pos:m.start()])))
            stukken.append(f'<mark class="letterlijk">{escape(m.group(0))}</mark>')
            pos = m.end()
    stukken.append(str(escape(knipsel[pos:])))
    if len(tekst) > MAX_KNIPSEL:
        stukken.append("&hellip;")
    return Markup("".join(stukken))


def leg_uit(vraag: str, treffer) -> dict:
    """Uitleg bij een Treffer uit Kennisbank.zoek().

    letterlijk   [(vraagwoord, tekstwoord)] wat er echt staat
    ontbreekt    [vraagwoord] wat er niet staat
    manier       'woorden' | 'betekenis' | 'beide'
    vector_rang  plek in de betekenisranglijst, of None
    html         het knipsel met markeringen
    """
    tekstwoorden = _woord.findall(treffer.tekst.lower())
    letterlijk: list[tuple[str, str]] = []
    ontbreekt: list[str] = []
    for w in vraagwoorden(vraag):
        tw = _letterlijk(w, tekstwoorden)
        if tw:
            letterlijk.append((w, tw))
        else:
            ontbreekt.append(w)

    if treffer.woord_rang and treffer.vector_rang:
        manier = "beide"
    elif treffer.woord_rang:
        manier = "woorden"
    else:
        manier = "betekenis"

    return {
        "letterlijk": letterlijk,
        "ontbreekt": ontbreekt,
        "manier": manier,
        "vector_rang": treffer.vector_rang,
        "html": _markeer(treffer.tekst, {tw for _, tw in letterlijk}),
    }
