#!/usr/bin/env python3
"""De alleen-lezende Zoom-app "Zoomwacht lezen" zetten en toetsen (ontwerp regie-zoom v1.2: Z2, J17, T106).

Mehdi's deel tot één handeling. Hij maakt de app in de Zoom Marketplace (Server-to-Server OAuth, alleen leesrechten)
en plakt bij de drie vragen de Account ID, de Client ID en de Client Secret. Er verschijnt niets op het scherm; dat
is de bedoeling. Nooit in een chat.

    ssh -t globaal '~/agents/.venv/bin/python ~/appportal/mijnagents-runner/zoom_leesapp.py --zet'
    zoom_leesapp.py                    alleen toetsen, niets schrijven
    zoom_leesapp.py --zet --vervang    bestaande sleutels vervangen (na een extra recht in Zoom, of een foute sleutel)

Schrijven, alleen met --zet, en pas na drie toetsen met de drie nieuwe waarden in het geheugen (RZ4-02, 22-10-2026: tot
dan stonden de sleutels al in .env voor de eigenaar gecontroleerd was). Faalt er een, dan schrijft het niets, is de
exitcode niet nul en zegt de laatste regel waarom ("niets geschreven: ..."):
1. een token. Komt er geen, dan "geen token met deze sleutels": een foute sleutel in .env liet De Zoomwacht met de
   leesapp lezen zonder token (ZOO-10);
2. de rechten: een verboden recht wordt geweigerd (zie hieronder), voor er een vraag naar Zoom gaat;
3. de eigenaar: de host van het meest voorkomende nummer in Mehdi's eigen Fathom-opnames (/meetings/<nummer>) moet
   /users/me van de nieuwe app zijn, beide gelezen met het token van de nieuwe sleutels (profiel nieuw van zoom.py,
   nooit een sleutel uit .env en nooit de app van de stack). En die gebruiker moet de eigenaar van de app van de stack
   zijn (/users/me met het profiel stack, gemeten: Mehdi): het anker van ZOO-08, ook hier (tegenproef op RZ4-02,
   22-10-2026: is dat nummer de ruimte van een collega en de nieuwe app van die collega, dan klopten de eerste twee en
   stonden zijn sleutels in .env). Anders "de eigenaar van de nieuwe app is niet de host van het eigen Fathom-nummer",
   "de eigenaar van de nieuwe app is niet de eigenaar van de app van de stack", of "eigenaar niet te controleren" met
   de reden.
Pas dan ZOOM_LEES_CLIENT_ID en ZOOM_LEES_CLIENT_SECRET in ~/appportal/.env, alleen als ze er nog niet staan (met
--vervang ook dan; staat er een andere waarde, dan zegt het dat). De Account ID vergelijkt het stil met ZOOM_ACCOUNT_ID
van de stack; alleen bij een verschil komt ZOOM_LEES_ACCOUNT_ID erbij. Het bestand wordt atomisch vervangen (tijdelijk
bestand ernaast, rechten 600, os.replace); de andere regels blijven zoals ze waren. Er wordt nooit een waarde afgedrukt.

Een verboden recht (13.6, rechten-zoomwacht-lezen.md, Nooit aanvinken: elk recht met write, update of delete, de
sleutels om als gebruiker te starten, de bediening van een ruimte, chatberichten, AI-samenvattingen en archieven): dan
weigert het te werken. Met --zet schrijft het niets ("niets geschreven: verboden recht <naam>"), zonder --zet toetst het
niets verder ("geweigerd: ... <naam>"); de exitcode is niet nul. Het Zoom-transcript
(cloud_recording:read:meeting_transcript:admin) staat ook onder Nooit; het vangnet kan het nodig hebben, maar sinds RZ3-04
(22-10-2026) wordt het geweigerd zoals de andere, tot Mehdi over dat recht beslist. De weigering zegt dat er dan bij
("dat recht blijft geweigerd tot Mehdi erover beslist"). Tot dan gaf het alleen een melding en werkte de app ermee.

Toetsen, met alleen namen, ja of nee en HTTP-codes op het scherm:
- of de app een token krijgt, en per recht 'aanwezig' of 'ontbreekt': KERN (nodig voor de telling en het vangnet; een
  ontbrekend recht maakt de exitcode niet nul) en ADVIES (voor de latere accountscan; telt niet mee). Geen token met
  sleutels die er al staan: de laatste regel zegt "opnieuw met --zet --vervang";
- de host van het meest voorkomende nummer in de opnames van Mehdi's eigen Fathom-account (via /meetings/<nummer>),
  naast de eigenaar van de app van de stack (/users/me, gemeten: Mehdi). Alleen als die twee dezelfde zijn, is de
  gebruiker zeker, en alleen dan en alleen met --zet schrijft het ZOOM_MEHDI_USER zelf als die nog niet staat (J17).
  Anders schrijft het niets en ontbreekt "gebruiker niet zeker" (ZOO-08): tot dan keurde de toets een collega met
  meer eigen opnames in zijn ruimte nooit af, want ze vergeleek die gebruiker met zijn eigen nummer;
- of de vaste vergaderruimte van die gebruiker hetzelfde nummer heeft (ja of nee);
- een proefdownload in het geheugen van de jongste TRANSCRIPT-opname (ja of nee, met de HTTP-code, nooit de url):
  of een Server-to-Server-token een Zoom-transcript mag downloaden, is niet bewezen, dus meten we het hier. Weigert Zoom
  de download (401, 403, of 400 met code 4711), dan meet ik welk recht Zoom noemt. Is het het transcriptrecht, dan zegt
  de regel "download van het transcript vraagt een recht dat Mehdi nog niet toestond", noemt een melding dat recht, en
  ontbreekt het (Mehdi beslist). Is het een ander recht, dan "download vraagt recht <naam>" en ontbreekt dat recht,
  zonder Mehdi. Noemt Zoom geen recht (bv. 401 met Zoom-code 124, een ongeldig token), dan "download geweigerd, HTTP
  <code>; Zoom noemde geen recht" (tegenproef op RZ3-04, 22-10-2026: tot dan heette elke weigering het transcriptrecht).
  De Zoomwacht zet bij een geweigerde download een nood voor Mehdi en telt het gesprek zonder tekst.
Exitcode 0 alleen als de kern volledig is en de andere toetsen slagen; een advies telt niet mee. De laatste regel is
"klaar", wat ontbreekt, of de weigering.
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
# De rechten van de app, uit de definitieve lijst (rechten-zoomwacht-lezen.md v1, ontwerp 13.6), alle alleen lezend.
# KERN is nodig voor de telling en het vangnet en bepaalt de exitcode. Het recht op chatberichten staat er bewust niet in:
# het tellen ervan blijft op de app van de stack (EIGEN-1).
KERN = ("user:read:user:admin", "meeting:read:meeting:admin", "meeting:read:list_meetings:admin",
        "meeting:read:past_meeting:admin", "meeting:read:list_past_participants:admin", "meeting:read:list_past_instances:admin",
        "report:read:user:admin", "cloud_recording:read:list_user_recordings:admin",
        "cloud_recording:read:list_recording_files:admin", "team_chat:read:list_user_sessions:admin")
# ADVIES is de rest van de lijst, voor de latere accountscan (fase 4b): per recht aanwezig of ontbreekt, zonder gevolg
# voor de exitcode. Een paar toont Zoom soms niet; dan ontbreken ze gewoon.
ADVIES = ("user:read:list_users:admin", "user:read:summary:admin", "user:read:settings:admin",
          "account:read:settings:admin", "account:read:lock_settings:admin",
          "meeting:read:list_templates:admin", "meeting:read:list_summaries:admin",
          "cloud_recording:read:list_account_recordings:admin", "cloud_recording:read:recording_settings:admin",
          "report:read:list_users:admin", "report:read:daily_usage:admin", "report:read:cloud_recording:admin",
          "report:read:user_activities:admin", "report:read:operation_logs:admin", "report:read:billing:admin",
          "report:read:list_history_meetings:admin",
          "dashboard:read:list_meetings:admin", "dashboard:read:client_versions:admin", "dashboard:read:chat:admin",
          "dashboard:read:ai_adoption:admin", "dashboard:read:ai_usage_trend:admin", "dashboard:read:ai_kpi:admin",
          "group:read:list_groups:admin", "group:read:list_members:admin", "group:read:settings:admin",
          "group:read:lock_settings:admin", "role:read:list_roles:admin", "role:read:list_members:admin", "role:read:role:admin",
          "team_chat:read:list_user_channels:admin", "team_chat:read:list_channels:admin", "team_chat:read:list_members:admin",
          "team_chat:read:retention:admin",
          "marketplace:read:list_apps:admin", "marketplace:read:app:admin", "marketplace:read:list_user_app_requests:admin",
          "billing:read:plan_information:admin", "billing:read:plan_usage:admin", "billing:read:list_invoices:admin",
          "zoom_rooms:read:list_rooms:admin", "webinar:read:list_webinars:admin", "h323_device:read:list_devices:admin",
          "contact_group:read:list_groups:admin", "tsp:read:tsp:admin", "tracking_field:read:list_tracking_fields:admin",
          "information_barrier:read:list_policies:admin")
MARKETPLACE = "haal het weg in de Zoom Marketplace, dan opnieuw"
# RZ3-04: wat de proefdownload zegt als Zoom de download van het transcript op een recht weigert
TRANSCRIPT_NIET_TOEGESTAAN = "download van het transcript vraagt een recht dat Mehdi nog niet toestond"
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


def wacht_op_mehdi(fout):
    """RZ3-04: de toevoeging bij een weigering voor een recht dat het vangnet misschien nodig heeft (TOT_MEHDI_BESLIST,
    het Zoom-transcript): het blijft geweigerd tot Mehdi erover beslist. Leeg als geen enkel geweigerd recht daarop
    wacht; zo zegt een weigering voor een recht dat nooit mag, niet dat Mehdi er nog over beslist."""
    wacht = [r for r in fout if r.lower() in Z.TOT_MEHDI_BESLIST]
    if not wacht:
        return ""
    wie = "dat recht" if len(wacht) == len(fout) == 1 else ", ".join(wacht)
    return f"; {wie} blijft geweigerd tot Mehdi erover beslist"


def vragen():
    """De drie waarden uit App Credentials, zonder echo. Een lege waarde of een met een spatie stopt het zetten."""
    waarden = {}
    for naam, vraag in (("account", "Account ID: "), ("client", "Client ID: "), ("geheim", "Client Secret: ")):
        w = getpass.getpass(vraag).strip()
        if not w or any(c.isspace() for c in w):
            raise SystemExit(f"{vraag.rstrip(': ')} leeg of met een spatie: niets geschreven")
        waarden[naam] = w
    return waarden


def eigenaar_nieuwe_app():
    """RZ4-02: is de nieuwe app van Mehdi? Drie gebruikers moeten dezelfde zijn: de host van het meest voorkomende
    eigen Fathom-nummer (/meetings/<nummer>) en /users/me van de nieuwe app, beide gelezen met het token van de nieuwe
    sleutels in het geheugen (profiel nieuw; zoom.nieuw_token staat dan al), en /users/me van de app van de stack, het
    anker van ZOO-08 (gemeten: Mehdi). Geeft None als dat klopt, anders de reden. Drukt nooit een id af.
    Tegenproef op RZ4-02 (22-10-2026): tot dan vergeleek ik alleen de host met de nieuwe app. Was het meest voorkomende
    nummer de ruimte van een collega (het geval van ZOO-08) en de nieuwe app van die collega, dan klopte dat, en stonden
    zijn sleutels in .env; zonder ZOOM_MEHDI_USER las De Zoomwacht daarna zijn gesprekken. De stack lees ik alleen als
    host en nieuwe app al gelijk zijn, en alleen /users/me."""
    nummer = eigen_nummer()
    if not nummer:
        return "eigenaar niet te controleren: geen eigen opnames in het Fathom-archief"
    Z.vastzetten(None)
    Z.nummer_erbij(nummer)
    try:
        return _eigenaar_vergelijken(nummer)
    finally:
        Z.vastzetten(None)


def _eigenaar_vergelijken(nummer):
    """Binnen het venster van eigenaar_nieuwe_app (vastzetten(None), het nummer erbij): de drie gebruikers lezen en
    vergelijken. Geeft None of de reden."""
    try:
        host = str((Z.lees(f"/meetings/{nummer}", profiel=Z.NIEUW) or {}).get("host_id") or "")
        eigenaar = str((Z.lees("/users/me", profiel=Z.NIEUW) or {}).get("id") or "")
    except Z.ZoomFout as e:
        return f"eigenaar niet te controleren ({e})"
    if not host:
        return "eigenaar niet te controleren: Zoom gaf geen host voor het eigen Fathom-nummer"
    if not eigenaar:
        return "eigenaar niet te controleren: de nieuwe app gaf geen eigen gebruiker"
    if host != eigenaar:
        return "de eigenaar van de nieuwe app is niet de host van het eigen Fathom-nummer"
    try:
        stack = str((Z.lees("/users/me", profiel="stack") or {}).get("id") or "")
    except Z.ZoomFout as e:
        return f"eigenaar niet te controleren: eigenaar van de app van de stack onbekend ({e})"
    if not stack:
        return "eigenaar niet te controleren: eigenaar van de app van de stack onbekend"
    if eigenaar != stack:
        return "de eigenaar van de nieuwe app is niet de eigenaar van de app van de stack"
    return None


def zetten(vervang=False):
    """De drie waarden vragen en pas schrijven na drie toetsen in het geheugen: een token (ZOO-10), geen verboden recht
    (13.6) en de eigenaar (RZ4-02). Geeft False als een toets faalt: dan staat er niets nieuws in .env, en is de laatste
    regel 'niets geschreven: <reden>'."""
    w = vragen()
    try:
        d = Z.token_halen(w["client"], w["geheim"], w["account"])
        print("token met de nieuwe sleutels: ja")
    except Z.ZoomFout as e:
        print(f"token met de nieuwe sleutels: nee ({e})")
        print("niets geschreven: geen token met deze sleutels")
        return False
    fout = Z.verboden((d.get("scope") or "").split())
    if fout:
        # 13.6: een app met een recht uit 'Nooit aanvinken' krijgt geen plaats in .env
        print(f"geweigerd: de app heeft een recht dat ze nooit mag hebben ({MARKETPLACE})")
        print("niets geschreven: verboden recht " + ", ".join(fout) + wacht_op_mehdi(fout))
        return False
    # RZ4-02: de eigenaar met het nieuwe token, in het geheugen, voor er iets in .env komt
    try:
        Z.nieuw_token(d)
        reden = eigenaar_nieuwe_app()
    except Z.ZoomFout as e:
        reden = f"eigenaar niet te controleren ({e})"
    finally:
        Z.nieuw_vergeten()
    if reden:
        print("eigenaar van de nieuwe app: niet zeker")
        print(f"niets geschreven: {reden}")
        return False
    print("eigenaar van de nieuwe app: de host van het eigen Fathom-nummer en de eigenaar van de app van de stack")
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
    """De jongste TRANSCRIPT-opname van de laatste 30 dagen, in het geheugen: (gelukt, uitleg, recht). Nooit de url.
    recht is het recht dat Zoom noemt als het de lijst of de download weigert, anders leeg. Tegenproef op RZ3-04
    (22-10-2026): tot dan heette elke geweigerde download 'een recht dat Mehdi nog niet toestond', ook een ander recht
    of een ongeldig token. Nu meet ik het (rechten-zoomwacht-lezen.md: 'dan meldt zoom_leesapp.py welk'):
    - Zoom noemt het transcriptrecht (TOT_MEHDI_BESLIST): TRANSCRIPT_NIET_TOEGESTAAN, en Mehdi beslist;
    - Zoom noemt een ander recht: 'download vraagt recht <naam>', zonder Mehdi;
    - Zoom noemt geen recht (401, 403, Zoom-code 124): 'download geweigerd, HTTP <code>; Zoom noemde geen recht'."""
    tot = date.today() + timedelta(days=1)
    try:
        lijst = Z.opnames((tot - timedelta(days=30)).isoformat(), tot.isoformat(), "lees")
    except Z.GeenRecht as e:
        return False, f"geen recht: {e.scope}", e.scope
    except Z.ZoomFout as e:
        return False, str(e), ""
    bestanden = sorted((b["start"], b["id"]) for m in lijst for b in m["bestanden"]
                       if b["soort"] == "TRANSCRIPT" and b["status"] == "completed" and b["id"])
    if not bestanden:
        return False, "geen TRANSCRIPT-opname in de laatste 30 dagen", ""
    try:
        Z.download(bestanden[-1][1], "lees", max_bytes=2_000_000)
    except Z.GeenRecht as e:
        if e.scope.lower() in Z.TOT_MEHDI_BESLIST:
            # RZ3-04: het recht voor het transcript staat onder Nooit aanvinken en blijft geweigerd tot Mehdi beslist
            return False, TRANSCRIPT_NIET_TOEGESTAAN, e.scope
        if e.scope != "download":
            return False, f"download vraagt recht {e.scope}", e.scope
        zoomcode = f", Zoom-code {e.zoomcode}" if e.zoomcode is not None else ""
        return False, f"download geweigerd, HTTP {e.http}{zoomcode}; Zoom noemde geen recht", ""
    except Z.ZoomFout as e:
        return False, str(e), ""
    return True, "HTTP 200", ""


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
        fout = Z.verboden(rechten)
    except Z.VerbodenRecht as e:
        rechten, fout = set(), e.rechten
    except Z.ZoomFout as e:
        print(f"token: nee ({e})")
        print(f"ontbreekt: token, de sleutels van de leesapp geven er geen: {VERVANG}")
        return 1
    if fout:
        # 13.6: met een recht uit 'Nooit aanvinken' werk ik niet verder; De Zoomwacht leest dan met de app van de stack
        print("token: ja, maar geweigerd")
        print(f"geweigerd: de leesapp heeft een recht dat ze nooit mag hebben: {', '.join(fout)} ({MARKETPLACE})"
              + wacht_op_mehdi(fout))
        return 1
    print("token: ja")
    for naam in KERN:
        aanwezig = naam in rechten
        print(f"recht {naam}: {'aanwezig' if aanwezig else 'ontbreekt'}")
        if not aanwezig:
            ontbreekt.append(naam)
    for naam in ADVIES:
        print(f"recht {naam}: {'aanwezig' if naam in rechten else 'ontbreekt'} (advies)")
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
            gelukt, uitleg, recht = proefdownload()
            print(f"proefdownload van een Zoom-transcript: {'ja' if gelukt else 'nee'} ({uitleg})")
            if recht.lower() in Z.TOT_MEHDI_BESLIST:
                # RZ3-04: geen fout van de app maar een keuze van Mehdi; tot dan telt De Zoomwacht zulke gesprekken zonder
                # tekst, met een nood voor hem. Alleen als Zoom dat recht zelf noemt (tegenproef van 22-10-2026).
                print(f"melding: het vangnet vraagt {recht}; dat recht staat onder Nooit aanvinken en blijft geweigerd tot "
                      "Mehdi erover beslist")
                ontbreekt.append("recht voor de download van het transcript (Mehdi beslist)")
            elif recht:
                ontbreekt.append(recht)          # een recht dat Zoom noemt en dat wel mag: aanvinken in de Marketplace
            elif not gelukt:
                ontbreekt.append("proefdownload van een Zoom-transcript")
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
