"""Budget en verzekering in de toets van De Deontologiewacht (opdrachtkaart v0.3, stap 7 van de bouw).

Verwijt D uit de tuchtzaak: budgetten die niet haalbaar zijn, een budget dat meer dan verdubbelt zonder aanpassing,
een verzekering die niet bijgewerkt wordt. De regels zijn allemaal oordeel of afgeleid, dus hoogstens oranje; de Wacht
toont de cijfers en Mehdi beslist.

- D2: het budget gedeeld door de oppervlakte, naast een referentieprijs per m². Zonder referentie toont de Wacht alleen
  de prijs per m² (onbekend, oranje). De referentie en de marge legt Mehdi vast (ontwerplezing, punt 6).
- D4: het contract noemt de verzekeraar en de polis voor de beroepsaansprakelijkheid, met de tienjarige.
- D3 en D5 bij een kost boven het budget: boven DREMPEL_PROCENT (15, zoals artikel 3.4 van de master) moet er een
  schriftelijke melding aan de opdrachtgever zijn, en de vraag of de verzekering op de nieuwe waarde staat.
"""
import re

from . import verslag as V

B = V.Bevinding
DREMPEL_PROCENT = 15


def _e(n):
    return f"{n:,.0f}".replace(",", ".")


def bedrag(tekst):
    """Een bedrag in euro uit Belgische schrijfwijze: 250.000,00 of 250000 of 2.350 €."""
    m = re.search(r"(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{1,2}))?", tekst)
    if not m:
        return None
    return float(m.group(1).replace(".", "") + "." + (m.group(2) or "0"))


def uit_contract(tekst):
    """(budget in euro, oppervlakte in m²) uit de tekst van een contract, of None waar het ontbreekt."""
    budget = opp = None
    m = re.search(r"bouwbudget[^.]{0,120}?op\s+(\d[\d.,]*)\s*(euro|eur\b|€)", tekst, re.I)
    if m:
        budget = bedrag(m.group(1))
    m = re.search(r"ca\.?\s*(\d[\d.,]*)\s*m(²|2)\s*oppervlakte", tekst, re.I)
    if m:
        opp = bedrag(m.group(1))
    return budget, opp


def d2_begroting(budget, oppervlakte, referentie=None, marge_procent=25):
    """`referentie`: prijs per m² die Mehdi als maatstaf vastlegt. Valt de begroting meer dan `marge_procent` eronder,
    dan faalt de regel (oranje)."""
    if not budget or not oppervlakte:
        return B("D2", V.ONBEKEND, "artikel over het budget", "Vermeld budget en oppervlakte, zodat de prijs per m² te "
                 "toetsen is.", "budget of oppervlakte ontbreekt")
    per_m2 = budget / oppervlakte
    cijfers = f"{_e(budget)} euro voor {_e(oppervlakte)} m², dus {_e(per_m2)} euro per m²"
    if not referentie:
        return B("D2", V.ONBEKEND, "artikel over het budget", "", f"{cijfers}; nog geen referentieprijs vastgelegd")
    if per_m2 < referentie * (1 - marge_procent / 100):
        return B("D2", V.FAALT, "artikel over het budget",
                 "Bespreek de begroting met de opdrachtgever en pas ze aan, of leg schriftelijk vast waarom ze lager ligt.",
                 f"{cijfers}; referentie {_e(referentie)} euro per m²")
    return B("D2", V.SLAAGT, "artikel over het budget", "", cijfers)


def d4_verzekering(tekst, tienjarig_nodig=True):
    """Verzekeraar, polisnummer en, bij een opdracht met uitvoering, de tienjarige aansprakelijkheid. Een voorstudie of
    regularisatie bouwt niets, dus daar is de tienjarige niet nodig (proef op echte contracten, 28-10-2026)."""
    plaats = "artikel over de verzekeringen"
    verzekeraar = re.search(r"verzekeraar|verzekerd bij|verzekeringsmaatschappij|\bpolis", tekst, re.I)
    tienjarig = re.search(r"tienjarig", tekst, re.I) or not tienjarig_nodig
    if verzekeraar and tienjarig and re.search(r"(polis|polisnummer)\s*(nr\.?|nummer)?\s*[:\-]?\s*[A-Z]{0,4}[\-./]?\d", tekst, re.I):
        return B("D4", V.SLAAGT, plaats)
    return B("D4", V.FAALT, plaats, "Vermeld: \"De Architect is voor zijn beroepsaansprakelijkheid, met inbegrip van de "
             "tienjarige aansprakelijkheid, verzekerd bij [verzekeraar], polis [nummer].\"",
             "verzekeraar, polisnummer of tienjarige aansprakelijkheid niet gevonden")


def overschrijding(budget, kost, gemeld, verzekering_bijgewerkt=None, drempel=DREMPEL_PROCENT):
    """D3 en D5 voor een dossier: `kost` is de werkelijke of geraamde kost, `gemeld` of de opdrachtgever schriftelijk
    verwittigd is, `verzekering_bijgewerkt` True, False of None (onbekend)."""
    if not budget or kost is None:
        return [B("D3", V.ONBEKEND, "", "", "budget of kost ontbreekt"), B("D5", V.ONBEKEND, "", "", "budget of kost ontbreekt")]
    procent = (kost - budget) / budget * 100
    cijfers = f"kost {_e(kost)} euro tegen budget {_e(budget)} euro ({procent:+.0f} procent)"
    if procent <= drempel:
        return [B("D3", V.SLAAGT, "", "", cijfers), B("D5", V.SLAAGT, "", "", cijfers)]
    d3 = B("D3", V.SLAAGT, "", "", cijfers) if gemeld else B(
        "D3", V.FAALT, "", "Meld de overschrijding schriftelijk aan de opdrachtgever, met het bedrag en de oorzaak.",
        f"{cijfers}, zonder melding")
    if verzekering_bijgewerkt is True:
        d5 = B("D5", V.SLAAGT, "", "", cijfers)
    elif verzekering_bijgewerkt is False:
        d5 = B("D5", V.FAALT, "", "Laat de verzekering aanpassen aan de nieuwe bouwwaarde.", f"{cijfers}, verzekering niet bijgewerkt")
    else:
        d5 = B("D5", V.ONBEKEND, "", "Ga na of de verzekering op de nieuwe bouwwaarde staat.", cijfers)
    return [d3, d5]
