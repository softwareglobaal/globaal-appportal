"""Per wacht wat er op een dag binnenkwam (Mehdi, 01-11-2026: "ik wil alle wachten zien, zodat ik weet per wacht wat
binnengekomen is en dat ik het kan controleren ... ik wil het als mens zien en begrijpen dat het werkt").

Alleen lezen uit de databank van het bord. Per wacht uit de groep Dagbundelaar: hoeveel items, de items zelf (tijd, van
wie of wat, kort), de rondes van die dag uit het werkverslag, en of er een fout was. Een wacht die die dag niets meldde,
staat als "niets binnen", nooit als nul. Nooit de tekst van een bericht: de wachten bewaren die ook niet.
"""
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
# Mehdi leest de wacht per dag in het Dagboek: niets wegkappen wat hij daar wil zien (Codex 01-11). Een dag heeft hoogstens
# enkele honderden rondes (de Fotowacht 435 op 30-10).
MAX_ITEMS = 2000
MAX_LOG = 1000                          # regels per blad van het werkverslag (T-0120 AG-9: 23-10 had er 4.445)
KORT = 160
# Welke wacht schrijft welke bron in de gesprekkentabel (gesprek_log.bron).
GESPREK_BRON = {"whatsapp-wacht": "whatsapp", "belwacht": "telefoon", "sms-wacht": "sms", "xelion-wacht": "xelion",
                "fathom-wacht": "fathom", "plaud-wacht": "plaud", "zoom-wacht": "zoom"}
MAIL_WACHTEN = ("mail-prive", "mail-mch", "mail-info-harc", "mail-hinv", "mail-melo")
# T-0120 AG-2: van een signaal of dagplan van deze wachten ook de regels van de inhoud, niet alleen de titel (welke
# afspraak, welke boeking). Hun inhoud is bij het klaarzetten gemaskeerd zoals op het bord (bord.Agent.maskeer geeft
# '(privé)'); ik toon ze zoals ze daar staan. Andere wachten niet: nooit de tekst van een bericht.
REGELS_VAN = ("agenda-wacht", "calendly-wacht")
MAX_REGELS = 200


def grenzen(dag):
    """De Brusselse dag als UTC-tekst [van, tot), zoals de ts in de databank staat (isoformat in UTC)."""
    d = date.fromisoformat(dag)
    van = datetime.combine(d, time(0), BRUSSEL).astimezone(timezone.utc)
    tot = datetime.combine(d + timedelta(days=1), time(0), BRUSSEL).astimezone(timezone.utc)
    return van.isoformat(), tot.isoformat()


def uur(waarde):
    """Een tijdstip uit de databank als HH:MM in Brussel; een losse HH:MM blijft staan; onleesbaar is leeg."""
    t = str(waarde or "").strip()
    if not t:
        return ""
    if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", t):
        return t[:5].rjust(5, "0")
    try:
        x = datetime.fromisoformat(t.replace("Z", "+00:00"))
    except ValueError:
        try:
            x = parsedate_to_datetime(t)
        except (TypeError, ValueError, IndexError):
            return ""
    if x.tzinfo is None:
        return x.strftime("%H:%M")
    return x.astimezone(BRUSSEL).strftime("%H:%M")


def kort(tekst, n=KORT):
    t = re.sub(r"\s+", " ", str(tekst or "")).strip()
    return t if len(t) <= n else t[: n - 1].rstrip() + "…"


def _json(tekst):
    try:
        x = json.loads(tekst or "")
    except (TypeError, ValueError):
        return None
    return x


def _telling_tekst(t):
    """Een telling (dict) als korte regel: 'dictaten 12, woorden 840'. Lijsten en dieper blijven weg."""
    if not isinstance(t, dict):
        return kort(t)
    delen = [f"{k.replace('_', ' ')} {v}" for k, v in t.items() if isinstance(v, (int, float, str)) and str(v) != ""]
    return kort(", ".join(delen))


def _item(tijd, wie, wat, fout=False):
    return {"tijd": tijd, "wie": kort(wie, 80), "wat": kort(wat), "fout": bool(fout)}


def is_prive_gesprek(r):
    """De privéregel van De Regisseur (RZ3-01, zoals De Dagbundelaar en De Communicatiebundelaar): afdeling prive of privé.
    De vlag prive=1 alleen betekent "van de Mac van Mehdi, alleen voor Mehdi" (WhatsApp, sms, telefoon: elke rij); die
    rijen dragen naam en aantal, nooit tekst, en deze pagina is alleen voor Mehdi: die blijven leesbaar."""
    return str(r["afdeling"] or "").strip().casefold() in ("prive", "privé")


