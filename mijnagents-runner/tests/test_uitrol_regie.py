"""Grendels op de uitrol van de regie (RZ4-07, herstelcontrole van Codex, 22-10-2026).

- (a) werkwijze_naar_bord.py --zet weigert voor De Bode, De Regisseur en De Zoomwacht: hun werkwijze gaat alleen als
  voorstel met het runbook werkwijze-bijwerken naar het bord, na een klik van Mehdi (ontwerp regie-zoom 13.5, vraag 6).
  Het verschil tonen zonder --zet blijft werken, en voor elke andere agent zet het zoals voordien.
- (b) mijnagents/deploy.sh schrijft de markering .built pas nadat een routetoets slaagt op de nieuw gestarte container:
  /gezondheid (leest de databank, schrijft niets) geeft ok true en de bordpagina / antwoordt, op 127.0.0.1:3022, met een
  time-out per aanroep en enkele pogingen. Faalt de toets, dan geen markering, een duidelijke logregel en een exit die
  niet nul is, zodat de volgende tik van de cron opnieuw bouwt en toetst. Het zetscript van de planning
  (planning/gesprekken_cron_zetten.py) wacht op die markering.

Geen netwerk en geen docker: het bord is nagebootst (bord.call); deploy.sh draait met /bin/sh en nagebootste git,
docker, curl, sleep en date vooraan in PATH, in een tijdelijke thuismap.
Draaien: python3 mijnagents-runner/tests/test_uitrol_regie.py
"""
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
REPO = os.path.dirname(RUNNER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import werkwijze_naar_bord as W  # noqa: E402

ZAAD = "# Werkwijze van de proef\n\n## Mandaat\n\nIk lees de proefbron.\n\n## Stappen\n\nEen nieuwe stap.\n"
OP_HET_BORD = "# Werkwijze van de proef\n\n## Mandaat\n\nIk lees de proefbron.\n\n## Stappen\n\nDe oude stap.\n"


def met_bord(doe, naam, op_het_bord=OP_HET_BORD):
    """Voert doe() uit met een nagebootst bord en een zaad in een tijdelijke map. Geeft (uitkomst, aanroepen, scherm)."""
    map_ = tempfile.mkdtemp(prefix="zaad-")
    pad = os.path.join(map_, f"{naam}.md")
    with open(pad, "w", encoding="utf-8") as f:
        f.write(ZAAD)
    aanroepen = []

    def call(route, payload=None, method=None):
        aanroepen.append((route, payload))
        if payload is None:
            return {"werkwijze": op_het_bord, "mandaat": "Ik lees de proefbron."}
        return {"ok": True}
    oud = (W.zaadpad, W.bord.call)
    W.zaadpad, W.bord.call = (lambda n: pad), call
    try:
        with redirect_stdout(io.StringIO()) as uit, redirect_stderr(io.StringIO()) as fout:
            uitkomst = doe()
    finally:
        W.zaadpad, W.bord.call = oud
    return uitkomst, aanroepen, uit.getvalue() + fout.getvalue()


def test_rz4_07a_zet_weigert_voor_de_regie_agents():
    """Tot RZ4-07 zette werkwijze_naar_bord.py --zet ook de werkwijze van De Bode, De Regisseur en De Zoomwacht
    rechtstreeks op het bord (zo kon BUNDELEN aan zonder de afgesproken voorstelklik). Nu weigeren zet() en --zet voor
    die drie, zonder schrijfactie; het verschil tonen blijft, en een andere agent gaat zoals voordien."""
    assert W.ALLEEN_VIA_VOORSTEL == frozenset({"bode", "regisseur", "zoom-wacht"}), W.ALLEEN_VIA_VOORSTEL
    for naam in sorted(W.ALLEEN_VIA_VOORSTEL):
        (ok, reden), aanroepen, _ = met_bord(lambda: W.zet(naam), naam)
        assert ok is False and "werkwijze-bijwerken" in reden and "klik van Mehdi" in reden, (naam, reden)
        assert aanroepen == [], f"{naam}: geen enkele aanroep naar het bord: {aanroepen}"
        code, aanroepen, scherm = met_bord(lambda: W.main([naam, "--zet"]), naam)
        assert code == 2 and "niet gezet" in scherm and "werkwijze-bijwerken" in scherm, (naam, code, scherm)
        assert "+Een nieuwe stap." in scherm, "het verschil staat er wel"
        assert all(payload is None for _, payload in aanroepen), f"{naam}: alleen lezen: {aanroepen}"
        code, aanroepen, scherm = met_bord(lambda: W.main([naam]), naam)
        assert code == 1 and "+Een nieuwe stap." in scherm and "Draai met --zet" not in scherm, (naam, code, scherm)
        assert "werkwijze-bijwerken" in scherm and all(payload is None for _, payload in aanroepen), (naam, scherm)
    (ok, reden), aanroepen, _ = met_bord(lambda: W.zet("ontwikkelaar"), "ontwikkelaar")
    assert ok is True and len(aanroepen) == 1, (ok, reden, aanroepen)
    route, payload = aanroepen[0]
    assert route == "/api/agent/ontwikkelaar/werkwijze" and payload["werkwijze"] == ZAAD and payload["overschrijf"] is True
    code, aanroepen, scherm = met_bord(lambda: W.main(["ontwikkelaar", "--zet"]), "ontwikkelaar")
    assert code == 0 and "ontwikkelaar: op het bord gezet." in scherm and aanroepen[-1][1]["werkwijze"] == ZAAD, scherm


def test_rz4_07a_voorstel_met_het_runbook_voor_de_regie_agents():
    """RZ4-07 en de uitrol van release 1 (22-10-2026): de voorstelroute had geen gereedschap; --zet weigert voor de drie
    regie-agents, en een voorstel met de volledige tekst moest met de hand op het bord. Nu zet --voorstel het zaad als
    voorstel met het runbook werkwijze-bijwerken op het bord, van De Regisseur, zoals zijn eigen tool voorstel. Het bord
    zelf verandert pas na de klik van Mehdi (de uitvoerder voert het runbook dan uit). Zijn zaad en bord al gelijk, dan
    komt er geen voorstel."""
    for naam in sorted(W.ALLEEN_VIA_VOORSTEL):
        code, aanroepen, scherm = met_bord(lambda: W.main([naam, "--voorstel"]), naam)
        assert code == 0 and "+Een nieuwe stap." in scherm and "wacht op de klik van Mehdi" in scherm, (naam, code, scherm)
        schrijven = [(route, payload) for route, payload in aanroepen if payload is not None]
        assert len(schrijven) == 1 and schrijven[0][0] == "/agent-status", (naam, schrijven)
        hartslag = schrijven[0][1]
        assert hartslag["naam"] == "regisseur" and hartslag["status"] == "waakt" and "nood" not in hartslag, hartslag
        v = hartslag["voorstel"]
        # het mandaat gaat mee, zoals bij --zet: anders bleef de kaarttekst oud en zag de controle na de klik een verschil
        assert v["runbook"] == "werkwijze-bijwerken" and v["parameters"] == {
            "agent": naam, "werkwijze": ZAAD, "mandaat": "Ik lees de proefbron."}, v
        assert naam in v["actie"], v
    # zaad en bord gelijk: geen voorstel, alleen gelezen
    code, aanroepen, scherm = met_bord(lambda: W.main(["bode", "--voorstel"]), "bode", op_het_bord=ZAAD)
    assert code == 0 and "al gelijk" in scherm and all(payload is None for _, payload in aanroepen), (scherm, aanroepen)
    # --zet en --voorstel samen gaat niet
    try:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            W.main(["bode", "--zet", "--voorstel"])
    except SystemExit as e:
        assert e.code == 2, e.code
    else:
        raise AssertionError("--zet en --voorstel samen werd aanvaard")


def test_rz4_07a_runbook_zet_ook_het_mandaat_van_het_voorstel():
    """Het runbook werkwijze-bijwerken zette alleen de tekst. Na de klik op een voorstel van --voorstel bleef zo de
    kaarttekst (het mandaat) oud, en zei werkwijze_naar_bord.py nog altijd dat zaad en bord verschillen. Nu zet het het
    mandaat mee als het voorstel het draagt; een voorstel zonder mandaat werkt zoals voordien."""
    import runbooks.werkwijze_bijwerken as WB  # noqa: PLC0415
    tekst = ZAAD + "".join(f"\nStap {i}: de proefbron lezen en niets veranderen.\n" for i in range(8))
    verstuurd = []

    class Antwoord:
        def read(self):
            return b'{"ok": true}'

    def urlopen(req, timeout=0):
        verstuurd.append((req.full_url, json.loads(req.data.decode())))
        return Antwoord()
    oud = (WB.urllib.request.urlopen, WB._token)
    WB.urllib.request.urlopen, WB._token = urlopen, lambda: "proef-token"
    try:
        WB.voer_uit({"agent": "bode", "werkwijze": tekst, "mandaat": "  Ik lees de proefbron.  "})
        WB.voer_uit({"agent": "bode", "werkwijze": tekst})
        WB.voer_uit({"agent": "bode", "werkwijze": tekst, "mandaat": "   "})
    finally:
        WB.urllib.request.urlopen, WB._token = oud
    assert [u for u, _ in verstuurd] == [f"{WB.PLATFORM}/api/agent/bode/werkwijze"] * 3, verstuurd
    assert verstuurd[0][1] == {"werkwijze": tekst.strip(), "overschrijf": True, "mandaat": "Ik lees de proefbron."}, verstuurd[0]
    assert verstuurd[1][1] == {"werkwijze": tekst.strip(), "overschrijf": True}, "zonder mandaat zoals voordien"
    assert verstuurd[2][1] == {"werkwijze": tekst.strip(), "overschrijf": True}, "een leeg mandaat gaat niet mee"


# ------------------------------------------------------------------------------------------------- deploy.sh ---
DEPLOY = os.path.join(REPO, "mijnagents", "deploy.sh")
NEP = {
    "git": '#!/bin/sh\necho "git $*" >> "$UITROL_SPOOR"\necho "${NEP_BOOM:-boom-nieuw}"\n',
    "docker": '#!/bin/sh\necho "docker $*" >> "$UITROL_SPOOR"\nexit "${NEP_DOCKER_EXIT:-0}"\n',
    "sleep": '#!/bin/sh\necho "sleep $*" >> "$UITROL_SPOOR"\n',
    "date": "#!/bin/sh\necho 2026-10-22T07:00:00+00:00\n",
    # NEP_CURL: ok, dicht (geen verbinding), traag (de eerste vier aanroepen geen verbinding), niet_ok (/gezondheid
    # zonder ok true), pagina_kapot (/ geeft een HTTP-fout, curl -f eindigt dan op 22)
    "curl": """#!/bin/sh
url=""
tijd=""
while [ $# -gt 0 ]; do
  case "$1" in
    --max-time) tijd="$2"; shift 2 ;;
    http*) url="$1"; shift ;;
    *) shift ;;
  esac
done
echo "curl $url max-time=$tijd" >> "$UITROL_SPOOR"
teller="$UITROL_MAP/curl-teller"
n=$(cat "$teller" 2>/dev/null || echo 0)
n=$((n + 1))
echo "$n" > "$teller"
if [ "$NEP_CURL" = dicht ]; then exit 7; fi
if [ "$NEP_CURL" = traag ] && [ "$n" -le 4 ]; then exit 7; fi
case "$url" in
  */gezondheid)
    if [ "$NEP_CURL" = niet_ok ]; then echo '{"ok":false}'; else echo '{"agents":3,"app":"Proefbord","ok":true}'; fi ;;
  */)
    if [ "$NEP_CURL" = pagina_kapot ]; then exit 22; fi
    echo "<html>bord</html>" ;;
esac
exit 0
""",
}


class Uitrol:
    """Een tijdelijke thuismap met appportal/ en nagebootste opdrachten; draai() voert de echte deploy.sh uit."""

    def __init__(self, gebouwd=None):
        self.map = tempfile.mkdtemp(prefix="uitrol-")
        self.thuis = os.path.join(self.map, "thuis")
        os.makedirs(os.path.join(self.thuis, "appportal", "mijnagents-data"))
        self.bin = os.path.join(self.map, "bin")
        os.makedirs(self.bin)
        for naam, tekst in NEP.items():
            pad = os.path.join(self.bin, naam)
            with open(pad, "w", encoding="utf-8") as f:
                f.write(tekst)
            os.chmod(pad, 0o755)
        self.mark = os.path.join(self.thuis, "appportal", "mijnagents-data", ".built")
        if gebouwd is not None:
            with open(self.mark, "w", encoding="utf-8") as f:
                f.write(gebouwd + "\n")
        self.spoor = os.path.join(self.map, "spoor.txt")

    def draai(self, curl="ok", docker_exit=0):
        if os.path.exists(self.spoor):
            os.remove(self.spoor)
        teller = os.path.join(self.map, "curl-teller")
        if os.path.exists(teller):
            os.remove(teller)
        env = {"HOME": self.thuis, "PATH": self.bin + os.pathsep + "/usr/bin:/bin", "UITROL_SPOOR": self.spoor,
               "UITROL_MAP": self.map, "NEP_CURL": curl, "NEP_DOCKER_EXIT": str(docker_exit)}
        r = subprocess.run(["/bin/sh", DEPLOY], capture_output=True, text=True, timeout=60, env=env)
        spoor = open(self.spoor, encoding="utf-8").read().splitlines() if os.path.exists(self.spoor) else []
        return r.returncode, r.stdout + r.stderr, spoor

    def gebouwd(self):
        return open(self.mark, encoding="utf-8").read().strip() if os.path.exists(self.mark) else None


def test_rz4_07b_markering_pas_na_een_geslaagde_routetoets():
    """Tot RZ4-07 schreef deploy.sh .built meteen na 'docker compose up', zonder te weten of het bord werkte. Een
    container die niet opstartte, of een bordpagina die faalde, gold zo als gebouwd: de cron probeerde niet opnieuw, en
    het zetscript van de planning zette de nieuwe planning toch. Nu komt de markering pas na een geslaagde routetoets."""
    u = Uitrol(gebouwd="boom-oud")
    code, log, spoor = u.draai("ok")
    assert code == 0 and u.gebouwd() == "boom-nieuw", (code, log, spoor)
    assert spoor == ["git rev-parse HEAD:mijnagents", "docker compose up -d --build app-mijnagents",
                     "curl http://127.0.0.1:3022/gezondheid max-time=5", "curl http://127.0.0.1:3022/ max-time=5"], spoor
    assert "mijnagents deployed (boom-nieuw)" in log, log


def test_rz4_07b_geen_markering_als_de_routetoets_faalt():
    for curl, reden in (("dicht", "de container antwoordt niet"), ("niet_ok", "/gezondheid zonder ok true"),
                        ("pagina_kapot", "de bordpagina geeft een fout")):
        u = Uitrol(gebouwd="boom-oud")
        code, log, spoor = u.draai(curl)
        assert code != 0, (reden, code, log)
        assert u.gebouwd() == "boom-oud", f"{reden}: de markering blijft de vorige boom"
        assert "NIET als gebouwd gemarkeerd" in log and "routetoets" in log and "127.0.0.1:3022" in log, (reden, log)
        assert "na 6 pogingen" in log and "volgende tik" in log and "deployed" not in log, (reden, log)
        assert spoor.count("curl http://127.0.0.1:3022/gezondheid max-time=5") == 6, (reden, spoor)
        assert spoor.count("sleep 5") == 5 and spoor.count("docker compose up -d --build app-mijnagents") == 1, (reden, spoor)
    # de volgende tik bouwt en toetst opnieuw; nu werkt het bord
    code, log, spoor = u.draai("ok")
    assert code == 0 and u.gebouwd() == "boom-nieuw" and "docker compose up -d --build app-mijnagents" in spoor, (code, log)


def test_rz4_07b_een_trage_start_krijgt_enkele_pogingen():
    u = Uitrol()
    code, log, spoor = u.draai("traag")
    assert code == 0 and u.gebouwd() == "boom-nieuw", (code, log, spoor)
    assert spoor.count("sleep 5") == 4 and spoor.count("curl http://127.0.0.1:3022/gezondheid max-time=5") == 5, spoor


def test_rz4_07b_het_bestaande_gedrag_blijft():
    """Ongewijzigde boom: niets bouwen en niets toetsen. Faalt de build zelf, dan stopt het script zoals voordien (set -e),
    zonder markering en zonder toets."""
    u = Uitrol(gebouwd="boom-nieuw")
    code, log, spoor = u.draai("ok")
    assert code == 0 and spoor == ["git rev-parse HEAD:mijnagents"] and u.gebouwd() == "boom-nieuw", (code, log, spoor)
    u = Uitrol(gebouwd="boom-oud")
    code, log, spoor = u.draai("ok", docker_exit=1)
    assert code != 0 and u.gebouwd() == "boom-oud" and not [r for r in spoor if r.startswith("curl")], (code, log, spoor)


def test_rz4_07b_bron():
    """De poort van de toets is die van de container (docker-compose.override.yml), het script houdt zijn execute-bit,
    en er staat geen gedachtestreepje in."""
    assert os.stat(DEPLOY).st_mode & stat.S_IXUSR, "deploy.sh houdt zijn execute-bit"
    modus = subprocess.run(["git", "-C", REPO, "ls-files", "-s", "mijnagents/deploy.sh"], capture_output=True, text=True).stdout
    assert modus.startswith("100755 "), modus
    compose = open(os.path.join(REPO, "docker-compose.override.yml"), encoding="utf-8").read()
    assert '"127.0.0.1:3022:3022"' in compose, "de container luistert op 127.0.0.1:3022"
    bron = open(DEPLOY, encoding="utf-8").read()
    assert "http://127.0.0.1:3022" in bron and "--max-time" in bron
    assert "\N{EM DASH}" not in bron and "\N{EN DASH}" not in bron


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
