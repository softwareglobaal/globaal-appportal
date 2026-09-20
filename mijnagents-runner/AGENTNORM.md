# De Agentnorm

Versie 1.4, 20-09-2026 (N12 en het minimum: de gedeelde ronde; v1.3 het woord stil in een signaaltitel belt Mehdi op; v1.2 N11 hartslag, en hoe een agent Mehdi bereikt nu zijn laptop 's ochtends slaapt; v1.1 N10, S1, de Normwacht en het logboek; v1.0 dezelfde dag).

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

## 2. De twaalf normen

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
| **N10** | Een nood draagt geen aantal in zijn tekst | Noden zijn declaratief: elke ronde stuurt een agent de hele lijst, en wat er niet meer in staat geldt als opgelost. Staat er een teller in de tekst ("11 afspraken zonder code"), dan is elke ronde formeel een nieuwe nood en sluit de lus nooit. Zo verzamelde de Agendawacht dertig identieke regels. Het aantal hoort in het detail. |

| **N11** | Verse hartslag, niet in fout en niet vastgelopen | Zes agents draaien op de Mac van Mehdi. Slaapt die laptop, dan gaat hun ronde niet door en merkt niemand het. Op 20-09-2026 stonden acht agents stil zonder dat iemand het wist: het commandocentrum 39 uur (cadans: elk kwartier), de dagbundelaar 54 uur, de wisprwacht zestien uur op fout, de icloudwacht achttien uur vastgelopen in dezelfde ronde. Stil vallen mag, ongemerkt stil vallen niet. |

| **N12** | De runner gaat door de gedeelde ronde (`with ag.ronde(...)`) | Dit is het minimum. Wie zijn eigen doorgang bouwt vergeet er altijd een: gemeten op 20-09-2026 haalden vier van de 39 runners hun werkwijze van het bord op, en meldde er precies een welk regelboek hij las. De werkwijze was voor de rest decoratie: een tekst die beschrijft wat de code zou moeten doen, die niemand naast de code legt. |

### De omgeving

| norm | de eis | waarom |
|---|---|---|
| **S1** | De VM staat niet voor of achter op GitHub | Op 20-09-2026 stonden zeventien commits alleen op de VM, en een paar uur later alweer een nieuwe. Werk dat maar op één schijf bestaat is geen werk, het is een risico. Deze toets draait niet per agent maar één keer per ronde. |

Een norm die niet van toepassing is (een agent die op de Mac draait heeft geen
runner in deze repo) telt niet mee en wordt als `n.v.t.` gemeld.

## 3. De nulmeting van 20-09-2026

28 actieve agents, 56 gezakte normen. Eén agent slaagde voor alles: de
contracten-agent. De meest voorkomende gaten:

- **N4 bij 27 van de 28.** Agents melden niet welk regelboek ze lazen.
- **N7 bij twaalf agents.** Noden die tot tien dagen open staan zonder besluit.
- **N6 bij zes agents**: het zaad in de repo wijkt af van het bord.
- **N2 bij vijf agents**: de werkwijze zegt niet wat Mehdi beslist.
- **N5 bij twee agents** (belwacht, communicatie-bundelaar): op het bord, maar
  zonder eigen runner.
- **N10 bij twee agents** (agenda-wacht, locatie-wacht): noden met een teller
  in de tekst.

Dit is regel één van het logboek. Elke volgende meting komt eronder, zodat je
ziet of we vooruit gaan of alleen praten.

Dat is de lijst om af te werken, niet een reden om de norm te verlagen.

## 4. De Normwacht en het logboek

`normwacht.py` doet elke ochtend om 06:10 een ronde, vóór de meeste agents aan
hun werk beginnen. Hij raakt geen enkele andere agent aan. Hij meet, en:

- **schrijft het logboek.** `mijnagents-data/agentnorm/logboek.jsonl` is de
  machinekant (één regel per meting, nooit overschreven), `logboek.md` de
  leesbare kant: waar we gestart zijn, waar we nu staan, en per norm hoeveel
  agents er nog zakken. Dat bestand komt via de export ook in Dropbox.
- **zet per gezakte norm één nood op het bord**, met een eigenaar erbij: wat een
  mens moet beslissen gaat naar Mehdi, wat code is naar claude-code. Zeven noden
  in plaats van 56 losse meldingen, en de tekst blijft morgen gelijk, zodat je
  ziet of iets echt is opgelost of alleen opnieuw gemeld.

```
normwacht.py --droog      meten en tonen, niets naar het bord schrijven
```

Zo komt hij terug tot het klopt, zonder dat iemand het hoeft te onthouden.

## 5. Het minimum: de ronde

Elke agent gaat door dezelfde doorgang, `Ronde` in `koppelingen/bord.py`. Wie
die gebruikt haalt N4, N10 en N11 vanzelf, zonder eraan te denken:

```python
import bord
ag = bord.Agent("post-wacht")

with ag.ronde("post sorteren") as r:
    regels = r.werkwijze                      # de tekst zoals ze nu op het bord staat
    r.bron("sorteerregels.json", open(pad).read())
    ...
    r.nood("Postvak niet leesbaar", wie="claude-code")
    r.detail = f"{n} berichten bekeken"
```

Wat de ronde zelf doet:

| bij het begin | bij het einde |
|---|---|
| hartslag op "actief" met de taak | hartslag op "klaar", of "waakt" als er noden zijn |
| de werkwijze van het bord ophalen en doorgeven als `r.werkwijze` | melden welke regelboeken hij las, met een vingerafdruk van acht tekens per bron (N4) |
| | het werkverslag versturen |
| | breekt de ronde, dan hartslag "fout" met de foutmelding, nooit blijven hangen op "actief" (N11) |

`r.nood()` haalt een aantal vooraan uit de tekst weg en weigert dubbels, zodat
dezelfde nood morgen dezelfde nood is (N10). Het aantal zet je in `r.detail`.

`tests/test_agentnorm.py` faalt zodra iemand deze doorgang weghaalt of uitholt,
en ook als het sjabloon hem niet meer gebruikt. Acht toetsen, allemaal groen op
20-09-2026.

## 6. Hoe een agent Mehdi bereikt

Zijn laptop slaapt 's nachts en vroeg in de ochtend. Een melding op een scherm
dat uit staat is geen melding. Drie kanalen, van zacht naar hard:

| kanaal | hoe | waarvoor |
|---|---|---|
| het bord | `hartslag(..., nood=[...])` | alles wat kan wachten tot hij kijkt |
| Telegram | een klaarzet-item met `soort: signaal` en `voor: mehdi`; De Bode bundelt en stuurt | wat hij vandaag moet weten |
| bellen (Twilio) | `koppelingen/bellen.py`, De Bode belt | alleen wat op een tijdstip moet gebeuren, zoals het belrooster van de Agendawacht |

**Een nood alleen op het bord bereikt hem niet.** De Bode stuurt klaarzet-items
en voorstellen door, geen noden. Wie wil dat Mehdi iets ziet, zet een signaal.

**Het woord "stil" in een signaaltitel belt hem op.** De Bode leest een signaal
met "stil" erin als alarm en start een gesproken oproep via Twilio, herhaald tot
er wordt opgenomen, ook in de stille uren (`alarm = [... if "stil" in titel]` in
`bode.py`). Gemeten op 20-09-2026: de eerste ronde van de Normwacht meldde "39
uur stil" en belde Mehdi daarop op. Een agent die niet draait is geen alarm; dat
heet nu "geen hartslag". Bellen blijft voor wat op een tijdstip moet gebeuren.

Geef elk signaal een `uniek` zonder aantallen erin, om dezelfde reden als N10:
anders komt hetzelfde bericht elke ronde opnieuw. De Normwacht gebruikt
`normwacht-stilte-<agent>-<fout|stil|vastgelopen>`, zodat een agent die weer
draait vanzelf uit de meldingen verdwijnt.

## 7. Wat je doet als een norm faalt

1. **Herstel in de bron, niet in het geval.** Een fout in één werkwijze los je op
   in het sjabloon of in de code, zodat elke volgende agent het goed heeft.
2. **Zet er een grendel op.** Een afspraak die stilzwijgend kan sneuvelen krijgt
   een test. Zie `tests/test_agenda_archief.py` en `tests/test_agenda_taken.py`:
   die falen zodra iemand de grendel weghaalt of de regels en de code uit elkaar
   laat lopen.
3. **Verlaag de norm alleen in dit document.** Wie een norm te streng vindt, past
   hem hier aan en in `controle_agenten.py`, nooit het geval dat toevallig faalt.

## 8. Een nieuwe agent die meteen slaagt

```
python3 ~/appportal/mijnagents-runner/nieuwe-agent.py --naam post-wacht --label "Postwacht" \
  --type h-architects --rol "sorteert nieuwe post op info@" --cadans "elk uur" \
  --mag "post labelen" --grens "nooit verwijderen" --werkwijze werkwijze/post-wacht.md
```

De werkwijze die je meegeeft moet zelf al door N1, N2, N8 en N9 komen. Daarna:

- laat de runner elke ronde melden wat hij las (N4);
- laat hem noden schrijven met een eigenaar en een besluit, niet als logregel (N7);
- draai `controle_agenten.py --agent <naam> --uitleg` voor je hem op de cron zet.

## 9. De chatkant

Een agent die Mehdi ook in een gesprek aanspreekt, hoort een skill te hebben in
`~/.claude/skills/<naam>/SKILL.md` op zijn Mac. Die skill wordt automatisch
geladen zodra het onderwerp valt, wijst naar de bron hierboven en draagt de
valkuilen. Zonder skill begint elke sessie blanco en moet Mehdi alles opnieuw
uitleggen. Vandaag bestaan `werfverslag` en `agendawacht`.

Een skill vervangt de werkwijze niet en herhaalt haar niet: ze wijst ernaar.
Twee teksten met dezelfde inhoud lopen altijd uit elkaar, zie N6.
