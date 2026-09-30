#!/usr/bin/env python3
"""Laag 4 van het leren (FR-72): de weekconsolidatie van de Agendawacht.

Mehdi, 30-09-2026: "ik begrijp niet waarom je na zoveel tijd nog altijd niet beter wordt". Het register groeide
met een fout per dag, maar niemand keek per week of dezelfde oorzaak in een andere vorm terugkwam, of regels
elkaar gingen tegenspreken, of de regels die Claude voor elke handeling krijgt (laag 1) nog de juiste waren.

Elke zondag om 20:00 Brusselse tijd leest dit script de week na: het foutenregister, de zelfcontrole, het
kleurherstel, de dagcontrole over veertien dagen, de commits aan de agent, agenda-taken.json en de vaste regels
van laag 1. Claude (claude-opus-5-5) maakt daar een weekoverzicht van. Het script:
- schrijft het overzicht naar export/Agendawacht/weekconsolidatie/JJJJ-Www.{json,md} (via de sync in Dropbox,
  Data uit Mehdi/Agendawacht);
- zet per categorie hoogstens twee regels van de week in export/Agendawacht/regels-vooraf.json, die de hook van
  laag 1 op de Mac naast de vaste regels toont (een vaste regel weghalen kan het niet);
- zet het overzicht als hele-dag-item op maandag in de privé-agenda (vrij, zonder melding), want Mehdi leest
  de agenda en niet het bord;
- schrijft een regel in het logboek van het bord.

Het model stelt voor; het past het register, de code en de werkwijze nooit zelf aan. Dat doet een volgende
sessie, met een test, zoals bij elke fout.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/weekconsolidatie.py
          --ronde          alleen zondag 20:xx Brusselse tijd (cron start om 18:05 en 19:05 UTC), een keer per week
          --zonder-model   alleen de invoer verzamelen en tonen, geen API-aanroep, niets schrijven
          --droog          wel het model en de bestanden (met -proef), geen agenda, geen bord, geen regels
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402
import dagcontrole as DC                      # noqa: E402

MODEL = os.environ.get("WEEKCONSOLIDATIE_MODEL", "claude-opus-5-5")
DATA = Path.home() / "appportal/mijnagents-data"
EXPORT = DATA / "export" / "Agendawacht"
WEEKMAP = EXPORT / "weekconsolidatie"
REGELS_WEEK = EXPORT / "regels-vooraf.json"
REGISTER = HIER / "werkwijze" / "foutenregister.json"
TAKEN = HIER / "werkwijze" / "agenda-taken.json"
REGELS_VAST = HIER / "claude-hooks" / "regels.json"
ZELFCONTROLE = DATA / "zelfcontrole.json"
KLEURHERSTEL = DATA / "agenda-kleurherstel.json"
PRIVE = "mehdipriveagena@gmail.com"
UUR = 20
WEEK_MAX = 2

SYSTEEM = """Je bent de weekconsolidatie van de Agendawacht, de agenda-agent van Mehdi Chegini (architect, stuurt een \
groep vennootschappen). Je krijgt de gegevens van de afgelopen week: het foutenregister (fouten, oorzaken, grendels, \
lessen), de zelfcontrole, het kleurherstel, de dagcontrole over veertien dagen, de commits aan de agent, de afspraken \
in agenda-taken.json, de vaste regels die Claude voor elke handeling krijgt (laag 1) en het overzicht van vorige week.

Je kijkt terug en vat samen; je herstelt niets. Wat je voorstelt, voert een volgende Claude-sessie uit, met een test.

Lever:
- overzicht: drie tot vijf zinnen voor Mehdi, gewoon Nederlands, beslissing eerst: hoe de week liep, wat terugkwam, \
wat hij moet beslissen.
- teruggekomen: fouten die deze week terugkwamen, of die dezelfde oorzaak hebben als een oudere fout in een andere \
vorm. Per stuk de fout-ids, wat er gebeurde, waarom de grendel het niet tegenhield en een voorstel. Leeg als er niets \
terugkwam.
- principes: hoogstens vijf lessen die meerdere fouten samenvatten en nog niet als les in het register staan, elk \
met de fout-ids waar ze uit volgen.
- opruimen: regels, controles of teksten die dubbel zijn, elkaar tegenspreken of niet meer kloppen met de code of het \
register, met de vindplaats (bestand en sleutel of id).
- regels_vooraf: per categorie hoogstens twee extra regels voor de komende week, alleen waar deze week er aanleiding \
toe gaf. Kort (hoogstens 200 tekens), als opdracht, met het fout-id erbij. Herhaal geen vaste regel en verzwak er \
nooit een.
- voor_mehdi: hoogstens vijf beslissingen die alleen Mehdi kan nemen, elk met een voorgestelde volgende stap.

