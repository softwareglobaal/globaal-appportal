"""Grendel op de meldingen van De Agendawacht (T-0120, meting 01-10 tot 01-11-2026, groep agenda).

- AG-3: twee titelredenen met hetzelfde begin geven twee sleutels, dus twee blijvende borditems;

Verzonnen voorbeelden, geen echte namen. Draaien: python3 mijnagents-runner/tests/test_agenda_meldingen.py
"""
import atexit
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen"), str(ROOT / "planning")]
os.environ["BELLEN_UIT"] = "1"
PROEF_HOME = tempfile.TemporaryDirectory(prefix="agenda-meldingen-proef-")
atexit.register(PROEF_HOME.cleanup)
os.environ["HOME"] = PROEF_HOME.name
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(PROEF_HOME.name, "agenda-whatsapp.json"))
import organisatie as ORGANISATIE  # noqa: E402
ORGANISATIE.firmas = lambda maximum_uren=24: [{"code": "HARC", "code_contact": "HA", "code_agenda": "HA",
                                                "naam": "H-Architects", "land": "BE", "actief": True}]
import agenda_wacht as W  # noqa: E402

BRON = (ROOT / "agenda_wacht.py").read_text(encoding="utf-8")
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print("ok   " + naam)
    else:
        fout += 1
        print("FOUT " + naam + (f" ({extra})" if extra else ""))


# --- AG-3: sleutelbotsing bij titelsignalen
DAG = "2026-10-29"
A = "geen firmacode, wellicht [AA]"
B = "geen firmacode, wellicht [BB]"
check("AG-3 de oude sleutel botste: hetzelfde begin van twintig tekens", f"agenda-titel-{A[:20]}:{DAG}" == f"agenda-titel-{B[:20]}:{DAG}")
check("AG-3 twee redenen met hetzelfde begin geven twee sleutels", W.titel_uniek(A, DAG) != W.titel_uniek(B, DAG),
      f"{W.titel_uniek(A, DAG)} {W.titel_uniek(B, DAG)}")
check("AG-3 dezelfde reden op dezelfde dag geeft dezelfde sleutel (geen nieuw item per ronde)",
      W.titel_uniek(A, DAG) == W.titel_uniek(A, DAG) and W.titel_uniek(A, DAG) != W.titel_uniek(A, "2026-10-30"))
check("AG-3 de sleutel eindigt op de dag (de wachtenpagina vindt hem op ':<dag>')", W.titel_uniek(A, DAG).endswith(f":{DAG}"))
check("AG-3 de ronde gebruikt titel_uniek voor de titelsignalen",
      '"uniek": titel_uniek(reden, vandaag)' in BRON and 'f"agenda-titel-{reden[:20]}:{vandaag}"' not in BRON)

print(f"agenda-meldingen: {ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
