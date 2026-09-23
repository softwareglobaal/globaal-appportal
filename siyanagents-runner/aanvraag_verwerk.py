#!/usr/bin/env python3
"""Verwerkt de wachtrij van het aanvraagformulier van unabo.be.

Volgorde is bewust en mag niet omgedraaid worden:

  1. Google-contact aanmaken. Google Contacts is de bron van waarheid voor
     alles wat met de persoon te maken heeft.
  2. Wachten tot de eenrichtingssync die persoon in Pipedrive heeft gezet.
     Niet blind een paar minuten, maar kijken tot hij er is.
  3. Pas dan de deal aanmaken en aan díé persoon koppelen.

Zo ontstaat er nooit een tweede contact in Pipedrive naast de gesynchroniseerde.

Naamgeving volgt de bestaande afspraak, die twee systemen tegelijk bedient:
Xelion toont bij een oproep voornaam gevolgd door achternaam, dus staat de hele
identiteit in het voornaamveld ("PA David Derluyn"); mailings groeten met het
achternaamveld, dus staat daar de voornaam ("David").

Cron (elke minuut):
  * * * * * ~/agents/.venv/bin/python ~/appportal/siyanagents-runner/aanvraag_verwerk.py >> ~/agents/aanvraag_verwerk.log 2>&1

Droogdraaien (toont wat er zou gebeuren, verandert niets):
  ~/agents/.venv/bin/python ~/appportal/siyanagents-runner/aanvraag_verwerk.py --droog
"""

import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

DB = os.path.expanduser(os.environ.get("AANVRAAG_DB_HOST", "~/appportal/aanvraag-data/aanvragen.db"))
MAX_POGINGEN = 5
SYNC_GEDULD = 600          # seconden wachten op de Google->Pipedrive-sync
SYNC_INTERVAL = 10


def _laad_env(pad):
    try:
        for regel in open(os.path.expanduser(pad)):
            regel = regel.strip()
            if regel and not regel.startswith("#") and "=" in regel:
                k, v = regel.split("=", 1)
                os.environ.setdefault(k, v.strip().strip('"').strip("'"))
    except OSError:
        pass


_laad_env("~/appportal/.env")
_laad_env("~/appportal/siyanagents-data/.env")

PD_TOKEN = os.environ.get("PIPEDRIVE_TOKEN_UNABO", "")
PD = "https://unabo.pipedrive.com/v1"

# ---- firma's met een eigen Pipedrive-account ----
#
# Dit script bediende oorspronkelijk alleen UNABO. Sinds de site van TKN-Buro
# (september 2026) komen er aanvragen binnen van een firma met een eigen
# Pipedrive-account, eigen pijplijnen en zonder contactsync.
#
# De regel is: staat de bron NIET in FIRMAS, dan gebeurt exact wat er altijd al
# gebeurde (UNABO). Zo kan deze uitbreiding de bestaande leadstroom niet raken.
#
# Per firma:
#   api, token_env  het Pipedrive-account waar de deal in komt
#   pipeline        vaste (pipeline_id, stage_id) voor elke websiteaanvraag
#   label           id van het deallabel
#   contactsync     True  = via Google Contacts, wachten op de sync (UNABO)
#                   False = persoon rechtstreeks in Pipedrive aanmaken
#   env             extra .env met de SMTP-gegevens voor de meldingsmail
FIRMAS = {
    "tkn-site": {
        "naam": "TKN-Buro",
        "api": "https://tkn-buro-tekenwerk.pipedrive.com/v1",
        "token_env": "PIPEDRIVE_TOKEN_TKNBURO",
        # Pijplijn 8 "TKN-Stabiliteitsstudie", eerste fase 110 "New / Off.
        # aanvraag". Bewust niet pijplijn 2 "TKN-Tekenwerk": die begint met
        # Mail 1, Postmaster, DoNotCallMe en Bellen en is dus een pijplijn voor
        # koude acquisitie, niet voor binnenkomende aanvragen.
        "pipeline": (8, 110),
        "label": 48,          # "website"
        "contactsync": False,
        "env": "~/tkn-site/.env",
    },
}


def firma_van(bron):
    """De firma-instellingen voor een bron, of None voor het standaardgedrag."""
    return FIRMAS.get((bron or "").strip().lower())
PLATFORM = os.environ.get("PLATFORM_URL", "http://127.0.0.1:3021")
AGENTS_TOKEN = os.environ.get("AGENTS_TOKEN", "")

