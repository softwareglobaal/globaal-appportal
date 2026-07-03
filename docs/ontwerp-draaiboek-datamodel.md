# Ontwerp — datamodel draaiboek-platform (concept v1)

> **Status: CONCEPT** — ter review door Shaniel/Mehdi en te verfijnen met de
> deep-research (Toolmaster/Monday/referentieklasse/veiligheidscoördinatie).
> Terminologie: DEFINITIEBOEK + `kern.definitie` (migratie 021): draaiboek,
> projectmanagement, fase, stap, run. Pas na review wordt dit een migratie.

## Het model in één zin

Een **draaiboek** is een sjabloon (fases → stappen); een **run** is dat sjabloon
toegepast op één dossier — de stappen worden bij de start **gekopieerd** naar de
run en krijgen daar status, wie en wanneer.

```
SJABLOON (beheer)                      UITVOERING (dagelijks werk)
draaiboek ─┬─ fase ─┬─ stap            run ─┬─ run_stap  (kopie van stap + status)
           │        └─ stap                 ├─ run_stap
           └─ fase ─── stap                 └─ run_stap_log (append-only historie)
                │                            │
                └── kern: —                  └── kern: firma, personen
```

## Ontwerpbeslissingen (met waarom)

1. **Runs kopiëren de stappen (snapshot), geen live verwijzing.** Dé klassieke
   valkuil van playbook-systemen: iemand past het sjabloon aan terwijl er tien
   runs lopen, en ineens klopt de voortgang van lopende dossiers niet meer of
   liegt de historie. Door stappen bij run-start te kopiëren (mét een
   `stap_id`-verwijzing voor afkomst) blijven lopende en afgeronde runs altijd
   waar; sjabloon-verbeteringen gelden vanaf de vólgende run.
2. **Historie is append-only**, net als finalisatie: elke statuswijziging van een
   run-stap is een nieuwe logrij (wie, wanneer, wat). Afvinken terugdraaien =
   nieuwe rij, nooit wissen ("rollen wijzigen; historie telt").
3. **Adaptief zonder AI-afhankelijkheid**: een stap kan een `conditie` dragen
   (bv. `torenkraan`, `groot_project`). Bij het starten van een run kies je welke
   kenmerken gelden; stappen waarvan de conditie niet geldt worden niet
   meegekopieerd. Dat is het "kleine gezinswoning ≠ torenkraan-stap"-gedrag uit
   de meeting — de AI-laag (document lezen → kenmerken voorstellen) komt hier
   later bovenop, het model hoeft er niet voor te veranderen.
4. **Volgorde + afhankelijkheid gescheiden.** `volgorde` bepaalt de weergave;
   `hangt_af_van` (nullable, zelfde tabel) bepaalt wat er pas kán na iets anders.
   De meeste stappen hebben genoeg aan volgorde; afhankelijkheid is voor de echte
   blokkades ("verslag 3 pas na verslag 2" — het sequentiële geheugen).
5. **Eén afhankelijkheid per stap in v1** (nullable kolom, geen koppeltabel).
   Meerdere afhankelijkheden kan later zonder breuk (koppeltabel erbij); starten
   met het simpelste dat het EPB-/verslagen-scenario dekt.
6. **Geen project-entiteit verzinnen.** Projecten/klanten bestaan nog niet in
   `kern` (staat op de TODO). De run krijgt een eigen `dossier`-naam + firma-link;
   zodra de project-entiteit er is, komt er een nullable FK bij — geen breuk.
7. **Resultaten als verwijzing, niet als opslag.** Een stap kan een op te leveren
   resultaat benoemen (bv. "werfverslag"); de run-stap krijgt een tekstverwijzing
   naar wáár dat staat. Documentbeheer/-generatie is een apart spoor (meeting
   2026-07-03); het model moet er alleen naar kunnen wijzen.
8. **Zelfde spoke-patroon als altijd**: schema `draaiboek` in de appportal-DB,
   eigen DB-rol (leest kern, schrijft eigen schema), FK's naar `kern.firma` en
   `kern.persoon`, zichtbaar in de Second Brain, terminologie uit `kern.definitie`.

## Tabellen (schema `draaiboek`)

### Sjabloon-kant (beheer — groep `draaiboek-editors`)

**`draaiboek`** — het sjabloon/playbook
| kolom | type | betekenis |
|---|---|---|
| id | uuid PK | |
| naam | text | bv. "Veiligheidscoördinatie — verwezenlijking" |
| omschrijving | text | waarvoor dit proces dient |
| proces_eigenaar_persoon_id | uuid → kern.persoon | wie het sjabloon inhoudelijk beheert |
| actief | boolean | zacht uitzetten |
| bijgewerkt_op/door | timestamptz/text | |

