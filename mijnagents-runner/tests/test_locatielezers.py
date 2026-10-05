"""Grendels op alle lezers van locatiegegevens buiten de tegel (opdracht v1.4, 05-10-2026).

De onafhankelijke controle vond: De Plaudwacht las een telefoonplek van 30 september en miste
een nieuw autoverblijf; het bord telde oude telefoondagboeken en nul voor het nieuwe formaat;
De Archivaris gaf "geparkeerd: Thuis" door als plaats van Mehdi; De Dagbundelaar liet een oud
locatie-item een ontbrekend dagboek verbergen. Elke lezer gaat nu door koppelingen/locatiecontext.py
of de dag-API, met de startgrens.

De inventaris onderaan faalt zodra een bestand locatiegegevens leest zonder in de lijst te staan.

Nagebootste context; geen netwerk, geen bord.
Draaien: python3 mijnagents-runner/tests/test_locatielezers.py
"""
import ast
import json
import os
import re
import sys
from types import SimpleNamespace

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(HIER)
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import locatiecontext as LC  # noqa: E402

PROJECT = {"sleutel": "HARC:9999", "firma": "HARC", "nummer": "9999", "project_id": "uuid-9999",
           "link": "https://ha-projecten.globaal.be/project/9999", "adres": "Proefstraat 1"}


def context_van(dag, verblijven=(), kandidaten=()):
    return {"dag": dag, "bronbeleid": "1.0", "verblijven": list(verblijven), "kandidaten": list(kandidaten)}


def verblijf(dag, van="10:00", tot="11:00", positief=True, project=PROJECT, zekerheid="waarschijnlijk"):
    return {"bron": "auto", "rol": "auto", "positief": positief, "aankomst": f"{dag}T{van}:00+02:00",
            "vertrek": f"{dag}T{tot}:00+02:00", "zekerheid": zekerheid, "reden": "proef",
            "bewijs": "motor uit om 10:02", "project": project if positief else None,
            "kandidaten": None if positief else [{"firma": "HARC", "nummer": "9998"}, {"firma": "HARC", "nummer": "9999"}]}


class Tegel:
    """Vervangt /api/context; onthoudt wat gevraagd werd."""
    def __init__(self, per_dag):
        self.per_dag, self.gevraagd = per_dag, []

    def __call__(self, pad):
        self.gevraagd.append(pad)
        dag = pad.split("dag=")[-1][:10]
        if dag not in self.per_dag:
            raise OSError("geen context")
        return self.per_dag[dag]


def met_tegel(per_dag):
    LC._cache.clear()
    LC._haal = Tegel(per_dag)
    return LC._haal


def test_plaud_leest_geen_oude_telefooncontext_en_vindt_een_nieuw_autoverblijf():
    import plaud_wacht as P
    tegel = met_tegel({"2026-10-03": context_van("2026-10-03", [verblijf("2026-10-03")])})
    P.bord.call = lambda *a, **k: {"items": [
        {"soort": "locatie", "sleutel": "2026-09-30", "titel": "Locatielogboek 2026-09-30",
         "inhoud": "| 10:00 | 11:00 | 60 min | bezoek | OUDE_GSM_PLEK | |"}]}
    _, plek = P.context_op("2026-09-30T10:30")
    assert plek == "" and not tegel.gevraagd, (plek, tegel.gevraagd)
    _, plek = P.context_op("2026-10-03T10:30")
    assert plek.startswith("auto bij project HARC 9999") and "geen bewijs van persoonlijke aanwezigheid" in plek, plek


def test_archivaris_noemt_de_auto_en_bewaart_project_zekerheid_en_bewijs():
    import archivaris as A
    met_tegel({"2026-10-03": context_van("2026-10-03", [verblijf("2026-10-03")],
                                         [verblijf("2026-10-03", "12:00", "13:00", positief=False, zekerheid="onzeker")])})
    zin, data = A.locatie_op("2026-10-03", "10:30")
    assert zin.startswith("auto bij project HARC 9999"), zin
    assert data["rol"] == "auto" and data["zekerheid"] == "waarschijnlijk" and data["bewijs"] and data["project_id"], data
    assert "geen bewijs van persoonlijke aanwezigheid" in data["betekenis"]
    # Een onzekere kandidaat, Thuis, een rit of een meetgat geeft niets positiefs.
    assert A.locatie_op("2026-10-03", "12:30") == ("", None)
    assert A.locatie_op("2026-10-03", "15:00") == ("", None)
    assert A.locatie_op("2026-09-30", "10:30") == ("", None), "voor de grens"