# ---- afspraken die in Pipedrive vastliggen (opgehaald 2026-08-31) ----
DIENST_PIPELINE = {
    "energie": (3, 79),
    "stabiliteit": (2, 67),
    "veiligheidscoordinatie": (5, 22),
    "vergunning": (14, 138),
    # Regularisatie is sinds 4 sep 2026 een eigen dienst op unabo.be en loopt door
    # dezelfde pijplijn als de vergunningen. Zonder deze regel valt zo'n aanvraag
    # in Engineering met label "Te routeren" (dat is gebeurd; rechtgezet 22 sep).
    "regularisatie": (14, 138),
    # Functiewijziging is sinds 23 sep 2026 een eigen dienst op unabo.be. Ook een
    # vergunningsdossier, dus dezelfde pijplijn als vergunningen en regularisatie.
    "functiewijziging": (14, 138),
    # Aankoopbegeleiding (23 sep 2026): de kern is de vergunningstoestand en
    # eventuele bouwovertredingen van het pand, dus de vergunningenpijplijn.
    # Bouwkundige vragen (vocht, stabiliteit) worden van daaruit doorgezet.
    "aankoopbegeleiding": (14, 138),
    # 3D-rendering: zelfde team en zelfde soort dossier als 3D-scanning.
    "3d-rendering": (4, 17),
    "3d-scanning": (4, 17),
    "landmeter": (21, 245),
    "plaatsbeschrijving": (26, 327),
}
BUNDEL = (8, 56)                 # twee of meer diensten tegelijk
ONBEKEND = (2, 67)               # alleen "Andere": Engineering, met label Te routeren
LABEL_WEBSITE = 110
LABEL_TE_ROUTEREN = 345
VELD_GEBOUWTYPE = "68f15f6c93058199f625aff59b5d8e903d3cae87"
VELD_TYPE_AANVRAAG = "cd1e5146cea21aecff4172a25ad7c99a7d4dfff0"
GEBOUWTYPE = {
    "eengezinswoning": 262, "meergezinswoning": 307, "appartement": 264,
    "commercieel / bedrijfsgebouw": 308, "commercieel": 308, "bedrijfsgebouw": 308,
    "industrieel": 268, "openbaar gebouw": 270,
    "bijgebouw / garage / tuinconstructie": 265, "bijgebouw": 265, "ander": 309,
}
TYPE_AANVRAAG = {
    "nieuwbouw": 272, "renovatie": 273, "uitbreiding / aanbouw": 274, "uitbreiding": 274,
    "dragende muur afbreken en/of ligger berekenen": 284, "dragende muur": 284,
}


def nu():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sleutel(t):
    t = (t or "").strip().lower()
    for a, b in (("ë", "e"), ("é", "e"), ("è", "e"), ("ï", "i"), ("ö", "o"), ("ü", "u"), ("ç", "c")):
        t = t.replace(a, b)
    return t


# ---------- Pipedrive ----------

def pd(pad, method="GET", body=None, _firma=None, **params):
    """Roept Pipedrive aan. Zonder _firma is dat het account van UNABO,
    precies zoals dit altijd werkte."""
    basis, token = (PD, PD_TOKEN)
    if _firma:
        token = os.environ.get(_firma["token_env"], "")
        if not token:
            raise RuntimeError(f"geen token {_firma['token_env']} voor {_firma['naam']}")
        basis = _firma["api"]
    params["api_token"] = token
    url = f"{basis}{pad}?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode())


def persoon_aanmaken(a, firma):
    """Maakt de persoon rechtstreeks in Pipedrive aan.

    Alleen voor accounts zonder sync vanuit Google Contacts. Daar kan geen
    dubbel contact ontstaan, want dat account kent maar een bron.
    """
    voor, achter = a.get("voornaam", ""), a.get("achternaam", "")
    body = {"name": f"{voor} {achter}".strip() or (a.get("email") or "Onbekend")}
    if a.get("email"):
        body["email"] = [{"value": a["email"], "primary": True}]
    if a.get("telefoon"):
        body["phone"] = [{"value": a["telefoon"], "primary": True}]
    return pd("/persons", method="POST", body=body, _firma=firma)["data"]["id"]


def zoek_persoon(email, firma=None):
    """Zoekt de persoon op e-mailadres in het account van de firma."""
    if not email:
        return None
    r = pd("/persons/search", term=email, fields="email", exact_match="true", limit=5,
           _firma=firma)
    items = (r.get("data") or {}).get("items") or []
    for it in items:
        p = it.get("item") or {}
        for e in p.get("emails") or []:
            if (e or "").strip().lower() == email.strip().lower():
                return p.get("id")
    return items[0]["item"]["id"] if items else None


# ---------- Google Contacts ----------

