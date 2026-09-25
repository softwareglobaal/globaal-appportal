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


def termijnen(register, vandaag, vz=None, blik=None):
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
            naam = re.split(r" \(|,", p.get("verzekeraar") or "verzekeraar")[0].strip()
            uit.append((v, f"vervaldag verzekering {naam}", einde, (einde - vandaag).days))
            # Wet 9-10-2023 (sinds 1-10-2024): minstens 2 maanden voor de vervaldag. Een dag vroeger, zodat je nooit te laat bent.
            opzeg = _min_maanden(einde, p.get("opzegtermijn_maanden") or 2) - timedelta(days=1)
            uit.append((v, f"opzeggen verzekering {naam}", opzeg, (opzeg - vandaag).days))
        belgie = (v.get("land") or "België") == "België"
        for pad, wat in TERMIJNEN:
            if pad == "verzekering.tot" and pol:
                continue
            if not belgie and pad in ("keuring_tot", "groene_kaart_tot", "verkeersbelasting_vervaldag"):
                continue  # Belgische keuring en verkeersbelasting gelden niet in Suriname
            d = _veld(v, pad)
            if pad == "onderhoud_volgend":
                # Altijd uit de laatste onderhoudsfactuur en het fabrieksinterval, nooit een vaste datum in het register:
                # op 25-09-2026 bleef 'onderhoud 2HHE117 verlopen' staan terwijl Auto 5 hem op 12-08-2026 onderhield.
                ob = next((b for b in (blik or {}).get(v["plaat"], {}).get("vooruitblik", []) if b["onderdeel"].startswith("onderhoudsbeurt")), None)
                d = ob["verwacht"] if ob else d
            if not d:
                if belgie and pad in ("keuring_tot", "verzekering.tot") and v.get("status") == "in gebruik":
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
    try:
        kost = kosten(register, vz, vandaag)
    except Exception as e:  # noqa: BLE001
        kost = {}
        print("kosten mislukt:", type(e).__name__, e, file=sys.stderr)
    for v in register["voertuigen"]:
        post = sorted(per.get(v["plaat"], []), key=lambda e: e["datum"], reverse=True)
        onderhoud = [dict(o, herkomst="register") for o in v.get("onderhoud") or []]
        onderhoud += [{"datum": e["datum"], "soort": e["soort"], "garage": e["van"], "km": None, "bedrag": None,
                       "omschrijving": e["onderwerp"], "bron": f"mail {e['postvak']}", "herkomst": "post"}
                      for e in post if e["soort"] in ("garage", "keuring", "schade")]
        onderhoud.sort(key=lambda o: o.get("datum") or "", reverse=True)
        km = sorted(v.get("km") or [], key=lambda k: k.get("datum") or "")
        extra = blik.get(v["plaat"], {})
        wagens.append(dict(v, polissen=polissen_van(v, vz), kosten=kost.get(v["plaat"], {}), bouwjaar_vin=bouwjaar_uit_vin(v.get("chassis"), vandaag), vooruitblik=extra.get("vooruitblik", []), vaak=extra.get("vaak", {}),
                           km_per_dag=extra.get("km_per_dag"), termijnen=sorted(termijn_per.get(v["plaat"], []), key=lambda t: (t["dagen"] is None, t["dagen"] or 0)),
                           onderhoud=onderhoud, post=post[:60], laatste_km=km[-1] if km else None,
                           te_klasseren=sum(1 for e in post if not e.get("geklasseerd"))))
    # Wat op meer dan een wagen terugkomt (bv. de aandrijfas op beide Transits): over het hele wagenpark.
    vloot = {}
    for plaat, b in blik.items():
        for o, n in (b.get("herstellingen") or {}).items():
            vloot.setdefault(o, {})[plaat] = n
    vloot = {o: p for o, p in vloot.items() if len(p) >= 2 or sum(p.values()) >= 2}
    return {"gemaakt": datetime.now(BRUSSEL).isoformat(timespec="minutes"), "vandaag": vandaag.isoformat(), "vaak_wagenpark": vloot,
            "wagens": wagens, "niet_toegewezen": sorted(per.get("", []), key=lambda e: e["datum"], reverse=True)[:40],
            "mappen_standaard": register.get("submappen_standaard", [])}


