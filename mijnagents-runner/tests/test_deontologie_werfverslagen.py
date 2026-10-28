"""Grendel op de toets van werfverslagen door De Deontologiewacht (opdrachtkaart v0.3, stap 6).

Alleen verzonnen verslagen en verzonnen namen. Een gewoon verslag moet groen kunnen zijn; elke regel wordt daarna apart
uitgelokt. Rood kan alleen uit D1 (de enige harde regel voor een werfverslag).

Draaien: python3 mijnagents-runner/tests/test_deontologie_werfverslagen.py
"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deontologie import register as R  # noqa: E402
from deontologie import verslag as V  # noqa: E402
from deontologie import werfverslagen as W  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


ARCHITECTEN = ["Ada Verzonnen", "Bert Bedacht"]
VANDAAG = date.fromisoformat(R.laad()["stand"]) + timedelta(days=1)
GEWOON = W.Werfverslag(
    "Werfbezoek bij de ruwbouw. De funderingen liggen volgens plan. De wapening is nagekeken. Volgende bezoek bij de "
    "dakwerken.", opgesteld_door="Ada Verzonnen", bezocht_door=("Ada Verzonnen",))


def toets(v, architecten=ARCHITECTEN):
    return {b.code: b for b in W.toets_werfverslag(v, architecten)}


def kleur(v, architecten=ARCHITECTEN):
    return V.maak("werfverslag", W.toets_werfverslag(v, architecten), vandaag=VANDAAG, elders=W.ELDERS)


def met(tekst=None, **kw):
    velden = dict(tekst=GEWOON.tekst, opgesteld_door=GEWOON.opgesteld_door, bezocht_door=GEWOON.bezocht_door, eerste=False)
    if tekst is not None:
        velden["tekst"] = tekst
    velden.update(kw)
    return W.Werfverslag(**velden)


print("Een gewoon verslag")
u = toets(GEWOON)
check("alle regels in orde", all(b.uitkomst == V.SLAAGT for b in u.values()), {c: b.toelichting for c, b in u.items()})
v = kleur(GEWOON)
check("een gewoon verslag is groen en vertrekt zonder klik", v.kleur == V.GROEN, v.markdown())
check("C4 staat apart als dossierregel", "C4" not in {p.code for p in v.punten} and "C4" in v.markdown())
V.OORDEEL_IN_ORDE_IS_GROEN = False
check("letterlijk volgens de ontwerplezing is het oranje", kleur(GEWOON).kleur == V.ORANJE)
V.OORDEEL_IN_ORDE_IS_GROEN = True

print("D1, de harde regel")
f = toets(met(GEWOON.tekst + " De opdrachtgever vraagt meerwerk: een extra dakkapel."))
check("meerwerk zonder addendum faalt", f["D1"].uitkomst == V.FAALT)
check("en wordt rood in het verslag", kleur(met(GEWOON.tekst + " Meerwerk: een extra dakkapel.")).kleur == V.ROOD)
f = toets(met(GEWOON.tekst + " Meerwerk: een extra dakkapel. Een addendum met de meerprijs van 4.000 euro volgt ter ondertekening."))
check("meerwerk met een addendum en de meerprijs slaagt", f["D1"].uitkomst == V.SLAAGT)
f = toets(met(GEWOON.tekst + " Het raam in de keuken is gewijzigd."))
check("een gewone wijziging is onbekend, niet rood", f["D1"].uitkomst == V.ONBEKEND)

print("Wie schreef en wie bezocht")
check("zonder lijst van architecten is C1 onbekend", toets(GEWOON, None)["C1"].uitkomst == V.ONBEKEND)
f = toets(met(opgesteld_door="Carla Medewerker", bezocht_door=("Carla Medewerker",)))
check("een bezoek door een niet-architect faalt C1", f["C1"].uitkomst == V.FAALT)
check("de naam staat niet in de toelichting", "Carla" not in f["C1"].toelichting)
check("C1 blijft oranje, nooit rood", kleur(met(opgesteld_door="Carla Medewerker")).kleur == V.ORANJE)
check("hoofdletters in de naam tellen niet", toets(met(opgesteld_door="ada verzonnen"))["C1"].uitkomst == V.SLAAGT)
instructie = GEWOON.tekst + " De aannemer moet de dakgoot herstellen voor vrijdag."
check("instructies van een architect zijn in orde", toets(met(instructie))["F1"].uitkomst == V.SLAAGT)
check("instructies van een niet-architect falen F1",
      toets(met(instructie, opgesteld_door="Carla Medewerker"))["F1"].uitkomst == V.FAALT)

print("Werfbord, budget en confraters")
check("een eerste verslag zonder werfbord faalt C3", toets(met(eerste=True))["C3"].uitkomst == V.FAALT)
check("een eerste verslag met werfbord slaagt",
      toets(met(GEWOON.tekst + " Het werfbord staat aan de straat.", eerste=True))["C3"].uitkomst == V.SLAAGT)
f = toets(met(GEWOON.tekst + " De kosten gaan 12 procent boven het budget."))
check("een overschrijding zonder melding faalt D3", f["D3"].uitkomst == V.FAALT)
check("en vraagt naar de verzekering (D5)", f["D5"].uitkomst == V.ONBEKEND)
f = toets(met(GEWOON.tekst + " De kosten gaan boven het budget; de opdrachtgever werd verwittigd per mail."))
check("een overschrijding met melding slaagt D3", f["D3"].uitkomst == V.SLAAGT)
f = toets(met(GEWOON.tekst + " De vorige architect heeft de trap slecht getekend."))
check("een uitspraak over een confrater faalt G4", f["G4"].uitkomst == V.FAALT)
check("alle oordeelsfouten samen blijven oranje",
      kleur(met(GEWOON.tekst + " De vorige architect tekende slecht. Kosten boven het budget.",
                opgesteld_door="Carla Medewerker", eerste=True)).kleur == V.ORANJE)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
