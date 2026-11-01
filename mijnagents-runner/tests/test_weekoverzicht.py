"""Het weekoverzicht (koppelingen/weekoverzicht.py, driehoeksoverleg fase 2 van 27-10-2026). Legt vast, zonder netwerk:
- de weken: ISO in Brusselse tijd, maandagnacht is de afgesloten vorige week (X3), W53 van 2026 en de jaarwissel (K4);
- de uitkomsten komen uit de dagvaststelling en worden alleen opgeteld (Q1); privé telt apart, zonder titel;
- onbekend is onbekend: een dag zonder vaststelling, een ongelezen agenda of mail staan als voorbehoud, nooit als nul;
- geplande uren per firma uit de titelcode, privé een post, een onduidelijke code zichtbaar als onbekend (X3), dezelfde
  afspraak op twee agenda's een keer;
- geen naam van een persoon, ontvanger of privétitel in het overzicht of het weekbestand (K5);
- geen datum of start bovenaan, zodat de dagenpagina het niet als een dag ziet.
Met verzonnen namen. Draaien: python3 mijnagents-runner/tests/test_weekoverzicht.py
"""
import json
import os
import sys
from datetime import datetime, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "koppelingen"))
import dagvaststelling as V  # noqa: E402
import weekoverzicht as WO  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


BXL = WO.BRUSSEL
# ---------------------------------------------------------------------------------------------------- weken ---
check("weken: maandag 26-10 vlak na middernacht is de afgesloten week W43, niet de pas begonnen W44",
      WO.vorige_week(datetime(2026, 10, 26, 0, 30, tzinfo=BXL)) == "2026-W43")
check("weken: 23:30 UTC op zondag 25-10 is in Brussel al maandag",
      WO.vorige_week(datetime(2026, 10, 25, 23, 30, tzinfo=timezone.utc)) == "2026-W43")
check("weken: zondagavond is de afgesloten week nog de week ervoor",
      WO.vorige_week(datetime(2026, 10, 25, 21, 0, tzinfo=BXL)) == "2026-W42")
check("weken: 2026 heeft een W53, maandag 4 januari 2027 vat W53 samen",
      WO.vorige_week(datetime(2027, 1, 4, 1, 0, tzinfo=BXL)) == "2026-W53")
check("weken: de dagen van W53 lopen over de jaarwissel",
      WO.dagen_van("2026-W53") == ["2026-12-28", "2026-12-29", "2026-12-30", "2026-12-31", "2027-01-01", "2027-01-02",
                                   "2027-01-03"])
check("weken: W43 loopt van maandag 19-10 tot zondag 25-10",
      WO.dagen_van("2026-W43")[0] == "2026-10-19" and WO.dagen_van("2026-W43")[-1] == "2026-10-25")
try:
    WO.dagen_van("2026-W54")
    bestaat = True
except ValueError:
    bestaat = False
check("weken: W54 bestaat niet", not bestaat)
try:
    WO.vorige_week(datetime(2026, 10, 26, 1, 0))
    zonder = True
except ValueError:
    zonder = False
check("weken: een tijd zonder zone wordt geweigerd", not zonder)

# --------------------------------------------------------------------------- een dag uit de dagvaststelling ---
DAG = "2026-10-19"


def afspraak(id_, start, einde, titel, deelnemers=(), prive=False):
    return {"id": id_, "titel": titel, "start": f"{DAG}T{start}:00+02:00", "einde": f"{DAG}T{einde}:00+02:00",
            "deelnemers": list(deelnemers), "kalender": "werk", "_prive": prive}


def rij(uniek, start, minuten, personen, bron="zoom", prive=0):
    return {"uniek": uniek, "datum": DAG, "start": start, "minuten": minuten, "personen": personen, "bron": bron,
            "prive": prive, "dubbel_van": "", "afdeling": "", "thema": ""}


AFS = [afspraak("a1", "09:00", "10:00", "Mehdi: [HA-KO] 2605 - Bertha Verzonnen", ["bertha@voorbeeld.test"]),
       afspraak("a2", "11:00", "11:30", "Mehdi: [UB-PO] Cyriel Bedacht"),
       afspraak("a3", "14:00", "15:00", "Tandarts Dorien Geheim", prive=True)]
RIJEN = [rij("fathom:1", "09:02", 40, "Bertha Verzonnen, Mehdi", bron="fathom"),
         rij("zoom:meeting:x", "16:00", 25, "Egbert Nergens, Mehdi"),
         rij("zoom:meeting:p", "18:00", 12, "Fien Privaat", prive=1),
         rij("zoom:chat:q:2026-10-19", "10:00", 0, "Gust Kanaal")]
