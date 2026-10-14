"""Regressies met echte functies en fictieve providers; geen sleutels, netwerk of dossierwrites."""
import ast
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import sys
import subprocess
from types import ModuleType, SimpleNamespace

import pytest

HIER = Path(__file__).resolve().parents[1]


class Agent:
    def __init__(self, *args):
        self.logs = []

    def log(self, *args, **kwargs):
        self.logs.append(args)

    def hartslag(self, *args, **kwargs):
        pass

    def log_verstuur(self):
        pass


def laad(naam, monkeypatch):
    tree = ast.parse((HIER / (naam + ".py")).read_text())
    # Importeer de echte functies, maar laad nooit echte .env-bestanden in tests.
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)
                                             and isinstance(n.value.func, ast.Name) and n.value.func.id == "_env")]
    module = ModuleType(naam)
    module.__file__ = str(HIER / (naam + ".py"))
    monkeypatch.setitem(sys.modules, naam, module)
    exec(compile(tree, module.__file__, "exec"), module.__dict__)
    return module


def gegevens(waarde="Proef BV"):
    return {"gegevens": [{"veld": "bouwheer", "waarde": waarde, "bron": "alinea 1", "zekerheid": "zeker"}],
            "situatie": "Eigen vaststelling.", "onderdelen": [], "acties": [], "ontbreekt": [], "verslagtype_voorstel": "werfverslag"}


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.syspath_prepend(str(HIER))
    monkeypatch.syspath_prepend(str(HIER / "koppelingen"))
    bord = ModuleType("bord")
    bord.Agent = Agent
    bronnen = ModuleType("bronnen")
    bronnen.lijst = lambda *args, **kwargs: []
    register = ModuleType("werfregister")
    cache, calls = {}, []

    def verwerk(*args):
        sleutel = json.dumps([args[0].get("id"), *args[3:11]], sort_keys=True, ensure_ascii=False)
        hergebruikt = sleutel in cache
        if not hergebruikt:
            out, usage = args[11]()
            cache[sleutel] = deepcopy(out)
            calls.append(args[3])
        else:
            usage = SimpleNamespace(input_tokens=0, output_tokens=0)
        usage.hergebruikt = hergebruikt
        usage.verwerking = {"id": sleutel[:20], "status": "hergebruikt" if hergebruikt else "gelukt"}
        return deepcopy(cache[sleutel]), usage

    register.verwerk = verwerk
    for n, m in (("bord", bord), ("bronnen", bronnen), ("werfregister", register)):
        monkeypatch.setitem(sys.modules, n, m)
    p = laad("werfverslag_proef", monkeypatch)
    p.vraag_gegevens = lambda *args, **kwargs: (gegevens(), SimpleNamespace(input_tokens=20, output_tokens=10))
    rij = {"id": 47, "dossier": "9999", "datum": "2026-10-14", "adres": "Proefstraat 1", "bezoekmap": "/proef/bezoek",
           "keuzes": {"bronnen": "eigen", "doorlopend": "nee"}, "bronnen": {"nr_label": "1"}, "gegevens": {}}
    writes = []
    bord.call = lambda pad, payload=None, **kwargs: {"rijen": [deepcopy(rij)]} if payload is None else writes.append((pad, payload)) or {"ok": True}
    return SimpleNamespace(p=p, bord=bord, bronnen=bronnen, register=register, calls=calls, rij=rij, writes=writes)


def test_volledige_segmenten_en_harde_bundelgrens(runtime):
    p = runtime.p
    teksten = [{"naam": f"bron{i}.txt", "tekst": "x" * 10000} for i in range(20)]
    with pytest.raises(p.extractie.BronLeesFout, match="boven de grens"):
        p.bronnenbundel(teksten)
    for t in teksten:
        seg = p.extractie.segmenten(t, 1777)
        assert "".join(s["tekst"] for s in seg) == t["tekst"]
        assert all(len(s["tekst"]) <= 1777 for s in seg)
        assert sum(s["tot"] - s["van"] for s in seg) == len(t["tekst"])


def test_sdk_herhaalt_geen_onzekere_betaalde_poging(runtime, monkeypatch):
    provider = ModuleType("anthropic")
    gezien = []
    client = object()
    def maak(**kwargs):
        gezien.append(kwargs)
        return client
    provider.Anthropic = maak
    monkeypatch.setitem(sys.modules, "anthropic", provider)
    assert runtime.p._client() is client
    assert gezien == [{"max_retries": 0, "timeout": 180}]


