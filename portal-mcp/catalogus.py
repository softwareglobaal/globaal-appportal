"""Welke applicaties bestaan er, en wie mag welke lezen.

Authentik is hier de bron van waarheid, en dat is geen implementatiedetail maar
het hele beveiligingsmodel. Wie een tegel op het portaal niet mag zien, mag de
data van die app hier ook niet lezen. Er is bewust geen tweede lijst van rechten
die naast Authentik kan gaan staan en stilletjes kan verouderen.

**Waarom de database en niet de API.** De API kan dit niet zonder superuser. De
endpoint `core/applications/` toont een aanroeper alleen de apps die hij zelf
mag openen; `superuser_full_list` en `for_user` staan allebei achter
`request.user.is_superuser` (zie `/authentik/core/api/applications.py`). Voor het
lezen van een cataloog zou je dus een volledig admin-token in `.env` moeten
zetten, en dat token kan ook schrijven: gebruikers aanmaken, groepen wijzigen,
tokens uitgeven. Een leesrol op vier tabellen is veel kleiner. De prijs is dat we
aan het interne schema van Authentik vastzitten, en daarom staan de aannames
hieronder als controles in de code in plaats van in een commentaarregel.

**Wat we controleren in plaats van aannemen.** Vandaag geldt op dit platform:
geen enkele app-binding gebruikt een expressie-policy, en geen enkele app staat
zonder binding. Beide zijn geverifieerd (08-09-2026). Verandert dat, dan mag de
uitkomst niet stilzwijgend verschuiven: zo'n app krijgt `onzeker` mee met een
reden, verschijnt wel in de cataloog en wordt niet leesbaar. Raden naar de
verkeerde kant is hier het ergste wat er kan gebeuren.

De rechten worden bij elke aanroep opnieuw bepaald (kort gebufferd), niet in het
OAuth-token gebakken. Een token leeft twaalf uur; een ingetrokken groep moet
binnen een minuut werken, niet pas na twaalf uur.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

BUFFER_TTL = 60          # seconden dat de cataloog blijft staan

# Een binding telt alleen mee als hij aanstaat, niet omgekeerd is, en naar een
# groep of een persoon wijst. Een binding met een policy erin kunnen we niet
# nabootsen; die maakt de app onzeker (zie ONZEKER_POLICY).
APPS_SQL = """
select a.policybindingmodel_ptr_id::text as pk,
       a.slug, a.name, coalesce(a.meta_launch_url, '') as url,
       coalesce(a.meta_description, '') as omschrijving
from authentik_core_application a
order by a.slug
"""

BINDINGEN_SQL = """
select b.target_id::text as doel, g.name as groep, u.username as gebruiker,
       b.policy_id is not null as heeft_policy, b.enabled, b.negate
from authentik_policies_policybinding b
join authentik_core_application a
  on a.policybindingmodel_ptr_id = b.target_id
