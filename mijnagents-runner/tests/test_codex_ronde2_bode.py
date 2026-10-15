"""Grendel op De Bode na de Codex-controle ronde 2 (A13, A19, A23, A26; 15-10-2026).

A13: een start die mislukt (Twilio-fout, lege sid) is geen oproep. Niet in 'gebeld', wel een teller in 'belpogingen',
de volgende minuut opnieuw binnen het belvenster, hoogstens drie keer; voor een alarm telt een mislukte start niet als
poging en zet ze de sleutel niet vast. 'Nooit twee keer voor hetzelfde' blijft gelden voor een echte oproep.
A19: met --droog (regisseur.py, agent_ronde) belt De Bode nooit, stuurt ze niets en blijft de stand ongewijzigd.
A23: de stille uren (22:00 tot 07:00) en het uur bovenaan een bericht zijn Brusselse tijd, ook op een VM in UTC.
A26: een ronde tegelijk (slot), de stand atomair en meteen na elke oproep op schijf, en een storing bij Telegram of het
bord houdt het bellen niet tegen.

Zonder netwerk en sleutels (ook CI): elk kanaal is nagebootst, BELLEN_UIT=1 houdt de echte bel() tegen, en de stand en
het belrooster staan in een tijdelijke map. Geen echte nummers, namen of sleutels.
"""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"      # een test belt nooit echt (FR-55)
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER / "koppelingen"))
sys.path.insert(0, str(HIER))
import bode as B    # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def probeer(fn, *a, **k):
    """(uitkomst, None) of (None, 'Fout: tekst'): een crash wordt een FOUT, geen afgebroken test."""
    try:
        return fn(*a, **k), None
    except Exception as e:  # noqa: BLE001
        return None, f"{type(e).__name__}: {e}"


def onbereikbaar(wat):
    def f(*a, **k):
        raise OSError(f"{wat} nagebootst onbereikbaar")
    return f


# ------------------------------------------------------------------ nabootsingen ---
TMP = Path(tempfile.mkdtemp())
B.STAAT = str(TMP / "bode.json")
B.bellen.ROOSTER = str(TMP / "belrooster.json")
B.TG_TOKEN, B.TG_CHAT = "proef-token", "1"
B.tg = onbereikbaar("telegram")
B.stuur_zoom = onbereikbaar("zoom")
B.whatsapp.binnen = onbereikbaar("whatsapp")
B.whatsapp.instellingen = onbereikbaar("whatsapp")
B.whatsapp.stuur = onbereikbaar("whatsapp")
verstuurd, logs, hartslagen = [], [], []
B.stuur = lambda tekst, nood: verstuurd.append(tekst) or "proef"
B.ag.log = lambda onderwerp, stap, tekst, detail="": logs.append(tekst)
B.ag.log_verstuur = lambda: None
B.ag.hartslag = lambda *a, **k: hartslagen.append(k)
BORD = {"fout": False, "items": [], "gesprek_fout": False}


def nep_bord(pad, payload=None, method=None):
    if BORD["fout"] or (BORD["gesprek_fout"] and pad.startswith("/api/gesprek")):
        raise OSError("bord nagebootst onbereikbaar")
    if pad.startswith("/api/klaarzet"):
        return {"items": list(BORD["items"])}
    return {"agents": []} if pad.startswith("/api/overzicht") else {}


B.bord.call = nep_bord
BEL = B.bellen
ECHT = {n: getattr(BEL, n) for n in ("afspraken_bellen", "alarm_bellen", "bel_afspraak", "bel")}
BEL.afspraak_bellen_beschikbaar = lambda: True
BEL.beschikbaar = lambda: True
BEL.callmebot_beschikbaar = lambda: False
BEL.status = lambda sid: "no-answer"
oproepen = []
UITSLAG = [[("twilio", "mislukt: HTTPError")]]


def nep_bel_afspraak(tekst, slot=""):
    oproepen.append(tekst)
    return UITSLAG[0]


BEL.bel_afspraak = nep_bel_afspraak
alarm_oproepen = []
BEL_UIT = [RuntimeError("Twilio nagebootst 500")]


