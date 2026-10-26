Niet klaar. Punten 3 en 4 zijn opgelost. Punt 5 werkt met het nieuwe bord, maar niet met een oude bordversie. De dubbele redenen bij twee falende eigen mappen zijn verholpen. In de drie reviewpunten blijft bovendien een gat voor ingehaalde dagen buiten het nachtvenster.

### Voor Claude en Shaniel

1. **Middel — oude bordversie.** Bij een onleesbare open lijst stuurt de ronde nieuwe noden met `nood_sluiten=false` ([dagbundelaar.py:315](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:315), [bord.py:448](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/koppelingen/bord.py:448)). `origin/main:mijnagents/app.py:2202-2204` negeert die vlag en sluit alle bestaande noden die niet zijn meegestuurd. Dat kan tijdens een mislukte borduitrol: de runnercode is dan al nieuw terwijl de oude container blijft draaien ([deploy.sh:21](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents/deploy.sh:21)). Grendel de runner op een bevestigd nieuw bord en toets deze gemengde versie.

2. **Middel — ingehaalde dag.** Een nacht kan een dag ouder dan veertien dagen eenmalig inhalen ([dagbundelaar.py:276](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:276)). De volgende ochtend controleert Dropbox alleen het nachtvenster en sluit de nood voor die oudere dag zonder ontvangstbewijs ([dagbundelaar.py:878](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:878)). Een locatie- of plafondnood blijft die ochtend staan, maar kan de volgende nacht eveneens sluiten zonder hercontrole ([dagbundelaar.py:299](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:299)). Bewaar zulke open dagen per datum tot ontvangst of hercontrole.

Met het nieuwe bord kloppen de gewone ochtend-, nacht- en handmatige paden. Andere agents behouden de standaardafsluiting. N7, het ochtendbericht en de bordexport lezen de bordstand; zij nemen een onterechte sluiting dus over.

Gedaan: volledige PR-diff alleen gelezen; niets gewijzigd.  
Nagekeken: codepaden en bestaande tests; tests niet opnieuw gedraaid.  
Open: twee middelpunten hierboven.

**BESLISSING: niet klaar.**