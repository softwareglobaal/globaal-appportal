# PLAN - Finance als template-discipline (Unified Dashboard)

> **Dit is de werklijst.** Eén stap per keer, in volgorde; een stap is pas af
> als het vinkje gezet is mét datum. Elke Claude-sessie (welk model ook) die
> hieraan werkt: (1) lees dit bestand + CLAUDE.md + docs/prompt-dashboard-
> ontwerp.md, (2) kijk bij **STATUS** wat de eerstvolgende stap is, (3) werk
> alléén die stap af, (4) werk STATUS + vinkje + logregel bij en push in
> dezelfde sessie. Niet vooruitwerken; blokkades noteren bij de stap.
>
> Doel (instructies Mehdi 2026-07-04, zie TODO.md § Unified Dashboard): één
> discipline - **Finance** - end-to-end bewijzen als herbruikbaar template:
> API-pull → centrale opslag → entiteit/relatie-model → views. Het
> gedocumenteerde patroon is het verkoopbare product.

## STATUS

- **Eerstvolgende stap: 7** (het template-discipline-document). Stappen
  3 t/m 6 zijn AF (2026-07-09/13): onderzoek + probe, de pijplijn
  (poller, migraties 062/063), de verzoening en de Financiën-tab - alles
  end-to-end bewezen tegen het Octopus-testdossier (35493, geseed met
  herkenbare testdata die onze echte facturen nabootst).
- Blokkades: geen voor stap 7/8. Voor **productie-data** rest van G1:
  een Octopus-gebruiker gekoppeld aan de acht echte dossiers (de
  Software House ID is binnen en werkend; het testaccount bewees de
  keten incl. schrijfrecht). Restant stap 2b wacht op G2; restpunt
  stap 6: spend per discipline wacht op een
  grootboek-naar-discipline-mapping.
