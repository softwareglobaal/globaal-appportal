"""Grendel op Lara en de schoolvakanties (driehoeksoverleg 27-10-2026, L2 tot L4; FR-210).

Gezien 22-10-2026: een fout blok 'Herfstvakantie Lara' (26/10 tot 1/11; officieel is het 2 tot 8/11) liet de Lara-ritten
wegvallen. Een assistent wiste daarop alle vaste Lara-afspraken van die week, om 06:00 belde de agent zes keer
'afgezegd, niet vertrekken', en op 23-10 boekte Calendly een klant op de rit van de zwemles naar huis.

Bewijst:
L2  de vakantiedagen komen alleen uit werkwijze/schoolvakanties.json; een gat of fout in dat bestand is onbekend (None),
    geen 'geen vakantie'; een blok in de Lara-agenda dat afwijkt, is een vraag in de privé-agenda, geen vakantie.
L3  een geschrapte instantie van een vaste Lara-reeks op een schooldag is een vraag (eenmaal), nooit een oproep
    'niet vertrekken'; een ritblok ook niet; op een vakantiedag of in het weekend gebeurt niets.
L4  per vakantieweek met vaste Lara-afspraken één vraag; de afspraken blijven staan; een ophaalmoment met 'vervalt'
    vooraan telt niet meer en krijgt geen rit.
Geen netwerk: alle Google-schrijfacties zijn nagemaakt. Geen Lara-titel in uitvoer voor het bord.
"""
import json
import os
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ["BELLEN_UIT"] = "1"
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W          # noqa: E402
import agenda_signaal as S        # noqa: E402

S.STAND = Path(tempfile.mkdtemp(prefix="lara-")) / "agenda-signaal.json"
S.CONTROLEPUNTEN = S.STAND.parent / "controlepunten.json"
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


LARA = next(k for k, n in W.KALENDERS.items() if n == "Lara")
WERK = W.WERKAGENDA

# --- L2: de officiële bron ---------------------------------------------------------------------------------
sv = W.schoolvakanties()
check("de officiële bron is te lezen", sv is not None)
dagen, dekking, namen = sv
check("herfstvakantie 2026 is 2 tot en met 8 november", {f"2026-11-0{i}" for i in range(2, 9)} <= dagen
      and "2026-11-01" not in dagen and "2026-11-09" not in dagen)
check("26 tot 30 oktober 2026 zijn schooldagen (het foute blok)", not ({f"2026-10-{i}" for i in range(26, 31)} & dagen))
check("Wapenstilstand 11/11/2026 en Pinkstermaandag 17/5/2027 zijn vrij", {"2026-11-11", "2027-05-17"} <= dagen)
check("de naam van een vakantiedag staat erbij", namen.get("2026-11-04") == "herfstvakantie")
check("lara_vakantiedagen geeft precies de officiële dagen", W.lara_vakantiedagen() == dagen)
_d = json.loads(W.SCHOOLVAKANTIES.read_text(encoding="utf-8"))
check("de bron noemt vlaanderen.be en een controledatum", "vlaanderen.be" in _d["bron"] and _d.get("gecontroleerd"))

_oud = W.SCHOOLVAKANTIES
_tmp = Path(tempfile.mkdtemp(prefix="sv-"))
try:
    W.SCHOOLVAKANTIES = _tmp / "bestaat-niet.json"
    check("een ontbrekend bestand is onbekend (None), niet 'geen vakantie'", W.lara_vakantiedagen() is None)
    _gat = json.loads(json.dumps(_d))
    _gat["schooljaren"].pop("2027-2028")
    (_tmp / "gat.json").write_text(json.dumps(_gat), encoding="utf-8")
    W.SCHOOLVAKANTIES = _tmp / "gat.json"
    check("een gat tussen twee schooljaren maakt de bron ongeldig", W.schoolvakanties() is None)
    _fout = json.loads(json.dumps(_d))
    _fout["schooljaren"]["2026-2027"]["vrij"][0]["tot"] = "2026-10-30"      # einde voor begin
    (_tmp / "fout.json").write_text(json.dumps(_fout), encoding="utf-8")
    W.SCHOOLVAKANTIES = _tmp / "fout.json"
    check("een vakantie die eindigt voor ze begint maakt de bron ongeldig", W.schoolvakanties() is None)
    _buiten = json.loads(json.dumps(_d))
    _buiten["schooljaren"]["2026-2027"]["vrij"][0]["van"] = "2026-08-20"     # buiten het schooljaar
    (_tmp / "buiten.json").write_text(json.dumps(_buiten), encoding="utf-8")
    W.SCHOOLVAKANTIES = _tmp / "buiten.json"
    check("een vakantie buiten haar schooljaar maakt de bron ongeldig", W.schoolvakanties() is None)
