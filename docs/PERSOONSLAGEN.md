# Persoonslagen: welke gegevens, welke laag, welke rol

> Status: **voorstel ter review** (Shaniel, 2026-07-20) naar aanleiding van de
> meeting met Mehdi en Ishara. Punt 4 uit die lijst (bron van waarheid per
> gegeven) komt later; eerst moet vastliggen welke gegevens we willen.

## Uitgangspunten

1. **Alle gegevens in `kern`.** Het HR-schema leidt af van kern, niet andersom.
   Zo blijft de persoon voor elke discipline koppelbaar en is niemand nodig om
   handmatig links te leggen.
2. **Wie het profiel ziet, ziet niet automatisch alles.** Salaris is alleen
   voor HR en management.
3. **Toegang per rol, niet per naam.** Wisselt iemand van functie, dan wisselt
   de toegang mee zonder dat er iets omgezet hoeft te worden.
4. **De database bewaakt de laag, niet alleen het scherm.** Dit is geen
   theorie: op dit moment kunnen zes app-rollen (`portal`, `communicatie`,
   `kosten`, `draaiboek`, `vermogen`, `hr_app`) `kern.persoon` lezen. Zet je
   salaris in die tabel, dan kan het communicatie-dashboard er in principe bij.
   Elke gevoelige laag krijgt daarom een **eigen tabel met eigen grants**.

Twee sloten dus, en ze doen verschillend werk: de **grants** bepalen welke
*applicatie* een laag mag lezen, de **rolcontrole in de app** bepaalt welke
*mens*. Geen van beide is alleen voldoende.

## De lagen

### Laag 0 - Publiek: de koppelbare kern

Doel: iedereen kan naar een persoon verwijzen en zien wie het is, zonder ook
maar iets gevoeligs te zien. Dit is Mehdi's eis dat "Abby uit de HR-map moet".

| Gegeven | Nu aanwezig |
|---|---|
| weergavenaam, voornaam, achternaam | ja (`kern.persoon`) |
| functie en rol | ja |
| afdeling, werkgever-firma, diensten-voor | ja |
| in dienst ja/nee | ja |
| zakelijk e-mailadres | ja |
| zakelijke telefoonnummers | ja, via `communicatie` |
| tools en accounts | ja, via `kosten.seat` |
| **officiële foto** | **nee, nieuw** |

Tabel: `kern.persoon` (bestaat) plus `kern.persoon_foto` (nieuw).
Leesbaar door: alle app-rollen. Dit is bewust de breedste laag.

### Laag 1 - HR

| Gegeven | Opmerking |
|---|---|
| hr-nummer | staat nu in `kern.persoon`, verhuist niet (niet gevoelig genoeg) |
| geboortedatum | nieuw |
| privé-adres, privé-telefoon, privé-e-mail | nieuw |
| contracttype en contracturen per week | nieuw; het HR-dashboard schat ze nu uit het rooster |
| rooster (begin- en eindtijd, flex) | nu in `hr.medewerker`; kern wordt de bron |
| datum in en uit dienst | staat al in `kern.persoon` |
| verlofrecht en verlofsaldo | nieuw; dit is de meestgestelde vraag aan Ishara |
| ziektedagen | nieuw |
| gespreks- en dossieraantekeningen | nieuw, later |

Tabel: `kern.persoon_hr` (nieuw).
Leesbaar door: `portal` en `hr_app`. **Niet** door communicatie, kosten,
draaiboek of vermogen.

### Laag 2 - Beloning

De zwaarste laag. Alleen HR en management, plus de medewerker zelf.

| Gegeven | Opmerking |
|---|---|
| brutoloon en betaalritme | |
| dertiende maand, toelagen | |
| betaald / niet betaald per periode | Mehdi noemde dit expliciet |
| ingangsdatum van de huidige beloning | historie bewaren, niet overschrijven |
| rekeningnummer | **voorstel: niet opnemen**, hoort bij de loonadministratie |

Tabel: `kern.persoon_beloning` (nieuw), met historie per regel.
Leesbaar door: alleen `portal`. Zelfs het HR-dashboard krijgt geen leesrecht
tot er een aantoonbare behoefte is.

Harde regels voor deze laag:
- **nooit in de graaf** (Second Brain) en **nooit in een AI-laag** (briefing,
  duiding, agenten), zelfde lijn als `communicatie.geheim`;
- **elke inzage wordt gelogd** met gebruiker en tijdstip;
- geen export, geen API die bedragen teruggeeft.

### Laag 3 - De eigen laag

De medewerker ziet zijn eigen laag 1 en 2: sinds wanneer hij in dienst is, zijn
verlofsaldo, zijn ziektedagen, zijn salaris en of het betaald is. Dit is geen
aparte tabel maar een **regel**: `persoon_id = de ingelogde gebruiker`.

Dit is ook de sleutel tot Mehdi's punt over de hoeveelheid herhaalvragen: wie
zijn eigen verlofsaldo kan zien, belt daar niet meer voor.

### Laag 4 - Afdelingshoofd

Ziet laag 0 van iedereen, plus **geaggregeerde** cijfers over het eigen team
(aanwezigheid, verlof, verzuim). Bewust geen individuele salarissen: voor
loonkosten per team volstaat een totaal.

## Rolmatrix

| Rol | Laag 0 publiek | Laag 1 HR | Laag 2 beloning | Team-aggregaten |
|---|---|---|---|---|
| elke ingelogde medewerker | ja | nee | nee | nee |
| zichzelf | ja | eigen gegevens | eigen gegevens | nee |
| `afdelingshoofd` (nieuw) | ja | eigen team | nee | eigen team |
| `hr` | ja | ja | ja | ja |
| `manager` | ja | ja | ja | ja |
| `admin` | ja | ja | ja | ja |

Toelichting bij twee keuzes:
- **`manager` ziet salaris** omdat Mehdi dat zo aangaf. Let op: `manager` is nu
  een brede groep die ook allerlei andere toegang geeft. Als salaris erin komt,
  moet die groep bewust klein blijven.
- **`afdelingshoofd` bestaat nog niet** als groep. Die is nodig zodra
  teamverantwoordelijken hun eigen mensen moeten kunnen inzien.

## Wat dit betekent voor het HR-dashboard

Het HR-dashboard (DeskTime) blijft afleiden uit kern in plaats van eigen
waarheden aan te leggen: het rooster en de contracturen verhuizen naar
`kern.persoon_hr`, en `hr.medewerker` houdt alleen nog de DeskTime-koppeling.
Zo staat het rooster op één plek in plaats van in een PowerShell-array, een
databasetabel en een dashboard tegelijk.

## Nog te beslissen

- Welke gegevens ontbreken in deze inventaris? (dit is de vraag aan Ishara)
- Nemen we rekeningnummers op, of blijft dat bij de loonadministratie?
- Wie worden de afdelingshoofden, en per welke afdeling?
- Punt 4: wat wordt de bron van waarheid per gegeven, nu er meerdere bronnen
  zijn (DeskTime, loonadministratie, het register zelf)?