MAIL = V.mail_telling(DAG, {"mch@voorbeeld.test": {"berichten": [
    {"datum": f"{DAG}T08:00:00+02:00", "message_id": "<m1@x>", "onderwerp": "Offerte", "aan": ["Hilde Ontvanger <h@x>"]}],
    "onvolledig": []}}, {"mch@voorbeeld.test": {"berichten": [
        {"datum": f"{DAG}T08:30:00+02:00", "message_id": "<m2@x>", "onderwerp": "Antwoord", "aan": ["Hilde Ontvanger <h@x>"]}],
        "onvolledig": []}})
V1 = V.vaststellen(DAG, AFS, set(), RIJEN, {}, [], "volledig", MAIL,
                   {"whatsapp": "niet aangesloten", "telefoon": "aangesloten"}, lambda a: a.get("_prive"), "afgesloten",
                   chatstand="volledig")
d1 = WO.dag_samenvatting(DAG, V1, 2)
check("dag: de uitkomsten komen uit de dagvaststelling, privé apart",
      d1["afspraken"] == {"bevestigd": 1, "aanwijzing": 0, "geen spoor": 1, "privé": 1, "totaal": 3}, str(d1["afspraken"]))
check("dag: niet gepland telt de gesprekken zonder afspraak (de chat nooit)",
      d1["niet_gepland"]["gesprekken"] == 2 and d1["niet_gepland"]["minuten"] == 37, str(d1["niet_gepland"]))
check("dag: Zoom-chats en de stand van de kanalen gaan mee",
      d1["zoom_chats"] == 1 and d1["whatsapp"]["stand"] == "niet aangesloten" and d1["telefoon"]["stand"] == "aangesloten")
check("dag: van mail alleen de totalen, zonder postvakken", d1["mail"] == {"binnen": 1, "verzonden": 1, "onvolledig": False},
      str(d1["mail"]))
check("dag: de versie van de dag staat erbij", d1["dagversie"] == 2 and d1["vastgesteld"] is True)
check("dag: zonder vaststelling is de dag 'niet vastgesteld', zonder getallen",
      WO.dag_samenvatting("2026-10-20", None) == {"dag": "2026-10-20", "vastgesteld": False})
V2 = V.vaststellen("2026-10-21", [], None, [], None, None, "onbekend", None, None, lambda a: False)
d2 = WO.dag_samenvatting("2026-10-21", V2, 1)
check("dag: een ongelezen agenda, Zoom en mail zijn onbekend, nooit nul",
      d2["afspraken"] is None and d2["zoom_chats"] is None and d2["mail"] is None and d2["niet_gepland"]["bezoeken"] is None,
      json.dumps(d2, ensure_ascii=False))
check("dag (Codex fase 2, punt 1): zonder Zoom-stand en zonder gezien gesprek zijn de gesprekken onbekend, geen nul",
      d2["gesprekken"]["aantal"] is None and d2["niet_gepland"]["gesprekken"] is None and d2["niet_gepland"]["minuten"] is None,
      json.dumps(d2, ensure_ascii=False))
V3 = V.vaststellen("2026-10-22", [], set(), [dict(rij("zoom:meeting:z", "10:00", 20, "Egbert Nergens"), datum="2026-10-22")],
                   {}, [], "onbekend", None, None, lambda a: False)
d3 = WO.dag_samenvatting("2026-10-22", V3, 1)
check("dag: met een gezien gesprek blijft het aantal staan als ondergrens, ook zonder Zoom-stand",
      d3["gesprekken"]["aantal"] == 1 and d3["niet_gepland"]["gesprekken"] == 1, json.dumps(d3, ensure_ascii=False))

# -------------------------------------------------------------------------------------------------- planning ---
FIRMA = {"HA": "HARC", "UB": "UNAB"}


def firma_van(a):
    t = a["titel"]
    if "[HA-" in t and "[UB-" in t:
        return None
    for kort, code in FIRMA.items():
        if f"[{kort}-" in t:
            return code
    return None


