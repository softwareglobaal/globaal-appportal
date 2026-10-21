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
    register.RegisterFout = type("RegisterFout", (RuntimeError,), {})
    register.registreer = lambda rij, d, n: {"bezoek_id": f"bezoek-{rij.get('id')}", "project_ref": f"h-architects:{d}"}
    werf = ModuleType("werfapp")  # nooit het netwerk op: de brug zelf zit in test_werfapp_brug.py

    class WerfappFout(RuntimeError):
        def __init__(self, status, fout):
            self.status, self.fout = status, fout
            super().__init__(fout)

    werf.WerfappFout, werf.concepten, werf.rijen = WerfappFout, [], []
    werf.concept = lambda verslag, rij, fotos, **kw: werf.concepten.append((verslag, kw)) or werf.rijen.append(rij) or {
        "id": 5, "nummer": f"{verslag['dossier']}-{verslag['bezoek']}", "url": "/verslag/5/bewerken", "nieuw": True, "project_nieuw": False}
    for n, m in (("bord", bord), ("bronnen", bronnen), ("werfregister", register), ("werfapp", werf)):
        monkeypatch.setitem(sys.modules, n, m)
    p = laad("werfverslag_proef", monkeypatch)
    p.vraag_gegevens = lambda *args, **kwargs: (gegevens(), SimpleNamespace(input_tokens=20, output_tokens=10))
    rij = {"id": 47, "dossier": "9999", "datum": "2026-10-14", "adres": "Proefstraat 1", "bezoekmap": "/proef/bezoek",
           "keuzes": {"bronnen": "eigen", "doorlopend": "nee"}, "bronnen": {"nr_label": "1"}, "gegevens": {}}
    writes = []
    bord.call = lambda pad, payload=None, **kwargs: {"rijen": [deepcopy(rij)]} if payload is None else writes.append((pad, payload)) or {"ok": True}
    return SimpleNamespace(p=p, bord=bord, bronnen=bronnen, register=register, werf=werf, calls=calls, rij=rij, writes=writes)


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
    # De proef gaat als concept naar de werfapp en de verwijzing staat op de bordrij.
    assert runtime.werf.concepten and runtime.werf.concepten[0][0]["bezoek"] == "1"
    assert runtime.werf.concepten[0][1] == {"proef_pad": "/proef/bezoek/9999-1 werfverslag (concept).docx", "bronnen": ["transcript.txt"]}
    assert runtime.werf.rijen[0]["registratie"] == {"bezoek_id": "bezoek-47", "project_ref": "h-architects:9999"}  # CX4-1: vers geregistreerd
    # CX4-4: de proef stond al op de bordrij vóór de brug draaide
    eerste = next(i for i, w in enumerate(runtime.writes) if w[1]["rijen"][0].get("proef_pad"))
    assert "werfapp" not in runtime.writes[eerste][1]["rijen"][0]["proef_info"]
    info = [w[1]["rijen"][0]["proef_info"] for w in runtime.writes if "proef_info" in w[1]["rijen"][0]][-1]
    assert info["werfapp"] == {"id": 5, "nummer": "9999-1", "url": "/verslag/5/bewerken", "nieuw": True}


def test_directe_proef_bewaart_gegevens_en_bijlagen_op_bezoekpagina(runtime, monkeypatch):
    p = runtime.p
    p.lees_bezoekmap = lambda *args, **kwargs: ([{"naam": "transcript.txt", "pad": "/proef/bezoek/transcript.txt",
                                                 "tekst": "Eigen vaststelling ter plaatse."}], [], [])
    p.vraag_verslag = lambda *args, **kwargs: ({"status_nl": "Ter plaatse", "status_en": "", "aanwezigen": [],
                                                "categorieen": [], "raming": [], "acties": [], "volgend": "", "akkoord": []},
                                               SimpleNamespace(input_tokens=30, output_tokens=10))
    monkeypatch.setattr(p.sjab, "naar_markdown", lambda *args: "# Concept")
    monkeypatch.setattr(p.sjab, "naar_docx", lambda *args: b"fictieve word")
    monkeypatch.setattr(p.sjab, "telling_open", lambda *args: {})
    p.bronnen.upload = lambda pad, data: pad
    p.proef(Agent(), "9999", 1)
    opgeslagen = [w[1]["rijen"][0] for w in runtime.writes if w[1]["rijen"][0].get("proef_pad")]
    assert opgeslagen and opgeslagen[0]["gegevens"]["gegevens"] == []  # eigen-modus vraagt geen klantgegevens
    assert opgeslagen[0]["bijlagen"][0]["naam"] == "transcript.txt"