Gebruik alleen wat in de invoer staat en noem bij elke bewering het id of de vindplaats; weet je iets niet, laat het \
weg. Schrijf nooit het woord Suriname, gebruik SU. Geen emoji. Wachtwoorden, codes en sleutels noem je nooit."""


def _lijst(eigenschappen):
    return {"type": "array", "items": {"type": "object", "properties": eigenschappen,
                                       "required": list(eigenschappen), "additionalProperties": False}}


_TEKST = {"type": "string"}
_IDS = {"type": "array", "items": {"type": "string"}}
SCHEMA = {
    "type": "object",
    "properties": {
        "overzicht": _TEKST,
        "teruggekomen": _lijst({"ids": _IDS, "wat": _TEKST, "waarom": _TEKST, "voorstel": _TEKST}),
        "principes": _lijst({"les": _TEKST, "uit": _IDS}),
        "opruimen": _lijst({"wat": _TEKST, "waar": _TEKST, "waarom": _TEKST}),
        "regels_vooraf": _lijst({"naam": {"type": "string", "enum": ["agenda", "server", "calendly", "wissen", "mail"]},
                                 "regels": {"type": "array", "items": {"type": "string"}}}),
        "voor_mehdi": _lijst({"vraag": _TEKST, "volgende_stap": _TEKST}),
    },
    "required": ["overzicht", "teruggekomen", "principes", "opruimen", "regels_vooraf", "voor_mehdi"],
    "additionalProperties": False,
}


class Weigering(RuntimeError):
    pass


def _lees(pad):
    try:
        return json.loads(Path(pad).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def weeknaam(nu):
    j, w, _ = nu.isocalendar()
    return f"{j}-W{w:02d}"


def maandag_na(nu):
    return nu.date() + timedelta(days=(7 - nu.weekday()) % 7 or 7)


def is_consolidatietijd(nu):
    return nu.weekday() == 6 and nu.hour == UUR


def al_gedaan(week, map_=None):
    """Een ronde draait een keer per week; een proef of een run met de hand telt niet mee."""
    return bool(_lees((map_ or WEEKMAP) / f"{week}.json").get("ronde"))


def sleutel_laden():
    """ANTHROPIC_API_KEY uit ~/appportal/.env of ~/agents/.env. De waarde komt nooit in een log of bestand."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return True
    for pad in (Path.home() / "appportal/.env", Path.home() / "agents/.env"):
        try:
            regels = pad.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for regel in regels:
            k, _, v = regel.partition("=")
            if k.strip().removeprefix("export ").strip() == "ANTHROPIC_API_KEY" and v.strip():
                os.environ["ANTHROPIC_API_KEY"] = v.strip().strip('"').strip("'")
                return True
    return False


def _datum(s):
    try:
        return datetime.strptime(s or "", "%d-%m-%Y").date()
    except ValueError:
        return None


