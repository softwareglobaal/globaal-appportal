"""Grendels uit de Codex-controle ronde 3 van De Agendawacht (restpunten van ronde 1 en 2, 15-10-2026; FR-158 en verder).
Zonder netwerk en sleutels (ook CI). Alle namen, adressen en links zijn verzonnen. Elke controle faalt op e8d9faf, behalve
de tegenproeven die bestaand gedrag vastzetten.
"""
import io
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import timedelta
from pathlib import Path

os.environ["TZ"] = "UTC"          # zoals de VM
time.tzset()
TMP = tempfile.mkdtemp()
os.environ.update({"BELLEN_UIT": "1", "MAIL_AFSPRAKEN_DB": os.path.join(TMP, "afspraken_mail.db")})
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W     # noqa: E402
import mail_afspraken as MA  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def veilig(f):
    try:
        return f()
    except Exception as e:  # noqa: BLE001
        return e


@contextmanager
def vervang(*paren):
    oud = [(obj, naam, getattr(obj, naam)) for obj, naam, _ in paren]
    try:
        for obj, naam, waarde in paren:
            setattr(obj, naam, waarde)
        yield
    finally:
        for obj, naam, waarde in oud:
            setattr(obj, naam, waarde)


_later = (W.nu_lokaal() + timedelta(days=2)).replace(hour=14, minute=0, second=0, microsecond=0)


def afspraak(id_, titel, **extra):
    return {"id": id_, "titel": titel, "start": _later.isoformat(), "einde": (_later + timedelta(minutes=30)).isoformat(),
            "kalender": W.WERKAGENDA, "locatie": "", "omschrijving": "", **extra}


# A05: een privécode op de werkagenda is privé
check("A05 '[PR]' en '[LA]' op de werkagenda zijn privé, een firmacode niet",
      W.is_prive(afspraak("p", "Mehdi: [PR] etentje")) and W.is_prive(afspraak("l", "Mehdi: [LA] ophalen"))
      and not W.is_prive(afspraak("h", "Mehdi: [HA-KB] 2601 - Jan Proef")))

# A09, A24: een collega als agendagast telt ook als gast
_gz = []
with vervang((W, "_patch", lambda a, body, tok, toch=False: _gz.append(a["id"])), (W.agenda, "_toegang", lambda: "t"),
             (W, "_volledige_omschrijving", lambda a, tok: "")):
    W.zoom_zetten([afspraak("collega", "Mehdi: [HA-PO] Jan Proef", _agendagasten=["collega@voorbeeld.test"])])
check("A09 ZL schrijft niet in een afspraak met een collega als gast", _gz == [], str(_gz))
_vr = []
with vervang((W, "_patch", lambda a, body, tok, toch=False: _vr.append(a["id"])), (W.agenda, "_toegang", lambda: "t"),
             (W.projectadressen, "index", lambda: {}), (W.zoom, "beschikbaar", lambda *x, **k: False)):
    W.vragen_in_agenda([afspraak("een-eigen-afspraak-lang", "Mehdi: [HA-KO] 2601 - Jan Proef", _agendagasten=["collega@voorbeeld.test"]),
                        afspraak("twee-eigen-afspraak-lang", "Mehdi: [HA-PO] Piet Proef")])
check("A24 geen VR in een afspraak met een collega als gast; de eigen afspraak zonder gasten wel",
      "een-eigen-afspraak-lang" not in _vr and "twee-eigen-afspraak-lang" in _vr, str(_vr))

# A11: een onleesbare geen-autobron noemt elke getroffen buitenafspraak
with vervang((W, "geen_auto_dagen", lambda: None), (W, "lara_vakantiedagen", lambda: frozenset()), (W, "_cache_laden", lambda: {}),
             (W, "_cache_bewaren", lambda c: None), (W, "coord", lambda *a, **k: (50.88, 4.70)), (W.projectadressen, "index", lambda: {}),
             (W, "_insert", lambda *a, **k: {}), (W, "_patch", lambda *a, **k: None), (W.agenda, "_toegang", lambda: "t")):
    _r = veilig(lambda: W.reistijd_zetten([afspraak("b1", "!! Mehdi: [HA-KB] 2601 - Jan Proef", locatie="Proefstraat 1, 3000 Leuven")]))
check("A11 geen-autodagen onbekend: de buitenafspraak staat apart in de meldingen",
      isinstance(_r, tuple) and any("2601 - Jan Proef" in x and "grendelbron niet te lezen" in x for x in _r[4]), str(_r)[:300])
_bron = (HIER / "agenda_wacht.py").read_text(encoding="utf-8")
check("A11 die regels worden een eigen nood ('grendelbron niet te lezen')", '"grendelbron niet te lezen (geen auto of vakantie)"' in _bron)

# A14: een rit op titel telt alleen op dezelfde agenda
_d = _later.replace(hour=11, minute=0)
_A = {**afspraak("A", "!! Mehdi: [HA-KB] 2601 - Alfa Proef"), "start": _d.isoformat(), "einde": (_d + timedelta(hours=1)).isoformat(),
      "locatie": "Proefstraat 1, 3000 Leuven"}
_rit_elders = {**afspraak("rE", "\U0001F697 Reistijd: thuis → Leuven"), "kalender": "andere@agenda.test",
               "start": (_d - timedelta(minutes=50)).isoformat(), "einde": (_d - timedelta(minutes=10)).isoformat(),
               "omschrijving": f"Reistijd voor: {_A['titel']} (40 min, OSRM)"}
