# De Agentnorm

Versie 1.15, 23-10-2026: een agent met cadans exact `op verzoek` houdt na een geslaagde ronde zijn kennis en eindhartslag geldig tot de volgende vraag. Bij WhatsApp-wacht moeten de kennistekst en de laatste eindhartslag dezelfde ronde-ID dragen; een fout of vastgelopen actieve ronde blijft zichtbaar.

Versie 1.14, 22-10-2026 (RZ4-03, RZ4-05 en RZ4-07: De Bode telt een bericht pas als gelezen als het verstuurd is of in een bundel zit, ook onder de eerste pagina van het bord; een agent met geplande taken past zijn grenzen toe voor de taakloper; de werkwijzen van De Bode, De Regisseur en De Zoomwacht gaan alleen als voorstel naar het bord; v1.13 dezelfde dag, RZ3-01 en RZ3-02: privé is ook een gesprek met afdeling prive, bij elke agent en lezer, en de stand van BUNDELEN staat als vaste regel in de werkwijze van De Bode, niet meer in de code; v1.12 dezelfde dag, RZ2-01: een privégesprek draagt ook in het klaarzet-item, de bundel van De Dagbundelaar en de export van het bord geen naam of onderwerp, bij De Fathomwacht en De Plaudwacht; v1.11 21-10-2026 BAS-01: het werkverslag draagt geen privé, van een privégesprek staat er alleen wanneer en hoe lang, en De Regisseur filtert wat hij leest; bij een omschakeling van BUNDELEN verdwijnt niets; v1.10 dezelfde dag, ontwerp regie-zoom v1.2, G2 en L7: De Regisseur en De Zoomwacht lezen hun regels niet meer als leeg bij onbekend; een signaal voor Mehdi komt op een vast moment, het ochtendbericht of de avondbundel; een nood voor Mehdi bereikt hem in het ochtendbericht; een agent aanspreken met "Naam, vraag"; de ronde neemt noden van voor de ronde mee en sluit ook bij een stopsignaal af; db_lees is de enige leesweg naar de databank van het bord; v1.9 16-10-2026 NA08 en NA09 in de code: zonder regelboek geen ronde, en de generator controleert eerst en geeft de cron pas na een gecontroleerde eerste ronde; v1.8 16-10-2026 hoofdstuk 8: van idee tot live, controle voor registratie en actief pas na een gecontroleerde eerste ronde; v1.7 26-09-2026 een agent die Mehdi wil laten bellen, zet een oproep klaar; v1.6 25-09-2026 N14: elke agent kent zijn collega's, levend van het bord; v1.5 24-09-2026 N13 en het gedeelde lessenboek: wat een agent leert, leest elke agent; v1.4 20-09-2026 N12 en het minimum: de gedeelde ronde; v1.3 het woord stil in een signaaltitel belt Mehdi op; v1.2 N11 hartslag, en hoe een agent Mehdi bereikt nu zijn laptop 's ochtends slaapt; v1.1 N10, S1, de Normwacht en het logboek; v1.0 dezelfde dag).

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

Werkwijze sinds 31-10-2026: eerst een slimme agent, pas een programma als een stap stabiel en bekend is. Zie `docs/werkwijze-eerst-agent-dan-programma.md`.

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

## 2. De normen

