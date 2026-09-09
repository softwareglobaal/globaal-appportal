"""Tests voor het gereedschap.

Twee soorten: of de poort dicht zit voor wie er niet in mag, en of de query
werkelijk onder de juiste rol en alleen-lezen draait. Dat laatste toetsen we op
de commando's die naar de database gaan, want dat is de plek waar het misgaat
als iemand later iets herschrijft.
"""
import pytest

import bronnen
from gereedschap import (RIJEN_MAX, Geweigerd, Gereedschap, rolnaam,
                         valideer_sql)


class NepCursor:
    def __init__(self, logboek, rijen):
        self.logboek = logboek
        self._rijen = list(rijen)
        self.description = [type("K", (), {"name": "a"})()]

    def execute(self, sql, params=None):
        self.logboek.append(" ".join(str(sql).split())[:60])

    def fetchmany(self, n):
        uit, self._rijen = self._rijen[:n], self._rijen[n:]
        return uit

    def fetchone(self):
        return self._rijen.pop(0) if self._rijen else None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class NepVerbinding:
    def __init__(self, logboek, rijen):
        self.logboek = logboek
        self.rijen = rijen

    def cursor(self):
        return NepCursor(self.logboek, self.rijen)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class NepCataloog:
    """Levert vaste apps; hr is leesbaar, staving staat elders."""

    def __init__(self, per_gebruiker, groepen=None, beheerders=()):
        self._per_gebruiker = per_gebruiker
        self._groepen = groepen or {}
        self._beheerders = set(beheerders)

    def apps_voor(self, gebruiker):
        return self._per_gebruiker.get(gebruiker, [])

    def groepen_van(self, gebruiker):
        return set(self._groepen.get(gebruiker, ()))

    def is_beheerder(self, gebruiker):
        return gebruiker in self._beheerders


class NepApp:
    def __init__(self, slug, naam):
        self.slug, self.naam = slug, naam

    def als_dict(self, bron=None):
        uit = {"app": self.slug, "naam": self.naam}
        if bron is not None:
            uit["bron"] = bron
        return uit


HR = NepApp("hr", "HR-dashboard")
STAVING = NepApp("staving", "Staving")
MEDEWERKERS = NepApp("medewerkers", "Organisatie")


def maak(rijen=(), gebruikers=None, groepen=None, beheerders=()):
    logboek = []
    cat = NepCataloog(gebruikers if gebruikers is not None
                      else {"joan": [HR, STAVING], "sufa": [MEDEWERKERS],
                            "petra": [MEDEWERKERS], "akadmin": [MEDEWERKERS]},
                      groepen=groepen or {"joan": ["hr"], "sufa": ["namenlijst"],
                                          "petra": ["hr"]},
                      beheerders=beheerders or ("akadmin",))
    g = Gereedschap(cat, lambda: NepVerbinding(logboek, rijen))
    return g, logboek


# ---- de poort -----------------------------------------------------------
def test_app_zonder_toegang_wordt_geweigerd():
    g, _ = maak()
    with pytest.raises(Geweigerd, match="geen toegang"):
        g.query("joan", "vermogen", "select 1")


def test_onbekende_gebruiker_komt_nergens_bij():
    g, _ = maak(gebruikers={})
    with pytest.raises(Geweigerd, match="geen toegang"):
        g.query("vreemdeling", "hr", "select 1")


def test_app_zonder_app_naam_wijst_naar_de_lijst():
    g, _ = maak()
    with pytest.raises(Geweigerd, match="apps"):
        g.query("joan", "", "select 1")


def test_app_die_elders_staat_geeft_de_reden_en_niet_de_data():
    """Toegang is niet hetzelfde als leesbaar; het verschil hoort uitgelegd."""
    g, logboek = maak()
    with pytest.raises(Geweigerd, match="Postgres op poort 5432"):
        g.query("joan", "staving", "select 1")
    assert logboek == []


# ---- de SQL -------------------------------------------------------------
@pytest.mark.parametrize("sql", [
    "delete from hr.medewerker",
    "update hr.medewerker set naam = 'x'",
    "insert into hr.medewerker values (1)",
    "drop table hr.medewerker",
    "",
])
def test_alleen_select(sql):
    with pytest.raises(Geweigerd):
        valideer_sql(sql)


def test_twee_statements_worden_geweigerd():
    with pytest.raises(Geweigerd, match="puntkomma"):
        valideer_sql("select 1; drop table hr.medewerker")


