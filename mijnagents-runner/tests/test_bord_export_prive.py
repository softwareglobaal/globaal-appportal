"""Grendel op de export van een privé-agent (T-0120 ANGEL-11, bord_export.py).

Tot 01-11-2026 keek de export alleen per item naar privé, niet naar de agent. Ai Angel (mehdi-agent, agent.prive = 1)
zette zijn volledige takenlijst klaar, met werknamen en concepten, en die ging voluit naar Data uit Mehdi.

- E01: van een privé-agent staat in klaargezet/ per item alleen tijd, soort, voor wie, status en titel; nooit verwijzing
  of inhoud;
- E02: de export van een gewone agent verandert niet: elk bestand buiten de map van de privé-agent is gelijk met of
  zonder de vlag, op het verslag van de privé-agent na, dat er met de vlag niet meer bij komt;
- E03: een privé-item van een privé-agent blijft '(privé)', zonder titel;
- E04: de export wist niets: een oud bestand van de privé-agent buiten het venster blijft staan;
- E05 (Codex, toets 1): ook een item met een eigen exportvorm (zoom-account, met delen en adviescodes uit de inhoud)
  geeft van een privé-agent geen inhoud; hetzelfde item van een gewone agent blijft zoals het was;
- E06 (Codex, toets 2): het ochtend- en avondverslag van Ai Angel (soort verslag, met alle open taken) staat in geen
  enkel exportbestand; een gewoon verslag blijft voluit in Ontwikkelaar/verslagen;
- E07: in het werkverslag van een privé-agent alleen tijd, stap en onderwerp, zoals De Regisseur (agent_verslag) het
  geeft; het werkverslag van een gewone agent blijft voluit;
- E08 (samen2, Codex-toets 1): van een privé-agent geven noden.md, voorstellen.md en de stand van het team alleen tijd,
  status en wie; van een gewone agent blijven ze voluit.

Geen netwerk: de databank is tijdelijk en komt uit init_db van mijnagents/app.py (export_db uit test_bord_lees.py).
Alle namen en inhoud zijn verzonnen.
Draaien: python3 mijnagents-runner/tests/test_bord_export_prive.py
"""
import io
import os
import re
import sqlite3
import sys
from contextlib import redirect_stderr, redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
from test_bord_lees import export, export_db  # noqa: E402

GEHEIM = ("Omega", "Sigma", "Tau")
TAKEN = {"van": "mehdi-agent", "voor": "mehdi", "soort": "taken", "titel": "Te doen: 3 open, 1 hoog",
         "inhoud": {"taken": [{"wat": "Proefconcept Omega naar Klant Sigma", "werknaam": "Werknaam Tau"}]},
         "verwijzing": "concept Omega Sigma", "status": "klaar"}
VERSLAG = {"van": "mehdi-agent", "voor": "mehdi", "soort": "verslag", "titel": "Te doen vandaag proef",
           "inhoud": "Overzicht van de dag.\n\n## Alle open taken\n\n1. Proefconcept Omega naar Klant Sigma (Werknaam Tau)"}
PRIVE_ITEM = {"van": "mehdi-agent", "voor": "mehdi", "soort": "taken", "titel": "Avond met Proefpersoon Zeta · PRIVÉ",
              "inhoud": {"prive": True}, "status": "klaar"}
GEWOON = {"van": "agenda-wacht", "voor": "mehdi", "soort": "dagplan", "titel": "Dagplan proefdag",
          "inhoud": {"punten": ["Werfbezoek Proefstraat 1"]}, "verwijzing": "agenda proef", "status": "klaar"}
GEWOON_VERSLAG = {"van": "ontwikkelaar", "voor": "mehdi", "soort": "verslag", "titel": "Ontwikkelverslag proef",
                  "inhoud": "Gewone inhoud Kappa"}