finally:
    W.SCHOOLVAKANTIES = _oud

# afwijkende blokken in de Lara-agenda
_blokken = [
    {"id": "fout", "titel": "Herfstvakantie Lara", "van": "2026-10-26", "tot": "2026-11-02"},
    {"id": "goed", "titel": "Lara: schoolvakantie Herfst", "van": "2026-11-02", "tot": "2026-11-09"},
    {"id": "feest", "titel": "Lara: feestdag Wapenstilstand", "van": "2026-11-11", "tot": "2026-11-12"},
    {"id": "reis", "titel": "Lara op vakantie:", "van": "2026-11-28", "tot": "2026-12-07"},
    {"id": "voorbij", "titel": "Herfstvakantie", "van": "2026-10-12", "tot": "2026-10-17"},
    {"id": "weekend", "titel": "Lara: vakantie weekend", "van": "2026-11-14", "tot": "2026-11-16"},
]
_afw = W.lara_vakantie_afwijkingen(_blokken, dagen, date(2026, 10, 20))
_ids = {b["id"]: b for b in _afw}
check("het foute herfstblok is een afwijking met de vijf schooldagen 26 tot 30/10",
      "fout" in _ids and _ids["fout"]["schooldagen"] == [f"2026-10-{i}" for i in range(26, 31)], str(_afw))
check("het juiste herfstblok en de feestdag wijken niet af", "goed" not in _ids and "feest" not in _ids)
check("een eigen reis ('Lara op vakantie') schakelt geen ritten uit maar is een vraag", "reis" in _ids
      and _ids["reis"]["schooldagen"][0] == "2026-11-30")
check("een voorbij blok en een blok in het weekend geven geen vraag", "voorbij" not in _ids and "weekend" not in _ids)
_na = W.lara_vakantie_afwijkingen([{"id": "na", "titel": "Lara: vakantie", "van": "2030-09-02", "tot": "2030-09-07"}],
                                  dagen, date(2030, 8, 20), dekking)
check("na de laatste dag van de bron is een dag onbekend, geen schooldag: geen vraag", not _na, str(_na))
_afw2 = W.lara_vakantie_afwijkingen(_blokken, dagen, date(2026, 10, 28))
check("een lopend blok telt alleen de schooldagen vanaf vandaag",
      next(b for b in _afw2 if b["id"] == "fout")["schooldagen"] == ["2026-10-28", "2026-10-29", "2026-10-30"])

# --- L4: vakantieweken en 'vervalt' --------------------------------------------------------------------------


def lara(dag, uur="16:00", titel="!! Mehdi: [LA] Lara ophalen en thuis afzetten", kal=LARA, **meer):
    a = {"kalender": kal, "id": f"{dag}{uur}", "titel": titel, "start": f"{dag}T{uur}:00+01:00",
         "einde": f"{dag}T17:00:00+01:00", "hele_dag": False}
    a.update(meer)
    return a


_items = [lara("2026-11-02"), lara("2026-11-03", "17:30", "!! Mehdi: Lara ophalen bij oma"),
          lara("2026-11-06", titel="vervalt (vakantie) !! Mehdi: [LA] Lara ophalen"),
          lara("2026-11-02", "15:45", "🚗 Reistijd: thuis → De Speelkriebel"),
          lara("2026-11-04", kal=WERK, titel="Mehdi: [HARC-KB] 2505 - klant"),
          lara("2026-10-29"), lara("2026-12-22"),
          {"kalender": LARA, "id": "hd", "titel": "Lara: schoolvakantie Herfst", "start": "2026-11-02",
           "einde": "2026-11-09", "hele_dag": True}]
_wk = W.lara_vakantieweken(_items, namen, date(2026, 10, 27))
check("één vakantieweek (herfst, week 45) met de twee vaste Lara-afspraken die nog openstaan",
      len(_wk) == 1 and _wk[0]["week"] == "2026-W45" and len(_wk[0]["afspraken"]) == 2
      and _wk[0]["van"] == "2026-11-02" and _wk[0]["tot"] == "2026-11-08", str(_wk))
check("een rit, een hele dag, een andere agenda, een schooldag en 'vervalt' tellen niet mee",
      all("Reistijd" not in t and "vervalt" not in t and "HARC" not in t for _, t in _wk[0]["afspraken"]))
