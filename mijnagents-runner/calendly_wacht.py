#!/usr/bin/env python3
"""De Calendlywacht (Privé): bewaakt de boekingskanalen van Mehdi in Calendly.

Werkt met één sleutel van de eigenaar (CALENDLY_TOKEN_MCH): daarmee leest hij de
hele organisatie, alle leden en al hun event types. Ontbreekt die, dan valt hij
terug op losse sleutels per account.

Meldt: dode types, dezelfde typenaam op meerdere accounts, types die het
agenda-document niet kent, boekingen zonder afspraak in de agenda's van De
Agendawacht (met haar archief, twee weken terug tot twee weken vooruit), en
annuleringen die nog in de toekomst liggen. Schrijft nooit in Calendly.

Draaien: calendly_wacht.py [--dagen 90]
"""
import collections
import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from koppelingen import bord  # noqa: E402

NAAM = "calendly-wacht"
API = "https://api.calendly.com"
DOOD_NA_DAGEN = 90
VOORUIT_DAGEN = 14
# T-0120 CL-2: ook een boeking van de voorbije twee weken zonder afspraak is een melding (de meting keek alleen vooruit),
# en die melding is een vaste nood voor Mehdi, geen los signaal. Geen aantal of datum in de tekst (N10); het detail
# staat in het signaal.
TERUG_DAGEN = 14
ZONDER_NOOD = "Calendly-boeking zonder afspraak in de agenda"
# De server draait in UTC; de agenda van Mehdi is altijd Brusselse tijd.
BRUSSEL = ZoneInfo("Europe/Brussels")

# Welke Google-agenda een account beschrijft, gemeten 19-09-2026. Leeg = nog niet
# vastgesteld. Dit is alleen voor het verslag; ik leid er niets uit af.
AGENDA_VAN = {
    "General": "mehdi werk agenda (mehdiprivewerkagenda@gmail.com), gezet 20-09-2026",
    "H-Architects Projects": "HA Light",
    "UNABO Afspraken": "UNABO (krijgt niets uit Calendly)",
    "Mehdi Chegini": "mehdiprivewerkagenda",
}

# Types die Mehdi bewust openhoudt hoewel ze niet geboekt worden: een firma zonder
# boekingslink is erger dan een link die stilligt. Beslist 20-09-2026.
BEWUST_LEEG = {
    "Contrax - Prospect", "TKN: Klant", "UNABO prospect - Permits",
    "EE: Energy", "Harmoniebouw: Prospect", "HA: Advies (Prospect)",
    "UNABO prospect - Plaatsbeschrijving", "UNABO prospect - Veiligheidscoörd.",
    "Bespreking", "H-Architects: Klant",
}

# De types die het agenda-document kent, met de naam zoals ze in Calendly heten: de vaste lijst in
# werkwijze/agenda-taken.json (calendly_types.bekend). Tot 01-11-2026 stond hier een kopie met de negen types van
# tabel J, en meldde ik elke dag de vijf drukste kanalen als onbekend (T-0120 CL-3).
AGENDA_TAKEN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "werkwijze", "agenda-taken.json")


def bekende_types():
    """De set bekende typenamen uit agenda-taken.json, of None als die lijst niet te lezen is. None is onbekend, niet
    leeg: dan sla ik de controle over en meld ik dat, in plaats van elk type als onbekend te melden."""
    try:
        lijst = (json.load(open(AGENDA_TAKEN, encoding="utf-8")).get("calendly_types") or {}).get("bekend")
    except (OSError, ValueError):
        return None
    return {x for x in lijst if isinstance(x, str)} if isinstance(lijst, list) and lijst else None


def dubbele_types(accounts):
    """naam -> accountnamen, voor een typenaam die actief op twee of meer verschillende accounts staat (T-0120 CL-3).
    Een inactief type telt niet, en dezelfde naam twee keer in hetzelfde account is geen dubbel over accounts: tot
    01-11-2026 kwam zo elke dag 'New Meeting' (twee inactieve types in een account) als dubbel binnen."""
    waar = collections.defaultdict(dict)
    for a in accounts:
        for t in a.get("types") or []:
            if t.get("active"):
                waar[t.get("name") or ""][a.get("uri") or a.get("naam")] = a.get("naam") or "?"
    return {nm: sorted(w.values()) for nm, w in waar.items() if len(w) > 1}


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


def vaste_duur():
    """De duur die Mehdi per firma vastlegde, uit werkwijze/agenda-taken.json (calendly_duur). Mehdi, 02-10-2026: TKN-Buro
    en UNABO voorzien allebei een halfuur, 'zodat het voor mij en de klant allemaal conform is'."""
    try:
        pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "werkwijze", "agenda-taken.json")
        return (json.load(open(pad, encoding="utf-8")).get("calendly_duur") or {}).get("per_firma") or {}
    except (OSError, ValueError):
        return {}


def duur_afwijkend(types, duur=None):
    """['naam (20 min, moet 30)'] voor actieve types van een firma met een vaste duur. De firma herken ik aan elke
    schrijfwijze vooraan de naam (TKN, TK, TKNB / UNABO, UB, UNAB), zodat een hernoeming naar de codes van twee letters
    de controle niet stil uitzet (v1.1 p. 9)."""
    duur = vaste_duur() if duur is None else duur
    alias = firma_aliassen()
    uit = []
    for t in types:
        nm = (t.get("name") or "").strip()
        for firma, minuten in duur.items():
            namen = alias.get(firma, [firma])
            if t.get("active") and any(re.match(rf"\s*\[?{re.escape(a)}\b", nm, re.I) for a in namen) \
                    and t.get("duration") != minuten:
                uit.append(f"{nm} ({t.get('duration')} min, moet {minuten})")
    return uit