ZOOM_ACCOUNT = {"soort": "zoom-account", "voor": "mehdi", "titel": "Zoom-account proef", "status": "klaar",
                "inhoud": {"delen": {"beveiliging": "ok", "opnames": "onbekend: proef"},
                           "adviezen": [{"code": "ZA-01"}]}, "verwijzing": "accountscan proef"}
LOG = [{"naam": "mehdi-agent", "onderwerp": "ronde", "stap": "melding", "tekst": "Proefconcept Omega bijgewerkt",
        "detail": "Klant Sigma, Werknaam Tau"},
       {"naam": "agenda-wacht", "onderwerp": "dag proef", "stap": "schrijf", "tekst": "Gewone logregel Kappa",
        "detail": "gewoon detail Lambda"}]


def met_agents(naam, prive):
    """Een databank met Ai Angel als agent, prive 0 of 1, en twee gewone agents."""
    pad = export_db(naam)
    c = sqlite3.connect(pad)
    for agent, label, p in (("mehdi-agent", "Ai Angel", prive), ("agenda-wacht", "De Agendawacht", 0),
                            ("ontwikkelaar", "De Ontwikkelaar", 0)):
        c.execute("INSERT OR IGNORE INTO agent(naam, label, aangemaakt) VALUES(?, ?, '2026-11-01')", (agent, label))
        c.execute("UPDATE agent SET label=?, prive=? WHERE naam=?", (label, p, agent))
    c.commit()
    c.close()
    return pad


def klaargezet(gelezen, map_):
    return "\n".join(t for p, t in gelezen.items() if p.startswith(os.path.join("export", map_, "klaargezet")))


def norm(tekst):
    """Zonder dag en uur: twee exports na elkaar mogen over een minuut of middernacht heen lopen."""
    return re.sub(r"\d{2}:?\d{2}", "UU:MM", re.sub(r"\d{4}-\d{2}-\d{2}", "DAG", tekst))


def gewone_bestanden(gelezen):
    """Elk bestand buiten de map van Ai Angel, zonder de stand van het team (die draagt het uur van de export)."""
    return {norm(p): norm(t) for p, t in gelezen.items()
            if not p.startswith(os.path.join("export", "Ai Angel")) and not p.endswith("stand van het team.md")}


def test_e01_prive_agent_alleen_tijd_soort_titel_status():
    tekst = klaargezet(export(met_agents("e01", 1), [TAKEN], []), "Ai Angel")
    assert "taken voor mehdi (klaar): Te doen: 3 open, 1 hoog" in tekst, tekst
    for geheim in GEHEIM + ("verwijzing",):
        assert geheim not in tekst, (geheim, tekst)


def test_e02_gewone_agent_onveranderd():
    items = [TAKEN, VERSLAG, GEWOON, GEWOON_VERSLAG]
    met = gewone_bestanden(export(met_agents("e02a", 1), items, LOG))
    zonder = gewone_bestanden(export(met_agents("e02b", 0), items, LOG))
    angel_verslag = [p for p in zonder if "Te doen vandaag proef" in p]
    assert len(angel_verslag) == 1, sorted(zonder)
    assert met == {p: t for p, t in zonder.items() if p not in angel_verslag}, set(met) ^ set(zonder)
    gewoon = "\n".join(met.values())
    assert "verwijzing: agenda proef" in gewoon and "Werfbezoek Proefstraat 1" in gewoon, gewoon
    # zonder de vlag gaat het item van Ai Angel zoals voorheen voluit: de vlag maakt het verschil
    assert "Proefconcept Omega" in "\n".join(zonder.values())


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


def test_e05_eigen_exportvorm_van_prive_agent_zonder_inhoud():
    items = [dict(ZOOM_ACCOUNT, van="mehdi-agent"), dict(ZOOM_ACCOUNT, van="agenda-wacht")]
    met = export(met_agents("e05a", 1), items, [])
    zonder = export(met_agents("e05b", 0), items, [])
    angel = klaargezet(met, "Ai Angel")
    assert "zoom-account voor mehdi (klaar): Zoom-account proef" in angel, angel
    for geheim in ("Delen", "Adviescodes", "ZA-01", "beveiliging", "accountscan"):
        assert geheim not in angel, (geheim, angel)
    gewoon = klaargezet(met, "Agendawacht")
    assert norm(gewoon) == norm(klaargezet(zonder, "Agendawacht")) and "Adviescodes: ZA-01" in gewoon, gewoon