check("verder dan 21 dagen vooruit (kerst) nog geen vraag", all(w["week"] != "2026-W52" for w in _wk))
check("'vervalt' vooraan herkent de agent, gewone titels niet",
      W.lara_vervalt({"titel": "Vervalt (vakantie) Lara ophalen"}) and not W.lara_vervalt({"titel": "Lara ophalen"}))

# --- de vragen in de privé-agenda -------------------------------------------------------------------------------
_ins, _pat, _opg, _gelezen = [], [], [], []
_o = {k: getattr(W, k) for k in ("_insert", "_patch", "_eigen_melding_opgelost", "_prive_item_lezen", "LARA_VRAGEN")}
W.LARA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="lara-vragen-")) / "agenda-lara-vragen.json")
W._insert = lambda kal, body, tok, toch=False: _ins.append((kal, body)) or {"id": f"n{len(_ins)}"}
W._patch = lambda a, body, tok, **k: _pat.append((a, body))
W._eigen_melding_opgelost = lambda x, k, tok, nu, reden="": _opg.append((x, k, reden)) or True
_buiten_venster = {}
W._prive_item_lezen = lambda eid, tok: _gelezen.append(eid) or _buiten_venster.get(eid)
try:
    _nu = datetime(2026, 10, 27, 9, 0, tzinfo=W.TIJDZONE)
    _r1 = W.lara_meldingen([_ids["fout"]], _wk, [], "tok", _nu)
    check("eerste ronde: twee vragen in de privé-agenda (afwijking en vakantieweek)",
          len(_ins) == 2 and all(k == W.PRIVE_AGENDA for k, _ in _ins), str(_r1))
    _b = {b["extendedProperties"]["private"][W.LARAMERK]: b for _, b in _ins}
    check("elke vraag is een eigen melding: mailmerk van 16 tekens en een Lara-sleutel",
          all(len(b["extendedProperties"]["private"][W.MAILMERK]) == 16 for b in _b.values())
          and set(_b) == {"afwijking:fout", "week:2026-W45"})
    check("Beschikbaar, zonder herinnering, titel begint met 'VR Agendawacht:'",
          all(b["transparency"] == "transparent" and b["reminders"] == {"useDefault": False, "overrides": []}
              and b["summary"].startswith("VR Agendawacht:") for b in _b.values()))
    check("de vraag sluit geen dag af (geen dagmarkering die Calendly of ritten blokkeert)",
          all(not W.markeringen_uit([{"titel": b["summary"], "start": b["start"]["date"], "einde": b["end"]["date"],
                                      "hele_dag": True}], b["start"]["date"]) for b in _b.values()))
    check("de tekst zegt markeren, nooit wissen", all("Wissen doe ik nooit" in b["description"] for b in _b.values()))
    check("de afwijking loopt van vandaag tot en met de laatste dag van het blok",
          _b["afwijking:fout"]["start"]["date"] == "2026-10-27" and _b["afwijking:fout"]["end"]["date"] == "2026-11-02")
    check("de weekvraag noemt de afspraken van die week", "Lara ophalen bij oma" in _b["week:2026-W45"]["description"])
    check("de regels voor het bord dragen geen Lara-titel", not any("Lara ophalen" in r or "Herfstvakantie" in r for r in _r1))
    # tweede ronde: de vragen staan er al
    _er = [{"kalender": W.PRIVE_AGENDA, "id": f"x{i}", "titel": b["summary"], "start": b["start"]["date"],
            "_merk": dict(b["extendedProperties"]["private"]), "hele_dag": True, "maker": W.WERKAGENDA,
            "deelnemers": [], "omschrijving": b["description"]} for i, (_, b) in enumerate(_ins)]
    _gewist = {"kalender": W.PRIVE_AGENDA, "id": "g1", "titel": "VR Agendawacht: vaste Lara-afspraak gewist", "start": "2026-10-28",
               "_merk": {W.MAILMERK: W._lara_mailk("gewist:x:2026-10-28"), W.LARAMERK: "gewist:x:2026-10-28"}, "hele_dag": True}
    _n = len(_ins)
    W.lara_meldingen([_ids["fout"]], _wk, _er + [_gewist], "tok", _nu)
    check("tweede ronde: geen dubbele vraag", len(_ins) == _n and not _pat, str(_ins[_n:]))
    # het foute blok is weg (Mehdi of Claude haalde het weg): de vraag wordt opgelost, de weekvraag blijft
    # Mehdi haalt de afwijkingsvraag weg (of beantwoordt ze) terwijl het blok blijft: een echte reis, niet opnieuw vragen
    W.lara_meldingen([_ids["fout"]], _wk, _er[1:], "tok", _nu)
    check("een weggehaalde of beantwoorde vraag komt niet terug zolang het blok blijft (eenmaal vragen)",
          len(_ins) == _n, str(_ins[_n:]))
    W.lara_meldingen([], _wk, _er + [_gewist], "tok", _nu)
    check("een afwijking die verdwijnt, krijgt 'Opgelost' (niet gewist); de weekvraag blijft",
          [k for _, k, _ in _opg] == [_er[0]["_merk"][W.MAILMERK]] and len(_ins) == _n, str(_opg))
    check("een vraag over een gewiste afspraak rondt de agent nooit zelf af",
          all(x["id"] != "g1" for x, _, _ in _opg))
    # de vakantieweek is voorbij en de vraag valt buiten het leesvenster: de agent leest ze op id terug en rondt af
    _wid = json.loads(Path(W.LARA_VRAGEN).read_text())["week:2026-W45"]["id"]
    _buiten_venster[_wid] = dict(_er[1], id=_wid)
    _opg.clear()
    W.lara_meldingen([], [], [], "tok", _nu + timedelta(days=14))
    _reg = json.loads(Path(W.LARA_VRAGEN).read_text())
    check("een weekvraag buiten het leesvenster wordt op id teruggelezen en krijgt 'Opgelost'",
          _wid in _gelezen and len(_opg) == 1 and _reg["week:2026-W45"]["open"] is False, str((_gelezen, _opg, _reg)))
    _opg.clear()
    W.lara_meldingen([], [], [], "tok", _nu + timedelta(days=15))
    check("een afgeronde vraag wordt niet nog eens afgerond", not _opg, str(_opg))
