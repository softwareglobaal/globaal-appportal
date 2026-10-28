"""Geeft Uptime-Kuma een meldkanaal: Telegram naar Mehdi, op elke monitor.

Waarom: TODO "Pipedrive-backup": monitors 62/63 worden rood, maar niemand krijgt een bericht. Kuma had geen enkele
melding ingesteld.

Draaien op de VM (doet vm-onderhoud.sh voor je):
    python3 scripts/kuma-telegram.py /pad/naar/kuma.db

Wat het doet, en niets anders:
- leest TELEGRAM_BOT_TOKEN en TELEGRAM_CHAT_ID uit ~/appportal/mijnagents-data/.env (dezelfde bot als De Bode);
- maakt een melding "Telegram Mehdi" aan, of werkt ze bij als ze er al is (op naam);
- hangt ze aan elke monitor die ze nog niet heeft, en zet ze als standaard voor nieuwe monitors.

Kuma moet gestopt zijn terwijl dit draait; vm-onderhoud.sh stopt hem, maakt eerst een kopie van de databank en start
hem daarna weer. Het token komt nooit op het scherm.
"""
import json
import os
import sqlite3
import sys

NAAM = "Telegram Mehdi"
ENV = os.path.expanduser("~/appportal/mijnagents-data/.env")


def lees_env(pad):
    waarden = {}
    try:
        with open(pad, encoding="utf-8") as f:
            for regel in f:
                regel = regel.strip()
                if "=" in regel and not regel.startswith("#"):
                    sleutel, waarde = regel.split("=", 1)
                    waarden[sleutel.strip()] = waarde.strip().strip('"').strip("'")
    except OSError:
        pass
    return waarden


def main(db):
    env = lees_env(ENV)
    token, chat = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print(f"OVERGESLAGEN: geen TELEGRAM_BOT_TOKEN of TELEGRAM_CHAT_ID in {ENV}")
        return 2
    con = sqlite3.connect(db)
    try:
        tabellen = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        if not {"notification", "monitor", "monitor_notification"} <= tabellen:
            print("OVERGESLAGEN: dit is geen Uptime-Kuma-databank die ik ken (tabellen ontbreken)")
            return 2
        gebruiker = con.execute("select id from user order by id limit 1").fetchone()
        config = json.dumps({
            "name": NAAM, "type": "telegram", "isDefault": True, "applyExisting": True,
            "telegramBotToken": token, "telegramChatID": chat, "telegramSendSilently": False,
        })
        rij = con.execute("select id from notification where name = ?", (NAAM,)).fetchone()
        if rij:
            nid = rij[0]
            con.execute("update notification set config = ?, active = 1, is_default = 1 where id = ?", (config, nid))
            print(f"melding '{NAAM}' bijgewerkt (id {nid})")
        else:
            cur = con.execute(
                "insert into notification (name, config, active, user_id, is_default) values (?, ?, 1, ?, 1)",
                (NAAM, config, gebruiker[0] if gebruiker else None))
            nid = cur.lastrowid
            print(f"melding '{NAAM}' aangemaakt (id {nid})")
        monitors = [r[0] for r in con.execute("select id from monitor")]
        bestaand = {r[0] for r in con.execute(
            "select monitor_id from monitor_notification where notification_id = ?", (nid,))}
        nieuw = [m for m in monitors if m not in bestaand]
        con.executemany("insert into monitor_notification (monitor_id, notification_id) values (?, ?)",
                        [(m, nid) for m in nieuw])
        con.commit()
        print(f"{len(monitors)} monitors, {len(nieuw)} nieuw gekoppeld, {len(bestaand)} hadden ze al")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
