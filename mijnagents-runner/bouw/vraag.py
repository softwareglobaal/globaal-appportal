"""Een vraag aan de afdeling Bouw ontleden. De Regisseur geeft ze door als velden, gescheiden door een puntkomma of een
nieuwe regel, bijvoorbeeld:

    firma: HB; werk: plafonneerwerk binnen; omvang: 120 m2 muren en plafonds; gemeente: 3020 Herent; straal: 25;
    tegen: 15-11-2026; project: 2145

De firma is altijd verplicht (overleg X1): zonder HA of HB werkt geen enkele agent van Bouw. Een vraag zonder veldnamen
krijgt alleen de firma uit de tekst; de rest moet dan opnieuw gevraagd worden.
"""
import re

from aankoop import privacy as P

from . import scheiding as S

VELDEN = ("firma", "werk", "omvang", "gemeente", "straal", "tegen", "project", "lot", "map", "bestanden")
SYNONIEMEN = {"vak": "werk", "taak": "werk", "werken": "werk", "gebied": "gemeente", "plaats": "gemeente",
              "postcode": "gemeente", "regio": "gemeente", "termijn": "tegen", "timing": "tegen", "deadline": "tegen",
              "km": "straal", "projectnummer": "project", "dossier": "project", "post": "lot", "pad": "map"}
FIRMA_WOORDEN = ((S.HA, r"\b(?:ha|harc|h\s?-?\s?architects?)\b"), (S.HB, r"\b(?:hb|harm|harmonie\s?-?\s?bouw)\b"))
STRAAL_STANDAARD = 25


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


GEMEENTE = re.compile(r"^\s*(?:\d{4}\s*)?[A-Za-zÀ-ÿ'’.\- ]{2,40}\s*$")
NAAM_NA = re.compile(r"\b(?i:bij|voor|van|familie|fam\.?|woning|huis|klant|bouwheer)\s+(?:(?i:de|van|der|den)\s+)*"
                     r"[A-ZÀ-Ý][a-zà-ÿ]+(?:\s+[A-ZÀ-Ý][a-zà-ÿ]+)+")
MAX_VELD = 160


def naar_buiten_fouten(v):
    """Waarom de velden die naar buiten gaan (werk, omvang, gemeente) niet mogen vertrekken (Codex X5, controle 2):
    persoonsgegevens volgens het patroon van De Prijsonderzoeker, een naam na 'bij', 'voor', 'familie' en dergelijke,
    een gemeente die meer is dan postcode en naam (een straat of huisnummer), of een veld dat te lang is."""
    fouten = list(P.gevonden(" ; ".join(str(v.get(k) or "") for k in ("werk", "omvang", "gemeente"))))
    if any(NAAM_NA.search(str(v.get(k) or "")) for k in ("werk", "omvang")):
        fouten.append("naam")
    if v.get("gemeente") and not GEMEENTE.match(v["gemeente"]):
        fouten.append("adres in de gemeente (alleen postcode en gemeente)")
    if any(len(str(v.get(k) or "")) > MAX_VELD for k in ("werk", "omvang", "gemeente")):
        fouten.append("een te lang veld")
    if any(S.noemt_een_firma(str(v.get(k) or "")) for k in ("werk", "omvang", "gemeente")):
        fouten.append("een firmanaam")
    return list(dict.fromkeys(fouten))


def ontbreekt_vergelijker(v):
    """Wat de vergelijker zeker nodig heeft: de firma, en een map of een project (met lot)."""
    blok = [] if v.get("firma") else ["firma"]
    if not v.get("map") and not v.get("project"):
        blok.append("project of map")
    return blok
