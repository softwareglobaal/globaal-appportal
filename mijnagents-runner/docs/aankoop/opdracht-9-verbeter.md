# Opdracht driehoeksoverleg: verbeterronde De Prijsonderzoeker (01-11-2026)

Lees alleen; wijzig niets. Nummer je punten zoals het script vraagt (Codex X1, Gemini G1, Claude K1).

## Waarom deze ronde

De Prijsonderzoeker staat sinds 30-10-2026 live als proef (main, `mijnagents-runner/prijsonderzoeker.py`, pakket
`mijnagents-runner/aankoop/`, werkwijze `mijnagents-runner/werkwijze/prijsonderzoeker.md`). Mehdi zei op 01-11-2026 in
de chat "Ja, verbeteren" na de tweede proefvraag. Dezelfde vraag als op 30-10:

> MOVA V70 Ultra robotstofzuiger met dweilfunctie, nieuw of refurbished, tweedehands mag ook. Voor privé. Levering in
> België; het toestel gaat daarna naar Suriname (220 V, 60 Hz). Zoek de beste totaalprijs in Europa. Tegen half november.

## Meting van de tweede proef (01-11-2026, klaarzet 4024 op het bord)

- Verbruik: 404.791 tokens in een enkele API-aanvraag (een beurt, einde `end_turn`), 5 zoekopdrachten, 6 leesbeurten
  waarvan 4 geslaagd. Bij Claude Opus 5.5 ($4 input, $20 output per miljoen) is dat ongeveer 1,7 tot 2 dollar. De
  eerste proef (30-10, zonder grenzen) gebruikte 4,27 miljoen tokens. Mehdi gaf zijn ja op de herhaling bij "geschat
  2 dollar per vraag".
- Uitkomst: geen aanbeveling, 0 aanbiedingen in het verslag, 2 afgewezen omdat ze "niet meer beschikbaar" waren
  (technik-studio.de en coolblue.nl; die afwijzing klopt).
- "Niet gevonden" in het verslag (tekst van het model, zonder links):
  - netspanning en netfrequentie van het basisstation staan op geen enkele gelezen pagina (mova.tech productpagina,
    Coolblue, technik-studio), dus compatibiliteit met 220 V 60 Hz onbekend;
  - MediaMarkt.de (949 euro nieuw, 901,55 refurbished volgens zoekresultaat): pagina niet leesbaar;
  - Vanden Borre BE (1.399 euro volgens zoekresultaat): gelezen pagina afgekapt voor de prijs;
  - Coolblue tweedekans (vanaf 751 euro volgens zoekresultaat): niet op de gelezen pagina;
  - Marktplaats-advertentie: pagina niet leesbaar;
  - Bol, Amazon, Galaxus, Otto, notebooksbilliger niet gelezen en veilingen/tweedehands niet doorzocht wegens de grenzen.
- Het model stelde een goede vervolgvraag (ook de Complete X? mag een DE/NL-winkel die niet naar België levert?).

## Wat de code nu doet (bestand:regel op deze tak, gelijk aan main)

- `aankoop/onderzoek.py:17-27`: basisversies `web_search_20250305` en `web_fetch_20250910`, 6 zoek, 6 lees,
  `max_content_tokens` 6.000 per pagina, plafond 300.000 tokens. Het plafond wordt alleen tussen beurten getoetst
  (`onderzoek.py:180`); binnen een aanvraag loopt de server zelf door zijn zoek- en leesstappen.
- `onderzoek.py:198-206`: geen prompt caching; het logboek bewaart alleen input plus output per beurt, niet de
  cache- of servertool-tellers uit `usage`.
- `onderzoek.py:1-8` en `:94-104`: de basisversies zijn gekozen omdat hun `web_fetch_tool_result` de url en de tekst
  van de gelezen pagina dragen; de code bewijst daarmee dat een prijs echt op die pagina staat. De nieuwe versies
  `web_search_20260209` en `web_fetch_20260209` filteren dynamisch (het model schrijft code die de pagina filtert voor
  ze de context in gaat; minder tokens). De documentatie zegt niet of het resultaatblok dan nog de volledige tekst
  van de pagina draagt. Dat is niet gemeten.
