"""De Agentnorm, vastgezet. Zie AGENTNORM.md.

Deze test bewaakt het minimum waar elke agent doorheen gaat: de ronde in
`koppelingen/bord.py`. Wie die doorgang weghaalt of uitholt, laat deze test
falen in plaats van het stilletjes kapot te maken.

Gemeten op 20-09-2026, en de reden dat dit bestaat: van de 39 runners haalden er
vier hun werkwijze van het bord op, en meldde er een enkele welk regelboek hij
las. De werkwijze was voor de rest decoratie.
"""
import io
import os
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(__import__("tempfile").mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))  # nooit de echte wachtrij
import sys
import urllib.error
from contextlib import redirect_stderr

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402


class BordNabootsing:
    """Vangt op wat een ronde naar het bord stuurt, zonder netwerk.

    werkwijze: de tekst op het bord, of een uitzondering die het lezen ervan opwerpt, of een dict als
    rauw antwoord. open_noden: wat /api/nood teruggeeft (None = het bord weet het niet, een uitzondering)."""

    def __init__(self, werkwijze="# Werkwijze\n\nWat ik nooit doe: niets.\nWat Mehdi beslist: alles.", open_noden=None):
        self.werkwijze = werkwijze
        self.open_noden = open_noden
        self.gestuurd = []

    def call(self, pad, payload=None, method=None):
        self.gestuurd.append((pad, payload))
        if "werkwijze" in pad:
            if isinstance(self.werkwijze, Exception):
                raise self.werkwijze
            if isinstance(self.werkwijze, dict):
                return self.werkwijze
            return {"werkwijze": self.werkwijze}
        if pad == "/api/nood":
            if self.open_noden is None:
                raise OSError("geen noden te lezen")
            return {"nood": self.open_noden}
        if pad == "/api/agents":
            return [{"naam": "proefagent", "label": "De Proefagent", "type": "regie", "rol": "ik zelf", "actief": 1},
                    {"naam": "bode", "label": "De Bode", "type": "regie", "rol": "brengt wat telt naar Mehdi", "actief": 1},
                    {"naam": "oud", "label": "Oude agent", "type": "regie", "rol": "uit dienst", "actief": 0}]
        return {"nieuw": 0}

    def statussen(self):
        return [p for pad, p in self.gestuurd if pad == "/agent-status"]

    def kennis(self):
        return [p for pad, p in self.gestuurd if pad.endswith("/kennis")]


def ronde_met(nabootsing, doe=None, taak="proef"):
    echt, bord.call = bord.call, nabootsing.call
    try:
        ag = bord.Agent("proefagent")
        with ag.ronde(taak) as r:
            if doe:
                doe(r)
        return r
    finally:
        bord.call = echt


def test_n4_kennis_wordt_gemeld_met_vingerafdruk():
    """Elke ronde meldt welk regelboek hij las, met een vingerafdruk per bron."""
    nb = BordNabootsing()
    ronde_met(nb, lambda r: r.bron("taken.json", '{"a": 1}'))
    gemeld = nb.kennis()
    assert len(gemeld) == 1, "geen kennis gemeld: norm N4 faalt voor elke agent die de ronde gebruikt"
    tekst = gemeld[0]["kennis"]
    assert "werkwijze op het bord" in tekst, "de werkwijze van het bord hoort in de kennis"
    assert "taken.json" in tekst, "een bron die de agent las hoort in de kennis"
    # een vingerafdruk van acht tekens per regel, anders weet je niet welke versie hij las
    for regel in tekst.splitlines():
        assert len(regel.rsplit(", ", 1)[-1]) == 8, f"geen vingerafdruk in: {regel}"


def test_n4_werkwijze_wordt_opgehaald():
    """De werkwijze van het bord is de bron; de ronde haalt hem op en geeft hem door."""
    nb = BordNabootsing(werkwijze="# Mijn regels\n\nRegel een.")
    r = ronde_met(nb)
    assert "Regel een." in r.werkwijze, "de ronde geeft de werkwijze van het bord niet door aan de agent"


def test_n10_nood_zonder_teller():
    """Een aantal vooraan in een noodtekst maakt van elke ronde een nieuwe nood."""
    nb = BordNabootsing()
    ronde_met(nb, lambda r: r.nood("11 afspraken zonder code"))
    noden = nb.statussen()[-1]["nood"]
    assert noden[0]["tekst"] == "Afspraken zonder code", f"teller niet weggehaald: {noden[0]['tekst']}"


def test_n10_dezelfde_nood_maar_een_keer():
    nb = BordNabootsing()
    ronde_met(nb, lambda r: [r.nood("Geen adres"), r.nood("Geen adres")])
    assert len(nb.statussen()[-1]["nood"]) == 1, "dezelfde nood hoort maar een keer op het bord te staan"


