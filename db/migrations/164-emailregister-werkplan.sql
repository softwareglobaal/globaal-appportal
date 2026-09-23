-- 164: Werkplan op het e-mailregister: wanneer is een adres af.
--
-- Aanleiding: vergadering 22-09-2026. Angela: "kunnen we niet een planning
-- maken ... met checks van, oke, dit is al gedaan. Anders gaan we geen
-- progres hebben", en later "ik weet niet waar ik moet starten, wat ik zou
-- moeten controleren". Het e-mailtabblad krijgt daarom een paneel Voortgang
-- per domein, kleinste blok bovenaan, en een filter "Nog te doen".
--
-- Alleen woordenboek: het vinkje wordt berekend uit de kolommen die er al zijn
-- (behouden, doel, verantwoordelijke_persoon_id). Een aparte afvinktabel zou
-- een tweede lijst zijn die gaat afwijken van het register zelf.
--
-- Keuze in de definitie van af: Elimineren is genoeg. Een adres dat
-- verdwijnt hoeft geen doel of eigenaar meer te krijgen; op h-architects.be
-- staan 138 van de 148 adressen al uit, en daar een doel voor laten zoeken is
-- werk voor niets. Verifieren telt niet als af: dat is nog een open vraag.

BEGIN;

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('email_werkplan', 'Werkplan',
     'De voortgang van het opruimen van het e-mailregister, per domein, met het kleinste domein bovenaan: daar begin je. Per domein staat hoeveel adressen af zijn en wat er nog ontbreekt (niet beoordeeld, te verifieren, zonder doel, zonder verantwoordelijke). Het vinkje wordt berekend uit het register zelf en niet apart bijgehouden, zodat het nooit afwijkt van wat er echt ingevuld is. Een klik op een domein toont alleen wat daar nog niet af is.'),
    ('email_af', 'Af',
     'Een e-mailadres is af als er een beslissing over ligt die niemand meer hoeft na te zoeken: ofwel Elimineren, ofwel Behouden met een doel en een verantwoordelijke. Een adres dat verdwijnt hoeft geen doel of eigenaar meer te krijgen. Verifieren telt niet als af, want dan is de vraag nog open. Een adres zonder oordeel is nooit af.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;

COMMIT;
