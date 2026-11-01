# Opdracht driehoeksoverleg: afdeling Bouw, De Aannemerszoeker en De Offertevergelijker (30-10-2026)

Lees alleen; wijzig niets. Nummer je punten zoals het script vraagt (Codex X1, Gemini G1, Claude K1).

## Wat Mehdi vroeg (samengevat uit zijn dictaat van 30-10-2026)

Mehdi wil een nieuwe afdeling **Bouw** op het bord mijnagents.globaal.be (achter Authentik), met agents die op de VM
draaien zoals alle andere.

1. **Een agent die aannemers zoekt.** Twee firma's in ons systeem hebben dat nodig, elk voor zichzelf:
   - **H-Architects** (architectenbureau) zoekt soms firma's die bepaalde werken voor een bouwheer kunnen uitvoeren
     (bijvoorbeeld een dakwerker, een ramenfirma of een stabiliteitsherstelling voor een klantproject).
   - **Harmonie Bouw** (aannemer) zoekt soms onderaannemers voor een deel van de werken.
   Per vraag krijgt de agent een taak, een gebied en de firma. Hij zoekt geschikte firma's en stelt de juiste mail op
   om een prijs of offerte te vragen, vanuit de context van die ene firma.
2. **Een agent die offertes vergelijkt.** Verschillende offertes voor hetzelfde werk naast elkaar leggen.
3. Later mogen er meer agents in Bouw komen. Vandaag: deze twee.

**Harde regel (letterlijk van Mehdi, geldt voor elke tekst die de agents maken):** de twee firma's zijn voor de
buitenwereld volledig gescheiden. In geen enkele mail, verslag, vergelijking of ander stuk mag staan of doorschemeren
dat H-Architects en Harmonie Bouw iets met elkaar te maken hebben: geen woorden als groep, verbonden, zusterbedrijf,
holding, partner, "onafhankelijk van", geen gedeelde afzender, handtekening, adres, telefoonnummer of mailadres, en de
naam van de ene firma komt nooit voor in een stuk van de andere. Een stuk dat deze regel breekt, mag nooit vertrekken.
Elke vraag hoort bij precies één firma; zonder firma geen werk.

## Context die je kunt nakijken (in deze werkmap, tak `bouwagents`, gebouwd op de tak `aankoopagents`)

- De norm voor elke agent: `mijnagents-runner/AGENTNORM.md` (N1 tot N14, hoofdstuk 5 de ronde, hoofdstuk 8 een nieuwe
  agent). Een werkwijze moet de koppen "## Wat ik nooit doe" en "## Wat Mehdi beslist" hebben.
- Het naaste voorbeeld, vandaag gebouwd en door Codex gecontroleerd: De Prijsonderzoeker (afdeling aankoop).
  `mijnagents-runner/prijsonderzoeker.py`, `mijnagents-runner/aankoop/` (onderzoek.py met web_search en web_fetch en
  de grendel "alleen gelezen pagina's", privacy.py, verslag.py), `mijnagents-runner/werkwijze/prijsonderzoeker.md`,
  de koppeling met De Regisseur (`regisseur.py`, RONDE_TOEGELATEN met `vraag`, INHOUD_SOORTEN) en het uitrolscript
  `mijnagents-runner/docs/aankoop/uitrol.sh`. Zijn werkwijze zegt al: "Prijzen van bouwwerken en herstellingen horen
  niet bij mij."
- Dropbox lezen op de VM: `mijnagents-runner/koppelingen/bronnen.py` (team-token van de stack; `projectmap(nummer)`,
  `lijst`, `download`, `pdf_tekst`, `upload`). Alleen lezen is daar de afspraak; `upload` bestaat voor de
  contracten-agent.
- Firma's van de groep: `kern.firma` (code, naam, kbo_nummer, adres_id, code_contact): HARC = H-Architects (HA),
  HARM = Harmoniebouw (HB). Lezen via `mijnagents-runner/koppelingen/organisatie.py`.
- Klanten en leveranciers uit de boekhouding: `kern.partij` (migratie 058, gegroepeerd per btw-nummer, zonder
  vakgebied), zie `DEFINITIEBOEK.md` onder "Partij". Pipedrive per firma via `mijnagents-runner/koppelingen/pipedrive.py`.
