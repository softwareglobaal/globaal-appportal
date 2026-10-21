"""Offline ketenproeven voor barsten en scheuren: TKN-map, inventaris, pakket en proef.

Draaien: python3 -B mijnagents-runner/tests/test_verslag_barsten.py
Dropbox, bord en Claude zijn nagebootst; de pakketbestanden staan alleen in tijdelijke mappen.
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import stat
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

RUNNER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNNER))
sys.path.insert(0, str(RUNNER / "koppelingen"))
import verslag_basis as V  # noqa: E402

BASIS = "/Work/TKN BURO WORK/1 Projects"
MAPNAAM = "47035_Barsten & Scheuren_Proeflaan 23, 9998 Proefgem"
MAP = f"{BASIS}/2026/{MAPNAAM}"
DATUM = "2026-10-21"
ADRES = "Proeflaan 23, 9998 Proefgem"
FOTOS = f"{MAP}/1. Foto’s"
PLAUD = f"{MAP}/2. Plaud"
DOCUMENTEN = f"{MAP}/3.Documents"
MAIL = f"{MAP}/4.Email"
CONTRACT_HASH = "5cf96524a337fc36456166ab12bbf5303e16c6a2b59aedbf6747151e3f319509"
SOORT = V.vs.SOORTEN["barsten-scheuren"]
CONTRACT = V.vs.pakketcontract()


def rij(**wijzig):
    uit = {"id": 77, "uniek": "afspraak:bs77", "agent": SOORT["agent"], "dossier": "3999",
           "datum": DATUM, "adres": ADRES, "klant": "Proefklant", "titel": "BS bezoek Proeflaan",
           "start": f"{DATUM}T09:00:00+02:00", "einde": f"{DATUM}T10:00:00+02:00",
           "dossiermap": MAP, "bezoekmap": MAP, "pakket": {}, "taken": [], "stand": "voorbereid", "proef_pad": ""}
    uit.update(wijzig)
    return uit


class Dropbox:
    def __init__(self):
        self.mappen = set()
        self.bestanden = {}
        self.gewijzigd = {}
        self.revisies = {}
        self.uploads = []
        self.gelezene = []
        for pad in (MAP, FOTOS, PLAUD, DOCUMENTEN, MAIL, f"{FOTOS}/{DATUM} iPhone"):
            self.map(pad)

    def map(self, pad):
        huidig = pad.rstrip("/")
        while huidig and huidig != "/":
            self.mappen.add(huidig)
            huidig = os.path.dirname(huidig)

    def bestand(self, pad, data, gewijzigd="2026-10-21T08:30:00Z", rev="r1"):
        self.map(os.path.dirname(pad))
        self.bestanden[pad] = data
        self.gewijzigd[pad] = gewijzigd
        self.revisies[pad] = rev
        return self.entry(pad)

    def entry(self, pad):
        data = self.bestanden[pad]
        return {".tag": "file", "name": os.path.basename(pad), "path_display": pad,
                "path_lower": pad.lower(), "size": len(data), "server_modified": self.gewijzigd[pad],
                "rev": self.revisies[pad], "content_hash": hashlib.sha256(data).hexdigest()}

    def lijst(self, pad, recursief=False):
        if pad not in self.mappen:
            return None
        pad = pad.rstrip("/")
        kinderen = []
        for map_pad in sorted(self.mappen):
            if map_pad != pad and (map_pad.startswith(pad + "/") if recursief else os.path.dirname(map_pad) == pad):
                kinderen.append({".tag": "folder", "name": os.path.basename(map_pad),
                                 "path_display": map_pad, "path_lower": map_pad.lower()})
        for bestand in sorted(self.bestanden):
            if bestand.startswith(pad + "/") if recursief else os.path.dirname(bestand) == pad:
                kinderen.append(self.entry(bestand))
        return kinderen

    def download(self, pad, maximum=25_000_000):
        self.gelezene.append(("heel", pad))
        data = self.bestanden[pad]
        if len(data) > maximum:
            raise RuntimeError("downloadgrens overschreden")
        return data

    def download_kop(self, pad, n):
        self.gelezene.append(("kop", pad, n))
        return self.bestanden[pad][:n]

    def upload(self, pad, data):
        if os.path.dirname(pad) not in self.mappen:
            raise RuntimeError("doelmap bestaat niet")
        self.uploads.append(pad)
        self.bestand(pad, data)
        return pad


class Bord:
    def __init__(self, rijen=()):
        self.rijen = {r["uniek"]: dict(r) for r in rijen}
        self.bewaard = []
        self.taken = {}
        self.opgepakt = []

    def call(self, pad, payload=None, method=None):
        if pad.startswith("/api/verslagopdracht?"):
            q = parse_qs(urlsplit(pad).query)
            if "uniek" in q:
                r = self.rijen.get(q["uniek"][0])
                return {"rijen": [r] if r else []}
            if "id" in q:
                return {"rijen": [r for r in self.rijen.values() if r["id"] == int(q["id"][0])]}
            return {"rijen": list(self.rijen.values())}
        if pad == "/api/verslagopdracht":
            for wijziging in payload["rijen"]:
                self.bewaard.append(dict(wijziging))
                self.rijen[wijziging["uniek"]].update({k: v for k, v in wijziging.items() if k != "_alleen"})
            return {"ok": True}
        if pad.startswith("/api/klaarzet?"):
            uniek = parse_qs(urlsplit(pad).query).get("uniek", [""])[0]
            taak = self.taken.get(uniek)
            return {"items": [taak] if taak else []}
        raise AssertionError(f"onverwachte bordoproep: {pad}")

    def pak(self, kid, door):
        self.opgepakt.append((kid, door))


class Log:
    def __init__(self):
        self.regels = []
        self.hartslagen = []

    def log(self, onderwerp, stap, tekst, detail=""):
        self.regels.append((onderwerp, stap, tekst))

    def hartslag(self, status, **kw):
        self.hartslagen.append((status, kw))

    def log_verstuur(self):
        pass


def vul_basis(db, transcript=True, foto=True):
    if transcript:
        db.bestand(f"{PLAUD}/{DATUM} Plaud transcript.txt", b"Plaud-ID: of_123\n" + b"-" * 25 + b"\nVaststelling ter plaatse")
    if foto:
        db.bestand(f"{FOTOS}/{DATUM} iPhone/IMG_001.jpg", b"foto")


class DossierkeuzeEnInventaris(unittest.TestCase):
    def test_contract_en_dossierkeuze_zonder_valse_nummermatch(self):
        self.assertEqual(hashlib.sha256((RUNNER / "koppelingen/pakketcontract.json").read_bytes()).hexdigest(), CONTRACT_HASH)
        mappen = [(MAPNAAM, MAP), ("470350_Barsten & Scheuren_Andereweg 9", f"{BASIS}/2026/470350_Barsten & Scheuren_Andereweg 9")]
        gekozen, hoe, nood = V.kies_dossiermap(rij(dossier="47035"), mappen, SOORT)
        self.assertEqual((gekozen, nood), (MAP, None))
        self.assertIn("nummer bevestigt", hoe)
        gekozen, hoe, nood = V.kies_dossiermap(rij(), mappen, SOORT)
        self.assertEqual((gekozen, nood), (MAP, None))
        self.assertIn("agendanummer 3999", hoe)
        self.assertNotIn("470350", hoe)
        r = rij(dossier="", adres=ADRES)
        vervuiling = [("1 Mapstructuur_Barsten & Scheuren_Proeflaan 23", f"{BASIS}/2026/sjabloon"),
                     ("0. Archive", f"{BASIS}/2026/archief")]
        self.assertEqual(V.kies_dossiermap(r, vervuiling + mappen, SOORT)[0], MAP)
        for verkeerd in ("Proeflaan 231", "Proeflaan 23A", "Proefstraat 12"):
            naam = f"47099_Barsten & Scheuren_{verkeerd}, 9998 Proefgem"
            self.assertIsNone(V.kies_dossiermap(r, [(naam, f"{BASIS}/2026/{naam}")], SOORT)[0])
        for fout in (MAP + "/", MAP + "/extra", MAP.replace("/2026/", "/2026/../"), MAP.replace("/2026/", "//2026/")):
            self.assertEqual(V.vs.tkn_pad(fout, BASIS), "")

    def test_postcode_sta_dubbele_match_en_klantnaam_kiezen_niet(self):
        alleen_nummer = "3999_Barsten & Scheuren_Andereweg 9"
        nrpad = f"{BASIS}/2026/{alleen_nummer}"
        gekozen, _, nood = V.kies_dossiermap(rij(adres="Onbekendstraat 2"), [(alleen_nummer, nrpad)], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn("adres bevestigt dat niet", nood)
        postcode_map = "9998_Barsten & Scheuren_Andereweg 9"
        gekozen, hoe, _ = V.kies_dossiermap(rij(dossier="9998", adres="Onbekendstraat 2, 9998 Proefgem"),
                                             [(postcode_map, f"{BASIS}/2026/{postcode_map}")], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn("postcode", hoe)
        sta = "47035_STA_Proeflaan 23, 9998 Proefgem"
        gekozen, _, nood = V.kies_dossiermap(rij(), [(sta, f"{BASIS}/2026/{sta}")], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn("alleen de stabiliteitsmap", nood)
        self.assertEqual(V.kies_dossiermap(rij(), [(sta, f"{BASIS}/2026/{sta}"), (MAPNAAM, MAP)], SOORT)[0], MAP)
        zelfde = "47035_Barsten & Scheuren_Andereweg 9"
        gekozen, _, nood = V.kies_dossiermap(rij(dossier="47035"), [(MAPNAAM, MAP), (zelfde, f"{BASIS}/2026/{zelfde}")], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn("meerdere", nood)
        zelfde_adres = "47099_Barsten & Scheuren_Proeflaan 23, 9998 Proefgem"
        gekozen, _, nood = V.kies_dossiermap(rij(dossier=""), [(MAPNAAM, MAP),
            (zelfde_adres, f"{BASIS}/2026/{zelfde_adres}")], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn("meerdere barstenmappen op", nood)
        strijd = "3999_Barsten & Scheuren_Andereweg 9"
        gekozen, _, nood = V.kies_dossiermap(rij(), [(MAPNAAM, MAP), (strijd, f"{BASIS}/2026/{strijd}")], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn("wijst naar", nood)
        klant = "47099_Barsten & Scheuren_Andereweg 8, 9998 Proefgem"
        gekozen, _, _ = V.kies_dossiermap(rij(adres="Andereweg 9, 9998 Proefgem", klant="Proefklant 9998 Proefgem"),
                                            [(klant, f"{BASIS}/2026/{klant}")], SOORT)
        self.assertIsNone(gekozen)

    def test_adres_is_exacte_straat_en_postcode(self):
        achtervoegsel = "47036_Barsten & Scheuren_Oude Proeflaan 23, 9998 Proefgem"
        ander_postnummer = "47037_Barsten & Scheuren_Proeflaan 23, 8888 Anderhem"
        zonder_postnummer = "47038_Barsten & Scheuren_Proeflaan 23"
        kandidaten = [(naam, f"{BASIS}/2026/{naam}") for naam in
                      (achtervoegsel, ander_postnummer, zonder_postnummer)]
        gekozen, _, _ = V.kies_dossiermap(rij(dossier=""), kandidaten + [(MAPNAAM, MAP)], SOORT)
        self.assertEqual(gekozen, MAP)
        for naam in (achtervoegsel, ander_postnummer, zonder_postnummer):
            gekozen, _, nood = V.kies_dossiermap(rij(dossier=""), [(naam, f"{BASIS}/2026/{naam}")], SOORT)
            self.assertIsNone(gekozen, naam)
            self.assertIn("geen barstenmap" if naam == achtervoegsel else naam, nood)
        gekozen, _, nood = V.kies_dossiermap(rij(dossier="", adres="Proeflaan 23, 8888 Anderhem"),
                                              [(MAPNAAM, MAP)], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn(MAPNAAM, nood)

    def test_postcode_na_bus_wordt_gecontroleerd_en_bijna_treffer_gemeld(self):
        adres = "Proeflaan 23, bus 2, 9998 Proefgem"
        verkeerd = "47036_Barsten & Scheuren_Proeflaan 23, 8888 Anderhem"
        gekozen, hoe, nood = V.kies_dossiermap(rij(adres=adres, dossier="9998"),
                                                [(verkeerd, f"{BASIS}/2026/{verkeerd}"), (MAPNAAM, MAP)], SOORT)
        self.assertEqual((gekozen, nood), (MAP, None))
        self.assertIn("nummer is de postcode", hoe)
        gekozen, _, nood = V.kies_dossiermap(rij(adres=adres, dossier=""),
                                              [(verkeerd, f"{BASIS}/2026/{verkeerd}")], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn(verkeerd, nood)
        self.assertIn("postcode 9998", nood)

    def test_vijfcijferig_nummer_overrulet_tegenstrijdig_straatadres_niet(self):
        verkeerde_straat = "47035_Barsten & Scheuren_Andereweg 9, 9998 Proefgem"
        gekozen, _, nood = V.kies_dossiermap(rij(dossier="47035"),
                                              [(verkeerde_straat, f"{BASIS}/2026/{verkeerde_straat}")], SOORT)
        self.assertIsNone(gekozen)
        self.assertIn(verkeerde_straat, nood)
        self.assertIn("adres bevestigt dat niet", nood)

    def test_postcode_en_gemeente_zonder_straat_kiezen_geen_dossier(self):
        for adres in ("9998 Proefgem, België", "8888 Anderhem"):
            with self.subTest(adres=adres):
                self.assertEqual(V.vs.straat_nummer(adres), "")
                gekozen, _, nood = V.kies_dossiermap(rij(dossier="", adres=adres), [(MAPNAAM, MAP)], SOORT)
                self.assertIsNone(gekozen)
                self.assertIn("geen barstenmap", nood)
                gekozen, _, nood = V.kies_dossiermap(rij(dossier="47035", adres=adres), [(MAPNAAM, MAP)], SOORT)
                self.assertIsNone(gekozen)
                self.assertIn(MAPNAAM, nood)
                self.assertIn("adres bevestigt dat niet", nood)

    def test_uniek_nummer_lost_dubbele_adresmatch_op(self):
        dubbel = "47099_Barsten & Scheuren_Proeflaan 23, 9998 Proefgem"
        gekozen, hoe, nood = V.kies_dossiermap(rij(dossier="47035"),
                                                [(MAPNAAM, MAP), (dubbel, f"{BASIS}/2026/{dubbel}")], SOORT)
        self.assertEqual((gekozen, nood), (MAP, None))
        self.assertIn("nummer bevestigt", hoe)

    def test_zoekt_huidig_bezoekjaar_vorig_jaar_en_eist_submappen(self):
        db = Dropbox()
        agent = V.VerslagAgent("barsten-scheuren")
        huidig = date.today().year
        zoekjaar = 2024 if huidig != 2024 else 2021
        met_jaar = rij(datum=f"{zoekjaar}-10-21", dossier="", dossiermap="", bezoekmap="")
        gevraagd = []
        origineel = db.lijst

        def lijst(pad, recursief=False):
            gevraagd.append(pad)
            return origineel(pad, recursief)

        with patch.object(V.bronnen, "lijst", lijst):
            agent.tkn_mappen(met_jaar)
            self.assertEqual(set(gevraagd), {f"{BASIS}/{zoekjaar - 1}", f"{BASIS}/{zoekjaar}", f"{BASIS}/{huidig}"})
            db.mappen.remove(PLAUD)
            gekozen, _ = agent.zoek_dossiermap(rij(dossiermap="", bezoekmap=""))
            self.assertIsNone(gekozen)
            self.assertIn("mist", agent._zoeknood)
            self.assertIn("2. plaud", agent._zoeknood)

    def test_inventaris_iphone_heic_jpg_plaud_fathom_en_mutatie(self):
        db = Dropbox()
        vul_basis(db)
        db.bestand(f"{FOTOS}/{DATUM} iPhone/IMG_001.heic", b"origineel")
        db.bestand(f"{FOTOS}/{DATUM} iPhone/IMG_002.jpg", b"tweede")
        db.bestand(f"{FOTOS}/{DATUM} Drone/DRONE.jpg", b"drone")
        db.bestand(f"{FOTOS}/2026-10-20 iPhone/oud.jpg", b"oud")
        db.bestand(f"{FOTOS}/{DATUM} iPhone/geluid.m4a", b"audio")
        db.bestand(f"{PLAUD}/{DATUM} samenvatting.txt", b"samenvatting")
        db.bestand(f"{DOCUMENTEN}/Fathom gesprek.docx", b"fathom")
        db.bestand(f"{DOCUMENTEN}/{DATUM} rapport (concept).docx", b"concept")
        db.bestand(f"{MAIL}/vraag.eml", b"mail", gewijzigd="2026-10-21T09:30:00Z")
        db.bestand(f"{MAIL}/screenshot.png", b"geen bijlage")
        inv = V.deel_in(db.lijst(MAP, recursief=True), MAP, DATUM, SOORT, CONTRACT)
        self.assertEqual(inv["submappen"], {"fotos": "1. Foto’s", "plaud": "2. Plaud",
                                            "documenten": "3.Documents", "mail": "4.Email"})
        self.assertEqual(sorted(e["name"] for e in inv["fotos"]), ["DRONE.jpg", "IMG_001.jpg", "IMG_002.jpg"])
        self.assertEqual([e["name"] for e in inv["fotos_iphone"]], ["IMG_001.jpg", "IMG_002.jpg"])
        self.assertEqual([e["name"] for e in inv["transcripten"]], [f"{DATUM} Plaud transcript.txt"])
        self.assertEqual([e["name"] for e in inv["opnames"]], ["geluid.m4a"])
        self.assertEqual([e["name"] for e in inv["documenten"]], ["Fathom gesprek.docx"])
        self.assertEqual([e["name"] for e in inv["mails"]], ["vraag.eml"])
        self.assertEqual([e["name"] for e in inv["proef"]], [f"{DATUM} rapport (concept).docx"])
        self.assertIn("oud.jpg", [e["name"] for e in inv["overig"]])
        self.assertEqual(inv["laatst_gewijzigd"], "2026-10-21T09:30:00Z")


def jpg(opnametijd=None):
    from PIL import Image
    beeld = Image.new("RGB", (8, 8), (123, 45, 67))
    uit = io.BytesIO()
    if opnametijd:
        exif = Image.Exif()
        exif[306] = opnametijd
        beeld.save(uit, format="JPEG", exif=exif)
    else:
        beeld.save(uit, format="JPEG")
    return uit.getvalue()


def pakket_bronnen():
    db = Dropbox()
    transcript = (f"Plaud-ID: of_test\nTranscript-Hash: oud\n" + "-" * 25 +
                  "\nScheur in de voorgevel.\nBreedte opmeten.").encode()
    db.bestand(f"{PLAUD}/{DATUM} Plaud transcript.txt", transcript)
    db.bestand(f"{FOTOS}/{DATUM} iPhone/Z_laat.jpg", jpg("2026:10:21 10:02:00"))
    db.bestand(f"{FOTOS}/{DATUM} iPhone/A_vroeg.jpg", jpg("2026:10:21 09:01:00"))
    db.bestand(f"{FOTOS}/{DATUM} iPhone/B_zonder.jpg", jpg())
    db.bestand(f"{MAIL}/vraag.eml", b"From: test@example.invalid\n\nMailtekst uitsluitend als bijlage")
    db.bestand(f"{DOCUMENTEN}/plan.pptx", b"synthetische pptx bijlage")
    db.bestand(f"{DOCUMENTEN}/rapport.pdf", b"synthetische pdf bijlage")
    inv = V.deel_in(db.lijst(MAP, recursief=True), MAP, DATUM, SOORT, CONTRACT)
    return db, inv, V.pakket_plan(rij(), inv, SOORT, CONTRACT)


class Pakket(unittest.TestCase):
    def test_plan_scheidt_invoer_en_bijlagen_en_houdt_meta_exact(self):
        db, inv, plan = pakket_bronnen()
        self.assertEqual(plan["naam"], "47035_2026-10-21")
        self.assertEqual(set(plan["meta"]), set(CONTRACT["meta_sleutels"]))
        self.assertEqual(set(plan["meta"]["bron"]), set(CONTRACT["bron_sleutels"]))
        self.assertEqual(plan["meta"]["projectnr"], "47035")
        self.assertEqual(plan["meta"]["bron"]["agendanummer"], "3999")
        self.assertEqual({b["rol"] for b in plan["bijlagen"]}, {"mail", "document"})
        self.assertIn(".pptx", {os.path.splitext(b["doel"])[1] for b in plan["bijlagen"]})
        oud_invoer, oud_bijlagen = plan["invoerhash"], plan["bijlagenhash"]
        db.bestand(f"{MAIL}/vraag.eml", b"From: test@example.invalid\n\nNieuwe mailtekst", rev="r2")
        nieuw = V.pakket_plan(rij(), V.deel_in(db.lijst(MAP, True), MAP, DATUM, SOORT, CONTRACT), SOORT, CONTRACT)
        self.assertEqual(nieuw["invoerhash"], oud_invoer)
        self.assertNotEqual(nieuw["bijlagenhash"], oud_bijlagen)
        te_groot = dict(inv["documenten"][0], size=CONTRACT["max_bestand_mb"] * 1_000_000 + 1)
        te_grote_inv = {**inv, "documenten": [te_groot]}
        beperkt = V.pakket_plan(rij(), te_grote_inv, SOORT, CONTRACT)
        self.assertNotIn(te_groot["path_display"], [b["entry"]["path_display"] for b in beperkt["bijlagen"]])
        self.assertIn(te_groot["path_display"], [x["dropbox"] for x in beperkt["overgeslagen"]])
        onbekend = db.bestand(f"{DOCUMENTEN}/onbekend.xyz", b"geen ondersteund formaat")
        met_onbekend = V.pakket_plan(rij(), V.deel_in(db.lijst(MAP, True), MAP, DATUM, SOORT, CONTRACT), SOORT, CONTRACT)
        self.assertIn(onbekend["path_display"], [x["dropbox"] for x in met_onbekend["overgeslagen"]])

    def test_meer_dan_99_bijlagen_per_type_worden_gemeld_en_niet_genummerd(self):
        db = Dropbox()
        vul_basis(db)
        for nummer in range(101):
            db.bestand(f"{MAIL}/bericht_{nummer:03d}.eml", b"synthetische mail")
            db.bestand(f"{DOCUMENTEN}/stuk_{nummer:03d}.pdf", b"synthetisch document")
        inv = V.deel_in(db.lijst(MAP, True), MAP, DATUM, SOORT, CONTRACT)
        plan = V.pakket_plan(rij(), inv, SOORT, CONTRACT)
        self.assertEqual(len(plan["bijlagen"]), 198)
        self.assertTrue(all(re.match(r"^(mail|doc)_\d{2}_", b["doel"])
                            for b in plan["bijlagen"]))
        self.assertEqual(len(plan["overgeslagen"]), 4)
        self.assertTrue(all("meer dan 99" in x["reden"] for x in plan["overgeslagen"]))

    def test_schrijft_atomaire_pakket_met_exif_bijlagen_en_rechten(self):
        from docx import Document
        db, _, plan = pakket_bronnen()
        nu = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(prefix="barsten-pakket-") as mapje:
            inbox = Path(mapje) / "inbox"
            oud = inbox / ".47035_2026-10-21.tmp-verweesd"
            oud.mkdir(parents=True)
            ouder = (nu - timedelta(hours=3)).timestamp()
            os.utime(oud, (ouder, ouder))
            jong = inbox / ".47035_2026-10-21.tmp-jong"
            jong.mkdir()
            jonger = (nu - timedelta(minutes=30)).timestamp()
            os.utime(jong, (jonger, jonger))
            vreemd = inbox / "niet-van-ons.tmp"
            vreemd.mkdir()
            uitslag = V.schrijf_pakket(plan, str(inbox), db.download, db.download_kop, nu)
            doel = Path(uitslag["pad"])
            self.assertEqual(uitslag["uitkomst"], "klaargezet")
            self.assertFalse(oud.exists())
            self.assertTrue(jong.is_dir(), "een recente eigen tijdelijke map blijft staan")
            self.assertTrue(vreemd.is_dir())
            self.assertTrue(V.toets_pakket(str(doel), CONTRACT))
            self.assertEqual(stat.S_IMODE(doel.stat().st_mode), 0o755)
            self.assertEqual(stat.S_IMODE((doel / "photos").stat().st_mode), 0o755)
            self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o644 for p in doel.rglob("*") if p.is_file()))
            meta = json.loads((doel / "meta.json").read_text())
            manifest = json.loads((doel / "manifest.json").read_text())
            self.assertEqual(meta, plan["meta"])
            self.assertEqual((manifest["invoerhash"], manifest["bijlagenhash"]),
                             (plan["invoerhash"], plan["bijlagenhash"]))
            bronnen = manifest["bronnen"]
            self.assertEqual([b["rol"] for b in bronnen].count("transcript"), 1)
            self.assertEqual([b["rol"] for b in bronnen].count("foto"), 3)
            self.assertEqual({b["rol"] for b in bronnen if b["rol"] in ("mail", "document")}, {"mail", "document"})
            fotos = [b for b in bronnen if b["rol"] == "foto"]
            self.assertEqual([b["opnametijd"] for b in fotos],
                             ["2026-10-21T09:01:00", "2026-10-21T10:02:00", None])
            self.assertEqual([Path(b["doel"]).name[:4] for b in fotos], ["001_", "002_", "003_"])
            self.assertTrue(any(b["doel"].endswith(".pptx") for b in bronnen))
            tekst = "\n".join(p.text for p in Document(doel / "Transcript.docx").paragraphs)
            self.assertIn("Scheur in de voorgevel", tekst)
            self.assertNotIn("Plaud-ID", tekst)
            self.assertNotIn("Transcript-Hash", tekst)
            self.assertNotIn("Mailtekst uitsluitend", tekst)
            eerste_hashes = {str(p.relative_to(doel)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in doel.rglob("*") if p.is_file()}
            goud = os.environ.get("BS_GOUD_UIT")
            if goud:
                uitvoer = Path(goud)
                uitvoer.mkdir(parents=True, exist_ok=True)
                kopie = uitvoer / doel.name
                if kopie.exists():
                    bestaande_hashes = {str(p.relative_to(kopie)): hashlib.sha256(p.read_bytes()).hexdigest()
                                         for p in kopie.rglob("*") if p.is_file()}
                    self.assertEqual(bestaande_hashes, eerste_hashes, "een bestaand gouden pakket wordt niet overschreven")
                else:
                    shutil.copytree(doel, kopie)
                self.assertEqual({str(p.relative_to(kopie)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in kopie.rglob("*") if p.is_file()}, eerste_hashes)
            gelezen = len(db.gelezene)
            zelfde = V.schrijf_pakket(plan, str(inbox), db.download, db.download_kop, nu)
            self.assertEqual((zelfde["uitkomst"], zelfde["pad"]), ("al klaargezet", str(doel)))
            self.assertEqual(len(db.gelezene), gelezen, "dezelfde invoer hoort niet opnieuw gedownload te worden")
            db.bestand(f"{FOTOS}/{DATUM} iPhone/C_nieuw.jpg", jpg("2026:10:21 10:10:00"), rev="r2")
            nieuw_inv = V.deel_in(db.lijst(MAP, True), MAP, DATUM, SOORT, CONTRACT)
            nieuw_plan = V.pakket_plan(rij(), nieuw_inv, SOORT, CONTRACT)
            tweede = V.schrijf_pakket(nieuw_plan, str(inbox), db.download, db.download_kop, nu)
            self.assertEqual((tweede["uitkomst"], tweede["naam"]), ("klaargezet", "47035_2026-10-21-2"))
            self.assertTrue(doel.is_dir(), "een nieuwe versie mag de vorige niet overschrijven")
            self.assertEqual({str(p.relative_to(doel)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in doel.rglob("*") if p.is_file()}, eerste_hashes)
            self.assertTrue(V.toets_pakket(tweede["pad"], CONTRACT))

    def test_fout_ruimt_alleen_eigen_tmp_op_en_rechten_worden_getoetst(self):
        db, _, plan = pakket_bronnen()
        nu = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(prefix="barsten-fout-") as mapje:
            inbox = Path(mapje) / "inbox"
            inbox.mkdir()
            vreemd = inbox / "onbekende-map"
            vreemd.mkdir()

            def kapot(pad):
                if pad.endswith("plan.pptx"):
                    raise RuntimeError("proeffout bij bijlage")
                return db.download(pad)

            with self.assertRaisesRegex(RuntimeError, "proeffout"):
                V.schrijf_pakket(plan, str(inbox), kapot, db.download_kop, nu)
            self.assertTrue(vreemd.is_dir())
            self.assertFalse(any(p.name.startswith(".47035_2026-10-21.tmp-") for p in inbox.iterdir()))
            self.assertFalse((inbox / "47035_2026-10-21").exists())
            echte_stat = os.stat

            class StatMetVerkeerdeEigenaar:
                def __init__(self, st):
                    self._st = st
                    self.st_uid = os.getuid() + 1

                def __getattr__(self, naam):
                    return getattr(self._st, naam)

            def verkeerde_eigenaar(pad, *args, **kwargs):
                st = echte_stat(pad, *args, **kwargs)
                return StatMetVerkeerdeEigenaar(st) if os.fspath(pad) == str(inbox) else st

            with patch.object(V.os, "stat", verkeerde_eigenaar):
                with self.assertRaisesRegex(PermissionError, "inbox"):
                    V.schrijf_pakket(plan, str(inbox), db.download, db.download_kop, nu)
            self.assertFalse((inbox / "47035_2026-10-21").exists())

    def test_toets_pakket_weigert_symlink_en_verkeerde_meta(self):
        db, _, plan = pakket_bronnen()
        nu = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(prefix="barsten-toets-") as mapje:
            uitslag = V.schrijf_pakket(plan, mapje, db.download, db.download_kop, nu)
            doel = Path(uitslag["pad"])
            (doel / "photos" / "link.jpg").symlink_to(doel / "meta.json")
            with self.assertRaisesRegex(ValueError, "symlink"):
                V.toets_pakket(str(doel), CONTRACT)
            (doel / "photos" / "link.jpg").unlink()
            verkeerde_naam = doel / "photos" / "ongeldige naam.jpg"
            verkeerde_naam.write_bytes(b"foto")
            with self.assertRaisesRegex(ValueError, "ongeldige bestandsnaam"):
                V.toets_pakket(str(doel), CONTRACT)
            verkeerde_naam.unlink()
            extra = doel / "extra.txt"
            extra.write_text("extra")
            with self.assertRaisesRegex(ValueError, "pakketwortel"):
                V.toets_pakket(str(doel), CONTRACT)
            extra.unlink()
            meta = json.loads((doel / "meta.json").read_text())
            meta["extra"] = "mag niet"
            (doel / "meta.json").write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError, "meta.json"):
                V.toets_pakket(str(doel), CONTRACT)

    def test_toets_pakket_weigert_bijlage_zonder_dashboardvoorvoegsel(self):
        db, _, plan = pakket_bronnen()
        nu = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(prefix="barsten-bijlagen-") as inbox:
            uitslag = V.schrijf_pakket(plan, inbox, db.download, db.download_kop, nu)
            doel = Path(uitslag["pad"])
            (doel / "bijlagen" / "mail_100_proef.eml").write_bytes(b"synthetische mail")
            with self.assertRaisesRegex(ValueError, "ongeldig bijlageformaat"):
                V.toets_pakket(str(doel), CONTRACT)

    def test_vijf_versies_blokkeren_zesde_zonder_oude_te_verwijderen(self):
        db, _, _ = pakket_bronnen()
        nu = datetime(2026, 10, 21, 13, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory(prefix="barsten-versies-") as inbox:
            namen = []
            for i in range(1, V.MAX_VERSIES + 2):
                inv = V.deel_in(db.lijst(MAP, True), MAP, DATUM, SOORT, CONTRACT)
                plan = V.pakket_plan(rij(), inv, SOORT, CONTRACT)
                uitslag = V.schrijf_pakket(plan, inbox, db.download, db.download_kop, nu)
                if i <= V.MAX_VERSIES:
                    self.assertEqual(uitslag["uitkomst"], "klaargezet")
                    namen.append(uitslag["naam"])
                    db.bestand(f"{FOTOS}/{DATUM} iPhone/nieuw_{i:02d}.jpg", jpg(), rev=f"r{i + 1}")
                else:
                    self.assertEqual(uitslag["uitkomst"], "grens")
            self.assertEqual(len({p.name for p in Path(inbox).iterdir() if p.is_dir()}), V.MAX_VERSIES)
            self.assertEqual(namen, ["47035_2026-10-21"] + [f"47035_2026-10-21-{i}" for i in range(2, 6)])
            self.assertTrue(all((Path(inbox) / n / "manifest.json").is_file() for n in namen))


class Klok(datetime):
    huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls.huidig.astimezone(tz) if tz else cls.huidig.replace(tzinfo=None)


class Rondes(unittest.TestCase):
    def setUp(self):
        self.db = Dropbox()
        vul_basis(self.db)
        self.board = Bord([rij(taken=[{"voor": "icloud-wacht", "uniek": "cc:bs77:icloud-wacht"},
                                     {"voor": "plaud-wacht", "uniek": "cc:bs77:plaud-wacht"}])])
        self.board.taken["cc:bs77:icloud-wacht"] = {"id": 99, "uniek": "cc:bs77:icloud-wacht",
                                                     "status": "opgepakt", "opgepakt_door": "icloud-wacht"}
        self.board.taken["cc:bs77:plaud-wacht"] = {"id": 100, "uniek": "cc:bs77:plaud-wacht", "status": "klaar"}
        self.log = Log()
        self.agent = V.VerslagAgent("barsten-scheuren")
        self.agent.ag = self.log
        self.pakketten = []

        def schrijver(plan, inbox, download, download_kop, nu):
            self.pakketten.append(plan)
            return {"uitkomst": "klaargezet", "naam": plan["naam"], "pad": "/nep-inbox/" + plan["naam"],
                    "invoerhash": plan["invoerhash"], "bijlagenhash": plan["bijlagenhash"],
                    "ts": nu.isoformat(), "fotos": len(plan["fotos"]), "bijlagen": len(plan["bijlagen"])}

        patches = [patch.object(V.bronnen, "lijst", self.db.lijst),
                   patch.object(V.bronnen, "download", self.db.download),
                   patch.object(V.bronnen, "download_kop", self.db.download_kop),
                   patch.object(V.bronnen, "upload", self.db.upload),
                   patch.object(V.bord, "call", self.board.call),
                   patch.object(V.bord, "klaargezet_voor", lambda *a, **kw: []),
                   patch.object(V.bord, "opgepakt", self.board.pak),
                   patch.object(V, "schrijf_pakket", schrijver),
                   patch.object(V, "datetime", Klok),
                   patch.object(V.wp, "_client", side_effect=AssertionError("ronde mag Claude niet aanroepen")),
                   patch.object(V.subprocess, "run", return_value=SimpleNamespace(stdout="test\n"))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_kandidaat_rust_open_taak_en_latere_mail(self):
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        self.agent.ronde()
        eerste = self.board.rijen["afspraak:bs77"]["pakket"]
        self.assertTrue(eerste["kandidaat"]["hash"])
        self.assertEqual(self.pakketten, [])
        Klok.huidig = datetime(2026, 10, 21, 11, 2, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(self.pakketten, [], "een open wachttaak houdt de overdracht tegen")
        self.board.taken["cc:bs77:plaud-wacht"]["status"] = "opgepakt"
        Klok.huidig = datetime(2026, 10, 21, 11, 3, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(len(self.pakketten), 1)
        overdracht = self.board.rijen["afspraak:bs77"]["pakket"]["overdracht"]
        self.assertEqual(overdracht["invoerhash"], self.pakketten[0]["invoerhash"])
        self.db.bestand(f"{MAIL}/later.eml", b"later bericht", gewijzigd="2026-10-21T11:04:00Z")
        Klok.huidig = datetime(2026, 10, 21, 11, 5, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(len(self.pakketten), 1, "mail na overdracht verandert de foto/transcript-invoer niet")
        self.assertEqual(self.board.rijen["afspraak:bs77"]["pakket"]["bijlagen_na_overdracht"], 1)
        self.assertTrue(any("nieuwe mail of document" in tekst for _, _, tekst in self.log.regels))
        self.assertFalse(self.db.uploads)

    def test_dronefoto_en_transcript_wachten_op_iphone_of_zes_uur(self):
        foto = f"{FOTOS}/{DATUM} iPhone/IMG_001.jpg"
        for opslag in (self.db.bestanden, self.db.gewijzigd, self.db.revisies):
            opslag.pop(foto)
        self.db.bestand(f"{FOTOS}/{DATUM} drone/DRONE_001.jpg", b"synthetische dronefoto")
        self.board.taken["cc:bs77:plaud-wacht"]["status"] = "opgepakt"
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        self.agent.ronde()
        Klok.huidig = datetime(2026, 10, 21, 11, 3, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(self.pakketten, [], "dronefoto's sluiten de iPhone-aanvoer niet vroegtijdig af")
        self.assertFalse(any("zonder iPhone-foto's" in n["tekst"] for n in
                             (self.log.hartslagen[-1][1].get("nood") or [])))
        Klok.huidig = datetime(2026, 10, 21, 15, 3, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(len(self.pakketten), 1, "na zes uur blijft overdracht zonder iPhone mogelijk")
        self.assertEqual([e["name"] for e in self.pakketten[0]["fotos"]], ["DRONE_001.jpg"])
        self.assertTrue(any("zonder iPhone-foto's" in n["tekst"] for n in
                            (self.log.hartslagen[-1][1].get("nood") or [])))

    def test_een_iphonefoto_zonder_afgeronde_fototaak_levert_niet_vroeg_over(self):
        self.board.rijen["afspraak:bs77"]["taken"] = [
            {"voor": "plaud-wacht", "uniek": "cc:bs77:plaud-wacht"}]
        self.board.taken.pop("cc:bs77:icloud-wacht")
        self.board.taken["cc:bs77:plaud-wacht"]["status"] = "opgepakt"
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        self.agent.ronde()
        Klok.huidig = datetime(2026, 10, 21, 11, 3, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(self.pakketten, [], "één iPhone-foto vóór de fototaak is geen levering")
        self.board.rijen["afspraak:bs77"]["taken"].append(
            {"voor": "icloud-wacht", "uniek": "cc:bs77:icloud-wacht"})
        self.board.taken["cc:bs77:icloud-wacht"] = {
            "id": 101, "uniek": "cc:bs77:icloud-wacht", "status": "klaar"}
        Klok.huidig = datetime(2026, 10, 21, 11, 4, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(self.pakketten, [], "ook een open fototaak bevestigt de levering niet")
        self.board.taken["cc:bs77:icloud-wacht"].update(
            status="opgepakt", opgepakt_door="icloud-wacht")
        Klok.huidig = datetime(2026, 10, 21, 11, 5, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(len(self.pakketten), 1)

    def test_partiele_iphone_levering_na_zes_uur_meldt_open_fototaak(self):
        self.board.taken["cc:bs77:icloud-wacht"]["status"] = "klaar"
        self.board.taken["cc:bs77:plaud-wacht"]["status"] = "opgepakt"
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        self.agent.ronde()
        Klok.huidig = datetime(2026, 10, 21, 11, 3, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(self.pakketten, [])
        Klok.huidig = datetime(2026, 10, 21, 15, 3, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(len(self.pakketten), 1)
        self.assertTrue(any("iCloud-wachttaak nog open" in n["tekst"] for n in
                            (self.log.hartslagen[-1][1].get("nood") or [])))

    def test_agentkeuze_blijft_na_overdracht_of_late_stand_vast(self):
        basisrij = self.board.rijen["afspraak:bs77"]
        basisrij["taken"] = []
        keuze = {"door": "agent", "pad": MAP, "hoe": "straat en huisnummer"}
        self.assertFalse(V.dossierkeuze_vast({**basisrij, "pakket": {"dossierkeuze": keuze}, "stand": "voorbereid"}))
        for pakket, stand in (({"dossierkeuze": keuze, "overdracht": {"invoerhash": "oud"}}, "voorbereid"),
                              ({"dossierkeuze": keuze}, "proef klaar")):
            with self.subTest(stand=stand, overdracht="overdracht" in pakket):
                basisrij["pakket"], basisrij["stand"] = pakket, stand
                self.assertTrue(V.dossierkeuze_vast(basisrij))
                Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
                with patch.object(self.agent, "zoek_dossiermap", side_effect=AssertionError("vaste keuze herzien")) as zoek:
                    self.agent.ronde()
                    zoek.assert_not_called()
                self.assertEqual(self.board.rijen["afspraak:bs77"]["dossiermap"], MAP)

    def test_recente_bron_stelt_overdracht_uit_en_nieuwe_foto_herstart_rust(self):
        self.board.taken["cc:bs77:plaud-wacht"]["status"] = "opgepakt"
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        self.agent.ronde()
        kandidaat = self.board.rijen["afspraak:bs77"]["pakket"]["kandidaat"]
        foto = f"{FOTOS}/{DATUM} iPhone/IMG_001.jpg"
        self.db.gewijzigd[foto] = "2026-10-21T10:30:00Z"
        Klok.huidig = datetime(2026, 10, 21, 11, 2, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(self.pakketten, [], "de laatste bronwijziging is nog geen uur oud")
        self.assertEqual(self.board.rijen["afspraak:bs77"]["pakket"]["kandidaat"]["hash"], kandidaat["hash"])
        self.db.bestand(f"{FOTOS}/{DATUM} iPhone/IMG_002.jpg", b"nieuwe foto", gewijzigd="2026-10-21T11:00:00Z")
        Klok.huidig = datetime(2026, 10, 21, 11, 3, tzinfo=timezone.utc)
        self.agent.ronde()
        nieuw = self.board.rijen["afspraak:bs77"]["pakket"]["kandidaat"]
        self.assertNotEqual(nieuw["hash"], kandidaat["hash"])
        self.assertEqual(self.pakketten, [])
        Klok.huidig = datetime(2026, 10, 21, 12, 5, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertEqual(len(self.pakketten), 1)
        self.assertEqual(len(self.pakketten[0]["fotos"]), 2)

    def test_foto_en_totaalgrens_blokkeren_overdracht(self):
        self.board.taken["cc:bs77:plaud-wacht"]["status"] = "opgepakt"
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        self.agent.ronde()
        Klok.huidig = datetime(2026, 10, 21, 11, 3, tzinfo=timezone.utc)
        for aanpassing in ({"max_fotos": 0}, {"max_totaal_mb": 0}):
            with self.subTest(grens=aanpassing), patch.object(V.vs, "pakketcontract", return_value={**CONTRACT, **aanpassing}):
                self.agent.ronde()
                self.assertFalse(self.pakketten)
                noden = self.log.hartslagen[-1][1].get("nood") or []
                self.assertTrue(any("boven de foto- of totaalgrens" in n["tekst"] for n in noden))

    def test_taakstatus_zes_uur_en_fout_in_een_rij(self):
        r = self.board.rijen["afspraak:bs77"]
        self.assertEqual(V.taken_dicht(r, datetime(2026, 10, 21, 10, tzinfo=timezone.utc),
                                      lambda uniek: {"items": [self.board.taken[uniek]]})[0], False)
        self.assertEqual(V.taken_dicht(r, datetime(2026, 10, 21, 15, tzinfo=timezone.utc),
                                      lambda uniek: {"items": [self.board.taken[uniek]]})[0], True)
        self.assertEqual(V.taken_dicht(r, datetime(2026, 10, 21, 10, tzinfo=timezone.utc),
                                      lambda uniek: (_ for _ in ()).throw(RuntimeError("bord onbereikbaar")))[0], False)
        ontbreekt = lambda uniek: {"items": []}
        self.assertEqual(V.taken_dicht(r, datetime(2026, 10, 21, 10, tzinfo=timezone.utc), ontbreekt)[0], False)
        self.assertEqual(V.taken_dicht(r, datetime(2026, 10, 21, 15, tzinfo=timezone.utc), ontbreekt)[0], True)
        self.board.taken["cc:bs77:icloud-wacht"]["opgepakt_door"] = "commandocentrum"
        self.board.taken["cc:bs77:plaud-wacht"]["status"] = "opgepakt"
        self.assertEqual(V.taken_dicht(r, datetime(2026, 10, 21, 10, tzinfo=timezone.utc),
                                      lambda uniek: {"items": [self.board.taken[uniek]]})[0], False)
        fout = rij(id=78, uniek="afspraak:kapot", datum=None)
        self.board.rijen[fout["uniek"]] = fout
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        self.agent.ronde()
        self.assertTrue(self.board.rijen["afspraak:bs77"]["pakket"].get("kandidaat"))
        self.assertTrue(any("ronde voor deze rij mislukt" in tekst for _, _, tekst in self.log.regels))
        self.assertEqual(self.log.hartslagen[-1][0], "waakt")

    def test_alleen_bordknop_mag_een_proef_starten(self):
        aangeroepen = []
        self.agent.proef = lambda r, onderwerp: aangeroepen.append(r["id"])
        taken = [{"id": 1, "soort": "opdracht", "titel": "proef 77", "van": "ander-agent"},
                 {"id": 2, "soort": "opdracht", "titel": "proef 77", "van": "bord:knop"}]
        with patch.object(V.bord, "klaargezet_voor", return_value=taken):
            self.assertEqual(self.agent.opdrachten(), 1)
        self.assertEqual(aangeroepen, [77])
        self.assertEqual({kid for kid, _ in self.board.opgepakt}, {1, 2})

    def test_droog_is_alleen_get_en_lijst_en_geeft_json_per_rij(self):
        uitvoer = io.StringIO()
        Klok.huidig = datetime(2026, 10, 21, 10, 0, tzinfo=timezone.utc)
        with patch.object(sys, "argv", ["verslag_basis.py", "--droog"]), \
             patch.object(V.bronnen, "download", side_effect=AssertionError("droog downloadt niet")), \
             patch.object(V.bronnen, "upload", side_effect=AssertionError("droog uploadt niet")), \
             patch.object(self.agent, "impulsen", side_effect=AssertionError("droog verwerkt geen impulsen")), \
             patch.object(self.agent, "opdrachten", side_effect=AssertionError("droog verwerkt geen opdrachten")), \
             patch.object(self.agent, "bewaar", side_effect=AssertionError("droog bewaart niets")), \
             patch.object(V, "schrijf_pakket", side_effect=AssertionError("droog schrijft geen pakket")), \
             patch.object(self.log, "log", side_effect=AssertionError("droog logt niets")), \
             patch.object(self.log, "log_verstuur", side_effect=AssertionError("droog verstuurt geen log")), \
             patch.object(self.log, "hartslag", side_effect=AssertionError("droog stuurt geen hartslag")), \
             patch.object(V.wp, "_client", side_effect=AssertionError("droog vraagt geen model")), \
             contextlib.redirect_stdout(uitvoer):
            self.agent.main()
        regels = [json.loads(x) for x in uitvoer.getvalue().splitlines() if x.strip()]
        self.assertEqual(len(regels), 1)
        self.assertEqual(regels[0]["dossiermap"]["gekozen"], MAP)
        self.assertEqual(regels[0]["pakketnaam"], "47035_2026-10-21")
        self.assertEqual(regels[0]["tellingen"]["fotos"], 1)
        self.assertEqual(regels[0]["tellingen"]["transcripten"], 1)
        self.assertFalse(self.board.bewaard)
        self.assertFalse(self.board.opgepakt)
        self.assertFalse(self.log.hartslagen)


class Model:
    def __init__(self):
        self.vragen = []
        self.messages = self

    def create(self, **kw):
        self.vragen.append(kw)
        return SimpleNamespace(stop_reason="tool_use", usage=SimpleNamespace(input_tokens=30, output_tokens=10))


class ProefEnLegacy(unittest.TestCase):
    def setUp(self):
        self.db = Dropbox()
        self.board = Bord([rij()])
        self.model = Model()
        self.antwoord = {"titel": "Concept barsten en scheuren", "hoofdstukken": [
            {"titel": "Vaststellingen", "tekst": "Scheur in de voorgevel", "punten": []}], "open_punten": []}
        self.log = Log()
        patches = [patch.object(V.bronnen, "lijst", self.db.lijst),
                   patch.object(V.bronnen, "download", self.db.download),
                   patch.object(V.bronnen, "download_kop", self.db.download_kop),
                   patch.object(V.bronnen, "upload", self.db.upload),
                   patch.object(V.bord, "call", self.board.call),
                   patch.object(V.wp, "_client", return_value=self.model),
                   patch.object(V.wp, "_tool", return_value=self.antwoord)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def test_transcript_van_150k_blijft_docs_en_mail_vallen_weg_en_concept_staat_in_documenten(self):
        eindteken = "EINDE_VAN_HET_TRANSCRIPT"
        transcript = ("Plaud-ID: of_123\n" + "-" * 25 + "\n" + "x" * 150000 + eindteken).encode()
        self.db.bestand(f"{PLAUD}/{DATUM} Plaud transcript.txt", transcript)
        self.db.bestand(f"{DOCUMENTEN}/historiek.txt", b"DOCUMENT_MOET_WEG" + b"d" * 100000)
        self.db.bestand(f"{MAIL}/brief.eml", b"MAIL_MOET_WEG" + b"m" * 60000)
        self.db.bestand(f"{FOTOS}/{DATUM} iPhone/IMG_001.jpg", jpg())
        agent = V.VerslagAgent("barsten-scheuren")
        agent.ag = self.log
        with patch.object(sys, "argv", ["verslag_basis.py", "--proef", "77"]):
            agent.main()  # uit een koud proces zonder eerdere ronde of inventariscache
        self.assertEqual(len(self.model.vragen), 1)
        inhoud = self.model.vragen[0]["messages"][0]["content"]
        self.assertIn(eindteken, inhoud)
        self.assertGreater(len(inhoud), 150000)
        self.assertNotIn("DOCUMENT_MOET_WEG", inhoud)
        self.assertNotIn("MAIL_MOET_WEG", inhoud)
        self.assertTrue(any("bron buiten proefbundel: historiek.txt" in tekst for _, _, tekst in self.log.regels))
        self.assertTrue(any("bron buiten proefbundel: brief.eml" in tekst for _, _, tekst in self.log.regels))
        uploads = self.db.uploads
        self.assertEqual(len(uploads), 2)
        self.assertTrue(all(p.startswith(DOCUMENTEN + "/") for p in uploads))
        self.assertTrue(any(p.endswith(".docx") for p in uploads))
        concept_md = next(self.db.bestanden[p].decode() for p in uploads if p.endswith(".md"))
        self.assertIn("- Dossier: 47035", concept_md)
        self.assertIn("- Agendanummer: 3999", concept_md)
        self.assertEqual(self.board.rijen["afspraak:bs77"]["stand"], "proef klaar")

    def test_zonder_documentenmap_geen_modelvraag_of_upload(self):
        self.db.mappen.remove(DOCUMENTEN)
        vul_basis(self.db)
        agent = V.VerslagAgent("barsten-scheuren")
        agent.ag = self.log
        with self.assertRaisesRegex(RuntimeError, "documentenmap ontbreekt"):
            agent.proef(self.board.rijen["afspraak:bs77"], "synthetisch bezoek")
        self.assertEqual(self.model.vragen, [])
        self.assertEqual(self.db.uploads, [])

    def test_transcript_alleen_boven_nieuwe_grens_stopt_voor_model(self):
        self.db.bestand(f"{PLAUD}/{DATUM} Plaud transcript.txt", b"x" * 201000)
        agent = V.VerslagAgent("barsten-scheuren")
        agent.ag = self.log
        with self.assertRaisesRegex(RuntimeError, "transcript alleen al boven de bronlimiet"):
            agent.proef(self.board.rijen["afspraak:bs77"], "synthetisch bezoek")
        self.assertEqual(self.model.vragen, [])
        self.assertEqual(self.db.uploads, [])

    def test_andere_verslagsoort_houdt_bezoekmap_en_oude_telling(self):
        dossiermap = "/Work All/02. UNABO/01. U-WORK/03. U-SAFETY/2531 Proefwerf"
        bezoekmap = f"{dossiermap}/_00. Communication/{DATUM} bezoek werf - veiligheidscoördinatie"
        for pad in (dossiermap, bezoekmap, bezoekmap + "/fotos"):
            self.db.map(pad)
        self.db.bestand(f"{bezoekmap}/fotos/IMG_001.jpg", jpg())
        self.db.bestand(f"{bezoekmap}/transcript.txt", b"Bespreking op de werf")
        self.db.bestand(f"{bezoekmap}/geluid.m4a", b"opname")
        self.db.bestand(f"{bezoekmap}/notities.md", b"Aantekeningen")
        self.db.bestand(f"{bezoekmap}/oud (concept).docx", b"concept")
        andere = V.VerslagAgent("veiligheidscoordinatie")
        andere.ag = self.log
        bezoek = rij(uniek="afspraak:vc", id=88, dossier="2531", dossiermap=dossiermap, bezoekmap=bezoekmap)
        self.board.rijen[bezoek["uniek"]] = bezoek
        pad, nieuw = andere.maak_bezoekmap(bezoek, dossiermap)
        self.assertEqual((pad, nieuw), (bezoekmap, False))
        self.assertEqual(self.db.uploads, [])
        telling = andere.meet_pakket(bezoek)
        self.assertEqual((telling["fotos"], telling["opnames"], telling["transcripten"],
                          telling["documenten"], telling["proef"]), (1, 1, 1, 1, 1))
        with patch.object(V.wp, "lees_bezoekmap", return_value=([{"naam": "transcript.txt", "tekst": "Bespreking"}], [], [])):
            andere.proef(bezoek, "legacy bezoek")
        self.assertEqual(len(self.model.vragen), 1)
        self.assertTrue(all(p.startswith(bezoekmap + "/") for p in self.db.uploads))
        concept_md = next(self.db.bestanden[p].decode() for p in self.db.uploads if p.endswith(".md"))
        self.assertIn("- Dossier: 2531", concept_md)
        self.assertNotIn("Agendanummer:", concept_md)


if __name__ == "__main__":
    resultaat = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print("alles geslaagd" if resultaat.wasSuccessful() else "proeven gefaald")
    sys.exit(0 if resultaat.wasSuccessful() else 1)
