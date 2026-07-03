# To-do — AppPortal / Organisatie / Communicatie

> Parkeerlijst van afgesproken maar nog niet gebouwde zaken. Bron: Zoom-meetings
> 2026-07-01 t/m 2026-07-03 + lopende afspraken. Afvinken of verplaatsen bij oppakken.

## ★ EINDDOEL — Eigen draaiboek-platform (meeting 2026-07-03, Mehdi)

> **Noordster, niet nu bouwen.** Visie: een eigen **draaiboek-(playbook-)management**
> in onze eigen dashboards, zodat die dé *source of truth* worden — als vervanging
> van **Toolmaster** (~€70/gebruiker/maand ≈ €3.000/mnd bij 20-30 mensen) en als
> aanvulling waar **Monday** tekortschiet. Kernonderscheid dat Mehdi maakt:
> **projectmanagement** (Monday: 100 projecten op grove lijnen; kan géén deeltaken/
> micromanagement — een EPB-proces met ~200 stappen blokkeert) vs. **draaiboek**
> (het *protocol/playbook* van één proces: alle fases + deeltaken, van A→Z zonder
> fouten). Een draaiboek legt het proces vast → maakt automatisering mogelijk →
> levert data op. Uiteindelijk óók verkoopbaar aan partners (€70/gebruiker-model).

- [ ] **Deep-research Toolmaster + Monday** (Mehdi vraagt dit expliciet): wat doen ze,
      waar zitten de limieten (Monday: geen deeltaken/playbook; Toolmaster: duur +
      je betaalt voor maatwerk dat ze daarna gratis aan iedereen aanbieden). →
      feature-matrix + wat we naboetsen en waar we verder gaan.
- [x] **Terminologie in het DEFINITIEBOEK** — GEDAAN (migratie 021): draaiboek,
      projectmanagement, fase, stap, run in `kern.definitie` + DEFINITIEBOEK.md.
- [ ] **Datamodel: draaiboek-schema** — **v2 TER REVIEW** (Mehdi/Shaniel):
      **`docs/ontwerp-draaiboek-datamodel.md`**, verfijnd met de deep-research
      van 2026-07-03. 10 tabellen: dossier→runs (VC-ontwerp + -verwezenlijking),
      kickoff-formulier + conditie-regels (adaptief klein/groot), snapshots,
      append-only log, stap-soorten incl. goedkeuring. MVP-inhoud (VC-flow,
      KB 25/01/2001) staat erin. 4 beslispunten onderaan het doc; daarna
      migratie 022 + MVP-skelet (repo `globaal-draaiboek`). NB uit de research:
      Toolmaster-€70-claim ONBEVESTIGD (enige €70 = support-uurtarief) → echte
      offerte vragen; documentgeneratie VGP/PID = fase 2 (dé vervanger).
- [ ] **MVP: veiligheidscoördinatie** — start klein (eenvoudige, kleine projecten):
      één draaiboek volledig end-to-end uitwerken als bewijs van concept.
- [ ] **Sequentieel geheugen ("waar staan we")** — lost het verslagen-probleem op:
      het draaiboek houdt bij welke fase/verslag af is, zodat mens én AI weten
      "verslag 2 klaar → volgende is 3". Het draaiboek wordt de projectvoortgang-bron
      die AI nu mist.
- [ ] **Fathom → deeltaken** (Shaniel): nu Fathom gelinkt is, kleine taken uit meetings
      automatisch in kaart brengen en aan draaiboek-stappen koppelen.
- [ ] **Automatisering op het draaiboek**: zodra het proces vastligt — trigger-acties
      ("stap af → mail → bij antwoord → volgende stap"). Precies wat Monday niet kan.
- [ ] **Document-gedreven / adaptief draaiboek**: AI leest een plan/document met de
      logica van (bv.) veiligheidscoördinatie en genereert/past het draaiboek aan —
      kleine gezinswoning = weinig stappen, groot project = meer. (Document-generatie
      zelf is een apart spoor.)
- [ ] **Adoptievoorwaarde**: iedereen (20-30) moet het gebruiken, anders geen data —
      UX + toegang op orde; kostenbesparing t.o.v. Toolmaster expliciet maken.
- [ ] **Commercialisering (lange termijn)**: draaiboek-product aan partners aanbieden —
      pas ná intern bewezen.
- [ ] **Directe actie-items uit de meeting**: (a) Ashwent's Toolmaster-account upgraden
      → dan samen met Shaniel de veiligheidscoördinatie-playbook opzetten om van te
      leren; (b) dashboard-review met Ivor inplannen.

## Meeting 2026-07-03 (dashboard-review + architectuur)

> Draaiboek-einddoel door Mehdi **bevestigd** ("Dat is het"). Nieuwe punten:

