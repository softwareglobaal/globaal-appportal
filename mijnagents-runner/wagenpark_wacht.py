#!/usr/bin/env python3
"""De Wagenparkwacht: beheert de wagens van H-Invest, Harmoniebouw, H-Architects en Melodie.

Mandaat van Mehdi, 25-09-2026: "alle facturen daarvan verzamelen, zodat ik die in de folders kan
plaatsen waar die auto's zijn. Alles volledig in beeld: wanneer ze gekocht zijn, wat er gebeurd is
elke keer dat we naar de garage gaan, de kilometerstanden, wanneer ze gekeurd moeten worden, naar
onderhoud moeten, en wanneer de belastingen en verkeersbelastingen betaald moeten worden. Een agent
die echt beheer doet." H-Invest heette vroeger H-Aannemingen.

Elke dag, een keer na 07:00 (Brusselse tijd):
  1. termijnen per wagen: keuring, groene kaart, verzekering, leasing, verkeersbelasting, onderhoud;
  2. post over wagens in de postvakken van de groep koppelen aan de juiste wagen (plaat, oude plaat,
     chassis, polis of een model dat maar een wagen heeft), via de postbus, alleen lezen;
  3. per wagen een tijdlijn en een lijst 'te klasseren' met de map waar het document hoort;
  4. een overzicht in Data uit Mehdi/Wagenparkwacht, en een signaal aan Mehdi op 30, 14 en 3 dagen
     voor een termijn en een keer als hij verlopen is.

Het register (mijnagents-data/wagenpark/voertuigen.json) is de waarheid over de wagens; de eerste
keer komt het uit eenmalig/wagenpark_zaad.json. Ik verplaats geen bestanden, betaal niets, en
schrijf niets in Dropbox: documenten in de map van de wagen zetten gebeurt op de Mac.

    wagenpark_wacht.py           de ronde van vandaag (een keer per dag)
    wagenpark_wacht.py --nu      nu een ronde, ook als die vandaag al liep
    wagenpark_wacht.py --droog   tonen wat hij zou melden, niets naar het bord
"""
import json
import os
import re
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402
import postvak  # noqa: E402

NAAM = "wagenpark-wacht"
BRUSSEL = ZoneInfo("Europe/Brussels")
DATA = os.path.expanduser("~/appportal/mijnagents-data/wagenpark")
REGISTER = os.path.join(DATA, "voertuigen.json")
TIJDLIJN = os.path.join(DATA, "tijdlijn.json")
STAAT = os.path.join(DATA, "staat.json")
EXPORT = os.path.expanduser("~/appportal/mijnagents-data/export/Wagenparkwacht")  # via de Mac-sync naar Data uit Mehdi
ZAAD = os.path.join(HIER, "eenmalig", "wagenpark_zaad.json")

# Waar post over wagens binnenkomt (onderzoek 25-09-2026): KBC-leasing en -verzekering, Ethias en
# Autoveiligheid in info@h-invest.be; Tesla en een keuring in mch@; Harmoniebouw heeft eigen postvakken.
POSTVAKKEN = ["info@h-invest.be", "boekhouding@h-invest.be", "mch@h-architects.be", "info@h-architects.be",
              "kantoor@harmoniebouw.be", "boekhouding@harmoniebouw.be", "admin1@harmoniebouw.be"]
