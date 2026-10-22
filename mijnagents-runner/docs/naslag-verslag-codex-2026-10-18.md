# Verslag Codex: naslag Buildwise

Datum: 18 oktober 2026.

## Gemaakt

- `mijnagents-runner/naslag/bouw_register.py` bouwt herhaalbaar een register uit de vier lokale pdf-mappen en de fase/werfpuntkoppeling in de inventaris. `bronnenregister.json` bevat nu 189 records: 146 TV-map, 17 dimensionering, 22 meetstaten en 4 keuring.
- `mijnagents-runner/naslag/naslag.py` biedt zoeken, paginagemarkeerde tekstcache, fragmenten, een begrensd promptblok en de CLI-commando's `zoek`, `tekst` en `index`.
- `werfverslag_proef.py` koppelt naslag aan voorbereiding en proef en voegt het optionele puntveld `naslag` toe. Het sjabloon schrijft en leest dit veld in Markdown en toont het in Word.
- Handleiding v1.0, werkwijze en vijf nieuwe tests zijn toegevoegd.

## Aannames

- Deze checkout bevat de server-pdf's niet. Het meegeleverde register is daarom gebouwd uit de 189 expliciet genoemde pdf-namen in `docs/kennisbank-inventaris.md`. Op de server moet `python naslag/bouw_register.py` opnieuw worden uitgevoerd voor een register van de werkelijk aanwezige bestanden.
- De bezoekpagina heeft geen apart veld `naslag`. Een afzonderlijke regel `Naslag: nee` in Keuzes > Opmerking werkt daarom als keuze per bezoek. Een later afzonderlijk veld `naslag = nee` wordt ook gelezen.
- Het jaartal van een TV volgt de oorspronkelijke uitgave in de inventaris, indien bekend. Waar geen betrouwbaar jaar staat, blijft het `null`.

## Nagekeken

- `python3 -m py_compile` van alle gewijzigde Python-modules: geslaagd.
- Pytest: 55 geslaagd, 1 overgeslagen, voor de nieuwe naslagtests en bestaande werfverslagverwerkings- en werfapp-tests.
- `tests/test_werfverslag_nummer.py`: 17 controles geslaagd als zelfstandig script.
- CLI `zoek dakisolatie`: TV 251 als eerste resultaat.
- `git diff --check`: geen witruimtefouten.

## Open

- De pdf's waren hier niet beschikbaar, dus de volledige serverindex en de leesbaarheid van alle pdf's zijn nog niet gecontroleerd. Voer op de VM `python naslag/bouw_register.py` en `python naslag/naslag.py index` uit en bekijk de gemelde pdf-fouten.
- De bezoekpagina kan later een eigen keuzelijst voor naslag krijgen. Dat valt buiten de gevraagde map `mijnagents-runner/`.
- Deze werkmap is niet gecommit, gepusht of uitgerold. De `.git`-map is hier alleen leesbaar; productie blijft ongewijzigd.
