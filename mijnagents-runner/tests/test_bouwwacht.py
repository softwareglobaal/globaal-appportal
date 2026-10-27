"""Grendels op De Bouwwacht (bouwwacht.py): alarm als een dienst op de VM niet meer herbouwt na een git pull.

Waarom: van 26-10 rond 19:00 tot 27-10 07:56 UTC faalde elke bouw van het bord en draaide het een oude bouw, zonder dat
iemand het zag (K5, uitrol van PR #103). Deze test legt vast wat het driehoeksoverleg van 27-10-2026 vroeg (X2, X3, X5,
K5), wat Mehdi besliste (een signaal per storing via De Bode) en wat de Codex-resultaattoetsen vonden:

- gelijk: geen nood; een verschil korter dan 10 minuten is een bouw die bezig is, geen nood;
- vanaf 10 minuten, of zonder markering, of met een markering die niet in de reflog staat, of zonder reflog: de nood
  "Bouw loopt achter op de code: <map>", voor claude-code, zonder getal in de tekst; zonder reflog ook een nood daarover;
- de klok begint bij de echte pull (reflog), ook in de eerste ronde; een tweede pull tijdens een storing zet ze niet
  terug; een pull die de map niet raakt, telt niet; een reset of branch-wissel terug naar de gebouwde boom is gelijk; een
  gelijkheid tussen twee rondes zet de klok opnieuw;
- herstel sluit de nood; twee diensten in storing geven twee noden; een dienst die niet na te kijken is, houdt de
  andere niet tegen; een onleesbare markering is onbekend;
- een storing is de tijd dat de bouwnood openstaat: een signaal per storing, met het nummer van die nood; een tweede
  pull of een markering die even ontbreekt, geeft geen tweede; een nieuwe storing een nieuw; de titel belt niet;
- de ronde leest alleen (rev-parse en log) en schrijft niets; --droog stuurt niets; een ronde tegelijk; zonder slot,
  zonder bord of zonder aangekomen eindhartslag een regel in het cronlog en exit 1;
- een nieuwe nood staat een keer in het werkverslag, niet elke ronde;
- de runner gaat door de gedeelde ronde, en zijn werkwijze haalt de norm.

Geen netwerk en geen echte klok: een tijdelijke git-repo met vaste reflogtijden (GIT_COMMITTER_DATE) en een nagebootst
bord dat noden nummert, opent en sluit zoals mijnagents/app.py (/agent-status) en klaarzet ontdubbelt op uniek.
Draaien: python3 mijnagents-runner/tests/test_bouwwacht.py
"""
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
from contextlib import redirect_stderr, redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402
import bouwwacht as B  # noqa: E402

WERKWIJZE = open(os.path.join(RUNNER, "werkwijze", "bouwwacht.md"), encoding="utf-8").read()
T0 = 1_800_000_000          # het moment van de pull in de meeste proeven
MIN = 60
ACHTER = "Bouw loopt achter op de code: mijnagents"
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1", "GIT_AUTHOR_NAME": "proef",
           "GIT_AUTHOR_EMAIL": "proef@example.invalid", "GIT_COMMITTER_NAME": "proef",
           "GIT_COMMITTER_EMAIL": "proef@example.invalid"}


