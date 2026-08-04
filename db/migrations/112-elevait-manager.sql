-- 112: Manager-agent Elevait
-- Aanleiding: gesprek Shaniel 04-08-2026. Elke agent kijkt in zijn eigen
-- koker; niemand kijkt erover heen. De manager-agent doet dat wel: hij houdt
-- toezicht op de andere agents, bewaakt de beloftes en houdt bij wat er
-- blijft liggen.
--
-- Mandaat, expliciet vastgelegd omdat een naam op den duur een mandaat wordt:
-- hij leidt de UITVOERING, jullie houden het GEZAG. Hij beslist niets over
-- mensen en niets over geld, hij wijzigt geen regels van andere agents, en hij
-- communiceert nooit naar buiten. Herstelacties stelt hij voor; een mens keurt
-- goed, net als bij de gezondheidsagent.

CREATE TABLE IF NOT EXISTS elevait.open_eindje (
    id           bigserial PRIMARY KEY,
    wat          text NOT NULL,
    toelichting  text NOT NULL DEFAULT '',
    categorie    text NOT NULL DEFAULT 'overig'
                 CHECK (categorie IN ('personeel', 'financien', 'juridisch',
                                      'techniek', 'commercieel', 'overig')),
    wie          text NOT NULL DEFAULT '',
    sinds        date NOT NULL DEFAULT CURRENT_DATE,
    opgelost     boolean NOT NULL DEFAULT false,
    opgelost_op  timestamptz,
    opgelost_door text NOT NULL DEFAULT '',
    aangemaakt_op timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_elevait_open_eindje_open
    ON elevait.open_eindje (opgelost, sinds);

-- De eindjes die nu al bekend zijn uit de gesprekken. Zonder bedragen: die
-- horen op de interne pagina, niet in een repo.
INSERT INTO elevait.open_eindje (wat, toelichting, categorie, wie, sinds)
SELECT * FROM (VALUES
  ('Opleidingsbudget vaststellen',
   'Regeling 10 in het regelingen-document staat op "wordt later vastgesteld".',
   'personeel', 'Shaniel en Mehdi', DATE '2026-07-28'),
  ('Juridische toets op de regelingen',
   'Drie punten: wettelijk minimum vakantiedagen, regels bij langere ziekte, en of de kennismakingsweek binnen de proeftijd moet vallen.',
   'juridisch', 'jurist', DATE '2026-07-28'),
  ('Bedrag en ingangsdatum interne verrekening Globaal',
   'De post staat als PM in het kostenregister; zonder bedrag klopt het maandtotaal niet.',
   'financien', 'Shaniel', DATE '2026-07-28'),
  ('Bedragen van de AI-abonnementen invullen',
   'ElevenLabs, ChatGPT en Gemini staan als PM in het register.',
   'financien', 'Shaniel', DATE '2026-08-03'),
  ('Staat het Claude-abonnement op Elevait of op Globaal',
   'Bepaalt of het in dit kostenregister thuishoort. De API loopt al via de Elevait-workspace.',
   'financien', 'Shaniel', DATE '2026-08-03'),
  ('Vaste werktijden afspreken met de eerste medewerker',
   'Regeling 1: er gelden vaste werktijden, de exacte tijden worden bij aanname vastgelegd.',
   'personeel', 'Shaniel en Mehdi', DATE '2026-07-28'),
  ('Contractsjabloon naar Surinaams arbeidsrecht',
   'Nodig voor fase 2 van de HR-agent; hoort door een jurist opgesteld te worden.',
   'juridisch', 'jurist', DATE '2026-07-28')
) AS v(wat, toelichting, categorie, wie, sinds)
WHERE NOT EXISTS (SELECT 1 FROM elevait.open_eindje);

INSERT INTO elevait.definitie (sleutel, term, definitie) VALUES
  ('open-eindje', 'Open eindje',
   'Iets waarvan is gezegd dat het later zou gebeuren en dat sindsdien niet is gebeurd. De manager-agent houdt ze bij met de datum waarop ze ontstonden, zodat "later" een leeftijd krijgt en niet oneindig kan duren.'),
  ('manager-agent', 'Manager-agent',
   'De agent die over de kokers heen kijkt: hij houdt toezicht op de andere agents, bewaakt de beloftes van het bedrijf en houdt de open eindjes bij. Hij leidt de uitvoering, de oprichters houden het gezag: hij beslist niets over mensen of geld en stelt herstelacties alleen voor.')
ON CONFLICT (sleutel) DO NOTHING;
