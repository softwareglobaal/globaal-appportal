# Inventaris H-A Knowledge Base voor de werfverslag-agent

Datum: 18-10-2026. Bron: Dropbox-MCP (server 56512b95), uitsluitend `list_folder`, `fetch` en metadata. Geen lokale paden gelezen.
Basis: `/Work All/o07. UNIVERSAL/0 H-A Knowledge Base/` (ns:1802736243).

Wat ik wel en niet kon lezen, in een paar regels:

- Alle gevraagde mappen zijn volledig gelist (recursief waar nodig). Drie recursieve lijsten werden door de MCP afgekapt op 600 items (Wetgeving, BiB_05.Lastenboeken, Templates_Sjablonen); de ontbrekende submappen heb ik apart gelist, dus de structuur is compleet, alleen de bestandsaantallen van die drie mappen zijn een ondergrens.
- 60 bestanden via `fetch` gelezen (45 Buildwise-TV's/rapporten/meetstaten, 15 uit andere mappen). Van TV 189 Dekvloeren is de fetch-uitvoer door een naamsbotsing in de tool-opslag verloren gegaan; die staat als "niet gelezen".
- `fetch` geeft de volledige tekst, niet alleen de eerste pagina's; ik heb per document de omslag (nummer, jaar, uitgever) en de inhoudsopgave gebruikt voor de eenregelige omschrijving.
- Mappen "Bouwdetails" en "Bouwgebreken" zijn leeg (0 bestanden).

## 1. Hoofdmap: 31 submappen

| Map | Laatst gewijzigd | In deze opdracht |
|---|---|---|
| Buildwise Documenten | 2026-05-20 | volledig |
| vb werfverslag | 2025-08-20 | volledig |
| Werfverslagen GPT | 2025-09-09 | volledig |
| Templates_Sjablonen_H-architects | 2023-08-04 | volledig (lijst afgekapt op 600, submappen apart) |
| Safety_Veiligheidscoordinatie | 2023-08-04 | volledig |
| keuring richtlijnen | 2023-08-04 | volledig |
| Wetgeving | 2023-08-04 (ANTWERPEN/LEUVEN 2025-08) | volledig (lijst afgekapt, submappen apart) |
| BiB_05.Lastenboeken | 2023-08-04 | volledig (lijst afgekapt, submappen apart) |
| BiB_03.Standard_STD | 2023-08-04 | volledig |
| 0. Omgevingsloket | 2023-08-04 | volledig |
| 001. Orde van Architecten | 2025-08-31 | volledig |
| Calculatie-meetstaat-bestek | 2023-08-04 | volledig |
| CursusEPB | 2023-08-04 | volledig |
| Boeken,Tijdschriften & Manuals en (renamed) | 2023-08-04 | alleen voor de dubbelcontrole |
| Niet gevraagd, wel aanwezig | | BiB_06.CAD, BT4, BT5, BT6, Vectorworks Execution..._Vitalie, constructie extra, CURSUSSEN AANNEMINGSACTIVITEITEN, Constructiv, Concullegas, BiB_02.Ontwerpgids, Courses, 0 OPLEIDINGEN, VCRO_Opleiding, BiB_10.FacillityManagement, E-learning Omgevingsvergunning (2025-10), Claude outputs (2026-09) |

## 2. Buildwise Documenten (6 submappen)

| Submap | Bestanden | Types | Grootte | Jaartallen | Opmerking |
|---|---|---|---|---|---|
| Bouwdetails | 0 | - | 0 | - | leeg |
| Technische Voorlichtingen | 152 (+ submap merged files 12, Geen download 28 png) | pdf 143, jpg 4, md 2 (in merged), submappen 2 | ca. 500 MB losse pdf's + 522 MB merged | TV 112 (jaren 70) tot TV 297 (2025) | kern van de kennisbank |
| dimensioneringsmethodes | 17 pdf (+ Geen download 3 png) | pdf | 52,7 MB | WTCB-Rapporten nr. 6-22 (ca. 2010-2020), CROW-CUR 2022 | 3 bestanden >5 MB |
| meetstaten van gebouwen | 22 pdf | pdf | 33,9 MB | WTCB-reeks Meetstaat van gebouwen (jaren 70-80) | alle <5 MB |
| Normen en regelgeving | 290 pdf (+ New folder: 7 jpg, 7 md, 1 docx) | pdf | ca. 185 MB | 1969 tot 2025 (zie verdeling) | NBN-normen, Eurocodes + ANB |
| Bouwgebreken | 0 | - | 0 | - | leeg |

Submap `Technische Voorlichtingen/merged files` (522 MB, allemaal >5 MB, niet leesbaar via MCP): Tech Voorlichtingen - 1 t/m 9.pdf (33 tot 65 MB elk), ALL_Normen en Regelgeving.pdf (54 MB), Tech Voorlichtingen 1tot 5.md (11,8 MB) en 6tot9.md (10,6 MB). De twee .md-bestanden zijn tekstversies van de samengevoegde TV's (oktober 2025) en zijn de meest kansrijke bron voor een tekstindex, maar ook zij overschrijden de 5 MiB-grens van `fetch`.

Submap `Technische Voorlichtingen/Geen download` (28 png, 13-14 aug 2025) en `dimensioneringsmethodes/Geen download` (3 png, 18 aug 2025): schermafbeeldingen van Buildwise-titels die niet gedownload konden worden; geen inhoud, wel een wenslijst.

Submap `Normen en regelgeving/New folder`: 1.jpg t/m 7.jpg (schermafbeeldingen van de normenlijst, 14-10-2025), 1.md t/m 7.md (OCR-tekst daarvan; 1.md gelezen: lijst van 42 NBN-bestandsnamen) en `benaming normen.docx` (gelezen: dezelfde lijst, 5x herhaald). Werkmateriaal voor het hernoemen van de normen, geen naslag.

### Gelezen Buildwise-documenten (45), met nummer, jaar en inhoud in een regel

Alle TV's: uitgever WTCB/Buildwise, herdruk met Buildwise-omslag (2023+); het jaartal is dat van de oorspronkelijke uitgave zoals op de omslag.

| Bestand | Jaar | In een regel |
|---|---|---|
| TVN_127 Toelaatbare maatafwijkingen | 1979 | toleranties uitzetting, prefabbeton, montage, metaalbouw, schrijnwerk; 65.000 metingen; verouderd maar nog de enige Belgische referentie voor maatafwijkingen |
| TVN_132 Toelaatbare vervormingen in gebouwen | 1980 | doorbuiging en vervormingseisen vloeren/balken; verouderd (Eurocodes vervangen dit) |
| TVN_144 Slooptechnieken voor betonconstructies | 1982 | inventaris sloopprocedés; verouderd, alleen terminologie |
| TVN_147 Funderingen van huizen | 1983 | praktische leidraad funderingen kleine en middelgrote gebouwen; verouderd (Eurocode 7, WTCB-Rapport 20) |
| TVN_153 Vochthuishouding in gebouwen | 1984 | schadeoorzaken, koudebruggen, binnenklimaat; verouderd (TV 252 en EPB-regels) |
| TVN_193 Dekvloeren deel 2 uitvoering | 1994 | uitvoering dekvloeren; verouderd voor materialen, nog bruikbaar voor controlepunten (dikte, droging, voegen) |
| TVN_198 Houten trappen | 1995 | ontwerp en uitvoering houten trappen, maten en toleranties |
| TVN_202 Daken met betonpannen | 1996 | opbouw en uitvoering; vervangen door TV 240 + Add2 Betonpannen |
| TVN_207 Kunststofbuissystemen water onder druk | 1998 | materialen, plaatsing, drukproef; oud |
| TVN_211 Radon in woningen | 1999 | voorkomen en bestrijden; oud maar niet vervangen |
| TVN_212 Leidraad installatie zonneboilers | 1999 | verouderd |
| TVN_219 Dakbedekkingen met leien | 2001 | dakdetails, opbouw, uitvoering leien; nog geldig naast TV 195 natuurleien |
| TVN_221 Plaatsing van glas in sponningen | 2001 | beglazingsregels, blokjes, sponningafmetingen; nog geldig |
| TVN_222 Dimensionering schrijnwerk onder windbelasting | 2001 | windbelasting op ramen; nog geldig in combinatie met Eurocode 1 |
| TVN_223 Draagvloeren in niet-industriele gebouwen | 2002 | vloertypes, toleranties, uitvoering |
| TVN_224 Waterwerende oppervlaktebehandeling | 2002 | hydrofobering van gevels; nog geldig |
| TVN_226 Onderhoud van brandwerende deuren | 2002 | onderhoud en controle |
| TVN_227 Muurbetegelingen | 2003 | ondergrond, lijmen, voegen, controle |
| TVN_229 Groendaken | 2006 | opbouw, afdichting, belasting |
| TVN_232 Verlaagde plafonds | 2007 | opbouw en plaatsing |
| TVN_233 Lichte binnenwanden | 2007 | gipsplaten en blokken, akoestiek, brand |
| TVN_235 Condensatieketels | 2008 | installatie, rookgasafvoer, condensafvoer |
| TVN_237 Keramische binnenvloerbetegelingen | 2009 | ondergrond, lijm, voegen, toleranties |
| TVN_246 Na-isolatie van spouwmuren | 2012, corrigendum 2022 | voorwaarden spouwvulling, controle |
| TVN_247 Vloeistofdichte betonconstructies | 2012, corrigendum 2021 | kelders, waterdichte beton, voegen |
| TVN_250 Referentiedetails ingegraven constructies | 2014 | kelderdetails (waterdichting, isolatie) |
| TVN_251 Thermische isolatie van hellende daken | 2014 | isolatie, dampscherm, luchtdichtheid hellend dak |
| TVN_252 Vocht in gebouwen, opstijgend vocht | 2014 | diagnose en behandeling opstijgend vocht (vervangt TV 210) |
| TVN_253 Parkeerdaken deel 1 | 2014 | belastingen en samenstelling |
| TVN_263 Montage van zonnepanelen op hellende daken | 2017 | bevestiging, waterdichtheid, wind |
| TVN_265 Afvoer van afvalwater in gebouwen | 2018 | binnenriolering, verluchting (vervangt TV 200 en TV 114) |
| TVN_267 Betonvloeren voor binnentoepassingen | 2019 | gepolierde en industriele betonvloeren (herziening TV 204) |
| TVN_269 Houten vloerbedekkingen deel 1 | 2019 | materialen, terminologie, eisen (vervangt TV 218) |
| TVN_270 Hemelwaterafvoer onder vrij verval | 2019 | ontwerp en dimensionering goten en afvoeren |
| TVN_273 Installatie vloerverwarming warm water | 2020 | opbouw, dekvloer, opstook |
| TVN_277 Harsgebonden vloeren | 2021, corrigendum 2023 | uitvoering (vervangt TV 216) |
| TVN_283 Plaatsen van buitenschrijnwerk deel 1 | 2022 | algemene aspecten, water-, lucht-, thermisch, akoestisch (vervangt TV 188) |
| TVN_284 Binnenbepleisteringen | 2022 | ondergrond, pleistersoorten, vlakheid (vervangt TV 199 en 201) |
| TVN_286 Buitenschrijnwerk deel 2 houten ramen | april 2023 | 16 fiches plaatsing in spouwmuur, basisregels EPB-bouwknopen |
| TVN_288 Buitenschrijnwerk deel 3 alu en pvc | oktober 2023 | 32 fiches plaatsing in spouwmuur |
| TVN_289 Buitenbepleisteringen op metselwerk en beton | december 2023 | vervangt deels TV 209 |
| TVN_293 Brandveilig afdichten doorvoeringen | december 2024 | brandwerende wanden, doorvoeringen |
| TVN_258.1 Ontwerpvoorbeeld ventilatiesysteem woning | augustus 2024 | aanvulling bij TV 258 |
| TVN_294 Renovatiedetails hellende daken sarking | januari 2025 | detailfiches sarking-renovatie |
| TVN_295 Referentiedetails ETICS renovatie | januari 2025 | fiches volle muur en spouwmuur, verwijst naar TV 257, 274, 279 |
| TVN_297 Opvoegen van metselwerk | april 2025 | vervangt TV 208 |
| WTCB_Digest nr. 1 Verluchting sanitaire afvoer | 1993 | vervangen door TV 265 (staat als sticky note in de pdf) |
| WTCB_Rapport_20 Eurocode 7 in Belgie | november 2020 | richtlijnen geotechnisch ontwerp NBN EN 1997-1 ANB |
| Meetstaat_1 Het opstellen van de meetstaat | jaren 70 (tekst tot 1980) | cursus meetstaat, geen uitvoeringsnaslag |
| Meetstaat_2_18 Dakbedekkingen | jaren 80 (tekst tot 1984) | meetmethode dakbedekkingen volgens NBN B 06-001 |
| NBN B 15-001:2024 Beton, nationale aanvulling bij NBN EN 206 | 2024 | geldig vanaf 23-01-2024, vervangt editie 2022 |

Niet gelezen (fetch verloren): TVN_189 Dekvloeren (1,82 MB).


### Tabellen Buildwise Documenten

### Technische Voorlichtingen: eerste 60 van 152 bestanden (gesorteerd op naam), plus 2 submappen

| Bestand | Type | MB | Jaar op omslag (alleen gefetchte) |
|---|---|---|---|
| 31000_nl_unprotected_TVN_274 Referentiesdetails voor ETICS met pleisternieuwbouw.pdf | pdf | 0.73 |  |
| 31200_nl_unprotected_TV_RECAP_17 ETICS 20 aandacht  spunten bij de uitvoering.pdf | pdf | 5.19 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_1 Verluchting van sanitaire afvoerinstallaties in gebouwen.pdf | pdf | 0.18 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_10_1 Condensatieketels. Voordelen en werking.pdf | pdf | 0.51 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_10_2 Condensatieketels. Een nieuwe verwarmingsinstallatie.pdf | pdf | 0.35 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_10_3 Condensatieketels. Een bestaande verwarmingsketel vervangen.pdf | pdf | 0.44 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_13 Injectie van metselwerk tegen opstijgend vocht.pdf | pdf | 0.55 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_14 Een binnenbepleistering schilderen volgens de regels van de kunst.pdf | pdf | 0.44 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_15 Doorvoeringen doorheen brandwerende wanden afdichten zodat ze brandwerend blijven.pdf | pdf | 0.68 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_16 Afvalwater afvoeren.pdf | pdf | 0.49 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_2 Een dekvloer kiezen.pdf | pdf | 0.16 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_4 Uitvoering van binnenbepleisteringen met fabriekspleister.pdf | pdf | 0.18 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_5 Ventilatie van woningen - Inleiding.pdf | pdf | 0.12 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_6 Ventilatie van woningen - Natuurlijke toevoer.pdf | pdf | 0.16 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_7 Ventilatie van woningen - Natuurlijke afvoer.pdf | pdf | 0.24 |  |
| 31200_nl_unprotected_WTCB_Digest_nr_9 Geslaagde veiligheidsbeglazing.pdf | pdf | 0.19 |  |
| Merge Tech Voorlichting 144.pdf | pdf | 3.44 |  |
| Schermafbeelding 2025-10-14 153939.jpg | jpg | 0.38 |  |
| Schermafbeelding 2025-10-14 154040.jpg | jpg | 0.32 |  |
| Schermafbeelding 2025-10-14 154122.jpg | jpg | 0.41 |  |
| Schermafbeelding 2025-10-14 154143.jpg | jpg | 0.24 |  |
| TVN_112 Leidraad voor de goede uitvoering van schilderwerken. 1ste deel-Woordenschat van de schilder.pdf | pdf | 2.06 |  |
| TVN_115 Pressiometerproeven en exploitatie van hun resultaten.pdf | pdf | 0.94 |  |
| TVN_116 Bekistingswoordenlijst.pdf | pdf | 0.94 |  |
| TVN_123 Glijbekistingen.pdf | pdf | 3.18 |  |
| TVN_124 Kitvoegen tussen gevelelementen. Ontwerp en aanbrengen.pdf | pdf | 1.16 |  |
| TVN_125 Bepaling van afmetingen in het bouwbedrijf. Praktische leidraad.pdf | pdf | 2.2 |  |
| TVN_127 Toelaatbare maatafwijkingen.pdf | pdf | 1.04 | 1979 |
| TVN_129 Diepfunderings- en onderbouwprocedes.pdf | pdf | 22.73 |  |
| TVN_132 Toelaatbare vervormingen ingebouwen.pdf | pdf | 1.31 | 1980 |
| TVN_143 Rolluiken voor woningen.pdf | pdf | 2.72 |  |
| TVN_144 Slooptechnieken voor betonkonstrukties. Inventaris van de procedes.pdf | pdf | 2.34 | 1982 |
| TVN_145 Aanbevelingen voor het gebruik van verzinkt stalen buizen voor de distributie van sanitair warm en koud water.pdf | pdf | 0.68 |  |
| TVN_146 Verticale buitenbekledingen van dunne natuursteenplaten.pdf | pdf | 3.5 |  |
| TVN_147 Funderingen van huizen.pdf | pdf | 4.06 | 1983 |
| TVN_148 Het lijmen van steen en marmer.pdf | pdf | 1.75 |  |
| TVN_150 Bedrijfsrendement van centrale verwarmingsketels voor eengezinswoningen.pdf | pdf | 1.07 |  |
| TVN_153 Vochthuishouding in gebouwen.pdf | pdf | 3.39 | 1984 |
| TVN_155 Raming van de nettoenergiebehoeften voor de verwarming van gebouwen.pdf | pdf | 2.05 |  |
| TVN_163.1 Gesteente en mineralen. De doornikse steen.pdf | pdf | 0.64 |  |
| TVN_163.2 De steen van vinalmont.pdf | pdf | 0.48 |  |
| TVN_164 Eenheden ‑ grootheden ‑symbolen. Toepassing op de bouwnijverheid.pdf | pdf | 0.7 |  |
| TVN_165 Leidraad voor de goede uitvoering van soepele vloerbedekkingen.pdf | pdf | 7.21 |  |
| TVN_168Soepele vloerbedekkingen. Lexicon.pdf | pdf | 2.15 |  |
| TVN_170 Warmteafgifte en dimensionering van vloerverwarmingsinstallaties.pdf | pdf | 5.72 |  |
| TVN_174 Elementaire begrippen over warmtetransmissie.pdf | pdf | 1.56 |  |
| TVN_175 Daken met pannen in gebakken aarde. Opbouw. Uitvoering.pdf | pdf | 2.61 |  |
| TVN_177 Woordenlijst van de dekvloerlegger.pdf | pdf | 1.27 |  |
| TVN_178 Thermische isolatie van gevels.pdf | pdf | 1.36 |  |
| TVN_179 Harde vloerbedekkingen op de verwarmde vloer.pdf | pdf | 4.27 |  |
| TVN_180 Curatieve houtbescherming in gebouwen.pdf | pdf | 4.47 |  |
| TVN_181 Vereenvoudigde berekeningsmethode voor een vloerverwarmingssysteem.pdf | pdf | 1.87 |  |
| TVN_182 Vlekken op witte kalksteen en kalkhoudend marmer.pdf | pdf | 1.9 |  |
| TVN_186 Daken met tegelpannen opbouw en uitvoering.pdf | pdf | 8.5 |  |
| TVN_187 Dampkappen en keukenventilatie.pdf | pdf | 0.8 |  |
| TVN_189 Dekvloeren.pdf | pdf | 1.82 |  |
| TVN_193 Dekvloeren Deel2; uitvoering.pdf | pdf | 1.62 | 1994 |
| TVN_194 Handleiding voor de plaatsing van soepele muurbekledingen.pdf | pdf | 0.87 |  |
| TVN_195 Daken met natuurleien. Opbouw en uitvoering.pdf | pdf | 0.99 |  |
| TVN_196 Balkons.pdf | pdf | 2.58 |  |

Overige 92 bestanden in deze map (alleen nummer/naam, geen fetch):

TVN_197 Gevelreiniging (vervangt de TV 121).pdf (5.25 MB); TVN_198 Houten trappen.pdf (3.07 MB); TVN_202 Daken met betonpannen opbouw en uitvoering.pdf (2.49 MB); TVN_206 Mecanische inbraakbeveiliging van schrijnwerk en beglazing.pdf (1.06 MB); TVN_207 Kunststofbuissystemen voor de distributie van warm en koud water onder druk in gebouwen.pdf (0.67 MB); TVN_209 Buitenbepleisteringen.pdf (1.2 MB); TVN_211 Voorkomen en bestrijden van radon in woningen.pdf (1.53 MB); TVN_212 Leidraad voor de installatie van zonneboilers.pdf (2.04 MB); TVN_213 Binnenvloeren van natuursteen.pdf (0.88 MB); TVN_214 Glas en glasproducten, functies van beglazing.pdf (8.46 MB); TVN_219 Dakbedekkingen met leien. Dakdetails, opbouw en uitvoering.pdf (2.27 MB); TVN_220 Belgische blauwe hardsteen of 'petit granit'uit het Tournaisiaanse geologische tijdperk (vervangt TV 156).pdf (6.64 MB); TVN_221 Plaatsing van glas in sponningen (De TV 214 en 221 vervangen de TV 110 en 113).pdf (1.31 MB); TVN_222 Dimensionering van schrijnwerk onder windbelasting.pdf (0.33 MB); TVN_223 Draagvloeren in niet-industriele gebouwen.pdf (3.03 MB); TVN_224 Waterwerende oppervlaktebehandeling (vervangt TV 140).pdf (1.74 MB); TVN_225 Daken met golfplaten van vezelcement; materiaalopbouw- uitvoering.pdf (4.09 MB); TVN_226 Onderhoud van brandwerende deuren.pdf (0.66 MB); TVN_227 Muurbetegelingen.pdf (0.6 MB); TVN_229 Groendaken.pdf (3.6 MB); TVN_230 Verhoogde vloeren.pdf (5.53 MB); TVN_231 Herstelling en bescherming van beton (gebouwen en burgerlijke bouwkunde).pdf (3.3 MB); TVN_232 Verlaagde plafonds.pdf (3.72 MB); TVN_233 Lichte binnenwanden.pdf (3.34 MB); TVN_234 Plaatsing van branwerende deuren (vervangt TV 185).pdf (5.01 MB); TVN_235 Condensatieketels.pdf (4.64 MB); TVN_236 Ontwerp en uitvoering van staalplaat-betonvloeren.pdf (3.52 MB); TVN_237 Keramische binnenvloerbetegelingen.pdf (4.94 MB); TVN_238 De applicatie van opzwellende verfsystemen op stalen constructies.pdf (3.17 MB); TVN_239 Mechanische bevestiging van de isolatie en de afdichting op geprofileerde staalplaten.pdf (7.76 MB); TVN_240 Pannendaken.pdf (6.45 MB); TVN_240_Add1 Dakpannen uit gebakken aarde.pdf (1.65 MB); TVN_240_Add2 Betonpannen.pdf (1.56 MB); TVN_241 Plaatsing van elastische vloerbekledingen.pdf (8.7 MB); TVN_242 Bijzondere bouwwerken uit glas Deel 1; structurele toepassingen.pdf (6.88 MB); TVN_243 Gevelbekledingen uit hout en plaatmaterialen op basis van hout.pdf (6.69 MB); TVN_244 Aansluitingsdetails bij platte daken; algemene principes (vervangt de TV 191) Uitgave Februari 2021.pdf (7.11 MB); TVN_245 Aanbevelingen voor het gebruik van koperen buizen voor de distributie van santitair koud en warm water (vervangt de TV 154).pdf (3.54 MB); TVN_246 Na-isolatie van spouwmuren door het opvullen van de luchtspouw.pdf (4.48 MB); TVN_247 Ontwerp en uitvoering van vloeistofdichte betonconstructies.pdf (4.75 MB); TVN_248 Gelijmde wapening voor de versterking van betonconstructies.pdf (2.82 MB); TVN_249 Leidraad voor de goede uitvoering van schilderwerken (herziening van de TV 159).pdf (7.22 MB); TVN_250 Referentiedetails voor ingegraven constructies.pdf (1.96 MB); TVN_251 Thermische isolatie van hellende daken.pdf (3.95 MB); TVN_252 Vocht in gebouwen Bijzonderheden van opstijgend vocht (vervangt de TV 210).pdf (2.64 MB); TVN_253 Parkeerdaken Deel 1; belastingen, ontwerpprincipes en samenstelling.pdf (4.05 MB); TVN_255 Luchtdichtheid van gebouwen.pdf (8.3 MB); TVN_256 Ontwerp en uitvoering van industriegebouwen in overeenstemming met de brandveiligheidseisen.pdf (6.94 MB); TVN_257 Bepleisteringen op buitenoisolatie (ETICS) vervangt gedeeltelijk de TV 209.pdf (9.37 MB); TVN_258 Praktische gids voor de basisventilatiesystemen voor woongebouwen (vervangt de TV's 192 en 203).pdf (5.1 MB); TVN_258.1 Ontwerpvoorbeeld van een ventilatiesysteem in een woning (Aanvulling 1 bij de TV 258).pdf (3.23 MB); TVN_259 Ondiepe geothermie. Ontwerp en uitvoering van bodemenergiesystemen met U-vormige bodemwarmtewisselaars.pdf (5.86 MB); TVN_260 Detaillering van de betonwapening (vervangt de TV 217).pdf (5.06 MB); TVN_261 Bijzondere bouwwerken uit glas Deel2; niet-structurele toepassingen (uitstalramen, deuren en gehelen uit gehard glas).pdf (4.16 MB); TVN_262 Leidraad voor de uitvoering van textiele vloerbekledingen.pdf (8.25 MB); TVN_263 Montage van zonnepanelen op hellende daken.pdf (2.64 MB); TVN_264 Referentiedetails voor spouwmuren.pdf (8.8 MB); TVN_265 Installaties voor de afvoer van afvalwater in gebouwen (herziening van TV 200).pdf (2.09 MB); TVN_266 Metalen dakbekledingen en gevelbekledingen met staande naden en roefnaden. Geactualiseerde uitgave 2022.pdf (6.7 MB); TVN_267 Betonvloeren voor binnentoepassingen ( herziening van TV 204).pdf (3.09 MB); TVN_268 Zichtbeton.pdf (6.3 MB); TVN_269 Houten vloerbedekkingen; plankenvloeren, parketten en houfineervloeren Deel1;materialen, terminologie en eisen.pdf (3.96 MB); TVN_270 Installaties voor hemelwaterafvoer onder vrij verval voor gebouwen. Ontwerp en dimensionering.pdf (4.91 MB); TVN_271 Uitvoering van metselwerk.pdf (7.7 MB); TVN_272 Houten vloerbedekkingen; plankenvloer, parketten en houtfineervloeren Deel 2; uitvoering (vervangt de TV 218).pdf (5.5 MB); TVN_273 Installatie van vloerverwarmingssystemen met warm water.pdf (2.36 MB); TVN_274 Referentiedetails voor.pdf (0.73 MB); TVN_275 Bijzondere bouwwerken uit glas Deel 3; niet-structurele toepassingen (glazen binnenwanden).pdf (2.67 MB); TVN_276 Leidraad voor de goede uitvoering van terrassen en garage-inritten op de volle grond.pdf (3.77 MB); TVN_277 Leidraad voor de goede uitvoering van harsgebonden vloeren (vervangt de TV 216).pdf (3.77 MB); TVN_278 Verwarmingsinstallaties met warm water; aanbevelingen om afzettingen en corrosie te voorkomen.pdf (1.76 MB); TVN_279 Harde bekledingen op buitenisolatie (ETICS met harde bekledingen).pdf (7.43 MB); TVN_280 Het platte dak Herziening van de TV 215.pdf (7.99 MB); TVN_281 Akoestische isolatie tussen woningen.pdf (17.33 MB); TVN_282 Brandveiligheid van gevels Ontwerp en uitvoering van gordijngevels (staal en aluminium).pdf (5.04 MB); TVN_283 Plaatsen van buitenschrijnwerk  Deel1 algemene aspecten (Vervangt de TV 188).pdf (4.43 MB); TVN_284 Binnenbepleisteringen ( Vervangt de TV's 199 en 201).pdf (3.68 MB); TVN_285 Uitvoeringen van betonconstructies.pdf (7.02 MB); TVN_286 Plaatsen van buitenschrijnwerk Deel 2 houten ramen in spouwmuurconstructies.pdf (0.37 MB); TVN_287 Stabiliteit van werkterreinen voor funderingsmachines en ontwerp van tijdelijke werkplatformen.pdf (2.19 MB); TVN_288 Plaatsen van buitenschrijnwerk Deel 3 vensters uit aluminium en pvc in spouwmuurconstructies.pdf (0.61 MB); TVN_289 Buitenbepleisteringen op metselwerk en beton (Vervangt gedeeltelijk TV 209).pdf (1.66 MB); TVN_290 Referentiedetails voor buitenbepleisteringen op metselwerk en beton.pdf (0.41 MB); TVN_291Eengezinswoningen met houten skelet.pdf (5.26 MB); TVN_292 Tijdelijke bemalingen op werven.pdf (9.09 MB); TVN_293 Brandveilig afdichten van doorvoeringen in brandwerende wanden.pdf (1.82 MB); TVN_294 Renovatiedetails voor hellende daken volgens het sarkingprocede.pdf (1.81 MB); TVN_295 Referentiedetails voor ETICS- Renovatie.pdf (0.89 MB); TVN_296 Gevelreiniging.pdf (7.28 MB); TVN_297 Opvoegen van metselwerk.pdf (0.96 MB); 

### Normen en regelgeving: eerste 60 van 290 bestanden (gesorteerd op naam), plus submap New folder

| Bestand | MB | Jaar in naam |
|---|---|---|
| NBN_A_24-301_1986(N)_scan.pdf | 0.4 | 1986 |
| NBN_A_24-302_1986(N).pdf | 0.26 | 1986 |
| NBN_A_24-303_1986(N)_scan.pdf | 0.24 | 1986 |
| NBN_A_24-303_A1_1990(N)_scan.pdf | 0.06 | 1990 |
| NBN_A_24-304_1986(N).pdf | 0.19 | 1986 |
| NBN_A_24-304_A1_1988(N).pdf | 0.07 | 1988 |
| NBN_B_03-003_2003(N).pdf | 0.17 | 2003 |
| NBN_B_03-004_2017(N).pdf | 2.17 | 2017 |
| NBN_B_06-001_1982(N).pdf | 3.5 | 1982 |
| NBN_B_06-005_1985(F_N).pdf | 0.65 | 1985 |
| NBN_B_11-205_1981(F_N)_scan.pdf | 0.32 | 1981 |
| NBN_B_11-208_1985(F_N)_scan.pdf | 0.17 | 1985 |
| NBN_B_12-108_2015(N).pdf | 0.52 | 2015 |
| NBN_B_12-109_2020(N).pdf | 0.35 | 2020 |
| NBN_B_12-110(N).pdf | 0.12 | geen |
| NBN_B_14-215_1983(F_N)_scan.pdf | 0.09 | 1983 |
| NBN_B_14-217_1983(F_N)_scan.pdf | 0.2 | 1983 |
| NBN_B_15-001_2024(N).pdf | 0.7 | 2024 |
| NBN_B_15-007_2018(N).pdf | 1.39 | 2018 |
| NBN_B_15-100_2018(N).pdf | 1.6 | 2018 |
| NBN_B_15-203_1990(N).pdf | 0.25 | 1990 |
| NBN_B_15-204_1973(NF).pdf | 0.27 | 1973 |
| NBN_B_15-210_1969(F_N)_scan.pdf | 0.39 | 1969 |
| NBN_B_15-211_1974(F_N)_scan.pdf | 0.2 | 1974 |
| NBN_B_15-215_2018(N).pdf | 0.44 | 2018 |
| NBN_B_15-216_1974(NF).pdf | 0.25 | 1974 |
| NBN_B_15-217_1984(NF).pdf | 0.21 | 1984 |
| NBN_B_15-226_1984(NF).pdf | 0.22 | 1984 |
| NBN_B_15-227_1973(NF).pdf | 0.63 | 1973 |
| NBN_B_15-228_1976(NF).pdf | 0.34 | 1976 |
| NBN_B_15-230_1976(NF).pdf | 0.44 | 1976 |
| NBN_B_15-231_1987(N)_scan.pdf | 0.15 | 1987 |
| NBN_B_15-236_1983(NF).pdf | 0.09 | 1983 |
| NBN_B_15-236_A1_1987(NF).pdf | 0.04 | 1987 |
| NBN_B_15-238_1992(N)_scan.pdf | 0.38 | 1992 |
| NBN_B_15-250_1991(N).pdf | 1.55 | 1991 |
| NBN_B_15-400_2024(N).pdf | 0.65 | 2024 |
| NBN_B_21-004_2020(N).pdf | 0.33 | 2020 |
| NBN_B_21-101_2004(N).pdf | 1.56 | 2004 |
| NBN_B_21-101_2016(N).pdf | 0.42 | 2016 |
| NBN_B_21-101_A2_2019(N).pdf | 0.33 | 2019 |
| NBN_B_21-101_A3_2020(N).pdf | 0.33 | 2020 |
| NBN_B_21-101_AC_2019(N).pdf | 0.18 | 2019 |
| NBN_B_21-106_2004(N).pdf | 1.23 | 2004 |
| NBN_B_21-106_2016(N).pdf | 0.34 | 2016 |
| NBN_B_21-106_A2_2020(N).pdf | 0.32 | 2020 |
| NBN_B_21-106_AC_2021(N).pdf | 0.25 | 2021 |
| NBN_B_21-211_2023(N).pdf | 0.39 | 2023 |
| NBN_B_21-311_2023(N).pdf | 0.24 | 2023 |
| NBN_B_21-411_2006(N).pdf | 0.57 | 2006 |
| NBN_B_21-600_2009(N).pdf | 0.12 | 2009 |
| NBN_B_21-602_2007(N).pdf | 0.59 | 2007 |
| NBN_B_21-603_2015(N).pdf | 0.45 | 2015 |
| NBN_B_21-604_2009(N).pdf | 0.03 | 2009 |
| NBN_B_21-605_2023(N).pdf | 0.58 | 2023 |
| NBN_B_21-606_2022(N).pdf | 1.2 | 2022 |
| NBN_B_21-701_1999(N)_scan.pdf | 5.24 | 1999 |
| NBN_B_22-104_1983(F_N)_scan.pdf | 0.85 | 1983 |
| NBN_B_22-105_1985(NF).pdf | 0.74 | 1985 |
| NBN_B_25-002-1_2019(N).pdf | 1.74 | 2019 |

Jaarverdeling van alle 290 normbestanden (laatste jaartal in de bestandsnaam; Eurocode-nummers 1990-1999 niet meegeteld):

1969: 1; 1973: 2; 1974: 2; 1976: 2; 1980: 2; 1981: 2; 1982: 1; 1983: 7; 1984: 2; 1985: 3; 1986: 7; 1987: 5; 1988: 1; 1990: 2; 1991: 3; 1992: 2; 1993: 4; 1995: 2; 1996: 4; 1997: 5; 1998: 6; 1999: 9; 2000: 2; 2002: 2; 2003: 9; 2004: 5; 2005: 11; 2006: 4; 2007: 6; 2008: 1; 2009: 3; 2010: 14; 2011: 46; 2012: 7; 2013: 17; 2014: 7; 2015: 15; 2016: 7; 2017: 3; 2018: 6; 2019: 7; 2020: 10; 2021: 10; 2022: 5; 2023: 8; 2024: 8; 2025: 1; geen: 1; 

Aantal van voor 2000: 74
; 2000-2014: 134
; 2015 en later: 80


Grootste normbestanden (>4 MB): 
NBN_D_51-003_2021(N).pdf (5.8 MB);NBN_B_21-701_1999(N)_scan.pdf (5.2 MB);NBN_B_41-001_1999(N)_scan.pdf (22.2 MB);NBN_DTD_B_61-001_2021(N).pdf (4.5 MB);NBN_S_21-100-1_2025(N).pdf (4.9 MB);NBN_S_23-002-3_2020(N).pdf (4.4 MB);

### Buildwise Documenten / dimensioneringsmethodes (16 pdf + submap Geen download met 3 schermafbeeldingen, 52,7 MB)

| Bestand | MB | Leesbaar via MCP (<5 MB) |
|---|---|---|
| WTCB_Rapport_6 PROBE Stap-voor-stap-renovatie van kantoorgebouwen.pdf | 2.92 | ja |
| WTCB_Rapport_7 Warmteoverdracht door wanden in contact met de grond.pdf | 1.41 | ja |
| WTCB_Rapport_8 Projectportaalsites, elektronisch documentbeheer.pdf | 1.11 | ja |
| 31300_nl_unprotected_WTCB_Rapport_9 Initiele thermische prestaties van dunne reflecterende producten.pdf | 2.43 | ja |
| WTCB_Rapport_10 Veiligheid bij de uitvoering van geprefabriceerde betonconstructies.pdf | 4.28 | ja |
| WTCB_Rapport_11 Toepassing van de Eurocodes op het ontwerp van buitenschrijnwerk.pdf | 2.34 | ja |
| 31300_nl_unprotected_WTCB_Rapport_13 Fysisch en mechanisch gedrag van hout-betonvloeren.pdf | 2.04 | ja |
| 31300_nl_unprotected_WTCB_Rapport_14 Ontwerp en dimensionering van cv-installaties met warm water.pdf | 7.45 | nee |
| WTCB_Rapport_15 Drukverliezen en dimensionering van luchtdistributienetwerken.pdf | 3.93 | ja |
| WTCB_Rapport_16 Berekening van verstijvers voor uitstalramen.pdf | 3.10 | ja |
| WTCB_Rapport_17 Keuze voor duurzame bouwmaterialen.pdf | 6.41 | nee |
| WTCB_Rapport_18 Dimensionering van vloerverwarmingssystemen met warmwaterbuizen.pdf | 1.02 | ja |
| WTCB_Rapport_20 Richtlijnen toepassing Eurocode 7 in Belgie (NBN EN 1997-1 ANB).pdf | 0.70 | ja, gelezen: WTCB-Rapport nr. 20, november 2020 |
| WTCB_Rapport_21 Installaties voor hemelwaterafvoer onder vrij verval.pdf | 2.18 | ja |
| WTCB_Rapport_22 CV met warm water, dimensionering gesloten expansievaten.pdf | 0.95 | ja |
| dimensioneringsmethode_23 CROW-CUR Rapport 231;2022 Handboek Diepwanden.pdf | 9.07 | nee |
| dimensioneringsmethode_24 Sanitairwarmwaterproductie in eengezinswoningen.pdf | 1.58 | ja |

### Buildwise Documenten / meetstaten van gebouwen (22 pdf, 33,9 MB; reeks 'Meetstaat van gebouwen' WTCB, toepassing NBN B 06-001)

| Bestand | MB |
|---|---|
| Meetstaat_1 Het opstellen van de meetstaat.pdf | 2.24 (gelezen: WTCB-werkgroep Uittrektechnieken, jaartallen in tekst tot 1980; cursusdeel) |
| Meetstaat_2_1 Algemeenheden, gemeenschappelijke clausules.pdf | 0.89 |
| Meetstaat_2_3 Grondwerk.pdf | 2.09 |
| Meetstaat_2_4 Diepfunderingen.pdf | 1.26 |
| Meetstaat_2_5 Ter plaatse gestort beton.pdf | 1.87 |
| Meetstaat_2_6_7 Systeemvloeren en -daken.pdf | 0.74 (zelfde grootte als volgende; mogelijk dubbel) |
| Meetstaat_2_6_7 Vooraf vervaardigd betonwerk en kunststeen.pdf | 0.74 |
| Meetstaat_2_8 Metselwerk.pdf | 1.78 |
| Meetstaat_2_12 Rioleringen.pdf | 1.46 |
| Meetstaat_2_13 Timmerwerk in hout.pdf | 2.36 |
| Meetstaat_2_14_15 Schrijnwerk in hout.pdf | 1.61 |
| Meetstaat_2_16 Metaalbouw.pdf | 1.32 |
| Meetstaat_2_18 Dakbedekkingen.pdf | 1.47 (gelezen: aflevering 18, C. Geiregat, jaartallen in tekst tot 1984) |
| Meetstaat_2_20_21 Sanitaire leidingen.pdf | 1.64 (zelfde grootte als volgende; mogelijk dubbel) |
| Meetstaat_2_20_21 Sanitaire toestellen en waterkranen.pdf | 1.64 |
| Meetstaat_2_23 Elektrische installaties.pdf | 3.12 |
| Meetstaat_2_24 Elektromechanische installaties.pdf | 1.02 |
| Meetstaat_2_27_1 Binnenbekleding 1 Tegelwerken.pdf | 1.05 |
| Meetstaat_2_27_2 Binnenbekleding 2 Bepleistering.pdf | 1.49 |
| Meetstaat_2_27_3 Binnenbekleding 3 Soepele bekledingen.pdf | 0.92 |
| Meetstaat_2_29 Beglazing.pdf | 1.00 |
| Meetstaat_2_30 Schilderwerk.pdf | 1.51 |

### vb werfverslag (43 pdf, 150 MB; ArchiSnapper-verslagen project 2110 Kwekerijstraat 34 Antwerpen, 2021-2024)

| Bestand | MB |
|---|---|
| 2110-1.pdf | 1.96 (2021-05-10) |
| 2110-2.pdf | 1.62 (2021-05-10) |
| 2110-3.pdf | 2.48 (2021-05-10) |
| 2110-4.pdf | 6.66 (2021-06-02), >5 MB |
| 2110-5.pdf | 3.31 (2021-06-02) |
| 2110-6.pdf | 4.82 (2021-06-29) |
| 2110-7.pdf | 3.86 (2021-06-29) |
| 2110-8.pdf | 2.84 (2023-02-20) |
| 2110-9.pdf | 1.73 (2023-02-20) |
| 2110-10.pdf | 2.76 (2023-02-20) |
| 2110-11.pdf | 1.20 (2023-02-20) |
| 2110-12.pdf | 2.59 (2023-02-20) |
| 2110-13.pdf | 1.88 (2023-02-20) |
| 2110-14.pdf | 2.71 (2023-02-20) |
| 2110-15.pdf | 2.52 (2023-02-20) |
| 2110-16.pdf | 1.05 (2023-02-20) |
| 2110-17.pdf | 2.27 (2023-02-20) |
| 2110-18.pdf | 12.15 (2023-02-20), >5 MB |
| 2110-19.pdf | 4.91 (2023-02-20) |
| 2110-20.pdf | 3.35 (2023-02-20) |
| 2110-21.pdf | 1.98 (2023-02-20) |
| 2110-22.pdf | 2.14 (2023-02-20) |
| 2110-23.pdf | 2.84 (2023-02-20) |
| 2110-24.pdf | 2.72 (2023-02-20) |
| 2110-25.pdf | 3.24 (2023-02-20) |
| 2110-26.pdf | 1.78 (2023-02-20) |
| 2110-27.pdf | 1.65 (2023-02-20) |
| 2110-28.pdf | 1.46 (2023-02-20) |
| 2110-29.pdf | 2.64 (2023-02-20) |
| 2110-30.pdf | 2.17 (2023-02-20) |
| 2110-31.pdf | 0.86 (2023-03-14) |
| 2110-32.pdf | 0.76 (2023-03-14) |
| 2110-33.pdf | 0.73 (2023-03-14), gelezen: verslag 33, 10-03-2023, samenvatting van twee bezoeken, ArchiSnapper-opmaak, tweetalig NL/EN, rubrieken binnenschrijnwerk/buitenwerk/algemeen |
| 2110-34.pdf | 2.74 (2023-03-29) |
| 2110-35.pdf | 3.23 (2023-03-29) |
| 2110-36.pdf | 3.39 (2023-06-26) |
| 2110-37.pdf | 2.14 (2023-06-26) |
| 2110-38.pdf | 0.23 (2023-06-26) |
| 2110-39.pdf | 4.82 (2023-07-05) |
| 2110-40.pdf | 1.00 (2023-12-15) |
| 2110-41.pdf | 0.14 (2023-12-15), gelezen: verslag 41, 24-08-2023, balustrades terras en trap, 2 pagina's |
| 2110-42.pdf | 9.86 (2023-12-19), >5 MB |
| 2110-43-Voorlopige Oplevering.pdf | 12.12 (2024-01-11), >5 MB; identiek in grootte aan Werfverslagen GPT/Voorbeeld_werfverslag.pdf |

## 3. Overige mappen

### vb werfverslag
Zie tabel hierboven. 43 ArchiSnapper-pdf's van project 2110 (Kwekerijstraat 34, Antwerpen, renovatie), verslagen 1 t/m 43 (2021-2024), 150 MB. Vier bestanden >5 MB (4, 18, 42, 43). Twee gelezen (33 en 41): vaste opmaak H-Architects BVBA, tabel aanwezigen, observaties per rubriek (Buitenwerk, Binnenafwerking, Binnenschrijnwerk, Algemeen), nummering verslag.punt, slotzin "zonder tegenbericht binnen 5 kalenderdagen". Dit is het stijlvoorbeeld voor de agent.

### Werfverslagen GPT (3 items)
| Bestand | MB | Opmerking |
|---|---|---|
| Voorbeeld_werfverslag.pdf | 12.12 | zelfde grootte en datum als vb werfverslag/2110-43-Voorlopige Oplevering.pdf: dubbel |
| ALL_Normen en Regelgeving.pdf | 54.2 | dubbel van Technische Voorlichtingen/merged files/ALL_Normen en Regelgeving.pdf |
| submap Tech voorlichtingen merges | 10 pdf, 504 MB | Tech Voorlichtingen - 1 t/m 10.pdf; 1 t/m 9 zijn dezelfde bestanden (identieke groottes) als in merged files; nr. 10 (46,4 MB) staat alleen hier |

Conclusie: deze map was de upload-set voor een ChatGPT-project (september 2025); alles >5 MB, niets leesbaar via MCP.

### Templates_Sjablonen_H-architects
Rootbestanden: HowToPublish_PDF_With_Vectorworks.pdf (6,0 MB) en .mov (339 MB), Signs for pictures for measurements.docx, STD_Opmetingen-Leeg.jpg (6,2 MB), TitelBlock_A4_A3.vwx, Uitvoering plans- start before permissin.docx.
Submappen: Oud_werkdocumenten (593 bestanden, 21 MB: 564 png, 19 json, 4 dwg, 2 vwx, 2 lin, zip, pdf; oude Vectorworks-werkmap), Bouwaanvraag (2 vwx-voorbeelddossiers 2085 en 2199, 31 en 87 MB), VerklarendeNotaOmgevingsloket (2 docx), PublicTender (5 pdf: HA_Projecten 8,2 MB, HA_Voorstelling, CV's), STD (16 submappen met standaardbrieven: First Contact, Gewestplan, Water Formulier, OMV vragen, Yellow Paper, Common Wall, Riolering, Verklarende Nota, HA Logo, Measurement Layout enz.; inhoud niet gelist, buiten de werfverslagscope).
Voor de werfverslag-agent: geen werfverslagsjabloon aanwezig; alleen huisstijl (HA Logo, TitelBlock).

### Safety_Veiligheidscoordinatie (208 bestanden, 257 MB)
| Submap | Bestanden | Types |
|---|---|---|
| VC_Algemeen&Scholing | 207 | pdf 90, jpeg/jpg 43, png 32, docx 31, eml 9, xls 2 |
| VC_PostInterventieDossier-PID | 1 | pdf 0,2 MB |

Inhoud VC_Algemeen&Scholing: lesopnames en PowerPoints van de opleiding veiligheidscoordinator (Vekmo, september 2021, Les 1 t/m 7 als pdf 2 tot 8 MB), submap 10_Templates_NOG_NIET_KLAAR met Checklist_werfverslag.docx (gelezen: rubriekenlijst veiligheid: documenten, werfinrichting, PBM, valgevaar, stellingen, hijswerktuigen, gevaarlijke producten, weer, PID), Coordinatiedagboek.docx, Overeenkomst.docx, VeiligheidsEnGezondheidsplan.docx, Template_Postinterventiedossier. Volledige lijst in de tool-uitvoer; 60 van 208 zijn opleidingsmateriaal met foto's.
Bruikbaar: de checklist als rubriekenlijst "veiligheid" in elk werfverslag; de PID-template voor de opleveringsfase.

### keuring richtlijnen (4 pdf, 7,1 MB)
| Bestand | MB | In een regel |
|---|---|---|
| vademecum-update-2021.pdf | 3.18 | gelezen: VLARIO Vademecum praktisch afkoppelen van hemelwater, update januari 2021 (nieuwere versie oktober 2023 staat in Wetgeving/Hemelwaterverordening) |
| Verduidelijking-schemas-MB-Keuring-01-04-2022.pdf | 0.74 | VLARIO-interpretatie afkeurschema's MB keuring privewaterafvoer, 1-4-2022 |
| Overzichtsdocument-keuring-privewaterafvoer-voor ontwerpers.pdf | 1.14 | gelezen: VLARIO versie 7, 1 april 2022; checklist rioleringsplan, afkeurcriteria, RWA/DWA-richtlijnen per afvoer (terras, oprit, kelder, groendak, cv-condens, zwembad) |
| Folder-keuring-privewaterafvoer-2021-1.pdf | 2.06 | folder keuring voor de burger |

### Wetgeving (16 submappen, minstens 473 bestanden, 4,0 GB)
| Submap | Bestanden | Opmerking |
|---|---|---|
| 1)Vrijstelllingsbesluit | 4 + submap | Vrijstellingsbesluit pdf 0,6 MB, OL_ChecklistVrijstelling, webloc, GSJ-advocaten mp4 38 MB |
| 2)melding | 1 | NL_Brochure_Vrijstelling&Melding.pdf 1,1 MB |
| 3)vergunning | 0 | leeg |
| ANTWERPEN WETGEVING | 16 pdf, 60 MB | bouwcode-achtige documenten (augustus 2025) |
| Leuven WETGEVING | 400 (399 pdf), 993 MB | grootste submap, augustus 2025 |
| Besluit ... vrijgesteld van medewerking architect | 2 | pdf 0,1 MB + docx (juli 2025) |
| burgerlijk wetboek lichten en zichten | 2 pdf | 0,3 MB |
| Functiewijziging | 1 pdf | |
| GemeneMuren | 13 | pdf 8, docx, png, webloc; 39 MB |
| Hemelwaterverordening | 7 | Hemelwaterverordening.pdf (gelezen: BVR Hemelwaterverordening 2023, in werking 2-10-2023, putvolumes 5000/7500/10000 l, infiltratie 8 procent en 33 l/m2), technisch-document-gsv-2023 (4,6 MB), vademecum oktober 2023 (3,2 MB), RBI 2023, provinciale verordening, infiltratievoorzieningen 2023 |
| OpsplitsenWoning | 1 docx | |
| R0_Ruimtelijke Ordening | 35, 2,9 GB | pdf 24, webloc 10, docx; video's vermoedelijk |
| Regularisatie | 8 | artikelen over bouwmisdrijven en regularisatie (2021); Boek Niet-vergunde constructies 177 MB |
| Verkavelingen | 1 webloc | |
| VermoedenVanVergunning_Antwerpen | 5 | pdf 3, docx, webloc |
| Wet_Peeters-Borsus | 5 | verzekeringsplicht 2018/2019, checklist, eml |

