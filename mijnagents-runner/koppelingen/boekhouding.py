"""Abonnementen en software-uitgaven uit de boekhouding van de groep, alleen lezen.

Twee bronnen in de appportal-Postgres (dezelfde als het kosten- en organisatiedashboard):
  - kosten.bank_transactie: de Visa-uitgavenstaten per firma (vendor al genormaliseerd, bv.
    "OpenAI / ChatGPT", "Claude (Anthropic)", "Wispr Flow"), bron = pdf van de uitgavenstaat.
  - finance.octopus_boeking + octopus_relatie: de aankoopfacturen in Octopus per dossier
    (Pipedrive, Microsoft, Zoom, ... die wél een factuur in de boekhouding hebben).
  - uitgaven.leverancier: de leverancierslijst met de vlag is_ai.
Lezen via docker exec in de Postgres-container (zoals organisatie.py); geen wachtwoord in code.
"""
import json
import os
import subprocess

CONTAINER = os.environ.get("KERN_POSTGRES_CONTAINER", "appportal-postgresql-1")
DB = os.environ.get("KERN_DB", "appportal")
# woorden waarop we een software-/abonnementsleverancier herkennen (aanvullen in de werkwijze van De Licentiewacht)
SAAS = ("wispr|anthropic|openai|chatgpt|claude|google|dropbox|monday|xelion|microsoft|adobe|zoom|fathom|plaud|calendly|pipedrive|notion|canva|"
        "telegram|apple|granola|cursor|github|slack|figma|midjourney|elevenlabs|perplexity|gemini|openrouter|replit|runway|surfer|tactiq|grok|"
        "glitch|linkedin|meta|facebook|instagram|autodesk|vectorworks|sketchup|enscape|twinmotion|lumion|bluebeam|docusign|pandadoc|"
        "quickbooks|octopus|exact|teamleader|hubspot|mailchimp|brevo|wix|squarespace|godaddy|combell|one\\.com|ovh|hetzner|aws|amazon web|"
        "digitalocean|cloudflare|twilio|deepgram|assembly|otter|fireflies|loom|miro|asana|trello|clickup|jira|atlassian|1password|lastpass|"
        "nordvpn|zapier|make\\.com|n8n|airtable|smartsheet|typeform|jotform|calendly|doodle|dext|yuki|billit|invoiceflow|payfit|sd worx")


def _psql(sql):
    gebruiker = subprocess.run(["docker", "exec", CONTAINER, "sh", "-c", "echo $POSTGRES_USER"], capture_output=True, text=True, timeout=30).stdout.strip() or "postgres"
    uit = subprocess.run(["docker", "exec", CONTAINER, "psql", "-U", gebruiker, "-d", DB, "-At", "-c", sql], capture_output=True, text=True, timeout=120)
    if uit.returncode != 0:
        raise RuntimeError(uit.stderr.strip()[:300])
    return json.loads(uit.stdout.strip() or "[]") or []


def kaartlijnen(sinds):
    """Visa-uitgavenstaten: [{firma, datum, vendor, categorie, bedrag, omschrijving, bron}] (bedrag negatief = uitgave)."""
    return _psql(f"""select coalesce(json_agg(json_build_object('firma', firma_code, 'datum', datum, 'vendor', coalesce(vendor,''), 'categorie', coalesce(categorie,''),
                   'bedrag', bedrag, 'omschrijving', coalesce(omschrijving,''), 'bron', coalesce(bron,'')) order by datum), '[]'::json)
                   from kosten.bank_transactie where datum >= '{sinds}' and (vendor ~* '{SAAS}' or omschrijving ~* '{SAAS}')""")


def facturen(sinds):
    """Aankoopfacturen in Octopus van software-leveranciers: [{firma, datum, leverancier, bedrag, omschrijving, referentie}]."""
    return _psql(f"""select coalesce(json_agg(json_build_object('firma', k.firma_code, 'datum', b.document_datum, 'leverancier', coalesce(r.naam,''),
                   'bedrag', b.bedrag, 'omschrijving', coalesce(b.omschrijving,''), 'referentie', coalesce(b.referentie,''), 'journaal', b.journal_key) order by b.document_datum), '[]'::json)
                   from finance.octopus_boeking b
                   left join finance.octopus_relatie r on r.dossier_id=b.dossier_id and r.octopus_id=b.relatie_octopus_id
                   left join kosten.octopus_boekhouding k on k.dossier_id=b.dossier_id
                   where b.document_datum >= '{sinds}' and b.soort='buysell' and b.journal_key like 'A%'
                   and (r.naam ~* '{SAAS}' or b.omschrijving ~* '{SAAS}')""")


def ai_leveranciers():
    return _psql("select coalesce(json_agg(json_build_object('naam', naam, 'soort', soort, 'is_ai', is_ai) order by naam), '[]'::json) from uitgaven.leverancier")


def laatste_uitgavenstaat():
    """Per firma de jongste datum in de kaartlijnen: zegt hoe ver de import achterloopt."""
    return _psql("select coalesce(json_agg(json_build_object('firma', firma_code, 'tot', mx) order by firma_code), '[]'::json) from (select firma_code, max(datum) mx from kosten.bank_transactie group by 1) t")
