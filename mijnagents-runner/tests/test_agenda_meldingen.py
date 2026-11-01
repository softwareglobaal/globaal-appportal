"""Grendel op de meldingen van De Agendawacht (T-0120, meting 01-10 tot 01-11-2026, groep agenda).

- AG-3: twee titelredenen met hetzelfde begin geven twee sleutels, dus twee blijvende borditems;
- AG-4: 'zonder adres' kent dezelfde adresbronnen als de reistijd (vaste plek, locatie.globaal.be, projectmap); een KO
  zonder nummer geeft alleen de nummermelding; elke afspraak staat in hoogstens een nood, ook zonder nummer en adres
  samen, en twee afspraken op dezelfde minuut blijven twee; een B&S-bezoek geeft dezelfde uitkomst als voordien;
- AG-5: 'Link doorsturen of titel nakijken' is een signaal per dag, met de regels van alle rondes van die dag samen
  (57 dagrondes op 29-10-2026 gaven 57 signalen); een nieuwe dag begint leeg; geen sleutel op de inhoud; ook na het
  oppakken komen nieuwe regels op het bord;
- op het echte bord (mijnagents/app.py, tijdelijke databank): de twee titelsignalen van AG-3 blijven twee items, en een
  ingekorte privétitel uit een titelsignaal komt als '(privé)' op de wachtenpagina, zonder rest (AG-2, Codex-toets 1).

Verzonnen voorbeelden, geen echte namen. Draaien: python3 mijnagents-runner/tests/test_agenda_meldingen.py
"""
import ast
import atexit
import inspect
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "koppelingen"), str(ROOT / "planning")]
os.environ["BELLEN_UIT"] = "1"
PROEF_HOME = tempfile.TemporaryDirectory(prefix="agenda-meldingen-proef-")
atexit.register(PROEF_HOME.cleanup)
os.environ["HOME"] = PROEF_HOME.name
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(PROEF_HOME.name, "agenda-whatsapp.json"))
import organisatie as ORGANISATIE  # noqa: E402
ORGANISATIE.firmas = lambda maximum_uren=24: [{"code": "HARC", "code_contact": "HA", "code_agenda": "HA",
                                                "naam": "H-Architects", "land": "BE", "actief": True}]
import agenda_wacht as W  # noqa: E402

BRON = (ROOT / "agenda_wacht.py").read_text(encoding="utf-8")
ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print("ok   " + naam)
    else:
        fout += 1
        print("FOUT " + naam + (f" ({extra})" if extra else ""))


# --- AG-3: sleutelbotsing bij titelsignalen
DAG = "2026-10-29"
A = "geen firmacode, wellicht [AA]"
B = "geen firmacode, wellicht [BB]"
check("AG-3 de oude sleutel botste: hetzelfde begin van twintig tekens", f"agenda-titel-{A[:20]}:{DAG}" == f"agenda-titel-{B[:20]}:{DAG}")
check("AG-3 twee redenen met hetzelfde begin geven twee sleutels", W.titel_uniek(A, DAG) != W.titel_uniek(B, DAG),
      f"{W.titel_uniek(A, DAG)} {W.titel_uniek(B, DAG)}")
check("AG-3 dezelfde reden op dezelfde dag geeft dezelfde sleutel (geen nieuw item per ronde)",
      W.titel_uniek(A, DAG) == W.titel_uniek(A, DAG) and W.titel_uniek(A, DAG) != W.titel_uniek(A, "2026-10-30"))
check("AG-3 de sleutel eindigt op de dag (de wachtenpagina vindt hem op ':<dag>')", W.titel_uniek(A, DAG).endswith(f":{DAG}"))
check("AG-3 de ronde gebruikt titel_uniek voor de titelsignalen",
      '"uniek": titel_uniek(reden, vandaag)' in BRON and 'f"agenda-titel-{reden[:20]}:{vandaag}"' not in BRON)

# --- AG-4: 'zonder adres' kent dezelfde bronnen als de reistijd, het nummer is een eigen melding, een afspraak een melding
import json  # noqa: E402
with open(ROOT / "werkwijze" / "agenda-taken.json", encoding="utf-8") as _bron:
    W.nummerlezer._master = lambda _r=json.load(_bron)["titelconventie"]: _r
