-- 149: De manager krijgt geheugen en een oordeel.
--
-- Tot nu toe begon elke ronde blanco. Daardoor kon hij wel zeggen DAT er 119
-- eindjes te lang openstaan, maar niet dat dat getal al drie weken niet
-- beweegt, en dat is een heel ander bericht. Zonder geheugen is elke melding
-- een momentopname en klinkt stilstand hetzelfde als vooruitgang.

-- Wat er nu is, met sinds wanneer. Een signaal dat verdwijnt wordt verwijderd:
-- komt het terug, dan is het ook echt opnieuw begonnen en hoort de teller weer
-- op nul.
CREATE TABLE IF NOT EXISTS elevait.manager_signaal (
    sleutel        text PRIMARY KEY,
    waar           text NOT NULL,
    ernst          text NOT NULL,
    tekst          text NOT NULL,
    -- Het getal waar het signaal om draait, als er een is. Hiermee kan de
    -- manager zien of iets oploopt of afneemt in plaats van alleen of het er is.
    waarde         numeric,
    eerst_gezien   timestamptz NOT NULL DEFAULT now(),
    laatst_gezien  timestamptz NOT NULL DEFAULT now(),
    -- Sinds wanneer de waarde onveranderd is; dit maakt "staat al drie weken
    -- stil" mogelijk.
    waarde_sinds   timestamptz NOT NULL DEFAULT now(),
    vorige_waarde  numeric
);

-- Het oordeel van de manager over de stand, in zijn eigen woorden. Bewaard en
-- niet alleen getoond, zodat je kunt terugkijken wat hij wanneer vond en of
-- dat ergens op sloeg.
CREATE TABLE IF NOT EXISTS elevait.manager_oordeel (
    id          bigserial PRIMARY KEY,
    gemaakt_op  timestamptz NOT NULL DEFAULT now(),
    kern        text NOT NULL,
    toon        text NOT NULL DEFAULT 'rustig',
    punten      jsonb NOT NULL DEFAULT '[]'::jsonb,
    model       text,
    signalen    integer NOT NULL DEFAULT 0,
    fout        text
);

CREATE INDEX IF NOT EXISTS ix_elevait_manager_oordeel_tijd
    ON elevait.manager_oordeel (gemaakt_op DESC);
