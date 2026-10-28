"""De harde controles van De Deontologiewacht op contracten (opdrachtkaart v0.3, stap 4 van de bouw).

Toetst de tekst van een contract aan de zes harde regels van het register: B1 tot B5 en D1. Elke controle zoekt naar
vaste formuleringen in de tekst en geeft een `Bevinding` met de plaats (het artikel van het contract) en een voorstel.
De kleur komt pas in `verslag.maak`, met de kleurregels van stap 3. Zo kan een controle hier nooit zelf rood of groen
maken: ze zegt alleen slaagt, faalt of onbekend.

Bewust streng en eenvoudig: wat de controle niet terugvindt, faalt. Een valse rode vlag kost Mehdi een blik; een
gemiste rode vlag staat in een contract van een klant. Twijfelt een controle (een uitsluiting die ze niet kan lezen), dan
zegt ze onbekend en wordt het oranje.

De masters zijn Jinja-sjablonen; de toets loopt op een gerenderde versie (de testdossiers van het contractsysteem), zodat
elke keuze in het sjabloon (budgetscenario, opdrachtomvang) apart getoetst wordt.

Gebruik:
    python3 -m deontologie.masters contract.docx [ander.txt ...]   (vanuit mijnagents-runner)
"""
import re
import sys
from pathlib import Path

from . import budget as G
from . import verslag as V

B = V.Bevinding
# Een artikelkop: "4." of "4.2" of "4.2.1." gevolgd door een woord. Een regel die met een bedrag, oppervlakte, postcode of
# telefoonnummer begint (een afgebroken pdf-regel), is geen kop (tegenlezing na de proef, 28-10-2026).
KOP = re.compile(r"^(\d{1,2}(?:\.\d{1,2})*\.|\d{1,2}(?:\.\d{1,2})+)\s+(?!(m²|m2|euro|eur)\b)[^\W\d]")
LOTEN = ("wind- en waterdicht", "technieken", "afwerking")

TAKEN = (  # de zeven taken van artikel 20 RBP2022, met de woorden waaraan ze in een contract te herkennen zijn
    ("de gegevens", r"verzamelen van (de )?gegevens|gegevens die nodig zijn"),
    ("het programma", r"behoeften van de (opdrachtgever|bouwheer)|programma|wenst volgende ruimtes"),
    ("schets en voorontwerp", r"schets|voorontwerp"),
    ("het administratief dossier", r"administratief dossier|aanvraag (van de |tot )?(omgevings|stedenbouwkundige )?vergunning|vergunningsaanvraag"),
    ("het dossier voor de bestelling", r"aanbesteding|meetsta|keuze van (de )?aannemer"),
    ("het uitvoeringsdossier met de controle der werken", r"uitvoerings(dossier|ontwerp|plannen)|controle op de uitvoering"),
    ("de bijstand bij de oplevering en het nazicht der rekeningen", r"bijstand bij de oplevering|nazicht van de vorderingsstaten"),
)
UITSLUITING = (r"niet belast|niet inbegrepen|valt buiten|vallen buiten|omvat niet|omvat geen|geen deel uit|uitgesloten|"
               r"te beperken tot|beperkt tot(?! de overeenstemming)|uitsluitend betrekking")
BEPERKT = (r"(opdracht|overeenkomst)[^.\n]{0,80}(te beperken (zijn )?tot|beperkt (is )?tot(?! de overeenstemming)|uitsluitend betrekking)|"
           r"omvat geen werfopvolging")
UITVOERING = r"uitvoerings(?:dossier|ontwerp|plannen)"  # artikel 21 zegt "uitvoeringsontwerp", de masters "uitvoeringsdossier"
NEEN = r"\b(niet|geen)\b|uitgesloten|valt buiten|vallen buiten"
# De taken van de architect staan in het artikel met deze kop; artikel 4.1 citeert daar de wet en telt niet mee.
TAKEN_KOP = r"taken van de architect|opdracht (en verplichtingen )?van de architect|^\d+\.?\s+opdracht\b"
WETSTEKST_KOP = r"wet op de bescherming|wettelijke opdracht"
# Een uitsluiting telt alleen in een zin over de opdracht of de taken, niet bij kosten, ereloon of aansprakelijkheid.
OVER_TAKEN = r"\btaak\b|\btaken\b|\bopdracht\b|\bbelast\b|\barchitect\b"  # niet "Opdrachtgever" (proef 28-10-2026)
NIET_OVER_TAKEN = r"kost|ereloon|bedrag|polis|aansprakelijk|gegevens"


