"""De toets van werfverslagen door De Deontologiewacht (opdrachtkaart v0.3, stap 6 van de bouw).

Een werfverslag gaat vooraf langs de Wacht (keuze 1 van Mehdi, 27-10-2026). Deze module maakt de bevindingen voor de
regels van het register die voor een werfverslag gelden; `verslag.maak("werfverslag", ...)` geeft de kleuren en
`stempel.maak` de stempel waarmee het verslag kan vertrekken.

- D1 (hard): een programmawijziging of meerwerk in het verslag zonder verwijzing naar een addendum of bijvoegsel met
  de financiele weerslag faalt, en wordt dus rood. Een gewone "wijziging" zonder die woorden is onbekend (oranje).
- C1 en F1: wie het bezoek deed en wie het verslag schreef, en of instructies aan aannemers van een architect komen.
  Wie architect is, staat op organisatie.globaal.be; de aanroeper geeft die lijst mee (`architecten`). Zonder lijst
  is het onbekend, nooit goed.
- C3: het eerste verslag van een werf zegt of het werfbord met de naam van de architect er staat.
- D3 en D5: een overschrijding van de begroting vraagt een melding aan de opdrachtgever, en de vraag of de verzekering
  op de nieuwe waarde staat.
- G4: een uitspraak over het werk van een andere architect of een ander bureau.
- C4 (een verslag bij elke kritieke fase) hoort bij het dossier, niet bij een verslag, en de lijst kritieke fasen moet
  Mehdi nog vastleggen (ontwerplezing, punt 6). Die regel staat in ELDERS en telt niet mee in de kleur van een verslag.

Alle andere regels dan D1 zijn oordeel of afgeleid: hoogstens oranje, ook als ze falen.
"""
import re
from dataclasses import dataclass

from . import verslag as V

B = V.Bevinding
ELDERS = ("C4",)  # dossierregel: geef dit mee als `verslag.maak(..., elders=ELDERS)`

WIJZIGING_ZEKER = r"programmawijziging|wijziging van het programma|meerwerk|bijkomende werken|extra werken|wijziging aan het bouwproject"
WIJZIGING_MISSCHIEN = (r"\bwijzig|\bgewijzigd|\baanpass|\bbijkomend|\buitbrei|\bom te bouwen|\bombouw|"
                       r"\bextra (ruimte|kamer|badkamer|slaapkamer|verdieping|bijgebouw|carport|garage|dakkapel|raam|ramen|werk|kost)|"
                       r"\bverhoo?g\w*|volledig nieuwe")
GEEN_MEERWERK = (r"\b(geen|niet)\b[^.\n]{0,20}(programmawijziging|meerwerk|bijkomende werken|extra werken)|"
                 r"(programmawijziging|meerwerk|bijkomende werken|extra werken)\w*\s*:\s*(geen|nihil|n\.?v\.?t)")
ONTKENNING = r"\b(geen|niet|nog niet)\b"
ADDENDUM = r"addendum|bijvoegsel"
FINANCIEEL = r"financi|meerprijs|meerkost|kostprijs|budget|euro|€"
OVERSCHRIJDING = (r"overschrijd|boven (de |het )?(begroting|budget|raming)|duurder dan (de |het )?(begroting|budget|raming)|"
                  r"meerkost|\bstijg\w* met|ten opzichte van (de |het )?(raming|begroting|budget)")
MELDING = r"(opdrachtgever|bouwheer) (is|werd|wordt) (schriftelijk )?(verwittigd|ingelicht|op de hoogte)|melding aan de (opdrachtgever|bouwheer)"
INSTRUCTIE = r"\baannemer\b[^.]{0,80}\b(moet|dient|zal|gelieve)\b|\bgelieve\b|\bte herstellen\b|\bop te volgen\b"
# Een werfverslag spreekt een aannemer vaak aan met zijn afkorting: "KV dient ...", "ODB zal ..." (proef 28-10-2026).
INSTRUCTIE_AFKORTING = re.compile(r"\b[A-Z]{2,4}\b\s+(dient|moet|zal)\b")
CONFRATER = r"(andere|vorige|vroegere) (architect|ontwerper|bureau)|confrater|architect van (de )?buren"


@dataclass(frozen=True)
class Werfverslag:
    tekst: str
    opgesteld_door: str = ""
    bezocht_door: tuple = ()
    eerste: bool = None  # None: niet bekend of dit het eerste verslag is, dan is C3 onbekend en nooit stil groen


def _zinnen(tekst):
    return [z.strip() for z in re.split(r"(?<=[.!?])\s+|\n", tekst) if z.strip()]


def _zin(tekst, patroon):
    """De zin waarin het patroon staat, als plaats in het verslag (ingekort)."""
    for zin in _zinnen(tekst):
        if re.search(patroon, zin, re.I):
            return zin[:120]
    return ""


