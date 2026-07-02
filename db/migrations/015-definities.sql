-- 015 — het woordenboek als data: kern.definitie (meeting 2026-07-02 avond).
--
-- Mehdi: "elke term moet een definitie hebben, iedereen moet die goed kunnen
-- zien, en als een term verandert moet dat op één plek". Die ene plek is deze
-- tabel: dashboards lezen term + definitie hieruit (kolomkoppen, tooltips,
-- woordenboek-pagina). DEFINITIEBOEK.md in de stack-repo blijft de leesbare
-- uitwerking en verwijst hierheen; de tabel is leidend voor de apps.
--
-- Terminologie-wijziging uit de meeting verwerkt: "Gefactureerd aan" heet nu
-- "Intern gefactureerd aan" (zonder "intern" kan het ook extern klinken —
-- externe facturatie aan klanten wordt hier niet bijgehouden), en
-- "Doorfactureren naar" heet "Interne doorfacturatie naar".
--
-- `sleutel` is stabiel (staat in code en in opgeslagen views); `term` en
-- `definitie` zijn de wijzigbare weergave. Hernoem dus nooit een sleutel.

CREATE TABLE kern.definitie (
    sleutel       text PRIMARY KEY,
    term          text NOT NULL,
    definitie     text NOT NULL,
    bijgewerkt_op timestamptz NOT NULL DEFAULT now()
);

INSERT INTO kern.definitie (sleutel, term, definitie) VALUES
-- Kolommen van het Communicatie-dashboard (sleutel = kolomsleutel in de views)
('telefoonnummer', 'Telefoonnummer',
 'Het nummer zelf — de resource. Elke andere kolom zegt iets over dit nummer.'),
('verantwoordelijke', 'Verantwoordelijke',
 'De ene persoon die aanspreekbaar en eigenaar is (accountable) — precies één, zodat niets eigenaarloos blijft. Altijd de 1e in de belvolgorde.'),
('backup', 'Backup',
 'De 2e persoon in de belvolgorde — neemt over als de verantwoordelijke niet kan opnemen.'),
('gefactureerd_aan', 'Intern gefactureerd aan',
 'De firma van de groep die de factuur van de leverancier ontvangt en betaalt (in de praktijk UnaBo). "Intern": facturatie aan externe klanten wordt hier niet bijgehouden.'),
('doorfactureren_naar', 'Interne doorfacturatie naar',
 'De firma van de groep aan wie de kost intern wordt doorgerekend — kan verschillen van wie de leveranciersfactuur ontvangt.'),
('gebruikt_voor', 'Gebruikt voor',
 'De firma (later ook klant of dossier) waarvoor de resource feitelijk gebruikt wordt, los van hoe er gefactureerd wordt.'),
('vaste_prijs', 'Vaste prijs',
 'Het vaste maandbedrag in euro excl. BTW voor de resource zelf. Leeg = onbekend of variabel. Verbruik (belminuten, data) valt hier niet onder.'),
('gebruikers', 'Gebruikers',
 'De personen die de resource gebruiken, genummerd in belvolgorde: 1 neemt eerst op, 2 is de backup.'),
('leverancier', 'Leverancier',
 'De externe partij die levert en die je betaalt (bv. Close Call BV, Mega, Proximus). Let op: op de factuur staat vaak een andere naam dan het platform.'),
('platform', 'Platform',
 'De software of dienst waarop iets draait (bv. Xelion). De leverancier factureert; het platform is wat je gebruikt — twee verschillende dingen.'),
('type', 'Type',
 'Het soort nummer (bv. vast, mobiel, virtueel) — keuzelijst, geen vrije tekst.'),
('doel', 'Doel',
 'Waarvoor het nummer dient (bv. algemeen nummer sales). Niet "functie" — dat woord is voor personen.'),
('land', 'Land',
 'Het land van het nummer; wordt automatisch afgeleid uit het nummerformaat.'),
('afdeling', 'Afdeling',
 'De organisatorische eenheid (functiegebied) waar de resource bij hoort — kan de firma-grens overschrijden.'),
('status', 'Status',
 'Actief / Niet-actief / Onbekend. Niet-actief verwijdert niets: het nummer blijft bewaard en vindbaar.'),
-- Algemene begrippen (woordenboek-pagina; geen kolommen)
('firma', 'Firma',
 'De juridische entiteit die contracten sluit, factureert en een BTW-nummer heeft (de 13 firma''s van de groep). Niet verwarren met afdeling.'),
('rol', 'Rol',
 'De verantwoordelijkheidslaag van een persoon: Lid / Hoofd / Partner / Management — bepaalt rechten en zichtbaarheid.'),
('werkgever', 'Werkgever',
 'De firma waar een persoon in dienst is (één). Los daarvan kan iemand diensten verrichten voor meerdere firma''s ("diensten-voor").'),
('facturatiecyclus', 'Facturatiecyclus',
 'Hoe vaak er gefactureerd wordt: wekelijks, maandelijks, per kwartaal of jaarlijks — kan per software of platform verschillen. Jaarcontract voor zekere zaken, maandelijks voor onzekere; de keuze wordt datagedreven.'),
('verbruik', 'Verbruik',
 'De variabele kosten van een resource (belminuten, data, gebruik) — apart van de vaste prijs. Nodig om houden-of-schrappen datagedreven te beslissen.');
