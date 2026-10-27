"""E1b: historische agendaopvraag blijft lezend, taken zijn begrensd en cron blijft afgebakend."""
import atexit
import io
import json
import os
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(__import__("tempfile").mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))  # nooit de echte wachtrij
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen"), str(ROOT / "planning")]
os.environ["BELLEN_UIT"] = "1"
PROEF_HOME = tempfile.TemporaryDirectory(prefix="agenda-terugkijken-proef-")
atexit.register(PROEF_HOME.cleanup)
os.environ["HOME"] = PROEF_HOME.name
import organisatie as ORGANISATIE  # noqa: E402
ORGANISATIE.firmas = lambda maximum_uren=24: [{"code": "HARC", "code_contact": "HA", "code_agenda": "HA",
                                                "naam": "H-Architects", "land": "BE", "actief": True}]
import agenda_wacht as W  # noqa: E402
import agenda_terugkijken_cron_zetten as CRON  # noqa: E402
with open(ROOT / "werkwijze" / "agenda-taken.json", encoding="utf-8") as bron:
    TITELREGELS = json.load(bron)["titelconventie"]
W.nummerlezer._master = lambda: TITELREGELS

DAG = "2025-06-06"
ACTIEF = next(k for k, naam in W.KALENDERS.items() if naam == "H-Architects")
ARCHIEF = "archief-voorbeeld@group.calendar.google.com"


def event(eid, titel, uur="10:00"):
    h, m = map(int, uur.split(":"))
    begin = datetime(2025, 6, 6, h, m, tzinfo=W.TIJDZONE)
    return {"id": eid, "summary": titel, "start": {"dateTime": begin.isoformat()},
            "end": {"dateTime": (begin + timedelta(hours=1)).isoformat()}}


class NepAgent:
    def __init__(self):
        self.items = []

    def werkwijze(self):
        return "E1b"

    def prive(self, _):
        pass

    def klaarzet(self, items):
        self.items.extend(items)
        return {"nieuw": len(items)}

    def log(self, *_args, **_kwargs):
        pass

    def log_verstuur(self):
        pass


