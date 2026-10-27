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
os.environ.setdefault("AGENDA_WHATSAPP_WACHTRIJ", os.path.join(__import__("tempfile").mkdtemp(prefix="aw-test-"), "agenda-whatsapp.json"))  # nooit de echte wachtrij
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
    _wk_meer = [dict(_wk[0], afspraken=_wk[0]["afspraken"] + [("2026-11-05T17:45", "!! Mehdi: [LA] Lara ophalen bij oma (optioneel)")],
                     ids=_wk[0]["ids"] + ["oma-0511"])]
    W.lara_meldingen([_ids["fout"]], _wk_meer, _er + [_gewist], "tok", _nu)
    check("de weekvraag wordt aangevuld als er een ophaalmoment bij komt (inhoudsmerk)",
          len(_ins) == _n and len(_pat) == 1 and "05/11" in _pat[0][1]["description"], str(_pat))
    _pat.clear()
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
_verplaatst = [json.dumps(["!! Mehdi: [LA] Lara ophalen", "confirmed", {"dateTime": "2026-11-10T16:00:00+01:00"}, {}, "",
                           [], False]), "2026-11-10"]
_vk = S.lara_wissing_kandidaat(LARA, dict(_inst, originalStartTime={"dateTime": "2026-10-20T16:00:00+02:00"}), _verplaatst,
                               _nu, dagen, dekking)
check("een verplaatste instantie die daarna gewist wordt, telt op haar echte (komende) dag, niet de oorspronkelijke",
      (_vk or {}).get("dag") == "2026-11-10", str(_vk))
_oud20 = [json.dumps(["!! Mehdi: [LA] Lara ophalen", "confirmed", {"dateTime": "2026-10-20T16:00:00+02:00"}, {}, "",
                       [], False]), "2026-10-20"]
_vk2 = S.lara_wissing_kandidaat(LARA, dict(_inst, start={"dateTime": "2026-11-10T16:00:00+01:00"},
                                           originalStartTime={"dateTime": "2026-10-20T16:00:00+02:00"}), _oud20,
                                _nu, dagen, dekking)
check("verplaatst en gewist tussen twee controles: de actuele start van Google gaat voor de opgeslagen",
      (_vk2 or {}).get("dag") == "2026-11-10", str(_vk2))
_blokweg = {"id": "hto6vqpr6vr9vodv76o1ett1pk", "status": "cancelled"}
_blokvorig = [json.dumps(["🍂 Herfstvakantie Lara", "confirmed", {"date": "2026-10-26"}, {"date": "2026-11-02"}, "", [], False]),
              "2026-10-26"]
check("het foute vakantieblok weghalen (zoals de vraag aanraadt) geeft geen vraag 'gewiste Lara-afspraak'",
      S.lara_wissing_kandidaat(LARA, _blokweg, _blokvorig, _nu, dagen, dekking) is None)
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
_lap = {"id": "p1", "status": "cancelled"}
_lapvorig = [json.dumps(["Mehdi: [LA] Halloween met Lara", "confirmed", {"dateTime": "2026-10-31T17:00:00+01:00"}, {}, "", [],
                         False]), "2026-10-31"]
check("een Lara-afspraak ([LA]) op een andere agenda geeft ook nooit 'niet vertrekken'",
      S.annulering_kandidaat(W.PRIVE_AGENDA, _lap, _lapvorig, _nu) is None)
for _t in ("Mehdi: [LARA] Lara bij mij", "Mehdi: [la] Lara bij mij", "Mehdi: [LA-PR] Lara bij mij"):
    _vt = [json.dumps([_t, "confirmed", {"dateTime": "2026-10-31T17:00:00+01:00"}, {}, "", [], False]), "2026-10-31"]
    check(f"ook '{_t[7:16]}' telt als Lara: geen 'niet vertrekken'", S.annulering_kandidaat(W.PRIVE_AGENDA, _lap, _vt, _nu) is None)
