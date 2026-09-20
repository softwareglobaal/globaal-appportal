#!/usr/bin/env python3
"""Controle van de agenda-opstelling van Mehdi. Leest alleen, verandert niets.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/controle_agenda.py
Elke regel is een toets met een uitkomst: GOED, LET OP of FOUT.
"""
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HIER = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
from koppelingen import agenda as A           # noqa: E402

goed = letop = fout = 0


def toets(naam, stand, tekst=""):
    global goed, letop, fout
    if stand == "GOED":
        goed += 1
    elif stand == "LET OP":
        letop += 1
    else:
        fout += 1
    print(f"  {stand:<7} {naam}" + (f" | {tekst}" if tekst else ""))


H = {"Authorization": "Bearer " + A._toegang()}


def g(pad, **q):
    return json.load(urllib.request.urlopen(urllib.request.Request(
        A.API + pad + ("?" + urllib.parse.urlencode(q) if q else ""), headers=H), timeout=60))


print("\n1. HET ACCOUNT VAN DE AGENT")
lijst = g("/users/me/calendarList", maxResults=250, showHidden="true")
prim = [c["id"] for c in lijst["items"] if c.get("primary")]
toets("draait op het eigen account van Mehdi",
      "GOED" if prim == ["mehdiprivewerkagenda@gmail.com"] else "FOUT", ", ".join(prim))
toets("ziet alle agenda's", "GOED" if len(lijst["items"]) >= 40 else "LET OP",
      f"{len(lijst['items'])} agenda's")

print("\n2. DE AGENDA'S DIE HIJ LEEST")
nu = datetime.now(timezone.utc)
for kal, label in W.KALENDERS.items():
    try:
        g(f"/calendars/{urllib.parse.quote(kal, safe='')}/events",
          timeMin=nu.isoformat(), timeMax=(nu + timedelta(days=1)).isoformat(), maxResults=1)
        stand, tekst = "GOED", ""
    except urllib.error.HTTPError as e:
        stand, tekst = "FOUT", f"HTTP {e.code}"
    if kal in W.gearchiveerd():
        stand, tekst = "LET OP", "staat op ZZ ARCHIEF en wordt overgeslagen"
    toets(label[:46], stand, tekst)

print("\n2b. DE VASTE AGENDAKLEUREN")
staat = {c["id"]: c for c in lijst["items"]}
for kal, afspraak in W.AGENDA_VASTE_KLEUR.items():
    c = staat.get(kal)
    if not c:
        toets(f"{afspraak['naam']} staat in de lijst", "FOUT", "niet gevonden")
        continue
    echt = (c.get("backgroundColor") or "").lower()
    toets(f"{afspraak['naam']} is {afspraak['kleur']}",
          "GOED" if echt == afspraak["achtergrond"] else "LET OP",
          f"staat op {echt or '?'}, afgesproken {afspraak['achtergrond']}")
    try:
        d = g(f"/calendars/{urllib.parse.quote(kal, safe='')}/events",
              timeMin=(nu - timedelta(days=30)).isoformat(), singleEvents="true", maxResults=2500,
              fields="items(colorId)")
        met = [e for e in d.get("items", []) if e.get("colorId")]
        toets(f"{afspraak['naam']} zonder eigen kleuren per afspraak",
              "GOED" if not met else "LET OP",
              f"{len(met)} afspraken hebben een eigen kleur en overschrijven de agendakleur")
    except urllib.error.HTTPError as e:
        toets(f"{afspraak['naam']} leesbaar", "FOUT", f"HTTP {e.code}")

print("\n3. DE GRENDEL OP HET ARCHIEF")
for kal, verwacht in (("mehdiprivewerkagenda@gmail.com", True),
                      ("mehdipriveagena@gmail.com", True),
                      ("haagendalightprojects@gmail.com", False),
                      ("harchitectsbvba@gmail.com", False)):
    uit = W.mag_schrijven(kal)
    toets(f"schrijven in {kal.split('@')[0]}", "GOED" if uit == verwacht else "FOUT",
          f"mag={uit}, verwacht={verwacht}")

print("\n4. HET VERLEDEN")
tel = 0
for kal in ("harchitectsbvba@gmail.com", "haagendalightprojects@gmail.com",
            "bfe28ee64dc72b449582af5e6a9fc6af3669709adf07adc8b49eb97666f07981@group.calendar.google.com"):
    try:
        d = g(f"/calendars/{urllib.parse.quote(kal, safe='')}/events",
              timeMin="2024-09-01T00:00:00Z", timeMax=nu.isoformat(), singleEvents="true",
              maxResults=2500, fields="items(id)")
        tel += len(d.get("items", []))
        toets(f"archief leesbaar: {kal.split('@')[0][:28]}", "GOED", f"{len(d.get('items', []))} afspraken")
    except urllib.error.HTTPError as e:
        toets(f"archief leesbaar: {kal.split('@')[0][:28]}", "FOUT", f"HTTP {e.code}")

