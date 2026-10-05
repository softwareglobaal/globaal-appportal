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
    def __init__(self, dagboeken, wacht=None, revisies=None):
        self.dagboeken, self.wacht, self.gevraagd, self.revisies = dagboeken, wacht or {}, [], revisies or {}

    def __call__(self, opdracht, pogingen=3, wacht=20):
        self.gevraagd.append(opdracht)
        if "/api/revisies" in opdracht:
            return json.dumps({"revisies": self.revisies})
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


def test_een_grote_achterstand_begint_bij_de_oudste_open_dag():
    """Controle 05-10-2026: bij meer dan 31 open dagen koos de inhaal de laatste 31."""
    zet_doel()
    dagen = E.te_doen(args(), vandaag="2026-11-10")
    assert dagen[0] == "2026-10-03" and len(dagen) == E.INHAAL_MAX, (dagen[0], len(dagen))


def test_na_meerdere_dagen_uitval_worden_alle_dagen_ingehaald_en_gelijk_aan_de_tegel():
    """Weekenduitval: de Mac draaide niet van 5 tot 9 oktober. Daarna komen alle dagen binnen, de
    oudste eerst, elk gelijk aan wat de tegel nu zegt."""
    doel = zet_doel()
    E.bewaar_stand(["2026-10-03", "2026-10-04"], {"2026-10-03": "a", "2026-10-04": "b"})
    E.B.vandaag = lambda: __import__("datetime").date(2026, 10, 10)
    boeken = {d: {"datum": d, "status": "afgesloten", "versie": "v-" + d, "markdown": "# Locatielogboek %s\n" % d,
                  "punten": [1], "sporen": {}} for d in ("2026-10-0%d" % i for i in range(5, 10))}
    boeken["2026-10-10"] = dict(boeken["2026-10-05"], datum="2026-10-10", status="voorlopig", versie="v-10")
    vm = VM(boeken, revisies={"2026-10-03": {"versie": "a"}, "2026-10-04": {"versie": "b"}})
    E.over_ssh = vm
    sys.argv = ["x", "--geen-kopie"]
    E.main()
    gevraagd = [o.split("/api/dagboek/")[1][:10] for o in vm.gevraagd if "/api/dagboek/" in o]
    assert gevraagd == ["2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08", "2026-10-09", "2026-10-10"], gevraagd
    for d in gevraagd[:-1]:
        assert json.loads(open(os.path.join(doel, "dagen", "%s.json" % d)).read())["versie"] == "v-" + d
    assert E.lees_stand() == "2026-10-09"


def test_een_late_revisie_van_een_afgesloten_dag_wordt_opnieuw_opgehaald():
    """Een late meting of correctie voor 5 oktober, terwijl de stand al op 8 oktober stond."""
    doel = zet_doel()
    E.bewaar_stand(["2026-10-03", "2026-10-04", "2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"],
                   {"2026-10-05": "oud"})
    E.B.vandaag = lambda: __import__("datetime").date(2026, 10, 8)
    nieuw = {"2026-10-05": {"datum": "2026-10-05", "status": "afgesloten", "versie": "nieuw",
                            "markdown": "# Locatielogboek 2026-10-05\nherzien\n", "punten": [1, 2], "sporen": {}}}
    vm = VM(nieuw, revisies={"2026-10-05": {"versie": "nieuw"}})
    E.over_ssh = vm
    sys.argv = ["x", "--geen-kopie"]
    E.main()
    assert any("/api/dagboek/2026-10-05" in o for o in vm.gevraagd), vm.gevraagd
    assert "herzien" in open(os.path.join(doel, "dagen", "2026-10-05.md")).read()
    assert E.lees_volledige_stand()["versies"]["2026-10-05"] == "nieuw"