- Log:
  - 2026-07-04 - plan opgesteld (Fable 5); nog geen stap gestart.
  - 2026-07-04 - stap 1 GEBOUWD (Fable 5): migratie 030 (kern.discipline, 17
    rijen + audit-trigger + 18 definities incl. 'discipline'), DEFINITIEBOEK-
    sectie, gecureerde discipline-knopen in de Second Brain (graaf.py, prefix
    disc: klaar voor de auto-edges van stap 2). Lokaal getest incl. rollen.
    Wacht op VM: `git pull && sh scripts/db-migrate.sh` (APPLY 030).
  - 2026-07-04 - stap 2 GEBOUWD (Fable 5): migratie 031 (discipline_sleutel op
    kosten.software + evidente seed-mappings Monday/Octopus/Pipedrive/DeskTime/
    Microsoft/Zoom/Close Call; kolom-level UPDATE-grant voor medewerker_writer -
    ontdekt en gefixt: die rol miste USAGE op schema kosten), Disciplines-pagina
    op het Organisatie-dashboard (per discipline: tools/abonnementen/firma's;
    lege disciplines gemarkeerd; "nog niet gemapt"-lijst), software→discipline-
    edges + verzamelsignaal in de Second Brain. Restant 2b = teamwerk (G2).
    Wacht op VM: db-migrate (APPLY 030 + 031).
  - 2026-07-08 - stap 3 DATA-SPOOR GESTART (Fable 5); API-spoor wacht op G1:
    Joan's Octopus-export geïmporteerd (migraties 056-059 + seeds
    octopus-import en partijen-opbouw: 2313 relaties, grootboek per firma,
    expliciete boekhouding→firma-mapping) en het entiteit/relatie-model
    staat als kern.partij (migratie 058, 1828 partijen, 0 wezen;
    klant/leverancier zijn rollen van dezelfde partij, BTW groepeert).
    Views erbovenop: Relaties-verkenner (organisatie), leverancier-paneel
    met relatie-ID/grootboek/klantnummer (communicatie), interne
    firma-relaties als kanten in de Second Brain.
  - 2026-07-09 - stap 3 ONDERZOEK AF (Fable 5): Software House ID
    ontvangen; docs/onderzoek-octopus-api.md geschreven op basis van de
    officiele OpenAPI-spec (78 endpoints); read-only probe klaar
    (scripts/octopus-probe.py). Rest van G1: API-gebruiker via Joan.
  - 2026-07-09 - stap 3 PROBE OK (lokaal, testaccount): keten bewezen
    (auth, dossier Globaal 35493, dossiertoken, 14 relations, 1 bookyear);
    header-les dossierToken gedocumenteerd. G1-rest = productie-toegang.
  - 2026-07-09 - stap 4 GEBOUWD (Fable 5): migratie 062 (finance-schema,
    lokaal getest), poller in de organisatie-app (finance_sync.py,
    standaard uit), compose-env, status-endpoint /api/octopus-sync.
    Wacht op VM: db-migrate 062 + OCTOPUS_* in .env + OCTOPUS_ENABLED=true;
    eerste run tegen het testdossier, productie zodra G1 helemaal dicht is.
  - 2026-07-13 - stap 6 GEBOUWD (Fable 5): Financien-tab (organisatie),
    getest met de Flask-testclient tegen de lokale spiegel incl.
    drill-down-verificatie. Geen migratie nodig; deployt vanzelf.
    Restpunt: spend per discipline wacht op een
    grootboek-naar-discipline-mapping.
  - 2026-07-14 - PRODUCTIE LIVE: echte Software House ID + leesgebruiker
    (minimale vinkjes: webservice, dossier manager, basis- en
    geavanceerde lijsten), 13 echte dossiers gesynct (~30k boekingen,
    alles ok) na drie robuustheid-fixes (timeout vangen, per boekjaar
    chunken, continue i.p.v. return). Migratie 065: KBO's gevuld,
    Corenbo + ENSTACO als firma erbij, elk dossier expliciet aan zijn
    firma (HDS aan de Suriname-variant). G1 DICHT.
  - 2026-07-13 - stap 5 GEBOUWD (Fable 5): migratie 063 (verzoening:
    finance.octopus_relatie + dossier_id op de boekhouding-mapping),
    relaties-sync met partij-koppeling in finance_sync, finance-laag in
    de graaf. Lokaal end-to-end bewezen op het testdossier. Wacht op VM:
    db-migrate 063; de eerstvolgende sync-run laadt de relaties vanzelf.
  - 2026-07-09 - schrijfrecht BEVESTIGD (no-op PUT, HTTP 204, data
    ongewijzigd) en het testdossier geseed met relevante testdata
    (scripts/octopus-seed-testdata.py, idempotent: 5 relaties waarvan 3
    telefonie-leveranciers met echte BTW-nummers, 5 boekingen die onze
    echte maandfacturen nabootsen op rekening 616200). De pijplijn pikte
    ze incrementeel op (5 bijgewerkt) en de spend-per-leverancier-query
    klopt op de cent: Proximus 105,20 / Mega 16,55 / Close Call 316,00.

## Gates (input van buiten, parallel aan te vragen)

- [ ] **G1 - Octopus-API-toegang**: de Software House ID is binnen
      (2026-07-09, in .env op de VM). Rest: een Octopus-gebruiker
      (user + wachtwoord, liefst leesbeperkt, gekoppeld aan alle acht
      dossiers) - vraag aan Joan. Dan kan de probe draaien.
- [ ] **G2 - lijst actieve tools**: Mehdi/Angela bevestigen welke tools het
      cluster vandaag betaalt/gebruikt (voor stap 2b); kosten.software is het
      vertrekpunt maar is alleen software.

## De stappen

### Stap 1 - Disciplines als centrale entiteit (klein, fundament) - ✔ 2026-07-04
- [x] Migratie 030: `kern.discipline` met de **17 vaste disciplines** (namen
      uit docs/prompt-dashboard-ontwerp.md, exact die lijst; sleutel stabiel,
      naam wijzigbaar - zelfde patroon als kern.definitie).
