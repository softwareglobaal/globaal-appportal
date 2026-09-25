#!/usr/bin/env python3
"""De koppen van mehdichegini@hotmail.com aan De Mailwacht hotmail (mail-prive, op de VM) geven.

Waarom via de Mac: Microsoft laat voor hotmail geen wachtwoord-login op IMAP toe (gemeten, ook op
25-09-2026). Mail op deze Mac haalt hotmail wel op (Exchange-account, Apple regelt de toegang), en
houdt een index bij: ~/Library/Mail/V10/MailData/Envelope Index. Dit script leest die index alleen
(sqlite, mode=ro), neemt de koppen (afzender, ontvangers, onderwerp, datum, Message-ID), nooit de
tekst, en zet ze op de VM in mijnagents-data/hotmail/koppen.json. De wacht op de VM doet de rest
met dezelfde regels als elke mailwacht (koppelingen/postvak.py).

Draait elk uur via launchd (be.globaal.mijnagents.mail-prive). Slaapt de Mac of staat Mail uit,
dan veroudert het bestand, en dan meldt de wacht dat zelf.

    hotmail_koppen.py            lezen en naar de VM zetten
    hotmail_koppen.py --droog    lezen en tellen, niets versturen
"""
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone

ADRES = "mehdichegini@hotmail.com"
INDEX = os.path.expanduser("~/Library/Mail/V10/MailData/Envelope Index")
ACCOUNTS = os.path.expanduser("~/Library/Accounts/Accounts4.sqlite")
DOEL = "~/appportal/mijnagents-data/hotmail/koppen.json"
ONTVANGEN_DAGEN, VERZONDEN_DAGEN = 30, 180
# Mappen van het account die geen binnengekomen post zijn.
NIET_BINNEN = ("Sent%20Items", "Deleted%20Items", "Junk%20Email", "Drafts", "Outbox", "Sync%20Issues",
               "Conversation%20History", "Archive", "Archiveren")


def ro(pad):
    return sqlite3.connect(f"file:{pad}?mode=ro", uri=True, timeout=10)


def account_id():
    """Het id van het Exchange-account van hotmail in de accounts van deze Mac."""
    c = ro(ACCOUNTS)
    r = c.execute("SELECT a.ZIDENTIFIER FROM ZACCOUNT a JOIN ZACCOUNTTYPE t ON a.ZACCOUNTTYPE=t.Z_PK "
                  "WHERE lower(a.ZUSERNAME)=? AND t.ZACCOUNTTYPEDESCRIPTION='Exchange'", (ADRES,)).fetchone()
    if not r:
        raise LookupError(f"{ADRES} staat niet als Exchange-account in Mail op deze Mac")
    return r[0]


def lees():
    acc = account_id()
    c = ro(INDEX)
    nu = datetime.now(timezone.utc)
    mappen = {}
    for rowid, url in c.execute("SELECT ROWID, url FROM mailboxes WHERE url LIKE ?", (f"ews://{acc}/%",)):
        pad = url.split(f"ews://{acc}/", 1)[1]
        if pad == "Sent%20Items":
            mappen[rowid] = "Sent"
        elif not pad.startswith(NIET_BINNEN):
            mappen[rowid] = "INBOX"
    if not mappen:
        raise LookupError("geen mappen van hotmail in de index van Mail")
    ontvangers = {}
    uit = []
    vraag = ("SELECT m.ROWID, m.mailbox, m.date_received, a.address, a.comment, m.subject_prefix, s.subject, g.message_id_header "
             "FROM messages m LEFT JOIN addresses a ON m.sender=a.ROWID LEFT JOIN subjects s ON m.subject=s.ROWID "
             "LEFT JOIN message_global_data g ON m.global_message_id=g.ROWID "
             f"WHERE m.deleted=0 AND m.mailbox IN ({','.join('?' * len(mappen))}) AND m.date_received >= ?")
    grens_verzonden = (nu - timedelta(days=VERZONDEN_DAGEN)).timestamp()
    for rid, mbox, ts, van, naam, prefix, ond, mid in c.execute(vraag, (*mappen, grens_verzonden)):
        kaart = mappen[mbox]
        if kaart == "INBOX" and ts < (nu - timedelta(days=ONTVANGEN_DAGEN)).timestamp():
            continue
        uit.append({"map": kaart, "uid": rid, "datum": datetime.fromtimestamp(ts, timezone.utc).isoformat(),
                    "van": (van or "").lower(), "van_naam": naam or "", "aan": [], "cc": [],
                    "onderwerp": ((prefix or "") + (ond or "")).strip(), "message_id": mid or ""})
    ids = [b["uid"] for b in uit]
    for i in range(0, len(ids), 500):
        deel = ids[i:i + 500]
        for msg, adres, naam, soort in c.execute(
                "SELECT r.message, a.address, a.comment, r.type FROM recipients r JOIN addresses a ON r.address=a.ROWID "
                f"WHERE r.message IN ({','.join('?' * len(deel))}) ORDER BY r.position", deel):
            ontvangers.setdefault(msg, []).append((f"{naam} <{adres}>" if naam else adres, soort))
    for b in uit:
        for tekst, soort in ontvangers.get(b["uid"], []):
            (b["cc"] if soort == 1 else b["aan"]).append(tekst)
    return {"gemaakt": nu.isoformat(), "adres": ADRES, "account": acc, "berichten": uit}


def main():
    d = lees()
    tel = {k: sum(1 for b in d["berichten"] if b["map"] == k) for k in ("INBOX", "Sent")}
    if "--droog" in sys.argv:
        print(json.dumps(tel), d["gemaakt"])
        return
    data = json.dumps(d, ensure_ascii=False)
    opdracht = f"mkdir -p ~/appportal/mijnagents-data/hotmail && cat > {DOEL}.nieuw && mv {DOEL}.nieuw {DOEL}"
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "globaal", opdracht],
                       input=data, capture_output=True, text=True, timeout=120)
    if r.returncode:
        raise SystemExit(f"naar de VM zetten mislukt: {r.stderr.strip()[:200]}")
    print(f"{datetime.now().isoformat(timespec='seconds')} hotmail: {tel['INBOX']} binnen ({ONTVANGEN_DAGEN} d), "
          f"{tel['Sent']} verzonden ({VERZONDEN_DAGEN} d), naar de VM gezet")


if __name__ == "__main__":
    main()
