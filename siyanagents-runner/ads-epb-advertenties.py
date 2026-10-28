#!/usr/bin/env python3
"""EPB-plan A4 (Siyan: GO, 28 okt 2026): eerlijke advertenties voor EPB-Promo-Search.

- Nieuwe RSA in "Ad group 1" (naar /promo-epb/) met de teksten van de seo-schrijver
  (marketing/seo/firmas/UNABO/drafts/2026-10-28-sea-epb.md, groep a).
- De oude RSA ("vanaf €330", "Gegarandeerd de Laagste Prijs", "10% korting",
  "EPB vs EPC") op PAUSED. Niets verwijderd.
- Sitelink "EPB vs EPC" (naar /epb-epc-verschil/, kostte geld zonder aanvragen)
  losgekoppeld van de campagne: koppeling op PAUSED, de asset zelf blijft.
- Nieuwe advertentiegroep "EPB te laat" met 7 zoekwoorden (woordgroep) en een
  RSA naar /epb-te-laat/ (groep b).

Gebruik:  python3 ads-epb-advertenties.py [--echt]
Zonder --echt draait het met validateOnly (Google controleert, wijzigt niets).
Momentopname vooraf: ~/Claude/marketing/seo/firmas/UNABO/onderzoek/ads-epb-advertenties-voor-2026-10-28.json
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "koppelingen"))
import googleads  # noqa: E402

K = "1907613111"
CAMPAGNE = f"customers/{K}/campaigns/22568475065"
GROEP_A = f"customers/{K}/adGroups/180014896055"
OUDE_RSA = f"customers/{K}/adGroupAds/180014896055~752782771621"
SITELINK_EPB_VS_EPC = f"customers/{K}/campaignAssets/22568475065~237472035741~SITELINK"
NIEUWE_GROEP = f"customers/{K}/adGroups/-1"

KOPPEN_A = [
    "EPB-verslaggever Vlaanderen", "Erkend EPB-verslaggever", "Vaste prijs EPB vooraf",
    "EPB renovatie €475 excl. btw", "EPB nieuwbouw €740 excl. btw", "Uw EPB-prijs binnen 24 uur",
    "Actief in heel Vlaanderen", "Startverklaring inbegrepen", "Startverklaring en aangifte",
    "EPB en ventilatie samen", "Vraag uw EPB-prijs aan", "Persoonlijke opvolging",
    "Vooraf weten wat het kost", "Eindaangifte inbegrepen", "Eén aanspreekpunt voor EPB",
]
BESCHR_A = [
    "Erkend EPB-verslaggever in heel Vlaanderen. Vaste prijzen vooraf, prijs binnen 24 uur.",
    "Renovatie €475, nieuwbouw €740 of ingrijpende renovatie €715. Alle bedragen excl. btw.",
    "Startverklaring, opvolging en EPB-eindaangifte in één prijs. Vraag uw offerte aan.",
    "Ook ventilatie nodig? Wij doen EPB en ventilatie, met één aanspreekpunt.",
]
KOPPEN_B = [
    "EPB te laat? Neem contact op", "Startverklaring vergeten?", "Brief van het VEKA ontvangen?",
    "Werken al bezig zonder EPB?", "Werken af, EPB niet in orde?", "Prijs op maat binnen 24 uur",
    "Erkend EPB-verslaggever", "Actief in heel Vlaanderen", "Lopend dossier overnemen",
    "Laat uw dossier nakijken", "EPB-aangifte te laat?", "Snel antwoord van UNABO",
    "Deadline van het VEKA?", "EPB-dossier alsnog opmaken", "Eerlijk advies, snel antwoord",
]
BESCHR_B = [
    "Startverklaring vergeten of werken al bezig? Prijs op maat binnen 24 uur.",
    "Brief van het VEKA gekregen? Wij kijken na wat er al is ingediend en wat nog kan.",
    "Erkend EPB-verslaggever in heel Vlaanderen. Wij nemen ook lopende dossiers over.",
    "Werken bezig of af zonder EPB-dossier? Wij zeggen binnen 24 uur wat de volgende stap is.",
]
ZOEKWOORDEN_B = [
    "epb boete", "startverklaring vergeten", "startverklaring te laat", "epb startverklaring te laat",
    "brief veka epb", "epb aangifte te laat", "epb aangifte vergeten",
]

for k in KOPPEN_A + KOPPEN_B:
    assert len(k) <= 30, (k, len(k))
for b in BESCHR_A + BESCHR_B:
    assert len(b) <= 90, (b, len(b))
assert len(KOPPEN_A) == len(KOPPEN_B) == 15 and len(BESCHR_A) == len(BESCHR_B) == 4


def rsa(groep, koppen, beschrijvingen, url):
    return {"adGroupAdOperation": {"create": {
        "adGroup": groep, "status": "ENABLED",
        "ad": {"finalUrls": [url], "responsiveSearchAd": {
            "headlines": [{"text": k} for k in koppen],
            "descriptions": [{"text": b} for b in beschrijvingen]}}}}}


def operaties():
    o = [
        # Eerst de nieuwe advertentie, dan pas de oude uit: de groep staat nooit leeg.
        rsa(GROEP_A, KOPPEN_A, BESCHR_A, "https://unabo.be/promo-epb/"),
        {"adGroupAdOperation": {"update": {"resourceName": OUDE_RSA, "status": "PAUSED"}, "updateMask": "status"}},
        {"campaignAssetOperation": {"update": {"resourceName": SITELINK_EPB_VS_EPC, "status": "PAUSED"}, "updateMask": "status"}},
        {"adGroupOperation": {"create": {"resourceName": NIEUWE_GROEP, "campaign": CAMPAGNE, "name": "EPB te laat",
                                         "status": "ENABLED", "type": "SEARCH_STANDARD"}}},
    ]
    for z in ZOEKWOORDEN_B:
        o.append({"adGroupCriterionOperation": {"create": {"adGroup": NIEUWE_GROEP, "status": "ENABLED",
                                                           "keyword": {"text": z, "matchType": "PHRASE"}}}})
    o.append(rsa(NIEUWE_GROEP, KOPPEN_B, BESCHR_B, "https://unabo.be/epb-te-laat/"))
    return o


def main(argv):
    echt = "--echt" in argv
    body = {"mutateOperations": operaties(), "partialFailure": False, "validateOnly": not echt}
    uit, kort = googleads.schrijf(K, "/googleAds:mutate", body)
    print(("ECHT: " if echt else "CONTROLE (validateOnly): ") + kort)
    if echt:
        print(json.dumps(uit, ensure_ascii=False)[:1500])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
