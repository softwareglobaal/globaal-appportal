# Locatielogboek

Vangt de berichten op van de OwnTracks-app op Mehdi's iPhone en maakt er een
dagboek van: waar was hij, wanneer, en hoe lang.

Waarom deze tegel bestaat: Google Maps bewaart de tijdlijn sinds eind 2024 op
het toestel zelf. Er is geen koppeling en geen cloudkopie meer, alleen een
exportknop die een mens moet indrukken. Wie een dagelijks logboek wil, moet het
zelf verzamelen. Dat doet deze tegel, zonder tussenpartij: de telefoon praat
rechtstreeks met onze eigen server.

## Hoe het loopt

    iPhone (OwnTracks)  ->  POST locatie.globaal.be/pub  ->  SQLite  ->  dashboard

De telefoon heeft geen browsersessie, dus `/pub` passeert de forward-auth van
Authentik en controleert zelf `LOCATIE_WACHTWOORD` uit de `.env`. Dat is
hetzelfde patroon als `/agent-status` op de agents-tegel. De rest van de tegel
zit gewoon achter de SSO, achter de rol `locatie`.

## Instellingen

| Variabele | Wat |
|---|---|
| `LOCATIE_WACHTWOORD` | wachtwoord dat de telefoon meestuurt; leeg = `/pub` bestaat niet |
| `LOCATIE_DB` | pad naar het SQLite-bestand, standaard `/data/locatie.db` |
| `PORT` | standaard 3031 |

## Routes

| Route | Wat |
|---|---|
| `POST /pub` | ontvangstpunt voor OwnTracks (wachtwoord vereist) |
| `GET /` | dagboek met kaart |
| `GET /api/dag/<JJJJ-MM-DD>` | punten en dagindeling als JSON |
| `GET /gezond` | aantal punten en hoe lang geleden het laatste binnenkwam |

## Van punten naar een dagboek

OwnTracks stuurt kale coördinaten. Google zegt "je was drie uur bij die klant";
OwnTracks zegt alleen "51.21, 4.40". Het verschil maken we in `dagindeling()`:
punten die binnen 120 meter van elkaar blijven gedurende minstens 8 minuten
worden één **bezoek**; wat ertussen ligt is een **verplaatsing**.

Die twee getallen (`STILSTAND_METER`, `STILSTAND_MINUTEN`) zijn de knoppen. Te
streng en een kort werfbezoek verdwijnt in de rit ernaartoe; te los en een file
op de ring wordt een bezoek. Ze staan bovenaan `app.py` en mogen bijgesteld
worden zodra er echte dagen in zitten om tegen te toetsen.

## Het andere spoor: de Google Maps-export

`tijdlijn.py` in deze map verwerkt de handmatige export uit Google Maps
(`Timeline.json` op iOS, `location-history.json` op Android). Dat spoor loopt
naast deze tegel: Google herkent plaatsen en vervoerswijze, wat OwnTracks niet
doet, maar de export vereist elke keer een mens die op een knop drukt. Draait op
de Mac, niet in de container:

    python3 tijdlijn.py ~/Downloads/Timeline.json
    python3 tijdlijn.py ~/Downloads/Timeline.json --dag 2026-09-09
    python3 tijdlijn.py ~/Downloads/Timeline.json --schrijf ~/Documents/Locatielogboek/dagen

Valkuil die het script opvangt: de export mengt tijdzones binnen een bestand.
Bezoeken dragen de lokale offset (`+02:00`), sporen staan in UTC (`Z`). Wie dat
niet omrekent ziet een spoor twee uur voor het bezoek dat erin zit.

## Wat er nog niet is

- Adressen. De database houdt coördinaten; reverse geocoding (Geopunt voor
  Vlaanderen, Nominatim daarbuiten) moet er nog bij.
- De koppeling met de agenda en met fotometadata, waar het uiteindelijk om
  begonnen is.
