# Controle 26 door Codex: vereenvoudiging na overleg 25 (tak aankoop-herstart, commit 551aa72)

Lees alleen; wijzig niets. Kort. Alleen De Prijsonderzoeker.

Overleg 25 (`rapport-25-herstart.md`) besliste 2-1 voor optie A (K2): vereenvoudigen. De weigering bij
`overageStatus: "allowed"`, de proefpoort met merkteken en de eis van een limietmelding voor "klaar" vervallen. Wat blijft:
stop bij `isUsingOverage`, boven 90 procent, bij een andere bron dan het abonnement. Nieuw: niet starten als de vorige
meting boven 90 procent lag en het venster nog niet herstart is. Jouw stem was B; het besluit is A. Toets de uitvoering
van A, niet de keuze.

1. Is A correct gebouwd (`git diff origin/main..551aa72`)? Een concreet scenario waarin de code afwijkt van K2?
2. Een nieuwe fout van ernst hoog? Mag dit live, waarna een keer de MOVA-vraag draait?

Geef bovenaan: klaar, klaar met kanttekeningen, of niet klaar.