### BiB_05.Lastenboeken (10 submappen, minstens 486 bestanden, 265 MB)
| Submap | Bestanden | Opmerking |
|---|---|---|
| Bestekken_0.AandachtspuntenOpTeNemen | 14 | msg 9, pdf 2, jpg 2, doc |
| Bestekken_1.Standaardbestekken | 447 (lijst afgekapt), 261 MB | doc 288, pdf 78, xls 22, docx 10, zip 5, url 8, ppt, rtf; ook bestanden zonder extensie; vermoedelijk VMSW/typebestek-teksten en productspecificaties |
| Bestekken_2.Restauratie&Renovatie | 4 submappen | Res_1.Standaardbestekken, Res_Voorbeeldbestekken, Res_Voorbeelden van aanpak, Res_Bestekteksten (niet dieper gelist) |
| Bestekken_3.Onderhoudsbestekken_dd120120 | 3 + 8 submappen | NMBS-stations (Antwerpen Centraal, Berchem, Leuven, Mechelen, Hasselt, Vilvoorde), Roltrappen, Afvalophaling; 2011 |
| Bestekken_4.Voorbeelden | 9 submappen | VbBestek_Koen, Tektoniek, NMBS, Technieken, Technum, Verkoopsbestek enz. |
| Bestekken_5.Diverse teksten | 25 | doc 24, pdf 1 |
| Bestekken_6.Veiligheid | 1 | NAVB lastenboek algemene bepalingen 2012 (.doc) |
| Bestekken_10.Ramingsprijzen | 10 submappen + 1 xls | KBC, Livios 2020, UPA-BUA borderel, Aspen Index, VMSW, Tektoniek, Technum 1998, NMBS, kbkw.be, Hout_Kostprijsberekening |
| Bestekken_20.Veiligheidscoordinatie | 4 submappen | SVGP_Wegenbouw, NMBS, Vennix, Aquafin |
| Bestekken_50.Tools | 3 | HandleidingUploadmeetstaat 2016, PS Form xls 2023, IFRS componenten 2009 |

