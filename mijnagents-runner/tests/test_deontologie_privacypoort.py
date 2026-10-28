"""Grendel op de privacypoort van De Deontologiewacht (opdrachtkaart v0.3, stap 2; voorwaarde 4 van de ontwerplezing).

Alleen verzonnen documenten. De kanarie is een verzonnen naam uit een verzonnen nepdossier: hij mag nergens opduiken,
niet in wat naar Codex of Gemini gaat, niet in de doorgang, niet in een foutmelding, niet in wat er geprint of gelogd
wordt, en niet in een ander bestand van de Deontologiewacht.

Draaien: python3 mijnagents-runner/tests/test_deontologie_privacypoort.py
"""
import contextlib
import io
import logging
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deontologie import privacypoort as P  # noqa: E402
from deontologie import register as R  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  goed  {naam}")
    else:
        fout += 1
        print(f"  FOUT  {naam} {extra}")


KANARIE = "Ottoline Brabazon-Kerckhove"  # verzonnen, bestaat in geen enkel dossier
NEPDOSSIER = (f"Klacht van {KANARIE} tegen de architect, werf Verzonnenstraat 7. "
              "Mail van de advocaat over de zitting van de tuchtraad.")
PUBLIEKE_TEKST = "Art. 99 . Een verzonnen artikel dat alleen in deze test bestaat."


class Verzender:
    def __init__(self):
        self.gestuurd = []

    def __call__(self, ontvanger, tekst):
        self.gestuurd.append((ontvanger, tekst))


def zonder_kanarie(*dingen):
    return all(KANARIE.casefold() not in repr(d).casefold() for d in dingen)


uitvoer = io.StringIO()
logboek = io.StringIO()
logging.getLogger().addHandler(logging.StreamHandler(logboek))
logging.getLogger().setLevel(logging.DEBUG)
os.environ.pop(P.VERBODEN_ENV, None)

with contextlib.redirect_stdout(uitvoer), contextlib.redirect_stderr(uitvoer):
    # 1. Wat geen publiek stuk is, gaat niet door
    v = Verzender()
    gemengd = [
        P.Stuk(NEPDOSSIER),                       # geen label: privé
        P.Stuk(NEPDOSSIER, "PRIVE"),
        P.Stuk(NEPDOSSIER, "publiek"),            # tikfout in het label
        P.Stuk(NEPDOSSIER, "PUBLIC"),
        P.Stuk(NEPDOSSIER, " PUBLIEK"),
        NEPDOSSIER,                               # een gewone tekst
        {"tekst": NEPDOSSIER, "label": "PUBLIEK"},  # lijkt op een stuk maar is het niet
        P.Stuk(PUBLIEKE_TEKST, "PUBLIEK", "verzonnen artikel"),
    ]
    d1 = P.stuur(gemengd, "codex", v)
    # 2. Een publiek stuk met een verboden term gaat ook niet door
    v2 = Verzender()
    d2 = P.stuur([P.Stuk(f"Een publieke uitspraak over {KANARIE}.", "PUBLIEK")], "gemini", v2,
                 verboden=[KANARIE.upper()])
    v3 = Verzender()
    d3 = P.stuur([P.Stuk(f"Over {KANARIE.replace(' ', chr(10) + '  ')}.", "PUBLIEK")], "gemini", v3,
                 verboden=[KANARIE])
    # 3. De lijst buiten git via de omgeving
    with tempfile.TemporaryDirectory() as tmp:
        lijst = Path(tmp) / "verboden.txt"
        lijst.write_text(f"# namen uit het dossier\n{KANARIE}\n\n", encoding="utf-8")
        os.environ[P.VERBODEN_ENV] = str(lijst)
        v4 = Verzender()
        d4 = P.stuur([P.Stuk(f"Publiek, maar met {KANARIE}.", "PUBLIEK"),
                      P.Stuk(PUBLIEKE_TEKST, "PUBLIEK")], "codex", v4)
        os.environ[P.VERBODEN_ENV] = str(Path(tmp) / "bestaat-niet.txt")
        v5 = Verzender()
        try:
            P.stuur([P.Stuk(PUBLIEKE_TEKST, "PUBLIEK")], "codex", v5)
            fout5 = None
        except P.PoortGesloten as e:
            fout5 = e
        os.environ.pop(P.VERBODEN_ENV, None)
    # 4. Alleen codex en gemini
    v6 = Verzender()
    try:
        P.stuur([P.Stuk(NEPDOSSIER, "PUBLIEK")], "chatgpt", v6)
        fout6 = None
    except P.PoortGesloten as e:
        fout6 = e
    # 5. Niets door: de verzender wordt niet aangeroepen
    v7 = Verzender()
    d7 = P.stuur([P.Stuk(NEPDOSSIER)], "codex", v7)

