-- 192-agent-tenderwachter.sql
-- Registreert De Tenderwachter, de vakagent voor overheidsopdrachten (Belgie/EU via BOSA
-- e-Procurement en TED, Suriname via Openbare Werken, IDB en andere donoren), en koppelt hem
-- aan de taken van blok A waar hij naast De Offertemeester werkt. De Tenderwachter spoort
-- tenders op en adviseert bid/no-bid; De Offertemeester maakt de offerte op.
-- Idempotent: dubbel draaien is veilig.

INSERT INTO kern.agent (code, naam, uitleg, url, actief, volgorde) VALUES
('tenderwachter', 'De Tenderwachter',
 'Overheidsopdrachten Belgie/EU en Suriname: spoort aanbestedingen op per firma, kent de regels en drempels, adviseert bid/no-bid. Dient nooit zelf in.',
 '', true, 22)
ON CONFLICT (code) DO UPDATE SET naam = EXCLUDED.naam, uitleg = EXCLUDED.uitleg,
    url = EXCLUDED.url, actief = true, volgorde = EXCLUDED.volgorde;

INSERT INTO kern.subelement_agent (subelement_code, agent_code, bijgewerkt_door) VALUES
('A1.2.4', 'tenderwachter', 'migratie 192'),
('A1.3.2', 'tenderwachter', 'migratie 192'),
('A1.3.3', 'tenderwachter', 'migratie 192'),
('A1.3.4', 'tenderwachter', 'migratie 192')
ON CONFLICT DO NOTHING;