def test_dagbundelaar_telt_alleen_een_dagboek_voor_precies_de_dag():
    oud = {"soort": "locatie", "van": "locatie-wacht", "sleutel": "2026-09-30", "titel": "Locatielogboek 2026-09-30"}
    juist = {"soort": "locatie", "van": "locatie-wacht", "sleutel": "2026-10-04", "titel": "Locatielogboek 2026-10-04"}
    assert not LC.dag_heeft_dagboek("2026-10-04", [oud])
    assert LC.dag_heeft_dagboek("2026-10-04", [oud, juist])
    assert not LC.dag_heeft_dagboek("2026-09-30", [oud]), "voor de grens bestaat geen dagboek"
    bron = open(os.path.join(HIER, "dagbundelaar.py"), encoding="utf-8").read()
    assert 'or it.get("soort") == "locatie"' not in bron, "elk locatie-item telde voor elke dag"
    assert "LC.dag_heeft_dagboek(DAG, items)" in bron


def test_dagbundelaar_meldt_een_ontbrekend_nieuw_dagboek_naast_een_oud_item():
    """De tegenproef van de controle, op de echte functie (uit de bron gehaald, geen bord)."""
    from collections import defaultdict
    bron = open(os.path.join(HIER, "dagbundelaar.py"), encoding="utf-8").read()
    boom = ast.parse(bron)
    knoop = next(n for n in boom.body if isinstance(n, ast.FunctionDef) and n.name == "main")
    harten = []
    ns = {"ag": SimpleNamespace(hartslag=lambda *a, **k: harten.append(k), klaarzet=lambda x: {"nieuw": 0},
                                log=lambda *a, **k: None, log_verstuur=lambda: None),
          "DAG": "2026-10-04", "NAAM": "proef", "json": json, "defaultdict": defaultdict, "LC": LC,
          "bord": SimpleNamespace(call=lambda *a, **k: {"items": [
              {"id": 1, "van": "locatie-wacht", "soort": "locatie", "sleutel": "2026-09-30",
               "titel": "Locatielogboek 2026-09-30", "inhoud": "oud", "status": "klaar"}]},
              opgepakt=lambda *a: None)}
    exec(compile(ast.Module(body=[knoop], type_ignores=[]), "dagbundelaar.py", "exec"), ns)
    ns["main"]()
    noden = [n["tekst"] for n in harten[-1]["nood"]]
    assert any("geen Locatiedagboek" in t for t in noden), noden


def test_het_bord_haalt_de_dagcijfers_uit_de_dag_api():
    bron = open(os.path.join(REPO, "mijnagents", "app.py"), encoding="utf-8").read()
    boom = ast.parse(bron)
    knoop = next(n for n in boom.body if isinstance(n, ast.FunctionDef) and n.name == "dagen_pagina")
    knoop.decorator_list = []
    oud = {"id": 1, "van": "locatie-wacht", "soort": "locatie", "sleutel": "2026-09-30", "titel": "x", "status": "klaar",
           "inhoud": "| 10:00 | 11:00 | 60 min | bezoek | OUDE_GSM_PLEK | |\n| 11:00 | 11:20 | 20 min | verplaatsing | 1,5 km |"}

    class Rijen(list):
        def fetchall(self):
            return self

    class Conn:
        def execute(self, sql, *a):
            return Rijen([oud] if "klaarzet" in sql else [])
    ns = {"mag_beslissen": lambda: True, "db": lambda: Conn(), "json": json, "APP_NAAM": "proef",
          "render_template": lambda *a, **k: k, "md": lambda t: t, "abort": lambda c: None,
          "_locatie": lambda pad, standaard=None: {"dagen": {"2026-10-03": {"verblijven": 6, "km": 166.5,
                                                                             "onderweg_min": 234}}}}
    exec(compile(ast.Module(body=[knoop], type_ignores=[]), "app.py", "exec"), ns)
    rijen = {r["dag"]: r for r in ns["dagen_pagina"]()["rijen"]}
    assert rijen["2026-10-03"]["km"] == 166.5 and rijen["2026-10-03"]["bezoeken"] == 6, rijen
    assert rijen["2026-09-30"]["km"] == 0 and rijen["2026-09-30"]["bezoeken"] == 0, "oude telefoondagboeken tellen niet"


