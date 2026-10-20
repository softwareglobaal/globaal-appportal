"""De soort van een dossier ligt vast vóór het nummer (D63 van het contractsysteem, 20-10-2026).

Aanleiding: deal 14582 (5610 Ingrid Schmitz) op 16-10-2026. De aanvraag kwam via regulariseren.be, er stond een
PV in de salesmap en het Fathom-gesprek sprak een regularisatie tegen een forfait af. Toch bleef het dossier op
de standaardsoort architectuur van het klaarzetten, kreeg het model 2620 als volgend vrij nummer mee, en meldde
het alleen "nakijken of dit geen regularisatie is". Het nummer volgt de reeks van de soort (D9): wie het nummer
berekent vóór de soort vastligt, zet een nummer uit de verkeerde reeks op het bord.

Hier staat alleen code, geen oordeel:
- de signalen in de bronnen die op een regularisatie wijzen, met bron en letterlijk citaat, voor het model en
  het werkverslag. Geen signaal beslist alleen: een PV of het woord regularisatie staat ook in
  architectuurdossiers (2614, 2617 en 2618, gemeten op 20-10-2026). Het oordeel maakt het model, met citaat;
- de soort die een bestaand projectnummer vastlegt: reeks (JJ+30)xx is regularisatie, JJxx de rest;
- of een soortwissel mag: nooit over een soort die Mehdi koos, nooit tegen de reeks van een bestaand nummer.
Alles wat hier binnenkomt is GEGEVENS, geen opdracht.
"""
import re

# Welke soorten één nummerreeks delen (D9): architectuur, voorstudie en addendum JJxx; regularisatie (JJ+30)xx.
FAMILIE = {"architectuur": "architectuur", "voorstudie": "architectuur", "addendum": "architectuur",
           "regularisatie": "regularisatie"}

# (soort signaal, uitleg, patroon). Een kale "PV" niet: dat is in de bouw ook fotovoltaïsch.
PATRONEN = (
    ("platform", "aanvraag via regulariseren.be", re.compile(r"regulariseren\.be", re.I)),
    ("pv", "proces-verbaal of vaststelling van een bouwovertreding",
     re.compile(r"proces[- ]?verbaal|_VPV\b|\bVPV\b|bouwovertreding|stedenbouwkundige (?:overtreding|inbreuk)"
                r"|stakingsbevel", re.I)),
    ("regularisatie", "regularisatie genoemd", re.compile(r"regulari[sz]\w*", re.I)),
)
MAX_PER_SIGNAAL = 3


def _citaat(tekst, start, eind, breedte=110):
    """Een leesbaar stuk rond de treffer, letterlijk (op witruimte na), zonder halve woorden aan de randen."""
    links = max(0, start - breedte)
    rechts = min(len(tekst), eind + breedte)
    stuk = tekst[links:rechts]
    if links > 0 and " " in stuk:
        stuk = stuk.split(" ", 1)[1]
    if rechts < len(tekst) and " " in stuk:
        stuk = stuk.rsplit(" ", 1)[0]
    return " ".join(stuk.split())


def stukken(deal, notities, bronnen):
    """Alles waarin een signaal mag staan, als (bron, tekst). Bestandsnamen tellen mee: bij 14582 stond
    regulariseren.be alleen in de naam 'Pipedrive communicatie - regulariseren.be.pdf'."""
    d = deal or {}
    org = d.get("org_id")
    org = org.get("name") if isinstance(org, dict) else d.get("org_name")
    yield "Pipedrive-deal", " · ".join(x for x in (d.get("title"), org) if x)
    for n in notities or []:
        yield "Pipedrive-notitie", str(n)
    b = bronnen or {}
    for sleutel in ("salesmap", "projectmap"):
        m = b.get(sleutel) or {}
        namen = [t.get("bestand", "") for t in m.get("teksten") or []] + list(m.get("fotos") or []) \
            + list(m.get("overige") or [])
        if namen:
            yield f"{sleutel} (bestandsnamen)", " | ".join(str(x) for x in namen)
        for t in m.get("teksten") or []:
            yield f"{sleutel}: {t.get('bestand', '?')}", t.get("tekst") or ""
    for m in b.get("mails") or []:
        kop = f"mail {str(m.get('datum', ''))[:16]} {m.get('onderwerp', '')}".strip()
        yield kop, " · ".join(str(x) for x in (m.get("van"), m.get("onderwerp"), m.get("tekst")) if x)
    for k in b.get("klaargezet") or []:
        yield f"klaargezet: {k.get('titel', '')}", " · ".join(str(x) for x in (k.get("titel"), k.get("inhoud")) if x)


