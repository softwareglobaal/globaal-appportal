# Archisnapper-analyse: opleveringsverslagen en vaste punten

Datum: 15-09-2026. Bron: `/H-Architects bvba/Apps/Archisnapper/<project>/Reports/` via de Dropbox-MCP (fetch, grens 5 MiB per bestand).
Gelezen: 33 pdf's (31 echte verslagen uit 25 projecten, verslagdata januari 2020 t/m juli 2025, plus 2 testsjablonen 2001-3 en 2001-4).
Elke bewering hieronder draagt het verslagnummer als bron. Wat niet gelezen kon worden staat als zodanig gemeld.

Gelezen verslagen: 1828-8, 1939-1, 1944-4, 2001-3, 2001-4, 2004-6, 2004-13, 2004-47, 2008-16, 2033-3, 2056-11, 2082-2, 2089-8, 2103-13, 2110-1, 2110-41, 2110-44, 2118-3, 2138-1, 2185-6, 2190-1, 2190-6, 2191-1, 2197-15, 2199-7, 2220-1, 2231-1, 2231-6, 2249-1, 2282-5, 2359-2, 2410-1, 2444-1.

---

## OPDRACHT A: opleveringsverslagen

### A.0 Wat gevonden is en wat niet

**Voorlopige oplevering: 9 echte verslagen gevonden en gelezen** (plus 2 lege testsjablonen 2001-3/2001-4):

| Nr | Project | Datum verslag | Vorm | Taal |
|---|---|---|---|---|
| 2008-16 | Corneel Vermijlenlaan 39, Antwerpen | 09-07-2021 | Apart Archisnapper-sjabloon "Proces-verbaal van voorlopige oplevering", met handtekeningblok | NL |
| 1828-8 | Nieuwstraat 81, Kontich (3 appartementen) | 23-05-2022 | Zelfde PV-sjabloon, gebreken per ruimte/appartement, 30 blz. foto's | EN (in NL-sjabloon) |
| 2033-3 | Buxuslaan 28, Hoevenen | 09-01-2023 | Gewoon werfverslag; status "Wind en Waterdicht fase - Voorlopige Oplevering"; alleen gevelfoto's | NL |
| 2089-8 | Lange Boomgaardstraat 15, Gent | 26-06-2023 | Gewoon werfverslag met "PV DELIVERY"-tekst in Status | EN |
| 2118-3 | Jan Avondstraat 16, Wilsele | 29-08-2023 | Idem "PV DELIVERY" | EN |
| 2103-13 | Vlierbeeklaan 32, Kessel-Lo | 07-09-2023 | Gewoon werfverslag met "PV voorlopige oplevering"-tekst in Status | NL/EN |
| 2056-11 | Azaleaweg 35, Hemiksem | 31-10-2023 | Idem; opvolging van opleveringsvergadering 15-09-2023 | NL |
| 2199-7 | Bergstraat 25, Herselt | 03-06-2025 (bezoek 26-09-2024) | Idem, tweetalig "PV Provisional Handover / PV voorlopige oplevering" | EN + NL |
| 2004-47 | Bisschoppenhoflaan 27-29, Deurne | 07-10-2024 | "aanvullend rapport van de sitebezoek na de voorlopige oplevering": restlijst per gebouw + uitgevoerde werken | EN + NL |

