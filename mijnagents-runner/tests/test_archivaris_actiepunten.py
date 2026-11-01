"""De Archivaris versie 3, De Gespreksanalist (T-0120 ANGEL-1 per bron, met VOL-5), en het voorwerk uit T-0095.

Alle gesprekken, personen, firma's en dossiers zijn verzonnen (Proefpersoon Zeta, Proefstraat, 2612). Geen netwerk,
geen bord, geen model: de modelvraag is een nepvraag of een nep-Claude Code die alleen zijn omgeving opschrijft.
Draaien: python3 mijnagents-runner/tests/test_archivaris_actiepunten.py
"""
import json
import os
import sqlite3
import sys
import tempfile
import traceback

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))

# Alles onder een lege, tijdelijke HOME: de paden van De Archivaris (mijnagents-data, bord, .env) wijzen dan nergens
# naar echte gegevens.
THUIS = tempfile.mkdtemp(prefix="archivaris-v3-")
os.environ["HOME"] = THUIS
import archivaris as AR  # noqa: E402

DATA = os.path.join(THUIS, "appportal", "mijnagents-data")


class NepAgent:
    def __init__(self):
        self.logboek, self.klaar = [], []

    def log(self, *a, **k):
        self.logboek.append(a)

    def klaarzet(self, items):
        self.klaar.extend(items)


class NepRonde:
    werkwijze = "## Correcties van Mehdi\n\n- (nog geen)\n"

    def __init__(self):
        self.noden, self.detail = [], ""

    def nood(self, tekst, wie=None):
        self.noden.append((tekst, wie))


def _schrijf(pad, data):
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    with open(pad, "w", encoding="utf-8") as f:
        f.write(data if isinstance(data, str) else json.dumps(data, ensure_ascii=False))


def _db(rijen):
    def db():
        con = sqlite3.connect(":memory:")
        con.row_factory = sqlite3.Row
        con.execute("create table gesprek_log (bron, datum, start, minuten, uniek, archief, project, personen, bedrijf,"
                    " afdeling, thema, prive, opgenomen_door)")
        for r in rijen:
            con.execute("insert into gesprek_log values (:bron, :datum, :start, :minuten, :uniek, :archief, :project,"
                        " :personen, :bedrijf, :afdeling, :thema, :prive, :opgenomen_door)",
                        {"bron": "fathom", "minuten": 30, "project": "", "personen": "Proefpersoon Zeta", "bedrijf": "",
                         "afdeling": "", "thema": "proefoverleg", "prive": 0, "opgenomen_door": "", **r})
        return con
    return db


class vervangen:
    """Zet attributen tijdelijk op een andere waarde: vervangen((module, "naam", waarde), ...)."""

    def __init__(self, *drietallen):
        self.drietallen, self.oud = drietallen, []

    def __enter__(self):
        for obj, naam, waarde in self.drietallen:
            self.oud.append((obj, naam, getattr(obj, naam)))
            setattr(obj, naam, waarde)

    def __exit__(self, *a):
        for obj, naam, waarde in reversed(self.oud):
            setattr(obj, naam, waarde)


def _labelronde(rijen, model):
    ag, r = NepAgent(), NepRonde()
    with vervangen((AR, "ag", ag), (AR, "db", _db(rijen)), (AR, "afspraken", lambda van, tot: []),
                   (AR.projectadressen, "index", lambda: {}), (AR, "locatie_op", lambda d, u: ("", None)),
                   (AR, "label_met_model", model), (AR, "BORDMAP", os.path.join(DATA, "bord"))):
        AR._ronde(r, "2026-10-20", "2026-10-22", "2026-10-22")
    return ag, r


# ------------------------------------------------------------------------------- voorwerk T-0095 (versie 2) ---
def test_weekoverzicht_valt_niet_om_op_een_oud_record_zonder_zekerheid():
    """T-0095: 101 rondes vielen uit op KeyError 'zekerheid' (archivaris.py:207). Een oud record zonder zekerheid geeft
    een lege cel, geen fout; de andere gesprekken van die week blijven in het overzicht."""
    oud = {"label": "HA project", "datum": "2026-10-20", "start": "10:00", "week": "2026-W43", "versie": 2}
    _schrijf(os.path.join(DATA, "fathom-data", "2026-10-20 1000 proef a", "gesprek.json"), {"archivaris": oud})
    goed = dict(oud, start="11:00", zekerheid="hoog")
    _schrijf(os.path.join(DATA, "fathom-data", "2026-10-20 1100 proef b", "gesprek.json"), {"archivaris": goed})
    with vervangen((AR, "BORDMAP", os.path.join(DATA, "bord"))):
        n = AR.weekoverzicht("2026-W43")
    tekst = open(os.path.join(DATA, "bord", "Labels 2026-W43.md"), encoding="utf-8").read()
    assert n == 2 and "| 11:00 |" in tekst and "| 10:00 |" in tekst, tekst


