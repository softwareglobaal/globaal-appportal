# Ontwerp De Mehdi-agent, versie 1 (31-10-2026)

Code: `mehdi_agent.py`. Werkwijze (zaad): `werkwijze/mehdi-agent.md`. Tests: `tests/test_mehdi_agent.py`.
Planning: `planning/mehdi-agent.cron` met `planning/mehdi_agent_cron_zetten.py`.

## De opdracht

Mehdi, 31-10-2026: De Dagbundelaar bundelt, en daarboven komt een aparte agent die de zaken voor hem analyseert, de
berichten leest en zijn taken en to-do's klaarzet, tot zes keer per dag. Dezelfde dag erbij: die agent doet meer dan een
lijst. Hij doet to-do's waar het kan, leert opdrachten naar de juiste persoon of agent te sturen, en leert Mehdi zijn
dagen en werk beter te organiseren.

Keuze van Mehdi over de bron (31-10-2026): een vaste plek, een bestand per dag. De agent leest alleen de dagbundel, en
gaat alleen via de verwijzing in de bundel naar de bron als hij meer detail nodig heeft.

## Wat hij leest

| Bron | Waar | Waarvoor |
|---|---|---|
| De dagbundel van vandaag en de twee dagen ervoor | `mijnagents-data/dagboek/JJJJ/JJJJ-MM-DD.md` en `.json` op de VM; de Dropbox-map Dagbundelaar is daar een kopie van | de taken zelf |
| Wat Mehdi tegen de agent zei | tabel `gesprek` van het bord, `aan = 'mehdi-agent'`, alleen lezend (`bord.db_lees`) | correcties, nummers ("2 is gedaan"), regels om te leren |
| De collega's | kern via `koppelingen/organisatie.py`: naam, functie, afdeling, firma | dispatchen naar een collega |
| De agents op het bord | `r.collegas` (N14) | dispatchen naar een agent |
| Zijn eigen staat | `mijnagents-data/mehdi-agent/staat.json` | open taken, nummers, geleerde regels |

Hij leest nooit zelf een wacht, een mailbox, WhatsApp of een transcript. Hij leest de bundel op de VM en niet de
Dropbox-kopie: die kopie maakt de Mac, en hij moet niet wachten tot de Mac wakker is.

## Wat hij doet, per ronde

1. Grenzen uit de werkwijze (N2); zonder grenzen geen werk.
2. De bundel lezen. Geen bundel van de laatste drie dagen: nood, niets klaargezet (onbekend is niet leeg).
3. Moment bepalen op de Brusselse klok: de eerste ronde tussen 07:00 en 12:00 is de ochtend, de eerste vanaf 19:00 de
   avond, de rest tussendoor. Tussendoor zonder nieuwe bundel en zonder nieuw bericht van Mehdi: geen aanroep van Claude.
4. Claude (`claude-opus-5-5`, effort medium, gestructureerd antwoord met een strikt JSON-schema, server-side fallback
   zoals `weekconsolidatie.py`) krijgt de werkwijze van het bord letterlijk (N12), de collega's op het bord (N14), de
   gedeelde lessen (N13), en als invoer de bundel, de open taken met hun nummer, de onlangs afgeronde taken, wat Mehdi
   zei, de geleerde regels en de collega's uit kern.
5. Elke taak gecontroleerd zonder model:
   - een nieuwe taak zonder bron die letterlijk in de bundel of in Mehdi's woorden staat, valt weg;
   - een collega die niet in kern staat, of een agent die niet op het bord staat, wordt Mehdi;
   - iets met privé in bron, tekst of reden gaat nooit naar een ander;
   - hoogstens twaalf nieuwe taken per ronde en veertig open; een taak die veertien dagen niets nieuws kreeg, vervalt;
   - een regel leert hij alleen als Mehdi die ronde iets zei.