### BiB_03.Standard_STD (8 bestanden + 2 submappen)
| Bestand | In een regel |
|---|---|
| PV_voorlopige_oplevering_c3a2019.dotx | gelezen: C3A-sjabloon proces-verbaal voorlopige oplevering (voorbehoud, inhouding, borg, termijn, handtekeningen) |
| PV_definitieve_oplevering_c3a2019.dotx | zelfde reeks, definitieve oplevering |
| Std_EMU_Klant_StartDerWerken.docx | gelezen: klantbrief start der werken melden in Omgevingsloket (8 dagen vooraf, vervaltermijn 2 jaar) |
| Std_EMU_Klant_ReminderGeleAffiche.docx | klantbrief gele affiche |
| Aanwijzingen voor aangifte start der werken.docx / Instructions for declaration start of work.docx | NL/EN handleiding |
| Apen_AaanvraagformulierBrandpreventie.docx | aanvraagformulier brandpreventie |
| Std_Teamleader/Tickets | Eerste ticket naar klant.docx, First Contact.docx |
| Std_OmgevingsLoket | submap, niet dieper gelist |

### 0. Omgevingsloket (6 submappen, 131 bestanden, 3,6 GB)
11_OMV vragen (3 docx, 3 png), 12_Eigendomgrens DXF Downloaden (2 mov, 234 MB), 14_Water Form (docx + 3 pdf, 20 MB), 20_VerklarendeNota (4 docx), KijkOokOnder 2.Ontwerpgids:17.Ontwerpproces (leeg of niet gelist), BiB_01.ArchiManagement (115 bestanden, 3,4 GB: pdf 64, msg 25, tif 7, webloc 8, doc 5, xlsx 3). Vergunningsfase, niet werf.

