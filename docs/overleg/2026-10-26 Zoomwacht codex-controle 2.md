**Niet klaar.** Privékanalen kunnen nog als werk zichtbaar blijven, en twee nieuwe tellingen kunnen Mehdi verkeerd of niet bereiken.

**Voor Claude en Shaniel**

1. **Hoog — nieuw privékanaal:** [zoom_wacht.py:563](mijnagents-runner/zoom_wacht.py:563) classificeert een naam als `H-Architects privé` als werk. Herken `prive` en `privé` ook naast een afdelingsnaam.
2. **Hoog — oude kanaalrijen:** [zoom_wacht.py:1531](mijnagents-runner/zoom_wacht.py:1531) herstelt alleen rijen met een onbekende afdeling. Eerder publieke rijen met een herkenbare afdeling én privénaam blijven buiten het leesvenster publiek. Herbeoordeel die rijen ook.
3. **Middel — dagregel:** Het nieuwe veld op [zoom_wacht.py:1361](mijnagents-runner/zoom_wacht.py:1361) ontbreekt in `KERN` op [regel 93](mijnagents-runner/zoom_wacht.py:93). Een al opgepakte dagregel krijgt daardoor geen revisie met de uitsplitsing.
4. **Middel — chatouderdom:** [zoom_wacht.py:536](mijnagents-runner/zoom_wacht.py:536) meet vanaf morgen om middernacht. Chats rond de grens van twee of zeven dagen vallen daardoor in de verkeerde groep; gebruik de rondetijd.

Gedaan: uitsluitend `git diff` gelezen.  
Nagekeken: classificatie, herstel, revisie en ouderdom.  
Open: vier correcties.