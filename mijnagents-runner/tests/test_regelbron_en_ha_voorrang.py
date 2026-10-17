"""H1-4, driehoeksoverleg C2, 17-10-2026: regelbron en H-A-dekking."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER))
sys.path.insert(0, str(RUNNER / "koppelingen"))
oud = os.environ.get("H1_TEST_OUDE_MODULE")
if oud:
    spec = importlib.util.spec_from_file_location("naamstructuur", oud)
    N = importlib.util.module_from_spec(spec)
    sys.modules["naamstructuur"] = N
    spec.loader.exec_module(N)
else:
    import naamstructuur as N
oude_ronde = os.environ.get("H1_TEST_OUDE_RONDE")
if oude_ronde:
    spec = importlib.util.spec_from_file_location("naamstructuur_ronde", oude_ronde)
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
else:
    import naamstructuur_ronde as R


class RegelbronEnHATest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.c = N.open_db(str(Path(self.tmp.name) / "index.sqlite3"))
        self.regels = copy.deepcopy(N.lees_regels(str(RUNNER / "werkwijze" / "naamstructuur-regels.json")))
        self.regels["roots"] = self.regels["roots"][:1]
        self.root = self.regels["roots"][0]
        self.ha = self.regels["profielen"][0]["prefix"]
        with self.c:
            N.instelling(self.c, "regelbron", {"geldig": True})

    def tearDown(self):
        self.c.close()
        self.tmp.cleanup()

    def scope(self, id, pad, compleet, meer, fout=""):
        with self.c:
            self.c.execute("INSERT INTO scope(id,pad,namespace,verbinding,compleet,meer,fout) VALUES(?,?,?,?,?,?,?)",
                           (id, pad, self.root["namespace"], self.root["verbinding"], compleet, meer, fout))

    def item(self, id, pad):
        firma, profiel = N.profiel_van(pad, self.regels)
        with self.c:
            self.c.execute("INSERT INTO item(scope,identiteit,pad,pad_sleutel,naam,soort,firma,profiel) VALUES(?,?,?,?,?,'folder',?,?)",
                           (self.root["id"], id, pad, pad.casefold(), Path(pad).name, firma, profiel))

    def test_ha_eigen_dekking_en_voorrang(self):
        self.scope(self.root["id"], self.root["pad"], 0, 1)
        self.item("ander", "/Work All/gewone:map")
        self.item("ha", self.ha + "/foute:map")
        bereiken = N.ha_bereiken(self.regels)
        for b, _ in bereiken:
            self.scope(b["id"], b["pad"], int(b["pad"] == self.ha), int(b["pad"] != self.ha))
        self.assertEqual(N.toets_index(self.c, "benamingen-wacht", self.regels, budget=1), 1)
        self.assertEqual(self.c.execute("SELECT naam_vuil FROM item WHERE identiteit='ha'").fetchone()[0], 0)
        self.assertEqual(self.c.execute("SELECT naam_vuil FROM item WHERE identiteit='ander'").fetchone()[0], 1)
        self.c.execute("UPDATE scope SET fout='Work All tijdelijk onleesbaar' WHERE id=?", (self.root["id"],))
        self.c.execute("UPDATE item SET naam_vuil=1 WHERE identiteit='ha'")
        self.c.commit()
        self.assertEqual(N.toets_index(self.c, "benamingen-wacht", self.regels, budget=1), 1)
        self.assertEqual(self.c.execute("SELECT naam_vuil FROM item WHERE identiteit='ha'").fetchone()[0], 0)
        self.assertEqual(self.c.execute("SELECT count(*) FROM bevinding WHERE identiteit='ha'").fetchone()[0], 1)
        self.c.execute("UPDATE scope SET fout='' WHERE id=?", (self.root["id"],))
        self.c.execute("UPDATE scope SET compleet=1,meer=0 WHERE id=?", (self.root["id"],))
        self.c.execute("UPDATE item SET naam_vuil=1")
        self.c.commit()
        self.assertEqual(N.toets_index(self.c, "benamingen-wacht", self.regels, budget=1), 1)
        self.assertEqual(self.c.execute("SELECT naam_vuil FROM item WHERE identiteit='ha'").fetchone()[0], 0)
        self.assertEqual(self.c.execute("SELECT naam_vuil FROM item WHERE identiteit='ander'").fetchone()[0], 1)
        self.c.execute("UPDATE scope SET compleet=0,meer=1 WHERE id=?", (bereiken[0][0]["id"],))
        self.c.execute("UPDATE item SET naam_vuil=1 WHERE identiteit='ha'")
        self.c.commit()
        self.assertEqual(N.toets_index(self.c, "benamingen-wacht", self.regels, budget=1), 1)
        self.assertEqual(self.c.execute("SELECT naam_vuil FROM item WHERE identiteit='ha'").fetchone()[0], 1)

    def test_bestaande_index_en_cursor_blijven_zonder_dubbele_items(self):
        kind = self.ha + "/foute:map"
        self.item("ha", kind)  # Al in de bestaande Work All-index vóór de uitrol.
        self.c.execute("UPDATE item SET naam_vuil=0,structuur_vuil=0 WHERE identiteit='ha'")
        self.c.commit()
        def folder(id, pad):
            return {"id": id, "path_display": pad, "name": Path(pad).name, ".tag": "folder"}
        def rpc(route, data):
            if route == "files/get_metadata":
                return folder("ha-root", self.ha)
            if data.get("path") == self.root["pad"]:
                return {"entries": [folder("ha", kind), folder("ander", "/Work All/ander")],
                        "cursor": "work-cursor", "has_more": True}
            return {"entries": [folder("ha", kind)], "cursor": "ha-cursor", "has_more": False}
        bereik = N.ha_bereiken(self.regels)[0][0]
        self.assertEqual(N.synchroniseer(self.c, self.root, self.root["namespace"], rpc, self.regels,
                                         budget=1, overslaan=[self.ha]), 1)
        self.assertEqual(N.synchroniseer(self.c, bereik, bereik["namespace"], rpc, self.regels,
                                         budget=1, opslag_scope=self.root["id"]), 2)
        self.assertEqual(self.c.execute("SELECT count(*) FROM item WHERE identiteit='ha'").fetchone()[0], 1)
        self.assertEqual(tuple(self.c.execute("SELECT naam_vuil,structuur_vuil FROM item WHERE identiteit='ha'").fetchone()), (0, 0))
        self.assertEqual(self.c.execute("SELECT cursor FROM scope WHERE id=?", (self.root["id"],)).fetchone()[0], "work-cursor")
        self.assertEqual(self.c.execute("SELECT compleet FROM scope WHERE id=?", (bereik["id"],)).fetchone()[0], 1)

    def test_migratie_en_beperkte_hercontrole(self):
        self.scope(self.root["id"], self.root["pad"], 1, 0)
        self.item("ha", self.ha + "/a")
        self.item("ander", "/Work All/ander")
        self.c.execute("UPDATE item SET naam_vuil=0,structuur_vuil=0")
        N.instelling(self.c, "regelsvingerafdruk", hashlib.sha256(json.dumps(self.regels, sort_keys=True).encode()).hexdigest())
        self.c.commit()
        N.hercontrole_regels(self.c, self.regels)
        self.assertEqual(self.c.execute("SELECT sum(naam_vuil+structuur_vuil) FROM item").fetchone()[0], 0)
        gewijzigd = copy.deepcopy(self.regels)
        gewijzigd["ha"]["kanalen"].append("nieuw")
        N.hercontrole_regels(self.c, gewijzigd)
        self.assertEqual(dict(self.c.execute("SELECT identiteit,naam_vuil FROM item")), {"ha": 1, "ander": 0})
        self.c.execute("UPDATE item SET naam_vuil=0,structuur_vuil=0")
        self.c.commit()
        # Een gewijzigde tweede root raakt de bestaande Work All-items niet.
        tweede = {"id": "ander-bereik", "pad": "/Data uit Mehdi", "namespace": self.root["namespace"],
                  "verbinding": self.root["verbinding"]}
        gewijzigd["roots"].append(tweede)
        self.scope(tweede["id"], tweede["pad"], 1, 0)
        with self.c:
            self.c.execute("INSERT INTO item(scope,identiteit,pad,pad_sleutel,naam,soort,firma,profiel,naam_vuil,structuur_vuil) "
                           "VALUES(?,?,?,?,?,'folder','onbekend','algemeen',0,0)",
                           (tweede["id"], "tweede", tweede["pad"] + "/x", (tweede["pad"] + "/x").casefold(), "x"))
        N.hercontrole_regels(self.c, gewijzigd)
        self.assertEqual(dict(self.c.execute("SELECT identiteit,naam_vuil FROM item")),
                         {"ha": 0, "ander": 0, "tweede": 1})
        self.c.execute("UPDATE item SET naam_vuil=0,structuur_vuil=0")
        self.c.commit()
        gewijzigd["roots"][1]["pad"] = "/Data uit Mehdi nieuw"
        N.hercontrole_regels(self.c, gewijzigd)
        self.assertEqual(dict(self.c.execute("SELECT identiteit,naam_vuil FROM item")),
                         {"ha": 0, "ander": 0, "tweede": 1})

    def test_migratie_met_gewijzigde_of_ontbrekende_oude_vingerafdruk(self):
        self.item("ha", self.ha + "/oud")
        self.item("ander", "/Work All/ander")
        for oude_waarde in ("andere-regels", None):
            with self.subTest(oude_waarde=oude_waarde):
                with self.c:
                    self.c.execute("UPDATE item SET naam_vuil=0,structuur_vuil=0")
                    self.c.execute("DELETE FROM instelling WHERE sleutel IN ('regelvingerafdrukken','regelsvingerafdruk')")
                    if oude_waarde is not None:
                        N.instelling(self.c, "regelsvingerafdruk", oude_waarde)
                N.hercontrole_regels(self.c, self.regels)
                self.assertEqual(self.c.execute("SELECT sum(naam_vuil+structuur_vuil) FROM item").fetchone()[0], 4)
                self.assertIsNone(N.instelling(self.c, "regelsvingerafdruk"))

    def test_eerste_volledige_ha_lezing_ruimt_spookrij_op(self):
        bereik = N.ha_bereiken(self.regels)[0][0]
        oud_pad = self.ha + "/verdwenen"
        self.item("verdwenen", oud_pad)
        self.item("buiten", "/Work All/gewone map")
        with self.c:
            self.c.execute("INSERT INTO bevinding(agent,scope,identiteit,regel,status) VALUES(?,?,?,'HA A1','open')",
                           ("mappen-wacht", self.root["id"], "verdwenen"))
        def folder(id, pad):
            return {"id": id, "path_display": pad, "name": Path(pad).name, ".tag": "folder"}
        def rpc(route, data):
            if route == "files/get_metadata":
                return folder("ha-root", self.ha)
            return {"entries": [folder("aanwezig", self.ha + "/aanwezig")], "cursor": "klaar", "has_more": False}
        N.synchroniseer(self.c, bereik, bereik["namespace"], rpc, self.regels, budget=1,
                        opslag_scope=self.root["id"])
        self.assertEqual(dict(self.c.execute("SELECT identiteit,actief FROM item")),
                         {"verdwenen": 0, "buiten": 1, "ha-root": 1, "aanwezig": 1})
        self.assertEqual(self.c.execute("SELECT status FROM bevinding WHERE identiteit='verdwenen'").fetchone()[0],
                         "bron niet meer aanwezig")

    def test_afgebroken_ha_lezing_ruimt_niets_op(self):
        bereik = N.ha_bereiken(self.regels)[0][0]
        self.item("verdwenen", self.ha + "/verdwenen")
        with self.c:
            self.c.execute("INSERT INTO bevinding(agent,scope,identiteit,regel,status) VALUES(?,?,?,'HA A1','open')",
                           ("mappen-wacht", self.root["id"], "verdwenen"))
        def rpc(route, data):
            if route == "files/get_metadata":
                return {"id": "ha-root", "path_display": self.ha, "name": Path(self.ha).name, ".tag": "folder"}
            if route == "files/list_folder":
                return {"entries": [], "cursor": "nog-meer", "has_more": True}
            raise OSError("leespagina faalt")
        N.synchroniseer(self.c, bereik, bereik["namespace"], rpc, self.regels, budget=1,
                        opslag_scope=self.root["id"])
        self.assertEqual(self.c.execute("SELECT actief FROM item WHERE identiteit='verdwenen'").fetchone()[0], 1)
        with self.assertRaises(OSError):
            N.synchroniseer(self.c, bereik, bereik["namespace"], rpc, self.regels, budget=1,
                            opslag_scope=self.root["id"])
        self.assertEqual(self.c.execute("SELECT actief FROM item WHERE identiteit='verdwenen'").fetchone()[0], 1)
        self.assertEqual(self.c.execute("SELECT status FROM bevinding WHERE identiteit='verdwenen'").fetchone()[0], "open")
        def hersteld(route, data):
            self.assertEqual(route, "files/list_folder/continue")
            return {"entries": [], "cursor": "klaar", "has_more": False}
        N.synchroniseer(self.c, bereik, bereik["namespace"], hersteld, self.regels, budget=1,
                        opslag_scope=self.root["id"])
        self.assertEqual(self.c.execute("SELECT actief FROM item WHERE identiteit='verdwenen'").fetchone()[0], 0)

    def test_ha_lezing_houdt_gezien_vast_tussen_paginas(self):
        bereik = N.ha_bereiken(self.regels)[0][0]
        self.item("blijft", self.ha + "/blijft")
        self.item("verdwenen", self.ha + "/verdwenen")
        def rpc(route, data):
            if route == "files/get_metadata":
                return {"id": "ha-root", "path_display": self.ha, "name": Path(self.ha).name, ".tag": "folder"}
            if route == "files/list_folder":
                return {"entries": [{"id": "blijft", "path_display": self.ha + "/blijft",
                                     "name": "blijft", ".tag": "folder"}], "cursor": "pagina-1", "has_more": True}
            return {"entries": [], "cursor": "klaar", "has_more": False}
        N.synchroniseer(self.c, bereik, bereik["namespace"], rpc, self.regels, budget=1,
                        opslag_scope=self.root["id"])
        self.assertEqual(self.c.execute("SELECT actief FROM item WHERE identiteit='verdwenen'").fetchone()[0], 1)
        N.synchroniseer(self.c, bereik, bereik["namespace"], rpc, self.regels, budget=1,
                        opslag_scope=self.root["id"])
        self.assertEqual(dict(self.c.execute("SELECT identiteit,actief FROM item WHERE identiteit IN ('blijft','verdwenen')")),
                         {"blijft": 1, "verdwenen": 0})

    def test_pad_en_overzichtindexen_worden_gebruikt(self):
        namen = {r[1] for r in self.c.execute("PRAGMA index_list(item)")}
        self.assertIn("item_pad_sleutel", namen)
        self.assertIn("item_scope_actief_profiel_vuil", namen)
        self.assertIn("bevinding_scope_identiteit",
                      {r[1] for r in self.c.execute("PRAGMA index_list(bevinding)")})
        self.item("ha", self.ha + "/map")
        with self.c:
            self.c.executemany("INSERT INTO item(scope,identiteit,pad,pad_sleutel,naam,soort,firma,profiel) "
                               "VALUES(?,?,?,?,?,'folder','onbekend','algemeen')",
                               [(self.root["id"], str(i), f"/Work All/ander/{i}", f"/work all/ander/{i}", str(i))
                                for i in range(100)])
            self.c.execute("ANALYZE")
        p = self.ha.casefold()
        ha_plan = " ".join(r[3] for r in self.c.execute(
            "EXPLAIN QUERY PLAN SELECT count(*) FROM item WHERE scope=? AND actief=1 AND "
            "(pad_sleutel=? OR (pad_sleutel>=? AND pad_sleutel<?))",
            (self.root["id"], p, p + "/", p + "0")))
        overzicht_plan = " ".join(r[3] for r in self.c.execute(
            "EXPLAIN QUERY PLAN SELECT count(*) FROM item WHERE scope=? AND actief=1 "
            "AND profiel NOT GLOB 'ha_*' AND naam_vuil=1", (self.root["id"],)))
        self.assertIn("item_pad_sleutel", ha_plan)
        self.assertIn("item_scope_actief_profiel_vuil", overzicht_plan)
        self.assertNotIn("SCAN item", ha_plan + overzicht_plan)
        bereik = N.ha_bereiken(self.regels)[0][0]
        self.scope(self.root["id"], self.root["pad"], 1, 0)
        self.scope(bereik["id"], bereik["pad"], 1, 0)
        queries = []
        self.c.set_trace_callback(lambda sql: queries.append(sql) if sql.startswith("SELECT i.* FROM item i") else None)
        N.toets_index(self.c, "benamingen-wacht", self.regels, budget=1)
        self.c.set_trace_callback(None)
        ha_sql = next(q for q in queries if "i.profiel GLOB 'ha_*' ORDER BY" in q)
        toets_plan = " ".join(r[3] for r in self.c.execute("EXPLAIN QUERY PLAN " + ha_sql))
        self.assertIn("USING INDEX item_ha_naam_vuil", toets_plan)
        self.assertNotIn("SCAN item", toets_plan)

    def test_regelbron_download_eenmaal_binnen_24_uur(self):
        inhoud = b"bevestigde testbron"
        self.regels["regelbron"]["sha256"] = hashlib.sha256(inhoud).hexdigest()
        aanroepen = []
        def rpc(route, data):
            if route == "files/list_folder":
                return {"entries": [{".tag": "file", "name": "H-A vaste afspraken v1.7.md"}],
                        "cursor": "klaar", "has_more": False}
            return {".tag": "file", "size": len(inhoud), "rev": "r1"}
        def download(*args, **kwargs):
            aanroepen.append(1)
            return inhoud
        for _ in range(2):
            self.assertTrue(N.controleer_regelbron(self.c, self.regels, rpc, download, force=False)["geldig"])
        self.assertEqual(len(aanroepen), 1)
        def rpc_nieuwe_versie(route, data):
            if route == "files/list_folder":
                return {"entries": [{".tag": "file", "name": "H-A vaste afspraken v1.8.md"}],
                        "cursor": "klaar", "has_more": False}
            self.fail("nieuwere versie moet vóór een download ontdekt worden")
        stand = N.controleer_regelbron(self.c, self.regels, rpc_nieuwe_versie, download, force=False)
        self.assertFalse(stand["geldig"])
        self.assertIn("v1.8", stand["status"])
        self.assertEqual(len(aanroepen), 1)

    def test_profielwijziging_herclassificeert_alleen_geraakte_prefix(self):
        self.scope(self.root["id"], self.root["pad"], 1, 0)
        self.item("oud", self.ha + "/los")
        self.item("nieuw", self.ha + "/sub/map")
        self.item("ander", "/Work All/ander")
        self.c.execute("UPDATE item SET naam_vuil=0,structuur_vuil=0")
        N.instelling(self.c, "regelsvingerafdruk", hashlib.sha256(json.dumps(self.regels, sort_keys=True).encode()).hexdigest())
        self.c.commit()
        N.hercontrole_regels(self.c, self.regels)
        gewijzigd = copy.deepcopy(self.regels)
        gewijzigd["profielen"][0]["prefix"] = self.ha + "/sub"
        N.hercontrole_regels(self.c, gewijzigd)
        stand = {r["identiteit"]: (r["profiel"], r["naam_vuil"]) for r in self.c.execute("SELECT identiteit,profiel,naam_vuil FROM item")}
        self.assertEqual(stand["oud"], ("algemeen", 1))
        self.assertEqual(stand["nieuw"], ("ha_project", 1))
        self.assertEqual(stand["ander"], ("algemeen", 0))

    def test_nieuwere_versie_pauzeert_en_bewaar_bevinding(self):
        bron = self.regels["regelbron"]
        inhoud = b"bevestigde testbron"
        bron["sha256"] = hashlib.sha256(inhoud).hexdigest()
        self.scope(self.root["id"], self.root["pad"], 1, 0)
        self.item("ha", self.ha + "/foute:map")
        self.c.execute("INSERT INTO bevinding(agent,scope,identiteit,regel,status) VALUES(?,?,?,'HA A1','open')",
                       ("benamingen-wacht", self.root["id"], "ha"))
        self.c.commit()
        def rpc_oud(route, data):
            if route == "files/list_folder":
                return {"entries": [{".tag": "file", "name": "H-A vaste afspraken v1.7.md"}],
                        "cursor": "klaar", "has_more": False}
            return {".tag": "file", "size": len(inhoud), "rev": "r1"}
        self.assertTrue(N.controleer_regelbron(self.c, self.regels, rpc_oud, lambda *a, **k: inhoud, force=True)["geldig"])
        def rpc_nieuw(route, data):
            if route == "files/list_folder":
                return {"entries": [{".tag": "file", "name": "H-A vaste afspraken v1.8.md"}],
                        "cursor": "klaar", "has_more": False}
            return {".tag": "file", "size": len(inhoud), "rev": "r1"}
        stand = N.controleer_regelbron(self.c, self.regels, rpc_nieuw, lambda *a, **k: inhoud, force=True)
        self.assertFalse(stand["geldig"])
        self.assertIn("v1.8 gevonden, niet bevestigd; vastgepind", stand["status"])
        self.assertEqual(N.toets_index(self.c, "benamingen-wacht", self.regels), 0)
        self.assertEqual(self.c.execute("SELECT status FROM bevinding").fetchone()[0], "open")
        def rpc_later(route, data):
            if route == "files/list_folder":
                return {"entries": [], "cursor": "vervolg", "has_more": True}
            if route == "files/list_folder/continue":
                return {"entries": [{".tag": "file", "name": "H-A vaste afspraken v1.8.md"}],
                        "cursor": "klaar", "has_more": False}
            self.fail("gepagineerde nieuwe versie moet de download voorkomen")
        self.assertFalse(N.controleer_regelbron(self.c, self.regels, rpc_later,
                                                 lambda *a, **k: inhoud, force=True)["geldig"])
        def fout(*a):
            raise OSError("map niet leesbaar")
        stand = N.controleer_regelbron(self.c, self.regels, fout, lambda *a, **k: inhoud, force=True)
        self.assertFalse(stand["geldig"])
        self.assertIn("gepauzeerd", stand["status"])

    def test_een_samenvattingsregel_en_nood_voor_mehdi(self):
        with self.c:
            N.instelling(self.c, "regelsvingerafdruk", hashlib.sha256(json.dumps(self.regels, sort_keys=True).encode()).hexdigest())
            N.instelling(self.c, "dagcontrole", N.nu()[:10])
        class Ronde:
            werkwijze = True
            def __init__(self):
                self.noden = []
            def bron(self, *a):
                pass
            def nood(self, tekst, voor):
                self.noden.append((tekst, voor))
        r = Ronde()
        client = type("Lezer", (), {"namespace": self.root["namespace"], "rpc": lambda *a: None,
                                     "download": lambda *a, **k: b""})()
        forces = []
        def bron(c, regels, rpc, download, force=False):
            forces.append(force)
            stand = {"geldig": False, "gevonden": "H-A vaste afspraken v1.8",
                     "versie": regels["regelbron"]["versie"],
                     "status": "H-A vaste afspraken v1.8 gevonden, niet bevestigd; vastgepind v1.7"}
            with c:
                N.instelling(c, "regelbron", stand)
            return stand
        with (patch.object(R.organisatie, "firmas", return_value=[]),
              patch.object(N, "lezer_van", return_value=client),
              patch.object(N, "controleer_regelbron", side_effect=bron),
              patch.object(N, "synchroniseer", return_value=0),
              patch.object(N, "lees_lokale_metadata", return_value=0),
              patch.object(N, "dagelijkse_dekking")):
            uitvoer = io.StringIO()
            with contextlib.redirect_stdout(uitvoer):
                R.werk("benamingen-wacht", r, self.regels, self.tmp.name)
        regels = uitvoer.getvalue().splitlines()
        self.assertEqual(len(regels), 1)
        self.assertIn("gelezen", regels[0])
        self.assertIn("getoetst", regels[0])
        self.assertIn("open punten", regels[0])
        self.assertIn("v1.8", regels[0])
        self.assertTrue(any(voor == "mehdi" and "v1.8" in tekst and "Welke versie geldt?" in tekst
                            for tekst, voor in r.noden))
        self.assertEqual(forces, [False])


if __name__ == "__main__":
    unittest.main()
