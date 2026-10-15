"""Grendel op De Bode na de Codex-controle ronde 2 (A13, A19, A23, A26; 15-10-2026) en ronde 3 (A31, A26, A13).

A13: een start die mislukt (Twilio-fout, lege sid) is geen oproep. Niet in 'gebeld', wel een teller in 'belpogingen',
de volgende minuut opnieuw binnen het belvenster, hoogstens drie keer; voor een alarm telt een mislukte start niet als
poging en zet ze de sleutel niet vast. 'Nooit twee keer voor hetzelfde' blijft gelden voor een echte oproep.
A19: met --droog (regisseur.py, agent_ronde) belt De Bode nooit, stuurt ze niets en blijft de stand ongewijzigd.
A23: de stille uren (22:00 tot 07:00) en het uur bovenaan een bericht zijn Brusselse tijd, ook op een VM in UTC.
A26: een ronde tegelijk (slot), de stand atomair en meteen na elke oproep op schijf, en een storing bij Telegram of het
bord houdt het bellen niet tegen.
Ronde 3:
A31: het bord levert nieuwe items dalend; De Bode meldt ze oplopend in groepen van hoogstens acht en schuift laatste_id
nooit voorbij een item dat geen bericht kreeg. Mislukt het sturen, dan schuift niets op.
A26: lukt het bewaren na een oproep niet, dan geen volgende oproep in die ronde, een logregel en een nood; het belspoor
naast de stand zorgt dat een nieuwe ronde dezelfde afspraak niet opnieuw belt.
A13: van CallMeBot telt alleen een herkend aanvaard-antwoord (gemeten op de VM) als oproep; een fout of een onbekend
antwoord niet.

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

# ------------------------------------------------------------------ ronde 3: A31 groepen ---
# De stille uren hangen af van de klok; hier altijd overdag, anders faalt de test 's nachts.
ECHT_STIL, ECHT_STUUR, ECHT_NIET_TG = B.is_stil, B.stuur, B.NIET_OP_TELEGRAM
B.is_stil = lambda t=None: False
B.NIET_OP_TELEGRAM = ("agenda-wacht",)
B.tg = lambda methode, **p: {"result": []}
rooster()


def klaarzet(ids, agenda=(), oproep=()):
    """Zoals het bord ze levert: dalend op id (ORDER BY id DESC). agenda: id's van De Agendawacht (niet naar Mehdi);
    oproep: id's die een oproep zijn (alarm)."""
    return [{"id": i, "soort": "oproep" if i in oproep else "signaal", "titel": f"Proefitem {i}",
             "van": "agenda-wacht" if i in agenda else "proef-agent"} for i in sorted(ids, reverse=True)]


def zet_stand(laatste_id=100):
    schone_stand()
    with open(B.STAAT, "w") as _fs:
        json.dump({"laatste_id": laatste_id, "tg_offset": 0, "wacht": [], "laatste_herinnering": "",
                   "laatste_voorstellen": 0}, _fs)


def gemeld(i):
    return any(f"Proefitem {i} " in t for t in verstuurd)


def rondes(n, tg_ids):
    """n rondes van main; per ronde (laatste_id, geen verstuurd item ooit onder laatste_id overgeslagen)."""
    uit = []
    for _ in range(n):
        probeer(B.main)
        lid = (stand() or {}).get("laatste_id", 0)
        uit.append((lid, all(gemeld(i) for i in tg_ids if i <= lid)))
    return uit


zet_stand()
BORD["items"] = klaarzet(range(101, 110))
verstuurd.clear()
_r = rondes(3, range(101, 110))
check("A31 negen nieuwe items: alle negen krijgen uiteindelijk een bericht",
      all(gemeld(i) for i in range(101, 110)), f"{[i for i in range(101, 110) if not gemeld(i)]} {verstuurd}")
check("A31 laatste_id staat nooit voorbij een item zonder bericht (na ronde 1 op 108, daarna 109)",
      [x[0] for x in _r] == [108, 109, 109] and all(x[1] for x in _r), str(_r))
check("A31 de oudste eerst, hoogstens acht per bericht, en het eerste bericht zegt dat er nog een volgt",
      len(verstuurd) == 2 and all(t.count("- signaal:") <= 8 for t in verstuurd)
      and gemeld(101) and "Proefitem 101 " in verstuurd[0] and "Proefitem 109 " in verstuurd[1]
      and "volgen in het volgende bericht" in verstuurd[0], str(verstuurd))

