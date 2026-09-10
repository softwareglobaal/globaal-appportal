"""Gedeelde bord-client voor de runners van Mehdi Agents: hartslag, werkverslag,
klaarzetten en lezen wat klaargezet is. Token uit mijnagents-data/.env."""
import json
import os
import sys
import urllib.parse
import urllib.request

PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3022")


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

    def klaarzet(self, items):
        """items: lijst van dicts met voor, soort, titel, en optioneel sleutel, inhoud, verwijzing, uniek."""
        for it in items:
            it.setdefault("van", self.naam)
        return call("/api/klaarzet", {"items": items}) if items else {"nieuw": 0, "bestaand": 0}


def klaargezet_voor(voor, sleutel=None, afdeling=None, status="klaar", n=100):
    q = {"voor": voor, "status": status, "n": n}
    if sleutel:
        q["sleutel"] = sleutel
    if afdeling:
        q["afdeling"] = afdeling
    return call("/api/klaarzet?" + urllib.parse.urlencode(q)).get("items", [])


def opgepakt(kid, door):
    return call(f"/api/klaarzet/{kid}/opgepakt", {"door": door})
