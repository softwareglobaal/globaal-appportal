-- 093: HR-app mag de ontwikkelcijfers van zijn eigen repo lezen
-- Aanleiding: vraag Shaniel 2026-07-29 - op het HR-dashboard moet te zien
-- zijn hoeveel tijd er via Claude Code aan het dashboard is gebouwd en
-- hoeveel tijd er in het dashboard zelf wordt doorgebracht. Het eerste staat
-- in schema ontwikkeling (migratie 074), het tweede in hr.app_gebruik.
-- Dit is uitsluitend LEESRECHT: de HR-app schrijft nooit in ontwikkeling.
-- De omgekeerde lijn blijft staan: de AI-lagen en de ontwikkelverzamelaar
-- lezen schema hr niet.

GRANT USAGE ON SCHEMA ontwikkeling TO hr_app;
GRANT SELECT ON ontwikkeling.cc_event, ontwikkeling.git_dag,
                ontwikkeling.gebruiker_koppeling, ontwikkeling.app,
                ontwikkeling.dag TO hr_app;

-- De verzamelaar ontdekt repos zelf en zette globaal-hr er kaal in; hier
-- krijgt hij zijn nette naam en adres, zoals de andere apps in migratie 074.
INSERT INTO ontwikkeling.app (repo, naam, url)
VALUES ('globaal-hr', 'HR-dashboard (HDS)', 'https://hr.globaal.be')
ON CONFLICT (repo) DO UPDATE
   SET naam = EXCLUDED.naam,
       url = coalesce(nullif(ontwikkeling.app.url, ''), EXCLUDED.url);
