#!/usr/bin/env python3
"""De Bode (Regie) — brengt wat telt van het bord naar Mehdi: nu via Zoom-chat
(Server-to-Server-koppeling van de stack, pipedrive-won-deals/.env), later
Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in mijnagents-data/.env).
Elke vijf minuten. Werkwijze op het bord (werkwijze/bode.md is het zaad).
"""
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import bord  # noqa: E402

NAAM = "bode"
ag = bord.Agent(NAAM)
STAAT = os.path.expanduser("~/appportal/mijnagents-data/bode.json")
STIL = (22, 7)
SOORTEN = ("signaal", "coaching", "verslag", "dagplan", "dagbundel")
ZOOM_ENV = os.path.expanduser("~/pipedrive-won-deals/.env")


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


def zoom_token():
    basis = base64.b64encode(f"{os.environ['ZOOM_CLIENT_ID']}:{os.environ['ZOOM_CLIENT_SECRET']}".encode()).decode()
    url = "https://zoom.us/oauth/token?" + urllib.parse.urlencode({"grant_type": "account_credentials", "account_id": os.environ["ZOOM_ACCOUNT_ID"]})
    req = urllib.request.Request(url, method="POST", headers={"Authorization": "Basic " + basis})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)["access_token"]


def stuur_zoom(tekst):
    sender = os.environ.get("ZOOM_SENDER", "")
    ontvanger = os.environ.get("ZOOM_MELDING_CONTACT", "")
    if not (sender and ontvanger and os.environ.get("ZOOM_CLIENT_ID")):
        raise RuntimeError("Zoom-koppeling niet ingesteld (ZOOM_SENDER, ZOOM_MELDING_CONTACT, ZOOM_CLIENT_*)")
    req = urllib.request.Request(f"https://api.zoom.us/v2/chat/users/{urllib.parse.quote(sender)}/messages",
                                 data=json.dumps({"to_contact": ontvanger, "message": tekst}).encode(), method="POST",
                                 headers={"Authorization": "Bearer " + zoom_token(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def stuur_telegram(tekst):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not (tok and chat):
        raise RuntimeError("geen Telegram-token")
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/sendMessage",
                                 data=json.dumps({"chat_id": chat, "text": tekst[:4000]}).encode(), method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def main():
    try:
        staat = json.load(open(STAAT))
    except (OSError, ValueError):
        staat = {"laatste_id": 0, "laatste_voorstel": 0}
    uur = datetime.now().hour
    stil = uur >= STIL[0] or uur < STIL[1]
    items = [it for it in bord.call("/api/klaarzet?voor=mehdi&status=alle&n=200").get("items", [])
             if it["id"] > staat["laatste_id"] and it["soort"] in SOORTEN]
    voorstellen = [a for a in bord.call("/api/overzicht").get("agents", []) if a.get("open_voorstellen")]
    alarm = [it for it in items if it["soort"] == "signaal" and "stil" in it["titel"].lower()]
    if not items and not voorstellen:
        ag.hartslag("waakt", taak="luistert", detail="niets nieuws voor Mehdi")
        return
    if stil and not alarm:
        ag.hartslag("rust", taak="stille uren", detail=f"{len(items)} items wachten tot 07:00")
        return
    regels = [f"Mehdi Agents, {datetime.now().strftime('%H:%M')}:"]
    for it in items[-8:]:
        regels.append(f"- {it['soort']}: {it['titel'][:110]} (van {it['van']})")
    if len(items) > 8:
        regels.append(f"- en nog {len(items) - 8} andere")
    for a in voorstellen:
        regels.append(f"- {a['open_voorstellen']} voorstel(len) van {a['label']} wachten op je goedkeuring")
    regels.append("Bord: https://mijnagents.globaal.be")
    tekst = "\n".join(regels)
    kanaal, nood = "", []
    try:
        stuur_telegram(tekst); kanaal = "telegram"
    except Exception:  # noqa: BLE001
        nood.append({"tekst": "Telegram niet ingesteld: bot aanmaken bij BotFather, TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID in mijnagents-data/.env", "wie": "mehdi"})
        try:
            stuur_zoom(tekst); kanaal = "zoom"
        except Exception as e:  # noqa: BLE001
            nood.append({"tekst": f"Zoom-chat mislukt: {type(e).__name__}: {str(e)[:120]}", "wie": "claude-code"})
    nood.append({"tekst": "Bellen bij een alarm: dienst kiezen (Twilio of Xelion-API)", "wie": "mehdi"})
    if kanaal:
        staat["laatste_id"] = max(it["id"] for it in items) if items else staat["laatste_id"]
        json.dump(staat, open(STAAT, "w"))
        ag.log("bericht", "melding", f"{len(items)} items en {len(voorstellen)} voorstel-agents gemeld via {kanaal}", tekst)
        ag.log_verstuur()
        ag.hartslag("waakt", taak="luistert", detail=f"laatste bericht {datetime.now().strftime('%H:%M')} via {kanaal}", nood=nood)
    else:
        ag.hartslag("fout", taak="geen kanaal werkt", detail="Telegram noch Zoom", nood=nood)


if __name__ == "__main__":
    main()
