#!/usr/bin/env python3
"""De Bode (Regie): twee richtingen tussen het bord en Mehdi.

Naar Mehdi: wat de agents voor hem klaarzetten, via WhatsApp (sinds 30-09-2026, koppelingen/whatsapp.py: de Cloud API
van Meta, van het agentennummer UNABO Assistant). Mag WhatsApp niet (venster van 24 uur dicht en nog geen sjabloon) of
lukt het niet, dan Telegram, dan Zoom-chat; een antwoord op een vraag van Mehdi gaat nooit via Zoom-chat (L2).
Sinds 21-10-2026 (ontwerp regie-zoom v1.2, keuze 1 van Mehdi: optie A) bundel ik, met BUNDELEN op 'ochtend-avond':
  - het ochtendbericht van De Regisseur (soort ochtendbericht, uniek ochtendbericht:JJJJ-MM-DD) gaat als eigen bericht,
    met zijn nummers en een regel "Gebundeld: ..." voor wat sinds de vorige bundel binnenkwam (ochtend_sturen). Staat
    er om 11:00 Brussel geen, dan stuur ik een terugval met de aantallen en meld ik het (terugval_sturen);
  - rond 17:00 Brussel volgt de avondbundel met de mailupdate van 17:00 en wat sinds de ochtend binnenkwam
    (avond_sturen);
  - alleen een oproep, een alarm en het bellen voor afspraken komen meteen.
Met BUNDELEN op 'uit' gaat alles los, zoals voor 21-10-2026; wat de bundelstand bij het terugzetten nog vasthield, gaat
eerst als slotbundel (slotbundel_sturen). De herinnering om de zes uur bestaat niet meer: in 'uit' geeft alleen een nieuw
voorstel (een hoger voorstel-id dan ik al meldde) een bericht (L8).
Van Mehdi: wat hij op WhatsApp of Telegram typt, wordt een bericht op het bord aan De Regisseur, of aan een agent als
hij begint met diens naam en een komma of dubbelepunt ("Zoomwacht, wat is er vanochtend afgesproken?", doel_van). Het
antwoord komt terug zodra de agent het op het bord zette.
Elke minuut. Eerst bel ik (afspraken en alarm), buiten de ronde, zodat een onleesbare werkwijze geen oproep tegenhoudt
(FR-154); daarna gaat de rest door de gedeelde ronde (ag.ronde, N12), met de noden van het bellen mee (X4). Werkwijze
op het bord (werkwijze/bode.md is het zaad).
Met --droog (regisseur.py, agent_ronde): alleen tonen wat ik zou doen; nooit bellen, niets sturen, het bord en de
stand niet wijzigen. Cron start zonder argumenten.
"""
import base64
import difflib
import fcntl
import hashlib
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bellen  # noqa: E402
import bord  # noqa: E402
import ochtend  # noqa: E402  de gedeelde inkortregel voor een antwoord van De Regisseur (REG-03)
import whatsapp  # noqa: E402

NAAM = "bode"
ag = bord.Agent(NAAM)
STAAT = os.path.expanduser("~/appportal/mijnagents-data/bode.json")
# De VM draait op UTC; de stille uren en het uur bovenaan een bericht zijn Brusselse tijd (Codex A23, 15-10-2026).
# Zelf gezet zoals calendly_wacht.py en koppelingen/taken.py: agenda_wacht importeren doet bij het laden een docker-aanroep.
BRUSSEL = ZoneInfo("Europe/Brussels")
STIL = (22, 7)
# "oproep": een agent vraagt uitdrukkelijk om Mehdi te bellen (sinds 26-09-2026 De Mailregisseur bij dringende mail).
# Dat vervangt voor nieuwe agents het woord "stil" in een signaaltitel, dat vroeger per ongeluk belde.
# "ochtendbericht": het bericht van De Regisseur met hoogstens vijf beslissingen; alleen ochtend_sturen verstuurt het (J4).
SOORTEN = ("signaal", "coaching", "verslag", "dagplan", "dagbundel", "ochtendbericht", "oproep")
# Keuze 1 van Mehdi (21-10-2026, in de chat met Claude; ontwerp regie-zoom v1.2, 13.4): optie A, twee vaste momenten.
# 'ochtend-avond': het ochtendbericht en rond 17:00 de avondbundel; wat kan wachten zit in een van die twee, alleen
# oproepen, alarmen en het bellen voor afspraken komen meteen. 'uit' is de terugval: alles los, zoals voor die dag.
# Bij elke omschakeling verdwijnt niets: naar de bundelstand begint de bundel na het laatste losse bericht (bundel_begin),
# terug naar 'uit' gaat eerst een slotbundel (slotbundel_sturen). Terugdraaien is deze ene regel, in dezelfde commit als werkwijze/bode.md, AGENTNORM hoofdstuk 6 en de docstring van
# mail_regisseur.py (tests/test_bode_regie.py, T77, houdt code en werkwijze gelijk). Optie C ('ochtend', een bericht per
# dag) is niet gebouwd; een onbekende stand werkt als 'uit', want daar verdwijnt niets.
BUNDELEN = "ochtend-avond"
BUNDEL_STANDEN = ("uit", "ochtend-avond")
TERUGVAL = (11, 0)            # Brussel: geen ochtendbericht van De Regisseur, dan een terugval met de aantallen (I7, I9)
AVOND_TRIGGER = "mailupdate:{datum}:17:00"   # de update van 17:00 van De Mailregisseur (mail_regisseur.py, UPDATES)
AVOND_VANAF = (17, 0)
AVOND_UITERLIJK = (17, 30)    # Brussel: ook zonder die update een avondbundel, als er iets gebundeld is
OCHTEND_VAN = "regisseur"     # alleen De Regisseur zet het ochtendbericht klaar (ontwerp regie-zoom v1.2, 4.2 en M6)
OCHTEND_DAGEN = 3             # zo lang bewaar ik de momentopname van een verstuurd ochtendbericht (B6)
BORD_URL = "https://mijnagents.globaal.be"
WEEKDAG = ("ma", "di", "wo", "do", "vr", "za", "zo")
# Hoogstens zoveel items in een bericht; de rest volgt de volgende ronde, een minuut later (Codex A31, 15-10-2026).
PER_BERICHT = 8
# Zoveel klaarzet-items vraag ik per ronde op; het bord levert de nieuwste eerst (mijnagents/app.py, /api/klaarzet).
KLAARZET_N = 200
# Mehdi, 25-09-2026: "stuur mij geen domme berichten over mijn agenda op mijn Telegram; heel mijn ding is
# visueel gemaakt". Wat deze agents klaarzetten blijft op het bord en in de agenda zelf, maar gaat niet naar
# Telegram. Een oproep (belrooster, vastzitten) blijft wel gewoon werken.
NIET_OP_TELEGRAM = tuple(x.strip() for x in os.environ.get("BODE_NIET_OP_TELEGRAM", "agenda-wacht,calendly-wacht").split(",") if x.strip())
ZOOM_ENV = os.path.expanduser("~/pipedrive-won-deals/.env")
# Zonder aantal (N10): zolang het venster dicht is en er geen sjabloon is, staat deze nood open.
WA_NOOD = ("WhatsApp mag je pas schrijven na een bericht van jou: stuur iets naar het agentennummer "
           "(UNABO Assistant, +32 460 23 30 42); tot dan gaat het via Telegram")
WA_KORT = ("start", "/start", "test", "hallo", "hoi", "hey", "hi", "hello", "goeiedag", "goedemorgen")


def laad_env(pad, zonder=()):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                if k.strip() not in zonder:
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/appportal/mijnagents-data/.env")
# L2 (ontwerp regie-zoom v1.2): uit ~/pipedrive-won-deals/.env alleen de sleutels van de gedeelde Zoom-app, niet wie
# er een Zoom-chat stuurt of krijgt. Dat bestand hoort bij een andere toepassing; afzender en ontvanger staan alleen
# in mijnagents-data/.env, en anders is er geen Zoom-chat.
laad_env(ZOOM_ENV, zonder=("ZOOM_SENDER", "ZOOM_MELDING_CONTACT"))
TG_TOKEN, TG_CHAT = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")


def nu():
    """Nu, in Brusselse tijd. Een functie, zodat een test de klok kan vastzetten."""
    return datetime.now(BRUSSEL)


def stand_bundelen():
    """De stand van BUNDELEN; een onbekende stand werkt als 'uit' (daar verdwijnt niets)."""
    return BUNDELEN if BUNDELEN in BUNDEL_STANDEN else "uit"


# ---------------------------------------------------------------- kanalen ---
def tg(methode, **params):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TG_TOKEN}/{methode}", data=json.dumps(params).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.load(r)


def stuur_telegram(tekst):
    if not (TG_TOKEN and TG_CHAT):
        raise RuntimeError("geen Telegram-token")
    for stuk in [tekst[i:i + 3900] for i in range(0, len(tekst), 3900)] or [""]:
        tg("sendMessage", chat_id=TG_CHAT, text=stuk, disable_web_page_preview=True)
    return "telegram"


def zoom_token():
    basis = base64.b64encode(f"{os.environ['ZOOM_CLIENT_ID']}:{os.environ['ZOOM_CLIENT_SECRET']}".encode()).decode()
    url = "https://zoom.us/oauth/token?" + urllib.parse.urlencode({"grant_type": "account_credentials", "account_id": os.environ["ZOOM_ACCOUNT_ID"]})
    with urllib.request.urlopen(urllib.request.Request(url, method="POST", headers={"Authorization": "Basic " + basis}), timeout=20) as r:
        return json.load(r)["access_token"]


