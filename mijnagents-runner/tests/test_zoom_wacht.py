"""Grendels op De Zoomwacht (ontwerp regie-zoom v1.2: Z1 tot Z9 en Z16, met 13.2 en 13.5).

Gemeten op 21-10-2026: De Zoomwacht zag de vaste vergaderruimte niet (1 van de 16 gesprekken van 20-10), zijn dagregel
bevroor bij het oppakken, de gesprekkentabel telde elk gesprek met Fathom twee keer, en geen enkele test raakte
zoom_wacht.py. Deze test legt vast wat het ontwerp belooft, met de T-nummers van hoofdstuk 6 en 13.5: T05 tot T30,
T95, T96, T101, T102, T104, T106 en de K5-regressie bij T23. Daarna de bevindingen van de tegenlezing (ZOO-01 tot
ZOO-10, 21-10-2026), van de bouwcontrole (RZ2-05, met EIGEN-1 tot EIGEN-3 uit 13.6, 22-10-2026) en van de
herstelcontrole (RZ3-04, 22-10-2026: het Zoom-transcript geweigerd tot Mehdi beslist) en van de tweede herstelcontrole
(RZ4-02, 22-10-2026: de leesapp schrijft pas na de eigenaarscontrole, De Zoomwacht schrijft niets met een vreemde
gebruiker): elk eerst als falende test op de code van toen, dan hersteld in de bron.

Geen netwerk en geen sleutels. Nagebootst: de Zoom-API op het laagste niveau (zoom._vraag en het token), de Fathom-API,
een tijdelijk Fathom-archief en een tijdelijke zoom-data, en de klok (zoom_wacht.nu). Het bord is het echte bord
(mijnagents/app.py via de Flask-testclient, op een tijdelijke databank uit init_db), en bord.db_lees leest dezelfde
databank: zo gelden de echte regels van klaarzet, revisie en koppelen. Zonder Flask slaan die toetsen lokaal over; in
de CI is Flask er altijd (regie-grendels.yml, job runners).
Draaien: python3 mijnagents-runner/tests/test_zoom_wacht.py
"""
import importlib.util
import io
import itertools
import json
import os
import re
import signal
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
REPO = os.path.dirname(RUNNER)
MAP = tempfile.mkdtemp(prefix="zoom-wacht-")
# Een eigen thuismap: geen enkel echt .env-bestand wordt gelezen (bord, Fathom, Zoom).
os.environ["HOME"] = os.path.join(MAP, "thuis")
os.makedirs(os.environ["HOME"], exist_ok=True)
os.environ["AGENTS_TOKEN"] = "proef"
os.environ["AGENTS_DB"] = os.path.join(MAP, "start.db")
for _k in [k for k in os.environ if k.startswith("ZOOM_") or k.startswith("FATHOM_")]:
    del os.environ[_k]
# Mehdi's eigen Fathom-account in de proef: verzonnen adressen via de omgeving, nooit de echte standaard uit
# koppelingen/fathom.py (die staat alleen in de code, en de proef toetst ze zonder ze te noemen).
EIGEN_ADRES, WERK_ADRES, ANDER_ADRES = "eigen@mehdi.test", "mch@kantoor.test", "ander@shaniel.test"
os.environ["FATHOM_MEHDI_ADRESSEN"] = f"{EIGEN_ADRES},{WERK_ADRES}"
sys.path.insert(0, HIER)
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord  # noqa: E402
import zoom as Z  # noqa: E402
import zoom_wacht as ZW  # noqa: E402

try:
    sys.path.insert(0, os.path.join(REPO, "mijnagents"))
    import app as A  # noqa: E402
    C = A.app.test_client()
except ImportError:
    A = C = None
    assert not os.environ.get("CI"), "Flask ontbreekt in de CI: deze toetsen horen op het echte bord te draaien"

K = {"X-Agents-Token": "proef"}
TELLER = itertools.count(1)
UTC = timezone.utc
ZOOM_DT = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"   # de vorm die de chat-API van Zoom in from en to leest
PMI = "9100000001"
IK = {"id": "mehdi-id", "email": "info@h-invest.test", "pmi": PMI}
ZAAD = open(os.path.join(RUNNER, "werkwijze", "zoom-wacht.md"), encoding="utf-8").read()
# De proeven geven De Zoomwacht het zaad met een verzonnen teamdomein erbij (kantoor.test): zo heeft een teamgenoot een
# proefadres en geen echt adres op een echt teamdomein. test_t25_bron_en_zaad toetst het zaad zelf.
TEAMDOMEIN = "kantoor.test"
WERKWIJZE = re.sub(r"^(Teamdomeinen[^:\n]*:\s*)", rf"\g<1>{TEAMDOMEIN}, ", ZAAD, count=1, flags=re.M)
assert WERKWIJZE != ZAAD, "het zaad heeft geen regel Teamdomeinen meer"
FATHOM_WW = f"""# Werkwijze van De Fathomwacht

## Betrokken personen (proef)

| Naam | E-mail | Afdeling | Rol | Bijzonder |
|---|---|---|---|---|
| Mehdi Chegini | {WERK_ADRES} | alle | eigenaar | |
| Jan Proef | jan.proef@klant.test | h-architects (sales) | klant | |
| Collega Proef | collega.proef@{TEAMDOMEIN} | h-architects (sales) | collega | |
"""
# Deelnemers zoals Zoom ze geeft (/past_meetings/<uuid>/participants).
MEHDI_D = {"id": "mehdi-id", "name": "Mehdi Chegini", "user_email": "info@h-invest.test"}
TEAM_ADRES = f"ypsilon@{TEAMDOMEIN}"
TEAM_D = {"id": "", "name": "Proefpersoon Ypsilon", "user_email": TEAM_ADRES}
BEKEND_D = {"id": "", "name": "Jan Proef", "user_email": "jan.proef@klant.test"}
NAAMGENOOT_D = {"id": "", "name": "Jan Proef", "user_email": "jan@vreemd.test"}
ZONDER_EMAIL_D = {"id": "", "name": "Kees Zonderadres", "user_email": ""}
BOT_D = {"id": "", "name": "Fathom Notetaker", "user_email": ""}
VTT = """WEBVTT

1
00:00:01.000 --> 00:00:04.500
Mehdi Chegini: Goedemorgen, dit is een proefzin.

2
00:01:02.250 --> 00:01:05.000
Proefpersoon Ypsilon: Herkenbare zin uit het vangnet.
"""
VERBODEN = re.compile(r"download_url|play_url|share_url|passcode|pwd=|access_token|/rec/|https://[^\s\"']*zoom\.us", re.I)


def iso(t):
    return t.astimezone(UTC).isoformat().replace("+00:00", "Z")


def bxl(s):
    """Een Brusselse tijd ('2026-10-20 10:00') als UTC."""
    return datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=ZW.BE).astimezone(UTC)


# ------------------------------------------------------------------------------------------ nabootsingen ---
class NepZoom:
    """De Zoom-API op het laagste niveau: zoom._vraag en het token. Alles in zoom.py (lees, lees_alles, opnames,
    download, de grendels) draait echt."""

    def __init__(self, ik=IK):
        self.ik = dict(ik)
        self.sessies, self.opnames, self.downloads, self.meetings = [], {}, {}, {}
        self.geen_recht, self.fout = {}, set()
        self.chat = []                      # (sessie, berichten) zoals de chat-API ze geeft
        self.laatste = None
        self.token_fout = False
        self.lees_token_fout = False        # alleen de leesapp geeft geen token (een foute sleutel, ZOO-10)
        self.gevraagd = []

    def toegang(self, profiel="stack"):
        if self.token_fout or (profiel == "lees" and self.lees_token_fout):
            raise Z.ZoomFout("geen token (HTTP 401)")
        return "proef-token"

    def sessie(self, uuid, start, minuten, nummer=PMI, onderwerp="", deelnemers=None, rapport=("past",), einde=True, host=None,
               instantie=None, gepland=None):
        s = {"uuid": uuid, "nummer": nummer, "onderwerp": onderwerp or ("Mehdi's Personal Meeting Room" if nummer == self.ik["pmi"] else "Overleg"),
             "start": start, "einde": start + timedelta(minutes=minuten) if einde else None, "minuten": minuten if einde else None,
             "host_id": host or self.ik["id"], "deelnemers": [MEHDI_D, TEAM_D, BOT_D] if deelnemers is None else deelnemers,
             "rapport": set(rapport), "instantie": nummer == self.ik["pmi"] if instantie is None else instantie,
             "gepland": nummer != self.ik["pmi"] if gepland is None else gepland}
        self.sessies.append(s)
        return s

    def opname(self, s, soorten=("TRANSCRIPT", "MP4"), status="completed", vtt=VTT):
        bestanden = []
        for soort in soorten:
            fid = f"{s['uuid']}-{soort}"
            url = f"https://proef.zoom.us/rec/download/{fid}"
            bestanden.append({"id": fid, "file_type": soort, "status": status, "recording_start": iso(s["start"] + timedelta(seconds=5)),
                              "recording_end": iso(s["einde"] or s["start"]), "download_url": url,
                              "play_url": f"https://proef.zoom.us/rec/play/{fid}"})
            if soort == "TRANSCRIPT":
                self.downloads[url] = vtt.encode()
        self.opnames[s["uuid"]] = {"uuid": s["uuid"], "id": int(s["nummer"]), "topic": s["onderwerp"], "start_time": iso(s["start"]),
                                   "duration": s["minuten"] or 0, "share_url": "https://proef.zoom.us/rec/share/x",
                                   "recording_play_passcode": "geheimcode", "recording_files": bestanden}

    def _detail(self, s):
        d = {"uuid": s["uuid"], "id": int(s["nummer"]), "topic": s["onderwerp"], "start_time": iso(s["start"]),
             "host_id": s["host_id"], "participants_count": len(s["deelnemers"]), "type": 4 if s["nummer"] == self.ik["pmi"] else 2}
        if s["einde"]:
            d.update(end_time=iso(s["einde"]), duration=s["minuten"])
        return d

    @staticmethod
    def _weiger(scope):
        return 400, "", json.dumps({"code": 4711, "message": f"Invalid access token, does not contain scopes:[{scope}]."}).encode()

    def antwoord(self, pad, q):
        ik = self.ik
        for bron, scope in self.geen_recht.items():
            if (bron == "rapport" and pad.startswith("/report/")) or (bron == "instanties" and pad.endswith("/instances")) \
                    or (bron == "opnames" and pad.endswith("/recordings")):
                return self._weiger(scope)
        if any(pad.startswith(p) for p in self.fout):
            return 500, "", b"{}"
        if pad in ("/users/me", f"/users/{ik['id']}"):
            return dict(ik)
        if pad == f"/report/users/{ik['id']}/meetings":
            return {"meetings": [dict(self._detail(s)) for s in self.sessies if q.get("type") in s["rapport"]]}
        if pad == f"/past_meetings/{ik['pmi']}/instances":
            return {"meetings": [{"uuid": s["uuid"], "start_time": iso(s["start"])} for s in self.sessies if s["instantie"]]}
        if pad == f"/users/{ik['id']}/meetings":
            return {"meetings": [{"uuid": s["uuid"], "id": int(s["nummer"]), "topic": s["onderwerp"], "start_time": iso(s["start"])}
                                 for s in self.sessies if s["gepland"]]}
        if pad == f"/users/{ik['id']}/recordings":
            return {"meetings": list(self.opnames.values())}
        if pad == f"/past_meetings/{ik['pmi']}":
            if self.laatste is not None:
                return self._detail(self.laatste)
            pmr = sorted((s for s in self.sessies if s["nummer"] == ik["pmi"]), key=lambda s: s["start"])
            return self._detail(pmr[-1]) if pmr else None
        if pad.startswith("/past_meetings/") and pad.endswith("/participants"):
            s = next((s for s in self.sessies if s["uuid"] == pad.split("/")[2]), None)
            return {"participants": s["deelnemers"]} if s else None
        if pad.startswith("/past_meetings/"):
            ref = pad.split("/")[2]
            s = next((s for s in self.sessies if s["uuid"] == ref), None)
            return self._detail(s) if s else None
        if pad == f"/chat/users/{ik['id']}/sessions":
            return {"sessions": [s for s, _ in self.chat]}
        if pad == f"/chat/users/{ik['id']}/messages":
            for s, berichten in self.chat:
                if (q.get("to_contact") and q["to_contact"] == s.get("peer_contact_email")) or \
                        (q.get("to_channel") and q["to_channel"] == s.get("channel_id")):
                    van, tot = q.get("from", ""), q.get("to", "")
                    if not (re.fullmatch(ZOOM_DT, van) and re.fullmatch(ZOOM_DT, tot)):
                        # zoals Zoom (gemeten 22-10-2026): from en to zonder tijd worden genegeerd, alleen de laatste dag
                        laatste = max((b["date_time"][:10] for b in berichten), default="")
                        return {"messages": [b for b in berichten if b["date_time"][:10] == laatste]}
                    return {"messages": [b for b in berichten if van <= b["date_time"] <= tot]}
            return {"messages": []}
        if pad.startswith("/meetings/"):
            return self.meetings.get(pad.split("/")[2])
        raise AssertionError("onverwachte Zoom-vraag " + pad)

    def vraag(self, url, koppen, max_bytes=2_000_000):
        self.gevraagd.append((url, dict(koppen)))
        u = urllib.parse.urlsplit(url)
        if u.hostname != "api.zoom.us":
            d = self.downloads.get(url)
            return (200, "", d) if d is not None else (404, "", b"")
        pad = urllib.parse.unquote(urllib.parse.unquote(u.path[len("/v2"):]))
        a = self.antwoord(pad, dict(urllib.parse.parse_qsl(u.query)))
        if isinstance(a, tuple):
            return a
        if a is None:
            return 404, "", b'{"code": 3001, "message": "niet gevonden"}'
        return 200, "", json.dumps(a).encode()

    def downloads_gevraagd(self):
        return [u for u, _ in self.gevraagd if "/rec/download/" in u]


class Bord:
    """Het echte bord op een tijdelijke databank. bord.call gaat via de Flask-testclient, bord.db_lees leest dezelfde
    databank alleen-lezend. Elke oproep wordt bijgehouden, ook de lezingen langs db_lees (voor de volgorde, T28)."""

    def __init__(self, werkwijze=WERKWIJZE, fathom_werkwijze=FATHOM_WW):
        self.pad = os.path.join(MAP, f"bord-{next(TELLER)}.db")
        A.DB_PAD = self.pad
        A.init_db()
        c = sqlite3.connect(self.pad)
        agents = [("zoom-wacht", "De Zoomwacht", werkwijze), ("regisseur", "De Regisseur", "regels"), ("dagbundelaar", "De Dagbundelaar", "regels")]
        if fathom_werkwijze is not None:
            agents.append(("fathom-wacht", "De Fathomwacht", fathom_werkwijze))
        c.executemany("INSERT INTO agent(naam, label, aangemaakt, werkwijze) VALUES(?,?,?,?)",
                      [(n, label, "2026-10-01T00:00:00Z", ww) for n, label, ww in agents])
        c.commit()
        c.close()
        self.oproepen = []

    def call(self, pad, payload=None, method=None):
        A.DB_PAD = self.pad
        self.oproepen.append((pad, json.loads(json.dumps(payload)) if payload is not None else None))
        r = C.get(pad, headers=K) if payload is None and (method or "GET") == "GET" else C.post(pad, json=payload, headers=K)
        if r.status_code >= 400:
            raise urllib.error.HTTPError(f"http://bord{pad}", r.status_code, "proef", None, None)
        return r.get_json()

    def db_lees(self, sql, args=()):
        self.oproepen.append(("db_lees", sql))
        echt = bord.BORD_DB
        bord.BORD_DB = self.pad
        try:
            return ECHTE_DB_LEES(sql, args)
        finally:
            bord.BORD_DB = echt

    def sql(self, q, a=()):
        c = sqlite3.connect(self.pad)
        c.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in c.execute(q, a).fetchall()]
        finally:
            c.close()

    def rij(self, uniek):
        r = self.sql("SELECT * FROM gesprek_log WHERE uniek=?", (uniek,))
        return r[0] if r else None

    def item(self, uniek):
        r = self.sql("SELECT * FROM klaarzet WHERE uniek=?", (uniek,))
        return r[0] if r else None

    def noden(self):
        return {r["tekst"]: r["wie"] for r in self.sql("SELECT tekst, wie FROM nood WHERE naam='zoom-wacht' AND open=1")}

    def status(self):
        r = self.sql("SELECT * FROM status WHERE naam='zoom-wacht'")
        return r[0] if r else None

    def posts(self, pad):
        return [p for q, p in self.oproepen if q == pad and p is not None]


ECHTE_DB_LEES = bord.db_lees
# De echte tokenweg van zoom.py, voor de toetsen met twee apps (EIGEN-1, EIGEN-2): Wereld vervangt _toegang.
ECHTE_TOEGANG, ECHTE_RECHTEN = Z._toegang, Z.rechten
ECHTE_DOWNLOAD = Z.download          # RZ3-04: de proefdownload langs de echte download() met haar grendels
ECHTE_LEES = Z.lees                  # RZ4-02: de eigenaarscontrole van de leesapp langs de echte lees() met haar grendels


class Wereld:
    """Een ronde van De Zoomwacht op nagebootste bronnen en het echte bord."""

    def __init__(self, werkwijze=WERKWIJZE, fathom_werkwijze=FATHOM_WW, leesapp=True, ik=IK, bewezen=True):
        n = next(TELLER)
        self.map = os.path.join(MAP, f"wereld-{n}")
        self.fathom = os.path.join(self.map, "fathom-data")
        os.makedirs(self.fathom)
        ZW.STAAT = os.path.join(self.map, "data", "zoom-wacht.json")
        if bewezen:
            # RZ6-01: de gebruiker van deze wereld was kort geleden op Fathom bewezen, zoals op de VM na een gewone week.
            # Een test die het bewijs zelf toetst, maakt de wereld met bewezen=False.
            os.makedirs(os.path.dirname(ZW.STAAT))
            with open(ZW.STAAT, "w", encoding="utf-8") as f:
                json.dump({"identiteit": {"id": ik["id"], "pmi": ik["pmi"], "bewezen": "2026-10-01T06:00:00+00:00"}}, f)
        ZW.ZOOM_DATA = os.path.join(self.map, "data", "zoom-data")
        ZW.FATHOM_DATA = self.fathom
        self.bord = Bord(werkwijze, fathom_werkwijze)
        self.zoom = NepZoom(ik)
        self.api, self.api_fout = [], None
        ZW.ag._prive, ZW.ag._prive_re, ZW.ag._log = set(), None, []
        bord.call, bord.db_lees = self.bord.call, self.bord.db_lees
        Z._vraag, Z._toegang = self.zoom.vraag, self.zoom.toegang
        Z._BESTANDEN, Z._LEES_BESTANDEN = (), ()
        Z._tokens.clear()
        Z.vastzetten(None)
        ZW.fathom.beschikbaar = lambda: True
        ZW.fathom.gesprekken = self._gesprekken
        for k in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"):
            os.environ[k] = "stack-proef"
        for k in ("ZOOM_LEES_CLIENT_ID", "ZOOM_LEES_CLIENT_SECRET"):
            if leesapp:
                os.environ[k] = "lees-proef"
            else:
                os.environ.pop(k, None)
        os.environ.pop("ZOOM_MEHDI_USER", None)
        self.uitvoer = ""

    def _gesprekken(self, sinds, met_transcript=False):
        assert met_transcript is False, "De Zoomwacht vraagt nooit een transcript aan Fathom"
        if self.api_fout:
            raise self.api_fout
        return [dict(g) for g in self.api]

    def fathom_opname(self, rid, s=None, nummer=None, start=None, einde=None, eigen=True, prive=False, archief=True, api=True,
                      rij=True, kapot=False, url=None, herkenning=None):
        """Een opname van Fathom: in het archief (gesprek.json als laatste), in de API, en als rij in de gesprekkentabel
        zoals De Fathomwacht ze schrijft. url: een andere meeting_url dan de Zoom-link met het nummer (BAS-03).
        herkenning: de herkenning in gesprek.json, als ze anders is dan {prive, thema} (RZ3-01)."""
        start = start or (s["start"] + timedelta(seconds=40))
        einde = einde or (s["einde"] if s else start + timedelta(minutes=20))
        nummer = nummer or (s["nummer"] if s else PMI)
        g = {"recording_id": rid, "title": f"Gesprek {rid}",
             "meeting_url": url if url is not None else f"https://us06web.zoom.us/j/{nummer}?pwd=abc",
             "url": f"https://fathom.video/calls/{rid}", "recording_start_time": iso(start), "recording_end_time": iso(einde),
             "recorded_by": {"name": "Afspraken" if eigen else "Shaniel Work",
                             "email": EIGEN_ADRES if eigen else ANDER_ADRES}}
        if archief:
            map_ = os.path.join(self.fathom, f"{start.astimezone(ZW.BE):%Y-%m-%d %H%M} Gesprek {rid}")
            os.makedirs(map_)
            with open(os.path.join(map_, "gesprek.json"), "w", encoding="utf-8") as f:
                f.write('{"recording_id": ' if kapot else
                        json.dumps(dict(g, herkenning=herkenning if herkenning is not None else {"prive": prive, "thema": "proefthema"})))
        if api:
            self.api.append(g)
        if rij:
            st = start.astimezone(ZW.BE)
            self.bord.call("/api/gesprekken", {"rijen": [{"uniek": f"fathom:{rid}", "datum": st.strftime("%Y-%m-%d"), "start": st.strftime("%H:%M"),
                                                          "minuten": round((einde - start).total_seconds() / 60), "personen": "Fathom-personen",
                                                          "thema": "Fathom-thema", "prive": prive, "archief": "fathom-map", "link": g["url"],
                                                          "opgenomen_door": g["recorded_by"]["name"], "bron": "fathom"}]})
        return g

    def ronde(self, nu, *argv):
        ZW.nu = lambda: nu
        self.bord.oproepen.clear()
        self.zoom.gevraagd.clear()
        uit = io.StringIO()
        with redirect_stdout(uit), redirect_stderr(io.StringIO()):
            try:
                ZW.main(list(argv))
                fout = None
            except Exception as e:  # noqa: BLE001
                fout = e
        self.uitvoer = uit.getvalue()
        return fout

    def dagregel(self, dag):
        it = self.bord.item(f"zoom:dag:{dag}")
        return (it, json.loads(it["inhoud"])) if it else (None, None)

    def vangnetmappen(self):
        return sorted(n for n in os.listdir(ZW.ZOOM_DATA) if not n.startswith(".")) if os.path.isdir(ZW.ZOOM_DATA) else []

    def alle_tekst(self):
        """Alles wat de ronde naar buiten bracht: bordoproepen, schermuitvoer en de zoom.json-bestanden."""
        delen = [json.dumps(self.bord.oproepen, ensure_ascii=False), self.uitvoer]
        for m in self.vangnetmappen():
            p = os.path.join(ZW.ZOOM_DATA, m, "zoom.json")
            if os.path.exists(p):
                delen.append(open(p, encoding="utf-8").read())
        return "\n".join(delen)


class Overgeslagen(Exception):
    """Lokaal zonder Flask: de toets heeft het echte bord nodig. In de CI kan dit niet (zie de import van app)."""


def bord_nodig(f):
    def omhulsel():
        if A is None:
            raise Overgeslagen("Flask niet geinstalleerd, het echte bord is nodig")
        return f()
    omhulsel.__name__ = f.__name__
    return omhulsel


def dag_twintig(w, n_pmr=15, met_gepland=True, zonder_fathom=(7, 11)):
    """Een synthetische dag zoals 20-10: sessies in de vaste vergaderruimte (plus een geplande meeting) met elk een
    Zoom-opname; Fathom van het eigen account 16 tot 195 seconden later gestart en op dezelfde seconde gestopt."""
    sessies, fathom = [], {}
    for i in range(n_pmr):
        s = w.zoom.sessie(f"pmr-{i:02d}", bxl("2026-10-20 08:30") + timedelta(minutes=40 * i), 20 + i)
        sessies.append(s)
    if met_gepland:
        sessies.append(w.zoom.sessie("gepland-01", bxl("2026-10-20 20:00"), 30, nummer="8200000002", onderwerp="[UNABO-PO] Klantgesprek",
                                     deelnemers=[MEHDI_D, BEKEND_D, BOT_D], rapport=("past",)))
    for i, s in enumerate(sessies):
        w.zoom.opname(s)
        if i not in zonder_fathom:
            rid = str(500 + i)
            w.fathom_opname(rid, s, start=s["start"] + timedelta(seconds=16 + (i * 12) % 180), einde=s["einde"])
            fathom[s["uuid"]] = rid
    return sessies, fathom


