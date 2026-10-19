"""Vaste-klokproeven voor de twee planregels van 19-10-2026, zonder netwerk of echte gegevens."""
import copy
import inspect
import json
import os
import sys
import unittest
from contextlib import ExitStack
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

os.environ["BELLEN_UIT"] = "1"
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W  # noqa: E402
import dagcontrole as D  # noqa: E402

NU = datetime.fromisoformat("2026-10-19T09:00:00+02:00")
DAG = "2026-10-22"
PLAATSEN = ("Proefstraat 1, 0000 Teststad", "Oefenlaan 2, 0000 Teststad",
            "Modelweg 3, 0000 Teststad")


def tijd(uur):
    return f"{DAG}T{uur}:00+02:00"


def afspraak(eid="a", titel="!! [HA-KB] scheurenonderzoek", begin="10:00", einde="11:00",
             kalender=None, locatie=None, **extra):
    a = {"id": eid, "kalender": kalender or W.WERKAGENDA, "titel": titel, "start": tijd(begin),
         "einde": tijd(einde), "locatie": locatie if locatie is not None else PLAATSEN[0],
         "omschrijving": "Proefafspraak", "maker": W.WERKAGENDA, "deelnemers": [],
         "_agendagasten": [], "_organisator_zelf": True, "_merk": {}, "_reminders": {},
         "_terugkerend": False, "hele_dag": False}
    a.update(extra)
    return a


def google_event(a):
    return {"id": a["id"], "summary": a["titel"], "start": {"dateTime": a["start"]},
            "end": {"dateTime": a["einde"]}, "description": a.get("omschrijving") or "",
            "location": a.get("locatie") or "", "extendedProperties": {"private": copy.deepcopy(a.get("_merk") or {})},
            "attendees": [{"email": e} for e in a.get("deelnemers") or []]}


class ProefSchrijven:
    def __init__(self, items):
        self.items = items
        self.events = {a["id"]: google_event(a) for a in items}
        self.patches = []
        self.inserts = []

    def event(self, a, _tok):
        return copy.deepcopy(self.events[a["id"]])

    def patch(self, a, body, _tok, **_kwargs):
        self.patches.append((a["id"], copy.deepcopy(body)))
        ev = self.events[a["id"]]
        ev.update(copy.deepcopy(body))
        for sleutel, veld in (("summary", "titel"), ("description", "omschrijving")):
            if sleutel in body:
                a[veld] = body[sleutel]
        for sleutel, veld in (("start", "start"), ("end", "einde")):
            if sleutel in body:
                a[veld] = body[sleutel]["dateTime"]
        if "extendedProperties" in body:
            a["_merk"] = copy.deepcopy(body["extendedProperties"]["private"])
        if "reminders" in body:
            a["_reminders"] = copy.deepcopy(body["reminders"])
        if "colorId" in body:
            a["_kleur"] = body["colorId"] or ""

    def insert(self, kalender, body, _tok, **_kwargs):
        self.inserts.append(copy.deepcopy(body))
        a = {"id": body["id"], "kalender": kalender, "titel": body["summary"],
             "start": body["start"]["dateTime"], "einde": body["end"]["dateTime"],
             "omschrijving": body["description"], "locatie": "", "deelnemers": [],
             "_merk": copy.deepcopy(body["extendedProperties"]["private"]),
             "_reminders": copy.deepcopy(body["reminders"]), "_kleur": body.get("colorId") or ""}
        self.items.append(a)
        self.events[a["id"]] = google_event(a)
        return copy.deepcopy(self.events[a["id"]])