def test_n11_ronde_die_breekt_meldt_fout():
    """Nooit blijven hangen op actief: daar zag niemand 18 uur lang iets van."""
    nb = BordNabootsing()

    def stuk(r):
        raise ValueError("iets liep mis")

    echt, bord.call = bord.call, nb.call
    try:
        ag = bord.Agent("proefagent")
        gebroken = False
        try:
            with ag.ronde("stukke ronde"):
                stuk(None)
        except ValueError:
            gebroken = True
        assert gebroken, "de ronde hoort de fout door te laten, niet op te slokken"
    finally:
        bord.call = echt
    laatste = nb.statussen()[-1]
    assert laatste["status"] == "fout", f"status na een gebroken ronde is {laatste['status']}, hoort fout te zijn"
    assert "ValueError" in laatste["detail"], "de fout hoort in het detail te staan"


def test_n11_geslaagde_ronde_blijft_niet_op_actief():
    nb = BordNabootsing()
    ronde_met(nb)
    assert nb.statussen()[0]["status"] == "actief", "een ronde begint op actief"
    assert nb.statussen()[-1]["status"] in ("klaar", "waakt"), "een ronde eindigt niet op actief"


def test_sjabloon_gebruikt_de_ronde():
    """Elke nieuwe agent erft het minimum. Wie het sjabloon uitholt, breekt dit."""
    sjabloon = open(os.path.join(RUNNER, "_sjabloon_agent.py"), encoding="utf-8").read()
    assert "import bord" in sjabloon, "het sjabloon hoort de gedeelde bord-module te gebruiken"
    assert "ag.ronde(" in sjabloon, "het sjabloon hoort de ronde te gebruiken, anders haalt een nieuwe agent N4 en N11 niet"


def test_de_norm_staat_beschreven():
    """Code zonder het document is een regel die niemand kan nalezen."""
    norm = open(os.path.join(RUNNER, "AGENTNORM.md"), encoding="utf-8").read()
    for code in ("N4", "N10", "N11", "N13", "N14"):
        assert code in norm, f"{code} wordt hier getoetst maar staat niet in AGENTNORM.md"


def test_n13_gedeelde_lessen_bestaan_en_zijn_geldig():
    """Wat een agent leert, hoort elke agent te weten. Het lessenboek moet er zijn
    en elke les moet zeggen waar ze vandaan komt, anders is het een mening."""
    import json
    pad = os.path.join(RUNNER, "werkwijze", "lessen.json")
    assert os.path.exists(pad), "werkwijze/lessen.json ontbreekt: dan leest geen enkele agent nog lessen"
    d = json.load(open(pad, encoding="utf-8"))
    lessen = d.get("lessen") or []
    assert lessen, "het lessenboek is leeg"
    ids = [l["id"] for l in lessen]
    assert len(ids) == len(set(ids)), "twee lessen met hetzelfde nummer"
    for l in lessen:
        for veld in ("id", "les", "bron", "geldt_voor"):
            assert l.get(veld), f"les {l.get('id')} mist het veld {veld}"
    assert any(l["id"] == "L15" for l in lessen), "L15 (zeg eerst wat blijft) is de les van 24-09-2026 en hoort erin"


def test_n13_ronde_leest_de_gedeelde_lessen():
    """De ronde leest het lessenboek mee als bron, zodat het in de kennis staat en
    de Normwacht kan zien dat een agent het echt las."""
    nb = BordNabootsing()
    r = ronde_met(nb)
    assert r.lessen, "de ronde geeft de lessen niet door aan de agent (r.lessen is leeg)"
    gemeld = nb.kennis()
    assert gemeld and "gedeelde lessen" in gemeld[0]["kennis"], "de gedeelde lessen staan niet in de gemelde kennis: N13 kan dan nooit slagen"


def test_n14_ronde_kent_de_collegas():
    """Mehdi, 25-09-2026: "zorg ervoor dat alle agents van elkaar op de hoogte zijn". De ronde
    haalt de actieve agents levend van het bord, zonder zichzelf en zonder wie uit dienst is,
    en meldt die lijst als bron, zodat de Normwacht kan zien dat hij ze kende."""
    nb = BordNabootsing()
    r = ronde_met(nb)
    namen = [c["naam"] for c in r.collegas]
    assert namen == ["bode"], f"de ronde hoort alleen actieve collega's te geven, zonder zichzelf: {namen}"
    gemeld = nb.kennis()
    assert gemeld and "collega's op het bord" in gemeld[0]["kennis"], "de collega's staan niet in de gemelde kennis: N14 kan dan nooit slagen"
    assert "De Bode (bode, regie)" in bord.collega_tekst(r.collegas), "de collega-tekst noemt label, naam en afdeling"


