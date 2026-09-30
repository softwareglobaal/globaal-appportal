#!/usr/bin/env python3
"""Het WhatsApp-sjabloon 'agent_melding' aanvragen bij Meta, of de status ervan tonen.

Waarom: Meta laat een bedrijfsnummer Mehdi vrij schrijven binnen 24 uur nadat hij dat
nummer iets stuurde. Daarbuiten mag alleen een goedgekeurd sjabloon. Met dit sjabloon
komen de meldingen van De Bode ook door als hij een dag niets stuurde. Mehdi gaf op
30-09-2026 toestemming om het aan te vragen.

    whatsapp_sjabloon.py <waba-id>          status tonen; aanvragen als het er nog niet is

Het WABA-ID (WhatsApp Business Account-ID) staat in Meta Business Suite van de portfolio
UNABO VOF: Instellingen, Accounts, WhatsApp-accounts. Het token kan het niet zelf opzoeken.
Na goedkeuring: WA_SJABLOON=agent_melding in mijnagents-data/.env; De Bode gebruikt het dan.
Idempotent: bestaat het al, dan vraagt het niets opnieuw aan.
"""
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0] + "/koppelingen")
import whatsapp  # noqa: E402

NAAM, TAAL = "agent_melding", "nl"
TEKST = "Melding van {{1}}:\n\n{{2}}\n\nMeer op mijnagents.globaal.be."
VOORBEELD = ["je agents", "signaal: 3 mails wachten op antwoord (van De Mailregisseur) · verslag: werfbezoek klaar"]


def graph(pad, data=None, **q):
    env = whatsapp._env()
    q["access_token"] = env["META_WA_TOKEN"]
    url = f"https://graph.facebook.com/{env.get('META_GRAPH_VERSION', 'v26.0')}/{pad}?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, data=json.dumps(data).encode() if data else None,
                                 method="POST" if data else "GET", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        fout = json.load(e).get("error", {})
        sys.exit(f"Meta: {fout.get('code')} {fout.get('error_user_msg') or fout.get('message')}")


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        sys.exit(__doc__)
    waba = sys.argv[1]
    bestaand = [t for t in graph(f"{waba}/message_templates", fields="name,status,language,category", limit=100)["data"]
                if t["name"] == NAAM and t["language"] == TAAL]
    if bestaand:
        t = bestaand[0]
        print(f"{NAAM} ({TAAL}) bestaat al: {t['status']}, categorie {t['category']}")
        if t["status"] == "APPROVED":
            print("Zet WA_SJABLOON=agent_melding in mijnagents-data/.env; De Bode gebruikt het bij de volgende ronde.")
        return
    uit = graph(f"{waba}/message_templates", {
        "name": NAAM, "language": TAAL, "category": "UTILITY",
        "components": [{"type": "BODY", "text": TEKST, "example": {"body_text": [VOORBEELD]}}]})
    print(f"{NAAM} aangevraagd: id {uit.get('id')}, status {uit.get('status')}, categorie {uit.get('category')}")


if __name__ == "__main__":
    main()
