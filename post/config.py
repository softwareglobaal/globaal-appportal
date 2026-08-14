"""Postbus: het mailboxenbestand lezen, controleren en de toegang bepalen.

Eén bestand op de VM (standaard /config/mailboxen.yaml, bind-mount van
~/post-config) is de enige plek waar mailadressen, IMAP-gegevens en de
toegangsregels staan. Het staat bewust NIET in git: er staan wachtwoorden in.

Toegang is dicht tenzij ze open staat: een mailbox zonder groepen en zonder
personen is voor niemand zichtbaar. Wie erbij mag wordt bepaald door de
Authentik-login (groepen uit de forward-auth, meegegeven in het OAuth-token).
"""
import os
import threading
import time

import yaml

PAD = os.environ.get("POSTBUS_CONFIG", "/config/mailboxen.yaml")

# Alleen deze sleutels mogen per mailbox voorkomen; een typefout in het
# bestand is anders een stille beperking (of erger, een stille verruiming).
SLEUTELS = {"adres", "naam", "imap_host", "imap_poort", "gebruiker",
            "wachtwoord", "groepen", "personen", "mappen"}
STANDAARD_SLEUTELS = {"imap_host", "imap_poort", "mappen"}

_slot = threading.Lock()
_cache = {"stempel": None, "gelezen_op": 0.0, "mailboxen": [], "fouten": []}
HERLEES_NA = 5.0  # seconden; bestand wijzigen werkt zonder herstart


def _lijst(waarde, veld, fouten, waar):
    if waarde is None:
        return []
    if not isinstance(waarde, list) or not all(
            isinstance(w, str) and w.strip() for w in waarde):
        fouten.append(f"{waar}: {veld} moet een lijst teksten zijn")
        return []
    return [w.strip() for w in waarde]


def _ontleed(ruw):
    """YAML-inhoud naar (mailboxen, fouten). Fouten blokkeren nooit de rest."""
    fouten = []
    if not isinstance(ruw, dict):
        return [], ["Het bestand moet met 'mailboxen:' beginnen (YAML-object)"]

    onbekend = set(ruw) - {"standaard", "mailboxen"}
    if onbekend:
        fouten.append("Onbekende sleutels op het hoogste niveau: "
                      + ", ".join(sorted(onbekend)))

    standaard = ruw.get("standaard") or {}
    if not isinstance(standaard, dict):
        fouten.append("standaard: moet een object zijn")
        standaard = {}
    else:
        vreemd = set(standaard) - STANDAARD_SLEUTELS
        if vreemd:
            fouten.append("standaard: onbekende sleutels "
                          + ", ".join(sorted(vreemd)))
    st_mappen = _lijst(standaard.get("mappen"), "mappen", fouten, "standaard")

    rijen = ruw.get("mailboxen")
    if rijen is None:
        return [], fouten + ["Er staat geen lijst 'mailboxen' in het bestand"]
    if not isinstance(rijen, list):
        return [], fouten + ["mailboxen: moet een lijst zijn"]

    uit, gezien = [], set()
    for i, rij in enumerate(rijen, start=1):
        waar = f"mailbox {i}"
        if not isinstance(rij, dict):
            fouten.append(f"{waar}: moet een object zijn")
            continue
        adres = str(rij.get("adres") or "").strip()
        waar = f"mailbox {i} ({adres})" if adres else waar
        vreemd = set(rij) - SLEUTELS
        if vreemd:
            fouten.append(f"{waar}: onbekende sleutels "
                          + ", ".join(sorted(vreemd)))
        if not adres or "@" not in adres:
            fouten.append(f"{waar}: 'adres' ontbreekt of is geen mailadres")
            continue
        if adres.lower() in gezien:
            fouten.append(f"{waar}: dit adres staat er al in, tweede negeerd")
            continue

        host = str(rij.get("imap_host") or standaard.get("imap_host") or "").strip()
        poort = rij.get("imap_poort", standaard.get("imap_poort", 993))
        gebruiker = str(rij.get("gebruiker") or adres).strip()
        wachtwoord = str(rij.get("wachtwoord") or "")
        try:
            poort = int(poort)
        except (TypeError, ValueError):
            fouten.append(f"{waar}: imap_poort moet een getal zijn")
            continue
        if not host:
            fouten.append(f"{waar}: imap_host ontbreekt (ook geen standaard)")
            continue
        if not wachtwoord or wachtwoord == "CHANGE_ME":
            fouten.append(f"{waar}: wachtwoord is nog niet ingevuld")
            continue

        groepen = _lijst(rij.get("groepen"), "groepen", fouten, waar)
        personen = _lijst(rij.get("personen"), "personen", fouten, waar)
        if not groepen and not personen:
            fouten.append(f"{waar}: geen groepen en geen personen, dus voor "
                          "niemand zichtbaar")
        mappen = _lijst(rij.get("mappen"), "mappen", fouten, waar) or st_mappen

        gezien.add(adres.lower())
        uit.append({
            "adres": adres,
            "naam": str(rij.get("naam") or adres).strip(),
            "imap_host": host,
            "imap_poort": poort,
            "gebruiker": gebruiker,
            "wachtwoord": wachtwoord,
            "groepen": [g.lower() for g in groepen],
            "personen": [p.lower() for p in personen],
            "mappen": mappen,
        })
    return uit, fouten


