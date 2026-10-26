# Ontwerp: de dagvaststelling (De Dagbundelaar, uitbreiding)

Versie 2.10, 26-10-2026: de hotmailkopie in een lezing, geen eigen mapnaam in de reden, een totale mailfout sluit geen postvaknood, en de kopie dekt 62 dagen binnen (Codex-controle mailnood 1, driehoeksoverleg "De Dagbundelaar afwerken"). Versie 2.9, 26-10-2026: mail per postvak een vaste nood, en een kopie die de dagen niet dekt is onvolledig (docs/overleg/2026-10-26 Dagbundelaar mailnood driehoeksoverleg.md). Versie 2.8, 26-10-2026: fase 2 uitgewerkt (blokken "Fase 2 uitgewerkt", "Antwoord op de ontwerplezing" en de antwoorden op de bouwcontroles r2 tot r8 onderaan). Versie 1.9, 26-10-2026. Claude 2. v1.0 en v1.1 gingen naar Codex (docs/codex/dagvaststelling-ontwerp-r1.md en -r2.md,
telkens "bouwen nee"). Deze versie beantwoordt ronde 2 (E1 tot E6) en beschrijft fase 1 zoals ze nu gebouwd is, met de
uitkomst van een droge proef op de VM met de echte gegevens van 22-10-2026. Waar v1.2 afwijkt van wat hieronder in v1.1
staat, geldt het blok "Wijzigingen in v1.2".

## Opdracht van Mehdi (26-10-2026)

Elke nacht na middernacht een vast overzicht van gisteren, om later terug te vinden: welke agenda-afspraken echt
doorgingen, wat er gebeurde zonder gepland te zijn (Zoom, telefoon, bezoeken), en de communicatie langs mail, Zoom en
WhatsApp. Hij plant niet alles in; het overzicht moet dat opvangen.

Beslist door Mehdi op 26-10-2026, na inventaris en bronproef:
1. De Dagbundelaar uitbreiden, geen nieuwe agent.
2. WhatsApp en telefoon met namen; nooit de tekst van berichten.
3. Vastleggen op het bord en als bestand per dag in Dropbox.
4. Na de vraag over de grens van de WhatsApp-wacht (v2.0, 23-10-2026): namen ook op het bord, in de gesprekkentabel
   (alleen beheer). De WhatsApp-wacht mag de WhatsApp-databank op de Mac automatisch lezen, alleen wie, wanneer,
   hoeveel en hoe lang.

## Twee fasen

- **Fase 1 (VM)**: de dagvaststelling in De Dagbundelaar, met agenda, locatie, Zoom, Fathom, Plaud en mail. WhatsApp en
  telefoon staan er als "nog niet aangesloten" tot fase 2 levert.
- **Fase 2 (Mac)**: WhatsApp-wacht en Belwacht lezen de databanken op de Mac en schrijven rijen in de gesprekkentabel.
  Eerst de nieuwe werkwijzen op het bord (D3), dan de runners (D4), dan de toegangsproef onder launchd (D10).

## Fase 1: De Dagbundelaar

### Eén runner, één ronde (D1, D2)

`dagbundelaar.py` gaat door de gedeelde ronde (`with ag.ronde(...)`, N12). Hij krijgt geen tweede runner en geen
tweede hartslag. Twee manieren van draaien, elk met een eigen taaknaam in de ronde:

| draai | wanneer | taak in de hartslag | wat |
|---|---|---|---|
| ochtend | werkdagen 07:00 UTC, laatste stap van `keten.py` (ongewijzigd) | `bundels en dagvaststelling` | bundels per dossier zoals nu, daarna de dagvaststelling |
| nacht (`--nacht`) | elke dag 23:30 UTC, eigen cronregel onder `/tmp/gesprekken.lock` | `dagvaststelling` | eerst `zoom_wacht.py` (time-out 1200 s), dan alleen de dagvaststelling, geen bundels |

`koppelingen/ochtend.py` geeft het ochtendbericht alleen vrij op een hartslag van De Dagbundelaar na de keten als de taak
`bundels` bevat. Een nachtronde of een handmatige `--nacht` geeft het nooit vrij (D1). Daarnaast ligt de nachtronde
altijd voor het geplande ochtendstart (23:30 UTC, hoogstens 1800 s wachten op het slot).

De bundellogica slaat soort `dagvaststelling` over en markeert ze nooit als opgepakt (D2). De noden over WhatsApp en
telefoon verdwijnen zodra er voor die dag rijen met bron `whatsapp` of `telefoon` zijn; tot dan staat er een nood
zonder aantal (N10).

"Gisteren" is altijd de Brusselse kalenderdag, ook op de VM die in UTC loopt (`ZoneInfo("Europe/Brussels")`). Om 23:30
UTC is het in Brussel 00:30 (winter) of 01:30 (zomer); gisteren is dan de dag die net eindigde.

### Wat de dagvaststelling leest (nieuwe module `koppelingen/dagvaststelling.py`)

Pure functies met tests; de runner haalt de bronnen op en geeft ze door.

1. **Gepland**: `agenda_wacht.afspraken_dag(D, alleen_lezen=True)`, zonder hele dag, ritten en geannuleerde. Staat er na
   het lezen een agenda in `agenda_wacht.ONGELEZEN`, dan is de agenda onvolledig: het overzicht zegt welke agenda's
   ontbreken en "Niet gepland" krijgt het label "onder voorbehoud" (D6). Een lege agenda is "geen afspraken"; een
   ongelezen agenda is "onbekend", nooit nul.
2. **Gesprekken**: `gesprek_log` voor datum D, alleen leidende rijen (`COALESCE(dubbel_van,'')=''`, de telregel Z10 van
   de dagenpagina). Zoom-chats (`zoom:chat:`) staan apart en tellen nooit als gesprek (D7). De Zoom-dagregel
   (`zoom:dag:D`) geeft de stand: volledig, ondergrens of onbekend; zo staat het in het overzicht.
3. **Locatie**: `locatie_wacht.vergelijk_agenda` krijgt een optionele uitvoer per afspraak-id. De auto ter plaatse is een
   **aanwijzing**, geen bewijs dat het gesprek plaatsvond (D6).
4. **Mail**: binnengekomen uit `mailbericht` per postvak en soort; verzonden per postvak uit de verzonden-mappen
   (`postvak.VERZONDEN`) via `postvak.koppen`, gefilterd op datum D in Brussel, ontdubbeld per Message-ID over alle
   postvakken. Een map die niet leesbaar is, een kopie ouder dan `BRON_VERS_UREN` (hotmail: sinds 26-10-2026 van de
   server, daarvoor van de Mac), of een kopie die de dagen niet dekt (`vanaf` in het bestand), maakt de telling van dat
   postvak "onvolledig" met de reden (D8). De nood staat per postvak en soort, zonder getal; de uren staan in het
   logboek (driehoeksoverleg mailnood, 26-10-2026). Hotmail is privé.
5. **WhatsApp en telefoon**: rijen met bron `whatsapp` en `telefoon` (fase 2). Zonder rijen: "nog niet aangesloten".

### Bewijs per afspraak (D6)

