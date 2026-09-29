-- 177: De vierletterige code van een firma heet agendacode.
--
-- Aanleiding: Mehdi, 29-09-2026, na migratie 175: "ik zie de afkorting voor agenda niet!
-- er moet 2 afkortingen zijn toch!" Klopt. De kolom heette Firmacode, maar het is de code
-- die sinds 21-09-2026 in de titel van een afspraak staat ([HARC-KB]; mandaat van Mehdi
-- van 23-09-2026 in de werkwijze van de Agendawacht). Gemeten op 29-09-2026: van de
-- afspraken gemaakt sinds 21-09 dragen er 55 de vierletterige code en 12 nog een oude
-- schrijfwijze (UNABO, HA, TKN), vooral afspraken met gasten. De definitie uit 175 zei
-- "staat in agenda-afspraken, mapnamen en gesprekken"; mapnamen en gesprekken waren niet
-- nagemeten en gaan eruit. De sleutel blijft firmacode, de term wordt Agendacode.
--
-- Rechtzetting van 175: daar stond dat buiten de organisatie-app niemand kern.firma.land
-- leest. Sinds 176 leest Organisatie kosten het bij het vullen van doorbelasting.firma
-- (src/lib/seed.ts). De gevulde tabel klopt (HDSI staat op India), maar een nieuwe
-- vulling zou IN overnemen zolang die omzetting IN niet kent.

BEGIN;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('firmacode', 'Agendacode',
     'De afkorting van vier letters van een firma, bv. HARC, UNAB, TKNB; ook firmacode genoemd. Staat sinds 21-09-2026 in de titel van een agenda-afspraak: [HARC-KB] 2601 Jan Peeters. Oudere afspraken dragen nog HA, UNABO of TKN; die blijven leesbaar. De agents herkennen er een firma mee. Uniek per firma; beheerd op organisatie.globaal.be bij Firma''s.'),
    ('contactcode', 'Contactcode',
     'De afkorting van twee letters van een firma in de naamregel van een contact in Google Contacts, die Xelion bij een oproep toont, bv. HA, UN, TK. Aan het dossiernummer geplakt: HA5609 is dossier 5609 van H-Architects. Uniek per firma; alleen een firma met klanten of prospects heeft er een. De Contactwacht leest ze hier. Niet te verwarren met de agendacode van vier letters.')
ON CONFLICT (sleutel) DO UPDATE SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

-- Alleen als niemand de tekst intussen zelf aanpaste.
UPDATE kern.bron_regel
   SET gegeven = 'Firma: naam, agendacode, contactcode, land', bijgewerkt_op = now()
 WHERE sleutel = 'firma' AND gegeven = 'Firma: naam, firmacode, contactcode, land';

COMMIT;
