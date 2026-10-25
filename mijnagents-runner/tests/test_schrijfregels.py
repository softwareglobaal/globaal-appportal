"""Grendel op de schrijfregels van het kantoor (schrijfregels.py).

Gebeurd op 22/23-10-2026 met het concept 2309 Verslag van bevindingen: het zei dat uit de stukken geen eerder bezoek
van het bureau bleek, noemde de beperking van de eigen opdracht, en verwees bij elke vaststelling naar de opname
"(opname 00:22:30)". Mehdi, 23-10-2026: dat mag nooit, ook niet "tegen de deontologie" of "de vorige architect is niet
geweest". Deze toets faalt zodra zo'n zin weer door het sjabloon komt, of zodra een gewone technische zin ten onrechte
geschrapt wordt.
"""
import sys
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

print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
