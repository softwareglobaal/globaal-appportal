"""Grendels op de aanvragen van de FelixArchief-pagina (13-10-2026).

Afspraak (Shaniel): Shelton vraagt zoektochten aan zonder goedkeuring van Mehdi; elk resultaat staat in het
logboek; opslaan in de projectmap gebeurt alleen op een klik, in een nieuwe map, nooit twee keer. De runner
schrijft alleen stand.json en log.jsonl, nooit het aanvragenbestand van de pagina. Geen netwerk, geen browser,
geen Dropbox: alles nagebootst.

Draaien:   python3 mijnagents-runner/tests/test_felix_aanvragen.py
"""
import json
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
os.environ["FELIX_DATA"] = tempfile.mkdtemp()
import felix_wacht as W  # noqa: E402
import bord  # noqa: E402
import bronnen  # noqa: E402

fouten = 0


def check(naam, voorwaarde, extra=""):
    global fouten
    print(("   geslaagd  " if voorwaarde else "   MISLUKT   ") + naam + ("" if voorwaarde else f": {extra}"))
    fouten += 0 if voorwaarde else 1


class NepRonde:
    def __init__(self):
        self.detail, self.noden = "", []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def bron(self, *a):
        pass

    def nood(self, tekst, wie="mehdi"):
        self.noden.append(tekst)


class NepAgent:
    def __init__(self, naam):
        self.r, self.logs = NepRonde(), []

    def ronde(self, taak):
        return self.r

    def log(self, *a):
        self.logs.append(a)


bord.Agent = NepAgent
gezocht = []


def nep_voer_uit(adres, uitmap=None, project=None):
    gezocht.append(adres)
    if "fout" in adres:
        raise RuntimeError("FelixArchief niet bereikbaar")
    if "traag" in adres:
        raise RuntimeError("Page.goto: Timeout 60000ms exceeded.")
    os.makedirs(os.path.join(uitmap, "_gegevens"), exist_ok=True)
    os.makedirs(os.path.join(uitmap, "FelixArchief", "123#4"), exist_ok=True)
    open(os.path.join(uitmap, "Controle.md"), "w").write("# x\n")
    open(os.path.join(uitmap, "FelixArchief", "123#4", "plan.pdf"), "wb").write(b"%PDF")
    open(os.path.join(uitmap, "_gegevens", "resultaat.json"), "w").write("{}")
    return uitmap, {"besluit": "Perceel X: 1 vergunning", "raak": [{}], "stad": {"vergunningen": [{}]}}


W.voer_uit = nep_voer_uit
geupload = []
bronnen.upload = lambda pad, data: geupload.append(pad) or pad
W.projectmap = lambda project: "/Work All/01. H-A WORK/1. STAN/3810 Kerkstraat 12, 2000 Antwerpen" if project == "3810" else None


def aanvraag(**a):
    with open(W.AANVRAGEN, "a") as f:
        f.write(json.dumps(a) + "\n")


aanvraag(id="a1", soort="zoek", project="3810", adres="Kerkstraat 12, 2000 Antwerpen", door="shelton", ts="t")
aanvraag(id="a2", soort="zoek", project="", adres="fout 1, 2000 Antwerpen", door="shelton", ts="t")
open(W.AANVRAGEN, "a").write("kapotte regel\n")
voor = open(W.AANVRAGEN).read()
W.ronde()
s = W.lees_stand()
check("zoektocht klaar met besluit en map", s["zoek"]["a1"]["status"] == "klaar" and s["zoek"]["a1"]["map"].startswith("a1 "), s["zoek"].get("a1"))
check("een falend adres wordt fout, de rest gaat door", s["zoek"]["a2"]["status"] == "fout" and "niet bereikbaar" in s["zoek"]["a2"]["fout"])
check("aanvragenbestand van de pagina onaangeroerd", open(W.AANVRAGEN).read() == voor)
log = [json.loads(x) for x in open(W.LOGBOEK)]
check("logboek: aanvraag, resultaat en fout", [l["gebeurtenis"] for l in log] == ["aanvraag", "resultaat", "aanvraag", "fout"], log)
check("geen upload zonder klik", not geupload)

W.ronde()
check("tweede ronde zoekt niets opnieuw", gezocht.count("Kerkstraat 12, 2000 Antwerpen") == 1, gezocht)

aanvraag(id="o1", soort="opslaan", zoek_id="a1", door="shelton", ts="t")
aanvraag(id="o2", soort="opslaan", zoek_id="a1", door="shelton", ts="t")
aanvraag(id="o3", soort="opslaan", zoek_id="a2", door="shelton", ts="t")
W.ronde()
s = W.lees_stand()
check("opslaan: alles behalve _gegevens, in een nieuwe map FelixArchief <datum>",
      len(geupload) == 2 and all("/3810 Kerkstraat" in p and "/FelixArchief " in p for p in geupload)
      and not any("_gegevens" in p for p in geupload), geupload)
check("tweede opslagklik: niet opnieuw geupload", len(geupload) == 2 and "al opgeslagen" in s["opslaan"]["o2"].get("fout", ""), s["opslaan"].get("o2"))
check("opslaan van een mislukte zoektocht: geweigerd", "niet" in s["opslaan"]["o3"].get("fout", ""))
check("opgeslagen staat bij de zoektocht", s["zoek"]["a1"]["opgeslagen"]["bestanden"] == 2)
log = [json.loads(x) for x in open(W.LOGBOEK)]
check("logboek: opgeslagen en geweigerd", [l["gebeurtenis"] for l in log][-3:] == ["opgeslagen", "opslaan_mislukt", "opslaan_mislukt"], log[-3:])

aanvraag(id="t1", soort="zoek", project="", adres="traag 1, 2000 Antwerpen", door="shelton", ts="t")
for _ in range(5):
    W.ronde()
s = W.lees_stand()
check("timeout: drie pogingen, dan fout", gezocht.count("traag 1, 2000 Antwerpen") == W.POGINGEN
      and s["zoek"]["t1"]["status"] == "fout" and s["zoek"]["t1"]["pogingen"] == W.POGINGEN, s["zoek"].get("t1"))
check("een gewone fout wordt niet opnieuw geprobeerd", gezocht.count("fout 1, 2000 Antwerpen") == 1)
log = [json.loads(x)["gebeurtenis"] for x in open(W.LOGBOEK)]
check("logboek: opnieuw geprobeerd staat erin", log.count("opnieuw") == W.POGINGEN - 1, log)

print("%d grendels mislukt" % fouten)
sys.exit(1 if fouten else 0)
