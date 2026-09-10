#!/usr/bin/env python3
"""De Mailwacht (Privé · Communicatie) — draait op Mehdi's Mac, per mailbox.
Wachtwoord uit de Keychain (service onemail, zoals ~/.claude/tools/onemail.py).
Leest alleen (BODY.PEEK, niets als gelezen gemarkeerd), triëert deterministisch
(rol van de afzender, sleutelwoorden, nieuwsbrief-koppen), zet rijen in de
gesprekkentabel (bron mail), signalen voor Mehdi, en het dagoverzicht.
Werkwijze op het bord: werkwijze/mail-mch.md en mail-prive.md.

Gebruik: mail_wacht.py --account mch@h-architects.be --naam mail-mch [--uren 24]
"""
import argparse
import email
import email.utils
import imaplib
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header

BORD = os.environ.get("MIJNAGENTS_URL", "https://mijnagents.globaal.be")
PROVIDERS = {"h-architects.be": ("imap.one.com", 993), "hotmail.com": ("outlook.office365.com", 993)}
ROLLEN = {  # domein- of naamdelen -> rol, belang hoog
    "boekhouder": ["octopus", "boekhoud", "accountant", "fiscal"], "bank": ["kbc", "belfius", "bnp", "ing.be", "argenta", "crelan", "bank"],
    "overheid": ["belgium.be", "vlaanderen.be", "minfin", "fod", "rsz", "onss", "gemeente", "stad", "omgevingsloket"],
    "notaris": ["notaris"], "advocaat": ["advoca", "law"], "verzekering": ["verzeker", "insurance", "ag.be", "axa", "ethias"],
    "arts": ["dokter", "ziekenhuis", "uz ", "az ", "apotheek", "mutualiteit", "cm.be"],
}
HOOG = ["factuur", "betaling", "betalen", "herinnering", "aanmaning", "deadline", "uiterlijk", "dringend", "urgent", "ingebrekestelling", "vervaldag", "contract", "vergunning", "belasting", "aanslag", "deurwaarder"]
LAAG = ["nieuwsbrief", "newsletter", "unsubscribe", "uitschrijven", "aanbieding", "korting", "promo", "webinar", "no-reply", "noreply"]


def token():
    try:
        return open(os.path.expanduser("~/.config/mijnagents/token")).read().strip()
    except OSError:
        return ""


def bord(pad, payload):
    req = urllib.request.Request(f"{BORD}{pad}", data=json.dumps(payload).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "X-Agents-Token": token()})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode() or "{}")