print("\n5. CALENDLY")
env = pathlib.Path.home() / "appportal/mijnagents-data/.env"
tok = ""
for r in env.read_text().splitlines():
    if r.startswith("CALENDLY_TOKEN_GENERAL="):
        tok = r.split("=", 1)[1].strip().strip('"')
CH = {"Authorization": "Bearer " + tok, "User-Agent": "mijnagents/1.0"}


def c(u):
    return json.load(urllib.request.urlopen(urllib.request.Request(u, headers=CH), timeout=30))


try:
    me = c("https://api.calendly.com/users/me")["resource"]
    toets("sleutel werkt", "GOED", me["email"])
except Exception as e:
    toets("sleutel werkt", "FOUT", str(e)[:60]); me = None

if me:
    types = c("https://api.calendly.com/event_types?" + urllib.parse.urlencode(
        {"organization": me["current_organization"], "count": 100, "active": "true"}))["collection"]
    toets("actieve boekingstypes", "GOED" if types else "FOUT", f"{len(types)} types")

    boek, pag = [], None
    while True:
        q = {"user": me["uri"], "status": "active", "count": 100,
             "min_start_time": nu.isoformat().replace("+00:00", "Z")}
        if pag:
            q["page_token"] = pag
        d = c("https://api.calendly.com/scheduled_events?" + urllib.parse.urlencode(q))
        boek += d["collection"]; pag = d["pagination"].get("next_page_token")
        if not pag:
            break

    def dt(x):
        return datetime.fromisoformat(x.replace("Z", "+00:00")).astimezone(timezone.utc)

    bezet = []
    for kal in list(W.KALENDERS) + ["haagendalightprojects@gmail.com"]:
        try:
            d = g(f"/calendars/{urllib.parse.quote(kal, safe='')}/events", timeMin=nu.isoformat(),
                  singleEvents="true", orderBy="startTime", maxResults=250,
                  fields="items(summary,start/dateTime,end/dateTime,transparency)")
        except urllib.error.HTTPError:
            continue
        for e in d.get("items", []):
            s, t = e.get("start", {}).get("dateTime"), e.get("end", {}).get("dateTime")
            if s and t and e.get("transparency") != "transparent":
                bezet.append((e.get("summary", ""), dt(s), dt(t)))
    bots = 0
    for b in boek:
        bs, be = dt(b["start_time"]), dt(b["end_time"])
        if len([1 for _, s, e in bezet if bs < e and s < be]) > 1:
            bots += 1
    toets("boekingen zonder dubbele bezetting", "GOED" if bots == 0 else "LET OP",
          f"{len(boek)} boekingen, {bots} botsen")

print("\n6. TITELS EN ADRESSEN")
items = A.afspraken(van_dagen=0, tot_dagen=30)
per_fout, geen_adres = {}, []
for a in items:
    if a.get("fout") or a.get("hele_dag") or a.get("kalender", "").startswith("en.be#"):
        continue
    i = W.lees_titel(a["titel"])
    if i["reistijd"]:
        continue
    for reden in W.titelfouten(a, i):
        per_fout.setdefault(reden, []).append(f"{a['start'][:16]} {a['titel'][:58]}")
    if i["buiten"] or i["soort"] in ("PB", "KB"):
        adres = a.get("locatie") or ""
        if not adres or adres.lower().startswith("http"):
            geen_adres.append(f"{a['start'][:16]} {a['titel'][:58]}")

for reden in ("geen firmacode", "buiten zonder !!", "intern zonder naam van een collega"):
    rij = per_fout.get(reden, [])
    toets(f"geen enkele afspraak met: {reden}", "GOED" if not rij else "FOUT",
          f"{len(rij)} in de komende dertig dagen")
    for x in rij[:12]:
        print(f"          {x}")

toets("elke buitenafspraak heeft een adres", "GOED" if not geen_adres else "FOUT",
      f"{len(geen_adres)} buiten zonder adres")
for r in geen_adres[:20]:
    print(f"          {r}")

print(f"\n{goed} goed, {letop} let op, {fout} fout\n")
sys.exit(1 if fout else 0)
