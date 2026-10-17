"""Bellen bij een alarm (De Bode, punt A12): een gesproken oproep via Twilio.

Sleutels bij naam in ~/appportal/mijnagents-data/.env:
  TWILIO_ACCOUNT_SID   het account (Console, Account Info; begint met AC)
  TWILIO_API_KEY_SID + TWILIO_API_KEY_SECRET   een API key (Settings, API keys & tokens;
                       aanbevolen door Twilio, intrekbaar zonder het account te raken)
  of, als er geen API key is: TWILIO_AUTH_TOKEN
  TWILIO_VAN      het gekochte Twilio-nummer, E.164 (+1..., +3197...)
  ALARM_NUMMER    Mehdi's gsm, E.164 (+32...)

Geen SDK: de REST-API rechtstreeks. De tekst wordt in het Nederlands uitgesproken
(Polly, stem Lotte) en twee keer herhaald. Wie de oproep opneemt, hoort alleen
de melding; er is geen menu en niets om in te toetsen. Herhalen als niemand
opneemt doet De Bode (elke 5 minuten, maximaal POGINGEN keer)."""
import base64
import json
import os
import urllib.parse
import urllib.request
from xml.sax.saxutils import escape

ENV = os.path.expanduser("~/appportal/mijnagents-data/.env")
# Een oproep, geen herhaling. Mehdi, 25-09-2026: "meestal neem ik het niet op, dus de agent moet niet drie keer
# na elkaar bellen. Voor mij is dat meer dan voldoende." Hoger kan alleen hier, in de code.
POGINGEN = min(int(os.environ.get("ALARM_POGINGEN", "1")), 1)
# Een start die mislukt (Twilio-fout, geen call-sid) is geen oproep: zo vaak probeer ik opnieuw, een keer per ronde
# (elke minuut), daarna geef ik het op met een logregel, anders herhaalt een kapotte koppeling eindeloos (Codex A13,
# 15-10-2026). Voor een afspraak binnen VENSTER_MIN, voor een alarm zonder venster.
MAX_BELPOGINGEN = 3
AFGEROND = {"completed", "busy", "no-answer", "failed", "canceled"}


def _env(pad):
    try:
        for regel in open(pad):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_env(ENV)


def _e(n):
    return os.environ.get(n, "").strip()


def uit():
    """BELLEN_UIT in mijnagents-data/.env (of de omgeving): de agents bellen Mehdi niet, langs geen enkele weg
    (afsprakenbel, alarm, vastzit, Telegram-oproep). Shaniel, 05-10-2026: "zet Mehdi zijn bel agent uit".
    Ook de grendel voor tests. Weer aan: de regel weghalen."""
    return bool(_e("BELLEN_UIT"))


def _aanmelding():
    """(gebruiker, geheim) voor Basic auth: API key als die er is, anders het Auth Token."""
    if _e("TWILIO_API_KEY_SID") and _e("TWILIO_API_KEY_SECRET"):
        return _e("TWILIO_API_KEY_SID"), _e("TWILIO_API_KEY_SECRET")
    return _e("TWILIO_ACCOUNT_SID"), _e("TWILIO_AUTH_TOKEN")


def beschikbaar():
    if uit():
        return False
    return bool(_e("TWILIO_ACCOUNT_SID") and _e("TWILIO_VAN") and _e("ALARM_NUMMER") and all(_aanmelding()))


def _verzoek(pad, data=None):
    gebruiker, geheim = _aanmelding()
    url = f"https://api.twilio.com/2010-04-01/Accounts/{_e('TWILIO_ACCOUNT_SID')}/{pad}"
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None,
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{gebruiker}:{geheim}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def twiml(tekst, slot="Details staan op WhatsApp en op het bord."):
    t = escape(tekst[:600])
    return ('<Response><Pause length="1"/>'
            f'<Say language="nl-NL" voice="Polly.Lotte">{t}</Say><Pause length="1"/>'
            f'<Say language="nl-NL" voice="Polly.Lotte">Ik herhaal. {t}</Say>'
            f'<Say language="nl-NL" voice="Polly.Lotte">{escape(slot)}</Say></Response>')


def _niet_in_een_test():
    """In een test belt niets echt, langs welke weg ook. Gezien 25-09-2026: een test stubde bel_afspraak,
    maar een nieuwe weg (bel_vast) belde Mehdi twee keer echt. De grendel zit daarom hier, op het laagste niveau."""
    if uit():
        raise RuntimeError("bellen staat uit (BELLEN_UIT)")


def bel(tekst, slot="Details staan op WhatsApp en op het bord.", van=None):
    """Start de oproep; geeft de call-sid terug. slot: de laatste zin (de Agendawacht zegt: in je agenda).
    van: afzender; standaard TWILIO_VAN (het afsprakennummer)."""
    _niet_in_een_test()
    uit = _verzoek("Calls.json", {"To": os.environ["ALARM_NUMMER"].strip(), "From": (van or os.environ["TWILIO_VAN"]).strip(),
                                  "Twiml": twiml(tekst, slot), "Timeout": "25"})
    return uit.get("sid", "")


