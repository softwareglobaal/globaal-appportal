"""Grendel: een dossier buiten het werfapp-bereik geeft een nood met het beheercommando, geen stille fout.

Gebeurd op 22-10-2026 met dossier 2513: de agenda liet het dossier volgen, de werfapp weigerde met
403 project_buiten_bereik, en het logboek toonde alleen een vage fout; niemand wist dat het bereik van de
servicesleutel verbreed moest worden. Deze toets faalt zodra die nood of het commando erin verdwijnt, of
zodra een andere registerfout ten onrechte als bereikprobleem gemeld wordt.
"""
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import werfverslag_voorbereider as V  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


nood = V.buiten_bereik_nood("2513", RuntimeError("werfregister 403 project_buiten_bereik: project buiten het bereik van deze service"))
check("nood bij project_buiten_bereik", nood is not None)
check("nood gaat naar claude-code", nood and nood["wie"] == "claude-code")
check("nood noemt het dossier", nood and "Dossier 2513" in nood["tekst"])
check("nood bevat het beheercommando met het dossier", nood and "werfbezoek-service bereik" in nood["tekst"]
      and "--toevoegen h-architects:2513" in nood["tekst"])
check("beide services in het commando", nood and "--service werf_schrijver" in nood["tekst"] and "--service dashboard" in nood["tekst"])
check("geen nood bij een andere registerfout",
      V.buiten_bereik_nood("2513", RuntimeError("werfregister niet bereikbaar; geen nieuwe modelaanroep toegestaan")) is None)
check("geen nood bij een dubbel bezoek",
      V.buiten_bereik_nood("2513", RuntimeError("meerdere werfapp-bezoeken met hetzelfde project en nummer")) is None)
print(f"{ok} ok, {fout} fout")
sys.exit(1 if fout else 0)
