# De Dagbundelaar: wie doet wat

**Dit is geen takenlijst meer.** Sinds 01-11-2026 is de werkstand de enige takenlijst, ook voor de Dagbundelaar, de
wachten, het Dagboek en Ai Angel (driehoeksoverleg T-0073, 14 punten aangenomen; ja van Mehdi in de chat op
01-11-2026). Twee lijsten die elk zeiden de enige te zijn, maakten onduidelijk wie wat moest doen.

## Waar dan wel

- De taken: repo softwareglobaal/werkstand, lokaal `~/dev/werkstand`. Bekijken met
  `python3 ~/dev/werkstand/werkstand.py lijst`; werk op jouw naam staat bovenaan onder "Voor jou".
- Wat op Mehdi wacht: `python3 ~/dev/werkstand/werkstand.py voor-mehdi`. Een chat vraagt Mehdi niets wat daar niet staat.
- Werk voor een andere Claude: `python3 ~/dev/werkstand/werkstand.py nieuw --titel "..." --doel "..." --voor claude1`.
- De werkwijze: `WERKWIJZE.md` in de werkstand, deel "Eén takenlijst".
- Claude 1, 2 en 3 zijn de toestellen uit `toestellen.json` (laptop, Mac mini, Mac Studio). Werk je vanuit een tweede
  Claude-account of de cloud, dan krijg je eerst een eigen id (taak T-0085).

De opdrachten in `opdrachten/` blijven als uitleg per stap; de taak in de werkstand verwijst ernaar. `naslag/` blijft
zoals het was.

## Waar de rijen van de oude tabel naartoe gingen

| Rij | Wat | Werkstand |
|---|---|---|
| 0 | Regel over de takenlijst in de eigen instellingen | Niet uitgevoerd; de regel staat in werkstand/instructies (T-0073) |
| 1 | Laptopkant: Sms-, WhatsApp- en Belwacht, Fotowacht, YouTube-wacht | T-0069 (sms, WhatsApp en Belwacht aan sinds 01-11 16:16), T-0042 (Fotowacht), T-0088 (YouTube-wacht). Dropbox-sync Data uit Mehdi draait al elke 30 minuten (log 01-11 16:54: klaar) |
| 2 | Websitewacht aan, Wispr-wacht draaien | T-0077 |
| 3 | Health Auto Export op de iPhone, map nakijken | T-0078 (wacht op Mehdi) |
| 4 | Driehoeksoverleg Dagboek compleet en Ai Angel | T-0079 |
| 5 | Plaud-routine op claude.ai | T-0080 |
| 6 | Mag Ai Angel berichttekst lezen | T-0079 zet de vraag met advies uit het verslag |
| 7 | Blok "Eigen werk en gezondheid" live | T-0079 zet de vraag met advies uit het verslag |
| 8 | Dagbundelaar: samenvatting, actiepunten, wie wacht, afspraken morgen | T-0081 |
| 9 | Ai Angel geeft taken echt door | T-0082 |
| 10 | Agendawacht: meldingen over titels en adressen | T-0083 |
| 11 | Laptopwachten groen op het bord | T-0088 (na het herstel van de YouTube-wacht) |
| 12 | Oproepen dubbel tellen (Xelion en iPhone), vanaf 08-11 | T-0084 |
| 13 (Mehdi) | Ja of nee: pagina Wachten in het Dagboek live | T-0087: ja 01-11 16:26, live 16:27. Overdracht aan Claude 1: `opdrachten/overdracht-pagina-wachten-01-11.md` |
| 14 | Na die ja: bord en Dagboek opnieuw bouwen, pagina nakijken | Gebouwd en nagekeken op de server; nakijken met Mehdi: zie de overdracht |
| 13 (Claude 2) | De nieuwe werkwijze lezen en toepassen, eigen id | T-0085 |

De oude tabel staat in de git-geschiedenis van dit bestand (laatste versie: commit b85103a).
