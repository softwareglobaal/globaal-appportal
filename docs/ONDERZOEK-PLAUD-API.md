# Onderzoek: Plaud API voor het uitschrijven van Xelion-opnames

*Opgesteld 31-08-2026, naar aanleiding van de vraag of we onze audiobestanden
door Plaud kunnen laten transcriberen. Bronnen: docs.plaud.ai en dev.plaud.ai,
plus een eigen proef op de live Xelion-API.*

## Conclusie

Ja, en zonder Plaud-hardware. Plaud opende eind 2025 een developer-platform.
De transcriptie-API neemt elk audiobestand aan waar hij bij kan; dat de dienst
verkocht wordt bij hun eigen recorders doet er niet toe. Aanmelden gaat via
portal.plaud.ai zonder tussenkomst van sales.

## Twee wegen, één bruikbaar

| | Wat het is | Bruikbaar voor ons |
|---|---|---|
| **Transcription API** | audio erin, JSON eruit | Ja: dit is de weg |
| **Plaud MCP en CLI** | leest opnames die al in een Plaud-account staan | Nee: kan niet uploaden |

De MCP-server en de CLI (`@plaud-ai/cli`) zijn leeshulpjes voor een bestaand
Plaud-account. Ze kunnen geen audio aanleveren. Wie in de consumentenapp een
bestand importeert kan ze daarna wel uitlezen, maar dat is handwerk aan de
voorkant en dus geen pijplijn.

## De keten

1. `POST /oauth/partner/access-token` - basic auth met client_id en
   client_secret, geeft een partnertoken (1 uur).
2. `POST /open/partner/users/access-token` - partnertoken erin, gebruikers-
   token eruit. Nodig voor de upload.
3. `POST /open/partner/files/upload/generate-presigned-urls` - geeft
   voorgetekende S3-URL's, standaard 5 MB per stuk.
4. `PUT` elk stuk naar zijn URL, ETag uit de antwoordheader bewaren.
5. `POST /open/partner/files/upload/complete-upload` - stukken afronden, geeft
   een download-URL die **24 uur** geldig is.
6. `POST /open/partner/ai/transcriptions/` - headers `X-Client-Id` en
   `X-Client-Api-Key`, body met `file_url`. Geeft een `transcription_id`.
7. `GET /open/partner/ai/transcriptions/<id>` - navragen tot `SUCCESS`.

Let op de twee soorten sleutels: het **secret** is voor de tokens, de
**api_key** voor de transcriptie-API. Ze zijn niet inwisselbaar.

Stap 3 tot 5 zijn optioneel: de transcriptie-API neemt elke publiek bereikbare
URL aan. Wij gebruiken toch de upload van Plaud, want anders moeten wij zelf
gespreksopnames publiek bereikbaar maken. Dat is precies wat je niet wil.

## Wat je terugkrijgt

`data.text` (de volledige tekst), `data.language`, `data.duration` en
`data.results[]` met per segment `start`, `end`, `text`, `speaker_id` en de
gedetecteerde taal. Sprekerherkenning zet je aan met
`params.diarization.enabled`. Taal mag `auto`; meerdere talen in één gesprek
zijn geen probleem, wat voor onze Nederlands-Frans-Engelse gesprekken telt.

Geen webhooks. Navragen is de enige manier om te weten dat een taak klaar is.

## Grenzen en kosten

- 60 verzoeken per minuut.
- Opname maximaal 24 uur, sprekerherkenning tot 6 uur.
- Formaten M4A, MP3, WAV.
- **$0,28 per uur audio**, pay-as-you-go, geen minimumafname. Eerste 300 uur
  gratis. Aangesloten apparaten kosten $15 per stuk per maand; wij sluiten geen
  apparaten aan, dus die post blijft nul.

Ter maat: op 31-08-2026 stonden er 1022 opgenomen gesprekken in het archief,
samen 28,4 uur over twee en een halve maand. De hele inhaalslag past ruim in de
gratis 300 uur; daarna is het orde $3 per maand.

## Privacy: het echte aandachtspunt

Plaud verwerkt standaard in de **Verenigde Staten** en bewaart
API-transcripties **7 dagen**. Verwerking in Europa bestaat, maar je moet
ervoor bij hun sales zijn; het is geen instelling die je zelf omzet.

Voor Belgische telefoongesprekken met klanten en medewerkers is dat een
beslissing die vóór het aanzetten genomen moet worden, niet erna. De koppeling
staat daarom standaard uit en de tekst is in het dashboard afgeschermd voor de
beheerdersgroepen.

## Xelion-kant, geverifieerd

`GET communications/<oid>/audio` met de bestaande sessie-header geeft de
opname terug: `audio/x-mp3`, ongeveer 64 kbit/s. Een gesprek van 104 seconden
was 227 KB, dus circa 0,5 MB per kwartier. De hele voorraad is enkele honderden
MB. Alleen oproepen met `recordingStatus = "recorded"` hebben een opname; de
rest geeft een 404.

Getest op 31-08-2026 tegen de live API, alleen lezend.
