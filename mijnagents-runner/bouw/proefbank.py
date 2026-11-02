#!/usr/bin/env python3
"""Proefbank van de afdeling Bouw: laat De Aannemerszoeker of De Offertevergelijker een reeks vragen afwerken zoals op de
server (zelfde code, zelfde bronnen, zelfde abonnement), maar schrijft niets op het bord. Elke schrijfopdracht naar het
bord (hartslag, klaarzet, logboek, nood, kennis, opgepakt) komt in een eigen proefmap; alleen lezen (de werkwijze, de
collega's) gaat naar het bord. Testagents werken nooit op echte data (les 24-09-2026).

    python3 -m bouw.proefbank draai aannemerszoeker docs/bouw/proeven/aannemerszoeker.json ~/proeven-bouw/2026-11-02
    python3 -m bouw.proefbank verken HA 2145          lotmappen van een project en hun PDF's (alleen lezen)

Draai met ~/agents/.venv/bin/python (zoals De Regisseur): met een andere Python ontbreekt pypdf. Referentiebedragen uit de
PDF's staan buiten de repo in ~/proeven-bouw/referentie.json (PROEF_REFERENTIE), {proef-id: [bedrag, ...]}.
Per proef: <id>.json (wat de agent zou schrijven, de Claude-vragen en de keuring) en <id>.md (het verslag), plus
uitslag.md met de keuring van alle proeven. De proefmap ligt buiten de repo: het verslag kan echte gegevens bevatten.
"""
import contextlib
import io
import json
import os
import re
import sys
import time

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
sys.path.insert(0, HIER)
import bord  # noqa: E402
import claude_abonnement  # noqa: E402

from . import scheiding as S  # noqa: E402
from . import vraag as Q  # noqa: E402

# Wat ook buiten de grendel van de code nooit in een verslag voor de ene firma mag staan: een tweede, eenvoudige toets
# naast scheiding.kruis, zodat een fout in de grendel zelf ook opvalt.
MAX_CLAUDE = 14
ANDERE_WOORDEN = {S.HA: ("harmonie", "harmoniebouw"), S.HB: ("h-architects", "h architects", "harchitects")}


class Opname:
    """Vangt elke schrijfopdracht naar het bord op; lezen gaat door naar het echte bord."""

    def __init__(self, echt):
        self.echt = echt
        self.schrijf = []

    def call(self, pad, payload=None, method=None):
        soort = method or ("POST" if payload is not None else "GET")
        if soort != "GET":
            self.schrijf.append({"pad": pad, "soort": soort, "payload": payload})
            if pad == "/api/klaarzet":
                return {"nieuw": len((payload or {}).get("items") or []), "bestaand": 0}
            return {}
        return self.echt(pad, payload, method)


class Teller:
    """Telt de vragen aan Claude op het abonnement en bewaart wat terugkwam (tokens, beurten), zonder de vraag zelf."""

    def __init__(self, echt):
        self.echt = echt
        self.vragen = []
        self.verboden = []          # wat in een proef nooit naar Claude mag (bv. de straat van een project)
        self.verboden_gezien = []
        self.vast = None            # een vast modelantwoord voor deze proef, of None: dan echt Claude
        self.totaal = 0
        self.antwoorden = []

    def vraag(self, *args, **kw):
        begin = time.monotonic()
        self.totaal += 1
        if self.totaal > MAX_CLAUDE:
            # Claude K4 (overleg 28): een proefreeks vraagt Claude hoogstens zoveel keer
            raise claude_abonnement.Fout(f"proefbank: meer dan {MAX_CLAUDE} vragen aan Claude in een reeks", "limiet")
        tekst = " ".join(str(a) for a in args) + " " + " ".join(str(x) for x in kw.values())
        self.verboden_gezien += [w for w in self.verboden if w.lower() in tekst.lower()]
        if self.vast is not None:
            # Codex X2 (overleg 28): een vast antwoord van het model, zodat de keuring van de code zelf getoetst wordt
            # met kandidaten die er nooit door mogen (de andere firma, een gestopte firma, een site zonder nummer)
            urls = [u for f in self.vast.get("firmas") or [] for u in [f.get("url")] + list(f.get("paginas") or []) if u]
            self.vragen.append({"tools": list(kw.get("tools") or ()), "vast": True, "tokens": 0, "beurten": 0, "duur": 0})
            return {"tekst": "```json\n" + json.dumps(self.vast, ensure_ascii=False) + "\n```", "tokens": 0,
                    "gereedschap": [("WebFetch", {"url": u}) for u in urls], "stop": "vast antwoord (proef)",
                    "model": "vast antwoord (proef)", "beurten": 0}
        try:
            uit = self.echt(*args, **kw)
        except claude_abonnement.Fout as e:
            self.vragen.append({"tools": list(kw.get("tools") or ()), "fout": str(e)[:300], "soort": e.soort,
                                "duur": round(time.monotonic() - begin, 1)})
            raise
        stuk = uit if isinstance(uit, dict) else {}
        self.antwoorden.append(str(stuk.get("tekst") or "")[-20000:])
        self.vragen.append({"tools": list(kw.get("tools") or ()), "tokens": stuk.get("tokens"),
                            "beurten": stuk.get("beurten"), "model": stuk.get("model"),
                            "duur": round(time.monotonic() - begin, 1)})
        return uit