NU = datetime(2026, 10, 21, 7, 20, tzinfo=UTC)


# ------------------------------------------------------------------------------------------------- koppelen ---
def _s(uuid, start, einde, nummer=PMI, deelnemers=None, host="mehdi-id"):
    d = ZW.deelnemers_uit([MEHDI_D, TEAM_D] if deelnemers is None else deelnemers)
    return {"uuid": uuid, "nummer": nummer, "start": start, "einde": einde, "deelnemers": d, "host_id": host, "deelname": False,
            "duur": None, "onderwerp": ""}


def _o(rid, start, einde, nummer=PMI, eigen=True):
    return {"rid": rid, "uniek": f"fathom:{rid}", "nummer": nummer, "start": start, "einde": einde, "eigen": eigen,
            "prive": False, "thema": "", "map": "m", "archief": True}


def _t(hms, dag="2026-10-20"):
    return datetime.fromisoformat(f"{dag}T{hms}+02:00").astimezone(UTC)


def test_t06_aansluitende_sessies_wisselen_niet():
    """Z09, Z10 (en Z06, Z07, Z14, Z15): sessies die op minder dan 20 seconden aansluiten. Elke opname hoort bij de
    sessie waarmee ze overlapt; geen omwisseling, geen opname bij twee sessies."""
    paren = [("Z09", "15:16:20", "15:17:55", "F09", "15:16:41", "15:17:55"), ("Z10", "15:18:14", "15:46:06", "F10", "15:18:33", "15:46:06"),
             ("Z06", "11:02:00", "11:30:10", "F06", "11:02:30", "11:30:10"), ("Z07", "11:30:25", "11:58:00", "F07", "11:30:50", "11:58:00"),
             ("Z14", "17:00:00", "17:12:00", "F14", "17:00:20", "17:12:00"), ("Z15", "17:12:15", "17:40:00", "F15", "17:12:40", "17:40:00")]
    sessies = [_s(z, _t(a), _t(b)) for z, a, b, _, _, _ in paren]
    opnames = [_o(f, _t(a), _t(b)) for _, _, _, f, a, b in paren]
    k = ZW.koppel(sessies, opnames, IK, NU)
    assert {u: o["rid"] for u, o in k["leidend"].items()} == {z: f for z, _, _, f, _, _ in paren}, k["leidend"]
    assert not k["dubbel"] and not k["buiten"] and not k["gezien"], k


def test_t07_opname_uit_een_andere_ruimte_koppelt_niet():
    """Z12: een opname van Shaniel Work uit een ander nummer overlapt 2,1 minuten met een sessie in de vaste ruimte."""
    s = _s("Z12", _t("12:00:00"), _t("12:30:00"))
    o = _o("SW1", _t("12:27:54"), _t("12:58:00"), nummer="7300000003", eigen=False)
    k = ZW.koppel([s], [o], IK, NU, rapport_ok=True)
    assert not k["leidend"] and not k["dubbel"], k
    assert k["buiten"] == {"SW1": "andere-ruimte"}, "de opname uit een andere ruimte telt niet voor Mehdi"
    assert not ZW.koppel([s], [o], IK, NU)["buiten"], "ZOO-03: zonder rapport is 'een andere ruimte' onbekend"


def test_t08_het_eigen_account_leidt():
    """Z08 (eigen 31,2 min, Shaniel Work 29,8), Z21 (eigen 31,2, Shaniel 1,7) en eigen 1 min tegen Shaniel 29 min."""
    for naam, eigen_min, ander_min in (("Z08", 31.2, 29.8), ("Z21", 31.2, 1.7), ("Z99", 1, 29)):
        s = _s(naam, _t("10:00:00"), _t("10:32:00"))
        eigen = _o(naam + "-eigen", _t("10:00:30"), _t("10:00:30") + timedelta(minutes=eigen_min))
        ander = _o(naam + "-sw", _t("10:00:40"), _t("10:00:40") + timedelta(minutes=ander_min), eigen=False)
        k = ZW.koppel([s], [ander, eigen], IK, NU)
        assert k["leidend"][naam]["rid"] == naam + "-eigen", (naam, k["leidend"])
        assert k["dubbel"] == {naam + "-sw": (naam, naam + "-eigen")}, (naam, k["dubbel"])
        wens = ZW.koppel_wensen(dict(k, _opnames={o["rid"]: o for o in (eigen, ander)}))
        assert wens[f"fathom:{naam}-sw"] == {"sessie": f"zoom:meeting:{naam}", "dubbel_van": f"fathom:{naam}-eigen"}, wens


def test_t95_een_lange_opname_over_twee_korte_sessies():
    """X2: een lange opname overspant twee korte sessies, een tweede opname past maar op een ervan. Een gulzige
    toewijzing gaf de lange opname aan de langste overlap en liet een sessie zonder koppeling; de maximale toewijzing
    koppelt beide sessies."""
    s1, s2 = _s("S1", _t("10:00:00"), _t("10:05:00")), _s("S2", _t("10:06:00"), _t("10:20:00"))
    lang, kort = _o("LANG", _t("10:00:10"), _t("10:20:00")), _o("KORT", _t("10:07:00"), _t("10:12:00"))
    k = ZW.koppel([s1, s2], [lang, kort], IK, NU)
    assert {u: o["rid"] for u, o in k["leidend"].items()} == {"S1": "LANG", "S2": "KORT"}, k["leidend"]
    assert not k["dubbel"], "geen van beide is een dubbel: elke sessie heeft haar eigen opname"


def test_t96_twee_eigen_opnames_van_een_sessie():
    s = _s("S", _t("09:00:00"), _t("09:40:00"))
    groot, klein = _o("GROOT", _t("09:00:20"), _t("09:40:00")), _o("KLEIN", _t("09:20:00"), _t("09:40:00"))
    k = ZW.koppel([s], [klein, groot], IK, NU)
    assert k["leidend"]["S"]["rid"] == "GROOT" and k["dubbel"] == {"KLEIN": ("S", "GROOT")}, k


def test_koppel_ander_account_alleen_met_mehdi_in_de_sessie():
    """13.1: een opname van een ander account telt alleen als Mehdi volgens Zoom in de sessie zat."""
    zonder = _s("Z", _t("09:00:00"), _t("09:30:00"), deelnemers=[TEAM_D, BEKEND_D])
    o = _o("SW", _t("09:00:30"), _t("09:30:00"), eigen=False)
    k = ZW.koppel([zonder], [o], IK, NU)
    assert not k["leidend"] and k["buiten"] == {"SW": "zonder-mehdi"}, k
    met = _s("M", _t("09:00:00"), _t("09:30:00"))
    assert ZW.koppel([met], [o], IK, NU)["leidend"]["M"]["rid"] == "SW"


# ------------------------------------------------------------------------------------------- dag en tijd ---
def test_t22_brusselse_dag_rond_de_wisseling():
    assert ZW.dag_van(datetime(2026, 10, 25, 22, 30, tzinfo=UTC)) == "2026-10-25", "23:30 Brussel (winteruur)"
    assert ZW.dag_van(datetime(2026, 10, 24, 22, 30, tzinfo=UTC)) == "2026-10-25", "00:30 Brussel (zomeruur)"
    b, e = ZW.dag_grenzen("2026-10-25")
    assert e - b == timedelta(hours=25), e - b
    b, e = ZW.dag_grenzen("2027-03-28")
    assert e - b == timedelta(hours=23), e - b


def test_vtt_in_de_vorm_van_fathom():
    uit = ZW.vtt_naar_fathom(VTT)
    assert uit == [{"speaker": {"display_name": "Mehdi Chegini"}, "text": "Goedemorgen, dit is een proefzin.", "timestamp": "00:00:01"},
                   {"speaker": {"display_name": "Proefpersoon Ypsilon"}, "text": "Herkenbare zin uit het vangnet.", "timestamp": "00:01:02"}], uit


# ------------------------------------------------------------------------------------------ de grote dag ---
@bord_nodig
def test_t05_t11_een_dag_zoals_twintig_oktober():
    """T05: 16 sessies (15 in de vaste ruimte, 1 gepland), 14 met Fathom. T11: nergens een link of toegangscode."""
    w = Wereld()
    sessies, fathom = dag_twintig(w)
    fout = w.ronde(NU)
    assert fout is None, fout
    for s in sessies:
        rij = w.bord.rij(f"zoom:meeting:{s['uuid']}")
        assert rij and rij["bron"] == "zoom" and rij["link"] == "" and rij["sessie"] == f"zoom:meeting:{s['uuid']}", rij
        if s["uuid"] in fathom:
            assert rij["dubbel_van"] == f"fathom:{fathom[s['uuid']]}", (s["uuid"], rij["dubbel_van"])
            f = w.bord.rij(f"fathom:{fathom[s['uuid']]}")
            assert f["sessie"] == f"zoom:meeting:{s['uuid']}" and f["dubbel_van"] == "", f
            assert f["personen"] == "Fathom-personen" and f["link"].startswith("https://fathom.video/"), "velden van Fathom blijven"
        else:
            assert rij["dubbel_van"] == "" and rij["archief"].startswith(ZW.ZOOM_DATA), rij
    assert sum(1 for s in sessies if w.bord.rij(f"zoom:meeting:{s['uuid']}")["dubbel_van"]) == 14
    assert len(w.vangnetmappen()) == 2, w.vangnetmappen()
    it, inhoud = w.dagregel("2026-10-20")
    minuten = sum(s["minuten"] for s in sessies)
    assert it["titel"] == f"Zoom 20-10: 16 gesprekken (14 met Fathom, 2 alleen in Zoom), {minuten} min; 0 chatgesprekken", it["titel"]
    assert inhoud["telling"] == "volledig" and inhoud["stand"] == "definitief", inhoud
    assert (inhoud["gesprekken"], inhoud["met_fathom"], inhoud["alleen_zoom_tekst"]) == (16, 14, 2), inhoud
    assert it["sleutel"] == "" and it["voor"] == "mehdi" and it["van"] == "zoom-wacht", it
    for sleutel in ("datum", "stand", "telling", "bronnen", "gesprekken", "minuten", "met_fathom", "alleen_zoom_tekst",
                    "opname_zonder_tekst", "zonder_opname", "wacht", "alleen_mehdi", "chat", "werk"):
        assert sleutel in inhoud, f"de dagregel mist {sleutel} (contract Z8)"
    # T11: de linkgrendel over alles wat de ronde naar buiten bracht
    tekst = w.alle_tekst()
    treffer = VERBODEN.search(tekst)
    assert not treffer, f"een link of code lekte: {treffer.group(0)}"
    assert all(r["link"] == "" for r in w.bord.sql("SELECT link FROM gesprek_log WHERE uniek LIKE 'zoom:%'"))
    st = w.bord.status()
    assert st["status"] in ("klaar", "waakt"), st
    assert w.bord.noden() == {}, w.bord.noden()


# --------------------------------------------------------------------------------------------- het vangnet ---
def een_sessie(w, *, fathom=False, opname=("TRANSCRIPT", "MP4"), deelnemers=None, onderwerp="", nummer=PMI, einde=True, status="completed"):
    s = w.zoom.sessie("z24", bxl("2026-10-20 10:00"), 30, nummer=nummer, onderwerp=onderwerp, deelnemers=deelnemers, einde=einde)
    if opname is not None:
        w.zoom.opname(s, opname, status=status)
    if fathom:
        w.fathom_opname("700", s)
    return s


@bord_nodig
def test_t09_t10_vangnet_na_dertig_minuten():
    """Z24: opname met TRANSCRIPT, geen Fathom. Na 20 minuten wacht hij; na 31 minuten bewaart hij de Zoom-tekst."""
    w = Wereld()
    s = een_sessie(w)
    fout = w.ronde(s["einde"] + timedelta(minutes=20), "--droog")
    assert fout is None, fout
    assert "10:00 30 min, vaste vergaderruimte: wacht: opname in verwerking" in w.uitvoer, w.uitvoer
    assert not w.zoom.downloads_gevraagd() and not w.vangnetmappen()
    fout = w.ronde(s["einde"] + timedelta(minutes=20))
    assert fout is None, fout
    assert not w.zoom.downloads_gevraagd() and not w.vangnetmappen() and not w.bord.item("zoom-tekst:z24"), "T10: niets voor 30 minuten"
    geschreven = []
    echt = ZW._schrijf
    ZW._schrijf = lambda pad, data: (geschreven.append(os.path.basename(pad)), echt(pad, data))[1]
    try:
        fout = w.ronde(s["einde"] + timedelta(minutes=31))
    finally:
        ZW._schrijf = echt
    assert fout is None, fout
    assert len(w.zoom.downloads_gevraagd()) == 1, "de VTT is gedownload"
    mappen = w.vangnetmappen()
    assert len(mappen) == 1 and mappen[0] == f"2026-10-20 1000 Zoom vaste vergaderruimte [{ZW.achtervoegsel('z24')}]", mappen
    inhoud = sorted(os.listdir(os.path.join(ZW.ZOOM_DATA, mappen[0])))
    assert inhoud == ["transcript.json", "transcript.vtt", "zoom.json"], inhoud
    assert geschreven == ["transcript.vtt", "transcript.json", "zoom.json"], f"zoom.json komt als laatste: {geschreven}"
    tj = json.load(open(os.path.join(ZW.ZOOM_DATA, mappen[0], "transcript.json"), encoding="utf-8"))
    assert tj[0]["speaker"]["display_name"] == "Mehdi Chegini" and tj[1]["timestamp"] == "00:01:02", tj
    zj = json.load(open(os.path.join(ZW.ZOOM_DATA, mappen[0], "zoom.json"), encoding="utf-8"))
    assert zj["prive"] is True and zj["stand"] == "tekst bewaard" and zj["uuid"] == "z24", "X1: vangnettekst is altijd privé"
    rij = w.bord.rij("zoom:meeting:z24")
    assert rij["dubbel_van"] == "" and rij["archief"] == os.path.join(ZW.ZOOM_DATA, mappen[0]), rij
    it = w.bord.item("zoom-tekst:z24")
    assert it["voor"] == "regisseur" and it["soort"] == "zoom-tekst" and it["sleutel"] == "", it
    assert it["titel"] == "2026-10-20 10:00 Zoom-gesprek, 30 min, alleen in Zoom", it["titel"]
    assert "Ypsilon" not in it["titel"] and "Ypsilon" not in it["inhoud"], "geen namen in het item"
    assert json.loads(it["inhoud"]) == {"datum": "2026-10-20", "start": "10:00", "minuten": 30, "ruimte": "vaste vergaderruimte",
                                        "prive": False, "stand": "tekst bewaard", "deelnemers": 2}, it["inhoud"]
    assert not VERBODEN.search(w.alle_tekst()), "T11 ook voor het vangnet"


@bord_nodig
def test_t12_opname_zonder_tekst():
    """Z19: MP4 en TIMELINE klaar, geen TRANSCRIPT. Na 7 uur wachten; na 25 uur 'opname zonder tekst', nooit uitschrijven."""
    w = Wereld()
    s = een_sessie(w, opname=("MP4", "TIMELINE"))
    assert w.ronde(s["einde"] + timedelta(hours=7), "--droog") is None
    assert "wacht: Zoom-tekst nog niet klaar" in w.uitvoer, w.uitvoer
    fout = w.ronde(s["einde"] + timedelta(hours=25))
    assert fout is None, fout
    assert not w.zoom.downloads_gevraagd() and not w.vangnetmappen(), "geen download en geen map zonder tekst"
    assert {urllib.parse.urlsplit(u).hostname for u, _ in w.zoom.gevraagd} == {"api.zoom.us"}, "geen uitschrijfdienst"
    it = w.bord.item("zoom-tekst:z24")
    assert json.loads(it["inhoud"])["stand"] == "opname zonder tekst" and it["verwijzing"] == "", it
    _, inhoud = w.dagregel("2026-10-20")
    assert inhoud["opname_zonder_tekst"] == 1 and inhoud["alleen_zoom_tekst"] == 0, inhoud


@bord_nodig
def test_t13_opname_in_verwerking():
    """Z25: opname op processing, zonder bestanden en zonder eindtijd."""
    w = Wereld()
    s = w.zoom.sessie("z25", bxl("2026-10-20 22:00"), 0, einde=False)
    w.zoom.opnames["z25"] = {"uuid": "z25", "id": int(PMI), "topic": s["onderwerp"], "start_time": iso(s["start"]), "duration": 0,
                             "recording_files": []}
    assert w.ronde(NU, "--droog") is None
    assert "wacht: opname in verwerking" in w.uitvoer, w.uitvoer
    assert w.ronde(NU) is None
    assert not w.zoom.downloads_gevraagd() and not w.vangnetmappen()
    _, inhoud = w.dagregel("2026-10-20")
    assert inhoud["stand"] == "voorlopig: opname in verwerking" and inhoud["wacht"] == 1, inhoud


@bord_nodig
def test_t14_fathom_levert_later():
    """Ronde 1 bewaart de Zoom-tekst; daarna verschijnt Fathom. De rij wordt een dubbel, het item vervalt (nog op
    klaar: bijgewerkt; al opgepakt: met revisie), de map blijft en bevat geen Fathom-id."""
    for opgepakt in (False, True):
        w = Wereld()
        s = een_sessie(w)
        assert w.ronde(s["einde"] + timedelta(minutes=31)) is None
        it = w.bord.item("zoom-tekst:z24")
        assert json.loads(it["inhoud"])["stand"] == "tekst bewaard"
        if opgepakt:
            w.bord.call(f"/api/klaarzet/{it['id']}/opgepakt", {"door": "regisseur"})
        w.fathom_opname("777", s)
        assert w.ronde(s["einde"] + timedelta(hours=5)) is None
        assert w.bord.rij("zoom:meeting:z24")["dubbel_van"] == "fathom:777"
        na = w.bord.item("zoom-tekst:z24")
        assert json.loads(na["inhoud"])["stand"] == "vervallen: Fathom heeft het gesprek" and na["status"] == "klaar", na
        items = [i for p in w.bord.posts("/api/klaarzet") for i in p["items"] if i["uniek"] == "zoom-tekst:z24"]
        assert items and bool(items[0].get("revisie")) is opgepakt, items
        revisies = w.bord.sql("SELECT * FROM klaarzet_revisie WHERE uniek='zoom-tekst:z24'")
        assert len(revisies) == (1 if opgepakt else 0), revisies
        mappen = w.vangnetmappen()
        assert len(mappen) == 1
        for naam in os.listdir(os.path.join(ZW.ZOOM_DATA, mappen[0])):
            assert "777" not in open(os.path.join(ZW.ZOOM_DATA, mappen[0], naam), encoding="utf-8").read(), naam


@bord_nodig
def test_t15_fathom_api_wel_archief_niet():
    w = Wereld()
    s = een_sessie(w)
    w.fathom_opname("801", s, archief=False, rij=False)
    assert w.ronde(NU) is None
    assert not w.zoom.downloads_gevraagd() and not w.vangnetmappen()
    _, inhoud = w.dagregel("2026-10-20")
    assert inhoud["stand"] == "voorlopig: Fathom-archief volgt" and inhoud["wacht"] == 1, inhoud
    assert "Fathom niet leesbaar voor de koppeling" not in w.bord.noden(), w.bord.noden()


@bord_nodig
def test_t16_fathom_api_onbekend():
    """Na 2 uur geen vangnet (onbekend is niet leeg); na 25 uur wel, met een nood voor claude-code."""
    w = Wereld()
    s = een_sessie(w)
    w.api_fout = RuntimeError("Fathom plat")
    assert w.ronde(s["einde"] + timedelta(hours=2)) is None
    assert not w.zoom.downloads_gevraagd() and not w.vangnetmappen()
    assert "Fathom niet leesbaar voor de koppeling" not in w.bord.noden()
    assert w.ronde(s["einde"] + timedelta(hours=25)) is None
    assert len(w.vangnetmappen()) == 1, "na 24 uur onbekend toch het vangnet"
    assert w.bord.noden().get("Fathom niet leesbaar voor de koppeling") == "claude-code", w.bord.noden()


@bord_nodig
def test_t17_half_geschreven_gesprek_json():
    w = Wereld()
    s = een_sessie(w)
    w.fathom_opname("901", s, kapot=True, api=False, rij=False)
    assert w.ronde(NU) is None
    assert not w.vangnetmappen() and not w.zoom.downloads_gevraagd(), "onbekend is niet 'geen Fathom'"
    _, inhoud = w.dagregel("2026-10-20")
    assert "Fathom-archief onleesbaar" in inhoud["stand"] and inhoud["wacht"] == 1, inhoud


@bord_nodig
def test_t24_privesessie_met_naamgenoot_en_zonder_adres():
    """H2: een naamgenoot van iemand uit de personentabel en een deelnemer zonder e-mail zijn niet bekend: privé.
    De namen gaan naar het masker en staan in geen enkele logregel, titel of hartslag."""
    for anderen in ([NAAMGENOOT_D], [ZONDER_EMAIL_D], [MEHDI_D.copy() | {"id": "", "user_email": "mehdi@elders.test", "name": "Piet Vreemd"}]):
        w = Wereld()
        s = een_sessie(w, deelnemers=[MEHDI_D] + anderen)
        assert w.ronde(s["einde"] + timedelta(minutes=31)) is None
        rij = w.bord.rij("zoom:meeting:z24")
        assert rij["prive"] == 1, rij
        zj = json.load(open(os.path.join(ZW.ZOOM_DATA, w.vangnetmappen()[0], "zoom.json"), encoding="utf-8"))
        assert zj["prive"] is True
        it = w.bord.item("zoom-tekst:z24")
        assert it["titel"].endswith(" · PRIVÉ"), it["titel"]
        naam = anderen[0]["name"]
        assert naam in ZW.ag._prive, ZW.ag._prive
        for pad, p in w.bord.oproepen:
            if pad in ("/api/logboek", "/agent-status", "/api/klaarzet"):
                assert naam not in json.dumps(p, ensure_ascii=False), (pad, naam)
        assert naam not in w.uitvoer


@bord_nodig
def test_t24b_onderwerp_van_een_prive_meeting_niet_in_de_verwijzing():
    """De verwijzing van het zoom-tekst-item is het mappad, en dat gaat met de export van het bord naar Dropbox. Het
    onderwerp van een privé geplande meeting gaat daarom door het masker; de map op de VM houdt haar naam."""
    w = Wereld()
    s = een_sessie(w, nummer="8200000002", onderwerp="Gesprek met notaris Vermeulen", deelnemers=[MEHDI_D, NAAMGENOOT_D])
    assert w.ronde(s["einde"] + timedelta(minutes=31)) is None
    assert "Gesprek met notaris Vermeulen" in w.vangnetmappen()[0]
    it = w.bord.item("zoom-tekst:z24")
    assert "Vermeulen" not in it["verwijzing"] and "(privé)" in it["verwijzing"], it["verwijzing"]
    assert it["verwijzing"].endswith(f"[{ZW.achtervoegsel('z24')}]")


@bord_nodig
def test_rz3_01_fathom_met_afdeling_prive_is_prive_in_de_dagregel():
    """RZ3-01 (tegenproef op de herstelcontrole, 22-10-2026): De Fathomwacht bewaart in gesprek.json de ruwe herkenning,
    en die kan prive=false zeggen met afdeling prive. De dossierbeslissing noemt zo'n gesprek privé, maar opname_uit las
    alleen herkenning.prive: de Zoom-rij van die sessie bleef op prive 0, en de dagregel zette naam en onderwerp in
    inhoud.werk, en daarmee in de export naar Data uit Mehdi. Ook voor elk bestaand archief. Nu telt afdeling prive (in
    elke schrijfwijze) als privé, met dezelfde regel als De Fathomwacht (fathom_wacht.is_prive)."""
    for afdeling in ("prive", " Privé "):
        w = Wereld()
        s = een_sessie(w)
        w.fathom_opname("700", s, herkenning={"prive": False, "afdeling": afdeling, "thema": "Proefonderwerp Omega regelen"})
        assert w.ronde(NU) is None
        assert w.bord.rij("zoom:meeting:z24")["prive"] == 1, (afdeling, w.bord.rij("zoom:meeting:z24"))
        _, inhoud = w.dagregel("2026-10-20")
        assert inhoud["werk"] == [] and inhoud["gesprekken"] == 1, (afdeling, inhoud)
        assert "Omega" not in w.alle_tekst() and "Ypsilon" not in json.dumps(inhoud, ensure_ascii=False), afdeling
    assert ZW.opname_uit({"recording_id": 1, "recording_start_time": "2026-10-20T08:00:00Z",
                          "recording_end_time": "2026-10-20T08:30:00Z",
                          "herkenning": {"prive": False, "afdeling": "h-architects"}})["prive"] is False, "zakelijk blijft zakelijk"