### 001. Orde van Architecten (3 submappen, 133 bestanden, 87 MB)
juridische bibliotheek (117: pdf 111, docx 6), opvolging (11: docx 8, pdf 3), plichten (5 docx). Deontologie en aansprakelijkheid; relevant voor de opleveringsfase (tienjarige aansprakelijkheid, controleplicht), niet bouwtechnisch.

### Calculatie-meetstaat-bestek (7 submappen + 4 bestanden, 316 bestanden, 9,5 GB)
| Item | Bestanden | Opmerking |
|---|---|---|
| C3A | 259, 5,5 GB | dotx 108, docx 70, xlsx 20, xltx 8, pdf 18, mp4 9, zip 5, webloc 8; C3A-bestekbibliotheek en opleidingsvideo's |
| eenheidsprijzen | 16, 3,9 GB | pdf 15, xlsx 1 (grote scans) |
| MeetstaatVanGebouwen | 21 pdf, 33 MB | dezelfde WTCB-reeks als Buildwise/meetstaten van gebouwen: dubbel |
| Aaa eenheidsprijzen | 4 | pdf 2, xls 2 |
| BB-SFB inlichting | 2 pdf, 14 MB | BB/SfB-classificatie |
| vmsw | 10 docx | |
| berekening opervlakte | 1 pdf | |
| N251HO_Kostprijsberekening.pdf/.xlsx, Meetstaat_TellenPleisterwerken.eml | 3 | |