def zetel_gemeente(firma, psql=None):
    """Postcode en gemeente van de zetel van een firma uit kern, zodat de proeven geen adres in de repo zetten."""
    import re
    if psql is None:
        import organisatie
        psql = organisatie._psql
    code = {S.HA: "HARC", S.HB: "HARM"}[firma]
    rijen = psql("select json_agg(json_build_object('weergave', coalesce(a.weergave, ''))) from kern.firma f "
                 f"left join kern.adres a on a.id = f.adres_id where f.code = '{code}'") or []
    m = re.search(r"\b(\d{4})\s+([^,]+)$", (rijen[0].get("weergave") if rijen else "") or "")
    if not m:
        raise SystemExit(f"geen zetel in kern voor {S.FIRMANAMEN[firma]}")
    return f"{m.group(1)} {m.group(2).strip()}"


def vul_in(vraag):
    """{zetel:HA} en {zetel:HB} worden de gemeente van die zetel uit kern."""
    for firma in (S.HA, S.HB):
        if f"{{zetel:{firma}}}" in vraag:
            vraag = vraag.replace(f"{{zetel:{firma}}}", zetel_gemeente(firma))
    return vraag


def project_straat(vraag):
    """De straat van het project in de vraag (H-Architects), om na te gaan dat ze nooit naar Claude gaat."""
    v = Q.ontleed(vraag)
    if v.get("firma") != S.HA or not v.get("project"):
        return []
    import projectadressen
    adres = projectadressen.adres(v["project"]) or ""
    straat = adres.split(",", 1)[0].strip()
    return [straat.rsplit(" ", 1)[0] if any(c.isdigit() for c in straat) else straat] if straat else []


def laad_agent(naam):
    if naam not in ("aannemerszoeker", "offertevergelijker"):
        raise SystemExit(f"onbekende agent: {naam}")
    import importlib
    return importlib.import_module(naam)


def items(opname):
    uit = []
    for s in opname.schrijf:
        if s["pad"] == "/api/klaarzet":
            uit += (s["payload"] or {}).get("items") or []
    return uit


def logregels(opname):
    uit = []
    for s in opname.schrijf:
        if s["pad"] == "/api/logboek":
            uit += (s["payload"] or {}).get("regels") or []
    return uit


def laatste_hartslag(opname):
    for s in reversed(opname.schrijf):
        if s["pad"] == "/agent-status":
            return s["payload"] or {}
    return {}


