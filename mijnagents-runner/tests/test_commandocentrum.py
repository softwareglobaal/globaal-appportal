"""Commandocentrum: TKN-taakinhoud en herziening zonder bord- of Dropbox-netwerk."""
import importlib.util
import json
import os
from datetime import datetime
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit


RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER / "plaud"))
import zoektaak as ZOEK  # noqa: E402
SPEC = importlib.util.spec_from_file_location("commandocentrum_uit_test", RUNNER / "commandocentrum.py")
CC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CC)
SOORT = CC.vs.SOORTEN["barsten-scheuren"]
MAP = "/Work/TKN BURO WORK/1 Projects/2026/47035_Barsten & Scheuren_Proeflaan 23, 9998 Proefgem"


def rij(**vervang):
    r = {"uniek": "afspraak:bs1", "dossier": "3999", "firma": "UNAB", "klant": "Proefklant", "adres": "Proeflaan 23, 9998 Proefgem",
         "datum": "2026-10-21", "start": "2026-10-21T08:00:00+02:00", "einde": "2026-10-21T10:00:00+02:00",
         "titel": "BS bezoek", "agenda": "werk", "deal_id": ""}
    r.update(vervang)
    return r


def oud(**vervang):
    o = {**rij(), "id": 77, "open": 1, "dossiermap": MAP, "bezoekmap": MAP, "pakket": {},
         "taken": [], "stand": "voorbereid", "impuls_voorbereiding_ts": "2026-10-20T12:00:00+02:00",
         "impuls_verslag_ts": "", "proef_pad": ""}
    o.update(vervang)
    return o


