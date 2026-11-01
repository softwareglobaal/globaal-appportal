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
        self.logboek, self.klaar, self.rondes = [], [], []

    def ronde(self, naam):
        agent = self

        class Ronde:
            def __enter__(self):
                agent.rondes.append(naam)
                return NepRonde()

            def __exit__(self, *a):
                return False
        return Ronde()

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


def _labelronde(rijen, model, alleen=False):
    ag, r = NepAgent(), NepRonde()
    with vervangen((AR, "ag", ag), (AR, "db", _db(rijen)), (AR, "afspraken", lambda van, tot: []),
                   (AR.projectadressen, "index", lambda: {}), (AR, "locatie_op", lambda d, u: ("", None)),
                   (AR, "label_met_model", model), (AR, "BORDMAP", os.path.join(DATA, "bord"))):
        AR._ronde(r, "2026-10-20", "2026-10-22", "2026-10-22", alleen)
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
    {"description": "Punt ver na de laatste uiting", "assignee": {"name": "Proefpersoon Zeta"}, "recording_timestamp": "00:31:00"},
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
    assert GA.is_prive({"bron": "zoom", "zoom_prive": False}), "ook een zoom.json met prive=false blijft privé"


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
    assert rec["weggegooid"] == 2, "zonder tijdstip, of ver van elke uiting, is er geen citaat"
    uit = GA.uitingen(os.path.join(map_, "transcript.json"))
    assert GA.citaat_bij(uit, GA.seconden("00:31:00")) == "" and GA.citaat_bij(uit, GA.seconden("00:04:05")).startswith("Ik stuur")


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



# ----------------------------------------------------------------------- Plaud en Zoom-tekst via het model ---
import time  # noqa: E402

import claude_abonnement as CA  # noqa: E402

PLAUD_TRANSCRIPT = [
    {"speaker": "Speaker 1", "content": "We hebben de stabiliteitsstudie voor de Proefstraat besproken.", "start_time": 1000},
    {"speaker": "Speaker 2", "content": "Ik bel de ingenieur morgen terug over de balk boven de keuken.", "start_time": 65000},
    {"speaker": "Speaker 1", "content": "Prima, dan plannen we het plaatsbezoek in de week van 9 november.", "start_time": 90000},
]
ANTWOORD = {"samenvatting": "Het gesprek ging over de stabiliteitsstudie. De ingenieur wordt teruggebeld. Een derde zin.",
            "actiepunten": [
                {"wat": "ingenieur terugbellen", "wie": "Speaker 2", "tegen_wanneer": "morgen", "voor_wie": "collega",
                 "citaat": "Ik bel de ingenieur morgen terug over de balk"},
                {"wat": "contract tekenen", "wie": "Speaker 1", "voor_wie": "mehdi", "citaat": "we tekenen het contract"},
                {"wat": "plaatsbezoek plannen", "voor_wie": "mehdi", "citaat": "dan plannen we het bezoek in november"}]}
LIMIET = os.path.join(THUIS, "limiet.json")


def _plaud(naam="2026-10-09 1400 proef", n=1):
    map_ = os.path.join(DATA, "plaud-invoer", naam)
    _schrijf(os.path.join(map_, "transcript.json"), PLAUD_TRANSCRIPT)
    return [{"uniek": f"plaud:p{i}", "bron": "plaud", "datum": "2026-10-09", "start": "14:00", "minuten": 18, "prive": 0,
             "afdeling": "", "label": "TKN project", "ha_nummer": "", "titel": "", "map": map_} for i in range(n)]


def _meet(benutting, gezien=None, herstart=None):
    _schrijf(LIMIET, {"info": {"status": "allowed", "isUsingOverage": False, "unifiedWindows": {"seven_day": {
        "utilization": benutting, "resetsAt": herstart or time.time() + 3 * 86400, "status": "allowed"}}},
        "gezien": gezien or time.time()})


class NepVraag:
    """Een nepmodel: geeft ANTWOORD en meet daarna het weekvenster (zoals claude_abonnement.onthoud_limiet)."""

    def __init__(self, antwoord=ANTWOORD, benutting=0.40, meet=True):
        self.antwoord, self.benutting, self.meet, self.vragen = antwoord, benutting, meet, []

    def __call__(self, systeem, gebruiker, **kw):
        self.vragen.append((systeem, gebruiker, kw))
        if self.meet:
            _meet(self.benutting)
        if isinstance(self.antwoord, Exception):
            raise self.antwoord
        return {"tekst": "```json\n" + json.dumps(self.antwoord, ensure_ascii=False) + "\n```", "tokens": 1234}


def _budget(dag="2026-11-02", teller=None, benutting=0.40):
    """Een budget met een verse meting van het weekvenster (zoals Ai Angel die op het abonnement achterlaat)."""
    if os.path.exists(LIMIET):
        os.remove(LIMIET)
    if benutting is not None:
        _meet(benutting)
    return GA.Budget(dag, teller=teller, limiet=LIMIET)


