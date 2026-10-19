"""De Tekenaar (tekenaar.py en koppelingen/ba_plannen.py), vastgezet. Ontwerplezing Codex DT01, DT02 en DT05, 18-10-2026.

Wat hier vastligt:
  - nieuw is een inhoud die De Tekenaar nog niet zag; een kopie of een verplaatst plan (een project dat van fasemap
    verandert) niet; wat voor de archiefcontrole van oktober 2026 laatst gewijzigd is, telt bij de eerste lijst als
    bekeken;
  - een plan uit de wachtrij dat verdwijnt, wordt vervangen door een plan met dezelfde inhoud, of valt terug;
  - een signaal voor Mehdi alleen bij een FOUT, een per week, zonder aantal in het uniek en zonder het woord "stil";
  - de werkmap ligt nooit in Dropbox, en de ronde van een week die al gelukt is, draait niet opnieuw;
  - een volledige ronde gaat door de gedeelde ag.ronde: hartslag, werkwijze, lessen, collega's en kennis (N4, N11 tot
    N14), ook als er niets nieuw is; zonder hulpscript op de VM een nood en geen afgevinkte week;
  - het hulpscript op de VM leest alleen BA-plannen onder de twee projectmappen.

Geen netwerk, geen ssh, geen Dropbox en geen PyMuPDF: het bord, de VM en de normcontrole worden nagebootst.
Draaien: python3 mijnagents-runner/tests/test_tekenaar.py
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
sys.path.insert(0, RUNNER)
import bord  # noqa: E402
import ba_plannen  # noqa: E402
import tekenaar as tk  # noqa: E402

S = "/Work All/01. H-A WORK/0 H-A Standaard projects"
L = "/Work All/01. H-A WORK/0 H-A Light projects"


def plan(i, pad, h, gewijzigd="2026-10-19T08:00:00Z"):
    return {"soort": "bestand", "id": f"id:proef{i:04d}", "pad": pad, "hash": h, "gewijzigd": gewijzigd}


P1 = f"{S}/2. STAN permission Awaited/9901 Proefstraat 1, 3120 Tremelo (stan)/3. Bouwaanvraag/2. PDF/BA_Proefstraat 1, 3120 Tremelo_P_N_1_00_gelijkvloers.pdf"
P2 = f"{S}/2. STAN permission Awaited/9901 Proefstraat 1, 3120 Tremelo (stan)/3. Bouwaanvraag/2. PDF/BA_Proefstraat 1, 3120 Tremelo_G_N_1_A_voorgevel.pdf"
P3 = f"{L}/3. H-A light permission received/9902 Proeflaan 2, 1000 Brussel/BA_Proeflaan 2, 1000 Brussel_P_B_1_00_gelijkvloers.pdf"


class NepNormcontrole:
    """Zoals normcontrole.py: FOUT voor een blad met _G_ (meetlijn), gewest FOUT voor Brussel, de rest OK."""

    def controleer_pdf(self, pdf, naam=None, map_naam=None):
        with open(pdf, "rb") as f:
            assert f.read(4) == b"%PDF"
        u = {"bestandsnaam": {"status": "OK", "reden": "volgt de code", "artikel": ""}}
        if "_G_" in naam:
            u["meetlijn"] = {"status": "FOUT", "reden": "5 m gemeten 25 mm, bij 1/100 hoort 50 mm", "artikel": "1.3.2"}
        if "1000 Brussel" in (naam or ""):
            u["gewest"] = {"status": "FOUT", "reden": "Brussel volgens de postcode", "artikel": "B01"}
        u["eenheid"] = {"status": "LET OP", "reden": "proef", "artikel": ""}
        statussen = {v["status"] for v in u.values()}
        return {"uitkomsten": u, "oordeel": next(s for s in ("FOUT", "ONBEKEND", "LET OP", "OK") if s in statussen | {"OK"})}

    def controleer_set(self, namen, regularisatie=None, nieuw=None):
        dubbel = len(namen) != len(set(n.rsplit("_", 1)[0] for n in namen))
        u = {"bladnummers": {"status": "FOUT" if dubbel else "OK", "reden": "dubbel" if dubbel else "ok", "artikel": ""}}
        return {"uitkomsten": u, "oordeel": "FOUT" if dubbel else "OK", "deelsets": {}}


def nep_haal(ident, doel):
    if ident.endswith("weg1"):
        return False
    with open(doel, "wb") as f:
        f.write(b"%PDF-1.7 proef")
    return True


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        oud = {k: getattr(tk, k) for k in ("STAND", "WERKMAP", "DROPBOX", "TOKEN_PAD")}
        self.addCleanup(lambda: [setattr(tk, k, v) for k, v in oud.items()])
        tk.STAND = os.path.join(self.tmp.name, "stand", "stand.json")
        tk.WERKMAP = os.path.join(self.tmp.name, "cache")
        tk.DROPBOX = os.path.join(self.tmp.name, "Dropbox")


class Selectie(Basis):
    def test_eerste_lijst_basis_en_nieuw(self):
        st = tk.lege_stand()
        lijst = {"cursors": {"standaard": "c1"}, "wijzigingen": [
            plan(1, P1, "h1", "2026-09-01T10:00:00Z"),              # voor de archiefcontrole: bekeken
            plan(2, P2, "h2", "2026-10-19T08:00:00Z"),              # erna: nieuw
            plan(3, P1.replace(".pdf", ".dwg"), "h3")]}             # geen BA-pdf
        nieuw, weg = tk.selecteer(st, lijst)
        self.assertEqual((nieuw, weg), (1, 0))
        self.assertEqual(st["gezien"]["h1"]["status"], "basis")
        self.assertEqual(st["wachtrij"], ["id:proef0002"])
        self.assertEqual(st["cursors"], {"standaard": "c1"})
        self.assertEqual(set(st["bekend"]), {"id:proef0001", "id:proef0002"})

    def test_kopie_en_verplaatsing_zijn_niet_nieuw(self):
        st = tk.lege_stand()
        tk.selecteer(st, {"wijzigingen": [plan(1, P1, "h1", "2026-09-01T10:00:00Z")]})
        verhuisd = P1.replace("2. STAN permission Awaited", "3. STAN permission received")
        nieuw, weg = tk.selecteer(st, {"wijzigingen": [
            {"soort": "weg", "pad": os.path.dirname(os.path.dirname(os.path.dirname(P1))).lower()},
            plan(1, verhuisd, "h1"),
            plan(9, P1.replace("2. PDF", "8. Latest PDF for Meetings"), "h1")]})
        self.assertEqual(nieuw, 0)
        self.assertEqual(st["wachtrij"], [])
        self.assertEqual(st["bekend"]["id:proef0001"]["pad"], verhuisd)
        self.assertIn("id:proef0009", st["bekend"])
        # Een gewijzigde inhoud is wel nieuw, ook na de eerste lijst en ook als het plan oud gedateerd is.
        nieuw, _ = tk.selecteer(st, {"wijzigingen": [plan(1, verhuisd, "h1b", "2026-01-01T00:00:00Z")]})
        self.assertEqual(nieuw, 1)
        self.assertEqual(st["wachtrij"], ["id:proef0001"])

    def test_verdwenen_plan_uit_de_wachtrij(self):
        st = tk.lege_stand()
        st["gezien"]["iets"] = {"status": "basis"}                   # niet de eerste lijst
        tk.selecteer(st, {"wijzigingen": [plan(2, P2, "h2"), plan(7, P2.replace("2. PDF", "kopie"), "h2")]})
        self.assertEqual(st["wachtrij"], ["id:proef0002"])
        tk.selecteer(st, {"wijzigingen": [{"soort": "weg", "pad": P2.lower()}]})
        self.assertEqual(st["wachtrij"], ["id:proef0007"])          # dezelfde inhoud neemt de plaats
        tk.selecteer(st, {"wijzigingen": [{"soort": "weg", "pad": P2.replace("2. PDF", "kopie").lower()}]})
        self.assertEqual(st["wachtrij"], [])
        self.assertNotIn("h2", st["gezien"])                        # komt ze terug, dan is ze nieuw

    def test_projectnummer_en_pad(self):
        self.assertEqual(tk.projectnummer(P1)[0], "9901")
        self.assertEqual(tk.projectnummer(P3)[0], "9902")
        self.assertEqual(tk.projectnummer(f"{L}/1. H-A light Submission/3.H-A light Subm/BA_x_P_N.pdf")[0], "zonder nummer")
        self.assertTrue(tk.kort_pad(P1).startswith("2. STAN permission Awaited/9901"))


class Controle(Basis):
    def test_wachtrij_controleren_en_stand(self):
        st = tk.lege_stand()
        st["gezien"]["iets"] = {"status": "basis"}
        tk.selecteer(st, {"wijzigingen": [plan(1, P1, "h1"), plan(2, P2, "h2"),
                                          {"soort": "bestand", "id": "id:proefweg1", "pad": P3, "hash": "h3"}]})
        gecontroleerd, ids, verdwenen = tk.controleer_wachtrij(NepNormcontrole(), st, haal=nep_haal)
        self.assertEqual((len(gecontroleerd), verdwenen), (2, 1))
        self.assertEqual(st["gezien"]["h2"]["status"], "gecontroleerd")
        self.assertEqual(st["gezien"]["h2"]["fout"], ["meetlijn"])
        self.assertEqual(st["wachtrij"], [])
        self.assertNotIn("id:proefweg1", st["bekend"])
        self.assertTrue(os.path.exists(tk.STAND))                    # na elk plan bewaard
        self.assertEqual(os.listdir(tk.WERKMAP), [])                 # geen PDF blijft achter

    def test_werkmap_nooit_in_dropbox(self):
        tk.WERKMAP = os.path.join(tk.DROPBOX, "Work All", "cache")
        with self.assertRaisesRegex(RuntimeError, "Dropbox"):
            tk.veilige_werkmap()

    def test_signaal_alleen_bij_fout(self):
        ok = (P1, {"oordeel": "LET OP", "fout": [], "fout_soorten": []})
        self.assertIsNone(tk.signaal([ok], {}, "2026-W43", "abc1234"))
        fout = (P2, {"oordeel": "FOUT", "fout": ["meetlijn: 5 m gemeten 25 mm"], "fout_soorten": ["meetlijn"]})
        item = tk.signaal([ok, fout], {os.path.dirname(P3): [("bladnummers", "dubbel")]}, "2026-W43", "abc1234")
        self.assertEqual((item["voor"], item["soort"], item["uniek"]), ("mehdi", "signaal", "tekenaar-normcontrole-2026-W43"))
        self.assertIn("9901", item["titel"])
        self.assertIn("9902", item["titel"])
        self.assertNotIn("stil", item["titel"].lower())
        self.assertLessEqual(len(item["titel"]), 160)
        self.assertTrue(any("Teken-agent-map" in v for v in item["inhoud"]["voorstel"]))
        projecten = {p["project"]: p for p in item["inhoud"]["projecten"]}
        self.assertEqual(projecten["9901"]["bladen"][0]["fouten"], ["meetlijn: 5 m gemeten 25 mm"])
        self.assertEqual(projecten["9902"]["set"], ["dubbele bladcode: dubbel"])


class NepBord:
    """Vangt op wat de ronde naar het bord stuurt (bord.call), zonder netwerk."""

    def __init__(self, werkwijze):
        self.werkwijze = werkwijze
        self.oproepen = []

    def __call__(self, pad, payload=None, method=None):
        self.oproepen.append((pad, payload))
        if pad == "/api/agent/tekenaar/werkwijze":
            return {"werkwijze": self.werkwijze}
        if pad == "/api/agents":
            return [{"naam": "bode", "label": "De Bode", "type": "regie", "rol": "brengt naar Telegram", "actief": 1}]
        if pad == "/api/nood":
            return {"nood": []}
        if pad == "/api/klaarzet":
            return {"nieuw": len(payload["items"]), "bestaand": 0}
        return {"ok": True}

    def van(self, pad):
        return [p for q, p in self.oproepen if q == pad]


class Ronde(Basis):
    def setUp(self):
        super().setUp()
        with open(os.path.join(RUNNER, "werkwijze", "tekenaar.md"), encoding="utf-8") as f:
            self.nep = NepBord(f.read())
        self.lijst = {"cursors": {"standaard": "c2", "light": "c3"}, "wijzigingen": []}
        vervang = {"call": (bord, self.nep), "tunnel": (tk, self._tunnel), "hulp_versie": (tk, lambda: tk.HULP_VERSIE),
                   "lijst_van_vm": (tk, lambda c: json.loads(json.dumps(self.lijst))), "haal_van_vm": (tk, nep_haal),
                   "normcontrole": (tk, NepNormcontrole),
                   "regelboek": (tk, lambda: ({"normcontrole.py": "code", "normenboek-B01-checklist.md": "lijst",
                                               "globaal-vectorworks-brug": "commit abc1234"}, "abc1234", False))}
        oud = {k: getattr(m, k) for k, (m, _) in vervang.items()}
        for k, (m, v) in vervang.items():
            setattr(m, k, v)
        oud_bord = (bord.PLATFORM, bord.TOKEN)
        self.addCleanup(lambda: [setattr(m, k, oud[k]) for k, (m, _) in vervang.items()])
        self.addCleanup(lambda: (setattr(bord, "PLATFORM", oud_bord[0]), setattr(bord, "TOKEN", oud_bord[1])))
        tk.TOKEN_PAD = os.path.join(self.tmp.name, "token")
        with open(tk.TOKEN_PAD, "w") as f:
            f.write("proeftoken")

    @contextlib.contextmanager
    def _tunnel(self):
        yield "http://127.0.0.1:1"

    def draai(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return tk.main(list(argv))

    def test_ronde_zonder_nieuwe_plannen_geeft_hartslag_en_kennis(self):
        self.assertEqual(self.draai(), 0)
        slagen = self.nep.van("/agent-status")
        self.assertEqual(slagen[0]["status"], "actief")
        self.assertEqual(slagen[-1]["status"], "klaar")
        kennis = self.nep.van("/api/agent/tekenaar/kennis")[-1]["bron"]
        for bron in ("werkwijze op het bord", "gedeelde lessen", "collega's op het bord", "normcontrole.py",
                     "normenboek-B01-checklist.md", "globaal-vectorworks-brug"):
            self.assertIn(bron, kennis)
        self.assertEqual(self.nep.van("/api/klaarzet"), [])
        st = tk.lees_stand()
        self.assertEqual(st["laatste_week"], tk.week())
        self.assertEqual(st["cursors"], {"standaard": "c2", "light": "c3"})
        # Dezelfde week opnieuw: niets, geen tunnel en geen hartslag (launchd start me dagelijks voor de inhaalronde).
        tk.tunnel = lambda: (_ for _ in ()).throw(AssertionError("geen tunnel verwacht"))
        voor = len(self.nep.oproepen)
        self.assertEqual(self.draai(), 0)
        self.assertEqual(len(self.nep.oproepen), voor)

    def test_ronde_met_fout_zet_een_signaal(self):
        st = tk.lege_stand()
        st["gezien"]["oud"] = {"status": "basis"}
        tk.bewaar_stand(st)
        self.lijst["wijzigingen"] = [plan(1, P1, "h1"), plan(2, P2, "h2")]
        self.assertEqual(self.draai("--nu"), 0)
        items = self.nep.van("/api/klaarzet")[0]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["van"], items[0]["soort"]), ("tekenaar", "signaal"))
        verslag = [r for p in self.nep.van("/api/logboek") for r in p["regels"]]
        self.assertTrue(any(r["onderwerp"] == "project 9901" for r in verslag))
        self.assertIn("FOUT 1", self.nep.van("/agent-status")[-1]["detail"])

    def test_zonder_hulpscript_op_de_vm_een_nood_en_geen_afgevinkte_week(self):
        tk.hulp_versie = lambda: None
        self.assertEqual(self.draai(), 1)
        laatste = self.nep.van("/agent-status")[-1]
        self.assertEqual(laatste["status"], "waakt")
        self.assertTrue(any("ba_plannen.py" in n["tekst"] for n in laatste["nood"]))
        self.assertIsNone(tk.lees_stand()["laatste_week"])

    def test_werkwijze_en_doorgang(self):
        with open(os.path.join(RUNNER, "tekenaar.py"), encoding="utf-8") as f:
            self.assertIn("with ag.ronde(", f.read())                # N12
        spec = importlib.util.spec_from_file_location("nieuwe_agent", os.path.join(RUNNER, "nieuwe-agent.py"))
        na = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(na)
        kaart = dict(naam="tekenaar", label="De Tekenaar", rol="x", mandaat="x", cadans="elke week", mag=["a"], grenzen=["b"])
        self.assertEqual(na.controleer(kaart, self.nep.werkwijze), [])
        nooit, mehdi = bord.grenzen(self.nep.werkwijze)
        self.assertTrue(any("projectmap" in n for n in nooit))


class Hulpscript(unittest.TestCase):
    def test_lijst_pagineert_en_filtert(self):
        paginas = {
            ("files/list_folder", S): {"entries": [
                {".tag": "file", "id": "id:aaaaaa1", "name": "BA_x_P_N.pdf", "path_display": S + "/9901 x/BA_x_P_N.pdf",
                 "content_hash": "h", "server_modified": "2026-10-19T08:00:00Z"},
                {".tag": "file", "id": "id:aaaaaa2", "name": "plan.pdf", "path_display": S + "/9901 x/plan.pdf"},
                {".tag": "folder", "id": "id:aaaaaa3", "name": "9901 x"}], "has_more": True, "cursor": "s1"},
            ("files/list_folder/continue", "s1"): {"entries": [
                {".tag": "deleted", "name": "oud.dwg", "path_lower": S.lower() + "/oud.dwg"},
                {".tag": "deleted", "name": "9800 weg", "path_lower": S.lower() + "/9800 weg"}],
                "has_more": False, "cursor": "s2"},
            ("files/list_folder/continue", "verlopen"): urllib.error.HTTPError("u", 409, "reset", {}, None),
            ("files/list_folder", L): {"entries": [], "has_more": False, "cursor": "l1"},
        }

        def rpc(pad, body):
            antwoord = paginas[(pad, body.get("path") or body.get("cursor"))]
            if isinstance(antwoord, Exception):
                raise antwoord
            return antwoord

        uit = ba_plannen.lijst({"light": "verlopen"}, rpc=rpc)
        self.assertEqual(uit["cursors"], {"standaard": "s2", "light": "l1"})
        self.assertEqual(uit["volledig"], {"standaard": True, "light": True})
        self.assertEqual([w["soort"] for w in uit["wijzigingen"]], ["bestand", "weg"])
        self.assertEqual(uit["wijzigingen"][0]["hash"], "h")
        self.assertEqual(uit["wijzigingen"][1]["pad"], S.lower() + "/9800 weg")

    def test_haal_alleen_ba_plannen_in_de_projectmappen(self):
        def meta(naam, pad):
            return lambda p, b: {".tag": "file", "name": naam, "path_lower": pad.lower(), "size": 10}
        download = lambda pad, maximum: b"%PDF"  # noqa: E731
        self.assertEqual(ba_plannen.haal("id:aaaaaa1", meta("BA_x_P_N.pdf", S + "/9901/BA_x_P_N.pdf"), download), b"%PDF")
        with self.assertRaises(PermissionError):
            ba_plannen.haal("id:aaaaaa1", meta("contract.pdf", S + "/9901/contract.pdf"), download)
        with self.assertRaises(PermissionError):
            ba_plannen.haal("id:aaaaaa1", meta("BA_x_P_N.pdf", "/Work All/o01. Sales/BA_x_P_N.pdf"), download)
        with self.assertRaises(PermissionError):
            ba_plannen.haal("id:aaaaaa1", lambda p, b: None, download)
        with self.assertRaises(ValueError):
            ba_plannen.haal("/Work All/geheim.pdf; rm -rf", meta("BA_x.pdf", S + "/BA_x.pdf"), download)


if __name__ == "__main__":
    unittest.main(verbosity=2)