6. Klaarzetten voor Mehdi en teruglezen:
   - `soort: taken`, uniek `mehdi-agent:taken:JJJJ-MM-DD`: de lijst van de dag, genummerd, in drie groepen (voor jou,
     voor een collega, voor een agent), met reden, bron en concept; volgt de staat zolang het item niet opgepakt is;
     was het opgepakt, dan komt de nieuwe versie ernaast met het uur in de sleutel;
   - `soort: verslag`, `Te doen vandaag DD-MM` ('s ochtends) en `Avondoverzicht DD-MM` met een tip ('s avonds). De Bode
     bundelt die in het ochtend- en avondbericht.
   Titels en werkverslag dragen geen namen.
   Mehdi ziet de nieuwste lijst en het nieuwste verslag op https://mijnagents.globaal.be/agent/mehdi-agent, blok
   "Laatst klaargezet" (alleen beheer; HTML en links uit een bron worden tekst).
7. Lukt Claude niet, dan blijft de lijst van de vorige ronde staan, met een nood, en probeert de volgende ronde opnieuw.

## Doen en dispatchen in versie 1

- Doen: hij schrijft concepten (een bericht of een mail) die Mehdi zelf stuurt. Hij verstuurt nooit zelf iets.
- Dispatchen: bij elke taak staat voor wie ze is. Een taak voor een agent zet hij nog niet bij die agent klaar: een
  ontvanger als De Plaudwacht leest elk `verzoek` als een eigen opdracht, en dat zou ruis geven. Mehdi beslist per
  soort wanneer de agent zelf mag doorsturen (werkwijze, Wat Mehdi beslist).
- Leren: Mehdi zegt via WhatsApp of op het bord "Mehdi-agent, 3 gaat naar" en een naam, of "2 is gedaan". De Regisseur
  antwoordt in de rol van de agent; de volgende ronde leest de agent dat gesprek, past de taak aan en bewaart een regel.

Volgende stap, pas na Mehdi's ja: een runbook dat een goedgekeurd concept via De Bode verstuurt, of een taak als
activiteit in Pipedrive zet, telkens als voorstel op het bord.

## Ritme

De cron draait elk uur op :20 (`20 * * * *`, met flock en een tijdslimiet van 40 minuten). De agent kijkt zelf of het
een van zijn uren is in Brussel: standaard 7, 10, 13, 16, 19 en 22 uur (`MEHDI_AGENT_UREN`), twintig minuten na de
rondes die De Dagbundelaar krijgt in het driehoeksoverleg Dagboek compleet (P5). De VM draait in UTC en Debian-cron kent
geen tijdzone; zo volgt het ritme de zomer- en wintertijd met een regel.

## Wat hij nodig heeft van De Dagbundelaar

Afgesproken met de taak Dagboek compleet (punt P7 van dat driehoeksoverleg):
1. per gesprek in Fathom, Zoom en Plaud: tijd, met wie, minuten, titel, samenvatting, actiepunten en een verwijzing;
2. per gesprek in WhatsApp, sms en telefoon: met wie, aantal in en uit, het laatste bericht en of de ander op antwoord
   wacht, en gemiste oproepen zonder terugbellen;
3. per postvak de mails die op antwoord wachten (afzender, onderwerp, sinds), zonder tekst;
4. de afspraken van vandaag, en in de laatste ronde ook van morgen;
5. bovenaan het tijdstip waarop de bundel gemaakt is.
Tot dan werkt de agent met wat de bundel nu heeft (Gepland, Niet gepland, Communicatie): afspraken die niet zeker
doorgingen, gesprekken zonder verslag, gemiste oproepen die de bundel noemt. Zodra de nieuwe blokken er zijn, leest
Claude ze mee zonder codewijziging; alleen de bron moet letterlijk in de bundel staan.

## Privacy

