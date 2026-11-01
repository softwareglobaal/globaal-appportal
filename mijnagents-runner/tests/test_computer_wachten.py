"""Grendels op de wachten van de computer (T-0120, groep computer-locatie): De YouTube-wacht, De Websitewacht en De
Wispr-wacht, die op de laptop draaien (mac/youtube_wacht.py, mac/browser_wacht.py, mac/wispr_wacht.py).

- C01 (YT-2): weigert macOS de browsergeschiedenis, dan noemt de melding "geweigerd" met de browser en staat de ronde
  als fout in het werkverslag; een kapot bestand is "onleesbaar"; zonder enig bestand blijft het "niet gevonden";
- C02 (WEB-2): leest De Websitewacht geen enkele browser, dan zet ze niets klaar (onbekend is nooit 0 bezoeken): alleen
  een foute hartslag en een foutregel in het werkverslag;
- C03 (WEB-3): Safari telt alleen de bezoeken van deze Mac (origin 0), niet die van een ander toestel via iCloud
  (origin 1, sinds 18-10-2026 elke dag), bij de websites en bij YouTube; een oudere Safari zonder kolom origin blijft
  leesbaar en telt mee (Codex-toets 1), ook naast een lege Chrome;
- C04 (WISPR-2): de inhaalweg van De Wispr-wacht (--dag voor een vroegere dag): per_dag is precies het venster tot die
  dag, ook een dag zonder dictaat (0, de wacht keek), niets erna; de titel is de telling van die dag; het rapport in
  Dropbox blijft staan (het toont de stand van vandaag); een gewone ronde van vandaag schrijft het wel. De Licentiewacht
  neemt daarna nog steeds het item van de nieuwste gebruiksdag, ook als een inhaalronde een oude dag later bijwerkte.

Verzonnen databanken in een tijdelijke map; geen netwerk, geen bord, geen echte geschiedenis.
Draaien: python3 mijnagents-runner/tests/test_computer_wachten.py
"""
import importlib.util
import json
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from zoneinfo import ZoneInfo

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

# C02 (WEB-2): zonder gelezen browser zette de Websitewacht 14 dagen met 0 bezoeken klaar; De Dagbundelaar nam die over.
for naam, thuis in (("lege map", tempfile.mkdtemp()), ("geweigerd", tempfile.mkdtemp())):
    B = laad("browser_wacht")
    if naam == "geweigerd":
        geweigerd_bestand(B, thuis, "Library/Application Support/Google/Chrome/Default/History")
    rc, nep = ronde(B, thuis)
    st = nep.naar("/agent-status")[-1]
    log = [r for p in nep.naar("/api/logboek") for r in p["regels"]]
    check(f"C02 websites ({naam}): geen klaarzet", not nep.naar("/api/klaarzet"), nep.naar("/api/klaarzet"))
    check(f"C02 websites ({naam}): hartslag fout met de reden", rc == 1 and st["status"] == "fout"
          and any(("geweigerd: Chrome" if naam == "geweigerd" else "Geen browsergeschiedenis gevonden") in n["tekst"] for n in st["nood"]), st)
    check(f"C02 websites ({naam}): fout in het werkverslag", [r["stap"] for r in log] == ["fout"], log)

# C03 (WEB-3): een verzonnen Safari-geschiedenis met een bezoek op deze Mac en een van de gsm (iCloud).
SAFARI_EPOCH = 978307200
middag = datetime(2026, 10, 30, 12, 0, tzinfo=ZoneInfo("Europe/Brussels")).timestamp()
thuis = tempfile.mkdtemp()
pad = bestand(thuis, "Library/Safari/History.db")
c = sqlite3.connect(pad)
c.execute("CREATE TABLE history_items (id INTEGER PRIMARY KEY, url TEXT)")
c.execute("CREATE TABLE history_visits (id INTEGER PRIMARY KEY, history_item INTEGER, visit_time REAL, title TEXT, "
          "origin INTEGER)")
for i, (adres, oorsprong) in enumerate((("https://proef-werk.test/a", 0), ("https://proef-gsm.test/b", 1),
                                         ("https://www.youtube.com/watch?v=werkvideo1", 0),
                                         ("https://www.youtube.com/watch?v=gsmvideo12", 1)), 1):
    c.execute("INSERT INTO history_items VALUES (?, ?)", (i, adres))
    c.execute("INSERT INTO history_visits VALUES (?, ?, ?, ?, ?)", (i, i, middag - SAFARI_EPOCH + i, f"Proef {i}", oorsprong))