def lees_gesprekken(conn, bron, dag):
    rijen = conn.execute("SELECT uniek, start, minuten, personen, thema, bron, COALESCE(dubbel_van,'') AS dubbel_van, "
                         "COALESCE(afdeling,'') AS afdeling FROM gesprek_log WHERE datum=? AND bron IN (?, 'dekking') "
                         "ORDER BY start", (dag, bron)).fetchall()
    items, gedekt = [], False
    for r in rijen:
        if r["bron"] == "dekking":
            if str(r["uniek"] or "").startswith(f"dekking:{bron}:"):
                gedekt = True
            continue
        if is_prive_gesprek(r):
            # RZ2-01: van een privégesprek alleen "privégesprek, N min", zonder naam of onderwerp.
            wat = ", ".join(x for x in (f"{r['minuten']} min" if r["minuten"] else "",
                                        "dubbel, telt niet" if r["dubbel_van"] else "") if x)
            items.append(_item(uur(r["start"]), "privégesprek", wat))
            continue
        wat = ", ".join(x for x in (f"{r['minuten']} min" if r["minuten"] else "", kort(r["thema"], 100),
                                    "dubbel, telt niet" if r["dubbel_van"] else "") if x)
        items.append(_item(uur(r["start"]), r["personen"] or "onbekend", wat))
    return items, gedekt


def lees_mail(conn, wacht, dag):
    rijen = conn.execute("SELECT datum, van, van_naam, onderwerp, soort, map FROM mailbericht WHERE wacht=? AND dag=? "
                         "ORDER BY datum LIMIT ?", (wacht, dag, MAX_ITEMS)).fetchall()
    return [_item(uur(r["datum"]), r["van_naam"] or r["van"] or "onbekend",
                  " · ".join(x for x in (r["onderwerp"] or "(geen onderwerp)", r["soort"] or "") if x)) for r in rijen]


def lees_klaarzet(conn, wacht, dag, van, tot):
    """Wat de wacht die dag klaarzette, of wat over die dag gaat (sleutel, uniek of titel met de dag)."""
    rijen = conn.execute(
        "SELECT ts, soort, titel, inhoud, uniek, sleutel FROM klaarzet WHERE van=? AND status!='vervallen' AND "
        "((ts>=? AND ts<?) OR sleutel=? OR uniek LIKE ? OR uniek LIKE ? OR titel LIKE ?) ORDER BY ts LIMIT ?",
        (wacht, van, tot, dag, f"%:{dag}", f"%:{dag}:%", f"{dag} %", MAX_ITEMS)).fetchall()
    items = []
    for r in rijen:
        inhoud = _json(r["inhoud"])
        wat = r["titel"] or ""
        if isinstance(inhoud, dict):
            pd = inhoud.get("per_dag")
            t = pd.get(dag) if isinstance(pd, dict) else inhoud.get("vandaag")
            if isinstance(t, dict) and t:
                wat = f"{wat}: {_telling_tekst(t)}"
        titel = str(r["titel"] or "")
        tijd = uur(r["ts"])
        if titel.startswith(dag + " "):
            # "2026-10-31 20:25-20:56: 22 foto's bij ...": de eerste tijd is de tijd, de rest is wat; een bereik komt erachter.
            wat = titel[len(dag) + 1:]
            m = re.match(r"([01]\d:[0-5]\d|2[0-3]:[0-5]\d)(?:-([01]\d:[0-5]\d|2[0-3]:[0-5]\d))?(?::\s*|\s+|$)", wat)
            if m:
                tijd, wat = m.group(1), wat[m.end():].strip()
                if m.group(2) and m.group(2) != m.group(1):
                    wat = f"{wat} ({m.group(1)} tot {m.group(2)})"
        it = _item(tijd, r["soort"] or "item", wat)
        if wacht in REGELS_VAN and r["soort"] in ("signaal", "dagplan") and inhoud is None and r["inhoud"]:
            it["regels"] = inhoud_regels(r["inhoud"])
        items.append(it)
    return items


def inhoud_regels(inhoud):
    """De regels van een tekstinhoud als lijst, zonder het streepje vooraan; lege regels vallen weg. Boven MAX_REGELS een
    slotregel met het aantal."""
    uit = [kort(re.sub(r"^\s*-\s+", "", x), 220) for x in str(inhoud or "").splitlines() if x.strip()]
    return uit[:MAX_REGELS] + ([f"en nog {len(uit) - MAX_REGELS} regel(s)"] if len(uit) > MAX_REGELS else [])


def lees_log(conn, wacht, van, tot):
    rijen = conn.execute("SELECT ts, stap, onderwerp, tekst FROM logboek WHERE naam=? AND ts>=? AND ts<? ORDER BY id",
                         (wacht, van, tot)).fetchall()
    return [{"tijd": uur(r["ts"]), "stap": r["stap"], "tekst": kort(f"{r['onderwerp']}: {r['tekst']}" if r["onderwerp"]
                                                                       else r["tekst"], 220),
             "fout": r["stap"] == "fout"} for r in rijen]


def alleen_werkdagen(cadans):
    """Of de cadans uit de tabel agent zegt dat de wacht alleen op werkdagen draait ('Elke werkdag 07:15'). Vrije tekst,
    dus streng: 'werkdag' en geen woord dat op het weekend of op rondes door de dag wijst; De Agendawacht draait op
    werkdagen, maar haar signaalwacht elke dag elke twaalf minuten (T-0120 CL-4)."""
    c = str(cadans or "").casefold()
    return "werkdag" in c and not re.search(r"weekend|zaterdag|zondag|elke dag|dagelijks|minuut|minuten|kwartier|\buur\b", c)