def test_select_en_with_mogen():
    assert valideer_sql("  SELECT 1;  ") == "SELECT 1"
    assert valideer_sql("with x as (select 1) select * from x").startswith("with")


def test_rolnaam_laat_geen_rare_tekens_door():
    assert rolnaam("angela-sr") == "mcp_app_angela_sr"
    with pytest.raises(Geweigerd):
        rolnaam("hr; drop role mcp_lezer")


# ---- de uitvoering ------------------------------------------------------
def test_query_draait_alleen_lezen_en_onder_de_rol_van_de_app():
    """joan zit in de groep hr, dus krijgt zij de personeelsrol van die app."""
    g, logboek = maak(rijen=[("x",)])
    g.query("joan", "hr", "select naam from hr.medewerker")
    assert logboek[0] == "begin read only"
    assert logboek[1] == "set local role mcp_app_hr_personeel"
    assert logboek[2].startswith("set local statement_timeout")
    assert "select naam from hr.medewerker" in logboek[3]


def test_zonder_de_hr_groep_geen_hr_tabellen():
    """Het hele schema hr is gevoelig; zonder die groep blijft de basisrol over.

    In de praktijk komt dit niet voor, want de app hr is in Authentik al aan
    hr, admin en manager gebonden. Het staat er voor het geval die binding ooit
    ruimer wordt: dan valt de bodem er niet uit.
    """
    g, logboek = maak(rijen=[("x",)],
                      gebruikers={"gast": [HR]}, groepen={"gast": ["iets"]})
    g.query("gast", "hr", "select 1")
    assert logboek[1] == "set local role mcp_app_hr"


def test_te_veel_rijen_wordt_gemeld_en_niet_stil_afgekapt():
    g, _ = maak(rijen=[(i,) for i in range(5)])
    uit = g.query("joan", "hr", "select 1", rijen=2)
    assert uit["aantal"] == 2
    assert uit["afgekapt"] is True
    assert "verfijn" in uit["toelichting"]


def test_rijenlimiet_blijft_binnen_het_maximum():
    g, _ = maak(rijen=[(i,) for i in range(3)])
    uit = g.query("joan", "hr", "select 1", rijen=99999)
    assert uit["afgekapt"] is False
    assert RIJEN_MAX == 1000


# ---- de lijst -----------------------------------------------------------
def test_apps_noemt_wie_je_bent():
    """Koppelt iemand per ongeluk als een collega, dan valt dit als eerste op."""
    g, _ = maak()
    uit = g.apps("joan")
    assert uit["ingelogd_als"] == "joan"
    assert "joan" in uit["toelichting"]


def test_apps_toont_ook_wat_niet_leesbaar_is():
    """Stil weglaten leest als 'bestaat niet'."""
    g, _ = maak()
    uit = g.apps("joan")
    slugs = [a["app"] for a in uit["apps"]]
    assert slugs == ["hr", "staving"]
    staving = next(a for a in uit["apps"] if a["app"] == "staving")
    assert staving["bron"]["soort"] == bronnen.ELDERS
    assert "reden" in staving["bron"]
    assert uit["samenvatting"] == {"toegang_tot": 2, "nu_leesbaar": 1,
                                   "staat_elders": 1, "nog_niet_uitgezocht": 0}


# ---- gevoelige tabellen -------------------------------------------------
def test_wie_alleen_de_tegel_mag_krijgt_de_basisrol():
    """sufa mag de Organisatie-tegel openen maar zit niet in hr of admin."""
    g, logboek = maak(rijen=[("x",)])
    g.query("sufa", "medewerkers", "select 1")
    assert logboek[1] == "set local role mcp_app_medewerkers"


def test_hr_groep_krijgt_de_personeelsrol():
    g, logboek = maak(rijen=[("x",)])
    g.query("petra", "medewerkers", "select 1")
    assert logboek[1] == "set local role mcp_app_medewerkers_personeel"


def test_beheerder_krijgt_alles():
    g, logboek = maak(rijen=[("x",)])
    g.query("akadmin", "medewerkers", "select 1")
    assert logboek[1] == "set local role mcp_app_medewerkers_financieel_personeel"


def test_verborgen_categorieen_worden_benoemd_en_niet_verzwegen():
    g, _ = maak(rijen=[("x",)])
    uit = g.query("sufa", "medewerkers", "select 1")
    tekst = " ".join(uit["niet_zichtbaar"])
    assert "personeelsgegevens" in tekst and "financiele" in tekst
    assert "hr" in tekst

    uit = g.query("akadmin", "medewerkers", "select 1")
    assert uit["niet_zichtbaar"] == []