### CursusEPB (5 submappen, 203 bestanden, 207 GB)
EPC (125 bestanden, 199 GB: 31 mov lesopnames 2021, 66 pdf cursus energiedeskundige type A, inspectieprotocol EPC 2021), EPB (68, 2,3 GB: SBM-modules 1 t/m 8 pdf, oefeningen .peb, 8 mp4), NAV cursus renovatieverplichting (4 mp4, 2 GB), Renovatie niet-residentiele gebouwen (2 mov + sbmreno.pdf), Ventilatie_Cursus (3 pdf: modules 6.1 en 6.2 ventilatie 2020, Bijlage X). Cursusmateriaal; voor de werf alleen Ventilatie_Cursus en EPB-module 3-5 Veiligheid op de werf, 3-4b Bouwtechniek en 3-4c Bouwfasering mogelijk nuttig.

### Dubbelcontrole "Boeken,Tijdschriften & Manuals" en "(renamed)"
- Origineel: 4 submappen (tijdschriften met NAV Nieuws, Feeling Wonen, Ik ga Bouwen 6 nummers 195-448 MB, BENO, Arch-Index, Bouwen met Baksteen 20 nummers; Manuals: Macbook, Archisnapper (leeg gelist), iPhone, "Deica 510 lasermeter"; BOEKEN: Bouw met Bouwstenen 356 MB, Anders Renoveren 212 MB, verbouwen en aanbouwen 120 MB, De Renovatie Bijbel 379 MB, plus Management/Marketing/ondernemen/Boekhouden; syllabus classes: Asbestverwijderen basisopleiding 68 MB, Expert training schadedossiers bouw deel 1 en 2 (204 en 229 MB, deel 2 staat er twee keer onder licht verschillende naam)).
- (renamed): alleen Manuals (Leica 510 lasermeter, Archisnapper, iPhone, Macbook) met identieke bestanden (zelfde groottes). Het is een restant van een hernoemactie: de map "(renamed)" is volledig dubbel en kan weg; alles bouwtechnisch zit in het origineel. Alles in deze map is >5 MB behalve Shortcuts Mac.pdf en de Bouwen met Baksteen-nummers (1 tot 12 MB).