def test_een_modelantwoord_zonder_zekerheid_wordt_niet_bewaard():
    """T-0095: het record werd weggeschreven voor iemand keek of label en zekerheid er waren (archivaris.py:271 voor
    :275). Nu blijft gesprek.json ongemoeid, staat er een fout in het werkverslag, en loopt de ronde door."""
    map_ = os.path.join(DATA, "fathom-data", "2026-10-21 0900 proef c")
    _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": 7001})
    _schrijf(os.path.join(map_, "transcript.md"), "# kop\n\n[00:00:01] Proefpersoon Zeta: goedemorgen")
    rij = {"datum": "2026-10-21", "start": "09:00", "uniek": "fathom:7001", "archief": map_}
    ag, r = _labelronde([rij], lambda *a: ({"label": "HA project", "reden": "proef"}, 10))
    d = json.load(open(os.path.join(map_, "gesprek.json"), encoding="utf-8"))
    assert "archivaris" not in d, d
    assert any(a[1] == "fout" and "zekerheid" in a[2] for a in ag.logboek), ag.logboek
    ag, r = _labelronde([rij], lambda *a: ({"label": "Verzonnen label", "zekerheid": "hoog", "reden": "proef"}, 10))
    assert "archivaris" not in json.load(open(os.path.join(map_, "gesprek.json"), encoding="utf-8"))
    ag, r = _labelronde([rij], lambda *a: ({"label": "HA project", "zekerheid": "hoog", "reden": "proef",
                                            "agenda_toets": "", "locatie_toets": "", "projectnummer": "",
                                            "vraag_aan_mehdi": ""}, 10))
    d = json.load(open(os.path.join(map_, "gesprek.json"), encoding="utf-8"))
    assert d["archivaris"]["label"] == "HA project" and d["archivaris"]["versie"] == 2, d



# ----------------------------------------------------------------------- versie 3: De Gespreksanalist ---
import gespreksanalist as GA  # noqa: E402

UIT = os.path.join(DATA, "gespreksanalist-proef")
FATHOM_TRANSCRIPT = [
    {"speaker": {"display_name": "Proefpersoon Zeta"}, "text": "Goedemorgen, zullen we beginnen?", "timestamp": "00:00:02"},
    {"speaker": {"display_name": "Mehdi"}, "text": "Ik stuur het aangepaste plan van de Proefstraat vrijdag naar de klant.",
     "timestamp": "00:04:10"},
    {"speaker": {"display_name": "Proefpersoon Zeta"}, "text": "Goed.", "timestamp": "00:09:00"},
    {"speaker": {"display_name": "Proefpersoon Zeta"}, "text": "Dan vraag ik de offerte voor het dak volgende week op bij de aannemer.",
     "timestamp": "00:09:03"},
]
SAMENVATTING = ("# Samenvatting van Fathom (niet als bron voor contract of verslag; het transcript telt)\n\n"
                "## Meeting Purpose\n\n[Het ontwerp van de Proefstraat doornemen](https://fathom.video/x)\n\n"
                "## Key Takeaways\n\n  - **Plan**: het plan wordt aangepast aan de opmerkingen van de klant.\n"
                "  - De offerte voor het dak volgt.\n  - Een derde punt dat niet meer meetelt.\n")
ACTIEPUNTEN = [
    {"description": "Aangepast plan naar de klant sturen", "assignee": {"name": "Mehdi", "email": "m@voorbeeld.test"},
     "recording_timestamp": "00:04:12"},
    {"description": "Offerte dak opvragen", "assignee": {"name": "Proefpersoon Zeta"}, "recording_timestamp": "00:09:01"},
    {"description": "Punt zonder tijdstip", "assignee": {"name": "Proefpersoon Zeta"}},
]


