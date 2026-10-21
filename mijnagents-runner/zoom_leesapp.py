#!/usr/bin/env python3
"""De alleen-lezende Zoom-app "Zoomwacht lezen" zetten en toetsen (ontwerp regie-zoom v1.2: Z2, J17, T106).

Mehdi's deel tot één handeling. Hij maakt de app in de Zoom Marketplace (Server-to-Server OAuth, alleen leesrechten)
en plakt bij de drie vragen de Account ID, de Client ID en de Client Secret. Er verschijnt niets op het scherm; dat
is de bedoeling. Nooit in een chat.

    ssh -t globaal '~/agents/.venv/bin/python ~/appportal/mijnagents-runner/zoom_leesapp.py --zet'
    zoom_leesapp.py                    alleen toetsen, niets schrijven
    zoom_leesapp.py --zet --vervang    bestaande sleutels vervangen (na een extra recht in Zoom, of een foute sleutel)

Schrijven, alleen met --zet: eerst haalt het met de drie nieuwe waarden een token, in het geheugen. Komt er geen, dan
schrijft het niets ("niets geschreven: geen token met deze sleutels"): een foute sleutel in .env liet De Zoomwacht met
de leesapp lezen zonder token (ZOO-10). Komt er wel een, dan ZOOM_LEES_CLIENT_ID en ZOOM_LEES_CLIENT_SECRET in
~/appportal/.env, alleen als ze er nog niet staan (met --vervang ook dan; staat er een andere waarde, dan zegt het
dat). De Account ID vergelijkt het stil met ZOOM_ACCOUNT_ID van de stack; alleen bij een verschil komt
ZOOM_LEES_ACCOUNT_ID erbij. Het bestand wordt atomisch vervangen (tijdelijk bestand ernaast, rechten 600,
os.replace); de andere regels blijven zoals ze waren. Er wordt nooit een waarde afgedrukt.

Toetsen, met alleen namen, ja of nee en HTTP-codes op het scherm:
- of de app een token krijgt, en per nodig recht 'aanwezig' of 'ontbreekt'; geen token met sleutels die er al staan:
  de laatste regel zegt "opnieuw met --zet --vervang";
- de host van het meest voorkomende nummer in de opnames van Mehdi's eigen Fathom-account (via /meetings/<nummer>),
  naast de eigenaar van de app van de stack (/users/me, gemeten: Mehdi). Alleen als die twee dezelfde zijn, is de
  gebruiker zeker, en alleen dan en alleen met --zet schrijft het ZOOM_MEHDI_USER zelf als die nog niet staat (J17).
  Anders schrijft het niets en ontbreekt "gebruiker niet zeker" (ZOO-08): tot dan keurde de toets een collega met
  meer eigen opnames in zijn ruimte nooit af, want ze vergeleek die gebruiker met zijn eigen nummer;
- of de vaste vergaderruimte van die gebruiker hetzelfde nummer heeft (ja of nee);
- een proefdownload in het geheugen van de jongste TRANSCRIPT-opname (ja of nee, met de HTTP-code, nooit de url):
  of een Server-to-Server-token een Zoom-transcript mag downloaden, is niet bewezen, dus meten we het hier.
Exitcode 0 alleen als alles in orde is. De laatste regel is "klaar" of wat ontbreekt.
"""
import argparse
import getpass
import os
import sys
import tempfile
from collections import Counter
from datetime import date, timedelta

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import zoom as Z  # noqa: E402

ENV = os.path.expanduser("~/appportal/.env")
# De rechten die De Zoomwacht nodig heeft (ontwerp, 8.1). Geen enkel recht met write.
NODIG = ("report:read:user:admin", "meeting:read:list_past_instances:admin", "meeting:read:past_meeting:admin",
         "meeting:read:list_past_participants:admin", "meeting:read:meeting:admin", "meeting:read:list_meetings:admin",
         "cloud_recording:read:list_user_recordings:admin", "user:read:user:admin",
         "team_chat:read:list_user_sessions:admin", "team_chat:read:list_user_messages:admin")
FACULTATIEF = ("cloud_recording:read:recording:admin",)   # "als Zoom hem toont"
FATHOM_DAGEN = 60
VERVANG = "opnieuw met --zet --vervang"
ANDERE_WAARDE = f"staat al, met een andere waarde ({VERVANG})"


