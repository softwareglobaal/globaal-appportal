#!/usr/bin/env python3
"""Kijkt of er iets aan de agenda veranderd is en zet de Agendawacht dan meteen aan.

De wacht draait 's ochtends, maar een afspraak die om elf uur verplaatst wordt mag geen
dag wachten op zijn reistijd, kleur en melding. Dit script vraagt elke keer welke
afspraken er sinds de vorige keer gewijzigd zijn, en start de wacht voor de dagen die
het betreft. Verandert er niets, dan doet het niets en kost het niets.

Afvinken gebeurt pas achteraf (audit 02-10-2026, A5): per agenda een cursor die pas vooruitgaat
als die agenda volledig gelezen is en elke getroffen dag verwerkt. Een dag waarvoor de wacht
faalt, blijft open in de stand en komt de volgende ronde terug, tot MAX_POGINGEN keer. Een dag waarvoor het
rondeslot van de wacht bezet bleef, blijft open zonder dat het als poging telt (Codex A28, 15-10-2026).

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/agenda_signaal.py
"""
import fcntl
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
from koppelingen import agenda as A           # noqa: E402

STAND = Path.home() / "appportal/mijnagents-data/agenda-signaal.json"
# Wat de wacht niet kon afhandelen, blijft zichtbaar tot het beoordeeld is (nacontrole v1.2, A5/A8): een dag die na vijf
# pogingen opgegeven werd, en een annulering zonder start waarvan de dag onbekend is. De zelfcontrole toont ze.
CONTROLEPUNTEN = Path.home() / "appportal/mijnagents-data/agenda-signaal-controlepunten.json"
ANNULERING_SPOOR = W.bellen.AFZEGSPOOR


def controlepunten():
    try:
        d = json.loads(CONTROLEPUNTEN.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    return {"opgegeven": list(d.get("opgegeven") or []), "onbekend": list(d.get("onbekend") or [])}


def controlepunten_bewaren(d):
    CONTROLEPUNTEN.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONTROLEPUNTEN.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, CONTROLEPUNTEN)


def beoordeeld(soort, sleutel, door="claude"):
    """Zet een controlepunt op beoordeeld (soort 'opgegeven' met de dag, of 'onbekend' met kalender|id)."""
    d = controlepunten()
    for c in d[soort]:
        if (c.get("dag") if soort == "opgegeven" else c.get("sleutel")) == sleutel and not c.get("beoordeeld"):
            c["beoordeeld"] = f"{datetime.now(timezone.utc).isoformat(timespec='minutes')} door {door}"
    controlepunten_bewaren(d)
PYTHON = str(Path.home() / "agents/.venv/bin/python")
# Een dag waarvoor de wacht faalt, probeer ik zo vaak (een poging per ronde van 12 minuten). Daarna geef ik
# hem luid op, anders houdt een kapotte dag de cursor van zijn agenda eeuwig vast (audit 02-10-2026, A5).
MAX_POGINGEN = 5
# Het dagproces krijgt 900 s, waarvan hooguit SLOT_WACHT op het rondeslot van de wacht. Blijft het slot bezet, dan
# eindigt het met SLOT_BEZET: dat is geen mislukte poging, de dag blijft open (Codex A28, 15-10-2026). Tot dan wachtte
# het dagproces tot 900 s op het slot, liep het in de time-out en werd een dag na vijf drukke rondes opgegeven.
BUDGET = 900
SLOT_WACHT = 120
SLOT_BEZET = 75
# Zoveel rondes na elkaar bezet (12 minuten per ronde) is geen drukte meer: dan zeg ik het luid, opgeven doe ik niet
BEZET_ALARM = 10
# nextPageToken moet in de velden staan, anders laat Google het weg en lijkt de eerste pagina alles (A4).
# originalStartTime geeft de dag waar een reeksinstantie oorspronkelijk stond (A7, A8).
VELDEN = ("nextPageToken,items(id,summary,status,updated,description,start/dateTime,start/date,end/dateTime,end/date,"
          "originalStartTime/dateTime,originalStartTime/date,recurringEventId,location,attendees(email,responseStatus,self))")


