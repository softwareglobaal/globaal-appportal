"""De drie stukken gereedschap: welke apps, welke tabellen, en lezen.

Elke aanroep begint met dezelfde vraag: mag deze gebruiker deze app lezen? Dat
antwoord komt uit `catalogus.py` en dus uit Authentik. Pas daarna komt de
database in beeld, en ook dan nog met een riem om: de query draait in een READ
ONLY-transactie, onder de rol van precies die ene app.

**Waarom de rolwissel er is en de controle in de code niet genoeg is.** Je zou
kunnen nakijken of er in de SQL geen schema van een andere app voorkomt. Dat is
een controle op tekst, en op tekst kun je je vergissen: een functie, een view,
een subquery, een naam tussen aanhalingstekens. `SET LOCAL ROLE mcp_app_<app>`
legt de grens bij Postgres neer. Gaat er hier iets mis, dan volgt "permission
denied" in plaats van andermans data. Zie portal-mcp/genereer_rollen.py.
"""
from __future__ import annotations

import re

import bronnen

RIJEN_STANDAARD = 200
RIJEN_MAX = 1000
TIJDSLIMIET_MS = 15000

ROL_PATROON = re.compile(r"^mcp_app_[a-z0-9_]+$")
BEGIN_SELECT = re.compile(r"(?is)^\s*(select|with)\b")


class Geweigerd(ValueError):
    """Een verzoek dat we bewust niet uitvoeren; de tekst gaat naar Claude."""


def rolnaam(slug, categorieen=()):
    """De rolnaam uit bronnen.py, met een slot erop.

    De naam gaat letterlijk in een SET LOCAL ROLE en is dus niet te parametreren.
    Vandaar deze controle: alleen kleine letters, cijfers en liggende streepjes.
    """
    naam = bronnen.rolnaam(slug, categorieen)
    if not ROL_PATROON.match(naam):
        raise Geweigerd(f"Onbruikbare appnaam: {slug!r}")
    return naam


def valideer_sql(sql):
    """Een enkele SELECT. Schrijven gaat sowieso niet, maar zeg het duidelijk."""
    schoon = str(sql or "").strip().rstrip(";").strip()
    if not schoon:
        raise Geweigerd("sql is verplicht")
    if ";" in schoon:
        raise Geweigerd("Precies een statement toegestaan, dus geen puntkomma")
    if not BEGIN_SELECT.match(schoon):
        raise Geweigerd("Alleen SELECT (eventueel met WITH). Deze server leest, "
                        "hij schrijft niet.")
    return schoon


def _rijen_limiet(waarde):
    try:
        n = int(waarde) if waarde is not None else RIJEN_STANDAARD
    except (TypeError, ValueError):
        raise Geweigerd("rijen moet een getal zijn") from None
    return max(1, min(n, RIJEN_MAX))


TABELLEN_SQL = """
select table_schema, table_name
from information_schema.tables
where table_schema = any(%s)
order by table_schema, table_name
"""

KOLOMMEN_SQL = """
select table_schema, table_name, column_name, data_type, is_nullable
from information_schema.columns
where table_schema = any(%s)
order by table_schema, table_name, ordinal_position
"""


