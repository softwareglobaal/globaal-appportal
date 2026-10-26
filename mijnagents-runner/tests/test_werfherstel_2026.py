"""Grendels voor de acht aangenomen punten van het driehoeksoverleg 21-10-2026."""
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "koppelingen"))
import werfverslag_voorbereider as V  # noqa: E402
import werfverslag_proef as P  # noqa: E402
import werfnamen  # noqa: E402
import sjabloon_werfverslag as S  # noqa: E402
from naslag import naslag as N  # noqa: E402


def test_status_en_werfstart_grendels():
    controles = [{"code": code, "naam": code, "stand": "ok"} for code in ("W1", "W2", "W3", "W4", "W5", "W6", "W12", "WERFSTART")]
    assert V.stand_van(controles) == "klaar voor verslag"
    for code in ("W4", "W5", "W6", "W12"):
        for stand in ("onbekend", "let_op"):
            kopie = [dict(c, stand=stand) if c["code"] == code else c for c in controles]
            assert V.stand_van(kopie) == "te verzamelen"
            assert any(x.startswith(code + " ") for x in V.ontbrekende_posten(kopie))
    controles[-1]["stand"] = "onbekend"
    assert V.stand_van(controles) == "te verzamelen"
    assert any(x.startswith("WERFSTART ") for x in V.ontbrekende_posten(controles))


def test_heic_dubbel_in_icloud_map_en_herkomst_transcript(monkeypatch):
    basis = "/bezoek/fotos icloud mehdi"
    items = [{".tag": "file", "name": naam, "path_display": basis + "/" + naam, "size": 3}
             for naam in ("beeld.heic", "beeld.jpg")]
    monkeypatch.setattr(P.bronnen, "lijst", lambda *_: items)
    assert [f["naam"] for f in P.lees_bezoekmap("/bezoek", alleen_eigen=True)[1]] == ["beeld.jpg"]
    assert werfnamen.vertrouwde_transcriptkop("plaud_id: of_ffffffffffffffffffffffffffffffff\n\ntekst")
    assert werfnamen.vertrouwde_transcriptkop("dossier: 2309\nbezoekmap: /bezoek\n\ntekst")
    assert not werfnamen.vertrouwde_transcriptkop("Transcript van klant\n\ntekst")


def test_eigen_velden_en_modelinvoer_zonder_meta(monkeypatch):
    gezien = {}
    class Client:
        messages = SimpleNamespace(create=lambda **kw: gezien.update(kw) or SimpleNamespace(
            stop_reason="tool_use", content=[SimpleNamespace(type="tool_use", name="gegevens", input={
                "verslagtype_voorstel": "werfverslag", "situatie": "", "onderdelen": [], "acties": [], "ontbreekt": [], "gegevens": []})],
            usage=SimpleNamespace(input_tokens=1, output_tokens=1)))
    monkeypatch.setattr(P, "_client", lambda: Client())
    P.vraag_gegevens("kop", "bron", eigen=True)
    assert "openstaande facturen" not in gezien["system"]
    assert "bouwheer" not in P.VELDEN_EIGEN


def _verslagpunt(bron="", fotos=None, naslag=""):
    return {"categorieen": [{"naam": "Ruwbouw", "punten": [{"titel": "Muur", "tekst_nl": "Er staat een muur.",
             "bron": bron, "fotos": fotos or [], "naslag": naslag}]}]}


def test_bronpoort_markeert_en_kantoorherkomst():
    verslag = _verslagpunt()
    verslag["categorieen"][0]["punten"].append({"titel": "Kantoor", "doorlopend": True, "tekst_nl": "Vaste afspraak."})
    assert P._bronpoort(verslag, [{"naam": "transcript.txt", "tekst": "x"}], []) == ["Muur"]
    punt = verslag["categorieen"][0]["punten"][0]
    assert "bron ontbreekt" in punt["tekst_nl"]
    assert verslag["categorieen"][0]["punten"][1]["bron"] == "vast punt kantoor"
    goed = _verslagpunt("transcript.txt 00:42")
    assert P._bronpoort(goed, [{"naam": "transcript.txt", "tekst": "x"}], []) == []
    assert P._bronpoort(_verslagpunt("transcript.txt"), [{"naam": "transcript.txt", "tekst": "x"}], []) == ["Muur"]


def test_naslagvalidator_licentie_lengte_en_letterlijke_overname(monkeypatch):
    woorden = "een twee drie vier vijf zes zeven acht negen tien elf twaalf dertien veertien"
    monkeypatch.setattr(P, "naslag_register", lambda: [{"sleutel": "TV283", "status": "verouderd", "bestand": "geheim.pdf"}])
    v = _verslagpunt("foto.jpg", naslag="TV283: " + "x" * 260 + " geheim.pdf")
    v["categorieen"][0]["punten"][0]["tekst_nl"] = woorden + ". Eigen waarneming. geheim.pdf"
    meldingen = P._naslagcontrole(v, f"### NASLAG\nTV283: bron\n[p. 1] {woorden}")
    punt = v["categorieen"][0]["punten"][0]
    assert punt["tekst_nl"].startswith("(zie naslag)")
    assert "geheim.pdf" not in punt["tekst_nl"]
    assert len(punt["naslag"]) <= 240 and "geheim.pdf" not in punt["naslag"]
    assert len(meldingen) >= 2
    ongeldig = _verslagpunt("", naslag="TV283: toelichting")
    P._naslagcontrole(ongeldig, "TV283: bron")
    assert not ongeldig["categorieen"][0]["punten"][0]["naslag"]