EERSTE_KEER_DAGEN, DAGELIJKS_DAGEN = 365, 14
SOORTEN = [  # soort, woorden in het onderwerp of de afzender, submap in het voertuigdossier
    ("keuring", ["autoveiligheid", "keuring", "aibv", "sbat", "goca", "autokeuring"], "04_Keuring"),
    ("inschrijving", ["inschrijving", "nummerplaat", "kentekenbewijs", "div ", "gelijkvormigheid", "car-pass", "carpass"],
     "03_Inschrijving en boorddocumenten"),
    ("verzekering", ["verzeker", "polis", "ethias", "axa", "groene kaart", "schorsing", "premie"], "06_Verzekering"),
    ("leasing", ["leasing", "lease", "renting", "alpha credit", "alphacredit", "aankoopoptie"], "00_Basisgegevens & contract"),
    ("belasting", ["verkeersbelasting", "biv", "belastingdienst", "vlabel", "aanslagbiljet"], "01_Facturen"),
    ("boete", ["boete", "parkeer", "parking.brussels", "onmiddellijke inning", "overtreding", "pv "], "07_Boetes"),
    ("schade", ["schade", "ongeval", "schadegeval", "aanrijding"], "02_Gebruik & historiek"),
    ("garage", ["garage", "onderhoud", "herstelling", "koppeling", "vliegwiel", "banden", "bestdrive", "carrosserie",
                "cloet", "carrect", "belauto", "d'ieteren", "offerte"], "05_Technisch en Onderhoud"),
    ("tanken", ["tankkaart", "fuel", "maes mobility", "kinesis", "fleetpass", "radius"], "02_Gebruik & historiek"),
]
TERMIJNEN = [("keuring_tot", "keuring"), ("groene_kaart_tot", "groene kaart"), ("verzekering.tot", "verzekering"),
             ("leasing.einde", "einde leasing"), ("verkeersbelasting_vervaldag", "verkeersbelasting"),
             ("onderhoud_volgend", "onderhoud")]
TREDEN = (30, 14, 3)
WEG = ("verkocht", "geschrapt", "buiten gebruik")
ONDERDELEN = os.path.join(HIER, "werkwijze", "wagenpark-onderdelen.json")
OPZEG_TREDEN = (60, 30, 14)  # tijd om offertes te vragen: een nieuwe verzekeraar geeft het eerste jaar 20 tot 25% korting
VZ_SQL = ("select coalesce(json_agg(json_build_object('id', v.id, 'verzekeraar', v.verzekeraar, 'polisnummer', v.polisnummer, "
          "'object', v.object, 'startdatum', v.startdatum, 'einddatum', v.einddatum, 'opzegtermijn_maanden', v.opzegtermijn_maanden, "
          "'jaarpremie', v.jaarpremie, 'omschrijving', v.omschrijving, 'firma', f.code, 'extra', v.extra)), '[]'::json) "
          "from vermogen.verzekering v left join kern.firma f on f.id = v.firma_id "
          "where lower(v.soort) = 'auto' and coalesce(v.actief, true)")


def verzekeringen():
    """De autoverzekeringen uit vermogen.verzekering: de bron, Mehdi beheert ze in de vastgoedapp
    (vermogen.globaal.be, Verzekeringen, soort Auto, object = nummerplaat). Leeg als de databank niet antwoordt."""
    import subprocess
    try:
        c = os.environ.get("KERN_POSTGRES_CONTAINER", "appportal-postgresql-1")
        g = subprocess.run(["docker", "exec", c, "sh", "-c", "echo $POSTGRES_USER"], capture_output=True, text=True,
                           timeout=30).stdout.strip() or "postgres"
        r = subprocess.run(["docker", "exec", c, "psql", "-U", g, "-d", os.environ.get("KERN_DB", "appportal"), "-At", "-c", VZ_SQL],
                           capture_output=True, text=True, timeout=60)
        return json.loads(r.stdout.strip() or "[]") if r.returncode == 0 else []
    except Exception:  # noqa: BLE001
        return []


def polissen_van(v, vz):
    return [p for p in vz or [] if _norm(v["plaat"]) and _norm(v["plaat"]) in _norm(p.get("object"))]


def _min_maanden(d, n):
    """d min n maanden (n negatief = erbij), met de dag begrensd op het einde van de maand."""
    import calendar
    j, m = divmod(d.month - 1 - int(n), 12)
    return date(d.year + j, m + 1, min(d.day, calendar.monthrange(d.year + j, m + 1)[1]))


def _norm(tekst):
    return re.sub(r"[^A-Z0-9]", "", (tekst or "").upper())


