# Plaud Agent: wat hij nu doet (v1.0, gemeten 17-09-2026)

Nulmeting vóór de verbeterronde. Alles hieronder is nagekeken op de VM, in Dropbox en in Plaud zelf.

## Twee helften

**1. De Plaud-routine (claude.ai, gepland).** Opdracht in `werkwijze/plaud-routine.md`. Bedoeld: twee keer per dag
(06:30 en 12:30) alle opnames van de laatste tien dagen ophalen, per opname het transcript (block `transaction`,
nooit de Plaud-samenvatting) als `<datum UUMM> Plaud transcript - <id>.md` in de Dropbox-inbox
`Work All/000 AI Opzet/Mehdi Agents/Plaud inbox` zetten, met kop `plaud_id / account / start (Belgische tijd) /
duur_minuten / naam_in_plaud / audio_url` (getekende link, 24 u geldig). Opnames zonder transcript in
`00 nog te transcriberen.md`. Sinds 14-09 ook: `00 gezocht.md` lezen (van de Werfverslag voorbereider) en per
bezoekdag de opname zoeken op `start_at`, tot een jaar terug, en het transcript met `dossier:` en `bezoekmap:`
in de kop wegzetten.

**2. De Plaudwacht (VM, `plaud_wacht.py`).** Cron elk uur op :20. Leest de inbox en elke map `0 Plaud` in de
salesmappen. Per nieuw bestand (Plaud-id nog niet in het archief):
- herkennen zoals de Fathomwacht: personentabel (uit de werkwijze van de Fathomwacht), agenda en locatie op de
  starttijd (uit de klaarzet-bak), Pipedrive-deals, en de openingszin van Mehdi in de eerste minuut;
- archiveren in `mijnagents-data/plaud/<jaar>/<JJJJ-MM-DD UUMM Hoofdpersoon>/` met `transcript.md`,
  `gesprek.json` en `opname.mp3` (opgehaald via `audio_url`); spiegel naar Mehdi's privé-Dropbox `/Plaud`;
- rij in de gesprekkentabel (bron `plaud`), klaarzetten voor de afdeling (of alleen Mehdi bij privé of onbekend),
  soort `werfbezoek` als het transcript daarop lijkt;
- kopie naar `0 Plaud` in de salesmap van de gekoppelde deal (nooit overschrijven);
- staat `bezoekmap:` in de kop, dan `transcript.txt` in die bezoekmap (regel E5);
- logboek en hartslag op het bord; nood als de inbox leeg is.

## Gemeten stand op 17-09-2026

| Wat | Gemeten |
|---|---|
| Geplande taken op Mehdi's account | alleen het ochtendoverzicht mail; **geen Plaud-routine** |
| Inbox | 4 transcripten, alle geschreven op 10-09 23:05 (eenmalige handmatige ronde) + `00 gezocht.md` |
| `00 nog te transcriberen.md` | bestaat niet |
| `00 gezocht.md` | 8 regels (2173, 2145, 2416 x3, 2324 x3), sinds 17-09 15:15, **niets beantwoord** |
| Plaud, opnames sinds 07-09 | 18; daarvan 14 nooit opgehaald (o.a. 12-09 inspectie 45 min, 14-09 conciërgewoning, 17-09 vergadering) |
| Archief op de VM | 4 gesprekmappen, elk met opname.mp3 (audio-keten werkt) |
| Plaudwacht-log | elk uur "4 bestanden, 0 nieuw"; hij draait, maar krijgt niets |

## Wat dat betekent

De achterkant (Plaudwacht, archief, audio, bezoekmap) staat en is getest op 4 opnames. De voorkant, de
claude.ai-routine, is nooit ingepland: sinds 10-09 komt er niets meer binnen, en de vraaglijst van de
werfverslagen blijft onbeantwoord. Elke verbetering begint dus met een aanvoer die niet van een handmatige
klik afhangt.

## Bekende zwaktes van het huidige ontwerp

1. **Aanvoer hangt aan claude.ai.** De VM kan Plaud niet bevragen; de routine moet Mehdi zelf inplannen en de
   desktop-app moet openstaan. Eén keer gedraaid, daarna stil.
2. **Tien-dagen-venster op uploaddatum.** Werfbezoeken die laat geüpload worden vallen erbuiten (les 2309).
   De gezocht-stap is een lapmiddel bovenop hetzelfde probleem.
3. **Zoeken in Plaud is beperkt.** `list_files` scant maximaal 500 opnames; naamprefix `MM-DD` werkt, datumfilter
   is op uploaddatum.
4. **Sprekers blijven "Speaker N"**; herkenning steunt op openingszin, agenda en locatie. Zonder openingszin is de
   zekerheid laag.
5. **Werfbezoek-detectie is een woordzoekactie** (`werf|plaatsbezoek|oplevering` in thema of eerste 800 tekens).
6. **Eén account.** Angela, Siyan en Shaniel zitten op hetzelfde Plaud-account; wie opnam wordt uit naam en tekst
   afgeleid.
7. **Bord-API vanaf de VM met het .env-token gaf 403** bij deze meting; logboek is alleen via het logbestand
   nagekeken.

## Bronnen
`mijnagents-runner/plaud_wacht.py`, `werkwijze/plaud-routine.md`, `werkwijze/plaud-wacht.md`,
`docs/Plaud-routine instellen (voor Mehdi).md`, cron op de VM, `/home/ubuntu/agents/plaud_wacht.log`,
Dropbox-inbox, Plaud `list_files` 07-09 t/m 17-09.
