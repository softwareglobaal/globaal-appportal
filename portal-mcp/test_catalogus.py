"""Tests voor de cataloog en de rechten.

Het gaat hier om precies een ding: dat niemand een app te zien krijgt die hij
op het portaal ook niet zou zien. De API wordt nagebootst, zodat de test geen
Authentik nodig heeft.
"""
import pytest

from catalogus import Authentik, Onbereikbaar

# Twee apps. 'hr' hangt aan een groep, 'boek' aan een persoon.
APPS = [
    {"pk": "pk-hr", "slug": "hr", "name": "HR-dashboard",
     "meta_launch_url": "https://hr.globaal.be", "meta_description": ""},
    {"pk": "pk-boek", "slug": "boek", "name": "Boek",
     "meta_launch_url": "", "meta_description": "Niet-vergunde constructies"},
]

BINDINGEN = [
    {"target": "pk-hr", "enabled": True, "negate": False,
     "group_obj": {"name": "hr"}, "user_obj": None},
    {"target": "pk-boek", "enabled": True, "negate": False,
     "group_obj": None, "user_obj": {"username": "mehdi"}},
    # Uitgezet en omgekeerd: allebei tellen niet mee als toegang.
    {"target": "pk-hr", "enabled": False, "negate": False,
     "group_obj": {"name": "uitgezet"}, "user_obj": None},
    {"target": "pk-hr", "enabled": True, "negate": True,
     "group_obj": {"name": "omgekeerd"}, "user_obj": None},
]


def maak(groepen_per_gebruiker, superusers=(), teller=None):
    """Een Authentik-client die uit deze vaste gegevens leest."""
    def ophaler(pad):
        if teller is not None:
            teller.append(pad)
        if pad.startswith("core/applications/"):
            return list(APPS)
        if pad.startswith("policies/bindings/"):
            return list(BINDINGEN)
        if pad.startswith("core/groups/"):
            naam = pad.split("member_by_username=")[1].split("&")[0]
            if "is_superuser=true" in pad:
                return [{"name": "authentik Admins"}] if naam in superusers else []
            return [{"name": g} for g in groepen_per_gebruiker.get(naam, ())]
        raise AssertionError(f"onverwacht pad: {pad}")

    return Authentik("https://auth.test", "token", ophaler=ophaler)


def slugs(apps):
    return sorted(a.slug for a in apps)


def test_groepslid_ziet_alleen_zijn_eigen_app():
    ak = maak({"joan": ["hr"]})
    assert slugs(ak.apps_voor("joan")) == ["hr"]


def test_binding_op_naam_telt_ook():
    ak = maak({"mehdi": []})
    assert slugs(ak.apps_voor("mehdi")) == ["boek"]


def test_zonder_groep_geen_enkele_app():
    ak = maak({"nieuw": []})
    assert ak.apps_voor("nieuw") == []


def test_onbekende_gebruiker_krijgt_niets():
    ak = maak({})
    assert ak.apps_voor("bestaat-niet") == []
    assert ak.apps_voor("") == []


def test_superuser_ziet_alles():
    ak = maak({"akadmin": []}, superusers=("akadmin",))
    assert slugs(ak.apps_voor("akadmin")) == ["boek", "hr"]


def test_uitgezette_en_omgekeerde_binding_geven_geen_toegang():
    ak = maak({"iemand": ["uitgezet", "omgekeerd"]})
    assert ak.apps_voor("iemand") == []


def test_cataloog_wordt_gebufferd_maar_rechten_niet():
    """De apps mogen uit de buffer komen, de groepen van een mens nooit.

    Anders blijft een ingetrokken groep geldig zolang de buffer staat.
    """
    paden = []
    ak = maak({"joan": ["hr"]}, teller=paden)
    ak.apps_voor("joan")
    ak.apps_voor("joan")
    assert sum(1 for p in paden if p.startswith("core/applications/")) == 1
    assert sum(1 for p in paden if p.startswith("policies/bindings/")) == 1
    assert sum(1 for p in paden if "member_by_username=joan" in p) == 4


def test_authentik_stuk_geeft_een_fout_en_niet_stilzwijgend_alles():
    def kapot(pad):
        raise Onbereikbaar("Authentik ligt eruit")

    ak = Authentik("https://auth.test", "token", ophaler=kapot)
    with pytest.raises(Onbereikbaar):
        ak.apps_voor("joan")


def test_app_zonder_binding_is_voor_niemand():
    """Een app die aan niets gebonden is, is geen open deur."""
    def ophaler(pad):
        if pad.startswith("core/applications/"):
            return [{"pk": "pk-los", "slug": "los", "name": "Losse app",
                     "meta_launch_url": "", "meta_description": ""}]
        if pad.startswith("policies/bindings/"):
            return []
        return []

    ak = Authentik("https://auth.test", "token", ophaler=ophaler)
    assert ak.apps_voor("joan") == []