_oud4 = (W.plek_zoeken, W.vaste_plek, W.projectadressen.index)
VASTE = {"proefbank": {"adres": "Proefstraat 1, 1000 Brussel"}}
W.plek_zoeken = lambda tekst: ((None, None) if "proefschool" not in tekst else ("Schoolweg 2, 1000 Brussel", "proefschool"))
W.vaste_plek = lambda titel: next(((w, v) for w, v in VASTE.items() if w in titel.lower()), (None, None))
W.projectadressen.index = lambda: {"2699": {"adres": "Projectlaan 3, 1000 Brussel"}}
try:
    MORGEN = (W.nu_lokaal().date() + W.timedelta(days=1)).isoformat()

    def afspraak(titel, uur="10:00", locatie=""):
        return {"kalender": W.WERKAGENDA, "id": f"id-{uur}", "titel": titel, "start": f"{MORGEN}T{uur}:00+01:00",
                "einde": f"{MORGEN}T{uur[:2]}:59:00+01:00", "locatie": locatie, "omschrijving": ""}

    vast = W.onvolledige_afspraken([afspraak("!! Mehdi: [HA-PB] kennismaking proefbank")], MORGEN)
    check("AG-4 een buitenafspraak met een vaste plek geeft geen adresmelding", vast == [], vast)
    plek = W.onvolledige_afspraken([afspraak("!! Mehdi: [HA-PB] ouderavond proefschool")], MORGEN)
    check("AG-4 een buitenafspraak met een plek uit locatie.globaal.be geeft geen adresmelding", plek == [], plek)
    proj = W.onvolledige_afspraken([afspraak("Mehdi: [HA-KB] 2699 - proefklant")], MORGEN)
    check("AG-4 een klantbezoek met een projectmap geeft geen adresmelding", proj == [], proj)
    geen = W.onvolledige_afspraken([afspraak("!! Mehdi: [HA-PB] proefprospect", "08:00")], MORGEN)
    check("AG-4 een buitenafspraak zonder enige bron blijft gemeld", len(geen) == 1 and "geen adres" in geen[0], geen)

    bs = afspraak("!! Mehdi: [HA-KB] 2698 - BS proefpersoon, Proefstraat 5, 3600 Proefstad", "13:00",
                  "Proefstraat 5, 3600 Proefstad")
    check("AG-4 B&S: een bezoek barsten en scheuren met adres geeft geen melding en geen adresvraag (zoals voordien)",
          W.onvolledige_afspraken([bs], MORGEN) == [] and W._adresvragen([bs]) == [])
    bs_zonder = dict(bs, locatie="")
    check("AG-4 B&S: zonder adresveld en zonder projectmap blijft het bezoek gemeld (zoals voordien)",
          len(W.onvolledige_afspraken([bs_zonder], MORGEN)) == 1 and len(W._adresvragen([bs_zonder])) == 1)
    TEKST = {"nummer": "Klantafspraken zonder projectnummer in de titel: zet het nummer erin",
             "adres": "Buitenafspraken zonder adres: zonder adres kan ik geen reistijd berekenen",
             "rit": "Buitenafspraken zonder reistijd, reden: geen adres in de agenda"}

    def teksten(noden):
        return [n["tekst"] for n in noden]

    ko_a = afspraak("Mehdi: [HA-KO] proefklant", "11:00", "https://zoom.example.test/j/1")
    ko = W.onvolledig_per_afspraak([ko_a], MORGEN)
    check("AG-4 een KO zonder nummer geeft alleen de nummermelding",
          teksten(W.adres_noden({}, ko, [])) == [TEKST["nummer"]], ko)

    # Een afspraak van 08:00 zonder adres: de reistijd zegt 'geen adres in de agenda', de adresvraag kon geen VR zetten,
    # en 'zonder adres' ziet haar ook. Tot 01-11-2026 waren dat drie meldingen voor dezelfde afspraak.
    pb = afspraak("!! Mehdi: [HA-PB] proefprospect", "08:00")
    geen_a = W.onvolledig_per_afspraak([pb], MORGEN)
    zr = {"geen adres in de agenda": [f"{pb['start'][:16]} {W._toon(pb, 50)}"], "adres niet gevonden": []}
    check("AG-4 een afspraak geeft een melding: de adresvraag gaat voor, de rest zwijgt", W.adres_noden(zr, geen_a, [pb]) == [])
    check("AG-4 zonder adresvraag blijft de reden van de reistijd de enige melding",
          teksten(W.adres_noden(zr, geen_a, [])) == [TEKST["rit"]])
    check("AG-4 wat de reistijd niet zag, krijgt nog 'zonder adres'", teksten(W.adres_noden({}, geen_a, [])) == [TEKST["adres"]])
    ander = W.adres_noden({"rit zonder afspraak": [f"{MORGEN}T16:00 Reistijd: proef: rit zonder afspraak"]}, [], [pb])
    check("AG-4 een andere reden van de reistijd blijft gewoon gemeld",
          teksten(ander) == ["Buitenafspraken zonder reistijd, reden: rit zonder afspraak"], ander)

    # Codex-toets 1: een klantbezoek zonder nummer en zonder adres staat in een nood, niet in twee
    kb = afspraak("Mehdi: [HA-KB] proefklant zonder nummer", "14:00")
    kb_a = W.onvolledig_per_afspraak([kb], MORGEN)
    check("AG-4 een klantbezoek zonder nummer en zonder adres: in het signaal allebei, in de noden een",
          "geen projectnummer" in kb_a[0][1] and any(w.startswith("geen adres") for w in kb_a[0][1])
          and teksten(W.adres_noden({}, kb_a, [])) == [TEKST["adres"]], kb_a)
    kb_rit = {"geen adres in de agenda": [f"{kb['start'][:16]} {W._toon(kb, 50)}"]}
    check("AG-4 hetzelfde bezoek met een reistijdreden: alleen die reden", teksten(W.adres_noden(kb_rit, kb_a, [])) == [TEKST["rit"]])
    # Codex-toets 1: twee afspraken op dezelfde minuut drukken elkaars nood niet weg
    tweede = dict(afspraak("!! Mehdi: [HA-PB] andere proefprospect", "08:00"), id="id-tweede")
    beide = W.onvolledig_per_afspraak([pb, tweede], MORGEN)
    check("AG-4 twee afspraken op dezelfde minuut: de adresvraag van de ene verbergt de andere niet",
          teksten(W.adres_noden({}, beide, [pb])) == [TEKST["adres"]], beide)
    check("AG-4 twee afspraken op dezelfde minuut: de reistijdregel van de ene verbergt de andere niet",
          teksten(W.adres_noden(zr, beide, [], [pb, tweede])) == [TEKST["rit"], TEKST["adres"]])
    # Codex-toets 2: twee titels op dezelfde minuut waarvan de ene met de andere begint
    kort_a = dict(afspraak("!! Mehdi: [HA-PB] proef", "15:00"), id="id-kort")
    lang_a = dict(afspraak("!! Mehdi: [HA-PB] proef bij de klant", "15:00"), id="id-lang")
    dubbel_a = dict(afspraak("!! Mehdi: [HA-PB] proef: tweede deel", "15:00"), id="id-dubbel")
    paar = W.onvolledig_per_afspraak([kort_a, lang_a], MORGEN)
    zr_lang = {"geen adres in de agenda": [f"{lang_a['start'][:16]} {W._toon(lang_a, 50)}"]}
    check("AG-4 de reistijdregel van 'proef bij de klant' dekt 'proef' op dezelfde minuut niet",
          teksten(W.adres_noden(zr_lang, paar, [], [kort_a, lang_a])) == [TEKST["rit"], TEKST["adres"]])
    check("AG-4 regel_afspraak kiest de langste titel en kent agenda, id en start",
          W.regel_afspraak(f"{kort_a['start'][:16]} {W._toon(dubbel_a, 50)}: adres niet gevonden (x)", [kort_a, dubbel_a])
          == (dubbel_a["kalender"], "id-dubbel", dubbel_a["start"])
          and W.regel_afspraak(f"{kort_a['start'][:16]} {W._toon(kort_a, 50)}: adres niet gevonden (x)", [kort_a, dubbel_a])
          == (kort_a["kalender"], "id-kort", kort_a["start"]))
    # Codex-toets 3: in dezelfde ronde zet vragen_in_agenda 'VR ' voor de titel, na de reistijdregel
    vr_a = dict(afspraak("!! Mehdi: [HA-PB] proef met een vraag", "16:00"), id="id-vr")
    vr_regel = f"{vr_a['start'][:16]} {W._toon(vr_a, 50)}"
    vr_onv = W.onvolledig_per_afspraak([vr_a], MORGEN)
    vr_kop = W.rit_koppeling({"geen adres in de agenda": [vr_regel]}, [vr_a])
    vr_a["titel"] = "VR " + vr_a["titel"]
    check("AG-4 na een VR-vraag in dezelfde ronde blijft het een nood (de koppeling van voor de vraag)",
          teksten(W.adres_noden({"geen adres in de agenda": [vr_regel]}, vr_onv, [], [vr_a], vr_kop)) == [TEKST["rit"]])
    check("AG-4 regel_afspraak herkent de afspraak ook met 'VR ' ervoor",
          W.regel_afspraak(vr_regel, [vr_a]) == (vr_a["kalender"], "id-vr", vr_a["start"])
          and teksten(W.adres_noden({"geen adres in de agenda": [vr_regel]}, vr_onv, [], [vr_a])) == [TEKST["rit"]])
    zelfde = dict(kort_a, id="id-zelfde", kalender="andere@proef.test")
    check("AG-4 twee afspraken met dezelfde titel op dezelfde minuut: onzeker, dus geen van beide verborgen",
          W.regel_afspraak(f"{kort_a['start'][:16]} {W._toon(kort_a, 50)}", [kort_a, zelfde]) is None
          and teksten(W.adres_noden({"geen adres in de agenda": [f"{kort_a['start'][:16]} {W._toon(kort_a, 50)}"]},
                                    W.onvolledig_per_afspraak([kort_a, zelfde], MORGEN), [], [kort_a, zelfde]))
          == [TEKST["rit"], TEKST["adres"]])
    check("AG-4 de regels van het signaal blijven zoals voordien (een per afspraak)",
          W.onvolledige_afspraken([pb], MORGEN) == [W.onvolledig_regel(pb, geen_a[0][1])]
          and W.onvolledige_afspraken([pb], MORGEN)[0].startswith(f"{pb['start'][:16]} {pb['titel']} ("))

    gevraagd = []
    W.adres_vraag_noden([afspraak("!! Mehdi: [HA-PB] proefprospect", "08:00")], gevraagd=gevraagd)
    check("AG-4 adres_vraag_noden geeft elke afspraak door waarvan de adresvraag een nood werd",
          [(g["id"], g["start"]) for g in gevraagd] == [(pb["id"], pb["start"])], gevraagd)
