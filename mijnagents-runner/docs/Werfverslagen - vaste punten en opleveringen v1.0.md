# Werfverslagen: vaste punten, fasepunten en de twee opleveringen (v1.0, 15-09-2026)

Bron: analyse van 33 verslagen uit Archisnapper (H-Architects bvba/Apps/Archisnapper, 1094 verslagen 2019-2025) op
15-09-2026; volledige analyse met bronvermelding per verslagnummer in `archisnapper-analyse.md` (repo appportal,
mijnagents-runner/docs). Code: `mijnagents-runner/sjabloon_werfverslag.py` (VASTE_PUNTEN, FASE_PUNTEN) en
`mijnagents-runner/sjabloon_oplevering.py` (twee proces-verbalen). Verandert een tekst, dan eerst hier, dan in de code.

## 1. Vaste punten: in elk werfverslag tot ze OK zijn

Genummerd 1.1 t/m 1.11 in verslag 1, in elk volgend verslag herhaald met de oorspronkelijke datum, tot de
sluitvoorwaarde vervuld is (dan nog één keer als OK, daarna weg). Tweetalig NL/EN volgens de keuze taal.

| Nr | Titel | Categorie | Verantwoordelijke | OK wanneer | Hoe vaak in de oude verslagen |
|---|---|---|---|---|---|
| 1.1 | Start- en einddatum van de werken (omgevingsloket) | Algemeen | bouwheer | startdatum gemeld; einddatum bij de oplevering | 13 van 31 |
| 1.2 | Werfbezoeken | Algemeen | bouwheer, aannemer | blijft staan (disclaimer) | 8 van 31 |
| 1.3 | Orde en netheid | Algemeen | alle aannemers | blijft staan; vuile werf = gedateerd NOK-punt | 8 van 31 |
| 1.4 | Facturatie | Algemeen | bouwheer | tot de eindafrekening van de erelonen | 4 van 31 |
| 1.5 | Veiligheidscoördinatie en VGP | Veiligheidscoördinatie | bouwheer (aanstelling), hoofdaannemer | coördinator aangesteld, getekend VGP op de werf | 21 van 31 (kopblok) |
| 1.6 | Verzekeringsattesten BA10 en BBR | Algemeen | bouwheer vraagt op, aannemers leveren | per aannemer zodra het attest in het dossier zit | 21 van 31 (kopblok) |
| 1.7 | Stabiliteitsplannen | Ruwbouw | aannemer, ingenieur | tot de ruwbouw wind- en waterdicht is | 6 van 31 |
| 1.8 | EPB-eisen | EPB | aannemer (stukken), bouwheer (foto's, eindverklaring) | tot de EPB-eindverklaring is ingediend | 9 van 31 |
| 1.9 | Uitvoering volgens de vergunde plannen | Algemeen | bouwheer | blijft staan; elke afwijking = gedateerd NOK-punt | 7 van 31 |
| 1.10 | Plaatsbeschrijving | Algemeen | bouwheer | zodra ze in het dossier zit | 1 van 31 |
| 1.11 | Actuele plannen op de werf | Algemeen | aannemer | blijft staan | 1 van 31 |

Vaste kop boven de waarnemingen: veiligheid (VGP) en tienjarige aansprakelijkheid (Peeters-Borsus). Vaste slotzin
(28 van 31 verslagen): zonder tegenbericht per e-mail binnen de vijf kalenderdagen wordt aangenomen dat alle partijen
akkoord gaan met dit verslag.

## 2. Fasepunten: in het eerste verslag van de fase, tot OK

Afbraak (sloopplannen, bescherming buur en openbaar domein, asbest, stutwerk, dak afdekken, plaatsbeschrijving),
ruwbouw (stabiliteitsplannen en wapeningsfoto's, fundering, staal, riolering RWA/DWA zichtbaar vóór beton,
scheidingsmuren, stelling, binnenhoogte 2,60 m, brandveiligheid meergezins), dak (opbouw, groendak, isolatie tegen
EPB, dakramen), buitenschrijnwerk en gevel (ramen, Uw-rapport, infiltratie, gevel conform vergunning, balustrades),
technieken (elektriciteit met keuring, sanitair, verwarming, ventilatie volgens EPB, airco, vloerisolatie), afwerking
(pleister en schilder, deuren en plinten, keuken en maatwerk, trapleuningen, badkamer, keuzes van de bouwheer),
oplevering (restpuntenlijst met deadline en vergunningstermijn, einddatum omgevingsloket, EPB-eindverklaring,
verharding, foto's van gevels en niveaus, opvolging restpunten, definitieve oplevering). Volledige lijst in de code.

## 3. Proces-verbaal van voorlopige oplevering

Negen echte PV's in Archisnapper (2021-2025), in twee vormen: een apart PV-sjabloon met handtekeningblok (2021-2022)
en een gewoon werfverslag met de PV-alinea in "Status werf" (2023-2025). Het sjabloon neemt het beste van beide:

1. Kop: projectnummer, titel, nummer `<nr>-VO`, project, omschrijving, bouwheer, hoofdaannemer, datum rondgang.
2. Voorwerp en aanvaarding (vaste tekst): aanvaard onder voorbehoud van de genummerde en geparafeerde opmerkingen
   met einddatum; de datum van het PV is de datum van voorlopige oplevering, start van waarborg en tienjarige
   aansprakelijkheid; geen aanvaarding van verborgen gebreken; documenten en attesten tegen de einddatum;
   opmerkingen schriftelijk binnen 8 werkdagen.
3. Contactpersonen en aanwezigen, met kolom "ontvangt PV".
4. Wettelijke verplichtingen: veiligheid, verzekeringsattesten BA10 en BBR, omgevingsloket, EPB.
5. Uitvoering volgens de vergunde plannen (ja of nee, lijst afwijkingen op verantwoordelijkheid van de bouwheer).
6. Gebreken en onafgewerkte werken: nr VO.n, ruimte of onderdeel, omschrijving, foto, verantwoordelijke aannemer,
   hersteltermijn, vlag.
7. Documenten en attesten (as-built, keuringen, EPB-stukken, BA10/BBR, onderhoud, sleutels, meterstanden).
8. Financieel: eindafrekening, inhouding of borg, erelonen.
9. Foto's van gevels en elk niveau op de dag van de oplevering.
10. Handtekeningen: architect ter kennisname, aannemer en bouwheer voor akkoord; weigering met reden.

## 4. Proces-verbaal van definitieve oplevering

In Archisnapper nooit als apart verslag gemaakt: de voorlopige ging "automatisch over". Het sjabloon bevat:
kop met verwijzing naar het PV van voorlopige oplevering; voorwerp en aanvaarding (zonder of onder voorbehoud;
einde waarborgtermijn; tienjarige aansprakelijkheid loopt door tot VO + 10 jaar; einde van de opdracht
werfopvolging); aanwezigen; wettelijke verplichtingen; opvolging van elk VO-punt (uitgevoerd op, niet uitgevoerd,
anders opgelost); nieuwe vaststellingen sinds de voorlopige oplevering (waarborg aannemer of gebruik bouwheer);
administratieve afsluiting (EPB-eindverklaring, omgevingsloket, as-built, keuringen, postinterventiedossier, laatste
factuur en borg); foto's; handtekeningen; bijlage kopie PV voorlopige oplevering.

## 5. Beslissingen voor Mehdi

- **Overgang**: automatisch (huidige praktijk: "gaat automatisch over naar een definitieve oplevering op <datum>")
  of tweede rondgang met apart PV (voorstel, juridisch veiliger: de definitieve oplevering dekt de gebreken die
  na ingebruikname blijken). Keuze per dossier op de bezoekpagina (`overgang`), standaard tweede rondgang.
- **Waarborgtermijn**: standaard 12 maanden; per dossier aanpasbaar (`waarborg`).
- Drie oude PV's waren te groot om te lezen (2463-1, 2359-6, 2197-16); vermoedelijk ook voorlopige opleveringen.