class Taakinhoud(unittest.TestCase):
    def test_fotovenster_submappen_en_projectidentiteit(self):
        pakket = {"submappen": {"fotos": "1. Foto’s", "plaud": "2. Plaud opnames"}}
        foto, plaud = CC.taakinhoud(rij(dossier=""), oud(pakket=pakket), SOORT, "barsten-scheuren")
        self.assertEqual((foto["start"], foto["einde"]),
                         ("2026-10-21T07:30:00+02:00", "2026-10-21T13:00:00+02:00"))
        self.assertEqual((foto["van_tijd"], foto["tot_tijd"]),
                         ("2026-10-21T08:00:00+02:00", "2026-10-21T10:00:00+02:00"))
        self.assertEqual(foto["dossier"], "47035")
        self.assertEqual(plaud["firma"], "UNAB")
        self.assertEqual(foto["mapnummer"], "47035")
        self.assertEqual(foto["projectmap"], MAP)
        self.assertEqual(foto["bezoekmap"], MAP)
        self.assertEqual(foto["doelmap"], MAP + "/1. Foto’s/2026-10-21 iPhone")
        self.assertEqual(plaud["plaud_doelmap"], MAP + "/2. Plaud opnames")
        self.assertEqual(plaud["transcriptnaam"], "2026-10-21 Plaud transcript.txt")
        self.assertEqual(foto["project_ref"], "tkn:47035")
        self.assertEqual(foto["bezoek_ref"], "verslagopdracht:77")
        self.assertEqual(foto["straal_m"], 300)
        self.assertEqual(foto["fotoformaat"], "jpg")
        self.assertEqual(foto["reden"], "barsten en scheuren: agendavenster -30/+180 min, vaste straal 300 m")
        foto_met_agendanummer, _ = CC.taakinhoud(rij(), oud(), SOORT, "barsten-scheuren")
        self.assertEqual((foto_met_agendanummer["dossier"], foto_met_agendanummer["mapnummer"]), ("3999", "47035"))

    def test_agendanummer_dat_postcode_is_wordt_geen_dossierbewijs(self):
        foto, plaud = CC.taakinhoud(rij(dossier="9998"), oud(), SOORT, "barsten-scheuren")
        self.assertEqual((foto["dossier"], plaud["dossier"], plaud["mapnummer"]),
                         ("47035", "47035", "47035"))
        self.assertFalse(CC.taak_bron_gewijzigd({"inhoud": plaud}, plaud))
        self.assertTrue(CC.taak_bron_gewijzigd({"inhoud": {**plaud, "dossier": "9998"}}, plaud))

    def test_laat_bezoek_begrenst_fotovenster_op_bezoekdag(self):
        r = rij(start="2026-10-21T20:30:00+02:00", einde="2026-10-21T22:30:00+02:00")
        foto, _ = CC.taakinhoud(r, oud(), SOORT, "barsten-scheuren")
        self.assertEqual(foto["start"], "2026-10-21T20:00:00+02:00")
        self.assertEqual(foto["einde"], "2026-10-21T23:59:59+02:00")

    def test_onbruikbare_bron_geeft_geen_taak(self):
        for r, o in ((rij(), oud(dossiermap="/verkeerde/map")), (rij(), oud(dossiermap=MAP.replace("47035", "GeenNummer"))),
                     (rij(), oud(id=None)), (rij(start="geen tijd"), oud()), (rij(einde="2026-10-21"), oud())):
            with self.subTest(r=r, o=o):
                self.assertIsNone(CC.taakinhoud(r, o, SOORT, "barsten-scheuren"))

    def test_andere_soort_behoudt_exact_de_oude_dict_en_volgorde(self):
        r = rij()
        o = oud(bezoekmap="/een/bezoekmap")
        verwacht = {"dossier": "3999", "datum": "2026-10-21", "adres": "Proeflaan 23, 9998 Proefgem",
                    "bezoekmap": "/een/bezoekmap", "van_tijd": "2026-10-21T08:00:00+02:00",
                    "tot_tijd": "2026-10-21T10:00:00+02:00", "verslagsoort": "plaatsbeschrijving"}
        foto, plaud = CC.taakinhoud(r, o, CC.vs.SOORTEN["plaatsbeschrijving"], "plaatsbeschrijving")
        self.assertEqual(json.dumps(foto, ensure_ascii=False), json.dumps(verwacht, ensure_ascii=False))
        self.assertEqual(json.dumps(plaud, ensure_ascii=False), json.dumps(verwacht, ensure_ascii=False))

    def test_gesloten_taak_wacht_op_nieuwe_bronmeting(self):
        taak = {"voor": "icloud-wacht", "uniek": "cc:afspraak:bs1:icloud-wacht", "inhoud": {}}
        oud = {"uniek": taak["uniek"]}
        bord_item = {"status": "opgepakt", "opgepakt_door": "icloud-wacht",
                     "opgepakt_ts": "2026-10-21T13:16:00+02:00", "inhoud": {}}
        self.assertIsNone(CC.taak_voor_nieuwe_ronde(taak.copy(), oud, bord_item, False, "2026-10-21T13:17:00+02:00"))
        self.assertIsNone(CC.taak_voor_nieuwe_ronde(taak.copy(), oud, bord_item, False, ""))
        self.assertIsNone(CC.taak_voor_nieuwe_ronde(taak.copy(), oud, bord_item, True, "2026-10-21T14:00:00+02:00"))
        nieuw = CC.taak_voor_nieuwe_ronde(taak.copy(), oud, bord_item, False, "2026-10-21T13:46:00+02:00")
        self.assertEqual(nieuw["uniek"], taak["uniek"] + ":2")

    def test_gewijzigd_venster_firma_of_doelmap_wacht_niet_op_bronpoort(self):
        basis = "cc:afspraak:bs1:icloud-wacht"
        oud_inhoud = {"van_tijd": "2026-10-21T08:00:00+02:00", "firma": "UNAB", "doelmap": MAP + "/oud"}
        bord_item = {"status": "opgepakt", "opgepakt_door": "icloud-wacht",
                     "opgepakt_ts": "2026-10-21T13:16:00+02:00", "inhoud": oud_inhoud}
        for wijziging in ({"van_tijd": "2026-10-21T08:30:00+02:00"}, {"firma": "TKNB"},
                          {"firma": ""}, {"doelmap": MAP + "/nieuw"}):
            with self.subTest(wijziging=wijziging):
                taak = {"voor": "icloud-wacht", "uniek": basis, "inhoud": {**oud_inhoud, **wijziging}}
                nieuw = CC.taak_voor_nieuwe_ronde(taak, {"uniek": basis}, bord_item, False, "")
                self.assertEqual(nieuw["uniek"], basis + ":2")


class NepAgent:
    def __init__(self):
        self.gestuurd = []
        self.logs = []
        self.hartslagen = []

    def hartslag(self, *a, **kw):
        self.hartslagen.append((a, kw))

    def log(self, *a, **kw):
        self.logs.append((a, kw))

    def log_verstuur(self):
        pass

    def klaarzet(self, items):
        self.gestuurd.append(items)
        return {"nieuw": len(items), "bestaand": 0}


