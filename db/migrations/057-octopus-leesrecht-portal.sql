-- 057 - leesrecht op de Octopus-import voor de portal-rol: het
-- organisatie-dashboard (relatie-verkenner) draait op portal en migratie
-- 056 grantte alleen communicatie en kosten.

GRANT SELECT ON kosten.octopus_relatie, kosten.octopus_grootboek TO portal;
