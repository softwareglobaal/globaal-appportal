-- 120: intercompany - onderscheid factuur, creditnota, betaling en overige.
--
-- Migratie 118 hield per boeking alleen `gefactureerd` (credit) en `betaald`
-- (debet) bij. Dat is te grof gebleken: aan de debetkant van een
-- leveranciersrekening staan drie heel verschillende dingen door elkaar.
--
-- Nagemeten op de volledige spiegel (20-08-2026):
--   A-dagboeken (A1, A2, A3)  aankoop. Credit = factuur van HDS.
--                             Debet  = creditnota. Er zijn er drie in de hele
--                             historie, waarvan een op A3 en twee op A1.
--   F-dagboeken (F1..F5)      financieel. Altijd debet, altijd echt geld.
--   D-dagboeken (D1, D2, D5)  diverse posten, samen 162.642,20 aan de
--                             debetkant. Geen betalingen maar herschikkingen.
--
-- Waarom dit ertoe doet: de app meldde dat de creditnota van H-Architects
-- (HA2026-04, 5.000 euro, 30-06-2026) niet in Octopus geboekt zou zijn en dat
-- H-Architects daardoor 5.000 te veel betaald had. Dat was fout. De creditnota
-- staat er wel, maar in dezelfde kolom als een betaling, en werd dus als
-- betaling meegeteld. Zonder dit onderscheid vertelt het signaal "betaald
-- zonder factuur" onwaarheden over geld.
--
-- Het saldo zelf verandert NIET. Dat blijft credit min debet, en dat is en
-- blijft het echte rekeningsaldo; alleen de duiding eronder wordt juist.

ALTER TABLE intercompany.boeking
    ADD COLUMN IF NOT EXISTS soort text NOT NULL DEFAULT 'onbekend';

-- Inhaalslag voor wat er al staat. De app zet dit voortaan bij elke verversing.
UPDATE intercompany.boeking
   SET soort = CASE
        WHEN gefactureerd > 0 AND dagboek LIKE 'A%' THEN 'factuur'
        WHEN betaald      > 0 AND dagboek LIKE 'A%' THEN 'creditnota'
        WHEN betaald      > 0 AND dagboek LIKE 'F%' THEN 'betaling'
        ELSE 'overig'
   END
 WHERE soort = 'onbekend';

CREATE INDEX IF NOT EXISTS ix_intercompany_boeking_soort
    ON intercompany.boeking (dossier_id, relatie_id, soort);

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('intercompany.creditnota', 'creditnota op een leveranciersrekening',
     'Een creditnota van een leverancier komt in Octopus aan de DEBETkant van '
     'de leveranciersrekening, in hetzelfde veld als een betaling. Wie die twee '
     'niet uit elkaar houdt, telt een creditnota mee als betaald geld.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