def nep_bel(tekst, slot="", van=None):
    alarm_oproepen.append(tekst)
    if isinstance(BEL_UIT[0], Exception):
        raise BEL_UIT[0]
    return BEL_UIT[0]


BEL.bel = nep_bel


def rooster(*regels):
    with open(BEL.ROOSTER, "w") as f:
        json.dump({"geschreven": datetime.now().astimezone().isoformat(), "regels": list(regels)}, f)


def regel(sleutel, min_geleden=1):
    t = datetime.now().astimezone() - timedelta(minutes=min_geleden)
    return {"sleutel": sleutel, "tijd": t.isoformat(), "tekst": "Mehdi, over 5 minuten online: proefafspraak.",
            "titel": f"Proefafspraak {sleutel}"}


def stand():
    try:
        return json.load(open(B.STAAT))
    except (OSError, ValueError):
        return None


def schone_stand():
    if os.path.exists(B.STAAT):
        os.remove(B.STAAT)


# ------------------------------------------------------------------ A13 afspraken ---
rooster(regel("proef-1"))
st = {}
logs.clear()
r1, f1 = probeer(BEL.afspraken_bellen, st, log=B.ag.log)
check("A13 een mislukte start (twilio: mislukt) staat niet in gebeld", f1 is None and "proef-1" not in st.get("gebeld", {}),
      f"{f1} {st}")
check("A13 een mislukte start telt in belpogingen (1)", st.get("belpogingen", {}).get("proef-1") == 1, str(st))
check("A13 de logregel zegt 'bellen mislukt', nooit 'gebeld voor'",
      any("bellen mislukt" in t for t in logs) and not any("gebeld voor" in t for t in logs), str(logs))
r2, f2 = probeer(BEL.afspraken_bellen, st, log=B.ag.log)
check("A13 de volgende minuut, binnen het venster, probeert hij opnieuw",
      f2 is None and len(oproepen) == 2 and st.get("belpogingen", {}).get("proef-1") == 2, f"{f2} {len(oproepen)} {st}")
UITSLAG[0] = [("twilio", "CA123")]
logs.clear()
r3, f3 = probeer(BEL.afspraken_bellen, st, log=B.ag.log)
check("A13 bij een echte oproep (CA123) staat hij in gebeld en verdwijnt de teller",
      f3 is None and len(oproepen) == 3 and "proef-1" in st.get("gebeld", {}) and "proef-1" not in st.get("belpogingen", {})
      and any("gebeld voor" in t for t in logs), f"{f3} {len(oproepen)} {st} {logs}")
probeer(BEL.afspraken_bellen, st, log=B.ag.log)
check("A13 na een echte oproep niet nog eens (elke oproep een keer)", len(oproepen) == 3, str(len(oproepen)))

rooster(regel("proef-2"))
st, UITSLAG[0] = {}, [("twilio", "mislukt: URLError")]
oproepen.clear()
logs.clear()
for _ in range(4):
    probeer(BEL.afspraken_bellen, st, log=B.ag.log)
check("A13 na drie mislukte pogingen geen vierde, en de sleutel is afgehandeld",
      len(oproepen) == 3 and "proef-2" in st.get("gebeld", {}) and "proef-2" not in st.get("belpogingen", {}),
      f"{len(oproepen)} {st}")
check("A13 het opgeven staat duidelijk in het logboek, zonder 'gebeld voor'",
      any("opgegeven na 3 mislukte pogingen" in t for t in logs) and not any("gebeld voor" in t for t in logs), str(logs))

rooster(regel("proef-3"))
st = {}
BEL.bel_afspraak = ECHT["bel_afspraak"]       # de echte keuze van kanaal, met een bel() die een lege sid geeft
BEL.bel = lambda tekst, slot="", van=None: ""
probeer(BEL.afspraken_bellen, st, log=B.ag.log)
BEL.bel_afspraak, BEL.bel = nep_bel_afspraak, nep_bel
check("A13 een lege call-sid van bel() is geen oproep", "proef-3" not in st.get("gebeld", {})
      and st.get("belpogingen", {}).get("proef-3") == 1, str(st))

