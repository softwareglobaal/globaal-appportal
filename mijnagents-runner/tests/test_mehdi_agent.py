"""Grendels op Ai Angel, technisch mehdi-agent (ontwerp docs/ontwerp-mehdi-agent.md, 31-10-2026).

Mehdi's opdracht: de agent leest alleen de dagbundel, zet taken klaar, schrijft concepten, zegt voor wie een taak is
(Mehdi, een collega of een agent), leert van zijn correcties en geeft 's ochtends een plan en 's avonds een overzicht
met een tip. Deze test legt vast:

- goed: een taak met een bron die letterlijk in de dagbundel staat, komt in de lijst, met een nummer;
- fout: een taak met een verzonnen bron valt weg; een collega die niet in kern staat of een agent die niet op het bord
  staat, wordt Mehdi; iets privé gaat nooit naar een ander;
- een nummer uit de lijst ("2 is gedaan") sluit de juiste taak; regels leert hij alleen uit wat Mehdi zei;
- zonder dagbundel: nood en niets klaargezet; Claude onbereikbaar: de lijst blijft staan, met een nood;
- tussendoor zonder nieuws: geen aanroep van Claude; ochtend en avond een keer per dag, op de Brusselse klok;
- titels en werkverslag zonder namen; een opgepakt item krijgt de nieuwe versie ernaast;
- de werkwijze haalt de norm (N1, N2, N8, N9), de runner gaat door de gedeelde ronde, het schema is strikt.

Geen netwerk: Claude, het bord en kern zijn nagebootst. Alle namen zijn verzonnen.
Draaien: python3 mijnagents-runner/tests/test_mehdi_agent.py
"""
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402
import mehdi_agent as M  # noqa: E402

WERKWIJZE = os.path.join(RUNNER, "werkwijze", "mehdi-agent.md")
OCHTEND_UTC = datetime(2026, 10, 31, 6, 20, tzinfo=timezone.utc)      # 07:20 in Brussel (wintertijd)
MIDDAG_UTC = datetime(2026, 10, 31, 12, 20, tzinfo=timezone.utc)      # 13:20
NAMIDDAG_UTC = datetime(2026, 10, 31, 15, 20, tzinfo=timezone.utc)    # 16:20
AVOND_UTC = datetime(2026, 10, 31, 18, 20, tzinfo=timezone.utc)       # 19:20
GISTEREN = "2026-10-30"

DAGBESTAND = """# Dag 2026-10-30 vastgesteld

## Gepland

- 10:00 Werfbezoek Proefstraat: ging door (auto ter plaatse)
- 14:00 (privé): geen spoor. Ging dit door?

## Niet gepland

- 16:10 telefoon met Klant Omega, 12 min
- 18:00 privégesprek, 20 min

## Communicatie

- gesprekken gezien in Zoom, Fathom en Plaud: 1, 45 min (1 met opname, 0 alleen in Zoom); De Zoomwacht: volledig gelezen
- WhatsApp: 40 berichten in 6 gesprekken, 2 oproepen, 5 min gezien
- telefoon: 3 oproepen, 15 min gezien
- mail: 25 binnen, 4 verzonden (uniek over alle postvakken)

## Gesprekken in Zoom, Fathom en Plaud

- 11:00 Fathom, met Klant Omega, 45 min: Offerte renovatie. Actiepunten: Mehdi stuurt de offerte voor vrijdag; Zeta tekent het plan. Verwijzing fathom:9001

## Over deze vaststelling

- versie 2, gemaakt 31-10-2026 00:31
"""
TELLING = {"dag": GISTEREN, "whatsapp": {"berichten": 40}, "telefoon": {"oproepen": 3}}
KERN = [
    {"naam": "Proefpersoon Zeta", "voornaam": "Zeta", "functie": "tekenaar", "afdeling": "Architecture", "firma": "Proeffirma"},
    {"naam": "Proefpersoon Eta", "voornaam": "Eta", "functie": "boekhouder", "afdeling": "Finance", "firma": "Proeffirma"},
]
AGENTS = [{"naam": "zoom-wacht", "label": "De Zoomwacht", "afdeling": "regie", "rol": "zoekt Zoom-gesprekken", "cadans": ""}]


class NepRonde:
    def __init__(self, werkwijze=None):
        self.werkwijze = open(WERKWIJZE, encoding="utf-8").read() if werkwijze is None else werkwijze
        self.detail = ""
        self.noden = []
        self.bronnen = {}
        self.collegas = list(AGENTS)
        self.lessen = [{"id": "L1", "les": "Kijk naar de uitkomst in het systeem."}]

    def nood(self, tekst, wie="mehdi"):
        self.noden.append((tekst, wie))

    def bron(self, naam, inhoud):
        self.bronnen[naam] = inhoud


def taak(tekst, bron, voor="mehdi", wie="", status="open", tid="", prioriteit="normaal", concept="", waarom="omdat"):
    return {"id": tid, "tekst": tekst, "voor": voor, "wie": wie, "waarom": waarom, "bron": bron, "dag": GISTEREN,
            "prioriteit": prioriteit, "status": status, "concept": concept}


def antwoord(taken=(), overzicht="", tip="", geleerd=(), ontbreekt=()):
    return {"taken": list(taken), "overzicht": overzicht, "tip": tip, "geleerd": list(geleerd), "ontbreekt": list(ontbreekt)}


class Omgeving:
    """Een tijdelijke map met de dagbundel en de staat, en nagebootste Claude, bord en kern."""

    def __init__(self, bundel=True):
        self.map = tempfile.mkdtemp(prefix="mehdi-agent-test-")
        self.staat = os.path.join(self.map, "staat", "staat.json")
        if bundel:
            os.makedirs(os.path.join(self.map, "2026"))
            with open(os.path.join(self.map, "2026", f"{GISTEREN}.md"), "w", encoding="utf-8") as f:
                f.write(DAGBESTAND)
            with open(os.path.join(self.map, "2026", f"{GISTEREN}.json"), "w", encoding="utf-8") as f:
                json.dump(TELLING, f)
        self.bord = {}            # uniek -> item zoals het bord het bewaart
        self.opgepakt = set()
        self.claude_oproepen = []
        self.gezegd = []

    def weg(self):
        shutil.rmtree(self.map, ignore_errors=True)

    def zet(self, items):
        for it in items:
            if it["uniek"] in self.opgepakt:
                continue          # het bord laat een opgepakt item staan
            self.bord[it["uniek"]] = dict(it, status="klaar", id=self.bord.get(it["uniek"], {}).get("id") or len(self.bord) + 1)
        return {"nieuw": len(items)}

    def lees(self, uniek):
        x = self.bord.get(uniek)
        if x is None:
            return []
        return [dict(x, status="opgepakt" if uniek in self.opgepakt else "klaar")]

    def ronde(self, uit=None, nu=OCHTEND_UTC, moment=None, fout=None, werkwijze=None):
        r = NepRonde(werkwijze)

        def claude(system, inhoud):
            self.claude_oproepen.append((system, inhoud))
            if fout:
                raise fout
            return (uit if uit is not None else antwoord()), {"tokens_in": 100, "tokens_uit": 50}

        staat = M.werk(r, nu=nu, map_=self.map, gezegd=lambda nu: list(self.gezegd), kern=lambda: list(KERN),
                       claude=claude, zet=self.zet, lees=self.lees, staatpad=self.staat, kies_moment=moment)
        return r, staat