@bord_nodig
def test_t104_tweede_ronde_met_een_ander_onderwerp_zelfde_map():
    """M11: de vangnetmap wordt gevonden op het achtervoegsel, niet op de volle naam."""
    w = Wereld()
    s = een_sessie(w, nummer="8200000002", onderwerp="Overleg A")
    assert w.ronde(s["einde"] + timedelta(minutes=31)) is None
    eerst = w.vangnetmappen()
    assert len(eerst) == 1 and "Zoom Overleg A [" in eerst[0], eerst
    s["onderwerp"] = "Overleg B, verplaatst"
    w.zoom.opnames["z24"]["topic"] = s["onderwerp"]
    os.unlink(ZW.STAAT)                       # geen cache: het nieuwe onderwerp komt echt binnen
    assert w.ronde(s["einde"] + timedelta(hours=3)) is None
    assert w.vangnetmappen() == eerst, w.vangnetmappen()
    assert len(w.zoom.downloads_gevraagd()) == 0, "de tekst is er al: geen tweede download"


# ------------------------------------------------------------------------------------------------ bronnen ---
@bord_nodig
def test_t18_alleen_de_huidige_rechten_en_daarna_m10():
    """T18: rapport, instanties en opnames zonder recht. Ondergrens, een nood per recht, geen vangnet en geen crash;
    Fathom-opnames met het nummer van de vaste ruimte tellen als 'gezien via Fathom'. M10: daarna een ronde met de
    leesapp geeft per gesprek precies een tellende rij."""
    w = Wereld(leesapp=False)
    sessies = [w.zoom.sessie(f"pmr-{i}", bxl("2026-10-20 09:00") + timedelta(hours=i), 25) for i in range(3)]
    for i, s in enumerate(sessies):
        w.zoom.opname(s)
        w.fathom_opname(str(600 + i), s)
    w.zoom.geen_recht = {"rapport": "report:read:user:admin", "instanties": "meeting:read:list_past_instances:admin",
                         "opnames": "cloud_recording:read:list_user_recordings, cloud_recording:read:list_user_recordings:admin"}
    assert w.ronde(NU) is None
    it, inhoud = w.dagregel("2026-10-20")
    assert it["titel"].startswith("Zoom 20-10: minstens 3 gesprekken (telling onvolledig)"), it["titel"]
    assert inhoud["telling"] == "ondergrens" and inhoud["met_fathom"] == 3, inhoud
    noden = w.bord.noden()
    for recht in ("report:read:user:admin", "meeting:read:list_past_instances:admin", "cloud_recording:read:list_user_recordings:admin"):
        assert noden.get(f"Zoom-telling onvolledig: de leesapp mist het recht {recht}") == "mehdi", noden
    assert noden.get("Zoom-leesapp ontbreekt: telling en vangnet zijn onvolledig") == "mehdi", noden
    assert not any(re.search(r"\d", t) for t in noden), f"N10: geen getal in een noodtekst {noden}"
    assert not w.vangnetmappen() and not w.zoom.downloads_gevraagd()
    assert w.bord.rij("zoom:meeting:pmr-0") is None, "M10: geen rij voor een gesprek dat alleen Fathom zag"
    # M10: met de leesapp verschijnen de sessies met hun uuid; per gesprek telt precies een rij
    for k in ("ZOOM_LEES_CLIENT_ID", "ZOOM_LEES_CLIENT_SECRET"):
        os.environ[k] = "lees-proef"
    w.zoom.geen_recht = {}
    assert w.ronde(NU + timedelta(hours=1)) is None
    for s in sessies:
        tellend = w.bord.sql("SELECT uniek FROM gesprek_log WHERE sessie=? AND COALESCE(dubbel_van,'')=''", (f"zoom:meeting:{s['uuid']}",))
        assert len(tellend) == 1 and tellend[0]["uniek"].startswith("fathom:"), (s["uuid"], tellend)
    assert w.dagregel("2026-10-20")[1]["telling"] == "volledig"


@bord_nodig
def test_t19_geen_enkele_bron_leesbaar():
    """Geen leesapp en geen token: de nood over de leesapp; hartslag fout; wat al open stond, blijft open (J13, N11).
    RZ7-01 (22-10-2026): zonder gelezen Zoom-gebruiker schrijft de ronde niets, ook geen dagregel 'gesprekken onbekend'
    en geen staat; De Dagbundelaar meldt dan zelf dat de dagregel ontbreekt (Z14), en onbekend wordt nooit 0."""
    w = Wereld(leesapp=False)
    w.zoom.token_fout = True
    w.bord.call("/agent-status", {"naam": "zoom-wacht", "status": "waakt", "nood": [{"tekst": "Oude nood", "wie": "mehdi"}]})
    staat_voor = open(ZW.STAAT, encoding="utf-8").read()
    fout = w.ronde(NU)
    assert isinstance(fout, RuntimeError), fout
    assert w.dagregel("2026-10-20")[0] is None, "geen dagregel zonder gelezen Zoom-gebruiker"
    assert not w.bord.posts("/api/klaarzet") and not w.bord.posts("/api/gesprekken")
    assert open(ZW.STAAT, encoding="utf-8").read() == staat_voor, "de staat bleef staan"
    assert w.bord.status()["status"] == "fout"
    noden = w.bord.noden()
    assert "Zoom-leesapp ontbreekt: telling en vangnet zijn onvolledig" in noden and "Oude nood" in noden, noden


@bord_nodig
def test_t19b_een_bekende_telling_wordt_niet_onbekend():
    w = Wereld()
    dag_twintig(w, n_pmr=2, met_gepland=False, zonder_fathom=())
    assert w.ronde(NU) is None
    w.zoom.token_fout = True
    assert isinstance(w.ronde(NU + timedelta(hours=6)), RuntimeError)
    assert w.dagregel("2026-10-20")[1]["telling"] == "volledig", "een storing overschrijft een bekende dagregel niet"


@bord_nodig
def test_t20_laatste_sessie_ontbreekt_in_de_telling():
    w = Wereld()
    s = w.zoom.sessie("pmr-a", bxl("2026-10-20 09:00"), 20)
    w.zoom.opname(s)
    w.fathom_opname("610", s)
    w.zoom.laatste = {"uuid": "pmr-verborgen", "nummer": PMI, "onderwerp": "x", "start": bxl("2026-10-20 18:00"),
                      "einde": bxl("2026-10-20 18:20"), "minuten": 20, "host_id": "mehdi-id", "deelnemers": [MEHDI_D, TEAM_D]}
    assert w.ronde(NU) is None
    _, inhoud = w.dagregel("2026-10-20")
    assert inhoud["telling"] == "ondergrens" and "laatste PMR-sessie ontbreekt" in inhoud["bronnen"]["onvolledig"], inhoud
    assert inhoud["bronnen"]["rapport"] == "ok", "ook als de andere bronnen ok zijn"
    rij = w.bord.rij("zoom:meeting:pmr-verborgen")
    assert rij and rij["prive"] == 1, "deelnemers niet te lezen: bij twijfel privé (H2)"


@bord_nodig
def test_t18b_j9_alleen_het_rapport_ontbreekt():
    """J9: volledig alleen als het rapport ok is. Ontbreekt alleen het rapport, dan een ondergrens met de reden dat de
    deelnames aan meetings van anderen niet gelezen zijn, ook als de vaste ruimte en de geplande meetings ok zijn."""
    w = Wereld()
    s = w.zoom.sessie("pmr-a", bxl("2026-10-20 09:00"), 20)
    w.zoom.opname(s)
    w.fathom_opname("615", s)
    w.zoom.geen_recht = {"rapport": "report:read:user:admin"}
    assert w.ronde(NU) is None
    _, inhoud = w.dagregel("2026-10-20")
    assert inhoud["telling"] == "ondergrens", inhoud
    assert inhoud["bronnen"]["onvolledig"] == ["deelnames aan meetings van anderen niet gelezen"], inhoud["bronnen"]
    assert inhoud["bronnen"]["vaste vergaderruimte"] == "ok" and inhoud["bronnen"]["gepland"] == "ok"


@bord_nodig
def test_t21_de_gebruiker_is_niet_de_eigenaar_van_de_ruimte():
    w = Wereld(ik=dict(IK, pmi="9100000099"))
    s = w.zoom.sessie("ander", bxl("2026-10-20 09:00"), 20, nummer="9100000099")
    w.zoom.opname(s)
    for i in range(3):
        w.fathom_opname(str(620 + i), None, nummer=PMI, start=bxl("2026-10-20 12:00") + timedelta(hours=i))
    assert w.ronde(NU) is None
    assert w.bord.noden().get("De Zoom-gebruiker van de leesapp is niet de eigenaar van de vaste vergaderruimte") == "mehdi"
    # RZ4-02: tot 22-10-2026 schreef de ronde dan toch een dagregel (een ondergrens); nu schrijft ze niets
    assert w.dagregel("2026-10-20")[0] is None, "met een vreemde Zoom-gebruiker geen dagregel"


@bord_nodig
def test_rz4_02_zoomwacht_schrijft_niets_als_de_identiteit_niet_klopt():
    """RZ4-02 (Codex RZ4-herstelcontrole, 22-10-2026): is de Zoom-gebruiker van de leesapp niet de eigenaar van de vaste
    vergaderruimte (identiteit_ok onwaar), dan meldde De Zoomwacht het verschil maar schreef ze toch de gesprekken, de
    koppelingen, de dagregels en de Zoom-tekst van een vreemde gebruiker weg. Nu schrijft ze niets: geen rij, geen
    koppeling, geen klaarzet, geen vangnetmap, geen download en geen staat, ook niet met --koppel-sinds. Alleen de nood
    voor Mehdi en een hartslag die zegt dat er niets geschreven is."""
    ander = "9100000099"
    w = Wereld(ik=dict(IK, pmi=ander), bewezen=False)
    # een oude rij met een joinlink, die --koppel-sinds anders zou koppelen en leegmaken
    w.bord.call("/api/gesprekken", {"rijen": [{"uniek": "zoom:meeting:oud-rz4", "datum": "2026-09-26", "start": "10:00", "minuten": 30,
                                               "personen": "Proefpersoon Zeta, Mehdi", "afdeling": "unabo", "thema": "Proefonderwerp Omega",
                                               "prive": False, "zekerheid": "middel", "waarom": "oud",
                                               "link": "https://us06web.zoom.us/j/8300000001", "opgenomen_door": "Mehdi", "bron": "zoom"}]})
    w.fathom_opname("830", None, nummer="8300000001", start=bxl("2026-09-26 10:00") + timedelta(seconds=50), einde=bxl("2026-09-26 10:29"))
    # in de ruimte van de vreemde gebruiker: een sessie met Fathom (koppeling) en een zonder (vangnet)
    s1 = w.zoom.sessie("rz4-a", bxl("2026-10-20 09:00"), 20, nummer=ander)
    w.zoom.opname(s1)
    w.fathom_opname("820", s1)
    w.zoom.opname(w.zoom.sessie("rz4-b", bxl("2026-10-20 11:00"), 30, nummer=ander))
    # het eigen Fathom-account zit meestal in een ander nummer: de identiteit klopt niet
    for i in range(3):
        w.fathom_opname(str(821 + i), None, nummer=PMI, start=bxl("2026-10-20 13:00") + timedelta(hours=i))
    w.zoom.chat = [({"type": "1:1", "peer_contact_email": TEAM_ADRES, "name": "Proefpersoon Ypsilon"},
                    [{"date_time": "2026-10-20T08:00:00Z", "sender": "info@h-invest.test"},
                     {"date_time": "2026-10-20T08:05:00Z", "sender": TEAM_ADRES}])]
    voor = w.bord.sql("SELECT * FROM gesprek_log ORDER BY uniek")
    assert w.ronde(NU, "--koppel-sinds", "2026-09-07") is None
    for pad in ("/api/gesprekken", "/api/gesprekken/koppel", "/api/klaarzet"):
        assert not w.bord.posts(pad), (pad, w.bord.posts(pad))
    assert w.bord.sql("SELECT * FROM gesprek_log ORDER BY uniek") == voor, "een rij of koppeling veranderde"
    assert not w.bord.sql("SELECT uniek FROM klaarzet WHERE van='zoom-wacht'"), "klaarzet met een vreemde gebruiker"
    assert not w.vangnetmappen() and not w.zoom.downloads_gevraagd() and not os.path.exists(ZW.STAAT)
    assert not w.bord.sql("SELECT tekst FROM logboek WHERE naam='zoom-wacht' AND stap='schrijf'")
    assert w.bord.noden().get("De Zoom-gebruiker van de leesapp is niet de eigenaar van de vaste vergaderruimte") == "mehdi", \
        w.bord.noden()
    st = w.bord.status()
    assert st["status"] == "waakt" and st["detail"] == ("niets geschreven: de Zoom-gebruiker van de leesapp is niet de eigenaar "
                                                        "van de vaste vergaderruimte"), st


def test_rz6_01_identiteit_alleen_bewezen_is_goed():
    """RZ6-01 (Codex, afgebakende controle release 1, 22-10-2026): zonder eigen Fathom-opname in het venster gold de
    gebruiker als goed. Nu is ze alleen goed met een bewijs: Fathom, ZOOM_MEHDI_USER, of een bewijs op Fathom van minder
    dan BEWIJS_GELDIG dagen voor dezelfde gebruiker en ruimte."""
    klok = datetime(2026, 10, 22, 7, 20, tzinfo=UTC)
    vers = {"identiteit": {"id": IK["id"], "pmi": PMI, "bewezen": "2026-10-01T06:00:00+00:00"}}
    oud = {"identiteit": {"id": IK["id"], "pmi": PMI, "bewezen": "2026-07-01T06:00:00+00:00"}}
    os.environ.pop("ZOOM_MEHDI_USER", None)
    assert ZW.identiteit(IK, PMI, {}, klok) == ("ok", "fathom")
    assert ZW.identiteit(IK, "9100000099", vers, klok) == ("anders", "fathom"), "Fathom gaat voor de staat"
    assert ZW.identiteit(IK, "", {}, klok) == ("onbekend", "")
    assert ZW.identiteit(IK, "", vers, klok) == ("ok", "staat")
    assert ZW.identiteit(IK, "", oud, klok) == ("onbekend", ""), "een bewijs ouder dan 90 dagen telt niet"
    assert ZW.identiteit(dict(IK, id="ander-id"), "", vers, klok) == ("onbekend", ""), "andere gebruiker"
    assert ZW.identiteit(dict(IK, pmi="9100000099"), "", vers, klok) == ("onbekend", ""), "andere ruimte"
    assert ZW.identiteit(IK, "", {"identiteit": {"id": IK["id"], "pmi": PMI, "bewezen": "kapot"}}, klok) == ("onbekend", "")
    assert ZW.identiteit(None, PMI, vers, klok) == ("onbekend", "")
    os.environ["ZOOM_MEHDI_USER"] = IK["id"]
    try:
        assert ZW.identiteit(IK, "", {}, klok) == ("ok", "instelling")
        assert ZW.identiteit(dict(IK, id="ander-id"), "", {}, klok) == ("onbekend", "")
    finally:
        os.environ.pop("ZOOM_MEHDI_USER", None)


@bord_nodig
def test_rz6_01_onbewezen_gebruiker_schrijft_niets_en_een_bewijs_wordt_onthouden():
    """RZ6-01: zonder bewijs schrijft De Zoomwacht niets (zoals bij een vreemde gebruiker, RZ4-02) en zet ze een nood voor
    Mehdi. Bewijst Fathom de gebruiker, dan schrijft ze en onthoudt ze dat bewijs in de staat."""
    w = Wereld(bewezen=False)
    s1 = w.zoom.sessie("rz6-a", bxl("2026-10-20 09:00"), 20)
    w.zoom.opname(s1)
    voor = w.bord.sql("SELECT * FROM gesprek_log ORDER BY uniek")
    assert w.ronde(NU) is None
    for pad in ("/api/gesprekken", "/api/gesprekken/koppel", "/api/klaarzet"):
        assert not w.bord.posts(pad), (pad, w.bord.posts(pad))
    assert w.bord.sql("SELECT * FROM gesprek_log ORDER BY uniek") == voor
    assert not w.vangnetmappen() and not w.zoom.downloads_gevraagd() and not os.path.exists(ZW.STAAT)
    assert w.bord.noden().get(ZW.IDENTITEIT_ONBEKEND_NOOD) == "mehdi", w.bord.noden()
    assert w.bord.status()["detail"] == "niets geschreven: de Zoom-gebruiker is niet bewezen", w.bord.status()
    # nu bewijst een eigen Fathom-opname in de vaste vergaderruimte de gebruiker
    w.fathom_opname("rz6-f", s1)
    assert w.ronde(NU + timedelta(minutes=5)) is None
    assert w.bord.posts("/api/gesprekken"), "met een bewijs schrijft de ronde weer"
    staat = json.load(open(ZW.STAAT, encoding="utf-8"))
    assert staat["identiteit"]["id"] == IK["id"] and staat["identiteit"]["pmi"] == PMI, staat
    assert ZW.IDENTITEIT_ONBEKEND_NOOD not in w.bord.noden(), w.bord.noden()


# ----------------------------------------------------------------------------------------------- dagregel ---
@bord_nodig
def test_t23_dagregel_in_vijf_stappen_en_k5():
    w = Wereld()
    s1 = w.zoom.sessie("d1", bxl("2026-10-20 10:00"), 30)
    w.zoom.opname(s1)
    w.fathom_opname("640", s1)
    w.zoom.sessie("d2", bxl("2026-10-21 08:00"), 30)
    # 1. een regel voor 20-10, geen voor 21-10, met lege sleutel
    assert w.ronde(NU) is None
    it, inhoud = w.dagregel("2026-10-20")
    assert it and it["sleutel"] == "" and inhoud["gesprekken"] == 1, (it, inhoud)
    assert w.dagregel("2026-10-21")[0] is None, "vandaag is nog niet afgelopen"
    # 2. dezelfde gegevens: bestaand
    assert w.ronde(NU + timedelta(minutes=5)) is None
    assert w.bord.item("zoom:dag:2026-10-20")["ts"] == it["ts"]
    schrijf = [r["tekst"] for r in w.bord.sql("SELECT tekst FROM logboek WHERE naam='zoom-wacht' AND stap='schrijf' ORDER BY id")]
    assert "dagregels: 0 nieuw, 0 bijgewerkt, 0 herzien, 7 bestaand" in schrijf[-1], schrijf[-1]
    # 3. opgepakt, dan een nieuwe sessie: revisie
    w.bord.call(f"/api/klaarzet/{it['id']}/opgepakt", {"door": "dagbundelaar"})
    w.zoom.sessie("d3", bxl("2026-10-20 15:00"), 20)
    assert w.ronde(NU + timedelta(minutes=10)) is None
    gestuurd = [i for p in w.bord.posts("/api/klaarzet") for i in p["items"] if i["uniek"] == "zoom:dag:2026-10-20"]
    assert gestuurd and gestuurd[0].get("revisie") is True, gestuurd
    na = w.bord.item("zoom:dag:2026-10-20")
    assert na["status"] == "klaar" and json.loads(na["inhoud"])["gesprekken"] == 2, na
    assert len(w.bord.sql("SELECT * FROM klaarzet_revisie WHERE uniek='zoom:dag:2026-10-20'")) == 1
    # 4. opgepakt, alleen een andere werklijst: geen revisie, de regel blijft zoals Mehdi ze kreeg
    w.bord.call(f"/api/klaarzet/{na['id']}/opgepakt", {"door": "dagbundelaar"})
    s1["deelnemers"] = [MEHDI_D, dict(TEAM_D, name="Ypsilon Anders"), BOT_D]
    os.unlink(ZW.STAAT)
    assert w.ronde(NU + timedelta(minutes=15)) is None
    gestuurd = [i for p in w.bord.posts("/api/klaarzet") for i in p["items"] if i["uniek"] == "zoom:dag:2026-10-20"]
    assert gestuurd and "Ypsilon Anders" in json.dumps(gestuurd[0]) and not gestuurd[0].get("revisie"), gestuurd
    assert w.bord.item("zoom:dag:2026-10-20")["status"] == "opgepakt"
    # 5. een dag van 9 dagen oud: nooit herzien, alleen een regel in het werkverslag
    w.zoom.sessie("d4", bxl("2026-10-20 18:00"), 20)
    assert w.ronde(datetime(2026, 10, 29, 7, 20, tzinfo=UTC), "--inhaal", "10") is None
    assert not [i for p in w.bord.posts("/api/klaarzet") for i in p["items"] if i["uniek"] == "zoom:dag:2026-10-20"]
    assert w.bord.item("zoom:dag:2026-10-20")["status"] == "opgepakt"
    regels = w.bord.sql("SELECT onderwerp, tekst FROM logboek WHERE naam='zoom-wacht' AND stap='besluit'")
    assert {"onderwerp": "dag 2026-10-20", "tekst": "dagregel niet herzien: ouder dan zes dagen"} in regels, regels


def test_k5_klaarzet_geeft_revisie_door():
    """K5: ag.klaarzet laat de sleutel revisie staan, ook door het masker heen."""
    gestuurd, echt = [], bord.call
    bord.call = lambda pad, payload=None, method=None: gestuurd.append((pad, payload)) or {"nieuw": 0}
    try:
        a = bord.Agent("proef-k5")
        a.prive(["Geheime Naam"])
        a.klaarzet([{"voor": "mehdi", "soort": "zoom", "titel": "Zoom met Geheime Naam", "uniek": "zoom:dag:x", "inhoud": {"a": 1}, "revisie": True}])
    finally:
        bord.call = echt
    item = gestuurd[0][1]["items"][0]
    assert item["revisie"] is True and "(privé)" in item["titel"], item


# ------------------------------------------------------------------------------------- ronde en werkwijze ---
def test_t25_bron_en_zaad():
    bron = open(os.path.join(RUNNER, "zoom_wacht.py"), encoding="utf-8").read()
    assert "ag.ronde(" in bron and "ag.hartslag(" not in bron, "N12: de ronde doet de hartslag"
    assert "pipedrive-won-deals" not in bron and "urllib.request" not in bron, "Z1: geen tweede Zoom-koppeling"
    nooit, beslist = bord.grenzen(ZAAD)
    assert nooit and beslist, "bord.grenzen geeft twee niet-lege lijsten"
    assert any("ander Fathom-account" in p for p in beslist), "13.1: de opnames van een ander account staan bij Wat Mehdi beslist"
    assert "\N{EM DASH}" not in ZAAD and "\N{EN DASH}" not in ZAAD and not bord.HTML.search(ZAAD), "N9 en NA44"
    assert "```" not in ZAAD and "~~~" not in ZAAD and len(ZAAD) >= 500
    assert ZAAD.splitlines()[2].startswith("Versie 2.2 ("), ZAAD.splitlines()[2]
    # RZ4-02 en RZ4-04 (22-10-2026): het zaad zegt wat de code doet bij een vreemde Zoom-gebruiker, wanneer de leesapp
    # sleutels bewaart, en dat De Dagbundelaar de laatste stap van de ochtendketen is (geen eigen wachttijd meer)
    zaad = " ".join(ZAAD.split())
    assert "schrijf ik die ronde niets" in zaad and "nood voor Mehdi" in zaad, "RZ4-02: Zoomwacht"
    assert "eigenaar van de app van de stack" in zaad, "RZ4-02: leesapp"
    assert "laatste stap van dezelfde keten" in zaad and "wacht op hetzelfde slot" not in zaad, "RZ4-04"
    import controle_agenten as CA  # noqa: PLC0415
    assert CA.n2_grenzen_in_werkwijze({"werkwijze": ZAAD}, None)[0] and CA.n9_stijl({"werkwijze": ZAAD}, None)[0]
    assert not CA.GEHEIM.search(ZAAD), "N8"
    assert ZW.teamdomeinen(ZAAD) and "globaal.be" in ZW.teamdomeinen(ZAAD)
    try:
        import markdown  # noqa: F401
    except ImportError:
        assert not os.environ.get("CI"), "markdown ontbreekt in de CI"
        return
    from test_agentnorm import _zo_op_het_bord  # noqa: PLC0415
    assert _zo_op_het_bord(ZAAD, bord.KOP_NOOIT, nooit) and _zo_op_het_bord(ZAAD, bord.KOP_MEHDI, beslist), \
        "wat bord.grenzen aanvaardt, staat zo op het bord"