def d1_wijziging(v):
    t = re.sub(GEEN_MEERWERK, " ", v.tekst, flags=re.I)  # "Meerwerken: geen." of "geen meerwerk" is geen meerwerk
    zeker = re.search(WIJZIGING_ZEKER, t, re.I)
    if not zeker and not re.search(WIJZIGING_MISSCHIEN, t, re.I):
        return B("D1", V.SLAAGT, "", "", "geen wijziging van het programma in dit verslag")
    patroon = WIJZIGING_ZEKER if zeker else WIJZIGING_MISSCHIEN
    plaats = _zin(t, patroon)
    # Een addendum telt alleen in een zin die het niet ontkent: "er wordt geen addendum opgemaakt" is er geen.
    addendum = [z for z in _zinnen(t) if re.search(ADDENDUM, z, re.I) and not re.search(ONTKENNING, z, re.I)]
    if addendum and re.search(FINANCIEEL, " ".join(addendum) + " " + plaats, re.I):
        return B("D1", V.SLAAGT, plaats)
    voorstel = ("Voeg toe: \"Deze wijziging wordt vastgelegd in een addendum bij de architectuurovereenkomst, met de "
                "financiele weerslag op het budget en het ereloon, ondertekend voor de uitvoering.\"")
    if zeker:
        return B("D1", V.FAALT, plaats, voorstel, "wijziging of meerwerk zonder addendum met de financiele weerslag")
    return B("D1", V.ONBEKEND, plaats, voorstel, "er staat een wijziging; nagaan of het programma verandert")


def _is_architect(naam, architecten):
    return naam.strip().casefold() in {a.strip().casefold() for a in architecten}


def c1_architect(v, architecten):
    mensen = [m for m in (*v.bezocht_door, v.opgesteld_door) if m]
    if architecten is None or not mensen:
        return B("C1", V.ONBEKEND, "", "", "niet na te gaan wie het bezoek deed en het verslag schreef")
    niet = [m for m in mensen if not _is_architect(m, architecten)]
    if niet:
        return B("C1", V.FAALT, "aanhef van het verslag",
                 "Laat het bezoek door een architect doen, of het verslag door een architect nalezen en ondertekenen.",
                 f"geen architect volgens organisatie.globaal.be: {len(niet)} persoon of personen")
    return B("C1", V.SLAAGT, "aanhef van het verslag")


def c3_werfbord(v):
    if v.eerste is None:
        return B("C3", V.ONBEKEND, "", "", "niet bekend of dit het eerste verslag van de werf is")
    if not v.eerste:
        return B("C3", V.SLAAGT, "", "", "niet het eerste verslag van de werf")
    if re.search(r"werfbord", v.tekst, re.I):
        return B("C3", V.SLAAGT, _zin(v.tekst, r"werfbord"))
    return B("C3", V.FAALT, "eerste verslag", "Vermeld: \"Het werfbord met de naam van de architect staat aan de "
             "straatzijde.\" of dat het ontbreekt.", "het eerste verslag zegt niets over het werfbord")


def d3_d5_overschrijding(v):
    if not re.search(OVERSCHRIJDING, v.tekst, re.I):
        return [B("D3", V.SLAAGT, "", "", "geen overschrijding genoemd"),
                B("D5", V.SLAAGT, "", "", "geen overschrijding genoemd")]
    plaats = _zin(v.tekst, OVERSCHRIJDING)
    d3 = (B("D3", V.SLAAGT, plaats) if re.search(MELDING, v.tekst, re.I) else
          B("D3", V.FAALT, plaats, "Meld de overschrijding schriftelijk aan de opdrachtgever, met het bedrag.",
            "overschrijding zonder melding aan de opdrachtgever"))
    d5 = B("D5", V.ONBEKEND, plaats, "Ga na of de verzekering op de nieuwe bouwwaarde staat.",
           "de kost gaat boven de begroting")
    return [d3, d5]


def f1_instructies(v, architecten):
    if not re.search(INSTRUCTIE, v.tekst, re.I) and not INSTRUCTIE_AFKORTING.search(v.tekst):
        return B("F1", V.SLAAGT, "", "", "geen instructies aan aannemers")
    plaats = _zin(v.tekst, INSTRUCTIE) or _zin(v.tekst, INSTRUCTIE_AFKORTING.pattern)
    if architecten is None or not v.opgesteld_door:
        return B("F1", V.ONBEKEND, plaats, "", "niet na te gaan of de schrijver architect is")
    if _is_architect(v.opgesteld_door, architecten):
        return B("F1", V.SLAAGT, plaats)
    return B("F1", V.FAALT, plaats, "Laat de instructies aan de aannemer door een architect geven of ondertekenen.",
             "instructies aan een aannemer van iemand die geen architect is")


def g4_confrater(v):
    if not re.search(CONFRATER, v.tekst, re.I):
        return B("G4", V.SLAAGT, "", "", "geen uitspraak over een confrater")
    return B("G4", V.FAALT, _zin(v.tekst, CONFRATER),
             "Beschrijf alleen de vaststelling, zonder oordeel over het werk van de andere architect.",
             "uitspraak over het werk van een andere architect of bureau")


def toets_werfverslag(v, architecten=None):
    """De bevindingen voor een werfverslag. `architecten`: namen van wie als architect of stagiair ingeschreven is."""
    v = Werfverslag(re.sub(r"[^\S\n]+", " ", v.tekst), v.opgesteld_door, v.bezocht_door, v.eerste)
    return [d1_wijziging(v), c1_architect(v, architecten), c3_werfbord(v), *d3_d5_overschrijding(v),
            f1_instructies(v, architecten), g4_confrater(v)]