rooster(regel("proef-4", min_geleden=10))
st = {"belpogingen": {"proef-4": 2}}
logs.clear()
probeer(BEL.afspraken_bellen, st, log=B.ag.log)
check("A13 belvenster voorbij na mislukte pogingen: teller weg en 'niet gebeld' in het logboek",
      "proef-4" not in st.get("belpogingen", {}) and any("niet gebeld" in t and "venster" in t for t in logs), f"{st} {logs}")

rooster(regel("proef-5"))
st, UITSLAG[0] = {}, [("telegram-oproep", "Please wait 65 seconds before the next call")]
probeer(BEL.afspraken_bellen, st, log=B.ag.log)
check("A13 de wachtmelding van CallMeBot (65 s) is geen oproep en geen poging",
      "proef-5" not in st.get("gebeld", {}) and "belpogingen" in st and "proef-5" not in st["belpogingen"], str(st))

# ------------------------------------------------------------------ A13 alarm ---
ALARM = [{"id": 41, "titel": "Proefsignaal dringend"}]
st = {}
alarm_oproepen.clear()
logs.clear()
BEL_UIT[0] = RuntimeError("Twilio nagebootst 500")
probeer(BEL.alarm_bellen, st, ALARM, log=B.ag.log)
_b = st.get("bel", {})
check("A13 alarm: een mislukte start (fout) zet de sleutel niet vast, telt niet als poging en staat als mislukt in het logboek",
      len(alarm_oproepen) == 1 and _b.get("sleutel") != "41" and _b.get("pogingen", 0) == 0
      and any("bellen mislukt" in t for t in logs), f"{_b} {logs}")
BEL_UIT[0] = ""          # lege sid; het signaal is intussen gemeld en zit niet meer in de alarmlijst
probeer(BEL.alarm_bellen, st, [], log=B.ag.log)
_b = st.get("bel", {})
check("A13 alarm: de volgende ronde opnieuw, ook als het signaal al gemeld is; een lege sid telt ook niet",
      len(alarm_oproepen) == 2 and _b.get("sleutel") != "41" and _b.get("pogingen", 0) == 0, f"{len(alarm_oproepen)} {_b}")
BEL_UIT[0] = "CA9"
probeer(BEL.alarm_bellen, st, [], log=B.ag.log)
_b = st.get("bel", {})
check("A13 alarm: een echte oproep zet de sleutel vast, een poging",
      len(alarm_oproepen) == 3 and _b.get("sleutel") == "41" and _b.get("sid") == "CA9" and _b.get("pogingen") == 1,
      f"{len(alarm_oproepen)} {_b}")
probeer(BEL.alarm_bellen, st, ALARM, log=B.ag.log)
check("A13 alarm: niet opgenomen, toch nooit twee keer voor hetzelfde", len(alarm_oproepen) == 3, str(len(alarm_oproepen)))

st = {}
alarm_oproepen.clear()
logs.clear()
BEL_UIT[0] = RuntimeError("Twilio nagebootst 500")
for _i in range(5):
    probeer(BEL.alarm_bellen, st, ALARM if _i in (0, 4) else [], log=B.ag.log)
check("A13 alarm: na drie mislukte starts opgegeven, met een logregel, ook als het alarm terugkomt",
      len(alarm_oproepen) == 3 and any("opgegeven" in t for t in logs) and not (st.get("bel", {}).get("open") or {}),
      f"{len(alarm_oproepen)} {st} {logs}")

# ------------------------------------------------------------------ A23 Brusselse tijd ---
UTC = timezone.utc
for _t, _verwacht, _uitleg in ((datetime(2026, 7, 15, 20, 30, tzinfo=UTC), True, "juli 20:30 UTC is 22:30 in Brussel"),
                               (datetime(2026, 7, 15, 5, 30, tzinfo=UTC), False, "juli 05:30 UTC is 07:30 in Brussel"),
                               (datetime(2026, 1, 15, 21, 30, tzinfo=UTC), True, "januari 21:30 UTC is 22:30 in Brussel"),
                               (datetime(2026, 1, 15, 12, 0, tzinfo=UTC), False, "januari 12:00 UTC")):
    _u, _f = probeer(lambda t=_t: B.is_stil(t))
    check(f"A23 is_stil: {_uitleg} -> {'stil' if _verwacht else 'niet stil'}", _f is None and _u is _verwacht, f"{_u} {_f}")


