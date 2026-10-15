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
_ok_ev = lambda a, tok: {"status": "confirmed", "start": {"dateTime": _t}}
with vervang((W.bellen, "ROOSTER", _ro), (W, "_event", _ok_ev), (W.agenda, "_toegang", lambda: "t")):
    _beh = veilig(lambda: W._rooster_behouden([], {"ongelezen@agenda.test"}))
check("A15 de komende oproep van de ongelezen agenda blijft, die van een gelezen agenda niet",
      isinstance(_beh, list) and [r["sleutel"].split(":")[1] for r in _beh] == ["x1"], str(_beh))
_later_t = (W.nu_lokaal() + timedelta(hours=5)).isoformat()
for naam, ev in (("geschrapt", lambda a, tok: {"status": "cancelled", "start": {"dateTime": _t}}),
                 ("verzet", lambda a, tok: {"status": "confirmed", "start": {"dateTime": _later_t}}),
                 ("niet te lezen", lambda a, tok: (_ for _ in ()).throw(OSError("503")))):
    with vervang((W.bellen, "ROOSTER", _ro), (W, "_event", ev), (W.agenda, "_toegang", lambda: "t")):
        _beh = veilig(lambda: W._rooster_behouden([], {"ongelezen@agenda.test"}))
    check(f"A15 ronde 4: een behouden oproep voor een afspraak die {naam} is, valt weg en telt als onzeker",
          _beh == [] and getattr(W, "ROOSTER_ONZEKER", 0) == 1, f"{_beh} {getattr(W, 'ROOSTER_ONZEKER', None)}")
# A15 en A29 (ronde 5): het belrooster van de ronde, als gedrag in plaats van tekst
_A15 = afspraak("A15", "Mehdi: [HA-PO] Jan Proef")
_kijk = []


def _rm(tweede, ev):
    _kijk.clear()
    noden = []
    W.ONGELEZEN.clear()
    W.ARCHIEF_FOUT = ""

    def _ev(a, tok):
        _kijk.append(a["id"])
        return ev(a)
    with vervang((W, "afspraken", lambda v, t: list(tweede)), (W, "archief_afspraken", lambda v, t: []), (W, "_event", _ev),
                 (W.agenda, "_toegang", lambda: "t")):
        r = veilig(lambda: W.rooster_maken([dict(_A15)], [], W.nu_lokaal().date().isoformat(), noden))
    return r, noden


_r, _n = _rm([dict(_A15)], lambda a: {"status": "confirmed", "start": {"dateTime": _A15["start"]}})
check("A15 ronde 5: de tweede lezing lukt: het rooster komt eruit, zonder nakijken", isinstance(_r, list)
      and [x["sleutel"].split(":")[1] for x in _r] == ["A15"] and _kijk == [] and _n == [], f"{_r} {_kijk} {_n}")
_r, _n = _rm([{"kalender": W.WERKAGENDA, "fout": "HTTP 503"}], lambda a: {"status": "cancelled", "start": {"dateTime": _A15["start"]}})
check("A15 ronde 5: de tweede lezing faalt en de afspraak is intussen geschrapt: geen oproep, wel een nood",
      isinstance(_r, list) and _r == [] and _kijk == ["A15"] and any("vielen weg" in n["tekst"] for n in _n), f"{_r} {_kijk} {_n}")
_r, _n = _rm([{"kalender": W.WERKAGENDA, "fout": "HTTP 503"}], lambda a: {"status": "confirmed", "start": {"dateTime": _A15["start"]}})
check("A15 ronde 5: de tweede lezing faalt maar de afspraak staat er nog zo: de oproep blijft",
      isinstance(_r, list) and [x["sleutel"].split(":")[1] for x in _r] == ["A15"] and _n == [], f"{_r} {_n}")
check("A15 de ronde schrijft het rooster uit rooster_maken", "rooster = rooster_maken(items, archief, vandaag, mail_noden)" in _bron)

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

# ------------------------------------------------------------------ ronde 4 ---
# A10: een rit hoort alleen bij een afspraak op zijn eigen agenda
_e0 = _later
_rit10 = {"id": "r10", "kalender": W.WERKAGENDA, "titel": "\U0001F697 Reistijd: thuis → Leuven", "start": (_e0 - timedelta(minutes=30)).isoformat(),
          "einde": _e0.isoformat(), "omschrijving": "Reistijd voor: !! Mehdi: [HA-KB] 2601 - X (30 min, OSRM)"}
