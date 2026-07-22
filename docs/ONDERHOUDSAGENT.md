# Onderhoudsagent: autonoom onderhoud van de AppPortal-apps

Doel (Shaniel, 2026-07-22): onderhoud en foutherstel gebeuren autonoom, niet
pas nadat een mens vraagt "kijk eens naar app X". Een agent checkt elke app op
een vaste cadans, duidt de bevindingen en grijpt binnen een afgesproken grens
zelf in. We rekenen niet op mensen voor het routineonderhoud.

## De keten

1. **Sonde** (`scripts/gezondheid.py`): deterministisch, geen AI. Verzamelt per
   app container-status, herstarts, foutregels in de logs (24u) en
   dataverse-checks (sync-vlaggen, versheid). Schrijft `~/gezondheid-laatste.json`.
   Mag zo vaak draaien als gewenst; kost niets.
2. **Duiding** (agent, architect/reviewer-rol): leest de sonde-uitvoer, oordeelt
   gezond / verzwakt / stuk en bepaalt bij stuk de oorzaak en een fix.
3. **Handelen in tiers** (zie hieronder).
4. **Melden** (`.claude/hooks/agent-event.sh` + push): elke ingreep en elk
   openstaand punt komt op de Onderhoud-tab en als melding.

## Autonomie-grens (besluit Shaniel 2026-07-22: "auto-fix veilige klasse")

### Veilige klasse: agent mag zelf handelen en mergen (na groene verifier)
- Een hangende of `unhealthy` container herstarten.
- Een mislukte spiegelsync opnieuw draaien.
- Een sync-race dichten met een advisory lock (zie [poller-race], commit 54b140a
  is het ijkpunt): puur defensieve serialisatie, geen gedragswijziging.
- Een verlopen versheidsdrempel/cron herstellen die aantoonbaar stilstond.
- Voorwaarde altijd: de verifier draait de controles (py_compile, render +
  V8-parse bij frontend, toegangsmatrix bij routes) en die zijn groen; de diff
  raakt alleen het gemelde probleem; geen schema- of rechtenwijziging.

### Buiten de veilige klasse: PR + melding, mens merget
- Elke schemawijziging (migratie), elke wijziging aan grants/rollen/toegang.
- Elke gedragswijziging in de UI of de berekeningen (bedragen, KPI's, matching).
- Alles wat data verwijdert of overschrijft buiten een idempotente re-sync.
- Alles waarvan de agent de oorzaak niet met zekerheid kent: dan alleen een
  volledige diagnose melden, niet ingrijpen.

### Nooit
- Secrets in beeld of in git. Productie-migraties zonder mens. CAPTCHA's.
  Externe berichten namens iemand. Onomkeerbaar verwijderen.

## Cadans en kosten

De sonde draait via cron op de VM. De duiding + het handelen vragen een
headless Claude-run: dat loopt op de API met een **uitgavenlimiet**, niet op
het abonnement (zelfde fase-2-conclusie als het agentic-AI-spoor). Zonder die
gecapte sleutel draait alleen de sonde en de melding; het autonoom fixen wacht
op die sleutel. Aanbevolen cadans: sonde elk uur, volledige agent-ronde 1x per
dag plus direct bij een `aandacht`-melding uit de sonde.
