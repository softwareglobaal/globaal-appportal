# Dashboard-template - bindend referentiedocument

> **Status: BINDEND** (besloten in de meeting van 2026-07-08, Mehdi + Siyan:
> "geen knowledge-document maar een template-document, voor iedereen, in een
> keer opgelost - anders is dat broeie broeie"). Voor **iedereen** die een
> dashboard voor de groep bouwt, met Claude of anders.
>
> **Zo gebruik je het:** geef dit bestand aan het begin van elke
> Claude Code-sessie als referentie mee ("volg DASHBOARD-TEMPLATE.md uit de
> stack-repo") en lever je dashboard af volgens dit document. Vrij
> experimenteren mag: een blueprint die hiervan afwijkt wordt niet
> weggegooid maar omgezet naar dit template (voorbeeld: het sales-dashboard
> van Siyan). Hoe eerder je het template volgt, hoe minder omzetwerk.

## 1. Data: alles gelinkt, niets los

1. **Personen, firma's, afdelingen en leveranciers komen uit `kern.*`** - de
   centrale gebruikersdatabase. Nooit vrije tekst: "Joey" of "Shilton" als
   losse string in je data is fout; het is een verwijzing naar de persoon of
   de firma, of hij bestaat (nog) niet.
2. **Displaynaam-regel**: personen heten overal `Voornaam (Afdeling)`
   (Zoom-formaat), live opgebouwd uit kern; uitzondering is
   `afdeling_in_naam = false` (dan de kale voornaam). Zelf namen knippen of
   formatteren mag niet.
3. **Terminologie uit het DEFINITIEBOEK** (`DEFINITIEBOEK.md`, machinebron
   `kern.definitie`): een begrip heeft in het hele platform precies een
   naam. Nieuwe term nodig? Eerst daar toevoegen, dan gebruiken.
4. **Nieuwe entiteit of relatie?** Eerst een genummerde migratie in de
   stack-repo (`db/migrations/`), met FK's naar kern. En in dezelfde sessie:
   de Second Brain (graaf.py) en de profielen bijwerken, anders bestaat de
   relatie alleen in jouw app.

## 2. UX-regels

1. **Elk getal is doorklikbaar** naar de records erachter. Een KPI of teller
   zonder drill-down is niet af.
2. **AppPortal-huisstijl**, bewust ontdaan van AI-tells: geen emoji, geen
   em-dash, geen icoonkaarten of taglines. Kijk naar het Medewerkers- of
   Communicatie-dashboard voor de visuele taal.
3. Firma's als volledige naam, personen klikbaar naar hun profiel,
   KPI-cijfers werken als filter, Excel-export waar dat zinvol is.
4. Kolomkoppen en tooltips komen uit `kern.definitie` waar een term bestaat.

## 3. Architectuur

1. De app draait als **compose-service** in de appportal-stack achter
   **nginx forward-auth (Authentik)**: eigen subdomein, eigen
   nginx-template, tegel via een `scripts/add-*-app.py`-script. Geen eigen
   loginsysteem.
2. **Eigen repo** onder `softwareglobaal` met een CLAUDE.md; de VM checkt
   uit en deployt automatisch (cron). Compose-wijzigingen alleen via git in
   de stack-repo; machine-specifiek gaat in `.env`.
3. **Secrets alleen in `.env` op de VM** - nooit in code, git of chat.
4. **Database**: een eigen schema in de appportal-Postgres met echte FK's
   naar kern, en een eigen DB-rol met minimale grants (lezen op kern,
   schrijven op het eigen schema). Logs die een audit-spoor zijn, zijn
   append-only (geen UPDATE/DELETE-grants).

## 4. Werkwijze

1. Schemawijzigingen zijn **genummerde migraties** in de stack-repo, lokaal
   getest voor de push; herhaalbare data-imports zijn idempotente seeds in
   `db/seeds/`.
2. **Frontend-code eerst parsen** (V8, bv. py-mini-racer) voor elke push:
   auto-deploy zet elke push vrijwel direct live.
3. **Documentatie in dezelfde push**: README van de app-repo, TODO.md,
   DEFINITIEBOEK.md + `kern.definitie` bij nieuwe terminologie.
4. Secrets, PIN/PUK en ander afgeschermd materiaal worden nooit door andere
   apps of de AI gelezen.

## Checklist voor livegang

- [ ] Alle namen zijn verwijzingen naar kern (geen losse strings)
- [ ] Displaynaam-regel gevolgd, nergens zelf geknipt
- [ ] Termen bestaan in DEFINITIEBOEK/kern.definitie
- [ ] Elk getal heeft een drill-down
- [ ] Geen emoji, geen em-dash, geen AI-tells
- [ ] Achter forward-auth, tegel geregeld, secrets in .env
- [ ] Migraties genummerd en lokaal getest, frontend geparst
- [ ] README + TODO + DEFINITIEBOEK in dezelfde push bijgewerkt
- [ ] Second Brain en profielen kennen de nieuwe entiteiten/relaties
