"""Postbus: de watcher die uit zichzelf doorstuurt.

De MCP-tool `doorsturen` werkt op verzoek: iemand vraagt het aan Claude en dan
gebeurt het. Voor post die zonder tussenkomst moet vertrekken, zoals de
facturen van Anthropic naar de boekhouding, is dat niet genoeg. Deze agent
draait als eigen proces, kijkt met een vast ritme in de mailbox en stuurt door
wat aan de regel voldoet.

Hij deelt bewust alle rails met de tool, want hij roept dezelfde
`verzenden.doorsturen` aan:

- De bestemming moet in `doorsturen:` van de mailbox staan (mailboxen.yaml).
- De noodrem POSTBUS_DOORSTUREN geldt ook hier: staat die uit, dan gaat er
  niets uit, ook niet automatisch.
- Het origineel gaat onaangeroerd als bijlage mee en er komt een kopie in
  Verzonden.

Wat deze agent er zelf bovenop zet:

1. **Alleen wat nieuw is.** Bij de eerste start noteert hij welke berichten er
   al staan en stuurt die NIET door. Anders zou hij bij het aanzetten in een
   klap de hele geschiedenis (honderden facturen) naar de boekhouding sturen.
   Wil je die geschiedenis wel, zet dan POSTBUS_AGENT_BACKFILL=ja.
2. **Nooit twee keer.** Elk doorgestuurd bericht wordt op Message-ID
   onthouden in een klein statusbestand, zodat een herstart niets herhaalt.

De regel staat in omgevingsvariabelen; er is er nu een. Komt er een tweede
soort post bij, dan is dit de plek om het uit te breiden.
"""
import json
import os
import time
from datetime import datetime, timezone

import config
import imapbron
import verzenden

MAILBOX = os.environ.get("POSTBUS_AGENT_MAILBOX", "").strip()
ONDERWERP = os.environ.get("POSTBUS_AGENT_ONDERWERP", "").strip()
NAAR = os.environ.get("POSTBUS_AGENT_NAAR", "").strip()
MAP = os.environ.get("POSTBUS_AGENT_MAP", "INBOX").strip() or "INBOX"
INTERVAL = int(os.environ.get("POSTBUS_AGENT_INTERVAL", "300"))
# Pauze tussen twee verzendingen. one.com knijpt af bij te veel mail binnen vijf
# minuten (een 451 "Too many mails"), dus we blijven daar ruim onder: 20 seconden
# is een stuk of vijftien per vijf minuten. Kost bij een grote inhaalslag wat
# tijd, maar dan komt alles aan in plaats van de helft te stuiten.
PAUZE = int(os.environ.get("POSTBUS_AGENT_PAUZE", "20"))
BACKFILL = os.environ.get("POSTBUS_AGENT_BACKFILL", "").strip().lower() in \
    {"ja", "yes", "waar", "true", "aan"}
STATUSPAD = os.environ.get("POSTBUS_AGENT_STATE",
                           "/state/doorgestuurd.json")


def log(boodschap):
    stempel = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[doorstuuragent] {stempel} {boodschap}", flush=True)


def _lees_status():
    try:
        with open(STATUSPAD, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError):
        return {}