class NepTijd(datetime):
    """De VM: een naieve klok in UTC; met een zone de juiste omrekening."""
    vast = datetime(2026, 7, 15, 10, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz=None):
        return cls.vast.astimezone(tz) if tz else cls.vast.replace(tzinfo=None)


ECHTE_TIJD = B.datetime
B.datetime = NepTijd
B.tg = lambda methode, **p: {"result": []}
rooster()
schone_stand()
BORD["items"] = [{"id": 7, "soort": "signaal", "titel": "Proefmelding", "van": "proef-agent"}]
verstuurd.clear()
_u, _f = probeer(B.main)
check("A23 het uur bovenaan het bericht is Brussels (10:00 UTC in juli -> 12:00)",
      _f is None and verstuurd and verstuurd[0].startswith("Mehdi Agents, 12:00"), f"{_f} {verstuurd[:1]}")
NepTijd.vast = datetime(2026, 7, 15, 20, 30, tzinfo=UTC)
schone_stand()
BORD["items"] = [{"id": 8, "soort": "signaal", "titel": "Proefmelding", "van": "proef-agent"}]
verstuurd.clear()
_u, _f = probeer(B.main)
check("A23 om 20:30 UTC in juli (22:30 Brussel) stuurt De Bode niets zonder alarm", _f is None and not verstuurd,
      f"{_f} {verstuurd[:1]}")
B.datetime = ECHTE_TIJD
BORD["items"] = []

# ------------------------------------------------------------------ A26 slot en stand ---
_s1, _f1 = probeer(lambda: B.slot_nemen())
_s2, _f2 = probeer(lambda: B.slot_nemen())
check("A26 een tweede slot terwijl het eerste vastgehouden wordt: overslaan (None)",
      _f1 is None and _s1 is not None and _f2 is None and _s2 is None, f"{_s1} {_s2} {_f1} {_f2}")
rooster(regel("proef-slot"))
schone_stand()
oproepen.clear()
UITSLAG[0] = [("twilio", "CA55")]
_u, _f = probeer(B.main)
check("A26 een ronde terwijl de vorige nog loopt, slaat over: niet gebeld en niets geschreven",
      _f is None and not oproepen and stand() is None, f"{_f} {len(oproepen)} {stand()}")
if _s1:
    _s1.close()
_s3, _f3 = probeer(lambda: B.slot_nemen())
check("A26 na de vorige ronde is het slot weer vrij", _f3 is None and _s3 is not None, str(_f3))
if _s3:
    _s3.close()

schone_stand()
_u, _f = probeer(lambda: B.bewaar({"a": 1}))
_u2, _f2 = probeer(lambda: B.bewaar({"kapot": object()}))
check("A26 de stand wordt atomair geschreven: een fout laat de vorige stand heel en geen tijdelijk bestand achter",
      _f is None and _f2 is not None and stand() == {"a": 1} and not list(TMP.glob("*.tmp")), f"{_f} {_f2} {stand()}")
_bron = (HIER / "bode.py").read_text(encoding="utf-8")
check("A26 main schrijft de stand niet meer met json.dump in een open bestand", "json.dump(staat, open(STAAT" not in _bron)

rooster(regel("proef-cb-1"), regel("proef-cb-2"))
schone_stand()
_op_schijf = []


def bel_en_kijk(tekst, slot=""):
    _op_schijf.append((stand() or {}).get("gebeld", {}).copy())
    return [("twilio", "CA77")]


BEL.bel_afspraak = bel_en_kijk
_u, _f = probeer(BEL.afspraken_bellen, {}, log=B.ag.log, bewaar=getattr(B, "bewaar", None))
check("A26 met de bewaar-callback staat de eerste oproep al op schijf voor de tweede begint",
      _f is None and len(_op_schijf) == 2 and "proef-cb-1" in _op_schijf[1], f"{_f} {_op_schijf}")
BEL.bel_afspraak = nep_bel_afspraak

