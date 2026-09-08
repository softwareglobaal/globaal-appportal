"""Tests voor de cataloog en de rechten.

Het gaat hier om precies een ding: dat niemand een app te zien krijgt die hij op
het portaal ook niet zou zien. De database wordt nagebootst, zodat de test geen
Postgres nodig heeft.

De vier gevallen die er echt toe doen staan onderaan: een uitgezette binding, een
omgekeerde binding, een app die aan een expressie-policy hangt en een app zonder
enkele binding. Bij die laatste twee weten we het niet, en dan is "niet leesbaar,
met een reden erbij" het enige goede antwoord.
"""
import pytest

from catalogus import (ONZEKER_GEEN_BINDING, ONZEKER_POLICY, Cataloog,
                       Onbereikbaar)

# pk, slug, naam, url, omschrijving
APPS = [
    ("pk-hr", "hr", "HR-dashboard", "https://hr.globaal.be", ""),
    ("pk-boek", "boek", "Boek", "", "Niet-vergunde constructies"),
    ("pk-slim", "slim", "Slimme app", "", ""),      # hangt aan een policy
    ("pk-los", "los", "Losse app", "", ""),         # heeft geen binding
]

# doel, groep, gebruiker, heeft_policy, enabled, negate
BINDINGEN = [
    ("pk-hr", "hr", None, False, True, False),
    ("pk-boek", None, "mehdi", False, True, False),
    ("pk-hr", "uitgezet", None, False, False, False),   # staat uit
    ("pk-hr", "omgekeerd", None, False, True, True),    # sluit juist uit
    ("pk-slim", None, None, True, True, False),         # expressie-policy
]


def maak(groepen_per_gebruiker, superusers=(), teller=None):
    """Een cataloog die uit deze vaste gegevens leest."""
    def uitvoerder(sql, params):
        if teller is not None:
            teller.append(sql.split()[1])
        if "authentik_core_application a\norder by" in sql:
            return list(APPS)
        if "authentik_policies_policybinding b" in sql:
            return list(BINDINGEN)
        if "authentik_core_user_groups" in sql:
            naam = params[0]
            rijen = [(g, False) for g in groepen_per_gebruiker.get(naam, ())]
            if naam in superusers:
                rijen.append(("authentik Admins", True))
            return rijen
        raise AssertionError(f"onverwachte query: {sql[:60]}")

    return Cataloog(uitvoerder)


def slugs(apps):
    return sorted(a.slug for a in apps)


def test_groepslid_ziet_alleen_zijn_eigen_app():
    assert slugs(maak({"joan": ["hr"]}).apps_voor("joan")) == ["hr"]


def test_binding_op_naam_telt_ook():
    assert slugs(maak({"mehdi": []}).apps_voor("mehdi")) == ["boek"]


def test_zonder_groep_geen_enkele_app():
    assert maak({"nieuw": []}).apps_voor("nieuw") == []


def test_onbekende_gebruiker_krijgt_niets():
    ak = maak({})
    assert ak.apps_voor("bestaat-niet") == []
    assert ak.apps_voor("") == []


def test_uitgezette_en_omgekeerde_binding_geven_geen_toegang():
    assert maak({"iemand": ["uitgezet", "omgekeerd"]}).apps_voor("iemand") == []


def test_superuser_ziet_alles_behalve_het_onzekere():
    """Ook een beheerder krijgt geen app waarvan we de rechten niet kennen."""
    apps = maak({"akadmin": []}, superusers=("akadmin",)).apps_voor("akadmin")
    assert slugs(apps) == ["boek", "hr"]


def test_app_met_expressie_policy_is_onzeker_en_niet_leesbaar():
    ak = maak({"joan": ["hr"]})
    slim = next(a for a in ak.applicaties() if a.slug == "slim")
    assert slim.onzeker == ONZEKER_POLICY
    assert "slim" not in slugs(ak.apps_voor("joan"))


def test_app_zonder_binding_is_onzeker_en_niet_leesbaar():
    """Geen binding is geen open deur, maar ook geen stilte."""
    ak = maak({"joan": ["hr"]})
    los = next(a for a in ak.applicaties() if a.slug == "los")
    assert los.onzeker == ONZEKER_GEEN_BINDING
    assert "los" not in slugs(ak.apps_voor("joan"))


def test_onzekere_apps_staan_wel_in_de_cataloog():
    """Stil overslaan leest als 'bestaat niet'; de reden hoort zichtbaar."""
    alles = maak({"joan": ["hr"]}).applicaties()
    assert slugs(alles) == ["boek", "hr", "los", "slim"]
    assert all(a.onzeker or a.slug in ("hr", "boek") for a in alles)


def test_cataloog_wordt_gebufferd_maar_rechten_niet():
    """De apps mogen uit de buffer komen, de groepen van een mens nooit.

    Anders blijft een ingetrokken groep geldig zolang de buffer staat.
    """
    paden = []
    ak = maak({"joan": ["hr"]}, teller=paden)
    ak.apps_voor("joan")
    ak.apps_voor("joan")
    assert paden.count("a.policybindingmodel_ptr_id::text") == 1  # apps
    assert paden.count("b.target_id::text") == 1                  # bindingen
    assert paden.count("g.name,") == 2                            # per aanroep


def test_database_stuk_geeft_een_fout_en_niet_stilzwijgend_alles():
    def kapot(sql, params):
        raise RuntimeError("verbinding geweigerd")

    with pytest.raises(Onbereikbaar):
        Cataloog(kapot).apps_voor("joan")


def test_als_dict_toont_de_reden():
    ak = maak({"joan": ["hr"]})
    los = next(a for a in ak.applicaties() if a.slug == "los")
    assert los.als_dict()["rechten_onzeker"] == ONZEKER_GEEN_BINDING
    hr = next(a for a in ak.applicaties() if a.slug == "hr")
    assert "rechten_onzeker" not in hr.als_dict()