- Op het bord bestaat al een lege afdeling `harmoniebouw` ("Bouw en renovatie", geen agents).

## Bronproef (gemeten op 30-10-2026, alleen lezen)

- **H-Architects, offertes per project:** `<project>/…Implementation & Site Control/3. Quotes & Invoices/Offerte/`.
  Twaalf projecten hebben zo'n map. Het rijkste voorbeeld is project 2145: per lot een map `NN Firma - vak`
  (01 ruwbouw en afwerking, 03 ramen, 04 pergola, 06 ventilatie, 07 airco/zonnepanelen/ventilatie, 08 keuken,
  09 vinyl, 11 sanitair, 13 klinkers, 14 arduin, 15 wc-pomp), een submap `00 Niet weerhouden`, een overzicht
  `00 OVERZICHT offertes 2145.xlsx` met vorige versies, en twee vergelijkingen die met de hand gemaakt zijn:
  `2145_Vergelijking ventilatie_MSS en EnergyKing_2026-09-21.pdf` en
  `2145_Vergelijking wc-pomp_Facq en waterpomp.be_2026-10-21.md`. Andere projecten hebben submappen per discipline
  (1. Fire Department, 2. EPB, 3. Stability, 4. Safety Coordination, 5. Doors and Windows, 6. Roof) met losse PDF's.
  Bestandsnamen volgen `<project>_<firma>_<datum>_<onderwerp>.pdf`, met GETEKEND of GEKOZEN in de naam.
- **Project 2405:** een eerder gemaakte vergelijking van twee aannemersoffertes voor een klant (een met de meetstaat
  van het bureau ingevuld, een op basis van plannen; verschil 14,4 procent; een post die bij de ene al in de prijs
  zat en bij de andere als korting stond). Geleerd: bedragen alleen uit offertes, nooit ramingen; zeggen op welke basis
  elke offerte rekende; een korting maakt een post gelijk, niet het verschil kleiner.
- **Harmonie Bouw, onderaannemers:** map `05. ONDERAANNEMER` per vak (afbraak, dakwerken, elektriciteit en sanitair,
  sanitair/ventilatie/verwarming, riolering, metaalconstructies, balustrades, liften, pur en eps, schilderwerken,
  lasbedrijf, grondwerken), vooral oude schermafdrukken uit 2020; een relatielijst `_Relaties Harmonie Bouw V2.xlsx`
  en `04. LEVERANCIERS/Posten en leveranciers.xlsx` (online-only, niet gelezen). Een prijzenboek met 1.866 betaalde
  materiaalprijzen uit eigen facturen staat buiten deze repo. Een eigen mailbox van Harmonie Bouw zit niet in de
  mailkoppeling.
- Er is dus geen gestructureerd register van onderaannemers per vak en per regio. Wat er is, is verspreid.

## Wat het overleg moet beslissen

Geef per punt een concreet advies met reden, en waar het kan een bestand:regel.

1. **Indeling.** Twee aparte agents (De Aannemerszoeker, De Offertevergelijker) in een nieuwe afdeling `bouw`, met de
   firma als verplicht gegeven per vraag? Of een agent per firma? Toets aan de regel uit de skill: een nieuwe agent
   alleen bij een eigen mandaat, een eigen ritme of een eigen toegangsgrens. Wat doen we met de lege afdeling
   `harmoniebouw`? Hoort de vergelijking van een wc-pomp (product) bij De Prijsonderzoeker of bij Bouw?
2. **De Aannemerszoeker: functies.** Wat krijgt hij als vraag (firma, werk of vak, omvang, gemeente of postcode en
   straal, timing, project)? In welke volgorde zoekt hij: eerst firma's waarmee de firma al werkte (kern.partij,
   Pipedrive van die firma, offertemappen van vorige projecten), dan nieuwe via het web? Welke controles doet de code
   (website in deze ronde gelezen, adres in het gebied, ondernemingsnummer actief in de KBO, voor Harmonie Bouw de
   inhoudingsplicht van een onderaannemer)? Wat levert hij per firma op (naam, website, gemeente, contact zoals op de
   site, ondernemingsnummer, specialiteit, waarom, eerder mee gewerkt ja of nee)? Hoe houdt hij een register bij
   zonder een kopie van kern te maken (norm: gedeelde gegevens uit kern, niet dupliceren)?
