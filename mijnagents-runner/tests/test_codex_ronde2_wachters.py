"""Grendel op de wachters naast de Agendawacht na de Codex-controle ronde 2 (15-10-2026): A12, A13 (Filewacht),
A19 (Filewacht), A25, A27 en A28.

A12  de Filewacht rekent vanaf het vertrekpunt van het heenblok (thuis of de vorige buitenafspraak van die dag), kiest
     het heenblok zoals de agent (einde op het begin van de afspraak, of 'Reistijd voor: <titel>'), nooit de terugrit
     van een andere afspraak; onbekend vertrekpunt: niet nagerekend, wel een logregel. Vertrek = max(nu, begin blok),
     aankomst = vertrek + rijtijd.
A13  een mislukte oproep (bellen.gelukt False) telt niet als oproep.
A19  alleen een geplande ronde (cron bij de voorouders) belt; met de hand gestart is het een proefronde.
A25  geen privétitel in de uitvoer van agenda_signaal of de Filewacht, en de bordklant drukt gemaskeerd af.
A27  een droge ronde laat de stand op schijf ongemoeid en logt nooit 'gebeld'.
A28  het dagproces krijgt --slot-wacht; exitcode 75 (rondeslot bezet) is geen poging, de dag blijft open.

Alle gegevens zijn verzonnen (plaatsen, straten, klanten). Geen netwerk, geen sleutels, geen echte oproep: rijtijd,
coördinaten, agenda, subprocess en bellen zijn nagemaakt, de standen staan in tijdelijke mappen.
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"      # een test belt nooit echt (FR-55)

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_signaal as S          # noqa: E402
import file_wacht as FW             # noqa: E402
import bord                         # noqa: E402

W = FW.W
S.STAND = Path(tempfile.mkdtemp(prefix="signaal-")) / "agenda-signaal.json"   # nooit de echte stand
S.CONTROLEPUNTEN = S.STAND.parent / "controlepunten.json"
S.PYTHON = "/usr/bin/false"                                                     # nooit de echte wacht
FW.STAND = Path(tempfile.mkdtemp(prefix="filewacht-")) / "file-wacht.json"

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


# ------------------------------------------------------------------------------------------- Filewacht-opzet
VAST = datetime.combine(date.today(), datetime.min.time()).replace(hour=10)     # 'nu' is vandaag 10:00, lokale tijd


class NepTijd(datetime):
    @classmethod
    def now(cls, tz=None):
        v = VAST if tz is None else VAST.astimezone(tz)
        return cls(v.year, v.month, v.day, v.hour, v.minute, v.second, v.microsecond, v.tzinfo)


def T(minuten):
    """ISO-tijd zoals de agenda ze geeft, minuten na 10:00 vandaag."""
    return (VAST + timedelta(minutes=minuten)).astimezone().isoformat()


THUIS = "Proefthuisstraat 1, 3000 Proefthuis"
ADR_A = "Eerstestraat 1, 2000 Proefstad"
ADR_B = "Tweedestraat 2, 3500 Anderstad"
ADR_C = "Derdestraat 3, 2800 Derdestad"
ADR_D = "Vierdestraat 4, 3200 Vierdestad"
ADR_P = "Geheimstraat 9, 3500 Anderstad"
COORD = {THUIS: [0.0, 0.0], ADR_A: [1.0, 1.0], ADR_B: [2.0, 2.0], ADR_C: [3.0, 3.0], ADR_D: [4.0, 4.0], ADR_P: [5.0, 5.0]}
PRIVE_KAL = sorted(W.PRIVE_KALENDERS)[0]


def afspr(id_, titel, van, tot, locatie="", kal="werk", oms=""):
    return {"id": id_, "titel": titel, "start": T(van), "einde": T(tot), "kalender": kal, "locatie": locatie,
            "omschrijving": oms}


def heen(id_, titel_afspraak, van, tot, rit, kal="werk", richting="voor"):
    """Een ritblok zoals de agent het schrijft (agenda_wacht, uitleg_h)."""
    oms = (f"Reistijd {richting}: {titel_afspraak} ({tot - van} min = vrije rijtijd x filefactor 1.1 + 10 min buffer, "
           f"OSRM; adres uit agenda; rit {rit})")
    return afspr(id_, "\U0001F697 Reistijd: " + rit, van, tot, kal=kal, oms=oms)


class NepRit:
    """Nagemaakte W.rijtijd_min: minuten per vertrekpunt, en welke vragen er kwamen."""

    def __init__(self, minuten):
        self.minuten, self.vragen = minuten, []

    def __call__(self, van, naar, vertrek):
        self.vragen.append((tuple(van), tuple(naar), vertrek))
        return self.minuten.get(tuple(van), 30), "proef"


class NepBel:
    def __init__(self, uit):
        self.uit, self.teksten = uit, []

    def __call__(self, tekst, slot=""):
        self.teksten.append(tekst)
        return self.uit


GELUKT = [("twilio", "CA0000proef")]
MISLUKT = [("twilio", "mislukt: RuntimeError")]


def filewacht(items, rit, bel, droog=False, gepland=True, stand=None):
    """Een ronde van file_wacht.main() met alles nagemaakt. gepland None: de echte W.geplande_start. Geeft (rc, uitvoer)."""
    FW.STAND = stand or (Path(tempfile.mkdtemp(prefix="filewacht-")) / "file-wacht.json")
    namen = ("afspraken", "_cache_laden", "coord", "THUIS", "plek_zoeken", "vaste_plek", "rijtijd_min", "geplande_start")
    oud_w = {n: W.__dict__.get(n, None) for n in namen}
    oud = (FW.datetime, W.projectadressen.index, FW.bellen.bel_afspraak, FW.DROOG)
    FW.datetime = NepTijd
    W.afspraken = lambda van_dagen=0, tot_dagen=1: [dict(x) for x in items]
    W._cache_laden = lambda: {}
    W.coord = lambda adres, cache: COORD.get(adres)
    W.THUIS = THUIS
    W.plek_zoeken = lambda tekst: (None, None)
    W.vaste_plek = lambda tekst: (None, None)
    W.rijtijd_min = rit
    if gepland is not None:
        W.geplande_start = lambda argv=None, voorouders=None: gepland
    W.projectadressen.index = lambda: {}
    FW.bellen.bel_afspraak = bel
    FW.DROOG = droog
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = FW.main()
    except Exception as e:  # noqa: BLE001  een crash telt als fout, niet als einde van de suite
        rc = f"CRASH {type(e).__name__}: {e}"
    finally:
        FW.datetime, W.projectadressen.index, FW.bellen.bel_afspraak, FW.DROOG = oud
        for n, v in oud_w.items():
            if v is None:
                W.__dict__.pop(n, None)
            else:
                setattr(W, n, v)
    return rc, buf.getvalue()


def stand_van(pad):
    try:
        return json.loads(pad.read_text())
    except (OSError, ValueError):
        return None


# ------------------------------------------------------------------------------------------- A12
TA = "Mehdi: [HA-KB] 2443 - Proefklant een"
TB = "Mehdi: [HA-KB] 2444 - Proefklant twee"
# twee buitenafspraken na elkaar: A 08:30-09:30 in Proefstad, B 11:30-12:30 in Anderstad, heenblok 10:30-11:30. De agent
# schrijft in het heenblok 'rit Proefstad → Anderstad': ritlabel(adres van A, adres van B).
_items = [afspr("a", TA, -90, -30, ADR_A), heen("rb", TB, 30, 90, "Proefstad → Anderstad"), afspr("b", TB, 90, 150, ADR_B)]
_rit, _bel = NepRit({(1.0, 1.0): 70, (0.0, 0.0): 30}), NepBel(GELUKT)
_rc, _uit = filewacht(_items, _rit, _bel)
check("A12 de rijtijd wordt gevraagd vanaf de vorige buitenafspraak, niet vanaf thuis",
      W.ritlabel(ADR_A, ADR_B) == "Proefstad" and len(_rit.vragen) == 1
      and _rit.vragen[0][0] == (1.0, 1.0) and _rit.vragen[0][1] == (2.0, 2.0), str((_rit.vragen, _rc, _uit[-300:])))
_vertrek = _rit.vragen[0][2] if _rit.vragen else None
check("A12 vertrek = begin van het heenblok (10:30), aankomst = vertrek + rijtijd: 10 min te laat en een oproep",
      _vertrek is not None and _vertrek.isoformat()[:16] == T(30)[:16] and "10 min te laat" in _uit and len(_bel.teksten) == 1,
      str((_vertrek, _uit[-300:], _bel.teksten)))

# een terugrit van een andere afspraak (C, 09:00-09:45) staat binnen drie uur voor D: niet kiezen, wel D's heenblok
TC = "Mehdi: [HA-KB] 2446 - Proefklant drie"
TD = "Mehdi: [HA-KB] 2447 - Proefklant vier"
_items = [afspr("c", TC, -120, -60, ADR_C), heen("rd", TD, 20, 60, "thuis → Vierdestad"),
          heen("rc", TC, -60, -15, "Derdestad → thuis", richting="na"), afspr("d", TD, 60, 120, ADR_D)]
_rit = NepRit({(0.0, 0.0): 40})
_rc, _uit = filewacht(_items, _rit, NepBel(GELUKT))
check("A12 de terugrit van een andere afspraak wordt niet als heenblok gekozen: gepland 40 min, vertrek 10:20",
      "gepland 40 min" in _uit and "gepland 45" not in _uit and len(_rit.vragen) == 1
      and _rit.vragen[0][2].isoformat()[:16] == T(20)[:16], str((_rit.vragen, _uit[-300:])))

# onbekend vertrekpunt: het blok zegt 'rit Elders → Anderstad', maar er was geen buitenafspraak in Elders
_items = [afspr("a", TA, -90, -30, ADR_A), heen("rb", TB, 30, 90, "Elders → Anderstad"), afspr("b", TB, 90, 150, ADR_B)]
_rit, _bel = NepRit({(0.0, 0.0): 200}), NepBel(GELUKT)
_rc, _uit = filewacht(_items, _rit, _bel)
check("A12 onbekend vertrekpunt: geen rijtijd gevraagd, geen oproep, wel een logregel",
      not _rit.vragen and not _bel.teksten and "niet nagerekend" in _uit, str((_rit.vragen, _bel.teksten, _uit[-300:])))

# ------------------------------------------------------------------------------------------- A27 droog
TE = "Mehdi: [HA-KB] 2448 - Proefklant vijf"
_items_e = [heen("re", TE, 30, 90, "thuis → Anderstad"), afspr("e", TE, 90, 150, ADR_B)]
_pad = Path(tempfile.mkdtemp(prefix="filewacht-")) / "file-wacht.json"
_pad.write_text(json.dumps({"dag": VAST.strftime("%Y-%m-%d"), "ander": {"laatst": T(-60), "oproepen": 0}}, indent=0))
_voor = _pad.read_bytes()
_rit, _bel = NepRit({(0.0, 0.0): 100}), NepBel(GELUKT)
_rc, _uit = filewacht(_items_e, _rit, _bel, droog=True, stand=_pad)
check("A27 een droge ronde rekent wel, belt niet en laat de stand op schijf ongewijzigd",
      _rit.vragen and not _bel.teksten and _pad.read_bytes() == _voor, str((_rit.vragen, _bel.teksten, _pad.read_text())))
check("A27 een droge ronde logt nooit 'gebeld'", "gebeld" not in _uit.lower(), _uit[-300:])
_rit2, _bel2 = NepRit({(0.0, 0.0): 100}), NepBel(GELUKT)
_rc, _uit2 = filewacht(_items_e, _rit2, _bel2, stand=_pad)
check("A27 de echte ronde na de droge doet wel haar berekening en belt",
      len(_rit2.vragen) == 1 and len(_bel2.teksten) == 1 and (stand_van(_pad) or {}).get("e", {}).get("oproepen") == 1,
      str((_rit2.vragen, _bel2.teksten, _uit2[-300:])))

# ------------------------------------------------------------------------------------------- A13 mislukte oproep
_pad = Path(tempfile.mkdtemp(prefix="filewacht-")) / "file-wacht.json"
_bel = NepBel(MISLUKT)
_rc, _uit = filewacht(_items_e, NepRit({(0.0, 0.0): 100}), _bel, stand=_pad)
check("A13 een mislukte oproep verhoogt 'oproepen' niet en heet niet 'Mehdi gebeld'",
      len(_bel.teksten) == 1 and (stand_van(_pad) or {}).get("e", {}).get("oproepen") == 0 and "Mehdi gebeld" not in _uit,
      str((stand_van(_pad), _uit[-300:])))

# ------------------------------------------------------------------------------------------- A19 alleen gepland belt
_argv, _voor_oud = sys.argv, W.__dict__.get("_voorouders")
try:
    sys.argv = ["file_wacht.py", "--ronde"]
    W._voorouders = lambda *a, **k: ["bash", "sshd"]          # met de hand, ook met '--ronde'
    _pad = Path(tempfile.mkdtemp(prefix="filewacht-")) / "file-wacht.json"
    _bel_h = NepBel(GELUKT)
    _rc_h, _uit_h = filewacht(_items_e, NepRit({(0.0, 0.0): 100}), _bel_h, gepland=None, stand=_pad)
    _stand_h = stand_van(_pad)
    W._voorouders = lambda *a, **k: ["python3", "sh", "cron"]  # door cron gestart
    _bel_c = NepBel(GELUKT)
    _rc_c, _uit_c = filewacht(_items_e, NepRit({(0.0, 0.0): 100}), _bel_c, gepland=None)
finally:
    sys.argv = _argv
    if _voor_oud is None:
        W.__dict__.pop("_voorouders", None)
    else:
        W._voorouders = _voor_oud
check("A19 met de hand gestart (ook met --ronde) belt niet en bewaart niets; door cron gestart belt wel",
      not _bel_h.teksten and _stand_h is None and len(_bel_c.teksten) == 1 and "gebeld" not in _uit_h.lower(),
      str((_bel_h.teksten, _stand_h, _bel_c.teksten, _rc_h, _rc_c, _uit_h[-200:])))

# ------------------------------------------------------------------------------------------- A25 privé
TP = "Mehdi: [HA-KB] 2449 - geheim proefbezoek"
_items = [heen("rp", TP, 30, 90, "thuis → Anderstad", kal=PRIVE_KAL), afspr("p", TP, 90, 150, ADR_P, kal=PRIVE_KAL)]
_bel = NepBel(GELUKT)
_rc, _uit = filewacht(_items, NepRit({(0.0, 0.0): 100}), _bel)
check("A25 de Filewacht drukt geen privétitel af en zegt 'je afspraak' in de oproep",
      "geheim" not in _uit and len(_bel.teksten) == 1 and "geheim" not in _bel.teksten[0] and "je afspraak" in _bel.teksten[0],
      str((_uit[-300:], _bel.teksten)))

_ag = bord.Agent("proef-masker-wachters")
_buf = io.StringIO()
try:
    _ag.prive(["geheim etentje bij proefvrienden"])
    with contextlib.redirect_stdout(_buf):
        _ag.log("dag", "bevinding", "rit naar geheim etentje bij proefvrienden loopt uit")
except Exception as e:  # noqa: BLE001
    _buf.write(f"CRASH {type(e).__name__}")
check("A25 bord.Agent drukt een als privé gemelde tekst gemaskeerd af",
      "geheim etentje" not in _buf.getvalue() and "(privé)" in _buf.getvalue(), _buf.getvalue())


def dag(n):
    return (date.today() + timedelta(days=n)).isoformat()


def nu_iso(min_=0):
    return (datetime.now(timezone.utc) + timedelta(minutes=min_)).isoformat()


def ev(eid, d, titel="Mehdi: [HA-KB] 2505 - proefklant", bijgewerkt=None, **meer):
    e = {"id": eid, "summary": titel, "status": "confirmed", "updated": bijgewerkt or nu_iso(-5),
         "start": {"dateTime": f"{d}T10:00:00+02:00"}, "end": {"dateTime": f"{d}T11:00:00+02:00"}}
    e.update(meer)
    return e


_v = {}
_d, _w = S.te_verwerken(PRIVE_KAL, [ev("s1", dag(3), titel="Mehdi: geheim etentje")], {}, _v)
_d2, _w2 = S.te_verwerken("werk", [ev("s2", dag(3), titel="Mehdi: tandarts controle"),
                                   ev("s3", dag(3), titel="Mehdi: [HA-KB] 2505 - proefklant zichtbaar")], {}, {})
_onb = []
S.te_verwerken(PRIVE_KAL, [{"id": "s4", "status": "cancelled", "summary": "Mehdi: geheim weg"}], {}, {}, "", _onb)
check("A25 agenda_signaal: een privé-agenda of zorgtitel wordt '(privé)', een werktitel blijft leesbaar",
      _d == {dag(3)} and "geheim" not in " ".join(_w) and "(privé)" in _w[0]
      and any("(privé)" in r for r in _w2) and not any("tandarts" in r for r in _w2) and any("zichtbaar" in r for r in _w2),
      str((_w, _w2)))
check("A25 agenda_signaal: een annulering zonder dag op de privé-agenda bewaart geen titel",
      len(_onb) == 1 and _onb[0]["titel"] == "(privé)", str([o.get("titel") for o in _onb]))


class NepGoogle:
    def __init__(self):
        self.items = {}

    def __call__(self, req, timeout=None, *a, **k):
        url = getattr(req, "full_url", req)
        u = urllib.parse.urlparse(url)
        kal = urllib.parse.unquote(u.path.split("/calendars/")[1].split("/events")[0])
        q = dict(urllib.parse.parse_qsl(u.query))
        sinds = datetime.fromisoformat(q["updatedMin"])
        return io.BytesIO(json.dumps({"items": [e for e in self.items.get(kal, [])
                                                 if datetime.fromisoformat(e["updated"]) >= sinds]}).encode())


class NepWacht:
    """Nagemaakte agenda_wacht.py --dag: onthoudt de gestarte dagen en de opdrachten, geeft de gevraagde exitcode."""

    def __init__(self):
        self.dagen, self.opdrachten, self.rc = [], [], {}

    def __call__(self, args, *a, **k):
        d = args[args.index("--dag") + 1]
        self.dagen.append(d)
        self.opdrachten.append((list(args), k))
        rc = self.rc.get(d, 0)
        fout = {0: "", 75: "rondeslot bezet\n"}.get(rc, "Traceback (most recent call last):\nRuntimeError: proef\n")
        return subprocess.CompletedProcess(args, rc, "  [schrijf] reistijd: 1 gezet\n", fout)


def nieuwe_stand():
    S.STAND = Path(tempfile.mkdtemp(prefix="signaal-")) / "agenda-signaal.json"
    S.CONTROLEPUNTEN = S.STAND.parent / "controlepunten.json"


def ronde(google, wacht, kals=("werk",)):
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


nieuwe_stand()
g = NepGoogle()
g.items[PRIVE_KAL] = [ev("s5", dag(4), titel="Mehdi: geheim etentje")]
g.items["werk"] = [ev("s6", dag(4), titel="Mehdi: [HA-KB] 2506 - proefklant zichtbaar")]
_rc, _uit, _err = ronde(g, NepWacht(), ("werk", PRIVE_KAL))
check("A25 een ronde van agenda_signaal drukt de wijziging op de privé-agenda af zonder titel",
      "geheim" not in _uit + _err and "(privé)" in _uit and "zichtbaar" in _uit, str((_uit, _err)))

# ------------------------------------------------------------------------------------------- A28 slot bezet
_opdr = NepWacht()
_o = S.subprocess.run
S.subprocess.run = _opdr
try:
    _r = S.draai_wacht(dag(3))
finally:
    S.subprocess.run = _o
_args, _kw = _opdr.opdrachten[0] if _opdr.opdrachten else ([], {})
check("A28 het dagproces krijgt --slot-wacht 120 en houdt zijn budget van 900 s",
      "--slot-wacht" in _args and _args[_args.index("--slot-wacht") + 1] == "120" and _kw.get("timeout") == 900,
      str((_args, _kw)))

MAX = S.MAX_POGINGEN
ALARM = getattr(S, "BEZET_ALARM", 10)
nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("t1", dag(3)), ev("t2", dag(5))]
w.rc = {dag(3): 75}
_rc, _uit, _err = ronde(g, w)
_open = stand().get("open", {})
check("A28 exitcode 75: de dag blijft open zonder poging, de volgende dag wacht op de volgende ronde, script 0",
      w.dagen == [dag(3)] and _open.get(dag(3), {}).get("pogingen") == 0 and _open.get(dag(3), {}).get("bezet") == 1
      and dag(5) in _open and _open[dag(5)].get("pogingen") == 0 and _rc == 0 and "MISLUKT" not in _err,
      str((w.dagen, _open, _rc, _err)))

nieuwe_stand()
g, w = NepGoogle(), NepWacht()
g.items["werk"] = [ev("t3", dag(4))]
w.rc = {dag(4): 1}
ronde(g, w)                                   # een echte mislukking: poging 1
w.rc = {dag(4): 75}
_rcs, _errs = [], []
for _ in range(ALARM):
    _rc, _, _err = ronde(g, w)
    _rcs.append(_rc)
    _errs.append(_err)
_st = stand()
_o4 = _st.get("open", {}).get(dag(4), {})
check(f"A28 {ALARM} rondes bezet na elkaar: de dag blijft open met 1 poging, nooit opgegeven",
      _o4.get("pogingen") == 1 and _o4.get("bezet") == ALARM and not any(o.get("dag") == dag(4) for o in _st.get("opgegeven", [])),
      str((_o4, _st.get("opgegeven"))))
check("A28 bezet is stil tot de alarmgrens, daarna luid op stderr en het script niet 0",
      all(r == 0 for r in _rcs[:-1]) and _rcs[-1] != 0 and "te lang bezet" in _errs[-1] and not any(_errs[:-1]),
      str((_rcs, _errs[-1][:200])))
w.rc = {}
_rc, _uit, _ = ronde(g, w)
check("A28 als het slot vrij is, slaagt de dag en gaat hij uit de open lijst",
      _rc == 0 and not stand().get("open") and f"wacht gedraaid voor {dag(4)}" in _uit, str((stand().get("open"), _uit)))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