def _fathom_map(naam, samenvatting=SAMENVATTING, actiepunten=ACTIEPUNTEN):
    map_ = os.path.join(DATA, "fathom-data", naam)
    _schrijf(os.path.join(map_, "transcript.json"), FATHOM_TRANSCRIPT)
    if samenvatting is not None:
        _schrijf(os.path.join(map_, "samenvatting.md"), samenvatting)
    if actiepunten is not None:
        _schrijf(os.path.join(map_, "actiepunten.md"), actiepunten)
    return map_


def _geval(**kw):
    return {"uniek": "fathom:9001", "bron": "fathom", "datum": "2026-10-14", "start": "10:00", "minuten": 34, "prive": 0,
            "afdeling": "", "label": "HA project", "ha_nummer": "2612", "titel": "", **kw}


def _geen_model(*a, **k):
    raise AssertionError("het model werd gevraagd")


def test_een_citaat_telt_alleen_als_het_letterlijk_in_het_transcript_staat():
    tekst = GA.corpus(GA.uitingen(os.path.join(_fathom_map("2026-10-14 1000 citaat"), "transcript.json")))
    assert GA.citaat_in("ik stuur het aangepaste plan van de Proefstraat vrijdag", tekst)
    assert GA.citaat_in("“Ik stuur het AANGEPASTE plan”", tekst), "hoofdletters en aanhalingstekens tellen niet"
    assert GA.citaat_in("vrijdag naar de klant. Goed. Dan vraag ik", tekst), "over twee uitingen heen is nog letterlijk"
    assert not GA.citaat_in("ik stuur het plan vrijdag naar de klant", tekst), "eigen verwoording"
    assert not GA.citaat_in("ik stuur het aangepaste plan ... naar de klant", tekst), "een weglating"
    assert not GA.citaat_in("Goed.", tekst) and not GA.citaat_in("de klant", tekst), "te kort"
    assert not GA.citaat_in("ik stuur het aangepaste plan " * 10, tekst), "meer dan 200 tekens"
    goed, weg = GA.keur([{"wat": "plan sturen", "citaat": "Ik stuur het aangepaste plan", "voor_wie": "iedereen"},
                         {"wat": "verzonnen", "citaat": "we tekenen morgen het contract"},
                         {"wat": "", "citaat": "Ik stuur het aangepaste plan"}, "geen punt"], tekst)
    assert weg == 3 and len(goed) == 1 and goed[0]["voor_wie"] == "onbekend", (goed, weg)
    assert set(goed[0]) == {"wat", "wie", "tegen_wanneer", "voor_wie", "citaat"}


def test_privegesprek_geeft_alleen_privegesprek_en_minuten_zonder_iets_te_lezen():
    for kw in ({"prive": 1}, {"afdeling": "Privé"}, {"label": "Prive"}, {"bron": "plaud", "uniek": "plaud:ab12", "prive": True}):
        rec, toestand = GA.verwerk(_geval(map="/bestaat/niet", **kw), vraag=_geen_model)
        assert toestand == "privé" and rec["regel"] == "privégesprek, 34 min" and rec["prive"] is True, (kw, rec)
        assert set(rec) == {"versie", "uniek", "bron", "datum", "start", "minuten", "prive", "regel", "ts"}, rec
    rec, _ = GA.verwerk(_geval(prive=1, minuten=0))
    assert rec["regel"] == "privégesprek, duur onbekend"


def test_zoom_vangnettekst_is_altijd_prive():
    """zoom_wacht.py:266 en vangnet_schrijven: zoom.json draagt altijd prive=true. Ontbreekt de vlag, dan ook privé.
    Alleen een uitdrukkelijk prive=false kan ooit werk zijn."""
    zoom = os.path.join(DATA, "zoom-data")
    tekst = [{"speaker": {"display_name": "Proefpersoon Zeta"}, "text": "Een gesprek dat niemand mag lezen, ook het model niet.",
              "timestamp": "00:00:01"}]
    for naam, meta in (("2026-10-17 1400 Zoom vaste vergaderruimte [aaaa1111]", {"uuid": "u1/A==", "prive": True}),
                       ("2026-10-18 0900 Zoom vaste vergaderruimte [bbbb2222]", {"uuid": "u2"}),
                       ("2026-11-03 0900 Zoom vaste vergaderruimte [cccc3333]", {"uuid": "u3", "prive": True})):
        _schrijf(os.path.join(zoom, naam, "transcript.json"), tekst)
        _schrijf(os.path.join(zoom, naam, "zoom.json"), {**meta, "start_brussel": f"{naam[:10]}T{naam[11:13]}:{naam[13:15]}:00+02:00",
                                                         "minuten": 41})
    gevallen = GA.zoom_gevallen("2026-10-01", "2026-10-31", zoom)
    assert [g["uniek"] for g in gevallen] == ["zoom:meeting:u1/A==", "zoom:meeting:u2"], gevallen
    for g in gevallen:
        rec, toestand = GA.verwerk(g, vraag=_geen_model)
        assert toestand == "privé" and rec["regel"] == "privégesprek, 41 min" and "samenvatting" not in rec, rec
    assert not GA.is_prive({"bron": "zoom", "zoom_prive": False})


