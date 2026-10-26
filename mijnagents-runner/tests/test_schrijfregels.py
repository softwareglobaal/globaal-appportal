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
check("V11 werfverslag: Herkomst V zonder opnametijdstip in de zichtbare tekst", "Herkomst: V" in zichtbaar and "00:22" not in zichtbaar and "transcript" not in zichtbaar, mdh[-900:])
check("V11 werfverslag: de bron blijft bewaard achter de V en komt terug bij van_markdown",
      sj.van_markdown(mdh)["categorieen"][0]["punten"][0]["bron"] == "transcript.txt 00:22:30-00:23:16", mdh[-400:])
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
                      ("De dorpel is 3 cm te laag; het tijdstip tussen haakjes verwijst naar de opname.", "De dorpel is 3 cm te laag."),
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
for b, code in [("EPB startverklaring.pdf", "S"), ("Prestatieverklaring PIR-isolatie.pdf", "S"), ("verklaring bouwheer", "B"),
                ("mondeling", "B"), ("transcript.txt 00:22:30", "V"), ("Lastenboek.pdf", "S")]:
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
        ("De goot lekt. Een tijdstip tussen haakjes verwijst naar de opname; de dorpel ligt te laag.", "De goot lekt. De dorpel ligt te laag."),
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

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
