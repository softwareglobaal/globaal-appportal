"""BORD1: een beslisser kan de inhoud van elk open voorstel lezen voor de klik."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(__file__))
BOOT = tempfile.TemporaryDirectory()
os.environ["AGENTS_DB"] = os.path.join(BOOT.name, "boot.db")
import app as A  # noqa: E402

BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "testbeheer"}
ANDER = {"X-authentik-groups": "agents", "X-authentik-username": "testkijker"}


class VoorstelLezenTest(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.TemporaryDirectory()
        self.oud_pad = A.DB_PAD
        A.DB_PAD = os.path.join(self.map.name, "test.db")
        A.init_db()
        self.client = A.app.test_client()
        with A.app.app_context():
            conn = A.db()
            for naam in ("regisseur", "zoom-wacht"):
                conn.execute("INSERT INTO agent(naam,label,aangemaakt) VALUES(?,?,?)",
                             (naam, naam, A.nu()))
            conn.commit()

    def tearDown(self):
        A.DB_PAD = self.oud_pad
        self.map.cleanup()

    def voeg_toe(self, parameters="", runbook="", doel="Volledig doel", reden="Volledige reden"):
        with A.app.app_context():
            conn = A.db()
            conn.execute(
                "INSERT INTO voorstel(naam,actie,doel,reden,parameters,runbook,ts) VALUES(?,?,?,?,?,?,?)",
                ("regisseur", "Testvoorstel", doel, reden,
                 json.dumps(parameters, ensure_ascii=False) if isinstance(parameters, dict) else parameters,
                 runbook, A.nu()))
            conn.commit()

    def html(self, headers=BEHEER):
        antwoord = self.client.get("/", headers=headers)
        self.assertEqual(antwoord.status_code, 200)
        return antwoord.get_data(as_text=True)

    def assert_leesbaar(self, html):
        self.assertIn("<summary>Lees</summary>", html)
        self.assertIn("Volledig doel", html)
        self.assertIn("Volledige reden", html)

    def test_werkwijze_toont_volledige_tekst_en_verschil_met_bord(self):
        oud = "Titel\nZelfde regel\nOude afspraak\nNog dezelfde regel\n"
        nieuw = "Titel\nZelfde regel\nNieuwe afspraak\nNog dezelfde regel\n" + "Lange tekst " + "x" * 13000
        with A.app.app_context():
            A.db().execute("UPDATE agent SET werkwijze=? WHERE naam='zoom-wacht'", (oud,))
            A.db().commit()
        self.voeg_toe({"agent": "zoom-wacht", "mandaat": "Ik controleer de bron.", "werkwijze": nieuw},
                      runbook="werkwijze-bijwerken")
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn("zoom-wacht", html)
        self.assertIn("Ik controleer de bron.", html)
        self.assertIn(nieuw, html)
        self.assertIn("-Oude afspraak", html)
        self.assertIn("+Nieuwe afspraak", html)
        self.assertIn("@@ -", html)
        self.assertIn('<details class="voorstel-lezen">', html)

    def test_andere_parameters_tonen_naam_waarde_en_ingesprongen_json(self):
        self.voeg_toe({"project": "verzonnen-gebouw", "opties": {"drempel": 2, "actief": True}})
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn("project", html)
        self.assertIn("verzonnen-gebouw", html)
        self.assertIn("opties", html)
        self.assertIn('&#34;drempel&#34;: 2', html)
        self.assertIn('&#34;actief&#34;: true', html)

    def test_parameter_html_wordt_ge_escaped(self):
        gevaar = '<script>alert("BORD1")</script>'
        self.voeg_toe({"inhoud": gevaar})
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn('&lt;script&gt;alert(&#34;BORD1&#34;)&lt;/script&gt;', html)
        self.assertNotIn(gevaar, html)

    def test_kijker_ziet_geen_leesdeel_of_parameterinhoud(self):
        self.voeg_toe({"geheim": "Alleen voor de beslisser"})
        self.assert_leesbaar(self.html())
        html = self.html(ANDER)
        self.assertNotIn("<summary>Lees</summary>", html)
        self.assertNotIn("Alleen voor de beslisser", html)

    def test_besluitknoppen_blijven_staan(self):
        self.voeg_toe({"antwoord": "ja"})
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn('value="goedgekeurd"', html)
        self.assertIn('value="geweigerd"', html)
        self.assertIn('>Goedkeuren</button>', html)
        self.assertIn('>Weigeren</button>', html)

    def test_zonder_parameters_toont_alleen_doel_en_reden(self):
        self.voeg_toe()
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn("signaal, niet uitvoerbaar", html)
        self.assertNotIn("<dt>Parameters</dt>", html)

    def test_ontbrekende_huidige_werkwijze_wordt_gemeld(self):
        self.voeg_toe({"agent": "zoom-wacht", "werkwijze": "Nieuwe tekst\nTweede regel"},
                      runbook="werkwijze-bijwerken")
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn("Nieuwe tekst\nTweede regel", html)
        self.assertIn("Geen huidige werkwijze op het bord", html)

    def test_lange_werkwijze_en_diff_hebben_zichtbare_grens(self):
        oud = "\n".join(f"oud {n}" for n in range(500))
        nieuw = "\n".join(f"nieuw {n}" for n in range(500)) + "\n" + "x" * 60_001 + "EIND"
        with A.app.app_context():
            A.db().execute("UPDATE agent SET werkwijze=? WHERE naam='zoom-wacht'", (oud,))
            A.db().commit()
        self.voeg_toe({"agent": "zoom-wacht", "werkwijze": nieuw}, runbook="werkwijze-bijwerken")
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn("Tekst afgekapt na 60.000 tekens", html)
        self.assertIn("Verschil afgekapt na 400 regels", html)
        self.assertNotIn("EIND", html)
        with A.app.app_context():
            voorstel = A.db().execute("SELECT * FROM voorstel").fetchone()
            details = A._voorstel_leesgegevens(voorstel, A.db())
        self.assertEqual(len(details["verschil"].splitlines()), 400)

    def test_veel_korte_regels_beperken_de_vergelijking_zichtbaar(self):
        oud = "\n".join(f"regel {n}" for n in range(5_001))
        nieuw = oud + "\nNieuwe laatste regel"
        with A.app.app_context():
            A.db().execute("UPDATE agent SET werkwijze=? WHERE naam='zoom-wacht'", (oud,))
            A.db().commit()
        self.voeg_toe({"agent": "zoom-wacht", "werkwijze": nieuw}, runbook="werkwijze-bijwerken")
        html = self.html()
        self.assert_leesbaar(html)
        self.assertIn("Nieuwe laatste regel", html)
        self.assertIn("Vergelijking gebruikt alleen de eerste 5.000 regels", html)
        self.assertIn("Geen verschillen in de eerste 5.000 regels", html)


if __name__ == "__main__":
    unittest.main()
