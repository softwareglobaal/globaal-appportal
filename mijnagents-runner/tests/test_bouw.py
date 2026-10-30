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
from bouw import vakwoorden as W  # noqa: E402
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
GELEZEN = {"https://dak-een.voorbeeld.com": "Dak Een BV, Dorpstraat 1, 3020 Herent, BTW BE 0537.405.239" + VUL,
           "https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html?ondernemingsnummer=0537405239":
               "Ondernemingsnummer 0537.405.239\nStatus: Actief\nAdres van de zetel:\nDorpstraat 1\n3020 Herent\nSinds 2010" + VUL,
           "https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html?ondernemingsnummer=0412345614":
               "Ondernemingsnummer 0412.345.614\nStatus: Actief\nAdres van de zetel:\nZeedijk 3\n8000 Brugge\nSinds 2001" + VUL,
           "https://dak-twee.voorbeeld.com": "Dak Twee, Kerkstraat 2, 3000 Leuven" + VUL,
           "https://dak-ver.voorbeeld.com": "Dak Ver, Zeedijk 3, 8000 Brugge, ondernemingsnummer 0412345614" + VUL,
           "https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html?ondernemingsnummer=0403170701":
               "Ondernemingsnummer 0403.170.701 Status: Stopgezet" + VUL,
           "https://dak-weg.voorbeeld.com": "Dak Weg, Molenstraat 4, 3000 Leuven" + VUL}
PUNTEN = {"3000 Leuven": {"lat": 50.879, "lon": 4.700}, "3020 Herent": {"lat": 50.905, "lon": 4.672},
          "8000 Brugge": {"lat": 51.209, "lon": 3.224}}