class Hoofdronde(unittest.TestCase):
    def setUp(self):
        self.r = rij()
        self.o = oud(pakket={"fotos": 1, "fotos_drone": 1, "fotos_iphone": 0, "transcripten": 0})
        self.agent = NepAgent()
        self.open_taken = {}
        self.afgevinkt = []
        self.bewaard = []
        self.api = []

        def bewaar(uniek, **velden):
            self.bewaard.append(velden)
            self.o.update(velden)

        def call(pad, payload=None):
            self.api.append((pad, payload))
            if pad.startswith("/api/klaarzet?"):
                uniek = parse_qs(urlsplit(pad).query).get("uniek", [""])[0]
                status = parse_qs(urlsplit(pad).query).get("status", ["klaar"])[0]
                item = self.open_taken.get(uniek)
                return {"items": [item] if item and (status == "alle" or item["status"] == status) else []}
            return {"ok": True}

        def opgepakt(kid, door):
            self.afgevinkt.append((kid, door))
            for item in self.open_taken.values():
                if item["id"] == kid:
                    item["status"] = "opgepakt"
                    item["opgepakt_door"] = door

        self.patches = [patch.object(CC, "ag", self.agent),
                        patch.object(CC, "afspraken", lambda sinds, tot: [({"uniek": self.r["uniek"], "verwijzing": "agenda"},
                                                                       {**self.r, "locatie": self.r["adres"], "nummer": self.r["dossier"], "type": "BS"})]),
                        patch.object(CC, "bord_rijen", lambda: {self.r["uniek"]: self.o}),
                        patch.object(CC, "bewaar", bewaar), patch.object(CC.bord, "call", call),
                        patch.object(CC.bord, "opgepakt", opgepakt), patch.object(sys, "argv", ["commandocentrum.py"])]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def ronde(self, tijd):
        class Klok(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime.fromisoformat(tijd).astimezone(tz)
        begin = len(self.agent.gestuurd)
        with patch.object(CC, "datetime", Klok):
            CC.main()
        items = [item for groep in self.agent.gestuurd[begin:] for item in groep]
        for t in items:
            if t["soort"] == "taak":
                oud = self.open_taken.setdefault(t["uniek"], {"id": 100 + len(self.open_taken), "uniek": t["uniek"],
                                                              "status": "klaar", "van": CC.NAAM, "opgepakt_door": ""})
                if oud["status"] == "klaar":
                    oud["inhoud"] = t["inhoud"]
        return items

    def test_plus_61_en_plus_196_en_drone_telt_niet(self):
        self.assertEqual(self.ronde("2026-10-21T10:59:00+02:00"), [])
        eerst = self.ronde("2026-10-21T11:01:00+02:00")
        self.assertEqual([t["voor"] for t in eerst], ["plaud-wacht"])
        self.assertEqual(self.o["taken"][0]["uniek"], "cc:afspraak:bs1:plaud-wacht")
        nog_niet = self.ronde("2026-10-21T13:14:00+02:00")
        self.assertEqual([t["voor"] for t in nog_niet], ["plaud-wacht"])
        later = self.ronde("2026-10-21T13:16:00+02:00")
        self.assertEqual([t["voor"] for t in later], ["icloud-wacht", "plaud-wacht"])
        self.assertEqual(later[1]["uniek"], eerst[0]["uniek"])
        self.assertEqual(later[0]["inhoud"]["doelmap"], MAP + "/1. Foto's/2026-10-21 iPhone")
        self.assertEqual(self.afgevinkt, [])

    def test_actuele_agenda_en_gedeeltelijke_fotos_houden_taak_open(self):
        self.ronde("2026-10-21T13:16:00+02:00")
        self.r["adres"] = "Nieuwe Proefstraat 2"
        nieuw = self.ronde("2026-10-21T13:17:00+02:00")
        self.assertEqual({t["voor"] for t in nieuw}, {"icloud-wacht", "plaud-wacht"})
        self.assertTrue(all(t["inhoud"]["adres"] == "Nieuwe Proefstraat 2" for t in nieuw))
        self.o["pakket"].update({"fotos_iphone": 1, "transcripten": 1})
        opnieuw = self.ronde("2026-10-21T13:18:00+02:00")
        self.assertEqual({t["voor"] for t in opnieuw}, {"icloud-wacht", "plaud-wacht"})
        self.assertEqual(self.afgevinkt, [])
        self.assertEqual(self.open_taken["cc:afspraak:bs1:icloud-wacht"]["status"], "klaar")
        self.assertNotEqual(self.o["stand"], "pakket klaar")
        self.open_taken["cc:afspraak:bs1:icloud-wacht"].update(status="opgepakt", opgepakt_door="icloud-wacht")
        self.open_taken["cc:afspraak:bs1:plaud-wacht"].update(status="opgepakt", opgepakt_door="plaud-wacht")
        afgerond = self.ronde("2026-10-21T13:19:00+02:00")
        self.assertEqual([t["soort"] for t in afgerond], ["impuls"])
        self.assertEqual(self.o["stand"], "pakket klaar")

    def test_ongeldige_agendatijd_meldt_nood_en_houdt_oude_taak_open(self):
        self.ronde("2026-10-21T13:16:00+02:00")
        self.r["einde"] = "geen tijd"
        self.ronde("2026-10-21T13:17:00+02:00")
        self.assertEqual(self.afgevinkt, [])
        foto = self.open_taken["cc:afspraak:bs1:icloud-wacht"]
        plaud = self.open_taken["cc:afspraak:bs1:plaud-wacht"]
        self.assertEqual((foto["status"], plaud["status"]), ("klaar", "klaar"))
        self.assertEqual((foto["inhoud"]["projectmap"], foto["inhoud"]["doelmap"]), ("", ""))
        self.assertEqual(plaud["inhoud"]["bezoekmap"], "")
        self.assertFalse(ZOEK.valideer_bezoekmap(plaud, CC.vs.SOORTEN)[0])
        with tempfile.TemporaryDirectory(prefix="icloud-toets-") as tijdelijk:
            with patch.dict(os.environ, {"HOME": tijdelijk}):
                spec = importlib.util.spec_from_file_location("icloud_uit_test", RUNNER / "mac" / "icloud_wacht.py")
                icloud = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(icloud)
        with self.assertRaises(ValueError):
            icloud._tkn_doel(foto["inhoud"])
        self.ronde("2026-10-21T13:18:00+02:00")
        self.assertIn("2026-10-21 barsten en scheuren: dossiermap of agendatijden onbruikbaar; geen taken voor de wachten",
                      [n["tekst"] for n in self.agent.hartslagen[-1][1]["nood"]])
        self.r["einde"] = "2026-10-21T10:00:00+02:00"
        hersteld = self.ronde("2026-10-21T13:19:00+02:00")
        self.assertEqual({t["uniek"] for t in hersteld if t["soort"] == "taak"},
                         {"cc:afspraak:bs1:icloud-wacht", "cc:afspraak:bs1:plaud-wacht"})
        self.assertTrue(ZOEK.valideer_bezoekmap(plaud, CC.vs.SOORTEN)[0])
        self.assertEqual(foto["inhoud"]["doelmap"], MAP + "/1. Foto's/2026-10-21 iPhone")

    def test_eerder_gesloten_taak_krijgt_pas_bij_herstart_een_nieuwe_sleutel(self):
        self.ronde("2026-10-21T13:16:00+02:00")
        oud = self.open_taken["cc:afspraak:bs1:icloud-wacht"]
        oud.update(status="opgepakt", opgepakt_door="commandocentrum", opgepakt_ts="2026-10-21T13:16:00+02:00")
        self.r["einde"] = "2026-10-21T12:00:00+02:00"
        self.ronde("2026-10-21T13:20:00+02:00")
        self.assertNotIn("cc:afspraak:bs1:icloud-wacht:2", self.open_taken)
        self.o["pakket"]["gemeten_ts"] = "2026-10-21T15:16:00+02:00"
        weer = self.ronde("2026-10-21T15:16:00+02:00")
        nieuw = next(t for t in weer if t["voor"] == "icloud-wacht")
        self.assertEqual(nieuw["uniek"], "cc:afspraak:bs1:icloud-wacht:2")
        self.assertEqual(self.open_taken[nieuw["uniek"]]["status"], "klaar")
        self.assertEqual(self.o["taken"][-1]["uniek"], nieuw["uniek"])
        self.r["adres"] = "Tweede Proefstraat 4"
        bijgewerkt = self.ronde("2026-10-21T15:17:00+02:00")
        foto = next(t for t in bijgewerkt if t["voor"] == "icloud-wacht")
        self.assertEqual(foto["uniek"], nieuw["uniek"])
        self.assertEqual(self.open_taken[nieuw["uniek"]]["inhoud"]["adres"], "Tweede Proefstraat 4")

    def test_verdwenen_bron_na_afgehandelde_taak_vraagt_opnieuw_aan(self):
        self.ronde("2026-10-21T13:16:00+02:00")
        for wacht in ("icloud-wacht", "plaud-wacht"):
            self.open_taken[f"cc:afspraak:bs1:{wacht}"].update(
                status="opgepakt", opgepakt_door=wacht, opgepakt_ts="2026-10-21T13:16:00+02:00")
        self.o["pakket"] = {"fotos_iphone": 0, "transcripten": 0, "gemeten_ts": "2026-10-21T13:17:00+02:00"}
        self.assertEqual([t for t in self.ronde("2026-10-21T13:17:00+02:00") if t["soort"] == "taak"], [])
        self.o["pakket"]["gemeten_ts"] = "2026-10-21T13:45:59+02:00"
        self.assertEqual([t for t in self.ronde("2026-10-21T13:45:59+02:00") if t["soort"] == "taak"], [])
        self.o["pakket"]["gemeten_ts"] = "2026-10-21T13:46:00+02:00"
        opnieuw = self.ronde("2026-10-21T13:46:00+02:00")
        self.assertEqual({t["uniek"] for t in opnieuw if t["soort"] == "taak"},
                         {"cc:afspraak:bs1:icloud-wacht:2"})
        self.o["pakket"]["gemeten_ts"] = "2026-10-21T14:15:59+02:00"
        self.assertNotIn("cc:afspraak:bs1:plaud-wacht:2",
                         {t["uniek"] for t in self.ronde("2026-10-21T14:15:59+02:00") if t["soort"] == "taak"})
        self.o["pakket"]["gemeten_ts"] = "2026-10-21T14:16:00+02:00"
        opnieuw = self.ronde("2026-10-21T14:16:00+02:00")
        self.assertIn("cc:afspraak:bs1:plaud-wacht:2", {t["uniek"] for t in opnieuw if t["soort"] == "taak"})

    def test_toekomstig_bezoek_zonder_map_geeft_nog_geen_nood(self):
        self.r.update(datum="2026-11-05", start="2026-11-05T08:00:00+01:00",
                      einde="2026-11-05T10:00:00+01:00")
        self.o.update(dossiermap="", bezoekmap="", id=None)
        self.ronde("2026-10-21T10:00:00+02:00")
        self.assertEqual(self.agent.hartslagen[-1][1]["nood"], [])
        self.o["taken"] = [{"voor": "icloud-wacht", "uniek": "cc:afspraak:bs1:icloud-wacht"}]
        self.ronde("2026-10-21T10:15:00+02:00")
        self.assertTrue(self.agent.hartslagen[-1][1]["nood"])


class DagbundelaarTaken(unittest.TestCase):
    def test_open_cc_taak_blijft_open_na_ochtendbundel(self):
        spec = importlib.util.spec_from_file_location("dagbundelaar_uit_test", RUNNER / "dagbundelaar.py")
        dag = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(dag)
        dag.DAG = "2026-10-21"
        agent = NepAgent()
        inhoud = json.dumps({"datum": dag.DAG})
        items = [
            {"id": 1, "uniek": "cc:afspraak:bs1:icloud-wacht", "van": "andere-maker", "voor": "icloud-wacht",
             "soort": "taak", "status": "klaar", "sleutel": "47035", "titel": "Fototaak", "inhoud": inhoud},
            {"id": 2, "uniek": "zelfstandige-taak", "van": "commandocentrum", "voor": "andere-agent",
             "soort": "taak", "status": "klaar", "sleutel": "47035", "titel": "Gewone taak", "inhoud": inhoud},
            {"id": 3, "uniek": "afspraak:test", "van": "agenda-wacht", "voor": "tkn", "soort": "afspraak",
             "status": "klaar", "sleutel": "47035", "titel": "Fictief bezoek", "inhoud": inhoud},
            {"id": 4, "uniek": "cc:afspraak:bs1:voorbereiding", "van": "commandocentrum", "voor": "tkn",
             "soort": "impuls", "status": "klaar", "sleutel": "47035", "titel": "Voorbereiding", "inhoud": inhoud},
            {"id": 5, "uniek": "cc:afspraak:bs1:verslag", "van": "commandocentrum", "voor": "tkn",
             "soort": "impuls", "status": "klaar", "sleutel": "47035", "titel": "Verslag", "inhoud": inhoud},
        ]
        afgevinkt = []
        with patch.object(dag, "ag", agent), patch.object(dag.bord, "call", return_value={"items": items}), \
                patch.object(dag.bord, "opgepakt", lambda kid, door: afgevinkt.append((kid, door))), \
                patch.object(dag.LC, "dag_heeft_dagboek", return_value=False):
            dag.main()
        self.assertEqual(afgevinkt, [(2, dag.NAAM), (3, dag.NAAM)])
        inhoud_bundel = "\n".join(it["inhoud"] for groep in agent.gestuurd for it in groep)
        self.assertNotIn("Fototaak", inhoud_bundel)
        self.assertNotIn("Voorbereiding", inhoud_bundel)
        self.assertNotIn("Verslag", inhoud_bundel)
        self.assertIn("Gewone taak", inhoud_bundel)


if __name__ == "__main__":
    uitslag = unittest.main(exit=False).result
    if not uitslag.wasSuccessful():
        raise SystemExit(1)
    print("alles geslaagd")
