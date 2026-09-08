"""Postbus: de watcher die uit zichzelf doorstuurt.

De MCP-tool `doorsturen` werkt op verzoek: iemand vraagt het aan Claude en dan
gebeurt het. Voor post die zonder tussenkomst moet vertrekken, zoals de
facturen van Anthropic naar de boekhouding, is dat niet genoeg. Deze agent
draait als eigen proces, kijkt met een vast ritme in de mailbox en stuurt door
wat aan een regel voldoet.

Hij deelt bewust alle rails met de tool, want hij roept dezelfde
`verzenden.doorsturen` aan:

- De bestemming moet in `doorsturen:` van de mailbox staan (mailboxen.yaml).
- De noodrem POSTBUS_DOORSTUREN geldt ook hier: staat die uit, dan gaat er
  niets uit, ook niet automatisch.
- Het origineel gaat onaangeroerd als bijlage mee en er komt een kopie in
  Verzonden.

Wat deze agent er zelf bovenop zet:

1. **Alleen wat nieuw is.** Bij de eerste start van een regel noteert hij welke
   berichten er al staan en stuurt die NIET door. Anders zou hij bij het
   aanzetten in een klap de hele geschiedenis (honderden facturen) naar de
   boekhouding sturen. Wil je die geschiedenis wel, zet dan backfill aan.
2. **Nooit twee keer.** Elk doorgestuurd bericht wordt op Message-ID
   onthouden in een klein statusbestand, per regel, zodat een herstart niets
   herhaalt.

Regels. Sinds 8 september 2026 kunnen het er meer zijn, in
POSTBUS_AGENT_REGELS als JSON-lijst:

    [{"mailbox": "mch@h-architects.be",
      "onderwerp": "Your receipt from Anthropic, PBC",
      "naar": "ap@unabo.be"},
     {"mailbox": "info@h-architects.be",
      "onderwerp": "elevaitnv.com", "van": "one.com",
      "naar": "admin@elevaitnv.com", "backfill": true}]

Per regel: mailbox, onderwerp (deeltekst, hoofdletterongevoelig), naar;
optioneel van (deeltekst van het afzenderadres), map (standaard INBOX) en
backfill. Zonder POSTBUS_AGENT_REGELS gelden de oude losse variabelen
(POSTBUS_AGENT_MAILBOX/ONDERWERP/NAAR/MAP) als de enige regel, precies zoals
voorheen.
"""
import json
import os
import time
from datetime import datetime, timezone

import config
import imapbron
import verzenden

INTERVAL = int(os.environ.get("POSTBUS_AGENT_INTERVAL", "300"))
PAUZE = int(os.environ.get("POSTBUS_AGENT_PAUZE", "20"))
BACKFILL = os.environ.get("POSTBUS_AGENT_BACKFILL", "").strip().lower() in \
    {"ja", "yes", "waar", "true", "aan"}
STATUSPAD = os.environ.get("POSTBUS_AGENT_STATE",
                           "/state/doorgestuurd.json")


def log(boodschap):
    stempel = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"[doorstuuragent] {stempel} {boodschap}", flush=True)


# ---------------------------------------------------------------- regels

def _regels():
    """De regels uit de omgeving. Elke regel: mailbox, onderwerp, naar,
    map, van, backfill, en een vaste sleutel voor het statusbestand."""
    ruw = os.environ.get("POSTBUS_AGENT_REGELS", "").strip()
    if ruw:
        try:
            lijst = json.loads(ruw)
        except ValueError as e:
            log(f"POSTBUS_AGENT_REGELS is geen geldige JSON: {e}")
            return []
        if not isinstance(lijst, list):
            log("POSTBUS_AGENT_REGELS moet een lijst zijn")
            return []
    else:
        lijst = [{
            "mailbox": os.environ.get("POSTBUS_AGENT_MAILBOX", ""),
            "onderwerp": os.environ.get("POSTBUS_AGENT_ONDERWERP", ""),
            "naar": os.environ.get("POSTBUS_AGENT_NAAR", ""),
            "map": os.environ.get("POSTBUS_AGENT_MAP", "INBOX"),
        }]
    uit = []
    for r in lijst:
        if not isinstance(r, dict):
            continue
        regel = {
            "mailbox": str(r.get("mailbox", "")).strip(),
            "onderwerp": str(r.get("onderwerp", "")).strip(),
            "van": str(r.get("van", "")).strip(),
            "naar": str(r.get("naar", "")).strip(),
            "map": (str(r.get("map", "INBOX")).strip() or "INBOX"),
            "backfill": bool(r.get("backfill", BACKFILL)),
        }
        regel["sleutel"] = "|".join(
            [regel["mailbox"].lower(), regel["map"], regel["onderwerp"].lower(),
             regel["van"].lower(), regel["naar"].lower()])
        uit.append(regel)
    return uit