def test_een_correctie_komt_binnen_een_lange_run_door():
    """Nacontrole v1.5: de dagcontext bleef per proces bewaard zonder vervaltijd. Een projectverblijf
    dat intussen geen_project werd, bleef dan voor de rest van de run een projectbezoek."""
    klok = [1000.0]
    LC._klok = lambda: klok[0]
    try:
        tegel = met_tegel({"2026-10-03": context_van("2026-10-03", [verblijf("2026-10-03")])})
        assert LC.verblijf_op("2026-10-03T10:30")["project"]["nummer"] == "9999"
        tegel.per_dag["2026-10-03"] = context_van("2026-10-03")          # rechtgezet: geen project
        klok[0] += 30
        assert LC.verblijf_op("2026-10-03T10:30"), "binnen de vervaltijd uit de cache"
        klok[0] += LC.CACHE_SECONDEN
        assert LC.verblijf_op("2026-10-03T10:30") is None, "na de vervaltijd geldt de correctie"
        assert len(tegel.gevraagd) == 2, tegel.gevraagd
    finally:
        LC._klok = __import__("time").monotonic


def test_levenscoach_grendel_blijft():
    bron = open(os.path.join(HIER, "levenscoach.py"), encoding="utf-8").read()
    assert "bronbeleid.dag_toegestaan(dag)" in bron


# Elk bestand dat locatiegegevens leest, met de controle die het toepast. Een nieuw bestand dat
# zulke gegevens leest zonder hier te staan laat deze grendel falen: eerst de grens, dan de lijst.
INVENTARIS = {
    "mijnagents-runner/locatie_wacht.py": "bronbeleid (dag_toegestaan, dagen_vanaf_grens); tegel-API's",
    "mijnagents-runner/archivaris.py": "locatiecontext (grens, alleen positieve autoverblijven)",
    "mijnagents-runner/plaud_wacht.py": "locatiecontext (grens, alleen positieve autoverblijven)",
    "mijnagents-runner/dagbundelaar.py": "locatiecontext.dag_heeft_dagboek (precies de dag, grens); sluit locatie uit bundels",
    "mijnagents-runner/levenscoach.py": "bronbeleid.dag_toegestaan op locatie-items",
    "mijnagents-runner/agenda_wacht.py": "leest alleen /api/plekken (benoemde plekken voor reistijd), geen metingen",
    "mijnagents-runner/koppelingen/locatiecontext.py": "de lezer zelf: bronbeleid, alleen /api/context",
    "mijnagents/app.py": "/api/dagcijfers en /api/beleid van de tegel; oude locatie-items niet getoond",
    "mijnagents-runner/planning/locatie_cron_zetten.py": "planning, leest geen gegevens",
}
PATRONEN = re.compile(r"soort\"\]? ?[!=]= ?\"locatie\"|\"soort\"\) ?== ?\"locatie\"|locatielogboek/dagen|/api/dag|"
                      r"/api/context|:3031|locatiecontext|locatie_op\(|/api/dagboek|/api/dagcijfers|/api/plekken")


def test_elke_lezer_van_locatiegegevens_staat_in_de_inventaris():
    gevonden = set()
    for wortel in ("mijnagents-runner", "mijnagents", "scripts"):
        for map_, _, bestanden in os.walk(os.path.join(REPO, wortel)):
            if "/tests" in map_ or "__pycache__" in map_:
                continue
            for b in bestanden:
                if b.endswith(".py"):
                    pad = os.path.join(map_, b)
                    if PATRONEN.search(open(pad, encoding="utf-8", errors="replace").read()):
                        gevonden.add(os.path.relpath(pad, REPO))
    onbekend = gevonden - set(INVENTARIS)
    assert not onbekend, "lezer(s) van locatiegegevens zonder grens in de inventaris: %s" % sorted(onbekend)
    for pad in INVENTARIS:
        if pad.endswith(("agenda_wacht.py", "locatie_cron_zetten.py", "mijnagents/app.py")):
            continue
        bron = open(os.path.join(REPO, pad), encoding="utf-8").read()
        assert "bronbeleid" in bron or "locatiecontext" in bron or "import locatiecontext" in bron, pad


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except Exception as e:  # noqa: BLE001
                fouten += 1
                print("   MISLUKT   %s: %s: %s" % (naam, type(e).__name__, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)