PER_DAG = {DAG: AFS + [dict(AFS[0], kalender="H-Architects"),
                       afspraak("a4", "16:00", "17:00", "Mehdi: zonder code Ivo Nergens"),
                       afspraak("a5", "17:00", "17:30", "[HA-KO] en [UB-PO] tegelijk"),
                       dict(afspraak("a6", "08:00", "08:00", "hele dag"), hele_dag=True),
                       dict(afspraak("a7", "19:00", "19:00", "Mehdi: [UB-PO] zonder einde"), einde="")],
           "2026-10-26": [afspraak("a8", "09:00", "10:00", "[HA-KO] volgende week")]}
p = WO.planning_uren(PER_DAG, WO.dagen_van("2026-W43"), set(), lambda a: bool(a.get("_prive")), firma_van,
                     {"HARC": "H-Architects", "UNAB": "UNABO"})
uren = {x["code"]: (x["afspraken"], x["minuten"]) for x in p["uren_per_firma"]}
check("planning: uren per firma uit de titelcode; dezelfde afspraak op twee agenda's telt een keer",
      uren.get("HARC") == (1, 60), str(uren))
check("planning: een afspraak zonder einde telt mee zonder minuten", uren.get("UNAB") == (2, 30), str(uren))
check("planning: geen of een tegenstrijdige code blijft zichtbaar als onbekend (X3)", uren.get("onbekend") == (2, 90), str(uren))
check("planning: privé is een post, hele dag en een andere week tellen niet",
      uren.get("privé") == (1, 60) and p["afspraken"] == 6, str(uren))
check("planning: privé en onbekend staan onderaan, de firma's eerst",
      [x["code"] for x in p["uren_per_firma"]][-2:] == ["onbekend", "privé"], str(p["uren_per_firma"]))
check("planning: de firmanaam komt van de aanroeper (kern)", p["uren_per_firma"][0]["naam"] in ("H-Architects", "UNABO"))
_werk = afspraak("k1", "13:00", "14:00", "Mehdi: [HA-KO] 2605 - Bertha Verzonnen")
_prive = dict(_werk, kalender="privé", start=f"{DAG}T11:00:00+00:00", einde=f"{DAG}T12:00:00+00:00", _prive=True)
_uitkomst = []
for volgorde in ([_werk, _prive], [_prive, _werk]):
    q = WO.planning_uren({DAG: volgorde}, [DAG], set(), lambda a: bool(a.get("_prive")), firma_van, {})
    _uitkomst.append({x["code"]: (x["afspraken"], x["minuten"]) for x in q["uren_per_firma"]})
check("planning (Codex fase 2, punt 2): dezelfde afspraak op werk en privé, ook in een andere tijdschrijfwijze, is een "
      "keer privé, in welke volgorde ook", _uitkomst == [{"privé": (1, 60)}, {"privé": (1, 60)}], str(_uitkomst))
q = WO.planning_uren({DAG: [_werk, dict(_werk, titel=_werk["titel"], kalender="UNABO", _code="UNAB")]}, [DAG], set(),
                     lambda a: False, lambda a: a.get("_code") or firma_van(a), {})
check("planning: twee kopieën met een andere firmacode tellen een keer, als onbekend",
      {x["code"]: x["afspraken"] for x in q["uren_per_firma"]} == {"onbekend": 1}, str(q["uren_per_firma"]))
check("planning: een ongelezen agenda maakt de planning onvolledig, een ongelezen geheel onbekend",
      WO.planning_uren(PER_DAG, WO.dagen_van("2026-W43"), {"archief"}, lambda a: False, firma_van, {})["stand"] == "onvolledig"
      and WO.planning_uren(PER_DAG, WO.dagen_van("2026-W43"), None, lambda a: False, firma_van, {})["afspraken"] is None)

# --------------------------------------------------------------------------------------------------- de week ---
w = WO.samenvatten("2026-W43", {DAG: (V1, 2), "2026-10-21": (V2, 1)}, p, "2026-10-26T23:40:00+00:00")
t = w["totaal"]
check("week: zeven dagen, twee vastgesteld", len(w["dagen"]) == 7 and t["vastgesteld"] == 2 and t["dagen"] == 7)
check("week: de totalen tellen alleen wat gekend is",
      t["afspraken"]["bevestigd"] == 1 and t["afspraken"]["totaal"] == 3 and t["gesprekken"]["aantal"] == d1["gesprekken"]["aantal"],
      json.dumps(t, ensure_ascii=False))
check("week: elk voorbehoud staat erbij: niet vastgestelde dagen, ongekende afspraken en mail, kanalen",
      "2026-10-20 niet vastgesteld" in t["voorbehoud"] and "afspraken op een dag niet gekend" in t["voorbehoud"]
      and "mail onvolledig" in t["voorbehoud"] and "WhatsApp niet aangesloten" in t["voorbehoud"]
      and "telefoon niet elke dag aangesloten" in t["voorbehoud"], str(t["voorbehoud"]))