def stuur_zoom(tekst):
    sender, ontvanger = os.environ.get("ZOOM_SENDER", ""), os.environ.get("ZOOM_MELDING_CONTACT", "")
    if not (sender and ontvanger and os.environ.get("ZOOM_CLIENT_ID")):
        raise RuntimeError("Zoom-koppeling niet ingesteld")
    req = urllib.request.Request(f"https://api.zoom.us/v2/chat/users/{urllib.parse.quote(sender)}/messages",
                                 data=json.dumps({"to_contact": ontvanger, "message": tekst}).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + zoom_token(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20):
        return "zoom"


def met_kop(tekst, kop):
    """De kop als eerste regel, voor de kanalen zonder aparte kop (Telegram, Zoom-chat; B2). Niet voor de gewone kop,
    en niet als de tekst er al mee begint."""
    if not kop or kop == whatsapp.STANDAARD_KOP or tekst.lstrip().startswith(kop):
        return tekst
    return f"{kop}\n\n{tekst}"


def stuur(tekst, nood, kop="je agents", voorrang=False, antwoord=False):
    # Mehdi, 30-09-2026: WhatsApp in plaats van Telegram. Telegram blijft het vangnet
    # zolang het WhatsApp-venster dicht kan zijn zonder goedgekeurd sjabloon.
    # kop: de eerste parameter van het sjabloon; voor Telegram en Zoom-chat de eerste regel (B2).
    # voorrang: een vast moment (ochtendbericht, terugval, avondbundel) mag in de reserve onder het dagplafond (B7).
    # antwoord: een antwoord op een vraag van Mehdi gaat nooit via Zoom-chat (L2).
    try:
        return whatsapp.stuur(tekst, kop=kop, voorrang=voorrang)
    except whatsapp.NietBeschikbaar as e:
        nood.append({"tekst": WA_NOOD if "venster" in str(e) else f"WhatsApp: {e}", "wie": "mehdi"})
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"WhatsApp sturen mislukt: {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"})
    try:
        return stuur_telegram(met_kop(tekst, kop))
    except Exception as e:  # noqa: BLE001
        if not TG_TOKEN:
            nood.append({"tekst": "Telegram niet ingesteld: bot bij BotFather, TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID in mijnagents-data/.env", "wie": "mehdi"})
        else:
            nood.append({"tekst": f"Telegram sturen mislukt: {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"})
    if antwoord:
        return ""
    try:
        return stuur_zoom(met_kop(tekst, kop))
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"Zoom-chat mislukt: {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"})
    return ""


def platte_tekst(md):
    t = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    return t.strip()


def sjabloonlengte(tekst):
    """Hoe lang de tekst is als sjabloonparameter, voor whatsapp.plat hem afknipt: de grens is whatsapp.MAX_PARAM."""
    return len(whatsapp.plat(tekst, None))


# ---------------------------------------------------------- van Mehdi ---
def agentnamen():
    try:
        return {a["naam"]: a["label"] for a in bord.call("/api/overzicht").get("agents", [])}
    except Exception:  # noqa: BLE001
        return {}


# Een agent aanspreken (B3, ontwerp regie-zoom v1.2). De kop is de tekst voor de eerste dubbelepunt, komma of los
# koppelteken tussen spaties, 2 tot 60 tekens, met een @ vooraan als hij wil. Tot 21-10-2026 gingen "Zoomwacht, ..." en
# "Mailregisseur, ..." naar De Regisseur, en hing de uitkomst af van de volgorde van /api/overzicht: 104 afwijkingen over
# 50 volgordes, gemeten met de 40 labels van het bord.
KOP = re.compile(r"^\s*@?(?P<kop>[^\n:,]{2,60}?)\s*(?::|,|\s-\s)\s*(?P<vraag>\S.*)$", re.S)
LIDWOORDEN = ("de", "het")
# Mehdi dicteert met spraakherkenning ("Zoemwacht"). Een bijna-match alleen als er geen enkele kandidaat is, voor een kop
# van minstens BIJNA_MIN tekens, en alleen bij precies een agent (I6, G4); de bevestiging noemt de gekozen agent.
BIJNA = 0.85
BIJNA_MIN = 5


def _ascii(s):
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()


def kopwoorden(kop):
    """De woorden van een kop of naam als (genormaliseerd, einde in de tekst): accenten weg, kleine letters, alleen
    letters en cijfers, zonder "de" of "het" vooraan."""
    uit = []
    for m in re.finditer(r"[^\W_]+", kop or ""):
        w = re.sub(r"[^a-z0-9]", "", _ascii(m.group()))
        if w:
            uit.append((w, m.end()))
    while uit and uit[0][0] in LIDWOORDEN:
        uit = uit[1:]
    return uit


def sleutels(namen):
    """{sleutel: {agentnamen}} uit de naam en het label van elke agent: zoom-wacht en De Zoomwacht geven allebei
    zoomwacht. Een sleutel kan bij meer dan een agent horen; dan kiest doel_van er geen."""
    uit = {}
    for naam, label in namen.items():
        for s in (naam, label):
            k = "".join(w for w, _ in kopwoorden(s))
            if k:
                uit.setdefault(k, set()).add(naam)
    return uit


def doel_en_kandidaten(tekst, namen):
    """(agent, vraag, kandidaten) voor een bericht van Mehdi (B3), in deze volgorde:
      1. het langste woordvoorvoegsel van de kop dat precies een sleutel is van een agent: die agent, en wat er van de
         kop overblijft, komt vooraan de vraag;
      2. is er geen enkele kandidaat (geen sleutel, en de kop is van geen sleutel het begin): een bijna-match met
         difflib, alleen bij precies een agent;
      3. anders, ook als een sleutel bij meer dan een agent hoort of de kop het begin is van sleutels: De Regisseur, met
         de volle tekst, en de kandidaten voor de bevestiging.
    De uitkomst hangt niet af van de volgorde van namen."""
    tekst = (tekst or "").strip()
    m = KOP.match(tekst)
    if not m:
        return "regisseur", tekst, []
    woorden = kopwoorden(m.group("kop"))
    idx = sleutels(namen)
    if not idx:
        return "regisseur", tekst, []         # het bord gaf geen namen: niemand te herkennen, De Regisseur kijkt
    for j in range(len(woorden), 0, -1):
        hit = idx.get("".join(w for w, _ in woorden[:j]))
        if hit and len(hit) == 1:
            rest = re.sub(r"^[^\w]+", "", m.group("kop")[woorden[j - 1][1]:]).strip()
            vraag = (rest + tekst[m.end("kop"):]).strip() if rest else m.group("vraag").strip()
            return next(iter(hit)), vraag, []
        if hit:
            return "regisseur", tekst, sorted(hit)
    kop = "".join(w for w, _ in woorden)
    kandidaten = sorted({n for s, ns in idx.items() if kop and s.startswith(kop) for n in ns})
    if kandidaten:
        return "regisseur", tekst, kandidaten
    if len(kop) >= BIJNA_MIN:
        bijna = sorted({n for s in difflib.get_close_matches(kop, sorted(idx), n=len(idx), cutoff=BIJNA) for n in idx[s]})
        if len(bijna) == 1:
            return bijna[0], m.group("vraag").strip(), []
        return "regisseur", tekst, bijna
    return "regisseur", tekst, []


def doel_van(tekst, namen):
    """'Zoomwacht, wat is er vanochtend afgesproken?' -> ('zoom-wacht', 'wat is er vanochtend afgesproken?'); past de kop
    op geen of op meer dan een agent, dan De Regisseur met de volle tekst (B3)."""
    aan, vraag, _ = doel_en_kandidaten(tekst, namen)
    return aan, vraag


def bevestiging(tekst, namen):
    """De zin waarmee ik een bericht van Mehdi bevestig: wie ernaar kijkt, en als zijn kop op meer agents past, dat hij
    de volle naam kan noemen. Zo is een vergissing meteen zichtbaar en kost ze alleen een leesvraag (I6)."""
    aan, _, kandidaten = doel_en_kandidaten(tekst, namen)
    wie = namen.get(aan) or ("De Regisseur" if aan == "regisseur" else aan)
    if not kandidaten:
        return f"Ontvangen, {wie} kijkt ernaar."
    m = KOP.match((tekst or "").strip())
    kop = m.group("kop").strip() if m else ""
    if len(kandidaten) == 1:
        return f"Ontvangen. {kop} past op {namen.get(kandidaten[0], kandidaten[0])}, niet op de volle naam; {wie} kijkt ernaar."
    return f"Ontvangen. {kop} past op {len(kandidaten)} agents; {wie} kijkt ernaar."