class Repo:
    """Een tijdelijke checkout met de drie diensten en een map die geen dienst is. Commits: a (begin), b (mijnagents
    verandert), c (alleen anders/ verandert), d (mijnagents weer), e (agents verandert)."""

    def __init__(self):
        self.map = tempfile.mkdtemp(prefix="bouwwacht-")
        self.repo = os.path.join(self.map, "appportal")
        os.makedirs(self.repo)
        self.git("init", "-q", "-b", "main", ts=T0 - 86400)
        self.c = {}
        for naam, wijziging in (("a", {"mijnagents": "a", "agents": "x", "siyanagents": "y", "anders": "z"}),
                                ("b", {"mijnagents": "b"}), ("c", {"anders": "z2"}), ("d", {"mijnagents": "d"}),
                                ("e", {"agents": "x2"})):
            for dienst, inhoud in wijziging.items():
                os.makedirs(os.path.join(self.repo, dienst), exist_ok=True)
                with open(os.path.join(self.repo, dienst, "f"), "w") as f:
                    f.write(inhoud)
            self.git("add", "-A", ts=T0 - 86400)
            self.git("commit", "-q", "-m", naam, ts=T0 - 86400)
            self.c[naam] = self.git("rev-parse", "HEAD")
        self.zet("a", T0 - 3600)          # de VM staat op a, en alles is gebouwd
        for dienst in B.DIENSTEN:
            self.bouw(dienst)
        self.slot = os.path.join(self.map, "mijnagents-data", "bouwwacht.slot")
        self.oud = (B.REPO, B.MARKERINGEN, B.LOGS, B.SLOT)
        B.REPO, B.MARKERINGEN, B.LOGS, B.SLOT = self.repo, self.map, self.map, self.slot

    def git(self, *args, ts=None):
        env = dict(os.environ, **GIT_ENV)
        if ts is not None:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = f"@{ts} +0000"
        return subprocess.run(["git", "-C", self.repo, *args], check=True, capture_output=True, text=True,
                              env=env).stdout.strip()

    def zet(self, naam, ts):
        """Een git pull (of reset) naar commit `naam` op tijdstip ts: een reflogstap met die tijd."""
        self.git("reset", "-q", "--hard", self.c[naam], ts=ts)

    def boom(self, naam, dienst):
        return self.git("rev-parse", f"{self.c[naam]}:{dienst}")

    def bouw(self, dienst, naam=None, inhoud=None):
        """Wat deploy.sh na een geslaagde bouw doet: de boom van HEAD (of van commit `naam`) in de markering."""
        map_ = os.path.join(self.map, f"{dienst}-data")
        os.makedirs(map_, exist_ok=True)
        if inhoud is None:
            inhoud = self.git("rev-parse", f"HEAD:{dienst}") if naam is None else self.boom(naam, dienst)
        with open(os.path.join(map_, ".built"), "w") as f:
            f.write(inhoud + "\n")

    def zonder_reflog(self):
        self.git("config", "core.logAllRefUpdates", "false")
        shutil.rmtree(os.path.join(self.repo, ".git", "logs"))

    def weg(self):
        B.REPO, B.MARKERINGEN, B.LOGS, B.SLOT = self.oud
        shutil.rmtree(self.map, ignore_errors=True)


class Bord:
    """Het bord zonder netwerk, met de regels van mijnagents/app.py die hier tellen: /agent-status opent een nood die er
    nog niet was met een nieuw nummer en sluit elke open nood die niet in de lijst staat (tenzij nood_sluiten false);
    /api/nood geeft de open noden met hun nummer; /api/klaarzet maakt een item met een bestaande uniek nooit opnieuw.
    weg: elke aanroep faalt; status_weg, klaarzet_weg, nood_weg: alleen die route."""

    def __init__(self, werkwijze=WERKWIJZE, weg=False, status_weg=False, klaarzet_weg=False, nood_weg=False):
        self.werkwijze = werkwijze
        self.weg, self.status_weg, self.klaarzet_weg, self.nood_weg = weg, status_weg, klaarzet_weg, nood_weg
        self.noden = {}         # tekst: nummer, de open noden van bouwwacht
        self.volgend = 100
        self.items = {}         # uniek: item
        self.gestuurd = []

    def call(self, pad, payload=None, method=None):
        self.gestuurd.append((pad, payload))
        if self.weg or (self.status_weg and pad == "/agent-status") or (self.klaarzet_weg and pad == "/api/klaarzet") \
                or (self.nood_weg and pad == "/api/nood"):
            raise OSError("bord onbereikbaar")
        if "werkwijze" in pad:
            return {"werkwijze": self.werkwijze}
        if pad == "/api/nood":
            return {"nood": [{"id": i, "naam": "bouwwacht", "tekst": t, "wie": "claude-code", "open": 1}
                             for t, i in self.noden.items()]}
        if pad == "/agent-status" and isinstance(payload.get("nood"), list):
            lijst = [n["tekst"] for n in payload["nood"]]
            for t in lijst:
                if t not in self.noden:
                    self.volgend += 1
                    self.noden[t] = self.volgend
            if payload.get("nood_sluiten") is not False:
                self.noden = {t: i for t, i in self.noden.items() if t in lijst}
        if pad == "/api/klaarzet":
            for it in payload["items"]:
                self.items.setdefault(it["uniek"], it)
        if pad == "/api/agents":
            return []
        return {"ok": True}

    def rondes(self):
        """Wat er sinds de vorige vraag gestuurd is, en dan opnieuw beginnen."""
        uit, self.gestuurd = self.gestuurd, []
        return uit


def ronde(nu, b):
    echt, bord.call = bord.call, b.call
    b.gestuurd = []
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with B.ag.ronde("proef") as r:
                uitslag = B.werk(r, nu=nu)
    finally:
        bord.call = echt
    return {m["dienst"]: m for m in uitslag}