zet_stand()
BORD["items"] = klaarzet(range(101, 110))
verstuurd.clear()
B.stuur = lambda tekst, nood: ""          # elk kanaal faalt
probeer(B.main)
_na_fout = (stand() or {}).get("laatste_id")
B.stuur = ECHT_STUUR
_r = rondes(2, range(101, 110))
check("A31 lukt het sturen niet, dan schuift laatste_id niet op; de volgende rondes sturen alles alsnog",
      _na_fout == 100 and all(gemeld(i) for i in range(101, 110)) and _r[-1][0] == 109, f"{_na_fout} {_r} {verstuurd}")

# Agendazaken (niet naar Mehdi) tussen de items: als afgehandeld geteld, maar nooit over een item zonder bericht heen.
_ids, _agenda = range(101, 126), set(range(102, 126, 2))
_tg = [i for i in _ids if i not in _agenda]
zet_stand()
BORD["items"] = klaarzet(_ids, agenda=_agenda)
verstuurd.clear()
_r = rondes(3, _tg)
check("A31 met agendazaken ertussen: elk item voor Mehdi krijgt een bericht, geen agendazaak, laatste_id eindigt op 125",
      all(gemeld(i) for i in _tg) and not any(gemeld(i) for i in _agenda) and _r[-1][0] == 125, f"{_r} {verstuurd}")
check("A31 met agendazaken ertussen: na elke ronde is alles onder laatste_id voor Mehdi echt verstuurd",
      all(x[1] for x in _r) and _r[0][0] == 116, str(_r))

# Twee alarmen aan weerszijden van de groepsgrens: een oproep, niet een tweede omdat de lijst van voren kromp.
zet_stand()
BORD["items"] = klaarzet(range(101, 113), oproep={103, 111})
verstuurd.clear()
alarm_oproepen.clear()
BEL_UIT[0] = "CA31"
rondes(2, range(101, 113))
check("A31 twee alarmen verdeeld over twee berichten: een oproep, geen tweede voor hetzelfde",
      len(alarm_oproepen) == 1 and all(gemeld(i) for i in range(101, 113)), f"{len(alarm_oproepen)} {verstuurd}")

# Geen stand (eerste ronde, of een onleesbare bode.json): een bericht met de nieuwste, de rest bewust als gelezen.
schone_stand()
BORD["items"] = klaarzet(range(201, 221))
verstuurd.clear()
rondes(2, [])
check("A31 zonder stand: een bericht met de nieuwste acht, de oudere als gelezen (geen tientallen berichten)",
      len(verstuurd) == 1 and gemeld(220) and gemeld(213) and not gemeld(212)
      and (stand() or {}).get("laatste_id") == 220, f"{verstuurd} {stand()}")

zet_stand(100)
BORD["items"] = klaarzet(range(1001, 1001 + B.KLAARZET_N)) if hasattr(B, "KLAARZET_N") else klaarzet(range(1001, 1201))
hartslagen.clear()
probeer(B.main)
check("A31 een volle pagina waarvan zelfs het oudste item nieuw is: een nood (er kunnen items onder vallen)",
      bool(hartslagen) and any("klaarzet-items" in n["tekst"] for n in (hartslagen[-1].get("nood") or [])),
      str(hartslagen[-1:])[:300])
BORD["items"] = []
B.is_stil, B.NIET_OP_TELEGRAM = ECHT_STIL, ECHT_NIET_TG

# ------------------------------------------------------------------ ronde 3: A26 belspoor ---
SPOOR = B.belspoor() if hasattr(B, "belspoor") else str(TMP / "bode-gebeld.jsonl")


def regel_t(sleutel, tekst):
    return {**regel(sleutel), "tekst": tekst}


def kapotte_bewaar(staat):
    raise OSError("schijf vol (nagebootst)")


rooster(regel_t("proef-a", "Proeftekst A"), regel_t("proef-b", "Proeftekst B"))
schone_stand()
if os.path.exists(SPOOR):
    os.remove(SPOOR)
oproepen.clear()
hartslagen.clear()
logs.clear()
UITSLAG[0] = [("twilio", "CA81")]
ECHTE_BEWAAR = B.bewaar
B.bewaar = kapotte_bewaar
try:
    _u, _f = probeer(B.main)
finally:
    B.bewaar = ECHTE_BEWAAR
check("A26 bewaarfout na de eerste oproep: geen tweede oproep in die ronde", oproepen == ["Proeftekst A"], str(oproepen))
check("A26 de gestopte belronde staat in het logboek en als nood op het bord, zonder crash",
      _f is None and any("belronde gestopt" in t for t in logs) and bool(hartslagen)
      and any("niet op schijf" in n["tekst"] for n in (hartslagen[-1].get("nood") or [])), f"{_f} {logs} {hartslagen[-1:]}")
oproepen.clear()
_u, _f = probeer(B.main)        # nieuwe ronde; de stand kwam nooit op schijf, het belspoor wel
check("A26 een nieuwe ronde belt de eerste afspraak niet opnieuw (belspoor), wel de tweede",
      _f is None and oproepen == ["Proeftekst B"], f"{_f} {oproepen}")
