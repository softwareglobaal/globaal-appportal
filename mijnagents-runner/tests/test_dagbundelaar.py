"""Grendels op De Dagbundelaar en de Zoom-dagregel (ontwerp regie-zoom v1.2: Z14, J14, I2; T31 tot T33).

Gemeten op 21-10-2026: 31 bundels voor h-architects hadden een datum als dossier (22 met de Zoom-dagregel, de rest met
gezondheid, coaching en mail), en de dagregels van vrijdag en zaterdag bleven liggen omdat De Dagbundelaar alleen op
werkdagen 'gisteren' bundelt. Deze test legt vast:

- T31: een item voor mehdi of met een datum als sleutel komt nooit in een bundel voor h-architects; de bundel 2531 voor
  h-architects bevat alleen zijn eigen transcript; het privétranscript voor mehdi krijgt een eigen bundel (J14, uniek
  bundel:<dag>:<sleutel>:mehdi); de dagregel staat als "Zoom: ..." in het Dagverslag; zoom-tekst en het ochtendbericht
  zitten nergens in;
- T32: op maandag komen de dagregels van vrijdag, zaterdag en een herziene van dinsdag mee onder "Nagekomen of herzien"
  en worden opgepakt; een van acht dagen oud niet;
- T33: zonder dagregel zegt het Dagverslag dat ze ontbreekt.

Geen netwerk: het bord is nagebootst (bord.call, bord.opgepakt) en de agent vangt zijn klaarzet en hartslag op.
Draaien: python3 mijnagents-runner/tests/test_dagbundelaar.py
"""
import io
import json
import os
import sys
from contextlib import redirect_stderr, redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
_argv, sys.argv = sys.argv, [sys.argv[0]]
import bord  # noqa: E402
import dagbundelaar as D  # noqa: E402
sys.argv = _argv


class NepBord:
    """Wat De Dagbundelaar leest (de hele bak, en apart de Zoom-dagregels op klaar) en wat hij schrijft."""

    def __init__(self, alle, zoom=None):
        self.alle = alle
        self.zoom = [it for it in (zoom if zoom is not None else alle) if it["soort"] == "zoom" and it["status"] == "klaar"]
        self.gelezen, self.opgepakt, self.bundels, self.harten = [], [], [], []

    def call(self, pad, payload=None, method=None):
        self.gelezen.append(pad)
        if pad.startswith("/api/klaarzet?") and "soort=zoom" in pad:
            assert "status=klaar" in pad, "de dagregels per soort lezen, op klaar"
            return {"items": [dict(it) for it in self.zoom]}
        if pad.startswith("/api/klaarzet?"):
            return {"items": [dict(it) for it in self.alle]}
        raise AssertionError("onverwachte bordoproep " + pad)


def bundelen(dag, nb):
    oud = (bord.call, bord.opgepakt, D.DAG)
    bord.call = nb.call
    bord.opgepakt = lambda kid, door: nb.opgepakt.append(kid)
    D.DAG = dag
    D.ag.klaarzet = lambda items: nb.bundels.extend(items) or {"nieuw": len(items)}
    D.ag.hartslag = lambda *a, **k: nb.harten.append(k)
    D.ag.log = lambda *a, **k: None
    D.ag.log_verstuur = lambda: None
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            D.main()
    finally:
        bord.call, bord.opgepakt, D.DAG = oud
        for naam in ("klaarzet", "hartslag", "log", "log_verstuur"):
            D.ag.__dict__.pop(naam, None)
    return nb


def item(kid, van, voor, soort, titel, sleutel="", inhoud=None, status="klaar", uniek=""):
    return {"id": kid, "van": van, "voor": voor, "soort": soort, "sleutel": sleutel, "titel": titel, "status": status,
            "uniek": uniek, "verwijzing": "", "inhoud": json.dumps(inhoud, ensure_ascii=False) if isinstance(inhoud, dict) else (inhoud or "")}


def dagregel(kid, dag, status="klaar", titel=None):
    return item(kid, "zoom-wacht", "mehdi", "zoom", titel or f"Zoom {dag[8:10]}-{dag[5:7]}: 3 gesprekken (2 met Fathom, 1 alleen in Zoom), 61 min; 4 chatgesprekken",
                inhoud={"datum": dag, "telling": "volledig"}, status=status, uniek=f"zoom:dag:{dag}")


DAG = "2026-10-20"
GEZONDHEID = item(1, "gezondheid-wacht", "mehdi", "gezondheid", "Gezondheid: hartslag en slaap", sleutel=DAG)
PRIVE = item(2, "fathom-wacht", "mehdi", "transcript", "2026-10-20T10:00 Fathom: Angela · persoonlijk · PRIVÉ", sleutel="2531",
             inhoud={"datum": DAG, "start": "10:00", "prive": True}, uniek="fathom:2")
WERK = item(3, "fathom-wacht", "h-architects", "transcript", "2026-10-20T11:00 Fathom: klant 2531 · werfoverleg", sleutel="2531",
            inhoud={"datum": DAG, "start": "11:00", "prive": False}, uniek="fathom:3")
ZOOMDAG = dagregel(4, DAG)
ZOOMTEKST = item(5, "zoom-wacht", "regisseur", "zoom-tekst", "2026-10-20 14:00 Zoom-gesprek, 12 min, alleen in Zoom",
                 inhoud={"datum": DAG, "start": "14:00", "stand": "tekst bewaard"}, uniek="zoom-tekst:u5")
OCHTEND = item(6, "regisseur", "mehdi", "ochtendbericht", "Ochtendbericht: drie beslissingen", inhoud={"datum": DAG, "punten": []},
               uniek=f"ochtendbericht:{DAG}")


def tekst_van(b):
    return b["titel"] + "\n" + b["inhoud"]


