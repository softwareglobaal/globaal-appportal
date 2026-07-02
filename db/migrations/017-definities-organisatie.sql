-- 017 — woordenboek-aanvulling voor het Organisatie-dashboard / de Second Brain.
--
-- Zelfde principe als migratie 015: kern.definitie is de machinebron; het
-- Organisatie-dashboard toont deze definities als tooltips op kolomkoppen en
-- graph-filters en op de woordenboek-pagina. Sleutels zijn stabiel.

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('persoon', 'Persoon',
 'Een medewerker uit de centrale gebruikersdatabase — dé bron voor alle apps. Weergave overal als "Voornaam (Afdeling)"; de volledige naam staat alleen in de bron zelf.'),
('diensten_voor', 'Diensten voor',
 'De firma''s waarvoor een persoon werkt of diensten verricht, los van waar hij in dienst is — meerdere mogelijk.'),
('eigenaar', 'Eigenaar',
 'De persoon aan wie een actiepunt is toegewezen. De AI stelt een eigenaar voor op basis van het transcript; een mens bevestigt (voorgesteld ≠ toegewezen).'),
('meeting', 'Meeting',
 'Een opgenomen vergadering (via Fathom): transcript, deelnemers, samenvatting, actiepunten en beslissingen komen automatisch de Second Brain in.'),
('actiepunt', 'Actiepunt',
 'Een taak of to-do uit een meeting. Door de AI uit het transcript gehaald (het vangnet) of door Fathom aangeleverd; eigenaar wordt door een mens bevestigd.'),
('beslissing', 'Beslissing',
 'Een genomen besluit uit een meeting — bewust apart van actiepunten: "management neemt iemand aan" is een beslissing, "HR maakt het profiel op" is het actiepunt.'),
('besproken', 'Besproken',
 'De koppeling tussen een meeting en waar het over ging (personen, firma''s, leveranciers, software) — alleen begrippen die al in de centrale database bestaan, geen vrije tekst.'),
('signaal', 'Signaal',
 'Een automatisch aandachtspunt uit de data (puur regels, geen AI): ontbrekende verantwoordelijke, niet-gematchte firma, open actiepunt. Met ernst hoog/middel/laag.'),
('briefing', 'Dagbriefing',
 'De dagelijkse AI-samenvatting van de belangrijkste signalen en veranderingen — één AI-oproep per dag, te verversen met de Ververs-knop.'),
('second_brain', 'Second Brain',
 'De knowledge-graph van de organisatie: een wéérgave van de centrale database (geen invoerkanaal) waarin personen, firma''s, nummers, software, kosten en meetings gelinkt zijn.'),
('software', 'Software',
 'Een softwarepakket of abonnement uit het kosten-schema, gelinkt aan leverancier, firma en seat-gebruikers.'),
('emailadres', 'E-mailadres',
 'Een e-mailadres uit het Communicatie-dashboard, met firma, verantwoordelijke en gebruikers.');
