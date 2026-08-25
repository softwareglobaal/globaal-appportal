#!/usr/bin/env python3
"""Dagelijkse wacht op het sales-dashboard.

Leest de doorgerekende cijfers via de agent-API van het dashboard
(/api/v1, zie docs/AGENT-API.md in de sales-repo) en zet opvallende dingen
als voorstel op het board van siyanagents. Rekent zelf niets na: het
dashboard bezit de definities, deze wacht kijkt alleen naar verloop.

Waarom hij bestaat: op 2026-08-24 bleek de advertentie-sync twaalf dagen
stil te staan en een pipelinenaam al maanden fout te matchen. Beide waren
zichtbaar in de cijfers; er keek alleen niemand.

Voorstellen krijgen bewust GEEN parameters. De uitvoerder slaat een
voorstel zonder parameters over, dus er kan hier niets uitgevoerd worden -
dit is een signaal, geen opdracht.

Cron (elke werkdag om 07:15 UTC, net na de sync van 06:45):
  15 7 * * 1-5 ~/agents/.venv/bin/python ~/appportal/siyanagents-runner/sales_wacht.py >> ~/agents/sales_wacht.log 2>&1

Droogdraaien (toont wat hij zou melden, zet niets op het board):
  ~/agents/.venv/bin/python ~/appportal/siyanagents-runner/sales_wacht.py --droog
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, timedelta

NAAM = "de-dealmaker"
RUNBOOK = "sales-signaal"          # geen uitvoerbare runbook: altijd zonder parameters
MIN_UITGAVEN = 100.0               # onder dit bedrag zegt kost-per-conversie te weinig
FACTOR_DUURDER = 1.5               # 50% duurder dan het gemiddelde = melden
FACTOR_MINDER = 0.6                # onder 60% van het gewone tempo = melden
KANAAL_DREMPEL = 5                 # zoveel aanvragen in de referentieperiode telt als "een kanaal"


def _laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except OSError:
        pass


_laad_env("~/appportal/siyanagents-data/.env")   # AGENTS_TOKEN, PLATFORM_URL
_laad_env("~/appportal/.env")                    # SALES_AGENT_TOKEN

PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3021")
AGENTS_TOKEN = os.environ.get("AGENTS_TOKEN", "")
SALES_API = os.environ.get("SALES_API_URL", "https://sales.globaal.be/api/v1")
SALES_TOKEN = os.environ.get("SALES_AGENT_TOKEN", "")


def haal(pad, **params):
    url = SALES_API + pad
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("Authorization", "Bearer " + SALES_TOKEN)
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def maanden_terug(n):
    """De n volledige maanden vóór de huidige, als 'JJJJ-MM'."""
    eerste = date.today().replace(day=1)
    uit = []
    for _ in range(n):
        eerste = (eerste - timedelta(days=1)).replace(day=1)
        uit.append(eerste.strftime("%Y-%m"))
    return list(reversed(uit))


def dagen_in_maand_tot_nu():
    return date.today().day


def dagen_in(maand):
    j, m = (int(x) for x in maand.split("-"))
    volgende = date(j + (m == 12), (m % 12) + 1, 1)
    return (volgende - date(j, m, 1)).days


# ---------- de controles ----------

def controle_versheid(signalen):
    h = haal("/health")
    if h.get("gezond"):
        return
    for w in h.get("waarschuwingen", []):
        signalen.append({
            "doel": "versheid",
            "actie": "Controleer de sync van het sales-dashboard",
            "reden": w + " Zolang dit duurt zijn de cijfers op het dashboard onvolledig.",
        })


def controle_tempo(signalen, afdeling):
    """Loopt de instroom van aanvragen deze maand ver achter op het gewone tempo?"""
    ref = maanden_terug(3)
    per_dag = []
    for m in ref:
        k = haal("/kpi", afdeling=afdeling, periode=m)
        per_dag.append(k["aanvragen"] / dagen_in(m))
    if not per_dag or sum(per_dag) == 0:
        return
    gewoon = sum(per_dag) / len(per_dag)

    nu_maand = date.today().strftime("%Y-%m")
    nu = haal("/kpi", afdeling=afdeling, periode=nu_maand)
    dagen = dagen_in_maand_tot_nu()
    if dagen < 7:
        return  # te vroeg in de maand om iets te kunnen zeggen
    tempo = nu["aanvragen"] / dagen

    if tempo < gewoon * FACTOR_MINDER:
        verwacht = round(gewoon * dagen)
        signalen.append({
            "doel": f"tempo:{afdeling}",
            "actie": f"Instroom {afdeling} ligt ver onder het gewone tempo",
            "reden": (
                f"{nu['aanvragen']} aanvragen in {dagen} dagen; op het gemiddelde van "
                f"{', '.join(ref)} waren er rond de {verwacht} verwacht. "
                f"Dat is {round((1 - tempo / gewoon) * 100)}% minder."
            ),
        })


def controle_campagnes(signalen):
    """Is een campagne fors duurder geworden per conversie?"""
    ref = maanden_terug(3)
    basis = {}
    for m in ref:
        for c in haal("/campagnes", periode=m).get("campagnes", []):
            if c["uitgaven"] and c["conversies"]:
                basis.setdefault(c["naam"], []).append(c["uitgaven"] / c["conversies"])

    nu_maand = date.today().strftime("%Y-%m")
    for c in haal("/campagnes", periode=nu_maand).get("campagnes", []):
        reeks = basis.get(c["naam"])
        if not reeks or c["uitgaven"] < MIN_UITGAVEN:
            continue
        gewoon = sum(reeks) / len(reeks)
        if not c["conversies"]:
            signalen.append({
                "doel": f"campagne:{c['naam']}",
                "actie": f"Campagne '{c['naam']}' levert deze maand niets op",
                "reden": (
                    f"EUR {round(c['uitgaven'])} uitgegeven, {c['klikken']} klikken, "
                    f"0 conversies. Normaal kost een conversie hier rond EUR {round(gewoon)}. "
                    "Controleer eerst of het formulier en de conversiemeting nog werken."
                ),
            })
            continue
        huidig = c["uitgaven"] / c["conversies"]
        if huidig > gewoon * FACTOR_DUURDER:
            signalen.append({
                "doel": f"campagne:{c['naam']}",
                "actie": f"Campagne '{c['naam']}' is fors duurder geworden",
                "reden": (
                    f"EUR {round(huidig)} per conversie deze maand, tegen EUR {round(gewoon)} "
                    f"gemiddeld over {', '.join(ref)} ({round((huidig / gewoon - 1) * 100)}% duurder). "
                    f"Uitgaven EUR {round(c['uitgaven'])}, {c['klikken']} klikken, "
                    f"{round(c['conversies'], 1)} conversies."
                ),
            })


def controle_kanalen(signalen, afdeling):
    """Is een kanaal dat normaal aanlevert deze maand helemaal stilgevallen?"""
    ref = maanden_terug(3)
    basis = {}
    for m in ref:
        for k in haal("/kanalen", afdeling=afdeling, periode=m).get("kanalen", []):
            basis[k["kanaal"]] = basis.get(k["kanaal"], 0) + k["aanvragen"]

    nu_maand = date.today().strftime("%Y-%m")
    nu = {k["kanaal"]: k["aanvragen"]
          for k in haal("/kanalen", afdeling=afdeling, periode=nu_maand).get("kanalen", [])}

    if dagen_in_maand_tot_nu() < 10:
        return
    for kanaal, aantal in basis.items():
        if aantal >= KANAAL_DREMPEL and nu.get(kanaal, 0) == 0:
            signalen.append({
                "doel": f"kanaal:{afdeling}:{kanaal}",
                "actie": f"Kanaal '{kanaal}' ({afdeling}) leverde deze maand niets",
                "reden": (
                    f"{aantal} aanvragen over {', '.join(ref)}, deze maand nul. "
                    "Mogelijk een campagne uit, een verwijzer die stilviel, of een label "
                    "dat niet meer wordt ingevuld."
                ),
            })


# ---------- naar het board ----------

def meld(body):
    req = urllib.request.Request(PLATFORM + "/agent-status",
                                 data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agents-Token", AGENTS_TOKEN)
    urllib.request.urlopen(req, timeout=20).read()


def main(argv):
    droog = "--droog" in argv
    if not SALES_TOKEN:
        print("SALES_AGENT_TOKEN ontbreekt; niets te doen.")
        return 1

    signalen = []
    fouten = []
    for naam, fn in [
        ("versheid", lambda: controle_versheid(signalen)),
        ("tempo engineering", lambda: controle_tempo(signalen, "engineering")),
        ("tempo energy", lambda: controle_tempo(signalen, "energy")),
        ("campagnes", lambda: controle_campagnes(signalen)),
        ("kanalen engineering", lambda: controle_kanalen(signalen, "engineering")),
        ("kanalen energy", lambda: controle_kanalen(signalen, "energy")),
    ]:
        try:
            fn()
        except Exception as e:                                  # noqa: BLE001
            fouten.append(f"{naam}: {e}")

    print(f"{date.today().isoformat()} · {len(signalen)} signaal/signalen"
          + (f" · {len(fouten)} controle(s) mislukt: {'; '.join(fouten)}" if fouten else ""))
    for s in signalen:
        print(f"  - [{s['doel']}] {s['actie']}\n      {s['reden']}")

    if droog:
        print("(droogdraai: niets op het board gezet)")
        return 0

    for s in signalen:
        meld({"naam": NAAM, "status": "actief", "taak": "wacht op het sales-dashboard",
              "detail": s["actie"][:400],
              "voorstel": {"actie": s["actie"], "runbook": RUNBOOK,
                           "doel": s["doel"], "reden": s["reden"]}})

    meld({"naam": NAAM, "status": "fout" if fouten else "waakt",
          "taak": "wacht op het sales-dashboard",
          "detail": ("; ".join(fouten))[:400] if fouten
                    else f"{len(signalen)} signaal/signalen op {date.today().isoformat()}"})
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
