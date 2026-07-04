# PLAN — Finance als template-discipline (Unified Dashboard)

> **Dit is de werklijst.** Eén stap per keer, in volgorde; een stap is pas af
> als het vinkje gezet is mét datum. Elke Claude-sessie (welk model ook) die
> hieraan werkt: (1) lees dit bestand + CLAUDE.md + docs/prompt-dashboard-
> ontwerp.md, (2) kijk bij **STATUS** wat de eerstvolgende stap is, (3) werk
> alléén die stap af, (4) werk STATUS + vinkje + logregel bij en push in
> dezelfde sessie. Niet vooruitwerken; blokkades noteren bij de stap.
>
> Doel (instructies Mehdi 2026-07-04, zie TODO.md § Unified Dashboard): één
> discipline — **Finance** — end-to-end bewijzen als herbruikbaar template:
> API-pull → centrale opslag → entiteit/relatie-model → views. Het
> gedocumenteerde patroon is het verkoopbare product.

## STATUS

- **Eerstvolgende stap: 1** (disciplines-entiteit)
- Blokkades: stap 3+ heeft Octopus-API-credentials nodig (gate G1, bij Mehdi).
- Log:
  - 2026-07-04 — plan opgesteld (Fable 5); nog geen stap gestart.

## Gates (input van buiten, parallel aan te vragen)

- [ ] **G1 — Octopus-API-toegang**: wie beheert Octopus? API-key/credentials
      aanvragen (zie stap 3). Zonder G1 kan t/m stap 2 gewoon door.
- [ ] **G2 — lijst actieve tools**: Mehdi/Angela bevestigen welke tools het
      cluster vandaag betaalt/gebruikt (voor stap 2b); kosten.software is het
      vertrekpunt maar is alleen software.

## De stappen

### Stap 1 — Disciplines als centrale entiteit (klein, fundament)
- [ ] Migratie 030: `kern.discipline` met de **17 vaste disciplines** (namen
      uit docs/prompt-dashboard-ontwerp.md, exact die lijst; sleutel stabiel,
      naam wijzigbaar — zelfde patroon als kern.definitie).
- [ ] Definities voor de 17 in `kern.definitie` (+ DEFINITIEBOEK.md).
- [ ] Verschijnt automatisch in de Second Brain (migratie 029-autolaag); via
      kern.graaf_regel meteen netjes benoemen.
- Klaar wanneer: 17 rijen in kern.discipline, zichtbaar in de graaf, definities
  live. Geen UI nodig in deze stap.

### Stap 2 — Tool→discipline-mapping (maakt dubbels/gaten zichtbaar)
- [ ] 2a. Migratie 031: `discipline_id` op `kosten.software` (+ trigger-vrij,
      handmatig te vullen; NULL = nog niet gemapt = signaal in de graaf).
- [ ] 2b. Bestaande tools mappen (Monday→operations/PM, Octopus→finance,
      Pipedrive→sales, DeskTime→HR, Zoom/Xelion→IT of communicatie — bij
      twijfel met team kortsluiten, niet gokken).
- [ ] 2c. Kosten-dashboard of Organisatie: eenvoudige weergave "per discipline:
      welke tools, wat kosten ze, waar zitten dubbels/gaten" (view = query,
      geen opslag).
- Klaar wanneer: elke rij in kosten.software heeft een discipline of een
  bewust-open signaal; de gaten-lijst bestaat als view.

### Stap 3 — Octopus-verkenning (onderzoek, géén bouw)
- [ ] Gate G1 binnen (credentials).
- [ ] API-docs doornemen; noteer in **docs/onderzoek-octopus-api.md**:
      auth-model, endpoints (facturen in/uit, kosten, grootboek, relaties,
      BTW), rate limits, per-dossier of per-firma, en wat NIET kan.
- [ ] Probe zoals bij Xelion: eerst read-only calls testen (nooit schrijven),
      foutcodes documenteren. Secrets alleen in .env op de VM.
- Klaar wanneer: het onderzoek-document beantwoordt "welke data, hoe vers, hoe
  betrouwbaar" en een go/no-go voor stap 4.

### Stap 4 — Octopus-pijplijn (het echte werk; patroon = Xelion-poller)
- [ ] Migratie 032: `finance`-schema — spiegeltabellen + `finance.octopus_sync`
      (status/versheid, zelfde patroon als communicatie.xelion_sync).
- [ ] Poller (standaard UIT via env-vlag, net als XELION_ENABLED), best-effort
      degradatie, paginering vanaf dag één (les van Xelion: default-pagina's
      zijn klein), sync-status zichtbaar.
- [ ] Waar draait hij: eigen host-app of in een bestaand dashboard — beslissen
      in stap 3 op basis van datavolume (voorkeur: aparte repo globaal-finance
      volgens het bestaande dashboard-repo-patroon).
- Klaar wanneer: spend-data van minstens één firma stroomt automatisch binnen,
  sync-status toont versheid, en een dag stilstand is zichtbaar als signaal.

### Stap 5 — Entiteit/relatie-model finance (de blauwe draad)
- [ ] Octopus-relaties (klanten/leveranciers) verzoenen met `kern.firma` en
      `kern.leverancier` (zelfde verzoen-patroon als migratie 012:
      echte FK's + naam-match als vangnet + mismatches worden signalen).
- [ ] Context in de relatie, nooit in de entiteit: zelfde factuur = kost voor
      firma A, opbrengst voor firma B → aparte relatierecords.
- [ ] Relaties verschijnen automatisch in de Second Brain (029); benoemen via
      graaf-regels.
- Klaar wanneer: een factuur in Octopus is in de graaf te volgen van leverancier
  → factuur → firma, zonder handwerk.

### Stap 6 — Views (pas nu de visuals)
- [ ] Per firma: spend per maand, per leverancier, per discipline.
- [ ] Cross-firma rollup ("alle firma's": geld in/uit per maand — het
      architectuurpunt van Mehdi uit TODO.md).
- [ ] Vergelijk met de handmatige kosten-data (kosten.software): verschillen
      = curatiesignalen, geen stille overschrijving.
- Klaar wanneer: de views beantwoorden Mehdi's standaardvragen zonder export
  of handwerk; views slaan niets op.

### Stap 7 — Het template-document (het product)
- [ ] **docs/template-discipline.md**: het herbruikbare stappenpatroon
      (onderzoek → pijplijn → verzoening → views → signalen) beschreven aan de
      hand van hoe Finance het doorliep, inclusief valkuilen. Generiek
      geformuleerd (niet aan één firma of tool gebonden).
- [ ] Metingen voor de case study vastleggen: wat kostte dit handmatig vóór,
      wat is er nu automatisch (voor de reselling-bewijsvoering).
- Klaar wanneer: een volgende discipline (bv. HR/DeskTime of sales/Pipedrive)
  kan het document volgen zonder nieuwe ontwerpbeslissingen.

### Stap 8 — Entiteit/relatie/view-audit (breed, na het bewijs)
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
