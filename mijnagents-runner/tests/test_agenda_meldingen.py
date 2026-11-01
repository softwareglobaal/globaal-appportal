"""Grendel op de meldingen van De Agendawacht (T-0120, meting 01-10 tot 01-11-2026, groep agenda).

- AG-3: twee titelredenen met hetzelfde begin geven twee sleutels, dus twee blijvende borditems;
- AG-4: 'zonder adres' kent dezelfde adresbronnen als de reistijd (vaste plek, locatie.globaal.be, projectmap); een KO
  zonder nummer geeft alleen de nummermelding; een afspraak zonder adres staat in hoogstens een nood; een B&S-bezoek
  geeft dezelfde uitkomst als voordien;

Verzonnen voorbeelden, geen echte namen. Draaien: python3 mijnagents-runner/tests/test_agenda_meldingen.py
"""
import atexit
import inspect
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

# --- AG-4: 'zonder adres' kent dezelfde bronnen als de reistijd, het nummer is een eigen melding, een afspraak een melding
import json  # noqa: E402
with open(ROOT / "werkwijze" / "agenda-taken.json", encoding="utf-8") as _bron:
    W.nummerlezer._master = lambda _r=json.load(_bron)["titelconventie"]: _r
_oud4 = (W.plek_zoeken, W.vaste_plek, W.projectadressen.index)
VASTE = {"proefbank": {"adres": "Proefstraat 1, 1000 Brussel"}}
W.plek_zoeken = lambda tekst: ((None, None) if "proefschool" not in tekst else ("Schoolweg 2, 1000 Brussel", "proefschool"))
W.vaste_plek = lambda titel: next(((w, v) for w, v in VASTE.items() if w in titel.lower()), (None, None))
W.projectadressen.index = lambda: {"2699": {"adres": "Projectlaan 3, 1000 Brussel"}}
try:
    MORGEN = (W.nu_lokaal().date() + W.timedelta(days=1)).isoformat()

    def afspraak(titel, uur="10:00", locatie=""):
        return {"kalender": W.WERKAGENDA, "id": f"id-{uur}", "titel": titel, "start": f"{MORGEN}T{uur}:00+01:00",
                "einde": f"{MORGEN}T{uur[:2]}:59:00+01:00", "locatie": locatie, "omschrijving": ""}

    vast = W.onvolledige_afspraken([afspraak("!! Mehdi: [HA-PB] kennismaking proefbank")], MORGEN)
    check("AG-4 een buitenafspraak met een vaste plek geeft geen adresmelding", vast == [], vast)
    plek = W.onvolledige_afspraken([afspraak("!! Mehdi: [HA-PB] ouderavond proefschool")], MORGEN)
    check("AG-4 een buitenafspraak met een plek uit locatie.globaal.be geeft geen adresmelding", plek == [], plek)
    proj = W.onvolledige_afspraken([afspraak("Mehdi: [HA-KB] 2699 - proefklant")], MORGEN)
    check("AG-4 een klantbezoek met een projectmap geeft geen adresmelding", proj == [], proj)
    geen = W.onvolledige_afspraken([afspraak("!! Mehdi: [HA-PB] proefprospect", "08:00")], MORGEN)
    check("AG-4 een buitenafspraak zonder enige bron blijft gemeld", len(geen) == 1 and "geen adres" in geen[0], geen)

    bs = afspraak("!! Mehdi: [HA-KB] 2698 - BS proefpersoon, Proefstraat 5, 3600 Proefstad", "13:00",
                  "Proefstraat 5, 3600 Proefstad")
    check("AG-4 B&S: een bezoek barsten en scheuren met adres geeft geen melding en geen adresvraag (zoals voordien)",
          W.onvolledige_afspraken([bs], MORGEN) == [] and W._adresvragen([bs]) == [])
    bs_zonder = dict(bs, locatie="")
    check("AG-4 B&S: zonder adresveld en zonder projectmap blijft het bezoek gemeld (zoals voordien)",
          len(W.onvolledige_afspraken([bs_zonder], MORGEN)) == 1 and len(W._adresvragen([bs_zonder])) == 1)
    ko = W.onvolledige_afspraken([afspraak("Mehdi: [HA-KO] proefklant", "11:00", "https://zoom.example.test/j/1")], MORGEN)
    nood_ko = W.adres_noden({}, ko, set())
    check("AG-4 een KO zonder nummer geeft alleen de nummermelding",
          [n["tekst"] for n in nood_ko] == ["Klantafspraken zonder projectnummer in de titel: zet het nummer erin"], nood_ko)

    # Een afspraak van 08:00 zonder adres: de reistijd zegt 'geen adres in de agenda', de adresvraag kon geen VR zetten,
    # en 'zonder adres' ziet haar ook. Tot 01-11-2026 waren dat drie meldingen voor dezelfde afspraak.
    _start = f"{MORGEN}T08:00"
    zr = {"geen adres in de agenda": [f"{_start} !! Mehdi: [HA-PB] proefprospect"], "adres niet gevonden": []}
    drie = W.adres_noden(zr, geen, {_start})
    check("AG-4 een afspraak geeft een melding: de adresvraag gaat voor, de rest zwijgt", drie == [], drie)
    twee = W.adres_noden(zr, geen, set())
    check("AG-4 zonder adresvraag blijft de reden van de reistijd de enige melding",
          [n["tekst"] for n in twee] == ["Buitenafspraken zonder reistijd, reden: geen adres in de agenda"], twee)
    los = W.adres_noden({}, geen, set())
    check("AG-4 wat de reistijd niet zag, krijgt nog 'zonder adres'",
          [n["tekst"] for n in los] == ["Buitenafspraken zonder adres: zonder adres kan ik geen reistijd berekenen"], los)
    ander = W.adres_noden({"rit zonder afspraak": [f"{MORGEN}T16:00 Reistijd: proef: rit zonder afspraak"]}, [], {_start})
    check("AG-4 een andere reden van de reistijd blijft gewoon gemeld",
          [n["tekst"] for n in ander] == ["Buitenafspraken zonder reistijd, reden: rit zonder afspraak"], ander)

    gevraagd = set()
    W.adres_vraag_noden([afspraak("!! Mehdi: [HA-PB] proefprospect", "08:00")], starts=gevraagd)
    check("AG-4 adres_vraag_noden geeft de starttijd door van elke adresvraag die een nood werd", gevraagd == {_start}, gevraagd)
finally:
    W.plek_zoeken, W.vaste_plek, W.projectadressen.index = _oud4
RONDE = inspect.getsource(W._ronde)
check("AG-4 de ronde meldt nummer, adres en reistijd via adres_noden, na de adresvragen",
      RONDE.index("noden.extend(adres_noden(zonder_rit, onvolledig, gevraagd))")
      > RONDE.index("adres_vraag_noden(rit_items, niet_op_kaart=niet_op_kaart, starts=gevraagd)")
      and "Buitenafspraken zonder reistijd, reden" not in RONDE and "Buitenafspraken zonder adres" not in RONDE)

print(f"agenda-meldingen: {ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