- [x] **Platform + leverancier klikbaar maken** in Communicatie — GEBOUWD
      (2026-07-03): beide kolommen blauwe links; klik = **filtert de lijst** op die
      waarde (toggle: nogmaals = uit). Platform kreeg dezelfde filter-infra als
      leverancier (distinct platforms via `/api/refs`, chip-rij, serverfilter). Een
      rijker leverancier-kostenoverzicht bij de klik = natuurlijke vervolgstap
      (koppelt aan "verbruik op kosten-dashboard").
- [ ] **ARCHITECTUUR — één dashboard, niet 17** (Mehdi, beslist): NIET 17 losse
      dashboards. Eén dashboard, **15 bedrijven**, met tabs + subtabs; **per firma
      filteren** (zoals boekhouding: één dashboard, kies de firma). **RBAC per tab via
      login** — wie iets niet hoeft te zien, ziet het niet. **Cross-firma rollup**:
      "alle firma's" → geld binnen/uit per maand, welke firma bracht het meeste op /
      kostte het meeste. (Structureel principe voor álle toekomstige dashboards.)
- [ ] **Xelion-data via screenshots** (ACTION ITEM — workaround voor de ontbrekende
      API): Shaniel maakt screenshots van álle Xelion-tabs → Claude extraheert de data
      → in het dashboard, zodat we up-to-date data hebben om beslissingen op te nemen.
      Overbrugt de geparkeerde Xelion-API-blocker tot die er eventueel komt.
- [ ] **Woordenboek-definities samen aanscherpen** (Mehdi + Shaniel, als er tijd is):
      de AI-gegenereerde definities nalopen en verscherpen via de beheer-UI. (Definitie
      "vaste prijs" al bevestigd: vast maandbedrag, excl. BTW, per resource.)

## Meeting 2026-07-02 (avond) — woordenboek, vermogens, agenda
- [x] **DEFINITIEBOEK zichtbaar op de dashboards** — GEBOUWD voor Communicatie
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
      Facturatiecyclus per software verschillend — veld `billing_cycle` bestaat al.
