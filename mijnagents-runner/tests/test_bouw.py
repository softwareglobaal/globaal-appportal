"""Grendels van de afdeling Bouw: De Aannemerszoeker en De Offertevergelijker.

Driehoeksoverleg 30-10-2026 (ontwerp, docs/bouw/rapport-1-ontwerp.md). Alleen verzonnen firma's en voorbeeld.com-links;
geen echte bouwheren, adressen of offertes.

Draaien: python3 mijnagents-runner/tests/test_bouw.py
"""
import json
import sys
import time
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
check("01-11-2026: het model weet dat de firma bewust weggelaten is en begint meteen, zonder een firma te noemen",
      "bewust weggelaten" in sys_ and "nooit voor welke firma" in sys_ and not S.noemt_een_firma(sys_))

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
_aan, F.OFFERTE_NAAR_AI = F.OFFERTE_NAAR_AI, False
try:
    F.posten_uit_model({"A": "x"}, vraag=lambda *a, **k: {"tekst": "{}"})
    check("zonder ja van Mehdi gaat geen offerte naar de AI (X5)", False)
except PermissionError:
    check("zonder ja van Mehdi gaat geen offerte naar de AI (X5)", True)
F.OFFERTE_NAAR_AI = _aan
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
check("X5 ja van Mehdi op 01-11-2026: de offerte gaat via zijn abonnement naar Claude", F.OFFERTE_NAAR_AI is True)
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

# 01-11-2026: Geopunt geeft bij een gemeente zonder straat geen postcode; het postinfo-register bevestigt die uit de vraag
GEO_GEMEENTE = {"postcode": None, "gemeente": "Herent", "lat": 50.9, "lon": 4.6}
POSTINFO = {"3020": "Herent", "3000": "Leuven"}.get
check("een gemeente zonder postcode van Geopunt krijgt de postcode uit de vraag als het register ze bevestigt",
      Q.officiele_gemeente(Q.met_postcode(GEO_GEMEENTE, "3020 Herent", POSTINFO)) == "3020 Herent")
check("een postcode van een andere gemeente gaat nooit naar buiten",
      Q.officiele_gemeente(Q.met_postcode(GEO_GEMEENTE, "3000 Herent", POSTINFO)) is None)
check("een postcode die het register niet kent gaat nooit naar buiten",
      Q.officiele_gemeente(Q.met_postcode(GEO_GEMEENTE, "3021 Herent", POSTINFO)) is None)
check("een postcode van Geopunt zelf blijft staan, zonder het register te vragen",
      Q.met_postcode({"postcode": "3000", "gemeente": "Leuven"}, "3020 Herent", lambda pc: 1 / 0)["postcode"] == "3000")
check("zonder punt of zonder postcode in de vraag verandert er niets",
      Q.met_postcode(None, "3020 Herent", POSTINFO) is None
      and Q.officiele_gemeente(Q.met_postcode(GEO_GEMEENTE, "Herent", POSTINFO)) is None)
check("De Aannemerszoeker laat de postcode bevestigen door het register",
      "Q.met_postcode(lokaliseer(gemeente), gemeente, postinfo_gemeente)" in open(
          Path(__file__).resolve().parents[1] / "aannemerszoeker.py", encoding="utf-8").read())
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


