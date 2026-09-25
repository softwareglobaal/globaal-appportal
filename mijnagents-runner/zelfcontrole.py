#!/usr/bin/env python3
"""De zelfcontrole van de Agendawacht: elke ochtend nakijken in de agenda zelf, niet in het
logboek, of wat de agent beweert ook echt zo staat.

Waarom dit bestaat (24-09-2026): de weekcontrole van 21 tot 27 september vond fouten die de
agent zelf nooit meldde. Zijn logboek zei "0 mislukt", terwijl een kleur verkeerd stond, een
rit een oude titel droeg en de ochtendronde twee uur te laat liep. Wie alleen zijn eigen
verslag leest, ziet alleen wat hij al dacht. Deze controle kijkt naar de uitkomst.

Elke bevinding hangt aan een fout uit werkwijze/foutenregister.json. Komt een fout terug die
daar als opgelost staat, dan heet ze TERUGGEKEERD en staat ze bovenaan: dat is het signaal
dat een grendel niet werkt. Een bevinding zonder fout in het register heet NIEUW: die hoort
erin, met oorzaak en grendel, voor iemand ze oplost.

De controle schrijft niets in de agenda. Ze leest, meldt op het bord en bewaart de uitkomst
in mijnagents-data/zelfcontrole.json.

Draaien:  ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/zelfcontrole.py
          --ronde   alleen om 07:xx Brusselse tijd (cron start het elk uur)
          --van 2026-09-21 --tot 2026-09-27   een vaste periode, bv. een weekcontrole
"""
import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
sys.path.insert(0, str(HIER / "koppelingen"))
import agenda_wacht as W                      # noqa: E402

REGISTER = HIER / "werkwijze" / "foutenregister.json"
STAND = Path.home() / "appportal/mijnagents-data/zelfcontrole.json"
RONDE_UUR = 7


def register():
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def _arg(naam):
    if naam in sys.argv and sys.argv.index(naam) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(naam) + 1]
    return None