def eind(b):
    return [p for pad, p in b.gestuurd if pad == "/agent-status"][-1]


def noden(b):
    return {n["tekst"]: n["wie"] for n in eind(b)["nood"]}


def signalen(b):
    """De signalen die deze ronde stuurde."""
    return [i for pad, p in b.gestuurd if pad == "/api/klaarzet" for i in p["items"]]


def logregels(b):
    return [r for pad, p in b.gestuurd if pad == "/api/logboek" for r in p["regels"]]


def main_met(b, nu, argv=()):
    echt, bord.call = bord.call, b.call
    echte_tijd, B.time = B.time, types.SimpleNamespace(time=lambda: nu)
    uit, fout = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(uit), redirect_stderr(fout):
            code = B.main(list(argv))
    finally:
        bord.call, B.time = echt, echte_tijd
    return code, uit.getvalue(), fout.getvalue()


def proef(f):
    def omhulsel():
        repo = Repo()
        try:
            f(repo)
        finally:
            repo.weg()
    omhulsel.__name__ = f.__name__
    return omhulsel


# --- de meting -----------------------------------------------------------------------------------------------------

@proef
def test_gelijk_geeft_geen_nood(repo):
    b = Bord()
    uit = ronde(T0, b)
    assert all(m["stand"] == "gelijk" for m in uit.values()), uit
    assert eind(b)["status"] == "klaar" and eind(b)["nood"] == [] and signalen(b) == []


@proef
def test_verschil_korter_dan_de_drempel_is_een_bouw_die_bezig_is(repo):
    repo.zet("b", T0)
    b = Bord()
    uit = ronde(T0 + 9 * MIN + 59, b)
    assert uit["mijnagents"]["stand"] == "bezig" and uit["mijnagents"]["minuten"] == 9
    assert eind(b)["nood"] == [] and "mijnagents wordt gebouwd, 9 min" in eind(b)["detail"]


@proef
def test_vanaf_tien_minuten_een_nood_voor_claude_code(repo):
    repo.zet("b", T0)
    with open(os.path.join(repo.map, "deploy-mijnagents.log"), "w") as f:
        f.write("vroeger\n\n 2026-10-27T08:00:00+00:00 mijnagents NIET als gebouwd gemarkeerd \n\n")
    b = Bord()
    uit = ronde(T0 + 10 * MIN, b)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 10
    assert noden(b) == {ACHTER: "claude-code"} and eind(b)["status"] == "waakt"
    detail = eind(b)["detail"]
    assert "mijnagents loopt achter, 10 min" in detail and repo.boom("b", "mijnagents")[:7] in detail
    assert "deploylog: 2026-10-27T08:00:00+00:00 mijnagents NIET als gebouwd gemarkeerd" in detail
    assert "agents gelijk" in detail and "siyanagents gelijk" in detail


def test_noodteksten_dragen_geen_getal():
    for tekst in [B.REFLOGNOOD, B.SIGNAALNOOD] + [f(d) for d in B.DIENSTEN for f in (B.noodtekst, B.onbekendtekst)]:
        assert not re.search(r"\d", tekst), tekst


@proef
def test_zonder_of_met_lege_markering_meteen_een_nood(repo):
    repo.zet("b", T0)
    os.remove(os.path.join(repo.map, "mijnagents-data", ".built"))
    repo.bouw("agents", inhoud="")
    b = Bord()
    uit = ronde(T0 + MIN, b)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None
    assert uit["agents"]["stand"] == "achter"
    assert "mijnagents loopt achter, ouder dan de drempel (geen gebouwd" in eind(b)["detail"]
    assert set(noden(b)) == {ACHTER, "Bouw loopt achter op de code: agents"}


@proef
def test_een_tweede_pull_tijdens_een_storing_zet_de_klok_niet_terug(repo):
    repo.zet("b", T0)
    repo.zet("d", T0 + 8 * MIN)
    uit = ronde(T0 + 11 * MIN, Bord())
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 11


@proef
def test_een_pull_die_de_map_niet_raakt_telt_niet(repo):
    repo.zet("b", T0)
    repo.bouw("mijnagents")                      # b is gebouwd
    repo.zet("c", T0 + 30 * MIN)                 # alleen anders/ verandert
    b = Bord()
    uit = ronde(T0 + 60 * MIN, b)
    assert uit["mijnagents"]["stand"] == "gelijk" and eind(b)["nood"] == []
    repo.bouw("mijnagents", naam="a")            # tijdens een storing: a gebouwd, b en c binnengehaald
    uit = ronde(T0 + 40 * MIN, Bord())
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 40