def test_afgekapt_proefantwoord_krijgt_een_kleinere_geregistreerde_herhaling(runtime, monkeypatch):
    p = runtime.p
    p.lees_bezoekmap = lambda *args, **kwargs: ([{"naam": "transcript.txt", "pad": "/proef/bezoek/transcript.txt",
                                                 "tekst": "plaud_id: of_ffffffffffffffffffffffffffffffff\nEigen vaststelling."}], [], [])
    pogingen = []

    def vraag(*args, **kwargs):
        pogingen.append(kwargs["max_tokens"])
        if len(pogingen) == 1:
            antwoord = SimpleNamespace(stop_reason="max_tokens", usage=SimpleNamespace(input_tokens=50, output_tokens=8000))
            raise p.ModelAntwoordFout("afgekapt", antwoord)
        return {"status_nl": "Ter plaatse", "status_en": "", "aanwezigen": [], "categorieen": [],
                "raming": [], "acties": [], "volgend": "", "akkoord": []}, SimpleNamespace(input_tokens=25, output_tokens=100)

    p.vraag_verslag = vraag
    monkeypatch.setattr(p.sjab, "naar_markdown", lambda *args: "# Concept")
    monkeypatch.setattr(p.sjab, "naar_docx", lambda *args: b"word")
    monkeypatch.setattr(p.sjab, "telling_open", lambda *args: {})
    p.bronnen.upload = lambda pad, data: pad
    p.proef(Agent(), "9999", 1)
    assert pogingen == [8000, 4000]
    assert runtime.calls == ["bron-feiten", "proef"]
    info = [w[1]["rijen"][0]["proef_info"] for w in runtime.writes if "proef_info" in w[1]["rijen"][0]][-1]
    assert info["tokens"]["proef_pogingen"] == [{"in": 50, "uit": 8000}, {"in": 25, "uit": 100}]


def test_werfappfout_laat_de_proef_staan_en_noemt_de_reden(runtime, monkeypatch):
    p = runtime.p
    p.lees_bezoekmap = lambda *args, **kwargs: ([{"naam": "transcript.txt", "pad": "/proef/transcript.txt", "tekst": "eigen"}], [], [])
    p.vraag_verslag = lambda *args, **kwargs: ({"status_nl": "x", "status_en": "", "aanwezigen": [], "categorieen": [], "raming": [],
                                                 "acties": [], "volgend": "", "akkoord": []}, SimpleNamespace(input_tokens=1, output_tokens=1))
    monkeypatch.setattr(p.sjab, "naar_markdown", lambda *args: "# Concept")
    monkeypatch.setattr(p.sjab, "naar_docx", lambda *args: b"word")
    monkeypatch.setattr(p.sjab, "telling_open", lambda *args: {})
    p.bronnen.upload = lambda pad, data: pad

    def weigert(*args, **kwargs):
        raise runtime.werf.WerfappFout(409, "verslag 9999-1 bestaat al in de werfapp")

    runtime.werf.concept = weigert
    pad, _ = p.proef(Agent(), "9999", 1)
    assert pad.endswith(".docx")
    info = [w[1]["rijen"][0]["proef_info"] for w in runtime.writes if "proef_info" in w[1]["rijen"][0]][-1]
    assert info["werfapp"] == {"fout": "verslag 9999-1 bestaat al in de werfapp", "status": 409}
    # ook een onverwachte fout in de brug laat de betaalde proef staan
    runtime.werf.concept = lambda *a, **k: {}["stuk"]
    pad, _ = p.proef(Agent(), "9999", 1)
    info = [w[1]["rijen"][0]["proef_info"] for w in runtime.writes if "proef_info" in w[1]["rijen"][0]][-1]
    assert pad.endswith(".docx") and info["werfapp"]["status"] == -1 and "KeyError" in info["werfapp"]["fout"]


