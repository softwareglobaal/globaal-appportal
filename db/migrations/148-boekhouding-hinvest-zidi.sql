-- 148: H-Invest en Zidi Construct toevoegen aan boekhouding.firma.
--
-- Het Octopus-account ziet dertien dossiers, maar boekhouding.firma bevatte er
-- zes (de acht uit Joan's aanlevering, waarvan zes met een dossier). Alles wat
-- op die tabel steunt kent een dossier dus niet: de Openstaand-tab toont het
-- niet, en de MCP-connector (boekhouding.globaal.be/mcp) antwoordt
-- "Dossier X staat niet in boekhouding.firma" op elke vraag erover.
--
-- Twee dossiers die wel opgevolgd horen te worden ontbraken. Nummers nagemeten
-- tegen GET /dossiers op 14-09-2026:
--   111725 = "H-Invest (voordien H-Aannemingen )"
--   110906 = "Zidi Construct"
-- De naam hier is de opgekuiste variant, zoals bij de andere rijen.
--
-- volgen = true, zodat ze in de Openstaand-tab verschijnen met een eigen
-- verversknop; dat kost geen rapport-aanroepen zolang niemand op die knop
-- drukt. factureren = false: er is geen Monday-board voor deze twee, dus
-- factureren vanuit de app is niet aan de orde (boards.py blijft ongewijzigd).
-- Betaaltermijn 7 dagen, de standaard buiten H-Architects.

INSERT INTO boekhouding.firma (dossier_id, naam, betaaltermijn_dagen, volgen, factureren) VALUES
    (111725, 'H-Invest',      7, true, false),
    (110906, 'Zidi Construct', 7, true, false)
ON CONFLICT (dossier_id) DO NOTHING;

-- Brug naar de centrale firma-laag, zoals migratie 102 dat deed.
UPDATE boekhouding.firma b
   SET kern_firma_id = f.id
  FROM kern.firma f
 WHERE f.code = CASE b.dossier_id
                    WHEN 111725 THEN 'HINV'
                    WHEN 110906 THEN 'ZIDI'
                END
   AND b.kern_firma_id IS NULL;