def test_e06_verslag_van_prive_agent_in_geen_enkel_exportbestand():
    gelezen = export(met_agents("e06", 1), [TAKEN, VERSLAG, GEWOON_VERSLAG], LOG)
    for pad, tekst in gelezen.items():
        for geheim in GEHEIM:
            assert geheim not in pad and geheim not in tekst, (geheim, pad, tekst)
    assert not [p for p in gelezen if "Te doen vandaag proef" in p], sorted(gelezen)
    gewoon = [t for p, t in gelezen.items() if p.startswith(os.path.join("export", "Ontwikkelaar", "verslagen"))]
    assert gewoon == ["Gewone inhoud Kappa"], gewoon


def test_e07_werkverslag_van_prive_agent_alleen_tijd_stap_onderwerp():
    gelezen = export(met_agents("e07", 1), [], LOG)
    angel = "\n".join(t for p, t in gelezen.items() if p.startswith(os.path.join("export", "Ai Angel", "werkverslag")))
    assert "[melding] ronde" in angel and "privé-agent" in angel, angel
    for geheim in GEHEIM:
        assert geheim not in angel, (geheim, angel)
    gewoon = "\n".join(t for p, t in gelezen.items() if p.startswith(os.path.join("export", "Agendawacht", "werkverslag")))
    assert "Gewone logregel Kappa" in gewoon and "gewoon detail Lambda" in gewoon, gewoon


def test_e08_noden_voorstellen_en_stand_van_prive_agent_zonder_inhoud():
    pad = met_agents("e08", 1)
    c = sqlite3.connect(pad)
    for agent, tekst in (("mehdi-agent", "Proefconcept Omega naar Klant Sigma"), ("agenda-wacht", "Gewone nood Kappa")):
        c.execute("INSERT INTO nood(naam, tekst, wie, open, ts) VALUES(?, ?, 'mehdi', 1, '2026-11-01T08:00:00Z')", (agent, tekst))
        c.execute("INSERT INTO voorstel(naam, actie, doel, reden, status, ts) VALUES(?, ?, ?, ?, 'open', "
                  "'2026-11-01T08:00:00Z')", (agent, f"Actie {tekst}", "Doel Werknaam Tau", "Reden Omega"))
        c.execute("INSERT OR REPLACE INTO status(naam, status, taak, detail, ts) VALUES(?, 'klaar', ?, ?, "
                  "'2026-11-01T08:00:00Z')", (agent, f"Taak {tekst}", "Detail Sigma"))
    c.commit()
    c.close()
    gelezen = export(pad, [], [])
    angel = "\n".join(t for p, t in gelezen.items() if p.startswith(os.path.join("export", "Ai Angel")))
    stand = "\n".join(t for p, t in gelezen.items() if p.endswith("stand van het team.md"))
    assert "privé-agent" in angel and "| ja |" in angel and "| open |" in angel, angel
    regel_angel = [r for r in stand.splitlines() if r.startswith("| Ai Angel |")]
    assert regel_angel and "privé-agent" in regel_angel[0], stand
    for geheim in GEHEIM:
        assert geheim not in angel and geheim not in regel_angel[0], (geheim, angel, regel_angel)
    gewoon = "\n".join(t for p, t in gelezen.items() if p.startswith(os.path.join("export", "Agendawacht")))
    assert "Gewone nood Kappa" in gewoon and "Actie Gewone nood Kappa" in gewoon, gewoon
    assert "Taak Gewone nood Kappa" in stand and "Detail Sigma" in stand, stand


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
