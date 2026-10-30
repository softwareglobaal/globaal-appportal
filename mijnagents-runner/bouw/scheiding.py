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
    HA: [r"(?-i:\bHA\b)", r"(?-i:\bH\.\s?A\.)", r"\bharc\b", r"\bh[\W_a]{0,5}architects?", r"harchitects", r"\bh-a\b", r"h-architects\.be", r"\+?32\s?\(?0?\)?\s?16\s?79\s?32\s?96",
         r"\+?32\s?\(?0?\)?\s?16\s?79\s?23\s?14", r"\+?32\s?\(?0?\)?\s?491\s?94\s?68\s?79"],
    HB: [r"(?-i:\bHB\b)", r"(?-i:\bH\.\s?B\.)", r"\bharm\b", r"harmonie[\W_]{0,3}bouw", r"harmoniebouw\.be", r"\b(?:be\s?)?0?537[.\s]?405[.\s]?239\b", r"gerzenstr(?:aat|\.)?\s*,?\s*5\b", r"\b5\s*,?\s*gerzenstr",
         r"hoveniersstr(?:aat|\.)?\s*,?\s*19\b"],
}
# Telefoon- en ondernemingsnummers in elke schrijfwijze (016/79.32.96, 0491 94 68 79, BE0537405239): de code vergelijkt
# de cijfers, niet de tekens ertussen (Codex X1, controle 3). Aangevuld met kern.firma via laad_kern().
CIJFERS = {HA: ["16793296", "16792314", "491946879"], HB: ["537405239"]}
EXTRA = {HA: {"patronen": [], "cijfers": []}, HB: {"patronen": [], "cijfers": []}}
KERN_CODES = {"HARC": HA, "HARM": HB}
NUMMERREEKS = re.compile(r"[+\d][\d\s./()\-]{5,}\d")

# De persoon achter de firma's: een mail tekent met de firma, nooit met zijn naam (zoals de mails van standaard@).
PERSOON = [r"chegini"]
# Woorden die een band leggen (2405: VERBODEN_BAND), aangevuld voor mails. "groep" en "verbonden" alleen in de zin
# van een band: een ventilatiegroep of een leiding die verbonden wordt met het riool is gewone bouwtaal.
BANDWOORDEN = (r"(?:dezelfde|zelfde)\s+groep\b|\btot\s+(?:de|onze|dezelfde)\s+groep\b|\bgroep\s+van\s+(?:bedrijven|firma)|"
               r"\bgroep\s+waartoe\b|"
               r"bedrijvengroep|groepsmaatschappij|groepsbedrijf|met elkaar verbonden|"
               r"verbonden\s+(?:firma|vennootschap|onderneming|bedrijf)|verwante?\s+(?:firma|bedrijf|vennootschap|onderneming)|"
               r"verwantschap|zuster|holding|aandeelhoud|"
               r"dezelfde eigenaar|zelfde eigenaar|onze eigen aannemer|ons eigen aannemersbedrijf|belangenconflict|"
               r"onafhankelijke?\s+(?:firma|bedrijf|vennootschap|onderneming|aannemer|architect|bureau)|"
               r"(?:volledig|totaal|geheel)\s+onafhankelijk|onafhankelijk\s+van\s+(?:elkaar|ons|de\s+(?:aannemer|architect))|"
               r"band tussen|band met|gelieerd|partnerbedrijf|partnerfirma|onze vaste partner|onze partner|"
               r"zaakvoerder van beide|onze aannemer|ons aannemersbedrijf|ons architectenbureau|onze vaste aannemer|huisaannemer")
BAND = re.compile(BANDWOORDEN, re.I)


def normaal(tekst):
    """Tekst om te toetsen: Unicode-streepjes en harde spaties worden gewone, accenten blijven."""
    t = unicodedata.normalize("NFKC", str(tekst or ""))
    t = re.sub(r"[‐-―−­]", "-", t)
    return re.sub(r"[   ]", " ", t)