finally:
    for k, v in _o.items():
        setattr(W, k, v)

_bewijs = {"kalender": W.PRIVE_AGENDA, "id": "x0", "titel": _b["afwijking:fout"]["summary"],
           "_merk": dict(_b["afwijking:fout"]["extendedProperties"]["private"]), "maker": W.WERKAGENDA,
           "deelnemers": [], "_agendagasten": [], "omschrijving": "x"}
check("de eigendomscontrole kent de vraag als eigen melding: 'Opgelost' mag",
      W._titel_patch_reden(_bewijs, "Opgelost: " + _bewijs["titel"][16:]) == "", W._titel_patch_reden(_bewijs, "Opgelost: x"))

# lara_vakantie_stap: een halve lezing zet niets, een nood draagt geen teller en geen Lara-titel
_o2 = {k: getattr(W, k) for k in ("lara_vakantieblokken", "lara_meldingen", "VERRE_FOUT")}
_ronde = []
try:
    W.lara_meldingen = lambda *a, **k: _ronde.append(a) or []
    W.VERRE_FOUT = [{"kalender": LARA, "fout": "500"}]
    W.lara_vakantieblokken = lambda: _blokken
    _nd = W.lara_vakantie_stap([], "2026-10-27")
    check("een verre agenda niet gelezen: geen vragen zetten of afronden (geen dubbel)", not _ronde, str(_nd))
    W.VERRE_FOUT = []
    W.lara_vakantieblokken = lambda: None
    _nd = W.lara_vakantie_stap([], "2026-10-27")
    check("de Lara-agenda niet te lezen: een nood, niets gezet", not _ronde and any("niet te lezen" in n["tekst"] for n in _nd))
    W.lara_vakantieblokken = lambda: _blokken
    _nd = W.lara_vakantie_stap([], "2026-10-27")
    check("noden zonder teller en zonder Lara-titel (N10, privé)",
          all(not any(c.isdigit() for c in n["tekst"]) and "Herfstvakantie" not in n["tekst"] for n in _nd), str(_nd))
finally:
    for k, v in _o2.items():
        setattr(W, k, v)

# --- ritten: 'vervalt' blijft vooraan, en een vervallen of vakantie-afspraak houdt geen rit meer vast (reviewronde) ---
check("'!!' gaat nooit voor 'vervalt' (anders herkent de agent de markering niet meer)",
      W.tekens_vooraan("vervalt (vakantie) !! Mehdi: [LA] Lara ophalen") == "vervalt (vakantie) !! Mehdi: [LA] Lara ophalen")