def invoer(nu, items):
    """Alles wat het model ziet, compact. Pure functie op de bestanden en de items (test zonder netwerk)."""
    begin = nu.date() - timedelta(days=7)
    reg = _lees(REGISTER)
    fouten = []
    for f in reg.get("fouten") or []:
        d = _datum(f.get("datum"))
        nieuw = bool(d and d >= begin)
        fouten.append({"id": f.get("id"), "datum": f.get("datum"), "status": f.get("status"), "deze_week": nieuw,
                       "fout": (f.get("fout") or "") if nieuw else (f.get("fout") or "")[:300],
                       "oorzaak": (f.get("oorzaak") or "")[:400], "soort_oorzaak": f.get("soort_oorzaak", ""),
                       "oplossing": (f.get("oplossing") or "") if nieuw else (f.get("oplossing") or "")[:200],
                       "grendel": (f.get("grendel") or {}).get("waar", ""), "controle": f.get("controle") or []})
    zc = _lees(ZELFCONTROLE)
    bekend = {}
    for b in zc.get("bevindingen") or []:
        if b.get("staat") == "BEKEND":
            bekend[b.get("controle")] = bekend.get(b.get("controle"), 0) + 1
    kh = _lees(KLEURHERSTEL)
    kh = [r for r in (kh if isinstance(kh, list) else []) if (r.get("tijd") or "")[:10] >= begin.isoformat()]
    per_dag = {}
    for r in kh:
        t = per_dag.setdefault(r["tijd"][:10], {"teruggezet": 0, "nieuw": 0, "mislukt": 0})
        for k in t:
            t[k] += int(r.get(k) or 0)
    dagen = [(nu.date() + timedelta(days=i)).isoformat() for i in range(-7, 8)]
    dagbev = [{"dag": d, "soort": b["soort"], "tekst": b["tekst"][:200]} for d in dagen for b in DC.dagcontrole(items, d)]
    try:
        commits = subprocess.run(["git", "-C", str(HIER), "log", "--since=8 days ago", "--date=short",
                                  "--pretty=format:%h %ad %s", "--", "."], capture_output=True, text=True,
                                 timeout=30).stdout.splitlines()
    except (OSError, subprocess.SubprocessError):
        commits = []
    vorige = _lees(WEEKMAP / f"{weeknaam(nu - timedelta(days=7))}.json")
    return {
        "week": weeknaam(nu), "van": begin.isoformat(), "tot": nu.date().isoformat(),
        "register": {"versie": reg.get("versie"), "lessen": reg.get("lessen") or [], "fouten": fouten},
        "zelfcontrole": {"tijd": zc.get("tijd"),
                         "niet_bekend": [b for b in zc.get("bevindingen") or [] if b.get("staat") != "BEKEND"][:60],
                         "bekend_per_controle": bekend, "geschiedenis": (zc.get("geschiedenis") or [])[-8:]},
        "kleurherstel": {"per_dag": per_dag,
                         "voorbeelden": [v for r in kh[-3:] for v in (r.get("voorbeelden") or [])[:4]]},
        "dagcontrole": dagbev,
        "commits": commits[:80],
        "agenda_taken": _lees(TAKEN),
        "regels_vooraf_vast": [{"naam": c.get("naam"), "regels": c.get("regels")}
                               for c in _lees(REGELS_VAST).get("categorieen") or []],
        "vorige_week": {k: vorige.get(k) for k in ("overzicht", "teruggekomen", "opruimen", "voor_mehdi")} if vorige else {},
    }


def model_oordeel(inv, client=None):
    """Een aanroep, gestructureerd antwoord (json_schema). Een weigering of een afgekapt antwoord is een gewoon
    antwoord met status 200: dat vangen we apart op, anders lijkt een leeg overzicht een rustige week."""
    if client is None:
        from anthropic import Anthropic
        client = Anthropic()
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        system=SYSTEEM,
        messages=[{"role": "user", "content": json.dumps(inv, ensure_ascii=False)}],
        timeout=900)
    meta = {"model": getattr(resp, "model", MODEL), "stop_reason": getattr(resp, "stop_reason", ""),
            "tokens_in": getattr(getattr(resp, "usage", None), "input_tokens", 0) or 0,
            "tokens_uit": getattr(getattr(resp, "usage", None), "output_tokens", 0) or 0}
    if meta["stop_reason"] == "refusal":
        raise Weigering(f"model weigerde ({meta['tokens_in']} tokens in)")
    if meta["stop_reason"] == "max_tokens":
        raise RuntimeError(f"antwoord afgekapt ({meta['tokens_uit']} tokens uit)")
    tekst = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    return json.loads(tekst), meta


def _s(t, n):
    t = re.sub(r"(?i)surinam\w*", "SU", re.sub(r"\s+", " ", str(t or ""))).strip()
    return t[:n]


def schoon(uit, vast=None):
    """Knipt het antwoord op maat: hoogstens vijf per lijst, korte teksten, 'SU' in plaats van het land, en per
    categorie hoogstens twee weekregels die geen herhaling zijn van een vaste regel."""
    vast = vast if vast is not None else (_lees(REGELS_VAST).get("categorieen") or [])
    vaste_regels = {c.get("naam"): {_s(r, 400).lower() for r in c.get("regels") or []} for c in vast}
    regels = []
    for c in uit.get("regels_vooraf") or []:
        naam = c.get("naam")
        if naam not in vaste_regels or any(r["naam"] == naam for r in regels):
            continue
        rr = [_s(r, 240) for r in c.get("regels") or [] if _s(r, 240) and _s(r, 400).lower() not in vaste_regels[naam]]
        if rr:
            regels.append({"naam": naam, "regels": rr[:WEEK_MAX]})
    return {
        "overzicht": _s(uit.get("overzicht"), 1500),
        "teruggekomen": [{"ids": [_s(i, 12) for i in x.get("ids") or []][:8], "wat": _s(x.get("wat"), 400),
                          "waarom": _s(x.get("waarom"), 400), "voorstel": _s(x.get("voorstel"), 400)}
                         for x in (uit.get("teruggekomen") or [])[:5]],
        "principes": [{"les": _s(x.get("les"), 400), "uit": [_s(i, 12) for i in x.get("uit") or []][:8]}
                      for x in (uit.get("principes") or [])[:5]],
        "opruimen": [{"wat": _s(x.get("wat"), 400), "waar": _s(x.get("waar"), 200), "waarom": _s(x.get("waarom"), 400)}
                     for x in (uit.get("opruimen") or [])[:5]],
        "regels_vooraf": regels,
        "voor_mehdi": [{"vraag": _s(x.get("vraag"), 400), "volgende_stap": _s(x.get("volgende_stap"), 300)}
                       for x in (uit.get("voor_mehdi") or [])[:5]],
    }


