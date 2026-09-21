#!/usr/bin/env python3
"""De naam van een gesprek: JJJJ-MM-DD UUMM FIRMA dossier - met wie - onderwerp.

Regel van Mehdi (18-09-2026), referentie: docs/Benamingen gesprekken. Dit is het
deterministische deel: wat uit de titel, de agendacode, de mensen en de herkenning
van De Fathomwacht af te leiden is zonder model. Wat overblijft staat in `ontbreekt`
en is werk voor het model of voor Mehdi op het dashboard.

Geen eigen lijsten (norm N6): firmacodes en collega's komen uit `kern` via
koppelingen/organisatie.py. Dit bestand schrijft niets en hernoemt niets.
"""
import re

# Agendacode van Mehdi -> firmacode in kern.firma. De agendacodes zijn van hem
# (werkwijze van De Agendawacht); de firmacodes staan op organisatie.globaal.be.
AGENDA_NAAR_FIRMA = {
    "HA": "HARC", "UNABO": "UNAB", "TKN": "TKNB", "HB": "HARM", "HARMONIEBOUW": "HARM",
    "CONTRAX": "CONT", "CTX": "CONT", "CX": "CONT", "ENERGIE": "ENEF", "EE": "ENEF", "ELEVAIT": "ELEV",
}
SOORT = {"KB": "klant buiten", "PB": "prospect buiten", "KO": "klant online", "PO": "prospect online",
         "KL": "klant", "IN": "intern"}
# afdeling in de herkenning van De Fathomwacht -> firmacode
AFDELING_NAAR_FIRMA = {"h-architects": "HARC", "unabo": "UNAB", "tkn": "TKNB", "harmoniebouw": "HARM",
                       "contrax": "CONT", "elevait": "ELEV"}
# firmanaam voluit als stuk van een titel ("Harmoniebouw: B2B: klant")
FIRMANAAM = {"HARCHITECTS": "HARC", "HARMONIEBOUW": "HARM", "TKNBURO": "TKNB", "ENERGIEEFFICIENT": "ENEF",
             "ENERGIEEFFICIËNT": "ENEF", "CONTRAX": "CONT", "ELEVAIT": "ELEV", "UNABO": "UNAB"}
FIRMA_VOORAAN = re.compile(r"^(H-?Architects|UNABO|TKN[- ]?Buro|Harmoniebouw|Energie[- ]?Effici[eë]nt|Contrax|Elevait)\b\s*(.*)$", re.I)
GENERIEK = re.compile(r"^(impromptu (zoom )?meeting|zoom meeting|meeting)$", re.I)
CODE = re.compile(r"\[\s*([A-Za-z]+)\s*-\s*([A-Za-z]{2})\s*-?\s*\]")
PROSPECTIE = re.compile(r"^(?P<naam>[^:]+):\s*(?P<firma>H-Architects|UNABO|UnaBo|TKN[- ]?Buro)\s+Prospections?\s*(?P<rest>\(.*\))?\s*$", re.I)
FIRMAWOORD = re.compile(r"\b(HA|UNABO|TKN|EE|HB|CONTRAX|CTX)\b")
PROJECTNR = re.compile(r"\b((?:2[0-9]|5[0-9])\d{2})\b")
VERBODEN = re.compile(r'[/\\:*?"<>|\x00-\x1f]')
EIGEN = {"mehdi", "mehdi chegini", "afspraken", "afspraken (mehdi)", "mch"}


def _schoon(t, maximum=60):
    t = VERBODEN.sub(" ", t or "").replace("–", "-")
    t = re.sub(r"\s+", " ", t).strip(" .,-")
    return t[:maximum].rstrip(" ,;-")


def _is_eigen(naam):
    n = (naam or "").lower()
    return n in EIGEN or n.startswith("afspraken") or n.startswith("mehdi")


