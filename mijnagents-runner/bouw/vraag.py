"""Een vraag aan de afdeling Bouw ontleden. De Regisseur geeft ze door als velden, gescheiden door een puntkomma of een
nieuwe regel, bijvoorbeeld:

    firma: HB; werk: plafonneerwerk binnen; omvang: 120 m2 muren en plafonds; gemeente: 3020 Herent; straal: 25;
    tegen: 15-11-2026; project: 2145

De firma is altijd verplicht (overleg X1): zonder HA of HB werkt geen enkele agent van Bouw. Een vraag zonder veldnamen
krijgt alleen de firma uit de tekst; de rest moet dan opnieuw gevraagd worden.
"""
import re

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


def ontbreekt_vergelijker(v):
    """Wat de vergelijker zeker nodig heeft: de firma, en een map of een project (met lot)."""
    blok = [] if v.get("firma") else ["firma"]
    if not v.get("map") and not v.get("project"):
        blok.append("project of map")
    return blok