- [x] Definities voor de 17 in `kern.definitie` (+ DEFINITIEBOEK.md).
- [x] Zichtbaar in de Second Brain - gecureerde knopen in graaf.py (type
      'discipline', hover toont de definitie) i.p.v. de auto-laag: zonder
      FK's zou de tabel anders pas in stap 2 verschijnen. Prefix `disc:`
      geregistreerd zodat de auto-edges van stap 2 eraan vasthaken.
- Klaar wanneer: 17 rijen in kern.discipline, zichtbaar in de graaf, definities
  live. Geen UI nodig in deze stap.

### Stap 2 - Tool→discipline-mapping (maakt dubbels/gaten zichtbaar) - ✔ 2026-07-04
- [x] 2a. Migratie 031: `discipline_sleutel` op `kosten.software` (nullable,
      FK naar kern.discipline; NULL = nog niet gemapt = verzamelsignaal in de
      graaf; alleen medewerker_writer mag de kolom bijwerken).
- [x] 2b. Evidente tools gemapt in de migratie (Monday→operations, Octopus→
      finance, Pipedrive→sales, DeskTime→HR, Microsoft/Zoom/Close Call→IT);
      **restant staat op de Disciplines-pagina onder "nog niet gemapt" en
      wacht op het team (gate G2) - niet gegokt.**
