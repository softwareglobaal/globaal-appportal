# De Agentnorm

Versie 1.0, 20-09-2026.

Elke agent wordt hieraan getoetst. Niet door iemand die vindt dat het goed zit,
maar door `controle_agenten.py`, dat meet en een exitcode teruggeeft.

```
python3 ~/appportal/mijnagents-runner/controle_agenten.py
python3 ~/appportal/mijnagents-runner/controle_agenten.py --agent agenda-wacht --uitleg
```

Waarom dit bestaat: op 20-09-2026 bleek de werkwijze van de Agendawacht in vier
versies tegelijk te bestaan (bord 476 regels, zaad in de repo 186, Dropbox 440,
GitHub 186). Welke sessie je ook aansprak, hij las andere regels en maakte daarom
telkens andere fouten. Zeventien commits met 1105 regels code stonden alleen op
de VM. Dat was geen domme AI, dat was een systeem zonder norm.

## 1. Waar de waarheid staat

Eén bron per soort gegeven. Wie iets anders leest, leest een kopie, en een kopie
veroudert altijd.

| gegeven | de waarheid | zo haal je het op | wat het niet is |
|---|---|---|---|
| wie hier werkt, afdelingen, firmacodes | schema `kern` in de appportal-Postgres | `koppelingen/organisatie.py`, of https://organisatie.globaal.be | een lijst met namen in een werkwijze |
| termen en definities | `kern.definitie` | `/woordenboek` op organisatie.globaal.be, `DEFINITIEBOEK.md` | een eigen definitie die een agent zelf verzint |
| de werkwijze van een agent | het bord: `mijnagents.db`, tabel `agent`, kolom `werkwijze` | `GET /api/agent/<naam>/werkwijze` | het zaad in `werkwijze/<naam>.md`, dat is alleen de eerste versie |
| de code | GitHub `softwareglobaal/globaal-appportal`, branch `main` | `git pull --rebase origin main` | de kopie op de VM, die kan vooruit of achter lopen |
| wat een agent deed en vond | `mijnagents-data` op de VM | de export in Dropbox, `Data uit Mehdi/<Agent>/` | wat er in een chatgesprek staat |
| sleutels | `~/appportal/.env` op de VM | nergens anders, nooit tonen | git, chat, documentatie, een werkwijze |

Twee regels die hieruit volgen:

- **Markdown voor wat een mens leest, JSON voor wat een programma schrijft.** Een
  Markdown-tabel die door een script wordt bijgehouden slibt dicht. Dat is precies
  hoe `noden.md` van de Agendawacht dertig identieke regels kreeg.
- **Wie een kopie maakt, is verantwoordelijk voor het verschil.** Kan een kopie
  niet gelijk blijven, dan hoort ze er niet te zijn.

## 2. De negen normen

| norm | de eis | waarom, en waar het misging |
|---|---|---|
| **N1** | Werkwijze op het bord, minstens 500 tekens | Een agent zonder werkwijze doet maar wat, en niemand kan nakijken of hij zich eraan hield. |
| **N2** | De werkwijze zegt wat hij **nooit** doet en wat **Mehdi beslist** | Zonder grens doet een agent vroeg of laat iets onomkeerbaars. De Agendawacht hernoemde op 19-09 een agenda naar ZZ ARCHIEF; tien andere accounts zagen die naam meteen. |
| **N3** | Rol, cadans, mandaat, mag en grenzen staan ingevuld op het bord | Dit is zijn kaart. Wat er niet op staat, kan niemand controleren. |
| **N4** | Hij meldde de laatste zeven dagen welk regelboek hij las (`kennis`) | Dit is de enige manier om achteraf te weten welke versie van de regels hij gebruikte toen hij de fout maakte. Vandaag doet alleen de contracten-agent dit; 27 agents laten het veld leeg. |
| **N5** | Er is een runner-bestand met zijn naam | Een agent op het bord zonder code is een belofte, geen agent. |
| **N6** | Het zaad in `werkwijze/` is gelijk aan het bord, of het ontbreekt | Het bord is de waarheid. Een afwijkend zaad is een tweede waarheid, en die leest iemand vroeg of laat per ongeluk. |
| **N7** | Geen nood die langer dan drie dagen open staat | Een nood die blijft terugkomen is geen melding meer maar ruis. De Agendawacht meldde dertig keer dezelfde nood over titels zonder code, zette hem telkens op opgelost, en meldde hem twee uur later opnieuw, omdat hij wachtte op een runbook dat niemand bouwde. |
| **N8** | Geen sleutel, token of wachtwoord in de werkwijze | Een werkwijze wordt geëxporteerd naar Dropbox en gelezen door elke sessie. |
| **N9** | Geen gedachtestreepjes in de werkwijze | Afspraak van 04-07-2026. Teksten horen menselijk te lezen. |