def test_n14_bord_dat_niet_antwoordt_breekt_de_ronde_niet():
    """Antwoordt het bord niet, dan loopt de ronde door; de Normwacht meldt het gat."""
    nb = BordNabootsing()
    echt_call = nb.call

    def zonder_agents(pad, payload=None, method=None):
        if pad == "/api/agents":
            raise OSError("bord weg")
        return echt_call(pad, payload, method)

    nb.call = zonder_agents
    r = ronde_met(nb)
    assert r.collegas == [], "zonder bord hoort de lijst leeg te zijn"
    assert nb.statussen()[-1]["status"] in ("klaar", "waakt"), "een ontbrekende collega-lijst mag de ronde niet breken"


# --- NA09 (Codex, 16-10-2026): zonder regelboek geen ronde --------------------------------------------
# Tot dan gaf bord.werkwijze() bij elke leesfout een lege tekst, en liep de ronde gewoon door: een agent
# kon zonder regelboek werken zonder dat iemand het zag. Onbekend is niet leeg, en leeg is geen regelboek.

def _http(code):
    return urllib.error.HTTPError("http://127.0.0.1:3022/api/agent/proefagent/werkwijze", code, "proef", None, None)


def ronde_die_moet_stoppen(nb):
    """(werk begonnen, uitzondering) voor een ronde op deze nabootsing."""
    echt, bord.call = bord.call, nb.call
    begonnen = []
    try:
        ag = bord.Agent("proefagent")
        try:
            with redirect_stderr(io.StringIO()):
                with ag.ronde("proef"):
                    begonnen.append(True)
        except bord.RondeGestopt as e:
            return begonnen, e
        return begonnen, None
    finally:
        bord.call = echt


def _gestopt(nb, soort_nood, wie):
    begonnen, fout = ronde_die_moet_stoppen(nb)
    assert not begonnen, "het werk begon zonder regelboek: precies wat NA09 verbiedt"
    assert fout is not None, "de ronde hoort te stoppen met RondeGestopt"
    laatste = nb.statussen()[-1]
    assert laatste["status"] == "fout", f"status na een ronde zonder regelboek is {laatste['status']}, hoort fout (N11)"
    assert soort_nood in laatste["detail"], f"de reden staat niet in het detail: {laatste['detail']}"
    assert {"tekst": soort_nood, "wie": wie} in laatste["nood"], f"nood ontbreekt of heeft de verkeerde eigenaar: {laatste['nood']}"
    assert not nb.kennis(), "een ronde die niets las, meldt geen kennis (anders slaagt N4 voor niets)"


def test_na09_agent_niet_op_het_bord_stopt_de_ronde():
    _gestopt(BordNabootsing(werkwijze=_http(404), open_noden=[]),
             "Werkwijze niet gelezen: agent staat niet op het bord", "claude-code")


def test_na09_geen_toegang_stopt_de_ronde():
    _gestopt(BordNabootsing(werkwijze=_http(403), open_noden=[]),
             "Werkwijze niet gelezen: geen toegang tot het bord", "claude-code")


def test_na09_bordfout_stopt_de_ronde_zonder_getal_in_de_nood():
    """De HTTP-code hoort in het detail, niet in de noodtekst: anders is een 502 morgen een andere nood (N10)."""
    nb = BordNabootsing(werkwijze=_http(502), open_noden=[])
    _gestopt(nb, "Werkwijze niet gelezen: bordfout", "claude-code")
    assert "HTTP 502" not in nb.statussen()[-1]["nood"][0]["tekst"]
    assert "HTTP 502" in nb.statussen()[-1]["detail"], "de HTTP-code hoort wel in het detail (Codex NA18)"


def test_na09_onleesbaar_antwoord_is_niet_leeg():
    """Een antwoord zonder werkwijze erin (of een lege body: {}) is onbekend, geen lege werkwijze."""
    _gestopt(BordNabootsing(werkwijze={}, open_noden=[]),
             "Werkwijze niet gelezen: onleesbaar antwoord van het bord", "claude-code")


def test_na09_lege_werkwijze_stopt_de_ronde():
    for leeg in ("", "  \n\t"):
        _gestopt(BordNabootsing(werkwijze=leeg, open_noden=[]), "Werkwijze leeg op het bord", "mehdi")


def test_na09_bord_onbereikbaar_stopt_en_sluit_niets():
    """Is het bord weg, dan weet de ronde ook niet welke noden open staan: dan stuurt ze geen lijst, zodat
    het bord niets sluit. De fout-hartslag wordt wel geprobeerd."""
    nb = BordNabootsing(werkwijze=urllib.error.URLError("verbinding geweigerd"))
    begonnen, fout = ronde_die_moet_stoppen(nb)
    assert not begonnen and isinstance(fout, bord.RondeGestopt)
    laatste = nb.statussen()[-1]
    assert laatste["status"] == "fout" and "bord onbereikbaar" in laatste["detail"]
    assert "nood" not in laatste, "zonder de open noden te kennen mag de ronde geen noodlijst sturen (die sluit alles)"