finally:
    W.plek_zoeken, W.vaste_plek, W.projectadressen.index = _oud4
RONDE = inspect.getsource(W._ronde)
check("AG-4 de ronde meldt nummer, adres en reistijd via adres_noden, na de adresvragen",
      RONDE.index("noden.extend(adres_noden(zonder_rit, onvolledig_a, gevraagd, rit_items, rit_sleutels))")
      > RONDE.index("rit_sleutels = rit_koppeling(zonder_rit, rit_items)")
      and RONDE.index("noden.extend(adres_noden(zonder_rit, onvolledig_a, gevraagd, rit_items, rit_sleutels))")
      > RONDE.index("adres_vraag_noden(rit_items, niet_op_kaart=niet_op_kaart, gevraagd=gevraagd)")
      and "Buitenafspraken zonder reistijd, reden" not in RONDE and "Buitenafspraken zonder adres" not in RONDE)

# --- AG-5: een signaal 'Link doorsturen of titel nakijken' per dag, de regels van alle rondes samen
_boom = ast.parse(BRON)
_romp = next(n for n in next(n for n in _boom.body if isinstance(n, ast.FunctionDef) and n.name == "_ronde").body
             if isinstance(n, ast.Try))
_link_if = next(n for n in _romp.body if isinstance(n, ast.If) and "zregels" in ast.unparse(n.test)
                and "ag.klaarzet" in ast.unparse(n))
