# Nummerreservering per voorstel (WP2b)

Versie 1.0, 12-10-2026. Uitgevoerd door Claude voor Mehdi Chegini, op basis van de vervolgopdracht contracten v1.0 (12-10-2026), punt 1. Alleen H-Architects, Pipedrive bedrijf-id 10068585.

## Wat er gebeurde met 2617

Alleen-lezen gereconstrueerd op 12-10-2026. Er is niets uitgevoerd, hernummerd of verwijderd.

| Bron | Vindplaats | Wat er staat |
|---|---|---|
| Agentbord | `mijnagents-data/mijnagents.db`, tabel `voorstel` | Drie **open** voorstellen met 2617: 25 (deal 14543, Nelleke Stropke, 05-10-2026 08:32), 26 (deal 14566, Paulina Andrzejczyk, 10-10-2026 21:03), 27 (deal 14518, Koen Van Den Steen, 10-10-2026 23:04). Geen enkel voorstel is goedgekeurd. |
| Pipedrive | deals 14543, 14566, 14518 | De titels dragen geen nummer ("Nelleke Stropke", "Paulina Andrzejczyk", "Koen Van Den Steen (ex H-A 2451)"). 2617 staat alleen in de notities van de agent. |
| Dashboard | MCP `voorbereidingen`, `zoek` | De drie dossiers staan op "te vervolledigen" en het projectnummer ontbreekt. Er is geen dossier met 2617. |
| Contractmappen | `0 H-A Contracts clients/2026 Design` en `2026 Signed` | Het hoogste nummer is 2616. Er is geen bestand met 2617. |
| Salesmappen | `o01. Sales` | Er is geen map met 2617. |

Besluit: 2617 is **alleen een voorstel**, drie keer gedaan en nergens goedgekeurd of gebruikt.

Oorzaak: de agent las vier bronnen, maar geen open voorstellen. Het bord ontdubbelde per deal en niet per nummer. Zo kreeg elke ronde tussen 05 en 10-10 hetzelfde volgende nummer.

## Wat er nu geldt

1. **Bord.** De tabel `nummerreservering` heeft twee unieke indexen, op (firma, nummer) en op (firma, deal), zolang het voorstel open of goedgekeurd is.
   - Een dealtitel-voorstel en zijn reservering worden samen bewaard in één transactie onder `BEGIN IMMEDIATE`.
   - Mogelijke uitkomsten: `gereserveerd`, `bestaat` (zelfde deal, zelfde nummer: idempotent), `bezet` (een andere deal), `eerder_geweigerd` of `geweigerd` (ongeldig, andere firma, of een goedgekeurd voorstel dat niet stilzwijgend mag veranderen).
2. **Akkoord.** Goedkeuren controleert opnieuw onder grendel. Staat hetzelfde nummer nog in een ander open of goedgekeurd voorstel voor een andere deal, dan weigert het bord (409) en noemt het die voorstellen. Op het bord staat het conflict bij het voorstel en is de knop Goedkeuren uitgeschakeld.
3. **Vrijgave.** Een reservering komt vrij wanneer het voorstel geweigerd, vervangen, mislukt of overgeslagen is. Ze vervalt nooit vanzelf na een tijd.
4. **Uitvoering.** Het runbook `pipedrive-dealtitel` vraagt vlak vóór de PUT `/api/nummercontrole`. Het voorstel moet goedgekeurd zijn, een actieve reservering hebben, en mag geen conflict hebben. Daarna leest het runbook de vier vaste bronnen opnieuw volledig.
   - Bij een bronfout of een nummer dat inmiddels elders gebruikt is: geen schrijfactie, en het voorstel krijgt "mislukt" met bewijs.
   - Een ander nummer wordt een nieuw voorstel voor Mehdi.
5. **Agent.** De nummers van open en goedgekeurde voorstellen tellen mee als vijfde bron (`/api/nummerreserveringen`); een onbereikbaar bord geeft geen nummer.
   - Een deal die al een voorstel heeft, houdt dat nummer.
   - Staat dat nummer ook in een voorstel voor een andere deal, dan stelt de agent niets nieuws voor: Mehdi beslist.
   - De agent leest de uitkomst van de reservering terug en meldt het voorstel alleen als het bewaard is.
6. **Oude voorstellen.** Voorstellen van vóór WP2b (zoals 25, 26 en 27) tellen afgeleid mee als bezet. Er is geen historische migratie. Het groepsregister valt erbuiten.

## Wat Mehdi doet

Op het agentbord kan geen van de drie voorstellen voor 2617 goedgekeurd worden zolang de andere twee open staan.

Kies wie 2617 krijgt en weiger de andere twee. Dan:
- keurt het bord het gekozen voorstel goed en legt het de reservering vast;
- stelt de agent in de volgende ronde voor de andere twee deals een nieuw nummer voor (2618, 2619), elk als eigen voorstel.

Bij Paulina staat het contracttype nog open (architectuur 26xx of regularisatie 56xx). Weiger haar voorstel dus tot dat beslist is.

## Grendels

- **`mijnagents/test_nummerreservering.py`** (34 controles, ook in de Docker-build). Gedekt:
  - opeenvolgende en gelijktijdige aanvragen (8 draden);
  - de unieke index zelf;
  - een goedgekeurd voorstel van een andere deal;
  - een herstart;
  - dezelfde deal opnieuw;
  - een verkeerde firma;
  - weigeren, vervangen en mislukken;
  - oude dubbele voorstellen met het geweigerde akkoord;
  - de controle vóór uitvoering.
- **`mijnagents-runner/tests/test_nummerreservering.py`** (18 controles, workflow `nummer-grendels`). Gedekt:
  - de vijfde bron en de idempotentie per deal;
  - een betwist nummer;
  - een nummer dat na het voorstel elders gebruikt is;
  - een bronfout en een onvolledige bordlijst;
  - de uitkomst teruglezen;
  - het runbook zonder PUT bij elke verliezende of onzekere uitvoering.
- **Bestaande grendels:** `test_nummeruitgifte.py` (12) en `test_nummerroutes.py` en `test_benaming.py` (50) slagen.
