"""Grendels op de nummerreservering aan de kant van de Contracten-agent en het runbook (WP2b, 12-10-2026).

De agent telt de nummers van open en goedgekeurde voorstellen op het bord mee als vijfde bron; een deal die al
een voorstel heeft, houdt zijn nummer; een betwist nummer laat hij aan Mehdi. Het runbook pipedrive-dealtitel
controleert vlak vóór de PUT het bord en de vier vaste bronnen; een verliezende of onzekere uitvoering schrijft
niets naar Pipedrive. Nepbronnen; geen netwerk, geen databank, geen Pipedrive.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_nummerreservering.py
"""
import os
import sys

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, os.path.join(HIER, "runbooks"))
import contracten_agent as ca  # noqa: E402
import pipedrive_dealtitel as R  # noqa: E402
from test_nummeruitgifte import Nep, met  # noqa: E402


def res(nummer, deal, vid, status="open"):
    return {"nummer": nummer, "deal_id": str(deal), "voorstel_id": vid, "status": status, "bron": "reservering"}


def fout_van(fn):
    try:
        fn()
    except ca.NummerFout as e:
        return str(e)
    raise AssertionError("verwacht een NummerFout")


# ------------------------------------------------------------------ agent ---
def test_open_voorstel_van_andere_deal_telt_als_bezet():
    nep = Nep(deals={"open": ["2620 Testklant"]}, reserveringen=[res("2621", 900102, 31)])
    bewijs = {}
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, bewijs, deal_id=900101)) == "2622"
    assert bewijs["per_bron"]["bord voorstellen"] == 1


def test_goedgekeurd_voorstel_van_andere_deal_telt_als_bezet():
    nep = Nep(reserveringen=[res("2601", 900102, 31, "goedgekeurd")])
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, deal_id=900101)) == "2602"


def test_dezelfde_deal_houdt_zijn_nummer():
    nep = Nep(deals={"open": ["2630 Testklant"]}, reserveringen=[res("2621", 900101, 31)])
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, deal_id=900101)) == "2621"


def test_betwist_nummer_laat_de_agent_aan_mehdi():
    """Zoals 2617 voor drie deals: de agent stelt voor geen van hen een ander nummer voor."""
    nep = Nep(reserveringen=[res("2617", 14543, 25), res("2617", 14566, 26), res("2617", 14518, 27)])
    for deal in (14543, 14566, 14518):
        melding = fout_van(lambda: met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, deal_id=deal)))
        assert "Mehdi beslist" in melding and "2617" in melding
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, deal_id=900999)) == "2618"


def test_nummer_na_voorstel_elders_gebruikt():
    nep = Nep(deals={"won": ["2621 Andere klant"]}, reserveringen=[res("2621", 900101, 31, "open")])
    bewijs = {}
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, bewijs, deal_id=900101)) == "2622"
    assert bewijs["eigen_voorstel_elders_gebruikt"] == "2621"
    nep = Nep(deals={"won": ["2621 Andere klant"]}, reserveringen=[res("2621", 900101, 31, "goedgekeurd")])
    melding = fout_van(lambda: met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, deal_id=900101)))
    assert "goedgekeurd voorstel 31" in melding and "Mehdi weigert" in melding


def test_bord_onbereikbaar_geeft_geen_nummer():
    melding = fout_van(lambda: met(Nep(fout="bord"), lambda: ca.volgend_vrij_nummer("architectuur", 2026)))
    assert "agentbord" in melding


def test_onvolledige_bordlijst_geeft_geen_nummer():
    oud = (ca.urllib.request.urlopen, ca.TOKEN)

    class Antwoord:
        def __init__(self, data):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    for data in (b'{"bezet": [], "aantal": 3, "volledig": true}', b'{"bezet": [], "aantal": 0}', b'[]'):
        ca.urllib.request.urlopen = lambda req, timeout=None, d=data: Antwoord(d)
        try:
            fout_van(ca.bord_reserveringen)
        finally:
            ca.urllib.request.urlopen, ca.TOKEN = oud


def test_reeks_van_nummer():
    oud = ca.nummerlezer.jaar_nu_brussel
    ca.nummerlezer.jaar_nu_brussel = lambda: 2026
    try:
        assert ca.reeks_van_nummer("2617") == ("architectuur", 2026)
        assert ca.reeks_van_nummer("5609") == ("regularisatie", 2026)
        assert ca.reeks_van_nummer("2701") == ("architectuur", 2027)
        fout_van(lambda: ca.reeks_van_nummer("2401"))
    finally:
        ca.nummerlezer.jaar_nu_brussel = oud


# ---------------------------------------------------------------- runbook ---
class Pipedrive:
    """Telt elke schrijfactie; een verliezende uitvoering mag er geen doen."""

    def __init__(self):
        self.puts, self.bedrijf, self.gelezen = [], [], []

    def schrijf(self, firma, methode, pad, body=None, params=None):
        self.puts.append((firma, methode, pad, body))
        return {}, "ok"

    def controleer_bedrijf(self, firma, verwacht):
        self.bedrijf.append((firma, verwacht))
        return verwacht


