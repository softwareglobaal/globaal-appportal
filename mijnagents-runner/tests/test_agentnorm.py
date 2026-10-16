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

### Een onderdeel van nooit
- ook dit telt mee

## Wat Mehdi beslist
- wat er met een melding gebeurt

## Bronnen
- het bord
"""


def test_sectie_punten_en_grenzen_lezen_de_werkwijze():
    assert bord.punten(bord.sectie(GOEDE_WERKWIJZE, "nooit")) == [
        "nooit iets verwijderen", "nooit iets versturen", "ook dit telt mee"], "een lagere kop hoort bij de sectie"
    assert bord.sectie(GOEDE_WERKWIJZE, "Mehdi beslist") == "- wat er met een melding gebeurt"
    assert bord.sectie(GOEDE_WERKWIJZE, "bestaat niet") == ""
    nooit, mehdi = bord.grenzen(GOEDE_WERKWIJZE)
    assert len(nooit) == 3 and mehdi == ["wat er met een melding gebeurt"]
    assert bord.grenzen("Wat ik nooit doe: niets. Wat Mehdi beslist: alles.") == ([], []), \
        "zonder koppen en punten zijn er geen grenzen om toe te passen"
    # Codex NA17: een kop die over allebei gaat, telt voor geen van beide
    assert bord.grenzen("## Wat ik beslist nooit doe\n- iets\n") == ([], [])
    assert bord.grenzen("## Wat ik nooit doe\n- a\n\n## Wat de klant beslist\n- b\n") == (["a"], []), \
        "de tweede kop gaat over wat Mehdi beslist, niet over een ander"
    assert bord.grenzen("## 7. Wat ik nooit doe\n- a\n\n## 8. Wat Mehdi beslist\n- b\n") == (["a"], ["b"])
    # Codex NA22: een kop over wat een ander nooit doet, is geen grens van de agent
    assert bord.grenzen("## Wat de klant nooit doet\n- a\n\n## Wat Mehdi beslist\n- b\n") == ([], ["b"])
    assert bord.grenzen("## Wat collega's nooit doen\n- a\n") == ([], [])


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
    assert nb.statussen()[-1]["nood"] == [{"tekst": "Werkwijze zegt niet wat ik nooit doe of wat Mehdi beslist",
                                           "wie": "mehdi"}], nb.statussen()[-1]["nood"]
    assert "geen werk gedaan" in r.detail


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
