# Opdracht voor Claude 1 op de MacBook (01-11-2026)

Van Claude 2 (servers en bouw) aan Claude 1 (op de MacBook van Mehdi).
De server staat al live sinds 01-11-2026 08:07. Deze opdracht zet de laptopkant aan.

Vaste regels:
- Nooit uitloggen of opnieuw inloggen bij Claude. Werk met het account dat er is.
- Mehdi's toestellen staan in het Engels. Menunamen hieronder staan zoals op het scherm.
- Niets wissen. Een stap die faalt: stoppen, de laatste 20 regels van de uitvoer bewaren en melden.
- Waar "Mehdi" staat, vraag je Mehdi die ene klik of dat wachtwoord. De rest doe je zelf.

Wat dit oplost:
- De Fotowacht staat op rood door 8 oude werfverslagtaken die op gegevens wachten. De nieuwe code meldt dat niet meer als fout.
- De Sms-wacht (nieuw) telt sms en iMessage: wie, wanneer, hoeveel. Nooit de tekst.
- De YouTube-wacht (nieuw) telt video's uit de browsergeschiedenis. Alleen titels.
- De Wispr-wacht wordt vanzelf weer groen bij zijn volgende ronde op de laptop.

## Stap 0. Nakijken

    cd ~/dev/globaal-appportal && git status --short | head
    ssh -o BatchMode=yes globaal true && echo "VM ok"

Staan er lokale wijzigingen in de repo: niet overschrijven, melden.

## Stap 1. Code ophalen

    cd ~/dev/globaal-appportal
    git pull --rebase origin main
    git log --oneline -1

De uitrolscripts zetten de wachten zelf in een eigen worktree op origin/main.

## Stap 2. iPhone klaarzetten voor sms (Mehdi, op de iPhone)

1. Settings, tik op je naam bovenaan, iCloud, See All, Messages in iCloud: zet "Use on this iPhone" aan.
2. Settings, Apps, Messages, Text Message Forwarding: zet de MacBook aan.

Op de MacBook: open Messages, menu Messages, Settings, tab iMessage, zet "Enable Messages in iCloud" aan.

## Stap 3. Hulpprogramma opnieuw bouwen

    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh installeer

Het hulpprogramma MacGesprekkenKopie is nieuw gebouwd (sms erbij), dus macOS vraagt opnieuw toestemming.

**Mehdi, op de MacBook:** open System Settings, Privacy & Security, Full Disk Access.
Zet MacGesprekkenKopie uit en weer aan. Staat het er niet: klik op +, en kies het programma
dat het script als laatste toonde. Vraagt macOS om "Quit & Reopen": klik op Later.

## Stap 4. Proef en aanzetten

    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh proef
    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh aan
    zsh mijnagents-runner/mac/uitrol_mac_gesprekken.sh controleer

WhatsApp en Belwacht iPhone staan uit tot de proef slaagt: deze stap niet overslaan.
De sms-proef mag apart falen. Dan blijven WhatsApp en Belwacht aan en staat alleen de Sms-wacht uit.
Faalt de sms-proef met "0 berichten": stap 2 nakijken, 10 minuten wachten, proef en aan opnieuw.

## Stap 5. Fotowacht bijwerken

    zsh mijnagents-runner/mac/uitrol_icloud_wacht.sh
    zsh mijnagents-runner/mac/uitrol_icloud_wacht.sh --controleer

**Mehdi:** typ het wachtwoord van de MacBook als Terminal erom vraagt. De controle moet "gelijk" melden.
Meldt hij iets anders: eerst `zsh mijnagents-runner/mac/uitrol_icloud_wacht.sh --herbouw-starter`,
en daarna geeft Mehdi in System Settings, Privacy & Security, Full Disk Access de app iCloudWacht opnieuw toegang.

## Stap 6. YouTube-wacht

    mkdir -p ~/.claude/tools/mijnagents
    cp mijnagents-runner/mac/youtube_wacht.py ~/.claude/tools/mijnagents/
    /usr/bin/python3 ~/.claude/tools/mijnagents/youtube_wacht.py --droog | head -30

Toont het een overzicht per dag, dan aanzetten:

    cp mijnagents-runner/mac/be.globaal.mijnagents.youtube.plist ~/Library/LaunchAgents/
    launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/be.globaal.mijnagents.youtube.plist
    launchctl kickstart gui/$(id -u)/be.globaal.mijnagents.youtube

Zegt hij "geen browsergeschiedenis gevonden" of "Operation not permitted":
**Mehdi:** System Settings, Privacy & Security, Full Disk Access: klik op +, druk Command Shift G,
typ /usr/bin/python3 en klik op Open. Daarna de droge proef opnieuw.

## Stap 7. Dropbox-sync

De Dagbundelaar meldt dat "Data uit Mehdi" niet synchroniseert. Volg stap 6 van
`mijnagents-runner/docs/laptop-inrichten-voor-de-dagbundelaar.md`.

## Stap 8. Nakijken en melden

Na een uur, op mijnagents.globaal.be, groep Dagbundelaar:
- De Sms-wacht, De YouTube-wacht, De Fotowacht, De WhatsApp-wacht, De Belwacht iPhone en De Wispr-wacht staan op klaar.

Meld aan Mehdi in één bericht: welke stappen gelukt zijn, welke niet, en bij een fout de laatste
regels uit `~/Library/Logs/mijnagents/`. Mehdi zet dat bericht door naar Claude 2.

Niet in deze opdracht (andere thread, eigen document): De Websitewacht en De Gezondheidswacht
(Health Auto Export), zie `wispr-websites-gezondheid-naar-het-dagboek.md`.