def test_pdf_leest_ook_pagina_na_twaalf_en_vraagt_ocr(runtime, monkeypatch):
    pdf = ModuleType("pypdf")
    pdf.PdfReader = lambda *args: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda i=i: f"tekst pagina {i}") for i in range(1, 14)])
    monkeypatch.setitem(sys.modules, "pypdf", pdf)
    assert "tekst pagina 13" in runtime.p.pdf_tekst(b"proef")
    pdf.PdfReader = lambda *args: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda: "")])
    with pytest.raises(runtime.p.extractie.BronLeesFout, match="OCR"):
        runtime.p.pdf_tekst(b"proef")


@pytest.mark.parametrize("stop,content", [("refusal", []), ("max_tokens", []), ("pause_turn", []), ("tool_use", []),
                                          ("tool_use", [SimpleNamespace(type="tool_use", name="gegevens", input={})]),
                                          ("tool_use", [SimpleNamespace(type="tool_use", name="gegevens", input=gegevens() | {"gegevens": "fout"})])])
def test_geen_refusal_leeg_of_ongeldig_toolresultaat(runtime, stop, content):
    usage = SimpleNamespace(input_tokens=100, output_tokens=7)
    resp = SimpleNamespace(stop_reason=stop, content=content, usage=usage)
    with pytest.raises(runtime.p.ModelAntwoordFout) as ex:
        runtime.p._tool(resp, runtime.p.GEGEVENS_SCHEMA)
    assert ex.value.usage.input_tokens == usage.input_tokens
    assert ex.value.usage.output_tokens == usage.output_tokens


def test_providerrequest_id_is_httpmetadata_en_geen_bericht_id(runtime):
    usage = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=17, cache_creation_input_tokens=3)
    resp = SimpleNamespace(id="msg_fictief", _request_id="req_fictief", usage=usage)
    gemeten = runtime.p._provider_usage(resp)
    assert gemeten.request_id == "req_fictief"
    assert gemeten.cache_read_input_tokens == 17
    assert gemeten.cache_creation_input_tokens == 3
    del resp._request_id
    assert runtime.p._provider_usage(resp).request_id is None


def test_model_mag_zichzelf_geen_menselijke_correctie_noemen(runtime):
    uit = gegevens()
    uit["gegevens"][0]["menselijk"] = True
    resp = SimpleNamespace(stop_reason="tool_use", content=[SimpleNamespace(type="tool_use", name="gegevens", input=uit)],
                           usage=SimpleNamespace(input_tokens=10, output_tokens=5))
    with pytest.raises(runtime.p.ModelAntwoordFout, match="onverwachte velden"):
        runtime.p._tool(resp, runtime.p.GEGEVENS_SCHEMA)


def test_ongewijzigde_bronnen_niet_opnieuw_betalen_en_delta(runtime):
    p, rij = runtime.p, runtime.rij
    tekst = {"naam": "transcript.txt", "pad": "/proef/transcript.txt", "tekst": "Brontekst ter plaatse."}
    p.lees_bezoekmap = lambda *args, **kwargs: ([tekst], [], [])
    een = p.voorbereid(Agent(), "9999", 1)
    twee = p.voorbereid(Agent(), "9999", 1)
    assert runtime.calls == ["bron-feiten"]
    assert twee["_verwerking"]["hergebruikt"] is True
    assert een["gegevens"] == twee["gegevens"]
    extra = tekst | {"naam": "00 verslag.md", "tekst": "Nieuwe waarneming."}
    p.lees_bezoekmap = lambda *args, **kwargs: ([tekst, extra], [], [])
    drie = p.voorbereid(Agent(), "9999", 1)
    assert runtime.calls == ["bron-feiten", "bron-feiten"]
    assert len(drie["dekking"]) == 2
    assert all(b["gelezen_tekens"] == b["tekens"] for b in drie["dekking"])


def test_onleesbare_bron_blokkeert_voor_eerste_betaalde_call(runtime):
    p = runtime.p
    p.lees_bezoekmap = lambda *args, **kwargs: ([{"naam": "ok.txt", "tekst": "gelezen"}, {"naam": "scan.pdf", "tekst": "", "leesfout": "OCR nodig"}], [], [])
    with pytest.raises(p.extractie.BronLeesFout, match="scan.pdf"):
        p.voorbereid(Agent(), "9999", 1)
    assert runtime.calls == []
    assert runtime.writes == []


