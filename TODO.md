# To-do — AppPortal / Organisatie / Communicatie

> Parkeerlijst van afgesproken maar nog niet gebouwde zaken. Bron: Zoom-meetings
> 2026-07-01 en 2026-07-02 + lopende afspraken. Afvinken of verplaatsen bij oppakken.

## Meeting 2026-07-02 (avond) — woordenboek, vermogens, agenda
- [x] **DEFINITIEBOEK zichtbaar op de dashboards** — GEBOUWD voor Communicatie
      (migratie 015): `kern.definitie` is de machinebron; kolomkoppen, tooltips,
      kolomkiezer, Woordenboek-knop en Excel-export lezen eruit. Terminologie
      doorgevoerd: "Intern gefactureerd aan" / "Interne doorfacturatie naar".
      Ook in het **Organisatie-dashboard** (migratie 017): ⓘ Woordenboek-pagina,
      tooltips op kolomkoppen en op de Second Brain-typefilters.
      Rest: beheer-UI voor definities (nu: UPDATE op kern.definitie +
      DEFINITIEBOEK.md in sync houden).
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
- [ ] **AI-factuurgoedkeuring** (meeting 2026-07-02): elke inkomende factuur langs de
      AI ("goed om te betalen?" — check tegen verwacht: seats × prijs + vaste prijzen);
      niet goedgekeurd → handmatig naar Mehdi of Angela; goedgekeurd → prijzen
      automatisch bijwerken. Bouwt op kosten.charge_actual (verwacht vs. werkelijk).
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
- [ ] **17 disciplines** deep-research → daarna beslissen: één dashboard met onderdelen
      of meerdere dashboards.

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
- [ ] **Telefoonregister-repo**: branch `claude/ecstatic-feynman-wctpk1` → `main`
      verzoenen (zelfde recept als appportal-drift).
- [x] **Communicatie eigen repo + auto-deploy** — gedaan 2026-07-02
      (`softwareglobaal/globaal-communicatie`, subtree-split + cron).
- [ ] Off-site kopie van de nachtelijke DB-backups (S3).
