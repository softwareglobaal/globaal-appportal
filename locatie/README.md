# Locatielogboek: handleiding

| | |
|---|---|
| **Versie** | **v2.2** (opdracht v1.2, 04-10-2026; aanvulling v1.4 na onafhankelijke controle, 05-10-2026; eerste rit na de uitrol, 05-10-2026) |
| **Adres** | https://locatie.globaal.be (Authentik, groep `locatie`) |
| **Code** | `locatie/` in softwareglobaal/globaal-appportal; De Locatiewacht in `mijnagents-runner/locatie_wacht.py` |
| **Containers** | `app-locatie` (webapp, poort 3031 op 127.0.0.1) en `app-locatie-tracker` (ontvanger, buiten poort 5000) |
| **Database** | `locatie-data/locatie.db` (SQLite), schema 3, versie in `PRAGMA user_version` (`schema.py`) |

## Besluit van Mehdi (bronbeleid)

De telefoonmetingen zijn bewust gestopt. Sinds **3 oktober 2026 00:00 Belgische tijd** meet alleen de
tracker in de auto, en alleen die reeks telt: voor de kaart, het dagboek, de projectherkenning, de
export, de bewaking en wat agents te lezen krijgen. Oude bewegingsdata (de telefoon van 9-9 tot 3-10,
de dagboeken die daaruit volgden, de plekken die daaruit geleerd waren) wordt nergens ingelezen,
vergeleken, gevalideerd of herberekend. Die bestanden blijven bewaard, buiten de verwerking; er wordt
niets gewist. Later komt er een draagbare tracker bij, met een eigen ingangsdatum en de rol persoon.

De regel staat op één plek, `bronbeleid.py`, en alle routes gebruiken hem:

| bron | rol | status | telt mee vanaf |
|---|---|---|---|
| `auto` (Queclink GV500CG in Mehdi's auto) | auto | actief | 2026-10-03T00:00:00+02:00 |
| `iphone` (OwnTracks) | persoon | uit gebruik | nooit; ontbreken is normaal, geen alarm |
| `draagbaar` | persoon | nog niet aangesloten | krijgt een eigen ingang |

Een punt telt alleen als **zijn meettijd** (`tst`, het moment van de meting volgens het toestel) op of na
de ingang van zijn bron ligt **en** het toestel het vastgelegde toestel van die bron is. De
ontvangsttijd telt niet: een oude meting die later binnenkomt blijft oud. Het IMEI staat alleen in
`ATRACK_IMEIS` in `~/appportal/.env`; in het beleid staat een vingerafdruk (sha256, 16 tekens).
Projectadressen en projectkennis volgen hun eigen bron, ongeacht de ouderdom van het project.

De tracker in de auto **bewijst waar de auto stond, niet waar Mehdi was**. Overal staat daarom "auto bij
project" of "mogelijk werfbezoek".

## Hoe het loopt

    tracker in de auto --@Track/TCP:5000--> app-locatie-tracker --> bericht + punt (SQLite)
                                                                         |
    H-A Projecten + projectmappen --projectsync.py--> projectplek -------+
                                                                         v
                     app-locatie: dagindeling per spoor -> herkenning -> dagboek, status, context
                         |                     |                         |
                     dashboard            De Locatiewacht (VM)      locatie-ophalen.py (Mac)
                                          agenda erbij, bord        kopie naar Dropbox privé

## De ontvanger (`atrack_server.py`, `atrack.py`)

- Eerst het **ruwe bericht** in `bericht` (toestel, soort, protocolversie, teller, verzendtijd, hoe vaak
  het binnenkwam, vingerafdruk), daarna elk positieblok als **punt** met sleutel `(bericht_id, volgnr)`,
  alles in één transactie, en pas dan de bevestiging `+SACK`. Een gebeurtenis is een bericht, geen
  fix: twee statusmeldingen met dezelfde oude fixtijd blijven twee punten (schema 3, 05-10-2026; met
  de sleutel `(bron, tst, berichtsoort, volgnr)` viel de tweede GTSTT nog weg).
- Per punt drie tijden: `tst` (fixtijd, wanneer de positie gemeten is), `moment` (gebeurtenistijd: met
  fix de fixtijd, zonder fix de verzendtijd, anders onbekend) en `ontvangen` (alleen bewijs van ontvangst).
- Een bericht dat al binnen was (exact hetzelfde, of dezelfde teller en verzendtijd met kop `+BUFF`)
  wordt opnieuw bevestigd maar niet opnieuw bewaard; `aantal` telt mee. Worden niet alle posities
  bewaard, dan heet het `deels`, nooit stil `bewaard`.
- **Verdacht**: een bericht met het IMEI van de auto maar een andere protocolversie dan het echte
  toestel, een toestelnaam die niet klopt (zodra die vastligt) of een onmogelijke sprong wordt bewaard
  en gemarkeerd, telt nergens mee en geeft een alarm. Dat is een aanwijzing, geen authenticatie.
- De ontvangerlog toont nooit een volledige toestelidentiteit (alleen de laatste vier cijfers).
- **Meerdere posities per bericht** (FRI en ERI met `<Number>` > 1) worden allemaal gelezen. Vinden we er
  minder dan gemeld, dan staat het bericht in `bericht` met verwerking `onvolledig: ...`.
- `GTSTT` geeft de bewegingsstand (21 motor aan en stil, 22 motor aan en rijdend). Zonder fix (hdop 0)
  is `tst` de tijd van de laatste fix; het moment van een "motor aan" is dan de verzendtijd.
- `toestelbericht` is een venster op `bericht` (berichten zonder positie: teruggelezen instellingen,
  hartslag, bevestigingen).

**Gemeten fout, hersteld (04-10-2026).** Met de oude sleutel `(bron, tst)` gingen op 3 en 4-10 22 van de
27 berichten "motor aan" en ongeveer de helft van de VGL-paren verloren: zonder fix dragen ze de
meettijd van het "motor uit" ervoor, en `ON CONFLICT DO NOTHING` gooide ze weg terwijl de log
"bewaard" zei. De volledige containerlog van die dagen staat in
`mijnagents-data/locatielogboek/archief/tracker-containerlog-tot-20261004T2044Z.txt`.

## Van punten naar een dagboek (`app.py`)

- **Per spoor apart**: elke tracker wordt afzonderlijk ingedeeld. Een geparkeerde auto en een bewegende
  draagbare tracker blijven twee sporen; de persoonlijke context volgt het gedragen toestel.
- **Punten zonder fix** blijven bewaard en zichtbaar, maar bewijzen geen aanwezigheid en tellen niet mee
  in een afstand.
- **Verblijf**: minstens 8 minuten binnen 150 m. **Parkeren**: na "motor uit" meldt de auto niets tot de
  motor aanslaat (spaarstand 1), dus die stilte is gemeten stilstand tot "motor aan", zolang het eerste
  punt erna binnen 1 km ligt. Aankomen en uitrollen vlak voor "motor uit" horen bij het parkeren.
- **Gat**: een stilte waarvan niet gemeten is wat er gebeurde; nooit een verzonnen rit.
- **Dagrand**: een dag loopt van middernacht tot middernacht Belgische tijd, ook op dagen van 23 en 25
  uur. Een dag kan beginnen met "geparkeerd sinds de vorige avond", maar nooit met een punt van voor de
  startgrens. Vandaag is voorlopig; een dag is afgesloten zes uur na middernacht.

## Projectherkenning (`herkenning.py`, `projectsync.py`)

- **Bronnen**: H-A Projecten (`/api/projecten`, H-Architects 2025 en 2026, met uuid, firma en
  adresherkomst) en, voor H-A-nummers buiten die afbakening, de projectmappen (A13, dezelfde bron die H-A
  Projecten voor het adres gebruikt). Geen eigen register. Andere firma's: hun eigen projectbron, nog
  aan te sluiten (Pipedrive is bewust niet aangesproken).
- **Sleutel** `FIRMA:nummer` (bv. `HARC:2604`). Hetzelfde nummer bij twee firma's blijft twee projecten.
- **Geocode**: Geopunt, dan Nominatim, met genormaliseerde schrijfwijzen uit de mapnaam (labels vooraan,
  nummerreeksen, letters achter het huisnummer); met adresvingerafdruk, datum, dienst en kwaliteit. Alleen
  een geocode op huisnummer mag herkennen. Verandert het adres, dan opnieuw; een grove of mislukte geocode
  hoogstens eens per dag opnieuw; een onbereikbare dienst (`fout`) laat de vorige coördinaat staan.
- **Twee fasen**: eerst lezen en geocoderen zonder schrijftransactie, dan de volledige index in één korte
  transactie. Tot 05-10-2026 hield de sync tijdens elk geocodeverzoek het schrijfslot vast en kreeg de
  ontvanger "database is locked" (test_robuust.py met een trage geocoder en een gelijktijdige schrijver).
- **Uit de bron verdwenen**: `actief = 0`, niet gewist. **Bron onbereikbaar**: de laatste goede index
  blijft staan, de taakstatus zegt wat er misliep en hoe oud de index is.
- **Override**: wat Mehdi met de hand rechtzet (ligging, straal, minimale duur, uitsluiten) staat apart in
  `projectplek_override` en wordt nooit overschreven. Een correctie van het adres zelf hoort in de bron.
- **Zekerheid** per verblijf: `bevestigd` (Mehdi), `waarschijnlijk` (één project in bereik, lang genoeg),
  `kort` (korter dan de minimale duur), `onzeker` (meer projecten in bereik: een kandidatenlijst, nooit een
  gekozen dossier), `geen`. Standaard straal 300 m, minimale duur 8 min; korter dan 20 min heet "kort gestopt".
  Een rit binnen 150 m van een projectadres zonder te stoppen is **voorbijrijden**, geen bezoek.
  Een verblijf op een benoemde plek zonder dossier (Thuis) is daar: een project in de buurt is dan
  hoogstens **onzeker**, nooit "mogelijk werfbezoek".
- **Plekken uit de telefoontijd** (Thuis en 2604, met wifi-namen en coördinaten uit de metingen van 9-9 tot
  3-10) staan sinds schema 3 op `actief = 0`, bewaard in `plek_historiek`. Thuis wordt opnieuw bevestigd
  uit een toegestane adresbron: `beheer.py thuis --adres ... --bron ... --door ...` (Geopunt).
- **Correcties** (dashboard of `beheer.py correctie`): welk project, geen project, of "auto niet bij mij".
  Herleidbaar (wie, wanneer, waarom), intrekken zet een tijdstip, toegepast bij elke volgende verwerking.

## Bewaking (`status.py`)

| toestand | betekenis | alarm |
|---|---|---|
| geen gegevens | nog niets van een actieve bron | ja, expliciet (nooit "0 min geleden") |
| in gebruik | laatste bericht minder dan 10 min oud | nee |
| geparkeerd | laatste toestandsmelding zei "motor uit" (GTVGF, of GTSTT 11/12/16/1A) | nee; na 72 uur een vraag (geen levensteken in spaarstand 1) |
| geen bericht zonder motor uit | stilte zonder "motor uit" ervoor | na 60 min |
| onbekend | geen toestandsmelding met bekende gebeurtenistijd, of motor uit en aan op hetzelfde moment | nee |
| niet ingesteld | het toestel van een actieve bron staat niet (juist) in ATRACK_IMEIS; geen dag wordt afgesloten | ja |
| uit gebruik / nog niet aangesloten | telefoon / draagbare tracker | nooit |

De toestand volgt de **gebeurtenistijd van het toestel**, binnen de grens en van het toegelaten toestel,
nooit de ontvangstvolgorde: een ouder "motor uit" dat later uit de buffer komt maakt een rijdende auto
niet geparkeerd. Wat een melding over de motor zegt, beslist één functie, `atrack.motorstand`: GTVGF is uit,
GTVGN/FRI/ERI/STR/IDN/IDF zijn aan, bij GTSTT de stand zelf (1x uit, 2x aan, 4x zegt niets). GTVGF en GTSTT 11
op dezelfde seconde is dus eensgezind motor uit (eerste rit, 05-10-2026). Daarnaast per taak een melding als ze faalt of langer dan **36 uur** niet slaagde
(projectsync, dagboek, export), en een melding bij verdachte berichten.

Een alarmtitel bevat nooit het woord "stil" (daarop belt De Bode).

## Routes

| Route | Wat |
|---|---|
| `GET /` | dashboard, standaard vandaag, ververst elke 45 s (kaart, tabel, cijfers, bronstatus, taken) |
| `GET /api/dag/<dag>` | punten (met bron, toestel, fix, hdop, ontvangen, verzonden, nagestuurd), indeling, sporen |
| `GET /api/dagboek/<dag>` | het dagboek als tekst en gegevens, met een versie: één generator voor VM, bord en export; leest alleen |
| `GET /api/revisies` | per dag de versie van het dagboek, zodat wacht en export een herziene afgesloten dag opnieuw ophalen |
| `GET /api/dagcijfers` | per dag verblijven, km, minuten onderweg: voor het bord (`/dagen`) |
| `GET /api/context?dag=<dag>` | locatiecontext voor agents: `verblijven` alleen positieve projectverblijven (auto bij project, waarschijnlijk of bevestigd), `kandidaten` apart en niet positief; nooit Thuis, rit, gat of rechtgezette verblijven |
| `GET /api/status` | per bron de stand, de taken met laatste geslaagde en volgende uitvoering, de projectdekking |
| `GET /api/beleid` | het bronbeleid |
| `GET /api/projectplekken` | projectplekken met overrides en de dekking |
| `GET/POST /api/correctie` | correcties; schrijven alleen via het portaal (Authentik) of met het wachtwoord |
| `GET/POST /api/plekken` | benoemde plekken (Thuis, een werf met dossier en firma), ook de niet-actieve, voor De Agendawacht |
| `GET /gezond`, `GET /health` | kort, per bron; gezondheidscontrole van de container |
| `POST /pub` | OwnTracks (uit gebruik): bewaard en herleidbaar, telt niet mee |

## Planning (Belgische tijd)

De VM draait in UTC en zijn cron kent geen tijdzone. Elke taak staat op beide mogelijke UTC-uren en
het script kijkt zelf of het het juiste Belgische uur is (`--om`, `--controle`). Tijden in
`bronbeleid.PLANNING`, regels in `mijnagents-runner/planning/locatie.cron`, op de VM gezet met
`mijnagents-runner/planning/locatie_cron_zetten.py --zet`.

| taak | wanneer | wat |
|---|---|---|
| dagboek | 21:30 | De Locatiewacht: verrijken (adressen), inhalen vanaf de oudste open dag, herziene afgesloten dagen opnieuw, agenda erbij, revisies bewaren, klaarzetten |
| controle | elk uur 07:05 tot 22:05 | bronbewaking |
| projectsync | 02:15, 08:15, 11:15, 14:15, 17:15, 20:15 | projectadressen uit hun bron (alleen opnieuw geocoderen bij een adreswijziging) |
| export | 22:45 (Mac, launchd, zonder `--dagen`) | dagboek en agendadeel (alleen bij dezelfde dagboekversie) naar de teammap private, databasekopie met datum |

## Beheer op de VM

    docker exec app-locatie python3 projectsync.py            # projectadressen nu bijwerken
    docker exec app-locatie python3 beheer.py status          # bronstatus en taken
    docker exec app-locatie python3 beheer.py verrijk 2026-10-05   # adressen opzoeken (netwerk eerst, kort schrijven)
    docker exec app-locatie python3 beheer.py thuis --adres "..." --bron "..." --door mehdi
    docker exec app-locatie python3 beheer.py correctie auto 2026-10-05T10:00 2026-10-05T11:00 project HARC:2604 --door mehdi --reden "..."
    docker exec app-locatie python3 beheer.py override HARC:2604 --lat .. --lon .. --reden "parking achteraan" --door mehdi
    ~/agents/.venv/bin/python ~/appportal/mijnagents-runner/locatie_wacht.py --droog --dag 2026-10-05

Een tweede tracker aansluiten: een regel in `bronbeleid.BRONNEN` (status actief, ingang, vingerafdruk van
het IMEI), het IMEI in `ATRACK_IMEIS`, de grendels laten draaien en uitrollen. Het ontvangstprotocol van
een draagbare tracker wordt pas vastgelegd na de keuze van het toestel.

## Bestanden en bewaren

- Schema-upgrade: eerst een kopie in `locatie-data/backups/locatie-schema<N>-<tijd>.db`, dan één transactie.
- Mac-export: `Prive met Claude/Locatielogboek/dagen/<dag>.{md,json}` in de **teammap private** (een
  teammap, geen persoonlijke map), vorige versies in `dagen/revisies/`, databasekopie per dag in
  `ruwe-database/locatie-<dag>.db` (oudere kopieën blijven; opruimen beslist Mehdi).
- De oude bestanden (telefoon 9-9 tot 3-10) staan in `Data uit Mehdi/Locatie/archief/` en als losse
  dagboeken in de mappen `dagen/`; ze worden niet meer gelezen (ook niet door de archivaris en
  `locatie-overzicht.py`).

## Grendels

De Docker-build draait de tests van de tegel: `test_dagindeling`, `test_atrack`, `test_atrack_server`,
`test_bronbeleid`, `test_schema`, `test_herkenning`, `test_auto`, `test_export`, `test_robuust`. GitHub
Actions draait die ook, en daarnaast in een tweede job (Python 3.12, zoals de VM) de lezers buiten de tegel:
`test_locatie_wacht`, `test_levenscoach_grens`, `test_locatielezers` (met de inventaris van elke lezer).
Eigen proefgegevens en een verzonnen IMEI; de echte meting bevat het thuisadres en hoort niet in git.

## Lezers van locatiegegevens (inventaris)

Elke lezer gebruikt de startgrens; `mijnagents-runner/tests/test_locatielezers.py` faalt zodra er een
lezer bijkomt die hier niet staat.

| lezer | wat hij leest | datum | toestel | rol |
|---|---|---|---|---|
| De Locatiewacht | `/api/dagboek`, `/api/revisies`, `/api/context`, `/api/status`, `/api/projectplekken` | bronbeleid (nooit voor 3-10) | via de tegel (sql_actief) | auto/persoon per spoor |
| De Archivaris | `koppelingen/locatiecontext.py` | grens | via de tegel | "auto bij project", geen aanwezigheid |
| De Plaudwacht | `koppelingen/locatiecontext.py` | grens | via de tegel | idem |
| De Dagbundelaar | `locatiecontext.dag_heeft_dagboek` (precies de dag) | grens | n.v.t. | sluit locatie uit bundels |
| De Levenscoach | klaarzet-items van soort locatie | `dag_toegestaan` | n.v.t. | alleen voor Mehdi |
| De Agendawacht | `/api/plekken` (benoemde plekken voor reistijd) | n.v.t. (geen metingen) | n.v.t. | n.v.t. |
| het bord (`/dagen`, `/dag/<datum>`) | `/api/dagcijfers`, `/api/beleid` | grens | via de tegel | alleen beheer |
| Mac-export, `locatie-overzicht.py` | `/api/dagboek`, `/api/revisies`; geëxporteerde JSON | `dag_toegestaan` | via de tegel | n.v.t. |

## Toestelbeveiliging

Het IMEI van de tracker is geen geheim meer: het stond in de publieke geschiedenis van deze repo (twee
commits, verwijderd in 84f1d28). Wie het kent kan berichten als "auto" insturen. Privé zetten van de repo
stopt verdere openbaarheid, maar trekt bestaande kopieën niet terug. Wat er nu staat is geen
authenticatie maar beperking van schade: verdachte berichten (andere protocolversie, onmogelijke sprong)
tellen niet mee en geven een alarm, en de log toont geen identiteit. De echte oplossing hangt af van wat
het toestel kan; zie `Prive met Claude/Locatielogboek` voor het onderzoek en het proefplan. Niets aan het
toestel wordt ingesteld zonder Mehdi.

## Wat Mehdi beslist

- Of de tracker op spaarstand 2 gaat (een levensteken elke 15 minuten bij stilstand), na het teruglezen
  van de instellingen (sms-reeks in `Data uit Mehdi/Locatie/04 Tracker in de auto, instellen`).
- Of een verblijf bij een project een werfbezoek was, en welk project bij een onzekere kandidatenlijst.
- Welke andere firma's (en welke projectbron) in de herkenning komen.
- Of oude databasekopieën en revisies ooit opgeruimd worden.

## Het andere spoor: de Google Maps-export

`tijdlijn.py` verwerkt de handmatige export uit Google Maps. Sinds 3-10-2026 hoort die niet bij de
actieve reeks; het script blijft voor wie een oude export wil lezen, buiten de verwerking.

## Versiehistoriek

- **v2.2 (05-10-2026, eerste rit na de uitrol)**: GTVGF en GTSTT 11 op dezelfde seconde gaven 'onbekend' op de
  tegel en geen parkeren in het dagboek, omdat elke STT als 'in gebruik' telde. Nu één regel
  (`atrack.motorstand`) voor tegel en dagindeling, met een grendel op het patroon van die rit.
- **v2.1 (05-10-2026, aanvulling v1.4)**: schema 3 (punt per bericht, gebeurtenistijd, verdacht); toestand
  op gebeurtenistijd; projectsync en adresverrijking zonder slot tijdens netwerkwerk; leesroutes schrijven
  niets; context alleen positieve projectverblijven, Thuis hoogstens onzeker; plekken uit de telefoontijd
  buiten de herkenning; inhaal oudste dag eerst en herziene afgesloten dagen opnieuw (`/api/revisies`);
  dag niet afgesloten zonder toestelconfiguratie; taakouderdom 36 uur; agents (Plaud, Archivaris,
  Dagbundelaar, bord) op `koppelingen/locatiecontext.py` en de dag-API; log zonder toestelidentiteit.

- **v2.0 (04-10-2026)**: bronbeleid met startgrens en toestel; ruwe berichten en een sleutel die
  gelijktijdige gebeurtenissen houdt; meerdere posities per bericht; schema met versie en kopie;
  parkeren na motor uit; fix 0 uit de afleiding; sporen per tracker; dagranden van 23 en 25 uur;
  projectherkenning uit H-A Projecten en de projectmappen met zekerheid en correcties; bronstatus per
  meetmodus; één dagboekgenerator; dashboard ververst zichzelf; planning in Belgische tijd.
- v1.x (9-9 tot 3-10-2026): OwnTracks op de telefoon, daarna de tracker in de auto ernaast.
