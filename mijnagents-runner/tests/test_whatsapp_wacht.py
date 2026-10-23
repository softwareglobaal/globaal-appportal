"""Synthetische grendels voor de persoonlijke WhatsApp-wacht.

Geen netwerk, geen echte export en geen WhatsApp-database. Draaien met
python3 mijnagents-runner/tests/test_whatsapp_wacht.py.
"""

import importlib.util
import contextlib
from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile


BRON = Path(__file__).resolve().parents[1] / "mac/whatsapp_wacht.py"
SPEC = importlib.util.spec_from_file_location("whatsapp_wacht_mac", BRON)
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)
STAND_PAD = Path(__file__).resolve().parents[1] / "koppelingen/bordstand.py"
STAND_SPEC = importlib.util.spec_from_file_location("whatsapp_bordstand", STAND_PAD)
BORDSTAND = importlib.util.module_from_spec(STAND_SPEC)
STAND_SPEC.loader.exec_module(BORDSTAND)
CONTROLE_PAD = Path(__file__).resolve().parents[1] / "controle_agenten.py"
CONTROLE_SPEC = importlib.util.spec_from_file_location("whatsapp_agentcontrole", CONTROLE_PAD)
CONTROLE = importlib.util.module_from_spec(CONTROLE_SPEC)
CONTROLE_SPEC.loader.exec_module(CONTROLE)

INHOUD = (
    "\u200e[13/10/2025, 09:12:01] Eigen: privé sentinel voorbeeld\n"
    "vervolgregel met URL https://voorbeeld.test/privé\n"
    "[13/10/2025, 09:13:02] Ander: nog een privé sentinel\n"
    "[14/10/2025, 10:00:00] Eigen: tweede dag\n"
    "[14/10/2025, 10:05:00] Messages and calls are end-to-end encrypted.\n"
)


