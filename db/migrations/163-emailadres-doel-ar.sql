-- 163: ar@ mist het doel dat ap@ wel kreeg.
--
-- Migratie 162 zette ap@ (accounts payable) op Finance en liet ar@ (accounts
-- receivable) leeg, omdat 'ar' niet in de rolwoordenlijst stond. Dat is niet
-- vol te houden: het zijn twee helften van dezelfde conventie en ze staan op
-- hetzelfde domein naast elkaar (ap@ en ar@energie-efficient.be). Of je neemt
-- ze allebei, of geen van beide.
--
-- Alleen waar het doel nog leeg is: een oordeel dat iemand intussen zelf
-- invulde blijft staan.

BEGIN;

UPDATE communicatie.emailadres
   SET doel = 'Finance',
       bijgewerkt_door = 'migratie-163',
       bijgewerkt_op = now()
 WHERE doel = ''
   AND split_part(adres::text, '@', 1) IN ('ar', 'accountsreceivable', 'accountspayable');

COMMIT;
