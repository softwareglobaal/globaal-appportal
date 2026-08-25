-- 129: functionele mailboxen erbij als gedeelde dienst
-- Aanleiding: vraag Sufa 25-08-2026, volgt op #35.
--
-- Bij het ophalen van de e-mailadressen bleek dat sommige collega's er twintig
-- of meer gebruiken. Dat zijn geen persoonlijke adressen maar functionele
-- mailboxen: drie tot vier mensen doen de boekhouding van het hele bedrijf en
-- hebben dus het boekhoudadres van elke afdeling.
--
-- Zulke adressen horen bij een functie of een afdeling en niet bij een mens.
-- Ze in organisatie.account zetten kan ook niet: daar geldt dat een adres in
-- dezelfde periode bij een persoon hoort, en de tweede collega zou terecht
-- geweigerd worden.
--
-- Ze zijn hetzelfde soort ding als een gedeeld Claude- of Dropbox-account, dus
-- ze passen in organisatie.gedeeld_account met de toegangslijst ernaast. Er is
-- alleen een derde dienstwaarde nodig. Zelfde patroon als 124 en 127 gebruikten.
--
-- Het persoonlijke, unieke adres in organisatie.account blijft wat het is: het
-- enige dat naar een naam wijst, en daarmee de sleutel voor verantwoordelijkheid.
-- Bij een mailbox levert het register de kring op die toegang had, geen naam.

ALTER TABLE organisatie.gedeeld_account
    DROP CONSTRAINT IF EXISTS gedeeld_account_dienst_check;

ALTER TABLE organisatie.gedeeld_account ADD CONSTRAINT gedeeld_account_dienst_check
    CHECK (dienst IN ('claude', 'dropbox', 'mailbox'));