_voorstellen = [n for n in _romp.body if isinstance(n, ast.Assign)
                and any(isinstance(x, ast.Name) and x.id == "voorstellen" for x in n.targets)]
LINK_CODE = compile(ast.fix_missing_locations(ast.Module(body=_voorstellen + [_link_if], type_ignores=[])), "agenda_wacht.py", "exec")
check("AG-5 de staat van het linksignaal staat in de proefmap, nooit in de echte datamap",
      W.LINKSIGNAAL.startswith(PROEF_HOME.name), W.LINKSIGNAAL)
gezet = []
NEP_AG = type("NepAg", (), {"klaarzet": staticmethod(lambda items: gezet.extend(items))})()


def linkronde(dag, dag_grens, zregels, nregels=()):
    exec(LINK_CODE, {"ag": NEP_AG, "zregels": list(zregels), "nregels": list(nregels), "pregels": [], "vandaag": dag,
                     "dag_grens": dag_grens, "linksignaal_regels": W.linksignaal_regels,
                     "LINKSIGNAAL_MAX": W.LINKSIGNAAL_MAX})


# 57 dagrondes op een dag, elk voor een andere dag, met wisselende regels; plus de volle ronde
for i in range(57):
    linkronde("2026-10-29", f"2026-11-{(i % 28) + 1:02d}", [f"2026-11-{(i % 20) + 1:02d}T09:00 proefafspraak {i % 20}: link doorsturen"])
