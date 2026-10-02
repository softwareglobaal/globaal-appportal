"""Draait IN de postcontainer (docker exec -i appportal-app-post-1 python -), via stdin, met de opdracht als JSON in
de omgevingsvariabele LEES. Leest alleen: map read-only geselecteerd, alles met PEEK (geen \\Seen), niets verplaatst.
Geeft op stdout JSON: per kandidaat-afspraakmail de koppen, de ICS-delen en een kort tekstuittreksel.

Waarom in de container: daar staan de mailboxconfiguratie en het OAuth-token van Hotmail (Microsoft laat geen
wachtwoord meer toe op IMAP). Zo leest de server Hotmail zelf, zonder de Mac (audit 02-10-2026, A1).
"""
import email
import json
import os
import re
import sys

sys.path.insert(0, "/app")
import config      # noqa: E402
import imapbron    # noqa: E402

opdracht = json.loads(os.environ.get("LEES", "{}"))
ONDERWERP = re.compile(r"(uitnodiging|invitation|invite|afspraak|appointment|meeting|vergadering|rendez-vous|"
                       r"geannuleerd|canceled|cancelled|geaccepteerd|accepted|bijgewerkt|updated|verplaatst|"
                       r"rescheduled|new event|nieuwe gebeurtenis|bevestiging van uw|confirmation of your|"
                       r"herinnering|reminder|reservatie|reservation|booking|boeking)", re.I)


def tekst_en_ics(ruw):
    m = email.message_from_bytes(ruw)
    ics, tekst = [], ""
    for deel in m.walk():
        soort = (deel.get_content_type() or "").lower()
        naam = (deel.get_filename() or "").lower()
        if soort == "text/calendar" or naam.endswith(".ics"):
            data = deel.get_payload(decode=True) or b""
            ics.append(data.decode(deel.get_content_charset() or "utf-8", "replace"))
        elif soort == "text/plain" and not tekst:
            data = deel.get_payload(decode=True) or b""
            tekst = data.decode(deel.get_content_charset() or "utf-8", "replace")[:1500]
    return m, ics, tekst


def kop(m, veld):
    return imapbron._kop(m.get(veld))


# Mappen die geen afspraak dragen; de rest wordt gelezen, want mch@ sorteert mail in submappen (INBOX.Zoom, INBOX.Reizen)
GEEN_AFSPRAAK = re.compile(r"(trash|spam|junk|drafts|deleted|sent|outbox|notes|sync issues|archief\.20\d\d|concepten|verzonden|prullenbak)", re.I)


def antwoorden(data):
    """(meta, inhoud) per bericht uit een FETCH-antwoord. Outlook zet UID en BODYSTRUCTURE na het letterlijke blok, in
    het element erna; Dovecot ervoor. Beide samen lezen, anders valt Hotmail stil weg (gezien 02-10-2026)."""
    uit = []
    for i, el in enumerate(data or []):
        if isinstance(el, tuple):
            meta = el[0].decode("ascii", "replace")
            if i + 1 < len(data) and isinstance(data[i + 1], bytes):
                meta += " " + data[i + 1].decode("ascii", "replace")
            uit.append((meta, el[1]))
    return uit


uit, fouten = [], []
mailboxen, _ = config.alles()
for adres in opdracht.get("mailboxen", []):
    mb = next((x for x in mailboxen if x["adres"].lower() == adres.lower()), None)
    if not mb:
        fouten.append({"mailbox": adres, "fout": "niet in de configuratie"})
        continue
    mappen = opdracht.get("mappen", {}).get(adres)
    if not mappen:
        try:
            with imapbron._Sessie(mb) as M:
                mappen = [n for a, n in imapbron._lijst_mappen(M) if "\\noselect" not in a and not GEEN_AFSPRAAK.search(n)]
        except Exception as e:  # noqa: BLE001
            fouten.append({"mailbox": adres, "fout": f"mappen niet te lezen: {type(e).__name__}: {str(e)[:200]}"})
            continue
    for mapnaam in mappen:
        try:
            with imapbron._Sessie(mb) as M:
                imapbron._selecteer(M, mapnaam)                      # read-only
                uids = imapbron.zoek_uids(M, imapbron._criteria(None, None, None, None, opdracht.get("sinds"), None, False))
                uids = uids[: int(opdracht.get("maximaal", 400))]
                for i in range(0, len(uids), 100):
                    stuk = ",".join(str(u) for u in uids[i:i + 100])
                    ok, data = M.uid("FETCH", stuk, "(BODYSTRUCTURE BODY.PEEK[HEADER.FIELDS (SUBJECT FROM LIST-UNSUBSCRIBE)])")
                    if ok != "OK":
                        raise ValueError("FETCH mislukt")
                    for prefix, inhoud in antwoorden(data):
                        um = re.search(r"UID (\d+)", prefix)
                        if not um:
                            fouten.append({"mailbox": adres, "map": mapnaam, "fout": "antwoord zonder UID"})
                            continue
                        koppen = email.message_from_bytes(inhoud)
                        heeft_ics = "CALENDAR" in prefix.upper() or ".ICS" in prefix.upper()
                        onderwerp = imapbron._kop(koppen.get("Subject"))
                        reclame = bool(koppen.get("List-Unsubscribe"))
                        if not (heeft_ics or (ONDERWERP.search(onderwerp or "") and not reclame)):
                            continue
                        ok2, d2 = M.uid("FETCH", um.group(1), "(BODY.PEEK[])")
                        ruw = next((x[1] for x in (d2 or []) if isinstance(x, tuple)), None)
                        if ok2 != "OK" or not ruw:
                            continue
                        m, ics, tekst = tekst_en_ics(ruw)
                        uit.append({"mailbox": mb["adres"], "map": mapnaam, "uid": int(um.group(1)),
                                    "message_id": kop(m, "Message-ID"), "van": kop(m, "From"), "onderwerp": kop(m, "Subject"),
                                    "datum": kop(m, "Date"), "ics": ics, "tekst": "" if ics else tekst})
        except Exception as e:  # noqa: BLE001
            fouten.append({"mailbox": adres, "map": mapnaam, "fout": f"{type(e).__name__}: {str(e)[:200]}"})
print(json.dumps({"kandidaten": uit, "fouten": fouten}, ensure_ascii=False))
