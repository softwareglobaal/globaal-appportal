# Wispr, websites en gezondheid naar het Dagboek (voor Claude 1 op de laptop, en twee stappen voor Mehdi)

Stand 31-10-2026. Vaste regels: nooit uitloggen of opnieuw inloggen bij Claude. Niets wissen, niets versturen.
Mehdi's toestellen staan in het Engels: de menunamen hieronder staan zoals op het scherm.

## Wat er al is

- Wispr Flow: de Wispr-wacht telt elke avond om 21:30 dictaten, woorden en minuten. Nooit de tekst. Werkt.
- Gezondheid: de Gezondheidswacht draait elke ochtend, maar vindt niets: de map
  `~/TKN-buro Dropbox/private/0 Chegini Mehdi/Prive met Claude/Data Appel Watch/inbox` is leeg.
  Health Auto Export op de iPhone stuurt nog geen bestanden.
- Websites: nieuw, de Browserwacht (`mac/browser_wacht.py`). Leest Chrome, Edge, Firefox en Safari, elk uur. Alleen de
  naam van de site (monday.com), nooit het volledige adres, nooit een zoekopdracht of titel.

## Voor Claude 1 op de laptop

> Vervangen voor de Websitewacht (01-11-2026, T-0120 WEB-1 en YT-1): browser_wacht.py en youtube_wacht.py lezen nu de
> kopie van MacGesprekkenKopie (set browser) en draaien uit de eigen worktree. Stap 2 tot 5 voor de Websitewacht gaan
> via `mac/uitrol_mac_gesprekken.sh` (installeer, proef, aan), nooit meer met de hand naar `~/.claude/tools`. Nooit
> Full Disk Access voor Python. Stap 6 en 7 (Wispr, gezondheid) blijven zoals hieronder.

1. `git -C ~/dev/globaal-appportal pull --rebase origin main`
2. Kopieer de twee wachten naar de vaste plek:
   `cp ~/dev/globaal-appportal/mijnagents-runner/mac/browser_wacht.py ~/dev/globaal-appportal/mijnagents-runner/mac/wispr_wacht.py ~/.claude/tools/mijnagents/`
3. Proef zonder iets te sturen: `/usr/bin/python3 ~/.claude/tools/mijnagents/browser_wacht.py --droog --dagen 2`.
   Je ziet bezoeken per dag en per browser. Staat Safari bij "onleesbaar" en gebruikt Mehdi Safari niet, laat het zo.
4. Zet de Browserwacht aan:
   `cp ~/dev/globaal-appportal/mijnagents-runner/mac/be.globaal.mijnagents.browser.plist ~/Library/LaunchAgents/`
   `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/be.globaal.mijnagents.browser.plist`
   `launchctl kickstart gui/$(id -u)/be.globaal.mijnagents.browser`
5. Controle: op mijnagents.globaal.be staat browser-wacht op "klaar". Log: `~/Library/Logs/mijnagents/browser_wacht.log`.
6. Draai de Wispr-wacht een keer met de hand: `/usr/bin/python3 ~/.claude/tools/mijnagents/wispr_wacht.py`.
   Hij stuurt nu ook de laatste 14 dagen mee, zodat een dag na 21:30 niet verloren gaat.
7. Gezondheid: kijk in `~/bin/gezondheid.py` uit welke map hij leest (nu de map `inbox` hierboven). Zodra Mehdi de
   stappen hieronder deed, staat er binnen een dag een JSON-bestand van Health Auto Export. Komt het in iCloud Drive
   (map `Health Auto Export`) en niet in de inbox, laat `gezondheid.py` dan ook die map lezen. Proef:
   `/usr/bin/python3 ~/dev/globaal-appportal/mijnagents-runner/mac/gezondheid_wacht.py --dag <gisteren>`; op het bord
   moet gezondheid-wacht "gegevens aanwezig" melden.
8. Geef Mehdi in vijf regels: wat werkt, wat niet.

## Voor Mehdi op de iPhone (twee stappen)

1. Open de app **Health Auto Export**. Staat ze niet op je iPhone, installeer ze uit de **App Store**.
   Geef toegang tot alles als **Health** het vraagt (**Turn On All**, dan **Allow**).
2. Tik onderaan op **Automations**, dan op **+** (New Automation):
   - **Automation Type**: **iCloud Drive**
   - **Data Type**: **Health Metrics**
   - **Export Format**: **JSON**
   - **Date Range**: **Yesterday** (of **Since Last Sync**)
   - **Sync Cadence**: elke dag, bijvoorbeeld 06:00
   - zet de automatisering **On** en tik **Save**.

Ziet je scherm er anders uit, stuur een screenshot naar Claude: dan duid ik aan waar je moet tikken.

Wat je daarna ziet: in het Dagboek, bij elke dag, het blok "Eigen werk en gezondheid" met Wispr, websites en de
cijfers van je Apple Watch (stappen, hartslag in rust, slaap). Een dag zonder gegevens staat als "onbekend", nooit als 0.

## Getypte tekst

Niet gebouwd. Wat je typt bijhouden kan alleen met een toetsenbord-registratie (Input Monitoring). Die ziet ook
wachtwoorden en privéberichten. Advies: niet doen; Wispr en de websites tonen al waar je aan werkte. Dat is jouw keuze.
