-- 189: Organisatie kosten leest de dienstdatums uit HR (personeel.pa_persoon).
--
-- Waarom: wie in een maand meetelt in de kostprijs van Suriname, volgt uit de
-- datum in en uit dienst in hr.globaal.be. HR is de eigenaar van de persoon;
-- Organisatie kosten leest alleen.
--
-- Alleen de kolommen die de kostenberekening nodig heeft: naam, status, datums,
-- uren en entiteit. Geen adres, rekeningnummer, verzekering of andere
-- persoonsgegevens. Geen salaris: dat staat niet in dit schema.

GRANT USAGE ON SCHEMA personeel TO doorbelasting_app;
GRANT SELECT (personeelsnummer, voornaam, achternaam, roepnaam, status, in_dienst, uit_dienst,
              uren_per_week, entiteit, afdelingscode, locatie, functie)
    ON personeel.pa_persoon TO doorbelasting_app;