@bord_nodig
def test_werkwijze_zonder_grenzen_alleen_lezen():
    """13.5 vraag 6: tot Mehdi de nieuwe werkwijze goedkeurt, staat de oude op het bord. Dan alleen lezen en een nood."""
    w = Wereld(werkwijze="# Werkwijze van De Zoomwacht\n\nVersie 1. Ik log de Zoom-communicatie.\n\n## Wat ik nooit doe\n\n- Een bericht sturen.\n", bewezen=False)
    s = een_sessie(w)
    assert w.ronde(s["einde"] + timedelta(hours=2)) is None
    assert w.bord.noden().get("Werkwijze mist de vaste grenzen") == "claude-code"
    assert not w.bord.posts("/api/gesprekken") and not w.bord.posts("/api/gesprekken/koppel") and not w.bord.posts("/api/klaarzet")
    assert not w.vangnetmappen() and not w.zoom.downloads_gevraagd() and not os.path.exists(ZW.STAAT)


@bord_nodig
def test_t26_personentabel_onbekend():
    w = Wereld(fathom_werkwijze=None)
    s = een_sessie(w, deelnemers=[MEHDI_D, BEKEND_D])
    w.zoom.sessie("z-team", bxl("2026-10-20 08:00"), 20, deelnemers=[MEHDI_D, TEAM_D])
    w.zoom.chat = [({"type": "1:1", "peer_contact_email": TEAM_ADRES, "name": "Proefpersoon Ypsilon"},
                    [{"date_time": "2026-10-20T08:00:00Z", "sender": "info@h-invest.test"},
                     {"date_time": "2026-10-20T08:05:00Z", "sender": TEAM_ADRES}])]
    assert w.ronde(s["einde"] + timedelta(hours=2)) is None
    assert w.bord.noden().get("Personentabel van De Fathomwacht niet gelezen") == "claude-code"
    assert w.bord.rij("zoom:meeting:z24")["prive"] == 1, "zonder personentabel is een klant onbekend: privé"
    assert w.bord.rij("zoom:meeting:z-team")["prive"] == 0, "het teamdomein uit mijn eigen werkwijze blijft gelden"
    chat = w.bord.rij(f"zoom:chat:{TEAM_ADRES}:2026-10-20")
    assert chat and chat["prive"] == 1 and chat["bron"] == "zoom", "zonder personentabel is elke 1:1 privé"
    assert "Proefpersoon Ypsilon" in ZW.ag._prive
    assert w.bord.status()["status"] in ("waakt", "klaar"), "de ronde loopt verder"


@bord_nodig
def test_t27_inhaal_droog_schrijft_niets():
    w = Wereld(bewezen=False)
    dag_twintig(w)
    assert w.ronde(NU, "--inhaal", "14", "--droog") is None
    posts = [(p, q) for p, q in w.bord.oproepen if q is not None]
    assert not posts, f"--droog stuurde iets naar het bord: {[p for p, _ in posts]}"
    assert not w.zoom.downloads_gevraagd() and not os.path.exists(ZW.ZOOM_DATA) and not os.path.exists(ZW.STAAT)
    assert "2026-10-07" in w.uitvoer and "2026-10-20: 16 gesprekken, 14 met Fathom" in w.uitvoer, w.uitvoer
    assert "08:30 20 min" in w.uitvoer, w.uitvoer
    for verboden in ("Ypsilon", "Mehdi Chegini", "Jan Proef", "UNABO", "Klantgesprek"):
        assert verboden not in w.uitvoer, verboden
    assert w.bord.status() is None, "geen hartslag in --droog"


@bord_nodig
def test_t28_koppel_sinds():
    """J12: eerst koppelen en teruglezen, dan dezelfde volledige rij met alleen link leeg. Niets verwijderd; een rij
    zonder Fathom blijft tellen. L4: een link met toegangscode van een terugkerende meeting geeft een nood."""
    w = Wereld()
    oud = [("zoom:meeting:oud-a", "2026-09-26", "10:00", 30, "https://us06web.zoom.us/j/8300000001?pwd=geheim"),
           ("zoom:meeting:oud-b", "2026-09-28", "14:00", 20, "https://us06web.zoom.us/j/8300000002")]
    for uniek, datum, start, minuten, link in oud:
        w.bord.call("/api/gesprekken", {"rijen": [{"uniek": uniek, "datum": datum, "start": start, "minuten": minuten, "personen": "Klant A, Mehdi",
                                                   "afdeling": "unabo", "thema": "Overleg", "prive": False, "zekerheid": "middel", "waarom": "oud",
                                                   "link": link, "opgenomen_door": "Mehdi", "bron": "zoom"}]})
    w.fathom_opname("650", None, nummer="8300000001", start=bxl("2026-09-26 10:00") + timedelta(seconds=50),
                    einde=bxl("2026-09-26 10:29"))
    w.zoom.meetings["8300000001"] = {"id": 8300000001, "type": 8}
    voor = {r["uniek"]: r for r in w.bord.sql("SELECT * FROM gesprek_log")}
    assert w.ronde(NU, "--koppel-sinds", "2026-09-07") is None
    volgorde = []
    for p, q in w.bord.oproepen:
        if p == "/api/gesprekken/koppel" and any(k["uniek"] == "zoom:meeting:oud-a" for k in q["koppelingen"]):
            volgorde.append("koppel")
        elif p == "db_lees":
            volgorde.append("lees")
        elif p == "/api/gesprekken" and any(r["uniek"] == "zoom:meeting:oud-a" and r.get("link") == "" for r in q["rijen"]):
            volgorde.append("wis")
    assert "koppel" in volgorde and "wis" in volgorde, volgorde
    assert volgorde.index("koppel") < volgorde.index("wis") and "lees" in volgorde[volgorde.index("koppel"):volgorde.index("wis")], volgorde
    na = {r["uniek"]: r for r in w.bord.sql("SELECT * FROM gesprek_log")}
    assert set(voor) <= set(na), "geen rij verwijderd"
    a, b = na["zoom:meeting:oud-a"], na["zoom:meeting:oud-b"]
    assert a["link"] == "" and a["dubbel_van"] == "fathom:650" and na["fathom:650"]["sessie"] == "zoom:meeting:oud-a", a
    for veld in ("datum", "start", "minuten", "personen", "afdeling", "thema", "prive", "zekerheid", "waarom", "archief", "opgenomen_door", "bron"):
        assert a[veld] == voor["zoom:meeting:oud-a"][veld], f"J12: {veld} veranderde"
    assert b["link"] == "" and b["dubbel_van"] == "" and b["personen"] == "Klant A, Mehdi", "zonder Fathom blijft de rij tellen"
    assert "Een oude Zoom-link met toegangscode hoort bij een terugkerende meeting: de code geldt tot ze in Zoom verandert" in w.bord.noden()
    assert not w.bord.sql("SELECT uniek FROM gesprek_log WHERE link LIKE '%pwd=%'"), "geen rij met pwd= meer"


@bord_nodig
def test_t29_koppeling_die_niet_terugkomt():
    """L32: koppel antwoordt onbekend (de Fathom-rij bestaat niet), of db_lees toont de koppeling niet. Dan telt de sessie
    niet als gekoppeld, komt er een nood voor claude-code, en staat ze in de dagregel niet als 'met Fathom'."""
    for geval in ("onbekend", "niet terug"):
        w = Wereld()
        s = een_sessie(w)
        w.fathom_opname("660", s, rij=geval != "onbekend")
        if geval == "niet terug":
            def verborgen(sql, args=(), echt=w.bord.db_lees):
                return [dict(r, sessie="") if r.get("uniek") == "fathom:660" else r for r in echt(sql, args)]
            bord.db_lees = verborgen
        assert w.ronde(NU) is None
        rij = w.bord.rij("zoom:meeting:z24")
        assert rij["dubbel_van"] == "", (geval, rij)
        assert w.bord.noden().get("Koppeling met Fathom niet bevestigd") == "claude-code", (geval, w.bord.noden())
        _, inhoud = w.dagregel("2026-10-20")
        assert inhoud["met_fathom"] == 0 and inhoud["gesprekken"] == 1, (geval, inhoud)
        assert not w.vangnetmappen(), "Fathom heeft het gesprek: geen vangnet"


def test_bas03_ander_account_zonder_zoomnummer_telt_niet():
    """BAS-03 (13.1, J11): een opname van een ander account zonder Zoom-nummer (Google Meet, of geen link) kan Zoom niet
    bevestigen, dus telt ze niet (buiten: zonder-zoom), ook zonder rapport. Een eigen opname zonder nummer blijft
    ongemoeid en telt; een opname van voor het venster krijgt niets (ZOO-02); zonder vaste gebruiker verandert er niets.
    Tot 21-10-2026 telde zo'n opname als gesprek van Mehdi."""
    van = _t("00:00:00")
    meet = _o("MEET", _t("14:00:00"), _t("14:30:00"), nummer="", eigen=False)
    eigen = _o("EIGEN-MEET", _t("16:00:00"), _t("16:30:00"), nummer="")
    oud = _o("OUD-MEET", _t("14:00:00", "2026-10-19"), _t("14:30:00", "2026-10-19"), nummer="", eigen=False)
    k = ZW.koppel([], [meet, eigen, oud], IK, NU, van=van)
    assert k["buiten"] == {"MEET": "zonder-zoom"} and not k["gezien"] and not k["leidend"], k
    wens = ZW.koppel_wensen(dict(k, _opnames={o["rid"]: o for o in (meet, eigen, oud)}))
    assert wens == {"fathom:MEET": {"dubbel_van": "buiten:zonder-zoom"}}, wens
    assert not ZW.koppel([], [meet], None, NU, van=van)["buiten"], "zonder vaste gebruiker: onbekend, niets gemarkeerd"
    assert "buiten (zonder zoom), ook zonder het rapport" in ZAAD, "het zaad zegt wat de code doet"


@bord_nodig
def test_bas03_zonder_zoom_op_het_bord():
    """BAS-03 op het bord: de rij van Shaniel Work zonder Zoom-link krijgt buiten:zonder-zoom en telt niet, de eigen
    opname zonder link telt, en De Regisseur ziet de rij nergens (J10)."""
    w = Wereld()
    p = w.zoom.sessie("P", bxl("2026-10-20 09:00"), 30)
    w.fathom_opname("700", p)
    w.fathom_opname("771", None, start=bxl("2026-10-20 14:00"), eigen=False, url="https://meet.google.com/abc-defg-hij")
    w.fathom_opname("772", None, start=bxl("2026-10-20 16:00"), url="")
    assert w.ronde(NU) is None
    assert koppelvelden(w, "fathom:771") == {"sessie": "", "dubbel_van": "buiten:zonder-zoom"}, koppelvelden(w, "fathom:771")
    assert tellend(w, "2026-10-20") == ["fathom:700", "fathom:772"], tellend(w, "2026-10-20")
    assert "Koppeling met Fathom niet bevestigd" not in w.bord.noden(), w.bord.noden()
    R, _ = _regisseur()
    oud = R.nu_utc
    R.nu_utc = lambda: NU
    try:
        uit = R.gesprekken_lees("2026-10-20", "2026-10-20")    # leest langs bord.db_lees van deze wereld
    finally:
        R.nu_utc = oud
    assert "fathom:771" not in json.dumps(uit) and uit["aantal"] == 2, uit


@bord_nodig
def test_t07_vangnet_en_buiten_op_het_bord():
    """T07 op het bord: de sessie gaat naar het vangnet, de opname uit de andere ruimte telt niet (buiten:andere-ruimte)."""
    w = Wereld()
    s = een_sessie(w)
    w.fathom_opname("670", None, nummer="7300000003", start=s["einde"] - timedelta(minutes=2, seconds=6), eigen=False)
    assert w.ronde(NU) is None
    assert w.bord.rij("fathom:670")["dubbel_van"] == "buiten:andere-ruimte"
    assert w.bord.rij("zoom:meeting:z24")["dubbel_van"] == "" and len(w.vangnetmappen()) == 1


# ----------------------------------------------------------------------------- het contract met De Regisseur ---
def _regisseur():
    """regisseur.py zoals De Regisseur draait, zonder echte databanken of sleutels (de thuismap is tijdelijk)."""
    os.environ.setdefault("TAKEN_DB", os.path.join(MAP, "taken.db"))
    os.environ["BELLEN_UIT"] = "1"
    import ochtend  # noqa: PLC0415
    import regisseur  # noqa: PLC0415
    return regisseur, ochtend


@bord_nodig
def test_contract_met_de_regisseur_dagregel_vangnet_en_zoom_tekst():
    """Wat De Zoomwacht op het echte bord zet, gelezen met de echte code van De Regisseur (13.5 X1, M5, I5): de dagregel
    geeft de Zoom-telling van het ochtendbericht met dezelfde getallen als haar titel, het zoom-tekst-item voor de
    regisseur komt in het ochtendbericht en wordt daarna opgepakt, en het vangnet geeft alleen metadata met het aantal
    deelnemers. Tot 21-10-2026 toetste elke kant dit contract alleen tegen een eigen, met de hand gemaakte versie."""
    R, O = _regisseur()
    w = Wereld()
    een_sessie(w)                                       # z24: alleen in Zoom, met tekst (vangnet)
    s2 = w.zoom.sessie("k1", bxl("2026-10-20 14:00"), 30)
    w.zoom.opname(s2)
    w.fathom_opname("641", s2)                          # k1: Fathom heeft het gesprek
    assert w.ronde(NU) is None
    it, inhoud = w.dagregel("2026-10-20")
    n, mf = inhoud["gesprekken"], inhoud["met_fathom"]
    assert (n, mf) == (2, 1), inhoud
    oud = (R.DATA, R.bord, R.nu_utc)
    R.DATA, R.bord, R.nu_utc = os.path.dirname(ZW.ZOOM_DATA), w.bord.call, (lambda: NU)
    try:
        # M5: de telling van het ochtendbericht en van de tool gesprekken komt uit de dagregel, met de getallen van de titel
        telling = O.zoom_telling(R._dagregels(["2026-10-20"])["2026-10-20"])
        assert telling.startswith(f"{n} gesprekken, {n - mf} alleen in Zoom"), (telling, it["titel"])
        assert f"{n} gesprekken ({mf} met Fathom, {n - mf} alleen in Zoom)" in it["titel"], it["titel"]
        b = R.ochtend_bronnen(NU)
        tekst = w.bord.item("zoom-tekst:z24")
        assert b["zoom"] == inhoud and b["zoom_teksten"] == [tekst["id"]], (b["zoom"], b["zoom_teksten"])
        assert f"Zoom gisteren: {telling}" in O.maak(b)["verder"], O.maak(b)["verder"]
        # X1: het vangnet geeft alleen metadata, met het aantal deelnemers uit het zoom-tekst-item
        uit = R.transcript_lees("zoom:meeting:z24", zoek="bloempot")
        assert uit.get("prive") is True and "uitingen" not in uit, uit
        assert uit["deelnemers"] == json.loads(tekst["inhoud"])["deelnemers"] and isinstance(uit["deelnemers"], int), uit
    finally:
        R.DATA, R.bord, R.nu_utc = oud


# --------------------------------------------------------------------------------------------- planning ---
def test_t30_planning():
    spec = importlib.util.spec_from_file_location("gesprekken_cron_zetten", os.path.join(RUNNER, "planning", "gesprekken_cron_zetten.py"))
    M = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(M)
    cron = open(os.path.join(RUNNER, "planning", "gesprekken.cron"), encoding="utf-8").read().splitlines()
    py, rn, lg = "/home/ubuntu/agents/.venv/bin/python", "/home/ubuntu/appportal/mijnagents-runner", "/home/ubuntu/agents"
    huidig = ["MAILTO=''", f"* * * * * {py} {rn}/bode.py >> {lg}/bode.log 2>&1",
              f"0 7 * * 1-5 {py} {rn}/dagbundelaar.py >> {lg}/dagbundelaar.log 2>&1",
              f"0 7,13 * * * {py} {rn}/fathom_wacht.py >> {lg}/fathom_wacht.log 2>&1",
              "# De Zoomwacht: mijnagents-runner/zoom_wacht.py (commentaar blijft staan)",
              f"15 7,13 * * * {py} {rn}/zoom_wacht.py >> {lg}/zoom_wacht.log 2>&1", ""]
    doel, oud = M.samenvoegen(huidig, cron)
    assert oud == 3, oud
    actief = [r for r in doel if r.strip() and not r.startswith("#") and not r.startswith("MAILTO")]
    keten = [r for r in actief if "keten.py" in r]
    assert len(keten) == 1 and keten[0].startswith("0 7,13 * * * /usr/bin/flock -w 1800 -E 75 /tmp/gesprekken.lock "), keten
    assert "; if [ $? -eq 75 ]; then " in keten[0], "een keten die het slot niet kreeg, staat in keten.log (RZ4-04)"
    assert not any("fathom_wacht.py" in r or "zoom_wacht.py" in r for r in actief), "de losse regels zijn weg"
    # RZ4-04: De Dagbundelaar heeft geen eigen regel meer; hij is de laatste stap van keten.py (tests/test_keten.py)
    assert not [r for r in actief if "dagbundelaar" in r], actief
    assert f"* * * * * {py} {rn}/bode.py >> {lg}/bode.log 2>&1" in doel and "MAILTO=''" in doel and huidig[4] in doel
    begin, einde = doel.index(M.BEGIN), doel.index(M.EINDE)
    assert doel[begin] == "# begin gesprekken (beheerd door planning/gesprekken_cron_zetten.py)" and doel[einde] == "# einde gesprekken"
    assert doel[begin + 1].startswith("# 07:00 UTC is 09:00 Brussel tot en met 24-10-2026"), "de tijden staan in het blok"
    import keten as KT  # noqa: PLC0415
    assert [s[0] for s in KT.STAPPEN] == ["fathom-wacht", "zoom-wacht"], "Fathom eerst, dan Zoom"
    assert M.samenvoegen(doel, cron) == (doel, 0), "twee keer samenvoegen geeft hetzelfde"
    for vreemd in (f"30 8 * * * {py} {rn}/zoom_wacht.py --inhaal 14", f"0 9 * * * {py} {rn}/keten.py",
                   f"0 7,13 * * * /usr/bin/timeout 2700 {py} {rn}/fathom_wacht.py >> {lg}/fathom_wacht.log 2>&1"):
        try:
            M.samenvoegen(huidig + [vreemd], cron)
        except ValueError:
            continue
        raise AssertionError(f"een onbekende regel werd aanvaard: {vreemd}")