# een geschrapt item met een nieuwe, algemene titel: de oude titel telt ook (Codex-hertest 12)
_nieuw = {"id": "p2", "status": "cancelled", "summary": "Afspraak"}
check("een geschrapte [LA]-afspraak met een nieuwe algemene titel geeft geen 'niet vertrekken'",
      S.annulering_kandidaat(W.PRIVE_AGENDA, _nieuw, _lapvorig, _nu) is None)
check("een geschrapt vakantieblok met een nieuwe algemene titel geeft geen vraag 'gewiste Lara-afspraak'",
      S.lara_wissing_kandidaat(LARA, dict(_blokweg, summary="Afspraak"), _blokvorig, _nu, dagen, dekking) is None)
check("een geschrapt ritblok met een nieuwe algemene titel geeft geen vraag",
      S.lara_wissing_kandidaat(LARA, dict(_rit, summary="Afspraak", originalStartTime={"dateTime": "2026-10-27T17:10:00+01:00"}),
                               _ritvorig, _nu, dagen, dekking) is None)
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
# de eerste wisdag is al voorbij: de aangevulde vraag verhuist naar de eerste komende gewiste dag (hertest 2)
_bijgewerkt5 = []
S.STAND = Path(tempfile.mkdtemp(prefix="lara5-")) / "agenda-signaal.json"
try:
    S.urllib.request.urlopen = _google4
    S.subprocess.run = lambda args, *a, **k: subprocess.CompletedProcess(args, 0, "", "")
    S.A._toegang = lambda: "nep-token"
    S.W.kalenders = lambda: [LARA]
    S.W.lara_gewist_melden = lambda dag, uur, titel, sleutel, tok, dagen=None: "nieuwe-vraag"
    S.W.lara_gewist_bijwerken = lambda eid, uur, titel, sleutel, tok, dagen: _bijgewerkt5.append((eid, dagen)) or True
    S.W.ag.klaarzet = lambda items: {}
    S.meld_annulering = lambda kandidaat, nu: True
    S.datetime = _Nu
    _golf[0] = _reeks3[:1]
    S.bewaar({"gekeken": "2026-10-21T21:00:00+00:00", "lara_vraag": {"41t2prmi75bpa224h1g8s1bfhj": {
        "id": "vraag-0", "sleutel": "41t2prmi75bpa224h1g8s1bfhj:2026-10-21", "dagen": ["2026-10-21"]}}})
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        S.main()
finally:
    (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
     S.W.lara_gewist_bijwerken, S.W.ag.klaarzet, S.meld_annulering, S.datetime) = _o5
check("een aangevulde vraag verhuist naar de eerste komende gewiste dag (de oude dag is voorbij)",
      _bijgewerkt5 == [("vraag-0", ["2026-11-10"])], str(_bijgewerkt5))
check("een reeks die over twee rondes gewist wordt, geeft één vraag die aangevuld wordt",
      len(_gemeld4) == 1 and _bijgewerkt4 and _bijgewerkt4[-1][0] == "vraag-1"
      and _bijgewerkt4[-1][2] == ["2026-11-10", "2026-11-13", "2026-11-16"], str((_gemeld4, _bijgewerkt4)))

# de officiële bron is even onleesbaar terwijl een Lara-afspraak gewist wordt: de wissing blijft wachten en geeft na
# herstel toch een vraag (Codex-hertest 5)
_gemeld7 = []
S.STAND = Path(tempfile.mkdtemp(prefix="lara7-")) / "agenda-signaal.json"
_bron = W.SCHOOLVAKANTIES
try:
    S.urllib.request.urlopen = _google4
    S.subprocess.run = lambda args, *a, **k: subprocess.CompletedProcess(args, 0, "", "")
    S.A._toegang = lambda: "nep-token"
    S.W.kalenders = lambda: [LARA]
    S.W.lara_gewist_melden = lambda dag, uur, titel, sleutel, tok, dagen=None: _gemeld7.append(dagen) or "v7"
    S.W.ag.klaarzet = lambda items: {}
    S.meld_annulering = lambda kandidaat, nu: True
    S.datetime = _Nu
    _golf[0] = _reeks3[:1]
    S.bewaar({"gekeken": "2026-10-21T21:00:00+00:00"})
    W.SCHOOLVAKANTIES = _bron.with_name("bestaat-niet.json")
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        _rc7a = S.main()
        S.main()                 # een tweede ronde met de bron nog weg: dezelfde wissing komt opnieuw binnen
    _wacht7 = dict(json.loads(S.STAND.read_text()).get("lara_wacht") or {})
    W.SCHOOLVAKANTIES = _bron
    _golf[0] = []
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        S.main()
finally:
    W.SCHOOLVAKANTIES = _bron
    (S.urllib.request.urlopen, S.subprocess.run, S.A._toegang, S.W.kalenders, S.W.lara_gewist_melden,
     S.W.lara_gewist_bijwerken, S.W.ag.klaarzet, S.meld_annulering, S.datetime) = _o5