| norm | de eis | waarom, en waar het misging |
|---|---|---|
| **N1** | Werkwijze op het bord, minstens 500 tekens | Een agent zonder werkwijze doet maar wat, en niemand kan nakijken of hij zich eraan hield. |
| **N2** | De werkwijze zegt wat hij **nooit** doet en wat **Mehdi beslist** | Zonder grens doet een agent vroeg of laat iets onomkeerbaars. De Agendawacht hernoemde op 19-09 een agenda naar ZZ ARCHIEF; tien andere accounts zagen die naam meteen. |
| **N3** | Rol, cadans, mandaat, mag en grenzen staan ingevuld op het bord | Dit is zijn kaart. Wat er niet op staat, kan niemand controleren. |
| **N4** | Hij meldde de laatste zeven dagen welk regelboek hij las (`kennis`); bij cadans exact `op verzoek` volstaat kennis van de laatste ronde. Voor WhatsApp-wacht moet dezelfde ronde-ID in kennistekst en eindhartslag staan | Dit is de enige manier om achteraf te weten welke versie van de regels hij gebruikte toen hij de fout maakte. Een agent op verzoek krijgt zonder nieuwe vraag geen nieuwe ronde; bij WhatsApp-wacht mag oude kennis een latere ronde niet groen maken. |
| **N5** | Er is een runner-bestand met zijn naam | Een agent op het bord zonder code is een belofte, geen agent. |
| **N6** | Het zaad in `werkwijze/` is gelijk aan het bord, of het ontbreekt | Het bord is de waarheid. Een afwijkend zaad is een tweede waarheid, en die leest iemand vroeg of laat per ongeluk. |
| **N7** | Geen nood die langer dan drie dagen open staat | Een nood die blijft terugkomen is geen melding meer maar ruis. De Agendawacht meldde dertig keer dezelfde nood over titels zonder code, zette hem telkens op opgelost, en meldde hem twee uur later opnieuw, omdat hij wachtte op een runbook dat niemand bouwde. |
| **N8** | Geen sleutel, token of wachtwoord in de werkwijze | Een werkwijze wordt geëxporteerd naar Dropbox en gelezen door elke sessie. |
| **N9** | Geen gedachtestreepjes in de werkwijze | Afspraak van 04-07-2026. Teksten horen menselijk te lezen. |
| **N10** | Een nood draagt geen aantal in zijn tekst | Noden zijn declaratief: elke ronde stuurt een agent de hele lijst, en wat er niet meer in staat geldt als opgelost. Staat er een teller in de tekst ("11 afspraken zonder code"), dan is elke ronde formeel een nieuwe nood en sluit de lus nooit. Zo verzamelde de Agendawacht dertig identieke regels. Het aantal hoort in het detail. |
| **N11** | Verse hartslag, niet in fout en niet vastgelopen; bij cadans exact `op verzoek` veroudert een laatste `klaar` of `waakt` niet | Een agent op verzoek draait pas na een nieuwe vraag. Een ontbrekende hartslag, fout of vastgelopen actieve ronde blijft altijd een probleem. |
| **N12** | De runner gaat door de gedeelde ronde (`with ag.ronde(...)`) | Dit is het minimum. Wie zijn eigen doorgang bouwt vergeet er altijd een: gemeten op 20-09-2026 haalden vier van de 39 runners hun werkwijze van het bord op, en meldde er precies een welk regelboek hij las. De werkwijze was voor de rest decoratie: een tekst die beschrijft wat de code zou moeten doen, die niemand naast de code legt. |
| **N13** | Hij las in zijn laatste ronde de gedeelde lessen (`werkwijze/lessen.json`) | Wat een agent leert, hoort elke agent te weten. Tot 24-09-2026 had alleen de Agendawacht een foutenregister (47 fouten, 14 lessen) en las geen enkele andere agent het. Dezelfde dag stelde de werfverslag-voorbereider voor om "dubbele rijen op te ruimen" van dossier 2145, en Mehdi las dat als "2145 verwijderen", terwijl het net het eerste testdossier van het nieuwe communicatiesysteem is. Die les (L15: zeg eerst wat blijft) gold voor elke agent die voorstellen schrijft, en niemand anders kende ze. De ronde leest de lessen nu mee als bron; deze toets kijkt of ze in de gemelde kennis van de agent staan. |
| **N14** | Hij las in zijn laatste ronde de lijst van actieve collega's van het bord | Mehdi, 25-09-2026: "zorg ervoor dat alle agents van elkaar op de hoogte zijn, en dat is momenteel niet het geval". Tot die dag wist geen agent wie er nog meer draaide, dus zette niemand iets klaar voor een collega die het beter kon, en vroeg elke agent alles aan Mehdi. De ronde haalt de lijst elke ronde levend van het bord (`/api/agents`), nooit uit een kopie, en geeft ze door als `r.collegas`; een taalmodel-agent krijgt `bord.collega_tekst(r.collegas)` in zijn opdracht. Hoort iets bij een collega, dan zet hij het voor die agent klaar (`klaarzet`, `voor: <naam>`). |

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
| is de werkwijze onbekend (bord onbereikbaar, geen toegang, niet op het bord, onleesbaar) of leeg, dan stopt de ronde voor het werk begint: een nood, hartslag "fout" en `RondeGestopt` | |
| de gedeelde lessen lezen (`r.lessen`, N13) en de collega's van het bord (`r.collegas`, N14) | |
| | het werkverslag versturen |
| | breekt de ronde, dan hartslag "fout" met de foutmelding, nooit blijven hangen op "actief" (N11); noden die al open stonden blijven open. Dat geldt ook voor een stopsignaal (SIGTERM van een time-out, Ctrl-C), ook terwijl de ronde nog begint |