def test_werkwijze_haalt_de_norm_en_runner_door_de_ronde():
    ww = open(WERKWIJZE, encoding="utf-8").read()
    nooit, mehdi = bord.grenzen(ww)
    assert len(nooit) >= 5 and len(mehdi) >= 4, (nooit, mehdi)
    assert len(ww) >= 500
    spec = importlib.util.spec_from_file_location("nieuwe_agent", os.path.join(RUNNER, "nieuwe-agent.py"))
    na = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(na)
    kaart = {"naam": "mehdi-agent", "label": "Ai Angel", "rol": "zet taken klaar", "mandaat": "lezen en klaarzetten",
             "cadans": "zes keer per dag", "mag": ["taken klaarzetten"], "grenzen": ["nooit iets versturen"]}
    assert na.controleer(kaart, ww) == []
    bron = open(os.path.join(RUNNER, "mehdi_agent.py"), encoding="utf-8").read()
    assert 'with ag.ronde("taken klaarzetten") as r:' in bron
    for tekst in (ww, bron):
        assert "\N{EM DASH}" not in tekst and "\N{EN DASH}" not in tekst


def test_schema_is_strikt():
    def kijk(s):
        if s.get("type") == "object":
            assert s["additionalProperties"] is False
            assert sorted(s["required"]) == sorted(s["properties"]), s["required"]
            for v in s["properties"].values():
                kijk(v)
        if s.get("type") == "array":
            kijk(s["items"])
    kijk(M.SCHEMA)


def test_zonder_dagbundel_nood_en_niets_klaargezet():
    o = Omgeving(bundel=False)
    try:
        r, staat = o.ronde(uit=antwoord([taak("Bel terug", "telefoon met Klant Omega")]))
        assert staat is None and o.bord == {} and o.claude_oproepen == []
        assert r.noden == [("Geen dagbundel gevonden van vandaag of de twee dagen ervoor", "claude-code")]
    finally:
        o.weg()


def test_taak_met_bron_komt_erin_en_verzonnen_bron_niet():
    o = Omgeving()
    try:
        r, staat = o.ronde(uit=antwoord([
            taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega, 12 min", prioriteit="hoog",
                 concept="Dag, ik zag je oproep. Wanneer past het om even te bellen?"),
            taak("Stuur de factuur naar Klant Sigma", "mail van Klant Sigma over de factuur"),
        ]))
        teksten = [t["tekst"] for t in staat["taken"].values()]
        assert teksten == ["Bel Klant Omega terug"], teksten
        assert "zonder bron geweigerd" in r.detail and "1 nieuw" in r.detail, r.detail
        lijst = o.bord[f"mehdi-agent:taken:2026-10-31"]
        assert lijst["soort"] == "taken" and lijst["voor"] == "mehdi"
        assert "1. Bel Klant Omega terug (hoog)" in lijst["inhoud"]
        assert "Concept: Dag, ik zag je oproep." in lijst["inhoud"]
        assert staat["nummers"] == {"1": next(iter(staat["taken"]))}
    finally:
        o.weg()


def test_bron_met_datum_of_weglating_telt_wel():
    corpus = M.normaal(DAGBESTAND)
    assert M.bron_in("2026-10-30, 16:10 telefoon met Klant Omega", corpus)
    assert M.bron_in("Mehdi stuurt de offerte ... Verwijzing fathom:9001", corpus)
    assert M.bron_in("\"Offerte renovatie\"", corpus)
    assert not M.bron_in("fathom:9002", corpus)
    assert not M.bron_in("tel", corpus)            # te kort om iets te bewijzen
    assert not M.bron_in("", corpus)


def test_collega_uit_kern_en_onbekende_wordt_mehdi():
    o = Omgeving()
    try:
        _, staat = o.ronde(uit=antwoord([
            taak("Teken het plan voor Klant Omega", "Zeta tekent het plan", voor="collega", wie="Zeta",
                 concept="Zeta, kan jij het plan voor Klant Omega tekenen?"),
            taak("Maak de offerte op", "Offerte renovatie", voor="collega", wie="Proefpersoon Onbekend"),
        ]))
        per = {t["tekst"]: (t["voor"], t["wie"]) for t in staat["taken"].values()}
        assert per["Teken het plan voor Klant Omega"] == ("collega", "Proefpersoon Zeta"), per
        assert per["Maak de offerte op"] == ("mehdi", ""), per
        lijst = o.bord["mehdi-agent:taken:2026-10-31"]["inhoud"]
        assert "## Voor een collega" in lijst and "Proefpersoon Zeta: Teken het plan" in lijst
    finally:
        o.weg()


def test_agent_op_naam_of_label_en_onbekende_agent_wordt_mehdi():
    o = Omgeving()
    try:
        _, staat = o.ronde(uit=antwoord([
            taak("Zoek de opname van het gesprek met Klant Omega", "Verwijzing fathom:9001", voor="agent", wie="Zoomwacht"),
            taak("Maak een werfverslag van het bezoek", "10:00 Werfbezoek Proefstraat", voor="agent", wie="De Verzonnen Agent"),
        ]))
        per = {t["tekst"]: (t["voor"], t["wie"]) for t in staat["taken"].values()}
        assert per["Zoek de opname van het gesprek met Klant Omega"] == ("agent", "De Zoomwacht"), per
        assert per["Maak een werfverslag van het bezoek"] == ("mehdi", ""), per
    finally:
        o.weg()


def test_prive_gaat_nooit_naar_een_ander():
    o = Omgeving()
    try:
        _, staat = o.ronde(uit=antwoord([
            taak("Vraag of de afspraak van 14:00 doorging", "14:00 (privé): geen spoor", voor="collega", wie="Zeta"),
        ]))
        (t,) = staat["taken"].values()
        assert (t["voor"], t["wie"]) == ("mehdi", ""), t
    finally:
        o.weg()