def test_na09_open_noden_blijven_open_bij_een_stop():
    """Onbekend is niet opgelost: de noden die al open stonden, gaan mee; die van een andere agent niet."""
    nb = BordNabootsing(werkwijze=_http(500), open_noden=[
        {"naam": "proefagent", "tekst": "Postvak niet leesbaar", "wie": "claude-code"},
        {"naam": "andere-agent", "tekst": "Iets anders", "wie": "mehdi"}])
    ronde_die_moet_stoppen(nb)
    teksten = [n["tekst"] for n in nb.statussen()[-1]["nood"]]
    assert teksten == ["Postvak niet leesbaar", "Werkwijze niet gelezen: bordfout"], teksten


def test_ronde_die_halverwege_breekt_sluit_geen_open_noden():
    """Dezelfde regel voor een ronde die breekt: wat ze niet meer kon nakijken, blijft open."""
    nb = BordNabootsing(open_noden=[{"naam": "proefagent", "tekst": "Oude nood", "wie": "mehdi"}])

    def breek(r):
        r.nood("Nieuwe nood", wie="claude-code")
        raise ValueError("halverwege stuk")

    echt, bord.call = bord.call, nb.call
    try:
        try:
            with bord.Agent("proefagent").ronde("proef") as r:
                breek(r)
        except ValueError:
            pass
    finally:
        bord.call = echt
    laatste = nb.statussen()[-1]
    assert laatste["status"] == "fout"
    assert [n["tekst"] for n in laatste["nood"]] == ["Oude nood", "Nieuwe nood"], laatste["nood"]


def _oude_runner(ag, gedaan):
    """Zoals archivaris, fathom-wacht en levenscoach: hartslag, dan in een try de werkwijze lezen en werken;
    bij een fout een fouthartslag en opnieuw opwerpen."""
    ag.hartslag("actief", taak="oude ronde")
    try:
        regels = ag.werkwijze()
        gedaan.append(regels)
    except Exception as e:  # noqa: BLE001
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


def test_na11_oude_runners_werken_niet_zonder_regelboek():
    """Codex NA11: agenda-wacht, archivaris, fathom-wacht en levenscoach lezen hun werkwijze nog buiten de ronde
    met ag.werkwijze(). Die gaf bij een leesfout een lege tekst, en de Archivaris labelde dan zonder Mehdi's
    correcties. Nu stopt ook hun werk, met dezelfde nood en een fouthartslag."""
    for werkwijze, nood, wie in ((urllib.error.URLError("weg"), "Werkwijze niet gelezen: bord onbereikbaar", "claude-code"),
                                 (_http(404), "Werkwijze niet gelezen: agent staat niet op het bord", "claude-code"),
                                 ("", "Werkwijze leeg op het bord", "mehdi")):
        nb = BordNabootsing(werkwijze=werkwijze, open_noden=[])
        echt, bord.call = bord.call, nb.call
        gedaan = []
        try:
            try:
                with redirect_stderr(io.StringIO()):
                    _oude_runner(bord.Agent("proefagent"), gedaan)
                gestopt = False
            except bord.RondeGestopt:
                gestopt = True
        finally:
            bord.call = echt
        assert gestopt and not gedaan, f"de oude runner werkte door zonder regelboek: {gedaan!r}"
        assert nb.statussen()[-1]["status"] == "fout"
        met_nood = [s for s in nb.statussen() if s.get("nood")]
        assert met_nood and {"tekst": nood, "wie": wie} in met_nood[-1]["nood"], nb.statussen()
    nb = BordNabootsing(werkwijze="# Regels\n\nRegel een.")
    echt, bord.call = bord.call, nb.call
    try:
        assert bord.Agent("proefagent").werkwijze() == "# Regels\n\nRegel een."
    finally:
        bord.call = echt


def test_na23_misvormde_noodlijst_is_onbekend():
    """Codex NA23: een antwoord van /api/nood met de verkeerde vorm (tekst als lijst) liet de ronde breken met een
    TypeError en de agent op actief staan. Nu is zo'n lijst onbekend: geen noodlijst, wel de fouthartslag."""
    krom = [{"naam": "proefagent", "tekst": ["geen", "tekst"], "wie": "mehdi"}]
    nb = BordNabootsing(werkwijze=_http(500), open_noden=krom)
    begonnen, fout = ronde_die_moet_stoppen(nb)
    assert not begonnen and isinstance(fout, bord.RondeGestopt), fout
    laatste = nb.statussen()[-1]
    assert laatste["status"] == "fout" and "nood" not in laatste, laatste

    nb = BordNabootsing(open_noden=krom)
    echt_tekst = bord.collega_tekst

    def stuk(lijst):
        raise ValueError("collega-lijst stuk")

    bord.collega_tekst = stuk
    try:
        try:
            ronde_met(nb)
        except ValueError:
            pass
    finally:
        bord.collega_tekst = echt_tekst
    assert nb.statussen()[-1]["status"] == "fout", f"bleef op {nb.statussen()[-1]['status']} staan (N11)"