# Het echte script als __main__, met een nagebootst bord dat alleen afdrukt, en een werk dat blijft hangen.
STUURPROGRAMMA = r"""
import json, os, runpy, sys, time
RUNNER = sys.argv[1]
sys.path.insert(0, RUNNER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import bord
bord.call = lambda pad, payload=None, method=None: print("BORD " + json.dumps([pad, payload]), flush=True) or {}
bord.Agent.werkwijze_lezen = lambda self: "# Werkwijze van de proef\n\nGenoeg om een ronde te beginnen.\n"

def traag(werkwijze):
    print("WERK", flush=True)
    time.sleep(60)

bord.grenzen = traag
sys.argv = [os.path.join(RUNNER, "zoom_wacht.py")]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


def test_t46_sigterm_midden_in_de_ronde_blijft_niet_op_actief():
    """J1, N11 (T46 voor De Zoomwacht): keten.py (na 1200 s) en De Regisseur (timeout 540) stoppen een te lange ronde met
    SIGTERM. Zonder handler stierf het proces zonder dat de ronde afsloot, bleef de hartslag op actief en weigerde De
    Regisseur tot een uur lang met 'loopt al'. Nu gaat SIGTERM als SystemExit door de ronde: exit 143, laatste hartslag fout."""
    p = subprocess.Popen([sys.executable, "-B", "-c", STUURPROGRAMMA, RUNNER], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    regels, einde = [], time.monotonic() + 60
    try:
        while time.monotonic() < einde:
            regel = p.stdout.readline()
            if not regel:
                break
            regels.append(regel.strip())
            if regel.strip() == "WERK":
                p.send_signal(signal.SIGTERM)
                break
        uit, fout = p.communicate(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
    regels += uit.splitlines()
    statussen = [json.loads(r[5:])[1] for r in regels if r.startswith("BORD ") and json.loads(r[5:])[0] == "/agent-status"]
    assert "WERK" in regels, f"de ronde kwam niet aan het werk: {regels} {fout[-600:]}"
    assert p.returncode == 128 + signal.SIGTERM, f"exitcode {p.returncode}, verwacht {128 + signal.SIGTERM}: {fout[-600:]}"
    assert statussen and statussen[0]["status"] == "actief" and statussen[-1]["status"] == "fout", statussen


# ------------------------------------------------------------------------------------- zoom.py: L1 en L5 ---
class _Http:
    def __init__(self, antwoorden):
        self.antwoorden, self.gevraagd = antwoorden, []

    def __call__(self, url, koppen, max_bytes=2_000_000):
        self.gevraagd.append((url, dict(koppen)))
        sleutel = url.split("?", 1)[0]
        if sleutel not in self.antwoorden:
            raise AssertionError("onverwachte vraag " + sleutel)
        return self.antwoorden[sleutel]


def _met_http(antwoorden, doe):
    oud = (Z._vraag, Z._toegang)
    h = _Http(antwoorden)
    Z._vraag, Z._toegang = h, (lambda profiel="stack": "tok")
    try:
        return doe(h)
    finally:
        Z._vraag, Z._toegang = oud


def test_t101_omleiding_naar_een_vreemde_host():
    """L1: een omleiding volgen we zelf: alleen naar https op zoom.us, na de eerste sprong zonder Authorization."""
    Z.vastzetten(None)
    Z._DOWNLOADS.update({"a": "https://proef.zoom.us/rec/download/a", "b": "https://proef.zoom.us/rec/download/b",
                         "c": "https://proef.zoom.us/rec/download/c"})
    antwoorden = {"https://proef.zoom.us/rec/download/a": (302, "https://evil.example/steel", b""),
                  "https://proef.zoom.us/rec/download/b": (302, "https://ssrweb.zoom.us/bestand/b", b""),
                  "https://ssrweb.zoom.us/bestand/b": (200, "", b"WEBVTT"),
                  "https://proef.zoom.us/rec/download/c": (302, "http://ssrweb.zoom.us/bestand/c", b"")}

    def doe(h):
        for bid in ("a", "c"):
            try:
                Z.download(bid)
                raise AssertionError(f"omleiding van {bid} naar een vreemde host werd gevolgd")
            except Z.Geweigerd as e:
                assert "http" not in str(e), "geen url in de fouttekst"
        assert all("evil.example" not in u for u, _ in h.gevraagd) and all(u.startswith("https://proef.") for u, _ in h.gevraagd), h.gevraagd
        h.gevraagd.clear()
        assert Z.download("b") == b"WEBVTT"
        assert h.gevraagd[0][1] == {"Authorization": "Bearer tok"} and h.gevraagd[1][1] == {}, h.gevraagd
    _met_http(antwoorden, doe)
    Z.vastzetten(None)


def test_t102_paden_buiten_de_vaste_gebruiker():
    """L5: lees() weigert elk pad buiten het vaste gebruikers-id, /past_meetings/ en de eigen nummers; download() alleen
    bestanden uit de eigen opnamelijst. Een weigering vraagt niets aan Zoom."""
    Z._LEES_BESTANDEN = ()
    os.environ.pop("ZOOM_MEHDI_USER", None)
    Z.vastzetten(None)
    ja = (200, "", b'{"id": "mehdi-id", "meetings": [{"uuid": "u1", "id": 1, "recording_files": [{"id": "f1", "file_type": "TRANSCRIPT", '
                    b'"status": "completed", "download_url": "https://proef.zoom.us/rec/download/f1"}]}]}')
    toegestaan = ["/users/mehdi-id", "/users/mehdi-id/recordings", "/report/users/mehdi-id/meetings", "/past_meetings/abc%3D%3D",
                  "/past_meetings/abc/participants", "/meetings/9100000001", "/chat/users/mehdi-id/sessions"]
    geweigerd = ["/users/ander-id/recordings", "/report/users/ander-id/meetings", "/meetings/9999999999", "/accounts/me/users",
                 "/users/mehdi-id/../ander-id/recordings", "/chat/users/ander-id/messages", "/past_meetings/", "/users"]
    antwoorden = {Z.API + "/users/me": ja}
    antwoorden.update({Z.API + p: ja for p in toegestaan})

    def doe(h):
        assert Z.lees("/users/me")["id"] == "mehdi-id"
        try:
            Z.lees("/users/mehdi-id/recordings")
            raise AssertionError("voor de vaste gebruiker gezet is, mag alleen de ingang")
        except Z.Geweigerd:
            pass
        Z.vastzetten("mehdi-id", ["9100000001"])
        for p in toegestaan:
            Z.lees(p)
        n = len(h.gevraagd)
        for p in geweigerd:
            try:
                Z.lees(p)
                raise AssertionError(f"{p} werd niet geweigerd")
            except Z.Geweigerd:
                pass
        assert len(h.gevraagd) == n, "een geweigerd pad vroeg toch iets aan Zoom"
        assert [b["id"] for m in Z.opnames("2026-10-01", "2026-10-21") for b in m["bestanden"]] == ["f1"]
        for bid in ("f2", "../f1", ""):
            try:
                Z.download(bid)
                raise AssertionError(f"download van {bid!r} buiten de eigen lijst")
            except Z.Geweigerd:
                pass
        assert len(h.gevraagd) == n + 1, "alleen de opnamelijst werd gevraagd"
    _met_http(antwoorden, doe)
    Z.vastzetten(None)


def test_geen_recht_is_een_toestand():
    """Z1: Zoom 400 met code 4711 wordt GeenRecht met de naam van het recht; 404 is None, geen fout."""
    Z.vastzetten("mehdi-id")
    antwoorden = {Z.API + "/report/users/mehdi-id/meetings": (400, "", b'{"code":4711,"message":"Invalid access token, does not contain scopes:[report:read:user:admin]."}'),
                  Z.API + "/users/mehdi-id/recordings": (400, "", b'{"code":124,"message":"Invalid access token, does not contain scopes:[cloud_recording:read:list_user_recordings, cloud_recording:read:list_user_recordings:admin]."}'),
                  Z.API + "/past_meetings/x": (404, "", b'{"code":3001}'),
                  Z.API + "/past_meetings/y": (500, "", b"")}

    def doe(h):
        for pad, scope in (("/report/users/mehdi-id/meetings", "report:read:user:admin"),
                           ("/users/mehdi-id/recordings", "cloud_recording:read:list_user_recordings:admin")):
            try:
                Z.lees(pad)
                raise AssertionError("geen GeenRecht")
            except Z.GeenRecht as e:
                assert e.scope == scope, e.scope
        assert Z.lees("/past_meetings/x") is None
        try:
            Z.lees("/past_meetings/y")
            raise AssertionError("geen fout")
        except Z.GeenRecht:
            raise AssertionError("een 500 is geen ontbrekend recht")
        except Z.ZoomFout as e:
            assert str(e) == "HTTP 500", str(e)
    _met_http(antwoorden, doe)
    Z.vastzetten(None)


def test_agendawacht_houdt_meeting_en_beschikbaar():
    """meeting() en beschikbaar() blijven werken zoals De Agendawacht ze gebruikt (agenda_wacht.py:4797)."""
    assert callable(Z.meeting) and callable(Z.beschikbaar)
    oud = Z._toegang
    Z._toegang = lambda profiel="stack": (_ for _ in ()).throw(Z.ZoomFout("geen token"))
    try:
        Z._meetings.pop("123", None)
        assert Z.meeting("123") is None, "een meeting die niet te lezen is, is None"
    finally:
        Z._toegang = oud


# ------------------------------------------------------------------------------------- zoom_leesapp: T106 ---
def test_t106_leesapp_schrijft_atomisch_met_600_en_toont_geen_waarde():
    import zoom_leesapp as ZL  # noqa: PLC0415
    map_ = os.path.join(MAP, "t106")
    os.makedirs(map_)
    env = os.path.join(map_, ".env")
    with open(env, "w", encoding="utf-8") as f:
        f.write("AGENTS_X=1\nZOOM_ACCOUNT_ID=stack-account-1234\n")
    os.chmod(env, 0o644)
    geheim = {"Account ID: ": "lees-account-998877", "Client ID: ": "lees-client-445566", "Client Secret: ": "lees-geheim-112233-zeer"}
    vervangen, echt_replace = [], os.replace
    oud = {"ENV": ZL.ENV, "getpass": ZL.getpass.getpass, "rechten": Z.rechten, "lees": Z.lees, "opnames": Z.opnames,
           "download": Z.download, "eigen": ZL.eigen_nummer, "best": Z._BESTANDEN, "lbest": Z._LEES_BESTANDEN,
           "token": Z.token_halen}
    ZL.ENV = env
    ZL.getpass.getpass = lambda vraag: geheim[vraag]
    Z.token_halen = lambda cid, geheim_, account: {"access_token": "proef", "scope": ""}     # ZOO-10: eerst een token
    # RZ4-02: dan de eigenaar, met het nieuwe token: de host van het eigen Fathom-nummer is /users/me van de nieuwe app
    ZL.eigen_nummer = lambda: PMI
    Z.lees = lambda pad, params=None, profiel="lees": {f"/meetings/{PMI}": {"host_id": "host-xyz-77"},
                                                        "/users/me": {"id": "host-xyz-77"},
                                                        "/users/host-xyz-77": {"id": "host-xyz-77", "pmi": int(PMI)}}[pad]
    os.replace = lambda a, b: (vervangen.append((a, b)), echt_replace(a, b))[1]
    Z._BESTANDEN, Z._LEES_BESTANDEN = (env,), (env,)
    for k in [k for k in os.environ if k.startswith("ZOOM_")]:
        del os.environ[k]
    uit = io.StringIO()
    try:
        with redirect_stdout(uit), redirect_stderr(uit):
            ZL.zetten()
        assert stat.S_IMODE(os.stat(env).st_mode) == 0o600, oct(os.stat(env).st_mode)
        regels = open(env, encoding="utf-8").read().splitlines()
        assert regels == ["AGENTS_X=1", "ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_LEES_CLIENT_ID=lees-client-445566",
                          "ZOOM_LEES_CLIENT_SECRET=lees-geheim-112233-zeer", "ZOOM_LEES_ACCOUNT_ID=lees-account-998877"], regels
        assert len(vervangen) == 1 and vervangen[0][1] == env and os.path.dirname(vervangen[0][0]) == map_, vervangen
        assert not [n for n in os.listdir(map_) if n != ".env"], "geen tijdelijk bestand achtergelaten"
        # zonder --vervang blijft een bestaande sleutel staan; met --vervang niet
        geheim["Client Secret: "] = "nieuw-geheim-998877-x"
        with redirect_stdout(uit):
            ZL.zetten()
        assert "ZOOM_LEES_CLIENT_SECRET=lees-geheim-112233-zeer" in open(env, encoding="utf-8").read()
        with redirect_stdout(uit):
            ZL.zetten(vervang=True)
        tekst = open(env, encoding="utf-8").read()
        assert "ZOOM_LEES_CLIENT_SECRET=nieuw-geheim-998877-x" in tekst and tekst.count("ZOOM_LEES_CLIENT_SECRET=") == 1
        assert stat.S_IMODE(os.stat(env).st_mode) == 0o600
        # toetsen: alleen namen, ja of nee; J17 schrijft ZOOM_MEHDI_USER zelf, met --zet en alleen als de host de
        # eigenaar van de app van de stack is (ZOO-08)
        Z.rechten = lambda profiel="lees": set(ZL.KERN) - {"report:read:user:admin"}
        Z.opnames = lambda van, tot, profiel="lees": [{"bestanden": [{"id": "f1", "soort": "TRANSCRIPT", "status": "completed", "start": "x"}]}]
        Z.download = lambda bid, profiel="lees", max_bytes=0: b"WEBVTT"
        with redirect_stdout(uit):
            code = ZL.toetsen(zet=True)
        laatste = uit.getvalue().strip().splitlines()[-1]
        assert code == 1 and laatste == "ontbreekt: report:read:user:admin", (code, laatste)
        assert "ZOOM_MEHDI_USER=host-xyz-77" in open(env, encoding="utf-8").read()
        Z.rechten = lambda profiel="lees": set(ZL.KERN)
        uit2 = io.StringIO()
        with redirect_stdout(uit2):
            assert ZL.toetsen() == 0
        assert uit2.getvalue().strip().splitlines()[-1] == "klaar"
        alles = uit.getvalue() + uit2.getvalue()
        for waarde in list(geheim.values()) + ["lees-geheim-112233-zeer", "host-xyz-77", "stack-account-1234"]:
            assert waarde not in alles, f"een waarde werd afgedrukt: {waarde[:6]}..."
    finally:
        os.replace = echt_replace
        ZL.ENV, ZL.getpass.getpass, ZL.eigen_nummer = oud["ENV"], oud["getpass"], oud["eigen"]
        Z.rechten, Z.lees, Z.opnames, Z.download = oud["rechten"], oud["lees"], oud["opnames"], oud["download"]
        Z._BESTANDEN, Z._LEES_BESTANDEN, Z.token_halen = oud["best"], oud["lbest"], oud["token"]
        for k in [k for k in os.environ if k.startswith("ZOOM_")]:
            del os.environ[k]


# ----------------------------------------------------------------------- de tegenlezing: ZOO-01 tot ZOO-10 ---
GEEN_RECHTEN = {"rapport": "report:read:user:admin", "instanties": "meeting:read:list_past_instances:admin",
                "opnames": "cloud_recording:read:list_user_recordings:admin"}


def tellend(w, dag):
    """De rijen van een dag die tellen (dubbel_van leeg), gesorteerd."""
    return sorted(r["uniek"] for r in w.bord.sql("SELECT uniek FROM gesprek_log WHERE datum=? AND COALESCE(dubbel_van,'')=''", (dag,)))


def koppelvelden(w, uniek):
    r = w.bord.rij(uniek)
    return {k: r[k] for k in ("sessie", "dubbel_van")} if r else None


def besluiten(w):
    return [(r["onderwerp"], r["tekst"]) for r in w.bord.sql("SELECT onderwerp, tekst FROM logboek WHERE naam='zoom-wacht' AND stap='besluit' ORDER BY id")]


def meeting_van_een_ander(w, uuid="K", start="2026-10-20 11:00"):
    """Een meeting van een klant waar Mehdi aan deelnam: alleen het rapport (pastJoined) kent ze."""
    return w.zoom.sessie(uuid, bxl(start), 40, nummer="7700000007", host="klant-host", rapport=("pastJoined",), gepland=False,
                         instantie=False)


@bord_nodig
def test_zoo02_opname_van_een_ander_account_telt_na_acht_dagen_nog():
    """ZOO-02: het Fathom-venster heeft een dag marge om te koppelen. Een opname van een ander account op die randdag had
    geen sessie meer in het Zoom-venster en kreeg buiten:andere-ruimte; de zoom:meeting-rij bleef naar haar wijzen, en
    vanaf de ronde van 28-10 telde geen enkele rij van dat gesprek nog. Beide varianten: een eigen geplande meeting en een
    meeting van een ander waar Mehdi aan deelnam."""
    for sessie in ({"nummer": "8200000002", "onderwerp": "Klantgesprek"},
                   {"nummer": "7700000007", "host": "klant-host", "rapport": ("pastJoined",), "gepland": False, "instantie": False}):
        w = Wereld()
        s = w.zoom.sessie("G", bxl("2026-10-20 11:00"), 40, **sessie)
        w.fathom_opname("992", s, eigen=False)
        assert w.ronde(NU) is None
        assert koppelvelden(w, "fathom:992") == {"sessie": "zoom:meeting:G", "dubbel_van": ""}, koppelvelden(w, "fathom:992")
        for dag in range(22, 31):
            assert w.ronde(datetime(2026, 10, dag, 7, 20, tzinfo=UTC)) is None, dag
            assert tellend(w, "2026-10-20") == ["fathom:992"], (sessie["nummer"], dag, koppelvelden(w, "fathom:992"))
        assert koppelvelden(w, "fathom:992") == {"sessie": "zoom:meeting:G", "dubbel_van": ""}


def test_zoo02_koppel_markeert_niets_voor_het_begin_van_het_venster():
    """ZOO-02: de dag marge dient alleen om te koppelen. Een opname die voor het Zoom-venster begint, krijgt geen buiten en
    wordt geen gesprek 'gezien via Fathom'; een opname in het venster wel."""
    van = _t("00:00:00")
    oud_ander = _o("OUD-SW", _t("11:00:00", "2026-10-19"), _t("11:40:00", "2026-10-19"), nummer="7700000007", eigen=False)
    oud_eigen = _o("OUD-EIGEN", _t("15:00:00", "2026-10-19"), _t("15:30:00", "2026-10-19"))
    nieuw_ander = _o("SW", _t("11:00:00"), _t("11:40:00"), nummer="7700000007", eigen=False)
    nieuw_eigen = _o("EIGEN", _t("15:00:00"), _t("15:30:00"))
    k = ZW.koppel([], [oud_ander, oud_eigen, nieuw_ander, nieuw_eigen], IK, NU, van=van, rapport_ok=True)
    assert k["buiten"] == {"SW": "andere-ruimte"}, k["buiten"]
    assert [[o["rid"] for o in g] for g in k["gezien"]] == [["EIGEN"]], k["gezien"]


@bord_nodig
def test_zoo02_grendel_geen_buiten_op_een_rij_met_een_sessie_van_buiten_de_ronde():
    """ZOO-02, tweede grendel: koppel_schrijven zet nooit buiten op een Fathom-rij die al bij een sessie hoort die deze
    ronde niet zag (eerst teruglezen met db_lees); is die sessie er wel, dan mag het (zonder-mehdi op verse kennis)."""
    w = Wereld()
    w.fathom_opname("995", None, nummer="7700000007", start=bxl("2026-10-20 11:00"), eigen=False)
    w.bord.call("/api/gesprekken/koppel", {"koppelingen": [{"uniek": "fathom:995", "sessie": "zoom:meeting:weg"}]})
    wens = {"fathom:995": {"dubbel_van": "buiten:andere-ruimte"}}
    bevestigd, gestuurd, gehouden = ZW.koppel_schrijven(dict(wens), {"zoom:meeting:ander"})
    assert gehouden == {"fathom:995"} and gestuurd == 0 and not w.bord.posts("/api/gesprekken/koppel")[1:], (gehouden, gestuurd)
    assert koppelvelden(w, "fathom:995") == {"sessie": "zoom:meeting:weg", "dubbel_van": ""}
    bevestigd, gestuurd, gehouden = ZW.koppel_schrijven(dict(wens), {"zoom:meeting:weg"})
    assert gehouden == set() and bevestigd == {"fathom:995"} and gestuurd == 1, (bevestigd, gestuurd, gehouden)


@bord_nodig
def test_zoo03_zonder_rapport_geen_buiten_andere_ruimte():
    """ZOO-03: het rapport (pastJoined) is de enige bron voor meetings van anderen waar Mehdi aan deelnam. Zonder rapport
    is 'een andere ruimte' onbekend: de opname blijft ongemoeid, nooit buiten."""
    # huidige rechten: rapport zonder recht, Mehdi in een meeting van een klant, alleen Shaniel Work nam op
    w = Wereld(leesapp=False)
    w.zoom.geen_recht = dict(GEEN_RECHTEN)
    w.fathom_opname("991", meeting_van_een_ander(w), eigen=False)
    assert w.ronde(NU) is None
    assert koppelvelden(w, "fathom:991") == {"sessie": "", "dubbel_van": ""}, koppelvelden(w, "fathom:991")
    assert tellend(w, "2026-10-20") == ["fathom:991"]
    # met de leesapp: het rapport geeft een ronde HTTP 500; de gekoppelde opname blijft gekoppeld en tellen
    w = Wereld()
    p = w.zoom.sessie("P", bxl("2026-10-20 09:00"), 30)
    w.fathom_opname("700", p)
    w.fathom_opname("701", meeting_van_een_ander(w), eigen=False)
    assert w.ronde(NU) is None
    assert tellend(w, "2026-10-20") == ["fathom:700", "fathom:701"], tellend(w, "2026-10-20")
    w.zoom.fout = {"/report/"}
    assert w.ronde(NU + timedelta(hours=6)) is None
    assert koppelvelden(w, "fathom:701") == {"sessie": "zoom:meeting:K", "dubbel_van": ""}, koppelvelden(w, "fathom:701")
    assert tellend(w, "2026-10-20") == ["fathom:700", "fathom:701"], tellend(w, "2026-10-20")


@bord_nodig
def test_zoo03_koppel_sinds_beoordeelt_andere_ruimte_opnieuw():
    """ZOO-03: wat zonder rapport niet te beoordelen was en daarna uit het venster schoof, beoordeelt --koppel-sinds
    opnieuw met het rapport. Een opname uit een meeting die in het rapport staat, telt (ook als ze eerder ten onrechte
    buiten:andere-ruimte kreeg); een uit een ruimte die niet in het rapport staat, krijgt buiten:andere-ruimte. Een eigen
    opname blijft ongemoeid, en zonder rapport verandert er niets."""
    w = Wereld()
    w.fathom_opname("981", meeting_van_een_ander(w, start="2026-10-01 11:00"), eigen=False)
    w.bord.call("/api/gesprekken/koppel", {"koppelingen": [{"uniek": "fathom:981", "dubbel_van": "buiten:andere-ruimte"}]})
    w.fathom_opname("982", None, nummer="7300000003", start=bxl("2026-10-02 15:00"), eigen=False)
    w.fathom_opname("983", None, nummer="7300000004", start=bxl("2026-10-02 17:00"))
    w.zoom.geen_recht = {"rapport": "report:read:user:admin"}
    assert w.ronde(NU, "--koppel-sinds", "2026-09-07") is None
    assert koppelvelden(w, "fathom:981")["dubbel_van"] == "buiten:andere-ruimte" and koppelvelden(w, "fathom:982")["dubbel_van"] == ""
    w.zoom.geen_recht = {}
    assert w.ronde(NU + timedelta(hours=6), "--koppel-sinds", "2026-09-07") is None
    assert koppelvelden(w, "fathom:981")["dubbel_van"] == "", koppelvelden(w, "fathom:981")
    assert koppelvelden(w, "fathom:982")["dubbel_van"] == "buiten:andere-ruimte", koppelvelden(w, "fathom:982")
    assert koppelvelden(w, "fathom:983")["dubbel_van"] == "", "een eigen opname blijft ongemoeid"


@bord_nodig
def test_zoo01_een_ondergrens_daalt_niet():
    """ZOO-01: van de vaste ruimte is alleen de laatste sessie zichtbaar. De ronde van 07:20 ziet S van 20-10 ('minstens
    1'), De Dagbundelaar pakt de regel op, Mehdi gebruikt zijn ruimte opnieuw en S valt uit de bronnen. S blijft
    meetellen (bewaard in de staat zodra ze een einde heeft), en de opgepakte regel gaat niet met een lagere telling
    terug naar Mehdi."""
    w = Wereld(leesapp=False)
    w.zoom.geen_recht = dict(GEEN_RECHTEN)
    w.zoom.sessie("S", bxl("2026-10-20 17:00"), 30)
    assert w.ronde(NU) is None
    it, inhoud = w.dagregel("2026-10-20")
    assert (inhoud["gesprekken"], inhoud["telling"]) == (1, "ondergrens"), inhoud
    w.bord.call(f"/api/klaarzet/{it['id']}/opgepakt", {"door": "dagbundelaar"})
    w.zoom.sessie("S2", bxl("2026-10-21 10:00"), 30)
    assert w.ronde(datetime(2026, 10, 21, 13, 20, tzinfo=UTC)) is None
    na = w.bord.item("zoom:dag:2026-10-20")
    assert na["status"] == "opgepakt" and json.loads(na["inhoud"])["gesprekken"] == 1, na
    assert not w.bord.sql("SELECT * FROM klaarzet_revisie WHERE uniek='zoom:dag:2026-10-20'")
    assert tellend(w, "2026-10-20") == ["zoom:meeting:S"], tellend(w, "2026-10-20")


@bord_nodig
def test_zoo01_volledig_wordt_geen_ondergrens_als_een_bron_faalt():
    """ZOO-01 met de leesapp: het rapport geeft een ronde HTTP 500. De opgepakte regel '2 gesprekken' blijft staan en gaat
    niet als 'minstens' terug naar Mehdi; de meeting van een ander blijft meetellen."""
    w = Wereld()
    w.fathom_opname("700", w.zoom.sessie("P", bxl("2026-10-20 09:00"), 30))
    w.fathom_opname("701", meeting_van_een_ander(w), eigen=False)
    assert w.ronde(NU) is None
    it, inhoud = w.dagregel("2026-10-20")
    assert (inhoud["gesprekken"], inhoud["telling"]) == (2, "volledig"), inhoud
    w.bord.call(f"/api/klaarzet/{it['id']}/opgepakt", {"door": "dagbundelaar"})
    w.zoom.fout = {"/report/"}
    assert w.ronde(NU + timedelta(hours=6)) is None
    na = w.bord.item("zoom:dag:2026-10-20")
    assert na["status"] == "opgepakt" and json.loads(na["inhoud"])["telling"] == "volledig", na
    assert not w.bord.sql("SELECT * FROM klaarzet_revisie WHERE uniek='zoom:dag:2026-10-20'")
    assert ("dag 2026-10-20", "dagregel niet herzien naar een lagere telling: deze ronde faalde een Zoom-bron") in besluiten(w), besluiten(w)


def test_zoo01_wat_lager_is():
    """ZOO-01: lager is minder gesprekken, of van volledig naar minstens zonder meer gesprekken. Minstens 3 na 2 is nieuws
    naar boven en gaat door."""
    assert ZW.lager({"telling": "volledig", "gesprekken": 2}, {"telling": "ondergrens", "gesprekken": 2})
    assert ZW.lager({"telling": "ondergrens", "gesprekken": 2}, {"telling": "ondergrens", "gesprekken": 1})
    assert not ZW.lager({"telling": "volledig", "gesprekken": 2}, {"telling": "ondergrens", "gesprekken": 3})
    assert not ZW.lager({"telling": "ondergrens", "gesprekken": 2}, {"telling": "volledig", "gesprekken": 2})


@bord_nodig
def test_zoo01_grendel_ook_zonder_staat():
    """ZOO-01, de grendel zelf: is de staat weg (zoals na een herinstallatie) en valt S uit de bronnen, dan daalt de
    telling. Faalde deze ronde een bron, dan gaat de opgepakte regel niet terug, met een regel in het werkverslag."""
    w = Wereld(leesapp=False)
    w.zoom.geen_recht = dict(GEEN_RECHTEN)
    w.zoom.sessie("S", bxl("2026-10-20 17:00"), 30)
    assert w.ronde(NU) is None
    it, _ = w.dagregel("2026-10-20")
    w.bord.call(f"/api/klaarzet/{it['id']}/opgepakt", {"door": "dagbundelaar"})
    os.unlink(ZW.STAAT)
    # RZ6-01: zonder staat bewijst een eigen Fathom-opname in de vaste vergaderruimte de gebruiker, anders schrijft de
    # ronde niets en is er geen grendel te toetsen
    w.fathom_opname("zoo01", None, nummer=PMI, start=bxl("2026-10-21 08:00"), einde=bxl("2026-10-21 08:20"))
    w.zoom.sessie("S2", bxl("2026-10-21 10:00"), 30)
    assert w.ronde(datetime(2026, 10, 21, 13, 20, tzinfo=UTC)) is None
    na = w.bord.item("zoom:dag:2026-10-20")
    assert na["status"] == "opgepakt" and json.loads(na["inhoud"])["gesprekken"] == 1, na
    assert ("dag 2026-10-20", "dagregel niet herzien naar een lagere telling: deze ronde faalde een Zoom-bron") in besluiten(w), besluiten(w)


@bord_nodig
def test_zoo04_een_bestaande_rij_met_alleen_mehdi_telt_niet_meer():
    """ZOO-04, J10: voor een sessie met alleen Mehdi schrijft de ronde geen rij. Een rij die er al stond (van de oude
    Zoomwacht, met joinlink en toegangscode, of van een ronde waarin de deelnemers onbekend waren) telt daarna niet meer:
    dezelfde rij met link leeg, en dubbel_van buiten:alleen-mehdi. Er wordt niets verwijderd."""
    w = Wereld()
    w.bord.call("/api/gesprekken", {"rijen": [{"uniek": "zoom:meeting:alleen", "datum": "2026-10-19", "start": "14:00", "minuten": 20,
                                               "personen": "Mehdi Chegini", "thema": "Klant kwam niet", "prive": False,
                                               "link": "https://us06web.zoom.us/j/8300000003?pwd=geheim", "opgenomen_door": "Mehdi",
                                               "bron": "zoom"}]})
    voor = w.bord.rij("zoom:meeting:alleen")
    w.zoom.sessie("alleen", bxl("2026-10-19 14:00"), 20, nummer="8300000003", onderwerp="Klant kwam niet", deelnemers=[MEHDI_D, BOT_D])
    assert w.ronde(NU) is None
    rij = w.bord.rij("zoom:meeting:alleen")
    assert rij["link"] == "" and rij["dubbel_van"] == "buiten:alleen-mehdi", rij
    for veld in ("datum", "start", "minuten", "personen", "thema", "prive", "opgenomen_door", "bron"):
        assert rij[veld] == voor[veld], f"{veld} veranderde"
    assert tellend(w, "2026-10-19") == [] and w.dagregel("2026-10-19")[1]["alleen_mehdi"] == 1
    assert not w.bord.sql("SELECT uniek FROM gesprek_log WHERE link LIKE '%pwd=%'")
    # eerst zijn de deelnemers onbekend (de sessie telt, de rij komt er), later blijkt alleen Mehdi
    w = Wereld()
    w.zoom.sessie("solo", bxl("2026-10-20 10:00"), 20, deelnemers=[MEHDI_D, BOT_D])
    w.zoom.fout = {"/past_meetings/solo/participants"}
    assert w.ronde(NU) is None
    assert koppelvelden(w, "zoom:meeting:solo") == {"sessie": "zoom:meeting:solo", "dubbel_van": ""}
    w.zoom.fout = set()
    assert w.ronde(NU + timedelta(hours=6)) is None
    assert koppelvelden(w, "zoom:meeting:solo")["dubbel_van"] == "buiten:alleen-mehdi" and tellend(w, "2026-10-20") == []
    assert "Markering alleen Mehdi niet bevestigd" not in w.bord.noden()


def _leesapp_proef(env_regels):
    """Een tijdelijk .env-bestand voor zoom_leesapp.py, en de nabootsingen die het nodig heeft, zonder netwerk: elke
    vraag aan Zoom die niet nagebootst is, faalt hard. Geeft (ZL, env, herstel)."""
    import zoom_leesapp as ZL  # noqa: PLC0415
    map_ = tempfile.mkdtemp(prefix="leesapp-", dir=MAP)
    env = os.path.join(map_, ".env")
    with open(env, "w", encoding="utf-8") as f:
        f.write("".join(r + "\n" for r in env_regels))
    oud = {"ENV": ZL.ENV, "getpass": ZL.getpass.getpass, "eigen": ZL.eigen_nummer,
           **{n: getattr(Z, n, None) for n in ("rechten", "lees", "opnames", "download", "token_halen", "_toegang", "_vraag")},
           "best": Z._BESTANDEN, "lbest": Z._LEES_BESTANDEN}
    ZL.ENV = env
    Z._BESTANDEN, Z._LEES_BESTANDEN = (env,), (env,)
    Z._tokens.clear()
    Z._vraag = lambda *a, **k: (_ for _ in ()).throw(AssertionError("netwerk in een proef"))
    for k in [k for k in os.environ if k.startswith("ZOOM_")]:
        del os.environ[k]

    def herstel():
        ZL.ENV, ZL.getpass.getpass, ZL.eigen_nummer = oud["ENV"], oud["getpass"], oud["eigen"]
        for n in ("rechten", "lees", "opnames", "download", "token_halen", "_toegang", "_vraag"):
            if oud[n] is not None:
                setattr(Z, n, oud[n])
        Z._BESTANDEN, Z._LEES_BESTANDEN = oud["best"], oud["lbest"]
        Z._tokens.clear()
        for k in [k for k in os.environ if k.startswith("ZOOM_")]:
            del os.environ[k]
    return ZL, env, herstel


def _geen_token(*a, **k):
    raise Z.ZoomFout("geen token (HTTP 401)")


def test_zoo10_leesapp_schrijft_niets_zonder_token():
    """ZOO-10: --zet haalt eerst met de nieuwe waarden een token, in het geheugen. Komt er geen (een afgeknipt geheim),
    dan schrijft het niets in .env: anders las zoom.py met foute sleutels en was elke Zoom-bron 'fout: geen token'."""
    ZL, env, herstel = _leesapp_proef(["AGENTS_X=1", "ZOOM_ACCOUNT_ID=stack-account-1234"])
    try:
        voor = open(env, encoding="utf-8").read()
        ZL.getpass.getpass = lambda vraag: {"Account ID: ": "stack-account-1234", "Client ID: ": "lees-client-445566",
                                            "Client Secret: ": "afgeknipt-geheim"}[vraag]
        Z.token_halen = _geen_token
        Z._toegang = _geen_token
        uit = io.StringIO()
        with redirect_stdout(uit), redirect_stderr(uit):
            code = ZL.main(["--zet"])
        assert open(env, encoding="utf-8").read() == voor, "met een sleutel zonder token werd toch iets geschreven"
        assert code == 1 and uit.getvalue().strip().splitlines()[-1] == "niets geschreven: geen token met deze sleutels", uit.getvalue()
        assert "afgeknipt" not in uit.getvalue() and "lees-client" not in uit.getvalue()
    finally:
        herstel()


def test_zoo10_een_foute_sleutel_noemt_vervang():
    """ZOO-10: staan er foute sleutels, dan zegt de laatste regel van de toets hoe het verder moet (--zet --vervang). Een
    tweede --zet zonder --vervang zegt dat de sleutel er al staat met een andere waarde."""
    ZL, env, herstel = _leesapp_proef(["ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_LEES_CLIENT_ID=lees-client-445566",
                                       "ZOOM_LEES_CLIENT_SECRET=afgeknipt-geheim"])
    try:
        Z._toegang = _geen_token
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.toetsen() == 1
        assert uit.getvalue().strip().splitlines()[-1].endswith("opnieuw met --zet --vervang"), uit.getvalue()
        ZL.getpass.getpass = lambda vraag: {"Account ID: ": "stack-account-1234", "Client ID: ": "lees-client-445566",
                                            "Client Secret: ": "het-juiste-geheim"}[vraag]
        Z.token_halen = lambda cid, geheim, account: {"access_token": "x", "scope": ""}
        # RZ4-02: de eigenaar van de nieuwe app klopt, zodat --zet aan het schrijven toekomt
        ZL.eigen_nummer = lambda: PMI
        Z.lees = lambda pad, params=None, profiel="lees": {f"/meetings/{PMI}": {"host_id": "mehdi-id"}, "/users/me": {"id": "mehdi-id"}}[pad]
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.main(["--zet"]) == 1
        assert "ZOOM_LEES_CLIENT_SECRET: staat al, met een andere waarde (opnieuw met --zet --vervang)" in uit.getvalue(), uit.getvalue()
        assert "ZOOM_LEES_CLIENT_SECRET=afgeknipt-geheim" in open(env, encoding="utf-8").read()
        assert "geheim" not in uit.getvalue().replace("ZOOM_LEES_CLIENT_SECRET", "")
    finally:
        herstel()


@bord_nodig
def test_zoo10_leesapp_zonder_token_valt_terug_op_de_stack():
    """ZOO-10: staan de sleutels van de leesapp er maar geven ze geen token, dan leest de ronde met de app van de stack:
    'minstens N' in plaats van 'onbekend' en een gebroken keten, met een nood voor Mehdi."""
    w = Wereld()
    w.zoom.lees_token_fout = True
    w.zoom.geen_recht = dict(GEEN_RECHTEN)
    w.fathom_opname("690", w.zoom.sessie("pmr-a", bxl("2026-10-20 09:00"), 20))
    assert w.ronde(NU) is None
    it, inhoud = w.dagregel("2026-10-20")
    assert inhoud["telling"] == "ondergrens" and inhoud["gesprekken"] == 1, inhoud
    assert w.bord.noden().get("Zoom-leesapp geeft geen token: telling en vangnet zijn onvolledig") == "mehdi", w.bord.noden()
    assert w.bord.status()["status"] in ("klaar", "waakt")


@bord_nodig
def test_zoo09_een_gesprek_alleen_via_fathom_maakt_de_telling_onvolledig():
    """ZOO-09, Z5: een eigen opname met het nummer van de vaste ruimte zonder Zoom-sessie bewijst dat de telling onvolledig
    is: die dag is een ondergrens, met de reden erbij. Een dag zonder zo'n opname blijft volledig."""
    w = Wereld()
    w.fathom_opname("710", w.zoom.sessie("A", bxl("2026-10-20 09:00"), 30))
    w.zoom.sessie("L", bxl("2026-10-20 18:00"), 30)
    w.fathom_opname("711", None, start=bxl("2026-10-20 12:00"), einde=bxl("2026-10-20 12:40"))
    w.zoom.sessie("B", bxl("2026-10-19 09:00"), 30)
    assert w.ronde(NU) is None
    it, inhoud = w.dagregel("2026-10-20")
    assert inhoud["telling"] == "ondergrens" and inhoud["bronnen"]["onvolledig"] == ["gesprek alleen via Fathom gezien"], inhoud
    assert it["titel"].startswith("Zoom 20-10: minstens 3 gesprekken (telling onvolledig)"), it["titel"]
    assert w.dagregel("2026-10-19")[1]["telling"] == "volledig"


def oude_dagregels(w, dagen):
    """Dagregels zoals de oude Zoomwacht ze schreef (sleutel de datum, inhoud met berichten en meetings, geen telling),
    opgepakt door De Dagbundelaar."""
    for d in dagen:
        w.bord.call("/api/klaarzet", {"items": [{"van": "zoom-wacht", "voor": "mehdi", "soort": "zoom", "sleutel": d, "uniek": f"zoom:dag:{d}",
                                                 "titel": f"Zoom {d}: 4 berichten in 2 gesprek(ken), 1 meeting(s), 24 min",
                                                 "inhoud": {"datum": d, "berichten": 4, "gesprekken": 2, "prive_gesprekken": 0,
                                                            "meetings": 1, "meeting_minuten": 24, "werk": []}}]})
        w.bord.call(f"/api/klaarzet/{w.bord.item(f'zoom:dag:{d}')['id']}/opgepakt", {"door": "dagbundelaar"})


@bord_nodig
def test_zoo05_dagregel_in_de_oude_vorm():
    """ZOO-05: een dagregel in de oude vorm (met meetings, zonder telling) is een bekende telling. Kan de eerste ronde Zoom
    niet lezen, dan blijft ze staan. Daarna gaat de overgang naar de nieuwe vorm bewust met herziening (de oude getallen
    telden alleen geplande meetings), eenmalig en met een regel per dag in het werkverslag."""
    dagen = [f"2026-10-{d}" for d in range(14, 21)]
    w = Wereld(leesapp=False)
    oude_dagregels(w, dagen)
    w.zoom.token_fout = True
    assert isinstance(w.ronde(NU), RuntimeError)
    for d in dagen:
        it, inhoud = w.dagregel(d)
        assert it["status"] == "opgepakt" and "meetings" in inhoud and "telling" not in inhoud, (d, inhoud)
    assert not w.bord.sql("SELECT * FROM klaarzet_revisie")
    # RZ7-01: zonder gelezen Zoom-gebruiker schrijft de ronde helemaal niets, dus ook geen dagregel in de nieuwe vorm
    assert not w.bord.posts("/api/klaarzet"), "geen klaarzet zonder gelezen Zoom-gebruiker"
    w.zoom.token_fout = False
    assert w.ronde(NU + timedelta(hours=6)) is None
    herzien = sorted(r["uniek"] for r in w.bord.sql("SELECT uniek FROM klaarzet_revisie"))
    assert herzien == [f"zoom:dag:{d}" for d in dagen[1:]], herzien
    for d in dagen[1:]:
        assert (f"dag {d}", "dagregel van de oude vorm naar de nieuwe telling, eenmalig met herziening") in besluiten(w), d
    assert w.ronde(NU + timedelta(hours=7)) is None
    assert len(w.bord.sql("SELECT * FROM klaarzet_revisie")) == 6, "de overgang is eenmalig"


@bord_nodig
def test_zoo06_een_gewoon_woord_als_prive_onderwerp_verminkt_niets():
    """ZOO-06: het onderwerp van een privé geplande meeting ging naar het masker van het bord (zonder woordgrens). Was dat
    een gewoon woord ('Gesprek', 'Opname', 'Zoom'), dan werden de vaste teksten verminkt. Nu gaat alleen het onderwerp in
    de verwijzing weg; de rest blijft leesbaar."""
    for onderwerp in ("Gesprek", "Opname", "Zoom"):
        w = Wereld()
        s = w.zoom.sessie("g1", bxl("2026-10-20 14:00"), 20, nummer="8300000004", onderwerp=onderwerp, deelnemers=[MEHDI_D, NAAMGENOOT_D])
        w.zoom.opname(s, soorten=("MP4",), status="processing")
        assert w.ronde(NU) is None
        it, inhoud = w.dagregel("2026-10-20")
        assert it["titel"] == "Zoom 20-10: 1 gesprekken (0 met Fathom, 1 alleen in Zoom), 20 min; 0 chatgesprekken", (onderwerp, it["titel"])
        assert inhoud["stand"] == "voorlopig: opname in verwerking", (onderwerp, inhoud["stand"])
        assert all("(privé)" not in t for t in w.bord.noden()), (onderwerp, w.bord.noden())
    w = Wereld()
    s = een_sessie(w, nummer="8200000002", onderwerp="Zoom", deelnemers=[MEHDI_D, NAAMGENOOT_D])
    assert w.ronde(s["einde"] + timedelta(minutes=31)) is None
    it = w.bord.item("zoom-tekst:z24")
    assert it["verwijzing"] == os.path.join(ZW.ZOOM_DATA, f"2026-10-20 1000 Zoom (privé) [{ZW.achtervoegsel('z24')}]"), it["verwijzing"]
    assert it["titel"] == "2026-10-20 10:00 Zoom-gesprek, 30 min, alleen in Zoom · PRIVÉ", it["titel"]
    assert "Jan Proef" in ZW.ag._prive, "de namen van een privégesprek gaan wel naar het masker"
    # hetzelfde mechanisme in de chat: een privé-1:1 zonder naam heet 'gesprek', en dat woord ging naar het masker
    w = Wereld()
    w.zoom.chat = [({"type": "1:1", "peer_contact_email": "iemand@elders.test", "name": ""},
                    [{"date_time": "2026-10-20T08:00:00Z", "sender": "info@h-invest.test"}])]
    assert w.ronde(NU) is None
    assert w.dagregel("2026-10-20")[0]["titel"] == "Zoom 20-10: 0 gesprekken (0 met Fathom, 0 alleen in Zoom), 0 min; 1 chatgesprekken", \
        w.dagregel("2026-10-20")[0]["titel"]
    assert w.bord.rij("zoom:chat:iemand@elders.test:2026-10-20")["prive"] == 1


def _zoo08_zoom(host, eigenaar, nieuw=None):
    """Zoom voor de toets van de leesapp: de host van het eigen Fathom-nummer, de eigenaar van de stack-app (/users/me)
    en de eigenaar van de nieuwe app bij --zet (/users/me met het profiel nieuw, RZ4-02; standaard dezelfde)."""
    def lees(pad, params=None, profiel="lees"):
        if pad == "/users/me" and profiel == "stack":
            return {"id": eigenaar}
        if pad == "/users/me" and profiel == Z.NIEUW:
            return {"id": nieuw or eigenaar}
        if pad == f"/meetings/{PMI}":
            return {"host_id": host}
        if pad.startswith("/users/"):
            return {"id": pad.split("/")[2], "pmi": int(PMI)}
        raise AssertionError("onverwachte vraag " + pad)
    Z.lees = lees
    Z.rechten = lambda profiel="lees": set(__import__("zoom_leesapp").KERN)
    Z.opnames = lambda van, tot, profiel="lees": [{"bestanden": [{"id": "f1", "soort": "TRANSCRIPT", "status": "completed", "start": "x"}]}]
    Z.download = lambda bid, profiel="lees", max_bytes=0: b"WEBVTT"


def test_zoo08_leesapp_kiest_de_gebruiker_alleen_met_zet_en_alleen_de_eigenaar():
    """ZOO-08: ZOOM_MEHDI_USER kwam van de host van het meest voorkomende eigen Fathom-nummer, en de controle daarna
    vergeleek met hetzelfde nummer: een collega werd zo nooit afgekeurd. Nu moet die host de eigenaar van de stack-app
    zijn (/users/me, gemeten: Mehdi); anders schrijft het niets. En de toets zonder --zet schrijft nooit iets."""
    ZL, env, herstel = _leesapp_proef(["ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_LEES_CLIENT_ID=lees-client-445566",
                                       "ZOOM_LEES_CLIENT_SECRET=lees-geheim-112233"])
    try:
        ZL.eigen_nummer = lambda: PMI
        ZL.getpass.getpass = lambda vraag: {"Account ID: ": "stack-account-1234", "Client ID: ": "lees-client-445566",
                                            "Client Secret: ": "lees-geheim-112233"}[vraag]
        Z.token_halen = lambda cid, geheim, account: {"access_token": "x", "scope": ""}
        # 1. alleen toetsen: niets geschreven, ook niet de gebruiker
        _zoo08_zoom("mehdi-id", "mehdi-id")
        voor = open(env, encoding="utf-8").read()
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.main([]) == 1
        assert open(env, encoding="utf-8").read() == voor, "de toets zonder --zet schreef in .env"
        assert uit.getvalue().strip().splitlines()[-1] == "ontbreekt: ZOOM_MEHDI_USER (alleen met --zet)", uit.getvalue()
        # 2. de host is een collega, en de nieuwe app ook. Met --zet stopt het sinds de tegenproef op RZ4-02 al in
        # zetten(): de eigenaar van de nieuwe app is niet die van de app van de stack (het anker van ZOO-08). Niets
        # geschreven, ook geen ZOOM_MEHDI_USER.
        _zoo08_zoom("collega-id", "mehdi-id", nieuw="collega-id")
        voor = open(env, encoding="utf-8").read()
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.main(["--zet"]) == 1
        assert open(env, encoding="utf-8").read() == voor and "ZOOM_MEHDI_USER" not in voor
        assert uit.getvalue().strip().splitlines()[-1] == \
            "niets geschreven: de eigenaar van de nieuwe app is niet de eigenaar van de app van de stack", uit.getvalue()
        assert "collega-id" not in uit.getvalue() and "mehdi-id" not in uit.getvalue()
        # de eigen toets van ZOO-08 (gebruiker_zetten), met de sleutels al in .env: ook zij schrijft niets
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.main([]) == 1
        assert open(env, encoding="utf-8").read() == voor
        assert "gebruiker niet zeker" in uit.getvalue().strip().splitlines()[-1], uit.getvalue()
        assert "collega-id" not in uit.getvalue() and "mehdi-id" not in uit.getvalue()
        # 3. de host is de eigenaar: met --zet geschreven, en klaar
        _zoo08_zoom("mehdi-id", "mehdi-id")
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.main(["--zet"]) == 0, uit.getvalue()
        assert "ZOOM_MEHDI_USER=mehdi-id" in open(env, encoding="utf-8").read()
        assert uit.getvalue().strip().splitlines()[-1] == "klaar"
    finally:
        herstel()


def test_zoo08_users_me_mag_voor_de_vaste_gebruiker_gezet_is():
    """ZOO-08 en L5: om de gebruiker te toetsen leest zoom_leesapp.py /users/me van de stack, ook als ZOOM_MEHDI_USER al
    staat. Dat mag alleen voor de vaste gebruiker gezet is; daarna niet meer, en een ander gebruikers-id nooit."""
    os.environ["ZOOM_MEHDI_USER"] = "mehdi-id"
    try:
        Z.vastzetten(None)
        assert Z.toegestaan("/users/me") and Z.toegestaan("/users/mehdi-id")
        assert not Z.toegestaan("/users/ander-id") and not Z.toegestaan("/users/me/recordings")
        Z.vastzetten("mehdi-id")
        assert not Z.toegestaan("/users/me"), "na het vastzetten alleen nog de vaste gebruiker"
    finally:
        os.environ.pop("ZOOM_MEHDI_USER", None)
        Z.vastzetten(None)


def test_rz4_02_leesapp_schrijft_pas_na_de_eigenaarscontrole():
    """RZ4-02 (Codex RZ4-herstelcontrole, 22-10-2026): --zet bewaarde de sleutels in .env voor de eigenaar gecontroleerd
    was; pas de toets daarna keek naar de host van het eigen Fathom-nummer. Nu in deze volgorde, alles met de ingevoerde
    waarden in het geheugen (profiel nieuw van zoom.py: nooit een sleutel uit .env en nooit de app van de stack): een
    token, de rechten (een verboden recht: geweigerd, zonder een vraag aan Zoom), dan de eigenaar (de host van het meest
    voorkomende eigen Fathom-nummer is /users/me van de nieuwe app). Pas als dat klopt, schrijft het, atomisch met
    rechten 600. Anders schrijft het niets, is de exitcode niet nul en zegt de laatste regel waarom. Nooit een id of een
    sleutel op het scherm."""
    ZL, env, herstel = _leesapp_proef(["AGENTS_X=1", "ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_CLIENT_ID=stack-client",
                                       "ZOOM_CLIENT_SECRET=stack-geheim", "ZOOM_LEES_CLIENT_ID=oud-client-778899",
                                       "ZOOM_LEES_CLIENT_SECRET=oud-geheim-778899"])
    os.chmod(env, 0o644)
    nieuw = {"Account ID: ": "stack-account-1234", "Client ID: ": "nieuw-client-445566", "Client Secret: ": "nieuw-geheim-112233"}
    # wie /users/me is, per token: de oude leesapp in .env en de stack zijn van Mehdi, de nieuwe app van een collega
    eigenaar = {"tok-oud": "mehdi-id", "tok-stack": "mehdi-id", "tok-nieuw": "collega-id"}
    host = {"id": "mehdi-id"}
    rechten = {"tok-nieuw": " ".join(sorted(KERN_PROEF))}
    gevraagd = []

    def vraag(url, koppen, max_bytes=0):
        tok = koppen.get("Authorization", "")[len("Bearer "):]
        pad = urllib.parse.urlsplit(url).path[len("/v2"):]
        gevraagd.append((pad, tok))
        if pad == "/users/me" and eigenaar[tok] is None:
            return 500, "", b"{}"
        if pad == "/users/me":
            return 200, "", json.dumps({"id": eigenaar[tok]}).encode()
        if pad == f"/meetings/{PMI}" and host["id"] is None:
            return 400, "", json.dumps({"code": 4711, "message": "Invalid access token, does not contain scopes:"
                                                                 "[meeting:read:meeting:admin]."}).encode()
        if pad == f"/meetings/{PMI}":
            return 200, "", json.dumps({"host_id": host["id"]}).encode()
        raise AssertionError("onverwachte vraag " + pad)

    def token(cid, geheim, account):
        tok = {"nieuw-client-445566": "tok-nieuw", "oud-client-778899": "tok-oud"}.get(cid, "tok-stack")
        return {"access_token": tok, "scope": rechten.get(tok, " ".join(sorted(KERN_PROEF)))}

    def zet():
        """--zet --vervang zoals Mehdi het draait; geeft (exitcode, schermuitvoer)."""
        gevraagd.clear()
        Z._tokens.clear()
        uit = io.StringIO()
        with redirect_stdout(uit), redirect_stderr(uit):
            code = ZL.main(["--zet", "--vervang"])
        return code, uit.getvalue()
    try:
        Z._toegang, Z.lees, Z._vraag, Z.token_halen = ECHTE_TOEGANG, ECHTE_LEES, vraag, token
        ZL.getpass.getpass = lambda v: nieuw[v]
        ZL.eigen_nummer = lambda: PMI
        voor = open(env, encoding="utf-8").read()

        def niets_geschreven(uit, reden):
            assert uit.strip().splitlines()[-1] == f"niets geschreven: {reden}", uit
            assert open(env, encoding="utf-8").read() == voor, "er werd toch iets in .env geschreven"
            assert stat.S_IMODE(os.stat(env).st_mode) == 0o644, "het bestand werd vervangen"
            assert "nieuw" not in Z._tokens, "het token van de nieuwe sleutels blijft niet in het geheugen"
            for waarde in ("mehdi-id", "collega-id", "nieuw-client", "nieuw-geheim", "oud-geheim", "stack-account"):
                assert waarde not in uit, f"een waarde werd afgedrukt: {waarde}"
        # 0. het profiel nieuw zonder token leest niets: geen sleutel uit .env, geen terugval op de stack
        Z.vastzetten(None)
        try:
            Z.lees("/users/me", profiel="nieuw")
            raise AssertionError("lees() met het profiel nieuw zonder token las toch")
        except Z.ZoomFout:
            pass
        assert gevraagd == [], gevraagd
        # 1. de nieuwe app is van een collega: niets geschreven, ook al is de oude leesapp in .env van Mehdi
        code, uit = zet()
        assert code == 1, uit
        niets_geschreven(uit, "de eigenaar van de nieuwe app is niet de host van het eigen Fathom-nummer")
        assert {t for _, t in gevraagd} == {"tok-nieuw"}, f"de controle las niet met het nieuwe token: {gevraagd}"
        assert {p for p, _ in gevraagd} == {f"/meetings/{PMI}", "/users/me"}, gevraagd
        # 1b. tegenproef op RZ4-02 (22-10-2026), het geval van ZOO-08: het meest voorkomende eigen Fathom-nummer is de
        # ruimte van een collega en de nieuwe app is van die collega. Host en nieuwe app zijn dan gelijk, en tot hier
        # schreef --zet de sleutels. Het anker is de eigenaar van de app van de stack (gemeten: Mehdi); die is anders.
        host["id"], eigenaar["tok-nieuw"] = "collega-id", "collega-id"
        code, uit = zet()
        assert code == 1, uit
        niets_geschreven(uit, "de eigenaar van de nieuwe app is niet de eigenaar van de app van de stack")
        assert [p for p, t in gevraagd if t == "tok-stack"] == ["/users/me"], f"met de stack alleen /users/me: {gevraagd}"
        assert {t for _, t in gevraagd} == {"tok-nieuw", "tok-stack"}, gevraagd
        # 1c. de eigenaar van de app van de stack is niet te lezen: niet te controleren, niets geschreven
        host["id"], eigenaar["tok-nieuw"], eigenaar["tok-stack"] = "mehdi-id", "mehdi-id", None
        code, uit = zet()
        assert code == 1, uit
        niets_geschreven(uit, "eigenaar niet te controleren: eigenaar van de app van de stack onbekend (HTTP 500)")
        eigenaar["tok-stack"], eigenaar["tok-nieuw"] = "mehdi-id", "collega-id"
        # 2. geen eigen Fathom-nummer: de eigenaar is niet te controleren, dus niets geschreven en niets gevraagd
        ZL.eigen_nummer = lambda: ""
        code, uit = zet()
        assert code == 1 and gevraagd == [], (code, gevraagd)
        niets_geschreven(uit, "eigenaar niet te controleren: geen eigen opnames in het Fathom-archief")
        ZL.eigen_nummer = lambda: PMI
        # 3. de nieuwe app mag de meeting niet lezen: niet te controleren, niets geschreven
        eigenaar["tok-nieuw"], host["id"] = "mehdi-id", None
        code, uit = zet()
        assert code == 1, uit
        niets_geschreven(uit, "eigenaar niet te controleren (geen recht: meeting:read:meeting:admin)")
        # 4. een verboden recht: geweigerd voor er iets naar Zoom gaat
        host["id"], rechten["tok-nieuw"] = "mehdi-id", " ".join(sorted(KERN_PROEF)) + " meeting:write:meeting:admin"
        code, uit = zet()
        assert code == 1 and gevraagd == [], (code, gevraagd)
        niets_geschreven(uit, "verboden recht meeting:write:meeting:admin")
        # 5. de nieuwe app is van Mehdi en hij is de host: dan pas geschreven, atomisch met rechten 600
        rechten["tok-nieuw"] = " ".join(sorted(KERN_PROEF))
        gevraagd.clear()
        Z._tokens.clear()
        uit = io.StringIO()
        with redirect_stdout(uit), redirect_stderr(uit):
            assert ZL.zetten(vervang=True) is True, uit.getvalue()
        assert [p for p, t in gevraagd if t == "tok-stack"] == ["/users/me"], gevraagd
        assert {p for p, t in gevraagd if t == "tok-nieuw"} == {f"/meetings/{PMI}", "/users/me"}, gevraagd
        assert open(env, encoding="utf-8").read().splitlines() == [
            "AGENTS_X=1", "ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_CLIENT_ID=stack-client", "ZOOM_CLIENT_SECRET=stack-geheim",
            "ZOOM_LEES_CLIENT_ID=nieuw-client-445566", "ZOOM_LEES_CLIENT_SECRET=nieuw-geheim-112233"]
        assert stat.S_IMODE(os.stat(env).st_mode) == 0o600, oct(os.stat(env).st_mode)
        assert "nieuw" not in Z._tokens
        for waarde in ("mehdi-id", "nieuw-client", "nieuw-geheim"):
            assert waarde not in uit.getvalue(), f"een waarde werd afgedrukt: {waarde}"
    finally:
        herstel()
        Z.vastzetten(None)


# ------------------------------------------------------------- bouwcontrole RZ2 en de eigen punten (13.6) ---
NACHT = "2026-10-25"
EERSTE_UUR, TWEEDE_UUR = datetime(2026, 10, 25, 0, 30, tzinfo=UTC), datetime(2026, 10, 25, 1, 30, tzinfo=UTC)
# De definitieve lijst van rechten-zoomwacht-lezen.md v1 (22-10-2026): KERN voor de telling en het vangnet, de rest advies.
KERN_PROEF = frozenset({"user:read:user:admin", "meeting:read:meeting:admin", "meeting:read:list_meetings:admin",
                        "meeting:read:past_meeting:admin", "meeting:read:list_past_participants:admin",
                        "meeting:read:list_past_instances:admin", "report:read:user:admin",
                        "cloud_recording:read:list_user_recordings:admin", "cloud_recording:read:list_recording_files:admin",
                        "team_chat:read:list_user_sessions:admin"})
AANVINKEN_PROEF = KERN_PROEF | frozenset({
    "user:read:list_users:admin", "user:read:summary:admin", "user:read:settings:admin", "account:read:settings:admin",
    "account:read:lock_settings:admin", "meeting:read:list_templates:admin", "meeting:read:list_summaries:admin",
    "cloud_recording:read:list_account_recordings:admin", "cloud_recording:read:recording_settings:admin",
    "report:read:list_users:admin", "report:read:daily_usage:admin", "report:read:cloud_recording:admin",
    "report:read:user_activities:admin", "report:read:operation_logs:admin", "report:read:billing:admin",
    "report:read:list_history_meetings:admin", "dashboard:read:list_meetings:admin", "dashboard:read:client_versions:admin",
    "dashboard:read:chat:admin", "dashboard:read:ai_adoption:admin", "dashboard:read:ai_usage_trend:admin",
    "dashboard:read:ai_kpi:admin", "group:read:list_groups:admin", "group:read:list_members:admin", "group:read:settings:admin",
    "group:read:lock_settings:admin", "role:read:list_roles:admin", "role:read:list_members:admin", "role:read:role:admin",
    "team_chat:read:list_user_channels:admin", "team_chat:read:list_channels:admin", "team_chat:read:list_members:admin",
    "team_chat:read:retention:admin", "marketplace:read:list_apps:admin", "marketplace:read:app:admin",
    "marketplace:read:list_user_app_requests:admin", "billing:read:plan_information:admin", "billing:read:plan_usage:admin",
    "billing:read:list_invoices:admin", "zoom_rooms:read:list_rooms:admin", "webinar:read:list_webinars:admin",
    "h323_device:read:list_devices:admin", "contact_group:read:list_groups:admin", "tsp:read:tsp:admin",
    "tracking_field:read:list_tracking_fields:admin", "information_barrier:read:list_policies:admin"})
# RZ3-04 (22-10-2026): ook het Zoom-transcript staat onder Nooit aanvinken en wordt geweigerd zoals de andere, tot Mehdi
# over dat recht beslist. Tot dan gaf het alleen een melding en werkte de leesapp ermee verder.
TRANSCRIPT_RECHT = "cloud_recording:read:meeting_transcript:admin"
VERBODEN_PROEF = ("meeting:write:meeting:admin", "meeting:update:meeting:admin", "cloud_recording:delete:recording_file:admin",
                  "recording:write", "user:read:token:admin", "user:read:zak:admin", "zoom_rooms:read:virtual_controller:admin",
                  "meeting:read:local_archiving_token:admin", "team_chat:read:list_user_messages:admin",
                  "meeting:read:summary:admin", "aic:read:conversation_archives:admin", TRANSCRIPT_RECHT)
OUD_RECHT = "cloud_recording:read:" + "recording:admin"     # bestaat niet bij Zoom; zo staat de naam niet letterlijk hier


def twee_apps(lees_rechten):
    """Echte tokens per app: zoom._toegang draait echt, alleen het tokenantwoord is nagebootst. De leesapp krijgt
    'tok-lees' met deze rechten, de stack 'tok-stack' met schrijfrechten (de gedeelde app kan meer). Geeft het herstel."""
    oud = Z.token_halen
    Z._toegang = ECHTE_TOEGANG
    Z.token_halen = lambda cid, geheim, account: ({"access_token": "tok-lees", "scope": lees_rechten} if cid == "lees-proef" else
                                                  {"access_token": "tok-stack", "scope": "meeting:write:meeting:admin"})
    Z._tokens.clear()

    def herstel():
        Z.token_halen = oud
        Z._tokens.clear()
    return herstel


def test_rz2_05_een_brusselse_tijd_die_twee_keer_bestaat():
    """RZ2-05: op 25-10-2026 gaat de klok terug en bestaat 02:30 Brussel twee keer, om 00:30 en om 01:30 UTC. Een
    onleesbare gesprek.json (de mapnaam is Brusselse tijd) is een kandidaat voor een sessie in elk van die uren: tot nu
    las kandidaat() alleen het eerste uur, en dan heette een sessie in het tweede uur 'zonder Fathom'. Een tijd zonder
    UTC-bron geeft twee kandidaten, het eerste uur eerst; een gewone tijd een."""
    klok = datetime(2026, 10, 27, 7, 20, tzinfo=UTC)
    x = {"dag": NACHT, "tijd": "0235", "map": "m"}
    for start, verwacht in ((EERSTE_UUR, True), (TWEEDE_UUR, True), (datetime(2026, 10, 25, 5, 0, tzinfo=UTC), False)):
        assert ZW.kandidaat({"start": start, "einde": start + timedelta(minutes=20)}, x, klok) is verwacht, start
    assert ZW.utc_tijden(NACHT, "02:30") == [EERSTE_UUR, TWEEDE_UUR]
    assert ZW.utc_tijden("2026-10-20", "10:00") == [bxl("2026-10-20 10:00")]
    assert len(ZW.utc_tijden("2027-03-28", "02:30")) == 2, "een tijd die niet bestaat (de klok gaat vooruit) is ook dubbelzinnig"


@bord_nodig
def test_rz2_05_koppel_sinds_rond_het_terugzetten_van_de_klok():
    """RZ2-05: een oude rij kent alleen de Brusselse datum en tijd, en --koppel-sinds las 02:30 op 25-10 altijd als het
    eerste uur. Een rij uit het tweede uur koppelde dan niet en verloor haar link, of nam de opname van het eerste uur.
    Nu beslist de UTC-tijd van Fathom (recording_start_time): raakt maar een van de twee uren een opname met hetzelfde
    nummer, dan is dat het uur (een rij in het eerste en een in het tweede uur, elk met een eigen nummer). Kan Fathom het
    niet zeggen (twee rijen met het nummer van de vaste ruimte, een opname in elk uur), dan blijft de rij ongekoppeld,
    houdt ze haar link en staat er een regel in het werkverslag."""
    w = Wereld()
    assert ZW.brussel(EERSTE_UUR).strftime("%H:%M") == ZW.brussel(TWEEDE_UUR).strftime("%H:%M") == "02:30"
    for uniek, link in (("nacht-1", "https://us06web.zoom.us/j/8300000011"), ("nacht-2", "https://us06web.zoom.us/j/8300000012"),
                        ("pmr-1", f"https://us06web.zoom.us/j/{PMI}"), ("pmr-2", f"https://us06web.zoom.us/j/{PMI}?pwd=geheim")):
        w.bord.call("/api/gesprekken", {"rijen": [{"uniek": f"zoom:meeting:{uniek}", "datum": NACHT, "start": "02:30", "minuten": 20,
                                                   "personen": "Klant A, Mehdi", "afdeling": "unabo", "thema": "Overleg", "prive": False,
                                                   "zekerheid": "middel", "waarom": "oud", "link": link, "opgenomen_door": "Mehdi",
                                                   "bron": "zoom"}]})
    for rid, nummer, t in (("801", "8300000011", EERSTE_UUR), ("802", "8300000012", TWEEDE_UUR), ("803", PMI, EERSTE_UUR),
                           ("804", PMI, TWEEDE_UUR)):
        w.fathom_opname(rid, None, nummer=nummer, start=t + timedelta(seconds=40), einde=t + timedelta(minutes=20))
    w.zoom.meetings[PMI] = {"id": int(PMI), "type": 8}
    assert w.ronde(datetime(2026, 10, 27, 7, 20, tzinfo=UTC), "--koppel-sinds", "2026-10-24") is None
    assert koppelvelden(w, "zoom:meeting:nacht-1") == {"sessie": "zoom:meeting:nacht-1", "dubbel_van": "fathom:801"}
    assert koppelvelden(w, "zoom:meeting:nacht-2") == {"sessie": "zoom:meeting:nacht-2", "dubbel_van": "fathom:802"}, \
        ("de rij uit het tweede uur", koppelvelden(w, "zoom:meeting:nacht-2"))
    assert w.bord.rij("fathom:801")["sessie"] == "zoom:meeting:nacht-1" and w.bord.rij("fathom:802")["sessie"] == "zoom:meeting:nacht-2"
    assert w.bord.rij("zoom:meeting:nacht-1")["link"] == "" and w.bord.rij("zoom:meeting:nacht-2")["link"] == ""
    for uniek in ("pmr-1", "pmr-2"):
        rij = w.bord.rij(f"zoom:meeting:{uniek}")
        assert rij["dubbel_van"] == "" and rij["link"].startswith("https://us06web.zoom.us/j/"), ("ongekoppeld, met link", rij)
    assert w.bord.rij("fathom:803")["sessie"] == "" and w.bord.rij("fathom:804")["sessie"] == ""
    regel = f"{NACHT} 02:30: niet gekoppeld, die tijd bestaat twee keer in Brussel en Fathom zegt niet welk uur; de rij houdt haar link"
    assert [t for o, t in besluiten(w) if o == "koppel-sinds"] == [regel, regel], besluiten(w)
    assert "Koppeling met Fathom niet bevestigd" not in w.bord.noden(), w.bord.noden()
    assert "Een oude Zoom-link met toegangscode hoort bij een terugkerende meeting: de code geldt tot ze in Zoom verandert" \
        in w.bord.noden(), "L4 telt ook een rij die haar link houdt"


def _oude_rijen(w, rijen):
    for uniek, start, minuten in rijen:
        w.bord.call("/api/gesprekken", {"rijen": [{"uniek": f"zoom:meeting:{uniek}", "datum": NACHT, "start": start, "minuten": minuten,
                                                   "personen": "Klant A, Mehdi", "afdeling": "unabo", "thema": "Overleg", "prive": False,
                                                   "zekerheid": "middel", "waarom": "oud", "link": f"https://us06web.zoom.us/j/{PMI}",
                                                   "opgenomen_door": "Mehdi", "bron": "zoom"}]})


@bord_nodig
def test_rz2_05_fathom_beslist_alleen_als_de_keuze_uitsluitend_is():
    """Tegenproef RZ2-05 (22-10-2026): 'raakt maar een van de twee uren een opname met dit nummer' bewijst niets als rijen
    hetzelfde nummer delen (83% van de meetings zit in de vaste ruimte). (A) Twee rijen in de vaste ruimte om 02:30 en een
    opname in het tweede uur: Fathom weet niet welke rij het is. (B) 02:10 (60 min) en 02:40 (20 min) in dezelfde ruimte en
    een opname om 01:40 UTC: in het tweede uur overlappen de twee rijen, wat in een ruimte niet kan. Toen kreeg een rij
    willekeurig de opname en verloor de andere haar link zonder koppeling. Nu blijven alle betrokken rijen ongekoppeld,
    met hun link en een regel in het werkverslag. (C) Geeft Zoom de UTC-start van de sessie (/past_meetings/<uuid>), dan
    beslist die: de rij koppelt juist, en een rij die met haar zou overlappen, blijft ongekoppeld."""
    klok = datetime(2026, 10, 27, 7, 20, tzinfo=UTC)
    regel = lambda uur: f"{NACHT} {uur}: niet gekoppeld, die tijd bestaat twee keer in Brussel en Fathom zegt niet welk uur; de rij houdt haar link"  # noqa: E731
    # (A)
    w = Wereld()
    _oude_rijen(w, (("pmr-a", "02:30", 20), ("pmr-b", "02:30", 20)))
    w.fathom_opname("804", None, nummer=PMI, start=TWEEDE_UUR + timedelta(seconds=40), einde=TWEEDE_UUR + timedelta(minutes=20))
    assert w.ronde(klok, "--koppel-sinds", "2026-10-24") is None
    for uniek in ("pmr-a", "pmr-b"):
        rij = w.bord.rij(f"zoom:meeting:{uniek}")
        assert rij["dubbel_van"] == "" and rij["link"] == f"https://us06web.zoom.us/j/{PMI}", ("A: ongekoppeld, met link", rij)
    assert w.bord.rij("fathom:804")["sessie"] == "", w.bord.rij("fathom:804")
    assert [t for o, t in besluiten(w) if o == "koppel-sinds"] == [regel("02:30")] * 2, besluiten(w)
    # (B)
    w = Wereld()
    _oude_rijen(w, (("pmr-x", "02:10", 60), ("pmr-y", "02:40", 20)))
    w.fathom_opname("805", None, nummer=PMI, start=datetime(2026, 10, 25, 1, 40, tzinfo=UTC), einde=datetime(2026, 10, 25, 2, 0, tzinfo=UTC))
    assert w.ronde(klok, "--koppel-sinds", "2026-10-24") is None
    for uniek in ("pmr-x", "pmr-y"):
        rij = w.bord.rij(f"zoom:meeting:{uniek}")
        assert rij["dubbel_van"] == "" and rij["link"], ("B: ongekoppeld, met link", rij)
    assert w.bord.rij("fathom:805")["sessie"] == "", w.bord.rij("fathom:805")
    assert sorted(t for o, t in besluiten(w) if o == "koppel-sinds") == [regel("02:10"), regel("02:40")], besluiten(w)
    # (C) zoals A, maar Zoom kent de start van pmr-b: het tweede uur. Die sessie staat in geen lijst, alleen achter
    # /past_meetings/<uuid>, zodat de gewone ronde haar niet als nieuwe sessie telt.
    w = Wereld()
    _oude_rijen(w, (("pmr-a", "02:30", 20), ("pmr-b", "02:30", 20)))
    w.zoom.sessie("pmr-b", TWEEDE_UUR, 20, nummer="8300000099", rapport=(), instantie=False, gepland=False)
    w.fathom_opname("804", None, nummer=PMI, start=TWEEDE_UUR + timedelta(seconds=40), einde=TWEEDE_UUR + timedelta(minutes=20))
    assert w.ronde(klok, "--koppel-sinds", "2026-10-24") is None
    assert koppelvelden(w, "zoom:meeting:pmr-b") == {"sessie": "zoom:meeting:pmr-b", "dubbel_van": "fathom:804"}, koppelvelden(w, "zoom:meeting:pmr-b")
    assert w.bord.rij("zoom:meeting:pmr-b")["link"] == "" and w.bord.rij("fathom:804")["sessie"] == "zoom:meeting:pmr-b"
    a = w.bord.rij("zoom:meeting:pmr-a")
    assert a["dubbel_van"] == "" and a["link"], ("C: de andere rij blijft ongekoppeld, met link", a)
    assert [t for o, t in besluiten(w) if o == "koppel-sinds"] == [regel("02:30")], besluiten(w)


@bord_nodig
def test_eigen1_chat_altijd_met_de_app_van_de_stack():
    """EIGEN-1 (13.6): de leesapp krijgt team_chat:read:list_user_messages:admin bewust niet. Het tellen van chatberichten
    (/chat/users/<id>/sessions en /messages) gaat daarom altijd met de app van de stack, die dat recht al heeft. Tot nu
    ging het met de leesapp; met de definitieve rechten was de chat dan 'geen recht' en haar telling onbekend. zoom.py
    weigert /messages met de leesapp, zonder iets aan Zoom te vragen."""
    w = Wereld()
    herstel = twee_apps(" ".join(sorted(KERN_PROEF)))
    chat = []

    def vraag(url, koppen, max_bytes=2_000_000, echt=w.zoom.vraag):
        pad = urllib.parse.unquote(urllib.parse.urlsplit(url).path)
        if "/chat/" in pad:
            chat.append((pad.rsplit("/", 1)[1], koppen.get("Authorization")))
            if koppen.get("Authorization") == "Bearer tok-lees" and pad.endswith("/messages"):
                return NepZoom._weiger("team_chat:read:list_user_messages:admin")
        return echt(url, koppen, max_bytes)
    Z._vraag = vraag
    try:
        w.zoom.chat = [({"type": "1:1", "peer_contact_email": TEAM_ADRES, "name": "Proefpersoon Ypsilon"},
                        [{"date_time": "2026-10-20T08:00:00Z", "sender": "info@h-invest.test"},
                         {"date_time": "2026-10-20T08:05:00Z", "sender": TEAM_ADRES}])]
        w.fathom_opname("730", w.zoom.sessie("c1", bxl("2026-10-20 09:00"), 20))
        assert w.ronde(NU) is None
        assert sorted({d for d, _ in chat}) == ["messages", "sessions"] and {k for _, k in chat} == {"Bearer tok-stack"}, chat
        rij = w.bord.rij(f"zoom:chat:{TEAM_ADRES}:2026-10-20")
        assert rij and rij["thema"].startswith("Zoom-chat: 2 bericht(en), 1 van Mehdi"), rij
        assert w.dagregel("2026-10-20")[1]["chat"] == {"berichten": 2, "gesprekken": 1, "prive": 0}, w.dagregel("2026-10-20")[1]
        assert not [t for t in w.bord.noden() if t.startswith("Zoom-chat niet gelezen")], w.bord.noden()
        assert any(k.get("Authorization") == "Bearer tok-lees" for _, k in w.zoom.gevraagd), "de rest leest met de leesapp"
        # de grendel in zoom.py: chatberichten nooit met de leesapp
        Z.vastzetten("mehdi-id")
        n = len(w.zoom.gevraagd)
        for profiel in ("lees", None):
            try:
                Z.lees("/chat/users/mehdi-id/messages", {"to_contact": TEAM_ADRES}, **({"profiel": profiel} if profiel else {}))
                raise AssertionError(f"/messages met de leesapp ({profiel}) werd niet geweigerd")
            except Z.Geweigerd:
                pass
        assert len(w.zoom.gevraagd) == n, "een geweigerde vraag ging toch naar Zoom"
    finally:
        herstel()
        Z.vastzetten(None)


@bord_nodig
def test_chat_venster_met_datum_en_tijd():
    """Live gemeten 22-10-2026: met from en to als datum zonder tijd negeert Zoom het venster en geeft /messages alleen
    de laatste dag. De dagregels van 19 en 20-10 zeiden zo '0 chatgesprekken', terwijl Zoom met datum en tijd er 30 en 36
    berichten gaf. Nu vraagt De Zoomwacht het venster in UTC met tijd, en telt elke dag van het venster."""
    w = Wereld()
    w.zoom.chat = [({"type": "1:1", "peer_contact_email": TEAM_ADRES, "name": "Proefpersoon Ypsilon"},
                    [{"date_time": "2026-10-18T09:00:00Z", "sender": "info@h-invest.test"},
                     {"date_time": "2026-10-19T09:00:00Z", "sender": "info@h-invest.test"},
                     {"date_time": "2026-10-19T09:05:00Z", "sender": TEAM_ADRES},
                     {"date_time": "2026-10-20T10:00:00Z", "sender": TEAM_ADRES}])]
    assert w.ronde(NU) is None
    for dag, n in (("2026-10-18", 1), ("2026-10-19", 2), ("2026-10-20", 1)):
        rij = w.bord.rij(f"zoom:chat:{TEAM_ADRES}:{dag}")
        assert rij and rij["thema"].startswith(f"Zoom-chat: {n} bericht(en)"), (dag, rij)
        assert w.dagregel(dag)[1]["chat"]["berichten"] == n, (dag, w.dagregel(dag)[1])
    gevraagd = [dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query)) for u, _ in w.zoom.gevraagd
                if urllib.parse.urlsplit(u).path.endswith("/messages")]
    assert gevraagd and all(re.fullmatch(ZOOM_DT, q.get("from", "")) and re.fullmatch(ZOOM_DT, q.get("to", "")) for q in gevraagd), gevraagd


