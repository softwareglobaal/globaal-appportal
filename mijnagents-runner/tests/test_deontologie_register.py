"""Grendel op het regelregister van De Deontologiewacht (opdrachtkaart v0.3, stap 1; driehoeksoverleg 27-10-2026, 3-0).

Het echte register moet zonder fouten door valideer(). Elke foutsoort die de grendel moet vangen, wordt hier met een
kleine wijziging aan een kopie van het register uitgelokt: een verzonnen citaat, een citaat bij het verkeerde artikel,
rood op een afgeleide of oordeelsregel, een gewijzigde bron, een punt zonder regel, een artikel zonder indeling. Een
grendel die alleen het goede geval test, bewijst niets.

Draaien: python3 mijnagents-runner/tests/test_deontologie_register.py
"""
import copy
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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


ECHT = R.laad()


def fouten_na(wijzig):
    reg = copy.deepcopy(ECHT)
    wijzig(reg)
    return R.valideer(reg)


def regel(reg, code):
    return next(r for r in reg["regels"] if r["code"] == code)


def vangt(naam, wijzig, stukje):
    gevonden = fouten_na(wijzig)
    check(naam, any(stukje in f for f in gevonden), str(gevonden))


# Het echte register
echte_fouten = R.valideer(ECHT)
check("het echte register heeft geen fouten", echte_fouten == [], str(echte_fouten))
bron = (R.HIER / ECHT["bronnen"]["RBP2022"]["bestand"]).read_text(encoding="utf-8")
delen = R.artikels(bron, 53)
check("de bron splitst in precies 53 artikels", len(delen) == 53, str(len(delen)))
check("artikel 21 begint bij zijn eigen kop en niet bij een verwijzing", delen["21"].startswith("Art. 21 . In toepassing"))
check("het laatste artikel stopt voor de ondertekening", "Handtekening" not in delen["53"] and "CLARINVAL" not in delen["53"])

# Wat Mehdi en het overleg vastlegden, blijft zo
check("B1 (schriftelijk contract) is HARD, LETTERLIJK en kan rood", regel(ECHT, "B1")["max_kleur"] == "rood"
      and regel(ECHT, "B1")["type"] == "HARD" and regel(ECHT, "B1")["status"] == "LETTERLIJK")
check("A1 (ereloon) is een afgeleid oordeel, hoogstens oranje: de ereloonhoogte beslist Mehdi",
      regel(ECHT, "A1")["status"] == "AFGELEID" and regel(ECHT, "A1")["max_kleur"] == "oranje")
for code in ("C1", "C4", "F1"):
    check(f"{code} staat niet letterlijk in het reglement en is dus hoogstens oranje",
          regel(ECHT, code)["status"] == "AFGELEID" and regel(ECHT, code)["max_kleur"] == "oranje")
check("elke rode regel is HARD en LETTERLIJK", all(r["type"] == "HARD" and r["status"] == "LETTERLIJK"
                                                    for r in ECHT["regels"] if r["max_kleur"] == "rood"))
check("de punten A tot F hebben elk een regel", all(any(r["punt"] == p for r in ECHT["regels"]) for p in "ABCDEF"))
check("regels('contract') geeft alleen contractregels", all("contract" in r["documenten"] for r in R.regels("contract"))
      and any(r["code"] == "B3" for r in R.regels("contract")))
check("regels('werfverslag') bevat de werfcontrole", {"C1", "C4"} <= {r["code"] for r in R.regels("werfverslag")})

# De grendel vangt elke foutsoort
vangt("een verzonnen citaat", lambda reg: regel(reg, "B1").update(
    citaat="Voor iedere opdracht volstaat een mondelinge afspraak met de bouwheer en de aannemer samen."),
    "staat niet letterlijk")
vangt("een echt citaat bij het verkeerde artikel", lambda reg: regel(reg, "B4").update(artikel="20"),
      "staat niet letterlijk")
vangt("een artikel dat niet bestaat", lambda reg: regel(reg, "B4").update(artikel="99"), "bestaat niet")
vangt("een te kort citaat", lambda reg: regel(reg, "B4").update(citaat="de aannemer"), "te kort")
vangt("rood op een afgeleide regel", lambda reg: regel(reg, "C1").update(max_kleur="rood", type="HARD"),
      "rood kan alleen bij HARD en LETTERLIJK")
vangt("rood op een oordeelsregel", lambda reg: regel(reg, "A2").update(max_kleur="rood"),
      "rood kan alleen bij HARD en LETTERLIJK")
vangt("een afgeleide regel zonder afleiding", lambda reg: regel(reg, "D2").pop("afleiding"), "zegt in afleiding")
vangt("een onbekende status", lambda reg: regel(reg, "B1").update(status="ONGEVEER"), "status moet")
vangt("een onbekend document", lambda reg: regel(reg, "B1").update(documenten=["factuur"]), "onbekende documenten")
vangt("een dubbele code", lambda reg: reg["regels"].append(copy.deepcopy(regel(reg, "B1"))), "meer dan een keer")
vangt("een code die niet bij het punt past", lambda reg: regel(reg, "B1").update(code="D9"), "letter van het punt")
vangt("een gedachtestreepje in de toets", lambda reg: regel(reg, "B1").update(toets="Een contract — schriftelijk."),
      "gedachtestreepje")
vangt("een punt zonder regel", lambda reg: reg.update(regels=[r for r in reg["regels"] if r["punt"] != "E"]),
      "punt E")
vangt("een artikel zonder indeling", lambda reg: reg.update(geen_toets=[g for g in reg["geen_toets"]
                                                                       if "17" not in g["artikels"]]), "17")
vangt("een artikel met een regel dat ook bij geen toets staat",
      lambda reg: reg["geen_toets"].append({"artikels": ["21"], "reden": "proef"}), "artikel 21: dubbel ingedeeld")
vangt("een regel op een artikel dat niet van toepassing is",
      lambda reg: reg["regels"].append(dict(copy.deepcopy(regel(reg, "G1")), code="G99", artikel="40",
                                            citaat="De architect die optreedt als vastgoedmakelaar-bemiddelaar moet "
                                                   "een derdenrekening openen.")),
      "artikel 40: dubbel ingedeeld")
vangt("een geen-toets zonder reden", lambda reg: reg["geen_toets"][0].update(reden=""), "reden ontbreekt")
vangt("een fout citaat in het toepassingsgebied",
      lambda reg: reg["toepassingsgebied"].update(citaat="Dit reglement geldt alleen voor werk binnen het monopolie."),
      "toepassingsgebied")

# Een gewijzigde bron laat de validatie falen tot iemand de citaten opnieuw nakijkt
with tempfile.TemporaryDirectory() as tmp:
    kopie = Path(tmp)
    shutil.copytree(R.HIER / "bronnen", kopie / "bronnen")
    pad = kopie / ECHT["bronnen"]["RBP2022"]["bestand"]
    pad.write_text(pad.read_text(encoding="utf-8") + "\nEen nieuwe stand.\n", encoding="utf-8")
    gevonden = R.valideer(copy.deepcopy(ECHT), basis=kopie)
    check("een gewijzigde bron faalt op de sha256", any("sha256 klopt niet" in f for f in gevonden), str(gevonden))
    pad.unlink()
    gevonden = R.valideer(copy.deepcopy(ECHT), basis=kopie)
    check("een ontbrekende bron faalt", any("ontbreekt" in f for f in gevonden), str(gevonden))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
