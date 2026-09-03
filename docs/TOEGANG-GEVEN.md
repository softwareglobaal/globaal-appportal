# Toegang geven aan een gebruiker, zonder Claude Code

Alles wat hieronder staat doe je in de Authentik-beheerpagina:
**https://auth.globaal.be/if/admin/** (inloggen als `akadmin` of een ander account
met beheerrechten).

## Het model in een zin

Je geeft nooit "een app" aan een persoon. **Toegang is lidmaatschap van een groep**,
en elke app luistert naar een of meer groepen. Iemand toegang geven is dus: de juiste
groep erbij zetten.

## 1. Bestaat de gebruiker al?

`Directory` > `Users`, zoek op de voornaam. De conventie hier is de **voornaam in
kleine letters** als gebruikersnaam (`angela`, `raisha`, `marise`).

## 2. Nieuwe gebruiker aanmaken

`Directory` > `Users` > `Create`.

| Veld | Wat erin hoort |
|---|---|
| Username | voornaam, kleine letters |
| Name | voornaam met hoofdletter, eventueel met afdeling: `Ishara (HR)` |
| Email | mag leeg, maar **zonder e-mail kun je geen herstellink sturen** |
| Type | `Internal` |

Een nieuwe gebruiker heeft nog geen wachtwoord en kan dus niet inloggen. Twee wegen:

- **Zij stelt het zelf in**: vul een e-mailadres in en gebruik bij de gebruiker de knop
  onder de drie puntjes om een herstellink te sturen. Voorkeur, want dan kent niemand
  anders haar wachtwoord.
- **Jij stelt het in**: bij de gebruiker `Set password`. Doe dit alleen als een
  e-mailadres ontbreekt, en laat haar het daarna zelf wijzigen.

## 3. In de juiste groep zetten

Twee wegen, ze doen hetzelfde:

- `Directory` > `Groups` > klik de groep > tabblad `Users` > `Add existing user`.
- `Directory` > `Users` > klik de gebruiker > tabblad `Groups`.

## Welke groep hoort bij welke app

| App (adres) | Groep die toegang geeft |
|---|---|
| agenda | `agenda-bekijken` |
| agents | `agents` (of admin/manager) |
| barstenscheuren | `barstenscheuren` |
| boekhouding | `boekhouding` |
| communicatie | `communicatie` |
| contracten | `contracten` |
| draaiboek | `draaiboek` |
| hr | `hr` |
| items | `items` |
| kosten | `kosten` |
| medewerkers (organisatie) | `organisatie` of `hr` |
| monday | `monday` |
| pipedrive (MCP via Claude) | `pipedrive` (kijken), `sales` of `admin`; wijzigen: `pipedrive-editors` |
| post (Postbus) | `postbus` (en daarnaast per mailbox in `mailboxen.yaml`) |
| projecten | `projecten` (kijken) of `projecten-editors` (bewerken) |
| renovision | `renovision` |
| sales | `sales` |
| schuldentracker | `schuldentracker` |
| stagebeoordeling | `stagebeoordeling`, plus `stagebeoordeling-bewerken` om te wijzigen |
| stavingsstukken | `stavingsstukken` |
| status | admin of manager |
| telefoonregister | `telefoonregister` |
| vermogen | `vermogen` |

Twijfel je? `Applications` > klik de app > `Policy / Group / User Bindings` laat
precies zien wie erdoor mag.

## De tweede poort: sommige apps controleren zelf nog eens

Dit is de valkuil. Authentik laat iemand door, maar de applicatie krijgt de groepen
mee in een kopregel en kijkt daar zelf nog een keer naar. Staat iemand wel in de
Authentik-koppeling maar krijgt hij binnen de app "geen toegang", dan zit het hier.

| App | Extra controle binnen de app |
|---|---|
| hr | `hr` of `manager` |
| boekhouding | `boekhouding` of `manager` |
| projecten | kijken: `projecten`/`manager`; bewerken: `projecten-editors`/`admin` |
| medewerkers (organisatie) | binnenkomen: `hr` of `organisatie`; de tabbladen financien, relaties, signalen, ontwikkeling en graaf: alleen `admin` of `manager` |
| communicatie | bewerken: `communicatie-editors` of `admin` |
| vermogen | bewerken: `vermogen-editors` of `admin` |
| monday | `monday` |
| pipedrive (MCP) | schrijven: `pipedrive-editors` of `admin`; iedereen die binnenkomt mag lezen. Elke opdracht moet een firma noemen (H-Architects, UNABO, TKN-Buro, Energie Efficient, HarmonieBOUW); de server vraagt erom en kiest nooit zelf. Koppelen: `pipedrive-mcp/README.md` |
| post (Postbus) | de groep opent alleen de tegel; welke mailboxen zichtbaar zijn staat per mailbox in `~/post-config/mailboxen.yaml` (`groepen` en `personen`), dicht tenzij opengezet. Koppelen: `docs/POSTBUS-KOPPELEN.md` |
| sales | bewerken: per naam ingesteld, niet per groep |

Die tweede laag staat in `docker-compose.override.yml` bij de betreffende service
(`HR_GROUPS`, `EDITOR_GROUPS`, `STAFF_GROUPS`). Wijzigen daarvan is een aanpassing in
de stack-repo, geen knop in Authentik.

## Controleren of het gelukt is

Laat de persoon uitloggen en opnieuw inloggen; groepen worden bij het inloggen
meegegeven. Op **https://globaal.be** ziet zij daarna de tegels waar zij bij mag.

## Wat je beter niet doet

**Zet niemand in `admin` of `manager` om een probleem op te lossen.** Die twee geven
toegang tot bijna alles, inclusief financien en personeelsgegevens. Zoek de groep die
bij die ene app hoort.

**Maak geen nieuwe groep** met een variant op een bestaande naam. De app luistert naar
de naam die in de compose-instelling staat; een groep die daar niet in voorkomt doet
niets, en dat is lastig te zien.

## Later

Er ligt een plan om dit te vervangen door twee groepen per app (`app-{naam}-read` en
`app-{naam}-edit`), zodat kijken en bewerken overal hetzelfde heten en `manager` kan
verdwijnen: `docs/plan-groepstoegang-blueprints.md`. Dat is nog niet uitgevoerd; tot
die tijd geldt de tabel hierboven.
