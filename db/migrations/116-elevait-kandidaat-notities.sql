-- 116: Notities per kandidaat en het hernoemde advies (Elevait)
-- Aanleiding: feedback Shaniel op de interne pagina.
--
-- 1. Notities: tot nu toe kon elke beoordelaar precies een notitie kwijt,
--    verstopt in het oordeelformulier. Er moeten er meerdere kunnen, met wie
--    en wanneer erbij, zodat het gespreksverslag en losse gedachten op een
--    plek staan.
-- 2. "Oordeel" heette gesprek/twijfel/afwijzen, en dat leek te veel op de
--    status van de kandidaat. Het is geen processtap maar de persoonlijke
--    mening van een oprichter. Vandaar de nieuwe woorden voorstander,
--    twijfel en tegenstander; op de pagina heet het voortaan "mijn advies".
--    Er stonden nog geen oordelen vastgelegd, dus er valt niets om te zetten.

CREATE TABLE IF NOT EXISTS elevait.notitie (
    id            bigserial PRIMARY KEY,
    kandidaat_id  bigint NOT NULL REFERENCES elevait.kandidaat(id) ON DELETE CASCADE,
    tekst         text NOT NULL,
    door          text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_elevait_notitie_kandidaat
    ON elevait.notitie (kandidaat_id, aangemaakt_op DESC);

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('mijn-advies', 'Mijn advies',
   'De persoonlijke mening van een oprichter over een kandidaat: voorstander, twijfel of tegenstander. Per persoon apart vastgelegd, want beide oprichters bekijken elke kandidaat en mogen het oneens zijn. Niet te verwarren met de status, die aangeeft waar de kandidaat in het proces staat en er maar een is.'),
  ('citaatcontrole', 'Citaatcontrole',
   'Bij elk criterium citeert de agent letterlijk uit het CV of de motivatie in plaats van samen te vatten, en de pagina controleert of dat fragment werkelijk in de brontekst voorkomt. Zo is elke bewering in twee seconden na te trekken en kan een taalmodel niet ongemerkt iets toeschrijven wat er niet staat.')
ON CONFLICT (sleutel) DO NOTHING;