linkronde("2026-10-29", None, [], ["2026-11-03T10:00 proef: VOORSTEL 'Mehdi: [HA-KO] proef' (reden)"])
sleutels = {x["uniek"] for x in gezet}
check("AG-5 57 dagrondes en de volle ronde geven een signaal (een sleutel per dag)",
      sleutels == {"agenda-zoom-titel:2026-10-29"}, sleutels)
laatste = gezet[-1]["inhoud"].split("\n")
check("AG-5 het signaal draagt de regels van alle rondes van die dag, elke regel een keer",
      len(laatste) == 21 and len(set(laatste)) == 21 and "VOORSTEL" in laatste[-1]
      and laatste[0] == "- 2026-11-01T09:00 proefafspraak 0: link doorsturen", laatste[:3])
gezet.clear()
linkronde("2026-10-30", "2026-11-05", ["2026-11-05T09:00 andere proef: link doorsturen"])
check("AG-5 een nieuwe dag begint leeg", gezet and gezet[-1]["uniek"] == "agenda-zoom-titel:2026-10-30"
      and gezet[-1]["inhoud"] == "- 2026-11-05T09:00 andere proef: link doorsturen", gezet)
gezet.clear()
_veel = [f"2026-11-06T{u:02d}:{m:02d} proef {u}-{m}" for u in range(8, 20) for m in range(0, 60, 2)]
linkronde("2026-10-31", "2026-11-06", _veel)
_r = gezet[-1]["inhoud"].split("\n")
check("AG-5 boven het maximum een slotregel met het aantal, geen afgekapte regel",
      len(_r) == W.LINKSIGNAAL_MAX + 1 and _r[-1] == f"- en nog {len(_veel) - W.LINKSIGNAAL_MAX} regel(s)", _r[-2:])
with open(W.LINKSIGNAAL, "w", encoding="utf-8") as _f:
    _f.write("{kapot")
gezet.clear()
linkronde("2026-10-31", "2026-11-07", ["2026-11-07T09:00 proef na een kapot bestand"])
check("AG-5 een onleesbaar staatbestand geeft geen fout, alleen de regels van nu",
      gezet and gezet[-1]["inhoud"] == "- 2026-11-07T09:00 proef na een kapot bestand", gezet)

# --- Op het echte bord (Codex-toets 1): AG-3 twee items, AG-5 na het oppakken, AG-2 privé van titel tot pagina
import importlib.util  # noqa: E402
import sqlite3  # noqa: E402
os.environ["AGENTS_DB"] = os.path.join(PROEF_HOME.name, "bord.db")
os.environ["AGENTS_TOKEN"] = "proef"
_bordmap = str(ROOT.parent / "mijnagents")
sys.path.insert(0, _bordmap)
try:
    _spec = importlib.util.spec_from_file_location("bord_app_proef", ROOT.parent / "mijnagents" / "app.py")
    BORD = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(BORD)
    import wachten_dag as WD  # noqa: E402
finally:
    sys.path.remove(_bordmap)
BC = BORD.app.test_client()
TOKEN = {"X-Agents-Token": "proef"}


def bord_zet(items, van="agenda-wacht"):
    r = BC.post("/api/klaarzet", json={"items": [dict(it, van=van) for it in items]}, headers=TOKEN)
    assert r.status_code == 200, r.get_data(as_text=True)


def bord_rijen(sql, args=()):
    con = sqlite3.connect(os.environ["AGENTS_DB"])
    con.row_factory = sqlite3.Row
    try:
        return [dict(x) for x in con.execute(sql, args).fetchall()]
    finally:
        con.close()


_dag3 = "2026-10-26"
for reden in (A, B):
    bord_zet([{"voor": "mehdi", "soort": "signaal", "sleutel": _dag3, "titel": f"Titels: {reden}",
               "uniek": W.titel_uniek(reden, _dag3), "inhoud": f"- {_dag3}T10:00 afspraak bij {reden}"}])