check("A26 na de nieuwe ronde staan beide afspraken als gebeld in de stand",
      {"proef-a", "proef-b"} <= set(((stand() or {}).get("gebeld") or {})), str(stand()))

# Ook het spoor niet te schrijven (zijn map is een bestand): niet verder bellen, en de nood zegt dat het onzeker is.
_geen_map = TMP / "geen-map"
_geen_map.write_text("bestand, geen map")
rooster(regel_t("proef-c", "Proeftekst C"), regel_t("proef-d", "Proeftekst D"))
oproepen.clear()
_nood = []
_u, _f = probeer(BEL.afspraken_bellen, {}, log=B.ag.log, bewaar=kapotte_bewaar, nood=_nood,
                 spoor=str(_geen_map / "spoor.jsonl"))
check("A26 spoor en stand allebei niet te schrijven: geen tweede oproep, en de nood zegt dat ze opnieuw kan vertrekken",
      _f is None and oproepen == ["Proeftekst C"] and any("nergens op schijf" in n["tekst"] for n in _nood),
      f"{_f} {oproepen} {_nood}")

_sp = TMP / "half.jsonl"
_sp.write_text('{"sleutel": "half')    # crash midden in een regel
_u, _f = probeer(lambda: BEL.spoor_schrijven(str(_sp), "heel", "2026-10-15T10:00:00+02:00"))
_l, _fl = probeer(lambda: BEL.spoor_lezen(str(_sp)))
check("A26 een halve laatste regel in het spoor: de nieuwe regel blijft leesbaar",
      _f is None and _fl is None and _l == {"heel": "2026-10-15T10:00:00+02:00"}, f"{_f} {_fl} {_l}")

_oud = (datetime.now().astimezone() - timedelta(days=3)).isoformat()
_vers = datetime.now().astimezone().isoformat()
_sp2 = TMP / "opruimen.jsonl"
_sp2.write_text(json.dumps({"sleutel": "oud", "tijd": _oud}) + "\n" + json.dumps({"sleutel": "vers", "tijd": _vers}) + "\n")
rooster()
probeer(BEL.afspraken_bellen, {}, log=B.ag.log, spoor=str(_sp2))
_l, _fl = probeer(lambda: BEL.spoor_lezen(str(_sp2)))
check("A26 het spoor ruimt regels ouder dan twee dagen op en houdt de rest", _fl is None and _l == {"vers": _vers}, f"{_fl} {_l}")

_sp3 = TMP / "droog.jsonl"
_sp3.write_text(json.dumps({"sleutel": "proef-e", "tijd": _vers}) + "\n")
_l, _fl = probeer(lambda: BEL.te_bellen({}, rooster=[regel("proef-e")], spoor=str(_sp3)))
check("A26 ook de droge ronde (te_bellen) telt het spoor als gebeld", _fl is None and _l == [], f"{_fl} {_l}")

# ------------------------------------------------------------------ ronde 3: A13 CallMeBot ---
# Gemeten op de VM (15-10-2026, logboek van de filewacht), gebruiker en nummer vervangen door een proefnaam.
GEMETEN_AANVAARD = ("Checking Authorization for @proefgebruiker... Using bot: @CallMeBot_txtbot Autorization OK "
                    "User:@proefgebruiker Text to speech:(tekst)")
GEMETEN_65 = ("ERROR: Two calls to the same user (@proefgebruiker) within 65 seconds is not allowed. This is to prevent "
              "the bot to overload the resources and colapse.")
_gel = BEL.gelukt
check("A13 het gemeten aanvaard-antwoord van CallMeBot telt als oproep", _gel([("telegram-oproep", GEMETEN_AANVAARD)]))
check("A13 een fout-antwoord van CallMeBot ('Error: user not available') telt niet als gebeld",
      not _gel([("telegram-oproep", "Error: user not available")]))
check("A13 een onbekend antwoord van CallMeBot is onzeker en telt niet als gebeld",
      not _gel([("telegram-oproep", "Onbekend antwoord van de dienst")]))
check("A13 de gemeten 65-secondenweigering telt niet als gebeld", not _gel([("telegram-oproep", GEMETEN_65)]))
check("A13 een fout na de autorisatie (in de staart van het antwoord) telt niet als gebeld",
      not _gel([("telegram-oproep", GEMETEN_AANVAARD + " Error: user not available")]))
check("A13 het vastzit-nummer (twilio-vast) telt alleen met een call-sid",
      _gel([("twilio-vast", "CA1")]) and not _gel([("twilio-vast", "")]) and not _gel([("twilio-vast", "mislukt: X")]))
