"""Regressies voor dubbele betaalde starts, stale keuzes en onzekere uitvoering. Geen modelcalls."""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
BOOT = tempfile.TemporaryDirectory()
os.environ.setdefault("AGENTS_DB", os.path.join(BOOT.name, "boot.db"))
import app as A

TOKEN = {"X-Agents-Token": "test-werf"}
BEHEER = {"X-authentik-groups": "admin", "X-authentik-username": "test"}


class WerfVerwerkingTest(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.TemporaryDirectory()
        self.oud_pad, self.oud_token = A.DB_PAD, A.TOKEN
        A.DB_PAD, A.TOKEN = os.path.join(self.map.name, "test.db"), "test-werf"
        A.init_db()
        with A.app.app_context():
            A._werfbezoek_tabel(A.db())
        self.client = A.app.test_client()
        self.seed()

    def tearDown(self):
        A.DB_PAD, A.TOKEN = self.oud_pad, self.oud_token
        self.map.cleanup()

    def seed(self, pad="/werf/bezoek-1", stand="te verzamelen"):
        resp = self.client.post("/api/werfbezoek", headers=TOKEN, json={"rijen": [{
            "dossier": "2309", "datum": "2026-10-14", "volgnr": 1, "bezoekmap": pad,
            "projectmap": "/werf", "bronnen": {"transcripten": ["bron-a.txt"]}, "stand": stand}]})
        self.assertEqual(resp.status_code, 200)
        with A.app.app_context():
            return A.db().execute("SELECT id FROM werfbezoek WHERE bezoekmap=?", (pad,)).fetchone()[0]

    def rij(self, rid=None):
        with A.app.app_context():
            return dict(A.db().execute("SELECT * FROM werfbezoek WHERE id=?", (rid or 1,)).fetchone())

    def form(self, soort="voorbereid", rid=1):
        return {"soort": soort, "rij_id": rid, "revisie": A.werfwerk.revisie(self.rij(rid))}

    def maak(self, soort="voorbereid"):
        self.assertEqual(self.client.post("/werfverslag/2309/1/opdracht", headers=BEHEER, data=self.form(soort)).status_code, 302)
        return self.client.get("/api/werfopdrachten?status=klaar", headers=TOKEN).get_json()["opdrachten"][0]

    def claim(self, kid):
        return self.client.post(f"/api/werfopdrachten/{kid}/claim", headers=TOKEN, json={"door": "test"})

    def finish(self, claim, status, **extra):
        return self.client.post(f"/api/werfopdrachten/{claim['opdracht']['id']}/resultaat", headers=TOKEN,
                                json={"lease_token": claim["lease_token"], "status": status, **extra})

    def bewaar(self, claimed):
        op = claimed["opdracht"]
        data = {"dossier": "2309", "datum": "2026-10-14", "bezoekmap": "/werf/bezoek-1", "werfbezoek_id": 1,
                "_opdracht_id": op["id"], "_lease_token": claimed["lease_token"], "_invoer_hash": op["invoer_hash"],
                "_alleen": ["gegevens"], "gegevens": {"gegevens": [{"veld": "dak", "waarde": "waarneming"}]}}
        return self.client.post("/api/werfbezoek", headers=TOKEN, json={"rijen": [data]})

    def test_tien_concurrente_knoppen_een_opdracht(self):
        form = self.form()
        gate = threading.Barrier(10)
        def klik(_):
            with A.app.test_client() as c:
                gate.wait()
                return c.post("/werfverslag/2309/1/opdracht", headers=BEHEER, data=form).status_code
        with ThreadPoolExecutor(max_workers=10) as pool:
            self.assertEqual(list(pool.map(klik, range(10))), [302] * 10)
        with A.app.app_context():
            self.assertEqual(A.db().execute("SELECT COUNT(*) FROM werfopdracht").fetchone()[0], 1)
            self.assertEqual(A.db().execute("SELECT COUNT(*) FROM klaarzet").fetchone()[0], 1)

    def test_twee_concurrente_claims_een_start(self):
        op = self.maak()
        gate = threading.Barrier(2)
        def claim(_):
            with A.app.test_client() as c:
                gate.wait()
                return c.post(f"/api/werfopdrachten/{op['id']}/claim", headers=TOKEN, json={"door": "test"}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(claim, range(2))), [200, 409])

    def test_verlopen_claim_wordt_onbekend_nooit_auto_retry(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        with A.app.app_context():
            A.db().execute("UPDATE werfopdracht SET lease_tot='2000-01-01' WHERE klaarzet_id=?", (op["id"],))
            A.db().commit()
        self.assertEqual(self.claim(op["id"]).status_code, 409)
        current = self.client.get("/api/werfopdrachten", headers=TOKEN).get_json()["opdrachten"][0]
        self.assertEqual(current["status"], "onbekend")
        self.assertEqual(self.bewaar(claimed).status_code, 200)
        self.assertEqual(self.finish(claimed, "gelukt").status_code, 200)  # late, bewezen resultaat is wel te registreren

    def test_fout_niet_groen_en_alleen_handmatig_veilig_opnieuw(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.assertEqual(self.finish(claimed, "fout", bewijs="Validatie vóór modelcall", veilig_opnieuw=True).status_code, 200)
        page = self.client.get("/werfverslag/2309/1", headers=BEHEER).get_data(as_text=True)
        self.assertIn("Validatie vóór modelcall", page)
        self.assertIn("Veilige herhaling starten", page)
        self.assertEqual(self.claim(op["id"]).status_code, 409)
        url = f"/werfverslag/2309/1/opdracht/{op['id']}/opnieuw"
        self.assertEqual(self.client.post(url, headers=BEHEER, data={"rij_id": 1}).status_code, 302)
        self.assertEqual(self.client.post(url, headers=BEHEER, data={"rij_id": 1}).status_code, 302)
        self.assertEqual(self.claim(op["id"]).status_code, 200)
        with A.app.app_context():
            self.assertEqual(A.db().execute("SELECT poging FROM werfopdracht").fetchone()[0], 2)

    def test_verouderd_formulier_overschrijft_geen_keuzes(self):
        oud = self.form()
        first = self.client.post("/werfverslag/2309/1/keuzes", headers=BEHEER, data={**oud, "opmerking": "eerste beslissing"})
        self.assertEqual(first.status_code, 302)
        second = self.client.post("/werfverslag/2309/1/keuzes", headers=BEHEER, data={**oud, "opmerking": "oude browser"})
        self.assertEqual(second.status_code, 409)
        self.assertEqual(json.loads(self.rij()["keuzes"])["opmerking"], "eerste beslissing")

    def test_keuzes_en_resultaat_alleen_exacte_rij(self):
        tweede = self.seed("/werf/bezoek-ander")
        self.assertEqual(self.client.get("/api/werf-context?dossier=2309&volgnr=1", headers=TOKEN).status_code, 409)
        self.assertEqual(self.client.post("/werfverslag/2309/1/keuzes", headers=BEHEER,
                                         data={**self.form(rid=tweede), "opmerking": "gekozen rij"}).status_code, 302)
        self.assertEqual(json.loads(self.rij()["keuzes"] or "{}"), {})
        self.assertEqual(json.loads(self.rij(tweede)["keuzes"])["opmerking"], "gekozen rij")

    def test_gewijzigde_keuzes_weigeren_resultaat_en_betaalde_successtatus(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.client.post("/werfverslag/2309/1/keuzes", headers=BEHEER, data={**self.form(), "bronnen": "eigen"})
        guarded = {"dossier": "2309", "datum": "2026-10-14", "bezoekmap": "/werf/bezoek-1", "werfbezoek_id": 1,
                   "_opdracht_id": op["id"], "_lease_token": claimed["lease_token"], "_invoer_hash": op["invoer_hash"],
                   "_alleen": ["gegevens"], "gegevens": {"gegevens": [{"veld": "oude bron"}]}}
        self.assertEqual(self.client.post("/api/werfbezoek", headers=TOKEN, json={"rijen": [guarded]}).status_code, 409)
        self.assertEqual(self.finish(claimed, "gelukt").status_code, 409)
        self.assertEqual(self.finish(claimed, "onbekend", bewijs="invoer gewijzigd").status_code, 200)

    def test_context_is_select_en_behoudt_migratie_en_auth(self):
        with A.app.app_context():
            A.db().execute("UPDATE werfbezoek SET registratie=? WHERE id=1", (json.dumps({"bezoek_id": "bezoek-abc"}),))
            A.db().commit()
        self.assertEqual(self.client.get("/api/werf-context?dossier=2309&volgnr=1").status_code, 403)
        data = self.client.get("/api/werf-context?dossier=2309&volgnr=1", headers=TOKEN).get_json()
        self.assertEqual(data["project_ref"], "h-architects:2309")
        self.assertEqual(data["bezoek_id"], "bezoek-abc")
        self.assertEqual(data["rij"]["id"], 1)
        from unittest.mock import patch
        with sqlite3.connect(A.DB_PAD) as read_only:
            read_only.row_factory = sqlite3.Row
            read_only.execute("PRAGMA query_only=ON")
            with patch.object(A, "db", return_value=read_only):
                self.assertEqual(self.client.get("/api/werf-context?dossier=2309&volgnr=1", headers=TOKEN).status_code, 200)
        with A.app.app_context():
            self.assertEqual(A.db().execute("SELECT COUNT(*) FROM werf_schema_migratie").fetchone()[0], 1)
            self.assertEqual(A.db().execute("SELECT COUNT(*) FROM werfopdracht").fetchone()[0], 0)

    def test_fotoproducent_bewaart_verificatievelden_op_exacte_rij(self):
        tweede = self.seed("/werf/bezoek-ander")
        oud = self.rij(tweede)
        body = {"dossier": "2309", "datum": "2026-10-14", "bezoekmap": "/werf/bezoek-1", "werfbezoek_id": 1,
                "_alleen": ["registratie", "taken", "controles", "stand"],
                "registratie": {"bezoek_id": "fictief-bezoek"}, "taken": [{"voor": "icloud-wacht", "uniek": "foto:bezoek"}],
                "controles": [{"code": "W4", "stand": "onbekend"}], "stand": "fotoaanvoer nog open"}
        self.assertEqual(self.client.post("/api/werfbezoek", headers=TOKEN, json={"rijen": [body]}).status_code, 200)
        rij = self.rij()
        self.assertEqual(json.loads(rij["taken"]), body["taken"])
        self.assertEqual(json.loads(rij["controles"]), body["controles"])
        self.assertEqual(rij["stand"], body["stand"])
        for k in ("taken", "controles", "stand", "gegevens", "keuzes", "proef_pad"):
            self.assertEqual(self.rij(tweede)[k], oud[k])
        body["controles"] = "ongeldige lijst"
        self.assertEqual(self.client.post("/api/werfbezoek", headers=TOKEN, json={"rijen": [body]}).status_code, 400)

    def test_andere_fase_mag_niet_parallel_zelfde_bezoek(self):
        first = self.maak()
        self.assertEqual(self.claim(first["id"]).status_code, 200)
        second = self.maak("proef")
        self.assertEqual(self.claim(second["id"]).status_code, 409)

    def test_voorbereiding_opslaan_verandert_eigen_signature_niet(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        data = {"dossier": "2309", "datum": "2026-10-14", "bezoekmap": "/werf/bezoek-1", "werfbezoek_id": 1,
                "_opdracht_id": op["id"], "_lease_token": claimed["lease_token"], "_invoer_hash": op["invoer_hash"],
                "_alleen": ["gegevens"], "gegevens": {"gegevens": [{"veld": "dak", "waarde": "waarneming"}],
                "_verwerking": {"hergebruikt": True, "tokens_in": 0, "tokens_uit": 0, "kosten_usd": .5}}}
        self.assertEqual(self.client.post("/api/werfbezoek", headers=TOKEN, json={"rijen": [data]}).status_code, 200)
        self.assertEqual(self.finish(claimed, "gelukt").status_code, 200)
        self.assertEqual(self.client.post("/werfverslag/2309/1/opdracht", headers=BEHEER, data=self.form()).status_code, 302)
        with A.app.app_context():
            self.assertEqual(A.db().execute("SELECT COUNT(*) FROM werfopdracht").fetchone()[0], 1)
        page = self.client.get("/werfverslag/2309/1", headers=BEHEER).get_data(as_text=True)
        self.assertIn("0.0000", page)
        self.assertIn("analyse hergebruikt", page)

    def test_geen_herhaling_van_onbekende_call_en_verkeerd_claimtoken(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.assertEqual(self.finish(claimed, "onbekend").status_code, 200)
        self.assertEqual(self.client.post(f"/werfverslag/2309/1/opdracht/{op['id']}/opnieuw", headers=BEHEER, data={"rij_id": 1}).status_code, 409)
        wrong = dict(claimed, lease_token="andere-uitvoering")
        self.assertEqual(self.finish(wrong, "gelukt").status_code, 403)

    def test_invoer_gewijzigd_voor_claim_wordt_verouderd(self):
        op = self.maak()
        self.client.post("/werfverslag/2309/1/keuzes", headers=BEHEER, data={**self.form(), "opmerking": "nieuwe keuze"})
        self.assertEqual(self.claim(op["id"]).status_code, 409)
        self.assertEqual(self.client.get("/api/werfopdrachten", headers=TOKEN).get_json()["opdrachten"][0]["status"], "verouderd")

    def test_gelukt_zonder_bewaard_resultaat_kan_niet(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.assertEqual(self.finish(claimed, "gelukt", bewijs="tekst is geen resultaat").status_code, 409)
        self.assertEqual(self.bewaar(claimed).status_code, 200)
        self.assertEqual(self.finish(claimed, "gelukt").status_code, 200)

    def test_commandline_zelfde_grendel_geen_bordimpersonatie(self):
        payload = {"dossier": "2309", "volgnr": 1, "soort": "voorbereid", "bron": "commandline"}
        self.assertEqual(self.client.post("/api/werfopdrachten/aanvragen", json=payload).status_code, 403)
        self.assertEqual(self.client.post("/api/werfopdrachten/aanvragen", headers=TOKEN, json=payload).status_code, 400)
        payload["reden"] = "Mehdi vroeg de voorbereiding via de commandline"
        first = self.client.post("/api/werfopdrachten/aanvragen", headers=TOKEN, json=payload).get_json()
        second = self.client.post("/api/werfopdrachten/aanvragen", headers=TOKEN, json=payload).get_json()
        self.assertTrue(first["nieuw"])
        self.assertFalse(second["nieuw"])
        self.assertEqual(first["opdracht"]["id"], second["opdracht"]["id"])
        self.assertEqual(first["opdracht"]["bron"], {"soort": "commandline", "reden": payload["reden"]})
        with A.app.app_context():
            self.assertEqual(A.db().execute("SELECT van FROM klaarzet").fetchone()[0], "commandline:werfverslag-schrijver")

    def test_commandline_mengt_geen_nieuwe_reden_in_een_bestaande_opdracht(self):
        payload = {"dossier": "2309", "volgnr": 1, "soort": "voorbereid", "bron": "commandline", "reden": "Eerste reden van Mehdi"}
        eerste = self.client.post("/api/werfopdrachten/aanvragen", headers=TOKEN, json=payload)
        self.assertEqual(eerste.status_code, 200)
        payload["reden"] = "Andere reden van Mehdi"
        tweede = self.client.post("/api/werfopdrachten/aanvragen", headers=TOKEN, json=payload)
        self.assertEqual(tweede.status_code, 409)
        op = self.client.get("/api/werfopdrachten", headers=TOKEN).get_json()["opdrachten"][0]
        self.assertEqual(op["bron"], {"soort": "commandline", "reden": "Eerste reden van Mehdi"})

    def test_werkwijze_zaad_zet_ook_mandaat_op_agentkaart(self):
        with A.app.app_context():
            A.db().execute("INSERT INTO agent(naam,label,aangemaakt) VALUES(?,?,?)",
                           ("werfverslag-dashboard", "Werfverslag dashboard", A.nu()))
            A.db().commit()
        inhoud = {"werkwijze": "## Mandaat\n\nIk toon de bewezen stand.",
                  "mandaat": "Ik toon de bewezen stand.", "overschrijf": True}
        self.assertEqual(self.client.post("/api/agent/werfverslag-dashboard/werkwijze", headers=TOKEN, json=inhoud).status_code, 200)
        antwoord = self.client.get("/api/agent/werfverslag-dashboard/werkwijze", headers=TOKEN).get_json()
        self.assertEqual(antwoord["mandaat"], inhoud["mandaat"])

    def test_budgetuitstel_vereist_tijdzone_en_veilige_claim(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.assertEqual(self.finish(claimed, "uitgesteld", veilig_opnieuw=True, hervat_utc="morgen").status_code, 400)
        self.assertEqual(self.finish(claimed, "uitgesteld", veilig_opnieuw=True, hervat_utc="2030-01-01T12:00:00").status_code, 400)
        self.assertEqual(self.finish(claimed, "uitgesteld", hervat_utc="2030-01-01T12:00:00Z").status_code, 409)
        resp = self.finish(claimed, "uitgesteld", veilig_opnieuw=True, hervat_utc="2030-01-01T12:00:00Z", bewijs="wacht op tokenbudget")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["opdracht"]["lease_tot"], "")
        self.assertEqual(self.claim(op["id"]).status_code, 409)
        self.assertEqual(self.client.get("/api/werfopdrachten?status=klaar", headers=TOKEN).get_json()["opdrachten"], [])
        self.assertIn("01-01-2030 13:00", self.client.get("/werfverslag/2309/1", headers=BEHEER).get_data(as_text=True))

    def test_budgetdatum_hervat_dezelfde_job_met_nieuwe_claim(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.assertEqual(self.finish(claimed, "uitgesteld", veilig_opnieuw=True, hervat_utc="2000-01-01T12:00:00Z").status_code, 200)
        klaar = self.client.get("/api/werfopdrachten?status=klaar", headers=TOKEN).get_json()["opdrachten"]
        self.assertEqual([r["id"] for r in klaar], [op["id"]])
        resumed = self.claim(op["id"])
        self.assertEqual(resumed.status_code, 200)
        self.assertNotEqual(resumed.get_json()["lease_token"], claimed["lease_token"])
        with A.app.app_context():
            self.assertEqual(A.db().execute("SELECT COUNT(*) FROM klaarzet").fetchone()[0], 1)

    def test_budgethervatting_stale_keuzes_en_onbekend_niet_uitvoeren(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.assertEqual(self.finish(claimed, "uitgesteld", veilig_opnieuw=True, hervat_utc="2000-01-01T12:00:00Z").status_code, 200)
        self.client.post("/werfverslag/2309/1/keuzes", headers=BEHEER, data={**self.form(), "opmerking": "na budgetwacht gewijzigd"})
        self.assertEqual(self.claim(op["id"]).status_code, 409)
        self.assertEqual(self.client.get("/api/werfopdrachten", headers=TOKEN).get_json()["opdrachten"][0]["status"], "verouderd")
        nieuw = self.maak()
        claim2 = self.claim(nieuw["id"]).get_json()
        self.assertEqual(self.finish(claim2, "onbekend").status_code, 200)
        self.assertEqual(self.finish(claim2, "uitgesteld", veilig_opnieuw=True, hervat_utc="2000-01-01T12:00:00Z").status_code, 409)
        self.assertEqual(self.client.get("/api/werfopdrachten?status=klaar", headers=TOKEN).get_json()["opdrachten"], [])

    def test_bronwacht_label_is_generiek_en_toont_reden(self):
        op = self.maak()
        claimed = self.claim(op["id"]).get_json()
        self.assertEqual(self.finish(claimed, "uitgesteld", veilig_opnieuw=True, hervat_utc="2030-01-01T12:00:00Z",
                                     bewijs="WachtBron: dezelfde bron wordt al verwerkt").status_code, 200)
        page = self.client.get("/werfverslag/2309/1", headers=BEHEER).get_data(as_text=True)
        self.assertIn("Uitgesteld tot", page)
        self.assertIn("WachtBron: dezelfde bron wordt al verwerkt", page)
        self.assertNotIn("wacht op budget", page.lower())

    def test_drie_schema_relations_en_bestaande_data_zijn_geldig(self):
        self.maak()
        with A.app.app_context():
            werk = {(r[2], r[3], r[4]) for r in A.db().execute("PRAGMA foreign_key_list(werfopdracht)")}
            events = {(r[2], r[3], r[4]) for r in A.db().execute("PRAGMA foreign_key_list(werfopdracht_gebeurtenis)")}
            self.assertEqual(werk, {("werfbezoek", "werfbezoek_id", "id"), ("klaarzet", "klaarzet_id", "id")})
            self.assertEqual(events, {("werfopdracht", "klaarzet_id", "klaarzet_id")})
            self.assertEqual(A.db().execute("PRAGMA foreign_key_check").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
