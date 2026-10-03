"""Grendel op de wijzigingswacht (agenda_signaal.py), audit 02-10-2026, fouten A4 tot A8.

A4  alle pagina's van Google lezen, niet alleen de eerste 250.
A5  pas afvinken na een volledige lezing en een geslaagde verwerking; een mislukte dag blijft open, met een
    begrensd aantal pogingen; de stand wordt atomair geschreven.
A6  een wacht die faalt (exitcode, time-out) heet mislukt, op stderr, en het script eindigt niet met 0.
A7  een verplaatsing plant ook de oude dag (zelfde agenda, andere agenda, reeksinstantie).
A8  een geschrapte afspraak zonder start plant de dag uit de bewaarde vingerafdruk.

Geen netwerk en geen echte wacht: urllib.request.urlopen en subprocess.run zijn nagemaakt op het module-object,
de stand staat in een tijdelijke map. Een test belt nooit en schrijft nooit in een agenda.
"""
import contextlib
import fcntl
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"      # een test belt nooit echt (FR-55)

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_signaal as S          # noqa: E402

# Nooit de echte stand op de VM en nooit de echte wacht, ook niet als een nagemaakte functie ontbreekt
S.STAND = Path(tempfile.mkdtemp(prefix="signaal-")) / "agenda-signaal.json"
S.CONTROLEPUNTEN = S.STAND.parent / "controlepunten.json"     # nooit de echte datamap
S.PYTHON = "/usr/bin/false"

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def dag(n):
    return (date.today() + timedelta(days=n)).isoformat()


def nu_iso(min_=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=min_)).isoformat()


def ev(eid, d, titel="Mehdi: [HARC-KB] 2505 - klant", bijgewerkt=None, **meer):
    e = {"id": eid, "summary": titel, "status": "confirmed", "updated": bijgewerkt or nu_iso(-5),
         "start": {"dateTime": f"{d}T10:00:00+02:00"}, "end": {"dateTime": f"{d}T11:00:00+02:00"}}
    e.update(meer)
    return e


class NepGoogle:
    """Nagemaakte events-lijst die zich gedraagt als Google: updatedMin, maxResults, pageToken, en
    nextPageToken alleen als het in `fields` gevraagd is."""

    def __init__(self):
        self.items = {}         # kalender -> lijst afspraken
        self.fout = {}          # kalender -> paginanummers die HTTP 500 geven
        self.vragen = []

    def __call__(self, req, timeout=None, *a, **k):
        url = getattr(req, "full_url", req)
        u = urllib.parse.urlparse(url)
        kal = urllib.parse.unquote(u.path.split("/calendars/")[1].split("/events")[0])
        q = dict(urllib.parse.parse_qsl(u.query))
        self.vragen.append((kal, q))
        pagina = int(q.get("pageToken", "0"))
        if pagina in self.fout.get(kal, ()):
            raise urllib.error.HTTPError(url, 500, "Backend Error", {}, None)
        sinds = datetime.fromisoformat(q["updatedMin"])
        lijst = [e for e in self.items.get(kal, []) if datetime.fromisoformat(e["updated"]) >= sinds]
        n = int(q.get("maxResults", "250"))
        d = {"items": lijst[pagina * n:(pagina + 1) * n]}
        if (pagina + 1) * n < len(lijst) and "nextPageToken" in q.get("fields", "nextPageToken"):
            d["nextPageToken"] = str(pagina + 1)
        return io.BytesIO(json.dumps(d).encode())


class NepWacht:
    """Nagemaakte agenda_wacht.py --dag: onthoudt welke dagen gestart werden en geeft de gevraagde exitcode."""

    def __init__(self):
        self.dagen = []
        self.rc = {}            # dag -> exitcode
        self.uitzondering = None

    def __call__(self, args, *a, **k):
        d = args[args.index("--dag") + 1]
        self.dagen.append(d)
        if self.uitzondering:
            raise self.uitzondering
        rc = self.rc.get(d, 0)
        return subprocess.CompletedProcess(args, rc, "  [schrijf] reistijd: 1 gezet\n",
                                           "" if rc == 0 else "Traceback (most recent call last):\nRuntimeError: quota op\n")


def t(iso):
    return datetime.fromisoformat(iso)


def nieuwe_stand():
    S.STAND = Path(tempfile.mkdtemp(prefix="signaal-")) / "agenda-signaal.json"
    S.CONTROLEPUNTEN = S.STAND.parent / "controlepunten.json"