def _laad():
    """Leest het bestand opnieuw als het gewijzigd is; anders uit de cache."""
    nu = time.time()
    with _slot:
        if _cache["gelezen_op"] and nu - _cache["gelezen_op"] < HERLEES_NA:
            return _cache["mailboxen"], _cache["fouten"]
        try:
            stempel = os.stat(PAD).st_mtime_ns
        except OSError as e:
            _cache.update(stempel=None, gelezen_op=nu, mailboxen=[],
                          fouten=[f"Kan {PAD} niet lezen: {e.strerror}"])
            return _cache["mailboxen"], _cache["fouten"]
        if stempel != _cache["stempel"]:
            try:
                with open(PAD, "r", encoding="utf-8") as f:
                    ruw = yaml.safe_load(f)
                mailboxen, fouten = _ontleed(ruw)
            except yaml.YAMLError as e:
                mailboxen, fouten = [], [f"YAML-fout in {PAD}: {e}"]
            except OSError as e:
                mailboxen, fouten = [], [f"Kan {PAD} niet lezen: {e.strerror}"]
            _cache.update(stempel=stempel, mailboxen=mailboxen, fouten=fouten)
        _cache["gelezen_op"] = nu
        return _cache["mailboxen"], _cache["fouten"]


def alles():
    """(mailboxen, fouten) van het hele bestand; alleen voor de beheerpagina."""
    return _laad()


def voor(wie):
    """De mailboxen die deze gebruiker mag zien.

    wie = {"gebruiker": <naam>, "groepen": [<groep>, ...]}. Groepen komen uit
    Authentik; matchen gebeurt hoofdletterongevoelig.
    """
    mailboxen, _ = _laad()
    naam = str(wie.get("gebruiker") or "").strip().lower()
    groepen = {str(g).strip().lower() for g in (wie.get("groepen") or []) if str(g).strip()}
    uit = []
    for m in mailboxen:
        if (groepen & set(m["groepen"])) or (naam and naam in m["personen"]):
            uit.append(m)
    return uit


def zoek(adres, wie):
    """Eén mailbox op adres, maar alleen als deze gebruiker erbij mag."""
    gezocht = str(adres or "").strip().lower()
    if not gezocht:
        raise ValueError("Geef een mailbox (mailadres) op; zie de tool mailboxen")
    for m in voor(wie):
        if m["adres"].lower() == gezocht:
            return m
    raise ValueError(f"Geen toegang tot '{adres}' of de mailbox bestaat niet. "
                     "De tool mailboxen toont wat je wel mag lezen.")


def map_toegestaan(mailbox, naam):
    """Mapnaam controleren tegen de allowlist (leeg = alle mappen mogen)."""
    schoon = str(naam or "INBOX").strip()
    if not schoon or "\r" in schoon or "\n" in schoon or '"' in schoon:
        raise ValueError(f"Ongeldige mapnaam: {naam!r}")
    toegestaan = mailbox["mappen"]
    if toegestaan and schoon.lower() not in [t.lower() for t in toegestaan]:
        raise ValueError(f"Map '{schoon}' staat niet open voor deze mailbox. "
                         "Toegestaan: " + ", ".join(toegestaan))
    return schoon
