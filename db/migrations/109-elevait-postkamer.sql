-- 109: Postkamer-agent Elevait (brok A: lezen en tonen)
-- Aanleiding: ontwerp postkamer-agent, akkoord Shaniel 31-07-2026. De agent
-- leest info@elevaitnv.com via IMAP, sorteert elk bericht in een categorie
-- en vat het samen; de postkamerbrief staat op het tabblad Post van
-- intern.elevaitnv.com.
--
-- BEWUST NIET OPGESLAGEN: de berichttekst zelf. Alleen afzender, onderwerp,
-- categorie en een korte samenvatting. Twee redenen: post van derden hoort
-- niet in een database die breder gelezen wordt dan de mailbox, en wat er
-- niet staat kan ook niet als instructie terugkomen in een latere prompt.
--
-- Categorienamen zijn Engels (besluit Shaniel 31-07-2026); de samenvatting
-- en de brief blijven Nederlands.
--
-- NIET in de Second Brain-graaf: berichten bevatten persoonsgegevens van
-- derden. Toegevoegd aan _NOOIT in graaf.py in dezelfde sessie.

CREATE TABLE IF NOT EXISTS elevait.bericht (
    id             bigserial PRIMARY KEY,
    message_id     text NOT NULL UNIQUE,
    van_naam       text NOT NULL DEFAULT '',
    van_adres      text NOT NULL DEFAULT '',
    onderwerp      text NOT NULL DEFAULT '',
    ontvangen_op   timestamptz NOT NULL,
    categorie      text NOT NULL
                   CHECK (categorie IN ('customer_enquiry', 'job_application',
                                        'invoice', 'system_notification',
                                        'newsletter', 'suspicious', 'other')),
    samenvatting   text NOT NULL DEFAULT '',
    reden          text NOT NULL DEFAULT '',
    eigen_melding  boolean NOT NULL DEFAULT false,
    afgehandeld    boolean NOT NULL DEFAULT false,
    afgehandeld_door text NOT NULL DEFAULT '',
    afgehandeld_op timestamptz,
    model          text NOT NULL DEFAULT '',
    verwerkt_op    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_elevait_bericht_ontvangen
    ON elevait.bericht (ontvangen_op DESC);
CREATE INDEX IF NOT EXISTS ix_elevait_bericht_categorie
    ON elevait.bericht (categorie);

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('postkamerbrief', 'Postkamerbrief',
   'Het dagoverzicht van de postkamer-agent op het tabblad Post: eerst wat aandacht vraagt (onbeantwoorde klantaanvragen en sollicitaties), dan de nieuwe post van vandaag, en tot slot de ruis alleen als aantal. De agent sorteert en signaleert; antwoorden doet een mens.'),
  ('eigen-melding', 'Eigen melding',
   'Een bericht dat de website zelf naar info@ stuurde bij een nieuwe sollicitatie of contactaanvraag. De postkamer herkent die aan afzender en onderwerp en telt ze niet als nieuwe post, omdat ze al in de eigen stromen verwerkt zijn.')
ON CONFLICT (sleutel) DO NOTHING;