def vorige():
    try:
        return json.loads(STAND.read_text())
    except (OSError, ValueError):
        return {}


def bewaar(d):
    """Atomair: eerst een tijdelijk bestand naast de stand, dan os.replace. Audit 02-10-2026 (A5): een crash
    midden in het schrijven kan een half bestand nalaten; vorige() leest dat als leeg en dan zijn alle
    vingerafdrukken weg, zodat elke afspraak weer als gewijzigd telt (het Google-plafond van FR-62)."""
    STAND.parent.mkdir(parents=True, exist_ok=True)
    tmp = STAND.with_name(f"{STAND.name}.{os.getpid()}.tmp")
    with open(tmp, "w") as f:
        f.write(json.dumps(d, indent=0))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STAND)


def slot_nemen():
    """Een ronde tegelijk, anders None. De stand wordt nu pas na de verwerking geschreven (A5); zonder slot
    deed een ronde die start terwijl de vorige nog loopt (elke dag tot 15 minuten) dezelfde dagen opnieuw."""
    STAND.parent.mkdir(parents=True, exist_ok=True)
    f = open(STAND.with_name(STAND.name + ".lock"), "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def vingerafdruk(ev):
    """Wat de agent aangaat van een afspraak: titel, status, tijd, plaats en gasten. Een kleur, omschrijving,
    herinnering of merk hoort er niet bij. Gezien 26-09-2026: elke kleurwissel van buiten en elke eigen
    schrijfactie startte de ronde opnieuw, elke 12 minuten voor 15 dagen, en het Google-plafond was om
    09:00 op (FR-62)."""
    return json.dumps([ev.get("summary"), ev.get("status"), ev.get("start"), ev.get("end"), ev.get("location"),
                       sorted((g.get("email") or "") for g in ev.get("attendees") or []),
                       W.bellen.afgezegd(ev)], ensure_ascii=False)


def _lara_reeks(kal, ev):
    """De reeks van een instantie in de Lara-agenda, of ''. Google geeft bij een geschrapte instantie vaak alleen id,
    recurringEventId en originalStartTime; zonder recurringEventId volstaat het deel van het id voor '_JJJJMMDD'."""
    if W.KALENDERS.get(kal) != "Lara":
        return ""
    if ev.get("recurringEventId"):
        return ev["recurringEventId"]
    m = re.match(r"^(.+)_\d{8}(?:T\d{6}Z?)?$", ev.get("id") or "")
    return m.group(1) if m else ""


def _is_rit(ev, vorig):
    return W.lees_titel(ev.get("summary") or _oude_titel(vorig) or "")["reistijd"]


def _is_lara(kal):
    return W.KALENDERS.get(kal) == "Lara"


def annulering_kandidaat(kal, ev, vorig, nu):
    """Een nieuwe, expliciete afzegging met een herleidbaar tijdstip; geen herhaalde eigen wijziging.
    Een afspraak in de Lara-agenda (een instantie van een reeks of een losse kopie) of een ritblok is nooit een afzegging
    om 'niet vertrekken' voor te bellen. Gezien 22-10-2026: een assistent wiste de Lara-afspraken van een week die ten onrechte als vakantie
    stond, en om 06:00 belde de agent zes keer 'afgezegd, niet vertrekken' voor ophaalmomenten die gewoon doorgingen
    (FR-210). Een gewiste Lara-afspraak op een schooldag wordt een vraag (lara_wissing_kandidaat)."""
    if not (ev.get("status") == "cancelled" or W.bellen.afzegging_tekst(ev)):
        return None
    if _is_lara(kal) or _is_rit(ev, vorig):
        return None
    oud = []
    if vorig:
        try:
            oud = json.loads(vorig[0])
        except (ValueError, TypeError):
            pass
    if len(oud) > 1 and (oud[1] == "cancelled" or (len(oud) > 6 and oud[6])):
        return None
    start = (ev.get("start") or {}).get("dateTime")
    if not start and len(oud) > 2:
        start = (oud[2] or {}).get("dateTime")
    try:
        begint = datetime.fromisoformat(start)
    except (TypeError, ValueError):
        return None
    # Geen historische afzegging bellen bij een eerste uitrol of een herlezing:
    # alleen een afspraak die nog moet beginnen krijgt een proactieve oproep.
    if not (nu <= begint <= nu + timedelta(days=30)):
        return None
    titel = _toonbare_titel(kal, ev.get("summary") or _oude_titel(vorig) or "afspraak")
    return {"sleutel": f"{kal}:{ev.get('id', '')}:{start}", "titel": titel[:80], "start": begint}


def lara_wissing_kandidaat(kal, ev, vorig, nu, officieel, dekking):
    """Een afspraak in de Lara-agenda (een instantie van een vaste reeks of een losse kopie, zoals de afspraken die
    Claude 1 op 26-10 terugzette) die nu geschrapt is, op een komende schooldag volgens de officiële bron (maandag tot
    vrijdag, geen vakantie of feestdag, binnen de dekking). Dan is het waarschijnlijk een fout: een vraag in de
    privé-agenda, de agent zet niets terug (driehoeksoverleg 27-10-2026, L3; FR-210). Geeft None of
    {sleutel, dag, uur, titel}; de titel blijft privé en komt in geen uitvoer."""
    if ev.get("status") != "cancelled" or not _is_lara(kal) or _is_rit(ev, vorig):
        return None
    reeks = _lara_reeks(kal, ev) or ev.get("id") or ""
    if not reeks:
        return None
    oud = []
    if vorig:
        try:
            oud = json.loads(vorig[0])
        except (ValueError, TypeError):
            pass
    if len(oud) > 1 and oud[1] == "cancelled":
        return None                                   # al eerder geschrapt gezien: geen tweede vraag
    # eerst de actuele start die Google meegeeft, dan de laatst bekende uit de vingerafdruk, dan de oorspronkelijke: een
    # verplaatste instantie kan een voorbije oorspronkelijke dag hebben terwijl de afspraak nog komt (Codex-hertest 3 en 4)
    o = (ev.get("start") if _dag(ev.get("start")) else None) \
        or (oud[2] if len(oud) > 2 and isinstance(oud[2], dict) and _dag(oud[2]) else None) \
        or ev.get("originalStartTime") or {}
    dag, uur = _dag(o), (o.get("dateTime") or "")[11:16]
    try:
        d = date.fromisoformat(dag)
    except ValueError:
        return None
    if d < nu.astimezone(W.TIJDZONE).date() or d.weekday() >= 5 or dag in officieel or (dekking and d > dekking):
        return None
    return {"sleutel": f"{reeks}:{dag}", "dag": dag, "uur": uur, "titel": ev.get("summary") or _oude_titel(vorig) or ""}


def meld_lara_wissing(kandidaat, tok):
    """De vraag in de privé-agenda, daarna een signaal op het bord (zonder titel: privé). Het signaal is bijzaak: lukt het
    niet, dan staat de vraag er toch. kandidaat['dagen'] zijn alle geschrapte schooldagen van dezelfde reeks in deze
    ronde: een hele reeks wissen geeft zo één vraag, geen tientallen (reviewronde 27-10-2026)."""
    eid = W.lara_gewist_melden(kandidaat["dag"], kandidaat["uur"], kandidaat["titel"], kandidaat["sleutel"], tok,
                               dagen=kandidaat.get("dagen"))
    try:
        W.ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": kandidaat["dag"],
                        "uniek": f"agenda-lara-gewist:{kandidaat['sleutel']}",
                        "titel": "Vaste Lara-afspraak gewist op een schooldag",
                        "inhoud": "De vraag staat in je privé-agenda op die dag. De agent zet niets terug."}])
    except Exception as e:  # noqa: BLE001
        print(f"Lara-signaal niet op het bord ({type(e).__name__}); de vraag staat in de privé-agenda", file=sys.stderr)
    return eid if isinstance(eid, str) else ""


