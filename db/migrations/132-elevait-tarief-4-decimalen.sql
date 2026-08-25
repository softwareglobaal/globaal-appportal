-- 132: Uurtarief tot 4 decimalen (Elevait)
-- Aanleiding: vraag Shaniel 25-08-2026. Het uurtarief was numeric(12,2) en
-- rondde de invoer af op centen. Een uurtarief is een rekenfactor, geen
-- geldbedrag: bij 201 uur maakt een tienduizendste per uur al centen uit in
-- het eindloon. De kolom wordt numeric(12,4); het berekende loonbedrag zelf
-- blijft op 2 decimalen (afronden gebeurt een keer, aan het eind).

ALTER TABLE elevait.uurtarief
    ALTER COLUMN uurtarief TYPE numeric(12,4);
