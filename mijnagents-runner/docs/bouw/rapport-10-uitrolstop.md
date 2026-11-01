AKKOORD.

Losse bestanden blijven staan: `git pull --ff-only` stopt bij een padconflict ([uitrol.sh:19](mijnagents-runner/docs/bouw/uitrol.sh:19)).  
Kopiëren, verwijderen en genereren gebeurt uitsluitend in de tijdelijke map ([uitrol.sh:27](mijnagents-runner/docs/bouw/uitrol.sh:27)).  
`--eerste-ronde` leest en start de bestaande runner, maar schrijft niets in de werkboom ([nieuwe-agent.py:290](mijnagents-runner/nieuwe-agent.py:290)). Alleen de bedoelde `git pull` kan gevolgde bestanden bijwerken.