def keur(proef, uitslag):
    """[(toets, goed, toelichting)] Algemene toetsen voor elke proef en de verwachtingen uit de proef zelf."""
    v = proef.get("verwacht") or {}
    firma = Q.ontleed(proef["vraag"]).get("firma")
    verslagen = uitslag["items"]
    tekst = "\n".join(f"{i.get('titel', '')}\n{i.get('inhoud', '')}" for i in verslagen)
    laag = tekst.lower()
    uit = [("geen fout in de agent", not uitslag["fout"], uitslag["fout"] or ""),
           ("precies een verslag voor Mehdi", len(verslagen) == 1 and verslagen[0].get("voor") == "mehdi",
            f"{len(verslagen)} verslagen")]
    if firma:
        kruis = S.kruis(tekst, firma)
        uit.append(("geen kenmerk van de andere firma (grendel)", not kruis, ", ".join(map(str, kruis))[:200]))
        woorden = [w for w in ANDERE_WOORDEN[firma] if w in laag]
        uit.append(("geen naam van de andere firma (tweede toets)", not woorden, ", ".join(woorden)))
    if "claude" in v:
        n = len(uitslag["claude"])
        uit.append(("Claude gevraagd" if v["claude"] else "Claude niet gevraagd", bool(n) == bool(v["claude"]),
                    f"{n} vragen aan Claude"))
    for stuk in v.get("titel_bevat") or []:
        titel = verslagen[0].get("titel", "") if verslagen else ""
        uit.append((f"titel noemt '{stuk}'", stuk.lower() in titel.lower(), titel[:120]))
    for stuk in (proef.get("referentie") or []):
        uit.append((f"verslag noemt referentie '{stuk}'", stuk.lower() in laag, "uit de PDF nagerekend, buiten de repo"))
    if "letters" in v:
        sleutel = tekst.split("## Welke offerte is welke letter", 1)[-1] if "## Welke offerte" in tekst else ""
        n = sum(1 for regel in sleutel.splitlines() if regel.startswith("- Inschrijver "))
        uit.append((f"precies {v['letters']} bestanden met een letter", n == v["letters"], f"{n} met een letter"))
    for stuk in v.get("bevat") or []:
        uit.append((f"verslag noemt '{stuk}'", stuk.lower() in laag, ""))
    for stuk in v.get("niet") or []:
        uit.append((f"verslag noemt '{stuk}' niet", stuk.lower() not in laag, ""))
    if "klaar_min" in v or "klaar_max" in v:
        n = uitslag.get("klaar")
        goed = n is not None and n >= v.get("klaar_min", 0) and n <= v.get("klaar_max", 10 ** 6)
        uit.append((f"firma's klaar tussen {v.get('klaar_min', 0)} en {v.get('klaar_max', '...')}", goed, f"{n} klaar"))
    if "weggelaten_min" in v:
        n = uitslag.get("weggelaten")
        uit.append((f"minstens {v['weggelaten_min']} kandidaten weggelaten", n is not None and n >= v["weggelaten_min"],
                    f"{n} weggelaten"))
    if v.get("klaar_binnen_straal"):
        straal = Q.ontleed(proef["vraag"]).get("straal")
        klaar = tekst.split("## Klaar om aan te schrijven", 1)[1].split("\n## ", 1)[0] if "## Klaar om" in tekst else ""
        km = [float(x) for x in re.findall(r"\((\d+(?:\.\d+)?) km\)", klaar)]
        regels = [r for r in klaar.splitlines() if re.match(r"\d+\. \[", r)]
        uit.append((f"elke firma onder klaar ligt binnen {straal} km van de KBO-zetel",
                    len(km) == len(regels) and all(k <= straal for k in km), f"{km}"))
    if "noden_max" in v:
        n = len(uitslag["noden"])
        uit.append((f"hoogstens {v['noden_max']} noden", n <= v["noden_max"], "; ".join(x["tekst"] for x in uitslag["noden"])))
    if v.get("adres_niet_naar_claude"):
        uit.append(("straat van het project niet naar Claude", bool(uitslag["verboden"]) and not uitslag["verboden_gezien"],
                    "geen straat gevonden om te toetsen" if not uitslag["verboden"] else
                    ("gezien in een vraag aan Claude" if uitslag["verboden_gezien"] else "")))
    if "duur_max" in v:
        uit.append((f"klaar binnen {v['duur_max']} s", uitslag["duur"] <= v["duur_max"], f"{uitslag['duur']} s"))
    return uit


def uit_log(regels, woord):
    """Het aantal voor 'klaar' of 'weggelaten' uit de beslissingsregel van De Aannemerszoeker, of None."""
    for r in regels:
        m = re.search(rf"(\d+) {woord}\b", r.get("tekst") or "")
        if m and "na te kijken" in (r.get("tekst") or ""):
            return int(m.group(1))
    return None


