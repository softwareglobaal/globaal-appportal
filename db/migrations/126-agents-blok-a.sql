-- 126-agents-blok-a.sql
-- Registreert de sales- en marketingagents van het siyanagents-team en
-- koppelt ze aan de taken van blok A (A1 verkoop, A2 marketing, A3 klantenservice,
-- A4 partners en externe relaties). Zonder deze koppeling toont het register
-- wel taken, maar niet wie ze uitvoert.
-- Idempotent: dubbel draaien is veilig.

-- 1. De agents zelf ------------------------------------------------------
INSERT INTO kern.agent (code, naam, uitleg, url, actief, volgorde) VALUES
('dealmaker', 'De Dealmaker',
 'Sales- en marketingagent voor Pipedrive en Google Ads: leest vrij, muteert enkel via een goedgekeurd voorstel.',
 'https://siyanagents.globaal.be/', true, 10),
('verkoopstrateeg', 'De Verkoopstrateeg',
 'Segmentatie, verkoopdoelstellingen en quota, territoria, prijszetting en business development.',
 '', true, 11),
('offertemeester', 'De Offertemeester',
 'Offertes, aanbestedingen, bid/no-bid, raamovereenkomsten en win/verlies-analyse.',
 '', true, 12),
('marktverkenner', 'De Marktverkenner',
 'Marktonderzoek, klantinzichten, concurrentie-analyse en het volgen van trends en regelgeving.',
 '', true, 13),
('branding', 'De Merkbewaker',
 'Legt de branding vast als brandbook en bewaakt dat alle output on-brand blijft.',
 '', true, 14),
('contentregisseur', 'De Contentregisseur',
 'Marketingjaarplan en budget, referentieprojecten en cases, social media en nieuwsbrief.',
 '', true, 15),
('beeld', 'De Ontwerper',
 'Maakt on-brand beeldmateriaal: branded ontwerpen via Canva en AI-beelden.',
 '', true, 16),
('seo', 'De SEO-keten',
 'Onderzoek, schrijven en kwaliteitscontrole van SEO-paginas, met een blueprint-poort.',
 '', true, 17),
('website_bouwer', 'De Website-bouwer',
 'Bouwt volledige statische websites van merk tot live site; publiceert nooit zonder akkoord.',
 '', true, 18),
('woordvoerder', 'De Woordvoerder',
 'Persrelaties, externe communicatie en interne teamcommunicatie.',
 '', true, 19),
('klantenzorg', 'De Klantenzorg-agent',
 'Klantcontact en antwoordtermijnen, klachten met oorzaakanalyse, tevredenheid en reviews.',
 '', true, 20),
('relatiebeheerder', 'De Relatiebeheerder',
 'Sector- en overheidsrelaties, bankrelatie en waarborgen, partnernetwerk.',
 '', true, 21)
ON CONFLICT (code) DO UPDATE SET naam = EXCLUDED.naam, uitleg = EXCLUDED.uitleg,
    url = EXCLUDED.url, actief = true, volgorde = EXCLUDED.volgorde;

