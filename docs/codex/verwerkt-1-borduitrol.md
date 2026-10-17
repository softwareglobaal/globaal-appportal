# Verwerking ronde 1: bewaakte borduitrol mijnagents

Door Claude, 16-10-2026. Codex: niet klaar, 2 hoog (BU-1, BU-2), 6 middel (BU-3 tot BU-8), 1 laag (BU-9). Elk punt
nagemeten; herstel in `mijnagents/deploy.sh`, nieuw `mijnagents/deploy_ci.py`, tests in `mijnagents/test_bord_deploy.py`
(35) en `mijnagents/test_deploy_ci.py` (6), workflow `.github/workflows/bord-grendels.yml` (vervangt bord-uitrol-grendels).

| Punt | Oordeel | Nameting | Herstel | Test |
|---|---|---|---|---|
| BU-1 hoog | gelijk (mechanisme) | `mijnagents/` heeft geen `.dockerignore`, `COPY . .`; op de VM is nu alleen `__pycache__/` genegeerd, geen `.env` of `.db`: geen actueel lek, wel een gat in "schone werkboom = wat draait" | bouw uit `git archive` van precies de tree van HEAD naar een eigen map; de werkboomcontrole vervalt | `test_bouwt_de_vastgelegde_tree_ook_als_de_werkboom_verandert` (genegeerde `.env` niet in de bouwcontext) |
| BU-2 hoog | gelijk | geen CI-grendel; `gh` is op de VM ingelogd (softwareglobaal); de repo is publiek, Actions draaien | `deploy_ci.py`: geslaagde, voltooide run van `bord-grendels.yml` op main (push) voor exact de HEAD-SHA, nieuwste poging telt, geen terugval, geen ruwe gh-uitvoer; `bord-grendels.yml` draait bij elke push naar main zonder padfilter en test alle bordtests | `test_deploy_ci.py` (6), `test_ci_lopend_...`, `test_ci_onbereikbaar_...` |
| BU-3 middel | gelijk | tree-hash werd vóór de bouw gelezen, de bouw las de werkboom | SHA één keer gelezen, tree daaruit, archief los van de werkboom; image draagt `mijnagents.tree` en `org.opencontainers.image.revision`; label nagekeken vóór de start | idem BU-1, `test_image_zonder_deze_revisie_telt_niet` |
| BU-4 middel | gelijk | nachtelijke kopie bestaat (`scripts/db-backup.sh` 03:15, 16 MB gz), niet per uitrol; db 242 MB, WAL | kopie vóór de bouw (`sqlite3 -readonly .backup`, `integrity_check`, gzip) in `~/backups/voor-uitrol/`, onder de bestaande rotatie van 14 dagen; ruimtecontrole; mislukt = geen bouw, geen `.mislukt`; terugzetten met de hand (kop van het script) | `test_kopie_van_de_databank_voor_de_bouw` (ook volgorde), `test_kopie_mislukt_bouwt_niet`, `test_te_weinig_ruimte_...` |
| BU-5 middel | gelijk | `.herstel` registreerde altijd een mislukte poging | hervatten kijkt wat draait: label = revisie en gezond → alsnog `.built`; vorige image gezond → niets, geen `.mislukt`; anders terugzetten | `test_onderbroken_voor_de_bouw_telt_niet_als_mislukt`, `test_gezonde_uitrol_zonder_built_wordt_voltooid` |
| BU-6 middel | gelijk (markering), deels (bewaking) | stille verwijdering bij `H_REV = .built` | geen blinde verwijdering meer (zie BU-5); wordt teruggezet terwijl `.built` de revisie noemt, dan wordt `.built` de boom van de teruggezette image; zonder nieuwe revisie één probe per ronde met een logregel bij elke verandering. Doorlopende bewaking met alarm hoort bij een bordagent, niet bij de uitrol | `test_achtergebleven_markering_...`, `test_bewaakt_een_ongewijzigde_revisie` |
| BU-7 middel | gelijk | met dash nagemeten: `printf '{"ok":true'; exit 18` gevolgd door `grep` geeft 0 | `curl`-uitvoer apart, dan volledig JSON met `ok is True` (python3) | `test_half_antwoord_of_ok_als_tekst_telt_niet` |
| BU-8 middel | gelijk | gezondheid en ID waren niet gekoppeld | eerst het ID, dan gezondheid voor dat ID, dan de tag, dan nacontrole van tag én draaiende image; handmatige acties: `flock` op hetzelfde slot (kop van het script) | `test_terugrolimage_is_de_draaiende_image`, `test_wissel_van_container_bij_het_taggen_bouwt_niet` |
| BU-9 laag | gelijk | logregel noemde alleen de wachttijd | absoluut tijdstip van de volgende poging in het log; een melding op het bord bij `.mislukt` wordt aan Mehdi voorgesteld | `test_ongezond_nieuw_bord_...` (tijdstip) |

Eigen toevoeging: drie gezonde probes na elkaar (`BORD_STABIEL`), test `test_wankel_bord_telt_niet_als_gezond`; `mktemp`
met expliciet sjabloon onder `TMPDIR` (macOS negeerde `TMPDIR` zonder sjabloon, de opruimtest zag daar niets).

Grendelproef: elke test faalt op het productiescript of op de ronde-1-versie, en elke BU-mutatie wordt gevangen:
zonder CI-grendel, oude probe, zonder kopie, geen voltooiing, altijd mislukt bij hervatten, `.built` blijft staan, geen
bewaking, geen nacontrole na de tag, geen labelcontrole, bouw uit de werkboom, bronmap blijft liggen, één probe.
Alle tien testbestanden in `mijnagents/` groen lokaal (dash; Python-vervangers voor flock en timeout op de Mac).