def van_vast():
    """Mehdi, 25-09-2026: een agent die vastzit of iets dringends heeft, belt van een ANDER nummer dan de
    afsprakenbel, zodat hij zonder op te nemen weet: dit is geen afspraak, een agent heeft mij nodig.
    TWILIO_VAN_VAST in mijnagents-data/.env (+32460233042, gekocht 25-09); ontbreekt het, dan TWILIO_VAN."""
    return _e("TWILIO_VAN_VAST") or _e("TWILIO_VAN")


def bel_vast(tekst, slot="Details staan op WhatsApp en op het bord."):
    """Een oproep van het vastzit-nummer. Geeft [(kanaal, sid of fout)], zelfde vorm als bel_afspraak."""
    if not beschikbaar():
        return []
    try:
        return [("twilio-vast", bel(tekst, slot, van=van_vast()))]
    except Exception as e:  # noqa: BLE001
        return [("twilio-vast", f"mislukt: {type(e).__name__}")]


def status(call_sid):
    """queued, ringing, in-progress, completed, busy, no-answer, failed, canceled."""
    return (_verzoek(f"Calls/{call_sid}.json") or {}).get("status", "")


def nood():
    return [] if beschikbaar() or uit() else [{"tekst": "Bellen bij een alarm: Twilio-account met nummer, dan TWILIO_ACCOUNT_SID, een API key "
                                                "(TWILIO_API_KEY_SID en _SECRET), TWILIO_VAN en ALARM_NUMMER in mijnagents-data/.env", "wie": "shaniel"}]


def alarm_bellen(staat, alarmen, log=None, spoor=None, nood=None):
    """Aangeroepen door De Bode bij elke ronde. `staat["bel"]` onthoudt de lopende oproep.
    Nieuw alarm: bellen. Vorige oproep niet opgenomen: opnieuw, tot POGINGEN keer.
    Geeft een korte tekst voor het detail van de hartslag, of ''.
    Een start die mislukt (fout of geen call-sid, zie gelukt) is geen oproep en geen poging: de sleutel wordt pas na
    een echte oproep vastgezet. Tot dan staat het alarm in b["open"] en probeer ik het elke ronde opnieuw, ook als het
    signaal al gemeld is en niet meer in `alarmen` zit; na MAX_BELPOGINGEN mislukte starts geef ik het op, met een
    logregel. Vroeger stond de sleutel al vast voor bel() en belde een alarm na een mislukte start nooit meer
    (Codex A13, 15-10-2026). 'Nooit twee keer voor hetzelfde' blijft gelden voor echte oproepen."""
    if not beschikbaar():
        return ""
    b = staat.setdefault("bel", {"sleutel": "", "sid": "", "pogingen": 0, "laatste_status": ""})
    sleutel = "|".join(str(a.get("id", "")) for a in alarmen) if alarmen else ""
    try:
        if b.get("sid") and b.get("laatste_status") not in AFGEROND:
            try:
                b["laatste_status"] = status(b["sid"])
            except Exception as e:  # noqa: BLE001
                # de status niet kunnen lezen mag een nieuw alarm niet tegenhouden
                if log:
                    log("alarm", "bellen", f"status van de vorige oproep niet leesbaar: {type(e).__name__}")
        open_ = b.get("open") or {}
        nieuw = bool(sleutel) and sleutel not in (b.get("sleutel"), open_.get("sleutel"))
        herkans = not nieuw and bool(open_.get("sleutel"))
        herhaal = (not (nieuw or herkans) and b.get("sleutel")
                   and b.get("laatste_status") in {"busy", "no-answer", "failed", "canceled"}
                   and b.get("pogingen", 0) < POGINGEN)
        if not (nieuw or herkans or herhaal):
            return f"oproep {b['laatste_status']}" if b.get("sid") and b.get("laatste_status") else ""
        if nieuw:
            # een eerdere mislukte start die nog openstaat, gaat mee in de tekst van deze oproep
            doel = {"sleutel": sleutel, "mislukt": 0,
                    "titels": ([a.get("titel", "")[:80] for a in alarmen] + list(open_.get("titels") or []))[:3]}
        elif herkans:
            doel = dict(open_)
        else:
            doel = {"sleutel": b["sleutel"], "titels": b.get("titels") or [], "mislukt": 0}
        ids = [aid for aid in str(doel["sleutel"]).split("|") if aid]
        nu = __import__("datetime").datetime.now().astimezone().isoformat()
        if spoor:
            try:
                al = spoor_lezen(spoor)
                bezig = spoor_bezig(spoor)
                if any(f"alarm:{aid}" in al or f"alarm:{aid}" in bezig for aid in ids):
                    if any(f"alarm:{aid}" in bezig for aid in ids) and nood is not None:
                        nood.append({"tekst": "Alarm bellen: een eerdere oproep is onderbroken en mogelijk vertrokken; kijk dit na",
                                     "wie": "claude-code"})
                    return "alarm mogelijk gebeld" if any(f"alarm:{aid}" in bezig for aid in ids) else ""
                for aid in ids:
                    spoor_schrijven(spoor, f"alarm:{aid}", nu, bezig=True)
            except OSError as e:
                if nood is not None:
                    nood.append({"tekst": f"Alarm bellen: belspoor niet te schrijven of te lezen ({type(e).__name__}); niet gebeld",
                                 "wie": "claude-code"})
                return "alarm belspoor onbruikbaar"
        tekst = "Dit is De Bode van Mehdi Agents met een dringend signaal. " + ". ".join(doel.get("titels") or ["Er wacht een dringend signaal"])
        try:
            sid, fout = bel(tekst, van=van_vast()), ""
            if not gelukt(sid):
                fout = "geen call-sid terug"
        except Exception as e:  # noqa: BLE001
            sid, fout = "", f"{type(e).__name__}: {str(e)[:120]}"
        if spoor:
            try:
                for aid in ids:
                    spoor_schrijven(spoor, f"alarm:{aid}", nu,
                                    poging=doel.get("mislukt", 0) + 1 if fout else None)
            except OSError as e:
                if nood is not None:
                    nood.append({"tekst": f"Alarm bellen: uitkomst niet in belspoor bewaard ({type(e).__name__}); mogelijk gebeld, kijk na",
                                 "wie": "claude-code"})
                return "alarm belspoor onbruikbaar"
        zelfde = doel["sleutel"] == b.get("sleutel")   # herhaling of herkansing van een herhaling: pogingen blijven
        if fout:
            doel["mislukt"] = doel.get("mislukt", 0) + 1
            if doel["mislukt"] < MAX_BELPOGINGEN:
                b["open"] = doel
                if log:
                    log("alarm", "bellen", f"bellen mislukt (start {doel['mislukt']} van {MAX_BELPOGINGEN}), "
                                           f"volgende ronde opnieuw: {fout}", tekst)
                return "bellen mislukt"
            b["open"] = {}
            if zelfde:
                b["pogingen"] = POGINGEN
            else:
                b.update({"sleutel": doel["sleutel"], "titels": doel.get("titels") or [], "sid": "",
                          "pogingen": POGINGEN, "laatste_status": "mislukt"})
            if log:
                log("alarm", "bellen", f"bellen opgegeven na {doel['mislukt']} mislukte starts, niet gebeld: {fout}", tekst)
            return "bellen opgegeven"
        if not zelfde:
            b.update({"sleutel": doel["sleutel"], "pogingen": 0, "titels": doel.get("titels") or []})
        b["open"] = {}
        b["sid"] = sid
        b["pogingen"] = b.get("pogingen", 0) + 1
        b["laatste_status"] = "queued"
        if log:
            log("alarm", "bellen", f"oproep gestart (poging {b['pogingen']} van {POGINGEN})", tekst)
        return f"belt (poging {b['pogingen']})"
    except Exception as e:  # noqa: BLE001
        if log:
            log("alarm", "bellen", f"bellen mislukt: {type(e).__name__}: {str(e)[:120]}")
        return "bellen mislukt"


