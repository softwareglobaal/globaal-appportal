# Opdracht 10: controle van de stop in uitrol.sh (01-11-2026)

Kijk de wijziging in `mijnagents-runner/docs/bouw/uitrol.sh` na (tak bouw-uitrol-losse-bestanden, vergelijk met origin/main).
Antwoord in het Nederlands, kort: AKKOORD of NIET AKKOORD, met reden en bewijs (bestand:regel).

Context: het script draait op de server in een git-werkboom op main. In `mijnagents-runner` staan twee bestanden buiten
git die van andere agents zijn, niet van deze uitrol. De oude stop keek ook naar losse bestanden en hield de uitrol tegen.
De nieuwe stop kijkt alleen naar gewijzigde bestanden uit git (`--untracked-files=no`).

Vraag: kan het script met de nieuwe stop iets van die losse bestanden verliezen of overschrijven, of iets anders in de
echte werkboom wijzigen? Let op `git pull --ff-only`, `cp -a` naar een tijdelijke kopie, de generator `nieuwe-agent.py`
in die kopie, en `--eerste-ronde` in de echte werkboom (lees `mijnagents-runner/nieuwe-agent.py`).