def test_na28_nood_met_een_vreemde_eigenaar_is_onbekend():
    """Codex NA28: een nood met wie als lijst gold als goed gevormd en kreeg stil de eigenaar mehdi."""
    nb = BordNabootsing(open_noden=[{"naam": "proefagent", "tekst": "Iets", "wie": []}])
    echt, bord.call = bord.call, nb.call
    try:
        assert bord.Agent("proefagent").open_noden() is None
        nb.open_noden = [{"naam": "proefagent", "tekst": "Iets", "wie": None}, {"naam": "proefagent", "tekst": "Ook"}]
        assert bord.Agent("proefagent").open_noden() == [{"tekst": "Iets", "wie": "mehdi"}, {"tekst": "Ook", "wie": "mehdi"}]
    finally:
        bord.call = echt


def test_na45_extra_bron_van_een_andere_soort_breekt_de_afsluiting_niet():
    """Codex NA45: een extra bron die geen tekst is, liet __exit__ breken voor de laatste hartslag; de agent bleef
    op actief. Nu wordt elke bron als tekst bewaard, en breekt het melden van kennis, dan gaat de hartslag toch uit."""
    nb = BordNabootsing()
    echt, bord.call = bord.call, nb.call
    try:
        with bord.Agent("proefagent").ronde("proef", bronnen={"extra": 42, "lijst": [1, 2],
                                                              "vreemd": {(1, 2): "waarde"}}):   # NA48
            pass
        assert nb.statussen()[-1]["status"] == "klaar"
        assert "extra: 2 tekens" in nb.kennis()[-1]["kennis"], nb.kennis()
        ag = bord.Agent("proefagent")

        def stuk(*a, **k):
            raise RuntimeError("kennis stuk")

        ag.kennis = stuk
        with redirect_stderr(io.StringIO()):
            with ag.ronde("proef"):
                pass
        assert nb.statussen()[-1]["status"] == "klaar", "de laatste hartslag hoort ook uit te gaan als kennis breekt"
    finally:
        bord.call = echt


def test_na15_fout_in_de_startfase_blijft_niet_op_actief():
    """Codex NA15: een fout na de hartslag 'actief' maar voor het werk (lessen.json met de verkeerde vorm,
    een stuk collega-lijst) liet de agent op actief staan, want __exit__ draait dan niet."""
    import json as _json
    import types
    nb = BordNabootsing()
    echt_json = bord.json
    bord.json = types.SimpleNamespace(loads=lambda s: [], dumps=_json.dumps)   # geldige JSON, verkeerde vorm
    try:
        r = ronde_met(nb)
    finally:
        bord.json = echt_json
    assert r.lessen == [] and nb.statussen()[-1]["status"] in ("klaar", "waakt"), \
        "een lessenboek met de verkeerde vorm hoort de ronde niet te breken (de Normwacht meldt N13)"

    nb = BordNabootsing()
    echt_tekst = bord.collega_tekst

    def stuk(lijst):
        raise ValueError("collega-lijst stuk")

    bord.collega_tekst = stuk
    try:
        try:
            ronde_met(nb)
            gebroken = False
        except ValueError:
            gebroken = True
    finally:
        bord.collega_tekst = echt_tekst
    assert gebroken, "de fout hoort door te gaan, niet opgeslokt te worden"
    assert nb.statussen()[-1]["status"] == "fout", f"bleef op {nb.statussen()[-1]['status']} staan (N11)"


GOEDE_WERKWIJZE = """# De Proefagent

## Wat ik doe
Ik lees en ik meld.

## Wat ik nooit doe
- nooit iets verwijderen
- nooit iets versturen
* nooit iets betalen

## Wat Mehdi beslist
- wat er met een melding gebeurt

## Bronnen
- het bord

```
- dit voorbeeld na de grenzen stoort niet
```
"""

