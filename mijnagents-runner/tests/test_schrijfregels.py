"""Grendel op de schrijfregels van het kantoor (schrijfregels.py).

Gebeurd op 22/23-10-2026 met het concept 2309 Verslag van bevindingen: het zei dat uit de stukken geen eerder bezoek
van het bureau bleek, noemde de beperking van de eigen opdracht, en verwees bij elke vaststelling naar de opname
"(opname 00:22:30)". Mehdi, 23-10-2026: dat mag nooit, ook niet "tegen de deontologie" of "de vorige architect is niet
geweest". Deze toets faalt zodra zo'n zin weer door het sjabloon komt, of zodra een gewone technische zin ten onrechte
geschrapt wordt.
"""
import io
import re
import sys
import zipfile
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import schrijfregels as S  # noqa: E402
import sjabloon_bevindingen as vb  # noqa: E402
import sjabloon_werfverslag as sj  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


# S1: niets over het eigen bureau
t, ing = S.toepassen("Uit de voorgelegde stukken blijkt geen eerder bezoek van het bureau aan de werken. Het bezoek vond plaats op vraag van de bouwheren.")
check("S1 'geen eerder bezoek van het bureau' geschrapt", "geen eerder bezoek" not in t and "schrijfregel S1" in t and "op vraag van de bouwheren" in t, t)
t, _ = S.toepassen("De opdracht is beperkt tot de vergunning, met hoogstens één controlebezoek tijdens de ruwbouwwerken.")
check("S1 'hoogstens één controlebezoek' geschrapt", "controlebezoek" not in t, t)
t, _ = S.toepassen("De architect is niet geweest tijdens de werken.")
check("S1 'architect is niet geweest' geschrapt", "niet geweest" not in t, t)
# S2: deontologie en Orde
t, ing = S.toepassen("Dit is tegen de deontologie. De Orde van Architecten schrijft voor dat de architect de werken volgt.")
check("S2 deontologie en Orde geschrapt", "deontolog" not in t.lower() and "orde van architecten" not in t.lower() and S.samenvatting(ing).get("S2") == 2, t)
# S3: collega
t, ing = S.toepassen("De vorige architect is nooit langsgekomen.")
check("S3 oordeel over collega geschrapt als S3", "langsgekomen" not in t and ing and ing[0][0] == "S3", (t, ing))
# S4: opname
t, ing = S.toepassen("Er blijft water staan (opname 00:22:30-00:23:16). Op de foto's staat water tegen het kader.")
check("S4 opnameverwijzing weg, zin blijft", t == "Er blijft water staan. Op de foto's staat water tegen het kader.", t)
t, _ = S.toepassen("Een kraan stond drie weken op de parking (mondeling, opname 00:30:06)")
check("S4 opname binnen haakjes weg, rest blijft", t == "Een kraan stond drie weken op de parking (mondeling)", t)
t, _ = S.toepassen("De architect nam 18 foto's en sprak zijn vaststellingen ter plaatse in. Een tijdstip tussen haakjes, zoals (opname 00:22:30), verwijst naar die opname van het bezoek. Het onderzoek was visueel.")
check("S4 zinnen over de opname weg, gewone zin blijft", t == "Het onderzoek was visueel.", t)
# S5: juridisch
t, _ = S.toepassen("De aannemer is aansprakelijk voor de schade.")
check("S5 aansprakelijkheid geschrapt", "aansprakelijk" not in t, t)
# gewone technische tekst blijft onaangeroerd
goed = ("De zinken dorpel vóór de drie raamelementen is niet vlak. Het afschot loopt naar de ramen toe in plaats van naar de "
        "dakgoot. Roofconcept was niet aanwezig en werd niet gehoord. Het bezoek van 3 juni 2026 vond plaats op vraag van de bouwheren.")
