#!/usr/bin/env python3
"""Proefbank van de afdeling Bouw: laat De Aannemerszoeker of De Offertevergelijker een reeks vragen afwerken zoals op de
server (zelfde code, zelfde bronnen, zelfde abonnement), maar schrijft niets op het bord. Elke schrijfopdracht naar het
bord (hartslag, klaarzet, logboek, nood, kennis, opgepakt) komt in een eigen proefmap; alleen lezen (de werkwijze, de
collega's) gaat naar het bord. Testagents werken nooit op echte data (les 24-09-2026).

    python3 -m bouw.proefbank draai aannemerszoeker docs/bouw/proeven/aannemerszoeker.json ~/proeven-bouw/2026-11-02
    python3 -m bouw.proefbank verken HA 2145          lotmappen van een project en hun PDF's (alleen lezen)

Per proef: <id>.json (wat de agent zou schrijven, de Claude-vragen en de keuring) en <id>.md (het verslag), plus
uitslag.md met de keuring van alle proeven. De proefmap ligt buiten de repo: het verslag kan echte gegevens bevatten.
"""
import contextlib
import io
import json
import os
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

    def vraag(self, *args, **kw):
        begin = time.monotonic()
        tekst = " ".join(str(a) for a in args) + " " + " ".join(str(x) for x in kw.values())
        self.verboden_gezien += [w for w in self.verboden if w.lower() in tekst.lower()]
        try:
            uit = self.echt(*args, **kw)
        except claude_abonnement.Fout as e:
            self.vragen.append({"tools": list(kw.get("tools") or ()), "fout": str(e)[:300], "soort": e.soort,
                                "duur": round(time.monotonic() - begin, 1)})
            raise
        stuk = uit if isinstance(uit, dict) else {}
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
    for stuk in v.get("bevat") or []:
        uit.append((f"verslag noemt '{stuk}'", stuk.lower() in laag, ""))
    for stuk in v.get("niet") or []:
        uit.append((f"verslag noemt '{stuk}' niet", stuk.lower() not in laag, ""))
    if "klaar_min" in v or "klaar_max" in v:
        n = uitslag.get("klaar")
        goed = n is not None and n >= v.get("klaar_min", 0) and n <= v.get("klaar_max", 10 ** 6)
        uit.append((f"firma's klaar tussen {v.get('klaar_min', 0)} en {v.get('klaar_max', '...')}", goed, f"{n} klaar"))
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


def klaar_uit_log(regels):
    for r in regels:
        tekst = r.get("tekst") or ""
        if " klaar, " in tekst and "na te kijken" in tekst:
            try:
                return int(tekst.split(": ", 1)[1].split(" klaar", 1)[0])
            except (IndexError, ValueError):
                return None
    return None


def draai_proef(mod, proef, opname, teller):
    opname.schrijf.clear()
    teller.vragen.clear()
    teller.verboden_gezien.clear()
    proef = dict(proef, vraag=vul_in(proef["vraag"]))
    teller.verboden = project_straat(proef["vraag"]) if (proef.get("verwacht") or {}).get("adres_niet_naar_claude") else []
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
               "detail": hart.get("detail"), "logboek": regels, "klaar": klaar_uit_log(regels),
               "verboden": list(teller.verboden), "verboden_gezien": list(teller.verboden_gezien),
               "scherm": scherm.getvalue()[-4000:]}
    uitslag["keuring"] = [{"toets": t, "goed": g, "toelichting": x} for t, g, x in keur(proef, uitslag)]
    uitslag["geslaagd"] = all(k["goed"] for k in uitslag["keuring"])
    return uitslag


def draai(agent, proeven_pad, uitmap, alleen=None):
    mod = laad_agent(agent)
    opname = Opname(bord.call)
    bord.call = opname.call                      # vanaf hier bereikt geen schrijfopdracht het bord
    teller = Teller(claude_abonnement.vraag)
    claude_abonnement.vraag = teller.vraag
    with open(proeven_pad, encoding="utf-8") as f:
        proeven = json.load(f)["proeven"]
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


if __name__ == "__main__":
    if len(sys.argv) >= 5 and sys.argv[1] == "draai":
        draai(sys.argv[2], sys.argv[3], os.path.expanduser(sys.argv[4]), set(sys.argv[5:]) or None)
    elif len(sys.argv) == 4 and sys.argv[1] == "verken":
        verken(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(2)
