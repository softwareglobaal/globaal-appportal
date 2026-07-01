-- 003 — belvolgorde (queue) op nummer-gebruikers.
--
-- De telefooncentrale werkt met een wachtrij per nummer: persoon 1 neemt eerst
-- op, dan persoon 2, enz. De gebruikerssectie in het Communicatie-dashboard
-- toont die volgorde; daarvoor krijgt de koppeltabel een positie (1 = eerste).

ALTER TABLE communicatie.nummer_gebruiker
    ADD COLUMN volgorde integer NOT NULL DEFAULT 0;
