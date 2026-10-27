"""Grendels op De Bouwwacht (bouwwacht.py): alarm als een dienst op de VM niet meer herbouwt na een git pull.

Waarom: van 26-10 rond 19:00 tot 27-10 07:56 UTC faalde elke bouw van het bord en draaide het een oude bouw, zonder dat
iemand het zag (K5, uitrol van PR #103). Deze test legt vast wat het driehoeksoverleg van 27-10-2026 vroeg (X2, X3, X5,
K2, K5):

- gelijk: geen nood; een verschil korter dan 10 minuten is een bouw die bezig is, geen nood;
- vanaf 10 minuten, of zonder markering, of met een markering die niet in de reflog staat: de nood
  "Bouw loopt achter op de code: <map>", voor claude-code, zonder getal in de tekst;
- de klok begint bij de echte pull (reflog), ook in de eerste ronde; een tweede pull tijdens een storing zet ze niet
  terug; een pull die de map niet raakt, telt niet; een reset of branch-wissel terug naar de gebouwde boom is gelijk;
- toont de reflog het begin, dan volgt het anker, ook na een tussentijdse gelijkheid die geen ronde zag; zonder
  reflog is de eigen stand de klok; een nieuwe markering begint het anker opnieuw;
- herstel sluit de nood; twee diensten in storing geven twee noden; een dienst die niet na te kijken is, houdt de
  andere niet tegen;
- de ronde leest alleen (rev-parse en log) en schrijft niets buiten haar eigen stand; --droog schrijft en stuurt niets;
- zonder bord staat de meting in het cronlog en is de exitcode niet 0;
- een nieuwe nood staat een keer in het werkverslag, niet elke ronde;
- de runner gaat door de gedeelde ronde, en zijn werkwijze haalt de norm.

Geen netwerk en geen echte klok: een tijdelijke git-repo met vaste reflogtijden (GIT_COMMITTER_DATE) en een nagebootst
bord. Draaien: python3 mijnagents-runner/tests/test_bouwwacht.py
"""
import io
import json
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
        self.stand = os.path.join(self.map, "mijnagents-data", "bouwwacht.json")
        self.oud = (B.REPO, B.MARKERINGEN, B.LOGS, B.STAND)
        B.REPO, B.MARKERINGEN, B.LOGS, B.STAND = self.repo, self.map, self.map, self.stand

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

    def weg(self):
        B.REPO, B.MARKERINGEN, B.LOGS, B.STAND = self.oud
        shutil.rmtree(self.map, ignore_errors=True)


class Bord:
    """Vangt op wat de ronde naar het bord stuurt, zonder netwerk. open_noden: wat /api/nood teruggeeft voor bouwwacht
    (None: het bord weet het niet). weg: elke aanroep faalt, zoals een bord dat niet antwoordt."""

    def __init__(self, open_noden=(), werkwijze=WERKWIJZE, weg=False, status_weg=False, klaarzet_weg=False):
        self.open_noden = None if open_noden is None else [dict(n, naam="bouwwacht") for n in open_noden]
        self.werkwijze = werkwijze
        self.weg = weg
        self.status_weg = status_weg
        self.klaarzet_weg = klaarzet_weg
        self.gestuurd = []

    def call(self, pad, payload=None, method=None):
        self.gestuurd.append((pad, payload))
        if self.weg or (self.status_weg and pad == "/agent-status") or (self.klaarzet_weg and pad == "/api/klaarzet"):
            raise OSError("bord onbereikbaar")
        if "werkwijze" in pad:
            return {"werkwijze": self.werkwijze}
        if pad == "/api/nood":
            if self.open_noden is None:
                raise OSError("geen noden te lezen")
            return {"nood": self.open_noden}
        if pad == "/api/agents":
            return []
        return {"ok": True}

    def eind(self):
        return [p for pad, p in self.gestuurd if pad == "/agent-status"][-1]

    def signalen(self):
        return [i for pad, p in self.gestuurd if pad == "/api/klaarzet" for i in p["items"]]

    def logregels(self):
        return [r for pad, p in self.gestuurd if pad == "/api/logboek" for r in p["regels"]]