def bevindingen(items, van, tot, nu):
    """Alle bevindingen in [van, tot] als dicts: controle, dag, titel, tekst. Pure functie op de
    items, zodat de test ze met nagemaakte afspraken kan nakijken."""
    uit = []
    vandaag = nu.date().isoformat()
    vaste = W.AGENDA_VASTE_KLEUR
    vrij = W.lara_vakantiedagen() if items else set()
    zonder_auto = W.geen_auto_dagen() if items else set()

    def meld(controle, a, tekst):
        uit.append({"controle": controle, "dag": a["start"][:10], "uur": a["start"][11:16],
                    "agenda": W.KALENDERS.get(a.get("kalender"), "")[:20], "titel": a["titel"][:70],
                    "tekst": tekst, "door": W.maker(a)})

    binnen = [a for a in items if van <= a.get("start", "")[:10] <= tot and not a.get("kalender", "").startswith("en.be#")]
    ritten = [a for a in binnen if W.lees_titel(a["titel"])["reistijd"] and not a.get("_archief")]
    projecten = W.projectadressen.index() if items else {}
    for a in binnen:
        info = W.lees_titel(a["titel"])
        kal = a.get("kalender", "")
        toekomst = a["start"][:10] >= vandaag
        if a.get("_archief"):
            # een archiefagenda lees ik alleen: een komende afspraak daar hoort op werk (FR-39)
            if toekomst and not a.get("hele_dag"):
                meld("afspraak_in_archief", a, f"staat in '{a['_archief'][:40]}': hoort op werk")
            continue
        # titelvorm (FR-40, FR-41): wat de agent zelf moet aanvullen, en wat een voorstel blijft
        if toekomst and not a.get("hele_dag") and kal not in vaste and "T" in a.get("start", ""):
            nieuw, _uitleg = W.titel_aanvulling(a, projecten)
            if nieuw:
                zelf = not a.get("deelnemers") and not a.get("_terugkerend") and kal != "zoomafspraken@gmail.com"
                if info["reistijd"]:
                    meld("rit_zonder_autootje" if zelf else "titel_voorstel", a, f"hoort '{nieuw[:70]}'")
                else:
                    meld("titel_onvolledig" if zelf else "titel_voorstel", a, f"hoort '{nieuw[:70]}'")
        elif toekomst and info["reistijd"] and not a["titel"].lstrip().startswith("🚗") and not a.get("deelnemers") \
                and not a.get("_terugkerend") and not a.get("hele_dag"):
            meld("rit_zonder_autootje", a, "rit zonder autootje")
        r = a.get("_reminders") or {}
        eigen = r.get("overrides") or []
        standaard = r.get("useDefault", True) and not eigen
        oms, loc = a.get("omschrijving") or "", a.get("locatie") or ""
        # SU: nooit "Suriname" zichtbaar, afgekort is SU of HDSS (regel van Mehdi)
        for veld, tekst in (("titel", a["titel"]), ("locatie", loc), ("omschrijving", oms)):
            if re.search(r"surinam", tekst, re.I):
                meld("su_zichtbaar", a, f"'Suriname' staat in de {veld}")
        if info["reistijd"]:
            if toekomst and standaard and "OSRM" not in oms and not a.get("hele_dag"):
                meld("rit_melding_standaard", a, "handmatige rit op de agendastandaard (rinkelt 30 min vooraf)")
            continue
        buitenachtig = info["buiten"] or info["soort"] in W.BUITEN_SOORTEN
        if toekomst and not a.get("hele_dag") and kal not in vaste:
            wens = W.kleur_gewenst(a, info)
            if wens and (a.get("_kleur") or "") != wens:
                actie = W.kleur_actie(a, wens)
                meld("kleur", a,
                     f"kleur {W.KLEURNAAM.get(a.get('_kleur'), a.get('_kleur') or 'agenda')}, regel zegt {W.KLEURNAAM.get(wens, wens)}")
            if info.get("firma") == "HARC" and info["soort"] in ("PO", "PB") and info["nummer"] in projecten:
                meld("prospect_met_projectmap", a, "prospect, maar er is een projectmap: is al klant (FR-43)")
            if info.get("agendacode") and (a.get("_gemaakt") or "")[:10] >= W.KANTELDATUM:
                meld("oude_code", a, f"[{info['agendacode']}] in een afspraak van na {W.KANTELDATUM}")
            gewenst, _ = W.melding_gewenst(a)
            if gewenst and not eigen:
                meld("melding_ontbreekt", a, "hoort een melding en heeft er geen")
            if not gewenst and standaard and info["soort"] == "IN":
                meld("melding_niet_stil", a, "intern overleg rinkelt op de agendastandaard")
            if kal == W.WERKAGENDA and not a.get("_terugkerend") and info.get("firma") \
                    and info["soort"] in W.EXTERN_ONLINE and not buitenachtig:
                link = bool(a.get("_conferentie")) or bool(re.search(r"https?://", f"{loc} {oms}"))
                zl = W._heeft_zl(a["titel"])
                bel = re.search(r"\bbel(t|len)?\b|telefo", f"{a['titel']} {oms}", re.I)
                if link and zl:
                    meld("zl", a, "ZL terwijl er een link in staat")
                elif not link and not zl and not bel:
                    meld("zl", a, "extern online zonder link en zonder ZL")
                elif zl and not a["titel"].startswith("ZL "):
                    meld("zl", a, "ZL staat niet vooraan")
        if info["onzeker"] and not a.get("hele_dag") and "T" in a.get("einde", ""):
            try:
                voorbij = datetime.fromisoformat(a["einde"]) <= nu
            except ValueError:
                voorbij = False
            if voorbij:
                meld("onbevestigd_voorbij", a, "?? staat nog op een afspraak die voorbij is: doorgegaan?")
        if toekomst and buitenachtig and not a.get("hele_dag"):
            dag = a["start"][:10]
            if dag in zonder_auto:
                meld("buiten_zonder_auto", a, "buiten op een dag zonder auto")
                continue
            if kal in vaste and vaste[kal].get("naam") == "Lara" and dag in vrij:
                continue
            try:
                start = datetime.fromisoformat(a["start"])
            except ValueError:
                continue
            # een heenrit eindigt voor het begin, of later als het te krap is; dan draagt hij de
            # titel van deze afspraak in zijn omschrijving (FR-37)
            heen = [x for x in ritten if x.get("kalender") == kal and "T" in x.get("einde", "")
                    and (start - timedelta(hours=3) <= datetime.fromisoformat(x["einde"]) <= start
                         or (x["start"][:10] == a["start"][:10]
                             and f"Reistijd voor: {a['titel']} (" in (x.get("omschrijving") or "")))]
            if not heen:
                fysiek = bool(loc.strip()) and not loc.lower().startswith("http")
                bekend = fysiek or (info["nummer"] and info["nummer"] in W.projectadressen.index()) \
                    or W.plek_zoeken(a["titel"] + " " + oms)[0]
                if bekend:
                    meld("rit_ontbreekt", a, "buitenafspraak met adres, maar zonder heenrit")
                else:
                    meld("buiten_zonder_adres", a, "buiten zonder adres: geen rit mogelijk")
    # ritten die een titel dragen van een afspraak die er zo niet meer staat
    titels = {W.zonder_zl(a["titel"]).strip() for a in binnen}
    for x in ritten:
        if x["start"][:10] < vandaag:
            continue
        m = re.search(r"Reistijd (?:voor|na): (.+?) \(\d+ min", x.get("omschrijving") or "")
        if m and W.zonder_zl(m.group(1)).strip() not in titels:
            meld("rit_oude_titel", x, f"rit verwijst naar '{m.group(1)[:45]}', die titel bestaat niet meer")
    # een eigen rit hoort op de agenda van zijn afspraak (FR-28, FR-42)
    for x in ritten:
        if x["start"][:10] < vandaag or "OSRM" not in (x.get("omschrijving") or ""):
            continue
        m = re.search(r"Reistijd (?:voor|na): (.+?) \(\d+ min", x.get("omschrijving") or "")
        if not m:
            continue
        bij = [a for a in binnen if a["titel"].strip() == m.group(1).strip() and a["start"][:10] == x["start"][:10]
               and not a.get("_archief")]
        if bij and all(a.get("kalender") != x.get("kalender") for a in bij):
            meld("rit_andere_agenda", x, f"de afspraak staat op {W.KALENDERS.get(bij[0]['kalender'], '?')[:20]}, de rit niet")
    # twee klanten tegelijk, op welke agenda ook (FR-57)
    for a, b in W.dubbele_boekingen(binnen, nu, uren=24 * 8):
        meld("dubbele_boeking", a, f"tegelijk met {b['start'][11:16]} {b['titel'][:40]}")
    # een klant met een Zoom-link zonder wachtwoord raakt niet in de vergadering (FR-54)
    for a in W.zoom_zonder_wachtwoord(binnen, nu, uren=24 * 8):
        meld("zoom_zonder_wachtwoord", a, "Zoom-link zonder wachtwoord: de klant kan gevraagd worden om een wachtwoord")
    # een rit van nul minuten is geen rit: hij verbergt dat het te krap is
    for x in ritten:
        if x["start"][:10] >= vandaag and "T" in x["start"] and x["start"] == x.get("einde"):
            meld("rit_nul_minuten", x, "rit van nul minuten: de afspraken volgen te krap op elkaar")
    # dubbele ritten: twee ritten die elkaar overlappen op dezelfde agenda
    for i, x in enumerate(ritten):
        for y in ritten[i + 1:]:
            if x.get("kalender") == y.get("kalender") and x["start"][:10] >= vandaag \
                    and y["start"] < x.get("einde", "") and x["start"] < y.get("einde", ""):
                meld("rit_dubbel", x, f"overlapt met {y['start'][11:16]} {y['titel'][:35]}")
    return uit