def lees_telegram(staat, namen):
    """Nieuwe berichten van Mehdi -> gesprek op het bord. Geeft aantal.
    De offset schuift pas op na een geslaagde bordaanroep: main vangt een storing nu op en schrijft de stand toch weg
    (Codex A26, 15-10-2026), en dan mag het bericht niet verloren gaan; de volgende ronde leest het opnieuw.
    In het werkverslag alleen de lengte van de vraag, nooit de tekst (H1)."""
    if not TG_TOKEN:
        return 0
    d = tg("getUpdates", offset=staat.get("tg_offset", 0), timeout=0, allowed_updates=["message"])
    n, zinnen = 0, []
    for u in d.get("result", []):
        m = u.get("message") or {}
        tekst = (m.get("text") or "").strip()
        if str(m.get("chat", {}).get("id")) == str(TG_CHAT) and tekst and not tekst.startswith("/start"):
            aan, vraag = doel_van(tekst, namen)
            uit = bord.call("/api/gesprek", {"aan": aan, "tekst": vraag, "van": "mehdi (telegram)"})
            staat.setdefault("wacht", []).append({"id": uit["id"], "aan": uit["aan"]})
            ag.log(f"bericht {uit['id']}", "bron", f"uit Telegram aan {namen.get(uit['aan'], uit['aan'])}, {len(vraag)} tekens")
            n += 1
            zin = bevestiging(tekst, namen)
            if zin not in zinnen:
                zinnen.append(zin)
        staat["tg_offset"] = u["update_id"] + 1
    if n:
        try:
            stuur_telegram(" ".join(zinnen) + " Antwoord binnen een paar minuten.")
        except Exception:  # noqa: BLE001
            pass
    return n


def lees_whatsapp(staat, namen, nood):
    """Nieuwe WhatsApp-berichten van Mehdi aan het agentennummer -> gesprek op het bord.
    De WhatsApp-app bewaart ze (whatsapp.bericht); ik lees daar, alleen lezend. Geeft aantal.
    In het werkverslag alleen de lengte van de vraag, nooit de tekst (H1)."""
    try:
        nieuw = whatsapp.binnen(staat.get("wa_laatste_id", 0))
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"WhatsApp lezen mislukt: {type(e).__name__}", "wie": "claude-code"})
        return 0
    if "wa_laatste_id" not in staat:
        # eerste ronde: alleen de stand onthouden, geen oude berichten opnieuw op het bord
        staat["wa_laatste_id"] = max([m["id"] for m in nieuw] or [0])
        return 0
    n, zinnen = 0, []
    for m in nieuw:
        tekst = (m.get("tekst") or "").strip()
        if tekst and tekst.lower() in WA_KORT:
            stuur("WhatsApp staat aan: de meldingen van je agents komen voortaan hier. Antwoord gewoon; begin met de "
                  "naam van een agent en een komma om hem rechtstreeks te spreken (Zoomwacht, ...).", nood)
        elif tekst:
            aan, vraag = doel_van(tekst, namen)
            # gooit het bord een fout, dan blijft wa_laatste_id voor dit bericht staan: volgende ronde opnieuw (A26)
            uit = bord.call("/api/gesprek", {"aan": aan, "tekst": vraag, "van": "mehdi (whatsapp)"})
            staat.setdefault("wacht", []).append({"id": uit["id"], "aan": uit["aan"]})
            ag.log(f"bericht {uit['id']}", "bron", f"uit WhatsApp aan {namen.get(uit['aan'], uit['aan'])}, {len(vraag)} tekens")
            n += 1
            zin = bevestiging(tekst, namen)
            if zin not in zinnen:
                zinnen.append(zin)
        staat["wa_laatste_id"] = max(staat["wa_laatste_id"], m["id"])
    if n:
        stuur(" ".join(zinnen) + " Antwoord binnen een paar minuten.", nood)
    return n


def antwoorden_terug(staat, namen, nood):
    """Beantwoorde berichten uit het bord -> Mehdi, nooit via Zoom-chat (L2). In het werkverslag alleen hoe lang het
    antwoord was (H1): het werkverslag gaat via de export naar Dropbox, het antwoord zelf blijft op het bord.
    Het volle antwoord staat in gesprek.antwoord; naar WhatsApp gaat het ingekort tot hoogstens 800 tekens met de regel
    van De Regisseur (ochtend.whatsapp_kort), met de verwijzing naar de pagina van de agent en de regel Gelezen als
    laatste (R6, REG-03). Een kort antwoord gaat ongewijzigd."""
    klaar, rest = 0, []
    for w in staat.get("wacht", []):
        try:
            g = bord.call(f"/api/gesprek/{w['id']}").get("gesprek", {})
        except Exception:  # noqa: BLE001
            rest.append(w); continue
        if g.get("status") in ("beantwoord", "mislukt"):
            kop = namen.get(w["aan"], "De Regisseur")
            kort = ochtend.whatsapp_kort(g.get("antwoord") or "(geen antwoord)", w["aan"])
            if stuur(f"{kop}:\n\n{platte_tekst(kort)}", nood, antwoord=True):
                klaar += 1
                ag.log(f"bericht {w['id']}", "melding", f"antwoord van {kop} naar Mehdi, {len(g.get('antwoord') or '')} tekens")
            else:
                rest.append(w)
        else:
            rest.append(w)
    staat["wacht"] = rest
    return klaar


# ------------------------------------------------------------------ main ---
def is_stil(t=None):
    """Stille uren (STIL, 22:00 tot 07:00) op Brusselse tijd. De VM draait op UTC: met datetime.now().hour begon de
    stilte in de zomer pas om middernacht en eindigde ze om 09:00 (Codex A23, 15-10-2026). t: een tijdstip met zone;
    zonder zone telt het als de klok van deze machine."""
    uur = (t or datetime.now(BRUSSEL)).astimezone(BRUSSEL).hour
    return uur >= STIL[0] or uur < STIL[1]


def slot_nemen():
    """Een ronde tegelijk, anders None (het patroon van agenda_signaal.slot_nemen). Cron start mij elke minuut; met
    time-outs bij Telegram, het bord of Twilio duurt een ronde soms langer, en dan las een tweede ronde dezelfde stand
    en belde ze opnieuw voor dezelfde afspraak (Codex A26, 15-10-2026)."""
    os.makedirs(os.path.dirname(STAAT), exist_ok=True)
    f = open(STAAT + ".lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        f.close()
        return None
    return f


def bewaar(staat):
    """Atomair, zoals agenda_signaal.bewaar: eerst een tijdelijk bestand naast de stand, dan os.replace. Vroeger
    json.dump in een open(STAAT, "w"): een fout of crash midden in het schrijven liet een half bode.json na, de
    volgende ronde las dat als leeg en belde opnieuw wat al gebeld was (Codex A26, 15-10-2026). Ook de callback die
    bellen.afspraken_bellen na elke oproep aanroept."""
    tekst = json.dumps(staat)
    os.makedirs(os.path.dirname(STAAT), exist_ok=True)
    tmp = f"{STAAT}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w") as f:
            f.write(tekst)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STAAT)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def lees_staat():
    """De stand uit bode.json. Oude sleutels (laatste_herinnering, laatste_voorstellen van voor 21-10-2026) storen niet.
    Nieuw (B6): ochtend en avond per Brusselse datum, hoogstens OCHTEND_DAGEN bewaard, en bundel_vanaf. Is de stand er
    niet of niet te lezen, dan begint de bundel 24 uur terug (B5): wat in die tijd binnenkwam, komt zo nog mee.
    Alleen zolang het nodig is: bundel_tot (terug naar 'uit', tot de slotbundel weg is, BOD-2) en alarm_gemeld (alarmen
    die al een bericht kregen terwijl laatste_id voor een ochtendbericht bleef staan, BOD-3)."""
    try:
        return json.load(open(STAAT))
    except (OSError, ValueError):
        return {"laatste_id": 0, "tg_offset": 0, "wacht": [], "ochtend": {}, "avond": {},
                "bundel_vanaf": (nu() - timedelta(hours=24)).astimezone(timezone.utc).isoformat()}


def belspoor():
    """Het belspoor naast de stand (bode-gebeld.jsonl): een regel per afgehandelde afspraakoproep, zie bellen.py. Lukt
    het wegschrijven van de stand na een oproep niet, dan weet de volgende ronde via dit spoor toch dat er gebeld is
    (Codex A26 ronde 3, 15-10-2026)."""
    return os.path.splitext(STAAT)[0] + "-gebeld.jsonl"


def nieuwe_items(bord_items, staat, nood):
    """De nieuwe klaarzet-items (id boven laatste_id, soort in SOORTEN), OPLOPEND op id. Het bord levert ze dalend
    (ORDER BY id DESC); vroeger nam ik daarvan items[-8:], de oudste acht, maar bewaarde ik het hoogste id als gelezen:
    het negende en verdere kregen nooit een bericht (Codex A31, 15-10-2026). Een volle pagina waarvan zelfs het oudste
    item nog nieuw is, kan nieuwe items missen die eronder vallen (het bord kent geen 'vanaf id'): dat wordt een nood."""
    laatste = staat.get("laatste_id", 0)
    if not laatste and len(bord_items) >= KLAARZET_N:
        # zonder stand en een volle pagina: een recent alarm kan onder de pagina vallen (Codex A36, ronde 6)
        nood.append({"tekst": f"De Bode had geen leesbare stand en het bord gaf een volle pagina ({KLAARZET_N}): een oproep of "
                              "dringend signaal kan erbuiten vallen; kijk het bord na", "wie": "claude-code"})
    if laatste and len(bord_items) >= KLAARZET_N and min(it["id"] for it in bord_items) > laatste:
        nood.append({"tekst": f"Meer dan {KLAARZET_N} nieuwe klaarzet-items voor Mehdi sinds de vorige ronde: de oudste "
                              "haalt De Bode niet op en ze krijgen geen bericht; kijk het bord na", "wie": "claude-code"})
    return sorted((it for it in bord_items if it["id"] > laatste and it["soort"] in SOORTEN), key=lambda it: it["id"])