## 4. Beoordeling

### 4.1 Bruikbaar als naslag per bouwfase (alleen bestanden <5 MB, leesbaar via MCP, tenzij anders vermeld)

| Fase | Werfpunt | Bron (map Technische Voorlichtingen tenzij anders) |
|---|---|---|
| afbraak | sloop beton, procedés | TV 144 (1982, alleen terminologie) |
| afbraak | asbest | syllabus classes/Asbestverwijderen (68 MB, lokaal) |
| afbraak, ruwbouw | bemaling | TV 292 Tijdelijke bemalingen op werven (9,1 MB, lokaal) |
| ruwbouw | funderingen, grondonderzoek | WTCB_Rapport_20 Eurocode 7 (2020); TV 147 (1983, verouderd); TV 287 werkplatformen funderingsmachines (2,2 MB) |
| ruwbouw | kelder, waterdichting | TV 247 vloeistofdicht beton (2012/2021); TV 250 referentiedetails ingegraven constructies (2014) |
| ruwbouw | beton, wapening | NBN B 15-001:2024 (Normen); TV 260 detaillering wapening (5,1 MB, net te groot); TV 285 uitvoering betonconstructies (7,0 MB, lokaal); TV 127 maatafwijkingen (1979) |
| ruwbouw | metselwerk, voegen | TV 271 uitvoering metselwerk (7,7 MB, lokaal); TV 297 opvoegen (2025); TV 264 referentiedetails spouwmuren (8,8 MB, lokaal) |
| ruwbouw | spouwisolatie, na-isolatie | TV 246 (2012/2022) |
| ruwbouw | opstijgend vocht | TV 252 (2014) |
| ruwbouw | draagvloeren, vervormingen | TV 223 (2002); TV 132 (1980, verouderd); TV 236 staalplaat-beton (3,5 MB) |
| dak | plat dak | TV 280 (8,0 MB) en TV 244 aansluitingsdetails platte daken 2021 (7,1 MB): beide lokaal; TV 229 groendaken (2006); TV 253 parkeerdaken (2014) |
| dak | hellend dak, isolatie | TV 251 (2014); TV 294 sarking-renovatie (2025) |
| dak | pannen, leien | TV 240 pannendaken (6,5 MB, lokaal) + Add1 en Add2 (1,6 MB elk); TV 219 leien (2001); TV 195 natuurleien (1,0 MB); TV 202 betonpannen (1996, vervangen door TV 240) |
| dak | hemelwaterafvoer | TV 270 (2019); WTCB_Rapport_21 (dimensionering); Hemelwaterverordening 2023 (Wetgeving) |
| dak | zonnepanelen | TV 263 (2017) |
| dak | metalen daken | TV 266 staande naden 2022 (6,7 MB, lokaal) |
| buitenschrijnwerk | plaatsing ramen | TV 283 (2022), TV 286 hout (2023), TV 288 alu/pvc (2023) |
| buitenschrijnwerk | beglazing | TV 221 (2001); TV 214 glas (8,5 MB, lokaal); TV 222 windbelasting (2001); TV 206 inbraak (1,1 MB) |
| buitenschrijnwerk | rolluiken, kitvoegen | TV 143 (2,7 MB); TV 124 kitvoegen (1,2 MB) |
| gevel | buitenbepleistering, ETICS | TV 289 (2023); TV 290 referentiedetails (0,4 MB); TV 257 ETICS (9,4 MB, lokaal); TV 274 nieuwbouw ETICS (0,7 MB); TV 295 renovatie ETICS (2025); TV 279 harde bekleding (7,4 MB, lokaal); TV_RECAP_17 ETICS 20 aandachtspunten (5,2 MB) |
| gevel | hydrofobering, reiniging | TV 224 (2002); TV 296 gevelreiniging (7,3 MB, lokaal) |
| gevel | houten gevelbekleding | TV 243 (6,7 MB, lokaal) |
| technieken | riolering binnen | TV 265 (2018); Digest 1 (1993, vervangen) |
| technieken | privewaterafvoer, keuring | keuring richtlijnen/Overzichtsdocument v7 (2022) en Verduidelijking schema's (2022); Hemelwaterverordening 2023 en vademecum 2023 (Wetgeving) |
| technieken | ventilatie | TV 258 (5,1 MB, net te groot); TV 258.1 (2024); Digests 5, 6, 7 (klein); TV 187 dampkappen (0,8 MB) |
| technieken | verwarming | TV 235 condensatieketels (2008); TV 278 corrosie cv (1,8 MB); TV 273 vloerverwarming (2020); WTCB_Rapport_18 en 22; TV 212 zonneboilers (1999, verouderd) |
| technieken | sanitair leidingwerk | TV 207 kunststof (1998); TV 245 koper (3,5 MB); TV 145 verzinkt (0,7 MB) |
| technieken | brand | TV 293 doorvoeringen (2024); TV 234 brandwerende deuren (5,0 MB, net te groot); TV 226 onderhoud (2002); TV 238 opzwellende verf (3,2 MB) |
| technieken | luchtdichtheid | TV 255 (8,3 MB, lokaal) |
| technieken | radon | TV 211 (1999) |
| afwerking | binnenbepleistering | TV 284 (2022); Digest 4 en 14 (klein) |
| afwerking | dekvloeren | TV 189 (niet gelezen), TV 193 (1994), Digest 2; TV 177 woordenlijst |
| afwerking | vloertegels, muurtegels | TV 237 (2009); TV 227 (2003); TV 213 natuursteen (0,9 MB) |
| afwerking | houten vloeren, parket | TV 269 (2019); TV 272 deel 2 uitvoering (5,5 MB, net te groot) |
| afwerking | hars, beton, soepel, textiel | TV 277 (2021); TV 267 (2019); TV 241 elastisch (8,7 MB) en TV 262 textiel (8,3 MB) lokaal; TV 165 (7,2 MB) |
| afwerking | lichte wanden, plafonds, verhoogde vloeren | TV 233 (2007); TV 232 (2007); TV 230 (5,5 MB) |
| afwerking | schilderwerk | TV 249 (7,2 MB, lokaal); TV 112 woordenschat (2,1 MB) |
| afwerking | trappen | TV 198 (1995) |
| oplevering | PV voorlopige en definitieve oplevering | BiB_03.Standard_STD/PV_*_c3a2019.dotx |
| oplevering | toleranties, vlakheid | TV 127 (1979); per TV de paragraaf toleranties (284, 237, 267) |
| oplevering | postinterventiedossier, veiligheid | Safety/VC_PostInterventieDossier-PID; Safety/10_Templates/Checklist_werfverslag.docx |
| alle fasen | meetstaat en hoeveelheden | meetstaten van gebouwen (22 afleveringen; ook dubbel in Calculatie-meetstaat-bestek/MeetstaatVanGebouwen) |
| alle fasen | stijl en structuur van het verslag | vb werfverslag/2110-33 en 2110-41 (ArchiSnapper-opmaak H-Architects) |

