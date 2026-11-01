"""Grendels op de wachten van de computer (T-0120, groep computer-locatie): De YouTube-wacht, De Websitewacht en De
Wispr-wacht, die op de laptop draaien (mac/youtube_wacht.py, mac/browser_wacht.py, mac/wispr_wacht.py).

- C01 (YT-2): weigert macOS de browsergeschiedenis, dan noemt de melding "geweigerd" met de browser en staat de ronde
  als fout in het werkverslag; een kapot bestand is "onleesbaar"; zonder enig bestand blijft het "niet gevonden".

Verzonnen databanken in een tijdelijke map; geen netwerk, geen bord, geen echte geschiedenis.
Draaien: python3 mijnagents-runner/tests/test_computer_wachten.py
"""
import importlib.util
import os
import sqlite3
import sys
import tempfile

HIER = os.path.dirname(os.path.abspath(__file__))
MAC = os.path.join(os.path.dirname(HIER), "mac")
fout = 0


def check(naam, ok, extra=""):
    global fout
    print(("  ok   " if ok else "  FOUT ") + naam, "" if ok else extra)
    fout += 0 if ok else 1


def laad(naam):
    spec = importlib.util.spec_from_file_location(naam, os.path.join(MAC, f"{naam}.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class NepBord:
    """Vangt elke oproep naar het bord op: (pad, payload)."""
    def __init__(self):
        self.oproepen = []

    def __call__(self, pad, payload):
        self.oproepen.append((pad, payload))
        return {"nieuw": 1, "bijgewerkt": 0}

    def naar(self, pad):
        return [p for x, p in self.oproepen if x == pad]


def bestand(thuis, deel):
    pad = os.path.join(thuis, deel)
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    return pad


def geweigerd_bestand(m, thuis, deel):
    """Een geschiedenis die macOS niet laat lezen: onder launchd zonder toestemming een PermissionError. Als root helpt
    chmod niet; dan geeft de lezer zelf de weigering."""
    pad = bestand(thuis, deel)
    open(pad, "wb").close()
    os.chmod(pad, 0)
    if os.geteuid() == 0:
        echt = m.lees_bestand

        def lees(p, q, s):
            if p == pad:
                raise PermissionError(1, "Operation not permitted")
            return echt(p, q, s)
        m.lees_bestand = lees


def ronde(m, thuis, dag="2026-10-30"):
    m.THUIS, m.DAG, m.DROOG = thuis, dag, False
    nep = NepBord()
    m.bord = nep
    return m.main(), nep


# C01 (YT-2): 01-11-2026 weigerde macOS Chrome en Firefox onder launchd; de melding zei "niet gevonden" en het
# werkverslag bleef leeg ("geen ronde" terwijl er 8 rondes waren).
Y = laad("youtube_wacht")
thuis = tempfile.mkdtemp()
geweigerd_bestand(Y, thuis, "Library/Application Support/Google/Chrome/Default/History")
os.makedirs(bestand(thuis, "Library/Application Support/Firefox/Profiles/proef.default/places.sqlite"))
rc, nep = ronde(Y, thuis)
st = nep.naar("/agent-status")[-1]
check("C01 YouTube: ronde mislukt", rc == 1 and st["status"] == "fout", (rc, st))
check("C01 YouTube: melding noemt geweigerd en onleesbaar",
      st["nood"] and "geweigerd: Chrome" in st["nood"][0]["tekst"] and "onleesbaar: Firefox" in st["nood"][0]["tekst"]
      and "niet gevonden" not in st["nood"][0]["tekst"], st)
log = [r for p in nep.naar("/api/logboek") for r in p["regels"]]
check("C01 YouTube: fout in het werkverslag", any(r["stap"] == "fout" and "geweigerd: Chrome" in r["tekst"] for r in log), log)
check("C01 YouTube: niets klaargezet", not nep.naar("/api/klaarzet"), nep.oproepen)
rc, nep = ronde(laad("youtube_wacht"), tempfile.mkdtemp())
st = nep.naar("/agent-status")[-1]
check("C01 YouTube: zonder bestand niet gevonden", rc == 1 and st["nood"][0]["tekst"] == "Geen browsergeschiedenis gevonden op deze Mac"
      and any(r["stap"] == "fout" for p in nep.naar("/api/logboek") for r in p["regels"]), nep.oproepen)

print("wachten van de computer:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
