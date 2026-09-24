"""Gedeelde bord-client voor de runners van Mehdi Agents: hartslag, werkverslag,
klaarzetten en lezen wat klaargezet is. Token uit mijnagents-data/.env."""
import hashlib
import json
import os
import re
import sys
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


class Agent:
    def __init__(self, naam):
        self.naam = naam
        self._log = []

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
            call("/agent-status", p)
        except Exception as e:  # noqa: BLE001
            print("hartslag mislukt:", e, file=sys.stderr)

    def log(self, onderwerp, stap, tekst, detail=""):
        self._log.append({"naam": self.naam, "onderwerp": onderwerp, "stap": stap, "tekst": tekst,
                          "detail": detail if isinstance(detail, str) else json.dumps(detail, ensure_ascii=False, indent=1)})
        print(f"  [{stap}] {tekst}")

    def log_verstuur(self):
        if not self._log:
            return
        try:
            call("/api/logboek", {"regels": self._log})
        except Exception as e:  # noqa: BLE001
            print("logboek mislukt:", e, file=sys.stderr)
        self._log = []

    def werkwijze(self):
        try:
            return call(f"/api/agent/{self.naam}/werkwijze").get("werkwijze") or ""
        except Exception:  # noqa: BLE001
            return ""

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
        return call("/api/klaarzet", {"items": items}) if items else {"nieuw": 0, "bestaand": 0}

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

    def __enter__(self):
        self.agent.hartslag("actief", taak=self.taak)
        self.werkwijze = self.agent.werkwijze()
        if self.werkwijze:
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
        return self

    def __exit__(self, soort, fout, spoor):
        self.agent.kennis(self._kennis(), bron=", ".join(self._bronnen) or "geen")
        self.agent.log_verstuur()
        if fout is not None:
            # N11: nooit blijven hangen op "actief". Een ronde die breekt meldt dat.
            self.agent.hartslag("fout", taak=self.taak,
                                detail=f"{type(fout).__name__}: {str(fout)[:180]}", nood=self._noden)
            return False
        self.agent.hartslag("klaar" if not self._noden else "waakt",
                            taak=self.taak, detail=self.detail, nood=self._noden)
        return False


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
