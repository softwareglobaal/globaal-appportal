"""Welke applicaties bestaan er, en wie mag welke lezen.

Authentik is hier de bron van waarheid, en dat is geen implementatiedetail maar
het hele beveiligingsmodel. Wie een tegel op het portaal niet mag zien, mag de
data van die app hier ook niet lezen. Er is bewust geen tweede lijst van
rechten die naast Authentik kan gaan staan en stilletjes kan verouderen.

De rechten worden bij elke aanroep opnieuw opgehaald (kort gebufferd), niet in
het OAuth-token gebakken. Een token leeft twaalf uur; een ingetrokken groep
moet binnen een minuut werken, niet pas na twaalf uur.

Dit bestand praat met de Authentik-API en verder met niets. Geen Flask, geen
database, zodat het te testen is zonder de rest van de server op te tuigen
(`test_catalogus.py`).
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

BUFFER_TTL = 60          # seconden dat de cataloog blijft staan
PAGINA = 200             # page_size voor de API
TIJDSLIMIET = 15         # seconden per API-aanroep


class Onbereikbaar(RuntimeError):
    """Authentik gaf geen antwoord. We weigeren dan alles, niet niets."""


@dataclass(frozen=True)
class Applicatie:
    """Een app zoals Authentik hem kent, plus waar zijn data staat."""
    slug: str
    naam: str
    url: str
    omschrijving: str
    groepen: tuple = field(default=())      # groepen die hem mogen zien
    gebruikers: tuple = field(default=())   # losse gebruikers, buiten een groep

    def als_dict(self, bron=None):
        uit = {"app": self.slug, "naam": self.naam,
               "url": self.url or None, "omschrijving": self.omschrijving or None}
        if bron is not None:
            uit["bron"] = bron
        return uit


class Authentik:
    """Leest de cataloog en de rechten. Schrijft nooit.

    Het serviceaccount achter `token` heeft alleen kijkrechten
    (view_application, view_group, view_user, view_policybinding); zie
    `scripts/add-portal-mcp-token.py`.
    """

    def __init__(self, basis, token, ttl=BUFFER_TTL, ophaler=None):
        self.basis = basis.rstrip("/")
        self._token = token
        self._ttl = ttl
        self._ophaler = ophaler or self._haal_op
        self._buffer = {}

    # ---- HTTP ------------------------------------------------------------
    def _haal_op(self, pad):
        """Alle pagina's van een API-endpoint als lijst van resultaten."""
        uit, url = [], f"{self.basis}/api/v3/{pad}"
        while url:
            verzoek = urllib.request.Request(
                url, headers={"Authorization": f"Bearer {self._token}",
                              "Accept": "application/json"})
            try:
                with urllib.request.urlopen(verzoek, timeout=TIJDSLIMIET) as a:
                    blok = json.loads(a.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                raise Onbereikbaar(
                    f"Authentik gaf {e.code} op {pad}. Heeft het "
                    f"serviceaccount de kijkrechten?") from e
            except Exception as e:
                raise Onbereikbaar(f"Authentik onbereikbaar: {e}") from e
            uit.extend(blok.get("results") or [])
            url = (blok.get("pagination") or {}).get("next") or ""
            if url and not url.startswith("http"):
                url = f"{self.basis}/api/v3/{url.lstrip('/')}"
        return uit

    def _gebufferd(self, sleutel, pad):
        nu = time.time()
        gezet, waarde = self._buffer.get(sleutel, (0, None))
        if waarde is not None and nu - gezet < self._ttl:
            return waarde
        waarde = self._ophaler(pad)
        self._buffer[sleutel] = (nu, waarde)
        return waarde

    # ---- Cataloog --------------------------------------------------------
    def applicaties(self):
        """Alle apps die Authentik kent, met de rechten erbij."""
        rauw = self._gebufferd(
            "apps", f"core/applications/?superuser_full_list=true&page_size={PAGINA}")
        bindingen = self._bindingen()
        uit = []
        for a in rauw:
            slug = a.get("slug") or ""
            rechten = bindingen.get(a.get("pk") or slug, {})
            uit.append(Applicatie(
                slug=slug,
                naam=a.get("name") or slug,
                url=a.get("meta_launch_url") or "",
                omschrijving=a.get("meta_description") or "",
                groepen=tuple(sorted(rechten.get("groepen", ()))),
                gebruikers=tuple(sorted(rechten.get("gebruikers", ())))))
        return sorted(uit, key=lambda a: a.slug)

    def _bindingen(self):
        """Per app-pk: welke groepen en welke losse gebruikers hem mogen zien.

        Een binding met `negate` sluit juist uit in plaats van toe te laten.
        Die komen bij ons niet voor, en zolang dat zo is slaan we ze over in
        plaats van ze verkeerd om te lezen.
        """
        rauw = self._gebufferd("bindingen", f"policies/bindings/?page_size={PAGINA}")
        uit = {}
        for b in rauw:
            if not b.get("enabled") or b.get("negate"):
                continue
            doel = b.get("target")
            if not doel:
                continue
            hok = uit.setdefault(doel, {"groepen": set(), "gebruikers": set()})
            groep = b.get("group_obj") or {}
            if groep.get("name"):
                hok["groepen"].add(groep["name"])
            gebruiker = b.get("user_obj") or {}
            if gebruiker.get("username"):
                hok["gebruikers"].add(gebruiker["username"])
        return uit

    # ---- Rechten ---------------------------------------------------------
    def groepen_van(self, gebruiker):
        """De groepen van een gebruiker. Onbekende gebruiker geeft niets."""
        naam = urllib.parse.quote(str(gebruiker or ""), safe="")
        if not naam:
            return set()
        rauw = self._ophaler(
            f"core/groups/?member_by_username={naam}&page_size={PAGINA}")
        return {g.get("name") for g in rauw if g.get("name")}

    def is_beheerder(self, gebruiker):
        """Superuser in Authentik ziet daar alles, dus hier ook."""
        naam = urllib.parse.quote(str(gebruiker or ""), safe="")
        if not naam:
            return False
        rauw = self._ophaler(
            f"core/groups/?member_by_username={naam}&is_superuser=true&page_size=1")
        return bool(rauw)

    def apps_voor(self, gebruiker):
        """De apps die deze gebruiker mag lezen.

        Gelijk aan wat hij op het portaal aan tegels ziet: lidmaatschap van een
        groep die aan de app gebonden is, of een binding op zijn eigen naam.
        """
        alles = self.applicaties()
        if self.is_beheerder(gebruiker):
            return alles
        groepen = self.groepen_van(gebruiker)
        return [a for a in alles
                if (groepen & set(a.groepen)) or gebruiker in a.gebruikers]
