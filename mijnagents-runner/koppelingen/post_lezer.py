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
import time

sys.path.insert(0, "/app")
import config      # noqa: E402
import imapbron    # noqa: E402

opdracht = json.loads(os.environ.get("LEES", "{}"))
# Beheerde zorgafzenders (kine, tandarts): apart gezocht, ook zonder afspraakwoord in het onderwerp, ook met een
# List-Unsubscribe en verder terug dan de gewone twee weken ('Opdracht kine en tandarts' v1.0, 14-10-2026)
ZORG_AFZENDERS = [a.lower() for a in opdracht.get("zorg_afzenders") or []]


class _Herkans:
    """Een IMAP-sessie die bij Microsofts 'User is authenticated but not connected' opnieuw probeert. Gemeten 15-10-2026:
    de eerste poging faalt, de tweede vijftien seconden later lukt; op 14-10 om 10:46 viel Hotmail daardoor uit."""

    def __init__(self, mb, pogingen=4, wacht=15):
        self.mb, self.pogingen, self.wacht, self.s = mb, pogingen, wacht, None

    def __enter__(self):
        for i in range(self.pogingen):
            self.s = imapbron._Sessie(self.mb)
            try:
                return self.s.__enter__()
            except ValueError as e:
                if "not connected" not in str(e) or i == self.pogingen - 1:
                    raise
                time.sleep(self.wacht)

    def __exit__(self, *fout):
        return self.s.__exit__(*fout) if self.s else False
ONDERWERP = re.compile(r"(uitnodiging|invitation|invite|afspraak|appointment|meeting|vergadering|rendez-vous|"
                       r"geannuleerd|canceled|cancelled|geaccepteerd|accepted|bijgewerkt|updated|verplaatst|"
                       r"rescheduled|new event|nieuwe gebeurtenis|bevestiging van uw|confirmation of your|"
                       r"herinnering|reminder|reservatie|reservation|booking|boeking)", re.I)


LINKTIJD = re.compile(r"dates=(\d{8}T\d{6}Z?)(?:/|%2F)(\d{8}T\d{6}Z?)", re.I)


def tekst_en_ics(ruw, lengte=1500):
    """(bericht, ICS-delen, tekst, linktijden). De tekst komt uit text/plain, anders uit text/html (een bevestiging van
    de tandarts is alleen HTML). Linktijden: begin/einde uit een meegeleverde agenda-link (Google 'dates='), gelezen
    als gegevens, de link wordt nooit geopend."""
    m = email.message_from_bytes(ruw)
    ics, tekst, html, ruwe = [], "", "", []
    for deel in m.walk():
        soort = (deel.get_content_type() or "").lower()
        naam = (deel.get_filename() or "").lower()
        if soort == "text/calendar" or naam.endswith(".ics"):
            data = deel.get_payload(decode=True) or b""
            ics.append(data.decode(deel.get_content_charset() or "utf-8", "replace"))
        elif soort in ("text/plain", "text/html"):
            data = (deel.get_payload(decode=True) or b"").decode(deel.get_content_charset() or "utf-8", "replace")
            ruwe.append(data)
            if soort == "text/plain" and not tekst:
                tekst = data
            elif soort == "text/html" and not html:
                html = imapbron._html_naar_tekst(data)
    links = sorted({f"{a}/{b}" for d in ruwe for a, b in LINKTIJD.findall(d)})
    return m, ics, (tekst or html)[:lengte], links


def kop(m, veld):
    return imapbron._kop(m.get(veld))


