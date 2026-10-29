-- 198: aanwezigheid van de Xelion-gebruikers en de instelling van elke lijn,
-- voor het overzicht Gemiste oproepen in de communicatie-app (29-10-2026).
--
-- Vraag van Siyan: krijgen de collega's de oproepen niet, of nemen ze niet op?
-- Het belarchief (034, 035) zegt hoelang een gemiste oproep rinkelde en wie op
-- dat moment in gesprek was, maar niet wiens toestel aanstond. Xelion bewaart
-- dat niet, het toont alleen de toestand van nu. De poller van de
-- communicatie-app legt die toestand daarom elke minuut vast, als tijdvakken
-- per gebruiker: een nieuwe rij alleen als er iets verandert, anders schuift
-- `tot` op.
--
-- xelion_lijn is de spiegel van de lijninstellingen: belbeleid, wachttijd per
-- persoon, openingsuren (dag/nacht-schema), terugval en voicemail, plus de
-- belrij zoals Xelion ze echt afwerkt (op skill, alleen wie inkomend krijgt).
-- Daarmee kan het overzicht zeggen of een oproep buiten de openingsuren viel
-- en bij wie hij gerinkeld heeft.

CREATE TABLE IF NOT EXISTS communicatie.xelion_aanwezigheid (
    id             bigserial PRIMARY KEY,
    gebruiker_oid  text NOT NULL,              -- xelion_gebruiker.oid
    computer       boolean NOT NULL,           -- belsoftware op de computer aangemeld
    gsm            boolean NOT NULL,           -- gsm-app gekoppeld (push, staat meestal altijd aan)
    status         text NOT NULL DEFAULT '',   -- aanwezigheid in Xelion: available, online, offline, dont_disturb, ...
    niet_storen    boolean NOT NULL DEFAULT false,
    toestellen     text NOT NULL DEFAULT '',   -- namen van de aangemelde toestellen
    van            timestamptz NOT NULL,
    tot            timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_xelion_aanwezigheid_gebruiker_van
    ON communicatie.xelion_aanwezigheid (gebruiker_oid, van);

CREATE TABLE IF NOT EXISTS communicatie.xelion_lijn (
    oid            text PRIMARY KEY,
    naam           text NOT NULL DEFAULT '',
    extern_nummer  text NOT NULL DEFAULT '',
    beleid         text NOT NULL DEFAULT '',   -- lineHuntingPolicy, bv. skillBased
    wachttijd_sec  integer,                    -- lineHuntingTimeout: zo lang rinkelt het per persoon
    status         text NOT NULL DEFAULT '',   -- automatic (volgt het schema), available, unavailable
    schema_naam    text NOT NULL DEFAULT '',
    open_uren      jsonb,                      -- [{dag, van, tot}] uit het dag/nacht-schema, Belgische tijd
    terugval       text NOT NULL DEFAULT '',   -- naam van de terugvallijn
    voicemail      boolean NOT NULL DEFAULT false,
    doorschakeling text NOT NULL DEFAULT '',
    leden          jsonb,                      -- [{naam, gebruiker_oid, positie, skill, inkomend}]
    gesynct_op     timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.xelion_aanwezigheid TO communicatie;
GRANT SELECT, INSERT, UPDATE, DELETE ON communicatie.xelion_lijn TO communicatie;
GRANT USAGE, SELECT ON SEQUENCE communicatie.xelion_aanwezigheid_id_seq TO communicatie;
