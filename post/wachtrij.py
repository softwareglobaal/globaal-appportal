"""Postbus: verzendopdrachten die wachten op toestemming van de gebruiker.

Niets gaat de deur uit zonder dat de gebruiker het eerst gezien heeft. De
tools versturen en doorsturen werken daarom in twee stappen:

1. Zonder 'bevestig': de server stelt het bericht samen, verstuurt NIETS, en
   geeft het concept terug (afzender, ontvangers, onderwerp, tekst) met een
   bevestigingscode. Het concept staat hier klaar.
2. Met 'bevestig': de server haalt precies dat concept op en verstuurt het.
   Wat verstuurd wordt, is dus altijd wat getoond werd; een wijziging vraagt
   een nieuw concept en een nieuwe code.

Een code is persoonlijk (alleen wie hem kreeg kan hem gebruiken), eenmalig,
en een half uur geldig. De opdrachten staan in een bestand, niet in het
geheugen: de server draait met meerdere workers, en de bevestiging komt niet
per se bij dezelfde worker binnen als de aanvraag. Na een herstart zijn ze
weg; dat is goed, dan vraag je gewoon een nieuw concept.
"""
import json
import os
import re
import secrets
import time

MAP = os.environ.get("POSTBUS_WACHT_MAP", "/tmp/postbus-wacht")
GELDIG_S = 30 * 60
_CODE = re.compile(r"^[0-9a-f]{8}$")


def _pad(code):
    return os.path.join(MAP, code + ".json")


def _opruimen():
    """Verlopen opdrachten weg, zodat de map niet volloopt."""
    grens = time.time() - GELDIG_S
    try:
        namen = os.listdir(MAP)
    except FileNotFoundError:
        return
    for naam in namen:
        pad = os.path.join(MAP, naam)
        try:
            if os.path.getmtime(pad) < grens:
                os.remove(pad)
        except OSError:
            pass


def zet(wie, soort, gegevens):
    """Legt een opdracht klaar; geeft (code, geldig_tot als tekst)."""
    os.makedirs(MAP, mode=0o700, exist_ok=True)
    _opruimen()
    code = secrets.token_hex(4)
    item = {"code": code, "gebruiker": str(wie.get("gebruiker") or ""),
            "soort": soort, "gegevens": gegevens, "gemaakt": time.time()}
    tijdelijk = _pad(code) + ".tmp"
    fd = os.open(tijdelijk, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(item, f)
    os.replace(tijdelijk, _pad(code))
    geldig_tot = time.strftime("%H:%M UTC",
                               time.gmtime(item["gemaakt"] + GELDIG_S))
    return code, geldig_tot


def neem(wie, soort, code):
    """Haalt een klaargezette opdracht op en maakt de code meteen ongeldig.

    Hernoemen is atomair: bij twee gelijktijdige bevestigingen krijgt er maar
    een de opdracht, dus een bericht kan nooit twee keer vertrekken. Mislukt
    het versturen daarna, dan is de code op en vraag je een nieuw concept.
    """
    code = str(code or "").strip().lower()
    if not _CODE.match(code):
        raise ValueError("Die bevestigingscode klopt niet. Vraag eerst een "
                         "concept op (zonder 'bevestig').")
    geclaimd = _pad(code) + ".bezig"
    try:
        os.rename(_pad(code), geclaimd)
    except FileNotFoundError:
        raise ValueError("Deze bevestigingscode bestaat niet (meer): al "
                         "gebruikt, verlopen, of de server is intussen "
                         "herstart. Vraag een nieuw concept op.")
    try:
        with open(geclaimd, encoding="utf-8") as f:
            item = json.load(f)
    finally:
        try:
            os.remove(geclaimd)
        except OSError:
            pass
    if item.get("gebruiker") != str(wie.get("gebruiker") or ""):
        raise ValueError("Deze bevestigingscode hoort bij een andere "
                         "gebruiker.")
    if item.get("soort") != soort:
        raise ValueError(f"Deze bevestigingscode hoort bij "
                         f"{item.get('soort')}, niet bij {soort}.")
    if time.time() - item.get("gemaakt", 0) > GELDIG_S:
        raise ValueError("Deze bevestigingscode is verlopen (een half uur "
                         "geldig). Vraag een nieuw concept op.")
    return item["gegevens"]
