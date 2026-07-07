-- 053 - kostregels per nummer (blueprint goedgekeurd door Shaniel
-- 2026-07-07: optie B nu, A later; per-minuut-regels volwaardig zichtbaar).
--
-- Een nummer kan bij meerdere partijen tegelijk kosten: Mehdi's 0486
-- betaalt Proximus voor het abonnement en Close Call voor de spoofing.
-- De bestaande kostprijs op het nummer blijft de hoofdregel (het
-- abonnement); kostregels zijn de extra diensten. Zo klopt de totale kost
-- per nummer en per leverancier ("dan moet je dat twee keer kost zetten").

CREATE TABLE communicatie.nummer_kost (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nummer_id       uuid NOT NULL REFERENCES communicatie.nummer(id) ON DELETE CASCADE,
    leverancier_id  uuid REFERENCES kern.leverancier(id) ON DELETE SET NULL,
    omschrijving    text NOT NULL DEFAULT '',
    bedrag          numeric,
    prijs_type      text NOT NULL DEFAULT 'per maand',
    peildatum       date,
    bijgewerkt_door text NOT NULL DEFAULT '',
    bijgewerkt_op   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_nummer_kost_nummer ON communicatie.nummer_kost (nummer_id);
CREATE INDEX ix_nummer_kost_leverancier ON communicatie.nummer_kost (leverancier_id);
GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.nummer_kost TO communicatie;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('kostregel', 'Kostregel',
     'Een extra kost die op een nummer drukt naast het hoofdabonnement, bv. de spoofing-dienst bij Close Call op een Proximus-nummer. Elke regel heeft een leverancier, omschrijving, bedrag excl. BTW (per maand of per minuut) en de peildatum van de factuur. Zo klopt de totale kost per nummer en per leverancier: een nummer kan twee keer berekend worden (meeting 2026-07-07).')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
