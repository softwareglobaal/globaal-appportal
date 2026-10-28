"""Grendel op de stempel van De Deontologiewacht (opdrachtkaart v0.3, stap 5).

Alleen verzonnen stukken en een testsleutel. Elke manier om langs de grendel te raken, wordt hier geprobeerd: geen
stempel, geen sleutel, een ander bestand, een vervallen stempel, een vervalste kleur, een bevestiging door iemand anders
dan Mehdi, een rood punt zonder reden.

Draaien: python3 mijnagents-runner/tests/test_deontologie_stempel.py
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deontologie import stempel as S  # noqa: E402
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


def dicht(f):
    try:
        f()
    except S.GrendelDicht:
        return True
    return False


SLEUTEL = "testsleutel-" + "x" * 40
ANDERE = "anderesleutel-" + "y" * 40
MEHDI = "bevestigsleutel-" + "m" * 40  # alleen in het bevestigscherm van Mehdi en in de apps die controleren
NU = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)
STUK = b"Verzonnen werfverslag nummer 1, Nergensstraat 1."


def verslag(kleur, rood=()):
    punten = [V.Punt(c, "verzonnen", "1", "rood", V.FAALT, "", "", "") for c in rood]
    punten.append(V.Punt("Z1", "verzonnen", "1", "groen" if kleur == "groen" else "oranje", V.SLAAGT, "", "", ""))
    return V.Verslag("werfverslag", kleur, punten, "RBP2022 (register 1.0)", "2026-10-27")


def mag(stuk, st, nu=NU, sleutel=SLEUTEL, bevestigsleutel=MEHDI):
    return S.controleer(stuk, st, sleutel=sleutel, nu=nu, bevestigsleutel=bevestigsleutel)


print("Groen")
groen = S.maak(STUK, verslag("groen"), sleutel=SLEUTEL, nu=NU)
check("een groen stuk met stempel vertrekt", mag(STUK, groen) == (True, ""))
check("zonder stempel vertrekt niets", mag(STUK, None)[0] is False and mag(STUK, {})[0] is False)
check("een ander bestand vertrekt niet", mag(STUK + b" ", groen) == (False, "het stuk is gewijzigd sinds de toets"))
check("een vervallen stempel vertrekt niet", mag(STUK, groen, nu=NU + timedelta(days=S.GELDIG_DAGEN))[0] is False)
check("op de laatste dag nog wel", mag(STUK, groen, nu=NU + timedelta(days=S.GELDIG_DAGEN) - timedelta(seconds=1))[0])
check("een stempel uit de toekomst vertrekt niet", mag(STUK, groen, nu=NU - timedelta(hours=1))[0] is False)

print("Sleutel en vervalsing")
check("zonder sleutel is de grendel dicht", mag(STUK, groen, sleutel="")[0] is False)
check("een te korte sleutel is ook dicht", mag(STUK, groen, sleutel="kort")[0] is False)
os.environ.pop(S.SLEUTEL_ENV, None)
check("ook als de omgeving geen sleutel heeft", S.controleer(STUK, groen, nu=NU)[0] is False)
check("een stempel met een andere sleutel is niet echt", mag(STUK, groen, sleutel=ANDERE)[0] is False)
rood = S.maak(STUK, verslag("rood", ["B1"]), sleutel=SLEUTEL, nu=NU)
vervalst = dict(rood, kleur="groen")
check("een rode stempel groen maken breekt de handtekening", mag(STUK, vervalst)[0] is False)
langer = dict(groen, vervalt=(NU + timedelta(days=365)).isoformat())
check("de vervaldatum verschuiven breekt de handtekening", mag(STUK, langer)[0] is False)
onleesbaar = {k: v for k, v in groen.items() if k != "handtekening"}
onleesbaar["gemaakt"] = "gisteren"
onleesbaar["handtekening"] = S._handtekening(onleesbaar, SLEUTEL.encode())
check("een echte maar onleesbare stempel vertrekt niet", mag(STUK, onleesbaar) == (False, "de stempel is onleesbaar"))
check("een handtekening met vreemde tekens sluit de grendel", mag(STUK, dict(groen, handtekening="é"))[0] is False
      and dicht(lambda: S.bevestig(dict(groen, handtekening="é"), "oranje", "mehdi", sleutel=SLEUTEL, bevestigsleutel=MEHDI)))
check("een stempel kan geen onbekende kleur krijgen", dicht(lambda: S.maak(STUK, verslag("paars"), sleutel=SLEUTEL)))

print("Kleur nagerekend")
groen_met_rood = V.Verslag("werfverslag", "groen", verslag("rood", ["D1"]).punten, "RBP2022 (register 1.0)", "2026-10-27")
check("een verslag dat groen zegt met een rood punt krijgt geen stempel",
      dicht(lambda: S.maak(STUK, groen_met_rood, sleutel=SLEUTEL, nu=NU)))
oranje_met_rood = V.Verslag("werfverslag", "oranje", groen_met_rood.punten, "RBP2022 (register 1.0)", "2026-10-27")
check("ook niet als het oranje zegt", dicht(lambda: S.maak(STUK, oranje_met_rood, sleutel=SLEUTEL, nu=NU)))
nagemaakt = dict(rood, kleur="groen")
nagemaakt["handtekening"] = S._handtekening(nagemaakt, SLEUTEL.encode())
check("een stempel met rode punten die niet rood is, vertrekt niet", mag(STUK, nagemaakt)[0] is False)

print("Oranje")
oranje = S.maak(STUK, verslag("oranje"), sleutel=SLEUTEL, nu=NU)
check("oranje vertrekt niet zonder Mehdi", mag(STUK, oranje)[0] is False)
check("een ander kan oranje niet laten vertrekken",
      dicht(lambda: S.bevestig(oranje, "oranje", "codex", "lijkt me goed", sleutel=SLEUTEL, bevestigsleutel=MEHDI)))
ok_oranje = S.bevestig(oranje, "oranje", "mehdi", sleutel=SLEUTEL, bevestigsleutel=MEHDI, nu=NU)
check("oranje met de bevestiging van Mehdi vertrekt", mag(STUK, ok_oranje) == (True, ""))
check("de oude stempel blijft ongewijzigd", "oranje" not in oranje["bevestigd"])
zelf = json.loads(json.dumps(oranje))
zelf["bevestigd"]["oranje"] = {"door": "mehdi", "reden": "", "ts": NU.isoformat()}
check("een zelf ingevulde bevestiging zonder handtekening telt niet", mag(STUK, zelf)[0] is False)
check("de Wacht zonder bevestigsleutel kan oranje niet laten vertrekken",
      dicht(lambda: S.bevestig(oranje, "oranje", "mehdi", sleutel=SLEUTEL, bevestigsleutel="")))
check("ook niet met de stempelsleutel als bevestigsleutel",
      dicht(lambda: S.bevestig(oranje, "oranje", "mehdi", sleutel=SLEUTEL, bevestigsleutel=SLEUTEL)))
wacht = json.loads(json.dumps(oranje))
wacht["bevestigd"]["oranje"] = {"door": "mehdi", "reden": "", "ts": NU.isoformat(), "teken": "0" * 64}
wacht["handtekening"] = S._handtekening(wacht, SLEUTEL.encode())
check("een bevestiging met alleen de stempelsleutel ondertekend vertrekt niet",
      mag(STUK, wacht) == (False, "een bevestiging is niet door Mehdi ondertekend"))
check("een bevestigde stempel controleren zonder bevestigsleutel vertrekt niet",
      mag(STUK, ok_oranje, bevestigsleutel="")[0] is False)

print("Rood")
rood2 = S.maak(STUK, verslag("rood", ["B1", "D1"]), sleutel=SLEUTEL, nu=NU)
check("rood vertrekt niet", mag(STUK, rood2)[0] is False)
check("een rood punt zonder reden kan niet vertrekken",
      dicht(lambda: S.bevestig(rood2, "B1", "mehdi", "  ", sleutel=SLEUTEL, bevestigsleutel=MEHDI)))
check("oranje bevestigen helpt niet bij rood", dicht(lambda: S.bevestig(rood2, "oranje", "mehdi", sleutel=SLEUTEL, bevestigsleutel=MEHDI)))
check("een punt dat niet rood is, kan niet bevestigd worden",
      dicht(lambda: S.bevestig(rood2, "Z1", "mehdi", "reden", sleutel=SLEUTEL, bevestigsleutel=MEHDI)))
een = S.bevestig(rood2, "B1", "mehdi", "klant tekent vandaag nog, verzonnen reden", sleutel=SLEUTEL,
                bevestigsleutel=MEHDI, nu=NU)
check("met een van de twee rode punten bevestigd vertrekt het nog niet", mag(STUK, een) == (False, "rood: D1 wacht op Mehdi"))
twee = S.bevestig(een, "D1", "mehdi", "addendum volgt, verzonnen reden", sleutel=SLEUTEL, bevestigsleutel=MEHDI,
                 nu=NU)
check("met elk rood punt bevestigd vertrekt het", mag(STUK, twee) == (True, ""))
check("de rode punten en hun reden blijven in de stempel",
      twee["rood"] == ["B1", "D1"] and twee["bevestigd"]["D1"]["reden"].startswith("addendum"))
check("een bevestiging op een vervalste stempel kan niet",
      dicht(lambda: S.bevestig(dict(rood2, rood=[]), "B1", "mehdi", "reden", sleutel=SLEUTEL,
                                bevestigsleutel=MEHDI)))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