check("bron twee rondes onleesbaar: geen vraag en exitcode niet 0, de eerste waarneming blijft wachten",
      _rc7a != 0 and len(_wacht7) == 1, str((_rc7a, _wacht7)))
check("na herstel van de bron komt de vraag er toch", _gemeld7 == [["2026-11-10"]], str(_gemeld7))

# geen tegenstrijdige instructie meer in de bronnen die een volgende sessie of een PDF overneemt (Codex-hertest 8)
_teksten = {n: (HIER / n).read_text(encoding="utf-8") for n in
            ("werkwijze/agenda-taken.json", "werkwijze/agenda-wacht.md", "werkwijze/pdf/afspraken_pdf.py")}
_verboden = ("leest de vakanties uit de agenda van Lara", "lees ik uit de agenda van Lara",
             "26-10 en vrijdag 30-10 (herfstvakantie)", "Geen ophaling, geen rit, en ook geen marker",
             "; de agent leest de vakantiedagen uit de agenda van Lara", "niet op vakantie- en feestdagen van de agenda van Lara",
             "(26-10, 30-10 en 02-07-2027)", "vervalt tijdens schoolvakanties en feestdagen",
             "marker 'Geen buiten afspraken Lara ophalen' blijven staan en Bezet",
             "marker `Geen buiten afspraken Lara ophalen`\n  **staan en Bezet**")
check("werkwijze, open taken en PDF zeggen nergens meer 'vakanties uit de Lara-agenda' of 26/10 en 30/10 als vakantie",
      not [(n, v) for n, t in _teksten.items() for v in _verboden if v in t],
      str([(n, v) for n, t in _teksten.items() for v in _verboden if v in t]))
_taken = json.loads(_teksten["werkwijze/agenda-taken.json"])
check("de dagmarker 'Geen buiten afspraken' heet overal Beschikbaar, de ophaalafspraken Bezet",
      all("Beschikbaar" in _teksten[n] and "ophaalafspraken" in _teksten[n] for n in _teksten))
check("de Lara-regels in agenda-taken noemen de officiële bron en 'nooit wissen'",
      "schoolvakanties.json" in _taken["reistijd"]["schoolvakantie"]["bron"]
      and "nooit wissen" in json.dumps(_taken, ensure_ascii=False).lower())
check("de werkwijze en de PDF zeggen 'nooit wissen' en noemen de officiële bron",
      all("schoolvakanties.json" in _teksten[n] for n in ("werkwijze/agenda-wacht.md", "werkwijze/pdf/afspraken_pdf.py")))

# een vervallen Lara-afspraak telt in de dagcontrole nergens meer mee: geen botsing en dus geen oproep (hertest 11)
import dagcontrole as _DC  # noqa: E402
_kl = {"kalender": WERK, "id": "k1", "titel": "!! Mehdi: [HARC-KB] 2505 - klant, Straat 1, 3000 Leuven",
       "start": "2026-11-10T16:15:00+01:00", "einde": "2026-11-10T16:45:00+01:00", "hele_dag": False, "locatie": "Straat 1, 3000 Leuven"}
