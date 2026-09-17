# Fathom data: volledig archief en mapindeling (v1.0, 18-09-2026)

Besluit van Mehdi op 18-09-2026: hetzelfde als voor Plaud (zie `Plaud Agent - eigen ophaalroute en
mapindeling v1.0.md`). Het volledige Fathom-archief komt binnen, plat, en de map heet **Fathom data**.

## Wat er was

De Fathomwacht kijkt veertien dagen terug en draait sinds augustus 2026. Daardoor stonden er op
18-09 maar 288 gesprekken in `Data uit Mehdi/Fathom` (276 in `2026/`, 12 in `Prive/2026/`),
terwijl Fathom er 2.248 heeft, terug tot 28 oktober 2024.

## Waar het vandaan komt

Fathom heeft een echte API, dezelfde die het contractsysteem al gebruikt:

| Wat | Waar |
|---|---|
| Basis | `https://api.fathom.ai/external/v1` |
| Lijst met transcript | `GET /meetings?created_after=...&include_transcript=true`, cursor in `next_cursor`, 10 per pagina |
| Sleutel | kop `X-Api-Key`; op de VM in `~/appportal/.env` als `FATHOM_API_KEYS` (twee sleutels, komma-gescheiden) |
| Grens | ongeveer 30 zware calls per minuut; de koppeling wacht 2,5 s per pagina en herkanst bij 429 |
| Video | geen bestand via de API, alleen `share_url`; per map `video (Fathom).webloc` en `video.md` |

Gemeten 18-09-2026, per sleutel:

| Sleutel | Opgenomen door | Gesprekken | Sinds |
|---|---|---|---|
| 1 | shaniel@hdssr.com | 97 | 02-07-2026 |
| 2 | zoomafspraken@gmail.com (Mehdi's Zoom-account) | 2.151 | 28-10-2024 |

De Fathom-connector op Mehdi's claude.ai is datzelfde tweede account (gemeten met `get_identity`),
dus die twee sleutels dekken alles. Er is geen derde account.

## De mapnaam, precies

`JJJJ-MM-DD UUMM <titel in Fathom>`, plat in `Fathom data/`, geen jaarmap en geen Prive-submap.
Datum en uur in Belgische tijd (Fathom levert UTC). Tekens die Dropbox niet in een naam wil worden
een spatie; langer dan 110 tekens wordt afgekapt. Botst de naam met een ander gesprek, dan komt het
`recording_id` erachter. De privé-vlag uit de herkenning van De Fathomwacht staat in `gesprek.json`.

**Let op de titels.** Fathom noemt bijna elk gesprek "Impromptu Zoom Meeting": bij de eerste 297
opgehaalde gesprekken waren er 259 zo. Dat is bewust zo gelaten: de naam die Fathom geeft is de
eerlijke nulstand. Een betekenisvolle naam uit de inhoud, de agenda, Pipedrive en het dashboard is
de volgende stap, met Mehdi's regels, en geldt dan voor Fathom en Plaud tegelijk.

In elke map: `transcript.md` (leesbaar, met kop), `transcript.json` (de ruwe uitingen, de bron),
`gesprek.json` (metadata, herkenning als die er was, `oud_archief` als de map is overgenomen),
`video.md` en de `.webloc`, en als Fathom ze had `samenvatting.md`, `actiepunten.md`,
`hoogtepunten.md`. De samenvatting van Fathom is geen bron (afspraak D7).

## De scripts

| Script | Wat het doet |
|---|---|
| `mijnagents-runner/fathom_haal_alles.py` | Draait op de VM. Haalt alle gesprekken van elke sleutel met transcript, één map per gesprek in `mijnagents-data/fathom-data/`, neemt bestaande mappen van De Fathomwacht over op `recording_id` (herkenning blijft), schrijft `00 index.md` en `00 opbouw.log`. Opnieuw draaien slaat over wat compleet is. |
| `mijnagents-runner/fathom_wacht.py` | `archiefmap()` maakt sindsdien dezelfde platte naam; `bestaande_map()` zoekt op `recording_id` met één index per ronde. Spiegelt naar Mehdi's privé-Dropbox onder `/Fathom data`. |
| `~/bin/data_uit_mehdi_sync.sh` (Mac) | Nieuwe regel `haal fathom-data "Fathom data"`: elk half uur van de VM naar Dropbox. |

Het archief staat op de VM omdat de sleutels daar staan en het alleen tekst is (2.248 gesprekken
is ongeveer 200 MB); de VM had op 18-09 weer 9,5 GB vrij.

## Uitkomst (18-09-2026, 01:55)

`fathom_haal_alles.py` liep in ongeveer 25 minuten, zonder één fout of herkansing. Daarna is
`data_uit_mehdi_sync.sh` met de hand gedraaid; de Mac telt hetzelfde als de VM.

| | |
|---|---|
| Gesprekken in Fathom | 2.248 (beide sleutels, ontdubbeld op `recording_id`) |
| Mappen in `Fathom data` | 2.248, elk met `gesprek.json` en `transcript.json` |
| Zonder transcript | 6 (Fathom heeft er geen; `geen-transcript.txt` in de map) |
| Overgenomen uit het oude archief, met herkenning | 288 |
| Naambotsingen | 0 |
| Uitingen samen | 668.725 |
| Omvang | 225 MB op de VM, 215 MB in Dropbox |
| Per jaar | 149 uit 2024, 912 uit 2025, 1.187 uit 2026 |
| Vroegste | 2024-10-28 1105 Joseph Ugale H-Architects Prospections |
| Titel "Impromptu Zoom Meeting" of even leeg | 843 van 2.248 (38 %) |

Twee dingen die de API niet geeft: `default_summary` is bij alle 2.248 leeg (de samenvatting van
Fathom zit niet in de lijst-oproep; niet erg, ze is geen bron), en er is geen videobestand (wel de
deellink in elke map).

## Wat hierna nog moet

1. **Opruimen.** `Data uit Mehdi/Fathom` (oude indeling, 288 mappen) en op de VM
   `mijnagents-data/fathom/` zijn dezelfde gesprekken onder de oude naam; alles is overgenomen.
   Weg zodra Mehdi ja zegt; dan ook de regel `haal fathom Fathom` uit het syncscript.
2. **Benamingen.** Fathom en Plaud samen hernoemen op inhoud, agenda, dossier en dashboard, zodat
   Mehdi dat niet met de hand doet. Eerst de regels afspreken; dan één script dat beide archieven
   in dezelfde stijl benoemt en de oude naam in `gesprek.json` bewaart.
