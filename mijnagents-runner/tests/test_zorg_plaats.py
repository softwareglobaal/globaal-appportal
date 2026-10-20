"""Z1-Z4: fictieve zorgprofielen, een vaste klok en een nagebootste agenda zonder netwerk."""
import copy
import inspect
import os
import sys
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

HIER = Path(__file__).resolve().parent.parent
TMP = HIER.parent / ".tmp"
TMP.mkdir(exist_ok=True)
os.environ["BELLEN_UIT"] = "1"
sys.path[:0] = [str(HIER), str(HIER / "koppelingen")]
import agenda_wacht as W  # noqa: E402
import mail_afspraken as MA  # noqa: E402

NU = datetime.fromisoformat("2026-10-20T09:00:00+02:00")
ADRES_A = "Oefenlaan 7, 0000 Teststad"
ADRES_B = "Modelweg 8, 0000 Teststad"
MAILADRES = "Nieuweweg 9, 0000 Teststad"
LARA = next(k for k, n in W.KALENDERS.items() if n == "Lara")


def profiel(pid="proef-a", naam="Praktijk Alpha", adres=ADRES_A):
    return {"id": pid, "naam": naam, "soort": "kine", "praktijknamen": [naam], "adres": adres,
            "patienten": ["Mo Voorbeeld"], "geverifieerd": "2026-10-19", "bewijs": ["proefbron"]}


def item(eid="zorg-1", kalender=None, titel="!! [PR] Kine controle", locatie="", **extra):
    kal = kalender or W.PRIVE_AGENDA
    a = {"id": eid, "kalender": kal, "titel": titel, "start": "2026-10-21T12:00:00+02:00",
         "einde": "2026-10-21T12:30:00+02:00", "locatie": locatie, "omschrijving": "Fictieve afspraak.",
         "maker": W.WERKAGENDA, "_organisator_zelf": True, "deelnemers": [], "_agendagasten": [],
         "_terugkerend": False, "_merk": {}, "hele_dag": False}
    a.update(extra)
    return a


class Schrijver:
    def __init__(self, items):
        self.items = items
        self.events = {(a["kalender"], a["id"]): self._event(a) for a in items}
        self.patches = []
        self.ritten = []

    @staticmethod
    def _event(a):
        return {"id": a["id"], "summary": a["titel"], "description": a.get("omschrijving") or "",
                "location": a.get("locatie") or "", "start": {"dateTime": a["start"]},
                "end": {"dateTime": a["einde"]}, "organizer": {"self": True, "email": a["maker"]},
                "attendees": [{"email": g} for g in a.get("deelnemers") or []],
                "extendedProperties": {"private": copy.deepcopy(a.get("_merk") or {})}}

    def lees(self, kal, eid, _tok):
        return copy.deepcopy(self.events.get((kal, eid)))

    def patch(self, a, body, _tok, **_kwargs):
        self.patches.append((a["id"], copy.deepcopy(body)))
        e = self.events[(a["kalender"], a["id"])]
        for k, v in body.items():
            if k == "extendedProperties":
                privaat = e.setdefault(k, {}).setdefault("private", {})
                for mk, mv in v["private"].items():
                    if mv is None:
                        privaat.pop(mk, None)
                    else:
                        privaat[mk] = mv
            else:
                e[k] = copy.deepcopy(v)
        for k, veld in (("summary", "titel"), ("description", "omschrijving"), ("location", "locatie")):
            if k in body:
                a[veld] = body[k]
        if "extendedProperties" in body:
            a["_merk"] = copy.deepcopy(e["extendedProperties"]["private"])

    def move(self, a, doel, _tok):
        e = self.events.pop((a["kalender"], a["id"]))
        self.events[(doel, a["id"])] = e

    def insert(self, kal, body, _tok, **_kwargs):
        self.ritten.append(copy.deepcopy(body))
        a = {"id": body["id"], "kalender": kal, "titel": body["summary"],
             "start": body["start"]["dateTime"], "einde": body["end"]["dateTime"],
             "omschrijving": body.get("description") or "", "locatie": body.get("location") or "",
             "maker": W.WERKAGENDA, "deelnemers": [], "_agendagasten": [], "_terugkerend": False,
             "_merk": body.get("extendedProperties", {}).get("private", {}), "hele_dag": False}
        self.items.append(a)
        self.events[(kal, a["id"])] = self._event(a)
        return copy.deepcopy(self.events[(kal, a["id"])])