**Definitieve oplevering: geen enkel verslag gevonden.** Eerlijk gezegd:
- Zoekopdrachten "definitieve oplevering" (40 treffers), "proces-verbaal oplevering" (37), "final acceptance" (16), "provisional acceptance" (11) geven allemaal dezelfde bestanden: het zijn PV's van voorlopige oplevering die de vaste zin "gaat automatisch over naar een definitieve oplevering" bevatten.
- Gerichte zoekopdrachten "PV definitieve oplevering", "final delivery / definitive acceptance / PV final", "waarborgtermijn definitieve oplevering aanvaard" en "definitieve oplevering proces-verbaal ondertekend" geven **0 treffers**.
- Drie treffers konden niet gelezen worden omdat ze groter zijn dan de fetch-grens van 5 MiB en geen kleinere sent_history-versie hebben: 2463-1 (Frans de Cortlaan 55, 8,8 MB), 2359-6 (Liemingenstraat 12, 7,6 MB; de sent_history-kopie is 42,7 MB) en 2197-16 (Vrijheidstraat 9, 8,7 MB). Op basis van het zoekpatroon (zelfde combinatie van termen als de andere PV's) zijn dit hoogstwaarschijnlijk ook PV's van voorlopige oplevering, maar dat is niet geverifieerd. Actie: die drie lokaal downloaden (Dropbox-API of "Make available offline") en met pypdf lezen.
- Conclusie: H-Architects heeft in Archisnapper de definitieve oplevering nooit als apart verslag opgemaakt. De praktijk volgens de eigen vaste tekst is dat de voorlopige oplevering **automatisch** overgaat in een definitieve op een vaste datum (2008-16, 2103-13, 2056-11, 2199-7, 2089-8, 2118-3) of "na 1 jaar" (sjabloon 2001-3/2001-4).

### A.1 Opbouw PV voorlopige oplevering, zoals in de praktijk

Twee varianten bestaan naast elkaar.

**Variant 1: apart Archisnapper-rapporttype "Proces-verbaal van voorlopige oplevering"** (2008-16, 1828-8, sjabloon 2001-3/2001-4). Opbouw:

1. Kop: "H-Architects BVBA / Herfstlaan 65 / 3010 Kessel-Lo / BE0646.974.162"; titel "Proces-verbaal van voorlopige oplevering voor project <nr adres>"; projectnaam, korte omschrijving (bv. "Renovatie eengezinswoning"), adres, "Nummer: 2008-16", "Datum: 09 juli 2021" (zonder uur).
2. Inleidende PV-tekst (letterlijk, 2008-16):
   > "PV voorlopige oplevering
   > Het betreft de voorlopige oplevering voor project 2008 Corneel Vermijlenlaan 39, 2100 Antwerpen.
   > Dit gebeurt in aanwezigheid van de bouwheer, de algemene aannemer en de architect.
   > De voorlopige oplevering wordt aanvaard onder voorbehoud van de hierbij gevoegde genummerde en door partijen gekorttekende opmerkingen, waaraan moet worden voldaan uiterlijk op vrijdag 27 augustus 2021. De voorlopige oplevering gaat automatisch over naar een definitieve oplevering, op vrijdag 27 augustus, als aan de opgesomde opmerkingen is voldaan.
   > De benodigde documenten, attesten en keuringsverslagen voor de opmaak van het asbuilt-dossier dienen eveneens ten laatste op deze einddatum, 27 augustus 2021, aangeleverd te worden aan het architectenkantoor.
   > Opmerkingen op dit proces-verbaal dienen schriftelijk én binnen de 8 werkdagen overgemaakt te worden aan het architectenkantoor."
   Het sjabloon 2001-3/2001-4 (30-08-2022) heeft een iets andere formule met placeholders:
   > "Dit verslag geldt als proces verbaal voor de voorlopige oplevering voor project projectnr projectadres. Dit gebeurt in aanwezigheid van de opdrachtgever, de algemene aannemer en de architect. De voorlopige oplevering wordt aanvaard onder voorbehoud van de voorafgaande werfverslagen en de hieronder gevoegde genummerde en door partijen gekorttekende opmerkingen, waaraan moet worden voldaan uiterlijk op weekdag datum maand jaar. De voorlopige oplevering gaat na 1 jaar automatisch over naar een definitieve oplevering, indien de opgesomde opmerkingen werden voldaan. De benodigde documenten, attesten en keuringsverslagen voor de opmaak van het asbuilt-dossier dienen eveneens ten laatste op deze einddatum, aangeleverd te worden aan het architectenkantoor. Opmerkingen op dit proces-verbaal dienen schriftelijk én binnen de 8 werkdagen overgemaakt te worden aan het architectenkantoor."
   (Let op de spelfout "gekorttekende" die in alle exemplaren staat; bedoeld is "geparafeerde/ondertekende".)
3. Tabel "Contactpersonen en aanwezigen": kolommen Rol | Naam | Contactgegevens | Aanw. (en in 2008-16 ook "Uitgenodigd"); vinkje of kruis per persoon; rol met firma tussen haken, bv. "Aannemer, Parket en binnendeuren [Timber Design]".
4. Vaste tekst veiligheid en 10-jarige aansprakelijkheid (letterlijk, in bijna alle verslagen sinds 2021):
   > "Veiligheid:
   > Het veiligheid- en gezondheidsplan van de veiligheidscoördinator is van toepassing tijdens de hele duur van de werken.
   > De planning van de werken dient tijdig te worden doorgegeven aan de veiligheidscoördinator.
   > 10-jarige aansprakelijkheid:
   > De verzekeringsfiches voor de 10-jarige burgerlijke aansprakelijkheid volgens de wet Peeters-Borsus (31 mei 2017, BS 9 juni 2017) dienen aangeleverd te worden door alle aannemers die een aandeel hebben in de constructie tot wind- en waterdichte staat van de werken."
   Engelse versie (2089-8): "Safety: The safety and health plan of the safety coordinator applies throughout the duration of the works. The schedule of works should be communicated to the safety coordinator in a timely manner. 10-year liability: Insurance sheets for the 10-year civil liability according to the Peeters-Borsus Act (31 May 2017, BS 9 June 2017) must be supplied by all contractors who have a share in the construction to wind and watertight condition of the works."
5. Tabel "Opmerkingen": kolommen Opmerking | Omschrijving | Verantwoordelijke. Per categorie (kop "Algemeen/General", "Riolering/Sewerage Works" ...) genummerde punten `<verslagnr>.<volgnr>` met vlag NOK/OK, titel, datum, tekst, foto's en de verantwoordelijke (naam van de aannemer of bouwheer). Voorbeelden 2008-16: "NOK 16.1 Afwerken keuken" (Kvik Keukens), "16.2 Afwerken maatwerkmeubilair gelijkvloers" (VHM), "16.3 Plaatsing binnendeuren, plinten en verdere afwerking" (Timber Design), "16.4 Afwerken achtergevel", "16.5 Toilet gelijkvloers", "16.6 Nieuwe UTP", "16.7 Afwerken badkamer" (Harmonie Bouw). In 1828-8 is de indeling per ruimte: "8.1 Entry Hall + Stair Hall (All floors)", "8.2 Apartment 1", "8.3 Apartment 2", "8.4 Apartment 3", "8.5 Pavement", "8.6 Facade", "8.7 Roof", elk met opsomming van gebreken en de aantekening "-This can be fixed under the agreement with the client!" (31 mei 2022).
6. Slotblok "Belangrijk" met handtekeningen (letterlijk, 2008-16, 1828-8, 2001-x):
   > "Na elke rondgang in het kader van een oplevering maken de architecten een procesverbaal op en sturen dit door naar alle betrokken partijen. Elke aannemer stuurt op zijn beurt het verslag door naar zijn onderaannemers. Opmerkingen op dit verslag worden uitsluitend schriftelijk gesteld. Het procesverbaal is op deze manier steeds aanvaard en goedgekeurd.
   > Handtekeningen van alle partijen:
   > ter kennisname | voor akkoord | voor akkoord
   > Architect | Aannemer | Bouwheer"
   Voettekst: "Verslag opgemaakt door  voor H-Architects bvba", paginanummer "x / y".

**Variant 2: gewoon werfverslag met PV-tekst in "Status werf"** (2103-13, 2056-11, 2199-7, 2089-8, 2118-3, 2033-3). Opbouw is die van het standaard werfverslag (kop, "Status werf" met de PV-alinea, aanwezigen met kolom "Ontv." of "Sent", veiligheid/Peeters-Borsus, opmerkingen per categorie, slot "Algemeen" met de 5-kalenderdagen-zin). Geen handtekeningblok. Verschillen in de PV-alinea:
- 2103-13 en 2056-11: "voor de opmaak van het **EPB-verslag**" in plaats van "asbuilt-dossier"; 2103-13 noemt ook "de ramen leverancier" bij de aanwezigen.
- Engelse formule (2089-8, 2118-3): "PV DELIVERY. This is the provisional acceptance for project ... This is done in the presence of the builder and the architect. The provisional acceptance is accepted subject to the numbered comments attached here, which must be complied with no later than the valid time to finish this construction works. The provisional acceptance will automatically pass to a final acceptance, on Tuesday, Oct 31, and the listed remarks should be finished by that time. **H-architects is not responsible for the works implemented after this date.** The necessary documents, certificates and inspection reports for the preparation of the EPB report must also be delivered by this final date, 31 October 2023, at the latest."
- Tweetalig (2199-7): "PV Provisional Handover. This concerns the provisional handover for project 2199 ... The provisional handover is accepted subject to the attached numbered and abbreviated remarks by the parties, which must be fulfilled no later than Friday, January 31, 2025. The provisional handover will automatically convert to a definitive acceptance on Friday, January 31, 2025, if the listed remarks have been fulfilled." gevolgd door de NL-versie.
- Vaste opleveringspunten in deze variant: "Einddatum van de werken" (omgevingsloket, 2199-7 7.1, 2089-8 8.5, 2118-3 3.2, 2103-13 13.2, 2004-47 46.3), "Lijst van te voltooien werkzaamheden" met deadline en waarschuwing over boetes van de gemeente (2199-7 7.2, 2004-47 46.1/46.2, 2118-3 3.1), "EPB-documenten" (2089-8 8.4, 2118-3 3.6, 2103-13 13.1), "Foto's van de gevels en het gelijkvloers genomen op de dag van de oplevering" (2199-7 7.3), en de vaststelling van werken die van de vergunde plannen afwijken met expliciete afschuiving van verantwoordelijkheid op de bouwheer (2103-13 13.3, 2089-8 8.2/8.3, 2118-3 2.1).
- Letterlijke waarschuwing bij restpunten (2199-7 7.2): "BELANGRIJK: Alle bovenstaande werkzaamheden moeten vóór 31/01/2025 zijn afgerond en binnen de geldige periode van de bouwvergunning, te beginnen vanaf de datum die in het omgevingsloket is vastgelegd als de startdatum van de werken. Let op: Tijdens de opleveringsvergadering is benadrukt dat de volgende openstaande punten binnen de gestelde termijn moeten worden afgerond om mogelijke boetes van de gemeente te voorkomen: ... Indien deze werkzaamheden niet tijdig of geheel niet worden uitgevoerd, zijn eventuele opgelegde boetes van de gemeente de verantwoordelijkheid van de klant."

**Wat NIET in de praktijk staat** (en in het voorstel wel moet): een expliciete startdatum van de waarborgtermijn en van de tienjarige aansprakelijkheid (art. 1792/2270 oud BW, nu boek 8), een vermelding van de vrijgave van de borg of inhouding, de datum van de eerste ingebruikname, meterstanden, sleuteloverdracht, de verklaring dat de werken conform vergunning zijn (of niet), en een echte handtekeningregel per aanwezige (variant 2 heeft er geen).

### A.2 Voorstel sjabloon: PV van voorlopige oplevering

Naam bestand/verslag: `<dossier>-VO` (of `<dossier>-<n>` met verslagtype "voorlopige oplevering" in de kop, zoals de keuze `verslagtype` op mijnagents).

1. **Kopgegevens** (zoals het huisstijl-Word): projectnummer, projectnaam en korte omschrijving, adres werf, bouwheer(s), hoofdaannemer, nummer PV, datum en uur van de rondgang, datum opmaak, verslagtype "Proces-verbaal van voorlopige oplevering", taal (NL of NL+EN).
2. **Voorwerp en aanvaarding** (vaste tekst, herwerkt uit 2008-16/2001-4):
   > "Dit verslag geldt als proces-verbaal van voorlopige oplevering voor project <nr> <adres>. De rondgang vond plaats op <datum> in aanwezigheid van de opdrachtgever, de (hoofd)aannemer(s) en de architect.
   > De voorlopige oplevering wordt aanvaard onder voorbehoud van de voorafgaande werfverslagen en van de hieronder genummerde en door partijen geparafeerde opmerkingen, waaraan moet worden voldaan uiterlijk op <weekdag dd maand jjjj>.
   > De datum van dit proces-verbaal geldt als datum van voorlopige oplevering. Vanaf deze datum lopen de waarborgtermijn en de tienjarige aansprakelijkheid van aannemer en architect (wet Peeters-Borsus; art. 1792 en 2270 oud Burgerlijk Wetboek). De voorlopige oplevering houdt geen aanvaarding in van verborgen gebreken.
   > De definitieve oplevering vindt plaats ten vroegste één jaar na deze datum, na een tweede rondgang en een afzonderlijk proces-verbaal, en op voorwaarde dat de hieronder opgesomde opmerkingen zijn uitgevoerd.
   > Opmerkingen op dit proces-verbaal dienen schriftelijk en binnen de 8 werkdagen overgemaakt te worden aan het architectenkantoor. Zonder tegenbericht binnen die termijn wordt het proces-verbaal als aanvaard beschouwd."
   Keuze voor Mehdi: de automatische overgang ("gaat automatisch over naar een definitieve oplevering op <datum>") behouden zoals in de praktijk, of vervangen door de bovenstaande formule met tweede rondgang. Juridisch is de tweede rondgang veiliger (de definitieve oplevering dekt de zichtbare gebreken die na ingebruikname blijken); de automatische overgang is wat H-A tot nu toe deed.
3. **Aanwezigen**: tabel Rol/firma | Naam | Contact | Aanwezig | Ontvangt verslag (zoals kolom "Aanw."/"Ontv." in 2199-7).
4. **Wettelijke verplichtingen** (blok zoals 2444-1/2185-6): veiligheid (VGP), verzekeringsattesten BA10 en BBR, start- en einddatum omgevingsloket ("Het is de verantwoordelijkheid van de bouwheer om ... de einddatum van de werken in het Omgevingsloket aan te geven"), EPB-eindverklaring (documenten bij de EPB-verslaggever aan te leveren uiterlijk op <datum>).
5. **Vaststellingen conformiteit**: werken uitgevoerd conform vergunde plannen ja/nee; lijst afwijkingen met de zin uit 2103-13/2249-1 dat de bouwheer de verantwoordelijkheid draagt voor wijzigingen die hij tegen advies in besliste.
6. **Lijst van gebreken en onafgewerkte werken** (tabel): Nr `VO.<n>` | Ruimte of onderdeel (categorie-indeling zoals de werfverslagen: Buitenwerk, Dak, Buitenschrijnwerk, Ruwbouw, Riolering, Technieken elektriciteit/sanitair/verwarming/ventilatie, Binnenafwerking, per verdieping of per appartement bij meergezins zoals 1828-8) | Omschrijving | Foto | Verantwoordelijke aannemer | Hersteltermijn (standaard: de einddatum uit punt 2, afwijkende termijn per punt mogelijk) | Vlag (NOK, Belangrijk, Dringend).
7. **Documenten en attesten**: checklist met status (ontvangen/ontbreekt): as-built plannen, keuringsverslag elektriciteit, keuring riolering/afkoppeling, EPB-stavingsstukken (facturen, technische fiches, Uw-rapporten, foto's), attesten BA10 per aannemer, onderhoudsvoorschriften technieken, sleutels en toegangscodes, meterstanden water/gas/elektriciteit op datum van oplevering.
8. **Financieel**: eindafrekening aannemer ontvangen ja/nee, inhouding of borg (bedrag en vrijgavevoorwaarde), erelonen architect (afrekening op werkelijke kost, zoals punt 1.4 Facturatie in de werfverslagen).
9. **Foto's van de toestand op de dag van de oplevering** (gevels en elk niveau, zoals 2199-7 7.3 en 2033-3).
10. **Handtekeningen**: "ter kennisname: Architect | voor akkoord: Aannemer | voor akkoord: Bouwheer", met de vaste tekst uit het blok "Belangrijk" (2008-16). Eén regel per aanwezige partij, met naam, datum en handtekening; bij weigering te tekenen: vermelding "weigert te tekenen, reden".
11. **Slot**: de 5-kalenderdagen-zin van de werfverslagen komt hier niet; het PV gebruikt de 8-werkdagen-regel uit punt 2.

### A.3 Voorstel sjabloon: PV van definitieve oplevering

Geen praktijkvoorbeeld in Archisnapper; voorstel gebaseerd op de eigen vaste teksten (automatische overgang, einddatum, restpuntenlijst) en de Belgische praktijk (definitieve oplevering ten vroegste een jaar na de voorlopige, tweede rondgang, PV ondertekend door de partijen, einde van de waarborgtermijn voor lichte verborgen gebreken, tienjarige aansprakelijkheid loopt door vanaf de voorlopige oplevering).

Naam: `<dossier>-DO`.

1. **Kopgegevens**: zoals A.2, verslagtype "Proces-verbaal van definitieve oplevering", verwijzing naar het PV van voorlopige oplevering (nummer en datum).
2. **Voorwerp en aanvaarding** (vaste tekst, voorstel):
   > "Dit verslag geldt als proces-verbaal van definitieve oplevering voor project <nr> <adres>. De voorlopige oplevering vond plaats op <datum VO> (PV <nr-VO>). De rondgang voor de definitieve oplevering vond plaats op <datum> in aanwezigheid van de opdrachtgever, de (hoofd)aannemer(s) en de architect.
   > De partijen stellen vast dat de opmerkingen van het proces-verbaal van voorlopige oplevering zijn uitgevoerd, met uitzondering van de hieronder genummerde punten. De definitieve oplevering wordt aanvaard [zonder voorbehoud / onder voorbehoud van de hieronder genummerde opmerkingen, uit te voeren uiterlijk op <datum>].
   > De definitieve oplevering sluit de waarborgtermijn af en dekt de zichtbare gebreken en de lichte verborgen gebreken die op de datum van dit proces-verbaal gekend waren. De tienjarige aansprakelijkheid voor ernstige gebreken die de stevigheid van het gebouw aantasten (art. 1792 en 2270 oud Burgerlijk Wetboek) loopt verder tot <datum VO + 10 jaar>.
   > Opmerkingen op dit proces-verbaal dienen schriftelijk en binnen de 8 werkdagen overgemaakt te worden aan het architectenkantoor."
   Variant als H-A de automatische overgang behoudt: "Overeenkomstig het proces-verbaal van voorlopige oplevering van <datum VO> is de voorlopige oplevering op <datum> automatisch overgegaan in een definitieve oplevering. Dit verslag bevestigt die overgang en legt de toestand van de werken op <datum rondgang> vast."
3. **Aanwezigen**: zelfde tabel.
4. **Opvolging van de VO-punten**: tabel met elk punt `VO.<n>` uit het vorige PV, status (Uitgevoerd op <datum> / Niet uitgevoerd / Anders opgelost), foto vóór en na, verantwoordelijke. Dit is de kern van het verslag; de praktijk in 2056-11 ("De klant heeft bevestigd dat de aannemer alle openstaande punten heeft afgewerkt die tijdens de opleveringsvergadering van 15 september 2023 werden genoemd") en 2004-47 ("De volgende werkzaamheden zijn uitgevoerd: ...") is precies dit, maar zonder tabelvorm.
5. **Nieuwe vaststellingen sinds de voorlopige oplevering**: gebreken die tijdens het gebruik zijn gebleken (scheuren, vochtschade, werking technieken), met dezelfde kolommen als A.2 punt 6 en de vraag of ze onder de waarborg vallen (verantwoordelijke aannemer) of onder gebruik/onderhoud (bouwheer).
6. **Administratieve afsluiting**: EPB-eindverklaring ingediend (datum, verslaggever), einddatum werken gemeld in het omgevingsloket (datum), as-built dossier volledig, keuringsattesten, postinterventiedossier overhandigd door de veiligheidscoördinator, laatste factuur en vrijgave borg/inhouding.
7. **Foto's op de dag van de definitieve oplevering** (gevels en niveaus).
8. **Handtekeningen**: zelfde blok als A.2 punt 10; aanvulling in de vaste tekst: "Met de ondertekening van dit proces-verbaal eindigt de opdracht van de architect voor de werfopvolging."
9. **Bijlage**: kopie van het PV van voorlopige oplevering.

Punt voor Mehdi (keuze): de waarborgtermijn. De Belgische praktijk voor privaat woningbouw hanteert meestal één jaar tussen voorlopige en definitieve oplevering, maar het is contractueel; het cijfer hoort in het sjabloon als veld `waarborgtermijn` met standaard 12 maanden, en de agent moet de datum berekenen uit het PV van voorlopige oplevering.

---

## OPDRACHT B: de vaste terugkerende punten

### B.1 Steekproef

31 echte verslagen, 25 projecten, verslagdata 2020 t/m 2025. Per project het eerste verslag "-1" en het hoogste nummer waar mogelijk (2004-6/13/47, 2110-1/41/44, 2190-1/6, 2231-1/6). Per verslag: genummerde punten (titel, categorie, doorlopend of nieuw) en de aanwezigheid van de vaste kopteksten.

| Verslag | Datum | Kopteksten (VGP / BA10) | Doorlopende punten uit oudere verslagen | Nieuwe punten (categorie: titel) |
|---|---|---|---|---|
| 1939-1 | 22-01-2020 | geen | geen | Algemeen: 1.1 start van werken, 1.2 veiligheidscoordinatoor, 1.3 ingenieur; Ruwbouw: 1.4 Aannemer, 1.5 attest van 10 jarige aansprakelijkheid van aannemer, 1.6 hoogte, 1.7 muur kamer; Rioleringswerken: 1.8; Brandweer: 1.9 |
| 1944-4 | 10-02-2021 | geen | geen | Buitenschrijnwerk/ Window & door: 4.1 platdakraam, 4.2 kleine raam in badkamer, 4.3 grote raam aan de living, 4.4 nieuw greep, 4.5 muggenraam |
| 2082-2 | 31-08-2021 | geen | geen | Foundation Works: 2.1 Fundering; Structural Works: 2.2 Kimblokken; Algemeen/General: 2.3 Plafondbalken |
| 2110-1 | 28-04-2021 | geen | geen | Breakdown: 1.1 Demolition works, 1.2 Ground Floor, 1.3 First Floor, 1.4 Second Floor |
| 2008-16 | 09-07-2021 | VGP + BA10 | geen | PV: 16.1 t/m 16.7 (zie A) |
| 1828-8 | 23-05-2022 | geen | geen | PV: 8.1 t/m 8.7 per ruimte (zie A) |
| 2004-6 | 22-08-2022 | geen | geen | Breakdown: 6.1 Basement, 6.2 Ground floor, 6.3 First floor, 6.4 Second floor, 6.5 Demolition works still to be done; Constructions: 6.6 Ground floor, 6.7 First floor; Algemeen: 6.8 Add. info 1, 6.9 Add. info 2 |
| 2004-13 | 30-11-2022 | geen | 6.5 Demolition works still to be done (04-11-2022, Incomplete!); 9.1 First floor | geen nieuwe (verslag bestaat alleen uit doorlopende punten) |
| 2190-1 | 08-09-2022 | VGP + BA10 | geen | Afbraak/Demolition: 1.1 Demolishing (OK), 1.2 Demolishing (Incomplete) |
| 2191-1 | 16-11-2022 | VGP + BA10 | geen | Algemeen/General: 1.1 Afbraak fase (bescherming terras, buur, voorlopige regenwaterbuis, OSB onder container) |
| 2033-3 | 09-01-2023 | VGP + BA10 | geen | Algemeen/General: 3.1 Werfverslag 3/3 (alleen gevelfoto's) |
| 2138-1 | 27-02-2023 | VGP + BA10 | geen | Afbraak: 1.1 werfverslag 1; Algemeen: 1.2 Opmerking (documenten bouwheer), 1.3 Plaatsbeschrijving |
| 2190-6 | 08-03-2023 | VGP + BA10 | 1.1, 1.2, 2.1, 2.2, 2.3, 3.1 t/m 3.5 (alle uit verslagen 1 t/m 3, met status Finished/Resolved/In progress) | Constructions 5.1 Floor, 5.2 Construction; Verwarming 5.3; Binnenafwerking 5.4 Gyproc, 5.5 Paint; Elektriciteit 5.6 |
| 2249-1 | 19-04-2023 | VGP + BA10 | geen | Algemeen: 1.1 Werfverslag 1, 1.2 Belangrijk (uitvoering exact volgens ingediende plannen), 1.3 Achtergevel, 1.4 Rechtergevel, 1.5 Linkergevel |
| 2089-8 | 26-06-2023 | VGP + BA10 (EN) | geen | PV: 8.1 Interior and exterior finishes, 8.2 Terrace, Riolering 8.3, EPB 8.4 EPB documents, Constructions 8.5 End date of the works |
| 2110-41 | 24-08-2023 | geen | geen | Buitenwerk: 41.1 Terrace balustrade; Binnenafwerking: 41.2 Stairs balustrade |
| 2118-3 | 29-08-2023 | VGP + BA10 | 2.1 Difference from the plans | PV: 3.1 Things that still need to be done, 3.2 End date of the work, Bovenbouw 3.3, Buitenschrijnwerk 3.4, EPB 3.5 Isolation, 3.6 Final declaration of EPB |
| 2103-13 | 07-09-2023 | VGP + BA10 | 12.1 Water problem basement (Resolved), 12.2 Cracks insulation block | EPB 13.1 EPB; Algemeen 13.2 End date of works; Buitenwerk 13.3 Stairs in the terrace |
| 2056-11 | 31-10-2023 | VGP + BA10 | 9.3 Zoldertrap, 8.6 Beluchter WC | Algemeen 11.1 Openstaande punten (OK, Finished) |
| 2359-2 | 25-03-2024 | VGP + BA10 | 1.4 Demolition works, 1.5 Stability plans (05-03-2024, Important!), 1.7 Electricity, 1.9 Sanitary, 1.10 radiator, 1.11 Interior finishing, 1.12 Plasterwork, 1.13 EPB (Important!) | Algemeen 2.1 Meeting 21/03/2024; Bovenbouw 2.2 Structural works; Binnenafwerking 2.3 Ground floor paint; Ventilatie 2.4 |
| 2410-1 | 15-05-2024 | VGP + BA10 | geen | Algemeen: 1.1 Start- en einddatum van de werken, 1.2 Werfbezoeken, 1.3 Orde en netheid, 1.4 Vergadering 15/05/24; Afbraak 1.5 Afbraakwerken; Bovenbouw 1.6 Stabiliteitsplannen, 1.7 Bovenbouw |
| 2220-1 | 27-06-2024 | VGP + BA10 | geen | Algemeen 1.1, 1.2, 1.3 (zelfde titels); Veiligheidscoordinatie 1.4; Bovenbouw 1.5; Ruwbouw 1.6; Dakwerken 1.7; Buitenschrijnwerk 1.8; Gevelafwerking 1.9 |
| 2110-44 | 11-07-2024 | geen | geen | Binnenafwerking: 44.1 Appartement 101, 44.2 Appartement 201 |
| 2004-47 | 07-10-2024 | geen | 46.1 Gebouw nr 27, 46.2 Gebouw nr 29, 46.3 Einddatum (20-09-2024) | 47.1 Gebouw nr 27, 47.2 Gebouw nr 29 (uitgevoerde werken) |
| 2231-1 | 10-12-2024 | VGP + BA10 | geen | Algemeen 1.1 Start- en einddatum, 1.2 Werfbezoeken, 1.3 Orde en netheid, 1.4 Facturatie / Invoices, 1.5 Vergadering 19/11/24, 1.6 Vergadering 10/12/24; Veiligheidscoordinatie 1.7; Bovenbouw 1.8 Stabiliteitsplannen; EPB 1.9 EPB; Afbraak 1.10; Ruwbouw 1.11 Stelling |
| 2444-1 | 07-01-2025 | blok "Wettelijke verplichtingen en verantwoordelijkheden" (VGP, Verzekeringsattesten BA10+BBR, Start- en einddatum, Werfbezoeken, Orde en netheid) | geen | Afbraak 1.1, 1.2; Bovenbouw 1.3 Veranda groendak; Scheidingsmuren 1.4; Algemeen 1.5 Vergunning Voorwaarden |
| 2185-6 | 07-03-2025 | idem blok "Wettelijke verplichtingen" | geen | Ruwbouw 6.1 Gelijkvloers, 6.2 Eerste verdieping; Foto's 6.3; Buitenschrijnwerk 6.4 10 Jarige attest (NOK) |
| 2197-15 | 11-03-2025 | VGP + BA10 | 1.1 t/m 1.4 (04-06-2024), 1.5 Veiligheidscoordinatie, 1.6 EPB, 2.4 Stabiliteitsplannen (Important!), 12.3 Binnenwerk, 14.1 Afwerking rechter buur (NOK), 14.2 Verwarming, 14.3 Electriciteit | Buitenwerk 15.1; Airconditioning 15.2; Ventilatie 15.3 |
| 2231-6 | 28-05-2025 | VGP + BA10 | 1.1 t/m 1.4 (10-12-2024), 1.7 Veiligheidscoordinatie, 1.8 Stabiliteitsplannen, 1.9 EPB, 5.3 Bovenbouw, 5.4 Dakwerken, 3.4 Foto's | Algemeen 6.1 Vergadering 28/05/25; Afbraak 6.2; EPB 6.3 Muurisolatie, 6.4 Dakisolatie; Buitenschrijnwerk 6.5 Dakramen |
| 2199-7 | 03-06-2025 | VGP + BA10 | geen | PV: 7.1 Einddatum van de werken, 7.2 Lijst van te voltooien werkzaamheden, 7.3 Foto's |
| 2282-5 | 09-07-2025 | VGP + BA10 | 1.1 t/m 1.4 (12-11-2024), 1.6 Veiligheidscoordinatie, 1.12 Stabiliteitsplannen, 1.14 EPB | Algemeen 5.1 Bodemverontreiniging; Riolering 5.2 (NOK, Urgent!, Doesn't Follow Architectural Execution Drawings!) |

Vaststellingen over de evolutie:
- 2020 t/m 2022: geen vaste kopteksten, punten zijn alleen werfwaarnemingen; 1939-1 is de uitzondering en zet veiligheidscoördinator, ingenieur, aannemer en BA10-attest als NOK-punten bij de bouwheer.
- Vanaf 2021/2022 (2008-16, 2190-1): het vaste blok "Veiligheid" + "10-jarige aansprakelijkheid" boven de opmerkingen.
- Vanaf midden 2023 (2089-8, 2118-3, 2103-13): "End date of the works" en "EPB documents" als vaste opleveringspunten.
- Vanaf 2024 (2359-2, 2410-1, 2220-1, 2197-15, 2231-1, 2282-5): de doorlopende reeks 1.1 t/m 1.6 in de eerste verslagen, tweetalig ("Nederlands: ... English: ..."), die in elk volgend verslag met de oorspronkelijke datum wordt herhaald (2197-15, 2231-6, 2282-5).
- Vanaf 2025 (2444-1, 2185-6): hetzelfde als kopblok "Wettelijke verplichtingen en verantwoordelijkheden" boven de opmerkingen in plaats van als genummerde punten; met een nieuwe formulering van de verzekeringen (BA10 én BBR). "Status werf" krijgt daar de velden "Projectfase:" en "Voortgang van de werken:" (2444-1).
- Vlaggen die Archisnapper gebruikt: OK, NOK, Finished!, Resolved!, Incomplete!, Needs to be Fixed!, In progress!, Important!, Urgent!, Doesn't Follow Architectural Execution Drawings! (2282-5).
- Categorienamen die letterlijk voorkomen: Algemeen/General; Afbraak/Demolition (ouder: Breakdown); Ruwbouw; Foundation Works; Bovenbouw/Structural Works (ouder: Constructions, Structural Works); Scheidingsmuren/dividing walls; Riolering/Sewerage Works (ouder: Rioleringswerken); Brandweer; Dakwerken/Roof Works; Buitenschrijnwerk/Exterior joinery (ouder: Buitenschrijnwerk/ Window & door); Gevelafwerking/ Facade finishing; Buitenwerk/Exterior works; Binnenwerk/ Interior works; Binnenafwerking/Interior finishes; Binnenpleisterwerk/Interiorplaster; Elektriciteit/Electricity; Sanitair/Plumbing; Verwarming/Heating; Ventilatie/Ventilation; Airconditioning/ Air conditioning; EPB ( Energieprestaties en Binnenklimaat ); Veiligheidscoordinatie; Foto's/ Photos; Nieuw besproken punten/ Newly discussed points (2103-13).

### B.2 Telling van de terugkerende onderwerpen (n = 31 verslagen)

| Onderwerp | In hoeveel verslagen | Letterlijke standaardtekst (NL) | Letterlijke standaardtekst (EN) | Verantwoordelijke | Categorie |
|---|---|---|---|---|---|
| Slotzin akkoord | 28 van 31 (alle werfverslagen; niet in de PV-vorm 2008-16, 1828-8) | "Zonder tegenbericht binnen de 5 kalenderdagen, per mail, zal worden aangenomen dat alle partijen akkoord gaan met dit verslag. Vragen of opmerkingen kunt u best per mail versturen." | geen (ook in Engelse verslagen in het NL, 2089-8) | alle partijen | Algemeen (slot) |
| Veiligheid (VGP) | 21 van 31 (alle sinds 2022 behalve 2004-x en 2110-x) | "Het veiligheid- en gezondheidsplan van de veiligheidscoördinator is van toepassing tijdens de hele duur van de werken. De planning van de werken dient tijdig te worden doorgegeven aan de veiligheidscoördinator." | "The safety and health plan of the safety coordinator applies throughout the duration of the works. The schedule of works should be communicated to the safety coordinator in a timely manner." (2089-8) | aannemer(s), bouwheer | kopblok |
| 10-jarige aansprakelijkheid (BA10) | 21 van 31 (19 oude formule, 2 nieuwe formule 2444-1/2185-6); plus als NOK-punt in 1939-1 (1.5) en 2185-6 (6.4) | Oud: "De verzekeringsfiches voor de 10-jarige burgerlijke aansprakelijkheid volgens de wet Peeters-Borsus (31 mei 2017, BS 9 juni 2017) dienen aangeleverd te worden door alle aannemers die een aandeel hebben in de constructie tot wind- en waterdichte staat van de werken." Nieuw (2444-1): "Om de correcte uitvoering van de werken en de naleving van de wettelijke verplichtingen te waarborgen, verzoeken wij u om de volgende attesten op te vragen bij uw aannemers en ons deze te bezorgen vóór de start van de werken: Het attest van de tienjarige burgerlijke aansprakelijkheid (BA 10) voor de werken aan de gesloten ruwbouw, zoals vereist door de wet Peeters-Borsus (31 mei 2017). Het attest van de burgerlijke beroepsaansprakelijkheid (BBR), dat vereist is voor alle betrokken aannemers, inclusief de hoofdaannemer en onderaannemers." | "Insurance sheets for the 10-year civil liability according to the Peeters-Borsus Act (31 May 2017, BS 9 June 2017) must be supplied by all contractors who have a share in the construction to wind and watertight condition of the works." (2089-8) | bouwheer vraagt op, aannemers leveren | kopblok |
| Start- en einddatum werken (omgevingsloket) | 13 van 31 (2410-1, 2220-1, 2231-1, 2231-6, 2197-15, 2282-5, 2444-1, 2185-6, 2199-7, 2004-47, 2089-8, 2118-3, 2103-13) | "Het is de verantwoordelijkheid van de bouwheer om de start- en einddatum van de werken in het omgevingsloket in te vullen. Volgens de vergunning: - De werken moeten binnen 2 jaar na de vergunning beginnen. - Het gebouw moet binnen 5 jaar na de vergunning wind- en waterdicht zijn." (2410-1) | "It is responsibility of the 'bouwheer' to fill in the starting and ending date of the works in the 'omgevingsloket'. According to permission: - Works have to begin within 2 years from permission - Building have to be wind and water tight within 5 years of the permission." (2410-1); oudere formule 2089-8: "It is the responsibility of the client to declare the end date of works in the system of omgevingsloket. This is very important to be done on time and not exceed the valid period to finish the construction works within the 2 years period starting from the start date of works declared in the omgevingsloket. This period can be extended with 1 extra year by doing a request to the municipality." | bouwheer | Algemeen/General, punt 1.1 |
| Werfbezoeken | 8 van 31 (alle verslagen vanaf 2024 in de nieuwe stijl) | "Werfbezoeken worden consequent uitgevoerd in overeenstemming met de architectenovereenkomst tussen opdrachtgevers en architecten. Echter zijn werfbezoeken altijd beschikbaar op oproep, zodat cruciale zaken continu worden gemonitord. Voor kritieke handelingen zoals het plaatsen van wapening en vergelijkbare taken die niet kunnen worden geïnspecteerd na uitvoering, worden visuele materialen consistent vastgelegd, zoals foto's genomen door de aannemers, en ter verificatie voorgelegd. Alle werfinspecties hebben altijd betrekking op de zichtbare staat van het pand. Foto's die tijdens de werkzaamheden worden genomen, wanneer de architecten niet ter plaatse zijn, moeten met de architecten worden gedeeld om ervoor te zorgen dat al het bewijs beschikbaar is." (2231-1; de laatste zin ontbreekt in 2410-1, 2220-1, 2444-1, 2185-6) | "Site visits are consistently conducted in accordance with the architect's agreement between clients and architects. However, site visits are always available on call, ensuring that crucial matters are continuously monitored. For critical actions such as the placement of reinforcement and similar tasks that cannot be inspected post-execution, visual materials are consistently captured, such as photographs taken by the contractors, and presented for verification. All site inspections always pertain to the visible condition of the property. Photos taken during the works, when the architects are not present on site, should be shared with the architects. This to ensure that all the evidence is available." (2231-1) | bouwheer, aannemer | Algemeen/General, punt 1.2 |
| Orde en netheid | 8 van 31 (zelfde reeks) | "Elke betrokken aannemer wordt verwacht de netheid en ordelijkheid op de bouwplaats te handhaven. Ze dienen snel al het puin of afval dat tijdens hun werkzaamheden wordt gegenereerd te verwijderen. Het net houden van de bouwplaats is essentieel voor de veiligheid. Bovendien is het belangrijk om regelmatig afvalitems zoals lege blikjes, sigarettenpeuken en verpakkingen weg te gooien." | "Each contractor involved is expected to maintain cleanliness and orderliness on the site. They should promptly remove any debris or waste generated during their work. Keeping the site tidy is essential for safety. Furthermore, it's important to dispose of waste items like empty cans, cigarette butts, and packaging regularly." | alle aannemers | Algemeen/General, punt 1.3 |
| Facturatie | 4 van 31 (2231-1, 2231-6, 2197-15, 2282-5) | "Om ervoor te zorgen dat de klant correct wordt gefactureerd door het architectenbureau volgens het contract, moet de klant alle facturen en de werkelijke kosten van de renovatiewerken met de architecten delen. Let op: Indien de bouwheer de architecten om hulp vraagt of verzoekt om extra werkzaamheden te volgen die geen deel uitmaakten van de oorspronkelijke opdracht en niet waren opgenomen in de originele plannen, dan worden de kosten van deze extra werkzaamheden meegenomen bij de herberekening voor de betaling van de erelonen van de architecten. Anders dient de klant deze werkzaamheden zelfstandig te beheren zonder de architecten erbij te betrekken." | "To ensure that the client is correctly invoiced by the architecture office in accordance with the contract, the client must share all invoices and the actual costs of the renovation works with the architecture office. Note: If the client asks the architects for assistance or requests to follow up additional work that was not part of the original assignment and was not included in the original plans, the cost of these additional works will be taken into account during the recalculations for the payment of the architects' fees. Otherwise, the client should manage these works independently without involving the architects." | bouwheer | Algemeen/General, punt 1.4 |
| Veiligheidscoördinatie (lange tekst) | 5 van 31 (2220-1, 2231-1, 2231-6, 2197-15, 2282-5); plus NOK-punt 1939-1 1.2 ("Het is verplicht om een veiligheidscoördinator aan te stellen. Architect benadrukt dat het de taak is van de Bouwheer om hiervoor iemand aan te stellen.") | "Veiligheid op de bouwplaats is cruciaal. De veiligheidscoördinator houdt toezicht op de veiligheid en levert rapporten aan. Volg de richtlijnen van de architect en veiligheidscoördinator en maak indien nodig aanpassingen. Voor gevaarlijke taken moeten aannemers op de hoogte worden gebracht van de juiste methoden. Elke aannemer ontvangt een VGP om te controleren en op de bouwplaats te bewaren. Neem altijd veiligheidsmaatregelen. De hoofdaannemer informeert onderaannemers over de VGP en beheert de veiligheid. Zorg voor valbescherming, leuningen, correct gebruik van ladders en nagelverwijdering. Voor risicovolle taken informeer de architect of veiligheidscoördinator en neem voorzorgsmaatregelen. Zelfbouwers moeten dezelfde veiligheidsvoorschriften volgen. Beveilig steigers en houd de weersomstandigheden in de gaten. De architect is niet aansprakelijk voor slecht verankerde steigers of het niet naleven van de VGP. Werfinspecties zijn momentopnames en vereisen geen constante aanwezigheid, zoals vermeld in de overeenkomst." | "Safety on the construction site is crucial. The safety coordinator oversees safety and provides reports. Follow guidelines from the architect and safety coordinator, making necessary adjustments. For hazardous tasks, contractors must be informed of proper methods. Each contractor gets a VGP to review and keep on site. Always take safety measures. The main contractor informs subcontractors about the VGP and manages safety. Ensure fall protection, guardrails, proper ladder use, and nail removal. For risky tasks, inform the architect or safety coordinator and take precautions. Self-builders must follow the same safety regulations. Secure scaffolding and monitor weather conditions. The architect is not liable for improperly anchored scaffolding or non-compliance with VGP. Site inspections are momentary and do not require constant presence, as stated in the agreement." | hoofdaannemer, onderaannemers, zelfbouwers | Veiligheidscoordinatie, punt 1.5/1.6/1.7 |
| Stabiliteitsplannen | 6 van 31 (2410-1, 2231-1, 2231-6, 2197-15, 2282-5, 2359-2); plus NOK 1939-1 1.3 ("Architect benadrukt expliciet dat er een ingenieur moet aangesteld worden.") | "Alle uitgevoerde werken moeten de stabiliteitsplannen van de ingenieur volgen. Alle wijzigingen ten opzichte van de plannen moeten worden gedocumenteerd, goedgekeurd door de ingenieur en verstrekt aan de architect." | "All the works that are carried out have to follow the stability plans of the engineer. All the changes from the plans have to be documented, approved by the engineer and provided to the architect." | aannemer, ingenieur | Bovenbouw/Structural Works, punt 1.6/1.8/1.12/2.4 |
| EPB | 9 van 31 (2231-1, 2231-6, 2197-15, 2282-5, 2359-2, 2089-8, 2118-3, 2103-13, 2056-11) | "Alle vereisten gespecificeerd in het EPB-rapport moeten worden gevolgd (isolatiewaarden, ventilatie, raamwaarden, enz.). Alle elementen moeten dezelfde waarden hebben (of beter) als die vereist zijn in het EPB-rapport. Het is de verantwoordelijkheid van de aannemer om alle facturen, technische fiches, Uw-rapporten met betrekking tot de nieuwe ramen, enzovoort, te verstrekken voor alle elementen die vereist zijn in het EPB-rapport. Het is de verantwoordelijkheid van de bouwheer om foto's te nemen van alle werkstappen waarvoor een fotobewijs nodig is voor de EPB. Om de EPB-eindverklaring op te stellen, is het de verantwoordelijkheid van de bouwheer om de nodige informatie (facturen, foto's, vorderingsstaten, technische fiches, enz.) aan het einde van het project met de EPB-verslaggever te delen." (2231-1) | "All the requirements specified in the EPB report have to be followed (isolation values, ventilation, windows values etc.). All the element have to have the same values (or better) like the ones required by the EPB report. It is responsibility of the contractor to provide all the invoices, 'technische fiches', Uw report regarding the new windows etc. for all the elements required by the EPB report. It is the clients responsibility to make photos of all work steps that require a photo evidence for the EPB. To prepare the EPB final declaration, it is the responsibility of the building owner to share the necessary information (invoices, photos, progress reports, technical datasheets, etc.) with the EPB reporter at the end of the project." Bij oplevering (2118-3 3.6): "All the information (pictures, invoices, technical sheets etc.) must be collected and submitted by the client to receive final declaration for EBP." | aannemer (stukken), bouwheer (foto's, eindverklaring) | EPB ( Energieprestaties en Binnenklimaat ), punt 1.9/1.13/1.14 |
| Uitvoering conform vergunde plannen; afwijkingen op verantwoordelijkheid bouwheer | 7 van 31 (2249-1, 2103-13, 2118-3, 2089-8, 2185-6, 2444-1, 1939-1) | "De uitvoering van de werken dienen exact te gebeuren volgens de ingediende plannen, alle aanpassingen of veranderingen die tijdens de werken zijn gedaan en die afwijken van de ingediende plannen, is de bouwheer hiervoor verantwoordelijk." (2249-1 1.2) | "IMPORTANT: All the unfinished works should be done respecting the permitted plans and following the requirements mentioned in the permitted documents." (2089-8); "At the time of the construction it was told to the client that this addition ... will violate the permission plans and that the H-Architects will not take responsibility for that." (2103-13 13.3) | bouwheer | Algemeen/General |
| Plaatsbeschrijving | 1 van 31 (2138-1 1.3) | "Plaatsbeschrijving (openbaardomein en rechterbuur) dient door de bouwheer zo snel als mogelijk uitgevoerd te worden en de aannemer en de architect op de hoogte brengen." | geen | bouwheer | Algemeen/General |
| Documenten van de bouwheer aan aannemer en architect | 1 van 31 (2138-1 1.2) | "Vloerafwerking, sanitair toestellen en technische plannen van de keuken dienen bezorgt te worden aan de aannemer en architect door de bouwheer." | geen | bouwheer | Algemeen/General |
| Actuele plannen op de werf | 1 van 31, maar bij bijna elk punt herhaald (2190-6) | geen NL | "Note to the Contractor: Make sure all the updated drawings are present on the site. When there is an updated drawing, remove the old plans from the site so that there will not be any misunderstandings." | aannemer | alle categorieën |
| Vergadering/meeting als punt | 4 van 31 (2410-1 1.4, 2231-1 1.5/1.6, 2231-6 6.1, 2359-2 2.1) | "Er werd een vergadering gehouden op de bouwplaats met de architect, de bouwheer en de aannemer. ... Tijdens de vergadering werden verschillende belangrijke onderwerpen besproken: ..." (2231-1 1.5) | "A meeting was held at the building with the architect, the building owner, and the contractor. ..." | n.v.t. | Algemeen/General |
| Lijst nog uit te voeren werken met deadline | 6 van 31 (2008-16, 1828-8, 2199-7, 2118-3, 2004-47, 2089-8) | "Werken die nog moeten worden afgerond: ... BELANGRIJK: Alle bovenstaande werkzaamheden moeten vóór <datum> zijn afgerond en binnen de geldige periode van de bouwvergunning, te beginnen vanaf de datum die in het omgevingsloket is vastgelegd als de startdatum van de werken." (2199-7 7.2) | "Works that still need to be finished: ... IMPORTANT: All the works mentioned above must be completed by <date> and within the valid period of the building permit, starting from the date recorded in the omgevingsloket as the start date of the works." | aannemer / bouwheer | Algemeen/General (oplevering) |
| Foto's als apart punt | 4 van 31 (2199-7 7.3, 2231-6 3.4, 2185-6 6.3, 2033-3 3.1) | "Hieronder zijn foto's bijgevoegd van de gevels en het gelijkvloers, genomen op de dag van de oplevering van het project." (2199-7); "De overige foto's van de werf." (2231-6) | "Attached below are pictures showcasing the facades and ground floor pictures taken on the day of the project's delivery." | n.v.t. | Foto's/ Photos |
| Verzekering ingenieur/ramenplaatser (BA10 per partij) | 2 van 31 (1939-1 1.3, 2185-6 6.4) | "De Opdrachtgever moet de attest van 10 jaarige verzekering van de Ramen installateur bezorgen aan de architect. De architect zal zijn attest ook aan de opdrachtgever bezorgen. De Opdrachtgever bezorgt de attest van 10 jaarige verzekering van de ingenieur aan de Architect." (2185-6) | geen | bouwheer | Buitenschrijnwerk |
| Planning (als vast punt) | 0 van 31 als apart punt; alleen als zin in de VGP-koptekst ("De planning van de werken dient tijdig te worden doorgegeven aan de veiligheidscoördinator") en in vergaderpunten (2231-1 1.5 "De planning van de werkzaamheden werd besproken. Wekelijkse werfbezoeken werden ingepland.") | zie links | zie links | aannemer | geen eigen categorie |

Niet aangetroffen als vast punt in deze steekproef: verzekering ABR/bouwheer, werfbord en werfinrichting, nutsaansluitingen, asbestinventaris (alleen als waarneming "dakpannen (gemaakt van asbest) werden verwijderd", 2231-1 1.10), sloopopvolgingsplan, toegang van de architect tot de werf.

### B.3 Voorstel "vaste punten": in elk werfverslag tot ze OK zijn

Genummerd als `1.1` t/m `1.8` in verslag 1 en in elk volgend verslag herhaald met de oorspronkelijke datum, zoals 2197-15, 2231-6 en 2282-5 dat doen, tot de vlag OK is (dan nog één keer tonen als OK en daarna weglaten). Tweetalig NL/EN volgens de keuze `taal`.

| Nr | Titel | Categorie | Verantwoordelijke | Vaste tekst (basis) | OK wanneer |
|---|---|---|---|---|---|
| 1.1 | Start- en einddatum van de werken | Algemeen/General | bouwheer | tekst 2410-1 (zie B.2) | startdatum gemeld in omgevingsloket (bewijs in dossier); einddatum-melding blijft open tot de oplevering |
| 1.2 | Werfbezoeken | Algemeen/General | bouwheer, aannemer | tekst 2231-1 (met de zin over foto's delen) | nooit OK; blijft staan als disclaimer (of verhuist naar het kopblok "Wettelijke verplichtingen", zoals 2444-1) |
| 1.3 | Orde en netheid | Algemeen/General | alle aannemers | tekst 2410-1 | blijft staan; bij vaststelling van een vuile werf wordt er een gedateerd NOK-punt onder gezet |
| 1.4 | Facturatie / Invoices | Algemeen/General | bouwheer | tekst 2231-1 | blijft staan tot de eindafrekening van de erelonen |
| 1.5 | Veiligheidscoördinatie en VGP | Veiligheidscoordinatie | bouwheer (aanstelling), hoofdaannemer (naleving) | tekst 2231-1 1.7; plus uit 1939-1: "Het is verplicht om een veiligheidscoördinator aan te stellen. ... De werken mochten niet gestart worden zonder dat er een veiligheidscoördinator was aangesteld." | OK zodra de veiligheidscoördinator is aangesteld en het VGP getekend op de werf ligt (2231-1 1.5); de disclaimer-zinnen blijven in het kopblok |
| 1.6 | Verzekeringsattesten BA10 en BBR | Algemeen/General (of kopblok) | bouwheer vraagt op, elke aannemer levert | nieuwe tekst 2444-1 (BA10 gesloten ruwbouw, BBR alle aannemers); plus per partij zoals 2185-6 6.4 (ramenplaatser, ingenieur, architect) | OK per aannemer zodra het attest in het dossier zit; lijst met naam aannemer en datum ontvangst |
| 1.7 | Stabiliteitsplannen | Bovenbouw/Structural Works | aannemer, ingenieur | tekst 2410-1 1.6 | blijft staan tot de ruwbouw is afgesloten (wind- en waterdicht) |
| 1.8 | EPB | EPB | aannemer (stukken), bouwheer (foto's, eindverklaring) | tekst 2231-1 1.9 | blijft staan tot de EPB-eindverklaring is ingediend (na oplevering) |
| 1.9 | Uitvoering volgens vergunde plannen | Algemeen/General | bouwheer | tekst 2249-1 1.2, aangevuld met 2444-1 1.5 (vergunningsvoorwaarden letterlijk overnemen uit de vergunning) | blijft staan; elke vastgestelde afwijking krijgt een gedateerd NOK-punt met de zin uit 2103-13 dat de bouwheer de verantwoordelijkheid draagt |
| 1.10 | Plaatsbeschrijving | Algemeen/General | bouwheer | tekst 2138-1 1.3 ("openbaar domein en buren") | OK zodra de plaatsbeschrijving vóór de start is opgemaakt en in het dossier zit; daarna weglaten |
| 1.11 | Actuele plannen op de werf | Algemeen/General | aannemer | NL-vertaling van 2190-6: "Zorg dat alle bijgewerkte plannen op de werf aanwezig zijn. Bij een nieuw plan worden de oude plannen van de werf verwijderd om misverstanden te vermijden." | blijft staan |

Kopblok (vast, boven de opmerkingen, zoals 2444-1 "Wettelijke verplichtingen en verantwoordelijkheden"): Veiligheid (VGP-zinnen), Verzekeringsattesten, Start- en einddatum, Werfbezoeken, Orde en netheid. Voorstel: de disclaimers (1.2, 1.3, de VGP-zinnen) alleen in het kopblok, en de punten met een concrete afsluiting (1.1, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10) als genummerde, opvolgbare punten. Dat vermijdt de dubbele opname die 2185-6 en 2444-1 nu hebben en houdt de nummering 1.x zinvol (in 2231-1 lopen de vaste punten al tot 1.9 vóór de eerste waarneming).

Slotzin (onveranderd, 28 van 31 verslagen): "Zonder tegenbericht binnen de 5 kalenderdagen, per mail, zal worden aangenomen dat alle partijen akkoord gaan met dit verslag. Vragen of opmerkingen kunt u best per mail versturen."

### B.4 Voorstel "fase-punten": per fase terugkerend

Elke fase-lijst komt in het eerste verslag van die fase en blijft tot OK. Bronvermelding: waar de praktijk het punt al kent.

**Afbraak** (Afbraak/Demolition)
- Sloop volgens sloopplannen; lijst "Demolition works still to be done" per verdieping (2004-6 6.5, 2004-13, 2190-1 1.2, 2231-6 6.2).
- Bescherming: terras, buur, voorlopige regenwaterafvoer, plaat onder de container tegen schade aan het openbaar domein (2191-1 1.1).
- Asbest: verwijdering vermelden met datum (2231-1 1.10); voorstel: asbestinventaris en attest van de verwijderaar in het dossier.
- Stutwerk na sloop van dragende wanden (2004-6 6.7, 2410-1 1.7).
- Dak afdekken met beschermfolie na verwijderen van de pannen (2231-1 1.11).
- Plaatsbeschrijving vóór de eerste sloop (2138-1 1.3).
- Onverwachte toestand (verborgen kelder, slechte muren) als "Add. info" met de beslissing ter plaatse (2004-6 6.8/6.9).

**Ruwbouw / bovenbouw** (Ruwbouw, Bovenbouw/Structural Works, Riolering/Sewerage Works, Scheidingsmuren)
- Stabiliteitsplannen (vast punt 1.7); foto's van wapening vóór het storten (1.2 werfbezoeken).
- Fundering en sleuven, positie afvoeren in de fundering (2082-2 2.1).
- Stalen balken en kolommen volgens ingenieur, lassen en verankering (2190-6 2.3, 2359-2 2.2, 2410-1 1.7).
- Riolering: positie leidingen volgens uitvoeringsplan, hellingen, aansluithoeken kleiner dan 90 graden, gescheiden RWA/DWA met één aansluiting op de straat, alles zichtbaar vóór wapening en beton (2282-5 5.2; 1939-1 1.8 septische put).
- Scheidingsmuren: verhoging eenvormig afwerken aan buurzijde (2444-1 1.4).
- Stelling geplaatst en verankerd (2231-1 1.11; VGP-tekst).
- Afgewerkte binnenhoogte (1939-1 1.6: "De afgewerkte binnen hoogte moet 260 zijn").
- Brandweer: plafonds EI60, brandwerende inkomdeuren bij meergezins (1939-1 1.9); brandcentrale, blussers en signalisatie bij oplevering (1828-8 8.1).

**Dak** (Dakwerken/Roof Works)
- Dakconstructie, onderdak, tengel- en panlatten, pannen, goten en afvoeren, overstek en boeiboorden (2231-6 5.4, 2220-1 1.7).
- Groendak: brandpreventienormen en de toplaag boven de EPDM als restpunt bij oplevering (2444-1 1.3, 2199-7 7.2, 2185-6 6.1 als afwijking van de vergunning).
- Dakisolatie: dikte en lambda tegen het EPB-verslag (2231-6 6.4: "22 cm en een λ-waarde van 0,035 W/mK").
- Dakramen en lichtkoepels: conform vergunning (2185-6 6.1), afwatering platdakraam (1944-4 4.1).

**Buitenschrijnwerk en gevel** (Buitenschrijnwerk/Exterior joinery, Gevelafwerking, Buitenwerk)
- Ramen en deuren geplaatst; silicone aan de randen; grepen; muggenramen (1944-4 4.2 t/m 4.5); rolluik en garagepoort (2118-3 3.4).
- Uw-rapport en factuur van de ramen voor EPB (vast punt 1.8); BA10-attest van de ramenplaatser (2185-6 6.4).
- Waterinfiltratie rond ramen en dorpels, herstel door hoofdaannemer op advies van de leverancier (2103-13 12.1).
- Gevelafwerking conform vergunning (steenstrips vs. thermowood, 2103-13 13.3); crepi-kleur volgens afspraak met de buur (2197-15 14.1); gevelplinten en ventilatierooster dampkap (2008-16 16.4).
- Balustrades terras en buitentrap (2110-41 41.1, 2004-47 46.1/46.2 als veiligheidsrestpunt).

**Technieken** (Elektriciteit, Sanitair, Verwarming, Ventilatie, Airconditioning)
- Elektriciteit volgens uitvoeringsplan, doosjes in de wand, videofoon, kabel laadpaal en zonnepanelen (2190-6 3.4/5.6, 2359-2 1.7); keuringsattest bij oplevering; elektriciteitsbord geplaatst (1828-8 8.2).
- Sanitair en afvoeren; beluchting toilet tegen vacuümeffect (2056-11 8.6); lavabo niet op dezelfde afvoer als het toilet (2282-5 5.2).
- Verwarming: leidingen en radiatoren, thermostaat volgens plan (2190-6 2.2, 2197-15 14.2).
- Ventilatie volgens EPB: unit, kanalen, ventielen, buitenaansluiting (2359-2 2.4, 2197-15 15.3); ventilatie keuken en toilet als EPB-eis (2089-8 8.4, 2008-16 16.5).
- Airco binnenunits (2197-15 15.2).
- Vloerisolatie en chape met EPB-waarden (2118-3 3.5: "XPS 300 Wl, 10 cm").

**Afwerking** (Binnenafwerking, Binnenpleisterwerk, Binnenwerk)
- Pleisterwerk, gyproc, schilderwerk (2359-2 1.11/1.12/2.3, 2190-6 3.2/3.3/5.4/5.5); afspraak wie schildert (2190-6 5.5).
- Binnendeuren, plinten, aansluitprofielen parket/trap/tegel (2008-16 16.3).
- Keuken en maatwerk: planning van de leverancier, kabeldoorvoeren, kastfronten (2008-16 16.1/16.2).
- Trapleuningen en trapopening beveiligd (2110-44, 2056-11 9.3).
- Badkamer: doucheplaat, baduitloop, voegen (2197-15 12.3, 2008-16 16.7).
- Vloerafwerking, sanitaire toestellen en keukenplannen door de bouwheer bezorgd (2138-1 1.2).

**Oplevering** (zie ook A.2)
- Lijst nog uit te voeren werken met deadline en verwijzing naar de geldigheid van de vergunning (2199-7 7.2, 2004-47 46.1/46.2, 2118-3 3.1).
- Einddatum werken melden in het omgevingsloket (vast punt 1.1, 2199-7 7.1).
- EPB-stukken en eindverklaring (2089-8 8.4, 2118-3 3.6, 2103-13 13.1).
- Verharding tuin en terras binnen de vergunde oppervlakte en waterdoorlatend, uit te voeren door de bouwheer binnen de vergunningstermijn (2089-8 8.2).
- Foto's van gevels en elk niveau op de dag van de oplevering (2199-7 7.3).
- Restpunten na de opleveringsvergadering opvolgen tot "Openstaande punten ... Finished" (2056-11 11.1) en uitgevoerde werken bevestigen (2004-47 47.1/47.2).
- Definitieve oplevering: apart PV (A.3), nu nergens in Archisnapper aanwezig.

---

## Aanbevolen volgende stappen

1. De drie te grote kandidaten (2463-1, 2359-6, 2197-16) lokaal downloaden en lezen om A.0 definitief te maken (verwachting: ook PV voorlopige oplevering).
2. In `sjabloon_werfverslag.py` de vaste punten uit B.3 opnemen als lijst met sleutel, titel NL/EN, categorie, verantwoordelijke, tekst en sluitvoorwaarde; en de fase-lijsten uit B.4 als keuze `fase` op de bezoekpagina.
3. Twee nieuwe verslagtypes in de schrijver: `voorlopige oplevering` (A.2) en `definitieve oplevering` (A.3), met handtekeningblok en de 8-werkdagen-regel in plaats van de 5-kalenderdagen-slotzin.
4. Beslissing van Mehdi: automatische overgang naar definitieve oplevering behouden (huidige praktijk) of tweede rondgang met apart PV (voorstel), en de standaard waarborgtermijn (12 maanden).
5. Spelfout "gekorttekende" in de vaste PV-tekst corrigeren naar "geparafeerde" bij overname in het sjabloon.
