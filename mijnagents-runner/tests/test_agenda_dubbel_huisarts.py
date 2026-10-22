"""Opdracht 16: uitsluitend fictieve zorggegevens en nagebootste agenda-acties."""
import copy
import sys
import unittest
import uuid
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

HIER = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(HIER), str(HIER / "koppelingen")]
import agenda_wacht as W  # noqa: E402
import mail_afspraken as MA  # noqa: E402

NU = datetime.fromisoformat("2026-10-22T09:00:00+02:00")
ADRES = "Proefstraat 7, 0000 Teststad"
PRIVE_MAILBOX = next(iter(MA.PRIVE))
PROFIEL = {"id": "proef-huisarts", "soort": "huisarts", "naam": "Praktijk Proef",
           "afzenders": [], "platform_afzenders": ["no-reply@boekingsplatform.test"],
           "locaties": [ADRES], "adres": ADRES,
           "praktijknamen": ["Praktijk Proef", "Arts Voorbeeld"],
           "patienten": ["Mora Voorbeeld"], "behandelaars": {"Arts Voorbeeld": "Huisarts"},
           "duur_minuten": 30, "geverifieerd": "2026-10-01", "bewijs": ["proef"]}


def mail(tekst, onderwerp="Uw afspraak bevestigd", mid="<proef-1@voorbeeld.test>"):
    return {"mailbox": PRIVE_MAILBOX, "map": "INBOX", "uid": 1,
            "message_id": mid, "van": "Boekingen <no-reply@boekingsplatform.test>",
            "onderwerp": onderwerp, "datum": "Thu, 22 Oct 2026 07:00:00 +0000",
            "ics": [], "linktijden": [], "tekst": tekst}


def bericht(locatie=ADRES, bij="Arts Voorbeeld", patient="Mora Voorbeeld", dag="22/10/2026", tijd="12:00"):
    return (f"Patiënt: {patient}\nDatum: {dag}\nTijdstip: {tijd}\n"
            f"Bij: {bij}\nLocatie: {locatie}\nDownload uw afspraak via https://voorbeeld.test/alleen-lezen")


def item(eid, kal, titel, plaats=ADRES, merk=None, start="2026-10-22T12:00:00+02:00"):
    return {"id": eid, "kalender": kal, "titel": titel, "start": start,
            "einde": "2026-10-22T12:30:00+02:00", "locatie": plaats,
            "omschrijving": "", "_merk": merk or {}, "hele_dag": False, "maker": W.WERKAGENDA,
            "_organisator_zelf": True, "deelnemers": [], "_agendagasten": [], "_terugkerend": False}


def afspraak():
    start = "2026-10-22T12:00:00+02:00"
    return {"soort": "zorg", "sleutel": "zorg|proef-huisarts|" + start,
            "start": start, "einde": "2026-10-22T12:30:00+02:00",
            "titel": "Huisarts Arts Voorbeeld", "locatie": ADRES, "geannuleerd": False,
            "bron_mailbox": PRIVE_MAILBOX, "bron_onderwerp": "Proefboeking",
            "bron_message_id": "<proef-1@voorbeeld.test>",
            "bron_ontvangen": "2026-10-22T09:00:00+02:00", "google": "",
            "zorg": {"praktijk": "proef-huisarts", "mehdi": True,
                     "patient": "Mora Voorbeeld", "behandelaar": "Arts Voorbeeld",
                     "gebeurtenis": "bevestiging"}}