def test_plaud_en_zoom_tekst_gaan_niet_naar_het_model_zolang_de_vlag_uit_staat():
    vraag = NepVraag()
    assert GA.MODEL_AAN is False, "de vlag staat in de code uit tot het ja van Mehdi (T-0122 keuze 1)"
    rec, toestand = GA.verwerk(_plaud()[0], _budget(), vraag)
    assert rec is None and toestand == "model staat uit" and not vraag.vragen
    zoom = {**_plaud()[0], "uniek": "zoom:meeting:w1", "bron": "zoom", "zoom_prive": False}
    with vervangen((GA, "MODEL_AAN", True)):
        assert GA.verwerk(zoom, _budget(), vraag)[1] == "privé" and not vraag.vragen, "Zoom-tekst is altijd privé"


def test_nepmodel_plaud_twee_zinnen_en_alleen_letterlijke_citaten():
    vraag = NepVraag()
    with vervangen((GA, "MODEL_AAN", True)):
        rec, toestand = GA.verwerk(_plaud()[0], _budget(), vraag)
    assert toestand == "model" and rec["samenvatting_van"] == "model" and rec["tokens"] == 1234, rec
    assert rec["samenvatting"] == "Het gesprek ging over de stabiliteitsstudie. De ingenieur wordt teruggebeld."
    assert [p["wat"] for p in rec["actiepunten"]] == ["ingenieur terugbellen"] and rec["weggegooid"] == 2, rec
    assert (rec["firma"], rec["soort"]) == ("TKN", "project")
    systeem, gebruiker, kw = vraag.vragen[0]
    assert kw == {"tools": (), "max_beurten": 2, "timeout": 600}, kw
    assert "Ik bel de ingenieur morgen terug" in json.loads(gebruiker)["transcript"]
    with vervangen((GA, "MODEL_AAN", True)):
        rec, toestand = GA.verwerk(_plaud()[0], _budget(), NepVraag({"samenvatting": "Kennismaking. Geen afspraken.",
                                                                     "actiepunten": []}))
    assert toestand == "model" and rec["actiepunten"] == [] and rec["weggegooid"] == 0, "een gesprek zonder actiepunt"
    for slecht in ({"actiepunten": []}, {"samenvatting": "x.", "actiepunten": "geen lijst"}):
        with vervangen((GA, "MODEL_AAN", True)):
            assert GA.verwerk(_plaud()[0], _budget(), NepVraag(slecht))[0] is None


def test_hoogstens_vijf_gesprekken_per_dag_hoe_vaak_de_ronde_ook_draait():
    teller = os.path.join(THUIS, "teller-vijf", "teller.json")
    vraag = NepVraag()
    with vervangen((GA, "MODEL_AAN", True), (GA, "UITVOER", os.path.dirname(teller))):
        budget = _budget(teller=teller)
        uit = [GA.verwerk(g, budget, vraag)[1] for g in _plaud(n=4)]
        tweede = GA.Budget("2026-11-02", teller=teller, limiet=LIMIET)        # een tweede ronde dezelfde dag
        uit += [GA.verwerk(g, tweede, vraag)[1] for g in _plaud(n=3)]
        assert os.stat(teller).st_mode & 0o777 == 0o600 and json.load(open(teller))["vragen"] == 5
        assert GA.Budget("2026-11-03", teller=teller, limiet=LIMIET).vandaag == 0, "een nieuwe dag begint bij nul"
    assert len(vraag.vragen) == 5 and uit.count("model") == 5, uit
    assert uit[-2:] == ["al 5 gesprekken naar het model vandaag"] * 2, uit


def test_geen_vraag_vanaf_60_procent_van_het_weekvenster_en_niet_zonder_nieuwe_meting():
    with vervangen((GA, "MODEL_AAN", True)):
        for benutting, herstart, gezien, verwacht in ((0.60, None, None, "weekvenster op 60 procent (grens 60)"),
                                                      (0.59, None, None, "model"),
                                                      (0.30, time.time() - 60, None, "weekvenster onbekend of ouder dan 12 uur"),
                                                      (0.30, None, time.time() - 13 * 3600, "weekvenster onbekend of ouder dan 12 uur"),
                                                      (None, None, None, "weekvenster onbekend of ouder dan 12 uur")):
            budget, vraag = _budget(benutting=None), NepVraag(benutting=0.30)
            if benutting is not None:
                _meet(benutting, gezien=gezien, herstart=herstart)
            toestand = GA.verwerk(_plaud()[0], budget, vraag)[1]
            assert toestand == verwacht and len(vraag.vragen) == (verwacht == "model"), (benutting, herstart, gezien, toestand)
        budget, vraag = _budget(), NepVraag(benutting=0.61)
        uit = [GA.verwerk(g, budget, vraag)[1] for g in _plaud(n=3)]
        assert len(vraag.vragen) == 1 and uit[1:] == ["weekvenster op 61 procent (grens 60)"] * 2, uit
        budget, vraag = _budget(), NepVraag(meet=False)
        uit = [GA.verwerk(g, budget, vraag)[1] for g in _plaud(n=2)]
        assert len(vraag.vragen) == 1 and uit[1] == "weekvenster na de vorige vraag niet gemeten", uit
    assert GA.WEEKGRENS == 0.60 and GA.MAX_PER_DAG == 5