firmas = [
    {"naam": "Dak Een", "url": "https://dak-een.voorbeeld.com", "adres": "Dorpstraat 1", "postcode": "3020", "gemeente": "Herent",
     "ondernemingsnummer": "0537.405.239", "bewijs": "Dakwerken, platte daken, EPDM, renovatie"},
    {"naam": "Dak Twee", "url": "https://dak-twee.voorbeeld.com/", "adres": "Kerkstraat 2", "postcode": "3000", "gemeente": "Leuven",
     "ondernemingsnummer": None},
    {"naam": "Dak Ver", "url": "https://dak-ver.voorbeeld.com", "adres": "Zeedijk 3", "postcode": "3000", "gemeente": "Leuven",
     "ondernemingsnummer": "0412.345.614", "bewijs": "Dakwerken, platte daken, EPDM, renovatie"},
    {"naam": "Dak Spook", "url": "https://dak-spook.voorbeeld.com", "postcode": "3000", "gemeente": "Leuven"},
    {"naam": "Dak Weg", "url": "https://dak-weg.voorbeeld.com", "adres": "Molenstraat 4", "postcode": "3000", "gemeente": "Leuven",
     "ondernemingsnummer": "0403.170.701"},
    {"naam": "Dak Een dubbel", "url": "https://www.dak-een.voorbeeld.com/contact", "adres": "Dorpstraat 1", "postcode": "3020",
     "gemeente": "Herent", "ondernemingsnummer": "0537405239"},
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
b = F.lees(pdf("Datum: 01-10-2026", "Totaal te betalen 11.130,00", "btw 6 %", "Geldigheid 30 dagen"))
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


print("\nRegressie na controle 2 van Codex (X1 tot X15)")
for f in (S.HA, S.HB, None):
    o = V.onvolledig("aannemerszoeker", f, ["werk"])
    check(f"X1 onvolledig verslag zonder de andere firma ({f})", f is None or S.kruis(o, f) == [])
check("X1 zonder firma: een neutraal voorbeeld", "<firmacode>" in V.onvolledig("aannemerszoeker", None, ["firma"]))
check("X2 de code HA in een stuk van HB wordt geweigerd", not S.mag_weg("Referentie HA 2999", S.HB))
check("X2 de code HB in een stuk van HA wordt geweigerd", not S.mag_weg("zie dossier HB", S.HA))
check("X2 hectare in kleine letters is geen firmacode", S.mag_weg("Een terrein van 2 ha met afsluiting.", S.HB))
check("X2 de verslagtoets kent ook bandwoorden", S.kruis("Dak Een behoort tot dezelfde groep.", S.HB) != [])
check("X3 'ventilatie groep D' en 'onafhankelijke ophanging' zijn gewone bouwtaal",
      S.mag_weg("Ventilatie groep D met onafhankelijke ophanging van de kanalen.", S.HB))
check("X3 'tot de groep' en 'onafhankelijke firma' blijven verboden",
      not S.mag_weg("Wij horen tot de groep.", S.HA) and not S.mag_weg("Een onafhankelijke firma.", S.HB))
check("X3 een firmanaam met Partners is geen band", S.mag_weg("Beste Renovatie Partners,", S.HB))
ww = open(Path(__file__).resolve().parents[1] / "werkwijze" / "aannemerszoeker.md", encoding="utf-8").read()
mw = Z.modelwerkwijze(ww)
check("X4 de werkwijze naar het model noemt geen van beide firma's", not S.noemt_een_firma(mw) and "Wat ik nooit doe" in mw)
sy, ge = Z.opdracht(ww, "dakwerken", "3000 Leuven", 25, "uitvoering", "2026-10-30", "", Z.kennis_voor_model(
    "- De Contractmaker (contracten-agent, h-architects): dossiers\n- De Postwacht (post, mail): post", [{"les": "Meet eerst."}]))
check("X4 en X13 de opdracht aan het model noemt geen firma, wel lessen en collega's",
      not S.noemt_een_firma(sy + ge) and "Meet eerst." in sy and "De Postwacht" in sy and "Contractmaker" not in sy)
check("X5 een straat in de gemeente gaat niet naar buiten",
      Q.naar_buiten_fouten({"werk": "dak", "gemeente": "Voorbeeldstraat 1, 3000 Leuven"}) != [])
check("X5 een naam na 'bij' in het werk gaat niet naar buiten",
      "naam" in Q.naar_buiten_fouten({"werk": "dakwerken bij Jan Voorbeeld", "gemeente": "3000 Leuven"}))
check("X5 een firmanaam in het werk gaat niet naar buiten",
      "een firmanaam" in Q.naar_buiten_fouten({"werk": "dak zoals Harmonie Bouw", "gemeente": "3000 Leuven"}))
check("controle 3: een naam zonder postcode als gemeente gaat niet naar buiten",
      Q.naar_buiten_fouten({"werk": "dakwerken", "gemeente": "Jan Voorbeeld"}) != [])
for schrijf in ("H. Architects", "H.Architects", "H_Architects", "H - Architects", "Harmonie.Bouw", "Harmonie_Bouw"):
    andere = S.HA if schrijf.lower().startswith("harmonie") else S.HB
    check(f"controle 3: '{schrijf}' wordt herkend", not S.mag_weg(f"Beste {schrijf} BV,", andere))
check("X5 een gewone vraag mag weg", Q.naar_buiten_fouten({"werk": "plat dak EPDM", "omvang": "40 m2",
                                                          "gemeente": "3010 Kessel-Lo"}) == [])
K = "https://kbopub.economie.fgov.be/kbopub/toonondernemingps.html?ondernemingsnummer=0537405239"
check("X6 'Niet actief' is niet actief", Z.kbo_actief("0537.405.239", {K: "0537.405.239 Status: Niet actief"}) is False)
check("X6 een nagemaakte KBO-host telt niet", Z.kbo_actief("0537.405.239", {
    "https://kbopub.economie.fgov.be.voorbeeld.com/?ondernemingsnummer=0537405239": "0537.405.239 Status: Actief"}) is None)
check("X6 een KBO-pagina van een ander nummer telt niet", Z.kbo_actief("0537.405.239", {
    K.replace("0537405239", "0403170701"): "0537.405.239 Status: Actief"}) is None)
check("X6 het woord actief zonder statusregel telt niet", Z.kbo_actief("0537.405.239", {K: "0537.405.239 actief sinds 2014"}) is None)
leeg = Z.keur([{"naam": "Leeg", "url": "https://leeg.voorbeeld.com"}], {"https://leeg.voorbeeld.com": ""}, None, 25, lambda p: None)
check("X6 een gelezen pagina zonder tekst bewijst niets", leeg["afgewezen"] and not leeg["na_te_kijken"])
x8 = F.lees(pdf("Subtotaal excl. btw 2.000,00", "Totaal excl. btw 12.000,00", "Sub-totaal excl. btw 3.000,00", "btw 21%",
                "Totaal incl. btw 14.520,00"))
check("X8 een subtotaal na het totaal overschrijft het totaal niet", x8["excl"] == 12000.0 and not any("rekenfout" in r for r in x8["redenen"]), x8)
check("X8 de Engelse schrijfwijze", F.bedrag("1,234.56") == 1234.56 and F._laatste_bedrag("Total excl. VAT 1,234.56") == 1234.56)
x8b = F.lees(pdf("Totaal excl. btw 5.000,00", "Totaal excl. btw 7.000,00", "btw 6%"))
check("X8 twee eindtotalen: het grootste, met een melding", x8b["excl"] == 7000.0 and any("meer dan een" in r for r in x8b["redenen"]))
p9, r9 = F.keur_posten({"offertes": {"A": {"posten": [{"nr": "1", "totaal": "4.000,00"}, {"nr": "2", "totaal": "6.000,00"},
                                                      {"nr": "3", "totaal": "1.500,00", "optie": True}]}}},
                       {"A": "4.000,00 6.000,00 1.500,00"}, {"A": 10000.0})
check("X9 een optie staat apart, niet in de vergelijking", p9["A"] == {"1": 4000.0, "2": 6000.0} and any("optie" in x for x in r9["A"]))
p9b, r9b = F.keur_posten({"offertes": {"A": {"posten": [{"nr": "1", "totaal": "4.000,00"}]}}}, {"A": "4.000,00"}, {"A": None})
check("X9 zonder bevestigd totaal geen vergelijking per post", p9b["A"] == {} and r9b["A"])
r10 = F.redigeer("Werf: Voorbeeldstraat 1\nProject: Renovatie bij de klant\nLevering te Kerkplein 12 bus 3.\nPlaatsen van ramen.")
check("X10 werfregel en adressen weg, het werk blijft", "Voorbeeldstraat" not in r10 and "Kerkplein 12" not in r10
      and "Plaatsen van ramen." in r10, r10)
check("X10 de offerte gaat nog niet naar de AI", F.OFFERTE_NAAR_AI is False)
klok = iter([0, 10, 999, 999]).__next__
gl, tk = F.lees_bestanden([("A", {"pad": "/a"}, "a"), ("B", {"pad": "/b"}, "b"), ("C", {"pad": "/c"}, "c")],
                          lambda p: (_ for _ in ()).throw(OSError("weg")), deadline=100, klok=klok)
check("X11 na de deadline geen download meer; elke offerte staat erbij", [g["lees"]["soort"] for g in gl] == ["onleesbaar"] * 3
      and "tijd van de ronde" in gl[2]["lees"]["redenen"][0])
oproepen = []
def rpc_nep(pad, body):
    oproepen.append(pad)
    return {"matches": [{"metadata": {"metadata": {".tag": "folder", "name": f"m{len(oproepen)}", "path_display": f"/x/m{len(oproepen)}"}}}],
            "has_more": True, "cursor": "c"}
tr = E._dropbox_zoek("dak", "/x", rpc=rpc_nep)
check("X12 vervolgpagina's gelezen, met een grens", len(tr) == E.MAX_PAGINAS and oproepen[1] == "files/search/continue_v2")
check("eigen mappen: een map die de andere firma noemt, telt niet", E.in_mappen(S.HA, "ruwbouw", zoek=lambda q, p: [
    {"soort": "folder", "naam": "01 Harmoniebouw - ruwbouw", "pad": "/Work All/01. H-A WORK/x/2999 S 1/Offerte/01 Harmoniebouw - ruwbouw"}]) == [])


print("\nRegressie na controle 3 van Codex (X1 tot X11)")
for nr in ("016/79.32.96", "016 79 32 96", "+32 (0)16 79.32.96", "0491/94.68.79"):
    check(f"X1 het nummer van H-A in de vorm {nr} wordt herkend", not S.mag_weg(f"Bel {nr}", S.HB))
check("X1 het ondernemingsnummer van HB zonder punten wordt herkend", not S.mag_weg("BE0537405239", S.HA))
kern_nep = lambda sql: [{"code": "HARC", "kbo": "0999.999.996", "straat": "Voorbeeldlaan", "nr": "7", "weergave": ""},
                        {"code": "HARM", "kbo": "0537.405.239", "straat": "Voorbeeldplein", "nr": "5", "weergave": ""}]
check("X1 gegevens uit kern gelezen", S.laad_kern(kern_nep))
check("X1 het adres van H-A uit kern wordt herkend", not S.mag_weg("Levering aan Voorbeeldlaan 7, Leuven", S.HB))
check("X1 het ondernemingsnummer van H-A uit kern wordt herkend", not S.mag_weg("btw BE 0999 999 996", S.HB))
check("X1 een gewoon nummer blijft toegelaten", S.mag_weg("Bel 0470 11 22 33 of mail info@dak.voorbeeld.com", S.HB))
kbo_alleen = Z.keur([{"naam": "Dak Een", "url": K, "postcode": "3020", "gemeente": "Herent", "ondernemingsnummer": "0537.405.239"}],
                    {K: "0537.405.239 Status: Actief 3020 Herent" + VUL}, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("X2 een KBO-pagina alleen is geen eigen pagina", not kbo_alleen["goed"] and kbo_alleen["afgewezen"])
ver = Z.keur([{"naam": "Dak Ver", "url": "https://dak-ver.voorbeeld.com", "postcode": "3000", "gemeente": "Leuven"}],
             {"https://dak-ver.voorbeeld.com": "Dak Ver, 8000 Brugge" + VUL}, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("X3 een gemeente die niet op de site staat, maakt de firma niet dichtbij", not ver["goed"] and ver["na_te_kijken"]
      and ver["na_te_kijken"][0].get("vestiging_onbewezen"))
kn = Z.kennis_voor_model("- De Postwacht (post, mail): post", [{"les": "Klant: Jan Voorbeeld, Voorbeeldstraat 1 belde."},
                                                               {"les": "Meet eerst."}])
check("X4 geen persoon of adres in de kennis naar het model", "Voorbeeld" not in kn and "Meet eerst." in kn)
check("X6 een losse naam op een eigen regel wordt weggehaald", "Jan Voorbeeld" not in F.redigeer("Offerte\nJan Voorbeeld\nRamen plaatsen"))
x7 = F.lees(pdf("Totaal excl. btw 12.000,00", "Korting 1.000,00", "Totaal excl. btw na korting 11.000,00", "btw 6%"))
check("X7 het totaal na korting wint van het bruto totaal", x7["excl"] == 11000.0, x7)
x7b = F.lees(pdf("Totaal excl. btw 12.000,00", "Totaal excl. btw 9.500,00", "btw 6%"))
check("X7 zonder aanduiding: het laatste totaal, met een melding", x7b["excl"] == 9500.0 and any("kijk het na" in r for r in x7b["redenen"]))
oproepen.clear()
tr = E._dropbox_zoek("dak", "/x", rpc=rpc_nep)
check("X8 meer pagina's dan de grens: onvolledig, en dat wordt gezegd", tr.volledig is False and len(tr) == E.MAX_PAGINAS)
onv = E.Onvolledig(); onv.volledig = False
check("X8 het verslag zegt dat de eigen mappen niet volledig gelezen zijn", "niet alle treffers" in V.zoekverslag(
    v, {}, res, onv, mails, {}, True, [], "2026-10-30"))
check("X9 'onze groep D' is bouwtaal", S.mag_weg("Onze groep D zorgt voor de ventilatie.", S.HB))


print("\nRegressie na controle 4 van Codex (X1 tot X10)")
check("X1 zonder beide firma's in kern: geen werk", S.laad_kern(lambda sql: [{"code": "HARC", "kbo": "", "straat": "", "nr": ""}]) is False)
check("X1 een onleesbare kern: geen werk", S.laad_kern(lambda sql: []) is False)
check("X2 'Harm BV' wordt als de andere firma herkend", S.is_andere_firma("Harm BV", S.HA) and S.is_andere_firma("harc nv", S.HB))
lijst = Z.keur([{"naam": "Dak Lijst", "url": "https://lijst.voorbeeld.com", "adres": "Zeedijk 3", "postcode": "3000", "gemeente": "Leuven",
                 "ondernemingsnummer": "0537.405.239"}],
               {"https://lijst.voorbeeld.com": "Dak Lijst, Zeedijk 3, 8000 Brugge. Werkgebied: Leuven 3000, Herent 3020." + VUL, K:
                "0537.405.239 Status: Actief" + VUL}, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("X3 een postcode in de lijst van het werkgebied is geen vestiging", not lijst["goed"] and lijst["na_te_kijken"])
for tekst in ("dakwerken bij JAN PEETERS", "plat dak, werf GROTE MARKT 12", "ramen voor Jan Peeters"):
    check(f"X4 '{tekst}' gaat niet naar buiten", Q.naar_buiten_fouten({"werk": tekst, "gemeente": "3000 Leuven"}) != [])
check("X4 gewone vakwoorden in hoofdletters blijven toegelaten", Q.naar_buiten_fouten(
    {"werk": "plat dak EPDM met PIR-isolatie", "gemeente": "3000 Leuven"}) == [])
check("X4 een les met een naam in hoofdletters gaat niet naar het model", "PEETERS" not in Z.kennis_voor_model(
    "", [{"les": "Bel JAN PEETERS terug."}, {"les": "Meet eerst."}]))
import regisseur as RG  # noqa: E402
check("X5 een antwoord over HB met de naam van H-A wordt tegengehouden", RG.bouw_grendel(
    "Drie dakwerkers gevonden, zie ook H-Architects.", {S.HB}) == RG.BOUW_GEWEIGERD)
check("X5 een antwoord over twee firma's gaat niet samen", RG.bouw_grendel("x", {S.HA, S.HB}) == RG.BOUW_TWEE)
check("X5 een gewoon antwoord over HB blijft", RG.bouw_grendel("Drie dakwerkers gevonden.", {S.HB}) == "Drie dakwerkers gevonden.")
check("X5 de firma uit de vraag en uit de sleutel", RG.bouw_firmas("agent_ronde", {"naam": "aannemerszoeker", "vraag": "firma: HB; werk: x"}, {})
      == {S.HB} and RG.bouw_firmas("klaargezet", {"naam": "offertevergelijker"}, {"items": [{"sleutel": "HA:abc"}]}) == {S.HA})
r6 = F.redigeer("Offerte voor Jan Voorbeeld, werf Grote Markt 12, plaatsen van ramen.")
check("X6 inline naam en adres weg", "Jan Voorbeeld" not in r6 and "Markt 12" not in r6 and "plaatsen van ramen" in r6, r6)
x7c = F.lees(pdf("Totaal excl. btw 12.000,00", "Totaal excl. btw na 10% korting 11.000,00", "btw 6%"))
check("X7 'na 10% korting' is het eindtotaal", x7c["excl"] == 11000.0, x7c)
check("X7 een prijsindicatie is een raming", F.lees(pdf("Prijsindicatie dakwerken", "Totaal excl. btw 8.000,00"))["raming"])
check("X8 'onze groep warmtepompen' is bouwtaal", S.mag_weg("Onze groep warmtepompen wordt vervangen.", S.HB))
uitrol = open(Path(__file__).resolve().parents[1] / "docs" / "bouw" / "uitrol.sh", encoding="utf-8").read()
check("X9 de uitrol stopt buiten main of als de VM niet gelijk is aan origin/main",
      "rev-parse --abbrev-ref HEAD" in uitrol and "rev-parse origin/main" in uitrol)


print("\nRegressie na controle 5 van Codex en het herbekeken ontwerp (X1 tot X9)")
proj = Z.keur([{"naam": "Dak Proj", "url": "https://proj.voorbeeld.com", "adres": "Kerkstraat 2", "postcode": "3000",
                "gemeente": "Leuven", "ondernemingsnummer": "0412.345.614"}],
              {"https://proj.voorbeeld.com": "Realisatie: Kerkstraat 2, 3000 Leuven. Contact Zeedijk 3, 8000 Brugge." + VUL,
               K.replace("0537405239", "0412345614"): "0412.345.614\nStatus: Actief\nAdres van de zetel:\nZeedijk 3\n8000 Brugge"},
              PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("X1 de afstand komt van de zetel in de KBO, niet van een projectadres op de site",
      not proj["goed"] and proj["buiten"] and proj["buiten"][0]["zetel"] == "8000 Brugge")
check("X1 zonder zetel in de KBO: na te kijken", Z.kbo_zetel("0537.405.239", {K: "0537.405.239 Status: Actief"}) is None)
check("X1 een gemeente met streepjes", Z.kbo_zetel("0537.405.239", {K: "Adres van de zetel:\nX 1\n3010 Kessel-Lo\nSinds"}) == "3010 Kessel-Lo")
x2 = F.lees(pdf("Totaal excl. btw 10.000,00 btw 21% 2.100,00 incl. btw 12.100,00"))
check("X2 exclusief, btw en inclusief op een regel", x2["excl"] == 10000.0 and x2["incl"] == 12100.0, x2)
check("X2 de labels per bedrag", F.bedragen_met_label("Totaal: excl. 1.000,00 / incl. 1.210,00") == [("excl", 1000.0), ("incl", 1210.0)])
for tekst, weg in (("dakwerken voor jan peeters", ["jan", "peeters"]), ("gevelrenovatie bij familie De Smet", ["familie", "Smet"])):
    gefilterd, weggelaten = W.filter_tekst(tekst)
    check(f"X3 '{tekst}': de naam valt weg voor het naar buiten gaat", all(w in weggelaten for w in weg)
          and not any(w.lower() in gefilterd.lower().split() for w in weg), (gefilterd, weggelaten))
for tekst in ("plat dak EPDM met PIR-isolatie 40 m2", "vloerverwarming en chape gelijkvloers 85 m2", "dakgoten in zink vervangen",
              "ventilatie systeem D met warmtepomp", "plafonneerwerken muren en plafonds 120 m2"):
    check(f"X3 vakwoorden blijven: '{tekst}'", W.filter_tekst(tekst)[1] == [], W.filter_tekst(tekst))
check("X4 kern zonder ondernemingsnummer of adres: geen werk", S.laad_kern(lambda sql: [
    {"code": "HARC", "kbo": "", "straat": "", "nr": ""}, {"code": "HARM", "kbo": "0537.405.239", "straat": "X", "nr": "1"}]) is False)
check("X5 het werkverslag of dossier van een bouwagent: nooit beide firma's in een antwoord",
      RG.bouw_grendel("Ik werk voor H-Architects en voor Harmonie Bouw.", RG.bouw_firmas("agent_verslag", {"naam": "aannemerszoeker"}, {}))
      == RG.BOUW_TWEE and RG.bouw_grendel("Drie vragen afgewerkt.", {"?"}) == "Drie vragen afgewerkt.")
check("X6 een naam in hoofdletters binnen een zin wordt weggehaald", "PEETERS" not in F.redigeer("Offerte voor de woning van JAN PEETERS."))
check("X7 'aanverwante werken' is bouwtaal", S.mag_weg("Ook aanverwante werken.", S.HB) and not S.mag_weg("Een verwante firma.", S.HB))
x8 = F.lees(pdf("Project gestart 01-01-2026", "Datum: 15-10-2026", "Totaal excl. btw 5.000,00", "btw 6%", "Geldig 30 dagen"))
check("X8 de offertedatum komt van het label, niet van de eerste datum", x8["datum"] == date(2026, 10, 15)
      and x8["geldig_tot"] == date(2026, 11, 14), x8)
check("X8 zonder label: datum onbekend, geen geldigheid berekend", F.lees(pdf("Project 01-01-2026", "Totaal excl. btw 5.000,00",
      "Geldig 30 dagen"))["geldig_tot"] is None)


print("\nRegressie na controle 6 van Codex (X1 tot X8)")
check("X1 alleen de officiele gemeente van Geopunt gaat naar buiten", Q.officiele_gemeente(
    {"postcode": "3000", "gemeente": "Leuven"}) == "3000 Leuven" and Q.officiele_gemeente(None) is None
    and Q.officiele_gemeente({"postcode": "", "gemeente": "Jan Peeters"}) is None)
nieuws = Z.keur([{"naam": "Dak Nieuws", "url": "https://krant.voorbeeld.com/artikel", "postcode": "3020", "gemeente": "Herent",
                  "ondernemingsnummer": "0537.405.239"}], {"https://krant.voorbeeld.com/artikel": "Nieuws over het weer." + VUL,
                 K: GELEZEN[K]}, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("X2 een pagina zonder het ondernemingsnummer bewijst de site niet: na te kijken", not nieuws["goed"] and nieuws["na_te_kijken"]
      and nieuws["na_te_kijken"][0]["site_bewezen"] is False)
with_nr = Z.nummer_op_site("0537.405.239", "https://dak-een.voorbeeld.com", {"https://dak-een.voorbeeld.com/contact": "BTW BE0537 405 239"})
check("X2 het nummer op een andere pagina van dezelfde site telt", with_nr)
import inspect  # noqa: E402
bron = inspect.getsource(RG.dossier)
check("X3 het dossier van een bouwagent laadt geen verslagen", "aan in BOUW_AGENTS" in bron)
check("X4 'medecontractant is niet van toepassing' is geen btw verlegd", not F.verlegd("Medecontractant is niet van toepassing."))
check("X4 'deze offerte vervangt de eerdere raming' is geen raming", not F.is_raming("Offerte 12\nDeze offerte vervangt de eerdere raming."))
check("X4 een raming in de kop blijft een raming", F.is_raming("Kostenraming dakwerken\nTotaal 8.000,00"))
x4 = F.lees(pdf("Totaal incl. btw 12.100,00", "btw 21%", "Medecontractant: btw verlegd"))
check("X4 btw verlegd en toch een tarief: niet berekend, wel gemeld", x4["excl"] is None and any("verlegd en toch" in r for r in x4["redenen"]), x4)
for schrijf, andere in (("H.B. BV", S.HA), ("H A Architects", S.HB), ("Gerzenstr. 5", S.HA), ("5 Gerzenstraat", S.HA)):
    check(f"X5 '{schrijf}' wordt herkend", not S.mag_weg(f"Zie {schrijf}.", andere))
S.laad_kern(kern_nep)
check("X5 het adres uit kern met afkorting en nummer ervoor", not S.mag_weg("Levering 7 Voorbeeldlaan", S.HB)
      and not S.mag_weg("Voorbeeldln. 7", S.HB))
check("X6 een naam voor een adres wordt weggehaald", "Jan Peeters" not in F.redigeer("Jan Peeters, Voorbeeldlaan 7"))
check("X7 'eigen aannemer', 'vaste aannemer' en 'partner van de fabrikant' zijn gewone taal",
      S.mag_weg("Geplaatst door de eigen aannemer of een vaste aannemer, partner van de fabrikant.", S.HB))
check("X7 'onze vaste aannemer' blijft verboden", not S.mag_weg("Dit doet onze vaste aannemer.", S.HA))


print("\nRegressie na controle 7 van Codex (X1 tot X6)")
voet = Z.keur([{"naam": "Dak Voet", "url": "https://voet.voorbeeld.com/blog", "postcode": "3020", "gemeente": "Herent",
                "ondernemingsnummer": "0537.405.239", "bewijs": "Wij leggen platte daken in EPDM"}],
              {"https://voet.voorbeeld.com/blog": "Recept van de week: soep." + VUL + " BTW BE 0537.405.239", K: GELEZEN[K]},
              PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("X1 alleen het nummer in de voettekst bewijst de site niet", not voet["goed"] and voet["na_te_kijken"])
x2 = F.lees(pdf("Totaal excl. BTW 10.000,00, geldig 30 dagen", "levering in 6 weken, totaal incl. btw 10.600,00", "btw 6%"))
check("X2 '30 dagen' en '6 weken' zijn geen bedrag", x2["excl"] == 10000.0 and x2["incl"] == 10600.0, x2)
check("X2 een bedrag zonder decimalen met euroteken telt wel", F.bedragen_met_label("Totaal excl. btw € 9500") == [("excl", 9500.0)])
for schrijf, andere in (("H B BV", S.HA), ("H A BV", S.HB), ("Gerzenstraat 5A", S.HA), ("5A Gerzenstraat", S.HA)):
    check(f"X3 '{schrijf}' wordt herkend", not S.mag_weg(f"Zie {schrijf}.", andere))
r4 = F.redigeer("Klantnaam: Jan Peeters\nLivraison Rue Neuve 3, Bruxelles\nRamen plaatsen")
check("X4 klantnaam en een Frans adres worden weggehaald", "Peeters" not in r4 and "Neuve 3" not in r4 and "Ramen plaatsen" in r4, r4)
check("X5 'zusterbalk' is bouwtaal, 'zusterbedrijf' niet", S.mag_weg("Een zusterbalk naast de balk.", S.HB)
      and not S.mag_weg("Ons zusterbedrijf.", S.HB))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