def lees_register():
    """Het register; de eerste keer uit het zaad in de repo."""
    try:
        return json.load(open(REGISTER, encoding="utf-8"))
    except (OSError, ValueError):
        zaad = json.load(open(ZAAD, encoding="utf-8"))
        os.makedirs(DATA, exist_ok=True)
        json.dump(zaad, open(REGISTER, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return zaad


def _veld(v, pad):
    for deel in pad.split("."):
        v = (v or {}).get(deel) if isinstance(v, dict) else None
    return v


def termijnen(register, vandaag, vz=None):
    """[(voertuig, wat, datum, dagen)] voor wagens in gebruik, plus [(voertuig, wat)] zonder datum.
    Staat de wagen in vermogen.verzekering, dan komen vervaldag en opzegdatum van daar, niet uit het register."""
    uit, onbekend = [], []
    for v in register["voertuigen"]:
        if v.get("status") not in ("in gebruik", "onzeker"):
            continue
        pol = polissen_van(v, vz)
        for p in pol:
            try:
                einde = date.fromisoformat(str(p.get("einddatum"))[:10])
            except ValueError:
                continue
            naam = p.get("verzekeraar") or "verzekeraar"
            uit.append((v, f"vervaldag verzekering {naam}", einde, (einde - vandaag).days))
            opzeg = _min_maanden(einde, p.get("opzegtermijn_maanden") or 3)
            uit.append((v, f"opzeggen verzekering {naam}", opzeg, (opzeg - vandaag).days))
        for pad, wat in TERMIJNEN:
            if pad == "verzekering.tot" and pol:
                continue
            d = _veld(v, pad)
            if not d:
                if pad in ("keuring_tot", "verzekering.tot") and v.get("status") == "in gebruik":
                    onbekend.append((v, wat))
                continue
            try:
                dd = date.fromisoformat(d)
            except ValueError:
                continue
            uit.append((v, wat, dd, (dd - vandaag).days))
    return sorted(uit, key=lambda t: t[3]), onbekend


def welke_wagen(tekst, register):
    """De wagen waar een tekst over gaat: plaat, oude plaat, chassis, polis, of een model dat maar een wagen heeft."""
    n = _norm(tekst)
    for v in register["voertuigen"]:
        sleutels = [v["plaat"]] + v.get("platen_oud", []) + [v.get("chassis") or "", _veld(v, "verzekering.polis") or ""]
        if any(s and len(_norm(s)) >= 6 and _norm(s) in n for s in sleutels):
            return v, "plaat, chassis of polis"
    woorden = set(re.findall(r"[A-Z]{4,}", (tekst or "").upper()))
    for w in woorden:
        kandidaten = [v for v in register["voertuigen"] if w in _norm(v["merk_model"]) and w not in ("FORD", "OPEL", "CUSTOM", "SPORTS", "TOURER")]
        if len(kandidaten) == 1:
            return kandidaten[0], f"model {w.lower()}"
    return None, ""


def soort_van(tekst):
    t = (tekst or "").lower()
    for soort, woorden, submap in SOORTEN:
        if any(w in t for w in woorden):
            return soort, submap
    return "", ""


def post_koppelen(register, tijdlijn, dagen, ag):
    """Nieuwe post over wagens in de tijdlijn zetten. Geeft (nieuw, niet leesbare postvakken)."""
    sinds = (datetime.now(BRUSSEL) - timedelta(days=dagen)).date().isoformat()
    nieuw, weg = 0, []
    for adres in POSTVAKKEN:
        if not postvak.postvak(adres):
            weg.append(adres)
            continue
        try:
            berichten = postvak.koppen_mappen(adres, postvak.mappen_van(adres), sinds, ag, plafond=3000)
        except Exception as e:  # noqa: BLE001
            weg.append(adres)
            ag.log("post", "bron", f"{adres}: {type(e).__name__}: {str(e)[:100]}")
            continue
        for b in berichten:
            ond = postvak.schoon(b.get("onderwerp"))
            if postvak.trieer(b)[0] in ("rommel", "verdacht") or re.match(
                    r"(ontvangstbevestiging|accus. de r.ception|automatic reply|automatisch antwoord|out of office)", ond, re.I):
                continue
            tekst = f"{ond} {b.get('van_naam') or ''} {b.get('van') or ''}"
            v, hoe = welke_wagen(ond, register)
            soort, submap = soort_van(tekst)
            if not v and not (soort and re.search(r"wagen|auto|voertuig|keuring|verkeersbelasting|nummerplaat", tekst, re.I)):
                continue
            uniek = (b.get("message_id") or f"{adres}:{b['uid']}")[:200]
            if uniek in tijdlijn:
                continue
            tijdlijn[uniek] = {"datum": (b.get("datum") or "")[:10], "postvak": adres, "uid": b.get("uid"),
                               "van": b.get("van_naam") or b.get("van"), "onderwerp": ond[:160],
                               "plaat": v["plaat"] if v else None, "herkend_op": hoe, "soort": soort or "overig",
                               "doelmap": (v["mappen"][-1] + "/" + submap) if v and v.get("mappen") and submap else None,
                               "geklasseerd": False}
            nieuw += 1
    return nieuw, weg


def overzicht(register, tijdlijn, lijst, onbekend, vandaag):
    r = [f"# Wagenpark, {vandaag.strftime('%d-%m-%Y')}", "",
         "Gemaakt door De Wagenparkwacht. Het register is mijnagents-data/wagenpark/voertuigen.json op de VM; "
         "wat hier staat, verandert daar. Niets is verplaatst of verwijderd.", "", "## Termijnen", ""]
    for v, wat, d, n in lijst:
        staat = f"verlopen sinds {d.strftime('%d-%m-%Y')}" if n < 0 else f"over {n} dagen ({d.strftime('%d-%m-%Y')})"
        r.append(f"- {v['plaat']} {v['merk_model']} ({v.get('gebruik')}): {wat} {staat}")
    for v, wat in onbekend:
        r.append(f"- {v['plaat']} {v['merk_model']}: {wat} niet bekend")
    per = {}
    for e in tijdlijn.values():
        per.setdefault(e.get("plaat") or "onbekende wagen", []).append(e)
    weg = [v for v in register["voertuigen"] if v.get("status") in WEG]
    if weg:
        r += ["", "Niet meer in het wagenpark (tellen niet mee): " + "; ".join(f"{v['plaat']} {v['merk_model']} ({v['status']})" for v in weg)]
    for v in register["voertuigen"]:
        if v.get("status") in WEG:
            continue
        r += ["", f"## {v['plaat']} {v['merk_model']}", "",
              f"- Status: {v.get('status')}; firma nu: {v.get('firma')}; gebruik: {v.get('gebruik')}",
              f"- Chassis: {v.get('chassis')}; oude platen: {', '.join(v.get('platen_oud') or []) or 'geen'}",
              f"- Verleden: " + "; ".join(f"{h['firma']} ({h.get('van') or '?'} tot {h.get('tot') or 'nu'})" for h in v.get("firma_historiek") or []),
              f"- Mappen: " + "; ".join(v.get("mappen") or ["geen"])]
        for vraag in v.get("open_vragen") or []:
            r.append(f"- Open vraag: {vraag}")
        posten = sorted(per.get(v["plaat"], []), key=lambda e: e["datum"], reverse=True)
        if posten:
            r.append("- Post (nieuwste eerst):")
            for e in posten[:12]:
                r.append(f"  - {e['datum']} {e['soort']}: {e['van']}, {e['onderwerp'][:90]} ({e['postvak']})"
                         + ("" if e.get("geklasseerd") else f"; te klasseren in {e['doelmap'] or 'map nog te bepalen'}"))
    los = sorted(per.get("onbekende wagen", []), key=lambda e: e["datum"], reverse=True)
    if los:
        r += ["", "## Post over een wagen die ik niet kon toewijzen", ""]
        r += [f"- {e['datum']} {e['soort']}: {e['van']}, {e['onderwerp'][:100]} ({e['postvak']})" for e in los[:30]]
    return "\n".join(r)


def dashboard(register, tijdlijn, lijst, onbekend, vandaag, vz=None):
    """De gegevens voor het wagenparkdashboard op vermogen.globaal.be/wagenpark-dashboard (alleen lezen daar).
    Per wagen: het register, de bestuurders, de termijnen met hun stand, de onderhoudshistoriek (uit het
    register en uit de post van garages) en de post. Nooit pincodes of kaartnummers: die staan niet in het register."""
    per = {}
    for e in tijdlijn.values():
        per.setdefault(e.get("plaat") or "", []).append(e)
    termijn_per = {}
    for v, wat, d, n in lijst:
        termijn_per.setdefault(v["plaat"], []).append(
            {"wat": wat, "datum": d.isoformat(), "dagen": n,
             "stand": "verlopen" if n < 0 else ("dringend" if n <= 14 else ("binnenkort" if n <= 30 else "ok"))})
    for v, wat in onbekend:
        termijn_per.setdefault(v["plaat"], []).append({"wat": wat, "datum": None, "dagen": None, "stand": "onbekend"})
    wagens = []
    try:
        blik = vooruitblik(register, vandaag)
    except Exception as e:  # noqa: BLE001  een fout in de vooruitblik mag het dashboard niet tegenhouden
        blik = {}
        print("vooruitblik mislukt:", type(e).__name__, e, file=sys.stderr)
    for v in register["voertuigen"]:
        post = sorted(per.get(v["plaat"], []), key=lambda e: e["datum"], reverse=True)
        onderhoud = [dict(o, herkomst="register") for o in v.get("onderhoud") or []]
        onderhoud += [{"datum": e["datum"], "soort": e["soort"], "garage": e["van"], "km": None, "bedrag": None,
                       "omschrijving": e["onderwerp"], "bron": f"mail {e['postvak']}", "herkomst": "post"}
                      for e in post if e["soort"] in ("garage", "keuring", "schade")]
        onderhoud.sort(key=lambda o: o.get("datum") or "", reverse=True)
        km = sorted(v.get("km") or [], key=lambda k: k.get("datum") or "")
        extra = blik.get(v["plaat"], {})
        wagens.append(dict(v, polissen=polissen_van(v, vz), vooruitblik=extra.get("vooruitblik", []), vaak=extra.get("vaak", {}),
                           km_per_dag=extra.get("km_per_dag"), termijnen=sorted(termijn_per.get(v["plaat"], []), key=lambda t: (t["dagen"] is None, t["dagen"] or 0)),
                           onderhoud=onderhoud, post=post[:60], laatste_km=km[-1] if km else None,
                           te_klasseren=sum(1 for e in post if not e.get("geklasseerd"))))
    return {"gemaakt": datetime.now(BRUSSEL).isoformat(timespec="minutes"), "vandaag": vandaag.isoformat(),
            "wagens": wagens, "niet_toegewezen": sorted(per.get("", []), key=lambda e: e["datum"], reverse=True)[:40],
            "mappen_standaard": register.get("submappen_standaard", [])}


def _bedrag(s):
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})*(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)", str(s or ""))
    if not m:
        return None
    x = m.group(1).replace(" ", "")
    x = x.replace(".", "").replace(",", ".") if "," in x else x
    try:
        return float(x)
    except ValueError:
        return None