def test_bestaande_proef_naar_de_werfapp_zonder_claude(runtime):
    p, rij = runtime.p, runtime.rij
    verslag = {"dossier": "9999", "bezoek": "2", "soort_bezoek": "werfbezoek", "adres": "Proefstraat 1", "datum": "2026-10-14", "opgemaakt": "2026-10-15",
               "verslagtype": "werfverslag", "status_nl": "Ruwbouw", "aanwezigen": [], "acties": [], "akkoord": [], "volgend": "",
               "categorieen": [{"naam": "Algemeen", "punten": [{"nummer": "1.1", "titel": "Werfbezoeken", "tekst_nl": "Kantoortekst", "vlag": ""}]},
                               {"naam": "Ruwbouw", "punten": [{"nummer": "2.2", "titel": "Latei", "tekst_nl": "Ontbreekt", "vlag": "dringend", "fotos": ["a.jpg"]}]}]}
    with pytest.raises(RuntimeError, match="geen bewaarde proef"):
        p.werfapp_uit_proef(Agent(), "9999", 1)
    rij.update(verslag_md=p.sjab.naar_markdown(verslag), proef_pad="/proef/bezoek/9999-2 werfverslag (concept).docx", proef_info={"punten": 2})
    p.lees_bezoekmap = lambda *args, **kwargs: ([], [{"naam": "a.jpg", "pad": "/proef/bezoek/fotos/a.jpg"}], [])
    p.vraag_verslag = p.vraag_gegevens = lambda *a, **k: pytest.fail("geen modelaanroep: deze route kost geen tokens")
    uit = p.werfapp_uit_proef(Agent(), "9999", 1)
    assert uit["nummer"] == "9999-2" and runtime.calls == []
    (v, kw), = runtime.werf.concepten
    assert [pt["titel"] for c in v["categorieen"] for pt in c["punten"]] == ["Werfbezoeken", "Latei"]
    assert v["categorieen"][0]["punten"][0]["doorlopend"] is True and not v["categorieen"][1]["punten"][0].get("doorlopend")
    assert kw["proef_pad"].endswith(".docx")
    assert kw["bronnen"] == []   # een bestaande proef: de bronlijst stond niet in de markdown
    info = [w[1]["rijen"][0]["proef_info"] for w in runtime.writes if "proef_info" in w[1]["rijen"][0]][-1]
    assert info["punten"] == 2 and info["werfapp"]["nummer"] == "9999-2"


def test_eigen_tekst_alleen_de_naamvormen_van_mehdis_eigen_hulpmiddelen(runtime):
    """CX5-4: elke vorm die live voorkomt (synthetische titels), en wat van derden kan komen."""
    eigen = ["transcript.txt", "transcript.docx", "00 verslag.md", "00 fotos.md", "05-07 Vergadering_ dak en goten-transcript.txt",
             "06-24 Vergadering_ terras — afvoer-transcript.docx", "20260820 2173 Vergadering_ gevel en dak-transcript.txt",
             "2026-06-16 Plaud transcript.txt", "Transcript.TXT"]
    derden = ["derden-transcript.txt", "transcript aannemer.txt", "verslag transcript aannemer.docx", "aannemer transcript.docx",
              "transcript.pdf", "05-07-transcript.txt", "opname niet getranscribeerd.md", "00 verslag aannemer.md", "notities.md"]
    assert [n for n in eigen if not runtime.p.eigen_tekst(n)] == []
    assert [n for n in derden if runtime.p.eigen_tekst(n)] == []


def test_eigen_bestand_op_plaats_en_naam(runtime):
    """CX4-3/CX4-8, met de vormen die op 16-10-2026 live in de bezoekmappen staan."""
    e, m = runtime.p.eigen_bestand, "/Work All/x/_00. Communicatie/20260507 werfbezoek"
    gevallen = {
        "transcript.txt": "tekst", "05-07 Vergadering_ dak-transcript.txt": "tekst", "2026-06-16 Plaud transcript.txt": "tekst",
        "00 verslag.md": "tekst", "fotos/IMG_1.jpg": "foto", "fotos/IMG_1.HEIC": "foto", "fotos/00 fotos.md": "tekst",
        "fotos icloud mehdi/IMG_2.jpg": "foto", "Fotos iCloud Mehdi/IMG_3.png": "foto",
        "offerte aannemer.pdf": None, "IMG_9.jpg": None, "4. foto's/IMG_4.jpg": None, "foto niet gebruiken/IMG_5.jpg": None,
        "aannemer/fotos/IMG_6.jpg": None, "aannemer/transcript.txt": None, "fotos/sub/IMG_7.jpg": None, "fotos/verslag.docx": None,
        "opname niet getranscribeerd.md": None, "opname.mp3": "opname", "video.MOV": "opname", "derden/opname.mp3": None,
    }
    for rel, verwacht in gevallen.items():
        assert e(m, f"{m}/{rel}", rel.rsplit("/", 1)[-1]) == verwacht, rel
    assert e(m, "/Work All/ander bezoek/transcript.txt", "transcript.txt") is None
    assert e(m.upper(), f"{m}/transcript.txt", "transcript.txt") == "tekst"  # Dropbox geeft hoofdletters wisselend terug


