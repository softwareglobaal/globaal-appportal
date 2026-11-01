"""Grendels op De Fathomwacht uit T-0120 (meting 01-10 tot 01-11-2026, overleg X1 tot X9).

- FATHOM-7: een archiefmap met "herkenning": null (de 1960 mappen van fathom_haal_alles.py) breekt de ronde niet meer
  af (01-10-2026: beide rondes AttributeError); het gesprek is dan privé, de veilige kant, zonder naam of onderwerp.
- FATHOM-1 en ANGEL-8 (een punt, X9): een aparte vraag zonder transcript met include_summary en include_action_items;
  per recording_id alleen ontbrekende samenvatting.md, actiepunten.json en actiepunten.md in de bestaande map, nooit
  overschrijven; de samenvatting is de markdown-tekst, geen str() van het object; onbekend is nooit een lege lijst;
  niets ervan op het bord, ook niet van een privégesprek; een mislukte aanvulvraag is een nood en laat de ronde staan.

Geen netwerk en geen taalmodel: Fathom en het bord zijn nagebootst (fathom_ronde uit test_bord_lees.py), elk gesprek
staat al in het archief, dus herkent de ronde niets opnieuw. Alle namen en adressen zijn verzonnen.
Draaien: python3 mijnagents-runner/tests/test_fathom_wacht.py
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from test_bord_lees import (MEHDI, WW_FATHOM, BordNabootsing, _fathom_wacht, fathom_ronde,  # noqa: E402
                            gesprek, herkenning)


# ------------------------------------------------------------------------------------------------ FATHOM-7 ---
def test_fathom7_herkenning_null_is_prive_en_breekt_niet():
    """FATHOM-7: .get("herkenning", {}) gaf None als de sleutel bestond met null; daarna herk.get(...) en een
    AttributeError, de hele ronde fout. Nu: privé bij twijfel, zonder naam of onderwerp in rij, item of werkverslag."""
    nb = BordNabootsing(werkwijze=WW_FATHOM, open_noden=[])
    g = gesprek(7101, "2026-10-20T07:10:00Z", "2026-10-20T07:41:00Z", door=MEHDI, titel="Proefgesprek Zonnedak")
    gezet, scherm, _ = fathom_ronde(nb, [(g, None)])
    assert nb.statussen()[-1]["status"] == "waakt", nb.statussen()[-1]
    rij = gezet["/api/gesprekken"][0]["rijen"][0]
    assert rij["prive"] is True and rij["personen"] == "" and rij["thema"] == "", rij
    item = gezet["/api/klaarzet"][0]["items"][0]
    assert "privégesprek, 31 min" in item["titel"] and item["inhoud"].get("prive") is True, item
    for tekst in (str(item), scherm):
        assert "Zonnedak" not in tekst, f"de titel in Fathom lekt bij een gesprek zonder herkenning: {tekst[:400]}"


# ------------------------------------------------------------------------------------- FATHOM-1 en ANGEL-8 ---
SAMENVATTING = {"template_name": "general", "markdown_formatted": "## Kort\n\n- Offerte voor het proefdak bespreken"}
ACTIEPUNTEN = [{"description": "Offerte proefdak doorsturen", "user_generated": False, "completed": False,
                "recording_timestamp": "00:12:05", "recording_playback_url": "https://fathom.video/calls/7201?t=725",
                "assignee": {"name": "Jan Proef", "email": "jan@proef.test", "team": None}},
               {"description": "Plan nakijken", "completed": True, "recording_timestamp": "00:20:00", "assignee": None}]


def _koppeling():
    import fathom as F  # noqa: PLC0415
    return F


def _nep_haal(F, paginas):
    """Een nagebootste fathom._haal: per sleutel een lijst pagina's; onthoudt (sleutel, pad, params) van elke vraag."""
    gevraagd = []

    def haal(sleutel, pad, params=None):
        gevraagd.append((sleutel, pad, dict(params or {})))
        nr = sum(1 for s, _, _ in gevraagd if s == sleutel) - 1
        return paginas[sleutel][nr]
    return haal, gevraagd


