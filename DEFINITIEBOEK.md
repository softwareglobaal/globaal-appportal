# Definitieboek - softwareglobaal / H-groep

> **Status: LEIDEND** (bekrachtigd in de Zoom-meetings van 2026-07-02). Doel: **één
> term per begrip, overal identiek**, zodat een wijziging op één plek overal klopt en
> niks dubbel of dubbelzinnig is.
>
> **Machinebron: `kern.definitie`** (migratie 015). De dashboards lezen term +
> definitie daaruit - kolomkoppen, ⓘ-tooltips, de Woordenboek-knop en de
> Excel-export. **Een term wijzigen = één `UPDATE` op die tabel**, en overal is hij
> juist. Dit document is de leesbare uitwerking; houd beide in sync (sleutels in
> `kern.definitie` zijn stabiel en hernoem je nooit - alleen `term`/`definitie`).

## Kernprincipes
1. **Uniek** - één begrip = één term. Geen synoniemen (bv. "sales" ≠ "sales team" ≠
   "afdeling sales" - kies er één).
2. **Centraal** - elk begrip heeft één bronlijst (firma's, afdelingen, medewerkers);
   apps **verwijzen** ernaar, kopiëren niet.
3. **Gelinkt** - namen zijn verwijzingen naar die bron, nooit losse vrije tekst.

## De termen

### Discipline
Een **vast bedrijfsdomein** uit het 17-disciplines-raamwerk (Unified Dashboard,
Mehdi 2026-07-04). Niet de firma's zijn de vaste structuur, maar deze 17
disciplines die elke servicefirma nodig heeft - een firma zonder invulling laat
de discipline leeg, maar het raamwerk verandert nooit (ziekenhuis-model: je
ziet meteen wat ontbreekt).
- **Bij ons:** de 17 rijen in `kern.discipline` (migratie 030), volgorde 1-17:
  HR & rekrutering, Sales & business development, Marketing & communicatie,
  Finance & accounting, Operations & projectmanagement, Legal & compliance,
  Customer service & support, IT & systemen, Procurement & vendor management,
  Quality assurance, Risk management, Strategische planning, Data & analytics,
  Facilities & administratie, Research & development, Supply chain management,
  Partnerships & vendor relations. Elke discipline heeft zijn eigen definitie
  in `kern.definitie` (zelfde sleutel).
- Tools/software worden aan een discipline gekoppeld (tool→discipline-mapping,
  PLAN.md stap 2) - zo worden dubbele software en gaten zichtbaar.


### Firma
De **juridische entiteit** (rechtspersoon) die contracten sluit, factureert en een
BTW-/ondernemingsnummer heeft. In grotere organisaties heet dit een *legal entity* - de
eenheid met eigen boekhouding en juridische scheiding.
- **Bij ons:** de 13 firma's in `kern.firma` (H-Architects, Contrax, UnaBo …).
- *Niet* verwarren met afdeling of team.

### Afdeling
Een **organisatorische eenheid** die medewerkers groepeert per functiegebied - de laagste
structuurlaag (*department / organizational unit*).
- **Bij ons:** Scanning, Energie, Sales … (`kern.afdeling`, momenteel 13). Mag de
  firma-grens overschrijden (mensen uit meerdere firma's in één afdeling).
- Een afdeling heeft één **hoofdverantwoordelijke**.

### Team
In de organisatietheorie is een team een groep met een **gedeelde verantwoordelijkheid of
doel** - géén laag in de hiërarchie. Juist daarom veroorzaakt "team" verwarring.
- **Afspraak:** gebruik **"team" niet** als structuurbegrip. Wat bedoeld wordt is meestal
  een **afdeling** (structuur) óf de **gebruikers** van een resource (bv. "wie werkt op het
  contractnummer"). Kies dat, niet "team".

### Functie
De **taken/verantwoordelijkheden** van een persoon, intern (*job function*). Verschilt van
een *jobtitel* (externe benaming) en van *rol* (zie onder).
- ⚠️ **Dubbelzinnigheid:** in het telefoonregister betekent "functie" iets anders - het
  **doel van het nummer** ("algemeen nummer", "technisch nummer"). Dat is geen
  persoons-functie. → hernoem dat veld naar **"doel"** of **"omschrijving"** om de botsing
  weg te nemen.

### Rol
De **positie/verantwoordelijkheidslaag** van een persoon in de organisatie, breder dan één
taak (*job role*).
- **Bij ons:** Lid / Hoofd / Partner / Management (`kern.persoon.rol`) - bepaalt
  rechten en zichtbaarheid.

### Werkgever
De **firma waar een persoon in dienst is** (ingeschreven).
- **Bij ons:** `persoon.werkgever_firma_id` (uniselect - één werkgever).

### Diensten-voor
De firma('s) waarvoor een persoon **werkt / diensten verricht**, los van waar hij in dienst
is.
- **Bij ons:** multiselect (iemand kan voor meerdere firma's werken).

### Leverancier
De **externe partij die je een dienst/product levert en die je betaalt** (*supplier/vendor*):
upstream, levert aan jou; jij factureert niet aan hen.
- **Bij ons:** bv. Close Call BV, Mega, Proximus. Klikbaar → alle nummers/kosten van
  die leverancier. Let op: op de factuur staat vaak een andere naam dan het platform
  (Close Call BV factureert, Xelion is het platform).
- Gebruik **"leverancier"** consistent - niet afwisselend "provider"/"platform" voor
  hetzelfde.

### Platform
De **software of dienst waarop iets draait** (bv. Xelion, Zoom). De leverancier
factureert; het platform is wat je gebruikt - twee verschillende dingen die elk hun
eigen veld hebben.

### Gebruiker
De **persoon/personen die een resource gebruiken** (telefoonnummer, softwarelicentie).
- **Bij ons:** link(s) naar `kern.persoon` (multi).

### Verantwoordelijke
De **ene persoon die aanspreekbaar en eigenaar is** van een resource
(accountable) - precies een, zodat niets eigenaarloos blijft. Generiek begrip:
wat de verantwoordelijkheid concreet inhoudt verschilt per resource.

### Verantwoordelijke voor het nummer
De verantwoordelijke van een **telefoonnummer**: aanspreekbaar en eigenaar,
precies een. In de telefonie is dit **altijd de 1e in de belvolgorde**. Eigen
term (migraties 036/037) zodat de algemene term "verantwoordelijke" overal dezelfde
generieke betekenis houdt.


### Backup
De **2e persoon in de belvolgorde** - neemt over als de verantwoordelijke niet kan.

### Extern contact
Een **externe partij** (klant, leverancier of andere beller) waarmee via een van
onze telefoonnummers contact is geweest, afgeleid uit het **Xelion-oproeparchief**
van de laatste 90 dagen. Zelfde partij met meerdere nummernotaties telt als een
contact (kanonieke nummervorm); anonieme bellers staan er niet in.
- **Bij ons:** `extern_nummer`/`extern_naam` op `communicatie.xelion_communicatie`
  (migratie 041) + eigen laag in de Second Brain (migratie 042, standaard uit).
- **Toekomst:** zodra de klantendatabase bestaat wordt het kanonieke nummer het
  koppelvlak naar de klant - dan wordt een extern contact een gelinkte klant in
  plaats van een los nummer.

### Intern gefactureerd aan
De firma van de groep **die de factuur van de leverancier ontvangt en betaalt** (in de
praktijk UnaBo). "Intern" staat er bewust: zonder dat woord kan het ook over externe
facturatie aan klanten lijken te gaan, en die houden we hier niet bij (meeting
2026-07-02 - verving de oude term "gefactureerd aan").

### Kosten aanrekenen aan
De firma van de groep **aan wie de kosten intern worden aangerekend** - kan verschillen
van wie de leveranciersfactuur ontvangt en betaalt. **Leeg wanneer de betalende firma
de kosten zelf draagt**: aan jezelf reken je niets aan. Verving "Interne doorfacturatie
naar" (meeting 2026-07-06): er wordt niets echt gefactureerd. Sleutel blijft
`doorfactureren_naar`.

### Gebruikt voor
Waarvoor de resource **feitelijk gebruikt wordt**, gekozen uit een **vaste
keuzelijst** (migratie 046; beheer in `communicatie.lijst`, categorie "Gebruikt
voor"): Contrax, Tekenwerk, Energie-efficiënt, de sales-campagnes, klanten
(Verbraeken en Co, Yannick Technics) en personen met een privé-nummer
(Cataline). **Alleen invullen wanneer dat afwijkt van wie betaalt**: aan jezelf
hoef je niets uit te leggen (meeting 2026-07-06, het "Shaniel is de voornaam
van Shaniel"-argument). Zodra de klantendatabase bestaat worden klanten hier
echte verwijzingen.

### Kostprijs
De **kostprijs van het abonnement in euro exclusief BTW**, overgenomen van de laatste
factuur van de leverancier. Niet "vast": elke prijs kan veranderen (meeting
2026-07-06, verving "Vaste prijs"; sleutel blijft `vaste_prijs`). Maandbedrag of
tarief per minuut: zie het prijstype. Leeg = onbekend. Kortingen en acties staan
alleen op de factuur; **de factuur blijft de bron** (de Xelion-API heeft geen
kosteninformatie, bewezen 2026-07-06).

### Prijstype
Of de kostprijs een **maandbedrag** is of een **tarief per minuut**. Alleen
maandbedragen tellen mee in maandtotalen.

### Prijs bijgewerkt op
De **datum van de laatste factuur** waarvan de kostprijs is overgenomen. Ouder dan
**2 maanden** geeft een waarschuwing in het register: mogelijk is er een factuur
gemist of is er iets veranderd.

### Verbruik
De **variabele kosten** van een resource (belminuten, data, gebruik) - apart van de
vaste prijs. Nodig om houden-of-schrappen **datagedreven** te beslissen.

### Facturatiecyclus
**Hoe vaak er gefactureerd wordt**: wekelijks, maandelijks, per kwartaal of jaarlijks -
kan per software/platform verschillen. Afspraak (meeting 2026-07-02): jaarcontract
voor zekere zaken (bv. Zoom), maandelijks voor onzekere; de keuze wordt datagedreven
op basis van verbruik.

### Finalisatie
Het **kwaliteitsstempel op data**: een collega heeft de knoop (nummer, persoon,
firma, …) gecontroleerd en goedgekeurd. Vastgelegd met **wie + wanneer**,
**append-only** - terugdraaien is een nieuwe registratie, historie telt (rollen
wijzigen). In de Second Brain: **blauw = gefinaliseerd, rood = nog niet**. Géén slot:
gefinaliseerde data blijft gewoon bewerkbaar.

### KBO-nummer
Het **ondernemingsnummer** van een firma in de Kruispuntbank van Ondernemingen -
de sleutel naar officiële bronnen (KBO Public Search, NBB-jaarrekeningen). Staat op
`kern.firma`; invullen via het firma-beheer in het Organisatie-dashboard.

### Draaiboek
Het **protocol (playbook) van één proces**: alle fases en deeltaken van A tot Z, in
volgorde en zonder fouten (meeting 2026-07-03, Mehdi). Een draaiboek legt het proces
vast → maakt **automatisering** mogelijk → levert **data** op. Het micromanagement
(bv. een EPB-proces met ~200 stappen) hoort hiér, niet in projectmanagement.

### Projectmanagement
**Veel projecten tegelijk op grove lijnen bewaken** (bv. Monday). Werkt pas als elk
project een draaiboek volgt - "projectmanagement zonder draaiboek heeft geen zin".
Monday blijft voor het overzicht; het draaiboek is van ons.

### Fase
Een **hoofdstuk van een draaiboek**: een geordende groep stappen (ontwerpfase,
uitvoeringsfase, …). Maakt de voortgang van een run in één blik leesbaar.

### Stap
De **kleinste eenheid van een draaiboek**: één (deel)taak, met volgorde, eventueel
een afhankelijkheid ("pas na stap X") en een op te leveren resultaat (bv. een
verslag).

### Run
Een **draaiboek toegepast op één concreet dossier/project**: dezelfde stappen, mét
status, wie en wanneer per stap. De run is het *sequentiële geheugen* - "verslag 2
is klaar, dus nu verslag 3" - en daarmee de projectvoortgang-bron die AI nu mist.

## Vermijden / opletten
| Niet doen | Wel |
|---|---|
| "team" als structuur | *afdeling* (structuur) of *gebruikers* (van een resource) |
| "functie" voor een nummer | *doel* / *omschrijving* |
| "provider" / "platform" door elkaar | *leverancier* |
| losse vrije-tekst namen | een **link** naar de centrale lijst |

---
*Grondslag: standaard org-design- en HR-terminologie (legal entity / department / team;
job function / role / title) en inkoop-terminologie (supplier / vendor / provider).
Bekrachtigd op de Zoom-meetings van 2026-07-02 en sindsdien **leidend**; de
machineleesbare bron is `kern.definitie` (migratie 015).*
