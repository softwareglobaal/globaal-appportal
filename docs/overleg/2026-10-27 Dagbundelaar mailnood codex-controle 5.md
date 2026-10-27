**Niet klaar.** De twee fouten uit toets 4 zijn voor de gewone ochtend- en nachtronde opgelost. Er blijven drie punten van ernst hoog of middel.

### Voor Claude en Shaniel

3. **Hoog, al op main:** een geslaagde handmatige `--dag` controleert één gekozen datum ([dagbundelaar.py:266](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:266)), maar sluit daarna ook open noden van andere dagen ([bord.py:445](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/koppelingen/bord.py:445)). Bewaar noden buiten de gecontroleerde datum.

4. **Middel, al op main:** zo’n handmatige ronde draagt dezelfde taaknaam als de gewone ochtend ([dagbundelaar.py:231](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:231)). Na de keten kan zij daardoor het ochtendbericht vrijgeven terwijl zij een andere dag behandelde ([ochtend.py:198](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/koppelingen/ochtend.py:198)). Laat de vrijgave ook de behandelde datum controleren.

5. **Middel, nieuw:** als `/api/nood` onleesbaar is maar de statusmelding werkt, bewaart `noden_onbekend` terecht de oude noden, maar ook **nieuwe** noden worden niet op het bord gezet ([dagbundelaar.py:297](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:297), [bord.py:445](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/koppelingen/bord.py:445)). Voeg nieuwe noden toe zonder oude te sluiten. De status kan intussen `klaar` tonen bij open noden; De Normwacht en de vrijgave behandelen `klaar` en `waakt` gelijk, maar het ochtendbericht leest de ontbrekende nood niet terug ([regisseur.py:1429](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/regisseur.py:1429)).

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: ochtend en nacht, succes en fout, leesbare en onleesbare noodlijst, handmatige `--dag`, volledige PR-diff; tests niet opnieuw gedraaid.  
Open: punten 3–5.

**BESLISSING: niet klaar.**