def test_fathom1_aanvulvraag_vraagt_samenvatting_en_actiepunten_zonder_transcript():
    """FATHOM-1 (overleg X1, K4): een aparte vraag met include_summary en include_action_items, zonder transcript, over
    elke sleutel en elke pagina. De gewone vraag met transcript blijft zoals ze was (pagina's van 600 kB braken al af)."""
    F = _koppeling()
    paginas = {"s1": [{"items": [{"recording_id": 1}], "next_cursor": "c2"}, {"items": [{"recording_id": 2}]}],
               "s2": [{"items": [{"recording_id": 3}]}]}
    echt = (F._haal, F.sleutels, F.time.sleep)
    F._haal, gevraagd = _nep_haal(F, paginas)
    F.sleutels, F.time.sleep = (lambda: ["s1", "s2"]), (lambda s: None)
    try:
        uit = F.samenvattingen("2026-10-01T00:00:00Z")
        assert [g["recording_id"] for g in uit] == [1, 2, 3], uit
        assert len(gevraagd) == 3 and all(pad == "/meetings" for _, pad, _ in gevraagd), gevraagd
        for _, _, p in gevraagd:
            assert p["include_summary"] == "true" and p["include_action_items"] == "true", p
            assert p["include_transcript"] == "false" and p["created_after"] == "2026-10-01T00:00:00Z", p
        assert gevraagd[1][2].get("cursor") == "c2" and "cursor" not in gevraagd[0][2], gevraagd
        F._haal, gevraagd = _nep_haal(F, {"s1": [{"items": []}], "s2": [{"items": []}]})
        F.gesprekken("2026-10-01T00:00:00Z", met_transcript=True)
        assert all(p["include_transcript"] == "true" and "include_summary" not in p and "include_action_items" not in p
                   for _, _, p in gevraagd), f"de vraag met transcript krijgt er niets bij: {gevraagd}"
    finally:
        F._haal, F.sleutels, F.time.sleep = echt


def test_angel8_samenvatting_is_markdown_geen_python_dict():
    """ANGEL-8: default_summary is een object met markdown_formatted; fathom_wacht.py:252 schreef str() van het geheel."""
    F = _koppeling()
    assert F.samenvatting_tekst({"default_summary": SAMENVATTING}) == SAMENVATTING["markdown_formatted"]
    assert F.samenvatting_tekst({"default_summary": "## Al tekst"}) == "## Al tekst"
    assert F.samenvatting_tekst({"default_summary": None}) == "" and F.samenvatting_tekst({}) == ""
    fw = _fathom_wacht()
    archief, oud = tempfile.mkdtemp(prefix="fathom-data-"), (fw.ARCHIEF, fw._INDEX)
    fw.ARCHIEF, fw._INDEX = archief, None
    try:
        g = dict(gesprek(7201, "2026-10-21T08:00:00Z", "2026-10-21T08:30:00Z"), default_summary=SAMENVATTING,
                 action_items=ACTIEPUNTEN)
        map_, nieuw = fw.bewaar(g, "", {"prive": False, "afdeling": "regie"})
    finally:
        fw.ARCHIEF, fw._INDEX = oud
    tekst = open(os.path.join(map_, "samenvatting.md"), encoding="utf-8").read()
    assert nieuw and "## Kort" in tekst and "- Offerte voor het proefdak bespreken" in tekst, tekst
    assert "template_name" not in tekst and "{'" not in tekst and "markdown_formatted" not in tekst, tekst
    punten = json.load(open(os.path.join(map_, "actiepunten.json"), encoding="utf-8"))
    assert punten["actiepunten"][0] == {"tekst": "Offerte proefdak doorsturen", "wie": "Jan Proef", "tijd": "00:12:05",
                                        "klaar": False}, punten


def test_fathom1_actiepunten_onbekend_is_nooit_leeg():
    """De vorm van een actiepunt (contract met De Dagbundelaar) en onbekend tegenover geen (VOL-19): een lege lijst
    alleen als Fathom het gesprek verwerkte (er is een samenvatting); niet gevraagd of nog niet verwerkt is None."""
    F = _koppeling()
    assert F.actiepunten({"action_items": ACTIEPUNTEN})[1] == {"tekst": "Plan nakijken", "wie": "", "tijd": "00:20:00",
                                                               "klaar": True}
    assert F.actiepunten({"action_items": [], "default_summary": SAMENVATTING}) == []
    assert F.actiepunten({"action_items": []}) is None, "geen samenvatting: nog niet verwerkt, dus onbekend"
    assert F.actiepunten({}) is None and F.actiepunten({"action_items": None}) is None
    assert F.actiepunten({"action_items": [{"description": " "}], "default_summary": SAMENVATTING}) is None, \
        "een lijst in een vorm die we niet kennen is onbekend, geen nul"


