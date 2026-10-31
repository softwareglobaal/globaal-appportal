# Driehoeksoverleg starten: het Dagboek compleet en de Mehdi-agent (voor Claude 1 op de laptop)

Vaste regels: nooit uitloggen of opnieuw inloggen bij Claude. Niets wissen, niets versturen.
Mehdi's toestellen staan in het Engels.

1. Haal de laatste versie op:
   `git -C ~/dev/globaal-appportal pull --rebase origin main`
   `git -C ~/dev/driehoeksoverleg pull --rebase origin main`
2. Start het overleg over het Dagboek:
   `cd ~/dev/driehoeksoverleg && ./overleg.sh -C ~/dev/globaal-appportal -o ~/dev/samenwerking-codex/dagboek-compleet-20261031/rapport.md -t "Dagboek compleet" < ~/dev/globaal-appportal/mijnagents-runner/docs/opdracht-driehoeksoverleg-dagboek-compleet.md`
3. Start daarna het overleg over de Mehdi-agent:
   `cd ~/dev/driehoeksoverleg && ./overleg.sh -C ~/dev/globaal-appportal -o ~/dev/samenwerking-codex/mehdi-agent-20261031/rapport.md -t "Mehdi-agent" < ~/dev/globaal-appportal/mijnagents-runner/docs/opdracht-driehoeksoverleg-mehdi-agent.md`
4. Geef Mehdi de beslissing bovenaan elk verslag, hoogstens vijf regels per verslag, en de ene ja/nee-vraag over
   berichttekst.
5. Zet de verslagen in de projectmap dagbundelaar als `rapport-dagboek-compleet.md` en `rapport-mehdi-agent.md`, of
   plak ze in de chat met Claude 2, zodat Claude 2 kan bouwen.