check("'vervalt' wordt ook na VR of !! herkend",
      all(W.lara_vervalt({"titel": t}) for t in ("!! vervalt (vakantie) Mehdi: Lara", "VR !! vervalt x", "VR vervalt x")))
_or = {k: getattr(W, k) for k in ("geen_auto_dagen", "coord", "rijtijd_min", "_cache_laden", "_cache_bewaren", "_patch",
                                  "_insert", "_eigen_rit_weg", "_verplaats", "plek_zoeken", "lara_vakantiedagen")}
_ok = (W.agenda._toegang, W.agenda.kalendernamen, W.projectadressen.index)
_RI, _RW = [], []
try:
    W.agenda._toegang = lambda: "tok"
    W.agenda.kalendernamen = lambda: dict(W.KALENDERS)
    W.projectadressen.index = lambda: {}
    W.geen_auto_dagen = lambda: frozenset()
    W.coord = lambda adres, cache: (50.88, 4.72) if adres == W.THUIS else (50.89, 4.73)
    W.rijtijd_min = lambda van, naar, vertrek: (15, 1.0)
    W._cache_laden = lambda: {}
    W._cache_bewaren = lambda c: None
    W.plek_zoeken = lambda t: (None, None)
    W._patch = lambda a, body, tok, **k: None
    W._insert = lambda kal, body, tok, toch=False: _RI.append((kal, body)) or {"id": body.get("id")}
    W._eigen_rit_weg = lambda x, tok: (W.is_eigen_rit(x) and _RW.append(x["titel"])) or W.is_eigen_rit(x)
    W._verplaats = lambda x, doel, tok: None
    _NU = datetime(2026, 10, 27, 9, 0, tzinfo=W.TIJDZONE)

    def _afspr(dag, titel="!! Mehdi: [LA] Lara ophalen en thuis afzetten"):
        return {"kalender": LARA, "id": "a" + dag.replace("-", ""), "titel": titel, "start": f"{dag}T16:00:00+01:00",
                "einde": f"{dag}T17:00:00+01:00", "locatie": "De Speelkriebel, Diestsesteenweg 1, 3010 Kessel-Lo",
                "hele_dag": False, "omschrijving": "", "deelnemers": []}

    def _ritten():
        return [{"kalender": k, "id": b["id"], "titel": b["summary"], "start": b["start"]["dateTime"],
                 "einde": b["end"]["dateTime"], "omschrijving": b["description"], "hele_dag": False,
                 "_merk": dict(b["extendedProperties"]["private"]), "_kleur": b.get("colorId", ""),
                 "_reminders": b.get("reminders"), "deelnemers": []}
                for k, b in _RI if b.get("summary", "").startswith("\U0001F697")]

    W.reistijd_zetten([_afspr("2026-11-10")], nu=_NU)
    _r = _ritten()
    check("tegenproef: een gewone Lara-afspraak op een schooldag krijgt een heen- en terugrit", len(_r) == 2, str(len(_r)))
    _RI.clear()
    _vt = W.tekens_vooraan("vervalt (vakantie) !! Mehdi: [LA] Lara ophalen en thuis afzetten")   # zoals uitroep_vooraan
    W.reistijd_zetten([_afspr("2026-11-10", _vt)] + [dict(x) for x in _r], nu=_NU)
    check("na 'vervalt' (ook na de stap die !! vooraan zet): geen nieuwe rit en de eigen ritten gaan weg",
          not _ritten() and len(_RW) == 2, str((_ritten(), _RW)))
    # een rit van voor de officiële bron, op een dag die nu officieel vakantie is (4/11)
    _RI.clear(); _RW.clear()
    W.lara_vakantiedagen = lambda: frozenset()
    W.reistijd_zetten([_afspr("2026-11-04")], nu=_NU)
    _r = _ritten()
    W.lara_vakantiedagen = _or["lara_vakantiedagen"]
    _RI.clear()
    W.reistijd_zetten([_afspr("2026-11-04")] + [dict(x) for x in _r], nu=_NU)
    check("een eigen rit op een dag die nu officieel vakantie is, gaat weg", len(_r) == 2 and len(_RW) == 2, str((len(_r), _RW)))
finally:
    for k, v in _or.items():
        setattr(W, k, v)
    W.agenda._toegang, W.agenda.kalendernamen, W.projectadressen.index = _ok

# een eigen Lara-vraag of een opgeloste vraag sluit nooit een dag af, ook niet met een bloktitel die op een markering lijkt
_lv = {"kalender": W.PRIVE_AGENDA, "titel": "VR Agendawacht: Lara geen afspraken", "start": "2026-11-28", "einde": "2026-12-07",
       "hele_dag": True, "_merk": {W.LARAMERK: "afwijking:x"}}