def test_fathom_gebruikt_eigen_samenvatting_en_actiepunten_en_slaat_het_model_over():
    map_ = _fathom_map("2026-10-14 1000 ontwerp")
    rec, toestand = GA.verwerk(_geval(map=map_), vraag=_geen_model)
    assert toestand == "fathom" and rec["samenvatting_van"] == "fathom" and rec["tokens"] == 0, rec
    assert rec["samenvatting"] == ("Het ontwerp van de Proefstraat doornemen. Plan: het plan wordt aangepast aan de "
                                   "opmerkingen van de klant."), rec["samenvatting"]
    tekst = GA.corpus(GA.uitingen(os.path.join(map_, "transcript.json")))
    assert [p["wat"] for p in rec["actiepunten"]] == ["Aangepast plan naar de klant sturen", "Offerte dak opvragen"]
    assert all(GA.citaat_in(p["citaat"], tekst) and len(p["citaat"]) <= 200 for p in rec["actiepunten"]), rec
    assert rec["actiepunten"][1]["citaat"].startswith("Goed. Dan vraag ik de offerte"), "een korte uiting wordt aangevuld"
    assert rec["weggegooid"] == 1, "het punt zonder tijdstip heeft geen citaat"


def test_fathom_zonder_samenvatting_wacht_en_vraagt_geen_model():
    rec, toestand = GA.verwerk(_geval(map=_fathom_map("2026-10-15 1000 zonder", samenvatting=None)), vraag=_geen_model)
    assert rec is None and toestand == "wacht op de samenvatting van Fathom"


def test_fathom_zonder_actiepunt_en_de_oude_samenvatting_als_python_dict():
    """Tot FATHOM-1 schreef De Fathomwacht str() van het object (fathom_wacht.py:252); de markdown komt eruit."""
    oud = "# Samenvatting van Fathom (niet als bron)\n\n" + str({"template_name": "general",
                                                                   "markdown_formatted": "## Doel\n\nKennismaking met de klant. Geen afspraken."})
    rec, toestand = GA.verwerk(_geval(map=_fathom_map("2026-10-16 1000 zonder punt", samenvatting=oud, actiepunten=None)))
    assert toestand == "fathom" and rec["samenvatting"] == "Kennismaking met de klant. Geen afspraken." and rec["actiepunten"] == []


def test_vol5_firmalabel_en_dossier_per_gesprek():
    map_ = _fathom_map("2026-10-20 1000 dossier")
    rec, _ = GA.verwerk(_geval(map=map_, label="UNABO project", ha_nummer="", titel="[UB-KO] 46118 Proefstraat opmeting"))
    assert (rec["firma"], rec["soort"], rec["dossier"], rec["dossier_bewijs"]) == ("UNABO", "project", "46118",
                                                                                 "agendatitel, niet bevestigd"), rec
    rec, _ = GA.verwerk(_geval(map=map_, label="HA project", ha_nummer="2612"))
    assert (rec["firma"], rec["soort"], rec["dossier"], rec["dossier_bewijs"]) == ("HA", "project", "2612", "bevestigd")
    rec, _ = GA.verwerk(_geval(map=map_, label="HA sales", ha_nummer="", titel="[UB-KO] 46118 Proefstraat"))
    assert (rec["firma"], rec["soort"], rec["dossier"]) == ("HA", "sales", ""), "geen nummer van een andere firma"
    rec, _ = GA.verwerk(_geval(map=map_, label="UNABO sales", titel="[HA-KO] 2612 Proeflaan"))
    assert rec["dossier"] == "", "de agendafirma moet de firma van het label zijn"
    assert GA.firma_en_soort("Regie intern") == ("", "intern") and GA.firma_en_soort("Harmoniebouw") == ("Harmoniebouw", "")
    rec, _ = GA.verwerk(_geval(map=map_, label="Prive"))
    assert rec["prive"] and "dossier" not in rec and "firma" not in rec


