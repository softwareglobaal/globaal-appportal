"""Grendels op De Fathomwacht uit T-0120 (meting 01-10 tot 01-11-2026, overleg X1 tot X9).

- FATHOM-7: een archiefmap met "herkenning": null (de 1960 mappen van fathom_haal_alles.py) breekt de ronde niet meer
  af (01-10-2026: beide rondes AttributeError); het gesprek is dan privé, de veilige kant, zonder naam of onderwerp.

Geen netwerk en geen taalmodel: Fathom en het bord zijn nagebootst (fathom_ronde uit test_bord_lees.py), elk gesprek
staat al in het archief, dus herkent de ronde niets opnieuw. Alle namen en adressen zijn verzonnen.
Draaien: python3 mijnagents-runner/tests/test_fathom_wacht.py
"""
import io
import os
import sys
import tempfile
from contextlib import redirect_stderr

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from test_bord_lees import (MEHDI, WW_FATHOM, BordNabootsing, _fathom_wacht, fathom_ronde,  # noqa: E402
                            gesprek)


# ------------------------------------------------------------------------------------------------ FATHOM-7 ---
def test_fathom7_herkenning_null_is_prive_en_breekt_niet():
    """FATHOM-7: .get("herkenning", {}) gaf None als de sleutel bestond met null; daarna herk.get(...) en een
    AttributeError, de hele ronde fout. Nu: privé bij twijfel, zonder naam of onderwerp in rij, item of werkverslag."""
    nb = BordNabootsing(werkwijze=WW_FATHOM, open_noden=[])
    g = gesprek(7101, "2026-10-20T07:10:00Z", "2026-10-20T07:41:00Z", door=MEHDI, titel="Proefgesprek Zonnedak")
    gezet, scherm, _ = fathom_ronde(nb, [(g, None)])
    assert nb.statussen()[-1]["status"] == "waakt", nb.statussen()[-1]
    rij = gezet["/api/gesprekken"][0]["rijen"][0]
    assert rij["prive"] is True and rij["personen"] == "" and rij["thema"] == "", rij
    item = gezet["/api/klaarzet"][0]["items"][0]
    assert "privégesprek, 31 min" in item["titel"] and item["inhoud"].get("prive") is True, item
    for tekst in (str(item), scherm):
        assert "Zonnedak" not in tekst, f"de titel in Fathom lekt bij een gesprek zonder herkenning: {tekst[:400]}"


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)
