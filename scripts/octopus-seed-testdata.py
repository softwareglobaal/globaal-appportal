"""Zaait herkenbare, relevante testdata in het Octopus-TESTDOSSIER (35493
"Globaal") - expliciet akkoord Shaniel 2026-07-09. Alles heet
"(API-testdata)" zodat het nooit met echte data verward wordt.

Wat het aanmaakt: 3 leveranciers met de ECHTE BTW-nummers van onze
telefonie-leveranciers (zodat de partij/BTW-koppeling testbaar is),
2 klanten, 3 aankoopfacturen die onze echte maandfacturen nabootsen en
2 verkoopfacturen. Idempotent: bestaat een relatie/boeking al, dan slaat
het script hem over.
"""
import json
import os
import urllib.error
import urllib.request

BASIS = "https://service.inaras.be/octopus-rest-api/v1"
DOSSIER = 35493


def vraag(pad, headers=None, body=None, methode=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(BASIS + pad, data=data,
        method=methode or ("POST" if data is not None else "GET"),
        headers={"content-type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            tekst = r.read().decode("utf-8", "replace")
            return r.status, json.loads(tekst) if tekst.strip() else {}
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:250]


_, auth = vraag("/authentication",
                headers={"softwareHouseUuid": os.environ["OCTOPUS_SOFTWAREHOUSE_UUID"]},
                body={"user": os.environ["OCTOPUS_USER"],
                      "password": os.environ["OCTOPUS_PASSWORD"]})
_, dt = vraag(f"/dossiers?dossierId={DOSSIER}&localeId=1",
              headers={"Token": auth["token"]}, body={})
KOP = {"dossierToken": dt["Dossiertoken"]}
print("ingelogd op testdossier", DOSSIER)

# Grootboekrekening voor telefoonkosten zoeken (61x, omschrijving telefoon).
_, accounts = vraag(f"/dossiers/{DOSSIER}/accounts?bookyearId=1", headers=KOP)
tel_rek = None
eerste_61 = None
for a in accounts:
    nr = ((a.get("accountKey") or {}).get("id"))
    oms = (a.get("description") or {})
    tekst = " ".join(str(v) for v in oms.values()) if isinstance(oms, dict) else str(oms)
    if nr and 610000 <= nr < 620000:
        if eerste_61 is None:
            eerste_61 = (nr, tekst.strip()[:40])
        if "telefoon" in tekst.lower() or "telefonie" in tekst.lower():
            tel_rek = (nr, tekst.strip()[:40])
            break
kosten_rek = (tel_rek or eerste_61)
print(f"kostenrekening voor de facturen: {kosten_rek}")

# ---- Relaties ---------------------------------------------------------------
_, bestaand = vraag(f"/dossiers/{DOSSIER}/relations", headers=KOP)
per_naam = {r.get("name"): r for r in bestaand}

RELATIES = [
    dict(naam="Proximus (API-testdata)", vat="BE0202.239.951", lev=True,
         adres=("Koning Albert II-laan 27", "1030", "Brussel")),
    dict(naam="Mega (API-testdata)", vat="BE0788.562.092", lev=True,
         adres=("Rue Natalis 2", "4020", "Luik")),
    dict(naam="Close Call BV (API-testdata)", vat="BE0799.782.024", lev=True,
         adres=("Testbaan 1", "2000", "Antwerpen")),
    dict(naam="Verbraeken en Co (API-testdata)", vat="", lev=False,
         adres=("Dorpsstraat 12", "9100", "Sint-Niklaas")),
    dict(naam="Yannick Technics (API-testdata)", vat="", lev=False,
         adres=("Nijverheidslaan 8", "3600", "Genk")),
]

for r in RELATIES:
    if r["naam"] in per_naam:
        print(f"relatie bestaat al: {r['naam']}")
        continue
    body = {
        "relationIdentificationServiceData": {"externalRelationId": 0},
        "name": r["naam"], "firstName": "",
        "client": not r["lev"], "supplier": r["lev"],
        "defaultBookingAccountClient": 400000 if not r["lev"] else 0,
        "defaultBookingAccountSupplier": 440000 if r["lev"] else 0,
        "streetAndNr": r["adres"][0], "postalCode": r["adres"][1],
        "city": r["adres"][2], "country": "BE",
        "currencyCode": "EUR",
        "vatNr": r["vat"], "vatType": 1 if r["vat"] else 0,
        "corporationType": 8, "active": True,
        "remarks": "API-testdata voor de Globaal-pijplijn; mag weg.",
    }
    status, antwoord = vraag(f"/dossiers/{DOSSIER}/relations", headers=KOP,
                             body=body, methode="PUT")
    print(f"relatie {r['naam']}: HTTP {status} {str(antwoord)[:120]}")

# Relatie-ID's ophalen voor de boekingen.
_, rels = vraag(f"/dossiers/{DOSSIER}/relations", headers=KOP)
rid = {}
for r in rels:
    if "(API-testdata)" in str(r.get("name", "")):
        rid[r["name"]] = (r.get("relationIdentificationServiceData") or {})
print("relatie-id's:", {k: v.get("relationKey") for k, v in rid.items()})

# ---- Boekingen --------------------------------------------------------------
def boeking(journal, nr, relnaam, datum, periode, excl, btw, oms, vatcode,
            rekening, verval=None, referentie=""):
    return {"buySellBookingServiceData": {
        "bookyearKey": {"id": 1},
        "journalKey": journal,
        "documentSequenceNr": nr,
        "relationIdentificationServiceData": rid[relnaam],
        "bookyearPeriodeNr": periode,
        "documentDate": datum,
        "expiryDate": verval or datum,
        "comment": oms,
        "orderReference": "", "reference": referentie,
        "amount": round(excl + btw, 2),
        "currencyCode": "EUR", "exchangeRate": 1.0,
        "paymentMethod": 0,
        "bookingLines": [{
            "accountKey": rekening,
            "baseAmount": excl, "vatCodeKey": vatcode, "vatAmount": btw,
            "comment": oms, "vatRecupPercentage": 100.0,
        }],
    }, "attachments": []}

_, huidige = vraag(f"/dossiers/{DOSSIER}/buysellbookings/modified?bookyearId=-1"
                   "&modifiedTimeStamp=2000-01-01%2000:00:00.000", headers=KOP)
al = {(b.get("journalKey"), b.get("documentSequenceNr")) for b in huidige} \
     if isinstance(huidige, list) else set()

BOEKINGEN = [
    ("A1", 7, "Proximus (API-testdata)", "2000-06-30", 200006, 105.20, 22.09,
     "Proximus (API-testdata) - 5 x Business Mobile Smart a 21,04", "D21",
     kosten_rek[0], "2000-07-30", ""),
    ("A1", 8, "Mega (API-testdata)", "2000-07-02", 200007, 16.55, 3.48,
     "Mega (API-testdata) - 5 x Mega Mobile 5 GB a 3,31", "D21",
     kosten_rek[0], "2000-08-01", ""),
    ("A1", 9, "Close Call BV (API-testdata)", "2000-07-05", 200007, 316.00, 66.36,
     "Close Call (API-testdata) - 41 nummers a 2,00 + 26 users a 9,00", "D21",
     kosten_rek[0], "2000-08-04", ""),
    ("V1", 3, "Verbraeken en Co (API-testdata)", "2000-07-07", 200007, 1500.00, 315.00,
     "EPB-verslaggeving 75% (API-testdata)", "21", 700300, "2000-08-06",
     "+++145/2000/00135+++"),
    ("V1", 4, "Yannick Technics (API-testdata)", "2000-07-08", 200007, 500.00, 105.00,
     "Technisch advies (API-testdata)", "21", 700300, "2000-08-07", ""),
]

for b in BOEKINGEN:
    if (b[0], b[1]) in al:
        print(f"boeking bestaat al: {b[0]} nr {b[1]}")
        continue
    status, antwoord = vraag(f"/dossiers/{DOSSIER}/buysellbookings",
                             headers=KOP, body=boeking(*b))
    print(f"boeking {b[0]} nr {b[1]} ({b[2][:20]}...): HTTP {status} {str(antwoord)[:120]}")

print("SEED KLAAR")
