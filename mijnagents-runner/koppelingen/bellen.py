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
