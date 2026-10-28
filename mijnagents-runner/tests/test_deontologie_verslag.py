"""Grendel op het toetsverslag en de kleuren van De Deontologiewacht (opdrachtkaart v0.3, stap 3).

Alleen verzonnen documenten: de bevindingen hieronder horen bij geen enkel echt contract. Elke kleurregel van de
ontwerplezing (driehoeksoverleg 27-10-2026, voorwaarden 2 en 5) wordt hier uitgelokt, ook de gevallen die niet mogen:
rood uit een oordeel, groen uit een ontbrekende toets, rood met een verouderde of gewijzigde bibliotheek.

Draaien: python3 mijnagents-runner/tests/test_deontologie_verslag.py
"""
import copy
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


def fout_bij(f):
    try:
        f()
    except ValueError:
        return True
    return False


REG = R.laad()
VANDAAG = date.fromisoformat(REG["stand"]) + timedelta(days=1)
B = V.Bevinding


def punt(verslag, code):
    return next(p for p in verslag.punten if p.code == code)


print("Kleuren")
v = V.maak("contract", [
    B("B1", V.FAALT, "artikel 1", "Partijen ondertekenen deze overeenkomst voor de opdracht begint."),
    B("B2", V.SLAAGT, "artikel 2"),
    B("B3", V.ONBEKEND, toelichting="de bijlage ontbreekt"),
    B("A1", V.FAALT, "artikel 7"),
    B("A2", V.SLAAGT),
], vandaag=VANDAAG)
check("een harde regel die faalt is rood", punt(v, "B1").kleur == V.ROOD)
check("een harde regel die slaagt is groen", punt(v, "B2").kleur == V.GROEN)
check("een harde regel zonder gegevens is oranje", punt(v, "B3").kleur == V.ORANJE)
check("een oordeel dat faalt is hoogstens oranje", punt(v, "A1").kleur == V.ORANJE)
check("een oordeel dat slaagt is groen (keuze 28-10-2026)", punt(v, "A2").kleur == V.GROEN)
check("een regel zonder uitkomst staat er als niet getoetst, oranje",
      punt(v, "B4").kleur == V.ORANJE and punt(v, "B4").uitkomst == V.NIET_GETOETST)
check("elke regel voor deze soort heeft een punt",
      {p.code for p in v.punten} == {r["code"] for r in R.regels("contract", REG)})
check("de totale kleur is de ergste", v.kleur == V.ROOD)
check("geen waarschuwing met een verse, kloppende bibliotheek", v.waarschuwingen == [])

alles_hard = [B(r["code"], V.SLAAGT) for r in R.regels("contract", REG)]
v2 = V.maak("contract", alles_hard, vandaag=VANDAAG)
check("alles geslaagd is groen", v2.kleur == V.GROEN)
V.OORDEEL_IN_ORDE_IS_GROEN = False
v3 = V.maak("contract", alles_hard, vandaag=VANDAAG)
check("letterlijk volgens de ontwerplezing blijft alles geslaagd oranje",
      v3.kleur == V.ORANJE and punt(v3, "A2").kleur == V.ORANJE and punt(v3, "B1").kleur == V.GROEN)
V.OORDEEL_IN_ORDE_IS_GROEN = True
check("zonder bevindingen is niets groen", all(p.kleur != V.GROEN for p in V.maak("werfverslag", [], vandaag=VANDAAG).punten))

print("Bibliotheek")
oud = V.maak("contract", [B("B1", V.FAALT), B("B2", V.SLAAGT)],
             vandaag=VANDAAG + timedelta(days=V.BIBLIOTHEEK_MAX_DAGEN + 1))
check("een bibliotheek ouder dan 45 dagen geeft geen rood", all(p.kleur == V.ORANJE for p in oud.punten))
check("en zegt waarom", any("45 dagen" in w for w in oud.waarschuwingen))
grens = V.maak("contract", [B("B1", V.FAALT)], vandaag=VANDAAG - timedelta(days=1) + timedelta(days=V.BIBLIOTHEEK_MAX_DAGEN))
check("op dag 45 telt rood nog", punt(grens, "B1").kleur == V.ROOD)

with tempfile.TemporaryDirectory() as tmp:
    shutil.copytree(R.HIER / "bronnen", Path(tmp) / "bronnen")
    bron = Path(tmp) / REG["bronnen"]["RBP2022"]["bestand"]
    bron.write_text(bron.read_text(encoding="utf-8") + "\nverzonnen toevoeging\n", encoding="utf-8")
    gewijzigd = V.maak("contract", [B("B1", V.FAALT)], vandaag=VANDAAG, basis=tmp)
check("een bron met een andere sha256 geeft geen rood", all(p.kleur == V.ORANJE for p in gewijzigd.punten))
check("en zegt dat het register niet door de controle komt", any("controle" in w for w in gewijzigd.waarschuwingen))
zonder_stand = copy.deepcopy(REG)
zonder_stand["stand"] = ""
check("een bibliotheek zonder datum geeft geen rood",
      all(p.kleur == V.ORANJE for p in V.maak("contract", [B("B1", V.FAALT)], register=zonder_stand, vandaag=VANDAAG).punten))

print("Verslag")
tekst = v.markdown()
check("het verslag zegt dat het geen juridisch advies is", V.VOORBEHOUD in tekst)
check("het verslag noemt bron, registerversie en datum van de bibliotheek",
      "RBP2022" in tekst and f"register {REG['versie']}" in tekst and REG["stand"] in tekst)
check("rood staat bovenaan", tekst.index("- ROOD") < tekst.index("- ORANJE"))
check("een rood punt draagt artikel, plaats en voorstel",
      "art. " in tekst and "Plaats: artikel 1" in tekst and "Voorstel: Partijen ondertekenen" in tekst)
check("zonder eigen voorstel staat de toets van het register er", "Voorstel: " + punt(v, "B4").voorstel in tekst
      and punt(v, "B4").voorstel)
check("de reden bij ontbrekende gegevens staat erbij", "de bijlage ontbreekt" in tekst)

print("Ongeldige invoer")
check("een regel die niet voor de soort geldt", fout_bij(lambda: V.maak("werfverslag", [B("B1", V.SLAAGT)], vandaag=VANDAAG)))
check("een onbekende regel", fout_bij(lambda: V.maak("contract", [B("Z9", V.SLAAGT)], vandaag=VANDAAG)))
check("een onbekende uitkomst", fout_bij(lambda: V.maak("contract", [B("B1", "ok")], vandaag=VANDAAG)))
check("twee uitkomsten voor dezelfde regel",
      fout_bij(lambda: V.maak("contract", [B("B1", V.SLAAGT), B("B1", V.FAALT)], vandaag=VANDAAG)))
check("een onbekende documentsoort", fout_bij(lambda: V.maak("brief", [], vandaag=VANDAAG)))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