@proef
def test_terug_naar_de_gebouwde_boom_is_gelijk(repo):
    repo.zet("b", T0)
    assert ronde(T0 + 3 * MIN, Bord())["mijnagents"]["stand"] == "bezig"
    repo.zet("a", T0 + 4 * MIN)                  # reset terug
    b = Bord()
    assert ronde(T0 + 20 * MIN, b)["mijnagents"]["stand"] == "gelijk" and eind(b)["nood"] == []


@proef
def test_een_branch_wissel_telt_als_een_pull(repo):
    repo.git("checkout", "-q", "-B", "zij", repo.c["b"], ts=T0)
    uit = ronde(T0 + 12 * MIN, Bord())
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 12
    repo.git("checkout", "-q", "main", ts=T0 + 13 * MIN)     # main staat nog op a
    assert ronde(T0 + 14 * MIN, Bord())["mijnagents"]["stand"] == "gelijk"


@proef
def test_een_markering_die_niet_in_de_reflog_staat_is_ouder_dan_de_drempel(repo):
    repo.zet("b", T0)
    repo.bouw("mijnagents", inhoud="0" * 40)
    b = Bord()
    uit = ronde(T0 + MIN, b)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None
    assert ACHTER in noden(b) and B.REFLOGNOOD not in noden(b), "de reflog is er, alleen de markering staat er niet in"


@proef
def test_tussen_twee_rondes_even_gelijk_begint_de_klok_opnieuw(repo):
    """Codex-resultaattoets 3.1: een verschil van 2 minuten gaf een bouwnood van 10 minuten."""
    repo.zet("b", T0)
    b = Bord()
    assert ronde(T0 + MIN, b)["mijnagents"]["stand"] == "bezig"
    repo.zet("a", T0 + 2 * MIN)                  # terug naar de gebouwde versie, geen ronde ziet het
    repo.zet("b", T0 + 9 * MIN)
    uit = ronde(T0 + 11 * MIN, b)
    assert uit["mijnagents"]["stand"] == "bezig" and uit["mijnagents"]["minuten"] == 2, uit["mijnagents"]
    assert eind(b)["nood"] == []


@proef
def test_zonder_reflog_meteen_een_nood_met_de_reden(repo):
    """X2: zonder reflog is het begin onbekend, dus ouder dan de drempel; de nood over de reflog zegt waarom."""
    repo.zonder_reflog()
    repo.zet("b", T0)
    assert B.reflog() == []
    b = Bord()
    uit = ronde(T0 + MIN, b)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None
    assert noden(b) == {ACHTER: "claude-code", B.REFLOGNOOD: "claude-code"}
    repo.bouw("mijnagents")
    b2 = Bord()
    ronde(T0 + 3 * MIN, b2)
    assert eind(b2)["nood"] == [], "gelijk heeft geen reflog nodig"


@proef
def test_een_achterstand_blijft_als_de_reflog_wegvalt(repo):
    """Codex-resultaattoets 4.3: een bestaande bouwnood sloot als de reflog wegviel."""
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 12 * MIN, b)
    assert ACHTER in b.noden
    repo.zonder_reflog()
    uit = ronde(T0 + 14 * MIN, b)
    assert uit["mijnagents"]["stand"] == "achter" and ACHTER in b.noden


@proef
def test_herstel_sluit_de_nood(repo):
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 15 * MIN, b)
    assert ACHTER in b.noden
    repo.bouw("mijnagents")
    ronde(T0 + 17 * MIN, b)
    assert b.noden == {} and eind(b)["status"] == "klaar" and eind(b).get("nood_sluiten") is not False


@proef
def test_twee_diensten_in_storing_geven_twee_noden(repo):
    repo.zet("b", T0)
    repo.zet("e", T0 + MIN)
    b = Bord()
    ronde(T0 + 12 * MIN, b)
    assert noden(b) == {ACHTER: "claude-code", "Bouw loopt achter op de code: agents": "claude-code"}


@proef
def test_een_dienst_die_niet_na_te_kijken_is_houdt_de_andere_niet_tegen(repo):
    oud = B.DIENSTEN
    B.DIENSTEN = ("weg", "mijnagents", "agents")
    try:
        repo.zet("b", T0)
        b = Bord()
        uit = ronde(T0 + 10 * MIN, b)
    finally:
        B.DIENSTEN = oud
    assert uit["weg"]["stand"] == "onbekend" and uit["agents"]["stand"] == "gelijk"
    assert noden(b) == {"Bouwwacht kan weg niet nakijken": "claude-code", ACHTER: "claude-code"}