t, ing = S.toepassen(goed)
check("gewone vaststellingen blijven intact", t == goed and not ing, (t, ing))
# S6/S7 alleen met het profiel aankoopkeuring (volledig getoetst in test_aankoopkeuring.py)
check("S6 raakt een gewoon verslag niet", not S.controleer("De offerte bedraagt 4.500 EUR."))
check("S6 geldt in het profiel aankoopkeuring", any(r == "S6" for r, _ in S.controleer("De offerte bedraagt 4.500 EUR.", "aankoopkeuring")))
check("controleer meldt zonder te wijzigen", S.controleer("Dit is tegen de deontologie (opname 00:01:00).") and len(S.controleer(goed)) == 0)

# de sjablonen passen de regels toe op elk tekstveld
v = vb.leeg("2309", "Stockemstraat 15, 3040 Huldenberg")
v["rol"] = ["Uit de stukken blijkt geen eerder bezoek van het bureau aan de werken."]
v["werkwijze"] = ["De architect sprak zijn vaststellingen ter plaatse in. Het onderzoek was visueel."]
v["onderdelen"] = [{"naam": "Dakkapel", "bevindingen": [{"nr": "B1", "titel": "Zinken dorpel", "herkomst": "V",
                    "vaststelling": "De dorpel is niet vlak (opname 00:22:30-00:23:16).", "beoordeling": "Dit is tegen de deontologie.", "fotos": []}]}]
md = vb.naar_markdown(v)
check("bevindingen-markdown zonder opname en zonder deontologie", "opname" not in md.lower() and "deontolog" not in md.lower() and "geen eerder bezoek" not in md, md[:400])
check("bevindingen-markdown houdt de vaststelling", "De dorpel is niet vlak." in md)
check("sjabloon wijzigt het aangeleverde dict niet", "opname 00:22:30" in v["onderdelen"][0]["bevindingen"][0]["vaststelling"])
w = {"dossier": "2145", "bezoek": "3", "adres": "Teststraat 1", "datum": "2026-10-01", "opgemaakt": "2026-10-02", "soort_bezoek": "werfbezoek",
     "status_nl": "De werf loopt (opname 00:10:00).", "aanwezigen": [], "categorieen": [{"naam": "Ruwbouw", "punten": [
         {"nummer": "3.1", "titel": "Metselwerk", "datum": "2026-10-01", "tekst_nl": "Het metselwerk is waterpas (opname 00:12:00). De architect is eerder niet geweest.", "fotos": []}]}],
     "actiepunten": [], "volgend_bezoek": ""}
try:
    mdw = sj.naar_markdown(w)
    check("werfverslag-markdown zonder opname en zonder S1-zin", "opname" not in mdw.lower() and "eerder niet geweest" not in mdw and "waterpas" in mdw, mdw[:300])
except Exception as e:  # noqa: BLE001
    check("werfverslag-markdown bouwt", False, repr(e))

# --- review PR 92 (26-10-2026) ---

# V1/V6: de vaste kantoortekst (VGP-zin "De architect is niet aansprakelijk ...") is tekst van Mehdi: nooit geschrapt
vgp = next(p for p in sj.VASTE_PUNTEN if p["sleutel"] == "veiligheidscoordinatie")["nl"]
wd = dict(w, categorieen=[{"naam": c, "punten": [{"nummer": f"1.{i}", "titel": t, "datum": "", "tekst_nl": tekst, "verantwoordelijke": wie,
                                                  "fotos": [], "doorlopend": True, "bron": "vast punt kantoor"}]}
                          for i, (c, t, tekst, wie) in enumerate(sj.DOORLOPEND, 1)])
mdv = sj.naar_markdown(wd)
check("V1 vaste VGP-zin blijft in de werfverslag-markdown", "De architect is niet aansprakelijk" in mdv and "schrijfregel S5" not in mdv)
xml = zipfile.ZipFile(io.BytesIO(sj.naar_docx(wd))).read("word/document.xml").decode("utf8")
check("V1 vaste VGP-zin blijft in Word", "De architect is niet aansprakelijk" in xml and "schrijfregel S5" not in xml)
kopie = {"punten": [{"tekst_nl": vgp}, {"tekst_nl": "De aannemer is aansprakelijk voor de schade."}]}
ing = S.wacht(kopie, vast=sj.VASTE_TEKSTEN)
check("V1 wacht met vast: kantoortekst vrij, eigen S5-zin van de schrijver wel geschrapt",
      kopie["punten"][0]["tekst_nl"] == vgp and [r for r, _ in ing] == ["S5"], ing)
