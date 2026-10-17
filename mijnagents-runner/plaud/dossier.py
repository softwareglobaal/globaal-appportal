"""Dossierbeslissing voor een gesprek (verbeteropdracht v1.0, §4). Gedeeld door De Plaudwacht en De Fathomwacht.

Eén dossieridentiteit: firma plus projectnummer ("HARC:2612"). De Pipedrive-deal is een apart veld
(deal_id) en nooit de uitwisselsleutel: een transcript voor HARC:9998 moet de werfverslagketen
bereiken, ook als de deal een ander id heeft.

Bewijs komt per bron, afzonderlijk bewaard:

    titel        de naam van de opname of vergadering (nummerlezer)
    kop          `dossier:` in de kop van een inboxbestand (oude routine)
    openingszin  de eerste minuut van het transcript
    agenda       een afspraak die het opnametijdstip overlapt (niet: dezelfde dag)
    zoektaak     een gevalideerde opdracht van het Commandocentrum of de verslagvoorbereider
    deelnemer    (Fathom) het e-mailadres van een deelnemer hoort bij één deal met dit projectnummer
    locatie      een positief projectverblijf (auto of tracker): steunt, bewijst niet alleen
    model        het project dat het taalmodel noemde: alleen een kandidaat, nooit bewijs

Regels (versie 3, nacontrole v1.1): zie beslis(). Kort: alleen zekere of bekende getallen tellen;
titel en openingszin zijn één bron; verschillende dossiers in het bewijs of een model dat een ander
bekend dossier noemt is een conflict; conflict, privé (ook afdeling privé), onbekende of niet passende
afdeling, lage zekerheid, onvolledig bewijs of geen dossier: geen zakelijke bestemming, alleen
beoordeling door Mehdi (voor=mehdi). Dezelfde beslissing geldt voor élke zakelijke bestemming:
klaarzet voor een afdeling, dossierkopie en bezoekmap.
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "koppelingen"))

# Versie van de beslisregels: gaat mee in de vingerafdruk van De Plaudwacht, zodat een nieuwe regel
# bestaande beslissingen opnieuw beoordeelt. 2 (12-10-2026): één bron telt alleen bij een bekend nummer.
# 3 (12-10-2026, nacontrole v1.1): de zekerheid van de nummerlezer telt; titel en openingszin zijn één
# bron; een onbekend nummer vraagt een gecontroleerde bron; de afdeling moet bij de firma passen.
VERSIE = 3
# Gecontroleerde bronnen: een systeem zegt uitdrukkelijk firma en nummer (agenda met code en nummer,
# een gevalideerde zoektaak, het veld dossier: in een kop, een deelnemer van één deal).
GECONTROLEERD = ("agenda", "zoektaak", "kop", "deelnemer")
# Bronnen die niet onafhankelijk zijn, tellen als één groep.
GROEP = {"titel": "tekst", "openingszin": "tekst"}
HARD = ("titel", "kop", "openingszin", "agenda", "zoektaak", "deelnemer")
FIRMA_AFDELING = {"HARC": "h-architects", "UNAB": "unabo", "TKNB": "tkn", "HARM": "harmoniebouw",
                  "CONT": "contrax", "ELEV": "elevait"}


def bewijs(soort, firma, nummer, detail="", zeker=None):
    """zeker: volgens de bron zelf. Gecontroleerde bronnen zijn zeker tenzij anders gezegd; een getal dat
    de nummerlezer uit vrije tekst haalt is dat alleen als de nummerlezer het zegt."""
    if zeker is None:
        zeker = soort in GECONTROLEERD
    return {"soort": soort, "firma": firma, "nummer": str(nummer), "detail": (detail or "")[:200], "zeker": bool(zeker)}


def uit_tekst(soort, tekst, bron="vergadertitel"):
    """Bewijs uit een titel, kop of zin via de nummerlezer, met diens zekerheid. Alleen kandidaten met een firma."""
    import nummerlezer
    uit = []
    for k in nummerlezer.lees(tekst or "", bron):
        if k.firma and k.nummer:
            uit.append(bewijs(soort, k.firma, k.nummer, k.reden, zeker=bool(k.zeker)))
    return uit


def openingszin(uitingen, seconden=60):
    """De tekst van de eerste minuut: daar zegt Mehdi waar hij is, met wie en wat."""
    stukken = []
    for u in uitingen or []:
        if (u.get("start_time") or 0) > seconden * 1000:
            break
        stukken.append(u.get("content") or "")
    return " ".join(stukken)


def uit_agenda(afspraken):
    """Bewijs uit afspraken die al op overlap geselecteerd zijn (zie context.afspraken_op)."""
    uit = []
    for a in afspraken:
        if a.get("firma") and a.get("nummer"):
            uit.append(bewijs("agenda", a["firma"], a["nummer"], a.get("titel", ""), zeker=True))
    return uit


def uit_locatie(verblijf):
    """Bewijs uit een verblijf dat de aanroeper al via koppelingen/locatiecontext (grens, alleen positieve
    verblijven) kreeg. Dit bestand leest zelf geen locatiegegevens. Steunt een dossier, bewijst het niet."""
    if verblijf and verblijf.get("positief") and verblijf.get("firma") and verblijf.get("nummer"):
        return [bewijs("locatie", verblijf["firma"], verblijf["nummer"], "%s, %s" % (verblijf.get("rol"), verblijf.get("zekerheid")), zeker=False)]
    return []


def _bekend(bekend, firma, nummer):
    if not bekend:
        return False
    # H1-2, driehoeksoverleg C2, 17-10-2026: een kaal nummer bewijst geen firma.
    return (firma, nummer) in bekend


def beslis(bewijzen, herkenning=None, model=None, bekend=None):
    """De beslissing: dossier, zekerheid, conflict, route en of een zakelijke kopie mag.

    bekend: bestaande dossiers als (firma, nummer), bv. uit Pipedrive. None betekent dat die bron niet
    gelezen kon worden: dan is het bewijs onvolledig en gaat niets zakelijk weg (bewijs_onvolledig).

    Een getal telt voor een dossier als de bron het zeker zegt (gecontroleerde bron of zekere
    nummerlezing) of als het dossier bekend is. Andere getallen (bouwjaar, postcode, huisnummer) worden
    genoemd in de redenen en verder genegeerd. Titel en openingszin zijn samen één bron.
    hoog: een zoektaak, of twee onafhankelijke bronnen waarvan minstens één gecontroleerd of een bekend dossier;
    middel: één bron met een bekend dossier, of één gecontroleerde bron;
    laag: de rest. Het model bewijst niets; het geeft alleen een conflict als het een ánder bekend dossier noemt."""
    herkenning = herkenning or {}
    model = model or []
    afdeling = (herkenning.get("afdeling") or "").lower()
    prive = bool(herkenning.get("prive")) or afdeling == "prive"
    uit = {"dossier": None, "firma": None, "projectnummer": None, "zekerheid": "laag", "conflict": False,
           "bewijs": list(bewijzen), "model": list(model), "redenen": [], "prive": prive,
           "bewijs_onvolledig": bekend is None}
    if afdeling == "prive" and not herkenning.get("prive"):
        uit["redenen"].append("tegenstrijdige herkenning: afdeling privé maar prive=false; beoordeling door Mehdi")
    if bekend is None:
        uit["redenen"].append("bron met bekende dossiers niet gelezen; bewijs onvolledig")
    sleutels, genegeerd = {}, set()
    for b in bewijzen:                                  # eerst wat op zichzelf telt
        sleutel = (b["firma"], b["nummer"])
        if b.get("zeker", b["soort"] in GECONTROLEERD) or _bekend(bekend, *sleutel):
            sleutels.setdefault(sleutel, set()).add(b["soort"])
    for b in bewijzen:                                  # een onzeker getal steunt alleen een al gegrond dossier
        sleutel = (b["firma"], b["nummer"])
        if sleutel in sleutels:
            sleutels[sleutel].add(b["soort"])
        elif b["soort"] != "locatie":
            genegeerd.add(sleutel)
    if genegeerd - set(sleutels):
        uit["redenen"].append("onzeker getal zonder bekend dossier genegeerd: " + ", ".join("%s:%s" % g for g in sorted(genegeerd - set(sleutels))))
    harde = {s: soorten for s, soorten in sleutels.items() if soorten & set(HARD)}
    if len(harde) > 1:
        uit["conflict"] = True
        uit["redenen"].append("bewijs wijst naar meer dan één dossier: " + ", ".join("%s:%s" % s for s in sorted(harde)))
    elif len(harde) == 1:
        (firma, nummer), soorten = next(iter(harde.items()))
        uit.update(firma=firma, projectnummer=nummer, dossier="%s:%s" % (firma, nummer))
        groepen = {GROEP.get(s, s) for s in soorten & set(HARD)}
        gecontroleerd = bool(soorten & set(GECONTROLEERD))
        is_bekend = _bekend(bekend, firma, nummer)
        if "zoektaak" in soorten or (len(groepen) >= 2 and (gecontroleerd or is_bekend)):
            uit["zekerheid"] = "hoog"
        elif is_bekend or gecontroleerd:
            uit["zekerheid"] = "middel"
        else:
            uit["zekerheid"] = "laag"
            uit["redenen"].append("projectnummer %s is niet bekend en geen gecontroleerde bron bevestigt het" % nummer)
        tegen = {(m["firma"], m["nummer"]) for m in model if _bekend(bekend, m["firma"], m["nummer"])} - {(firma, nummer)}
        if tegen:
            uit["conflict"] = True
            uit["redenen"].append("het model noemt een ander bekend dossier: " + ", ".join("%s:%s" % t for t in sorted(tegen)))
    elif sleutels:
        uit["redenen"].append("alleen locatie: steunt, bewijst niet")
    elif model:
        uit["redenen"].append("alleen het model noemt een dossier; modeltekst is geen bewijs")
    if afdeling in ("", "onbekend"):
        uit["redenen"].append("afdeling onbekend")
    elif uit["firma"] and afdeling != "prive" and FIRMA_AFDELING.get(uit["firma"]) != afdeling:
        uit["redenen"].append("afdeling %s past niet bij firma %s" % (afdeling, uit["firma"]))
    if (herkenning.get("zekerheid") or "") == "laag":
        uit["redenen"].append("herkenning met lage zekerheid")
    if prive:
        uit["redenen"].append("privé")
    mag = (uit["dossier"] is not None and not uit["conflict"] and not prive and not uit["bewijs_onvolledig"]
           and uit["zekerheid"] in ("hoog", "middel") and uit["firma"] in FIRMA_AFDELING
           and afdeling == FIRMA_AFDELING[uit["firma"]] and (herkenning.get("zekerheid") or "") != "laag")
    uit["kopie_toegestaan"] = mag
    uit["voor"] = FIRMA_AFDELING[uit["firma"]] if mag else "mehdi"
    return uit