def test_naslag_alleen_bij_vaststelling_met_bron_en_aparte_modelsectie(monkeypatch):
    gezien = {}
    monkeypatch.setattr(P, "naslag_voor_punten", lambda onderdelen, **kw: gezien.update(onderdelen=onderdelen, opties=kw) or "TV283: kader")
    onderdelen = [{"onderdeel": "Dak", "vaststellingen": ["zichtbare pan"], "bron": "foto.jpg"},
                  {"onderdeel": "Muur", "vaststellingen": ["scheur"], "bron": ""}]
    assert P._naslagblok({"keuzes": {}}, {"onderdelen": onderdelen}) == "TV283: kader"
    assert gezien["onderdelen"] == onderdelen[:1]

    class Client:
        messages = SimpleNamespace(create=lambda **kw: gezien.update(verzoek=kw) or SimpleNamespace(
            stop_reason="tool_use", content=[SimpleNamespace(type="tool_use", name="werfverslag", input={
                "status_nl": "", "status_en": "", "aanwezigen": [], "categorieen": [], "raming": [],
                "acties": [], "volgend": "", "akkoord": []})], usage=SimpleNamespace(input_tokens=1, output_tokens=1)))
    monkeypatch.setattr(P, "_client", lambda: Client())
    P.vraag_verslag("kop", {}, {}, "foto.jpg", naslag="TV283: kader")
    prompt = gezien["verzoek"]["messages"][0]["content"]
    assert "## EIGEN FOTO'S\nfoto.jpg" in prompt
    assert "## NASLAG (alleen toelichting)\nTV283: kader" in prompt


def test_naslagprompt_licentie_verouderd_zonder_pdfnaam(monkeypatch):
    bron = {"sleutel": "TV283", "titel": "Dak", "uitgever": "Buildwise", "jaar": 2008,
            "status": "verouderd", "licentie": "buildwise", "bestand": "geheim.pdf"}
    monkeypatch.setattr(N, "zoek", lambda **kw: [bron])
    monkeypatch.setattr(N, "fragmenten", lambda *args, **kw: ["[p. 2] Korte toelichting"])
    blok = N.naslag_voor_punten([{"onderdeel": "Dak", "vaststellingen": ["dakpan"]}])
    assert "citeren, niet kopiëren" in blok
    assert "(opvolger na te kijken)" in blok
    assert "geheim.pdf" not in blok


def test_fotofout_word_en_zichtbare_markdown(monkeypatch):
    verslag = _verslagpunt("foto.jpg", ["foto.jpg"])
    monkeypatch.setattr(P.bronnen, "download", lambda *_: (_ for _ in ()).throw(OSError("offline")))
    assert P._fotos_verzamelen([], [{"naam": "foto.jpg", "pad": "/bezoek/foto.jpg", "grootte": 10}], verslag) == {}
    assert verslag["fotos_niet_geplaatst"] == [{"naam": "foto.jpg", "reden": "download: OSError"}]
    verslag["categorieen"][0]["punten"][0]["nummer"] = "1.1"
    basis = {"dossier": "9999", "bezoek": "1", "adres": "Teststraat", "datum": "2026-10-21", "opgemaakt": "2026-10-21", **verslag}
    md = S.naar_markdown(basis)
    # herkomst in het verslag alleen als V, B of S (schrijfregel S4); de bestandsnaam blijft in het veld bron
    # een foto: de naam zegt niet of ze van Mehdi is, dus de naam (zonder tijdstip) en geen onjuiste V (zeventiende review)
    assert "Foto's niet geplaatst" in md and "Herkomst: foto.jpg" in md
    assert basis["categorieen"][0]["punten"][0]["bron"] == "foto.jpg"
    terug = S.van_markdown(md)
    assert terug["categorieen"][0]["punten"][0]["bron"] == "foto.jpg"   # de bron blijft bewaard achter de V
    assert terug["fotos_niet_geplaatst"] == verslag["fotos_niet_geplaatst"]
    # naar_docx werkt op een kopie (grendel), maar de plaatsingsfout komt in het verslag van de aanroeper (V2/V8/V13)
    S.naar_docx(basis, {"foto.jpg": b"geen afbeelding"})
    assert any("plaatsing in Word" in f["reden"] for f in basis["fotos_niet_geplaatst"])
    assert "plaatsing in Word" in S.naar_markdown(basis)


def test_tokenbudget_standaard_uit(monkeypatch):
    monkeypatch.delenv("WERF_TOKENBUDGET", raising=False)
    assert not P._budget_aan()
    monkeypatch.setenv("WERF_TOKENBUDGET", "ja")
    assert P._budget_aan()


def test_tokenbudget_blokkeert_voor_nieuwe_betaalde_bron(monkeypatch):
    monkeypatch.setenv("WERF_TOKENBUDGET", "ja")
    aangeroepen = []
    def verwerk(*args):
        aangeroepen.append(args[3])
        return ({"verslagtype_voorstel": "werfverslag", "situatie": "", "onderdelen": [], "acties": [],
                 "ontbreekt": [], "gegevens": []}, SimpleNamespace(input_tokens=6000, output_tokens=1))
    monkeypatch.setattr(P.register, "verwerk", verwerk)
    agent = SimpleNamespace(log=lambda *args: None)
    bron = {"naam": "00 verslag.md", "pad": "/bezoek/00 verslag.md", "tekst": "a" * 40000}
    with pytest.raises(P.extractie.BronLeesFout, match="WERF_TOKENBUDGET"):
        P._voorbereid_bronnen(agent, "9999", 1, {"keuzes": {}}, [bron], [], [])
    assert len(aangeroepen) < 4
