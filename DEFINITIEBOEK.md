# Definitieboek — softwareglobaal / H-groep

> **Status: DRAFT** — werkdocument, nog niet leidend. Bedoeld om op een Zoom af te
> stemmen en dan vast te leggen. Doel: **één term per begrip, overal identiek**, zodat
> een wijziging op één plek overal klopt en niks dubbel of dubbelzinnig is.

## Kernprincipes
1. **Uniek** — één begrip = één term. Geen synoniemen (bv. "sales" ≠ "sales team" ≠
   "afdeling sales" — kies er één).
2. **Centraal** — elk begrip heeft één bronlijst (firma's, afdelingen, medewerkers);
   apps **verwijzen** ernaar, kopiëren niet.
3. **Gelinkt** — namen zijn verwijzingen naar die bron, nooit losse vrije tekst.

## De termen

### Firma
De **juridische entiteit** (rechtspersoon) die contracten sluit, factureert en een
BTW-/ondernemingsnummer heeft. In grotere organisaties heet dit een *legal entity* — de
eenheid met eigen boekhouding en juridische scheiding.
- **Bij ons:** de 13 firma's in `kern.firma` (H-Architects, Contrax, UnaBo …).
- *Niet* verwarren met afdeling of team.

### Afdeling
Een **organisatorische eenheid** die medewerkers groepeert per functiegebied — de laagste
structuurlaag (*department / organizational unit*).
- **Bij ons:** Scanning, Energie, Sales … (`kern.afdeling`, momenteel 13). Mag de
  firma-grens overschrijden (mensen uit meerdere firma's in één afdeling).
- Een afdeling heeft één **hoofdverantwoordelijke**.

### Team
In de organisatietheorie is een team een groep met een **gedeelde verantwoordelijkheid of
doel** — géén laag in de hiërarchie. Juist daarom veroorzaakt "team" verwarring.
- **Afspraak:** gebruik **"team" niet** als structuurbegrip. Wat bedoeld wordt is meestal
  een **afdeling** (structuur) óf de **gebruikers** van een resource (bv. "wie werkt op het
  contractnummer"). Kies dat, niet "team".

### Functie
De **taken/verantwoordelijkheden** van een persoon, intern (*job function*). Verschilt van
een *jobtitel* (externe benaming) en van *rol* (zie onder).
- ⚠️ **Dubbelzinnigheid:** in het telefoonregister betekent "functie" iets anders — het
  **doel van het nummer** ("algemeen nummer", "technisch nummer"). Dat is geen
  persoons-functie. → hernoem dat veld naar **"doel"** of **"omschrijving"** om de botsing
  weg te nemen.

### Rol
De **positie/verantwoordelijkheidslaag** van een persoon in de organisatie, breder dan één
taak (*job role*).
- **Bij ons:** Lid / Hoofd / Partner / Management (`kern.persoon.rol`) — bepaalt
  rechten en zichtbaarheid.

### Werkgever
De **firma waar een persoon in dienst is** (ingeschreven).
- **Bij ons:** `persoon.werkgever_firma_id` (uniselect — één werkgever).

### Diensten-voor
De firma('s) waarvoor een persoon **werkt / diensten verricht**, los van waar hij in dienst
is.
- **Bij ons:** multiselect (iemand kan voor meerdere firma's werken).

### Leverancier
De **externe partij die je een dienst/product levert en die je betaalt** (*supplier/vendor*):
upstream, levert aan jou; jij factureert niet aan hen.
- **Bij ons:** bv. Proximus (abonnementen), Excellion (platform). Klikbaar → alle
  nummers/kosten van die leverancier.
- Gebruik **"leverancier"** consistent — niet afwisselend "provider"/"platform" voor
  hetzelfde.

### Gebruiker
De **persoon/personen die een resource gebruiken** (telefoonnummer, softwarelicentie).
- **Bij ons:** link(s) naar `kern.persoon` (multi).

### Verantwoordelijke
De **ene persoon die aanspreekbaar/eigenaar is** voor een resource — *accountable* (RACI).
Precies één, zodat niks "open" (eigenaarloos) blijft.
- **Bij ons:** link naar `kern.persoon`.

### Facturatie-firma (factuur)
De firma **aan wie een resource gefactureerd wordt** (wie de rekening betaalt).

### Doorfacturatie-firma (doorfactuur)
De firma **aan wie de kost wordt doorgerekend** — kan verschillen van wie de factuur
ontvangt.

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
Dit is een **draft** — aanpassen op de Zoom, dan vastleggen en pas daarna leidend maken.*