_lv2 = lara("2026-11-10", titel="vervalt (vakantie) !! Mehdi: [LA] Lara ophalen en thuis afzetten")
_lv2["einde"] = "2026-11-10T17:00:00+01:00"
_lg = lara("2026-11-10")
_lg["einde"] = "2026-11-10T17:00:00+01:00"
check("tegenproef: een gewone Lara-afspraak die samenvalt met een klant is een botsing",
      any(b["soort"] == "lara_botsing" for b in _DC.dagcontrole([_kl, _lg], "2026-11-10")))
check("een vervallen Lara-afspraak die samenvalt met een klant is geen botsing meer",
      not any(b["soort"] == "lara_botsing" for b in _DC.dagcontrole([_kl, _lv2], "2026-11-10")))
# het belrooster: een [LA]-afspraak buiten de Lara-agenda krijgt een Lara-merk, ook als de titel gemaskeerd is (hertest 13)
_morgen = (W.nu_lokaal() + timedelta(days=1)).date().isoformat()
_la_online = {"kalender": W.PRIVE_AGENDA, "id": "la1", "titel": "Mehdi: [LA] Lara bij mij", "start": f"{_morgen}T10:00:00+01:00",
              "einde": f"{_morgen}T11:00:00+01:00", "hele_dag": False, "locatie": "", "omschrijving": "", "deelnemers": []}
_rr = [r for r in W.belrooster([_la_online], W.nu_lokaal().date().isoformat()) if r["sleutel"].endswith(_la_online["start"])]
check("een roosterregel voor een [LA]-afspraak draagt het Lara-merk, met gemaskeerde titel",
      bool(_rr) and _rr[0].get("lara") is True and "Lara" not in _rr[0]["titel"], str(_rr))
check("een vervallen Lara-afspraak geeft geen botsingssignaal op het bord meer (hertest 12)",
      not W.botsingen([_kl, _lv2]) and W.botsingen([_kl, _lg]), str((W.botsingen([_kl, _lv2]), W.botsingen([_kl, _lg]))))
check("de belregel in werkwijze en agenda-taken zegt: nooit 'niet vertrekken' voor Lara of een rit",
      all("nooit voor een afspraak van lara" in _teksten[n].lower()
          for n in ("werkwijze/agenda-taken.json", "werkwijze/agenda-wacht.md")))

# de Filewacht belt geen 'vertrek nu' voor een vervallen Lara-afspraak of een Lara-ophaling op een vakantiedag (sweep)
import file_wacht as FW  # noqa: E402
_fw_o = {k: getattr(W, k) for k in ("afspraken", "coord", "rijtijd_min", "_cache_laden", "geplande_start", "lara_vakantiedagen")}
_fw_o2 = (W.projectadressen.index, W.ag.log, W.ag.prive, FW.stand, FW.bewaar, FW.bellen.bel_afspraak, FW.bellen.gelukt)
_fw_bel = []


def _fw_ronde(titel, vrij):
    _fw_bel.clear()
    st = datetime.now().astimezone() + timedelta(minutes=12)
    item = {"kalender": LARA, "id": "fw1", "titel": titel, "start": st.isoformat(timespec="seconds"),
            "einde": (st + timedelta(hours=1)).isoformat(timespec="seconds"), "hele_dag": False,
            "locatie": "De Speelkriebel, Jozef Pierrestraat 104, 3010 Kessel-Lo", "omschrijving": "", "deelnemers": []}
    W.afspraken = lambda van_dagen=0, tot_dagen=1, **k: [item]
    W.lara_vakantiedagen = lambda: vrij
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        FW.main()
    return list(_fw_bel)


try:
    W.coord = lambda adres, cache: (50.88, 4.72) if adres == W.THUIS else (50.89, 4.73)
    W.rijtijd_min = lambda van, naar, vertrek: (18, "proef")
    W._cache_laden = lambda: {}
    W.geplande_start = lambda: True
    W.projectadressen.index = lambda: {}
    W.ag.log = lambda *a, **k: None
    W.ag.prive = lambda *a, **k: None
    FW.stand = lambda: {}
    FW.bewaar = lambda d: None
    FW.bellen.bel_afspraak = lambda tekst, slot=None: _fw_bel.append(tekst) or [("twilio", "CAproef")]
    FW.bellen.gelukt = lambda uit: True
    _vandaag = datetime.now().astimezone().date().isoformat()
    _fw_school = _fw_ronde("!! Mehdi: [LA] Lara ophalen en thuis afzetten", frozenset())
    _fw_vak = _fw_ronde("!! Mehdi: [LA] Lara ophalen en thuis afzetten", frozenset({_vandaag}))
    _fw_verv = _fw_ronde("vervalt (vakantie) !! Mehdi: [LA] Lara ophalen en thuis afzetten", frozenset())
