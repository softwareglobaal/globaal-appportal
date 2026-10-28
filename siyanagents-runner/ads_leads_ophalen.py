#!/usr/bin/env python3
"""Haalt leads uit het leadformulier van de Google-advertenties van UNABO op en
zet ze in de gewone wachtrij van aanvraag_verwerk.py (deal + mail aan sales).

Waarom: het leadformulier in de advertenties (account 1907613111) had geen
webhook. Tussen 16 sep en 22 okt 2026 bleven zes leads in Google Ads hangen
zonder dat sales er ooit iets van zag. Een webhook vraagt een publiek eindpunt
met een eigen sleutel; dit script leest via de API wat er binnenkwam en heeft
dat allemaal niet nodig.

Cron (elk kwartier):
  */15 * * * * /usr/bin/flock -n /tmp/ads-leads.lock python3 ~/appportal/siyanagents-runner/ads_leads_ophalen.py >> ~/ads-leads.log 2>&1

Droogdraaien:  python3 ads_leads_ophalen.py --droog
"""
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "koppelingen"))
import googleads  # noqa: E402

KLANT = "1907613111"
DB = os.path.expanduser(os.environ.get("AANVRAAG_DB_HOST", "~/appportal/aanvraag-data/aanvragen.db"))
BRON = "google-ads-lead"
VANAF = "2026-09-01 00:00:00"

# Het formulier vraagt geen dienst: die leiden we af uit de campagne, zodat de
# deal in de juiste pijplijn komt (DIENST_PIPELINE in aanvraag_verwerk.py).
DIENST_PER_CAMPAGNE = (
    ("epb", "Energie"),
    ("energie", "Energie"),
    ("stabiliteit", "Stabiliteit"),
    ("3d", "3D-scanning"),
)


def dienst(campagne):
    c = (campagne or "").lower()
    for sleutel, d in DIENST_PER_CAMPAGNE:
        if sleutel in c:
            return [d]
    return []


def main(argv):
    droog = "--droog" in argv
    namen = {str(x["campaign"]["id"]): x["campaign"]["name"]
             for x in googleads.zoek(KLANT, "SELECT campaign.id, campaign.name FROM campaign")}
    rijen = googleads.zoek(KLANT, (
        "SELECT lead_form_submission_data.id, lead_form_submission_data.campaign, "
        "lead_form_submission_data.submission_date_time, "
        "lead_form_submission_data.lead_form_submission_fields, "
        "lead_form_submission_data.custom_lead_form_submission_fields "
        "FROM lead_form_submission_data "
        f"WHERE lead_form_submission_data.submission_date_time >= '{VANAF}'"))

    conn = sqlite3.connect(DB, timeout=30)
    bekend = {json.loads(p).get("ads_lead_id") for (p,) in
              conn.execute("SELECT payload FROM aanvraag WHERE bron=?", (BRON,))}
    nieuw = 0
    for r in rijen:
        d = r["leadFormSubmissionData"]
        if d["id"] in bekend:
            continue
        v = {f.get("fieldType"): f.get("fieldValue", "") for f in d.get("leadFormSubmissionFields", [])}
        eigen = [f"{c.get('questionText')}: {c.get('fieldValue')}"
                 for c in d.get("customLeadFormSubmissionFields", [])]
        campagne = namen.get(d.get("campaign", "").split("/")[-1], "onbekende campagne")
        tijd = datetime.fromisoformat(d["submissionDateTime"]).astimezone(timezone.utc)
        payload = {
            "tijdstip": tijd.isoformat(timespec="seconds"),
            "bron": BRON,
            "ads_lead_id": d["id"],
            "pagina": f"Google Ads-leadformulier ({campagne})",
            "herkomst": "Google Ads (leadformulier in de advertentie)",
            "voornaam": v.get("FIRST_NAME", ""),
            "achternaam": v.get("LAST_NAME", ""),
            "email": v.get("EMAIL", ""),
            "telefoon": v.get("PHONE_NUMBER", ""),
            "adres": v.get("CITY") or v.get("POSTAL_CODE") or "",
            "diensten": dienst(campagne),
            "gevonden_via": "Google Ads",
            "omschrijving": (
                f"Lead via het formulier in de Google-advertentie '{campagne}', "
                f"ingevuld op {tijd.astimezone().strftime('%d-%m-%Y %H:%M')}. "
                "Het formulier vraagt geen dienst en geen adres: bel de klant om te horen wat hij nodig heeft."
                + ("\n" + "\n".join(eigen) if eigen else "")),
        }
        print(f"{'(droog) ' if droog else ''}lead {d['id']} van {payload['tijdstip']} ({campagne}) -> wachtrij")
        if not droog:
            # ontvangen = nu, niet het tijdstip van de lead: de wachttijd op de
            # Google-sync en de noodmail tellen vanaf het moment dat wij hem kennen.
            conn.execute("INSERT INTO aanvraag(ontvangen, bron, payload, status) VALUES (?,?,?, 'wacht')",
                         (datetime.now(timezone.utc).isoformat(timespec="seconds"), BRON,
                          json.dumps(payload, ensure_ascii=False)))
            conn.commit()
        nieuw += 1
    conn.close()
    if nieuw:
        print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {nieuw} nieuwe lead(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
