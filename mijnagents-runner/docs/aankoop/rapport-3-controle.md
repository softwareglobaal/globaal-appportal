**Niet klaar.** De eerste echte prijsvraag kan nog een verkeerd geprijsd of onbewezen compatibel aanbod aanbevelen. Ook gaat de naam uit de werkwijze nog mee naar de externe AI. Ik adviseer deze punten eerst in de bron te herstellen.

### Voor Mehdi

De lege-paginacontrole en de route naar De Regisseur zijn verbeterd, maar de prijs en geschiktheid zijn nog niet betrouwbaar genoeg voor een aanbeveling. Het bewuste restrisico rond een gewone naam zonder aanspreking vind ik nu **niet aanvaardbaar**: De Regisseur krijgt alleen een instructie om zo’n naam weg te laten, en een vraag kan ook rechtstreeks of via een klaargezet item binnenkomen.

### Voor Claude en Shaniel

1. **X1 — hoog — deels.** [aanbod.py:143](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:143): een lege pagina wordt geweigerd. Tegenproef: productprijs 999 euro, elders op dezelfde pagina 499 euro verzendkosten; het model geeft 499 als productprijs en de code beveelt die aan. Koppel het bedrag aan het betreffende aanbod.

2. **X2 — hoog — deels.** [aanbod.py:235](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:235), [verslag.py:66](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/verslag.py:66): de code haalt 60 Hz uit de vraag, maar aanvaardt een onbewezen modeloordeel `ja`. Vrije modeltekst in `waarom` verschijnt nog in de aanbeveling. Controleer geschiktheid tegen de bron en begrens die tekst.

3. **X3 — hoog — deels.** [prijsonderzoeker.py:111](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:111), [verslag.py:83](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/verslag.py:83): extra naampatronen werken, maar een gewone naam passeert; het gelogde verslag bevat vervolgens de oorspronkelijke vraag. Laat die weg uit het logboek.

4. **X4 — hoog — deels.** [onderzoek.py:139](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:139), [prijsonderzoeker.md:3](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/werkwijze/prijsonderzoeker.md:3): collega’s en lessen zijn verwijderd, maar de echte werkwijze met Mehdi’s naam gaat nog integraal naar het model. Maak de externe werkwijze gegevensarm.

5. **X5 — middel — deels.** [regisseur.py:120](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/regisseur.py:120) maakt de inhoud leesbaar. [detail.html:150](/Users/mehdichegini/dev/_aankoopagents/mijnagents/templates/detail.html:150) toont het verslag slechts als platte logtekst; de test bewijst geen daadwerkelijk chatantwoord. Maak het verslag op het bord klikbaar en toets de chatroute.

6. **X6 — hoog — opgelost in code.** [prijsonderzoeker.py:129](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/prijsonderzoeker.py:129) zet één rondedeadline; [onderzoek.py:166](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:166) bewaakt de resterende tijd.

7. **X7 — middel — deels.** [onderzoek.py:170](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:170): na twaalf zoekopdrachten geeft `max(1, 0)` de zoektool opnieuw één beurt. Laat een uitgeputte tool weg.

8. **X8 — middel — opgelost.** [onderzoek.py:173](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:173) bewaart de blokken van eerdere pauzes; de proef met twee pauzes slaagt.

9. **X9 — middel — deels.** [aanbod.py:208](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:208): btw op een prijs exclusief btw wordt bijgeteld, maar ook op verzending die al inclusief btw kan zijn. Tegenproef: 100 euro exclusief plus 10 euro inclusief geeft 133,10 in plaats van 131 euro. Leg btw per kostenpost vast.

10. **X10 — middel — nieuw.** [privacy.py:19](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/privacy.py:19): een gewone productvraag over “Mr. Proper allesreiniger” wordt als persoonsnaam tegengehouden. Maak een uitzondering voor productnamen.

11. **X11 — middel — nieuw.** [aanbod.py:87](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:87): de zichtbare prijs `1 299,00` met smalle spatie wordt niet herkend. Neem die schrijfwijze op in de prijscontrole.

Gedaan: diff en volledige relevante bestanden alleen gelezen; niets gewijzigd.  
Nagekeken: 100 bestaande prijstests slagen; gerichte tegenproeven bevestigen de bovenstaande fouten.  
Open: herstel vooral X1–X4 vóór de eerste echte ronde en toets daarna bord en chat daadwerkelijk.