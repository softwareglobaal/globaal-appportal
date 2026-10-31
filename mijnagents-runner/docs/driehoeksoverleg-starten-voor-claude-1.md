# Driehoeksoverleg starten: het Dagboek compleet (voor Claude 1 op de laptop)

Vaste regels: nooit uitloggen of opnieuw inloggen bij Claude. Niets wissen, niets versturen.
Mehdi's toestellen staan in het Engels.

1. Haal de laatste versie op:
   `git -C ~/dev/globaal-appportal pull --rebase origin main`
   `git -C ~/dev/driehoeksoverleg pull --rebase origin main`
2. Start het overleg:
   `cd ~/dev/driehoeksoverleg && ./overleg.sh -C ~/dev/globaal-appportal -o ~/dev/samenwerking-codex/dagboek-compleet-20261031/rapport.md -t "Dagboek compleet" < ~/dev/globaal-appportal/mijnagents-runner/docs/opdracht-driehoeksoverleg-dagboek-compleet.md`
3. Geef Mehdi de beslissing bovenaan het verslag, hoogstens vijf regels, en de ene ja/nee-vraag over berichttekst.
4. Zet het verslag in de projectmap dagbundelaar als `rapport-dagboek-compleet.md`, of plak het in de chat met
   Claude 2, zodat Claude 2 kan bouwen.