def test_nummer_uit_de_lijst_sluit_de_juiste_taak():
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega", prioriteit="hoog"),
                              taak("Stuur de offerte", "Mehdi stuurt de offerte voor vrijdag")]))
        staat = M.laad_staat(o.staat)
        nummer_offerte = next(nr for nr, tid in staat["nummers"].items() if staat["taken"][tid]["tekst"] == "Stuur de offerte")
        o.gezegd = [{"id": 7, "ts": "2026-10-31T11:00", "tekst": f"{nummer_offerte} is gedaan", "antwoord": "Genoteerd."}]
        _, staat = o.ronde(nu=MIDDAG_UTC, uit=antwoord([taak("Stuur de offerte", "", status="gedaan", tid=nummer_offerte,
                                                             waarom="Mehdi zei dat het gedaan is")]))
        assert [t["tekst"] for t in staat["taken"].values()] == ["Bel Klant Omega terug"]
        assert staat["afgerond"][-1]["tekst"] == "Stuur de offerte" and staat["afgerond"][-1]["status"] == "gedaan"
        lijst = o.bord["mehdi-agent:taken:2026-10-31"]["inhoud"]
        assert "## Afgerond vandaag" in lijst and "- Stuur de offerte (gedaan)" in lijst
    finally:
        o.weg()


def test_dezelfde_taak_twee_keer_wordt_niet_dubbel():
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        o.gezegd = [{"id": 8, "ts": "2026-10-31T11:00", "tekst": "dank je", "antwoord": ""}]   # iets nieuws: wel een ronde
        _, staat = o.ronde(nu=MIDDAG_UTC, uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        assert len(staat["taken"]) == 1
    finally:
        o.weg()


def test_tussendoor_zonder_nieuws_roept_claude_niet_aan():
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        assert len(o.claude_oproepen) == 1
        o.bord.clear()
        r, _ = o.ronde(nu=MIDDAG_UTC)
        assert len(o.claude_oproepen) == 1 and o.bord == {}
        assert "niets nieuw" in r.detail, r.detail
    finally:
        o.weg()


def test_overgeslagen_ronde_laat_een_logregel():
    """ANGEL-10 (T-0120): een overgeslagen ronde liet op 01-11 geen spoor in het werkverslag, alleen een hartslag."""
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        o.bord.clear()
        M.ag._log.clear()
        o.ronde(nu=MIDDAG_UTC)
        assert len(o.claude_oproepen) == 1 and o.bord == {}
        assert [(x["onderwerp"], x["stap"], x["tekst"]) for x in M.ag._log] == [
            ("ronde", "melding", "overgeslagen: niets nieuw in de dagbundel")], M.ag._log
    finally:
        M.ag._log.clear()
        o.weg()


def test_ochtend_en_avond_een_keer_per_dag_op_de_brusselse_klok():
    vandaag = "2026-10-31"
    assert M.moment(OCHTEND_UTC, {}) == "ochtend"
    assert M.moment(OCHTEND_UTC, {"ochtend": vandaag}) == "tussendoor"
    assert M.moment(MIDDAG_UTC, {}) == "tussendoor"
    assert M.moment(AVOND_UTC, {}) == "avond"
    assert M.moment(AVOND_UTC, {"avond": vandaag}) == "tussendoor"
    assert M.aan_de_beurt(OCHTEND_UTC) and not M.aan_de_beurt(datetime(2026, 10, 31, 5, 20, tzinfo=timezone.utc))
    assert M.aan_de_beurt(datetime(2026, 7, 1, 5, 20, tzinfo=timezone.utc))       # zomertijd: 07:20 in Brussel
    assert M.dagen_terug(datetime(2026, 10, 31, 23, 30, tzinfo=timezone.utc)) == ["2026-11-01", "2026-10-31", "2026-10-30"]


def test_avondoverzicht_klaar_voor_de_avondbundel_van_de_bode():
    """ANGEL-4 (T-0120): De Bode bundelt het avondbericht vanaf 17:00 (bode.py, AVOND_VANAF). Het avondoverzicht van de
    ronde van 19:20 kwam daardoor pas de volgende dag mee. Nu is de ronde van 16:20 de avond."""
    import ast
    bode = ast.parse(open(os.path.join(RUNNER, "bode.py"), encoding="utf-8").read())
    (vanaf,) = [ast.literal_eval(n.value) for n in bode.body if isinstance(n, ast.Assign)
                and [getattr(t, "id", "") for t in n.targets] == ["AVOND_VANAF"]]
    eerste = min(u for u in M.UREN if u >= M.AVOND)
    assert (eerste, 20) < tuple(vanaf), (eerste, vanaf)          # de cron draait op :20
    assert M.moment(NAMIDDAG_UTC, {}) == "avond"
    assert M.moment(AVOND_UTC, {"avond": "2026-10-31"}) == "tussendoor"
    assert M.moment(MIDDAG_UTC, {}) == "tussendoor"
    ww = open(WERKWIJZE, encoding="utf-8").read()
    assert "na 19:00" not in ww and "vanaf 16:00" in ww
    o = Omgeving()
    try:
        _, staat = o.ronde(nu=NAMIDDAG_UTC, uit=antwoord([], overzicht="Vandaag bleef een oproep liggen.", tip="Bel na."))
        assert o.bord["mehdi-agent:avond:2026-10-31"]["titel"] == "Avondoverzicht 31-10" and staat["avond"] == "2026-10-31"
    finally:
        o.weg()


def test_ochtend_geeft_plan_en_avond_een_tip():
    o = Omgeving()
    try:
        _, staat = o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")],
                                        overzicht="1. Eerst Klant Omega terugbellen."))
        ochtend = o.bord["mehdi-agent:ochtend:2026-10-31"]
        assert ochtend["soort"] == "verslag" and ochtend["titel"] == "Te doen vandaag 31-10"
        assert ochtend["inhoud"].startswith("1. Eerst Klant Omega terugbellen.") and "## Alle open taken" in ochtend["inhoud"]
        assert staat["ochtend"] == "2026-10-31"
        o.gezegd = [{"id": 9, "ts": "2026-10-31T17:00", "tekst": "goed zo", "antwoord": ""}]
        _, staat = o.ronde(nu=AVOND_UTC, uit=antwoord([], overzicht="Vandaag bleef een oproep liggen.",
                                                      tip="Plan een vast belmoment na je afspraken."))
        avond = o.bord["mehdi-agent:avond:2026-10-31"]
        assert avond["titel"] == "Avondoverzicht 31-10" and "Tip: Plan een vast belmoment" in avond["inhoud"]
        assert staat["avond"] == "2026-10-31"
        assert "Het is avond." in o.claude_oproepen[-1][1]["opdracht"]
    finally:
        o.weg()


def test_titels_en_werkverslag_zonder_namen():
    o = Omgeving()
    try:
        r, _ = o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega"),
                                     taak("Teken het plan", "Zeta tekent het plan", voor="collega", wie="Zeta")],
                                    overzicht="Klant Omega eerst.", ontbreekt=["de inhoud van het gesprek met Klant Omega"]))
        for it in o.bord.values():
            for naam in ("Omega", "Zeta"):
                assert naam not in it["titel"], it["titel"]
        for naam in ("Omega", "Zeta"):
            assert naam not in r.detail, r.detail
        for regel in M.ag._log:
            assert "Omega" not in regel["tekst"] and "Zeta" not in regel["tekst"], regel
        assert "## Wat ik miste in de dagbundel" in o.bord["mehdi-agent:taken:2026-10-31"]["inhoud"]
    finally:
        M.ag._log.clear()
        o.weg()


