-- 191: Organisatie kosten leest de btw-opvolging uit het BTW dashboard (schema btw).
--
-- Waarom: de liquiditeitsprognose, de fiscale schulden en de gaten van Organisatie kosten
-- houden rekening met de btw die betaald moet worden, de openstaande schulden bij de FOD
-- en de documenten die ontbreken voor de btw-aangifte. Het BTW dashboard (Joan) is de
-- eigenaar van die gegevens; Organisatie kosten leest alleen, schrijft nooit.
--
-- Van btw.firma alleen de koppeling (code, naam, Octopus-dossier), geen contactgegevens
-- van boekhouders. Geen gebruikers, mails, notities of audit-log.

GRANT USAGE ON SCHEMA btw TO doorbelasting_app;
GRANT SELECT (id, code, naam, octopus_dossier, heeft_myminfin, actief) ON btw.firma TO doorbelasting_app;
GRANT SELECT ON btw.schuld, btw.officiele_stand, btw.schatting, btw.betaling, btw.ontbrekend TO doorbelasting_app;