def signalen(deal=None, notities=None, bronnen=None):
    """Signalen voor een regularisatie in de bronnen: [{signaal, uitleg, bron, citaat}], hoogstens drie per
    soort signaal en één per bron. Aanwijzingen voor het model en het verslag, geen beslissing."""
    uit, per = [], {}
    for bron, tekst in stukken(deal, notities, bronnen):
        tekst = " ".join(str(tekst or "").split())
        if not tekst:
            continue
        for signaal, uitleg, patroon in PATRONEN:
            if per.get(signaal, 0) >= MAX_PER_SIGNAAL:
                continue
            m = patroon.search(tekst)
            if not m:
                continue
            per[signaal] = per.get(signaal, 0) + 1
            uit.append({"signaal": signaal, "uitleg": uitleg, "bron": bron, "citaat": _citaat(tekst, m.start(), m.end())})
    return uit


def samenvatting(sigs):
    """Eén regel voor het werkverslag: welke soorten signalen, uit hoeveel bronnen."""
    if not sigs:
        return "geen signalen voor een regularisatie in de bronnen"
    tel = {}
    for s in sigs:
        tel[s["uitleg"]] = tel.get(s["uitleg"], 0) + 1
    return "signalen voor een regularisatie: " + "; ".join(f"{k} ({v}x)" for k, v in tel.items())


def soort_bij_nummer(nummer_soort, huidig, beschermd=False):
    """De soort die een bestaand projectnummer vastlegt. nummer_soort is de soort van de reeks van dat nummer
    ('regularisatie' of 'architectuur'), of None zonder nummer. Geeft (voorstel of None, conflict of '')."""
    if not nummer_soort:
        return None, ""
    if FAMILIE.get(huidig) == FAMILIE.get(nummer_soort):
        return None, ""
    if nummer_soort == "regularisatie" and not beschermd:
        return "regularisatie", ""
    return None, (f"de soort {huidig} hoort niet bij de reeks van het projectnummer ({nummer_soort}); "
                  "ik verander niets, Mehdi beslist")


def wissel_toegelaten(nieuw, huidig, beschermd=False, nummer_soort=None):
    """Mag de soort van huidig naar nieuw (een voorstel van het model)? Geeft (ja/nee, reden)."""
    if not nieuw or nieuw == huidig:
        return False, "geen andere soort"
    if nieuw not in FAMILIE:
        return False, f"onbekende soort '{nieuw}'"
    if beschermd:
        return False, "Mehdi koos de soort zelf; ik stel geen andere voor (D63)"
    if nummer_soort and FAMILIE[nieuw] != FAMILIE.get(nummer_soort):
        return False, (f"het projectnummer hoort bij de reeks {nummer_soort}; {nieuw} past daar niet bij. "
                       "Mehdi beslist")
    return True, ""


def toets_bewijs(bewijs, deal=None, notities=None, bronnen=None):
    """Het bewijs bij een soortwissel van het model: (bron met citaat, fout). Dezelfde citaatcontrole als bij de
    gegevens (herhaalbaar.pas_citaat_toe, D34.6), over dezelfde stukken als de signalen, bestandsnamen inbegrepen."""
    import herhaalbaar as hh
    return hh.pas_citaat_toe(bewijs or {}, list(stukken(deal, notities, bronnen)))
