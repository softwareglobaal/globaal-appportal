# Ontwerp: de dagvaststelling (De Dagbundelaar, uitbreiding)

Versie 1.3, 26-10-2026. Claude 2. v1.0 en v1.1 gingen naar Codex (docs/codex/dagvaststelling-ontwerp-r1.md en -r2.md,
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
   postvakken. Een map die niet leesbaar is, of een Mac-kopie ouder dan `BRON_VERS_UREN`, maakt de telling van dat
   postvak "onvolledig" met de reden (D8). Hotmail is privé.
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
- Mail: onleesbare verzonden-map en oude Mac-kopie geven onvolledig; dezelfde Message-ID in twee postvakken telt een keer.
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
| E3 | persoon van de afspraak: het stuk na de code tussen haken en de gasten van buiten, nooit wat voor de code staat (de eigenaar) en nooit Mehdi; `lees_titel().klant` is niet betrouwbaar ('Catalin: PL'). Een gesprek hoort alleen via die persoon bij een afspraak; overlap zonder persoon is hoogstens een aanwijzing en het gesprek blijft onder niet gepland |
| E4 | ontvangen mail rechtstreeks uit de mappen die de mailwachten lezen (leesdekking van deze ronde gekend), aangevuld met wat de wachten registreerden en wegsorteerden; per postvak eerlijk, het totaal ontdubbeld per Message-ID; onvolledig met reden. De mailcode draait als kind met /usr/bin/python3 (yaml), zoals de mailwachten |
| E5 | geen watermerk: de nachtronde herberekent veertien dagen volledig (agenda en mail een keer per venster gelezen), alleen een andere vaste inhoud geeft een versie |
| E6 | de hash dekt de vaste inhoud zonder het blok over de vaststelling; teruglezen vergelijkt bestand en borditem met wat geschreven werd; het Dropbox-bewijs vergelijkt de sha256 van het bestand |

Gesprekken worden geteld als een totaal over Zoom, Fathom en Plaud (elk gesprek een keer), met hoeveel met opname en
hoeveel alleen in Zoom: een Zoom-gesprek met Fathom-opname staat in de tabel als leidende Fathom-rij.

Droge proef op de VM (26-10-2026, dag 22-10, schrijven alleen naar /tmp, geen bordoproep): 24 s; Ternat aanwijzing (auto
14:31 tot 16:07), Leuven, de twee privéafspraken en het interne overleg van 23:00 geen spoor; 12 gesprekken en 2 bezoeken
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
