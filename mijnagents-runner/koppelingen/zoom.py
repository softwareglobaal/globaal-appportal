"""Zoom, alleen lezen: de instellingen van een meeting.

Een Server-to-Server-app van het Zoom-account met leesrechten op meetings
(meeting:read:meeting:admin). De sleutels ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID en
ZOOM_CLIENT_SECRET staan in ~/appportal/.env of, zoals op 28-09-2026, in
~/pipedrive-won-deals/.env. Nooit in de code. Schrijven kan deze app niet: een
instelling in Zoom veranderen blijft een handeling van Mehdi.
"""
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

_BESTANDEN = ("~/appportal/.env", "~/appportal/mijnagents-data/.env", "~/pipedrive-won-deals/.env")
_token = {"waarde": "", "tot": 0.0}
_meetings = {}


def _sleutel(naam):
    if os.environ.get(naam):
        return os.environ[naam].strip()
    for pad in _BESTANDEN:
        try:
            for regel in open(os.path.expanduser(pad)):
                if regel.startswith(naam + "="):
                    return regel.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            continue
    return ""


def beschikbaar():
    return all(_sleutel(n) for n in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"))


def _toegang():
    if _token["waarde"] and time.time() < _token["tot"]:
        return _token["waarde"]
    basic = base64.b64encode(f"{_sleutel('ZOOM_CLIENT_ID')}:{_sleutel('ZOOM_CLIENT_SECRET')}".encode()).decode()
    url = "https://zoom.us/oauth/token?" + urllib.parse.urlencode(
        {"grant_type": "account_credentials", "account_id": _sleutel("ZOOM_ACCOUNT_ID")})
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, method="POST",
                                                                headers={"Authorization": "Basic " + basic}), timeout=30))
    _token.update(waarde=d["access_token"], tot=time.time() + int(d.get("expires_in", 3600)) - 120)
    return _token["waarde"]


def meeting(mid):
    """De meeting met haar instellingen, of None als ze niet te lezen is. Een keer per ronde."""
    if mid in _meetings:
        return _meetings[mid]
    try:
        req = urllib.request.Request(f"https://api.zoom.us/v2/meetings/{mid}",
                                     headers={"Authorization": "Bearer " + _toegang()})
        _meetings[mid] = json.load(urllib.request.urlopen(req, timeout=30))
    except (urllib.error.URLError, KeyError, ValueError, OSError):
        _meetings[mid] = None
    return _meetings[mid]
