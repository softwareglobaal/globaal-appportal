"""Grendels op de soort vóór het nummer in de Contracten-agent (D63 van het contractsysteem, 20-10-2026).

Aanleiding: deal 14582 (5610 Ingrid Schmitz) op 16-10-2026. De aanvraag kwam via regulariseren.be, er stond een PV
in de salesmap en het Fathom-gesprek sprak een regularisatie tegen een forfait af. Het dossier bleef op de
standaardsoort architectuur, het model kreeg 2620 als vrij nummer mee en meldde alleen "nakijken of dit geen
regularisatie is". Deze test faalt zodra een nummer uit de reeks van een verworpen soort naar het bord kan gaan,
zodra een bestaand nummer de soort niet meer vastlegt, of zodra de agent over Mehdi's soort heen kan.

Draaien, zonder pytest:   python3 mijnagents-runner/tests/test_soortbepaling.py
Geen netwerk, geen dashboard, geen model. De bronnen zijn nagemaakt in de vorm van de echte.
"""
import os
import sys
import tempfile

HIER = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HIER)
sys.path.insert(0, os.path.join(HIER, "koppelingen"))
os.environ.setdefault("HOME", tempfile.mkdtemp(prefix="soort_"))
import soortbepaling as S  # noqa: E402
import contracten_agent as ca  # noqa: E402
import nummerlezer  # noqa: E402

ok = fout = 0


def check(naam, voorwaarde, extra=""):
    global ok, fout
    if voorwaarde:
        ok += 1
        print(f"  OK   {naam}")
    else:
        fout += 1
        print(f"  FOUT {naam} -> {extra}")


TRANSCRIPT = ("[42:10] Mehdi: Dus wat wij doen is het regularisatiedossier voor het terras opmaken en indienen. "
              "[43:03] Mehdi: het zou in 3.500 euro exclusief BTW kosten, als forfait.")
BRONNEN = {
    "salesmap": {"map": "/sales/Ingrid Schmitz", "fotos": ["03 Eigen plan en fotos/terras.jpg"],
                 "overige": ["Pipedrive communicatie - regulariseren.be.pdf (niet gelezen: RuntimeError)"],
                 "teksten": [{"bestand": "00 Fathom/Transcript_Ingrid_Schmitz.pdf", "gewijzigd": "2026-10-15",
                              "tekst": TRANSCRIPT},
                             {"bestand": "03 Eigen plan en fotos/11002_2024_18344_VPV_anoniem.pdf", "gewijzigd": "2026-10-06",
                              "tekst": "Stad Antwerpen. Proces-verbaal van vaststelling van een stedenbouwkundige overtreding."}]},
    "projectmap": None,
    "mails": [{"datum": "Mon, 05 Oct 2026 10:00:00 +0200", "van": "ingrid@example.test", "onderwerp": "Aanvraag",
               "tekst": "Ik wil dat de aanvraag volledig wordt opgemaakt en ingediend via het Omgevingsloket."}],
    "fouten": [],
}
DEAL = {"id": 900582, "title": "Ingrid Schmitz"}

print("\n1. signalen uit de bronnen, met bron en letterlijk citaat")
sigs = S.signalen(DEAL, ["[2026-10-05] Lead binnen via het formulier"], BRONNEN)
soorten = {s["signaal"] for s in sigs}
check("regulariseren.be telt ook als het alleen in een bestandsnaam staat (14582)", "platform" in soorten, sigs)
check("een PV telt: proces-verbaal in de tekst of _VPV in de naam", "pv" in soorten, sigs)
check("regularisatie in het transcript telt", "regularisatie" in soorten, sigs)
teksten = [" ".join(t.split()) for _, t in S.stukken(DEAL, [], BRONNEN)]
check("elk citaat staat letterlijk in de bron", all(any(s["citaat"] in t for t in teksten) for s in sigs),
      [s["citaat"] for s in sigs])
