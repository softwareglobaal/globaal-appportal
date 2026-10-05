"""Grendels op de nummeruitgifte van de Contracten-agent (codering WP2a, 05-10-2026).

Het volgende vrije H-A-nummer komt uit de reeks van het volledige jaar (JJ, regularisatie JJ+30) en uit vier
bronnen die VOLLEDIG gelezen zijn: contractmappen van die reeks, dashboard, voorbereidingen en alle H-A-deals
in Pipedrive, alle pagina's. Een bron die niet volledig gelezen is, of een volle reeks: geen nummer.
Alleen het H-A-account (bedrijf-id 10068585). Nepbronnen; geen netwerk, geen databank, geen Pipedrive.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_nummeruitgifte.py
"""
import os
import sys

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import contracten_agent as ca  # noqa: E402
import pipedrive as P  # noqa: E402


class Nep:
    """Nepbronnen voor volgend_vrij_nummer; elke bron kan falen of onvolledig zijn."""

    def __init__(self, mappen=None, dossiers=(), aantal=None, voorbereidingen=(), deals=None,
                 fout=None, bedrijf=10068585):
        self.mappen = mappen or {}
        self.dossiers, self.aantal, self.voorbereidingen = list(dossiers), aantal, list(voorbereidingen)
        self.deals = deals or {}
        self.fout, self.bedrijf = fout, bedrijf
        self.gelezen = []

    def lijst(self, pad, recursief=True):
        if self.fout == "map":
            raise RuntimeError("Dropbox 500")
        self.gelezen.append(pad)
        naam = pad.rsplit("/", 1)[-1]
        return None if naam not in self.mappen else [{"name": n} for n in self.mappen[naam]]

    def call(self, naam, **args):
        if self.fout == "dashboard":
            raise RuntimeError("MCP onbereikbaar")
        if naam == "dossiers":
            return {"aantal": self.aantal if self.aantal is not None else len(self.dossiers),
                    "dossiers": [{"project_nummer": n} for n in self.dossiers]}
        if naam == "voorbereidingen":
            return {"dossiers": [{"nummer": n} for n in self.voorbereidingen]}
        raise AssertionError(naam)

    def alles(self, firma, pad, params=None):
        assert firma == "harchitects" and pad == "/deals"
        if self.fout == "pipedrive":
            raise RuntimeError("Pipedrive HTTP 500 op pagina 2")
        return [{"title": t} for t in self.deals.get(params["status"], [])]

    def controleer_bedrijf(self, firma, verwacht):
        if self.bedrijf != verwacht:
            raise RuntimeError(f"bedrijf {self.bedrijf}, verwacht {verwacht}")
        return self.bedrijf


def met(nep, fn):
    oud = (ca.bronnen_mod.lijst, ca.mcp.call, ca.pipedrive.alles, ca.pipedrive.controleer_bedrijf)
    ca.bronnen_mod.lijst, ca.mcp.call = nep.lijst, nep.call
    ca.pipedrive.alles, ca.pipedrive.controleer_bedrijf = nep.alles, nep.controleer_bedrijf
    try:
        return fn()
    finally:
        ca.bronnen_mod.lijst, ca.mcp.call, ca.pipedrive.alles, ca.pipedrive.controleer_bedrijf = oud


def fout_bij(nep, **kw):
    try:
        uit = met(nep, lambda: ca.volgend_vrij_nummer(**kw))
    except ca.NummerFout as e:
        return str(e)
    raise AssertionError(f"verwacht een NummerFout, kreeg nummer {uit}")


def test_alle_bronnen_samen_ook_een_latere_status():
    nep = Nep(mappen={"2026 Design": ["2601 Teststraat 1, 3000 Leuven.docx"], "2026 Signed": ["2603 Proeflaan 2.pdf"]},
              dossiers=["2605", "PROEF-2690"], voorbereidingen=["2607"],
              deals={"open": ["2610 Testklant", "Testklant zonder nummer"], "won": ["2614 Testklant"], "lost": ["2620 Testklant"]})
    bewijs = {}
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, bewijs)) == "2621"
    assert bewijs["per_bron"] == {"contractmappen": 2, "dashboard": 1, "voorbereidingen": 1,
                                  "pipedrive open": 1, "pipedrive won": 1, "pipedrive lost": 1}


def test_meer_dan_500_deals_en_een_nummer_op_een_latere_pagina():
    deals = [f"Testklant {i}" for i in range(1200)]
    deals[1100] = "2640 Testklant op pagina drie"
    nep = Nep(deals={"open": deals})
    bewijs = {}
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026, bewijs)) == "2641"
    assert bewijs["deals"]["open"] == 1200


def test_paginering_leest_alle_paginas_of_faalt():
    paginas = {0: (500, True, 500), 500: (500, True, 1000), 1000: (200, False, None)}

    def nep_vraag(firma, method, path, params=None, body=None):
        n, meer, volgend = paginas[params["start"]]
        titels = [f"x {params['start'] + i}" for i in range(n)]
        if params["start"] == 1000:
            titels[150] = "2647 Testklant"
        return {"success": True, "data": [{"title": t} for t in titels],
                "additional_data": {"pagination": {"more_items_in_collection": meer, "next_start": volgend}}}
    oud = P._vraag
    P._vraag = nep_vraag
    try:
        alle = P.alles("harchitects", "/deals", {"status": "open"})
        assert len(alle) == 1200 and any(d["title"] == "2647 Testklant" for d in alle)
        paginas[500] = (500, True, None)          # paginering zonder volgende start: niet volledig
        try:
            P.alles("harchitects", "/deals", {"status": "open"})
            raise AssertionError("onvolledige paginering gaf geen fout")
        except RuntimeError:
            pass
    finally:
        P._vraag = oud