print("\nRegressie na controle 8 van Codex (X1 tot X8)")
tooltekst = next(t["description"] for t in RG.TOOLS if t["name"] == "agent_ronde")
check("X1 de tooltekst van De Regisseur noemt geen firma", not S.noemt(tooltekst, S.HA) and not S.noemt(tooltekst, S.HB))
x2 = F.lees(pdf("Totaal excl. btw: nog te bepalen, geldig tot 30.10.2026", "btw 21%"))
check("X2 een datum is nooit een bedrag", x2["excl"] is None, x2)
fant = Z.keur([{"naam": "Dakwerken Fantasio", "url": "https://dak-een.voorbeeld.com", "postcode": "3020", "gemeente": "Herent",
                "ondernemingsnummer": "0537.405.239", "bewijs": "Dakwerken, platte daken, EPDM, renovatie"}],
              GELEZEN, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
check("X3 een naam die niet op de site staat ('Fantasio'): niet bovenaan", not fant["goed"] and fant["na_te_kijken"])
check("X4 'indicatieve uitvoeringstermijn' maakt een offerte geen raming",
      not F.is_raming("Offerte dakwerken\nIndicatieve uitvoeringstermijn: 6 weken") and F.is_raming("Indicatieve prijs dakwerken"))
for schrijf, andere in (("h a bv", S.HB), ("Gerzenstraat nr. 5A", S.HA), ("19 Hoveniersstraat", S.HA)):
    check(f"X5 '{schrijf}' wordt herkend", not S.mag_weg(f"Zie {schrijf}.", andere))
check("X5 het adres uit kern met nr. ertussen", not S.mag_weg("Voorbeeldlaan nr. 7", S.HB))
vt = V.vergelijkingsverslag({"firma": S.HA, "project": "2999"}, "06 ventilatie", lt, F.vergelijk(
    [{"letter": "A", "lees": a}, {"letter": "B", "lees": b}], date(2026, 10, 30)), None, {}, "2026-10-30", False)
check("X6 zonder vergelijking per post zegt de eerste regel dat alleen de totalen vergeleken zijn",
      "alleen de totalen" in vt.splitlines()[0])
check("X7 een Frans adres met het nummer vooraan wordt weggehaald", "Neuve" not in F.redigeer("Livraison 3 Rue Neuve, 1000 Bruxelles"))


print("\nRegressie na controle 9 van Codex (X2 tot X7)")
for schrijf, andere in (("h.a. bv", S.HB), ("h.b. bv", S.HA), ("H. A. BV", S.HB), ("h.b.bv", S.HA)):
    check(f"X2 '{schrijf}' wordt herkend", not S.mag_weg(f"Zie {schrijf}.", andere))
verlopen = F.lees(pdf("Totaal excl. btw 7.000,00", "btw 21%", "geldig tot 01-09-2026"))
u9 = F.vergelijk([{"letter": "A", "lees": verlopen}, {"letter": "B", "lees": a}], date(2026, 10, 30))
check("X3 een verlopen offerte staat nooit bovenaan als laagste", u9["laagste"]["letter"] == "B")
check("X4 een indicatieve offerte is niet bindend: als raming gemeld", F.is_raming("Indicatieve offerte dakwerken"))
c5 = {"naam": "Dak Een", "url": "https://dak-een.voorbeeld.com", "email": "verzonnen@voorbeeld.com", "telefoon": "0470 99 99 99"}
Z.contact_van_site(c5, {"https://dak-een.voorbeeld.com": "Contact: info@dak-een.voorbeeld.com, tel 016 12 34 56"})
check("X5 een mailadres of telefoon dat niet op de site staat, valt weg", c5["email"] is None and c5["telefoon"] is None)
c5b = {"naam": "Dak Een", "url": "https://dak-een.voorbeeld.com", "email": "info@dak-een.voorbeeld.com", "telefoon": "+32 16 12 34 56"}
Z.contact_van_site(c5b, {"https://dak-een.voorbeeld.com/contact": "Contact: info@dak-een.voorbeeld.com, tel 016/12.34.56"})
check("X5 wat wel op de site staat, blijft", c5b["email"] and c5b["telefoon"])
check("X6 een huisnummer voor de straat wordt weggehaald", "Voorbeeldlaan" not in F.redigeer("Levering 3 Voorbeeldlaan, Leuven"))
check("X7 de uitrol stopt zonder pypdf", "import pypdf" in uitrol or "import pypdf" in open(
    Path(__file__).resolve().parents[1] / "docs" / "bouw" / "uitrol.sh", encoding="utf-8").read())

print("\nHet adres van de zetel in kern, uit de KBO (01-11-2026)")
from bouw import kern_adres as K  # noqa: E402


def kbo_pagina(nummer="0123.456.749", adres="Voorbeeldstraat&nbsp;12 bus 3\n<br/>3000&nbsp;Leuven"):
    return ('<tr><td class="QL">Ondernemingsnummer:</td><td class="QL" colspan="3">' + nummer + '</td></tr>'
            '<tr><td class="RL">Adres van de zetel:</td><td class="RL" colspan="3">\n' + adres +
            '\n<span class="upd"><br/>Sinds 1 januari 2020</span></td></tr>')


check("de zetel wordt gelezen: straat, nummer met bus, postcode en gemeente",
      K.zetel(kbo_pagina(), "0123456749") == {"straat": "Voorbeeldstraat", "huisnummer": "12 bus 3", "postcode": "3000",
                                              "gemeente": "Leuven"})
check("een pagina met een ander ondernemingsnummer geeft geen adres", K.zetel(kbo_pagina(), "0123456750") is None)
check("een adres zonder huisnummer geeft geen adres", K.zetel(kbo_pagina(adres="Voorbeeldstraat<br/>3000 Leuven"),
                                                              "0123456749") is None)


class NepKern:
    def __init__(self, rijen):
        self.rijen, self.sql = rijen, []

    def __call__(self, sql):
        self.sql.append(sql)
        if sql == K.SQL_LEES:
            return self.rijen
        if "adres_vind_of_maak" in sql:
            return {"id": "00000000-0000-0000-0000-000000000001"}
        return {"adres": 1, "firma": 1}


leeg = [{"code": "HARC", "kbo": "0123.456.749", "adres_id": None}, {"code": "HARM", "kbo": "0123.456.749", "adres_id": None}]
nk = NepKern(leeg)
regels = K.vul(nk, lambda url: kbo_pagina(), schrijf=False)
check("zonder --schrijf schrijft het niets in kern", len(nk.sql) == 1 and all("zou" in r for r in regels), regels)
nk = NepKern(leeg)
regels = K.vul(nk, lambda url: kbo_pagina(), schrijf=True)
check("met --schrijf krijgen beide firma's het adres", all("gezet" in r for r in regels), regels)
check("het adres komt nooit in de uitvoer", not any("Voorbeeldstraat" in r or "3000" in r for r in regels))
check("een firma met een adres wordt nooit overschreven", all("adres_id is null" in s for s in nk.sql if "update kern.firma" in s))
nk = NepKern([{"code": "HARC", "kbo": "0123.456.749", "adres_id": "x", "straat": "s", "nr": "1"},
              {"code": "HARM", "kbo": "0123.456.749", "adres_id": None}])
regels = K.vul(nk, lambda url: kbo_pagina(adres="Rue d'Exemple 4<br/>1000 Bruxelles"), schrijf=True)
check("een bestaand adres blijft ongemoeid", "ongemoeid" in regels[0] and not any("HARC" in s for s in nk.sql[1:]))
check("een aanhalingsteken in de straat wordt veilig doorgegeven", any("Rue d''Exemple" in s for s in nk.sql))
check("controle 11: een gedeelde adresrij wordt alleen aangevuld als al haar velden leeg zijn",
      all("huisnummer = '' and postcode = '' and gemeente = ''" in s for s in nk.sql if "update kern.adres" in s))
check("controle 11: zonder volledige kern eindigt het hulpmiddel met een fout, zodat de uitrol stopt",
      "sys.exit(0 if compleet else 1)" in open(Path(K.__file__), encoding="utf-8").read())
check("de uitrol vult het adres voor de eerste ronde", "bouw.kern_adres --schrijf" in open(
    Path(__file__).resolve().parents[1] / "docs" / "bouw" / "uitrol.sh", encoding="utf-8").read())

print("\nDe code leest de KBO zelf (01-11-2026: web_fetch van het model opent de KBO niet)")
def kbo_html(nummer="0123.456.749", status="Actief", zetel=None, ve=None):
    h = ('<tr><td class="QL">Ondernemingsnummer:</td><td class="QL" colspan="3">' + nummer + '\n\t</td></tr>'
         '<tr><td class="RL">Status:</td><td class="RL" colspan="3"><strong><span class="pageactief">' + status +
         '</span></strong></td></tr>')
    if zetel:
        h += ('<tr><td class="RL">Adres van de zetel:</td><td class="RL" colspan="3">' + zetel +
              '<span class="upd"><br/>Sinds 1 januari 2020</span></td></tr>')
    if ve:
        h += ('<tr><td class="QL">Aantal vestigingseenheden (VE): </td><td class="QL" colspan="2"><strong>' + ve +
              '</strong>&nbsp; <a href="toonvestigingps.html" class="QL">Gegevens en activiteiten per VE</a><br/></td></tr>')
    return h


def ve_html(nummer="0123.456.749", adres="Voorbeeldstraat&nbsp;12<br/>3020&nbsp;&nbsp;Herent"):
    return ('<tr><td>Ondernemingsnummer:</td><td>' + nummer + '</td></tr><tr><td class="QL">Adres van de vestigingseenheid:<br/></td><td class="QL" colspan="3">\n\t'
            + adres + '<br/><span class="upd">Sinds 1 januari 2020</span></td></tr>')


class NepKbo:
    def __init__(self, hoofd, ve=""):
        self.hoofd, self.ve, self.urls = hoofd, ve, []

    def __call__(self, url):
        self.urls.append(url)
        if "toonvestigingps" in url:
            return self.ve
        return self.hoofd


nk = NepKbo(kbo_html(zetel="Voorbeeldstraat&nbsp;12<br/>3000&nbsp;Leuven"))
check("met een zetel: actief en alleen postcode en gemeente, nooit de straat",
      Z.kbo_van_code("0123.456.749", nk) == {"actief": True, "plaats": "3000 Leuven"} and len(nk.urls) == 1
      and "ondernemingsnummer=0123456749" in nk.urls[0])
nk = NepKbo(kbo_html(ve="1"), ve_html())
check("een natuurlijk persoon zonder zetel: de plaats van de enige vestigingseenheid",
      Z.kbo_van_code("0123456749", nk) == {"actief": True, "plaats": "3020 Herent"} and "toonvestigingps" in nk.urls[1])
nk = NepKbo(kbo_html(ve="2"), ve_html())
check("met meer vestigingseenheden: geen plaats, dus na te kijken", Z.kbo_van_code("0123456749", nk)["plaats"] is None
      and len(nk.urls) == 1)
check("een vestigingspagina met een ander nummer telt niet",
      Z.kbo_van_code("0123456749", NepKbo(kbo_html(ve="1"), ve_html(nummer="0123.456.850")))["plaats"] is None)
check("een KBO-pagina met een ander nummer telt niet",
      Z.kbo_van_code("0123456749", NepKbo(kbo_html(nummer="0123.456.850"))) == {"actief": None, "plaats": None})
nk = NepKbo(kbo_html(status="Stopgezet", ve="1"), ve_html())
check("stopgezet: niet actief en geen vestiging opgezocht", Z.kbo_van_code("0123456749", nk)["actief"] is False
      and len(nk.urls) == 1)
check("een onbekende status is onbekend, nooit actief",
      Z.kbo_van_code("0123456749", NepKbo(kbo_html(status="Iets anders")))["actief"] is None)


def kbo_weg(url):
    raise OSError("kbo weg")


check("lees_kbo: alleen geldige nummers, een keer per nummer",
      list(Z.lees_kbo([{"ondernemingsnummer": "0123.456.749"}, {"ondernemingsnummer": "BE0123456749"},
                       {"ondernemingsnummer": "0123.456.789"}, {"ondernemingsnummer": None}, "x"],
                      NepKbo(kbo_html(zetel="X 1<br/>3000 Leuven")))) == ["0123.456.749"])
check("lees_kbo: een KBO die niet antwoordt laat het nummer weg", Z.lees_kbo([{"ondernemingsnummer": "0123.456.749"}],
                                                                             kbo_weg) == {})
check("lees_kbo: na de deadline leest het niets meer", Z.lees_kbo([{"ondernemingsnummer": "0123.456.749"}],
                                                                  NepKbo(""), deadline=time.monotonic() - 1) == {})
EEN = {"https://dak-een.voorbeeld.com": GELEZEN["https://dak-een.voorbeeld.com"]}


def dak_een():
    return [{"naam": "Dak Een", "url": "https://dak-een.voorbeeld.com", "ondernemingsnummer": "0537.405.239",
             "bewijs": "Dakwerken, platte daken, EPDM, renovatie", "postcode": "3000", "gemeente": "Leuven"}]


zonder = Z.keur(dak_een(), EEN, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
met = Z.keur(dak_een(), EEN, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p),
             {"0537.405.239": {"actief": True, "plaats": "3020 Herent"}})
check("zonder KBO-pagina: na te kijken", [f["naam"] for f in zonder["na_te_kijken"]] == ["Dak Een"] and not zonder["goed"])
check("met de KBO van de code: bovenaan, met de afstand vanaf de KBO-plaats",
      [f["naam"] for f in met["goed"]] == ["Dak Een"] and met["goed"][0]["zetel"] == "3020 Herent"
      and met["goed"][0]["afstand_km"] is not None)
stop = Z.keur(dak_een(), EEN, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p),
              {"0537.405.239": {"actief": False, "plaats": None}})
check("stopgezet volgens de KBO van de code valt weg", not stop["goed"] and not stop["na_te_kijken"])
check("het verslag toont de plaats uit de KBO, niet die van het model",
      "3020 Herent" in V._firma_regel(1, met["goed"][0], S.HB, {}, True)
      and "3000 Leuven" not in V._firma_regel(1, met["goed"][0], S.HB, {}, True))
check("het model leest de KBO niet meer zelf", "lees die dus niet" in Z.VORM and "Zoek het ondernemingsnummer op in" not in Z.VORM)
_az = open(Path(__file__).resolve().parents[1] / "aannemerszoeker.py", encoding="utf-8").read()
check("De Aannemerszoeker geeft de KBO van de code aan de keuring",
      "Z.lees_kbo(firmas, lambda url: kbo_haal(url, timeout=Z.KBO_TIMEOUT), deadline)" in _az and "lokaliseer, kbo)" in _az)
# Codex 15
MET_KBO_PAGINA = dict(EEN, **{k: v for k, v in GELEZEN.items() if "0537405239" in k})
onbekend = Z.keur(dak_een(), MET_KBO_PAGINA, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p),
                  {"0537.405.239": {"actief": None, "plaats": None}})
check("Codex 15-1: las de code de KBO zonder uitslag, dan telt een pagina van het model niet",
      not onbekend["goed"] and onbekend["na_te_kijken"][0]["kbo_actief"] is None and onbekend["na_te_kijken"][0]["zetel"] is None)
check("zonder lezing door de code blijft een gelezen KBO-pagina van het model gelden",
      [f["naam"] for f in Z.keur(dak_een(), MET_KBO_PAGINA, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))["goed"]]
      == ["Dak Een"])
teller = []


def kbo_weg_tel(url):
    teller.append(url)
    raise OSError("kbo weg")


Z.lees_kbo([{"ondernemingsnummer": "0123.456.749"}, {"ondernemingsnummer": "0123456749"}], kbo_weg_tel)
check("Codex 15-2: na een fout wordt hetzelfde nummer niet opnieuw gevraagd", len(teller) == 1)
nk = NepKbo(kbo_html(ve="1"), ve_html())
check("Codex 15-3: geen vestigingspagina als ze niet meer voor de deadline klaar kan zijn",
      Z.kbo_van_code("0123456749", nk, deadline=time.monotonic() + Z.KBO_TIMEOUT - 1)["plaats"] is None and len(nk.urls) == 1)
