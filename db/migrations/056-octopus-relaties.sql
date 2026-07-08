-- 056 - Octopus-relaties en grootboekrekeningen (aanlevering Joan
-- 2026-07-08, meeting Mehdi/Joan 2026-07-07: "Octopus is de source of
-- truth; Octopus maakt het en wij linken").
--
-- Elke firma heeft zijn eigen Octopus-boekhouding met eigen relatie-ID's:
-- dezelfde partij (Proximus) is relatie 9 bij EE en 21 bij H-Architects.
-- Het BTW-nummer groepeert dezelfde partij over boekhoudingen heen. Het
-- externe relatienummer is ons klantnummer bij die leverancier (Mehdi:
-- nodig om te kunnen bellen). Import via db/seeds/, herhaalbaar.

CREATE TABLE kosten.octopus_relatie (
    id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firma_code           text NOT NULL,
    octopus_id           text NOT NULL,
    naam                 text NOT NULL,
    voornaam             text NOT NULL DEFAULT '',
    actief               boolean NOT NULL DEFAULT true,
    is_klant             boolean NOT NULL DEFAULT false,
    is_leverancier       boolean NOT NULL DEFAULT false,
    grootboek_klant      text NOT NULL DEFAULT '',
    grootboek_leverancier text NOT NULL DEFAULT '',
    extern_relatienummer text NOT NULL DEFAULT '',
    btw_nummer           text NOT NULL DEFAULT '',
    btw_type             text NOT NULL DEFAULT '',
    land                 text NOT NULL DEFAULT '',
    gemeente             text NOT NULL DEFAULT '',
    telefoon             text NOT NULL DEFAULT '',
    gsm                  text NOT NULL DEFAULT '',
    email                text NOT NULL DEFAULT '',
    zoekveld             text NOT NULL DEFAULT '',
    is_intern            boolean NOT NULL DEFAULT false,
    leverancier_id       uuid REFERENCES kern.leverancier(id) ON DELETE SET NULL,
    geimporteerd_op      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (firma_code, octopus_id)
);
CREATE INDEX ix_octopus_relatie_btw ON kosten.octopus_relatie (btw_nummer);
CREATE INDEX ix_octopus_relatie_lev ON kosten.octopus_relatie (leverancier_id);

CREATE TABLE kosten.octopus_grootboek (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    firma      text NOT NULL,
    boekhouder text NOT NULL DEFAULT '',
    type       text NOT NULL,
    rekening   text NOT NULL,
    UNIQUE (firma, type, rekening)
);

GRANT SELECT ON kosten.octopus_relatie, kosten.octopus_grootboek TO communicatie;
GRANT SELECT ON kosten.octopus_relatie, kosten.octopus_grootboek TO kosten;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('octopus_relatie', 'Octopus-relatie',
     'Een klant of leverancier zoals hij in de Octopus-boekhouding van een van onze firma''s staat, met zijn relatie-ID en grootboekrekening. Elke firma heeft een eigen boekhouding met eigen nummers; het BTW-nummer groepeert dezelfde partij over boekhoudingen heen. Octopus is hiervoor de source of truth: wij linken, wij beheren het niet.'),
    ('klantnummer_bij_leverancier', 'Klantnummer bij leverancier',
     'Ons klantnummer in de administratie van de leverancier (in Octopus het externe relatienummer). Nodig aan de telefoon: de leverancier vraagt er altijd naar.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