def _schrijf_status(status):
    tijdelijk = STATUSPAD + ".tmp"
    os.makedirs(os.path.dirname(STATUSPAD) or ".", exist_ok=True)
    with open(tijdelijk, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    os.replace(tijdelijk, STATUSPAD)


def _treffers(mailbox, alles=False):
    """(uid, message_id, onderwerp) van berichten die aan de regel voldoen.

    Het zoeken gebeurt op de mailserver via imapbron.lijst; SUBJECT is daar
    hoofdletterongevoelig en op deeltekst. We controleren het onderwerp daarna
    zelf nog eens, want de serverzoekopdracht is ruimer dan we willen en we
    sturen liever te weinig dan te veel door.

    Standaard halen we alleen de nieuwste pagina op: bij het gewone rondje zijn
    er per keer maar een paar nieuwe. Met alles=True (de eerste start) lopen we
    door tot de laatste, zodat de hele bestaande voorraad wordt afgedekt.
    """
    uit = []
    vanaf = 0
    while True:
        blok = imapbron.lijst(mailbox, MAP, onderwerp=ONDERWERP,
                              maximaal=100, vanaf=vanaf)
        for b in blok["berichten"]:
            onderwerp = b.get("onderwerp") or ""
            if ONDERWERP.lower() not in onderwerp.lower():
                continue
            uit.append((b["uid"], b.get("message_id"), onderwerp))
        if not alles or not blok.get("meer"):
            break
        vanaf = blok["volgende_vanaf"]
    return uit


def _ronde(mailbox):
    status = _lees_status()
    gezien = set(status.get("gezien", []))
    eerste_keer = "gestart" not in status

    try:
        treffers = _treffers(mailbox, alles=eerste_keer)
    except Exception as e:
        log(f"kon niet zoeken in {MAILBOX}: {type(e).__name__}: {e}")
        return

    if eerste_keer and not BACKFILL:
        for _, mid, _ in treffers:
            if mid:
                gezien.add(mid)
        status = {"gestart": datetime.now(timezone.utc).isoformat(),
                  "gezien": sorted(gezien)}
        _schrijf_status(status)
        log(f"eerste start: {len(gezien)} bestaande berichten overgeslagen, "
            "vanaf nu worden nieuwe doorgestuurd. Zet POSTBUS_AGENT_BACKFILL=ja "
            "als de bestaande wel doorgestuurd moeten worden.")
        return

    if eerste_keer and BACKFILL:
        log(f"eerste start met backfill: {len(treffers)} bestaande berichten "
            "worden alsnog doorgestuurd.")
        status["gestart"] = datetime.now(timezone.utc).isoformat()

    # treffers staan nieuwste eerst; omdraaien zodat we in volgorde van
    # binnenkomst doorsturen, dat leest in de boekhouding het prettigst.
    nieuw = [(uid, mid, ond) for uid, mid, ond in reversed(treffers)
             if not mid or mid not in gezien]
    if not nieuw:
        return

    for i, (uid, mid, onderwerp) in enumerate(nieuw):
        try:
            resultaat = verzenden.doorsturen(mailbox, MAP, uid, NAAR)
        except Exception as e:
            # Het dagplafond is geen storing maar een grens: de rest gaat morgen
            # vanzelf. Dan heeft doorgaan geen zin, dus we stoppen dit rondje.
            if "plafond" in str(e).lower():
                log("dagplafond bereikt; de resterende berichten volgen een "
                    "volgende dag vanzelf.")
                break
            # Andere fouten (bijvoorbeeld tijdelijk afknijpen door de mailserver):
            # niet als gezien markeren, zodat de volgende ronde het opnieuw
            # probeert. Wel pauzeren, om de server niet verder te belasten.
            log(f"doorsturen mislukte voor uid {uid} ({onderwerp[:60]}): "
                f"{type(e).__name__}: {e}")
            if i < len(nieuw) - 1:
                time.sleep(PAUZE)
            continue
        if mid:
            gezien.add(mid)
        status["gezien"] = sorted(gezien)
        _schrijf_status(status)
        log(f"doorgestuurd naar {NAAR}: {onderwerp[:70]} "
            f"({resultaat.get('vandaag_verstuurd')}/{resultaat.get('dagplafond')} "
            f"vandaag, kopie in Verzonden: {resultaat.get('kopie_in_verzonden')})")
        # Rustig aan blijven, ook als het net goed ging: het is juist het tempo
        # dat de mailserver deed afknijpen.
        if i < len(nieuw) - 1:
            time.sleep(PAUZE)


def _controleer_opzet():
    fouten = []
    if not MAILBOX:
        fouten.append("POSTBUS_AGENT_MAILBOX is niet gezet")
    if not ONDERWERP:
        fouten.append("POSTBUS_AGENT_ONDERWERP is niet gezet")
    if not NAAR:
        fouten.append("POSTBUS_AGENT_NAAR is niet gezet")
    if fouten:
        for f in fouten:
            log("opzet onvolledig: " + f)
        return None
    # config.zoek filtert op de toegang van een ingelogde gebruiker; de agent
    # hoort niet achter een login te zitten, dus we pakken de mailbox
    # rechtstreeks uit het bestand.
    alle, _ = config.alles()
    mailbox = next((m for m in alle if m["adres"].lower() == MAILBOX.lower()),
                   None)
    if not mailbox:
        log(f"opzet: mailbox {MAILBOX} staat niet in mailboxen.yaml")
        return None
    if NAAR.lower() not in (mailbox.get("doorsturen") or []):
        log(f"opzet: {NAAR} staat niet in 'doorsturen:' van {MAILBOX}. "
            "Voeg het daar toe, anders weigert het versturen terecht.")
        return None
    if not mailbox.get("smtp_host"):
        log(f"opzet: {MAILBOX} heeft geen smtp_host, doorsturen kan niet.")
        return None
    return mailbox


def main():
    log(f"start. mailbox={MAILBOX or '?'} onderwerp={ONDERWERP!r} "
        f"naar={NAAR or '?'} interval={INTERVAL}s backfill={BACKFILL}")
    if not verzenden.ACTIEF:
        log("let op: de noodrem POSTBUS_DOORSTUREN staat uit. De agent draait, "
            "maar er gaat niets de deur uit tot die op 'ja' staat.")
    while True:
        mailbox = _controleer_opzet()
        if mailbox is None:
            time.sleep(INTERVAL)
            continue
        if not verzenden.ACTIEF:
            time.sleep(INTERVAL)
            continue
        try:
            _ronde(mailbox)
        except Exception as e:
            log(f"onverwacht in deze ronde: {type(e).__name__}: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
