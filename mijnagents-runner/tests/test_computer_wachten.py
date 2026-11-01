"""Grendels op de wachten van de computer (T-0120, groep computer-locatie): De YouTube-wacht, De Websitewacht en De
Wispr-wacht, die op de laptop draaien (mac/youtube_wacht.py, mac/browser_wacht.py, mac/wispr_wacht.py).

- C01 (YT-2): weigert macOS de browsergeschiedenis, dan noemt de melding "geweigerd" met de browser en staat de ronde
  als fout in het werkverslag; een kapot bestand is "onleesbaar"; zonder enig bestand blijft het "niet gevonden";
- C02 (WEB-2): leest De Websitewacht geen enkele browser, dan zet ze niets klaar (onbekend is nooit 0 bezoeken): alleen
  een foute hartslag en een foutregel in het werkverslag;
- C03 (WEB-3): Safari telt alleen de bezoeken van deze Mac (origin 0), niet die van een ander toestel via iCloud
  (origin 1, sinds 18-10-2026 elke dag), bij de websites en bij YouTube; een oudere Safari zonder kolom origin blijft
  leesbaar en telt mee (Codex-toets 1), ook naast een lege Chrome. Sinds YT-1 en WEB-1 (groep telefoon) leest alleen
  de helper MacGesprekkenKopie de browsers: de filter op origin staat in zijn Safari-vraag en wordt getest in
  tests/test_mac_gesprekken.py (test_web3_safari_alleen_de_bezoeken_van_deze_mac); hier de wacht met de kopie;
- C04 (WISPR-2): de inhaalweg van De Wispr-wacht (--dag voor een vroegere dag): per_dag is precies het venster tot die
  dag, ook een dag zonder dictaat (0, de wacht keek), niets erna; de titel is de telling van die dag; het rapport in
  Dropbox blijft staan (het toont de stand van vandaag); een gewone ronde van vandaag schrijft het wel. De Licentiewacht
  en het teamrapport van de Wispr-teamwacht nemen daarna nog steeds het item van de nieuwste gebruiksdag, ook als een
  inhaalronde een oude dag later bijwerkte.

Verzonnen databanken in een tijdelijke map; geen netwerk, geen bord, geen echte geschiedenis. De browserwachten krijgen
een verzonnen kopie van de helper (main(vragen)): nooit launchctl, nooit de echte helper.
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


def kopie(bronnen=(), bezoeken=()):
    """Een verzonnen kopie van de helper (set browser, zoals mac_gesprekken.browser_kopie ze leest): bronnen
    [(browser, uitkomst)] per databank, bezoeken [(browser, tijd, site, video, titel, duur)]."""
    def vragen(_kanaal):
        pad = os.path.join(tempfile.mkdtemp(), "kopie.sqlite")
        c = sqlite3.connect(pad)
        c.executescript("CREATE TABLE BEZOEK (browser, tijd, site, video, titel, duur); CREATE TABLE BRON (browser, uitkomst);"
                        "CREATE TABLE META (sleutel, waarde);")
        c.executemany("INSERT INTO BEZOEK VALUES (?, ?, ?, ?, ?, ?)", bezoeken)
        c.executemany("INSERT INTO BRON VALUES (?, ?)", bronnen)
        c.commit()
        c.close()
        return pad, datetime.now()
    return vragen


def ronde(m, vragen, dag="2026-10-30"):
    m.DAG, m.DROOG = dag, False
    nep = NepBord()
    m.bord = nep
    return m.main(vragen), nep


# C01 (YT-2): 01-11-2026 weigerde macOS Chrome en Firefox onder launchd; de melding zei "niet gevonden" en het
# werkverslag bleef leeg ("geen ronde" terwijl er 8 rondes waren).
Y = laad("youtube_wacht")
rc, nep = ronde(Y, kopie([("Chrome", "geweigerd"), ("Firefox", "fout")]))
st = nep.naar("/agent-status")[-1]
check("C01 YouTube: ronde mislukt", rc == 1 and st["status"] == "fout", (rc, st))
check("C01 YouTube: melding noemt geweigerd en onleesbaar",
      st["nood"] and "geweigerd: Chrome" in st["nood"][0]["tekst"] and "onleesbaar: Firefox" in st["nood"][0]["tekst"]
      and "niet gevonden" not in st["nood"][0]["tekst"], st)
log = [r for p in nep.naar("/api/logboek") for r in p["regels"]]
check("C01 YouTube: fout in het werkverslag", any(r["stap"] == "fout" and "geweigerd: Chrome" in r["tekst"] for r in log), log)
check("C01 YouTube: niets klaargezet", not nep.naar("/api/klaarzet"), nep.oproepen)
check("C01 ook de uitkomst geweigerd van de helper (YT-1)", "geweigerd: Chrome" in Y.niet_gelezen({"Chrome": "geweigerd"})
      and "geweigerd: Safari" in laad("browser_wacht").niet_gelezen({"Safari": "geweigerd"}))
rc, nep = ronde(laad("youtube_wacht"), kopie())
st = nep.naar("/agent-status")[-1]
check("C01 YouTube: zonder bestand niet gevonden", rc == 1 and st["nood"][0]["tekst"] == "Geen browsergeschiedenis gevonden op deze Mac"
      and any(r["stap"] == "fout" for p in nep.naar("/api/logboek") for r in p["regels"]), nep.oproepen)


def geen_kopie(_kanaal):
    raise laad("youtube_wacht").M.MacFout("MacGesprekkenKopie niet gestart", "MacGesprekkenKopie staat niet in launchd op de Mac")


for naam in ("youtube_wacht", "browser_wacht"):
    rc, nep = ronde(laad(naam), geen_kopie)
    log = [r for p in nep.naar("/api/logboek") for r in p["regels"]]
    check(f"C01 {naam}: zonder kopie van de helper een fout in het werkverslag, niets klaargezet",
          rc == 1 and not nep.naar("/api/klaarzet") and [r["stap"] for r in log] == ["fout"]
          and "staat niet in launchd" in log[0]["tekst"], nep.oproepen)

# C02 (WEB-2): zonder gelezen browser zette de Websitewacht 14 dagen met 0 bezoeken klaar; De Dagbundelaar nam die over.
for naam, bronnen in (("lege map", []), ("geweigerd", [("Chrome", "geweigerd")])):
    B = laad("browser_wacht")
    rc, nep = ronde(B, kopie(bronnen))
    st = nep.naar("/agent-status")[-1]
    log = [r for p in nep.naar("/api/logboek") for r in p["regels"]]
    check(f"C02 websites ({naam}): geen klaarzet", not nep.naar("/api/klaarzet"), nep.naar("/api/klaarzet"))
    check(f"C02 websites ({naam}): hartslag fout met de reden", rc == 1 and st["status"] == "fout"
          and any(("geweigerd: Chrome" if naam == "geweigerd" else "Geen browsergeschiedenis gevonden") in n["tekst"] for n in st["nood"]), st)
    check(f"C02 websites ({naam}): fout in het werkverslag", [r["stap"] for r in log] == ["fout"], log)

# C03 (WEB-3): de filter op origin zit in de helper (test_mac_gesprekken.py). Hier: een Safari die de helper las, naast
# een lege Chrome (Codex-toets 1: dat gaf 0 bezoeken met "Safari onleesbaar"), telt mee bij de websites en bij YouTube.
middag = datetime(2026, 10, 30, 12, 0, tzinfo=ZoneInfo("Europe/Brussels")).timestamp()
safari = kopie([("Chrome", "ok"), ("Safari", "ok")],
               [("Safari", middag, "youtube.com", "oudevideo1", "Proef oud", None)])
B = laad("browser_wacht")
B.DAGEN = 3
rc, nep = ronde(B, safari)
inh = nep.naar("/api/klaarzet")[-1]["items"][0]["inhoud"] if nep.naar("/api/klaarzet") else {}
check("C03 websites: Safari zonder origin telt mee naast een lege Chrome", rc == 0 and inh.get("onleesbaar") == {}
      and inh["per_dag"]["2026-10-30"]["per_browser"] == {"Safari": 1}, (rc, inh))
Y = laad("youtube_wacht")
Y.DAGEN = 3
rc, nep = ronde(Y, safari)
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

# Codex-toets 1 en 2: de Licentiewacht en het teamrapport van de Wispr-teamwacht namen het laatst bijgewerkte item
# (order by ts); na een inhaalronde was dat 20-10. Alleen hun keuzefunctie, uit de bron gelezen: geen bord, geen .env.
RUNNER = os.path.dirname(HIER)


def functie(bestand, van, tot, **ns):
    src = open(os.path.join(RUNNER, bestand), encoding="utf-8").read()
    ns.update(json=json, sqlite3=sqlite3)
    exec(src[src.index(van):src.index(tot)], ns)
    return ns


bord_db = os.path.join(map_, "bord.db")
c = sqlite3.connect(bord_db)
c.execute("CREATE TABLE klaarzet (van TEXT, sleutel TEXT, soort TEXT, inhoud TEXT, ts TEXT)")
for d, ts in (("2026-11-01", "2026-11-01T20:30:00+00:00"), ("2026-10-20", "2026-11-02T09:00:00+00:00")):
    c.execute("INSERT INTO klaarzet VALUES ('wispr-wacht', 'Proef', 'gebruik', ?, ?)",
              (json.dumps({"dienst": "Wispr Flow", "gebruiker": "Proef", "dag": d, "week_woorden": len(d)}), ts))
c.commit()
c.close()
g = functie("licentiewacht.py", "def gebruik_uit_bord(", "def main(", DB=bord_db)["gebruik_uit_bord"]()
check("C04 Licentiewacht: nieuwste gebruiksdag, niet de laatste inhaal", g[("Wispr Flow", "Proef")]["dag"] == "2026-11-01", g)
g = functie("wispr_team_wacht.py", "def gebruik_per_persoon(", "def kruiscontrole(")["gebruik_per_persoon"](
    sqlite3.connect(bord_db))
check("C04 Wispr-teamrapport: nieuwste gebruiksdag, niet de laatste inhaal", g["proef"]["dag"] == "2026-11-01", g)

print("wachten van de computer:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