def google_client():
    sys.path.insert(0, "/srv/app")
    sys.path.insert(0, os.path.expanduser("~/appportal/contactsync"))
    from app.google_client import GoogleContactsClient  # noqa: E402
    pad = os.environ.get("GOOGLE_TOKEN_PATH", "/data/google_token.json")
    return GoogleContactsClient(pad)


def google_contact_aanmaken(a):
    """Maakt het contact in de container van contactsync, die de sleutel heeft."""
    voor, achter = a["voornaam"], a["achternaam"]
    body = {
        "names": [{"givenName": f"PA {voor} {achter}".strip(), "familyName": voor}],
        "emailAddresses": [{"value": a["email"]}] if a.get("email") else [],
        "phoneNumbers": [{"value": a["telefoon"]}] if a.get("telefoon") else [],
        "addresses": [{"formattedValue": a["adres"]}] if a.get("adres") else [],
    }
    script = (
        "import sys,os,json;sys.path.insert(0,'/srv/app');"
        "from app.google_client import GoogleContactsClient as G;"
        "c=G(os.environ.get('GOOGLE_TOKEN_PATH','/data/google_token.json'));"
        "b=json.loads(sys.stdin.read());"
        "print(c.create_contact(b))"
    )
    import subprocess
    p = subprocess.run(
        ["docker", "exec", "-i", "appportal-app-contactsync-1", "python", "-c", script],
        input=json.dumps(body), capture_output=True, text=True, timeout=90)
    if p.returncode != 0:
        raise RuntimeError("google-contact aanmaken mislukt: " + (p.stderr or "")[-300:])
    return (p.stdout or "").strip().splitlines()[-1]


# ---------- routering ----------

def kies_pipeline(diensten):
    treffers = []
    for d in diensten or []:
        k = sleutel(d)
        for naam, pp in DIENST_PIPELINE.items():
            if naam in k or k in naam:
                treffers.append(pp)
                break
    treffers = list(dict.fromkeys(treffers))
    if len(treffers) > 1:
        return BUNDEL, LABEL_WEBSITE
    if len(treffers) == 1:
        return treffers[0], LABEL_WEBSITE
    return ONBEKEND, LABEL_TE_ROUTEREN


def optie(tabel, waarde):
    k = sleutel(waarde)
    if not k:
        return None
    if k in tabel:
        return tabel[k]
    for naam, i in tabel.items():
        if naam in k or k in naam:
            return i
    return None


# ---------- verwerking ----------