def test_grenzen_alleen_in_de_strikte_vorm():
    """Codex NA17 tot NA37 en de stopregel: de grenzen staan onder de twee afgesproken koppen, met daaronder alleen
    punten ("- " of "* " op kolom 0) en lege regels, voor elk codeblok of stuk HTML. Wat daar niet in past, geeft
    geen grenzen: een twijfelgeval wordt geweigerd, nooit aanvaard."""
    g = bord.grenzen
    assert g(GOEDE_WERKWIJZE) == (["nooit iets verwijderen", "nooit iets versturen", "nooit iets betalen"],
                                  ["wat er met een melding gebeurt"])
    assert g("Wat ik nooit doe: niets. Wat Mehdi beslist: alles.") == ([], [])
    # NA17, NA22, NA27: alleen de afgesproken koppen, eventueel genummerd of met een toevoeging tussen haakjes
    assert g("## Wat ik beslist nooit doe\n- iets\n") == ([], [])
    assert g("## Wat ik nooit doe\n- a\n\n## Wat de klant beslist\n- b\n") == (["a"], [])
    assert g("## 7. Wat ik nooit doe\n- a\n\n## 8. Wat Mehdi beslist\n- b\n") == (["a"], ["b"])
    assert g("## Wat de klant nooit doet\n- a\n\n## Wat Mehdi beslist\n- b\n") == ([], ["b"])
    assert g("## Wat collega's nooit doen\n- a\n") == ([], [])
    assert g("## Wat ik weet over wat de klant nooit doet\n- a\n\n## Wat Mehdi beslist\n- b\n") == ([], ["b"])
    assert g("## Wat ik nooit doe (sinds 16-10-2026)\n- a\n\n## 3) Wat Mehdi beslist\n- b\n") == (["a"], ["b"])
    # NA32, NA33, NA35, NA36: na het eerste codeblok, stuk HTML of commentaar telt niets meer
    assert g("```\n## Wat ik nooit doe\n- a\n## Wat Mehdi beslist\n- b\n```\n") == ([], [])
    assert g("## Wat ik nooit doe\n- a\n```\n- in code\n```\n- b\n\n## Wat Mehdi beslist\n- c\n") == ([], []), \
        "een sectie die nog open is bij het eerste codeblok, telt niet"
    assert g("## Wat ik nooit doe\n- a\n\n## Wat Mehdi beslist\n- b\n\n## Bronnen\n```\nx\n```\n") == (["a"], ["b"])
    assert g("```\n## Wat ik nooit doe\n- a\n\t```\n## Wat Mehdi beslist\n- b\n```\n") == ([], [])
    assert g("\t```\n## Wat ik nooit doe\n- a\n## Wat Mehdi beslist\n- b\n") == ([], [])
    assert g("```\n## Wat ik nooit doe\n- a\n````\n## Wat Mehdi beslist\n- b\n```\n") == ([], [])
    assert g("<!-- klaar --> <!--\n## Wat ik nooit doe\n- a\n## Wat Mehdi beslist\n- b\n-->\n") == ([], [])
    assert g("<!-- uitleg -->\n## Wat ik nooit doe\n- a\n## Wat Mehdi beslist\n- b\n") == ([], [])
    assert g("<div>\n## Wat ik nooit doe\n- a\n## Wat Mehdi beslist\n- b\n</div>\n") == ([], [])
    # NA34, NA37: onder de kop alleen punten op kolom 0 en lege regels
    assert g("## Wat ik nooit doe\n\n    - a\n\n## Wat Mehdi beslist\n\n    - b\n") == ([], [])
    assert g("## Wat ik nooit doe\nToelichting\n- niets verwijderen\n\n## Wat Mehdi beslist\n- b\n") == ([], ["b"])
    assert g("## Wat ik nooit doe\n- a\n### meer\n- c\n\n## Wat Mehdi beslist\n- b\n") == ([], ["b"])
    assert g("## Wat ik nooit doe\n- - -\n\n## Wat Mehdi beslist\n* b\n") == ([], ["b"])
    assert g("## Wat ik nooit doe\n1. genummerd\n\n## Wat Mehdi beslist\n* b\n") == ([], ["b"])
    # NA39, NA40: alleen een gewoon regeleinde, en een punt is gewone tekst
    assert g("## Wat ik nooit doe\u2028- nooit wissen\n\n## Wat Mehdi beslist\n- b\n") == ([], [])
    assert g("## Wat ik nooit doe\n- <span style='display:none'>nooit wissen</span>\n\n## Wat Mehdi beslist\n- b\n") == ([], []), \
        "ruwe HTML ergens in de werkwijze: geen grenzen"
    assert g("## Wat ik nooit doe\n- _a_\n- [a](b)\n\n## Wat Mehdi beslist\n- b\n") == ([], ["b"])
    # gevonden door de proef tegen de weergave van het bord: een witregel voor de kop, en de kop maar een keer
    assert g("* x\n    - a\n## Wat ik nooit doe\n- b\n") == ([], [])
    assert g("## Wat ik nooit doe ##\n```\n```\n\n## Wat ik nooit doe\n- b\n") == ([], [])
    # NA43: een tweede kop met opmaak, als link of als setext-kop telt als dubbel
    tweede = "## Wat ik nooit doe\n- nooit verwijderen\n\n## Wat Mehdi beslist\n- verzenden\n\n"
    assert g(tweede + "## Wat ik *nooit* doe\n- toch verwijderen\n") == ([], ["verzenden"])
    assert g(tweede + "## [Wat ik nooit doe](x)\n") == ([], ["verzenden"])
    assert g(tweede + "## Bronnen\n\nWat ik nooit doe\n===\n") == ([], ["verzenden"])
    # NA44: ruwe HTML, ook na de grenzen, geeft geen grenzen; een losse < is gewone tekst
    assert g(tweede + "## Bronnen\n<style>.md ul { display: none !important; }</style>\n") == ([], [])
    assert g("Intro, minder dan < 500 tekens.\n\n" + tweede) == (["nooit verwijderen"], ["verzenden"])
    # NA46: een tweede kop met een tekenverwijzing of een verwijzingslink telt ook als dubbel; gewone tekst niet
    assert g(tweede + "## Wat ik n&#111;oit doe\n- toch\n") == ([], ["verzenden"])
    assert g(tweede + "## [Wat ik nooit doe][grens]\n\n[grens]: http://x\n") == ([], ["verzenden"])
    assert g("Lees eerst wat ik nooit doe.\n\n" + tweede) == (["nooit verwijderen"], ["verzenden"])