| uitkomst | wanneer |
|---|---|
| bevestigd | een leidend gesprek (Zoom, Fathom, Plaud, oproep) overlapt het venster (15 min marge) **en** deelt een persoon met de afspraak (naam uit titel of deelnemers, minstens een naamdeel van vier letters) |
| aanwijzing | alleen overlap in tijd, of de auto ter plaatse |
| geen spoor | niets van het bovenstaande; de vraag "Ging dit door?" |

Nooit "niet doorgegaan" als feit. Een privéafspraak toont op het bord alleen "privé".

### Niet gepland

Leidende gesprekken en oproepen van minstens 2 minuten zonder overlap met een afspraak; projectbezoeken en verblijven
van 20 minuten of meer zonder afspraak (uit `locatie_wacht.maak`, de lijsten werf en elders).

### Privé (D5)

Kern bevat alleen medewerkers. Regel: een rij is privé als de bron ze privé markeert (`prive=1` of afdeling privé,
RZ3-01), en alles van WhatsApp en telefoon is privé tot het tegendeel bewezen is. Op het bord (klaarzet) staat van een
privérij alleen "privé" met aantal en minuten (RZ2-01). De gesprekkentabel (alleen beheer) en het bestand in Dropbox
dragen de namen, zoals Mehdi besliste. Twijfel is privé.

### Uitvoer, versies en teruglezen (D9)

- Bestand `mijnagents-data/dagboek/<jaar>/<D>.md`, atomisch. Een vorige versie die verschilt, blijft staan als
  `dagboek/<jaar>/versies/<D> v<n>.md`. Onderaan elk bestand: versie, gemaakt om, bronnen en hun stand, en wat er
  tegenover de vorige versie veranderde.
- Klaarzet voor mehdi, soort `dagvaststelling`, uniek `vaststelling:<D>`, `revisie: true`, zonder privénamen. Het bord
  houdt alleen de laatste versie; de geschiedenis staat in de bestanden.
- Teruglezen in dezelfde ronde: het bestand van schijf, het item via `/api/klaarzet?uniek=`; zonder beide is de ronde
  niet geslaagd.
- Dropbox: `planning/mac/data_uit_mehdi_sync.sh` haalt `dagboek` naar `Data uit Mehdi/Dagboek` (zelfde plek en regel als
  Locatie, beslissing Mehdi 12-09-2026: alles, ook privé). Na de rsync schrijft de Mac een ontvangstbewijs
  (`dagboek/.dropbox-ontvangst.json`: bestand en sha256 van de kopie in Dropbox) terug naar de VM; de volgende ronde
  meldt welke dagen in Dropbox bevestigd zijn en welke nog niet.

### Herzien met een watermerk (D10)

Staat in `mijnagents-data/dagboek/staat.json`: per dag de hash, het tijdstip en het versienummer. Elke ronde maakt
gisteren en eergisteren altijd opnieuw, en daarnaast elke dag van de laatste veertien waarvoor een bron nieuwer is dan
de laatste vaststelling (max `ts` in `gesprek_log` voor die datum, in `mailbericht` voor die dag, het locatie-item van
die dag). Alleen bij een andere hash komt een nieuwe versie. Zo komt een Mac die drie dagen sliep alsnog mee.

### Tests vooraf (tests/test_dagvaststelling.py en uitbreiding van test_dagbundelaar, test_ochtend)

- Brusselse daggrens: 23:30 UTC in winter en zomer, en de nachten van beide wissels (29-03 en 25-10-2026).
- Ochtendbericht: een nachtronde of een `--nacht` na de keten geeft het ochtendbericht niet vrij; een volledige ronde wel.
- Bundels: een item `dagvaststelling` komt nooit in een bundel en wordt nooit opgepakt.
- Agenda: lege agenda tegenover ongelezen agenda; onvolledig label op "Niet gepland".
- Bewijs: auto ter plaatse zonder gesprek is aanwijzing; overlap zonder persoon is aanwijzing; overlap met persoon is
  bevestigd; niets is geen spoor.
- Dubbels: Zoom en Fathom met dubbel_van tellen een keer; chats tellen niet als gesprek.
- Mail: onleesbare verzonden-map, een oude kopie en een kopie die de dagen niet dekt geven onvolledig; dezelfde
  Message-ID in twee postvakken telt een keer; de mailnood blijft gelijk als de uren of andere postvakken wisselen.
  Faalt het hele lezen, dan blijven open mailnoden open; is dat onbekend, dan breekt de ronde als laatste stap.
  Een vervangen kopie tijdens het lezen verandert de telling niet; een eigen map heet "een eigen map".
- Zoom-stand onbekend of ondergrens staat zo in het overzicht.
- Privacy: geen privénaam in het klaarzet-item; wel in het bestand.
- Revisie: zelfde inhoud schrijft niets; andere inhoud geeft versie 2 en bewaart versie 1.
- Watermerk: een nieuwe rij voor een dag van vijf dagen terug maakt die dag opnieuw.
- Voorbeeld 22-10-2026 uit de bronproef als goudtest (zonder namen in de repo).

## Fase 2: WhatsApp-wacht en Belwacht op de Mac (D3, D4, D10)

- **Eerst het bord** (D3): nieuwe werkwijzen, mandaat, mag en grenzen voor WhatsApp-wacht (v3.0) en Belwacht, met de
  beslissingen van Mehdi van 26-10-2026; zaad in `werkwijze/` gelijk (N6). Pas na Mehdi's ja in de chat.
- **Twee runners met eigen naam** (D4, N5): `mijnagents-runner/whatsapp_wacht.py` (vervangt `mac/whatsapp_wacht.py`) en
  `mijnagents-runner/belwacht.py`, elk door de gedeelde ronde via de ssh-tunnel naar 127.0.0.1:3022 zoals
  `tekenaar.py`, met teruglezen van hartslag en kennis via `koppelingen/bordstand.py`. Gedeelde leescode in
  `koppelingen/mac_gesprekken.py`.
- **Wat ze lezen**: een sqlite-kopie van ChatStorage.sqlite en CallHistory.sqlite (WhatsApp) en
  CallHistory.storedata (iPhone). Nooit berichttekst of bijlagen.
- **Dubbels** (D7): een WhatsApp-oproep staat ook in de iPhone-geschiedenis (provider `net.whatsapp.WhatsApp`); de
  Belwacht slaat die over. Rijen: `whatsapp:<sha1 jid>:<dag>` per gesprek per dag, `whatsapp-oproep:<id>`,
  `telefoon:<id>`.
- **Toegang** (D10): eerst een proef onder launchd met het exacte programma; geeft macOS geen toegang, dan alleen een
  vaste helper volledige schijftoegang geven, niet de algemene Python. Mehdi zet die ene toestemming.

## Wat nooit gebeurt

- Berichttekst, mailinhoud of bijlagen lezen of bewaren.
- Iets versturen, de agenda wijzigen, iets uit de bak verwijderen, of een item als opgepakt markeren dat niet van mij is.
- Een privénaam in een klaarzet-item of een afdelingsbundel.
- "Niet doorgegaan" zeggen zonder bewijs; een onbekende of falende bron als nul tonen.

