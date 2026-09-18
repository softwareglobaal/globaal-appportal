-- 153: naam en dienstverband bewerkbaar maken vanuit het Organisatie-dashboard
--
-- Tot nu toe kon de app van kern.persoon alleen werkgever_firma_id (baseline)
-- en weergavenaam (064) bijwerken. Wie vertrok of van naam veranderde, moest
-- met de hand in de database worden rechtgezet; dat is telkens een los stukje
-- SQL op productie en dus precies wat we niet willen.
--
-- Vertrekkers worden niet verwijderd maar op in_dienst = false gezet, met de
-- datum erbij: de lijst toont standaard alleen wie in dienst is, en historie
-- (uren, beloning, meetings, firma-koppelingen) blijft gewoon staan.

GRANT UPDATE (voornaam, achternaam, in_dienst, datum_uit_dienst)
    ON kern.persoon TO medewerker_writer;
