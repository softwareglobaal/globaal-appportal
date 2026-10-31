# Laptop: nieuwe wachten aanzetten (31-10-2026)

Voor Claude 1 op de laptop van Mehdi. Doe de stappen in volgorde. Mehdi hoeft alleen te
doen wat er bij "Mehdi" staat. Menunamen staan in het Engels, zoals op het scherm.

Wat dit oplost:
- De Fotowacht staat niet meer op rood door oude werfverslagtaken die op gegevens wachten.
- De Sms-wacht leest sms en iMessage (alleen wie, wanneer, hoeveel; nooit tekst).
- De YouTube-wacht telt video's uit de browsergeschiedenis (alleen titels, nooit zoekopdrachten).

## 1. Code bijwerken

    cd ~/dev/globaal-appportal
    git pull --rebase origin main

De uitrolscripts zetten de wachten zelf in een eigen worktree op origin/main.

## 2. Hulpprogramma opnieuw bouwen (sms erbij)

    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh installeer

Het hulpprogramma MacGesprekkenKopie is nieuw gebouwd, dus macOS vraagt opnieuw toestemming.

**Mehdi:** open System Settings, Privacy & Security, Full Disk Access. Zet MacGesprekkenKopie
uit en weer aan (staat het er niet, klik op +, kies het programma dat het script toont).

## 3. Proef en aanzetten

    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh proef
    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh aan
    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh controleer

Let op: WhatsApp en Belwacht iPhone staan uit tot de proef slaagt. De sms-proef mag apart
falen; dan blijven WhatsApp en Belwacht gewoon aan en staat alleen de Sms-wacht uit.

Faalt de sms-proef met "0 berichten": op de iPhone moeten Messages in iCloud en Text Message
Forwarding aan staan. Stappen staan in `docs/whatsapp-sms-iphone-naar-het-dagboek.md`.

## 4. Fotowacht bijwerken

    zsh mijnagents-runner/mac/uitrol_icloud_wacht.sh
    zsh mijnagents-runner/mac/uitrol_icloud_wacht.sh --controleer

**Mehdi:** typ je wachtwoord van de laptop als erom gevraagd wordt. De controle moet 'gelijk' melden.

## 5. YouTube-wacht

    mkdir -p ~/.claude/tools/mijnagents
    cp mijnagents-runner/mac/youtube_wacht.py ~/.claude/tools/mijnagents/
    /usr/bin/python3 ~/.claude/tools/mijnagents/youtube_wacht.py --droog | head -30

Toont het een overzicht per dag: dan aanzetten.

    cp mijnagents-runner/mac/be.globaal.mijnagents.youtube.plist ~/Library/LaunchAgents/
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/be.globaal.mijnagents.youtube.plist
    launchctl kickstart gui/$(id -u)/be.globaal.mijnagents.youtube

Zegt hij "geen browsergeschiedenis gevonden" of "operation not permitted":
**Mehdi:** System Settings, Privacy & Security, Full Disk Access, zet /usr/bin/python3 aan
(of Terminal, als dat er staat).

## 6. Dropbox

De Dagbundelaar meldt dat de Dropbox-synchronisatie op de Mac niet loopt. Zie stap 6 van
`docs/laptop-inrichten-voor-de-dagbundelaar.md`.

## 7. Klaar melden

Na een uur staan op mijnagents.globaal.be, groep Dagbundelaar, De Sms-wacht, De YouTube-wacht
en De Fotowacht op klaar. Meld in de thread welke stap niet lukte, met de laatste regels uit
`~/Library/Logs/mijnagents/`.
