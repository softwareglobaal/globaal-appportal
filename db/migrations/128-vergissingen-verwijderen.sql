-- 128: vergissingen van vandaag mogen weg, historie niet
-- Aanleiding: vraag Sufa 25-08-2026, volgt op #31, #32, #33 en #34.
--
-- Het register sluit regels af met geldig_tot in plaats van ze te verwijderen,
-- en de schrijfrol heeft daarom geen DELETE. Dat is goed: zonder die grens kan
-- de app de historie wissen waar het register juist voor bestaat.
--
-- Er zit alleen een gat in. Typt iemand een adres verkeerd en haalt hij het
-- meteen weer weg, dan blijft er een afgesloten regel staan die beweert dat dat
-- adres een dag lang bij die collega hoorde. Zoek je later op wie dat adres op
-- 25 augustus had, dan krijg je een naam die er nooit bij hoorde. Dat is geen
-- rommel maar een onwaarheid, in een register dat over verantwoordelijkheid gaat.
--
-- Het onderscheid dat we willen: een regel die vandaag is aangemaakt en vandaag
-- weer weg gaat heeft nooit iets betekend en mag verdwijnen. Een regel van
-- gisteren of ouder is historie en moet blijven.
--
-- Dat is geen regel voor de app maar voor de database, net als de uniciteit:
-- alleen hier geldt hij voor alles wat schrijft. Vandaar een trigger, en pas
-- daarna het DELETE-recht. Zonder de trigger zou dat recht precies de grens
-- weghalen die we willen houden.
--
-- LET OP voor beheer: de trigger geldt ook voor de superuser. Moet er ooit
-- echt een oude regel weg, bijvoorbeeld op verzoek van iemand zelf, dan kan dat
-- met  SET session_replication_role = 'replica';  in dezelfde sessie. Dat is
-- bewust een handeling die je expres doet en niet per ongeluk.

CREATE OR REPLACE FUNCTION organisatie.alleen_vergissingen_verwijderen()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.geldig_van <> current_date THEN
        RAISE EXCEPTION
            'regel uit % mag niet verwijderd worden; sluit hem af met geldig_tot',
            OLD.geldig_van
            USING ERRCODE = 'restrict_violation';
    END IF;
    RETURN OLD;
END
$$;

DROP TRIGGER IF EXISTS tr_account_vergissing ON organisatie.account;
CREATE TRIGGER tr_account_vergissing
    BEFORE DELETE ON organisatie.account
    FOR EACH ROW EXECUTE FUNCTION organisatie.alleen_vergissingen_verwijderen();

DROP TRIGGER IF EXISTS tr_gedeeld_toegang_vergissing ON organisatie.gedeeld_toegang;
CREATE TRIGGER tr_gedeeld_toegang_vergissing
    BEFORE DELETE ON organisatie.gedeeld_toegang
    FOR EACH ROW EXECUTE FUNCTION organisatie.alleen_vergissingen_verwijderen();

DROP TRIGGER IF EXISTS tr_gedeeld_account_vergissing ON organisatie.gedeeld_account;
CREATE TRIGGER tr_gedeeld_account_vergissing
    BEFORE DELETE ON organisatie.gedeeld_account
    FOR EACH ROW EXECUTE FUNCTION organisatie.alleen_vergissingen_verwijderen();

-- Pas nu het recht erbij. De trigger bepaalt hoe ver het reikt.
GRANT DELETE ON organisatie.account,
                organisatie.gedeeld_toegang,
                organisatie.gedeeld_account TO medewerker_writer;
