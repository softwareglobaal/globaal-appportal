-- 111: Uitgaande mail van de HR-agent (Elevait)
-- Aanleiding: besluit Shaniel 03-08-2026. De HR-agent mag vanaf nu zelf de
-- ontvangstbevestiging aan een sollicitant sturen. Dat is de eerste keer dat
-- een Elevait-agent zelfstandig naar buiten communiceert, dus elke verstuurde
-- mail wordt vastgelegd: wat, aan wie, wanneer, en op welke grond.
--
-- De agent beslist nog steeds niets over een mens. De bevestiging bevat geen
-- enkel oordeel; uitnodigen en afwijzen blijft mensenwerk.

CREATE TABLE IF NOT EXISTS elevait.uitgaande_mail (
    id            bigserial PRIMARY KEY,
    kandidaat_id  bigint REFERENCES elevait.kandidaat(id) ON DELETE SET NULL,
    soort         text NOT NULL
                  CHECK (soort IN ('ontvangstbevestiging', 'statusantwoord',
                                   'uitnodiging', 'afwijzing')),
    ontvanger     text NOT NULL,
    onderwerp     text NOT NULL DEFAULT '',
    status        text NOT NULL DEFAULT 'verzonden'
                  CHECK (status IN ('verzonden', 'mislukt', 'overgeslagen')),
    reden         text NOT NULL DEFAULT '',
    door          text NOT NULL DEFAULT 'agent',
    verzonden_op  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_elevait_uitgaande_mail_kandidaat
    ON elevait.uitgaande_mail (kandidaat_id, soort);

-- Waarborg tegen post met terugwerkende kracht: iedereen die al in het
-- systeem staat krijgt een overslaan-regel, zodat niemand acht dagen na zijn
-- sollicitatie alsnog een "we hebben je bericht ontvangen" krijgt.
INSERT INTO elevait.uitgaande_mail
       (kandidaat_id, soort, ontvanger, onderwerp, status, reden, door)
SELECT k.id, 'ontvangstbevestiging', k.email, '', 'overgeslagen',
       'Solliciteerde voordat de agent zelf bevestigingen stuurde (03-08-2026).',
       'migratie'
  FROM elevait.kandidaat k
 WHERE NOT EXISTS (
       SELECT 1 FROM elevait.uitgaande_mail u
        WHERE u.kandidaat_id = k.id AND u.soort = 'ontvangstbevestiging');

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('ontvangstbevestiging', 'Ontvangstbevestiging',
   'Het enige bericht dat de HR-agent zelfstandig naar een sollicitant stuurt: de bevestiging dat de sollicitatie binnen is, met de termijn waarop iemand iets hoort. Vaste tekst met alleen naam en vacature als invulveld, want een bericht dat een termijn belooft hoort niet per keer opnieuw geformuleerd te worden. Bevat geen enkel oordeel; uitnodigen en afwijzen blijft mensenwerk.')
ON CONFLICT (sleutel) DO NOTHING;