pv_panelen = S.signalen({"title": "Jan"}, ["PV-panelen en een batterij op het dak, 10 kWp"], {})
check("fotovoltaïsche PV-panelen zijn geen proces-verbaal", not pv_panelen, pv_panelen)
check("hoogstens drie signalen per soort", all(sum(1 for s in S.signalen(DEAL, ["regularisatie"] * 9, BRONNEN)
                                                    if s["signaal"] == k) <= 3 for k in ("regularisatie",)))
check("de samenvatting zegt dat er geen signalen zijn", "geen signalen" in S.samenvatting([]))

print("\n2. een bestaand nummer legt de soort vast (D9)")
check("5610 met de standaard architectuur: regularisatie voorstellen",
      S.soort_bij_nummer("regularisatie", "architectuur") == ("regularisatie", ""))
check("2618 met architectuur: niets te doen (een PV maakt het nog geen regularisatie)",
      S.soort_bij_nummer("architectuur", "architectuur") == (None, ""))
check("2603 met addendum: zelfde reeks, niets te doen", S.soort_bij_nummer("architectuur", "addendum") == (None, ""))
v, c = S.soort_bij_nummer("architectuur", "regularisatie")
check("2618 met regularisatie: conflict melden, niets veranderen", v is None and "Mehdi beslist" in c, (v, c))
v, c = S.soort_bij_nummer("regularisatie", "architectuur", beschermd=True)
check("5610 maar Mehdi koos architectuur: niets veranderen, wel melden", v is None and c, (v, c))
check("zonder nummer geen voorstel", S.soort_bij_nummer(None, "architectuur") == (None, ""))
nummerlezer.jaar_nu_brussel = lambda: 2026
check("de runner leest de reeks van 5610 als regularisatie", ca.soort_van_nummer("5610") == "regularisatie")
check("en van 2618 als architectuur", ca.soort_van_nummer("2618") == "architectuur")
check("en een vreemd nummer als niets", ca.soort_van_nummer("9912") is None)

print("\n3. wanneer een soortwissel van het model mag")
check("architectuur naar regularisatie zonder nummer: ja", S.wissel_toegelaten("regularisatie", "architectuur")[0])
check("niet over de soort van Mehdi", not S.wissel_toegelaten("regularisatie", "architectuur", beschermd=True)[0])
check("niet tegen de reeks van een bestaand nummer",
      not S.wissel_toegelaten("regularisatie", "architectuur", nummer_soort="architectuur")[0])
check("voorstudie binnen de reeks van 26xx mag", S.wissel_toegelaten("voorstudie", "architectuur", nummer_soort="architectuur")[0])
check("een onbekende soort niet", not S.wissel_toegelaten("verbouwing", "architectuur")[0])

print("\n4. de ronde: eerst de soort, dan het nummer uit haar reeks, dan het plan met haar master")


class Record:
    def __init__(self, *args):
        self.record = {"run_id": "fictief"}
        self.velden = {}

    def zet(self, **kwargs):
        self.velden.update(kwargs)
        return self

    def sluit(self, *args):
        return self


