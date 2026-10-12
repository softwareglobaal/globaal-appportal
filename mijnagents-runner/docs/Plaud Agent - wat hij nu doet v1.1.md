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
