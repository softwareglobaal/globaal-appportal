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