@proef
def test_een_onleesbare_markering_is_onbekend_geen_vals_alarm(repo):
    pad = os.path.join(repo.map, "mijnagents-data", ".built")
    os.remove(pad)
    os.makedirs(pad)
    b = Bord()
    uit = ronde(T0 + MIN, b)
    assert uit["mijnagents"]["stand"] == "onbekend" and "markering niet leesbaar" in uit["mijnagents"]["reden"]
    assert noden(b) == {"Bouwwacht kan mijnagents niet nakijken": "claude-code"} and signalen(b) == []


# --- het signaal: een per storing -----------------------------------------------------------------------------------

@proef
def test_een_storing_geeft_een_signaal_voor_mehdi(repo):
    """Mehdi, 27-10-2026: "stuurt bij een bouw die achterloopt een keer per storing een signaal via De Bode"."""
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 9 * MIN, b)
    assert signalen(b) == [], "een bouw die bezig is, geeft geen signaal"
    ronde(T0 + 10 * MIN, b)
    assert signalen(b) == [] and ACHTER in b.noden, "eerst de nood; het signaal draagt haar nummer"
    nummer = b.noden[ACHTER]
    ronde(T0 + 12 * MIN, b)
    [s] = signalen(b)
    gebouwd = repo.boom("a", "mijnagents")[:7]
    assert s["voor"] == "mehdi" and s["soort"] == "signaal" and s["van"] == "bouwwacht"
    assert s["titel"] == "Bouw van mijnagents loopt achter op de code"
    assert s["uniek"] == f"bouwwacht-achter-mijnagents-{nummer}"
    assert "~/deploy-mijnagents.log" in s["inhoud"] and gebouwd in s["inhoud"] and "10 minuten of langer" in s["inhoud"]
    # dezelfde storing, ook na een tweede pull en later: zelfde uniek, dus het bord maakt geen tweede
    repo.zet("d", T0 + 13 * MIN)
    ronde(T0 + 30 * MIN, b)
    assert [x["uniek"] for x in signalen(b)] == [s["uniek"]] and list(b.items) == [s["uniek"]]
    # na herstel: nog een keer dezelfde uniek, als terugblik (het bord maakt er geen tweede van), en de nood sluit
    repo.bouw("mijnagents")
    ronde(T0 + 31 * MIN, b)
    assert [x["uniek"] for x in signalen(b)] == [s["uniek"]] and "intussen weer gelijk" in signalen(b)[0]["inhoud"]
    assert ACHTER not in b.noden and len(b.items) == 1
    ronde(T0 + 33 * MIN, b)
    assert signalen(b) == []
    # de volgende storing is nieuw
    repo.zet("b", T0 + 40 * MIN)
    for minuut in (50, 52):
        ronde(T0 + minuut * MIN, b)
    assert len(b.items) == 2 and b.noden[ACHTER] != nummer
    assert f"bouwwacht-achter-mijnagents-{b.noden[ACHTER]}" in b.items


@proef
def test_na_herstel_door_terugzetten_is_de_volgende_storing_nieuw(repo):
    """Codex-resultaattoets 6.1: zonder nieuwe bouw kreeg een latere storing dezelfde uniek, en dan geen signaal."""
    repo.zet("b", T0)
    b = Bord()
    for minuut in (10, 12):
        ronde(T0 + minuut * MIN, b)
    assert len(b.items) == 1
    repo.zet("a", T0 + 13 * MIN)                 # terug naar de gebouwde code; geen ronde ziet het
    repo.zet("b", T0 + 14 * MIN)
    ronde(T0 + 15 * MIN, b)                      # de klok begon opnieuw: bezig, de nood sluit
    assert ACHTER not in b.noden
    for minuut in (24, 26):
        ronde(T0 + minuut * MIN, b)
    assert len(b.items) == 2