def test_een_fout_van_het_abonnement_stopt_het_model_zonder_uitwijking_en_geeft_de_bestaande_nood():
    vraag = NepVraag(CA.Fout("Claude via het abonnement: limiet", "limiet"))
    with vervangen((GA, "MODEL_AAN", True)):
        budget = _budget()
        uit = [GA.verwerk(g, budget, vraag)[1] for g in _plaud(n=3)]
    assert len(vraag.vragen) == 1 and uit == ["abonnement: limiet"] * 3, uit
    bron = open(os.path.join(HIER, "gespreksanalist.py"), encoding="utf-8").read()
    for woord in ("import anthropic", "from anthropic", "Anthropic(", "messages.create", "sleutelbron", "ANTHROPIC_API_KEY"):
        assert woord not in bron, f"De Gespreksanalist mag de API niet kennen: {woord}"
    plaud = os.path.join(DATA, "plaud-invoer", "2026-10-21 0900 Proefpersoon Zeta")
    _schrijf(os.path.join(plaud, "transcript.json"), PLAUD_TRANSCRIPT)
    rij = {"bron": "plaud", "datum": "2026-10-21", "start": "09:00", "uniek": "plaud:ef56",
           "archief": "Data uit Mehdi/Plaud/2026-10-21 0900 Proefpersoon Zeta/transcript.md"}
    with vervangen((GA, "ANALYSE_AAN", True), (GA, "MODEL_AAN", True), (GA, "UITVOER", os.path.join(THUIS, "nood")),
                   (GA, "ZOOM_DATA", os.path.join(DATA, "zoom-leeg")), (CA, "vraag", vraag),
                   (CA, "LIMIET_BESTAND", LIMIET)):
        _meet(0.40)
        ag, r = _labelronde([rij], _geen_model)
    assert (CA.LIMIET_NOOD, "mehdi") in r.noden and len(vraag.vragen) == 2, (r.noden, vraag.vragen)
    assert any("1 abonnement: limiet" in str(a) for a in ag.logboek), ag.logboek


_NEP_CLAUDE = r"""import json, os, sys
rec, uit = sys.argv[1], sys.argv[2]
json.dump({"env": dict(os.environ), "invoer": sys.stdin.read()}, open(rec, "w"))
for regel in open(uit):
    print(regel.rstrip("\n"), flush=True)
"""