def test_claude_onbereikbaar_lijst_blijft_met_nood():
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        vinger = M.laad_staat(o.staat)["vingerafdruk"]
        o.gezegd = [{"id": 10, "ts": "2026-10-31T11:00", "tekst": "nog iets?", "antwoord": ""}]
        r, staat = o.ronde(nu=MIDDAG_UTC, fout=RuntimeError("verbinding weg"))
        assert ("Claude niet bereikbaar voor de takenlijst", "claude-code") in r.noden
        assert [t["tekst"] for t in staat["taken"].values()] == ["Bel Klant Omega terug"]
        assert "Bel Klant Omega terug" in o.bord["mehdi-agent:taken:2026-10-31"]["inhoud"]
        assert M.laad_staat(o.staat)["vingerafdruk"] == vinger          # de volgende ronde probeert opnieuw
        r, _ = o.ronde(nu=MIDDAG_UTC, fout=M.Weigering("nee"))
        assert ("Claude weigerde de takenlijst te maken", "claude-code") in r.noden
    finally:
        M.ag._log.clear()
        o.weg()


def test_regels_leert_hij_alleen_uit_wat_mehdi_zei():
    o = Omgeving()
    try:
        _, staat = o.ronde(uit=antwoord([], geleerd=["Offertes gaan naar Proefpersoon Eta"]))
        assert staat["geleerd"] == []
        o.gezegd = [{"id": 11, "ts": "2026-10-31T11:00", "tekst": "offertes gaan voortaan naar Eta", "antwoord": ""}]
        _, staat = o.ronde(nu=MIDDAG_UTC, uit=antwoord([], geleerd=["Offertes gaan naar Proefpersoon Eta",
                                                                    "offertes gaan naar proefpersoon eta"]))
        assert staat["geleerd"] == ["Offertes gaan naar Proefpersoon Eta"]
        assert o.claude_oproepen[-1][1]["wat_mehdi_zei"][0]["tekst"] == "offertes gaan voortaan naar Eta"
    finally:
        o.weg()


def test_te_veel_nieuwe_taken_wordt_begrensd():
    o = Omgeving()
    try:
        veel = [taak(f"Taak nummer {i}", "16:10 telefoon met Klant Omega") for i in range(20)]
        _, staat = o.ronde(uit=antwoord(veel))
        assert len(staat["taken"]) == M.MAX_NIEUW
    finally:
        o.weg()


def test_opgepakt_item_krijgt_de_nieuwe_versie_ernaast():
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        o.opgepakt.add("mehdi-agent:taken:2026-10-31")
        o.gezegd = [{"id": 12, "ts": "2026-10-31T11:00", "tekst": "en de offerte?", "antwoord": ""}]
        r, _ = o.ronde(nu=MIDDAG_UTC, uit=antwoord([taak("Stuur de offerte", "Mehdi stuurt de offerte voor vrijdag")]))
        assert "mehdi-agent:taken:2026-10-31:1320" in o.bord, sorted(o.bord)
        assert "Stuur de offerte" in o.bord["mehdi-agent:taken:2026-10-31:1320"]["inhoud"]
        assert not [n for n in r.noden if "staat niet zo op het bord" in n[0]], r.noden
    finally:
        o.weg()


def test_zonder_grenzen_geen_werk():
    o = Omgeving()
    try:
        r, staat = o.ronde(werkwijze="# Werkwijze\n\nIk zet taken klaar.\n")
        assert staat is None and o.bord == {} and o.claude_oproepen == [] and r.noden[0][1] == "mehdi"
    finally:
        o.weg()


def test_invoer_en_systeem():
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        system, inhoud = o.claude_oproepen[0]
        assert "=== JOUW WERKWIJZE ===" in system and "## Wat ik nooit doe" in system
        assert "De Zoomwacht (zoom-wacht, regie)" in system and "L1: Kijk naar de uitkomst" in system
        assert inhoud["moment"] == "ochtend" and inhoud["vandaag"] == "2026-10-31"
        assert inhoud["dagbundel"][0]["dag"] == GISTEREN and "Offerte renovatie" in inhoud["dagbundel"][0]["dagbestand"]
        assert inhoud["collegas"][0] == {"naam": "Proefpersoon Zeta", "functie": "tekenaar", "afdeling": "Architecture",
                                         "firma": "Proeffirma"}
        json.dumps(inhoud)          # moet als JSON naar het model kunnen
    finally:
        o.weg()


def test_vraag_claude_met_nagebootste_client():
    class Blok:
        type = "text"

        def __init__(self, text):
            self.text = text

    class Antwoord:
        def __init__(self, stop, tekst):
            self.stop_reason, self.model = stop, M.MODEL
            self.content = [Blok(tekst)]
            self.usage = type("U", (), {"input_tokens": 10, "output_tokens": 5})()

    class Client:
        def __init__(self, stop, tekst):
            self.stop, self.tekst, self.kwargs = stop, tekst, None
            self.beta = type("B", (), {})()
            self.beta.messages = self

        def create(self, **kwargs):
            self.kwargs = kwargs
            return Antwoord(self.stop, self.tekst)

    c = Client("end_turn", json.dumps(antwoord()))
    uit, meta = M.vraag_claude("systeem", {"a": 1}, client=c)
    assert uit == antwoord() and meta["tokens_in"] == 10
    assert c.kwargs["model"] == M.MODEL and c.kwargs["output_config"]["format"]["schema"] is M.SCHEMA
    assert c.kwargs["betas"] == ["server-side-fallback-2026-07-01"] and c.kwargs["fallbacks"] == "default"
    for stop, fout in (("refusal", M.Weigering), ("max_tokens", RuntimeError)):
        try:
            M.vraag_claude("systeem", {}, client=Client(stop, ""))
            raise AssertionError(f"geen fout bij {stop}")
        except fout:
            pass


# ANGEL-3 en VOL-17 (T-0120): Ai Angel kan op het Claude-abonnement van Mehdi draaien, zoals De Prijsonderzoeker. De
# route staat achter MEHDI_AGENT_ROUTE; de standaard blijft de API tot Mehdi kiest (werkstand T-0122). Geen echt model:
# de vraag aan het abonnement is nagebootst.
class NepAbonnement:
    """Bootst claude_abonnement.vraag na: geeft tekst zoals lees_stroom, of gooit een Fout."""

    def __init__(self, tekst="", fout=None):
        self.tekst, self.fout, self.oproepen = tekst, fout, []

    def __call__(self, systeem, gebruiker, **kw):
        self.oproepen.append((systeem, gebruiker, kw))
        if self.fout:
            raise self.fout
        return {"tekst": self.tekst, "gereedschap": [], "tokens": 1234, "beurten": 1, "stop": "success",
                "model": "nepmodel", "fout": None}