check("Codex 15-3: geen oproep die niet meer voor de deadline klaar kan zijn",
      Z.lees_kbo([{"ondernemingsnummer": "0123.456.749"}], NepKbo(""), deadline=time.monotonic() + 1) == {})


def ve_weg(url):
    if "toonvestigingps" in url:
        raise OSError("ve weg")
    return kbo_html(ve="1")


check("een vestigingspagina die niet antwoordt laat alleen de plaats leeg", Z.kbo_van_code("0123456749", ve_weg)
      == {"actief": True, "plaats": None})
sys_kbo, _ = Z.opdracht("werkwijze", "dakwerken", "3000 Leuven", 25, "uitvoering", "2026-11-01")
check("Codex 15-4: het model krijgt geen KBO-veld en geen KBO-taak meer", "kbo_url" not in sys_kbo
      and "het web en de KBO" not in sys_kbo and "in de KBO, of null" not in sys_kbo)
_ww = open(Path(__file__).resolve().parents[1] / "werkwijze" / "aannemerszoeker.md", encoding="utf-8").read()
check("de werkwijze zegt dat de code de KBO leest", "leest de code ook zelf" in _ww)

print("\nOp het abonnement van Mehdi, nooit de API-sleutel (Mehdi 01-11-2026)")
import os  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402

import claude_abonnement as CA  # noqa: E402
from bouw import webpagina as WP  # noqa: E402

_oud_env = dict(os.environ)
os.environ.update({"ANTHROPIC_API_KEY": "sk-ant-api-nep", "SALES_ANTHROPIC_API_KEY": "x", "ANTHROPIC_AUTH_TOKEN": "y",
                   "KENNIS_DSN": "postgres://geheim", "PATH": "/usr/bin"})
env = CA.omgeving("sk-ant-oat01-nep", "/tmp/thuis-nep")
check("het kindproces krijgt geen API-sleutel en geen ander geheim", not any(
    k in env for k in ("ANTHROPIC_API_KEY", "SALES_ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "KENNIS_DSN"))
    and env.get("CLAUDE_CODE_OAUTH_TOKEN") == "sk-ant-oat01-nep" and env.get("PATH") == "/usr/bin")
check("controle 17: een eigen lege HOME, geen instellingen of login van de server", env["HOME"] == "/tmp/thuis-nep"
      and env["CLAUDE_CONFIG_DIR"].startswith("/tmp/thuis-nep") and env["XDG_CONFIG_HOME"].startswith("/tmp/thuis-nep"))
os.environ.clear()
os.environ.update(_oud_env)
cmd = CA.opdracht("systeem", ("WebSearch", "WebFetch"), "opus", 25)
check("Claude Code zonder CLAUDE.md, plugins, MCP of andere tools", all(x in cmd for x in (
    "--safe-mode", "--restricted", "--strict-mcp-config", "--no-session-persistence")) and "--bare" not in cmd
    and cmd[cmd.index("--tools") + 1] == "WebSearch,WebFetch" and cmd[cmd.index("--allowedTools") + 1] == "WebSearch,WebFetch")
cmd0 = CA.opdracht("systeem", (), "opus", 2)
check("zonder gereedschap: --tools leeg en niets toegelaten", cmd0[cmd0.index("--tools") + 1] == "" and "--allowedTools" not in cmd0)

INIT = {"type": "system", "subtype": "init", "model": "claude-opus-5-5", "apiKeySource": "none"}
LIMIET_OK = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": False}}
WS = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebSearch", "input": {"query": "dak"}}]}}
WF = {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "WebFetch",
                                                   "input": {"url": "https://www.dakeen.voorbeeld.com/"}}]}}