def test_nep_claude_code_krijgt_geen_api_sleutel_en_geen_gereedschap():
    """De echte claude_abonnement.vraag met een nep-Claude Code die alleen zijn omgeving opschrijft: De Archivaris zet
    de API-sleutel in zijn eigen omgeving (sleutelbron), het kindproces mag ze nooit zien."""
    d = tempfile.mkdtemp(prefix="nep-claude-", dir=THUIS)
    token, nep, rec, uitf = (os.path.join(d, n) for n in ("token", "nep.py", "rec.json", "uit.jsonl"))
    _schrijf(token, "sk-ant-oat01-nep\n")
    os.chmod(token, 0o600)
    _schrijf(nep, _NEP_CLAUDE)
    tekst = "```json\n" + json.dumps(ANTWOORD, ensure_ascii=False) + "\n```"
    regels = [{"type": "system", "subtype": "init", "model": "claude-opus-nep", "apiKeySource": "none"},
              {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": False,
                                                              "unifiedWindows": {"seven_day": {"utilization": 0.35,
                                                                                               "resetsAt": time.time() + 86400}}}},
              {"type": "result", "subtype": "success", "is_error": False, "result": tekst, "num_turns": 1,
               "usage": {"input_tokens": 900, "output_tokens": 100}}]
    _schrijf(uitf, "\n".join(json.dumps(r) for r in regels) + "\n")
    opdrachten, echte_opdracht = [], CA.opdracht

    def opdracht(*a, **k):
        opdrachten.append(echte_opdracht(*a, **k))
        return [sys.executable, nep, rec, uitf]

    os.environ["ANTHROPIC_API_KEY"] = "sk-ant-api-nep"
    try:
        with vervangen((GA, "MODEL_AAN", True), (CA, "opdracht", opdracht), (CA, "controleer_bron", lambda env, cwd: None),
                       (CA, "TOKEN_BESTAND", token), (CA, "LIMIET_BESTAND", LIMIET)):
            budget = _budget()
            uit = [GA.verwerk(g, budget)[1] for g in _plaud(n=2)]
    finally:
        del os.environ["ANTHROPIC_API_KEY"]
    gezien = json.load(open(rec, encoding="utf-8"))
    assert uit == ["model", "model"], uit
    assert "ANTHROPIC_API_KEY" not in gezien["env"] and gezien["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-nep"
    cmd = opdrachten[0]
    assert cmd[cmd.index("--tools") + 1] == "" and "--allowedTools" not in cmd and "--safe-mode" in cmd, cmd
    assert "Ik bel de ingenieur morgen terug" in gezien["invoer"]
    assert GA.weekbenutting(LIMIET)[0] == 0.35, "de meting van het abonnement is wat het budget leest"



# ------------------------------------------------------------------------------------- de proef (X5), droog ---
import hashlib  # noqa: E402
import io  # noqa: E402
import contextlib  # noqa: E402

import gespreksanalist_proef as PR  # noqa: E402


class GeenBord:
    """De proef raakt het bord niet: elke oproep van de agent is een fout."""

    def __getattr__(self, naam):
        raise AssertionError(f"de proef riep het bord aan: {naam}")


def _proefdata(zonder=True, naam=None):
    basis = os.path.join(THUIS, naam or ("proefdata" if zonder else "proefdata-zonder"))
    fathom, plaud, zoom = (os.path.join(basis, n) for n in ("fathom-data", "plaud-invoer", "zoom-data"))
    rijen = []
    for dag, sleutel, samenvatting, punten in (("06", "f1", SAMENVATTING, None if zonder else ACTIEPUNTEN),
                                               ("27", "f2", SAMENVATTING, ACTIEPUNTEN),
                                               ("08", "f3", None, ACTIEPUNTEN), ("14", "f4", SAMENVATTING, ACTIEPUNTEN)):
        map_ = os.path.join(fathom, f"2026-10-{dag} 1000 Proefpersoon Zeta {sleutel}")
        _schrijf(os.path.join(map_, "transcript.json"), FATHOM_TRANSCRIPT)
        _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": sleutel, "archivaris": {"label": "HA project",
                                                                                             "zekerheid": "hoog", "versie": 2}})
        if samenvatting:
            _schrijf(os.path.join(map_, "samenvatting.md"), samenvatting)
        if punten:
            _schrijf(os.path.join(map_, "actiepunten.md"), punten)
        rijen.append({"datum": f"2026-10-{dag}", "start": "10:00", "uniek": f"fathom:{sleutel}", "archief": map_,
                      "prive": 1 if sleutel == "f4" else 0, "minuten": 25})
    for dag, sleutel in (("03", "p1"), ("29", "p2")):
        naam = f"2026-10-{dag} 1400 Proefpersoon Zeta"
        _schrijf(os.path.join(plaud, naam, "transcript.json"), PLAUD_TRANSCRIPT)
        rijen.append({"bron": "plaud", "datum": f"2026-10-{dag}", "start": "14:00", "uniek": f"plaud:{sleutel}",
                      "archief": f"Data uit Mehdi/Plaud/{naam}/transcript.md", "minuten": 18})
    naam = "2026-10-17 1400 Zoom Proefonderwerp Omega [dddd4444]"
    _schrijf(os.path.join(zoom, naam, "transcript.json"), [{"speaker": {"display_name": "Proefpersoon Zeta"},
                                                            "text": "Privé, nooit lezen.", "timestamp": "00:00:01"}])
    _schrijf(os.path.join(zoom, naam, "zoom.json"), {"uuid": "z1", "prive": True, "minuten": 41,
                                                     "start_brussel": "2026-10-17T14:00:00+02:00"})
    return basis, fathom, plaud, zoom, rijen


def _vingerafdruk(map_):
    uit = {}
    for wortel, _, namen in os.walk(map_):
        for n in namen:
            p = os.path.join(wortel, n)
            uit[p] = hashlib.sha256(open(p, "rb").read()).hexdigest()
    return uit


class _NaDeProeven(PR.datetime):
    """De klok van main() in _proef: vast op 04-11. De proeven zelf staan vast op 02-11; met de echte klok deelde main()
    op 02-11 de dag met hen en telden de modelvragen anders (T-0120 samen, 02-11-2026)."""
    @classmethod
    def now(cls, tz=None):
        return PR.datetime(2026, 11, 4, 4, 0, tzinfo=tz)