Een norm die niet van toepassing is (een agent die op de Mac draait heeft geen
runner in deze repo) telt niet mee en wordt als `n.v.t.` gemeld.

## 3. De nulmeting van 20-09-2026

28 actieve agents, 53 gezakte normen. Eén agent slaagde voor alles: de
contracten-agent. De meest voorkomende gaten:

- **N4 bij 27 van de 28.** Agents melden niet welk regelboek ze lazen.
- **N7 bij dertien agents.** Noden die tot tien dagen open staan zonder besluit.
- **N6 bij vier agents** (belwacht, fathom-wacht, werfverslag-voorbereider,
  zoom-wacht): het zaad in de repo wijkt af van het bord.
- **N5 bij twee agents** (belwacht, communicatie-bundelaar): op het bord, maar
  zonder eigen runner.

Dat is de lijst om af te werken, niet een reden om de norm te verlagen.

## 4. Wat je doet als een norm faalt

1. **Herstel in de bron, niet in het geval.** Een fout in één werkwijze los je op
   in het sjabloon of in de code, zodat elke volgende agent het goed heeft.
2. **Zet er een grendel op.** Een afspraak die stilzwijgend kan sneuvelen krijgt
   een test. Zie `tests/test_agenda_archief.py` en `tests/test_agenda_taken.py`:
   die falen zodra iemand de grendel weghaalt of de regels en de code uit elkaar
   laat lopen.
3. **Verlaag de norm alleen in dit document.** Wie een norm te streng vindt, past
   hem hier aan en in `controle_agenten.py`, nooit het geval dat toevallig faalt.

## 5. Een nieuwe agent die meteen slaagt

```
python3 ~/appportal/mijnagents-runner/nieuwe-agent.py --naam post-wacht --label "Postwacht" \
  --type h-architects --rol "sorteert nieuwe post op info@" --cadans "elk uur" \
  --mag "post labelen" --grens "nooit verwijderen" --werkwijze werkwijze/post-wacht.md
```

De werkwijze die je meegeeft moet zelf al door N1, N2, N8 en N9 komen. Daarna:

- laat de runner elke ronde melden wat hij las (N4);
- laat hem noden schrijven met een eigenaar en een besluit, niet als logregel (N7);
- draai `controle_agenten.py --agent <naam> --uitleg` voor je hem op de cron zet.

## 6. De chatkant

Een agent die Mehdi ook in een gesprek aanspreekt, hoort een skill te hebben in
`~/.claude/skills/<naam>/SKILL.md` op zijn Mac. Die skill wordt automatisch
geladen zodra het onderwerp valt, wijst naar de bron hierboven en draagt de
valkuilen. Zonder skill begint elke sessie blanco en moet Mehdi alles opnieuw
uitleggen. Vandaag bestaan `werfverslag` en `agendawacht`.

Een skill vervangt de werkwijze niet en herhaalt haar niet: ze wijst ernaar.
Twee teksten met dezelfde inhoud lopen altijd uit elkaar, zie N6.
