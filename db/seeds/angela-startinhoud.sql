-- Startinhoud van de Angela-tegel: wat er in de twee opstartgesprekken van
-- 28 en 29 juli 2026 besloten en afgesproken is. Idempotent: opnieuw draaien
-- voegt niets dubbel toe (match op bron_ref + titel).
--
-- Draaien NA migratie 097:
--   docker compose exec -T postgresql psql -U authentik -d appportal \
--     < db/seeds/angela-startinhoud.sql
--
-- Herkomst: twee Plaud-opnames. bron_ref is het opname-id, zodat een item
-- terug te voeren is op het gesprek waar het uit komt.

BEGIN;

CREATE TEMP TABLE _start (
    soort        text,
    titel        text,
    tekst        text,
    werkstroom   text,
    verantw      text,
    status       text,
    besloten_op  date,
    bron_ref     text,
    bron_titel   text
) ON COMMIT DROP;

INSERT INTO _start VALUES
-- Gesprek 29 juli, website en branding voor Angela.
('beslissing', 'Website start met de verkoopsectie, bio-pagina volgt daarna',
 'De pilot begint met de verkoopsectie. De bio-pagina voor Angela komt in een tweede stap.',
 'website', 'Shaniel', 'klaar', DATE '2026-07-29',
 'fdb122579dd8442e2ce5c95f75d7b383', 'Overleg 29 juli: website, branding en social'),
('beslissing', 'Social media via een pagina, niet via een persoonlijk profiel',
 'Een pagina is schaalbaar en te beheren door meerdere mensen; een persoonlijk profiel niet.',
 'social', NULL, 'klaar', DATE '2026-07-29',
 'fdb122579dd8442e2ce5c95f75d7b383', 'Overleg 29 juli: website, branding en social'),
('taak', 'Logo en beeldmerk uitwerken',
 'Concepten met silhouet en de Surinaamse vlag; ook de Liberty-symboliek is besproken.',
 'merk', 'Shaniel', 'open', NULL,
 'fdb122579dd8442e2ce5c95f75d7b383', 'Overleg 29 juli: website, branding en social'),
('taak', 'Domein en accounts vastleggen',
 'Domeinnaam plus de social accounts in één keer claimen, voordat de pagina live gaat.',
 'website', NULL, 'open', NULL,
 'fdb122579dd8442e2ce5c95f75d7b383', 'Overleg 29 juli: website, branding en social'),
('notitie', 'Positionering: Suriname tegenover Surinamers',
 'Het narratief gaat over de mensen, niet alleen over het land. Contentplanning wordt aan producten gekoppeld.',
 'social', NULL, 'open', NULL,
 'fdb122579dd8442e2ce5c95f75d7b383', 'Overleg 29 juli: website, branding en social'),
('notitie', 'Dataverzameling als lange termijn kracht',
 'Publieksbereik en registers leveren data op; die data is op termijn de eigenlijke waarde. Ambitie richting overheid en AI.',
 'data', NULL, 'open', NULL,
 'fdb122579dd8442e2ce5c95f75d7b383', 'Overleg 29 juli: website, branding en social'),
('taak', 'Korte overleggen meerdere keren per week inplannen',
 'Afgesproken werkritme om de voortgang te bewaken.',
 NULL, 'Mehdi', 'open', NULL,
 'fdb122579dd8442e2ce5c95f75d7b383', 'Overleg 29 juli: website, branding en social'),
-- Gesprek 29 juli, webshop en inkoop.
('beslissing', 'Webshop op Shopify met een gratis thema',
 'Structuur met productcategorieën: elektronica en ICT tegenover niet-elektronische goederen zoals kleding.',
 'webshop', NULL, 'klaar', DATE '2026-07-29',
 'e5bbd175c3acbfdaead943dc306dfb59', 'Overleg 29 juli: webshop, inkoop en fiscaal'),
('notitie', 'Breed inkopen via veilingen van gesloten bedrijven',
 'Niet beperken tot ICT: apparatuur, meubilair en decoratie in één keer overnemen. Verkoop per pallet.',
 'inkoop', NULL, 'open', NULL,
 'e5bbd175c3acbfdaead943dc306dfb59', 'Overleg 29 juli: webshop, inkoop en fiscaal'),
('taak', 'Uitzoeken wat de huidige regels zijn voor import en belastingnummer',
 'Bij grotere volumes (containers, meerdere pallets) speelt dit. Een eerdere grote lading leidde tot de verplichting een belastingnummer aan te vragen.',
 'fiscaal', NULL, 'open', NULL,
 'e5bbd175c3acbfdaead943dc306dfb59', 'Overleg 29 juli: webshop, inkoop en fiscaal'),
('notitie', 'NGO-vorm overwegen naast de commerciële lijn',
 'Voordelen die genoemd zijn: donaties van bedrijven en internationale organisaties, en een lagere lastendruk. Nog geen beslissing.',
 'fiscaal', NULL, 'open', NULL,
 'e5bbd175c3acbfdaead943dc306dfb59', 'Overleg 29 juli: webshop, inkoop en fiscaal'),
('taak', 'Foto''s maken van de producten en van de opbouw',
 'Veel en goede productfoto''s zijn bepalend voor de verkoop.',
 'webshop', 'Siam', 'open', NULL,
 'e5bbd175c3acbfdaead943dc306dfb59', 'Overleg 29 juli: webshop, inkoop en fiscaal');

INSERT INTO angela.item
       (soort, titel, tekst, werkstroom_id, verantwoordelijke_id, status,
        besloten_op, bron_soort, bron_ref, bron_titel, aangemaakt_door)
SELECT s.soort, s.titel, s.tekst, w.id, b.id, s.status,
       s.besloten_op, 'plaud', s.bron_ref, s.bron_titel, 'startinhoud'
  FROM _start s
  LEFT JOIN angela.werkstroom w ON w.sleutel = s.werkstroom
  LEFT JOIN angela.betrokkene b ON b.naam = s.verantw
 WHERE NOT EXISTS (
       SELECT 1 FROM angela.item i
        WHERE i.bron_ref = s.bron_ref AND i.titel = s.titel);

COMMIT;
