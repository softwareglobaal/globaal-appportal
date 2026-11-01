#!/usr/bin/env python3
"""De indeling van de foto's op de VM (koppelingen/fotoindeling.py, T-0120 FOTO-4 en FOTO-5), zonder netwerk.

Alleen verzonnen plekken, nummers en afspraken. Drie proefdagen in de vorm van de meting 29-10 tot 31-10 (2, 10 en 10
werkfoto's): een afspraak met adres, een verblijf "auto bij project", een afspraak van een tweede firma en een
werkkandidaat bij een projectplek. Privé, mensen en scherm staan nooit met id, tijd of plaats in de uitvoer.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER / "koppelingen"))
SPEC = importlib.util.spec_from_file_location("fotoindeling_proef", RUNNER / "koppelingen" / "fotoindeling.py")
FI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FI)

P1 = {"firma": "HARC", "nummer": "9001", "naam": "Proefwoning Alfa", "lat": 50.1000, "lon": 4.1000,
      "link": "https://ha-projecten.globaal.be/project/9001"}
P2 = {"firma": "HARC", "nummer": "9002", "naam": "Proefwoning Beta", "lat": 50.2000, "lon": 4.2000,
      "link": "https://www.dropbox.com/s/gedeeld-mag-niet"}
PRIVE = (50.3000, 4.3000)          # een verzonnen plek ver van elk project
DERDE = (50.4000, 4.4000)          # het adres van een afspraak van een tweede firma (geen projectplek)


def foto(fid, uur, lat=None, lon=None, mensen=False, scherm=False, app=False, video=False, dag="2026-10-29"):
    return {"id": fid, "utc": f"{dag}T{uur}:00+01:00", "lat": lat, "lon": lon, "video": video, "scherm": scherm,
            "app": app, "mensen": mensen}


def bij(plek, meter=40):
    """Een punt op ongeveer `meter` noordelijk van de plek."""
    return plek[0] + meter / 111000, plek[1]


def afspraak(firma, nummer, dag, van, tot, plek, titel="Proefbezoek"):
    return {"firma": firma, "nummer": nummer, "titel": titel, "start": FI._tijd(f"{dag}T{van}:00+01:00"),
            "einde": FI._tijd(f"{dag}T{tot}:00+01:00"), "lat": plek[0] if plek else None, "lon": plek[1] if plek else None}


def dag_29():
    a = bij((P1["lat"], P1["lon"]))
    fotos = [foto("w1", "10:15", *a), foto("w2", "10:20", *a)]
    fotos += [foto(f"p{i}", "18:00", *PRIVE) for i in range(12)]
    fotos += [foto("portret", "19:00", *PRIVE, mensen=True), foto("s1", "10:16", *a, scherm=True), foto("app1", "10:17", app=True)]
    return fotos, [afspraak("HARC", "9001", "2026-10-29", "10:00", "11:00", (P1["lat"], P1["lon"]))], []


def dag_30():
    a = bij((P2["lat"], P2["lon"]), 60)
    fotos = [foto(f"a{i}", f"14:{5 + 3 * i:02d}", *a, dag="2026-10-30") for i in range(10)]
    fotos += [foto("gezicht", "20:00", *PRIVE, mensen=True, dag="2026-10-30")] + [foto(f"q{i}", "21:00", *PRIVE, dag="2026-10-30") for i in range(3)]
    verblijf = {"firma": "HARC", "nummer": "9002", "naam": "Proefwoning Beta", "aankomst": FI._tijd("2026-10-30T14:00:00+01:00"),
                "vertrek": FI._tijd("2026-10-30T15:00:00+01:00"), "lat": P2["lat"], "lon": P2["lon"]}
    return fotos, [], [verblijf]


def dag_31():
    d, k = bij(DERDE), bij((P1["lat"], P1["lon"]), 90)
    fotos = [foto(f"t{i}", f"09:{10 + 5 * i:02d}", *d, dag="2026-10-31") for i in range(5)]
    fotos += [foto(f"k{i}", f"16:{i:02d}", *k, dag="2026-10-31") for i in range(5)]
    fotos += [foto("zonder", "20:00", dag="2026-10-31")]
    return fotos, [afspraak("TKNB", "47001", "2026-10-31", "09:00", "12:00", DERDE, "Proefbezoek tweede firma")], []


class Regels(unittest.TestCase):
    def werk(self, ind):
        return sum(g["aantal"] for g in ind["werf"] + ind["kandidaat"])

    def test_drie_proefdagen_geven_2_10_en_10_werkfotos(self):
        uit = []
        for dag, maak in (("2026-10-29", dag_29), ("2026-10-30", dag_30), ("2026-10-31", dag_31)):
            fotos, afspraken, verblijven = maak()
            uit.append(FI.indeel(dag, fotos, [P1, P2], afspraken, verblijven))
        self.assertEqual([self.werk(i) for i in uit], [2, 10, 10])
        a29, a30, a31 = uit
        self.assertEqual((a29["werf"][0]["anker"]["soort"], a29["werf"][0]["naam"]), ("afspraak", "Proefwoning Alfa"))
        self.assertEqual(a30["werf"][0]["anker"]["soort"], "auto bij project")
        self.assertEqual([(g["firma"], g["nummer"], g["soort"]) for g in a31["werf"] + a31["kandidaat"]],
                         [("TKNB", "47001", "zeker"), ("HARC", "9001", "kandidaat")])
        self.assertEqual(a29["telling"], {"prive": 12, "mensen": 1, "overig": 2, "onbeslist": 0})
        self.assertEqual(a31["telling"]["onbeslist"], 1)

    def test_groot_gezicht_buiten_werk_is_privé_en_staat_nergens_met_plaats(self):
        f, a, v = dag_30()
        ind = FI.indeel("2026-10-30", f, [P1, P2], a, v)
        self.assertEqual(ind["telling"]["mensen"], 1)
        tekst = json.dumps(ind)
        for x in ("gezicht", '"q0"', str(PRIVE[0]), "21:00", "20:00"):
            self.assertNotIn(x, tekst)

    def test_mensen_binnen_werk_geteld_nooit_voorvertoning(self):
        a = bij((P1["lat"], P1["lon"]))
        fotos = [foto("w1", "10:15", *a), foto("mens", "10:20", *a, mensen=True), foto("onbekend", "10:25", *a, mensen=None),
                 foto("film", "10:30", *a, video=True)]
        ind = FI.indeel("2026-10-29", fotos, [P1], [afspraak("HARC", "9001", "2026-10-29", "10:00", "11:00", (P1["lat"], P1["lon"]))], [])
        g = ind["werf"][0]
        self.assertEqual((g["aantal"], g["met_mensen"], g["video"]), (4, 1, 1))
        self.assertEqual([f["id"] for f in g["fotos"] if f["voorbeeld"]], ["w1"])

    def test_scherm_bij_een_project_is_geen_werk(self):
        a = bij((P1["lat"], P1["lon"]))
        ind = FI.indeel("2026-10-29", [foto("s", "10:15", *a, scherm=True)], [P1],
                        [afspraak("HARC", "9001", "2026-10-29", "10:00", "11:00", (P1["lat"], P1["lon"]))], [])
        self.assertEqual((ind["werf"], ind["telling"]["overig"]), ([], 1))

    def test_zonder_gps_tussen_twee_werkfotos_hoort_bij_de_groep(self):
        a = bij((P1["lat"], P1["lon"]))
        fotos = [foto("w1", "10:10", *a), foto("los", "10:20"), foto("w2", "10:30", *a), foto("na", "13:00")]
        ind = FI.indeel("2026-10-29", fotos, [P1], [afspraak("HARC", "9001", "2026-10-29", "10:00", "11:00", None)], [])
        self.assertEqual(ind["werf"], [], "een afspraak zonder plaats en zonder projectplek koppelt niets")
        ind = FI.indeel("2026-10-29", fotos, [P1], FI.met_plaats([afspraak("HARC", "9001", "2026-10-29", "10:00", "11:00", None)], [P1]), [])
        g = ind["werf"][0]
        self.assertEqual((g["aantal"], g["zonder_plaats"], ind["telling"]["onbeslist"]), (3, 1, 1))
        self.assertEqual([f["voorbeeld"] for f in g["fotos"]], [True, False, True])

    def test_buiten_straal_of_venster_is_geen_werf(self):
        ver = bij((P1["lat"], P1["lon"]), 200)
        ind = FI.indeel("2026-10-29", [foto("ver", "10:15", *ver), foto("laat", "12:31", *bij((P1["lat"], P1["lon"])))], [],
                        [afspraak("HARC", "9001", "2026-10-29", "10:00", "11:00", (P1["lat"], P1["lon"]))], [])
        self.assertEqual((ind["werf"], ind["telling"]["prive"]), ([], 2))

    def test_alleen_veilige_links(self):
        f, a, v = dag_30()
        ind = FI.indeel("2026-10-30", f, [P1, P2], a, v)
        self.assertEqual(ind["werf"][0]["link"], "", "geen gedeelde Dropbox-link (VOL-19)")
        f, a, v = dag_29()
        self.assertTrue(FI.indeel("2026-10-29", f, [P1, P2], a, v)["werf"][0]["link"].startswith("https://ha-projecten.globaal.be/"))

    def test_register_is_uitbreidbaar_met_een_tweede_firma(self):
        tweede = {"firma": "TKNB", "nummer": "47002", "naam": "Proefdossier Gamma", "lat": 50.5, "lon": 4.5, "link": ""}
        with patch.object(FI, "PLEKBRONNEN", (lambda: [P1, P2], lambda: [tweede, dict(P1, naam="dubbel")])):
            plekken = FI.projectplekken()
        self.assertEqual([(p["firma"], p["nummer"], p["naam"]) for p in plekken],
                         [("HARC", "9001", "Proefwoning Alfa"), ("HARC", "9002", "Proefwoning Beta"), ("TKNB", "47002", "Proefdossier Gamma")])
        ind = FI.indeel("2026-10-29", [foto("g", "10:00", *bij((50.5, 4.5)))], plekken, [], [])
        self.assertEqual([(g["firma"], g["soort"]) for g in ind["kandidaat"]], [("TKNB", "kandidaat")])


class Ronde(unittest.TestCase):
    """deel_in tegen een nep-bord en een nep-Locatie-dashboard, in een eigen datamap."""

    def setUp(self):
        self.map = tempfile.TemporaryDirectory()
        self.addCleanup(self.map.cleanup)
        self.oud = (FI.UIT, FI.VOORBEELD, FI.AGENDA_ADRESSEN)
        FI.UIT, FI.VOORBEELD = os.path.join(self.map.name, "fotoindeling"), os.path.join(self.map.name, "fotovoorbeeld")
        FI.AGENDA_ADRESSEN = os.path.join(self.map.name, "agenda-adressen.json")
        Path(FI.AGENDA_ADRESSEN).write_text(json.dumps({"proefstraat 1, 9999 proefdorp": [P1["lat"], P1["lon"]]}))
        self.addCleanup(lambda: setattr(FI, "UIT", self.oud[0]) or setattr(FI, "VOORBEELD", self.oud[1])
                        or setattr(FI, "AGENDA_ADRESSEN", self.oud[2]))
        self.bak, self.gepost, self.verslag = [], [], []
        self.context = {"dag": "2026-10-29", "bronbeleid": "1", "verblijven": []}

        def db_lees(sql, args=()):
            if "soort = 'fotometadata'" in sql and "DISTINCT" in sql:
                return [{"sleutel": s} for s in sorted({json.loads(r["inhoud"])["datum"] for r in self.bak if r["soort"] == "fotometadata"})]
            soort = "fotometadata" if "fotometadata" in sql else "afspraak"
            return [r for r in self.bak if r["soort"] == soort and (soort != "fotometadata" or r["uniek"].startswith(args[-1].rstrip("%")))]
        self.patches = [patch.object(FI.bord, "db_lees", db_lees),
                        patch.object(FI.bord, "call", lambda pad, data=None: self.gepost.append(data) or {"nieuw": len(data["items"])}),
                        patch.object(FI.LC, "context", lambda dag: self.context)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

        class Ag:
            def log(ag, onderwerp, stap, tekst, detail=""):
                self.verslag.append((onderwerp, stap, tekst))
        self.ag = Ag()

    def zet(self, dag, fotos):
        self.bak = [r for r in self.bak if not r["uniek"].startswith(f"fotodag:{dag}:")]
        self.bak.append({"soort": "fotometadata", "uniek": f"fotodag:{dag}:1", "voor": "fotoindeling",
                         "inhoud": json.dumps({"prive": True, "datum": dag, "aantal": len(fotos), "deel": 1, "delen": 1, "fotos": fotos})})

    def test_ronde_schrijft_indeling_en_items_zonder_privé(self):
        fotos, _, _ = dag_29()
        self.zet("2026-10-29", fotos)
        self.bak.append({"soort": "afspraak", "uniek": "agenda:x:1", "voor": "h-architects", "inhoud": json.dumps(
            {"datum": "2026-10-29", "start": "2026-10-29T10:00:00+01:00", "einde": "2026-10-29T11:00:00+01:00",
             "titel": "!! Mehdi: [HA] 9001 proefbezoek", "firma": "HARC", "nummer": "9001", "locatie": "Proefstraat 1, 9999 Proefdorp"})})
        self.bak.append({"soort": "afspraak", "uniek": "agenda:x:2", "voor": "prive", "inhoud": json.dumps(
            {"datum": "2026-10-29", "start": "2026-10-29T18:00:00+01:00", "einde": "2026-10-29T19:00:00+01:00",
             "titel": "privé", "firma": "PRIVE", "locatie": "Ergens 1"})})
        uit = FI.deel_in("2026-10-29", self.ag, [P1, P2])
        self.assertIn("2 werkfoto's in 1 werfgroepen", uit)
        ind = json.loads(Path(FI.UIT, "2026", "2026-10-29.json").read_text())
        items = self.gepost[-1]["items"]
        titels = [it["titel"] for it in items]
        self.assertIn("2026-10-29 10:15-10:20: HARC 9001 Proefwoning Alfa: 2 werkfoto's, bij afspraak '[HA] 9001 proefbezoek' 10:00-11:00", titels)
        self.assertIn("2026-10-29: geen werk: privé 12, met mensen 1, scherm of app 2, onbeslist 0 (alleen geteld, geen plaats)", titels)
        nodig = [it for it in items if it["soort"] == "fotoindeling"][0]["inhoud"]["voorbeeld_nodig"]
        self.assertEqual(nodig, ["w1", "w2"])
        self.assertEqual(sum(it["inhoud"]["aantal"] for it in items if it["soort"] == "foto"), len(fotos))
        alles = json.dumps(ind) + json.dumps(items)
        for x in (str(PRIVE[0]), '"p0"', "portret", '"s1"', "18:00", "19:00"):
            self.assertNotIn(x, alles)
        self.assertEqual(oct(os.stat(Path(FI.UIT, "2026", "2026-10-29.json")).st_mode & 0o777), "0o640")
        # ongewijzigd: niets nieuws op het bord
        n = len(self.gepost)
        self.assertIsNone(FI.deel_in("2026-10-29", self.ag, [P1, P2]))
        self.assertEqual(len(self.gepost), n)
        # een voorvertoning kwam aan: alleen het item voor de Mac wordt bijgewerkt
        Path(FI.VOORBEELD, "2026-10-29").mkdir(parents=True)
        Path(FI.VOORBEELD, "2026-10-29", "w1.jpg").write_bytes(b"\xff\xd8 fictief")
        self.assertEqual(FI.deel_in("2026-10-29", self.ag, [P1, P2], recent=False), "1 voorvertoningen nog nodig")
        self.assertEqual([it["inhoud"]["voorbeeld_nodig"] for it in self.gepost[-1]["items"]], [["w2"]])

    def test_verdwenen_werfgroep_wordt_als_vervallen_gemeld(self):
        f, _, _ = dag_31()
        self.context = {"dag": "2026-10-31", "bronbeleid": "1", "verblijven": []}
        self.zet("2026-10-31", f)
        FI.deel_in("2026-10-31", self.ag, [P1, P2])
        self.assertIn("fotos:2026-10-31:kandidaat:HARC:9001", [it["uniek"] for it in self.gepost[-1]["items"]])
        self.zet("2026-10-31", [x for x in f if not x["id"].startswith("k")])
        FI.deel_in("2026-10-31", self.ag, [P1, P2])
        vervallen = [it for it in self.gepost[-1]["items"] if it["uniek"] == "fotos:2026-10-31:kandidaat:HARC:9001"][0]
        self.assertEqual((vervallen["inhoud"]["aantal"], vervallen["inhoud"]["vervallen"]), (0, True))

    def test_locatie_onbereikbaar_is_onbekend_en_schrijft_niets(self):
        self.context = None
        self.zet("2026-10-29", dag_29()[0])
        self.assertEqual(FI.deel_in("2026-10-29", self.ag, [P1]), "onbekend")
        self.assertFalse(Path(FI.UIT, "2026", "2026-10-29.json").exists())
        self.assertEqual(self.gepost, [])
        self.assertEqual(self.verslag[-1][1], "melding")

    def test_dag_voor_de_meetreeks_heeft_geen_verblijven_maar_wordt_ingedeeld(self):
        self.context = None
        self.zet("2026-10-01", [foto("v", "10:00", *bij((P1["lat"], P1["lon"])), dag="2026-10-01")])
        self.assertIn("1 kandidaat", FI.deel_in("2026-10-01", self.ag, [P1]))

    def test_onvolledige_metadata_wordt_niet_ingedeeld(self):
        self.bak.append({"soort": "fotometadata", "uniek": "fotodag:2026-10-29:1", "voor": "fotoindeling",
                         "inhoud": json.dumps({"datum": "2026-10-29", "aantal": 300, "deel": 1, "delen": 2, "fotos": []})})
        self.assertIsNone(FI.deel_in("2026-10-29", self.ag, [P1]))
        self.assertEqual(self.gepost, [])

    def test_main_zonder_projectplekken_is_een_melding(self):
        verstuurd = []

        class Ag:
            def __init__(ag, naam):
                ag.regels = []

            def log(ag, *a, **k):
                ag.regels.append(a)

            def log_verstuur(ag):
                verstuurd.extend(ag.regels)
        with patch.object(FI.bord, "Agent", Ag), patch.object(FI, "PLEKBRONNEN", (lambda: (_ for _ in ()).throw(OSError("fictief")),)):
            self.assertEqual(FI.main([]), 0)
        self.assertEqual(verstuurd[0][1], "melding")


class Planning(unittest.TestCase):
    def test_cronblok_vervangt_alleen_zijn_eigen_regels(self):
        spec = importlib.util.spec_from_file_location("foto_cron_proef", RUNNER / "planning" / "foto_cron_zetten.py")
        cron = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cron)
        huidig = ["0 1 * * * /bin/true andere taak", "40 19 * * * python oud/koppelingen/fotoindeling.py"]
        een = cron.samenvoegen(huidig)
        self.assertEqual(een[0], "0 1 * * * /bin/true andere taak")
        self.assertEqual(sum("koppelingen/fotoindeling.py" in r for r in een), 2)
        self.assertEqual(cron.samenvoegen(een), een)
        self.assertTrue(all(r.split()[1].replace(",", "").isdigit() for r in een if "fotoindeling.py" in r))


if __name__ == "__main__":
    uitslag = unittest.main(exit=False).result
    if not uitslag.wasSuccessful():
        raise SystemExit(1)
    print("alles geslaagd")