def draai_proef(mod, proef, opname, teller):
    opname.schrijf.clear()
    teller.vragen.clear()
    teller.verboden_gezien.clear()
    teller.antwoorden.clear()
    proef = dict(proef, vraag=vul_in(proef["vraag"]))
    teller.verboden = project_straat(proef["vraag"]) if (proef.get("verwacht") or {}).get("adres_niet_naar_claude") else []
    teller.vast = proef.get("model")
    begin = time.monotonic()
    scherm, fout = io.StringIO(), ""
    with contextlib.redirect_stdout(scherm):
        try:
            with mod.ag.ronde(f"proef {proef['id']}") as r:
                if mod.NAAM == "aannemerszoeker":
                    mod.werk(r, proef["vraag"], False, begin)
                else:
                    mod.werk(r, proef["vraag"], False)
        except Exception as e:  # noqa: BLE001  een proef die breekt is een uitslag, geen einde van de proefbank
            fout = f"{type(e).__name__}: {str(e)[:300]}"
    regels = logregels(opname)
    hart = laatste_hartslag(opname)
    uitslag = {"id": proef["id"], "vraag": proef["vraag"], "doel": proef.get("doel", ""),
               "duur": round(time.monotonic() - begin, 1), "fout": fout, "items": items(opname),
               "claude": list(teller.vragen), "noden": hart.get("nood") or [], "status": hart.get("status"),
               "detail": hart.get("detail"), "logboek": regels, "klaar": uit_log(regels, "klaar"), "weggelaten": uit_log(regels, "weggelaten"),
               "verboden": list(teller.verboden), "verboden_gezien": list(teller.verboden_gezien),
               # wat het model teruggaf (zonder de vraag): bouwstof voor een volgende proef met een vast antwoord
               "model_antwoord": list(teller.antwoorden),
               "scherm": scherm.getvalue()[-4000:]}
    uitslag["keuring"] = [{"toets": t, "goed": g, "toelichting": x} for t, g, x in keur(proef, uitslag)]
    uitslag["geslaagd"] = all(k["goed"] for k in uitslag["keuring"])
    return uitslag


def afschermen():
    """Codex X4 (overleg 28): ook een rechtstreekse aanroep naar het bord (niet via bord.call) mag alleen lezen."""
    import urllib.parse
    import urllib.request
    echt = urllib.request.urlopen
    bordhost = urllib.parse.urlsplit(bord.PLATFORM).netloc

    def urlopen(req, *args, **kw):
        if isinstance(req, urllib.request.Request):
            url, methode = req.full_url, req.get_method()
        else:   # Codex 29: ook een gewone URL met data is een POST
            data = args[0] if args else kw.get("data")
            url, methode = str(req), ("POST" if data is not None else "GET")
        if urllib.parse.urlsplit(url).netloc == bordhost and methode != "GET":
            raise PermissionError(f"proefbank: {methode} naar het bord geweigerd")
        return echt(req, *args, **kw)
    urllib.request.urlopen = urlopen


def draai(agent, proeven_pad, uitmap, alleen=None, referentie=None):
    import importlib.util
    if importlib.util.find_spec("pypdf") is None:
        raise SystemExit("pypdf ontbreekt: draai de proefbank met ~/agents/.venv/bin/python, zoals De Regisseur")
    repo = os.path.dirname(HIER)
    if os.path.abspath(uitmap).startswith(repo + os.sep):
        raise SystemExit("de proefmap ligt in de repo: het verslag kan echte gegevens bevatten; kies een map erbuiten")
    afschermen()
    mod = laad_agent(agent)
    opname = Opname(bord.call)
    bord.call = opname.call                      # vanaf hier bereikt geen schrijfopdracht het bord
    teller = Teller(claude_abonnement.vraag)
    claude_abonnement.vraag = teller.vraag
    with open(proeven_pad, encoding="utf-8") as f:
        proeven = json.load(f)["proeven"]
    # Referentiebedragen uit de PDF's staan buiten de (openbare) repo: {proef-id: ["2.069,35", ...]}
    ref = {}
    if referentie and os.path.isfile(referentie):
        with open(referentie, encoding="utf-8") as f:
            ref = json.load(f)
    proeven = [dict(p, referentie=ref.get(p["id"]) or []) for p in proeven]
    os.makedirs(uitmap, exist_ok=True)
    alle = []
    for proef in proeven:
        if alleen and proef["id"] not in alleen:
            continue
        print(f"proef {proef['id']}: {proef.get('doel', '')}", flush=True)
        u = draai_proef(mod, proef, opname, teller)
        with open(os.path.join(uitmap, f"{proef['id']}.json"), "w", encoding="utf-8") as f:
            json.dump(u, f, ensure_ascii=False, indent=1)
        with open(os.path.join(uitmap, f"{proef['id']}.md"), "w", encoding="utf-8") as f:
            for it in u["items"]:
                f.write(f"# {it.get('titel', '')}\n\n{it.get('inhoud', '')}\n")
        for k in u["keuring"]:
            print(f"   {'goed' if k['goed'] else 'FOUT'}  {k['toets']}  {k['toelichting'][:100]}", flush=True)
        print(f"   {u['duur']} s, {len(u['claude'])} Claude-vragen, {'GESLAAGD' if u['geslaagd'] else 'NIET GESLAAGD'}",
              flush=True)
        alle.append(u)
    with open(os.path.join(uitmap, "uitslag.md"), "w", encoding="utf-8") as f:
        f.write(f"# Proefbank {agent}\n\n{sum(u['geslaagd'] for u in alle)} van {len(alle)} geslaagd\n\n")
        for u in alle:
            f.write(f"## {u['id']} {'geslaagd' if u['geslaagd'] else 'NIET geslaagd'} ({u['duur']} s, "
                    f"{len(u['claude'])} Claude-vragen)\n{u['doel']}\n\n")
            for k in u["keuring"]:
                f.write(f"- {'goed' if k['goed'] else 'FOUT'}: {k['toets']} {k['toelichting'][:160]}\n")
            f.write("\n")
    return alle


