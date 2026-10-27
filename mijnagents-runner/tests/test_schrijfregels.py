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

# V4, beslist na drie reviewrondes (26-10-2026): S1 is gelijk aan productie. Elke uitzondering voor derden liet een zin
# over het eigen bureau door ("... ; wel maar één bezoek van de landmeter", "de projectarchitect", "de keurder" van
# UNABO). Een zin zonder onderwerp over een derde wordt dus zichtbaar gemarkeerd; Mehdi zet hem zelf terug.
derden = ["De veiligheidscoördinator is nog niet eerder langsgekomen op de werf.", "De EPB-verslaggever is niet eerder ter plaatse geweest.",
          "De ramenplaatser was vroeger niet aanwezig bij de werfvergadering.", "De landmeter is eerder niet gekomen.",
          "De architect stelt vast dat de dakwerker niet aanwezig was.", "Er is slechts één bezoek van de keurder voorzien."]
for zin in derden:
    nieuw, ing = S.toepassen(zin)
    check(f"V4 zin over een derde zichtbaar gemarkeerd, nooit stil weg: '{zin[:40]}'",
          "schrijfregel S1" in nieuw and ing == [("S1", zin)], (nieuw, ing))
for zin in ("De architect is niet eerder ter plaatse geweest.", "Het bureau heeft de werken nooit gecontroleerd.", "We waren niet eerder ter plaatse."):
    check(f"V4 S1 blijft voor het eigen bureau: '{zin[:40]}'", [r for r, _ in S.toepassen(zin)[1]] == ["S1"], S.toepassen(zin))

# V5/V12: S4 laat geen vaststelling spoorloos verdwijnen
for zin in ("Volgens de opname van de bestaande toestand is de muur 30 cm dik.", "Uit de opname van de bestaande toestand blijkt dat de balk doorbuigt."):
    check(f"V5 opmeting is geen opname: '{zin[:40]}'", S.toepassen(zin) == (zin, []), S.toepassen(zin))
t, ing = S.toepassen("Volgens de opname is de dorpel 3 cm te laag. De goot lekt.")
check("V12 'volgens de opname' zichtbaar gemarkeerd, zin in de ingrepen",
      t.startswith("(geschrapt: schrijfregel S4") and t.endswith("De goot lekt.") and ("S4", "Volgens de opname is de dorpel 3 cm te laag.") in ing, (t, ing))
t, ing = S.toepassen("De architect sprak zijn vaststellingen ter plaatse in: de dorpel is 3 cm te laag.")
check("V12 een vaststelling na 'sprak ... in:' verdwijnt nooit stil: zichtbare markering, volledige zin in het logboek",
      t == S.MARKERING.format(regel="S4") and ing == [("S4", "De architect sprak zijn vaststellingen ter plaatse in: de dorpel is 3 cm te laag.")], (t, ing))
t, ing = S.toepassen("De architect nam 18 foto's en sprak zijn vaststellingen ter plaatse in. Het onderzoek was visueel.")
check("V12 een weggevallen opnamezin staat volledig in de ingrepen (logboek)", ("S4", "De architect nam 18 foto's en sprak zijn vaststellingen ter plaatse in.") in ing, ing)

# V16: 'in gebreke' in alle vormen is S5
for zin in ("De aannemer is in gebreke gebleven.", "De aannemer werd in gebreke gesteld.", "Een ingebrekestelling is nodig."):
    check(f"V16 S5 '{zin[:36]}'", any(r == "S5" for r, _ in S.controleer(zin)), S.controleer(zin))

# V11: herkomst in het verslag alleen V, B of S; het tijdstip blijft in het veld bron
wb = dict(w, categorieen=[{"naam": "Ramen", "punten": [{"nummer": "3.1", "titel": "Dorpel", "datum": "2026-10-01", "tekst_nl": "Er blijft water staan.",
                                                       "bron": "transcript.txt 00:22:30-00:23:16", "fotos": []}]}])
mdh = sj.naar_markdown(wb)
import re as _re  # noqa: E402
zichtbaar = _re.sub(r"\s*<!--.*?-->", "", mdh)
check("V11 werfverslag: Herkomst zonder opnametijdstip in de zichtbare tekst (18e review: geen geraden V)",
      "Herkomst: transcript.txt" in zichtbaar and "00:22" not in zichtbaar, mdh[-900:])
check("V11 werfverslag: de bron blijft bewaard achter de V en komt terug bij van_markdown",
      sj.van_markdown(mdh)["categorieen"][0]["punten"][0]["bron"] == "transcript.txt 00:22:30-00:23:16", mdh[-400:])
xml = zipfile.ZipFile(io.BytesIO(sj.naar_docx(wb))).read("word/document.xml").decode("utf8")
check("V11 werfverslag Word zonder opnametijdstip", "00:22" not in xml)
check("V11 bron in de gegevens ongewijzigd", wb["categorieen"][0]["punten"][0]["bron"] == "transcript.txt 00:22:30-00:23:16")
check("V11/zeventiende review: herkomst-codes, nooit een onjuiste V",
      [sj.herkomst(x) for x in ("IMG_1.jpg", "lastenboek.pdf", "verklaring bouwheer, transcript.txt 00:03:10", "V + B", "vast punt kantoor", "",
                               "transcript.txt 00:22:30", "opname 00:12:00", "transcript aannemer.txt 00:05:10",
                               "WhatsApp Image 2026-09-30 at 18.04.11.jpeg")]
      == ["IMG_1.jpg", "lastenboek.pdf", "verklaring bouwheer, transcript.txt", "V + B", "vast punt kantoor", "", "transcript.txt",
          "(na te kijken)", "transcript aannemer.txt", "WhatsApp Image 2026-09-30 at 18.04.11.jpeg"],
      [sj.herkomst(x) for x in ("IMG_1.jpg", "transcript aannemer.txt 00:05:10")])
bvw = vb.uit_werfproef(dict(wb, categorieen=[{"naam": "Ramen", "punten": [dict(wb["categorieen"][0]["punten"][0], nummer="VB1.1")]}]))
mdb = vb.naar_markdown(bvw)
check("V11 bevindingen: herkomst zonder opnametijdstip en zonder geraden 'eigen vaststelling'",
      "herkomst: transcript.txt" in mdb and "00:22" not in mdb and "eigen vaststelling ter plaatse - " not in mdb.split("Bevindingen")[-1], mdb)
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

