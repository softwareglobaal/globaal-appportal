"""Gedeelde bord-client voor de runners van Mehdi Agents: hartslag, werkverslag,
klaarzetten en lezen wat klaargezet is. Token uit mijnagents-data/.env."""
import hashlib
import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# Eigen variabele, bewust niet PLATFORM_URL: die staat ook in het .env van de
# Siyan-tegel (poort 3021) dat koppelingen/pipedrive.py inleest, en dan
# kwam elke klaarzet-aanroep op het verkeerde bord uit (404, 9 tot 15-9).
PLATFORM = os.environ.get("MIJNAGENTS_URL", "http://127.0.0.1:3022")


def token():
    try:
        for regel in open(os.path.expanduser("~/appportal/mijnagents-data/.env")):
            if regel.startswith("AGENTS_TOKEN="):
                return regel.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return os.environ.get("AGENTS_TOKEN", "")


TOKEN = token()


def call(pad, payload=None, method=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"{PLATFORM}{pad}", data=data, method=method or ("POST" if data else "GET"),
                                 headers={"Content-Type": "application/json", "X-Agents-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


class RondeGestopt(RuntimeError):
    """De ronde stopte voor het werk begon, omdat de agent zijn regelboek niet heeft (Codex NA09, 16-10-2026)."""


class WerkwijzeOnbekend(RondeGestopt):
    """De werkwijze kon niet gelezen worden. Onbekend is niet leeg: wie zijn regelboek niet kon lezen,
    werkt niet alsof er geen regels zijn. `soort` zegt waarom, zonder getal erin (N10)."""

    def __init__(self, soort, reden=""):
        self.soort = soort
        self.reden = reden
        super().__init__(f"{soort} ({reden})" if reden else soort)


def sectie(tekst, kop):
    """De tekst onder de eerste kop die `kop` bevat (hoofdletters tellen niet), tot de volgende kop van
    hetzelfde of een hoger niveau. Leeg als die kop er niet is. Zo leest een agent een deel van zijn
    werkwijze, bijvoorbeeld sectie(r.werkwijze, "nooit"), in plaats van een kopie in zijn code te houden."""
    niveau, regels = None, []
    for regel in (tekst or "").splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", regel)
        if niveau is None:
            if m and kop.lower() in m.group(2).lower():
                niveau = len(m.group(1))
            continue
        if m and len(m.group(1)) <= niveau:
            break
        regels.append(regel)
    return "\n".join(regels).strip()


def punten(tekst):
    """De opsommingspunten uit een stuk werkwijze ("- ...", "* ..." of "1. ..."), zonder het teken ervoor."""
    return [m.group(1).strip() for m in re.finditer(r"^\s*(?:[-*]|\d+[.)])\s+(.+)$", tekst or "", re.M)]


def grenzen(werkwijze):
    """Norm N2 als regels: de punten onder de kop over wat de agent nooit doet en onder de kop over wat
    Mehdi beslist. De generator eist ze voor hij registreert, het sjabloon past ze elke ronde toe."""
    return punten(sectie(werkwijze, "nooit")), punten(sectie(werkwijze, "beslist"))


class Agent:
    def __init__(self, naam):
        self.naam = naam
        self._log = []
        self._prive = set()
        self._prive_re = None

    # Privacygrens (nacontrole v1.3, R1): een agent meldt de teksten uit een privébron aan (privé-agenda, Lara,
    # Hotmail). Elk bericht naar het bord (hartslag, nood, logboek, klaargezet) gaat door maskeer(), welke route ook.
    PRIVE_NIET = {"mehdi", "mehdi:", "vandaag", "gisteren"}

    def prive(self, teksten):
        nieuw = {t.strip() for t in teksten if isinstance(t, str) and len(t.strip()) >= 4
                 and t.strip().lower() not in self.PRIVE_NIET} - self._prive
        if nieuw:
            self._prive |= nieuw
            self._prive_re = re.compile("|".join(re.escape(t) for t in sorted(self._prive, key=len, reverse=True)), re.I)

    def maskeer(self, obj):
        if self._prive_re is None:
            return obj
        if isinstance(obj, str):
            return self._prive_re.sub("(privé)", obj)
        if isinstance(obj, list):
            return [self.maskeer(x) for x in obj]
        if isinstance(obj, dict):
            return {k: self.maskeer(v) for k, v in obj.items()}
        return obj

    def hartslag(self, status, taak="", detail="", voorstel=None, nood=None):
        """nood: de volledige lijst van wat de agent nodig heeft of wat bij hem niet
        werkt, elk {"tekst": ..., "wie": "mehdi|claude-code|collega"}; wat er niet
        meer in staat, is voor het bord opgelost."""
        p = {"naam": self.naam, "status": status, "taak": taak, "detail": detail}
        if voorstel:
            p["voorstel"] = voorstel
        if nood is not None:
            p["nood"] = nood
        try:
            call("/agent-status", self.maskeer(p))
        except Exception as e:  # noqa: BLE001
            print("hartslag mislukt:", e, file=sys.stderr)

    def log(self, onderwerp, stap, tekst, detail=""):
        self._log.append({"naam": self.naam, "onderwerp": onderwerp, "stap": stap, "tekst": tekst,
                          "detail": detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, indent=1)})
        # ook de schermregel door het masker: die komt in de cron-logboeken (Codex A25, 15-10-2026)
        print(self.maskeer(f"  [{stap}] {tekst}"))

    def log_verstuur(self):
        if not self._log:
            return
        try:
            call("/api/logboek", {"regels": self.maskeer(self._log)})
        except Exception as e:  # noqa: BLE001
            print("logboek mislukt:", e, file=sys.stderr)
        self._log = []

    def werkwijze_lezen(self):
        """De werkwijze zoals ze nu op het bord staat. Een lege tekst is een antwoord en komt terug;
        kon het bord niet antwoorden, dan WerkwijzeOnbekend, nooit een lege tekst (NA09)."""
        try:
            antwoord = call(f"/api/agent/{self.naam}/werkwijze")
        except urllib.error.HTTPError as e:
            soort = {403: "geen toegang tot het bord", 404: "agent staat niet op het bord"}.get(e.code, "bordfout")
            raise WerkwijzeOnbekend(soort, f"HTTP {e.code}") from e
        except (OSError, http.client.HTTPException) as e:
            raise WerkwijzeOnbekend("bord onbereikbaar", type(e).__name__) from e
        except ValueError as e:
            raise WerkwijzeOnbekend("onleesbaar antwoord van het bord", type(e).__name__) from e
        tekst = antwoord.get("werkwijze") if isinstance(antwoord, dict) else None
        if not isinstance(tekst, str):
            raise WerkwijzeOnbekend("onleesbaar antwoord van het bord", "geen werkwijze in het antwoord")
        return tekst

    def werkwijze(self):
        """Verouderd, alleen nog voor de runners van voor de ronde (agenda-wacht, archivaris, fathom-wacht,
        levenscoach): geeft "" als het bord niet antwoordt, zodat zij blijven draaien zoals voorheen. Dat
        onderscheidt onbekend niet van leeg; het cron-logboek zegt het wel. Nieuwe code gaat door de ronde."""
        try:
            return self.werkwijze_lezen()
        except WerkwijzeOnbekend as e:
            print(f"werkwijze niet gelezen ({e}); verouderde aanroep werkt verder zonder regelboek", file=sys.stderr)
            return ""

    def open_noden(self):
        """Mijn noden die nu open staan op het bord, of None als dat onbekend is."""
        try:
            rijen = call("/api/nood").get("nood")
        except Exception:  # noqa: BLE001
            return None
        if not isinstance(rijen, list):
            return None
        return [{"tekst": r["tekst"], "wie": r.get("wie") or "mehdi"}
                for r in rijen if isinstance(r, dict) and r.get("naam") == self.naam and r.get("tekst")]

    def kennis(self, tekst, bron=""):
        """Norm N4: melden welk regelboek ik deze ronde las, zodat achteraf te zien is
        welke versie van de regels ik gebruikte toen ik iets deed."""
        try:
            call(f"/api/agent/{self.naam}/kennis", {"kennis": tekst, "bron": bron})
        except Exception as e:  # noqa: BLE001
            print("kennis niet gemeld:", e, file=sys.stderr)

    def klaarzet(self, items):
        """items: lijst van dicts met voor, soort, titel, en optioneel sleutel, inhoud, verwijzing, uniek."""
        for it in items:
            it.setdefault("van", self.naam)
        return call("/api/klaarzet", {"items": self.maskeer(items)}) if items else {"nieuw": 0, "bestaand": 0}

    def ronde(self, taak="ronde", bronnen=None):
        """De standaarddoorgang van een ronde. Zie AGENTNORM.md.

        Wie hiermee werkt haalt vanzelf N4 (melden welk regelboek je las), N11
        (nooit blijven hangen op actief) en N10 (een nood zonder teller):

            with ag.ronde("agenda in het oog") as r:
                regels = r.werkwijze          # de tekst zoals ze nu op het bord staat
                r.bron("agenda-taken.json", open(pad).read())
                ...
                r.nood("Buitenafspraken zonder adres", wie="mehdi")
                r.detail = f"{n} afspraken bekeken"

        bronnen: extra regelboeken als {naam: inhoud}, bovenop de werkwijze.

        Is de werkwijze op het bord onbekend of leeg, dan stopt de ronde voor het werk begint:
        een nood, hartslag "fout" en RondeGestopt (NA09). Zonder regelboek werkt geen agent.
        """
        return Ronde(self, taak, bronnen or {})


class Ronde:
    """Eén ronde van een agent, van hartslag tot hartslag."""

    def __init__(self, agent, taak, bronnen):
        self.agent = agent
        self.taak = taak
        self.detail = ""
        self.werkwijze = ""
        self._bronnen = dict(bronnen)
        self._noden = []

    def bron(self, naam, inhoud):
        """Een regelboek dat ik deze ronde gelezen heb. Gaat mee als kennis."""
        self._bronnen[naam] = inhoud if isinstance(inhoud, str) else json.dumps(inhoud, ensure_ascii=False)

    def nood(self, tekst, wie="mehdi"):
        """Wat ik nodig heb of wat bij mij niet werkt.

        Norm N10: geen aantal vooraan in de tekst. Noden zijn declaratief, dus met
        een teller erin ("11 afspraken zonder code") is elke ronde formeel een
        nieuwe nood en sluit de lus nooit. Het aantal hoort in het detail.
        """
        schoon = tekst.strip()
        if re.match(r"^\d+\s", schoon):
            schoon = re.sub(r"^\d+\s+", "", schoon)
            schoon = schoon[:1].upper() + schoon[1:]
            print(f"  [norm N10] aantal uit de noodtekst gehaald: {tekst[:50]}", file=sys.stderr)
        if not any(n["tekst"] == schoon for n in self._noden):
            self._noden.append({"tekst": schoon, "wie": wie})

    def _kennis(self):
        """Wat ik las, met een vingerafdruk per bron, zodat achteraf te zien is
        welke versie van de regels gold toen ik iets deed."""
        return "\n".join(
            f"{naam}: {len(inhoud or '')} tekens, {hashlib.sha256((inhoud or '').encode()).hexdigest()[:8]}"
            for naam, inhoud in self._bronnen.items())

    def _noden_naar_bord(self):
        """De noden voor een ronde die niet afliep. Wat al open stond blijft open, want of het intussen
        opgelost is, weet deze ronde niet; is ook dat onbekend, dan geen lijst, zodat het bord niets sluit."""
        bestaand = self.agent.open_noden()
        if bestaand is None:
            return None
        teksten = {n["tekst"] for n in bestaand}
        return bestaand + [n for n in self._noden if n["tekst"] not in teksten]

    def _stop(self, tekst, wie, oorzaak):
        """NA09: zonder regelboek geen ronde. Een nood met een eigenaar, hartslag op fout zodat N11 en de
        Normwacht het zien, en stoppen voor het werk begint. Geen kennis: er is niets gelezen."""
        self.nood(tekst, wie=wie)
        self.agent.log_verstuur()
        self.agent.hartslag("fout", taak=self.taak, detail=f"{tekst}; ronde gestopt voor het werk",
                            nood=self._noden_naar_bord())
        raise RondeGestopt(tekst) from oorzaak

    def __enter__(self):
        self.agent.hartslag("actief", taak=self.taak)
        # NA09 (Codex, 16-10-2026): tot dan gaf een leesfout een lege werkwijze en werkte de agent gewoon
        # door zonder regelboek, zonder dat iemand het zag. Onbekend is niet leeg, en leeg is geen regelboek.
        try:
            self.werkwijze = self.agent.werkwijze_lezen()
        except WerkwijzeOnbekend as e:
            self._stop(f"Werkwijze niet gelezen: {e.soort}", "claude-code", e)
        if not self.werkwijze.strip():
            self._stop("Werkwijze leeg op het bord", "mehdi", None)
        self._bronnen.setdefault("werkwijze op het bord", self.werkwijze)
        # Norm N13: wat een agent leert, leest elke agent. De gedeelde lessen gaan elke
        # ronde mee als bron, zodat ze in de kennis staan en een taalmodel ze in zijn
        # opdracht krijgt. Ontbreekt het bestand, dan breekt de ronde niet: dat meldt de
        # Normwacht. Mandaat van Mehdi, 24-09-2026.
        self.lessen = []
        try:
            pad = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "werkwijze", "lessen.json")
            with open(pad, encoding="utf-8") as f:
                tekst = f.read()
            self.lessen = json.loads(tekst).get("lessen", [])
            self._bronnen.setdefault("gedeelde lessen", tekst)
        except (OSError, ValueError):
            pass
        # Norm N14: een agent kent zijn collega's. Mehdi, 25-09-2026: "zorg ervoor dat alle
        # agents van elkaar op de hoogte zijn". De lijst komt elke ronde levend van het bord
        # (de waarheid, N6), nooit uit een kopie: wie er morgen bijkomt, kent iedereen meteen.
        self.collegas = collegas(zonder=self.agent.naam)
        if self.collegas:
            self._bronnen.setdefault("collega's op het bord", collega_tekst(self.collegas))
        return self

    def __exit__(self, soort, fout, spoor):
        self.agent.kennis(self._kennis(), bron=", ".join(self._bronnen) or "geen")
        self.agent.log_verstuur()
        if fout is not None:
            # N11: nooit blijven hangen op "actief". Een ronde die breekt meldt dat, en sluit geen noden
            # die ze niet meer kon nakijken.
            self.agent.hartslag("fout", taak=self.taak,
                                detail=f"{type(fout).__name__}: {str(fout)[:180]}", nood=self._noden_naar_bord())
            return False
        self.agent.hartslag("klaar" if not self._noden else "waakt",
                            taak=self.taak, detail=self.detail, nood=self._noden)
        return False