check("een eigen Lara-vraag sluit geen dag af", not W.markeringen_uit([_lv], "2026-11-30"))
check("de titel van een afwijkingsvraag neemt de bloktitel niet over (alleen in de omschrijving)",
      "Lara op vakantie" not in W.lara_afwijking_body(_ids["reis"], date(2026, 10, 27))[1]["summary"])

# --- L3: een gewiste vaste Lara-afspraak (agenda_signaal) --------------------------------------------------------
_nu = datetime(2026, 10, 21, 23, 15, tzinfo=timezone.utc)
_inst = {"id": "41t2prmi75bpa224h1g8s1bfhj_20261026T150000Z", "status": "cancelled",
         "recurringEventId": "41t2prmi75bpa224h1g8s1bfhj",
         "originalStartTime": {"dateTime": "2026-10-26T16:00:00+01:00"}}
_vorig = [json.dumps(["!! Mehdi: [LA] Lara ophalen en thuis afzetten", "confirmed",
                      {"dateTime": "2026-10-26T16:00:00+01:00"}, {}, "", [], False]), "2026-10-26"]
_k = S.lara_wissing_kandidaat(LARA, _inst, _vorig, _nu, dagen, dekking)
check("een gewiste Lara-instantie op een schooldag is een kandidaat met dag en uur",
      _k and _k["dag"] == "2026-10-26" and _k["uur"] == "16:00" and _k["sleutel"].startswith("41t2prmi75bpa224h1g8s1bfhj:"), str(_k))
check("daarvoor belt de agent nooit 'niet vertrekken'", S.annulering_kandidaat(LARA, _inst, _vorig, _nu) is None)
_zonder = {"id": "41t2prmi75bpa224h1g8s1bfhj_20261027", "status": "cancelled",
           "originalStartTime": {"date": "2026-10-27"}}
check("ook zonder recurringEventId herkent hij de reeks aan het id (hele dag)",
      (S.lara_wissing_kandidaat(LARA, _zonder, None, _nu, dagen, dekking) or {}).get("dag") == "2026-10-27")
_vak = dict(_inst, id="x_20261104T150000Z", originalStartTime={"dateTime": "2026-11-04T16:00:00+01:00"})
check("op een officiële vakantiedag gebeurt niets", S.lara_wissing_kandidaat(LARA, _vak, None, _nu, dagen, dekking) is None)
_za = dict(_inst, id="x_20261031T090000Z", originalStartTime={"dateTime": "2026-10-31T10:00:00+01:00"})
check("in het weekend gebeurt niets", S.lara_wissing_kandidaat(LARA, _za, None, _nu, dagen, dekking) is None)
_al = [json.dumps(["x", "cancelled", {"dateTime": "2026-10-26T16:00:00+01:00"}, {}, "", [], False]), "2026-10-26"]
check("een instantie die al geschrapt was, geeft geen tweede vraag", S.lara_wissing_kandidaat(LARA, _inst, _al, _nu, dagen, dekking) is None)
check("een gewone afspraak op een andere agenda valt niet onder deze regel",
      S.lara_wissing_kandidaat(WERK, dict(_inst), _vorig, _nu, dagen, dekking) is None)
_kopie = {"id": "1m7vfkp25otiu8oo005mgag41o", "status": "cancelled"}
_kopievorig = [json.dumps(["!! Mehdi: [LA] Lara ophalen en thuis afzetten", "confirmed",
                           {"dateTime": "2026-10-30T16:00:00+01:00"}, {}, "", [], False]), "2026-10-30"]
check("een gewiste losse Lara-kopie (zoals de teruggezette van 26-10) op een schooldag is ook een vraag",
      (S.lara_wissing_kandidaat(LARA, _kopie, _kopievorig, _nu, dagen, dekking) or {}).get("dag") == "2026-10-30")
check("en ook daarvoor nooit een oproep 'niet vertrekken'", S.annulering_kandidaat(LARA, _kopie, _kopievorig, _nu) is None)
_rit = {"id": "rit0123", "status": "cancelled"}
_ritvorig = [json.dumps(["🚗 Reistijd: thuis → Wilselsesteenweg 57", "confirmed",
                         {"dateTime": "2026-10-27T17:10:00+01:00"}, {}, "", [], False]), "2026-10-27"]
