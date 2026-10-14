"""De echte adapter doorloopt de Flask-registry met fictieve providers; nooit netwerk/keys."""
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from datetime import datetime, timezone

PORTAL = Path(__file__).resolve().parents[2]
WERF = Path(os.environ.get("WERF_TEST_REPO", PORTAL.parent / "globaal-werfverslag"))
sys.path.insert(0, str(WERF / "tests"))
sys.path.insert(0, str(WERF))
from test_werfbezoek import Api, client, nieuw_project
from app import db

spec = importlib.util.spec_from_file_location("werfregister_keten", PORTAL / "mijnagents-runner/koppelingen/werfregister.py")
register = importlib.util.module_from_spec(spec)
spec.loader.exec_module(register)


def test_echte_adapter_reserveert_cache_en_delta(client, monkeypatch):
    project = nieuw_project()
    dossier = project.split(":")[1]
    api = Api(client, "werf_schrijver", [project])
    rij = {"id": 17, "dossier": dossier, "datum": "2026-10-14", "bronnen": {"nr_label": "1"}}
    calls = []

    def call(pad, payload=None):
        r = api.post(pad, payload) if payload is not None else api.get(pad)
        if r.status_code >= 400:
            raise register._http_fout(r.status_code, r.json)
        return r.json

    monkeypatch.setattr(register, "call", call)

    def provider():
        calls.append(1)
        return {"feit": "gemeten"}, SimpleNamespace(input_tokens=10, output_tokens=20)

    kwargs = (rij, dossier, 1, "bron-feiten", {"tekst": "volledig"}, "claude-opus-5", "v1", "s1", "nl", "eigen",
              [{"naam": "transcript.txt", "sha256": "d" * 64}], provider, 3000)
    a, u1 = register.verwerk(*kwargs)
    a["feit"] = "niet in de cache aanpassen"
    b, u2 = register.verwerk(*kwargs)
    assert b == {"feit": "gemeten"} and len(calls) == 1
    assert u1.hergebruikt is False and u2.hergebruikt is True and u2.input_tokens == u2.output_tokens == 0
    rij2 = {**rij, "id": 18, "bronnen": {"nr_label": "2"}}
    register.verwerk(rij2, *kwargs[1:])
    assert len(calls) == 1
    assert db.q1("SELECT COUNT(*) n FROM bezoek WHERE project_ref=?", (project,))["n"] == 2
    assert db.q1("SELECT COUNT(*) n FROM verwerking WHERE betaald=1 AND bezoek_id IN (SELECT bezoek_id FROM bezoek WHERE project_ref=?)", (project,))["n"] == 1
    nieuw = list(kwargs)
    nieuw[4] = {"tekst": "nieuwe inhoud"}
    nieuw[10] = [{"naam": "transcript.txt", "sha256": "e" * 64}]
    register.verwerk(*nieuw)
    assert len(calls) == 2


def test_download_geeft_nooit_stil_gedeeltelijke_bytes(monkeypatch):
    import ast
    import io
    import json
    import urllib.request
    pad = PORTAL / "mijnagents-runner/koppelingen/bronnen.py"
    boom = ast.parse(pad.read_text())
    functie = next(n for n in boom.body if isinstance(n, ast.FunctionDef) and n.name == "download")
    scope = {"urllib": SimpleNamespace(request=SimpleNamespace(Request=urllib.request.Request,
                           urlopen=lambda *a, **kw: io.BytesIO(b"123456"))),
             "INHOUD": "https://content.dropboxapi.com", "json": json, "_koppen": lambda x: x}
    exec(compile(ast.Module(body=[functie], type_ignores=[]), str(pad), "exec"), scope)
    try:
        scope["download"]("/fictief.txt", maximum=5)
        assert False, "gedeeltelijke bron is teruggegeven"
    except RuntimeError:
        pass
    assert scope["download"]("/fictief.txt", maximum=6) == b"123456"


def test_peerbron_wacht_zonder_onbekende_call_te_herhalen():
    gestart = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = {"code": "verwerking_onzeker", "details": {"status": "gestart", "fase": "bron-feiten", "gestart_utc": gestart}}
    ex = register._http_fout(409, body)
    assert isinstance(ex, register.WachtBron) and ex.veilig_opnieuw and ex.hervat_utc
    body["details"]["status"] = "onbekende_uitkomst"
    assert not isinstance(register._http_fout(409, body), register.WachtBudget)
    body["details"].update(status="gestart", gestart_utc="2020-01-01T00:00:00Z")
    assert not isinstance(register._http_fout(409, body), register.WachtBudget)