def is_alarm(it):
    """Een oproep, of een signaal met "stil" in de titel (AGENTNORM 6): ik bel, en het bericht gaat meteen, ook in de
    stille uren en in de bundelstand (T74)."""
    return it["soort"] == "oproep" or (it["soort"] == "signaal" and "stil" in (it.get("titel") or "").lower())


def apart(it, stand="uit"):
    """Hoort dit item niet in het gewone bericht van deze ronde (B4)? Een agendazaak (NIET_OP_TELEGRAM, gaat niet naar
    Mehdi), elk ochtendbericht (dat verstuurt alleen ochtend_sturen, J4), en in de bundelstand alles wat geen alarm is:
    dat is bundelwerk en komt op een vast moment mee, op tijdvenster."""
    return (it.get("van") in NIET_OP_TELEGRAM or it.get("soort") == "ochtendbericht"
            or (stand != "uit" and not is_alarm(it)))


def ochtend_afgehandeld(it, staat):
    """Telt dit ochtendbericht als afgehandeld voor laatste_id (J4)? Als het niet meer op klaar staat, als ik het
    verstuurde (staat['ochtend'][datum] heeft verzonden), of als ik het als verlopen opzij zette."""
    if it.get("status", "klaar") != "klaar":
        return True
    for datum, dag in (staat.get("ochtend") or {}).items():
        if not isinstance(dag, dict):
            continue
        if it.get("id") in (dag.get("verlopen") or []):
            return True
        if dag.get("verzonden") and (dag.get("klaarzet_id") == it.get("id") or it.get("uniek") == f"ochtendbericht:{datum}"):
            return True
    return False


def melding_groep(items, eerste=False, staat=None, stand=None):
    """Welke nieuwe items in dit bericht gaan, en tot welk id ze na een geslaagde verzending als gelezen tellen.
    items: oplopend (nieuwe_items). Geeft (groep, tot, rest):
      groep  hoogstens PER_BERICHT items voor Mehdi, de oudste eerst; in de bundelstand alleen alarmen;
      tot    het id tot waar alles verstuurd of bewust afgehandeld is: de groep, plus wat apart is (agendazaken,
             bundelwerk, een verstuurd ochtendbericht) ertussen en erna, tot het eerste item dat niet meer in de groep
             past. Nooit voorbij een item dat niet verstuurd is: dat komt de volgende ronde (Codex A31). Ook niet voorbij
             een ochtendbericht dat nog niet weg is (J4); dat stuurt ochtend_sturen, nooit deze groep. Een alarm erachter
             gaat wel mee in de groep (BOD-3: een oproep komt meteen, ook als het ochtendbericht in de stille uren
             wacht); berichten() onthoudt het in staat['alarm_gemeld'] tot laatste_id erover schuift, en wat daar staat,
             telt hier als afgehandeld. Een gewoon item erachter wacht;
      rest   hoeveel items voor Mehdi na deze groep nog wachten.
    eerste: er is nog geen laatste_id (eerste ronde, of een onleesbare bode.json). Dan de nieuwste PER_BERICHT en de
    rest bewust als gelezen; anders kwam heel de geschiedenis van het bord in tientallen berichten terug. Een
    ochtendbericht van vandaag vindt ochtend_sturen dan toch, want dat zoekt het op zijn uniek."""
    staat = staat or {}
    stand = stand or stand_bundelen()
    gemeld = set(staat.get("alarm_gemeld") or [])
    voor_mehdi = [it for it in items if not apart(it, stand) and it["id"] not in gemeld]
    if eerste:
        return voor_mehdi[-PER_BERICHT:], (items[-1]["id"] if items else 0), max(0, len(voor_mehdi) - PER_BERICHT)
    groep, tot, wacht = [], 0, False
    for it in items:
        if it["id"] in gemeld:
            pass                     # al verstuurd achter een ochtendbericht dat toen nog niet weg was
        elif apart(it, stand):
            if it.get("soort") == "ochtendbericht" and not ochtend_afgehandeld(it, staat):
                wacht = True         # tot blijft ervoor staan
        elif not wacht or is_alarm(it):
            if len(groep) == PER_BERICHT:
                break
            groep.append(it)
        if not wacht:
            tot = it["id"]
    return groep, tot, len(voor_mehdi) - len(groep)


ALARM_RECENT_MIN = 30      # zonder stand: een alarm van het laatste halfuur is nieuw genoeg om te bellen (A34)


def ts_van(item):
    """Het tijdstip van een bord-item, met zone. Het bord zet ts (ISO); zonder zone is het UTC (de server).
    None als het onleesbaar is."""
    try:
        t = datetime.fromisoformat(str(item.get("ts") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def is_recent(item, nu=None):
    """Is dit bord-item van de laatste ALARM_RECENT_MIN minuten? Onleesbaar telt als niet recent: dan meld ik het in
    plaats van te bellen."""
    t = ts_van(item)
    if t is None:
        return False
    return (nu or datetime.now(timezone.utc)) - t <= timedelta(minutes=ALARM_RECENT_MIN)


def nog_niet_gebeld(staat, alarm):
    """De alarmen waarvoor nog geen oproep liep of openstaat. Sinds De Bode in groepen meldt (A31) blijft een alarm dat
    niet in de eerste groep zat een ronde langer nieuw; de lijst krimpt dan van voren, alarm_bellen zag een andere
    sleutel ('5|11' werd '11') en zou opnieuw bellen voor hetzelfde signaal. Item-id's lopen op: wat niet hoger is dan
    het hoogste id in de sleutel van de vorige of de openstaande oproep, was al aan de beurt (Codex A31, 15-10-2026)."""
    b = staat.get("bel") or {}
    gehad = 0
    for s in (b.get("sleutel"), (b.get("open") or {}).get("sleutel")):
        for d in str(s or "").split("|"):
            if d.strip().isdigit():
                gehad = max(gehad, int(d))
    return [it for it in alarm if int(it.get("id") or 0) > gehad]


def veilig(nood, wat, fn, standaard=0):
    """fn(), maar een storing bij Telegram, WhatsApp of het bord wordt een nood in plaats van een crash. Vroeger liet
    een fout in lees_telegram of bord.call main crashen voor er gebeld was (Codex A26, 15-10-2026)."""
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"{wat} mislukt: {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"})
        return standaard


# ------------------------------------------------------- vaste momenten ---
def dag_van(moment):
    """De Brusselse datum van een tijdstip, als JJJJ-MM-DD (de VM draait op UTC)."""
    return moment.astimezone(BRUSSEL).date().isoformat()


def na(moment, uur_minuut):
    b = moment.astimezone(BRUSSEL)
    return (b.hour, b.minute) >= uur_minuut


def meervoud(n, een, meer):
    return f"{n} {een if n == 1 else meer}"


def open_voorstellen(nood):
    """[(id, agent)] van de open voorstellen, uit de databank van het bord (bord.db_lees, alleen lezen, I3), of None als
    dat onbekend is. Onbekend is niet leeg: dan meld ik geen nieuw voorstel en zeg ik "onbekend" (L29)."""
    try:
        return [(int(r["id"]), r["naam"]) for r in bord.db_lees("SELECT id, naam FROM voorstel WHERE status='open' ORDER BY id")]
    except bord.BordOnbekend:
        nood.append({"tekst": "Open voorstellen niet leesbaar uit de databank van het bord", "wie": "claude-code"})
        return None


def nieuwe_voorstellen(staat, voorstellen):
    """De open voorstellen met een hoger id dan het hoogste dat ik al meldde (L8: op het id, niet op het aantal; een
    gesloten en een nieuw voorstel in dezelfde dag gaven anders geen bericht). Zonder stand leer ik het hoogste id
    zonder bericht, anders kwam bij elke verloren stand alles terug. Onbekend (None): niets."""
    if voorstellen is None:
        return []
    if not isinstance(staat.get("voorstel_hoogste"), int):
        staat["voorstel_hoogste"] = max((i for i, _ in voorstellen), default=0)
        return []
    return [(i, n) for i, n in voorstellen if i > staat["voorstel_hoogste"]]


def voorstellen_gemeld(staat, voorstellen):
    if voorstellen:
        staat["voorstel_hoogste"] = max([staat.get("voorstel_hoogste") or 0] + [i for i, _ in voorstellen])


def ochtend_voorstellen_gemeld(staat, inhoud):
    """Na het ochtendbericht telt als gemeld wat De Regisseur telde toen hij het opstelde: bronnen.voorstellen.
    hoogste_voorstel (koppelingen/ochtend.py). Ontbreekt die waarde (hij kon de voorstellen niet lezen), dan niets (BOD-5).
    Tot 21-10-2026 telde elk voorstel dat op het moment van versturen open stond, ook een dat na het opstellen bijkwam:
    dat kreeg in 'uit' geen bericht en stond niet in de avondbundel, en kwam pas de volgende ochtend."""
    hoogste = ((inhoud.get("bronnen") or {}).get("voorstellen") or {}).get("hoogste_voorstel")
    if isinstance(hoogste, int) and not isinstance(hoogste, bool):
        staat["voorstel_hoogste"] = max(staat.get("voorstel_hoogste") or 0, hoogste)