def test_route_staat_standaard_op_de_api_en_importeert_geen_sleutel_bovenaan():
    import ast
    assert M.ROUTE == "api", M.ROUTE                     # wat nu draait, tot Mehdi kiest (T-0122)
    bron = open(os.path.join(RUNNER, "mehdi_agent.py"), encoding="utf-8").read()
    assert 'os.environ.get("MEHDI_AGENT_ROUTE", "api")' in bron
    bovenaan = set()
    for n in ast.parse(bron).body:
        if isinstance(n, ast.Import):
            bovenaan |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            bovenaan.add((n.module or "").split(".")[0])
    assert not bovenaan & {"anthropic", "sleutelbron"}, bovenaan
    assert "claude_abonnement" in bovenaan


def test_abonnement_geeft_een_geldig_antwoord_zonder_api_sleutel():
    nep = NepAbonnement("```json\n" + json.dumps(antwoord([taak("Bel Klant Omega terug", "16:10 telefoon")])) + "\n```")
    weg = object()
    oud = {k: sys.modules.get(k, weg) for k in ("sleutelbron", "anthropic")}
    sys.modules["sleutelbron"] = None                    # elke import van de API-weg faalt nu meteen
    sys.modules["anthropic"] = None
    try:
        uit, meta = M.vraag_claude("regelboek", {"a": 1}, route="abonnement", vraag=nep)
    finally:
        for k, v in oud.items():
            if v is weg:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    assert uit["taken"][0]["tekst"] == "Bel Klant Omega terug"
    assert meta["tokens_in"] + meta["tokens_uit"] == 1234 and meta["model"] == "nepmodel"
    ((systeem, gebruiker, kw),) = nep.oproepen
    assert systeem.startswith("regelboek") and json.dumps(M.SCHEMA, ensure_ascii=False) in systeem
    assert json.loads(gebruiker) == {"a": 1} and kw["tools"] == () and kw["max_beurten"] <= 2
    uit, _ = M.vraag_claude("regelboek", {}, route="abonnement", vraag=NepAbonnement(json.dumps(antwoord())))
    assert uit == antwoord()                             # ook zonder codeblok


def test_abonnement_buiten_het_schema_of_geen_json_is_een_fout_zonder_inhoud():
    slecht = antwoord([taak("Bel Proefpersoon Zeta", "16:10 telefoon", voor="Proefpersoon Zeta")])
    extra = dict(antwoord(), uitleg="Proefpersoon Zeta")
    zonder = {k: v for k, v in antwoord().items() if k != "tip"}
    for tekst in (json.dumps(slecht), json.dumps(extra), json.dumps(zonder), "Ik kan dit niet.", "[]"):
        try:
            M.vraag_claude("regelboek", {}, route="abonnement", vraag=NepAbonnement(tekst))
            raise AssertionError(f"geen fout bij {tekst[:40]}")
        except RuntimeError as e:
            assert "Zeta" not in str(e), e              # de melding komt in het werkverslag: nooit een naam
    assert M.schema_fout(antwoord(), M.SCHEMA) == ""
    assert M.schema_fout(slecht, M.SCHEMA) == "antwoord.taken[0].voor: geen toegelaten waarde"