def test_een_onbereikbare_revisie_index_is_een_fout_en_de_herziening_komt_later_alsnog():
    """Nacontrole v1.5: /api/revisies faalde terwijl een afgesloten dag een nieuwe versie had. De open
    dagen kwamen binnen, de herziening niet, en toch meldde de taak 'gelukt' met exit 0."""
    doel = zet_doel()
    E.bewaar_stand(["2026-10-03", "2026-10-04", "2026-10-05"], {"2026-10-05": "oud"})
    E.B.vandaag = lambda: __import__("datetime").date(2026, 10, 6)
    boeken = {"2026-10-05": {"datum": "2026-10-05", "status": "afgesloten", "versie": "nieuw",
                             "markdown": "# Locatielogboek 2026-10-05\nherzien\n", "punten": [1], "sporen": {}},
              "2026-10-06": {"datum": "2026-10-06", "status": "voorlopig", "versie": "v6",
                             "markdown": "# Locatielogboek 2026-10-06\n", "punten": [1], "sporen": {}}}

    class IndexWeg(VM):
        def __call__(self, opdracht, pogingen=3, wacht=20):
            if "/api/revisies" in opdracht:
                self.gevraagd.append(opdracht)
                raise SystemExit("SSH mislukt (proef)")
            return VM.__call__(self, opdracht, pogingen, wacht)
    vm = IndexWeg(boeken, revisies={"2026-10-05": {"versie": "nieuw"}})
    E.over_ssh = vm
    sys.argv = ["x", "--geen-kopie"]
    assert E.main() == 1, "een gemiste revisie-index is geen geslaagde export"
    melding = [o for o in vm.gevraagd if "beheer.py taak export" in o]
    assert melding and " fout " in melding[-1] and "revisie-index" in melding[-1], melding
    assert os.path.exists(os.path.join(doel, "dagen", "2026-10-06.md")), "de open dag gaat wel door"
    assert not any("/api/dagboek/2026-10-05" in o for o in vm.gevraagd)
    assert E.lees_volledige_stand()["versies"]["2026-10-05"] == "oud", "de gemiste herziening blijft open"
    # De index werkt weer: de herziening komt binnen en de taak slaagt.
    vm = VM(boeken, revisies={"2026-10-05": {"versie": "nieuw"}, "2026-10-06": {"versie": "v6"}})
    E.over_ssh = vm
    assert E.main() == 0
    assert "herzien" in open(os.path.join(doel, "dagen", "2026-10-05.md")).read()
    assert E.lees_volledige_stand()["versies"]["2026-10-05"] == "nieuw"
    assert " ok " in [o for o in vm.gevraagd if "beheer.py taak export" in o][-1]


def test_het_agendadeel_komt_alleen_mee_bij_dezelfde_dagboekversie():
    E.over_ssh = VM({}, {"2026-10-05": "# x\n\n## Naast de agenda\n\n- (geen)\n<!-- dagboekversie v1 -->\n"})
    assert "dagboekversie v1" in E.agenda_deel("2026-10-05", "v1")
    assert "Volgt na de volgende ronde" in E.agenda_deel("2026-10-05", "v2")


def test_een_dag_zonder_toestelconfiguratie_wordt_niet_afgesloten():
    zet_doel()
    E.B.vandaag = lambda: __import__("datetime").date(2026, 10, 4)
    E.over_ssh = VM({d: {"datum": d, "status": "niet ingesteld", "versie": "x", "markdown": "# x\n", "punten": [],
                         "sporen": {}} for d in ("2026-10-03", "2026-10-04")})
    sys.argv = ["x", "--geen-kopie"]
    E.main()
    assert E.lees_stand() == ""


def test_de_launchd_taak_beperkt_de_export_niet_tot_twee_dagen():
    plist = os.path.expanduser("~/Library/LaunchAgents/com.mehdi.locatielogboek.plist")
    if not os.path.exists(plist):
        return                    # alleen op de Mac van Mehdi
    assert "--dagen" not in open(plist, encoding="utf-8").read(), "launchd geeft nog --dagen mee"


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except Exception as e:  # noqa: BLE001
                fouten += 1
                print("   MISLUKT   %s: %s: %s" % (naam, type(e).__name__, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)
