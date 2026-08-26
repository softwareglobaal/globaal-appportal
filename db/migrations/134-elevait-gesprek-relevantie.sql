-- 134: Relevantie van gesprekken (Elevait, Second Brain)
-- Aanleiding: besluit Shaniel 26-08-2026. Mehdi's Fathom-account bevat vooral
-- gesprekken van andere firma's (H-A-klanten, bouwdossiers). Die horen niet in
-- de Elevait-Second-Brain. Een model classificeert elk gesprek op de
-- samenvatting: elevait / twijfel / niet. Getest op een mix van 12 echte
-- gesprekken: alle duidelijke gevallen correct, grensgevallen vallen bewust
-- naar twijfel/opnemen (een gemist Elevait-gesprek is erger dan ruis).
--
-- Regels:
--   onbeoordeeld  nog niet geclassificeerd
--   elevait       hoort in de Second Brain; wordt gedestilleerd
--   twijfel       wordt opgenomen en gedestilleerd, maar zichtbaar als twijfel
--                 zodat een mens het met een klik kan corrigeren (vangnet)
--   niet          geen Elevait-gesprek; wordt NIET gedestilleerd en het
--                 transcript wordt niet bewaard (klantdata van andere firma's)
--
-- beoordeeld_door: 'model' of de gebruikersnaam bij een handmatige correctie.
-- Een menselijke keuze wint altijd; de pijplijn overschrijft die nooit.

ALTER TABLE elevait.gesprek
    ADD COLUMN IF NOT EXISTS relevantie text NOT NULL DEFAULT 'onbeoordeeld'
        CHECK (relevantie IN ('onbeoordeeld', 'elevait', 'twijfel', 'niet')),
    ADD COLUMN IF NOT EXISTS relevantie_reden text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS beoordeeld_door text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS beoordeeld_op timestamptz;

CREATE INDEX IF NOT EXISTS ix_elevait_gesprek_relevantie
    ON elevait.gesprek (relevantie);

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('gesprek-relevantie', 'Gesprek-relevantie',
   'Per opgehaald gesprek de vraag of het in de Elevait-Second-Brain hoort: elevait, twijfel of niet. Een model beoordeelt de samenvatting; twijfel wordt opgenomen maar blijft zichtbaar voor een menselijke correctie met een klik. Een gesprek dat niet over Elevait gaat wordt niet gedestilleerd en het transcript wordt niet bewaard, want klantgesprekken van andere firma''s horen niet in de Elevait-database. Een menselijk oordeel wint altijd van het model.')
ON CONFLICT (sleutel) DO NOTHING;
