# To-do - AppPortal / Organisatie / Communicatie

> Parkeerlijst van afgesproken maar nog niet gebouwde zaken. Bron: Zoom-meetings
> 2026-07-01 t/m 2026-07-03 + lopende afspraken. Afvinken of verplaatsen bij oppakken.

## ★ EINDDOEL - Eigen draaiboek-platform (meeting 2026-07-03, Mehdi)

> **Noordster, niet nu bouwen.** Visie: een eigen **draaiboek-(playbook-)management**
> in onze eigen dashboards, zodat die dé *source of truth* worden - als vervanging
> van **Toolmaster** (~€70/gebruiker/maand ≈ €3.000/mnd bij 20-30 mensen) en als
> aanvulling waar **Monday** tekortschiet. Kernonderscheid dat Mehdi maakt:
> **projectmanagement** (Monday: 100 projecten op grove lijnen; kan géén deeltaken/
> micromanagement - een EPB-proces met ~200 stappen blokkeert) vs. **draaiboek**
> (het *protocol/playbook* van één proces: alle fases + deeltaken, van A→Z zonder
> fouten). Een draaiboek legt het proces vast → maakt automatisering mogelijk →
> levert data op. Uiteindelijk óók verkoopbaar aan partners (€70/gebruiker-model).

- [ ] **Deep-research Toolmaster + Monday** (Mehdi vraagt dit expliciet): wat doen ze,
      waar zitten de limieten (Monday: geen deeltaken/playbook; Toolmaster: duur +
      je betaalt voor maatwerk dat ze daarna gratis aan iedereen aanbieden). →
      feature-matrix + wat we naboetsen en waar we verder gaan.
- [x] **Terminologie in het DEFINITIEBOEK** - GEDAAN (migratie 021): draaiboek,
      projectmanagement, fase, stap, run in `kern.definitie` + DEFINITIEBOEK.md.
- [ ] **Datamodel: draaiboek-schema** - **v2 TER REVIEW** (Mehdi/Shaniel):
      **`docs/ontwerp-draaiboek-datamodel.md`**, verfijnd met de deep-research
      van 2026-07-03. 10 tabellen: dossier→runs (VC-ontwerp + -verwezenlijking),
      kickoff-formulier + conditie-regels (adaptief klein/groot), snapshots,
      append-only log, stap-soorten incl. goedkeuring. MVP-inhoud (VC-flow,
      KB 25/01/2001) staat erin. 4 beslispunten onderaan het doc; daarna
      migratie 022 + MVP-skelet (repo `globaal-draaiboek`). NB uit de research:
      Toolmaster-€70-claim ONBEVESTIGD (enige €70 = support-uurtarief) → echte
      offerte vragen; documentgeneratie VGP/PID = fase 2 (dé vervanger).
- [x] **MVP: veiligheidscoördinatie** - PROTOTYPE LIVE op draaiboek.globaal.be
      (2026-07-03, §14.7): migratie 022 (schema + VC-draaiboek geseed: 5 fases /
      26 stappen / kickoff + condities), app-repo `globaal-draaiboek` (snapshot-
      runs, blokkades, append-only log, herhaal-stappen; 18 e2e-tests groen),
      UI ont-AI'd, adres-autocomplete op dossiers. Rest: (a) **demo aan Mehdi**,
      (b) VC-flow valideren met Ashwent, (c) fase 2-lijst in de README
      (documentgeneratie VGP/PID, sjabloon-beheer-UI, automatisering, Fathom).
- [ ] **Sequentieel geheugen ("waar staan we")** - lost het verslagen-probleem op:
      het draaiboek houdt bij welke fase/verslag af is, zodat mens én AI weten
      "verslag 2 klaar → volgende is 3". Het draaiboek wordt de projectvoortgang-bron
      die AI nu mist.
- [ ] **Fathom → deeltaken** (Shaniel): nu Fathom gelinkt is, kleine taken uit meetings
      automatisch in kaart brengen en aan draaiboek-stappen koppelen.
- [ ] **Automatisering op het draaiboek**: zodra het proces vastligt - trigger-acties
      ("stap af → mail → bij antwoord → volgende stap"). Precies wat Monday niet kan.
- [ ] **Document-gedreven / adaptief draaiboek**: AI leest een plan/document met de
      logica van (bv.) veiligheidscoördinatie en genereert/past het draaiboek aan -
      kleine gezinswoning = weinig stappen, groot project = meer. (Document-generatie
      zelf is een apart spoor.)
- [ ] **Adoptievoorwaarde**: iedereen (20-30) moet het gebruiken, anders geen data -
      UX + toegang op orde; kostenbesparing t.o.v. Toolmaster expliciet maken.
- [ ] **Commercialisering (lange termijn)**: draaiboek-product aan partners aanbieden -
      pas ná intern bewezen.
- [ ] **Directe actie-items uit de meeting**: (a) Ashwent's Toolmaster-account upgraden
      → dan samen met Shaniel de veiligheidscoördinatie-playbook opzetten om van te
      leren; (b) dashboard-review met Ivor inplannen.

## Unified Dashboard - instructies Mehdi (2026-07-04)

> Bron: schriftelijke visie + feedback van Mehdi. Vaste architectuur = **17
> disciplines** (nu definitief, mét namen: HR/recruitment, sales/bizdev,
> marketing/communicatie, finance/accounting, operations/PM, legal/compliance,
> customer service, IT/systemen, procurement/vendor mgmt, QA, risk mgmt,
> strategische planning, data/analytics, facilities/administratie, R&D, supply
> chain, partnerships). Bedrijven (±15) zijn de variabele laag. Meta-laag óver
> bestaande tools (API, realtime), niet vervangen. Herbruikbare ontwerp-prompt:
> **`docs/prompt-dashboard-ontwerp.md`** - gebruiken bij elk nieuw tab-ontwerp.

- [ ] **17 disciplines als centrale entiteit** in kern + DEFINITIEBOEK (met de
      vaste namen); lege discipline blijft zichtbaar als leeg (ziekenhuis-model).
- [ ] **Tool→discipline-mapping**: elke tool (Monday, Octopus, Pipedrive,
      DeskTime, Google Calendar, Toolmaster, …) aan zijn discipline koppelen →
      dubbele software, ongebruikte licenties, prijsverschillen en gaten
      zichtbaar. Sluit aan op kosten-dashboard + kern.leverancier.
- [ ] **Entiteit/relatie/view-audit**: bestaande schema's nalopen op het
      principe entiteit (bestaat één keer) / relatie (aparte record, daar leeft
      de context: zelfde pand = kost voor A, opbrengst voor B) / view (slaat
      nooit data op). Overtredingen → migratie.
- [ ] **Master data layer aanvullen**: elk entiteitstype één canoniek record met
      stabiel id (personen/firma's/adressen/leveranciers zijn er; tools,
      abonnementen, panden-verrijking volgen).
- [ ] **Finance end-to-end als template-discipline** - **PLAN LIGT KLAAR:
      zie PLAN.md** (8 stappen, één per keer; stap 1 = disciplines-entiteit,
      gate G1 = Octopus-credentials). Patroon documenteren tíjdens het bouwen -
      dat document ís het verkoopbare product.
- [x] **DeskTime-API gekoppeld** (2026-07-04): tweede tool-API na Xelion.
      Spiegel kosten.desktime_medewerker (migratie 033) met e-mail/voornaam-
      match naar kern.persoon; de gebruik-relatie firma-discipline leest de
      spiegel mee, dus DeskTime-seats hoeven niet handmatig. Sync in de
      Organisatie-app (interval, best-effort); DESKTIME_API_KEY in .env.