### 4.2 Verouderd (ouder dan 2015 of vervangen)
- Expliciet vervangen volgens de titel of inhoud: TV 202 (door TV 240 Add2), TV 209 (deels door TV 289 en 257), Digest 1 en TV 114 (door TV 265), TV 140 (door 224), TV 188 (door 283), TV 199/201 (door 284), TV 200 (door 265), TV 204 (door 267), TV 208 (door 297), TV 210 (door 252), TV 216 (door 277), TV 218 (door 269), TV 215 (door 280), TV 191 (door 244), TV 192/203 (door 258), TV 185 (door 234), TV 121/156 (door 197/220), TV 110/113 (door 214/221), TV 154 (door 245), TV 159 (door 249). De oude nummers staan niet in de map, alleen de opvolgers; dat is goed.
- Ouder dan 2015 en niet vervangen, met voorzichtigheid te gebruiken: TV 112, 115, 116, 123, 124, 125, 127, 129, 132, 143, 144, 145, 146, 147, 148, 150, 153, 155, 163.1/163.2, 164, 165, 168, 170, 174, 175, 177, 178, 179, 180, 181, 182, 186, 187, 189, 193, 194, 195, 196, 197, 198, 206, 207, 211, 212, 213, 214, 219, 220, 221, 222, 223, 224, 225, 226, 227, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239, 241, 242, 243, 246 (herdruk 2022), 247 (corr. 2021), 248, 249, 250, 251, 252, 253 (allen 2014). Regel voor de agent: bij TV's van voor 2010 altijd eerst nakijken of Buildwise ondertussen een opvolger heeft (de map is in augustus 2025 samengesteld, dus de lijst is actueel tot dan).
- Normen: 290 bestanden; 74 van voor 2000 (NBN B 15-2xx betonproeven jaren 70-80, NBN B 06/11/14/22/27 jaren 80, NBN I 10 jaren 80), 134 uit 2000-2014 (vooral Eurocodes 2002-2013 met ANB), 80 van 2015 of later, 2 zonder jaartal in de naam. Van de Eurocodes staan vaak meerdere edities naast elkaar (bv. NBN EN 1990 2002 en 2015, NBN EN 1991-1-1 2002 en 2015, NBN EN 1993-1-1 2005/2015/2018, NBN EN 1998-1 2011/2014/2015): de agent moet de nieuwste editie plus bijhorende ANB nemen.
- keuring richtlijnen/vademecum-update-2021: vervangen door vademecum oktober 2023 in Wetgeving/Hemelwaterverordening; de Hemelwaterverordening 2023 vervangt de GSV 2013 waarnaar het Overzichtsdocument 2022 nog verwijst.
- WTCB-Rapport 21 (hemelwaterafvoer) is de rekenbijlage bij TV 270 en blijft geldig; Rapport 17 (duurzame materialen) en 8 (projectportaalsites) zijn geen werfnaslag.

### 4.3 Te groot voor de MCP (>5 MB), lokaal downloaden
- Technische Voorlichtingen (30 pdf): TV 129 (22,7), 281 (17,3), 257 (9,4), 292 (9,1), 264 (8,8), 241 (8,7), 186 (8,5), 214 (8,5), 255 (8,3), 262 (8,3), 280 (8,0), 239 (7,8), 271 (7,7), 279 (7,4), 296 (7,3), 249 (7,2), 165 (7,2), 244 (7,1), 285 (7,0), 256 (6,9), 242 (6,9), 243 (6,7), 266 (6,7), 220 (6,6), 240 (6,5), 268 (6,3), 259 (5,9), 170 (5,7), 230 (5,5), 272 (5,5), 291 (5,3), 197 (5,3), 258 (5,1), 260 (5,1), 234 (5,0), TV_RECAP_17 (5,2). Van deze zijn voor de werf het belangrijkst: 280, 244, 271, 264, 240, 255, 257, 285, 258, 249, 272, 260, 234.
- merged files en Werfverslagen GPT: alle 13 pdf en 2 md (33 tot 65 MB).
- dimensioneringsmethodes: Rapport 14 (7,5), Rapport 17 (6,4), CROW-CUR 231 (9,1).
- Normen: NBN_B_41-001_1999 scan (22,2), NBN_D_51-003_2021 (5,8), NBN_B_21-701_1999 scan (5,2).
- vb werfverslag: 2110-4, -18, -42, -43; Werfverslagen GPT/Voorbeeld_werfverslag.
- Boeken en syllabi: alles behalve Shortcuts Mac en de Bouwen met Baksteen-nummers.
Praktisch: de agent kan deze via de Dropbox-API (download_link) binnenhalen en lokaal met pypdf of Vision-OCR lezen; de MCP-fetch weigert boven 5 MiB.

### 4.4 Dubbels
- Boeken,Tijdschriften & Manuals (renamed) = volledige kopie van Manuals in het origineel (4 submappen, identieke groottes). Weg kan.
- Werfverslagen GPT/Voorbeeld_werfverslag.pdf = vb werfverslag/2110-43-Voorlopige Oplevering.pdf (12.704.998 bytes, zelfde datum).
- Werfverslagen GPT/ALL_Normen en Regelgeving.pdf = Technische Voorlichtingen/merged files/ALL_Normen en Regelgeving.pdf (54.219.051 bytes).
- Werfverslagen GPT/Tech voorlichtingen merges/Tech Voorlichtingen - 1 t/m 9 = merged files/Tech Voorlichtingen - 1 t/m 9 (identieke groottes); nummer 10 bestaat alleen in Werfverslagen GPT.
- Calculatie-meetstaat-bestek/MeetstaatVanGebouwen (21 pdf, 32,9 MB) en Buildwise Documenten/meetstaten van gebouwen (22 pdf, 33,9 MB): dezelfde WTCB-reeks; Buildwise-map is de meest complete.
- Binnen meetstaten: Meetstaat_2_6_7 Systeemvloeren en Vooraf vervaardigd betonwerk (beide 737.796 bytes) en Meetstaat_2_20_21 Sanitaire leidingen en Sanitaire toestellen (beide 1.641.279 bytes) zijn vermoedelijk hetzelfde bestand onder twee namen; niet gelezen, grootte-indicatie.
- TVN_274 Referentiedetails voor.pdf (0,73 MB) en 31000_nl_unprotected_TVN_274 Referentiesdetails voor ETICS met pleisternieuwbouw.pdf (0,73 MB): zelfde TV, twee namen.
- Merge Tech Voorlichting 144.pdf (3,4 MB) naast TVN_144 (2,3 MB): vermoedelijk een samenvoeging, niet gelezen.
- Expert training/schadedossier bouw deel 2 staat twee keer (228.716.380 bytes).
- Vier Schermafbeelding-jpg's (14-10-2025) staan los in de TV-map en horen in Geen download of weg.
- keuring richtlijnen/vademecum-update-2021 versus Wetgeving/Hemelwaterverordening/vademecum-update-2023-oktober-1: geen dubbel maar een oudere versie.