def meld_annulering(kandidaat, nu):
    """Bel vanaf het vaste nummer; het afsprakenummer blijft exclusief voor vertrek."""
    sleutel = kandidaat["sleutel"]
    try:
        if sleutel in W.bellen.spoor_lezen(ANNULERING_SPOOR):
            return True
        if sleutel in W.bellen.spoor_bezig(ANNULERING_SPOOR):
            print(f"afzegging mogelijk gebeld, handmatige controle nodig: {sleutel}", file=sys.stderr)
            return False
        W.bellen.spoor_schrijven(ANNULERING_SPOOR, sleutel, nu.isoformat(), bezig=True)
    except OSError as e:
        print(f"afzegging niet gebeld: belspoor onleesbaar ({type(e).__name__})", file=sys.stderr)
        return False
    tijd = kandidaat["start"].astimezone(W.TIJDZONE).strftime("%d-%m om %H:%M")
    tekst = f"Mehdi, afspraak {tijd} is afgezegd. Niet vertrekken. {kandidaat['titel']}."
    uitkomst = W.bellen.bel_vast(tekst, "Controleer je agenda of mail.")
    if not W.bellen.gelukt(uitkomst):
        # Er is zeker geen oproep gestart; sluit het 'bezig'-record af als mislukte poging.
        try:
            W.bellen.spoor_schrijven(ANNULERING_SPOOR, sleutel, nu.isoformat(), poging=1)
        except OSError:
            print(f"afzegging niet gebeld: belspoor niet af te sluiten ({sleutel})", file=sys.stderr)
        print(f"afzegging mogelijk niet gemeld: {sleutel}", file=sys.stderr)
        return False
    try:
        W.bellen.spoor_schrijven(ANNULERING_SPOOR, sleutel, nu.isoformat())
    except OSError:
        print(f"afzegging gebeld, maar belspoor niet afgemaakt: {sleutel}", file=sys.stderr)
        return False
    print(f"afzegging gemeld: {tijd} {kandidaat['titel']}")
    return True


