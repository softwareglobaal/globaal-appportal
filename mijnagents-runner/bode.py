#!/usr/bin/env python3
"""De Bode (Regie) — twee richtingen tussen het bord en Mehdi.

Naar Mehdi: wat de agents voor hem klaarzetten en welke voorstellen wachten,
gebundeld, via Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID in
mijnagents-data/.env), anders Zoom-chat. Alleen als er iets NIEUWS is; een
herinnering aan open voorstellen hoogstens één keer per zes uur.
Van Mehdi: wat hij in Telegram typt wordt een bericht op het bord aan De
Regisseur, of aan een agent als hij begint met diens naam ("Contractmaker: ...").
Het antwoord komt terug in Telegram zodra de agent het op het bord zette.
Elke minuut. Werkwijze op het bord (werkwijze/bode.md is het zaad).
"""
import base64
import json
import os
import re
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
HERINNERING_UREN = 6
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
    """Nieuwe berichten van Mehdi -> gesprek op het bord. Geeft aantal."""
    if not TG_TOKEN:
        return 0
    d = tg("getUpdates", offset=staat.get("tg_offset", 0), timeout=0, allowed_updates=["message"])
    n = 0
    for u in d.get("result", []):
        staat["tg_offset"] = u["update_id"] + 1
        m = u.get("message") or {}
        if str(m.get("chat", {}).get("id")) != str(TG_CHAT):
            continue
        tekst = (m.get("text") or "").strip()
        if not tekst or tekst.startswith("/start"):
            continue
        aan, vraag = doel_van(tekst, namen)
        uit = bord.call("/api/gesprek", {"aan": aan, "tekst": vraag, "van": "mehdi (telegram)"})
        staat.setdefault("wacht", []).append({"id": uit["id"], "aan": uit["aan"]})
        ag.log(f"bericht {uit['id']}", "bron", f"uit Telegram aan {namen.get(uit['aan'], uit['aan'])}: {vraag[:120]}")
        n += 1
    if n:
        try:
            stuur_telegram(f"Ontvangen, {namen.get(aan, 'De Regisseur')} kijkt ernaar. Antwoord binnen een paar minuten.")
        except Exception:  # noqa: BLE001
            pass
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
                ag.log(f"bericht {w['id']}", "melding", f"antwoord van {kop} naar Telegram", g.get("antwoord", "")[:2000])
            else:
                rest.append(w)
        else:
            rest.append(w)
    staat["wacht"] = rest
    return klaar


# ------------------------------------------------------------------ main ---
def main():
    try:
        staat = json.load(open(STAAT))
    except (OSError, ValueError):
        staat = {"laatste_id": 0, "tg_offset": 0, "wacht": [], "laatste_herinnering": "", "laatste_voorstellen": 0}
    nood = []
    namen = agentnamen()
    binnen = lees_telegram(staat, namen)
    terug = antwoorden_terug(staat, namen, nood)

    uur = datetime.now().hour
    stil = uur >= STIL[0] or uur < STIL[1]
    items = [it for it in bord.call("/api/klaarzet?voor=mehdi&status=alle&n=200").get("items", [])
             if it["id"] > staat.get("laatste_id", 0) and it["soort"] in SOORTEN]
    agents_met_voorstel = [a for a in bord.call("/api/overzicht").get("agents", []) if a.get("open_voorstellen")]
    totaal_voorstellen = sum(a["open_voorstellen"] for a in agents_met_voorstel)
    alarm = [it for it in items if it["soort"] == "signaal" and "stil" in it["titel"].lower()]
    herinnering_oud = (not staat.get("laatste_herinnering")) or (datetime.now() - datetime.fromisoformat(staat["laatste_herinnering"])).total_seconds() > HERINNERING_UREN * 3600
    herinner = totaal_voorstellen and (totaal_voorstellen != staat.get("laatste_voorstellen", 0) or herinnering_oud)
    kanaal = ""
    if (items or herinner) and (not stil or alarm):
        regels = [f"Mehdi Agents, {datetime.now().strftime('%H:%M')}:"]
        for it in items[-8:]:
            regels.append(f"- {it['soort']}: {it['titel'][:110]} (van {it['van']})")
        if len(items) > 8:
            regels.append(f"- en nog {len(items) - 8} andere")
        if herinner:
            for a in agents_met_voorstel:
                regels.append(f"- {a['open_voorstellen']} voorstel(len) van {a['label']} wachten op je goedkeuring")
        regels.append("Bord: https://mijnagents.globaal.be")
        kanaal = stuur("\n".join(regels), nood)
        if kanaal:
            if items:
                staat["laatste_id"] = max(it["id"] for it in items)
            if herinner:
                staat["laatste_herinnering"] = datetime.now().isoformat()
                staat["laatste_voorstellen"] = totaal_voorstellen
            ag.log("bericht", "melding", f"{len(items)} items{', herinnering voorstellen' if herinner else ''} via {kanaal}", "\n".join(regels))
    json.dump(staat, open(STAAT, "w"))
    if not TG_TOKEN:
        nood.append({"tekst": "Telegram niet ingesteld: bot bij BotFather, TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID in mijnagents-data/.env", "wie": "mehdi"})
    nood.append({"tekst": "Bellen bij een alarm: dienst kiezen (Twilio of Xelion-API)", "wie": "mehdi"})
    ag.log_verstuur()
    detail = f"{binnen} binnen, {terug} antwoorden terug, {len(items)} items" + (f" via {kanaal}" if kanaal else "") + (f"; {len(staat.get('wacht', []))} wacht op antwoord" if staat.get("wacht") else "")
    ag.hartslag("actief" if (binnen or terug or kanaal) else ("rust" if stil else "waakt"),
                taak="luistert op Telegram" if TG_TOKEN else "luistert", detail=detail, nood=nood)


if __name__ == "__main__":
    main()