def test_bronstoring_geeft_geen_nummer():
    assert "contractmap" in fout_bij(Nep(fout="map"), soort="architectuur", jaar=2026)
    assert "dashboard" in fout_bij(Nep(fout="dashboard"), soort="architectuur", jaar=2026)
    assert "Pipedrive" in fout_bij(Nep(fout="pipedrive"), soort="architectuur", jaar=2026)
    assert "niet volledig" in fout_bij(Nep(dossiers=["2601"], aantal=640), soort="architectuur", jaar=2026)


def test_alleen_het_h_a_account():
    assert "10068585" in fout_bij(Nep(bedrijf=13811111), soort="architectuur", jaar=2026)


def test_volle_reeks_is_een_uitdrukkelijke_fout_nooit_2700():
    melding = fout_bij(Nep(deals={"won": ["2699 Testklant"]}), soort="architectuur", jaar=2026)
    assert "vol" in melding and "2700" not in melding
    melding = fout_bij(Nep(deals={"won": ["5699 Testklant"]}), soort="regularisatie", jaar=2026)
    assert "vol" in melding


def test_toekomstige_jaren_en_regularisatiereeksen():
    leeg = Nep()
    assert met(leeg, lambda: ca.volgend_vrij_nummer("architectuur", 2027)) == "2701"
    assert met(leeg, lambda: ca.volgend_vrij_nummer("addendum", 2027)) == "2701"
    assert met(leeg, lambda: ca.volgend_vrij_nummer("regularisatie", 2027)) == "5701"
    assert met(leeg, lambda: ca.volgend_vrij_nummer("architectuur", 2030)) == "3001"
    assert met(leeg, lambda: ca.volgend_vrij_nummer("regularisatie", 2030)) == "6001"
    nep = Nep(deals={"open": ["5703 Testklant", "2703 Testklant"]})
    assert met(nep, lambda: ca.volgend_vrij_nummer("regularisatie", 2027)) == "5704"


def test_mappen_van_de_reeks_zoals_het_contractsysteem_ze_kiest():
    assert ca.contract_mappen("architectuur", "27") == [f"{ca.CONTRACTS_PAD}/2027 Design", f"{ca.CONTRACTS_PAD}/2027 Signed"]
    assert ca.contract_mappen("regularisatie", "56") == [f"{ca.CONTRACTS_PAD}/5600 Design", f"{ca.CONTRACTS_PAD}/5600 Signed"]
    assert ca.contract_mappen("architectuur", "30")[0].endswith("/2030 Design")      # 30 is architectuur in 2030
    nep = Nep()
    bewijs = {}
    met(nep, lambda: ca.volgend_vrij_nummer("regularisatie", 2026, bewijs))
    assert nep.gelezen == ca.contract_mappen("regularisatie", "56")
    assert bewijs["ontbrekende_mappen"] == nep.gelezen                              # 409: map bestaat niet


def test_jaar_komt_uit_de_kalender_niet_uit_een_getal_in_de_tekst():
    nep = Nep(deals={"open": ["2026 Testklant", "Kickoff 2026", "2612 Testklant"]})
    assert met(nep, lambda: ca.volgend_vrij_nummer("architectuur", 2026)) == "2613"


def test_alleen_het_berekende_nummer_mag_als_voorstel_naar_het_bord():
    assert ca.nummervoorstel_toegelaten("2615", "2615")
    assert not ca.nummervoorstel_toegelaten("2699", "2615")      # het model koos zelf
    assert not ca.nummervoorstel_toegelaten("2615", "")          # bronfout: geen nummer
    assert not ca.nummervoorstel_toegelaten("null", "2615")
    assert not ca.nummervoorstel_toegelaten(None, "2615")


def test_nummer_uit_titel_leest_elk_jaar():
    assert ca.nummer_uit_titel("2503 Testklant", 2026) == "2503"
    assert ca.nummer_uit_titel("5703 Testklant", 2027) == "5703"
    assert ca.nummer_uit_titel("6003 Testklant", 2030) == "6003"
    assert ca.nummer_uit_titel("Testklant 2603", 2026) == ""       # niet vooraan: geen dealnummer (D9)


def test_runbook_aanvaardt_elk_geldig_h_a_nummer_en_controleert_het_account():
    sys.path.insert(0, os.path.join(HIER, "runbooks"))
    import pipedrive_dealtitel as R
    geschreven, gecontroleerd = [], []
    oud = (R.pipedrive.schrijf, R.pipedrive.controleer_bedrijf, R.nummerlezer.jaar_nu_brussel)
    R.pipedrive.schrijf = lambda firma, m, pad, body=None, params=None: (geschreven.append((firma, pad, body)), "ok")
    R.pipedrive.controleer_bedrijf = lambda firma, verwacht: gecontroleerd.append((firma, verwacht)) or verwacht
    R.nummerlezer.jaar_nu_brussel = lambda: 2026          # vaste kalender: 2803 blijft ook in 2027 een fout hier
    try:
        for titel in ("2465 Testklant", "2703 Testklant", "5603 Testklant"):
            R.voer_uit({"deal_id": 900001, "titel": titel})
        for titel in ("46125 Testklant", "Testklant", "2603", "2803 Testklant"):
            try:
                R.voer_uit({"deal_id": 900001, "titel": titel})
                raise AssertionError(f"runbook aanvaardde '{titel}'")
            except ValueError:
                pass
    finally:
        R.pipedrive.schrijf, R.pipedrive.controleer_bedrijf, R.nummerlezer.jaar_nu_brussel = oud
    assert [b["title"] for _, _, b in geschreven] == ["2465 Testklant", "2703 Testklant", "5603 Testklant"]
    assert gecontroleerd == [("harchitects", 10068585)] * 3


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