def test_eigen2_zoom_weigert_een_leestoken_met_een_verboden_recht():
    """EIGEN-2 (13.6) in zoom.py: een token van het profiel lees met een recht uit 'Nooit aanvinken' wordt geweigerd. Het
    wordt niet bewaard en gaat nooit naar Zoom; lees() leest dan met de app van de stack, en leesapp_verboden() noemt
    het recht. Sinds RZ3-04 hoort het Zoom-transcript daarbij (VERBODEN_PROEF), tot Mehdi over dat recht beslist; tot
    dan werd een token met dat recht aanvaard. De app van de stack valt er niet onder."""
    ZL, env, herstel = _leesapp_proef(["ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_CLIENT_ID=stack-client", "ZOOM_CLIENT_SECRET=stack-geheim",
                                       "ZOOM_LEES_CLIENT_ID=lees-client-445566", "ZOOM_LEES_CLIENT_SECRET=lees-geheim-112233"])
    try:
        Z._toegang = ECHTE_TOEGANG
        for recht in VERBODEN_PROEF:
            Z._tokens.clear()
            Z.vastzetten(None)
            Z.token_halen = lambda cid, geheim, account, r=recht: ({"access_token": "tok-lees", "scope": f"user:read:user:admin {r}"}
                                                                   if cid.startswith("lees") else
                                                                   {"access_token": "tok-stack", "scope": "meeting:write:meeting:admin"})
            try:
                Z._toegang("lees")
                raise AssertionError(f"een leestoken met {recht} werd aanvaard")
            except Z.VerbodenRecht as e:
                assert e.rechten == [recht] and recht in str(e) and "tok-" not in str(e), (recht, str(e))
            assert "lees" not in Z._tokens, "het geweigerde token wordt niet bewaard"
            gevraagd = []
            Z._vraag = lambda url, koppen, max_bytes=0, g=gevraagd: (g.append(koppen.get("Authorization")), (200, "", b'{"id": "mehdi-id"}'))[1]
            assert Z.lees("/users/me")["id"] == "mehdi-id"
            assert gevraagd == ["Bearer tok-stack"] and Z.leesapp_verboden() == [recht], (recht, gevraagd, Z.leesapp_verboden())
        Z._tokens.clear()
        Z.vastzetten(None)
        assert Z.leesapp_verboden() == [], "een nieuwe ronde begint zonder weigering"
        assert TRANSCRIPT_RECHT in Z.TOT_MEHDI_BESLIST and not hasattr(Z, "MELDEN_RECHTEN"), "RZ3-04: geen recht met alleen een melding"
        Z.token_halen = lambda cid, geheim, account: {"access_token": "tok-stack", "scope": "meeting:write:meeting:admin"}
        assert Z._toegang("stack") == "tok-stack", "de gedeelde app van de stack valt niet onder de lijst"
    finally:
        herstel()
        Z.vastzetten(None)