-- 2. Welke agent werkt op welke taak -------------------------------------
INSERT INTO kern.subelement_agent (subelement_code, agent_code, bijgewerkt_door) VALUES
('A1.1.1', 'verkoopstrateeg', 'migratie 126'),
('A1.1.1', 'marktverkenner', 'migratie 126'),
('A1.1.2', 'verkoopstrateeg', 'migratie 126'),
('A1.1.3', 'verkoopstrateeg', 'migratie 126'),
('A1.1.4', 'dealmaker', 'migratie 126'),
('A1.1.4', 'verkoopstrateeg', 'migratie 126'),
('A1.1.5', 'verkoopstrateeg', 'migratie 126'),
('A1.2.1', 'dealmaker', 'migratie 126'),
('A1.2.2', 'dealmaker', 'migratie 126'),
('A1.2.3', 'dealmaker', 'migratie 126'),
('A1.2.3', 'verkoopstrateeg', 'migratie 126'),
('A1.2.4', 'offertemeester', 'migratie 126'),
('A1.3.1', 'offertemeester', 'migratie 126'),
('A1.3.2', 'offertemeester', 'migratie 126'),
('A1.3.3', 'offertemeester', 'migratie 126'),
('A1.3.4', 'offertemeester', 'migratie 126'),
('A1.3.5', 'offertemeester', 'migratie 126'),
('A1.3.5', 'dealmaker', 'migratie 126'),
('A1.4.1', 'dealmaker', 'migratie 126'),
('A1.4.2', 'dealmaker', 'migratie 126'),
('A1.4.3', 'dealmaker', 'migratie 126'),
('A1.4.4', 'dealmaker', 'migratie 126'),
('A1.4.5', 'klantenzorg', 'migratie 126'),
('A1.4.5', 'dealmaker', 'migratie 126'),
('A1.5.1', 'dealmaker', 'migratie 126'),
('A1.5.2', 'offertemeester', 'migratie 126'),
('A1.5.3', 'verkoopstrateeg', 'migratie 126'),
('A1.5.4', 'verkoopstrateeg', 'migratie 126'),
('A1.5.5', 'dealmaker', 'migratie 126'),
('A1.6.1', 'verkoopstrateeg', 'migratie 126'),
('A1.6.1', 'marktverkenner', 'migratie 126'),
('A1.6.2', 'verkoopstrateeg', 'migratie 126'),
('A1.6.3', 'relatiebeheerder', 'migratie 126'),
('A1.6.3', 'verkoopstrateeg', 'migratie 126'),
('A1.6.4', 'verkoopstrateeg', 'migratie 126'),
('A2.1.1', 'marktverkenner', 'migratie 126'),
('A2.1.2', 'marktverkenner', 'migratie 126'),
('A2.1.3', 'marktverkenner', 'migratie 126'),
('A2.1.3', 'seo', 'migratie 126'),
('A2.1.4', 'marktverkenner', 'migratie 126'),
('A2.2.1', 'branding', 'migratie 126'),
('A2.2.2', 'branding', 'migratie 126'),
('A2.2.3', 'contentregisseur', 'migratie 126'),
('A2.2.3', 'dealmaker', 'migratie 126'),
('A2.3.1', 'website_bouwer', 'migratie 126'),
('A2.3.1', 'seo', 'migratie 126'),
('A2.3.2', 'contentregisseur', 'migratie 126'),
('A2.3.2', 'seo', 'migratie 126'),
('A2.3.3', 'contentregisseur', 'migratie 126'),
('A2.3.4', 'beeld', 'migratie 126'),
('A2.4.1', 'woordvoerder', 'migratie 126'),
('A2.4.2', 'woordvoerder', 'migratie 126'),
('A2.4.3', 'woordvoerder', 'migratie 126'),
('A3.1.1', 'klantenzorg', 'migratie 126'),
('A3.1.2', 'klantenzorg', 'migratie 126'),
('A3.1.3', 'klantenzorg', 'migratie 126'),
('A3.2.1', 'klantenzorg', 'migratie 126'),
('A3.2.2', 'klantenzorg', 'migratie 126'),
('A3.2.3', 'klantenzorg', 'migratie 126'),
('A3.3.1', 'klantenzorg', 'migratie 126'),
('A3.3.2', 'klantenzorg', 'migratie 126'),
('A3.3.2', 'seo', 'migratie 126'),
('A3.3.3', 'klantenzorg', 'migratie 126'),
('A4.1.1', 'relatiebeheerder', 'migratie 126'),
('A4.1.2', 'relatiebeheerder', 'migratie 126'),
('A4.1.3', 'relatiebeheerder', 'migratie 126'),
('A4.2.1', 'relatiebeheerder', 'migratie 126'),
('A4.2.2', 'relatiebeheerder', 'migratie 126'),
('A4.2.3', 'relatiebeheerder', 'migratie 126'),
('A4.3.1', 'relatiebeheerder', 'migratie 126'),
('A4.3.2', 'relatiebeheerder', 'migratie 126'),
('A4.3.3', 'relatiebeheerder', 'migratie 126')
ON CONFLICT DO NOTHING;

-- 3. Controle: geen enkele taak in blok A mag zonder agent achterblijven --
DO $$
DECLARE n integer;
BEGIN
    SELECT count(*) INTO n
      FROM kern.subelement e
      JOIN kern.subdiscipline s ON s.code = e.subdiscipline_code
     WHERE s.discipline_sleutel IN ('sales_bizdev', 'marketing_communicatie',
                                    'customer_service', 'partnerships_relaties')
       AND NOT EXISTS (SELECT 1 FROM kern.subelement_agent ta
                        WHERE ta.subelement_code = e.code);
    IF n > 0 THEN
        RAISE EXCEPTION 'migratie 126: % taken in blok A hebben nog geen agent', n;
    END IF;
END $$;
