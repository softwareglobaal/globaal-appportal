"""Toezichtgrendels: hervatten, echte dekking, stabiele punten en geen bronmutatie."""
import importlib.util
import json
import os
import sys
import tempfile
import unittest
import io
from unittest.mock import patch
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
        self.regels["roots"] = [self.root]
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

    def test_bestaande_omv_config_refresh_alleen_in_geheugen(self):
        config = Path(self.map.name) / ".env"
        tokenbestand = Path(self.map.name) / "dropbox_tokens.json"
        config.write_text("DROPBOX_APP_KEY=verzonnen-app\nDROPBOX_APP_SECRET=verzonnen-secret\nDROPBOX_TOKEN_FILE=/data/dropbox_tokens.json\n")
        tokenbestand.write_text(json.dumps({"DROPBOX_REFRESH_TOKEN": "verzonnen-refresh", "DROPBOX_ACCESS_TOKEN": "oude-verzonnen-toegang"}))
        voor = tokenbestand.read_bytes()
        regels = {"verbindingen": {"omv-v2": {"type": "omv-v2", "configpad": str(config)}}}
        root = {"verbinding": "omv-v2", "namespace": "123"}
        with patch.object(N.urllib.request, "urlopen", return_value=io.BytesIO(b'{"access_token":"verzonnen-toegang","expires_in":14400}')) as request:
            a = N.lezer_van(root, regels)
            self.assertEqual(a.koppen({})["Authorization"], "Bearer verzonnen-toegang")
            b = N.lezer_van({**root, "namespace": "456"}, regels)
            self.assertEqual(b.koppen({})["Authorization"], "Bearer verzonnen-toegang")
            self.assertEqual(request.call_count, 1)
            body = N.urllib.parse.parse_qs(request.call_args[0][0].data.decode())
            self.assertEqual(body["grant_type"], ["refresh_token"])
            self.assertNotIn("scope", body)
        self.assertEqual(tokenbestand.read_bytes(), voor)
        self.assertEqual(a.verbinding, "omv-v2")
        self.assertEqual(a.pathroot()["namespace_id"], "123")

    def test_omv_configfout_geeft_geen_fallback_naar_stack(self):
        bron = N.OMVVerbinding(str(Path(self.map.name) / "ontbreekt.env"))
        with patch.object(N.urllib.request, "urlopen", side_effect=AssertionError("geen netwerk zonder config")):
            with self.assertRaisesRegex(RuntimeError, "configuratie"):
                bron.toegang()
        regels = {"verbindingen": {"omv-v2": {"type": "omv-v2", "configpad": "ontbreekt.env"}}}
        for root in ({"namespace": "123"}, {"verbinding": "ander", "namespace": "123"}, {"verbinding": "omv-v2", "namespace": "onbekend"}):
            with self.assertRaises(ValueError):
                N.lezer_van(root, regels)

    def test_omv_authfout_redigeert_antwoord_en_wijzigt_tokenbestand_niet(self):
        import urllib.error
        config = Path(self.map.name) / ".env"
        token = Path(self.map.name) / "dropbox_tokens.json"
        config.write_text("DROPBOX_APP_KEY=verzonnen-app\nDROPBOX_APP_SECRET=verzonnen-secret\nDROPBOX_TOKEN_FILE=dropbox_tokens.json\n")
        token.write_text('{"DROPBOX_REFRESH_TOKEN":"verzonnen-refresh"}')
        voor = token.read_bytes()
        fout = urllib.error.HTTPError("https://api.dropboxapi.com/oauth2/token", 400, "verzonnen-secret", {}, io.BytesIO(b'verzonnen-refresh'))
        with patch.object(N.urllib.request, "urlopen", side_effect=fout):
            with self.assertRaises(RuntimeError) as e:
                N.OMVVerbinding(str(config)).toegang()
        self.assertNotIn("verzonnen", str(e.exception))
        self.assertEqual(token.read_bytes(), voor)

    def test_config_geheimvelden_en_onbekende_verbinding_weigeren(self):
        regels = N.lees_regels()
        regels["verbindingen"]["omv-v2"]["refresh_token"] = "verzonnen"
        p = Path(self.map.name) / "regels.json"
        p.write_text(json.dumps(regels))
        with self.assertRaises(ValueError):
            N.lees_regels(p)

    def test_verbindingswisseling_behoudt_bronbewijs_en_weigert_cursor(self):
        e = self.folder("id:1", "/Work All/foute:naam")
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([e], "oude-cursor"), self.regels)
        N.toets_index(self.c, "benamingen-wacht", self.regels)
        nieuw = {**self.root, "verbinding": "omv-v2"}
        with self.assertRaisesRegex(ValueError, "rescan"):
            N.synchroniseer(self.c, nieuw, "123", lambda *a: self.fail("oude cursor nooit gebruiken"), self.regels)
        self.assertEqual(self.c.execute("SELECT cursor FROM scope").fetchone()[0], "oude-cursor")
        self.assertEqual(self.c.execute("SELECT count(*) FROM item").fetchone()[0], 1)
        self.assertEqual(self.c.execute("SELECT status FROM bevinding").fetchone()[0], "open")
        andere_regels = {**self.regels, "roots": [{"id": "nieuw", "pad": "/Work All"}]}
        self.c.execute("UPDATE item SET naam_vuil=1")
        self.c.commit()
        self.assertEqual(N.toets_index(self.c, "benamingen-wacht", andere_regels), 0)
        stand = N.overzicht(self.c, andere_regels, "benamingen-wacht")
        self.assertFalse(stand["scopes"][0]["ingesteld"])
        self.assertEqual(stand["tellingen"]["benamingen-wacht"], 0)

    def test_kinderen_en_ouders_gebruiken_scope_padindex(self):
        p = "/work all/map"
        queries = [
            ("SELECT * FROM item WHERE scope=? AND pad_sleutel=?", ("test", p)),
            ("SELECT * FROM item WHERE scope=? AND actief=1 AND pad_sleutel>=? AND pad_sleutel<?", ("test", p + "/", p + "0")),
            ("SELECT identiteit FROM item WHERE scope=? AND pad_sleutel=? UNION SELECT identiteit FROM item WHERE scope=? AND pad_sleutel>=? AND pad_sleutel<?", ("test", p, "test", p + "/", p + "0"))]
        for query, params in queries:
            plan = " ".join(row[3] for row in self.c.execute("EXPLAIN QUERY PLAN " + query, params))
            self.assertIn("item_pad_sleutel", plan)
            self.assertNotIn("SCAN item", plan)
        entries = [self.folder("id:1", "/Work All/map"), self.folder("id:2", "/Work All/map/kind"),
                   self.folder("id:3", "/Work All/map/kind/kleinkind"), self.folder("id:4", "/Work All/mapje/verkeerd")]
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina(entries), self.regels)
        rij = dict(self.c.execute("SELECT * FROM item WHERE identiteit='id:1'").fetchone())
        self.assertEqual([x["naam"] for x in N.kinderen(self.c, rij)], ["kind"])

    def test_unicode_moment_vindt_verslag_markeert_ouder_en_tombstone(self):
        project = "/Work All/01. H-A WORK/0 H-A Standaard projects/1. STAN  Submission/2601 Teststraat 1, 3000 Leuven (stan)(ww)"
        pad = project + "/_00. Communication/2026-10-05 mail klant - ÉCLAIR"
        verslag = {"id": "id:verslag", "path_display": pad + "/00 verslag.md", "name": "00 verslag.md", ".tag": "file"}
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([self.folder("id:moment", pad)]), self.regels)
        self.c.execute("UPDATE item SET structuur_vuil=0")
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([verslag], "c2"), self.regels)
        rij = dict(self.c.execute("SELECT * FROM item WHERE identiteit='id:moment'").fetchone())
        # Reproduceert het verschil dat een valse ontbreektmelding veroorzaakte.
        self.assertNotEqual(self.c.execute("SELECT lower(?)", (pad,)).fetchone()[0], pad.casefold())
        self.assertEqual(self.c.execute("SELECT count(*) FROM item WHERE lower(pad)>=? AND lower(pad)<?",
                                       (pad.casefold() + "/", pad.casefold() + "0")).fetchone()[0], 0)
        self.assertTrue(N.momentnaam(rij["naam"], self.regels))
        self.assertEqual(rij["structuur_vuil"], 1)
        self.assertEqual([x["naam"] for x in N.kinderen(self.c, rij)], ["00 verslag.md"])
        self.assertEqual(N.structuurtoets(self.c, rij, self.regels), [])
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina([{ ".tag": "deleted", "path_lower": pad.casefold()}], "c3"), self.regels)
        self.assertEqual(self.c.execute("SELECT count(*) FROM item WHERE actief=1").fetchone()[0], 0)

    def test_casefold_lengtevariant_scheidt_direct_kind_van_kleinkind(self):
        entries = [self.folder("id:1", "/Work All/Straße"), self.folder("id:2", "/Work All/STRASSE/kind"),
                   self.folder("id:3", "/Work All/STRASSE/kind/dieper")]
        N.synchroniseer(self.c, self.root, "123", lambda *a: self.pagina(entries), self.regels)
        rij = dict(self.c.execute("SELECT * FROM item WHERE identiteit='id:1'").fetchone())
        self.assertEqual([x["naam"] for x in N.kinderen(self.c, rij)], ["kind"])

    def test_oude_unicode_index_backfill_behoudt_bronbewijs_en_is_idempotent(self):
        import sqlite3
        pad = os.path.join(self.map.name, "oude-index.sqlite3")
        oud = sqlite3.connect(pad)
        oud.executescript("""
          CREATE TABLE item(scope TEXT,identiteit TEXT,pad TEXT,naam TEXT,soort TEXT,firma TEXT,
            profiel TEXT,gegevens TEXT DEFAULT '{}',actief INTEGER DEFAULT 1,
            naam_vuil INTEGER DEFAULT 1,structuur_vuil INTEGER DEFAULT 1,PRIMARY KEY(scope,identiteit));
          CREATE TABLE scope(id TEXT PRIMARY KEY,pad TEXT,namespace TEXT,cursor TEXT DEFAULT '',
            compleet INTEGER DEFAULT 0,meer INTEGER DEFAULT 1,poging TEXT DEFAULT '',gelukt TEXT DEFAULT '',
            fout TEXT DEFAULT '',controle TEXT DEFAULT '');
          INSERT INTO scope(id,pad,namespace,cursor) VALUES('historisch','/Work All','123','oude-cursor');
          INSERT INTO item(scope,identiteit,pad,naam,soort,firma,profiel,structuur_vuil)
            VALUES('historisch','id:1','/Work All/ÉCLAIR','ÉCLAIR','folder','onbekend','algemeen',0);
          INSERT INTO item(scope,identiteit,pad,naam,soort,firma,profiel)
            VALUES('historisch','id:2','','','metadata','onbekend','lokale metadata');
        """)
        oud.close()
        for opening in range(2):
            nieuw = N.open_db(pad)
            rij = nieuw.execute("SELECT * FROM item WHERE identiteit='id:1'").fetchone()
            self.assertEqual(rij["pad"], "/Work All/ÉCLAIR")
            self.assertEqual(rij["pad_sleutel"], "/work all/éclair")
            self.assertEqual(rij["structuur_vuil"], 1 if opening == 0 else 0)
            self.assertEqual(nieuw.execute("SELECT cursor FROM scope").fetchone()[0], "oude-cursor")
            self.assertEqual(nieuw.execute("SELECT count(*) FROM item WHERE pad_sleutel IS NULL").fetchone()[0], 0)
            self.assertEqual(N.instelling(nieuw, "pad_sleutel_versie"), 1)
            nieuw.execute("UPDATE item SET structuur_vuil=0")
            nieuw.commit()
            nieuw.close()

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