check("een gewist ritblok geeft nooit een oproep 'niet vertrekken'", S.annulering_kandidaat(LARA, _rit, _ritvorig, _nu) is None)
_werk = {"id": "w1", "status": "cancelled"}
_werkvorig = [json.dumps(["Mehdi: [HARC-KB] 2505 - klant", "confirmed",
                          {"dateTime": "2026-10-26T10:00:00+01:00"}, {}, "", [], False]), "2026-10-26"]
check("een gewone geschrapte afspraak blijft een afzegging (tegenproef)",
      S.annulering_kandidaat(WERK, _werk, _werkvorig, _nu) is not None)

# een echte ronde van het signaal: eenmaal een vraag, nooit de titel in de uitvoer, nooit een oproep
import contextlib  # noqa: E402
import io           # noqa: E402
import subprocess   # noqa: E402
import urllib.parse  # noqa: E402

_gemeld, _signalen, _gebeld = [], [], []


def _google(req, timeout=None, *a, **k):
    url = getattr(req, "full_url", req)
    kal = urllib.parse.unquote(urllib.parse.urlparse(url).path.split("/calendars/")[1].split("/events")[0])
    lijst = [dict(_inst, updated=datetime.now(timezone.utc).isoformat())] if kal == LARA else []
    return io.BytesIO(json.dumps({"items": lijst}).encode())


_o3 = (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
       S.W.ag.klaarzet, S.meld_annulering, S.datetime)


class _Nu(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 22, 4, 0, tzinfo=timezone.utc)


try:
    S.urllib.request.urlopen = _google
    S.subprocess.run = lambda args, *a, **k: subprocess.CompletedProcess(args, 0, "", "")
    S.A._toegang = lambda: "nep-token"
    S.W.kalenders = lambda: [LARA]
    S.W.lara_gewist_melden = lambda dag, uur, titel, sleutel, tok, **k: _gemeld.append((dag, uur, titel, sleutel)) or True
    S.W.ag.klaarzet = lambda items: _signalen.extend(items) or {}
    S.meld_annulering = lambda kandidaat, nu: _gebeld.append(kandidaat) or True
    S.datetime = _Nu
    S.bewaar({"gekeken": "2026-10-21T21:00:00+00:00", "vinger": {f"{LARA}|{_inst['id']}": _vorig},
              "annulering_open": {f"{LARA}:oud_20261027T160000Z:2026-10-27T17:00:00+01:00":
                                  {"sleutel": "x", "titel": "(privé)", "start": "2026-10-27T17:00:00+01:00"}}})
    _uit = io.StringIO()
    with contextlib.redirect_stdout(_uit), contextlib.redirect_stderr(io.StringIO()):
        _rc1 = S.main()
        _rc2 = S.main()
finally:
    (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
     S.W.ag.klaarzet, S.meld_annulering, S.datetime) = _o3
check("in een echte ronde: eenmaal een vraag in de privé-agenda, ook na een tweede ronde",
      len(_gemeld) == 1 and _gemeld[0][0] == "2026-10-26" and _rc1 == 0, str((_gemeld, _rc1, _rc2)))
check("in een echte ronde: geen oproep 'niet vertrekken', ook niet voor een opgeslagen Lara-afzegging van voor FR-210",
      not _gebeld and not json.loads(S.STAND.read_text()).get("annulering_open"), str(_gebeld))
check("het signaal op het bord draagt geen Lara-titel en geen 'stil' (dat belt)",
      len(_signalen) == 1 and "Lara ophalen" not in json.dumps(_signalen) and "stil" not in _signalen[0]["titel"].lower(),
      str(_signalen))
check("de uitvoer van de ronde draagt geen Lara-titel", "Lara ophalen" not in _uit.getvalue(), _uit.getvalue()[:200])
check("de stand onthoudt dat de vraag gezet is", list(json.loads(S.STAND.read_text()).get("lara_gemeld", {}).values()) == ["2026-10-26"])

# een hele reeks gewist (drie schooldagen in dezelfde ronde): één vraag met de drie dagen, niet drie vragen
_reeks3 = [dict(_inst, id=f"41t2prmi75bpa224h1g8s1bfhj_202611{d}T150000Z",
                originalStartTime={"dateTime": f"2026-11-{d}T16:00:00+01:00"}) for d in ("10", "13", "16")]
_gemeld3 = []
S.STAND = Path(tempfile.mkdtemp(prefix="lara3-")) / "agenda-signaal.json"
_o4 = (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
       S.W.ag.klaarzet, S.meld_annulering, S.datetime)