def ronde(google, wacht, kals=("werk",)):
    """Een ronde van main() met nagemaakte Google en wacht. Geeft (exitcode, stdout, stderr)."""
    oud = (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders)
    S.urllib.request.urlopen, S.subprocess.run = google, wacht
    S.A._toegang = lambda: "nep-token"
    S.W.kalenders = lambda: list(kals)
    uit, err = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(uit), contextlib.redirect_stderr(err):
            rc = S.main()
    finally:
        S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders = oud
    return rc, uit.getvalue(), err.getvalue()


def stand():
    return json.loads(S.STAND.read_text())


MAX = getattr(S, "MAX_POGINGEN", 5)

# --- het bestaande gedrag blijft (FR-62) ---------------------------------------------------------------
_e = ev("e1", dag(4))
_v = {}
_d1, _ = S.te_verwerken("werk", [_e], {}, _v)
_d2, _ = S.te_verwerken("werk", [dict(_e, colorId="3", description="x")], dict(_v), dict(_v))
_d3, _ = S.te_verwerken("werk", [ev("r1", dag(4), titel="\U0001F697 Reistijd: thuis → Herent")], {}, {})
check("een nieuwe afspraak plant zijn dag, een kleurwissel niets, een eigen ritblok niets",
      _d1 == {dag(4)} and not _d2 and not _d3, str((_d1, _d2, _d3)))

# --- A4: alle pagina's ---------------------------------------------------------------------------------
nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev(f"p{i}", dag(3)) for i in range(250)] + [ev(f"q{i}", dag(6)) for i in range(10)]
rc, uit, err = ronde(g, w)
check("A4 ook de 251ste wijziging en verder wordt gelezen: de dag op pagina 2 krijgt de wacht",
      dag(6) in w.dagen and dag(3) in w.dagen, str(w.dagen))
check("A4 alle 260 vingerafdrukken staan in de stand", len(stand().get("vinger", {})) == 260,
      str(len(stand().get("vinger", {}))))
check("A4 nextPageToken en originalStartTime worden bij Google gevraagd",
      all("nextPageToken" in q.get("fields", "") and "originalStartTime" in q.get("fields", "") for _, q in g.vragen),
      str(g.vragen[:1]))

nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev(f"p{i}", dag(3)) for i in range(250)] + [ev(f"q{i}", dag(6)) for i in range(10)]
g.fout["werk"] = {1}
rc1, _, err1 = ronde(g, w)
w1 = list(w.dagen)
g.fout = {}
rc2, _, _ = ronde(g, w)
check("A4 een fout op pagina 2 maakt de hele lezing mislukt: niets van die agenda telt, en het script faalt",
      rc1 != 0 and not w1 and "HTTP 500" in err1, str((rc1, w1, err1)))
check("A4 de ronde daarna leest beide pagina's opnieuw en plant beide dagen",
      rc2 == 0 and dag(3) in w.dagen and dag(6) in w.dagen, str(w.dagen))

# --- A5: te vroeg afgevinkt ----------------------------------------------------------------------------
nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("a1", dag(3))]
g.items["prive"] = [ev("b1", dag(5))]
g.fout["prive"] = {0}
rc1, _, err1 = ronde(g, w, ("werk", "prive"))
st1 = stand()
g.fout = {}
w2 = NepWacht()
rc2, _, _ = ronde(g, w2, ("werk", "prive"))
st2 = stand()
_c1 = st1.get("cursor", {})
check("A5 na een HTTP-fout gaat de cursor van die agenda niet vooruit, die van de andere wel",
      "werk" in _c1 and "prive" in _c1 and _c1["werk"] == st1.get("gekeken") and t(_c1["prive"]) < t(_c1["werk"]),
      str(_c1))
check("A5 de wijziging op de agenda die faalde komt de volgende ronde alsnog",
      dag(3) in w.dagen and dag(5) not in w.dagen and w2.dagen == [dag(5)], str((w.dagen, w2.dagen)))
check("A5 een mislukte bronlezing laat het script niet met 0 eindigen", rc1 != 0 and rc2 == 0, str((rc1, rc2)))

# een crash tijdens de verwerking: de stand is nog niet geschreven, de volgende ronde doet de dag opnieuw
nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("c1", dag(4))]
w.uitzondering = RuntimeError("stroom weg")
try:
    ronde(g, w)
    _crash = False
except RuntimeError:
    _crash = True
w2 = NepWacht()
ronde(g, w2)
check("A5 na een crash tijdens de verwerking verdwijnt de wijziging niet: de volgende ronde doet de dag",
      _crash and w2.dagen == [dag(4)], str((_crash, w2.dagen)))