def benoem(g, collega_herken=None):
    """g = gesprek.json van Fathom. collega_herken(naam) -> collega-dict of None
    (koppelingen.organisatie.herken). Geeft de delen, de bron per deel en wat ontbreekt."""
    titel = (g.get("title") or g.get("meeting_title") or "").strip()
    herk = g.get("herkenning") or {}
    uit = {"firma": "", "dossier": "", "met_wie": "", "onderwerp": "", "soort": "", "prive": bool(herk.get("prive")),
           "bron": {}, "ontbreekt": []}

    def zet(deel, waarde, bron):
        if waarde and not uit[deel]:
            uit[deel] = _schoon(waarde) if deel != "firma" else waarde
            uit["bron"][deel] = bron

    rest = titel
    # 1. de agendacode [FIRMA-SOORT]
    m = CODE.search(titel)
    if m:
        zet("firma", AGENDA_NAAR_FIRMA.get(m.group(1).upper(), ""), "agendacode in de titel")
        uit["soort"] = SOORT.get(m.group(2).upper(), "")
        rest = titel[m.end():]
    # 2. Calendly-vorm "Naam: H-Architects Prospections (second meeting)"
    p = PROSPECTIE.match(titel)
    if p:
        f = p.group("firma").upper().replace("-", "").replace(" ", "")
        zet("firma", {"HARCHITECTS": "HARC", "UNABO": "UNAB", "TKNBURO": "TKNB"}.get(f, ""), "Calendly-titel")
        zet("dossier", p.group("naam"), "naam van de prospect (sales zonder dossier)")
        zet("met_wie", p.group("naam"), "Calendly-titel")
        tweede = "tweede " if p.group("rest") and "second" in p.group("rest").lower() else ""
        zet("onderwerp", f"{tweede}prospectiegesprek", "Calendly-titel")
        uit["soort"] = uit["soort"] or "prospect online"
        rest = ""
    # 3. "EE: Mehdi: Ashvand: Klant" en "Mehdi: Klant"
    # Vorm: stukken gescheiden door dubbele punten. Firmawoorden, eigen mensen en
    # soortwoorden (B2B, (3RD)) vallen weg; het eerste stuk dat overblijft is de klant,
    # de rest is het onderwerp.
    delen = [d.strip() for d in rest.split(":") if d.strip()] if ":" in rest and not p else []
    if delen:
        over = []
        for d in delen:
            kaal = re.sub(r"\b(B2B|B2C)\b|\((?:\d+(?:ST|ND|RD|TH)|second meeting|2nd)\)", "", d, flags=re.I).strip(" -")
            woord = kaal.upper().replace("-", "").replace(" ", "")
            firma = AGENDA_NAAR_FIRMA.get(woord) or FIRMANAAM.get(woord)
            if firma:
                zet("firma", firma, "firmawoord in de titel"); continue
            # "H-Architects Light projects": firmanaam vooraan, de rest is het soort afspraak
            fp = FIRMA_VOORAAN.match(kaal)
            if fp:
                zet("firma", FIRMANAAM.get(fp.group(1).upper().replace("-", "").replace(" ", ""), ""), "Calendly-titel")
                if fp.group(2).strip():
                    over.append(fp.group(2).strip())
                continue
            namen = [x.strip() for x in re.split(r"&|\ben\b", kaal) if x.strip()]
            if not kaal or all(_is_eigen(x) or (collega_herken and collega_herken(x)) for x in namen):
                continue
            over.append(kaal)
        rest = over[0] + (" - " + ", ".join(over[1:]) if over[1:] else "") if over else ""
    rest = re.sub(r"^\s*(Mehdi\s*:?\s*)?(!!|\?\?)?\s*", "", rest).strip()
    # 4. firmawoord zonder haken ("Gerrit Van Onsem HA Klant")
    if not uit["firma"]:
        w = FIRMAWOORD.search(titel)
        if w:
            zet("firma", AGENDA_NAAR_FIRMA[w.group(1).upper()], "firmawoord in de titel")
            rest = FIRMAWOORD.sub("", rest)
            rest = re.sub(r"\b(Klant|Prospect|Online|Meeting)\b", "", rest, flags=re.I)
    # 5. projectnummer van H-Architects (26xx, 56xx en ouder)
    n = PROJECTNR.search(titel)
    if n and (uit["firma"] in ("", "HARC")):
        zet("firma", "HARC", "projectnummer in de titel")
        zet("dossier", n.group(1), "projectnummer in de titel")
        rest = rest.replace(n.group(1), "")
    # 6. wat er van de titel overblijft: "klant - onderwerp"
    rest = _schoon(re.sub(r"\b(Meeting|Online)\b", "", rest, flags=re.I), 90)
    if rest and not GENERIEK.match(titel):
        if " - " in rest:
            klant, onderwerp = rest.split(" - ", 1)
            zet("met_wie", klant, "titel"); zet("onderwerp", onderwerp, "titel")
        else:
            zet("met_wie", rest, "titel")
    # 7. de herkenning van De Fathomwacht vult aan
    if herk:
        zet("firma", AFDELING_NAAR_FIRMA.get((herk.get("afdeling") or "").lower(), ""), "herkenning Fathomwacht (afdeling)")
        # het "project" van de herkenning is meestal een omschrijving, geen dossier:
        # alleen een nummer of een korte naam telt als dossier, de rest is onderwerp
        project = herk.get("project") or ""
        pn = PROJECTNR.search(project)
        if pn:
            zet("dossier", pn.group(1), "projectnummer in de herkenning")
        elif project and len(project) <= 32 and len(project.split()) <= 4:
            zet("dossier", project, "herkenning Fathomwacht (project)")
        anderen = [x for x in (herk.get("personen") or []) if not _is_eigen(x)]
        zet("met_wie", " & ".join(anderen[:2]), "herkenning Fathomwacht (personen)")
        zet("onderwerp", project if (project and not uit["dossier"] == _schoon(project)) else "", "herkenning Fathomwacht (project)")
        zet("onderwerp", (herk.get("thema") or "").split(":")[0], "herkenning Fathomwacht (thema)")
    # 8. een collega als gesprekspartner: intern, en zijn firma als er maar een is
    if collega_herken and uit["met_wie"] and not uit["dossier"]:
        c = collega_herken(uit["met_wie"].split(" & ")[0])
        if c:
            zet("dossier", "intern", "gesprekspartner is een collega (kern)")
            dv = c.get("diensten_voor") or []
            if len(dv) == 1:
                zet("firma", dv[0], "collega werkt voor een firma (kern)")
    # sales zonder dossier: de naam is het dossier (regel van Mehdi)
    if uit["firma"] and uit["met_wie"] and not uit["dossier"]:
        zet("dossier", uit["met_wie"], "naam van de persoon (sales zonder dossier)")

    uit["ontbreekt"] = [d for d in ("firma", "dossier", "met_wie", "onderwerp") if not uit[d]]
    if uit["prive"]:
        uit["ontbreekt"] = [d for d in uit["ontbreekt"] if d not in ("firma", "dossier")]
    sterk = {"agendacode in de titel", "Calendly-titel", "projectnummer in de titel", "firmawoord vooraan in de titel"}
    uit["zekerheid"] = ("hoog" if uit["bron"].get("firma") in sterk and uit["dossier"] else
                        "midden" if uit["firma"] and uit["dossier"] else "laag")
    return uit


def naam(start_stempel, b):
    """De mapnaam, alleen als firma en dossier er zijn; anders ''."""
    if not (b.get("firma") and b.get("dossier")):
        return ""
    n = f"{start_stempel} {b['firma']} {b['dossier']}"
    if b.get("met_wie"):
        n += f" - {b['met_wie']}"
    if b.get("onderwerp"):
        n += f" - {b['onderwerp']}"
    return n[:120].rstrip(" ,;-")