def ronde(titel, soort, plannen, beschermd=(), droog=False, citaat_ok=True):
    """Eén verwerk-ronde met nagemaakte koppelingen. Geeft (uitkomst, gebeurtenissen)."""
    gebeurd = []
    staat = {"soort": soort}

    def voorbereiding():
        return {"deal_id": DEAL["id"], "soort": staat["soort"], "velden": {}, "keuzes": [],
                "beschermd": [{"sleutel": k, "reden": "ingevuld in het dashboard"} for k in beschermd]}

    def call(naam, **args):
        gebeurd.append(("mcp", naam, args))
        if naam == "keuze_maken" and "soort" in (args.get("keuzes") or {}):
            if "soort" in beschermd:
                return {"niet_overschreven": {"soort": staat["soort"]}}
            staat["soort"] = args["keuzes"]["soort"]
            return {"vastgelegd": True}
        if naam in ("voorbereiding", "voorbereiding_starten"):
            return voorbereiding()
        if naam == "dossiercontrole":
            return {"controles": [{"nummer": "C4", "status": "ok", "bewijs": "/sales/Ingrid Schmitz"}]}
        if naam == "tijdlijn":
            return {"momenten": []}
        if naam == "proef_maken":
            raise ca.mcp.ToolFout("niet volledig")
        return {}

    def vrij(soort_, jaar=None, bewijs=None, deal_id=None):
        gebeurd.append(("nummer", soort_))
        return {"regularisatie": "5611", "architectuur": "2621"}.get(soort_, "2621")

    def plan(werk, deal, voorb, controle, notities, vrij_nummer, bronnen=None, soortsignalen=None):
        gebeurd.append(("plan", voorb.get("soort"), vrij_nummer, len(soortsignalen or [])))
        p = plannen.pop(0)(voorb, vrij_nummer)
        return p, 100, {"model_id": "fictief", "stop_reason": "tool_use", "tokens_in": 50, "tokens_uit": 50}

    import bord
    oud = dict(DROOG=ca.DROOG, VERS=ca.VERS)
    ca.DROOG, ca.VERS = droog, True
    zet = {"mcp_call": lambda naam, **a: call(naam, **a), "volgend_vrij_nummer": vrij, "plan_met_model": plan,
           "notities": lambda d: [], "veldenschema_voor": lambda s: {"master": {s: {"velden": []}}},
           "log": lambda *a, **k: None, "log_verstuur": lambda: None, "verzoeken_op_bord": lambda *a: None,
           "notitie_bijwerken": lambda d, t: gebeurd.append(("notitie", t)) or "bijgewerkt",
           "nummervoorstel_op_bord": lambda d, n, k, s: gebeurd.append(("bord", n, s)) or {"uitkomst": "gereserveerd"}}
    bewaard = {k: getattr(ca, k) for k in zet}
    bewaard_mcp, bewaard_pd, bewaard_hh = ca.mcp.call, ca.pipedrive.controleer_bedrijf, ca.hh.RunRecord
    bewaard_bronnen, bewaard_bord, bewaard_citaat = ca.bronnen_mod.verzamel, bord.klaargezet_voor, ca.hh.pas_citaat_toe
    try:
        for k, v in zet.items():
            setattr(ca, k, v)
        ca.mcp.call = lambda naam, **a: call(naam, **a)
        ca.pipedrive.controleer_bedrijf = lambda firma, verwacht: verwacht
        ca.hh.RunRecord = Record
        ca.bronnen_mod.verzamel = lambda *a: dict(BRONNEN)
        bord.klaargezet_voor = lambda *a, **k: []
        if not citaat_ok:
            ca.hh.pas_citaat_toe = lambda post, teksten: ("", "citaat niet teruggevonden")
        uit = ca.verwerk({"id": DEAL["id"], "title": titel}, "", {})
    finally:
        for k, v in bewaard.items():
            setattr(ca, k, v)
        ca.mcp.call, ca.pipedrive.controleer_bedrijf, ca.hh.RunRecord = bewaard_mcp, bewaard_pd, bewaard_hh
        ca.bronnen_mod.verzamel, bord.klaargezet_voor, ca.hh.pas_citaat_toe = bewaard_bronnen, bewaard_bord, bewaard_citaat
        ca.DROOG, ca.VERS = oud["DROOG"], oud["VERS"]
    return uit, gebeurd


MELDING = {"vastligt": [], "nakijken": [], "keuzes_vastgelegd": [], "ontbreekt": [], "volgende_stap": "nakijken"}


def wil_regularisatie(voorb, vrij):
    return {"gegevens": [], "keuzes": {"soort": "regularisatie"}, "nummer_voorstel": None, "melding": MELDING,
            "soort_bewijs": {"bron": "Fathom-transcript 15-10-2026", "citaat": "het regularisatiedossier voor het terras opmaken en indienen"}}


def gewoon_plan(voorb, vrij):
    return {"gegevens": [], "keuzes": {}, "nummer_voorstel": vrij or None, "melding": MELDING}


uit, g = ronde("Ingrid Schmitz", "architectuur", [wil_regularisatie, gewoon_plan])
soortkeuze = next((i for i, e in enumerate(g) if e[0] == "mcp" and e[1] == "keuze_maken"
                   and "soort" in (e[2].get("keuzes") or {})), None)