def _sjabloon_werk():
    code = open(os.path.join(RUNNER, "_sjabloon_agent.py"), encoding="utf-8").read()
    ns = {"__name__": "sjabloonproef", "__file__": os.path.join(RUNNER, "sjabloonproef.py")}
    exec(compile(code.replace("%%NAAM%%", "proefagent").replace("%%LABEL%%", "proefagent"), "sjabloon", "exec"), ns)
    return ns["werk"]


def test_sjabloon_past_de_werkwijze_toe():
    """Het sjabloon toont hoe een agent zijn werkwijze toepast: het leest zijn grenzen uit het regelboek
    van het bord, en zonder grenzen doet het geen werk maar meldt het een nood (NA09)."""
    werk = _sjabloon_werk()
    nb = BordNabootsing(werkwijze=GOEDE_WERKWIJZE)
    r = ronde_met(nb, werk)
    assert "3 grenzen" in r.detail and "1 beslissingen voor Mehdi" in r.detail, r.detail
    assert nb.statussen()[-1]["nood"] == [], "met grenzen in de werkwijze hoort er geen nood te zijn"

    nb = BordNabootsing(werkwijze="# Werkwijze\n\nIk doe maar wat, zonder grenzen.")
    r = ronde_met(nb, werk)
    assert nb.statussen()[-1]["nood"] == [{"tekst": "Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist",
                                           "wie": "mehdi"}], nb.statussen()[-1]["nood"]
    assert "geen werk gedaan" in r.detail


# --- wat grenzen() aanvaardt, staat zo op het bord (Codex NA32 tot NA42) ----------------------------------------
# Het bord toont een werkwijze met Python-Markdown (mijnagents/app.py, md(): extensies tables en fenced_code). Deze
# proef legt de belofte van de vaste vorm vast tegen die echte weergave: voor duizenden gegenereerde, lastige
# werkwijzen geldt dat wat grenzen() aanvaardt, op het bord als kop met precies die lijstpunten staat. Een geval dat
# grenzen() weigert, is geen fout (een weigering is goedkoop); een aanvaarding die het bord anders toont, wel.

def _bordweergave(tekst):
    import markdown
    return markdown.markdown(tekst, extensions=["tables", "fenced_code"])