def collegas(zonder=None):
    """De actieve agents zoals ze nu op het bord staan: naam, label, afdeling, rol, cadans.
    Leeg als het bord niet antwoordt; de ronde breekt daar niet op, de Normwacht meldt het (N14)."""
    try:
        rijen = call("/api/agents")
    except Exception:  # noqa: BLE001
        return []
    if not isinstance(rijen, list):
        return []
    rijen = [r for r in rijen if isinstance(r, dict) and r.get("naam")]
    return sorted(({"naam": r["naam"], "label": r.get("label") or r["naam"], "afdeling": r.get("type") or "",
                    "rol": r.get("rol") or "", "cadans": r.get("cadans") or ""}
                   for r in rijen if r.get("actief") and r.get("naam") != zonder),
                  key=lambda c: (c["afdeling"], c["naam"]))


def collega_tekst(lijst):
    """Een regel per collega, voor de kennis van de ronde en voor de opdracht van een taalmodel-agent:
    wie bestaat er, waarvoor, en bij wie hoort een vraag die niet de mijne is."""
    regels = ["Mijn collega's op het bord. Hoort iets bij een van hen, dan zet ik het voor die agent klaar "
              "(klaarzet, voor: <naam>) in plaats van het zelf te doen. Mehdi bereik ik via De Bode (signaal)."]
    for c in lijst:
        regels.append(f"- {c['label']} ({c['naam']}, {c['afdeling']}): {c['rol'][:160]}")
    return "\n".join(regels)


def klaargezet_voor(voor, sleutel=None, afdeling=None, status="klaar", n=100):
    q = {"status": status, "n": n}
    if voor:
        q["voor"] = voor
    if sleutel:
        q["sleutel"] = sleutel
    if afdeling:
        q["afdeling"] = afdeling
    return call("/api/klaarzet?" + urllib.parse.urlencode(q)).get("items", [])


def opgepakt(kid, door):
    return call(f"/api/klaarzet/{kid}/opgepakt", {"door": door})
