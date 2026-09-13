# Handleiding: de Wispr-wacht op de computer van elke gebruiker

Versie 1.0, 13-09-2026. Voor Shaniel, in opdracht van Mehdi.

## Waarvoor

Mehdi wil weten wie Wispr Flow gebruikt en wie niet (20 betaalde zetels). Het beheerportaal
van Wispr Flow toont dat per persoon alleen op een duurder plan; Mehdi betaalt niet extra.
De Wispr Flow-app bewaart op elke computer een lokale databank met per dictaat tijd, aantal
woorden, duur en app. Het script `wispr_wacht.py` leest daar elke avond de **tellingen** uit
en stuurt ze naar het bord Mehdi Agents. **Nooit de tekst van een dictaat**; dat staat ook zo
in de code, en de gebruiker mag het nalezen.

## Wat de gebruiker ziet

Niets, behalve dat er een taak op zijn computer draait. Op het bord verschijnt per persoon:
dictaten, woorden, minuten spreken, per app, per dag, en een oordeel per week (gebruikt vanaf
1.000 woorden, weinig gebruikt, niet gebruikt). Zeg het de collega vooraf: alleen aantallen.

## Wat je nodig hebt

- Het script: `mijnagents-runner/mac/wispr_wacht.py` uit de repo (werkt op macOS en Windows).
- Python 3 op de computer (macOS heeft het; Windows: python.org, "Add to PATH" aanvinken).
- Het bordtoken: `AGENTS_TOKEN` uit `~/appportal/mijnagents-data/.env` op de VM. Zet het op de
  computer in `~/.config/mijnagents/token` (macOS) of `%USERPROFILE%\.config\mijnagents\token`
  (Windows), één regel, alleen het token. Niet in chat of mail plakken.
- De naam van de gebruiker zoals in de organisatiedatabase (voornaam), als `WISPR_GEBRUIKER`.

## macOS (3 stappen)

1. Script naar `~/.claude/tools/mijnagents/wispr_wacht.py` (map aanmaken als ze niet bestaat), token naar `~/.config/mijnagents/token`.
2. Test: `WISPR_GEBRUIKER=Voornaam /usr/bin/python3 ~/.claude/tools/mijnagents/wispr_wacht.py` — de uitvoer eindigt met "rapport in ...".
3. Avondtaak: kopieer `be.globaal.mijnagents.wispr.plist` (in de repo onder `mac/`) naar `~/Library/LaunchAgents/`, pas het pad en `WISPR_GEBRUIKER` aan, dan
   `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/be.globaal.mijnagents.wispr.plist`.

## Windows (3 stappen)

1. Script naar `C:\Users\<naam>\mijnagents\wispr_wacht.py`, token naar `C:\Users\<naam>\.config\mijnagents\token`.
2. Test in PowerShell: `$env:WISPR_GEBRUIKER="Voornaam"; python C:\Users\<naam>\mijnagents\wispr_wacht.py`
   Het script zoekt de databank zelf: `%APPDATA%\Wispr Flow\flow.sqlite`. Bestaat die niet, dan is de app daar niet geïnstalleerd; dat meldt het script op het bord.
3. Dagelijkse taak (Task Scheduler), één regel in PowerShell als de gebruiker:
   ```
   schtasks /Create /SC DAILY /ST 21:30 /TN "Mehdi Agents Wispr-wacht" /TR "cmd /c set WISPR_GEBRUIKER=Voornaam&& python C:\Users\<naam>\mijnagents\wispr_wacht.py" /F
   ```
   Op Windows landt het rapport in `%USERPROFILE%\Dropbox\Data uit Mehdi\Wispr-wacht\` als die map er is; anders alleen op het bord. Zet `WISPR_RAPPORT` als de Dropbox elders staat.

## Controle

Op het bord: De Wispr-wacht toont per persoon de laatste melding. In Data uit Mehdi/Wispr-wacht
staat per gebruiker een `.md`. De serverkant van de Wispr-wacht vergelijkt elke avond de ledenlijst
van het beheerportaal met wie een pc-script heeft; wie ontbreekt staat in zijn nood op het bord.

## Volgorde (voorstel)

Eerst de collega's met de meeste kans op niet-gebruik (Mehdi beslist), daarna de rest. Per computer
tien minuten. Meld op het bord (of aan Claude Code) wie klaar is.
