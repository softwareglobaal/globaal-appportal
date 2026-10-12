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

Regels:
- verschillende dossiers in het bewijs, of een model dat iets anders zegt dan het bewijs: conflict
- conflict, privé, onbekende afdeling, lage zekerheid of geen dossier: geen zakelijke kopie en
  geen routering naar een afdeling; alleen beoordeling door Mehdi (voor=mehdi)
- zekerheid hoog bij twee of meer onafhankelijke bronnen of een zoektaak, middel bij één harde bron,
  laag bij alleen locatie of alleen model
"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "koppelingen"))

# Versie van de beslisregels: gaat mee in de vingerafdruk van De Plaudwacht, zodat een nieuwe regel
# bestaande beslissingen opnieuw beoordeelt. 2 (12-10-2026): één bron telt alleen bij een bekend nummer.
VERSIE = 2
HARD = ("titel", "kop", "openingszin", "agenda", "zoektaak", "deelnemer")
FIRMA_AFDELING = {"HARC": "h-architects", "UNAB": "unabo", "TKNB": "tkn", "HARM": "harmoniebouw",
                  "CONT": "contrax", "ELEV": "elevait"}


def bewijs(soort, firma, nummer, detail=""):
    return {"soort": soort, "firma": firma, "nummer": str(nummer), "detail": (detail or "")[:200]}


def uit_tekst(soort, tekst, bron="vergadertitel"):
    """Bewijs uit een titel, kop of zin via de nummerlezer. Alleen kandidaten met een firma tellen."""
    import nummerlezer
    uit = []
    for k in nummerlezer.lees(tekst or "", bron):
        if k.firma and k.nummer:
            uit.append(bewijs(soort, k.firma, k.nummer, k.reden))
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
            uit.append(bewijs("agenda", a["firma"], a["nummer"], a.get("titel", "")))
    return uit


def uit_locatie(verblijf):
    if verblijf and verblijf.get("positief") and verblijf.get("firma") and verblijf.get("nummer"):
        return [bewijs("locatie", verblijf["firma"], verblijf["nummer"], "%s, %s" % (verblijf.get("rol"), verblijf.get("zekerheid")))]
    return []


def beslis(bewijzen, herkenning=None, model=None, bekend=None):
    """De beslissing: dossier, zekerheid, conflict, route en of een zakelijke kopie mag.

    bekend: projectnummers die bestaan (bv. uit Pipedrive). Eén harde bron met een onbekend nummer is
    laag: in "Renovatieplan vrijstaande woning 1933" is 1933 een bouwjaar, geen dossier (12-10-2026)."""
    herkenning = herkenning or {}
    model = model or []
    sleutels = {}
    for b in bewijzen:
        sleutels.setdefault((b["firma"], b["nummer"]), set()).add(b["soort"])
    uit = {"dossier": None, "firma": None, "projectnummer": None, "zekerheid": "laag", "conflict": False,
           "bewijs": list(bewijzen), "model": list(model), "redenen": [], "prive": bool(herkenning.get("prive"))}
    if len(sleutels) > 1:
        uit["conflict"] = True
        uit["redenen"].append("bewijs wijst naar meer dan één dossier: " + ", ".join("%s:%s" % s for s in sorted(sleutels)))
    elif len(sleutels) == 1:
        (firma, nummer), soorten = next(iter(sleutels.items()))
        uit.update(firma=firma, projectnummer=nummer, dossier="%s:%s" % (firma, nummer))
        harde = soorten & set(HARD)
        if "zoektaak" in soorten or len(soorten) >= 2 and harde:
            uit["zekerheid"] = "hoog"
        elif harde and bekend is not None and nummer not in bekend:
            uit["zekerheid"] = "laag"
            uit["redenen"].append("projectnummer %s is niet bekend; één bron volstaat dan niet" % nummer)
        elif harde:
            uit["zekerheid"] = "middel"
        else:
            uit["zekerheid"] = "laag"
            uit["redenen"].append("alleen locatie: steunt, bewijst niet")
        tegen = {(m["firma"], m["nummer"]) for m in model} - {(firma, nummer)}
        if tegen:
            uit["conflict"] = True
            uit["redenen"].append("het model noemt een ander dossier: " + ", ".join("%s:%s" % t for t in sorted(tegen)))
    elif model:
        uit["redenen"].append("alleen het model noemt een dossier; modeltekst is geen bewijs")
    afdeling = (herkenning.get("afdeling") or "").lower()
    if afdeling in ("", "onbekend"):
        uit["redenen"].append("afdeling onbekend")
    if (herkenning.get("zekerheid") or "") == "laag":
        uit["redenen"].append("herkenning met lage zekerheid")
    if uit["prive"]:
        uit["redenen"].append("privé")
    mag = (uit["dossier"] is not None and not uit["conflict"] and not uit["prive"] and uit["zekerheid"] in ("hoog", "middel")
           and afdeling not in ("", "onbekend") and (herkenning.get("zekerheid") or "") != "laag"
           and uit["firma"] in FIRMA_AFDELING)
    uit["kopie_toegestaan"] = mag
    uit["voor"] = FIRMA_AFDELING[uit["firma"]] if mag else "mehdi"
    return uit
