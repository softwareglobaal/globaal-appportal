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

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