def ronde(nu, nabootsing=None):
    nabootsing = nabootsing or Bord()
    echt, bord.call = bord.call, nabootsing.call
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with B.ag.ronde("proef") as r:
                uitslag = B.werk(r, nu=nu)
    finally:
        bord.call = echt
    return {m["dienst"]: m for m in uitslag}, nabootsing


def noden(nabootsing):
    return {n["tekst"]: n["wie"] for n in nabootsing.eind()["nood"]}


def proef(f):
    def omhulsel():
        repo = Repo()
        try:
            f(repo)
        finally:
            repo.weg()
    omhulsel.__name__ = f.__name__
    return omhulsel


@proef
def test_gelijk_geeft_geen_nood(repo):
    uit, b = ronde(T0)
    assert all(m["stand"] == "gelijk" for m in uit.values()), uit
    assert b.eind()["status"] == "klaar" and b.eind()["nood"] == []
    assert not os.path.exists(repo.stand), "niets te onthouden als alles gelijk is"


@proef
def test_verschil_korter_dan_de_drempel_is_een_bouw_die_bezig_is(repo):
    repo.zet("b", T0)
    uit, b = ronde(T0 + 9 * MIN + 59)
    assert uit["mijnagents"]["stand"] == "bezig" and uit["mijnagents"]["minuten"] == 9
    assert b.eind()["nood"] == [] and "mijnagents wordt gebouwd, 9 min" in b.eind()["detail"]


