#!/usr/bin/env python3
"""De Agendawacht (Privé) — leest Mehdi's agenda's volgens de afspraken met Nova
en zet klaar wat anderen nodig hebben.

Elke werkdag om 06:30 en daarna elke twee uur:
  1. de negen actieve agenda's (AGENDA_KALENDERS in mijnagents-data/.env, anders
     de vaste lijst hieronder) van gisteren tot zeven dagen vooruit;
  2. per afspraak de titel lezen zoals Nova hem afspraak: "Mehdi: !! [HA-KB] WB 2310 -
     werfbezoek ..." -> firma HA, soort KB (klant buiten), type WB, nummer 2310;
     "!!" = buiten met reistijd, "??" = niet bevestigd; "Reistijd"-blokken slaan we over;
  3. koppelen aan een deal (Pipedrive H-Architects: projectnummer, anders naam);
  4. klaarzetten per firma (h-architects, unabo, harmoniebouw, contrax; PRIVE -> mehdi),
     het dagplan van vandaag en "gisteren zonder verslag" voor Mehdi, en een signaal
     voor titels die de conventie niet volgen (zodat we beter communiceren);
  5. werkverslag op het bord.
Leest alleen. Verandert nooit een afspraak.
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import agenda  # noqa: E402
import bord  # noqa: E402
import pipedrive  # noqa: E402

NAAM = "agenda-wacht"
ag = bord.Agent(NAAM)

# De negen actieve agenda's volgens "agenda afspraken met Nova" (Feestdagen is read-only).
KALENDERS = {
    "mehdiprivewerkagenda@gmail.com": "mehdiprivewerkagenda (intern + Harmoniebouw-werk)",
    "73e8b6359d04b7bdb02aa045e668cd6f9d9f007bec51ce370494e7de7501f0c4@group.calendar.google.com": "H-Architects",
    "b135d9900db83399539bb5fe4ad9dc1ace19af20273c078ce2180cc47e9232fe@group.calendar.google.com": "UNABO",
    "e108191db825d97fb068a781463302c0e9c527d3927a85a514b1c8c5754b6048@group.calendar.google.com": "Harmoniebouw",
    "contraxcalendar@gmail.com": "Contrax",
    "385ee9ff8749fe5e5929090550d42611f4ce2437d11b56f3d4d943619b4c479f@group.calendar.google.com": "Lara",
    "bfe28ee64dc72b449582af5e6a9fc6af3669709adf07adc8b49eb97666f07981@group.calendar.google.com": "Prive Buiten",
    "zoomafspraken@gmail.com": "zoomafspraken (sales via Calendly)",
    "en.be#holiday@group.v.calendar.google.com": "Feestdagen BE",
}
FIRMA_AFDELING = {"HA": "h-architects", "UNABO": "unabo", "HB": "harmoniebouw", "HARMONIEBOUW": "harmoniebouw",
                  "CONTRAX": "contrax", "ENERGIE": "unabo", "PRIVE": "mehdi"}
KALENDER_AFDELING = {"H-Architects": "h-architects", "UNABO": "unabo", "Harmoniebouw": "harmoniebouw", "Contrax": "contrax",
                     "zoomafspraken (sales via Calendly)": "h-architects"}
SOORT = {"KB": "klant buiten", "PB": "prospect buiten (plaatsbezoek)", "KO": "klant online", "PO": "prospect online", "IN": "intern"}
TYPES = {"WB": "werfbezoek", "OPL": "oplevering", "PLB": "plaatsbeschrijving", "SCN": "3D-scan", "EPB": "EPB"}
CODE_RE = re.compile(r"\[(HA|UNABO|HB|HARMONIEBOUW|CONTRAX|ENERGIE|PRIVE)(?:-(KB|PB|KO|PO|IN))?\]", re.I)


def kalenders():
    ruw = os.environ.get("AGENDA_KALENDERS", "").strip()
    return [k.strip() for k in ruw.split(",") if k.strip()] or list(KALENDERS)


def lees_titel(titel):
    """Ontleedt een titel volgens de Nova-conventie. Geeft dict met firma, soort, type,
    nummer, klant, buiten (!!), onzeker (??), reistijd, conform."""
    t = titel.strip()
    uit = {"reistijd": bool(re.search(r"reistijd", t, re.I)) or t.startswith("🚗"),
           "buiten": "!!" in t, "onzeker": "??" in t, "firma": "", "soort": "", "type": "", "nummer": "", "klant": ""}
    m = CODE_RE.search(t)
    if m:
        uit["firma"] = m.group(1).upper()
        uit["soort"] = (m.group(2) or "").upper()
    rest = CODE_RE.sub("", t)
    rest = re.sub(r"^\s*(mehdi|siyan|shelton|angela)\s*:\s*", "", rest, flags=re.I)
    rest = rest.replace("!!", "").replace("??", "").strip(" -")
    mt = re.match(r"^\s*(WB|OPL|PLB|SCN|EPB)\b", rest, re.I)
    if mt:
        uit["type"] = mt.group(1).upper()
        rest = rest[mt.end():].strip(" -")
    mn = re.search(r"\b(\d{4,5})\b", rest)
    if mn:
        uit["nummer"] = mn.group(1)
    uit["klant"] = re.sub(r"\b\d{4,5}\b", "", rest).strip(" -:").split(" - ")[0][:80]
    uit["conform"] = bool(m) or uit["reistijd"]
    return uit


def deals_index():
    d = pipedrive.get("harchitects", "/deals", {"status": "open", "limit": 500})
    items = d if isinstance(d, list) else (d or {}).get("data") or []
    uit = []
    for x in items:
        titel = x.get("title", "")
        m = re.match(r"^\s*((?:26|56)\d\d)\b", titel)
        uit.append({"id": x.get("id"), "titel": titel, "nummer": m.group(1) if m else "",
                    "delen": {w for w in re.split(r"[^a-z0-9]+", titel.lower()) if len(w) > 2 and not w.isdigit()}})
    return uit


def koppel(info, titel, deals):
    if info["nummer"]:
        for d in deals:
            if d["nummer"] == info["nummer"]:
                return d, "projectnummer in de titel"
    delen = {w for w in re.split(r"[^a-z0-9]+", (info["klant"] or titel).lower()) if len(w) > 2}
    beste, score = None, 0
    for d in deals:
        s = len(d["delen"] & delen)
        if s > score:
            beste, score = d, s
    return (beste, f"naam in de titel ({score} woorden)") if beste and score >= 2 else (None, "")


ONLINE_MIN = int(os.environ.get("AGENDA_HERINNERING_ONLINE", "5"))
BUITEN_MIN = int(os.environ.get("AGENDA_HERINNERING_BUITEN", "30"))
OVERIG_MIN = int(os.environ.get("AGENDA_HERINNERING_OVERIG", "10"))


PROSPECT_FIRMAS = ("HA", "UNABO", "TKN")
PROSPECT_SOORTEN = ("PO", "PB")


def melding_gewenst(a):
    """De regel van Mehdi (11-09-2026): alleen afspraken met prospecten van
    H-Architects, UNABO en TKN (codes PO en PB) krijgen een melding. Geen intern,
    geen terugkerende afspraken, geen reistijd, geen hele-dag-items."""
    info = lees_titel(a["titel"])
    if a.get("hele_dag") or a.get("_terugkerend") or info["reistijd"]:
        return False, info
    return (info["firma"] in PROSPECT_FIRMAS and info["soort"] in PROSPECT_SOORTEN), info


def _patch(a, body, tok):
    import urllib.parse
    import urllib.request
    url = f"{agenda.API}/calendars/{urllib.parse.quote(a['kalender'], safe='')}/events/{urllib.parse.quote(a['id'], safe='')}"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="PATCH",
                                 headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=30)


def herinneringen_zetten(items, alleen_dag=None):
    """Werkwijze stap 5: een pop-upherinnering op elke komende prospect-afspraak
    (regel in melding_gewenst) die er nog geen heeft: online 5 min, buiten (!!) 30 min.
    Een herinnering die ik zelf eerder op een niet-gewenste afspraak zette (mijn
    handtekening: één pop-up van 10 of 30 min) haal ik weer weg, zodat intern en
    terugkerend stil blijven. Bestaande herinneringen van Mehdi laat ik staan.
    Geeft (gezet, al, weggehaald, fout)."""
    tok = agenda._toegang()
    nu_iso = datetime.now().astimezone().isoformat()
    gezet, al, weg, fout = 0, 0, 0, 0
    for a in items:
        if a["start"] < nu_iso[:len(a["start"])] or a.get("kalender", "").startswith("en.be#"):
            continue
        if alleen_dag and a["start"][:10] != alleen_dag:
            continue
        gewenst, info = melding_gewenst(a)
        r = a.get("_reminders") or {}
        eigen = r.get("overrides") or []
        mijn = len(eigen) == 1 and eigen[0].get("method") == "popup" and eigen[0].get("minutes") in (OVERIG_MIN, BUITEN_MIN, ONLINE_MIN)
        try:
            if gewenst and not eigen:
                minuten = BUITEN_MIN if info["buiten"] else ONLINE_MIN
                _patch(a, {"reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": minuten}]}}, tok)
                gezet += 1
            elif gewenst:
                al += 1
            elif not gewenst and mijn:
                _patch(a, {"reminders": {"useDefault": True, "overrides": []}}, tok)
                weg += 1
        except Exception as e:  # noqa: BLE001
            fout += 1
            print("herinnering mislukt:", a["titel"][:40], type(e).__name__, file=sys.stderr)
    return gezet, al, weg, fout


def main():
    ag.hartslag("actief", taak="agenda lezen")
    try:
        if not agenda.beschikbaar():
            ag.hartslag("fout", taak="geen agendatoegang", detail="GOOGLE_AGENDA_* ontbreekt in ~/appportal/.env")
            return
        os.environ["CONTRACTEN_KALENDERS"] = ",".join(kalenders())   # agenda.kalenders() leest die
        items = agenda.afspraken(-1, 8)
        fouten = [i for i in items if i.get("fout")]
        items = [i for i in items if not i.get("fout")]
        deals = deals_index()
        vandaag = datetime.now().date().isoformat()
        gisteren = (datetime.now().date() - timedelta(days=1)).isoformat()
        klaar, gekoppeld, niet_conform, dagplan, gisteren_lijst = [], 0, [], [], []
        per_afdeling = {}
        for a in items:
            info = lees_titel(a["titel"])
            if info["reistijd"] or a["kalender"] == "en.be#holiday@group.v.calendar.google.com":
                continue
            kal = KALENDERS.get(a["kalender"], a["kalender"])
            dag = a["start"][:10]
            afdeling = FIRMA_AFDELING.get(info["firma"]) or KALENDER_AFDELING.get(kal) or "mehdi"
            deal, hoe = (None, "")
            if afdeling == "h-architects":
                deal, hoe = koppel(info, a["titel"], deals)
                gekoppeld += 1 if deal else 0
            if not info["conform"] and kal not in ("Lara", "Prive Buiten", "Feestdagen BE") and dag >= vandaag:
                niet_conform.append(f"{dag} {a['start'][11:16]} {a['titel']} ({kal})")
            oms = ", ".join(x for x in (SOORT.get(info["soort"], ""), TYPES.get(info["type"], ""),
                                        "buiten + reistijd" if info["buiten"] else "", "niet bevestigd" if info["onzeker"] else "") if x)
            regel = f"{'hele dag' if a['hele_dag'] else a['start'][11:16]} {a['titel']}" + (f" [{oms}]" if oms else "") + (f" · deal {deal['id']}" if deal else "")
            if dag == vandaag:
                dagplan.append(regel)
            if dag == gisteren and (info["soort"] in ("KB", "PB", "KO", "PO") or deal):
                gisteren_lijst.append(regel)
            if dag >= vandaag and afdeling != "mehdi":
                per_afdeling[afdeling] = per_afdeling.get(afdeling, 0) + 1
                klaar.append({"voor": afdeling, "soort": "afspraak", "sleutel": str(deal["id"]) if deal else (info["nummer"] or ""),
                              "titel": f"{dag} {regel}", "uniek": f"agenda:{a['kalender']}:{a['id']}", "verwijzing": a.get("link", ""),
                              "inhoud": {"datum": dag, "start": a["start"], "einde": a["einde"], "titel": a["titel"], "agenda": kal,
                                         "firma": info["firma"], "soort": info["soort"], "type": info["type"], "nummer": info["nummer"],
                                         "klant": info["klant"], "buiten": info["buiten"], "onzeker": info["onzeker"],
                                         "locatie": a["locatie"], "deelnemers": a["deelnemers"],
                                         "deal_id": deal["id"] if deal else None, "koppeling": hoe, "omschrijving": a["omschrijving"][:800]}})
        tekst = "Vandaag:\n" + ("\n".join("- " + r for r in dagplan) or "- niets in de agenda") + \
                "\n\nGisteren, klantcontact waar een verslag of opname bij hoort:\n" + ("\n".join("- " + r for r in gisteren_lijst) or "- niets")
        klaar.append({"voor": "mehdi", "soort": "dagplan", "sleutel": vandaag, "titel": f"Dagplan {vandaag}", "uniek": f"dagplan:{vandaag}", "inhoud": tekst})
        if niet_conform:
            klaar.append({"voor": "mehdi", "soort": "signaal", "sleutel": vandaag, "titel": f"{len(niet_conform)} afspraken zonder Nova-code ([HA-KB] enz.)",
                          "uniek": f"agenda-conventie:{vandaag}", "inhoud": "\n".join("- " + x for x in niet_conform[:40])})
        uit = ag.klaarzet(klaar)
        gezet, al, weg, fout_h = herinneringen_zetten(items)
        ag.log(f"dag {vandaag}", "schrijf", f"herinneringen (alleen prospecten HA/UNABO/TKN, PO en PB): {gezet} gezet (online {ONLINE_MIN} min, buiten {BUITEN_MIN} min), {al} hadden er al een, {weg} weggehaald van intern of terugkerend, {fout_h} mislukt",
               "\n".join(f"{'MELDING ' if melding_gewenst(a)[0] else 'stil    '} {a['start'][:16]} {a['titel'][:70]}" for a in items if a['start'][:10] >= vandaag and not a.get('hele_dag')))
        ag.log(f"dag {vandaag}", "bron", f"{len(items)} afspraken uit {len(kalenders())} agenda's; {gekoppeld} H-A-afspraken aan een deal gekoppeld; per afdeling: " +
               ", ".join(f"{k} {v}" for k, v in sorted(per_afdeling.items())) + (f"; {len(fouten)} agenda's niet leesbaar: " + ", ".join(f['kalender'] for f in fouten) if fouten else ""),
               "\n".join(f"{a['start'][:16]} {KALENDERS.get(a['kalender'], a['kalender'])[:14]} | {a['titel']}" for a in items))
        ag.log(f"dag {vandaag}", "bevinding", f"{len(niet_conform)} toekomstige afspraken zonder Nova-code", "\n".join(niet_conform[:60]))
        ag.log(f"dag {vandaag}", "schrijf", f"klaargezet: {uit.get('nieuw', 0)} nieuw, {uit.get('bestaand', 0)} al bekend", tekst)
        ag.log_verstuur()
        ag.hartslag("waakt", taak="agenda in het oog", detail=f"vandaag {len(dagplan)} afspraken; {gekoppeld} gekoppeld; {len(niet_conform)} zonder code",
                    nood=([{"tekst": f"{len(niet_conform)} toekomstige afspraken zonder code ([HA-KB] enz.): titels rechtzetten (Mehdi, of via een voorstel zodra het runbook agenda-titel er is)", "wie": "mehdi"}] if niet_conform else [])
                    + ([{"tekst": f"{fout_h} herinneringen konden niet gezet worden", "wie": "claude-code"}] if fout_h else [])
                    + ([{"tekst": f"{len(fouten)} agenda(s) niet leesbaar: " + ", ".join(f["kalender"][:30] for f in fouten), "wie": "mehdi"}] if fouten else []))
    except Exception as e:  # noqa: BLE001
        ag.log("", "fout", f"{type(e).__name__}: {str(e)[:300]}")
        ag.log_verstuur()
        ag.hartslag("fout", taak="ronde mislukt", detail=f"{type(e).__name__}: {str(e)[:120]}")
        raise


if __name__ == "__main__":
    main()