c.commit()
c.close()
B, Y = laad("browser_wacht"), laad("youtube_wacht")
q = next(x for b, _, x in B.BRONNEN if b == "Safari")
sites = sorted({s for _, s in B.lees_bestand(pad, q, 0)})
check("C03 websites: alleen Safari van deze Mac", sites == ["proef-werk.test", "youtube.com"], sites)
q = next(x for b, _, x in Y.BRONNEN if b == "Safari")
videos = [v for _, v, _, _ in Y.lees_bestand(pad, q, 0)]
check("C03 YouTube: alleen Safari van deze Mac", videos == ["werkvideo1"], videos)
# Codex-toets 1: een Safari zonder kolom origin naast een lege Chrome gaf 0 bezoeken met "Safari onleesbaar".
thuis = tempfile.mkdtemp()
c = sqlite3.connect(bestand(thuis, "Library/Safari/History.db"))
c.execute("CREATE TABLE history_items (id INTEGER PRIMARY KEY, url TEXT)")
c.execute("CREATE TABLE history_visits (id INTEGER PRIMARY KEY, history_item INTEGER, visit_time REAL, title TEXT)")
c.execute("INSERT INTO history_items VALUES (1, 'https://www.youtube.com/watch?v=oudevideo1')")
c.execute("INSERT INTO history_visits VALUES (1, 1, ?, 'Proef oud')", (middag - SAFARI_EPOCH,))
c.commit()
c.close()
c = sqlite3.connect(bestand(thuis, "Library/Application Support/Google/Chrome/Default/History"))
c.execute("CREATE TABLE urls (id INTEGER PRIMARY KEY, url TEXT, title TEXT)")
c.execute("CREATE TABLE visits (id INTEGER PRIMARY KEY, url INTEGER, visit_time INTEGER, visit_duration INTEGER)")
c.commit()
c.close()
B = laad("browser_wacht")
B.DAGEN = 3
rc, nep = ronde(B, thuis)
inh = nep.naar("/api/klaarzet")[-1]["items"][0]["inhoud"] if nep.naar("/api/klaarzet") else {}
check("C03 websites: Safari zonder origin telt mee naast een lege Chrome", rc == 0 and inh.get("onleesbaar") == {}
      and inh["per_dag"]["2026-10-30"]["per_browser"] == {"Safari": 1}, (rc, inh))
Y = laad("youtube_wacht")
Y.DAGEN = 3
rc, nep = ronde(Y, thuis)
inh = nep.naar("/api/klaarzet")[-1]["items"][0]["inhoud"] if nep.naar("/api/klaarzet") else {}
check("C03 YouTube: Safari zonder origin telt mee", rc == 0 and inh.get("onleesbaar") == {}
      and inh["per_dag"]["2026-10-30"]["keer"] == 1, (rc, inh))

# C04 (WISPR-2): een verzonnen flow.sqlite; de middag in UTC is in elke tijdzone van Europa dezelfde dag.
map_ = tempfile.mkdtemp()
db = os.path.join(map_, "flow.sqlite")
c = sqlite3.connect(db)
c.execute("CREATE TABLE History (timestamp TEXT, numWords INTEGER, duration REAL, app TEXT)")
for d, n in (("2026-10-27", 1), ("2026-10-28", 2), ("2026-10-30", 1), ("2026-10-31", 3)):
    for i in range(n):
        c.execute("INSERT INTO History VALUES (?, ?, ?, ?)", (f"{d} 12:0{i}:00.000 +00:00", 100, 30.0, "com.apple.Notes"))
c.commit()
c.close()
rapport = os.path.join(map_, "rapport")
W = laad("wispr_wacht")
W.DB, W.RAPPORT, W.TOKEN, W.GEBRUIKER, W.DAG, W.DAGEN = db, rapport, "proef", "Proef", "2026-10-30", 3
W.bord = nep = NepBord()
W.main()
item = nep.naar("/api/klaarzet")[-1]["items"][0]
pd = item["inhoud"]["per_dag"]
check("C04 Wispr: per_dag is het venster tot de dag", sorted(pd) == ["2026-10-28", "2026-10-29", "2026-10-30"], sorted(pd))
check("C04 Wispr: dag zonder dictaat is 0, niet onbekend", pd.get("2026-10-29", {}).get("dictaten") == 0, pd)
check("C04 Wispr: titel is de telling van die dag", item["uniek"] == "wispr:Proef:2026-10-30"
      and "2026-10-30: 1 dictaten, 100 woorden" in item["titel"], item["titel"])
check("C04 Wispr: week telt niets na de dag", item["inhoud"]["week_dictaten"] == 3, item["inhoud"]["week_dictaten"])
log = [r for p in nep.naar("/api/logboek") for r in p["regels"]]
check("C04 Wispr: inhaalronde laat het rapport staan", not os.path.exists(rapport)
      and any(r["stap"] == "schrijf" and "inhaalronde" in r["tekst"] for r in log), log)
W.DAG = datetime.now().date().isoformat()
W.main()
check("C04 Wispr: ronde van vandaag schrijft het rapport", os.path.exists(os.path.join(rapport, "Proef.md"))
      and os.path.exists(os.path.join(rapport, "Proef.json")))

# Codex-toets 1: de Licentiewacht nam het laatst bijgewerkte item (order by ts); na een inhaalronde was dat 20-10.
# De Licentiewacht draait op de VM (Python 3.12); onder de Python 3.9 van de laptop slaat deze proef over.
if sys.version_info >= (3, 12):
    sys.path.insert(0, os.path.dirname(HIER))
    import licentiewacht as LW  # noqa: E402
    LW.DB = os.path.join(map_, "bord.db")
    c = sqlite3.connect(LW.DB)
    c.execute("CREATE TABLE klaarzet (van TEXT, sleutel TEXT, soort TEXT, inhoud TEXT, ts TEXT)")
    for d, ts in (("2026-11-01", "2026-11-01T20:30:00+00:00"), ("2026-10-20", "2026-11-02T09:00:00+00:00")):
        c.execute("INSERT INTO klaarzet VALUES ('wispr-wacht', 'Proef', 'gebruik', ?, ?)",
                  (json.dumps({"dienst": "Wispr Flow", "gebruiker": "Proef", "dag": d, "week_woorden": len(d)}), ts))
    c.commit()
    c.close()
    g = LW.gebruik_uit_bord()
    check("C04 Licentiewacht: nieuwste gebruiksdag, niet de laatste inhaal", g[("Wispr Flow", "Proef")]["dag"] == "2026-11-01",
          g)
else:
    print("  --   C04 Licentiewacht: overgeslagen onder Python", sys.version.split()[0])

print("wachten van de computer:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
