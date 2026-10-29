"""Grendel FR-212 (29-10-2026): 'VR Mehdi en Tom' en 'VR Mehdi; Tom, Aqib' kregen de vraag 'zeg voor welke firma en
welke klant', terwijl organisatie.globaal.be zegt dat Tom en Aqib voor TKN-Buro werken. Zonder netwerk en sleutels.

Bewijst: alleen gekende collega's na 'Mehdi' (met of zonder dubbele punt, ';' scheidt ook) en een firma die ze allemaal
delen geven intern overleg van die firma; een onbekende naam, een klant, een buitenafspraak, een adres of collega's van
verschillende firma's niet; dan noemt de vraag per collega de firma's in plaats van de algemene vraag.
"""
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W     # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def persoon(voornaam, naam, diensten):
    return {"voornaam": voornaam, "naam": naam, "email": voornaam.lower() + "@globaal.be",
            "diensten_voor": diensten, "in_dienst": True, "afdeling": "", "firma": ""}


COLLEGAS = [persoon("Tom", "Tom (P-Engineering)", ["TKNB"]), persoon("Aqib", "Aqib Khan", ["TKNB"]),
            persoon("Leen", "Leen Peeters", ["HARC"])]
_oud = W.organisatie.collegas
W.organisatie.collegas = lambda *a, **k: COLLEGAS


def onderzoek(titel, **extra):
    return W.titel_uit_onderzoek({"titel": titel, "start": "2026-10-30T14:00:00+01:00", **extra})[0]


try:
    check("'VR Mehdi en Tom' wordt intern overleg van TKN-Buro",
          onderzoek("VR Mehdi en Tom") == "Mehdi & Tom: [TK-IN] overleg", onderzoek("VR Mehdi en Tom"))
    check("'VR Mehdi; Tom, Aqib' wordt intern overleg met beide namen",
          onderzoek("VR Mehdi; Tom, Aqib") == "Mehdi, Tom & Aqib: [TK-IN] overleg", onderzoek("VR Mehdi; Tom, Aqib"))
    check("het onderwerp na de dubbele punt blijft staan",
          onderzoek("Mehdi & Tom: planning engineering") == "Mehdi & Tom: [TK-IN] Planning engineering")
    check("een online link telt niet als adres",
          onderzoek("Mehdi en Tom", locatie="https://zoom.us/j/1") == "Mehdi & Tom: [TK-IN] overleg")
    check("een onbekende naam erbij: geen titel, de agent vraagt",
          onderzoek("VR Mehdi en Tom en Jan") is None and onderzoek("Mehdi en Jan Peeters") is None)
    check("'Mehdi: planning' heeft geen namen en blijft een vraag", onderzoek("Mehdi: planning") is None)
    check("collega's van verschillende firma's: geen titel", onderzoek("Mehdi, Tom en Leen") is None)
    check("buitenafspraak of fysiek adres: geen titel",
          onderzoek("!! Mehdi en Tom") is None and onderzoek("Mehdi en Tom", locatie="Kerkstraat 1, 2000 Antwerpen") is None)

    _a = {"titel": "VR Mehdi en Tom", "start": "2026-10-30T14:00:00+01:00"}
    _nieuw = W.titel_aanvulling(_a, {})[0]
    check("de aanvulroute neemt de titel zonder VR over en de schrijfgrendel laat het onderzoek door",
          _nieuw == "Mehdi & Tom: [TK-IN] overleg" and W.canoniek(_nieuw, False) == _nieuw
          and W._titel_patch_reden({**_a, "deelnemers": [], "maker": W.WERKAGENDA, "omschrijving": "",
                                    "kalender": W.WERKAGENDA}, _nieuw, uit_onderzoek=True) == "", _nieuw)

    nu = datetime.fromisoformat("2026-10-29T10:00:00+01:00")
    start = (nu + timedelta(hours=28)).isoformat()

    def vraag(titel):
        a = {"id": "x1", "titel": titel, "start": start, "einde": start, "kalender": W.WERKAGENDA}
        try:
            uit = W._vastgelopen([a], nu=nu)
        except Exception as e:  # noqa: BLE001
            return f"fout {type(e).__name__}: {e}"
        return next((t for k, t, _ in uit if k == "x1:firma"), "")

    v = vraag("VR Mehdi, Tom en Leen")
    check("de vraag noemt per collega de firma en vraagt alleen de firma",
          "Tom werkt voor TKNB" in v and "Leen werkt voor HARC" in v and "welke klant" not in v, v)
    v = vraag("VR Mehdi en Jan")
    check("zonder gekende collega's blijft de algemene vraag", "zeg voor welke firma en welke klant" in v, v)
finally:
    W.organisatie.collegas = _oud

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