check("week: telefoon telt alleen de aangesloten dagen", t["telefoon"]["aangesloten_dagen"] == 1)
check("week: geen datum of start bovenaan (de dagenpagina leest die als een dag)",
      "datum" not in w and "start" not in w and w["soort"] == "weekoverzicht" and w["versie"] == 1)
check("week: een week zonder enige vaststelling heeft overal onbekend, nooit nul",
      WO.samenvatten("2026-W44", {}, p, "x")["totaal"]["afspraken"] is None)
md = WO.tekst(w)
alles = json.dumps(w, ensure_ascii=False) + md
namen = ("Bertha", "Cyriel", "Dorien", "Egbert", "Fien", "Gust", "Hilde", "Ivo", "Tandarts")
check("privé en namen (K5): geen persoon, ontvanger of titel in het overzicht of het weekbestand",
      not [n for n in namen if n in alles], str([n for n in namen if n in alles]))
check("weekbestand: kort, met voorbehoud, per dag en uren met een Nederlandse komma",
      md.startswith("# Week 2026-W43 (19-10 tot 25-10)") and "Voorbehoud:" in md and "- di 20-10: niet vastgesteld" in md
      and "1,0 uur" in md, md[:400])
check("weekbestand: geen gedachtestreepje", "—" not in md and "–" not in md)
check("week: een onbekende Zoom-dag staat als voorbehoud: de gesprekken zijn een ondergrens",
      "gesprekken zijn een ondergrens: Zoom niet elke dag volledig gelezen" in t["voorbehoud"], str(t["voorbehoud"]))
check("week: de stand van WhatsApp en telefoon over de week",
      t["whatsapp"]["stand"] == "niet aangesloten" and t["telefoon"]["stand"] == "deels aangesloten", str(t["telefoon"]))
V4 = V.vaststellen("2026-10-23", [], set(), [], {}, [], "volledig", MAIL, {"whatsapp": "onbekend voor deze dag",
                                                                          "telefoon": "aangesloten"}, lambda a: False)
w4 = WO.samenvatten("2026-W43", {"2026-10-23": (V4, 1)}, p, "x")["totaal"]
check("week (Codex fase 2, punt 1): een onbekende WhatsApp-dag is nooit 'niet aangesloten'",
      w4["whatsapp"]["stand"] == "onbekend" and "WhatsApp op een dag onbekend" in w4["voorbehoud"]
      and "WhatsApp niet aangesloten" not in w4["voorbehoud"], json.dumps(w4["whatsapp"]))
# WA-6 (T-0120): een kanaal dat die dag niet aangesloten was en geen rij had, is onbekend (None), nooit 0. Wat wel gezien
# is, blijft als ondergrens; een aangesloten dag zonder rij is een echte nul.
_stil = {"whatsapp": "stil sinds 27-10 10:07", "telefoon": "onbekend voor deze dag", "sms": "stil sinds 27-10 10:07",
         "xelion": "onbekend voor deze dag"}
d6 = WO.dag_samenvatting("2026-10-13", V.vaststellen("2026-10-13", [], set(), [], {}, [], "volledig", MAIL, _stil,
                                                      lambda a: False), 3)
check("dag (WA-6): stil of onbekend en geen rij is onbekend, geen 0",
      all(v is None for k in ("whatsapp", "telefoon", "sms", "xelion") for s_, v in d6[k].items() if s_ != "stand")
      and d6["whatsapp"]["stand"] == "stil sinds 27-10 10:07" and d6["telefoon"]["stand"] == "onbekend voor deze dag",
      json.dumps({k: d6[k] for k in ("whatsapp", "telefoon", "sms", "xelion")}))
_wa = [{"uniek": "whatsapp:0a1b:2026-10-13", "datum": "2026-10-13", "start": "09:00", "minuten": 0,
        "personen": "Lien Proef", "thema": "5 berichten (2 in, 3 uit), 09:00 tot 09:30", "prive": 1, "bron": "whatsapp",
        "dubbel_van": ""}]
d6b = WO.dag_samenvatting("2026-10-13", V.vaststellen("2026-10-13", [], set(), _wa, {}, [], "volledig", MAIL, _stil,
                                                       lambda a: False), 3)