_elders = {**afspraak("y10", "!! Mehdi: [HA-KB] 2601 - X"), "kalender": "andere@agenda.test"}
check("A10 ronde 4: een rit op agenda A hoort niet bij een afspraak met dezelfde titel op agenda B",
      veilig(lambda: W._afspraak_van_rit(_rit10, [_elders], _e0 - timedelta(minutes=30), _e0)) == [])

# A11: geen 'geen rit'-melding als er al een rit staat, of buiten de gevraagde dag
_b11 = afspraak("b11", "!! Mehdi: [HA-KB] 2601 - X", locatie="Proefstraat 1, 3000 Leuven")
with vervang((W, "geen_auto_dagen", lambda: None), (W, "lara_vakantiedagen", lambda: frozenset()), (W, "_cache_laden", lambda: {}),
             (W, "_cache_bewaren", lambda c: None), (W, "coord", lambda *a, **k: (50.88, 4.70)), (W.projectadressen, "index", lambda: {}),
             (W, "_insert", lambda *a, **k: {}), (W, "_patch", lambda *a, **k: None), (W.agenda, "_toegang", lambda: "t"),
             (W, "_eigen_rit_weg", lambda *a: False), (W, "_verplaats", lambda *a: None)):
    _r11a = veilig(lambda: W.reistijd_zetten([dict(_b11), dict(_rit10)]))
    _r11b = veilig(lambda: W.reistijd_zetten([dict(_b11)], alleen_dag="2000-01-01"))
check("A11 ronde 4: een buitenafspraak die al een rit heeft, staat niet als 'geen rit' in de meldingen",
      isinstance(_r11a, tuple) and not any("grendelbron niet te lezen" in x and "2601" in x for x in _r11a[4]), str(_r11a)[:300])
check("A11 ronde 4: buiten de gevraagde dag geen melding", isinstance(_r11b, tuple) and not any("grendelbron niet te lezen" in x for x in _r11b[4]))

# A25: een rit die naar een verdwenen privé-afspraak verwijst, herhaalt die titel niet; de tekst van een privé-bevinding ook niet
_zr = veilig(lambda: Z.bevindingen([{**_rit10, "omschrijving": "Reistijd voor: [PR] Proefconsult geheim (30 min, OSRM)"}],
                                   _later.date().isoformat(), _later.date().isoformat(), W.nu_lokaal()))
check("A25 ronde 4: een rit naar een verdwenen privé-afspraak noemt die titel niet",
      isinstance(_zr, list) and not any("Proefconsult" in b["tekst"] for b in _zr), str(_zr)[:300])
_zo = io.StringIO()
with redirect_stdout(_zo), vervang((W, "afspraken", lambda v, t: [afspraak("pz", "Mehdi: [PR] x")]),
                                   (W, "archief_afspraken", lambda v, t: []), (Z, "omgeving", lambda nu: []),
                                   (Z, "bevindingen", lambda items, van, tot, nu: [{"controle": "titel", "dag": items[0]["start"][:10],
                                    "uur": "14:00", "agenda": "", "titel": "x", "tekst": "Proefconsult geheim", "door": "", "prive": True}]),
                                   (Z, "STAND", Path(TMP) / "zelfcontrole2.json")):
    veilig(lambda: Z.main())
check("A25 ronde 4: de zelfcontrole drukt ook de tekst van een privé-bevinding niet af", "Proefconsult" not in _zo.getvalue(),
      _zo.getvalue()[-200:])

# A11 (ronde 5): een rit met dezelfde titel op een andere agenda onderdrukt de melding niet
_rit_ander = {**_rit10, "id": "r11", "kalender": "andere@agenda.test"}
with vervang((W, "geen_auto_dagen", lambda: None), (W, "lara_vakantiedagen", lambda: frozenset()), (W, "_cache_laden", lambda: {}),
             (W, "_cache_bewaren", lambda c: None), (W, "coord", lambda *a, **k: (50.88, 4.70)), (W.projectadressen, "index", lambda: {}),
             (W, "_insert", lambda *a, **k: {}), (W, "_patch", lambda *a, **k: None), (W.agenda, "_toegang", lambda: "t"),
             (W, "_eigen_rit_weg", lambda *a: False), (W, "_verplaats", lambda *a: None)):
    _r11c = veilig(lambda: W.reistijd_zetten([dict(_b11), dict(_rit_ander)]))