def test_abonnement_aan_zijn_limiet_of_niet_aangemeld_lijst_blijft_met_nood():
    import claude_abonnement as CA
    o = Omgeving()
    try:
        o.ronde(uit=antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega")]))
        for soort, nood, wie in (("limiet", CA.LIMIET_NOOD, "mehdi"), ("aanmelden", CA.AANMELDEN_NOOD, "mehdi"),
                                 ("bron", CA.BRON_NOOD, "claude-code"),
                                 (None, "Claude niet bereikbaar voor de takenlijst", "claude-code")):
            o.gezegd.append({"id": len(o.gezegd) + 20, "ts": "2026-10-31T11:00", "tekst": "nog iets?", "antwoord": ""})
            nep = NepAbonnement(fout=CA.Fout("Claude via het abonnement: proef", soort))
            r = NepRonde()
            staat = M.werk(r, nu=MIDDAG_UTC, map_=o.map, gezegd=lambda nu: list(o.gezegd), kern=lambda: list(KERN),
                           claude=lambda s, i: M.vraag_claude(s, i, route="abonnement", vraag=nep),
                           zet=o.zet, lees=o.lees, staatpad=o.staat)
            assert len(nep.oproepen) == 1 and r.noden == [(nood, wie)], (soort, r.noden)
            assert [t["tekst"] for t in staat["taken"].values()] == ["Bel Klant Omega terug"]
            assert "Bel Klant Omega terug" in o.bord["mehdi-agent:taken:2026-10-31"]["inhoud"]
    finally:
        M.ag._log.clear()
        o.weg()


def test_staat_wordt_atomair_bewaard_en_teruggelezen():
    d = tempfile.mkdtemp(prefix="mehdi-agent-staat-")
    try:
        pad = os.path.join(d, "a", "staat.json")
        staat = M.laad_staat(pad)
        assert staat == {"taken": {}, "afgerond": [], "geleerd": [], "nummers": {}}
        staat["taken"]["t-1"] = {"id": "t-1", "tekst": "proef"}
        M.bewaar_staat(staat, pad)
        assert M.laad_staat(pad)["taken"]["t-1"]["tekst"] == "proef"
        assert [f for f in os.listdir(os.path.dirname(pad)) if f.startswith(".staat-")] == []
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_droog_stil_toont_geen_namen_en_schrijft_het_volledige_resultaat_apart():
    import contextlib
    import io
    d = tempfile.mkdtemp(prefix="mehdi-agent-droog-")
    gisteren = M.dagen_terug(datetime.now(timezone.utc))[1]
    os.makedirs(os.path.join(d, gisteren[:4]))
    with open(os.path.join(d, gisteren[:4], f"{gisteren}.md"), "w", encoding="utf-8") as f:
        f.write(DAGBESTAND)
    oud = (M.DAGBOEK, M.STAAT, M.vraag_claude, M.collegas_kern, M.wat_mehdi_zei)
    M.DAGBOEK, M.STAAT = d, os.path.join(d, "staat.json")
    M.collegas_kern, M.wat_mehdi_zei = (lambda: list(KERN)), (lambda nu: [])
    M.vraag_claude = lambda system, inhoud: (antwoord([
        taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega", concept="Dag Klant Omega, ik bel je straks."),
        taak("Teken het plan", "Zeta tekent het plan", voor="collega", wie="Zeta")], overzicht="Eerst Klant Omega."), {})
    uit = os.path.join(d, "uit", "droog.md")
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = M.droog(["mehdi_agent.py", "--droog", "--zaad", "--moment", "ochtend", "--stil", "--uit", uit])
        tekst = buf.getvalue()
        assert code == 0, tekst
        assert "Omega" not in tekst and "Zeta" not in tekst, tekst
        assert "1. mehdi, normaal, begint met 'Bel', concept ja" in tekst, tekst
        assert "Klant Omega" in open(uit, encoding="utf-8").read()
        assert oct(os.stat(uit).st_mode & 0o777) == "0o600"
        assert not os.path.exists(M.STAAT)                       # droog bewaart geen staat
    finally:
        M.DAGBOEK, M.STAAT, M.vraag_claude, M.collegas_kern, M.wat_mehdi_zei = oud
        M.ag._log.clear()
        shutil.rmtree(d, ignore_errors=True)


# ANGEL-9 (T-0120, M10): De Doorgever. Een taak voor een agent zet Ai Angel zelf bij die agent klaar, als voorstel, maar
# alleen met de vlag aan en bij een ontvanger op de witte lijst. Beide zijn een keuze van Mehdi: de vlag staat uit en de
# lijst is leeg. Geen ontvangende agent verandert.
ZOOM_TAAK = taak("Zoek de opname van het gesprek", "11:00 Fathom, met Klant Omega, 45 min", voor="agent", wie="De Zoomwacht")
AGENTS_TWEE = AGENTS + [{"naam": "plaud-wacht", "label": "De Plaudwacht", "afdeling": "regie", "rol": "", "cadans": ""}]


def _agenttaak(tid, wie="De Zoomwacht", bron="11:00 Fathom, met Klant Omega", tekst="Zoek de opname"):
    return {"id": tid, "tekst": tekst, "voor": "agent", "wie": wie, "waarom": "omdat", "bron": bron, "dag": GISTEREN,
            "prioriteit": "normaal", "status": "open", "concept": "", "sinds": "2026-10-31T06:20:00+00:00"}


def test_doorgever_staat_uit_met_een_lege_witte_lijst():
    assert M.DOORGEVEN is False and M.ONTVANGERS == {}
    bron = open(os.path.join(RUNNER, "mehdi_agent.py"), encoding="utf-8").read()
    assert 'os.environ.get("MEHDI_AGENT_DOORGEVEN", "uit") == "aan"' in bron
    o = Omgeving()
    try:
        _, staat = o.ronde(uit=antwoord([ZOOM_TAAK]))
        assert [t["voor"] for t in staat["taken"].values()] == ["agent"]
        assert list(o.bord) == ["mehdi-agent:taken:2026-10-31"]            # niets bij De Zoomwacht
        assert not any(t.get("doorgegeven") for t in staat["taken"].values())
    finally:
        M.ag._log.clear()
        o.weg()


def test_doorgever_besluit_per_taak_zonder_iets_te_zetten():
    staat = {"taken": {"t-1": _agenttaak("t-1"), "t-2": _agenttaak("t-2", wie="De Plaudwacht"),
                       "t-3": _agenttaak("t-3", bron="14:00 (privé): geen spoor"),
                       "t-4": _agenttaak("t-4", wie="De Onbekende Wacht"),
                       "t-5": dict(_agenttaak("t-5"), voor="mehdi", wie="")}}
    besluit = {b["id"]: (b["naar"], b["besluit"]) for b in M.doorgeef_besluiten(staat, AGENTS_TWEE)}
    assert besluit == {"t-1": ("", "blijft bij Mehdi: zoom-wacht staat niet op de witte lijst"),
                       "t-2": ("", "blijft bij Mehdi: plaud-wacht staat niet op de witte lijst"),
                       "t-3": ("", "blijft bij Mehdi: privé"),
                       "t-4": ("", "blijft bij Mehdi: de agent staat niet op het bord")}, besluit
    lijst = {"zoom-wacht": "zoekt een opname"}
    besluit = {b["id"]: (b["naar"], b["besluit"]) for b in M.doorgeef_besluiten(staat, AGENTS_TWEE, lijst, aan=False)}
    assert besluit["t-1"] == ("zoom-wacht", "zou naar zoom-wacht (doorgeven staat uit)")
    assert besluit["t-2"] == ("", "blijft bij Mehdi: plaud-wacht staat niet op de witte lijst")   # De Plaudwacht niet
    assert besluit["t-3"][0] == "" and M.doorgeef_besluiten(staat, AGENTS_TWEE, lijst, aan=True)[0]["besluit"] == \
        "gaat naar zoom-wacht"
    veel = {"taken": {f"t-{i}": _agenttaak(f"t-{i}") for i in range(7)}}
    besluiten = M.doorgeef_besluiten(veel, AGENTS, lijst, aan=True)
    assert sum(1 for b in besluiten if b["naar"]) == M.MAX_DOORGEVEN == 5
    assert sum(1 for b in besluiten if b["besluit"] == "blijft bij Mehdi: hoogstens 5 per ronde") == 2


def test_doorgever_zet_als_voorstel_leest_terug_en_geeft_na_drie_dagen_terug_aan_mehdi():
    o = Omgeving()
    lijst = {"zoom-wacht": "zoekt een opname"}
    gepakt = []

    def doorgeef(staat, nu, agents):
        return M.doorgeven(staat, nu, agents, zet=o.zet, lees=o.lees, pak=gepakt.append, ontvangers=lijst, aan=True)

    try:
        r = NepRonde()
        staat = M.werk(r, nu=OCHTEND_UTC, map_=o.map, gezegd=lambda nu: [], kern=lambda: list(KERN),
                       claude=lambda s, i: (antwoord([ZOOM_TAAK]), {}), zet=o.zet, lees=o.lees, staatpad=o.staat,
                       doorgeef=doorgeef)
        (tid,) = staat["taken"]
        it = o.bord[f"mehdi-agent:taak:{tid}"]
        assert it["voor"] == "zoom-wacht" and it["soort"] == "taak" and it["sleutel"] == tid
        assert "Omega" not in it["titel"] and r.noden == []
        inhoud = json.loads(it["inhoud"])
        assert inhoud["voorstel"] is True and inhoud["taak"] == ZOOM_TAAK["tekst"] and inhoud["wat"] == "zoekt een opname"
        assert staat["taken"][tid]["doorgegeven"]["naar"] == "zoom-wacht"
        assert "Doorgegeven aan zoom-wacht" in o.bord["mehdi-agent:taken:2026-10-31"]["inhoud"]
        assert "1 doorgegeven" in r.detail and "Omega" not in r.detail, r.detail
        # een dag later ligt het nog klaar: niets verandert, en het gaat niet een tweede keer weg
        _, telling = M.doorgeven(staat, datetime(2026, 11, 1, 6, 20, tzinfo=timezone.utc), AGENTS, zet=o.zet,
                                 lees=o.lees, pak=gepakt.append, ontvangers=lijst, aan=True)
        assert sum(telling.values()) == 0 and staat["taken"][tid]["voor"] == "agent" and gepakt == []
        # na drie dagen nog altijd klaar: terug naar Mehdi, en het item neem ik terug zodat het niet dubbel gebeurt
        _, telling = M.doorgeven(staat, datetime(2026, 11, 3, 6, 21, tzinfo=timezone.utc), AGENTS, zet=o.zet,
                                 lees=o.lees, pak=gepakt.append, ontvangers=lijst, aan=True)
        t = staat["taken"][tid]
        assert telling["terug_naar_mehdi"] == 1 and t["voor"] == "mehdi" and t["wie"] == "" and "doorgegeven" not in t
        assert gepakt == [it["id"]] and t["teruggekomen"] == ["zoom-wacht"]
        t["voor"], t["wie"] = "agent", "De Zoomwacht"                      # het model zet het opnieuw bij de agent
        (b,) = M.doorgeef_besluiten(staat, AGENTS, lijst, aan=True)
        assert b["naar"] == "" and b["besluit"] == "blijft bij Mehdi: ging al eens terug"
    finally:
        M.ag._log.clear()
        o.weg()


def test_doorgever_opgepakt_is_beweging_en_onleesbaar_bord_beslist_niets():
    o = Omgeving()
    lijst = {"zoom-wacht": "zoekt een opname"}
    try:
        staat = {"taken": {"t-1": _agenttaak("t-1")}}
        M.doorgeven(staat, OCHTEND_UTC, AGENTS, zet=o.zet, lees=o.lees, pak=None, ontvangers=lijst, aan=True)
        o.opgepakt.add("mehdi-agent:taak:t-1")
        _, telling = M.doorgeven(staat, datetime(2026, 11, 5, 6, 20, tzinfo=timezone.utc), AGENTS, zet=o.zet,
                                 lees=o.lees, pak=None, ontvangers=lijst, aan=True)
        assert telling["opgepakt_door_agent"] == 1 and staat["taken"]["t-1"]["doorgegeven"]["status"] == "opgepakt"
        assert staat["taken"]["t-1"]["voor"] == "agent"
        staat = {"taken": {"t-2": dict(_agenttaak("t-2"), doorgegeven={"naar": "zoom-wacht", "uniek": "mehdi-agent:taak:t-2",
                                                                      "ts": "2026-10-20T06:20:00+00:00"})}}

        def stuk(uniek):
            raise bord.BordOnbekend("bord weg")

        _, telling = M.doorgeven(staat, OCHTEND_UTC, AGENTS, zet=o.zet, lees=stuk, pak=None, ontvangers=lijst, aan=True)
        assert telling["niet_gelezen"] == 1 and staat["taken"]["t-2"]["voor"] == "agent"     # onbekend is niet leeg
    finally:
        o.weg()


def test_doorgever_neemt_terug_wat_afgerond_of_niet_meer_voor_die_agent_is():
    o = Omgeving()
    lijst = {"zoom-wacht": "zoekt een opname"}
    gepakt = []
    try:
        staat = {"taken": {"t-1": _agenttaak("t-1"), "t-2": _agenttaak("t-2")}, "afgerond": []}
        M.doorgeven(staat, OCHTEND_UTC, AGENTS, zet=o.zet, lees=o.lees, pak=gepakt.append, ontvangers=lijst, aan=True)
        assert all(staat["taken"][k].get("doorgegeven") for k in ("t-1", "t-2"))
        staat["afgerond"].append(dict(staat["taken"].pop("t-1"), status="gedaan"))     # "1 is gedaan"
        staat["taken"]["t-2"].update(voor="mehdi", wie="")                             # "2 doe ik zelf"
        _, telling = M.doorgeven(staat, MIDDAG_UTC, AGENTS, zet=o.zet, lees=o.lees, pak=gepakt.append,
                                 ontvangers=lijst, aan=True)
        assert telling["ingetrokken"] == 2 and sorted(gepakt) == sorted(o.bord[f"mehdi-agent:taak:t-{i}"]["id"] for i in (1, 2))
        assert staat["afgerond"][0]["doorgegeven"]["status"] == "ingetrokken" and "doorgegeven" not in staat["taken"]["t-2"]
        assert staat["taken"]["t-2"]["voor"] == "mehdi" and staat["taken"]["t-2"]["teruggekomen"] == ["zoom-wacht"]
        _, telling = M.doorgeven(staat, MIDDAG_UTC, AGENTS, zet=o.zet, lees=o.lees, pak=gepakt.append,
                                 ontvangers=lijst, aan=True)
        assert sum(telling.values()) == 0 and len(gepakt) == 2                          # een keer terugnemen is genoeg
        staat["taken"]["t-2"].update(voor="agent", wie="De Zoomwacht")                 # weer bij de agent: niet opnieuw
        assert [b["besluit"] for b in M.doorgeef_besluiten(staat, AGENTS, lijst, aan=True)] == [
            "blijft bij Mehdi: ging al eens terug"]
        # wat ik zelf terugnam, is geen beweging van de ontvanger
        weg = {"naar": "zoom-wacht", "uniek": "u-3", "ts": "2026-10-20T06:20:00+00:00"}
        staat = {"taken": {"t-3": dict(_agenttaak("t-3"), doorgegeven=weg)}, "afgerond": []}
        _, telling = M.doorgeven(staat, OCHTEND_UTC, AGENTS, zet=o.zet, pak=gepakt.append, ontvangers=lijst, aan=True,
                                 lees=lambda uniek: [{"id": 9, "status": "opgepakt", "opgepakt_door": "mehdi-agent"}])
        assert telling == {"terug_naar_mehdi": 1} and staat["taken"]["t-3"]["voor"] == "mehdi", telling
    finally:
        o.weg()


def test_abonnementsfout_met_een_naam_komt_nooit_in_het_werkverslag():
    """Codex toets 1, bezwaar 1: ook een Fout met een soort kan een stuk antwoord dragen (aanmelden uit de fouttekst)."""
    import claude_abonnement as CA
    o = Omgeving()
    try:
        for soort in ("aanmelden", "limiet", "bron", "tijd", None):
            M.ag._log.clear()
            o.gezegd.append({"id": len(o.gezegd) + 40, "ts": "2026-10-31T11:00", "tekst": "nog iets?", "antwoord": ""})
            nep = NepAbonnement(fout=CA.Fout("Claude via het abonnement: 401 voor Klant Omega", soort))
            r = NepRonde()
            M.werk(r, nu=MIDDAG_UTC, map_=o.map, gezegd=lambda nu: list(o.gezegd), kern=lambda: list(KERN),
                   claude=lambda s, i: M.vraag_claude(s, i, route="abonnement", vraag=nep), zet=o.zet, lees=o.lees,
                   staatpad=o.staat)
            assert M.ag._log and not any("Omega" in x["tekst"] for x in M.ag._log), (soort, M.ag._log)
            assert "Omega" not in r.detail and not any("Omega" in n for n, _ in r.noden), (soort, r.detail, r.noden)
    finally:
        M.ag._log.clear()
        o.weg()


def test_doorgever_met_de_vlag_uit_raakt_het_bord_niet():
    """Codex toets 1, bezwaar 2: met de vlag uit leest, zet en neemt De Doorgever niets, ook niet wat al weg was."""
    oud = {"naar": "zoom-wacht", "uniek": "mehdi-agent:taak:t-1", "ts": "2026-10-20T06:20:00+00:00"}
    staat = {"taken": {"t-1": dict(_agenttaak("t-1"), doorgegeven=dict(oud)), "t-2": _agenttaak("t-2")}, "afgerond": []}
    voor = json.dumps(staat, sort_keys=True)

    def nooit(*a, **k):
        raise AssertionError("bord geraakt met de vlag uit")

    besluiten, telling = M.doorgeven(staat, OCHTEND_UTC, AGENTS, zet=nooit, lees=nooit, pak=nooit,
                                     ontvangers={"zoom-wacht": "zoekt een opname"}, aan=False)
    assert json.dumps(staat, sort_keys=True) == voor and sum(telling.values()) == 0
    assert [(b["id"], b["naar"]) for b in besluiten] == [("t-2", "zoom-wacht")]          # alleen: zou naar


def test_taak_uit_een_priveblok_of_priveregel_gaat_nooit_naar_een_ander():
    """Codex toets 1, bezwaar 3: de bron telt, ook als het woord privé niet in de taak zelf staat."""
    bundel = DAGBESTAND.replace("## Over deze vaststelling", "## Eigen werk en gezondheid\n\n- 2 uur aan tekening Proefplan "
                                "op de computer\n\n## Over deze vaststelling")
    bundels = [{"dag": GISTEREN, "dagbestand": bundel, "telling": TELLING}]
    assert M.bron_prive("2 uur aan tekening Proefplan", bundels)
    assert M.bron_prive("18:00 privégesprek", bundels) and M.bron_prive("14:00 (privé): geen spoor", bundels)
    assert not M.bron_prive("16:10 telefoon met Klant Omega", bundels)
    staat, telling, _ = M.verwerk(antwoord([taak("Zoek de tekening op", "2 uur aan tekening Proefplan", voor="agent",
                                                 wie="De Zoomwacht"),
                                            taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega",
                                                 voor="collega", wie="Zeta")]),
                                  M.laad_staat("/nergens/staat.json"), bundels, [], KERN, AGENTS, OCHTEND_UTC)
    per = {t["tekst"]: t for t in staat["taken"].values()}
    assert per["Zoek de tekening op"]["voor"] == "mehdi" and per["Zoek de tekening op"]["prive"] is True
    assert per["Bel Klant Omega terug"]["voor"] == "collega" and not per["Bel Klant Omega terug"].get("prive")
    assert telling["prive_bij_mehdi"] >= 1
    t = per["Zoek de tekening op"]
    t["voor"], t["wie"] = "agent", "De Zoomwacht"           # ook als het later toch bij een agent staat: nooit weg
    (b,) = [b for b in M.doorgeef_besluiten(staat, AGENTS, {"zoom-wacht": "zoekt"}, aan=True) if b["id"] == t["id"]]
    assert b == {"id": t["id"], "naar": "", "besluit": "blijft bij Mehdi: privé"}


