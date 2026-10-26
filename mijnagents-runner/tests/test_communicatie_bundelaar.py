"""Grendels op De Communicatiebundelaar (ontwerp v1, 26-10-2026, docs/codex/communicatie-bundelaar-ontwerp-v1.md).

Tot 26-10-2026 draaide ze als skelet en las niemand de rijen van De Zoomwacht (driehoeksoverleg Zoomwacht 2, X4/X5).
Deze test legt de keuzes van Mehdi en de grenzen vast:

- goed: een collega in Zoom ("Voornaam (Afdeling)") en in Fathom ("Voornaam") is een persoon, met een naam uit kern;
- fout: een Zoom-meeting en haar Fathom-opname tellen twee keer; een rij buiten:<reden> telt mee;
- privé (kolom prive of afdeling prive) is alleen een aantal en een duur per kanaal, nooit een naam, ook niet in de
  titel, en de naam uit een privégesprek maakt een mailafzender niet bekend;
- mail per persoon alleen voor een collega of iemand uit een gesprek (keuze 1); een firma of een adres is overige mail;
- kanaal uit het voorvoegsel (keuze 3); minuten alleen bij video en ter plaatse, een rij zonder minuten is zonder duur;
- Mehdi en onbekende sprekers zijn geen persoon;
- onleesbare tabel: nood en niets klaargezet; kern onleesbaar, minder dan twee kanalen of een onbekend kanaal: nood;
- de runner leest geen inhoudskolommen, gaat door de gedeelde ronde, en de werkwijze geeft grenzen;
- geen sleutel prive bovenaan de inhoud (De Dagbundelaar zou het hele item als privégesprek lezen).

Geen netwerk: de databank en kern zijn nagebootst. Alle namen zijn verzonnen.
Draaien: python3 mijnagents-runner/tests/test_communicatie_bundelaar.py
"""
import json
import os
import sys
from datetime import date

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402
import communicatie_bundelaar as C  # noqa: E402

VANDAAG = date(2026, 10, 26)
DAG = "2026-10-25"
COLLEGAS = [
    {"naam": "Proefpersoon Zeta", "voornaam": "Zeta", "email": "zeta@voorbeeld.test"},
    {"naam": "Mehdi Proef", "voornaam": "Mehdi", "email": "mehdi@voorbeeld.test"},
]


def herken(tekst):
    t = (tekst or "").strip().lower()
    for p in COLLEGAS:
        if t in (p["naam"].lower(), p["email"]) or t.split()[0] == p["voornaam"].lower():
            return p
    return None


def rij(uniek, personen, minuten=0, prive=0, afdeling="", dubbel_van="", datum=DAG):
    return {"uniek": uniek, "datum": datum, "minuten": minuten, "personen": personen, "prive": prive,
            "afdeling": afdeling, "dubbel_van": dubbel_van}


RIJEN = [
    rij("zoom:meeting:a1", "Mehdi, Zeta (Architecture)", 30, dubbel_van="fathom:1"),
    rij("fathom:1", "Mehdi Chegini, Zeta", 28),
    rij("zoom:chat:zeta@voorbeeld.test:2026-10-25", "Zeta (Office)", 0),
    rij("fathom:2", "Mehdi, Klant Omega, Speaker 1", 45),
    rij("fathom:3", "Mehdi, Proefgeheim Sigma", 20, afdeling="prive"),
    rij("zoom:meeting:b2", "Mehdi, Proefgeheim Tau", 15, prive=1),
    rij("fathom:4", "Mehdi, Klant Omega", 0, dubbel_van="buiten:andere-ruimte"),
    rij("plaud:9", "Mehdi Chegini, Klant Omega", 60),
    rij("plaud:10", "Mehdi Chegini, Klant Omega", 0),
    rij("mail:<x1@voorbeeld.test>", "zeta@voorbeeld.test"),
    rij("mail:<x2@voorbeeld.test>", "Klant Omega"),
    rij("mail:<x3@voorbeeld.test>", "Robotfirma Proef"),
    rij("mail:<x4@voorbeeld.test>", "meldingen@robot.test"),
    rij("mail:<x5@voorbeeld.test>", "Proefgeheim Sigma"),
    rij("fathom:0", "Mehdi, Klant Omega", 10, datum="2026-08-01"),   # oud: alleen voor wie bekend is
]


class NepRonde:
    def __init__(self, werkwijze=None):
        self.werkwijze = werkwijze if werkwijze is not None else open(
            os.path.join(RUNNER, "werkwijze", "communicatie-bundelaar.md"), encoding="utf-8").read()
        self.noden, self.detail = [], ""

    def nood(self, tekst, wie="mehdi"):
        self.noden.append((tekst, wie))


def ronde(rijen=RIJEN, collegas=lambda: COLLEGAS, lees=None, werkwijze=None):
    r, gezet = NepRonde(werkwijze), []
    gelezen = []

    def lezen(sql, args):
        gelezen.append((sql, args))
        return [x for x in rijen if args[0] <= x["datum"] <= args[1]]
    dagen = C.werk(r, vandaag=VANDAAG, lees=lees or lezen, collegas=collegas, herken=herken,
                   zet=lambda its: gezet.extend(its) or {"nieuw": len(its)})
    return r, gezet, dagen, gelezen