def _werken(o):
    """De werken van een onderhoudsregel als teksten: uit de factuur (werken) of anders de omschrijving."""
    w = o.get("werken") or []
    if w:
        return [(f"{x.get('onderdeel') or ''} {x.get('omschrijving') or ''}", x.get("bedrag")) for x in w]
    return [(f"{o.get('soort') or ''} {o.get('omschrijving') or ''}", o.get("bedrag"))]


def vooruitblik(register, vandaag):
    """Per wagen die er nog is: wanneer elk onderdeel weer aan de beurt is, wat het volgens de eigen facturen kost,
    en welke herstellingen vaak terugkomen. Regels in werkwijze/wagenpark-onderdelen.json; een fabrieksgegeven gaat voor."""
    regels = json.load(open(ONDERDELEN, encoding="utf-8"))
    prijzen = {}
    for v in register["voertuigen"]:
        for o in v.get("onderhoud") or []:
            # Alleen een aparte factuurlijn telt als prijs van een onderdeel; het totaal van een factuur
            # hoort niet bij de ruitenwissers omdat die er toevallig ook op stonden (gezien 25-09-2026: 945 EUR).
            for tekst, bedrag in [(f"{x.get('onderdeel') or ''} {x.get('omschrijving') or ''}", x.get("bedrag")) for x in o.get("werken") or []]:
                for r in regels["onderdelen"]:
                    if any(w in tekst.lower() for w in r["woorden"]) and _bedrag(bedrag):
                        prijzen.setdefault(r["onderdeel"], []).append(_bedrag(bedrag))
    uit = {}
    for v in register["voertuigen"]:
        if v.get("status") in WEG or v.get("status") == "stilgelegd":
            continue
        fab = v.get("fabrikant") or {}
        km = sorted([k for k in v.get("km") or [] if k.get("km") and k.get("datum")], key=lambda k: k["datum"])
        per_dag = None
        if len(km) >= 2:
            dagen = (date.fromisoformat(km[-1]["datum"][:10]) - date.fromisoformat(km[0]["datum"][:10])).days
            if dagen > 60:
                per_dag = (km[-1]["km"] - km[0]["km"]) / dagen
        blik, vaak = [], {}
        for r in regels["onderdelen"]:
            gedaan = []
            for o in v.get("onderhoud") or []:
                if any(any(w in tekst.lower() for w in r["woorden"]) for tekst, _ in _werken(o)):
                    gedaan.append(o)
            if r.get("alleen_bij_klacht"):
                if len(gedaan) >= 2:
                    vaak[r["onderdeel"]] = len(gedaan)
                continue
            i_km, i_m = r.get("interval_km"), r.get("interval_maanden")
            herkomst = "richtwaarde"
            if r["onderdeel"].startswith("onderhoudsbeurt"):
                i_km, i_m, herkomst = fab.get("interval_km"), fab.get("interval_maanden"), "fabrikant"
            if r.get("alleen_als_riem"):
                i_km, i_m, herkomst = fab.get("riem_km"), fab.get("riem_maanden"), "fabrikant"
            if not (i_km or i_m) or i_km == "fabrikant":
                continue
            laatst = max(gedaan, key=lambda o: o.get("datum") or "") if gedaan else None
            basis_d = (laatst or {}).get("datum") or v.get("eerste_inschrijving")
            basis_km = (laatst or {}).get("km") or (0 if not laatst else None)
            kandidaten = []
            if i_m and basis_d:
                d0 = date.fromisoformat(str(basis_d)[:10])
                kandidaten.append(_min_maanden(d0, -int(i_m)))
            verwacht_km = (basis_km + i_km) if (i_km and basis_km is not None) else None
            if verwacht_km and per_dag and km:
                kandidaten.append(date.fromisoformat(km[-1]["datum"][:10]) + timedelta(days=max(0, (verwacht_km - km[-1]["km"]) / max(per_dag, 1))))
            if not kandidaten:
                continue
            wanneer = min(kandidaten)
            kost = prijzen.get(r["onderdeel"])
            n = (wanneer - vandaag).days
            blik.append({"onderdeel": r["onderdeel"], "laatst": (laatst or {}).get("datum"), "laatst_km": (laatst or {}).get("km"),
                         "interval": " of ".join(x for x in (f"{i_m} maanden" if i_m else "", f"{i_km:,} km".replace(",", ".") if i_km else "") if x),
                         "herkomst": herkomst, "verwacht": wanneer.isoformat(), "verwacht_km": verwacht_km, "dagen": n,
                         # Zonder historiek weet ik niet of het te laat is: een richtwaarde zonder factuur is een vraag, geen alarm.
                         "stand": ("geen historiek" if (not laatst and herkomst == "richtwaarde") else
                                   "te laat" if n < 0 else ("binnenkort" if n <= regels.get("vooruit_dagen", 90) else "later")),
                         "kost_eigen_facturen": round(sum(kost) / len(kost)) if kost else None, "groot": r.get("groot", False)})
            if len([o for o in gedaan if o.get("soort") == "herstelling"]) >= 2:
                vaak[r["onderdeel"]] = len(gedaan)
        uit[v["plaat"]] = {"vooruitblik": sorted(blik, key=lambda b: b["dagen"]), "vaak": vaak, "km_per_dag": round(per_dag) if per_dag else None}
    return uit


