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

print(f"\n{ok} goed, {fout} fout")
sys.exit(1 if fout else 0)
