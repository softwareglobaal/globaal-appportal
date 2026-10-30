"""Eerst de eigen bronnen van die ene firma (overleg X2, G2): met wie werkte zij al?

  - Dropbox: map- en bestandsnamen met het werk erin, alleen onder de mappen van die firma
    (H-Architects: offertemappen per project, "NN Firma - vak"; Harmonie Bouw: 05. ONDERAANNEMER en Offerte IN per post);
  - de Octopus-boekhouding van die firma (kosten.octopus_relatie): was een kandidaat van het web al leverancier?

Nooit de mappen of de boekhouding van de andere firma: wat de ene firma weet, gebruikt de andere niet. Alleen lezen.
Er komt geen eigen lijst van aannemers: het verslag noemt wat het vond, met het pad als bron (een register volgt later,
met alleen firmacode, partij_id, vak, regio, bewijs en datum).
"""
import json
import re

from . import scheiding as S

BASIS = {S.HA: "/Work All/01. H-A WORK", S.HB: "/Work All/04. Harmoniebouw"}
OCTOPUS_CODES = {S.HA: ("HA", "HARC"), S.HB: ("HB", "HARM")}
STOPWOORDEN = {"binnen", "buiten", "werken", "werk", "nieuwe", "nieuw", "plaatsen", "plaatsing", "leveren", "levering",
               "voor", "met", "van", "een", "het", "de", "en", "of", "in", "op", "aan", "uitvoeren", "renovatie"}
NIET_ZOEKEN = ("/0 archive/", "/_mag weg", "/nog te sorteren")


def zoekwoorden(werk, maximum=2):
    """De woorden van het werk waarop een mapnaam zou passen: de langste eerst, zonder stopwoorden."""
    woorden = [w for w in re.findall(r"[a-zà-ÿ]{4,}", S.normaal(werk).lower()) if w not in STOPWOORDEN]
    return sorted(dict.fromkeys(woorden), key=len, reverse=True)[:maximum]


def _dropbox_zoek(query, pad):
    import bronnen
    uit = bronnen._rpc("files/search_v2", {"query": query, "options": {"path": pad, "max_results": 100,
                                                                      "filename_only": True}})
    treffers = []
    for m in (uit or {}).get("matches") or []:
        meta = ((m.get("metadata") or {}).get("metadata")) or {}
        if meta.get("path_display"):
            treffers.append({"soort": meta.get(".tag"), "naam": meta.get("name", ""), "pad": meta["path_display"]})
    return treffers


def in_mappen(firma, werk, zoek=None, maximum=12):
    """[{naam, pad, project}] uit de mappen van deze firma, met het werk in de naam. zoek(query, pad) is te vervangen
    in een test. Een map die onder de andere firma ligt, telt nooit mee (ook niet als de zoekfunctie ze teruggeeft)."""
    zoek = zoek or _dropbox_zoek
    basis = BASIS[firma]
    gezien, uit = set(), []
    for woord in zoekwoorden(werk):
        for t in zoek(woord, basis) or []:
            pad = t.get("pad") or ""
            laag = pad.lower()
            if not laag.startswith(basis.lower() + "/") or any(n in laag for n in NIET_ZOEKEN):
                continue
            if laag.startswith(BASIS[S.andere(firma)].lower()):
                continue
            ouder = pad.rsplit("/", 1)[0] if t.get("soort") == "file" else pad
            if ouder.lower() in gezien:
                continue
            gezien.add(ouder.lower())
            m = re.search(r"/(\d{4})\s[^/]*", pad)
            uit.append({"naam": t.get("naam", ""), "pad": pad, "project": m.group(1) if m else ""})
            if len(uit) >= maximum:
                return uit
    return uit


def eerder_leverancier(firma, nummers, psql=None):
    """({cijfers: naam in de boekhouding}, boekhouding_bekend) voor de ondernemingsnummers van webkandidaten, alleen in
    de Octopus-relaties van deze firma. boekhouding_bekend is False als er voor deze firma niets in kern staat; dan zegt
    het verslag "niet nagekeken", nooit "nee"."""
    cijfers = sorted({re.sub(r"\D", "", n or "") for n in nummers if n} - {""})
    cijfers = [c for c in cijfers if re.fullmatch(r"\d{9,10}", c)]
    codes = ",".join(f"'{c}'" for c in OCTOPUS_CODES[firma])
    lijst = ",".join(f"'{c.zfill(10)}'" for c in cijfers) or "''"
    sql = ("select json_build_object('totaal', (select count(*) from kosten.octopus_relatie where firma_code in "
           f"({codes})), 'treffers', (select json_agg(json_build_object('btw', btw_nummer, 'naam', naam)) from "
           f"kosten.octopus_relatie where firma_code in ({codes}) and is_leverancier and "
           f"lpad(regexp_replace(btw_nummer, '[^0-9]', '', 'g'), 10, '0') in ({lijst})))")
    if psql is None:
        import organisatie
        psql = organisatie._psql
    uit = psql(sql) or {}
    if isinstance(uit, str):
        uit = json.loads(uit)
    treffers = {re.sub(r"\D", "", t.get("btw") or "").zfill(10): t.get("naam", "") for t in uit.get("treffers") or []}
    return treffers, bool(uit.get("totaal"))
