**Niet klaar: `SEIN_AAN` moet uit blijven.** Punt 39 is in de code en de vier testgevallen hersteld, maar nieuwe geheugenproeven leveren nog onterechte groene signalen op.

### Voor Mehdi

- Als de bewaarde archiefstand ontbreekt, kan een eerder geziene opname verdwijnen zonder dat het systeem het verlies meldt. De volgende ronde zegt dan toch dat alles gedekt en veilig is.
- Een bestaand wisadvies blijft open wanneer de volledige dekking wegvalt door een recente opname. De Zoomwacht geeft daarbij geen waarschuwing.
- Staat de wisregel al aan en ontbreekt later een oude kopie, dan noemt De Zoomwacht de regel “goed” zonder waarschuwing als er geen open voorstel is.
- Een verdwenen `opname.json` wordt niet opnieuw gecontroleerd. De mediabestanden blijven aanwezig, maar het archief meldt toch volledige dekking.
- Een dekkingbestand met een datum in de toekomst wordt als geldig gelezen.

### Voor Claude en Shaniel

40. **Hoog — `zoom_archief.py:120`.** Proef: oude opname in verwerking, daarna `staat.json` ontbreekt en Zoom toont haar niet meer → `dekking=true`, `wisregel_veilig=true`. **Fix:** ontbrekende staat na een eerdere ronde als fout behandelen; eerste ingebruikname expliciet initialiseren.

41. **Middel — `zoom_account.py:695`.** Open ZA-01, `dekking=nee`, `archief_veilig=ja` → geen waarschuwing. **Fix:** bestaande voorstellen ook tegen de actuele volledige dekking toetsen.

42. **Hoog — `zoom_account.py:723`.** Wisregel aan, beide archiefsignalen `nee`, geen open voorstel → ZA-01 “goed”, nul waarschuwingen. **Fix:** bij een actieve wisregel onveilige archiefstand zelfstandig melden en ZA-01 niet als goed tonen.

43. **Middel — `zoom_archief.py:665`.** `opname.json` ontbreekt na eerdere succesvolle opslag → geen hercontrole, toch beide signalen groen. **Fix:** beschrijving opnieuw bewijzen of de blokkade heropenen.

44. **Laag — `zoom_account.py:644`.** Toekomstige tijdstempel met passend bordrecord → tweemaal “ja”. **Fix:** toekomstige tijdstempels weigeren.

Gedaan: diff gelezen en vijf alleen-lezen geheugenproeven uitgevoerd.  
Nagekeken: herstel van punt 39 en de vier bijbehorende testgevallen; de volledige testsuite niet opnieuw gedraaid.  
Open: bevindingen herstellen en met tegenproeven vastzetten.

**BESLISSING B (sein aan): niet klaar.**