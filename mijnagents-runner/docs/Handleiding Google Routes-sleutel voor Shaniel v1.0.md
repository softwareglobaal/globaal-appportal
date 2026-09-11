# Handleiding: Google Routes-sleutel voor De Agendawacht

Versie 1.2, 11-09-2026. Voor Shaniel, in opdracht van Mehdi.

## Wat alleen Mehdi kan doen

Alles hieronder wacht op twee dingen die niemand anders kan doen: **inloggen op
zijn eigen Google-account** en **zijn betaalkaart invoeren bij Billing**. Dat is
stap 1 en 2, samen ongeveer vijf minuten. Geeft hij daarna Shaniel de rol Editor
op het project (optie B hieronder), dan doet Shaniel stap 3 tot 7 alleen.

## Waarvoor

De Agendawacht (Mehdi Agents, mijnagents.globaal.be) zet rond elke buitenafspraak van
Mehdi een reistijdblok heen en terug. Nu rekent hij met een vaste filefactor per
vertrekuur. Met een Google Routes-sleutel rekent hij met het echte verkeer op het
vertrekuur. De code staat klaar: zodra de sleutel op de server staat, gebruikt hij
die vanzelf. Er hoeft niets herstart te worden.

## Onder welk account

**Het Google-account van Mehdi: mehdiprivewerkagenda@gmail.com.** Niet het project
hr-assistant-calendar en niet een ander bedrijfsaccount. Het Cloud-project hoort
bij Mehdi's eigen agenda-account, zodat de sleutel bij hem blijft.

Shaniel kan niet in dat account inloggen. Twee manieren:

- **Optie A (eenvoudigst):** Mehdi logt in op console.cloud.google.com en Shaniel
  doet de stappen op zijn scherm (Zoom met schermdeling, of naast elkaar).
- **Optie B:** Mehdi doet stap 1 en 2 zelf en geeft Shaniel daarna de rol Editor
  op het project (IAM & Admin > IAM > Grant access > e-mail van Shaniel > rol
  Editor). Shaniel doet dan stap 3 tot 6 vanuit zijn eigen Google-login.

## Wat het kost

Google Maps Platform rekent per aanvraag, per maand, met een gratis deel per SKU.
Een route met verkeersinfo valt onder **Routes: Compute Routes Pro**:

| | |
|---|---|
| Gratis per maand | 5.000 aanvragen |
| Daarboven | 10 dollar per 1.000 aanvragen (tot 100.000 per maand) |

De Agendawacht vraagt per buitenafspraak drie routes: twee voor de heenweg (een
eerste schatting om het vertrekuur te kennen, dan de echte) en een voor de terugweg.
Dat gebeurt alleen bij een nieuwe afspraak en een keer per dag in de ochtendronde ter
controle. Bij pakweg tien buitenafspraken per week is dat ruim onder 500 aanvragen per
maand. **Verwachte kost: 0 euro.** Als grendel zetten we in stap 7 een dagplafond en
een budgetmelding.

Een betaalkaart is wel verplicht om Billing te activeren; zonder Billing werkt de
API niet, ook niet in het gratis deel.

## Stappen (menu's in het Engels, zoals op het scherm)

1. **Project.** Ga naar console.cloud.google.com, ingelogd als
   mehdiprivewerkagenda@gmail.com. Klik bovenaan op de projectkiezer, dan
   **New project**. Name: `mehdi-agents`. Create. Kies daarna dat project.
2. **Billing.** Menu (drie streepjes) > **Billing** > **Link a billing account**.
   Is er nog geen: **Create billing account**, land Belgium, betaalkaart van Mehdi
   (Mehdi voert die zelf in). Het account mag op naam van H-Architects staan; de
   factuur komt dan daar terecht. Kies "Individual" of "Business" naar keuze van Mehdi.
3. **Routes API aanzetten.** Menu > **APIs & Services** > **Library**. Zoek
   `Routes API`. Klik erop, dan **Enable**.
4. **Sleutel maken.** Menu > **APIs & Services** > **Credentials** >
   **+ Create credentials** > **API key**. Er verschijnt een venster met de sleutel.
   Kopieer hem (knop Copy) en klik **Edit API key** om hem meteen te beperken (stap 5).
5. **Sleutel beperken.** Op de sleutelpagina: Name: `agendawacht-routes`.
   **Application restrictions: None** (de server roept de API rechtstreeks aan).
   **API restrictions: Restrict key** > vink alleen **Routes API** aan. **Save**.
6. **Sleutel op de server zetten.** Dit doet Mehdi of Shaniel via ssh naar de
   Globaal-VM. Vervang PLAK-HIER door de sleutel. De sleutel komt nergens anders:
   niet in chat, niet in een document, niet in git.

   ```bash
   ssh globaal 'bash ~/appportal/scripts/agendawacht-routes-sleutel.sh PLAK-HIER'
   ```

   Het script probeert de sleutel eerst bij Google en schrijft pas weg als er een
   rijtijd terugkomt. Werkt de sleutel niet, dan zegt het waarom (Billing, Routes
   API of de beperking uit stap 5) en blijft `.env` ongemoeid. Daarna doet het
   meteen de controle van de volgende paragraaf. Twee keer draaien mag: een
   bestaande regel wordt vervangen, niet verdubbeld.

   Dit is met opzet geen losse `>>`-regel. De Agendawacht slikt een mislukte
   route-aanroep stil en valt terug op de filefactor, dus een foute sleutel zou
   je anders pas weken later opmerken.

7. **Grendels tegen kosten.**
   - De dagquota van de Routes API is **niet verlaagbaar**: in de console staat
     die rij op "Adjustable: No". Daarom zit de harde stop in onze eigen code.
     `agenda_wacht.py` telt de aanroepen per dag in
     `~/appportal/mijnagents-data/routes-teller.json` en valt bij het plafond
     terug op de filefactor, met een melding op het bord. Standaard 100 per dag,
     bij te stellen met `AGENDA_ROUTES_DAGLIMIET` in `~/appportal/.env`. Ook een
     volle maand op dat plafond blijft onder de 5.000 gratis aanvragen.
   - Menu > **Billing** > **Budgets & alerts** > **Create budget**. Name
     `mehdi-agents`, Amount **5 EUR**, meldingen op 50, 90 en 100 procent naar
     mehdiprivewerkagenda@gmail.com. Create.

## Controleren dat het werkt

Het script uit stap 6 doet deze controle zelf. Wil je later opnieuw kijken, dan is
dit het commando; het antwoord moet "live" bevatten:

```bash
ssh globaal 'cd ~/appportal/mijnagents-runner && ~/agents/.venv/bin/python -c "import sys; sys.path[:0]=[\"koppelingen\",\".\"]; import agenda_wacht as aw, datetime; print(aw.rijtijd_min([50.8798,4.7005],[51.0603,4.3604], (datetime.datetime.now()+datetime.timedelta(days=1)).replace(hour=8).astimezone()))"'
```

Vanaf de volgende ronde van de Agendawacht (werkdagen 06:30 en dan elke twee uur)
staat in elk nieuw reistijdblok "live verkeer Google". Blijft er "filefactor" staan,
dan is de sleutel niet gelezen: controleer de regel in `~/appportal/.env` en of de
Routes API in het juiste project aanstaat.

## Wat er nooit gebeurt

- De sleutel komt niet in code, chat, documentatie of git. Alleen in `~/appportal/.env`.
- De Agendawacht maakt en verplaatst geen afspraken; alleen zijn eigen reistijdblokken.
- Ander gebruik van de sleutel (andere API's) staat uit door de beperking in stap 5.
