"""De harde regel van Mehdi (17-10-2026, herhaald 30-10-2026): H-Architects en Harmonie Bouw zijn voor de buitenwereld
volledig gescheiden. Geen enkel stuk van de afdeling Bouw mag zeggen of laten doorschemeren dat ze iets met elkaar te
maken hebben. Een stuk dat deze grendel niet haalt, vertrekt nooit: de agent zet het niet klaar en meldt een nood.

Voor elk stuk (een prijsaanvraag of een vergelijking van offertes) geldt: de naam, het domein, het adres en de nummers
van de andere firma komen er nooit in, en de persoon achter de firma's ook niet (een stuk tekent met de firma). Een
offerte van de andere firma in een vergelijking heet "Inschrijver B", zoals elke inschrijver een letter krijgt
(overleg 30-10-2026, X4). Daarbij de lijst met bandwoorden uit de grendel van dossier 2405 (verify_geen_groepsband).
"""
import re
import unicodedata

HA, HB = "HA", "HB"
FIRMANAMEN = {HA: "H-Architects", HB: "Harmonie Bouw"}

# Wat een stuk aan een firma koppelt. Hoofdletters tellen niet; streepjes en spaties worden gelijkgetrokken.
KENMERKEN = {
    HA: [r"(?-i:\bHA\b)", r"(?-i:\bHARC\b)", r"\bh[\W_]{0,3}architects?", r"harchitects", r"\bh-a\b", r"h-architects\.be", r"\+?32\s?\(?0?\)?\s?16\s?79\s?32\s?96",
         r"\+?32\s?\(?0?\)?\s?16\s?79\s?23\s?14", r"\+?32\s?\(?0?\)?\s?491\s?94\s?68\s?79"],
    HB: [r"(?-i:\bHB\b)", r"(?-i:\bHARM\b)", r"harmonie[\W_]{0,3}bouw", r"harmoniebouw\.be", r"\b(?:be\s?)?0?537[.\s]?405[.\s]?239\b", r"gerzenstraat\s?5\b",
         r"hoveniersstraat\s?19\b"],
}
# De persoon achter de firma's: een mail tekent met de firma, nooit met zijn naam (zoals de mails van standaard@).
PERSOON = [r"chegini"]
# Woorden die een band leggen (2405: VERBODEN_BAND), aangevuld voor mails. "groep" en "verbonden" alleen in de zin
# van een band: een ventilatiegroep of een leiding die verbonden wordt met het riool is gewone bouwtaal.
BANDWOORDEN = (r"(?:dezelfde|zelfde|onze|uw|een|één)\s+groep\b|\btot\s+de\s+groep\b|\bgroep\s+(?:van|waartoe)\b|"
               r"bedrijvengroep|groepsmaatschappij|groepsbedrijf|met elkaar verbonden|"
               r"verbonden\s+(?:firma|vennootschap|onderneming|bedrijf)|verwant|zuster|holding|aandeelhoud|"
               r"dezelfde eigenaar|zelfde eigenaar|eigen aannemer|belangenconflict|"
               r"onafhankelijke?\s+(?:firma|bedrijf|vennootschap|onderneming|aannemer|architect|bureau)|"
               r"(?:volledig|totaal|geheel)\s+onafhankelijk|onafhankelijk\s+van\s+(?:elkaar|ons|de\s+(?:aannemer|architect))|"
               r"band tussen|band met|gelieerd|partnerbedrijf|partnerfirma|vaste partner|onze partner|partner van|"
               r"zaakvoerder van beide|onze aannemer|ons aannemersbedrijf|ons architectenbureau|vaste aannemer|huisaannemer")
BAND = re.compile(BANDWOORDEN, re.I)


def normaal(tekst):
    """Tekst om te toetsen: Unicode-streepjes en harde spaties worden gewone, accenten blijven."""
    t = unicodedata.normalize("NFKC", str(tekst or ""))
    t = re.sub(r"[‐-―−­]", "-", t)
    return re.sub(r"[   ]", " ", t)


def andere(firma):
    if firma not in (HA, HB):
        raise ValueError(f"onbekende firma {firma!r}: alleen {HA} of {HB}")
    return HB if firma == HA else HA


def schendingen(tekst, firma, extra_kenmerken=None):
    """De redenen waarom dit stuk van `firma` niet mag vertrekken; leeg als het mag.
    extra_kenmerken: {firma: [patronen]} uit kern (ondernemingsnummer, adres), naast de vaste lijst."""
    tegen = andere(firma)
    t = normaal(tekst)
    weg = [f"bandwoord '{m.group(0)}'" for m in BAND.finditer(t)]
    for p in KENMERKEN[tegen] + list((extra_kenmerken or {}).get(tegen) or []):
        weg += [f"kenmerk van {FIRMANAMEN[tegen]} '{m.group(0)}'" for m in re.finditer(p, t, re.I)]
    for p in PERSOON:
        weg += [f"persoonsnaam '{m.group(0)}' (een stuk tekent met de firma)" for m in re.finditer(p, t, re.I)]
    return list(dict.fromkeys(weg))


def kruis(tekst, firma):
    """Dezelfde toets voor een verslag aan Mehdi (Codex X2, controle 2): kenmerken, bandwoorden en de persoon. Tekst van
    derden (de specialiteit van een kandidaat) gaat eerst door schoon_veld, zodat die het verslag niet blokkeert."""
    return schendingen(tekst, firma)


def schoon_veld(tekst, firma):
    """Een vrij veld van een kandidaat of een offerte: leeg als het de toets niet haalt, anders ongewijzigd."""
    return "" if schendingen(tekst, firma) else tekst


def noemt_een_firma(tekst):
    """Noemt deze tekst een van de twee firma's (naam, code, domein, nummer, adres)? Voor wat naar het model gaat:
    daar hoort geen van beide in (Codex X4)."""
    t = normaal(tekst)
    return any(re.search(p, t, re.I) for f in (HA, HB) for p in KENMERKEN[f])


def is_andere_firma(naam, firma):
    """Is deze inschrijver (naam zoals op de offerte of in de bestandsnaam) de andere firma?"""
    t = normaal(naam)
    return any(re.search(p, t, re.I) for p in KENMERKEN[andere(firma)])


def mag_weg(tekst, firma, extra_kenmerken=None):
    return not schendingen(tekst, firma, extra_kenmerken)