# Tweede review 26-10-2026: S1 gaat voor volledigheid (een zin over het eigen bureau mag nooit door), met alleen een
# smalle uitzondering voor een zin over een derde; het gedrag voor aankoopkeuring en barsten blijft dat van productie.
for zin in ["De architect was op dat moment niet aanwezig.", "De architect was toen niet aanwezig.", "Het bureau was die dag niet aanwezig.",
            "De architect heeft die wapening niet gecontroleerd.",
            "De architect heeft, ondanks herhaalde vraag van de bouwheer, de werken niet opgevolgd.",
            "De architect heeft, volgens de bouwheer, zijn plicht verzuimd.", "De werf werd voordien niet bezocht door de architect.",
            "De architect werd pas na de werken aangesteld, hij was voordien niet ter plaatse.", "Mehdi Chegini was niet eerder ter plaatse.",
            "Het architectenbureau is niet eerder langsgekomen.", "Ik ben hier niet eerder geweest.",
            "De architectenovereenkomst voorziet slechts één controlebezoek.", "Het ereloon dekt maar één bezoek.",
            "De aannemer zegt dat de architect niet eerder ter plaatse was.", "De bouwheer meldt dat het bureau voordien niet geweest is.",
            "Uit de stukken blijkt geen eerder bezoek van het bureau; wel was er maar één bezoek van de landmeter.",
            "De aannemer verklaart dat de projectarchitect niet eerder ter plaatse kwam.",
            "De bouwheer zegt dat het kantoor niet eerder ter plaatse kwam.", "De aannemer zegt dat hij mij niet eerder ter plaatse heeft gezien.",
            "De eigenaar verklaart dat de architecte niet eerder ter plaatse was.", "De aannemer zegt dat Mehdi niet eerder ter plaatse was.",
            "De keurder van UNABO was niet eerder ter plaatse.", "De architect stelt vast dat de bouwheer zegt dat wij niet aanwezig waren."]:
    check(f"S1 blijft voor het eigen bureau: '{zin[:40]}'", any(r == "S1" for r, _ in S.controleer(zin))
          and any(r == "S1" for r, _ in S.controleer(zin, "aankoopkeuring")), S.controleer(zin))
for zin in ["Bij het bezoek van de architect was geen aannemer aanwezig.",
            "Indien de architect niet ter plaatse is, legt de aannemer de wapening fotografisch vast.",
            "Volgens de architect is er geen dampscherm aanwezig.", "Wij hebben de kelder niet bezocht wegens wateroverlast.",
            "Ondergetekende heeft het platte dak niet gecontroleerd wegens het ontbreken van een veilige toegang.",
            "We konden de kruipruimte niet bezoeken: het luik was dichtgeschroefd.", "We zien geen ventilatie aanwezig in de badkamer."]:
    check(f"S1 laat staan: '{zin[:40]}'", not S.controleer(zin) and not S.controleer(zin, "aankoopkeuring"), S.controleer(zin))
for zin in ["De raming bedraagt € 3.200 excl. btw (3.872 incl. btw).", "Herstel kost € 3.200 excl. btw, of 3.872 incl. btw."]:
    t6, _ = S.toepassen(zin, "aankoopkeuring")
    check(f"S6 geen restbedrag na een afkorting: '{zin[:30]}'", "3.872" not in t6 and "200" not in t6, t6)
for zin in ["De herstelkosten worden geraamd op 4500 tot 6000.", "Richtprijs: 8000 per woning."]:
    check(f"S6 kostenraming zonder euro: '{zin[:30]}'", any(r == "S6" for r, _ in S.controleer(zin, "aankoopkeuring")), S.controleer(zin, "aankoopkeuring"))
for zin in ["Het bouwmisdrijf verjaart na tien jaar.", "De overtreding kan niet meer verjaren.", "De verjaarde overtreding vraagt geen regularisatie."]:
    check(f"S7 elke vorm van verjaren: '{zin[:30]}'", any(r == "S7" for r, _ in S.controleer(zin, "aankoopkeuring")), S.controleer(zin, "aankoopkeuring"))
check("S7 een verjaardag is geen verjaring", not S.controleer("De verjaardag van de bouwheer viel op het bezoek.", "aankoopkeuring"))
for zin, verwacht in [("De architect sprak zijn vaststellingen ter plaatse in, het kader is 2 cm uit het lood.", S.MARKERING.format(regel="S4")),
                      ("De architect sprak zijn vaststellingen ter plaatse in; het kader is 2 cm uit het lood.", S.MARKERING.format(regel="S4")),
                      ("De architect sprak zijn vaststellingen ter plaatse in; de opname en het transcript zitten in de bezoekmap.",
                       S.MARKERING.format(regel="S4")),
                      ("De dorpel is 3 cm te laag; het tijdstip tussen haakjes verwijst naar de opname.", S.MARKERING.format(regel="S4")),
                      ("Volgens de opname bestaande toestand is de muur 30 cm dik.", "Volgens de opname bestaande toestand is de muur 30 cm dik."),
                      ("Uit de opname van de landmeter blijkt dat de perceelgrens 20 cm verschuift.",
                       "Uit de opname van de landmeter blijkt dat de perceelgrens 20 cm verschuift.")]:
    t4, _ = S.toepassen(zin)
    check(f"S4 vaststelling blijft: '{zin[:40]}'", t4 == verwacht, t4)
# Vaste kantoortekst per zin: ook een oudere bewoording van het punt rond dezelfde VGP-zin blijft staan; het veld bron ook.
vgp = "De architect is niet aansprakelijk voor slecht verankerde stellingen of het niet naleven van het VGP; werfinspecties zijn momentopnames."
oud = {"punten": [{"tekst_nl": "Werfinspecties: helmen en nagelverwijdering zijn verplicht. " + vgp, "bron": "transcript.txt (opname 00:22:30)"}]}
check("vaste zin blijft in een oudere bewoording en de bron blijft heel",
      not S.wacht(oud, vast=["Andere bewoording van het punt. " + vgp]) and vgp in oud["punten"][0]["tekst_nl"]
      and "00:22:30" in oud["punten"][0]["bron"], oud)
check("een eigen S5-zin van de schrijver gaat nog altijd weg", S.wacht({"t": "De aannemer is aansprakelijk."}, vast=[vgp]))
for b, code in [("EPB startverklaring.pdf", "EPB startverklaring.pdf"), ("Prestatieverklaring PIR-isolatie.pdf", "Prestatieverklaring PIR-isolatie.pdf"),
                ("verklaring bouwheer", "B"), ("mondeling", "B"), ("transcript.txt 00:22:30", "transcript.txt"), ("Lastenboek.pdf", "Lastenboek.pdf"),
                ("offerte bouwheer.pdf", "offerte bouwheer.pdf"), ("transcript.txt 12m30s", "transcript.txt")]:
    check(f"herkomst '{b}' is {code}", sj.herkomst(b) == code, sj.herkomst(b))

