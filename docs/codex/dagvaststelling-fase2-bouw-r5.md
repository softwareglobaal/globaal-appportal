**Niet klaar.** S2, S3 en S4 zijn voor de gewone uitrolpaden hersteld. S1 kan bij een overstap met oude bordrijen nog oproepen uit de telling laten verdwijnen.

### Voor Mehdi

| Punt | Oordeel |
|---|---|
| S1 | Gedeeltelijk. Een proef met vijf oude oproepen en een lege of sterk uitgedunde Macbron eindigde zonder fout, maar markeerde alle vijf oude oproepen als vervallen. Claude meldt dat er nu geen oude rijen op het bord staan; ik kon dat niet zelf live controleren. |
| S2 | Opgelost. De helper ruimt alleen zijn exacte uitvoernamen op; de test bewaart een ander bestand. |
| S3 | Opgelost. Een wacht die geladen blijft of haar rondeslot vasthoudt, blokkeert de codewissel. |
| S4 | Opgelost voor gewone opdrachten. Het uitrolslot omvat ook `proef` en `terug`; de test houdt het slot vast en ziet de uitrol stoppen. |

### Voor Claude en Shaniel

1. **T1, middel:** [mac_gesprekken.py:608](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:608). De rem negeert oude sleutels volledig. Mijn geheugenproef gaf bij vijf oude rijen en nul of één nieuwe rij respectievelijk vijf vervallen rijen, zonder fout. Bovendien herkent `HUIDIGE_SLEUTEL` een oude WhatsApp sleutel zoals `whatsapp-oproep:ID-42` als nieuw. [De S1-test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:761) beproeft alleen een volledige bron. Vergelijk oude en nieuwe bronoproepen expliciet vóór het vervallen markeren; test ook lege en gedeeltelijke bronnen en oude sleutels met een numeriek achtervoegsel.

2. **T2, laag:** [uitrol_mac_gesprekken.sh:101](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:101). Een vooraf ingestelde `UITROL_SLOT` laat de interne opdrachten de controles omzeilen. Maak de interne wissel alleen bereikbaar vanuit het proces dat de sloten werkelijk vasthoudt en test een directe aanroep.

Gedaan: beide diffs en de broncode alleen gelezen.  
Nagekeken: tests, shellsyntaxis en twee geheugenproeven; Mac-tests niet herhaald.  
Open: T1 en T2.

live: nee