# Mappen die geen afspraak dragen; de rest wordt gelezen, want mch@ sorteert mail in submappen (INBOX.Zoom, INBOX.Reizen)
# De jaarlijkse archiefmappen (Archief.2026) lees ik ook: een uitnodiging die Mehdi zelf daarheen sorteert, telt mee. De
# master zegt 'alle mappen behalve prullenbak, spam, verzonden en concepten' (Codex A21, 15-10-2026); SINCE houdt oude mail
# er toch buiten.
GEEN_AFSPRAAK = re.compile(r"(trash|spam|junk|drafts|deleted|sent|outbox|notes|sync issues|concepten|verzonden|prullenbak)", re.I)
GEEN_ZORG = GEEN_AFSPRAAK      # de zorgafzenders lazen de archiefmappen al: een oude bevestiging kan daar liggen


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
    zorg_mappen = mappen
    if not mappen:
        try:
            with _Herkans(mb) as M:
                alle = [n for a, n in imapbron._lijst_mappen(M) if "\\noselect" not in a]
            mappen = [n for n in alle if not GEEN_AFSPRAAK.search(n)]
            zorg_mappen = [n for n in alle if not GEEN_ZORG.search(n)]
        except Exception as e:  # noqa: BLE001
            fouten.append({"mailbox": adres, "fout": f"mappen niet te lezen: {type(e).__name__}: {str(e)[:200]}"})
            continue
    for mapnaam in list(dict.fromkeys(mappen + (zorg_mappen if ZORG_AFZENDERS else []))):
        try:
            with _Herkans(mb) as M:
                imapbron._selecteer(M, mapnaam)                      # read-only
                uids = []
                if mapnaam in mappen:
                    uids = imapbron.zoek_uids(M, imapbron._criteria(None, None, None, None, opdracht.get("sinds"), None, False))
                grens = int(opdracht.get("maximaal", 2000))
                if len(uids) > grens:
                    # een afgekapte map is geen volledige dekking: zeggen, niet zwijgen (nacontrole v1.2, V7)
                    fouten.append({"mailbox": adres, "map": mapnaam, "fout": f"afgekapt: {len(uids)} berichten sinds "
                                                                            f"{opdracht.get('sinds')}, {grens} gelezen"})
                uids = uids[:grens]
                # de zorgafzenders: apart, op afzender, sinds zorg_sinds; elk van die berichten is een kandidaat
                zorg_uids = set()
                for afz in ZORG_AFZENDERS:
                    try:
                        zorg_uids |= set(imapbron.zoek_uids(M, imapbron._criteria(afz, None, None, None, opdracht.get("zorg_sinds"), None, False)))
                    except Exception as e:  # noqa: BLE001
                        # een mislukte zorgzoekactie laat de gewone mail van deze map staan, maar telt als onvolledig (A06)
                        fouten.append({"mailbox": adres, "map": mapnaam, "fout": f"zorgzoekactie mislukt: {type(e).__name__}"})
                uids = list(dict.fromkeys(uids + sorted(zorg_uids - set(uids), reverse=True)))
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
                        zorg = int(um.group(1)) in zorg_uids
                        if not (zorg or heeft_ics or (ONDERWERP.search(onderwerp or "") and not reclame)):
                            continue
                        ok2, d2 = M.uid("FETCH", um.group(1), "(BODY.PEEK[])")
                        ruw = next((x[1] for x in (d2 or []) if isinstance(x, tuple)), None)
                        if ok2 != "OK" or not ruw:
                            fouten.append({"mailbox": adres, "map": mapnaam, "uid": int(um.group(1)),
                                           "fout": f"bericht niet op te halen ({ok2})"})
                            continue
                        try:
                            m, ics, tekst, links = tekst_en_ics(ruw, 6000 if zorg else 1500)
                        except Exception as e:  # noqa: BLE001
                            fouten.append({"mailbox": adres, "map": mapnaam, "uid": int(um.group(1)),
                                           "fout": f"bericht niet te ontleden ({type(e).__name__})"})
                            continue
                        # een zorgmail houdt zijn tekst ook naast een ICS: patiënt en behandelaar staan in de tekst
                        uit.append({"mailbox": mb["adres"], "map": mapnaam, "uid": int(um.group(1)),
                                    "message_id": kop(m, "Message-ID"), "van": kop(m, "From"), "onderwerp": kop(m, "Subject"),
                                    "datum": kop(m, "Date"), "ics": ics, "tekst": tekst if (zorg or not ics) else "",
                                    "zorg": zorg, "linktijden": links})
        except Exception as e:  # noqa: BLE001
            fouten.append({"mailbox": adres, "map": mapnaam, "fout": f"{type(e).__name__}: {str(e)[:200]}"})
print(json.dumps({"kandidaten": uit, "fouten": fouten}, ensure_ascii=False))