_titels = bord_rijen("SELECT titel, status FROM klaarzet WHERE uniek LIKE ?", (f"agenda-titel-%:{_dag3}",))
check("AG-3 op het bord: twee redenen met hetzelfde begin blijven twee klare items",
      sorted(x["titel"] for x in _titels) == [f"Titels: {A}", f"Titels: {B}"] and {x["status"] for x in _titels} == {"klaar"},
      _titels)

# AG-5: het dagsignaal wordt opgepakt; een latere ronde met een nieuwe regel zet het weer klaar met alle regels
gezet.clear()
NEP_AG = type("BordAg", (), {"klaarzet": staticmethod(lambda items: bord_zet(items))})()
linkronde("2026-10-28", "2026-11-09", ["2026-11-09T09:00 proef eerste: link doorsturen"])
_id = bord_rijen("SELECT id FROM klaarzet WHERE uniek='agenda-zoom-titel:2026-10-28'")[0]["id"]
BC.post(f"/api/klaarzet/{_id}/opgepakt", json={"door": "proefagent"}, headers=TOKEN)
linkronde("2026-10-28", "2026-11-09", ["2026-11-09T09:00 proef eerste: link doorsturen"])
_zelfde = bord_rijen("SELECT status FROM klaarzet WHERE uniek='agenda-zoom-titel:2026-10-28'")
check("AG-5 op het bord: dezelfde regel na het oppakken laat het signaal opgepakt (niets nieuws, niet terug)",
      [x["status"] for x in _zelfde] == ["opgepakt"], _zelfde)
linkronde("2026-10-28", "2026-11-10", ["2026-11-10T09:00 proef tweede: link doorsturen"])
_na = bord_rijen("SELECT status, inhoud FROM klaarzet WHERE uniek='agenda-zoom-titel:2026-10-28'")
check("AG-5 op het bord: na het oppakken komen de nieuwe regels erbij en staat het signaal weer klaar",
      len(_na) == 1 and _na[0]["status"] == "klaar" and "proef eerste" in _na[0]["inhoud"] and "proef tweede" in _na[0]["inhoud"]
      and bord_rijen("SELECT count(*) AS n FROM klaarzet_revisie WHERE uniek='agenda-zoom-titel:2026-10-28'")[0]["n"] == 1, _na)

# AG-2: een privéafspraak met een lange titel in een titelsignaal ([:58]) komt als '(privé)' op het bord en de pagina
_prive_kal = next(iter(W.PRIVE_KALENDERS))
_pt = "   Mehdi: [HA-KO] proefgesprek met een heel lange titel die privé blijft tot op het einde"   # spaties vooraan
_pa = {"kalender": _prive_kal, "id": "p1", "titel": _pt, "start": "2026-10-27T09:00:00+01:00", "locatie": ""}
_ag = W.bord.Agent("agenda-wacht")
_ag.prive(W.prive_teksten([_pa]))
_oud_call, W.bord.call = W.bord.call, lambda pad, payload=None, method=None: bord_zet(payload["items"]) or {}
try:
    _ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": "2026-10-27", "titel": "Titels: geen firmacode",
                   "uniek": W.titel_uniek("geen firmacode", "2026-10-27"), "inhoud": f"- {W.titel_regel(_pa)}"}])
finally:
    W.bord.call = _oud_call
_rij = bord_rijen("SELECT inhoud FROM klaarzet WHERE sleutel='2026-10-27'")
with BORD.app.app_context():
    _pagina = WD.dag(BORD.db(), "2026-10-27", {"agenda-wacht": "De Agendawacht"}, (), ("agenda-wacht",))
_regels = [r for w in _pagina["vakken"][0]["wachten"] for it in w["items"] for r in it.get("regels", [])]
check("AG-2 een ingekorte privétitel uit een titelsignaal komt als '(privé)' op de pagina, zonder rest",
      _rij and _rij[0]["inhoud"] == "- 2026-10-27T09:00 (privé)" and _regels == ["2026-10-27T09:00 (privé)"], (_rij, _regels))
check("AG-2 het masker kent elke inkorting van een titel die naar het bord gaat (ook 58)", 58 in W.KORT_LENGTES)
check("AG-2 de titelsignalen in de ronde gebruiken titel_regel (een privéafspraak heet '(privé)')",
      "titel_fouten.setdefault(reden, []).append(titel_regel(a))" in RONDE and "get('titel','')[:58]" not in RONDE
      and W.titel_regel(dict(_pa, kalender=W.WERKAGENDA)) == f"2026-10-27T09:00 {_pt[:58]}")

print(f"agenda-meldingen: {ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