class ZorgPlaats(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.profiles = [profiel()]
        self.items = []
        self.writer = Schrijver(self.items)
        p = self.stack.enter_context
        p(patch.object(W, "_patch", self.writer.patch))
        p(patch.object(W, "_lees_event", self.writer.lees))
        p(patch.object(W, "_verplaats_naar", self.writer.move))
        p(patch.object(W, "_insert", self.writer.insert))
        p(patch.object(W.agenda, "_toegang", lambda: "proef"))
        p(patch.object(W, "mag_schrijven", lambda _kal: True))
        p(patch.object(MA, "zorgprofielen", lambda: self.profiles))
        p(patch.object(W.projectadressen, "index", lambda: {}))
        p(patch.object(W, "plek_zoeken", lambda _tekst: (None, None)))
        p(patch.object(W, "vaste_plek", lambda _titel: (None, None)))
        p(patch.object(W, "zoom_zonder_wachtwoord", lambda *_a: []))
        p(patch.object(W, "zoom_zonder_wachtkamer", lambda *_a: []))

    def voeg(self, a):
        self.items.append(a)
        self.writer.events[(a["kalender"], a["id"])] = self.writer._event(a)
        return a

    def zorg(self):
        extra = {"bijwerken_items": True} if "bijwerken_items" in inspect.signature(W.zorg_afspraken_zetten).parameters else {}
        return W.zorg_afspraken_zetten([], self.items, "proef", nu=NU, **extra)

    def vraag(self, niet_op_kaart=None):
        opties = {"nu": NU}
        if niet_op_kaart is not None and "niet_op_kaart" in inspect.signature(W.vragen_in_agenda).parameters:
            opties["niet_op_kaart"] = niet_op_kaart
        return W.vragen_in_agenda(self.items, **opties)

    def rit(self, kaart_adressen=(), niet_op_kaart=None):
        p = self.stack.enter_context
        p(patch.object(W, "_cache_laden", lambda: {}))
        p(patch.object(W, "_cache_bewaren", lambda _cache: None))
        p(patch.object(W, "lara_vakantiedagen", lambda: set()))
        p(patch.object(W, "geen_auto_dagen", lambda: set()))
        vindbaar = {ADRES_A, *kaart_adressen}
        p(patch.object(W, "coord", lambda adres, _cache: (0, 0) if adres == W.THUIS else (1, 1) if adres in vindbaar else None))
        p(patch.object(W, "ritlabel", lambda adres, _ander="": "thuis" if adres == W.THUIS else "Teststad"))
        p(patch.object(W, "rijtijd_min", lambda _a, _b, _t: (20, "proef")))
        p(patch.object(W, "kleur_gewenst", lambda *_a: "11"))
        p(patch.object(W, "_eigen_rit_weg", lambda *_a: False))
        opties = {"nu": NU}
        if niet_op_kaart is not None and "niet_op_kaart" in inspect.signature(W.reistijd_zetten).parameters:
            opties["niet_op_kaart"] = niet_op_kaart
        return W.reistijd_zetten(self.items, **opties)

    def test_benoemde_plek_zonder_nummer_krijgt_rit_geen_vraag(self):
        plek = "Teststation Zuid"
        self.voeg(item("benoemde-plek", titel="!! [PR] Buitenproef", locatie=plek))
        self.assertGreaterEqual(self.rit(kaart_adressen={plek})[0], 1)
        self.assertEqual(self.vraag(), (0, 0))
        self.assertFalse(W._adresvragen(self.items, nu=NU, projecten={}))
        self.assertFalse(W._bruikbare_locatie("https://voorbeeld.test/route"))
        self.assertFalse(MA.zorg_locatie_is_adres(plek))
        self.assertFalse(MA.zorg_locatie_is_adres("De afspraak is bevestigd"))

    def test_kaartadres_niet_gevonden_vraagt_en_sluit_na_correctie(self):
        a = self.voeg(item("kaart-prive", titel="!! [PR] Buitenproef", locatie=ADRES_B))
        niet_op_kaart = set()
        self.assertEqual(self.rit(niet_op_kaart=niet_op_kaart)[0], 0)
        self.assertEqual(niet_op_kaart, {(a["kalender"], a["id"], a["start"])})
        self.assertEqual(self.vraag(niet_op_kaart), (1, 0))
        verwacht = ("Mehdi, het adres van de buitenafspraak van 21-10 12:00 vind ik niet op de kaart; "
                   "schrijf het zoals op de kaart (straat nummer, postcode gemeente).")
        self.assertEqual(a["omschrijving"].split("\n", 1)[0], W.VR_REGEL + verwacht)
        self.assertFalse(W.adres_vraag_noden(self.items, nu=NU, niet_op_kaart=niet_op_kaart))
        a["locatie"] = ADRES_A
        nu_vindbaar = set()
        self.rit(niet_op_kaart=nu_vindbaar)
        self.assertFalse(nu_vindbaar)
        self.assertEqual(self.vraag(nu_vindbaar), (0, 1))
        self.assertFalse(a["titel"].startswith("VR "))
        self.assertNotIn("vind ik niet op de kaart", a["omschrijving"])

    def test_kaartadres_niet_gevonden_geeft_stabiele_nood_als_vr_niet_kan(self):
        a = self.voeg(item("kaart-gast", titel="!! [PR] Buitenproef", locatie=ADRES_B,
                           deelnemers=["gast@voorbeeld.test"]))
        niet_op_kaart = set()
        self.rit(niet_op_kaart=niet_op_kaart)
        self.assertEqual(niet_op_kaart, {(a["kalender"], a["id"], a["start"])})
        self.assertEqual(self.vraag(niet_op_kaart), (0, 0))
        nood = W.adres_vraag_noden(self.items, nu=NU, niet_op_kaart=niet_op_kaart)
        self.assertEqual(len(nood), 1)
        self.assertIn("vind ik niet op de kaart", nood[0]["tekst"])
        self.assertEqual(W.adres_vraag_noden(self.items, nu=NU, niet_op_kaart=niet_op_kaart), nood)

    def test_kaartfout_gaat_in_dezelfde_ronde_naar_vraag_en_nood(self):
        bron = inspect.getsource(W.main)
        rit = "reistijd_zetten(rit_items, dag_grens, niet_op_kaart=niet_op_kaart)"
        vraag = "vragen_in_agenda(rit_items, niet_op_kaart=niet_op_kaart)"
        nood = "adres_vraag_noden(rit_items, niet_op_kaart=niet_op_kaart)"
        for stap in (rit, vraag, nood):
            self.assertIn(stap, bron)
        self.assertLess(bron.index(rit), bron.index(vraag))
        self.assertLess(bron.index(vraag), bron.index(nood))

    def test_huisbezoek_als_plaats_geeft_geen_rit_of_vraag(self):
        self.voeg(item("huisbezoek-plaats", titel="!! [PR] Buitenproef",
                       locatie="Huisbezoek bij testgezin"))
        self.assertEqual(self.rit()[0], 0)
        self.assertEqual(self.vraag(), (0, 0))
        self.assertFalse(W._bruikbare_locatie("aan-huis bij testgezin"))
        self.assertFalse(MA.zorg_locatie_is_adres("aan-huis bij testgezin, Modelweg 8"))

    def test_zorg_profieladres_uniek_en_gemerkt(self):
        a = self.voeg(item(kalender=W.WERKAGENDA, titel="Kine controle"))
        r = self.zorg()
        self.assertEqual(r["verhuisd"], 1)
        self.assertEqual(a["kalender"], W.PRIVE_AGENDA)
        self.assertEqual(a["locatie"], ADRES_A, "test_zorg_profieladres_uniek_en_gemerkt")
        self.assertTrue(a["_merk"].get("agendawacht_zorgplaats", "").startswith("proef-a:"))
        self.assertEqual(a["omschrijving"].count("Adres uit het geverifieerde zorgprofiel (Agendawacht, 20-10-2026)"), 1)
        self.assertNotIn("Praktijk Alpha", a["omschrijving"])
        self.assertGreaterEqual(self.rit()[0], 1)
        aantal = len(self.writer.patches)
        self.zorg()
        self.assertEqual(len(self.writer.patches), aantal)

    def test_zorg_twee_profielen_vraagt(self):
        self.profiles.append(profiel("proef-b", "Praktijk Beta", ADRES_B))
        a = self.voeg(item())
        self.zorg()
        self.assertEqual(a["locatie"], "")
        self.assertEqual(self.vraag()[0], 1)
        self.assertTrue(a["titel"].startswith("VR "))

    def test_zorg_praktijknaam_ondubbelzinnig(self):
        self.profiles.append(profiel("proef-b", "Praktijk Beta", ADRES_B))
        a = self.voeg(item(titel="!! [PR] Kine bij Praktijk Beta"))
        self.zorg()
        self.assertEqual(a["locatie"], ADRES_B)

    def test_zorg_huisbezoek_geen_praktijkadres(self):
        a = self.voeg(item(titel="!! [PR] Kine huisbezoek", locatie="aan huis"))
        self.zorg()
        self.assertEqual(a["locatie"], "aan huis")
        self.assertEqual(self.vraag(), (0, 0))
        self.assertEqual(self.rit()[0], 0)
        self.assertFalse(MA.zorg_locatie_is_adres("Huisbezoek bij patiënt thuis"))

    def test_zorg_nooit_aan_huis_standaardzin_krijgt_profieladres_en_rit(self):
        self.profiles[0]["aan_huis"] = False
        zin = "Indien u een huisbezoek hebt aangevraagd, komen we aan huis."
        a = self.voeg(item(omschrijving="Fictieve afspraak. " + zin))
        self.zorg()
        self.assertEqual(a["locatie"], ADRES_A)
        self.assertGreaterEqual(self.rit()[0], 1)
        self.assertEqual(self.vraag(), (0, 0))
        self.assertFalse(W._adresvragen(self.items, nu=NU, projecten={}))

    def test_zorg_nooit_aan_huis_tandarts_titel_krijgt_profieladres(self):
        self.profiles[0]["soort"] = "tandarts"
        self.profiles[0]["aan_huis"] = False
        a = self.voeg(item(titel="!! [PR] Tandarts thuis"))
        self.zorg()
        self.assertEqual(a["locatie"], ADRES_A)
        self.assertGreaterEqual(self.rit()[0], 1)
        self.assertEqual(self.vraag(), (0, 0))

    def test_zorg_huisbezoekzin_bij_onbekend_aan_huis_blijft_onbekend(self):
        a = self.voeg(item(omschrijving="Indien u een huisbezoek hebt aangevraagd, komen we aan huis."))
        self.zorg()
        self.assertEqual(a["locatie"], "")
        self.assertEqual(self.rit()[0], 0)
        self.assertEqual(self.vraag(), (0, 0))

    def test_zorg_mailplaats_huisbezoekzin_met_nooit_aan_huis_krijgt_rit(self):
        self.profiles[0]["aan_huis"] = False
        self.profiles.append(profiel("proef-b", "Praktijk Beta", ADRES_B))
        zin = "Indien u een huisbezoek hebt aangevraagd, komen we aan huis"
        mail = {"onderwerp": "Bevestiging afspraak kine op 21/10/2026 om 12:00",
                "tekst": "Beste Mo Voorbeeld. Uw afspraak is bevestigd. Waar: " + zin + " Toevoegen aan agenda",
                "ics": [], "linktijden": []}
        self.assertEqual(MA.zorg_herken(mail, self.profiles[0])["locatie"], "")
        self.assertFalse(MA.zorg_locatie_is_adres(zin))
        a = self.voeg(item(locatie=zin, _merk={W.ZORGMERK: "zorg|proef-a|2026-10-21T12:00:00+02:00"}))
        self.zorg()
        self.assertEqual(a["locatie"], ADRES_A)
        self.assertGreaterEqual(self.rit()[0], 1)
        self.assertEqual(self.vraag(), (0, 0))

    def test_zorg_nieuwe_mail_met_huisbezoekzin_krijgt_dezelfde_ronde_rit(self):
        self.profiles[0]["aan_huis"] = False
        onderwerp = "Bevestiging afspraak kine op 21/10/2026 om 12:00"
        mail = {"onderwerp": onderwerp,
                "tekst": "Beste Mo Voorbeeld. Uw afspraak is bevestigd. Waar: Indien u een huisbezoek hebt "
                         "aangevraagd, komen we aan huis Toevoegen aan agenda",
                "ics": [], "linktijden": []}
        z = MA.zorg_herken(mail, self.profiles[0])
        self.assertTrue(z["mehdi"])
        self.assertEqual(z["locatie"], "")
        regel = {"soort": "zorg", "sleutel": "zorg|proef-a|2026-10-21T12:00:00+02:00",
                 "status": "ontbreekt", "start": "2026-10-21T12:00:00+02:00",
                 "einde": "2026-10-21T12:30:00+02:00", "titel": "Kine controle",
                 "locatie": z["locatie"], "zorg": z, "bron_mailbox": "postvak@voorbeeld.test",
                 "bron_onderwerp": onderwerp, "bron_ontvangen": "2026-10-20T08:00:00+02:00",
                 "bron_message_id": "<proef@voorbeeld.test>"}

        def zet_nieuw(kal, body, _tok, **_opties):
            e = {**copy.deepcopy(body), "id": "uit-mail", "organizer": {"self": True},
                 "creator": {"email": W.WERKAGENDA}}
            self.writer.events[(kal, e["id"])] = copy.deepcopy(e)
            return e

        with patch.object(W, "_insert", zet_nieuw):
            resultaat = W.zorg_afspraken_zetten([regel], self.items, "proef", nu=NU, bijwerken_items=True)
        self.assertEqual(resultaat["gezet"], 1)
        self.assertEqual(resultaat["profielplaats"], 1)
        self.assertEqual(len(self.items), 1)
        self.assertEqual(self.items[0]["locatie"], ADRES_A)
        self.assertGreaterEqual(self.rit()[0], 1)
        self.assertEqual(self.vraag(), (0, 0))

    def test_zorg_profielplaatsmerk_gaat_voor_huisbezoekwoord(self):
        self.profiles[0]["aan_huis"] = False
        self.profiles.append(profiel("proef-b", "Praktijk Beta", ADRES_B))
        merk = W._zorg_profielmerk(self.profiles[0])
        a = self.voeg(item(omschrijving="Huisbezoek indien aangevraagd.",
                           _merk={W.ZORGPLAATSMERK: merk}))
        self.zorg()
        self.assertEqual(a["locatie"], ADRES_A)
        self.assertGreaterEqual(self.rit()[0], 1)
        self.assertEqual(self.vraag(), (0, 0))

    def test_zorg_praktijknaam_alleen_bewijst_nooit_aan_huis_niet(self):
        self.profiles[0]["aan_huis"] = False
        self.profiles.append(profiel("proef-b", "Praktijk Beta", ADRES_B))
        a = self.voeg(item(titel="!! [PR] Kine bij Praktijk Alpha huisbezoek"))
        self.zorg()
        self.assertEqual(a["locatie"], "")
        self.assertEqual(self.rit()[0], 0)
        self.assertEqual(self.vraag(), (0, 0))

    def test_zorg_nooit_aan_huis_houdt_gast_en_reeks_buiten_z1(self):
        self.profiles[0]["aan_huis"] = False
        zin = "Indien u een huisbezoek hebt aangevraagd, komen we aan huis."
        gast = self.voeg(item("nooit-gast", omschrijving=zin, deelnemers=["gast@voorbeeld.test"]))
        reeks = self.voeg(item("nooit-reeks", omschrijving=zin, _terugkerend=True))
        self.zorg()
        self.assertEqual((gast["locatie"], reeks["locatie"]), ("", ""))
        self.assertEqual(len(W.adres_vraag_noden(self.items, nu=NU)), 2)

    def test_zorg_handmatige_plaats_blijft(self):
        a = self.voeg(item(locatie=ADRES_B))
        self.zorg()
        self.assertEqual(a["locatie"], ADRES_B)
        self.assertFalse(self.writer.patches)

    def test_zorg_andere_patient_of_organisator_krijgt_geen_profielplaats(self):
        ander = self.voeg(item("ander", omschrijving="Patiënt: Lisa Proef."))
        organisator = self.voeg(item("organisator", _organisator_zelf=False,
                                   start="2026-10-21T15:00:00+02:00", einde="2026-10-21T15:30:00+02:00"))
        self.zorg()
        self.assertEqual((ander["locatie"], organisator["locatie"]), ("", ""))

    def test_zorg_mailzin_is_geen_adres(self):
        k = {"onderwerp": "Bevestiging afspraak kine op 21/10/2026 om 12:00",
             "tekst": "Beste Mo Voorbeeld. Uw afspraak is bevestigd. Waar: Huisbezoek bij patiënt thuis Toevoegen aan agenda",
             "ics": [], "linktijden": []}
        z = MA.zorg_herken(k, profiel())
        self.assertEqual(z["locatie"], "")

    def test_zorg_mailplaats_wint_van_gemerkte_profielplaats(self):
        a = self.voeg(item())
        self.zorg()
        sleutel = "zorg|proef-a|2026-10-21T12:00:00+02:00"
        mail = {"soort": "zorg", "sleutel": sleutel, "status": "gekoppeld",
                "google": f"{W.PRIVE_AGENDA}|{a['id']}", "start": a["start"], "einde": a["einde"],
                "titel": "Kine controle", "locatie": MAILADRES, "zorg": {"praktijk": "proef-a", "mehdi": True}}
        self.zorg_mail(mail)
        self.assertEqual(a["locatie"], MAILADRES)
        self.assertNotIn("agendawacht_zorgplaats", a["_merk"])
        hand = self.voeg(item("hand", locatie=ADRES_B))
        tweede = dict(mail, google=f"{W.PRIVE_AGENDA}|hand", sleutel="zorg|proef-a|hand")
        self.zorg_mail(tweede)
        self.assertEqual(hand["locatie"], ADRES_B)
        self.assertEqual(tweede["status"], "zorg_open")

    def test_zorg_werk_handmatige_plaats_met_mailafwijking_blijft_open(self):
        a = self.voeg(item("werk-hand", kalender=W.WERKAGENDA, titel="Kine controle", locatie=ADRES_B))
        sleutel = "zorg|proef-a|werk-hand"
        mail = {"soort": "zorg", "sleutel": sleutel, "status": "gekoppeld",
                "google": f"{W.WERKAGENDA}|{a['id']}", "start": a["start"], "einde": a["einde"],
                "titel": "Kine controle", "locatie": MAILADRES, "zorg": {"praktijk": "proef-a", "mehdi": True}}
        body = {"summary": "!! [PR] Kine controle", "location": MAILADRES,
                "extendedProperties": {"private": {W.ZORGMERK: sleutel}}}
        with patch.object(W, "_zorg_body", return_value=body):
            resultaat = self.zorg_mail(mail)
        self.assertEqual(resultaat["open"], 1)
        self.assertEqual(mail["status"], "zorg_open")
        self.assertEqual(self.writer.events[(W.PRIVE_AGENDA, a["id"])]["location"], ADRES_B)

    def zorg_mail(self, mail):
        return W.zorg_afspraken_zetten([mail], self.items, "proef", nu=NU)

    def test_zorg_gast_of_reeks_geeft_nood(self):
        gast = self.voeg(item("gast", deelnemers=["gast@voorbeeld.test"]))
        reeks = self.voeg(item("reeks", _terugkerend=True))
        self.zorg()
        self.assertEqual((gast["locatie"], reeks["locatie"]), ("", ""))
        self.assertEqual(self.vraag(), (0, 0))
        self.assertEqual(len(W.adres_vraag_noden(self.items, nu=NU)), 2)

    def test_buiten_zonder_schrijfrecht_geeft_stabiele_nood(self):
        a = self.voeg(item(titel="!! [PR] Buitenproef"))
        with patch.object(W, "_patch", side_effect=PermissionError):
            self.assertEqual(self.vraag(), (0, 0))
        eerste = W.adres_vraag_noden(self.items, nu=NU)
        self.assertEqual(len(eerste), 1)
        self.assertEqual(W.adres_vraag_noden(self.items, nu=NU), eerste)
        self.assertEqual(a["locatie"], "")

    def test_buiten_zonder_adres_vr_prive_lara_of_nood(self):
        prive = self.voeg(item("prive", titel="!! [PR] Buitenproef"))
        lara = self.voeg(item("lara", kalender=LARA, titel="!! [LA] Buitenproef",
                              start="2026-10-21T14:00:00+02:00", einde="2026-10-21T14:30:00+02:00"))
        self.assertEqual(self.vraag(), (2, 0), "test_buiten_zonder_adres_vr_prive_lara_of_nood")
        self.assertFalse(W.adres_vraag_noden(self.items, nu=NU))
        for a in (prive, lara):
            a["locatie"] = ADRES_A
        self.assertEqual(self.vraag(), (0, 2))
        self.assertFalse(prive["titel"].startswith("VR "))
        self.assertFalse(lara["titel"].startswith("VR "))
        self.assertEqual(W._toon(prive), "(privé)")

    def test_mailbron_tijdelijk_herstelt(self):
        with tempfile.TemporaryDirectory(dir=TMP) as d:
            with patch.object(MA, "DB", str(Path(d) / "mail.db")):
                mb = "postvak@voorbeeld.test"
                MA.leesstand_zet(mb, False, "tijdelijk", nu=NU, dekking="mislukt")
                self.assertIsNone(MA.mailbron_nood(mb, nu=NU))
                MA.leesstand_zet(mb, True, nu=NU + timedelta(minutes=30))
                self.assertEqual(MA.leesstand()[mb]["fout_rondes"], 0)

    def test_mailbron_blijvend_herkoppelen(self):
        with tempfile.TemporaryDirectory(dir=TMP) as d:
            with patch.object(MA, "DB", str(Path(d) / "mail.db")):
                mb = "postvak@voorbeeld.test"
                MA.leesstand_zet(mb, False, "onleesbaar", nu=NU, dekking="mislukt")
                self.assertIsNone(MA.mailbron_nood(mb, nu=NU))
                t = NU + timedelta(hours=2)
                MA.leesstand_zet(mb, False, "onleesbaar", nu=t, dekking="mislukt")
                nood = MA.mailbron_nood(mb, nu=t)
                self.assertEqual(nood["wie"], "mehdi", "test_mailbron_blijvend_herkoppelen")
                self.assertIn("ssh -t globaal 'docker exec -it appportal-app-post-1 "
                              "python oauth_koppel.py postvak@voorbeeld.test'", nood["tekst"])
                self.assertNotIn("<adres>", nood["tekst"])
                self.assertIn("Microsoft toont daarna een code; meld je daarmee aan.", nood["tekst"])
                self.assertIn("tijdelijk", nood["tekst"])
                self.assertEqual(MA.mailbron_nood(mb, nu=t + timedelta(hours=3)), nood)
                self.assertNotEqual(MA.mailbron_nood(mb, nu=t + timedelta(hours=24)), nood)

    def test_mailbron_succes_wist_foutreeks(self):
        with tempfile.TemporaryDirectory(dir=TMP) as d:
            with patch.object(MA, "DB", str(Path(d) / "mail.db")):
                mb = "postvak@voorbeeld.test"
                MA.leesstand_zet(mb, False, "onleesbaar", nu=NU, dekking="mislukt")
                self.assertEqual(MA.mailbron_nood(mb, afhankelijk=True, nu=NU)["wie"], "mehdi")
                MA.leesstand_zet(mb, True, nu=NU + timedelta(minutes=1))
                self.assertIsNone(MA.mailbron_nood(mb, afhankelijk=True, nu=NU + timedelta(minutes=1)))
                self.assertEqual(MA.leesstand()[mb]["laatste_nood"], "")

    def test_mailbron_zorg_binnen_24_uur_meteen(self):
        mb = next(iter(MA.PRIVE))
        a = self.voeg(item(start="2026-10-21T08:00:00+02:00", einde="2026-10-21T08:30:00+02:00"))
        self.assertTrue(W._mailbron_zorg_afhankelijk(mb, self.items, nu=NU))
        with tempfile.TemporaryDirectory(dir=TMP) as d:
            with patch.object(MA, "DB", str(Path(d) / "mail.db")):
                MA.leesstand_zet(mb, False, "onleesbaar", nu=NU, dekking="mislukt")
                self.assertEqual(MA.mailbron_nood(mb, afhankelijk=W._mailbron_zorg_afhankelijk(mb, self.items, NU),
                                                   nu=NU)["wie"], "mehdi")
        a["start"] = "2026-10-22T12:00:00+02:00"
        self.assertFalse(W._mailbron_zorg_afhankelijk(mb, self.items, nu=NU))
        a["start"], a["kalender"] = "2026-10-21T08:00:00+02:00", LARA
        self.assertFalse(W._mailbron_zorg_afhankelijk(mb, self.items, nu=NU))


if __name__ == "__main__":
    unittest.main(verbosity=2)
