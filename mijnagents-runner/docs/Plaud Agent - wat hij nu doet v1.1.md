# Plaud Agent: wat hij nu doet, v1.1

12-10-2026. Vervangt v1.0 (nulmeting). Uitvoering van de verbeteropdracht Plaud-agent v1.0.
Werkwijze op het bord: `werkwijze/plaud-wacht.md` versie 3.

## De keten in één oogopslag

| Stap | Waar | Wat | Bestand |
|---|---|---|---|
| Ophalen | Mac, launchd `be.globaal.plaud.ophalen`, elk uur op :05 | alle opnames uit de Plaud-API naar het archief; slot, tijdslimiet 50 min | `plaud/plaud_haal_alles.py` |
| Bouwen | Mac | één map per opname, op Plaud-id; atomair; audio-extensie uit de inhoud | `plaud/bouw_map.py`, `plaud/archief.py` |
| Manifest | Mac | `00 manifest.json`, `00 status.json`, `00 plaud_lijst.json` in het archief | `plaud/manifest.py`, `plaud/lijst.py` |
| Doorzetten | Mac → VM | rsync van manifest, status, lijst en `transcript.json`; nooit audio, nooit `--delete` | `plaud/plaud_invoer_push.sh` |
| Verwerken | VM, cron :20 met flock en timeout | zoektaken, context, herkenning, dossier, publicaties | `plaud_wacht.py` |
| Staat | VM | `mijnagents-data/plaud-staat/<id>.json`: wat gedaan is en wat open staat | `plaud/staat.py` |

Archief: Dropbox `Data uit Mehdi/Plaud`. Er is één archief; de oude VM-map `plaud` gaat niet meer
naar de Mac (`planning/mac/data_uit_mehdi_sync.sh`).

## Het opnamecontract (`plaud/contract.py`, versie 1)

`plaud_id` (`of_<32 hex>`), `start_utc`, `start_brussel`, `duur_minuten`, `naam_in_plaud`,
`transcript` {staat aanwezig | wacht | onbekend, pogingen, volgende_controle}, `audio`, `archief`,
`account`, `toestel` (serienummer), `opgenomen_door`, `bronbewijs`, `herstel`.

- Zonder geldige opnametijd: herstel, nooit de wijzigingsdatum van een bestand.
- Gedeeld account: `account` en `opgenomen_door` blijven "onbekend" tot bewijs; het toestel staat apart.
- Transcript dat (nog) niet bestaat: opnieuw vragen na 1 u, 6 u, 1 dag, 3 dagen, daarna wekelijks.

## Volledig is volledig (`plaud/archief.py`)

Compleet = `gesprek.json` met het juiste id, parsebare `transcript.json`, `transcript.md` en een
definitief audiobestand. `.deel`, `.tmp`, `.part` tellen nooit. Eén resolver op id: een hernoemde
map blijft dezelfde opname; een botsing krijgt een suffixmap `[kort id]`; één id op twee plaatsen is
een conflict. Online-only bestanden in Dropbox tellen als aanwezig.

## Veilige links (`plaud/veilig.py`)

Alleen https naar de vaste opslag van Plaud, poort 443, alle opgeloste adressen publiek, omleidingen
opnieuw gecontroleerd (hoogstens drie), grootte en tijd begrensd. Links verschijnen nooit in status,
manifest, logboek of transcripten.

## Dossier en zoektaken (`plaud/dossier.py`, `plaud/zoektaak.py`)

- Dossier = firma plus projectnummer, op bewijs: titel, openingszin, overlappende afspraak, kop,
  zoektaak (Fathom ook: e-mail van een deelnemer bij één deal). Het model levert een kandidaat.
- Conflict, privé, onbekende afdeling of lage zekerheid: geen kopie, klaarzetten voor Mehdi.
- Klaarzet: soort `transcript`, sleutel = projectnummer, `deal_id` apart, `verslagsoort` erbij.
  De Werfverslag voorbereider leest ook het oude soort `werfbezoek` en het veld `projectnummer`.
- Zoektaak: bezoekmap gevalideerd uit de taak; tijdvenster bevestigt; alleen een datum vraagt eigen
  bewijs van de opname; levering bevestigd (`plaud_id:` bovenaan) vóór de taak op opgepakt gaat.

## Foutcodes

| Script | 0 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| `plaud_haal_alles.py` | alles gelukt | aanmelding ontbreekt of geweigerd | bron niet bereikbaar | een of meer opnames mislukt | al een ronde bezig |
| `plaud_wacht.py` | alles gelukt | | invoer ontbreekt of ouder dan 3 uur | een opname of publicatie mislukt | |