nummers = [(i, e[1]) for i, e in enumerate(g) if e[0] == "nummer"]
plannen = [e for e in g if e[0] == "plan"]
borden = [e for e in g if e[0] == "bord"]
check("het model stelt regularisatie voor: keuze_maken soort met bewijs als bron",
      soortkeuze is not None and "regularisatiedossier" in g[soortkeuze][2].get("bron", ""), g)
check("het nummer van de nieuwe soort wordt pas ná die keuze berekend",
      soortkeuze is not None and any(i > soortkeuze and s == "regularisatie" for i, s in nummers), nummers)
check("het tweede plan krijgt de soort regularisatie en het nummer 5611",
      len(plannen) == 2 and plannen[1][1] == "regularisatie" and plannen[1][2] == "5611", plannen)
check("het model kreeg de signalen uit de bronnen mee", plannen and plannen[0][3] >= 3, plannen)
check("op het bord komt 5611 met soort regularisatie, nooit 2621",
      borden == [("bord", "5611", "regularisatie")], borden)

uit, g = ronde("Ingrid Schmitz", "architectuur", [wil_regularisatie, gewoon_plan], droog=True)
check("droog: niets geschreven, wel de soort en het nummer uit de juiste reeks",
      uit.get("soort") == "regularisatie" and uit.get("vrij_nummer") == "5611"
      and not any(e[0] == "mcp" and e[1] in ("keuze_maken", "voorbereiding_starten", "gegeven_invullen") for e in g)
      and not any(e[0] == "bord" for e in g), (uit, g))

uit, g = ronde("Ingrid Schmitz", "architectuur", [wil_regularisatie], citaat_ok=False)
check("zonder letterlijk bewijs geen wissel en geen nummer op het bord",
      not any(e[0] == "mcp" and e[1] == "keuze_maken" and "soort" in (e[2].get("keuzes") or {}) for e in g)
      and not any(e[0] == "bord" for e in g) and len([e for e in g if e[0] == "plan"]) == 1, g)

uit, g = ronde("Ingrid Schmitz", "architectuur", [wil_regularisatie], beschermd=("soort",))
check("over de soort van Mehdi: geen wissel, één plan",
      not any(e[0] == "mcp" and e[1] == "keuze_maken" and "soort" in (e[2].get("keuzes") or {}) for e in g)
      and len([e for e in g if e[0] == "plan"]) == 1, g)

uit, g = ronde("5611 Ingrid Schmitz", "architectuur", [gewoon_plan])
soortkeuze = next((i for i, e in enumerate(g) if e[0] == "mcp" and e[1] == "keuze_maken"
                   and (e[2].get("keuzes") or {}).get("soort") == "regularisatie"), None)
eerste_plan = next((i for i, e in enumerate(g) if e[0] == "plan"), None)
check("een nummer 56xx in de dealtitel zet de soort op regularisatie vóór het plan",
      soortkeuze is not None and eerste_plan is not None and soortkeuze < eerste_plan
      and g[eerste_plan][1] == "regularisatie", g)
check("en dan wordt er geen nieuw nummer berekend", not any(e[0] == "nummer" for e in g), g)

uit, g = ronde("2618 Paulina Andrzejczyk", "architectuur", [wil_regularisatie])
check("2618 met een PV: het nummer houdt de soort architectuur, geen wissel",
      not any(e[0] == "mcp" and e[1] == "keuze_maken" and "soort" in (e[2].get("keuzes") or {}) for e in g), g)

print("\n5. de instructie aan het model")
check("het model hoort dat de soort eerst komt en het nummer bij de soort hoort",
      "De soort eerst (D63)" in ca.SCHEMA_UITLEG and "soort_van_dit_dossier" in ca.SCHEMA_UITLEG)

print(f"\n{'=' * 50}\n{ok} geslaagd, {fout} gefaald\n{'=' * 50}")
sys.exit(1 if fout else 0)
