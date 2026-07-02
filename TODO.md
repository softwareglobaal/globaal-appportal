# To-do — AppPortal / Organisatie / Communicatie

> Parkeerlijst van afgesproken maar nog niet gebouwde zaken. Bron: Zoom-meetings
> 2026-07-01 en 2026-07-02 + lopende afspraken. Afvinken of verplaatsen bij oppakken.

## Organisatie-dashboard & AI (vervolg op graph v1)
- [ ] **Facturatie-terminologie** vastleggen (DEFINITIEBOEK-aanvulling): gefactureerd-naar
      vs betaald-door; **doorfactureerbaar ja/nee + basis** (maandelijks / vast bedrag /
      percentage / effectief); leverancier ≠ platform. Daarná de telefonie-kolommen in
      Communicatie uitbreiden.
- [ ] **Documenten koppelen aan de graph** (bv. testresultaten per collega over meerdere
      jaren) → AI-vragen als "wie is het meest geschikt voor deze taak", trends
      (groei/demotivatie).
- [ ] **Fathom-integratie**: meeting-transcripts als AI-bron ("lezen of we goed bezig
      zijn"); Gullok toegang tot Fathom geven.
- [ ] **Nieuwe entiteiten** in kern + graph: klanten, diensten, contracten (leveranciers
      bestaan al) — met vervaldatums, zodat de AI proactief kan signaleren (het
      verzekerings-voorbeeld van Mehdi).
- [ ] **RBAC verfijnen**: wie ziet welk deel van het dashboard (nu: admin/manager alles).

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
- [ ] **Communicatie eigen repo + auto-deploy** (zelfde pad als globaal-organisatie),
      als dat bevalt.
- [ ] Off-site kopie van de nachtelijke DB-backups (S3).