# ------------------------------------------------------------ afspraken bellen ---
# Mehdi's zwakke punt (11-09-2026): een agendamelding volstaat niet, hij moet effectief
# gebeld worden voor een afspraak, ook al is het een gemiste oproep. Twee kanalen:
#   1. Telegram-spraakoproep via CallMeBot (gratis): CALLMEBOT_USER in mijnagents-data/.env
#      (Telegram-gebruikersnaam met @, of gsm-nummer met landcode); Mehdi stuurt één keer
#      /start naar @CallMeBot_txtbot. Stem: CALLMEBOT_STEM (standaard nl-NL-Standard-B).
#   2. Echte telefoonoproep via Twilio (zie boven), zodra die sleutels er zijn.
# Zijn beide beschikbaar, dan bellen we via beide: dubbel is beter dan gemist.
# Het rooster (mijnagents-data/belrooster.json) schrijft De Agendawacht; De Bode leest het
# elke minuut en belt op het moment zelf.

ROOSTER = os.path.expanduser("~/appportal/mijnagents-data/belrooster.json")
VENSTER_MIN = 4  # binnen zoveel minuten na het beltijdstip bellen we nog


def callmebot_beschikbaar():
    if uit():
        return False
    return bool(os.environ.get("CALLMEBOT_USER", "").strip())


def afspraak_bellen_beschikbaar():
    return callmebot_beschikbaar() or beschikbaar()