finally:
    for k, v in _fw_o.items():
        setattr(W, k, v)
    (W.projectadressen.index, W.ag.log, W.ag.prive, FW.stand, FW.bewaar, FW.bellen.bel_afspraak, FW.bellen.gelukt) = _fw_o2
check("tegenproef: de Filewacht belt wel voor een Lara-ophaling op een schooldag als het te krap wordt", len(_fw_school) == 1,
      str(_fw_school))
check("de Filewacht belt niet voor een Lara-ophaling op een officiële vakantiedag", not _fw_vak, str(_fw_vak))
check("de Filewacht belt niet voor een vervallen Lara-afspraak", not _fw_verv, str(_fw_verv))
check("'vervalt' geldt op elke agenda: geen rit en geen vertrekoproep in het belrooster",
      W.lara_zonder_rit({"kalender": W.PRIVE_AGENDA, "titel": "vervalt (vakantie) Mehdi: [LA] Lara bij mij"}, frozenset())
      and not W.belrooster([dict(_la_online, titel="vervalt (vakantie) " + _la_online["titel"])], W.nu_lokaal().date().isoformat()))

# een afgeronde vraag over een gewiste reeks wordt niet meer aangevuld: dan komt er een nieuwe (sweep)
_o8 = (W._prive_item_lezen, W._patch)
try:
    W._patch = lambda a, body, tok, **k: None
    W._prive_item_lezen = lambda eid, tok: {"id": eid, "titel": "Opgelost: vaste Lara-afspraak gewist",
                                            "_merk": {W.LARAMERK: "gewist:r:2026-11-10", W.MAILMERK: "opgelost:abc"}}
    _afg = W.lara_gewist_bijwerken("v1", "16:00", "x", "r:2026-11-10", "tok", ["2026-11-10"])
finally:
    W._prive_item_lezen, W._patch = _o8
check("een afgeronde vraag wordt niet aangevuld (dan een nieuwe vraag)", _afg is False)

# hertest 14: rit blijft gekoppeld na 'vervalt', [LA-PR] botst niet met de dagmarker, afgeronde week heropent
check("een rit blijft gekoppeld aan zijn afspraak als die 'vervalt' vooraan kreeg",
      W.titel_sleutel(W.zonder_vervalt("vervalt (vakantie) !! Mehdi: [LA] Lara ophalen en thuis afzetten"))
      == W.titel_sleutel("!! Mehdi: [LA] Lara ophalen en thuis afzetten"))
check("een Lara-afspraak met [LA-PR] of [lara] botst niet met de dagmarker 'Geen buiten afspraken'",
      all(W.markering_tegen(t, "2026-11-10", markers=[("!! Mehdi: Geen buiten afspraken Lara ophalen", "buiten")]) is None
          for t in ("!! Mehdi: [LA-PR] Lara ophalen", "!! Mehdi: [lara] Lara ophalen"))
      and W.markering_tegen("!! Mehdi: [HARC-KB] 2505 - klant", "2026-11-10",
                            markers=[("!! Mehdi: Geen buiten afspraken Lara ophalen", "buiten")]) is not None)