def voorstel_regels(nieuw, namen):
    """Een regel per agent met nieuwe voorstellen, voor het bericht in de stand 'uit' en de avondbundel."""
    per = {}
    for _, naam in nieuw:
        per[naam] = per.get(naam, 0) + 1
    return [f"- {meervoud(n, 'nieuw voorstel', 'nieuwe voorstellen')} van {namen.get(naam, naam)} "
            f"{'wacht' if n == 1 else 'wachten'} op je goedkeuring" for naam, n in sorted(per.items())]


def noden_voor_mehdi():
    """Hoeveel noden voor Mehdi open staan (/api/nood), of None als het bord het niet zegt."""
    try:
        rijen = bord.call("/api/nood").get("nood")
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(rijen, list):
        return None
    return sum(1 for r in rijen if isinstance(r, dict) and (r.get("wie") or "mehdi") == "mehdi")


def is_bundelwerk(it):
    """Wat in de bundelstand op een vast moment meekomt: een item voor Mehdi dat geen alarm, geen ochtendbericht en
    geen agendazaak is."""
    return (it.get("soort") in SOORTEN and it.get("soort") != "ochtendbericht" and not is_alarm(it)
            and it.get("van") not in NIET_OP_TELEGRAM)


def bundelwerk(bord_items, staat):
    """(items, volledig): het bundelwerk sinds staat['bundel_vanaf'], oudste eerst. (None, False) als het bord niet
    gelezen is: onbekend is niet leeg. volledig is onwaar als de pagina van het bord vol was en zelfs het oudste item nog
    in het venster valt; dan kan er meer zijn, en zegt de bundel dat."""
    if bord_items is None:
        return None, False
    try:
        vanaf = datetime.fromisoformat(staat.get("bundel_vanaf") or "")
    except ValueError:
        return [], True
    if vanaf.tzinfo is None:
        vanaf = vanaf.replace(tzinfo=timezone.utc)
    binnen = [it for it in bord_items if is_bundelwerk(it) and ts_van(it) is not None and ts_van(it) > vanaf]
    oudste = min((t for t in (ts_van(it) for it in bord_items) if t is not None), default=None)
    volledig = not (len(bord_items) >= KLAARZET_N and oudste is not None and oudste > vanaf)
    return sorted(binnen, key=lambda it: it["id"]), volledig


def bundel_begin(staat, bord_items, moment):
    """Waar de bundel begint bij de overgang naar de bundelstand (BOD-1): na het jongste item dat al los afgehandeld is
    (id tot en met laatste_id), want wat daarna kwam, ging nog niet weg. Staat er zo geen item op de pagina, dan 24 uur
    terug, zoals lees_staat. Tot 21-10-2026 begon de bundel bij de eerste ronde in de bundelstand: wat in de stille uren
    was blijven liggen, of tussen de laatste losse ronde en de uitrol binnenkwam, telde meteen als afgehandeld en kwam in
    geen enkele bundel."""
    laatste = staat.get("laatste_id") or 0
    tijden = [t for t in (ts_van(it) for it in bord_items if it["id"] <= laatste) if t is not None]
    begin = max(tijden) if tijden else moment - timedelta(hours=24)
    return begin.astimezone(timezone.utc).isoformat()


def kort_item(it, namen):
    """Een bundelitem in een paar woorden: "mailupdate 08:00", "dagverslag", "signaal van De Normwacht"."""
    m = re.match(r"^mailupdate:\d{4}-\d{2}-\d{2}:(\d{2}:\d{2})$", str(it.get("uniek") or ""))
    if m:
        return f"mailupdate {m.group(1)}"
    if it.get("soort") == "dagbundel":
        return "dagverslag"
    if it.get("soort") in ("dagplan", "coaching"):
        return it["soort"]
    return f"{it.get('soort')} van {namen.get(it.get('van'), it.get('van'))}"


def bundelregel(tekst, bundel, volledig, namen):
    """De regel "Gebundeld: ..." onder een vast bericht (B5): wat sinds de vorige bundel binnenkwam, zo kort dat de hele
    tekst als sjabloonparameter binnen whatsapp.MAX_PARAM (900) blijft. De Regisseur houdt zijn deel op 720 (I1); ik
    voeg alleen deze regel toe. Eerst met namen, anders alleen de aantallen; leeg als er niets gebundeld is of zelfs de
    aantallen niet passen. Een onleesbaar bord is "onbekend", nooit "niets"."""
    if bundel is None:
        kandidaten = ["Gebundeld: onbekend, het bord was niet te lezen; alles op het bord"]
    elif not bundel:
        return ""
    else:
        delen, tel = [], {}
        for it in bundel:
            k = kort_item(it, namen)
            if k not in tel:
                delen.append(k)
            tel[k] = tel.get(k, 0) + 1
        lijst = ", ".join(k if tel[k] == 1 else f"{k} ({tel[k]})" for k in delen)
        minstens = "" if volledig else "minstens "
        kandidaten = [f"Gebundeld: {lijst}{'' if volledig else ' en mogelijk meer'}; alles op het bord",
                      f"Gebundeld: {minstens}{meervoud(len(bundel), 'bericht', 'berichten')} van "
                      f"{meervoud(len({it.get('van') for it in bundel}), 'agent', 'agents')}, op het bord",
                      f"Gebundeld: {minstens}{meervoud(len(bundel), 'bericht', 'berichten')}, op het bord"]
    for regel in kandidaten:
        if sjabloonlengte(f"{tekst}\n{regel}") <= whatsapp.MAX_PARAM:
            return regel
    return ""


def ochtend_inhoud(it):
    """De inhoud van een ochtendbericht als dict (het bord bewaart ze als JSON-tekst), of {} als ze onleesbaar is.
    Ik lees er alleen tekst en punten uit (contract met De Regisseur, ontwerp regie-zoom v1.2, 4.2)."""
    inhoud = it.get("inhoud")
    if isinstance(inhoud, str):
        try:
            inhoud = json.loads(inhoud)
        except ValueError:
            return {}
    return inhoud if isinstance(inhoud, dict) else {}


def ochtend_fout(it, datum):
    """Waarom dit ochtendbericht niet verstuurd mag worden, of None: alleen van De Regisseur, alleen voor Mehdi, alleen
    met de Brusselse datum van vandaag in de uniek, en met een tekst (J4, T71)."""
    if it.get("van") != OCHTEND_VAN:
        return f"afzender {it.get('van')}"
    if it.get("voor") not in (None, "mehdi"):
        return f"voor {it.get('voor')}"
    if it.get("uniek") != f"ochtendbericht:{datum}":
        return f"datum {str(it.get('uniek') or '')[len('ochtendbericht:'):] or 'onbekend'}"
    if not str(ochtend_inhoud(it).get("tekst") or "").strip():
        return "geen tekst"
    return None


def ochtend_verlopen(staat, datum, droog=False):
    """De ochtendberichten op klaar die ik niet mag versturen: van een andere afzender, van een andere dag of zonder
    tekst. Ik stuur ze niet, zet ze op opgepakt als verlopen en onthoud ze bij vandaag, zodat de nood de hele dag blijft
    staan (J4, T71). Gevonden via soort=ochtendbericht&status=klaar. Geeft hun id's."""
    q = urllib.parse.urlencode({"voor": "mehdi", "soort": "ochtendbericht", "status": "klaar", "n": 20})
    dag = staat.setdefault("ochtend", {}).setdefault(datum, {})
    uit = []
    for it in bord.call(f"/api/klaarzet?{q}").get("items", []):
        if it.get("soort") != "ochtendbericht" or it.get("status", "klaar") != "klaar":
            continue
        reden = ochtend_fout(it, datum)
        if reden is None:
            continue
        uit.append(it["id"])
        if droog:
            print(f"  (droog) ochtendbericht {it['id']} niet versturen ({reden}); zou het opzij zetten als verlopen")
            continue
        bord.opgepakt(it["id"], f"{NAAM}: verlopen, niet verstuurd")
        if it["id"] not in dag.setdefault("verlopen", []):
            dag["verlopen"].append(it["id"])
        ag.log(f"ochtendbericht {datum}", "besluit", f"item {it['id']} niet verstuurd ({reden}); opgepakt als verlopen")
    return uit


def ochtend_item(datum):
    """Het ochtendbericht voor deze Brusselse datum: alleen het item met precies die uniek (/api/klaarzet?uniek=...,
    ook als het al opgepakt is), of None."""
    uniek = f"ochtendbericht:{datum}"
    q = urllib.parse.urlencode({"uniek": uniek, "status": "alle", "n": 5})
    items = [it for it in bord.call(f"/api/klaarzet?{q}").get("items", [])
             if it.get("uniek") == uniek and it.get("soort") == "ochtendbericht"]
    return items[0] if items else None


