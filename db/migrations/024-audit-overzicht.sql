-- 024 — leesbare audit: view die per wijziging alleen de véranderde velden toont.
--
-- kern.audit bewaart volledige oude/nieuwe rijen (jsonb); deze view maakt daar
-- het antwoord van: "wat is er precies veranderd" als {veld: {van, naar}}.
-- Bij INSERT toont hij de nieuwe rij, bij DELETE de verwijderde.

CREATE VIEW kern.audit_overzicht AS
SELECT id, op, rol, app_gebruiker, tabel, rij_id, actie,
       CASE
           WHEN actie = 'UPDATE' THEN
               (SELECT jsonb_object_agg(key, jsonb_build_object('van', oud -> key,
                                                                'naar', nieuw -> key))
                  FROM jsonb_each(nieuw)
                 WHERE oud -> key IS DISTINCT FROM nieuw -> key)
           WHEN actie = 'INSERT' THEN nieuw
           ELSE oud
       END AS wijzigingen
  FROM kern.audit;

GRANT SELECT ON kern.audit_overzicht TO portal;
REVOKE ALL ON kern.audit_overzicht FROM communicatie, vermogen, draaiboek, medewerker_writer;