_o9 = {k: getattr(W, k) for k in ("_insert", "_patch", "_eigen_melding_opgelost", "_prive_item_lezen", "LARA_VRAGEN")}
_ins9 = []
try:
    W.LARA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="lara-vragen9-")) / "agenda-lara-vragen.json")
    W._insert = lambda kal, body, tok, toch=False: _ins9.append(body) or {"id": f"w{len(_ins9)}"}
    W._patch = lambda a, body, tok, **k: None
    W._eigen_melding_opgelost = lambda x, k, tok, nu, reden="": True
    W._prive_item_lezen = lambda eid, tok: None
    _nu9 = datetime(2026, 10, 27, 9, 0, tzinfo=W.TIJDZONE)
    W.lara_meldingen([], _wk, [], "tok", _nu9)                 # gevraagd
    W.lara_meldingen([], [], [], "tok", _nu9)                  # afgerond (geen open ophaalmoment meer)
    W.lara_meldingen([], _wk, [], "tok", _nu9)                 # dezelfde inhoud: niet opnieuw
    _n9 = len(_ins9)
    W.lara_meldingen([], _wk_meer, [], "tok", _nu9)            # een nieuw ophaalmoment in die week: opnieuw vragen
finally:
    for k, v in _o9.items():
        setattr(W, k, v)
check("een afgeronde weekvraag komt niet terug met dezelfde inhoud, wel bij een nieuw ophaalmoment",
      _n9 == 1 and len(_ins9) == 2, str((_n9, len(_ins9))))
# hertest 15: (1) Mehdi haalt de weekvraag weg terwijl de afspraken blijven, (2) er komt een ophaalmoment bij
_ins10 = []
try:
    W.LARA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="lara-vragen10-")) / "agenda-lara-vragen.json")
    W._insert = lambda kal, body, tok, toch=False: _ins10.append(body) or {"id": f"x{len(_ins10)}"}
    W._patch = lambda a, body, tok, **k: None
    W._prive_item_lezen = lambda eid, tok: None
    W.lara_meldingen([], _wk, [], "tok", _nu9)                 # gevraagd; daarna haalt Mehdi de vraag weg (geen item meer)
    W.lara_meldingen([], _wk, [], "tok", _nu9)                 # zelfde inhoud: niet opnieuw
    _n10 = len(_ins10)
    W.lara_meldingen([], _wk_meer, [], "tok", _nu9)            # nieuw ophaalmoment: opnieuw vragen
    # en een bestaande vraag die bijgewerkt wordt, onthoudt haar nieuwe inhoud: geen dubbel daarna
    _b10 = _ins10[-1]
    _x10 = {"kalender": W.PRIVE_AGENDA, "id": "x2", "titel": _b10["summary"], "start": _b10["start"]["date"],
            "_merk": dict(_b10["extendedProperties"]["private"]), "hele_dag": True}
    _n10b = len(_ins10)
    W.lara_meldingen([], _wk_meer, [_x10], "tok", _nu9)
finally:
    for k, v in _o9.items():
        setattr(W, k, v)
# hertest 16: opeenvolgende dagen in een vakantieweek, de afspraken van gisteren vallen weg: geen tweede vraag
_ins11, _pat11 = [], []
_vier = [lara(f"2026-11-0{d}") for d in (2, 3, 4, 5)]
try:
    W.LARA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="lara-vragen11-")) / "agenda-lara-vragen.json")
    W._insert = lambda kal, body, tok, toch=False: _ins11.append(body) or {"id": f"y{len(_ins11)}"}
    W._patch = lambda a, body, tok, **k: _pat11.append(body)
    W._prive_item_lezen = lambda eid, tok: None
    _er11 = []
    for _dag in (2, 3, 4):
        _v = date(2026, 11, _dag)
        _nu11 = datetime(2026, 11, _dag, 9, 0, tzinfo=W.TIJDZONE)
        _w11 = W.lara_vakantieweken(_vier, namen, _v)
        W.lara_meldingen([], _w11, _er11, "tok", _nu11)
        if _ins11 and not _er11:
            _b = _ins11[0]
            _er11 = [{"kalender": W.PRIVE_AGENDA, "id": "y1", "titel": _b["summary"], "start": _b["start"]["date"],
                      "_merk": dict(_b["extendedProperties"]["private"]), "hele_dag": True}]
finally:
    for k, v in _o9.items():
        setattr(W, k, v)