rooster(regel("proef-schijf"))
schone_stand()
oproepen.clear()
_tussen = []
ECHTE_NAMEN = B.agentnamen
B.agentnamen = lambda: _tussen.append((stand() or {}).get("gebeld", {})) or {}
_u, _f = probeer(B.main)
B.agentnamen = ECHTE_NAMEN
check("A26 na een echte oproep staat de sleutel al op schijf voor main eindigt",
      _f is None and len(oproepen) == 1 and _tussen and "proef-schijf" in _tussen[0], f"{_f} {len(oproepen)} {_tussen}")

for _wat, _bord_fout, _tg in (("Telegram", False, onbereikbaar("telegram")),
                              ("het bord", True, lambda methode, **p: {"result": []})):
    rooster(regel(f"proef-storing-{_wat}"))
    schone_stand()
    oproepen.clear()
    hartslagen.clear()
    BORD["fout"], B.tg = _bord_fout, _tg
    _u, _f = probeer(B.main)
    check(f"A26 als {_wat} een fout gooit, wordt er toch gebeld en staat het op schijf",
          _f is None and len(oproepen) == 1 and f"proef-storing-{_wat}" in ((stand() or {}).get("gebeld") or {}),
          f"{_f} {len(oproepen)} {stand()}")
    check(f"A26 een storing bij {_wat} wordt een nood op het bord, geen crash",
          bool(hartslagen) and any("mislukt" in n["tekst"] for n in (hartslagen[-1].get("nood") or [])),
          str(hartslagen[-1:]))
BORD["fout"] = False

rooster()
schone_stand()
B.tg = lambda methode, **p: {"result": [{"update_id": 500, "message": {"chat": {"id": 1}, "text": "proefvraag"}}]}
BORD["gesprek_fout"] = True
_u, _f = probeer(B.main)
check("A26 een bericht van Telegram dat het bord niet aannam, wordt de volgende ronde opnieuw gelezen",
      _f is None and (stand() or {}).get("tg_offset", 0) == 0, f"{_f} {stand()}")
BORD["gesprek_fout"] = False

# ------------------------------------------------------------------ A19 droog ---
rooster(regel("proef-droog"))
schone_stand()
with open(B.STAAT, "w") as _f_st:
    json.dump({"laatste_id": 0, "tg_offset": 0, "wacht": [], "laatste_herinnering": "", "laatste_voorstellen": 0,
               "gebeld": {}}, _f_st)
_voor = Path(B.STAAT).read_bytes()
BORD["items"] = [{"id": 9, "soort": "oproep", "titel": "Proefoproep dringend", "van": "proef-agent"}]
B.tg = lambda methode, **p: {"result": []}
oproepen.clear()
alarm_oproepen.clear()
verstuurd.clear()
hartslagen.clear()
UITSLAG[0], BEL_UIT[0] = [("twilio", "CA66")], "CA67"
_aanroepen = []
BEL.afspraken_bellen = lambda *a, **k: _aanroepen.append("afspraken") or ECHT["afspraken_bellen"](*a, **k)
BEL.alarm_bellen = lambda *a, **k: _aanroepen.append("alarm") or ECHT["alarm_bellen"](*a, **k)
_argv = sys.argv
sys.argv = ["bode.py", "--droog"]
try:
    _u, _f = probeer(B.main)
finally:
    sys.argv = _argv
    BEL.afspraken_bellen, BEL.alarm_bellen = ECHT["afspraken_bellen"], ECHT["alarm_bellen"]
check("A19 met --droog loopt afspraken_bellen noch alarm_bellen, en er vertrekt geen oproep",
      _f is None and not _aanroepen and not oproepen and not alarm_oproepen,
      f"{_f} {_aanroepen} {len(oproepen)} {len(alarm_oproepen)}")
check("A19 met --droog blijft de stand ongewijzigd, gaat er niets naar Mehdi en geen hartslag naar het bord",
      Path(B.STAAT).read_bytes() == _voor and not verstuurd and not hartslagen,
      f"{Path(B.STAAT).read_bytes()[:200]} {verstuurd[:1]} {hartslagen[:1]}")
BORD["items"] = []

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