class Gereedschap:
    """Bindt de cataloog aan de database.

    `verbinding_maken()` levert een psycopg-verbinding met de rol `mcp_lezer`
    op de appportal-database. Die rol mag zelf niets; alles gaat via de rolwissel
    hieronder.
    """

    def __init__(self, cataloog, verbinding_maken):
        self._cataloog = cataloog
        self._verbinding_maken = verbinding_maken

    # ---- toegang ---------------------------------------------------------
    def _niveau_voor(self, gebruiker, schemas):
        """Welke gevoelige categorieen deze gebruiker in deze app mag zien."""
        aanwezig = set(bronnen.categorieen_in(schemas))
        if not aanwezig:
            return ()
        if self._cataloog.is_beheerder(gebruiker):
            return tuple(sorted(aanwezig))
        groepen = self._cataloog.groepen_van(gebruiker)
        return tuple(sorted(aanwezig & set(bronnen.categorieen_voor(groepen))))

    def _app_voor(self, gebruiker, slug):
        """De app, of een weigering die uitlegt waarom niet."""
        if not slug:
            raise Geweigerd("app is verplicht. Vraag eerst de tool `apps`.")
        toegestaan = {a.slug: a for a in self._cataloog.apps_voor(gebruiker)}
        app = toegestaan.get(slug)
        if app is None:
            raise Geweigerd(
                f"Je hebt geen toegang tot de app {slug!r}, of hij bestaat niet. "
                f"De tool `apps` laat zien wat je wel mag lezen.")
        bron = bronnen.bron_van(slug)
        if not bron.leesbaar:
            raise Geweigerd(
                f"De app {slug!r} is nog niet te lezen. {bron.reden}")
        return app, bron

    def _lees(self, slug, sql, params=(), limiet=RIJEN_MAX, niveau=()):
        """Voert een query uit onder de rol van deze app, alleen-lezen."""
        rol = rolnaam(slug, niveau)
        with self._verbinding_maken() as verbinding:
            with verbinding.cursor() as cur:
                cur.execute("begin read only")
                cur.execute(f"set local role {rol}")
                cur.execute(f"set local statement_timeout = {TIJDSLIMIET_MS}")
                cur.execute(sql, params)
                kolommen = [k.name for k in (cur.description or ())]
                rijen = cur.fetchmany(limiet)
                meer = cur.fetchone() is not None
        return kolommen, rijen, meer

    def _groepen_of_alles(self, gebruiker):
        """De groepen van de gebruiker; een beheerder telt als alle groepen."""
        if self._cataloog.is_beheerder(gebruiker):
            alle = set()
            for cat in bronnen.CATEGORIEEN.values():
                alle.update(cat["groepen"])
            return alle
        return self._cataloog.groepen_van(gebruiker)

    # ---- de tools --------------------------------------------------------
    def apps(self, gebruiker):
        """Alle apps die deze gebruiker mag lezen, en wat ervan leesbaar is."""
        toegestaan = self._cataloog.apps_voor(gebruiker)
        uit = [a.als_dict(bron=bronnen.bron_van(a.slug).als_dict())
               for a in toegestaan]
        telling = bronnen.overzicht(a.slug for a in toegestaan)
        return {
            "apps": uit,
            "samenvatting": {
                "toegang_tot": len(uit),
                "nu_leesbaar": telling[bronnen.GEDEELDE_DB],
                "staat_elders": telling[bronnen.ELDERS],
                "nog_niet_uitgezocht": telling[bronnen.ONBEKEND],
            },
            "toelichting": (
                "Toegang volgt Authentik: dit zijn de apps waarvan je ook de "
                "tegel op het portaal ziet. Wat niet leesbaar is, staat er met "
                "de reden bij en is niet weggelaten."),
        }

    def schema(self, gebruiker, slug):
        """De tabellen en kolommen van een app."""
        app, bron = self._app_voor(gebruiker, slug)
        lijst = list(bron.schemas)
        niveau = self._niveau_voor(gebruiker, lijst)
        _, rijen, _ = self._lees(slug, KOLOMMEN_SQL, (lijst,), niveau=niveau)
        tabellen = {}
        for s, t, kolom, soort, leeg_mag in rijen:
            tabellen.setdefault(f"{s}.{t}", []).append(
                {"kolom": kolom, "type": soort, "leeg_mag": leeg_mag == "YES"})
        return {
            "app": app.slug,
            "naam": app.naam,
            "schemas": lijst,
            "tabellen": [{"tabel": naam, "kolommen": k}
                         for naam, k in sorted(tabellen.items())],
            "aantal_tabellen": len(tabellen),
            "niet_zichtbaar": bronnen.ontbrekende_uitleg(
                lijst, self._groepen_of_alles(gebruiker)),
        }

    def query(self, gebruiker, slug, sql, rijen=None):
        """Een SELECT op de data van een app."""
        app, bron = self._app_voor(gebruiker, slug)
        schoon = valideer_sql(sql)
        limiet = _rijen_limiet(rijen)
        niveau = self._niveau_voor(gebruiker, list(bron.schemas))
        kolommen, data, meer = self._lees(slug, schoon, (), limiet, niveau)
        return {
            "app": app.slug,
            "kolommen": kolommen,
            "rijen": [list(r) for r in data],
            "aantal": len(data),
            "afgekapt": meer,
            "niet_zichtbaar": bronnen.ontbrekende_uitleg(
                list(bron.schemas), self._groepen_of_alles(gebruiker)),
            "toelichting": (
                f"Meer dan {limiet} rijen; verfijn de query of verhoog `rijen` "
                f"(maximaal {RIJEN_MAX})." if meer else ""),
        }
