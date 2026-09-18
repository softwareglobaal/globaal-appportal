#!/usr/bin/env python3
"""De Calendlywacht (Privé): bewaakt de boekingskanalen van Mehdi in Calendly.

Leest per account (eigen token) de event types en de boekingen, en meldt:
dode types, dubbele types over accounts heen, types die het agenda-document niet
kent, boekingen zonder agenda-item, en annuleringen. Schrijft nooit in Calendly.

Sleutels: CALENDLY_TOKEN_<NAAM> in mijnagents-data/.env, nooit in deze code.
Draaien: calendly_wacht.py [--dagen 90] [--stil]
"""
import collections
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from koppelingen import bord  # noqa: E402

try:
    from koppelingen import agenda as google_agenda
except Exception:  # noqa: BLE001
    google_agenda = None

NAAM = "calendly-wacht"
API = "https://api.calendly.com"
DOOD_NA_DAGEN = 90
VOORUIT_DAGEN = 14
# De server draait in UTC; de agenda van Mehdi is altijd Brusselse tijd.
BRUSSEL = ZoneInfo("Europe/Brussels")

# De accounts zoals Mehdi ze kent. De sleutelnaam is de achtervoegsel van
# CALENDLY_TOKEN_<NAAM> in het .env. "agenda" is de Google-agenda waar dit
# account volgens de meting naar schrijft; leeg betekent nog niet vastgesteld.
ACCOUNTS = [
    {"sleutel": "GENERAL", "label": "General (prospecten)", "agenda": "zoomafspraken"},
    {"sleutel": "LIGHT", "label": "H-Architects Projects", "agenda": "HA Light"},
    {"sleutel": "UNABO", "label": "UNABO Afspraken", "agenda": "UNABO"},
    {"sleutel": "MCH", "label": "Mehdi Chegini (eigenaar)", "agenda": ""},
]

# De negen types uit het agenda-document (tabel J). Alles daarbuiten meld ik
# als "kent het document niet". De namen zijn zoals ze in Calendly staan, met
# tussen haakjes de naam in het document als die afwijkt.
DOCUMENT_TYPES = {
    "HA: Klant",                        # document: HA: Standaard Projects
    "HA: Advies (Prospect)",            # document: HA: Advies
    "HA: Prospect (Kennismaking)",      # document: HA: Prospect
    "UNABO: Klant",                     # document: UNABO: Klant afspraak
    "UNABO: Offerte",                   # document: UNABO: Offertebespreking
    "Harmoniebouw: Prospect",           # document: Harmoniebouw: Afspraak
    "EE: Energy",                       # document: Energie: Afspraak
    "Contrax: Klant",                   # document: Contrax: Afspraak
}


def env(sleutel):
    pad = os.path.expanduser("~/appportal/mijnagents-data/.env")
    try:
        for regel in open(pad):
            if regel.startswith(sleutel + "="):
                return regel.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        pass
    return os.environ.get(sleutel, "")


