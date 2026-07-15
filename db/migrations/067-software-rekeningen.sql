-- 067 - grootboek-vangnet voor software-uitgaven (besluit Shaniel
-- 2026-07-15: kosten-dashboard toont "werkelijk betaald" uit de
-- Octopus-spiegel; de leverancier-koppeling is de precieze route en het
-- grootboek is het vangnet voor wat nog niet gekoppeld is).
--
-- Een mens wijst per dossier aan welke grootboekrekeningen (accountKey in
-- de boekingsregels) software/licenties zijn. Boekingen op die rekeningen
-- tellen dan mee als software-uitgave, ook als de tegenpartij nog niet
-- aan een centrale leverancier gekoppeld is. Het kosten-dashboard toont
-- ter hulp de rekeningen met de meeste uitgaven, zodat het aanwijzen
-- gewoon curatiewerk is (machine stelt voor, mens beslist).

CREATE TABLE kosten.software_rekening (
    dossier_id    integer NOT NULL,
    account_key   integer NOT NULL,
    omschrijving  text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (dossier_id, account_key)
);

-- Lezen voor de dashboards en de signalen-agent; beheren doet de
-- kosten-rol (het kosten-dashboard is de plek waar dit curatiewerk hoort).
GRANT SELECT ON kosten.software_rekening TO portal, communicatie, kosten;
GRANT INSERT, UPDATE, DELETE ON kosten.software_rekening TO kosten;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('software_rekening', 'Software-rekening',
     'Een grootboekrekening die per Octopus-dossier is aangewezen als rekening waar software- en licentiekosten op geboekt worden. Boekingen op zo''n rekening tellen in het kosten-dashboard mee als software-uitgave, ook wanneer de tegenpartij nog niet aan een centrale leverancier gekoppeld is (het grootboek-vangnet).')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
