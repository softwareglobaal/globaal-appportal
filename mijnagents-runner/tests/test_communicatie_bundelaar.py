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
- onleesbare tabel of kern onleesbaar: nood en niets klaargezet; een onbekend kanaal: nood;
- een groepschat is alleen een aantal (CB06); een vreemde met de voornaam van een collega is geen collega (CB07);
- elke dag van het venster krijgt een item, ook zonder contact (CB04); elk item wordt teruggelezen (CB09);
- De Dagbundelaar slaat de soort communicatie over (CB02);
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


def rij(uniek, personen, minuten=0, prive=0, afdeling="", dubbel_van="", datum=DAG, sessie=""):
    return {"uniek": uniek, "datum": datum, "minuten": minuten, "personen": personen, "prive": prive,
            "afdeling": afdeling, "dubbel_van": dubbel_van, "sessie": sessie}


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


def ronde(rijen=RIJEN, collegas=lambda: COLLEGAS, lees=None, werkwijze=None, terug=lambda its: []):
    r, gezet = NepRonde(werkwijze), []
    gelezen = []

    def lezen(sql, args):
        gelezen.append((sql, args))
        return [x for x in rijen if args[0] <= x["datum"] <= args[1]]
    dagen = C.werk(r, vandaag=VANDAAG, lees=lees or lezen, collegas=collegas,
                   zet=lambda its: gezet.extend(its) or {"nieuw": len(its)}, terug=terug)
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


def test_prive_geldt_voor_het_hele_gesprek():
    """Codex, ontwerplezing 26-10-2026, zoals De Regisseur (_prive_sessies): een Fathom-rij die zelf niet privé is, met
    een Zoom-dubbel die het wel is (via dubbel_van of dezelfde sessie, ook van vandaag), is privé. Een rij buiten:<reden>
    maakt niets privé."""
    rijen = [rij("fathom:7", "Mehdi, Proefgeheim Sigma", 30),
             rij("zoom:meeting:c3", "Mehdi, Proefgeheim Sigma", 31, prive=1, dubbel_van="fathom:7"),
             rij("fathom:8", "Mehdi, Proefgeheim Tau", 12, sessie="zoom:meeting:d4"),
             rij("zoom:meeting:d4", "Mehdi, Proefgeheim Tau", 12, afdeling="prive", datum="2026-10-26",
                 sessie="zoom:meeting:d4"),
             rij("fathom:9", "Mehdi, Klant Omega", 5),
             rij("fathom:10", "Mehdi, Klant Omega", 5, prive=1, dubbel_van="buiten:andere-ruimte")]
    _, gezet, dagen, _ = ronde(rijen=rijen)
    d = dagen[DAG]
    assert d["prive_per_kanaal"] == {"video": {"aantal": 2, "minuten": 42}}, d["prive_per_kanaal"]
    assert list(personen(d)) == ["Klant Omega"]
    assert "Sigma" not in json.dumps(gezet) and "Tau" not in json.dumps(gezet)


def test_prive_over_een_keten_van_dubbels():
    """Codex, controle 1: met alleen de directe voorganger lekte de naam uit een privégesprek via een keten."""
    rijen = [rij("fathom:20", "Mehdi, Proefgeheim Sigma", 30),
             rij("fathom:21", "Mehdi, Proefgeheim Sigma", 30, dubbel_van="fathom:20"),
             rij("zoom:meeting:e5", "Mehdi, Proefgeheim Sigma", 30, prive=1, dubbel_van="fathom:21", sessie="zoom:meeting:e5"),
             rij("fathom:22", "Mehdi, Proefgeheim Sigma", 30, sessie="zoom:meeting:e5", dubbel_van="fathom:20")]
    _, gezet, dagen, _ = ronde(rijen=rijen)
    assert dagen[DAG]["personen"] == [] and dagen[DAG]["prive_per_kanaal"] == {"video": {"aantal": 1, "minuten": 30}}
    assert "Sigma" not in json.dumps(gezet)


def test_items_met_revisie_zodat_een_opgepakt_item_de_bron_volgt():
    """Codex, controle 1 (CB04): zonder revisie laat het bord een opgepakt item ongemoeid (mijnagents/app.py,
    api_klaarzet), en bleef een naam staan als het gesprek later privé werd."""
    _, gezet, _, _ = ronde()
    assert gezet and all(it["revisie"] is True for it in gezet)
    app = open(os.path.join(os.path.dirname(RUNNER), "mijnagents", "app.py"), encoding="utf-8").read()
    assert 'oud["status"] != "klaar" and it.get("revisie")' in app


def test_mehdi_en_onbekende_sprekers_geen_persoon():
    _, _, dagen, _ = ronde()
    p = personen(dagen[DAG])
    assert not any(n.lower().startswith("mehdi") for n in p), p
    assert "Speaker 1" not in p and dagen[DAG]["onbekende_deelnemers"] == 1