def per_wacht(conn, wacht, label, dag, status=None, noden=(), blad=None, cadans=""):
    """blad: welk blad van het werkverslag (1 is het begin); zonder blad het laatste, zoals voordien de laatste MAX_LOG
    regels. Een blad buiten het bereik wordt het dichtstbijzijnde (T-0120 AG-9)."""
    van, tot = grenzen(dag)
    items, gedekt, leesfout, logfout = [], None, "", ""
    # Items en werkverslag apart gelezen en apart gemeld (Codex 01-11): faalt het een, dan blijft het ander staan.
    try:
        if wacht in GESPREK_BRON:
            items, gedekt = lees_gesprekken(conn, GESPREK_BRON[wacht], dag)
        elif wacht in MAIL_WACHTEN:
            items = lees_mail(conn, wacht, dag)
        items += lees_klaarzet(conn, wacht, dag, van, tot)
    except Exception as e:  # noqa: BLE001  een kapotte tabel mag de rest van de pagina niet tegenhouden
        leesfout = f"niet gelezen ({type(e).__name__})"
    try:
        log = lees_log(conn, wacht, van, tot)
    except Exception as e:  # noqa: BLE001
        log, logfout = [], f"werkverslag niet gelezen ({type(e).__name__})"
    items.sort(key=lambda x: x["tijd"] or "99")
    fouten = [x for x in log if x["fout"]]
    st = dict(status) if status else None
    # De hartslag is alleen de stand van nu: hij telt alleen mee voor vandaag.
    status_fout = bool(st and dag == datetime.now(BRUSSEL).date().isoformat()
                       and str(st.get("status")) in ("fout", "error"))
    if leesfout or logfout or fouten or status_fout:
        oordeel, kleur = "fout", "rood"
    elif items:
        oordeel, kleur = "binnen", "groen"
    elif log:
        oordeel, kleur = "draaide, niets binnen", "oranje"
    elif alleen_werkdagen(cadans) and date.fromisoformat(dag).weekday() >= 5:
        # T-0120 CL-4: in het weekend heeft een werkdagwacht geen ronde gepland; dat is het schema, geen grijs gat
        oordeel, kleur = "geen ronde gepland", "groen"
    else:
        oordeel, kleur = "niets binnen, geen ronde", "grijs"
    bladen = max(1, -(-len(log) // MAX_LOG))
    blad = bladen if blad is None else min(max(1, int(blad)), bladen)
    return {"naam": wacht, "label": label, "oordeel": oordeel, "kleur": kleur, "aantal": len(items),
            "items": items[:MAX_ITEMS], "rondes": len(log), "fouten": fouten,
            "log": log[(blad - 1) * MAX_LOG:blad * MAX_LOG], "log_blad": blad, "log_bladen": bladen,
            "gedekt": gedekt, "leesfout": leesfout, "logfout": logfout, "noden": list(noden),
            "status": None if not st else {"status": st.get("status"), "detail": kort(st.get("detail"), 200),
                                            "laatste": uur(st.get("ts")), "laatste_ts": st.get("ts")}}


def dag(conn, dag_, agents, vakken, boven, wacht=None, blad=None):
    """Alle wachten van de groep Dagbundelaar voor één dag, in hun vakken. agents: naam -> label. wacht en blad: dat blad
    van het werkverslag voor die ene wacht (T-0120 AG-9); de andere wachten krijgen hun laatste blad."""
    date.fromisoformat(dag_)
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    nood = {}
    for r in conn.execute("SELECT naam, tekst FROM nood WHERE open=1 ORDER BY id").fetchall():
        nood.setdefault(r["naam"], []).append(kort(r["tekst"], 200))
    try:                                        # CL-4: de cadans uit de tabel agent; zonder tabel blijft grijs grijs
        cadans = {r["naam"]: r["cadans"] or "" for r in conn.execute("SELECT naam, cadans FROM agent").fetchall()}
    except Exception:  # noqa: BLE001
        cadans = {}
    groepen = [("De Dagbundelaar en Ai Angel", tuple(boven))] + [(v, tuple(w)) for v, w in vakken]
    uit = []
    for vak, namen in groepen:
        uit.append({"vak": vak, "wachten": [per_wacht(conn, n, agents.get(n, n), dag_, st.get(n), nood.get(n, ()),
                                                      blad=blad if n == wacht else None, cadans=cadans.get(n, ""))
                                            for n in namen]})
    alle = [w for v in uit for w in v["wachten"]]
    return {"dag": dag_, "vakken": uit,
            "telling": {k: sum(1 for w in alle if w["kleur"] == k) for k in ("groen", "oranje", "rood", "grijs")},
            "items": sum(w["aantal"] for w in alle)}