- `aankoop/aanbod.py:355-371` en `:382-413`: een "ja" op netspanning of netfrequentie telt alleen met een citaat van
  de eigen aanbodpagina, met die waarde, en niet als de pagina ook de andere frequentie noemt zonder 50/60 Hz.
  Winkelpagina's noemen zelden spanning of Hz, dus voor Suriname kan er in de praktijk nooit een aanbeveling komen.
- `aanbod.py:473-475`: alleen een aanbod met volledig totaal en compatibel "ja" kan beste of reserve zijn.
- Het verslag (`aankoop/verslag.py`) toont "Niet gevonden" als vrije tekst van het model, zonder links. Prijzen uit
  zoekresultaten staan daar wel, maar Mehdi kan ze niet aanklikken.
- Met de hand draaien: de runner heeft `~/agents/.venv/bin/python` nodig (De Regisseur gebruikt die al,
  `regisseur.py:103`); met `/usr/bin/python3` faalt hij op `import anthropic` (01-11, zonder kosten).

## Wat het overleg moet beslissen

Geef per punt een concreet advies met reden en waar het kan bestand:regel. Hou het klein: de agent moet bij deze
vraag een bruikbaar verslag geven, binnen ongeveer 2 dollar per vraag.

1. **Bewijs voor spanning en frequentie.** Mag een netspanning- of netfrequentie-citaat van een andere gelezen pagina
   komen dan de aanbodpagina (fabrikant, handleiding, specificatieblad), als die pagina hetzelfde exacte model of
   dezelfde modelcode noemt als het aanbod? Hoe voorkom je dat een Amerikaanse of andere variant het bewijs levert
   (modelcode op beide pagina's, 50/60 Hz-regel, accessoire-regel)? Moet de werkwijze een zoek- en leesbeurt
   reserveren voor de handleiding of het specificatieblad?
2. **Afgekapte pagina's.** Winkelpagina's zijn groot; bij 6.000 tokens viel de prijs eraf. Een hogere grens (welke),
   minder pagina's, of de nieuwe toolversies met dynamisch filteren? Als je de nieuwe versies kiest: hoe blijft de
   paginaproef (`onderzoek.py:94-104`) gelden, en moet dat eerst met een goedkope meting bewezen worden?
3. **Kosten binnen een beurt.** Het plafond geldt alleen tussen beurten. Wat beperkt de kosten binnen een aanvraag:
   prompt caching (`cache_control` op de aanvraag), een `task_budget` (beta `task-budgets-2026-03-13`, Opus 5.5 kan
   het; een advies-plafond dat het model zelf ziet), minder `max_uses` per aanvraag, of iets anders? Welke tellers uit
   `usage` moet het logboek bewaren om het volgende verbruik echt te meten (input, output, cache, aantal
   zoek- en leesbeurten)?
4. **Wat niet nagekeken kon worden.** Prijzen die het model alleen in een zoekresultaat zag of op een pagina die niet
   leesbaar was: weglaten (zoals nu, als vrije tekst), of als aparte lijst "gezien, niet nagekeken" met klikbare link,
   nooit als beste of reserve, en alleen met een url die echt in een zoekresultaat van deze ronde stond?
5. **Grenzen per vraag.** Blijft het 6 zoek en 6 lees, of anders (bijvoorbeeld meer zoeken voor tweedehands en
   veilingen)? Wat is de verwachte kost per vraag met je voorstel? Meer dan ongeveer 2 dollar per vraag is een
   `GRENS:` voor Mehdi.
6. **Tests vooraf.** Welke goede en foute voorbeelden worden tests (bijvoorbeeld: een 60 Hz-citaat uit de handleiding
   van een andere modelcode telt niet; een niet-nagekeken prijs kan nooit beste zijn; een url die in geen enkel
   zoekresultaat stond, komt niet in de lijst)?
7. **Proef na de bouw.** Dezelfde vraag nog een keer draaien om te meten, of eerst een goedkopere controle?

## Grenzen voor dit overleg

- Niemand bestelt, biedt of contacteert iets. Het gaat over het ontwerp van de agent.
- Meer dan ongeveer 2 dollar per vraag, een betaalde bron of een account bij een winkel is een `GRENS:` voor Mehdi.
- Hou je aan AGENTNORM (`mijnagents-runner/AGENTNORM.md`) en aan de bestaande grendels: geen aanbod zonder gelezen
  pagina, geen prijs zonder citaat, geen aanbeveling zonder volledig totaal en compatibel "ja".
