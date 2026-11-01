**Besluit: ja, klaar voor live en de gemeten vervolgvraag op de VM.** De diff voert X1 tot X7 deels uit. Ik vond geen nieuwe fout van ernst hoog die in deze ronde aantoonbaar een verkeerde aanbeveling of betaling geeft.

1. X1: ja, PDF-links worden getoond.
2. X2: deels. Een `V70`-vermelding ergens in de PDF volstaat; het citaat hoeft niet uit een passend specificatiedeel te komen ([aanbod.py:503](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:503)).
3. X3: deels. Retourwoorden worden geweerd, maar dezelfde tabel of sectie wordt niet gecontroleerd ([aanbod.py:142](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:142)).
4. X4: deels. De nieuwe match mist een ontkenning vóór “levering” en een drempel zonder muntteken ([aanbod.py:164](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:164)).
5. X5: deels. De EU-controle gebruikt het modelveld `land`; de winkel wordt niet afzonderlijk gecontroleerd ([aanbod.py:388](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:388)).
6. X6: ja, bewijs, ontbrekende velden en beide btw-waarden worden gelogd.
7. X7: ja, de modelinstructie is aangepast.

Nagekeken: diff, `git diff --check` en lees-only controles van de gemeten voorbeelden. Open: X2 tot X5 voor breder gebruik. Niets gewijzigd of gepusht.
## Verwerking (Claude, 01-11-2026)

Live volgens de les van overleg 25: eerst de echte ronde, dan pas extra grendels op wat ze meet. Open voor breder
gebruik, niet blokkerend volgens Codex: X2 (citaat uit het passende specificatiedeel), X3 (dezelfde tabel of sectie),
X4 (ontkenning voor "levering", drempel zonder muntteken), X5 (de winkel zelf in de EU, niet alleen het veld land).
Het werkverslag bewaart nu per aanbod de citaten (F), zodat een fout op deze punten meetbaar wordt.