def personen(dag):
    return {p["naam"]: p["kanalen"] for p in dag["personen"]}


def test_collega_in_elk_kanaal_een_persoon_en_dubbel_telt_niet():
    _, _, dagen, _ = ronde()
    p = personen(dagen[DAG])
    assert p["Proefpersoon Zeta"] == {"video": {"aantal": 1, "minuten": 28}, "chat": {"aantal": 1},
                                      "mail": {"aantal": 1}}, p["Proefpersoon Zeta"]
    assert "Zeta" not in p and "Zeta (Architecture)" not in p


def test_buiten_telt_niet_en_kanaal_ter_plaatse_zonder_duur():
    _, _, dagen, _ = ronde()
    omega = personen(dagen[DAG])["Klant Omega"]
    assert omega["video"] == {"aantal": 1, "minuten": 45}, omega   # fathom:4 is buiten: en telt niet
    assert omega["ter plaatse"] == {"aantal": 2, "minuten": 60, "zonder_duur": 1}, omega
    assert omega["mail"] == {"aantal": 1}, "Klant Omega zat in een gesprek, dus is zijn mail bekend"


def test_prive_alleen_aantal_nooit_naam():
    _, gezet, dagen, _ = ronde()
    d = dagen[DAG]
    assert d["prive_per_kanaal"] == {"video": {"aantal": 2, "minuten": 35}}, d["prive_per_kanaal"]
    tekst = json.dumps(gezet, ensure_ascii=False)
    assert "Sigma" not in tekst and "Tau" not in tekst, "een naam uit een privégesprek staat in het item"
    assert d["overige_mail"] == 3, "de privénaam maakt de afzender niet bekend; firma en adres zijn overige mail"


def test_mehdi_en_onbekende_sprekers_geen_persoon():
    _, _, dagen, _ = ronde()
    p = personen(dagen[DAG])
    assert not any(n.lower().startswith("mehdi") for n in p), p
    assert "Speaker 1" not in p and dagen[DAG]["onbekende_deelnemers"] == 1


def test_item_zonder_namen_in_titel_en_zonder_prive_sleutel():
    _, gezet, dagen, _ = ronde()
    assert [it["uniek"] for it in gezet] == [f"communicatie:dag:{DAG}"]
    it = gezet[0]
    assert it["voor"] == "mehdi" and it["soort"] == "communicatie" and it["sleutel"] == DAG
    assert "Zeta" not in it["titel"] and "Omega" not in it["titel"], it["titel"]
    assert "prive" not in json.loads(it["inhoud"]), "De Dagbundelaar leest een sleutel prive als privégesprek"
    assert "2026-08-01" not in dagen, "een dag buiten het venster krijgt geen item"


def test_venster_zeven_dagen_voor_vandaag():
    _, _, _, gelezen = ronde()
    assert gelezen[0][1] == ("2026-07-28", "2026-10-25"), gelezen[0][1]
    assert C.venster(VANDAAG)[:2] == ("2026-10-19", "2026-10-25")


def test_geen_inhoudskolommen_gelezen():
    sql = C.SQL.lower()
    for kolom in ("thema", "waarom", "link", "archief", "project", "select *"):
        assert kolom not in sql, kolom


def test_onleesbare_tabel_nood_en_niets_klaargezet():
    def kapot(sql, args):
        raise bord.BordOnbekend("databank van het bord ontbreekt")
    r, gezet, dagen, _ = ronde(lees=kapot)
    assert dagen is None and gezet == []
    assert ("Gesprekkentabel niet leesbaar", "claude-code") in r.noden


def test_kern_onleesbaar_en_te_weinig_kanalen_en_onbekend_kanaal_nood():
    r, _, _, _ = ronde(rijen=[rij("fathom:1", "Mehdi, Klant Omega", 5), rij("whatsapp:1", "Klant Omega")],
                       collegas=lambda: [])
    teksten = [t for t, _ in r.noden]
    assert "Collega's uit kern niet leesbaar, namen niet samengevoegd" in teksten
    assert "Minder dan twee kanalen leverden rijen in de laatste zeven dagen" in teksten
    assert "Rij met een onbekend kanaal in de gesprekkentabel" in teksten
    assert not any(ch.isdigit() for t in teksten for ch in t), "N10: geen getal in een nood"


def test_zonder_grenzen_geen_werk():
    r, gezet, dagen, _ = ronde(werkwijze="# Werkwijze\n\nIk bundel.\n")
    assert dagen is None and gezet == [] and r.noden[0][1] == "mehdi"


def test_werkwijze_geeft_grenzen_en_runner_door_de_ronde():
    ww = NepRonde().werkwijze
    nooit, mehdi = bord.grenzen(ww)
    assert len(nooit) >= 4 and len(mehdi) >= 3, (nooit, mehdi)
    assert len(ww) >= 500
    bron = open(os.path.join(RUNNER, "communicatie_bundelaar.py"), encoding="utf-8").read()
    assert 'with ag.ronde("communicatie bundelen") as r:' in bron
    for tekst in (ww, bron):
        assert "\N{EM DASH}" not in tekst and "\N{EN DASH}" not in tekst


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
