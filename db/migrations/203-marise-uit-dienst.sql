-- 203: Marise uit dienst (Shaniel, 30-10-2026).
--
-- Het Zoom-account van Marise is op 30-10-2026 verwijderd wegens uit dienst; hier stond Marise nog als in dienst, met het
-- adres uit migratie 201. De echte einddatum is niet opgegeven: dan geldt vandaag, net als op het profiel in de
-- organisatie-app. Er wordt niets verwijderd, de historie blijft staan. De regel moet precies een persoon raken.

BEGIN;

UPDATE kern.persoon
   SET in_dienst = false,
       datum_uit_dienst = coalesce(datum_uit_dienst, current_date),
       email = NULL
 WHERE voornaam = 'Marise' AND achternaam = 'Main' AND in_dienst AND email = 'ha.marise@globaal.be';

DO $$
BEGIN
    IF (SELECT count(*) FROM kern.persoon
         WHERE voornaam = 'Marise' AND achternaam = 'Main' AND NOT in_dienst AND email IS NULL) <> 1 THEN
        RAISE EXCEPTION 'Marise Main hoort als precies een persoon uit dienst te staan';
    END IF;
END $$;

COMMIT;