check("A11 ronde 5: een rit met dezelfde titel op een andere agenda onderdrukt de melding 'geen rit' niet",
      isinstance(_r11c, tuple) and any("grendelbron niet te lezen" in x and "2601" in x for x in _r11c[4]), str(_r11c)[:300])

# A15 (ronde 6): faalt agenda B in de tweede lezing, dan komt agenda A uit de verse lezing, en de inhoud wordt herbeoordeeld
_X = {**afspraak("X6", "Mehdi: [HA-PO] Xavier Proef"), "kalender": W.WERKAGENDA}
_Y = {**afspraak("Y6", "Mehdi: [HA-PO] Yara Proef"), "kalender": "b@agenda.test"}
_kijk6, _n6 = [], []
W.ONGELEZEN.clear()
W.ARCHIEF_FOUT = ""
with vervang((W, "afspraken", lambda v, t: [{"kalender": "b@agenda.test", "fout": "HTTP 503"}]), (W, "archief_afspraken", lambda v, t: []),
             (W, "_event", lambda a, tok: _kijk6.append(a["id"]) or {"status": "confirmed", "start": {"dateTime": _Y["start"]},
                                                                     "end": {"dateTime": _Y["einde"]}, "summary": _Y["titel"]}),
             (W.agenda, "_toegang", lambda: "t")):
    _r6 = veilig(lambda: W.rooster_maken([dict(_X), dict(_Y)], [], W.nu_lokaal().date().isoformat(), _n6))
check("A15 ronde 6: een afspraak op de wel gelezen agenda die er de tweede keer niet meer staat, krijgt geen oproep",
      isinstance(_r6, list) and [x["sleutel"].split(":")[1] for x in _r6] == ["Y6"] and _kijk6 == ["Y6"], f"{_r6} {_kijk6}")
with vervang((W, "afspraken", lambda v, t: [{"kalender": "b@agenda.test", "fout": "HTTP 503"}]), (W, "archief_afspraken", lambda v, t: []),
             (W, "_event", lambda a, tok: {"status": "confirmed", "start": {"dateTime": _Y["start"]}, "end": {"dateTime": _Y["einde"]},
                                           "summary": "Mehdi: [HA-IN] intern overleg"}), (W.agenda, "_toegang", lambda: "t")):
    _r6b = veilig(lambda: W.rooster_maken([dict(_Y)], [], W.nu_lokaal().date().isoformat(), []))
check("A15 ronde 6: een afspraak die intussen intern werd, krijgt geen oude oproep", _r6b == [], str(_r6b))

# A11 (ronde 6): twee afspraken met dezelfde titel op dezelfde dag: de rit van de eerste dekt de tweede niet
_b11b = {**_b11, "id": "b11b", "start": (_later + timedelta(hours=3)).isoformat(), "einde": (_later + timedelta(hours=4)).isoformat()}
with vervang((W, "geen_auto_dagen", lambda: None), (W, "lara_vakantiedagen", lambda: frozenset()), (W, "_cache_laden", lambda: {}),
             (W, "_cache_bewaren", lambda c: None), (W, "coord", lambda *a, **k: (50.88, 4.70)), (W.projectadressen, "index", lambda: {}),
             (W, "_insert", lambda *a, **k: {}), (W, "_patch", lambda *a, **k: None), (W.agenda, "_toegang", lambda: "t"),
             (W, "_eigen_rit_weg", lambda *a: False), (W, "_verplaats", lambda *a: None)):
    _r11d = veilig(lambda: W.reistijd_zetten([dict(_b11), dict(_b11b), dict(_rit10)]))
check("A11 ronde 6: de rit van de eerste afspraak dekt de tweede met dezelfde titel niet",
      isinstance(_r11d, tuple) and sum(1 for x in _r11d[4] if "grendelbron niet te lezen" in x) == 1, str(_r11d)[:300])

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