def firma_aliassen():
    """firma -> alle schrijfwijzen vooraan een Calendly-naam, uit agenda-taken.json (calendly_duur.aliassen)."""
    try:
        pad = os.path.join(os.path.dirname(os.path.abspath(__file__)), "werkwijze", "agenda-taken.json")
        return (json.load(open(pad, encoding="utf-8")).get("calendly_duur") or {}).get("aliassen") or {}
    except (OSError, ValueError):
        return {}


def agenda_bewijs(van_dagen, tot_dagen):
    """Per starttijd (Brussel, tot op de minuut) de afspraken in precies de agenda's van De Agendawacht, met haar
    archiefagenda's, als {'id', 'calendly'}; en de agenda's die niet gelezen werden (T-0120 CL-2; tot 01-11-2026 las ik er
    maar drie). calendly: de afspraak draagt een kenmerk van Calendly (agenda_wacht.is_calendly: een boekingsaccount of
    de links van calendly.com in de omschrijving). Alleen lezen. Een privé-agenda heet hier 'een privé-agenda'."""
    import agenda_wacht as W  # noqa: PLC0415  pas hier: het laden van De Agendawacht leest organisatie.globaal.be
    ruw = W.afspraken(van_dagen, tot_dagen, alleen_lezen=True)
    archief = W.archief_afspraken(van_dagen, tot_dagen, alleen_lezen=True)
    ongelezen = {"een privé-agenda" if x.get("kalender") in W.PRIVE_KALENDERS else W.KALENDERS.get(x.get("kalender"), "een agenda")
                 for x in ruw if x.get("fout")}
    if W.ARCHIEF_FOUT:
        ongelezen.add("archief")
    bewijs = collections.defaultdict(list)
    for x in ruw + archief:
        if not x.get("fout"):
            bewijs[(x.get("start") or "")[:16]].append({"id": x.get("id") or "", "calendly": bool(W.is_calendly(x))})
    return dict(bewijs), sorted(ongelezen)


def zonder_afspraak(boekingen, bewijs, nu, terug=TERUG_DAGEN, vooruit=VOORUIT_DAGEN):
    """De actieve boekingen van terug dagen geleden tot vooruit dagen verder zonder hun eigen afspraak, als
    'JJJJ-MM-DD UU:MM type'. Een eigen afspraak staat op het geboekte uur en is de afspraak die Calendly in Google zette
    (calendar_event.external_id) of draagt een kenmerk van Calendly. Een andere afspraak op hetzelfde uur is geen bewijs
    (Codex-toets 2): dan zegt de regel dat erbij. bewijs: uit agenda_bewijs."""
    uit = []
    for b in boekingen:
        if b.get("status") != "active" or not b.get("start_time"):
            continue
        lok = datetime.datetime.fromisoformat(b["start_time"].replace("Z", "+00:00")).astimezone(BRUSSEL)
        if lok < nu - datetime.timedelta(days=terug) or lok > nu + datetime.timedelta(days=vooruit):
            continue
        eigen = (b.get("calendar_event") or {}).get("external_id") or ""
        op_uur = bewijs.get(lok.strftime("%Y-%m-%dT%H:%M"), [])
        if not any(x["calendly"] or (eigen and x["id"] == eigen) for x in op_uur):
            uit.append(f"{lok:%Y-%m-%d %H:%M} {b.get('name')}"
                       + (" (op dat uur een andere afspraak, zonder kenmerk van Calendly)" if op_uur else ""))
    return sorted(uit)


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

    regels = []
    bekend = bekende_types()
    if bekend is None:
        noden.append({"tekst": "lijst bekende Calendly-types in werkwijze/agenda-taken.json niet te lezen", "wie": "claude-code"})
    for a in accounts:
        t_tel = tel[a["uri"]] if a["uri"] in tel else tel[None]
        dood = []
        for t in a["types"]:
            nm = t.get("name") or ""
            if not t.get("active"):
                continue
            if t_tel[nm] == 0 and nm not in BEWUST_LEEG:
                dood.append(f"{nm} ({t.get('duration')} min)")
            if bekend is not None and nm not in bekend and nm not in BEWUST_LEEG:
                signalen.append(f"{a['naam']}: type '{nm}' staat niet in het agenda-document")
        for afw in duur_afwijkend(a["types"]):
            signalen.append(f"{a['naam']}: duur wijkt af van de afspraak: {afw}")
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

    for nm, waar in sorted(dubbele_types(accounts).items()):
        signalen.append(f"type '{nm}' staat op meerdere accounts ({', '.join(waar)}): "
                        "boekingen komen dan op verschillende agenda's")

    # Een mislukte of onvolledige lezing is onbekend, niet leeg: dan vergelijk ik niet (geen vals alarm) en meld ik de
    # lezing aan Claude.
    zonder = []
    try:
        bewijs, ongelezen = agenda_bewijs(-TERUG_DAGEN - 1, VOORUIT_DAGEN + 1)
    except Exception as e:  # noqa: BLE001
        noden.append({"tekst": f"agendacontrole mislukt ({type(e).__name__}): boekingen zonder afspraak niet nagekeken",
                      "wie": "claude-code"})
    else:
        if ongelezen:
            noden.append({"tekst": "agendacontrole onvolledig, niet gelezen: " + ", ".join(ongelezen)
                                   + "; boekingen zonder afspraak niet nagekeken", "wie": "claude-code"})
        else:
            zonder = zonder_afspraak(boekingen, bewijs, nu_b)
    if zonder:
        signalen.append(f"{len(zonder)} boeking(en) zonder afspraak in de agenda's van De Agendawacht: " + "; ".join(zonder[:8]))
        noden.append({"tekst": ZONDER_NOOD, "wie": "mehdi"})

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