def beperkte_opdracht(tekst):
    """Een voorstudie of regularisatie: de opdracht is uitdrukkelijk beperkt en er is geen uitvoeringsdossier. Of de
    regels over aannemer, begroting en programmawijziging daar gelden, is een keuze van Mehdi (opdrachtkaart,
    ontwerplezing punt 6: welke regel bij welke master hoort). Tot dan wordt zo een fout oranje, niet rood."""
    return bool(re.search(BEPERKT, tekst, re.I)) and not any(
        re.search(UITVOERING, z, re.I) and not re.search(NEEN, z, re.I) for z in _zinnen(tekst))


def _beperkt(b, tekst):
    if b.uitkomst == V.FAALT and beperkte_opdracht(tekst):
        return B(b.code, V.ONBEKEND, b.plaats, b.voorstel,
                 f"{b.toelichting}; beperkte opdracht, Mehdi beslist of deze regel hier geldt")
    return b


def _hoofdnummer(kop):
    m = re.match(r"\d+", kop)
    return int(m.group()) if m else 0


def secties(tekst):
    """De tekst per artikel: [(kop, [alinea's])]. Wat voor de eerste kop staat, heet 'aanhef'. Een genummerde lijst in
    een artikel ("1. ..." in artikel 5) is geen nieuwe kop: het nummer ligt lager dan dat van het lopende artikel."""
    uit, kop, alineas = [], "aanhef", []
    for regel in (r.strip() for r in tekst.replace("\r", "").split("\n")):
        if not regel:
            continue
        lijst = re.match(r"\d+\.\s", regel) and _hoofdnummer(regel) < _hoofdnummer(kop)
        if KOP.match(regel) and len(regel) < 120 and not lijst:
            uit.append((kop, alineas))
            kop, alineas = regel, []
        else:
            alineas.append(regel)
    uit.append((kop, alineas))
    return uit


def _zinnen(tekst):
    return [z.strip() for z in re.split(r"(?<=[.;!?])\s+|\n", tekst) if z.strip()]


def _doorlopend(tekst):
    """De zinnen van de tekst met de regels samengevoegd: een pdf breekt een zin over twee regels af."""
    return [z.strip() for z in re.split(r"(?<=[.;!?])\s+", re.sub(r"\s*\n\s*", " ", tekst)) if z.strip()]


def _taken_secties(secs):
    """Alleen het artikel over de taken van de architect, zonder de wetstekst; bestaat het niet, dan alles."""
    hoofd = next((_hoofdnummer(k) for k, _ in secs if re.search(TAKEN_KOP, k, re.I)), None)
    if not hoofd:
        return secs
    return [(k, a) for k, a in secs if _hoofdnummer(k) == hoofd and not re.search(WETSTEKST_KOP, k, re.I)]


def _klein(t):
    return re.sub(r"\s+", " ", t).casefold()


def _zoek(secs, patroon):
    """De eerste sectie (kop) waarin het patroon staat, in de kop of in een alinea; anders None."""
    p = re.compile(patroon, re.I)
    for kop, alineas in secs:
        if p.search(kop) or any(p.search(a) for a in alineas):
            return kop
    return None


def b1_schriftelijk(secs, tekst):
    partijen = re.search(r"\btussen\b", tekst, re.I) and re.search(r"de (opdrachtgever|bouwheer)", tekst, re.I) \
        and re.search(r"de architect", tekst, re.I)
    slot = re.search(r"(opgesteld|opgemaakt|gedaan) te [^,]{1,60},? op (\S+ \S+ \d{4}|\d{1,2}[./-]\d{1,2}[./-]\d{2,4})"
                     r"[^.]{0,160}?(onderteken|exempla)", re.sub(r"\s+", " ", tekst), re.I)
    if partijen and slot:
        return B("B1", V.SLAAGT, "slotbepaling")
    return B("B1", V.FAALT, "slotbepaling" if partijen else "aanhef",
             "Opgesteld te [plaats], op [datum], in twee exemplaren, ondertekend door de Opdrachtgever en de Architect "
             "voor de opdracht begint.",
             "geen partijen" if not partijen else "geen datum en ondertekening in het slot")


def b2_taken(secs, tekst):
    ontbreekt = []
    taken = _taken_secties(secs)
    for naam, patroon in TAKEN:
        if _zoek(taken, patroon):
            continue
        ontbreekt.append(naam)
    if not ontbreekt and _keuze_uitgesloten(tekst):
        return B("B2", V.ONBEKEND, "artikel over de taken van de architect", "",
                 "de taken staan er, maar een andere zin sluit de aanbesteding of de keuze van de aannemer uit")
    if not ontbreekt:
        return B("B2", V.SLAAGT, "artikel over de taken van de architect")
    if any(re.search(UITSLUITING, z, re.I) and re.search(OVER_TAKEN, z, re.I) and not re.search(NIET_OVER_TAKEN, z, re.I)
           for z in _zinnen(tekst)):
        # Er staat een uitsluiting, maar de controle kan niet lezen of die precies deze taken noemt.
        return B("B2", V.ONBEKEND, "artikel over de taken van de architect",
                 _b2_voorstel(ontbreekt), f"niet teruggevonden: {', '.join(ontbreekt)}; er staat wel een uitsluiting")
    return B("B2", V.FAALT, "artikel over de taken van de architect", _b2_voorstel(ontbreekt),
             f"niet teruggevonden: {', '.join(ontbreekt)}")