t4, ing4 = S.toepassen("De architect sprak zijn vaststellingen ter plaatse in, het kader is 2 cm uit het lood.")
check("S4 de gemarkeerde zin staat volledig in het logboek", ing4 == [("S4", "De architect sprak zijn vaststellingen ter plaatse in, het kader is 2 cm uit het lood.")], ing4)
pm = dict(w, categorieen=[{"naam": "Ramen", "punten": [{"nummer": "3.1", "titel": "Latei", "datum": "2026-10-01", "tekst_nl": "De latei ontbreekt.",
                                                       "bron": "transcript.txt 00:12:00\ntranscript.txt 00:14:30 ---> map", "fotos": []}]}])
mdm = sj.naar_markdown(pm)
pt = sj.van_markdown(mdm)["categorieen"][0]["punten"][0]
check("een bron over meer regels of met '-->' breekt het verborgen commentaar niet",
      pt["tekst_nl"] == "De latei ontbreekt." and "00:12:00" in pt["bron"] and "00:14:30" in pt["bron"], (pt, mdm[-300:]))

# De grendel zit ook in Word (naar_docx), niet alleen in de markdown.
try:
    import io as _io
    from docx import Document as _Doc
    def _woord(data):
        return " ".join(par.text for par in _Doc(_io.BytesIO(data)).paragraphs)
    ww = dict(w, categorieen=[{"naam": "Ruwbouw", "punten": [{"nummer": "3.1", "titel": "Metselwerk", "datum": "2026-10-01",
                                                          "tekst_nl": "Het metselwerk is waterpas (opname 00:12:00). De architect is eerder niet geweest.", "fotos": []}]}])
    tw = _woord(sj.naar_docx(ww))
    check("werfverslag-Word zonder opname en zonder S1-zin", "00:12" not in tw and "eerder niet geweest" not in tw and "waterpas" in tw, tw[:300])
    tb = _woord(vb.naar_docx(v))
    check("bevindingen-Word zonder opname en zonder deontologie", "opname 00:22" not in tb and "deontolog" not in tb.lower(), tb[:300])
except ImportError as e:
    check("python-docx beschikbaar voor de Word-toets", False, repr(e))

# Vierde review 26-10-2026
for tekst, blijft in [("De ramen worden geplaatst door Schrijnwerkerij Peeters BV. Volgens de opname zijn de dorpels 2 cm te laag.",
                       "De ramen worden geplaatst door Schrijnwerkerij Peeters BV."),
                      ("Stellingbouw Claes BV.\nHet tijdstip tussen haakjes verwijst naar de opname.", "Stellingbouw Claes BV."),
                      ("De werf wordt opgevolgd door Bouwbedrijf Janssens bv. Dit verwijst naar de opname.", "Bouwbedrijf Janssens bv."),
                      ("Volgens de opname plaatst Peeters BV. De dorpels zijn 2 cm te laag.", "De dorpels zijn 2 cm te laag."),
                      ("Peeters bv. 2 ramen zijn beschadigd en de leverancier is aansprakelijk.", "Peeters bv.")]:
    t5, _ = S.toepassen(tekst)
    check(f"firmanaam met BV blijft een eigen zin: '{blijft[:35]}'", blijft in t5, t5)
t5, ing5 = S.toepassen("De architect kwam om 14:30 aan en sprak zijn vaststellingen ter plaatse in. De goot lekt.")
check("S4 een kloktijd breekt de ingesproken-zin niet af", t5 == "De goot lekt." and "14:" not in t5, (t5, ing5))
for zin in ["Volgens de opname van het terreinbezoek is de dorpel 3 cm te laag.",
            "Uit de opname van het terreinbezoek blijkt dat de stelling niet verankerd is."]:
    check(f"S4 'terreinbezoek' is geen opmeting: '{zin[:40]}'", any(r == "S4" for r, _ in S.controleer(zin)), S.controleer(zin))
check("S4 'opname van het terrein' blijft een opmeting", not S.controleer("Volgens de opname van het terrein ligt de tuin 40 cm lager."))

# Vijfde review 26-10-2026: een tijdstip of een nieuwe regel na de ingesproken-zin laat geen brokstukken achter
for tekst, verwacht in [("De architect sprak zijn vaststellingen in tussen 00:00:00 en 00:45:12. De dorpel ligt te laag.", "De dorpel ligt te laag."),
                        ("De architect sprak zijn vaststellingen in om 10:15. De barst in de zijgevel is 2 mm breed.", "De barst in de zijgevel is 2 mm breed."),
                        ("De architect sprak zijn vaststellingen in van 00:02:10 tot 00:41:55.", ""),
                        ("De architect sprak zijn vaststellingen in om 11:05; de bouwheer was afwezig.", S.MARKERING.format(regel="S4")),
                        ("De architect sprak zijn vaststellingen ter plaatse in\nDe dakgoot lekt aan de achtergevel.", "De dakgoot lekt aan de achtergevel.")]:
    t5, _ = S.toepassen(tekst)
    check(f"S4 ingesproken-zin zonder brokstukken: '{tekst[38:70]}'", t5 == verwacht and not S.controleer(t5), t5)
check("S5 ook het meervoud ingebrekestellingen", any(r == "S5" for r, _ in S.controleer("De bouwheer stuurde twee ingebrekestellingen naar de aannemer.")))

# Zesde review 26-10-2026: S4 per zin; een markering of een buurzin wordt nooit aangetast
for tekst, verwacht in [
        ("Mehdi Chegini bezocht het goed op 3 juni 2026 en sprak zijn vaststellingen ter plaatse in tijdens een rondgang van 45 minuten. "
         "Een tijdstip tussen haakjes verwijst naar de opname. Het onderzoek was visueel.", S.MARKERING.format(regel="S4") + " Het onderzoek was visueel."),
        ("Noot: een tijdstip tussen haakjes verwijst naar de opname.", ""),
        ("De goot lekt. Een tijdstip tussen haakjes verwijst naar de opname; de dorpel ligt te laag.", "De goot lekt. " + S.MARKERING.format(regel="S4")),
        ("Wie schildert de plafonds? De architect sprak zijn vaststellingen ter plaatse in.", "Wie schildert de plafonds?"),
        ("De goot lekt aan de achtergevel! Een tijdstip tussen haakjes verwijst naar de opname.", "De goot lekt aan de achtergevel!"),
        ("Volgens de opname van de plaatsgesteldheid vóór de werken was de barst er al.", "Volgens de opname van de plaatsgesteldheid vóór de werken was de barst er al."),
        ("Blijkens de opname door de verzekeringsexpert is de schade beperkt.", "Blijkens de opname door de verzekeringsexpert is de schade beperkt."),
        ("Er blijft water staan (opname 00:22:30-00:23:16).\nRegel twee blijft.", "Er blijft water staan.\nRegel twee blijft.")]:
    t6, _ = S.toepassen(tekst)
    check(f"S4 per zin: '{tekst[:40]}'", t6 == verwacht, t6)
    check(f"S4 geen gebroken markering: '{tekst[:30]}'", t6.count("(geschrapt:") == t6.count("kantoor)"), t6)