def test_fathom1_vul_aan_schrijft_alleen_wat_ontbreekt():
    """Een map zonder bestanden krijgt ze; een bestaand bestand blijft byte voor byte gelijk; droog schrijft niets;
    een map die niet bestaat, wordt niet gemaakt."""
    F = _koppeling()
    map_ = tempfile.mkdtemp(prefix="fathom-map-")
    g = {"recording_id": 7301, "default_summary": SAMENVATTING, "action_items": ACTIEPUNTEN}
    assert F.vul_aan(map_, g, droog=True) == ["samenvatting.md", "actiepunten.json", "actiepunten.md"]
    assert os.listdir(map_) == [], "droog schrijft niets"
    eigen = "# eigen samenvatting, met de hand\n".encode("utf-8")
    with open(os.path.join(map_, "samenvatting.md"), "wb") as f:
        f.write(eigen)
    assert F.vul_aan(map_, g) == ["actiepunten.json", "actiepunten.md"]
    assert open(os.path.join(map_, "samenvatting.md"), "rb").read() == eigen, "nooit overschrijven"
    md = open(os.path.join(map_, "actiepunten.md"), encoding="utf-8").read()
    assert "- [ ] Offerte proefdak doorsturen (Jan Proef, 00:12:05)" in md and "- [x] Plan nakijken (00:20:00)" in md, md
    voor = {n: open(os.path.join(map_, n), "rb").read() for n in os.listdir(map_)}
    ander = dict(g, default_summary={"markdown_formatted": "iets anders"}, action_items=[])
    assert F.vul_aan(map_, ander) == [] and voor == {n: open(os.path.join(map_, n), "rb").read() for n in os.listdir(map_)}
    weg = os.path.join(map_, "bestaat-niet")
    assert F.vul_aan(weg, g) == [] and not os.path.exists(weg)
    leeg = tempfile.mkdtemp(prefix="fathom-map-")
    assert F.vul_aan(leeg, {"recording_id": 7302, "action_items": []}) == [], "nog niet verwerkt: niets, ook geen []"
    assert F.vul_aan(leeg, {"recording_id": 7302, "action_items": [], "default_summary": SAMENVATTING}) == \
        ["samenvatting.md", "actiepunten.json", "actiepunten.md"]
    assert json.load(open(os.path.join(leeg, "actiepunten.json"), encoding="utf-8"))["actiepunten"] == []
    assert "geen actiepunt" in open(os.path.join(leeg, "actiepunten.md"), encoding="utf-8").read()


def test_fathom1_ronde_vult_aan_en_zet_niets_op_het_bord():
    """De ronde vult de samenvatting en de actiepunten aan in de archiefmap, ook van een gesprek dat er al stond; niets
    daarvan gaat naar het bord: niet in de gesprekkentabel, niet in het klaarzet-item, niet in het werkverslag of op het
    scherm, ook niet van een privégesprek."""
    werk = gesprek(7401, "2026-10-21T08:00:00Z", "2026-10-21T08:30:00Z", titel="Proefgesprek werk")
    prive = gesprek(7402, "2026-10-21T18:00:00Z", "2026-10-21T18:20:00Z", titel="Proefgesprek thuis")
    met = [dict(werk, default_summary=SAMENVATTING, action_items=ACTIEPUNTEN),
           dict(prive, default_summary={"markdown_formatted": "## Geheim\n\n- Vakantie boeken"},
                action_items=[{"description": "Vakantie boeken", "assignee": {"name": "Lotte Geheim"}}])]
    archief, gevraagd = tempfile.mkdtemp(prefix="fathom-data-"), []
    nb = BordNabootsing(werkwijze=WW_FATHOM, open_noden=[])
    gezet, scherm, _ = fathom_ronde(nb, [(werk, herkenning(["Jan Proef"], "Proefdak")),
                                         (prive, herkenning(["Zeta Thuis"], "thuis", prive=True, afdeling="prive"))],
                                    archief=archief, samenvattingen=lambda sinds: gevraagd.append(sinds) or met)
    fw = _fathom_wacht()
    assert gevraagd and nb.statussen()[-1]["status"] == "waakt", (gevraagd, nb.statussen()[-1])
    for g in (werk, prive):
        map_ = os.path.join(archief, fw.archiefmap(g))
        assert {"samenvatting.md", "actiepunten.json", "actiepunten.md"} <= set(os.listdir(map_)), os.listdir(map_)
    naar_bord = json.dumps(gezet, ensure_ascii=False) + scherm
    for geheim in ("Kort", "Offerte proefdak", "Geheim", "Vakantie", "Lotte"):
        assert geheim not in naar_bord, f"{geheim!r} ging naar het bord of het scherm"
    assert "samenvatting en actiepunten van Fathom: 2 samenvatting(en), 2 lijst(en) actiepunten" in scherm, scherm


