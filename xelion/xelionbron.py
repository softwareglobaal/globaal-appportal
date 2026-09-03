"""Xelion-koppeling voor de MCP-server: lezen en wijzigen.

De opzet volgt de bestaande client van de contactsync (`contactsync/app/
xelion_client.py`), die al sinds juli 2026 contacten naar Xelion schrijft. Wat
hier anders is: geen achtergrondsync maar losse aanroepen namens een ingelogde
persoon, en elke wijziging gaat eerst langs `config.mag()`.

Alle schrijfoperaties op Xelion zijn ONMIDDELLIJK en definitief. Xelion kent
geen prullenbak: een verwijderd contact is weg. Daarom staat verwijderen in de
rechten los van bijwerken, en zit er bovendien een noodrem op in de omgeving.
"""
import os
import threading
import time
from datetime import datetime, timedelta

import requests

MAX_POGINGEN = 3
HERHAALBAAR = (429, 500, 502, 503, 504)
# Xelion stelt commonName samen uit givenName + familyName. De contactsync
# schrijft de volledige weergavenaam in givenName en laat familyName leeg;
# dat is empirisch vastgesteld op de live API (zie xelion_payload.py daar).
NAAM_VELD = "givenName"
LEEG_VELD = "familyName"


class XelionFout(Exception):
    def __init__(self, boodschap, status=None):
        super().__init__(boodschap)
        self.status = status


def _instellingen():
    uit = {
        "base_url": os.environ.get("XELION_BASE_URL", "").strip().rstrip("/"),
        "username": os.environ.get("XELION_USERNAME", "").strip(),
        "password": os.environ.get("XELION_PASSWORD", "").strip(),
        "userspace": os.environ.get("XELION_USERSPACE", "").strip(),
        "appkey": os.environ.get("XELION_APP_KEY", "").strip(),
    }
    ontbreekt = [k for k in ("base_url", "username", "password", "userspace")
                 if not uit[k]]
    if ontbreekt:
        raise XelionFout("Xelion niet ingesteld, ontbreekt: " + ", ".join(ontbreekt))
    return uit