def test_afgebroken_download_claimt_geen_volledige_hash(runtime):
    runtime.bronnen.lijst = lambda *args, **kwargs: [{".tag": "file", "name": "transcript.txt", "path_display": "/proef/transcript.txt", "size": 12}]
    downloads = []
    runtime.bronnen.download = lambda pad, **kwargs: downloads.append(kwargs) or b"half"
    tekst, _, _ = runtime.p.lees_bezoekmap("/proef", alleen_eigen=True)
    assert downloads == [{"maximum": 50_000_000}]
    assert "bronmetadata verwacht 12" in tekst[0]["leesfout"]
    assert "sha256" not in tekst[0]
    with pytest.raises(runtime.p.extractie.BronLeesFout):
        runtime.p._voorbereid_bronnen(Agent(), "9999", 1, runtime.rij, tekst, [], [])
    assert runtime.calls == []


def test_eigen_bronnen_en_menselijke_correctie_in_proef_zonder_hele_bundel(runtime, monkeypatch):
    p, rij = runtime.p, runtime.rij
    rij["gegevens"] = {"gegevens": [{"veld": "meerkosten", "waarde": "123 EUR", "bron": "factuur-derde.pdf", "zekerheid": "zeker"},
                                     {"veld": "bouwheer", "waarde": "Door Mehdi bevestigd", "bron": "Mehdi", "zekerheid": "zeker", "menselijk": True}]}
    raw = "VOLLEDIGE BRONTEKST DIE NIET OPNIEUW NAAR PROEF MAG"
    p.lees_bezoekmap = lambda *args, **kwargs: ([{"naam": "transcript.txt", "pad": "/proef/transcript.txt", "tekst": raw}], [], [])
    p.voorbereid(Agent(), "9999", 1)
    gezien = []

    def vraag(*args, **kwargs):
        gezien.append(args)
        return {"status_nl": "Eigen vaststelling", "status_en": "", "aanwezigen": [], "categorieen": [], "raming": [], "acties": [], "volgend": "", "akkoord": []}, SimpleNamespace(input_tokens=30, output_tokens=10)

    p.vraag_verslag = vraag
    monkeypatch.setattr(p.sjab, "naar_markdown", lambda *args: "# Concept")
    monkeypatch.setattr(p.sjab, "naar_docx", lambda *args: b"fictieve word")
    monkeypatch.setattr(p.sjab, "telling_open", lambda *args: {})
    p.bronnen.upload = lambda pad, data: pad
    p.proef(Agent(), "9999", 1)
    p.proef(Agent(), "9999", 1)
    assert runtime.calls == ["bron-feiten", "proef"]
    assert len(gezien) == 1
    bericht = json.dumps(gezien, ensure_ascii=False)
    assert raw not in bericht
    assert "factuur-derde.pdf" not in bericht
    assert "123 EUR" not in bericht
    assert "Door Mehdi bevestigd" in bericht


def test_conflicterende_bronnen_behouden_en_zichtbaar(runtime):
    uit = runtime.p.extractie.voeg_samen([gegevens("Firma A"), gegevens("Firma B")])
    assert {g["waarde"] for g in uit["gegevens"]} == {"Firma A", "Firma B"}
    assert all(g["zekerheid"] == "na te kijken" for g in uit["gegevens"])
    assert any("Tegenstrijdige" in t for t in uit["ontbreekt"])


def test_modelkeuze_laden_voor_import_met_shellvoorrang(runtime):
    p = runtime.p
    env = {}
    bestanden = {"~/agents/.env": 'WERFVERSLAG_MODEL="model-proef-agents"\n', "~/appportal/.env": "WERFVERSLAG_MODEL=model-proef-stack\n"}
    fake_os = SimpleNamespace(environ=env, path=SimpleNamespace(expanduser=lambda x: x, exists=lambda x: True))
    tree = ast.parse((HIER / "werfverslag_proef.py").read_text())
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_env"
             or isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name) and n.value.func.id == "_env"
             or isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODEL" for t in n.targets)]
    context = {"os": fake_os, "open": lambda pad, **kwargs: io.StringIO(bestanden[pad])}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "fictieve-config", "exec"), context)
    assert context["MODEL"] == "model-proef-agents"
    env["WERFVERSLAG_MODEL"] = "model-proef-shell"
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "fictieve-config", "exec"), context)
    assert context["MODEL"] == "model-proef-shell"
    model_line = next(n.lineno for n in nodes if isinstance(n, ast.Assign))
    bronnen_line = next(n.lineno for n in tree.body if isinstance(n, ast.Import) and any(a.name == "bronnen" for a in n.names))
    assert model_line < bronnen_line