def test_item_zonder_namen_in_titel_en_zonder_prive_sleutel():
    _, gezet, dagen, _ = ronde()
    assert [it["uniek"] for it in gezet] == [f"communicatie:dag:2026-10-{d}" for d in range(19, 26)]
    assert gezet[0]["titel"] == "Communicatie 2026-10-19: geen contact in de gesprekkentabel"
    it = gezet[-1]
    assert it["voor"] == "mehdi" and it["soort"] == "communicatie" and it["sleutel"] == DAG
    assert "Zeta" not in it["titel"] and "Omega" not in it["titel"], it["titel"]
    assert "prive" not in json.loads(it["inhoud"]), "De Dagbundelaar leest een sleutel prive als privégesprek"
    assert "2026-08-01" not in dagen, "een dag buiten het venster krijgt geen item"


def test_venster_zeven_dagen_voor_vandaag():
    _, _, _, gelezen = ronde()
    assert gelezen[0][1] == ("2026-07-28", "2026-10-26"), gelezen[0][1]
    assert C.venster(VANDAAG) == ("2026-10-19", "2026-10-25", "2026-07-28", "2026-10-26")


def test_namen_haakjes_met_komma_en_label_na_dubbelepunt():
    """Gemeten bij de droge proef op de VM, 26-10-2026: een komma tussen haakjes maakte van een deel van de uitleg een
    persoon, en een Zoom-chat met een label na de naam werd een tweede persoon naast dezelfde naam."""
    assert list(C.namen("Mehdi, Speaker 1 (onbekend, mogelijk Zeta of Omega), Klant Omega: FIRMA: Offerte")) == \
        ["Mehdi", "Speaker 1", "Klant Omega"]


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


def test_kern_onleesbaar_nood_en_niets_klaargezet():
    r, gezet, dagen, _ = ronde(collegas=lambda: [])
    assert dagen is None and gezet == [] and r.noden == [("Collega's uit kern niet leesbaar", "claude-code")]


def test_onbekend_kanaal_nood_zonder_getal():
    r, _, dagen, _ = ronde(rijen=[rij("fathom:1", "Mehdi, Klant Omega", 5), rij("whatsapp:1", "Klant Omega")])
    teksten = [t for t, _ in r.noden]
    assert teksten == ["Rij met een onbekend kanaal in de gesprekkentabel"], teksten
    assert not any(ch.isdigit() for t in teksten for ch in t), "N10: geen getal in een nood"
    assert dagen[DAG]["contacten"] == 1


def test_groepschat_alleen_aantal():
    rijen = [rij("zoom:chat:kanaal-proef-123:2026-10-25", "Proefkanaal Delta", 0),
             rij("mail:<y1@voorbeeld.test>", "Proefkanaal Delta")]
    _, _, dagen, _ = ronde(rijen=rijen)
    d = dagen[DAG]
    assert d["personen"] == [] and d["kanalen"] == {"groepschat": 1, "mail": 1}
    assert d["overige_mail"] == 1, "een kanaalnaam maakt een mailafzender niet bekend"


def test_vreemde_met_voornaam_van_collega_is_geen_collega():
    rijen = [rij("fathom:1", "Mehdi, Zeta Vreemdeling", 10), rij("fathom:2", "Mehdi Chegini, Zeta", 5),
             rij("mail:<y2@voorbeeld.test>", "Mehdi Vreemd")]
    _, _, dagen, _ = ronde(rijen=rijen)
    p = personen(dagen[DAG])
    assert set(p) == {"Zeta Vreemdeling", "Proefpersoon Zeta"}, p
    assert dagen[DAG]["overige_mail"] == 1, "alleen Mehdi en Mehdi Chegini zijn Mehdi, niet elke Mehdi"


def test_terug_lezen_geeft_nood_als_het_bord_anders_is():
    r, gezet, _, _ = ronde(terug=lambda its: [its[0]["uniek"]])
    assert ("Een klaargezet item staat niet zo op het bord", "claude-code") in r.noden
    gelezen = []
    assert C.terug_lezen(gezet[:1], lees=lambda u: gelezen.append(u) or [dict(gezet[0])]) == []
    assert C.terug_lezen(gezet[:1], lees=lambda u: [dict(gezet[0], inhoud="{}")]) == [gezet[0]["uniek"]]
    assert C.terug_lezen(gezet[:1], lees=lambda u: [dict(gezet[0], voor="h-architects")]) == [gezet[0]["uniek"]]
    assert gelezen == [gezet[0]["uniek"]]


def test_dagbundelaar_slaat_communicatie_over():
    bron = open(os.path.join(RUNNER, "dagbundelaar.py"), encoding="utf-8").read()
    regel = next(r for r in bron.splitlines() if '"zoom-tekst", "ochtendbericht"' in r)
    assert '"communicatie"' in regel, regel


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
