"""Een vraag aan de afdeling Bouw ontleden. De Regisseur geeft ze door als velden, gescheiden door een puntkomma of een
nieuwe regel, bijvoorbeeld:

    firma: HB; werk: plafonneerwerk binnen; omvang: 120 m2 muren en plafonds; gemeente: 3020 Herent; straal: 25;
    tegen: 15-11-2026; project: 2145

De firma is altijd verplicht (overleg X1): zonder HA of HB werkt geen enkele agent van Bouw. Een vraag zonder veldnamen
krijgt alleen de firma uit de tekst; de rest moet dan opnieuw gevraagd worden.
"""
import hashlib
import re

from aankoop import privacy as P

from . import scheiding as S

VELDEN = ("firma", "werk", "omvang", "gemeente", "straal", "tegen", "project", "lot", "map", "bestanden")
SYNONIEMEN = {"vak": "werk", "taak": "werk", "werken": "werk", "gebied": "gemeente", "plaats": "gemeente",
              "postcode": "gemeente", "regio": "gemeente", "termijn": "tegen", "timing": "tegen", "deadline": "tegen",
              "km": "straal", "projectnummer": "project", "dossier": "project", "post": "lot", "pad": "map"}
FIRMA_WOORDEN = ((S.HA, r"\b(?:ha|harc|h\s?-?\s?architects?)\b"), (S.HB, r"\b(?:hb|harm|harmonie\s?-?\s?bouw)\b"))
STRAAL_STANDAARD = 25


def vingerafdruk(tekst, vandaag):
    """Het logboek bewaart nooit de vraag zelf, alleen een vingerafdruk (zoals De Prijsonderzoeker)."""
    return hashlib.sha256(f"{vandaag}:{str(tekst or '').strip()}".encode()).hexdigest()[:12]


def sleutel(tekst, vandaag):
    """De sleutel van het verslag van een vraag: de firma en de vingerafdruk. De Regisseur rekent dezelfde sleutel uit
    de vraag die hij doorgaf en leest alleen dat ene verslag (Codex X5, controle 3)."""
    return f"{firma_uit(ontleed(tekst).get('firma') or '') or 'geen'}:{vingerafdruk(tekst, vandaag)}"


def firma_uit(tekst):
    """HA of HB als de tekst precies een van beide noemt, anders None (beide of geen: niet raden)."""
    t = S.normaal(tekst).lower()
    gevonden = {f for f, p in FIRMA_WOORDEN if re.search(p, t)}
    return gevonden.pop() if len(gevonden) == 1 else None


def ontleed(tekst):
    """{veld: waarde} met firma als HA, HB of None, straal als getal."""
    uit = {}
    for stuk in re.split(r"[;\n]", str(tekst or "")):
        if ":" not in stuk:
            continue
        sleutel, waarde = stuk.split(":", 1)
        sleutel = SYNONIEMEN.get(sleutel.strip().lower(), sleutel.strip().lower())
        if sleutel in VELDEN and waarde.strip():
            uit[sleutel] = " ".join(waarde.split())
    uit["firma"] = firma_uit(uit.get("firma") or tekst)
    try:
        uit["straal"] = max(1, min(150, int(re.sub(r"\D", "", str(uit.get("straal") or "")) or STRAAL_STANDAARD)))
    except ValueError:
        uit["straal"] = STRAAL_STANDAARD
    if uit.get("project"):
        m = re.search(r"\b\d{4}\b", uit["project"])
        uit["project"] = m.group(0) if m else uit["project"]
    return uit


def ontbreekt_zoeker(v):
    """(blokkerend, aan_te_vullen): zonder firma, werk en gemeente zoek ik niet; zonder omvang of timing zoek ik wel,
    maar zijn de mails niet klaar om te versturen."""
    blok = [n for n in ("firma", "werk") if not v.get(n)]
    if not v.get("gemeente") and not (v.get("firma") == S.HA and v.get("project")):
        blok.append("gemeente")
    return blok, [n for n in ("omvang", "tegen") if not v.get(n)]


# Een gemeente is altijd postcode en naam (Codex, controle 3: een naam zonder postcode kan een persoon zijn).
GEMEENTE = re.compile(r"^\s*[1-9]\d{3}\s+[A-Za-zÀ-ÿ'’.\- ]{2,40}\s*$")
NAAM_NA = re.compile(r"\b(?i:bij|voor|van|familie|fam\.?|woning|huis|klant|bouwheer)\s+(?:(?i:de|van|der|den)\s+)*"
                     r"[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)+")