**Zonder regelboek geen ronde** (Codex NA09, 16-10-2026). Tot dan gaf een leesfout
een lege werkwijze en werkte de agent gewoon door, zonder dat iemand het zag.
Onbekend is niet leeg: kon het bord de werkwijze niet geven, dan krijgt de agent de
nood "Werkwijze niet gelezen: <reden>" (voor claude-code); is ze leeg, dan "Werkwijze
leeg op het bord" (voor Mehdi). De hartslag "fout" laat N11 en de Normwacht het zien.
Er gaat geen kennis mee, want er is niets gelezen, en de noden die al open stonden
blijven open: of die intussen opgelost zijn, weet deze ronde niet. Dezelfde regel
geldt in `ag.werkwijze()`, waarmee vier oudere runners (agenda-wacht, archivaris,
fathom-wacht, levenscoach) hun werkwijze nog buiten de ronde lezen: ook hun werk
stopt (Codex NA11). Ze horen alsnog door de ronde te gaan.

Open, gemeten op 16-10-2026 en opnieuw op 21-10-2026: vier plekken lezen een werkwijze
nog met eigen code en maken van onbekend een lege tekst: `contracten_agent.py`
(`werkwijze_van_bord`), `plaud_wacht.py` (de personentabel van fathom-wacht),
`mac/mail_wacht.py` en `zelfcontrole.py`. Die horen `ag.werkwijze()` of
`werkwijze_lezen()` te gebruiken. Sinds 21-10-2026 (ontwerp regie-zoom v1.2) niet meer
`regisseur.py`, die zijn eigen werkwijze als `r.werkwijze` uit de ronde leest en een
onleesbare werkwijze van een andere agent als onbekend meldt, en niet meer
`zoom_wacht.py`, die de personentabel van fathom-wacht met `werkwijze_lezen()` leest:
is die onbekend, dan volgt een nood en is elke sessie met een onbekende privé. En weet de ronde de open
noden niet, dan stuurt ze geen lijst; de nieuwe nood staat dan alleen in het
detail van de fouthartslag. Een nood toevoegen zonder de lijst te vervangen,
vraagt een route op het bord (Codex NA16).

Een runner op de Mac kan ook door de ronde (sinds 19-10-2026, De Tekenaar, `tekenaar.py`). De publieke ingang van
het bord laat alleen hartslag, klaarzet, gesprekken en logboek door, niet de werkwijze, de kennis, de noden of de
collega's. Daarom praat zo'n runner met het bord via een ssh-tunnel naar 127.0.0.1:3022 op de VM, met het token uit
`~/.config/mijnagents/token`, en vraagt hij na de ronde met `koppelingen/bordstand.py` (alleen lezen) of hartslag en
kennis echt aankwamen. Zijn runner staat in deze repo, dus meet de controle ook N5 en N12 tot N14. De oudere
Mac-wachten in `mac/` doen dat nog niet.