def bel_telegram(tekst):
    """Telegram-spraakoproep via CallMeBot; de tekst wordt voorgelezen (twee keer). Geeft het antwoord van CallMeBot
    als korte platte tekst (callmebot_antwoord); of de oproep vertrok, beslist gelukt()."""
    _niet_in_een_test()
    voorlezen = tekst[:300]
    # de gebruiker (+32... of @naam) mag niet URL-gecodeerd worden: CallMeBot leest %2B verkeerd
    q = urllib.parse.urlencode({"text": voorlezen, "lang": os.environ.get("CALLMEBOT_STEM", "nl-NL-Standard-B"), "rpt": "2", "timeout": "40"})
    with urllib.request.urlopen(f"https://api.callmebot.com/start.php?user={os.environ['CALLMEBOT_USER'].strip()}&{q}", timeout=60) as r:
        h = r.read().decode(errors="replace")
    return callmebot_antwoord(h, voorlezen)


def callmebot_antwoord(h, voorlezen=""):
    """Het HTML-antwoord van CallMeBot als platte tekst van hoogstens 200 tekens. CallMeBot herhaalt onze tekst midden
    in zijn antwoord ('Text to speech:...'); die vervang ik door '(tekst)', en bij een lang antwoord houd ik begin en
    staart. Vroeger knipte ik gewoon op 200 tekens: dan bleef alleen de autorisatie plus onze eigen tekst over en viel
    weg wat er na de tekst over de oproep zelf staat (gemeten op de VM, Codex A13 ronde 3, 15-10-2026)."""
    import html
    import re
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h or "", flags=re.S | re.I)
    h = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h))).strip()
    v = re.sub(r"\s+", " ", voorlezen or "").strip()
    if v:
        h = h.replace(v, "(tekst)")
    return h if len(h) <= 200 else f"{h[:95]} ... {h[-100:]}"


def bel_afspraak(tekst, slot="Details staan op WhatsApp en op het bord."):
    """Belt een keer, via een kanaal: de telefoon (Twilio), en alleen als die niet kan de Telegram-oproep.
    Mehdi, 25-09-2026: een oproep is meer dan voldoende; vroeger belden beide kanalen tegelijk.
    Geeft lijst van (kanaal, resultaat of fout)."""
    if beschikbaar():
        try:
            return [("twilio", bel(tekst, slot))]
        except Exception as e:  # noqa: BLE001
            fout = [("twilio", f"mislukt: {type(e).__name__}")]
    else:
        fout = []
    if callmebot_beschikbaar():
        try:
            return fout + [("telegram-oproep", bel_telegram(tekst))]
        except Exception as e:  # noqa: BLE001
            return fout + [("telegram-oproep", f"mislukt: {type(e).__name__}")]
    return fout


# Wat CallMeBot antwoordt, gemeten in de logboeken op de VM (15-10-2026, telefoonnummer en gebruiker weggelaten):
#   aanvaard: "Checking Authorization for <gebruiker>... Using bot: @<bot> Autorization OK User:<gebruiker>
#              Text to speech:<onze tekst>"   (CallMeBot schrijft zelf "Autorization")
#   geweigerd: "ERROR: Two calls to the same user (<gebruiker>) within 65 seconds is not allowed. ..."
# "call queued" en "calling" zijn de woorden die CallMeBot voor een vertrekkende oproep gebruikt; een foutwoord wint
# altijd, ook na "Autorization OK" (een weigering na de autorisatie staat in de staart van het antwoord).
CALLMEBOT_AANVAARD = ("autorization ok", "authorization ok", "call queued", "calling")
CALLMEBOT_FOUT = ("error", "not allowed", "not available", "not authori", "unauthori", "denied", "invalid", "fail",
                  "65 seconds", "mislukt")


def callmebot_aanvaard(antwoord):
    """Zegt het antwoord van CallMeBot (bel_telegram) uitdrukkelijk dat de oproep vertrok? Alleen een herkend
    aanvaard-antwoord zonder foutwoord telt. Onbekend is onzeker: niet gebeld, en afspraken_bellen probeert opnieuw
    binnen het belvenster. Vroeger telde elk niet-leeg antwoord behalve twee foutvormen, ook 'Error: user not
    available' (Codex A13 ronde 3, 15-10-2026). De gebruiker zelf (CALLMEBOT_USER) staat in het antwoord en telt niet
    mee, anders kon een naam met 'error' of 'fail' erin een echte oproep als mislukt laten tellen."""
    t = str(antwoord or "").lower()
    gebruiker = os.environ.get("CALLMEBOT_USER", "").strip().lower()
    if gebruiker:
        t = t.replace(gebruiker, " ")
    if t.startswith("mislukt") or any(w in t for w in CALLMEBOT_FOUT):
        return False
    return any(w in t for w in CALLMEBOT_AANVAARD)


def gelukt(res):
    """Is er echt een oproep vertrokken? res is wat bel_afspraak of bel_vast teruggeeft [(kanaal, resultaat)], of een
    call-sid van bel(). Twilio ('twilio', 'twilio-vast'): alleen een call-sid (CA...). CallMeBot ('telegram-oproep'):
    alleen een herkend aanvaard-antwoord (callmebot_aanvaard). Een fout ('mislukt: ..'), een lege sid, een onbekend
    antwoord, een onbekend kanaal of een lege lijst is geen oproep: dan mag niets als 'gebeld' bewaard worden
    (Codex A13, 15-10-2026; onbekend is onzeker sinds ronde 3)."""
    if isinstance(res, str):
        return res.startswith("CA")
    for kanaal, v in res or []:
        v = str(v or "")
        if str(kanaal).startswith("twilio"):
            if v.startswith("CA"):
                return True
        elif kanaal == "telegram-oproep" and callmebot_aanvaard(v):
            return True
    return False