- [x] **Vermogens-dashboard (skelet)** — GEBOUWD (repo `globaal-vermogen`, §14.6;
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
- [x] ~~Screen-monitoring collega's~~ — afgewezen voor nu: eerst waarde uit
      applicatiedata halen, geen extra kosten.

## Organisatie-dashboard & AI (vervolg op graph v1)
- [ ] **Facturatie-terminologie** vastleggen (DEFINITIEBOEK-aanvulling): gefactureerd-aan
      (= Unabo) / doorfactureren-naar / **gebruikt-voor** (gebouwd, migratie 013);
      nog: betaald-door, **doorfactureerbaar ja/nee + basis** (maandelijks / vast bedrag /
      percentage / effectief); leverancier ≠ platform. Let op: naamgeving wijzigt naar
      "intern gefactureerd" (zie meeting-blok hierboven).
- [ ] **Xelion-belstatistieken** (meeting 2026-07-02, prioriteit): dagelijkse sync
      (einde van de dag) via de Xelion-API — per nummer inkomend/uitgaand,
      opgenomen/gemist, belminuten, wie opnam → kolommen + statistiek in Communicatie
      ("welke nummers zijn hun geld waard"). Eerst uitzoeken: API-toegang via
      Close Call BV. Daarna doorkoppeling van communicatiestatistiek per project
      naar **Monday** (projectverantwoordelijke ziet de communicatie).
- [ ] **AI-factuurgoedkeuring = Factuurrouter 2.0** (meeting 2026-07-02, bevestigd
      2026-07-03): GEEN nieuwe app — de bestaande Factuurrouter (§6A:
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
      (staffel 1-10 / 11-20 / 21-35) — dat is € 212 van de € 292 vaste maandkost en
      hangt aan personen, niet aan nummers. Aparte registratie nodig (per persoon of
      als firmakost) vóór de doorfacturering per firma kan kloppen. Belminuten
      (± € 23/maand) zijn variabel en blijven buiten `vaste_prijs`.
- [ ] **Documenten koppelen aan de graph** (bv. testresultaten per collega over meerdere
      jaren) → AI-vragen als "wie is het meest geschikt voor deze taak", trends
      (groei/demotivatie).
- [ ] **Fathom-integratie**: meeting-transcripts als AI-bron ("lezen of we goed bezig
      zijn"); Gullok toegang tot Fathom geven.
- [ ] **Nieuwe entiteiten** in kern + graph: klanten, diensten, contracten (leveranciers
      bestaan al) — met vervaldatums + opzegtermijnen. Zodra aanwezig: regel
      "vervalt < 90 dagen" → signaal → de **dagbriefing** adviseert (laag 3 van de
      proactieve AI; het verzekerings-voorbeeld van Mehdi).
- [ ] **Briefing per WhatsApp** versturen (laag 2½ — het duwtje dat je opzoekt;
      toekomst, expliciet geparkeerd).
- [ ] **RBAC verfijnen**: wie ziet welk deel van het dashboard (nu: admin/manager alles).

## Second Brain (meeting 2026-07-02, Mehdi)
- [x] **Finalisatie-status + kleurcodering** — GEBOUWD (migratie 018): toggle
      "Finalisatie" in de Second Brain (blauw = gefinaliseerd, rood = nog niet),
      markeer/terugdraai-knop op de knoopkaart, append-only historie met wie +
      wanneer. Rest: team laten finaliseren (curatie).
- [ ] **17-disciplines-structuur** (hybride model uit de deep-research; document van
      Mehdi) als laag in de Second Brain — per firma, afwijkingen expliciet, lege
      disciplines onzichtbaar.
- [x] **KBO-koppeling + jaarrekeningen** v1 — GEBOUWD (migratie 018):
      `kern.firma.kbo_nummer` + op het firma-detail directe links naar KBO Public
      Search en de NBB-jaarrekeningen (Balanscentrale). Rest: (a) KBO-nummers van
      de 13 firma's invullen (beheer-formulier), (b) later API-verrijking
      (NBB CBSO-API voor jaarrekening-data in het dashboard zelf).
- [ ] **E-mail- en telefonie-statistieken via API's** (aantallen, spam, gemiste calls,
      wie neemt op) — voorwaarde voor de communicatie-coach-rol; principe: levende
      data, nooit handmatig.
- [ ] **Onderzoek beste bestaande tools per discipline** (marketing/sales/HR… met AI)
      — wij bouwen ze niet, wij verbinden ze (integrator-rol).
- [ ] **Structuurskelet + invoerinstructies** voor Mehdi/Angela/Sian zodat het team
      zelf data invult, parallel aan het bouwen.
- [ ] **Governance-signalering**: systeem merkt als binnengekomen data over een
      collega gedeeld hoort te worden met betrokkenen; RBAC verder verfijnen.
- [x] **Naamgeving**: organisatiegraaf heet voortaan **Second Brain** (2026-07-02).

## Onderzoek (vóór bouwen)
- [ ] **Movetex.com** onderzoeken: planning-algoritme (Fati gebruikt het). Doel: 4
      planningen (Matthias/Mathieu/Shilton/Luc) → 1 planningtool. Géén eigen bouw —
      bestaand pakket koppelen via API; Monday blijft alleen visueel.
- [ ] **17 disciplines** deep-research (via Claude) — **BESLIST 2026-07-03: ÉÉN
      dashboard, geen 17 losse** ("anders is onze brain verspreid"). Rest: per thema/tab
      een eigen deep-search → tab/subtab-structuur die op alle 15 firma's toepasbaar is.
      De 17 = referentiekader (auto-analogie: je ziet wat je mist), niet in beton.

## Data & beheer
- [ ] **Data-curatie Communicatie** (Siyan): doorfactuur-firma's, afdelingen, doelen en
      belvolgorde-queues invullen; oude records actief/niet-actief zetten.
- [ ] **Close Call afletteren**: factuur 2025-0119 telt 41 telefoonnummers, het register
      heeft er 40 onder Close Call BV — één Xelion-nummer ontbreekt of zit fout onder
      Proximus/Telesur. Nummerbijlage bij Close Call opvragen en vergelijken. (Mega is
      wél sluitend: 5 op factuur 1126002031 = 5 in register, à € 3,31 excl.)
- [ ] **Verantwoordelijken toewijzen** op nummers en e-mailadressen (team).
- [ ] **kosten.firma → kern.firma** verzoenen — brug ligt er (migratie 012:
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
      bewust géén — collega.)
- [ ] **Telefoonregister-repo**: branch `claude/ecstatic-feynman-wctpk1` → `main`
      verzoenen (zelfde recept als appportal-drift).
- [x] **Communicatie eigen repo + auto-deploy** — gedaan 2026-07-02
      (`softwareglobaal/globaal-communicatie`, subtree-split + cron).
- [x] **Off-site backups naar S3** — LIVE sinds 2026-07-03. Bucket
      `globaal-db-backups-2026` (us-east-1, lifecycle 30 dgn, block-public-access),
      upload-only IAM-user `backup-uploader` (`backup-upload-only`-policy). VM: AWS
      CLI v2 (officiële installer — apt-pakket ontbrak), gnupg, `~/.backup-passphrase`
      (chmod 600, kopie in wachtwoordkluis), `S3_BACKUP_BUCKET` in .env. Testrun OK:
      beide dumps GPG-versleuteld naar S3. Loopt automatisch mee in de 03:15-cron.
      Setup-checklist: `docs/offsite-backup-setup.md`.