Een werkwijze die alleen gelezen wordt, is decoratie. `bord.grenzen(r.werkwijze)` geeft
de punten onder "## Wat ik nooit doe" en "## Wat Mehdi beslist", zodat de code de
grenzen van het bord toepast en geen kopie bijhoudt. Het sjabloon toont het: zonder
die grenzen in de vaste vorm (hoofdstuk 8) doet het geen werk en meldt het een nood.
Een agent die geplande taken uitvoert, kijkt zijn grenzen na voor de taakloper, niet
erna (RZ4-05, 22-10-2026): De Regisseur voert zonder beide grenssecties, met een lege
of een onleesbare werkwijze geen enkele geplande taak uit (geen agent-ronde, geen
poging); een ronde meldt de nood, alleen lezend. Tot dan liep `taken_uitvoeren` eerst,
zoals het ontwerp het voorschreef, en gold de alleen-lezenstand niet voor zijn taken.

`r.nood()` haalt een aantal vooraan uit de tekst weg en weigert dubbels, zodat
dezelfde nood morgen dezelfde nood is (N10). Het aantal zet je in `r.detail`.

Noden die een agent al heeft voor zijn ronde begint, zoals De Bode met het bellen en
het alarm, geeft hij mee als `ag.ronde(taak, begin_noden=[{"tekst": ..., "wie": ...}])`
(sinds 21-10-2026, ontwerp regie-zoom X4). Ze staan in de ronde alsof ze met `r.nood()`
gemeld zijn, en gaan ook mee als de ronde stopt omdat het regelboek ontbreekt.

Wie rechtstreeks uit de databank van het bord leest, doet dat langs een weg: `bord.db_lees(sql, args)`,
alleen lezend (mode=ro en query_only), alleen een vraag die met SELECT of WITH begint.
Een fout geeft `bord.BordOnbekend` met een reden, nooit een lege lijst: wie dat
opvangt, zegt onbekend. Schrijven gaat altijd via de API van het bord, en teruglezen
met `db_lees` is het bewijs dat iets echt staat.

**Het werkverslag draagt geen privé** (BAS-01, 21-10-2026). Wat een agent met `ag.log` schrijft,
leest een taalmodel mee: het dossier en de tool `agent_verslag` van De Regisseur, en De
Ontwikkelaar. Van een privégesprek of een privébron staat er alleen wanneer, hoe lang en het
woord privé; met wie, waarover en waarom blijven in het archief (M3, ontwerp regie-zoom 13.2).
Het masker van het bord (`ag.prive()`) vangt alleen wat een agent aanmeldt; wat hij niet
aanmeldt, gaat er onbewerkt door. De Fathomwacht doet dit sinds 21-10-2026, in de bevinding,
de bronregel en de schermregel (`tests/test_bord_lees.py`). Hetzelfde geldt voor het klaarzet-item
van een privégesprek (RZ2-01, 22-10-2026): alleen datum, start, minuten, privé en een verwijzing
naar het archief met "(privé)" en het id, bij De Fathomwacht en De Plaudwacht (`tests/test_bord_lees.py`,
`tests/test_plaud_wacht.py`); De Plaudwacht schrijft sinds dan ook in haar bevinding alleen
"privégesprek" en de duur. De Dagbundelaar zet er "privégesprek, N min" van, ook voor een oud item,
en de export van het bord (`bord_export.py`) maakt van elke regel met PRIVÉ "(privé)".
**Privé is ook afdeling prive** (RZ3-01, 22-10-2026). De dossierbeslissing (`plaud/dossier.py`) noemt
een gesprek met afdeling prive privé, ook als de herkenning prive=false zegt; elke lezer volgt dat,
in elke schrijfwijze: De Fathomwacht en De Plaudwacht (`is_prive`, voor de gesprekkentabel, het
klaarzet-item en het werkverslag), De Zoomwacht (een Fathom-opname met die afdeling maakt de
sessie privé, en dan staat ze niet in de dagregel), De Dagbundelaar (ook nooit in een bundel voor
een afdeling), De Regisseur (gesprekkentabel, transcript, klaargezette items en de telling van het
ochtendbericht) en de export. De Regisseur en de export maken ook van een regel met de titel of de
verwijzing van een privé-item "(privé)", en de export ook van de oude Fathom-bevinding met " · prive · ". Oude exportbestanden buiten het venster
van veertien dagen wist de export niet; dat is een afzonderlijke opruiming met een ja van Mehdi. Open, gemeten
op 21-10-2026: De Archivaris (`archivaris.py`, de bevinding met personen en reden) schrijft het nog;
het twijfelsignaal van De Archivaris, een klaargezet signaal, noemt ook personen. De Regisseur filtert wat hij
leest wel zelf (`werkverslag_lees` in `regisseur.py`, voor het dossier en de tool `agent_verslag`):
nooit het detail, een regel die privé noemt wordt "(privé)", en van een privé-agent of een agent
waarvan dat onbekend is alleen tijd, stap en onderwerp. Dat beschermt alleen die lezer; het
werkverslag zelf gaat ook naar de export en naar De Ontwikkelaar.