def verwerk(conn, rij, droog=False):
    a = json.loads(rij["payload"])
    a.setdefault("voornaam", "")
    a.setdefault("achternaam", "")
    if not a["voornaam"] and not a.get("email"):
        raise ValueError("aanvraag zonder naam en zonder e-mail")

    firma = firma_van(rij["bron"])
    if firma:
        # Eigen Pipedrive-account: een vaste pijplijn voor elke websiteaanvraag.
        (pipeline, fase), label = firma["pipeline"], firma["label"]
    else:
        (pipeline, fase), label = kies_pipeline(a.get("diensten"))
    titel = (a.get("adres") or "").strip() or f"{a['voornaam']} {a['achternaam']}".strip() or "Aanvraag via website"

    if droog:
        waar = firma["naam"] if firma else "UNABO (standaard)"
        print(f"  #{rij['id']} [{rij['bron']}] zou worden: {waar}, pipeline {pipeline}, "
              f"fase {fase}, label {label}, titel '{titel}'")
        return

    persoon = rij["persoon_id"]
    if firma and not firma["contactsync"]:
        # Naar dit account loopt geen sync vanuit Google Contacts, dus zoeken wij
        # de persoon zelf op en maken hem anders meteen aan.
        if not persoon:
            persoon = zoek_persoon(a.get("email"), firma=firma)
        if not persoon:
            persoon = persoon_aanmaken(a, firma)
        conn.execute("UPDATE aanvraag SET persoon_id=? WHERE id=?", (persoon, rij["id"]))
        conn.commit()
    else:
        # 1. Google-contact
        google_id = rij["google_id"]
        if not google_id:
            google_id = google_contact_aanmaken(a)
            conn.execute("UPDATE aanvraag SET google_id=? WHERE id=?", (google_id, rij["id"]))
            conn.commit()

        # 2. wachten tot de sync hem in Pipedrive heeft gezet
        if not persoon:
            einde = time.time() + SYNC_GEDULD
            while time.time() < einde:
                persoon = zoek_persoon(a.get("email"))
                if persoon:
                    break
                time.sleep(SYNC_INTERVAL)
            if not persoon:
                raise TimeoutError(
                    f"persoon staat na {SYNC_GEDULD // 60} minuten nog niet in Pipedrive "
                    "(sync van Google Contacts loopt achter of ligt stil)")
            conn.execute("UPDATE aanvraag SET persoon_id=? WHERE id=?", (persoon, rij["id"]))
            conn.commit()

    # 3. deal
    body = {
        "title": titel,
        "person_id": persoon,
        "pipeline_id": pipeline,
        "stage_id": fase,
        "label": label,
    }
    if not firma:
        # Deze veld-ids zijn die van UNABO en bestaan niet in een ander account.
        # Wat erin stond, komt daar in de notitie terecht.
        g = optie(GEBOUWTYPE, a.get("gebouwtype"))
        if g:
            body[VELD_GEBOUWTYPE] = g
        t = optie(TYPE_AANVRAAG, a.get("type_aanvraag"))
        if t:
            body[VELD_TYPE_AANVRAAG] = t

    deal = pd("/deals", method="POST", body=body, _firma=firma)["data"]["id"]

    regels = [f"Aanvraag via het formulier op {a.get('pagina') or 'unabo.be'}."]
    if firma:
        for k, lab in (("gebouwtype", "Gebouwtype"), ("type_aanvraag", "Aard van de werken")):
            if a.get(k):
                regels.append(f"{lab}: {a[k]}")
    if a.get("diensten"):
        regels.append("Gevraagde diensten: " + ", ".join(a["diensten"]))
    for k, lab in (("gevonden_via", "Gevonden via"), ("telefoon", "Telefoon"), ("email", "E-mail")):
        if a.get(k):
            regels.append(f"{lab}: {a[k]}")
    if a.get("omschrijving"):
        regels.append("\nOmschrijving van de klant:\n" + a["omschrijving"])
    pd("/notes", method="POST", body={"deal_id": deal, "content": "\n".join(regels)}, _firma=firma)

    conn.execute(
        "UPDATE aanvraag SET status='klaar', deal_id=?, verwerkt=?, laatste_fout='' WHERE id=?",
        (deal, nu(), rij["id"]))
    conn.commit()
    print(f"  #{rij['id']} -> {firma['naam'] if firma else 'UNABO'}: deal {deal} "
          f"({titel}) in pipeline {pipeline}, persoon {persoon}")


def meld_vastgelopen(rij, fout):
    """Een aanvraag die het niet redt hoort op het board, niet in een logbestand."""
    if not AGENTS_TOKEN:
        return
    body = {"naam": "de-dealmaker", "status": "fout", "taak": "aanvragen van de website",
            "detail": f"aanvraag #{rij['id']} loopt vast"[:400],
            "voorstel": {
                "actie": f"Aanvraag #{rij['id']} van de website is niet in Pipedrive geraakt",
                "runbook": "sales-signaal",
                "doel": f"aanvraag:{rij['id']}",
                "reden": (f"Na {MAX_POGINGEN} pogingen nog steeds mis: {fout} "
                          "De inzending staat veilig in de wachtrij en in WPForms; "
                          "ze moet met de hand worden ingevoerd of de oorzaak verholpen.")[:400]}}
    req = urllib.request.Request(PLATFORM + "/agent-status", data=json.dumps(body).encode(), method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Agents-Token", AGENTS_TOKEN)
    try:
        urllib.request.urlopen(req, timeout=20).read()
    except Exception:  # noqa: BLE001
        pass


def main(argv):
    droog = "--droog" in argv
    if not os.path.exists(DB):
        print(f"{nu()} geen wachtrij op {DB}")
        return 0
    conn = sqlite3.connect(DB, timeout=30)
    conn.row_factory = sqlite3.Row
    rijen = conn.execute(
        "SELECT * FROM aanvraag WHERE status='wacht' AND pogingen < ? ORDER BY id", (MAX_POGINGEN,)).fetchall()
    if not rijen:
        conn.close()
        return 0

    print(f"{nu()} {len(rijen)} aanvraag/aanvragen in de rij")
    for rij in rijen:
        try:
            verwerk(conn, rij, droog)
        except Exception as e:  # noqa: BLE001
            fout = f"{type(e).__name__}: {e}"[:400]
            pogingen = rij["pogingen"] + 1
            vast = pogingen >= MAX_POGINGEN
            conn.execute(
                "UPDATE aanvraag SET pogingen=?, laatste_fout=?, status=? WHERE id=?",
                (pogingen, fout, "vast" if vast else "wacht", rij["id"]))
            conn.commit()
            print(f"  #{rij['id']} MISLUKT ({pogingen}/{MAX_POGINGEN}): {fout}")
            if vast:
                meld_vastgelopen(rij, fout)
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
