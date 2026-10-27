Niet klaar. De venstercontrole werkt voor een stabiele kopie, maar ik vond twee gevallen waarin het resultaat toch onjuist kan zijn.

### Voor Mehdi

Een volledige leesfout kan een bestaande nood voor een postvak sluiten, terwijl niet is vastgesteld dat dit postvak weer werkt. Rond de verversing van de Hotmail-kopie kan een oude dag bovendien stil te weinig mail tellen.

De nieuwe mailnood bevat geen afzender, onderwerp of inhoud. Het nieuwe werkverslag kan wel een mapnaam tonen die een klantnaam bevat. De werkwijze van De Dagbundelaar beschrijft de nieuwe kopiecontrole nog niet.

### Voor Claude en Shaniel

1. **Belangrijk — [dagbundelaar.py:805](/Users/mehdichegini/dev/_dagbundel-mail/mijnagents-runner/dagbundelaar.py:805), [bord.py:428](/Users/mehdichegini/dev/_dagbundel-mail/mijnagents-runner/koppelingen/bord.py:428).** Na een postvaknood geeft een totale leesfout alleen de algemene mailnood door. `Ronde.__exit__` sluit daardoor de oude nood zonder herstelbewijs; dit is in een proef over twee rondes bevestigd. Behoud bestaande mailnoden bij een totale leesfout en test die overgang.

2. **Belangrijk — [dagbundelaar.py:616](/Users/mehdichegini/dev/_dagbundel-mail/mijnagents-runner/dagbundelaar.py:616), [postvak.py:195](/Users/mehdichegini/dev/_dagbundel-mail/mijnagents-runner/koppelingen/postvak.py:195).** Begindatum en koppen worden afzonderlijk gelezen. Wordt `koppen.json` ertussen vervangen, dan kan de oude begindatum slagen terwijl de nieuwe kopie vroege berichten van een Brusselse dag mist. Een nagebootste vervanging gaf geen melding van onvolledigheid. Lees begindatum en koppen uit één momentopname; voeg een grensproef toe.

3. **Belangrijk — [dagbundelaar.py:601](/Users/mehdichegini/dev/_dagbundel-mail/mijnagents-runner/dagbundelaar.py:601), [dagbundelaar.py:729](/Users/mehdichegini/dev/_dagbundel-mail/mijnagents-runner/dagbundelaar.py:729).** Bij een onleesbare map neemt het nieuwe logbericht de volledige mapnaam over. Een proef met een map genaamd `INBOX.Klant X` bevestigde dit. Log alleen het postvakadres en een vaste foutsoort; houd uren waar nodig.

4. **Klein — [dagbundelaar.md:22](/Users/mehdichegini/dev/_dagbundel-mail/mijnagents-runner/werkwijze/dagbundelaar.md:22).** De werkwijze noemt alleen het lezen van mappen. Vermeld de Hotmail-serverkopie, de dekkingsgrens en de nood per postvak en soort; verhoog het versienummer.

De vijf gevraagde tests zijn gestart. `test_dagvaststelling.py` slaagt; de overige lopen vast op `tempfile` omdat deze sessie geen schrijfbare tijdelijke map heeft. Losse leesproeven bevestigden de IMAP-startdatum, de grenscontrole, het ontbrekende `vanaf` en het behoud van `soorten` bij een JSON-ronde. Andere lezers lijken het extra veld te negeren; het kindproces kon hier niet van begin tot eind draaien.

Gedaan: diff en besluit gecontroleerd, niets gewijzigd.  
Nagekeken: vijf tests gestart en gerichte breekproeven uitgevoerd.  
Open: vier herstelpunten en een volledige testrun in een schrijfbare testomgeving.

**BESLISSING: niet klaar.**