# ---------------------------------------------------------------- status

def _lees_status():
    try:
        with open(STATUSPAD, "r", encoding="utf-8") as f:
            status = json.load(f)
    except (FileNotFoundError, ValueError):
        return {"regels": {}}
    if "regels" not in status:
        # Oude, platte vorm van voor de meerdere regels: die hoort bij de
        # regel uit de losse omgevingsvariabelen. Zo blijft de geschiedenis
        # van de Anthropic-regel gelden en stuurt hij niets opnieuw.
        oud = {"gestart": status.get("gestart"), "gezien": status.get("gezien", [])}
        status = {"regels": {"__oud__": oud}}
    return status


def _schrijf_status(status):
    tijdelijk = STATUSPAD + ".tmp"
    os.makedirs(os.path.dirname(STATUSPAD) or ".", exist_ok=True)
    with open(tijdelijk, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    os.replace(tijdelijk, STATUSPAD)


def _regelstatus(status, regel, eerste_regel):
    """De status van deze regel; de oude platte status gaat naar de eerste
    regel (dat is de regel die er al was)."""
    per = status.setdefault("regels", {})
    if regel["sleutel"] not in per and eerste_regel and "__oud__" in per:
        per[regel["sleutel"]] = per.pop("__oud__")
    return per.setdefault(regel["sleutel"], {})


# ---------------------------------------------------------------- werk

def _treffers(mailbox, regel):
    """(uid, message_id, onderwerp) van alle berichten die aan de regel voldoen.

    Het zoeken gebeurt op de mailserver via imapbron.lijst; SUBJECT is daar
    hoofdletterongevoelig en op deeltekst. We controleren onderwerp en
    afzender daarna zelf nog eens, want de serverzoekopdracht is ruimer dan we
    willen en we sturen liever te weinig dan te veel door.
    """
    uit = []
    vanaf = 0
    while True:
        blok = imapbron.lijst(mailbox, regel["map"], onderwerp=regel["onderwerp"],
                              van=regel["van"] or None, maximaal=100, vanaf=vanaf)
        for b in blok["berichten"]:
            onderwerp = b.get("onderwerp") or ""
            if regel["onderwerp"].lower() not in onderwerp.lower():
                continue
            if regel["van"] and regel["van"].lower() not in (b.get("van") or "").lower():
                continue
            uit.append((b["uid"], b.get("message_id"), onderwerp))
        if not blok.get("meer"):
            break
        vanaf = blok["volgende_vanaf"]
    return uit


def _ronde(mailbox, regel, eerste_regel):
    status = _lees_status()
    rs = _regelstatus(status, regel, eerste_regel)
    gezien = set(rs.get("gezien", []))
    eerste_keer = "gestart" not in rs
    naam = f"{regel['mailbox']} [{regel['onderwerp']!r}] -> {regel['naar']}"
    try:
        treffers = _treffers(mailbox, regel)
    except Exception as e:
        log(f"kon niet zoeken voor {naam}: {type(e).__name__}: {e}")
        return
    if eerste_keer and not regel["backfill"]:
        for _, mid, _ in treffers:
            if mid:
                gezien.add(mid)
        rs["gestart"] = datetime.now(timezone.utc).isoformat()
        rs["gezien"] = sorted(gezien)
        _schrijf_status(status)
        log(f"eerste start {naam}: {len(gezien)} bestaande berichten "
            "overgeslagen, vanaf nu worden nieuwe doorgestuurd. Zet backfill "
            "op true als de bestaande wel doorgestuurd moeten worden.")
        return
    if eerste_keer and regel["backfill"]:
        log(f"eerste start met backfill {naam}: {len(treffers)} bestaande "
            "berichten worden alsnog doorgestuurd.")
        rs["gestart"] = datetime.now(timezone.utc).isoformat()
    nieuw = [(uid, mid, ond) for uid, mid, ond in reversed(treffers)
             if not mid or mid not in gezien]
    if not nieuw:
        _schrijf_status(status)
        return
    for i, (uid, mid, onderwerp) in enumerate(nieuw):
        try:
            resultaat = verzenden.doorsturen(mailbox, regel["map"], uid, regel["naar"])
        except Exception as e:
            if "plafond" in str(e).lower():
                log("dagplafond bereikt; de resterende berichten volgen een "
                    "volgende dag vanzelf.")
                break
            log(f"doorsturen mislukte voor uid {uid} ({onderwerp[:60]}) "
                f"{naam}: {type(e).__name__}: {e}")
            if i < len(nieuw) - 1:
                time.sleep(PAUZE)
            continue
        if mid:
            gezien.add(mid)
        rs["gezien"] = sorted(gezien)
        _schrijf_status(status)
        log(f"doorgestuurd naar {regel['naar']}: {onderwerp[:70]} "
            f"({resultaat.get('vandaag_verstuurd')}/{resultaat.get('dagplafond')} "
            f"vandaag, kopie in Verzonden: {resultaat.get('kopie_in_verzonden')})")
        if i < len(nieuw) - 1:
            time.sleep(PAUZE)


def _controleer_opzet(regel):
    """De mailbox van deze regel, of None met een logregel die zegt waarom."""
    fouten = []
    for veld in ("mailbox", "onderwerp", "naar"):
        if not regel[veld]:
            fouten.append(f"regel zonder {veld}")
    if fouten:
        for f in fouten:
            log("opzet onvolledig: " + f)
        return None
    # config.zoek filtert op de toegang van een ingelogde gebruiker; de agent
    # hoort niet achter een login te zitten, dus we pakken de mailbox
    # rechtstreeks uit het bestand.
    alle, _ = config.alles()
    mailbox = next((m for m in alle
                    if m["adres"].lower() == regel["mailbox"].lower()), None)
    if not mailbox:
        log(f"opzet: mailbox {regel['mailbox']} staat niet in mailboxen.yaml")
        return None
    if regel["naar"].lower() not in [x.lower() for x in (mailbox.get("doorsturen") or [])]:
        log(f"opzet: {regel['naar']} staat niet in 'doorsturen:' van "
            f"{regel['mailbox']}. Voeg het daar toe, anders weigert het "
            "versturen terecht.")
        return None
    if not mailbox.get("smtp_host"):
        log(f"opzet: {regel['mailbox']} heeft geen smtp_host, doorsturen kan niet.")
        return None
    return mailbox


def main():
    regels = _regels()
    log(f"start. {len(regels)} regel(s), interval={INTERVAL}s")
    for r in regels:
        log(f"  regel: {r['mailbox']} [{r['onderwerp']!r}"
            f"{' van ' + r['van'] if r['van'] else ''}] -> {r['naar']} "
            f"map={r['map']} backfill={r['backfill']}")
    if not verzenden.ACTIEF:
        log("let op: de noodrem POSTBUS_DOORSTUREN staat uit. De agent draait, "
            "maar er gaat niets de deur uit tot die op 'ja' staat.")
    while True:
        if verzenden.ACTIEF:
            for i, regel in enumerate(regels):
                mailbox = _controleer_opzet(regel)
                if mailbox is None:
                    continue
                try:
                    _ronde(mailbox, regel, eerste_regel=(i == 0))
                except Exception as e:
                    log(f"onverwacht in ronde {regel['mailbox']}: "
                        f"{type(e).__name__}: {e}")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
