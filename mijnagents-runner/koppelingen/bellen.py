"""Bellen bij een alarm (De Bode, punt A12): een gesproken oproep via Twilio.

Sleutels bij naam in ~/appportal/mijnagents-data/.env:
  TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN  (Twilio Console, Account Info)
  TWILIO_VAN      het gekochte Twilio-nummer, E.164 (+32..., +31..., +1...)
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
POGINGEN = int(os.environ.get("ALARM_POGINGEN", "3"))
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


def beschikbaar():
    return all(os.environ.get(n, "").strip() for n in ("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_VAN", "ALARM_NUMMER"))


def _verzoek(pad, data=None):
    sid, tok = os.environ["TWILIO_ACCOUNT_SID"].strip(), os.environ["TWILIO_AUTH_TOKEN"].strip()
    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/{pad}"
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode() if data else None,
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{sid}:{tok}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def twiml(tekst):
    t = escape(tekst[:600])
    return ('<Response><Pause length="1"/>'
            f'<Say language="nl-NL" voice="Polly.Lotte">{t}</Say><Pause length="1"/>'
            f'<Say language="nl-NL" voice="Polly.Lotte">Ik herhaal. {t}</Say>'
            '<Say language="nl-NL" voice="Polly.Lotte">Details staan op Telegram en op het bord.</Say></Response>')


def bel(tekst):
    """Start de oproep; geeft de call-sid terug."""
    uit = _verzoek("Calls.json", {"To": os.environ["ALARM_NUMMER"].strip(), "From": os.environ["TWILIO_VAN"].strip(),
                                  "Twiml": twiml(tekst), "Timeout": "25"})
    return uit.get("sid", "")


def status(call_sid):
    """queued, ringing, in-progress, completed, busy, no-answer, failed, canceled."""
    return (_verzoek(f"Calls/{call_sid}.json") or {}).get("status", "")


def nood():
    return [] if beschikbaar() else [{"tekst": "Bellen bij een alarm: Twilio-account met nummer, dan TWILIO_ACCOUNT_SID, "
                                                "TWILIO_AUTH_TOKEN, TWILIO_VAN en ALARM_NUMMER in mijnagents-data/.env", "wie": "shaniel"}]


def alarm_bellen(staat, alarmen, log=None):
    """Aangeroepen door De Bode bij elke ronde. `staat["bel"]` onthoudt de lopende oproep.
    Nieuw alarm: bellen. Vorige oproep niet opgenomen: opnieuw, tot POGINGEN keer.
    Geeft een korte tekst voor het detail van de hartslag, of ''."""
    if not beschikbaar():
        return ""
    b = staat.setdefault("bel", {"sleutel": "", "sid": "", "pogingen": 0, "laatste_status": ""})
    sleutel = "|".join(str(a.get("id", "")) for a in alarmen) if alarmen else ""
    try:
        if b.get("sid") and b.get("laatste_status") not in AFGEROND:
            b["laatste_status"] = status(b["sid"])
        nieuw = bool(sleutel) and sleutel != b.get("sleutel")
        herhaal = (b.get("sleutel") and b.get("laatste_status") in {"busy", "no-answer", "failed", "canceled"}
                   and b.get("pogingen", 0) < POGINGEN)
        if not (nieuw or herhaal):
            return f"oproep {b['laatste_status']}" if b.get("sid") and b.get("laatste_status") else ""
        if nieuw:
            b.update({"sleutel": sleutel, "pogingen": 0, "titels": [a.get("titel", "")[:80] for a in alarmen][:3]})
        tekst = "Dit is De Bode van Mehdi Agents met een dringend signaal. " + ". ".join(b.get("titels") or ["Er wacht een dringend signaal"])
        b["sid"] = bel(tekst)
        b["pogingen"] += 1
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
    return bool(os.environ.get("CALLMEBOT_USER", "").strip())


def afspraak_bellen_beschikbaar():
    return callmebot_beschikbaar() or beschikbaar()


def bel_telegram(tekst):
    """Telegram-spraakoproep via CallMeBot; de tekst wordt voorgelezen (twee keer)."""
    # de gebruiker (+32... of @naam) mag niet URL-gecodeerd worden: CallMeBot leest %2B verkeerd
    q = urllib.parse.urlencode({"text": tekst[:300], "lang": os.environ.get("CALLMEBOT_STEM", "nl-NL-Standard-B"), "rpt": "2", "timeout": "40"})
    import re
    with urllib.request.urlopen(f"https://api.callmebot.com/start.php?user={os.environ['CALLMEBOT_USER'].strip()}&{q}", timeout=60) as r:
        h = r.read().decode(errors="replace")
    h = re.sub(r"<script.*?</script>|<style.*?</style>", "", h, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()[:200]


def bel_afspraak(tekst):
    """Belt via elk beschikbaar kanaal. Geeft lijst van (kanaal, resultaat of fout)."""
    uit = []
    if callmebot_beschikbaar():
        try:
            uit.append(("telegram-oproep", bel_telegram(tekst)))
        except Exception as e:  # noqa: BLE001
            uit.append(("telegram-oproep", f"mislukt: {type(e).__name__}"))
    if beschikbaar():
        try:
            uit.append(("twilio", bel(tekst)))
        except Exception as e:  # noqa: BLE001
            uit.append(("twilio", f"mislukt: {type(e).__name__}"))
    return uit


def rooster_schrijven(regels):
    """regels: [{sleutel, tijd (ISO, lokale tijd met zone), tekst, titel}]. Vervangt het rooster."""
    os.makedirs(os.path.dirname(ROOSTER), exist_ok=True)
    json.dump({"geschreven": __import__("datetime").datetime.now().astimezone().isoformat(), "regels": regels},
              open(ROOSTER, "w"), ensure_ascii=False, indent=0)


def afspraken_bellen(staat, log=None):
    """Elke minuut door De Bode. Belt elke roosterregel waarvan het beltijdstip nu is
    (tot VENSTER_MIN minuten geleden) en die nog niet gebeld is. Geeft korte tekst of ''."""
    from datetime import datetime, timedelta
    if not afspraak_bellen_beschikbaar():
        return ""
    try:
        rooster = json.load(open(ROOSTER)).get("regels", [])
    except (OSError, ValueError):
        return ""
    gebeld = staat.setdefault("gebeld", {})
    nu = datetime.now().astimezone()
    # opruimen: ouder dan twee dagen
    for k in [k for k, v in gebeld.items() if v < (nu - timedelta(days=2)).isoformat()]:
        gebeld.pop(k, None)
    uit = []
    for r in rooster:
        try:
            t = datetime.fromisoformat(r["tijd"])
        except (KeyError, ValueError):
            continue
        if r["sleutel"] in gebeld or not (t <= nu < t + timedelta(minutes=VENSTER_MIN)):
            continue
        res = bel_afspraak(r["tekst"])
        if any("65 seconds" in str(v) for _, v in res):
            # CallMeBot laat maar één oproep per 65 s toe: deze regel volgende minuut opnieuw
            if log:
                log("bellen", "afspraak", f"even wachten (één oproep per 65 s): {r.get('titel', '')[:60]}")
            break
        gebeld[r["sleutel"]] = nu.isoformat()
        samen = ", ".join(f"{k}: {str(v)[:40]}" for k, v in res)
        if log:
            log("bellen", "afspraak", f"gebeld voor: {r.get('titel', '')[:80]}", f"{r['tekst']}\n{samen}")
        uit.append(r.get("titel", "")[:40])
    return ("belt: " + "; ".join(uit)) if uit else ""


def nood_afspraken():
    if afspraak_bellen_beschikbaar():
        return []
    return [{"tekst": "Bellen voor afspraken: gratis via Telegram-oproep. Mehdi: in Telegram een gebruikersnaam zetten "
                      "(Settings > Username), /start sturen naar @CallMeBot_txtbot, en CALLMEBOT_USER=@gebruikersnaam "
                      "in mijnagents-data/.env (of het gsm-nummer met +32)", "wie": "mehdi"}]