def api(token, pad):
    # Zonder eigen User-Agent antwoordt Calendly 403 op urllib (gemeten 19-09-2026).
    req = urllib.request.Request(pad if pad.startswith("http") else API + pad,
                                 headers={"Authorization": f"Bearer {token}",
                                          "Accept": "application/json",
                                          "User-Agent": "MehdiAgents-Calendlywacht/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return {"_fout": f"{e.code}"}
    except Exception as e:  # noqa: BLE001
        return {"_fout": str(e)[:80]}


def alles(token, pad):
    uit = []
    while pad:
        d = api(token, pad)
        if "_fout" in d:
            return uit, d["_fout"]
        uit.extend(d.get("collection", []))
        pad = (d.get("pagination") or {}).get("next_page")
    return uit, None


def meet_account(acc):
    """Haalt types en boekingen op. Geeft een dict terug, of een reden waarom niet."""
    token = env("CALENDLY_TOKEN_" + acc["sleutel"])
    if not token:
        return {"reden": "geen sleutel"}
    ik = api(token, "/users/me").get("resource") or {}
    if not ik.get("uri"):
        return {"reden": "sleutel werkt niet"}
    u = urllib.parse.quote(ik["uri"], safe="")
    types, fout = alles(token, f"/event_types?user={u}&count=100")
    if fout:
        return {"reden": f"types niet leesbaar ({fout})"}
    nu = datetime.datetime.now(datetime.timezone.utc)
    van = (nu - datetime.timedelta(days=DOOD_NA_DAGEN)).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    tot = (nu + datetime.timedelta(days=VOORUIT_DAGEN)).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    boekingen, _ = alles(token, f"/scheduled_events?user={u}&min_start_time={van}&max_start_time={tot}&count=100")
    return {"ik": ik, "types": types, "boekingen": boekingen}


def main():
    dagen = DOOD_NA_DAGEN
    for i, a in enumerate(sys.argv):
        if a == "--dagen" and i + 1 < len(sys.argv):
            dagen = int(sys.argv[i + 1])
    ag = bord.Agent(NAAM)
    vandaag = datetime.date.today().isoformat()
    ag.hartslag("actief", "Calendly nakijken")

    gemeten, noden, signalen, voorstellen = {}, [], [], []
    for acc in ACCOUNTS:
        r = meet_account(acc)
        if "reden" in r:
            noden.append({"tekst": f"{acc['label']}: {r['reden']} (CALENDLY_TOKEN_{acc['sleutel']} in mijnagents-data/.env)",
                          "wie": "mehdi"})
            continue
        gemeten[acc["label"]] = (acc, r)

    if not gemeten:
        ag.log(f"dag {vandaag}", "bron", "geen enkel Calendly-account leesbaar")
        ag.log_verstuur()
        ag.hartslag("fout", "geen sleutels", "Ik kan niets meten zonder token.", nood=noden)
        return

    # 1. per account: types, boekingen, dode types
    alle_types = collections.defaultdict(list)   # naam -> [accountlabel]
    regels = []
    for label, (acc, r) in gemeten.items():
        tel = collections.Counter()
        laatste = {}
        geannuleerd = []
        for b in r["boekingen"]:
            nm = b.get("name") or "?"
            if b.get("status") == "active":
                tel[nm] += 1
                laatste[nm] = max(laatste.get(nm, ""), (b.get("start_time") or "")[:10])
            elif b.get("status") == "canceled" and (b.get("start_time") or "") >= datetime.datetime.now(BRUSSEL).date().isoformat():
                geannuleerd.append(f"{(b.get('start_time') or '')[:16]} {nm}")
        dood = []
        for t in r["types"]:
            nm = t.get("name") or ""
            alle_types[nm].append(label)
            if t.get("active") and tel[nm] == 0:
                dood.append(f"{nm} ({t.get('duration')} min)")
            if t.get("active") and nm not in DOCUMENT_TYPES:
                signalen.append(f"{label}: type '{nm}' staat niet in het agenda-document")
        regels.append(f"{label}: {len(r['types'])} types, {sum(tel.values())} boekingen, "
                      f"{len(dood)} zonder boeking in {dagen} dagen"
                      + (f"; schrijft naar {acc['agenda']}" if acc["agenda"] else ""))
        if dood:
            voorstellen.append(f"{label}: uitzetten voorstellen: " + ", ".join(sorted(dood)))
        if geannuleerd:
            signalen.append(f"{label}: geannuleerde boeking nog in de toekomst: " + "; ".join(geannuleerd[:5]))
        ag.log(f"dag {vandaag}", "bron", f"{label}: {len(r['types'])} types, {sum(tel.values())} boekingen",
               "\n".join(f"{tel[t.get('name','')]:>4}x  {laatste.get(t.get('name',''),'nooit'):<11} "
                         f"{t.get('duration')}m  {t.get('name')}" + ("" if t.get("active") else "  (inactief)")
                         for t in sorted(r["types"], key=lambda x: -tel[x.get("name", "")])))

    # 2. dubbele types over accounts heen
    for nm, waar in alle_types.items():
        if len(waar) > 1:
            signalen.append(f"type '{nm}' bestaat op meerdere accounts ({', '.join(waar)}): "
                            f"boekingen komen dan op verschillende agenda's")

    # 3. boeking zonder agenda-item
    zonder = []
    if google_agenda is not None:
        try:
            afspraken = google_agenda.afspraken(van_dagen=0, tot_dagen=VOORUIT_DAGEN)
            starts = {(a.get("start") or "")[:16] for a in afspraken}
            for label, (_acc, r) in gemeten.items():
                for b in r["boekingen"]:
                    if b.get("status") != "active":
                        continue
                    st = (b.get("start_time") or "")
                    if not st:
                        continue
                    lokaal = datetime.datetime.fromisoformat(st.replace("Z", "+00:00")).astimezone(BRUSSEL)
                    if lokaal < datetime.datetime.now(BRUSSEL):
                        continue
                    if lokaal.strftime("%Y-%m-%dT%H:%M") not in starts:
                        zonder.append(f"{lokaal:%Y-%m-%d %H:%M} {b.get('name')} ({label})")
        except Exception as e:  # noqa: BLE001
            noden.append({"tekst": f"agendacontrole mislukt: {str(e)[:60]}", "wie": "claude-code"})
    if zonder:
        signalen.append(f"{len(zonder)} boeking(en) zonder afspraak in de agenda: " + "; ".join(zonder[:5]))

    ag.log(f"dag {vandaag}", "bron", "; ".join(regels))
    if signalen:
        ag.log(f"dag {vandaag}", "bevinding", f"{len(signalen)} signalen", "\n".join(signalen))
    if voorstellen:
        ag.log(f"dag {vandaag}", "bevinding", "voorstellen om uit te zetten", "\n".join(voorstellen))
    ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                  "titel": f"Calendly: {len(signalen)} signalen",
                  "inhoud": "\n".join(signalen), "uniek": f"calendly:{vandaag}"}] if signalen else [])
    ag.log_verstuur()

    voorstel = None
    if voorstellen:
        voorstel = {"titel": "Calendly: types zonder boekingen uitzetten",
                    "toelichting": "\n".join(voorstellen) + "\n\nUitzetten is omkeerbaar. Ik doe het niet zelf: "
                                   "zeg ja tegen Claude Code of doe het in Calendly."}
    ag.hartslag("klaar", f"{len(gemeten)} account(s) nagekeken",
                "; ".join(regels), voorstel=voorstel, nood=noden)


if __name__ == "__main__":
    main()