def test_t31_geen_lek_naar_de_afdeling():
    nb = bundelen(DAG, NepBord([GEZONDHEID, PRIVE, WERK, ZOOMDAG, ZOOMTEKST, OCHTEND]))
    per_uniek = {b["uniek"]: b for b in nb.bundels}
    afdeling = [b for b in nb.bundels if b["voor"] == "h-architects"]
    for b in afdeling:
        for weg in (GEZONDHEID, PRIVE, ZOOMDAG):
            assert weg["titel"] not in tekst_van(b), f"{weg['soort']} lekte naar h-architects: {b['uniek']}"
        assert b["sleutel"] and not D.DAG == b["sleutel"], "een bundel voor de afdeling heeft een dossier, geen datum"
    assert [b["uniek"] for b in afdeling] == [f"bundel:{DAG}:2531"], [b["uniek"] for b in afdeling]
    assert WERK["titel"] in per_uniek[f"bundel:{DAG}:2531"]["inhoud"] and PRIVE["titel"] not in per_uniek[f"bundel:{DAG}:2531"]["inhoud"]
    voor_mehdi = per_uniek[f"bundel:{DAG}:2531:mehdi"]
    assert voor_mehdi["voor"] == "mehdi" and voor_mehdi["sleutel"] == "2531" and PRIVE["titel"] in voor_mehdi["inhoud"], voor_mehdi
    zonder = per_uniek[f"bundel:{DAG}:(zonder dossier)"]
    assert zonder["voor"] == "mehdi" and GEZONDHEID["titel"] in zonder["inhoud"], "een datum als sleutel is geen dossier"
    verslag = per_uniek[f"dagverslag:{DAG}"]["inhoud"]
    assert f"Zoom: {ZOOMDAG['titel']}" in verslag, verslag
    for b in nb.bundels:
        assert ZOOMTEKST["titel"] not in tekst_van(b) and OCHTEND["titel"] not in tekst_van(b), b["uniek"]
        if b["uniek"] != f"dagverslag:{DAG}":
            assert ZOOMDAG["titel"] not in tekst_van(b), "de dagregel is een regel in het Dagverslag, geen bundel"
    assert sorted(nb.opgepakt) == [1, 2, 3, 4], nb.opgepakt
    assert any("soort=zoom" in p for p in nb.gelezen), "de dagregels worden apart gelezen (n=500 dekt geen week)"


def test_t32_maandag_neemt_het_weekend_en_herzieningen_mee():
    zondag = "2026-10-25"
    vrijdag, zaterdag = dagregel(11, "2026-10-23"), dagregel(12, "2026-10-24")
    dinsdag = dagregel(13, "2026-10-20", titel="Zoom 20-10: 4 gesprekken (3 met Fathom, 1 alleen in Zoom), 80 min; 4 chatgesprekken")
    oud = dagregel(14, "2026-10-18")
    vandaag = dagregel(15, zondag)
    opgepakt_al = dagregel(16, "2026-10-22", status="opgepakt")
    # De hele bak (n=500) bevat ze niet meer: alleen de lezing per soort vindt ze.
    nb = bundelen(zondag, NepBord([vandaag], zoom=[vrijdag, zaterdag, dinsdag, oud, vandaag, opgepakt_al]))
    verslag = next(b for b in nb.bundels if b["uniek"] == f"dagverslag:{zondag}")["inhoud"]
    assert f"Zoom: {vandaag['titel']}" in verslag
    blok = verslag.split("Nagekomen of herzien:", 1)
    assert len(blok) == 2, verslag
    for it in (vrijdag, zaterdag, dinsdag):
        assert f"- Zoom: {it['titel']}" in blok[1], it["titel"]
    assert oud["titel"] not in verslag and "18-10" not in verslag, "acht dagen oud valt buiten de terugblik"
    assert sorted(nb.opgepakt) == [11, 12, 13, 15], nb.opgepakt
    assert not any(b["voor"] == "h-architects" for b in nb.bundels)


def test_t33_geen_dagregel():
    nb = bundelen(DAG, NepBord([WERK]))
    verslag = next(b for b in nb.bundels if b["uniek"] == f"dagverslag:{DAG}")["inhoud"]
    assert "Zoom: dagregel ontbreekt (Zoomwacht niet klaar)" in verslag, verslag
    assert "Nagekomen of herzien" not in verslag


def test_oude_dagregel_met_datum_als_sleutel():
    """Een dagregel van voor versie 2 heeft de datum als sleutel. Ook die gaat naar het Dagverslag, nooit naar een bundel."""
    oud = dict(dagregel(21, DAG), sleutel=DAG)
    nb = bundelen(DAG, NepBord([oud, WERK]))
    assert not any(b["voor"] == "h-architects" and oud["titel"] in tekst_van(b) for b in nb.bundels)
    assert f"Zoom: {oud['titel']}" in next(b for b in nb.bundels if b["uniek"] == f"dagverslag:{DAG}")["inhoud"]


def test_bron_houdt_de_bestaande_grendels():
    """test_postvak.py en test_locatielezers.py lezen de bron van De Dagbundelaar; hun grendels blijven staan."""
    bron = open(os.path.join(RUNNER, "dagbundelaar.py"), encoding="utf-8").read()
    assert '"mail-regisseur" in (it.get("van"), it.get("voor"))' in bron
    assert "LC.dag_heeft_dagboek(DAG, items)" in bron and 'or it.get("soort") == "locatie"' not in bron
    assert "07:05 UTC" in bron and "gesprekken.lock" in bron, "Z14 punt 6: de docstring zegt wanneer hij draait"
    assert "\N{EM DASH}" not in bron and "\N{EN DASH}" not in bron


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)