## Grendels (CI `plaud-grendels`)

- `tests/test_plaud_archief.py` (Python 3.9 en 3.12): contract, botsingen, afgekapte titels,
  hernoemde map, half geschreven map, `.deel`, wachtend transcript, verlopen link, id-conflict,
  file:/interne adressen/omleidingen, momentopname, foutcodes, manifest zonder links.
- `tests/test_plaud_wacht.py` (3.12): bron tot tabel, klaarzet en bezoekmap met een tweede ronde
  zonder dubbel; geforceerde fouten en hervatting; later toegevoegde bezoekmap; fout bij de tweede
  opname; conflict titel/kop; onbekende afdeling; HARC:9998 met een andere deal-id tot in de
  werfketen; context na teken 6000; ongeldige bezoekmappen; dezelfde dag is geen bevestiging; geen
  overschrijving; wachtend transcript; oude inbox is geen gezonde aanvoer; verouderde invoer;
  planning met slot en tijdslimiet; de oude Plaud-pull blijft weg.

## Wat Mehdi doet

Eén keer aanmelden bij Plaud op de Mac (het wachtwoord blijft bij hem):

    /usr/bin/python3 ~/dev/globaal-appportal/mijnagents-runner/plaud/plaud_login.py

Daarna loopt alles elk uur. Zolang de aanmelding ontbreekt, meldt De Plaudwacht dat als nood.

## Reconciliatie

`plaud/reconciliatie.py` schrijft `00 reconciliatie.md` in het archief: per Plaud-id gearchiveerd,
transcript wacht, onvolledig, metadata onvolledig, ontbreekt, mogelijke dubbel, oud VM-archief,
mogelijk verkeerd gekoppeld, plus de bordtaken met de opnames van die dag. Alleen lezen.

## Stand bij de uitrol (12-10-2026)

| Wat | Bewijs |
|---|---|
| Commits | `4f7cbb9` (keten), `c1ce954` (brug vanuit de koppeling), `9b453df` (bouwjaar is geen dossier) |
| VM | `git pull` naar `9b453df`; `test_plaud_archief`, `test_plaud_wacht`, `test_locatielezers` groen onder `~/agents/.venv` |
| VM-cron | beheerd blok `# >>> plaud`, `20 * * * *` met `flock -n` en `timeout 3000`; de oude regel zonder slot is vervangen |
| Mac-launchd | `be.globaal.plaud.ophalen`, elk uur op :05; eerste run: manifest gemaakt en doorgezet, foutcode 2 (aanmelding ontbreekt) |
| Archief | 822 opnames: 713 compleet, 109 wachten op transcript, 0 onvolledig, 0 id-conflicten |
| Aanvulling | 26 opnames van 25-09 tot 09-10 via de Plaud-koppeling gebouwd (`plaud/uit_koppeling.py`), alle compleet |
| Ronde 1 | 15 opnames sinds 01-10 herkend en gepubliceerd (gesprekkentabel en klaarzet), 0 fouten |
| Gevonden | "woning 1933" werd HARC:1933 voor h-architects; hersteld in `9b453df`, het item is bijgewerkt naar Mehdi zonder sleutel |
| Ronde 2 | 15 klaarzet-items, 15 uniek: geen dubbel; 14 opnames 0 nieuwe publicaties, het 1933-item bijgewerkt |
| Zoektaken | 6 open werftaken: 3 niet gevonden (geen eigen bewijs op de bezoekdag), 3 geweigerd (bezoekmap is een verzamelmap zonder bezoekdag) |
| Bord | werkwijze versie 3 gezet (vorige versie in de versiegeschiedenis); status "waakt"; noden: aanmelding Plaud (Mehdi), ongeldige bezoekmap (claude-code) |

Open:
- Mehdi meldt één keer aan bij Plaud (`plaud_login.py`); tot dan haalt de Mac niets nieuws en blijven de 109 wachtende transcripten staan.
- Voorstel voor de Werfverslag voorbereider: een bezoek dat alleen als los verslag in `4. Werfverslagen` of `1. Werf updates` bestaat, krijgt geen Plaud-taak met die verzamelmap als bezoekmap, maar een momentmap met de bezoekdag.
- Het verzoek van De Contractmaker (Nelleke Stropke, plaatsbezoek 2026-10-01) heeft geen bezoekmap; De Plaudwacht meldt het alleen.
- 6 mogelijke dubbels en de oude jaarmap `2026/` (4 opnames, ook in het hoofdarchief) staan in `00 reconciliatie.md`; niets verwijderd.

## Nacontrole v1.1 (12-10-2026, avond): wat hersteld is

