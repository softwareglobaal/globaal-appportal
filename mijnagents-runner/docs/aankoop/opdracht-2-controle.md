# Controle door Codex: De Prijsonderzoeker (commit e2bd408 op tak aankoopagents)

Lees alleen; wijzig niets. Nummer je punten X1, X2, ... met een ernst (hoog, middel, laag) en een bestand:regel.

## Wat er gebouwd is

Het ontwerp uit `mijnagents-runner/docs/aankoop/rapport-1-ontwerp.md` (16 aangenomen punten). Bekijk de diff met
`git diff origin/main...HEAD` in deze map. Nieuwe bestanden: `mijnagents-runner/aankoop/` (aanbod, koersen,
onderzoek, privacy, verslag), `mijnagents-runner/prijsonderzoeker.py`, `mijnagents-runner/werkwijze/prijsonderzoeker.md`,
`mijnagents-runner/tests/test_aankoop_prijs.py`, `.github/workflows/aankoop-grendels.yml`. Gewijzigd:
`mijnagents-runner/regisseur.py` (toelatingslijst en `--vraag`) en `mijnagents-runner/tests/test_regisseur.py`.

## Wat je nagaat

1. Correctheid: kan een aanbod zonder gelezen pagina, link, prijs of datum toch in het verslag komen? Kan een
   veiling zonder opgeld of veilingkosten, of een aanbod buiten de EU zonder invoer, toch als beste of reserve
   komen? Kan een niet compatibel aanbod aanbevolen worden?
2. De lus met de servertools in `aankoop/onderzoek.py`: `pause_turn`, het plafond op tokens en tijd, de
   terugval op een ander model, de vorm van de resultaatblokken van `web_fetch_20250910` (url en tekst van de
   pagina). Klopt de manier waarop een gepauzeerde beurt hervat wordt?
3. Privacy (`aankoop/privacy.py`): houdt hij persoonsgegevens tegen zonder gewone productvragen te blokkeren
   (modelnummers, spanning, prijzen, maten)? Gaat er ergens een vraag met persoonsgegevens in het logboek of op het bord?
4. De Regisseur: botst `vraag` met de bestaande regels (kwartierregel, droog, taken, `onbekende_vlag`)? Past de ronde
   binnen de 540 seconden?
5. De Agentnorm (`mijnagents-runner/AGENTNORM.md`): haalt deze agent N1 tot N14 na de generator en de eerste ronde?
   Zakt er iets (bijvoorbeeld een aantal in een noodtekst, N10)?
6. Het bord en De Bode: het verslag gaat als soort `prijsverslag` voor mehdi. Toont het bord dat, en stuurt De Bode
   het niet vanzelf door (overleg X2)? Zie `mijnagents/app.py` en `mijnagents-runner/bode.py`.
7. Ontbrekende tests voor wat hierboven kan breken.

Geef bovenaan een beslissing: klaar, klaar met kanttekeningen, of niet klaar. Alleen punten met bewijs.
