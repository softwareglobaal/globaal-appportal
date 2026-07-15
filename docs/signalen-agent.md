# Signalen-agent (archetype 2)

Automatische bewaking van de bedrijfsdata: vaste regels detecteren
afwijkingen, de AI duidt ze. Besluit Shaniel 2026-07-15 (AI-agent-brainstorm);
gebouwd in de organisatie-app (`signalen.py`, migratie 066, tab Signalen op
organisatie.globaal.be).

## Waarom twee lagen (en niet elk uur een AI-call)

Onderzoek naar hoe vergelijkbare bedrijven dit draaien (o.a. Anthropic's
"Building Effective Agents" en de gangbare praktijk bij alert-triage) wijst
een kant op: de betrouwbare systemen in productie zijn workflows met vaste
regels, waarbij het taalmodel alleen de stap doet die regels niet kunnen
(prioriteren, bundelen, in gewone taal uitleggen wat te doen). Een LLM die
elk uur zelf de data doorzoekt is duurder, trager en niet reproduceerbaar.

Daarom:

1. **Detectoren** (laag 1): gewone SQL in de organisatie-app, standaard elk
   uur (`SIGNALEN_MIN`). Kost niets. Bevindingen komen in
   `organisatie.signaal` met een vingerafdruk: geen dubbels, en een signaal
   sluit vanzelf (`opgelost_op`) zodra de oorzaak weg is.
2. **AI-duiding** (laag 2): een keer per dag (na `SIGNALEN_DUIDING_UUR`,
   standaard 6u UTC) vat Claude de open signalen samen: prioriteit plus
   eerstvolgende actie per punt. Komt er tussendoor een nieuw signaal met
   ernst 'hoog' bij, dan volgt direct een extra duiding (escalatie, hooguit
   een per uur). Zelfde sleutel (`ANTHROPIC_API_KEY`) en model
   (`AI_MODEL`, claude-sonnet-5) als de dagbriefing.

## Detectoren v1

| code | wat | ernst |
|---|---|---|
| `octopus_sync` | sync faalt, of data ouder dan 24 uur | middel / hoog |
| `dossier_leeg` | dossier met 0 boekingen in de spiegel (High Design Studio-les) | middel |
| `grote_boeking` | aankoop of verkoop van minstens `SIGNALEN_GROTE_BOEKING_EUR` (standaard 25.000) in de laatste 7 dagen | middel |
| `maand_uitschieter` | aankopen vorige maand minstens dubbel het maandgemiddelde ervoor (en minstens 5.000) | middel |

Nieuwe detectoren zijn een functie plus een regel in `DETECTOREN` in
`signalen.py`; verder niets. Kandidaten: vervallen facturen
(verval_datum), contactsync-stilte, DeskTime-afwijkingen.

## Kosten (gemeten prijzen 2026-07, claude-sonnet-5)

Sonnet 5 kost $3 per miljoen input-tokens en $15 per miljoen output-tokens
(introductietarief tot 2026-08-31: $2/$10). Een duiding-call is klein
(signalenlijst in, ~150 woorden uit): ruwweg een halve dollarcent per call.

| ritme | AI-calls | kosten per maand |
|---|---|---|
| dagelijks + escalaties (gekozen) | ~30-45 | ~1 euro |
| elk uur een LLM-call (afgewezen) | ~720 | ~25-40 euro, zonder meerwaarde |

De detectoren zelf zijn SQL en kosten niets. Ter vergelijking: de
dagbriefing (1 call per dag met de hele graaf als context) is de duurste
bestaande AI-post en blijft ook op enkele euro's per maand.

## Vangrails (afspraken uit de brainstorm)

- Alleen-lezen op de bedrijfsdata; de agent schrijft uitsluitend in de
  eigen tabellen `organisatie.signaal` en `organisatie.signaal_duiding`.
- Geen DELETE-rechten: opgeloste signalen en oude duidingen blijven staan
  als historie.
- `communicatie.geheim` (PIN/PUK) komt nooit in een detector of duiding.
- De AI stelt voor; een mens beslist. Duidingen zijn tekst, geen acties.