- Het dagbestand is al gemaskeerd door De Dagbundelaar (privé is "privé" of een aantal).
- Een privétaak blijft bij Mehdi; titels en werkverslag dragen geen namen; het logboek krijgt alleen aantallen.
- Berichttekst: de agent leest ze niet. Of dat verandert, is een keuze van Mehdi (kaart van 31-10-2026).
- De repo is publiek: de tests gebruiken alleen verzonnen namen (`tests/test_geen_echte_namen.py`).

## Kosten

Claude Opus 5.5 kost 4 dollar per miljoen tokens in en 20 dollar per miljoen uit. Een ronde leest ongeveer 20.000 tot
40.000 tokens en schrijft er enkele duizenden, samen ongeveer 0,20 tot 0,35 dollar. Met overslaan als er niets nieuws is,
zijn dat twee tot zes rondes met Claude per dag: naar schatting 15 tot 60 dollar per maand. Ander model kiezen kan met
`MEHDI_AGENT_MODEL`.

## Live zetten (gedaan op 31-10-2026, op Mehdi's ja)

Alles via `softwareglobaal/globaal-vm-beheer` (workflow vm):
1. De code komt op de VM met de volgende pull van `~/appportal`; zonder kaart en cron doet ze niets.
2. Droog proberen, zonder bord of staat te raken (alleen de vorm in het logboek, het volledige resultaat in een
   bestand voor beheer):
   `MEHDI_AGENT_STAAT=/tmp/mehdi-proef.json ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/mehdi_agent.py --droog --zaad --moment ochtend --stil --uit ~/appportal/mijnagents-data/mehdi-agent/droog.md`
   Gedaan op 31-10-2026 (workflow vm, run 41232708315), met de code uit `git show` in een tijdelijke map zodat de pull
   niets anders live zette: dagbestanden van 29 en 30-10, 8 taken (6 voor Mehdi, 2 voor een agent), geen enkele zonder
   bron geweigerd, 4 punten die de bundel miste, 19.064 tokens, exit 0. Volledig resultaat (rechten 600) in
   `mijnagents-data/mehdi-agent/droog-20261031.md` op de VM.
   Daarna, voor stap 3: het driehoeksoverleg (`opdracht-driehoeksoverleg-mehdi-agent.md`) zonder open punten van
   ernst hoog of middel (AGENTNORM.md 8).
3. Aanmaken met de generator. Die weigert een runner met eigen code, dus het skelet gaat naar een tijdelijke map
   (`RUNNERMAP`, zoals in `tests/test_nieuwe_agent.py`); de kaart en de werkwijze komen op het bord met alle controles
   van de generator. In `~/appportal/mijnagents-runner`:
   `~/agents/.venv/bin/python -c "import importlib.util as u, sys, tempfile; s = u.spec_from_file_location('na', 'nieuwe-agent.py'); m = u.module_from_spec(s); s.loader.exec_module(m); m.RUNNERMAP = tempfile.mkdtemp(); sys.exit(m.main(sys.argv[1:]))" --naam mehdi-agent --label "De Mehdi-agent" --type regie --prive --rol "zet de taken van Mehdi klaar uit de dagbundel, met concepten en voor wie" --mandaat "lezen en klaarzetten, nooit versturen" --cadans "zes keer per dag" --mag "taken klaarzetten" --mag "concepten schrijven" --grens "nooit iets versturen" --grens "alleen de dagbundel lezen" --levert-aan mehdi --werkwijze werkwijze/mehdi-agent.md`
4. De eerste ronde, met elk uur toegestaan: `MEHDI_AGENT_UREN=0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23 nieuwe-agent.py --eerste-ronde mehdi-agent --cron "20 * * * *"`.
5. De planning: `python3 planning/mehdi_agent_cron_zetten.py --zet`.

Gedaan op 31-10-2026 op Mehdi's ja ("alles nu live", voor het driehoeksoverleg), in een run van de workflow vm
(41240626256): pull van `~/appportal`, wachten tot het bord uitgerold was, stap 3, stap 4 (alle 14 normen ok, 2 items
klaargezet), stap 5 (planning gezet en nagelezen).