def ochtend_sturen(staat, nood, moment, namen, stand, bord_items, voorstellen, droog=False, gelezen=None):
    """Het ochtendbericht van De Regisseur naar Mehdi, als eigen bericht (B5, J4, M6). Alleen hier gaat het weg: van De
    Regisseur, met de datum van vandaag, op klaar. De tekst is inhoud.tekst; in de bundelstand komt de regel
    "Gebundeld: ..." erbij, behalve na een terugval (die droeg de bundel al). Met de titel als kop en met voorrang.
    Na het versturen bewaar ik een momentopname (punten, ref, vingerafdruk van de verstuurde tekst) in staat['ochtend']
    en stuur ik voor die datum nooit een tweede keer (M6); daarna pas zet ik het item op opgepakt. Mislukt het sturen,
    dan verschuift er niets en probeert de volgende ronde opnieuw.
    Een verkeerd item zet ik elke ronde opzij, ook nadat het ochtendbericht van vandaag weg is (BOD-3): tot 21-10-2026
    bleef het dan tot middernacht op klaar, en wachtte elk bericht erachter, ook dat van een oproep.
    Geeft (uitkomst, detail): verstuurd, eerder, mislukt, wacht, droog of geen."""
    datum = dag_van(moment)
    dag = staat.setdefault("ochtend", {}).setdefault(datum, {})
    try:
        ochtend_verlopen(staat, datum, droog)
    except Exception as e:  # noqa: BLE001
        # onbekend is niet leeg: of er een verkeerd item klaarstaat, weet ik dan niet
        nood.append({"tekst": f"Ochtendberichten op klaar niet te lezen: {type(e).__name__}", "wie": "claude-code"})
    if dag.get("verzonden"):
        if not dag.get("opgepakt") and dag.get("klaarzet_id") and not droog:
            ochtend_oppakken(dag, nood)
        return "eerder", ""
    it = ochtend_item(datum)
    if it is None or ochtend_fout(it, datum):
        return "geen", ""
    if it.get("status") != "klaar":
        # opgepakt zonder dat mijn stand het weet (een verloren bode.json): niet opnieuw, en geen terugval
        return "eerder", ""
    if is_stil(moment):
        return "wacht", ""
    inhoud = ochtend_inhoud(it)
    tekst = str(inhoud["tekst"]).strip()
    kop = (it.get("titel") or "Ochtendbericht").strip()[:60]
    bundel, volledig = (None, False) if stand == "uit" or dag.get("terugval") else bundelwerk(bord_items, staat)
    regel = "" if stand == "uit" or dag.get("terugval") else bundelregel(tekst, bundel, volledig, namen)
    volledige_tekst = tekst + (f"\n{regel}" if regel else "")
    if sjabloonlengte(volledige_tekst) > whatsapp.MAX_PARAM:
        nood.append({"tekst": "Ochtendbericht past niet in een sjabloonbericht van WhatsApp", "wie": "claude-code"})
    if droog:
        print(f"  (droog) zou het ochtendbericht {it['id']} sturen, kop {kop!r}:\n{volledige_tekst}")
        return "droog", ""
    kanaal = stuur(volledige_tekst, nood, kop=kop, voorrang=True)
    if not kanaal:
        return "mislukt", "ochtendbericht niet verstuurd"
    punten = [p for p in (inhoud.get("punten") if isinstance(inhoud.get("punten"), list) else []) if isinstance(p, dict)]
    dag.update({"klaarzet_id": it["id"], "verzonden": moment.isoformat(), "kanaal": kanaal,
                "punten": [{"nr": p.get("nr"), "soort": p.get("soort"), "ref": p.get("ref"),
                            "vingerafdruk": p.get("vingerafdruk")} for p in punten],
                "sha": hashlib.sha256(volledige_tekst.encode()).hexdigest()[:12]})
    if stand != "uit" and not dag.get("terugval") and bundel is not None and (regel or not bundel):
        staat["bundel_vanaf"] = (gelezen or moment).astimezone(timezone.utc).isoformat()
    ochtend_voorstellen_gemeld(staat, inhoud)
    ag.log(f"ochtendbericht {datum}", "melding", f"ochtendbericht {datum} via {kanaal} (item {it['id']}, "
                                                 f"{meervoud(len(punten), 'punt', 'punten')})",
           "\n".join(f"{p.get('nr')}. {p.get('soort')} {p.get('ref')} ({p.get('agent')}) {p.get('link')}" for p in punten))
    ochtend_oppakken(dag, nood)
    return "verstuurd", f"ochtendbericht via {kanaal}"


def ochtend_oppakken(dag, nood):
    """Het verstuurde ochtendbericht op opgepakt zetten. Lukt dat niet, dan een nood, en de volgende ronde probeert
    alleen dat opnieuw: verstuurd is verstuurd (M6)."""
    try:
        bord.opgepakt(dag["klaarzet_id"], NAAM)
        dag["opgepakt"] = True
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"Ochtendbericht verstuurd maar niet opgepakt op het bord: {type(e).__name__}",
                     "wie": "claude-code"})


def terugval_sturen(staat, nood, moment, namen, stand, bord_items, voorstellen, droog=False, gelezen=None):
    """Geen ochtendbericht om 11:00 Brussel (B5, I7): een bericht zonder nummers met de aantallen, en in de bundelstand
    de regel Gebundeld. Een keer per dag; de nood staat apart (vaste_momenten). Onbekend is nooit 0 (L29)."""
    datum = dag_van(moment)
    dag = staat.setdefault("ochtend", {}).setdefault(datum, {})
    if dag.get("terugval") or is_stil(moment):
        return ""
    nieuw = nieuwe_voorstellen(staat, voorstellen)
    v = ("voorstellen onbekend" if voorstellen is None else meervoud(len(voorstellen), "voorstel", "voorstellen")
         + (f" ({len(nieuw)} nieuw)" if nieuw else ""))
    n = noden_voor_mehdi()
    tekst = (f"De Regisseur zette vandaag geen ochtendbericht klaar; {v} en "
             f"{'noden onbekend' if n is None else meervoud(n, 'nood', 'noden') + ' voor jou'} open, alles op het bord.")
    if stand != "uit":
        bundel, volledig = bundelwerk(bord_items, staat)
        regel = bundelregel(tekst, bundel, volledig, namen)
        tekst += f"\n{regel}" if regel else ""
    else:
        bundel, regel = None, ""
    b = moment.astimezone(BRUSSEL)
    kop = f"Ochtend {WEEKDAG[b.weekday()]} {b:%d-%m}: geen ochtendbericht"
    if droog:
        print(f"  (droog) zou de terugval sturen, kop {kop!r}:\n{tekst}")
        return ""
    kanaal = stuur(tekst, nood, kop=kop, voorrang=True)
    if not kanaal:
        return "terugval niet verstuurd"
    dag.update({"terugval": moment.isoformat(), "terugval_kanaal": kanaal})
    if stand != "uit" and bundel is not None and (regel or not bundel):
        staat["bundel_vanaf"] = (gelezen or moment).astimezone(timezone.utc).isoformat()
    voorstellen_gemeld(staat, voorstellen)
    ag.log(f"ochtendbericht {datum}", "melding", f"terugval {datum} via {kanaal}: geen ochtendbericht van De Regisseur", tekst)
    return f"terugval via {kanaal}"


def avond_regels(update, bundel, nieuw, namen, volledig):
    """De regels van de avondbundel: eerst de mailupdate van 17:00, dan de rest oudste eerst, dan de nieuwe voorstellen,
    zo dat de hele tekst als sjabloonparameter binnen whatsapp.MAX_PARAM blijft; wat niet past, staat op het bord.
    Alleen titels, zoals elk bericht van De Bode."""
    items = update + [it for it in bundel if it not in update]
    staart = voorstel_regels(nieuw, namen)
    if not volledig:
        staart.append("- er kan meer zijn: het bord gaf een volle pagina")
    regels = []
    for i, it in enumerate(items):
        kandidaat = regels + [f"- {it['soort']}: {(it.get('titel') or '')[:110]} (van {namen.get(it.get('van'), it.get('van'))})"]
        over = len(items) - i - 1
        slot = staart + ([f"- en nog {over}, die staan op het bord"] if over else []) + [f"Bord: {BORD_URL}"]
        if sjabloonlengte("\n\n".join(kandidaat + slot)) > whatsapp.MAX_PARAM:
            return regels + staart + [f"- en nog {len(items) - i}, die staan op het bord", f"Bord: {BORD_URL}"]
        regels = kandidaat
    return regels + staart + [f"Bord: {BORD_URL}"]


def avond_sturen(staat, nood, moment, namen, bord_items, voorstellen, droog=False, gelezen=None):
    """De avondbundel (alleen in 'ochtend-avond', B5): bij de mailupdate van 17:00 (AVOND_TRIGGER), of vanaf 17:30
    Brussel als er iets gebundeld is. Een keer per dag, niet in de stille uren, met voorrang; daarna begint de bundel
    opnieuw. Is het bord niet gelezen, dan niets: ik stuur geen bundel alsof er niets is."""
    datum = dag_van(moment)
    dag = staat.setdefault("avond", {}).setdefault(datum, {})
    if dag.get("verzonden") or not na(moment, AVOND_VANAF) or is_stil(moment):
        return ""
    bundel, volledig = bundelwerk(bord_items, staat)
    if bundel is None:
        return ""
    update = [it for it in bundel if it.get("uniek") == AVOND_TRIGGER.format(datum=datum)]
    nieuw = nieuwe_voorstellen(staat, voorstellen)
    if not update and not (na(moment, AVOND_UITERLIJK) and (bundel or nieuw)):
        return ""
    b = moment.astimezone(BRUSSEL)
    kop = f"Avondbundel {WEEKDAG[b.weekday()]} {b:%d-%m}"
    tekst = "\n\n".join(avond_regels(update, bundel, nieuw, namen, volledig))
    if droog:
        print(f"  (droog) zou de avondbundel sturen, kop {kop!r}:\n{tekst}")
        return ""
    kanaal = stuur(tekst, nood, kop=kop, voorrang=True)
    if not kanaal:
        return "avondbundel niet verstuurd"
    dag.update({"verzonden": moment.isoformat(), "kanaal": kanaal, "items": len(bundel), "met_update": bool(update)})
    staat["bundel_vanaf"] = (gelezen or moment).astimezone(timezone.utc).isoformat()
    voorstellen_gemeld(staat, voorstellen)
    ag.log(f"avondbundel {datum}", "melding", f"avondbundel {datum} via {kanaal}: {meervoud(len(bundel), 'item', 'items')}"
                                              f"{', met de mailupdate van 17:00' if update else ''}", tekst)
    return f"avondbundel via {kanaal}"


