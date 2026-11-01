"""Per wacht wat er op een dag binnenkwam (Mehdi, 01-11-2026: "ik wil alle wachten zien, zodat ik weet per wacht wat
binnengekomen is en dat ik het kan controleren ... ik wil het als mens zien en begrijpen dat het werkt").

Alleen lezen uit de databank van het bord. Per wacht uit de groep Dagbundelaar: hoeveel items, de items zelf (tijd, van
wie of wat, kort), de rondes van die dag uit het werkverslag, en of er een fout was. Een wacht die die dag niets meldde,
staat als "niets binnen", nooit als nul. Nooit de tekst van een bericht: de wachten bewaren die ook niet.
"""
import json
import os
import re
from datetime import date, datetime, time, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
# Mehdi leest de wacht per dag in het Dagboek: niets wegkappen wat hij daar wil zien (Codex 01-11). Een dag heeft hoogstens
# enkele honderden rondes (de Fotowacht 435 op 30-10).
MAX_ITEMS = 2000
MAX_LOG = 1000
KORT = 160
# Welke wacht schrijft welke bron in de gesprekkentabel (gesprek_log.bron).
GESPREK_BRON = {"whatsapp-wacht": "whatsapp", "belwacht": "telefoon", "sms-wacht": "sms", "xelion-wacht": "xelion",
                "fathom-wacht": "fathom", "plaud-wacht": "plaud", "zoom-wacht": "zoom"}
MAIL_WACHTEN = ("mail-prive", "mail-mch", "mail-info-harc", "mail-hinv", "mail-melo")


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
        items.append(_item(tijd, r["soort"] or "item", wat))
    return items


def lees_log(conn, wacht, van, tot):
    rijen = conn.execute("SELECT ts, stap, onderwerp, tekst FROM logboek WHERE naam=? AND ts>=? AND ts<? ORDER BY id",
                         (wacht, van, tot)).fetchall()
    return [{"tijd": uur(r["ts"]), "stap": r["stap"], "tekst": kort(f"{r['onderwerp']}: {r['tekst']}" if r["onderwerp"]
                                                                       else r["tekst"], 220),
             "fout": r["stap"] == "fout"} for r in rijen]


# De slotregel van een ronde in het werkverslag (De Plaudwacht: ag.log("Plaud", "bron", "ronde: ...")); PLAUD-8.
RONDE_REGEL = "ronde:"


# PLAUD-7 (T-0120): De Plaudwacht zet alleen een opname met transcript in de gesprekkentabel; de opnames zonder transcript
# waren hier onzichtbaar (oktober: 6), en of de audio er was, stond nergens (oktober: 5 zonder). Het bord heeft
# mijnagents-data op /data; daar zet de Mac het manifest (plaud/plaud_invoer_push.sh). Alleen tijd, duur en toestand,
# nooit de naam in Plaud of een pad. Een eigen naam voor de variabele: PLAUD_INVOER van de runner is een pad op de VM.
PLAUD_INVOER = os.environ.get("WACHTEN_PLAUD_INVOER", "/data/plaud-invoer")
PLAUD_KORT_MINUTEN = 1                          # zoals KORT_MINUTEN in plaud/manifest.py (PLAUD-9)


def _duur(minuten):
    try:
        m = float(minuten)
    except (TypeError, ValueError):
        return "duur onbekend"
    return f"{round(m * 60)} s" if m < 1 else f"{int(m)} min"


def _kort_wachtend(o):
    try:
        return o.get("toestand") == "wacht_op_transcript" and float(o.get("duur_minuten")) < PLAUD_KORT_MINUTEN
    except (TypeError, ValueError):
        return False