d6c = WO.dag_samenvatting("2026-10-13", V.vaststellen("2026-10-13", [], set(), [], {}, [], "volledig", MAIL,
                                                       {k: "aangesloten" for k in _stil}, lambda a: False), 3)
check("dag (WA-6): wat gezien is, blijft een ondergrens, een nul ernaast is onbekend; aangesloten zonder rij is 0",
      d6b["whatsapp"]["berichten"] == 5 and d6b["whatsapp"]["gesprekken"] == 1 and d6b["whatsapp"]["oproepen"] is None
      and d6b["whatsapp"]["minuten"] is None and d6b["telefoon"]["oproepen"] is None
      and d6c["whatsapp"]["berichten"] == 0 and d6c["telefoon"]["oproepen"] == 0 and d6c["xelion"]["gemist"] == 0,
      json.dumps([d6b["whatsapp"], d6c["whatsapp"]]))
check("week (WA-6): een onbekende dag telt niet mee en geeft geen fout",
      WO.samenvatten("2026-W42", {"2026-10-13": (V.vaststellen("2026-10-13", [], set(), [], {}, [], "volledig", MAIL,
                                                               _stil, lambda a: False), 3)}, p, "x")["totaal"]
      ["whatsapp"]["stand"] == "onbekend")

# Codex-controle fase 2, ronde 3 (K5): een bewaarde dagtelling met een onverwacht naamveld, ook genest
_vies = dict(d1, naam="Jozef Lekker", afspraken=dict(d1["afspraken"], wie="Karel Lekker"),
             whatsapp=dict(d1["whatsapp"], met="Lien Lekker"), standen=dict(d1["standen"], wie="Mon Lekker"))
_wv = WO.samenvatten("2026-W43", {DAG: _vies}, p, "x")
_wvt = json.dumps(_wv, ensure_ascii=False) + WO.tekst(_wv)
check("K5 (Codex ronde 3): uit een bewaarde telling komen alleen de velden van het contract, nooit een naam",
      "Lekker" not in _wvt and _wv["dagen"][0]["afspraken"] == d1["afspraken"]
      and _wv["dagen"][0]["whatsapp"]["stand"] == d1["whatsapp"]["stand"], _wvt[:300])
check("K5: een bewaarde telling en een verse vaststelling geven dezelfde week",
      WO.samenvatten("2026-W43", {DAG: d1}, p, "x") == WO.samenvatten("2026-W43", {DAG: (V1, 2)}, p, "x"))

# ------------------------------------------------- van begin tot eind: runner, klaarzet en de pagina /week (K5) ---
BORD = os.path.join(os.path.dirname(os.path.dirname(HIER)), "mijnagents")
try:
    import tempfile
    os.environ["AGENTS_DB"] = os.path.join(tempfile.mkdtemp(), "week.db")
    os.environ["AGENTS_TOKEN"] = "proef"
    sys.path.insert(0, BORD)
    import app as A  # noqa: E402
except ImportError as e:
    A = None
    print(f"  overgeslagen: de pagina /week zonder Flask ({e}); CI installeert Flask voor deze job")
if A is not None:
    C = A.app.test_client()
    r = C.post("/api/klaarzet", headers={"X-Agents-Token": "proef"}, json={"items": [{
        "van": "dagbundelaar", "voor": "mehdi", "soort": "weekoverzicht", "sleutel": "2026-W43", "titel": "Week 2026-W43",
        "uniek": "weekoverzicht:2026-W43", "inhoud": json.dumps(w, ensure_ascii=False)}]})
    pagina = C.get("/week/2026-W43", headers={"X-authentik-groups": "admin", "X-authentik-username": "proef"})
    html = pagina.get_data(as_text=True)
    bak = C.get("/api/klaarzet?uniek=weekoverzicht:2026-W43", headers={"X-Agents-Token": "proef"}).get_json() or {}
    inhoud = "".join(str(x.get("inhoud") or "") for x in bak.get("items") or [])
    check("van begin tot eind: het weekoverzicht van de runner staat op het bord en op de pagina",
          r.status_code == 200 and pagina.status_code == 200 and json.loads(inhoud)["week"] == "2026-W43"
          and "niet vastgesteld" in html and "H-Architects" in html, f"{r.status_code} {pagina.status_code} {inhoud[:80]}")
    check("van begin tot eind (K5): geen persoon, ontvanger of privétitel in klaarzet of op de pagina",
          not [n for n in namen if n in html or n in inhoud], str([n for n in namen if n in html or n in inhoud]))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