def voer(params, nep=None, bord=None, titel_nu="Testklant", deal_gelezen=900101):
    pd = Pipedrive()
    nep = nep or Nep()
    oud = (R.pipedrive.schrijf, R.pipedrive.controleer_bedrijf, R.nummerlezer.jaar_nu_brussel,
           ca.nummerlezer.jaar_nu_brussel, R.pipedrive.get)
    R.pipedrive.schrijf = pd.schrijf
    R.pipedrive.get = lambda firma, pad, params=None: (pd.gelezen.append((firma, pad)) or
                                                       {"id": deal_gelezen, "title": titel_nu})
    R.nummerlezer.jaar_nu_brussel = ca.nummerlezer.jaar_nu_brussel = lambda: 2026
    p = {"deal_id": 900101, "titel": "2621 Testklant", "nummer": "2621", "firma": "harchitects", "_voorstel_id": 31,
         "_bord": bord or (lambda pad: {"ok": True, "nummer": "2621", "deal_id": "900101"}), **params}
    try:
        def uitvoeren():
            R.pipedrive.controleer_bedrijf = pd.controleer_bedrijf     # na met(): die zet zijn eigen nep
            return R.voer_uit(p)
        try:
            return met(nep, uitvoeren), pd
        except (R.NummerConflict, ValueError) as e:
            return e, pd
    finally:
        (R.pipedrive.schrijf, R.pipedrive.controleer_bedrijf, R.nummerlezer.jaar_nu_brussel,
         ca.nummerlezer.jaar_nu_brussel, R.pipedrive.get) = oud


def test_runbook_schrijft_na_volledige_controle():
    uit, pd = voer({})
    assert pd.puts == [("harchitects", "PUT", "/deals/900101", {"title": "2621 Testklant"})]
    assert pd.bedrijf and set(pd.bedrijf) == {("harchitects", 10068585)}      # bronlezing én vóór de PUT
    assert "bord ok" in uit[1] and "bronnen volledig" in uit[1]


def test_runbook_bord_blokkeert_geen_put():
    uit, pd = voer({}, bord=lambda pad: {"ok": False, "reden": "nummer 2621 staat ook in voorstel 32 voor een andere deal"})
    assert isinstance(uit, R.NummerConflict) and "voorstel 32" in str(uit) and pd.puts == []


def test_runbook_bord_onbereikbaar_geen_put():
    def weg(pad):
        raise OSError("connection refused")
    uit, pd = voer({}, bord=weg)
    assert isinstance(uit, R.NummerConflict) and pd.puts == []


def test_runbook_bord_kent_ander_nummer_geen_put():
    uit, pd = voer({}, bord=lambda pad: {"ok": True, "nummer": "2622", "deal_id": "900101"})
    assert isinstance(uit, R.NummerConflict) and pd.puts == []


def test_runbook_zonder_voorstel_id_geen_put():
    uit, pd = voer({"_voorstel_id": None})
    assert isinstance(uit, R.NummerConflict) and pd.puts == []


def test_runbook_nummer_inmiddels_elders_gebruikt_geen_put():
    uit, pd = voer({}, nep=Nep(deals={"open": ["2621 Andere klant"]}))
    assert isinstance(uit, R.NummerConflict) and "inmiddels gebruikt" in str(uit) and pd.puts == []
    uit, pd = voer({}, nep=Nep(mappen={"2026 Design": ["2621 Andere straat 1.docx"]}))
    assert isinstance(uit, R.NummerConflict) and "contractmappen" in str(uit) and pd.puts == []


def test_runbook_bronfout_geen_put():
    for fout in ("map", "dashboard", "pipedrive"):
        uit, pd = voer({}, nep=Nep(fout=fout))
        assert isinstance(uit, R.NummerConflict) and pd.puts == [], fout


def test_runbook_verkeerde_firma_of_nummer_geen_put():
    uit, pd = voer({"firma": "unabo"})
    assert isinstance(uit, ValueError) and pd.puts == []
    uit, pd = voer({"nummer": "2622"})
    assert isinstance(uit, ValueError) and pd.puts == []


def test_runbook_eigen_deal_mag_het_nummer_al_dragen():
    """Staat het nummer al in de voorbereiding van dezelfde deal, dan is dat geen conflict."""
    nep = Nep(voorbereidingen=["2621"])
    nep.call = lambda naam, **kw: ({"aantal": 1, "dossiers": [{"nummer": "2621", "deal_id": 900101}]}
                                   if naam == "voorbereidingen" else {"aantal": 0, "dossiers": []})
    uit, pd = voer({}, nep=nep)
    assert len(pd.puts) == 1