def env_zetten(waarden, vervang=False, pad=None):
    """Sleutels in het .env-bestand: een nieuwe regel per sleutel die er nog niet staat, een bestaande alleen met
    vervang. Atomisch: een tijdelijk bestand naast het doel met rechten 600, dan os.replace, zodat een lezer nooit een
    half bestand ziet. Geeft per naam 'gezet', 'vervangen', 'staat al' of ANDERE_WAARDE (zonder vervang, met een andere
    waarde dan de nieuwe), nooit een waarde."""
    pad = pad or ENV
    try:
        with open(pad, encoding="utf-8") as f:
            regels = f.read().splitlines()
    except FileNotFoundError:
        regels = []
    uit = {}
    for naam, waarde in waarden.items():
        plekken = [i for i, r in enumerate(regels) if r.startswith(naam + "=")]
        if plekken and not vervang:
            oud = regels[plekken[0]].split("=", 1)[1].strip().strip('"').strip("'")
            uit[naam] = "staat al" if oud == waarde else ANDERE_WAARDE
            continue
        if plekken:
            regels[plekken[0]] = f"{naam}={waarde}"
            for i in reversed(plekken[1:]):
                del regels[i]
            uit[naam] = "vervangen"
        else:
            regels.append(f"{naam}={waarde}")
            uit[naam] = "gezet"
    if any(v in ("gezet", "vervangen") for v in uit.values()):
        map_ = os.path.dirname(pad) or "."
        os.makedirs(map_, exist_ok=True)
        fd, tijdelijk = tempfile.mkstemp(prefix=".env-", dir=map_)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(regels) + "\n")
            os.replace(tijdelijk, pad)
        except BaseException:
            if os.path.exists(tijdelijk):
                os.unlink(tijdelijk)
            raise
    return uit


def vragen():
    """De drie waarden uit App Credentials, zonder echo. Een lege waarde of een met een spatie stopt het zetten."""
    waarden = {}
    for naam, vraag in (("account", "Account ID: "), ("client", "Client ID: "), ("geheim", "Client Secret: ")):
        w = getpass.getpass(vraag).strip()
        if not w or any(c.isspace() for c in w):
            raise SystemExit(f"{vraag.rstrip(': ')} leeg of met een spatie: niets geschreven")
        waarden[naam] = w
    return waarden


def zetten(vervang=False):
    """De drie waarden vragen, eerst een token halen in het geheugen, en pas dan schrijven (ZOO-10). Geeft False als
    er geen token kwam: dan staat er niets nieuws in .env, en is de laatste regel 'niets geschreven: ...'."""
    w = vragen()
    try:
        Z.token_halen(w["client"], w["geheim"], w["account"])
        print("token met de nieuwe sleutels: ja")
    except Z.ZoomFout as e:
        print(f"token met de nieuwe sleutels: nee ({e})")
        print("niets geschreven: geen token met deze sleutels")
        return False
    nieuw = {"ZOOM_LEES_CLIENT_ID": w["client"], "ZOOM_LEES_CLIENT_SECRET": w["geheim"]}
    if w["account"] != Z._sleutel("ZOOM_ACCOUNT_ID"):
        nieuw["ZOOM_LEES_ACCOUNT_ID"] = w["account"]
    for naam, wat in env_zetten(nieuw, vervang).items():
        print(f"{naam}: {wat}")
    if "ZOOM_LEES_ACCOUNT_ID" not in nieuw:
        print("ZOOM_LEES_ACCOUNT_ID: niet nodig (zelfde account als de stack)")
    for naam in nieuw:
        os.environ.pop(naam, None)       # zoom.py leest het bestand opnieuw, niet een oude kopie in de omgeving
    Z._tokens.clear()
    return True


def eigen_nummer():
    """Het meest voorkomende meetingnummer in de opnames van Mehdi's eigen Fathom-account (archief van De Fathomwacht)."""
    import zoom_wacht as ZW  # noqa: PLC0415  (pas hier: het archief lezen hoort bij De Zoomwacht)
    vandaag = date.today()
    opnames, _, _ = ZW.fathom_lezen((vandaag - timedelta(days=FATHOM_DAGEN)).isoformat(), vandaag.isoformat())
    teller = Counter(o["nummer"] for o in opnames if o["eigen"] and o["nummer"])
    return teller.most_common(1)[0][0] if teller else ""


def proefdownload():
    """De jongste TRANSCRIPT-opname van de laatste 30 dagen, in het geheugen: (gelukt, uitleg). Nooit de url."""
    tot = date.today() + timedelta(days=1)
    try:
        lijst = Z.opnames((tot - timedelta(days=30)).isoformat(), tot.isoformat(), "lees")
    except Z.GeenRecht as e:
        return False, f"geen recht: {e.scope}"
    except Z.ZoomFout as e:
        return False, str(e)
    bestanden = sorted((b["start"], b["id"]) for m in lijst for b in m["bestanden"]
                       if b["soort"] == "TRANSCRIPT" and b["status"] == "completed" and b["id"])
    if not bestanden:
        return False, "geen TRANSCRIPT-opname in de laatste 30 dagen"
    try:
        Z.download(bestanden[-1][1], "lees", max_bytes=2_000_000)
    except Z.GeenRecht:
        return False, "geen downloadrecht (HTTP 401 of 403)"
    except Z.ZoomFout as e:
        return False, str(e)
    return True, "HTTP 200"


