#!/usr/bin/env python3
"""De Bode (Regie) — twee richtingen tussen het bord en Mehdi.

Naar Mehdi: wat de agents voor hem klaarzetten en welke voorstellen wachten,
gebundeld, via WhatsApp (sinds 30-09-2026, koppelingen/whatsapp.py: de Cloud API
van Meta, van het agentennummer UNABO Assistant). Mag WhatsApp niet (venster van 24 uur
dicht en nog geen sjabloon) of lukt het niet, dan Telegram, dan Zoom-chat. Alleen
als er iets NIEUWS is; een herinnering aan open voorstellen hoogstens één keer per
zes uur.
Van Mehdi: wat hij op WhatsApp of Telegram typt wordt een bericht op het bord aan
De Regisseur, of aan een agent als hij begint met diens naam ("Contractmaker: ...").
Het antwoord komt terug zodra de agent het op het bord zette.
Elke minuut. Werkwijze op het bord (werkwijze/bode.md is het zaad).
Met --droog (regisseur.py, agent_ronde): alleen tonen wat ik zou doen; nooit bellen, niets sturen, het bord en de
stand niet wijzigen. Cron start zonder argumenten.
"""
import base64
import fcntl
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bellen  # noqa: E402
import bord  # noqa: E402
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
SOORTEN = ("signaal", "coaching", "verslag", "dagplan", "dagbundel", "oproep")
HERINNERING_UREN = 6
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


def laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


laad_env("~/appportal/mijnagents-data/.env")
laad_env(ZOOM_ENV)
TG_TOKEN, TG_CHAT = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")


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


def stuur(tekst, nood):
    # Mehdi, 30-09-2026: WhatsApp in plaats van Telegram. Telegram blijft het vangnet
    # zolang het WhatsApp-venster dicht kan zijn zonder goedgekeurd sjabloon.
    try:
        return whatsapp.stuur(tekst)
    except whatsapp.NietBeschikbaar as e:
        nood.append({"tekst": WA_NOOD if "venster" in str(e) else f"WhatsApp: {e}", "wie": "mehdi"})
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"WhatsApp sturen mislukt: {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"})
    try:
        return stuur_telegram(tekst)
    except Exception as e:  # noqa: BLE001
        if not TG_TOKEN:
            nood.append({"tekst": "Telegram niet ingesteld: bot bij BotFather, TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID in mijnagents-data/.env", "wie": "mehdi"})
        else:
            nood.append({"tekst": f"Telegram sturen mislukt: {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"})
    try:
        return stuur_zoom(tekst)
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"Zoom-chat mislukt: {type(e).__name__}: {str(e)[:100]}", "wie": "claude-code"})
    return ""


def platte_tekst(md):
    t = re.sub(r"^#{1,6}\s*", "", md, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"`([^`]*)`", r"\1", t)
    return t.strip()


# ---------------------------------------------------------- van Mehdi ---
def agentnamen():
    try:
        return {a["naam"]: a["label"] for a in bord.call("/api/overzicht").get("agents", [])}
    except Exception:  # noqa: BLE001
        return {}


def doel_van(tekst, namen):
    """'Contractmaker: wat deed je' -> ('contracten-agent', 'wat deed je'); anders de Regisseur."""
    m = re.match(r"^\s*@?([\w\- ]{3,40}?)\s*[:\-]\s+(.+)$", tekst, re.S)
    if m:
        kop = m.group(1).lower().replace("de ", "").strip()
        for naam, label in namen.items():
            kort = label.lower().replace("de ", "").strip()
            if kop in (kort, naam) or kop in kort or kort.split()[0] in kop:
                return naam, m.group(2).strip()
    return "regisseur", tekst.strip()


