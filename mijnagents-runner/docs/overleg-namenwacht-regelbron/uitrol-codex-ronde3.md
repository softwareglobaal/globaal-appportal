**Klaar met kanttekening.** De afweging is aanvaardbaar voor deze eenmalige run.

1. Bij één inhoudelijke bewerking tussen lezen en POST bewaart de bordroute de vervangen tekst en stopt de [nacontrole](commando.sh:1). Zonder andere schrijver geeft een gewone run geen vals alarm. De controle is niet sluitend: [normalisatie](mijnagents-runner/werkwijze_naar_bord.py:50) kan witruimtebewerkingen missen; bij meerdere snelle bewerkingen hoeft de laatste versierij niet bij onze POST te horen.
2. Het SQLite-pad wijst vanuit `~/appportal` naar de gedeelde hostmap. Relatieve `file:`-paden en lezen in WAL-modus worden ondersteund; de bestaande hostcron bevestigt dit gebruik. [SQLite URI](https://www.sqlite.org/uri.html), [SQLite WAL](https://www.sqlite.org/wal.html).
3. Bij een STOP moet Mehdi de bordtekst en versiegeschiedenis nakijken voordat hij opnieuw start.

Gedaan: alleen gelezen.  
Nagekeken: commando, bordroute en proefopzet; geen live VM-meting.  
Open: de eenmalige uitvoering door Mehdi.

AKKOORD