def markdown(week, uit, meta):
    r = [f"# Agendawacht weekoverzicht {week}", "", uit["overzicht"], ""]
    for kop, sleutel, fmt in (
            ("Voor Mehdi", "voor_mehdi", lambda x: f"- {x['vraag']} Volgende stap: {x['volgende_stap']}"),
            ("Teruggekomen", "teruggekomen", lambda x: f"- {', '.join(x['ids'])}: {x['wat']} Waarom: {x['waarom']} Voorstel: {x['voorstel']}"),
            ("Principes", "principes", lambda x: f"- {x['les']} ({', '.join(x['uit'])})"),
            ("Opruimen", "opruimen", lambda x: f"- {x['wat']} ({x['waar']}): {x['waarom']}"),
            ("Regels van de week (laag 1)", "regels_vooraf", lambda x: f"- {x['naam']}: " + " | ".join(x["regels"]))):
        r += [f"## {kop}", ""] + ([fmt(x) for x in uit[sleutel]] or ["- niets"]) + [""]
    r.append(f"Gemaakt door {meta.get('model')} ({meta.get('tokens_in')} tokens in, {meta.get('tokens_uit')} uit). "
             "Voorstellen; register, code en werkwijze past een volgende sessie aan, met een test.")
    return "\n".join(r) + "\n"