def signalen(lijst, vandaag, register=None):
    """Een signaal op 30, 14 en 3 dagen voor een termijn en een keer als hij verlopen is; uniek per trede.
    Plus een signaal per achterstand op een lening of renting (25-09-2026: KBC dreigde bij 2BAS423 met inbeslagname)."""
    uit = []
    for v in (register or {}).get("voertuigen", []):
        a = (v.get("leasing") or {}).get("achterstand")
        if a and v.get("status") not in WEG:
            uit.append({"voor": "mehdi", "soort": "signaal", "sleutel": v["plaat"],
                        "titel": re.sub("stil", "st.l", f"Wagenpark: achterstand {v['leasing'].get('maatschappij') or ''} op {v['plaat']} "
                                                        f"({v['merk_model']}): {str(a)[:120]}", flags=re.I),
                        "uniek": f"wagenpark:{v['plaat']}:achterstand:{(v['leasing'].get('contract') or '')[:40]}",
                        "inhoud": {"plaat": v["plaat"], "financiering": v["leasing"],
                                   "voorstel": "achterstand betalen, dan pas de aankoopoptie; bewijs in 00_Basisgegevens & contract"}})
    for v, wat, d, n in lijst:
        treden = OPZEG_TREDEN if wat.startswith("opzeggen verzekering") else TREDEN
        trede = "verlopen" if n < 0 else next((str(t) for t in sorted(treden) if n <= t), None)
        if not trede:
            continue
        staat = f"verlopen sinds {d.strftime('%d-%m-%Y')}" if n < 0 else f"over {n} dagen, op {d.strftime('%d-%m-%Y')}"
        titel = f"Wagenpark: {wat} {v['plaat']} ({v['merk_model']}, {v.get('gebruik')}) {staat}"
        uit.append({"voor": "mehdi", "soort": "signaal", "sleutel": v["plaat"],
                    "titel": re.sub("stil", "st.l", titel, flags=re.I),
                    "uniek": f"wagenpark:{v['plaat']}:{wat}:{d.isoformat()}:{trede}",
                    "inhoud": {"plaat": v["plaat"], "wat": wat, "datum": d.isoformat(), "mappen": v.get("mappen"),
                               "voorstel": (f"Vraag nu offertes bij minstens twee andere verzekeraars (het eerste jaar geeft een nieuwe verzekeraar "
                                            f"20 tot 25% korting). Opzeggen aangetekend of via de nieuwe verzekeraar, uiterlijk {d.strftime('%d-%m-%Y')}."
                                            if wat.startswith("opzeggen verzekering") else
                                            f"{wat} regelen voor {v['plaat']}; het bewijs in de map {v['mappen'][-1] if v.get('mappen') else ''}")}})
    return uit


