#!/usr/bin/env python3
"""Geen foto-I/O/export/netwerk: geweigerde bron blijft als fout zichtbaar."""
import importlib.util
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import json
import os
import re
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
from types import SimpleNamespace
from zoneinfo import ZoneInfo


class ICloudStatus(unittest.TestCase):
    def inhoud(self, **changes):
        project = "/Work All/01. H-A WORK/0 H-A Standaard projects/5. STAN/9999 Fictief"
        data = {"dossier": "9999", "project_ref": "h-architects:9999", "bezoek_id": "dc2ba603-1f46-4014-9d16-65d473b14712",
                "datum": "2026-10-14", "start": "2026-10-14T11:00:00+02:00", "einde": "2026-10-14T12:00:00+02:00",
                "adres": "Fictief adres", "projectmap": project, "bezoekmap": project + "/_00. Communication/20261014 bezoek 1"}
        data.update(changes)
        return data

    def setUp(self):
        self.home = tempfile.TemporaryDirectory()
        self.addCleanup(self.home.cleanup)
        spec = importlib.util.spec_from_file_location("icloud_status_proef", Path(__file__).resolve().parents[1] / "mac/icloud_wacht.py")
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(os.environ, {"HOME": self.home.name}), patch.object(sys, "argv", ["icloud_wacht.py"]):
            spec.loader.exec_module(self.module)
        self.module.TOKEN = "alleen-fictief-testtoken"
        self.export_orig = self.module.exporteer_naar
        self.export_jpg_orig = self.module.exporteer_jpg_naar
        self.hartslag_orig = self.module.hartslag
        self.module.DROPBOX_LOKAAL = str(Path(self.home.name) / "Dropbox")
        self.statussen, self.afgevinkt = [], []
        self.module.hartslag = lambda status, **kw: self.statussen.append((status, kw))
        self.module.taak_opgepakt = lambda kid: self.afgevinkt.append(kid)
        self.module.exporteer_naar = lambda *a: self.fail("geweigerde bron mag niet worden geëxporteerd")
        self.module.exporteer_jpg_naar = lambda *a: self.fail("geweigerde bron mag niet worden geëxporteerd")
        self.module.exporteer = lambda *a: self.fail("geweigerde bron mag niet worden geëxporteerd")
        self.module.bord = lambda *a: self.fail("deze fout mag geen inhoud publiceren")

    def test_fototaak_met_authorization_denied_blijft_open_en_gaat_op_fout(self):
        m = self.module
        m.taken_lezen = lambda: [{"id": 12, "inhoud": json.dumps(self.inhoud())}]
        m.coord = lambda address: (50.0, 4.0)
        m.fotos_van = lambda day: (_ for _ in ()).throw(sqlite3.DatabaseError("authorization denied"))
        with patch.object(sys, "argv", ["icloud_wacht.py", "--taken"]):
            self.assertEqual(m.main(), 1)
        self.assertEqual([s for s, _ in self.statussen], ["actief", "fout"])
        self.assertEqual(self.afgevinkt, [])
        self.assertIn("macOS weigert", self.statussen[-1][1]["detail"])

    def test_avondronde_met_permissionerror_publiceert_geen_fotogegevens(self):
        m = self.module
        m.fotos_van = lambda day: (_ for _ in ()).throw(PermissionError("gevoelig pad of token mag niet in de melding"))
        with patch.object(m.os.path, "exists", return_value=True):
            self.assertEqual(m.main(), 1)
        self.assertEqual([s for s, _ in self.statussen], ["actief", "fout"])
        self.assertNotIn("gevoelig", self.statussen[-1][1]["detail"])
        self.assertEqual(self.afgevinkt, [])

    def test_timeout_is_fout_en_niet_klaar_of_blijvend_actief(self):
        self.module.taken_lezen = lambda: (_ for _ in ()).throw(urllib.error.URLError("fictieve timeout"))
        with patch.object(sys, "argv", ["icloud_wacht.py", "--taken"]):
            self.assertEqual(self.module.main(), 1)
        self.assertEqual([s for s, _ in self.statussen], ["fout"])
        self.assertEqual(self.afgevinkt, [])

    def test_lege_werkvoorraad_is_geen_providerfout(self):
        self.module.taken_lezen = lambda: []
        with patch.object(sys, "argv", ["icloud_wacht.py", "--taken"]):
            self.assertEqual(self.module.main(), 0)
        self.assertEqual(self.statussen, [])
        self.assertEqual(self.afgevinkt, [])

    def inhoud_tkn(self, **changes):
        project = "/Work/TKN BURO WORK/1 Projects/2026/47035_Barsten & Scheuren_Proeflaan 23, 9998 Proefgem"
        fotomap = Path(self.module.DROPBOX_LOKAAL) / project.lstrip("/") / "1. Foto's"
        fotomap.mkdir(parents=True, exist_ok=True)
        data = {"dossier": "3999", "mapnummer": "47035", "project_ref": "tkn:47035",
                "bezoek_ref": "verslagopdracht:12", "datum": "2026-10-14",
                "van_tijd": "2026-10-14T11:00:00+02:00", "tot_tijd": "2026-10-14T12:00:00+02:00",
                "adres": "Proeflaan 23, 9998 Proefgem", "projectmap": project,
                "doelmap": project + "/1. Foto's/2026-10-14 iPhone", "lat": 50.0, "lon": 4.0}
        data.update(changes)
        return data

    def fake_run(self, fotos, inhoud=None, geleverd=None, echt_jpg=False, nu=None, taak_id=12, ext=".jpg", jpg_lukt=True):
        m = self.module
        logs, exports = [], []
        m.taken_lezen = lambda: [{"id": taak_id, "inhoud": json.dumps(inhoud or self.inhoud())}]
        m.coord = lambda address: (50.0, 4.0)
        self.lezingen = []
        m.fotos_van = lambda day: self.lezingen.append(day) or fotos
        m.bord = lambda path, data: logs.append((path, data)) or {"ok": True}
        def export(selected, doel):
            exports.append([f["uuid"] for f in selected])
            Path(doel).mkdir(parents=True, exist_ok=True)
            n = len(selected) if geleverd is None else geleverd
            for f in selected[:n]:
                f["geexporteerd"] = True
                f["export"] = f["uuid"] + ext
                Path(doel, f["export"]).write_bytes(b"x")
            return n
        m.exporteer_naar = export
        m.exporteer_jpg_naar = self.export_jpg_orig if echt_jpg else export
        def jpeg_kopieen(doel):
            for heic in Path(doel).glob("*.heic") if jpg_lukt else ():
                heic.with_suffix(".jpg").write_bytes(b"jpg")
            return 0
        m.jpeg_kopieen = jpeg_kopieen
        class Klok(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromisoformat(nu).astimezone(tz)
        klok = patch.object(m, "datetime", Klok) if nu else nullcontext()
        with patch.object(sys, "argv", ["icloud_wacht.py", "--taken"]), klok:
            code = m.main()
        return code, exports, logs

    def foto(self, uid, tijd="2026-10-14T09:30:00+00:00", lat=50.0, lon=4.0):
        return {"uuid": uid, "vastgelegd_utc": tijd, "tijd": "11:30", "lat": lat, "lon": lon, "bestand": "fictief.jpg"}

    def test_alleen_gevraagde_uur_en_straal_worden_geleverd(self):
        fotos = [self.foto("binnen"), self.foto("voor_bezoek", "2026-10-14T08:59:59+00:00"),
                 self.foto("ander_bezoek", "2026-10-14T10:30:00+00:00"), self.foto("exact_einde", "2026-10-14T10:00:00+00:00"),
                 self.foto("tussen_300_600m", lat=50.004)]
        code, exports, _ = self.fake_run(fotos)
        self.assertEqual(code, 0)
        self.assertEqual(exports, [["binnen"]])
        self.assertEqual(self.afgevinkt, [12])
        self.assertEqual(self.statussen[-1][0], "klaar")

    def test_geen_automatische_straalverruiming_bij_lege_selectie(self):
        code, exports, _ = self.fake_run([self.foto("tussen_300_600m", lat=50.004)])
        self.assertEqual(code, 1)
        self.assertEqual(exports, [])
        self.assertEqual(self.afgevinkt, [])
        self.assertIn("fotoselectie_leeg", self.statussen[-1][1]["detail"])

    def test_lege_of_gedeeltelijke_export_wordt_nooit_afgevinkt(self):
        for n in (0, 1):
            with self.subTest(geleverd=n):
                self.statussen.clear()
                code, _, _ = self.fake_run([self.foto("eerste"), self.foto("tweede")], geleverd=n)
                self.assertEqual(code, 1)
                self.assertEqual(self.afgevinkt, [])
                self.assertIn("fotolevering_gedeeltelijk", self.statussen[-1][1]["detail"])

    def test_ha_heic_zonder_jpg_wordt_niet_afgevinkt(self):
        # Overleg W4 P3, Codex X4: een hersteltaak komt maar één keer; een mislukte omzetting houdt haar open.
        code, _, _ = self.fake_run([self.foto("eerste")], ext=".heic", jpg_lukt=False)
        self.assertEqual(code, 1)
        self.assertEqual(self.afgevinkt, [])
        self.assertIn("omzetting_mislukt", self.statussen[-1][1]["detail"])
        self.afgevinkt.clear()
        code, _, _ = self.fake_run([self.foto("tweede")], ext=".heic", jpg_lukt=True, taak_id=13)
        self.assertEqual(code, 0)
        self.assertEqual(self.afgevinkt, [13])

    def test_ontbrekend_venster_leest_geen_fotometadata(self):
        data = self.inhoud()
        data.pop("start")
        self.module.fotos_van = lambda day: self.fail("ontbrekend venster mag geen foto's lezen")
        code, exports, _ = self.fake_run([], inhoud=data)
        self.assertEqual(code, 1)
        self.assertEqual(exports, [])
        self.assertEqual(self.afgevinkt, [])
        self.assertEqual(self.lezingen, [])
        self.assertIn("bezoekvenster_ontbreekt", self.statussen[-1][1]["detail"])

    def test_e4_terugvalvenster_wordt_aanvaard_en_reden_staat_in_manifest(self):
        data = self.inhoud(start="2026-10-14T11:15:00+02:00", einde="2026-10-14T12:30:00+02:00",
                           reden="E4, geen afspraak", lat=50.0, lon=4.0)
        code, exports, _ = self.fake_run([self.foto("e4", "2026-10-14T09:30:00Z")], inhoud=data)
        self.assertEqual(code, 0)
        self.assertEqual(exports, [["e4"]])
        tekst = (Path(self.module.taakdoel(data)) / "00 fotos.md").read_text()
        self.assertIn("E4, geen afspraak", tekst)

    def test_e4_bij_middernacht_houdt_het_volledige_terugvalvenster(self):
        d = self.inhoud(start="2026-10-13T23:50:00+02:00", einde="2026-10-14T01:05:00+02:00",
                        reden="E4, geen afspraak")
        start, einde = self.module.taakvenster(d)
        self.assertEqual((start + timedelta(minutes=15)).astimezone(ZoneInfo("Europe/Brussels")).date().isoformat(), d["datum"])
        self.assertEqual((einde - timedelta(minutes=60)).astimezone(ZoneInfo("Europe/Brussels")).date().isoformat(), d["datum"])

    def test_bestaand_fotomanifest_blijft_bewaard_bij_nieuwe_ronde(self):
        data = self.inhoud(lat=50.0, lon=4.0)
        doel = Path(self.module.taakdoel(data))
        doel.mkdir(parents=True, exist_ok=True)
        (doel / "00 fotos.md").write_text("oude meting\n")
        code, _, _ = self.fake_run([self.foto("nieuw")], inhoud=data)
        self.assertEqual(code, 0)
        self.assertEqual((doel / "00 fotos.md").read_text(), "oude meting\n")
        versies = list(doel.glob("00 fotos *.md"))
        self.assertEqual(len(versies), 1)
        self.assertIn("Venster:", versies[0].read_text())

    def test_geen_gps_of_tijd_blijft_onbeslist_en_wordt_niet_geexporteerd(self):
        code, exports, _ = self.fake_run([self.foto("goed"), self.foto("geen_gps", lat=None)])
        self.assertEqual(code, 1)
        self.assertEqual(exports, [["goed"]])
        self.assertEqual(self.afgevinkt, [])
        self.assertIn("fotoselectie_onbeslist", self.statussen[-1][1]["detail"])

    def test_verkeerde_firma_of_buiten_project_geeft_geen_export(self):
        for data in (self.inhoud(project_ref="unabo:9999"), self.inhoud(bezoekmap="/private/fotos"),
                     self.inhoud(start="2026-10-14T11:00:00"), self.inhoud(bezoek_id=None), self.inhoud(straal_m=600)):
            with self.subTest(gegevens=data):
                code, exports, _ = self.fake_run([self.foto("fictief")], inhoud=data)
                self.assertEqual(code, 1)
                self.assertEqual(exports, [])
                self.assertEqual(self.afgevinkt, [])
                self.assertEqual(self.lezingen, [])

    def test_dubbel_lokaal_uur_bij_wintertijd_wordt_op_utc_gescheiden(self):
        m = self.module
        start, einde = m.taakvenster(self.inhoud(datum="2026-10-25", start="2026-10-25T02:15:00+02:00", einde="2026-10-25T02:45:00+02:00"))
        fotos = [self.foto("eerste_0230", "2026-10-25T00:30:00Z"), self.foto("tweede_0230", "2026-10-25T01:30:00Z")]
        selected, onbeslist = m.selecteer(fotos, start, einde, (50.0, 4.0), 300)
        self.assertEqual([f["uuid"] for f in selected], ["eerste_0230"])
        self.assertEqual(onbeslist, 0)

    def test_meer_dan_80_fictieve_originelen_hervat_alleen_ontbrekende(self):
        m = self.module
        m.exporteer_naar = self.export_orig
        m.LIB = str(Path(self.home.name) / "fictieve-originelen")
        doel = str(Path(self.home.name) / "fictieve-uitvoer")
        fotos = [self.foto(f"{i:08x}-0000-4000-8000-000000000000") for i in range(85)]
        requests = []
        def photos_stub(command, **kw):
            requests.append(command)
            tmp = re.search(r'to POSIX file "([^"]+)"', command[-1]).group(1)
            (Path(tmp) / "fictief.jpg").write_bytes(b"uitsluitend fictieve testbytes, geen echte foto")
            return SimpleNamespace(returncode=0, stderr="")
        with patch("subprocess.run", photos_stub):
            self.assertEqual(m.exporteer_naar(fotos, doel), 80)
            self.assertEqual(sum(f["geexporteerd"] for f in fotos), 80)
            self.assertEqual(m.exporteer_naar(fotos, doel), 85)
        self.assertEqual(len(requests), 85)
        self.assertTrue(all(f["geexporteerd"] for f in fotos))

    def test_fotos_van_leest_originele_naam_en_valt_terug_bij_oud_sqlite_schema(self):
        m = self.module
        m.DB = str(Path(self.home.name) / "Photos.sqlite")
        t = datetime.fromisoformat("2026-10-14T11:30:00+02:00").timestamp() - m.APPLE_EPOCH
        con = sqlite3.connect(m.DB)
        con.execute("CREATE TABLE ZASSET (Z_PK INTEGER, ZUUID TEXT, ZFILENAME TEXT, ZDATECREATED REAL, ZLATITUDE REAL, ZLONGITUDE REAL, ZKIND INTEGER, ZTRASHEDSTATE INTEGER)")
        con.execute("CREATE TABLE ZADDITIONALASSETATTRIBUTES (ZASSET INTEGER, ZORIGINALFILENAME TEXT)")
        con.execute("INSERT INTO ZASSET VALUES (1, 'uuid', 'UUID.HEIC', ?, 50, 4, 0, 0)", (t,))
        con.execute("INSERT INTO ZADDITIONALASSETATTRIBUTES VALUES (1, 'IMG_0001.HEIC')")
        con.commit()
        self.assertEqual(m.fotos_van("2026-10-14")[0]["origineel"], "IMG_0001.HEIC")
        con.execute("DROP TABLE ZADDITIONALASSETATTRIBUTES")
        con.commit()
        con.close()
        self.assertIsNone(m.fotos_van("2026-10-14")[0]["origineel"])

    def test_tkn_tijd_aliasen_en_alleen_fotos_naar_bestaande_fotomap(self):
        data = self.inhoud_tkn()
        fotos = [self.foto("goed"), self.foto("film")]
        fotos[1]["video"] = True
        code, exports, _ = self.fake_run(fotos, inhoud=data)
        self.assertEqual(code, 0)
        self.assertEqual(exports, [["goed"]])
        self.assertEqual(self.afgevinkt, [12])
        doel = Path(self.module.taakdoel(data))
        self.assertEqual(doel.name, "2026-10-14 iPhone")
        tekst = (doel / "00 fotos.md").read_text()
        self.assertIn("verslagopdracht:12", tekst)
        self.assertIn("van de Agendawacht", tekst)

    def test_tkn_onbeslist_blokkeert_geldige_foto_niet(self):
        data = self.inhoud_tkn()
        fotos = [self.foto("goed"), self.foto("zonder_gps", lat=None), self.foto("zonder_tijd", tijd="")]
        code, exports, logs = self.fake_run(fotos, inhoud=data)
        self.assertEqual((code, exports), (0, [["goed"]]))
        self.assertEqual(self.afgevinkt, [12])
        self.assertIn("2 foto's niet toewijsbaar", (Path(self.module.taakdoel(data)) / "00 fotos.md").read_text())
        self.assertTrue(any("2 onbeslist" in r.get("tekst", "") for _, payload in logs if "regels" in payload for r in payload["regels"]))

    def test_tkn_twee_gelijke_selecties_minstens_45_minuten_uiteen(self):
        data = self.inhoud_tkn()
        fotos = [self.foto("eerste")]
        for nu in ("2026-10-14T11:00:00+00:00", "2026-10-14T11:44:59+00:00"):
            code, exports, _ = self.fake_run(fotos, inhoud=data, nu=nu)
            self.assertEqual((code, exports[-1], self.afgevinkt), (1, ["eerste"], []))
        self.assertFalse((Path(self.module.taakdoel(data)) / "00 fotos.md").exists())
        code, _, _ = self.fake_run(fotos, inhoud=data, nu="2026-10-14T11:45:00+00:00")
        self.assertEqual((code, self.afgevinkt), (0, [12]))
        staat = json.loads((Path(self.module.SELECTIE_STAAT) / "12.json").read_text())
        self.assertEqual(staat["eerste_meting"], "2026-10-14T11:00:00+00:00")
        self.assertEqual(set(staat), {"selectiehash", "eerste_meting"})

    def test_tkn_groeiende_selectie_reset_rust_en_levert_nieuwe_foto(self):
        data = self.inhoud_tkn()
        eerste = self.foto("eerste")
        tweede = self.foto("tweede")
        self.fake_run([eerste], inhoud=data, nu="2026-10-14T11:00:00+00:00")
        code, exports, _ = self.fake_run([eerste, tweede], inhoud=data, nu="2026-10-14T11:46:00+00:00")
        self.assertEqual((code, exports, self.afgevinkt), (1, [["eerste", "tweede"]], []))
        self.assertFalse((Path(self.module.taakdoel(data)) / "00 fotos.md").exists())
        code, _, _ = self.fake_run([eerste, tweede], inhoud=data, nu="2026-10-14T12:31:00+00:00")
        self.assertEqual((code, self.afgevinkt), (0, [12]))

    def test_tkn_zesuursgrens_en_groei_op_de_grens(self):
        data = self.inhoud_tkn()
        eerste = self.foto("eerste")
        tweede = self.foto("tweede")
        self.fake_run([eerste], inhoud=data, nu="2026-10-14T15:59:59+00:00")
        self.assertEqual(self.afgevinkt, [])
        code, _, _ = self.fake_run([eerste, tweede], inhoud=data, nu="2026-10-14T16:00:00+00:00")
        self.assertEqual((code, self.afgevinkt), (1, []))
        code, _, _ = self.fake_run([eerste, tweede], inhoud=data, nu="2026-10-14T16:30:00+00:00")
        self.assertEqual((code, self.afgevinkt), (0, [12]))
        nieuw = self.inhoud_tkn(bezoek_ref="verslagopdracht:13")
        code, _, _ = self.fake_run([eerste], inhoud=nieuw, nu="2026-10-14T16:00:00+00:00", taak_id=13)
        self.assertEqual((code, self.afgevinkt), (0, [12, 13]))

    def test_tkn_identiteit_en_fotomap_worden_gecontroleerd_voor_fotolezing(self):
        basis = self.inhoud_tkn()
        fouten = [
            (dict(mapnummer=None), "projectidentiteit_ontbreekt"),
            (dict(mapnummer="260010"), "projectidentiteit_ontbreekt"),
            (dict(bezoek_ref="verslagopdracht:x"), "bronregistratie_ontbreekt"),
            (dict(projectmap="/Work/TKN BURO WORK/1 Projects/2026/47035_Barsten & Scheuren_Proeflaan 23, 9998 Proefgem/../ander"), "bezoekmap_buiten_project"),
            (dict(projectmap="/Work/TKN BURO WORK/1 Projects/2026/999999_Ander"), "bezoekmap_buiten_project"),
            (dict(projectmap="/private/47035_Barsten & Scheuren_Proeflaan 23, 9998 Proefgem"), "bezoekmap_buiten_project"),
            (dict(doelmap=basis["projectmap"] + "/2. plaud/2026-10-14 iPhone"), "bezoekmap_buiten_project"),
            (dict(tot_tijd=None), "bezoekvenster_ontbreekt"),
        ]
        for changes, fout in fouten:
            with self.subTest(changes=changes):
                self.statussen.clear()
                self.afgevinkt.clear()
                code, exports, _ = self.fake_run([self.foto("goed")], inhoud={**basis, **changes})
                self.assertEqual((code, exports, self.afgevinkt, self.lezingen), (1, [], [], []))
                self.assertIn(fout, self.statussen[-1][1]["detail"])
        ontbreekt = {**basis, "projectmap": "/Work/TKN BURO WORK/1 Projects/2026/47035_Onbestaand"}
        code, exports, _ = self.fake_run([self.foto("goed")], inhoud=ontbreekt)
        self.assertEqual((code, exports), (1, []))
        self.assertIn("fotomap_ontbreekt", self.statussen[-1][1]["detail"])
        self.assertFalse(Path(self.module.DROPBOX_LOKAAL, "Work/TKN BURO WORK/1 Projects/2026/47035_Onbestaand").exists())

    def test_tkn_fotomap_symlink_buiten_project_wordt_geweigerd(self):
        data = self.inhoud_tkn()
        project = Path(self.module.DROPBOX_LOKAAL) / data["projectmap"].lstrip("/")
        (project / "1. Foto's").rmdir()
        buiten = Path(self.home.name) / "buiten-project"
        buiten.mkdir()
        (project / "1. Foto's").symlink_to(buiten, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "bezoekmap_buiten_project"):
            self.module.taakdoel(data)

    def test_tkn_onvolledig_twee_keer_geen_manifest_en_volledig_een_manifest(self):
        data = self.inhoud_tkn()
        fotos = [self.foto("eerste"), self.foto("tweede")]
        doel = Path(self.module.taakdoel(data))
        for _ in range(2):
            code, _, _ = self.fake_run(fotos, inhoud=data, geleverd=1)
            self.assertEqual(code, 1)
            self.assertFalse((doel / "00 fotos.md").exists())
        code, _, _ = self.fake_run(fotos, inhoud=data)
        self.assertEqual(code, 0)
        origineel = (doel / "00 fotos.md").read_text()
        code, _, _ = self.fake_run(fotos, inhoud=data)
        self.assertEqual(code, 0)
        self.assertEqual((doel / "00 fotos.md").read_text(), origineel)
        self.assertEqual(len(list(doel.glob("00 fotos*.md"))), 1)

    def test_tkn_schermafbeelding_telt_niet_als_bezoekfoto(self):
        data = self.inhoud_tkn()
        fotos = [dict(self.foto("scherm"), origineel="Screenshot 2026-10-14.png"),
                 dict(self.foto("goed"), origineel="IMG_0001.HEIC")]
        code, exports, _ = self.fake_run(fotos, inhoud=data)
        self.assertEqual(code, 0)
        self.assertEqual(exports, [["goed"]])

    def test_tkn_jpg_bestaand_bestand_blijft_en_heic_wordt_omgezet(self):
        m = self.module
        m.exporteer_jpg_naar = self.export_jpg_orig
        m.LIB = str(Path(self.home.name) / "originelen")
        doel = Path(self.home.name) / "doel"
        doel.mkdir()
        bestaand = doel / "IMG_0001.jpg"
        bestaand.write_bytes(b"oude, fictieve inhoud")
        mtime = bestaand.stat().st_mtime_ns
        fotos = [dict(self.foto("a"), origineel="IMG_0001.HEIC", bestand="a.HEIC"),
                 dict(self.foto("b"), origineel="IMG_0002.HEIC", bestand="b.HEIC")]
        bron = Path(m.LIB) / "b" / "b.HEIC"
        bron.parent.mkdir(parents=True)
        bron.write_bytes(b"fictieve HEIC")
        def sips_stub(command, **kw):
            self.assertEqual(command[:6], ["sips", "-s", "format", "jpeg", "-s", "formatOptions"])
            Path(command[-1]).write_bytes(b"fictieve JPEG")
            return SimpleNamespace(returncode=0, stderr="")
        with patch("subprocess.run", sips_stub):
            self.assertEqual(m.exporteer_jpg_naar(fotos, str(doel)), 2)
        self.assertEqual(bestaand.read_bytes(), b"oude, fictieve inhoud")
        self.assertEqual(bestaand.stat().st_mtime_ns, mtime)
        self.assertEqual((doel / "IMG_0002.jpg").read_bytes(), b"fictieve JPEG")
        self.assertFalse(list(doel.glob("*.HEIC")))

    def test_tkn_live_photo_negeert_grotere_mov(self):
        m = self.module
        m.exporteer_jpg_naar = self.export_jpg_orig
        m.LIB = str(Path(self.home.name) / "geen-originelen")
        doel = Path(self.home.name) / "doel"
        foto = dict(self.foto("beeld"), origineel="IMG_0003.JPG", bestand="beeld.JPG")
        def photos_stub(command, **kw):
            tmp = re.search(r'to POSIX file "([^"]+)"', command[-1]).group(1)
            (Path(tmp) / "IMG_0003.MOV").write_bytes(b"video" * 1000)
            (Path(tmp) / "IMG_0003.JPG").write_bytes(b"fictieve foto")
            return SimpleNamespace(returncode=0, stderr="")
        with patch("subprocess.run", photos_stub):
            self.assertEqual(m.exporteer_jpg_naar([foto], str(doel)), 1)
        self.assertEqual((doel / "IMG_0003.jpg").read_bytes(), b"fictieve foto")
        self.assertEqual(len(list(doel.iterdir())), 1)

    def test_tkn_twee_originelen_met_dezelfde_naam_worden_niet_stil_afgevinkt(self):
        m = self.module
        m.exporteer_jpg_naar = self.export_jpg_orig
        m.LIB = str(Path(self.home.name) / "originelen")
        for uid in ("a", "b"):
            bron = Path(m.LIB) / uid / (uid + ".JPG")
            bron.parent.mkdir(parents=True)
            bron.write_bytes(uid.encode())
        fotos = [dict(self.foto(uid), origineel="IMG_0010.JPG", bestand=uid + ".JPG") for uid in ("a", "b")]
        doel = Path(self.home.name) / "doel"
        self.assertEqual(m.exporteer_jpg_naar(fotos, str(doel)), 1)
        self.assertEqual((doel / "IMG_0010.jpg").read_bytes(), b"a")
        self.assertEqual(fotos[1]["export_fout"], "bestandsnaam_dubbel")

    def test_tkn_sips_fout_houdt_taak_open_en_schrijft_geen_manifest(self):
        m = self.module
        m.LIB = str(Path(self.home.name) / "originelen")
        bron = Path(m.LIB) / "h" / "heic.HEIC"
        bron.parent.mkdir(parents=True)
        bron.write_bytes(b"fictieve HEIC")
        data = self.inhoud_tkn()
        foto = dict(self.foto("heic"), origineel="IMG_0004.HEIC", bestand="heic.HEIC")
        with patch("subprocess.run", return_value=SimpleNamespace(returncode=1, stderr="mislukt")):
            code, exports, _ = self.fake_run([foto], inhoud=data, echt_jpg=True)
        doel = Path(self.module.taakdoel(data))
        self.assertEqual(code, 1)
        self.assertEqual(exports, [])
        self.assertEqual(self.afgevinkt, [])
        self.assertIn("omzetting_mislukt", self.statussen[-1][1]["detail"])
        self.assertFalse((doel / "00 fotos.md").exists())
        self.assertFalse((doel / "IMG_0004.jpg").exists())

    def test_hartslag_vermeldt_versie_of_onbekend(self):
        m = self.module
        m.hartslag = self.hartslag_orig
        meldingen = []
        m.bord = lambda path, data: meldingen.append(data)
        m.__file__ = str(Path(self.home.name) / "icloud_wacht.py")
        m.hartslag("klaar", detail="proef")
        self.assertIn("VERSIE onbekend", meldingen[-1]["detail"])
        Path(self.home.name, "VERSIE").write_text("abc123\n")
        m.hartslag("klaar", detail="proef")
        self.assertIn("VERSIE abc123", meldingen[-1]["detail"])


if __name__ == "__main__":
    uitslag = unittest.main(exit=False).result
    if not uitslag.wasSuccessful():
        raise SystemExit(1)
    print("alles geslaagd")
