## Voor Mehdi

**Niet klaar.** De privévlag en de rijnamen sluiten grotendeels aan op fase 1. De helper kopieert echter ook berichttekst, en enkele telregels kunnen het dagoverzicht onjuist maken.

## Voor Claude en Shaniel

1. **P1, hoog.** [Ontwerp:338](/Users/mehdichegini/dev/_dagvaststelling-f2/docs/ontwerp-dagvaststelling.md:338), [helper:149](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:149). `sqlite3_serialize` bewaart de volledige WhatsApp-databank, inclusief berichttekst, in een kopie die andere processen van dezelfde gebruiker kunnen lezen. Een eigen helper is de juiste keuze tegenover de Python-starter, maar laat hem uitsluitend toegestane metadata afleveren.

2. **P2, hoog.** [Helper:144](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:144). De claim dat de kopie recente WAL-gegevens bevat, is niet aangetoond. [SQLite beschrijft serialisatie van een schijfdatabank als een schijfkopie](https://www.sqlite.org/c3ref/serialize.html), terwijl recente transacties nog in de [WAL](https://www.sqlite.org/wal.html) kunnen staan. Dit is een risico afgeleid uit die documentatie. Toets een ongecheckpointte transactie vóór gebruik van de kopie.

3. **P3, hoog.** [Ontwerp:375](/Users/mehdichegini/dev/_dagvaststelling-f2/docs/ontwerp-dagvaststelling.md:375), [app:1626](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/app.py:1626). Elke WhatsApp-chatrij met lege `dubbel_van` verhoogt op de dagenpagina het aantal gesprekken. Sluit chatrijen daar uit en toets chat, beantwoorde oproep, gemiste oproep en dekking samen.

4. **P4, hoog.** [Ontwerp:383](/Users/mehdichegini/dev/_dagvaststelling-f2/docs/ontwerp-dagvaststelling.md:383), [dagbundelaar:619](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/dagbundelaar.py:619). Een gebeurtenis ná dag D bewijst niet dat WhatsApp of de iPhone tijdens D gegevens doorgaf. Die dekkingsrij kan een ontbrekende dag als nul laten verschijnen. Vereis bewijs van dekking tijdens D; toon anders onbekend.

5. **P5, hoog.** [Ontwerp:375](/Users/mehdichegini/dev/_dagvaststelling-f2/docs/ontwerp-dagvaststelling.md:375), [dagvaststelling:76](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/dagvaststelling.py:76). Alleen `HH:MM` verliest het tweede uur bij wintertijd. Een geheugenproef las beide keren 02:30 als zomertijd, waardoor bewijs bij een afspraak verkeerd kan vallen. Bewaar een UTC-tijdstip en toets beide klokwissels.

6. **P6, hoog.** [Ontwerp:320](/Users/mehdichegini/dev/_dagvaststelling-f2/docs/ontwerp-dagvaststelling.md:320), [app:699](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents/app.py:699). De oproep-ID is slechts voor één week uniek gemeten; een latere botsing overschrijft stil een rij. Ook is het providerfilter voor dubbele WhatsApp-oproepen niet bewezen met de gemeten iPhone-rijen. Detecteer ID-botsingen en vergelijk oproepen tussen beide bronnen vóór schrijven.

7. **P7, hoog.** [Ontwerp:363](/Users/mehdichegini/dev/_dagvaststelling-f2/docs/ontwerp-dagvaststelling.md:363), [venster:51](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/dagvaststelling.py:51). Na meer dan veertien dagen zonder Mac-ronde vallen oudere gegevens buiten beide vensters. Bewaar een inhaalwatermerk en herbereken ook de gemiste oudere dagen.

8. **P8, hoog.** [Ontwerp:367](/Users/mehdichegini/dev/_dagvaststelling-f2/docs/ontwerp-dagvaststelling.md:367), [N4-controle:114](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/controle_agenten.py:114). Bij de nieuwe uurcadans vergelijkt N4 de ronde-ID niet meer. Een mislukte teruglezing met alleen `exit 1` kan een eerdere status `klaar` laten staan. Controleer de ID bij elke cadans, zet de eigen ronde op fout en schakel de oude runner met dezelfde naam gecontroleerd uit. N11 zal bij lang slapen terecht rood worden; N6 vereist nog gelijkheid tussen bord en zaad.

9. **P9, middel.** [Helper:57](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:57), [helper:195](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:195). Broncontrole en openen gebeuren afzonderlijk; een tijdstempel bindt `status.json` niet aan één aanvraag. Pin de bronidentiteit en gebruik een unieke kopiegeneratie. Toets schemawijziging, onderbroken kopie, twee gelijktijdige starts en exacte teruglezing, zonder bij een leesfout rijen als vervallen te markeren.

Gedaan: ontwerp en code alleen gelezen; niets gewijzigd.  
Nagekeken: rijcontracten en twee geheugenproeven voor telregel en wintertijd.  
Open: deze bevindingen en een toegangsproef van de definitieve helper onder launchd.

bouwen: nee