def omgeving(nu):
    """De dingen buiten de agenda: het Google-plafond en of de ochtendronde op tijd liep."""
    uit = []
    _, gebruikt = W.routes_vandaag()
    if gebruikt > W.ROUTES_PLAFOND:
        uit.append({"controle": "google_plafond", "dag": nu.date().isoformat(), "uur": "", "agenda": "", "titel": "",
                    "tekst": f"Google Routes {gebruikt} van {W.ROUTES_PLAFOND}", "door": ""})
    log = Path.home() / "agents/agenda_wacht.log"
    if nu.weekday() < 5 and nu.hour >= 7 and log.exists():
        staart = log.read_text(errors="ignore")[-200000:]
        vandaag = nu.strftime("%Y-%m-%d")
        if not re.search(rf"=== {vandaag} 06:\d\d Brussel", staart):
            uit.append({"controle": "ochtendronde", "dag": vandaag, "uur": "", "agenda": "", "titel": "",
                        "tekst": "geen ronde om 06:30 Brusselse tijd in het logboek", "door": ""})
    # De nachtelijke kleurwissel (FR-21): zolang die bron niet uit is, zet het kleurherstel elke
    # nacht kleuren terug. Dat blijft zichtbaar tot het ophoudt, anders lijkt het opgelost.
    try:
        herstel = json.loads(Path(W.KLEURHERSTEL_LOG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        herstel = []
    grens = (nu - timedelta(days=1)).isoformat(timespec="minutes")
    recent = [h for h in herstel if h.get("tijd", "") >= grens and h.get("teruggezet")]
    if recent:
        uit.append({"controle": "kleur_nacht", "dag": nu.date().isoformat(), "uur": recent[-1]["tijd"][11:16],
                    "agenda": "", "titel": "",
                    "tekst": f"iets buiten de agent veranderde {sum(h['teruggezet'] for h in recent)} kleuren in 24 uur; "
                             f"het kleurherstel zette ze terug", "door": ""})
    return uit


def indelen(gevonden, reg):
    """Koppelt elke bevinding aan een fout uit het register: TERUGGEKEERD als die als opgelost
    staat, BEKEND als ze open is of een vraag aan Mehdi, NIEUW als ze er nog niet in staat."""
    per_controle = {}
    for f in reg["fouten"]:
        for c in f.get("controle") or []:
            per_controle[c] = f
    for b in gevonden:
        f = per_controle.get(b["controle"])
        b["register"] = f["id"] if f else ""
        if not f:
            b["staat"] = "NIEUW"
        elif f["status"] == "opgelost":
            b["staat"] = "TERUGGEKEERD"
        else:
            b["staat"] = "BEKEND"
    volgorde = {"TERUGGEKEERD": 0, "NIEUW": 1, "BEKEND": 2}
    return sorted(gevonden, key=lambda b: (volgorde[b["staat"]], b["dag"], b["uur"]))


def main():
    nu = W.nu_lokaal()
    if "--ronde" in sys.argv and not (nu.weekday() < 5 and nu.hour == RONDE_UUR):
        return 0
    van = _arg("--van") or (nu.date() - timedelta(days=7)).isoformat()
    tot = _arg("--tot") or (nu.date() + timedelta(days=7)).isoformat()
    d_van = (datetime.fromisoformat(van).date() - datetime.now().date()).days
    d_tot = (datetime.fromisoformat(tot).date() - datetime.now().date()).days
    items = [a for a in W.afspraken(d_van - 1, d_tot + 2) if not a.get("fout")]
    items += W.archief_afspraken(d_van - 1, d_tot + 2)      # alleen lezen (FR-39)
    reg = register()
    gevonden = indelen(bevindingen(items, van, tot, nu) + omgeving(nu), reg)
    tel = {s: sum(1 for b in gevonden if b["staat"] == s) for s in ("TERUGGEKEERD", "NIEUW", "BEKEND")}
    print(f"=== {nu:%Y-%m-%d %H:%M} Brussel · zelfcontrole {van} tot {tot}: {len(items)} afspraken, "
          f"{tel['TERUGGEKEERD']} teruggekeerd, {tel['NIEUW']} nieuw, {tel['BEKEND']} bekend")
    for b in gevonden:
        print(f"  {b['staat']:<12} {b['register'] or '-':<7} {b['dag'][5:]} {b['uur']} {b['controle']:<22} {b['titel'][:48]} | {b['tekst'][:70]}")
    try:
        oud = json.loads(STAND.read_text())
    except (OSError, ValueError):
        oud = {}
    geschiedenis = (oud.get("geschiedenis") or [])[-29:] + [{"tijd": nu.isoformat()[:16], **tel}]
    STAND.parent.mkdir(parents=True, exist_ok=True)
    STAND.write_text(json.dumps({"tijd": nu.isoformat()[:16], "van": van, "tot": tot, "bevindingen": gevonden,
                                 "geschiedenis": geschiedenis}, ensure_ascii=False, indent=1))
    if "--droog" in sys.argv:
        return 0
    ag = W.ag
    ag.log(f"dag {nu.date().isoformat()}", "bevinding",
           f"zelfcontrole: {tel['TERUGGEKEERD']} teruggekeerd, {tel['NIEUW']} nieuw, {tel['BEKEND']} bekend",
           "\n".join(f"{b['staat']} {b['register']} {b['dag']} {b['uur']} {b['titel'][:50]}: {b['tekst']}" for b in gevonden[:80]))
    if tel["TERUGGEKEERD"] or tel["NIEUW"]:
        ag.klaarzet([{"voor": "mehdi", "soort": "signaal", "sleutel": nu.date().isoformat(),
                      "titel": f"Zelfcontrole: {tel['TERUGGEKEERD']} fout(en) teruggekeerd, {tel['NIEUW']} nieuw",
                      "uniek": f"agenda-zelfcontrole:{nu.date().isoformat()}",
                      "inhoud": "\n".join(f"- {b['staat']} {b['register']} {b['dag']} {b['uur']} {b['titel'][:50]}: {b['tekst']}"
                                          for b in gevonden if b["staat"] != "BEKEND")[:6000]}])
    ag.log_verstuur()
    return 0


if __name__ == "__main__":
    sys.exit(main())
