"""Grendels van De Prijsonderzoeker: wat nooit in een prijsverslag mag, en hoe het totaal en de rangorde ontstaan.

Driehoeksoverleg 30-10-2026 (ontwerp) en de controle van Codex daarna (X1 tot X9). Alleen verzonnen aanbiedingen en
voorbeeld.com-links; geen echte bestellingen of personen.

Draaien: python3 mijnagents-runner/tests/test_aankoop_prijs.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "koppelingen"))
from aankoop import aanbod as A  # noqa: E402
from aankoop import koersen as K  # noqa: E402
from aankoop import onderzoek as O  # noqa: E402
from aankoop import privacy as P  # noqa: E402
from aankoop import verslag as V  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


VANDAAG = date(2026, 10, 30)
KOERSEN = {"USD": 1.10, "GBP": 0.85, "SRD": 40.0}
VULLING = " Productomschrijving, specificaties, levering en retour volgens de voorwaarden van de winkel." * 4


def aanbod(**over):
    basis = {"titel": "Vloerwasser X1", "url": "https://winkel.voorbeeld.com/x1", "winkel": "Winkel", "land": "BE",
             "soort": "nieuw", "prijs": 500, "munt": "EUR", "btw_inbegrepen": True, "verzending": 0,
             "verzending_btw_inbegrepen": True, "gezien_op": "2026-10-30", "beschikbaar": True}
    basis.update(over)
    return basis


def pagina(*stukken):
    return " ".join(stukken) + VULLING


print("Wat nooit in het verslag mag")
check("een aanbod zonder link", "geen werkende link" in A.keur(aanbod(url=""), VANDAAG))
check("een link zonder http", "geen werkende link" in A.keur(aanbod(url="winkel.voorbeeld.com/x1"), VANDAAG))
check("een aanbod zonder prijs", "geen prijs" in A.keur(aanbod(prijs=None), VANDAAG))
check("een prijs van nul", "geen prijs" in A.keur(aanbod(prijs=0), VANDAAG))
check("zonder datum gezien", "geen datum gezien" in A.keur(aanbod(gezien_op=None), VANDAAG))
check("een prijs van vorige week is te oud", "prijs te oud" in A.keur(aanbod(gezien_op="2026-10-20"), VANDAAG))
check("een datum in de toekomst", "datum gezien ligt in de toekomst" in A.keur(aanbod(gezien_op="2026-11-02"), VANDAAG))
check("uitverkocht", "niet meer beschikbaar" in A.keur(aanbod(beschikbaar=False), VANDAAG))
check("een onbekende soort", "soort onbekend" in A.keur(aanbod(soort="koopje"), VANDAAG))
check("een volledig aanbod mag", A.keur(aanbod(), VANDAAG) == [])

print("De prijs staat op de gelezen pagina (Codex X1)")
check("een lege pagina telt niet als gelezen", "pagina zonder leesbare tekst" in A.keur(aanbod(), VANDAAG, ""))
check("een pagina met alleen een titel telt niet", "pagina zonder leesbare tekst" in A.keur(aanbod(), VANDAAG, "Vloerwasser X1 500"))
def met_bewijs(citaat, **over):
    return aanbod(bewijs={"prijs": citaat}, **over)


check("een prijs die niet op de pagina staat", "prijs niet bewezen op de gelezen pagina" in
      A.keur(met_bewijs("voor 450,00 euro", prijs=450), VANDAAG, pagina("Vloerwasser X1 voor 500,00 euro")))
check("zonder citaat geen bewezen prijs", "prijs niet bewezen op de gelezen pagina" in
      A.keur(aanbod(prijs=500), VANDAAG, pagina("Vloerwasser X1 voor 500,00 euro")))
check("Belgische schrijfwijze op de pagina", A.keur(met_bewijs("Prijs: 1.299,00 €", prijs=1299), VANDAAG, pagina("Prijs: 1.299,00 €")) == [])
check("Engelse schrijfwijze op de pagina", A.keur(met_bewijs("Price $1,299.00", prijs=1299, munt="USD", land="US"), VANDAAG,
                                                  pagina("Price $1,299.00")) == [])
check("schrijfwijze met streepje", A.keur(met_bewijs("X1 nu 1299,-", prijs=1299), VANDAAG, pagina("X1 nu 1299,-")) == [])
check("met centen", A.keur(met_bewijs("Prijs € 499,95", prijs=499.95), VANDAAG, pagina("Prijs € 499,95")) == [])
check("smalle vaste spatie in 1 299,00 (Codex X11)", A.keur(met_bewijs("Prijs 1 299,00 €", prijs=1299), VANDAAG,
                                                           pagina("Prijs 1\u202f299,00 €")) == [])
TEGENPROEF = pagina("Vloerwasser X1 Prijs: 999,00 euro. Verzendkosten: 499,00 euro.")
check("een verzendkost als productprijs wordt geweigerd (Codex X1, ronde 2)", "prijs niet bewezen op de gelezen pagina" in
      A.keur(met_bewijs("Verzendkosten: 499,00 euro", prijs=499), VANDAAG, TEGENPROEF))
check("ook als het citaat alleen het bedrag noemt", "prijs niet bewezen op de gelezen pagina" in
      A.keur(met_bewijs("499,00 euro", prijs=499), VANDAAG, TEGENPROEF))
check("de echte productprijs wel", A.keur(met_bewijs("Prijs: 999,00 euro", prijs=999), VANDAAG, TEGENPROEF) == [])
OUD = pagina("MOVA V70 Ultra Adviesprijs ~~1.399,00 €~~ Nu 1.099,00 €. Gratis verzending 1.099,00 € in je mandje.")
check("een doorgestreepte of adviesprijs is niet de prijs van vandaag (Codex X1, ronde 3)", "prijs niet bewezen op de gelezen pagina"
      in A.keur(met_bewijs("1.399,00 €", prijs=1399), VANDAAG, OUD))
R4 = pagina("Vloerwasser X1 100,00 euro (oude prijs). Vandaag 90,00 euro. Verzendkosten nu 25,00 euro.")
check("een kostwoord voor 'nu' telt nog (Codex X14, ronde 4)", "prijs niet bewezen op de gelezen pagina" in
      A.keur(met_bewijs("nu 25,00 euro", prijs=25), VANDAAG, R4))
check("een oude prijs met de vermelding erna (Codex X1, ronde 4)", "prijs niet bewezen op de gelezen pagina" in
      A.keur(met_bewijs("Vloerwasser X1 100,00 euro", prijs=100), VANDAAG, R4))
check("de prijs van vandaag wel", A.keur(met_bewijs("Vandaag 90,00 euro", prijs=90), VANDAAG, R4) == [])
R5 = pagina("X1 100,00 euro. (oude prijs) Vandaag 90,00 euro.")
check("een oude prijs met de vermelding na de punt (Codex X1, ronde 5)", "prijs niet bewezen op de gelezen pagina" in
      A.keur(met_bewijs("X1 100,00 euro", prijs=100), VANDAAG, R5))
check("een volgende prijs met een eigen label blijft geldig", A.keur(met_bewijs("Nu 1.099,00 €", prijs=1099), VANDAAG,
      pagina("Nu 1.099,00 €. Adviesprijs 1.399,00 €")) == [])
check("de huidige prijs wel, ook met gratis verzending ervoor", A.keur(met_bewijs("Nu 1.099,00 €", prijs=1099), VANDAAG, OUD) == []
      and A.keur(met_bewijs("Gratis verzending 1.099,00 €", prijs=1099), VANDAAG, OUD) == [])
check("499 is niet 1499", not A.bedrag_op_pagina(499, "1499 euro"))
check("499 is niet 499,99", not A.bedrag_op_pagina(499, "499,99 euro"))
check("procent op de pagina", A.procent_op_pagina(18, "opgeld 18 % excl. btw") and not A.procent_op_pagina(8, "opgeld 18%"))

print("Bedragen en omrekening")
check("Belgische schrijfwijze", A._getal("1.299,00") == 1299.0)
check("Engelse schrijfwijze", A._getal("1,299.00") == 1299.0)
check("decimale komma", A._getal("49,95") == 49.95)
check("een boolean is geen bedrag", A._getal(True) is None)
check("dollar naar euro met de ECB-koers", round(A.in_euro(110, "USD", KOERSEN), 2) == 100.0)
check("zonder koers geen bedrag", A.in_euro(100, "CNY", KOERSEN) is None)

print("Totaalprijs, btw en invoer (Codex X9)")
check("binnen de EU met btw: prijs plus verzending", A.totaal(aanbod(prijs=500, verzending=25), KOERSEN)[:2] == (525.0, []))
check("zonder verzending is het totaal onvolledig", A.totaal(aanbod(verzending=None), KOERSEN)[:2] == (None, ["verzending"]))
check("onbekend of de btw erin zit: onvolledig", A.totaal(aanbod(btw_inbegrepen=None), KOERSEN)[:2] == (None, ["btw"]))
t = A.totaal(aanbod(prijs=1000, verzending=0, btw_inbegrepen=False), KOERSEN)
check("een prijs zonder btw krijgt 21 procent erbij", t[0] == 1210.0 and "21 procent btw bijgeteld op de prijs" in t[2], str(t))
t = A.totaal(aanbod(prijs=100, verzending=10, btw_inbegrepen=False, verzending_btw_inbegrepen=True), KOERSEN)
check("btw per kostenpost: 100 zonder btw plus 10 verzending met btw is 131 (Codex X9, ronde 2)", t[:2] == (131.0, []), str(t))
t = A.totaal(aanbod(prijs=100, verzending=10, btw_inbegrepen=False, verzending_btw_inbegrepen=None), KOERSEN)
check("prijs zonder btw en verzending zonder opgave: onvolledig, niet erven (Codex X9, ronde 3)", t[:2] == (None, ["btw"]), str(t))
t = A.totaal(aanbod(prijs=100, verzending=10, verzending_btw_inbegrepen=None), KOERSEN)
check("bij een consumentenprijs met btw in de EU erft de verzending de btw (overleg 33, X5)", t[:2] == (110.0, []), str(t))
t = A.totaal(aanbod(prijs=100, verzending=10, verzending_btw_inbegrepen=None, bewijs={"verzending": "verzending 10 euro"}),
             KOERSEN, pagina("100 euro, verzending 10 euro. Alle bedragen excl. btw."))
check("zegt de winkel dat bedragen zonder btw zijn, dan erft de verzending niet (overleg 33, X5)",
      t[:2] == (None, ["btw"]), str(t))
t = A.totaal(aanbod(prijs=100, verzending=0, verzending_btw_inbegrepen=None), KOERSEN)
check("gratis verzending heeft geen btw-status nodig", t[:2] == (100.0, []), str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, veilingkosten=0), KOERSEN)
check("een veilingprijs zonder opgeld is geen totaalprijs", t[:2] == (None, ["opgeld"]), str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18), KOERSEN)
check("onbekende vaste veilingkosten tellen niet als nul (overleg K3)", t[:2] == (None, ["veilingkosten"]), str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=10), KOERSEN)
check("veiling met opgeld en kosten", t[:2] == (1240.0, []), str(t))
tekst = pagina("Hamerprijs 1.000 euro; verzending 50 euro; dossierkosten 10 euro")
BEWIJS = {"verzending": "verzending 50 euro", "veilingkosten": "dossierkosten 10 euro", "opgeld": "opgeld 18%"}
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=10, bewijs=BEWIJS), KOERSEN, tekst)
check("opgeld dat op geen gelezen pagina staat, maakt het totaal onvolledig", t[:2] == (None, ["opgeld niet bewezen"]), str(t))
t = A.totaal(aanbod(soort="veiling", prijs=1000, verzending=50, opgeld_pct=18, veilingkosten=10, bewijs=BEWIJS), KOERSEN,
             tekst + " Voorwaarden: opgeld 18% op de hamerprijs.")
check("met de veilingvoorwaarden gelezen is het totaal volledig", t[:2] == (1240.0, []), str(t))
t = A.totaal(aanbod(prijs=500, verzending=25, bewijs={"verzending": "verzending 25 euro"}), KOERSEN, pagina("500 euro"))
check("een verzendprijs die nergens staat, is niet bewezen", t[:2] == (None, ["verzending niet bewezen"]), str(t))
t = A.totaal(aanbod(prijs=500, verzending=0, bewijs={"verzending": "Gratis verzending in Belgie"}), KOERSEN,
             pagina("500 euro. Gratis verzending in Belgie"))
check("gratis verzending met citaat", t[:2] == (500.0, []), str(t))
t = A.totaal(aanbod(prijs=500, verzending=0), KOERSEN, pagina("500 euro"))
check("verzending 0 zonder citaat is niet bewezen", t[:2] == (None, ["verzending niet bewezen"]), str(t))
t = A.totaal(aanbod(prijs=100, verzending=0, bewijs={"verzending": "geen gratis verzending"}), KOERSEN,
             pagina("100 euro, geen gratis verzending, verzending 25 euro"))
check("geen gratis verzending is geen gratis verzending (Codex X12, ronde 4)", t[:2] == (None, ["verzending niet bewezen"]), str(t))
check("gratis verzending zonder ontkenning", A.gratis_verzending("Gratis verzending vanaf 50 euro")
      and not A.gratis_verzending("Helaas geen gratis verzending") and not A.gratis_verzending("no free shipping"))
t = A.totaal(aanbod(prijs=100, verzending=0, bewijs={"verzending": "Gratis retourneren binnen 30 dagen"}), KOERSEN,
             pagina("100 euro. Gratis retourneren binnen 30 dagen. Verzending 25 euro."))
check("gratis retourneren bewijst geen gratis verzending (Codex X12, ronde 3)", t[:2] == (None, ["verzending niet bewezen"]), str(t))
t = A.totaal(aanbod(land="US", munt="USD", prijs=550, verzending=55), KOERSEN)
check("buiten de EU zonder douane is onvolledig", t[:2] == (None, ["invoer"]), str(t))
t = A.totaal(aanbod(land="US", munt="USD", prijs=550, verzending=55, douane=22), KOERSEN)
check("buiten de EU: douane en 21 procent btw door de code", t[0] == 689.7 and "invoer" in t[2][0], str(t))
check("zonder land geldt het als onvolledig", A.totaal(aanbod(land=""), KOERSEN)[:2] == (None, ["land"]))

print("Eisen uit de vraag, niet alleen van het model (Codex X2)")
check("Suriname wordt 60 Hz", A.eisen_uit_vraag("vloerwasser MOVA V70 voor Suriname") == ["netfrequentie 60 Hz"])
check("spanning en frequentie letterlijk", A.eisen_uit_vraag("toestel op 220 V en 60 Hz")
      == ["netfrequentie 60 Hz", "netspanning 220 V"])
check("een lidar zonder bestemming heeft geen vaste eisen", A.eisen_uit_vraag("Livox Mid-360 lidar, levering in Belgie") == [])
eisen = A.eisen_uit_vraag("vloerwasser voor Suriname")
r = A.verwerk([aanbod(prijs=300), aanbod(url="https://b.voorbeeld.com/1", prijs=450,
                                          compatibiliteit={"netfrequentie 60 Hz": "nee"})], VANDAAG, KOERSEN, eisen)
check("model vergat de eis: het goedkope toestel is onbekend en nooit de beste", r["beste"] is None
      and r["goed"][0]["compatibel"] == "onbekend")
check("een toestel op 50 Hz staat apart als niet compatibel", len(r["niet_compatibel"]) == 1)
SPEC = pagina("Specificaties: 220-240 V, 50 Hz. Versie VS: 120 V, 60 Hz.")
check("ja zonder citaat is onbekend (Codex X2, ronde 2)",
      A.compatibel(aanbod(compatibiliteit={"netfrequentie 60 Hz": "ja"}), ["netfrequentie 60 Hz"], SPEC) == "onbekend")
check("ja met een citaat dat 50 Hz zegt, is onbekend", A.compatibel(aanbod(compatibiliteit={"netfrequentie 60 Hz": {
      "oordeel": "ja", "citaat": "Specificaties: 220-240 V, 50 Hz"}}), ["netfrequentie 60 Hz"], SPEC) == "onbekend")
check("een 60 Hz-citaat van een andere variant op dezelfde pagina is onbekend (Codex X2, ronde 3)",
      A.compatibel(aanbod(compatibiliteit={"netfrequentie 60 Hz": {"oordeel": "ja", "citaat": "Versie VS: 120 V, 60 Hz"}}),
                   ["netfrequentie 60 Hz"], SPEC, SPEC) == "onbekend")
ALLEEN60 = pagina("Specificaties: 127 V, 60 Hz, stekker type A.")
check("ja met een citaat van de eigen pagina dat alleen 60 Hz noemt", A.compatibel(aanbod(compatibiliteit={
      "netfrequentie 60 Hz": {"oordeel": "ja", "citaat": "Specificaties: 127 V, 60 Hz"}}), ["netfrequentie 60 Hz"],
      ALLEEN60, ALLEEN60) == "ja")
check("het citaat moet van de eigen aanbodpagina komen", A.compatibel(aanbod(compatibiliteit={
      "netfrequentie 60 Hz": {"oordeel": "ja", "citaat": "Specificaties: 127 V, 60 Hz"}}), ["netfrequentie 60 Hz"],
      ALLEEN60, SPEC) == "onbekend")
BEIDE = pagina("Ingang 100-240 V, 50/60 Hz, wereldwijd bruikbaar.")
check("een toestel voor 50/60 Hz is ja", A.compatibel(aanbod(compatibiliteit={"netfrequentie 60 Hz": {
      "oordeel": "ja", "citaat": "Ingang 100-240 V, 50/60 Hz"}}), ["netfrequentie 60 Hz"], BEIDE, BEIDE) == "ja")
check("ja met een verzonnen citaat is onbekend", A.compatibel(aanbod(compatibiliteit={"netfrequentie 60 Hz": {
      "oordeel": "ja", "citaat": "Werkt op 60 Hz overal"}}), ["netfrequentie 60 Hz"], SPEC) == "onbekend")

print("Spanning en frequentie uit de handleiding van hetzelfde model (overleg 9, X1, K1, X6)")
HZV = ["netfrequentie 60 Hz", "netspanning 220 V"]
WINKEL = "https://winkel.voorbeeld.com/x1"
HANDL = "https://fabrikant.voorbeeld.com/x1-handleiding"
WPAG = pagina("Vloerwasser X1 Complete, typenummer VX-200EU. Nu 500,00 euro.")
HPAG = pagina("Technische gegevens VX-200EU. Basisstation: ingang 220-240 V~ 50/60 Hz, 80 W.")


def met_hand(code="VX-200EU", citaat="ingang 220-240 V~ 50/60 Hz", bewijs_url=HANDL, **over):
    return aanbod(modelcode=code, compatibiliteit={e: {"oordeel": "ja", "citaat": citaat, "bewijs_url": bewijs_url}
                                                   for e in HZV}, **over)


def hand_oordeel(a, paginas):
    return A.compatibel(a, HZV, "\n".join(paginas.values()), paginas.get(WINKEL, ""), paginas)


check("een handleiding met dezelfde modelcode bewijst 220 V en 60 Hz (bereik 220-240 V en 50/60 Hz)",
      hand_oordeel(met_hand(), {WINKEL: WPAG, HANDL: HPAG}) == "ja")
DOC = "https://data.winkel.voorbeeld.com/manual/v70-ultra-complete.pdf"
WPAG_DOC = pagina(f"Documenten: {DOC} https://winkel.voorbeeld.com/bebat.pdf\nMOVA V70 ULTRA COMPLETE WHITE. Nu 1.399,00 euro.")
HPAG_DOC = pagina("MOVA V70 Ultra Complete Robotic Vacuum Cleaner. Base Station / Model RCVE0707 / Rated Input 220-240 V / "
                  "50-60 Hz / Rated Output 20 V")
V70 = dict(titel="MOVA V70 ULTRA COMPLETE WHITE", code="MOVA-RC-V70ULC-WHT")
check("een handleiding die de aanbodpagina zelf linkt en hetzelfde model noemt, bewijst 220 V en 60 Hz (overleg 33, M2)",
      hand_oordeel(met_hand(citaat="Rated Input 220-240 V / 50-60 Hz", bewijs_url=DOC, **V70), {WINKEL: WPAG_DOC, DOC: HPAG_DOC})
      == "ja")
check("dezelfde handleiding zonder link op de aanbodpagina telt niet (overleg 33, X2)",
      hand_oordeel(met_hand(citaat="Rated Input 220-240 V / 50-60 Hz", bewijs_url=DOC, **V70),
                   {WINKEL: WPAG_DOC.replace(DOC, "https://andere.voorbeeld.com/x.pdf"), DOC: HPAG_DOC}) == "onbekend")
check("een gelinkt document van een ander model telt niet (overleg 33, X2)",
      hand_oordeel(met_hand(citaat="Rated Input 220-240 V / 50-60 Hz", bewijs_url=DOC, **V70),
                   {WINKEL: WPAG_DOC, DOC: HPAG_DOC.replace("V70", "P70")}) == "onbekend")
check("een gelinkt document over een optioneel laadstation telt niet (overleg 33, X2)",
      hand_oordeel(met_hand(citaat="Rated Input 220-240 V / 50-60 Hz", bewijs_url=DOC, **V70),
                   {WINKEL: WPAG_DOC, DOC: HPAG_DOC.replace("Base Station", "Optioneel laadstation")}) == "onbekend")
print("Overleg 35: eigen eisen, modelcode uit de vraag, dezelfde EAN")
EAN = "6978794734941"
check("een EAN telt met label en geldig controlecijfer, alleen met 13 cijfers (overleg 35, G3)",
      A.gtins(f"Barcodenummer: {EAN}") == {EAN} and A.gtins(f"EAN-code\n{EAN}\nFabrikantcode") == {EAN}
      and A.gtins(f'"gtin13": "{EAN}"') == {EAN} and A.gtins("EAN 6978794734942") == set()
      and A.gtins(f"artikel {EAN}") == set() and A.gtins("UPC barcode 036000291452") == set())
check("de modelcode uit de vraag wordt een vaste eis", A.eisen_uit_vraag(
      "MOVA V70 Ultra Complete (modelcode MOVA-RC-V70ULC-WHT), naar Suriname") ==
      ["netfrequentie 60 Hz", "modelcode MOVA-RC-V70ULC-WHT"] and A.eisen_uit_vraag("een robotstofzuiger") == [])
check("ook een modelcode zonder het woord modelcode wordt een vaste eis (Codex controle 36, punt 2)",
      A.eisen_uit_vraag("MOVA V70 Ultra Complete MOVA-RC-V70ULC-WHT, levering tegen half november") ==
      ["modelcode MOVA-RC-V70ULC-WHT"] and A.eisen_uit_vraag("een e-mail over de WD-40 voor 220 V") == ["netspanning 220 V"]
      and A.eisen_uit_vraag("toestel AB-12C") == ["modelcode AB-12C"],
      str(A.eisen_uit_vraag("een e-mail over de WD-40 voor 220 V")))
check("een eis over de koper hoort niet in eisen (overleg 35, B)", "niet de koper" in O.VORM
      and "dezelfde EAN-code" in O.VORM)
check("zonder leesbare handleiding zoekt het model op de EAN-code (overleg 38, E)",
      "zoek dan op de EAN-code" in " ".join(O.VORM.split()))
RC, VB = "https://robo.voorbeeld.com/v70", "https://keten.voorbeeld.be/v70"
RCPAG = pagina(f"Mova Robot Vacuum V70 Ultra Complete\nBarcodenummer: {EAN}\nNu 949,00 euro. "
               "Verzending naar België: 12,50 euro.")
VBPAG = pagina(f"Documenten: {DOC}\nMOVA V70 ULTRA COMPLETE WHITE. Nu 1.399,00 euro. Gratis levering aan huis. "
               f"EAN-code\n{EAN}\nFabrikantcode\nMOVA-RC-V70ULC-WHT")
EISEN35 = ["netfrequentie 60 Hz", "netspanning 220 V", "modelcode MOVA-RC-V70ULC-WHT",
           "levering in Belgie tegen half november"]
HAND = {"oordeel": "ja", "citaat": "Rated Input 220-240 V / 50-60 Hz", "bewijs_url": DOC}


def rc(**over):
    return aanbod(**{"titel": "Mova Robot Vacuum V70 Ultra Complete", "url": RC, "winkel": "RoboCleaners", "prijs": 949,
                     "verzending": 12.5, "bewijs": {"prijs": "Nu 949,00 euro",
                                                    "verzending": "Verzending naar België: 12,50 euro"},
                     "compatibiliteit": {"netfrequentie 60 Hz": HAND, "netspanning 220 V": HAND}, **over})


VBA = aanbod(titel="MOVA V70 ULTRA COMPLETE WHITE", url=VB, winkel="Vanden Borre", prijs=1399, verzending=0,
             modelcode="MOVA-RC-V70ULC-WHT", bewijs={"prijs": "Nu 1.399,00 euro", "verzending": "Gratis levering aan huis"},
             compatibiliteit={"netfrequentie 60 Hz": HAND, "netspanning 220 V": HAND})
P35 = {RC: RCPAG, VB: VBPAG, DOC: HPAG_DOC}
r = A.verwerk([VBA, rc()], VANDAAG, KOERSEN, EISEN35, paginas=P35)
check("zelfde EAN: de goedkoopste winkel gebruikt de handleiding van de andere en wordt aanbevolen (overleg 35, M3, K5)",
      r["beste"] and r["beste"]["url"] == RC and r["reserve"]["url"] == VB
      and r["beste"]["per_eis"] == ["ja", "ja", "ja", "onbekend"]
      and r["beste"]["niet_bevestigd"] == ["levering in Belgie tegen half november"], str(r["beste"] or r["goed"]))
check("het verslag noemt de herkomst via de EAN en wat niet bevestigd is (overleg 35, A en K3)",
      r["beste"]["via_ean"] == {e: VB for e in EISEN35[:3]} and "via dezelfde EAN" in V.maak("v", {}, r, "2026-10-30",
      "2026-10-30") and "niet bevestigd: levering in Belgie tegen half november" in V.maak("v", {}, r, "2026-10-30",
      "2026-10-30"), str(r["beste"].get("via_ean")))
LEV = {"oordeel": "ja", "citaat": "Gratis levering aan huis"}
r = A.verwerk([dict(VBA, compatibiliteit=dict(VBA["compatibiliteit"], **{EISEN35[3]: LEV})), rc()], VANDAAG, KOERSEN,
              EISEN35, paginas=P35)
check("een bevestigde eigen eis gaat niet voor een lager totaal (Codex controle 36, punt 1)",
      r["beste"]["url"] == RC and r["reserve"]["url"] == VB and r["reserve"]["per_eis"][3] == "ja")
r = A.verwerk([VBA, rc(titel="Mova Robot Vacuum P70 Ultra")], VANDAAG, KOERSEN, EISEN35, paginas=P35)
rij = next(x for x in r["goed"] if x["url"] == RC)
check("zelfde EAN maar een ander model in de titel: geen bewijs, nooit aanbevolen (overleg 35, K3, K5)",
      r["beste"]["url"] == VB and rij["per_eis"][:3] == ["onbekend"] * 3 and not rij["kandidaat"], str(rij["per_eis"]))
r = A.verwerk([rc(modelcode="MOVA-RC-V70ULC-BLK")], VANDAAG, KOERSEN, EISEN35, paginas=P35)
check("zelfde EAN maar een andere modelcode bij het aanbod: geen bewijs (overleg 35, K3)", r["beste"] is None
      and r["goed"][0]["per_eis"][:3] == ["onbekend"] * 3)
r = A.verwerk([rc()], VANDAAG, KOERSEN, EISEN35, paginas={RC: RCPAG.replace("Barcodenummer", f"EAN 4006381333931 Barcodenummer"),
                                                           VB: VBPAG, DOC: HPAG_DOC})
check("twee EAN-codes op de aanbodpagina koppelen niets", r["beste"] is None)
ZWART = "https://goedkoop.voorbeeld.com/v70-zwart"
r = A.verwerk([aanbod(titel="MOVA V70 Ultra Complete Black", url=ZWART, prijs=899, modelcode="MOVA-RC-V70ULC-BLK",
                      bewijs={"prijs": "Nu 899,00 euro", "verzending": "Gratis verzending."},
                      compatibiliteit={e: {"oordeel": "ja", "citaat": "Ingang 220-240 V, 50/60 Hz"} for e in EISEN35[:2]})],
              VANDAAG, KOERSEN, EISEN35, paginas={ZWART: pagina(
                  "MOVA V70 Ultra Complete Black, typenummer MOVA-RC-V70ULC-BLK. Nu 899,00 euro. Gratis verzending. "
                  "Ingang 220-240 V, 50/60 Hz.")})
check("een andere modelcode dan de vraag wordt nooit aanbevolen, ook goedkoper en met netwaarden (overleg 35, X1, X5)",
      r["beste"] is None and r["goed"][0]["per_eis"] == ["ja", "ja", "onbekend", "onbekend"]
      and "modelcode MOVA-RC-V70ULC-WHT" in r["goed"][0]["niet_bevestigd"], str(r["goed"][0]["per_eis"]))
r = A.verwerk([rc(compatibiliteit=dict(rc()["compatibiliteit"], **{EISEN35[3]: "nee"}))], VANDAAG, KOERSEN, EISEN35,
              paginas=P35)
check("een eigen eis van het model met nee sluit uit (overleg 35, A)", r["beste"] is None and len(r["niet_compatibel"]) == 1)

check("een handleiding van een andere modelcode telt niet", hand_oordeel(met_hand(), {
      WINKEL: WPAG, HANDL: HPAG.replace("VX-200EU", "VX-200US")}) == "onbekend")
check("een langere modelcode op de handleiding is een andere variant (VX-200EUX)", hand_oordeel(met_hand(), {
      WINKEL: WPAG, HANDL: HPAG.replace("VX-200EU", "VX-200EUX")}) == "onbekend")
check("een regioaanhangsel na een liggend streepje is een andere variant (VX-200EU_US, Codex controle 10)",
      hand_oordeel(met_hand(), {WINKEL: WPAG, HANDL: HPAG.replace("VX-200EU", "VX-200EU_US")}) == "onbekend"
      and not A.modelcode_op("VX-200EU", "typenummer VX-200EU+US") and A.modelcode_op("VX-200EU", "typenummer vx 200eu, wit"))
check("een robot op 50/60 Hz naast een basisstation op 230 V 50 Hz bewijst niets (Codex controle 10)", hand_oordeel(
      met_hand(citaat="Robot: 220-240 V, 50/60 Hz"), {WINKEL: WPAG, HANDL: pagina(
          "Technische gegevens VX-200EU. Robot: 220-240 V, 50/60 Hz. Basisstation: 230 V, 50 Hz.")}) == "onbekend")
check("een winkelpagina met basisstation op 50 Hz wint van een handleiding met 50/60 Hz voor de robot (Codex controle 11)",
      hand_oordeel(met_hand(citaat="Robot: 220-240 V, 50/60 Hz"), {
          WINKEL: WPAG + " Basisstation: 220-240 V, 50 Hz.",
          HANDL: pagina("Technische gegevens VX-200EU. Robot: 220-240 V, 50/60 Hz.")}) == "onbekend")
DERDE = "https://andere.voorbeeld.com/vx-200eu-review"
check("een derde gelezen pagina met dezelfde modelcode en basisstation 50 Hz spreekt het tegen (Codex controle 12)",
      hand_oordeel(met_hand(), {WINKEL: WPAG, HANDL: HPAG, DERDE: pagina("Test van de VX-200EU. Basisstation: 50 Hz.")})
      == "onbekend")
check("een derde pagina van een ander model spreekt niets tegen", hand_oordeel(met_hand(), {
      WINKEL: WPAG, HANDL: HPAG, DERDE: pagina("Test van de VX-300. Basisstation: 50 Hz.")}) == "ja")
check("ook op de eigen pagina spreekt een losse 50 Hz een 50/60 Hz-citaat tegen", A.compatibel(aanbod(compatibiliteit={
      "netfrequentie 60 Hz": {"oordeel": "ja", "citaat": "Ingang 100-240 V, 50/60 Hz"}}), ["netfrequentie 60 Hz"],
      BEIDE + " Lader: 50 Hz.", BEIDE + " Lader: 50 Hz.") == "onbekend")
check("een losse andere netspanning op de pagina spreekt een bereik tegen", A.tegenstrijdig("v", "220", "ingang 220-240 V, stekker 230 V")
      and not A.tegenstrijdig("v", "220", "ingang 220-240 V, accu 14,4 V, 100-240 V lader"))
check("zonder modelcode op de aanbodpagina telt de handleiding niet", hand_oordeel(met_hand(), {
      WINKEL: pagina("Vloerwasser X1 Complete. Nu 500,00 euro."), HANDL: HPAG}) == "onbekend")
check("een te korte modelcode bewijst niets", hand_oordeel(met_hand(code="X1"), {
      WINKEL: WPAG + " X1", HANDL: HPAG + " X1"}) == "onbekend")
check("een handleiding met ook 120 V voor een andere streek telt niet (K1)", hand_oordeel(met_hand(), {
      WINKEL: WPAG, HANDL: HPAG + " Versie Noord-Amerika: 120 V 60 Hz."}) == "onbekend")
check("een bewijspagina die niet gelezen is, telt niet", hand_oordeel(met_hand(), {WINKEL: WPAG}) == "onbekend")
check("een citaat dat niet op de bewijspagina staat, telt niet", hand_oordeel(met_hand(citaat="ingang 110-240 V 50/60 Hz"), {
      WINKEL: WPAG, HANDL: HPAG}) == "onbekend")
check("een past vlak na accessoire op de handleiding telt niet", hand_oordeel(met_hand(citaat="lader 220-240 V~ 50/60 Hz"), {
      WINKEL: WPAG, HANDL: HPAG + " Accessoire: externe lader 220-240 V~ 50/60 Hz."}) == "onbekend")
check("alleen 230 V bewijst geen 220 V", hand_oordeel(met_hand(citaat="ingang 230 V~ 50/60 Hz"), {
      WINKEL: WPAG, HANDL: HPAG + " Basisstation ingang 230 V~ 50/60 Hz."}) == "onbekend")
check("50 Hz alleen op de handleiding is geen 60 Hz", hand_oordeel(met_hand(citaat="ingang 220-240 V~ 50 Hz"), {
      WINKEL: WPAG, HANDL: pagina("Technische gegevens VX-200EU. Basisstation: ingang 220-240 V~ 50 Hz.")}) == "onbekend")
EIGEN60 = pagina("Vloerwasser X1, typenummer VX-200EU. Nu 500,00 euro. Ingang 220-240 V, 50/60 Hz.")
check("een citaat van de eigen pagina werkt nog zoals voorheen", A.compatibel(aanbod(compatibiliteit={
      e: {"oordeel": "ja", "citaat": "Ingang 220-240 V, 50/60 Hz"} for e in HZV}), HZV, EIGEN60, EIGEN60, {WINKEL: EIGEN60}) == "ja")
r = A.verwerk([met_hand(bewijs={"prijs": "Nu 500,00 euro"}, verzending=None)], VANDAAG, KOERSEN, HZV,
              paginas={WINKEL: WPAG, HANDL: HPAG})
check("het verslag toont het handleidingbewijs met de link naar de handleiding",
      r["goed"][0]["compatibel"] == "ja" and r["goed"][0]["context"]["netfrequentie 60 Hz"][1] == HANDL, str(r["goed"][0].get("context")))

print("Compatibiliteit en rangorde")
eisen = ["netfrequentie 60 Hz", "stekker type A/B"]
check("een eis die nee is maakt het niet compatibel", A.compatibel(aanbod(compatibiliteit={e: "nee" for e in eisen}), eisen) == "nee")
check("alle eisen ja", A.compatibel(aanbod(compatibiliteit={e: "ja" for e in eisen}), eisen) == "ja")
check("een eis zonder oordeel is onbekend", A.compatibel(aanbod(compatibiliteit={eisen[0]: "ja"}), eisen) == "onbekend")
check("zonder eisen altijd compatibel", A.compatibel(aanbod(), []) == "ja")
r = A.verwerk([
    aanbod(prijs=300, compatibiliteit={e: "nee" for e in eisen}),
    aanbod(url="https://b.voorbeeld.com/1", prijs=450, compatibiliteit={e: "ja" for e in eisen}),
    aanbod(url="https://c.voorbeeld.com/1", prijs=400, verzending=None, compatibiliteit={e: "ja" for e in eisen}),
    aanbod(url="https://d.voorbeeld.com/1", prijs=420, compatibiliteit={eisen[0]: "ja"}),
    aanbod(url="", prijs=100),
    aanbod(url="https://b.voorbeeld.com/1/", prijs=450, compatibiliteit={e: "ja" for e in eisen}),
], VANDAAG, KOERSEN, eisen)
check("het goedkoopste maar niet compatibele aanbod staat apart", [a["prijs"] for a in r["niet_compatibel"]] == [300])
check("een eigen eis van het model zonder oordeel houdt het goedkoopste niet tegen, maar staat erbij (overleg 35, A; "
      "Codex controle 36)", r["beste"]["url"] == "https://d.voorbeeld.com/1"
      and r["beste"]["niet_bevestigd"] == ["stekker type A/B"] and r["reserve"]["url"] == "https://b.voorbeeld.com/1")
check("onvolledig totaal komt achteraan", r["goed"][-1]["url"] == "https://c.voorbeeld.com/1")
check("zonder link afgewezen, met reden", any("geen werkende link" in a["redenen"] for a in r["afgewezen"]))
check("dezelfde link twee keer telt een keer", any(a["redenen"] == ["dubbel"] for a in r["afgewezen"]))
r = A.verwerk([aanbod(prijs=500), aanbod(url="https://b.voorbeeld.com/2", prijs=520),
               aanbod(url="https://c.voorbeeld.com/3", prijs=480)], VANDAAG, KOERSEN)
check("een beste keuze en een reserve (overleg X2)", r["beste"]["prijs"] == 480 and r["reserve"]["prijs"] == 500)
r = A.verwerk([aanbod(soort="veiling", prijs=100, veilingkosten=0)], VANDAAG, KOERSEN)
check("een veiling zonder opgeld wordt nooit het beste aanbod", r["beste"] is None and len(r["goed"]) == 1)
paginas = {"https://winkel.voorbeeld.com/x1": pagina("X1 nu 500,00 euro. Netstekker type C."),
           "https://andere.voorbeeld.com/y": pagina("Ander toestel Y. Stekker type A/B. Gratis verzending."),
           "https://winkel.voorbeeld.com/verzending": pagina("Verzending: 7,95 euro voor elke bestelling.")}
X1 = aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Gratis verzending."}, compatibiliteit={
    "stekker type A/B": {"oordeel": "ja", "citaat": "Stekker type A/B."}})
r = A.verwerk([X1], VANDAAG, KOERSEN, ["stekker type A/B"], paginas=paginas)
check("een stekkerbewijs van een ander product telt niet (Codex X2, ronde 4)", r["beste"] is None
      and r["goed"][0]["compatibel"] == "onbekend")
check("gratis verzending van een andere winkel bewijst niets (Codex X12, ronde 4)",
      "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"][0]["ontbreekt"]))
paginas_y = dict(paginas, **{"https://winkel.voorbeeld.com/y": pagina("Product Y. Gratis verzending voor Y.")})
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Gratis verzending voor Y."})], VANDAAG, KOERSEN,
              paginas=paginas_y)
check("gratis verzending van een ander product in dezelfde winkel bewijst niets (Codex X12, ronde 5)",
      "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"][0]["ontbreekt"]))
ACC = {"https://winkel.voorbeeld.com/x1": pagina("X1 nu 500,00 euro. Gratis verzending. Netstekker type C. "
                                                  "Accessoire laadstation: Stekker type A/B.")}
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Gratis verzending."}, compatibiliteit={
    "stekker type A/B": {"oordeel": "ja", "citaat": "Stekker type A/B."}})], VANDAAG, KOERSEN, ["stekker type A/B"], paginas=ACC)
check("een past vlak na het woord accessoire telt niet (Codex X2, ronde 6)",
      r["goed"][0]["compatibel"] == "onbekend" and r["goed"][0]["niet_bevestigd"] == ["stekker type A/B"])
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzending: 7,95 euro"}, verzending=7.95)],
              VANDAAG, KOERSEN, paginas=paginas)
check("een verzendkost van een andere pagina zonder Belgie of alle bestellingen in het citaat telt niet (overleg 29, X2)",
      r["beste"] is None and "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"]))
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzending: 7,95 euro voor elke bestelling"},
                      verzending=7.95)], VANDAAG, KOERSEN, paginas=paginas)
check("de verzendpagina van dezelfde winkel telt voor alle bestellingen, met die pagina als bron (Codex X16; overleg 29, X2)",
      r["beste"] is not None and r["beste"]["totaal_eur"] == 507.95
      and r["beste"]["context"]["verzending"][1] == "https://winkel.voorbeeld.com/verzending", str(r["goed"]))
LANDEN = dict(paginas, **{"https://winkel.voorbeeld.com/verzending": pagina(
    "Verzendkosten Nederland: 6,95 euro. Verzendkosten België: 9,95 euro. Verzendkosten BE grote toestellen: 19,95 euro.")})
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzendkosten Nederland: 6,95 euro"},
                      verzending=6.95)], VANDAAG, KOERSEN, paginas=LANDEN)
check("het tarief voor Nederland van de verzendpagina telt niet (overleg 29, X2)",
      r["beste"] is None and "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"]))
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzendkosten België: 9,95 euro"}, verzending=9.95),
               aanbod(url="https://winkel.voorbeeld.com/x1", bewijs={"prijs": "X1 nu 500,00 euro",
                      "verzending": "Verzendkosten BE grote toestellen: 19,95 euro"}, verzending=19.95)],
              VANDAAG, KOERSEN, paginas=LANDEN)
check("het tarief voor Belgie telt, ook met de landcode BE (overleg 29, X2)",
      r["beste"]["totaal_eur"] == 509.95 and A.voor_belgie("Verzendkosten BE grote toestellen: 19,95 euro")
      and not A.voor_belgie("Wij verzenden to be sure") and not A.voor_belgie("Verzending Nederland 6,95"), str(r["goed"]))
TABEL = dict(paginas, **{"https://winkel.voorbeeld.com/verzending": pagina(
    "U kan de verzendkosten als volgt simuleren:\n| Land\n| Verzendkost\n| België/Luxemburg/Nederland\n| 12,50 €\n"
    "| Frankrijk, Duitsland\n| 15,00 €")})
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "België/Luxemburg/Nederland | 12,50 €"},
                      verzending=12.5, verzending_btw_inbegrepen=None)], VANDAAG, KOERSEN, paginas=TABEL)
check("een tarief uit de verzendtabel telt met het verzendwoord in de kop (overleg 33, M3)",
      r["beste"] is not None and r["beste"]["totaal_eur"] == 512.5, str([(g["totaal_eur"], g["ontbreekt"]) for g in r["goed"]]))
RETOURTABEL = dict(paginas, **{"https://winkel.voorbeeld.com/verzending": pagina(
    "Verzendkosten: zie de kassa. Retour naar België: 9,95 €")})
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "naar België: 9,95 €"}, verzending=9.95)],
              VANDAAG, KOERSEN, paginas=RETOURTABEL)
check("een retourbedrag na het verzendwoord telt niet als verzending (overleg 33, X3)",
      r["beste"] is None and "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"]))
check("gratis levering met een datum ertussen telt (overleg 33, M4)",
      A.gratis_verzending("Levering aan huis : vanaf di. 03 november Gratis"))
check("geen gratis levering bij retour, drempelbedrag, afhaling of ontkenning ertussen (overleg 33, X4)",
      not A.gratis_verzending("Levering aan huis. Retourneren is gratis")
      and not A.gratis_verzending("Levering vanaf 50 euro gratis")
      and not A.gratis_verzending("Levering aan huis 9,95 Afhaling in de winkel gratis")
      and not A.gratis_verzending("Levering is helaas niet altijd gratis"))
PRODUCT_Y = dict(paginas, **{"https://winkel.voorbeeld.com/y": pagina(
    'Product Y. {"offers": {"price": 99, "priceCurrency": "EUR"}} Gratis verzending naar België voor Y.')})
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Gratis verzending naar België voor Y."})],
              VANDAAG, KOERSEN, paginas=PRODUCT_Y)
check("verzending van de productpagina van een ander product telt niet, ook met Belgie (overleg 29, X2)",
      r["beste"] is None and "verzending niet bewezen" in r["goed"][0]["ontbreekt"]
      and "verzending" not in r["goed"][0]["context"], str(r["goed"]))
MODEL = dict(paginas, **{"https://winkel.voorbeeld.com/levering": pagina(
    "Levering: gratis verzending naar België voor de P70. Verzending naar België voor de X1: 4,95 euro.")})
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "gratis verzending naar België voor de P70"},
                      verzending=0)], VANDAAG, KOERSEN, paginas=MODEL)
check("een tarief voor een ander model op de verzendpagina telt niet (Codex-controle 30, X2)",
      r["beste"] is None and "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"]))
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzending naar België voor de X1: 4,95 euro"},
                      verzending=4.95)], VANDAAG, KOERSEN, paginas=MODEL)
TWEE = dict(paginas, **{"https://winkel.voorbeeld.com/levering": pagina("Verzending naar België: P70 gratis; X1 39,95 euro.")})
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzending naar België: P70 gratis; X1 39,95 euro"},
                      verzending=0)], VANDAAG, KOERSEN, paginas=TWEE)
check("een citaat met een tarief voor een ander model naast dit model telt niet (Codex-controle 31, X2)",
      r["beste"] is None and "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"]))
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzending naar België voor de X1: 4,95 euro"},
                      verzending=4.95)], VANDAAG, KOERSEN, paginas=MODEL)
check("een tarief voor dit model op de verzendpagina telt (Codex-controle 30, X2)",
      r["beste"] is not None and r["beste"]["totaal_eur"] == 504.95 and A.voor_dit_product("België: 9,95 euro", {})
      and not A.voor_dit_product("voor de MOVA-RC-P70ULC", {"titel": "MOVA V70 Ultra", "modelcode": "MOVA-RC-V70ULC-WHT"}),
      str(r["goed"]))
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 500,00 euro", "verzending": "Verzending: 7,95 euro voor elke bestelling"},
                      verzending=7.95)], VANDAAG, KOERSEN,
              paginas={"https://winkel.voorbeeld.com/x1": paginas["https://winkel.voorbeeld.com/x1"],
                       "https://andere.voorbeeld.com/verzending": pagina("Verzending: 7,95 euro voor elke bestelling.")})
check("een verzendkost van een andere winkel telt niet (overleg 29, X2)",
      r["beste"] is None and "verzending niet bewezen" in r["goed"][0]["ontbreekt"], str(r["goed"]))
EIGEN = {"https://winkel.voorbeeld.com/x1": pagina("X1 nu 100,00 euro. Verzendkosten: 5,00 euro."),
         "https://winkel.voorbeeld.com/z": pagina("Z nu 130,00 euro. Gratis verzending.")}
r = A.verwerk([aanbod(bewijs={"prijs": "X1 nu 100,00 euro", "verzending": "Verzendkosten: 5,00 euro"}, prijs=100, verzending=5),
               aanbod(url="https://winkel.voorbeeld.com/z", bewijs={"prijs": "Z nu 130,00 euro", "verzending": "Gratis verzending."},
                      prijs=130, verzending=0)], VANDAAG, KOERSEN, paginas=EIGEN)
check("met de verzending op de eigen pagina wint het goedkoopste totaal", r["beste"]["totaal_eur"] == 105.0
      and r["reserve"]["totaal_eur"] == 130.0, str([(g["totaal_eur"], g["ontbreekt"]) for g in r["goed"]]))
VEIL = {"https://veiling.voorbeeld.com/kavel/1": pagina("Kavel 1 hamerprijs 1.000 euro. Verzending: 50 euro."),
        "https://veiling.voorbeeld.com/voorwaarden": pagina("Op elke kavel geldt een opgeld van 18% en dossierkosten 10 euro.")}
r = A.verwerk([aanbod(url="https://veiling.voorbeeld.com/kavel/1", soort="veiling", prijs=1000, verzending=50, opgeld_pct=18,
                      veilingkosten=10, bewijs={"prijs": "Kavel 1 hamerprijs 1.000 euro", "verzending": "Verzending: 50 euro",
                                                "opgeld": "opgeld van 18%", "veilingkosten": "dossierkosten 10 euro"})],
              VANDAAG, KOERSEN, paginas=VEIL)
check("opgeld en kosten uit de voorwaarden van hetzelfde veilinghuis tellen", r["beste"] is not None
      and r["beste"]["totaal_eur"] == 1240.0, str([(g["totaal_eur"], g["ontbreekt"]) for g in r["goed"]]))
fout_type = A.verwerk([aanbod(compatibiliteit="past wel")], VANDAAG, KOERSEN)
check("een compatibiliteit als tekst laat het verslag niet crashen (Codex X15, ronde 4)",
      V.maak("v", {}, fout_type, None, "2026-10-30").startswith("**Aanbevolen:**"))
paginas = {"https://winkel.voorbeeld.com/x1": pagina("X1 nu 500,00 euro. Gratis verzending")}
BEW = {"prijs": "X1 nu 500,00 euro", "verzending": "Gratis verzending"}
r = A.verwerk([aanbod(bewijs=BEW), aanbod(url="https://andere.voorbeeld.com/x1", bewijs=BEW)], VANDAAG, KOERSEN, paginas=paginas)
check("met de gelezen pagina's: alleen het aanbod met bewezen prijs gaat door", len(r["goed"]) == 1
      and r["afgewezen"][0]["redenen"] == ["pagina zonder leesbare tekst"], str(r["afgewezen"]))

print("Alleen gelezen pagina's (onderzoek)")
check("www, http en fragment tellen niet", O.schoon_url("http://WWW.Winkel.voorbeeld.com/x1/#foto")
      == "https://winkel.voorbeeld.com/x1")
check("de query telt wel (product-id)", O.schoon_url("https://w.voorbeeld.com/p?id=1") != O.schoon_url("https://w.voorbeeld.com/p?id=2"))
PAGINA_X1 = pagina("X1 499,00 euro, gratis verzending. Netspanning 127 V, 60 Hz. ![X1](https://cdn.voorbeeld.com/x1.jpg)")
gelezen = {"https://winkel.voorbeeld.com/x1": PAGINA_X1}
goed, weg = O.alleen_gelezen([aanbod(), aanbod(url="https://zoek.voorbeeld.com/a"), aanbod(url="https://verzonnen.voorbeeld.com/z")], gelezen)
check("een link uit een zoekresultaat alleen gaat er niet in", len(goed) == 1 and len(weg) == 2
      and all(w["redenen"] == ["pagina niet gelezen in deze ronde"] for w in weg))
goed, _ = O.alleen_gelezen([aanbod(foto="https://cdn.voorbeeld.com/x1.jpg")], gelezen)
check("een foto die op de gelezen pagina staat, blijft", goed[0]["foto"] == "https://cdn.voorbeeld.com/x1.jpg")
goed, _ = O.alleen_gelezen([aanbod(foto="https://cdn.voorbeeld.com/verzonnen.jpg")], gelezen)
check("een foto die niet op de pagina staat, wordt nooit getoond (overleg X5)", goed[0]["foto"] is None)
check("JSON uit een ```json-blok", O.json_uit('Uitleg\n```json\n{"eisen": []}\n```') == {"eisen": []})
check("het laatste blok telt", O.json_uit('```json\n{"a": 1}\n```\n```json\n{"a": 2}\n```') == {"a": 2})
check("geen JSON geeft None", O.json_uit("ik vond niets") is None)

print("Via het Claude-abonnement, nooit via de API (overleg 14)")
FIXTURE = [json.loads(r) for r in open(Path(__file__).parent / "fixtures" / "claude_stream_proef.jsonl", encoding="utf-8")]
INIT = next(d for d in FIXTURE if d.get("subtype") == "init")
EINDE = FIXTURE[-1]
st = O._Stand()
redenen = [O.verwerk_regel(st, d) for d in FIXTURE]
check("de gemeten stream van claude -p wordt gelezen (overleg 14, X3)", redenen[-1] == "einde"
      and [r for r in redenen[:-1] if r] == [] and st.bron == "none" and st.extra_verbruik == "allowed"
      and st.gezocht == 1 and st.zoekvragen == 2 and st.einde is EINDE
      and len(st.zoek) >= 5, str((st.bron, st.gezocht, st.zoek))[:300])
check("de zoekresultaten dragen de titel uit de lijst Links", st.zoek.get(
      "https://robocleaners.com/nl/tags/mova-v70-ultra-complete-x-transparent-black") == "mova v70 ultra complete x transparent black",
      str(st.zoek)[:200])

NEP = r'''import json, os, subprocess, sys, time
spec = json.load(open("nep.json" if os.path.exists("nep.json") else os.path.join(os.path.dirname(sys.argv[0]), "nep.json")))
args = sys.argv[1:]
if args[:2] == ["auth", "status"]:
    # Geen modelaanvraag: alleen het account (Codex controle 16); centrale instellingen komen in de configuratiemap.
    if spec.get("centraal"):
        json.dump(spec["centraal"], open(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "remote-settings.json"), "w"))
    # Zoals gemeten met een token uit setup-token: geen subscriptionType (bouwsessie, 01-11-2026).
    print(json.dumps(spec.get("auth", {"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty",
                                       "analyticsDisabled": False})))
    sys.exit(0)
if spec.get("centraal_bij_start"):
    json.dump(spec["centraal_bij_start"], open(os.path.join(os.environ["CLAUDE_CONFIG_DIR"], "remote-settings.json"), "w"))
json.dump(args, open("args.json", "w"))
json.dump(dict(os.environ), open("env.json", "w"))
open("invoer.txt", "w").write("" if spec.get("lees_niet") else sys.stdin.read())
if "--mcp-config" in args:
    log = json.loads(args[args.index("--mcp-config") + 1])["mcpServers"]["lees"]["env"]["LEES_LOG"]
    with open(log, "a") as f:
        for r in spec.get("lees", []):
            f.write(json.dumps(r) + "\n")
if spec.get("kind"):
    open("kind.pid", "w").write(str(subprocess.Popen([sys.executable, "-c", "import time; time.sleep(120)"]).pid))
for r in spec.get("regels", []):
    print(json.dumps(r), flush=True)
time.sleep(spec.get("slaap", 0))
'''
NEPMAP = tempfile.mkdtemp(prefix="nepclaude-")
O.CLAUDE = os.path.join(NEPMAP, "claude")
with open(O.CLAUDE, "w") as f:
    f.write(f"#!{sys.executable}\n" + NEP)
os.chmod(O.CLAUDE, 0o700)
O.LIMIET_BESTAND = os.path.join(NEPMAP, "limiet.json")


def nep_vraag(spec, vraag="Vloerwasser X1 voor Suriname", werkwijze="WERKWIJZE", eisen=("netfrequentie 60 Hz",), **kw):
    """onderzoek() met een nagebootste claude; geeft (uitkomst of fout, args, env, invoer, map)."""
    m = tempfile.mkdtemp(prefix="nepvraag-")
    json.dump(spec, open(os.path.join(m, "nep.json"), "w"))
    try:
        uit = O.onderzoek(vraag, werkwijze, "2026-10-30", list(eisen), token=kw.pop("token", "sk-ant-oat01-nep"), werkmap=m, **kw)
    except O.GeenAbonnement as e:
        uit = e

    def lees(n):
        p = os.path.join(m, n)
        return (json.load(open(p)) if n.endswith(".json") else open(p).read()) if os.path.exists(p) else None
    return uit, lees("args.json"), lees("env.json"), lees("invoer.txt"), m


def assistent(*blokken):
    return {"type": "assistant", "message": {"content": list(blokken)}}


def zoekuit(*items):
    return {"type": "user", "message": {"content": []}, "tool_use_result": {"query": "x1", "results": [
        {"tool_use_id": "srvtoolu_nep", "content": [{"title": t, "url": u} for t, u in items]}]}}


JSON = ('```json\n{"vraag_kort": "vloerwasser X1 voor Suriname", "eisen": [], '
        '"aanbiedingen": [{"titel": "X1", "url": "https://winkel.voorbeeld.com/x1", "winkel": "W", "land": "BE", '
        '"soort": "nieuw", "prijs": 499, "munt": "EUR", "btw_inbegrepen": true, "verzending": 0, "beschikbaar": true, '
        '"bewijs": {"prijs": "X1 499,00 euro", "verzending": "gratis verzending"}, '
        '"compatibiliteit": {"netfrequentie 60 Hz": {"oordeel": "ja", "citaat": "Netspanning 127 V, 60 Hz"}}, '
        '"waarom": "60 Hz-versie, officiele dealer."}, '
        '{"titel": "X1 verzonnen", "url": "https://verzonnen.voorbeeld.com/z", "soort": "nieuw", "prijs": 10, "munt": "EUR", '
        '"land": "BE", "verzending": 0}], "advies": "Koop X1 verzonnen, die is het goedkoopst."}\n```')
ZOEKUIT = zoekuit(("X1 tweedehands 380 euro", "https://markt.voorbeeld.com/a"), ("X1 kopen", "https://media.voorbeeld.com/x1"))
# Een limietmelding van een abonnement met Usage credits uit; elke vraag moet er een tonen (Codex controle 20).
ABO = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": False, "overageStatus": "disabled",
       "unifiedWindows": {"five_hour": {"utilization": 0.1, "status": "allowed"}}}}
GEWOON = {"regels": [INIT, ABO, assistent({"type": "tool_use", "name": O.ZOEK, "input": {"query": "x1"}}), ZOEKUIT,
                     assistent({"type": "tool_use", "name": O.LEES, "input": {"url": "https://winkel.voorbeeld.com/x1"}}),
                     assistent({"type": "text", "text": JSON}), dict(EINDE, result=JSON)],
          "lees": [{"url": "https://winkel.voorbeeld.com/x1", "eind_url": "https://www.winkel.voorbeeld.com/x1/", "ok": True,
                    "tekst": PAGINA_X1, "fout": ""},
                   {"url": "https://kapot.voorbeeld.com/p", "eind_url": "https://kapot.voorbeeld.com/p", "ok": False,
                    "tekst": "", "fout": "HTTP 403"}]}
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-api03-nep-mag-nooit-mee"
os.environ["SALES_ANTHROPIC_API_KEY"] = "sk-ant-api03-nep-ook-niet"
os.environ["ANTHROPIC_BASE_URL"] = "https://api.voorbeeld.com"
uit, args, env, invoer, m_gewoon = nep_vraag(GEWOON)
check("geen enkele API-sleutel in de omgeving van claude -p, ook als de runner er een heeft (K1, K6)",
      env is not None and not any("ANTHROPIC" in k or "API_KEY" in k for k in env)
      and env.get("CLAUDE_CODE_OAUTH_TOKEN") == "sk-ant-oat01-nep", str(sorted(env or {})))
check("de omgeving is de witte lijst plus het token", env is not None
      # LC_CTYPE en __CF_* zet de nagebootste python of macOS zelf in het kindproces
      and set(k for k in env if not k.startswith("__") and k != "LC_CTYPE") <= set(O.OMGEVING) | {
          "CLAUDE_CODE_OAUTH_TOKEN", "DISABLE_AUTOUPDATER", "CLAUDE_CONFIG_DIR"},
      str(sorted(env or {})))
check("alleen WebSearch en de eigen leestool, in restricted-modus en nooit --bare (X1, K2)", args is not None
      and "--restricted" in args and args[args.index("--tools") + 1] == "WebSearch"
      and args[args.index("--allowedTools") + 1] == "WebSearch,mcp__lees__lees_pagina" and "--strict-mcp-config" in args
      and "--bare" not in args and "WebFetch" not in " ".join(args) and "--no-session-persistence" in args, str(args)[:400])
haak = json.loads(args[args.index("--settings") + 1])["hooks"]["PreToolUse"][0]
check("de zoekgrens zit als hook op WebSearch, met de grens van 6 (A3)", haak["matcher"] == "WebSearch"
      and "zoekgrens.py" in haak["hooks"][0]["command"] and haak["hooks"][0]["command"].endswith(" 6"))
check("het model is de alias opus en de vraag gaat via stdin, niet als argument", args[args.index("--model") + 1] == "opus"
      and "Vloerwasser X1 voor Suriname" in invoer and not any("Vloerwasser" in a for a in args))
systeem = open(args[args.index("--system-prompt-file") + 1], encoding="utf-8").read()
check("de systeemtekst staat in een bestand in de werkmap, niet op de opdrachtregel",
      args[args.index("--system-prompt-file") + 1] == os.path.join(m_gewoon, "systeem.txt") and "--system-prompt" not in args)
check("de werkwijze gaat mee, maar geen naam, collega's of lessen (Codex X4)", "WERKWIJZE" in systeem
      and "Mehdi" not in systeem and "collega" not in systeem.lower())
check("de vaste eisen staan in de vraag aan het model", "VASTE EISEN" in invoer and "netfrequentie 60 Hz" in invoer
      and "lees_pagina" in invoer)
_, args2, _, _, _ = nep_vraag(GEWOON, werkwijze="Wat Mehdi beslist: de aankoop. Mehdi Chegini kiest.")
s2 = open(args2[args2.index("--system-prompt-file") + 1], encoding="utf-8").read()
check("ook een naam in de werkwijze gaat niet naar buiten (Codex X4, ronde 2)", "Mehdi" not in s2 and "Chegini" not in s2
      and "Wat de opdrachtgever beslist" in s2)
check("gegevens, gelezen pagina's en tellers terug", isinstance(uit, dict) and uit["gegevens"]["vraag_kort"] ==
      "vloerwasser X1 voor Suriname" and set(uit["gelezen"]) == {"https://winkel.voorbeeld.com/x1"}
      and uit["zoekopdrachten"] == 1 and uit["leesbeurten"] == (1, 1) and uit["stop"] == "klaar" and uit["bron"] == "none",
      str({k: uit[k] for k in ("stop", "leesbeurten", "zoekopdrachten")}) if isinstance(uit, dict) else str(uit))
check("het leeslog is de gelezen tekst, ook onder de eind-url (X2)", uit["gelezen"]["https://winkel.voorbeeld.com/x1"] == PAGINA_X1)
_, _, env_c, _, m_c = nep_vraag(GEWOON)
check("claude krijgt een eigen lege configuratiemap, niets uit ~/.claude (Codex 15, punt 1)",
      env_c["CLAUDE_CONFIG_DIR"] == os.path.join(m_c, "claude-config") and os.path.isdir(env_c["CLAUDE_CONFIG_DIR"]))
gebruik = EINDE["usage"]
check("de tellers komen uit de eindregel, zonder dollar", uit["tokens"] == gebruik["input_tokens"] + gebruik["output_tokens"]
      + gebruik["cache_creation_input_tokens"] + gebruik["cache_read_input_tokens"] and "kosten" not in uit
      and set(uit["tellers"][0]) == {"input", "output", "cache_schrijven", "cache_lezen", "zoek", "lees"})
goed, weg = O.alleen_gelezen(uit["gegevens"]["aanbiedingen"], uit["gelezen"])
for a in goed:
    a["gezien_op"] = "2026-10-30"
r = A.verwerk(goed, VANDAAG, KOERSEN, ["netfrequentie 60 Hz"], paginas=uit["gelezen"])
r["afgewezen"] = weg + r["afgewezen"]
tekst = V.maak("Vloerwasser X1 voor Suriname", uit["gegevens"], r, "2026-10-30", "2026-10-30")
check("het verslag begint met de aanbeveling", tekst.startswith("**Aanbevolen:** [X1](https://winkel.voorbeeld.com/x1)"), tekst[:120])
check("het verzonnen aanbod staat nergens in het verslag, ook niet via vrij advies (Codex X2)", "verzonnen" not in tekst)
check("de uitleg van het model staat bij het aanbod, niet in de aanbeveling", "toelichting: 60 Hz-versie, officiele dealer." in tekst
      and "officiele dealer" not in tekst.splitlines()[0])
check("vrije modeltekst is begrensd", len(V._kort("x" * 500)) == 160)
bewijsdeel = tekst.split("Bewijs op de pagina:")[1].split("**Voorstel:**")[0] if "Bewijs op de pagina:" in tekst else ""
check("het verslag toont het bewijs met de tekst eromheen (Codex ronde 5)", "- prijs:" in bewijsdeel
      and "X1 499,00 euro, gratis verzending" in bewijsdeel and "- netfrequentie 60 Hz:" in bewijsdeel
      and "Netspanning 127 V, 60 Hz" in bewijsdeel and "- verzending:" in bewijsdeel, bewijsdeel)
check("het verslag zegt dat er niets gekocht is", "Ik kocht, bood en contacteerde niets." in tekst)
check("bedrag in Belgische schrijfwijze", V.euro(1299.5) == "1.299,50 euro")
check("titel met het beste totaal", V.titel(uit["gegevens"], r) == "Prijsonderzoek: vloerwasser X1 voor Suriname (beste 499,00 euro)")
r_onv = A.verwerk([aanbod(prijs=1099, verzending=None)], VANDAAG, KOERSEN)
check("ook bij een onvolledig totaal staat de prijs in het verslag (proef 30-10-2026)",
      "prijs 1099 EUR, totaal onvolledig: verzending" in V.maak("v", {}, r_onv, None, "2026-10-30"))
check("zonder goed aanbod geen aanbeveling", V.maak("v", {}, A.verwerk([], VANDAAG, KOERSEN), None, "2026-10-30")
      .startswith("**Geen aanbeveling:**"))
r = A.verwerk([aanbod(prijs=500), aanbod(url="https://b.voorbeeld.com/2", prijs=520)], VANDAAG, KOERSEN)
tekst = V.maak("v", {"vervolgvraag": "Is het voor privé of voor een firma?"}, r, "2026-10-30", "2026-10-30")
check("de reserve en de vervolgvraag staan bovenaan", "**Reserve:**" in tekst.split("## Aanbiedingen")[0]
      and "**Vraag aan jou:** Is het voor privé of voor een firma?" in tekst)

print("Grendels: geen API, geen betaald extra verbruik, grenzen (overleg 14, X1, X4, X6, K3, K4)")
SLAAP = {"regels": [], "slaap": 30}
begin = time.monotonic()
uit, _, _, _, _ = nep_vraag(dict(SLAAP, regels=[dict(INIT, apiKeySource="ANTHROPIC_API_KEY")]))
check("een andere bron dan het abonnement stopt meteen, zonder terugval (K1)", isinstance(uit, O.GeenAbonnement)
      and "ANTHROPIC_API_KEY" in str(uit) and time.monotonic() - begin < 10, f"{uit!r} {time.monotonic() - begin:.1f}s")
uit, _, _, _, _ = nep_vraag(dict(SLAAP, regels=[INIT, {"type": "rate_limit_event", "rate_limit_info": {
    "status": "allowed", "isUsingOverage": True}}]))
check("extra betaald verbruik bovenop het abonnement stopt meteen", isinstance(uit, O.GeenAbonnement) and "betaald" in str(uit))
uit, _, _, _, _ = nep_vraag({"regels": [INIT, assistent({"type": "text", "text": "Not logged in · Please run /login"}),
                                        dict(EINDE, is_error=True, result="Not logged in · Please run /login")]})
check("een token dat niet werkt is geen abonnement (gemeten 01-11: init zegt dan ook 'none')", isinstance(uit, O.GeenAbonnement)
      and "token" in str(uit))
uit, _, _, _, _ = nep_vraag({"regels": [INIT, {"type": "rate_limit_event", "rate_limit_info": {"status": "rejected"}},
                                        dict(EINDE, is_error=True, result="You've hit your limit · resets 5pm")]})
check("de limiet van het abonnement wordt stop 'limiet', geen API (G4)", isinstance(uit, dict) and uit["stop"] == "limiet"
      and "limit" in uit["fout"], str(uit)[:200])
uit, _, _, _, _ = nep_vraag({"regels": [INIT, dict(EINDE, is_error=True, result="Iets anders liep mis")]})
check("een andere fout wordt stop 'fout'", isinstance(uit, dict) and uit["stop"] == "fout")
uit, _, _, _, _ = nep_vraag({"regels": [INIT]})
check("zonder eindregel geen 'klaar'", isinstance(uit, dict) and uit["stop"] == "fout")
uit, _, _, _, _ = nep_vraag({"regels": [INIT, dict(EINDE, result=JSON)]})
check("een vraag zonder limietmelding blokkeert niet meer (overleg 25: alleen stoppen op een gemeten signaal)",
      isinstance(uit, dict) and uit["stop"] == "klaar", str(uit)[:200])
uit, _, _, _, _ = nep_vraag({"regels": [ABO, dict(EINDE, result=JSON)]})
check("een vraag zonder startbericht bewijst de bron niet (Codex 20, punt 1)", isinstance(uit, O.GeenAbonnement)
      and "startbericht" in str(uit), str(uit)[:200])
begin = time.monotonic()
uit, _, _, _, m = nep_vraag({"regels": [INIT], "slaap": 60, "kind": True}, deadline=time.monotonic() + 3)
duur = time.monotonic() - begin
kind = int(open(os.path.join(m, "kind.pid")).read())
time.sleep(0.3)
try:
    os.kill(kind, 0)
    kind_leeft = True
except OSError:
    kind_leeft = False
check("de deadline van de ronde stopt claude en zijn leestool samen (X4)", isinstance(uit, dict) and uit["stop"] == "plafond"
      and uit["reden"] == "tijd" and duur < 15 and not kind_leeft, f"{uit!r:.200} {duur:.1f}s kind {kind_leeft}")
begin = time.monotonic()
uit, _, _, _, _ = nep_vraag({"regels": [INIT, ABO, dict(EINDE, result=JSON)], "slaap": 60}, deadline=time.monotonic() + 40)
check("na de eindregel wacht de runner niet op een stdout die open blijft (Codex 15, punt 4)", isinstance(uit, dict)
      and uit["stop"] == "klaar" and time.monotonic() - begin < 15, f"{time.monotonic() - begin:.1f}s")
begin = time.monotonic()
uit, _, _, _, _ = nep_vraag({"regels": [], "slaap": 60, "lees_niet": True}, vraag="w" * 2_000_000,
                            deadline=time.monotonic() + 3)
check("een kind dat de vraag niet leest, houdt de deadline niet tegen (Codex 15, punt 4)",
      time.monotonic() - begin < 15, f"{uit!r:.120} {time.monotonic() - begin:.1f}s")
check("ook bij de deadline zonder startbericht is de bron niet bewezen (Codex 21, punt 1)",
      isinstance(uit, O.GeenAbonnement) and "startbericht" in str(uit), str(uit)[:200])
vol = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": False, "overageStatus": "disabled",
       "unifiedWindows": {"five_hour": {"utilization": 0.93, "status": "allowed"}}}}
begin = time.monotonic()
uit, _, _, _, _ = nep_vraag(dict(SLAAP, regels=[INIT, vol]))
check("boven 90 procent van een limiet stopt de vraag, voor er betaald extra verbruik kan komen (Codex 15, punt 1)",
      isinstance(uit, dict) and uit["stop"] == "limiet" and uit["reden"] == "vol" and uit["extra_verbruik"] == "disabled"
      and time.monotonic() - begin < 10)
check("die meting blokkeert de volgende vraag (zonder herstarttijd vijf uur)", O.te_vol())
os.remove(O.LIMIET_BESTAND)
aan = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": False, "overageStatus": "allowed",
       "unifiedWindows": {"five_hour": {"utilization": 0.2, "status": "allowed"}}}}
uit, _, _, _, _ = nep_vraag(dict(GEWOON, regels=[INIT, aan] + GEWOON["regels"][2:]))
check("overageStatus 'allowed' blokkeert niet meer, het wordt alleen bewaard (overleg 25, X1 en K2)",
      isinstance(uit, dict) and uit["stop"] == "klaar" and uit["extra_verbruik"] == "allowed", str(uit)[:200])
os.remove(O.LIMIET_BESTAND)
OAUTH = {"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty"}
for naam, spec_extra, woord in (("Team-account", {"auth": dict(OAUTH, subscriptionType="team")}, "persoonlijk"),
                                ("API-sleutel volgens auth status", {"auth": dict(OAUTH, authMethod="api_key")}, "niet aanvaard"),
                                ("een sleutelbron naast het token", {"auth": dict(OAUTH, apiKeySource="ANTHROPIC_API_KEY")},
                                 "niet aanvaard"),
                                ("niet aangemeld", {"auth": dict(OAUTH, loggedIn=False)}, "niet aanvaard"),
                                ("andere aanbieder", {"auth": dict(OAUTH, apiProvider="bedrock")}, "niet aanvaard"),
                                ("centrale instellingen", {"centraal": {"env": {"ANTHROPIC_AUTH_TOKEN": "x"}}}, "centrale")):
    uit, args, _, _, _ = nep_vraag(dict(GEWOON, **spec_extra))
    check(f"{naam}: claude -p start niet, er gaat geen aanvraag naar het model (Codex 16, punt 1)",
          isinstance(uit, O.GeenAbonnement) and woord in str(uit) and args is None, str(uit))
uit, _, _, _, _ = nep_vraag(dict(GEWOON, auth=dict(OAUTH, subscriptionType="max")))
check("een persoonlijk abonnementstype dat wel getoond wordt, mag", isinstance(uit, dict) and uit["abonnement"] == "max")
uit, _, _, _, _ = nep_vraag(GEWOON)
check("een setup-token zonder abonnementstype mag (gemeten: auth status toont het niet)", isinstance(uit, dict)
      and uit["stop"] == "klaar" and uit["abonnement"] == "oauth_token", str(uit)[:200])
begin = time.monotonic()
uit, _, _, _, _ = nep_vraag(dict(SLAAP, regels=[INIT], centraal_bij_start={"env": {"ANTHROPIC_AUTH_TOKEN": "x"}}))
check("centrale instellingen die claude -p bij de start ophaalt, stoppen de vraag bij het init-bericht",
      isinstance(uit, O.GeenAbonnement) and "centrale" in str(uit) and time.monotonic() - begin < 10, str(uit))
beheer = tempfile.mkdtemp(prefix="beheer-")
open(os.path.join(beheer, "managed-settings.json"), "w").write("{}")
oud_beheerd, O.BEHEERD = O.BEHEERD, (beheer,)
uit, args, _, _, _ = nep_vraag(GEWOON)
O.BEHEERD = oud_beheerd
check("met beheerde instellingen op de machine start claude niet (Codex 15, punt 1)", isinstance(uit, O.GeenAbonnement)
      and "beheerde instellingen" in str(uit) and args is None)
zeven = [zoekuit((f"r{i}", f"https://z.voorbeeld.com/{i}")) for i in range(O.MAX_ZOEKEN + 1)]
uit, _, _, _, _ = nep_vraag(dict(SLAAP, regels=[INIT] + zeven))
check("weigert de hook niet, dan stopt de runner bij de zevende zoekopdracht (K3)", isinstance(uit, dict)
      and uit["stop"] == "plafond" and uit["reden"] == "zoeken" and uit["zoekopdrachten"] == O.MAX_ZOEKEN + 1)
uit, _, _, _, _ = nep_vraag(dict(SLAAP, regels=[INIT] + [assistent({"type": "text", "text": "."})] * (O.MAX_BEURTEN + 1)))
check("meer dan MAX_BEURTEN beurten stopt de runner (K4)", isinstance(uit, dict) and uit["reden"] == "beurten")
check("de grenzen: 6 zoek, 6 gelezen, 10.000 tokens per pagina (G2, G5)",
      (O.MAX_ZOEKEN, O.MAX_LEZEN, O.MAX_PAGINA_TOKENS) == (6, 6, 10000))
uit, _, _, _, _ = nep_vraag(GEWOON)
bewaard = json.load(open(O.LIMIET_BESTAND))
check("de gemeten vensters worden bewaard voor de volgende vraag, rechten 600 (overleg 25, K2)",
      bewaard["vensters"]["five_hour"]["utilization"] == 0.1 and os.stat(O.LIMIET_BESTAND).st_mode & 0o077 == 0)
with open(O.LIMIET_BESTAND, "w") as f:
    json.dump({"vensters": {"five_hour": {"utilization": 0.95, "resetsAt": time.time() + 3600}}}, f)
uit, args, _, _, _ = nep_vraag(GEWOON)
check("lag de vorige meting boven 90 procent en is het venster nog niet herstart, dan start er niets (overleg 25, K2)",
      isinstance(uit, dict) and uit["stop"] == "limiet" and uit["reden"] == "vol_vooraf" and args is None, str(uit)[:200])
with open(O.LIMIET_BESTAND, "w") as f:
    json.dump({"vensters": {"five_hour": {"utilization": 0.95, "resetsAt": time.time() - 60}}}, f)
uit, args, _, _, _ = nep_vraag(GEWOON)
check("na de herstart van het venster mag het weer", isinstance(uit, dict) and uit["stop"] == "klaar" and args is not None)
alleen_boven = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": False,
                "rateLimitType": "five_hour", "utilization": 0.93, "resetsAt": time.time() + 3600,
                "unifiedWindows": {"five_hour": {"utilization": 0.93}}}}
uit, _, _, _, _ = nep_vraag(dict(SLAAP, regels=[INIT, alleen_boven]))
uit, args, _, _, _ = nep_vraag(GEWOON)
check("een herstarttijd die alleen bovenaan de melding staat, telt ook (Codex 26, punt 1)",
      isinstance(uit, dict) and uit["reden"] == "vol_vooraf" and args is None, str(uit)[:200])
def vol_bestand(naam, uren_geleden, met_ts=True):
    with open(O.LIMIET_BESTAND, "w") as f:
        json.dump({"vensters": {naam: {"utilization": 0.95}}, **({"gemeten_ts": time.time() - uren_geleden * 3600}
                                                                 if met_ts else {})}, f)


vol_bestand("five_hour", 1)
check("zonder herstarttijd blokkeert een vijfuursvenster vijf uur (Codex 26 en 27)", O.te_vol())
vol_bestand("five_hour", 6)
check("na die vijf uur niet meer", not O.te_vol())
vol_bestand("seven_day", 6)
check("een weekvenster zonder herstarttijd blokkeert een week, niet vijf uur (Codex 27)", O.te_vol())
vol_bestand("seven_day", 8 * 24)
check("na een week niet meer", not O.te_vol())
vol_bestand("onbekend", 6 * 24)
check("een onbekend venster telt als het langste (Codex 27)", O.te_vol())
vol_bestand("seven_day", 0, met_ts=False)
check("een oud bestand zonder meettijd telt vanaf de tijd van het bestand (Codex 27)", O.te_vol())
with open(O.LIMIET_BESTAND, "w") as f:
    json.dump({"vensters": {"five_hour": {"utilization": 0.95, "resetsAt": time.time() + 3600}}}, f)
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("ook de abonnementsproef start niet na een meting boven 90 procent (Codex 26, punt 2)", not gelukt
      and "vorige meting" in melding, melding)
os.remove(O.LIMIET_BESTAND)
json.dump({"regels": [INIT, alleen_boven, dict(EINDE, result="ok")]}, open(os.path.join(NEPMAP, "nep.json"), "w"))
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("stopt de proef boven 90 procent, dan bewaart ze die meting voor de volgende vraag (Codex 26, punt 2)",
      not gelukt and O.te_vol(), melding)
os.remove(O.LIMIET_BESTAND)
oud_bestand = O.TOKEN_BESTAND
O.TOKEN_BESTAND = os.path.join(NEPMAP, "bestaat-niet")
uit, args, _, _, _ = nep_vraag(GEWOON, token=None)
check("zonder token start claude niet (K6)", isinstance(uit, O.GeenAbonnement) and args is None)
O.TOKEN_BESTAND = oud_bestand
tok = os.path.join(NEPMAP, "claude-token")
with open(tok, "w") as f:
    f.write("CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-abc_DEF-123\n")
os.chmod(tok, 0o644)
try:
    O.lees_token(tok)
    open_leesbaar = False
except O.GeenAbonnement:
    open_leesbaar = True
os.chmod(tok, 0o600)
check("het token komt uit een eigen bestand met rechten 600 (X8, K8)", open_leesbaar and O.lees_token(tok) == "sk-ant-oat01-abc_DEF-123")
with open(tok, "w") as f:
    f.write("ANTHROPIC_API_KEY=sk-ant-api03-nep\n")
try:
    O.lees_token(tok)
    api_aanvaard = True
except O.GeenAbonnement:
    api_aanvaard = False
check("een API-sleutel in dat bestand telt nooit als token", not api_aanvaard)
uit_meld = {"type": "rate_limit_event", "rate_limit_info": {"status": "allowed", "isUsingOverage": False,
            "overageStatus": "disabled", "unifiedWindows": {"five_hour": {"utilization": 0.1, "status": "allowed"}}}}
json.dump({"regels": [INIT, uit_meld, dict(EINDE, result="ok")]}, open(os.path.join(NEPMAP, "nep.json"), "w"))
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("de abonnementsproef zegt 'werkt' bij bron none, extra verbruik uit en een gewoon einde (X7)",
      gelukt and "werkt via het abonnement oauth_token" in melding and "disabled" in melding, melding)
json.dump({"regels": [INIT, aan, dict(EINDE, result="ok")]}, open(os.path.join(NEPMAP, "nep.json"), "w"))
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("de proef slaagt ook bij overageStatus 'allowed' en meldt het (overleg 25)", gelukt and "allowed" in melding, melding)
json.dump({"regels": [INIT], "auth": {"loggedIn": True, "authMethod": "oauth_token", "apiProvider": "firstParty",
                                      "subscriptionType": "enterprise"}},
          open(os.path.join(NEPMAP, "nep.json"), "w"))
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("de abonnementsproef weigert een Enterprise-account voor elke modelaanvraag", not gelukt and "persoonlijk" in melding)
json.dump({"regels": [dict(INIT, apiKeySource="ANTHROPIC_API_KEY"), dict(EINDE, result="ok")]},
          open(os.path.join(NEPMAP, "nep.json"), "w"))
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("de abonnementsproef faalt als Claude Code een API-sleutel gebruikt", not gelukt and "ANTHROPIC_API_KEY" in melding)
json.dump({"regels": [ABO, dict(EINDE, result="ok")]}, open(os.path.join(NEPMAP, "nep.json"), "w"))
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("een proef zonder startbericht slaagt niet (Codex 20, punt 1)", not gelukt and "startbericht" in melding, melding)
json.dump({"regels": [INIT, dict(EINDE, is_error=True, result="Invalid token sk-ant-oat01-geheim-123")]},
          open(os.path.join(NEPMAP, "nep.json"), "w"))
gelukt, melding = O.proef_abonnement(token="sk-ant-oat01-nep")
check("een fout toont nooit het token", not gelukt and "geheim" not in melding and "Invalid token" in melding, melding)
O.TOKEN_BESTAND = os.path.join(NEPMAP, "bestaat-niet")
gelukt, melding = O.proef_abonnement()
check("zonder tokenbestand faalt de proef met uitleg", not gelukt and "geen abonnementstoken" in melding)
O.TOKEN_BESTAND = oud_bestand
for k in ("ANTHROPIC_API_KEY", "SALES_ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL"):
    os.environ.pop(k, None)
broncode = open(Path(O.__file__), encoding="utf-8").read()
check("onderzoek.py kent de API-bibliotheek niet meer", "import anthropic" not in broncode and "from anthropic" not in broncode)

print("Zoekgrens (hook) en leestool (MCP)")
from aankoop import leesserver as L  # noqa: E402
from aankoop import zoekgrens as Z  # noqa: E402
teller = os.path.join(NEPMAP, "teller")
uitslagen = [Z.tel(teller, 6) for _ in range(7)]
check("de hook laat zes zoekopdrachten door en weigert de zevende", uitslagen[:6] == [None] * 6
      and uitslagen[6]["hookSpecificOutput"]["permissionDecision"] == "deny")
for url in ("http://127.0.0.1:3022/api", "http://localhost/", "http://169.254.169.254/latest", "http://10.0.0.5/",
            "http://[::1]/", "ftp://winkel.voorbeeld.com/", "https://example.com:8443/", "file:///etc/passwd"):
    try:
        L.openbaar(url)
        doorgelaten = True
    except L.Geweigerd:
        doorgelaten = False
    check(f"de leestool weigert {url} (X2)", not doorgelaten)
try:
    L._Doorverwijzing().redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1:3022/api/agent")
    omweg = True
except L.Geweigerd:
    omweg = False
check("ook een doorverwijzing naar de VM zelf wordt geweigerd (X2)", not omweg)


class NepAntwoordSock:
    def __init__(self, adres):
        self.fp = type("fp", (), {"raw": type("raw", (), {"_sock": type("s", (), {"getpeername": lambda s: (adres, 443)})()})()})()


def verbonden(adres):
    try:
        L.verbonden_openbaar(NepAntwoordSock(adres))
        return True
    except L.Geweigerd:
        return False


check("na het verbinden telt het echte adres: 127.0.0.1 of de Docker-bridge nooit, ook na DNS-rebinding",
      not verbonden("127.0.0.1") and not verbonden("172.17.0.1") and not verbonden("::ffff:127.0.0.1")
      and verbonden("172.66.147.243"))
try:
    L.verbonden_openbaar(object())
    onbekend_door = True
except L.Geweigerd:
    onbekend_door = False
check("een onbekend verbonden adres telt niet", not onbekend_door)
HTML = ("<html><head><title>X1</title><script>var geheim=1;</script>"
        "<meta property='og:image' content='/img/x1.jpg'><meta name='description' content='X1 vloerwasser'></head><body>"
        "<script type='application/ld+json'>{\"offers\": {\"price\": 499, \"priceCurrency\": \"EUR\"}}</script>"
        "<h1>Vloerwasser X1</h1><p>Nu&nbsp;499,00&nbsp;euro</p><table><tr><td>Netspanning</td><td>127 V, 60 Hz</td></tr></table>"
        "<style>.x{}</style><img src='https://cdn.voorbeeld.com/x1b.jpg'></body></html>")
leeslog = os.path.join(NEPMAP, "gelezen.jsonl")
nep_haal = lambda url: ("https://www.winkel.voorbeeld.com/x1", "text/html; charset=utf-8", HTML.encode())
tekst, gelukt = L.lees("https://winkel.voorbeeld.com/x1", leeslog, nep_haal)
check("de leestool maakt tekst van de pagina, met productgegevens en foto's, zonder scripts", gelukt
      and "Nu 499,00 euro" in tekst and "Netspanning | 127 V, 60 Hz" in tekst and '"price": 499' in tekst
      and "https://www.winkel.voorbeeld.com/img/x1.jpg" in tekst and "https://cdn.voorbeeld.com/x1b.jpg" in tekst
      and "geheim" not in tekst and ".x{}" not in tekst, tekst)
log5 = os.path.join(NEPMAP, "documenten.jsonl")
DOCHTML = ("<html><body><h1>X1</h1><a href='/manual/x1.pdf'>Handleiding</a><a href='https://cdn.voorbeeld.com/spec.PDF'>"
           "Specificaties</a><a href='/x2'>X2</a></body></html>")
tekst5, _ = L.lees("https://winkel.voorbeeld.com/x1", log5, lambda u: (u, "text/html", DOCHTML.encode()))
check("de leestool toont de PDF-links van de pagina, zoals een handleiding (overleg 33, A)",
      "Documenten: https://winkel.voorbeeld.com/manual/x1.pdf https://cdn.voorbeeld.com/spec.PDF" in tekst5
      and "/x2" not in tekst5.split("Documenten:")[1].splitlines()[0], tekst5)
regel = json.loads(open(leeslog).read().splitlines()[0])
check("het model krijgt precies de tekst die in het leeslog staat (X2)", tekst == f"URL: {regel['eind_url']}\n\n{regel['tekst']}")
gl, lb = O.gelezen_uit(leeslog)
check("het leeslog geeft gelezen onder de eind-url", set(gl) == {"https://winkel.voorbeeld.com/x1"} and lb == (1, 0))
log3 = os.path.join(NEPMAP, "omweg.jsonl")
with open(log3, "w") as f:
    f.write(json.dumps({"url": "https://w.voorbeeld.com/x1", "eind_url": "https://w.voorbeeld.com/categorie", "ok": True,
                        "tekst": "Andere X 99 euro"}) + "\n")
    f.write(json.dumps({"url": "https://w.voorbeeld.com/x2", "eind_url": "https://w.voorbeeld.com/x2", "ok": True,
                        "tekst": "X2 nu 500 euro"}) + "\n")
    f.write(json.dumps({"url": "https://w.voorbeeld.com/x2", "eind_url": "https://w.voorbeeld.com/x2", "ok": True,
                        "tekst": "X2 uitverkocht, gratis verzending"}) + "\n")
gl3, _ = O.gelezen_uit(log3)
check("tekst na een doorverwijzing hoort bij de eindpagina, niet bij de gevraagde (Codex 15, punt 3)",
      "https://w.voorbeeld.com/x1" not in gl3 and gl3["https://w.voorbeeld.com/categorie"] == "Andere X 99 euro")
check("twee lezingen van dezelfde pagina worden niet aan elkaar geplakt: de laatste telt (Codex 15, punt 3)",
      gl3["https://w.voorbeeld.com/x2"] == "X2 uitverkocht, gratis verzending")
for host in ("localhost", "127.0.0.1"):
    try:
        L._vast_verbinden((host, 80), 2)
        vast_door = True
    except L.Geweigerd:
        vast_door = False
    check(f"de verbinding zelf gaat nooit naar {host}, ook na een DNS-wissel (Codex 15, punt 2)", not vast_door)
check("de leestool verbindt via de vaste verbinders", isinstance(L._VasteHTTPS("voorbeeld.com"), L.http.client.HTTPSConnection)
      and L._VasteHTTPS("voorbeeld.com")._create_connection is L._vast_verbinden
      and L._VasteHTTP("voorbeeld.com")._create_connection is L._vast_verbinden)


def kapot(url):
    raise L.Geweigerd("geen openbaar adres")


for _ in range(L.MAX_LEZEN - 1):
    L.lees("http://127.0.0.1/", leeslog, kapot)
tekst, gelukt = L.lees("https://winkel.voorbeeld.com/x2", leeslog, nep_haal)
check("een mislukte lezing kost geen leesbeurt (overleg 29, X1)", gelukt and O.gelezen_uit(leeslog)[1] == (2, L.MAX_LEZEN - 1))
for _ in range(L.MAX_POGINGEN - L.MAX_LEZEN - 1):
    L.lees("http://127.0.0.1/", leeslog, kapot)
tekst, gelukt = L.lees("https://winkel.voorbeeld.com/x3", leeslog, nep_haal)
check("na twaalf pogingen samen is de leesgrens bereikt, ook met weinig gelezen (overleg 29, X1)",
      L.MAX_POGINGEN == 12 and
      not gelukt and "Leesgrens" in tekst and sum(O.gelezen_uit(leeslog)[1]) == L.MAX_POGINGEN)
log4 = os.path.join(NEPMAP, "tien.jsonl")
for i in range(L.MAX_LEZEN):
    L.lees(f"https://winkel.voorbeeld.com/p{i}", log4, nep_haal)
tekst, gelukt = L.lees("https://winkel.voorbeeld.com/p99", log4, nep_haal)
check("na zes gelezen pagina's is de leesgrens bereikt", not gelukt and "Leesgrens" in tekst
      and O.gelezen_uit(log4)[1] == (L.MAX_LEZEN, 0))
lang = ("<p>" + "woord " * 20000 + "</p>").encode()
log2 = os.path.join(NEPMAP, "lang.jsonl")
tekst, _ = L.lees("https://winkel.voorbeeld.com/lang", log2, lambda u: (u, "text/html", lang))
check("een lange pagina wordt afgekapt op ongeveer 10.000 tokens", len(json.loads(open(log2).read())["tekst"]) <= L.MAX_TEKENS + 20
      and tekst.endswith("[afgekapt]"))
a = L.antwoord({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}}, leeslog)
check("de MCP-server antwoordt op initialize met dezelfde protocolversie", a["result"]["protocolVersion"] == "2025-06-18")
check("een melding zonder id krijgt geen antwoord", L.antwoord({"jsonrpc": "2.0", "method": "notifications/initialized"}, leeslog) is None)
a = L.antwoord({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, leeslog)
check("de MCP-server biedt alleen lees_pagina", [t["name"] for t in a["result"]["tools"]] == ["lees_pagina"])
a = L.antwoord({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "schrijf", "arguments": {}}}, leeslog)
check("een andere tool bestaat niet", "error" in a)
proc = subprocess.run([sys.executable, str(Path(L.__file__))], input=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
                      + "\n", capture_output=True, text=True, timeout=20, env=dict(os.environ, LEES_LOG=os.path.join(NEPMAP, "x.jsonl")))
check("de leestool draait als los proces over stdin en stdout", json.loads(proc.stdout)["result"]["tools"][0]["name"] == "lees_pagina",
      proc.stderr[-300:])

print("Gezien, niet nagekeken: alleen een prijs uit de titel (overleg 9, X4; overleg 14, A3)")
zoek = {**O.zoekresultaten_uit(ZOEKUIT["tool_use_result"])}
check("zoekresultaten met titel", zoek == {"https://markt.voorbeeld.com/a": "X1 tweedehands 380 euro",
                                           "https://media.voorbeeld.com/x1": "X1 kopen"}, str(zoek))
gz = O.alleen_gezien([
    {"titel": "X1 markt", "url": "https://markt.voorbeeld.com/a", "prijs": 380, "citaat": "X1 tweedehands 380 euro", "reden": "niet leesbaar"},
    {"titel": "X1 media", "url": "https://media.voorbeeld.com/x1", "prijs": 949, "citaat": "nu voor 949,00 euro"},
    {"titel": "X1 verzonnen", "url": "https://verzonnen.voorbeeld.com/z", "prijs": 10, "citaat": "10 euro"},
    {"titel": "X1 andere prijs", "url": "https://markt.voorbeeld.com/a", "prijs": 300, "citaat": "X1 tweedehands 380 euro"},
    {"titel": "X1 al gelezen", "url": "https://winkel.voorbeeld.com/x1", "prijs": 499}], {**zoek, "https://winkel.voorbeeld.com/x1": "X1"},
    ["https://winkel.voorbeeld.com/x1"])
check("alleen urls uit een zoekresultaat van deze ronde, een keer, met een prijs uit de titel",
      [(x["url"], x["prijs"]) for x in gz] == [("https://markt.voorbeeld.com/a", 380)], str(gz))
check("een prijs die niet in het zoekresultaat staat: de rij valt weg", O.alleen_gezien(
      [{"titel": "X1", "url": "https://markt.voorbeeld.com/a", "prijs": 250, "citaat": "X1 tweedehands 380 euro"}], zoek) == [])
zoek_v = {"https://w.voorbeeld.com/x": "X1 Complete. Shipping 19 euro. Price 949 USD"}
check("een verzendkost is geen productprijs (Codex controle 10)", O.alleen_gezien(
      [{"titel": "X1", "url": "https://w.voorbeeld.com/x", "prijs": 19, "munt": "EUR", "citaat": "Shipping 19 euro"}], zoek_v) == [])
check("de munt hoort bij het bedrag, Europa is geen euro (Codex controle 11)", O.alleen_gezien(
      [{"titel": "X1", "url": "https://w.voorbeeld.com/e", "prijs": 949, "munt": "EUR", "citaat": "MOVA Europa 949 USD"}],
      {"https://w.voorbeeld.com/e": "MOVA Europa 949 USD"}) == [] and O._munt_bij_bedrag(1299, "EUR", "nu € 1.299,00")
      and O._munt_bij_bedrag(949, "EUR", "voor 949,- euro") and not O._munt_bij_bedrag(949, "EUR", "949 USD of 19 euro"))
check("de munt moet in het citaat staan", O.alleen_gezien(
      [{"titel": "X1", "url": "https://w.voorbeeld.com/x", "prijs": 949, "munt": "EUR", "citaat": "Price 949 USD"}], zoek_v) == []
      and len(O.alleen_gezien([{"titel": "X1", "url": "https://w.voorbeeld.com/x", "prijs": 949, "munt": "USD",
                                "citaat": "Price 949 USD"}], zoek_v)) == 1)
r = A.verwerk([], VANDAAG, KOERSEN)
tekst = V.maak("v", {}, r, "2026-10-30", "2026-10-30", gz, {"tokens": 401000})
check("gezien-niet-nagekeken staat apart met klikbare link en is nooit de aanbeveling",
      tekst.startswith("**Geen aanbeveling:**") and "## Gezien, niet nagekeken (nooit aanbevolen)" in tekst
      and "- [X1 markt](https://markt.voorbeeld.com/a): 380 EUR volgens het zoekresultaat; niet leesbaar" in tekst, tekst)
check("het verbruik staat in de controleregel, zonder dollar", "Verbruik: 401000 tokens via het Claude-abonnement, geen API-kost."
      in tekst and "dollar" not in tekst)

print("Alleen de productvraag naar de AI (overleg X4 en K6, Codex X3)")
check("een gewone productvraag gaat door", P.gevonden(
    "Livox Mid-360 lidar, nieuw of tweedehands, levering in Belgie, voor een firma, voor half november, budget 900 euro") == [])
check("spanning, frequentie, merken en modelnummers zijn geen persoonsgegevens",
      P.gevonden("MOVA V70 vloerwasser voor Suriname, 220 V 60 Hz, stekker type A/B, bandje voor Apple Watch, "
                 "voor Harmonie Bouw, monitor 1 ms Reactietijd, model RX-7900 XTX, Mr. Proper allesreiniger") == [])
check("een e-mailadres houdt de vraag tegen", P.gevonden("stuur naar iemand@voorbeeld.com") == ["e-mailadres"])
check("een telefoonnummer", P.gevonden("bel 0470 12 34 56") == ["telefoonnummer"])
check("een rekeningnummer", P.gevonden("betaal met BE68 5390 0754 7034") == ["rekeningnummer"])
check("een ondernemingsnummer", P.gevonden("factuur op 0123.456.789") == ["ondernemingsnummer"])
check("een adres", P.gevonden("leveren in de Voorbeeldstraat 12") == ["adres"])
check("een naam met aanspreking", P.gevonden("droger voor mevrouw Proefnaam") == ["naam"])
check("Mr. met een naam blijft tegengehouden, Mr. Proper niet (Codex X10, ronde 3)", P.gevonden("cadeau voor Mr. John") == ["naam"]
      and P.gevonden("Mr Proper allesreiniger 5 liter") == [])
check("een klant met voor- en achternaam", P.gevonden("klant Jan Proefnaam wil een droger") == ["naam"])
check("een naam zonder aanspreking houdt de vraag tegen (overleg 39, K4)",
      P.gevonden("Zoek lasklemmen, te leveren aan Lotte Proefnaam in Mechelen") == ["naam"]
      and P.gevonden("stofzuiger voor Jan Peeters") == ["naam"])
check("een merk met een voornaam gaat door (overleg 39, K4)", all(P.gevonden(t) == [] for t in (
      "Herman Miller Aeron bureaustoel tweedehands", "Tommy Hilfiger jas", "Seat Leon Cupra velgen",
      "Stanley Black and Decker boor", "iPhone 15 Pro Max", "Sonos Era 100 wit", "Jan 2026 levering")))
check("het korte verslag zegt wat het zag, niet de gegevens zelf",
      "e-mailadres" in V.tegengehouden(["e-mailadres"]) and "@" not in V.tegengehouden(["e-mailadres"]))

print("De runner: geen vraag in het logboek, een deadline per ronde")
import prijsonderzoeker as PO  # noqa: E402

logboek, klaar, opgepakt, noden = [], [], [], []
PO.ag.log = lambda *a: logboek.append(a)
PO.ag.klaarzet = lambda items: klaar.extend(items)
PO.bord.opgepakt = lambda kid, door: opgepakt.append(kid)
PO.K.haal = lambda: ("2026-10-30", KOERSEN)


class NepRonde:
    werkwijze = "## Wat ik nooit doe\n\n- nooit kopen\n\n## Wat Mehdi beslist\n\n- de aankoop\n"
    detail = ""

    def nood(self, tekst, wie="mehdi"):
        noden.append(tekst)

    def bron(self, naam, inhoud):
        pass


GEHEIM = "Proefvraag-zeven-zeven"


def geen_abonnement(*a, **k):
    raise PO.O.GeenAbonnement("geen abonnementstoken in ~/.config/prijsonderzoeker/claude-token")


PO.O.onderzoek = geen_abonnement
PO.werk(NepRonde(), "vloerwasser X1")
check("zonder werkend abonnement een nood met de reden, en niets via de API (overleg 14, K1)",
      any("Claude-abonnement werkt niet" in n and "niets via de API" in n and "geen abonnementstoken" in n for n in noden),
      str(noden))
oud_open = PO.open_vragen
PO.open_vragen = lambda: [{"id": 7, "inhoud": "lidar"}, {"id": 8, "inhoud": "drone"}]
r = NepRonde()
PO.werk(r, None)
check("zonder werkend abonnement blijven bordvragen klaarstaan, niets opgepakt (Codex 20, punt 3)",
      opgepakt == [] and "2 wachten" in r.detail, r.detail)


def kapotte_vraag(*a, **k):
    raise RuntimeError("iets anders liep mis")


PO.O.onderzoek = kapotte_vraag
r = NepRonde()
PO.werk(r, None)
check("ook bij een andere fout blijft de bordvraag klaarstaan, met een nood (Codex 21, punt 3)",
      opgepakt == [] and "2 wachten" in r.detail and any("blijft klaarstaan" in n for n in noden), r.detail)
for stop in ("fout", "limiet", "plafond"):
    PO.O.onderzoek = lambda *a, stop=stop, **k: {"gegevens": {"vraag_kort": "lidar", "aanbiedingen": []}, "gelezen": {},
                                                 "zoekresultaten": {},
                                                 "tekst": "", "tokens": 10, "tellers": [], "leesbeurten": (0, 0),
                                                 "zoekopdrachten": 0, "stop": stop, "model": "m", "fout": "x"}
    klaar.clear()
    r = NepRonde()
    PO.werk(r, None)
    check(f"bij stop '{stop}' geen verslag en blijft de bordvraag klaarstaan (Codex 22, punt 3)",
          opgepakt == [] and not klaar and "2 wachten" in r.detail, r.detail)
PO.open_vragen = oud_open
noden.clear()
PO.O.onderzoek = lambda *a, **k: {"gegevens": {"aanbiedingen": []}, "gelezen": {}, "zoekresultaten": {}, "tekst": "",
                                  "tokens": 600000, "tellers": [], "leesbeurten": (0, 0), "zoekopdrachten": 0,
                                  "stop": "limiet", "model": "m", "fout": "You've hit your limit"}
PO.werk(NepRonde(), "vloerwasser X1")
check("de limiet van het abonnement wordt een nood (G4)", any("limiet van het Claude-abonnement" in n for n in noden), str(noden))
check("geen dollargrens meer in de runner", not hasattr(PO, "MAX_DOLLAR"))
PO.O.onderzoek = lambda *a, **k: {"gegevens": None, "gelezen": {}, "tekst": "", "tokens": 10, "zoekopdrachten": 0,
                                  "stop": "klaar", "model": "m"}
PO.werk(NepRonde(), f"vloerwasser {GEHEIM}")
check("de vraag staat nooit in het logboek, ook niet bij een fout (Codex X3)",
      logboek and not any(GEHEIM in str(x) for x in logboek), str(logboek)[:300])
check("zonder leesbaar antwoord geen leeg verslag, wel een nood (Codex 22, punt 3)",
      not klaar and any("zonder leesbaar antwoord" in n for n in noden), str(klaar)[:200])
logboek.clear()
PO.werk(NepRonde(), "droger voor mevrouw Proefnaam")
check("een vraag met persoonsgegevens gaat niet naar het model", klaar[-1]["titel"] == "Prijsvraag niet verstuurd: persoonsgegevens"
      and not any("Proefnaam" in str(x) for x in logboek))
PO.open_vragen = lambda: [{"id": 7, "inhoud": "lidar"}, {"id": 8, "inhoud": "drone"}]
r = NepRonde()
PO.werk(r, None, False, begin=time.monotonic() - PO.RONDE_SECONDEN)
check("zonder tijd over blijft een klaargezette vraag staan (Codex X6)", opgepakt == [] and "2 wachten" in r.detail, r.detail)

rij = {"compatibiliteit": {"netspanning 220 V": {"oordeel": "ja", "citaat": "220-240 V", "bewijs_url": "https://w.be/h.pdf"},
                           GEHEIM: "onbekend"}, "per_eis": ["ja", "onbekend"]}
regels = PO.per_eis(rij, ["netspanning 220 V", GEHEIM])
check("het werkverslag toont per eis het oordeel van model en code, een eigen eis zonder haar woorden",
      regels == [{"eis": "netspanning 220 V", "model": "ja", "citaat": "220-240 V", "bewijs_url": "https://w.be/h.pdf",
                  "code": "ja"},
                 {"eis": "eis 2", "model": "onbekend", "citaat": None, "bewijs_url": None, "code": "onbekend"}]
      and GEHEIM not in str(regels), str(regels))

check("het werkverslag telt sleutels die geen eis zijn, zonder hun tekst (overleg 35, D)",
      PO.andere_sleutels({"compatibiliteit": {"netspanning 220 V": "ja", GEHEIM: "ja"}}, ["netspanning 220 V"]) == 1)

bron = open(Path(PO.__file__), encoding="utf-8").read()
check("de runner zet geen API-sleutel klaar voor de prijsvraag (overleg 14)", "sleutelbron" not in bron
      and "zet_anthropic" not in bron and "anthropic" not in bron.lower().replace("claude-abonnement", ""))

print("Proefbank: prijsvragen zonder het bord (overleg 39)")
from aankoop import proefbank as PB  # noqa: E402

X1URL = "https://winkel.voorbeeld.com/x1"
PB_PAG = {X1URL: pagina("Vloerwasser X1 nu 500,00 euro. Gratis verzending naar België.")}
PO.O.onderzoek = lambda *a, **k: {
    "gegevens": {"vraag_kort": "vloerwasser", "eisen": [], "aanbiedingen": [aanbod(bewijs={
        "prijs": "X1 nu 500,00 euro", "verzending": "Gratis verzending naar België."})]},
    "gelezen": PB_PAG, "zoekresultaten": {}, "tekst": "", "tokens": 10, "tellers": [], "leesbeurten": (1, 0),
    "zoekopdrachten": 1, "stop": "klaar", "model": "m", "bron": "none"}
voor_log, voor_klaar, echte_log = len(logboek), len(klaar), PO.ag.log
uit = PB.een_proef(PO, {"id": "T1", "vraag": "vloerwasser X1 voor thuis"}, "2026-10-30", KOERSEN, "werkwijze")
check("de proefbank schrijft niets op het bord en zet het bord daarna terug",
      len(logboek) == voor_log and len(klaar) == voor_klaar and PO.ag.log is echte_log and uit["logboek"]
      and "**Aanbevolen:**" in uit["verslag"], str(uit.get("fout")))
check("de proefbank bewaart de keuze van de code", uit["keuze"]["beste"]["url"] == X1URL and uit["model_vragen"] == 1)
check("een geslaagde proef doorstaat de keuring", all(ok for ok, _ in PB.keur(
      {"automatisch": {"aanbeveling": True, "verslag_moet": ["Aanbevolen"], "beste_nooit": ["veiling"],
                       "beste_max_eur": 600, "model": True}}, uit)))
check("een verkeerde aanbeveling valt op in de keuring", not all(ok for ok, _ in PB.keur(
      {"automatisch": {"aanbeveling": False, "beste_nooit": ["x1"]}}, uit)))
check("een aanbeveling boven het budget valt op in de keuring", not all(ok for ok, _ in PB.keur(
      {"automatisch": {"beste_max_eur": 150}}, uit)))
check("een aanbod zonder gelezen pagina valt op in de keuring", not all(ok for ok, _ in PB.keur(
      {}, dict(uit, gelezen=[]))))
uit = PB.een_proef(PO, {"id": "T2", "vraag": "stofzuiger, bel Jan Proefnaam op 0478 12 34 56"}, "2026-10-30", KOERSEN, "w")
check("een vraag met persoonsgegevens gaat in de proefbank ook niet naar het model", uit["model_vragen"] == 0
      and all(ok for ok, _ in PB.keur({"automatisch": {"model": False, "aanbeveling": False}}, uit)), str(uit["keuze"]))
reeks = json.load(open(os.path.join(PB.HIER, "docs", "aankoop", "proeven", "prijsonderzoeker.json"), encoding="utf-8"))
check("de reeks van overleg 39 heeft twintig proeven P01 tot P20, zonder echte persoonsgegevens buiten P18 en P19",
      [p["id"] for p in reeks] == [f"P{i:02d}" for i in range(1, 21)]
      and [p["id"] for p in reeks if P.gevonden(p["vraag"])] == ["P18", "P19"])
try:
    PB.draai("onbestaand.json", os.path.join(PB.HIER, "proeven"))
    binnen = False
except SystemExit as e:
    binnen = "buiten de repo" in str(e)
check("de proefmap mag nooit in de repo liggen", binnen)

print("Koersen van de ECB")
XML = """<gesmes:Envelope><Cube><Cube time='2026-10-30'>
<Cube currency='USD' rate='1.0812'/><Cube currency='GBP' rate='0.8461'/></Cube></Cube></gesmes:Envelope>"""
datum, k = K.lees(XML)
check("datum en koersen gelezen", datum == "2026-10-30" and k == {"USD": 1.0812, "GBP": 0.8461}, str(k))
check("onleesbaar geeft niets", K.lees("geen xml") == (None, {}))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