def lees_telegram(staat, namen):
    """Nieuwe berichten van Mehdi -> gesprek op het bord. Geeft aantal.
    De offset schuift pas op na een geslaagde bordaanroep: main vangt een storing nu op en schrijft de stand toch weg
    (Codex A26, 15-10-2026), en dan mag het bericht niet verloren gaan; de volgende ronde leest het opnieuw."""
    if not TG_TOKEN:
        return 0
    d = tg("getUpdates", offset=staat.get("tg_offset", 0), timeout=0, allowed_updates=["message"])
    n, aan = 0, "regisseur"
    for u in d.get("result", []):
        m = u.get("message") or {}
        tekst = (m.get("text") or "").strip()
        if str(m.get("chat", {}).get("id")) == str(TG_CHAT) and tekst and not tekst.startswith("/start"):
            aan, vraag = doel_van(tekst, namen)
            uit = bord.call("/api/gesprek", {"aan": aan, "tekst": vraag, "van": "mehdi (telegram)"})
            staat.setdefault("wacht", []).append({"id": uit["id"], "aan": uit["aan"]})
            ag.log(f"bericht {uit['id']}", "bron", f"uit Telegram aan {namen.get(uit['aan'], uit['aan'])}: {vraag[:120]}")
            n += 1
        staat["tg_offset"] = u["update_id"] + 1
    if n:
        try:
            stuur_telegram(f"Ontvangen, {namen.get(aan, 'De Regisseur')} kijkt ernaar. Antwoord binnen een paar minuten.")
        except Exception:  # noqa: BLE001
            pass
    return n


def lees_whatsapp(staat, namen, nood):
    """Nieuwe WhatsApp-berichten van Mehdi aan het agentennummer -> gesprek op het bord.
    De WhatsApp-app bewaart ze (whatsapp.bericht); ik lees daar, alleen lezend. Geeft aantal."""
    try:
        nieuw = whatsapp.binnen(staat.get("wa_laatste_id", 0))
    except Exception as e:  # noqa: BLE001
        nood.append({"tekst": f"WhatsApp lezen mislukt: {type(e).__name__}", "wie": "claude-code"})
        return 0
    if "wa_laatste_id" not in staat:
        # eerste ronde: alleen de stand onthouden, geen oude berichten opnieuw op het bord
        staat["wa_laatste_id"] = max([m["id"] for m in nieuw] or [0])
        return 0
    n, aan = 0, "regisseur"
    for m in nieuw:
        tekst = (m.get("tekst") or "").strip()
        if tekst and tekst.lower() in WA_KORT:
            stuur("WhatsApp staat aan: de meldingen van je agents komen voortaan hier. "
                  "Antwoord gewoon; begin met de naam van een agent om hem rechtstreeks te spreken.", nood)
        elif tekst:
            aan, vraag = doel_van(tekst, namen)
            # gooit het bord een fout, dan blijft wa_laatste_id voor dit bericht staan: volgende ronde opnieuw (A26)
            uit = bord.call("/api/gesprek", {"aan": aan, "tekst": vraag, "van": "mehdi (whatsapp)"})
            staat.setdefault("wacht", []).append({"id": uit["id"], "aan": uit["aan"]})
            ag.log(f"bericht {uit['id']}", "bron", f"uit WhatsApp aan {namen.get(uit['aan'], uit['aan'])}: {vraag[:120]}")
            n += 1
        staat["wa_laatste_id"] = max(staat["wa_laatste_id"], m["id"])
    if n:
        stuur(f"Ontvangen, {namen.get(aan, 'De Regisseur')} kijkt ernaar. Antwoord binnen een paar minuten.", nood)
    return n


def antwoorden_terug(staat, namen, nood):
    """Beantwoorde berichten uit het bord -> Telegram."""
    klaar, rest = 0, []
    for w in staat.get("wacht", []):
        try:
            g = bord.call(f"/api/gesprek/{w['id']}").get("gesprek", {})
        except Exception:  # noqa: BLE001
            rest.append(w); continue
        if g.get("status") in ("beantwoord", "mislukt"):
            kop = namen.get(w["aan"], "De Regisseur")
            if stuur(f"{kop}:\n\n{platte_tekst(g.get('antwoord') or '(geen antwoord)')}", nood):
                klaar += 1
                ag.log(f"bericht {w['id']}", "melding", f"antwoord van {kop} naar Mehdi", g.get("antwoord", "")[:2000])
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
    try:
        return json.load(open(STAAT))
    except (OSError, ValueError):
        return {"laatste_id": 0, "tg_offset": 0, "wacht": [], "laatste_herinnering": "", "laatste_voorstellen": 0}


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