class Bron:
    """Eén gedeelde sessie naar Xelion; de tokens leven kort en vernieuwen zelf."""

    def __init__(self):
        self._sessie = requests.Session()
        self._token = None
        self._vernieuw_token = None
        self._geldig_tot = None
        self._slot = threading.Lock()

    # ---- sessie ------------------------------------------------------
    def _inloggen(self):
        inst = _instellingen()
        body = {"userName": inst["username"], "password": inst["password"],
                "userSpace": inst["userspace"]}
        if inst["appkey"]:
            body["appKey"] = inst["appkey"]
        r = self._sessie.post(inst["base_url"] + "/me/login", json=body, timeout=30)
        if r.status_code != 200:
            raise XelionFout(
                "Xelion-login mislukt (%s): %s" % (r.status_code, r.text[:200]),
                status=r.status_code)
        d = r.json()
        self._token = d.get("authentication")
        self._vernieuw_token = d.get("renewalToken")
        self._geldig_tot = _tot(d.get("validUntil"))

    def _zorg_voor_sessie(self):
        with self._slot:
            if self._token is None:
                self._inloggen()
                return
            if self._geldig_tot and datetime.now() > self._geldig_tot - timedelta(minutes=5):
                self._inloggen()

    def _koppen(self):
        return {"Authorization": "xelion " + str(self._token)}

    # ---- verzoek -----------------------------------------------------
    def verzoek(self, methode, pad, body=None, params=None):
        self._zorg_voor_sessie()
        url = _instellingen()["base_url"] + pad
        poging = 0
        while True:
            poging += 1
            try:
                r = self._sessie.request(methode, url, json=body, params=params,
                                         headers=self._koppen(), timeout=60)
            except requests.RequestException as e:
                if poging > MAX_POGINGEN:
                    raise XelionFout("netwerkfout na %s pogingen: %s" % (poging, e))
                time.sleep(min(20.0, 0.5 * (2 ** poging)))
                continue
            if r.status_code == 401 and poging <= MAX_POGINGEN:
                with self._slot:
                    self._token = None
                self._zorg_voor_sessie()
                continue
            if r.status_code in HERHAALBAAR and poging <= MAX_POGINGEN:
                time.sleep(min(20.0, 0.5 * (2 ** poging)))
                continue
            if r.status_code >= 400:
                raise XelionFout(
                    "%s %s mislukt (%s): %s" % (methode, pad, r.status_code, r.text[:200]),
                    status=r.status_code)
            if r.status_code == 204 or not r.content:
                return None
            return r.json()

    # ---- lezen -------------------------------------------------------
    def contact(self, oid):
        return _uitpakken(self.verzoek("GET", "/addressables/%s" % oid))

    def zoek_contacten(self, naam, limiet=10):
        d = self.verzoek("GET", "/addressables",
                         params={"name": naam, "limit": max(1, min(int(limiet), 100))})
        if isinstance(d, dict):
            return [_uitpakken(x) for x in (d.get("data") or [])]
        return d or []

    def labels(self, oid):
        d = self.verzoek("GET", "/addressables/%s/telecom_address_labels" % oid)
        if isinstance(d, dict):
            return d.get("data") or d.get("labels") or []
        return d or []

    def lijsten(self, naam=None):
        d = self.verzoek("GET", "/lists", params={"name": naam} if naam else None)
        items = d.get("data") if isinstance(d, dict) else d
        return [_uitpakken(x) for x in (items or [])]

    def gesprekken(self, limiet=25):
        d = self.verzoek("GET", "/communications",
                         params={"limit": max(1, min(int(limiet), 100))})
        items = d.get("data") if isinstance(d, dict) else d
        return [_uitpakken(x) for x in (items or [])]

    # ---- wijzigen ----------------------------------------------------
    # Elke aanroep hieronder verandert de telefooncentrale meteen.
    def contact_aanmaken(self, weergavenaam, telefoons=None, emails=None,
                         roepnaam=None):
        body = {NAAM_VELD: weergavenaam, LEEG_VELD: ""}
        if roepnaam:
            body["additionalNames"] = roepnaam
        adressen = _telecom(telefoons, emails)
        if adressen:
            body["telecomAddresses"] = adressen
        d = self.verzoek("POST", "/addressables", body=body)
        oid = str(_uitpakken(d).get("oid") or "")
        if not oid:
            raise XelionFout("geen oid terug van Xelion bij aanmaken")
        return oid

    def contact_bijwerken(self, oid, operaties):
        if not operaties:
            raise ValueError("geen operaties opgegeven")
        self.verzoek("PATCH", "/addressables/%s" % oid,
                     body={"operations": operaties})

    def contact_verwijderen(self, oid):
        self.verzoek("DELETE", "/addressables/%s" % oid)

    def lijst_aanmaken(self, naam):
        d = self.verzoek("POST", "/lists", body={"name": naam})
        return str(_uitpakken(d).get("oid") or "")

    def lijst_toevoegen(self, lijst_oid, contact_oid):
        self.verzoek("PATCH", "/lists/%s" % lijst_oid, body={"operations": [
            {"op": "add", "path": "/elements/v1", "value": contact_oid}]})

    def lijst_verwijderen_uit(self, lijst_oid, contact_oid):
        self.verzoek("PATCH", "/lists/%s" % lijst_oid, body={"operations": [
            {"op": "remove", "path": "/elements/%s" % contact_oid}]})


def _telecom(telefoons, emails):
    """Bouwt de telecomAddresses zoals de contactsync ze schrijft."""
    uit, volgorde = [], 0
    for nummer in (telefoons or []):
        if isinstance(nummer, dict):
            waarde, label = nummer.get("nummer", ""), nummer.get("label", "werk")
        else:
            waarde, label = str(nummer), "werk"
        if not waarde:
            continue
        uit.append({"type": "Telephone", "address": waarde, "label": label,
                    "order": volgorde})
        volgorde += 1
    for adres in (emails or []):
        if not adres:
            continue
        uit.append({"type": "Email", "address": str(adres), "label": "werk",
                    "order": volgorde})
        volgorde += 1
    return uit


def _uitpakken(d):
    """Xelion verpakt een object als {"object": {...}} of {"data": {...}}."""
    if not isinstance(d, dict):
        return {}
    if isinstance(d.get("object"), dict):
        return d["object"]
    binnen = d.get("data", d)
    if isinstance(binnen, dict):
        return binnen.get("object", binnen.get("attributes", binnen))
    return {}


def _tot(waarde):
    if not waarde:
        return None
    for vorm in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(waarde)[:19], vorm)
        except ValueError:
            continue
    return None


BRON = Bron()