# Mengtest: elke combinatie van drie lastige zinnen geeft hele markeringen, geen tijdstip en geen brokstuk van een tijdstip
import itertools as _it  # noqa: E402
POOL = ["De goot lekt.", "Wie schildert de plafonds?", "De dorpel ligt 2 cm te laag!", "Peeters BV.", "Het kost € 4.500 excl. btw.",
        "De architect sprak zijn vaststellingen in om 10:15.", "De architect sprak zijn vaststellingen in, de kil is open.",
        "Een tijdstip tussen haakjes verwijst naar de opname.", "Noot: dit verwijst naar de opname.",
        "Volgens de opname is de muur nat.", "Er blijft water staan (opname 00:22:30).", "De opname van de bestaande toestand klopt.",
        "De architect is eerder niet geweest.", "De aannemer is aansprakelijk."]
kapot = []
for combi in _it.product(POOL, repeat=3):
    tekst = " ".join(combi)
    uit, _ = S.toepassen(tekst)
    if (uit.count("(geschrapt:") != uit.count("kantoor)") or re.search(r"\d{1,2}:\d{2}", uit) or re.search(r"(?:^|\s)\d{1,2}\.\s", uit)
            or any(r == "S4" for r, _ in S.controleer(uit))):
        kapot.append((tekst, uit))
check(f"mengtest: {len(POOL) ** 3} combinaties zonder gebroken markering of tijdstip", not kapot, kapot[:3])

# Zevende review 26-10-2026: een weggevallen zin laat de regelovergang staan; 'verwijst naar de opname van de bestaande
# toestand' is een opmeting
for tekst, verwacht in [
        ("Rondgang met de aannemer:\n- De dorpel ligt 2 cm te laag. De architect sprak zijn vaststellingen ter plaatse in.\n- De dakgoot lekt.",
         "Rondgang met de aannemer:\n- De dorpel ligt 2 cm te laag.\n- De dakgoot lekt."),
        ("Alinea een. Een tijdstip tussen haakjes verwijst naar de opname.\n\nAlinea drie.", "Alinea een.\n\nAlinea drie."),
        ("A.\nDe architect sprak zijn vaststellingen in.\nB.", "A.\nB."),
        ("A.\nDe architect sprak zijn vaststellingen in.\n\nB.", "A.\n\nB."),
        ("Het uitvoeringsplan verwijst naar de opname van de bestaande toestand door de landmeter. De dorpel ligt goed.",
         "Het uitvoeringsplan verwijst naar de opname van de bestaande toestand door de landmeter. De dorpel ligt goed.")]:
    t7, _ = S.toepassen(tekst)
    check(f"S4 regels en opmeting: '{tekst[:35]}'", t7 == verwacht, repr(t7))
kapot = []
for combi in _it.product(POOL, repeat=3):
    for scheiding in ("\n", "\n\n- "):
        uit, _ = S.toepassen(scheiding.join(combi))
        regels_in, regels_uit = scheiding.join(combi).count("\n"), uit.count("\n")
        if uit.count("(geschrapt:") != uit.count("kantoor)") or re.search(r"\d{1,2}:\d{2}", uit) or regels_uit > regels_in:
            kapot.append((scheiding.join(combi), uit))
check(f"mengtest met regelovergangen: {2 * len(POOL) ** 3} combinaties heel", not kapot, kapot[:3])

# Achtste review 26-10-2026: de grendel is idempotent (de sjablonen passen hem een tweede keer toe), het restdeel na een
# legende wordt opnieuw getoetst, en de tijdstippen waar de legende naar verwijst gaan mee
for tekst, verwacht in [
        ("Volgens de opname is de scheur 1 mm breed; een tijdstip tussen haakjes verwijst naar de opname.", S.MARKERING.format(regel="S4")),
        ("De dakgoot boven de keuken lekt (00:12:30); het tijdstip verwijst naar de opname.", S.MARKERING.format(regel="S4")),
        ("De aannemer kwam aan (10:15). De goot lekt.", "De aannemer kwam aan (10:15). De goot lekt."),
        ("De aannemer is aansprakelijk.\n- De goot lekt.", S.MARKERING.format(regel="S5") + "\n- De goot lekt.")]:
    t8, _ = S.toepassen(tekst)
    check(f"S4/S5 achtste review: '{tekst[:35]}'", t8 == verwacht, repr(t8))
niet_idempotent = []
for combi in _it.product(POOL + ["Volgens de opname is de goot nat; een tijdstip tussen haakjes verwijst naar de opname."], repeat=3):
    for scheiding in (" ", "\n"):
        for profiel in (None, "aankoopkeuring"):
            een, _ = S.toepassen(scheiding.join(combi), profiel)
            twee, ing2 = S.toepassen(een, profiel)
            if een != twee or ing2:
                niet_idempotent.append((scheiding.join(combi), een, twee))
check("de grendel is idempotent: een tweede doorgang verandert niets en meldt niets", not niet_idempotent, niet_idempotent[:2])

# Negende review 26-10-2026: een legendezin valt weg als hij alleen over de opname gaat, anders zichtbaar gemarkeerd (geen
# brokstukken als "Mm:ss)"); een harde regelovergang midden in een zin breekt de zin niet; de bron in het verslag van
# bevindingen toont geen opname of tijdstip
for tekst, verwacht in [
        ("Visueel onderzoek op 3 juni 2026. Een tijdstip tussen haakjes (uu:mm:ss) verwijst naar de opname van het plaatsbezoek.",
         "Visueel onderzoek op 3 juni 2026."),
        ("Een tijdstip tussen haakjes verwijst naar de opname; zo kan Mehdi elke vaststelling in de opname terugvinden.", ""),
        ("Een tijdstip tussen haakjes (uu:mm:ss) geeft het moment in de opname van het plaatsbezoek aan.", ""),
        ("De architect nam 42 foto's en sprak zijn vaststellingen\nter plaatse in. Volgens de\nopname is de dorpel 3 cm te laag.", S.MARKERING.format(regel="S4")),
        ("Een tijdstip tussen\nhaakjes verwijst naar de opname.", ""),
        ("Ruwbouw loopt.\nDe dakwerken starten volgende week.", "Ruwbouw loopt.\nDe dakwerken starten volgende week.")]:
    t9, _ = S.toepassen(tekst)
    check(f"S4 negende review: '{tekst[:35]}'", t9 == verwacht and S.toepassen(t9)[0] == t9, repr(t9))