class Planregels(unittest.TestCase):
    def rit_zetten(self, items):
        # HEAD had nog geen nu-parameter. De terugproef geeft ook die versie dezelfde vaste klok.
        if "nu" in inspect.signature(W.reistijd_zetten).parameters:
            return W.reistijd_zetten(items, nu=NU)
        with patch.object(W, "nu_lokaal", lambda: NU):
            return W.reistijd_zetten(items)

    def p1(self, items):
        schrijver = ProefSchrijven(items)
        stapel = ExitStack()
        self.addCleanup(stapel.close)
        stapel.enter_context(patch.object(W, "_event", schrijver.event))
        stapel.enter_context(patch.object(W, "_patch", schrijver.patch))
        stapel.enter_context(patch.object(W.agenda, "_toegang", lambda: "proef"))
        stapel.enter_context(patch.object(W, "mag_schrijven", lambda _kal: True))
        stapel.enter_context(patch.object(W.projectadressen, "index", lambda: {}))
        stapel.enter_context(patch.object(W, "zoom_zonder_wachtwoord", lambda *_a: []))
        stapel.enter_context(patch.object(W, "zoom_zonder_wachtkamer", lambda *_a: []))
        return schrijver

    def p2(self, items):
        schrijver = ProefSchrijven(items)
        stapel = ExitStack()
        self.addCleanup(stapel.close)
        stapel.enter_context(patch.object(W, "_insert", schrijver.insert))
        stapel.enter_context(patch.object(W, "_patch", schrijver.patch))
        stapel.enter_context(patch.object(W, "_event", schrijver.event))
        stapel.enter_context(patch.object(W.agenda, "_toegang", lambda: "proef"))
        stapel.enter_context(patch.object(W, "_cache_laden", lambda: {}))
        stapel.enter_context(patch.object(W, "_cache_bewaren", lambda _cache: None))
        stapel.enter_context(patch.object(W.projectadressen, "index", lambda: {}))
        stapel.enter_context(patch.object(W, "plek_zoeken", lambda _tekst: (None, None)))
        stapel.enter_context(patch.object(W, "vaste_plek", lambda _titel: (None, None)))
        stapel.enter_context(patch.object(W, "lara_vakantiedagen", lambda: set()))
        stapel.enter_context(patch.object(W, "geen_auto_dagen", lambda: set()))
        stapel.enter_context(patch.object(W, "coord", lambda adres, _cache: {
            W.THUIS: (0, 0), PLAATSEN[0]: (1, 1), PLAATSEN[1]: (2, 2), PLAATSEN[2]: (3, 3)}.get(adres)))
        stapel.enter_context(patch.object(W, "ritlabel", lambda adres, _ander: {
            W.THUIS: "thuis", PLAATSEN[0]: "plek A", PLAATSEN[1]: "plek B", PLAATSEN[2]: "plek C"}[adres]))
        stapel.enter_context(patch.object(W, "rijtijd_min", lambda van, naar, _vertrek: (
            60 if van == (1, 1) and naar == (2, 2) else
            85 if van == (2, 2) and naar == (3, 3) else 20, "proef")))
        stapel.enter_context(patch.object(W, "kleur_gewenst", lambda *_a: "11"))
        stapel.enter_context(patch.object(W, "_eigen_rit_weg", lambda *_a: False))
        W.ONGELEZEN.clear()
        return schrijver

    def test_master_en_werkwijze(self):
        master = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text())
        werkwijze = (HIER / "werkwijze" / "agenda-wacht.md").read_text()
        self.assertEqual(master["versie"], "5.16")
        self.assertEqual(master["duur_ter_plaatse"]["trefwoorden"], ["barst", "scheur"])
        self.assertEqual(master["duur_ter_plaatse"]["minuten"], 120)
        self.assertTrue(any("barsten en scheuren voorzie ter plaatse altijd 2 uur" in b["wat"]
                            for b in master["beslissingen"]))
        self.assertIn("Aanvulling v8.20 (19-10-2026)", werkwijze)
        self.assertIn("Versie 8.13", werkwijze)

    def test_eigen_scheuren_wordt_twee_uur_en_tweede_ronde_stil(self):
        a = afspraak(titel="!! [HA-KB] SCHEURENONDERZOEK")
        schrijver = self.p1([a])
        gezet, open_ = W.duur_ter_plaatse_zetten([a], nu=NU)
        self.assertEqual((gezet, open_), (1, []))
        self.assertEqual(a["start"], tijd("10:00"))
        self.assertEqual(a["einde"], tijd("12:00"))
        self.assertEqual(a["_merk"]["agendawacht_duur"], "120")
        self.assertEqual(a["omschrijving"].count("Duur 2 uur: vaste regel"), 1)
        self.assertIn("19-10-2026", a["omschrijving"])
        self.assertNotIn("summary", schrijver.patches[0][1])
        self.assertEqual(W.duur_ter_plaatse_zetten([a], nu=NU), (0, []))
        self.assertEqual(len(schrijver.patches), 1)

    def test_botsing_vraagt_vr_en_sluit_na_verlenging(self):
        a = afspraak()
        b = afspraak("b", "!! [HA-KB] andere proef", "11:30", "12:30", kalender=W.PRIVE_AGENDA)
        schrijver = self.p1([a, b])
        gezet, open_ = W.duur_ter_plaatse_zetten([a, b], nu=NU)
        self.assertEqual(gezet, 0)
        self.assertTrue(any("VRAAG" in regel for regel in open_))
        self.assertEqual(W.vragen_in_agenda([a, b], nu=NU), (1, 0))
        self.assertTrue(a["titel"].startswith("VR "))
        self.assertIn("Barsten en scheuren ter plaatse", a["omschrijving"])
        self.assertNotIn("end", schrijver.patches[0][1])
        a["einde"] = tijd("12:00")
        schrijver.events[a["id"]]["end"] = {"dateTime": a["einde"]}
        self.assertEqual(W.vragen_in_agenda([a, b], nu=NU), (1, 0))
        self.assertNotIn("Barsten en scheuren ter plaatse", a["omschrijving"])
        b["start"], b["einde"] = tijd("13:00"), tijd("14:00")
        self.assertEqual(W.vragen_in_agenda([a, b], nu=NU), (0, 1))
        self.assertFalse(a["titel"].startswith("VR "))

    def test_gast_reeks_en_geen_schrijfrecht_geven_bevinding(self):
        gast = afspraak(deelnemers=["gast@voorbeeld.test"])
        reeks = afspraak("reeks", _reeks="serie")
        schrijver = self.p1([gast, reeks])
        gezet, regels = W.duur_ter_plaatse_zetten([gast, reeks], nu=NU)
        self.assertEqual(gezet, 0)
        self.assertEqual(len(regels), 2)
        self.assertTrue(all("NOOD" in r for r in regels))
        self.assertEqual(schrijver.patches, [])
        self.assertEqual(gast["titel"], "!! [HA-KB] scheurenonderzoek")
        eigen = afspraak("geen-recht")
        with patch.object(W, "mag_schrijven", lambda _kal: False):
            self.assertIn("NOOD", W.duur_ter_plaatse_zetten([eigen], nu=NU)[1][0])

    def test_geen_trefwoord_online_en_bewust_ingekort_blijven(self):
        zonder = afspraak(titel="!! [HA-KB] gewone inspectie")
        online = afspraak("online", "[HA-KO] scheuren", locatie="https://meeting.voorbeeld.test")
        ingekort = afspraak("ingekort", _merk={"agendawacht_duur": "120"})
        schrijver = self.p1([zonder, online, ingekort])
        self.assertEqual(W.duur_ter_plaatse_zetten([zonder, online, ingekort], nu=NU), (0, []))
        self.assertEqual(schrijver.patches, [])

    def test_woordbegin_in_plaats_of_omschrijving_en_eigen_rit_telt_niet_als_botsing(self):
        locatie = afspraak("loc", "!! [HA-KB] inspectie", locatie="Scheurenproject, " + PLAATSEN[0])
        tekst = afspraak("tekst", "!! [HA-KB] inspectie", "13:00", "14:00", locatie=PLAATSEN[1],
                         omschrijving="Barsten in het testpaneel")
        rit = {"id": "ritproef", "kalender": W.WERKAGENDA, "titel": "🚗 Reistijd: plek A → plek B",
               "start": tijd("11:00"), "einde": tijd("11:20"),
               "omschrijving": "Reistijd voor: proef (20 min, OSRM)",
               "_merk": {"agendawacht_rit": "ritproef"}}
        items = [locatie, tekst, rit]
        schrijver = self.p1(items)
        self.assertEqual(W.duur_ter_plaatse_zetten(items, nu=NU), (2, []))
        self.assertEqual((locatie["einde"], tekst["einde"]), (tijd("12:00"), tijd("15:00")))
        self.assertEqual(len(schrijver.patches), 2)

    def test_dagmarkering_blokkeert_verlenging(self):
        a = afspraak()
        marker = afspraak("marker", "Geen afspraken", begin="00:00", einde="00:00", hele_dag=True)
        marker["start"], marker["einde"] = DAG, "2026-10-23"
        schrijver = self.p1([a, marker])
        self.assertEqual(W.duur_ter_plaatse_zetten([a, marker], nu=NU)[0], 0)
        self.assertEqual(schrijver.patches, [])

    def test_keten_blokkeert_beide_gaten_en_belt_op_vertrek(self):
        tweede_kalender = W.PRIVE_AGENDA
        a = afspraak("a", "!! [HA-KB] proef A", "12:30", "13:00", locatie=PLAATSEN[0])
        b = afspraak("b", "!! [HA-KB] proef B", "14:15", "16:15", locatie=PLAATSEN[1])
        c = afspraak("c", "!! [PR] proef C", "17:45", "18:15", kalender=tweede_kalender, locatie=PLAATSEN[2])
        items = [a, b, c]
        schrijver = self.p2(items)
        gemaakt, _al, _geen, fouten, _regels = self.rit_zetten(items)
        self.assertEqual(fouten, 0)
        self.assertEqual(gemaakt, 4)
        self.assertTrue(all(body["extendedProperties"]["private"]["agendawacht_rit"] == body["id"]
                            for body in schrijver.inserts))
        heen_a = next(x for x in items if "Reistijd voor: " + a["titel"] in x.get("omschrijving", ""))
        heen_b = next(x for x in items if "Reistijd voor: " + b["titel"] in x.get("omschrijving", ""))
        heen_c = next(x for x in items if "Reistijd voor: " + c["titel"] in x.get("omschrijving", ""))
        terug_c = next(x for x in items if "Reistijd na: " + c["titel"] in x.get("omschrijving", ""))
        self.assertEqual(heen_a["start"], tijd("12:10"))  # thuis blijft vrij tot de echte vertrekvoorbereiding
        self.assertEqual((heen_b["start"], heen_b["einde"]), (tijd("13:00"), tijd("14:15")))
        self.assertEqual((heen_c["start"], heen_c["einde"]), (tijd("16:15"), tijd("17:45")))
        self.assertEqual(heen_c["kalender"], tweede_kalender)
        self.assertEqual(terug_c["start"], c["einde"])
        self.assertEqual(heen_b["_merk"]["agendawacht_vertrek"], tijd("13:15"))
        self.assertEqual(heen_c["_merk"]["agendawacht_vertrek"], tijd("16:20"))
        self.assertIn("15 min wachten", heen_b["omschrijving"])
        self.assertIn("5 min wachten", heen_c["omschrijving"])
        self.assertEqual(heen_b["_reminders"]["overrides"], [])
        self.assertEqual(b["_reminders"]["overrides"], [{"method": "popup", "minutes": 65}])
        rooster = W.belrooster(items, DAG)
        bel_b = next(r for r in rooster if ":b:" in r["sleutel"])
        self.assertEqual(bel_b["tijd"], tijd("13:10"))
        oude_lezing = copy.deepcopy(items)
        oude_rit = next(x for x in oude_lezing if x.get("id") == heen_b["id"])
        oude_rit["_merk"]["agendawacht_vertrek"] = tijd("13:00")
        goed, weg = W._nakijken([bel_b], tok="proef", ritten=oude_lezing)
        self.assertEqual((weg, goed[0]["tijd"]), (0, tijd("13:10")))
        oud_aantal = len(schrijver.patches)
        self.assertEqual(self.rit_zetten(items)[0], 0)
        self.assertEqual(len(schrijver.patches), oud_aantal)

    def test_langs_huis_houdt_tijd_thuis_vrij(self):
        a = afspraak("a", "!! [HA-KB] proef A", "12:30", "13:00", locatie=PLAATSEN[0])
        b = afspraak("b", "!! [HA-KB] proef B", "14:15", "15:00", locatie=PLAATSEN[1])
        handmatig = {"id": "hand", "kalender": W.PRIVE_AGENDA, "titel": "🚗 Reistijd: plek A → thuis",
                     "start": tijd("13:00"), "einde": tijd("13:20"), "omschrijving": "handmatig", "locatie": ""}
        items = [a, b, handmatig]
        schrijver = self.p2(items)
        self.assertEqual(self.rit_zetten(items)[3], 0)
        heen_b = next(x for x in items if "Reistijd voor: " + b["titel"] in x.get("omschrijving", ""))
        self.assertEqual(heen_b["start"], tijd("13:55"))
        self.assertNotIn("agendawacht_keten_vanaf", heen_b["_merk"])
        self.assertEqual(handmatig["start"], tijd("13:00"))
        self.assertFalse(any(eid == "hand" for eid, _body in schrijver.patches))

    def test_bestaande_ketenrit_schuift_eenmaal_naar_vorig_einde(self):
        a = afspraak("a", "!! [HA-KB] proef A", "12:30", "13:00", locatie=PLAATSEN[0])
        b = afspraak("b", "!! [HA-KB] proef B", "14:15", "15:00", locatie=PLAATSEN[1])
        items = [a, b]
        schrijver = self.p2(items)
        self.assertEqual(self.rit_zetten(items)[3], 0)
        rit = next(x for x in items if "Reistijd voor: " + b["titel"] in x.get("omschrijving", ""))
        rit["start"] = tijd("13:15")
        rit["_merk"].pop("agendawacht_keten_vanaf", None)
        rit["omschrijving"] = rit["omschrijving"].split(" (60 min rijden", 1)[0]
        rit["_reminders"] = {"useDefault": False, "overrides": [{"method": "popup", "minutes": 5}]}
        schrijver.events[rit["id"]] = google_event(rit)
        voor = len(schrijver.patches)
        self.assertEqual(self.rit_zetten(items)[3], 0)
        self.assertEqual(rit["start"], tijd("13:00"))
        self.assertEqual(rit["_merk"]["agendawacht_vertrek"], tijd("13:15"))
        self.assertEqual(len([p for p in schrijver.patches[voor:] if p[0] == rit["id"]]), 1)
        na = len(schrijver.patches)
        self.assertEqual(self.rit_zetten(items)[0], 0)
        self.assertEqual(len(schrijver.patches), na)

    def test_ketenblok_begint_na_getimede_tussenafspraken_op_alle_agendas(self):
        a = afspraak("a", "!! [HA-KB] proef A", "12:30", "13:00", locatie=PLAATSEN[0])
        b = afspraak("b", "!! [HA-KB] proef B", "14:15", "15:00", locatie=PLAATSEN[1])
        werk = afspraak("werk", "[HA-IN] intern overleg", "13:02", "13:10", locatie="")
        lara = afspraak("lara", "[LA-IN] taak", "13:12", "13:20", kalender=next(
            k for k, v in W.KALENDERS.items() if v == "Lara"), locatie="")
        zonder_adres = afspraak("zonder", "!! [HA-KB] zonder adres", "13:20", "13:25",
                                kalender=W.PRIVE_AGENDA, locatie="")
        afgezegd = afspraak("afgezegd", "[HA-IN] geannuleerd", "13:25", "13:29", status="cancelled")
        eigen_rit = {"id": "eigen", "kalender": W.PRIVE_AGENDA, "titel": "🚗 Reistijd: proef",
                     "start": tijd("13:25"), "einde": tijd("13:29"),
                     "omschrijving": "Reistijd voor: proef (OSRM)", "_merk": {"agendawacht_rit": "eigen"}}
        items = [a, b, werk, lara, zonder_adres, afgezegd, eigen_rit]
        schrijver = self.p2(items)
        basis = W.rijtijd_min

        def rijtijd(van, naar, vertrek):
            return (45, "proef") if van == (1, 1) and naar == (2, 2) else basis(van, naar, vertrek)

        with patch.object(W, "rijtijd_min", rijtijd):
            self.assertEqual(self.rit_zetten(items)[3], 0)
            heen_b = next(x for x in items if "Reistijd voor: " + b["titel"] in x.get("omschrijving", ""))
            self.assertEqual((heen_b["start"], heen_b["einde"]), (tijd("13:25"), tijd("14:15")))
            self.assertEqual(heen_b["_merk"]["agendawacht_vertrek"], tijd("13:30"))
            aantal = len(schrijver.patches)
            self.assertEqual(self.rit_zetten(items)[0], 0)
            self.assertEqual(len(schrijver.patches), aantal, schrijver.patches[aantal:])

    def test_tussenafspraak_na_vertrek_geeft_te_krap_zonder_ritoverlap(self):
        a = afspraak("a", "!! [HA-KB] proef A", "12:30", "13:00", locatie=PLAATSEN[0])
        b = afspraak("b", "!! [HA-KB] proef B", "14:15", "15:00", locatie=PLAATSEN[1])
        overleg = afspraak("overleg", "[HA-IN] intern overleg", "13:10", "13:40", locatie="")
        items = [a, b, overleg]
        self.p2(items)
        basis = W.rijtijd_min

        def rijtijd(van, naar, vertrek):
            return (45, "proef") if van == (1, 1) and naar == (2, 2) else basis(van, naar, vertrek)

        with patch.object(W, "rijtijd_min", rijtijd), patch.object(W, "BUFFER_MIN", 0):
            _gemaakt, _al, _geen, fouten, regels = self.rit_zetten(items)
        self.assertEqual(fouten, 0)
        heen_b = next(x for x in items if "Reistijd voor: " + b["titel"] in x.get("omschrijving", ""))
        self.assertTrue(any("TE KRAP" in regel for regel in regels), regels)
        self.assertGreaterEqual(heen_b["start"], overleg["einde"])
        self.assertEqual(heen_b["_merk"]["agendawacht_vertrek"], heen_b["start"])
        self.assertGreater(heen_b["einde"], b["start"])

    def test_dagcontrole_meldt_boekbaar_gat_in_gemerkte_keten(self):
        a = afspraak("a", "!! [HA-KB] proef A", "12:30", "13:00")
        b = afspraak("b", "!! [PR] proef B", "14:15", "16:15", kalender=W.PRIVE_AGENDA, locatie=PLAATSEN[1])
        rit = {"id": "rittest", "kalender": W.PRIVE_AGENDA, "titel": "🚗 Reistijd: plek A → plek B",
               "start": tijd("13:15"), "einde": tijd("14:15"),
               "omschrijving": "Reistijd voor: !! [HA-KB] proef B (60 min, OSRM)",
               "_merk": {"agendawacht_rit": "rittest", "agendawacht_vertrek": tijd("13:15"),
                         "agendawacht_keten_vanaf": tijd("13:00")}}
        bevindingen = D.dagcontrole([a, b, rit], DAG)
        self.assertTrue(any(x["soort"] == "boekbaar_gat_in_keten" and "13:00" in x["tekst"] for x in bevindingen))


if __name__ == "__main__":
    unittest.main(verbosity=2)
