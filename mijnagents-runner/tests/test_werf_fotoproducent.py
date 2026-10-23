"""Producer/consumercontract met fictieve agenda, bord en registratie; nooit Photos-I/O."""
import ast
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch
import uuid
from zoneinfo import ZoneInfo

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))
PROJECT = "/Work All/01. H-A WORK/0 H-A Standaard projects/5. STAN/9999 Fictief"


class FotoProducent(unittest.TestCase):
    def bezoek(self, suffix="1", fotos=0):
        return {"map": PROJECT + "/_00. Communication/2026-10-14 bezoek " + suffix, "datum": "2026-10-14", "fotos": fotos,
                "opnames": [], "transcripten": ["transcript.txt"], "verslagen": [], "notities": [], "bestanden": 1,
                "bron_map": "_00. Communication", "volgnr": int(suffix), "nr_label": suffix, "soort_bezoek": "werfbezoek"}

    def afspraak(self, suffix="1", **updates):
        d = {"firma": "HARC", "nummer": "9999", "datum": "2026-10-14", "agenda": "H-A Buiten", "type": "WB",
             "onzeker": False, "buiten": True, "start": "2026-10-14T11:00:00+02:00", "einde": "2026-10-14T12:00:00+02:00"}
        d.update(updates)
        return {"van": "agenda-wacht", "voor": "h-architects", "status": "klaar", "soort": "afspraak",
                "uniek": "agenda:kalender-proef:event-" + suffix, "titel": "Fictief werfbezoek", "inhoud": json.dumps(d)}

    def setUp(self):
        self.events, self.gepubliceerd, self.afgevinkt = [], [], []
        self.rows, self.open_foto, self.open_plaud = {}, [], []
        self.bezoeken = [self.bezoek()]
        self.bak = {"afspraak": [self.afspraak()], "foto": [], "transcript": []}
        bord, bronnen, register = ModuleType("bord"), ModuleType("bronnen"), ModuleType("werfregister")

        class RegisterFout(RuntimeError):
            pass

        register.RegisterFout = RegisterFout
        self.register = register

        def registreer(rij, dossier, volg):
            self.events.append(("registratie", rij["id"]))
            return {"bezoek_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "fictief-bord:" + str(rij["id"]))),
                    "project_ref": "h-architects:" + dossier, "bordrij_id": rij["id"]}

        register.registreer = registreer

        def call(pad, payload=None):
            if payload is None:
                return {"rijen": [deepcopy(r) for r in self.rows.values()]}
            self.events.append(("bordopslaan", deepcopy(payload)))
            for r in payload["rijen"]:
                key = (r["bezoekmap"], r["datum"])
                if r.get("_alleen"):
                    self.assertEqual(self.rows[key]["id"], r["werfbezoek_id"])
                    self.rows[key].update({k: deepcopy(r[k]) for k in r["_alleen"]})
                else:
                    oud = self.rows.get(key, {})
                    self.rows[key] = {**oud, **deepcopy(r), "id": oud.get("id", len(self.rows) + 100)}
            return {"ok": True, "herkoppeld": []}

        bord.call = call
        bord.opgepakt = lambda kid, naam: self.afgevinkt.append((kid, naam))
        bord.klaargezet_voor = lambda naam, **kwargs: self.open_foto if naam == "icloud-wacht" else self.open_plaud if naam == "plaud-wacht" else []

        outer = self

        class Agent:
            def __init__(self, *args):
                pass

            def log(self, *args, **kwargs):
                pass

            def klaarzet(self, items):
                outer.events.append(("publiceren", deepcopy(items)))
                outer.gepubliceerd.extend(deepcopy(items))
                return {"nieuw": len(items)}

        bord.Agent = Agent
        spec = importlib.util.spec_from_file_location("werf_fotoproducent_proef", HIER / "werfverslag_voorbereider.py")
        self.v = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"bord": bord, "bronnen": bronnen, "werfregister": register}):
            spec.loader.exec_module(self.v)
        self.v.zoek_projectmap = lambda nummer: (PROJECT, "standaard")
        self.v.bezoeken_in = lambda project, nummer=None: deepcopy(self.bezoeken)
        self.v.dossiers_lezen = lambda: {}
        self.v.klaargezet = lambda nummer: deepcopy(self.bak)
        self.v.projectcoordinaten = lambda nummer, adres, bak: (51.0, 4.0)
        self.v.vooraf_koppelen = lambda bezoeken, *args: bezoeken
        self.v.contractbewijs = lambda nummer: ("onbekend", "fictief contractdashboard")
        self.v.werfapp_bezoeken = lambda nummer: []

    def fotos(self):
        return [t for t in self.gepubliceerd if t["voor"] == "icloud-wacht"]

    def test_bordstoring_slaat_het_dossier_over(self):
        """Driehoeksoverleg 22-10-2026 (C5): zonder bordrijen geen nummering, registratie of taken, anders wordt een
        verslag van bevindingen stil weer werfbezoek 1."""
        echt = self.v.bord.call

        def stuk(pad, payload=None):
            if payload is None and pad.startswith("/api/werfbezoek?dossier="):
                raise OSError("bord niet bereikbaar")
            return echt(pad, payload)

        self.v.bord.call = stuk
        rijen, noden, dubbels = self.v.verwerk("9999")
        self.assertEqual((rijen, dubbels), ([], []))
        self.assertIn("bord niet leesbaar", noden[0]["tekst"])
        self.assertFalse(self.gepubliceerd)
        self.assertFalse([e for e in self.events if e[0] in ("bordopslaan", "registratie")])

    def test_opslaan_en_vaste_registratie_voor_fototaak(self):
        self.v.verwerk("9999")
        self.assertEqual(len(self.fotos()), 1)
        self.assertLess(next(i for i, e in enumerate(self.events) if e[0] == "bordopslaan"),
                        next(i for i, e in enumerate(self.events) if e[0] == "registratie"))
        self.assertLess(next(i for i, e in enumerate(self.events) if e[0] == "registratie"),
                        next(i for i, e in enumerate(self.events) if e[0] == "publiceren"))
        d = self.fotos()[0]["inhoud"]
        self.assertEqual(d["project_ref"], "h-architects:9999")
        self.assertEqual(d["projectmap"], PROJECT)
        self.assertEqual(d["bezoekmap"], self.bezoeken[0]["map"])
        self.assertEqual(d["start"], "2026-10-14T11:00:00+02:00")
        self.assertEqual(d["einde"], "2026-10-14T12:00:00+02:00")
        self.assertEqual(d["straal_m"], 300)
        self.assertEqual((d["lat"], d["lon"]), (51.0, 4.0))
        self.assertEqual(str(uuid.UUID(d["bezoek_id"])), d["bezoek_id"])
        self.assertIn(d["bezoek_id"], self.fotos()[0]["uniek"])

    def test_daadswerkelijke_consument_accepteert_producentcontract(self):
        self.v.verwerk("9999")
        d = self.fotos()[0]["inhoud"]
        # Alleen de drie echte guardfuncties laden. Geen token, SQLite, Photos of exportfunctie.
        tree = ast.parse((HIER / "mac/icloud_wacht.py").read_text())
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ("_tijd_met_zone", "taakvenster", "taakdoel")]
        with tempfile.TemporaryDirectory() as root:
            context = {"datetime": datetime, "timedelta": timedelta, "timezone": timezone, "ZoneInfo": ZoneInfo,
                       "uuid": uuid, "Path": Path, "PurePosixPath": PurePosixPath, "re": re, "DROPBOX_LOKAAL": root}
            exec(compile(ast.Module(body=nodes, type_ignores=[]), "echte-fotoguards", "exec"), context)
            start, einde = context["taakvenster"](d)
            self.assertEqual(einde - start, timedelta(hours=1))
            self.assertTrue(context["taakdoel"](d).endswith("/fotos"))

    def test_geen_afvinkrecht_bij_een_aanwezige_foto_oude_taak_blijft_open(self):
        self.bezoeken = [self.bezoek(fotos=1)]
        self.open_foto = [{"id": 12, "soort": "taak", "van": self.v.NAAM, "voor": "icloud-wacht",
                           "uniek": "werf:9999:2026-10-14:icloud-wacht", "titel": "Oude fototaak",
                           "inhoud": json.dumps({"dossier": "9999", "datum": "2026-10-14", "bezoekmap": self.bezoeken[0]["map"]})}]
        rijen, noden, _ = self.v.verwerk("9999")
        self.assertEqual(self.afgevinkt, [])
        self.assertEqual(self.fotos(), [])
        self.assertTrue(any("mist bezoekvenster" in n["tekst"] for n in noden))
        self.assertEqual(next(c for c in rijen[0]["controles"] if c["code"] == "W4")["stand"], "ontbreekt")

    def test_meerdere_bezoeken_dezelfde_dag_krijgen_aparte_identiteit_en_venster(self):
        self.bezoeken = [self.bezoek("1"), self.bezoek("2")]
        self.bak["afspraak"] = [self.afspraak("1", bezoekmap=self.bezoeken[0]["map"]),
                                 self.afspraak("2", bezoekmap=self.bezoeken[1]["map"], start="2026-10-14T14:00:00+02:00", einde="2026-10-14T15:00:00+02:00")]
        self.v.verwerk("9999")
        self.assertEqual(len(self.fotos()), 2)
        self.assertEqual(len({t["uniek"] for t in self.fotos()}), 2)
        self.assertEqual(len({t["inhoud"]["bezoek_id"] for t in self.fotos()}), 2)
        self.assertEqual({t["inhoud"]["start"] for t in self.fotos()}, {"2026-10-14T11:00:00+02:00", "2026-10-14T14:00:00+02:00"})

    def test_zonder_afspraak_krijgt_fototaak_e4_venster_uit_fototijd(self):
        self.bak["afspraak"] = []
        self.bak["foto"] = [{"van": "icloud-wacht", "soort": "foto", "sleutel": "2026-10-14",
                             "inhoud": json.dumps({"datum": "2026-10-14", "fotos": [
                                 {"vastgelegd_utc": "2026-10-14T09:30:00Z", "lat": 51.0, "lon": 4.0}]})}]
        self.v.verwerk("9999")
        self.assertEqual(len(self.fotos()), 1)
        d = self.fotos()[0]["inhoud"]
        self.assertEqual(d["reden"], "E4, geen afspraak")
        self.assertEqual(d["start"], "2026-10-14T11:15:00+02:00")
        self.assertEqual(d["einde"], "2026-10-14T12:30:00+02:00")

    def test_zonder_afspraak_krijgt_fototaak_e4_venster_uit_opnamestart(self):
        self.bak["afspraak"] = []
        self.bezoeken[0]["opname_starts"] = ["2026-10-14T11:30:00+02:00"]
        self.v.verwerk("9999")
        self.assertEqual(len(self.fotos()), 1)
        d = self.fotos()[0]["inhoud"]
        self.assertEqual(d["reden"], "E4, geen afspraak")
        self.assertEqual(d["start"], "2026-10-14T11:15:00+02:00")
        self.assertEqual(d["einde"], "2026-10-14T12:30:00+02:00")

    def test_bron_in_map_sluit_alleen_taak_van_dezelfde_bezoeksleutel(self):
        b = self.bezoeken[0]
        b["fotos"] = 1
        b["foto_bestanden"] = [b["map"] + "/fotos/1130 a.jpg"]
        b["foto_manifest"] = b["map"] + "/fotos/00 fotos.md"
        b["transcript_bestanden"] = [b["map"] + "/transcript.txt"]
        self.v.bronnen.download = lambda *a, **kw: b"- 2026-10-14T11:30:00+02:00 | 1130 a.jpg\n"
        sleutel = self.v.bezoeksleutel("9999", b)
        self.open_foto = [{"id": 13, "van": self.v.NAAM, "soort": "taak", "uniek": "zelfde",
                           "inhoud": json.dumps({"bezoeksleutel": sleutel})},
                          {"id": 14, "van": self.v.NAAM, "soort": "taak", "uniek": "ander",
                           "inhoud": json.dumps({"bezoeksleutel": "9999:2026-10-14:/ander"})}]
        self.open_plaud = [{"id": 15, "van": self.v.NAAM, "soort": "taak", "uniek": "zelfde-plaud",
                            "inhoud": json.dumps({"bezoeksleutel": sleutel})}]
        self.v.verwerk("9999")
        self.assertEqual(set(self.afgevinkt), {(13, self.v.NAAM), (15, self.v.NAAM)})

    def test_meerdere_bezoeken_zonder_expliciete_binding_niet_op_dag_samenvoegen(self):
        self.bezoeken = [self.bezoek("1"), self.bezoek("2")]
        _, noden, _ = self.v.verwerk("9999")
        self.assertEqual(self.fotos(), [])
        self.assertEqual(len([e for e in self.events if e[0] == "registratie"]), 2)
        self.assertTrue(any("geen ondubbelzinnig" in n["tekst"] for n in noden))

    def test_twee_agenda_afspraken_zonder_binding_geeft_geen_eerste_match(self):
        self.bak["afspraak"] = [self.afspraak("1"), self.afspraak("2", start="2026-10-14T14:00:00+02:00", einde="2026-10-14T15:00:00+02:00")]
        self.v.verwerk("9999")
        self.assertEqual(self.fotos(), [])

    def test_geen_tijden_firma_dossier_of_bevestiging_raden(self):
        for updates in ({"firma": "UNAB"}, {"nummer": "9998"}, {"onzeker": True}, {"buiten": False}, {"type": "KO"},
                        {"start": "2026-10-14T11:00:00"}, {"einde": None}, {"geannuleerd": True}, {"prive": True},
                        {"datum": "2026-10-13"}, {"project_ref": "unabo:9999"}):
            with self.subTest(updates=updates):
                self.gepubliceerd.clear()
                self.bak["afspraak"] = [self.afspraak(**updates)]
                self.v.verwerk("9999")
                self.assertEqual(self.fotos(), [])

    def test_onjuiste_afdeling_of_andere_producer_geeft_geen_fototaak(self):
        for key, value in (("voor", "prive"), ("van", "onbekende-bron"), ("status", "vervallen")):
            with self.subTest(key=key):
                self.gepubliceerd.clear()
                it = self.afspraak()
                it[key] = value
                self.bak["afspraak"] = [it]
                self.v.verwerk("9999")
                self.assertEqual(self.fotos(), [])

    def test_geen_vaste_registratie_geen_nieuwe_fototaak(self):
        self.register.registreer = lambda *args: (_ for _ in ()).throw(self.register.RegisterFout("fictieve dienst niet bereikbaar"))
        _, noden, _ = self.v.verwerk("9999")
        self.assertEqual(self.fotos(), [])
        self.assertTrue(any("vaste registratie" in n["tekst"] for n in noden))

    def test_bordopslaan_mislukt_geen_registratie_of_publicatie(self):
        self.v.bord.call = lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("fictief bord offline"))
        self.v.verwerk("9999")
        self.assertEqual(self.fotos(), [])
        self.assertFalse(any(e[0] in ("registratie", "publiceren") for e in self.events))

    def test_ongeldig_bezoek_id_geeft_geen_fototaak(self):
        self.register.registreer = lambda *args: {"bezoek_id": "datum-is-geen-uuid", "project_ref": "h-architects:9999"}
        self.v.verwerk("9999")
        self.assertEqual(self.fotos(), [])

    def test_droog_is_geen_registratie_opdracht_of_afvinken(self):
        with patch("builtins.print"):
            self.v.verwerk("9999", droog=True)
        self.assertEqual(self.events, [])
        self.assertEqual(self.afgevinkt, [])


if __name__ == "__main__":
    unittest.main()