_rb = {r["sleutel"].split(":")[1]: r["tijd"][11:16] for r in W.belrooster([_A, _rit_elders], _d.date().isoformat())}
check("A14 een rit met dezelfde titel op een andere agenda bepaalt het vertrek niet", _rb.get("A") != "10:05", str(_rb))

# A15: een onvolledige lezing behoudt de komende oproepen van de ongelezen agenda
_ro = os.path.join(TMP, "belrooster.json")
_t = (W.nu_lokaal() + timedelta(hours=3)).isoformat()
json.dump({"regels": [{"sleutel": "ongelezen@agenda.test:x1:" + _t, "tijd": _t, "tekst": "t", "titel": "a"},
                      {"sleutel": W.WERKAGENDA + ":x2:" + _t, "tijd": _t, "tekst": "t", "titel": "b"}]}, open(_ro, "w"))
with vervang((W.bellen, "ROOSTER", _ro)):
    _beh = veilig(lambda: W._rooster_behouden([], {"ongelezen@agenda.test"}))
check("A15 de komende oproep van de ongelezen agenda blijft, die van een gelezen agenda niet",
      isinstance(_beh, list) and [r["sleutel"].split(":")[1] for r in _beh] == ["x1"], str(_beh))
check("A15 de ronde vult het rooster aan bij een onvolledige lezing", "_rooster_behouden(rooster, _onvolledig)" in _bron)

# A20: een jaartal is geen projectnummer
check("A20 'Project 2615 overleg 2026' koppelt niet aan 'Project 2614 overleg 2026'; hetzelfde nummer wel",
      MA.zelfde_onderwerp("Project 2615 overleg 2026", "Project 2614 overleg 2026") is False
      and MA.zelfde_onderwerp("Project 2615 overleg", "Mehdi: [HA-IN] 2615 Project overleg") is True)

# A25: foutpaden en de zelfcontrole drukken geen privétitel af
_uit = io.StringIO()
with redirect_stderr(_uit), vervang((W, "_patch", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x"))), (W.agenda, "_toegang", lambda: "t")):
    veilig(lambda: W.herinneringen_zetten([afspraak("pr", "Mehdi: [PR] Proefconsult", omschrijving="", _reminders={})]))
check("A25 een mislukte herinnering op een privé-afspraak noemt de titel niet in het logboek", "Proefconsult" not in _uit.getvalue(),
      _uit.getvalue()[:200])
check("A25 _toon geeft '(privé)' voor een privé-afspraak", veilig(lambda: W._toon(afspraak("pr", "Mehdi: [PR] Proefconsult"))) == "(privé)")
import zelfcontrole as Z      # noqa: E402
_zo = io.StringIO()
with redirect_stdout(_zo), vervang((W, "afspraken", lambda v, t: [afspraak("pz", "Mehdi: [PR] Proefconsult ZL")]),
                                   (W, "archief_afspraken", lambda v, t: []), (Z, "omgeving", lambda nu: []),
                                   (Z, "bevindingen", lambda items, van, tot, nu: [{"controle": "titel", "dag": items[0]["start"][:10],
                                    "uur": "14:00", "agenda": "", "titel": items[0]["titel"], "tekst": "proef", "door": "", "prive": True}]),
                                   (Z, "STAND", Path(TMP) / "zelfcontrole.json")):
    veilig(lambda: Z.main())
check("A25 de zelfcontrole drukt een privé-bevinding af zonder titel", "Proefconsult" not in _zo.getvalue(), _zo.getvalue()[-300:])

# A30: de zelfcontrole gebruikt dezelfde vergaderlinkregel als de agent
_zb = veilig(lambda: Z.bevindingen([afspraak("zl", "ZL Mehdi: [HA-PO] Jan Proef", omschrijving="https://www.dropbox.com/s/voorbeeld")],
                                   _later.date().isoformat(), _later.date().isoformat(), W.nu_lokaal()))
check("A30 ZL met alleen een documentlink is in de zelfcontrole geen fout 'ZL terwijl er een link in staat'",
      isinstance(_zb, list) and not any("ZL terwijl" in b["tekst"] for b in _zb), str(_zb)[:300])

# A07: een nieuw zorgblok wordt ook op titel, herinnering en merk teruggelezen
_body = {"summary": "!! [PR] Kine - Proef", "start": {"dateTime": _later.isoformat()}, "end": {"dateTime": (_later + timedelta(minutes=30)).isoformat()},
         "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": 30}]},
         "extendedProperties": {"private": {W.ZORGMERK: "zorg|p|x"}}}
_terug = {"start": _body["start"], "end": _body["end"], "transparency": "opaque", "summary": "Kine", "reminders": {"useDefault": True}}
with vervang((W, "_lees_event", lambda kal, eid, tok: dict(_terug))):
    _p = veilig(lambda: W._zorg_teruglezen(W.PRIVE_AGENDA, "e1", _body, "t"))
check("A07 een zorgblok zonder titel, herinnering of merk heet niet 'gezet'",
      isinstance(_p, str) and all(w in _p for w in ("titel", "herinnering", "merk")), repr(_p))

# A29: de live tak van test_agenda_taken draait alleen met --live
_tt = (HIER / "tests" / "test_agenda_taken.py").read_text(encoding="utf-8")
check("A29 test_agenda_taken gaat alleen met --live naar buiten, ook als er sleutels zijn",
      'LIVE = _live_sleutels() if "--live" in sys.argv else {}' in _tt)

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
