"""Grendel op het blok 'Eigen werk en gezondheid' (Mehdi, 31-10-2026: Wispr, websites en Apple Watch in het Dagboek).

- E01: een dag die een wacht zag, toont aantallen, ook 0; een dag zonder wacht is onbekend, nooit 0;
- E02: de nieuwste ronde van een wacht met per_dag wint; een oud Wispr-item zonder per_dag telt voor zijn eigen dag;
- E03: geen gezondheidsmetingen geeft de zin over Health Auto Export, metingen staan zonder kop;
- E04: de Browserwacht houdt alleen de sitenaam, nooit het adres, en geen chrome:, file: of about:;
- E05: zonder eigen (oude aanroep) blijft het blok weg en de tekst gelijk; geen gedachtestreepje.
- E07: leest de Browserwacht geen enkele browser (geen Full Disk Access), dan zet ze niets klaar, geen nullen.
- E08: De Dagbundelaar laat een websites-item zonder gelezen browser weg (onbekend); een gelezen browser met 0 bezoeken telt.
"""
import importlib.util
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(RUNNER, "koppelingen"))
import dagvaststelling as V  # noqa: E402

fout = 0


def check(naam, ok, extra=""):
    global fout
    print(("  ok   " if ok else "  FOUT ") + naam, "" if ok else extra)
    fout += 0 if ok else 1


def laad(naam, pad):
    spec = importlib.util.spec_from_file_location(naam, pad)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def dag(eigen=None):
    v = V.vaststellen("2026-10-30", [], [], [], {}, [], "volledig", None, {}, lambda a: False, eigen=eigen)
    return V.tekst(v)


t = dag({"wispr": {"dictaten": 19, "woorden": 2599, "seconden": 902.5},
         "websites": {"bezoeken": 0, "sites": 0, "top": []}, "gezondheid": None})
check("E01 Wispr met aantallen", "- Wispr Flow: 19 dictaten, 2599 woorden, 15 min ingesproken" in t, t)
check("E01 websites 0 als de wacht keek", "- websites: 0 bezoeken op 0 sites" in t, t)
t = dag({"wispr": None, "websites": None, "gezondheid": None})
check("E01 zonder wacht onbekend", "Wispr Flow: onbekend" in t and "websites: nog niet aangesloten" in t, t)
check("E03 geen gezondheid", "Health Auto Export stuurt nog niets" in t)

# dagbundelaar zonder zijn zware imports: alleen de leesfuncties
src = open(os.path.join(RUNNER, "dagbundelaar.py"), encoding="utf-8").read()
ns = {"json": __import__("json"), "os": os}
start = src.index("def _inhoud(x):")
eind = src.index("\ndef ", src.index("def lees_eigen(eerste):") + 1)
exec(src[start:eind], ns)
ns["WISPR_GEBRUIKER"] = "Mehdi"
items = [{"uniek": "wispr:Mehdi:2026-10-29", "inhoud": '{"vandaag": {"dictaten": 3, "woorden": 40, "seconden": 30}}'},
         {"uniek": "wispr:Mehdi:2026-10-31", "inhoud": '{"vandaag": {"dictaten": 0}, "per_dag": {"2026-10-30": {"dictaten": 19}, "2026-10-31": {"dictaten": 0}}}'},
         {"uniek": "wispr:Mehdi:2026-10-30", "inhoud": '{"vandaag": {"dictaten": 7}}'}]
pd = ns["per_dag_uit"](items, "wispr:Mehdi:", lambda i: i.get("vandaag"))
check("E02 nieuwste ronde wint", pd["2026-10-30"]["dictaten"] == 19 and pd["2026-10-31"]["dictaten"] == 0, pd)
check("E02 oud item telt voor zijn dag", pd["2026-10-29"]["dictaten"] == 3, pd)
# E08 (overleg 02-11-2026 K4): tweede vangnet in De Dagbundelaar tegen oude items met nullen.
wi = [{"uniek": "websites:2026-11-01", "inhoud": '{"browsers": {}, "per_dag": {"2026-11-01": {"bezoeken": 0, "sites": 0, "top": []}}}'},
      {"uniek": "websites:2026-11-02", "inhoud": '{"browsers": {"Chrome": 9}, "per_dag": {"2026-11-02": {"bezoeken": 0, "sites": 0, "top": []}}}'},
      {"uniek": "websites:2026-10-31", "inhoud": '{"per_dag": {"2026-10-31": {"bezoeken": 5, "sites": 1, "top": [["a.be", 5]]}}}'}]


class _Bord:
    """Nagebootst bord voor lees_eigen: alleen websites-items, de rest leeg."""
    def db_lees(self, sql, params):
        return wi if "websites:" in sql else []


ns["bord"] = _Bord()
eigen = ns["lees_eigen"]("2026-10-31")
check("E08 zonder gelezen browser onbekend", eigen("2026-11-01")["websites"] is None and eigen("2026-10-31")["websites"] is None,
      [eigen(d) for d in ("2026-10-31", "2026-11-01")])
check("E08 gelezen browser met 0 bezoeken telt", eigen("2026-11-02")["websites"] == {"bezoeken": 0, "sites": 0, "top": []},
      eigen("2026-11-02"))

