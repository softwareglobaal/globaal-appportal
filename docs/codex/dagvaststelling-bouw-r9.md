**Niet klaar. Fase 1 mag niet live.** K2 is hersteld, maar K1 blijft open: een dagvaststelling kan na zes dagen een exact Zoomgetal tonen terwijl er nog gesprekken bijkomen.

**Status:** K1 open, K2 gesloten, G2 gesloten, G3 open, F4 gesloten, F9 open en D6 open. G3, F9 en D6 blijven open door K1. De gerichte proef voor het namiddagbezoek zonder afspraak slaagt.

### Voor Claude en Shaniel

1. **L1, hoog:** De grens van zes dagen geldt in [zoom_wacht.py](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/zoom_wacht.py:1436) alleen voor een *opgepakt* item. Een item dat nog `klaar` staat, kan op dag zeven opnieuw worden aangeboden en door [het bord](/Users/mehdichegini/dev/_dagvaststeller/mijnagents/app.py:605) worden bijgewerkt. Een alleen lezende geheugenproef bevestigt beide uitkomsten. Pas de grens ook op `klaar` toe, of behoud een ondergrens zolang wijziging mogelijk is.

2. **L2, hoog:** Ook een bevroren dagregel bewijst geen exact totaal. [De Fathomwacht](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/fathom_wacht.py:373) leest veertien dagen terug en schrijft gespreksrijen; [De Dagbundelaar](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:618) telt die opnieuw, maar noemt Zoom na dag zes volledig. Een geheugenproef gaf met dezelfde dagregel eerst **0 exact** en na een late Fathomrij **1 exact**. Vereis bewijs dat alle meegetelde bronnen voor die dag uitgewerkt zijn; toon anders een ondergrens.

**Laag, L3:** [De nieuwe K1-test](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/tests/test_dagbundelaar_vaststelling.py:428) toetst alleen de datumgrens met een vaste dagregel. Voeg de gevallen uit L1 en L2 toe als grendel.

### Live installatie na herstel

1. Rol de herstelde code uit, zet de nachtregel met `gesprekken_cron_zetten.py --zet` en lees de actieve planning terug.
2. Zet werkwijze versie 3 op het bord en lees die terug.
3. Installeer de [nieuwe Mac-sync](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/planning/mac/data_uit_mehdi_sync.sh:31) in `~/bin` en lees de kopie terug. De huidige [geïnstalleerde kopie](/Users/mehdichegini/bin/data_uit_mehdi_sync.sh:26) mist de dagboekoverdracht.
4. Controleer een eerste nachtronde aan `nacht.json`, dagbestand, borditem en Dropbox-ontvangstbewijs.

Gedaan: alleen gelezen, niets gewijzigd.  
Nagekeken: diff, broncode en gerichte geheugenproeven.  
Open: K1 herstellen en daarna de live installatie controleren.