def _dag(tijd):
    return ((tijd or {}).get("dateTime") or (tijd or {}).get("date") or "")[:10]


def vroegere_dagen(kal, ev, oud):
    """De dag(en) waar deze afspraak vroeger stond. Eerst de eigen vingerafdruk. Is die er niet, dan dezelfde
    afspraak (zelfde id) op een andere agenda: verhuisd. En de oorspronkelijke start van een reeksinstantie.
    Audit 02-10-2026 (A7): een verplaatsing plande alleen de nieuwe dag, de oude bleef met zijn rit staan."""
    eid = ev.get("id", "")
    vorig = oud.get(f"{kal}|{eid}")
    if vorig:
        return {vorig[1]}
    uit = {v[1] for k, v in oud.items() if eid and k.endswith("|" + eid)}
    o = _dag(ev.get("originalStartTime"))
    return uit | ({o} if o else set())


def _oude_titel(vorig):
    try:
        return json.loads(vorig[0])[0] or ""
    except (TypeError, ValueError, IndexError):
        return ""


def te_verwerken(kal, items, oud, vinger, vanaf="", onbekend=None):
    """Geeft (dagen, regels) voor de afspraken die echt veranderden, en werkt `vinger` bij.
    Een verplaatste afspraak plant de nieuwe en de oude dag (A7). Een geschrapte afspraak zonder start (Google
    geeft dan alleen id en status) plant de dag uit de bewaarde vingerafdruk (A8). Een oude dag voor `vanaf`
    plan ik niet: die ligt voor het venster dat ik bij Google opvraag."""
    dagen, wat = set(), []
    for ev in items:
        # reistijdblokken van de wacht zelf tellen niet mee, anders start hij zichzelf
        if W.lees_titel(ev.get("summary", "") or "")["reistijd"]:
            continue
        sleutel = f"{kal}|{ev.get('id', '')}"
        vorig = oud.get(sleutel)
        s = _dag(ev.get("start"))
        vroeger = vroegere_dagen(kal, ev, oud)
        dag = s or min(vroeger, default="")
        if not dag:
            # een annulering zonder start en zonder vingerafdruk: de dag is onbekend. Niet stil afvinken (A8).
            if onbekend is not None and ev.get("status") == "cancelled":
                onbekend.append({"sleutel": sleutel, "kalender": kal, "id": ev.get("id", ""),
                                 "titel": _toonbare_titel(kal, ev.get("summary") or "")[:80]})
            continue
        vp = vingerafdruk(ev)
        vinger[sleutel] = [vp, dag]
        vorig_vp = (vorig or [None])[0]
        # Migratie van de oude vingerafdruk met zes velden: geen volledige dagronde
        # enkel omdat annulering als zevende veld is toegevoegd.
        if vorig_vp:
            try:
                oude_waarden = json.loads(vorig_vp)
                if isinstance(oude_waarden, list) and len(oude_waarden) == 6:
                    vorig_vp = json.dumps(oude_waarden + [False], ensure_ascii=False)
            except (TypeError, ValueError):
                pass
        if vorig_vp == vp:
            continue
        dagen |= {d for d in vroeger if d >= vanaf} | ({s} if s else set())
        was = sorted(d for d in vroeger if d != dag)
        titel = _toonbare_titel(kal, ev.get("summary") or _oude_titel(vorig) or "(zonder titel)")
        wat.append(f"{dag} {ev.get('status','')[:9]:<9} {titel[:52]}" + (f" (was {', '.join(was)})" if was else ""))
    return dagen, wat


