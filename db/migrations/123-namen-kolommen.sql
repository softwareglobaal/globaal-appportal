-- 123: eigen kolommen op de namenlijst (/namen)
-- Aanleiding: vraag Sufa 21-08-2026 via Shaniel. Hij wil op zijn pagina kolommen
-- kunnen toevoegen zoals in Notion, met een soort per kolom, en de lijst kunnen
-- groeperen.
--
-- BELANGRIJK, de reden dat dit een eigen tabel is en geen uitbreiding van
-- kern.persoon: de namenlijst is bewust kaal (alleen voornaam en afdeling). Wat
-- hier bijkomt is NIET personeelsinformatie uit het HR-domein, maar eigen
-- aantekeningen van de gebruiker bovenop die lijst. Daarom staan de waarden los
-- van de persoonsgegevens en hangen ze aan de gebruiker die ze maakte.
--
-- Per gebruiker, niet gedeeld: het gaat om aantekeningen OVER collega's. Wie ze
-- wil delen, doet dat bewust; standaard ziet alleen de maker ze.

CREATE TABLE IF NOT EXISTS organisatie.namen_kolom (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    eigenaar      text NOT NULL,                       -- Authentik-gebruikersnaam
    naam          text NOT NULL,
    soort         text NOT NULL DEFAULT 'tekst'
                  CHECK (soort IN ('tekst', 'selectie', 'vinkje', 'datum', 'getal')),
    -- Alleen bij soort 'selectie': de keuzemogelijkheden, in volgorde.
    opties        jsonb NOT NULL DEFAULT '[]'::jsonb,
    volgorde      int NOT NULL DEFAULT 0,
    aangemaakt_op timestamptz NOT NULL DEFAULT now(),
    UNIQUE (eigenaar, naam)
);

CREATE TABLE IF NOT EXISTS organisatie.namen_waarde (
    kolom_id      uuid NOT NULL REFERENCES organisatie.namen_kolom(id) ON DELETE CASCADE,
    persoon_id    uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE CASCADE,
    waarde        text NOT NULL DEFAULT '',
    bijgewerkt_op timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (kolom_id, persoon_id)
);

CREATE INDEX IF NOT EXISTS ix_namen_kolom_eigenaar
    ON organisatie.namen_kolom (eigenaar, volgorde);

-- Rechten: de organisatie-app schrijft, het portaal leest niet mee (dit zijn
-- persoonlijke aantekeningen, geen bedrijfsgegevens).
GRANT SELECT, INSERT, UPDATE, DELETE
    ON organisatie.namen_kolom, organisatie.namen_waarde TO medewerker_writer;