def test_context_bewaren_gebruikt_exacte_rij_lease_en_hash(runtime):
    p = runtime.p
    opdracht = {"id": 81, "werfbezoek_id": 47, "invoer_hash": "fictieve-invoerhash", "soort": "voorbereid",
                "invoer": p._claim_invoer(runtime.rij, "voorbereid")}
    with p.opdrachtcontext(opdracht, "fictieve-lease"):
        assert p._rij("9999", 1)["id"] == 47
        p._bewaar(runtime.rij, "9999", 1, gegevens=gegevens())
    velden = runtime.writes[-1][1]["rijen"][0]
    assert velden["werfbezoek_id"] == 47
    assert velden["_opdracht_id"] == 81
    assert velden["_lease_token"] == "fictieve-lease"
    assert velden["_invoer_hash"] == "fictieve-invoerhash"


def test_gewijzigde_keuzes_blokkeren_voordat_provider_begint(runtime):
    p = runtime.p
    opdracht = {"id": 81, "werfbezoek_id": 47, "invoer_hash": "fictieve-invoerhash", "soort": "voorbereid",
                "invoer": p._claim_invoer(runtime.rij, "voorbereid")}
    runtime.rij["keuzes"] = {"bronnen": "alle"}
    with p.opdrachtcontext(opdracht, "fictieve-lease"), pytest.raises(p.extractie.BronLeesFout, match="gewijzigd"):
        p.voorbereid(Agent(), "9999", 1)
    assert runtime.calls == []


@pytest.mark.parametrize("bekend,status", [(True, "fout"), (False, "onbekend")])
def test_schrijver_fout_wordt_nooit_legacy_afgevinkt(runtime, monkeypatch, bekend, status):
    p, bord = runtime.p, runtime.bord
    taken = [{"id": 81, "werfbezoek_id": 47, "invoer_hash": "fictieve-hash", "soort": "voorbereid", "dossier": "9999", "volgnr": 1}]
    results = []

    def api(pad, payload=None, **kwargs):
        if pad.startswith("/api/werfopdrachten?"):
            return {"opdrachten": taken}
        if pad.endswith("/claim"):
            return {"geclaimd": True, "lease_token": "fictieve-lease", "opdracht": taken[0]}
        if pad.endswith("/resultaat"):
            results.append(payload)
            return {"ok": True}
        raise AssertionError(f"onverwachte route {pad}")

    bord.call = api
    bord.opgepakt = lambda *args: pytest.fail("legacy afvinken is geen geldige resultaatmelding")

    def fout(*args):
        if bekend:
            raise p.extractie.BronLeesFout("scan.pdf: OCR nodig")
        raise TimeoutError("fictieve provider-timeout")

    p.voorbereid = fout
    schrijver = laad("werfverslag_schrijver", monkeypatch)
    assert schrijver.opdrachten() == 0
    assert results[-1]["status"] == status
    assert results[-1]["veilig_opnieuw"] is bekend


def test_budget_is_uitgesteld_en_hervat_dezelfde_geautoriseerde_opdracht(runtime, monkeypatch):
    class WachtBudget(RuntimeError):
        veilig_opnieuw = True
        hervat_utc = "2026-10-15T10:00:00Z"

    runtime.register.WachtBudget = WachtBudget
    taak = {"id": 81, "werfbezoek_id": 47, "invoer_hash": "fictieve-hash", "soort": "voorbereid", "dossier": "9999", "volgnr": 1}
    meldingen = []

    def api(pad, payload=None, **kwargs):
        if payload is None:
            return {"opdrachten": [taak]}
        if pad.endswith("/claim"):
            return {"geclaimd": True, "lease_token": "fictieve-lease", "opdracht": taak}
        meldingen.append(payload)
        return {"ok": True}

    runtime.bord.call = api

    def wacht(*args):
        raise WachtBudget("budget bereikt; geen modelaanroep uitgevoerd")

    runtime.p.voorbereid = wacht
    schrijver = laad("werfverslag_schrijver", monkeypatch)
    assert schrijver.opdrachten() == 0
    assert meldingen[-1]["status"] == "uitgesteld"
    assert meldingen[-1]["veilig_opnieuw"] is True
    assert meldingen[-1]["hervat_utc"] == WachtBudget.hervat_utc


def test_geweigerde_claim_doet_geen_modelwerk(runtime, monkeypatch):
    taken = [{"id": 81, "soort": "voorbereid", "dossier": "9999", "volgnr": 1}]
    runtime.bord.call = lambda pad, payload=None, **kwargs: {"opdrachten": taken} if payload is None else {"geclaimd": False}
    runtime.p.voorbereid = lambda *args: pytest.fail("geen werk zonder exclusieve claim")
    schrijver = laad("werfverslag_schrijver", monkeypatch)
    assert schrijver.opdrachten() == 0