## Wat Mehdi beslist

- Of een afspraak zonder spoor doorging.
- Of een privécontact werk is.
- Welke postvakken en kanalen meetellen, en wie toegang heeft tot `Data uit Mehdi`.

## Antwoord op ronde 1

| punt | antwoord |
|---|---|
| D1 | geen tweede runner; ochtendvrijgave alleen op taak met `bundels`; test |
| D2 | soort overslaan en nooit oppakken; noden afhankelijk van echte rijen; Dagbundelaar door de ronde (N12) |
| D3 | fase 2 begint met de werkwijzen op het bord, na Mehdi's ja |
| D4 | twee runners met eigen naam, gedeelde ronde via tunnel, teruglezen |
| D5 | privé tenzij bewezen; namen alleen in gesprekkentabel en bestand; Dropbox-plek zoals Locatie (Mehdi 12-09) |
| D6 | bewijs, aanwijzing, geen spoor; ongelezen agenda is onbekend; Zoom-stand uit de dagregel |
| D7 | alleen leidende rijen, chats apart, WhatsApp-oproep niet ook als telefoon |
| D8 | verzonden per map, onvolledig bij fout of oude kopie, ontdubbeld per Message-ID |
| D9 | versies als bestanden, klaarzet met revisie, teruglezen, Dropbox-ontvangstbewijs |
| D10 | watermerk over veertien dagen, zomertijdtests, toegangsproef in fase 2 |

## Wijzigingen in v1.2 (antwoord op ronde 2)

Bijkomende beslissing van Mehdi (26-10-2026): hij weet niet wie de Dropbox-map `Data uit Mehdi` kan zien. Dus draagt
ook het bestand in Dropbox geen privénamen; de namen staan alleen in de gesprekkentabel (alleen beheer). Bord, bestand
en Dropbox dragen daardoor dezelfde tekst, met het masker van het bord al toegepast voor het schrijven.

| punt | antwoord in v1.2 en in de code |
|---|---|
| D1 | `ochtend._bundelronde_klaar_na`: alleen klaar of waakt, nooit fout, en nooit taak `dagvaststelling` (NACHTTAAK); `regisseur.py` leest de taak mee; test in test_regisseur.py |
| D2 | kanaalstand uit de hartslag van whatsapp-wacht en belwacht (taak met `databank`, klaar of waakt, hoogstens 26 uur oud), niet uit rijen; de oude noden over exports en Xelion zijn weg; nood zonder aantal zolang niet aangesloten |
| D5 | Dropbox zonder privénamen (beslissing Mehdi hierboven) |
| E1 | alleen bronnen zoom, fathom, plaud, whatsapp, telefoon tellen als gesprek; mail en chats nooit; een Plaud-opname die voor minstens de helft samenvalt met een leidend Zoom- of Fathom-gesprek telt niet |
| E2 | agenda over het venster met `W.afspraken` en `W.archief_afspraken`, ongelezen agenda's en `ARCHIEF_FOUT` maken de agenda onvolledig |
| E3 | persoon van de afspraak: het stuk na de code tussen haken en de gasten van buiten, nooit wat voor de code staat (de eigenaar) en nooit Mehdi; `lees_titel().klant` is niet betrouwbaar ('<collega>: PL'). Een gesprek hoort alleen via die persoon bij een afspraak; overlap zonder persoon is hoogstens een aanwijzing en het gesprek blijft onder niet gepland |
| E4 | ontvangen mail rechtstreeks uit de mappen die de mailwachten lezen (leesdekking van deze ronde gekend), aangevuld met wat de wachten registreerden en wegsorteerden; per postvak eerlijk, het totaal ontdubbeld per Message-ID; onvolledig met reden. De mailcode draait als kind met /usr/bin/python3 (yaml), zoals de mailwachten |
| E5 | geen watermerk: de nachtronde herberekent veertien dagen volledig (agenda en mail een keer per venster gelezen), alleen een andere vaste inhoud geeft een versie |
| E6 | de hash dekt de vaste inhoud zonder het blok over de vaststelling; teruglezen vergelijkt bestand en borditem met wat geschreven werd; het Dropbox-bewijs vergelijkt de sha256 van het bestand |

Gesprekken worden geteld als een totaal over Zoom, Fathom en Plaud (elk gesprek een keer), met hoeveel met opname en
hoeveel alleen in Zoom: een Zoom-gesprek met Fathom-opname staat in de tabel als leidende Fathom-rij.

Droge proef op de VM (26-10-2026, dag 22-10, schrijven alleen naar /tmp, geen bordoproep): 24 s; een plaatsbezoek
aanwijzing (auto ter plaatse), de andere afspraken geen spoor; 12 gesprekken en 2 bezoeken
niet gepland; 14 gesprekken, 119 min (8 met opname, 6 alleen in Zoom), 10 Zoom-chats; mail per postvak, hotmail
onvolledig omdat de Mac-kopie 144 uur oud is.

Bestanden: `koppelingen/dagvaststelling.py` (nieuw), `dagbundelaar.py`, `koppelingen/ochtend.py`, `regisseur.py`,
`locatie_wacht.py` (uitkomst per afspraak-id), `planning/dagvaststelling.cron` (nieuw), `planning/mac/data_uit_mehdi_sync.sh`,
`werkwijze/dagbundelaar.md` (versie 3), tests `test_dagvaststelling.py`, `test_dagbundelaar_vaststelling.py` (nieuw),
`test_dagbundelaar.py`, `test_locatielezers.py`, `test_regisseur.py`.

## Wijzigingen in v1.3 (antwoord op ronde 3, docs/codex/dagvaststelling-bouw-r3.md)

| punt | antwoord in de code |
|---|---|
| F1 | een ongelezen privé-agenda heet 'een privé-agenda' (`lees_agenda`); een postvak van een wacht van firma PRIV of afdeling privé (mch@ en hotmail) toont geen ontvangers |
| F2 | bij naam alleen een werkproject (werf: waarschijnlijk of bevestigd); een twijfelgeval wordt 'projectbezoek, project onzeker', een ander verblijf 'verblijf zonder afspraak (plek in het locatielogboek)' |
| F3 | een afspraak is bevestigd alleen als een naam uit de afspraak en een gesprekspersoon minstens twee naamdelen delen (voornaam en familienaam; partikels en Mehdi tellen niet); tegenproef met twee personen met dezelfde voornaam en met een plaatsnaam in de tests |
| F4 | `locatie_wacht.maak(dag, afspraken=...)` vergelijkt met dezelfde gefilterde lijst (met archief, zonder annuleringen); de stand van het dagboek (afgesloten, voorlopig) staat in het overzicht; een andere stand of een fout is 'niet gelezen' |
| F5 | Zoom-stand onbekend geeft 'Zoom-chat: onbekend' en elk Zoom-getal als 'minstens'; WhatsApp en telefoon per dag: een aangesloten wacht bewijst alleen de dagen met een rij `dekking:<kanaal>:<dag>` (bron dekking, contract voor fase 2), anders 'onbekend voor deze dag', nooit nul |
| F6 | een Zoom-gesprek met een samenvallende Plaud-opname telt een keer en als gesprek met opname |
| F7 | verzonden post ook van de adressen in antwoord_vanuit; een map op het plafond (2000) is onvolledig, ook bij verzonden |
| F8 | de versie volgt het bestand zelf (`versie_van`), de staat wordt per dag meteen geschreven, een bewaarde versie wordt nooit overschreven (anders een naam met tijdstempel), bord en bestand worden letterlijk teruggelezen |
| F9 | de nachtregel staat in het beheerde blok van `planning/gesprekken.cron` als `keten.py --nacht` (zetscript kent het blok van voor de nacht als vorige vorm); de nachtketen schrijft `nacht.json`, nooit `keten.json`; `ochtend.ketenstart` slaat de nachtregel over; een bezet slot staat in keten.log, een mislukte Zoomwacht en een nachtketen die niet liep worden een nood van De Dagbundelaar |
| F10 | de Mac-sync eindigt met exit 1 en 'fout' in het logboek bij een mislukte rsync of een mislukt ontvangstbewijs |

