"""A48: een goedgekeurd advies zonder runbook blijft voor handmatige uitvoering staan."""
import importlib.util
import os
import sys

RUNNER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_thuis = os.environ.get("HOME")
os.environ["HOME"] = os.path.join(RUNNER, ".niet-bestaande-proef-thuis")
spec = importlib.util.spec_from_file_location("uitvoerder_proef", os.path.join(RUNNER, "mijnagents_uitvoerder.py"))
U = importlib.util.module_from_spec(spec)
spec.loader.exec_module(U)
if _thuis is None:
    os.environ.pop("HOME", None)
else:
    os.environ["HOME"] = _thuis


def test_a48_leeg_runbook_blijft_goedgekeurd_andere_loopt():
    oud_api, oud_token, oud_runboeken = U.api, U.TOKEN, U.RUNBOEKEN
    calls = []
    def api(pad, method="GET", payload=None):
        calls.append((pad, method, payload))
        if pad == "/api/uitvoer-wacht":
            return {"wacht": [{"id": 1, "naam": "zoom-wacht", "runbook": "", "parameters": '{"zoom_advies":"ZA-04"}'},
                              {"id": 2, "runbook": "pipedrive-dealtitel", "parameters": '{"proef":true}'}]}
        return {"ok": True}
    try:
        U.api, U.TOKEN = api, "proef"
        U.RUNBOEKEN = {"pipedrive-dealtitel": lambda p: ("proef uitgevoerd", "bewijs")}
        U.main()
        resultaten = [x for x in calls if x[0] == "/uitvoer-resultaat"]
        assert len(resultaten) == 1 and resultaten[0][2]["id"] == 2
        assert resultaten[0][2]["uitvoering"] == "gelukt"
    finally:
        U.api, U.TOKEN, U.RUNBOEKEN = oud_api, oud_token, oud_runboeken


def test_za2_ander_voorstel_met_parameters_en_leeg_runbook_meldt_mislukt():
    oud_api, oud_token, oud_runboeken = U.api, U.TOKEN, U.RUNBOEKEN
    calls = []
    def api(pad, method="GET", payload=None):
        calls.append((pad, method, payload))
        if pad == "/api/uitvoer-wacht":
            return {"wacht": [{"id": 7, "naam": "regisseur", "runbook": "",
                              "parameters": '{"tekst":"verzonnen proef"}'}]}
        return {"ok": True}
    try:
        U.api, U.TOKEN, U.RUNBOEKEN = api, "proef", {}
        U.main()
        resultaten = [x[2] for x in calls if x[0] == "/uitvoer-resultaat"]
        assert len(resultaten) == 1 and resultaten[0]["id"] == 7
        assert resultaten[0]["uitvoering"] == "mislukt" and "allowlist" in resultaten[0]["detail"]
    finally:
        U.api, U.TOKEN, U.RUNBOEKEN = oud_api, oud_token, oud_runboeken


if __name__ == "__main__":
    test_a48_leeg_runbook_blijft_goedgekeurd_andere_loopt()
    test_za2_ander_voorstel_met_parameters_en_leeg_runbook_meldt_mislukt()
    print("2 goed, 0 fout")
