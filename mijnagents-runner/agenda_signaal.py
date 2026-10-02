#!/usr/bin/env python3
"""Kijkt of er iets aan de agenda veranderd is en zet de Agendawacht dan meteen aan.

De wacht draait 's ochtends, maar een afspraak die om elf uur verplaatst wordt mag geen
dag wachten op zijn reistijd, kleur en melding. Dit script vraagt elke keer welke
afspraken er sinds de vorige keer gewijzigd zijn, en start de wacht voor de dagen die
het betreft. Verandert er niets, dan doet het niets en kost het niets.

Afvinken gebeurt pas achteraf (audit 02-10-2026, A5): per agenda een cursor die pas vooruitgaat
als die agenda volledig gelezen is en elke getroffen dag verwerkt. Een dag waarvoor de wacht
faalt, blijft open in de stand en komt de volgende ronde terug, tot MAX_POGINGEN keer.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/agenda_signaal.py
"""
import fcntl
import http.client
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
from koppelingen import agenda as A           # noqa: E402

STAND = Path.home() / "appportal/mijnagents-data/agenda-signaal.json"
PYTHON = str(Path.home() / "agents/.venv/bin/python")
# Een dag waarvoor de wacht faalt, probeer ik zo vaak (een poging per ronde van 12 minuten). Daarna geef ik
# hem luid op, anders houdt een kapotte dag de cursor van zijn agenda eeuwig vast (audit 02-10-2026, A5).
MAX_POGINGEN = 5
# nextPageToken moet in de velden staan, anders laat Google het weg en lijkt de eerste pagina alles (A4).
# originalStartTime geeft de dag waar een reeksinstantie oorspronkelijk stond (A7, A8).
VELDEN = ("nextPageToken,items(id,summary,status,updated,start/dateTime,start/date,end/dateTime,end/date,"
          "originalStartTime/dateTime,originalStartTime/date,location,attendees/email)")


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
                       sorted((g.get("email") or "") for g in ev.get("attendees") or [])], ensure_ascii=False)


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


def te_verwerken(kal, items, oud, vinger, vanaf=""):
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
            continue
        vp = vingerafdruk(ev)
        vinger[sleutel] = [vp, dag]
        if (vorig or [None])[0] == vp:
            continue
        dagen |= {d for d in vroeger if d >= vanaf} | ({s} if s else set())
        was = sorted(d for d in vroeger if d != dag)
        titel = ev.get("summary") or _oude_titel(vorig) or "(zonder titel)"
        wat.append(f"{dag} {ev.get('status','')[:9]:<9} {titel[:52]}" + (f" (was {', '.join(was)})" if was else ""))
    return dagen, wat


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
    een gecrashte wacht stond in het logboek als 'wacht gedraaid'."""
    try:
        r = subprocess.run([PYTHON, str(HIER / "agenda_wacht.py"), "--dag", dag],
                           capture_output=True, text=True, timeout=900)
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"{type(e).__name__}: {str(e)[:150]}"
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
    dagen, wat, niet_gelezen, per_kal = set(), [], [], {}
    oud = st.get("vinger") or {}
    vinger = dict(oud)
    for kal in kals:
        try:
            items = lees_wijzigingen(kal, cursor[kal], nu, kop)
        except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as e:
            print(f"{tijd} {kal[:32]}: {_leesfout(e)}, deze agenda telt deze ronde niet", file=sys.stderr)
            niet_gelezen.append(kal)
            continue
        per_kal[kal], w_ = te_verwerken(kal, items, oud, vinger, vanaf)
        dagen |= per_kal[kal]
        wat += w_

    if dagen:
        print(f"{tijd} {len(wat)} wijziging(en) op {len(dagen)} dag(en):")
        for r in sorted(set(wat))[:20]:
            print("  ", r)
    elif open_:
        print(f"{tijd} geen nieuwe wijziging, {len(open_)} open dag(en) opnieuw")
    else:
        print(tijd, "niets gewijzigd" + (f", maar {len(niet_gelezen)} agenda('s) niet gelezen" if niet_gelezen else ""))
    gefaald = {}
    for dag in sorted(dagen | set(open_)):
        gelukt, uitleg = draai_wacht(dag)
        if gelukt:
            open_.pop(dag, None)
            print(f"  wacht gedraaid voor {dag}: {uitleg}")
        else:
            gefaald[dag] = uitleg

    opgegeven = list(st.get("opgegeven") or [])
    for dag, uitleg in sorted(gefaald.items()):
        o = dict(open_.get(dag) or {"pogingen": 0, "kalenders": []})
        o["pogingen"] += 1
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

    # De cursor gaat alleen vooruit voor een agenda die volledig gelezen is en geen open dag meer heeft (A5)
    vast = {k for o in open_.values() for k in o["kalenders"]}
    for kal in per_kal:
        if kal not in vast:
            cursor[kal] = nu.isoformat()
    grens = (nu - timedelta(days=2)).date().isoformat()
    vinger = {k: v for k, v in vinger.items() if v[1] >= grens}
    bewaar({"gekeken": nu.isoformat(), "cursor": cursor, "laatste_dagen": sorted(dagen), "vinger": vinger,
            "open": open_, "opgegeven": opgegeven[-20:]})
    return 1 if niet_gelezen or gefaald else 0


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