- [ ] **Pijplijn boven visuals**: sync-betrouwbaarheid en versheid als expliciete
      kwaliteitseis bij elke API-koppeling (staleness zichtbaar maken, zoals de
      xelion_sync-status).
- [ ] **Interne rollout = case study**: meetbare resultaten bijhouden (minder
      handmatige coördinatie, schonere spend) voor de latere reselling.
- [ ] **Agent-ready (later)**: één agent per discipline + COO-agent; rapportage-
      structuur standaard, agent-logica per bedrijfstype gespecialiseerd.

## Meeting 2026-07-03 (dashboard-review + architectuur)

> Draaiboek-einddoel door Mehdi **bevestigd** ("Dat is het"). Nieuwe punten:

- [x] **Platform + leverancier klikbaar maken** in Communicatie - GEBOUWD
      (2026-07-03): beide kolommen blauwe links; klik = **filtert de lijst** op die
      waarde (toggle: nogmaals = uit). Platform kreeg dezelfde filter-infra als
      leverancier (distinct platforms via `/api/refs`, chip-rij, serverfilter). Een
      rijker leverancier-kostenoverzicht bij de klik = natuurlijke vervolgstap
      (koppelt aan "verbruik op kosten-dashboard").
- [ ] **ARCHITECTUUR - één dashboard, niet 17** (Mehdi, beslist): NIET 17 losse
      dashboards. Eén dashboard, **15 bedrijven**, met tabs + subtabs; **per firma
      filteren** (zoals boekhouding: één dashboard, kies de firma). **RBAC per tab via
      login** - wie iets niet hoeft te zien, ziet het niet. **Cross-firma rollup**:
      "alle firma's" → geld binnen/uit per maand, welke firma bracht het meeste op /
      kostte het meeste. (Structureel principe voor álle toekomstige dashboards.)
- [x] ~~Xelion-data via screenshots~~ - VERVALLEN (2026-07-03, latere meeting):
      Siyan heeft API-toegang tot Xelion gekregen; de echte API-koppeling vervangt
      deze workaround. Zie "Xelion-API - TOEGANG BINNEN" hieronder.
- [ ] **Woordenboek-definities samen aanscherpen** (Mehdi + Shaniel, als er tijd is):
      de AI-gegenereerde definities nalopen en verscherpen via de beheer-UI. (Definitie
      "vaste prijs" al bevestigd: vast maandbedrag, excl. BTW, per resource.)

## Second Brain & Xelion (2026-07-03, avond)

- [x] **Xelion-API gekoppeld** - belvolgorde live gespiegeld (migratie 028; login
      via userName/password/userSpace, paginering, allowedNumbers, kanonieke
      nummer-match). Kolom in Communicatie + persoonsprofielen + graaf.
      Open: appKey aanvragen (wordt verplicht); XELION_DEBUG uitzetten na een
      week stabiel draaien; fase 2 = belvolgorde schrijven (PATCH phonelines).
- [x] **Second Brain schema-gedreven** (migratie 029) - besluit: geen afhankelijkheid
      van Claude/mensen om de graaf bij te houden. Auto-laag uit de Postgres-
      catalogus + curatie als data (kern.graaf_regel) + signalen voor onbenoemde
      relaties + versiebeheer met vastpinnen (paneel "Graaf-versies", wb-editors).
- [ ] **Graaf-curatie eerste ronde**: na migratie 029 de nieuw verschenen
      relaties (draaiboek, vermogen, definitie-verwijzingen) benoemen of
      verbergen via de signalen-lijst.

## Meeting Mehdi 2026-07-04 (dashboard-feedback, avond)

> Punten 1-11 GEBOUWD dezelfde avond (migratie 039 + communicatie-app):
> "Gefactureerd aan" zonder intern, belvolgorde-definitie, statistiek-kolommen
> uit het register naar de Xelion-statistieken, gebruikt-voor met vrije tekst,
> contracttype/opzegtermijn-velden, statistieken v2 met filters (periode,
> dag/week/maand/weekdag, nummer, persoon) en kerncijfers. Rest hieronder:

- [ ] **Platform centraliseren** (Mehdi: definitie van platform mag niet per
      dashboard verschillen): platforms van de app-eigen keuzelijst naar een
      centrale kern-lijst tillen, zoals leveranciers. Apart klusje (migratie +
      verzoening bestaande waarden).
- [ ] **VERRE TOEKOMST - gesprekstranscripten** automatisch in een map
      (opnames bestaan al in het archief via recordingStatus); privacy- en
      opslagvragen eerst.
- [ ] **VERRE TOEKOMST - e-mailstatistieken** met labeling (junk/reclame/
      klant) en reactietijden.
- [ ] **VERRE TOEKOMST - OMV-scraper naar een agent** die zelfstandig draait
      en bericht stuurt bij fouten.

## Xelion-communicatielog (2026-07-04) - laag 2 en 3, bewust geparkeerd

> Laag 1 (archief) is GEBOUWD: migratie 034 + incrementele poller-sync,
> append-only met ruwe API-records (her-afleidbaar), rijdt mee in de
> nachtelijke S3-backup. 90 dagen = trend-bril en backfill-diepte, geen
> bewaartermijn. Hieronder wat er nog op staat:

- [x] **Laag 2a - kolommen in het nummerregister** - GEBOUWD (2026-07-04):
      "Oproepen (30 d)" in de standaardview (0 = rood) en "Laatste oproep"
      via Mijn view. Gemist-percentage wacht op 2c (semantiek).
- [x] **Laag 2b - Statistieken-tab** - GEBOUWD (2026-07-04): oproepen per
      dag (30 d), drukste nummers, stil-lijst (60+ d, met validatiestatus).
      Nog open: gemist-percentage en piekuren (na 2c), wie neemt op (na het
      privacy-besluit).
- [x] **Laag 2c - veldsemantiek verfijnd** - GEBOUWD (2026-07-04, migratie
      035): detail-call per record (gedoseerd), beantwoord = callAnswerTime
      aanwezig, lijn-match via phoneLine.oid naar de belvolgorde-spiegel,
      deelnemer-adressen als vangnet. Gemist-kolommen in register en tab.
      Bonus in het ruwe detail voor later: wachttijd, doorverbindingen,
      audiokwaliteit (mos-scores), WhatsApp-categorie.
- [x] **PRIVACY-BESLISPUNT - BESLIST (Shaniel, 2026-07-04)**: belminuten per
      persoon mogen; dit is bewuste personeelsmonitoring. Gebouwd via de
      Xelion-gebruikers-spiegel (migratie 038). contentSummary blijft
      voorlopig ongetoond; RBAC-verfijning kan later meeliften op het
      RBAC-per-tab-architectuurpunt van Mehdi.
- [ ] **Laag 3 - analyse**: eerst regels-signalen (nummer X dagen stil,
      gemist-percentage verdubbeld, voicemail vol), daarna AI-duiding op
      dagaggregaten (nooit ruwe logs): communicatie-coach in de briefing.
- [ ] **Optioneel archief-export**: maandelijkse JSONL-dump van de spiegel
      naar S3 naast de databasebackup (alleen als het team losse bestanden
      wil; de tabel zelf is al het archief).

## Externe contacten & lagen-model (2026-07-06)

- [x] **Lagen-model Second Brain** (organisatie-app): graaf opent met de kern
      (persoon, firma, afdeling, telefoonnummer); overige typen zijn
      legenda-chips die per laag aan/uit gaan, gerenderd in porties van 80.
      Keuze per browser onthouden (localStorage, geen serverlast); zoeken
      werkt over alle lagen en zet een uitgeschakelde laag zelf aan.