- [x] 2c. Disciplines-pagina op het Organisatie-dashboard: per discipline de
      tools (abonnementen, firma's, seats), lege disciplines gemarkeerd
      ("leeg" = ziekenhuis-model), ongemapte lijst onderaan. View = query.
- Klaar wanneer: elke rij in kosten.software heeft een discipline of een
  bewust-open signaal; de gaten-lijst bestaat als view.

### Stap 3 - Octopus-verkenning (onderzoek, géén bouw)
- [ ] Gate G1 binnen (Software House ID ontvangen 2026-07-09; de
      API-gebruiker via Joan is het laatste stuk).
- [x] API-docs doorgenomen (2026-07-09): **docs/onderzoek-octopus-api.md**
      - auth-model (softwareHouseUuid-header + user/password -> token 10
      min -> dossiertoken per boekhouding), alle 78 endpoints gemapt op
      onze behoeften (relations/accounts/journals/bookings incl.
      modified-varianten voor incrementele sync; deliverynotes voor de
      facturatievoorstel-flow), aandachtspunten (rate limits onbekend,
      alles per dossier, alleen-GET-poller).
- [ ] Probe draaien (script staat klaar: **scripts/octopus-probe.py**,
      read-only, secrets uit .env): dossiers oplijsten + relations-check
      tegen de import van 2026-07-08 -> go/no-go voor stap 4.
- Klaar wanneer: het onderzoek-document beantwoordt "welke data, hoe vers, hoe
  betrouwbaar" en een go/no-go voor stap 4.

### Stap 4 - Octopus-pijplijn (het echte werk; patroon = Xelion-poller)
- [x] Migratie **062** (was 032 in het oorspronkelijke plan): `finance`-schema
      met octopus_sync (status/versheid per dossier), octopus_bookyear en
      octopus_boeking (getypte kern + regels/ruw als jsonb); grants expliciet,
      schrijven alleen via medewerker_writer. Lokaal getest 2026-07-09.
- [x] Poller GEBOUWD (organisatie-app, finance_sync.py): standaard UIT
      (OCTOPUS_ENABLED), best-effort, re-auth per run (token 10 min),
      incrementeel via de modified-endpoints (bookyearId=-1 +
      modifiedTimeStamp met een uur overlap; upserts idempotent),
      sync-status zichtbaar via GET /api/octopus-sync (incl.
      verouderd-vlag bij een dag stilstand).
- [x] Waar draait hij: **in de organisatie-app** (beslissing conform stap 3:
      datavolume is klein, DeskTime-poller-precedent, schrijfrol bestaat al);
      een aparte repo globaal-finance kan later alsnog als het volume groeit.
- Klaar wanneer: spend-data van minstens één firma stroomt automatisch binnen,
  sync-status toont versheid, en een dag stilstand is zichtbaar als signaal.

### Stap 5 - Entiteit/relatie-model finance (de blauwe draad)
- [x] Octopus-relaties verzoend (migratie 063 + finance_sync): relaties per
      dossier gespiegeld naar finance.octopus_relatie met partij_id via
      BTW-cijfers en exacte-naam-vangnet; dossiers aan firma's via BTW/KBO
      (dossier_id op kosten.octopus_boekhouding, expliciet - geen
      naam-raden). Wat niet koppelt blijft zichtbaar als los.
- [x] Context in de relatie: boekingen leven per dossier (kost voor A en
      opbrengst voor B zijn twee records in twee dossiers), tegenpartij is
      een verwijzing naar de partij-entiteit.
- [x] Second Brain: finance-laag met dossier-ankers (gelinkt dossier = de
      firma-knoop zelf), boeking-knopen (cap: 90 dagen, 400 stuks) en
      tegenpartij-kanten naar bestaande firma-/leverancier-knopen waar de
      partij dat toelaat. Lokaal bewezen: leverancier -> factuur -> dossier
      is te volgen (Proximus-testfactuur naar de Proximus-knoop).
- Klaar wanneer: een factuur in Octopus is in de graaf te volgen van leverancier
  → factuur → firma, zonder handwerk.

### Stap 6 - Views (pas nu de visuals)
- [x] Financien-tab op het Organisatie-dashboard (2026-07-13): geld in/uit
      per maand met saldo, spend per tegenpartij (partij-naam via de
      verzoening), per firma filterbaar; elk getal doorklikbaar naar de
      boekingen erachter. Spend per discipline volgt zodra de
      grootboek-naar-discipline-mapping bestaat (klein vervolgwerk, kan
      met Joan's grootboek-analyse als startpunt).
- [x] Cross-firma rollup: het "alle firma's"-filter is de standaardstand.
- [x] Vergelijk met kosten.software: eigen sectie "Naast het
      kosten-dashboard" per gedeelde leverancier; verschillen zijn
      zichtbare curatiesignalen, niets wordt overschreven.
- Klaar wanneer: de views beantwoorden Mehdi's standaardvragen zonder export
  of handwerk; views slaan niets op.

### Stap 7 - Het template-document (het product)
- [ ] **docs/template-discipline.md**: het herbruikbare stappenpatroon
      (onderzoek → pijplijn → verzoening → views → signalen) beschreven aan de
      hand van hoe Finance het doorliep, inclusief valkuilen. Generiek
      geformuleerd (niet aan één firma of tool gebonden).
- [ ] Metingen voor de case study vastleggen: wat kostte dit handmatig vóór,
      wat is er nu automatisch (voor de reselling-bewijsvoering).
- Klaar wanneer: een volgende discipline (bv. HR/DeskTime of sales/Pipedrive)
  kan het document volgen zonder nieuwe ontwerpbeslissingen.

### Stap 8 - Entiteit/relatie/view-audit (breed, na het bewijs)
- [ ] Alle bestaande schema's nalopen op het drie-lagen-principe; overtredingen
      (waarden die eigenlijk relaties zijn) → migraties, één per keer.
- [ ] Master data layer aanvullen: tools en abonnementen als canonieke
      entiteiten waar nodig.
- Klaar wanneer: de audit-lijst leeg is of bewust geparkeerd met reden.

## Werkafspraken voor de uitvoerende sessie

- Alle vaste regels uit CLAUDE.md gelden (migraties genummerd + lokaal getest
  op poort 5433, V8-parse vóór frontend-push, geen heredocs, secrets via .env,
  exec-bit op scripts, nieuwe relaties zelfde sessie in graaf + profielen).
- Voortgang is pas voortgang als hij gepusht is: STATUS-blok + vinkje + log in
  dít bestand horen bij elke afgeronde stap in dezelfde commit.
- Eén stap per keer betekent ook: een halve stap laten staan mét notitie in de
  log is beter dan twee halve stappen.