def gebruiker_zetten(host, zet, vervang):
    """ZOO-08: ZOOM_MEHDI_USER is de host van het eigen Fathom-nummer, maar alleen als die de eigenaar van de app van de
    stack is (/users/me, gemeten: Mehdi). Een vergelijking met zijn eigen nummer keurde een collega nooit af. Schrijven
    alleen met --zet (J17). Geeft wat ontbreekt, of None; drukt nooit een id af."""
    try:
        eigenaar = (Z.lees("/users/me", profiel="stack") or {}).get("id") or ""
    except Z.ZoomFout as e:
        eigenaar = ""
        print(f"eigenaar van de app van de stack: onbekend ({e})")
    if not (host and eigenaar and host == eigenaar):
        print("ZOOM_MEHDI_USER: niets geschreven, de host van het eigen Fathom-nummer is niet zeker de eigenaar van de "
              "app van de stack")
        return "gebruiker niet zeker"
    huidig = Z._lees_sleutel("ZOOM_MEHDI_USER")
    if huidig == host:
        print("ZOOM_MEHDI_USER: staat al")
        return None
    if not zet:
        print("ZOOM_MEHDI_USER: niet geschreven (alleen met --zet)" if not huidig else
              "ZOOM_MEHDI_USER: staat al, met een andere gebruiker (opnieuw met --zet --vervang)")
        return "ZOOM_MEHDI_USER (alleen met --zet)" if not huidig else "gebruiker niet zeker"
    wat = env_zetten({"ZOOM_MEHDI_USER": host}, vervang)["ZOOM_MEHDI_USER"]
    print(f"ZOOM_MEHDI_USER: {wat.replace('waarde', 'gebruiker')}")
    os.environ.pop("ZOOM_MEHDI_USER", None)
    return None if wat in ("gezet", "vervangen", "staat al") else "gebruiker niet zeker"


def toetsen(zet=False, vervang=False):
    ontbreekt = []
    if not Z.leesapp():
        print("sleutels van de leesapp: ontbreken")
        print("ontbreekt: sleutels van de leesapp (zoom_leesapp.py --zet)")
        return 1
    try:
        rechten = Z.rechten("lees")
        print("token: ja")
    except Z.ZoomFout as e:
        print(f"token: nee ({e})")
        print(f"ontbreekt: token, de sleutels van de leesapp geven er geen: {VERVANG}")
        return 1
    for naam in NODIG + FACULTATIEF:
        aanwezig = naam in rechten
        print(f"recht {naam}: {'aanwezig' if aanwezig else 'ontbreekt'}" + (" (facultatief)" if naam in FACULTATIEF else ""))
        if not aanwezig and naam in NODIG:
            ontbreekt.append(naam)
    nummer = eigen_nummer()
    if not nummer:
        print("nummer van de vaste vergaderruimte uit Fathom: onbekend (geen eigen opnames in het archief)")
        ontbreekt.append("eigen Fathom-nummer")
    else:
        Z.vastzetten(None)
        Z.nummer_erbij(nummer)
        try:
            host = (Z.lees(f"/meetings/{nummer}", profiel="lees") or {}).get("host_id") or ""
        except Z.ZoomFout as e:
            host = ""
            print(f"host van de vaste vergaderruimte: onbekend ({e})")
        Z.vastzetten(None)
        gebruiker = gebruiker_zetten(host, zet, vervang)
        if gebruiker:
            ontbreekt.append(gebruiker)
        try:
            ik = Z.lees(f"/users/{Z.ingang()}", profiel="lees") or {}
        except Z.ZoomFout as e:
            ik = {}
            print(f"gebruiker: onbekend ({e})")
        zelfde = bool(ik.get("pmi")) and str(ik["pmi"]) == nummer
        print(f"de vaste vergaderruimte van de gebruiker is het eigen Fathom-nummer: {'ja' if zelfde else 'nee'}")
        if not zelfde:
            ontbreekt.append("eigenaar van de vaste vergaderruimte")
        if ik.get("id"):
            Z.vastzetten(ik["id"], [nummer])
            gelukt, uitleg = proefdownload()
            print(f"proefdownload van een Zoom-transcript: {'ja' if gelukt else 'nee'} ({uitleg})")
            if not gelukt:
                ontbreekt.append("downloadrecht voor opnames")
        else:
            ontbreekt.append("gebruiker")
    print("klaar" if not ontbreekt else "ontbreekt: " + ", ".join(ontbreekt))
    return 0 if not ontbreekt else 1


def main(argv=None):
    p = argparse.ArgumentParser(description="De Zoom-leesapp van De Zoomwacht zetten en toetsen.")
    p.add_argument("--zet", action="store_true", help="de drie waarden vragen en in ~/appportal/.env zetten")
    p.add_argument("--vervang", action="store_true", help="met --zet: bestaande sleutels vervangen")
    a = p.parse_args(argv)
    if a.vervang and not a.zet:
        p.error("--vervang alleen met --zet")
    if a.zet and not zetten(a.vervang):
        return 1
    return toetsen(a.zet, a.vervang)


if __name__ == "__main__":
    sys.exit(main())