@proef
def test_een_markering_die_even_ontbreekt_is_geen_nieuwe_storing(repo):
    """Codex-resultaattoets 6.2, 6.3 en 7.1: geen tweede signaal; zonder markering zegt de tekst dat de duur onbekend
    is; en een gelijkheid daarna is wel een nieuwe storing."""
    pad = os.path.join(repo.map, "mijnagents-data", ".built")
    repo.zet("b", T0)
    b = Bord()
    for minuut in (10, 12):
        ronde(T0 + minuut * MIN, b)
    [eerste] = b.items
    os.remove(pad)
    ronde(T0 + 14 * MIN, b)
    [s] = signalen(b)
    assert s["uniek"] == eerste and "sinds een onbekende tijd" in s["inhoud"] and "10 minuten" not in s["inhoud"]
    repo.bouw("mijnagents", naam="a")            # de oude markering komt terug
    ronde(T0 + 16 * MIN, b)
    assert [x["uniek"] for x in signalen(b)] == [eerste] and len(b.items) == 1
    repo.zet("a", T0 + 17 * MIN)                 # terug naar de gebouwde code; geen ronde ziet het
    repo.zet("b", T0 + 18 * MIN)
    for minuut in (19, 29, 31):
        ronde(T0 + minuut * MIN, b)
    assert len(b.items) == 2


def test_de_signaaltitel_belt_mehdi_niet_op():
    """Het woord stil in een signaaltitel laat De Bode bellen (AGENTNORM.md 6); een bouw die achterloopt is geen oproep."""
    for dienst in B.DIENSTEN:
        for m in ({"stand": "achter", "minuten": None, "gebouwd": "abc1234"},
                  {"stand": "achter", "minuten": 12, "gebouwd": "abc1234"},
                  {"stand": "gelijk"}, {"stand": "bezig", "minuten": 2, "gebouwd": "abc1234"},
                  {"stand": "onbekend", "reden": "x"}):
            s = B.signaal(dict(m, dienst=dienst), 101)
            assert "stil" not in s["titel"].lower() and "stil" not in s["uniek"].lower(), s
            assert s["uniek"] == f"bouwwacht-achter-{dienst}-101" and s["titel"] == f"Bouw van {dienst} loopt achter op de code"


@proef
def test_een_storing_die_herstelt_voor_haar_signaal_krijgt_het_toch(repo):
    """Tweede overleg X2: de nood ging open, de bouw herstelde voor de volgende ronde, en Mehdi kreeg niets."""
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 10 * MIN, b)
    assert ACHTER in b.noden and b.items == {}
    nummer = b.noden[ACHTER]
    repo.bouw("mijnagents")                      # hersteld voor de volgende ronde
    ronde(T0 + 12 * MIN, b)
    [s] = signalen(b)
    assert s["uniek"] == f"bouwwacht-achter-mijnagents-{nummer}" and "intussen weer gelijk" in s["inhoud"]
    assert ACHTER not in b.noden, "na het signaal sluit de nood"
    # ook als de klok door een nieuwe pull onder de drempel zakt: dan een terugblik met de nieuwe bouw
    repo.zet("d", T0 + 13 * MIN)
    for minuut in (24, 26):
        ronde(T0 + minuut * MIN, b)
    nummer2 = b.noden[ACHTER]
    repo.zet("b", T0 + 27 * MIN)                 # even gelijk met de gebouwde versie, geen ronde ziet het
    repo.zet("d", T0 + 27 * MIN + 30)            # en meteen een nieuwe pull
    ronde(T0 + 28 * MIN, b)
    assert [x["uniek"] for x in signalen(b)] == [f"bouwwacht-achter-mijnagents-{nummer2}"]
    assert "opnieuw aan het bouwen" in signalen(b)[0]["inhoud"] and ACHTER not in b.noden


@proef
def test_een_dienst_die_even_niet_na_te_kijken_is_sluit_zijn_storing_niet(repo):
    """Tweede overleg K2: achter, gesignaleerd, onbekend, achter gaf twee signalen voor een storing."""
    pad = os.path.join(repo.map, "mijnagents-data", ".built")
    repo.zet("b", T0)
    b = Bord()
    for minuut in (10, 12):
        ronde(T0 + minuut * MIN, b)
    nummer = b.noden[ACHTER]
    with open(pad) as f:
        gebouwd = f.read()
    os.remove(pad)
    os.makedirs(pad)                             # de markering is even niet te lezen
    ronde(T0 + 14 * MIN, b)
    assert b.noden[ACHTER] == nummer and "Bouwwacht kan mijnagents niet nakijken" in b.noden
    os.rmdir(pad)
    with open(pad, "w") as f:
        f.write(gebouwd)
    ronde(T0 + 16 * MIN, b)
    assert b.noden[ACHTER] == nummer and len(b.items) == 1


