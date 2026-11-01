"""Waar de offertes van een lot staan, per firma, en welke bestanden de vergelijker leest. Alleen lezen.

H-Architects: <projectmap>/…Implementation & Site Control/…Quotes & Invoices/Offerte/<lot>, bv. "06 … - ventilatie".
Harmonie Bouw: <projectmap onder 10. PROJECTEN>/5. Offerte IN+OUT/Offerte IN/<post>, bv. "54. BINNENDEUREN EN -RAMEN".
Een map buiten de mappen van de firma wordt geweigerd: de ene firma leest de offertes van de andere niet.
"""
import re

from . import eigen as E
from . import scheiding as S

HB_PROJECTEN = "/Work All/04. Harmoniebouw/10. PROJECTEN ◀︎◀︎"
STAPPEN = {S.HA: (("implementation",), ("quotes",), ("offerte",)),
           S.HB: (("offerte in+out", "offerte in + out"), ("offerte in",))}
OVERSLAAN = ("oude versies", "documentatie", "niet weerhouden", "_mag weg")


class MapFout(Exception):
    pass


def van_firma(pad, firma):
    laag = (pad or "").lower()
    return laag.startswith(E.BASIS[firma].lower() + "/") and not laag.startswith(E.BASIS[S.andere(firma)].lower())


def _kind(lijst_fn, pad, woorden):
    for e in lijst_fn(pad, recursief=False) or []:
        naam = e.get("name", "").lower()
        if e.get(".tag") == "folder" and any(w in naam for w in woorden):
            return e.get("path_display")
    return None


def _woorden(tekst):
    return {w for w in re.findall(r"[a-zà-ÿ]{3,}|\d{1,3}", S.normaal(tekst).lower())}


def kies_lot(lots, hint):
    """De lotmap die het best past bij de hint (nummer vooraan of gemeenschappelijke woorden), of None."""
    if not hint:
        return None
    h = _woorden(hint)
    nummer = re.match(r"\s*(\d{1,3})\b", hint)
    beste, score = None, 0
    for lot in lots:
        naam = lot.rsplit("/", 1)[-1]
        if nummer and re.match(rf"0*{int(nummer.group(1))}\b", naam):
            return lot
        s = len(h & _woorden(naam))
        if s > score:
            beste, score = lot, s
    return beste


def offertemap(v, lijst_fn, projectmap_fn):
    """(pad van de lotmap of None, [lotmappen]). v: de ontlede vraag. lijst_fn = bronnen.lijst; projectmap_fn(firma,
    project) geeft de projectmap. Zonder lot: (None, lots), zodat het verslag de keuze voorlegt."""
    firma = v["firma"]
    if v.get("map"):
        if not van_firma(v["map"], firma):
            raise MapFout(f"de map hoort niet bij {S.FIRMANAMEN[firma]}")
        return v["map"], []
    pad = projectmap_fn(firma, v.get("project"))
    if not pad:
        raise MapFout(f"project {v.get('project')} niet gevonden bij {S.FIRMANAMEN[firma]}")
    if not van_firma(pad, firma):
        raise MapFout(f"de projectmap hoort niet bij {S.FIRMANAMEN[firma]}")
    for woorden in STAPPEN[firma]:
        pad = _kind(lijst_fn, pad, woorden)
        if not pad:
            raise MapFout("geen offertemap gevonden in het project")
    lots = sorted(e["path_display"] for e in (lijst_fn(pad, recursief=False) or [])
                  if e.get(".tag") == "folder" and not any(o in e.get("name", "").lower() for o in OVERSLAAN))
    return kies_lot(lots, v.get("lot")), lots


def offertebestanden(pad, lijst_fn):
    """De PDF's direct in de lotmap, zonder eerdere vergelijkingen; oude versies en documentatie staan in submappen en
    tellen niet mee."""
    uit = []
    for e in lijst_fn(pad, recursief=False) or []:
        naam = e.get("name", "")
        if e.get(".tag") == "file" and naam.lower().endswith(".pdf") and "vergelijking" not in naam.lower():
            uit.append({"naam": naam, "pad": e.get("path_display") or e.get("path_lower"),
                        "gewijzigd": e.get("client_modified", ""), "grootte": e.get("size")})
    return sorted(uit, key=lambda b: b["naam"].lower())


def projectmap(firma, project, zoek=None):
    """De projectmap van een firma. H-Architects via de projectindex (koppelingen/projectadressen.py); Harmonie Bouw
    via een zoekopdracht op de projectcode onder 10. PROJECTEN."""
    if not project:
        return None
    if firma == S.HA:
        import projectadressen
        p = projectadressen.index().get(str(project))
        return p["map"] if p else None
    zoek = zoek or E._dropbox_zoek
    for t in zoek(str(project), HB_PROJECTEN) or []:
        if t.get("soort") == "folder" and str(project).lower() in t.get("naam", "").lower():
            return t["pad"]
    return None
