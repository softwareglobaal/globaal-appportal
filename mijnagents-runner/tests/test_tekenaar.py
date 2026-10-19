"""De Tekenaar (tekenaar.py en koppelingen/ba_plannen.py), vastgezet. Ontwerplezing Codex DT01, DT02 en DT05
(18-10-2026) en de controle voor registratie DT06 tot DT12 (19-10-2026).

Wat hier vastligt:
  - nieuw is een inhoud die De Tekenaar nog niet zag; een kopie of een verplaatst plan (een project dat van fasemap
    verandert) niet; wat voor de archiefcontrole van oktober 2026 laatst gewijzigd is, telt bij de eerste lijst als
    vrijgesteld; een volledige lijst ruimt op wat er niet meer staat (DT11);
  - een gecontroleerd plan blijft te melden tot het bord werkverslag en signaal bevestigt (DT06); een te groot of
    onleesbaar plan wordt na te kijken, nooit weggelaten, en een volle wachtrij houdt de ronde open (DT07);
  - een regularisatie herkent hij ook aan de projectmap (DT08); naar het bord gaan geen adressen (DT10);
  - een signaal alleen bij een FOUT, gebundeld, zonder aantal in het uniek, zonder het woord "stil", met een fout uit
    het sjabloon achteraan;
  - de werkmap en de stand liggen nooit in Dropbox, ook niet even (DT12); de normcontrole komt uit origin/main;
  - een volledige ronde gaat door de gedeelde ag.ronde: hartslag, werkwijze, lessen, collega's en kennis (N4, N11 tot
    N14), ook als er niets nieuw is; zonder hulpscript op de VM of met een onleesbare stand een nood;
  - een ronde is aan de beurt na zes dagen of als er iets wacht (N4 binnen zeven dagen);
  - het hulpscript op de VM leest alleen BA-plannen onder de twee projectmappen.

Geen netwerk, geen ssh, geen Dropbox en geen PyMuPDF: het bord, de VM en de normcontrole worden nagebootst.
Draaien: python3 mijnagents-runner/tests/test_tekenaar.py
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
sys.path.insert(0, RUNNER)
import bord  # noqa: E402
import ba_plannen  # noqa: E402
import tekenaar as tk  # noqa: E402

S = "/Work All/01. H-A WORK/0 H-A Standaard projects"
L = "/Work All/01. H-A WORK/0 H-A Light projects"
PROJECT = "9901 Proefstraat 1, 3120 Tremelo (stan)"
P1 = f"{S}/2. STAN permission Awaited/{PROJECT}/3. Bouwaanvraag/2. PDF/BA_Proefstraat 1, 3120 Tremelo_P_N_1_00_gelijkvloers.pdf"
P2 = f"{S}/2. STAN permission Awaited/{PROJECT}/3. Bouwaanvraag/2. PDF/BA_Proefstraat 1, 3120 Tremelo_G_N_1_A_voorgevel.pdf"
P3 = f"{L}/3. H-A light permission received/9902 Proeflaan 2, 1000 Brussel (reg)/BA_Proeflaan 2, 1000 Brussel_P_B_1_00_gelijkvloers.pdf"


def plan(i, pad, h, gewijzigd="2026-10-19T08:00:00Z"):
    return {"soort": "bestand", "id": f"id:proef{i:04d}", "pad": pad, "hash": h, "gewijzigd": gewijzigd}


class NepNormcontrole:
    """Zoals normcontrole.py: FOUT voor een blad met _G_ (meetlijn), persoonsgegevens op elk blad uit het sjabloon,
    gewest FOUT voor Brussel. Onthoudt hoe de set gevraagd werd."""

    def __init__(self):
        self.sets = []

    def controleer_pdf(self, pdf, naam=None, map_naam=None):
        with open(pdf, "rb") as f:
            assert f.read(4) == b"%PDF"
        u = {"bestandsnaam": {"status": "OK", "reden": "volgt de code", "artikel": ""},
             "persoonsgegevens": {"status": "FOUT", "reden": "rijksregisternummer", "artikel": "p.4"}}
        if "_G_" in naam:
            u["meetlijn"] = {"status": "FOUT", "reden": "5 m gemeten 25 mm, bij 1/100 hoort 50 mm", "artikel": "1.3.2"}
        if "1000 Brussel" in (naam or ""):
            u["gewest"] = {"status": "FOUT", "reden": "Brussel volgens de postcode", "artikel": "B01"}
        u["eenheid"] = {"status": "LET OP", "reden": "proef", "artikel": ""}
        statussen = {v["status"] for v in u.values()}
        return {"uitkomsten": u, "oordeel": next(s for s in ("FOUT", "ONBEKEND", "LET OP", "OK") if s in statussen | {"OK"})}

    def is_regularisatie(self, *namen):
        return True if any("(reg" in (n or "").lower() for n in namen) else None

    def controleer_set(self, namen, regularisatie=None, nieuw=None):
        self.sets.append({"namen": namen, "regularisatie": regularisatie, "nieuw": nieuw})
        u = {}
        if regularisatie and not any("_V_" in n or "_BV_" in n for n in namen):
            u["toestanden"] = {"status": "FOUT", "reden": "regularisatie onvolledig: grondplan zonder V", "artikel": ""}
        return {"uitkomsten": u, "oordeel": "FOUT" if u else "OK", "deelsets": {}}


def nep_haal(ident, doel):
    if ident.endswith("weg1"):
        return "weg"
    if ident.endswith("groot"):
        return "te_groot"
    with open(doel, "wb") as f:
        f.write(b"%PDF-1.7 proef")
    return "ok"


class Basis(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        oud = {k: getattr(tk, k) for k in ("STAND", "WERKMAP", "DROPBOX", "TOKEN_PAD", "BRUG")}
        self.addCleanup(lambda: [setattr(tk, k, v) for k, v in oud.items()])
        tk.STAND = os.path.join(self.tmp.name, "stand", "stand.json")
        tk.WERKMAP = os.path.join(self.tmp.name, "cache")
        tk.DROPBOX = os.path.join(self.tmp.name, "Dropbox")

    def stand_met_basis(self):
        st = tk.lege_stand()
        st["gezien"]["oud"] = {"status": "basis"}       # niet meer de eerste lijst
        return st


class Selectie(Basis):
    def test_eerste_lijst_basis_en_nieuw(self):
        st = tk.lege_stand()
        lijst = {"cursors": {"standaard": "c1"}, "wijzigingen": [
            plan(1, P1, "h1", "2026-09-01T10:00:00Z"),              # voor de archiefcontrole: vrijgesteld
            plan(2, P2, "h2", "2026-10-19T08:00:00Z"),              # erna: nieuw
            plan(3, P1.replace(".pdf", ".dwg"), "h3")]}             # geen BA-pdf
        nieuw, weg = tk.selecteer(st, lijst)
        self.assertEqual((nieuw, weg), (1, 0))
        self.assertEqual(st["gezien"]["h1"]["status"], "basis")
        self.assertEqual(st["wachtrij"], ["id:proef0002"])
        self.assertEqual(st["cursors"], {"standaard": "c1"})
        self.assertEqual(set(st["bekend"]), {"id:proef0001", "id:proef0002"})

    def test_kopie_en_verplaatsing_zijn_niet_nieuw(self):
        st = tk.lege_stand()
        tk.selecteer(st, {"wijzigingen": [plan(1, P1, "h1", "2026-09-01T10:00:00Z")]})
        verhuisd = P1.replace("2. STAN permission Awaited", "3. STAN permission received")
        nieuw, weg = tk.selecteer(st, {"wijzigingen": [
            {"soort": "weg", "pad": f"{S}/2. STAN permission Awaited/{PROJECT}".lower()},
            plan(1, verhuisd, "h1"),
            plan(9, P1.replace("2. PDF", "8. Latest PDF for Meetings"), "h1")]})
        self.assertEqual(nieuw, 0)
        self.assertEqual(st["wachtrij"], [])
        self.assertEqual(st["bekend"]["id:proef0001"]["pad"], verhuisd)
        self.assertIn("id:proef0009", st["bekend"])
        # Een gewijzigde inhoud is wel nieuw, ook na de eerste lijst en ook als het plan oud gedateerd is.
        nieuw, _ = tk.selecteer(st, {"wijzigingen": [plan(1, verhuisd, "h1b", "2026-01-01T00:00:00Z")]})
        self.assertEqual(nieuw, 1)
        self.assertEqual(st["wachtrij"], ["id:proef0001"])

    def test_verdwenen_plan_uit_de_wachtrij(self):
        st = self.stand_met_basis()
        tk.selecteer(st, {"wijzigingen": [plan(2, P2, "h2"), plan(7, P2.replace("2. PDF", "kopie"), "h2")]})
        self.assertEqual(st["wachtrij"], ["id:proef0002"])
        tk.selecteer(st, {"wijzigingen": [{"soort": "weg", "pad": P2.lower()}]})
        self.assertEqual(st["wachtrij"], ["id:proef0007"])          # dezelfde inhoud neemt de plaats
        tk.selecteer(st, {"wijzigingen": [{"soort": "weg", "pad": P2.replace("2. PDF", "kopie").lower()}]})
        self.assertEqual(st["wachtrij"], [])
        self.assertNotIn("h2", st["gezien"])                        # komt ze terug, dan is ze nieuw

    def test_volledige_lijst_ruimt_op(self):
        # DT11: na een geweigerde cursor komt een volledige lijst; wat er niet in staat, is weg (ook onder een map met
        # een punt in de naam, die het hulpscript nu ook doorgeeft).
        st = self.stand_met_basis()
        tk.selecteer(st, {"wijzigingen": [plan(1, P1, "h1"), plan(2, P2, "h2"), plan(3, P3, "h3")]})
        nieuw, weg = tk.selecteer(st, {"volledig": {"standaard": True, "light": False},
                                       "wijzigingen": [plan(1, P1, "h1")]})
        self.assertEqual((nieuw, weg), (0, 1))
        self.assertEqual(set(st["bekend"]), {"id:proef0001", "id:proef0003"})   # light niet volledig: blijft

    def test_mappen_zonder_toegang_worden_gemeld(self):
        st = tk.lege_stand()
        tk.selecteer(st, {"volledig": {"standaard": True, "light": True},
                          "geen_toegang": [{"basis": "standaard", "pad": S + "/H-A Mehdi(oud)"}]})
        self.assertEqual(tk.blinde_vlekken(st), [S + "/H-A Mehdi(oud)"])
        tk.selecteer(st, {"volledig": {"standaard": False, "light": False}, "geen_toegang": []})
        self.assertEqual(tk.blinde_vlekken(st), [S + "/H-A Mehdi(oud)"])     # een deellijst ziet de map niet
        tk.selecteer(st, {"volledig": {"standaard": True}, "geen_toegang": []})
        self.assertEqual(tk.blinde_vlekken(st), [])                          # toegang gekregen

    def test_projectnummer_en_labels_zonder_adres(self):
        self.assertEqual(tk.projectnummer(P1)[0], "9901")
        self.assertEqual(tk.projectnummer(P3)[0], "9902")
        self.assertEqual(tk.projectnummer(f"{L}/1. H-A light Submission/3.H-A light Subm/BA_x_P_N.pdf")[0], "zonder nummer")
        self.assertEqual(tk.blad_label(P1), "9901 / 3. Bouwaanvraag / 2. PDF / P_N_1_00_gelijkvloers.pdf")
        self.assertEqual(tk.bladcode("BA_Proefstraat 1, 3120 Tremelo_Legende.pdf"), "Legende.pdf")
        self.assertEqual(tk.bladcode("BA_Proefstraat 1, 3120 Tremelo.pdf"), "blad zonder tekeningsoort in de naam")
        self.assertEqual(tk.map_label(os.path.dirname(P1)), "9901 / 3. Bouwaanvraag / 2. PDF")


class Controle(Basis):
    def test_wachtrij_controleren_te_groot_en_weg(self):
        st = self.stand_met_basis()
        tk.selecteer(st, {"wijzigingen": [plan(1, P1, "h1"), plan(2, P2, "h2"),
                                          {"soort": "bestand", "id": "id:proefweg1", "pad": P3, "hash": "h3"},
                                          {"soort": "bestand", "id": "id:proefgroot", "pad": P3.replace("P_B", "G_B"),
                                           "hash": "h4"}]})
        verdwenen = tk.controleer_wachtrij(NepNormcontrole(), st, haal=nep_haal)
        self.assertEqual(verdwenen, 1)
        self.assertEqual([m["id"] for m in st["te_melden"]], ["id:proef0001", "id:proef0002", "id:proefgroot"])
        groot = st["te_melden"][2]["uitslag"]
        self.assertEqual(groot["oordeel"], "ONBEKEND")                   # DT07: gemeld, niet weggelaten
        self.assertIn("80 MB", groot["onbekend"][0])
        self.assertEqual(st["gezien"]["h2"]["fout"], ["persoonsgegevens", "meetlijn"])
        self.assertEqual(st["wachtrij"], [])
        self.assertNotIn("id:proefweg1", st["bekend"])
        self.assertEqual(tk.lees_stand()["te_melden"], st["te_melden"])  # na elk plan bewaard
        self.assertEqual([x for x in os.listdir(tk.WERKMAP) if x.startswith("ronde-")], [])   # geen PDF blijft

    def test_werkmap_en_stand_nooit_in_dropbox(self):
        tk.WERKMAP = os.path.join(tk.DROPBOX, "Work All", "cache")
        with self.assertRaisesRegex(RuntimeError, "Dropbox"):
            tk.controleer_wachtrij(NepNormcontrole(), tk.lege_stand(), haal=nep_haal)
        self.assertFalse(os.path.exists(tk.WERKMAP))                     # DT12: ook niet even aangemaakt
        with self.assertRaisesRegex(RuntimeError, "Dropbox"):
            tk.bewaar_stand(tk.lege_stand(), os.path.join(tk.DROPBOX, "stand.json"))
        self.assertFalse(os.path.exists(tk.DROPBOX))

    def test_regularisatie_uit_de_projectmap(self):
        # DT08: alleen een B-blad, geen V, maar de projectmap zegt (reg): de set is onvolledig.
        st = self.stand_met_basis()
        tk.selecteer(st, {"wijzigingen": [plan(3, P3, "h3")]})
        nep = NepNormcontrole()
        tk.controleer_wachtrij(nep, st, haal=nep_haal)
        sets = tk.set_bevindingen(nep, st, st["te_melden"])
        self.assertTrue(nep.sets[0]["regularisatie"])
        self.assertEqual(list(sets.values()), [[("toestanden", "regularisatie onvolledig: grondplan zonder V")]])

    def test_signaal_alleen_bij_fout_en_sjabloonfout_achteraan(self):
        ok = {"id": "id:proef0001", "pad": P1, "uitslag": {"oordeel": "LET OP", "fout": [], "fout_reden": {}}}
        self.assertIsNone(tk.signaal([ok], {}, "2026-W43", "abc1234"))
        fout = {"id": "id:proef0002", "pad": P2, "uitslag": {"oordeel": "FOUT", "fout": ["meetlijn: 25 mm"],
                "fout_reden": {"persoonsgegevens": "rijksregisternummer", "meetlijn": "5 m gemeten 25 mm"}}}
        item = tk.signaal([ok, fout], {os.path.dirname(P3): [("bladnummers", "dubbel")]}, "2026-W43", "abc1234")
        self.assertEqual((item["voor"], item["soort"]), ("mehdi", "signaal"))
        self.assertRegex(item["uniek"], r"^tekenaar-normcontrole-2026-W43-[0-9a-f]{8}$")
        self.assertIn("9901", item["titel"])
        self.assertIn("9902", item["titel"])
        self.assertTrue(item["titel"].endswith(", persoonsgegevens)"), item["titel"])   # sjabloonfout achteraan
        self.assertIn("meetlijn", item["titel"])
        self.assertNotIn("stil", item["titel"].lower())
        self.assertLessEqual(len(item["titel"]), 110)          # De Bode toont 110 tekens
        self.assertTrue(any("Teken-agent-map" in v for v in item["inhoud"]["voorstel"]))
        projecten = {p["project"]: p for p in item["inhoud"]["projecten"]}
        self.assertEqual((projecten["9901"]["nieuwe_bladen"], projecten["9901"]["met_fout"]), (2, 1))
        self.assertEqual([f["wat"] for f in projecten["9901"]["fouten"]], ["meetlijn", "persoonsgegevens"])
        self.assertEqual(projecten["9901"]["fouten"][0]["voorbeeld"], ["G_N_1_A_voorgevel.pdf"])
        self.assertEqual(projecten["9902"]["set"], ["dubbele bladcode: dubbel"])
        tekst = json.dumps(item, ensure_ascii=False)
        for adres in ("Proefstraat", "Proeflaan", "3120", "1000 Brussel"):
            self.assertNotIn(adres, tekst)                        # DT10
        # Veel bladen met dezelfde fout: een regel per soort, hoogstens drie voorbeelden; zelfde melding, zelfde uniek.
        veel = [dict(fout, id=f"id:proefv{i:03d}", pad=P2.replace("voorgevel", f"gevel{i}")) for i in range(40)]
        f = tk.signaal(veel, {}, "2026-W43", "abc1234")["inhoud"]["projecten"][0]["fouten"]
        self.assertEqual((len(f), f[0]["bladen"], len(f[0]["voorbeeld"])), (2, 40, 3))
        self.assertEqual(tk.signaal(veel, {}, "2026-W43", "x")["uniek"], tk.signaal(veel, {}, "2026-W43", "y")["uniek"])
        self.assertNotEqual(tk.signaal(veel, {}, "2026-W43", "x")["uniek"], tk.signaal(veel[:5], {}, "2026-W43", "x")["uniek"])

    def test_aan_de_beurt(self):
        nu = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
        st = tk.lege_stand()
        self.assertTrue(tk.aan_de_beurt(st, nu))                         # nooit een ronde gedaan
        st["laatste_ronde"] = (nu - timedelta(days=5)).isoformat()
        self.assertFalse(tk.aan_de_beurt(st, nu))
        st["laatste_ronde"] = (nu - timedelta(days=5, hours=23)).isoformat()
        self.assertTrue(tk.aan_de_beurt(st, nu))                         # dag zes, binnen de zeven van N4
        st["laatste_ronde"] = (nu - timedelta(days=1)).isoformat()
        st["wachtrij"] = ["id:proef0001"]
        self.assertTrue(tk.aan_de_beurt(st, nu))                         # DT07: de wachtrij gaat morgen verder
        st["wachtrij"], st["te_melden"] = [], [{"id": "x"}]
        self.assertTrue(tk.aan_de_beurt(st, nu))                         # DT06: een melding wacht op het bord


class Ssh(unittest.TestCase):
    def test_socketpad_past_in_een_unix_socket(self):
        # %C wordt 40 tekens, ssh plakt er bij het aanmaken 17 achter; macOS laat 104 toe (gemeten 19-10-2026).
        lengte = len(tk.SSH_SOCKET.replace("%C", "x" * 40)) + 17
        self.assertLess(len(os.path.expanduser("~/.ssh/tekenaar-")) + 40 + 17, 104)
        self.assertLess(lengte, 104)


class Regelboek(Basis):
    def test_normcontrole_komt_uit_origin_main(self):
        bron = os.path.join(self.tmp.name, "bron")
        os.makedirs(os.path.join(bron, "gereedschap"))
        os.makedirs(os.path.join(bron, "kennis"))

        def git(*a, cwd=bron):
            subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True)

        git("init", "-q", "-b", "main")
        with open(os.path.join(bron, "gereedschap", "normcontrole.py"), "w") as f:
            f.write("VERSIE = 'github'\n")
        with open(os.path.join(bron, "kennis", "normenboek-B01-checklist.md"), "w") as f:
            f.write("# checklist\n")
        git("add", ".")
        git("-c", "user.name=proef", "-c", "user.email=proef@example.invalid", "commit", "-q", "-m", "proef")
        kloon = os.path.join(self.tmp.name, "kloon")
        subprocess.run(["git", "clone", "-q", bron, kloon], check=True, capture_output=True)
        with open(os.path.join(kloon, "gereedschap", "normcontrole.py"), "w") as f:
            f.write("VERSIE = 'half bewerkt'\n")                         # een andere sessie in de werkmap
        tk.BRUG = kloon
        bronnen, commit, nc_pad, opgehaald = tk.regelboek()
        self.assertTrue(opgehaald)
        self.assertEqual(tk.normcontrole(nc_pad).VERSIE, "github")
        self.assertIn(commit, bronnen["globaal-vectorworks-brug"])
        self.assertTrue(nc_pad.startswith(tk.WERKMAP))


class NepBord:
    """Vangt op wat de ronde naar het bord stuurt (bord.call), zonder netwerk. faal: routes die een fout geven."""

    def __init__(self, werkwijze):
        self.werkwijze = werkwijze
        self.oproepen = []
        self.faal = set()

    def __call__(self, pad, payload=None, method=None):
        if pad in self.faal:
            raise urllib.error.URLError("bord weg")
        self.oproepen.append((pad, payload))
        if pad == "/api/agent/tekenaar/werkwijze":
            return {"werkwijze": self.werkwijze}
        if pad == "/api/agents":
            return [{"naam": "bode", "label": "De Bode", "type": "regie", "rol": "brengt naar Telegram", "actief": 1}]
        if pad == "/api/nood":
            return {"nood": []}
        if pad == "/api/klaarzet":
            return {"nieuw": len(payload["items"]), "bestaand": 0}
        return {"ok": True}

    def van(self, pad):
        return [p for q, p in self.oproepen if q == pad]


class Ronde(Basis):
    def setUp(self):
        super().setUp()
        with open(os.path.join(RUNNER, "werkwijze", "tekenaar.md"), encoding="utf-8") as f:
            self.nep = NepBord(f.read())
        self.lijst = {"cursors": {"standaard": "c2", "light": "c3"}, "wijzigingen": []}
        vervang = {"call": (bord, self.nep), "tunnel": (tk, self._tunnel), "hulp_versie": (tk, lambda: tk.HULP_VERSIE),
                   "lijst_van_vm": (tk, lambda c: json.loads(json.dumps(self.lijst))), "haal_van_vm": (tk, nep_haal),
                   "normcontrole": (tk, lambda pad: NepNormcontrole()),
                   "regelboek": (tk, lambda: ({"normcontrole.py": "code", "normenboek-B01-checklist.md": "lijst",
                                               "globaal-vectorworks-brug": "origin/main abc1234"}, "abc1234",
                                              "/geen/pad", True))}
        oud = {k: getattr(m, k) for k, (m, _) in vervang.items()}
        for k, (m, v) in vervang.items():
            setattr(m, k, v)
        oud_bord = (bord.PLATFORM, bord.TOKEN)
        self.addCleanup(lambda: [setattr(m, k, oud[k]) for k, (m, _) in vervang.items()])
        self.addCleanup(lambda: (setattr(bord, "PLATFORM", oud_bord[0]), setattr(bord, "TOKEN", oud_bord[1])))
        tk.TOKEN_PAD = os.path.join(self.tmp.name, "token")
        with open(tk.TOKEN_PAD, "w") as f:
            f.write("proeftoken")

    @contextlib.contextmanager
    def _tunnel(self):
        yield "http://127.0.0.1:1"

    def draai(self, *argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                return tk.main(list(argv))
            except urllib.error.URLError:
                return "breuk"

    def test_ronde_zonder_nieuwe_plannen_geeft_hartslag_en_kennis(self):
        self.assertEqual(self.draai(), 0)
        slagen = self.nep.van("/agent-status")
        self.assertEqual(slagen[0]["status"], "actief")
        self.assertEqual(slagen[-1]["status"], "klaar")
        kennis = self.nep.van("/api/agent/tekenaar/kennis")[-1]["bron"]
        for bron in ("werkwijze op het bord", "gedeelde lessen", "collega's op het bord", "normcontrole.py",
                     "normenboek-B01-checklist.md", "globaal-vectorworks-brug"):
            self.assertIn(bron, kennis)
        self.assertEqual(self.nep.van("/api/klaarzet"), [])
        st = tk.lees_stand()
        self.assertEqual(st["laatste_week"], tk.week())
        self.assertEqual(st["cursors"], {"standaard": "c2", "light": "c3"})
        # Meteen opnieuw: niet aan de beurt, dus geen tunnel en geen hartslag (launchd start me dagelijks).
        tk.tunnel = lambda: (_ for _ in ()).throw(AssertionError("geen tunnel verwacht"))
        voor = len(self.nep.oproepen)
        self.assertEqual(self.draai(), 0)
        self.assertEqual(len(self.nep.oproepen), voor)

    def test_ronde_met_fout_zet_een_signaal_zonder_adres(self):
        tk.bewaar_stand(self.stand_met_basis())
        self.lijst["wijzigingen"] = [plan(1, P1, "h1"), plan(2, P2, "h2")]
        self.assertEqual(self.draai("--nu"), 0)
        items = [i for p in self.nep.van("/api/klaarzet") for i in p["items"]]
        self.assertEqual(len(items), 1)
        self.assertEqual((items[0]["van"], items[0]["soort"]), ("tekenaar", "signaal"))
        verslag = [r for p in self.nep.van("/api/logboek") for r in p["regels"]]
        self.assertTrue(any(r["onderwerp"] == "project 9901" for r in verslag))
        self.assertIn("FOUT 2", self.nep.van("/agent-status")[-1]["detail"])
        alles = json.dumps(self.nep.oproepen, ensure_ascii=False)
        for adres in ("Proefstraat", "3120 Tremelo"):
            self.assertNotIn(adres, alles)                        # DT10: niets met een adres naar het bord
        self.assertEqual(tk.lees_stand()["te_melden"], [])

    def test_melding_blijft_tot_het_bord_ze_bevestigt(self):
        # DT06: het werkverslag haalt het bord niet; de ronde breekt, de melding blijft, en de volgende ronde meldt ze.
        tk.bewaar_stand(self.stand_met_basis())
        self.lijst["wijzigingen"] = [plan(2, P2, "h2")]
        self.nep.faal = {"/api/logboek"}
        self.assertEqual(self.draai("--nu"), "breuk")
        st = tk.lees_stand()
        self.assertEqual([m["id"] for m in st["te_melden"]], ["id:proef0002"])
        self.assertIsNone(st["laatste_ronde"])
        self.assertEqual(st["gezien"]["h2"]["status"], "gecontroleerd")
        self.nep.faal = set()
        self.lijst["wijzigingen"] = []                             # de cursor is al verder: niets nieuws in de lijst
        self.assertEqual(self.draai(), 0)                          # aan de beurt omdat er een melding wacht
        self.assertEqual(len([i for p in self.nep.van("/api/klaarzet") for i in p["items"]]), 1)
        self.assertEqual(tk.lees_stand()["te_melden"], [])

    def test_volle_wachtrij_houdt_de_ronde_open(self):
        # DT07: meer plannen dan een ronde aankan; de ronde is niet af en gaat bij de volgende start verder.
        tk.bewaar_stand(self.stand_met_basis())
        self.lijst["wijzigingen"] = [plan(i, P1.replace("gelijkvloers", f"blad{i}"), f"h{i}") for i in range(1, 6)]
        oud = tk.MAX_PER_RONDE
        tk.MAX_PER_RONDE = 3
        self.addCleanup(setattr, tk, "MAX_PER_RONDE", oud)
        self.assertEqual(self.draai("--nu"), 1)
        st = tk.lees_stand()
        self.assertEqual((len(st["wachtrij"]), st["laatste_ronde"]), (2, None))
        self.assertTrue(any("Meer nieuwe plannen" in n["tekst"] for n in self.nep.van("/agent-status")[-1]["nood"]))
        self.lijst["wijzigingen"] = []
        self.assertEqual(self.draai(), 0)
        self.assertEqual(tk.lees_stand()["wachtrij"], [])

    def test_zonder_hulpscript_op_de_vm_een_nood(self):
        tk.hulp_versie = lambda: None
        self.assertEqual(self.draai(), 1)
        laatste = self.nep.van("/agent-status")[-1]
        self.assertEqual(laatste["status"], "waakt")
        self.assertTrue(any("ba_plannen.py" in n["tekst"] for n in laatste["nood"]))
        self.assertIsNone(tk.lees_stand()["laatste_ronde"])

    def test_onleesbare_stand_geeft_een_nood(self):
        os.makedirs(os.path.dirname(tk.STAND), exist_ok=True)
        with open(tk.STAND, "w") as f:
            f.write("{kapot")
        self.assertEqual(self.draai(), 1)
        laatste = self.nep.van("/agent-status")[-1]
        self.assertTrue(any("Stand van De Tekenaar onleesbaar" in n["tekst"] for n in laatste["nood"]))

    def test_werkwijze_en_doorgang(self):
        with open(os.path.join(RUNNER, "tekenaar.py"), encoding="utf-8") as f:
            self.assertIn("with ag.ronde(", f.read())                # N12
        spec = importlib.util.spec_from_file_location("nieuwe_agent", os.path.join(RUNNER, "nieuwe-agent.py"))
        na = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(na)
        kaart = dict(naam="tekenaar", label="De Tekenaar", rol="x", mandaat="x", cadans="elke week", mag=["a"], grenzen=["b"])
        self.assertEqual(na.controleer(kaart, self.nep.werkwijze), [])
        nooit, mehdi = bord.grenzen(self.nep.werkwijze)
        self.assertTrue(any("projectmap" in n for n in nooit))


class Hulpscript(unittest.TestCase):
    def test_lijst_pagineert_en_filtert(self):
        paginas = {
            ("files/list_folder", S): {"entries": [
                {".tag": "file", "id": "id:aaaaaa1", "name": "BA_x_P_N.pdf", "path_display": S + "/9901 x/BA_x_P_N.pdf",
                 "content_hash": "h", "server_modified": "2026-10-19T08:00:00Z"},
                {".tag": "file", "id": "id:aaaaaa2", "name": "plan.pdf", "path_display": S + "/9901 x/plan.pdf"},
                {".tag": "folder", "id": "id:aaaaaa3", "name": "9901 x"},
                {".tag": "folder", "id": "id:aaaaaa4", "name": "oud", "path_display": S + "/oud",
                 "sharing_info": {"no_access": True, "read_only": True}}], "has_more": True, "cursor": "s1"},
            ("files/list_folder/continue", "s1"): {"entries": [
                {".tag": "deleted", "name": "oud.dwg", "path_lower": S.lower() + "/oud.dwg"},
                {".tag": "deleted", "name": "9800 weg v1.2", "path_lower": S.lower() + "/9800 weg v1.2"}],
                "has_more": False, "cursor": "s2"},
            ("files/list_folder/continue", "verlopen"): urllib.error.HTTPError("u", 409, "reset", {}, None),
            ("files/list_folder", L): {"entries": [], "has_more": False, "cursor": "l1"},
        }

        def rpc(pad, body):
            antwoord = paginas[(pad, body.get("path") or body.get("cursor"))]
            if isinstance(antwoord, Exception):
                raise antwoord
            return antwoord

        uit = ba_plannen.lijst({"light": "verlopen"}, rpc=rpc)
        self.assertEqual(uit["cursors"], {"standaard": "s2", "light": "l1"})
        self.assertEqual(uit["volledig"], {"standaard": True, "light": True})
        self.assertEqual([w["soort"] for w in uit["wijzigingen"]], ["bestand", "weg", "weg"])
        self.assertEqual(uit["wijzigingen"][0]["hash"], "h")
        self.assertEqual(uit["wijzigingen"][2]["pad"], S.lower() + "/9800 weg v1.2")   # DT11: map met een punt
        self.assertEqual(uit["geen_toegang"], [{"basis": "standaard", "pad": S + "/oud"}])

    def test_haal_alleen_ba_plannen_in_de_projectmappen(self):
        def meta(naam, pad, grootte=10):
            return lambda p, b: {".tag": "file", "name": naam, "path_lower": pad.lower(), "size": grootte}
        download = lambda pad, maximum: b"%PDF"  # noqa: E731
        self.assertEqual(ba_plannen.haal("id:aaaaaa1", meta("BA_x_P_N.pdf", S + "/9901/BA_x_P_N.pdf"), download), b"%PDF")
        with self.assertRaises(PermissionError):
            ba_plannen.haal("id:aaaaaa1", meta("contract.pdf", S + "/9901/contract.pdf"), download)
        with self.assertRaises(PermissionError):
            ba_plannen.haal("id:aaaaaa1", meta("BA_x_P_N.pdf", "/Work All/o01. Sales/BA_x_P_N.pdf"), download)
        with self.assertRaises(PermissionError):
            ba_plannen.haal("id:aaaaaa1", lambda p, b: None, download)
        with self.assertRaises(ValueError):
            ba_plannen.haal("/Work All/geheim.pdf; rm -rf", meta("BA_x.pdf", S + "/BA_x.pdf"), download)
        with self.assertRaises(ba_plannen.TeGroot):                     # DT07: uitgang 5, niet 4
            ba_plannen.haal("id:aaaaaa1", meta("BA_x_P_N.pdf", S + "/9901/BA_x_P_N.pdf", 10 ** 9), download)


if __name__ == "__main__":
    unittest.main(verbosity=2)
