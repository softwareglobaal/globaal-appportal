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

## Uitkomst

Wordt aangevuld zodra `fathom_haal_alles.py` klaar is (regel `KLAAR` in `00 opbouw.log`).

## Wat hierna nog moet

1. **Opruimen.** `Data uit Mehdi/Fathom` (oude indeling, 288 mappen) en op de VM
   `mijnagents-data/fathom/` zijn dezelfde gesprekken onder de oude naam; alles is overgenomen.
   Weg zodra Mehdi ja zegt; dan ook de regel `haal fathom Fathom` uit het syncscript.
2. **Benamingen.** Fathom en Plaud samen hernoemen op inhoud, agenda, dossier en dashboard, zodat
   Mehdi dat niet met de hand doet. Eerst de regels afspreken; dan één script dat beide archieven
   in dezelfde stijl benoemt en de oude naam in `gesprek.json` bewaart.