def _bedrag(s):
    # Eerst een getal met duizendtallen (1.379,60 of 2.000), dan een gewoon getal (3036,49): anders werd 3036,49 gelezen als 303.
    m = re.search(r"(\d{1,3}(?:[.\s]\d{3})+(?:,\d{1,2})?|\d+(?:[.,]\d{1,2})?)", str(s or ""))
    if not m:
        return None
    x = m.group(1).replace(" ", "")
    if "," in x:
        x = x.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(\.\d{3})+", x):
        x = x.replace(".", "")  # '2.000 SRD' is tweeduizend, geen twee (gezien 25-09-2026)
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
        blik, vaak, herst = [], {}, {}
        for r in regels["onderdelen"]:
            gedaan = []
            for o in v.get("onderhoud") or []:
                if any(any(w in tekst.lower() for w in r["woorden"]) for tekst, _ in _werken(o)):
                    gedaan.append(o)
            if r.get("alleen_bij_klacht"):
                if gedaan:
                    herst[r["onderdeel"]] = len(gedaan)
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
        uit[v["plaat"]] = {"vooruitblik": sorted(blik, key=lambda b: b["dagen"]), "vaak": vaak, "herstellingen": herst,
                           "km_per_dag": round(per_dag) if per_dag else None}
    return uit


JAARCODE = "ABCDEFGHJKLMNPRSTVWXY123456789"  # ISO 3779, zonder I, O, Q, U, Z en 0; A = 2010


def bouwjaar_uit_vin(vin, vandaag=None):
    """Bouwjaar uit het chassisnummer, alleen waar de fabrikant het vast codeert: Ford Europa (WF0) op positie 11,
    Opel (W0V, W0L) op positie 10. Anders None: nooit gokken."""
    v = re.sub(r"[^A-Z0-9]", "", (vin or "").upper())
    if len(v) != 17:
        return None
    pos = 10 if v.startswith("WF0") else (9 if v[:3] in ("W0V", "W0L") else None)
    if pos is None or v[pos] not in JAARCODE:
        return None
    jaar = 2010 + JAARCODE.index(v[pos])
    return jaar if jaar <= (vandaag or date.today()).year + 1 else jaar - 30


def _incl(s):
    """Het bedrag incl. btw uit een tekst als '414,57 excl. btw = 501,63 incl. btw'; anders het eerste bedrag."""
    m = re.search(r"([\d.\s]+,\d{2}|\d+(?:\.\d{2})?)\s*(?:eur\s*)?incl", str(s or ""), re.I)
    return _bedrag(m.group(1)) if m else _bedrag(s)


def _km_op(punten, d):
    """Kilometerstand op dag d door lineair te interpoleren tussen twee gekende standen; None als d er niet tussen ligt."""
    voor = [p for p in punten if p[0] <= d]
    na = [p for p in punten if p[0] >= d]
    if not voor or not na:
        return None
    a, b = voor[-1], na[0]
    if a[0] == b[0]:
        return a[1]
    return a[1] + (b[1] - a[1]) * (d - a[0]).days / (b[0] - a[0]).days


CATEGORIE = {"onderhoud": "onderhoud en herstel", "herstelling": "onderhoud en herstel", "garage": "onderhoud en herstel",
             "banden": "banden", "keuring": "keuring", "schade": "schade", "verzekering": "verzekering", "brandstof": "brandstof"}


EIGEN_FIRMA = re.compile(r"h-?\s?invest|h-?\s?aannemingen|harmonie\s?bouw|h-?\s?architects|melodie|high design|hds\b|tkn|unabo|"
                         r"energie effici|zidi|elevait", re.I)
BOEK_CATEGORIE = {"onderhoud": "onderhoud en herstel", "herstelling": "onderhoud en herstel", "banden": "banden", "keuring": "keuring",
                  "schade": "schade", "verzekering": "verzekering", "belasting": "belasting", "leasing": "financiering",
                  "brandstof": "brandstof", "aankoop": "aankoop", "andere": "andere"}


