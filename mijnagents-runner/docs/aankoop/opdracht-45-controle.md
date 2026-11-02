# Codex-controle 45: herstel na overleg 44 (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff bd6dec4c..06951573` op de tak `aankoop-proefuitslag`. Achtergrond: `docs/aankoop/opdracht-44-herstel-proeven.md`
en het besluit in `docs/aankoop/rapport-44-herstel-proeven.md` (A tot F, X4, X6, X7, K1 tot K7 aangenomen).

- A `aankoop/aanbod.py` GELEVERD_GRATIS en INBEGREPEN in `gratis_verzending`; ook geen bedrag vlak erna, tenzij een drempel.
- B `boven_drempel`: drempel met munt, excl. btw tegen prijs/1,21; in `totaal` voor elke gratis verzending.
- C `belgische_winkel`: land BE of .be; anders moet ook een eigen-paginacitaat voor_belgie zijn.
- D `aankoop/leesserver.py` `_gelezen_tot_nu`: verzendpagina (pad) van een al gelezen host kost geen leesbeurt, max 4.
- E `aankoop/onderzoek.py` MAX_BEURTEN 40, bestand "beurten" in de werkmap, leestool meldt afronden vanaf 8 ervoor;
  `prijsonderzoeker.py` zet op een grens een noodverslag (`verslag.onvolledig`), de vraag blijft staan.
- F `eisen_uit_vraag` "past op <code>" na "voor/op/bij/met mijn|onze|de ... <merk> <code>"; bindend; ja alleen met een
  citaat op de aanbodpagina dat de code en een paswoord bevat en geen accessoire ervoor.
- Tests per punt met de echte citaten.

Een hoge fout alleen met een concreet scenario dat in een echte ronde een verkeerde aanbeveling of een betaling geeft.

## Vragen

1. Voert de diff de aangenomen punten uit? Per punt ja, of wat ontbreekt met `bestand:regel`.
2. Een fout van ernst hoog?
3. Klaar om live te zetten en de hele reeks opnieuw te draaien: ja of nee.