**`fase`** — hoofdstuk van een draaiboek
| kolom | type | betekenis |
|---|---|---|
| id | uuid PK; draaiboek_id FK | |
| naam | text | bv. "Ontwerpfase" |
| volgorde | integer | |

**`stap`** — de kleinste eenheid
| kolom | type | betekenis |
|---|---|---|
| id | uuid PK; fase_id FK | |
| naam | text | bv. "Werfverslag opstellen" |
| omschrijving | text | hoe/waarmee (de instructie) |
| volgorde | integer | binnen de fase |
| hangt_af_van_stap_id | uuid → stap, nullable | harde blokkade ("pas na X") |
| conditie | text, default '' | leeg = altijd; anders kenmerk-label (bv. `torenkraan`) |
| resultaat | text, default '' | op te leveren (bv. "werfverslag") — leeg = geen |
| rol_hint | text, default '' | wie dit typisch doet (vrije hint; toewijzing gebeurt per run) |
| termijn_dagen | integer, nullable | richtdeadline: dagen na start van de run |

### Run-kant (uitvoering — alle gebruikers van de app)

**`run`** — een draaiboek toegepast op één dossier
| kolom | type | betekenis |
|---|---|---|
| id | uuid PK; draaiboek_id FK | afkomst (sjabloon) |
| dossier | text | naam van het project/dossier (later + project-FK) |
| firma_id | uuid → kern.firma | voor wie |
| verantwoordelijke_persoon_id | uuid → kern.persoon | eigenaar van de run |
| kenmerken | text[] of jsonb | gekozen condities bij de start (bv. `{groot_project}`) |
| status | 'lopend' / 'afgerond' / 'gestopt' | |
| gestart_op / afgerond_op | timestamptz | |
| aangemaakt_door | text | |

**`run_stap`** — kopie van een stap, mét status (het sequentiële geheugen)
| kolom | type | betekenis |
|---|---|---|
| id | uuid PK; run_id FK | |
| stap_id | uuid → stap, nullable | afkomst (lineage; sjabloon kan later wijzigen) |
| fase_naam / naam / omschrijving / resultaat | text | **snapshot** bij run-start |
| volgorde | integer | globale volgorde in de run |
| hangt_af_van_run_stap_id | uuid → run_stap, nullable | |
| toegewezen_aan_persoon_id | uuid → kern.persoon, nullable | |
| deadline | date, nullable | berekend uit termijn_dagen of handmatig |
| status | 'open' / 'klaar' / 'overgeslagen' | huidige stand (afgeleid v.d. log) |
| resultaat_verwijzing | text | waar het opgeleverde staat (URL/pad/omschrijving) |
| notitie | text | |

**`run_stap_log`** — append-only historie (patroon van organisatie.finalisatie)
| kolom | type | betekenis |
|---|---|---|
| id | uuid PK; run_stap_id FK | |
| status | text | nieuwe status |
| door | text | Authentik-username |
| op | timestamptz default now() | |
| notitie | text | bv. reden van overslaan |

## Wat dit model meteen mogelijk maakt

- **"Waar staan we?"** per run: eerstvolgende open stap, per fase de voortgang —
  het verslagen-probleem ("2 is klaar dus nu 3") is een simpele query.
- **Second Brain**: runs als knopen aan firma + verantwoordelijke; signalen als
  "run al X dagen geen activiteit", "stap over deadline", "run zonder
  verantwoordelijke" — zelfde regels-patroon als bestaande signalen.
- **Automatisering later**: de log is de event-bron ("stap X werd klaar") waar
  triggers op kunnen reageren — het model hoeft daarvoor niet te wijzigen.
- **Fathom-koppeling later**: meeting-actiepunten kunnen naar een run_stap
  verwijzen (kolom erbij op organisatie.meeting_actiepunt, geen breuk).

## Open vragen (voor de deep-research / Mehdi)

1. Bevestigt de referentieklasse het snapshot-model, of werken zij met
   sjabloon-versies? (Beslissing 1 — belangrijkste om te toetsen.)
2. Welke stap-statussen zijn in de praktijk nodig? (Nu bewust minimaal:
   open/klaar/overgeslagen — geen "bezig".)
3. Hoe doen zij goedkeuringsstappen (stap die een tweede persoon moet aftekenen)?
   Zit niet in v1 — nodig voor veiligheidscoördinatie?
4. De echte veiligheidscoördinatie-flow (spoor 4): hoeveel fases/stappen, welke
   verplichte documenten — bepaalt of `resultaat` als tekst volstaat.
5. Deadline-logica: volstaat `termijn_dagen` vanaf run-start, of moet het
   "X dagen na stap Y" zijn?
