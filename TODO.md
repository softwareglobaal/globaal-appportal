# To-do — AppPortal / Organisatie / Communicatie

> Parkeerlijst van afgesproken maar nog niet gebouwde zaken. Bron: Zoom-meetings
> 2026-07-01 en 2026-07-02 + lopende afspraken. Afvinken of verplaatsen bij oppakken.

## Organisatie-dashboard & AI (vervolg op graph v1)
- [ ] **Facturatie-terminologie** vastleggen (DEFINITIEBOEK-aanvulling): gefactureerd-naar
      vs betaald-door; **doorfactureerbaar ja/nee + basis** (maandelijks / vast bedrag /
      percentage / effectief); leverancier ≠ platform. Daarná de telefonie-kolommen in
      Communicatie uitbreiden.
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
- [ ] **Finalisatie-status + kleurcodering** in de Second Brain: blauw = gefinaliseerd,
      rood = nog niet — met vastlegging *wie* finaliseerde (Mehdi/Angela/Sian) en
      *wanneer* (rollen wijzigen; historie telt).
- [ ] **17-disciplines-structuur** (hybride model uit de deep-research; document van
      Mehdi) als laag in de Second Brain — per firma, afwijkingen expliciet, lege
      disciplines onzichtbaar.
- [ ] **KBO-koppeling + jaarrekeningen** aan de firma's (door Mehdi als eerstvolgende
      databron genoemd; daarna één-voor-één verder).
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
- [ ] **Verantwoordelijken toewijzen** op nummers en e-mailadressen (team).
- [ ] **kosten.firma → kern.firma** verzoenen (dubbele firmalijst weg; migratie).
- [ ] Ontbrekende HR-nummers/familienamen/e-mails in kern.persoon aanvullen.

## Techniek / hygiëne
- [ ] **Telefoonregister-repo**: branch `claude/ecstatic-feynman-wctpk1` → `main`
      verzoenen (zelfde recept als appportal-drift).
- [x] **Communicatie eigen repo + auto-deploy** — gedaan 2026-07-02
      (`softwareglobaal/globaal-communicatie`, subtree-split + cron).
- [ ] Off-site kopie van de nachtelijke DB-backups (S3).