def _toonbare_titel(kal, titel):
    """Een titel van de privé-agenda, van Lara of een zorgafspraak komt in geen uitvoer: '(privé)'. De lijst komt uit
    W.kalenders(), dus ook die agenda's (Codex A25, 15-10-2026). Zelfde regel als de agent: W.is_prive."""
    return "(privé)" if W.is_prive({"kalender": kal, "titel": titel}) else titel


def _haal(url, kop):
    with urllib.request.urlopen(urllib.request.Request(url, headers=kop), timeout=40) as r:
        return json.load(r)


def lees_wijzigingen(kal, sinds, nu, kop):
    """Alle gewijzigde afspraken van een agenda sinds `sinds`, over alle pagina's. Een fout op welke pagina ook
    gooit door: dan is de bronlezing niet geslaagd en telt niets van deze agenda. Audit 02-10-2026 (A4): alleen
    de eerste 250 werden gelezen, de rest viel stil weg."""
    q = {"updatedMin": sinds, "singleEvents": "true", "showDeleted": "true", "maxResults": "250",
         "timeMin": (nu - timedelta(days=1)).isoformat(),
         "timeMax": (nu + timedelta(days=366)).isoformat(),   # afspraak is afspraak, hoe ver ook (FR-65)
         "fields": VELDEN}
    items, pagina = [], None
    while True:
        if pagina:
            q["pageToken"] = pagina
        d = _haal(f"{A.API}/calendars/{urllib.parse.quote(kal, safe='')}/events?" + urllib.parse.urlencode(q), kop)
        items += d.get("items", [])
        pagina = d.get("nextPageToken")
        if not pagina:
            return items


def draai_wacht(dag):
    """Start de wacht voor een dag. Geeft (gelukt, uitleg). Alleen exitcode 0 is gelukt; een andere exitcode,
    een time-out of een start die niet lukt is mislukt. Audit 02-10-2026 (A6): de exitcode werd genegeerd en
    een gecrashte wacht stond in het logboek als 'wacht gedraaid'.
    gelukt is None als het rondeslot bezet bleef (exitcode SLOT_BEZET): niet geprobeerd, geen mislukking (Codex A28,
    15-10-2026)."""
    try:
        r = subprocess.run([PYTHON, str(HIER / "agenda_wacht.py"), "--dag", dag, "--slot-wacht", str(SLOT_WACHT)],
                           capture_output=True, text=True, timeout=BUDGET)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{type(e).__name__}: {str(e)[:150]}"
    if r.returncode == SLOT_BEZET:
        return None, f"rondeslot bezet na {SLOT_WACHT} s (exitcode {SLOT_BEZET})"
    if r.returncode != 0:
        fout = [x.strip() for x in (r.stderr or "").splitlines() if x.strip()]
        return False, f"exitcode {r.returncode}: " + (fout[-1][:200] if fout else "geen foutmelding")
    laatste = [x for x in (r.stdout or "").splitlines() if "[schrijf]" in x or "[bevinding]" in x]
    return True, "; ".join(x.strip()[:70] for x in laatste[:3]) or "geen uitvoer"