@bord_nodig
def test_eigen2_zoomwacht_met_een_geweigerde_leesapp():
    """EIGEN-2 in de ronde: een leesapp met een verboden recht wordt geweigerd. De ronde leest met de app van de stack,
    het token van de leesapp gaat nooit naar Zoom, en Mehdi krijgt een nood die zegt wat er mis is; de naam van het recht
    staat in het werkverslag."""
    w = Wereld()
    herstel = twee_apps(" ".join(sorted(KERN_PROEF)) + " meeting:write:meeting:admin")
    try:
        w.fathom_opname("740", w.zoom.sessie("v1", bxl("2026-10-20 09:00"), 20))
        assert w.ronde(NU) is None
    finally:
        herstel()
    assert {k.get("Authorization") for _, k in w.zoom.gevraagd if k} == {"Bearer tok-stack"}, {k.get("Authorization") for _, k in w.zoom.gevraagd}
    assert w.bord.noden().get("Zoom-leesapp geweigerd: ze heeft een recht dat ze nooit mag hebben; telling en vangnet zijn "
                              "onvolledig") == "mehdi", w.bord.noden()
    assert "Zoom-leesapp geeft geen token: telling en vangnet zijn onvolledig" not in w.bord.noden()
    assert "meeting:write:meeting:admin" in json.dumps(w.bord.posts("/api/logboek")), "het werkverslag noemt het recht"
    Z.vastzetten(None)


