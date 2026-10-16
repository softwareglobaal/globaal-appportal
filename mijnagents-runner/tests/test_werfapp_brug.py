"""Brug proef -> werfapp: vertaling, één concept per bordrij, nooit overschrijven. Fictieve gegevens, geen netwerk."""
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType

import pytest

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER / "koppelingen"))
if "bord" not in sys.modules:
    nep = ModuleType("bord")
    nep.TOKEN = "nep"
    sys.modules["bord"] = nep
import werfapp  # noqa: E402

VERSLAG = {
    "dossier": "9999", "bezoek": "3", "soort_bezoek": "werfbezoek", "adres": "Proefstraat 1, 3000 Leuven", "datum": "2026-10-14",
    "verslagtype": "werfverslag", "status_nl": "Ruwbouw loopt.", "status_en": "", "volgend": "21 oktober, 9 uur",
    "aanwezigen": [{"rol": "aannemer", "firma": "Proef Bouw", "naam": "Piet Proef", "aanwezig": "ja"}, {"naam": " "}],
    "categorieen": [
        {"naam": "Ruwbouw", "punten": [
            {"nummer": "3.1", "titel": "Latei boven raam", "datum": "", "vlag": "dringend", "tekst_nl": "Latei ontbreekt.", "tekst_en": "",
             "verantwoordelijke": "aannemer", "fotos": ["IMG_0001.jpg", "dia 4", "IMG_0002.HEIC"]},
            {"nummer": "3.2", "titel": "Spouw", "datum": "2026-10-13", "vlag": "ok", "tekst_nl": "In orde.", "tekst_en": "Fine.",
             "verantwoordelijke": "", "fotos": []}]}],
    "acties": [{"wie": "aannemer", "wat": "Latei plaatsen", "tegen": "volgend bezoek"}, {"wie": "x", "wat": " "}],
}
FOTOS = [{"naam": "IMG_0001.jpg", "pad": "/Work All/proef/bezoek/fotos/IMG_0001.jpg"},
         {"naam": "IMG_0002.HEIC", "pad": "/Work All/proef/bezoek/fotos/IMG_0002.HEIC"}]
RIJ = {"id": 47, "dossier": "9999", "datum": "2026-10-14", "adres": "Proefstraat 1, 3000 Leuven", "bezoekmap": "/Work All/proef/bezoek"}


def test_punten_worden_opmerkingen_met_eigen_fotos_en_open_status():
    body = werfapp.payload(VERSLAG, RIJ, FOTOS, proef_pad="/Work All/proef/bezoek/9999-3 werfverslag (concept).docx")
    assert body["project"] == "9999" and body["volgnummer"] == 3 and body["door"] == "werfverslag-schrijver"
    latei, spouw, actie = body["opmerkingen"]
    assert latei["categorie"] == "Ruwbouw" and latei["status"] is None and latei["tags"] == ["Dringend"]
    assert latei["verantwoordelijken"] == ["aannemer"] and latei["datum"] == "2026-10-14"
    assert latei["fotos"] == ["/Work All/proef/bezoek/fotos/IMG_0001.jpg"]   # geen dia, geen HEIC
    assert spouw["status"] == "OK" and spouw["omschrijving"] == "In orde.\n\nFine." and spouw["datum"] == "2026-10-13"
    assert actie == {"categorie": "Actiepunten", "titel": "Latei plaatsen", "status": None, "omschrijving": "Tegen: volgend bezoek",
                     "verantwoordelijken": ["aannemer"], "tags": [], "fotos": []}
    assert body["aanwezigen"] == [{"naam": "Piet Proef", "rol": "aannemer", "firma": "Proef Bouw", "aanwezig": True}]
    assert body["inleiding"] == "Volgend werfbezoek: 21 oktober, 9 uur"
    assert body["bron"]["soort"] == "werfverslag-proef" and body["bron"]["detail"]["bordrij"] == 47
    assert body["bron"]["detail"]["fotos_niet_gevonden"] == ["IMG_0002.HEIC", "dia 4"]
    assert "bezoek_id" not in body  # zonder registratie geen koppeling


