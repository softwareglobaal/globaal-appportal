# Plaud Agent: eigen ophaalroute en mapindeling (v1.0, 17-09-2026)

Besluiten van Mehdi op 17-09-2026, en wat er die avond gebouwd is. Lees eerst
`Plaud Agent - wat hij nu doet v1.0.md`: dat is de nulmeting waar dit op volgt.

## Wat Mehdi besliste

1. **Alles binnenhalen.** Het volledige Plaud-archief komt in Dropbox, niet alleen de laatste tien dagen.
2. **Geen jaarmap meer.** De mappen staan plat in `Data uit Mehdi/Plaud/`; de datum vooraan
   rangschikt zichzelf. De map `2026/` vervalt.
3. **De naam van Plaud blijft staan.** De mapnaam is `JJJJ-MM-DD UUMM <naam in Plaud>` in Belgische
   tijd, niet meer de naam van de hoofdpersoon.

## De mapnaam, precies

`mapnaam.py` maakt hem:

- Datum en uur uit `start_at`. Plaud levert UTC; wij rekenen om naar Europe/Brussels (zomer +2, winter +1).
- Plaud zet zelf `MM-DD ` voor zijn titels; dat voorvoegsel gaat eraf, het is dubbel met de datum.
- Tekens die Dropbox of macOS niet in een mapnaam willen (`: / \ * ? " < > |`) worden een spatie.
- Een opname zonder eigen titel heet in Plaud alleen een tijdstempel; die map heet `... zonder titel`.
- Langer dan 110 tekens wordt afgekapt.

Voorbeeld: `2026-09-16 1521 Vergadering Keuze en plaatsing nieuwe voordeur Bittawiri straat`.

In elke map: `transcript.md` (leesbaar, `[uu:mm:ss] Speaker N: tekst`), `transcript.json` (de ruwe
uitingen van Plaud, de bron), `gesprek.json` (metadata) en `opname.ogg` of `.mp3` (de geluidsopname).
De samenvatting van Plaud halen we niet op; afspraak D7 blijft staan.

## De nieuwe ophaalroute: rechtstreeks, zonder claude.ai

Tot nu hing alles aan een geplande Claude-taak op claude.ai, en die was nooit ingepland. Dat hoeft
niet meer. Plaud heeft een eigen API die het account kan uitlezen, dezelfde die de officiële
Plaud-CLI en hun MCP-server gebruiken:

| Wat | Waar |
|---|---|
| Basis | `https://platform.plaud.ai/developer/api` |
| Lijst | `GET /open/third-party/files/?page=N&page_size=100` |
| Eén opname | `GET /open/third-party/files/<id>` → `presigned_url` (audio, 24 u) en `source_list` met `data_link` per blok (transcript, 1 u) |
| Aanmelden | OAuth met PKCE: `https://web.plaud.ai/platform/oauth`, token op `/oauth/third-party/access-token` |

De client-id is die van de publieke Plaud-CLI; er is geen geheim nodig. Het toegangsbewijs komt in
`~/.config/plaud/token.json` (alleen leesbaar voor Mehdi) en staat nergens in code of documentatie.

Let op: dit is een ander spoor dan `PLAUD_CLIENT_ID` / `PLAUD_API_KEY` op de VM. Die twee zijn voor
de **transcriptie**-API (audio erin, tekst eruit, voor Xelion-gesprekken) en geven geen toegang tot
het archief van het account. Gemeten op 17-09: elk leesverzoek met die sleutels geeft 404.

## De scripts (`mijnagents-runner/plaud/`)

| Script | Wat het doet |
|---|---|
| `plaud_login.py` | Eenmalige aanmelding. Toont een link, vangt de terugkeer op poort 8199, bewaart het bewijs. Mehdi logt zelf in; er gaat geen wachtwoord door het script. |
| `plaud_haal_alles.py` | Haalt de lijst en per opname de map. Slaat over wat al compleet is, dus opnieuw draaien mag. `--max N` voor een proef, `--lijst` om alleen te tellen. |
| `bouw_map.py` | Bouwt één map uit de links: audio en transcript via `curl` (de systeem-Python op de Mac heeft geen bruikbare rootstore). |
| `mapnaam.py` | De naamregel hierboven. |
| `controle.py` | Meet of het archief volledig is en schrijft `00 index.md` in de Plaud-map. |

## Omvang, gemeten op 17-09-2026

| | |
|---|---|
| Opnames in Plaud | 773 |
| Oudste | 28-08-2025 |
| Nieuwste | 17-09-2026 |
| Audio samen | 751 uur |
| Schijfruimte | ongeveer 11,3 GB (gemeten 15 MB per uur) |

Daarom staat het archief op de **Mac** in Dropbox en niet op de VM: die zat op 17-09 op 98 % vol,
met 2,1 GB vrij.

## Wat hierna nog moet

1. **De Plaudwacht meeverhuizen.** `plaud_wacht.py` schrijft nog naar `mijnagents-data/plaud/<jaar>/`
   met de hoofdpersoon in de mapnaam. Zolang dat zo is, botst hij met de nieuwe indeling.
2. **De sync omdraaien.** `~/bin/data_uit_mehdi_sync.sh` haalt elk half uur de VM-map naar Dropbox en
   zet zo `Plaud/2026/` terug. Zodra de Plaudwacht mee is, moet de Mac leidend zijn voor Plaud.
3. **Opruimen.** De vier mappen in `Plaud/2026/` zijn dezelfde gesprekken onder de oude naam. Ze
   mogen weg zodra de nieuwe mappen compleet zijn; dat is Mehdi's ja.
4. **De claude.ai-routine uitzetten.** Die is met deze route overbodig. Wel blijft `00 gezocht.md`
   nuttig: de werfverslag-voorbereider kan nu rechtstreeks in het volledige archief zoeken.