def rooster_schrijven(regels):
    """regels: [{sleutel, tijd (ISO, lokale tijd met zone), tekst, titel}]. Vervangt het rooster."""
    os.makedirs(os.path.dirname(ROOSTER), exist_ok=True)
    json.dump({"geschreven": __import__("datetime").datetime.now().astimezone().isoformat(), "regels": regels},
              open(ROOSTER, "w"), ensure_ascii=False, indent=0)


def _tijd(r):
    """Het beltijdstip van een roosterregel, met zone; zonder zone (of onleesbaar) None. Een tijd zonder zone is niet
    te vergelijken met nu en liet vroeger de hele ronde van De Bode crashen (Codex A13, 15-10-2026)."""
    from datetime import datetime
    try:
        t = datetime.fromisoformat(r["tijd"])
    except (KeyError, TypeError, ValueError):
        return None
    return t if t.tzinfo else None


def _rooster_regels():
    """De regels uit het belrooster, of None als het niet te lezen is."""
    try:
        return json.load(open(ROOSTER)).get("regels", [])
    except (OSError, ValueError, AttributeError):
        return None


def te_bellen(staat, nu=None, rooster=None, spoor=None):
    """Alleen lezen: de roosterregels waarvan het beltijdstip nu is (tot VENSTER_MIN minuten geleden) en die nog niet
    afgehandeld zijn. afspraken_bellen belt ze; de droge ronde van De Bode toont ze alleen (Codex A19, 15-10-2026).
    spoor: het belspoor (spoor_lezen); wat daarin staat is afgehandeld, ook als de stand het niet weet (A26)."""
    from datetime import datetime, timedelta
    nu = nu or datetime.now().astimezone()
    rooster = _rooster_regels() if rooster is None else rooster
    try:
        gebeld = {**spoor_lezen(spoor), **spoor_bezig(spoor), **staat.get("gebeld", {})}
    except OSError:
        return []          # een onleesbaar spoor: niets is zeker aan de beurt (A33); afspraken_bellen meldt het
    uit = []
    for r in rooster or []:
        t = _tijd(r)
        if t and r.get("sleutel") and r["sleutel"] not in gebeld and t <= nu < t + timedelta(minutes=VENSTER_MIN):
            uit.append(r)
    return uit


# ---------------------------------------------------------------- belspoor (A26) ---
# Een tweede, append-only bewijs naast de stand: een JSON-regel {sleutel, tijd} per afgehandelde afspraak, met flush en
# fsync, geschreven VOOR de stand. Waarom zo: de stand is een heel JSON-bestand dat atomair vervangen wordt; lukt dat
# niet (schijf vol, rechten), dan wist de volgende ronde niet dat er gebeld was en vertrok dezelfde oproep opnieuw.
# Een regel achteraan een bestand bijschrijven is de kleinste schrijfactie die er is, raakt niets wat er al staat, en
# een halve laatste regel (crash midden in het schrijven) valt bij het lezen gewoon weg. Lukt ook dat niet, dan belt
# De Bode niet verder (afspraken_bellen) (Codex A26 ronde 3, 15-10-2026).

def _spoor_regels(pad):
    """Alle leesbare regels van het belspoor als dicts; geen pad, geen bestand of geen map: []. Een bestand dat er is maar
    niet te lezen valt (rechten, schijffout), gooit: dat is geen leeg spoor (Codex A33, ronde 4)."""
    uit = []
    if not pad:
        return uit
    try:
        with open(pad, encoding="utf-8", errors="replace") as f:
            for regel in f:
                try:
                    d = json.loads(regel)
                    str(d["sleutel"]), str(d["tijd"])
                    uit.append(d)
                except (ValueError, KeyError, TypeError):
                    continue
    except (FileNotFoundError, NotADirectoryError):
        pass               # er is (nog) geen spoor: leeg
    return uit


def spoor_lezen(pad):
    """{sleutel: tijd} waarvan het laatste record een afgehandelde oproep of gemelde onderbreking is."""
    laatst = {}
    for d in _spoor_regels(pad):
        laatst[str(d["sleutel"])] = d
    return {k: str(d["tijd"]) for k, d in laatst.items()
            if not d.get("poging") and not d.get("bezig") and not d.get("wacht")}


def spoor_bezig(pad):
    """{sleutel: tijd} van oproepen waarvan het laatste record in het spoor 'bezig' is: de oproep kan vertrokken zijn maar
    de uitkomst kwam nooit op schijf (een crash midden in de ronde). Die bel ik niet blind opnieuw (Codex A26, ronde 6)."""
    laatst = {}
    for d in _spoor_regels(pad):
        laatst[str(d["sleutel"])] = d
    return {k: str(d["tijd"]) for k, d in laatst.items() if d.get("bezig")}