Droge proef op de VM met v1.3 (22, 24 en 25-10-2026, schrijven naar /tmp): werkt; mail 10 binnen en 14 verzonden op 22-10
over acht adressen; gewone verblijven zonder plek; hotmail onvolledig (Mac-kopie 144 uur oud).

## Wijzigingen in v1.4 (antwoord op ronde 4, docs/codex/dagvaststelling-bouw-r4.md)

| punt | antwoord in de code |
|---|---|
| G1 | namen in een titel worden ook gesplitst op 'en', '&', 'met' en '+': "Anna Peeters en Jan Claes" zijn twee personen; "Anna Claes" bevestigt niets |
| G2 | `locatie_wacht.maak` geeft de gaten van de tracker en het aantal geldige punten; zonder geldige meting die dag is de locatie niet gelezen; een afspraak waarvan het uur (met 30 minuten marge) in een gat valt, is 'onbekend: auto zonder meting op dat uur' in plaats van 'niet gezien'. Op 22-10 gold dat voor een vooroverleg (gat van 36 minuten) |
| G3 | overdag kijkt De Dagbundelaar naar einde en exits van de nachtketen (Zoomwacht en Dagbundelaar), en in de ochtendketen naar de exit van De Zoomwacht in keten.json; faalde die, dan is Zoom van gisteren een ondergrens |
| G4 | een ontbrekend postvak maakt ontvangen en verzonden onvolledig |
| G5 | zonder volledige Zoom-stand: 'minstens N, minstens M min (verdeling onbekend)' |
| G6 | de Mac-sync draait met PIPE_FAIL: een falende find of shasum laat het ontvangstbewijs falen |
| G7 | een vrije archiefnaam ('v1 (2)', 'v1 (3)', ...); een bewaarde versie wordt nooit overschreven |

## Wijzigingen in v1.5 (antwoord op ronde 5, docs/codex/dagvaststelling-bouw-r5.md)

| punt | antwoord in de code |
|---|---|
| G2 | `locatie_wacht.meetgaten`: ongemeten is wat voor de eerste en na de laatste meting van de dag ligt, een pauze tussen twee stukken, een gat, en een verblijf zonder een enkel meetpunt (geparkeerd 'al van daarvoor'); bij meer sporen de doorsnede. 'Niet gezien' wordt in zo'n stuk 'auto zonder meting op dat uur' |
| G3 | de staat bewaart de dagen waarvoor De Zoomwacht faalde (`_zoom_onzeker`); zo'n dag blijft een ondergrens tot een geslaagde Zoomwacht hem in haar venster van zeven dagen opnieuw las; een ronde buiten een keten verandert niets (tri-state zoom_gelezen); test met twee mislukte nachten na elkaar |
| H1 | ook de adressen waaruit een privéwacht antwoordt (info@, light@, standaard@ voor mch@) zijn privé: geen ontvangers bij naam |

## Wijzigingen in v1.6 (antwoord op ronde 6, docs/codex/dagvaststelling-bouw-r6.md)

| punt | antwoord in de code |
|---|---|
| G2 | geen indeling meer als bewijs: `locatie_wacht.meettijden` geeft de tijden van de geldige meetpunten; 'niet gezien' blijft alleen staan als er op het uur van de afspraak (met 30 minuten marge) een echte meting is, anders 'auto zonder meting op dat uur'. Een afgeleid of samengevoegd parkeerstuk telt niet als meting |
| G3 | de Zoom-stand komt uit de dagregel zelf: volledig alleen als de telling volledig is en elke bron van de ronde die de regel schreef 'ok' was; de chat heeft haar eigen telling (meestal ondergrens). Een dag waarvoor De Zoomwacht faalde, wordt bewaard met de vingerafdruk van zijn dagregel op dat moment, en blijft een ondergrens tot de regel herschreven is door zo'n volledige ronde; een geslaagde exit alleen wist niets |

Bij het live zetten hoort ook: de nieuwe Mac-sync installeren als ~/bin/data_uit_mehdi_sync.sh (de LaunchAgent gebruikt die
kopie) en teruglezen.

Gezien bij de droge proef, buiten deze opdracht: De Locatiewacht toetst een afspraak met een projectnummer aan de plek van
het project, ook als de titel een ander adres noemt (gezien op 22-10-2026). De
vaststelling zegt dan 'auto niet gezien op de plek' met de vraag of het doorging; ze bevestigt niets ten onrechte.

## Herziening in v1.7 (stopregel na ronde 7, docs/codex/dagvaststelling-bouw-r7.md)

G2 en G3 daalden twee rondes niet. Dus geen bijlapwerk meer, maar een ander ontwerp voor beide.

**Locatie (G2, J1, F4, D6): het oordeel komt uit ruwe meetpunten, niet uit de indeling.** De indeling van het dagboek
leidt parkeerstukken af en kan ze samenvoegen met een later bezoek; daarop steunde zowel 'doorgegaan' als 'niet gezien'.
Nu neemt de vaststelling van De Locatiewacht alleen de plek van de afspraak (lat, lon), en oordeelt zelf op de geldige
meetpunten (`locatie_wacht.meetpunten`: tijd, plek, snelheid) in het venster van de afspraak met 30 minuten marge:

| meting in het venster | uitkomst |
|---|---|
| geen | onbekend: auto zonder meting op dat uur |
| een gemeten stop binnen 300 m: minstens twee punten van hoogstens 3 km/u, of punten bij de plek over minstens tien minuten | aanwijzing: auto gestopt bij de plek |
| punten binnen 300 m maar geen stop | niet gezien: auto reed voorbij de plek |
| alleen punten elders | niet gezien: auto gemeten elders |

Gemeten op 22-10-2026: bij een voorbijrit langs een project was er een punt op 1 km/u op 261 m en de rest rijdend, drie
minuten; bij twee echte stops stond de auto minutenlang op 0 km/u binnen 40 m. Een bezoek zonder afspraak telt alleen
met een echte meting erin. Zonder geldige meting die dag is de locatie niet gelezen.