_oud_user = os.environ.get("CALLMEBOT_USER")
os.environ["CALLMEBOT_USER"] = "@proef_error"
_v = _gel([("telegram-oproep", GEMETEN_AANVAARD.replace("@proefgebruiker", "@proef_error"))])
if _oud_user is None:
    os.environ.pop("CALLMEBOT_USER", None)
else:
    os.environ["CALLMEBOT_USER"] = _oud_user
check("A13 een gebruikersnaam met een foutwoord erin maakt een aanvaarde oproep niet mislukt", _v)

_tekst = "Mehdi, over vijf minuten online: proefafspraak met een lange zin die CallMeBot herhaalt. " * 3
_html = ("<html><body><p>Checking Authorization for @proefgebruiker...</p><p>Using bot: @CallMeBot_txtbot</p>"
         f"<p>Autorization OK</p><p>User:@proefgebruiker</p><p>Text to speech:{_tekst[:300]}</p>"
         "<p>Language:nl-NL-Standard-B</p><p>Error: user not available</p></body></html>")
_k, _fk = probeer(lambda: BEL.callmebot_antwoord(_html, _tekst[:300]))
check("A13 het antwoord van CallMeBot verliest zijn staart niet meer door onze herhaalde tekst",
      _fk is None and "(tekst)" in _k and "user not available" in _k and len(_k) <= 200 and not _gel([("telegram-oproep", _k)]),
      f"{_fk} {_k}")

for _antw, _verwacht in (("Onbekend antwoord van de dienst", False), ("Error: user not available", False),
                         (GEMETEN_AANVAARD, True)):
    rooster(regel("proef-cmb"))
    st, UITSLAG[0] = {}, [("telegram-oproep", _antw)]
    _u, _f = probeer(BEL.afspraken_bellen, st, log=B.ag.log)
    _ok = ("proef-cmb" in st.get("gebeld", {})) == _verwacht and (st.get("belpogingen", {}).get("proef-cmb") == (None if _verwacht else 1))
    check(f"A13 afspraken_bellen met CallMeBot-antwoord '{_antw[:40]}': {'gebeld' if _verwacht else 'niet gebeld, poging 1, volgende minuut opnieuw'}",
          _f is None and _ok, f"{_f} {st}")

# ------------------------------------------------------------------ ronde 4: A26, A33, A32 ---
# A26: een onzekere poging en een bewaarfout: ook dan stoppen, want de pogingenteller staat niet op schijf
rooster(regel_t("proef-e", "Proeftekst E"), regel_t("proef-f", "Proeftekst F"))
UITSLAG[0] = [("telegram-oproep", "een antwoord dat niemand kent")]
oproepen.clear()
_nood = []
_sp4 = str(TMP / "spoor-r4.jsonl")
_u, _f = probeer(BEL.afspraken_bellen, {}, log=B.ag.log, bewaar=kapotte_bewaar, nood=_nood, spoor=_sp4)
check("A26 ronde 4: een onzekere poging en een bewaarfout: geen volgende oproep, en een nood over de onzekere oproep",
      _f is None and oproepen == ["Proeftekst E"] and any("onzeker of mislukt" in n["tekst"] for n in _nood), f"{_f} {oproepen} {_nood}")

# A33: een spoor dat er is maar niet te lezen valt, is geen leeg spoor: niet bellen, wel melden
_onleesbaar = TMP / "spoor-is-een-map"
_onleesbaar.mkdir(exist_ok=True)
UITSLAG[0] = [("twilio", "CA91")]
oproepen.clear()
_nood = []
_u, _f = probeer(BEL.afspraken_bellen, {}, log=B.ag.log, bewaar=lambda st: True, nood=_nood, spoor=str(_onleesbaar))
check("A33 een onleesbaar belspoor: geen oproep, de belronde stopt met een nood",
      _f is None and oproepen == [] and any("onleesbaar" in n["tekst"] for n in _nood), f"{_f} {oproepen} {_nood}")

# A32: zonder leesbare stand belt De Bode geen alarm voor items die al op het bord stonden
schone_stand()
rooster()
B.is_stil, B.NIET_OP_TELEGRAM = (lambda t=None: False), ("agenda-wacht",)
BORD["items"] = klaarzet(range(301, 306), oproep=(303,))
alarm_oproepen.clear()
hartslagen.clear()
BEL_UIT[0] = "CA32"
probeer(B.main)
check("A32 zonder stand: een oproep-item op het bord geeft geen alarmoproep, wel een nood",
      alarm_oproepen == [] and bool(hartslagen) and any("geen leesbare stand" in n["tekst"] for n in (hartslagen[-1].get("nood") or [])),
      f"{alarm_oproepen} {hartslagen[-1:]}")
BORD["items"] = []
B.is_stil, B.NIET_OP_TELEGRAM = ECHT_STIL, ECHT_NIET_TG

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