def spoor_pogingen(pad):
    """{sleutel: hoogste poging} van mislukte of onzekere pogingen in het belspoor. Zo overleeft de pogingenteller een
    stand die niet weg te schrijven is (Codex A26, ronde 5)."""
    uit = {}
    for d in _spoor_regels(pad):
        if d.get("poging") and not d.get("bezig"):
            uit[str(d["sleutel"])] = max(uit.get(str(d["sleutel"]), 0), int(d["poging"]))
    return uit


def spoor_schrijven(pad, sleutel, tijd, poging=None, bezig=False, wacht=False, gemeld=False):
    """Een regel achteraan het belspoor, met flush en fsync. Staat er nog een halve regel achteraan (crash), dan eerst
    een regeleinde, anders plakt de nieuwe regel eraan vast en is ook hij onleesbaar. Gooit bij een fout."""
    os.makedirs(os.path.dirname(pad) or ".", exist_ok=True)
    with open(pad, "a+b") as f:
        f.seek(0, os.SEEK_END)
        heel = True
        if f.tell():
            f.seek(-1, os.SEEK_END)
            heel = f.read(1) == b"\n"
        d = {"sleutel": sleutel, "tijd": tijd, **({"poging": int(poging)} if poging else {}),
             **({"bezig": True} if bezig else {}), **({"wacht": True} if wacht else {}),
             **({"gemeld": True} if gemeld else {})}
        f.write((b"" if heel else b"\n") + json.dumps(d, ensure_ascii=False).encode() + b"\n")
        f.flush()
        os.fsync(f.fileno())


