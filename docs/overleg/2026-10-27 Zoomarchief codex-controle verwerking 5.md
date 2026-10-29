**Voor Mehdi — niet klaar.** Ik vond twee volgordes waarin de archivaris een opname als verloren meldt terwijl haar vervanger als gekopieerd in de staat staat. `SEIN_AAN=False` voorkomt een wisadvies, maar deze onterechte verliesmelding niet.

**Voor Claude en Shaniel**  
De regelnummers hieronder gelden voor commit `509930f`.

47. **Middel — `mijnagents-runner/zoom_archief.py:640-669, 683-684`.** A1 en A2 zijn in verwerking. B en C verschijnen later en worden gekopieerd, maar beide voorlopige ids onthouden alleen B. A1 gebruikt B; C verdwijnt uit Zoom terwijl de kopie bewezen blijft; A2 verdwijnt daarna. Na 24 uur wordt A2 toch `verdwenen`. Bewaar alle passende kandidaten en wijs elke vervanger hoogstens één keer toe. Zet deze volgorde vast als regressietest.

48. **Middel — `mijnagents-runner/zoom_archief.py:640-669, 674-684`.** A verdwijnt en wordt aan bewezen B gekoppeld. Als hetzelfde A-id tijdelijk terugkomt en opnieuw verdwijnt, vergeet de nieuwe waarneming die koppeling. Na 24 uur volgt opnieuw vals verlies. Behoud een geldige koppeling bij terugkeer en test juist terugkeer *na* de toewijzing.

Gedaan: `509930f` alleen lezend gecontroleerd; niets gewijzigd.  
Nagekeken: beide volgordes met de vastgepinde `_ronde` in het geheugen uitgevoerd; beide eindigen met een verliesmelding. De gemelde 79 tests kon ik in deze leesomgeving niet herhalen.  
Open: beide toestandsovergangen herstellen en testen. De intussen verschenen commit `b337110` wijzigt deze overgangen niet.

BESLISSING: niet klaar