def main():
    droog, forceer = "--droog" in sys.argv, "--nu" in sys.argv
    nu = datetime.now(BRUSSEL)
    vandaag = nu.date()
    try:
        staat = json.load(open(STAAT))
    except (OSError, ValueError):
        staat = {}
    if not (droog or forceer) and (nu.hour < 7 or staat.get("laatste_dag") == vandaag.isoformat()):
        return
    register = lees_register() if not droog else (json.load(open(REGISTER)) if os.path.exists(REGISTER) else json.load(open(ZAAD)))
    try:
        tijdlijn = json.load(open(TIJDLIJN, encoding="utf-8"))
    except (OSError, ValueError):
        tijdlijn = {}
    dagen = DAGELIJKS_DAGEN if tijdlijn else EERSTE_KEER_DAGEN
    vz = verzekeringen()
    lijst, onbekend = termijnen(register, vandaag, vz)
    if droog:
        class _L:
            def log(self, *a):
                print("  [log]", *a[:3])
        n, weg = post_koppelen(register, tijdlijn, dagen, _L())
        print(overzicht(register, tijdlijn, lijst, onbekend, vandaag)[:6000])
        print(f"\nnieuwe post: {n}; niet leesbaar: {weg}")
        for s in signalen(lijst, vandaag):
            print("signaal:", s["titel"])
        return
    ag = bord.Agent(NAAM)
    with ag.ronde("wagenpark in het oog") as r:
        r.bron("voertuigen.json", json.dumps(register, ensure_ascii=False, sort_keys=True))
        n, weg = post_koppelen(register, tijdlijn, dagen, ag)
        json.dump(tijdlijn, open(TIJDLIJN, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
        tekst = overzicht(register, tijdlijn, lijst, onbekend, vandaag)
        os.makedirs(EXPORT, exist_ok=True)
        with open(os.path.join(EXPORT, "Wagenpark overzicht.md"), "w", encoding="utf-8") as f:
            f.write(tekst + "\n")
        json.dump(register, open(os.path.join(EXPORT, "voertuigen.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        r.bron("vermogen.verzekering (autoverzekeringen)", json.dumps(vz, ensure_ascii=False, sort_keys=True, default=str))
        r.bron("wagenpark-onderdelen.json", open(ONDERDELEN, encoding="utf-8").read())
        json.dump(dashboard(register, tijdlijn, lijst, onbekend, vandaag, vz),
                  open(os.path.join(EXPORT, "dashboard.json"), "w", encoding="utf-8"), ensure_ascii=False)
        # Mehdi, 25-09-2026: wagens die er niet meer zijn tellen niet mee (verkocht, geschrapt, buiten gebruik).
        hier = {v["plaat"] for v in register["voertuigen"] if v.get("status") not in WEG}
        te_klasseren = [e for e in tijdlijn.values() if not e.get("geklasseerd") and e.get("plaat") in hier]
        json.dump(sorted(te_klasseren, key=lambda e: e["datum"]), open(os.path.join(EXPORT, "te klasseren.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        sig = signalen(lijst, vandaag, register)
        if sig:
            ag.klaarzet(sig)
        ag.log(f"dag {vandaag.isoformat()}", "overzicht", f"{len(lijst)} termijnen, {n} nieuwe post, {len(te_klasseren)} te klasseren", tekst)
        if "wagenparkha@gmail.com" not in POSTVAKKEN:
            r.nood("wagenparkha@gmail.com is niet gekoppeld: daar sturen de bestuurders garagefacturen heen. Nodig: een "
                   "app-wachtwoord van dat Google-account in ~/post-config/mailboxen.yaml (imap.gmail.com)", wie="mehdi")
        if weg:
            r.nood("Postvakken voor het wagenpark niet leesbaar via de postbus: " + ", ".join(weg), wie="claude-code")
        r.nood("Pincodes van tankkaarten staan in klare tekst in 'overzicht wagenpark (keuring en verzekering).xlsx' "
               "(Work All/o16. Wagenpark/Wagens) en in bestandsnamen onder Work All/o07. UNIVERSAL/00. CARS/*/Tank Card. "
               "Voorstel: die kolom en die namen opschonen en de codes in de Keychain of een kluis", wie="mehdi")
        r.nood("Twee mapstructuren voor de wagens (o16. Wagenpark en Harmoniebouw 60. INVENTARIS/Werkvoertuigen). "
               "Voorstel: de Harmoniebouw-structuur met submappen 00 tot 07 als standaard voor elke firma", wie="mehdi")
        r.nood("Documenten in de map van de wagen zetten kan alleen vanaf de Mac; de klasseerhulp die 'te klasseren.json' "
               "afwerkt is nog te bouwen", wie="claude-code")
        if any(v.get("open_vragen") for v in register["voertuigen"]):
            r.nood("Open vragen over de wagens staan in Data uit Mehdi/Wagenparkwacht/Wagenpark overzicht.md", wie="mehdi")
        verlopen = [f"{wat} {v['plaat']}" for v, wat, d, dd in lijst if dd < 0]
        r.detail = (f"{sum(1 for v in register['voertuigen'] if v.get('status') == 'in gebruik')} wagens in gebruik; "
                    f"termijnen: {len(lijst)}, verlopen: {', '.join(verlopen) or 'geen'}; nieuwe post: {n}; te klasseren: {len(te_klasseren)}")
        staat["laatste_dag"] = vandaag.isoformat()
        os.makedirs(DATA, exist_ok=True)
        json.dump(staat, open(STAAT, "w"), ensure_ascii=False)


if __name__ == "__main__":
    main()