def _proef(model_aan, vraag, zonder=True, keer=1, naam=None):
    basis, fathom, plaud, zoom, rijen = _proefdata(zonder, naam)
    uitvoer = os.path.join(basis, "gespreksanalist")
    voor = {p: h for p, h in _vingerafdruk(THUIS).items() if p != LIMIET}
    with vervangen((AR, "db", _db(rijen)), (AR, "afspraken", lambda van, tot: []), (AR, "ag", GeenBord()),
                   (AR.projectadressen, "CACHE", os.path.join(basis, "geen-cache.json")),
                   (AR.projectadressen, "index", _geen_model), (GA, "MODEL_AAN", model_aan), (GA, "UITVOER", uitvoer),
                   (GA, "PLAUD_INVOER", plaud), (GA, "ZOOM_DATA", zoom), (CA, "LIMIET_BESTAND", LIMIET),
                   (CA, "vraag", vraag)):
        _meet(0.40)
        for i in range(keer):
            pad, u = PR.proef("2026-10", vraag, nu=AR.datetime(2026, 11, 2, 3, 0, i).astimezone())
        scherm = io.StringIO()
        with contextlib.redirect_stdout(scherm), vervangen((sys, "argv", ["proef", "--maand", "2026-10"]),
                                                           (PR, "datetime", _NaDeProeven)):
            PR.main()
    na = {p: h for p, h in _vingerafdruk(THUIS).items() if p != LIMIET}     # de hele tijdelijke HOME
    nieuw = sorted(set(na) - set(voor))
    gewijzigd = [p for p in voor if na.get(p) != voor[p] and "/gespreksanalist/proef/" not in p]
    return pad, u, nieuw, gewijzigd, scherm.getvalue()


def test_proef_neemt_zes_gesprekken_verspreid_en_schrijft_alleen_het_proefbestand():
    vraag = NepVraag()
    pad, u, nieuw, gewijzigd, scherm = _proef(True, vraag)
    rollen = [(g["rol"], g["uniek"], g["toestand"]) for g in u["gesprekken"]]
    assert rollen == [("fathom zonder actiepunt", "fathom:f1", "fathom"), ("fathom met actiepunten", "fathom:f2", "fathom"),
                      ("plaud", "plaud:p1", "model"), ("plaud", "plaud:p2", "model"),
                      ("zoom-tekst", "zoom:meeting:z1", "privé"), ("privé", "fathom:f4", "privé")], rollen
    assert u["gekozen"] == 6 and u["tekort"] == [] and u["zonder_actiepunt"] and u["prive_alleen_regel"], u
    assert u["actiepunten"] == 4 and u["weggegooid"] == 6 and u["letterlijk_procent"] == 40, u
    assert u["tokens"] == 2468 and u["modelvragen"] == 2 and u["weekvenster_na"] == 0.40, u
    assert len(vraag.vragen) == 4, "proef() en main() samen: vier vragen"
    assert os.stat(pad).st_mode & 0o777 == 0o600 and os.path.dirname(pad).endswith("gespreksanalist/proef"), pad
    assert len(nieuw) == 2 and not gewijzigd, ("buiten het proefbestand niets nieuws of gewijzigd", nieuw, gewijzigd)
    assert all(p.endswith(".json") and "/gespreksanalist/proef/proef-2026-10-" in p for p in nieuw), nieuw
    assert "Zeta" not in scherm and "Proefstraat" not in scherm and "proefbestand:" in scherm, scherm
    d = json.load(open(pad, encoding="utf-8"))
    tekst = {g["uniek"]: g for g in d["gesprekken"]}
    assert tekst["zoom:meeting:z1"]["record"]["regel"] == "privégesprek, 41 min"
    assert tekst["fathom:f4"]["record"]["regel"] == "privégesprek, 25 min" and "samenvatting" not in tekst["fathom:f4"]["record"]


def test_proef_met_het_model_uit_vraagt_niets_en_noemt_het():
    pad, u, nieuw, gewijzigd, scherm = _proef(False, _geen_model)
    assert [g["toestand"] for g in u["gesprekken"] if g["bron"] == "plaud"] == ["model staat uit"] * 2, u["gesprekken"]
    assert u["model_aan"] is False and u["tokens"] == 0 and not gewijzigd



# --------------------------------------------------------------------------- inhaalweg en hernoemde mappen ---
def test_alleen_analyse_labelt_niet_en_vraagt_dus_de_api_niet():
    """De inhaalweg voor oktober (X7: bouwen mag, draaien niet): archivaris.py --alleen-analyse slaat de labels over,
    want die gaan nog via de API (label_met_model). Ook een gesprek zonder label gaat dan alleen door versie 3."""
    map_ = _fathom_map("2026-10-21 1500 inhaal")
    _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": 9300})
    rijen = [{"datum": "2026-10-21", "start": "15:00", "uniek": "fathom:9300", "archief": map_}]
    uitvoer = os.path.join(THUIS, "inhaal")
    with vervangen((GA, "UITVOER", uitvoer), (GA, "ZOOM_DATA", os.path.join(DATA, "zoom-leeg")), (GA, "ANALYSE_AAN", True)):
        ag, r = _labelronde(rijen, _geen_model, alleen=True)
    rec = json.load(open(os.path.join(uitvoer, "fathom", "9300.json"), encoding="utf-8"))
    assert rec["label"] == "" and rec["samenvatting_van"] == "fathom" and r.noden == [], (rec, r.noden)
    assert "archivaris" not in json.load(open(os.path.join(map_, "gesprek.json"), encoding="utf-8"))
    ag, r = _labelronde(rijen, _geen_model, alleen=True)
    assert any("staat uit" in str(a) for a in ag.logboek), "zonder de vlag zegt de inhaalweg dat hij niets deed"
    nep = NepAgent()
    with vervangen((AR, "ag", nep), (AR, "_ronde", lambda r, van, tot, vandaag, alleen=False: nep.logboek.append(alleen)),
                   (sys, "argv", ["archivaris.py", "--alleen-analyse", "--van", "2026-10-01", "--tot", "2026-10-31"])):
        assert AR.main() == 0
    assert nep.rondes == ["gesprekken analyseren 2026-10-01 tot 2026-10-31"] and nep.logboek == [True], nep.rondes