def wachtwoord(account):
    r = subprocess.run(["security", "find-generic-password", "-s", "onemail", "-a", account, "-w"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def dec(v):
    try:
        return str(make_header(decode_header(v or "")))
    except Exception:  # noqa: BLE001
        return v or ""


def tekst_van(b):
    if b.is_multipart():
        for d in b.walk():
            if d.get_content_type() == "text/plain" and not d.get_filename():
                return d.get_payload(decode=True).decode(d.get_content_charset() or "utf-8", "replace")
        for d in b.walk():
            if d.get_content_type() == "text/html":
                return re.sub(r"<[^>]+>", " ", d.get_payload(decode=True).decode(d.get_content_charset() or "utf-8", "replace"))
        return ""
    return b.get_payload(decode=True).decode(b.get_content_charset() or "utf-8", "replace")


def trieer(van, onderwerp, tekst, koppen):
    laag = (van + " " + onderwerp).lower()
    rol = next((r for r, delen in ROLLEN.items() if any(d in laag for d in delen)), "")
    nieuwsbrief = bool(koppen.get("List-Unsubscribe")) or any(w in laag for w in LAAG)
    hoog = rol in ("boekhouder", "bank", "overheid", "notaris", "advocaat", "deurwaarder") or any(w in (onderwerp + " " + tekst[:600]).lower() for w in HOOG)
    belang = "laag" if nieuwsbrief and not hoog else ("hoog" if hoog else "midden")
    soort = "nieuwsbrief" if nieuwsbrief else ("factuur" if re.search(r"factuur|invoice|betaling", laag) else ("afspraak" if re.search(r"afspraak|meeting|uitnodiging", laag) else "bericht"))
    waarom = ", ".join(x for x in (f"rol {rol}" if rol else "", "nieuwsbrief-kop" if koppen.get("List-Unsubscribe") else "",
                                   next((f"woord '{w}'" for w in HOOG if w in (onderwerp + " " + tekst[:600]).lower()), "")) if x) or "geen bijzonder kenmerk"
    return rol, belang, soort, waarom


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--account", required=True); p.add_argument("--naam", required=True); p.add_argument("--uren", type=int, default=25)
    p.add_argument("--prive", action="store_true", help="alles alleen voor Mehdi, nooit voor een afdeling")
    a = p.parse_args()
    naam = a.naam
    pw = wachtwoord(a.account)
    if not pw:
        bord("/agent-status", {"naam": naam, "status": "rust", "taak": "geen wachtwoord", "detail": "wacht op Keychain",
                               "nood": [{"tekst": f"Geen wachtwoord in de Keychain voor {a.account}: security add-generic-password -s onemail -a {a.account} -w (hotmail: app-wachtwoord)", "wie": "mehdi"}]})
        print("geen wachtwoord"); return
    bord("/agent-status", {"naam": naam, "status": "actief", "taak": "mail lezen"})
    host = PROVIDERS.get(a.account.split("@")[-1].lower(), ("imap.one.com", 993))
    sinds = (datetime.now(timezone.utc) - timedelta(hours=a.uren)).strftime("%d-%b-%Y")
    M = imaplib.IMAP4_SSL(*host)
    try:
        M.login(a.account, pw)
        M.select("INBOX", readonly=True)
        ok, nums = M.search(None, "SINCE", sinds)
        uids = nums[0].split() if ok == "OK" and nums and nums[0] else []
        rijen, signalen, tel = [], [], {"hoog": 0, "midden": 0, "laag": 0}
        for uid in uids[-300:]:
            ok, data = M.fetch(uid, "(BODY.PEEK[])")
            if ok != "OK" or not data or not data[0]:
                continue
            b = email.message_from_bytes(data[0][1])
            van, ond = dec(b.get("From")), dec(b.get("Subject"))
            try:
                dt = email.utils.parsedate_to_datetime(b.get("Date")).astimezone()
            except Exception:  # noqa: BLE001
                dt = datetime.now().astimezone()
            if dt < datetime.now().astimezone() - timedelta(hours=a.uren):
                continue
            tekst = re.sub(r"\s+", " ", tekst_van(b)).strip()
            rol, belang, soort, waarom = trieer(van, ond, tekst, b)
            tel[belang] += 1
            mid = (b.get("Message-ID") or f"{a.account}:{uid.decode()}").strip()
            rijen.append({"uniek": f"mail:{mid[:150]}", "datum": dt.strftime("%Y-%m-%d"), "start": dt.strftime("%H:%M"), "minuten": 0,
                          "personen": re.sub(r"<.*?>", "", van).strip()[:80], "bedrijf": (re.search(r"@([\w.-]+)", van) or [None, ""])[1],
                          "afdeling": "prive" if a.prive else "", "thema": f"{soort}: {ond[:90]}", "project": "", "prive": 1 if a.prive else 0,
                          "zekerheid": "hoog" if rol else "middel", "waarom": f"belang {belang}; {waarom}", "archief": "", "link": "",
                          "opgenomen_door": a.account, "bron": "mail"})
            if belang == "hoog":
                signalen.append({"van": naam, "voor": "mehdi", "soort": "signaal", "sleutel": dt.strftime("%Y-%m-%d"),
                                 "titel": f"Mail hoog belang: {re.sub(r'<.*?>', '', van).strip()[:40]} · {ond[:70]}", "uniek": f"mailsignaal:{mid[:150]}",
                                 "inhoud": {"van": van, "onderwerp": ond, "datum": dt.isoformat(), "rol": rol, "waarom": waarom, "begin": tekst[:400]}})
        vandaag = datetime.now().date().isoformat()
        overzicht = f"{a.account} laatste {a.uren} u: {len(rijen)} mails; hoog {tel['hoog']}, midden {tel['midden']}, laag (nieuwsbrief) {tel['laag']}"
        if rijen:
            bord("/api/gesprekken", {"rijen": rijen})
        items = signalen + [{"van": naam, "voor": "mehdi", "soort": "mail", "sleutel": vandaag, "titel": f"Mail {a.account} {vandaag}", "uniek": f"mailoverzicht:{naam}:{vandaag}",
                             "inhoud": {"datum": vandaag, "overzicht": overzicht, "hoog": [s["titel"] for s in signalen][:20]}}]
        uit = bord("/api/klaarzet", {"items": items})
        bord("/api/logboek", {"regels": [
            {"naam": naam, "onderwerp": f"dag {vandaag}", "stap": "bron", "tekst": overzicht, "detail": "\n".join(f"{r['datum']} {r['start']} {r['personen'][:30]} | {r['thema'][:70]} | {r['waarom']}" for r in rijen[-80:])},
            {"naam": naam, "onderwerp": f"dag {vandaag}", "stap": "schrijf", "tekst": f"{len(rijen)} rijen in de gesprekkentabel; {len(signalen)} signalen; klaargezet {uit.get('nieuw', 0)} nieuw"}]})
        bord("/agent-status", {"naam": naam, "status": "waakt", "taak": "mail in het oog", "detail": overzicht,
                               "nood": [{"tekst": "Opruimen (verplaatsen, uitschrijven) gebeurt pas na een goedgekeurd voorstel; runbook nog te maken", "wie": "claude-code"}]})
        print(overzicht)
    finally:
        try:
            M.logout()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
