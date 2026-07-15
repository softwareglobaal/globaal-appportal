-- 068 - partij-leverancier-koppelingen, eerste curatieronde (akkoord
-- Shaniel 2026-07-15: "koppel maar").
--
-- De kolom "Werkelijk betaald" in het kosten-dashboard loopt via
-- kern.partij.leverancier_id; de productie-meting toonde dat maar 4 van
-- de 1.828 partijen gekoppeld waren. Dit zijn de 20 naam-matches die de
-- machine voorstelde en een mens bevestigde (exacte naam of duidelijke
-- prefix van een leverancier met een softwarekaart). Idempotent en op
-- naam gematcht, zodat een partij-herimport de koppeling niet breekt;
-- alleen lege leverancier_id's worden gevuld.

UPDATE kern.partij p
   SET leverancier_id = l.id
  FROM (VALUES
    ('microsoft ireland operations ltd',          'Microsoft'),
    ('dropbox international unlimited company',   'Dropbox'),
    ('dropbox international unlimited  company',  'Dropbox'),
    ('pipedrive ou',                              'Pipedrive'),
    ('desktime',                                  'DeskTime'),
    ('monday.com ltd',                            'Monday.com'),
    ('zoom communications, inc.',                 'Zoom'),
    ('zoom video communcation',                   'Zoom'),
    ('zoom video communications inc.',            'Zoom'),
    ('hovercode',                                 'Hovercode'),
    ('zapier inc',                                'Zapier'),
    ('zoho corporation pte ltd',                  'Zoho'),
    ('teamleader orbit bv',                       'Teamleader'),
    ('teamleader nv',                             'Teamleader'),
    ('canva pty ltd abn 80158929938',             'Canva'),
    ('wetransfer b.v.',                           'WeTransfer'),
    ('calendly llc',                              'Calendly'),
    ('pandadoc inc',                              'PandaDoc'),
    ('setmore',                                   'Setmore')
  ) AS v(partij_naam, leverancier_naam)
  JOIN kern.leverancier l ON lower(btrim(l.naam)) = lower(v.leverancier_naam)
 WHERE lower(btrim(p.naam)) = v.partij_naam
   AND p.leverancier_id IS NULL;

-- NB: er stonden twee spellingen van "Dropbox International Unlimited
-- Company" in de lijst (enkele en dubbele spatie); beide hierboven.
-- De vierde Dropbox-variant en verdere partijen volgen in latere
-- curatierondes; de matchvoorstellen-query staat in TECHNICAL-REFERENCE
-- 14.7C-context en het kosten-dashboard toont wat nog los staat.