KLAAR = {"type": "result", "subtype": "success", "is_error": False, "result": "klaar", "num_turns": 3,
         "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 100}}
_NEP = r"""import json, os, sys, time
rec, uit, code = sys.argv[1], sys.argv[2], int(sys.argv[3])
json.dump({"env": dict(os.environ), "cwd": os.getcwd(), "invoer": sys.stdin.read()}, open(rec, "w"))
for regel in open(uit):
    if regel.strip() == "SLAAP":
        time.sleep(30)
    if regel.startswith("STDERR:"):
        sys.stderr.write(regel[7:])
        continue
    print(regel.rstrip("\n"), flush=True)
sys.exit(code)
"""
_echt_opdracht, _echt_bron, _echt_limiet = CA.opdracht, CA.controleer_bron, CA.LIMIET_BESTAND
with tempfile.TemporaryDirectory() as _d:
    CA.LIMIET_BESTAND = os.path.join(_d, "limiet.json")
    CA.controleer_bron = lambda env, cwd: None
    leeg, vol = os.path.join(_d, "leeg.env"), os.path.join(_d, "vol.env")
    open(leeg, "w").write("ANTHROPIC_API_KEY=sk-ant-api-nep\n")
    open(vol, "w").write("sk-ant-oat01-nep\n")
    os.chmod(vol, 0o600)
    _open = os.path.join(_d, "open")
    open(_open, "w").write("sk-ant-oat01-nep\n")
    os.chmod(_open, 0o644)
    check("het gedeelde tokenbestand: alleen met rechten 600", CA.lees_token(vol) == "sk-ant-oat01-nep"
          and CA.lees_token(_open) == "" and CA.lees_token(leeg) == "" and CA.lees_token(os.path.join(_d, "weg")) == "")
    check("een plek voor alle agents op het abonnement (zoals De Prijsonderzoeker)",
          CA.TOKEN_BESTAND.endswith("/.config/prijsonderzoeker/claude-token"))
    nep, rec, uitf = os.path.join(_d, "nep.py"), os.path.join(_d, "rec.json"), os.path.join(_d, "uit.txt")
    open(nep, "w").write(_NEP)

    def nep_claude(regels, code=0):
        open(uitf, "w").write("\n".join(r if isinstance(r, str) else json.dumps(r) for r in regels) + "\n")
        CA.opdracht = lambda *a, **k: [sys.executable, nep, rec, uitf, str(code)]

    def fout_van(**kw):
        try:
            CA.vraag("s", "g", bron=vol, **kw)
            return None
        except CA.Fout as e:
            return e

    _gestart = []
    _echt_draai = CA.draai
    CA.draai = lambda *a, **k: _gestart.append(a) or ("", "", 0, None)
    e = None
    try:
        CA.vraag("s", "g", bron=leeg)
    except CA.Fout as x:
        e = x
    check("zonder token start niets en valt niets terug op de API", e is not None and e.aanmelden and not _gestart)
    CA.draai = _echt_draai

    nep_claude([INIT, LIMIET_OK, WS, WF, KLAAR])
    uit = CA.vraag("systeem", "de vraag", tools=("WebSearch", "WebFetch"), bron=vol)
    r = json.load(open(rec))
    check("de vraag gaat via stdin, in een lege werkmap, met alleen het token", r["invoer"] == "de vraag"
          and "claude-abonnement-" in r["cwd"] and "ANTHROPIC_API_KEY" not in r["env"]
          and r["env"]["CLAUDE_CODE_OAUTH_TOKEN"] == "sk-ant-oat01-nep" and "claude-thuis-" in r["env"]["HOME"])
    check("antwoord, gereedschap, tokens en model uit de stroom", uit["tekst"] == "klaar" and uit["tokens"] == 115
          and uit["beurten"] == 3 and uit["model"] == "claude-opus-5-5"
          and [n for n, _ in uit["gereedschap"]] == ["WebSearch", "WebFetch"])
    _t0 = time.monotonic()
    nep_claude([dict(INIT, apiKeySource="ANTHROPIC_API_KEY"), "SLAAP", KLAAR])
    e = fout_van()
    check("controle 17: meldt Claude Code bij de start toch een API-sleutel, dan stopt de code het proces meteen",
          e is not None and e.soort == "bron" and e.wacht and time.monotonic() - _t0 < 10)
    nep_claude([dict(INIT, apiKeySource="apiKeyHelper"), "SLAAP", KLAAR])
    check("controle 17: ook een apiKeyHelper telt als API-sleutel", fout_van() is not None)
    _t0 = time.monotonic()
    nep_claude([INIT, {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": True}},
                "SLAAP", KLAAR])
    e = fout_van()
    check("controle 17: extra verbruik boven het abonnement stopt het proces meteen", e is not None and e.limiet
          and time.monotonic() - _t0 < 10)
    _gestart.clear()
    CA.draai = lambda *a, **k: _gestart.append(a) or ("", "", 0, None)
    e = fout_van()
    check("controle 18: na extra verbruik start de volgende vraag niet tot het venster voorbij is", e is not None
          and e.limiet and not _gestart)
    CA.draai = _echt_draai
    os.remove(CA.LIMIET_BESTAND)
    nep_claude([INIT, {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed_warning",
                                                                      "resetsAt": time.time() + 3600}}, "SLAAP", KLAAR])
    e = fout_van()
    check("controle 18: een waarschuwing van het abonnement stopt ook", e is not None and e.limiet)
    _echt_onthoud = CA.onthoud_limiet
    os.remove(CA.LIMIET_BESTAND)
    CA.onthoud_limiet = lambda info, bestand=None: False
    e = fout_van()
    CA.onthoud_limiet = _echt_onthoud
    check("controle 20: mislukt het bewaren van een limiet na de vraag, dan is het een limietfout", e is not None
          and e.limiet and "niet te onthouden" in str(e))
    json.dump({"info": {"status": "allowed_warning", "resetsAt": time.time() - 10}}, open(CA.LIMIET_BESTAND, "w"))
    check("een voorbij venster houdt niets meer tegen", CA.bekende_limiet() is None)
    check("controle 18: boven 90 procent van een venster start geen nieuwe vraag", CA.limiet_reden(
        {"status": "allowed", "unifiedWindows": {"seven_day": {"utilization": 0.93}}}) is not None
          and CA.limiet_reden({"status": "allowed", "unifiedWindows": {"seven_day": {"utilization": 0.36}}}) is None)
    os.remove(CA.LIMIET_BESTAND)
    CA.controleer_bron = lambda env, cwd: "bron: Claude Code zou aanmelden met api_key (ANTHROPIC_API_KEY)"
    _gestart.clear()
    CA.draai = lambda *a, **k: _gestart.append(a) or ("", "", 0, None)
    e = fout_van()
    check("controle 18: zegt auth status iets anders dan het abonnement, dan start er niets", e is not None
          and e.soort == "bron" and e.wacht and not _gestart)
    CA.draai = _echt_draai
    CA.controleer_bron = lambda env, cwd: None
    nep_claude([INIT, {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected"}}, "SLAAP", KLAAR])
    e = fout_van()
    check("een bereikte limiet laat de vraag wachten", e is not None and e.limiet)
    os.remove(CA.LIMIET_BESTAND)          # de limiet zonder eindtijd geldt een uur; de volgende proeven beginnen vrij
    nep_claude([INIT, WS, WS, WS, "SLAAP", KLAAR])
    e = fout_van(max_gereedschap=2)
    check("controle 17: een harde grens op zoek- en leesbeurten", e is not None and "zoek- of leesbeurten" in str(e))
    _t0 = time.monotonic()
    nep_claude([INIT, "SLAAP", KLAAR])
    e = fout_van(timeout=2)
    check("na de timeout stopt de code het proces", e is not None and "binnen 2 s" in str(e) and time.monotonic() - _t0 < 10)
    nep_claude([INIT, {"type": "result", "subtype": "success", "is_error": True,
                       "result": "Invalid API key sk-ant-oat01-nep · Please run /login"}], code=1)
    e = fout_van()
    check("een geweigerde login vraagt Mehdi om aan te melden, zonder het token te tonen", e is not None and e.aanmelden
          and "sk-ant-oat01-nep" not in str(e))
    nep_claude([INIT, "STDERR:kapot bij sk-ant-oat01-nep: stream afgebroken"], code=2)
    e = fout_van()
    check("controle 26: zonder eindresultaat staan code en foutuitvoer in de melding, zonder token", e is not None
          and "code 2" in str(e) and "stream afgebroken" in str(e) and "sk-ant-oat01-nep" not in str(e)
          and "[token]" in str(e), str(e))
    nep_claude([INIT, {"type": "result", "subtype": "error_max_turns", "is_error": True}], code=1)
    e = fout_van()
    check("te veel beurten is een fout, geen half antwoord", e is not None and not e.aanmelden and not e.limiet)
CA.opdracht, CA.controleer_bron, CA.LIMIET_BESTAND = _echt_opdracht, _echt_bron, _echt_limiet


def _status(uit, fout=None):
    def run(cmd, **kw):
        if fout:
            raise fout
        _statusrun.append((cmd, kw))
        return subprocess.CompletedProcess(cmd, 0, json.dumps(uit), "")
    return run


_statusrun = []
_oud_beheerd = CA.BEHEERD
with tempfile.TemporaryDirectory() as _bd:
    CA.BEHEERD = (_bd,)
    open(os.path.join(_bd, "managed-settings.json"), "w").write("{}")
    check("beheerde instellingen op de machine: niet starten", str(CA.controleer_bron({}, "/y", run=_status(
        {"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty"}))).startswith("bron"))
CA.BEHEERD = ("/geen/beheerde/map",)
check("auth status met het abonnementstoken: goed", CA.controleer_bron({"HOME": "/x"}, "/y", run=_status(
    {"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty"})) is None
      and _statusrun[0][0][1:] == ["auth", "status"] and _statusrun[0][1]["env"] == {"HOME": "/x"})
check("auth status met een API-sleutel: niet starten", str(CA.controleer_bron({}, "/y", run=_status(
    {"loggedIn": True, "authMethod": "api_key", "apiProvider": "firstParty", "apiKeySource": "ANTHROPIC_API_KEY"}))
    ).startswith("bron"))
check("auth status zonder login of onleesbaar: aanmelden", str(CA.controleer_bron({}, "/y", run=_status(
    {"loggedIn": False}))).startswith("aanmelden") and str(CA.controleer_bron({}, "/y", run=_status(
        {}, OSError("weg")))).startswith("aanmelden"))
CA.BEHEERD = _oud_beheerd
_zv = []
try:
    Z.zoek("w", "dak", "3000 Leuven", 25, "uitvoering", deadline=time.monotonic() + Z.LEESTIJD + 10,
           vraag=lambda *a, **k: _zv.append(1))
    check("controle 18: te weinig tijd in de ronde: de vraag wacht en Claude start niet", False)
except CA.Fout as e:
    check("controle 18: te weinig tijd in de ronde: de vraag wacht en Claude start niet", e.soort == "tijd" and not _zv)
_t0 = time.monotonic()
check("controle 19: een onbekende limietstatus stopt ook", CA.limiet_reden({}) is not None
      and CA.limiet_reden({"status": "allowed"}) is None)
_oud_lb, _oud_draai = CA.LIMIET_BESTAND, CA.draai
CA.LIMIET_BESTAND = "/dev/null/geen/limiet.json"
_gestart = []
CA.draai = lambda *a, **k: _gestart.append(a) or ("", "", 0, None)
with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False) as _tf:
    _tf.write("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-nep\n")
try:
    CA.vraag("s", "g", bron=_tf.name)
    check("controle 19: kan de code een limiet niet onthouden, dan start er geen vraag", False)
except CA.Fout as e:
    check("controle 19: kan de code een limiet niet onthouden, dan start er geen vraag", e.soort == "bron"
          and "niet te onthouden" in str(e) and not _gestart)
with tempfile.TemporaryDirectory() as _d2:
    _ro = os.path.join(_d2, "limiet.json")
    open(_ro, "w").write("{}")
    os.chmod(_ro, 0o444)
    check("controle 20: een limietbestand dat niet te schrijven is, telt als niet schrijfbaar",
          CA.limiet_schrijfbaar(_ro) is False and CA.limiet_schrijfbaar(_d2) is False
          and CA.limiet_schrijfbaar(os.path.join(_d2, "goed", "limiet.json")) is True)
    os.chmod(_ro, 0o644)
os.remove(_tf.name)
CA.LIMIET_BESTAND, CA.draai = _oud_lb, _oud_draai
_t0 = time.monotonic()


_t0 = time.monotonic()
check("controle 18: een trage DNS-opzoeking houdt de code niet op", WP.openbaar_ip(
    "traag.voorbeeld.com", 443, opzoeken=lambda *a, **k: time.sleep(3) or [], timeout=0.2) is None
      and time.monotonic() - _t0 < 1)
check("bewaking: een gewone start en een toegelaten limiet stoppen niets", CA.bewaking(json.dumps(INIT), {}) is None
      and CA.bewaking(json.dumps(LIMIET_OK), {}) is None and CA.bewaking("geen json", {}) is None)

_hier = Path(__file__).resolve().parents[1]
_bronnen = [_hier / "aannemerszoeker.py", _hier / "offertevergelijker.py"] + sorted((_hier / "bouw").glob("*.py"))
_api = [p.name for p in _bronnen if any(w in p.read_text(encoding="utf-8") for w in (
    "from anthropic", "import anthropic", "Anthropic(", "messages.create", "zet_anthropic"))]
check("grendel: geen enkele bouwmodule roept de API aan (alleen claude_abonnement)", _api == [], _api)


def _dns(adres):
    return lambda host, poort, **kw: [(2, 1, 6, "", (adres, poort))]


check("webpagina: een openbaar adres mag", WP.openbaar("https://dakeen.voorbeeld.com/", _dns("93.184.216.34")))
for _url, _ip in (("http://127.0.0.1:3022/api", "127.0.0.1"), ("http://localhost/", "127.0.0.1"),
                  ("http://intern.voorbeeld.com/", "10.0.0.5"), ("http://169.254.169.254/latest/meta-data", "169.254.169.254"),
                  ("https://dakeen.voorbeeld.com:8443/", "93.184.216.34"), ("ftp://dakeen.voorbeeld.com/", "93.184.216.34"),
                  ("file:///etc/passwd", "93.184.216.34")):
    check(f"webpagina: {_url} mag niet", not WP.openbaar(_url, _dns(_ip)))


class _Antw:
    def __init__(self, status=200, soort="text/html; charset=utf-8", data=b"<p>hallo</p>", plaats=None, traag=0):
        self.status, self.soort, self.data, self.plaats, self.traag = status, soort, data, plaats, traag

    def getheader(self, naam):
        return {"Content-Type": self.soort, "Location": self.plaats}.get(naam)

    def read(self, n):
        time.sleep(self.traag)
        stuk, self.data = self.data[:n], self.data[n:]
        return stuk


def _web(antwoorden, verbonden):
    class Verbinding:
        def __init__(self, schema, host, poort, ip, timeout):
            verbonden.append((host, ip))

        def request(self, *a, **k):
            pass

        def getresponse(self):
            return antwoorden.pop(0)

        def close(self):
            pass
    return Verbinding


_vb = []
_dnsrij = iter(["93.184.216.34", "10.0.0.5"])
WP.haal("https://dakeen.voorbeeld.com/", opzoeken=lambda h, p, **k: [(2, 1, 6, "", (next(_dnsrij), p))],
        verbinding=_web([_Antw()], _vb))
check("controle 17: de code verbindt met het gekeurde adres, een tweede opzoeking telt niet", _vb == [("dakeen.voorbeeld.com",
                                                                                                         "93.184.216.34")])


def _dns_naar(tabel):
    return lambda host, poort, **kw: [(2, 1, 6, "", (tabel[host], poort))]


_dnst = {"dakeen.voorbeeld.com": "93.184.216.34", "intern.voorbeeld.com": "10.0.0.5"}
for _naam, _antw, _verwacht in (
        ("een omleiding naar binnen", [_Antw(302, plaats="http://intern.voorbeeld.com/")], "geen openbaar adres"),
        ("te veel omleidingen", [_Antw(301, plaats="/a") for _ in range(WP.MAX_OMLEIDINGEN + 1)], "te veel omleidingen"),
        ("een pdf is geen webpagina", [_Antw(soort="application/pdf")], "geen webpagina"),
        ("een fout van de server", [_Antw(500)], "http 500")):
    try:
        WP.haal("https://dakeen.voorbeeld.com/", opzoeken=_dns_naar(_dnst), verbinding=_web(_antw, []))
        check(f"webpagina: {_naam} wordt geweigerd", False)
    except OSError as e:
        check(f"webpagina: {_naam} wordt geweigerd", _verwacht in str(e), str(e))
_t0 = time.monotonic()
try:
    WP.haal("https://dakeen.voorbeeld.com/", timeout=0.5, opzoeken=_dns_naar(_dnst),
            verbinding=_web([_Antw(data=b"x" * 300000, traag=0.2)], []))
    check("controle 17: een trage pagina stopt na de totale tijd", False)
except OSError as e:
    check("controle 17: een trage pagina stopt na de totale tijd", "te traag" in str(e) and time.monotonic() - _t0 < 3)
check("een omleiding binnen de site wordt gevolgd", WP.haal("http://dakeen.voorbeeld.com/", opzoeken=_dns_naar(_dnst),
      verbinding=_web([_Antw(301, plaats="https://dakeen.voorbeeld.com/nl"), _Antw(data=b"<p>welkom</p>")], [])) ==
      "<p>welkom</p>")
_t0 = time.monotonic()
def _traag_web():
    class Verbinding:
        def __init__(self, *a):
            pass

        def request(self, *a, **k):
            time.sleep(0.4)

        def getresponse(self):
            time.sleep(0.4)
            return _Antw(data=b"x" * 400000, traag=0.4)

        def close(self):
            pass
    return Verbinding


try:
    WP.haal("https://dakeen.voorbeeld.com/", timeout=0.6, opzoeken=_dns_naar(_dnst), verbinding=_traag_web())
    check("controle 19: trage stappen na elkaar stoppen samen op de totale tijd", False)
except OSError as e:
    check("controle 19: trage stappen na elkaar stoppen samen op de totale tijd", time.monotonic() - _t0 < 1.5, str(e))
_t0 = time.monotonic()
_trdb = E._dropbox_zoek("dak", "/x", rpc=lambda m, b: time.sleep(3) or {"matches": []}, deadline=time.monotonic() + 1.5)
check("controle 19: een druppelend antwoord van Dropbox stopt op de deadline", _trdb.volledig is False
      and time.monotonic() - _t0 < 2.5)
_html = ("<html><head><title>x</title><style>.a{}</style></head><body><script>var geheim=1</script><nav>Menu</nav>"
         "<p>Wij leggen&nbsp;EPDM op platte daken.</p><footer>BTW BE 0123.456.749 <a href='mailto:info@dakeen.voorbeeld.com'>"
         "mail ons</a> <span data-cfemail='" + bytes([0x42] + [ord(c) ^ 0x42 for c in "jo@dakeen.voorbeeld.com"]).hex()
         + "'>[email&#160;protected]</span></footer></body></html>")
_t = WP.tekst(_html)
check("webpagina: tekst zonder script en stijl, met mailto en verborgen mailadres", "geheim" not in _t and ".a{}" not in _t
      and "Wij leggen EPDM op platte daken." in _t and "info@dakeen.voorbeeld.com" in _t and "jo@dakeen.voorbeeld.com" in _t, _t)

_gehaald = []


def _haal_nep(url):
    _gehaald.append(url)
    if "kapot" in url:
        raise OSError("weg")
    return {"https://www.dakeen.voorbeeld.com/": "<p>Dak Een BV legt EPDM op platte daken in de regio Leuven.</p>" * 3,
            "https://www.dakeen.voorbeeld.com/contact": "<p>Dak Een BV, BTW BE 0123.456.749, info@dakeen.voorbeeld.com</p>"
            }.get(url, "<p>andere pagina</p>" * 20)


_firmas = [{"naam": "Dak Een BV", "url": "https://www.dakeen.voorbeeld.com/",
            "paginas": ["https://www.dakeen.voorbeeld.com/contact", "https://gids.voorbeeld.com/dakeen",
                        "https://www.dakeen.voorbeeld.com/kapot"]},
           {"naam": "Dak Twee", "url": "https://daktwee.voorbeeld.com/"}]
_lz = Z.lees_sites(_firmas, ["https://daktwee.voorbeeld.com/a", "https://daktwee.voorbeeld.com/b",
                             "https://daktwee.voorbeeld.com/c", "https://daktwee.voorbeeld.com/d"], _haal_nep)
check("de code leest zelf: de url zoals het model ze gaf, bewaard zonder www", "https://www.dakeen.voorbeeld.com/" in _gehaald
      and "https://dakeen.voorbeeld.com" in _lz and "https://dakeen.voorbeeld.com/contact" in _lz)
check("alleen pagina's van de eigen site, een kapotte pagina ontbreekt", not any("gids." in u for u in _gehaald)
      and not any("kapot" in u for u in _lz))
check("hoogstens PER_FIRMA pagina's per firma", sum(1 for u in _gehaald if "daktwee" in u) == Z.PER_FIRMA)
_gehaald.clear()
check("na de deadline leest de code geen pagina meer", Z.lees_sites(_firmas, [], _haal_nep, deadline=time.monotonic() + 1) == {}
      and _gehaald == [])

_vragen = []


def _vraag_nep(systeem, gebruiker, **kw):
    _vragen.append(kw)
    return {"tekst": "```json\n" + json.dumps({"firmas": [
        {"naam": "Dak Een BV", "url": "https://www.dakeen.voorbeeld.com/", "paginas": ["https://www.dakeen.voorbeeld.com/contact"],
         "ondernemingsnummer": "0123.456.749", "email": "info@dakeen.voorbeeld.com", "telefoon": "016 00 00 00",
         "bewijs": "Dak Een BV legt EPDM op platte daken in de regio Leuven."},
        {"naam": "Dak Drie", "url": "https://dakdrie.voorbeeld.com/", "ondernemingsnummer": "0123.456.749",
         "bewijs": "Een zin die alleen in de samenvatting van WebFetch stond."}]}) + "\n```",
            "gereedschap": [("WebSearch", {}), ("WebFetch", {"url": "https://dakdrie.voorbeeld.com/"})], "tokens": 1000,
            "beurten": 4, "stop": "success", "model": "claude-opus-5-5"}


_z = Z.zoek("werkwijze", "plat dak EPDM", "3000 Leuven", 25, "uitvoering", "2026-11-01", deadline=time.monotonic() + 300,
            vraag=_vraag_nep, haal=_haal_nep)
check("zoeken vraagt WebSearch en WebFetch op het abonnement", _vragen[-1]["tools"] == ("WebSearch", "WebFetch")
      and _vragen[-1]["max_beurten"] == Z.MAX_BEURTEN and _z["zoekopdrachten"] == 1 and _z["leesbeurten"] == 1)
_k = Z.keur(_z["gegevens"]["firmas"], _z["gelezen"], {"lat": 50.88, "lon": 4.70}, 25, lambda p: {"lat": 50.9, "lon": 4.7},
            {"0123.456.749": {"actief": True, "plaats": "3000 Leuven"}})
_een = next(f for f in _k["goed"] + _k["na_te_kijken"] if f["naam"] == "Dak Een BV")
_drie = next((f for f in _k["goed"] + _k["na_te_kijken"] + [x["aanbod"] for x in _k["afgewezen"]] if f["naam"] == "Dak Drie"),
             {})
check("een firma met citaat en nummer op de pagina die de code las, staat klaar", _een in _k["goed"] and _een["site_bewezen"]
      and _een["email"] == "info@dakeen.voorbeeld.com" and _een["telefoon"] is None)
check("een citaat dat niet op de pagina staat die de code las, bewijst niets", not _drie.get("site_bewezen"))
check("het model hoort dat de code de pagina's zelf leest", "De code leest die pagina's daarna zelf" in Z.VORM
      and "web_fetch" not in Z.VORM)

_gids = {"https://gids.voorbeeld.com/x": "<p>Dak X legt EPDM op platte daken in de regio Leuven.</p>" * 3,
         "https://gids.voorbeeld.com/y": "<p>Dak Y, BTW BE 0123.456.749, dakwerken.</p>" * 3}
_fg = [{"naam": "Dak X", "url": "https://gids.voorbeeld.com/x", "ondernemingsnummer": "0123.456.749",
        "bewijs": "Dak X legt EPDM op platte daken in de regio Leuven."},
       {"naam": "Dak Y", "url": "https://gids.voorbeeld.com/y"}]
_lg = Z.lees_sites(_fg, ["https://gids.voorbeeld.com/z"], lambda u: _gids.get(u, "<p>andere firma</p>" * 20))
check("controle 17: op een gedeelde gids leest de code alleen de eigen pagina van elke firma", "https://gids.voorbeeld.com/z"
      not in _lg and _fg[0]["_paginas"] == ["https://gids.voorbeeld.com/x"])
_kg = Z.keur(_fg, _lg, {"lat": 50.88, "lon": 4.70}, 25, lambda p: {"lat": 50.9, "lon": 4.7},
             {"0123.456.749": {"actief": True, "plaats": "3000 Leuven"}})
_x = next(f for f in _kg["goed"] + _kg["na_te_kijken"] if f["naam"] == "Dak X")
check("controle 17: het nummer van een andere firma op dezelfde gids bewijst niets", not _x["site_bewezen"] and _x not in _kg["goed"])
_kort = {"https://kort.voorbeeld.com": "Welkom", "https://kort.voorbeeld.com/over":
         "Kort BV legt EPDM op platte daken. BTW BE 0123.456.749. " * 3}
_fk = [{"naam": "Kort BV", "url": "https://kort.voorbeeld.com/", "_paginas": list(_kort), "ondernemingsnummer": "0123.456.749",
        "bewijs": "Kort BV legt EPDM op platte daken."}]
_kk = Z.keur(_fk, _kort, {"lat": 50.88, "lon": 4.70}, 25, lambda p: {"lat": 50.9, "lon": 4.7},
             {"0123.456.749": {"actief": True, "plaats": "3000 Leuven"}})
check("controle 17: een korte homepage met een goede tweede pagina wordt niet geweerd", [f["naam"] for f in _kk["goed"]] == ["Kort BV"])
_db = {"https://een.voorbeeld.com": "<p>Een</p>" * 30, "https://twee.voorbeeld.com":
       "Dak Twee BV legt EPDM op platte daken. BTW BE 0123.456.749. " * 3}
_fd = [{"naam": "Dak Een", "url": "https://een.voorbeeld.com/", "ondernemingsnummer": "0123.456.749", "bewijs": "niets"},
       {"naam": "Dak Twee BV", "url": "https://twee.voorbeeld.com/", "ondernemingsnummer": "0123.456.749",
        "bewijs": "Dak Twee BV legt EPDM op platte daken."}]
_kd = Z.keur(_fd, _db, {"lat": 50.88, "lon": 4.70}, 25, lambda p: {"lat": 50.9, "lon": 4.7},
             {"0123.456.749": {"actief": True, "plaats": "3000 Leuven"}})
check("controle 17: bij een dubbel blijft de best bewezen kandidaat", [f["naam"] for f in _kd["goed"]] == ["Dak Twee BV"]
      and not _kd["na_te_kijken"])
_dbp = []
_tr0 = E._dropbox_zoek("dak", "/x", rpc=lambda m, b: _dbp.append(m) or {"matches": [], "has_more": True, "cursor": "c"},
                       deadline=time.monotonic() - 1)
check("controle 18: na de deadline start geen verzoek naar Dropbox meer", _dbp == [] and _tr0.volledig is False)


def _dbx_traag(m, b):
    raise TimeoutError("timed out")


check("controle 18: een verzoek dat niet voor de deadline antwoordt, maakt de lijst onvolledig",
      E._dropbox_zoek("dak", "/x", rpc=_dbx_traag, deadline=time.monotonic() + 30).volledig is False)
_woorden = []
E.in_mappen(S.HA, "dakwerken epdm", zoek=lambda q, p: _woorden.append(q) or [], deadline=time.monotonic() - 1)
check("controle 18: geen nieuw zoekwoord na de deadline", _woorden == [])

print("\nEigen mappen: hele woorden, alleen offertemappen (gemeten 01-11-2026)")
for _naam in ("Fastening Plates", "Platane 6Platane_6.rfa", "04 Percelen Informatie Platform", "Offerte koper dak Platteau.pdf",
              "Plategrond 1st verdiep.pdf"):
    check(f"'plat' past niet op {_naam}", not E.woord_in("plat", _naam))
for _naam in ("06 Plat dak - EPDM", "Platdak offerte.pdf", "platte daken.pdf"):
    check(f"'plat' past op {_naam}", E.woord_in("plat", _naam))
_tr = [{"soort": "file", "naam": "platdakvensters.eml",
        "pad": "/Work All/01. H-A WORK/x/2999 S 1/00. Communicatie/11. Mails/platdakvensters.eml"},
       {"soort": "folder", "naam": "06 Plat dak - EPDM",
        "pad": "/Work All/01. H-A WORK/x/2999 S 1/3. Quotes & Invoices/Offerte/06 Plat dak - EPDM"},
       {"soort": "file", "naam": "Offerte koper dak Platteau.pdf",
        "pad": "/Work All/01. H-A WORK/x/2998 S 2/3. Quotes & Invoices/Offerte/6. Roof/Offerte koper dak Platteau.pdf"}]
check("alleen de offertemap met het hele woord blijft", [e["naam"] for e in E.in_mappen(S.HA, "plat dak EPDM",
      zoek=lambda q, p: _tr)] == ["06 Plat dak - EPDM"])

print("\nOffertevergelijker: fiches tellen niet mee, OCR pas na het ja van Mehdi")
check("een technische fiche zonder totaal is geen offerte", F.lees(["Technische fiche EPDM-membraan" + VUL2])["soort"]
      == "geen offerte")
check("een document zonder totaal en zonder offertewoord is geen offerte", F.lees(["Plaatsingsadvies. De membranen worden volledig gekleefd op een droge, "
                                                  "stofvrije ondergrond, met overlappen van tien centimeter."])["soort"]
      == "geen offerte")
check("een offerte die naar een technische fiche verwijst, blijft een offerte", F.lees([
    "Offerte dakwerken. Technische fiche in bijlage." + VUL2 + "\nTotaal excl. btw 10.000,00\n"])["soort"] == "offerte")
check("fiche volgens de naam", F.fiche_naam("Technische fiche EPDM.pdf") and F.fiche_naam("DoP membraan.pdf")
      and not F.fiche_naam("Offerte technische installaties.pdf") and not F.fiche_naam("2026-10 Dak Een.pdf"))
_vs = V.vergelijkingsverslag({"firma": S.HB}, "lot 06", [("A", {}, "a"), ("B", {}, "b")],
                             F.vergelijk([{"letter": "A", "lees": F.lees(["Offerte" + VUL2 + "\nTotaal excl. btw 10.000,00\n"])},
                                          {"letter": "B", "lees": F.lees(["Technische fiche EPDM" + VUL2])}], date(2026, 11, 1)),
                             None, {}, "2026-11-01", True, 2)
_gl = [{"letter": "A", "lees": {"soort": "offerte"}}, {"letter": "B", "lees": {"soort": "geen offerte"}},
       {"letter": "C", "lees": {"soort": "scan"}}]
check("controle 25: een offerte met een fiche en een scan gaat niet naar Claude", F.voor_claude(
    _gl, {"A": "offerte", "B": "fiche", "C": "stukje scan"}) == {})
_gl[0]["lees"]["excl"] = 100.0
check("controle 25: twee echte offertes wel, zonder de fiche", F.voor_claude(
    _gl + [{"letter": "D", "lees": {"soort": "offerte", "excl": 200.0}}], {"A": "a", "B": "fiche", "D": "d"})
    == {"A": "a", "D": "d"})
_ov = open(_hier / "offertevergelijker.py", encoding="utf-8").read()
check("controle 25: de vergelijker roept Claude alleen via voor_claude aan", "F.voor_claude(gelezen, teksten)" in _ov
      and "len(teksten) >= 2" not in _ov)
check("controle live 01-11: met een offerte zegt het verslag dat er niets per post te vergelijken is",
      "minder dan twee leesbare offertes" in _vs and "niet betrouwbaar" not in _vs)
check("het verslag telt fiches apart, ook de overgeslagen", "1 offertes gelezen" in _vs and "3 documenten die geen offerte zijn" in _vs,
      _vs.splitlines()[0])
_echt_paginas = F.paginas
F.paginas = lambda data: {b"scan": ["  "], b"ocr": ["Offerte" + VUL2 + "\nTotaal excl. btw 2.000,00\n"]}.get(data)
_ocr = []
gl, _ = F.lees_bestanden([("A", {"pad": "/a"}, "a")], lambda p: b"scan", ocr_fn=lambda d: _ocr.append(d) or b"ocr")
check("zonder ja van Mehdi geen OCR: de scan blijft OCR nodig", gl[0]["lees"]["soort"] == "scan" and not _ocr)
F.OCR_AAN = True
gl, _ = F.lees_bestanden([("A", {"pad": "/a"}, "a")], lambda p: b"scan", ocr_fn=lambda d: b"ocr")
check("met OCR wordt een scan gelezen, met de vraag de bedragen na te kijken", gl[0]["lees"]["soort"] == "offerte"
      and gl[0]["lees"]["excl"] == 2000.0 and F.OCR_REDEN in gl[0]["lees"]["redenen"])
gl, _ = F.lees_bestanden([("A", {"pad": "/a"}, "a")], lambda p: b"scan", ocr_fn=lambda d: None)
check("mislukte OCR: de scan blijft OCR nodig", gl[0]["lees"]["soort"] == "scan")
gl, _ = F.lees_bestanden([("A", {"pad": "/a"}, "a")], lambda p: b"scan", deadline=100, klok=lambda: 50,
                         ocr_fn=lambda d: b"ocr")
check("geen OCR als de tijd van de ronde er niet meer voor volstaat", gl[0]["lees"]["soort"] == "scan")
F.OCR_AAN = False
F.paginas = _echt_paginas
_pv = []
_aan, F.OFFERTE_NAAR_AI = F.OFFERTE_NAAR_AI, True
F.posten_uit_model({"A": "tekst A", "B": "tekst B"}, vraag=lambda s, g, **kw: _pv.append((s, g, kw)) or {"tekst": "```json\n{}\n```"})
F.OFFERTE_NAAR_AI = _aan
check("posten via het abonnement, zonder gereedschap", _pv and _pv[0][2]["tools"] == () and "INSCHRIJVER A" in _pv[0][1])
_wv = open(_hier / "werkwijze" / "offertevergelijker.md", encoding="utf-8").read()
import bord  # noqa: E402
for _naam, _tekst in (("De Offertevergelijker", _wv), ("De Aannemerszoeker", _ww)):
    _nooit, _mehdi = bord.grenzen(_tekst)
    check(f"{_naam}: het bord leest de grenzen uit de werkwijze (live gemeten 01-11-2026: een ingesprongen vervolgregel "
          "gaf geen grenzen)", bool(_nooit) and bool(_mehdi), f"{len(_nooit)} {len(_mehdi)}")
check("werkwijzen zeggen: abonnement, nooit een API-sleutel", "nooit met een" in _wv and "API-sleutel" in _wv
      and "Of een scan met OCR gelezen mag worden." in _wv and "API-sleutel" in _ww and "Versie 1.2" in _ww)

print("\nProefbank 02-11-2026 (overleg 28): wat de proeven op echte lotmappen vonden")
_p = F.lees(pdf("Offerte 670010001", "Artikel 7,00 PCE 293,38", "Totaal  2.069,35€", "2.503,92€", "Deze offerte wordt een bestelling na betaling."))
check("totaal zonder label, inclusief op de volgende regel: bewezen door de btw-som", _p["excl"] == 2069.35
      and _p["incl"] == 2503.92 and _p["btw_tarief"] == 21 and any("btw-som" in r for r in _p["redenen"]), _p)
_p = F.lees(pdf("Meerwerk MW 1", "Totaal € 5 458,69", "6% (6) Totalen", "Incl B.T.W. 5 786,21 € 5 786,21",
                "Eindbedrag (geldig tot 27/10/2026) € 5 786,21"))
check("'Incl B.T.W.' en eindbedrag: exclusief en inclusief gelezen", _p["excl"] == 5458.69 and _p["incl"] == 5786.21, _p)
_p = F.lees(pdf("Offerte ramen", "729,40 E Totaal", "Totaal gewicht: 127,4 Kg", "Voorwaarden volgen."))
check("een kaal totaal zonder bewijs wordt niet gebruikt, wel gemeld", _p["excl"] is None and _p["incl"] is None
      and any("niet gebruikt" in r for r in _p["redenen"]), _p)
_p = F.lees(pdf("Offerte ramen", "Bij afwijkend adres bent u verplicht extra kosten te betalen. Deze kosten betreffen 50 "
                "euro per levering.", "Bij totale bedragen boven de 10.000,00 euro vragen wij een voorschot."))
check("'te betalen' in een zin en 'totale bedragen' zijn geen totaal (gemeten: 50 euro inclusief btw)",
      _p["excl"] is None and _p["incl"] is None, _p)
_p = F.lees(pdf("TOTAAL BEDRAG EXCL.BTW.  69800,00Euro", "BTW  6%         4188,00Euro", "TOTAAL BEDRAG INCL.BTW.  73988,00Euro"))
check("hoofdletters met plakkende Euro blijven gelezen", _p["excl"] == 69800.0 and _p["incl"] == 73988.0, _p)
check("geen totaal: niet naar Claude, ook met twee offertes", F.voor_claude(
    [{"letter": "A", "lees": {"soort": "offerte", "excl": None}}, {"letter": "B", "lees": {"soort": "offerte", "excl": None}}],
    {"A": "a", "B": "b"}) == {})
_boom = {"/L": [{".tag": "file", "name": "los.pdf", "path_display": "/L/los.pdf"},
                {".tag": "folder", "name": "Dak Een BV", "path_display": "/L/Dak Een BV"},
                {".tag": "folder", "name": "archief", "path_display": "/L/archief"},
                {".tag": "folder", "name": "Oude versies", "path_display": "/L/Oude versies"}],
         "/L/Dak Een BV": [{".tag": "file", "name": "offerte.pdf", "path_display": "/L/Dak Een BV/offerte.pdf"},
                           {".tag": "folder", "name": "ouder", "path_display": "/L/Dak Een BV/ouder"}],
         "/L/Dak Een BV/ouder": [{".tag": "file", "name": "v1.pdf", "path_display": "/L/Dak Een BV/ouder/v1.pdf"}],
         "/L/archief": [{".tag": "file", "name": "oud.pdf", "path_display": "/L/archief/oud.pdf"}],
         "/L/Oude versies": [{".tag": "file", "name": "v0.pdf", "path_display": "/L/Oude versies/v0.pdf"}]}
_b = MP.offertebestanden("/L", lambda p, recursief=False: _boom.get(p, []))
check("X6: een submap per inschrijver telt mee, een map diep; archief en oude versies niet",
      [x["naam"] for x in _b] == ["Dak Een BV/offerte.pdf", "los.pdf"], [x["naam"] for x in _b])
_l = [(chr(65 + i), {"pad": f"/{i}"}, str(i)) for i in range(10)]
_gl, _ = F.lees_bestanden(_l, lambda p: b"x", maximum=8)
check("X7: boven de acht staat elk bestand erbij als niet gelezen, niets valt stil weg",
      len(_gl) == 10 and all("niet gelezen" in g["lees"]["redenen"][0] for g in _gl[8:]))
import offertevergelijker as OV  # noqa: E402
_namen = [OV.lotnaam(f"/P/Offerte/{n}", S.HA) for n in ("01 Harmonie Bouw - ruwbouw", "02 Dak Een - dakwerken")]
_lk = V.lotkeuze({"firma": S.HA, "project": "2999"}, _namen)
check("X8: de keuzelijst toont geen naam van de andere firma, de grendel laat ze door", not S.kruis(_lk, S.HA)
      and "lot 01" in _lk and "02 Dak Een - dakwerken" in _lk, _lk)
check("X8: de vergelijker geeft de keuzelijst alleen veilige lotnamen", "V.lotkeuze(v, [lotnaam(l, firma) for l in lots])"
      in open(_hier / "offertevergelijker.py", encoding="utf-8").read())
check("A4: een gemeente zonder postcode is een onvolledige vraag, geen persoonsgegeven",
      Q.naar_buiten_fouten(Q.ontleed("firma: HB; werk: tegelwerk; gemeente: Atlantis")) == [Q.GEMEENTE_FOUT]
      and "gemeente zonder postcode" in open(_hier / "aannemerszoeker.py", encoding="utf-8").read())
_hits = [{"soort": "folder", "naam": "2026-06-16 Dakwerken (ontvangen van U82)", "pad": "/H/P/17. U82_X/0/1/2026-06-16 D"},
         {"soort": "folder", "naam": "17. U82_Jachtlaan 2", "pad": "/H/P/17. U82_X"},
         {"soort": "folder", "naam": "18. U820_Ander", "pad": "/H/P/18. U820_Ander"}]
check("HB: de projectmap is de map die met de code begint, niet een fotomap met de code erin",
      MP.projectmap(S.HB, "U82", zoek=lambda q, p: _hits) == "/H/P/17. U82_X"
      and MP.projectmap(S.HB, "U82", zoek=lambda q, p: _hits[:1]) is None)
_p = F.lees(pdf("Offerte OFR 1", "Totaal zonder B.T.W. :                          4.750,20",
                "Totaal :                               EUR      5.747,74", "Betaling binnen 30 dagen."))
check("'zonder B.T.W.' met punten is exclusief; het kale totaal erna is inclusief door de btw-som",
      _p["excl"] == 4750.2 and _p["incl"] == 5747.74 and _p["btw_tarief"] == 21, _p)
_p = F.lees(pdf("Offerte ramen", "729,40 E 0% Totaal elementen", "729,40 E Totaal", "Voorwaarden volgen."))
check("een totaal bij 0 procent btw is exclusief, met de vraag het na te kijken", _p["excl"] == 729.4
      and any("0 procent" in r for r in _p["redenen"]), _p)
_vb = [{"naam": "Klantofferte 670010001 (Dak Een).pdf", "gewijzigd": "2026-02-19T10:00:00Z"},
       {"naam": "Klantofferte 670010001 - tweede versie.pdf", "gewijzigd": "2026-02-20T10:00:00Z"},
       {"naam": "Dak Twee/2999_Dak Twee_2026-08-25_offerte 2026013.pdf", "gewijzigd": "2026-08-25T10:00:00Z"},
       {"naam": "Dak Twee/2999_Dak Twee_2026-10-20_offerte 2026013 en overeenkomst 2026006.pdf", "gewijzigd": "2026-10-20T10:00:00Z"},
       {"naam": "Dak Twee/2999_Dak Twee_2026-09-28_meerwerk MW 2026022.pdf", "gewijzigd": "2026-09-28T10:00:00Z"},
       {"naam": "2999 20260904 RAMENPLAN.pdf", "gewijzigd": "2026-09-04T10:00:00Z"},
       {"naam": "2999 20260904 RAMENPLAN v2.pdf", "gewijzigd": "2026-09-05T10:00:00Z"}]
_tel, _oud = F.versies(_vb)
check("versies van dezelfde offerte: alleen de nieuwste telt, een meerwerk en een datum zijn geen offertenummer",
      [b["naam"] for b in _tel] == ["2999 20260904 RAMENPLAN v2.pdf", "2999 20260904 RAMENPLAN.pdf",
                                    "Dak Twee/2999_Dak Twee_2026-09-28_meerwerk MW 2026022.pdf",
                                    "Dak Twee/2999_Dak Twee_2026-10-20_offerte 2026013 en overeenkomst 2026006.pdf",
                                    "Klantofferte 670010001 - tweede versie.pdf"]
      and len(_oud) == 2, [b["naam"] for b in _tel])
_vs2 = V.vergelijkingsverslag({"firma": S.HB}, "40. POST", [("A", {}, "a.pdf")], F.vergelijk(
    [{"letter": "A", "lees": F.lees(["Offerte" + VUL2 + "\nTotaal excl. btw 10.000,00\n"])}], date(2026, 11, 1)),
    None, {}, "2026-11-01", True, 0, [("A", "a-v1.pdf")])
check("het verslag noemt een oudere versie, zonder letter", "1 oudere versies van dezelfde offerte tellen niet mee" in _vs2
      and "- Oudere versie van inschrijver A, telt niet mee: a-v1.pdf" in _vs2, _vs2.splitlines()[0])
_tel, _oud = F.versies([{"naam": "Offerte 670010001 (Dak Een).pdf", "gewijzigd": "2026-03-01T10:00:00Z"},
                        {"naam": "Offerte 670010001 - (tweede versie).pdf", "gewijzigd": "2026-02-20T10:00:00Z"}])
check("de tweede versie volgens de naam telt, ook als Dropbox de eerste later bewaarde",
      [b["naam"] for b in _tel] == ["Offerte 670010001 - (tweede versie).pdf"])
_pp = F.per_post([{"onderwerp": "metselwerk", "posten": {"B": ["1"]}}, {"onderwerp": "ramen", "posten": {"B": ["1"]}}],
                 {"B": {"1": 69800.0}})
check("een post van een inschrijver telt in een onderdeel, niet in twee", _pp[0]["cellen"]["B"] == 69800.0
      and _pp[1]["cellen"]["B"] is None, _pp)
check("een datum in maart is geen verlegde btw, artikel 20 wel", not F.verlegd("Open zondag 29 maart 2026.")
      and F.verlegd("Btw te voldoen door de medecontractant, art. 20 van het KB nr. 1."))
_p = F.lees(pdf("Klantofferte 670010002", "Totaal  2.069,35€", "BTW", "Totaal (Incl. BTW)", "434,57", "2.503,92€", "€",
                "Deze offerte wordt een bestelling na betaling van een voorschot."))
check("totalen onder elkaar in een kolom: de btw-som vindt exclusief en inclusief", _p["excl"] == 2069.35
      and _p["incl"] == 2503.92 and _p["btw_tarief"] == 21, _p)
check("hydrofoberen is een vakwoord; een los 'en' op het einde valt weg",
      W.filter_tekst("gevelreiniging en hydrofoberen")[0] == "gevelreiniging en hydrofoberen"
      and W.filter_tekst("gevelreiniging en Peeters")[0] == "gevelreiniging")
_f = {"naam": "Dak Een", "url": "https://dak-een.voorbeeld.com", "telefoon": "0537.405.239", "ondernemingsnummer": None,
      "bewijs": "Dakwerken, platte daken, EPDM, renovatie", "adres": "Dorpstraat 1", "postcode": "3020", "gemeente": "Herent"}
_r = Z.keur([_f], GELEZEN, PUNTEN["3000 Leuven"], 25, lambda p: PUNTEN.get(p))
_alle = _r["goed"] + _r["na_te_kijken"] + _r["buiten"]
check("een ondernemingsnummer in het telefoonveld wordt het nummer, nooit een telefoonnummer",
      _alle and _alle[0]["ondernemingsnummer"] == "0537.405.239" and _alle[0]["telefoon"] is None, _r)
_zk = lambda q, p: [{"soort": "file", "naam": "06-17 Vergadering dakwerken.mp3", "pad": E.BASIS[S.HA] + "/2999 X/Quotes/06-17 Vergadering dakwerken.mp3"},
                    {"soort": "file", "naam": "offerte dakwerken.pdf", "pad": E.BASIS[S.HA] + "/2998 Y/Quotes/offerte dakwerken.pdf"}]
check("een opname of foto in een offertemap is geen eerdere offerte", [t["naam"] for t in E.in_mappen(S.HA, "dakwerken", zoek=_zk)]
      == ["offerte dakwerken.pdf"])
for _t, _e, _i in (("Totaal excl. BTW 10.000,00", 10000.0, None), ("Totaal incl. BTW: 12.100,00", None, 12100.0),
                   ("TOTAAL EXCL. BTW 9.000,00 EUR", 9000.0, None), ("Totaal excl. Btw 9.000,00 EUR", 9000.0, None)):
    _p = F.lees(pdf("Offerte", _t))
    check(f"'{_t}': de punt na de afkorting is geen zinseinde", _p["excl"] == _e and _p["incl"] == _i, _p)
_tel, _oud = F.versies([{"naam": "Dak Een/Offerte 2026050.pdf", "gewijzigd": "2026-05-01"},
                        {"naam": "Dak Twee/Offerte 2026050 dakwerken.pdf", "gewijzigd": "2026-05-02"},
                        {"naam": "Kosztorys OF_26_1098155.pdf", "gewijzigd": "2026-09-01"},
                        {"naam": "Nieuwe offerte/Kosztorys OF_26_1098155 2.pdf", "gewijzigd": "2026-09-20"}])
check("twee inschrijvers met toevallig hetzelfde nummer blijven apart; een kopie in een andere map is een versie",
      len(_tel) == 3 and [o[0]["naam"] for o in _oud] == ["Kosztorys OF_26_1098155.pdf"], [b["naam"] for b in _tel])
from bouw import proefbank as PB  # noqa: E402
_p = F.lees(pdf("Offerte 12", "Totaal 1.000,00 EUR", "Optie 1.210,00 EUR", "Voorwaarden volgen."))
check("Codex 29: een optie op de regel na een kaal totaal is geen inclusief", _p["incl"] is None and _p["excl"] is None, _p)
_p = F.lees(pdf("Offerte 12b", "Totaal 1.000,00 EUR", "X 1.210,00 EUR", "Voorwaarden volgen."))
check("Codex 30: ook een woord van een letter naast het bedrag maakt er geen totaal van", _p["incl"] is None, _p)
_p = F.lees(pdf("Offerte 13", "Transport incl. BTW 50,00 EUR", "Voorwaarden volgen."))
check("Codex 29: 'Transport incl. BTW 50,00' is geen totaal", _p["incl"] is None, _p)
_p = F.lees(pdf("Offerte 14", "De vorige som 210,00 EUR is af. Totaal 1.000,00 EUR", "Incl. BTW 1.210,00 EUR", "Einde."))
check("Codex 29: na een kort woord als 'af' eindigt de zin wel", _p["excl"] == 1000.0 and _p["incl"] == 1210.0, _p)
_tel, _oud = F.versies([{"naam": "Dak Een/Offerte 2026001.pdf", "gewijzigd": "2026-05-01"},
                        {"naam": "Dak Twee/Offerte 2026001.pdf", "gewijzigd": "2026-05-02"}])
check("Codex 29: dezelfde naam in twee inschrijversmappen is geen versie", len(_tel) == 2 and not _oud)
import urllib.request as _ur  # noqa: E402
_echt_open = _ur.urlopen
_gezien = []
_ur.urlopen = lambda *a, **k: _gezien.append(a) or "doorgelaten"
PB.afschermen()
try:
    _ur.urlopen(PB.bord.PLATFORM + "/api/klaarzet", b"{}")
    check("Codex 29: een gewone URL met data naar het bord wordt geweigerd", False)
except PermissionError:
    check("Codex 29: een gewone URL met data naar het bord wordt geweigerd", not _gezien)
finally:
    _ur.urlopen = _echt_open

_o = PB.Opname(lambda *a, **k: {"gelezen": True})
check("proefbank: schrijven naar het bord wordt opgevangen, lezen gaat door",
      _o.call("/api/klaarzet", {"items": [{"titel": "t"}]}) == {"nieuw": 1, "bestaand": 0} and len(_o.schrijf) == 1
      and _o.call("/api/agent/x/werkwijze") == {"gelezen": True} and len(_o.schrijf) == 1)
_t = PB.Teller(lambda *a, **k: (_ for _ in ()).throw(AssertionError("echt Claude")))
_t.vast = {"firmas": [{"naam": "Dak Een", "url": "https://dak-een.voorbeeld.com"}]}
_a = _t.vraag("s", "g", tools=("WebSearch",))
check("proefbank: een vast modelantwoord vraagt Claude niet", "Dak Een" in _a["tekst"] and _t.vragen[0]["vast"])
_pypdf = sys.modules.get("pypdf")
sys.modules["pypdf"] = None
try:
    F.paginas(b"%PDF")
    check("zonder pypdf een fout, nooit 'PDF niet te openen' (proefbank met de verkeerde Python)", False)
except ImportError:
    check("zonder pypdf een fout, nooit 'PDF niet te openen' (proefbank met de verkeerde Python)", True)
finally:
    if _pypdf is not None:
        sys.modules["pypdf"] = _pypdf
    else:
        sys.modules.pop("pypdf", None)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