def _b2_voorstel(ontbreekt):
    return ("Zeg per taak van artikel 20 of de Architect ermee belast is, ook wat niet: \"De Architect is niet belast "
            f"met {ontbreekt[0]}.\" Ontbreekt nu: {', '.join(ontbreekt)}.")


def _keuze_uitgesloten(tekst):
    """Een zin die de keuze van de aannemer of de aanbesteding uit de opdracht haalt, ook als de standaardtaak er nog
    staat (een deelopdracht, tegenlezing na de proef 28-10-2026)."""
    return any(re.search(r"keuze van (de )?aannemer|aanbesteding", z, re.I)
               and re.search(r"geen deel uit|maken geen deel|valt buiten|vallen buiten|niet inbegrepen|uitgesloten", z, re.I)
               for z in _doorlopend(tekst))


def b3_controle(secs, tekst):
    # Per zin, zodat "de Architect is niet belast met de controle op de uitvoering" geen controle is (laatste toets).
    zinnen = [_klein(z) for z in _zinnen(tekst)]
    uitvoering = [z for z in zinnen if re.search(UITVOERING, z) and not re.search(NEEN, z)]
    if not uitvoering:
        return B("B3", V.SLAAGT, "", "", "geen uitvoeringsdossier in de opdracht")
    controle = [z for z in zinnen if "controle op de uitvoering" in z and not re.search(NEEN, z)]
    zonder = [lot for lot in LOTEN
              if any(re.search(rf"{UITVOERING} voor de {re.escape(lot)}", z) for z in uitvoering)
              and not any(f"controle op de uitvoering van de {lot}" in z for z in controle)]
    if not controle:
        zonder = zonder or ["de werken"]
    if not zonder:
        return B("B3", V.SLAAGT, _zoek(secs, r"controle op de uitvoering") or "")
    if re.search(r"andere (ingeschreven )?architect.{0,80}controle", _klein(tekst)):
        return B("B3", V.ONBEKEND, _zoek(secs, UITVOERING) or "", "",
                 "een andere architect wordt genoemd, nagaan of hij de controle krijgt")
    return B("B3", V.FAALT, _zoek(secs, UITVOERING) or "",
             f"Voeg toe: \"Controle op de uitvoering van de {zonder[0]}\", of noem de andere ingeschreven architect "
             "die de controle doet.", f"uitvoeringsdossier zonder controle: {', '.join(zonder)}")


def b4_aannemer(secs, tekst):
    patroon = r"bijstand bij de keuze van (de )?aannemer"
    kop = _zoek(secs, patroon)
    voorstel = "Neem op bij de taken: \"Bijstand bij de keuze van de aannemer(s) en de aanbesteding.\""
    if not kop:
        return B("B4", V.FAALT, "artikel over de taken van de architect", voorstel, "bijstand bij de keuze niet gevonden")
    alineas = dict(secs)[kop] if kop in dict(secs) else []
    zin = next((a for a in alineas if re.search(patroon, a, re.I)), None)
    if zin is None:  # de bijstand is de kop zelf: een uitsluiting kan in de alinea eronder staan
        zin = " ".join([kop] + alineas)
    if re.search(r"\bniet\b|uitgesloten|behalve|\bgeen\b|valt buiten|vallen buiten", zin, re.I):
        return B("B4", V.FAALT, kop, voorstel, "de bijstand staat er met een uitsluiting")
    if _keuze_uitgesloten(tekst):
        return B("B4", V.ONBEKEND, kop, voorstel, "de bijstand staat bij de taken, maar een andere zin sluit ze uit")
    return B("B4", V.SLAAGT, kop)