3. **De mail.** Hoe zorgen we dat de mail de juiste context heeft? Voorstel om te toetsen: de code bouwt de mail uit
   een vast sjabloon per firma (afzender, aanhef, standaardvragen, handtekening uit kern.firma), het model schrijft
   alleen de werkomschrijving uit de vraag; een grendel weigert elke mail met een verboden woord of met de naam, het
   adres, het nummer of het domein van de andere firma. H-Architects vraagt een prijs namens of voor een bouwheer
   (plannen en meetstaat in bijlage, plaatsbezoek mogelijk, termijn); Harmonie Bouw vraagt als aannemer een prijs aan
   een onderaannemer (prijs excl. btw per post, beschikbaarheid, uitvoeringstermijn, verzekering). Wat staat er
   precies in elk sjabloon? Eén mail per firma of één tekst voor allemaal? Waar komt de mail terecht: als tekst in het
   verslag op het bord, of als concept in een postvak (en welk, nu Harmonie Bouw geen postvak in de koppeling heeft)?
   Versturen blijft altijd Mehdi.
4. **De Offertevergelijker: functies.** Wat krijgt hij (project, lot of map, firma, of losse PDF's)? Hoe leest hij een
   offerte (pypdf-tekst, of de PDF als document naar het model voor scans)? Wat haalt hij eruit (posten met
   hoeveelheid, eenheid en prijs, totaal excl. en incl. btw, btw-tarief, wat inbegrepen en uitgesloten is, geldigheid,
   betalingsvoorwaarden, termijn, basis van de offerte: meetstaat of plannen en welke versie)? Wat rekent de code zelf
   (totalen nakijken, btw gelijk trekken, posten die ontbreken als "ontbreekt" en nooit als nul, verschillen per post)?
   Wat levert hij op en waar (verslag op het bord, een Excel of Markdown in de offertemap met versienummer, nooit iets
   overschrijven)? Geeft hij een advies of alleen een vergelijking? Hoe blijft hij neutraal als een van de offertes van
   Harmonie Bouw komt in een vergelijking voor een klant van H-Architects?
5. **Grenzen en gegevens.** Wat doen ze nooit (versturen, een aannemer contacteren, een offerte aanvaarden of
   tekenen, een bestaand bestand overschrijven of verplaatsen)? Wat beslist Mehdi altijd? Welke gegevens mogen naar de
   AI: bij het zoeken alleen vak en gemeente, nooit de naam of het adres van de bouwheer; bij het vergelijken leest het
   model de offerte zelf (daar staan namen in). Is dat aanvaardbaar, of een `GRENS:`?
6. **Tests vooraf.** Goede en foute voorbeelden die tests worden. Bijvoorbeeld: een mail van Harmonie Bouw met
   "H-Architects", "architect" als afzender of het domein h-architects.be wordt geweigerd; een mail van H-Architects
   die Harmonie Bouw voorstelt of noemt wordt geweigerd; een firma waarvan de website niet gelezen is komt niet in de
   lijst; een firma buiten het gebied staat apart; een post die in een offerte ontbreekt telt niet als nul; een
   offerte excl. btw en een incl. btw worden op dezelfde voet gezet; de vergelijking ventilatie 2145 (MSS tegen
   EnergyKing) als goed voorbeeld van de uitkomst.
7. **Volgorde.** Wat bouwen we vandaag, wat later (register van onderaannemers per vak en regio, inhoudingsplicht,
   concept in een postvak, opvolging van gevraagde offertes)? Wat is de eerste ronde die bewijst dat het werkt?

## Grenzen voor dit overleg

- Niemand verstuurt, contacteert of tekent iets in dit overleg. Het gaat over het ontwerp.
- Een keuze die geld uitgeeft of een account aanmaakt, is een `GRENS:` voor Mehdi (bijvoorbeeld een betaalde
  bedrijvengids-API). Zet die als eigen regel `GRENS: ...` met je advies.
- Hou het praktisch: de eerste versie moet vandaag te bouwen zijn met wat er al is, op de manier van De
  Prijsonderzoeker.
