"""Regressies uit het incident van 17-10-2026; uitsluitend nagebootste gegevens."""
import sys
import os
import io
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "koppelingen"))
_data = tempfile.TemporaryDirectory(prefix="agenda-incident-proef-")
_expanduser = os.path.expanduser


def _proefpad(pad):
    return str(Path(_data.name) / pad.removeprefix("~/")) if pad.startswith("~/appportal/") else _expanduser(pad)


with patch("os.path.expanduser", side_effect=_proefpad):
    import organisatie
    with patch.object(organisatie, "firmacodes", return_value={}), \
            patch.object(organisatie, "agendacodes", return_value={}):
        import agenda_wacht as W
    from koppelingen import bellen
    from koppelingen import agenda


class Incident(unittest.TestCase):
    def test_explicit_cancellation_without_false_calendly_match(self):
        self.assertFalse(bellen.afgezegd({"description": "Need to change? Cancel: https://calendly.test/x"}))
        self.assertTrue(bellen.afgezegd({"description": "Door omstandigheden zal de call niet kunnen doorgaan."}))
        self.assertFalse(bellen.afgezegd({"description": "Als een afspraak afgezegd wordt, meld ik dat."}))
        self.assertFalse(bellen.afgezegd({"description": "De afspraak gaat niet door. De afspraak is alsnog bevestigd."}))
        self.assertTrue(bellen.afgezegd({"attendees": [{"self": True, "responseStatus": "declined"}]}))
        self.assertTrue(bellen.afgezegd({"status": "cancelled"}))

    def test_home_is_not_outside_or_departure(self):
        home = "Herfstlaan 65, 3010 Leuven, België"
        self.assertTrue(W.is_thuis_adres(home))
        self.assertFalse(W.is_thuis_adres("Herfstlaan 66, 3010 Leuven"))
        self.assertIsNone(W.markering_tegen(
            "!! Mehdi: [UB-PB] OB", "2026-10-16",
            [("Geen buiten afspraken", "buiten")], locatie=home))
        start = (datetime.now().astimezone() + timedelta(days=1)).replace(second=0, microsecond=0)
        a = {"kalender": W.WERKAGENDA, "id": "home", "titel": "!! Mehdi: [UB-PB] OB",
             "start": start.isoformat(), "einde": (start + timedelta(hours=1)).isoformat(),
             "locatie": home, "omschrijving": ""}
        rooster = W.belrooster([a], start.date().isoformat())
        self.assertEqual(len(rooster), 1)
        self.assertIn("minuten thuis", rooster[0]["tekst"])
        self.assertNotIn("vertrekken", rooster[0]["tekst"], "Herfstlaan is thuis en heeft geen vertrekmelding")

    def test_partner_beats_unrelated_deal_at_home(self):
        a = {"titel": "!! mehdi: catalin offerte dorin", "locatie": "Herfstlaan 65, 3010 Leuven, België"}
        with patch.object(W, "_gastregels", return_value={"firma_gasten": {"HARM": ["Catalin"]}}), \
                patch.object(W, "_deal_op_adres", side_effect=AssertionError("geen deal op thuisadres")):
            nieuw, uitleg = W.titel_uit_onderzoek(a)
        self.assertEqual(nieuw, "Mehdi & Catalin: [HB-IN] Offerte dorin",
                         "Catalin blijft Harmoniebouw zonder klantgok")
        self.assertIn("thuis", uitleg)

    def test_home_never_creates_a_route(self):
        begin = (datetime.now().astimezone() + timedelta(days=2)).replace(second=0, microsecond=0)
        event = {"kalender": W.WERKAGENDA, "id": "thuis", "titel": "!! Mehdi: [UB-PB] OB",
                 "start": begin.isoformat(), "einde": (begin + timedelta(hours=1)).isoformat(),
                 "locatie": "Herfstlaan 65, 3010 Leuven, België"}
        with patch.object(W.agenda, "_toegang", return_value="proef"), \
                patch.object(W, "_cache_laden", return_value={}), \
                patch.object(W, "coord", return_value=(0, 0)), \
                patch.object(W.projectadressen, "index", return_value={}), \
                patch.object(W, "lara_vakantiedagen", return_value=set()), \
                patch.object(W, "geen_auto_dagen", return_value={begin.date().isoformat()}), \
                patch.object(W, "_insert", side_effect=AssertionError("geen rit aanmaken")):
            gemaakt, _, _, _, regels = W.reistijd_zetten([event])
        self.assertEqual(gemaakt, 0, "Thuis-naar-thuis mag geen rit opleveren")
        self.assertFalse(any("BUITEN" in r for r in regels), "Thuis is ook op een autoloze dag niet buiten")

    def test_placeholder_person_is_not_prospect(self):
        W._DEALS_OP_ADRES.clear()
        data = {"items": [{"item": {"title": "Herfstlaan 65 - proef", "person": {"name": "Voornaam Achternaam"},
                                    "status": "open"}}]}
        with patch.object(W.pipedrive, "get", return_value=data):
            self.assertIsNone(W._deal_op_adres("UNAB", "Herfstlaan 65, 3010 Leuven"))
        W._DEALS_OP_ADRES.clear()

    def test_address_deal_does_not_overwrite_a_different_person(self):
        with patch.object(W, "_deal_op_adres", return_value=("Jan Peeters", False)):
            nieuw, _ = W.titel_uit_onderzoek({"titel": "mehdi: Marie barsten scheuren",
                                               "locatie": "Dorpstraat 10, 3000 Leuven"})
        self.assertIsNone(nieuw, "Een adresdeal zonder naamovereenkomst blijft een vraag")

    def test_cancelled_call_never_uses_departure_number(self):
        now = datetime.now().astimezone()
        regel = {"sleutel": f"{W.WERKAGENDA}:fake:{(now + timedelta(minutes=5)).isoformat()}",
                 "tijd": (now - timedelta(seconds=1)).isoformat(), "tekst": "vertrek", "titel": "proefafspraak"}
        calls = []
        with patch.object(bellen, "afspraak_bellen_beschikbaar", return_value=True), \
                patch.object(bellen, "_rooster_regels", return_value=[regel]), \
                patch.object(bellen, "belafspraak_actueel", return_value=(False, "afgezegd")), \
                patch.object(bellen, "bel_afspraak", side_effect=AssertionError("vertrekoproep")), \
                patch.object(bellen, "bel_vast", side_effect=lambda *a, **k: calls.append(a) or [("twilio-vast", "CAproef")]):
            bellen.afspraken_bellen({"gebeld": {}, "belpogingen": {}}, spoor=None)
        self.assertEqual(len(calls), 1)
        self.assertIn("Niet vertrekken", calls[0][0])

    def test_cancelled_lara_call_is_never_niet_vertrekken(self):
        # FR-210: een afgezegde Lara-afspraak ([LA], ook op een andere agenda) of rit geeft nooit 'niet vertrekken'
        now = datetime.now().astimezone()
        for titel in ("!! Mehdi: [LA] Lara bij mij", "\U0001F697 Reistijd: thuis \u2192 school"):
            regel = {"sleutel": f"{W.PRIVE_AGENDA}:fake:{(now + timedelta(minutes=5)).isoformat()}",
                     "tijd": (now - timedelta(seconds=1)).isoformat(), "tekst": "vertrek", "titel": titel}
            calls, staat = [], {"gebeld": {}, "belpogingen": {}}
            with patch.object(bellen, "afspraak_bellen_beschikbaar", return_value=True), \
                    patch.object(bellen, "_rooster_regels", return_value=[regel]), \
                    patch.object(bellen, "belafspraak_actueel", return_value=(False, "afgezegd")), \
                    patch.object(bellen, "bel_afspraak", side_effect=AssertionError("vertrekoproep")), \
                    patch.object(bellen, "bel_vast", side_effect=lambda *a, **k: calls.append(a) or [("twilio-vast", "CAproef")]):
                bellen.afspraken_bellen(staat, spoor=None)
                bellen.afspraken_bellen(staat, spoor=None)
            self.assertEqual(calls, [], titel)

    def test_google_item_is_checked_at_call_time(self):
        begin = "2026-10-20T09:00:00+02:00"
        regel = {"sleutel": f"werk@example.com:abc:{begin}"}
        gevallen = [({"start": {"dateTime": begin},
                     "description": "Door omstandigheden zal de call niet kunnen doorgaan."},
                    (False, "afgezegd")),
                   ({"start": {"dateTime": begin}, "status": "confirmed"}, (True, "")),
                   ({"start": {"dateTime": "2026-10-20T10:00:00+02:00"}},
                    (False, "afspraak verplaatst of verdwenen"))]
        for event, verwacht in gevallen:
            with patch.object(agenda, "_toegang", return_value="proef"), \
                    patch.object(bellen.urllib.request, "urlopen",
                                 return_value=io.BytesIO(json.dumps(event).encode())):
                self.assertEqual(bellen.belafspraak_actueel(regel), verwacht,
                                 "Actueel Google-item beslist over de vertrekoproep")

    def test_unreadable_google_uses_one_distinct_warning(self):
        now = datetime.now().astimezone()
        regel = {"sleutel": f"werk@example.com:fout:{(now + timedelta(minutes=5)).isoformat()}",
                 "tijd": (now - timedelta(seconds=1)).isoformat(), "tekst": "vertrek", "titel": "proef"}
        oproepen = []
        with tempfile.TemporaryDirectory() as tmp, \
                patch.object(bellen, "AFZEGSPOOR", str(Path(tmp) / "afzeg.jsonl")), \
                patch.object(bellen, "afspraak_bellen_beschikbaar", return_value=True), \
                patch.object(bellen, "_rooster_regels", return_value=[regel]), \
                patch.object(bellen, "belafspraak_actueel", return_value=(False, "agenda niet te verifiëren (TimeoutError)")), \
                patch.object(bellen, "bel_afspraak", side_effect=AssertionError("geen vertreknummer")), \
                patch.object(bellen, "bel_vast", side_effect=lambda *a: oproepen.append(a) or [("twilio-vast", "CAproef")]):
            bellen.afspraken_bellen({"gebeld": {}, "belpogingen": {}}, spoor=None, nood=[])
            bellen.afspraken_bellen({"gebeld": {}, "belpogingen": {}}, spoor=None, nood=[])
        self.assertEqual(len(oproepen), 1, "Onleesbare agenda geeft precies één waarschuwing via vast nummer")


if __name__ == "__main__":
    unittest.main()
