# To-do — AppPortal / Organisatie / Communicatie

> Parkeerlijst van afgesproken maar nog niet gebouwde zaken. Bron: Zoom-meetings
> 2026-07-01 en 2026-07-02 + lopende afspraken. Afvinken of verplaatsen bij oppakken.

## Organisatie-dashboard & AI (vervolg op graph v1)
- [ ] **Facturatie-terminologie** vastleggen (DEFINITIEBOEK-aanvulling): gefactureerd-aan
      (= Unabo) / doorfactureren-naar / **gebruikt-voor** (gebouwd, migratie 013);
      nog: betaald-door, **doorfactureerbaar ja/nee + basis** (maandelijks / vast bedrag /
      percentage / effectief); leverancier ≠ platform.
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
