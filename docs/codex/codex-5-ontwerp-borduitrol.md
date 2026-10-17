**Beslissing: optie A, met één herstelovergang per cronronde. Nog niet klaar voor merge of een bewaakte uitrol.** Een open `.herstel` krijgt voorrang op een bouw. Ook na geslaagd herstel begint een eventuele nieuwe uitrol pas in de volgende ronde.

### Nieuwe bevindingen

1. **BU-23 — middel — [mijnagents/deploy.sh:249](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:249).** Een Git-fout stopt het script vóór het een bestaande `.herstel` behandelt. Een ongezonde kandidaat wordt dan niet teruggezet, hoewel de markering de benodigde image-ID’s bevat. **Fix:** behandel `.herstel` vóór het lezen van HEAD.

2. **BU-24 — middel — [mijnagents/deploy.sh:283](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:283).** Als terugrollen `:latest` al op de vorige image heeft gezet maar Compose faalt, kan de kandidaat blijven draaien en later gezond worden. Hervatten markeert die kandidaat dan als gebouwd en wist `.herstel`, terwijl `:latest` nog naar de vorige image wijst. **Fix:** controleer ook `:latest=KANDIDAAT-ID` vóór voltooiing.

3. **BU-25 — middel — [mijnagents/deploy.sh:69](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:69).** Een tijdelijke fout bij containerinspectie wordt een leeg ID. Zonder bestaande `:vorige` kan het script daardoor een gezond bord vervangen zonder terugrolimage; bij een mislukte kandidaat kan het niet terugzetten. **Fix:** onderscheid een ontbrekende container van een inspectiefout en stop zolang een gezond bord geen verifieerbaar ID heeft.

4. **BU-26 — middel — [mijnagents/deploy.sh:382](/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh:382), [scripts/apps-bijwerken.sh:41](/Users/mehdichegini/dev/_bord-uitrol/scripts/apps-bijwerken.sh:41).** De imagebron en CI zijn aan één commit gekoppeld, maar `docker compose up` leest de veranderlijke werkboom. Een gelijktijdige pull kan configuratie van een latere commit toepassen op de gecontroleerde image; een image-terugrol herstelt die configuratie niet. **Fix:** pin de Compose-configuratie of laat iedere pull hetzelfde uitrolslot respecteren. Of het pullscript momenteel in de VM-cron staat, kon ik niet nagaan.

### Antwoorden

1. **A heeft de kleinste toestandsruimte**, mits `.herstel` nooit wordt overschreven en pas verdwijnt bij een *volledig* kloppende eindtoestand: draaiend ID gezond, `:latest` op datzelfde ID, en `.built` én `.built_id` passend bij die toestand. Bij herstel naar de vorige image moeten dus ook beide metadatabestanden worden gecontroleerd of hersteld. Een bestaande drieveldenmarkering moet bij de overgang naar vier velden behouden en veilig behandeld worden; een onleesbare markering mag niet automatisch verdwijnen.

2. **Nee, niet voor een tijdelijke storing.** CX10 betrof een revisie die na enkele pogingen blijvend in `.mislukt` zou vastlopen. A probeert een open herstel elke ronde opnieuw. A verandert wel bewust de eerdere regel dat een nieuwere revisie mag bouwen terwijl herstel faalt. Voor handmatige vrijgave is alleen `rm .herstel` geen volledige procedure: `.built=HEAD` of een lopende afkoeling kan de volgende bouw alsnog tegenhouden.

3. **Minimale tests:** gewone wissel; onderbreking vóór en na de tag; gezonde kandidaat met verkeerde `:latest`; gezonde vorige image met half geschreven metadata; mislukte terugzetting met nieuwere HEAD zonder bouw en daarna geslaagd herstel; halve tagfout waarbij terugtaggen faalt; Git-fout met open markering; oud of ongeldig markerformaat; inspectiefout bij een gezond bestaand bord. Leg de eerste uitrol zonder vorige image als expliciete uitzondering vast.

4. **Ja.** BU-25 en BU-26 liggen buiten de levensloop van `.herstel` en vragen herstel of een aantoonbare afdekking vóór merge en de bewaakte uitrol.

1. **Gedaan:** werkafspraken v1.3, ronde-4-verwerking, ontwerp, code, tests en Git-status en -geschiedenis gelezen op `ad0ceff9f2820b930665c5eabad0ceb18fbbd28c`. Geen bestanden gewijzigd of commits gemaakt.
2. **Nagekeken:** `git diff --check`, `sh -n` en Python-AST-controle slaagden. De deploytests schrijven tijdelijke bestanden en zijn in deze alleen-lezen controle niet uitgevoerd; CI en de VM zijn niet benaderd.
3. **Open:** Claude kan optie A en BU-19 tot BU-26 met gerichte regressietests uitwerken. Daarna volgt een nieuwe controle; de ontwerpkeuze gaat volgens de stopregel naar Mehdi vóór merge.