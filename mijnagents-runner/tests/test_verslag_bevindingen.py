"""Grendel: een verslag van bevindingen is geen werfverslag.

Gebeurd met dossier 2309 (Stockemstraat 15, Huldenberg): het bezoek van 3 juni 2026 voor gebreken na werken van een
derde (Roofconcept) kwam op het bord als 'werfbezoek 1' en de schrijver maakte acht keer '2309-1 werfverslag (concept)'
met veiligheidstekst, volgend werfbezoek en akkoord binnen vijf dagen. Mehdi, 21-10-2026: "is niet een WV maar een
verslag van bevinding". Deze toetsen falen zodra zo'n bezoek weer een werfverslagnummer krijgt, naar de werfapp gaat
of de opmaak van een werfverslag krijgt.
"""
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import sjabloon_bevindingen as vb  # noqa: E402
import sjabloon_werfverslag as sj  # noqa: E402
import werfapp  # noqa: E402
import werfregister  # noqa: E402
import werfregistratie  # noqa: E402
import werfverslag_voorbereider as V  # noqa: E402

MAP = "/Work All/01. H-A WORK/0 H-A Light projects/5. H-A light SITE VISITS/9999 Proefstraat 1/3. Implementation & Site Control/5. Site Reports"


def docx_tekst(b):
    from docx import Document
    d = Document(io.BytesIO(b))
    tekst = [p.text for p in d.paragraphs] + [c.text for t in d.tables for r in t.rows for c in r.cells]
    for s in d.sections:
        tekst += [p.text for p in s.footer.paragraphs] + [c.text for t in s.footer.tables for r in t.rows for c in r.cells]
    return "\n".join(tekst)


def proef_verslag():
    """Zoals de schrijver het aanlevert: een vast werfpunt en twee eigen vaststellingen."""
    return {"dossier": "9999", "bezoek": "VB1", "soort_bezoek": "bevindingen", "adres": "Proefstraat 1, 3000 Leuven",
            "datum": "2026-06-03", "opgemaakt": "2026-10-21", "verslagtype": vb.SOORT, "status_nl": "Bezoek na werken van een derde.",
            "bronnen_kort": "1 document(en), 2 foto's en 1 opname(s) in de bezoekmap",
            "categorieen": [{"naam": "Algemeen", "punten": [{"titel": "Werfbezoeken", "doorlopend": True, "fotos": [], "tekst_nl": "vast"}]},
                            {"naam": "Dakkapel", "punten": [
                                {"titel": "Zinken dorpel oneffen", "tekst_nl": "Water blijft staan.", "bron": "1027 a.jpg", "fotos": ["1027 a.jpg"]},
                                {"titel": "Naad aan het raam", "tekst_nl": "Open naad.", "bron": "", "fotos": []}]}],
            "raming": [{"onderdeel": "Dakkapel", "herstelling": "dorpel vernieuwen", "raming": "(raming door de architect in te vullen)"}]}


class Sjabloon(unittest.TestCase):
    def test_leeg_sjabloon_is_geen_werfverslag(self):
        tekst = docx_tekst(vb.naar_docx(vb.leeg("9999", "Proefstraat 1")))
        self.assertIn("Verslag van bevindingen", tekst)
        self.assertIn("9999 | Verslag van bevindingen", tekst)
        for werfverslagtekst in ("Werfverslag", sj.VAST_VEILIGHEID[:40], "Peeters-Borsus", "vijf kalenderdagen", "Volgend werfbezoek"):
            self.assertNotIn(werfverslagtekst, tekst)

    def test_herkomst_en_raming(self):
        self.assertEqual(vb._herkomst("V + B"), "eigen vaststelling ter plaatse, verklaring van de bouwheer")
        self.assertEqual(vb._herkomst("transcript.txt 00:22:30"), "transcript.txt 00:22:30")
        self.assertEqual(vb._herkomst(""), "(na te kijken)")
        v = {"raming": [{"van": 100, "tot": 200}, {"van": 7000, "tot": 9000, "variant": True}, {"tekst": "open"}]}
        self.assertEqual(vb.raming_totaal(v), (100, 200))

    def test_proef_van_de_schrijver_wordt_verslag_van_bevindingen(self):
        v = vb.uit_werfproef(proef_verslag())
        self.assertEqual(v["referentie"], "9999-VB1")
        nrs = [b["nr"] for o in v["onderdelen"] for b in o["bevindingen"]]
        self.assertEqual(nrs, ["B1", "B2"])                     # het vaste werfpunt valt weg
        self.assertEqual(v["onderdelen"][0]["bevindingen"][1]["herkomst"], "(na te kijken)")
        self.assertEqual(vb.als_werfverslag(v)["categorieen"][0]["punten"][0]["fotos"], ["1027 a.jpg"])
        md = vb.naar_markdown(v)
        self.assertIn("(raming door de architect in te vullen)", md)
        self.assertGreater(sj.telling_open(md)["in_te_vullen"], 0)


class Nummering(unittest.TestCase):
    def test_bevindingen_telt_niet_als_werfbezoek(self):
        bezoeken = [{"map": MAP + "/20260603", "datum": "2026-06-03"}, {"map": MAP + "/20260910", "datum": "2026-09-10"}]
        rijen = [{"bezoekmap": MAP + "/20260603", "keuzes": {"verslagtype": "verslag_bevindingen"}},
                 {"bezoekmap": MAP + "/20260910", "keuzes": {"verslagtype": "werfverslag"}}]
        V.nummer_bezoeken(bezoeken, "", V.bevindingenmappen(rijen))
        self.assertEqual([(b["soort_bezoek"], b["nr_label"], b["werfnr"]) for b in bezoeken],
                         [("bevindingen", "VB1", 0), ("werfbezoek", "1", 1)])

    def test_zonder_keuze_blijft_de_nummering_zoals_ze_was(self):
        bezoeken = [{"map": MAP + "/20260603", "datum": "2026-06-03"}]
        V.nummer_bezoeken(bezoeken, "")
        self.assertEqual(bezoeken[0]["nr_label"], "1")

    def test_werfapp_weigert_een_vb_nummer(self):
        self.assertIsNone(werfapp.volgnummer("VB1"))

    def test_registratie_vraagt_geen_werfbezoeknummer_voor_bevindingen(self):
        geschreven = []

        def api(pad, payload=None):
            if pad.startswith("/bezoeken?"):
                return {"bezoeken": [], "meer": False}
            geschreven.append(payload)
            return {"bezoek": {"bezoek_id": "vb-1", "project_ref": "h-architects:9999", "status": "onzeker", "revisie": 1}}

        bezoeken = [{"map": MAP + "/20260603", "datum": "2026-06-03"}]
        with patch.object(werfregister, "call", side_effect=api):
            werfregistratie.koppel_voor_nummering(bezoeken, "9999", MAP, "", [], bevindingen={(MAP + "/20260603").casefold()})
        self.assertEqual(geschreven[0]["bezoektype"], "overig")
        self.assertEqual(bezoeken[0]["registratie"]["bezoek_id"], "vb-1")


if __name__ == "__main__":
    unittest.main()
