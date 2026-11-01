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
            self.bord[it["uniek"]] = dict(it, status="klaar")
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