def test_fathom1_mislukte_aanvulvraag_laat_de_ronde_staan_met_een_nood():
    """Faalt de aparte vraag, dan blijven de gesprekkentabel en de klaarzet-items van deze ronde staan; de fout is een
    nood (geen stille nul) en het werkverslag noemt alleen de soort fout."""
    def kapot(sinds):
        raise ValueError("Fathom kapot met Geheime tekst (proef)")

    nb = BordNabootsing(werkwijze=WW_FATHOM, open_noden=[])
    werk = gesprek(7501, "2026-10-21T08:00:00Z", "2026-10-21T08:30:00Z")
    gezet, scherm, _ = fathom_ronde(nb, [(werk, herkenning(["Jan Proef"], "Proefdak"))], samenvattingen=kapot)
    laatste = nb.statussen()[-1]
    assert gezet.get("/api/gesprekken") and gezet.get("/api/klaarzet"), list(gezet)
    assert laatste["status"] == "waakt" and any("samenvatting en actiepunten" in n["tekst"] for n in laatste["nood"]), laatste
    assert "ValueError" in scherm and "Geheime tekst" not in scherm, scherm


def test_fathom1_eenmalige_aanvulronde_droog_en_echt():
    """fathom_haal_alles.py --aanvullen JJJJ-MM-DD [--droog]: de vraag begint om middernacht in Brussel; droog schrijft
    niets (ook geen log in het archief); echt vult alleen bestaande mappen aan, maakt geen map voor een onbekend gesprek
    en laat een bestaand bestand gelijk; op het scherm alleen tellingen."""
    sys.path.insert(0, os.path.dirname(HIER))
    import fathom_haal_alles as H  # noqa: PLC0415
    doel = tempfile.mkdtemp(prefix="fathom-data-")
    map_ = os.path.join(doel, "2026-10-21 1000 Proefgesprek")
    os.makedirs(map_)
    with open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8") as f:
        json.dump({"recording_id": 7601, "herkenning": None}, f)
    with open(os.path.join(map_, "actiepunten.md"), "w", encoding="utf-8") as f:
        f.write("[]")
    gevraagd = []
    antwoord = [{"recording_id": 7601, "title": "Proefgesprek Geheim", "default_summary": SAMENVATTING,
                 "action_items": ACTIEPUNTEN}, {"recording_id": 7699, "default_summary": SAMENVATTING}]
    oud = (H.DOEL, H.fathom.samenvattingen)
    H.DOEL, H.fathom.samenvattingen = doel, (lambda sinds: gevraagd.append(sinds) or antwoord)
    try:
        voor = sorted(os.listdir(doel)), sorted(os.listdir(map_))
        scherm = io.StringIO()
        with redirect_stdout(scherm):
            assert H.aanvullen("2026-10-01", droog=True) == 0
        assert (sorted(os.listdir(doel)), sorted(os.listdir(map_))) == voor, "droog schrijft niets"
        assert gevraagd == ["2026-09-30T22:00:00Z"], gevraagd
        assert '"samenvatting": 1' in scherm.getvalue() and '"zonder_map": 1' in scherm.getvalue(), scherm.getvalue()
        with redirect_stdout(scherm):
            assert H.aanvullen("2026-10-01") == 0 and H.aanvullen("gisteren") == 2
        assert sorted(os.listdir(doel)) == voor[0], "geen nieuwe map, geen log in het archief"
        assert {"samenvatting.md", "actiepunten.json"} <= set(os.listdir(map_)), os.listdir(map_)
        assert open(os.path.join(map_, "actiepunten.md"), encoding="utf-8").read() == "[]", "nooit overschrijven"
        assert "Geheim" not in scherm.getvalue() and "Kort" not in scherm.getvalue(), scherm.getvalue()
    finally:
        H.DOEL, H.fathom.samenvattingen = oud


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)
