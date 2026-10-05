"""Werkelijke nummerroutes blijven gesloten bij een onvolledige bron of onduidelijke koppeling.

Alle bronnen zijn fictief. Geen netwerk, nummeraanvraag, overeenkomst of Pipedrive-schrijfactie.
"""
import io
import json
import os
import sys
import urllib.error

import pytest

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import contracten_agent as C
import pipedrive as P
import bronnen as B
import nummerlezer as N
import agenda_wacht as A
import fathom_wacht as F
import archivaris as AR


@pytest.fixture(autouse=True)
def fictieve_bronnen(monkeypatch):
    def verboden(*args, **kwargs):
        raise AssertionError("een live bron of schrijfactie werd aangeroepen")
    monkeypatch.setattr(P, "_vraag", verboden)
    monkeypatch.setattr(C.mcp, "call", verboden)
    monkeypatch.setattr(B, "_rpc", verboden)
    monkeypatch.setattr(P, "schrijf", verboden)
    monkeypatch.setattr(N, "jaar_nu_brussel", lambda: 2026)
    register = [
        {"code": "HARC", "code_agenda": "HA", "code_contact": "HA"},
        {"code": "UNAB", "code_agenda": "UB", "code_contact": "UN"},
        {"code": "TKNB", "code_agenda": "TK", "code_contact": "TK"},
    ]
    monkeypatch.setattr(N, "codes", lambda register_=None: N._bouw_codes(register))


def bronantwoord(aantal=0, rijen=None, **extra):
    return {"aantal": aantal, "dossiers": [] if rijen is None else rijen, **extra}


@pytest.mark.parametrize("antwoord", [None, {}, {"fout": "niet bereikbaar"},
    {"dossiers": []}, {"aantal": 0, "dossiers": None}, bronantwoord(True),
    bronantwoord(1, ["2603"]), bronantwoord(1), bronantwoord(0, [], volgende_offset=500)])
def test_misvormde_dashboardbron_geeft_geen_nummer(monkeypatch, antwoord):
    monkeypatch.setattr(B, "lijst", lambda *a, **kw: None)
    monkeypatch.setattr(C.mcp, "call", lambda *a, **kw: antwoord)
    with pytest.raises(C.NummerFout):
        C.volgend_vrij_nummer("architectuur", 2026)


def test_dashboardbron_boven_500_wordt_volledig_gelezen(monkeypatch):
    gevraagd = []
    def call(naam, **kw):
        gevraagd.append((naam, kw["offset"]))
        if naam == "voorbereidingen":
            return bronantwoord(1, [{"nummer": "2637"}])
        if kw["offset"] == 0:
            return bronantwoord(501, [{"project_nummer": "2601"}] * 500, offset=0, volgende_offset=500)
        return bronantwoord(501, [{"project_nummer": "2647"}], offset=500, volgende_offset=None)
    monkeypatch.setattr(B, "lijst", lambda *a, **kw: None)
    monkeypatch.setattr(C.mcp, "call", call)
    monkeypatch.setattr(P, "controleer_bedrijf", lambda firma, verwacht: verwacht)
    monkeypatch.setattr(P, "alles", lambda *a, **kw: [])
    assert C.volgend_vrij_nummer("architectuur", 2026) == "2648"
    assert gevraagd == [("dossiers", 0), ("dossiers", 500), ("voorbereidingen", 0)]


def test_onvolledige_voorbereidingen_blokkeert_nummer(monkeypatch):
    monkeypatch.setattr(B, "lijst", lambda *a, **kw: None)
    monkeypatch.setattr(C.mcp, "call", lambda naam, **kw: bronantwoord() if naam == "dossiers" else bronantwoord(2, [{"nummer": "2690"}]))
    with pytest.raises(C.NummerFout, match="voorbereidingen.*niet volledig"):
        C.volgend_vrij_nummer("architectuur", 2026)


@pytest.mark.parametrize("tweede", [bronantwoord(3, [{"nummer": "2690"}], offset=1),
    bronantwoord(2, [{"nummer": "2690"}], offset=0)])
def test_veranderde_telling_of_verkeerde_pagina_is_geen_volledige_bron(monkeypatch, tweede):
    def call(naam, **kw):
        return bronantwoord(2, [{"nummer": "2601"}], offset=0, volgende_offset=1) if kw["offset"] == 0 else tweede
    monkeypatch.setattr(C.mcp, "call", call)
    with pytest.raises(C.NummerFout, match="telling of paginapositie"):
        C.nummerbron_dashboard("dossiers")


@pytest.mark.parametrize("antwoord", [{"data": []}, {"data": [] , "additional_data": {"pagination": {}}},
    {"data": [], "additional_data": {"pagination": {"more_items_in_collection": "false"}}},
    {"data": [], "additional_data": {"pagination": {"more_items_in_collection": True, "next_start": 500}}},
    {"data": {"id": 1}, "additional_data": {"pagination": {"more_items_in_collection": False}}}])