def test_een_hernoemde_fathommap_wordt_ook_gelezen():
    """De labelronde vindt een hernoemde map op het recording_id (archivaris.py, zoek op uniek); versie 3 leest dan
    dezelfde map en niet het oude pad."""
    map_ = _fathom_map("2026-10-21 1600 hernoemd")
    _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": "rec9400", "archivaris": {
        "label": "HA project", "zekerheid": "hoog", "versie": 2, "week": "2026-W43", "datum": "2026-10-21", "start": "16:00"}})
    rijen = [{"datum": "2026-10-21", "start": "16:00", "uniek": "fathom:rec9400",
              "archief": os.path.join(DATA, "fathom-data", "2026-10-21 1400 oude naam")}]
    uitvoer = os.path.join(THUIS, "hernoemd")
    with vervangen((GA, "UITVOER", uitvoer), (GA, "ZOOM_DATA", os.path.join(DATA, "zoom-leeg")), (GA, "ANALYSE_AAN", True)):
        ag, r = _labelronde(rijen, _geen_model)
    rec = json.load(open(os.path.join(uitvoer, "fathom", "rec9400.json"), encoding="utf-8"))
    assert rec["label"] == "HA project" and rec["actiepunten"], rec


def test_een_meting_zonder_weekvenster_na_een_vraag_stopt_het_model():
    """Meldt het abonnement na de vraag alleen het venster van vijf uur, dan is het weekvenster onbekend: geen tweede
    vraag (onbekend is geen ruimte). Alleen de eerste vraag van een ronde mag het venster meten."""
    class VijfUur(NepVraag):
        def __call__(self, *a, **k):
            uit = super().__call__(*a, **k)
            _schrijf(LIMIET, {"info": {"status": "allowed", "unifiedWindows": {"five_hour": {"utilization": 0.1}}},
                              "gezien": time.time()})
            return uit
    vraag = VijfUur()
    with vervangen((GA, "MODEL_AAN", True)):
        budget = _budget()
        uit = [GA.verwerk(g, budget, vraag)[1] for g in _plaud(n=3)]
    assert len(vraag.vragen) == 1 and uit[1:] == ["weekvenster na de vorige vraag niet gemeten"] * 2, uit



# ------------------------------------------------------------------------------- Codex T-0120 toets 1 ---
def test_proef_herhalen_omzeilt_de_vijf_per_dag_niet():
    vraag = NepVraag()
    pad, u, nieuw, gewijzigd, scherm = _proef(True, vraag, keer=3, naam="proefdata-herhaal")
    gemaakt = sorted(p for p in nieuw if "20261102-03000" in p)
    tellen = [json.load(open(p, encoding="utf-8"))["modelvragen"] for p in gemaakt]
    assert tellen == [2, 2, 1], tellen
    assert "al 5 gesprekken naar het model vandaag" in [g["toestand"] for g in u["gesprekken"]], u["gesprekken"]


def test_proef_zonder_fathomgesprek_zonder_actiepunt_noemt_het_tekort():
    pad, u, nieuw, gewijzigd, scherm = _proef(True, NepVraag(), zonder=False)
    rollen = [g["rol"] for g in u["gesprekken"]][:2]
    assert rollen == ["fathom", "fathom met actiepunten"], rollen
    assert "geen werkgesprek zonder actiepunt in de uitkomst" in u["tekort"] and not u["zonder_actiepunt"], u["tekort"]


def test_vol5_twee_nummers_in_de_titel_en_plaud_zonder_label():
    assert GA.dossier_van("UNABO project", "", "[UB-KO] 46118 en 46200 Proefstraat") == ("", "")
    assert GA.dossier_van("UNABO project", "", "[UB-KO] 46118 HA2612 Proefstraat") == ("", "")
    plaud = {"label": "", "afdeling": "unabo", "project": "UNAB:46118", "zekerheid": "middel"}
    assert GA.herkomst(plaud) == {"label": "", "firma": "UNABO", "soort": "", "dossier": "46118",
                                  "dossier_bewijs": "dossier van de wacht, zekerheid middel", "label_van": "afdeling van de wacht"}
    assert GA.herkomst({**plaud, "zekerheid": "laag"})["dossier"] == ""
    assert GA.herkomst({**plaud, "project": "HARC:2612"})["dossier"] == "", "het dossier moet bij de firma horen"
    assert GA.herkomst({"afdeling": "regie"})["soort"] == "intern" and GA.herkomst({"afdeling": "onbekend"})["label_van"] == ""
    rec, _ = GA.verwerk({**_plaud()[0], "label": "", "afdeling": "h-architects", "project": "HARC:2612", "zekerheid": "hoog"})
    assert rec is None, "zonder model komt Plaud niet verder"
    map_ = _fathom_map("2026-10-24 1000 zonder label")
    rec, _ = GA.verwerk(_geval(map=map_, label="", afdeling="tkn"))
    assert (rec["firma"], rec["label_van"]) == ("TKN", "afdeling van de wacht"), rec


