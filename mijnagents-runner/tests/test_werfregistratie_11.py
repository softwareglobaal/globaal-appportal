"""Vaste werfapp-identiteit bij een verhuis van de projectmap; alle API-antwoorden zijn stubs."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "koppelingen"))
sys.path.insert(0, str(ROOT))
import werfregister  # noqa: E402
import werfregistratie  # noqa: E402


class RegistratieBijVerhuis(unittest.TestCase):
    def rij(self, bord_id, pad):
        return {"id": bord_id, "dossier": "9999", "datum": "2026-10-14", "bezoekmap": pad,
                "bronnen": {"nr_label": "3", "soort_bezoek": "werfbezoek"}}

    def test_verhuisde_map_hergebruikt_appbezoek_id(self):
        bezoeken, geschreven = [], []

        def api(pad, payload=None):
            if pad.startswith("/bezoeken?"):
                return {"bezoeken": list(bezoeken), "meer": False}
            geschreven.append(payload)
            bezoek = {"bezoek_id": "vast-bezoek-3", "project_ref": "h-architects:9999", "bezoektype": "werfbezoek",
                      "weergave_nummer": "3", "gepland": {"dag": "2026-10-14"}, "status": "onzeker", "revisie": 1}
            bezoeken.append(bezoek)
            return {"bezoek": bezoek}

        with patch.object(werfregister, "call", side_effect=api):
            oud = werfregister.registreer(self.rij(11, "/oud/bezoek"), "9999", 3)
            nieuw = werfregister.registreer(self.rij(99, "/nieuw/bezoek"), "9999", 3)
        self.assertEqual(oud["bezoek_id"], nieuw["bezoek_id"])
        self.assertEqual(nieuw["bordrij_id"], 99)
        self.assertEqual(len(geschreven), 1)

    def test_ambigu_appnummer_blokkeert_nieuw_bezoek(self):
        bezoek = {"bezoek_id": "een", "project_ref": "h-architects:9999", "bezoektype": "werfbezoek",
                  "weergave_nummer": "3", "gepland": {"dag": "2026-10-14"}}
        with patch.object(werfregister, "call", return_value={"bezoeken": [bezoek, dict(bezoek, bezoek_id="twee")], "meer": False}) as api:
            with self.assertRaisesRegex(werfregister.RegisterFout, "meerdere werfapp-bezoeken"):
                werfregister.registreer(self.rij(99, "/nieuw/bezoek"), "9999", 3)
        self.assertEqual(api.call_count, 1)

    def test_rapport_telt_bordverhuis_als_een_appbezoek(self):
        rijen = [dict(self.rij(11, "/oud/bezoek"), volgnr=3, stand="klaar", projectmap="/oud"),
                 dict(self.rij(99, "/nieuw/bezoek"), volgnr=3, stand="klaar", projectmap="/nieuw")]
        with patch.object(werfregister, "registreer", side_effect=lambda rij, *a: {
                "bezoek_id": "vast-bezoek-3", "project_ref": "h-architects:9999", "bordrij_id": rij["id"]}), \
             patch.object(werfregistratie.bord, "call", return_value={"ok": True}):
            rapport = werfregistratie.aansluiten(rijen, toepassen=True)
        self.assertEqual(rapport["geregistreerd"], 2)
        self.assertEqual(rapport["unieke_werfapp_bezoeken"], 1)

    def test_vooraf_koppelen_hergebruikt_id_van_oude_projectmap(self):
        bezoek = {"map": "/nieuw/project/2026-10-14 bezoek", "datum": "2026-10-14"}
        oud = {"projectmap": "/oud/project", "bezoekmap": "/oud/project/2026-10-14 bezoek",
               "datum": "2026-10-14", "registratie": {"bezoek_id": "vast-3", "project_ref": "h-architects:9999"}}
        meting = []
        with patch.object(werfregister, "call", side_effect=lambda pad, payload=None: meting.append(pad) or {"bezoeken": [], "meer": False}):
            uit = werfregistratie.koppel_voor_nummering([bezoek], "9999", "/nieuw/project", "", [oud])
        self.assertEqual(uit[0]["registratie"]["bezoek_id"], "vast-3")
        self.assertEqual(len(meting), 1)  # alleen de leesroute, geen tweede upsert
        self.assertNotIn("volgnr", uit[0])  # identiteit vóór de bordnummering

    def test_vooraf_registreert_ontbrekend_bezoek_eenmaal_met_stabiele_alias(self):
        bezoeken = [{"map": "/nieuw/project/2026-10-14 bezoek", "datum": "2026-10-14"}]
        geschreven = []

        def api(pad, payload=None):
            if payload is None:
                return {"bezoeken": [], "meer": False}
            geschreven.append(payload)
            return {"bezoek": {"bezoek_id": "vast-3", "project_ref": "h-architects:9999"}}

        with patch.object(werfregister, "call", side_effect=api):
            werfregistratie.koppel_voor_nummering(bezoeken, "9999", "/nieuw/project", "", [])
        self.assertEqual(bezoeken[0]["registratie"]["bezoek_id"], "vast-3")
        self.assertEqual(len(geschreven), 1)
        self.assertIn("moment:9999:2026-10-14", geschreven[0]["alias"]["externe_id"])


if __name__ == "__main__":
    unittest.main()
