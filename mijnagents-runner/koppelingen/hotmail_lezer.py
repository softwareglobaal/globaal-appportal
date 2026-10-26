"""Draait IN de postcontainer (docker exec -i appportal-app-post-1 python -), via stdin, met de opdracht als JSON in
de omgevingsvariabele LEES. Leest de koppen van hotmail voor De Mailwacht hotmail: map read-only geselecteerd, alles
met PEEK (geen \\Seen), niets verplaatst, nooit de tekst. Geeft op stdout JSON: {"berichten": [...], "fouten": [...]}.

Waarom hier: daar staat het OAuth-token van Hotmail (post/oauth_ms.py), zoals bij post_lezer.py. Tot 26-10-2026 kwamen
deze koppen van Mail op de Mac (mac/hotmail_koppen.py), maar launchd heeft daar geen Full Disk Access en elke run viel
sinds 26-09-2026 stil op 'authorization denied'.

Een bericht heeft de vorm van imapbron.lijst (van, aan, cc, onderwerp, datum, message_id, in_antwoord_op, verwijzingen)
plus wat de Mac ook gaf: map (INBOX of Sent), automatisch en lijst.
"""
import email
import json
import os
import re
import sys
from datetime import date, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

sys.path.insert(0, "/app")
import config      # noqa: E402
import imapbron    # noqa: E402

# Zoals de Mac (mac/hotmail_koppen.py, NIET_BINNEN, daar met de Exchange-namen): een map die zo begint, ook een
# onderliggende, is geen binnengekomen post (overleg 26-10-2026, X2). Outlook.com noemt ze over IMAP Deleted, Junk, ...
NIET_BINNEN = re.compile(r"^(deleted|junk|drafts|outbox|sync issues|conversation history|archive)", re.I)
NIET_BINNEN_SOORT = {"\\trash", "\\junk", "\\drafts", "\\archive"}
VERZONDEN = re.compile(r"^sent( items)?$", re.I)
KOPPEN = ("FROM TO CC SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES AUTO-SUBMITTED PRECEDENCE LIST-ID "
          "LIST-UNSUBSCRIBE")
_UID = re.compile(r"UID (\d+)")


def soort_map(attributen, naam):
    """'Sent', 'INBOX' of None (niet lezen) voor een map uit de LIST van hotmail."""
    if "\\noselect" in attributen:
        return None
    if "\\sent" in attributen or VERZONDEN.match(naam):
        return "Sent"
    if NIET_BINNEN_SOORT & set(attributen) or NIET_BINNEN.match(naam):
        return None
    return "INBOX"


def antwoorden(data):
    """(meta, koppen) per bericht uit een FETCH-antwoord. Outlook zet de UID na het letterlijke blok, in het element
    erna; Dovecot ervoor (zie post_lezer.antwoorden, gezien 02-10-2026). Beide samen lezen."""
    uit = []
    for i, el in enumerate(data or []):
        if isinstance(el, tuple):
            meta = el[0].decode("ascii", "replace")
            if i + 1 < len(data) and isinstance(data[i + 1], bytes):
                meta += " " + data[i + 1].decode("ascii", "replace")
            uit.append((meta, el[1]))
    return uit


def automatisch(m):
    """Automatisch verstuurd (geen mens): Auto-Submitted (RFC 3834) anders dan 'no', of Precedence bulk, list of junk
    (overleg 26-10-2026, X3). De Mac gaf hier Mails eigen oordeel (automated_conversation)."""
    auto = imapbron._kop(m.get("Auto-Submitted")).strip().lower()
    return (bool(auto) and auto != "no") or imapbron._kop(m.get("Precedence")).strip().lower() in ("bulk", "list", "junk")


def bericht(mapsoort, mapnaam, uid, ruw):
    m = email.message_from_bytes(ruw)
    try:
        datum = parsedate_to_datetime(m.get("Date"))
        datum = datum.astimezone(timezone.utc).isoformat() if datum else None   # zoals de Mac: in UTC, dan sorteert het
    except (TypeError, ValueError):
        datum = None
    naam, adres = parseaddr(imapbron._kop(m.get("From")))
    return {"map": mapsoort, "uid": f"{mapnaam}/{uid}", "datum": datum, "van": adres.lower(), "van_naam": naam,
            "aan": imapbron._adressen(m.get("To")), "cc": imapbron._adressen(m.get("Cc")),
            "onderwerp": imapbron._kop(m.get("Subject")), "message_id": imapbron._kop(m.get("Message-ID")),
            "in_antwoord_op": imapbron._kop(m.get("In-Reply-To")),
            "verwijzingen": re.findall(r"<[^<>\s]+>", imapbron._kop(m.get("References"))),
            "automatisch": automatisch(m), "lijst": bool(m.get("List-Id") or m.get("List-Unsubscribe"))}


def lees_map(M, mapsoort, mapnaam, sinds):
    imapbron._selecteer(M, mapnaam)                                      # read-only
    uids = imapbron.zoek_uids(M, imapbron._criteria(None, None, None, None, sinds, None, False))
    uit = []
    for i in range(0, len(uids), 200):
        ok, data = M.uid("FETCH", ",".join(str(u) for u in uids[i:i + 200]), f"(UID BODY.PEEK[HEADER.FIELDS ({KOPPEN})])")
        if ok != "OK":
            raise ValueError("koppen ophalen mislukt: " + imapbron._leesbaar(data))
        for meta, ruw in antwoorden(data):
            u = _UID.search(meta)
            uit.append(bericht(mapsoort, mapnaam, u.group(1) if u else "?", ruw))
    return uit, len(uids)


def main():
    opdracht = json.loads(os.environ.get("LEES", "{}"))
    adres = opdracht["adres"]
    vandaag = date.fromisoformat(opdracht["vandaag"])
    sinds = {"INBOX": (vandaag - timedelta(days=opdracht["binnen_dagen"])).isoformat(),
             "Sent": (vandaag - timedelta(days=opdracht["verzonden_dagen"])).isoformat()}
    mailboxen, _ = config.alles()
    mb = next((x for x in mailboxen if x["adres"].lower() == adres.lower()), None)
    if not mb:
        return {"berichten": [], "fouten": [f"{adres} niet in de configuratie"], "mappen": {}}
    berichten, fouten, mappen = [], [], {}
    with imapbron._Sessie(mb) as M:
        for attributen, mapnaam in imapbron._lijst_mappen(M):
            mapsoort = soort_map(attributen, mapnaam)
            if not mapsoort:
                continue
            try:
                deel, gevonden = lees_map(M, mapsoort, mapnaam, sinds[mapsoort])
            except Exception as e:  # noqa: BLE001
                fouten.append(f"{mapnaam}: {type(e).__name__}: {str(e)[:200]}")
                continue
            if len(deel) != gevonden:
                fouten.append(f"{mapnaam}: {gevonden} gevonden, {len(deel)} gelezen")
            mappen[mapnaam] = {"soort": mapsoort, "berichten": len(deel)}
            berichten += deel
    return {"berichten": berichten, "fouten": fouten, "mappen": mappen}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
