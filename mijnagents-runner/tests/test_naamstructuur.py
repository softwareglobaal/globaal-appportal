"""Toezichtgrendels: hervatten, echte dekking, stabiele punten en geen bronmutatie."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER / "koppelingen"))
import naamstructuur as N

spec = importlib.util.spec_from_file_location("naamstructuur_installeren", RUNNER / "planning" / "naamstructuur_installeren.py")
INSTALLER = importlib.util.module_from_spec(spec)
spec.loader.exec_module(INSTALLER)


class ToezichtTest(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.TemporaryDirectory()
        self.c = N.open_db(os.path.join(self.map.name, "index.sqlite3"))
        self.regels = N.lees_regels()
        self.root = {"id": "test", "pad": "/Work All"}
        with self.c:
            N.instelling(self.c, "regelbron", {"geldig": True})

    def tearDown(self):
        self.c.close()
        self.map.cleanup()

    def pagina(self, entries, cursor="c1", meer=False):
        return {"entries": entries, "cursor": cursor, "has_more": meer}

    def folder(self, id, pad):
        return {"id": id, "path_display": pad, "name": Path(pad).name, ".tag": "folder"}

    def test_cursor_hervat_achter_paginabudget(self):
        aanroepen = []
        project = "/Work All/01. H-A WORK/0 H-A Standaard projects/1. STAN  Submission/2601 Teststraat 1, 3000 Leuven (stan)(ww)"
        eerste = self.pagina([self.folder("id:1", project)], "begin", True)
        tweede = self.pagina([self.folder("id:2", project + "/_00. Communication")], "klaar")
        def rpc(route, data):
            aanroepen.append((route, data))
            return eerste if route == "files/list_folder" else tweede
        N.synchroniseer(self.c, self.root, "123", rpc, self.regels, budget=1)
        self.assertEqual(N.toets_index(self.c, "mappen-wacht", self.regels), 0)
        self.assertEqual(self.c.execute("SELECT compleet FROM scope").fetchone()[0], 0)
        N.synchroniseer(self.c, self.root, "123", rpc, self.regels, budget=1)
        self.assertEqual(aanroepen[1], ("files/list_folder/continue", {"cursor": "begin"}))
        N.toets_index(self.c, "mappen-wacht", self.regels)
        self.assertEqual(self.c.execute("SELECT count(*) FROM bevinding WHERE status='open'").fetchone()[0], 0)

    def test_fout_halverwege_bewaart_laatste_gecommitte_cursor(self):
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([], "goed", True), self.regels, budget=1)
        def fout(*a):
            raise RuntimeError("verzonnen leesfout")
        with self.assertRaises(RuntimeError):
            N.synchroniseer(self.c, self.root, "123", fout, self.regels)
        s = self.c.execute("SELECT * FROM scope").fetchone()
        self.assertEqual(s["cursor"], "goed")
        self.assertEqual(s["compleet"], 0)
        self.assertTrue(s["fout"])

    def test_pagina_met_item_buiten_root_commit_niets(self):
        fout = self.pagina([self.folder("id:1", "/Work All/a"), self.folder("id:2", "/ander/b")])
        with self.assertRaises(ValueError):
            N.synchroniseer(self.c, self.root, "123", lambda *a: fout, self.regels)
        self.assertEqual(self.c.execute("SELECT count(*) FROM item").fetchone()[0], 0)
        self.assertEqual(self.c.execute("SELECT cursor FROM scope").fetchone()[0], "")

    def test_namespacewissel_neemt_nooit_cursor_mee(self):
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([]), self.regels)
        with self.assertRaises(ValueError):
            N.synchroniseer(self.c, self.root, "456", lambda *a: self.fail("geen API-aanroep"), self.regels)

    def test_has_more_moet_explicit_bool_zijn(self):
        for waarde in (None, "false", 0, [], {}):
            pagina = {"entries": [], "cursor": "verkeerd"}
            if waarde is not None:
                pagina["has_more"] = waarde
            with self.assertRaises(RuntimeError):
                N.synchroniseer(self.c, self.root, "123", lambda *a: pagina, self.regels)
            self.assertEqual(self.c.execute("SELECT compleet FROM scope").fetchone()[0], 0)
            self.assertEqual(self.c.execute("SELECT cursor FROM scope").fetchone()[0], "")

    def test_namespaceheader_voor_gedeelde_teammap(self):
        self.assertEqual(N.DropboxLezer("123").pathroot(), {".tag": "namespace_id", "namespace_id": "123"})

    def test_numerieke_opnamemap_is_geen_project(self):
        for ouder in ("0 Fathom", "1. opnames", "2026-10-05", "1. STAN  Submission"):
            pad = "/Work All/01. H-A WORK/_0 Claude reorganisatie/" + ouder + "/2601 test"
            rij = {"naam": "2601 test", "pad": pad, "profiel": "ha_project", "soort": "folder"}
            self.assertFalse(N.is_projectmap(rij, self.regels))
            self.assertEqual(N.naamtoets(rij, self.regels), [])

    def test_lokale_bron_met_backlog_claimt_geen_complete_dekking(self):
        import sqlite3
        pad = os.path.join(self.map.name, "bord.db")
        b = sqlite3.connect(pad)
        b.execute("CREATE TABLE klaarzet(uniek,titel,inhoud,ts,soort)")
        b.execute("CREATE TABLE gesprek_log(uniek,archief,ts,bron)")
        for i in range(3):
            b.execute("INSERT INTO klaarzet VALUES(?,?,?,?,?)", (str(i), "afspraak", '{}', "2026-10-05", "afspraak"))
        b.commit()
        b.close()
        self.assertEqual(N.lees_lokale_metadata(self.c, pad, budget=2), 2)
        s = self.c.execute("SELECT compleet,meer FROM scope WHERE id='lokaal:agenda'").fetchone()
        self.assertEqual(tuple(s), (0, 1))
        self.assertEqual(N.lees_lokale_metadata(self.c, pad, budget=2), 1)
        s = self.c.execute("SELECT compleet,meer FROM scope WHERE id='lokaal:agenda'").fetchone()
        self.assertEqual(tuple(s), (1, 0))
        self.assertEqual(N.lees_lokale_metadata(self.c, pad, budget=2), 0)

    def test_later_bevestigde_namespace_kan_starten(self):
        self.c.execute("INSERT INTO scope(id,pad,namespace) VALUES('test','/Work All','niet vastgesteld')")
        self.c.commit()
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([]), self.regels)
        self.assertEqual(self.c.execute("SELECT namespace FROM scope").fetchone()[0], "123")

    def test_punten_zijn_idempotent_en_herstel_sluit_punt(self):
        e = self.folder("id:1", "/Work All/foute:naam")
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e]), self.regels)
        N.toets_index(self.c, "benamingen-wacht", self.regels)
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e]), self.regels)
        N.toets_index(self.c, "benamingen-wacht", self.regels)
        self.assertEqual(self.c.execute("SELECT count(*) FROM bevinding").fetchone()[0], 1)
        e = self.folder("id:1", "/Work All/veilige naam")
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e]), self.regels)
        N.toets_index(self.c, "benamingen-wacht", self.regels)
        self.assertEqual(self.c.execute("SELECT status FROM bevinding").fetchone()[0], "opgelost in bron")

    def test_tombstone_deactiveert_alleen_index(self):
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([self.folder("id:1", "/Work All/a")]), self.regels)
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([{ ".tag": "deleted", "path_lower": "/work all/a"}]), self.regels)
        self.assertEqual(self.c.execute("SELECT actief FROM item").fetchone()[0], 0)
        self.assertEqual(self.c.execute("SELECT count(*) FROM item").fetchone()[0], 1)

    def test_online_only_size_speelt_geen_rol(self):
        e = {"id": "id:1", "path_display": "/Work All/bericht.md", "name": "bericht.md", ".tag": "file", "size": 0}
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e]), self.regels)
        self.assertEqual(self.c.execute("SELECT actief FROM item").fetchone()[0], 1)
        N.toets_index(self.c, "benamingen-wacht", self.regels)
        self.assertEqual(self.c.execute("SELECT count(*) FROM bevinding").fetchone()[0], 0)

    def test_onbekende_firma_krijgt_geen_ha_structuurregel(self):
        e = self.folder("id:1", "/Work All/Ander bedrijf/2601 test")
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e]), self.regels)
        N.toets_index(self.c, "mappen-wacht", self.regels)
        self.assertEqual(self.c.execute("SELECT firma FROM item").fetchone()[0], "onbekend")
        self.assertEqual(self.c.execute("SELECT count(*) FROM bevinding").fetchone()[0], 0)

    def test_verslag_ontbreekt_pas_na_volledige_cloudlijst(self):
        pad = "/Work All/01. H-A WORK/0 H-A Standaard projects/1. STAN  Submission/2601 Teststraat 1, 3000 Leuven (stan)(ww)/_00. Communication/2026-10-01 bezoek klant - werfbezoek 1"
        e = self.folder("id:1", pad)
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e]), self.regels)
        N.toets_index(self.c, "mappen-wacht", self.regels)
        self.assertEqual(self.c.execute("SELECT regel FROM bevinding WHERE status='open'").fetchone()[0], "HA B1")
        file = {"id": "id:2", "path_display": pad + "/00 verslag.md", "name": "00 verslag.md", ".tag": "file", "size": 0}
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([file]), self.regels)
        N.toets_index(self.c, "mappen-wacht", self.regels)
        self.assertEqual(self.c.execute("SELECT status FROM bevinding").fetchone()[0], "opgelost in bron")

    def test_regelbronwijziging_sluit_geen_bestaande_ha_punten(self):
        pad = "/Work All/01. H-A WORK/0 H-A Standaard projects/1. STAN  Submission/2601 test"
        e = self.folder("id:1", pad)
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e]), self.regels)
        N.toets_index(self.c, "mappen-wacht", self.regels)
        with self.c:
            N.instelling(self.c, "regelbron", {"geldig": False})
            self.c.execute("UPDATE item SET structuur_vuil=1")
        self.assertEqual(N.toets_index(self.c, "mappen-wacht", self.regels), 0)
        self.assertEqual(self.c.execute("SELECT status FROM bevinding").fetchone()[0], "open")

    def test_dropbox_adapter_weigert_schrijfroute(self):
        d = N.DropboxLezer("123")
        for route in ("files/move_v2", "files/delete_v2", "files/upload", "sharing/share_folder"):
            with self.assertRaises(ValueError):
                d.rpc(route, {})
        with self.assertRaises(ValueError):
            N.DropboxLezer("")

    def test_planning_behoudt_andere_taken_en_is_idempotent(self):
        bestaand = ["MAILTO=", "5 * * * * andere-agent", "# handmatige notitie"]
        regels = (RUNNER / "planning" / "naamstructuur.cron").read_text().splitlines()
        doel = INSTALLER.samenvoegen(bestaand, regels)
        self.assertEqual(doel[:3], bestaand)
        self.assertEqual(INSTALLER.samenvoegen(doel, regels), doel)
        self.assertEqual(sum("benamingen_wacht.py" in r for r in doel), 1)
        self.assertEqual(sum("mappen_wacht.py" in r for r in doel), 1)
        with self.assertRaises(ValueError):
            INSTALLER.samenvoegen(["* * * * * mijnagents-runner/mappen_wacht.py"], regels)

    def test_runners_sturen_geen_signalen_of_mutaties(self):
        tekst = (RUNNER / "naamstructuur_ronde.py").read_text()
        self.assertNotIn(".klaarzet(", tekst)
        self.assertNotIn("stel_voor(", tekst)
        self.assertNotIn("files/move", tekst)
        self.assertNotIn("files/delete", tekst)
        self.assertIn("ag.ronde(", tekst)
        self.assertIn("flock", tekst)


if __name__ == "__main__":
    unittest.main()
