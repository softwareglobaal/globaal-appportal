"""Grendel op de export van een privé-agent (T-0120 ANGEL-11, bord_export.py).

Tot 01-11-2026 keek de export alleen per item naar privé, niet naar de agent. Ai Angel (mehdi-agent, agent.prive = 1)
zette zijn volledige takenlijst klaar, met werknamen en concepten, en die ging voluit naar Data uit Mehdi.

- E01: van een privé-agent staat in klaargezet/ per item alleen tijd, soort, voor wie, status en titel; nooit verwijzing
  of inhoud;
- E02: de export van een gewone agent verandert niet: zijn bestand is gelijk met of zonder een privé-agent ernaast;
- E03: een privé-item van een privé-agent blijft '(privé)', zonder titel;
- E04: de export wist niets: een oud bestand van de privé-agent buiten het venster blijft staan.

Geen netwerk: de databank is tijdelijk en komt uit init_db van mijnagents/app.py (export_db uit test_bord_lees.py).
Alle namen en inhoud zijn verzonnen.
Draaien: python3 mijnagents-runner/tests/test_bord_export_prive.py
"""
import io
import os
import sqlite3
import sys
from contextlib import redirect_stderr, redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from test_bord_lees import export, export_db  # noqa: E402

TAKEN = {"van": "mehdi-agent", "voor": "mehdi", "soort": "taken", "titel": "Te doen: 3 open, 1 hoog",
         "inhoud": {"taken": [{"wat": "Proefconcept Omega naar Klant Sigma", "werknaam": "Werknaam Tau"}]},
         "verwijzing": "concept Omega Sigma", "status": "klaar"}
PRIVE_ITEM = {"van": "mehdi-agent", "voor": "mehdi", "soort": "taken", "titel": "Avond met Proefpersoon Zeta · PRIVÉ",
              "inhoud": {"prive": True}, "status": "klaar"}
GEWOON = {"van": "agenda-wacht", "voor": "mehdi", "soort": "dagplan", "titel": "Dagplan proefdag",
          "inhoud": {"punten": ["Werfbezoek Proefstraat 1"]}, "verwijzing": "agenda proef", "status": "klaar"}


def met_agents(naam, prive):
    """Een databank met Ai Angel als agent, prive 0 of 1, en een gewone agent."""
    pad = export_db(naam)
    c = sqlite3.connect(pad)
    for agent, label, p in (("mehdi-agent", "Ai Angel", prive), ("agenda-wacht", "De Agendawacht", 0)):
        c.execute("INSERT OR IGNORE INTO agent(naam, label, aangemaakt) VALUES(?, ?, '2026-11-01')", (agent, label))
        c.execute("UPDATE agent SET label=?, prive=? WHERE naam=?", (label, p, agent))
    c.commit()
    c.close()
    return pad


def klaargezet(gelezen, map_):
    return "\n".join(t for p, t in gelezen.items() if p.startswith(os.path.join("export", map_, "klaargezet")))


def test_e01_prive_agent_alleen_tijd_soort_titel_status():
    tekst = klaargezet(export(met_agents("e01", 1), [TAKEN], []), "Ai Angel")
    assert "taken voor mehdi (klaar): Te doen: 3 open, 1 hoog" in tekst, tekst
    for geheim in ("Omega", "Sigma", "Tau", "verwijzing"):
        assert geheim not in tekst, (geheim, tekst)


def test_e02_gewone_agent_onveranderd():
    met = export(met_agents("e02a", 1), [TAKEN, GEWOON], [])
    zonder = export(met_agents("e02b", 0), [TAKEN, GEWOON], [])
    assert klaargezet(met, "Agendawacht") == klaargezet(zonder, "Agendawacht")
    gewoon = klaargezet(met, "Agendawacht")
    assert "verwijzing: agenda proef" in gewoon and "Werfbezoek Proefstraat 1" in gewoon, gewoon
    # zonder de vlag gaat het item van Ai Angel zoals voorheen voluit: de vlag maakt het verschil
    assert "Proefconcept Omega" in klaargezet(zonder, "Ai Angel")


def test_e03_prive_item_van_prive_agent_blijft_prive():
    tekst = klaargezet(export(met_agents("e03", 1), [PRIVE_ITEM], []), "Ai Angel")
    assert "taken voor mehdi (klaar): (privé)" in tekst and "Zeta" not in tekst, tekst


def test_e04_export_wist_niets():
    import bord_export as E  # noqa: PLC0415
    pad = met_agents("e04", 1)
    oud = (E.DB, E.DATA, E.UIT)
    data = os.path.join(os.path.dirname(pad), "e04-data")
    oud_bestand = os.path.join(data, "export", "Mehdi-agent", "klaargezet", "2026-10-01.md")
    os.makedirs(os.path.dirname(oud_bestand), exist_ok=True)
    with open(oud_bestand, "w", encoding="utf-8") as f:
        f.write("oud bestand van voor de hernoeming\n")
    E.DB, E.DATA, E.UIT = pad, data, os.path.join(data, "export")
    try:
        with redirect_stdout(io.StringIO()):
            E.main()
    finally:
        E.DB, E.DATA, E.UIT = oud
    assert open(oud_bestand, encoding="utf-8").read() == "oud bestand van voor de hernoeming\n"


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