@pytest.mark.parametrize("argument,soort", [("--voorbereid", "voorbereid"), ("--proef", "proef")])
def test_cli_gebruikt_getypeerde_opdracht_in_plaats_van_betaalde_bypass(runtime, monkeypatch, argument, soort):
    verzoeken, opgehaald = [], []
    runtime.bord.call = lambda pad, payload: verzoeken.append((pad, payload)) or {"opdracht": {"id": 81, "status": "klaar"}}
    schrijver = laad("werfverslag_schrijver", monkeypatch)
    schrijver.opdrachten = lambda alleen_id=None: opgehaald.append(alleen_id) or 1
    runtime.p.voorbereid = runtime.p.proef = lambda *args: pytest.fail("CLI mag niet rechtstreeks een betaalde functie aanroepen")
    monkeypatch.setattr(sys, "argv", ["werfverslag_schrijver.py", argument, "9999", "1"])
    schrijver.main()
    assert verzoeken == [("/api/werfopdrachten/aanvragen", {"dossier": "9999", "volgnr": 1, "soort": soort, "bron": "commandline"})]
    assert opgehaald == [81]


def test_echte_registerclient_met_backendtestclient_en_cache_tussen_bezoeken():
    """Los proces voor de andere app-module; alle data en servicetokens zijn fictief."""
    backend = HIER.parents[1] / "globaal-werfverslag"
    python = backend / ".venv/bin/python"
    if not python.exists():
        pytest.skip("ketentest vraagt de naastgelegen werfapp-testvenv")
    script = r'''
import importlib.util, sys
from pathlib import Path
from types import SimpleNamespace
backend, runner = map(Path, sys.argv[1:])
sys.path.insert(0, str(backend))
sys.path.insert(0, str(backend / 'tests'))
import test_app
from app.main import app
from app import db
from test_werfbezoek import dienst
spec = importlib.util.spec_from_file_location('werkelijke_registerclient', runner / 'koppelingen/werfregister.py')
register = importlib.util.module_from_spec(spec)
spec.loader.exec_module(register)
kop = dienst('werf_schrijver', ['h-architects:9999'])
def call(pad, payload=None):
    with app.test_client() as client:
        response = client.post('/api/v1' + pad, json=payload, headers=kop)
        assert response.status_code in (200, 201), (response.status_code, response.json)
        return response.json
register.call = call
calls = []
def provider():
    calls.append(1)
    return {'gegevens': [{'veld': 'dak', 'waarde': 'eigen feit', 'bron': 'transcript.txt'}]}, SimpleNamespace(input_tokens=100, output_tokens=20)
rij = {'id': 47, 'dossier': '9999', 'bronnen': {'nr_label': '1'}}
manifest = [{'naam': 'transcript.txt', 'sha256': 'a' * 64, 'bytes': 100, 'soort': 'document'},
            {'naam': '1234 foto.jpg', 'beeldanalyse': 'niet uitgevoerd'},
            {'naam': 'opname.mp3', 'audioanalyse': 'niet uitgevoerd'}]
args = ('9999', 1, 'bron-feiten', {'bron': 'transcript.txt', 'tekst': 'dezelfde inhoud'},
        'claude-opus-5', 'bron-feiten-1', 'gegevens-1', 'nl', 'eigen', manifest, provider, 3000)
eerste, u1 = register.verwerk(rij, *args)
tweede, u2 = register.verwerk(rij, *args)
derde, u3 = register.verwerk(rij | {'id': 48}, *args)
assert eerste == tweede == derde
assert len(calls) == 1
assert not u1.hergebruikt and u2.hergebruikt and u3.hergebruikt
assert u2.input_tokens == u2.output_tokens == 0
assert db.q1("SELECT COUNT(*) n FROM verwerking WHERE taaktype='handmatig:bron-feiten'")['n'] == 1
assert db.q1('SELECT COUNT(*) n FROM bezoek')['n'] == 2
assert db.q1('SELECT COUNT(*) n FROM bron')['n'] == 1
assert db.q1("SELECT COUNT(*) n FROM bron_versie WHERE bewaring='geverifieerd'")['n'] == 0
print('echte registerclient: één betaalde fakeproviderstart, projectcache, geen mediahashclaim')
'''
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "DYLD_LIBRARY_PATH": "/opt/homebrew/lib"}
    resultaat = subprocess.run([str(python), "-c", script, str(backend), str(HIER)], cwd=backend, env=env, capture_output=True, text=True, timeout=60)
    assert resultaat.returncode == 0, resultaat.stdout + resultaat.stderr
    assert "één betaalde fakeproviderstart" in resultaat.stdout