g = ns["gezondheid_regels"]("Gezondheid op 2026-10-30\n========================\nGeen metingen in deze periode.")
check("E03 geen metingen is None", g is None, g)
g = ns["gezondheid_regels"]("Gezondheid op 2026-10-30\n=====\nStappen: 8234\nRusthartslag: 58\n\nSlaap: 6u40")
check("E03 metingen zonder kop", g == ["Stappen: 8234", "Rusthartslag: 58", "Slaap: 6u40"], g)
t = dag({"wispr": None, "websites": None, "gezondheid": g})
check("E03 gezondheid in het blok", "- gezondheid (Apple Watch):\n  - Stappen: 8234" in t, t)

B = laad("browser_wacht", os.path.join(RUNNER, "mac", "browser_wacht.py"))
check("E04 alleen de sitenaam", B.site("https://www.monday.com/boards/1?q=geheim") == "monday.com")
check("E04 geen interne adressen", B.site("chrome://settings") is None and B.site("file:///Users/x") is None
      and B.site("about:blank") is None)
tl = B.tel([("Chrome", 1793350800, "monday.com"), ("Chrome", 1793350900, "monday.com"), ("Firefox", 1793351000, "claude.ai"),
            ("Chrome", 1793351100, None)], ["2026-10-30", "2026-10-29"])
check("E04 telling per dag, ook 0", tl["2026-10-29"]["bezoeken"] == 0 and tl["2026-10-30"]["bezoeken"] == 3
      and tl["2026-10-30"]["top"][0] == ["monday.com", 2], tl)

Y = laad("youtube_wacht", os.path.join(RUNNER, "mac", "youtube_wacht.py"))
check("E06 alleen video's", Y.video("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=5") == "dQw4w9WgXcQ"
      and Y.video("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ" and Y.video("https://www.youtube.com/shorts/abcdef12")
      == "abcdef12" and Y.video("https://www.youtube.com/results?search_query=geheim") is None
      and Y.video("https://www.youtube.com/") is None and Y.video("https://monday.com/watch?v=abcdefgh") is None)
check("E06 titel zonder YouTube", Y.titel_schoon("(3) Werfbezoek uitleg - YouTube") == "Werfbezoek uitleg")
ty = Y.tel([("Chrome", 1793350800, "a1b2c3d4", "Video A", 600.0), ("Chrome", 1793351800, "a1b2c3d4", "Video A", 99999.0),
            ("Safari", 1793352000, "z9y8x7w6", "Video B", None)], ["2026-10-30", "2026-10-29"])
check("E06 telling per dag", ty["2026-10-30"]["videos"] == 2 and ty["2026-10-30"]["keer"] == 3
      and ty["2026-10-30"]["minuten"] == 190 and ty["2026-10-30"]["top"][0] == ["Video A", 2]
      and ty["2026-10-29"] == {"videos": 0, "keer": 0, "minuten": 0, "top": []}, ty)
check("E06 zonder duur onbekend", Y.tel([("Safari", 1793352000, "z9y8x7w6", "B", None)], ["2026-10-30"])["2026-10-30"]["minuten"] is None)
t = dag({"wispr": None, "websites": None, "youtube": ty["2026-10-30"], "gezondheid": None})
check("E06 YouTube in het blok", "- YouTube: 2 video's, 190 min; meest: Video A (2); Video B (1)" in t, t)
t = dag({"wispr": None, "websites": None, "youtube": ty["2026-10-29"], "gezondheid": None})
check("E06 0 als de wacht keek", "- YouTube: 0 video's, 0 min" in t, t)
t = dag({"wispr": None, "websites": None, "youtube": None, "gezondheid": None})
check("E06 onbekend zonder wacht", "- YouTube: onbekend (YouTube-wacht las deze dag niet)" in t, t)
t2 = dag({"wispr": None, "websites": None, "gezondheid": None})
check("E06 oude aanroep zonder YouTube-regel", "YouTube" not in t2, t2)

# E07 (T-0077, 02-11-2026): onder launchd zonder Full Disk Access leest de wacht niets; dan geen klaarzet met nullen.
aanroepen = []
B.bord = lambda pad, payload: aanroepen.append((pad, payload)) or {}
B.BRONNEN = ()
B.DROOG = False
B.DAGEN = 3
B.main()
paden = [p for p, _ in aanroepen]
status = [p.get("status") for pad, p in aanroepen if pad == "/agent-status"]
check("E07 niets gelezen: geen klaarzet", "/api/klaarzet" not in paden, paden)
check("E07 niets gelezen: precies een logregel", paden.count("/api/logboek") == 1
      and len(aanroepen[paden.index("/api/logboek")][1]["regels"]) == 1, aanroepen)
check("E07 niets gelezen: hartslag eindigt op fout", status and status[-1] == "fout", status)


def bord_faalt(pad, payload):
    aanroepen.append((pad, payload))
    if pad == "/api/logboek":
        raise OSError("bord weg")
    return {}


aanroepen = []
B.bord = bord_faalt
B.main()
status = [p.get("status") for pad, p in aanroepen if pad == "/agent-status"]
check("E07 logboek mislukt: toch hartslag fout en geen klaarzet", status[-1] == "fout"
      and "/api/klaarzet" not in [p for p, _ in aanroepen], aanroepen)

oud = dag()
check("E05 zonder eigen geen blok", "Eigen werk en gezondheid" not in oud)
check("E05 geen gedachtestreepje", "—" not in t + oud and "–" not in t + oud)
print("eigen werk en gezondheid:", "alles ok" if not fout else f"{fout} fout")
sys.exit(1 if fout else 0)
