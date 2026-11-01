# De Dagbundelaar: wie doet wat

> **Regel voor elke Claude (Claude 1 en Claude 2) en elk agent:**
> lees dit bestand eerst, voor je iets doet aan de Dagbundelaar, de wachten, het Dagboek of Ai Angel.
> Werk het bij na elk werk: zet je rij op gedaan, zet er een nieuwe rij bij als er iets openkomt, en push naar main.
> Dit is de enige takenlijst. Wat hier niet staat, is niet afgesproken.

Plaats: repo globaal-appportal, `mijnagents-runner/docs/dagbundelaar/WIE-DOET-WAT.md`.
Laatst bijgewerkt: 01-11-2026 16:30 door Claude 1.

## Wie is wie

- **Mehdi**: beslist, en doet de klikken die alleen hij kan (iPhone, een wachtwoord, Full Disk Access).
- **Claude 1**: werkt op de MacBook van Mehdi (browser, account mch@h-architects.be). Voert de opdrachten uit.
- **Claude 2**: bouwt code en zet de server live (desktop-app, account hotmail). Schrijft de opdrachten.

## Hoe we samenwerken

1. Claude 2 schrijft een opdracht in de map `opdrachten/` en zet een rij in de tabel hieronder.
2. Claude 1 haalt de repo op (`git -C ~/dev/globaal-appportal pull --rebase origin main`), leest dit bestand en doet zijn rijen.
3. Claude 1 zet zijn resultaat in de kolom Stand (gedaan, of fout met de foutregel) en pusht. Mehdi hoeft niets door te sturen.
4. Een opdracht die niet meer geldt, gaat naar `opdrachten/vervallen/` met bovenaan VERVALLEN.
5. Overzichten en momentopnames staan in `naslag/`. Die zijn niet om uit te voeren.

## Open taken

| # | Wie | Wat | Opdracht | Stand |
|---|---|---|---|---|
| 0 | Claude 1 | De vaste regel over deze takenlijst in je eigen instellingen zetten. | `opdrachten/claude1-regel-takenlijst-instellen.md` | open |
| 1 | Claude 1 (Mehdi klikt mee) | Laptopkant aanzetten: Sms-wacht, Fotowacht, YouTube-wacht, Dropbox-sync. Mehdi zet Messages in iCloud en Text Message Forwarding aan op de iPhone, geeft Full Disk Access en typt het laptopwachtwoord. | `opdrachten/opdracht-claude1-macbook-01-11.md` | deels, 01-11 16:16 (Claude 1): Sms-wacht, WhatsApp-wacht en Belwacht aan, proef geslaagd, rondes op het bord. Full Disk Access werkte pas na verwijderen (-) en opnieuw toevoegen; uit en aan zetten hield de oude versie vast. Open: Fotowacht (wachtwoord Mehdi, werkstand T-0042); YouTube-wacht vindt onder launchd geen browsergeschiedenis (in Terminal wel), voor Claude 2. |
| 2 | Claude 1 | Websitewacht aanzetten en Wispr-wacht een keer draaien (stap 1 tot 6). Daarna de map van de Gezondheidswacht nakijken (stap 7). | `opdrachten/wispr-websites-gezondheid-naar-het-dagboek.md` | open |
| 3 | Mehdi | Health Auto Export op de iPhone instellen (twee stappen onderaan). | `opdrachten/wispr-websites-gezondheid-naar-het-dagboek.md` | open |
| 4 | Claude 1 | Driehoeksoverleg draaien over Dagboek compleet en Ai Angel. Verslagen in de map `naslag/` zetten als `rapport-dagboek-compleet.md` en `rapport-mehdi-agent.md`, en pushen. | `opdrachten/driehoeksoverleg-starten-voor-claude-1.md` | open |
| 5 | Claude 1 | Plaud-routine op claude.ai laten draaien. Er wachten 6 opnames op een transcript. | `../Plaud-routine instellen (voor Mehdi).md` | open |
| 6 | Mehdi | Kiezen: mag Ai Angel de tekst van berichten lezen (WhatsApp, sms)? Ja of nee. | geen | open |
| 7 | Mehdi | Ja of nee: blok "Eigen werk en gezondheid" live zetten in het Dagboek (kaart in de taak "Maak het dagboek compleet"). | geen | open, als nog niet beantwoord |
| 8 | Claude 2 | Na taak 4: de Dagbundelaar levert samenvatting en actiepunten van gesprekken, wie op antwoord wacht, afspraken van morgen, zes keer per dag. Ook de vaste Dropbox-map "Dagbundelaar". | `opdrachten/opdracht-driehoeksoverleg-dagboek-compleet.md` (P2, P5, P7) | wacht op taak 4 |
| 9 | Claude 2 | Ai Angel: taken echt doorgeven voor werk dat geen agent vanzelf oppakt. | `../ontwerp-mehdi-agent.md` | open |
| 10 | Claude 2 | De Agendawacht: meldingen over titels en adressen van afspraken wegwerken. | geen | open |
| 11 | Claude 2 | Na taak 1: op het bord nakijken dat alle wachten van de laptop groen staan. | geen | wacht op taak 1 |
| 12 | Claude 2 | Vanaf 08-11: nakijken of oproepen dubbel tellen (Xelion en iPhone). | geen | later |

## Gedaan (laatste dagen)

| Wanneer | Wie | Wat |
|---|---|---|
| 01-11 | Claude 2 | Server live: Sms-wacht, Belwacht Xelion, YouTube-wacht op het bord; Xelion draait elk uur. |
| 01-11 | Claude 2 | Ai Angel zet geen taak meer voor werk dat een agent vanzelf doet. |
| 31-10 | Claude 2 | Ai Angel live (7, 10, 13, 16, 19 en 22 uur). Alle Dagbundelaar-agents in één groep op het bord. |
| 31-10 | Claude 2 | Fotowacht en Wispr-wacht hersteld in de code. Dagboek toont locatie, gesprekken en de pagina Bronnen. |
| 28 tot 30-10 | Claude 1 | Laptop ingericht: WhatsApp-wacht en Belwacht iPhone groen. |

## Mappen

- `opdrachten/`: wat nog uitgevoerd moet worden.
- `opdrachten/vervallen/`: oude opdrachten, niet meer uitvoeren.
- `naslag/`: overzichten (welke agent, welke bron, stand op een dag) en afbeeldingen.