def test_eigen2_leesapp_kern_advies_en_verboden_rechten():
    """EIGEN-2 (13.6, rechten-zoomwacht-lezen.md v1): zoom_leesapp.py toetst de rechten tegen de definitieve lijst. KERN is
    nodig voor de telling en het vangnet en bepaalt de exitcode; ADVIES (de rest, voor de latere accountscan) meldt hij per
    recht als aanwezig of ontbreekt. Heeft het token een recht uit 'Nooit aanvinken', dan weigert hij te werken: exit
    niet-nul met de naam, niets geschreven en niets verder getoetst. Het Zoom-transcript ook (RZ3-04), en dan zegt de
    melding dat het geweigerd blijft tot Mehdi beslist. Het recht dat bij Zoom niet bestaat, is overal weg. Tot nu stond
    team_chat:read:list_user_messages:admin bij de nodige rechten en toetste niets een verboden recht."""
    import zoom_leesapp as ZL  # noqa: PLC0415
    assert set(ZL.KERN) == KERN_PROEF and len(ZL.KERN) == len(KERN_PROEF), ZL.KERN
    assert set(ZL.KERN) | set(ZL.ADVIES) == AANVINKEN_PROEF and not set(ZL.KERN) & set(ZL.ADVIES), set(ZL.ADVIES) ^ (AANVINKEN_PROEF - KERN_PROEF)
    assert len(ZL.ADVIES) == len(set(ZL.ADVIES)) == len(AANVINKEN_PROEF) - len(KERN_PROEF)
    assert not Z.verboden(AANVINKEN_PROEF), Z.verboden(AANVINKEN_PROEF)
    assert [r for r in VERBODEN_PROEF if Z.verboden({r}) != [r]] == [], "elk verboden recht wordt herkend"
    assert Z.verboden({TRANSCRIPT_RECHT}) == [TRANSCRIPT_RECHT] and TRANSCRIPT_RECHT in Z.TOT_MEHDI_BESLIST
    assert Z.TOT_MEHDI_BESLIST <= Z.VERBODEN_RECHTEN, "wat op Mehdi wacht, wordt geweigerd zoals de rest"
    for pad in ("zoom_leesapp.py", "zoom_wacht.py", os.path.join("koppelingen", "zoom.py")):
        assert OUD_RECHT not in open(os.path.join(RUNNER, pad), encoding="utf-8").read(), pad
    ZL, env, herstel = _leesapp_proef(["ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_LEES_CLIENT_ID=lees-client-445566",
                                       "ZOOM_LEES_CLIENT_SECRET=lees-geheim-112233", "ZOOM_MEHDI_USER=mehdi-id"])
    try:
        ZL.eigen_nummer = lambda: PMI
        _zoo08_zoom("mehdi-id", "mehdi-id")
        gelezen, lees = [], Z.lees
        Z.lees = lambda pad, params=None, profiel="lees": (gelezen.append(pad), lees(pad, params, profiel))[1]
        voor = open(env, encoding="utf-8").read()

        def toets(rechten, *argv):
            Z.rechten = lambda profiel="lees": set(rechten)
            gelezen.clear()
            uit = io.StringIO()
            with redirect_stdout(uit):
                code = ZL.main(list(argv))
            return code, uit.getvalue().strip().splitlines()
        # 1. alleen de kern: klaar, en elk advies apart als ontbreekt
        code, regels = toets(KERN_PROEF)
        assert code == 0 and regels[-1] == "klaar", regels[-3:]
        assert all(f"recht {r}: aanwezig" in regels for r in KERN_PROEF)
        assert all(f"recht {r}: ontbreekt (advies)" in regels for r in AANVINKEN_PROEF - KERN_PROEF), regels
        code, regels = toets(AANVINKEN_PROEF)
        assert code == 0 and all(f"recht {r}: aanwezig (advies)" in regels for r in AANVINKEN_PROEF - KERN_PROEF)
        # 2. een recht van de kern ontbreekt
        code, regels = toets(KERN_PROEF - {"report:read:user:admin"})
        assert code == 1 and regels[-1] == "ontbreekt: report:read:user:admin", regels[-1]
        # 3. een verboden recht: geweigerd, met de naam, en niets verder gevraagd of geschreven
        for recht in VERBODEN_PROEF:
            code, regels = toets(KERN_PROEF | {recht})
            assert code != 0 and regels[-1].startswith("geweigerd: ") and recht in regels[-1], (recht, regels[-1])
            assert not gelezen, (recht, gelezen)
        # 4. het Zoom-transcript (RZ3-04): geweigerd zoals de andere, en de melding zegt dat het wacht op Mehdi
        code, regels = toets(KERN_PROEF | {TRANSCRIPT_RECHT})
        assert code != 0 and regels[-1].startswith("geweigerd: ") and TRANSCRIPT_RECHT in regels[-1], regels[-1]
        assert regels[-1].endswith("; dat recht blijft geweigerd tot Mehdi erover beslist"), regels[-1]
        assert not gelezen, gelezen
        code, regels = toets(KERN_PROEF | {"user:read:zak:admin"})
        assert "Mehdi" not in regels[-1], "een recht dat nooit mag, wacht niet op Mehdi"
        # 5. de echte weg: zoom.py weigert het token, de toets noemt het recht
        Z.rechten, Z._toegang = ECHTE_RECHTEN, ECHTE_TOEGANG
        Z._tokens.clear()
        Z.token_halen = lambda cid, geheim, account: {"access_token": "x", "scope": " ".join(sorted(KERN_PROEF)) + " user:read:zak:admin"}
        uit = io.StringIO()
        with redirect_stdout(uit):
            code = ZL.main([])
        laatste = uit.getvalue().strip().splitlines()[-1]
        assert code != 0 and laatste.startswith("geweigerd: ") and "user:read:zak:admin" in laatste, laatste
        # 6. --zet met nieuwe sleutels die zo'n token geven: niets geschreven
        ZL.getpass.getpass = lambda vraag: {"Account ID: ": "stack-account-1234", "Client ID: ": "lees-client-445566",
                                            "Client Secret: ": "nieuw-geheim-998877"}[vraag]
        uit = io.StringIO()
        with redirect_stdout(uit):
            code = ZL.main(["--zet", "--vervang"])
        laatste = uit.getvalue().strip().splitlines()[-1]
        assert code != 0 and laatste.startswith("niets geschreven: ") and "user:read:zak:admin" in laatste, laatste
        assert open(env, encoding="utf-8").read() == voor, "met een verboden recht werd toch iets geschreven"
        assert "nieuw-geheim" not in uit.getvalue() and "lees-geheim" not in uit.getvalue()
        # 7. --zet met een token met het Zoom-transcript (RZ3-04): niets geschreven, en de melding noemt Mehdi
        Z._tokens.clear()
        Z.token_halen = lambda cid, geheim, account: {"access_token": "x", "scope": " ".join(sorted(KERN_PROEF | {TRANSCRIPT_RECHT}))}
        uit = io.StringIO()
        with redirect_stdout(uit):
            code = ZL.main(["--zet", "--vervang"])
        laatste = uit.getvalue().strip().splitlines()[-1]
        assert code != 0 and laatste == f"niets geschreven: verboden recht {TRANSCRIPT_RECHT}; dat recht blijft geweigerd tot " \
            "Mehdi erover beslist", laatste
        assert open(env, encoding="utf-8").read() == voor, "met het Zoom-transcript werd toch iets geschreven"
    finally:
        herstel()
        Z.vastzetten(None)


def test_rz3_04_proefdownload_zonder_het_transcriptrecht():
    """RZ3-04 in zoom_leesapp.py: het Zoom-transcript wordt geweigerd tot Mehdi beslist. Weigert Zoom de download van het
    transcript op dat recht (400 met code 4711, of 401 of 403 met dat recht in de melding), dan zegt de proefdownload dat
    in die woorden, noemt een melding het recht, en is de exitcode niet nul. Langs de echte download() van zoom.py, met de
    grendels L1 en L5; alleen het antwoord van Zoom is nagebootst. Nooit een url op het scherm.
    Tegenproef van 22-10-2026: de proefdownload mat niet welk recht ontbrak. download() gooide de naam uit de melding van
    Zoom weg, en elke weigering heette 'een recht dat Mehdi nog niet toestond': ook een ander recht dat wel aangevinkt mag
    worden, en een ongeldig token (401, Zoom-code 124). Zo stuurde de melding Mehdi op een gok naar een recht onder Nooit
    aanvinken. Nu noemt ze het recht dat Zoom noemt, en Mehdi alleen voor het transcriptrecht."""
    ZL, env, herstel = _leesapp_proef(["ZOOM_ACCOUNT_ID=stack-account-1234", "ZOOM_LEES_CLIENT_ID=lees-client-445566",
                                       "ZOOM_LEES_CLIENT_SECRET=lees-geheim-112233", "ZOOM_MEHDI_USER=mehdi-id"])
    url = "https://proef.zoom.us/rec/download/f1"
    ander = "cloud_recording:read:list_recording_files:admin"

    def weiger(http, scope):
        return http, "", json.dumps({"code": 4711, "message": f"Invalid access token, does not contain scopes:[{scope}]."}).encode()
    try:
        ZL.eigen_nummer = lambda: PMI
        _zoo08_zoom("mehdi-id", "mehdi-id")
        Z.download, Z._toegang = ECHTE_DOWNLOAD, ECHTE_TOEGANG
        Z.token_halen = lambda cid, geheim, account: {"access_token": "x", "scope": " ".join(sorted(KERN_PROEF))}
        Z.opnames = lambda van, tot, profiel="lees": (Z._DOWNLOADS.__setitem__("f1", url),
                                                       [{"bestanden": [{"id": "f1", "soort": "TRANSCRIPT", "status": "completed",
                                                                        "start": "x"}]}])[1]
        for naam, antwoord, soort in (("4711 met het transcriptrecht", weiger(400, TRANSCRIPT_RECHT), "mehdi"),
                                      ("403 met het transcriptrecht", weiger(403, TRANSCRIPT_RECHT), "mehdi"),
                                      ("4711 met een ander recht", weiger(400, ander), "ander"),
                                      ("401 met Zoom-code 124", (401, "", b'{"code": 124, "message": "Invalid access token."}'), "geen"),
                                      ("403 zonder tekst", (403, "", b""), "geen")):
            gevraagd = []
            Z._vraag = lambda u, koppen, max_bytes=0, a=antwoord, g=gevraagd: (g.append(u), a)[1]
            uit = io.StringIO()
            with redirect_stdout(uit):
                code = ZL.main([])
            regels = uit.getvalue().strip().splitlines()
            assert gevraagd == [url] and code == 1, (naam, gevraagd, code)
            if soort == "mehdi":
                assert "proefdownload van een Zoom-transcript: nee (download van het transcript vraagt een recht dat Mehdi nog " \
                       "niet toestond)" in regels, (naam, regels)
                assert f"melding: het vangnet vraagt {TRANSCRIPT_RECHT}; dat recht staat onder Nooit aanvinken en blijft " \
                       "geweigerd tot Mehdi erover beslist" in regels, (naam, regels)
                assert regels[-1] == "ontbreekt: recht voor de download van het transcript (Mehdi beslist)", (naam, regels[-1])
            elif soort == "ander":
                assert f"proefdownload van een Zoom-transcript: nee (download vraagt recht {ander})" in regels, (naam, regels)
                assert regels[-1] == f"ontbreekt: {ander}" and "Mehdi" not in uit.getvalue(), (naam, uit.getvalue())
            else:
                assert f"proefdownload van een Zoom-transcript: nee (download geweigerd, HTTP {antwoord[0]}" \
                       f"{', Zoom-code 124' if antwoord[0] == 401 else ''}; Zoom noemde geen recht)" in regels, (naam, regels)
                assert regels[-1] == "ontbreekt: proefdownload van een Zoom-transcript", (naam, regels[-1])
                assert "Mehdi" not in uit.getvalue() and TRANSCRIPT_RECHT not in uit.getvalue(), (naam, uit.getvalue())
            assert "proef.zoom.us" not in uit.getvalue() and "/rec/" not in uit.getvalue(), "geen url op het scherm"
        # een andere fout bij de download is geen recht dat op Mehdi wacht
        Z._vraag = lambda u, koppen, max_bytes=0: (500, "", b"")
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.main([]) == 1
        assert "proefdownload van een Zoom-transcript: nee (download: HTTP 500)" in uit.getvalue(), uit.getvalue()
        assert "Mehdi" not in uit.getvalue(), uit.getvalue()
        # met de download in orde: klaar
        Z._vraag = lambda u, koppen, max_bytes=0: (200, "", b"WEBVTT")
        uit = io.StringIO()
        with redirect_stdout(uit):
            assert ZL.main([]) == 0, uit.getvalue()
        assert "proefdownload van een Zoom-transcript: ja (HTTP 200)" in uit.getvalue(), uit.getvalue()
    finally:
        herstel()
        Z.vastzetten(None)


@bord_nodig
def test_rz3_04_zoomwacht_zonder_downloadrecht_zet_een_nood_en_crasht_niet():
    """RZ3-04 in de ronde: het vangnet moet de Zoom-tekst ophalen, en Zoom weigert de download (403, het recht voor het
    transcript is niet toegestaan). De ronde crasht niet: geen map, geen tekst, de sessie telt mee met toestand onbekend,
    en Mehdi krijgt een nood. De volgende ronde probeert opnieuw, zonder een tweede nood."""
    w = Wereld()
    s = een_sessie(w)
    echt, geweigerd = Z._vraag, []
    Z._vraag = lambda u, koppen, max_bytes=2_000_000: ((geweigerd.append(u), (403, "", b'{"code": 124, "message": "proef"}'))[1]
                                                       if "/rec/download/" in u else echt(u, koppen, max_bytes))
    try:
        fout = w.ronde(s["einde"] + timedelta(minutes=31))
        assert fout is None, fout
        assert len(geweigerd) == 1 and not w.vangnetmappen(), (geweigerd, w.vangnetmappen())
        assert w.bord.noden().get("Zoom-tekst niet op te halen: de leesapp mist het downloadrecht voor opnames") == "mehdi", \
            w.bord.noden()
        assert w.bord.status()["status"] in ("klaar", "waakt"), w.bord.status()
        assert w.bord.rij("zoom:meeting:z24") and not w.bord.item("zoom-tekst:z24"), "de sessie telt, zonder tekst"
        fout = w.ronde(s["einde"] + timedelta(minutes=45))
        assert fout is None and len([t for t in w.bord.noden() if t.startswith("Zoom-tekst niet op te halen")]) == 1, w.bord.noden()
    finally:
        Z._vraag = echt


def test_eigen3_eigen_account_alleen_op_een_exact_adres():
    """EIGEN-3: 'eigen account' op een exact adres, nooit op een deel. Een plek: MEHDI_FATHOM_ADRESSEN in
    koppelingen/fathom.py, uit FATHOM_MEHDI_ADRESSEN met een standaard in de code (gemeten op de VM: elke eigen opname
    heeft een van die adressen, de andere 177 het adres van een ander account). Tot nu herkende De Zoomwacht het eigen
    account aan deelstukken van De Fathomwacht ('h-architects', 'mch@'): de opname van een collega met een adres op het
    domein van het kantoor telde als die van Mehdi, kreeg voorrang bij het koppelen en telde zonder hem in de sessie.
    Tegenproef van 22-10-2026: ook De Fathomwacht (sleutel_nood) zocht nog op die deelstukken, met een eigen lijst en een
    eigen naam in .env; een opname van een collega dempte zo de nood over Mehdi's eigen Fathom-sleutel. Nu leest ook zij
    de ene lijst. De proef zet FATHOM_MEHDI_ADRESSEN op verzonnen adressen (kantoor.test staat voor het domein van het
    kantoor) en toetst de standaard uit de code zonder ze te noemen."""
    import fathom as F  # noqa: PLC0415
    assert F.MEHDI_FATHOM_ADRESSEN == frozenset({EIGEN_ADRES, WERK_ADRES}), F.MEHDI_FATHOM_ADRESSEN
    g = {"recording_id": 1, "recording_start_time": "2026-10-20T08:00:00Z", "recording_end_time": "2026-10-20T08:30:00Z",
         "meeting_url": f"https://us06web.zoom.us/j/{PMI}"}
    for email, eigen in (("collega@kantoor.test", False), ("xmch@elders.example", False), ("mch@ander-domein.example", False),
                         ("mch@kantoor.test.example", False), ("jan@kantoor-partner.example", False), ("", False),
                         (ANDER_ADRES, False), (" MCH@Kantoor.TEST ", True), (EIGEN_ADRES, True),
                         ("Eigen@Mehdi.Test", True)):
        assert ZW.opname_uit(dict(g, recorded_by={"email": email}))["eigen"] is eigen, email
    zw = open(os.path.join(RUNNER, "zoom_wacht.py"), encoding="utf-8").read()
    assert "MEHDI_FATHOM_EIGENAARS" not in zw and "fathom.MEHDI_FATHOM_ADRESSEN" in zw, "De Zoomwacht leest de ene lijst"
    fw = open(os.path.join(RUNNER, "fathom_wacht.py"), encoding="utf-8").read()
    assert "MEHDI_FATHOM_EIGENAARS" not in fw and "FATHOM_MEHDI_EIGENAARS" not in fw and "fathom.MEHDI_FATHOM_ADRESSEN" in fw, \
        "De Fathomwacht leest dezelfde lijst, zonder eigen naam in .env"
    # De Fathomwacht: alleen een opname van een exact eigen adres bewijst de sleutel (volle venster: anders de nood)
    oud_dagen, ZW.fw.DAGEN = ZW.fw.DAGEN, ZW.fw.STANDAARD_DAGEN
    try:
        for email, nood in (("collega@kantoor.test", True), ("xmch@elders.example", True), (ANDER_ADRES, True),
                            (" Eigen@Mehdi.TEST ", False), (WERK_ADRES, False)):
            uit = ZW.fw.sleutel_nood([{"recorded_by": {"email": email}}])
            assert uit == ([{"tekst": ZW.fw.SLEUTEL_NOOD, "wie": "mehdi"}] if nood else []), (email, uit)
    finally:
        ZW.fw.DAGEN = oud_dagen
    # de omgeving bepaalt de lijst; zonder waarde geldt de standaard uit de code: twee volle adressen in kleine letters,
    # precies die uit de bron (de proef leest ze daar en schrijft ze nergens zelf)
    bron = open(os.path.join(RUNNER, "koppelingen", "fathom.py"), encoding="utf-8").read()
    m = re.search(r'os\.environ\.get\("FATHOM_MEHDI_ADRESSEN"\) or\s+"([^"]+)"', bron)
    assert m, "de standaard van FATHOM_MEHDI_ADRESSEN staat niet meer in koppelingen/fathom.py"
    standaard = {a.strip().lower() for a in m.group(1).split(",") if a.strip()}
    assert len(standaard) == 2 and all(re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9-]+(\.[a-z0-9-]+)+", a) for a in standaard), \
        "de standaard is twee volle adressen, nooit een deelstuk"
    oud = os.environ.get("FATHOM_MEHDI_ADRESSEN")
    try:
        for waarde, verwacht in ((" Ander@Voorbeeld.test , x@y.test,", {"ander@voorbeeld.test", "x@y.test"}), ("", standaard)):
            os.environ["FATHOM_MEHDI_ADRESSEN"] = waarde
            spec = importlib.util.spec_from_file_location("fathom_proef", os.path.join(RUNNER, "koppelingen", "fathom.py"))
            M = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(M)
            assert M.MEHDI_FATHOM_ADRESSEN == frozenset(verwacht), waarde
    finally:
        if oud is None:
            os.environ.pop("FATHOM_MEHDI_ADRESSEN", None)
        else:
            os.environ["FATHOM_MEHDI_ADRESSEN"] = oud


if __name__ == "__main__":
    import traceback
    goed = fout = over = 0
    for naam, f in sorted(globals().items()):
        if naam.startswith("test_") and callable(f):
            try:
                with redirect_stderr(io.StringIO()):
                    f()
                goed += 1
                print(f"   geslaagd  {naam}")
            except Overgeslagen as e:
                over += 1
                print(f"   overgeslagen  {naam} ({e})")
            except Exception:  # noqa: BLE001
                fout += 1
                print(f"   GEFAALD   {naam}")
                traceback.print_exc()
    print(f"{goed} goed, {fout} fout" + (f", {over} overgeslagen" if over else ""))
    sys.exit(1 if fout else 0)