class Opdracht16(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(MA, "zorgprofielen", lambda: [PROFIEL]))
        self.stack.enter_context(patch.object(W, "zorg_profielplaatsen_zetten", lambda *_a, **_k: (0, [])))

    def test_gedeeld_platform_vereist_locatie_en_behandelaar(self):
        goed = MA.uit_kandidaat(mail(bericht()), [PROFIEL])
        self.assertEqual(len(goed), 1)
        self.assertEqual(goed[0]["soort"], "zorg")
        self.assertEqual(goed[0]["zorg"]["behandelaar"], "Arts Voorbeeld")
        self.assertEqual(goed[0]["locatie"], ADRES)
        geen_bewijs = bericht(locatie="Andereweg 9, 0000 Teststad", bij="Onbekend Persoon")
        self.assertEqual(MA.uit_kandidaat(mail(geen_bewijs), [PROFIEL]), [])
        self.assertTrue(MA.ZORG_WERKVERSLAG, "test_gedeeld_platform_vereist_locatie_en_behandelaar")
        dubbel_ingeschreven = dict(PROFIEL, afzenders=["no-reply@boekingsplatform.test"])
        self.assertEqual(MA.uit_kandidaat(mail(geen_bewijs), [dubbel_ingeschreven]), [])
        self.assertEqual(MA.uit_kandidaat(mail(bericht(locatie="", bij="Praktijk Proef")), [PROFIEL])[0]["soort"], "zorg")

    def test_huisarts_zonder_einde_krijgt_standaardduur(self):
        with patch("urllib.request.urlopen", side_effect=AssertionError("downloadlink opgehaald")):
            a = MA.uit_kandidaat(mail(bericht()), [PROFIEL])[0]
        self.assertEqual(a["start"], "2026-10-22T12:00:00+02:00")
        self.assertEqual(a["einde"], "2026-10-22T12:30:00+02:00")
        self.assertTrue(a["zorg"]["duur_geschat"])
        self.assertNotIn("Download", str(a["zorg"]), "test_huisarts_zonder_einde_krijgt_standaardduur")
        woorden = MA.uit_kandidaat(mail(bericht(dag="do 22 oktober 2026")), [PROFIEL])[0]
        self.assertEqual(woorden["start"], a["start"])
        kaal = bericht().replace("Datum: 22/10/2026", "do 22 oktober 2026")
        self.assertEqual(MA.uit_kandidaat(mail(kaal), [PROFIEL])[0]["start"], a["start"])

    def test_gemaskeerde_patient_telt_als_mehdi(self):
        a = MA.uit_kandidaat(mail(bericht(patient="Mor*** Voo***")), [PROFIEL])[0]
        self.assertTrue(a["zorg"]["mehdi"])
        ander = MA.uit_kandidaat(mail(bericht(patient="And*** Per***")), [PROFIEL])[0]
        self.assertFalse(ander["zorg"]["mehdi"], "test_gemaskeerde_patient_telt_als_mehdi")

    def test_huisarts_wijziging_en_annulering_houden_dezelfde_sleutel(self):
        db = Path("/tmp/cx16") / f"zorgproef-{uuid.uuid4().hex}.db"
        with patch.object(MA, "DB", str(db)):
            eerst = MA.uit_kandidaat(mail(bericht(dag="23/10/2026"), mid="<eerst@voorbeeld.test>"), [PROFIEL])
            MA.bewaar(eerst, NU)
            nieuw = bericht(dag="23/10/2026", tijd="13:00") + "\nOud tijdstip: 23/10/2026 om 12:00"
            gewijzigd = MA.uit_kandidaat(mail(nieuw, "Uw afspraak gewijzigd naar een ander uur",
                                               "<nieuw@voorbeeld.test>"), [PROFIEL])
            MA.bewaar(gewijzigd, NU)
            rijen = [a for a in MA.alle() if a["soort"] == "zorg"]
            self.assertEqual(len(rijen), 1)
            self.assertEqual(rijen[0]["start"], "2026-10-23T13:00:00+02:00")
            afzeg = MA.uit_kandidaat(mail(bericht(dag="23/10/2026", tijd="13:00"),
                                           "Uw afspraak is geannuleerd", "<afzeg@voorbeeld.test>"), [PROFIEL])
            MA.bewaar(afzeg, NU)
            rijen = [a for a in MA.alle() if a["soort"] == "zorg"]
            self.assertEqual(len(rijen), 1)
            self.assertEqual(rijen[0]["geannuleerd"], 1)

    def test_huisarts_vandaag_geeft_nood(self):
        a = afspraak()
        a.update(status="ontbreekt")
        inserts = []
        def ins(kal, body, _tok, **_kw):
            inserts.append((kal, copy.deepcopy(body)))
            return {"id": "nieuw-1"}
        self.stack.enter_context(patch.object(W, "_insert", ins))
        self.stack.enter_context(patch.object(W, "_zorg_teruglezen", lambda *_a, **_k: ""))
        st = W.zorg_afspraken_zetten([a], [], "proef", NU)
        self.assertEqual(len(inserts), 1)
        self.assertEqual(inserts[0][0], W.PRIVE_AGENDA)
        self.assertEqual(len(st["noden"]), 1)
        self.assertIn("vandaag", st["noden"][0]["tekst"].lower())
        self.assertNotIn("Arts Voorbeeld", str(st["noden"]), "test_huisarts_vandaag_geeft_nood")
        morgen = afspraak()
        morgen.update(sleutel="zorg|proef-huisarts|2026-10-23T02:00:00+02:00",
                      start="2026-10-23T02:00:00+02:00", einde="2026-10-23T02:30:00+02:00",
                      status="ontbreekt")
        nacht = W.zorg_afspraken_zetten([morgen], [], "proef", datetime.fromisoformat("2026-10-22T21:00:00+02:00"))
        self.assertEqual(len(nacht["noden"]), 1)
        self.assertIn("binnen zes uur", nacht["noden"][0]["tekst"])

    def test_parkeerhint_is_gelijk_maar_ander_huisnummer_niet(self):
        zelfde = "PROEFSTRAAT 7, 0000 Teststad (parkeren achteraan), België"
        self.assertTrue(MA.zorg_plaats_gelijk(zelfde, "proefstraat 7 0000 teststad"))
        self.assertTrue(MA.zorg_plaats_gelijk("Proefstraat 7, 0000 Teststad, parkeren: achteraan", ADRES))
        self.assertFalse(MA.zorg_plaats_gelijk(zelfde, "Proefstraat 8, 0000 Teststad"))
        self.assertFalse(MA.zorg_plaats_gelijk(zelfde, "Modelweg 7, 0000 Teststad"))
        self.assertFalse(MA.zorg_plaats_gelijk(zelfde, "Proefstraat 7, 1000 Teststad"))
        a = afspraak()
        a.update(status="gekoppeld", google=f"{W.PRIVE_AGENDA}|prive-1")
        prive = item("prive-1", W.PRIVE_AGENDA, "!! [PR] Huisarts", zelfde,
                     {W.ZORGMERK: a["sleutel"]})
        st = W.zorg_afspraken_zetten([a], [prive], "proef", NU)
        self.assertEqual(st["open"], 0)
        prive["locatie"] = "Proefstraat 8, 0000 Teststad"
        st = W.zorg_afspraken_zetten([a], [prive], "proef", NU)
        self.assertEqual(st["open"], 1, "test_parkeerhint_is_gelijk_maar_ander_huisnummer_niet")

    def test_zorg_dubbel_prive_is_bron_en_werk_is_schaduw(self):
        a = afspraak()
        prive = item("prive-1", W.PRIVE_AGENDA, "!! [PR] Huisarts",
                     merk={W.ZORGMERK: a["sleutel"]})
        werk = item("werk-1", W.WERKAGENDA, "!! [PR] Huisarts Arts Voorbeeld",
                    start="2026-10-22T12:10:00+02:00")
        res = MA.vergelijk([a], [werk, prive], NU)[0]
        self.assertEqual(res["google"], f"{W.PRIVE_AGENDA}|prive-1")
        werk["_merk"] = {W.ZORGMERK: a["sleutel"]}
        self.assertEqual(MA.vergelijk([a], [werk, prive], NU)[0]["google"], f"{W.PRIVE_AGENDA}|prive-1")
        self.assertEqual(MA.vergelijk([dict(a, geannuleerd=True)], [werk, prive], NU)[0]["google"],
                         f"{W.PRIVE_AGENDA}|prive-1")
        patches, moves = [], []
        self.stack.enter_context(patch.object(W, "_patch", lambda x, *_a, **_k: patches.append(x["id"])))
        self.stack.enter_context(patch.object(W, "_verplaats_naar", lambda x, *_a: moves.append(x["id"])))
        st = W.zorg_afspraken_zetten([res], [werk, prive], "proef", NU)
        self.assertTrue(werk.get("_zorg_schaduw"))
        dubbel = [n for n in st["noden"] if n["tekst"].startswith("Dubbele zorgafspraak")]
        self.assertEqual(len(dubbel), 1)
        self.assertEqual(dubbel[0]["tekst"],
                         "Dubbele zorgafspraak op 22-10 12:00: een collega zette ze ook op de werkagenda. "
                         "Zal ik die verwijderen? (antwoord aan Claude)")
        self.assertNotIn("werk-1", patches + moves)
        self.assertNotIn("Arts Voorbeeld", str(st["noden"] + st["bord"]),
                         "test_zorg_dubbel_prive_is_bron_en_werk_is_schaduw")

    def test_schaduwitems_worden_nooit_gepatcht_of_verhuisd(self):
        a = afspraak()
        prive = item("prive-1", W.PRIVE_AGENDA, "!! [PR] Huisarts", merk={W.ZORGMERK: a["sleutel"]})
        werk = item("werk-1", W.WERKAGENDA, "!! [PR] Huisarts", start="2026-10-22T12:10:00+02:00")
        W.markeer_zorgschaduwen([werk, prive], [PROFIEL], NU)
        self.assertTrue(werk.get("_zorg_schaduw"))
        self.assertTrue(W._titel_patch_reden(werk, "VR " + werk["titel"]))
        with patch.object(W, "mag_schrijven", lambda _k: True), \
             patch("urllib.request.urlopen", side_effect=AssertionError("netwerkactie")):
            with self.assertRaises(W.SchaduwItem, msg="test_schaduwitems_worden_nooit_gepatcht_of_verhuisd"):
                W._patch(werk, {"location": ADRES}, "proef")
            with self.assertRaises(W.SchaduwItem):
                W._verplaats_naar(werk, W.PRIVE_AGENDA, "proef")

    def test_profielplaatsmerk_en_verhuisd_item_zijn_privebron(self):
        for merk, oms in (({W.ZORGPLAATSMERK: W._zorg_profielmerk(PROFIEL)}, ""),
                          ({}, "Van de werkagenda naar privé verhuisd door de Agendawacht")):
            with self.subTest(merk=bool(merk)):
                prive = item("prive-1", W.PRIVE_AGENDA, "!! [PR] Huisarts", merk=merk)
                prive["omschrijving"] = oms
                werk = item("werk-1", W.WERKAGENDA, "!! [PR] Huisarts", start="2026-10-22T12:10:00+02:00")
                noden = W.markeer_zorgschaduwen([werk, prive], [PROFIEL], NU)
                self.assertTrue(werk.get("_zorg_schaduw"))
                self.assertEqual(len(noden), 1)
        prive = item("prive-2", W.PRIVE_AGENDA, "!! [PR] Huisarts", merk={W.ZORGMERK: afspraak()["sleutel"]})
        ander = item("werk-2", W.WERKAGENDA, "!! [PR] Huisarts", plaats="Modelweg 8, 0000 Teststad")
        self.assertEqual(W.markeer_zorgschaduwen([ander, prive], [PROFIEL], NU), [])
        self.assertFalse(ander.get("_zorg_schaduw"))

    def test_handmatige_rit_onderdrukt_agentrit_over_zorgcluster(self):
        a = afspraak()
        prive = item("prive-1", W.PRIVE_AGENDA, "!! [PR] Huisarts", merk={W.ZORGMERK: a["sleutel"]})
        werk = item("werk-1", W.WERKAGENDA, "!! [PR] Huisarts", start="2026-10-22T12:10:00+02:00")
        heen = item("hand-heen", W.WERKAGENDA, "Rijden naar Teststad", plaats="",
                    start="2026-10-22T11:40:00+02:00")
        heen["einde"] = prive["start"]
        terug = item("hand-terug", W.WERKAGENDA, "🚗 Reistijd ← Teststad", plaats="",
                     start=prive["einde"])
        terug["einde"] = "2026-10-22T13:00:00+02:00"
        items = [werk, prive, heen, terug]
        inserts = []
        p = self.stack.enter_context
        p(patch.object(W.agenda, "_toegang", lambda: "proef"))
        p(patch.object(W, "_cache_laden", lambda: {}))
        p(patch.object(W, "_cache_bewaren", lambda _c: None))
        p(patch.object(W, "lara_vakantiedagen", lambda: set()))
        p(patch.object(W, "geen_auto_dagen", lambda: set()))
        p(patch.object(W.projectadressen, "index", lambda: {}))
        p(patch.object(W, "plek_zoeken", lambda _s: (None, None)))
        p(patch.object(W, "vaste_plek", lambda _s: (None, None)))
        p(patch.object(W, "coord", lambda adres, _c: (0, 0) if adres == W.THUIS else (1, 1) if adres == ADRES else None))
        p(patch.object(W, "rijtijd_min", lambda *_a: (20, "proef")))
        p(patch.object(W, "ritlabel", lambda *_a: "Teststad"))
        p(patch.object(W, "_insert", lambda *_a, **_k: inserts.append(_a)))
        p(patch.object(W, "_patch", lambda *_a, **_k: None))
        W.reistijd_zetten(items, nu=NU)
        self.assertTrue(werk.get("_zorg_schaduw"))
        self.assertEqual(inserts, [])
        heen["einde"] = werk["start"]  # ook het grensuur van de schaduw hoort bij dezelfde zorgcluster
        W.reistijd_zetten(items, nu=NU)
        self.assertEqual(inserts, [])
        heen["titel"] = "🚗 Reistijd → Teststad"
        W.reistijd_zetten(items, nu=NU)
        self.assertEqual(inserts, [])
        W.reistijd_zetten([werk, prive], nu=NU)
        self.assertGreaterEqual(len(inserts), 1, "test_handmatige_rit_onderdrukt_agentrit_over_zorgcluster")


if __name__ == "__main__":
    unittest.main(verbosity=2)