def verken(firma, project):
    """De lotmappen van een project met het aantal PDF's en fiches; leest alleen."""
    import bronnen
    from . import mappen as MP
    from . import offertes as F
    firma = Q.firma_uit(firma)
    pad, lots = MP.offertemap({"firma": firma, "project": project}, bronnen.lijst, MP.projectmap)
    for lot in lots:
        b = MP.offertebestanden(lot, bronnen.lijst)
        fiches = sum(1 for x in b if F.fiche_naam(x["naam"]))
        print(f"{lot.rsplit('/', 1)[-1]}: {len(b)} PDF's, {fiches} fiches volgens de naam")


def naloop(firma, project, lot):
    """Voor de hercontrole met de hand: per PDF van een lot (ook een submap diep) de regels met een totaal of een
    bedrag, zoals pypdf ze leest. Leest alleen; de uitvoer komt alleen op het scherm."""
    import re
    import bronnen
    from . import mappen as MP
    from . import offertes as F
    firma = Q.firma_uit(firma)
    pad, lots = MP.offertemap({"firma": firma, "project": project, "lot": lot}, bronnen.lijst, MP.projectmap)
    if not pad:
        raise SystemExit("lot niet gevonden")
    bestanden = MP.offertebestanden(pad, bronnen.lijst)
    for e in bronnen.lijst(pad, recursief=False) or []:
        if e.get(".tag") == "folder":
            bestanden += [dict(b, naam=f"{e['name']}/{b['naam']}") for b in MP.offertebestanden(e["path_display"], bronnen.lijst)]
    woord = re.compile(r"totaal|total|suma|razem|netto|brutto|btw|vat|tva|eur|€|zł|pln", re.I)
    for b in bestanden:
        blz = F.paginas(bronnen.download(b["pad"]))
        print(f"== {b['naam']}: {len(blz) if blz else 'niet te openen'} blz, "
              f"{sum(len(x) for x in blz) if blz else 0} tekens, soort volgens de agent: {F.lees(blz)['soort']}")
        regels = "\n".join(blz or []).splitlines()
        rond = os.environ.get("NALOOP_ROND")      # bv. NALOOP_ROND=verlegd: drie regels rond elk treffer
        for i, regel in enumerate(regels):
            if rond and re.search(rond, regel, re.I):
                print("   ---", " | ".join(r.strip()[:90] for r in regels[max(0, i - 2):i + 4]))
            elif not rond and woord.search(regel) and re.search(r"\d", regel):
                print("   ", regel.strip()[:140])
        lees = F.lees(blz)
        print(f"    agent leest: excl {lees.get('excl')}, incl {lees.get('incl')}, btw {lees.get('btw_tarief')}, "
              f"verlegd {lees.get('verlegd')}, {'; '.join(lees.get('redenen') or [])[:160]}")


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "draai":
        draai(sys.argv[2], sys.argv[3], os.path.expanduser(sys.argv[4]), set(sys.argv[5:]) or None,
              os.path.expanduser(os.environ.get("PROEF_REFERENTIE", "~/proeven-bouw/referentie.json")))
    elif len(sys.argv) == 5 and sys.argv[1] == "naloop":
        naloop(sys.argv[2], sys.argv[3], sys.argv[4])
    elif len(sys.argv) == 4 and sys.argv[1] == "verken":
        verken(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(2)