| Punt | Herstel | Grendel |
|---|---|---|
| P1-2 bezoekmap buiten de dossiergrens | bezoekmap alleen bij `kopie_toegestaan`; afgewezen levering laat de taak open | `test_onbekende_afdeling_of_lage_zekerheid_blijft_bij_mehdi`, `test_tegenstrijdige_privevelden_leveren_niets` |
| P1-3 voorbereider zonder firma/privacy | `transcript_telt`: HARC plus nummer, bestemming h-architects, geen privé/conflict/laag; legacy alleen sleutel of titel | `test_voorbereider_telt_alleen_het_toegestane_harc_transcript` |
| P1-4 herhaald bouwjaar | zekerheid van de nummerlezer, titel+opening één bron, bekend dossier of gecontroleerde bron | `tests/test_plaud_dossier.py` |
| P1-5 correctie na oppakken | bord: `klaarzet_revisie` (opt-in `revisie: true`), uitvoerder leest de opgeslagen versie terug | `tests/test_plaud_revisie.py`, `mijnagents/test_klaarzet_revisie.py` (Docker-build) |
| P1-6 onbekende eigenaar | `archief.eigenaar`: map met bestanden zonder leesbare gesprek.json is niet vrij; herstel, niets geschreven | `test_bestaande_map_met_onbekende_eigenaar_is_niet_vrij` |
| P1-7 id-conflict | selectie, manifest (toestand conflict + herstel) en VM weigeren; nood | `test_id_conflict_wordt_niet_als_compleet_overgeslagen`, `test_id_conflict_in_het_manifest_publiceert_niets` |
| P2-8 beslisbronnen | modelvingerafdruk en beslisvingerafdruk apart; Pipedrive-uitval = onvolledig bewijs | `test_pipedrive_herstel_…`, `test_gewijzigde_titel_…` |
| P2-9 transcriptversie | `transcript_hash` in de kop; nieuwe versie naast de oude | `test_gewijzigd_transcript_wordt_als_nieuwe_versie_geleverd` |
| P2-10 onbekend JSON | alleen een lijst van uitingen met content en start_time; anders schemafout of leeg, met backoff | `test_onbekend_json_…`, `test_leeg_transcript_…` |
| P2-11 tokenrechten | `plaud/tokenbestand.py`: 0600 vanaf aanmaak, map 0700 | `test_token_is_altijd_0600_ook_tijdens_het_schrijven` |
| Agenda niet gezien | afspraken apart opvragen (`soort=afspraak`) | live: opname 1 oktober overlapt UNAB 46118 |
| Losse verslagen | Plaud-taak krijgt `<verzamelmap>/JJJJMMDD` als doel | `test_los_verslag_krijgt_een_gedateerde_momentmap_als_taakdoel` |
| Verzoek Contractmaker | alleen een opname die een afspraak met de klant overlapt; Mehdi bevestigt | `test_verzoek_van_de_contractmaker_vraagt_een_overlappende_afspraak` |

### Stand na de uitrol van de nacontrole (12-10-2026, 22:05)

| Wat | Bewijs |
|---|---|
| Commit | `3de1cdd` op GitHub, Mac en VM; CI groen (plaud-, locatie-, agenda-, nummer-, naamstructuurgrendels) |
| Bord | herbouwd door `deploy.sh` (tree 686d0d3), Docker-build met `test_klaarzet_revisie.py` groen; filters `uniek` en `soort` live; werkwijze 3.1 gezet |
| Ronde na uitrol | 15 opnames opnieuw beoordeeld, 0 fouten. Opname 1 oktober 09:31 = UNAB:46118 (overlappende afspraak Natasja Gerritsen, zekerheid middel) en gaat naar unabo. De andere 14 hebben geen dossier en staan bij Mehdi |
| Tweede ronde | 15 ongewijzigd, 15 items en 15 uniek: geen dubbel |
| Verzoek Stropke | niet gevonden: geen Plaud-opname rond de afspraak van 1 oktober 20:00-21:00 |
| 109 wachtende transcripten | opnieuw getoetst via de Plaud-koppeling: 2 hebben nu een transcript (11 augustus, 363 en 180 uitingen), bij 107 geeft Plaud nog geen transcript; archief 715 compleet en 107 wachtend |
| Werftaken | 3 niet gevonden (geen eigen bewijs op de bezoekdag). 3 wachten op de voorbereider (werkdagen vanaf 07:15 UTC), die als doel een gedateerde momentmap meegeeft |

Nog niet bewezen: een echte levering in een bezoekmap en een dossierkopie. Er is nog geen open taak met een opname die het dossierbewijs haalt. De automatische ophaling van een nieuwe opname vraagt eerst de aanmelding van Mehdi.