**Zoom (G3, J2, F9): de dagregel is het bewijs, zonder vlaggen per keten.** De Zoomwacht schrijft een dagregel alleen voor
een afgelopen dag, met de bronstanden van de ronde die ze schreef (`zoom_wacht.dag_inhoud`, bronnen uit die ronde, telling
volledig alleen als elke Zoom-bron ok was), en verlaagt een opgepakte regel nooit tijdens een ronde met uitval (ZOO-01).
Een regel met telling volledig, stand definitief en elke bron ok is dus geschreven door een volledige ronde na het einde
van de dag: de Zoom-sessies van een afgelopen dag veranderen niet meer. Een latere ronde met uitval maakt die regel niet
fout; ze laat hem staan. De vlaggen per keten (v1.6) en de vingerafdruk vervallen, en daarmee J2. Is er geen regel (de
Zoomwacht faalde in de nacht), dan is Zoom onbekend; de ochtendketen schrijft de regel en de ochtendronde herberekent
gisteren.

Verder: namen zonder accenten vergelijken; de uitleg van een aanwijzing noemt hoogstens drie gesprekken, op volgorde.

## Wijzigingen in v1.8 (antwoord op ronde 8, docs/codex/dagvaststelling-bouw-r8.md)

| punt | antwoord in de code |
|---|---|
| K1 | 'ok' zegt dat een bron antwoordde, niet dat elke opname er al was. De Zoomwacht kan een dagregel nog herzien tot zes dagen na de dag (zoom_wacht.TERUGBLIK) en daarna nooit meer. Tot dan is een volledige regel 'voorlopig': 'minstens N, minstens M min (voorlopig: De Zoomwacht kan de dag nog aanvullen)'. Daarna exact; de nachtronde herberekent veertien dagen, dus de dag krijgt dan vanzelf een nieuwe versie |
| K2 | de bezoeken zonder afspraak komen niet meer uit de lijsten van De Locatiewacht (die een samengevoegd parkeerstuk aan een ochtendafspraak kan hangen), maar uit haar verblijven met de echte meettijden (eerste en laatste meting binnen 300 m: aankomen en vertrekken) en de eigen koppeling: een verblijf hoort bij een afspraak alleen als die volgens de metingen doorging, binnen 300 m van haar plek en in haar venster |

## Herziening in v1.9 (ronde 9, docs/codex/dagvaststelling-bouw-r9.md): geen belofte van volledigheid meer

K1, L1 en L2 tonen hetzelfde: met deze bronnen is een volledig aantal gesprekken niet te bewijzen. De Fathomwacht schrijft
tot veertien dagen terug, een dagregel die nog klaarstaat blijft herzienbaar, en elke grens die de vaststelling kiest, kan
een latere bron doorbreken. Daarom belooft de vaststelling geen volledigheid meer:

- Gesprekken, Zoom-chats, WhatsApp en telefoon heten 'gezien': wat de bronnen tot dan toonden, per definitie een
  ondergrens. Ernaast staat wat De Zoomwacht over haar eigen lezing zegt ('De Zoomwacht: volledig gelezen', 'nog niet
  afgesloten', 'onvolledig gelezen', 'stand onbekend'), als haar oordeel, niet als dat van de vaststelling.
- Onbekend blijft onbekend: zonder bron en zonder iets gezien staat er 'onbekend', nooit 0.
- Komt er later iets bij, dan maakt de nachtronde (veertien dagen) een nieuwe versie; de vorige blijft in versies/.

De vaststelling is zo een logboek van wat er gezien werd, met datum en versie, wat Mehdi vroeg: terugvinden wat er was.

## Fase 2 uitgewerkt (v2.0, 26-10-2026)

### Bronproef (26-10-2026, alleen aantallen, week van 19 tot 26-10)

- **WhatsApp** (ChatStorage.sqlite): 100 tot 450 berichten per dag in 13 tot 41 gesprekken, ongeveer de helft in
  groepen. Elk gesprek heeft een naam (ZPARTNERNAME). Berichtsoorten: 6 (groepsmelding) en 10 (systeemmelding) zijn
  geen berichten; 59 is de melding van een oproep in het gesprek (ZSTANZAID is de oproep-ID: 46 van 46).
- **WhatsApp-oproepen** (CallHistory.sqlite): 99 in een week, een tot negentien per dag, geen groepsoproepen. 62 hebben
  een deelnemer (altijd een LID-adres, altijd terug te vinden in het adresboek van WhatsApp, ContactsV2.sqlite); voor de
  rest wijst de oproepmelding in het gesprek of de beller (ZGROUPCALLCREATORUSERJIDSTRING, bij inkomend) de persoon aan.
  Een oproep met duur nul is gemist of niet beantwoord.
- **iPhone-oproepen** (CallHistory.storedata): 132 in een week, allemaal com.apple.Telephony, ZNAME altijd leeg,
  ZUNIQUE_ID uniek. Van de 24 nummers staan er 14 in het adresboek van WhatsApp en 6 in de Mac-contacten (samen 16).
  74 oproepen waren gemist (twee nummers belden 47 en 32 keer).

### Toegangsproef (D10)

Een launchd-taak die alleen de drie databanken opent: geweigerd voor /usr/bin/python3 ("authorization denied") en voor
Python 3.14 ("unable to open database file"). Een vaste helper met volledige schijftoegang is dus nodig.

### De helper: MacGesprekkenKopie

Een klein C-programma (`mijnagents-runner/mac/kopie/macgesprekken_kopie.c`), ad hoc ondertekend met hardened runtime,
het enige programma dat volledige schijftoegang krijgt. Het voert geen andere code uit (geen Python, geen script, geen
omgevingsvariabelen; de thuismap komt uit getpwuid), zodat de toestemming aan de cdhash vastzit: wie het bestand
vervangt, verliest de toegang.

- Eén argument, de set: `whatsapp` (ChatStorage, CallHistory en ContactsV2 van WhatsApp) of `telefoon`
  (CallHistory.storedata en ContactsV2). Vaste bronpaden.
- Per bron: alleen lezend openen (busy timeout), `sqlite3_serialize` binnen een leestransactie (een samenhangend
  beeld, met de WAL erbij), de kop op rollback-modus zetten, en schrijven naar
  `~/Library/Caches/mijnagents/mac-gesprekken/<set>/<bron>.sqlite` met O_CREAT|O_EXCL|O_NOFOLLOW (0600) en rename. De
  map is 0700, van de gebruiker, geen symlink; anders weigert de helper. Caches gaan niet mee in Time Machine.
- Daarna `status.json` met het tijdstip en per bron `ok`, `geweigerd` of `fout`, zonder paden of inhoud.
- Twee launchd-taken zonder schema (`be.globaal.mijnagents.kopie-whatsapp`, `-telefoon`), alleen op vraag: de runner
  start ze met `launchctl kickstart` en wacht hoogstens 120 s op een status die jonger is dan zijn vraag. Zo is de
  helper zelf het verantwoordelijke proces (TCC), en de Python-runner heeft geen schijftoegang nodig.

### De twee runners

`mijnagents-runner/whatsapp_wacht.py` en `mijnagents-runner/belwacht.py`, elk door de gedeelde ronde via de
ssh-tunnel naar 127.0.0.1:3022 (zoals `tekenaar.py`), met een eigen slot, het token uit `~/.config/mijnagents/token`
en een ronde-ID. Elk uur via launchd (WhatsApp op :07, telefoon op :37); slaapt de Mac, dan bij het ontwaken.
Taak in de hartslag: `WhatsApp-databank lezen` en `iPhone-oproepen uit de databank lezen` (het woord `databank`, zie
`dagbundelaar.kanaalstand`). Python 3.14 van python.org, code uit een eigen worktree op origin/main
(`~/Library/Application Support/mijnagents/repo`), bijgewerkt door `mac/uitrol_mac_gesprekken.sh`, nooit uit de
werkmap van een sessie.

Ronde, in deze volgorde:

1. Werkwijze van het bord; zonder de koppen "Wat ik nooit doe" en "Wat Mehdi beslist" stopt de ronde (`bord.grenzen`).
2. Verse kopie vragen; geweigerd of te laat is een nood, en dan wordt niets gelezen of geschreven.
3. Lezen met vaste kolommen (`koppelingen/mac_gesprekken.py`, pure functies met tests). Nooit ZTEXT, ZLASTMESSAGETEXT,
   media of bijlagen; een test houdt de lijst van gelezen kolommen vast.
4. Rijen voor de laatste veertien Brusselse dagen (zelfde venster als de nachtronde), privé, naar `/api/gesprekken`.
5. Teruglezen van de rijen (`bordstand.py --gesprekken <kanaal> <van> <tot>`: per rij een vingerafdruk, geen namen in
   de uitvoer); verschil is een fout. Een rij in het venster die de bron niet meer toont (een gewist gesprek), krijgt
   `dubbel_van = buiten:vervallen`; komt ze terug, dan zet de volgende ronde ze weer leeg.
6. Na de ronde: hartslag en kennis met de ronde-ID teruglezen (`bordstand.py <naam> --ronde`); zonder dat een
   foutmelding op de console en exit 1.
7. De kopie van de berichten (ChatStorage) wordt na het lezen gewist.

### Rijen in de gesprekkentabel (contract met De Dagbundelaar)

| uniek | bron | wat | telt (dubbel_van) |
|---|---|---|---|
| `whatsapp:<sha1 jid>:<dag>` | whatsapp | per gesprek per dag: thema "N berichten (x in, y uit), HH:MM tot HH:MM", start = eerste bericht, minuten 0, personen = naam of "groep: naam" | leeg |
| `whatsapp-oproep:<oproep-ID>` | whatsapp | begin, minuten (afgerond), in of uit, video, met wie | leeg; gemist of zonder antwoord `buiten:gemist` |
| `telefoon:<ZUNIQUE_ID>` | telefoon | begin, minuten, in of uit, met wie; WhatsApp-oproepen in de iPhone-geschiedenis overgeslagen | leeg; gemist of zonder antwoord `buiten:gemist` |
| `dekking:<kanaal>:<dag>` | dekking | deze dag is gelezen | `buiten:dekking` |

Alles `prive = 1`, afdeling leeg. Een berichtsoort 6, 10 of 59 telt niet als bericht. Een gemiste oproep staat in de
tabel maar telt niet als gesprek (zelfde regel als Z10): de dagvaststelling telt alleen oproepen met duur.

**Dekking** van dag D alleen als D voorbij was toen de kopie gemaakt werd, en de bron zelf iets jonger dan het einde
van D toont (het nieuwste bericht of de nieuwste oproep). Zo is een dag van een Mac waarop WhatsApp niet draaide nooit
"0 berichten gezien", maar onbekend. Is het nieuwste bericht ouder dan 48 uur, dan een nood (WhatsApp op de Mac
ontvangt niets nieuws); bij de iPhone-oproepen na zeven dagen.

**Namen**: een gesprek heeft de naam die WhatsApp toont; een oproep de deelnemer, de oproepmelding in het gesprek of de
beller, opgezocht in het adresboek van WhatsApp (ContactsV2, de kopie van het iPhone-adresboek) of de naam van het
gesprek. Een iPhone-nummer via hetzelfde adresboek; een onbekend nummer staat er als nummer (Mehdi beslist). De
Mac-contacten blijven buiten (twee nummers meer, een extra bron met wisselende paden).

### Privé

- Namen alleen in de gesprekkentabel (alleen beheer). Hartslag, nood, werkverslag en kennis dragen geen naam en geen
  nummer: elke gelezen naam gaat ook in het masker van de agent (`ag.prive`).
- De klaarzet van De Dagbundelaar toont WhatsApp en telefoon alleen als "privé" met aantal en minuten (D5, ongewijzigd).

### Wat verdwijnt

`mac/whatsapp_wacht.py` (tellen van gekozen exports, v2.0) en zijn test. De exports en het instellingenbestand op de
Mac blijven staan; Mehdi beslist of ze weg mogen.

### Mehdi beslist (vraag van 26-10-2026)

1. De werkwijzen WhatsApp-wacht v3.0 en Belwacht v2.0 op het bord, met de kaart (label "De WhatsApp-wacht", cadans
   "elk uur als de Mac wakker is", draait op Mac).
2. Een onbekend nummer als nummer in de gesprekkentabel (aanbevolen), of alleen "onbekend nummer".
3. Groepsgesprekken tellen mee, met de naam van de groep (aanbevolen).
4. Volledige schijftoegang voor MacGesprekkenKopie (System Settings > Privacy & Security > Full Disk Access).
5. Xelion blijft voorlopig buiten de Belwacht.

### Antwoord op de ontwerplezing (v2.1, docs/codex/dagvaststelling-fase2-ontwerp-r1.md, "bouwen: nee")

| punt | antwoord in de code |
|---|---|
| P1 | de helper kopieert geen databank meer: hij leest de bronnen met vaste vragen (ATTACH, alleen lezend) in een databank in het geheugen en schrijft alleen de toegelaten kolommen weg (`gesprekken.sqlite`, 350 kB in plaats van 75 MB): berichten zonder tekst, ZSTANZAID alleen van een oproepmelding, oproepen, deelnemers, de gesprekken van het venster en alleen de contacten die bij een gesprek, oproep of nummer van het venster horen. Venster 62 dagen. De runner wist de uitvoer na het lezen. Test: geen tekstkolom in de vragen van module en helper, en geen geheime tekst in de uitvoer van een proefbouw |
| P2 | geen serialisatie van de bron meer: de vragen lopen binnen een leestransactie door SQLite, dus met de WAL. Test met een proefbouw (`-DBASIS_TEST`): een bericht dat alleen in de WAL staat (open schrijver, geen checkpoint) komt mee. Zonder -wal naast de bron (app gesloten) leest de helper immutable |
| P3 | `mijnagents/app.py`: de dagenpagina en de dagpagina tellen een chat (`zoom:chat:`, `whatsapp:`) niet als gesprek; de dagpagina zegt "N chats tellen niet als gesprek". Test met chat, beantwoorde en gemiste oproep en dekking samen |
| P4 | dekking van dag D alleen als D voorbij was bij de kopie, de bron die dag zelf een bericht of oproep toont, en daarna nog iets nieuws kreeg. Een dag zonder enig gegeven blijft onbekend. Test |
| P5 | in het uur dat bij de wintertijd twee keer voorkomt, draagt start de UTC-afstand (`02:30+01:00`); `dagvaststelling.gesprek_venster` leest die en geeft de vensters in UTC (Python vergelijkt twee tijden in dezelfde zone zonder fold). Test met beide klokwissels en een afspraak in dat uur |
| P6 | dezelfde oproep-ID binnen zes uur is een oproep (opnieuw verbonden), verder uit elkaar een andere met een eigen sleutel. Gemeten over de hele iPhone-geschiedenis (641 oproepen): alleen com.apple.Telephony (630) en com.apple.FaceTime (11); de Belwacht neemt alleen die twee, dus een WhatsApp-oproep kan er niet dubbel in |
| P7 | de stand op de Mac onthoudt de laatste gedekte dag; na een lange slaap leest de ronde vanaf daar, tot zestig dagen. De nachtronde van De Dagbundelaar haalt een dag buiten haar venster in als zijn dekkingsrij nieuwer is dan zijn laatste vaststelling (hoogstens zeven per nacht; `dagvaststelling-inhaal.json`). Werkwijze De Dagbundelaar 3.1 |
| P8 | N4 vergelijkt de ronde-ID van kennis en eindhartslag bij elke cadans voor whatsapp-wacht en belwacht (`controle_agenten.RONDE_ID_AGENTS`); zonder bevestiging zet de runner zijn hartslag altijd op fout (het slot houdt een tweede ronde op de Mac tegen). `mac/whatsapp_wacht.py` en zijn test zijn weg; de CI draait `tests/test_mac_gesprekken.py` |
| P9 | elke kopie hoort bij een aanvraag-ID die de runner net voor de vraag schrijft en de helper in zijn status terugzet; een andere ID is geen antwoord. Een ander schema is "onverwacht", een symlink in het bronpad ook, een ontbrekende bron "ontbreekt"; nooit een halve uitvoer. Teruglezen exact met dezelfde vingerafdruk als het bord opslaat (test door de echte `/api/gesprekken`). Toont de bron veel minder rijen dan het bord kent (meer dan een vijfde, minstens vijf), dan markeert de ronde niets als vervallen en stopt ze |

Uitrol op de Mac: `mac/uitrol_mac_gesprekken.sh` (eigen worktree op origin/main, helper alleen opnieuw gebouwd als zijn
bron verandert, vier LaunchAgents; `aan` zet de twee wachten pas aan na de gecontroleerde eerste ronde).

### Antwoord op de bouwcontrole r2 (v2.2, docs/codex/dagvaststelling-fase2-bouw-r2.md, "live: nee")

| punt | antwoord in de code |
|---|---|
| Q1 | een tweede iPhone-oproep met dezelfde ID krijgt haar tijdstip in de sleutel (`telefoon:ID-<seconden>`); `schrijf_en_lees_terug` weigert twee rijen met dezelfde sleutel. Test in de module en door de echte `/api/gesprekken` |
| Q2 | stoppen zonder te markeren als de bron niets meer toont terwijl het bord rijen kent, of als minstens vijf rijen en meer dan een vijfde van het bord tegelijk verdwijnen; alleen dekking telt niet als gegeven. Test op de grenzen (5 van 5, 1 van 1, 5 van 20, 5 van 100, 4 van 10) |
| Q3 | de helper opent de bron zelf langs de mappen zonder symlink, onthoudt apparaat en inode, en vergelijkt die na de ATTACH met het bestand dat SQLite echt open heeft (SQLITE_FCNTL_FILE_POINTER); een ander bestand is "onverwacht", veilig dicht. Racetest in de proefbouw (een `.wissel` neemt na de controle de plaats van de bron in) |
| Q4 | de uitvoer draagt zelf de aanvraag-ID (`META aanvraag`); de runner leest ze alleen als die gelijk is aan zijn vraag. Test met een uitvoer van een andere start |
| Q5 | `mac_gesprekken.lees_veilig`: een leesfout gaat alleen als soort verder (`ValueError`), nooit met een waarde uit de bron. Test met een naam in een tijdveld |
| Q6 | `mac_gesprekken.eindcontrole`: zonder bevestiging een hartslag fout met de vaste nood "Bord heeft de ronde niet bevestigd: hartslag of kennis ontbreekt" (de open noden blijven), en ook die fout wordt teruggelezen. Test |
| Q7 | `uitrol_mac_gesprekken.sh`: de vorige helper en LaunchAgents blijven bewaard (`terug`); een nieuwe helper of gewijzigde wacht zet de wachten uit; `proef` doet de toegangsproef onder launchd met het exacte programma en een eerste ronde van elke wacht en schrijft een proefbewijs voor precies die cdhash en commit; `aan` weigert zonder dat bewijs |
| Q8 | de dagenpagina en de dagpagina tellen alleen rijen van een gespreksbron die geen chat is (`telt_als_gesprek`): ook mail telt niet meer. De dagpagina zegt "N mails en chats tellen niet als gesprek". Test |

### Antwoord op de bouwcontrole r3 (v2.3, docs/codex/dagvaststelling-fase2-bouw-r3.md, "live: nee")

Vooruitgang: Q2, Q3, Q5 en Q8 waren opgelost; R1 tot R6 gaan dieper op Q1, Q4, Q6 en Q7.

| punt | antwoord in de code |
|---|---|
| R1 | elke oproepsleutel draagt haar eigen begin: `telefoon:<ZUNIQUE_ID>-<seconden>` en `whatsapp-oproep:<oproep-ID>-<seconden van het begin>`. De groepering van WhatsApp-gebeurtenissen loopt over alles wat de helper gaf (62 dagen), de rijen alleen over het venster (hoogstens 60): de sleutel verandert niet als het venster opschuift. Test met twee opeenvolgende vensters, ook een oproep die over middernacht opnieuw verbonden werd. Het voorvoegsel (het contract met De Dagbundelaar) blijft |
| R2 | de helper schrijft per aanvraag een eigen uitvoer (`gesprekken-<aanvraag>.sqlite`) en ruimt wat ouder is dan tien minuten op; de runner zet ze eerst om naar een naam die alleen hij kent (`.lezen-<aanvraag>.sqlite`) en leest dan pas. Test met twee aanvragen na elkaar en de opruiming |
| R3 | de hartslag fout van de eindcontrole draagt de ronde-ID; `bordstand.py --ronde` geeft ook de open noodteksten van de agent; de eindcontrole bevestigt fout, ronde-ID en nood samen. Test met een fout die niet aankwam, een oude fout en een fout zonder nood |
| R4 | een uitrol zet eerst de wachten uit (en wist het proefbewijs), elke keer, ook bij alleen gewijzigde Python-code; daarna blijven ze uit tot `proef` en `aan` |
| R5 | een bezette wacht eindigt met 75; een geslaagde ronde drukt haar ronde-ID af; `proef` eist per wacht exit 0, precies een ronde-ID en die ID in eindhartslag en kennis op het bord (`mac_gesprekken.proefronde`). Test |
| R6 | de uitrol bewaart de vorige versie als geheel (commit, helper, BRON_SHA256, alle LaunchAgents) en `terug` zet dat geheel terug, ook een LaunchAgent die er toen niet was. Test met nagebootste launchctl, codesign en cc: drie uitrollen na elkaar, `aan` geweigerd zonder proefbewijs, terug naar versie 2, `aan` met een proefbewijs voor precies die versie |

### Antwoord op de bouwcontrole r4 (v2.4, docs/codex/dagvaststelling-fase2-bouw-r4.md, "live: nee")

Vooruitgang: R1 tot R6 waren in hun gewone paden opgelost; S1 tot S4 zijn randgevallen bij overstap en uitrol.

| punt | antwoord in de code |
|---|---|
| S1 | gemeten op 26-10-2026: de gesprekkentabel heeft nog geen enkele rij `whatsapp`, `telefoon` of `dekking`, dus live bestaan geen oude sleutels. De overstap is toch expliciet: een rij van het kanaal met een andere sleutelvorm dan `HUIDIGE_SLEUTEL` komt van een oudere versie en wordt vervallen, buiten de rem. En de rem gaat nu voor het schrijven: een halve bron schrijft en markeert niets. Test met vijf oude en vijf nieuwe rijen (geen dubbele telling) en een halve bron (geen schrijfoproep) |
| S2 | `ruim_op` herkent alleen de eigen namen (`gesprekken.sqlite`, `gesprekken-<32 hex>.sqlite`, `.lezen-<32 hex>.sqlite`). Test: `gesprekken-archief.sqlite` blijft staan |
| S3 | `wachten_echt_uit`: na de bootout moet elke wacht echt uit launchd zijn, anders wisselt niets; de wissel loopt met de rondesloten van beide wachten vast (`lockf`, hetzelfde flock als `mac_gesprekken.slot`). Test met een wacht die geladen blijft en met een vastgehouden rondeslot |
| S4 | een slot voor alle opdrachten behalve controleer (`.uitrol.lock`): installeer, proef, aan, uit en terug lopen nooit samen. Test met een vastgehouden uitrolslot |

### Antwoord op de bouwcontrole r5 (v2.5, docs/codex/dagvaststelling-fase2-bouw-r5.md, "live: nee")

Vooruitgang: S2, S3 en S4 opgelost; T1 (middel) en T2 (laag) blijven.

| punt | antwoord in de code |
|---|---|
| T1 | geen uitzondering meer voor een andere sleutelvorm: elke verdwenen rij telt in de rem, die voor het schrijven staat. Er staat live geen enkele WhatsApp-, telefoon- of dekkingsrij (gemeten 26-10-2026), dus een overstap is er niet; verschijnt ooit zo'n rij, dan stopt de ronde met de nood en beslist een mens. Test: vijf rijen met een andere vorm (ook `telefoon:ID-42`) tegenover een volle, lege en halve bron schrijven en markeren niets; een verdwenen rij van honderd wordt gewoon vervallen |
| T2 | `UITROL_SLOT` alleen volstaat niet meer: elke opdracht behalve controleer kijkt of het uitrolslot echt vastzit (`lockf -t 0` moet falen), en de interne wissel ook of beide rondesloten vastzitten. Test: `__installeer` en `__terug` rechtstreeks met `UITROL_SLOT=1` worden geweigerd |

### Antwoord op de bouwcontrole r6 (v2.6, docs/codex/dagvaststelling-fase2-bouw-r6.md, "live: nee")

Vooruitgang: T1 opgelost; U1 (middel, nieuw bij de controle van het geheel) en U2 (laag) blijven.

| punt | antwoord in de code |
|---|---|
| U1 | wat de wachten niet tellen, verlaat de bron ook niet: de helper neemt alleen gesprekken met een persoon of een groep (ZSESSIONTYPE 0 en 1, ook voor het nieuwste bericht) en alleen gewone oproepen en FaceTime (ook voor de nieuwste oproep en de contacten bij hun nummers); van andere apps alleen het aantal (`META andere_apps`). Gemeten op de echte databank: alleen sessies 0 en 1 in de uitvoer, 0 oproepen van andere apps. Test met een status met bericht en contact, en een WhatsApp-oproep met contact in de iPhone-geschiedenis: geen van hun namen, nummers of ID's staat in de uitvoer |
| U2 | elke uitrol maakt een eigen sleutel (`UITROL_SLEUTEL`, 16 willekeurige bytes) die alleen het eigen proces en zijn kinderen kennen; ze staat in `.uitrol.sleutel` zodra het uitrolslot vastzit, en de interne wissel loopt alleen met precies die sleutel en alle sloten vast. Test: een directe interne aanroep terwijl een (nagebootste) andere uitrol alle sloten houdt, wordt geweigerd |

### Antwoord op de bouwcontrole r7 (v2.7, docs/codex/dagvaststelling-fase2-bouw-r7.md, "live: nee")

Vooruitgang: U1 opgelost; V1 (middel, nieuw) en V2, V3 (laag).

| punt | antwoord in de code |
|---|---|
| V1 | `dagbundelaar.gedekte_dagen`: een dekkingsrij met `buiten:vervallen` bewijst niets meer; ook de inhaalbeurt van de nacht kijkt alleen naar actieve dekking. Test over de hele route: drie dagen oproepen, dan verdwijnen de oproepen van een dag; de ronde markeert ze en de dekking als vervallen, en het dagoverzicht toont die dag als "telefoon: onbekend (onbekend voor deze dag)" |
| V2 | laag, bewust zo gelaten: de sleutel en de sloten houden een vergissing tegen (twee uitrollen of een uitrol tijdens een proef). Een proces van dezelfde gebruiker dat dat bewust omzeilt, kan de worktree evengoed rechtstreeks wijzigen; daartegen beschermt geen slot in een script. De echte grens is de helper: die voert geen code uit de worktree uit, en zijn toestemming hangt aan zijn cdhash |
| V3 | de helper geeft van oproepen van andere apps alleen het tijdstip (`ANDERE_APPS`, geen nummer of dienst); de runner telt ze in zijn eigen venster. Test |

### Antwoord op de bouwcontrole r8 (v2.8, docs/codex/dagvaststelling-fase2-bouw-r8.md, "live: nee")

Vooruitgang: V1 en V3 opgelost, de reden voor V2 (laag) aanvaard; W1 (middel) blijft.

| punt | antwoord in de code |
|---|---|
| W1 | `/api/gesprekken/koppel` zet `ts` als een koppeling iets verandert (zoals een upsert), en laat ze staan als er niets verandert; alleen De Dagbundelaar leest die ts (gemeten in de code). De inhaalbeurt kijkt naar elke wijziging van een dekkingsrij, ook een vervallen verklaring: een oudere, al vastgestelde dag die zijn dekking verliest, wordt in de nacht opnieuw vastgesteld en toont dan "onbekend". Tests: de ts in de API (wel en niet veranderd), en de route met een vastgestelde dag van 26 dagen terug (inhaalkeuze met de echte functie, dan de dagtekst) |
