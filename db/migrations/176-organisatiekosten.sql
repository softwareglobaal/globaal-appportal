-- 176: schema `doorbelasting` voor de app Organisatie kosten (werknaam Doorbelasting).
--
-- Wat de app doet: elke maand tonen wat elke firma van de groep aan gedeelde
-- kosten draagt, per land (Suriname, België, India), met bij elke regel de bron
-- en de redenering. Vervangt de statische kostenplaat van Angela
-- (kostenplaat.globaal.be). Repo softwareglobaal/globaal-doorbelasting.
--
-- Deze migratie maakt enkel het schema en de rol. De tabellen maakt de app zelf
-- bij de start (src/lib/schema.sql in de app-repo, idempotent) en vult ze uit
-- data/bron/ als ze leeg zijn. Het schema is eigendom van de app-rol, zodat die
-- zijn eigen tabellen kan aanmaken zonder CREATE-recht op de database.
--
-- Bewust GEEN leesrecht voor de rol `portal`: in doorbelasting.persoon_kost
-- komen later individuele lonen. Die horen niet in de portaal-MCP.
--
-- Bewust nog niet in de graaf: de app verwijst in fase 1 nog niet naar kern.
-- Firma's en personen komen uit een momentopname in de app-repo. Zodra de app
-- kern.firma en kern.persoon rechtstreeks leest, komt dat in een eigen migratie
-- met de knopen in graaf.py.
--
-- Eigen LOGIN-rol doorbelasting_app (wachtwoord via ALTER ROLE op de VM).

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'doorbelasting_app') THEN
        CREATE ROLE doorbelasting_app LOGIN;
    END IF;
END $$;

CREATE SCHEMA IF NOT EXISTS doorbelasting AUTHORIZATION doorbelasting_app;
GRANT USAGE, CREATE ON SCHEMA doorbelasting TO doorbelasting_app;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('doorbelasting.kostprijs', 'kostprijs (doorbelasting)',
     'Eigen kost per persoon plus werkplek plus directie-aandeel. De werkplek is '
     'huisvesting en gedeelde kosten in Suriname gedeeld door de voltijdsen. Per '
     'firma opgeteld volgens de verdeelsleutel.'),
    ('doorbelasting.marge', 'marge (doorbelasting)',
     'Eén opslag van 10% op de totale kost, voor elke firma, HDS inbegrepen. Geen '
     'buffer meer (afspraak 28-09-2026).'),
    ('doorbelasting.loonbelasting', 'loonbelastingreservering',
     'Loonbelasting berekend op de nettolonen maar niet afgedragen. Apart getoond, '
     'niet in het factuurbedrag tot er met de accountant beslist is.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
