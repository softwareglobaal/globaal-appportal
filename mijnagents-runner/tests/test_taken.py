"""Grendel op toezeggingen en voorstellen ('Agendawacht - onderzoek en herstelvoorstel v1.1', A9-A11, FR-98 tot FR-100).

Bewijst: een toezegging voor later is een opgeslagen taak met ID (dubbel plannen geeft dezelfde taak); de taak overleeft
een herstart (andere verbinding) en volgt een verplaatste afspraak, vervalt bij een geschrapte; mislukt is een nieuwe
poging later tot het maximum; een voorstel heet pas gezet met een voorstel-ID uit het bord; een werkwijze van een agent
met regels in code wordt via het bord een regelwijziging-taak, geen losse tekst. Zonder netwerk en sleutels (ook CI).
"""
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

TMP = tempfile.mkdtemp()
os.environ["TAKEN_DB"] = os.path.join(TMP, "taken.db")
os.environ["BORD_DB"] = os.path.join(TMP, "bord.db")
os.environ["BELLEN_UIT"] = "1"

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import taken as T                     # noqa: E402
import regisseur as R                 # noqa: E402
import runbooks.werkwijze_bijwerken as WB   # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


nu = datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)

# --- A9: een toezegging is een opgeslagen taak met ID ------------------------------------------------------------
t1 = T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-10"}, "2026-10-02T15:00",
               reden="acht dagen voor de afspraak de titel nakijken", afspraak_kalender="werk", afspraak_id="ev1", afspraak_dag="2026-10-10")
t1b = T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-10"}, "2026-10-02T15:00")
check("een toezegging voor later is een opgeslagen taak met ID; dezelfde taak twee keer plannen geeft dezelfde taak",
      t1["id"] and t1b["id"] == t1["id"] and len(T.lijst()) == 1, str((t1, t1b)))
check("zonder tijdzone is het Brusselse tijd: 15:00 in Brussel is 13:00 UTC", t1["due_at"] == "2026-10-02T13:00:00+00:00"
      and t1["brussel"] == "02-10-2026 15:00", t1["due_at"])
c = sqlite3.connect(os.environ["TAKEN_DB"])
check("de taak staat in de opslag zelf, niet in het geheugen van het proces (overleeft een herstart)",
      c.execute("SELECT status FROM taak WHERE id=?", (t1["id"],)).fetchone() == ("gepland",))
c.close()
try:
    T.plannen("iets", "x", {}, nu)
    _onbekend = False
except ValueError:
    _onbekend = True
check("een onbekende soort wordt niet opgeslagen", _onbekend)
check("voor het moment is de taak niet te doen, daarna wel",
      not T.te_doen(nu) and [x["id"] for x in T.te_doen(nu + timedelta(hours=2))] == [t1["id"]])

# --- uitvoering door de Regisseur ----------------------------------------------------------------------------------
_rondes = []
R.voer_tool_uit_orig = R.voer_tool_uit


def _nep_tool(naam, inp):
    if naam == "agent_ronde":
        _rondes.append(dict(inp))
        return {"exit": _exit[0], "uitvoer": "klaar"}
    return R.voer_tool_uit_orig(naam, inp)


R.voer_tool_uit = _nep_tool
R.TAKEN_SLOT = os.path.join(TMP, "taken.slot")
_exit = [0]
R.afspraak_nu = lambda kal, aid: ("er", "2026-10-12")          # Mehdi verplaatste de afspraak van 10-10 naar 12-10
_g = R.taken_uitvoeren(nu + timedelta(hours=2))
_t = T.haal(t1["id"])
check("een taak aan een verplaatste afspraak volgt de afspraak: de ronde draait voor de nieuwe dag",
      _rondes and _rondes[-1].get("dag") == "2026-10-12" and _t["afspraak_dag"] == "2026-10-12", str((_rondes, _t)))
check("geslaagd heet pas geverifieerd met exitcode 0 en de uitvoer als bewijs",
      _g == [(t1["id"], "geverifieerd")] and _t["status"] == "geverifieerd" and "exit 0" in _t["bewijs"], str((_g, _t)))
check("een geverifieerde taak wordt niet opnieuw uitgevoerd", R.taken_uitvoeren(nu + timedelta(hours=3)) == [])

t2 = T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-20"}, nu, afspraak_kalender="werk",
               afspraak_id="ev2", afspraak_dag="2026-10-20")
R.afspraak_nu = lambda kal, aid: ("weg", None)
R.taken_uitvoeren(nu + timedelta(minutes=1))
check("een taak aan een geschrapte afspraak vervalt, zonder uitvoering", T.haal(t2["id"])["status"] == "vervallen"
      and not any(r.get("dag") == "2026-10-20" for r in _rondes))

t3 = T.plannen("agent_ronde", "agenda-wacht", {"naam": "agenda-wacht", "dag": "2026-10-21"}, nu)
_exit[0] = 75
R.taken_uitvoeren(nu + timedelta(minutes=1))
_t3 = T.haal(t3["id"])
check("een mislukte uitvoering (exit 75, slot bezet) is een nieuwe poging later, geen succes",
      _t3["status"] == "gepland" and _t3["pogingen"] == 1 and _t3["volgende"] > T._iso(nu), str(_t3))
_moment = nu
for _ in range(T.MAX_POGINGEN + 2):
    _moment = _moment + timedelta(hours=3)
    R.taken_uitvoeren(_moment)
