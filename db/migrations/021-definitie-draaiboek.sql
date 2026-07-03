-- 021 — woordenboek: de draaiboek-begrippen (meetings 2026-07-03, Mehdi).
--
-- Terminologie eerst, dan pas het datamodel — het kernonderscheid draaiboek vs
-- projectmanagement draagt het hele draaiboek-platform (het ★-einddoel op de TODO).

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
('draaiboek', 'Draaiboek',
 'Het protocol (playbook) van één proces: alle fases en deeltaken van A tot Z, in volgorde en zonder fouten. Een draaiboek legt het proces vast, maakt automatisering mogelijk en levert data op. Niet verwarren met projectmanagement.'),
('projectmanagement', 'Projectmanagement',
 'Veel projecten tegelijk op grove lijnen bewaken (bv. Monday). Werkt pas goed als elk project een draaiboek volgt — projectmanagement zonder draaiboek heeft geen zin. Deeltaken en micromanagement horen in het draaiboek, niet hier.'),
('fase', 'Fase',
 'Een hoofdstuk van een draaiboek: een geordende groep stappen (bv. "ontwerpfase", "uitvoeringsfase"). Fases maken de voortgang leesbaar: je ziet in één blik waar een run staat.'),
('stap', 'Stap',
 'De kleinste eenheid van een draaiboek: één taak of deeltaak, met volgorde en eventueel een afhankelijkheid ("pas na stap X") en een op te leveren resultaat (bv. een verslag).'),
('run', 'Run',
 'Een draaiboek toegepast op één concreet dossier of project: dezelfde stappen, maar mét status, wie en wanneer per stap. De run is het sequentiële geheugen — "verslag 2 is klaar, dus nu verslag 3".');
