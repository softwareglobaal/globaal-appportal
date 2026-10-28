# Opdracht driehoeksoverleg: Agendawacht, vaste contacten (FR-211)

In drie hoeken overleggen. Claude, Codex en Gemini: stem per punt (eens / oneens / voorstel), met bewijs
(bestand:regel, invoer en uitkomst). Antwoord in het Nederlands, kort, zonder emoji en zonder gedachtestreepjes.

## Hoe Claude 1 dit draait
1. Geef deze opdracht aan Codex en aan Gemini, elk apart, met toegang tot repo `softwareglobaal/globaal-appportal` op `main`.
2. Plak hun antwoorden onder "Stem Codex" en "Stem Gemini" hieronder en push.
3. Claude 2 maakt daarna de stemtabel en verwerkt wat 2 van de 3 vragen.

## Context
- Op 28-10-2026 vond Mehdi vier fouten in zijn agenda van 29-10. Oorzaak en oplossing staan in FR-211
  (`mijnagents-runner/werkwijze/foutenregister.json`). De wijziging is commit `d4a1ae9` (PR 125), live sinds 28-10 23:47.
- Kort: '!! Mehdi en Catlain: HA 2605 plaatsbezoek' werd herschreven zonder Catalin (geen gast, geen uitnodiging);
  de boekhouder ('Nandien') en 'AI van EE afdeling' kregen een VR-vraag welke firma; afspraken zonder code stonden in
  de lichtgroene agendakleur en leken intern.
- Nieuw: `mehdi_kop`, `bekende_naam`, `_lijkt_op` in `agenda_wacht.py`; uitbreiding van `titel_voorstel`,
  `titels_normaliseren`, `kleur_gewenst`; tabel vaste contacten bovenaan `werkwijze/agenda-wacht.md` (v8.27).

## Punten om te stemmen
- P1. Tikfout-herkenning (een letter verschil, vanaf vijf letters, alleen als precies een bekende naam erop lijkt). Kan ze
  een verkeerde persoon als gast zetten of een uitnodigingsmail laten vertrekken naar wie dat niet hoort?
- P2. `mehdi_kop` houdt de namen voor de dubbele punt in een herschreven titel. Kan het een titel breken?
- P3. De boekhouder is altijd `[AL-LO]` (met `!!` `[AL-LB]`); 'afdeling' bij een eigen firma is intern. Valse positieven?
- P4. Een collega als agendagast houdt de codecorrectie niet meer tegen. Veilig?
- P5. Afspraak zonder code wordt grafiet (alleen als er nog geen kleur staat). Bijwerkingen?
- P6. Ontbreekt een test of grendel?
- P7. Het oude Google Apps Script `colorCodeEvents` (account mehdiprivewerkagenda, sinds 14-04-2025) zet elke 30 minuten
  kleuren om. Uitzetten of laten staan? (Grens: uitzetten vraagt Mehdi's ja.)

## Grenzen
Niets verwijderen, live zetten of versturen zonder Mehdi's ja. Geen echte afspraken wijzigen, alleen lezen.

## Stem Claude
Onafhankelijke review van `d4a1ae9`, 28-10-2026. De fixes staan in de vervolgcommit (FR-211, tweede alinea van de oplossing).
- P1 oneens: 'Mehdi en Karim' maakte via de bijnaam Karam Catalin gast, met uitnodigingsmail. Hersteld: zes letters, geen bijnaam.
- P2 oneens (klein): 'Mehdi + Werf' werd een naam, 'Mehdi met Catalin' viel weg. Hersteld: alleen bekende namen, 'met' scheidt.
- P3 oneens: 'nadeel' en 'boekhouden' werden boekhouder. Hersteld: alleen namen met hoofdletter, per relatie geteld.
- P4 eens: `_agendagasten` bevat alleen interne agenda-adressen; externe gasten houden de schrijfactie nog tegen.
- P5 oneens: grafiet op zorgschaduw en Calendly, en een blijvende melding in de zelfcontrole. Hersteld.
- P6 voorstel: negatieve tests. Toegevoegd in `tests/test_agendagasten.py`.
- P7 onthouding: grens, Mehdi beslist.
- Blijft open: 'Catalina' als gast na 'Mehdi' lijkt nog op Catalin.

## Stem Codex
(plakken)

## Stem Gemini
(plakken)