class Terugkijken(unittest.TestCase):
    def setUp(self):
        self.agent = NepAgent()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(W, "ag", self.agent))
        self.stack.enter_context(patch.object(W.agenda, "beschikbaar", return_value=True))
        self.stack.enter_context(patch.object(W.agenda, "_toegang", return_value="fictief-token"))
        self.stack.enter_context(patch.object(W.agenda, "interne_adressen", return_value=set()))
        self.stack.enter_context(patch.object(W.agenda, "kalendernamen", return_value={ARCHIEF: "ZZ ARCHIEF H-A"}))
        self.stack.enter_context(patch.object(W, "deals_index", return_value=[
            {"id": 24, "nummer": "2405", "delen": set()}, {"id": 21, "nummer": "2145", "delen": set()}]))
        self.stack.enter_context(patch.object(W, "nu_lokaal", return_value=datetime(2026, 10, 18, tzinfo=W.TIJDZONE)))
        self.stack.enter_context(patch.dict(os.environ, {"AGENDA_KALENDERS": ACTIEF}))

        def schrijffout(*_args, **_kwargs):
            raise AssertionError("terugkijken raakt een schrijfroutine")

        # agenda.py schrijft normaal de lokale leesstand; ook die route staat in deze stand dicht.
        self.stack.enter_context(patch.object(W.agenda, "_leesstand_zet", side_effect=schrijffout))
        for naam in ("_patch", "_insert", "_verplaats", "_eigen_rit_weg", "kleur_actie",
                     "kleuren_zetten", "reistijd_zetten", "agendagasten_zetten", "zoom_zetten",
                     "titels_normaliseren", "titels_aanvullen", "uitroep_vooraan", "herinneringen_zetten",
                     "mail_meldingen", "zorg_afspraken_zetten", "projectnummers_zetten", "contact_zetten",
                     "bel_als_vastgelopen"):
            self.stack.enter_context(patch.object(W, naam, side_effect=schrijffout))

        self.methoden = []

        def google(req, timeout=30):
            self.methoden.append(req.get_method())
            if req.get_method() != "GET":
                raise AssertionError("Google-API kreeg een schrijfmethode")
            if "archief-voorbeeld" in req.full_url:
                gebeurtenissen = [event("archief-1", "!! Mehdi: [HA-KB] WB 2145 werfbezoek", "14:00")]
            else:
                gebeurtenissen = [event("ha-1", "!! Mehdi: 2405 plaatsbezoek (meetstaten bespreken)"),
                                  event("prive-1", "[PR] privégesprek", "16:00")]
            return io.BytesIO(json.dumps({"items": gebeurtenissen}).encode())

        self.stack.enter_context(patch.object(W.agenda.urllib.request, "urlopen", side_effect=google))

    def test_beide_standen_lezen_actieve_en_archiefagenda_zonder_schrijfroutes(self):
        self.assertEqual(W.terugkijkstand(["--terugkijken", DAG]), 0)
        eerste = list(self.agent.items)
        self.assertEqual(len(eerste), 2)
        self.assertEqual({i["uniek"] for i in eerste}, {f"agenda:{ACTIEF}:ha-1", f"agenda:{ARCHIEF}:archief-1"})
        self.assertTrue(all(i["inhoud"]["terugkijken"] is True for i in eerste))
        ha = next(i for i in eerste if i["inhoud"]["nummer"] == "2405")
        self.assertEqual((ha["voor"], ha["inhoud"]["firma"], ha["inhoud"]["type"]), ("h-architects", "", ""))
        self.assertTrue(ha["inhoud"]["buiten"])
        self.assertEqual(set(self.methoden), {"GET"})

        taken = [{"id": 11, "voor": W.NAAM, "van": "werfverslag-voorbereider", "soort": "taak",
                  "inhoud": json.dumps({"terugkijken": DAG, "dossier": "2405"})}]
        gepakt = []
        with patch.object(W.bord, "klaargezet_voor", return_value=taken), \
             patch.object(W.bord, "opgepakt", side_effect=lambda kid, door: gepakt.append((kid, door))):
            self.assertEqual(W.terugkijkstand(["--taken"]), 0)
        self.assertEqual(gepakt, [(11, W.NAAM)])
        self.assertEqual([i["uniek"] for i in self.agent.items[2:]], [i["uniek"] for i in eerste])
        self.assertEqual(set(self.methoden), {"GET"})

    def test_onvolledig_gelezen_dag_wordt_niet_klaargezet_of_afgevinkt(self):
        taak = {"id": 12, "voor": W.NAAM, "van": "werfverslag-voorbereider", "soort": "taak",
                "inhoud": {"terugkijken": DAG}}
        def onvolledig(*_args, **_kwargs):
            W.ONGELEZEN.add(ACTIEF)
            return []
        with patch.object(W, "afspraken_dag", side_effect=onvolledig), \
             patch.object(W, "archief_afspraken", return_value=[]), \
             patch.object(W.bord, "klaargezet_voor", return_value=[taak]), \
             patch.object(W.bord, "opgepakt") as pak:
            with self.assertRaisesRegex(RuntimeError, "niet volledig gelezen"):
                W.terugkijkstand(["--taken"])
            pak.assert_not_called()
        self.assertEqual(self.agent.items, [])
        W.ONGELEZEN.clear()

    def test_maximaal_veertig_unieke_oude_dagen_en_nieuwe_dagen_overslaan(self):
        dagen = [(datetime(2025, 1, 1) + timedelta(days=i)).date().isoformat() for i in range(45)]
        taken = [{"id": i + 1, "voor": W.NAAM, "van": "werfverslag-voorbereider", "soort": "taak",
                  "inhoud": {"terugkijken": dag}} for i, dag in enumerate(dagen)]
        taken += [{"id": 100, "voor": W.NAAM, "van": "werfverslag-voorbereider", "soort": "taak",
                   "inhoud": {"terugkijken": dagen[0]}},
                  {"id": 101, "voor": W.NAAM, "van": "werfverslag-voorbereider", "soort": "taak",
                   "inhoud": {"terugkijken": "2026-10-18"}},
                  {"id": 102, "voor": W.NAAM, "van": "werfverslag-voorbereider", "soort": "taak",
                   "inhoud": {"terugkijken": "2026-99-99"}},
                  {"id": 103, "voor": W.NAAM, "van": "andere-agent", "soort": "taak",
                   "inhoud": {"terugkijken": DAG}}]
        gevraagd, gepakt = [], []
        with patch.object(W.bord, "klaargezet_voor", return_value=taken), \
             patch.object(W.bord, "opgepakt", side_effect=lambda kid, door: gepakt.append(kid)), \
             patch.object(W, "terugkijkdag", side_effect=lambda dag, deals: gevraagd.append(dag)):
            self.assertEqual(W.terugkijktaken(), 40)
        self.assertEqual(gevraagd, dagen[:40])
        self.assertIn(100, gepakt)
        self.assertIn(101, gepakt)
        self.assertNotIn(102, gepakt)
        self.assertNotIn(103, gepakt)
        self.assertNotIn(45, gepakt)

    def test_ongeldige_of_niet_oude_directe_dag_stopt_voor_bronlezing(self):
        with patch.object(W, "deals_index") as deals:
            self.assertEqual(W.terugkijkstand(["--terugkijken", "2026-99-99"]), 2)
            self.assertEqual(W.terugkijkstand(["--terugkijken", "2026-10-18"]), 2)
            deals.assert_not_called()
        self.assertEqual(self.agent.items, [])