`tests/test_agentnorm.py` faalt zodra iemand deze doorgang weghaalt of uitholt,
en ook als het sjabloon hem niet meer gebruikt. Acht toetsen, allemaal groen op
20-09-2026.

## 6. Hoe een agent Mehdi bereikt

Zijn laptop slaapt 's nachts en vroeg in de ochtend. Een melding op een scherm
dat uit staat is geen melding. Drie kanalen, van zacht naar hard:

| kanaal | hoe | waarvoor |
|---|---|---|
| het bord | `hartslag(..., nood=[...])` | alles wat kan wachten tot hij kijkt |
| WhatsApp, met Telegram als vangnet | een klaarzet-item met `soort: signaal` en `voor: mehdi`; De Bode bundelt het in het eerstvolgende vaste moment: het ochtendbericht of de avondbundel (rond 17:00 Brussel, met de mailupdate van 17:00) | wat hij vandaag moet weten; wat niet kan wachten, is een oproep |
| bellen (Twilio) | `koppelingen/bellen.py`, De Bode belt | alleen wat op een tijdstip moet gebeuren, zoals het belrooster van de Agendawacht |

Dat is keuze 1 van Mehdi (21-10-2026): de stand ochtend-avond. Die staat niet in de code,
maar als vaste regel `BUNDELEN: ochtend-avond` in de werkwijze van De Bode op het bord
(RZ3-02, 22-10-2026, werkwijze 2.8): De Bode bundelt pas als Mehdi die werkwijze met een
klik zette, ook als de code al eerder live stond. Alleen oproepen, alarmen en het bellen
voor afspraken gaan meteen. Het ochtendbericht maakt De Regisseur (hoogstens vijf
beslissingen, met een link naar het bord); De Bode stuurt het als eigen bericht. Komt het
er om 11:00 Brussel niet, dan stuurt De Bode een terugval met de aantallen. Zonder die
regel, in een andere vorm, of met een tweede vermelding van de stand (in welke
schrijfwijze ook) is de stand `uit`, de terugval: dan gaat elk signaal los, zoals voor
21-10-2026. Omschakelen of terugdraaien is dus een werkwijze op het bord, geen commit; dan
hoort deze tabel mee te veranderen. Bij een omschakeling verdwijnt niets: terug naar `uit`
stuurt De Bode eerst wat al gebundeld was als een slotbundel (in de stille uren om 07:00),
en naar `ochtend-avond` begint de eerste bundel na het laatste bericht dat los wegging,
en nooit na een bericht dat nog niet weg is (RZ4-03, 22-10-2026, werkwijze 2.9). De
leesstand van De Bode schuift pas over een bericht als het verstuurd is of in een bundel
zit; wat in geen bundel past, gaat los. Wat onder een volle pagina van het bord valt, haalt
De Bode op met `tot_id`, voor de leesstand en voor de lopende bundel. Lukt dat niet, dan
blijft de leesstand staan, zegt het volgende vaste moment "onbekend of meer" en schuift de
bundel niet op, met een nood. Tot dan kon een signaal zo stil verdwijnen.