def test_oude_registratie_alleen_van_deze_bordrij_en_link_blijft_bij_fout(runtime):
    p, rij = runtime.p, runtime.rij
    fout = type("RegisterFoutProef", (runtime.register.RegisterFout,), {})

    def faalt(*a):
        raise fout("register onbereikbaar")

    runtime.register.registreer = faalt
    rij["registratie"] = {"bezoek_id": "oud", "bordrij_id": 12, "project_ref": "h-architects:9999"}   # van een andere rij (CX5-2)
    assert p._vast_bezoek(rij, "9999", 1) == {}
    rij["registratie"] = {"bezoek_id": "eigen", "bordrij_id": 47, "project_ref": "h-architects:9999"}
    assert p._vast_bezoek(rij, "9999", 1)["bezoek_id"] == "eigen"
    rij["proef_info"] = {"werfapp": {"id": 7, "nummer": "9999-1"}}

    def weigert(*a, **k):
        raise runtime.werf.WerfappFout(409, "bezet")

    runtime.werf.concept = weigert
    uit = p.naar_werfapp(Agent(), "9999", 1, rij, {"bezoek": "1", "dossier": "9999"}, [], "/p.docx")
    assert uit == {"fout": "bezet", "status": 409, "id": 7, "nummer": "9999-1"}   # CX5-3: de bevestigde link blijft zichtbaar
    rij["proef_info"] = {"werfapp": {"id": 7, "nummer": "9999-1", "verstuurd": True}}
    uit = p.naar_werfapp(Agent(), "9999", 1, rij, {"bezoek": "1", "dossier": "9999"}, [], "/p.docx")
    assert uit["verstuurd"] is True and uit["id"] == 7   # CX6-2: de verzendstatus gaat bij een fout niet verloren


def test_dubbele_fotonamen_vallen_uit_beide_kanalen(runtime):
    f = runtime.p.zonder_dubbele_namen([{"naam": "IMG_1.jpg", "pad": "/m/fotos/IMG_1.jpg"}, {"naam": "IMG_1.jpg", "pad": "/m/fotos icloud mehdi/IMG_1.jpg"},
                                         {"naam": "IMG_2.jpg", "pad": "/m/fotos/IMG_2.jpg"}])
    assert [x["naam"] for x in f] == ["IMG_2.jpg"]


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
    monkeypatch.setattr(sys, "argv", ["werfverslag_schrijver.py", argument, "9999", "1",
                                    "--op-vraag-van-mehdi", "Mehdi vroeg deze proef"])
    schrijver.main()
    assert verzoeken == [("/api/werfopdrachten/aanvragen", {"dossier": "9999", "volgnr": 1, "soort": soort,
                                                          "bron": "commandline", "reden": "Mehdi vroeg deze proef"})]
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
        response = (client.post('/api/v1' + pad, json=payload, headers=kop) if payload is not None
                    else client.get('/api/v1' + pad, headers=kop))
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
assert db.q1('SELECT COUNT(*) n FROM bezoek')['n'] == 1  # twee bordrijen, één vast appbezoek
assert db.q1('SELECT COUNT(*) n FROM bron')['n'] == 1
assert db.q1("SELECT COUNT(*) n FROM bron_versie WHERE bewaring='geverifieerd'")['n'] == 0
print('echte registerclient: één betaalde fakeproviderstart, projectcache, geen mediahashclaim')
'''
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "DYLD_LIBRARY_PATH": "/opt/homebrew/lib"}
    resultaat = subprocess.run([str(python), "-c", script, str(backend), str(HIER)], cwd=backend, env=env, capture_output=True, text=True, timeout=60)
    assert resultaat.returncode == 0, resultaat.stdout + resultaat.stderr
    assert "één betaalde fakeproviderstart" in resultaat.stdout