class Planning(unittest.TestCase):
    def test_master_noemt_de_lezende_terugkijkstand(self):
        master = json.loads((ROOT / "werkwijze" / "agenda-taken.json").read_text())
        wachten = [w for w in master["wachten"] if w["naam"] == "Terugkijken op vraag"]
        self.assertEqual(len(wachten), 1)
        self.assertIn("--taken", wachten[0]["bestand"])
        self.assertIn("--terugkijken", wachten[0]["bestand"])
        self.assertIn("geen agenda-afspraak", wachten[0]["wat"])

    def test_eigen_blok_en_proef_zonder_crontab_schrijven(self):
        regels = (ROOT / "planning" / "agenda-terugkijken.cron").read_text().splitlines()
        self.assertEqual(len(regels), 1)
        self.assertTrue(regels[0].startswith("40 */2 * * * /usr/bin/flock -n "))
        self.assertIn("/usr/bin/timeout", regels[0])
        huidig = ["1 1 * * * een geheim", CRON.BEGIN, "oude eigen regel", CRON.EINDE,
                  "2 2 * * * andere taak"]
        doel = CRON.samenvoegen(huidig, regels)
        self.assertEqual([x for x in doel if x in huidig and x not in (CRON.BEGIN, CRON.EINDE)],
                         ["1 1 * * * een geheim", "2 2 * * * andere taak"])
        self.assertNotIn("oude eigen regel", doel)
        meting = SimpleNamespace(returncode=0, stderr="", stdout="\n".join(huidig) + "\n")
        with patch.object(CRON.subprocess, "run", return_value=meting) as run, \
             patch("sys.stdout", new_callable=io.StringIO) as uitvoer:
            self.assertEqual(CRON.main([]), 0)
        run.assert_called_once_with(["crontab", "-l"], capture_output=True, text=True)
        self.assertNotIn("een geheim", uitvoer.getvalue())
        with self.assertRaises(ValueError):
            CRON.samenvoegen([CRON.BEGIN, "halve planning"], regels)
        with self.assertRaisesRegex(ValueError, "buiten het eigen blok"):
            CRON.samenvoegen(["40 */2 * * * python agenda_wacht.py --taken"], regels)

    def test_zetten_schrijft_alleen_eigen_blok_en_leest_terug(self):
        bestaand = ["1 1 * * * andere taak"]
        geschreven = []
        meting = SimpleNamespace(returncode=0, stderr="", stdout="\n".join(bestaand) + "\n")

        def crontab(args, **kwargs):
            if args == ["crontab", "-"]:
                geschreven.append(kwargs["input"])
                return SimpleNamespace(returncode=0)
            if geschreven:
                return SimpleNamespace(returncode=0, stderr="", stdout=geschreven[0])
            return meting

        with patch.object(CRON.subprocess, "run", side_effect=crontab), \
             patch("sys.stdout", new_callable=io.StringIO):
            self.assertEqual(CRON.main(["--zet"]), 0)
        self.assertEqual(len(geschreven), 1)
        self.assertEqual(geschreven[0].splitlines()[0], bestaand[0])
        self.assertIn(CRON.BEGIN, geschreven[0])
        self.assertIn(CRON.EINDE, geschreven[0])


if __name__ == "__main__":
    unittest.main(verbosity=1)
