-- 071: kosten.firma koppelen aan kern.firma waar dat nog ontbrak.
-- Energie Efficient had geen kern_firma_id, waardoor EE-aankoopfacturen in
-- het kosten-dashboard nooit aan de eigen firma toegewezen werden (ze vielen
-- terug op het groepstotaal); HDS en Zidi idem, voor de volledigheid.
-- Idempotent: alleen lege koppelingen worden gevuld.

UPDATE kosten.firma SET kern_firma_id = '98459ba1-1a02-40e0-b4bb-c6f95272ff50'
 WHERE id = 'Energie Efficient' AND kern_firma_id IS NULL;

UPDATE kosten.firma SET kern_firma_id = '12917508-f678-4d22-bf3c-963c671fa060'
 WHERE id = 'HDS' AND kern_firma_id IS NULL;

UPDATE kosten.firma SET kern_firma_id = '6b2ad865-de03-4d9b-957b-3f25291360c4'
 WHERE id = 'Zidi' AND kern_firma_id IS NULL;