def b5_budget(secs, tekst):
    plaats = _zoek(secs, r"bouwbudget|begroting") or "artikel over het budget"
    if re.search(r"geen budgetverantwoordelijkheid|geen (bouw)?budget\b|zonder (bouw)?budget\b", tekst, re.I):
        return B("B5", V.FAALT, plaats, "Schrap de uitsluiting van de budgetverantwoordelijkheid en vermeld: \"Het "
                 "Bouwbudget wordt op [bedrag] euro vooropgesteld.\"", "de budgetverantwoordelijkheid wordt uitgesloten")
    programma = _programma(secs)
    bedrag = None
    for kop, alineas in secs:
        if re.search(r"budget|begroting", kop, re.I):
            bedrag = bedrag or next((a for a in alineas if re.search(r"\d[\d.]*(,\d{2})?\s?(euro|eur\b|€)|€\s?\d", a, re.I)), None)
    if programma and bedrag and not re.search(r"(€|euro)\s*/\s*m|per (m²|m2|vierkante)", bedrag, re.I):
        return B("B5", V.SLAAGT, plaats)
    if programma and bedrag:
        return B("B5", V.ONBEKEND, plaats, "Vermeld naast de prijs per m² het totale Bouwbudget in euro.",
                 "alleen een prijs per m², geen totaal in euro")
    return B("B5", V.FAALT, plaats,
             "Vermeld bij ondertekening het programma en een begroting in euro: \"Het Bouwbudget wordt op [bedrag] euro "
             "vooropgesteld.\" Een raming die later volgt, komt in een Bijvoegsel.",
             "geen programma" if not programma else "geen begroting in euro bij het budget")


def _programma(secs):
    """Het artikel dat het programma beschrijft. De standaardzin "Het programma van het Bouwproject, zoals hierna
    beschreven" telt niet: er moet een eigen beschrijving van minstens 40 tekens staan (tegenlezing na de proef)."""
    for kop, alineas in secs:
        eigen = [a for a in alineas if not re.search(r"zoals hierna beschreven", a, re.I)]
        if re.search(r"\d\.?\s+het (bouw)?project\s*$", kop, re.I) and len(" ".join(eigen)) >= 40:
            return kop
    return _zoek(secs, r"wenst volgende ruimtes|ruimtes, functies|programma van het bouwproject\s*:\s*\S")


def d1_wijziging(secs, tekst):
    plaatsen, goed = [], None
    for kop, alineas in secs:
        blok = " ".join([kop] + alineas)
        if re.search(r"wijziging", blok, re.I) and re.search(r"bouwproject|programma", blok, re.I):
            plaatsen.append(kop)
            if re.search(r"bijvoegsel|addendum", blok, re.I) and re.search(r"financi|weerslag op het (bouw)?budget", blok, re.I):
                goed = kop
    if goed:
        return B("D1", V.SLAAGT, goed)
    return B("D1", V.FAALT, plaatsen[0] if plaatsen else "artikel over wijzigingen",
             "\"Elke wijziging van het programma wordt vastgelegd in een Bijvoegsel, ondertekend door beide Partijen, dat "
             "de financiele weerslag op het Bouwbudget en op het ereloon vermeldt.\"",
             "een wijziging van het programma vraagt geen addendum met de financiele weerslag")


CONTROLES = (b1_schriftelijk, b2_taken, b3_controle, b4_aannemer, b5_budget, d1_wijziging)


def gewone_spaties(tekst):
    """Tabs en harde spaties tussen woorden worden een spatie (een pdf geeft "Bijstand\tbij\tde keuze"); regeleinden
    blijven, want de artikels worden per regel herkend (proef op echte contracten, 28-10-2026)."""
    return re.sub(r"[^\S\n]+", " ", tekst.replace("\r", ""))


def toets_contract(tekst):
    """De bevindingen voor de harde regels; de andere regels blijven 'niet getoetst' (oranje) in het verslag."""
    tekst = gewone_spaties(tekst)
    secs = secties(tekst)
    uit = [c(secs, tekst) for c in CONTROLES]
    uit = [_beperkt(b, tekst) if b.code in ("B4", "B5", "D1") else b for b in uit]
    # Stap 7: budget tegen oppervlakte (D2, alleen cijfers zolang er geen referentie is) en de verzekering (D4).
    return uit + [G.d2_begroting(*G.uit_contract(tekst)), G.d4_verzekering(tekst, tienjarig_nodig=not beperkte_opdracht(tekst))]


def lees(pad):
    pad = Path(pad)
    if pad.suffix.lower() == ".docx":
        from docx import Document
        d = Document(str(pad))
        delen = [p.text for p in d.paragraphs]
        for tabel in d.tables:
            for rij in tabel.rows:
                delen.append(" | ".join(c.text for c in rij.cells))
        return "\n".join(delen)
    return pad.read_text(encoding="utf-8")


if __name__ == "__main__":
    for pad in sys.argv[1:]:
        print(f"## {Path(pad).name}\n")
        print(V.maak("contract", toets_contract(lees(pad))).markdown())
        print()
