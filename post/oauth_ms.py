"""Postbus: Microsoft-OAuth2 voor IMAP (XOAUTH2), voor mailboxen met auth: microsoft.

Waarom dit bestaat: Microsoft heeft basic authentication op IMAP uitgezet,
ook voor app-wachtwoorden ("Basic authentication is disabled", gemeten
30-09-2026 op mehdichegini@hotmail.com). Zo'n mailbox logt daarom niet in met
een wachtwoord maar met een access token.

Hoe het loopt:

1. Eenmalig koppelen met `python oauth_koppel.py <adres>` in de container
   (device-code-login: de eigenaar logt in op microsoft.com/devicelogin). Dat
   levert een refresh token op, en dat komt in POSTBUS_OAUTH_MAP/<adres>.json.
   Die koppeling vraagt toestemming voor lezen (IMAP) en versturen (SMTP);
   in het tokenbestand staat welke van de twee de eigenaar gaf.
2. Bij elke IMAP- of SMTP-sessie ruilt deze module het refresh token in voor een access
   token (een uur geldig, hier gecachet tot kort voor het verloopt).
   Microsoft geeft daarbij vaak een NIEUW refresh token terug; dat schrijven we
   meteen weg, anders verloopt de koppeling na verloop van tijd.

Het tokenbestand is het geheim: het staat in een eigen volume, nooit in git en
nooit in mailboxen.yaml (dat is read-only aangekoppeld en kan geen roterend
token bijhouden). De client-ID is geen geheim: het is een public client.
"""
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

MAP = os.environ.get("POSTBUS_OAUTH_MAP", "/oauth")
# 'consumers' = persoonlijke Microsoft-accounts (hotmail, outlook.com, live).
TENANT = os.environ.get("POSTBUS_OAUTH_TENANT", "consumers")
BASIS = f"https://login.microsoftonline.com/{TENANT}/oauth2/v2.0"
TOKEN_URL = BASIS + "/token"
DEVICE_URL = BASIS + "/devicecode"
# Een token voor lezen (IMAP) en versturen (SMTP) tegelijk: beide horen bij
# dezelfde resource (outlook.office.com), dus een access token dekt ze allebei.
SCOPE = ("https://outlook.office.com/IMAP.AccessAsUser.All "
         "https://outlook.office.com/SMTP.Send offline_access")
# Koppelingen van voor 30-09-2026 kregen alleen toestemming voor IMAP. Hun
# tokenbestand heeft geen 'scope'; die vernieuwen we met deze smallere scope,
# anders weigert Microsoft (toestemming voor SMTP is nooit gegeven).
SCOPE_ALLEEN_IMAP = ("https://outlook.office.com/IMAP.AccessAsUser.All "
                     "offline_access")
TIMEOUT = 30
MARGE_S = 300  # een access token vijf minuten voor het verloopt al vervangen

_slot = threading.Lock()
_cache = {}  # adres -> (access_token, verloopt_op)


def pad(adres):
    return os.path.join(MAP, str(adres).strip().lower() + ".json")


def post(url, velden):
    """POST als formulier; geeft altijd JSON terug, ook bij een HTTP-fout."""
    data = urllib.parse.urlencode(velden).encode()
    verzoek = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(verzoek, timeout=TIMEOUT) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return json.load(e)
        except Exception:
            return {"error": f"http_{e.code}", "error_description": str(e)}
    except Exception as e:
        return {"error": type(e).__name__, "error_description": str(e)}


def bewaar(adres, gegevens):
    """Schrijft het tokenbestand atomair en alleen leesbaar voor de eigenaar."""
    os.makedirs(MAP, exist_ok=True)
    doel = pad(adres)
    tijdelijk = doel + ".tmp"
    fd = os.open(tijdelijk, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(gegevens, f)
    os.replace(tijdelijk, doel)


def gekoppeld(adres):
    return os.path.exists(pad(adres))


def toegangstoken(mailbox, smtp=False):
    """Een geldig access token voor deze mailbox; vernieuwt als het moet.

    smtp=True: het token moet ook mogen versturen. Een koppeling zonder
    toestemming voor SMTP.Send geeft dan een duidelijke melding in plaats van
    een onbegrijpelijke weigering van de mailserver.
    """
    adres = mailbox["adres"].strip().lower()
    client_id = mailbox.get("oauth_client_id")
    if not client_id:
        raise ValueError(f"{adres} staat op auth: microsoft maar heeft geen "
                         "oauth_client_id in mailboxen.yaml.")
    with _slot:
        gecacht = _cache.get(adres)
        if gecacht and gecacht[1] - MARGE_S > time.time():
            return gecacht[0]
        try:
            with open(pad(adres), encoding="utf-8") as f:
                opgeslagen = json.load(f)
        except FileNotFoundError:
            raise ValueError(
                f"{adres} is nog niet gekoppeld. De beheerder draait eenmalig "
                f"in de container: python oauth_koppel.py {adres}")
        scope = opgeslagen.get("scope") or SCOPE_ALLEEN_IMAP
        if smtp and "SMTP.Send" not in scope:
            raise ValueError(
                f"De koppeling van {adres} geeft alleen toestemming om te "
                "lezen, niet om te versturen. De beheerder koppelt opnieuw "
                f"met: python oauth_koppel.py {adres}")
        antwoord = post(TOKEN_URL, {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": opgeslagen["refresh_token"],
            "scope": scope,
        })
        if "access_token" not in antwoord:
            raise ValueError(
                f"Het token van {adres} vernieuwen lukt niet "
                f"({antwoord.get('error')}: "
                f"{str(antwoord.get('error_description', ''))[:200]}). "
                "Meestal betekent dit dat de koppeling is ingetrokken of "
                "verlopen; koppel opnieuw met oauth_koppel.py.")
        if antwoord.get("refresh_token") and \
                antwoord["refresh_token"] != opgeslagen["refresh_token"]:
            opgeslagen["refresh_token"] = antwoord["refresh_token"]
            opgeslagen["vernieuwd_op"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            bewaar(adres, opgeslagen)
        verloopt = time.time() + int(antwoord.get("expires_in", 3600))
        _cache[adres] = (antwoord["access_token"], verloopt)
        return antwoord["access_token"]


def xoauth2(gebruiker, token):
    """De SASL-string voor XOAUTH2 (IMAP AUTHENTICATE en SMTP AUTH)."""
    return f"user={gebruiker}\x01auth=Bearer {token}\x01\x01".encode()