def melding_groep(items, eerste=False):
    """Welke nieuwe items in dit bericht gaan, en tot welk id ze na een geslaagde verzending als gelezen tellen.
    items: oplopend (nieuwe_items). Geeft (groep, tot, rest):
      groep  hoogstens PER_BERICHT items voor Mehdi, de oudste eerst;
      tot    het id tot waar alles verstuurd of bewust afgehandeld is: de groep, plus de agendazaken
             (NIET_OP_TELEGRAM, die gaan niet naar Mehdi) ertussen en erna, tot het eerste item dat niet meer in de
             groep past. Nooit voorbij een item dat niet verstuurd is: dat komt de volgende ronde (Codex A31);
      rest   hoeveel items voor Mehdi na deze groep nog wachten.
    eerste: er is nog geen laatste_id (eerste ronde, of een onleesbare bode.json). Dan de nieuwste PER_BERICHT en de
    rest bewust als gelezen; anders kwam heel de geschiedenis van het bord in tientallen berichten terug."""
    voor_mehdi = [it for it in items if it.get("van") not in NIET_OP_TELEGRAM]
    if eerste:
        return voor_mehdi[-PER_BERICHT:], (items[-1]["id"] if items else 0), max(0, len(voor_mehdi) - PER_BERICHT)
    groep, tot = [], 0
    for it in items:
        if it.get("van") not in NIET_OP_TELEGRAM:
            if len(groep) == PER_BERICHT:
                break
            groep.append(it)
        tot = it["id"]
    return groep, tot, len(voor_mehdi) - len(groep)


ALARM_RECENT_MIN = 30      # zonder stand: een alarm van het laatste halfuur is nieuw genoeg om te bellen (A34)


