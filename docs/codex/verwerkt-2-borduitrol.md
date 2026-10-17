# Verwerking ronde 2: bewaakte borduitrol mijnagents

Door Claude, 16-10-2026. Codex: niet klaar, 0 hoog en 4 middel (BU-10 tot BU-13), tegen 2 hoog en 6 middel in ronde 1.
BU-1, BU-2, BU-3, BU-5, BU-7 en BU-8 volstaan; BU-4 en BU-6 deels (via BU-10 tot BU-13); BU-9 deels, laag.
Codex bevestigt dat `docker compose up -d --no-build --force-recreate` de met `docker build` gemaakte
`appportal-app-mijnagents:latest` gebruikt, en dat de eerste ronde na de pull (image zonder label) loopt zoals bedoeld.

| Punt | Oordeel | Nameting | Herstel | Test |
|---|---|---|---|---|
| BU-10 middel | gelijk | tweede hersteltak (`deploy.sh` ronde 2, r. 204) haalde `.herstel` weg en liet `.built` en `:latest` staan | ook in die tak `herstel` (zet `:latest` terug op het draaiende ID, zonder nieuwe container als dat ID gezond draait); noemt `.built` de niet-draaiende revisie, dan wordt `.built` het label van de draaiende image of `onbekend` | `test_achtergebleven_markering_bij_gezonde_vorige_image_ontmarkeert` |
| BU-11 middel | gelijk | `bewaak` keek alleen naar `/gezondheid`; de test zette zelf een tegenstrijdige toestand | `bewaak` vergelijkt het label van de draaiende image met `.built`; wijkt het af, dan volgt `.built` de werkelijkheid en rolt dezelfde ronde HEAD bewaakt uit; alleen op een geslaagde inspectie (een haperende docker verandert niets) | `test_gezonde_maar_verkeerde_image_wordt_opgemerkt_en_rechtgezet`, `test_haperende_inspectie_zet_built_niet_om`; de bewakingstest heeft nu een consistente toestand |
| BU-12 middel | gelijk | zonder `mijnagents.db` werd gebouwd; `init_db()` maakt dan een lege aan en `/gezondheid` geeft `ok: true` met 0 agents (`app.py:1722`) | geen bouw zonder leesbare databank; de kopie eist minstens één actieve agent; de gezondheidsproef eist `agents` als geheel getal van minstens 1 | `test_zonder_databank_geen_bouw`, `test_bord_zonder_actieve_agents_is_niet_gezond`, `db-leeg` in `test_kopie_mislukt_start_niet_en_blokkeert_niet` |
| BU-13 middel | gelijk | de kopie kwam vóór een bouw van tot 30 min | één kopie, direct vóór het vervangen van de container (na bouw en labelcontrole). Mislukt ze, dan start de nieuwe image niet: `:latest` terug op het draaiende ID, `.herstel` weg, geen `.mislukt`, de volgende ronde probeert opnieuw | `test_kopie_van_de_databank_direct_voor_de_start` (volgorde bouw, kopie, start), `test_kopie_mislukt_start_niet_en_blokkeert_niet`, `test_te_weinig_ruimte_voor_de_kopie_start_niet` |
| BU-9 laag | deels | tijdens de afkoeling blijft de status stil, buiten de eerste foutregel met het absolute tijdstip | voorstel aan Mehdi: een melding op het bord bij `.mislukt`, `.herstel` of `.ongezond` (eigen taak) | — |

Eigen toevoeging: `test_eerste_ronde_na_de_pull_met_een_image_zonder_label` (de echte toestand op de VM: image zonder
label, `.built` uit het oude script). In de testopzet draagt de oude image nu het label `oud`; de afkoelingstests
verbieden bouw, tag en start, niet de twee inspecties van `bewaak`.

Grendelproef ronde 3: de tests falen op de versie van ronde 2 (`dce3f1b`, 9 tests) en op elke gerichte mutatie: `.built` blijft
staan in de tweede tak, `:latest` niet teruggezet, geen labelcontrole in `bewaak`, inspectie die een fout slikt, geen
databankcontrole, 0 agents als gezond, kopie zonder telling, kopie vóór de bouw. De mutatie zonder terugzetten van `:latest` ontsnapte eerst (dezelfde ronde rolde daarna opnieuw uit); de test zet de revisie nu in afkoeling en vangt haar.