@proef
def test_twee_diensten_in_storing_geven_twee_signalen(repo):
    """Tweede overleg X3."""
    repo.zet("b", T0)
    repo.zet("e", T0 + MIN)
    b = Bord()
    for minuut in (12, 14):
        ronde(T0 + minuut * MIN, b)
    assert sorted(i["sleutel"] for i in b.items.values()) == ["agents", "mijnagents"]
    assert len({i["uniek"] for i in b.items.values()}) == 2


@proef
def test_zonder_open_noden_sluit_de_ronde_niets(repo):
    """Tweede overleg X2: weet de ronde de open noden niet, dan verdwijnt geen storing voor haar signaal vertrok."""
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 10 * MIN, b)
    nummer = b.noden[ACHTER]
    repo.bouw("mijnagents")
    b.nood_weg = True
    ronde(T0 + 12 * MIN, b)
    assert eind(b)["nood_sluiten"] is False and b.noden[ACHTER] == nummer and b.items == {}
    b.nood_weg = False
    ronde(T0 + 14 * MIN, b)
    assert [x["uniek"] for x in signalen(b)] == [f"bouwwacht-achter-mijnagents-{nummer}"] and ACHTER not in b.noden


@proef
def test_een_signaal_dat_niet_lukt_houdt_de_bouwnood_niet_tegen(repo):
    repo.zet("b", T0)
    b = Bord(klaarzet_weg=True)
    for minuut in (12, 14):
        ronde(T0 + minuut * MIN, b)
    assert noden(b) == {ACHTER: "claude-code", B.SIGNAALNOOD: "claude-code"}
    assert "signaal niet klaargezet" in eind(b)["detail"]
    b.klaarzet_weg = False
    ronde(T0 + 16 * MIN, b)
    assert len(b.items) == 1 and B.SIGNAALNOOD not in b.noden, "de volgende ronde probeert opnieuw"


@proef
def test_zonder_open_noden_wacht_het_signaal(repo):
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 12 * MIN, b)
    b.nood_weg = True
    ronde(T0 + 14 * MIN, b)
    assert signalen(b) == [] and noden(b) == {ACHTER: "claude-code", B.SIGNAALNOOD: "claude-code"}
    assert logregels(b) == [], "zonder de open noden geen regel in het werkverslag"
    b.nood_weg = False
    ronde(T0 + 16 * MIN, b)
    assert len(b.items) == 1 and B.SIGNAALNOOD not in b.noden


# --- de ronde -------------------------------------------------------------------------------------------------------

@proef
def test_de_ronde_leest_alleen_en_schrijft_niets(repo):
    repo.zet("b", T0)
    voor = {p: open(p).read() for p in (os.path.join(repo.map, f"{d}-data", ".built") for d in B.DIENSTEN)}
    bestanden = sorted(os.path.relpath(os.path.join(w, f), repo.map) for w, _, fs in os.walk(repo.map) for f in fs)
    head, status, reflog = repo.git("rev-parse", "HEAD"), repo.git("status", "--porcelain"), repo.git("reflog")
    gebruikt = []
    echt = B.subprocess.run

    def vang(cmd, *a, **k):
        gebruikt.append(cmd[3])
        return echt(cmd, *a, **k)

    B.subprocess.run = vang
    try:
        ronde(T0 + 12 * MIN, Bord())
    finally:
        B.subprocess.run = echt
    assert set(gebruikt) <= {"rev-parse", "log"}, gebruikt
    assert {p: open(p).read() for p in voor} == voor
    assert (repo.git("rev-parse", "HEAD"), repo.git("status", "--porcelain"), repo.git("reflog")) == (head, status, reflog)
    assert sorted(os.path.relpath(os.path.join(w, f), repo.map) for w, _, fs in os.walk(repo.map) for f in fs) == bestanden


@proef
def test_een_nieuwe_nood_staat_een_keer_in_het_werkverslag(repo):
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 12 * MIN, b)
    assert [(r["onderwerp"], r["stap"]) for r in logregels(b)] == [("mijnagents", "fout")]
    ronde(T0 + 14 * MIN, b)
    assert logregels(b) == [] and ACHTER in noden(b)


@proef
def test_alleen_mijn_eigen_naam_op_het_bord(repo):
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 12 * MIN, b)
    assert {p["naam"] for pad, p in b.gestuurd if pad == "/agent-status"} == {"bouwwacht"}