def test_uitvoer_600_een_keer_en_opnieuw_bij_nieuw_label_of_privé():
    map_ = _fathom_map("2026-10-21 1000 uitvoer")
    rec, toestand = GA.stap(_geval(map=map_, uniek="fathom:9100"), map_=UIT)
    pad = GA.bewaar(rec, UIT)
    assert toestand == "fathom" and os.stat(pad).st_mode & 0o777 == 0o600, oct(os.stat(pad).st_mode)
    assert os.stat(os.path.dirname(pad)).st_mode & 0o777 == 0o700 and pad == os.path.join(UIT, "fathom", "9100.json")
    assert GA.stap(_geval(map=map_, uniek="fathom:9100"), map_=UIT) == (None, "al gedaan")
    rec, toestand = GA.stap(_geval(map=map_, uniek="fathom:9100", label="HA sales", ha_nummer=""), vraag=_geen_model, map_=UIT)
    assert toestand == "nieuw label" and rec["soort"] == "sales" and rec["dossier"] == "" and rec["actiepunten"], rec
    GA.bewaar(rec, UIT)
    rec, toestand = GA.stap(_geval(map=map_, uniek="fathom:9100", label="Prive"), map_=UIT)
    GA.bewaar(rec, UIT)
    assert toestand == "privé" and set(json.load(open(pad, encoding="utf-8"))) == {
        "versie", "uniek", "bron", "datum", "start", "minuten", "prive", "regel", "ts"}, "de samenvatting moet weg"
    a, b = GA.pad_van("zoom:meeting:u1/A==", UIT), GA.pad_van("zoom:meeting:u1_A==", UIT)
    assert a != b and os.path.dirname(a) == os.path.join(UIT, "zoom") and "/" not in os.path.basename(a), (a, b)


def test_de_ronde_doet_niets_zolang_de_analyse_uit_staat_en_logt_daarna_alleen_aantallen():
    map_ = _fathom_map("2026-10-22 1000 ronde")
    _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": 9200, "archivaris": {
        "label": "HA project", "zekerheid": "hoog", "versie": 2, "week": "2026-W43", "datum": "2026-10-22", "start": "10:00"}})
    plaud = os.path.join(DATA, "plaud-invoer", "2026-10-22 1400 Proefpersoon Zeta")
    _schrijf(os.path.join(plaud, "transcript.json"), [{"speaker": "Speaker 1", "content": "Een Plaud-opname over de werf.",
                                                       "start_time": 1000}])
    rijen = [{"datum": "2026-10-22", "start": "10:00", "uniek": "fathom:9200", "archief": map_},
             {"datum": "2026-10-22", "start": "12:00", "uniek": "fathom:9201", "archief": map_, "prive": 1, "minuten": 12},
             {"bron": "plaud", "datum": "2026-10-22", "start": "14:00", "uniek": "plaud:cd34",
              "archief": "Data uit Mehdi/Plaud/2026-10-22 1400 Proefpersoon Zeta/transcript.md"}]
    uitvoer = os.path.join(DATA, "gespreksanalist")
    with vervangen((GA, "UITVOER", uitvoer), (GA, "ZOOM_DATA", os.path.join(DATA, "zoom-leeg"))):
        ag, r = _labelronde(rijen, _geen_model)
        assert not os.path.exists(uitvoer) and not any("gespreksanalist" in str(a) for a in ag.logboek)
        with vervangen((GA, "ANALYSE_AAN", True)):
            ag, r = _labelronde(rijen, _geen_model)
    assert json.load(open(os.path.join(uitvoer, "fathom", "9200.json"), encoding="utf-8"))["dossier"] == ""
    assert json.load(open(os.path.join(uitvoer, "fathom", "9201.json"), encoding="utf-8"))["regel"] == "privégesprek, 12 min"
    assert not os.path.exists(os.path.join(uitvoer, "plaud")), "het model staat uit: Plaud wacht"
    regel = [a for a in ag.logboek if "gespreksanalist" in str(a)]
    assert len(regel) == 1 and "1 fathom" in regel[0][2] and "1 privé" in regel[0][2] and "1 model staat uit" in regel[0][2], regel
    assert not any(w in str(ag.logboek) + str(ag.klaar) for w in ("Zeta", "Proefstraat", "offerte", "plan")), ag.logboek


if __name__ == "__main__":
    goed = fout = 0
    for naam, f in list(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
                print(f"  OK   {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"  FOUT {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)
