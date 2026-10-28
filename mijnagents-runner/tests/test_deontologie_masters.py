"""Grendel op de harde controles van De Deontologiewacht op contracten (opdrachtkaart v0.3, stap 4).

Alleen verzonnen contracten. Een goed contract moet door alle zes controles; elke controle wordt daarna apart doen
falen met een kleine wijziging, zodat een controle die altijd "slaagt" zeggen hier rood staat.

Draaien: python3 mijnagents-runner/tests/test_deontologie_masters.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deontologie import masters as M  # noqa: E402
from deontologie import register as R  # noqa: E402
from deontologie import verslag as V  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


GOED = """Architectuurovereenkomst
TUSSEN
Verzonnen Opdrachtgever, Nergensstraat 1
Hierna genoemd "de Opdrachtgever"
EN
Verzonnen Architectenbureau
Hierna genoemd "de Architect"
1. HET VOORWERP
De Opdrachtgever doet een beroep op de Architect.
3. HET BOUWPROJECT EN HET BOUWBUDGET
3.1. Het bouwproject
Een woning met ca. 150 m² oppervlakte. Het programma van het Bouwproject: drie slaapkamers.
3.2. Wijzigingen aan het bouwproject
Elke wijziging van het programma wordt vastgelegd in een Bijvoegsel, ondertekend door beide Partijen, dat de financiele weerslag op het Bouwbudget vermeldt.
3.4. Het bouwbudget
Het Bouwbudget wordt op 250.000,00 euro vooropgesteld.
4. TAKEN VAN DE ARCHITECT
4.2.1. Studiefase
Het verzamelen van de gegevens die nodig zijn voor het ontwerp;
De studie van de behoeften van de Opdrachtgever;
4.2.2. Fase voorontwerp
Het maken van de architecturale schetsen;
4.2.3. Fase aanvraag vergunning
Het opmaken van het administratief dossier om de Omgevingsvergunning aan te vragen.
4.2.4. Uitvoeringsfase
De opmaak van het uitvoeringsdossier voor de technieken.
Bijstand bij de keuze van aannemer(s) en de aanbesteding.
4.2.6. Controle op de uitvoering der werken
Controle op de uitvoering van de technieken.
4.3. Het nazicht van de vorderingsstaten en de facturen.
4.4. De bijstand bij de oplevering.
9. VERZEKERINGEN
De Architect is verzekerd bij Verzonnen Verzekeraar, polis nr. VZ123, ook voor de tienjarige aansprakelijkheid.
17. SLOT
Opgesteld te Nergenshuizen, op 1 januari 2026, in twee ondertekende exemplaren.
"""


def uitkomst(tekst):
    return {b.code: b for b in M.toets_contract(tekst)}


def zonder(tekst, *regels):
    for r in regels:
        assert r in tekst, r
        tekst = tekst.replace(r, "")
    return tekst


print("Een goed contract")
u = uitkomst(GOED)
HARD = ("B1", "B2", "B3", "B4", "B5", "D1")
check("alle zes harde regels en de verzekering slagen", all(u[c].uitkomst == V.SLAAGT for c in HARD + ("D4",)),
      {c: b.toelichting for c, b in u.items() if b.uitkomst != V.SLAAGT})
check("de controles leveren B1 tot B5, D1, D2 en D4", set(u) == set(HARD) | {"D2", "D4"})
check("D2 toont de prijs per m² zolang er geen referentie is", u["D2"].uitkomst == V.ONBEKEND and "per m²" in u["D2"].toelichting)

print("Elke controle kan falen")
f = uitkomst(zonder(GOED, "Opgesteld te Nergenshuizen, op 1 januari 2026, in twee ondertekende exemplaren."))
check("B1: zonder datum en ondertekening", f["B1"].uitkomst == V.FAALT)
f = uitkomst(zonder(GOED, "4.3. Het nazicht van de vorderingsstaten en de facturen.", "4.4. De bijstand bij de oplevering."))
check("B2: zonder bijstand bij de oplevering", f["B2"].uitkomst == V.FAALT and "oplevering" in f["B2"].toelichting)
f = uitkomst(GOED.replace("Controle op de uitvoering van de technieken.", "Periodiek nazicht."))
check("B3: uitvoeringsdossier voor de technieken zonder hun controle", f["B3"].uitkomst == V.FAALT)
f = uitkomst(GOED.replace("Bijstand bij de keuze van aannemer(s)", "Geen bijstand bij de keuze van aannemer(s)"))
check("B4: bijstand bij de keuze met een uitsluiting", f["B4"].uitkomst == V.FAALT)
f = uitkomst(zonder(GOED, "Bijstand bij de keuze van aannemer(s) en de aanbesteding."))
check("B4: zonder bijstand bij de keuze", f["B4"].uitkomst == V.FAALT)
f = uitkomst(GOED.replace("Het Bouwbudget wordt op 250.000,00 euro vooropgesteld.",
                          "Er wordt afgesproken het ontwerp eerst te tekenen en daarna te ramen."))
check("B5: geen begroting in euro", f["B5"].uitkomst == V.FAALT)
f = uitkomst(GOED.replace("Het Bouwbudget wordt op 250.000,00 euro vooropgesteld.",
                          "De Architect draagt geen budgetverantwoordelijkheid."))
check("B5: uitsluiting van budgetverantwoordelijkheid", f["B5"].uitkomst == V.FAALT)
f = uitkomst(GOED.replace("Het Bouwbudget wordt op 250.000,00 euro vooropgesteld.",
                          "Het project houdt rekening met 2.000,00 €/m²."))
check("B5: alleen een prijs per m² is onbekend, niet groen", f["B5"].uitkomst == V.ONBEKEND)
f = uitkomst(GOED.replace(", dat de financiele weerslag op het Bouwbudget vermeldt", "").replace(
    "in een Bijvoegsel", "in een verslag of via e-mail"))
check("D1: wijziging via mail zonder financiele weerslag", f["D1"].uitkomst == V.FAALT)

print("Ontkenningen en andere woorden (laatste toets 28-10-2026)")
f = uitkomst(GOED.replace("De opmaak van het uitvoeringsdossier voor de technieken.",
                          "De Architect maakt het uitvoeringsontwerp op.")
             .replace("4.2.6. Controle op de uitvoering der werken\nControle op de uitvoering van de technieken.\n", ""))
check("B3: een uitvoeringsontwerp zonder controle faalt", f["B3"].uitkomst == V.FAALT)
f = uitkomst(GOED.replace("4.2.6. Controle op de uitvoering der werken\nControle op de uitvoering van de technieken.",
                          "4.2.6. Werfopvolging\nDe Architect is niet belast met de controle op de uitvoering."))
check("B3: een uitgesloten controle is geen controle", f["B3"].uitkomst == V.FAALT)
f = uitkomst(GOED.replace("Bijstand bij de keuze van aannemer(s) en de aanbesteding.",
                          "4.2.5. Bijstand bij de keuze van de aannemer\nDeze taak valt buiten de opdracht van de Architect."))
check("B4: een uitsluiting op de regel onder de kop faalt", f["B4"].uitkomst == V.FAALT)
f = uitkomst(zonder(GOED, "4.3. Het nazicht van de vorderingsstaten en de facturen.",
                    "4.4. De bijstand bij de oplevering.") +
             "De kosten van de opmeting zijn niet inbegrepen. De aansprakelijkheid is beperkt tot het bedrag van de polis.\n")
check("B2: een uitsluiting over kosten maakt een ontbrekende taak niet oranje", f["B2"].uitkomst == V.FAALT)
check("een beperkte aansprakelijkheid is geen beperkte opdracht",
      not M.beperkte_opdracht("De aansprakelijkheid van de Architect is beperkt tot het bedrag van de polis."))
f = uitkomst(GOED + "De Architect waakt erover dat er geen budgetoverschrijding ontstaat.\n")
check("B5: geen budgetoverschrijding is geen uitsluiting van het budget", f["B5"].uitkomst == V.SLAAGT)
for datum in ("01/01/2026", "1-1-2026", "01.01.2026"):
    f = uitkomst(GOED.replace("op 1 januari 2026", f"op {datum}"))
    check(f"B1: een datum als {datum} telt", f["B1"].uitkomst == V.SLAAGT)

print("Beperkte opdracht")
beperkt = ("Overeenkomst\nTUSSEN\nVerzonnen\nde Opdrachtgever\nEN\nde Architect\n"
           "4. OPDRACHT\nDe opdracht is te beperken tot de studiefase.\nHet verzamelen van de gegevens die nodig zijn.\n"
           "8. SLOT\nOpgesteld te Nergenshuizen, op 1 januari 2026, in twee ondertekende exemplaren.\n")
u = uitkomst(beperkt)
check("B4, B5 en D1 zijn bij een beperkte opdracht onbekend, nooit rood",
      all(u[c].uitkomst == V.ONBEKEND for c in ("B4", "B5", "D1")))
check("B2 met een uitdrukkelijke beperking is onbekend", u["B2"].uitkomst == V.ONBEKEND)

print("Naar het verslag")
vandaag = date.fromisoformat(R.laad()["stand"]) + timedelta(days=1)
v = V.maak("contract", M.toets_contract(GOED.replace("in een Bijvoegsel", "via e-mail")), vandaag=vandaag)
check("een gefaalde harde regel wordt rood in het verslag", v.kleur == V.ROOD)
check("het voorstel staat in het verslag", "Bijvoegsel" in v.markdown())
check("een goed contract heeft groene harde punten en verder oranje",
      V.maak("contract", M.toets_contract(GOED), vandaag=vandaag).kleur == V.ORANJE)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