def test_pipedrive_paginering_moet_volledigheid_aantonen(monkeypatch, antwoord):
    monkeypatch.setattr(P, "_vraag", lambda *a, **kw: antwoord)
    with pytest.raises(RuntimeError, match="niet volledig"):
        P.alles("harchitects", "/deals")


def test_startfase_leest_ook_een_deal_na_de_eerste_100(monkeypatch):
    gecontroleerd = []
    monkeypatch.setattr(P, "controleer_bedrijf", lambda f, v: gecontroleerd.append((f, v)))
    deals = [{"id": i, "pipeline_id": C.PIJPLIJN} for i in range(301)]
    def alles(firma, pad, params):
        assert params == {"status": "open", "stage_id": C.STARTFASE}
        return deals
    monkeypatch.setattr(P, "alles", alles)
    assert C.deals_in_startfase()[-1]["id"] == 300
    assert gecontroleerd == [("harchitects", 10068585)]


@pytest.mark.parametrize("route", [C.deals_in_startfase, A.deals_index, F.deals_index,
    lambda: C.verwerk({"id": 900001, "title": "2603 Fictief"}, "", {})])
def test_verkeerd_account_blokkeert_ook_een_bestaand_dossier(monkeypatch, route):
    def verkeerd(*args):
        raise RuntimeError("verkeerd bedrijf, verwacht 10068585")
    monkeypatch.setattr(P, "controleer_bedrijf", verkeerd)
    with pytest.raises(RuntimeError, match="10068585"):
        route()


def test_agendatitel_leest_nummercontext_en_bewaart_adres():
    for titel in ("[HA-KB] WB Teststraat 2611", "[HA-KB] WB Bespreking 2026", "[HA-KB] WB Klant, 2611 Wilrijk"):
        assert A.lees_titel(titel)["nummer"] == ""
    assert A.lees_titel("[TK-KB] ST 46118 - Fictief, Teststraat 1")["nummer"] == "46118"
    assert A.lees_titel("[HARC-KB] 2503 - Fictief")["nummer"] == "2503"


def deal(id_, nummer="2603", mails=(), delen=("fictieve", "klant")):
    return {"id": id_, "nummer": nummer, "mails": set(mails), "delen": set(delen)}


@pytest.mark.parametrize("code", ["TK", "UB", "ZZ"])
def test_andere_agendafirma_wordt_geen_h_a_deal(code):
    titel = f"[{code}-KB] ST 2603 - fictieve klant"
    assert A.koppel(A.lees_titel(titel), titel, [deal(1)])[0] is None
    assert F.koppel_deal({"title": titel, "calendar_invitees": [{"email": "klant@example.test"}]},
                         [deal(1, mails=["klant@example.test"])])[0] is None


def test_meerdere_h_a_deals_worden_niet_op_lijstvolgorde_gekozen():
    deals = [deal(1), deal(2)]
    titel = "[HA-KB] WB 2603 - fictieve klant"
    assert A.koppel(A.lees_titel(titel), titel, deals)[0] is None
    assert F.koppel_deal({"title": titel}, deals)[0] is None
    assert A.koppel(A.lees_titel("fictieve klant"), "fictieve klant", deals)[0] is None
    assert F.koppel_deal({"title": "fictieve klant"}, deals)[0] is None
    deals = [deal(1, "2603", ["klant@example.test"]), deal(2, "2612", ["klant@example.test"])]
    assert F.koppel_deal({"calendar_invitees": [{"email": "klant@example.test"}]}, deals)[0] is None
    assert F.koppel_deal({"title": "HA2612"}, deals)[0]["id"] == 2


def test_explicit_projectnummer_wordt_niet_vervangen_door_een_naam_of_mailmatch():
    deals = [deal(1, "2612", ["klant@example.test"])]
    titel = "[HA-KB] WB 2603 - fictieve klant"
    assert A.koppel(A.lees_titel(titel), titel, deals)[0] is None
    assert F.koppel_deal({"title": titel, "calendar_invitees": [{"email": "klant@example.test"}]}, deals)[0] is None
    assert F.koppel_deal({"title": "HA2603 en HA2612", "calendar_invitees": [{"email": "klant@example.test"}]}, deals)[0] is None


def test_onbekende_contractsoort_krijgt_geen_architectuurnummer():
    with pytest.raises(C.NummerFout, match="onbekende"):
        C.volgend_vrij_nummer("onbekend", 2026)


def test_toegekend_voorbereidingsnummer_blijft_zonder_nummer_in_de_dealtitel():
    voorbereiding = {"velden": {"project_nummer": "2603"}}
    assert C.nummer_van_voorbereiding(voorbereiding, "", 2026) == "2603"
    assert C.nummer_van_voorbereiding(voorbereiding, "2603", 2026) == "2603"
    with pytest.raises(C.NummerFout, match="wijkt af"):
        C.nummer_van_voorbereiding(voorbereiding, "2612", 2026)
    with pytest.raises(C.NummerFout, match="geen bevestigd"):
        C.nummer_van_voorbereiding({"velden": {"project_nummer": "46118"}}, "", 2026)