def slotbundel_sturen(staat, nood, moment, namen, bord_items, droog=False):
    """Terug naar 'uit' (BOD-2). Wat de bundelstand sinds het laatste vaste moment als afgehandeld telde, staat al voorbij
    laatste_id en gaat in 'uit' niet meer los. Dat stuur ik eerst als slotbundel, met voorrang en niet in de stille uren;
    pas na een geslaagde verzending laat ik bundel_vanaf los. Mislukt het, of is het bord niet gelezen, dan blijft alles
    staan en probeert de volgende ronde opnieuw. De grens is laatste_id bij de omschakeling (bundel_tot): wat daarna
    binnenkomt, gaat los en hoort niet ook in de slotbundel. Tot 21-10-2026 gooide 'uit' bundel_vanaf meteen weg."""
    if "bundel_vanaf" not in staat:
        staat.pop("bundel_tot", None)
        return ""
    tot = staat.setdefault("bundel_tot", staat.get("laatste_id") or 0)
    bundel, volledig = bundelwerk(bord_items, staat)
    if bundel is None:
        return ""
    slot = [it for it in bundel if it["id"] <= tot]
    if not slot:
        staat.pop("bundel_vanaf", None)
        staat.pop("bundel_tot", None)
        return ""
    if is_stil(moment):
        return ""
    datum = dag_van(moment)
    b = moment.astimezone(BRUSSEL)
    kop = f"Bundel {WEEKDAG[b.weekday()]} {b:%d-%m}"
    tekst = "\n\n".join(avond_regels([], slot, [], namen, volledig))
    if droog:
        print(f"  (droog) zou de slotbundel sturen, kop {kop!r}:\n{tekst}")
        return ""
    kanaal = stuur(tekst, nood, kop=kop, voorrang=True)
    if not kanaal:
        return "slotbundel niet verstuurd"
    staat.pop("bundel_vanaf", None)
    staat.pop("bundel_tot", None)
    ag.log(f"bundel {datum}", "melding", f"slotbundel {datum} via {kanaal}: {meervoud(len(slot), 'item', 'items')}, "
                                         "terug naar de stand uit", tekst)
    return f"slotbundel via {kanaal}"


def vaste_momenten(staat, nood, moment, namen, stand, bord_items, voorstellen, droog=False, gelezen=None):
    """De vaste momenten naar Mehdi (ontwerp regie-zoom v1.2, B5): het ochtendbericht, de terugval om 11:00 en, in de
    stand 'ochtend-avond', de avondbundel; in de stand 'uit' eerst nog de slotbundel als de bundelstand iets achterliet.
    Elke ronde opnieuw afgeleid; de noden ook (N10: zonder aantal, en ze blijven de hele dag staan zolang het zo is).
    gelezen: wanneer het bord gelezen is; daar begint na een vast moment de volgende bundel (BOD-4). Geeft een korte
    tekst voor het detail van de hartslag."""
    gelezen = gelezen or moment
    datum = dag_van(moment)
    grens = (moment.astimezone(BRUSSEL).date() - timedelta(days=OCHTEND_DAGEN)).isoformat()
    for sleutel in ("ochtend", "avond"):
        if not isinstance(staat.get(sleutel), dict):
            staat[sleutel] = {}
        for d in [d for d in staat[sleutel] if d < grens]:
            staat[sleutel].pop(d)
    uit = []
    if stand == "uit":
        uit.append(slotbundel_sturen(staat, nood, moment, namen, bord_items, droog))
    else:
        staat.pop("bundel_tot", None)
        if "bundel_vanaf" not in staat and bord_items is not None:
            # de overgang naar de bundelstand (BOD-1): wat al los afgehandeld is, komt niet nog eens in een bundel, en wat
            # nog niet wegging, komt er wel in. Is het bord niet gelezen, dan de volgende ronde.
            staat["bundel_vanaf"] = bundel_begin(staat, bord_items, moment)
    uitkomst, detail = ochtend_sturen(staat, nood, moment, namen, stand, bord_items, voorstellen, droog, gelezen=gelezen)
    uit.append(detail)
    if uitkomst == "geen" and na(moment, TERUGVAL):
        nood.append({"tekst": "Geen ochtendbericht van De Regisseur om 11:00", "wie": "claude-code"})
        uit.append(terugval_sturen(staat, nood, moment, namen, stand, bord_items, voorstellen, droog, gelezen=gelezen))
    if (staat["ochtend"].get(datum) or {}).get("verlopen"):
        nood.append({"tekst": "Ochtendbericht niet verstuurd: een item van een andere afzender of een andere dag",
                     "wie": "claude-code"})
    if stand == "ochtend-avond":
        uit.append(avond_sturen(staat, nood, moment, namen, bord_items, voorstellen, droog, gelezen=gelezen))
    return "; ".join(x for x in uit if x)


# ---------------------------------------------------------------- ronde ---
def main(droog=None):
    """Een ronde onder het slot. droog (standaard: --droog op de opdrachtregel, zoals regisseur.py agent_ronde het
    meegeeft; cron start zonder argumenten): zie ronde(). Een droge ronde neemt het slot niet, want ze schrijft niets
    en mag een echte ronde (die belt) niet laten overslaan."""
    if droog is None:
        droog = "--droog" in sys.argv
    if droog:
        return ronde(droog=True)
    slot = slot_nemen()
    if slot is None:
        print(f"{datetime.now(BRUSSEL):%d-%m %H:%M} de vorige ronde loopt nog, deze slaat over")
        return
    try:
        return ronde()
    finally:
        slot.close()