### 4.5 Licentie en gebruik
- Buildwise-TV's, Digests, WTCB-Rapporten en de meetstaat-reeks zijn auteursrechtelijk beschermd. Elke TV vermeldt het expliciet (colofon TV 286 en 288, 295, 297): overnemen of vertalen van de teksten, zelfs gedeeltelijk, is alleen toegelaten met schriftelijk akkoord van de verantwoordelijke uitgever. De bestanden zijn gedownload onder het Buildwise-lidmaatschap of abonnement van het bureau (de prefix "31200_nl_unprotected" en de Buildwise-herdrukomslag wijzen op downloads uit de ledenzone in augustus 2025).
- NBN-normen zijn eveneens betalend en beschermd (NBN/CEN); doorgeven of integraal reproduceren is niet toegestaan.
- VLARIO-documenten, de Hemelwaterverordening (Vlaamse overheid) en de eigen H-A-sjablonen en werfverslagen zijn vrij bruikbaar binnen het bureau; overheidsbesluiten zijn vrij citeerbaar.
- Regel voor de agent: citeren met bron (bv. "volgens TV 283, Buildwise 2022, par. x"), korte parafrase van de eis, nooit paragrafen kopieren of de pdf aan derden (aannemer, bouwheer) doorsturen. Verwijs de aannemer naar het nummer; hij heeft via zijn eigen Buildwise-lidmaatschap toegang.
- De merged files en de ChatGPT-uploadset (Werfverslagen GPT) zijn kopieen voor eigen gebruik; niet verder verspreiden.

## 5. Voorstel bronnenregister (json)

Een bestand `bronnenregister.json` naast de agent, een record per bron. Sleutel = uitgever-afkorting plus nummer. De lijst hieronder is een startset met de gelezen documenten; de niet-gelezen TV's kunnen uit de bestandsnamen worden aangevuld met `jaar: null` en `gelezen: false`.

```json
{
  "versie": "0.1",
  "datum": "2026-10-18",
  "basis": "/Work All/o07. UNIVERSAL/0 H-A Knowledge Base/",
  "namespace": "ns:1802736243",
  "fases": ["afbraak", "ruwbouw", "dak", "buitenschrijnwerk", "gevel", "technieken", "afwerking", "oplevering"],
  "licentieklassen": {
    "buildwise": "auteursrechtelijk beschermd; citeren met bron, niet kopieren of doorsturen",
    "nbn": "betalende norm; citeren met nummer en editie, niet reproduceren",
    "overheid": "vrij citeerbaar",
    "vlario": "sectordocument, intern bruikbaar, bron vermelden",
    "ha": "eigen materiaal H-Architects"
  },
  "bronnen": [
    {
      "sleutel": "TV283",
      "titel": "Plaatsen van buitenschrijnwerk. Deel 1: algemene aspecten",
      "map": "Buildwise Documenten/Technische Voorlichtingen",
      "bestand": "TVN_283 Plaatsen van buitenschrijnwerk  Deel1 algemene aspecten (Vervangt de TV 188).pdf",
      "jaar": 2022,
      "uitgever": "Buildwise",
      "vervangt": ["TV188"],
      "fases": ["buitenschrijnwerk"],
      "werfpunten": ["plaatsing ramen", "waterdichtheid raamaansluiting", "luchtdichtheid raamaansluiting", "bouwknoop raam"],
      "mb": 4.43,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "buildwise",
      "status": "geldig"
    },
    {
      "sleutel": "TV286",
      "titel": "Plaatsen van buitenschrijnwerk. Deel 2: houten ramen in spouwmuurconstructies",
      "map": "Buildwise Documenten/Technische Voorlichtingen",
      "bestand": "TVN_286 Plaatsen van buitenschrijnwerk Deel 2 houten ramen in spouwmuurconstructies.pdf",
      "jaar": 2023,
      "uitgever": "Buildwise",
      "vervangt": [],
      "fases": ["buitenschrijnwerk"],
      "werfpunten": ["plaatsing houten ramen", "plaatsingskader", "raamdook", "dorpel"],
      "mb": 0.37,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "buildwise",
      "status": "geldig"
    },
    {
      "sleutel": "TV280",
      "titel": "Het platte dak (herziening van TV 215)",
      "map": "Buildwise Documenten/Technische Voorlichtingen",
      "bestand": "TVN_280 Het platte dak Herziening van de TV 215.pdf",
      "jaar": null,
      "uitgever": "Buildwise",
      "vervangt": ["TV215"],
      "fases": ["dak"],
      "werfpunten": ["plat dak opbouw", "dakafdichting", "dakisolatie", "dampscherm", "dakopstand"],
      "mb": 7.99,
      "leesbaar_via_mcp": false,
      "gelezen": false,
      "licentie": "buildwise",
      "status": "geldig, lokaal downloaden"
    },
    {
      "sleutel": "TV127",
      "titel": "Toelaatbare maatafwijkingen",
      "map": "Buildwise Documenten/Technische Voorlichtingen",
      "bestand": "TVN_127 Toelaatbare maatafwijkingen.pdf",
      "jaar": 1979,
      "uitgever": "WTCB",
      "vervangt": [],
      "fases": ["ruwbouw", "oplevering"],
      "werfpunten": ["toleranties uitzetting", "toleranties prefabbeton", "toleranties openingen", "toleranties buitenschrijnwerk"],
      "mb": 1.04,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "buildwise",
      "status": "verouderd, alleen bij gebrek aan recentere bron"
    },
    {
      "sleutel": "NBN-B15-001-2024",
      "titel": "Beton. Specificatie, eigenschappen, vervaardiging en conformiteit. Nationale aanvulling bij NBN EN 206",
      "map": "Buildwise Documenten/Normen en regelgeving",
      "bestand": "NBN_B_15-001_2024(N).pdf",
      "jaar": 2024,
      "uitgever": "NBN",
      "vervangt": ["NBN-B15-001-2022"],
      "fases": ["ruwbouw"],
      "werfpunten": ["betonspecificatie", "omgevingsklasse", "betonlevering"],
      "mb": 0.70,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "nbn",
      "status": "geldig vanaf 23-01-2024"
    },
    {
      "sleutel": "VLARIO-OVERZICHT-2022",
      "titel": "Overzichtsdocument keuring privewaterafvoer voor ontwerpers, versie 7",
      "map": "keuring richtlijnen",
      "bestand": "Overzichtsdocument-keuring-privewaterafvoer-voor ontwerpers.pdf",
      "jaar": 2022,
      "uitgever": "VLARIO",
      "vervangt": [],
      "fases": ["technieken", "oplevering"],
      "werfpunten": ["RWA/DWA scheiding", "keuring privewaterafvoer", "afvoer terras", "afvoer oprit", "cv-condens", "groendak afvoer"],
      "mb": 1.14,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "vlario",
      "status": "geldig, verwijst nog naar GSV 2013; combineren met Hemelwaterverordening 2023"
    },
    {
      "sleutel": "BVR-HEMELWATER-2023",
      "titel": "Hemelwaterverordening van 2023 (BVR, in werking 2-10-2023)",
      "map": "Wetgeving/Hemelwaterverordening",
      "bestand": "Hemelwaterverordening.pdf",
      "jaar": 2023,
      "uitgever": "Vlaamse Regering",
      "vervangt": ["GSV-HEMELWATER-2013"],
      "fases": ["ruwbouw", "technieken"],
      "werfpunten": ["hemelwaterput volume", "infiltratievoorziening", "buffervoorziening", "aftappunten"],
      "mb": 0.77,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "overheid",
      "status": "geldig"
    },
    {
      "sleutel": "HA-PV-VO-2019",
      "titel": "Proces-verbaal van voorlopige oplevering (C3A 2019)",
      "map": "BiB_03.Standard_STD",
      "bestand": "PV_voorlopige_oplevering_c3a2019.dotx",
      "jaar": 2019,
      "uitgever": "C3A / H-Architects",
      "vervangt": [],
      "fases": ["oplevering"],
      "werfpunten": ["voorlopige oplevering", "voorbehoud", "inhouding", "borg"],
      "mb": 0.03,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "ha",
      "status": "geldig"
    },
    {
      "sleutel": "HA-WV-2110-33",
      "titel": "Werfverslag 33 project 2110 (stijlvoorbeeld ArchiSnapper)",
      "map": "vb werfverslag",
      "bestand": "2110-33.pdf",
      "jaar": 2023,
      "uitgever": "H-Architects",
      "vervangt": [],
      "fases": ["afwerking"],
      "werfpunten": ["opmaak werfverslag", "rubrieken", "aanwezigen", "slotclausule 5 kalenderdagen"],
      "mb": 0.73,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "ha",
      "status": "stijlvoorbeeld"
    },
    {
      "sleutel": "HA-VC-CHECKLIST",
      "titel": "Checklist werfverslag veiligheid (template, nog niet klaar)",
      "map": "Safety_Veiligheidscoordinatie/VC_Algemeen&Scholing/10_Templates_NOG_NIET_KLAAR",
      "bestand": "Checklist_werfverslag.docx",
      "jaar": 2021,
      "uitgever": "H-Architects",
      "vervangt": [],
      "fases": ["ruwbouw", "dak", "oplevering"],
      "werfpunten": ["PBM", "valgevaar", "stellingen", "hijswerktuigen", "werfinrichting", "postinterventiedossier"],
      "mb": 0.02,
      "leesbaar_via_mcp": true,
      "gelezen": true,
      "licentie": "ha",
      "status": "concept"
    }
  ]
}
```

Aanvulregels voor het register: (1) elke TV in de map krijgt een record, jaar uit de omslag na fetch, anders null; (2) `leesbaar_via_mcp` = grootte onder 5 MiB; (3) `status` kiest uit geldig, vervangen (met opvolger), verouderd, concept, stijlvoorbeeld; (4) bij dubbels een `dubbel_van`-veld met de sleutel van de hoofdkopie; (5) de agent citeert alleen records met status geldig of stijlvoorbeeld en vermeldt bij verouderd dat een nieuwere bron ontbreekt in de kennisbank.

## 6. Voorgestelde volgende stappen
1. De 13 belangrijkste grote TV's (280, 244, 271, 264, 240, 255, 257, 285, 258, 249, 272, 260, 234) via download_link lokaal halen en als tekst naast het register zetten; dat dekt plat dak, metselwerk, luchtdichtheid en ventilatie, nu de grootste gaten.
2. De twee merged .md-bestanden (22 MB samen) lokaal splitsen per TV; dat levert in een keer de tekst van alle TV's 1 t/m 9 zonder 150 losse fetches.
3. Opruimen: map (renamed) verwijderen, Werfverslagen GPT ontdubbelen (alleen nr. 10 bewaren of verplaatsen naar merged files), losse schermafbeeldingen naar Geen download, Meetstaat-dubbels nakijken. Verwijderen alleen na ja van Mehdi.
4. Register aanvullen tot alle 152 TV's en 17 rapporten; de aanvulregels hierboven volgen.