def adrespatronen(straat, nr):
    """Een adres in de gangbare schrijfwijzen: Voorbeeldstraat 5, Voorbeeldstr. 5, 5 Voorbeeldstraat (Codex X5, controle 6)."""
    straat, nr = straat.strip(), re.escape(nr.strip())
    stam = re.escape(straat)
    for lang, kort in (("straat", r"str(?:aat|\.)?"), ("laan", r"l(?:aan|n\.?)"), ("steenweg", r"st(?:eenweg|wg\.?)")):
        if straat.lower().endswith(lang):
            stam = re.escape(straat[:-len(lang)]) + kort
            break
    return [stam + r"\s*,?\s*" + nr + r"\b", r"\b" + nr + r"\s*,?\s*" + stam]


def laad_kern(psql=None):
    """Het ondernemingsnummer en het adres van beide firma's uit kern.firma en kern.adres, naast de vaste lijst. Geeft
    True als kern gelezen is. Zonder kern blijft de vaste lijst gelden; de runner meldt dat als nood."""
    sql = ("select json_agg(json_build_object('code', f.code, 'kbo', coalesce(f.kbo_nummer, ''), 'straat', "
           "coalesce(a.straat, ''), 'nr', coalesce(a.huisnummer, ''), 'weergave', coalesce(a.weergave, ''))) "
           "from kern.firma f left join kern.adres a on a.id = f.adres_id where f.code in ('HARC', 'HARM')")
    if psql is None:
        import organisatie
        psql = organisatie._psql
    rijen = psql(sql) or []
    # Codex X4 (controle 5): beide firma's, elk met een ondernemingsnummer en een adres; anders werkt Bouw niet
    if {r.get("code") for r in rijen} != set(KERN_CODES) or not all(
            len(re.sub(r"\D", "", r.get("kbo") or "")) >= 9 and r.get("straat") and r.get("nr") for r in rijen):
        return False
    for r in rijen:
        firma = KERN_CODES.get(r.get("code"))
        if not firma:
            continue
        cijfers = re.sub(r"\D", "", r.get("kbo") or "").lstrip("0")
        if len(cijfers) >= 8 and cijfers not in EXTRA[firma]["cijfers"]:
            EXTRA[firma]["cijfers"].append(cijfers)
        if r.get("straat") and r.get("nr"):
            for p in adrespatronen(r["straat"], r["nr"]):
                if p not in EXTRA[firma]["patronen"]:
                    EXTRA[firma]["patronen"].append(p)
    return True


def _cijfertreffers(t, firma):
    bekend = CIJFERS[firma] + EXTRA[firma]["cijfers"]
    for m in NUMMERREEKS.finditer(t):
        cijfers = re.sub(r"\D", "", m.group(0))
        if any(b in cijfers for b in bekend):
            yield m.group(0).strip()


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
    for p in KENMERKEN[tegen] + EXTRA[tegen]["patronen"] + list((extra_kenmerken or {}).get(tegen) or []):
        weg += [f"kenmerk van {FIRMANAMEN[tegen]} '{m.group(0)}'" for m in re.finditer(p, t, re.I)]
    weg += [f"nummer van {FIRMANAMEN[tegen]} '{n}'" for n in _cijfertreffers(t, tegen)]
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
    return any(re.search(p, t, re.I) for f in (HA, HB) for p in KENMERKEN[f] + EXTRA[f]["patronen"]) or any(
        True for f in (HA, HB) for _ in _cijfertreffers(t, f))


def noemt(tekst, firma):
    """Noemt de tekst deze firma (naam, code, domein, nummer, adres)?"""
    t = normaal(tekst)
    return any(re.search(p, t, re.I) for p in KENMERKEN[firma] + EXTRA[firma]["patronen"]) or any(
        True for _ in _cijfertreffers(t, firma))


def is_andere_firma(naam, firma):
    """Is deze inschrijver (naam zoals op de offerte of in de bestandsnaam) de andere firma?"""
    t, tegen = normaal(naam), andere(firma)
    return any(re.search(p, t, re.I) for p in KENMERKEN[tegen] + EXTRA[tegen]["patronen"]) or any(
        True for _ in _cijfertreffers(t, tegen))


def mag_weg(tekst, firma, extra_kenmerken=None):
    return not schendingen(tekst, firma, extra_kenmerken)
