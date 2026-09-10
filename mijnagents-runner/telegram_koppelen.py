"""Eenmalig: de Telegram-bot van De Bode koppelen (punt A5).

Draaien op de VM, in een gewone SSH-sessie, met Mehdi bereikbaar:

    python3 ~/appportal/mijnagents-runner/telegram_koppelen.py

Wat het doet:
1. vraagt het bot-token (van BotFather; zonder echo) of leest het uit
   ~/appportal/mijnagents-data/.env als het er al staat;
2. controleert het token bij Telegram (getMe) en toont de botnaam;
3. wacht tot Mehdi de bot opent en /start stuurt, en leest zo zijn chat-id;
4. schrijft TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID in mijnagents-data/.env
   (backup ernaast) en stuurt een testbericht.

Het token komt nooit op het scherm. De Bode (elke 5 min) gebruikt daarna
Telegram in plaats van Zoom-chat."""
import getpass
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.request

ENV = os.path.expanduser("~/appportal/mijnagents-data/.env")
WACHT_SECONDEN = 300


def lees_env():
    d = {}
    try:
        for regel in open(ENV, encoding="utf-8"):
            r = regel.strip()
            if r and not r.startswith("#") and "=" in r:
                k, v = r.split("=", 1)
                d[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return d


def zet_env(waarden):
    tekst = open(ENV, encoding="utf-8", newline="").read() if os.path.exists(ENV) else ""
    if os.path.exists(ENV):
        shutil.copy(ENV, ENV + ".bak-" + time.strftime("%Y%m%d%H%M"))
    for k, v in waarden.items():
        if re.search(rf"^{k}=.*$", tekst, re.M):
            tekst = re.sub(rf"^{k}=.*$", f"{k}={v}", tekst, flags=re.M)
        else:
            if tekst and not tekst.endswith("\n"):
                tekst += "\n"
            tekst += f"{k}={v}\n"
    open(ENV, "w", encoding="utf-8", newline="").write(tekst)
    os.chmod(ENV, 0o600)


def api(tok, methode, **params):
    data = json.dumps(params).encode() if params else None
    req = urllib.request.Request(f"https://api.telegram.org/bot{tok}/{methode}", data=data,
                                 headers={"Content-Type": "application/json"}, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=40) as r:
        a = json.load(r)
    if not a.get("ok"):
        raise RuntimeError(a.get("description", "onbekende fout"))
    return a["result"]


def main():
    env = lees_env()
    tok = env.get("TELEGRAM_BOT_TOKEN") or getpass.getpass("Bot-token van BotFather (wordt niet geëchood): ").strip()
    if not tok:
        print("Geen token; stop.")
        return 1
    try:
        bot = api(tok, "getMe")
    except (urllib.error.HTTPError, RuntimeError) as e:
        print("Telegram weigert het token:", str(e)[:120])
        return 1
    naam = bot.get("username", "")
    print(f"Bot gevonden: {bot.get('first_name', '')} (@{naam})")
    print(f"\nLaat MEHDI op zijn telefoon https://t.me/{naam} openen en op Start drukken (of /start sturen).")
    print(f"Ik wacht maximaal {WACHT_SECONDEN // 60} minuten op dat bericht...\n")

    # oude updates overslaan, dan wachten op een nieuw privébericht
    laatste = 0
    for u in api(tok, "getUpdates", timeout=0):
        laatste = max(laatste, u["update_id"])
    chat = None
    einde = time.time() + WACHT_SECONDEN
    while time.time() < einde and not chat:
        for u in api(tok, "getUpdates", offset=laatste + 1, timeout=25):
            laatste = max(laatste, u["update_id"])
            m = u.get("message") or {}
            if (m.get("chat") or {}).get("type") == "private":
                chat = m["chat"]
                break
    if not chat:
        print("Geen bericht ontvangen. Draai opnieuw zodra Mehdi de bot heeft geopend.")
        return 1
    wie = " ".join(x for x in (chat.get("first_name"), chat.get("last_name")) if x) + (f" (@{chat['username']})" if chat.get("username") else "")
    print(f"Bericht ontvangen van: {wie}")
    if "mehdi" not in wie.lower():
        antwoord = input("Dit lijkt niet Mehdi. Toch koppelen? [j/N] ").strip().lower()
        if antwoord != "j":
            print("Niet gekoppeld.")
            return 1
    zet_env({"TELEGRAM_BOT_TOKEN": tok, "TELEGRAM_CHAT_ID": str(chat["id"])})
    print("TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID staan in mijnagents-data/.env (backup ernaast).")
    api(tok, "sendMessage", chat_id=chat["id"],
        text="Gekoppeld. Vanaf nu meldt De Bode hier wat er voor je klaarstaat op https://mijnagents.globaal.be")
    print("Testbericht verstuurd. Klaar; De Bode gebruikt Telegram bij zijn volgende ronde (elke 5 min).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