check("V1 wacht zonder vast (verslag_basis) werkt zoals voorheen", S.wacht({"t": "De aannemer is aansprakelijk."}) == [("S5", "De aannemer is aansprakelijk.")])
check("V1 voorbehoud van het verslag van bevindingen blijft", vb.VOORBEHOUD.split("\n")[2] in vb.naar_markdown(vb.leeg()))

# V4: S1 alleen over het eigen bureau, nooit over derden
derden = ["De veiligheidscoördinator is nog niet eerder langsgekomen op de werf.", "De EPB-verslaggever is niet eerder ter plaatse geweest.",
          "De ramenplaatser was vroeger niet aanwezig bij de werfvergadering.", "De landmeter is eerder niet gekomen.",
          "De architect stelt vast dat de dakwerker niet aanwezig was.", "Er is slechts één bezoek van de keurder voorzien."]
for zin in derden:
    check(f"V4 S1 laat derden staan: '{zin[:40]}'", S.toepassen(zin) == (zin, []), S.toepassen(zin))
for zin in ("De architect is niet eerder ter plaatse geweest.", "Het bureau heeft de werken nooit gecontroleerd.", "We waren niet eerder ter plaatse."):
    check(f"V4 S1 blijft voor het eigen bureau: '{zin[:40]}'", [r for r, _ in S.toepassen(zin)[1]] == ["S1"], S.toepassen(zin))

# V5/V12: S4 laat geen vaststelling spoorloos verdwijnen
for zin in ("Volgens de opname van de bestaande toestand is de muur 30 cm dik.", "Uit de opname van de bestaande toestand blijkt dat de balk doorbuigt."):
    check(f"V5 opmeting is geen opname: '{zin[:40]}'", S.toepassen(zin) == (zin, []), S.toepassen(zin))
t, ing = S.toepassen("Volgens de opname is de dorpel 3 cm te laag. De goot lekt.")
check("V12 'volgens de opname' zichtbaar gemarkeerd, zin in de ingrepen",
      t.startswith("(geschrapt: schrijfregel S4") and t.endswith("De goot lekt.") and ("S4", "Volgens de opname is de dorpel 3 cm te laag.") in ing, (t, ing))
t, ing = S.toepassen("De architect sprak zijn vaststellingen ter plaatse in: de dorpel is 3 cm te laag.")
check("V12 vaststelling na 'sprak ... in:' blijft", t == "De dorpel is 3 cm te laag." and ing == [("S4", "De architect sprak zijn vaststellingen ter plaatse in:")], (t, ing))
t, ing = S.toepassen("De architect nam 18 foto's en sprak zijn vaststellingen ter plaatse in. Het onderzoek was visueel.")
check("V12 een weggevallen opnamezin staat volledig in de ingrepen (logboek)", ("S4", "De architect nam 18 foto's en sprak zijn vaststellingen ter plaatse in.") in ing, ing)

# V16: 'in gebreke' in alle vormen is S5
for zin in ("De aannemer is in gebreke gebleven.", "De aannemer werd in gebreke gesteld.", "Een ingebrekestelling is nodig."):
    check(f"V16 S5 '{zin[:36]}'", any(r == "S5" for r, _ in S.controleer(zin)), S.controleer(zin))

# V11: herkomst in het verslag alleen V, B of S; het tijdstip blijft in het veld bron
wb = dict(w, categorieen=[{"naam": "Ramen", "punten": [{"nummer": "3.1", "titel": "Dorpel", "datum": "2026-10-01", "tekst_nl": "Er blijft water staan.",
                                                       "bron": "transcript.txt 00:22:30-00:23:16", "fotos": []}]}])