for bron, verwacht in [("opname 00:31:10", ""), ("factuur 2026-114, zie opname 00:12:05", "factuur 2026-114"),
                       ("transcript.txt 00:12:00-00:12:40", "transcript.txt"), ("offerte Peeters 2026-03", "offerte Peeters 2026-03")]:
    check(f"bron_zichtbaar '{bron}'", S.bron_zichtbaar(bron) == verwacht, S.bron_zichtbaar(bron))
vg = vb.leeg("2309", "Stockemstraat 15")
vg["gemeld"] = [{"punt": "Bij hevige regen loopt water binnen langs het dakraam.", "bron": "opname 00:31:10"}]
vg["posten"] = [{"post": "Dakraam plaatsen", "bron": "factuur 2026-114, zie opname 00:12:05", "bedrag": "", "opmerking": ""}]
mdg = vb.naar_markdown(vg)
check("bevindingen: gemeld en posten tonen geen opname of tijdstip", "00:31" not in mdg and "00:12" not in mdg and "factuur 2026-114" in mdg, mdg[-500:])

# Tiende review 26-10-2026: een opsomming over meerdere regels (regels op ; of :) blijft een reeks eigen zinnen
t10, _ = S.toepassen("Aan de achtergevel werden genoteerd:\nbarst B1 boven het keukenraam, 0,3 mm, diagonaal;\nbarst B2 in de linkerhoek, 1 mm, "
                     "verticaal;\nde aannemer van de buren is aansprakelijk voor beide barsten.")
check("opsomming: de metingen blijven, alleen de S5-regel wordt gemarkeerd",
      "0,3 mm" in t10 and "1 mm" in t10 and "schrijfregel S5" in t10 and "aansprakelijk" not in t10, t10)
t10, _ = S.toepassen("Bij de rondgang werd vastgesteld:\nde zinken dakgoot lekt;\nde pannen zijn verweerd;\nde herstelkost wordt geraamd op ca. € 2.500.",
                     "aankoopkeuring")
check("opsomming aankoopkeuring: de vaststellingen blijven, het bedrag gaat weg",
      "dakgoot lekt" in t10 and "verweerd" in t10 and "2.500" not in t10 and "500" not in t10, t10)

# Elfde review 26-10-2026: elke regelovergang sluit een zin af (zoals productie); een opsomming zonder leesteken of met
# komma's verliest geen regels door één verboden regel
for tekst, profiel, moeten_blijven, weg in [
        ("Aan de achtergevel werden genoteerd:\nbarst B1 boven het keukenraam, 0,3 mm, diagonaal\nbarst B2 in de linkerhoek, 1 mm, verticaal\n"
         "de aannemer van de buren is aansprakelijk voor beide barsten.", None, ["0,3 mm", "1 mm"], "aansprakelijk"),
        ("Bij de rondgang werd vastgesteld:\nde zinken dakgoot lekt\nde pannen zijn verweerd\nde veranda is stedenbouwkundig verjaard.",
         "aankoopkeuring", ["dakgoot lekt", "pannen zijn verweerd"], "verjaard"),
        ("barst B1, 0,3 mm,\nbarst B2, 1 mm,\nde aannemer is aansprakelijk.", None, ["0,3 mm", "1 mm"], "aansprakelijk")]:
    t11, _ = S.toepassen(tekst, profiel)
    check(f"opsomming per regel: '{tekst[:30]}'", all(x in t11 for x in moeten_blijven) and weg not in t11, t11)
LAAG = ["barst B1, 0,3 mm", "de goot lekt", "de aannemer is aansprakelijk", "volgens de opname is de muur nat",
        "de architect sprak zijn vaststellingen in", "zie opname 00:12:30", "de veranda is verjaard"]
verlies = []
for combi in _it.product(LAAG, repeat=3):
    for profiel in (None, "aankoopkeuring"):
        uit, _ = S.toepassen("\n".join(combi), profiel)
        for regel in combi:
            schoon = S.toepassen(regel, profiel)[0]
            if schoon and schoon not in uit:
                verlies.append(("\n".join(combi), uit))
                break
check("mengtest regels zonder leesteken: elke regel blijft zoals hij alleen zou blijven", not verlies, verlies[:2])

# Twaalfde review 26-10-2026: weggevallen opnameregels laten geen lege regel achter
SP, LG = "De architect sprak zijn vaststellingen ter plaatse in.", "Een tijdstip tussen haakjes verwijst naar de opname."
for tekst, verwacht in [(f"A.\n{SP}\n{LG}\nB.", "A.\nB."), (f"A.\n\n{SP}\n\nB.", "A.\n\nB."), (f"A. {SP}\n- B.", "A.\n- B."),
                        (f"- De dorpel ligt 3 cm te laag.\n- {SP}\n- {LG}\n- De voeg is open.", "- De dorpel ligt 3 cm te laag.\n- De voeg is open."),
                        (f"{SP}\n{LG}\nB.", "B.")]:
    t12, _ = S.toepassen(tekst)
    check(f"regelafstand na weggevallen opnameregels: {tekst[:20]!r}", t12 == verwacht, repr(t12))

# Dertiende review 26-10-2026: geluidsopname is nooit een opmeting; van_markdown houdt de regels van een punt apart
for zin in ["Volgens de geluidsopname van de expert is de barst 2 mm breed.", "Uit de geluidsopname van de landmeter blijkt dat de grens verschuift.",
            "Blijkens de geluidsopname door de verzekeringsexpert is de schade beperkt."]:
    check(f"S4 geluidsopname is nooit een opmeting: '{zin[:40]}'", any(r == "S4" for r, _ in S.controleer(zin)), S.controleer(zin))
check("S4 'opname van de expert' blijft een opmeting", not S.controleer("Volgens de opname van de expert is de barst 2 mm breed."))
pl = dict(w, categorieen=[{"naam": "Stukken", "punten": [{"nummer": "2.1", "titel": "Stukken", "datum": "2026-10-01", "fotos": [],
         "tekst_nl": "Nog te bezorgen aan de architect:\n- het EPB-verslag\n- de keuring, de keurder is niet gekomen"}]}])
terug = sj.van_markdown(sj.naar_markdown(pl))["categorieen"][0]["punten"][0]["tekst_nl"]
check("van_markdown houdt de regels van een punt apart", terug == pl["categorieen"][0]["punten"][0]["tekst_nl"], repr(terug))
check("na het teruglezen grijpt de grendel niet in op een schone lijst", not S.wacht({"t": terug}), S.wacht({"t": terug}))

