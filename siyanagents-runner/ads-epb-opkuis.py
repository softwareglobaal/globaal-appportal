#!/usr/bin/env python3
"""EPB-Promo-Search opkuisen (deel A1-A3 van het EPB-plan, GO van Siyan op 28 okt 2026).

Aanleiding: de energy-analyse van 27-28 okt. "Maximize conversions" stuurde op
knopklikken (57 van 69 conversies waren de codeloze "Request quote"), ±68 % van
de klikken ging naar loketten, premies, EPC en firmanamen, en mensen met enkel
"interesse" in Vlaanderen (o.a. Brussel) kregen de advertentie te zien.

  A1  enkel echte aanvragen primair (Offerteaanvraag website, Lead form - Submit,
      Calls from ads); de rest secundair
  A2  generieke brede zoekwoorden pauzeren, koopintentie als woordgroep/exact erbij
  A3  uitsluitingen (woordgroep) + geo enkel "aanwezig in" + Brussel uitgesloten

Momentopname van de toestand ervoor:
  ~/Claude/marketing/seo/firmas/UNABO/onderzoek/ads-epb-voor-2026-10-28.json

Gebruik:  python3 ads-epb-opkuis.py <stap> [--echt]
  stap = a1 | a1lokaal | a2 | a3
Zonder --echt draait het met validateOnly (Google controleert, wijzigt niets).
"""
import json
import sys

sys.path.insert(0, "/home/ubuntu/appportal/siyanagents-runner/koppelingen")
import googleads  # noqa: E402

CID = "1907613111"
CAMP = "22568475065"
AG = "180014896055"   # "Ad group 1", de enige advertentiegroep van de campagne
R = f"customers/{CID}"

# De codeloze acties "Request quote" (7093214557) en "Contact Us" (7110422807)
# en de "Local actions" geeft de API terug met MUTATE_NOT_ALLOWED (28 okt 2026):
# die moeten in de interface op secundair (Doelen > Samenvatting > actie >
# "Secundaire actie"). Hieronder enkel wat de API wel toelaat.
SECUNDAIR_WEB = {
    "7090933360": "REQUEST_QUOTE (GA4)",
    "7081060511": "Form (GA4)",
    "7356302636": "Submit lead form",
}
SECUNDAIR_LOKAAL = {  # niet via API: MUTATE_NOT_ALLOWED
    "7182316797": "Local actions - Website visits",
    "7185226048": "Local actions - Directions",
    "7366670375": "Local actions - Other engagements",
}

PAUZEER = {
    "19532990": "epb",
    "347481528668": "epb keuring",
    "13642136585": "epb certificaat",
    "382252226325": "epb certificaat vlaanderen",
    "342647948134": "epc attest prijs",
    "342212215914": "epc certificaat prijs",
    "358219658318": "epb vlaanderen",
    "383329039181": "epb bouw",
    "2419907661746": "e peil eisen",
    "347481528628": "epb epc",
}
NIEUW = [
    ("epb verslaggever", "PHRASE"),
    ("epb verslaggever", "EXACT"),
    ("epb verslaggever prijs", "PHRASE"),
    ("epb verslag prijs", "PHRASE"),
    ("prijs epb verslag", "PHRASE"),
    ("epb offerte", "PHRASE"),
    ("epb aangifte renovatie", "PHRASE"),
    ("epb startverklaring", "PHRASE"),
    ("ventilatieverslaggever", "PHRASE"),
]

# Woordgroep. "epb boete" en "startverklaring" staan er bewust NIET in: die zijn
# voor de advertentiegroep "EPB te laat" die nog komt.
UITSLUITEN = [
    "omgevingsloket", "omgevingsvergunning", "ruimtelijke ordening", "stedenbouw", "dienst",
    "gemeente", "stad", "ecohuis", "eco huis", "energieloket", "woonloket", "woningpas",
    "verbouwpremie", "premie", "bouwfederatie", "erkenning", "omgevingsinspectie",
    "bouwvoorschriften",
    "brussel", "bruxelles", "peb", "leefmilieu",
    "epc", "energieprestatiecertificaat", "energielabel",
    "wat is", "verschil", "betekenis", "tabel", "normen", "berekenen", "calculator",
    "software", "databank", "vacature", "job", "cursus", "examen",
]
# Firmanamen als woordgroep i.p.v. exact: exact sluit alleen de kale naam uit,
# niet "certipoint epb prijs".
FIRMAS = [
    "engie", "certipoint", "house check", "etib", "realed", "kubiek", "dethier", "ghw",
    "gefra", "adins", "concelio", "easyreno", "balfroid", "dgp inspections", "2be safe",
    "acasus", "kreps", "jampens", "raoul goris", "kenny geens", "epb excellent",
    "ep certificatie", "peritas", "greesa", "thirion", "dimar", "aceg",
]
BRUSSEL = "geoTargetConstants/20052"


def primair_uit(ids):
    return [{"conversionActionOperation": {
        "update": {"resourceName": f"{R}/conversionActions/{i}", "primaryForGoal": False},
        "updateMask": "primaryForGoal"}} for i in ids]


def bestaande_negatieven():
    rijen = googleads.zoek(CID, f"SELECT campaign_criterion.keyword.text FROM campaign_criterion "
                                f"WHERE campaign.id = {CAMP} AND campaign_criterion.negative = TRUE "
                                f"AND campaign_criterion.type = 'KEYWORD'")
    return {x["campaignCriterion"]["keyword"]["text"].lower() for x in rijen}


def ops(stap):
    if stap == "a1":
        return primair_uit(SECUNDAIR_WEB)
    if stap == "a1lokaal":
        return primair_uit(SECUNDAIR_LOKAAL)
    if stap == "a2":
        o = [{"adGroupCriterionOperation": {
            "update": {"resourceName": f"{R}/adGroupCriteria/{AG}~{c}", "status": "PAUSED"},
            "updateMask": "status"}} for c in PAUZEER]
        o += [{"adGroupCriterionOperation": {"create": {
            "adGroup": f"{R}/adGroups/{AG}", "status": "ENABLED",
            "keyword": {"text": t, "matchType": m}}}} for t, m in NIEUW]
        return o
    if stap == "a3":
        al = bestaande_negatieven()
        o = [{"campaignCriterionOperation": {"create": {
            "campaign": f"{R}/campaigns/{CAMP}", "negative": True,
            "keyword": {"text": t, "matchType": "PHRASE"}}}}
            for t in UITSLUITEN + FIRMAS if t.lower() not in al]
        o.append({"campaignCriterionOperation": {"create": {
            "campaign": f"{R}/campaigns/{CAMP}", "negative": True,
            "location": {"geoTargetConstant": BRUSSEL}}}})
        o.append({"campaignOperation": {
            "update": {"resourceName": f"{R}/campaigns/{CAMP}",
                       "geoTargetTypeSetting": {"positiveGeoTargetType": "PRESENCE"}},
            "updateMask": "geoTargetTypeSetting.positiveGeoTargetType"}})
        return o
    raise SystemExit(__doc__)


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    stap, echt = argv[0], "--echt" in argv
    o = ops(stap)
    body = {"mutateOperations": o, "partialFailure": False, "validateOnly": not echt}
    uit, kort = googleads.schrijf(CID, "/googleAds:mutate", body)
    print(("ECHT " if echt else "VALIDATIE ") + stap + f": {len(o)} operaties -> {kort}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