def test_bezoek_id_alleen_uit_een_registratie_van_hetzelfde_project():
    goed = dict(RIJ, registratie={"bezoek_id": "b-1", "project_ref": "h-architects:9999"})
    assert werfapp.payload(VERSLAG, goed, FOTOS)["bezoek_id"] == "b-1"
    fout = dict(RIJ, registratie={"bezoek_id": "b-2", "project_ref": "h-architects:1234"})
    assert "bezoek_id" not in werfapp.payload(VERSLAG, fout, FOTOS)


def test_vast_punt_is_herkenbaar_en_geen_waarneming():
    v = dict(VERSLAG, categorieen=[{"naam": "Algemeen", "punten": [{"titel": "Werfbezoeken", "tekst_nl": "Kantoortekst", "doorlopend": True}]}], acties=[])
    (o,) = werfapp.opmerkingen(v, [])
    assert o["tags"] == ["Vast punt"] and o["status"] is None


REG = dict(RIJ, registratie={"bezoek_id": "b-1", "project_ref": "h-architects:9999"})


@pytest.fixture(autouse=True)
def schone_cache(monkeypatch):
    monkeypatch.delenv("WERFAPP_URL", raising=False)
    monkeypatch.setattr(werfapp, "_KAN", {})


def nep(antwoorden, gezien):
    """Een werfapp zonder netwerk: antwoorden[(methode, pad)] is een dict of een WerfappFout."""
    def call(pad, payload=None, method=None):
        sleutel = ("POST" if payload is not None else "GET", pad)
        gezien.append(sleutel)
        uit = antwoorden.get(sleutel)
        if isinstance(uit, Exception):
            raise uit
        if uit is None:
            pytest.fail(f"onverwachte aanroep {sleutel}")
        return uit
    return call


def test_plaatsbezoek_krijgt_geen_werfverslagnummer(monkeypatch):
    monkeypatch.setattr(werfapp, "call", lambda *a, **k: pytest.fail("geen aanroep verwacht"))
    for v in (dict(VERSLAG, bezoek="PB2", soort_bezoek="plaatsbezoek"), dict(VERSLAG, bezoek="0")):
        with pytest.raises(werfapp.WerfappFout, match="plaatsbezoek"):
            werfapp.concept(v, REG, FOTOS)
    assert "volgnummer" not in werfapp.payload(dict(VERSLAG, bezoek="PB2"), RIJ, FOTOS)


def test_zonder_vast_bezoek_of_tegen_een_oude_werfapp_niets(monkeypatch):
    gezien = []
    monkeypatch.setattr(werfapp, "call", nep({("GET", "/"): {"versie": 1}}, gezien))
    with pytest.raises(werfapp.WerfappFout, match="geen vast bezoek"):
        werfapp.concept(VERSLAG, RIJ, FOTOS)                        # CX4-1: geen registratie, geen aanroep
    assert gezien == []
    with pytest.raises(werfapp.WerfappFout, match="oudere versie"):
        werfapp.concept(VERSLAG, REG, FOTOS)                        # CX4-11: werfapp zonder bezoek_koppeling
    assert gezien == [("GET", "/")]


def test_herhaling_geeft_hetzelfde_concept_en_een_antwoord_zonder_koppeling_is_fout(monkeypatch):
    gezien = []
    ok = {("GET", "/"): {"bezoek_koppeling": 1}, ("GET", "/projecten/9999"): {"nummer": "9999"},
          ("POST", "/verslagen"): {"ok": True, "id": 12, "nummer": "9999-3", "url": "/verslag/12/bewerken", "bestond": True}}
    monkeypatch.setattr(werfapp, "call", nep(ok, gezien))
    r = werfapp.concept(VERSLAG, REG, FOTOS)
    assert r["id"] == 12 and r["nieuw"] is False and r["url"] == "https://werf.globaal.be/verslag/12/bewerken"
    zonder = dict(ok)
    zonder[("POST", "/verslagen")] = {"ok": True, "id": 13, "nummer": "9999-3", "url": "/x"}
    monkeypatch.setattr(werfapp, "call", nep(zonder, gezien))
    with pytest.raises(werfapp.WerfappFout, match="geen bezoekkoppeling"):
        werfapp.concept(VERSLAG, REG, FOTOS)