# Zestiende review 26-10-2026
t16, _ = S.toepassen("De dorpel ligt 3 cm te laag en de architect sprak zijn vaststellingen ter plaatse in.")
check("ingesproken-zin met een vaststelling ervoor: zichtbaar gemarkeerd, niet stil weg", t16 == S.MARKERING.format(regel="S4"), t16)
for zin, regel in [("The contractor is liable for the moisture damage.", "S5"), ("The contractor is in default.", "S5"),
                   ("According to the recording the sill is 3 cm too low.", "S4"), ("The architect has not visited the site before.", "S1"),
                   ("This is against the rules of the Order of Architects.", "S2"), ("The previous architect never checked the works.", "S3")]:
    check(f"Engels {regel}: '{zin[:40]}'", any(r == regel for r, _ in S.controleer(zin)), S.controleer(zin))
t16, _ = S.toepassen("The sill is too low (recording 00:12:00).")
check("Engels: opnametijdstip weg, vaststelling blijft", t16 == "The sill is too low.", t16)
check("Engels: gewone tekst blijft", not S.controleer("The ten-year liability insurance must be in the file. The gutter leaks."))
twee = dict(w, categorieen=[{"naam": "Vocht", "punten": [{"nummer": "3.1", "titel": "Vocht", "datum": "2026-10-01", "fotos": [],
          "tekst_nl": "De aannemer is aansprakelijk voor de vochtschade (opname 00:12:00).",
          "tekst_en": "The contractor is liable for the moisture damage (recording 00:12:00)."}]}])
md2 = sj.naar_markdown(twee)
check("tweetalig werfverslag: ook het Engels gaat door de grendel", "liable" not in md2 and "00:12" not in md2.split("<!--")[0], md2[-300:])
# Negentiende review 26-10-2026: een losse verwijzing "Zie opname 00:12:05." laat geen punt achter
for tekst, verwacht in [("Er blijft water staan. Zie opname 00:22:30. De aannemer herstelt de afvoer.", "Er blijft water staan. De aannemer herstelt de afvoer."),
                        ("Zie opname 00:14:40. De pannen tonen mosgroei.", "De pannen tonen mosgroei."),
                        ("De goot lekt! Transcript 12:30.", "De goot lekt!"), ("Opname 00:12:05.", ""),
                        ("De gevel loopt trapsgewijs.\nZie opname 00:12:05.", "De gevel loopt trapsgewijs."),
                        ("Raam R3 (...) staat uit lood... zie detail.", "Raam R3 (...) staat uit lood... zie detail.")]:
    t19, _ = S.toepassen(tekst, "aankoopkeuring")
    check(f"losse opnameverwijzing zonder losse punt: '{tekst[:30]}'", t19 == verwacht, repr(t19))

# Twintigste review 26-10-2026: een opnamezin valt alleen stil weg als elk woord een meta-woord is
for tekst in ["De dorpel van raam R3 ligt 3 cm te laag, het tijdstip tussen haakjes verwijst naar de opname.",
              "De dorpel ligt 3 cm te laag en dit verwijst naar de opname.",
              "Er blijft water staan op het terras (00:22:30), wat verwijst naar de opname.",
              "Mehdi zag dat de dakgoot aan de achtergevel lekt en sprak zijn vaststellingen ter plaatse in.",
              "De architect stelde vast dat de zinken dorpel 3 cm te laag ligt en sprak zijn vaststellingen in."]:
    t20, ing20 = S.toepassen(tekst + "\nDe voeg is open.")
    check(f"vaststelling aan een opnamezin: zichtbaar gemarkeerd: '{tekst[:35]}'",
          t20 == S.MARKERING.format(regel="S4") + "\nDe voeg is open." and ("S4", tekst) in ing20, repr(t20))
for tekst in ["De architect sprak zijn vaststellingen ter plaatse in.", "De architect nam 18 foto's en sprak zijn vaststellingen ter plaatse in.",
              "Een tijdstip tussen haakjes (uu:mm:ss) verwijst naar de opname van het plaatsbezoek.", "Dit verwijst naar de opname van het bezoek.",
              "The architect dictated his findings at 10:15."]:
    check(f"zuivere opnamezin valt weg: '{tekst[:35]}'", S.toepassen(tekst)[0] == "", S.toepassen(tekst))

# Tweeëntwintigste review 26-10-2026: een opnamezin over een harde regelovergang op andere plekken
for tekst, verwacht in [
        ("Het onderzoek was visueel. Elk tijdstip tussen haakjes verwijst naar\nde opname van het plaatsbezoek.", "Het onderzoek was visueel."),
        ("Een tijdstip tussen haakjes verwijst\nnaar de opname van het bezoek op 3 juni.", S.MARKERING.format(regel="S4")),
        ("De goot lekt. De architect\nsprak zijn vaststellingen ter plaatse in. De dorpel ligt te laag.", "De goot lekt. De dorpel ligt te laag."),
        ("de goot lekt\nde architect sprak zijn vaststellingen in", "de goot lekt")]:
    t22, _ = S.toepassen(tekst)
    check(f"harde regelovergang in een opnamezin: '{tekst[:35]}'", t22 == verwacht and not any(r == "S4" for r, _ in S.controleer(t22)), repr(t22))

# Drieëntwintigste review 26-10-2026: een opnamezin met twee harde regelovergangen
for tekst, verwacht in [("De dakgoot lekt aan de achterzijde.\nDe architect sprak zijn\nvaststellingen ter plaatse\nin. De dorpel ligt 3 cm te laag.",
                         "De dakgoot lekt aan de achterzijde. De dorpel ligt 3 cm te laag."),
                        ("De architect sprak\nzijn vaststellingen\nter plaatse in.", "")]:
    t23, _ = S.toepassen(tekst, "aankoopkeuring")
    check(f"opnamezin over drie regels: '{tekst[-30:]}'", t23.replace("\n", " ") == verwacht and not any(r == "S4" for r, _ in S.controleer(t23)), repr(t23))
woorden = "De architect sprak zijn vaststellingen ter plaatse in.".split()
lek = []
for a in range(1, len(woorden)):
    for b in range(a + 1, len(woorden)):
        tekst = " ".join(woorden[:a]) + "\n" + " ".join(woorden[a:b]) + "\n" + " ".join(woorden[b:])
        if any(r == "S4" for r, _ in S.controleer(S.toepassen(tekst)[0])) or S.toepassen(tekst)[0]:
            lek.append(tekst)
check("elke plaatsing van twee harde regelovergangen in de ingesproken-zin wordt gevangen", not lek, lek[:3])

