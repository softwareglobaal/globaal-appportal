"""Het weekoverzicht van De Dagbundelaar (driehoeksoverleg fase 2, 27-10-2026, rapport-fase2.md Q1 tot Q8): de zeven
dagvaststellingen van een ISO-week opgeteld, en de geplande uren per firma. Mehdi vroeg op 26-10-2026 "een dashboard,
zodat ik zie wat ik effectief gedaan heb", wekelijks.

Geen eigen koppeling (Q1): de uitkomst per afspraak (bevestigd, aanwijzing, geen spoor) komt uit de dagvaststelling
(koppelingen/dagvaststelling.py), die de enige waarheid blijft. Dit telt alleen op.
Geen namen (Q5): het weekoverzicht draagt alleen aantallen, minuten en firmanamen; een privéafspraak telt als "privé",
nooit met haar titel. Wie iets wil nakijken, opent de dag.
Onbekend is onbekend (D6): een dag zonder vaststelling is "niet vastgesteld", een bron die niet gelezen werd is None,
en elk voorbehoud staat in totaal.voorbehoud. Nooit nul in de plaats van onbekend.
Geplande uren en gemeten gespreksminuten staan apart; ze worden nooit tegen elkaar weggestreept.

Pure functies: de runner (dagbundelaar.py --week) haalt de bronnen op. Het resultaat is het contract met het bord
(klaarzet weekoverzicht:<JJJJ-Www>, pagina /week in mijnagents/app.py), versie 1.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

BRUSSEL = ZoneInfo("Europe/Brussels")
UITKOMSTEN = ("bevestigd", "aanwijzing", "geen spoor")
PRIVE = "privé"
ONBEKEND = "onbekend"
VERSIE = 1


# ------------------------------------------------------------------------------------------------- weken ---
def weeknaam(d):
    j, w, _ = d.isocalendar()
    return f"{j}-W{w:02d}"


def vorige_week(nu):
    """De laatst afgesloten ISO-week in Brusselse tijd: op maandagnacht is dat de week van gisteren, nooit de pas
    begonnen week (X3)."""
    if nu.tzinfo is None:
        raise ValueError("nu zonder tijdzone")
    vandaag = nu.astimezone(BRUSSEL).date()
    return weeknaam(vandaag - timedelta(days=vandaag.weekday() + 7))


def dagen_van(week):
    """De zeven dagen (maandag tot zondag) van een week als 2026-W43; ValueError bij een week die niet bestaat."""
    j, w = week.split("-W")
    maandag = date.fromisocalendar(int(j), int(w), 1)
    return [(maandag + timedelta(days=i)).isoformat() for i in range(7)]


# -------------------------------------------------------------------------------------------------- dagen ---
def _getal(x):
    return int(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def dag_samenvatting(dag, v, dagversie=None):
    """De telling van een dag uit het dict van dagvaststelling.vaststellen, of 'niet vastgesteld' zonder dict."""
    if not v:
        return {"dag": dag, "vastgesteld": False}
    agenda = v.get("agenda") or {}
    if agenda.get("stand") == ONBEKEND:
        afspraken = None
    else:
        afspraken = {u: 0 for u in UITKOMSTEN}
        afspraken[PRIVE] = 0
        for x in agenda.get("afspraken") or []:
            if x.get("prive"):
                afspraken[PRIVE] += 1
            elif x.get("uitkomst") in UITKOMSTEN:
                afspraken[x["uitkomst"]] += 1
            else:
                afspraken["geen spoor"] += 1          # een onbekende uitkomst is nooit een bewijs
        afspraken["totaal"] = sum(afspraken.values())
    ng = v.get("niet_gepland") or {}
    bezoeken = ng.get("bezoeken")
    gesprekken = v.get("gesprekken") or {}
    zoom = v.get("zoom") or {}
    wa = v.get("whatsapp") or {}
    tel = v.get("telefoon") or {}
    mail = v.get("mail")
    # Zoals de dagtekst (dagvaststelling.tekst): zonder stand van De Zoomwacht en zonder een gezien gesprek is het aantal
    # onbekend, geen nul (Codex fase 2, punt 1). Wat wel gezien is, blijft staan als ondergrens.
    zoom_onbekend = (zoom.get("stand") or ONBEKEND) == ONBEKEND
    chatstand = zoom.get("chatstand") or zoom.get("stand") or ONBEKEND
    praat = ng.get("gesprekken") or []
    return {
        "dag": dag, "vastgesteld": True, "dagversie": dagversie,
        "afspraken": afspraken,
        "niet_gepland": {"gesprekken": None if zoom_onbekend and not praat else len(praat),
                         "minuten": None if zoom_onbekend and not praat else sum(int(g.get("minuten") or 0) for g in praat),
                         "bezoeken": None if bezoeken is None else len(bezoeken)},
        "gesprekken": ({k: None for k in ("aantal", "minuten", "met_opname", "alleen_zoom")}
                       if zoom_onbekend and not _getal(gesprekken.get("aantal")) else
                       {k: _getal(gesprekken.get(k)) for k in ("aantal", "minuten", "met_opname", "alleen_zoom")}),
        "zoom_chats": None if chatstand == ONBEKEND and not _getal(zoom.get("chats")) else _getal(zoom.get("chats")),
        "whatsapp": {"stand": wa.get("stand") or "niet aangesloten",
                     **{k: _getal(wa.get(k)) for k in ("gesprekken", "berichten", "oproepen", "minuten")}},
        "telefoon": {"stand": tel.get("stand") or "niet aangesloten",
                     **{k: _getal(tel.get(k)) for k in ("oproepen", "minuten")}},
        # Alleen de totalen: de postvakken dragen namen van ontvangers en blijven in het dagbestand.
        "mail": None if mail is None else {"binnen": _getal(mail.get("binnen")), "verzonden": _getal(mail.get("verzonden")),
                                           "onvolledig": bool(mail.get("onvolledig"))},
        "standen": {"agenda": agenda.get("stand") or ONBEKEND, "zoom": zoom.get("stand") or ONBEKEND,
                    "locatie": ng.get("locatiestand") or ("niet gelezen" if bezoeken is None else ONBEKEND)},
    }


# Het contract van een dagtelling: wat een bewaarde telling meebrengt buiten deze velden, valt weg (Codex-controle fase
# 2, ronde 3, K5: een onverwacht naamveld mag nooit in het weekoverzicht of op het bord komen).
TELLING_GETALLEN = {"afspraken": UITKOMSTEN + (PRIVE, "totaal"), "niet_gepland": ("gesprekken", "minuten", "bezoeken"),
                    "gesprekken": ("aantal", "minuten", "met_opname", "alleen_zoom"),
                    "whatsapp": ("gesprekken", "berichten", "oproepen", "minuten"), "telefoon": ("oproepen", "minuten"),
                    "mail": ("binnen", "verzonden")}


def _stand(x):
    return x[:60] if isinstance(x, str) else None


def telling_schoon(dag, x):
    """Een bewaarde dagtelling met alleen de velden van het contract: getallen, de standen en de vlag onvolledig."""
    uit = {"dag": dag, "vastgesteld": True, "dagversie": _getal(x.get("dagversie")), "zoom_chats": _getal(x.get("zoom_chats"))}
    for veld, sleutels in TELLING_GETALLEN.items():
        bron = x.get(veld)
        uit[veld] = None if not isinstance(bron, dict) else {k: _getal(bron.get(k)) for k in sleutels}
    for kanaal in ("whatsapp", "telefoon"):
        if uit[kanaal] is not None:
            uit[kanaal]["stand"] = _stand(x[kanaal].get("stand")) or ONBEKEND
    if uit["mail"] is not None:
        uit["mail"]["onvolledig"] = bool(x["mail"].get("onvolledig"))
    standen = x.get("standen") if isinstance(x.get("standen"), dict) else {}
    uit["standen"] = {k: _stand(standen.get(k)) or ONBEKEND for k in ("agenda", "zoom", "locatie")}
    return uit


def _optellen(waarden):
    """Som van wat gekend is; None als niets gekend is."""
    gekend = [w for w in waarden if w is not None]
    return sum(gekend) if gekend else None


def totaal(dagen):
    vast = [d for d in dagen if d.get("vastgesteld")]
    voorbehoud = [f"{d['dag']} niet vastgesteld" for d in dagen if not d.get("vastgesteld")]

    def groep(veld, sleutels, wanneer=lambda d: True):
        rijen = [d.get(veld) for d in vast if wanneer(d)]
        if any(r is None for r in rijen):
            voorbehoud.append(f"{veld.replace('_', ' ')} op een dag niet gekend")
        rijen = [r for r in rijen if r is not None]
        if not rijen:
            return None
        return {k: _optellen(r.get(k) for r in rijen) for k in sleutels}

    uit = {"dagen": len(dagen), "vastgesteld": len(vast),
           "afspraken": groep("afspraken", UITKOMSTEN + (PRIVE, "totaal")),
           "niet_gepland": groep("niet_gepland", ("gesprekken", "minuten", "bezoeken")),
           "gesprekken": groep("gesprekken", ("aantal", "minuten", "met_opname", "alleen_zoom")),
           "zoom_chats": _optellen(d.get("zoom_chats") for d in vast)}
    if any(d.get("zoom_chats") is None for d in vast):
        voorbehoud.append("Zoom-chats op een dag niet gekend")
    if any((d.get("standen") or {}).get("zoom") != "volledig" for d in vast):
        voorbehoud.append("gesprekken zijn een ondergrens: Zoom niet elke dag volledig gelezen")
    for kanaal, sleutels, naam in (("whatsapp", ("gesprekken", "berichten", "oproepen", "minuten"), "WhatsApp"),
                                   ("telefoon", ("oproepen", "minuten"), "telefoon")):
        standen = [(d.get(kanaal) or {}).get("stand") or ONBEKEND for d in vast]
        aan = [d for d in vast if (d.get(kanaal) or {}).get("stand") == "aangesloten"]
        # Onbekend is nooit 'niet aangesloten' (Codex fase 2, punt 1): elke stand die geen van beide is, is onbekend.
        if standen and all(s == "aangesloten" for s in standen):
            stand = "aangesloten"
        elif standen and all(s == "niet aangesloten" for s in standen):
            stand = "niet aangesloten"
        elif any(s not in ("aangesloten", "niet aangesloten") for s in standen):
            stand = ONBEKEND
        else:
            stand = "deels aangesloten"
        uit[kanaal] = {**{k: _optellen(d[kanaal].get(k) for d in aan) for k in sleutels}, "aangesloten_dagen": len(aan),
                       "stand": stand if standen else ONBEKEND}
        if stand == "niet aangesloten":
            voorbehoud.append(f"{naam} niet aangesloten")
        elif stand == ONBEKEND:
            voorbehoud.append(f"{naam} op een dag onbekend")
        elif stand == "deels aangesloten":
            voorbehoud.append(f"{naam} niet elke dag aangesloten")
    mails = [d.get("mail") for d in vast]
    gelezen = [m for m in mails if m is not None]
    uit["mail"] = None if not gelezen else {"binnen": _optellen(m.get("binnen") for m in gelezen),
                                           "verzonden": _optellen(m.get("verzonden") for m in gelezen),
                                           "onvolledig": len(gelezen) < len(mails) or any(m.get("onvolledig") for m in gelezen)}
    if uit["mail"] is None or uit["mail"]["onvolledig"]:
        voorbehoud.append("mail onvolledig")
    if any((d.get("standen") or {}).get("agenda") == "onvolledig" for d in vast):
        voorbehoud.append("agenda niet volledig gelezen")
    uit["voorbehoud"] = list(dict.fromkeys(voorbehoud))
    return uit


# ------------------------------------------------------------------------------------------------ planning ---
def _tijd(iso):
    t = datetime.fromisoformat(str(iso))
    return t if t.tzinfo else t.replace(tzinfo=BRUSSEL)


def planning_uren(afspraken_per_dag, dagen, ongelezen, is_prive, firma_van, firmanamen):
    """Geplande uren per firma uit de titelcode (Q3). afspraken_per_dag: van dagbundelaar.lees_agenda (zonder ritten,
    hele dagen en geannuleerde); ongelezen: de agenda's die niet gelezen werden, of None als de agenda helemaal niet
    gelezen werd. firma_van(afspraak): de firmacode van vier letters of None (geen of een tegenstrijdige code);
    firmanamen: {code: naam} uit kern. Privé is een post zonder titels; dezelfde afspraak op twee agenda's telt een keer;
    overlappende afspraken tellen elk; een afspraak zonder einde telt mee zonder minuten."""
    if ongelezen is None:
        return {"stand": ONBEKEND, "uren_per_firma": [], "afspraken": None, "minuten": None}
    # Eerst de kopieën van dezelfde afspraak samen (begin en einde als tijdstip, dus ook in een andere schrijfwijze),
    # dan pas indelen: zo hangt de post niet af van welke agenda eerst gelezen werd (Codex fase 2, punt 2). Privé gaat
    # voor (twijfel is privé); verschillende firmacodes zijn onbekend.
    groepen = {}
    for dag in dagen:
        for a in afspraken_per_dag.get(dag) or []:
            if a.get("hele_dag") or "T" not in str(a.get("start") or ""):
                continue
            einde = _tijd(a["einde"]).astimezone(BRUSSEL).isoformat() if a.get("einde") else ""
            identiteit = (_tijd(a["start"]).astimezone(BRUSSEL).isoformat(), einde,
                          " ".join(str(a.get("titel") or "").lower().split()))
            groepen.setdefault(identiteit, []).append(a)
    posten = {}
    for kopieen in groepen.values():
        a = kopieen[0]
        if any(is_prive(k) for k in kopieen):
            code = PRIVE
        else:
            codes = {firma_van(k) for k in kopieen} - {None}
            code = codes.pop() if len(codes) == 1 else ONBEKEND
        minuten = 0
        if a.get("einde"):
            minuten = max(int((_tijd(a["einde"]) - _tijd(a["start"])).total_seconds() // 60), 0)
        p = posten.setdefault(code, {"code": code, "naam": firmanamen.get(code) or code, "afspraken": 0, "minuten": 0})
        p["afspraken"] += 1
        p["minuten"] += minuten
    if ONBEKEND in posten:
        posten[ONBEKEND]["naam"] = "zonder of met onduidelijke firmacode"
    rij = sorted((p for c, p in posten.items() if c not in (ONBEKEND, PRIVE)), key=lambda p: (-p["minuten"], p["code"]))
    rij += [posten[c] for c in (ONBEKEND, PRIVE) if c in posten]
    return {"stand": "onvolledig" if ongelezen else "volledig", "uren_per_firma": rij,
            "afspraken": sum(p["afspraken"] for p in rij), "minuten": sum(p["minuten"] for p in rij)}


# -------------------------------------------------------------------------------------------------- geheel ---
def samenvatten(week, vaststellingen, planning, gemaakt):
    """vaststellingen: per vastgestelde dag ofwel (dict van vaststellen, versie), ofwel de telling die
    dag_samenvatting al maakte (zoals De Dagbundelaar ze naast het dagbestand bewaart); planning: van planning_uren.
    Geeft het weekoverzicht als gewone gegevens, zonder datum of start bovenaan (anders ziet de dagenpagina het als
    een dag)."""
    dagen = dagen_van(week)

    def rij(d):
        x = vaststellingen.get(d)
        if isinstance(x, dict) and x.get("vastgesteld") is True and x.get("dag") == d:
            return telling_schoon(d, x)
        return dag_samenvatting(d, *(x if isinstance(x, tuple) else (None, None)))

    rijen = [rij(d) for d in dagen]
    return {"soort": "weekoverzicht", "versie": VERSIE, "week": week, "van": dagen[0], "tot": dagen[-1],
            "gemaakt": gemaakt, "dagen": rijen, "totaal": totaal(rijen), "planning": planning}


def _n(x):
    return "?" if x is None else str(x)


def _uren(minuten):
    return "?" if minuten is None else f"{minuten / 60:.1f}".replace(".", ",")


def tekst(w):
    """Het weekbestand in Dropbox (dagboek/<jaar>/week/<week>.md): kort, zonder namen."""
    t = w["totaal"]
    r = [f"# Week {w['week']} ({w['van'][8:10]}-{w['van'][5:7]} tot {w['tot'][8:10]}-{w['tot'][5:7]})", ""]
    if t["voorbehoud"]:
        r += ["Voorbehoud: " + "; ".join(t["voorbehoud"]) + ".", ""]
    a = t.get("afspraken") or {}
    ng = t.get("niet_gepland") or {}
    g = t.get("gesprekken") or {}
    m = t.get("mail") or {}
    r += ["## Gepland tegenover gebeurd", "",
          f"- afspraken: {_n(a.get('totaal'))}, waarvan bevestigd {_n(a.get('bevestigd'))}, aanwijzing "
          f"{_n(a.get('aanwijzing'))}, geen spoor {_n(a.get('geen spoor'))}, privé {_n(a.get(PRIVE))}",
          f"- niet gepland: {_n(ng.get('gesprekken'))} gesprekken, {_n(ng.get('minuten'))} min; "
          f"{_n(ng.get('bezoeken'))} bezoeken zonder afspraak",
          f"- gesprekken in Zoom, Fathom en Plaud: {_n(g.get('aantal'))}, {_n(g.get('minuten'))} min "
          f"({_n(g.get('met_opname'))} met opname)",
          f"- Zoom-chats: {_n(t.get('zoom_chats'))} chatgesprekken",
          f"- mail: {_n(m.get('binnen'))} binnen, {_n(m.get('verzonden'))} verzonden",
          "", "## Per dag", ""]
    namen = ("ma", "di", "wo", "do", "vr", "za", "zo")
    for i, d in enumerate(w["dagen"]):
        kop = f"- {namen[i]} {d['dag'][8:10]}-{d['dag'][5:7]}"
        if not d.get("vastgesteld"):
            r.append(f"{kop}: niet vastgesteld")
            continue
        da = d.get("afspraken") or {}
        r.append(f"{kop}: {_n(da.get('totaal'))} afspraken ({_n(da.get('bevestigd'))} bevestigd, "
                 f"{_n(da.get('geen spoor'))} zonder spoor), {_n((d.get('niet_gepland') or {}).get('gesprekken'))} "
                 f"niet gepland, {_n((d.get('gesprekken') or {}).get('aantal'))} gesprekken, "
                 f"{_n(d.get('zoom_chats'))} Zoom-chats")
    p = w.get("planning") or {}
    r += ["", "## Geplande uren per firma", ""]
    if p.get("stand") != "volledig":
        r.append(f"Planning: {p.get('stand') or ONBEKEND}.")
    for x in p.get("uren_per_firma") or []:
        r.append(f"- {x['naam']}: {x['afspraken']} afspraken, {_uren(x['minuten'])} uur")
    r += ["", "Geplande uren en gemeten gespreksminuten staan apart; een afspraak zonder spoor is niet 'niet gedaan'."]
    return "\n".join(r) + "\n"