def test_agent_leest_de_uitkomst_van_de_reservering_terug():
    oud = ca.urllib.request.urlopen
    gestuurd = []

    class Antwoord:
        def __init__(self, data):
            self.data = data

        def read(self):
            return self.data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def bezet(req, timeout=None):
        gestuurd.append(ca.json.loads(req.data.decode()))
        return Antwoord(b'{"ok": true, "voorstel": {"bewaard": false, "uitkomst": "bezet", "bezet_door": [{"voorstel_id": 31}]}}')

    def weg(req, timeout=None):
        raise OSError("timeout")
    try:
        ca.urllib.request.urlopen = bezet
        uit = ca.nummervoorstel_op_bord(900101, "2621", "Testklant", "architectuur")
        assert uit["uitkomst"] == "bezet"
        p = gestuurd[0]["voorstel"]["parameters"]
        assert p == {"deal_id": 900101, "titel": "2621 Testklant", "nummer": "2621", "firma": "harchitects",
                     "soort": "architectuur"}
        ca.urllib.request.urlopen = weg
        assert ca.nummervoorstel_op_bord(900101, "2621", "Testklant", "architectuur")["uitkomst"] == "onzeker"
    finally:
        ca.urllib.request.urlopen = oud


# ------------------------------------------------- reeds voldaan (12-10-2026) ---
def test_eigen_gebruik_tegenover_gebruik_door_een_ander():
    eigen, ander = ("voorbereidingen", "14531"), ("pipedrive open", "99")
    bestand = ("contractmappen", None)
    assert ca.gebruik_elders([eigen], 14531) == []
    assert ca.gebruik_elders([bestand, eigen], 14531) == []               # bestand gebonden aan de eigen deal
    assert ca.gebruik_elders([bestand], 14531) == [bestand]               # bestand zonder bewezen koppeling
    assert ca.gebruik_elders([bestand, eigen, ander], 14531) == [ander, bestand]


def test_agent_houdt_een_nummer_dat_alleen_de_eigen_deal_draagt():
    nep = Nep(mappen={"5600 Design": ["5609 Kessel-Losesteenweg 7.docx"]}, reserveringen=[res("5609", 14531, 20)])
    nep.call = lambda naam, **kw: ({"aantal": 1, "dossiers": [{"nummer": "5609", "deal_id": 14531}]}
                                   if naam == "voorbereidingen" else {"aantal": 0, "dossiers": []})
    assert met(nep, lambda: ca.volgend_vrij_nummer("regularisatie", 2026, deal_id=14531)) == "5609"
    assert met(nep, lambda: ca.volgend_vrij_nummer("regularisatie", 2026, deal_id=777)) == "5610"


def test_runbook_titel_staat_er_al_nul_puts():
    for _ in range(2):                                                    # herhalen: nooit een dubbele actie
        uit, pd = voer({}, titel_nu="2621 Testklant")
        assert pd.puts == [] and "reeds voldaan" in uit[0] and "2621 Testklant" in uit[1], uit
        assert pd.gelezen == [("harchitects", "/deals/900101")]


def test_runbook_reconciliatie_alleen_als_alles_klopt():
    oud_voorstel = lambda pad: {"ok": False, "reconciliatie": True, "nummer": "2621", "deal_id": "900101",
                                "reden": "geen actieve reservering"}
    uit, pd = voer({}, bord=oud_voorstel, titel_nu="2621 Testklant")
    assert pd.puts == [] and "reeds voldaan" in uit[0], uit
    uit, pd = voer({}, bord=oud_voorstel, titel_nu="Testklant")           # er moet iets geschreven worden
    assert isinstance(uit, R.NummerConflict) and "Opnieuw voorleggen" in str(uit) and pd.puts == []
    uit, pd = voer({}, bord=oud_voorstel, titel_nu="2621 Testklant", nep=Nep(fout="pipedrive"))   # onvolledig bewijs
    assert isinstance(uit, R.NummerConflict) and pd.puts == []


def test_runbook_open_voorstel_of_andere_deal_blijft_dicht():
    open_ = lambda pad: {"ok": False, "nummer": "2621", "deal_id": "900101", "reden": "voorstel staat op 'open'"}
    uit, pd = voer({}, bord=open_, titel_nu="2621 Testklant")             # geen automatisch akkoord
    assert isinstance(uit, R.NummerConflict) and pd.puts == []
    uit, pd = voer({}, titel_nu="2621 Testklant", nep=Nep(deals={"open": ["2621 Andere klant"]}))
    assert isinstance(uit, R.NummerConflict) and pd.puts == []
    uit, pd = voer({}, titel_nu="2621 Testklant", deal_gelezen=900999)    # andere deal gelezen
    assert isinstance(uit, R.NummerConflict) and pd.puts == []
    uit, pd = voer({}, titel_nu="2621 Andere titel")                      # zelfde nummer, andere titel: gewone PUT
    assert len(pd.puts) == 1


if __name__ == "__main__":
    fouten = 0
    for naam, fn in sorted(globals().items()):
        if naam.startswith("test_") and callable(fn):
            try:
                fn()
                print("   geslaagd  %s" % naam)
            except AssertionError as e:
                fouten += 1
                print("   MISLUKT   %s: %s" % (naam, e))
    print("%d van de %d grendels mislukt" % (fouten, sum(1 for n in globals() if n.startswith("test_"))))
    sys.exit(1 if fouten else 0)