def test_t0095_antwoord_zonder_reden_laat_de_ronde_niet_vallen_en_geen_vrije_tekst_in_het_werkverslag():
    map_ = os.path.join(DATA, "fathom-data", "2026-10-21 1100 proef reden")
    _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": 7101})
    _schrijf(os.path.join(map_, "transcript.md"), "# kop\n\n[00:00:01] Proefpersoon Zeta: goedemorgen")
    rij = {"datum": "2026-10-21", "start": "11:00", "uniek": "fathom:7101", "archief": map_}
    ag, r = _labelronde([rij], lambda *a: ({"label": "Onbekend", "zekerheid": "laag"}, 10))
    d = json.load(open(os.path.join(map_, "gesprek.json"), encoding="utf-8"))
    assert d["archivaris"]["label"] == "Onbekend" and d["archivaris"]["reden"] == "", d
    assert ag.klaar and "Archivaris: 1 gesprek" in ag.klaar[0]["titel"], ag.klaar
    _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": 7101})
    ag, r = _labelronde([rij], lambda *a: ({"label": "Proefpersoon Zeta sales", "zekerheid": "Proefonderwerp Omega"}, 10))
    fout = [a for a in ag.logboek if a[1] == "fout"]
    assert fout and not any(w in str(fout) for w in ("Zeta", "Omega")), fout


def test_alleen_analyse_vindt_ook_een_hernoemde_fathommap():
    map_ = _fathom_map("2026-10-21 1700 hernoemd inhaal")
    _schrijf(os.path.join(map_, "gesprek.json"), {"recording_id": "rec9500"})
    rijen = [{"datum": "2026-10-21", "start": "17:00", "uniek": "fathom:rec9500",
              "archief": os.path.join(DATA, "fathom-data", "2026-10-21 1500 oude naam")}]
    uitvoer = os.path.join(THUIS, "hernoemd-inhaal")
    with vervangen((GA, "UITVOER", uitvoer), (GA, "ZOOM_DATA", os.path.join(DATA, "zoom-leeg")), (GA, "ANALYSE_AAN", True)):
        ag, r = _labelronde(rijen, _geen_model, alleen=True)
    assert json.load(open(os.path.join(uitvoer, "fathom", "rec9500.json"), encoding="utf-8"))["samenvatting_van"] == "fathom"



# ------------------------------------------------------------------------------- Codex T-0120 toets 2 ---
def test_proef_en_nachtronde_tellen_elkaars_modelvragen_mee():
    """Vijf modelvragen in drie proeven, daarna de nachtronde dezelfde dag: geen vraag meer. En omgekeerd: vier in de
    nachtronde, dan krijgt de proef er nog een. Twee proeven in dezelfde seconde geven twee bestanden."""
    vraag = NepVraag()
    pad, u, nieuw, gewijzigd, scherm = _proef(True, vraag, keer=3, naam="proefdata-samen")
    uitvoer = os.path.join(THUIS, "proefdata-samen", "gespreksanalist")
    with vervangen((GA, "MODEL_AAN", True), (GA, "UITVOER", uitvoer)):
        nacht = GA.Budget("2026-11-02", limiet=LIMIET)
        _meet(0.40)
        assert nacht.vandaag == 5 and GA.verwerk(_plaud()[0], nacht, vraag)[1] == "al 5 gesprekken naar het model vandaag"
    basis = os.path.join(THUIS, "proefdata-omgekeerd", "gespreksanalist")
    GA.schrijf_600(os.path.join(basis, "teller.json"), {"dag": "2026-11-02", "vragen": 4})
    vraag = NepVraag()
    with vervangen((GA, "UITVOER", basis)):
        pad, u, *_ = _proef(True, vraag, naam="proefdata-omgekeerd")
    assert u["modelvragen"] == 1 and len(vraag.vragen) == 3, "1 op 02-11 (4 al in de nacht), 2 voor main() op vandaag"
    assert json.load(open(os.path.join(basis, "teller.json")))["vragen"] == 4, "de proef raakt de dagteller niet"
    namen = sorted(n for n in os.listdir(os.path.join(THUIS, "proefdata-samen", "gespreksanalist", "proef"))
                   if n.startswith("proef-2026-10-20261102-030000"))
    assert len(namen) == 1
    with vervangen((AR, "db", _db([])), (AR, "afspraken", lambda van, tot: []), (AR, "ag", GeenBord()),
                   (GA, "UITVOER", os.path.join(THUIS, "zelfde-seconde")), (GA, "ZOOM_DATA", os.path.join(DATA, "zoom-leeg"))):
        nu = AR.datetime(2026, 11, 2, 4, 0).astimezone()
        a, _ = PR.proef("2026-10", NepVraag(), nu=nu)
        b, _ = PR.proef("2026-10", NepVraag(), nu=nu)
    assert a != b and os.path.exists(a) and os.path.exists(b), (a, b)