def ronde(droog=False):
    """droog (--droog, zoals regisseur.py agent_ronde het meegeeft): alleen tonen wat ik zou doen. Nooit bellen
    (afspraken_bellen en alarm_bellen lopen niet), niets sturen, geen berichten van Mehdi op het bord, geen hartslag,
    en de stand blijft ongewijzigd. Vroeger negeerde ik --droog en belde een proefronde echt (Codex A19, 15-10-2026).

    Volgorde (B5, ontwerp regie-zoom v1.2): 1. afspraken bellen en 2. de items lezen en alarm bellen, allebei buiten de
    ronde en ongewijzigd, zodat een onleesbare werkwijze geen oproep tegenhoudt (FR-154); 3. bij --droog alles tonen;
    4. de rest door de gedeelde ronde (N12), met de noden van 1 en 2 als begin_noden (X4). Stopt de ronde omdat het
    regelboek ontbreekt (RondeGestopt), dan wachten de berichten en gaat de stand van het bellen toch op schijf."""
    staat = lees_staat()
    nood = []
    moment = nu()
    stand = stand_bundelen()
    # Eerst bellen: dat hangt alleen af van het belrooster op schijf. Een storing bij Telegram of het bord liet main
    # vroeger crashen voor afspraken_bellen liep, en dan belde ik voor geen enkele afspraak. Na elke oproep staat de
    # stand meteen op schijf (bewaar), niet pas aan het eind na de time-outs (Codex A26, 15-10-2026).
    bel_afspraak = ""
    if droog:
        for r in bellen.te_bellen(staat, spoor=belspoor()):
            print(f"  (droog) zou bellen voor: {r.get('titel', '')[:80]}")
    else:
        bel_afspraak = veilig(nood, "Afspraken bellen", lambda: bellen.afspraken_bellen(
            staat, log=ag.log, bewaar=bewaar, nood=nood, spoor=belspoor()), "")

    stil = is_stil(moment)
    # Vlak voor het lezen van het bord, niet bij het begin van de ronde: daar begint de volgende bundel (BOD-4). Een item
    # dat binnenkwam terwijl ik belde, stond anders in deze bundel en, met een ts na moment, ook in de volgende. Voor de
    # GET, niet erna: dubbel bij een item dat tijdens het lezen zelf binnenkomt is beter dan verloren.
    gelezen = nu()
    # None als het bord niet te lezen was: dan is de bundel onbekend, niet leeg
    bord_items = veilig(nood, "Het bord lezen", lambda: bord.call(
        f"/api/klaarzet?voor=mehdi&status=alle&n={KLAARZET_N}").get("items", []), None)
    items = nieuwe_items(bord_items or [], staat, nood)
    eerste = not staat.get("laatste_id")
    alarm = [it for it in items if is_alarm(it)]
    # dringend signaal: bellen (Twilio), ook in de stille uren; herhaalt tot er opgenomen wordt
    bel_detail = ""
    if droog:
        if alarm:
            print(f"  (droog) {len(alarm)} dringend(e) signaal/oproep(en); zou bellen als het nieuw is: "
                  + "; ".join(it["titel"][:60] for it in alarm[:3]))
    else:
        # zonder leesbare stand weet ik niet welke alarmen al gebeld zijn: de items op het bord kunnen historisch zijn.
        # Niet automatisch bellen, wel melden (Codex A32, ronde 4). De volgende rondes kennen weer een laatste_id.
        # Het belspoor houdt ook alarmoproepen bij ('alarm:<id>'): wat daar staat, bel ik nooit opnieuw. Zonder stand bel ik
        # alleen een alarm dat recent is (ALARM_RECENT_MIN) en niet in het spoor staat; een ouder item meld ik (Codex A34,
        # ronde 5: na een verloren stand werd ook een zojuist binnengekomen alarm niet gebeld en daarna nooit meer).
        alarm_spoor = veilig(nood, "Belspoor lezen", lambda: (bellen.spoor_lezen(belspoor()),
                                                               bellen.spoor_bezig(belspoor())), None)
        al_gebeld = ({k.split(":", 1)[1] for deel in alarm_spoor for k in deel if k.startswith("alarm:")}
                     if alarm_spoor is not None else None)
        if alarm_spoor is not None:
            onzeker = [it for it in alarm if f"alarm:{it.get('id')}" in alarm_spoor[1]]
            if onzeker:
                nood.append({"tekst": f"De Bode: {len(onzeker)} alarmoproep(en) mogelijk vertrokken en onderbroken; "
                                      "niet herhaald, kijk ze na", "wie": "claude-code"})
        if al_gebeld is None:
            te_alarm = []                  # een onleesbaar spoor: niets is zeker nieuw (A33)
        elif eerste:
            te_alarm = [it for it in alarm if str(it.get("id")) not in al_gebeld and is_recent(it)]
            oud = [it for it in alarm if str(it.get("id")) not in al_gebeld and not is_recent(it)]
            if oud:
                nood.append({"tekst": f"De Bode had geen leesbare stand: {len(oud)} ouder(e) oproep- of stil-signaal(en) op het bord "
                                      "niet gebeld, want ze kunnen al gebeld zijn; kijk het bord na", "wie": "claude-code"})
        else:
            te_alarm = [it for it in nog_niet_gebeld(staat, alarm) if str(it.get("id")) not in al_gebeld]
        bel_detail = veilig(nood, "Alarm bellen", lambda: bellen.alarm_bellen(staat, te_alarm, log=ag.log,
                                                                              spoor=belspoor(), nood=nood), "")
        if bel_detail:
            veilig(nood, "Stand wegschrijven na het alarm", lambda: bewaar(staat), None)
    if bel_afspraak:
        bel_detail = (bel_detail + '; ' if bel_detail else '') + bel_afspraak
    # de noden van het bellen gaan mee, ook als de ronde stopt (X4)
    nood += bellen.nood() + bellen.nood_afspraken()

    if droog:
        namen = agentnamen()
        voorstellen = open_voorstellen(nood)
        vast = veilig(nood, "Vaste momenten", lambda: vaste_momenten(staat, nood, moment, namen, stand, bord_items,
                                                                       voorstellen, droog=True, gelezen=gelezen), "")
        groep, _, rest = melding_groep(items, eerste, staat, stand)
        nieuw = nieuwe_voorstellen(staat, voorstellen) if stand == "uit" else []
        if (groep or nieuw) and (not stil or alarm):
            print("  (droog) zou sturen:\n" + "\n".join(
                [f"- {it['soort']}: {it['titel'][:110]} (van {it['van']})" for it in groep] + voorstel_regels(nieuw, namen)))
        print(f"  (droog) stand {stand}; {len(items)} nieuwe items, {'stille uren' if stil else 'geen stille uren'}; "
              "niets gebeld, niets gestuurd, bord en stand ongewijzigd" + (f"; {vast}" if vast else "")
              + (f"; nood: {[n['tekst'] for n in nood]}" if nood else ""))
        return
    try:
        with ag.ronde("berichten van en naar Mehdi", bronnen={"BUNDELEN": stand}, begin_noden=nood) as r:
            werk = []
            try:
                r.detail = berichten(staat, werk, moment, stand, items, eerste, alarm, bord_items, bel_detail, gelezen)
            finally:
                # Een stand die niet op schijf kan, mag de hartslag niet tegenhouden: anders bereikt de nood van
                # afspraken_bellen (belronde gestopt, A26 ronde 3) het bord nooit. Het belspoor houdt een gevoerde
                # oproep intussen vast.
                veilig(werk, "Stand wegschrijven", lambda: bewaar(staat), None)
                for n in werk:
                    r.nood(n["tekst"], n.get("wie") or "mehdi")
    except bord.RondeGestopt:
        # zonder regelboek geen berichten (de ronde meldde het al, met de noden van het bellen); wat het bellen aan de
        # stand veranderde, gaat toch op schijf (B5)
        veilig([], "Stand wegschrijven", lambda: bewaar(staat), None)


def berichten(staat, nood, moment, stand, items, eerste, alarm, bord_items, bel_detail="", gelezen=None):
    """Het werk binnen de ronde (B5): berichten van Mehdi op het bord zetten, antwoorden terugbrengen, de vaste momenten
    en wat nu naar Mehdi moet. gelezen: wanneer het bord gelezen is (BOD-4). Geeft het detail voor de hartslag."""
    stil = is_stil(moment)
    namen = agentnamen()
    binnen = (veilig(nood, "WhatsApp lezen", lambda: lees_whatsapp(staat, namen, nood))
              + veilig(nood, "Telegram lezen", lambda: lees_telegram(staat, namen)))
    terug = veilig(nood, "Antwoorden terugbrengen", lambda: antwoorden_terug(staat, namen, nood))
    voorstellen = open_voorstellen(nood)
    nieuwe_voorstellen(staat, voorstellen)      # zonder stand: het hoogste id leren, zonder bericht
    vast = veilig(nood, "Vaste momenten", lambda: vaste_momenten(staat, nood, moment, namen, stand, bord_items,
                                                                   voorstellen, gelezen=gelezen), "")
    gemeld = set(staat.get("alarm_gemeld") or [])
    groep, tot, rest = melding_groep(items, eerste, staat, stand)
    # een alarm dat al een bericht kreeg (BOD-3), trekt in de stille uren geen ander bericht meer mee
    alarm = [it for it in alarm if it["id"] not in gemeld]
    # De herinnering om de zes uur bestaat niet meer (I7). In de stand 'uit' geeft een nieuw voorstel een bericht (L8);
    # in de bundelstand komt het in het volgende vaste moment.
    nieuw = nieuwe_voorstellen(staat, voorstellen) if stand == "uit" else []
    if items and not groep:
        staat["laatste_id"] = max(staat.get("laatste_id", 0), tot)  # alleen wat apart is: niet sturen, wel als gezien tellen
    kanaal = ""
    if (groep or nieuw) and (not stil or alarm):
        regels = [f"Mehdi Agents, {moment.astimezone(BRUSSEL).strftime('%H:%M')}:"]
        for it in groep:
            regels.append(f"- {it['soort']}: {it['titel'][:110]} (van {it['van']})")
        if rest:
            regels.append(f"- en nog {rest} oudere, die staan op het bord" if eerste else
                          f"- en nog {rest}, die volgen in het volgende bericht")
        regels += voorstel_regels(nieuw, namen)
        regels.append(f"Bord: {BORD_URL}")
        # Een witregel tussen de punten: op een gsm leest een aaneengesloten lijst te ingepakt
        # (Shaniel, 30-09-2026). Het sjabloon buiten het venster plat dit toch tot een regel.
        kanaal = stuur("\n\n".join(regels), nood)
        if kanaal:
            if items:
                # alleen tot het laatst verstuurde of bewust afgehandelde item; mislukt het sturen, dan schuift niets op
                staat["laatste_id"] = max(staat.get("laatste_id", 0), tot)
                # een alarm voorbij tot (achter een ochtendbericht dat nog niet weg is) is wel verstuurd (BOD-3)
                gemeld |= {it["id"] for it in groep if it["id"] > staat["laatste_id"]}
            if nieuw:
                voorstellen_gemeld(staat, voorstellen)
            ag.log("bericht", "melding", f"{len(groep)} van {len(items)} items{', nieuwe voorstellen' if nieuw else ''} "
                                         f"via {kanaal}", "\n".join(regels))
    # wat laatste_id intussen dekt, hoef ik niet meer apart te onthouden
    gemeld = sorted(i for i in gemeld if i > staat.get("laatste_id", 0))
    if gemeld:
        staat["alarm_gemeld"] = gemeld
    else:
        staat.pop("alarm_gemeld", None)
    if not TG_TOKEN:
        nood.append({"tekst": "Telegram niet ingesteld: bot bij BotFather, TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID in mijnagents-data/.env", "wie": "mehdi"})
    try:
        ins = whatsapp.instellingen()
        if not ins["sjabloon"] and not whatsapp.venster(ins)[0]:
            nood.append({"tekst": WA_NOOD, "wie": "mehdi"})
    except Exception:  # noqa: BLE001
        pass
    return (f"{binnen} binnen, {terug} antwoorden terug, {len(items)} items" + (f" via {kanaal}" if kanaal else "")
            + (f"; {vast}" if vast else "") + (f"; {bel_detail}" if bel_detail else "")
            + (f"; {len(staat.get('wacht', []))} wacht op antwoord" if staat.get("wacht") else ""))


if __name__ == "__main__":
    main()