try:
    S.urllib.request.urlopen = lambda req, timeout=None, *a, **k: io.BytesIO(json.dumps({"items": [
        dict(e, updated=datetime.now(timezone.utc).isoformat()) for e in _reeks3]}).encode())
    S.subprocess.run = lambda args, *a, **k: subprocess.CompletedProcess(args, 0, "", "")
    S.A._toegang = lambda: "nep-token"
    S.W.kalenders = lambda: [LARA]
    S.W.lara_gewist_melden = lambda dag, uur, titel, sleutel, tok, dagen=None: _gemeld3.append((dag, dagen)) or True
    S.W.ag.klaarzet = lambda items: {}
    S.meld_annulering = lambda kandidaat, nu: True
    S.datetime = _Nu
    S.bewaar({"gekeken": "2026-10-21T21:00:00+00:00"})
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        S.main()
finally:
    (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
     S.W.ag.klaarzet, S.meld_annulering, S.datetime) = _o4
check("een hele reeks gewist geeft één vraag met alle geschrapte schooldagen",
      len(_gemeld3) == 1 and _gemeld3[0][1] == ["2026-11-10", "2026-11-13", "2026-11-16"], str(_gemeld3))

# dezelfde reeks over twee rondes gewist: de bestaande vraag wordt aangevuld, geen tweede vraag (Codex-hertest)
_gemeld4, _bijgewerkt4 = [], []
S.STAND = Path(tempfile.mkdtemp(prefix="lara4-")) / "agenda-signaal.json"
_o5 = (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
       S.W.lara_gewist_bijwerken, S.W.ag.klaarzet, S.meld_annulering, S.datetime)
_golf = [_reeks3[:2]]


def _google4(req, timeout=None, *a, **k):
    return io.BytesIO(json.dumps({"items": [dict(e, updated=datetime.now(timezone.utc).isoformat()) for e in _golf[0]]}).encode())


try:
    S.urllib.request.urlopen = _google4
    S.subprocess.run = lambda args, *a, **k: subprocess.CompletedProcess(args, 0, "", "")
    S.A._toegang = lambda: "nep-token"
    S.W.kalenders = lambda: [LARA]
    S.W.lara_gewist_melden = lambda dag, uur, titel, sleutel, tok, dagen=None: _gemeld4.append((sleutel, dagen)) or "vraag-1"
    S.W.lara_gewist_bijwerken = lambda eid, uur, titel, sleutel, tok, dagen: _bijgewerkt4.append((eid, sleutel, dagen)) or True
    S.W.ag.klaarzet = lambda items: {}
    S.meld_annulering = lambda kandidaat, nu: True
    S.datetime = _Nu
    S.bewaar({"gekeken": "2026-10-21T21:00:00+00:00"})
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        S.main()
        _golf[0] = _reeks3[2:]
        S.main()
finally:
    (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
     S.W.lara_gewist_bijwerken, S.W.ag.klaarzet, S.meld_annulering, S.datetime) = _o5
check("een reeks die over twee rondes gewist wordt, geeft één vraag die aangevuld wordt",
      len(_gemeld4) == 1 and _bijgewerkt4 and _bijgewerkt4[-1][0] == "vraag-1"
      and _bijgewerkt4[-1][2] == ["2026-11-10", "2026-11-13", "2026-11-16"], str((_gemeld4, _bijgewerkt4)))

_o6 = (W._prive_item_lezen, W._patch)
_pat6 = []
try:
    W._patch = lambda a, body, tok, **k: _pat6.append(body)
    W._prive_item_lezen = lambda eid, tok: {"id": eid, "kalender": W.PRIVE_AGENDA, "_merk": {W.LARAMERK: "gewist:r:2026-11-10"}}
    _ja = W.lara_gewist_bijwerken("v1", "16:00", "x", "r:2026-11-10", "tok", ["2026-11-10", "2026-11-13"])
    _nee = W.lara_gewist_bijwerken("v1", "16:00", "x", "andere:2026-11-10", "tok", ["2026-11-10"])
    W._prive_item_lezen = lambda eid, tok: None
    _weg = W.lara_gewist_bijwerken("v1", "16:00", "x", "r:2026-11-10", "tok", ["2026-11-10"])
finally:
    W._prive_item_lezen, W._patch = _o6
check("aanvullen werkt alleen op de eigen vraag van die reeks, en niet als ze weg is",
      _ja and not _nee and not _weg and len(_pat6) == 1 and "13/11" in _pat6[0]["description"], str((_ja, _nee, _weg, _pat6)))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
