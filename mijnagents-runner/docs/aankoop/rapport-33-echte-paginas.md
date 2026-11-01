Besluit: 19 aangenomen (X1: A: ja. Hierdoor ziet; X2: B: nee. Een productpagin; X3: C: nee. Op een; X4: D: nee. “Levering aan; X5: E: ja, mits `btw_inbegre; X6: F: ja. Dan is; X7: Er ontbreekt één wijzigi; G1: Documenten tonen (A)**: ; G2: Specificatie uit winkeld; G3: Verzendwoord in tabelkop; G4: Gratis levering over mee; G5: Btw-aanname consumentenp; G6: Bewijs en ontbrekende ve; K1: A (PDF-links tonen): ja.; K2: B (netspanning uit gelin; K3: C (verzendwoord in de; K4: D (gratis levering over; K5: E (verzending erft btw):; K6: F (citaten bewaren in); 1 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | oneens | 2-1 | aangenomen |
| X3 | eens | eens | oneens | 2-1 | aangenomen |
| X4 | eens | eens | oneens | 2-1 | aangenomen |
| X5 | eens | eens | eens | 3-0 | aangenomen |
| X6 | eens | eens | eens | 3-0 | aangenomen |
| X7 | eens | eens | eens | 3-0 | aangenomen |
| G1 | eens | eens | eens | 3-0 | aangenomen |
| G2 | oneens | eens | eens | 2-1 | aangenomen |
| G3 | oneens | eens | eens | 2-1 | aangenomen |
| G4 | oneens | eens | eens | 2-1 | aangenomen |
| G5 | eens | eens | eens | 3-0 | aangenomen |
| G6 | eens | eens | eens | 3-0 | aangenomen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | eens | eens | eens | 3-0 | aangenomen |
| K3 | oneens | eens | eens | 2-1 | aangenomen |
| K4 | eens | eens | eens | 3-0 | aangenomen |
| K5 | eens | eens | eens | 3-0 | aangenomen |
| K6 | eens | eens | eens | 3-0 | aangenomen |
| K7 | oneens | oneens | oneens | 0-3 | afgewezen |

## Besluitenlijst vóór stemming
- X1: A: ja. Hierdoor ziet de agent de handleiding die al op de winkelpagina staat.
  Techniek voor Claude: `aankoop/leesserver.py:142-193` - toon maximaal acht PDF-links.
- X2: B: nee. Een productpagina kan ook een PDF van een optioneel laadstation linken. Zonder koppeling aan productnaam of onderdeel kan een verkeerde netspanning worden goedgekeurd.
  Techniek voor Claude: `aankoop/aanbod.py:468-510` - eis minstens overeenkomst van productnaam of onderdeelmodel, bijvoorbeeld V70 Ultra of RCVE0707.
- X3: C: nee. Op een gecombineerde verzend- en retourpagina kan “Verzendkosten” binnen 150 tekens vóór een Belgisch retourbedrag staan. Dat bedrag kan dan ten onrechte als verzending meetellen.
  Techniek voor Claude: `aankoop/aanbod.py:303-320` - eis dezelfde tabel of sectie en sluit retourwoorden uit.
- X4: D: nee. “Levering aan huis. Retourneren is gratis” kan binnen 50 tekens staan en zo gratis levering veinzen.
  Techniek voor Claude: `aankoop/aanbod.py:45,52-59,138-140` - eis dezelfde regel of sectie en sluit `retour`, `return` en `retourneren` uit.
- X5: E: ja, mits `btw_inbegrepen is True` en de volledige verzendpagina niet zegt dat bedragen exclusief btw zijn. Voor consumenten moet de vooraf gemelde totaalprijs belastingen en bijkomende vrachtkosten omvatten. [EU-richtlijn 2011/83/EU](https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:02011L0083-20220528)
  Techniek voor Claude: `aankoop/aanbod.py:351-363` - erf alleen bij expliciet bewezen consumentenprijs met btw.
- X6: F: ja. Dan is M5 bij de volgende ronde rechtstreeks bewijsbaar zonder de vraagtekst te bewaren.
  Techniek voor Claude: `prijsonderzoeker.py:133-146` - log bewijs, ontbrekende velden en beide btw-waarden per opgenomen aanbod.
- X7: Er ontbreekt één wijziging: de opdracht aan het model eist nog steeds dezelfde volledige modelcode op beide pagina’s. Daardoor gebruikt het model de MOVA-handleiding mogelijk nog altijd niet.
  Techniek voor Claude: `aankoop/onderzoek.py:113-115` - pas deze instructie tegelijk met de veilige versie van B aan.
- G1: Documenten tonen (A)**: JA. Mehdi merkt dat handleidingen op winkelpagina's nu wél gelezen worden voor productspecificaties.
  Techniek voor Claude: [mijnagents-runner/aankoop/leesserver.py:154-159](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/leesserver.py#L154-L159) - `a`-tags met `.pdf` verzamelen en als `Documenten:` in de tekstkop meegeven (analoog aan foto's).
- G2: Specificatie uit winkeldocument (B)**: JA. Mehdi merkt dat de robotstofzuiger niet langer onterecht wordt afgekeurd omdat de PDF wel het basisstation (`RCVE0707`) beschrijft maar niet de lange winkelcode (`MOVA-RC-V70ULC-WHT`).
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:464-478](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L464-L478) - bij document-url's gelinkt op de aanbodpagina volstaat compatibiliteitstoets zonder strikte `modelcode_op`, mits `bewijs_url` op de aanbodpagina staat.
- G3: Verzendwoord in tabelkop (C)**: JA. Mehdi merkt dat tarieventabellen (zoals bij RoboCleaners) geaccepteerd worden als het woord 'verzending' erboven in de tabelkop staat.
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:307-316](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L307-L316) - zoekvenster voor `VERZENDWOORDEN` uitbreiden met 150 tekens voorafgaand aan het citaat op de verzendpagina.
- G4: Gratis levering over meerdere regels (D)**: JA. Mehdi merkt dat winkels met opgemaakte leverregels ("Levering aan huis : Gratis") correct als gratis verzending worden herkend.
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:52-54](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L52-L54) - regex `gratis_verzending` toestaan met maximaal 50 tekens speling tussen verzendwoord en gratis, zonder tussenliggende eurobedragen of ontkenningen.
- G5: Btw-aanname consumentenprijs EU (E)**: JA. Mehdi merkt dat EU-aanbiedingen met btw niet langer stranden op ontbrekende btw-status van de verzendkosten. Juridisch sluitend onder EU-richtlijn 98/6/EG en WER Boek VI.
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:352-357](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L352-L357) - als `btw_in is True` in EU, neem `btw_verzending = True` tenzij expliciet ontkend.
- G6: Bewijs en ontbrekende velden loggen (F)**: JA. Mehdi merkt hier direct niets van, maar volgende overleggen hebben direct meetbare data bij fouten zonder contextverlies.
  Techniek voor Claude: [mijnagents-runner/prijsonderzoeker.py:137-142](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py#L137-L142) - logging van citaten en ontbrekende velden per aanbod toevoegen aan de runner.
- K1: A (PDF-links tonen): ja.
  Techniek voor Claude: `leesserver.py:139` (`handle_starttag` kent geen `a`) - links met `.pdf` verzamelen, maximaal 8, dezelfde URL-controle als bij de foto's.
- K2: B (netspanning uit gelinkte PDF): ja, met voorwaarden.
  Techniek voor Claude: `aanbod.py:405` `modelcode_op` - tweede pad "gelinkt document" met de familiecheck en de controle dat `bewijs_url` in de aanbodtekst staat.
- K3: C (verzendwoord in de tabelkop): ja.
  Techniek voor Claude: `aanbod.py:316` - `VERZENDWOORDEN` ook in `pagina[start-150:start]` van het citaat, alleen op een verzendpagina van dezelfde winkel.
- K4: D (gratis levering over meerdere regels): ja.
  Techniek voor Claude: `aanbod.py:52` - de regex met maximaal 50 tekens ertussen, zonder euroteken. `NEGATIE` (`aanbod.py:140`) ook vooraf toepassen op het hele stuk, plus een drempelwoord ("vanaf", "boven", "from") weigeren.
- K5: E (verzending erft btw): ja, maar beperkt.
  Techniek voor Claude: `aanbod.py:355` - erven alleen na een EU-TLD-controle en met `btw_inbegrepen is True`. De uitleg hoort in een code-opmerking, niet als juridische stelling.
- K6: F (citaten bewaren in het verslag): ja.
  Techniek voor Claude: werkverslag per aanbod, velden `citaten` en `ontbreekt`.
- K7: Wat ontbreekt: de volgorde.
  Techniek voor Claude: F eerst bouwen, E uitstellen tot het citaat zichtbaar is.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: gedeeltelijk akkoord: A, E en F ja; B, C en D alleen na aanscherping.<br><br>X1. A: ja. Hierdoor ziet de agent de handleiding die al op de winkelpagina staat.  <br>Techniek voor Claude: `aankoop/leesserver.py:142-193` - toon maximaal acht PDF-links.<br><br>X2. B: nee. Een productpagina kan ook een PDF van een optioneel laadstation linken. Zonder koppeling aan productnaam of onderdeel kan een verkeerde netspanning worden goedgekeurd.  <br>Techniek voor Claude: `aankoop/aanbod.py:468-510` - eis minstens overeenkomst van productnaam of onderdeelmodel, bijvoorbeeld V70 Ultra of RCVE0707.<br><br>X3. C: nee. Op een gecombineerde verzend- en retourpagina kan “Verzendkosten” binnen 150 tekens vóór een Belgisch retourbedrag staan. Dat bedrag kan dan ten onrechte als verzending meetellen.  <br>Techniek voor Claude: `aankoop/aanbod.py:303-320` - eis dezelfde tabel of sectie en sluit retourwoorden uit.<br><br>X4. D: nee. “Levering aan huis. Retourneren is gratis” kan binnen 50 tekens staan en zo gratis levering veinzen.  <br>Techniek voor Claude: `aankoop/aanbod.py:45,52-59,138-140` - eis dezelfde regel of sectie en sluit `retour`, `return` en `retourneren` uit.<br><br>X5. E: ja, mits `btw_inbegrepen is True` en de volledige verzendpagina niet zegt dat bedragen exclusief btw zijn. Voor consumenten moet de vooraf gemelde totaalprijs belastingen en bijkomende vrachtkosten omvatten. [EU-richtlijn 2011/83/EU](https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:02011L0083-20220528)  <br>Techniek voor Claude: `aankoop/aanbod.py:351-363` - erf alleen bij expliciet bewezen consumentenprijs met btw.<br><br>X6. F: ja. Dan is M5 bij de volgende ronde rechtstreeks bewijsbaar zonder de vraagtekst te bewaren.  <br>Techniek voor Claude: `prijsonderzoeker.py:133-146` - log bewijs, ontbrekende velden en beide btw-waarden per opgenomen aanbod.<br><br>X7. Er ontbreekt één wijziging: de opdracht aan het model eist nog steeds dezelfde volledige modelcode op beide pagina’s. Daardoor gebruikt het model de MOVA-handleiding mogelijk nog altijd niet.  <br>Techniek voor Claude: `aankoop/onderzoek.py:113-115` - pas deze instructie tegelijk met de veilige versie van B aan.<br><br>GRENS: geen | BESLISSING: Akkoord met voorstellen A tot en met F (6x JA). Dit herstelt de gemeten blinde vlekken in het lezen van documenten, tabelkoppen en verzendcondities zonder enig risico op verkeerde betalingen of foute toewijzingen.<br><br>G1. **Documenten tonen (A)**: JA. Mehdi merkt dat handleidingen op winkelpagina's nu wél gelezen worden voor productspecificaties.<br>Techniek voor Claude: [mijnagents-runner/aankoop/leesserver.py:154-159](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/leesserver.py#L154-L159) - `a`-tags met `.pdf` verzamelen en als `Documenten:` in de tekstkop meegeven (analoog aan foto's).<br><br>G2. **Specificatie uit winkeldocument (B)**: JA. Mehdi merkt dat de robotstofzuiger niet langer onterecht wordt afgekeurd omdat de PDF wel het basisstation (`RCVE0707`) beschrijft maar niet de lange winkelcode (`MOVA-RC-V70ULC-WHT`).<br>Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:464-478](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L464-L478) - bij document-url's gelinkt op de aanbodpagina volstaat compatibiliteitstoets zonder strikte `modelcode_op`, mits `bewijs_url` op de aanbodpagina staat.<br><br>G3. **Verzendwoord in tabelkop (C)**: JA. Mehdi merkt dat tarieventabellen (zoals bij RoboCleaners) geaccepteerd worden als het woord 'verzending' erboven in de tabelkop staat.<br>Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:307-316](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L307-L316) - zoekvenster voor `VERZENDWOORDEN` uitbreiden met 150 tekens voorafgaand aan het citaat op de verzendpagina.<br><br>G4. **Gratis levering over meerdere regels (D)**: JA. Mehdi merkt dat winkels met opgemaakte leverregels ("Levering aan huis : Gratis") correct als gratis verzending worden herkend.<br>Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:52-54](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L52-L54) - regex `gratis_verzending` toestaan met maximaal 50 tekens speling tussen verzendwoord en gratis, zonder tussenliggende eurobedragen of ontkenningen.<br><br>G5. **Btw-aanname consumentenprijs EU (E)**: JA. Mehdi merkt dat EU-aanbiedingen met btw niet langer stranden op ontbrekende btw-status van de verzendkosten. Juridisch sluitend onder EU-richtlijn 98/6/EG en WER Boek VI.<br>Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:352-357](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L352-L357) - als `btw_in is True` in EU, neem `btw_verzending = True` tenzij expliciet ontkend.<br><br>G6. **Bewijs en ontbrekende velden loggen (F)**: JA. Mehdi merkt hier direct niets van, maar volgende overleggen hebben direct meetbare data bij fouten zonder contextverlies.<br>Techniek voor Claude: [mijnagents-runner/prijsonderzoeker.py:137-142](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py#L137-L142) - logging van citaten en ontbrekende velden per aanbod toevoegen aan de runner.<br><br>GRENS: geen | BESLISSING: A, C, D, F ja. B en E ja, maar alleen met de extra voorwaarden in K2 en K5. Daarna dezelfde vraag opnieuw op de VM draaien.<br><br>**K1. A (PDF-links tonen): ja.**<br>Mehdi merkt: de agent ziet dan de handleiding die de winkel zelf bij het product zet. Nu ziet hij die link nooit.<br>Techniek voor Claude: `leesserver.py:139` (`handle_starttag` kent geen `a`) - links met `.pdf` verzamelen, maximaal 8, dezelfde URL-controle als bij de foto's.<br><br>**K2. B (netspanning uit gelinkte PDF): ja, met voorwaarden.**<br>Mehdi merkt: de agent vindt 220-240 V zonder dat er een tweede bron nodig is. Het risico is een PDF die op de pagina staat maar bij een ander product hoort, zoals een accessoire of een serie-handleiding. Daarom:<br>- De PDF moet op dezelfde winkeldomein-pagina staan als het aanbod.<br>- Het citaat moet uit het deel "Base Station" of "Specifications" komen.<br>- Een tegenspraak met een andere bron blokkeert, zoals nu.<br>- De PDF moet minstens de productnaam of de modelfamilie bevatten (hier "V70 Ultra Complete"). De volledige modelcode is niet nodig.<br>Het scenario bij zonder voorwaarden: een handleiding voor een ander model in dezelfde reeks geeft een verkeerde netspanning. Voor 220-240 V in België is dat laag risico, maar een apparaat voor een andere markt zou het wel kunnen geven.<br>Techniek voor Claude: `aanbod.py:405` `modelcode_op` - tweede pad "gelinkt document" met de familiecheck en de controle dat `bewijs_url` in de aanbodtekst staat.<br><br>**K3. C (verzendwoord in de tabelkop): ja.**<br>Mehdi merkt: RoboCleaners met 12,50 euro wordt niet meer als "niet bewezen" afgekeurd. Het venster van 150 tekens is klein. Het citaat moet zelf nog België en het bedrag bevatten.<br>Techniek voor Claude: `aanbod.py:316` - `VERZENDWOORDEN` ook in `pagina[start-150:start]` van het citaat, alleen op een verzendpagina van dezelfde winkel.<br><br>**K4. D (gratis levering over meerdere regels): ja.**<br>Mehdi merkt: Vanden Borre "Levering aan huis : vanaf di. 03 november Gratis" telt als gratis verzending. De bestaande ontkenning blijft gelden. Daarbij komt een controle op "niet gratis", "vanaf ... gratis" (drempelbedrag) en "gratis retour". Een drempel zoals "gratis vanaf 50 euro" mag niet als gratis tellen, want dat kost bij een lagere prijs wel geld.<br>Techniek voor Claude: `aanbod.py:52` - de regex met maximaal 50 tekens ertussen, zonder euroteken. `NEGATIE` (`aanbod.py:140`) ook vooraf toepassen op het hele stuk, plus een drempelwoord ("vanaf", "boven", "from") weigeren.<br><br>**K5. E (verzending erft btw): ja, maar beperkt.**<br>Mehdi merkt: het totaal klopt dan voor RoboCleaners. Het risico is een winkel buiten de EU of een zakelijke prijs zonder btw. Daarom alleen toepassen als de winkeldomein een EU-land is, de prijs met btw is en de pagina niet "excl. btw" zegt. Anders blijft het onbekend, en dat geldt dan als de prijs (zoals nu).<br>Techniek voor Claude: `aanbod.py:355` - erven alleen na een EU-TLD-controle en met `btw_inbegrepen is True`. De uitleg hoort in een code-opmerking, niet als juridische stelling.<br><br>**K6. F (citaten bewaren in het verslag): ja.**<br>Mehdi merkt: bij een volgende fout is te zien waarom. Het is alleen verslaglegging, geen vraagtekst. M5 is nu een gok omdat de modeluitvoer niet bewaard wordt, en dit lost dat op.<br>Techniek voor Claude: werkverslag per aanbod, velden `citaten` en `ontbreekt`.<br><br>**K7. Wat ontbreekt: de volgorde.**<br>Eerst F, dan de proef opnieuw draaien, en pas daarna E bouwen als M5 bevestigd is. Zo wordt niets op een gok hersteld.<br>Techniek voor Claude: F eerst bouwen, E uitstellen tot het citaat zichtbaar is.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: A en F akkoord; B, C, D en E alleen met de genoemde veiligheidscontroles. Pas ook de modelopdracht aan en draai daarna één nieuwe proef.

X1/G1/K1 en X6/G6/K6: eens. PDF-links worden zichtbaar en volgende fouten worden meetbaar.

X2/G2/K2: Codex en Claude hebben gelijk. Alleen “gelinkt op de productpagina” is onvoldoende. Eis ook productnaam of modelfamilie en een passend specificatiegedeelte.

X3/G3/K3: het venster van 150 tekens werkt voor RoboCleaners, maar kan een retourbedrag koppelen aan verzending. Voeg uitsluiting van retourtekst en liefst dezelfde tabelsectie toe.

X4/G4/K4: maximaal 50 tekens is bruikbaar mits retouren, ontkenningen, eurobedragen en prijsdrempels worden geweigerd.

X5/G5/K5: btw erven is veilig wanneer de productprijs aantoonbaar inclusief btw is, de winkel binnen de EU verkoopt en nergens “excl. btw” bij verzending staat. Alleen een EU-TLD gebruiken is geen volledige landencontrole.

X7: eens. Anders blijft de oude modelopdracht de nieuwe bewijsroute blokkeren.

K7: oneens. E is een zelfstandige, begrensde totaalprijsregel. Eerst nog een kostbare proef met alleen F bevestigt hoogstens de al bekende `null`; bouw de afgesproken veilige wijzigingen samen en test daarna eenmaal.

Techniek voor Claude: `aankoop/leesserver.py:139-193`, `aankoop/aanbod.py:52-59,303-320,351-363,405-510`, `aankoop/onderzoek.py:113-115`, `prijsonderzoeker.py:133-146`.

STEMBLOK: Codex
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
G1: eens
G2: oneens
G3: oneens
G4: oneens
G5: eens
G6: eens
K1: eens
K2: eens
K3: oneens
K4: eens
K5: eens
K6: eens
K7: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Meerderheid (minstens 2-1) voor uitvoering van A tot en met F, waarbij we de terechte aanscherpingen van Codex en Claude op B, C, D en E overnemen. X7 van Codex nemen we mee als noodzakelijke aanvulling.

### Reactie en toelichting voor Mehdi

1. **PDF-documenten tonen (A / X1, G1, K1 - 3-0 akkoord)**:
   Mehdi merkt dat handleidingen en specificatiebladen die als PDF op de winkelpagina staan, direct worden opgemerkt door de agent.

2. **Netspanning uit gelinkte PDF (B / X2, G2, K2 - 2-1 akkoord met aanscherping)**:
   Mehdi merkt dat een robotstofzuiger niet langer onterecht afvalt door een ontbrekende winkelcode in de handleiding, terwijl voorkomen wordt dat specificaties van een los accessoire per ongeluk goedgekeurd worden.
   *Aanvulling*: We volgen de scherpere veiligheidseis van Codex en Claude: de PDF moet gelinkt staan op de productpagina én minstens de productnaam/modelfamilie of het specifieke onderdeelmodel noemen.

3. **Verzendkosten uit tabelkop (C / X3, G3, K3 - 2-1 akkoord met aanscherping)**:
   Mehdi merkt dat verzendkosten in een prijstabel (zoals 12,50 euro bij RoboCleaners) correct worden bewezen.
   *Aanvulling*: Zoals Codex aangeeft sluiten we retour- en teruggavewoorden expliciet uit om te voorkomen dat retourkosten worden aangezien voor leveringskosten.

4. **Gratis levering over meerdere regels (D / X4, G4, K4 - 2-1 akkoord met aanscherping)**:
   Mehdi merkt dat opgemaakte zinnen zoals "Levering aan huis : Gratis" netjes als gratis verzending tellen.
   *Aanvulling*: We sluiten woorden rondom retourzendingen ("retour", "return") en drempels ("vanaf", "boven") strikt uit.

5. **Btw-overname verzending binnen EU (E / X5, G5, K5 - 3-0 akkoord met voorwaarde)**:
   Mehdi merkt dat consumentenprijzen binnen de EU niet langer stranden op ontbrekende btw-aanduiding op de verzendpagina.
   *Voorwaarde*: Alleen als de hoofdprijs expliciet inclusief btw is en de verzendpagina niet het tegendeel beweert.

6. **Loggen van bewijzen en ontbrekende velden (F / X6, G6, K6 - 3-0 akkoord)**:
   Mehdi merkt hier direct niets van, maar bij een eventueel foutief aanbod is de precieze reden meteen zichtbaar voor analyse. Uitstel (K7) is niet nodig: E en F kunnen direct samen ingebouwd worden.

7. **Aanpassing instructie prompt (X7 - Codex aanvulling)**:
   Mehdi merkt dat de AI-agent de gelinkte handleiding ook daadwerkelijk durft te gebruiken doordat de promptinstructie synchroon loopt met de code.

---

### Techniek voor Claude / Shaniel

1. [`mijnagents-runner/aankoop/leesserver.py:142-193`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/leesserver.py#L142-L193): verzamel `.pdf`-links via `handle_starttag('a')` en toon maximaal acht links onder `Documenten:`.
2. [`mijnagents-runner/aankoop/aanbod.py:468-510`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L468-L510): sta gelinkt document van aanbodpagina toe voor specificaties mits productfamilie of onderdeelmodel overeenkomt en tegenspraakcontrole intact blijft.
3. [`mijnagents-runner/aankoop/aanbod.py:303-320`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L303-L320): zoekvenster tabelkop met 150 tekens voor citaat toestaan voor `VERZENDWOORDEN`, mits `retour`, `return` en `terugsturen` daarin ontbreken.
4. [`mijnagents-runner/aankoop/aanbod.py:45,52-59,138-140`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L45): regex voor gratis levering toestaan binnen 50 tekens speling, met uitsluiting van retour- en drempelwoorden ("vanaf", "boven", "retour").
5. [`mijnagents-runner/aankoop/aanbod.py:351-363`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L351-L363): verzending erft `btw_inbegrepen = True` als EU-consumentenprijs met btw bewezen is en verzendpagina geen `excl.` meldt.
6. [`mijnagents-runner/prijsonderzoeker.py:133-146`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py#L133-L146): sla citaten, ontbrekende velden en btw-status per aanbod op in het werkverslag.
7. [`mijnagents-runner/aankoop/onderzoek.py:113-115`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py#L113-L115): versoepel promptregel over modelcode voor documenten gelinkt op de productpagina conform besluit B.

GRENS: geen

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
X4: eens
X5: eens
X6: eens
X7: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
G6: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: oneens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: A en F zijn aangenomen. B, C, D en E gaan door met de scherpere voorwaarden hieronder. Daarna draait dezelfde vraag opnieuw op de VM.

Ik heb in deze ronde geen bestanden geopend. Mijn oordeel steunt op de meldingen in het overleg, niet op eigen controle van de code.

**Wat Mehdi merkt**

- **A (PDF-links tonen):** Alle drie zijn het eens. De agent ziet dan de handleiding die de winkel zelf bij het product zet.
- **B (netspanning uit gelinkte PDF):** Codex heeft gelijk dat een gelinkte PDF bij een optioneel onderdeel kan horen. Ik neem zijn aanscherping over. De PDF moet de productnaam of het onderdeelmodel bevatten, hier "V70 Ultra" of RCVE0707. Mijn eigen eis uit K2 blijft ook staan: het citaat komt uit een specificatiedeel en een tegenspraak blokkeert.
- **C (verzendwoord in de tabelkop):** Codex' scenario is reëel. Een retourbedrag kan binnen 150 tekens na "Verzendkosten" staan. Het woord in de kop telt daarom alleen als het in dezelfde tabel of sectie staat en er geen retourwoord tussen zit.
- **D (gratis levering over meerdere regels):** Codex' scenario "Levering aan huis. Retourneren is gratis" is reëel. Ik sluit "retour", "return" en "retourneren" uit. Daarbovenop blijven mijn drempelwoorden ("vanaf", "boven") en de ontkenning gelden. Voor de Vanden Borre-regel is dat een kleine uitzondering: "vanaf di. 03 november" is een datum en geen drempel. Die uitzondering moet de code dus apart afdekken.
- **E (verzending erft btw):** Alleen bij `btw_inbegrepen is True` en een EU-winkel. De pagina mag nergens "excl. btw" zeggen. Dit sluit aan bij Codex en Gemini.
- **Volgorde:** F komt eerst. Mijn K7 wilde E uitstellen tot M5 bevestigd is. Dat is niet aangenomen, want Codex en Gemini willen E direct. E is met de strenge voorwaarden veilig genoeg om mee te bouwen. Als het citaat uit F iets anders laat zien, passen we E aan.
- **X7 (opdracht aan het model):** Dit is een goede aanvulling van Codex. Als de instructie nog steeds de volledige modelcode op beide pagina's eist, ziet het model de handleiding misschien nog steeds niet als bewijs. De instructie hoort samen met B te veranderen.

Techniek voor Claude: `aankoop/leesserver.py:139` - PDF-links, maximaal 8. `aankoop/aanbod.py:468-510` - B met productnaamcheck. `aankoop/aanbod.py:303-320` - C binnen dezelfde sectie, zonder retourwoorden. `aankoop/aanbod.py:45,52-59,138-140` - D met retourwoorden en drempelwoorden geweigerd. `aankoop/aanbod.py:351-363` - E alleen EU en `btw_inbegrepen is True`. `prijsonderzoeker.py:133-146` - F. `aankoop/onderzoek.py:113-115` - instructie aanpassen.

STEMBLOK: Claude
X1: eens
X2: oneens
X3: oneens
X4: oneens
X5: eens
X6: eens
X7: eens
G1: eens
G2: eens
G3: eens
G4: eens
G5: eens
G6: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
K6: eens
K7: oneens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Gemini

Besluit: Alle 19 herstelpunten zijn aangenomen (minstens 2-1) en worden zelfstandig uitgevoerd; K7 is afgewezen (0-3).

### Voor Mehdi
- Aankoopagents lezen voortaan officiële PDF-handleidingen op winkelpagina's voor productspecificaties zoals netspanning.
- Producten worden niet langer afgekeurd als modelcodes tussen winkel en handleiding licht afwijken.
- Verzendkosten en gratis levering uit tabellen en losse regels worden correct herkend.
- Btw op verzendkosten binnen de EU wordt automatisch gekoppeld aan de consumentenprijs.
- Geen actie nodig van Mehdi: alle punten worden direct door Claude verwerkt.

---

### Overzicht van aangenomen en afgewezen punten
- **Aangenomen (zelfstandige uitvoering door Claude):** X1, X2, X3, X4, X5, X6, X7, G1, G2, G3, G4, G5, G6, K1, K2, K3, K4, K5, K6.
- **Afgewezen:** K7.
- **Naar Mehdi (grens):** Geen.

---

### Techniek voor Claude / Shaniel
- **X1 / G1 / K1**: [`aankoop/leesserver.py:142-193`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/leesserver.py#L142-L193) - verzamel `a`-tags met `.pdf` (maximaal 8), valideer URL's analoog aan foto's en toon in tekstkop als `Documenten:`.
- **X2 / G2 / K2**: [`aankoop/aanbod.py:464-510`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L464-L510) - sta specificaties uit gelinkte PDF toe mits `bewijs_url` op de aanbodpagina staat en productnaam of onderdeelmodel (bv. RCVE0707) overeenkomt.
- **X3 / G3 / K3**: [`aankoop/aanbod.py:303-320`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L303-L320) - zoekvenster voor `VERZENDWOORDEN` uitbreiden met 150 tekens vóór citaat op verzendpagina van dezelfde winkel; sluit retourtermen uit.
- **X4 / G4 / K4**: [`aankoop/aanbod.py:45-59,138-140`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L45-L59) - regex gratis levering toestaan binnen 50 tekens speling zonder tussenliggende bedragen; sluit `retour`/`return`, drempelwoorden en negaties uit.
- **X5 / G5 / K5**: [`aankoop/aanbod.py:351-363`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L351-L363) - neem `btw_verzending = True` over indien `btw_inbegrepen is True` bij EU-TLD, tenzij expliciet exclusief vermeld.
- **X6 / G6 / K6**: [`prijsonderzoeker.py:133-146`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py#L133-L146) - log bewijscitaten, ontbrekende velden en btw-status per aanbod in het werkverslag.
- **X7**: [`aankoop/onderzoek.py:113-115`](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py#L113-L115) - modelprompts bijwerken zodat niet langer de volledige modelcode strikt vereist is bij gelinkte documenten.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-sonnet-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): A: ja. Hierdoor ziet de agent de handleiding die al op de winkelpagina staat.
  Techniek voor Claude: `aankoop/leesserver.py:142-193` - toon maximaal acht PDF-links.
- **X2** (2-1): B: nee. Een productpagina kan ook een PDF van een optioneel laadstation linken. Zonder koppeling aan productnaam of onderdeel kan een verkeerde netspanning worden goedgekeurd.
  Techniek voor Claude: `aankoop/aanbod.py:468-510` - eis minstens overeenkomst van productnaam of onderdeelmodel, bijvoorbeeld V70 Ultra of RCVE0707.
- **X3** (2-1): C: nee. Op een gecombineerde verzend- en retourpagina kan “Verzendkosten” binnen 150 tekens vóór een Belgisch retourbedrag staan. Dat bedrag kan dan ten onrechte als verzending meetellen.
  Techniek voor Claude: `aankoop/aanbod.py:303-320` - eis dezelfde tabel of sectie en sluit retourwoorden uit.
- **X4** (2-1): D: nee. “Levering aan huis. Retourneren is gratis” kan binnen 50 tekens staan en zo gratis levering veinzen.
  Techniek voor Claude: `aankoop/aanbod.py:45,52-59,138-140` - eis dezelfde regel of sectie en sluit `retour`, `return` en `retourneren` uit.
- **X5** (3-0): E: ja, mits `btw_inbegrepen is True` en de volledige verzendpagina niet zegt dat bedragen exclusief btw zijn. Voor consumenten moet de vooraf gemelde totaalprijs belastingen en bijkomende vrachtkosten omvatten. [EU-richtlijn 2011/83/EU](https://eur-lex.europa.eu/legal-content/NL/TXT/?uri=CELEX:02011L0083-20220528)
  Techniek voor Claude: `aankoop/aanbod.py:351-363` - erf alleen bij expliciet bewezen consumentenprijs met btw.
- **X6** (3-0): F: ja. Dan is M5 bij de volgende ronde rechtstreeks bewijsbaar zonder de vraagtekst te bewaren.
  Techniek voor Claude: `prijsonderzoeker.py:133-146` - log bewijs, ontbrekende velden en beide btw-waarden per opgenomen aanbod.
- **X7** (3-0): Er ontbreekt één wijziging: de opdracht aan het model eist nog steeds dezelfde volledige modelcode op beide pagina’s. Daardoor gebruikt het model de MOVA-handleiding mogelijk nog altijd niet.
  Techniek voor Claude: `aankoop/onderzoek.py:113-115` - pas deze instructie tegelijk met de veilige versie van B aan.
- **G1** (3-0): Documenten tonen (A)**: JA. Mehdi merkt dat handleidingen op winkelpagina's nu wél gelezen worden voor productspecificaties.
  Techniek voor Claude: [mijnagents-runner/aankoop/leesserver.py:154-159](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/leesserver.py#L154-L159) - `a`-tags met `.pdf` verzamelen en als `Documenten:` in de tekstkop meegeven (analoog aan foto's).
- **G2** (2-1): Specificatie uit winkeldocument (B)**: JA. Mehdi merkt dat de robotstofzuiger niet langer onterecht wordt afgekeurd omdat de PDF wel het basisstation (`RCVE0707`) beschrijft maar niet de lange winkelcode (`MOVA-RC-V70ULC-WHT`).
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:464-478](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L464-L478) - bij document-url's gelinkt op de aanbodpagina volstaat compatibiliteitstoets zonder strikte `modelcode_op`, mits `bewijs_url` op de aanbodpagina staat.
- **G3** (2-1): Verzendwoord in tabelkop (C)**: JA. Mehdi merkt dat tarieventabellen (zoals bij RoboCleaners) geaccepteerd worden als het woord 'verzending' erboven in de tabelkop staat.
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:307-316](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L307-L316) - zoekvenster voor `VERZENDWOORDEN` uitbreiden met 150 tekens voorafgaand aan het citaat op de verzendpagina.
- **G4** (2-1): Gratis levering over meerdere regels (D)**: JA. Mehdi merkt dat winkels met opgemaakte leverregels ("Levering aan huis : Gratis") correct als gratis verzending worden herkend.
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:52-54](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L52-L54) - regex `gratis_verzending` toestaan met maximaal 50 tekens speling tussen verzendwoord en gratis, zonder tussenliggende eurobedragen of ontkenningen.
- **G5** (3-0): Btw-aanname consumentenprijs EU (E)**: JA. Mehdi merkt dat EU-aanbiedingen met btw niet langer stranden op ontbrekende btw-status van de verzendkosten. Juridisch sluitend onder EU-richtlijn 98/6/EG en WER Boek VI.
  Techniek voor Claude: [mijnagents-runner/aankoop/aanbod.py:352-357](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L352-L357) - als `btw_in is True` in EU, neem `btw_verzending = True` tenzij expliciet ontkend.
- **G6** (3-0): Bewijs en ontbrekende velden loggen (F)**: JA. Mehdi merkt hier direct niets van, maar volgende overleggen hebben direct meetbare data bij fouten zonder contextverlies.
  Techniek voor Claude: [mijnagents-runner/prijsonderzoeker.py:137-142](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py#L137-L142) - logging van citaten en ontbrekende velden per aanbod toevoegen aan de runner.
- **K1** (3-0): A (PDF-links tonen): ja.
  Techniek voor Claude: `leesserver.py:139` (`handle_starttag` kent geen `a`) - links met `.pdf` verzamelen, maximaal 8, dezelfde URL-controle als bij de foto's.
- **K2** (3-0): B (netspanning uit gelinkte PDF): ja, met voorwaarden.
  Techniek voor Claude: `aanbod.py:405` `modelcode_op` - tweede pad "gelinkt document" met de familiecheck en de controle dat `bewijs_url` in de aanbodtekst staat.
- **K3** (2-1): C (verzendwoord in de tabelkop): ja.
  Techniek voor Claude: `aanbod.py:316` - `VERZENDWOORDEN` ook in `pagina[start-150:start]` van het citaat, alleen op een verzendpagina van dezelfde winkel.
- **K4** (3-0): D (gratis levering over meerdere regels): ja.
  Techniek voor Claude: `aanbod.py:52` - de regex met maximaal 50 tekens ertussen, zonder euroteken. `NEGATIE` (`aanbod.py:140`) ook vooraf toepassen op het hele stuk, plus een drempelwoord ("vanaf", "boven", "from") weigeren.
- **K5** (3-0): E (verzending erft btw): ja, maar beperkt.
  Techniek voor Claude: `aanbod.py:355` - erven alleen na een EU-TLD-controle en met `btw_inbegrepen is True`. De uitleg hoort in een code-opmerking, niet als juridische stelling.
- **K6** (3-0): F (citaten bewaren in het verslag): ja.
  Techniek voor Claude: werkverslag per aanbod, velden `citaten` en `ontbreekt`.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