_t3 = T.haal(t3["id"])
check(f"na {T.MAX_POGINGEN} pogingen heet de taak mislukt en wordt ze niet meer geprobeerd",
      _t3["status"] == "mislukt" and _t3["pogingen"] == T.MAX_POGINGEN, str(_t3))

_antw = R.voer_tool_uit_orig("taak_plannen", {"agent": "agenda-wacht", "wanneer": "2026-10-09T08:00", "reden": "titel nakijken",
                                              "dag": "2026-10-17"})
check("de tool taak_plannen geeft het taak-ID terug zoals het opgeslagen is",
      _antw.get("ok") and T.haal(_antw["taak_id"])["parameters"]["dag"] == "2026-10-17", str(_antw))
check("een taak voor een agent zonder runner wordt niet opgeslagen",
      R.voer_tool_uit_orig("taak_plannen", {"agent": "bestaat-niet", "wanneer": "2026-10-09T08:00", "reden": "x"}).get("ok") is False)

# --- A10: een voorstel heet pas gezet met een voorstel-ID uit het bord --------------------------------------------
b = sqlite3.connect(os.environ["BORD_DB"])
b.execute("CREATE TABLE voorstel (id INTEGER PRIMARY KEY, naam TEXT, actie TEXT, doel TEXT, reden TEXT, parameters TEXT, "
          "runbook TEXT, status TEXT DEFAULT 'open', besluit_door TEXT, besluit_ts TEXT, bewijs TEXT, ts TEXT)")
b.commit()
_bord_orig = R.bord


def _bord_valt_uit(pad, payload=None, method=None):
    raise OSError("bord onbereikbaar")


R.bord = _bord_valt_uit
_v1 = R.voer_tool_uit_orig("voorstel", {"actie": "Titel van deal 14474 aanpassen", "reden": "x", "runbook": "pipedrive-dealtitel",
                                        "parameters": {"deal_id": 14474, "titel": "2607 Robin"}})
check("valt het bord uit, dan zegt de voorstel-tool dat er niets staat (geen succes)", _v1.get("ok") is False, str(_v1))


def _bord_slikt(pad, payload=None, method=None):
    return {"ok": True}          # antwoordt, maar bewaart niets


R.bord = _bord_slikt
_v2 = R.voer_tool_uit_orig("voorstel", {"actie": "Titel van deal 14474 aanpassen", "reden": "x", "runbook": "pipedrive-dealtitel",
                                        "parameters": {"deal_id": 14474, "titel": "2607 Robin"}})
check("antwoordt het bord zonder het voorstel te bewaren, dan ook geen succes", _v2.get("ok") is False, str(_v2))


def _bord_bewaart(pad, payload=None, method=None):
    v = payload["voorstel"]
    b.execute("INSERT INTO voorstel(naam,actie,reden,parameters,runbook,ts) VALUES(?,?,?,?,?,?)",
              (payload["naam"], v["actie"], v["reden"], json.dumps(v["parameters"]) if v.get("parameters") else "", v["runbook"], "nu"))
    b.commit()
    return {"ok": True}


R.bord = _bord_bewaart
_v3 = R.voer_tool_uit_orig("voorstel", {"actie": "Titel van deal 14474 aanpassen", "reden": "x", "runbook": "pipedrive-dealtitel",
                                        "parameters": {"deal_id": 14474, "titel": "2607 Robin"}})
check("een voorstel heet pas gezet met een voorstel-ID uit het bord", _v3.get("ok") is True and _v3.get("voorstel_id") == 1, str(_v3))
R.bord = _bord_orig

# --- A11: een werkwijze met regels in code wordt een regelwijziging, geen losse tekst op het bord ------------------
WB.REGELWIJZIGINGEN = os.path.join(TMP, "regelwijzigingen")
_aanroep = []
WB.urllib.request.urlopen = lambda *a, **k: _aanroep.append(a) or (_ for _ in ()).throw(AssertionError("geen bord"))
_r = WB.voer_uit({"agent": "agenda-wacht", "werkwijze": "Versie 9.0 (nieuw) " + "x" * 300})
_rw = [t for t in T.lijst() if t["soort"] == "regelwijziging"]
check("een regelwijziging via het bord wordt een taak voor de ontwikkelaar, niet alleen tekst op het bord",
      not _aanroep and "niet rechtstreeks op het bord" in _r[0] and len(_rw) == 1 and _rw[0]["eigenaar"] == "claude"
      and Path(_rw[0]["parameters"]["tekst"]).read_text(encoding="utf-8").startswith("Versie 9.0"), str((_r, _rw)))
_voor = len(_rondes)
_exit[0] = 0
R.taken_uitvoeren(datetime.now(timezone.utc) + timedelta(days=30))
check("de Regisseur voert een regelwijziging nooit zelf uit: ze blijft gepland voor de ontwikkelaar",
      T.haal(_rw[0]["id"])["status"] == "gepland" and not any(r.get("naam") == "agenda-wacht" and not r.get("dag") for r in _rondes[_voor:]),
      str((T.haal(_rw[0]["id"]), _rondes[_voor:])))

_src = (HIER / "regisseur.py").read_text(encoding="utf-8")
_blok = _src[_src.index("def taken_uitvoeren"):_src.index("def antwoord(")]
check("de uitvoering gebruikt een klok: elke taken.zet krijgt het tijdstip van de ronde mee (FR-103)",
      _blok.count("taken.zet(") == _blok.count("nu=nu)") > 0, str((_blok.count("taken.zet("), _blok.count("nu=nu)"))))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
