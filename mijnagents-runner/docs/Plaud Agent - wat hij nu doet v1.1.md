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
