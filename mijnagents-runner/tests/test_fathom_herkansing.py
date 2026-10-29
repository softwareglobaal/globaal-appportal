"""Grendel op koppelingen/fathom._haal (29-10-2026: de middagketen faalde op IncompleteRead midden in een pagina).

- F01: een afgebroken antwoord krijgt een herkansing en de tweede poging geeft het antwoord;
- F02: blijft het afbreken, dan komt na POGINGEN pogingen de echte fout door;
- F03: een andere HTTP-fout dan 429 (bv. 401) krijgt geen herkansing.

Geen netwerk: urlopen en time.sleep zijn vervangen.
"""
import http.client
import io
import json
import os
import sys
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "koppelingen"))
os.environ["FATHOM_POGINGEN"] = "3"
import fathom as F  # noqa: E402

F.time.sleep = lambda s: None
fout = 0


def check(naam, voorwaarde, extra=""):
    global fout
    print(("  ok   " if voorwaarde else "  FOUT ") + naam, "" if voorwaarde else extra)
    fout += 0 if voorwaarde else 1


class Antwoord(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def nep(gedrag):
    pogingen = []

    def urlopen(req, timeout=None):
        pogingen.append(1)
        stap = gedrag[min(len(pogingen), len(gedrag)) - 1]
        if isinstance(stap, Exception):
            raise stap
        return Antwoord(json.dumps(stap).encode())
    return urlopen, pogingen


def f01():
    F.urllib.request.urlopen, p = nep([http.client.IncompleteRead(b"x", 10), {"items": [1]}])
    check("F01 herkansing na een afgebroken antwoord", F._haal("s", "/meetings") == {"items": [1]} and len(p) == 2, p)


def f02():
    F.urllib.request.urlopen, p = nep([http.client.IncompleteRead(b"x", 10)])
    try:
        F._haal("s", "/meetings")
        check("F02 echte fout na alle pogingen", False)
    except http.client.IncompleteRead:
        check("F02 echte fout na alle pogingen", len(p) == 3, p)


def f03():
    F.urllib.request.urlopen, p = nep([urllib.error.HTTPError("u", 401, "nee", {}, None)])
    try:
        F._haal("s", "/meetings")
        check("F03 401 zonder herkansing", False)
    except urllib.error.HTTPError:
        check("F03 401 zonder herkansing", len(p) == 1, p)


if __name__ == "__main__":
    f01()
    f02()
    f03()
    print(f"{fout} fout")
    sys.exit(1 if fout else 0)
