#!/usr/bin/env python3
"""Geen foto-I/O/export/netwerk: geweigerde bron blijft als fout zichtbaar."""
import importlib.util
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
        self.statussen, self.afgevinkt = [], []
        self.module.hartslag = lambda status, **kw: self.statussen.append((status, kw))
        self.module.taak_opgepakt = lambda kid: self.afgevinkt.append(kid)
        self.module.exporteer_naar = lambda *a: self.fail("geweigerde bron mag niet worden geëxporteerd")
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

    def fake_run(self, fotos, inhoud=None, geleverd=None):
        m = self.module
        logs, exports = [], []
        m.taken_lezen = lambda: [{"id": 12, "inhoud": json.dumps(inhoud or self.inhoud())}]
        m.coord = lambda address: (50.0, 4.0)
        self.lezingen = []
        m.fotos_van = lambda day: self.lezingen.append(day) or fotos
        m.bord = lambda path, data: logs.append((path, data)) or {"ok": True}
        def export(selected, doel):
            exports.append([f["uuid"] for f in selected])
            Path(doel).mkdir(parents=True, exist_ok=True)
            return len(selected) if geleverd is None else geleverd
        m.exporteer_naar = export
        m.jpeg_kopieen = lambda doel: 0
        with patch.object(sys, "argv", ["icloud_wacht.py", "--taken"]):
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


if __name__ == "__main__":
    unittest.main()