def is_recent(item, nu=None):
    """Is dit bord-item van de laatste ALARM_RECENT_MIN minuten? Het bord zet ts (ISO); zonder zone is het UTC (de server).
    Onleesbaar telt als niet recent: dan meld ik het in plaats van te bellen."""
    try:
        t = datetime.fromisoformat(str(item.get("ts") or "").replace("Z", "+00:00"))
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
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
    en de stand blijft ongewijzigd. Vroeger negeerde ik --droog en belde een proefronde echt (Codex A19, 15-10-2026)."""
    staat = lees_staat()
    nood = []
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
    namen = agentnamen()
    binnen = terug = 0
    if droog:
        print("  (droog) berichten van en naar Mehdi blijven liggen")
    else:
        binnen = (veilig(nood, "WhatsApp lezen", lambda: lees_whatsapp(staat, namen, nood))
                  + veilig(nood, "Telegram lezen", lambda: lees_telegram(staat, namen)))
        terug = veilig(nood, "Antwoorden terugbrengen", lambda: antwoorden_terug(staat, namen, nood))

    stil = is_stil()
    items = nieuwe_items(veilig(nood, "Het bord lezen", lambda: bord.call(
        f"/api/klaarzet?voor=mehdi&status=alle&n={KLAARZET_N}"), {}).get("items", []), staat, nood)
    eerste = not staat.get("laatste_id")
    groep, tot, rest = melding_groep(items, eerste)
    agents_met_voorstel = [a for a in veilig(nood, "Het bord lezen", lambda: bord.call("/api/overzicht"), {}).get("agents", []) if a.get("open_voorstellen")]
    totaal_voorstellen = sum(a["open_voorstellen"] for a in agents_met_voorstel)
    alarm = [it for it in items if it["soort"] == "oproep" or (it["soort"] == "signaal" and "stil" in it["titel"].lower())]
    # laatste_herinnering blijft naief (klok van de machine), bewaard en vergeleken met datetime.now(): zo blijven
    # bestaande standen vergelijkbaar. Alleen de stille uren en het uur in het bericht zijn Brussels (A23).
    herinnering_oud = (not staat.get("laatste_herinnering")) or (datetime.now() - datetime.fromisoformat(staat["laatste_herinnering"])).total_seconds() > HERINNERING_UREN * 3600
    herinner = totaal_voorstellen and (totaal_voorstellen != staat.get("laatste_voorstellen", 0) or herinnering_oud)
    kanaal = ""
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
        al_gebeld = veilig(nood, "Belspoor lezen", lambda: {k.split(":", 1)[1] for k in bellen.spoor_lezen(belspoor())
                                                              if k.startswith("alarm:")}, None)
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
        bel_detail = veilig(nood, "Alarm bellen", lambda: bellen.alarm_bellen(staat, te_alarm, log=ag.log), "")
        if str(bel_detail).startswith("belt"):
            # de werkelijk gebelde alarmen staan in de sleutel van de oproep, ook bij een herkansing waar te_alarm leeg is
            # (Codex A34, ronde 6)
            gebeld_ids = [d for d in str((staat.get("bel") or {}).get("sleutel") or "").split("|") if d.strip()]
            for aid in gebeld_ids or [str(it.get("id")) for it in te_alarm]:
                veilig(nood, "Belspoor bijschrijven (alarm)",
                       lambda aid=aid: bellen.spoor_schrijven(belspoor(), f"alarm:{aid}", datetime.now().astimezone().isoformat()), None)
        if bel_detail:
            veilig(nood, "Stand wegschrijven na het alarm", lambda: bewaar(staat), None)
    if bel_afspraak:
        bel_detail = (bel_detail + '; ' if bel_detail else '') + bel_afspraak
    if items and not groep:
        staat["laatste_id"] = max(staat.get("laatste_id", 0), tot)  # alleen agendazaken: niet sturen, wel als gezien tellen
    if (groep or herinner) and (not stil or alarm):
        regels = [f"Mehdi Agents, {datetime.now(BRUSSEL).strftime('%H:%M')}:"]
        for it in groep:
            regels.append(f"- {it['soort']}: {it['titel'][:110]} (van {it['van']})")
        if rest:
            regels.append(f"- en nog {rest} oudere, die staan op het bord" if eerste else
                          f"- en nog {rest}, die volgen in het volgende bericht")
        if herinner:
            for a in agents_met_voorstel:
                regels.append(f"- {a['open_voorstellen']} voorstel(len) van {a['label']} wachten op je goedkeuring")
        regels.append("Bord: https://mijnagents.globaal.be")
        if droog:
            print("  (droog) zou sturen:\n" + "\n".join(regels))
        else:
            # Een witregel tussen de punten: op een gsm leest een aaneengesloten lijst te ingepakt
            # (Shaniel, 30-09-2026). Het sjabloon buiten het venster plat dit toch tot een regel.
            kanaal = stuur("\n\n".join(regels), nood)
        if kanaal:
            if items:
                # alleen tot het laatst verstuurde of bewust afgehandelde item; mislukt het sturen, dan schuift niets op
                staat["laatste_id"] = max(staat.get("laatste_id", 0), tot)
            if herinner:
                staat["laatste_herinnering"] = datetime.now().isoformat()
                staat["laatste_voorstellen"] = totaal_voorstellen
            ag.log("bericht", "melding", f"{len(groep)} van {len(items)} items{', herinnering voorstellen' if herinner else ''} "
                                         f"via {kanaal}", "\n".join(regels))
    if droog:
        print(f"  (droog) {len(items)} nieuwe items, {'stille uren' if stil else 'geen stille uren'}; "
              "niets gebeld, niets gestuurd, bord en stand ongewijzigd" + (f"; nood: {[n['tekst'] for n in nood]}" if nood else ""))
        return
    # Een stand die niet op schijf kan, mag de hartslag niet tegenhouden: anders bereikt de nood van afspraken_bellen
    # (belronde gestopt, A26 ronde 3) het bord nooit. Het belspoor houdt een gevoerde oproep intussen vast.
    veilig(nood, "Stand wegschrijven", lambda: bewaar(staat), None)
    if not TG_TOKEN:
        nood.append({"tekst": "Telegram niet ingesteld: bot bij BotFather, TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID in mijnagents-data/.env", "wie": "mehdi"})
    nood += bellen.nood() + bellen.nood_afspraken()
    try:
        ins = whatsapp.instellingen()
        if not ins["sjabloon"] and not whatsapp.venster(ins)[0]:
            nood.append({"tekst": WA_NOOD, "wie": "mehdi"})
    except Exception:  # noqa: BLE001
        pass
    nood = list({n["tekst"]: n for n in nood}.values())   # dezelfde nood een keer, ook als hij twee keer ontstond
    ag.log_verstuur()
    detail = f"{binnen} binnen, {terug} antwoorden terug, {len(items)} items" + (f" via {kanaal}" if kanaal else "") + (f"; {bel_detail}" if bel_detail else "") + (f"; {len(staat.get('wacht', []))} wacht op antwoord" if staat.get("wacht") else "")
    ag.hartslag("actief" if (binnen or terug or kanaal) else ("rust" if stil else "waakt"),
                taak="luistert op WhatsApp" + (" en Telegram" if TG_TOKEN else ""), detail=detail, nood=nood)


if __name__ == "__main__":
    main()