check("alleen het publieke stuk gaat door", d1.doorgelaten == 1 and d1.tekst == PUBLIEKE_TEKST, repr(d1.tekst[:80]))
check("zonder label, privé, tikfout of ander label telt als privé", d1.tegengehouden.get(P.REDEN_PRIVE) == 5,
      str(d1.tegengehouden))
check("een gewone tekst of een dict telt niet als stuk", d1.tegengehouden.get(P.REDEN_GEEN_STUK) == 2,
      str(d1.tegengehouden))
check("de verzender kreeg precies een keer de publieke tekst", v.gestuurd == [("codex", PUBLIEKE_TEKST)])
check("een publiek stuk met een verboden term gaat niet door, ook met andere hoofdletters",
      d2.doorgelaten == 0 and d2.tegengehouden == {P.REDEN_VERBODEN: 1} and v2.gestuurd == [])
check("ook niet als de naam over twee regels gesplitst staat", d3.doorgelaten == 0 and v3.gestuurd == [])
check("de lijst buiten git werkt via DEONTOLOGIE_VERBODEN", d4.doorgelaten == 1 and d4.tekst == PUBLIEKE_TEKST
      and d4.tegengehouden == {P.REDEN_VERBODEN: 1})
check("een gezette maar onleesbare lijst houdt de poort dicht", fout5 is not None and v5.gestuurd == [])
check("een andere ontvanger dan codex of gemini krijgt niets", fout6 is not None and v6.gestuurd == [])
check("niets door: de verzender wordt niet aangeroepen", d7.doorgelaten == 0 and v7.gestuurd == [])

# De kanarie duikt nergens op
alles_gestuurd = v.gestuurd + v2.gestuurd + v3.gestuurd + v4.gestuurd + v5.gestuurd + v6.gestuurd + v7.gestuurd
check("de kanarie staat in niets wat naar Codex of Gemini ging", zonder_kanarie(alles_gestuurd))
check("de kanarie staat in geen enkele doorgang", zonder_kanarie(d1, d2, d3, d4, d7))
check("de kanarie staat in geen enkele foutmelding", zonder_kanarie(str(fout5), str(fout6)))
check("de kanarie staat niet in wat geprint of gelogd werd", zonder_kanarie(uitvoer.getvalue(), logboek.getvalue()))
dit_bestand = Path(__file__).resolve()
andere = [p for p in (R.HIER.parent).rglob("*") if p.is_file() and "deontologie" in p.name.lower() + str(p.parent)
          and p.resolve() != dit_bestand and "__pycache__" not in p.parts]
check("de kanarie staat in geen ander bestand van de Deontologiewacht",
      bool(andere) and all(KANARIE not in p.read_text(encoding="utf-8", errors="ignore") for p in andere),
      str([p.name for p in andere]))

# De bibliotheek is publiek, maar alleen met de juiste sha256
bib = P.uit_bibliotheek("RBP2022")
check("het reglement uit de bibliotheek is publiek", bib.label == P.PUBLIEK and "Art. 21 ." in bib.tekst)
check("het reglement gaat door de poort", P.poort([bib], "gemini", verboden=[]).doorgelaten == 1)
with tempfile.TemporaryDirectory() as tmp:
    reg = R.laad()
    pad = Path(tmp) / reg["bronnen"]["RBP2022"]["bestand"]
    pad.parent.mkdir(parents=True)
    pad.write_text(bib.tekst + "\nEen nieuwe stand.\n", encoding="utf-8")
    try:
        P.uit_bibliotheek("RBP2022", reg, basis=tmp)
        gesloten = False
    except P.PoortGesloten:
        gesloten = True
    check("een gewijzigde bron is niet meer publiek", gesloten)
try:
    P.uit_bibliotheek("BESTAAT_NIET")
    gesloten = False
except P.PoortGesloten:
    gesloten = True
check("een bron die niet in het register staat is niet publiek", gesloten)

# Accenten en onzichtbare tekens omzeilen de lijst niet
for naam, tekst in (("zonder accent", "Over Jose Muller."), ("in hoofdletters", "Over JOSÉ MÜLLER."),
                    ("met een onzichtbaar teken", "Over Jos\u00e9 M\u00fcl\u200bler."),
                    ("ontleed accent", "Over Jose\u0301 Mu\u0308ller.")):
    vx = Verzender()
    dx = P.stuur([P.Stuk(tekst, "PUBLIEK")], "codex", vx, verboden=["José Müller"])
    check(f"verboden term {naam} gaat niet door", dx.doorgelaten == 0 and not vx.gestuurd)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
