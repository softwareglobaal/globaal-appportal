"""Render echte bezoekpagina's en laat V8 hun inline scripts parsen vóór uitrol."""
import re
import shutil
import subprocess
import unittest

import test_werfverwerking as fixture_module


class WerfFrontendTest(unittest.TestCase):
    def test_gerenderde_scripts_alle_opdrachtstanden(self):
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node/V8 is vereist voor de frontend-uitrolcontrole")
        fixture = fixture_module.WerfVerwerkingTest("test_gelukt_zonder_bewaard_resultaat_kan_niet")
        A, BEHEER = fixture_module.A, fixture_module.BEHEER
        fixture.setUp()
        try:
            op = fixture.maak()
            for status in ("klaar", "actief", "onbekend", "fout", "uitgesteld", "gelukt"):
                with self.subTest(status=status), A.app.app_context():
                    A.db().execute("UPDATE werfopdracht SET status=?,hervat_utc='2026-10-15T10:00:00Z',lease_tot='2099-01-01T00:00:00Z' WHERE klaarzet_id=?",
                                   (status, op["id"]))
                    A.db().commit()
                for url in ("/werfverslag/2309/1?rij_id=1", "/werfverslagen"):
                    response = fixture.client.get(url, headers=BEHEER)
                    self.assertEqual(response.status_code, 200)
                    html = response.get_data(as_text=True)
                    scripts = re.findall(r"<script[^>]*>(.*?)</script>", html, re.S | re.I)
                    if "rij_id" in url:
                        self.assertTrue(scripts)
                    for script in scripts:
                        parsed = subprocess.run([node, "--check"], input=script, text=True, capture_output=True)
                        self.assertEqual(parsed.returncode, 0, parsed.stderr)
                    if status in ("klaar", "actief", "uitgesteld") and "rij_id" in url:
                        self.assertIn("keuzesGewijzigd", html)
        finally:
            fixture.tearDown()

    def test_conceptlink_naar_de_werfapp_en_een_vreemde_url_niet(self):
        """De schrijver zet de werfapp-verwijzing in proef_info; het bord toont alleen een link naar werf.globaal.be."""
        import json
        fixture = fixture_module.WerfVerwerkingTest("test_gelukt_zonder_bewaard_resultaat_kan_niet")
        A, BEHEER = fixture_module.A, fixture_module.BEHEER
        fixture.setUp()
        try:
            for url, zichtbaar in (("https://werf.globaal.be/verslag/7/bewerken", True), ("https://elders.example/verslag/7", False)):
                with self.subTest(url=url), A.app.app_context():
                    info = {"punten": 3, "fotos": 1, "werfapp": {"id": 7, "nummer": "2309-1", "url": url, "nieuw": True}}
                    A.db().execute("UPDATE werfbezoek SET proef_pad='/proef/2309-1 werfverslag (concept).docx', proef_ts='2026-10-16', proef_info=? WHERE id=1",
                                   (json.dumps(info),))
                    A.db().commit()
                for pagina in ("/werfverslag/2309/1?rij_id=1", "/werfverslagen"):
                    html = fixture.client.get(pagina, headers=BEHEER).get_data(as_text=True)
                    self.assertEqual(url in html, zichtbaar, pagina)
                html = fixture.client.get("/werfverslag/2309/1?rij_id=1", headers=BEHEER).get_data(as_text=True)
                self.assertIn("Maak concept", html)
                if zichtbaar:
                    self.assertIn("Verslag 2309-1 openen", html)
                    self.assertIn("concept in de werfapp", fixture.client.get("/werfverslagen", headers=BEHEER).get_data(as_text=True))
        finally:
            fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
