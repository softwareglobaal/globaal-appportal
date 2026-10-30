"""Grendels van de afdeling Bouw: De Aannemerszoeker en De Offertevergelijker.

Driehoeksoverleg 30-10-2026 (ontwerp, docs/bouw/rapport-1-ontwerp.md). Alleen verzonnen firma's en voorbeeld.com-links;
geen echte bouwheren, adressen of offertes.

Draaien: python3 mijnagents-runner/tests/test_bouw.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "koppelingen"))
from datetime import date  # noqa: E402

from bouw import eigen as E  # noqa: E402
from bouw import mail as M  # noqa: E402
from bouw import mappen as MP  # noqa: E402
from bouw import offertes as F  # noqa: E402
from bouw import scheiding as S  # noqa: E402
from bouw import verslag as V  # noqa: E402
from bouw import vraag as Q  # noqa: E402
from bouw import zoeken as Z  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


print("De harde regel: H-Architects en Harmonie Bouw zijn gescheiden")
check("mail van HB met de naam H-Architects wordt geweigerd",
      not S.mag_weg("Beste, de plannen van H-Architects vindt u in bijlage.", S.HB))
check("mail van HB met een Unicode-streepje in de naam wordt geweigerd",
      not S.mag_weg("Plannen van H‑Architects in bijlage.", S.HB))
check("mail van HB met het domein h-architects.be wordt geweigerd",
      not S.mag_weg("Vragen? Mail naar standaard@h-architects.be", S.HB))
check("mail van HB met het kantoornummer van H-A wordt geweigerd",
      not S.mag_weg("Bel ons op +32 16 79 32 96.", S.HB))
check("mail van HA die Harmonie Bouw noemt wordt geweigerd",
      not S.mag_weg("Wij werken graag met Harmonie Bouw.", S.HA))
check("mail van HA met harmoniebouw aan elkaar wordt geweigerd",
      not S.mag_weg("Een prijs van HarmonieBouw hebben we al.", S.HA))
check("mail van HA met het ondernemingsnummer van HB wordt geweigerd",
      not S.mag_weg("Factuur aan BE 0537.405.239.", S.HA))
check("mail met een bandwoord wordt geweigerd", not S.mag_weg("Wij behoren tot dezelfde groep.", S.HA))
check("mail met 'zusterbedrijf' wordt geweigerd", not S.mag_weg("Ons zusterbedrijf voert uit.", S.HB))
check("mail met 'onafhankelijk' wordt geweigerd", not S.mag_weg("Wij zijn onafhankelijk van de aannemer.", S.HA))
check("mail met 'partner' wordt geweigerd", not S.mag_weg("Onze vaste partner voor dakwerken.", S.HB))
check("mail met de naam van de persoon achter de firma's wordt geweigerd",
      not S.mag_weg("Met vriendelijke groeten, M. Chegini", S.HB))
check("gewone mail van HA met eigen handtekening mag",
      S.mag_weg("Beste,\n\nGraag uw offerte voor de dakwerken.\n\nIn opdracht van H-Architects BV,\n"
                "E-mail: standaard@h-architects.be\nTelefoon: +32 16 79 32 96", S.HA), S.schendingen("x", S.HA))
check("gewone mail van HB mag", S.mag_weg("Beste,\n\nWij zoeken een onderaannemer voor plafonneerwerken.\n\n"
                                          "Harmonie Bouw BV\nkantoor@harmoniebouw.be", S.HB))
check("bouwtaal is geen band: ventilatiegroep en een leiding verbonden met het riool",
      S.mag_weg("Ventilatiegroep D, de afvoer wordt verbonden met het riool.", S.HB))
check("HB mag het woord architect in de werkomschrijving gebruiken",
      S.mag_weg("Uitvoering volgens de plannen van de architect.", S.HB))
check("in een vergelijking van H-A mag de naam Harmonie Bouw niet staan (X4: Inschrijver B)", not S.mag_weg(
      "Offerte Harmonie Bouw: 169.303,08 euro excl. btw. Offerte Profi: 148.024,00 euro.", S.HA))
check("de andere firma wordt herkend als inschrijver", S.is_andere_firma("01 Harmoniebouw - ruwbouw", S.HA)
      and not S.is_andere_firma("06 MSS bv - ventilatie", S.HA))
try:
    S.schendingen("tekst", "XX")
    check("onbekende firma wordt geweigerd", False)
except ValueError:
    check("onbekende firma wordt geweigerd", True)


print("\nDe prijsaanvraag: vast sjabloon per firma (X3)")
ha = M.maak(S.HA, "dakwerken", "Vernieuwen van een plat dak van ongeveer 40 m2 met EPDM.", "Leuven", "15-11-2026",
            "2999 - Voorbeeldstraat 1, 3000 Leuven", aanhef="Beste Dak BV,")
check("H-A tekent in opdracht van H-Architects BV, vanuit standaard@", "In opdracht van H-Architects BV" in ha["tekst"]
      and ha["van"] == "standaard@h-architects.be" and ha["onderwerp"].startswith("2999 - Voorbeeldstraat 1"))
check("H-A vraagt de offerte op naam van de bouwheer, met plaatsbezoek", "op naam van de bouwheer" in ha["tekst"]
      and "plaatsbezoek" in ha["tekst"])
hb = M.maak(S.HB, "plafonneerwerk", "Plafonneren van muren en plafonds.", "3020 Herent", None)
check("HB vraagt btw verlegd, verzekering, vanuit kantoor@", "btw verlegd" in hb["tekst"] and "verzekering" in hb["tekst"]
      and hb["van"] == "kantoor@harmoniebouw.be")
check("de mail van HB noemt H-Architects nergens", S.mag_weg(hb["onderwerp"] + hb["tekst"] + hb["van"], S.HB))
check("de mail van HA noemt Harmonie Bouw nergens", S.mag_weg(ha["onderwerp"] + ha["tekst"] + ha["van"], S.HA))
check("HB zet geen project of werfadres in het onderwerp", "2999" not in M.maak(S.HB, "x", "", "Herent", None, "2999 - X")["onderwerp"])
for naam, args in (("werkomschrijving van het model met de naam van H-A", (S.HB, "dak", "Zoals H-Architects tekende.", "Herent")),
                   ("aanhef aan de andere firma", (S.HA, "dak", "", "Leuven")),
                   ("bandwoord in de werkomschrijving", (S.HB, "dak", "Voor onze vaste partner.", "Herent"))):
    try:
        M.maak(*args, aanhef="Beste Harmonie Bouw," if "aanhef" in naam else "Beste,")
        check(f"geweigerd: {naam}", False)
    except M.MailGeweigerd:
        check(f"geweigerd: {naam}", True)

print("\nDe vraag (X1, X2)")
v = Q.ontleed("firma: HB; werk: plafonneerwerk; omvang: 120 m2; gemeente: 3020 Herent; straal: 30; tegen: 15-11-2026")
check("velden ontleed", v["firma"] == S.HB and v["werk"] == "plafonneerwerk" and v["straal"] == 30 and v["gemeente"] == "3020 Herent")
check("zonder firma begint niemand", Q.ontbreekt_zoeker(Q.ontleed("werk: dak; gemeente: Leuven"))[0] == ["firma"])
check("beide firma's genoemd is geen firma", Q.firma_uit("H-Architects of Harmonie Bouw") is None)
check("H-A met project mag zonder gemeente", Q.ontbreekt_zoeker(Q.ontleed("firma: HA; werk: dak; project: 2999"))[0] == [])
check("HB met project heeft wel een gemeente nodig", "gemeente" in Q.ontbreekt_zoeker(Q.ontleed("firma: HB; werk: dak; project: U77"))[0])
check("zonder omvang en timing: aan te vullen", Q.ontbreekt_zoeker(Q.ontleed("firma: HB; werk: x; gemeente: y"))[1] == ["omvang", "tegen"])
check("vergelijker zonder project of map begint niet", Q.ontbreekt_vergelijker(Q.ontleed("firma: HA")) == ["project of map"])

print("\nKandidaten keuren (X2, G2)")
check("geldig ondernemingsnummer", Z.btw_geldig("BE 0537.405.239") == "0537.405.239")
check("ongeldig ondernemingsnummer vervalt", Z.btw_geldig("0123.456.789") is None and Z.btw_geldig("12") is None)
VUL = " Dakwerken, platte daken, EPDM, renovatie, zinkwerk, onderhoud en herstellingen in de regio." * 3
GELEZEN = {"https://dak-een.voorbeeld.com": "Dak Een BV" + VUL,
           "https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html?ondernemingsnummer=0537405239":
               "Ondernemingsnummer 0537.405.239 Status: Actief" + VUL,
           "https://dak-twee.voorbeeld.com": "Dak Twee" + VUL, "https://dak-ver.voorbeeld.com": "Dak Ver" + VUL,
           "https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html?ondernemingsnummer=0403170701":
               "Ondernemingsnummer 0403.170.701 Status: Stopgezet" + VUL,
           "https://dak-weg.voorbeeld.com": "Dak Weg" + VUL}
PUNTEN = {"3000 Leuven": {"lat": 50.879, "lon": 4.700}, "3020 Herent": {"lat": 50.905, "lon": 4.672},
          "8000 Brugge": {"lat": 51.209, "lon": 3.224}}
firmas = [
    {"naam": "Dak Een", "url": "https://dak-een.voorbeeld.com", "postcode": "3020", "gemeente": "Herent", "ondernemingsnummer": "0537.405.239"},
    {"naam": "Dak Twee", "url": "https://dak-twee.voorbeeld.com/", "postcode": "3000", "gemeente": "Leuven", "ondernemingsnummer": None},
    {"naam": "Dak Ver", "url": "https://dak-ver.voorbeeld.com", "postcode": "8000", "gemeente": "Brugge"},
    {"naam": "Dak Spook", "url": "https://dak-spook.voorbeeld.com", "postcode": "3000", "gemeente": "Leuven"},
    {"naam": "Dak Weg", "url": "https://dak-weg.voorbeeld.com", "postcode": "3000", "gemeente": "Leuven", "ondernemingsnummer": "0403.170.701"},
    {"naam": "Dak Een dubbel", "url": "https://www.dak-een.voorbeeld.com/contact", "postcode": "3020", "gemeente": "Herent", "ondernemingsnummer": "0537405239"},
]
res = Z.keur(firmas, GELEZEN, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("bovenaan alleen met gelezen site, actieve KBO en binnen de straal", [f["naam"] for f in res["goed"]] == ["Dak Een"])
check("zonder KBO-bewijs: na te kijken, nooit groen", [f["naam"] for f in res["na_te_kijken"]] == ["Dak Twee"])
check("buiten de straal apart, met afstand", [f["naam"] for f in res["buiten"]] == ["Dak Ver"] and res["buiten"][0]["afstand_km"] > 25)
weg = {x["aanbod"]["naam"]: x["redenen"] for x in res["afgewezen"]}
check("een site die niet gelezen is, valt weg", "Dak Spook" in weg)
check("stopgezet in de KBO valt weg", weg.get("Dak Weg") == ["stopgezet volgens de KBO"])
check("dubbel op ondernemingsnummer telt een keer", sum(f["naam"].startswith("Dak Een") for f in res["goed"] + res["na_te_kijken"]) == 1)
res2 = Z.keur(firmas[:1], GELEZEN, PUNTEN["3000 Leuven"], 25, lambda p: (_ for _ in ()).throw(OSError("geopunt weg")))
check("Geopunt onbereikbaar: afstand onbekend, dus na te kijken", res2["na_te_kijken"] and not res2["goed"])
sys_, gebr = Z.opdracht("werkwijze", "dakwerken", "3000 Leuven", 25, "onderaanneming", "2026-10-30", "40 m2")
check("naar het model alleen werk, omvang, gemeente en straal", "Harmonie" not in gebr and "Architects" not in gebr
      and "40 m2" in gebr and "onderaanneming" in gebr)

print("\nEigen bronnen van die ene firma (X2)")
def zoek_nep(q, pad):
    return [{"soort": "folder", "naam": "06 Dak Een - dakwerken", "pad": "/Work All/01. H-A WORK/x/2999 Straat 1, 3000 Leuven/Offerte/06 Dak Een - dakwerken"},
            {"soort": "file", "naam": "dakwerken.pdf", "pad": "/Work All/04. Harmoniebouw/05. ONDERAANNEMER/dakwerken/dakwerken.pdf"},
            {"soort": "folder", "naam": "dakwerken", "pad": "/Work All/01. H-A WORK/0 Archive/2019/dakwerken"}]
eigen = E.in_mappen(S.HA, "dakwerken plat dak", zoek=zoek_nep)
check("H-A ziet alleen haar eigen mappen, zonder archief", [e["naam"] for e in eigen] == ["06 Dak Een - dakwerken"] and eigen[0]["project"] == "2999")
check("HB ziet alleen haar eigen mappen", all(e["pad"].startswith("/Work All/04. Harmoniebouw") for e in E.in_mappen(S.HB, "dakwerken", zoek=zoek_nep)))
sqls = []
def psql_nep(sql):
    sqls.append(sql)
    return {"totaal": 3, "treffers": [{"btw": "BE0537405239", "naam": "Dak Een"}]}
eerder, bekend = E.eerder_leverancier(S.HB, ["0537.405.239", "x'; drop"], psql=psql_nep)
check("boekhouding: alleen de codes van die firma, geen vreemde invoer", "'HB','HARM'" in sqls[0] and "'HA'" not in sqls[0]
      and "drop" not in sqls[0])
check("eerder leverancier herkend", eerder == {"0537405239": "Dak Een"} and bekend)
check("niets in kern voor de firma: niet nagekeken, nooit nee", E.eerder_leverancier(S.HA, [], psql=lambda s: {"totaal": 0})[1] is False)

print("\nOffertes lezen (X4)")
VUL2 = " Levering en plaatsing volgens bestek, inclusief afvoer van afval en opkuis van de werf." * 2
def pdf(*regels):
    return ["\n".join(regels) + VUL2]
a = F.lees(pdf("Offerte 12-09-2026", "Ventilatie systeem D", "Totaal excl. btw 10.000,00 EUR", "BTW 6% 600,00",
               "Totaal incl. btw 10.600,00 EUR", "Deze offerte is geldig tot 31-12-2026"))
check("totalen, btw en geldigheid gelezen", a["excl"] == 10000.0 and a["incl"] == 10600.0 and a["btw_tarief"] == 6
      and a["geldig_tot"] == date(2026, 12, 31) and not a["redenen"], a)
b = F.lees(pdf("Prijs 01-10-2026", "Totaal te betalen 11.130,00", "btw 6 %", "Geldigheid 30 dagen"))
check("alleen inclusief: exclusief berekend en gemeld", b["excl"] == 10500.0 and any("berekend" in r for r in b["redenen"]))
check("geldigheid in dagen wordt een datum", b["geldig_tot"] == date(2026, 10, 31))
c = F.lees(pdf("Totaal excl. btw 9.000,00", "BTW 21%", "Totaal incl. btw 10.000,00"))
check("rekenfout gemeld", any("rekenfout" in r for r in c["redenen"]))
d = F.lees(pdf("Kostenraming dakwerken", "Totaal excl. btw 8.000,00", "btw 6%"))
check("een raming is geen offerte", d["raming"] and any("raming" in r for r in d["redenen"]))
check("een pagina zonder tekst is een scan: OCR nodig", F.lees(["Offerte" + VUL2, "   "])["soort"] == "scan")
check("een kapotte PDF is onleesbaar", F.lees(None)["soort"] == "onleesbaar")
e = F.lees(pdf("Totaal excl. btw 5.000,00", "BTW verlegd, medecontractant"))
check("btw verlegd herkend, geen rekenfout", e["verlegd"] and not any("rekenfout" in r for r in e["redenen"]))
z = F.lees(pdf("Prijs per m2 25,00", "Geen totaal vermeld"))
check("geen totaal: blijft onbekend, nooit nul", z["excl"] is None and any("geen totaal" in r for r in z["redenen"]))

print("\nVergelijken (X4, X6): goed voorbeeld naar het model van 2145 ventilatie, met verzonnen bedragen")
uit = F.vergelijk([{"letter": "A", "lees": a}, {"letter": "B", "lees": b}, {"letter": "C", "lees": z},
                   {"letter": "D", "lees": d}], date(2026, 10, 30))
check("laagste en hoogste uit de offertes met een totaal", uit["laagste"]["letter"] == "A" and uit["hoogste"]["letter"] == "B")
check("verschil in euro en procent", uit["verschil"] == 500.0 and uit["verschil_pct"] == 5.0)
check("zonder totaal en raming doen niet mee, maar staan erbij", any("Inschrijver C" in x for x in uit["letop"])
      and any("Inschrijver D" in x and "raming" in x for x in uit["letop"]))
oud = F.lees(pdf("Totaal excl. btw 7.000,00", "btw 21%", "geldig tot 01-09-2026"))
check("verlopen offerte gemeld", any("verlopen" in x for x in F.vergelijk([{"letter": "A", "lees": oud}], date(2026, 10, 30))["letop"]))
check("verschillend btw-tarief gemeld", any("btw-tarief verschilt" in x for x in
      F.vergelijk([{"letter": "A", "lees": a}, {"letter": "B", "lees": oud}], date(2026, 10, 30))["letop"]))
rij = F.per_post([{"onderwerp": "Ventilatiegroep", "posten": {"A": ["1"], "B": []}},
                  {"onderwerp": "Kanalen", "posten": {"A": ["2", "9"], "B": ["3"]}}], {"A": {"1": 4000.0, "2": 6000.0}, "B": {"3": 5000.0}})
check("een post die ontbreekt is ontbreekt, nooit nul", rij[0]["cellen"]["B"] is None and rij[1]["cellen"]["A"] is None
      and rij[1]["cellen"]["B"] == 5000.0)
posten, red = F.keur_posten({"offertes": {"A": {"posten": [{"nr": "1", "totaal": "4.000,00"}, {"nr": "2", "totaal": "6.000,00"},
                                                           {"nr": "3", "totaal": "999,00"}]}}},
                            {"A": "Post 1 4.000,00 Post 2 6.000,00"}, {"A": 10000.0})
check("een bedrag dat niet in de offerte staat, valt weg", posten["A"] == {"1": 4000.0, "2": 6000.0} and red["A"])
posten, red = F.keur_posten({"offertes": {"A": {"posten": [{"nr": "1", "totaal": "4.000,00"}]}}}, {"A": "4.000,00"}, {"A": 10000.0})
check("posten die niet optellen tot het totaal: geen vergelijking per post", posten["A"] == {} and red["A"])
try:
    F.posten_uit_model({"A": "x"})
    check("zonder ja van Mehdi gaat geen offerte naar de AI (X5)", F.OFFERTE_NAAR_AI)
except PermissionError:
    check("zonder ja van Mehdi gaat geen offerte naar de AI (X5)", True)
r = F.redigeer("Aan: Jan Voorbeeld\nMevr. An Voorbeeld\nmail an@voorbeeld.com, tel 0470 12 34 56\nWerf Voorbeeldstraat 1\n"
               "De werken aan de gevel.", ["Voorbeeldstraat 1"])
check("redactie: bouwheer, contact en werfadres weg, gewone tekst blijft", "Jan" not in r and "An Voorbeeld" not in r
      and "@" not in r and "0470" not in r and "Voorbeeldstraat" not in r and "De werken aan de gevel." in r, r)

print("\nDe andere firma als anonieme inschrijver (X4, X6)")
best = [{"naam": "2999_Dak Een_2026-09-01.pdf", "gewijzigd": "2026-09-01T10:00:00Z"},
        {"naam": "2999_Harmoniebouw_2026-09-02.pdf", "gewijzigd": "2026-09-02T10:00:00Z"}]
lt = F.letters(best, S.HA)
check("letters in de volgorde van de bestanden", [l for l, _, _ in lt] == ["A", "B"])
check("de sleutel noemt de andere firma niet", "Harmonie" not in lt[1][2] and lt[1][2].startswith("bestand 2"))
vv = {"firma": S.HA, "project": "2999"}
tekst = V.vergelijkingsverslag(vv, "06 ventilatie", lt, F.vergelijk([{"letter": "A", "lees": a}, {"letter": "B", "lees": b}],
                               date(2026, 10, 30)), None, {}, "2026-10-30", False)
check("het verslag haalt de scheiding", S.kruis(tekst, S.HA) == [] and "Geen gunning" in tekst and "Inschrijver A" in tekst)
check("zonder ja: de vergelijking per post wacht, dat staat erbij", "naar de AI mag" in tekst)

print("\nMappen van die ene firma (X4)")
BOOM = {"/Work All/01. H-A WORK/F/2999 Straat 1, 3000 Leuven": [{".tag": "folder", "name": "4. Implementation & Site Control", "path_display": "/P/4. Implementation & Site Control"}],
        "/P/4. Implementation & Site Control": [{".tag": "folder", "name": "3. Quotes & Invoices", "path_display": "/P/Q"}],
        "/P/Q": [{".tag": "folder", "name": "Offerte", "path_display": "/P/Q/Offerte"}],
        "/P/Q/Offerte": [{".tag": "folder", "name": "06 Dak Een - ventilatie", "path_display": "/P/Q/Offerte/06 Dak Een - ventilatie"},
                         {".tag": "folder", "name": "01 Harmoniebouw - ruwbouw", "path_display": "/P/Q/Offerte/01 Harmoniebouw - ruwbouw"},
                         {".tag": "folder", "name": "00 Niet weerhouden", "path_display": "/P/Q/Offerte/00 Niet weerhouden"}]}
lijst_nep = lambda pad, recursief=False: BOOM.get(pad, [])
pm = lambda firma, project: "/Work All/01. H-A WORK/F/2999 Straat 1, 3000 Leuven"
pad, lots = MP.offertemap({"firma": S.HA, "project": "2999", "lot": "06"}, lijst_nep, pm)
check("lot gevonden op het nummer", pad == "/P/Q/Offerte/06 Dak Een - ventilatie" and len(lots) == 2)
check("lot gevonden op een woord", MP.offertemap({"firma": S.HA, "project": "2999", "lot": "ventilatie"}, lijst_nep, pm)[0] == pad)
check("zonder lot: de keuze, nog niets gelezen", MP.offertemap({"firma": S.HA, "project": "2999"}, lijst_nep, pm)[0] is None)
try:
    MP.offertemap({"firma": S.HB, "map": "/Work All/01. H-A WORK/F/2999/Offerte"}, lijst_nep, pm)
    check("een map van de andere firma wordt geweigerd", False)
except MP.MapFout:
    check("een map van de andere firma wordt geweigerd", True)
bestanden = MP.offertebestanden("/L", lambda p, recursief=False: [
    {".tag": "file", "name": "b.pdf", "path_display": "/L/b.pdf"}, {".tag": "file", "name": "2999_Vergelijking x.pdf"},
    {".tag": "file", "name": "overzicht.xlsx"}, {".tag": "folder", "name": "Oude versies"}, {".tag": "file", "name": "A.pdf", "path_display": "/L/A.pdf"}])
check("alleen offerte-PDF's, geen eerdere vergelijking", [x["naam"] for x in bestanden] == ["A.pdf", "b.pdf"])

print("\nHet verslag van De Aannemerszoeker")
v = Q.ontleed("firma: HB; werk: dakwerken; gemeente: 3000 Leuven; straal: 25")
mails = {f["url"]: M.maak(S.HB, "dakwerken", "Plat dak vernieuwen.", "3000 Leuven", None, aanhef=f"Beste {f['naam']},")
         for f in res["goed"] + res["na_te_kijken"]}
eigen_hb = E.in_mappen(S.HB, "dakwerken", zoek=zoek_nep)
check("de grendel vangt een pad van H-A in een verslag van HB", S.kruis(V.zoekverslag(
      v, {}, res, eigen, mails, {}, True, [], "2026-10-30"), S.HB) != [])
vs = V.zoekverslag(v, {"aannames": ["plat dak"]}, res, eigen_hb, mails, {"0537405239": "Dak Een"}, True, ["omvang", "tegen"], "2026-10-30")
check("eerste regel: hoeveel klaar en niets verstuurd", vs.splitlines()[0].endswith("Niets verstuurd.") and "1 firma's klaar" in vs.splitlines()[0])
check("HB: inhoudingsplicht niet gecontroleerd, met de handeling", "inhoudingsplicht niet gecontroleerd" in vs and "checkinhoudingsplicht" in vs)
check("eerder leverancier vermeld", "al leverancier in onze boekhouding" in vs)
check("de mails staan als concept, met afzender van HB", "Van: kantoor@harmoniebouw.be" in vs and "concept, niet verstuurd" in vs)
check("het verslag van HB noemt H-A niet", S.kruis(vs, S.HB) == [])

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