- [x] **Externe partij als kolom** (migratie 041): `extern_nummer`/
      `extern_naam` op het oproep-archief + `communicatie.canoniek_nummer()`
      als SQL-functie; backfill over bestaande records (deelnemers,
      terugbelnummer, pijl-patroon); poller vult nieuwe records; drill-down
      leest de kolom met de oude parse-keten als vangnet.
- [x] **Extern contact als graaf-laag** (migratie 042 + organisatie-app):
      knopen per kanoniek nummer met kanten naar de register-nummers;
      standaard uit (lagen-model); drukste 300, rest wordt een signaal.
- [x] **AI-context ontkoppeld** - GEBOUWD (2026-07-08): bouw_ai() levert
      de kern-waarheid zonder bulk-lagen, met top-10-veelbellers-aggregaat
      en een niet_meegegeven-blok (met aantallen); de systeemprompt
      verplicht de AI eerlijk te benoemen wat hij niet ziet en naar het
      dashboard te verwijzen voor detail.
- [x] **Veelbellers en verkeer op onbekende nummers** - GEBOUWD
      (2026-07-08): twee secties op de Xelion-statistieken met drill-down
      per beller (extern-filter) en per onbekend nummer (genorm-filter).
- [x] **Xelion-kosten via de API: onderzocht, bestaat niet** (2026-07-06):
      0 kostvelden in 720 archiefrecords, alle facturatie-endpoints 404.
      Gesprekskosten dus via Businesscom (factuur/portaal). Wel gebouwd:
      licentie-spiegel (migratie 043, licenses-endpoint) met twee Second
      Brain-signalen: gebruikerslicenties vol (12/12 = onboarding-blokker,
      eerst bijkopen) en betaald-maar-ongebruikt (nu: exchange 1/0,
      navragen bij Businesscom). Bijvangst voor later: reports-endpoint
      heeft een AutomatedReport "missed call" in de centrale.
- [ ] **KLANTENDATABASE (theorie eerst, afspraak 2026-07-06)**: brainstorm
      loopt; kern van het idee: klant als kern-entiteit met telefoonnummers
      en e-mailadressen als koppelvlak (kanonieke vorm), zodat externe
      contacten, facturatie en dossiers aan dezelfde klant linken. Eerst
      beslissen waar de klant vandaag echt leeft (CRM/Excel/facturatie) en
      of we spiegelen of zelf bronhouder worden. Nog niets bouwen.

## Meeting Mehdi 2026-07-06 (communicatie-register, Fathom-transcript)

- [x] **"Vaste prijs" wordt "Kostprijs"** (migratie 044): "vast" is fout want
      elke prijs kan veranderen; excl. BTW, van de laatste factuur. Sleutel
      blijft vaste_prijs.
- [x] **"Interne doorfacturatie naar" wordt "Kosten aanrekenen aan"**
      (migratie 044): er wordt niets echt gefactureerd. Leeg laten wanneer de
      betalende firma zelf gebruikt. Sleutel blijft doorfactureren_naar.
- [x] **Prijs-metadata** (migratie 044 + register): prijstype (per maand of
      per minuut, alleen maandbedragen in maandtotalen), peildatum van de
      laatste factuur, en een rood uitroepteken in het register wanneer de
      prijs 2+ maanden oud is of geen peildatum heeft.
- [x] **Sticky kolomkoppen** in het register bij verticaal scrollen.
- [ ] **Doel wordt een vaste, unieke woordenlijst** i.p.v. vrije tekst
      (het grote structuurpunt): office/algemeen, sales, finance, spoofing,
      cold calling, B2B, standaardprojecten, klantnummer, prive. Doel:
      kunnen tellen ("hoeveel finance-nummers hebben we"). Daarna alle
      bestaande doelen hermappen (energie-efficient hoort bij gebruikt-voor,
      dubbele sales-varianten samenvoegen).
- [x] **"Gebruikt voor" als vaste keuzelijst + data hermapte** - KLAAR
      (2026-07-06, migraties 045-048): opties Contrax, Tekenwerk,
      Energie-efficiënt, Sales-campagne Unabo, Sales Unabo inbound en
      Privé in communicatie.lijst; dropdown in detailpaneel en
      toevoegformulier; redundante zelf-verwijzingen opgeschoond. Alle 34
      afwijkende nummers hermapte: persoonlijke nummers (doel = naam
      collega) op Privé incl. Telesur; klantnummers Verbraeken & Co en
      Yannick Technics op doel "Klantnummer [firmanaam]" met gebruikt-voor
      Contrax; TKN-cluster op Tekenwerk; EE-cluster op Energie-efficiënt.
      De doel-teksten zelf normaliseren volgt in de taxonomie-ronde.
- [x] **Ontbrekende kostprijzen aanvullen** - Proximus GEDAAN (factuur
      7604078875 verwerkt, 21,04/mnd + peildatum). Nog open: peildatum van
      de Mega-nummers (factuur Mega ernaast leggen; prijs 3,31 staat er al).
- [ ] **Actief vs niet-actief uit de statistieken**: welke nummers zijn echt
      nog in gebruik (kiem: de stil-lijst). Gesprek brak hier af; precieze
      wens eerst afmaken met Mehdi.
- [ ] **Overleg finance (actie Shaniel)**: een centraal finance-nummer i.p.v.
      een per firma.
- UNABO-spelling blijft zoals hij is (United + Bouw), geen actie.

## Meeting Mehdi + Siyan + Joan 2026-07-08 (impromptu: labels + Octopus)

> Bron: Fathom-transcript (19 min). Rode draad: labels standaardiseren
> ("office/bureau/kantoor is broeie broeie") en het Unabo-duplicaat op het
> Mega-leverancierpaneel.

- [x] **Gebruikt-voor gestandaardiseerd** - GEBOUWD (migratie 061):
      "Algemene communicatie" als vaste waarde voor algemene
      klantcommunicatie (de WhatsApp-nummers); de data-omzetting van de
      betrokken nummers draait via een SQL-blok met preview.
- [x] **Doel-regel vastgelegd** - GEBOUWD (migratie 061): het doel mag
      nooit herhalen wat platform of gebruikt-voor al zegt. Categorie
      "WhatsApp" heet voortaan "Klantencommunicatie"; "Spoofing" blijft
      juist (Mehdi: wie spoofing nergens ziet staan begrijpt het nummer
      niet). Doel-veld blijft bestaan - besloten na de AI-adviesvraag.
- [x] **Inactieve Octopus-relaties zichtbaar** - GEBOUWD: de actief-vlag
      zat al in Joan's export (migratie 056); het leverancier-paneel toont
      inactieve relaties nu grijs met label "inactief (historiek)" i.p.v.
      als verwarrend duplicaat (het Unabo-geval bij Mega: Octopus maakt
      bewust een nieuwe relatie aan bij bv. een bankrekeningwijziging).
- [ ] **Joan levert de lijst duplicate/inactieve relatie-ID's** - deels al
      afgedekt door de actief-vlag in de export; de lijst is de dubbelcheck.