def _leesfout(e):
    return f"HTTP {e.code}" if isinstance(e, urllib.error.HTTPError) else f"{type(e).__name__}: {str(e)[:150]}"


def ronde(tijd):
    st = vorige()
    nu = datetime.now(timezone.utc)
    # Een agenda zonder eigen cursor (eerste ronde, of een stand van voor 02-10-2026) begint waar de vorige
    # ronde keek. Ook een agenda die nu faalt krijgt die cursor vast, anders schuift hij mee met 'gekeken'.
    standaard = st.get("gekeken") or (nu - timedelta(minutes=20)).isoformat()
    kals = W.kalenders()
    cursor = {k: (st.get("cursor") or {}).get(k) or standaard for k in kals}
    open_ = dict(st.get("open") or {})
    kop = {"Authorization": "Bearer " + A._toegang()}
    vanaf = (nu - timedelta(days=1)).date().isoformat()
    dagen, wat, niet_gelezen, per_kal, onbekend = set(), [], [], {}, []
    annuleringen = dict(st.get("annulering_open") or {})
    lara_open = dict(st.get("lara_open") or {})
    lara_gemeld = dict(st.get("lara_gemeld") or {})
    lara_vraag = dict(st.get("lara_vraag") or {})      # reeks -> de vraag die er al staat (id, sleutel, dagen)
    officieel = W.lara_vakantiedagen()
    dekking = W.schoolvakantie_dekking() if officieel is not None else None
    if officieel is None:
        print(f"{tijd} officiële schoolvakanties niet te lezen: gewiste Lara-afspraken deze ronde niet nagekeken",
              file=sys.stderr)
    oud = st.get("vinger") or {}
    vinger = dict(oud)
    for kal in kals:
        try:
            items = lees_wijzigingen(kal, cursor[kal], nu, kop)
        except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
            print(f"{tijd} {kal[:32]}: {_leesfout(e)}, deze agenda telt deze ronde niet", file=sys.stderr)
            niet_gelezen.append(kal)
            continue
        per_kal[kal], w_ = te_verwerken(kal, items, oud, vinger, vanaf, onbekend)
        for ev in items:
            kandidaat = annulering_kandidaat(kal, ev, oud.get(f"{kal}|{ev.get('id', '')}"), nu)
            if kandidaat:
                annuleringen[kandidaat["sleutel"]] = {**kandidaat, "start": kandidaat["start"].isoformat()}
            lk = officieel is not None and lara_wissing_kandidaat(kal, ev, oud.get(f"{kal}|{ev.get('id', '')}"), nu,
                                                                  officieel, dekking)
            if lk and lk["sleutel"] not in lara_gemeld:
                lara_open[lk["sleutel"]] = lk
        dagen |= per_kal[kal]
        wat += w_

    melding_mislukt = officieel is None
    per_reeks = {}
    for sleutel, k in lara_open.items():
        per_reeks.setdefault(sleutel.rsplit(":", 1)[0], []).append((sleutel, k))
    for reeks, lijst in sorted(per_reeks.items()):
        lijst.sort(key=lambda sk: sk[1]["dag"])
        eerste = lijst[0][1]
        nieuw = [k["dag"] for _, k in lijst]
        try:
            v = lara_vraag.get(reeks) or {}
            # een reeks die over meer rondes gewist wordt, krijgt een vraag die aangevuld wordt, geen tweede (Codex-hertest);
            # alleen de komende dagen tellen, zodat de vraag naar de eerste komende gewiste dag verhuist (hertest 2)
            vandaag = nu.astimezone(W.TIJDZONE).date().isoformat()
            alle = sorted(d for d in set(v.get("dagen") or []) | set(nieuw) if d >= vandaag)
            if not (v.get("id") and alle and W.lara_gewist_bijwerken(v["id"], v.get("uur", ""), v.get("titel", ""),
                                                                   v["sleutel"], A._toegang(), alle)):
                v = {"sleutel": f"{reeks}:{eerste['dag']}", "uur": eerste["uur"], "titel": eerste["titel"]}
                v["id"] = meld_lara_wissing({**eerste, "sleutel": v["sleutel"], "dagen": nieuw}, A._toegang())
                alle = nieuw
            lara_vraag[reeks] = {**v, "dagen": alle}
            for sleutel, k in lijst:
                lara_gemeld[sleutel] = k["dag"]
                lara_open.pop(sleutel, None)
            print(f"{tijd} vaste Lara-afspraak gewist op schooldag {eerste['dag']}"
                  + (f" en {len(lijst) - 1} latere dag(en)" if len(lijst) > 1 else "") + ": vraag in de privé-agenda gezet")
        except Exception as e:  # noqa: BLE001
            melding_mislukt = True
            print(f"{tijd} gewiste Lara-afspraak op {eerste.get('dag')}: vraag niet gezet ({type(e).__name__}), blijft open",
                  file=sys.stderr)
    for sleutel, kandidaat in list(annuleringen.items()):
        if any(sleutel.startswith(k + ":") for k, n in W.KALENDERS.items() if n == "Lara"):
            annuleringen.pop(sleutel, None)        # een opgeslagen Lara-afzegging van voor FR-210: nooit meer bellen
            continue
        try:
            kandidaat["start"] = datetime.fromisoformat(kandidaat["start"])
            gemeld = meld_annulering(kandidaat, nu)
        except (TypeError, ValueError, KeyError):
            gemeld = False
        if gemeld:
            annuleringen.pop(sleutel, None)
        else:
            kandidaat["start"] = (kandidaat["start"].isoformat() if isinstance(kandidaat.get("start"), datetime)
                                  else kandidaat.get("start", ""))
            melding_mislukt = True

    if dagen:
        print(f"{tijd} {len(wat)} wijziging(en) op {len(dagen)} dag(en):")
        for r in sorted(set(wat))[:20]:
            print("  ", r)
    elif open_:
        print(f"{tijd} geen nieuwe wijziging, {len(open_)} open dag(en) opnieuw")
    else:
        print(tijd, "niets gewijzigd" + (f", maar {len(niet_gelezen)} agenda('s) niet gelezen" if niet_gelezen else ""))
    gefaald, geslaagd, bezet = {}, set(), {}
    for dag in sorted(dagen | set(open_)):
        if bezet:
            # het slot houdt een ronde van de wacht vast (tot 15 minuten): de overige dagen wachten op de volgende ronde,
            # anders wacht elke dag nog eens SLOT_WACHT seconden en loopt deze ronde over de volgende heen (A28)
            bezet[dag] = "niet gestart, het rondeslot was bezet"
            continue
        gelukt, uitleg = draai_wacht(dag)
        if gelukt:
            open_.pop(dag, None)
            geslaagd.add(dag)
            print(f"  wacht gedraaid voor {dag}: {uitleg}")
        elif gelukt is None:
            bezet[dag] = uitleg
        else:
            gefaald[dag] = uitleg

    opgegeven = list(st.get("opgegeven") or [])
    for dag, uitleg in sorted(gefaald.items()):
        o = dict(open_.get(dag) or {"pogingen": 0, "kalenders": []})
        o["pogingen"] += 1
        o.pop("bezet", None)           # de wacht liep echt: de reeks 'bezet na elkaar' is voorbij
        o["kalenders"] = sorted(set(o["kalenders"]) | {k for k, d in per_kal.items() if dag in d})
        o["fout"], o["laatst"] = uitleg[:200], nu.isoformat()
        if o["pogingen"] >= MAX_POGINGEN:
            open_.pop(dag, None)
            opgegeven.append(dict(o, dag=dag))
            print(f"{tijd} wacht MISLUKT voor {dag}, opgegeven na {o['pogingen']} pogingen: {uitleg}", file=sys.stderr)
        else:
            open_[dag] = o
            print(f"{tijd} wacht MISLUKT voor {dag} (poging {o['pogingen']} van {MAX_POGINGEN}, blijft open): {uitleg}",
                  file=sys.stderr)

    # Bezet is geen poging (A28): de dag blijft open en houdt de cursor van zijn agenda vast, de pogingen blijven staan.
    # Een eigen teller telt de rondes bezet na elkaar; vanaf BEZET_ALARM zeg ik het op stderr en eindigt het script niet 0.
    alarm = False
    for dag, uitleg in sorted(bezet.items()):
        o = dict(open_.get(dag) or {"pogingen": 0, "kalenders": []})
        o["bezet"] = o.get("bezet", 0) + 1
        o["kalenders"] = sorted(set(o["kalenders"]) | {k for k, d in per_kal.items() if dag in d})
        o["laatst"] = nu.isoformat()
        open_[dag] = o
        regel = (f"{tijd} wacht voor {dag} niet gestart, {uitleg}: blijft open, telt niet als poging "
                 f"({o['pogingen']} van {MAX_POGINGEN}), {o['bezet']} keer na elkaar bezet")
        if o["bezet"] >= BEZET_ALARM:
            alarm = True
            print(regel + "; het slot blijft te lang bezet, kijk na welke ronde het vasthoudt", file=sys.stderr)
        else:
            print(regel)

    # De cursor gaat alleen vooruit voor een agenda die volledig gelezen is en geen open dag meer heeft (A5)
    vast = {k for o in open_.values() for k in o["kalenders"]}
    for kal in per_kal:
        if kal not in vast:
            cursor[kal] = nu.isoformat()
    # Controlepunten: opgegeven dagen en onbekende annuleringen blijven staan tot ze beoordeeld zijn; een opgegeven dag
    # die later toch slaagt, is daarmee beoordeeld (resultaatcontrole), met het tijdstip erbij
    cp = controlepunten()
    for o in opgegeven[len(st.get("opgegeven") or []):]:
        cp["opgegeven"].append(dict(o, beoordeeld=""))
    for c in cp["opgegeven"]:
        if not c.get("beoordeeld") and c.get("dag") in geslaagd:
            c["beoordeeld"] = f"{nu.isoformat(timespec='minutes')}: de wacht slaagde later voor deze dag"
    gekend = {c["sleutel"] for c in cp["onbekend"]}
    for c in onbekend:
        if c["sleutel"] not in gekend:
            cp["onbekend"].append(dict(c, gezien=nu.isoformat(timespec="minutes"), beoordeeld=""))
            print(f"{tijd} annulering zonder bekende dag: {c['kalender'][:32]} {c['id'][:20]}; controlepunt", file=sys.stderr)
    if onbekend or len(opgegeven) > len(st.get("opgegeven") or []) or any(c.get("dag") in geslaagd for c in cp["opgegeven"]):
        controlepunten_bewaren(cp)
    grens = (nu - timedelta(days=2)).date().isoformat()
    vinger = {k: v for k, v in vinger.items() if v[1] >= grens}
    lara_gemeld = {k: d for k, d in lara_gemeld.items() if d >= grens}
    # een reeks blijft 60 dagen na haar laatste gewiste dag gekend: een latere wissing vult dezelfde vraag aan (hertest 2)
    lara_vraag = {r: v for r, v in lara_vraag.items()
                  if max(v.get("dagen") or [""]) >= (nu - timedelta(days=60)).date().isoformat()}
    bewaar({"gekeken": nu.isoformat(), "cursor": cursor, "laatste_dagen": sorted(dagen), "vinger": vinger,
            "open": open_, "opgegeven": opgegeven[-20:], "annulering_open": annuleringen,
            "lara_open": lara_open, "lara_gemeld": lara_gemeld, "lara_vraag": lara_vraag})
    return 1 if niet_gelezen or gefaald or alarm or melding_mislukt else 0


def main():
    tijd = f"{W.nu_lokaal():%d-%m %H:%M}"          # elke regel met zijn tijd (Brussel)
    slot = slot_nemen()
    if slot is None:
        print(tijd, "de vorige ronde loopt nog, deze slaat over")
        return 0
    try:
        return ronde(tijd)
    finally:
        slot.close()


if __name__ == "__main__":
    # cron start dit om de 12 minuten, de klok rond; ik kijk van 06:00 tot 23:59 Brusselse
    # tijd. Mehdi verzet ook 's avonds laat nog afspraken. Gezien 24-09-2026: op UTC liep het
    # van 08:00 tot 23:59 en miste het de vroege ochtend.
    if "--ronde" in sys.argv and not W.binnen_uren(6, 23):
        sys.exit(0)
    sys.exit(main())