def _blokken(html):
    """De blokken op het hoogste niveau: (tag, tekst, li-teksten, of er iets anders dan tekst of <p> in een li zat)."""
    from html.parser import HTMLParser

    class Lezer(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.blokken, self.diepte, self.huidig = [], 0, None
            self.koppen, self.in_kop = [], None      # elke kop, op welke diepte ook

        def handle_starttag(self, tag, attrs):
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
                self.koppen.append("")
                self.in_kop = self.diepte
            if self.diepte == 0:
                self.huidig = {"tag": tag, "tekst": "", "li": [], "vreemd": False}
            elif self.huidig is not None:
                if self.huidig["tag"] in ("ul", "ol") and self.diepte == 1 and tag == "li":
                    self.huidig["li"].append("")
                elif not (self.diepte == 2 and tag == "p"):
                    self.huidig["vreemd"] = True
            if tag not in ("br", "hr", "img", "input", "meta", "link"):
                self.diepte += 1

        def handle_startendtag(self, tag, attrs):
            if self.huidig is not None and self.diepte > 0:
                self.huidig["vreemd"] = True

        def handle_endtag(self, tag):
            if tag in ("br", "hr", "img", "input", "meta", "link"):
                return
            self.diepte = max(0, self.diepte - 1)
            if tag in ("h1", "h2", "h3", "h4", "h5", "h6") and self.in_kop == self.diepte:
                self.in_kop = None
            if self.diepte == 0 and self.huidig is not None:
                self.blokken.append(self.huidig)
                self.huidig = None

        def handle_data(self, data):
            if self.in_kop is not None and self.koppen:
                self.koppen[-1] += data
            if self.huidig is None:
                return
            if self.huidig["tag"] in ("ul", "ol"):
                if self.huidig["li"]:
                    self.huidig["li"][-1] += data
            else:
                self.huidig["tekst"] += data

    lezer = Lezer()
    lezer.feed(html)
    return lezer.blokken, lezer.koppen


def _zichtbaar(tekst):
    import unicodedata
    return "".join(c for c in tekst if unicodedata.category(c) != "Cf").strip().lower()


def _zo_op_het_bord(tekst, kop, punten_):
    """Op het bord staat precies een kop die zo heet (op welke diepte ook), op het hoogste niveau, en direct
    daarna een lijst met precies deze punten, zonder opmaak erin."""
    blokken, koppen = _blokken(_bordweergave(tekst))
    if sum(1 for k in koppen if kop.match(_zichtbaar(k))) != 1:
        return False
    for i, b in enumerate(blokken):
        if b["tag"] in ("h1", "h2", "h3", "h4", "h5", "h6") and kop.match(_zichtbaar(b["tekst"])):
            if i + 1 >= len(blokken) or blokken[i + 1]["tag"] != "ul" or blokken[i + 1]["vreemd"]:
                return False
            return [li.strip() for li in blokken[i + 1]["li"]] == punten_
    return False


def test_wat_grenzen_aanvaardt_staat_zo_op_het_bord():
    try:
        import markdown  # noqa: F401
    except ImportError:
        assert not os.environ.get("CI"), "markdown ontbreekt in de CI: deze grendel hoort daar te draaien"
        print("  (overgeslagen: markdown niet geinstalleerd)")
        return
    import random
    koppen = ["## Wat ik nooit doe", "## Wat Mehdi beslist", "## 7. Wat ik nooit doe", "### Wat Mehdi beslist",
              "## Bronnen", "# Titel", "## Wat de klant nooit doet", "## Wat ik nooit doe ##", "﻿## Wat ik nooit doe",
              "#### Wat ik nooit doe (vast)"]
    punten_ = ["- nooit iets verwijderen", "* nooit versturen", "- a", "-\tb", "- - a", "- 1. a", "1. a", "- _a_",
               "- *a*", "- <span style='display:none'>x</span>", "- [a](b)", "- &#8203;", "- ​", "- a  ",
               "- (info@x.be)", "    - a", "  - a", "- \"x\"", "- a\\", "- x | y", "+ a", "- ok, 100% zeker!"]
    koppen += ["## Wat ik *nooit* doe", "## [Wat ik nooit doe](x)", "##Wat Mehdi beslist", "## Wat `Mehdi` beslist",
               "## Wat ik n&#111;oit doe", "## [Wat ik nooit doe][grens]", "## Wat Mehdi beslist&nbsp;",
               "> ## Wat Mehdi beslist", "- ## Wat ik nooit doe"]
    anders = ["", "", "", "", "Toelichting", "```", "````", " ```", "\t```", "~~~", "<!--", "-->", "<!-- x -->",
              "Wat ik nooit doe", "Wat Mehdi beslist", "minder dan < 500", "<style>ul{display:none}</style>",
              "[grens]: http://x", "Lees eerst wat ik nooit doe.", "&amp;",
              "<http://x>", "a <b>vet</b>",
              "<pre>", "</pre>", "<div>", "</div>", "> citaat", "[a]: http://x", "===", "---", "- - -", "| a | b |",
              "|---|---|", " ", "x - a", "\r", "<span style='display:none'>", "    code", "\\- a"]
    rnd = random.Random(1610)
    aanvaard = 0
    for _ in range(6000):
        regels = [rnd.choice(koppen if r < 0.2 else punten_ if r < 0.6 else anders)
                  for r in (rnd.random() for _ in range(rnd.randint(3, 14)))]
        if rnd.random() < 0.8:
            for kop in ("## Wat ik nooit doe", "## Wat Mehdi beslist"):
                plaats = rnd.randint(0, len(regels))
                regels[plaats:plaats] = (["", kop] if rnd.random() < 0.7 else [kop]) + \
                    [rnd.choice(punten_[:3]) for _ in range(rnd.randint(0, 3))]
        tekst = "\n".join(regels) + rnd.choice(["", "\n"])
        nooit, mehdi = bord.grenzen(tekst)
        for kop, lijst in ((bord.KOP_NOOIT, nooit), (bord.KOP_MEHDI, mehdi)):
            if lijst:
                aanvaard += 1
                assert _zo_op_het_bord(tekst, kop, lijst), \
                    f"grenzen() aanvaardt {lijst!r}, maar het bord toont het anders:\n{tekst!r}\n{_bordweergave(tekst)}"
    assert aanvaard > 300, f"de proef aanvaardde te weinig gevallen om iets te bewijzen ({aanvaard})"


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"FOUT {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)
