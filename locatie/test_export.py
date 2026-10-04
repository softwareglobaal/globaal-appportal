"""Grendels op de export naar Dropbox privé (locatie-ophalen.py, draait op de Mac).

Uit de opdracht v1.2: een dag met een enkel punt wordt geëxporteerd; nooit een dag
voor de startgrens; een herzien dagboek bewaart de vorige versie; gemiste dagen
worden ingehaald; de databasekopie draagt een datum. De VM wordt nagebootst: geen
SSH, geen echte gegevens.

Draaien: python3 locatie/test_export.py
"""
import importlib.util
import json
import os
import sys
import tempfile
from types import SimpleNamespace

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
spec = importlib.util.spec_from_file_location("ophalen", os.path.join(HIER, "locatie-ophalen.py"))
E = importlib.util.module_from_spec(spec)
spec.loader.exec_module(E)


def zet_doel():
    doel = tempfile.mkdtemp()
    E.DOEL, E.DAGEN = doel, os.path.join(doel, "dagen")
    E.RUWE_KOPIE, E.STAND = os.path.join(doel, "ruwe-database"), os.path.join(doel, "werkbestanden", "s.json")
    return doel


class VM:
    """Nagebootste VM: antwoordt op curl naar /api/dagboek en cat van een wachtdagboek."""
    def __init__(self, dagboeken, wacht=None):
        self.dagboeken, self.wacht, self.gevraagd = dagboeken, wacht or {}, []

    def __call__(self, opdracht, pogingen=3, wacht=20):
        self.gevraagd.append(opdracht)
        if "/api/dagboek/" in opdracht:
            dag = opdracht.split("/api/dagboek/")[1][:10]
            return json.dumps(self.dagboeken.get(dag, {"datum": dag, "status": "afgesloten", "markdown":
                                                       "# Locatielogboek %s\n" % dag, "punten": [], "sporen": {}}))
        if opdracht.startswith("cat "):
            dag = opdracht.split("/dagen/")[1][:10]
            return self.wacht.get(dag, "")
        return ""


def args(**kw):
    return SimpleNamespace(**dict({"dag": None, "dagen": None, "geen_kopie": True}, **kw))


def test_een_los_punt_wordt_geexporteerd():
    zet_doel()
    g = {"datum": "2026-10-05", "status": "afgesloten", "markdown": "# Locatielogboek 2026-10-05\n",
         "punten": [{"tijd": "2026-10-05T12:00:00+02:00", "lat": 50.9, "lon": 4.6}], "indeling": [], "sporen": {}}
    js, md = E.bestanden_voor("2026-10-05", g)
    assert js and md and json.loads(js)["punten"], "een dag met een punt mag niet overgeslagen worden"


def test_nooit_een_dag_voor_de_startgrens():
    zet_doel()
    assert E.te_doen(args(dag="2026-10-02")) == []
    assert E.te_doen(args(dagen=30), vandaag="2026-10-05") == ["2026-10-03", "2026-10-04", "2026-10-05"]
    vm = VM({})
    E.over_ssh = vm
    sys.argv = ["x", "--dagen", "30", "--geen-kopie"]
    E.B.vandaag = lambda: __import__("datetime").date(2026, 10, 5)
    E.main()
    gevraagd = [o for o in vm.gevraagd if "/api/dagboek/" in o]
    assert gevraagd and all(o.split("/api/dagboek/")[1][:10] >= "2026-10-03" for o in gevraagd), gevraagd
    assert E.bestanden_voor("2026-10-02", {"buiten_reeks": True}) == (None, None)


def test_inhalen_vanaf_de_laatst_afgesloten_dag():
    zet_doel()
    assert E.te_doen(args(), vandaag="2026-10-06") == ["2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06"]
    assert E.bewaar_stand(["2026-10-03", "2026-10-04"]) == "2026-10-04"
    assert E.te_doen(args(), vandaag="2026-10-06") == ["2026-10-05", "2026-10-06"]


def test_een_herzien_dagboek_bewaart_de_vorige_versie_en_het_agendadeel_gaat_mee():
    doel = zet_doel()
    E.B.vandaag = lambda: __import__("datetime").date(2026, 10, 5)
    eerst = {"2026-10-05": {"datum": "2026-10-05", "status": "voorlopig", "markdown": "# Locatielogboek 2026-10-05 (voorlopig)\n",
                            "punten": [1], "sporen": {}}}
    E.over_ssh = VM(eerst, {"2026-10-05": "# x\n\n## Naast de agenda\n\nDoorgegaan volgens de locatie:\n- (geen)\n"})
    sys.argv = ["x", "--dag", "2026-10-05", "--geen-kopie"]
    E.main()
    md = open(os.path.join(doel, "dagen", "2026-10-05.md")).read()
    assert "(voorlopig)" in md and "## Naast de agenda" in md, md
    later = {"2026-10-05": dict(eerst["2026-10-05"], status="afgesloten", markdown="# Locatielogboek 2026-10-05\n",
                                punten=[1, 2])}
    E.over_ssh = VM(later)
    E.main()
    rev = os.listdir(os.path.join(doel, "dagen", "revisies"))
    assert len([r for r in rev if r.endswith(".md")]) == 1 and len([r for r in rev if r.endswith(".json")]) == 1, rev
    assert "(voorlopig)" not in open(os.path.join(doel, "dagen", "2026-10-05.md")).read()


def test_de_databasekopie_draagt_een_datum():
    import inspect
    bron = inspect.getsource(E.kopieer_database)
    assert '"locatie-%s.db" % date.today().isoformat()' in bron, "de kopie moet per dag een eigen naam krijgen"
    assert "os.remove" not in bron and "unlink" not in bron, "oude kopieën worden niet gewist"


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except AssertionError as e:
                fouten += 1
                print("   MISLUKT   %s: %s" % (naam, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)