# Vierentwintigste review 26-10-2026: een opnameverwijzing na een harde regelovergang midden in de zin
for tekst, verwacht in [("Diagonale barst van 0,3 mm boven het raam, zie\nopname 00:12:05.", "Diagonale barst van 0,3 mm boven het raam."),
                        ("Barst in het kader, zie\nopname 00:12:05. De goot lekt.", "Barst in het kader. De goot lekt."),
                        ("Scheur 2 mm breed,\nopname 00:11:49 tot 00:12:10.", "Scheur 2 mm breed.")]:
    t24, _ = S.toepassen(tekst, "aankoopkeuring")
    check(f"opnameverwijzing na een regelovergang: '{tekst[:30]}'", t24.replace("\n", " ").replace("  ", " ") == verwacht, repr(t24))

# Vijfentwintigste review 26-10-2026: een bestandsnaam die met V, B of S begint, is geen herkomstcode
for b in ["V - Vergunningsbesluit.pdf p. 2", "B-plan stabiliteit.pdf blad 3", "S 1015.jpg", "V-plan.dwg", "B&W besluit.pdf", "S/plan.pdf"]:
    check(f"geen code uit een bestandsnaam: '{b}'", sj.herkomst(b) not in ("V", "B", "S"), sj.herkomst(b))
for b in ["V", "B", "S", "V + B", "V/S"]:
    check(f"een volledige code blijft: '{b}'", sj.herkomst(b) == b, sj.herkomst(b))

# Zesentwintigste review 26-10-2026: een verwijzing tussen haakjes als eigen zin na een punt
for tekst, verwacht in [("Er blijft water staan in de goot. (opname 00:22:30). De goot hangt door.", "Er blijft water staan in de goot. De goot hangt door."),
                        ("De schoorsteen vertoont scheuren aan de bovenzijde! (opname 00:31:10).", "De schoorsteen vertoont scheuren aan de bovenzijde!"),
                        ("Lekt de goot? (transcript 00:12).", "Lekt de goot?"), ("(opname 00:22:30). De goot hangt door.", "De goot hangt door."),
                        ("De goot lekt. (zie opname 00:12:05). De dorpel ligt te laag.", "De goot lekt. De dorpel ligt te laag."),
                        ("De goot lekt (opname 00:12:05).", "De goot lekt.")]:
    t26, _ = S.toepassen(tekst, "aankoopkeuring")
    check(f"verwijzing tussen haakjes na een punt: '{tekst[:35]}'", t26 == verwacht, repr(t26))

# Zevenentwintigste review 26-10-2026: een zin tussen haakjes die met 'opname' begint maar geen verwijzing is, blijft
for tekst in ["Diagonale barst boven de keukendeur, 0,5 mm breed. (Opname van de bestaande toestand door expert Claes op 3.3.2025: barst niet vermeld.)",
              "Haarscheur in de gemene muur. (opname plaatsbeschrijving 3.3.2025, foto 14)",
              "De keuring vond plaats op 12.10.2026. (Opname visueel en niet-destructief; de kruipruimte en de zolder waren niet toegankelijk.)",
              "Meterstanden genoteerd. (Opname meterstanden: water 123 m³, elektriciteit 4.567 kWh.)",
              "De luidsprekers hangen. (audio-installatie nog aan te sluiten)"]:
    for profiel in (None, "aankoopkeuring"):
        t27, ing27 = S.toepassen(tekst, profiel)
        check(f"haakjestekst die geen opnameverwijzing is, blijft: '{tekst[-35:]}' {profiel}", t27 == tekst and not ing27, (t27, ing27))

# Achtentwintigste review 26-10-2026: de zichtbare bron houdt opmetingen, bestandsnamen en schalen; alleen opnametijdstippen weg
for b in ["opname van de bestaande toestand door expert Claes, 3.3.2025", "Opname plaatsgesteldheid expert Claes.pdf", "plan A-201 schaal 1:100",
          "grondplan 1:50", "verslag audioinstallateur", "momentopname werf.jpg", "Planopname.pdf", "WhatsApp Image 2026-09-30 at 18.04.11.jpeg"]:
    check(f"bron blijft zoals ze is: '{b}'", S.bron_zichtbaar(b) == b and sj.herkomst(b) == b, (S.bron_zichtbaar(b), sj.herkomst(b)))
for b, verwacht in [("transcript.txt (00:12:00)", "transcript.txt"), ("transcript.txt 12m30s", "transcript.txt"),
                    ("transcript.txt (00:12:00)\n00 fotos.md", "transcript.txt / 00 fotos.md")]:
    check(f"opnametijdstip weg uit de bron: '{b[:30]}'", S.bron_zichtbaar(b) == verwacht and sj.herkomst(b) == verwacht, S.bron_zichtbaar(b))

# Negenentwintigste review 26-10-2026: na een legende blijft een schaal tussen haakjes staan, een opnametijdstip niet
t29, _ = S.toepassen("Nagekeken werden het gevelplan (1:50) en de doorsnede (1:20). Een tijdstip tussen haakjes verwijst naar de opname. "
                     "De dorpel ligt te laag (00:12:30).")
check("schaal blijft na een legende, opnametijdstip niet", "(1:50)" in t29 and "(1:20)" in t29 and "00:12" not in t29, t29)

# Dertigste review 26-10-2026: een schaal in een opname-haakje is geen opnametijdstip
for tekst in ["Haarscheur in de gemene muur boven de trap. (Opname van de bestaande toestand door landmeter Claes, schaal 1:50.)",
              "De bestaande toestand is opgemeten (opname landmeter Claes, plan 1:100); de gemene muur is 28 cm dik."]:
    t30, ing30 = S.toepassen(tekst)
    check(f"schaal in een opname-haakje blijft: '{tekst[:35]}'", t30 == tekst and not ing30, (t30, ing30))
for tekst, verwacht in [("De goot lekt (opname 00:12:30).", "De goot lekt."), ("De goot lekt (opname 0:12:30).", "De goot lekt."),
                        ("De goot lekt, zie opname 12:30.", "De goot lekt."), ("The gutter leaks (recording 00:12:30).", "The gutter leaks.")]:
    check(f"opnametijdstip blijft weg: '{tekst}'", S.toepassen(tekst)[0] == verwacht, S.toepassen(tekst))

# Eenendertigste review 27-10-2026: direct na "opname" of "transcript" is ook een kort tijdstip (3:45, 0:45) een
# opnametijdstip, zoals in productie; de schaal verder in een opname-haakje (dertigste review) blijft
for tekst, verwacht in [("De goot lekt (opname 3:45).", "De goot lekt."), ("De goot lekt, zie opname 7:12.", "De goot lekt."),
                        ("De goot lekt (opname 0:45).", "De goot lekt."), ("De goot lekt (transcript 4:05).", "De goot lekt."),
                        ("De goot lekt. Zie opname 3:45.", "De goot lekt."), ("De goot lekt. (opname 3:45).", "De goot lekt."),
                        ("De goot (opname 3:45-4:10) lekt.", "De goot lekt."), ("The gutter leaks (recording at 3:45).", "The gutter leaks.")]:
    for profiel in (None, "aankoopkeuring"):
        t31, ing31 = S.toepassen(tekst, profiel)
        check(f"kort opnametijdstip weg: '{tekst}' {profiel}", t31 == verwacht and ing31 and S.toepassen(t31, profiel)[0] == t31, (t31, ing31))
