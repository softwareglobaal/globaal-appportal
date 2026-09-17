"""Grendels op de herhaalbaarheidslaag van de runners (masker, validatie, hash, record, slot)."""
import json, os, sys, tempfile
from pathlib import Path
HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER / "koppelingen"))
os.environ["HOME"] = tempfile.mkdtemp(prefix="hh_")  # record en slot in een wegwerpmap
import herhaalbaar as hh
hh.DATA = Path(os.environ["HOME"]) / "mijnagents-data"

ok = fout = 0
def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde: ok += 1; print(f"  OK   {naam}")
    else: fout += 1; print(f"  FOUT {naam} -> {extra}")

print("\n1. masker: rijksregisternummers verdwijnen, andere getallen niet")
for ruw in ("83.01.03-095.13", "83010309513", "83 01 03 095 13", "62.08.10-239.43"):
    check(f"{ruw} -> [RRN]", hh.masker_rrn(f"nummer {ruw} van de klant") == "nummer [RRN] van de klant", hh.masker_rrn(ruw))
check("een telefoonnummer blijft staan", hh.masker_rrn("gsm 0497235988") == "gsm 0497235988")
check("een ondernemingsnummer blijft staan", hh.masker_rrn("KBO 0824.378.947") == "KBO 0824.378.947")
check("een bedrag blijft staan", hh.masker_rrn("150.000,00 euro") == "150.000,00 euro")
check("diep door dicts en lijsten", hh.masker_diep({"a": ["83.01.03-095.13"], "b": {"c": "x"}}) == {"a": ["[RRN]"], "b": {"c": "x"}})

print("\n2. validatie vóór het schrijven")
goed, weg = hh.valideer_gegevens({"bouwbudget_bedrag_euro": "150000", "ereloon_percentage_bouwproject": "12%",
                                  "opdrachtgever_1_email": "kim@example.be", "opdrachtgever_1_tel": "0497 23 59 88",
                                  "project_capakey": "13050B0328/00S003", "opdrachtgever_1_rijksregister": "83010309513",
                                  "hoedanigheid_opdrachtgever_label": " eigenaar ", "zomaar": "x"},
                                 "mail van de klant 07-09-2026",
                                 toegelaten={"bouwbudget_bedrag_euro", "ereloon_percentage_bouwproject", "opdrachtgever_1_email",
                                             "opdrachtgever_1_tel", "hoedanigheid_opdrachtgever_label", "project_capakey",
                                             "opdrachtgever_1_rijksregister"})
check("bedrag genormaliseerd", goed.get("bouwbudget_bedrag_euro") == "150.000,00", goed)
check("percentage genormaliseerd", goed.get("ereloon_percentage_bouwproject") == "12", goed)
check("tekst gestript", goed.get("hoedanigheid_opdrachtgever_label") == "eigenaar")
check("e-mail en telefoon aanvaard", "opdrachtgever_1_email" in goed and "opdrachtgever_1_tel" in goed)
redenen = {v: r for v, _, r in weg}
check("capakey geweigerd (systeem bepaalt)", "project_capakey" in redenen, redenen)
check("rijksregister geweigerd (D18) en gemaskeerd in de reden", "opdrachtgever_1_rijksregister" in redenen
      and all("83010309513" not in str(x) for x in weg))
check("onbekend veld geweigerd", "zomaar" in redenen)
for ruw, net in (("150.000", "150.000,00"), ("150000.00", "150.000,00"), ("2.500,5", "2.500,50"), ("7000", "7.000,00"), ("abc", None), ("-5", None)):
    check(f"bedrag {ruw!r} -> {net!r}", hh.normaliseer_bedrag(ruw) == net, hh.normaliseer_bedrag(ruw))
goed, weg = hh.valideer_gegevens({"x": "y"}, "kort")
check("zonder bron niets", not goed and weg)
goed, weg = hh.valideer_keuzes({"architectuur_scope": "Wind_Waterdicht", "budget_scenario": "vierkante_meterprijs", "project_beschrijving": "tekst"},
                               {"architectuur_scope": ["wind_waterdicht", "volledige_afwerking"], "budget_scenario": ["vast_bedrag"]},
                               {"project_beschrijving"})
check("keuze hoofdletterongevoelig naar de canonieke waarde", goed.get("architectuur_scope") == "wind_waterdicht", goed)
check("ongeldige keuze geweigerd", any(v == "budget_scenario" for v, _, _ in weg))
check("vrij veld aanvaard", goed.get("project_beschrijving") == "tekst")

print("\n3. invoerhash en plan-cache")
h1, per = hh.invoerhash({"bronnen": {"a": 1}, "dossier": {"b": 2}, "model": "claude-opus-5"})
h2, _ = hh.invoerhash({"bronnen": {"a": 1}, "dossier": {"b": 2}, "model": "claude-opus-5"})
h3, per3 = hh.invoerhash({"bronnen": {"a": 1}, "dossier": {"b": 3}, "model": "claude-opus-5"})
check("zelfde invoer, zelfde hash", h1 == h2)
check("andere invoer, andere hash, en het deel dat verschilt is aanwijsbaar", h1 != h3 and per["bronnen"] == per3["bronnen"] and per["dossier"] != per3["dossier"])
check("cache leeg", hh.plan_uit_cache("agent-x", 1, h1) is None)
hh.plan_in_cache("agent-x", 1, h1, {"gegevens": []}, {"model": "m"})
check("plan uit cache", hh.plan_uit_cache("agent-x", 1, h1)["plan"] == {"gegevens": []})

print("\n4. run-record: alleen toevoegen, gemaskeerd")
r = hh.RunRecord("agent-x", 1).zet(invoerhash=h1, model_id="claude-opus-5", plan={"velden": {"n": "83010309513"}}).sluit("klaar")
regels = (hh.DATA / "runrecords" / "agent-x.jsonl").read_text().splitlines()
check("één regel geschreven met run_id, start, einde, status", len(regels) == 1 and all(k in json.loads(regels[0]) for k in ("run_id", "start", "einde", "status")))
check("geen rijksregisternummer in het record", "83010309513" not in regels[0])
check("kost berekend voor een bekend model", hh.kost_eur("claude-opus-5", 100000, 4000) is not None and hh.kost_eur("onbekend", 1, 1) is None)

print("\n5. slot tegen dubbele rondes")
with hh.Slot("agent-x") as s1:
    try:
        with hh.Slot("agent-x"):
            check("tweede ronde geweigerd terwijl de eerste loopt", False)
    except RuntimeError as e:
        check("tweede ronde geweigerd terwijl de eerste loopt", "loopt nog" in str(e))
with hh.Slot("agent-x"):
    check("na afloop is het slot vrij", True)

print(f"\n{'='*50}\n{ok} geslaagd, {fout} gefaald\n{'='*50}")
sys.exit(1 if fout else 0)