def kosten(register, vz, vandaag):
    """Kosten per wagen per kalenderjaar en per categorie, met km en kost per km. Munt apart: SRD wordt nooit bij EUR opgeteld.
    Bronnen: onderhoudsregels met een bedrag, de financiering (maandbedrag maal de maanden in het jaar), de jaarpremie uit
    vermogen.verzekering, en brandstof per maand zodra de tankkaarten gelezen zijn (veld brandstof_maanden)."""
    uit = {}
    for v in register["voertuigen"]:
        if v.get("status") in WEG:
            continue
        jaren, uit_boekhouding = {}, set()

        def boek(jaar, cat, bedrag, munt="EUR", bron="aanvulling"):
            if not bedrag:
                return
            # De boekhouding gaat voor: een aanvulling uit contract of factuur telt alleen als de boekhouding voor die
            # wagen, dat jaar en die categorie niets heeft. Zo telt niets dubbel.
            if bron == "aanvulling" and munt == "EUR" and (str(jaar), cat) in uit_boekhouding:
                return
            j = jaren.setdefault(str(jaar), {"munt": {}})
            j["munt"].setdefault(munt, {}).setdefault(cat, 0.0)
            j["munt"][munt][cat] += bedrag
        gezien = set()
        for b in v.get("boekingen") or []:
            if not b.get("datum"):
                continue
            # Interne huur telt niet voor de groep: H-Invest least bij KBC en verhuurt aan Harmoniebouw, en beide boeken
            # huur (gezien 26-09-2026: 2ACH377 kwam op 13.112 EUR in 2024). Dezelfde factuur twee keer telt een keer.
            if EIGEN_FIRMA.search(b.get("leverancier") or ""):
                continue
            sleutel = (b.get("datum"), (b.get("leverancier") or "").lower(), b.get("factuurnummer"), b.get("excl") or b.get("incl"))
            if b.get("factuurnummer") and sleutel in gezien:
                continue
            gezien.add(sleutel)
            cat = BOEK_CATEGORIE.get(b.get("soort") or "andere", "andere")
            if cat == "andere" and "boete" in (b.get("omschrijving") or "").lower():
                cat = "boetes"
            bedrag = _bedrag(b.get("excl")) if b.get("excl") not in (None, "") else _bedrag(b.get("incl"))
            if bedrag and str(b.get("excl") or b.get("incl") or "").strip().startswith("-"):
                bedrag = -bedrag  # creditnota
            if bedrag:
                uit_boekhouding.add((b["datum"][:4], cat))
                boek(b["datum"][:4], cat, bedrag, bron="boekhouding")
        for o in v.get("onderhoud") or []:
            tekst = f"{o.get('bedrag') or ''} {o.get('omschrijving') or ''}".lower()
            if not o.get("datum") or not o.get("bedrag") or o.get("soort") == "offerte" or "offerte" in tekst:
                continue  # een offerte is geen uitgave
            munt = "SRD" if "srd" in str(o["bedrag"]).lower() else ("USD" if "usd" in str(o["bedrag"]).lower() else "EUR")
            boek(o["datum"][:4], CATEGORIE.get(o.get("soort"), "andere"), _incl(o["bedrag"]), munt)
        l = v.get("leasing") or {}
        mb = _incl(l.get("maandbedrag")) if l.get("maandbedrag") else None
        start = re.search(r"\d{4}-\d{2}-\d{2}", str(l.get("start") or ""))
        einde = re.findall(r"\d{4}-\d{2}-\d{2}", str(l.get("einde") or l.get("einde_tekst") or ""))
        if mb and start:
            s = date.fromisoformat(start.group(0))
            e = min(date.fromisoformat(min(einde)) if einde else vandaag, vandaag)  # de laatste betaalde huur, niet het contracteinde
            d = date(s.year, s.month, 1)
            while d <= e:
                boek(d.year, "financiering", mb)
                d = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        for p in polissen_van(v, vz):
            if p.get("jaarpremie") and p.get("einddatum"):
                boek(int(str(p["einddatum"])[:4]) - 1, "verzekering", float(p["jaarpremie"]))
        for m in v.get("brandstof_maanden") or []:
            boek(m["maand"][:4], "brandstof", _bedrag(m.get("bedrag_excl") or m.get("bedrag_incl")))
        punten = sorted({(date.fromisoformat(k["datum"][:10]), k["km"]) for k in v.get("km") or [] if k.get("datum") and k.get("km")})
        for jaar, j in jaren.items():
            y = int(jaar)
            a, b = _km_op(punten, date(y, 1, 1)), _km_op(punten, min(date(y, 12, 31), vandaag))
            binnen = [p[1] for p in punten if p[0].year == y]
            if a is not None and b is not None:
                j["km"], j["km_zeker"] = round(b - a), True
            elif len(binnen) >= 2:
                j["km"], j["km_zeker"] = max(binnen) - min(binnen), False
            eur = {c: x for c, x in j["munt"].get("EUR", {}).items() if c != "aankoop"}  # een aankoop is een investering, geen jaarkost
            j["totaal_eur"] = round(sum(eur.values()))
            if j.get("km") and j["km"] > 500 and eur:
                j["per_km"] = round(sum(eur.values()) / j["km"], 3)
            j["munt"] = {m: {c: round(x) for c, x in cats.items()} for m, cats in j["munt"].items()}
        uit[v["plaat"]] = dict(sorted(jaren.items()))
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
    try:
        blik_nu = vooruitblik(register, vandaag)
    except Exception:  # noqa: BLE001
        blik_nu = {}
    lijst, onbekend = termijnen(register, vandaag, vz, blik_nu)
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
