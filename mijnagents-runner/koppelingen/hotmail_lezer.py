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
from datetime import date, datetime, timedelta, timezone
from email.utils import parseaddr, parsedate_to_datetime

sys.path.insert(0, "/app")
import config      # noqa: E402
import imapbron    # noqa: E402

# Zoals de Mac (mac/hotmail_koppen.py, NIET_BINNEN, daar met de Exchange-namen): een map die zo begint, ook een
# onderliggende, is geen binnengekomen post (overleg 26-10-2026, X2). Outlook.com noemt ze over IMAP Deleted, Junk, ...
NIET_BINNEN = re.compile(r"^(deleted|junk|drafts|outbox|sync issues|conversation history|archive)", re.I)
NIET_BINNEN_SOORT = {"\\trash", "\\junk", "\\drafts", "\\archive"}
VERZONDEN = re.compile(r"^sent( items)?$", re.I)
KOPPEN = ("FROM TO CC BCC SUBJECT DATE MESSAGE-ID IN-REPLY-TO REFERENCES AUTO-SUBMITTED PRECEDENCE LIST-ID "
          "LIST-UNSUBSCRIBE")
_UID = re.compile(r"UID (\d+)")
_ONTVANGEN = re.compile(r'INTERNALDATE "([^"]+)"')


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


def adressen(waarde):
    """Alle adressen van een kopregel, als 'Naam <adres>'. imapbron._adressen houdt er twintig; de klantenlijst
    (uitschrijven.ooit_gemaild) moet ze allemaal zien (Codex-controle 26-10-2026)."""
    return [d.strip() for d in re.split(r",(?![^<]*>)", imapbron._kop(waarde)) if d.strip()]


def _tijd(tekst, vorm=None):
    try:
        d = datetime.strptime(tekst.strip(), vorm) if vorm else parsedate_to_datetime(tekst)
    except (TypeError, ValueError, AttributeError):
        return None
    return d.astimezone(timezone.utc).isoformat() if d and d.tzinfo else None


def datum_van(meta, m):
    """De ontvangsttijd (INTERNALDATE) in UTC, zoals de Mac (date_received) en zoals SINCE zoekt; anders de Date-kop."""
    t = _ONTVANGEN.search(meta)
    return (t and _tijd(t.group(1), "%d-%b-%Y %H:%M:%S %z")) or _tijd(m.get("Date"))


def bericht(mapsoort, mapnaam, meta, ruw):
    m = email.message_from_bytes(ruw)
    u = _UID.search(meta)
    naam, adres = parseaddr(imapbron._kop(m.get("From")))
    # Bcc staat alleen op eigen verzonden post; de Mac zette het bij 'aan' (mac/hotmail_koppen.py, soort != 1).
    return {"map": mapsoort, "uid": f"{mapnaam}/{u.group(1)}" if u else None, "datum": datum_van(meta, m),
            "van": adres.lower(), "van_naam": naam,
            "aan": adressen(m.get("To")) + adressen(m.get("Bcc")), "cc": adressen(m.get("Cc")),
            "onderwerp": imapbron._kop(m.get("Subject")), "message_id": imapbron._kop(m.get("Message-ID")),
            "in_antwoord_op": imapbron._kop(m.get("In-Reply-To")),
            "verwijzingen": re.findall(r"<[^<>\s]+>", imapbron._kop(m.get("References"))),
            "automatisch": automatisch(m), "lijst": bool(m.get("List-Id") or m.get("List-Unsubscribe"))}


def lees_map(M, mapsoort, mapnaam, sinds):
    imapbron._selecteer(M, mapnaam)                                      # read-only
    uids = imapbron.zoek_uids(M, imapbron._criteria(None, None, None, None, sinds, None, False))
    uit = []
    for i in range(0, len(uids), 200):
        ok, data = M.uid("FETCH", ",".join(str(u) for u in uids[i:i + 200]),
                         f"(UID INTERNALDATE BODY.PEEK[HEADER.FIELDS ({KOPPEN})])")
        if ok != "OK":
            raise ValueError("koppen ophalen mislukt: " + imapbron._leesbaar(data))
        uit += [bericht(mapsoort, mapnaam, meta, ruw) for meta, ruw in antwoorden(data)]
    # Een bericht zonder UID of zonder datum zou de wacht stil overslaan (postvak.werk): dan is de map niet volledig.
    zonder = sum(1 for b in uit if not b["uid"] or not b["datum"])
    if zonder:
        raise ValueError(f"{zonder} bericht(en) zonder UID of datum")
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
    # vanaf: de eerste dag die elke soort dekt (SINCE); De Dagbundelaar meldt een oudere dag als onvolledig (overleg X2)
    return {"berichten": berichten, "fouten": fouten, "mappen": mappen, "vanaf": sinds}


if __name__ == "__main__":
    print(json.dumps(main(), ensure_ascii=False))
