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
import time

from . import scheiding as S

BASIS = {S.HA: "/Work All/01. H-A WORK", S.HB: "/Work All/04. Harmoniebouw"}
OCTOPUS_CODES = {S.HA: ("HA", "HARC"), S.HB: ("HB", "HARM")}
STOPWOORDEN = {"binnen", "buiten", "werken", "werk", "nieuwe", "nieuw", "plaatsen", "plaatsing", "leveren", "levering",
               "voor", "met", "van", "een", "het", "de", "en", "of", "in", "op", "aan", "uitvoeren", "renovatie"}
NIET_ZOEKEN = ("/0 archive/", "/_mag weg", "/nog te sorteren")
# Alleen een treffer in een offerte- of onderaannemersmap zegt met wie de firma al werkte (gemeten 01-11-2026: "plat"
# gaf Revit-bibliotheken, mails en "Platteau"); H-A: .../Quotes & Invoices/Offerte/<lot>, HB: 05. ONDERAANNEMER en
# Offerte IN per post.
OFFERTEMAP = re.compile(r"\b(?:offerte\w*|quotes?|onderaannem\w*|prijsaanbieding\w*|prijsvragen?)\b", re.I)
UITGANG = ("", "en", "s", "e", "te", "ten")


def zoekwoorden(werk, maximum=2):
    """De woorden van het werk waarop een mapnaam zou passen: de langste eerst, zonder stopwoorden."""
    woorden = [w for w in re.findall(r"[a-zà-ÿ]{4,}", S.normaal(werk).lower()) if w not in STOPWOORDEN]
    return sorted(dict.fromkeys(woorden), key=len, reverse=True)[:maximum]


def woord_in(woord, naam):
    """Staat het woord als heel woord in de naam (ook meervoud of een samenstelling met een vakwoord, platdak), en niet
    als stuk van een ander woord (Platane, Plates, platform, Platteau)?"""
    from .vakwoorden import _samengesteld
    for t in re.findall(r"[a-z0-9à-ÿ]+", S.normaal(naam).lower()):
        if any(t == woord + u for u in UITGANG):
            return True
        if t.startswith(woord) and len(t) - len(woord) >= 3 and _samengesteld(t[len(woord):]):
            return True
        if t.endswith(woord) and len(t) - len(woord) >= 3 and _samengesteld(t[:-len(woord)]):
            return True
    return False


def in_offertemap(pad):
    """Ligt dit pad onder een offerte- of onderaannemersmap (een bovenliggende map, niet de treffer zelf)?"""
    return any(OFFERTEMAP.search(deel) for deel in pad.split("/")[:-1])


MAX_PAGINAS = 20


class Onvolledig(list):
    """Een lijst treffers waarvan Dropbox zei dat er meer zijn (Codex X8, controle 3): het verslag zegt het."""
    volledig = True


def _dropbox_zoek(query, pad, rpc=None, deadline=None):
    """Treffers van files/search_v2 met vervolgpagina's (search/continue_v2), hoogstens MAX_PAGINAS (Codex X12). Met een
    deadline (time.monotonic, controle 17 en 18) start geen verzoek meer na de deadline en wacht elk verzoek hoogstens tot
    de deadline; dan zegt het verslag dat er meer zijn."""
    from .webpagina import binnen
    if rpc is None:
        import bronnen
        basis = lambda p, body, t: bronnen._rpc(p, body, timeout=t)     # noqa: E731
    else:
        basis = lambda p, body, t: rpc(p, body)     # noqa: E731

    def vraag(p, body):
        if not deadline:
            return basis(p, body, 60)
        rest = deadline - time.monotonic()
        if rest < 1:
            raise TimeoutError("deadline")
        # Codex, controle 19: ook een antwoord dat druppelsgewijs binnenkomt, stopt op de deadline
        return binnen(lambda: basis(p, body, min(60, rest)), rest)
    treffers = Onvolledig()
    try:
        if deadline and time.monotonic() > deadline:
            raise TimeoutError("deadline")
        uit = vraag("files/search_v2", {"query": query, "options": {"path": pad, "max_results": 100, "filename_only": True}})
        for _ in range(MAX_PAGINAS):
            for m in (uit or {}).get("matches") or []:
                meta = ((m.get("metadata") or {}).get("metadata")) or {}
                if meta.get("path_display"):
                    treffers.append({"soort": meta.get(".tag"), "naam": meta.get("name", ""), "pad": meta["path_display"]})
            if not (uit or {}).get("has_more") or not (uit or {}).get("cursor"):
                return treffers
            if deadline and time.monotonic() > deadline:
                break
            uit = vraag("files/search/continue_v2", {"cursor": uit["cursor"]})
    except TimeoutError:          # ook een verzoek dat niet voor de deadline antwoordt (socket-timeout)
        pass
    treffers.volledig = False
    return treffers


def in_mappen(firma, werk, zoek=None, maximum=12, deadline=None):
    """[{naam, pad, project}] uit de offerte- en onderaannemersmappen van deze firma, met het werk als heel woord in de
    naam. zoek(query, pad) is te vervangen in een test. Een map die onder de andere firma ligt, telt nooit mee (ook niet
    als de zoekfunctie ze teruggeeft)."""
    zoek = zoek or (lambda q, p: _dropbox_zoek(q, p, deadline=deadline))
    basis = BASIS[firma]
    gezien, uit = set(), Onvolledig()
    for woord in zoekwoorden(werk):
        if deadline and time.monotonic() > deadline:      # Codex, controle 18: geen nieuw zoekwoord na de deadline
            uit.volledig = False
            break
        treffers = zoek(woord, basis) or []
        if getattr(treffers, "volledig", True) is False:
            uit.volledig = False
        for t in treffers:
            pad = t.get("pad") or ""
            laag = pad.lower()
            if not laag.startswith(basis.lower() + "/") or any(n in laag for n in NIET_ZOEKEN):
                continue
            if laag.startswith(BASIS[S.andere(firma)].lower()) or S.schendingen(pad, firma):
                continue
            if not woord_in(woord, t.get("naam") or pad.rsplit("/", 1)[-1]) or not in_offertemap(pad):
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