**Een nood voor Mehdi bereikt hem in het ochtendbericht, als punt of onder Verder.**
De Regisseur neemt elke ochtend de open noden met `wie: mehdi` mee: als punt (samen,
oudste eerst, met hoeveel nieuw) als er plaats is binnen de vijf beslissingen, en
altijd als aantal onder Verder; kon hij de noden niet lezen, dan staan ze onder
Onbekend, nooit als 0. Dat is een keer per dag. De Bode stuurt zelf geen noden
door: wat Mehdi vandaag nog moet weten, zet je als signaal, en wat niet kan wachten,
als oproep.

**Mehdi spreekt een agent aan met "Naam, vraag"**, via WhatsApp of Telegram: de naam of
het label van de agent, dan een komma, een dubbelepunt of een los koppelteken, dan de
vraag ("Zoomwacht, wat is er vanochtend afgesproken?"). De Bode herkent de naam met een
vaste regel: accenten, hoofdletters en "De" of "Het" vooraan tellen niet, dus
"Zoomwacht", "De Zoomwacht" en "zoom-wacht" zijn dezelfde; een kleine verschrijving van
minstens vijf tekens telt alleen als ze op precies een agent past. De Regisseur antwoordt
dan in de rol van die agent, met diens dossier en een regel "Gelezen:" met bron en tijd.
Past de naam op meer dan een agent, of op geen, dan kijkt De Regisseur ernaar, en zegt de
bevestiging dat.

**Het woord "stil" in een signaaltitel belt hem op.** De Bode leest een signaal
met "stil" erin als alarm en start een gesproken oproep via Twilio, herhaald tot
er wordt opgenomen, ook in de stille uren (`is_alarm()` in `bode.py`: een oproep, of
een signaal met "stil" in de titel). Gemeten op 20-09-2026: de eerste ronde van de Normwacht meldde "39
uur stil" en belde Mehdi daarop op. Een agent die niet draait is geen alarm; dat
heet nu "geen hartslag". Bellen blijft voor wat op een tijdstip moet gebeuren.

**Wie Mehdi wil laten bellen, zet een oproep klaar**: een klaarzet-item met `soort: oproep` en `voor: mehdi`. De
Bode belt dan meteen, van het vaste nummer (L17), en bundelt wat tegelijk binnenkomt in een gesprek. Geef elke oproep
een eigen `uniek` per zaak, dan wordt Mehdi nooit twee keer voor hetzelfde gebeld. Sinds 26-09-2026 doet De
Mailregisseur dit bij dringende mail zonder antwoord (deurwaarder, ingebrekestelling, laatste aanmaning, schorsing,
tuchtprocedure; `postvak.DRINGEND`), op werkdagen om 08:00, 12:30 of 17:00. Nieuwe agents gebruiken dit, niet het
woord "stil".

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

Een agent die meteen slaagt, begint niet bij de generator maar bij de inhoud. De
fasen van idee tot live staan in de Werkafspraken Claude en Codex (hoogste versie,
punt 4a; aanvaard door Mehdi op 16-10-2026). In het kort:

| voor de generator | waarom |
|---|---|
| Mehdi spreekt de opdrachtkaart in: probleem, bron, wat hij wil zien, wat nooit, wat hij beslist, met een goed en een verkeerd voorbeeld | zonder doel en grenzen haalt een werkwijze N1 en N2 alleen op papier |
| keuze uitbreiden of nieuw staat op papier en Mehdi bevestigt ze; nieuw alleen bij een eigen mandaat, ritme of toegangsgrens | twee agents voor hetzelfde onderwerp is N6 in het groot |
| een kleine bronproef, alleen lezend, gegroepeerd in soorten | op 25-09-2026 werden 34 mailwachters voorgesteld op basis van aantallen; de meting toonde iets heel anders |
| Codex leest het ontwerp voor de bouw, alleen lezend | de meeste latere fouten bij de Agendawacht waren ontwerpfouten (les L38) |
| de voorbeelden van Mehdi worden tests: verwacht resultaat en foutgevallen | dat is het opstartbewijs; zonder voorbeeld weet niemand wanneer de agent goed werkt |

Dan de generator:

```
cd ~/appportal/mijnagents-runner && ~/agents/.venv/bin/python nieuwe-agent.py --naam post-wacht \
  --label "De Postwacht" --type h-architects --rol "sorteert nieuwe post op info@" \
  --mandaat "lezen en labelen, nooit verwijderen" --cadans "elk uur" \
  --mag "post labelen" --grens "nooit verwijderen" --werkwijze werkwijze/post-wacht.md

# werk() invullen, dan:
~/agents/.venv/bin/python nieuwe-agent.py --eerste-ronde post-wacht --cron "0 * * * *"
```

De werkwijze die je meegeeft moet zelf al door N1, N2, N8 en N9 komen, met punten
onder de twee afgesproken koppen "## Wat ik nooit doe" en "## Wat Mehdi beslist"
(eventueel genummerd, of met een toevoeging tussen haakjes), in de vaste vorm: elke
kop staat er een keer, met een witregel ervoor; eronder alleen punten (regels die op
kolom 0 met "- " of "* " beginnen, gewone tekst zonder opmaak of HTML) en lege
regels; elke sectie is afgesloten door een volgende kop of het einde van de tekst,
voor het eerste codeblok; en de werkwijze bevat nergens ruwe HTML of commentaar,
want het bord zet die onbewerkt op de pagina, waar ze de grenzen kan verbergen
(Codex NA44). Een kop over wat een ander
nooit doet, telt niet. Dat is bewust een kleine, strikte vorm in plaats van een
nabootsing van Markdown: wat er niet in past, wordt geweigerd, nooit aanvaard (Codex
NA17 tot NA42, stopregel). Een proef in de CI legt met de Markdown-weergave van het
bord (Python-Markdown 3.11.1, zoals `md()` in `mijnagents/app.py`) vast dat wat
`bord.grenzen` aanvaardt, op het bord precies zo als kop met lijstpunten staat. Ze geldt voor
nieuwe agents en voor wie het sjabloon gebruikt; bestaande werkwijzen hoeven ze niet
te hebben, want die lopen niet door `bord.grenzen`. De generator weigert
anders, voor er iets op schijf of op het bord staat. Daarna:

- laat de runner elke ronde melden wat hij las (N4);
- laat hem noden schrijven met een eigenaar en een besluit, niet als logregel (N7);
- draai `controle_agenten.py --agent <naam> --uitleg` voor je hem op de cron zet.

Twee eisen aan de doorgang zelf, sinds v1.8:

- **Controle voor registratie.** Naam, label, rol, mandaat, minstens een grens en
  een werkwijze die N1 en N2 haalt, worden gecontroleerd voor er iets op het bord
  komt. Een generator die eerst registreert en dan pas faalt, laat een halve kaart
  achter (Codex NA08, 16-10-2026).
- **Actief pas na een gecontroleerde eerste ronde.** De eerste ronde draait, de
  controle hierboven slaagt, het werkverslag is gelezen en tegen de voorbeelden van
  Mehdi gelegd. Pas dan gaat de agent actief en op de cron. Dat is de norm; vandaag
  zet het bord een kaart al bij de registratie op actief, en wacht alleen de cron
  (zie "Wat nog niet kan" hieronder).