def _spoor_opruimen(pad, grens):
    """Regels ouder dan grens (ISO) uit het spoor, atomair zoals bode.bewaar; alleen als er zulke regels zijn. Lukt het
    niet, dan blijft het spoor zoals het was: opruimen is huishouden, geen bewijs."""
    try:
        regels = _spoor_regels(pad)
    except OSError:
        return
    if not pad or not any(str(d["tijd"]) < grens for d in regels):
        return
    tmp = f"{pad}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            for d in regels:
                if str(d["tijd"]) >= grens:
                    f.write(json.dumps(d, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, pad)
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _bewaar(bewaar, staat, log):
    """bewaar(staat); True als het lukte. Een fout wordt een logregel; wat erop volgt beslist afspraken_bellen."""
    try:
        bewaar(staat)
        return True
    except Exception as e:  # noqa: BLE001
        if log:
            log("bellen", "afspraak", f"stand na de oproep niet weggeschreven: {type(e).__name__}: {str(e)[:120]}")
        return False


def afspraken_bellen(staat, log=None, bewaar=None, nood=None, spoor=None):
    """Elke minuut door De Bode. Belt elke roosterregel waarvan het beltijdstip nu is
    (tot VENSTER_MIN minuten geleden) en die nog niet afgehandeld is. Geeft korte tekst of ''.
    staat["gebeld"]: afgehandeld, dus echt gebeld (of opgegeven na MAX_BELPOGINGEN mislukte starts).
    Een start die mislukt (fout, lege sid, zie gelukt) is geen oproep: niet in "gebeld" en nooit "gebeld voor" in het
    logboek, wel een teller in staat["belpogingen"]; de volgende minuut opnieuw, binnen VENSTER_MIN en tot
    MAX_BELPOGINGEN keer, daarna opgegeven met een logregel. "Elke oproep een keer" (werkwijze/bode.md) en "nooit
    herhaald" (agenda-wacht.md) gaan over een oproep die vertrok en niet opgenomen werd (Codex A13, 15-10-2026).
    bewaar: callback die de stand na elke poging meteen wegschrijft, zodat een time-out of crash verderop in de ronde
    geen tweede oproep voor dezelfde afspraak geeft (Codex A26, 15-10-2026).
    spoor: pad van het belspoor (zie boven). Wat erin staat telt als gebeld; elke afgehandelde afspraak komt er eerst in.
    Staat een afgehandelde afspraak niet volledig op schijf (spoor of stand mislukt), dan stopt de belronde: geen
    volgende oproep, een logregel en een nood in de lijst nood. Vroeger slikte _bewaar de fout in en belde de lus
    verder; na een herstart ontbrak het bewijs en kon dezelfde oproep opnieuw vertrekken (Codex A26 ronde 3)."""
    from datetime import datetime, timedelta
    if not afspraak_bellen_beschikbaar():
        return ""
    if spoor:
        # opruimen los van het rooster: ook zonder rooster groeit het spoor (alarmen) (Codex A37, ronde 6)
        _spoor_opruimen(spoor, (datetime.now().astimezone() - timedelta(days=2)).isoformat())
    rooster = _rooster_regels()
    if rooster is None:
        return ""
    gebeld = staat.setdefault("gebeld", {})
    pogingen = staat.setdefault("belpogingen", {})
    nu = datetime.now().astimezone()
    try:
        sp, sp_pog, sp_bezig = spoor_lezen(spoor), spoor_pogingen(spoor), spoor_bezig(spoor)
    except OSError as e:
        # een spoor dat er is maar niet te lezen valt, kan een gevoerde oproep bevatten: deze ronde niet bellen (A33)
        if log:
            log("bellen", "afspraak", f"belronde gestopt: belspoor onleesbaar ({type(e).__name__}); niet gebeld deze ronde")
        if nood is not None:
            nood.append({"tekst": f"Afspraken bellen: het belspoor is onleesbaar ({type(e).__name__}); ik bel niet tot het weer te "
                                  "lezen is (rechten en schijf van mijnagents-data nakijken)", "wie": "claude-code"})
        return "belronde gestopt: belspoor onleesbaar"
    for k, t in sp.items():
        gebeld.setdefault(k, t)
    for k, n in sp_pog.items():
        if k not in gebeld:
            pogingen[k] = max(pogingen.get(k, 0), n)
    for k, t in sp_bezig.items():
        if k not in gebeld:
            # onderbroken: misschien gebeld. Niet opnieuw, wel melden (Codex A26, ronde 6)
            gebeld[k] = t
            if spoor:
                try:
                    spoor_schrijven(spoor, k, t, gemeld=True)
                except OSError as e:
                    if nood is not None:
                        nood.append({"tekst": f"Afspraken bellen: onderbreking niet duurzaam gemeld ({type(e).__name__}); "
                                              "belronde gestopt", "wie": "claude-code"})
                    return "belronde gestopt: onderbreking niet duurzaam gemeld"
            if log:
                log("bellen", "afspraak", "mogelijk gebeld: een vorige ronde werd onderbroken na de start van de oproep; niet herhaald")
            if nood is not None:
                nood.append({"tekst": "Afspraken bellen: een oproep werd onderbroken na haar start (mogelijk gebeld) en wordt niet "
                                      "herhaald; kijk na of Mehdi ze kreeg", "wie": "claude-code"})
    # opruimen: ouder dan twee dagen
    for k in [k for k, v in gebeld.items() if v < (nu - timedelta(days=2)).isoformat()]:
        gebeld.pop(k, None)
    # mislukte pogingen voor een regel die niet meer aan de beurt is (venster voorbij, of uit het rooster): niet gebeld
    nog = {r.get("sleutel") for r in rooster if _tijd(r) and nu < _tijd(r) + timedelta(minutes=VENSTER_MIN)}
    titels = {r.get("sleutel"): r.get("titel", "") for r in rooster}
    for k in [k for k in pogingen if k not in nog]:
        n = pogingen.pop(k)
        if log and k not in gebeld:
            log("bellen", "afspraak", f"niet gebeld: belvenster voorbij na {n} mislukte poging(en): {titels.get(k, '')[:80]}")
    uit, mislukt, gestopt = [], [], ""
    beurt = te_bellen(staat, nu, rooster)
    for i, r in enumerate(beurt):
        titel = r.get("titel", "")
        if spoor:
            try:
                # eerst een duurzaam 'bezig': crasht de ronde na de start, dan belt de volgende ronde niet blind opnieuw (A26)
                spoor_schrijven(spoor, r["sleutel"], nu.isoformat(), bezig=True)
            except Exception as e:  # noqa: BLE001
                gestopt = "belronde gestopt: belspoor niet te schrijven voor de oproep"
                if log:
                    log("bellen", "afspraak", f"{gestopt} ({type(e).__name__}); niet gebeld deze ronde")
                if nood is not None:
                    nood.append({"tekst": "Afspraken bellen: het belspoor is niet te schrijven; ik bel niet tot dat weer lukt "
                                          "(schijfruimte en rechten van mijnagents-data nakijken)", "wie": "claude-code"})
                break
        res = bel_afspraak(r["tekst"], "Details staan in je agenda.")   # het belrooster komt uit de agenda
        if not gelukt(res) and any("65 seconds" in str(v) for _, v in res):
            # CallMeBot laat maar één oproep per 65 s toe: deze regel volgende minuut opnieuw
            if spoor:
                try:
                    spoor_schrijven(spoor, r["sleutel"], nu.isoformat(), wacht=True)
                except OSError as e:
                    if nood is not None:
                        nood.append({"tekst": f"Afspraken bellen: weigering niet in belspoor bewaard ({type(e).__name__}); "
                                              "belronde gestopt", "wie": "claude-code"})
                    return "belronde gestopt: weigering niet bewaard"
            if log:
                log("bellen", "afspraak", f"even wachten (één oproep per 65 s): {titel[:60]}")
            break
        # 160 tekens: bij een onbekend antwoord van CallMeBot moet in het logboek staan wat er wel kwam (A13 ronde 3)
        samen = ", ".join(f"{k}: {str(v)[:160]}" for k, v in res)
        if gelukt(res):
            gebeld[r["sleutel"]] = nu.isoformat()
            pogingen.pop(r["sleutel"], None)
            if log:
                log("bellen", "afspraak", f"gebeld voor: {titel[:80]}", f"{r['tekst']}\n{samen}")
            uit.append(titel[:40])
        else:
            n = pogingen[r["sleutel"]] = pogingen.get(r["sleutel"], 0) + 1
            if n >= MAX_BELPOGINGEN:
                gebeld[r["sleutel"]] = nu.isoformat()   # afgehandeld, anders herhaalt een kapotte koppeling eindeloos
                pogingen.pop(r["sleutel"], None)
                if log:
                    log("bellen", "afspraak", f"bellen opgegeven na {n} mislukte pogingen, niet gebeld: {titel[:80]}",
                        f"{r['tekst']}\n{samen or 'geen kanaal'}")
            elif log:
                log("bellen", "afspraak", f"bellen mislukt (poging {n} van {MAX_BELPOGINGEN}), volgende minuut opnieuw: "
                                          f"{titel[:80]}", f"{r['tekst']}\n{samen or 'geen kanaal'}")
            mislukt.append(titel[:40])
        # spoor_ok en stand_ok: True gelukt, False mislukt, None niet van toepassing (geen spoor of geen callback)
        afgehandeld = r["sleutel"] in gebeld
        spoor_ok = None
        if spoor:
            try:
                # ook een mislukte of onzekere poging komt in het spoor, met haar nummer (Codex A26, ronde 5)
                spoor_schrijven(spoor, r["sleutel"], gebeld[r["sleutel"]] if afgehandeld else nu.isoformat(),
                                poging=None if afgehandeld else pogingen.get(r["sleutel"]))
                spoor_ok = True
            except Exception as e:  # noqa: BLE001
                spoor_ok = False
                if log:
                    log("bellen", "afspraak", f"belspoor niet bijgeschreven: {type(e).__name__}: {str(e)[:120]}")
        stand_ok = _bewaar(bewaar, staat, log) if bewaar else None
        if spoor_ok is False or (spoor_ok is None and stand_ok is False):
            # onzeker bewijs: geen volgende oproep in deze ronde (A26 ronde 3). Ook na een onzekere of mislukte poging: dan
            # gaat bij een herstart de pogingenteller verloren (Codex A26, ronde 4)
            wacht = len(beurt) - i - 1
            # staat het spoor veilig op schijf, dan gaan de andere oproepen door: niemand verhongert achter een kapotte stand
            # (Codex A26, ronde 5). Alleen als ook het spoor faalt (of er geen is), stopt de ronde.
            bewijs = ("de oproep was onzeker of mislukt en de pogingenteller staat niet op schijf" if not afgehandeld else
                      "het belspoor houdt haar vast, ze wordt niet opnieuw gebeld" if spoor_ok else
                      "de stand houdt haar vast" if stand_ok else
                      "ze staat nergens op schijf en kan opnieuw gebeld worden")
            gestopt = f"belronde gestopt: {'stand' if stand_ok is False else 'belspoor'} niet weggeschreven"
            if log:
                log("bellen", "afspraak", f"{gestopt} na de oproep voor {titel[:60]}; {bewijs}; geen volgende oproep "
                                          f"deze ronde ({wacht} wacht(en) tot de volgende minuut)", samen)
            if nood is not None:
                nood.append({"tekst": f"Afspraken bellen: na een oproep kon {'de stand' if stand_ok is False else 'het belspoor'} "
                                      f"niet op schijf (mijnagents-data); {bewijs}. Ik bel per ronde hoogstens een "
                                      "afspraak tot dat weer lukt: schijfruimte en rechten nakijken", "wie": "claude-code"})
            break
        if stand_ok is False and nood is not None and not any("stand niet weg" in n["tekst"] for n in nood):
            # het spoor houdt de oproep vast, dus ik bel verder; de kapotte stand meld ik wel (A26, ronde 5)
            nood.append({"tekst": "Afspraken bellen: de stand kon niet weg (mijnagents-data), het belspoor houdt elke oproep en "
                                  "poging vast: schijfruimte en rechten nakijken", "wie": "claude-code"})
    delen = ((["belt: " + "; ".join(uit)] if uit else []) + (["bellen mislukt: " + "; ".join(mislukt)] if mislukt else [])
             + ([gestopt] if gestopt else []))
    return "; ".join(delen)


def nood_afspraken():
    if afspraak_bellen_beschikbaar() or uit():
        return []
    return [{"tekst": "Bellen voor afspraken: gratis via Telegram-oproep. Mehdi: in Telegram een gebruikersnaam zetten "
                      "(Settings > Username), /start sturen naar @CallMeBot_txtbot, en CALLMEBOT_USER=@gebruikersnaam "
                      "in mijnagents-data/.env (of het gsm-nummer met +32)", "wie": "mehdi"}]
