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

- **Eerstvolgende stap: 3** (Octopus-verkenning) - het **API-spoor is
  GEBLOKKEERD op gate G1** (credentials; belletje uitgesteld), maar het
  **data-spoor is gestart**: Joan's export is geïmporteerd en het
  entiteit/relatie-model (partij-laag) staat - zie de log van 2026-07-08.
  Zolang G1 open staat: restant-mapping van stap 2b afwerken via de
  Disciplines-pagina zodra het team (G2) de twijfelgevallen bevestigt.
- Blokkades: G1 (Octopus-credentials, bij Mehdi) blokkeert stap 3.
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

## Gates (input van buiten, parallel aan te vragen)

- [ ] **G1 - Octopus-API-toegang**: wie beheert Octopus? API-key/credentials
      aanvragen (zie stap 3). Zonder G1 kan t/m stap 2 gewoon door.
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
- [ ] Gate G1 binnen (credentials).
- [ ] API-docs doornemen; noteer in **docs/onderzoek-octopus-api.md**:
      auth-model, endpoints (facturen in/uit, kosten, grootboek, relaties,
      BTW), rate limits, per-dossier of per-firma, en wat NIET kan.
- [ ] Probe zoals bij Xelion: eerst read-only calls testen (nooit schrijven),
      foutcodes documenteren. Secrets alleen in .env op de VM.
- Klaar wanneer: het onderzoek-document beantwoordt "welke data, hoe vers, hoe
  betrouwbaar" en een go/no-go voor stap 4.

### Stap 4 - Octopus-pijplijn (het echte werk; patroon = Xelion-poller)
- [ ] Migratie 032: `finance`-schema - spiegeltabellen + `finance.octopus_sync`
      (status/versheid, zelfde patroon als communicatie.xelion_sync).
- [ ] Poller (standaard UIT via env-vlag, net als XELION_ENABLED), best-effort
      degradatie, paginering vanaf dag één (les van Xelion: default-pagina's
      zijn klein), sync-status zichtbaar.
- [ ] Waar draait hij: eigen host-app of in een bestaand dashboard - beslissen
      in stap 3 op basis van datavolume (voorkeur: aparte repo globaal-finance
      volgens het bestaande dashboard-repo-patroon).
- Klaar wanneer: spend-data van minstens één firma stroomt automatisch binnen,
  sync-status toont versheid, en een dag stilstand is zichtbaar als signaal.

### Stap 5 - Entiteit/relatie-model finance (de blauwe draad)
- [ ] Octopus-relaties (klanten/leveranciers) verzoenen met `kern.firma` en
      `kern.leverancier` (zelfde verzoen-patroon als migratie 012:
      echte FK's + naam-match als vangnet + mismatches worden signalen).
- [ ] Context in de relatie, nooit in de entiteit: zelfde factuur = kost voor
      firma A, opbrengst voor firma B → aparte relatierecords.
- [ ] Relaties verschijnen automatisch in de Second Brain (029); benoemen via
      graaf-regels.
- Klaar wanneer: een factuur in Octopus is in de graaf te volgen van leverancier
  → factuur → firma, zonder handwerk.

### Stap 6 - Views (pas nu de visuals)
- [ ] Per firma: spend per maand, per leverancier, per discipline.
- [ ] Cross-firma rollup ("alle firma's": geld in/uit per maand - het
      architectuurpunt van Mehdi uit TODO.md).
- [ ] Vergelijk met de handmatige kosten-data (kosten.software): verschillen
      = curatiesignalen, geen stille overschrijving.
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