Zo doet de generator het sinds v1.9 (`tests/test_nieuwe_agent.py`, in de CI):

- **Aanmaken** controleert eerst naam, label, rol, mandaat, cadans, minstens een mag
  en een grens (N3) en de werkwijze (N1, N2, N8, N9 en de twee koppen met punten),
  en of de naam nog vrij is op het bord en geen eigen runner heeft. Weet het bord
  dat niet, dan maakt hij niets: onbekend is niet vrij. Daarna schrijft hij het
  skelet, registreert hij, zet hij de werkwijze en leest hij die terug. Breekt een
  stap na de registratie, dan staat de kaart er zonder werkwijze en zegt hij hoe je
  ze zet: de goedgekeurde tekst in `werkwijze/<naam>.md` (hij waarschuwt als daar een
  andere tekst staat), `werkwijze_naar_bord.py <naam>`, dan `--zet`. Zelf hervat hij nooit: een
  kaart zonder werkwijze is niet vanzelf de zijne, en het bord toont te weinig om
  dat te herkennen (Codex NA13 en NA20). De werkwijzen van De Bode, De Regisseur en
  De Zoomwacht zet `--zet` nooit (RZ4-07, 22-10-2026): `werkwijze_naar_bord.py <naam>
  --voorstel` zet het zaad als voorstel met het runbook werkwijze-bijwerken op het bord,
  en het geldt pas na de klik van Mehdi.
- **`--eerste-ronde`** weigert een runner die nog het skelet is, draait de runner
  een keer en toetst de agent met `controle_agenten.py`. Hartslag en gemelde kennis
  moeten van die ronde zijn, niet van een eerdere (Codex NA14), en de ronde moet op
  klaar of waakt eindigen. Pas als elke norm slaagt, krijg je de cron-regel. Het
  werkverslag naast de voorbeelden van Mehdi leggen blijft een menselijke stap.
- **Wat nog niet kan (open, vraagt een wijziging aan het bord):**
  - het bord zet een kaart bij de registratie meteen op actief (`POST /api/agent`
    in `mijnagents/app.py`); wat tot na de eerste ronde wacht, is alleen de cron.
    Een kaart die pas na die ronde actief wordt, vraagt het bord en
    `controle_agenten.py` (dat alleen actieve kaarten toetst) (Codex NA12);
  - de registratie is een bijwerking als de naam al bestaat; tussen de vraag "is
    de naam vrij" en de registratie kan een andere sessie dezelfde naam aanmaken,
    en dan werkt `POST /api/agent` die kaart bij (rol, mandaat, grenzen, actief).
    Alleen een registratie die op het bord zelf weigert wat bestaat (alleen nieuw,
    409 als de naam bestaat), sluit dat (Codex NA13 en NA47, ernst middel; risico
    aanvaard door Mehdi op 17-10-2026: "Uitrollen met NA47 open. Ik aanvaard dat
    risico"). Het speelt alleen als twee aanmaken van dezelfde naam tegelijk lopen.

De controlerondes met Codex na de bouw volgen de stopregel uit de werkafspraken:
twee rondes zonder vooruitgang betekent eerst het ontwerp herbekijken, en live gaat
alleen zonder open punten van ernst hoog of middel.

## 9. De chatkant

Een agent die Mehdi ook in een gesprek aanspreekt, hoort een skill te hebben in
`~/.claude/skills/<naam>/SKILL.md` op zijn Mac. Die skill wordt automatisch
geladen zodra het onderwerp valt, wijst naar de bron hierboven en draagt de
valkuilen. Zonder skill begint elke sessie blanco en moet Mehdi alles opnieuw
uitleggen. Vandaag bestaan `werfverslag` en `agendawacht`.

Een skill vervangt de werkwijze niet en herhaalt haar niet: ze wijst ernaar.
Twee teksten met dezelfde inhoud lopen altijd uit elkaar, zie N6.