class Wachttest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.basis = Path(self.tmp.name).resolve()
        self.exports = self.basis / "exports"
        self.exports.mkdir(mode=0o700)
        gekozen_map = patch.object(W, "EXPORT_MAP", self.exports)
        gekozen_map.start()
        self.addCleanup(gekozen_map.stop)
        rondeslot = patch.object(W, "LOCK_PAD", self.basis / "ronde.lock")
        rondeslot.start()
        self.addCleanup(rondeslot.stop)
        ronde_id = patch.object(W.secrets, "token_hex", return_value="a" * 32)
        ronde_id.start()
        self.addCleanup(ronde_id.stop)
        self.config = self.basis / "keuze.json"
        self.staat = self.basis / "dagen.json"
        self.token = self.basis / "token"
        self.token.write_text("synthetisch-token", encoding="utf-8")
        self.token.chmod(0o600)

    def maak_txt(self, naam="gekozen.txt", inhoud=INHOUD):
        pad = self.exports / naam
        pad.write_text(inhoud, encoding="utf-8")
        pad.chmod(0o600)
        return pad

    def maak_zip(self, naam="gekozen.zip", inhoud=INHOUD, extra=None):
        pad = self.exports / naam
        with zipfile.ZipFile(pad, "w") as pakket:
            pakket.writestr("_chat.txt", inhoud)
            if extra:
                pakket.writestr(extra, b"geen echte media")
        pad.chmod(0o600)
        return pad

    def kies(self, naam="gekozen.txt", datumvolgorde="DMY", eigen="Eigen", andere="Ander"):
        data = {"versie": 1, "export_map": str(self.exports), "gesprekken": [
            {"bestand": naam, "eigen_afzender": eigen, "andere_afzender": andere,
             "datumvolgorde": datumvolgorde}]}
        self.config.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        self.config.chmod(0o600)
        return data

    def tel(self):
        return W.tel_geselecteerde(W.laad_config(self.config))

    @contextlib.contextmanager
    def nep_tunnel(self):
        yield "http://127.0.0.1:12345"

    def test_zip_met_een_chat_zonder_media_en_meerregelige_tekst(self):
        self.maak_zip()
        self.kies("gekozen.zip")
        self.assertEqual(self.tel(), {
            "2025-10-13": {"inkomend": 1, "uitgaand": 1},
            "2025-10-14": {"inkomend": 0, "uitgaand": 1},
        })

    def test_android_stempel_en_maand_dag_volgorde(self):
        self.maak_txt(inhoud=(
            "10/13/2025, 9:12 AM - Eigen: privé\n"
            "10/13/2025, 9:13 AM - Ander: privé\n"
            "10/14/2025, 10:00 - Ander: privé\n"))
        self.kies(datumvolgorde="MDY")
        self.assertEqual(self.tel()["2025-10-13"], {"inkomend": 1, "uitgaand": 1})
        self.assertEqual(self.tel()["2025-10-14"], {"inkomend": 1, "uitgaand": 0})

    def test_opnieuw_tellen_is_idempotent_en_late_export_corrigeert_dag(self):
        pad = self.maak_txt()
        self.kies()
        eerste = self.tel()
        self.assertTrue(W.bewaar_dagen(self.staat, eerste))
        voor = self.staat.stat().st_mtime_ns
        self.assertFalse(W.bewaar_dagen(self.staat, self.tel()))
        self.assertEqual(voor, self.staat.stat().st_mtime_ns)
        pad.write_text(INHOUD + "[13/10/2025, 11:00:00] Ander: later gesynchroniseerd\n", encoding="utf-8")
        pad.chmod(0o600)
        nieuwe = self.tel()
        self.assertTrue(W.bewaar_dagen(self.staat, nieuwe))
        self.assertEqual(nieuwe["2025-10-13"], {"inkomend": 2, "uitgaand": 1})
        opgeslagen = self.staat.read_text(encoding="utf-8")
        self.assertNotIn("Ander", opgeslagen)
        self.assertNotIn("sentinel", opgeslagen)
        self.assertNotIn("voorbeeld.test", opgeslagen)
        self.assertEqual(self.staat.stat().st_mode & 0o777, 0o600)

    def test_geen_selectie_of_ambigue_map_leest_niets(self):
        self.maak_txt()
        with self.assertRaises(W.BronFout):
            W.laad_config(self.config)
        self.kies()
        self.maak_txt("gekozen (1).txt", "[13/10/2025, 09:12] Ander: niet lezen\n")
        with self.assertRaisesRegex(W.BronFout, "extra bestanden"):
            self.tel()

    def test_dubbele_json_sleutels_in_hoofdobject_en_gesprek_stoppen(self):
        self.maak_txt()
        data = self.kies()
        tekst = json.dumps(data, ensure_ascii=False)
        for deel, dubbel in (
            ("hoofdobject", tekst.replace('"versie": 1', '"versie": 1, "versie": 1', 1)),
            ("gesprek", tekst.replace('"bestand": "gekozen.txt"',
                                      '"bestand": "gekozen.txt", "bestand": "gekozen.txt"', 1)),
        ):
            with self.subTest(deel=deel):
                self.assertNotEqual(dubbel, tekst)
                self.config.write_text(dubbel, encoding="utf-8")
                with self.assertRaisesRegex(W.BronFout, "onleesbaar") as fout:
                    W.laad_config(self.config)
                self.assertNotIn("gekozen.txt", str(fout.exception))

    def test_twee_momentopnamen_met_hetzelfde_afzenderpaar_stoppen(self):
        self.maak_txt("oud.txt")
        self.maak_txt("nieuw.txt")
        data = self.kies("oud.txt", eigen="Café")
        data["gesprekken"].append({
            "bestand": "nieuw.txt", "eigen_afzender": "Ander",
            "andere_afzender": "Cafe\u0301", "datumvolgorde": "DMY",
        })
        self.config.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(W.BronFout, "hetzelfde afzenderpaar"):
            self.tel()

    def test_exportmap_is_exact_lokaal_pad_zonder_omleiding(self):
        self.maak_txt()
        data = self.kies()
        andere = self.basis / "repo"
        andere.mkdir(mode=0o700)
        (andere / "gekozen.txt").write_text(INHOUD, encoding="utf-8")
        (andere / "gekozen.txt").chmod(0o600)
        data["export_map"] = str(andere)
        self.config.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(W.BronFout, "niet de toegestane"):
            W.laad_config(self.config)
        alias = self.basis / "alias"
        alias.symlink_to(self.exports, target_is_directory=True)
        data["export_map"] = str(alias)
        self.config.write_text(json.dumps(data), encoding="utf-8")
        with patch.object(W, "EXPORT_MAP", alias):
            with self.assertRaisesRegex(W.BronFout, "omleiding"):
                W.laad_config(self.config)

    def test_afzenderprefixen_zijn_niet_dubbelzinnig(self):
        self.maak_txt()
        self.kies(eigen="Eigen", andere="Eigen: Team")
        with self.assertRaisesRegex(W.BronFout, "dubbelzinnig"):
            self.tel()

    def test_naamvariant_met_hoofdletters_is_dubbelzinnig(self):
        self.maak_txt()
        self.kies()
        namen = [self.exports / "gekozen.txt", self.exports / "GEKOZEN.TXT"]
        with patch.object(Path, "iterdir", return_value=namen):
            with self.assertRaisesRegex(W.BronFout, "extra bestanden"):
                self.tel()

    def test_zip_met_media_wordt_afgewezen_zonder_uitpakken(self):
        self.maak_zip(extra="foto.jpg")
        self.kies("gekozen.zip")
        with self.assertRaisesRegex(W.BronFout, "zonder media"):
            self.tel()
        self.assertFalse((self.exports / "foto.jpg").exists())

    def test_zip_met_onbekende_compressie_wordt_afgewezen(self):
        pad = self.exports / "gekozen.zip"
        with zipfile.ZipFile(pad, "w", compression=zipfile.ZIP_BZIP2) as pakket:
            pakket.writestr("_chat.txt", INHOUD)
        pad.chmod(0o600)
        self.kies("gekozen.zip")
        with self.assertRaisesRegex(W.BronFout, "compressie"):
            self.tel()

    def test_tekststream_stopt_bij_grootte_en_lange_regel(self):
        with patch.object(W, "MAX_EXPORT_BYTES", 12):
            with self.assertRaisesRegex(W.BronFout, "te groot"):
                list(W._decodeer(io.BytesIO(b"[13/10/2025]\n[14/10/2025]\n")))
        with patch.object(W, "MAX_REGEL", 5):
            with self.assertRaisesRegex(W.BronFout, "te lange regel"):
                list(W._decodeer(io.BytesIO(b"een heel lange regel\n")))

    def test_onverwachte_afzender_en_beschadigde_tijd_stoppen(self):
        pad = self.maak_txt(inhoud="[13/10/2025, 09:12] Derde: privé\n")
        self.kies()
        with self.assertRaisesRegex(W.BronFout, "onverwachte afzender"):
            self.tel()
        pad.write_text("[31/02/2025, 09:12] Ander: privé\n", encoding="utf-8")
        with self.assertRaisesRegex(W.BronFout, "ongeldig"):
            self.tel()
        pad.write_text("[13/10/2025, 99:99] Ander: privé\n", encoding="utf-8")
        with self.assertRaisesRegex(W.BronFout, "Tijd.*ongeldig"):
            self.tel()
        pad.write_text("[13/10/2025 09:12] Ander: privé\n", encoding="utf-8")
        with self.assertRaisesRegex(W.BronFout, "Berichtkop.*onleesbaar"):
            self.tel()
        pad.write_text("[13/10/2025, 09:12] Derde:\tprivé\n", encoding="utf-8")
        with self.assertRaisesRegex(W.BronFout, "onverwachte afzender"):
            self.tel()

    def test_tab_na_bekende_afzender_wordt_geteld(self):
        self.maak_txt(inhoud="[13/10/2025, 09:12] Ander:\tprivé\n")
        self.kies()
        self.assertEqual(self.tel(), {"2025-10-13": {"inkomend": 1, "uitgaand": 0}})

    def test_datumachtige_vervolgregel_en_nfc_afzender(self):
        self.maak_txt(inhoud=("[13/10/2025, 09:12] Cafe\u0301: privé\n"
                             "13/10/2025 blijft een datum in de tekst, geen nieuwe kop\n"))
        self.kies(eigen="Eigen", andere="Café")
        self.assertEqual(self.tel(), {"2025-10-13": {"inkomend": 1, "uitgaand": 0}})

    def test_geen_symlinks_of_open_rechten(self):
        pad = self.maak_txt()
        self.kies()
        pad.chmod(0o644)
        with self.assertRaises(W.BronFout):
            self.tel()

    def test_gekozen_export_wisselt_na_selectie_niet_naar_symlink(self):
        pad = self.maak_txt()
        self.kies()
        gekozen = W.laad_config(self.config)
        pad.unlink()
        ander = self.basis / "ander.txt"
        ander.write_text(INHOUD, encoding="utf-8")
        ander.chmod(0o600)
        pad.symlink_to(ander)
        with self.assertRaises(W.BronFout):
            W.tel_geselecteerde(gekozen)
        pad.unlink()
        doel = self.basis / "niet-gekozen.txt"
        doel.write_text(INHOUD, encoding="utf-8")
        doel.chmod(0o600)
        pad.symlink_to(doel)
        with self.assertRaises(W.BronFout):
            self.tel()

    def test_exportmap_wisselt_na_selectie_niet_naar_andere_map(self):
        self.maak_txt()
        self.kies()
        gekozen = W.laad_config(self.config)
        oud = self.basis / "oude-exports"
        self.exports.rename(oud)
        vervanging = self.basis / "vervanging"
        vervanging.mkdir(mode=0o700)
        (vervanging / "gekozen.txt").write_text(INHOUD, encoding="utf-8")
        (vervanging / "gekozen.txt").chmod(0o600)
        vervanging.rename(self.exports)
        with self.assertRaisesRegex(W.BronFout, "sinds de selectie gewijzigd"):
            W.tel_geselecteerde(gekozen)

    def test_selectie_en_token_volgen_geen_symlink(self):
        self.maak_txt()
        self.kies()
        andere_config = self.basis / "andere-config.json"
        self.config.rename(andere_config)
        self.config.symlink_to(andere_config)
        with self.assertRaises(W.BronFout):
            W.laad_config(self.config)
        self.config.unlink()
        andere_config.rename(self.config)
        ander_token = self.basis / "ander-token"
        self.token.rename(ander_token)
        self.token.symlink_to(ander_token)
        with self.assertRaisesRegex(W.BronFout, "Bordtoegang ontbreekt"):
            W.run(self.config, self.staat, self.token)

    def test_selectie_in_dropbox_of_open_map_wordt_geweigerd(self):
        self.maak_txt()
        data = self.kies()
        dropbox = self.basis / "Test Dropbox"
        dropbox.mkdir(mode=0o700)
        config = dropbox / "keuze.json"
        config.write_text(json.dumps(data), encoding="utf-8")
        config.chmod(0o600)
        with self.assertRaisesRegex(W.BronFout, "Dropbox"):
            W.laad_config(config)
        open_map = self.basis / "open-map"
        open_map.mkdir(mode=0o755)
        config = open_map / "keuze.json"
        config.write_text(json.dumps(data), encoding="utf-8")
        config.chmod(0o600)
        with self.assertRaisesRegex(W.BronFout, "niet privé"):
            W.laad_config(config)

    def test_fifo_als_export_blokkeert_niet(self):
        fifo = self.exports / "gekozen.txt"
        os.mkfifo(fifo, 0o600)
        self.kies()
        with self.assertRaisesRegex(W.BronFout, "niet privé"):
            self.tel()

    def test_tweede_ronde_stopt_voor_bordactie_en_slot_is_prive(self):
        self.maak_txt()
        self.kies()
        with W.exclusieve_ronde():
            with patch.object(W, "tunnel", side_effect=AssertionError("bord mocht niet openen")):
                with self.assertRaisesRegex(W.BronFout, "loopt al een WhatsApp-ronde"):
                    W.run(self.config, self.staat, self.token)
        self.assertFalse(self.staat.exists())
        self.assertEqual(W.LOCK_PAD.stat().st_mode & 0o777, 0o600)
        W.LOCK_PAD.chmod(0o644)
        with self.assertRaisesRegex(W.BronFout, "niet privé"):
            with W.exclusieve_ronde():
                pass
        W.LOCK_PAD.unlink()
        ander = self.basis / "ander-slot"
        ander.write_text("", encoding="utf-8")
        ander.chmod(0o600)
        W.LOCK_PAD.symlink_to(ander)
        with self.assertRaisesRegex(W.BronFout, "niet beschikbaar"):
            with W.exclusieve_ronde():
                pass

    def test_privacygrendel_op_bord_en_geen_verstuurroute(self):
        self.maak_zip()
        self.kies("gekozen.zip")
        vastgelegd = []

        class Ronde:
            def __enter__(self):
                self.detail = ""
                self.werkwijze = "synthetische grenzen"
                return self

            def __exit__(self, soort, fout, spoor):
                vastgelegd.append(("detail", self.detail))
                return False

            def bron(self, naam, inhoud):
                vastgelegd.append((naam, inhoud))

            def nood(self, tekst, wie="mehdi"):
                vastgelegd.append(("nood", tekst))

        class Agent:
            def __init__(self, naam):
                self.naam = naam

            def ronde(self, taak):
                vastgelegd.append(("taak", taak))
                return Ronde()

            def klaarzet(self, *_):
                raise AssertionError("geen bericht naar een andere agent")

        nep = types.SimpleNamespace(Agent=Agent, TOKEN="", grenzen=lambda _: (["grens"], ["besluit"]))
        oud = sys.modules.get("bord")
        sys.modules["bord"] = nep
        self.addCleanup(lambda: sys.modules.__setitem__("bord", oud) if oud is not None else sys.modules.pop("bord", None))
        nu = datetime.now(timezone.utc).isoformat()
        meting = {"status": "klaar", "ts": nu, "kennis_ts": nu,
                  "status_ronde": "a" * 32, "kennis_ronde": "a" * 32}
        with patch.object(W, "tunnel", self.nep_tunnel), patch.object(W, "bord_stand", return_value=meting):
            self.assertTrue(W.run(self.config, self.staat, self.token))
        self.assertEqual(nep.PLATFORM, "http://127.0.0.1:12345")
        uitvoer = json.dumps(vastgelegd, ensure_ascii=False) + self.staat.read_text(encoding="utf-8")
        for prive in ("Eigen", "Ander", "sentinel", "voorbeeld.test", "gekozen.zip"):
            self.assertNotIn(prive, uitvoer)
        self.assertIn("2025-10-14", uitvoer)

    def test_echte_gedeelde_ronde_stopt_bij_bronfout_zonder_privegegevens(self):
        self.maak_zip(inhoud="[13/10/2025, 09:12:01] Derde: privé sentinel voorbeeld\n")
        self.kies("gekozen.zip")
        pad = Path(__file__).resolve().parents[1] / "koppelingen/bord.py"
        spec = importlib.util.spec_from_file_location("bord", pad)
        bord = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bord)
        uitgaand = []

        def call(route, payload=None, method=None):
            uitgaand.append((route, payload))
            if route.endswith("/werkwijze"):
                return {"werkwijze": (Path(__file__).resolve().parents[1]
                                      / "werkwijze/whatsapp-wacht.md").read_text(encoding="utf-8")}
            if route == "/api/nood":
                return {"nood": []}
            if route == "/api/agents":
                return []
            return {}

        bord.call = call
        with patch.dict(sys.modules, {"bord": bord}), patch.object(W, "tunnel", self.nep_tunnel):
            with self.assertRaises(W.BronFout):
                W.run(self.config, self.staat, self.token)
        statussen = [p for route, p in uitgaand if route == "/agent-status"]
        self.assertEqual(statussen[-1]["status"], "fout")
        self.assertFalse(self.staat.exists())
        uitvoer = json.dumps(uitgaand, ensure_ascii=False)
        for prive in ("Eigen", "Ander", "Derde", "sentinel", "voorbeeld", "gekozen.zip"):
            self.assertNotIn(prive, uitvoer)
        self.assertFalse(any(route in ("/api/klaarzet", "/api/gesprekken") for route, _ in uitgaand))

    def test_gedeelde_ronde_gebruikt_interne_api_en_controleert_bordstand(self):
        self.maak_zip()
        self.kies("gekozen.zip")
        pad = Path(__file__).resolve().parents[1] / "koppelingen/bord.py"
        spec = importlib.util.spec_from_file_location("bord", pad)
        bord = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bord)
        uitgaand = []

        def call(route, payload=None, method=None):
            self.assertEqual(bord.PLATFORM, "http://127.0.0.1:12345")
            uitgaand.append((route, payload))
            if route.endswith("/werkwijze"):
                return {"werkwijze": (Path(__file__).resolve().parents[1]
                                      / "werkwijze/whatsapp-wacht.md").read_text(encoding="utf-8")}
            if route == "/api/nood":
                return {"nood": []}
            if route == "/api/agents":
                return []
            return {}

        bord.call = call
        nu = datetime.now(timezone.utc).isoformat()
        meting = {"status": "klaar", "ts": nu, "kennis_ts": nu,
                  "status_ronde": "a" * 32, "kennis_ronde": "a" * 32}
        with patch.dict(sys.modules, {"bord": bord}), patch.object(W, "tunnel", self.nep_tunnel), \
                patch.object(W, "bord_stand", return_value=meting):
            self.assertTrue(W.run(self.config, self.staat, self.token))
        gevallen = (
            ("bord onleesbaar", None, False),
            ("kennis uit andere ronde", {**meting, "kennis_ronde": "b" * 32}, True),
            ("latere geslaagde ronde", {**meting, "status_ronde": "b" * 32,
                                        "kennis_ronde": "b" * 32}, False),
        )
        for naam, onbevestigd, eigen_status in gevallen:
            voor = len([p for route, p in uitgaand if route == "/agent-status"])
            with self.subTest(geval=naam), \
                    patch.dict(sys.modules, {"bord": bord}), \
                    patch.object(W, "tunnel", self.nep_tunnel), \
                    patch.object(W, "bord_stand", return_value=onbevestigd):
                with self.assertRaisesRegex(W.BronFout, "niet bevestigd"):
                    W.run(self.config, self.staat, self.token)
            statussen = [p for route, p in uitgaand if route == "/agent-status"][voor:]
            self.assertEqual([p["status"] for p in statussen],
                             ["actief", "klaar"] + (["fout"] if eigen_status else []))
            if eigen_status:
                self.assertEqual(statussen[-1]["detail"], "Bord heeft de ronde niet bevestigd")
        routes = [route for route, _ in uitgaand]
        self.assertIn("/api/agent/whatsapp-wacht/werkwijze", routes)
        self.assertIn("/api/agent/whatsapp-wacht/kennis", routes)
        status = [p for route, p in uitgaand if route == "/agent-status" and p["status"] == "klaar"][0]
        kennis = [p for route, p in uitgaand if route.endswith("/kennis")][-1]
        self.assertEqual(BORDSTAND._enige_ronde(status["detail"], BORDSTAND.STATUS_RONDE), "a" * 32)
        self.assertEqual(BORDSTAND._enige_ronde(kennis["kennis"], BORDSTAND.KENNIS_RONDE), "a" * 32)
        self.assertFalse(any(route in ("/api/klaarzet", "/api/gesprekken") for route in routes))
        uitvoer = json.dumps(uitgaand, ensure_ascii=False)
        for prive in ("Eigen", "Ander", "sentinel", "voorbeeld.test", "gekozen.zip"):
            self.assertNotIn(prive, uitvoer)

    def test_geen_succes_als_bord_eindstatus_of_kennis_niet_bevestigt(self):
        self.maak_zip()
        self.kies("gekozen.zip")
        nonce = "a" * 32
        nu = datetime.now(timezone.utc).isoformat()
        juist = {"status": "klaar", "ts": nu, "kennis_ts": nu,
                 "status_ronde": nonce, "kennis_ronde": nonce}
        self.assertTrue(W.bevestigd(juist, nonce))
        self.assertFalse(W.bevestigd(None, nonce))
        self.assertFalse(W.bevestigd({**juist, "kennis_ronde": "b" * 32}, nonce))
        self.assertFalse(W.bevestigd({**juist, "status_ronde": "b" * 32}, nonce))
        self.assertFalse(W.bevestigd({**juist, "kennis_ts": "2100-01-01T00:00:00Z"}, nonce))
        self.assertFalse(W.bevestigd({**juist, "status": "actief"}, nonce))

    def test_bordstand_geeft_alleen_twee_ronde_ids_uit_de_database(self):
        database = self.basis / "bord.db"
        con = sqlite3.connect(database)
        con.executescript("CREATE TABLE status(naam TEXT PRIMARY KEY, status TEXT, ts TEXT, detail TEXT);"
                          "CREATE TABLE agent(naam TEXT PRIMARY KEY, kennis_ts TEXT, kennis TEXT);")
        nu = datetime.now(timezone.utc).isoformat()
        nonce = "a" * 32
        con.execute("INSERT INTO status VALUES(?,?,?,?)",
                    ("whatsapp-wacht", "klaar", nu, f"privé; 3 berichten; ronde-id:{nonce}"))
        con.execute("INSERT INTO agent VALUES(?,?,?)",
                    ("whatsapp-wacht", nu, f"werkwijze: PRIVÉ SENTINEL\nronde-id-{nonce}: 0 tekens, e3b0c442"))
        con.commit()
        con.close()
        stand = BORDSTAND.stand("whatsapp-wacht", database, met_ronde=True)
        self.assertEqual(stand["status_ronde"], nonce)
        self.assertEqual(stand["kennis_ronde"], nonce)
        self.assertNotIn("detail", stand)
        self.assertNotIn("kennis", stand)
        self.assertNotIn("SENTINEL", json.dumps(stand))
        self.assertTrue(W.bevestigd(stand, nonce))
        opdracht = subprocess.run([sys.executable, str(STAND_PAD), "whatsapp-wacht", "--ronde"],
                                 env={**os.environ, "AGENTS_DB": str(database)},
                                 capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(opdracht.stdout)["status_ronde"], nonce)
        self.assertNotIn("SENTINEL", opdracht.stdout)
        con = sqlite3.connect(database)
        con.execute("UPDATE status SET detail=? WHERE naam='whatsapp-wacht'",
                    ("privé; 3 berichten; ronde-id:" + "b" * 32,))
        con.commit()
        con.close()
        self.assertFalse(W.bevestigd(BORDSTAND.stand("whatsapp-wacht", database, met_ronde=True), nonce))

    def test_zonder_bordgrenzen_wordt_geen_export_geopend(self):
        self.maak_zip()
        self.kies("gekozen.zip")

        class Ronde:
            werkwijze = "geen grenzen"

            def __enter__(self):
                return self

            def __exit__(self, soort, fout, spoor):
                return False

            def nood(self, tekst, wie="mehdi"):
                pass

        nep = types.SimpleNamespace(Agent=lambda _: types.SimpleNamespace(ronde=lambda _: Ronde()),
                                    TOKEN="", grenzen=lambda _: ([], []))
        with patch.dict(sys.modules, {"bord": nep}), patch.object(W, "tunnel", self.nep_tunnel), \
                patch.object(W, "laad_config") as laad:
            with self.assertRaisesRegex(W.BronFout, "veiligheidsgrenzen"):
                W.run(self.config, self.staat, self.token)
        laad.assert_not_called()

    def test_ci_draait_de_whatsapp_grendels(self):
        workflow = Path(__file__).resolve().parents[2] / ".github/workflows/agentnorm-grendels.yml"
        self.assertIn("python3 mijnagents-runner/tests/test_whatsapp_wacht.py",
                      workflow.read_text(encoding="utf-8"))

    def test_agentnorm_vindt_de_mac_runner(self):
        rij = {"naam": "whatsapp-wacht", "draait_op": "Mac",
               "kennis": "gedeelde lessen\ncollega's op het bord"}
        self.assertEqual(Path(CONTROLE._runnerpad("whatsapp-wacht")), BRON)
        self.assertTrue(CONTROLE.n5_runner_bestaat(rij, None)[0])
        self.assertTrue(CONTROLE.n12_gebruikt_de_ronde(rij, None)[0])
        self.assertTrue(CONTROLE.n13_leest_de_lessen(rij, None)[0])
        self.assertTrue(CONTROLE.n14_kent_zijn_collegas(rij, None)[0])

    def test_agentnorm_op_verzoek_veroudert_geslaagd_niet(self):
        oud = (datetime.now(timezone.utc) - timedelta(days=9)).isoformat()
        ronde_id = "a" * 32
        rij = {"naam": "whatsapp-wacht", "cadans": "op verzoek", "kennis_ts": oud,
               "kennis": f"werkwijze op het bord: 10 tekens, abcdef12\n"
                         f"ronde-id-{ronde_id}: 0 tekens, e3b0c442",
               "draait_op": "Mac"}
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.execute("CREATE TABLE status(naam TEXT PRIMARY KEY, status TEXT, ts TEXT, taak TEXT, detail TEXT)")
        con.execute("INSERT INTO status VALUES(?,?,?,?,?)",
                    ("whatsapp-wacht", "klaar", oud, "proef", f"privé; ronde-id:{ronde_id}"))
        self.assertTrue(CONTROLE.n4_kennis_gemeld(rij, con)[0])
        self.assertTrue(CONTROLE.n11_hartslag(rij, con)[0])
        con.execute("UPDATE status SET detail=?", ("privé; ronde-id:" + "b" * 32,))
        self.assertFalse(CONTROLE.n4_kennis_gemeld(rij, con)[0])
        con.execute("UPDATE status SET detail=?", (f"privé; ronde-id:{ronde_id}",))
        self.assertTrue(CONTROLE.n4_kennis_gemeld(rij, con)[0])
        con.execute("UPDATE status SET status='waakt'")
        self.assertTrue(CONTROLE.n4_kennis_gemeld(rij, con)[0])
        self.assertTrue(CONTROLE.n11_hartslag(rij, con)[0])
        for status in ("fout", "actief"):
            con.execute("UPDATE status SET status=?", (status,))
            self.assertFalse(CONTROLE.n11_hartslag(rij, con)[0])
            self.assertFalse(CONTROLE.n4_kennis_gemeld(rij, con)[0])
        con.execute("DELETE FROM status")
        self.assertFalse(CONTROLE.n11_hartslag(rij, con)[0])
        self.assertFalse(CONTROLE.n4_kennis_gemeld(rij, con)[0])
        self.assertFalse(CONTROLE.n4_kennis_gemeld({**rij, "kennis_ts": ""}, con)[0])
        con.execute("INSERT INTO status VALUES(?,?,?,?,?)",
                    ("whatsapp-wacht", "klaar", oud, "proef", f"privé; ronde-id:{ronde_id}"))
        gewone = {**rij, "cadans": "dagelijks"}
        self.assertFalse(CONTROLE.n4_kennis_gemeld(gewone, con)[0])
        self.assertFalse(CONTROLE.n11_hartslag(gewone, con)[0])
        andere_op_verzoek = {**rij, "naam": "andere-agent", "kennis": "werkwijze gemeld"}
        self.assertTrue(CONTROLE.n4_kennis_gemeld(andere_op_verzoek, con)[0])


if __name__ == "__main__":
    unittest.main()