def test_archiefmap_zoekt_op_het_id_zelf_en_niet_op_een_stukje_tekst():
    ander = os.path.join(DATA, "fathom-data", "2026-10-25 0900 ander gesprek")
    _schrijf(os.path.join(ander, "gesprek.json"), {"recording_id": "rec96001", "url": "https://fathom.video/calls/rec96001"})
    juist = os.path.join(DATA, "fathom-data", "2026-10-25 1100 hernoemd juist")
    _schrijf(os.path.join(juist, "gesprek.json"), {"recording_id": "rec9600"})
    assert AR.archiefmap({"uniek": "fathom:rec9600", "archief": ander}) == juist, "een oud pad naar een ander gesprek telt niet"
    assert AR.archiefmap({"uniek": "fathom:rec9600", "archief": os.path.join(DATA, "fathom-data", "weg")}) == juist
    assert AR.archiefmap({"uniek": "fathom:rec960", "archief": ""}) == "", "rec960 is niet rec9600 of rec96001"
    zonder_id = os.path.join(DATA, "fathom-data", "2026-10-25 1300 zonder id")
    _schrijf(os.path.join(zonder_id, "gesprek.json"), {"title": "oud"})
    assert AR.archiefmap({"uniek": "fathom:rec9700", "archief": zonder_id}) == zonder_id, "zonder id: zoals vroeger"
    g = {"uniek": "fathom:rec9600", "bron": "fathom", "archief": ander, "datum": "2026-10-25", "start": "11:00", "minuten": 5}
    assert AR.geval_van(g, [], {})["map"] == juist and AR.geval_van(g, [], {}, "")["map"] == ""



# ------------------------------------------------------------------------------- Codex T-0120 toets 3 ---
def test_de_dagteller_telt_proefvragen_niet_dubbel():
    """Twee proefvragen, een nachtvraag, daarna een nieuwe proef: die mag nog twee vragen doen (2 + 1 + 2 = 5)."""
    vraag = NepVraag()
    pad, u, *_ = _proef(True, vraag, naam="proefdata-dubbel")
    uitvoer = os.path.join(THUIS, "proefdata-dubbel", "gespreksanalist")
    assert u["modelvragen"] == 2
    with vervangen((GA, "MODEL_AAN", True), (GA, "UITVOER", uitvoer)):
        nacht = GA.Budget("2026-11-02", limiet=LIMIET)
        _meet(0.40)
        assert GA.verwerk(_plaud()[0], nacht, vraag)[1] == "model"
        assert json.load(open(os.path.join(uitvoer, "teller.json")))["vragen"] == 1, "alleen de nachtvraag in de teller"
        assert GA.Budget("2026-11-02", limiet=LIMIET).vandaag == 3
    with vervangen((GA, "UITVOER", uitvoer)):
        pad, u, *_ = _proef(True, NepVraag(), naam="proefdata-dubbel")
    assert u["modelvragen"] == 2, u["modelvragen"]


def test_de_labelronde_volgt_geen_oud_pad_naar_een_ander_gesprek():
    ander = os.path.join(DATA, "fathom-data", "2026-10-22 0800 ander gesprek labelronde")
    _schrijf(os.path.join(ander, "gesprek.json"), {"recording_id": "rec98001"})
    _schrijf(os.path.join(ander, "transcript.md"), "# kop\n\n[00:00:01] Proefpersoon Zeta: een ander gesprek")
    juist = os.path.join(DATA, "fathom-data", "2026-10-22 0900 hernoemd labelronde")
    _schrijf(os.path.join(juist, "gesprek.json"), {"recording_id": "rec9800"})
    _schrijf(os.path.join(juist, "transcript.md"), "# kop\n\n[00:00:01] Proefpersoon Zeta: het juiste gesprek")
    gelezen = []

    def model(g, tekst, *a):
        gelezen.append(tekst)
        return {"label": "HA sales", "zekerheid": "middel", "reden": "proef"}, 5
    ag, r = _labelronde([{"datum": "2026-10-22", "start": "09:00", "uniek": "fathom:rec9800", "archief": ander}], model)
    assert gelezen and "het juiste gesprek" in gelezen[0], gelezen
    assert json.load(open(os.path.join(juist, "gesprek.json"), encoding="utf-8"))["archivaris"]["label"] == "HA sales"
    assert "archivaris" not in json.load(open(os.path.join(ander, "gesprek.json"), encoding="utf-8")), "het andere gesprek bleef ongemoeid"


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