left join authentik_core_group g on g.group_uuid = b.group_id
left join authentik_core_user u on u.id = b.user_id
"""

GROEPEN_SQL = """
select g.name, g.is_superuser
from authentik_core_user u
join authentik_core_user_groups ug on ug.user_id = u.id
join authentik_core_group g on g.group_uuid = ug.group_id
where u.username = %s and u.is_active
"""

ONZEKER_POLICY = ("Deze app hangt aan een expressie-policy, en die kan deze "
                  "server niet nabootsen. Rechten daarom niet vast te stellen.")
ONZEKER_GEEN_BINDING = ("Deze app heeft geen enkele policy-binding. Of hij "
                        "daarmee voor iedereen of voor niemand open staat, "
                        "hangt af van een Authentik-instelling, dus we nemen "
                        "hier niets aan.")


class Onbereikbaar(RuntimeError):
    """De cataloog is niet te lezen. We weigeren dan alles, niet niets."""


@dataclass(frozen=True)
class Applicatie:
    """Een app zoals Authentik hem kent."""
    slug: str
    naam: str
    url: str
    omschrijving: str
    groepen: tuple = field(default=())      # groepen die hem mogen zien
    gebruikers: tuple = field(default=())   # losse personen, buiten een groep
    onzeker: str = ""                       # reden, of leeg als het klopt

    def als_dict(self, bron=None):
        uit = {"app": self.slug, "naam": self.naam,
               "url": self.url or None,
               "omschrijving": self.omschrijving or None}
        if self.onzeker:
            uit["rechten_onzeker"] = self.onzeker
        if bron is not None:
            uit["bron"] = bron
        return uit


class Cataloog:
    """Leest de applicaties en de rechten uit de Authentik-database.

    `uitvoerder(sql, params)` geeft een lijst tuples terug. In productie is dat
    een read-only verbinding met de rol `mcp_lezer`; in de tests een nabootsing,
    zodat dit bestand zonder Postgres te controleren is.
    """

    def __init__(self, uitvoerder, ttl=BUFFER_TTL):
        self._uitvoeren = uitvoerder
        self._ttl = ttl
        self._buffer = {}

    def _gebufferd(self, sleutel, sql, params=None):
        nu = time.time()
        gezet, waarde = self._buffer.get(sleutel, (0, None))
        if waarde is not None and nu - gezet < self._ttl:
            return waarde
        waarde = self._vraag(sql, params)
        self._buffer[sleutel] = (nu, waarde)
        return waarde

    def _vraag(self, sql, params=None):
        try:
            return list(self._uitvoeren(sql, params or ()))
        except Onbereikbaar:
            raise
        except Exception as e:
            raise Onbereikbaar(f"Cataloog niet te lezen: {e}") from e

    # ---- Cataloog --------------------------------------------------------
    def applicaties(self):
        """Alle apps die Authentik kent, met hun rechten en twijfels."""
        rijen = self._gebufferd("apps", APPS_SQL)
        rechten = self._rechten_per_app()
        uit = []
        for pk, slug, naam, url, omschrijving in rijen:
            hok = rechten.get(pk)
            if hok is None:
                uit.append(Applicatie(slug, naam, url, omschrijving,
                                      onzeker=ONZEKER_GEEN_BINDING))
                continue
            uit.append(Applicatie(
                slug=slug, naam=naam, url=url, omschrijving=omschrijving,
                groepen=tuple(sorted(hok["groepen"])),
                gebruikers=tuple(sorted(hok["gebruikers"])),
                onzeker=ONZEKER_POLICY if hok["policy"] else ""))
        return uit

    def _rechten_per_app(self):
        rijen = self._gebufferd("bindingen", BINDINGEN_SQL)
        uit = {}
        for doel, groep, gebruiker, heeft_policy, aan, omgekeerd in rijen:
            hok = uit.setdefault(doel, {"groepen": set(), "gebruikers": set(),
                                        "policy": False})
            if heeft_policy:
                # Ook een uitgezette policy-binding laten we meetellen als
                # twijfel: we weten niet wat er bedoeld is, dus we raden niet.
                hok["policy"] = True
                continue
            if not aan or omgekeerd:
                continue
            if groep:
                hok["groepen"].add(groep)
            if gebruiker:
                hok["gebruikers"].add(gebruiker)
        return uit

    # ---- Rechten ---------------------------------------------------------
    def _groepsrijen(self, gebruiker):
        """Niet gebufferd: rechten van een mens moeten vers zijn."""
        if not gebruiker:
            return []
        return self._vraag(GROEPEN_SQL, (str(gebruiker),))

    def groepen_van(self, gebruiker):
        return {naam for naam, _ in self._groepsrijen(gebruiker)}

    def is_beheerder(self, gebruiker):
        """Superuser in Authentik ziet daar alles, dus hier ook."""
        return any(super_ for _, super_ in self._groepsrijen(gebruiker))

    def apps_voor(self, gebruiker):
        """De apps die deze gebruiker mag lezen.

        Gelijk aan wat hij op het portaal aan tegels ziet. Apps waarvan de
        rechten niet vast te stellen zijn vallen af, ook voor een beheerder:
        die horen thuis in de cataloog met hun reden, niet in een leesrecht.
        """
        rijen = self._groepsrijen(gebruiker)
        groepen = {naam for naam, _ in rijen}
        beheerder = any(super_ for _, super_ in rijen)
        uit = []
        for app in self.applicaties():
            if app.onzeker:
                continue
            if beheerder or (groepen & set(app.groepen)) \
                    or gebruiker in app.gebruikers:
                uit.append(app)
        return uit