def test_nummer_bezet_maakt_niets_en_project_wordt_aangemaakt(monkeypatch):
    gezien, bestaat = [], []

    def call(pad, payload=None, method=None):
        gezien.append(("POST" if payload is not None else "GET", pad))
        if pad == "/":
            return {"bezoek_koppeling": 1}
        if pad == "/projecten/9999":
            if not bestaat:
                raise werfapp.WerfappFout(404, "onbekend project")
            return {"nummer": "9999"}
        if pad == "/projecten":
            bestaat.append(payload)
            return {"ok": True, "id": 1}
        if pad == "/verslagen":
            raise werfapp.WerfappFout(409, "verslag 9999-3 bestaat al")
        pytest.fail(pad)

    monkeypatch.setattr(werfapp, "call", call)
    with pytest.raises(werfapp.WerfappFout, match="niets aangemaakt") as ex:
        werfapp.concept(VERSLAG, REG, FOTOS)
    assert ex.value.status == 409 and bestaat == [{"nummer": "9999", "naam": "Proefstraat 1, 3000 Leuven"}]
    assert gezien == [("GET", "/"), ("GET", "/projecten/9999"), ("POST", "/projecten"), ("GET", "/projecten/9999"), ("POST", "/verslagen")]


def test_html_of_omleiding_wordt_een_werfappfout(monkeypatch):
    import io
    import urllib.error

    class Antwoord(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def __init__(self, gedrag):
            self.gedrag = gedrag

        def open(self, req, timeout=None):
            return self.gedrag(req)

    def html(req):
        return Antwoord(b"<html>login</html>")

    def omleiding(req):
        raise urllib.error.HTTPError(req.full_url, 302, "Found", {}, io.BytesIO(b""))

    def weg(req):
        raise ConnectionResetError("verbroken")

    for gedrag, status in ((html, 0), (omleiding, 302), (weg, 0)):
        monkeypatch.setattr(werfapp.urllib.request, "build_opener", lambda *a, g=gedrag: Opener(g))
        with pytest.raises(werfapp.WerfappFout) as ex:
            werfapp.call("/projecten/9999")
        assert ex.value.status == status


@pytest.mark.parametrize("url,goed", [("https://werf.globaal.be", True), ("https://werf.globaal.be/", True), ("http://127.0.0.1:3025", True),
                                      ("http://werf.globaal.be", False), ("https://werf.globaal.be.elders.example", False),
                                      ("https://elders.example", False), ("http://127.0.0.1:@elders.example", False),
                                      ("http://127.0.0.1:3025@elders.example", False)])
def test_token_gaat_alleen_naar_de_exacte_werfapp(monkeypatch, url, goed):
    monkeypatch.setenv("WERFAPP_URL", url)
    if goed:
        assert werfapp.basis() in ("https://werf.globaal.be", "http://127.0.0.1:3025")
    else:
        with pytest.raises(werfapp.WerfappFout, match="alleen op"):
            werfapp.basis()


def test_ketentest_tegen_de_echte_werfapp():
    """Los proces met de werfapp-testclient en een tijdelijke databank (test_app zet WERF_DATA in een tempmap)."""
    backend = Path(os.environ.get("WERFAPP_BACKEND") or HIER.parents[1] / "globaal-werfverslag")
    python = backend / ".venv/bin/python"
    if not python.exists():
        pytest.skip("ketentest vraagt de naastgelegen werfapp-testvenv")
    script = r'''
import importlib.util, os, sys, tempfile
from pathlib import Path
from types import ModuleType
backend, runner = map(Path, sys.argv[1:])
sys.path.insert(0, str(backend)); sys.path.insert(0, str(backend / 'tests'))
import test_app
assert os.environ['WERF_DATA'].startswith(tempfile.gettempdir()), 'nooit op echte data'
from app.main import app
from app import db
bord = ModuleType('bord'); bord.TOKEN = os.environ['AGENTS_TOKEN']; sys.modules['bord'] = bord
spec = importlib.util.spec_from_file_location('werfapp', runner / 'koppelingen/werfapp.py')
werfapp = importlib.util.module_from_spec(spec); spec.loader.exec_module(werfapp)
import json
def call(pad, payload=None, method=None):
    with app.test_client() as c:
        kop = {'X-Agents-Token': bord.TOKEN}
        r = c.post('/api/v1' + pad, json=payload, headers=kop) if payload is not None else c.get('/api/v1' + pad, headers=kop)
        if r.status_code >= 400:
            raise werfapp.WerfappFout(r.status_code, (r.json or {}).get('fout', ''))
        return r.json
werfapp.call = call
werfapp.basis = lambda: 'https://werf.globaal.be'
sys.path.insert(0, str(runner / 'tests'))
from test_werfapp_brug import VERSLAG, FOTOS, RIJ
from test_werfbezoek import Api, bezoek
with app.test_client() as c:
    b = bezoek(Api(c, 'commandocentrum', ['h-architects:9999']), 'h-architects:9999')
    ander = bezoek(Api(c, 'commandocentrum', ['h-architects:9999']), 'h-architects:9999')
try:                                                # zonder vast bezoek: niets
    werfapp.concept(VERSLAG, RIJ, FOTOS)
    raise SystemExit('concept zonder bezoek aanvaard')
except werfapp.WerfappFout as ex:
    assert 'geen vast bezoek' in ex.fout
assert db.q1('SELECT COUNT(*) n FROM verslag')['n'] == 0
RIJ = dict(RIJ, registratie={'bezoek_id': b['bezoek_id'], 'project_ref': 'h-architects:9999'})
eerste = werfapp.concept(VERSLAG, RIJ, FOTOS, proef_pad='/Work All/proef/bezoek/9999-3 werfverslag (concept).docx')
assert eerste['nieuw'] and eerste['project_nieuw'] and eerste['nummer'] == '9999-3', eerste
assert eerste['url'] == f"https://werf.globaal.be/verslag/{eerste['id']}/bewerken"
assert eerste['fotos_niet_gevonden'] == ['IMG_0002.HEIC', 'dia 4']
verloren = werfapp.concept(VERSLAG, RIJ, FOTOS)     # tweede klik of verloren antwoord: hetzelfde bezoek, hetzelfde concept
assert verloren['id'] == eerste['id'] and not verloren['nieuw'], verloren
nr = dict(VERSLAG, bezoek='4')                      # ook als het bezoeknummer intussen veranderde (CX4-1)
assert werfapp.concept(nr, RIJ, FOTOS)['id'] == eerste['id']
assert db.q1('SELECT COUNT(*) n FROM verslag')['n'] == 1
assert db.q1('SELECT bezoek_id FROM verslag WHERE id=?', (eerste['id'],))['bezoek_id'] == b['bezoek_id']
v = db.q1('SELECT * FROM verslag WHERE id=?', (eerste['id'],))
assert v['historisch'] == 0 and v['verzonden'] == '[]' and v['gemaakt_door'] == 'werfverslag-schrijver'
opm = db.rijen(db.q('SELECT nr, categorie, status, tags, nakijken FROM opmerking WHERE verslag_id=? ORDER BY positie', (eerste['id'],)))
assert [o['nr'] for o in opm] == ['3.1', '3.2', '3.3'] and opm[0]['status'] is None and opm[1]['status'] == 'OK', opm
assert json.loads(opm[0]['tags']) == ['Dringend'] and all(o['nakijken'] == 1 for o in opm)
assert db.q1("SELECT COUNT(*) n FROM foto WHERE verslag_id=? AND dropbox_pad LIKE '%IMG_0001.jpg'", (eerste['id'],))['n'] == 1
assert db.q1('SELECT COUNT(*) n FROM werfbezoek_bron WHERE verslag_id=?', (eerste['id'],))['n'] == 1
try:                                                # een ander bezoek dat hetzelfde nummer vraagt: niets aangemaakt
    werfapp.concept(VERSLAG, dict(RIJ, registratie={'bezoek_id': ander['bezoek_id'], 'project_ref': 'h-architects:9999'}), FOTOS)
    raise SystemExit('tweede concept met hetzelfde nummer werd aanvaard')
except werfapp.WerfappFout as ex:
    assert ex.status == 409
assert db.q1('SELECT COUNT(*) n FROM verslag')['n'] == 1
print('brug: één concept 9999-3 met drie opmerkingen, eigen foto, bron; geen tweede bij herhaling')
'''
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "DYLD_LIBRARY_PATH": "/opt/homebrew/lib"}
    r = subprocess.run([str(python), "-c", script, str(backend), str(HIER)], cwd=backend, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "één concept 9999-3" in r.stdout