# hertest 17: een titelwijziging (bv. '(optioneel)' erbij) is geen nieuw ophaalmoment; een eenmalig feest telt niet;
# een gewiste getimede ophaling met 'vakantie' in de titel geeft wel een vraag
_ins12 = []
try:
    W.LARA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="lara-vragen12-")) / "agenda-lara-vragen.json")
    W._insert = lambda kal, body, tok, toch=False: _ins12.append(body) or {"id": f"z{len(_ins12)}"}
    W._patch = lambda a, body, tok, **k: None
    W._prive_item_lezen = lambda eid, tok: None
    _twee = [lara("2026-11-03", "17:30", "!! Mehdi: Lara ophalen bij oma"), lara("2026-11-06")]
    W.lara_meldingen([], W.lara_vakantieweken(_twee, namen, date(2026, 10, 27)), [], "tok", _nu9)
    _twee[0]["titel"] += " (optioneel)"
    W.lara_meldingen([], W.lara_vakantieweken(_twee, namen, date(2026, 10, 27)), [], "tok", _nu9)
finally:
    for k, v in _o9.items():
        setattr(W, k, v)
check("alleen een titelwijziging maakt geen tweede weekvraag (stabiele identiteit)", len(_ins12) == 1, str(len(_ins12)))
# hertest 18: een ophaling verschuift binnen de week (zelfde id): de bestaande vraag wordt bijgewerkt, geen nieuwe
_ins13, _pat13 = [], []
try:
    W.LARA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="lara-vragen13-")) / "agenda-lara-vragen.json")
    W._insert = lambda kal, body, tok, toch=False: _ins13.append(body) or {"id": "q1"}
    W._patch = lambda a, body, tok, **k: _pat13.append(body)
    W._prive_item_lezen = lambda eid, tok: None
    _drie = [lara("2026-11-03", "17:30", "!! Mehdi: Lara ophalen bij oma")]
    W.lara_meldingen([], W.lara_vakantieweken(_drie, namen, date(2026, 10, 27)), [], "tok", _nu9)
    _b13 = _ins13[0]
    _x13 = [{"kalender": W.PRIVE_AGENDA, "id": "q1", "titel": _b13["summary"], "start": _b13["start"]["date"],
             "_merk": dict(_b13["extendedProperties"]["private"]), "hele_dag": True}]
    _drie[0]["start"], _drie[0]["einde"] = "2026-11-05T17:30:00+01:00", "2026-11-05T18:00:00+01:00"   # zelfde id, ander uur
    W.lara_meldingen([], W.lara_vakantieweken(_drie, namen, date(2026, 10, 27)), _x13, "tok", _nu9)
finally:
    for k, v in _o9.items():
        setattr(W, k, v)
check("een ophaling die binnen de week verschuift, werkt de bestaande vraag bij (nieuw uur), zonder nieuwe vraag",
      len(_ins13) == 1 and len(_pat13) == 1 and "05/11 17:30" in _pat13[0]["description"], str((len(_ins13), _pat13)))
# hertest 19: één van twee ophaalmomenten vervalt: de vraag wordt bijgewerkt; daarna het gewone verstrijken: niets
_ins14, _pat14 = [], []
try:
    W.LARA_VRAGEN = str(Path(tempfile.mkdtemp(prefix="lara-vragen14-")) / "agenda-lara-vragen.json")
    W._insert = lambda kal, body, tok, toch=False: _ins14.append(body) or {"id": "r1"}
    W._patch = lambda a, body, tok, **k: _pat14.append(body)
    W._prive_item_lezen = lambda eid, tok: None
    _paar = [lara("2026-11-03", "17:30", "!! Mehdi: Lara ophalen bij oma"), lara("2026-11-06")]
    W.lara_meldingen([], W.lara_vakantieweken(_paar, namen, date(2026, 10, 27)), [], "tok", _nu9)
    _b14 = _ins14[0]
    _x14 = [{"kalender": W.PRIVE_AGENDA, "id": "r1", "titel": _b14["summary"], "start": _b14["start"]["date"],
             "_merk": dict(_b14["extendedProperties"]["private"]), "hele_dag": True}]
    _paar[0]["titel"] = "vervalt (vakantie) " + _paar[0]["titel"]
    W.lara_meldingen([], W.lara_vakantieweken(_paar, namen, date(2026, 10, 27)), _x14, "tok", _nu9)
    _np14 = len(_pat14)
    # 4/11: de ophaling van 3/11 is voorbij (en vervallen), die van 6/11 blijft: geen bijwerking meer
    W.lara_meldingen([], W.lara_vakantieweken(_paar, namen, date(2026, 11, 4)), _x14, "tok",
                     datetime(2026, 11, 4, 9, 0, tzinfo=W.TIJDZONE))
