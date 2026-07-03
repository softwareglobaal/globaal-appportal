# Data governance — softwareglobaal / H-groep

> Waarom: alles in de centrale database is gelinkt — één fout plant zich overal
> voort. Dit document bundelt de regels die gelden, de vangnetten die bestaan,
> en wat er nog gepland staat. Technische details: TECHNICAL-REFERENCE §14.

## De regels die gelden (en al afgedwongen worden)

1. **Eén bron per begrip.** Personen, firma's, afdelingen, leveranciers en
   definities leven één keer, in `kern`; alle apps verwijzen met echte FK's.
   Geen vrije tekst waar een verwijzing kan (DEFINITIEBOEK-discipline).
2. **Terminologie is data.** Termen + definities staan in `kern.definitie`
   (beheer: alleen `WOORDENBOEK_EDITORS` — mehdi, akadmin); de dashboards lezen
   ze live. DEFINITIEBOEK.md is de leesbare uitwerking.
3. **Schema wijzigt alleen via migraties.** Genummerd in `db/migrations/`,
   toegepast met `scripts/db-migrate.sh`, getest vóór de push. Nooit ad-hoc DDL.
4. **Smalle toegang.** Elke app heeft een eigen db-rol die alleen het eigen
   schema schrijft en kern leest; schrijven in de UI is per Authentik-groep.
   De geheim-tabel (PIN/PUK) wordt door niets anders gelezen, ook niet door AI.
5. **Historie telt.** Finalisatie en run-logs zijn append-only (ook op
   databaseniveau); terugdraaien is een nieuwe registratie, nooit wissen.
6. **Kwaliteit is zichtbaar.** De Second Brain-signalen melden open eindjes
   (geen verantwoordelijke, niet-gematchte firma's, …); finalisatie
   (blauw/rood) toont wat gecontroleerd is, met wie en wanneer.
7. **Herstelbaar.** Nachtelijke dumps (14 dagen lokaal) + GPG-versleuteld
   off-site naar S3 (30 dagen, upload-only sleutel). Setup/restore:
   `docs/offsite-backup-setup.md`.

## De audit-trail (migratie 023 — sinds 2026-07-03)

Elke INSERT/UPDATE/DELETE op de menselijk beheerde tabellen (kern,
communicatie, kosten, vermogen, draaiboek, meeting-actiepunten) wordt door
database-triggers vastgelegd in **`kern.audit`**: wanneer, welke db-rol (= welke
app), welke rij, en de volledige oude én nieuwe waarden. De app-rollen kunnen
de audit zelf niet schrijven of wijzigen; alleen `portal` mag lezen.

**"Wie heeft dit veranderd en wat stond er eerst?"** is nu één query:
```sql
SELECT op, rol, app_gebruiker, actie, oud, nieuw
  FROM kern.audit
 WHERE tabel = 'communicatie.nummer' AND rij_id = '<uuid>'
 ORDER BY op DESC;
```
Een foute wijziging herstel je gericht met de `oud`-waarden — geen volledige
restore nodig.

Bewuste keuzes: `communicatie.geheim` wordt alleen als metadata geauditeerd
(nooit PIN/PUK-waarden); machine-geschreven tabellen (fathom-meetings,
briefings, run-logs) niet — die hebben eigen herkomst. **Vervolgstap:** apps
laten per transactie `SET LOCAL app.gebruiker = '<username>'` zetten zodat ook
de mens (niet alleen de app-rol) in de audit staat; tot dan geven de
`bijgewerkt_door`-kolommen in `oud`/`nieuw` dat houvast.

## Eigenaarschap (in te vullen met de collega's)

**`kern.data_domein`** — acht domeinen, elk met een eigenaar (data steward):
personen, firma's, terminologie, telefonie, e-mailadressen, kosten, vermogen,
draaiboeken. De eigenaar is aanspreekbaar voor de kwaliteit van zijn domein en
degene die finaliseert. **Actie (Shaniel + Mehdi): eigenaars toewijzen** —
daarna meldt de Second Brain domeinen zonder eigenaar als signaal.

## Gepland (bewust nog niet gebouwd)

- **Kwaliteitsmetriek** per domein (% gefinaliseerd, veld-dekking, wezen,
  duplicaten, staleness) → in de dagbriefing. (TODO)
- **Restore-test**: eenmalig oefenen met een S3-backup, daarna elk kwartaal.
  (agenda Shaniel)
- **Toegangsreview**: periodiek de Authentik-groepen nalopen. (agenda)
- **`app.gebruiker` in de audit** (zie hierboven), per app uit te rollen.