# een mislukte dag blijft open, komt terug, en pas dan gaat de cursor vooruit
nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("d1", dag(3)), ev("d2", dag(7))]
w.rc[dag(7)] = 1
rc1, _, _ = ronde(g, w)
st1 = stand()
w.rc = {}
w2 = NepWacht()
rc2, _, _ = ronde(g, w2)
st2 = stand()
check("A5 een dag waarvoor de wacht faalt, staat als open dag in de stand met zijn pogingen",
      st1.get("open", {}).get(dag(7), {}).get("pogingen") == 1 and dag(3) not in st1.get("open", {}), str(st1.get("open")))
check("A5 de open dag wordt de volgende ronde opnieuw geprobeerd, de geslaagde niet",
      w2.dagen == [dag(7)] and not st2.get("open"), str((w2.dagen, st2.get("open"))))
check("A5 de cursor blijft staan zolang er een open dag is en gaat daarna vooruit",
      "werk" in st1.get("cursor", {}) and t(st1["cursor"]["werk"]) < t(st1["gekeken"])
      and st2.get("cursor", {}).get("werk") == st2.get("gekeken"), str((st1.get("cursor"), st2.get("cursor"))))

# een dag die blijft falen wordt begrensd geprobeerd en dan luid opgegeven
nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("f1", dag(5))]
w.rc[dag(5)] = 1
_errs = [ronde(g, w)[2] for _ in range(MAX + 2)]
check(f"A5 een dag die blijft falen wordt precies {MAX} keer geprobeerd en dan opgegeven",
      w.dagen.count(dag(5)) == MAX and not stand().get("open") and "opgegeven" in _errs[MAX - 1],
      str((w.dagen, stand().get("open"), _errs[MAX - 1][:200])))
check("A5 na het opgeven gaat de cursor vooruit en staat de dag in de lijst opgegeven",
      stand().get("cursor", {}).get("werk") == stand().get("gekeken")
      and any(o.get("dag") == dag(5) for o in stand().get("opgegeven", [])), str(stand().get("opgegeven")))

# de stand wordt atomair geschreven: tijdelijk bestand en os.replace
nieuwe_stand()
_vervangen = []
_echt = S.os.replace
S.os.replace = lambda a, b: _vervangen.append((str(a), str(b))) or _echt(a, b)
try:
    ronde(NepGoogle(), NepWacht())
finally:
    S.os.replace = _echt
check("A5 de stand wordt atomair geschreven: tijdelijk bestand, dan os.replace",
      len(_vervangen) == 1 and _vervangen[0][1] == str(S.STAND) and _vervangen[0][0] != str(S.STAND)
      and [p.name for p in S.STAND.parent.iterdir() if p.name.endswith(".tmp")] == [], str(_vervangen))

# een stand van voor deze herstelling (alleen 'gekeken') wordt de cursor van elke agenda
nieuwe_stand()
_t = nu_iso(-30)
S.STAND.write_text(json.dumps({"gekeken": _t, "vinger": {}}))
g = NepGoogle()
ronde(g, NepWacht(), ("werk", "prive"))
check("A5 een oude stand: elke agenda leest vanaf het oude 'gekeken'",
      sorted(q["updatedMin"] for _, q in g.vragen) == [_t, _t], str([q["updatedMin"] for _, q in g.vragen]))

# een tweede ronde terwijl de eerste nog loopt, slaat over (de stand komt pas achteraf)
nieuwe_stand()
_slot = open(S.STAND.with_name(S.STAND.name + ".lock"), "w")
fcntl.flock(_slot, fcntl.LOCK_EX | fcntl.LOCK_NB)
g = NepGoogle()
try:
    rc, uit, _ = ronde(g, NepWacht())
finally:
    _slot.close()
check("A5 loopt de vorige ronde nog, dan slaat deze over zonder Google te vragen",
      rc == 0 and not g.vragen and "loopt nog" in uit, str((rc, g.vragen, uit)))

# --- A6: falen lijkt succes ----------------------------------------------------------------------------
nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("g1", dag(3))]
w.rc[dag(3)] = 2
rc, uit, err = ronde(g, w)
check("A6 een wacht met exitcode 2 heet mislukt: foutregel op stderr met dag en exitcode, script niet 0",
      rc != 0 and dag(3) in err and "exitcode 2" in err and "quota op" in err
      and f"wacht gedraaid voor {dag(3)}" not in uit, str((rc, uit, err)))
check("A6 de mislukte dag blijft open", dag(3) in stand().get("open", {}), str(stand().get("open")))

nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("h1", dag(3))]
w.uitzondering = subprocess.TimeoutExpired(["agenda_wacht.py"], 900)
try:
    rc, uit, err = ronde(g, w)
    _ok = True
except subprocess.TimeoutExpired:
    rc, uit, err, _ok = None, "", "", False
check("A6 een time-out van de wacht laat het script niet crashen: dag open, script niet 0",
      _ok and rc != 0 and dag(3) in stand().get("open", {}) and "TimeoutExpired" in err, str((_ok, rc, err)))

nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("i1", dag(3))]
rc, uit, err = ronde(g, w)
check("A6 alles gelukt: exitcode 0, geen foutregel", rc == 0 and not err and f"wacht gedraaid voor {dag(3)}" in uit,
      str((rc, uit, err)))

# --- A7: verplaatsen vergeet de oude dag ---------------------------------------------------------------
_v = {}
S.te_verwerken("werk", [ev("m1", dag(3))], {}, _v)
_d, _w = S.te_verwerken("werk", [ev("m1", dag(8))], dict(_v), dict(_v))
check("A7 een verplaatsing op dezelfde agenda plant de oude en de nieuwe dag",
      _d == {dag(3), dag(8)} and "was" in _w[0], str((_d, _w)))
_d, _ = S.te_verwerken("prive", [ev("m1", dag(8))], dict(_v), {})
check("A7 een verhuis naar een andere agenda plant ook de dag waar hij vroeger stond",
      _d == {dag(3), dag(8)}, str(_d))
_d, _ = S.te_verwerken("werk", [ev("reeks_20261005T080000Z", dag(9), originalStartTime={"date": dag(4)})], {}, {})
check("A7 een verplaatste reeksinstantie plant ook zijn oorspronkelijke dag", _d == {dag(4), dag(9)}, str(_d))
try:
    _d, _ = S.te_verwerken("werk", [ev("m1", dag(8))], {"werk|m1": [S.vingerafdruk(ev("m1", dag(-5))), dag(-5)]}, {},
                           (date.today() - timedelta(days=1)).isoformat())
except TypeError as e:          # een versie zonder 'vanaf' telt als fout, niet als crash van de suite
    _d = f"TypeError: {e}"
check("A7 een oude dag voor het venster wordt niet gepland", _d == {dag(8)}, str(_d))

nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("m2", dag(3))]
ronde(g, w)
g.items["werk"] = [ev("m2", dag(10), bijgewerkt=nu_iso(1))]
w2 = NepWacht()
ronde(g, w2)
check("A7 in een echte ronde krijgt na een verplaatsing ook de oude dag de wacht",
      sorted(w2.dagen) == sorted([dag(3), dag(10)]), str(w2.dagen))

# --- A8: annulering zonder start ----------------------------------------------------------------------
_v = {}
S.te_verwerken("werk", [ev("x1", dag(5), titel="Mehdi: [UNABO-IN] EPB Sales")], {}, _v)
_weg = {"id": "x1", "status": "cancelled", "updated": nu_iso(1)}
_v2 = dict(_v)
_d, _w = S.te_verwerken("werk", [_weg], dict(_v), _v2)
_d2, _ = S.te_verwerken("werk", [_weg], dict(_v2), dict(_v2))
check("A8 een geschrapte afspraak zonder start plant de dag uit de vingerafdruk, met zijn oude titel",
      _d == {dag(5)} and "EPB Sales" in _w[0] and "cancelled" in _w[0], str((_d, _w)))
check("A8 dezelfde annulering een tweede keer plant niets meer", not _d2, str(_d2))
_d, _ = S.te_verwerken("werk", [{"id": "reeks_20261012T080000Z", "status": "cancelled",
                                  "originalStartTime": {"dateTime": f"{dag(6)}T10:00:00+02:00"}}], {}, {})
check("A8 een geschrapte reeksinstantie zonder vingerafdruk plant zijn oorspronkelijke dag", _d == {dag(6)}, str(_d))
_d, _ = S.te_verwerken("werk", [{"id": "onbekend", "status": "cancelled"}], {}, {})
check("A8 een annulering waarvan geen dag te vinden is, wordt stil overgeslagen", not _d, str(_d))

nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("x2", dag(4))]
ronde(g, w)
g.items["werk"] = [{"id": "x2", "status": "cancelled", "updated": nu_iso(1)}]
w2 = NepWacht()
rc, uit, _ = ronde(g, w2)
check("A8 in een echte ronde krijgt de dag van een geschrapte afspraak de wacht", w2.dagen == [dag(4)] and rc == 0,
      str((w2.dagen, uit)))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
