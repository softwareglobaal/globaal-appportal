-- 042 - woordenboek-term voor het nieuwe graaf-element "Extern contact"
-- (de hover op elk graaf-element toont de definitie uit kern.definitie).

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
    ('extern_contact', 'Extern contact',
     'Een externe partij (klant, leverancier of andere beller) waarmee via een van onze telefoonnummers contact is geweest, afgeleid uit het Xelion-oproeparchief van de laatste 90 dagen. Zelfde persoon met meerdere nummernotaties telt als een contact (kanonieke nummervorm). Anonieme bellers staan er niet in.')
ON CONFLICT (sleutel) DO UPDATE
   SET term = EXCLUDED.term, definitie = EXCLUDED.definitie;