for b, verwacht in [("verklaring bouwheer, opname 3:45", "verklaring bouwheer"), ("foto 12 (opname 0:45)", "foto 12")]:
    check(f"kort opnametijdstip weg uit de bron: '{b}'", S.bron_zichtbaar(b) == verwacht, S.bron_zichtbaar(b))
for tekst in ["De goot is nagemeten. (Opname van de bestaande toestand, schaal 1:50.)", "Afspraak om 10:15 op de werf (10:15)."]:
    check(f"geen opnametijdstip, blijft: '{tekst[:35]}'", S.toepassen(tekst) == (tekst, []), S.toepassen(tekst))

# Tweeëndertigste review 27-10-2026: (1) "direct na het woord" laat ook een leesteken, een eenheid of een samengesteld
# woord toe, zoals productie; (2) een verwijzing op een eigen regel of alinea laat geen ".." of extra lege regel achter
for tekst, verwacht in [("De dakgoot lekt aan de achterzijde (opname: 3:45). De kilgoot is vervangen.",
                         "De dakgoot lekt aan de achterzijde. De kilgoot is vervangen."),
                        ("De barst loopt diagonaal (transcript: 4:05).", "De barst loopt diagonaal."),
                        ("De dakgoot lekt (opname, 7:12).", "De dakgoot lekt."), ("De dorpel (opname - 3:45) is niet vlak.", "De dorpel is niet vlak."),
                        ("De dorpel (opname 3:45min) is niet vlak.", "De dorpel is niet vlak."),
                        ("De dorpel (opname 12:30u) is niet vlak.", "De dorpel is niet vlak."),
                        ("De dorpel is niet vlak (audio-opname 3:45). Rest.", "De dorpel is niet vlak. Rest."),
                        ("De goot lekt. Zie opname: 3:45. Rest.", "De goot lekt. Rest."),
                        ("De dakgoot lekt aan de achterzijde.\n\nZie opname 00:12:05.", "De dakgoot lekt aan de achterzijde."),
                        ("De dakgoot lekt aan de achterzijde.\n\n(opname 00:12:05).", "De dakgoot lekt aan de achterzijde."),
                        ("De dakgoot lekt aan de achterzijde.\n\nZie transcript 12:30.", "De dakgoot lekt aan de achterzijde."),
                        ("De dakgoot lekt aan de achterzijde. \nZie opname 00:12:05.", "De dakgoot lekt aan de achterzijde."),
                        ("De dakgoot lekt.\n(opname 00:12:30)\nDe kilgoot is vervangen.", "De dakgoot lekt.\nDe kilgoot is vervangen."),
                        ("De dakgoot lekt.\n\nZie opname 00:12:05.\n\nDe kilgoot is vervangen.", "De dakgoot lekt.\n\nDe kilgoot is vervangen."),
                        ("De dakgoot lekt.\n\nZie opname 00:12:05. Daarna de kilgoot.", "De dakgoot lekt.\n\nDaarna de kilgoot."),
                        ("- De dakgoot lekt.\n- Zie opname 00:12:05.\n- De kilgoot is vervangen.", "- De dakgoot lekt.\n- De kilgoot is vervangen."),
                        ("**3.1 Goot**\nZie opname 00:12.\nDe dakgoot lekt.", "**3.1 Goot**\nDe dakgoot lekt."),
                        ("Het raam is gebarsten, zie\nopname 00:12:30.\nDe deur klemt.", "Het raam is gebarsten.\nDe deur klemt.")]:
    for profiel in (None, "aankoopkeuring"):
        t32, ing32 = S.toepassen(tekst, profiel)
        check(f"opnameverwijzing netjes weg: {tekst[-40:]!r} {profiel}", t32 == verwacht and ing32 and S.toepassen(t32, profiel)[0] == t32, (t32, ing32))
check("kort opnametijdstip na een dubbelpunt weg uit de bron", S.bron_zichtbaar("foto 12 (opname: 0:45)") == "foto 12", S.bron_zichtbaar("foto 12 (opname: 0:45)"))
for tekst in ["De bestaande toestand is opgemeten (opname landmeter Claes, plan 1:100); de gemene muur is 28 cm dik.",
              "De dakgoot lekt.\n\nDe kilgoot is vervangen.", "- De dakgoot lekt.\n- De kilgoot is vervangen."]:
    check(f"zonder opnameverwijzing blijft alles: {tekst[:35]!r}", S.toepassen(tekst) == (tekst, []), S.toepassen(tekst))

# Drieëndertigste review 27-10-2026: buiten haakjes mag alleen "van" (of "at") tussen opname en tijdstip, zoals productie;
# "de opname op 1:50" of "de opname om 9:30" is gewone tekst over een opmeting of plaatsbeschrijving
for tekst in ["De opname op 1:50 toont een gemene muur van 28 cm.", "De landmeter bezorgt de opname op 1:50 van de bestaande toestand.",
              "Tijdens de opname om 9:30 werd een nieuwe barst vastgesteld in de keuken.",
              "Bij de tegensprekelijke opname om 14:00 waren de buren aanwezig.", "Plannen:\n- De opname op 1:50.\n- Het grondplan op 1:100."]:
    for profiel in (None, "aankoopkeuring"):
        check(f"opname om/op blijft: {tekst[:40]!r} {profiel}", S.toepassen(tekst, profiel) == (tekst, []), S.toepassen(tekst, profiel))
    check(f"opname om/op geeft geen S4: {tekst[:40]!r}", S.controleer(tekst) == [], S.controleer(tekst))
check("opname op 1:50 in een bestandsnaam blijft", S.bron_zichtbaar("Opname op 1:50 gevel Claes.pdf") == "Opname op 1:50 gevel Claes.pdf",
      S.bron_zichtbaar("Opname op 1:50 gevel Claes.pdf"))
for tekst, verwacht in [("De goot lekt, zie opname van 7:12.", "De goot lekt."), ("The gutter leaks, see recording at 3:45.", "The gutter leaks.")]:
    check(f"van/at blijft een verwijzing: {tekst!r}", S.toepassen(tekst)[0] == verwacht, S.toepassen(tekst))

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