finally:
    for k, v in _o9.items():
        setattr(W, k, v)
check("een ophaalmoment dat vervalt, verdwijnt uit de weekvraag (bijgewerkt), zonder nieuwe vraag",
      len(_ins14) == 1 and _np14 == 1 and "03/11" not in _pat14[0]["description"], str((len(_ins14), _np14)))
check("het gewone verstrijken van een afspraak werkt de weekvraag niet bij", len(_pat14) == _np14, str(len(_pat14)))
check("een eenmalig verjaardagsfeest in Lara's agenda is geen vast ophaalmoment",
      not W.lara_vakantieweken([lara("2026-11-04", "14:00", "Lara verjaardagsfeest bij Noor")], namen, date(2026, 10, 27)))
_vakophaal = [json.dumps(["!! Mehdi: Lara ophalen voor vakantie", "confirmed", {"dateTime": "2026-10-30T16:00:00+01:00"}, {}, "",
                          [], False]), "2026-10-30"]
check("een gewiste getimede ophaling met 'vakantie' in de titel geeft wel een vraag",
      (S.lara_wissing_kandidaat(LARA, {"id": "vo1", "status": "cancelled"}, _vakophaal, _nu, dagen, dekking) or {}).get("dag")
      == "2026-10-30")
check("de wisregel van laag 1 zegt: een Lara-reeks in een vakantie nooit stopzetten",
      "Lara-reeks in een vakantie nooit stopzetten" in (HIER / "claude-hooks" / "regels.json").read_text(encoding="utf-8"))
check("opeenvolgende vakantiedagen: één weekvraag, geen tweede en geen dagelijkse bijwerking als afspraken voorbij gaan",
      len(_ins11) == 1 and not _pat11, str((len(_ins11), len(_pat11))))
check("een weekvraag begint nooit in het verleden",
      W.lara_vakantieweken(_vier, namen, date(2026, 11, 4))[0]["van"] == "2026-11-04")
check("een pedagogische studiedag of vrije dag van de school is ook een vergelijkingsblok",
      all(W.LARA_VRIJ_RE.search(t) for t in ("Lara: pedagogische studiedag", "Lara vrije dag school", "geen school"))
      and not W.LARA_VRIJ_RE.search("!! Mehdi: [LA] Lara ophalen en thuis afzetten"))
_stud = {"id": "st1", "status": "cancelled"}
_studvorig = [json.dumps(["Lara: pedagogische studiedag", "confirmed", {"date": "2026-11-18"}, {"date": "2026-11-19"}, "", [],
                          False]), "2026-11-18"]
check("een studiedagblok weghalen geeft geen vraag 'gewiste Lara-afspraak'",
      S.lara_wissing_kandidaat(LARA, _stud, _studvorig, _nu, dagen, dekking) is None)
check("een weggehaalde weekvraag komt terug bij een nieuw ophaalmoment, niet bij dezelfde inhoud",
      _n10 == 1 and _n10b == 2 and len(_ins10) == 2, str((_n10, _n10b, len(_ins10))))

_o6 = (W._prive_item_lezen, W._patch)
_pat6 = []
try:
    W._patch = lambda a, body, tok, **k: _pat6.append(body)
    W._prive_item_lezen = lambda eid, tok: {"id": eid, "kalender": W.PRIVE_AGENDA, "titel": "VR Agendawacht: vaste Lara-afspraak",
                                            "_merk": {W.LARAMERK: "gewist:r:2026-11-10"}}
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
