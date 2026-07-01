-- 004 — gebruikers (multi) op e-mailadressen.
--
-- Een e-mailadres heeft één verantwoordelijke (aanspreekbaar), maar vaak
-- meerdere gebruikers die erop ingelogd zijn. Zelfde patroon als
-- nummer_gebruiker, zonder volgorde (een mailbox heeft geen belwachtrij).
-- Rechten: gedekt door de default privileges van migratie 002.

CREATE TABLE communicatie.emailadres_gebruiker (
    emailadres_id uuid NOT NULL REFERENCES communicatie.emailadres(id) ON DELETE CASCADE,
    persoon_id    uuid NOT NULL REFERENCES kern.persoon(id) ON DELETE RESTRICT,
    PRIMARY KEY (emailadres_id, persoon_id)
);