def test_doorgever_een_onvolledig_bordantwoord_beslist_niets():
    """Codex toets 1, bezwaar 4: {} of {"items": null} is geen lege lijst."""
    for antwoord_bord in ({}, {"items": None}, {"items": "x"}, None):
        try:
            M.klaarzet_items(antwoord_bord)
            raise AssertionError(f"geen fout bij {antwoord_bord!r}")
        except bord.BordOnbekend:
            pass
    assert M.klaarzet_items({"items": []}) == []
    weg = {"naar": "zoom-wacht", "uniek": "mehdi-agent:taak:t-1", "ts": "2026-10-20T06:20:00+00:00"}
    for terug in (None, {}, "x"):
        staat = {"taken": {"t-1": dict(_agenttaak("t-1"), doorgegeven=dict(weg))}, "afgerond": []}
        _, telling = M.doorgeven(staat, OCHTEND_UTC, AGENTS, zet=None, lees=lambda uniek, terug=terug: terug,
                                 pak=None, ontvangers={"zoom-wacht": "zoekt"}, aan=True)
        assert telling == {"niet_gelezen": 1} and staat["taken"]["t-1"]["voor"] == "agent", (terug, telling)


def test_droog_toont_per_taak_waar_ze_heen_zou_gaan():
    import contextlib
    import io
    d = tempfile.mkdtemp(prefix="mehdi-agent-droog-")
    gisteren = M.dagen_terug(datetime.now(timezone.utc))[1]
    os.makedirs(os.path.join(d, gisteren[:4]))
    with open(os.path.join(d, gisteren[:4], f"{gisteren}.md"), "w", encoding="utf-8") as f:
        f.write(DAGBESTAND)
    oud = (M.DAGBOEK, M.STAAT, M.vraag_claude, M.collegas_kern, M.wat_mehdi_zei, bord.collegas)
    M.DAGBOEK, M.STAAT = d, os.path.join(d, "staat.json")
    M.collegas_kern, M.wat_mehdi_zei, bord.collegas = (lambda: list(KERN)), (lambda nu: []), (lambda zonder=None: AGENTS)
    M.vraag_claude = lambda system, inhoud: (antwoord([taak("Bel Klant Omega terug", "16:10 telefoon met Klant Omega"),
                                                       dict(ZOOM_TAAK, dag=gisteren)]), {})
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = M.droog(["mehdi_agent.py", "--droog", "--zaad", "--moment", "ochtend", "--stil"])
        tekst = buf.getvalue()
        assert code == 0 and "Omega" not in tekst, tekst
        assert "(droog) 1. mehdi, normaal, begint met 'Bel'" in tekst and "blijft bij Mehdi: eigen taak" in tekst, tekst
        assert "blijft bij Mehdi: zoom-wacht staat niet op de witte lijst" in tekst, tekst
    finally:
        M.DAGBOEK, M.STAAT, M.vraag_claude, M.collegas_kern, M.wat_mehdi_zei, bord.collegas = oud
        M.ag._log.clear()
        shutil.rmtree(d, ignore_errors=True)


def test_cronregel_elk_uur_met_slot_en_tijdslimiet():
    regels = [r for r in open(os.path.join(RUNNER, "planning", "mehdi-agent.cron"), encoding="utf-8").read().splitlines()
              if r.strip() and not r.startswith("#")]
    assert len(regels) == 1, regels
    (regel,) = regels
    assert regel.startswith("20 * * * * /usr/bin/flock -n /tmp/mehdi-agent.lock /usr/bin/timeout ")
    assert "/home/ubuntu/appportal/mijnagents-runner/mehdi_agent.py" in regel and "%" not in regel


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
