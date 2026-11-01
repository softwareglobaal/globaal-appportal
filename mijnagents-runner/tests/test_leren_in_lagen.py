"""Grendel op het leren in lagen (FR-71, FR-72).

Laag 1 (claude-hooks/regels_vooraf.py + regels.json): de harde regels staan voor Claude voor hij handelt, en de
weekconsolidatie kan er alleen regels bijzetten, nooit een vaste regel of een patroon weghalen.
Laag 3 (claude-hooks/correctie.py): een correctie van Mehdi wordt een opdracht om het in de bron vast te zetten.
Laag 4 (weekconsolidatie.py): een keer per week, gestructureerd antwoord, een weigering valt op, het item in de
agenda blokkeert niets. Een test roept het model nooit echt aan en schrijft nooit in een echte agenda.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

os.environ["BELLEN_UIT"] = "1"      # een test belt nooit echt (FR-55)

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
sys.path.insert(0, str(HIER / "claude-hooks"))
import agenda_wacht as W            # noqa: E402
import regels_vooraf as R1          # noqa: E402
import weekconsolidatie as WC       # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  ok   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} {extra}")


def hook(script, invoer):
    r = subprocess.run([sys.executable, str(HIER / "claude-hooks" / script)], input=json.dumps(invoer),
                       capture_output=True, text=True, timeout=30)
    try:
        return r.returncode, json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None
    except (ValueError, KeyError):
        return r.returncode, {"fout": r.stdout}


# ---------- laag 1: de vaste regels ----------
vast = json.loads((HIER / "claude-hooks" / "regels.json").read_text(encoding="utf-8"))
namen = [c["naam"] for c in vast["categorieen"]]
check("laag 1: de vijf categorieen bestaan", set(namen) == {"agenda", "server", "calendly", "wissen", "mail"}, str(namen))
check("laag 1: de categorieen van de weekconsolidatie zijn dezelfde",
      set(WC.SCHEMA["properties"]["regels_vooraf"]["items"]["properties"]["naam"]["enum"]) == set(namen))
for c in vast["categorieen"]:
    try:
        re.compile(c["bericht"]), re.compile(c["opdracht"])
        geldig = True
    except re.error:
        geldig = False
    check(f"laag 1: {c['naam']} heeft geldige patronen en hoogstens drie regels", geldig and 1 <= len(c["regels"]) <= 3)
alles = json.dumps(vast, ensure_ascii=False)
for kern in ("Niets verwijderen zonder expliciete ja", "git pull --ff-only", "!! staat altijd vooraan",
             "'0 fout'", "nooit gokken", "dagcontrole.py --dag"):
    check(f"laag 1: vaste regel staat erin: {kern}", kern in alles)

# ---------- laag 1: de hook ----------
rc, uit = hook("regels_vooraf.py", {"hook_event_name": "UserPromptSubmit",
                                    "prompt": "zet zaterdag om 13 uur een afspraak met 2443"})
check("laag 1: een agendavraag krijgt de agendaregels vooraf",
      rc == 0 and uit and uit["hookEventName"] == "UserPromptSubmit" and "Harde regels voor agenda" in uit["additionalContext"], str(uit)[:200])
rc, uit = hook("regels_vooraf.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                    "tool_input": {"command": "ssh globaal 'cd ~/appportal && git pull --rebase --autostash'"}})
check("laag 1: een git-opdracht op de server krijgt de serverregels",
      rc == 0 and uit and "Harde regels voor server" in uit["additionalContext"] and "ff-only" in uit["additionalContext"], str(uit)[:200])
rc, uit = hook("regels_vooraf.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash",
                                    "tool_input": {"command": "curl -X DELETE https://www.googleapis.com/calendar/v3/calendars/x/events/y"}})
check("laag 1: een DELETE krijgt de regels over wissen", rc == 0 and uit and "Harde regels voor wissen" in uit["additionalContext"], str(uit)[:200])
rc, uit = hook("regels_vooraf.py", {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls -la"}})
check("laag 1: een gewone opdracht krijgt niets", rc == 0 and uit is None, str(uit)[:200])
r = subprocess.run([sys.executable, str(HIER / "claude-hooks" / "regels_vooraf.py")], input="geen json",
                   capture_output=True, text=True, timeout=30)
check("laag 1: kapotte invoer blokkeert Claude nooit", r.returncode == 0 and not r.stdout.strip())

with tempfile.TemporaryDirectory() as d:
    nu = datetime(2026, 10, 5, 8, tzinfo=timezone.utc)
    wk = Path(d) / "regels-vooraf.json"
    wk.write_text(json.dumps({"gemaakt": "2026-10-04T18:05:00+00:00", "categorieen": [
        {"naam": "agenda", "regels": ["een", "twee", "drie"], "bericht": ".*"},
        {"naam": "wissen", "regels": []}]}))
    rr = {c["naam"]: c for c in R1.regels(wk, nu)}
    check("laag 1: de week zet hoogstens twee regels bij", rr["agenda"]["week"] == ["een", "twee"], str(rr["agenda"]["week"]))
    check("laag 1: het patroon komt altijd uit de repo, nooit uit de week",
          rr["agenda"]["bericht"] == next(c["bericht"] for c in vast["categorieen"] if c["naam"] == "agenda"))
    check("laag 1: een lege week haalt geen vaste regel weg",
          rr["wissen"]["regels"] == next(c["regels"] for c in vast["categorieen"] if c["naam"] == "wissen"))
    check("laag 1: de weekregels staan achter de vaste regels in de tekst",
          R1.tekst_voor(rr["agenda"]).index("(4) een") > R1.tekst_voor(rr["agenda"]).index("(3)"))
    oud = {c["naam"]: c for c in R1.regels(wk, nu + timedelta(days=20))}
    check("laag 1: een weekbestand ouder dan twee weken telt niet", oud["agenda"]["week"] == [])
    check("laag 1: zonder weekbestand gewoon de vaste regels",
          all(c["week"] == [] and c["regels"] for c in R1.regels(Path(d) / "bestaat-niet.json", nu)))

# ---------- laag 2: de dagcontrole toont de markers (FR-74) ----------
import dagcontrole as DC2    # noqa: E402
_mk = [{"id": "b1", "titel": "Mehdi: Buitenland", "start": "2026-10-04", "einde": "2026-10-12", "hele_dag": True, "kalender": W.WERKAGENDA},
       {"id": "w1", "titel": "!! Mehdi: [HARC-KB] WB 2145 - wekelijks werfbezoek", "start": "2026-10-12T09:30:00+02:00",
        "einde": "2026-10-12T11:30:00+02:00", "kalender": W.WERKAGENDA}]
check("laag 2: een marker over meerdere dagen staat in de dagcontrole van elke dag die hij dekt",
      "Buitenland" in DC2.samenvatting(_mk, "2026-10-05") and "tot 12-10" in DC2.samenvatting(_mk, "2026-10-05")
      and "Buitenland" in DC2.samenvatting(_mk, "2026-10-11") and "Buitenland" not in DC2.samenvatting(_mk, "2026-10-12"),
      DC2.samenvatting(_mk, "2026-10-05"))
check("laag 1: eerst de agenda van de week lezen voor een vraag", "wat daar staat vraag je niet" in alles or
      "wat daar staat vraag je niet" in json.dumps(json.loads((HIER / "claude-hooks" / "regels.json").read_text(encoding="utf-8")), ensure_ascii=False))

# ---------- laag 3: de correctie-hook ----------
rc, uit = hook("correctie.py", {"hook_event_name": "UserPromptSubmit", "prompt": "waarom blijf je dezelfde fout maken"})
check("laag 3: een correctie wordt een opdracht om het vast te zetten",
      rc == 0 and uit and "additionalContext" in uit, str(uit)[:200])
rc, uit = hook("correctie.py", {"hook_event_name": "UserPromptSubmit", "prompt": "zet morgen om tien uur Tom bellen"})
check("laag 3: een gewone opdracht krijgt niets", rc == 0 and uit is None, str(uit)[:200])

# ---------- laag 4: planning en schema ----------
zondag = datetime(2026, 10, 4, 20, 5)
check("laag 4: weeknaam is ISO", WC.weeknaam(zondag) == "2026-W40", WC.weeknaam(zondag))
check("laag 4: het overzicht komt op de maandag erna", WC.maandag_na(zondag) == date(2026, 10, 5))
check("laag 4: met de hand op maandag gaat het naar de volgende maandag", WC.maandag_na(datetime(2026, 10, 5, 9)) == date(2026, 10, 12))
check("laag 4: alleen zondag om 20 uur Brusselse tijd", WC.is_consolidatietijd(zondag)
      and not WC.is_consolidatietijd(zondag.replace(hour=19)) and not WC.is_consolidatietijd(datetime(2026, 10, 5, 20)))
with tempfile.TemporaryDirectory() as d:
    (Path(d) / "2026-W40.json").write_text(json.dumps({"ronde": False}))
    check("laag 4: een run met de hand houdt de zondagsronde niet tegen", not WC.al_gedaan("2026-W40", Path(d)))
    (Path(d) / "2026-W40.json").write_text(json.dumps({"ronde": True}))
    check("laag 4: een tweede zondagsronde in dezelfde week draait niet", WC.al_gedaan("2026-W40", Path(d)))


def streng(s, pad="schema"):
    """Gestructureerde uitvoer eist bij elk object additionalProperties false en alle velden verplicht."""
    fouten = []
    if s.get("type") == "object":
        if s.get("additionalProperties") is not False or set(s.get("required", [])) != set(s.get("properties", {})):
            fouten.append(pad)
        for k, v in s.get("properties", {}).items():
            fouten += streng(v, f"{pad}.{k}")
    if s.get("type") == "array":
        fouten += streng(s.get("items", {}), f"{pad}[]")
    return fouten


check("laag 4: het schema is streng (additionalProperties false, alles verplicht)", not streng(WC.SCHEMA), str(streng(WC.SCHEMA)))

# ---------- laag 4: de aanroep (nagemaakt) ----------
ANTWOORD = {"overzicht": "Rustige week. Suriname-reis voorbereid.", "teruggekomen": [
    {"ids": ["FR-68"], "wat": "rit overlapt", "waarom": "grendel keek niet naar Lara", "voorstel": "dagcontrole uitbreiden"}],
    "principes": [{"les": "kijk naar de dag", "uit": ["FR-68", "FR-69"]}], "opruimen": [],
    "regels_vooraf": [{"naam": "agenda", "regels": ["!! staat altijd vooraan, dan de naam; buiten is altijd rood, ook met ?? (FR-64, FR-67).",
                                                    "nieuw 1", "nieuw 2", "nieuw 3"]},
                      {"naam": "onbekend", "regels": ["x"]}, {"naam": "agenda", "regels": ["dubbel"]}],
    "voor_mehdi": [{"vraag": "Lara op 23-11?", "volgende_stap": "kies wie Lara haalt"}] * 7}


class Nep:
    def __init__(self, stop="end_turn", tekst=json.dumps(ANTWOORD)):
        self.kw = None
        self.stop, self.tekst = stop, tekst
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self.create))

    def create(self, **kw):
        self.kw = kw
        return SimpleNamespace(model="claude-opus-5-5", stop_reason=self.stop,
                               usage=SimpleNamespace(input_tokens=100, output_tokens=50),
                               content=[] if self.stop == "refusal" else [SimpleNamespace(type="text", text=self.tekst)])


nep = Nep()
ruw, meta = WC.model_oordeel({"week": "2026-W40"}, client=nep)
kw = nep.kw
check("laag 4: model claude-opus-5-5", kw["model"] == "claude-opus-5-5", kw["model"])
check("laag 4: fallbacks default met de juiste beta",
      kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"], str((kw.get("fallbacks"), kw.get("betas"))))
check("laag 4: gestructureerd antwoord volgens het schema",
      kw["output_config"]["format"] == {"type": "json_schema", "schema": WC.SCHEMA} and kw["output_config"]["effort"] == "high")
check("laag 4: geen thinking uitgezet en geen budget_tokens (400 op Opus 5.5)", "thinking" not in kw)
check("laag 4: ruimte voor denken en antwoord (16000 kapte W40 tot W42 af)", kw["max_tokens"] >= 64000 and kw["timeout"] >= 1800,
      str((kw.get("max_tokens"), kw.get("timeout"))))
check("laag 4: het antwoord wordt gelezen", ruw["overzicht"].startswith("Rustige week") and meta["tokens_in"] == 100)
for stop in ("refusal", "max_tokens"):
    try:
        WC.model_oordeel({}, client=Nep(stop=stop))
        gevangen = False
    except (WC.Weigering, RuntimeError):
        gevangen = True
    check(f"laag 4: stop_reason {stop} valt op en wordt geen leeg overzicht", gevangen)

uit = WC.schoon(ruw, vast["categorieen"])
check("laag 4: nooit het woord Suriname", "urinam" not in json.dumps(uit, ensure_ascii=False).lower() and "SU-reis" in uit["overzicht"])
check("laag 4: hoogstens vijf vragen", len(uit["voor_mehdi"]) == 5)
check("laag 4: per categorie hoogstens twee weekregels, zonder herhaling van een vaste regel",
      uit["regels_vooraf"] == [{"naam": "agenda", "regels": ["nieuw 1", "nieuw 2"]}], str(uit["regels_vooraf"]))

# ---------- laag 4: bestanden en agenda ----------
with tempfile.TemporaryDirectory() as d:
    oud = WC.WEEKMAP, WC.REGELS_WEEK
    WC.WEEKMAP, WC.REGELS_WEEK = Path(d) / "weekconsolidatie", Path(d) / "regels-vooraf.json"
    try:
        WC.schrijf("2026-W40", uit, meta, ronde=False, proef=True)
        check("laag 4: een proef raakt de regels van laag 1 niet", not WC.REGELS_WEEK.exists()
              and (WC.WEEKMAP / "2026-W40-proef.md").exists())
        WC.schrijf("2026-W40", uit, meta, ronde=True, nu_utc=datetime(2026, 10, 4, 18, 5, tzinfo=timezone.utc))
        rw = json.loads(WC.REGELS_WEEK.read_text())
        rr = {c["naam"]: c for c in R1.regels(WC.REGELS_WEEK, datetime(2026, 10, 5, tzinfo=timezone.utc))}
        check("laag 4 -> laag 1: de weekregels komen in de hook", rr["agenda"]["week"] == ["nieuw 1", "nieuw 2"], str(rw))
        check("laag 4: de ronde telt als gedaan", WC.al_gedaan("2026-W40"))
    finally:
        WC.WEEKMAP, WC.REGELS_WEEK = oud

body = WC.agenda_body("2026-W40", date(2026, 10, 5), uit)
check("laag 4: agenda-item op de privé-agenda, die de agent mag lezen", WC.PRIVE in W.KALENDERS)
check("laag 4: hele dag op maandag", body["start"] == {"date": "2026-10-05"} and body["end"] == {"date": "2026-10-06"})
check("laag 4: vrij, blokkeert geen Calendly-slot (FR-57)", body["transparency"] == "transparent")
check("laag 4: zonder melding", body["reminders"] == {"useDefault": False, "overrides": []})
check("laag 4: gestempeld met het weeknummer", body["extendedProperties"]["private"]["agendawacht_week"] == "2026-W40")
_lang = WC.agenda_body("2026-W40", date(2026, 10, 5), dict(uit, overzicht="x" * 9000))
check("laag 4 (fase 2, Q6): de link naar de weekpagina staat er precies een keer, ook bij een lange tekst",
      body["description"].count("https://mijnagents.globaal.be/week/2026-W40") == 1
      and "mijnagents.globaal.be/week/2026-W40" in WC.agenda_body("2026-W40", date(2026, 10, 5),
                                                                   WC.mislukt_overzicht("2026-W40", RuntimeError("x")))["description"]
      and _lang["description"].startswith("Wat je deze week deed: https://mijnagents.globaal.be/week/2026-W40\n"),
      body["description"][:200])
gedaan = []
oud_insert, oud_patch = W._insert, W._patch
W._insert = lambda kal, b, tok: gedaan.append(("insert", kal))
W._patch = lambda a, b, tok: gedaan.append(("patch", a["id"], sorted(b)))
try:
    WC.in_agenda("2026-W40", date(2026, 10, 5), uit, [], tok="t")
    WC.in_agenda("2026-W40", date(2026, 10, 5), uit, [{"id": "e1", "kalender": WC.PRIVE, "_merk": {"agendawacht_week": "2026-W40"}}], tok="t")
    WC.in_agenda("2026-W40", date(2026, 10, 5), uit, [{"id": "e2", "kalender": WC.PRIVE, "_merk": {"agendawacht_week": "2026-W39"}}], tok="t")
finally:
    W._insert, W._patch = oud_insert, oud_patch
check("laag 4: eerste keer een nieuw item, daarna alleen de tekst bijwerken",
      gedaan == [("insert", WC.PRIVE), ("patch", "e1", ["description", "summary"]), ("insert", WC.PRIVE)], str(gedaan))

class Limiet(Exception):
    pass


mis = WC.mislukt_overzicht("2026-W40", Limiet("You have reached your specified workspace API usage limits. "
                                              "You will regain access on 2026-10-01 at 00:00 UTC."))
mb = WC.agenda_body("2026-W40", date(2026, 10, 5), mis)
check("laag 4: een mislukte week komt toch in de agenda, met de volgende stap (Mehdi leest het bord niet)",
      "mislukt" in mb["summary"] and "console.anthropic.com" in mb["description"] and "2026-10-01" in mb["description"]
      and mb["transparency"] == "transparent", mb["summary"])
check("laag 4: een mislukte week zet geen regels voor laag 1", mis["regels_vooraf"] == [])

# ---------- laag 4: de invoer ----------
inv = WC.invoer(datetime(2026, 10, 4, 20, 5), [])
ff = {f["id"]: f for f in inv["register"]["fouten"]}
check("laag 4: de fouten van deze week zijn gemarkeerd", ff["FR-71"]["deze_week"] and not ff["FR-51"]["deze_week"])
check("laag 4: de invoer bevat register, dagcontrole, commits, taken en vaste regels",
      {"register", "zelfcontrole", "kleurherstel", "dagcontrole", "commits", "agenda_taken", "regels_vooraf_vast"} <= set(inv))

# ---------- vastgelegd in de werkwijze ----------
taken = json.loads((HIER / "werkwijze" / "agenda-taken.json").read_text(encoding="utf-8"))
lagen = json.dumps(taken.get("leren_in_lagen", {}), ensure_ascii=False)
check("werkwijze: laag 1 en laag 4 staan in agenda-taken.json", "regels_vooraf.py" in lagen and "weekconsolidatie.py" in lagen)
check("werkwijze: de zondagsronde staat in de dagplanning", "weekconsolidatie.py --ronde" in json.dumps(taken, ensure_ascii=False))

# ---------- laag 4: de weeknood (overleg 27-10-2026: W40 tot W43 mislukten vier weken zonder dat iemand het zag) ----------
BXL = W.TIJDZONE
check("weeknood: de map van de Agendawacht is die van de weekconsolidatie",
      Path(W.WEEKCONSOLIDATIE_MAP) == Path.home() / "appportal/mijnagents-data/export/Agendawacht/weekconsolidatie"
      and Path(W.WEEKCONSOLIDATIE_MAP) == WC.WEEKMAP, W.WEEKCONSOLIDATIE_MAP)
check("weeknood: maandag 06:30 is het anker de zondag ervoor om 20:00 (wintertijd na 25-10)",
      W.weekconsolidatie_anker(datetime(2026, 10, 26, 6, 30, tzinfo=BXL)) == datetime(2026, 10, 25, 20, 0, tzinfo=BXL))
check("weeknood: maandag voor 06:00 telt nog de week ervoor (zomertijd)",
      W.weekconsolidatie_anker(datetime(2026, 10, 26, 5, 59, tzinfo=BXL)) == datetime(2026, 10, 18, 20, 0, tzinfo=BXL))
check("weeknood: zondagavond na 20:00 telt nog het anker van vorige week",
      W.weekconsolidatie_anker(datetime(2026, 10, 25, 21, 0, tzinfo=BXL)) == datetime(2026, 10, 18, 20, 0, tzinfo=BXL))


def _weekmap(d, bestanden):
    for naam, inhoud in bestanden.items():
        (Path(d) / naam).write_text(inhoud if isinstance(inhoud, str) else json.dumps(inhoud), encoding="utf-8")
    return d


MAANDAG = datetime(2026, 10, 26, 6, 30, tzinfo=BXL)
with tempfile.TemporaryDirectory() as d:
    nood = W.weekconsolidatie_noden(os.path.join(d, "bestaat-niet"), MAANDAG)
    check("weeknood: een ontbrekende map geeft de nood, geen crash", nood == [W.WEEKNOOD], str(nood))
    check("weeknood: een lege map geeft de nood", W.weekconsolidatie_noden(d, MAANDAG) == [W.WEEKNOOD])
    tekst = W.WEEKNOOD["tekst"]
    check("weeknood: vaste tekst zonder cijfers en zonder 'stil' (N10; 'stil' belt Mehdi op)",
          not re.search(r"\d", tekst) and "stil" not in tekst.lower() and W.WEEKNOOD["wie"] == "mehdi", tekst)
with tempfile.TemporaryDirectory() as d:
    _weekmap(d, {"2026-W43.json": {"gemaakt": "2026-10-25T19:35:00+00:00"}})
    check("weeknood: een geslaagde run zondag 20:35 (wintertijd) sluit de nood op maandag",
          W.weekconsolidatie_noden(d, MAANDAG) == [])
    check("weeknood: dezelfde run houdt de nood dicht tot de volgende zondag 21:00",
          W.weekconsolidatie_noden(d, datetime(2026, 11, 1, 21, 0, tzinfo=BXL)) == [])
    check("weeknood: maar op maandag 2 november is ze weer open zonder nieuwe run",
          W.weekconsolidatie_noden(d, datetime(2026, 11, 2, 6, 30, tzinfo=BXL)) == [W.WEEKNOOD])
with tempfile.TemporaryDirectory() as d:
    _weekmap(d, {"2026-W43.json": {"gemaakt": "2026-10-25T18:55:00+00:00"}})
    check("weeknood: 18:55 UTC is 19:55 Brussel, voor het anker: telt niet", W.weekconsolidatie_noden(d, MAANDAG) == [W.WEEKNOOD])
with tempfile.TemporaryDirectory() as d:
    _weekmap(d, {"2026-W43-proef.json": {"gemaakt": "2026-10-25T19:35:00+00:00"},
                 "2026-W43.json": {"gemaakt": "2026-10-25T20:35:00"},
                 "2026-W44.json": {"gemaakt": "kapot"},
                 "laatste.json": {"gemaakt": "2026-10-25T19:35:00+00:00", "ok": True}})
    check("weeknood: een proef, een tijd zonder zone, een kapotte tijd en laatste.json tellen nooit als geslaagd",
          W.weekconsolidatie_noden(d, MAANDAG) == [W.WEEKNOOD])
with tempfile.TemporaryDirectory() as d:
    _weekmap(d, {"2026-W44.json": {"gemaakt": "2026-10-28T09:00:00+00:00"}, "2026-W43.json": "{half"})
    check("weeknood: een tijd in de toekomst telt nooit als geslaagd, een half bestand is geen crash",
          W.weekconsolidatie_noden(d, MAANDAG) == [W.WEEKNOOD])
    check("weeknood: een geslaagde herhaling met de hand op dinsdag (weeklabel W44) sluit de nood",
          W.weekconsolidatie_noden(d, datetime(2026, 10, 28, 11, 0, tzinfo=BXL)) == [])
    check("weeknood (Codex fase 1, punt 3): een minuut in de toekomst telt al niet",
          W.weekconsolidatie_noden(d, datetime(2026, 10, 28, 8, 59, tzinfo=timezone.utc)) == [W.WEEKNOOD])
with tempfile.TemporaryDirectory() as d:
    check("weeknood: zonder laatste.json is er geen fout voor het detail", W.weekconsolidatie_fout(d) == "")
    _weekmap(d, {"laatste.json": {"ok": False, "fout": "RuntimeError: antwoord afgekapt (16000 tokens uit)"}})
    check("weeknood: de fout van laatste.json gaat naar het detail", "afgekapt" in W.weekconsolidatie_fout(d))
    _weekmap(d, {"laatste.json": {"ok": True, "fout": ""}})
    check("weeknood: na een geslaagde run geen fout meer in het detail", W.weekconsolidatie_fout(d) == "")

# de weekconsolidatie zelf: een echte run schrijft laatste.json, een proef nooit; een mislukking nooit <week>.json
_patch_w = {"nu_lokaal": W.nu_lokaal, "afspraken": W.afspraken, "archief_afspraken": W.archief_afspraken}
_patch_wc = {"WEEKMAP": WC.WEEKMAP, "REGELS_WEEK": WC.REGELS_WEEK, "sleutel_laden": WC.sleutel_laden,
             "model_oordeel": WC.model_oordeel, "in_agenda": WC.in_agenda, "invoer": WC.invoer}
_patch_ag = {"log": W.ag.log, "log_verstuur": W.ag.log_verstuur}
_argv = sys.argv


def _draai(d, argv, model):
    WC.WEEKMAP, WC.REGELS_WEEK = Path(d) / "weekconsolidatie", Path(d) / "regels-vooraf.json"
    W.nu_lokaal = lambda: datetime(2026, 10, 25, 20, 5, tzinfo=BXL)
    W.afspraken = lambda *a, **k: []
    W.archief_afspraken = lambda *a, **k: []
    WC.invoer = lambda nu, items: {"register": {"fouten": []}, "zelfcontrole": {"niet_bekend": []}, "dagcontrole": [],
                                   "commits": []}
    WC.sleutel_laden = lambda: True
    WC.model_oordeel = model
    WC.in_agenda = lambda *a, **k: "nieuw"
    W.ag.log = lambda *a, **k: None
    W.ag.log_verstuur = lambda *a, **k: None
    sys.argv = ["weekconsolidatie.py"] + argv
    return WC.main()


def _afgekapt(inv):
    raise RuntimeError("antwoord afgekapt (16000 tokens uit)")


def _geslaagd(inv):
    return ANTWOORD, {"model": "nep", "stop_reason": "end_turn", "tokens_in": 1, "tokens_uit": 1}


try:
    with tempfile.TemporaryDirectory() as d:
        rc = _draai(d, ["--ronde"], _afgekapt)
        stand = json.loads((Path(d) / "weekconsolidatie" / "laatste.json").read_text())
        check("weeknood: een mislukte zondagsronde schrijft laatste.json met de fout en geen <week>.json",
              rc == 1 and stand["ok"] is False and "afgekapt" in stand["fout"] and stand["week"] == "2026-W43"
              and datetime.fromisoformat(stand["tijd"]).tzinfo is not None
              and not (Path(d) / "weekconsolidatie" / "2026-W43.json").exists()
              and not (Path(d) / "weekconsolidatie" / "laatste.json.tmp").exists(), str(stand))
        rc = _draai(d, [], _geslaagd)
        stand = json.loads((Path(d) / "weekconsolidatie" / "laatste.json").read_text())
        check("weeknood: de volgende geslaagde run overschrijft de fout",
              rc == 0 and stand["ok"] is True and stand["fout"] == "" and (Path(d) / "weekconsolidatie" / "2026-W43.json").exists(),
              str(stand))
    with tempfile.TemporaryDirectory() as d:
        _draai(d, ["--droog"], _afgekapt)
        _draai(d, ["--droog"], _geslaagd)
        check("weeknood: een proef (--droog) schrijft nooit laatste.json", not (Path(d) / "weekconsolidatie" / "laatste.json").exists())
    _oud_md = WC.markdown
    try:
        with tempfile.TemporaryDirectory() as d:
            WC.markdown = lambda *a, **k: (_ for _ in ()).throw(OSError("schijf vol"))
            rc = _draai(d, ["--ronde"], _geslaagd)
            wm = Path(d) / "weekconsolidatie"
            stand = json.loads((wm / "laatste.json").read_text())
            check("weeknood (Codex fase 1, punt 1): faalt het wegschrijven, dan geen <week>.json, de nood blijft open "
                  "en de week kan opnieuw",
                  rc == 1 and not (wm / "2026-W43.json").exists() and not (wm / "2026-W43.json.tmp").exists()
                  and stand["ok"] is False and "schijf vol" in stand["fout"] and not WC.al_gedaan("2026-W43", wm)
                  and W.weekconsolidatie_noden(str(wm), datetime(2026, 10, 26, 6, 30, tzinfo=BXL)) == [W.WEEKNOOD],
                  str(stand))
    finally:
        WC.markdown = _oud_md
    with tempfile.TemporaryDirectory() as d:
        wm = Path(d) / "weekconsolidatie"
        (wm / "2026-W43.json.tmp").mkdir(parents=True)         # een vroege stap faalt: hier kan geen bestand komen
        (Path(d) / "regels-vooraf.json").write_text('{"week": "2026-W42"}')
        rc = _draai(d, ["--ronde"], _geslaagd)
        check("weeknood (Codex fase 1, ronde 2): faalt een vroege stap, dan blijven de weekregels van vorige week gelden",
              rc == 1 and not (wm / "2026-W43.json").exists()
              and json.loads((Path(d) / "regels-vooraf.json").read_text()) == {"week": "2026-W42"}
              and json.loads((wm / "laatste.json").read_text())["ok"] is False)

    def _vervang_faalt_op(einde):
        echt = WC._vervang

        def vervang(bron, doel):
            if str(doel).endswith(einde):
                raise OSError(f"vervangen mislukt: {einde}")
            echt(bron, doel)
        return vervang

    _oud_vervang = WC._vervang
    try:
        for einde, wat in (("2026-W43.json", "het weekbestand (de allerlaatste stap)"),
                           ("regels-vooraf.json", "de weekregels")):
            for vooraf in ('{"week": "2026-W42"}', None):
                with tempfile.TemporaryDirectory() as d:
                    wm = Path(d) / "weekconsolidatie"
                    if vooraf:
                        (Path(d) / "regels-vooraf.json").write_text(vooraf)
                    WC._vervang = _vervang_faalt_op(einde)
                    rc = _draai(d, ["--ronde"], _geslaagd)
                    WC._vervang = _oud_vervang
                    regels = (Path(d) / "regels-vooraf.json")
                    check(f"weeknood (Codex fase 1, ronde 3): faalt het vervangen van {wat}"
                          f"{' zonder oude regels' if not vooraf else ''}, dan geen geslaagde week, de oude regels, "
                          "de nood open en de week kan opnieuw",
                          rc == 1 and not (wm / "2026-W43.json").exists() and not WC.al_gedaan("2026-W43", wm)
                          and (regels.read_text() == vooraf if vooraf else not regels.exists())
                          and json.loads((wm / "laatste.json").read_text())["ok"] is False
                          and W.weekconsolidatie_noden(str(wm), datetime(2026, 10, 26, 6, 30, tzinfo=BXL)) == [W.WEEKNOOD],
                          regels.read_text() if regels.exists() else "geen regels")
    finally:
        WC._vervang = _oud_vervang
finally:
    for k, v in _patch_w.items():
        setattr(W, k, v)
    for k, v in _patch_wc.items():
        setattr(WC, k, v)
    for k, v in _patch_ag.items():
        setattr(W.ag, k, v)
    sys.argv = _argv

import inspect                      # noqa: E402
# Sinds NA09-rest (01-11-2026, overleg 12) loopt de ronde van de Agendawacht door de gedeelde ronde: main() neemt het
# slot en de ronde, _ronde(rd) is de romp, en de ronde zet de eindhartslag met rd.detail en de noden.
_bron = inspect.getsource(W._ronde)
_i_nood, _i_hart = _bron.find("weekconsolidatie_noden("), _bron.find("rd.detail = ")
check("weeknood: de ronde zet de weeknood voor de eindhartslag, buiten 'if not DAG_ARG'",
      0 < _i_nood < _i_hart and re.search(r"\n {8}weeknood = weekconsolidatie_noden\(\)", _bron) is not None)

# ---------- F8 (overleg 27-10-2026): een dagronde opent noden, sluit ze nooit ----------
# Tot NA09-rest deed noden_voor_hartslag dat (open plus nieuw, of geen lijst); nu zet een dagronde rd.noden_onbekend, en
# dan stuurt de ronde haar noden met nood_sluiten false: wat nieuw is komt erbij, wat open stond blijft open.
check("F8: een dagronde zet noden_onbekend, de volledige ronde niet", "rd.noden_onbekend = bool(DAG_ARG)" in _bron)
_gestuurd = []


def _f8_call(pad, payload=None, method=None):
    _gestuurd.append((pad, payload))
    if pad.endswith("/werkwijze"):
        return {"werkwijze": "# Proef F8\n\nRegel."}
    return [] if pad == "/api/agents" else {}


_oud_call, W.bord.call = W.bord.call, _f8_call
try:
    for _dag, _sluit in ((None, True), ("2026-10-27", False)):
        _gestuurd.clear()
        with W.bord.Agent("proef-f8").ronde("proef") as _rd:
            _rd.noden_onbekend = bool(_dag)
            _rd.nood("TE KRAP: kies welke afspraak schuift", wie="mehdi")
        _laatste = [p for pad, p in _gestuurd if pad == "/agent-status"][-1]
        check(f"F8: {'een dagronde opent de nood en sluit niets' if _dag else 'de volledige ronde stuurt haar eigen lijst'}",
              (_laatste.get("nood_sluiten") is not False) == _sluit
              and _laatste["nood"] == [{"tekst": "TE KRAP: kies welke afspraak schuift", "wie": "mehdi"}], str(_laatste))
finally:
    W.bord.call = _oud_call
_zr = W.zonder_rit_indelen([
    "2026-11-23T16:00 Reistijd: x: mijn rit zonder afspraak weggehaald",
    "2026-11-23T16:00 Reistijd: x: rit zonder afspraak (zonder mijn merk: ik verhuis of haal hem niet weg)",
    "2026-11-24T16:00 Reistijd: y: rit zonder afspraak, niet opgeruimd (1 agenda('s) niet gelezen)",
    "2026-11-25T16:00 Reistijd: z: rit zonder afspraak",
    "2026-12-09T08:30 (privé): adres niet gevonden (Straat 1, 3000 Leuven (achteraan))",
    "2026-09-21T16:00 Werfbezoek: geen adres, geen reistijd"])
check("F8: 'mijn rit zonder afspraak weggehaald' is een geslaagde opruiming, geen nood; de andere ritregels wel",
      len(_zr["rit zonder afspraak"]) == 3 and not any("weggehaald" in r for r in _zr["rit zonder afspraak"]), str(_zr))
check("F8: de andere redenen blijven zoals ze waren",
      len(_zr["adres niet gevonden"]) == 1 and _zr["geen adres in de agenda"] == ["2026-09-21T16:00 Werfbezoek"], str(_zr))

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