- [x] **Rest van Joan's Octopus-pakket verwerkt** - GEBOUWD (2026-07-08):
      dagboek-structuur per firma (8 screenshots), grootboek-analyses en
      het voorbeeld-facturatievoorstel (eigen nummerreeks, percentage-
      facturatie, dossiernummer als koppelsleutel, L-dagboeken bij EE)
      samengevat in docs/octopus-dossier.md. Transactie-dagboeken (32
      PDF's) bewust geparkeerd tot de Octopus-API er is.
- [x] **Dashboard-template-document** - GEBOUWD: docs/DASHBOARD-TEMPLATE.md,
      bindend voor iedereen die een dashboard bouwt (besluit Mehdi + Siyan:
      template-document i.p.v. knowledge-document); als referentie mee te
      geven aan elke Claude Code-sessie.
- [ ] **Siyan's sales-blueprint omzetten** naar het template en koppelen
      aan de organisatiedata (naam-matching: Joey, Shilton, ...); zijn werk
      wordt niet weggegooid, de blueprint is het vertrekpunt.
- [ ] **Inkt-levering natrekken** (actie Shaniel; volgens de mail geleverd).
- [x] **Leveranciers-inventaris telefonie afgerond** (2026-07-08, avond):
      Mega digitaal af (5 nummers compleet incl. spoofing-firma's), Proximus
      af (5 actief volgens prive-patroon; 29 vervallen correct leeg),
      Close Call sluit op de euro op de factuur aan (38 unieke actieve
      nummers a 2 euro + 3 spoofing-kostregels = 41; duplicaat-record
      053 89 53 75 samengevoegd; 26 users a 9 euro zit in de
      licentie-spiegel, niet in het nummer-register). Fysiek restwerk:
      sim-foto's + PIN/PUK voor de 5 Mega- en 5 Proximus-sims.
- [ ] **Vragen voor Mehdi (Close Call-restjes)**: (a) zijn Enstaco (3
      nummers), HDS, MEDIAN en Techpoint eigen handelsnamen die als firma
      in kern.firma horen, of externe partijen? (b) horen "Coldcalling -
      Energy" en "EPB & VENT - Tech" bij Energie Efficient? (geen
      naam-gokken, expliciet bevestigen). (c) op de eerstvolgende
      Close Call-factuur checken of 03 375 62 81 (Unused/Archive Anjeza,
      Niet-actief) nog gefactureerd wordt - zo ja: 2 euro/mnd voor een
      archiefnummer, opzeggen.

## Meeting Mehdi 2026-07-08 (dashboard-review)

> Bron: Fathom-transcript 15 min. Bevestigd door Shaniel 2026-07-08.

- [x] **Naamweergave zonder afdeling** - GEBOUWD (migratie 054): Mehdi,
      Angela en Siyan heten op het medewerkers-dashboard alleen bij hun
      voornaam (data-vlag afdeling_in_naam; graaf en taken-pagina volgen).
- [ ] **Achterstallige datascripts draaien** (verzamelscript geleverd):
      spoofing-vlaggen, 0486-doelen, WhatsApp-verantwoordelijken,
      Mega-factuurgegevens, Mega = fysieke sim. Daarna toont het register
      wat Mehdi in de review miste.
- [x] **Bug-onderzoek verantwoordelijke-namen** - GESLOTEN (2026-07-08):
      diagnose toonde nul niet-gematchte queue-leden; het was de afgeleide
      Xelion-queue die het lege register-veld opvulde. Verzamelscript zet
      de echte verantwoordelijken; geen code-bug.
- [x] **Octopus-pakket van Joan verwerkt** - GEBOUWD (2026-07-08,
      migratie 056 + seed): 2313 relaties uit 8 boekhoudingen en 52
      grootboekregels geimporteerd (idempotent); Proximus/Mega/Close Call
      gekoppeld op BTW-nummer; interne relaties gevlagd; leverancier-paneel
      toont per firma relatie-ID, grootboek en ons klantnummer. Open:
      (a) overige leveranciers verzoenen met kern.leverancier (werkbank:
      de verkenner-filter "leveranciers zonder koppeling"),
      (b) klantendatabase-gesprek met Mehdi nu de kiem zichtbaar is
      (684 HA-klanten in de verkenner), (c) dagboek-screenshots en
      facturatievoorstel-flow zodra de Octopus-API er is (belletje
      uitgesteld).
- [x] **Relatie-verkenner op partij-niveau (XX1-laag)** - GEBOUWD
      (2026-07-08, migratie 058 + partijen-opbouw): kern.partij als
      entiteit met eigen volgnummer (2313 vlakken -> 1829 partijen, 0
      wezen); klant/leverancier zijn rollen; groepering op BTW-nummer,
      zonder BTW op exacte naam (gedocumenteerde aanname). Verkenner
      toont per partij de boekhoud-vlakken met relatie-ID's en ons
      klantnummer; interne partijen linken naar de firma-pagina; de
      interne klant/leverancier-relaties tussen eigen firma's zijn kanten
      in de Second Brain. Herimport-flow: octopus-import-seed en daarna
      partijen-opbouw-seed.
- [x] **Sim-foto's** - GEBOUWD (migratie 055): upload in de geheim-sectie
      (achter de Toon-knop, want PIN/PUK staan op de kaartfoto), client
      verkleint, thumbnails met verwijderknop, opslag in de database dus
      mee in de S3-backup. Rest datawerk: sims fysiek nalopen en PIN/PUK
      plus foto's invullen.
- [ ] **Zoom-naam Mehdi corrigeren** (actie mens: Zoom-profiel hernoemen
      naar "Mehdi", conform de kale-naam-uitzondering van migratie 054).
- [x] **AI-bewaking Zoom-naamconventie** - GEBOUWD (2026-07-08): de Second
      Brain vlagt sprekers in recente transcripts die niet Voornaam
      (Afdeling) of een toegestane kale voornaam zijn, als aandachtspunt.

## Meeting Mehdi 2026-07-07 (avond: spoofing, dubbele kosten, afbouw)

> Bron: Fathom-transcript 19 min. Taken bevestigd door Shaniel 2026-07-07.

- [ ] **0486 33 35 21 bijwerken** (script geleverd): doel-bullet Spoofing
      erbij, xelion_uitgesloten aan (roaming-spoofing vanuit buitenland),
      aandacht-notitie.
- [x] **Meerdere kostregels per nummer** - GEBOUWD (migratie 053, blueprint
      goedgekeurd: optie B nu / A later, per-minuut-regels volwaardig
      zichtbaar): kostenblok met plus-patroon in het detailpaneel,
      register-kolom toont maandtotaal plus per-minuut-tarieven met
      opbouw-hover, leverancier-totaal telt kostregels mee. Adviseur:
      on-demand lijst, opzegtermijn/contract mag harde blokkade zijn
      (fase 2, na het vullen van de spoofing-kosten).
- [x] **Xelion-spoofingkosten** - KLAAR (factuur Close Call 2025-0119):
      2 euro per nummer per maand bevestigd; kostregels op alle drie de
      spoofing-nummers, peildatum 2025-09-01 (duplicaat; recente factuur
      ververst de peildatum). Bijvangst: de factuur telt 41 betaalde
      nummers tegenover 26 actieve in het register plus 26 users a 9 euro:
      munitie voor de houden-of-schrappen-ronde (elk geschrapt nummer =
      2/mnd, elke geschrapte user = 9/mnd).
- [x] **Mega-factuur 1126002490 verwerkt** (2026-07-02): 5 nummers elk
      3,31/mnd excl. BTW, abonnementstype Mega Mobile 5 GB, contract
      onbepaalde duur, peildatum gezet (script geleverd). Juni-verbruik:
      nul belminuten op alle vijf; alleen de WhatsApp-nummers gebruiken
      data.
- [x] **Kostenadviseur fase 2a** - GEBOUWD (2026-07-08, migratie 060):
      deterministische advieslijst op de statistieken-tab (kost zonder
      gebruik = afbouwen, verkeer buiten belarchief of spoofing = navragen,
      dubbele persoonlijke nummers = navragen) met redenering, besparing
      per maand, accepteer/afwijs en append-only log (60 dagen
      onderdrukking). Accepteren van afbouwen zet validatie op Elimineren.
      Fase 2b GEBOUWD (2026-07-08): het advies is **AI-gewogen** (Claude via
      ANTHROPIC_API_KEY in compose), één advies per nummer met de exacte
      kostopbouw (bv. 0486: 21,04 + 2,00 = 23,04); de regels blijven de
      terugval en de bron-badge in de kop zegt welke van de twee je ziet.
      Stille-terugval-bug opgelost met [adviseur]-warnings in de logs; de
      wortel bleek de eigen 60s-timeout terwijl het model op volle
      denkkracht stond (fix: output_config effort low + 120s timeout,
      zelfde patroon als organisatie/ai.py).
- [ ] **Afbouw-kandidatenlijst** (beleidslijn Mehdi, 99-auto's-analogie):
      ongebruikte (persoonlijke) nummers met belstatistieken als
      opzeg-kandidaten voor de houden-of-schrappen-ronde.
- [ ] **GEPARKEERD - transcripts als beslicontext**: Mehdi's
      nummer-gesprekken structureel verzamelen (Plaud-connector nog
      autoriseren) zodat de adviseur leert hoe Mehdi redeneert. Besluit
      volgt achteraf.
- [ ] **Proximus afronden in het dashboard**: openstaande datascripts
      draaien (quick wins + ItsMe + 0486); klantnummer 624745262 bij de
      leverancier vastleggen zodra de leverancier-velden er zijn (wacht op
      Joan's Octopus-aanlevering); Mega-peildatum bij de eerstvolgende
      Mega-factuur.

## Meeting Mehdi + Joan 2026-07-07 (register-verfijning + Octopus-spoor)

> Bron: Fathom-transcript 69 min. Quick wins zijn gebouwd (migratie 051 +
> communicatie-app + datascript); de rest staat hieronder open.

- [x] **Spoofing-nummers tellen niet als Xelion** - GEBOUWD (migratie 051):
      kolom xelion_uitgesloten; vlag telt door in register, statistieken,
      stil-lijst en belvolgorde-spiegel; schakelaar in het detailpaneel.
      Sleutel-analogie Mehdi: een sleutel hebben is niet met de auto rijden.
- [x] **Status "Vervallen"** - GEBOUWD (migratie 051): derde status naast
      Actief en Niet-actief; definitief weg, niet te heractiveren. Eigen
      badge-kleur; datascript zet de vervallen Proximus-reeks om.
- [x] **Abonnementstype per nummer** - GEBOUWD (migratie 051): veld naast de
      kostprijs (bv. Business Mobile Smart), kolom via Mijn view,
      detailpaneel-veld; datascript vult de actieve Proximus-nummers.
- [x] **WhatsApp-datawerk Mega** (datascript): platform WhatsApp op de drie
      WhatsApp-nummers; verantwoordelijken Siyan (Contrax), Shelton (H-A),
      Ashvand (EE); Vlad-verificatie afgerond (aandacht-notitie weg);
      datasim-context (Mehdi's auto + ItsMe Zohreh) vastgelegd.
- [x] **Meerdere doelen per nummer** - GROUNDWORK GEBOUWD (2026-07-07,
      ontwerp Shaniel): plus-knop in detailpaneel en register-cel, elk doel
      een eigen bullet, klik op een bullet bewerkt dat ene doel (leegmaken
      = weg). Opslag in het bestaande doel-veld met "; " als scheiding:
      geen migratie, zoeken/statistieken blijven werken, tellen per doel =
      splitsen. Bij de dropdown-only-slag later evt. naar een koppeltabel.
- [ ] **Ian vragen de Xelion-nummers na te lopen** (actie Shaniel):
      gebruikt-voor en verantwoordelijken per nummer; Mega en Proximus zijn
      door Mehdi zelf gedaan.
- [x] **Octopus API-toegang** - GROTENDEELS BINNEN (2026-07-09/13, verving
      het belletje): Software House ID ontvangen en werkend, keten
      end-to-end bewezen op het testaccount (incl. schrijfrecht), pijplijn
      + verzoening + Financiën-tab live (PLAN stappen 3-6). Rest van G1:
      een productie-gebruiker gekoppeld aan de acht echte dossiers
      (aanvragen bij Octopus of via Joan).
- [ ] **Joan levert aan**: (a) Octopus-terminologie (dagboeken, relatie
      K/L/KL, relatie-ID vs grootboekrekening, grootboeknummers per firma);
      (b) leveranciersinfo Mega/Proximus/Close Call zoals in Octopus, met
      printscreens; (c) relaties-export met ID's (alles; wij filteren
      intern/extern); (d) voorbeeld-facturatievoorstellen (Delivery Notes)
      als PDF met nummer. Joan past ook de Delivery Note-nummering aan
      zodat die niet gelijk loopt met factuurnummers.
      Stand 2026-07-08 (avond): alles uit de zip is verwerkt of bewust
      geparkeerd - (c) relaties + grootboek in de database, (a) dagboeken
      en grootboek-analyses en (d) het voorbeeld-facturatievoorstel
      samengevat in docs/octopus-dossier.md; de transactie-dagboeken
      (PDF's) wachten op de API. Alleen de aangepaste Delivery-Note-
      nummering moet Joan nog doorvoeren.
- [x] **Leveranciers-entiteit uitbouwen met Octopus-velden** - GEBOUWD
      (2026-07-08): het leverancier-paneel in communicatie toont per
      firma-boekhouding het Octopus-relatie-ID, de grootboekrekening en ons
      klantnummer bij de leverancier (kosten.octopus_relatie + de expliciete
      boekhouding-mapping van migratie 059). Dagboeken volgen met de
      Octopus-API (gate G1).
- [x] **Validatie-beeld per leverancier** - GEBOUWD (2026-07-08): het
      leverancier-paneel opent met de verwachte maandfactuur (excl. BTW):
      samenstelling N x abonnementstype a prijs plus kostregels, totaal,
      per-minuut apart als variabel, waarschuwingen bij nummers zonder
      kostprijs en bij een peildatum ouder dan 2 maanden.
- [ ] **Facturatievoorstel-workflow** (na de Octopus-koppeling): geen
      facturen vooraf of proforma (BTW); voorstellen klaarzetten per
      projectdeel, dupliceren per fase, delivery-note-nummer als unieke
      link naar dashboard/Monday met activeer-knop; test met
      1-cent-voorstellen intercompany.
- [ ] **WhatsApp-nummer voor Angela** regelen en registreren.
- [ ] **VERRE TOEKOMST**: domiciliering terug zodra het validatie-framework
      staat (betaalwerk Angela vervalt); AI-verificatie van facturen buiten
      Peppel (fraudegevoelig); KBC-koppeling onderzoeken; MacMini/VM-opzet
      voor meerdere WhatsApp-nummers (expliciet geparkeerd tot dit stuk af
      is).

## Meeting Mehdi 2026-07-06 (tweede, Mega/Proximus-opschoning)

> Bron: Fathom-transcript 2 + Proximus-factuurscreenshot (Shaniel).
> Regel: per provider alleen de genoemde nummers Actief; de rest Niet-actief.
> Telesur BLIJFT zoals hij staat (expliciete uitzondering).

- [x] **Mega: 5 actieve nummers** - VERWERKT (2026-07-06): register had ze
      alle vijf al Actief; doelen aangevuld (0491 94 68 78 = Whatsapp
      Contrax, 0491 94 68 79 = Whatsapp H-Architects) en prijstype per
      maand gezet. Peildatum nog leeg tot er een Mega-factuur naast ligt.
- [x] **Proximus-opschoning** - VERWERKT (2026-07-06): 3 factuurnummers
      Actief met kostprijs 21,04/mnd en peildatum 2026-07-06 (Catalin,
      Mehdi, Stefan); 30 overige op Niet-actief; Telesur ongemoeid.
      Mehdi schaft de inactieve lijnen op het Proximus-portaal af.
- [x] **Factuur 7604078875 (9 jun 2026) volledig verzoend met het register**
      (2026-07-06): 5 actieve Proximus-nummers, elk 21,04/mnd excl. BTW,
      peildatum 2026-06-09. Vlad-rij gecorrigeerd (0467 54 41 25 bestond
      niet bij Proximus, is 0465 54 41 25); 0471 54 50 77 toegevoegd als
      vermoedelijke datasim (67 GB, geen gesprekken). Twee kleine
      verificaties staan als aandacht-notitie op de nummers zelf:
      naam Vlad bevestigen en uitzoeken welk apparaat de datasim voedt.
- [ ] **Xelion: houden-of-schrappen-ronde** met Mehdi - VOORBEREIDING
      GEBOUWD (2026-07-07): kandidatenlijst op de statistieken-tab met
      maandkost, 90-dagen-gebruik, factoren (WhatsApp/ItsMe/datasim) en
      de validatie-knoppen direct in de lijst. Rest: de ronde zelf met
      Mehdi doorlopen en beslissingen zetten.

## Meeting 2026-07-03 (communicatie-review, met Siyan/Angela)

- [x] **Leverancier/platform: échte detailpagina's** i.p.v. alleen filteren - GEBOUWD
      (2026-07-03): klik op leverancier/platform opent nu een detailpaneel (zelfde
      drawer als nummer/firma). Leverancier: alle nummers + totale vaste maandprijs +
      software-abonnementen en werkelijke facturen uit het kosten-schema (migratie 027
      geeft de communicatie-rol read-only op kosten). Platform: nummers + leveranciers
      die het leveren. Filteren blijft kunnen via de knop ín het paneel; deep-links
      `#leverancier=`/`#platform=`. ⚠ Open verfijning - RBAC: "toont niet alles aan
      iedereen" (Mehdi) - rechten per sectie, oppakken zodra het RBAC-per-tab-principe
      (architectuurpunt hierboven) vorm krijgt. Facturen/contracten in het paneel
      volgen met Factuurrouter 2.0.
- [x] **Definitie "verantwoordelijke" generiek gemaakt** - GEBOUWD (2026-07-04,
      migratie 036): nieuwe sleutel verantwoordelijke_nummer ("Verantwoordelijke
      voor nummer", met de belvolgorde-uitleg) voor de telefonie-kolom; de
      algemene term is nu generiek (accountable, precies een, per resource
      anders ingevuld). Was ook het verzoek "hernoem de kolom". Origineel punt:
      de huidige definitie is telefoonlijn-specifiek ("altijd de 1e in de
      belvolgorde") terwijl de term over álle dashboards hetzelfde moet betekenen.
      Fix: generieke definitie (aanspreekbaar/eigenaar, accountable, precies één);
      de belvolgorde-uitleg verhuist naar een eigen sleutel voor de telefonie-kolom
      (bv. "verantwoordelijke van de telefoonlijn" of kolom hernoemen naar "eerste
      in de rij" - met team kortsluiten welke van de twee).
- [x] **Filter op persoon + positie in de belvolgorde** - GEBOUWD (2026-07-03):
      "In belvolgorde"-filter (persoon-dropdown + positie 1e t/m 6e) in Communicatie.
- [x] **"Behouden"-kolom + nummer-validatie** - GEBOUWD (migratie 026): kolom
      Behouden (behouden/verifiëren/elimineren, inline te zetten door editors,
      database-constraint bewaakt de waarden) + Validatie-filter; in de
      standaardview. Rest: het team laten valideren (92 → 41; Proximus-lijst als
      referentie; elimineren pas ná verificatie).
- [ ] **Toolmaster-opname → transcript** (Shaniel): de demo-opname downloaden en
      transcriberen - input voor het draaiboek-spoor.
- Team (geen bouwwerk van Shaniel): **Pipedrive-sanering** (Siyan + Fable):
      velden/labels fout opgezet; eerst deep-search naar Pipedrive-mogelijkheden,
      dan aanpassen in een **sandbox** (advies van Claude zelf), UNABO + TKN;
      deadline di (TKN-meeting). **Sales-dashboard** (Siyan, Pipedrive-MCP) loopt.
      **Curatie vóór agents** (Mehdi): eerst 2-3 mensen met kennis de data goed
      laten zetten; agents pas als er genoeg inzicht/data is.

## Meeting 2026-07-03 (vermogen-walkthrough) - adressen, kostenplaats, kennisbank

> Adres-autocomplete uit deze meeting is GEBOUWD (Photon, vermogen + draaiboek).
> Nieuwe punten:

- [x] **Adres als gelinkte entiteit ("blauw")** - GEBOUWD (migratie 025):
      `kern.adres` met dedup + vind-of-maak-functie; firma/pand/dossier gekoppeld
      (adres_id); adres- én pand-knopen in de Second Brain met relaties ("gevestigd
      op", "op adres", "eigendom van"); firma-adresveld in het Organisatie-dashboard
      met autocomplete; bestaande adressen gebackfilld. Rest: (a) adres klikbaar in
      de lijstweergaven (nu alleen in de graph + detail), (b) gestructureerde delen
      (postcode/gemeente) uit Photon opslaan i.p.v. alleen de weergavetekst.
- [ ] **Adres → kostenplaats automatisch koppelen**: de maandelijkse kost van een
      pand vloeit automatisch naar de kostenplaats van de vennootschap ("hoeveel cash
      per maand nodig"). Koppelt aan het kosten-schema + de verwacht-vs-werkelijk-lijn.
- [ ] **Firma-adressen ↔ panden integreren** (Mehdi, "één centraal dashboard"): bijna
      alle firma-adressen zijn eigen panden/eigendommen (op één contract na). De
      firma-adressen moeten linken naar het vermogen-dashboard i.p.v. los te staan.
      Sluit aan op de ARCHITECTUUR-beslissing (één dashboard) hierboven.
- [ ] **Privé-eigendom-sectie + HR-koppeling**: een privé-pand (bv. van Mehdi) hoort
      onder de persoon te verschijnen, gelinkt aan HR ("over HR wil je alles weten").
      Wacht op de HR-laag; privacy/RBAC goed regelen (privé ≠ voor iedereen zichtbaar).
- [ ] **GitHub-repos → organisatieportaal / Second Brain-kennisbank**: alle repos
      zichtbaar maken in het portaal zodat collega's weten waar dingen staan en wat er
      te doen is - continuïteit als iemand uitvalt (Shaniel: "worst case, ik val een
      week weg"). Rechten: niet iedereen ziet alles. (De TODO/CLAUDE.md zijn al
      AI-leesbaar via GitHub; dit maakt het ook mens-leesbaar in het portaal.)
- Team/persoonlijk (geen bouwwerk): **Fathom-accounts voor de collega's** aanmaken;
  Mehdi's **persoonlijke** Fathom bewust NIET linken (privé-gesprekken); **naam-meeting**
  met de andere leden inplannen; Mehdi levert de definitieve **pand-kolommenlijst**.
- ~~⚠ Attentie - aantal disciplines wisselt~~ - **OPGELOST (2026-07-04)**: Mehdi
  heeft de lijst vastgepind op **17 disciplines mét namen** (zie "Unified Dashboard
  - instructies Mehdi" bovenaan). Bedrijven blijven de variabele laag (±15).

## Meeting 2026-07-02 (avond) - woordenboek, vermogens, agenda
- [x] **DEFINITIEBOEK zichtbaar op de dashboards** - GEBOUWD voor Communicatie
      (migratie 015): `kern.definitie` is de machinebron; kolomkoppen, tooltips,
      kolomkiezer, Woordenboek-knop en Excel-export lezen eruit. Terminologie
      doorgevoerd: "Intern gefactureerd aan" / "Interne doorfacturatie naar".
      Ook in het **Organisatie-dashboard** (migratie 017): ⓘ Woordenboek-pagina,
      tooltips op kolomkoppen en op de Second Brain-typefilters. **Beheer-UI
      gebouwd** (migratie 020): bewerken/toevoegen op de woordenboek-pagina,
      alleen voor `WOORDENBOEK_EDITORS` (mehdi + akadmin). Rest: DEFINITIEBOEK.md
      handmatig in sync houden bij wijzigingen.
- [ ] **Verbruik op het kosten-dashboard** (actiepunt): usage per software naast
      prijs/seats, zodat houden-of-schrappen en jaarlijks-vs-maandelijks
      **datagedreven** wordt (jaarcontract voor zekere zaken zoals Zoom, maandelijks
      voor onzekere). AI bewaakt continu de kostenstructuur ("dat kun je schrappen").
      Facturatiecyclus per software verschillend - veld `billing_cycle` bestaat al.
- [x] **Vermogens-dashboard (skelet)** - GEBOUWD (repo `globaal-vermogen`, §14.6;
      migratie 016): vier tabs met elk hun eigen aanpasbaar skelet, alles gelinkt
      aan kern.firma en onderling (pand ↔ lening/verzekering/syndicus). Rest:
      (a) VM-installatie (rol, .env, tegel, cron), (b) Mehdi in `vermogen-editors`
      + Claude Code-toegang voor skelet-aanpassingen, (c) data laden (Mehdi),
      (d) vervaldatum-signalen (verzekering/huurcontract) in de Second Brain.
- [ ] **Firma-agenda** (actiepunt): centrale agenda met alle vervaldatums (contracten,
      opzegtermijnen, verzekeringen, syndicus-jaarvergadering), eigenaar per event,
      reminders; rolverduidelijking (wie is verantwoordelijk voor leningen/leasingen/…).
      Sluit aan op het bestaande TODO-punt contract-entiteiten + briefing-signalen.
- [ ] **Klantdossier & templates** (actiepunt, later): tab per klant (documenten,
      contract, getekende offerte, communicatie) + AI-opvolging; project-templates
      (bv. "EPB renovatie") i.p.v. telkens opnieuw; e-mailkoppeling (info@ →
      systeem stelt acties voor); uiteindelijk **klantenportaal** op eigen subdomein
      (Proximus-model: verbruik/contract/vragen). Monday blijft voor specifieke doelen.
- [x] ~~Screen-monitoring collega's~~ - afgewezen voor nu: eerst waarde uit
      applicatiedata halen, geen extra kosten.

## Organisatie-dashboard & AI (vervolg op graph v1)
- [ ] **Facturatie-terminologie** vastleggen (DEFINITIEBOEK-aanvulling): gefactureerd-aan
      (= Unabo) / doorfactureren-naar / **gebruikt-voor** (gebouwd, migratie 013);
      nog: betaald-door, **doorfactureerbaar ja/nee + basis** (maandelijks / vast bedrag /
      percentage / effectief); leverancier ≠ platform. Let op: naamgeving wijzigt naar
      "intern gefactureerd" (zie meeting-blok hierboven).
- [ ] **Xelion-API - TOEGANG BINNEN (2026-07-03, via Siyan)**: Siyan stuurt de
      inlog + documentatie-link naar Shaniel. Acties: (a) documentatie downloaden
      en doornemen - let op: de API oogt write-heavy (change/create/set, "nergens
      import"), dus eerst uitzoeken wat er te LEZEN valt; (b) verbinden en zo veel
      mogelijk data binnenhalen (belstatistieken per nummer: in/uit, gemist,
      minuten, wie opnam); (c) **hele belvolgorde-queue (persoon 1/2/3…) op het
      dashboard** én via de API kunnen AANPASSEN ("Joey is ziek → wie neemt over"
      zonder via Siyan te gaan); (d) daarna Monday-doorkoppeling per project.
      De screenshots-workaround vervalt zodra dit loopt.
- [ ] **AI-factuurgoedkeuring = Factuurrouter 2.0** (meeting 2026-07-02, bevestigd
      2026-07-03): GEEN nieuwe app - de bestaande Factuurrouter (§6A:
      scanfacturen@gmail.com → OCR → AI herkent firma → routeert; review-dashboard
      voor twijfel) uitbreiden ("paar extra lagen", Mehdi) met:
      (1) **goedkeuringstoets** "goed om te betalen?" tegen verwacht (kosten
      seats × prijs + communicatie vaste_prijs + charge_actual-historiek);
      (2) **contract-check**: hebben we een contract, matcht de factuur dat contract?;
      (3) **prijswijziging-detectie** → ons op de hoogte stellen bij veranderde prijzen;
      (4) **dashboards automatisch bijwerken** met de nieuwe prijzen zodat we
      beslissingen kunnen nemen; niet goedgekeurd → escalatie Mehdi/Angela via het
      bestaande review-patroon; goedgekeurd → charge_actual-rij + prijs-update.
      Nodig: db-koppeling voor de router (leesrol + smalle schrijfrol); contract-
      entiteit (zie kern-uitbreiding); beslispunt bij bouw: gpt-5-mini houden of
      migreren naar de Claude API (één AI-lijn in het platform).
- [ ] **Gespreksopname-transcriptie** (meeting 2026-07-02): opnames uit Xelion
      downloaden → transcriberen → aan het dossier/de communicatie hangen (het
      gemeente-Leuven-ideaal). GDPR eerst regelen: opnamemelding in de wachtrij
      (Siyans punt).
- [ ] **Contactenlijst → projecten → firma's**: wacht op de Excel van de leverancier
      (bij Siyan belegd); elke contact linken, dan projecten, dan Monday.
- [ ] **Gebruikersabonnement-kost telefonie** (Close Call-factuur 2025-0119): naast
      € 2,00/nummer (in `vaste_prijs`) rekent Close Call € 9/8/7 per *gebruiker*
      (staffel 1-10 / 11-20 / 21-35) - dat is € 212 van de € 292 vaste maandkost en
      hangt aan personen, niet aan nummers. Aparte registratie nodig (per persoon of
      als firmakost) vóór de doorfacturering per firma kan kloppen. Belminuten
      (± € 23/maand) zijn variabel en blijven buiten `vaste_prijs`.
- [ ] **Documenten koppelen aan de graph** (bv. testresultaten per collega over meerdere
      jaren) → AI-vragen als "wie is het meest geschikt voor deze taak", trends
      (groei/demotivatie).
- [ ] **Fathom-integratie**: meeting-transcripts als AI-bron ("lezen of we goed bezig
      zijn"); Gullok toegang tot Fathom geven.
- [ ] **Nieuwe entiteiten** in kern + graph: klanten, diensten, contracten (leveranciers
      bestaan al) - met vervaldatums + opzegtermijnen. Zodra aanwezig: regel
      "vervalt < 90 dagen" → signaal → de **dagbriefing** adviseert (laag 3 van de
      proactieve AI; het verzekerings-voorbeeld van Mehdi).
- [ ] **Briefing per WhatsApp** versturen (laag 2½ - het duwtje dat je opzoekt;
      toekomst, expliciet geparkeerd).
- [ ] **RBAC verfijnen**: wie ziet welk deel van het dashboard (nu: admin/manager alles).

## Second Brain (meeting 2026-07-02, Mehdi)
- [x] **Finalisatie-status + kleurcodering** - GEBOUWD (migratie 018): toggle
      "Finalisatie" in de Second Brain (blauw = gefinaliseerd, rood = nog niet),
      markeer/terugdraai-knop op de knoopkaart, append-only historie met wie +
      wanneer. Rest: team laten finaliseren (curatie).
- [ ] **17-disciplines-structuur** (hybride model uit de deep-research; document van
      Mehdi) als laag in de Second Brain - per firma, afwijkingen expliciet, lege
      disciplines onzichtbaar.
- [x] **KBO-koppeling + jaarrekeningen** v1 - GEBOUWD (migratie 018):
      `kern.firma.kbo_nummer` + op het firma-detail directe links naar KBO Public
      Search en de NBB-jaarrekeningen (Balanscentrale). Rest: (a) KBO-nummers van
      de 13 firma's invullen (beheer-formulier), (b) later API-verrijking
      (NBB CBSO-API voor jaarrekening-data in het dashboard zelf).
- [ ] **E-mail- en telefonie-statistieken via API's** (aantallen, spam, gemiste calls,
      wie neemt op) - voorwaarde voor de communicatie-coach-rol; principe: levende
      data, nooit handmatig.
- [ ] **Onderzoek beste bestaande tools per discipline** (marketing/sales/HR… met AI)
      - wij bouwen ze niet, wij verbinden ze (integrator-rol).
- [ ] **Structuurskelet + invoerinstructies** voor Mehdi/Angela/Sian zodat het team
      zelf data invult, parallel aan het bouwen.
- [ ] **Governance-signalering**: systeem merkt als binnengekomen data over een
      collega gedeeld hoort te worden met betrokkenen; RBAC verder verfijnen.
- [x] **Naamgeving**: organisatiegraaf heet voortaan **Second Brain** (2026-07-02).

## Onderzoek (vóór bouwen)
- [ ] **Streamlit als labo/view-laag** - VOORONDERZOEK GEDAAN (2026-07-04):
      geschikt als snelle, read-only view-laag (past op het principe "views
      slaan nooit op"): labo-app op de portal-rol achter forward-auth
      (websocket-proxying in nginx-template; username uit X-Authentik-header
      via st.context.headers). NIET voor de CRUD-dashboards of de pijplijn.
      Concreet inzetten bij PLAN.md stap 6 als prototype van de finance-views;
      bewezen views promoveren naar het echte dashboard. PoC: container +
      nginx-template + één spend-view.
- [ ] **Movetex.com** onderzoeken: planning-algoritme (Fati gebruikt het). Doel: 4
      planningen (Matthias/Mathieu/Shilton/Luc) → 1 planningtool. Géén eigen bouw -
      bestaand pakket koppelen via API; Monday blijft alleen visueel.
- [ ] **17 disciplines** deep-research (via Claude) - **BESLIST 2026-07-03: ÉÉN
      dashboard, geen 17 losse** ("anders is onze brain verspreid"). Rest: per thema/tab
      een eigen deep-search → tab/subtab-structuur die op alle 15 firma's toepasbaar is.
      De 17 = referentiekader (auto-analogie: je ziet wat je mist), niet in beton.

## Data & beheer
- [x] **Governance laag 1** - GEBOUWD (2026-07-03, migratie 023 + GOVERNANCE.md):
      audit-trail via triggers (kern.audit: wie/wanneer/oud/nieuw, append-only,
      geheim = metadata-only) + kern.data_domein (8 domeinen). Rest:
      (a) **eigenaars toewijzen** (Shaniel + Mehdi/collega's), (b) kwaliteitsmetriek
      per domein in de dagbriefing, (c) restore-test inplannen (kwartaalritme),
      (d) toegangsreview Authentik-groepen (periodiek), (e) app.gebruiker-doorgifte
      in communicatie (Node/Knex; Flask-apps + audit_overzicht-view GEDAAN,
      migratie 024).
- [ ] **Group-based toegang via Authentik Blueprints** - plan vastgesteld
      2026-07-07, zie `docs/plan-groepstoegang-blueprints.md`. Per app
      `app-{naam}-read`/`-edit`; groep `manager` verdwijnt, `admin` op termijn
      ook; akadmin = break-glass. Eerste stap: inventarisatie draaien
      (`sh scripts/ak-exec.sh scripts/inventariseer-groepen.py`) en de
      hertoewijzing per persoon laten goedkeuren. Uitvoering pas na akkoord.
- [ ] **Data-curatie Communicatie** (Siyan): doorfactuur-firma's, afdelingen, doelen en
      belvolgorde-queues invullen; oude records actief/niet-actief zetten.
- [ ] **Close Call afletteren**: factuur 2025-0119 telt 41 telefoonnummers, het register
      heeft er 40 onder Close Call BV - één Xelion-nummer ontbreekt of zit fout onder
      Proximus/Telesur. Nummerbijlage bij Close Call opvragen en vergelijken. (Mega is
      wél sluitend: 5 op factuur 1126002031 = 5 in register, à € 3,31 excl.)
- [ ] **Verantwoordelijken toewijzen** op nummers en e-mailadressen (team).
- [ ] **kosten.firma → kern.firma** verzoenen - brug ligt er (migratie 012:
      `kern_firma_id` + leverancier-links + trigger); rest: (a) niet-gematchte
      firma's handmatig koppelen (Second Brain meldt ze), (b) prijzen/seats van de
      66 vendors vullen (factuur voor factuur), (c) creditcard-afschriften →
      `charge_actual` voor verwacht-vs-werkelijk, (d) uiteindelijk text-id's weg
      samen met de host-app (`globaal-kosten`).
- [ ] Ontbrekende HR-nummers/familienamen/e-mails in kern.persoon aanvullen.

## Techniek / hygiëne
- [x] **CLAUDE.md-dekking compleet** (2026-07-03): de host-app-repo's (kosten,
      factuurrouter, stagebeoordeling, schuldentracker) hádden al een eigen
      CLAUDE.md; verouderde deploy-beschrijvingen (kosten/stagebeoordeling)
      geactualiseerd naar de cron-auto-deploy en overal een verwijzing naar de
      stack-werkafspraken toegevoegd. Overzichtstabel (incl. PR-vs-directe-push-
      workflow per repo) staat in CLAUDE.md van deze repo. (telefoonregister:
      bewust géén - collega.)
- [ ] **Telefoonregister-repo**: branch `claude/ecstatic-feynman-wctpk1` → `main`
      verzoenen (zelfde recept als appportal-drift).
- [x] **Communicatie eigen repo + auto-deploy** - gedaan 2026-07-02
      (`softwareglobaal/globaal-communicatie`, subtree-split + cron).
- [x] **Off-site backups naar S3** - LIVE sinds 2026-07-03. Bucket
      `globaal-db-backups-2026` (us-east-1, lifecycle 30 dgn, block-public-access),
      upload-only IAM-user `backup-uploader` (`backup-upload-only`-policy). VM: AWS
      CLI v2 (officiële installer - apt-pakket ontbrak), gnupg, `~/.backup-passphrase`
      (chmod 600, kopie in wachtwoordkluis), `S3_BACKUP_BUCKET` in .env. Testrun OK:
      beide dumps GPG-versleuteld naar S3. Loopt automatisch mee in de 03:15-cron.
      Setup-checklist: `docs/offsite-backup-setup.md`.
