#!/usr/bin/env python3
"""Goudstandaard voor De Contractmaker (rapport 17-09-2026, stap 6; afspraak D35).

Bevroren invoer erin, hetzelfde resultaat eruit, k keer na elkaar. Dit is de
enige maat voor "doet hij altijd hetzelfde".

    goudstandaard.py bevries --deal 14318            bevriest de invoer van een dossier en zet een
                                                     goedgekeurd.json klaar (Mehdi keurt na en past aan)
    goudstandaard.py test [--runs 3] [--case 2616]   laat het model plannen op de bevroren invoer en
                                                     vergelijkt per veld: gelijk, anders, ontbreekt, extra
    goudstandaard.py lijst                           welke cases er zijn en hun laatste uitslag

Map per case: mijnagents-data/goudstandaard/<nummer>/invoer.json (gemaskeerd),
goedgekeurd.json, en rapporten per run. Nooit in git: het zijn klantdossiers.

Harde velden: exacte gelijkheid na normalisatie (bedrag, hoofdletters, spaties).
Vrije tekst (projectbeschrijving, doel, programma, te regulariseren werken): een
lijst verplichte feiten die er letterlijk in moeten staan (ja of nee). pass^k =
alle k runs zonder afwijking op harde velden en zonder ontbrekend feit.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
import contracten_agent as ca  # noqa: E402  (laadt env en koppelingen)
import herhaalbaar as hh  # noqa: E402

MAP = Path(os.path.expanduser("~/appportal/mijnagents-data/goudstandaard"))
VRIJE_TEKST = {"project_beschrijving", "project_omvat_extra_vrije_toevoeging", "doel_context",
               "programma_bullets", "regularisatiewerken_bullets", "opdracht_omschrijving",
               "vaststellingen_bullets", "betaalschema_bullets", "addendum_aanleiding_omschrijving"}
SYSTEEMVELDEN = hh.VERBODEN_VELDEN | {"opdrachtgever_1_rijksregister", "opdrachtgever_2_rijksregister",
                                      "vertegenwoordiger_rijksregister"}


def normaal(v):
    s = " ".join(str(v).split()).strip().casefold()
    return s


# ------------------------------------------------------------------ bevries ---
def bevries(deal_id: int):
    deal = ca.pipedrive.get(ca.FIRMA, f"/deals/{deal_id}")
    deal = deal.get("data", deal) if isinstance(deal, dict) else deal
    voorb = ca.mcp.call("voorbereiding", deal_id=deal_id)
    controle = ca.mcp.call("dossiercontrole", deal_id=deal_id)
    soort = voorb.get("soort") or "architectuur"
    nummer = str((voorb.get("velden") or {}).get("project_nummer") or ca.nummer_uit_titel(deal.get("title", "")) or deal_id)
    salesmap = ""
    for c in controle.get("controles", []):
        if c.get("nummer") == "C4" and c.get("status") == "ok":
            salesmap = (c.get("bewijs") or "").strip()
    velden = voorb.get("velden") or {}
    klant_email = velden.get("opdrachtgever_1_email") or velden.get("opdrachtgever_email") or ""
    lopend = soort in ("addendum", "regularisatie")
    bronnen = ca.bronnen_mod.verzamel(salesmap, nummer if lopend else "", klant_email)
    werk = ca.mcp.call("dashboard_document", sleutel="werkinstructie")
    # De test vertrekt van het dossier VÓÓR het modelwerk: alles wat als afgeleid of
    # uit een gesprek in de Herkomst staat, en alle keuzes (behalve de soort), gaan
    # eruit, zodat het model ze opnieuw moet leveren. Wat de klant, Pipedrive, een
    # register of het kantoor gaf, blijft staan: dat is invoer, geen oordeel.
    herkomst_vol = {g["sleutel"]: g for g in (voorb.get("herkomst") or {}).get("gevuld", [])}
    weg = {k for k, g in herkomst_vol.items() if g.get("soort") in ("afgeleid", "gesprek", "dashboard")} | VRIJE_TEKST
    keuzevelden = {k["veld"] for k in voorb.get("keuzes", []) if isinstance(k, dict) and k.get("veld") != "soort"}
    weg |= keuzevelden
    test_voorb = json.loads(json.dumps(voorb))
    test_voorb["velden"] = {k: v for k, v in velden.items() if k not in weg}
    test_voorb["herkomst"] = {
        "gevuld": [g for g in herkomst_vol.values() if g["sleutel"] not in weg],
        "ontbreekt": (voorb.get("herkomst") or {}).get("ontbreekt", []) + [
            {"veld": herkomst_vol[k].get("veld", k), "sleutel": k, "verwacht_uit": "nog te bepalen"}
            for k in sorted(weg) if k in velden and k not in VRIJE_TEKST and k in herkomst_vol],
    }
    test_voorb["keuzes"] = [dict(k, gekozen="" if k.get("veld") != "soort" else k.get("gekozen")) for k in voorb.get("keuzes", [])]
    test_voorb["vrije_velden"] = [dict(v, waarde="") for v in voorb.get("vrije_velden", [])]
    test_voorb["ontbreekt"] = [o["veld"] for o in test_voorb["herkomst"]["ontbreekt"]]
    test_voorb["stand"] = "te vervolledigen"
    invoer = {
        "bevroren_op": datetime.now(timezone.utc).isoformat(), "deal_id": deal_id, "nummer": nummer, "soort": soort,
        "deal": {"id": deal.get("id"), "title": deal.get("title"), "value": deal.get("value"),
                 "person_name": (deal.get("person_id") or {}).get("name") if isinstance(deal.get("person_id"), dict) else deal.get("person_name"),
                 "org_name": (deal.get("org_id") or {}).get("name") if isinstance(deal.get("org_id"), dict) else deal.get("org_name")},
        "voorbereiding": test_voorb, "voorbereiding_volledig": voorb, "controle": controle, "notities": ca.notities(deal_id),
        "vrij_nummer": "" if ca.nummer_uit_titel(deal.get("title", "")) else ca.volgend_vrij_nummer("56" if soort == "regularisatie" else "26"),
        "bronnen": ca._bronnen_compact(bronnen),
        "werkinstructie": werk.get("markdown", "") if isinstance(werk, dict) else str(werk),
        "werkinstructie_versie": werk.get("versie", "") if isinstance(werk, dict) else "",
        "werkwijze": ca.werkwijze_van_bord(), "veldenschema": ca.veldenschema_voor(soort), "model": ca.MODEL,
    }
    invoer = hh.masker_diep(invoer)
    m = MAP / nummer
    m.mkdir(parents=True, exist_ok=True)
    (m / "invoer.json").write_text(json.dumps(invoer, ensure_ascii=False, indent=1), encoding="utf-8")
    # Startpunt voor het goedgekeurde resultaat: wat het dossier nu draagt aan
    # modelwerk (afgeleid/gesprek) en keuzes. Mehdi keurt na en past aan.
    herkomst = {g["sleutel"]: g for g in (voorb.get("herkomst") or {}).get("gevuld", [])}
    gegevens = {k: v for k, v in velden.items()
                if k not in SYSTEEMVELDEN and k not in VRIJE_TEKST and k not in keuzevelden
                and herkomst.get(k, {}).get("soort") in ("afgeleid", "gesprek", "dashboard")}
    keuzes = {k["veld"]: k["gekozen"] for k in voorb.get("keuzes", []) if k.get("gekozen")}
    feiten = {k: [] for k in VRIJE_TEKST if velden.get(k)}
    goed = m / "goedgekeurd.json"
    bestaand = json.loads(goed.read_text(encoding="utf-8")) if goed.exists() else {}
    if not bestaand.get("goedgekeurd_op"):
        goed.write_text(json.dumps({"nummer": nummer, "goedgekeurd_door": "", "goedgekeurd_op": "",
                                    "gegevens": gegevens, "keuzes": keuzes, "vrije_tekst_feiten": feiten,
                                    "toelichting": "gegevens = harde velden die het model moet leveren (exact na normalisatie); "
                                                   "keuzes = de keuzes die het model moet voorstellen; vrije_tekst_feiten = "
                                                   "per vrij veld de zinnen of woorden die er letterlijk in moeten staan."},
                                   ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"bevroren: {m} ({len(gegevens)} harde velden, {len(keuzes)} keuzes, {len(feiten)} vrije velden; "
          f"{'goedgekeurd.json aangemaakt, na te kijken door Mehdi' if goed.stat().st_size else ''})")


# --------------------------------------------------------------------- test ---
def plan_op_bevroren(invoer: dict):
    ca.WERKWIJZE = invoer.get("werkwijze", "")
    ca._SCHEMA_CACHE[invoer["soort"]] = invoer.get("veldenschema") or {}
    bronnen_compact = invoer.get("bronnen")
    # plan_met_model verwacht ruwe bronnen en kort ze zelf in; een compacte set past ongewijzigd.
    ca._bronnen_compact_orig = getattr(ca, "_bronnen_compact_orig", ca._bronnen_compact)
    ca._bronnen_compact = lambda b, **k: b
    try:
        plan, tokens, meta = ca.plan_met_model(invoer["werkinstructie"], invoer["deal"], invoer["voorbereiding"],
                                               invoer["controle"], invoer["notities"], invoer["vrij_nummer"], bronnen_compact)
    finally:
        ca._bronnen_compact = ca._bronnen_compact_orig
    return plan, tokens, meta


def uitkomst_van(plan: dict, invoer: dict):
    """Het plan door dezelfde validatie als de runner: wat er in het dossier zou komen."""
    soort = invoer["soort"]
    schema = invoer.get("veldenschema") or {}
    toegelaten = set(((schema.get("master") or {}).get(soort) or {}).get("velden") or []) or None
    gegevens = {}
    teksten = hh.bronteksten(invoer.get("bronnen"), invoer.get("notities"))
    for post in plan.get("gegevens") or []:
        bron, citaatfout = hh.pas_citaat_toe(post, teksten)
        if citaatfout:
            continue
        goed, _ = hh.valideer_gegevens(post.get("velden") or {}, bron, toegelaten)
        gegevens.update(goed)
    opties = {k.get("veld"): list(k.get("opties") or []) for k in (invoer["voorbereiding"].get("keuzes") or []) if isinstance(k, dict)}
    vrij = set(((schema.get("master") or {}).get(soort) or {}).get("vrije_velden") or []) | ca.VRIJE_STANDAARD
    keuzes, _ = hh.valideer_keuzes(plan.get("keuzes") or {}, opties, vrij)
    return gegevens, keuzes


def vergelijk(goed: dict, gegevens: dict, keuzes: dict):
    uit = {"gelijk": [], "anders": [], "ontbreekt": [], "extra": [], "feit_ontbreekt": []}
    verwacht = dict(goed.get("gegevens") or {})
    verwacht.update({k: v for k, v in (goed.get("keuzes") or {}).items() if k not in VRIJE_TEKST})
    gekregen = dict(gegevens); gekregen.update({k: v for k, v in keuzes.items() if k not in VRIJE_TEKST})
    for veld, w in verwacht.items():
        if veld in VRIJE_TEKST:
            continue
        if veld not in gekregen:
            uit["ontbreekt"].append(veld)
        elif normaal(gekregen[veld]) == normaal(w):
            uit["gelijk"].append(veld)
        else:
            uit["anders"].append({"veld": veld, "verwacht": w, "gekregen": gekregen[veld]})
    for veld in gekregen:
        if veld not in verwacht and veld not in VRIJE_TEKST:
            uit["extra"].append(veld)
    teksten = {k: v for k, v in {**gegevens, **keuzes}.items() if k in VRIJE_TEKST}
    for veld, feiten in (goed.get("vrije_tekst_feiten") or {}).items():
        tekst = normaal(teksten.get(veld, ""))
        for feit in feiten:
            if normaal(feit) not in tekst:
                uit["feit_ontbreekt"].append({"veld": veld, "feit": feit})
    uit["geslaagd"] = not uit["anders"] and not uit["ontbreekt"] and not uit["feit_ontbreekt"]
    return uit


def test(runs: int, alleen: str | None):
    cases = sorted(p for p in MAP.iterdir() if p.is_dir() and (p / "invoer.json").exists()) if MAP.exists() else []
    if alleen:
        cases = [c for c in cases if c.name == alleen]
    if not cases:
        print("geen cases; bevries er eerst een met: goudstandaard.py bevries --deal <id>"); return 2
    stempel = datetime.now(timezone.utc).strftime("%Y-%m-%d %H%M")
    regels = [f"# Goudstandaard {stempel} UTC — model {ca.MODEL}, {runs} run(s) per case\n",
              "| case | pass^k | runs geslaagd | anders | ontbreekt | feit ontbreekt | verspringende velden | tokens | kost |",
              "|---|---|---|---|---|---|---|---|---|"]
    alles_goed = True
    for c in cases:
        invoer = json.loads((c / "invoer.json").read_text(encoding="utf-8"))
        goed = json.loads((c / "goedgekeurd.json").read_text(encoding="utf-8"))
        uitkomsten, tokens_tot, kost_tot, waarden = [], 0, 0.0, {}
        for i in range(runs):
            plan, tokens, meta = plan_op_bevroren(invoer)
            gegevens, keuzes = uitkomst_van(plan, invoer)
            v = vergelijk(goed, gegevens, keuzes)
            v["run"] = i + 1; v["model_id"] = meta.get("model_id"); v["tokens"] = tokens
            uitkomsten.append(v)
            tokens_tot += tokens; kost_tot += hh.kost_eur(meta.get("model_id") or "", meta.get("tokens_in", 0), meta.get("tokens_uit", 0)) or 0
            for k, w in {**gegevens, **keuzes}.items():
                waarden.setdefault(k, set()).add(normaal(w))
        verspringt = sorted(k for k, s in waarden.items() if len(s) > 1 and k not in VRIJE_TEKST)
        geslaagd = sum(1 for u in uitkomsten if u["geslaagd"])
        pk = geslaagd == runs
        alles_goed &= pk
        anders = sorted({a["veld"] for u in uitkomsten for a in u["anders"]})
        ontbr = sorted({x for u in uitkomsten for x in u["ontbreekt"]})
        feit = sorted({f"{f['veld']}: {f['feit'][:30]}" for u in uitkomsten for f in u["feit_ontbreekt"]})
        regels.append(f"| {c.name} | {'JA' if pk else 'NEE'} | {geslaagd}/{runs} | {', '.join(anders) or '—'} | {', '.join(ontbr) or '—'} | "
                      f"{'; '.join(feit) or '—'} | {', '.join(verspringt) or '—'} | {tokens_tot} | {kost_tot:.2f} |")
        (c / f"rapport {stempel}.json").write_text(json.dumps({"model": ca.MODEL, "runs": uitkomsten,
                                                               "goedgekeurd_op": goed.get("goedgekeurd_op", "")},
                                                              ensure_ascii=False, indent=1), encoding="utf-8")
    tekst = "\n".join(regels) + "\n\nLegenda: pass^k = alle runs zonder afwijking op harde velden en zonder ontbrekend feit; " \
            "'verspringende velden' krijgen tussen runs verschillende waarden en zijn de echte onzekerheid.\n"
    MAP.mkdir(parents=True, exist_ok=True)
    (MAP / f"rapport {stempel}.md").write_text(tekst, encoding="utf-8")
    print(tekst)
    return 0 if alles_goed else 1


def lijst():
    for c in sorted(MAP.iterdir()) if MAP.exists() else []:
        if not c.is_dir():
            continue
        g = json.loads((c / "goedgekeurd.json").read_text(encoding="utf-8")) if (c / "goedgekeurd.json").exists() else {}
        rapporten = sorted(c.glob("rapport *.json"))
        laatste = ""
        if rapporten:
            r = json.loads(rapporten[-1].read_text(encoding="utf-8"))
            laatste = f"{sum(1 for u in r['runs'] if u['geslaagd'])}/{len(r['runs'])} op {rapporten[-1].stem[8:]}"
        print(f"{c.name}: {len(g.get('gegevens', {}))} harde velden, {len(g.get('keuzes', {}))} keuzes, "
              f"goedgekeurd: {g.get('goedgekeurd_op') or 'nog niet'}; laatste test: {laatste or 'geen'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bevries"); b.add_argument("--deal", type=int, required=True)
    t = sub.add_parser("test"); t.add_argument("--runs", type=int, default=3); t.add_argument("--case")
    sub.add_parser("lijst")
    a = p.parse_args()
    if a.cmd == "bevries":
        bevries(a.deal)
    elif a.cmd == "test":
        sys.exit(test(a.runs, a.case))
    else:
        lijst()
