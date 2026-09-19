#!/usr/bin/env python3
"""De Calendlywacht (Privé): bewaakt de boekingskanalen van Mehdi in Calendly.

Werkt met één sleutel van de eigenaar (CALENDLY_TOKEN_MCH): daarmee leest hij de
hele organisatie, alle leden en al hun event types. Ontbreekt die, dan valt hij
terug op losse sleutels per account.

Meldt: dode types, dezelfde typenaam op meerdere accounts, types die het
agenda-document niet kent, boekingen zonder afspraak in de negen agenda's, en
annuleringen die nog in de toekomst liggen. Schrijft nooit in Calendly.

Draaien: calendly_wacht.py [--dagen 90]
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

# Welke Google-agenda een account beschrijft, gemeten 19-09-2026. Leeg = nog niet
# vastgesteld. Dit is alleen voor het verslag; ik leid er niets uit af.
AGENDA_VAN = {
    "General": "zoomafspraken, wordt mehdiprivewerkagenda",
    "H-Architects Projects": "HA Light",
    "UNABO Afspraken": "UNABO (krijgt niets uit Calendly)",
    "Mehdi Chegini": "mehdiprivewerkagenda",
}

# De negen types uit tabel J van het agenda-document, met de naam zoals ze in
# Calendly heten. Alles daarbuiten meld ik als "kent het document niet".
DOCUMENT_TYPES = {
    "HA: Klant", "HA: Advies (Prospect)", "HA: Prospect (Kennismaking)",
    "UNABO: Klant", "UNABO: Offerte", "Harmoniebouw: Prospect",
    "EE: Energy", "Contrax: Klant", "Intern Overleg",
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
        return {"_fout": str(e.code)}
    except Exception as e:  # noqa: BLE001
        return {"_fout": str(e)[:80]}


def alles(token, pad):
    uit = []
    while pad:
        d = api(token, pad)
        if "collection" not in d:
            return uit, d.get("_fout") or str(d)[:80]
        uit.extend(d["collection"])
        pad = (d.get("pagination") or {}).get("next_page")
    return uit, None


def q(u):
    return urllib.parse.quote(u, safe="")


def verzamel(noden):
    """Geeft (accounts, boekingen_per_user) terug. Accounts: lijst dicts met
    naam, email, rol, uri, types."""
    # Sinds 19-09-2026 is General de eigenaar van de organisatie; zijn sleutel leest alles.
    token = env("CALENDLY_TOKEN_GENERAL") or env("CALENDLY_TOKEN_MCH")
    nu = datetime.datetime.now(datetime.timezone.utc)
    van = (nu - datetime.timedelta(days=DOOD_NA_DAGEN)).strftime("%Y-%m-%dT%H:%M:%S.000000Z")
    accounts, boekingen = [], []

    if token:
        ik = api(token, "/users/me").get("resource") or {}
        org = ik.get("current_organization")
        if org:
            leden, fout = alles(token, f"/organization_memberships?organization={q(org)}&count=100")
            if fout:
                noden.append({"tekst": f"organisatie niet leesbaar ({fout}); is CALENDLY_TOKEN_MCH nog geldig?",
                              "wie": "mehdi"})
            boekingen, _ = alles(token, f"/scheduled_events?organization={q(org)}&min_start_time={van}&count=100")
            for m in leden:
                u = m.get("user") or {}
                types, f2 = alles(token, f"/event_types?user={q(u.get('uri',''))}&count=100")
                if f2:
                    noden.append({"tekst": f"types van {u.get('name')} niet leesbaar ({f2})", "wie": "claude-code"})
                accounts.append({"naam": u.get("name") or "?", "email": u.get("email") or "",
                                 "rol": m.get("role") or "", "uri": u.get("uri") or "", "types": types})
            return accounts, boekingen
        noden.append({"tekst": "CALENDLY_TOKEN_GENERAL werkt niet meer; nieuwe sleutel nodig", "wie": "mehdi"})

    # terugval: losse sleutels per account
    for sl in ("GENERAL",):
        t = env("CALENDLY_TOKEN_" + sl)
        if not t:
            noden.append({"tekst": f"geen sleutel voor {sl} en geen eigenaarssleutel", "wie": "mehdi"})
            continue
        ik = api(t, "/users/me").get("resource") or {}
        if not ik.get("uri"):
            noden.append({"tekst": f"sleutel {sl} werkt niet", "wie": "mehdi"})
            continue
        types, _ = alles(t, f"/event_types?user={q(ik['uri'])}&count=100")
        b, _ = alles(t, f"/scheduled_events?user={q(ik['uri'])}&min_start_time={van}&count=100")
        boekingen.extend(b)
        accounts.append({"naam": ik.get("name") or sl, "email": ik.get("email") or "", "rol": "",
                         "uri": ik["uri"], "types": types})
    return accounts, boekingen


def main():
    ag = bord.Agent(NAAM)
    vandaag = datetime.datetime.now(BRUSSEL).date().isoformat()
    ag.hartslag("actief", "Calendly nakijken")
    noden, signalen, voorstellen = [], [], []

    accounts, boekingen = verzamel(noden)
    if not accounts:
        ag.log(f"dag {vandaag}", "bron", "geen enkel Calendly-account leesbaar")
        ag.log_verstuur()
        ag.hartslag("fout", "geen sleutel", "Ik kan niets meten.", nood=noden)
        return

    # boekingen toewijzen aan de accounts
    tel = collections.defaultdict(collections.Counter)
    laatste = collections.defaultdict(dict)
    geannuleerd = collections.defaultdict(list)
    nu_b = datetime.datetime.now(BRUSSEL)
    for b in boekingen:
        nm = b.get("name") or "?"
        st = b.get("start_time") or ""
        users = [m.get("user") for m in (b.get("event_memberships") or [])] or [None]
        for u in users:
            if b.get("status") == "active":
                tel[u][nm] += 1
                if st[:10] > laatste[u].get(nm, ""):
                    laatste[u][nm] = st[:10]
            elif b.get("status") == "canceled" and st:
                lok = datetime.datetime.fromisoformat(st.replace("Z", "+00:00")).astimezone(BRUSSEL)
                if lok > nu_b:
                    geannuleerd[u].append(f"{lok:%Y-%m-%d %H:%M} {nm}")

    namen = collections.defaultdict(list)
    regels = []
    for a in accounts:
        t_tel = tel[a["uri"]] if a["uri"] in tel else tel[None]
        dood = []
        for t in a["types"]:
            nm = t.get("name") or ""
            namen[nm].append(a["naam"])
            if not t.get("active"):
                continue
            if t_tel[nm] == 0:
                dood.append(f"{nm} ({t.get('duration')} min)")
            if nm not in DOCUMENT_TYPES:
                signalen.append(f"{a['naam']}: type '{nm}' staat niet in het agenda-document")
        doel = AGENDA_VAN.get(a["naam"], "")
        regels.append(f"{a['naam']}: {len(a['types'])} types, {sum(t_tel.values())} boekingen, "
                      f"{len(dood)} dood" + (f", schrijft naar {doel}" if doel else ""))
        if dood:
            voorstellen.append(f"{a['naam']}: " + ", ".join(sorted(dood)))
        if geannuleerd.get(a["uri"]):
            signalen.append(f"{a['naam']}: geannuleerde boeking nog in de toekomst: "
                            + "; ".join(geannuleerd[a["uri"]][:5]))
        ag.log(f"dag {vandaag}", "bron", f"{a['naam']} <{a['email']}>: {len(a['types'])} types, "
                                         f"{sum(t_tel.values())} boekingen",
               "\n".join(f"{t_tel[t.get('name','')]:>4}x  {laatste[a['uri']].get(t.get('name',''),'nooit'):<11} "
                         f"{t.get('duration')}m  {t.get('name')}" + ("" if t.get("active") else "  (inactief)")
                         for t in sorted(a["types"], key=lambda x: -t_tel[x.get("name", "")])))

    for nm, waar in namen.items():
        if len(waar) > 1:
            signalen.append(f"type '{nm}' staat op meerdere accounts ({', '.join(waar)}): "
                            "boekingen komen dan op verschillende agenda's")

    zonder = []
    if google_agenda is not None:
        try:
            afspraken = google_agenda.afspraken(van_dagen=0, tot_dagen=VOORUIT_DAGEN)
            starts = {(x.get("start") or "")[:16] for x in afspraken}
            for b in boekingen:
                if b.get("status") != "active" or not b.get("start_time"):
                    continue
                lok = datetime.datetime.fromisoformat(b["start_time"].replace("Z", "+00:00")).astimezone(BRUSSEL)
                if lok < nu_b or lok > nu_b + datetime.timedelta(days=VOORUIT_DAGEN):
                    continue
                if lok.strftime("%Y-%m-%dT%H:%M") not in starts:
                    zonder.append(f"{lok:%Y-%m-%d %H:%M} {b.get('name')}")
        except Exception as e:  # noqa: BLE001
            noden.append({"tekst": f"agendacontrole mislukt: {str(e)[:60]}", "wie": "claude-code"})
    if zonder:
        signalen.append(f"{len(zonder)} boeking(en) zonder afspraak in de negen agenda's: " + "; ".join(zonder[:8]))

    ag.log(f"dag {vandaag}", "bron", "; ".join(regels))
    if signalen:
        ag.log(f"dag {vandaag}", "bevinding", f"{len(signalen)} signalen", "\n".join(signalen))
    if voorstellen:
        ag.log(f"dag {vandaag}", "bevinding", "types zonder boeking", "\n".join(voorstellen))
    if signalen:
        ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": vandaag,
                      "titel": f"Calendly: {len(signalen)} signalen",
                      "inhoud": "\n".join(signalen), "uniek": f"calendly:{vandaag}"}])
    ag.log_verstuur()

    voorstel = None
    if voorstellen:
        voorstel = {"titel": "Calendly: types zonder boekingen uitzetten",
                    "toelichting": "\n".join(voorstellen)
                                   + "\n\nUitzetten is omkeerbaar en ik doe het niet zelf."}
    ag.hartslag("klaar", f"{len(accounts)} accounts nagekeken", "; ".join(regels),
                voorstel=voorstel, nood=noden)


if __name__ == "__main__":
    main()