MAX_VELD = 160
GEMEENTE_FOUT = "gemeente zonder postcode, of met een adres (alleen postcode en gemeente)"
# Een straat als los woord met een huisnummer (Grote Markt 12, Rue Neuve 3), naast de patronen van De Prijsonderzoeker
LOS_ADRES = re.compile(r"\b(?:grote\s+|kleine\s+|oude\s+)?(?:markt|plein|steenweg|lei|dreef|kaai|vest|square|avenue|rue|"
                       r"chaussée|place|boulevard|weg|laan|straat)\s+\d{1,4}[a-z]?\b", re.I)
HOOFDLETTERNAAM = re.compile(r"\b[A-ZÀ-Ý]{3,}(?:\s+(?:VAN|DE|DER|DEN)\b)*\s+[A-ZÀ-Ý]{3,}\b")


def persoonsgegevens(tekst):
    """De soorten persoonsgegevens in een tekst, ook in hoofdletters (Codex X4, controle 4): de patronen van De
    Prijsonderzoeker op de tekst en op de tekst met hoofdletters per woord, een naam na bij of voor, een straat als los
    woord met een nummer, en twee woorden helemaal in hoofdletters (een naam als JAN PEETERS)."""
    t = str(tekst or "")
    titel = " ".join(w[:1].upper() + w[1:].lower() if w.isupper() and len(w) > 1 else w for w in t.split())
    uit = list(P.gevonden(t)) + [s for s in P.gevonden(titel) if s not in P.gevonden(t)]
    if NAAM_NA.search(t) or NAAM_NA.search(titel):
        uit.append("naam")
    if LOS_ADRES.search(t):
        uit.append("adres")
    if HOOFDLETTERNAAM.search(t):
        uit.append("naam in hoofdletters")
    return list(dict.fromkeys(uit))


def naar_buiten_fouten(v):
    """Waarom de velden die naar buiten gaan (werk, omvang, gemeente) niet mogen vertrekken (Codex X5, controle 2):
    persoonsgegevens volgens het patroon van De Prijsonderzoeker, een naam na 'bij', 'voor', 'familie' en dergelijke,
    een gemeente die meer is dan postcode en naam (een straat of huisnummer), of een veld dat te lang is."""
    fouten = []
    for k in ("werk", "omvang"):
        fouten += persoonsgegevens(v.get(k))
    fouten += [s for s in P.gevonden(str(v.get("gemeente") or "")) if s != "naam"]
    if v.get("gemeente") and not GEMEENTE.match(v["gemeente"]):
        fouten.append(GEMEENTE_FOUT)
    if any(len(str(v.get(k) or "")) > MAX_VELD for k in ("werk", "omvang", "gemeente")):
        fouten.append("een te lang veld")
    if any(S.noemt_een_firma(str(v.get(k) or "")) for k in ("werk", "omvang", "gemeente")):
        fouten.append("een firmanaam")
    return list(dict.fromkeys(fouten))


def met_postcode(punt, gevraagd, postinfo):
    """Geopunt geeft bij een gemeente zonder straat geen postcode (01-11-2026). Dan telt de postcode uit de vraag, maar
    alleen als het postinfo-register die postcode bij dezelfde gemeente zet. postinfo: postcode -> gemeente of None."""
    if not isinstance(punt, dict) or str(punt.get("postcode") or "").strip() or not punt.get("gemeente"):
        return punt
    m = re.match(r"^\s*([1-9]\d{3})\s", str(gevraagd or "") + " ")
    if not m or str(postinfo(m.group(1)) or "").strip().lower() != str(punt["gemeente"]).strip().lower():
        return punt
    return {**punt, "postcode": m.group(1)}


def officiele_gemeente(punt):
    """'postcode Gemeente' zoals Geopunt het adres kent, of None. Alleen dit gaat als gebied naar buiten."""
    if not isinstance(punt, dict):
        return None
    postcode, gemeente = str(punt.get("postcode") or "").strip(), str(punt.get("gemeente") or "").strip()
    if not re.fullmatch(r"[1-9]\d{3}", postcode) or not GEMEENTE.match(f"{postcode} {gemeente}"):
        return None
    return f"{postcode} {gemeente}"


def ontbreekt_vergelijker(v):
    """Wat de vergelijker zeker nodig heeft: de firma, en een map of een project (met lot)."""
    blok = [] if v.get("firma") else ["firma"]
    if not v.get("map") and not v.get("project"):
        blok.append("project of map")
    return blok