def schrijf(week, uit, meta, ronde, proef=False, nu_utc=None):
    nu_utc = nu_utc or datetime.now(timezone.utc)
    WEEKMAP.mkdir(parents=True, exist_ok=True)
    naam = f"{week}-proef" if proef else week
    (WEEKMAP / f"{naam}.json").write_text(json.dumps({"week": week, "gemaakt": nu_utc.isoformat(timespec="seconds"),
                                                      "ronde": ronde, "model": meta, **uit},
                                                     ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (WEEKMAP / f"{naam}.md").write_text(markdown(week, uit, meta), encoding="utf-8")
    if not proef:
        REGELS_WEEK.write_text(json.dumps({"week": week, "gemaakt": nu_utc.isoformat(timespec="seconds"),
                                           "bron": f"weekconsolidatie/{week}.json",
                                           "categorieen": uit["regels_vooraf"]}, ensure_ascii=False, indent=1) + "\n",
                               encoding="utf-8")


def mislukt_overzicht(week, fout):
    """Wat Mehdi maandag in de agenda ziet als het model niet bereikbaar was: hij leest het bord niet, dus een
    mislukte week mag niet stil voorbijgaan (gezien 30-09-2026: de maandlimiet van de API was bereikt)."""
    tekst = str(fout)
    m = re.search(r"regain access on (\d{4}-\d{2}-\d{2}) at (\d{2}:\d{2}) UTC", tekst)
    if "usage limit" in tekst:
        vraag = ("De gebruikslimiet van de Claude-API is bereikt" + (f" (weer open op {m.group(1)} om {m.group(2)} UTC)" if m else "")
                 + "; alle agents die de API gebruiken liggen dan stil, niet alleen deze.")
        stap = ("Verhoog de limiet in console.anthropic.com (Settings, Limits); daarna draait Claude de weekconsolidatie "
                "met de hand opnieuw.")
    else:
        vraag = f"De weekconsolidatie liep niet ({type(fout).__name__})."
        stap = "Claude kijkt ~/agents/weekconsolidatie.log na, lost het op in de bron en draait ze opnieuw."
    return {"mislukt": True, "overzicht": f"De weekconsolidatie van {week} liep niet; er is deze week geen overzicht.",
            "teruggekomen": [], "principes": [], "opruimen": [], "regels_vooraf": [],
            "voor_mehdi": [{"vraag": vraag, "volgende_stap": stap}]}


def agenda_body(week, maandag, uit):
    """Hele dag op maandag, op de privé-agenda. Vrij (transparent), zodat het nooit een Calendly-slot of een
    rit blokkeert (FR-57), en zonder melding."""
    oms = [uit["overzicht"], ""]
    if uit["voor_mehdi"]:
        oms += ["Voor jou:"] + [f"- {x['vraag']} Volgende stap: {x['volgende_stap']}" for x in uit["voor_mehdi"]] + [""]
    if uit["teruggekomen"]:
        oms += ["Teruggekomen:"] + [f"- {', '.join(x['ids'])}: {x['wat']}" for x in uit["teruggekomen"]] + [""]
    oms.append(f"Volledig overzicht: Data uit Mehdi/Agendawacht/weekconsolidatie/{week}.md")
    titel = (f"Agendawacht weekoverzicht {week} mislukt: actie voor jou" if uit.get("mislukt") else
             f"Agendawacht weekoverzicht {week}: {len(uit['teruggekomen'])} teruggekomen, {len(uit['voor_mehdi'])} voor jou")
    return {"summary": titel,
            "description": "\n".join(oms)[:7500],
            "start": {"date": maandag.isoformat()}, "end": {"date": (maandag + timedelta(days=1)).isoformat()},
            "transparency": "transparent",
            "reminders": {"useDefault": False, "overrides": []},
            "extendedProperties": {"private": {"agendawacht_week": week}}}


def in_agenda(week, maandag, uit, items, tok=None):
    """Een keer per week: staat het item met dit weeknummer er al, dan werkt het de tekst bij."""
    body = agenda_body(week, maandag, uit)
    tok = tok or W.agenda._toegang()
    er = [a for a in items if a.get("kalender") == PRIVE and (a.get("_merk") or {}).get("agendawacht_week") == week]
    if er:
        W._patch(er[0], {"summary": body["summary"], "description": body["description"]}, tok)
        return "bijgewerkt"
    W._insert(PRIVE, body, tok)
    return "nieuw"


def main():
    nu = W.nu_lokaal()
    week = weeknaam(nu)
    ronde = "--ronde" in sys.argv
    droog = "--droog" in sys.argv
    if ronde and (not is_consolidatietijd(nu) or al_gedaan(week)):
        return 0
    items = [a for a in W.afspraken(-8, 9) if not a.get("fout")] + W.archief_afspraken(-8, 9)
    inv = invoer(nu, items)
    print(f"=== {nu:%Y-%m-%d %H:%M} Brussel · weekconsolidatie {week}: "
          f"{sum(f['deze_week'] for f in inv['register']['fouten'])} fouten deze week, "
          f"{len(inv['zelfcontrole']['niet_bekend'])} zelfcontrole niet bekend, {len(inv['dagcontrole'])} dagcontrole, "
          f"{len(inv['commits'])} commits, invoer {len(json.dumps(inv, ensure_ascii=False)) // 1000} kB")
    if "--zonder-model" in sys.argv:
        return 0
    if not sleutel_laden():
        print("geen ANTHROPIC_API_KEY in ~/appportal/.env of ~/agents/.env", file=sys.stderr)
        return 1
    try:
        ruw, meta = model_oordeel(inv)
    except Exception as e:  # noqa: BLE001
        print(f"weekconsolidatie mislukt: {type(e).__name__}: {e}", file=sys.stderr)
        if not droog:
            W.ag.log(f"week {week}", "fout", f"weekconsolidatie {week} mislukt: {type(e).__name__}", str(e)[:500])
            W.ag.log_verstuur()
            try:
                hoe = in_agenda(week, maandag_na(nu), mislukt_overzicht(week, e), items)
                print(f"  agenda: {hoe} op maandag {maandag_na(nu).isoformat()}: mislukt, met de volgende stap")
            except Exception as e2:  # noqa: BLE001
                print(f"  agenda mislukt: {type(e2).__name__}: {e2}", file=sys.stderr)
        return 1
    uit = schoon(ruw)
    schrijf(week, uit, meta, ronde, proef=droog)
    print(markdown(week, uit, meta))
    if droog:
        return 0
    try:
        hoe = in_agenda(week, maandag_na(nu), uit, items)
        print(f"  agenda: {hoe} op maandag {maandag_na(nu).isoformat()} (privé, hele dag, vrij)")
    except Exception as e:  # noqa: BLE001
        print(f"  agenda mislukt: {type(e).__name__}: {e}", file=sys.stderr)
    W.ag.log(f"week {week}", "bevinding",
             f"weekconsolidatie {week}: {len(uit['teruggekomen'])} teruggekomen, {len(uit['voor_mehdi'])} voor Mehdi",
             markdown(week, uit, meta)[:6000])
    W.ag.log_verstuur()
    return 0


if __name__ == "__main__":
    sys.exit(main())
