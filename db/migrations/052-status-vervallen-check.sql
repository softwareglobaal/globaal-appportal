-- 052 - reparatie op 051: de CHECK-constraint op de statuskolom (uit
-- migratie 002) kende "Vervallen" nog niet, waardoor de status-omzetting
-- van de vervallen Proximus-nummers blokkeerde.

ALTER TABLE communicatie.nummer
    DROP CONSTRAINT ck_nummer_status;
ALTER TABLE communicatie.nummer
    ADD CONSTRAINT ck_nummer_status
    CHECK (status IN ('Actief', 'Niet-actief', 'Vervallen', 'Onbekend'));