def lees_plaud(conn, dag):
    """(items, stand) van De Plaudwacht uit het manifest van de Mac. items: de opnames van die dag zonder rij in de
    gesprekkentabel; een opname met een rij staat er al, met de privéregel (is_prive_gesprek). stand: de telling van die
    dag, of None als het manifest niet te lezen is (onbekend, nooit 0).

    Contract voor een link (VOL-19: één route achter Authentik, de weergave doet de groep pagina): het Dagboek vraagt het
    bord om het transcript van plaud:<id>, en het bord leest /data/plaud-invoer/<archief.map>/transcript.json. Nooit bij
    een privégesprek, nooit een Dropboxpad of gedeelde link. De audio staat alleen op de Mac: geen audiolink, wel de
    telling zonder_audio."""
    try:
        with open(os.path.join(PLAUD_INVOER, "00 manifest.json"), encoding="utf-8") as f:
            m = json.load(f)
        opnames = [o for o in m["opnames"] if isinstance(o, dict) and str(o.get("start_brussel") or "")[:10] == dag]
        gemaakt = str((m.get("meta") or {}).get("gemaakt") or "")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return [], None
    # Codex-toets 1: een manifest van voor die dag kent die dag niet; dat is onbekend, geen nul. Van tijdens de dag
    # (vandaag) is de telling nog niet af: na_de_dag zegt het.
    van, tot = (datetime.fromisoformat(x) for x in grenzen(dag))
    try:
        gemaakt_t = datetime.fromisoformat(gemaakt.replace("Z", "+00:00"))
        gemaakt_t = gemaakt_t if gemaakt_t.tzinfo else gemaakt_t.replace(tzinfo=timezone.utc)
    except ValueError:
        return [], None
    if gemaakt_t < van:
        return [], None
    unieken = [f"plaud:{o.get('plaud_id')}" for o in opnames]
    in_tabel = {r["uniek"] for r in conn.execute(
        f"SELECT uniek FROM gesprek_log WHERE bron='plaud' AND uniek IN ({','.join('?' * len(unieken))})", unieken)} \
        if unieken else set()
    items = []
    for o in opnames:
        if f"plaud:{o.get('plaud_id')}" in in_tabel:
            continue
        toestand = o.get("toestand")
        zonder_audio = (o.get("audio") or {}).get("staat") == "ontbreekt"
        if toestand == "wacht_op_transcript":
            wat = "kort, na te kijken" if _kort_wachtend(o) else "wacht op transcript"
        elif toestand == "onvolledig":
            wat = "onvolledig, audio ontbreekt" if zonder_audio else "onvolledig"
        elif toestand == "compleet":
            wat = "transcript binnen, nog niet verwerkt"
        elif toestand == "conflict":
            wat = "staat in meer dan één map, Mehdi kiest"
        else:
            wat = str(toestand or "toestand onbekend")
        items.append(_item(uur(o.get("start_brussel")), "Plaud-opname", f"{_duur(o.get('duur_minuten'))}, {wat}"))
    stand = {"opnames": len(opnames), "in_tabel": len(in_tabel),
             "wacht_op_transcript": sum(1 for o in opnames if o.get("toestand") == "wacht_op_transcript"),
             "kort": sum(1 for o in opnames if _kort_wachtend(o)),
             "onvolledig": sum(1 for o in opnames if o.get("toestand") == "onvolledig"),
             "zonder_audio": sum(1 for o in opnames if (o.get("audio") or {}).get("staat") == "ontbreekt"),
             "manifest_van": gemaakt, "na_de_dag": gemaakt_t >= tot}
    return items, stand


def per_wacht(conn, wacht, label, dag, status=None, noden=()):
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
    # PLAUD-8 (T-0120): 'rondes' is het aantal regels in het werkverslag (zo toont de pagina het: '408 regels'), niet het
    # aantal rondes (29-10 bij De Plaudwacht 24). rondes_geteld telt de slotregels 'ronde:'; een wacht die er geen
    # schrijft, heeft geen meetbare rondes: None, nooit 0.
    try:
        rondes_geteld = conn.execute("SELECT COUNT(*) FROM logboek WHERE naam=? AND ts>=? AND ts<? AND tekst LIKE ?",
                                     (wacht, van, tot, RONDE_REGEL + "%")).fetchone()[0] or None
    except Exception:  # noqa: BLE001  dan onbekend; het werkverslag zelf staat hierboven al apart
        rondes_geteld = None
    plaud = None
    if wacht == "plaud-wacht" and not leesfout:
        try:
            extra, plaud = lees_plaud(conn, dag)
            items += extra
        except Exception as e:  # noqa: BLE001  zoals hierboven: de rest van de pagina blijft staan
            leesfout = f"niet gelezen ({type(e).__name__})"
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
    else:
        oordeel, kleur = "niets binnen, geen ronde", "grijs"
    return {"naam": wacht, "label": label, "oordeel": oordeel, "kleur": kleur, "aantal": len(items),
            "items": items[:MAX_ITEMS], "rondes": len(log), "fouten": fouten, "log": log[-MAX_LOG:],
            "gedekt": gedekt, "leesfout": leesfout, "logfout": logfout, "noden": list(noden),
            "status": None if not st else {"status": st.get("status"), "detail": kort(st.get("detail"), 200),
                                            "laatste": uur(st.get("ts")), "laatste_ts": st.get("ts")},
            "rondes_geteld": rondes_geteld,
            # PLAUD-7: bij De Plaudwacht de opnames van die dag volgens het manifest, of None (onbekend)
            **({"plaud": plaud} if wacht == "plaud-wacht" else {})}


def dag(conn, dag_, agents, vakken, boven):
    """Alle wachten van de groep Dagbundelaar voor één dag, in hun vakken. agents: naam -> label."""
    date.fromisoformat(dag_)
    st = {r["naam"]: r for r in conn.execute("SELECT * FROM status").fetchall()}
    nood = {}
    for r in conn.execute("SELECT naam, tekst FROM nood WHERE open=1 ORDER BY id").fetchall():
        nood.setdefault(r["naam"], []).append(kort(r["tekst"], 200))
    groepen = [("De Dagbundelaar en Ai Angel", tuple(boven))] + [(v, tuple(w)) for v, w in vakken]
    uit = []
    for vak, namen in groepen:
        uit.append({"vak": vak, "wachten": [per_wacht(conn, n, agents.get(n, n), dag_, st.get(n), nood.get(n, ()))
                                            for n in namen]})
    alle = [w for v in uit for w in v["wachten"]]
    return {"dag": dag_, "vakken": uit,
            "telling": {k: sum(1 for w in alle if w["kleur"] == k) for k in ("groen", "oranje", "rood", "grijs")},
            "items": sum(w["aantal"] for w in alle)}