@proef
def test_zonder_grenzen_in_de_werkwijze_geen_werk_en_geen_bouwnood_gesloten(repo):
    repo.zet("b", T0)
    b = Bord()
    ronde(T0 + 12 * MIN, b)
    b.werkwijze = "# Werkwijze\n\nIk kijk naar de bouw."
    ronde(T0 + 14 * MIN, b)
    assert noden(b) == {"Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist": "mehdi"}
    assert eind(b)["nood_sluiten"] is False and ACHTER in b.noden, "niet gemeten, dus de bouwnood blijft open"
    assert signalen(b) == []


@proef
def test_droog_stuurt_niets(repo):
    repo.zet("b", T0)
    b = Bord()
    code, uit, _ = main_met(b, T0 + 12 * MIN, ["--droog"])
    assert b.gestuurd == [] and not os.path.exists(repo.slot)
    assert code == 1 and "mijnagents loopt achter, 12 min" in uit, uit


@proef
def test_main_draait_een_ronde(repo):
    repo.zet("b", T0)
    b = Bord()
    code, _, _ = main_met(b, T0 + 12 * MIN)
    assert code == 0 and ACHTER in b.noden


@proef
def test_zonder_bord_staat_de_meting_in_het_cronlog(repo):
    repo.zet("b", T0)
    code, _, fout = main_met(Bord(weg=True), T0 + 12 * MIN)
    assert code == 1 and "ronde gestopt: Werkwijze niet gelezen: bord onbereikbaar" in fout
    assert "mijnagents loopt achter, 12 min" in fout, fout


@proef
def test_een_eindhartslag_die_niet_aankomt_geeft_exit_1(repo):
    repo.zet("b", T0)
    code, _, fout = main_met(Bord(status_weg=True), T0 + 12 * MIN)
    assert code == 1
    assert "eindhartslag niet aangekomen" in fout and "mijnagents loopt achter, 12 min" in fout


@proef
def test_een_tweede_ronde_tegelijk_slaat_over(repo):
    repo.zet("b", T0)
    b = Bord()
    slot = B.neem_slot()
    try:
        assert slot
        code, _, fout = main_met(b, T0 + 12 * MIN)
        assert code == 0 and b.gestuurd == [] and "een vorige ronde loopt nog" in fout
    finally:
        slot.close()
    code, _, _ = main_met(b, T0 + 12 * MIN)
    assert code == 0 and ACHTER in b.noden


@proef
def test_geen_slotbestand_geen_ronde_en_exit_1(repo):
    """Codex-resultaattoets 2.2: zonder slot draait er geen ronde die met een andere kan botsen."""
    with open(os.path.join(repo.map, "bestand"), "w") as f:
        f.write("geen map")
    B.SLOT = os.path.join(repo.map, "bestand", "bouwwacht.slot")
    repo.zet("b", T0)
    b = Bord()
    code, _, fout = main_met(b, T0 + 12 * MIN)
    assert code == 1 and b.gestuurd == []
    assert "geen slot voor de ronde" in fout and "mijnagents loopt achter, 12 min" in fout, fout


@proef
def test_een_andere_slotfout_is_geen_bezette_ronde(repo):
    repo.zet("b", T0)
    b = Bord()

    def kapot(f, wijze):
        raise OSError(9, "Bad file descriptor")

    echt = B.fcntl
    B.fcntl = types.SimpleNamespace(flock=kapot, LOCK_EX=echt.LOCK_EX, LOCK_NB=echt.LOCK_NB)
    try:
        code, _, fout = main_met(b, T0 + 12 * MIN)
    finally:
        B.fcntl = echt
    assert code == 1 and b.gestuurd == [] and "geen slot voor de ronde (OSError" in fout, fout


def test_runner_gaat_door_de_gedeelde_ronde():
    with open(os.path.join(RUNNER, "bouwwacht.py"), encoding="utf-8") as f:
        assert "with ag.ronde(" in f.read()


def test_werkwijze_haalt_de_norm():
    import importlib
    nieuwe_agent = importlib.import_module("nieuwe-agent")
    agent = {"naam": "bouwwacht", "label": "De Bouwwacht", "type": "regie", "rol": "ziet of de diensten bouwen",
             "mandaat": "lezen en melden", "cadans": "elke 2 minuten", "mag": ["een nood zetten"],
             "grenzen": ["nooit bouwen"]}
    assert nieuwe_agent.controleer(agent, WERKWIJZE) == []
    nooit, mehdi = bord.grenzen(WERKWIJZE)
    assert len(nooit) == 6 and len(mehdi) == 4, (nooit, mehdi)


if __name__ == "__main__":
    import traceback
    goed = fout = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                f()
                goed += 1
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"FOUT {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout")
    sys.exit(1 if fout else 0)