def test_verwerk_stelt_geen_tweede_nummer_voor_bij_een_bestaande_voorbereiding(monkeypatch):
    import bord
    class Record:
        def __init__(self, *args):
            self.record = {"run_id": "fictief"}
        def zet(self, **kwargs):
            return self
        def sluit(self, *args):
            return self
    def call(naam, **args):
        if naam == "voorbereiding":
            return {"velden": {"project_nummer": "2603"}, "soort": "addendum"}
        if naam == "dossiercontrole":
            return {}
        raise AssertionError("de droogproef mag niet schrijven")
    def geen_nieuw_nummer(*args, **kwargs):
        raise AssertionError("een bestaande voorbereiding werd opnieuw genummerd")
    def plan(*args):
        assert args[5] == ""
        return {"gegevens": [], "keuzes": {}}, 0, {}
    monkeypatch.setattr(C, "DROOG", True)
    monkeypatch.setattr(C, "VERS", True)
    monkeypatch.setattr(P, "controleer_bedrijf", lambda firma, verwacht: verwacht)
    monkeypatch.setattr(C.mcp, "call", call)
    monkeypatch.setattr(bord, "klaargezet_voor", lambda *a, **kw: [])
    monkeypatch.setattr(B, "verzamel", lambda *a: {"mails": []})
    monkeypatch.setattr(B, "samenvatting", lambda *a: "fictief")
    monkeypatch.setattr(C, "notities", lambda *a: [])
    monkeypatch.setattr(C, "veldenschema_voor", lambda *a: {})
    monkeypatch.setattr(C.hh, "RunRecord", Record)
    monkeypatch.setattr(C, "volgend_vrij_nummer", geen_nieuw_nummer)
    monkeypatch.setattr(C, "plan_met_model", plan)
    assert C.verwerk({"id": 900001, "title": "Fictief addendum"}, "", {})["droog"]


def test_archivaris_verliest_de_agendafirma_niet_bij_een_kaal_nummer():
    assert AR.ha_projectnummer({"nummer": "4437", "titel": "[TK-KB] ST 4437 - fictief"}, "") == ""
    assert AR.ha_projectnummer({"nummer": "2603", "titel": "[UB-KB] BS 2603 - fictief"}, "") == ""
    assert AR.ha_projectnummer({"nummer": "2603", "titel": "[HA-KB] WB 2603 - fictief"}, "") == "2603"
    assert AR.ha_projectnummer({"nummer": "2603", "titel": "[HA-KB] WB 2603 - fictief"}, "HA2612") == ""


@pytest.mark.parametrize("error,ontbreekt", [( {".tag": "path", "path": {".tag": "not_found"}}, True),
    ({".tag": "path", "path": {".tag": "no_permission"}}, False),
    ({".tag": "reset"}, False)])
def test_dropbox_409_is_alleen_bij_not_found_een_ontbrekende_map(monkeypatch, error, ontbreekt):
    # Gebruik de echte RPC-functie; vervang uitsluitend het HTTP-transport en de koppen.
    oorspronkelijke_rpc = fictieve_rpc
    body = io.BytesIO(json.dumps({"error": error}).encode())
    def http(*args, **kw):
        raise urllib.error.HTTPError("https://example.test", 409, "Conflict", {}, body)
    monkeypatch.setattr(B, "_koppen", lambda *args: {})
    monkeypatch.setattr(B.urllib.request, "urlopen", http)
    if ontbreekt:
        assert oorspronkelijke_rpc("files/list_folder", {"path": "/fictief"}) is None
    else:
        with pytest.raises(urllib.error.HTTPError):
            oorspronkelijke_rpc("files/list_folder", {"path": "/fictief"})


fictieve_rpc = B._rpc


def test_onbekende_dropbox_teamruimte_is_geen_ontbrekende_projectmap(monkeypatch):
    monkeypatch.setattr(B, "_toegang", lambda: "fictief")
    monkeypatch.setattr(B, "team_namespace", lambda: "")
    with pytest.raises(RuntimeError, match="teamruimte niet vastgesteld"):
        B._koppen()


@pytest.mark.parametrize("vervolg", [None, {}, {"entries": [], "has_more": "false"}])
def test_dropbox_onvolledige_vervolgpagina_is_geen_lege_map(monkeypatch, vervolg):
    antwoorden = iter([{"entries": [{"name": "2603.pdf"}], "has_more": True, "cursor": "fictief"}, vervolg])
    monkeypatch.setattr(B, "_rpc", lambda *a, **kw: next(antwoorden))
    with pytest.raises(RuntimeError, match="onvolledige"):
        B.lijst("/fictief", recursief=False)