@proef
def test_vanaf_tien_minuten_een_nood_voor_claude_code(repo):
    repo.zet("b", T0)
    with open(os.path.join(repo.map, "deploy-mijnagents.log"), "w") as f:
        f.write("vroeger\n\n 2026-10-27T08:00:00+00:00 mijnagents NIET als gebouwd gemarkeerd \n\n")
    uit, b = ronde(T0 + 10 * MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 10
    assert noden(b) == {"Bouw loopt achter op de code: mijnagents": "claude-code"}
    assert b.eind()["status"] == "waakt"
    detail = b.eind()["detail"]
    assert "mijnagents loopt achter, 10 min" in detail and repo.boom("b", "mijnagents")[:7] in detail
    assert "deploylog: 2026-10-27T08:00:00+00:00 mijnagents NIET als gebouwd gemarkeerd" in detail
    assert "agents gelijk" in detail and "siyanagents gelijk" in detail


def test_noodteksten_dragen_geen_getal():
    for dienst in B.DIENSTEN:
        for tekst in (B.noodtekst(dienst), B.onbekendtekst(dienst)):
            assert not re.search(r"\d", tekst), tekst


@proef
def test_zonder_of_met_lege_markering_meteen_een_nood(repo):
    repo.zet("b", T0)
    os.remove(os.path.join(repo.map, "mijnagents-data", ".built"))
    uit, b = ronde(T0 + MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None
    assert "mijnagents loopt achter, ouder dan de drempel (geen gebouwd" in b.eind()["detail"]
    repo.bouw("agents", inhoud="")
    uit, b = ronde(T0 + MIN)
    assert uit["agents"]["stand"] == "achter"
    assert set(noden(b)) == {"Bouw loopt achter op de code: mijnagents", "Bouw loopt achter op de code: agents"}


@proef
def test_een_tweede_pull_tijdens_een_storing_zet_de_klok_niet_terug(repo):
    repo.zet("b", T0)
    repo.zet("d", T0 + 8 * MIN)
    uit, _ = ronde(T0 + 11 * MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 11


@proef
def test_een_pull_die_de_map_niet_raakt_telt_niet(repo):
    repo.zet("b", T0)
    repo.bouw("mijnagents")                      # b is gebouwd
    repo.zet("c", T0 + 30 * MIN)                 # alleen anders/ verandert
    uit, b = ronde(T0 + 60 * MIN)
    assert uit["mijnagents"]["stand"] == "gelijk" and b.eind()["nood"] == []
    repo.bouw("mijnagents", naam="a")            # tijdens een storing: a gebouwd, b en c binnengehaald
    uit, _ = ronde(T0 + 40 * MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 40


@proef
def test_terug_naar_de_gebouwde_boom_is_gelijk(repo):
    repo.zet("b", T0)
    uit, _ = ronde(T0 + 3 * MIN)
    assert uit["mijnagents"]["stand"] == "bezig"
    assert "mijnagents" in json.load(open(repo.stand))
    repo.zet("a", T0 + 4 * MIN)                  # reset terug
    uit, b = ronde(T0 + 20 * MIN)
    assert uit["mijnagents"]["stand"] == "gelijk" and b.eind()["nood"] == []
    assert "mijnagents" not in json.load(open(repo.stand)), "gelijk wist het anker"


@proef
def test_een_branch_wissel_telt_als_een_pull(repo):
    repo.git("checkout", "-q", "-B", "zij", repo.c["b"], ts=T0)
    uit, _ = ronde(T0 + 12 * MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 12
    repo.git("checkout", "-q", "main", ts=T0 + 13 * MIN)     # main staat nog op a
    uit, _ = ronde(T0 + 14 * MIN)
    assert uit["mijnagents"]["stand"] == "gelijk"


@proef
def test_een_markering_die_niet_in_de_reflog_staat_is_ouder_dan_de_drempel(repo):
    repo.zet("b", T0)
    repo.bouw("mijnagents", inhoud="0" * 40)
    uit, b = ronde(T0 + MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None
    assert "Bouw loopt achter op de code: mijnagents" in noden(b)


@proef
def test_een_storing_geeft_een_signaal_voor_mehdi(repo):
    """Mehdi, 27-10-2026: "stuurt bij een bouw die achterloopt een keer per storing een signaal via De Bode"."""
    repo.zet("b", T0)
    _, b = ronde(T0 + 9 * MIN)
    assert b.signalen() == [], "een bouw die bezig is, geeft geen signaal"
    _, b = ronde(T0 + 10 * MIN)
    [s] = b.signalen()
    gebouwd = repo.boom("a", "mijnagents")[:7]
    assert s["voor"] == "mehdi" and s["soort"] == "signaal" and s["van"] == "bouwwacht"
    assert s["titel"] == "Bouw van mijnagents loopt achter op de code"
    assert s["uniek"] == f"bouwwacht-achter-mijnagents-{gebouwd}"
    assert "~/deploy-mijnagents.log" in s["inhoud"] and gebouwd in s["inhoud"]
    # dezelfde storing, ook na een tweede pull en later: zelfde uniek en zelfde tekst, dus het bord maakt geen tweede
    repo.zet("d", T0 + 12 * MIN)
    _, b2 = ronde(T0 + 30 * MIN)
    assert b2.signalen() == [s]
    # na een geslaagde bouw is de volgende storing nieuw
    repo.bouw("mijnagents")
    _, b3 = ronde(T0 + 31 * MIN)
    assert b3.signalen() == []
    repo.zet("b", T0 + 40 * MIN)
    _, b4 = ronde(T0 + 55 * MIN)
    assert [x["uniek"] for x in b4.signalen()] == [f"bouwwacht-achter-mijnagents-{repo.boom('d', 'mijnagents')[:7]}"]


def test_de_signaaltitel_belt_mehdi_niet_op():
    """Het woord stil in een signaaltitel laat De Bode bellen (AGENTNORM.md 6); een bouw die achterloopt is geen oproep."""
    for dienst in B.DIENSTEN:
        s = B.signaal({"dienst": dienst, "gebouwd": "abc1234"})
        assert "stil" not in s["titel"].lower() and "stil" not in s["uniek"].lower(), s


@proef
def test_geen_signaal_als_de_dienst_niet_na_te_kijken_is(repo):
    pad = os.path.join(repo.map, "mijnagents-data", ".built")
    os.remove(pad)
    os.makedirs(pad)
    _, b = ronde(T0 + MIN)
    assert b.signalen() == []


@proef
def test_een_signaal_dat_niet_lukt_houdt_de_bouwnood_niet_tegen(repo):
    repo.zet("b", T0)
    _, b = ronde(T0 + 12 * MIN, Bord(klaarzet_weg=True))
    assert noden(b) == {"Bouw loopt achter op de code: mijnagents": "claude-code",
                        "Bouwwacht kan het signaal voor Mehdi niet klaarzetten": "claude-code"}
    assert "signaal niet klaargezet" in b.eind()["detail"]
    _, b = ronde(T0 + 14 * MIN)
    assert len(b.signalen()) == 1 and "Bouwwacht kan het signaal voor Mehdi niet klaarzetten" not in noden(b)


@proef
def test_een_vastgestelde_achterstand_blijft_als_de_reflog_wegvalt(repo):
    """Codex-resultaattoets 4.3: anders begon de klok opnieuw en sloot het bord een bestaande bouwnood."""
    repo.zet("b", T0)
    repo.bouw("mijnagents", inhoud="0" * 40)
    uit, _ = ronde(T0 + MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None
    repo.git("config", "core.logAllRefUpdates", "false")
    shutil.rmtree(os.path.join(repo.repo, ".git", "logs"))
    assert B.reflog() == []
    uit, b = ronde(T0 + 3 * MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None, uit["mijnagents"]
    assert "Bouw loopt achter op de code: mijnagents" in noden(b)
    repo.bouw("mijnagents")                      # gebouwd: gelijk, en het anker is weg
    uit, b = ronde(T0 + 5 * MIN)
    assert uit["mijnagents"]["stand"] == "gelijk" and b.eind()["nood"] == []
    assert "mijnagents" not in json.load(open(repo.stand))


@proef
def test_zonder_reflog_is_de_eigen_stand_het_anker(repo):
    repo.git("config", "core.logAllRefUpdates", "false")
    shutil.rmtree(os.path.join(repo.repo, ".git", "logs"))
    repo.zet("b", T0)
    assert B.reflog() == []
    uit, b = ronde(T0 + 2 * MIN)                 # eerste ronde: het anker is nu
    assert uit["mijnagents"]["stand"] == "bezig" and uit["mijnagents"]["minuten"] == 0 and b.eind()["nood"] == []
    uit, _ = ronde(T0 + 11 * MIN)
    assert uit["mijnagents"]["stand"] == "bezig" and uit["mijnagents"]["minuten"] == 9
    uit, b = ronde(T0 + 12 * MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] == 10
    assert "Bouw loopt achter op de code: mijnagents" in noden(b)


@proef
def test_toont_de_reflog_het_begin_dan_volgt_het_anker(repo):
    gebouwd = repo.boom("a", "mijnagents")
    os.makedirs(os.path.dirname(repo.stand), exist_ok=True)
    with open(repo.stand, "w") as f:
        json.dump({"mijnagents": {"gebouwd": gebouwd, "sinds": T0 - 20 * MIN}}, f)
    repo.zet("b", T0)
    uit, _ = ronde(T0 + 5 * MIN)
    assert uit["mijnagents"]["minuten"] == 5, "de reflog toont dat de code tot T0 gelijk was; het oude anker vervalt"
    assert json.load(open(repo.stand))["mijnagents"]["sinds"] == T0
    with open(repo.stand, "w") as f:
        json.dump({"mijnagents": {"gebouwd": gebouwd, "sinds": T0 + 4 * MIN}}, f)
    uit, _ = ronde(T0 + 5 * MIN)
    assert uit["mijnagents"]["minuten"] == 5, "de reflog zet het begin vroeger dan het anker"


@proef
def test_tussen_twee_rondes_even_gelijk_begint_de_klok_opnieuw(repo):
    """Codex-resultaattoets 3.1: een verschil van 2 minuten gaf een bouwnood van 10 minuten."""
    repo.zet("b", T0)
    uit, _ = ronde(T0 + MIN)                     # het anker komt op T0
    assert uit["mijnagents"]["stand"] == "bezig"
    repo.zet("a", T0 + 2 * MIN)                  # terug naar de gebouwde versie, geen ronde ziet het
    repo.zet("b", T0 + 9 * MIN)
    uit, b = ronde(T0 + 11 * MIN)
    assert uit["mijnagents"]["stand"] == "bezig" and uit["mijnagents"]["minuten"] == 2, uit["mijnagents"]
    assert b.eind()["nood"] == []


@proef
def test_een_nieuwe_markering_begint_het_anker_opnieuw(repo):
    os.makedirs(os.path.dirname(repo.stand), exist_ok=True)
    with open(repo.stand, "w") as f:
        json.dump({"mijnagents": {"gebouwd": "f" * 40, "sinds": T0 - 86400}}, f)
    repo.zet("b", T0)
    uit, _ = ronde(T0 + 3 * MIN)
    assert uit["mijnagents"]["stand"] == "bezig" and uit["mijnagents"]["minuten"] == 3
    assert json.load(open(repo.stand))["mijnagents"] == {"gebouwd": repo.boom("a", "mijnagents"), "sinds": T0}


@proef
def test_herstel_sluit_de_nood(repo):
    repo.zet("b", T0)
    _, b = ronde(T0 + 15 * MIN)
    assert "Bouw loopt achter op de code: mijnagents" in noden(b)
    repo.bouw("mijnagents")
    _, b = ronde(T0 + 17 * MIN, Bord(open_noden=[{"tekst": "Bouw loopt achter op de code: mijnagents",
                                                  "wie": "claude-code"}]))
    assert b.eind()["nood"] == [] and b.eind().get("nood_sluiten") is not False
    assert b.eind()["status"] == "klaar"


@proef
def test_twee_diensten_in_storing_geven_twee_noden(repo):
    repo.zet("b", T0)
    repo.zet("e", T0 + MIN)
    _, b = ronde(T0 + 12 * MIN)
    assert noden(b) == {"Bouw loopt achter op de code: mijnagents": "claude-code",
                        "Bouw loopt achter op de code: agents": "claude-code"}


@proef
def test_een_dienst_die_niet_na_te_kijken_is_houdt_de_andere_niet_tegen(repo):
    oud = B.DIENSTEN
    B.DIENSTEN = ("weg", "mijnagents", "agents")
    try:
        repo.zet("b", T0)
        uit, b = ronde(T0 + 10 * MIN)
    finally:
        B.DIENSTEN = oud
    assert uit["weg"]["stand"] == "onbekend" and uit["agents"]["stand"] == "gelijk"
    assert noden(b) == {"Bouwwacht kan weg niet nakijken": "claude-code",
                        "Bouw loopt achter op de code: mijnagents": "claude-code"}


@proef
def test_de_ronde_leest_alleen_en_schrijft_alleen_haar_stand(repo):
    repo.zet("b", T0)
    voor = {p: open(p).read() for p in (os.path.join(repo.map, f"{d}-data", ".built") for d in B.DIENSTEN)}
    head, status = repo.git("rev-parse", "HEAD"), repo.git("status", "--porcelain")
    reflog = repo.git("reflog")
    gebruikt = []
    echt = B.subprocess.run

    def vang(cmd, *a, **k):
        gebruikt.append(cmd[3])
        return echt(cmd, *a, **k)

    B.subprocess.run = vang
    try:
        ronde(T0 + 12 * MIN)
    finally:
        B.subprocess.run = echt
    assert set(gebruikt) <= {"rev-parse", "log"}, gebruikt
    assert {p: open(p).read() for p in voor} == voor
    assert (repo.git("rev-parse", "HEAD"), repo.git("status", "--porcelain"), repo.git("reflog")) == (head, status, reflog)
    nieuw = {os.path.relpath(os.path.join(w, f), repo.map) for w, _, fs in os.walk(repo.map) if "/.git" not in w
             for f in fs} - {os.path.relpath(p, repo.map) for p in voor}
    assert {n for n in nieuw if not n.startswith("appportal/")} == {"mijnagents-data/bouwwacht.json"}, nieuw


@proef
def test_een_nieuwe_nood_staat_een_keer_in_het_werkverslag(repo):
    repo.zet("b", T0)
    _, b = ronde(T0 + 12 * MIN, Bord(open_noden=[]))
    assert [(r["onderwerp"], r["stap"]) for r in b.logregels()] == [("mijnagents", "fout")]
    _, b = ronde(T0 + 14 * MIN, Bord(open_noden=[{"tekst": "Bouw loopt achter op de code: mijnagents",
                                                  "wie": "claude-code"}]))
    assert b.logregels() == [] and "Bouw loopt achter op de code: mijnagents" in noden(b)
    _, b = ronde(T0 + 16 * MIN, Bord(open_noden=None))
    assert b.logregels() == [] and "Bouw loopt achter op de code: mijnagents" in noden(b)


@proef
def test_droog_stuurt_niets_en_schrijft_geen_stand(repo):
    repo.zet("b", T0)
    b = Bord()
    echt, bord.call = bord.call, b.call
    echte_tijd, B.time = B.time, types.SimpleNamespace(time=lambda: T0 + 12 * MIN)
    uit = io.StringIO()
    try:
        with redirect_stdout(uit):
            code = B.main(["--droog"])
    finally:
        bord.call, B.time = echt, echte_tijd
    assert b.gestuurd == [] and not os.path.exists(repo.stand)
    assert code == 1 and "mijnagents loopt achter" in uit.getvalue(), uit.getvalue()


@proef
def test_zonder_bord_staat_de_meting_in_het_cronlog(repo):
    repo.zet("b", T0)
    b = Bord(weg=True)
    echt, bord.call = bord.call, b.call
    echte_tijd, B.time = B.time, types.SimpleNamespace(time=lambda: T0 + 12 * MIN)
    fout = io.StringIO()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(fout):
            code = B.main([])
    finally:
        bord.call, B.time = echt, echte_tijd
    assert code == 1
    assert "ronde gestopt: Werkwijze niet gelezen: bord onbereikbaar" in fout.getvalue()
    assert "mijnagents loopt achter, 12 min" in fout.getvalue(), fout.getvalue()


@proef
def test_alleen_mijn_eigen_naam_op_het_bord(repo):
    repo.zet("b", T0)
    _, b = ronde(T0 + 12 * MIN)
    assert {p["naam"] for pad, p in b.gestuurd if pad == "/agent-status"} == {"bouwwacht"}


@proef
def test_zonder_grenzen_in_de_werkwijze_geen_werk_en_geen_bouwnood_gesloten(repo):
    repo.zet("b", T0)
    _, b = ronde(T0 + 12 * MIN, Bord(werkwijze="# Werkwijze\n\nIk kijk naar de bouw.",
                                     open_noden=[{"tekst": "Bouw loopt achter op de code: mijnagents", "wie": "claude-code"}]))
    assert noden(b) == {"Werkwijze zegt niet in de vaste vorm wat ik nooit doe of wat Mehdi beslist": "mehdi"}
    assert b.eind()["nood_sluiten"] is False, "niet gemeten, dus de open bouwnood blijft open (Codex-resultaattoets 2)"
    assert not os.path.exists(repo.stand)


@proef
def test_een_stand_die_niet_te_bewaren_is_houdt_de_bouwnood_niet_tegen(repo):
    with open(os.path.join(repo.map, "bestand"), "w") as f:
        f.write("geen map")
    B.STAND = os.path.join(repo.map, "bestand", "bouwwacht.json")
    repo.zet("b", T0)
    _, b = ronde(T0 + 20 * MIN)
    assert noden(b) == {"Bouw loopt achter op de code: mijnagents": "claude-code",
                        "Bouwwacht kan zijn stand niet bewaren": "claude-code"}
    assert "stand niet bewaard" in b.eind()["detail"] and b.eind().get("nood_sluiten") is not False


@proef
def test_zonder_reflog_en_zonder_bewaarbare_stand_telt_het_verschil_als_oud(repo):
    """Codex-resultaattoets 2.1: anders begint de klok elke ronde opnieuw en komt er nooit een bouwnood."""
    repo.git("config", "core.logAllRefUpdates", "false")
    shutil.rmtree(os.path.join(repo.repo, ".git", "logs"))
    with open(os.path.join(repo.map, "bestand"), "w") as f:
        f.write("geen map")
    B.STAND = os.path.join(repo.map, "bestand", "bouwwacht.json")
    repo.zet("b", T0)
    uit, b = ronde(T0 + MIN)
    assert uit["mijnagents"]["stand"] == "achter" and uit["mijnagents"]["minuten"] is None
    assert uit["agents"]["stand"] == "gelijk"
    assert noden(b) == {"Bouw loopt achter op de code: mijnagents": "claude-code",
                        "Bouwwacht kan zijn stand niet bewaren": "claude-code"}


def main_met(b, nu):
    echt, bord.call = bord.call, b.call
    echte_tijd, B.time = B.time, types.SimpleNamespace(time=lambda: nu)
    fout = io.StringIO()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(fout):
            code = B.main([])
    finally:
        bord.call, B.time = echt, echte_tijd
    return code, fout.getvalue()


@proef
def test_geen_slotbestand_geen_ronde_en_exit_1(repo):
    """Codex-resultaattoets 2.2: zonder slot draait er geen ronde die met een andere kan botsen."""
    with open(os.path.join(repo.map, "bestand"), "w") as f:
        f.write("geen map")
    B.STAND = os.path.join(repo.map, "bestand", "bouwwacht.json")
    repo.zet("b", T0)
    b = Bord()
    code, fout = main_met(b, T0 + 12 * MIN)
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
        code, fout = main_met(b, T0 + 12 * MIN)
    finally:
        B.fcntl = echt
    assert code == 1 and b.gestuurd == [] and "geen slot voor de ronde (OSError" in fout, fout


@proef
def test_een_onleesbare_markering_is_onbekend_geen_vals_alarm(repo):
    pad = os.path.join(repo.map, "mijnagents-data", ".built")
    os.remove(pad)
    os.makedirs(pad)
    uit, b = ronde(T0 + MIN)
    assert uit["mijnagents"]["stand"] == "onbekend" and "markering niet leesbaar" in uit["mijnagents"]["reden"]
    assert noden(b) == {"Bouwwacht kan mijnagents niet nakijken": "claude-code"}


@proef
def test_een_tweede_ronde_tegelijk_slaat_over(repo):
    repo.zet("b", T0)
    b = Bord()
    echt, bord.call = bord.call, b.call
    echte_tijd, B.time = B.time, types.SimpleNamespace(time=lambda: T0 + 12 * MIN)
    slot = B.neem_slot()
    fout = io.StringIO()
    try:
        assert slot
        with redirect_stdout(io.StringIO()), redirect_stderr(fout):
            code = B.main([])
        assert code == 0 and b.gestuurd == [] and "een vorige ronde loopt nog" in fout.getvalue()
        slot.close()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = B.main([])
        assert code == 0 and "Bouw loopt achter op de code: mijnagents" in noden(b)
    finally:
        slot.close()
        bord.call, B.time = echt, echte_tijd


@proef
def test_een_eindhartslag_die_niet_aankomt_geeft_exit_1(repo):
    repo.zet("b", T0)
    b = Bord(status_weg=True)
    echt, bord.call = bord.call, b.call
    echte_tijd, B.time = B.time, types.SimpleNamespace(time=lambda: T0 + 12 * MIN)
    fout = io.StringIO()
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(fout):
            code = B.main([])
    finally:
        bord.call, B.time = echt, echte_tijd
    assert code == 1
    assert "eindhartslag niet aangekomen" in fout.getvalue() and "mijnagents loopt achter, 12 min" in fout.getvalue()


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