mdh = sj.naar_markdown(wb)
check("V11 werfverslag: Herkomst V zonder opnametijdstip", "Herkomst: V" in mdh and "00:22" not in mdh and "transcript" not in mdh, mdh[-900:])
xml = zipfile.ZipFile(io.BytesIO(sj.naar_docx(wb))).read("word/document.xml").decode("utf8")
check("V11 werfverslag Word zonder opnametijdstip", "00:22" not in xml and "transcript.txt" not in xml)
check("V11 bron in de gegevens ongewijzigd", wb["categorieen"][0]["punten"][0]["bron"] == "transcript.txt 00:22:30-00:23:16")
check("V11 herkomst-codes", [sj.herkomst(x) for x in ("IMG_1.jpg", "lastenboek.pdf", "verklaring bouwheer, transcript.txt 00:03:10", "V + B", "vast punt kantoor", "")]
      == ["V", "S", "B", "V + B", "vast punt kantoor", ""])
bvw = vb.uit_werfproef(dict(wb, categorieen=[{"naam": "Ramen", "punten": [dict(wb["categorieen"][0]["punten"][0], nummer="VB1.1")]}]))
mdb = vb.naar_markdown(bvw)
check("V11 bevindingen: herkomst eigen vaststelling, geen opnametijdstip", "herkomst: eigen vaststelling ter plaatse" in mdb and "00:22" not in mdb, mdb)
check("V11 bevindingen: bron met tijdstip blijft in de gegevens", bvw["onderdelen"][0]["bevindingen"][0]["bron"] == "transcript.txt 00:22:30-00:23:16")

# V7: fotonummers in de bevindingen-tekst zoals in de fotobijlage (alleen de foto's die er echt in staan)
bv7 = vb.leeg("2309", "Teststraat 1")
bv7["onderdelen"] = [{"naam": "Gevel", "bevindingen": [{"nr": "B1", "titel": "Dorpel", "herkomst": "V", "vaststelling": "x", "fotos": ["IMG_1.HEIC", "IMG_2.jpg"]},
                                                     {"nr": "B2", "titel": "Goot", "herkomst": "V", "vaststelling": "y", "fotos": ["IMG_3.jpg"]}]}]
beelden = {"IMG_2.jpg": b"a", "IMG_3.jpg": b"b"}
md7 = vb.naar_markdown(bv7, beelden)
bijlage = [bij for _, bij in vb._fotonummers(bv7, beelden)[1]]
check("V7 tekst en fotobijlage nummeren gelijk", "**B1 Dorpel** - herkomst: eigen vaststelling ter plaatse - foto 1" in md7
      and "**B2 Goot** - herkomst: eigen vaststelling ter plaatse - foto 2" in md7 and bijlage == ["B1 Dorpel", "B2 Goot"], (md7, bijlage))

# Het document voor Mehdi: elk voorbeeld Fout wordt echt geschrapt (met die regel), elk voorbeeld Goed blijft staan
doc = (HIER / "docs" / "Werfverslagen - schrijfregels v1.0.md").read_text(encoding="utf8")
regel = None
n_voorbeelden = 0
for lijn in doc.splitlines():
    m = re.match(r"\*\*(S\d)\.", lijn)
    if m:
        regel = m.group(1)
    m = re.match(r'- (Fout|Goed): "(.*?)"', lijn)
    if m and regel:
        n_voorbeelden += 1
        profiel = "aankoopkeuring" if regel in ("S6", "S7") else None
        uit, ing = S.toepassen(m.group(2), profiel=profiel)
        if m.group(1) == "Fout":
            # helemaal weg (geen rest zoals '200.'), of bij S4 alleen de verwijzing weg en de vaststelling zonder opname
            volledig = uit == S.MARKERING.format(regel=regel) or (regel == "S4" and not S.controleer(uit) and uit != m.group(2))
            check(f"document {regel} Fout wordt geschrapt: '{m.group(2)[:40]}'", ing and all(r == regel for r, _ in ing) and volledig, (uit, ing))
        else:
            check(f"document {regel} Goed blijft: '{m.group(2)[:40]}'", (uit, ing) == (m.group(2), []), (uit, ing))
check("document heeft voorbeelden voor elke regel", n_voorbeelden >= 14, n_voorbeelden)

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
