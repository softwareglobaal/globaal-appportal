# De Communicatiebundelaar: ontwerp v1 (26-10-2026)

Aanleiding: tweede driehoeksoverleg over De Zoomwacht (26-10-2026, X4/X5). De Zoomwacht levert aan
`communicatie-bundelaar` (veld `levert_aan`), maar die draait als skelet (`wacht_skelet.py`, cron 07:20) met de nood
"Eigen runner nog te bouwen". Niemand leest de uitvoer.

## Fase 1. Inventaris: uitbreiden of nieuw

De agent bestaat al op het bord (`communicatie-bundelaar`, afdeling prive-communicatie, actief, VM). Geen nieuwe agent:
deze runner vervangt het skelet. De Dagbundelaar (per dossier) en De Regisseur (dagtelling Zoom-chat) lezen de
gesprekkentabel voor iets anders: geen overlap met "per persoon, per kanaal".

## Fase 2. Bronproef `gesprek_log` (26-10-2026, alleen lezen)

| bron | soort (uniek) | rijen | minuten 0 | privé | dubbel_van |
|---|---|---|---|---|---|
| fathom | fathom:<id> | 693 | 27 | 30 | 17 fathom:, 4 buiten: |
| zoom | zoom:meeting:<uuid> | 239 | 0 | 66 | 95 fathom: |
| zoom | zoom:chat:<sleutel>:<dag> | 279 | 279 | 12 | 0 |
| mail | mail:<message-id> | 278 | 278 | 0 | 0 |
| plaud | plaud:<id> | 19 | 0 | 0 | 0 |

Soorten in `personen` (komma-gescheiden): collega's met afdeling tussen haakjes ("Voornaam (Architecture)"), Mehdi in
695 rijen ("Mehdi", "Mehdi Chegini", "Mehdi (Afspraken)"), externen met naam, onbekende sprekers ("Speaker 1",
"Externe deelneemster (...)"), bij mail de afzender: een naam, een adres, of een firma of robot (de top tien van mail is
grotendeels firma's en meldingen). `prive` is een vlag; ook afdeling `prive` of `privé` geldt als privé (regel van De
Regisseur, RZ3-01). Fathom zonder Zoom-sessie: 581 van 693.

## Fase 3. Keuzes van Mehdi (26-10-2026, in de chat)

1. Mail per persoon alleen voor bekende mensen: een collega uit kern (`organisatie.herken`) of iemand die in het
   venster ook in een Zoom-, Fathom- of Plaudrij voorkomt. De rest is een aantal "overige mail".
2. Uitvoer: een klaarzet-item per dag voor Mehdi (soort `communicatie`). De Levenscoach (`voor=mehdi`) en De
   Dagbundelaar lezen het vanzelf mee. Werkverslag met alleen aantallen.
3. Kanaal: Zoom-meeting en Fathom zijn `video`, Zoom-chat is `chat`, mail is `mail`, Plaud is `ter plaatse`. Een
   gesprek in Zoom en Fathom telt een keer (de telregel `dubbel_van`).

## Opdrachtkaart (uit rol, mandaat, werkwijze v1 en de keuzes hierboven)

1. Probleem: de kanaalagents schrijven elk hun rijen, niemand legt ze per persoon naast elkaar.
2. Voor: Mehdi privé (afdeling prive-communicatie), als bron voor De Levenscoach.
3. Nu: skelet, uitvoer van De Zoomwacht ongelezen.
4. Bron: `gesprek_log` op het bord (alleen lezen via `bord.db_lees`), personen uit kern.
5. Al gemaakt: werkwijze v1 (10-09-2026) op het bord.
6. Goed: "Voornaam (Architecture)" in Zoom en "Voornaam" in Fathom is een persoon, video, twee contacten. Fout: een naam uit
   een privérij op het bord of in het item; Anthropic als persoon; een Zoom-meeting en haar Fathom-opname twee keer.
7. Te zien: klaarzet-item per dag voor Mehdi, werkverslag op de kaart.
8. Volgende stap: geen voorstel; de agent beschrijft, De Levenscoach duidt.
9. Mag: lezen en klaarzetten. Nooit: schrijven in de gesprekkentabel, inhoud (thema, waarom, link, archief) gebruiken,
   privénamen tonen.
10. Mehdi beslist: wie als persoon telt (keuze 1), wat er met de uitkomst gebeurt.
11. Ritme: elke ochtend 07:20 na de kanaalagents; nood als de tabel onleesbaar is of minder dan twee kanalen rijen
    hebben in het venster.

Bewust open: wie begon, toon, weekpatronen (werkwijze v1 punt 2). Daar is geen meting voor zonder inhoud te lezen.

## Ontwerp

- Venster: de zeven Brusselse dagen voor vandaag (niet vandaag zelf, die is nog bezig). Elke ronde rekent ze opnieuw;
  een item dat nog niet is opgepakt volgt de bron (upsert op `uniek` = `communicatie:dag:<JJJJ-MM-DD>`), een opgepakt
  item blijft staan (geen `revisie`).
- Lezen: `bord.db_lees("SELECT uniek, bron, datum, minuten, personen, prive, afdeling, dubbel_van FROM gesprek_log
  WHERE datum BETWEEN ? AND ?")`. Nooit `thema`, `waarom`, `link`, `archief`, `project`. `BordOnbekend` is een nood en
  de ronde stopt zonder klaarzet: onbekend is niet leeg.
- Telregel: een rij met niet-lege `dubbel_van` telt niet (gelijk aan het dagenoverzicht van het bord, Z10).
- Privé: `prive` of afdeling `prive`/`privé`. Een privérij telt als aantal (contacten, minuten) per kanaal, zonder
  namen. Een persoon uit een privérij komt ook niet in de lijst "bekende mensen" voor mail.
- Kanaal uit het voorvoegsel van `uniek`: `zoom:chat:` chat, `zoom:` en `fathom:` video, `plaud:` ter plaatse, `mail:`
  mail. Een onbekend voorvoegsel telt als kanaal `overig` en geeft een nood.
- Personen: splitsen op komma, tekst tussen haakjes weg, Mehdi weg (via kern en de vaste vormen "Mehdi"), onbekende
  sprekers ("Speaker N", "Externe ...", "onbekend") als aantal `onbekende deelnemers`. Een collega uit kern krijgt zijn
  kernnaam, zodat "Voornaam (Architecture)" en "Voornaam" een persoon zijn. Mail: alleen bekende mensen (keuze 1).
- Per dag en persoon: per kanaal aantal contacten en minuten. Minuten alleen bij video en ter plaatse; chat en mail
  hebben geen duur (geen 0 maar weggelaten).
- Item: `{voor: mehdi, soort: communicatie, sleutel: <dag>, uniek: communicatie:dag:<dag>, titel: "Communicatie <dag>:
  N contacten met M personen, K kanalen", inhoud: JSON {datum, personen: [{naam, kanalen: {video: {aantal, minuten}}}],
  prive: {kanaal: {aantal, minuten}}, overige_mail, onbekende_deelnemers}}`. Geen dag met nul rijen: geen item.
- Werkverslag (`r.detail`): alleen aantallen. Noden zonder getal.
- Gedeelde ronde: `with ag.ronde("communicatie bundelen") as r:` in het runnerbestand; grenzen via `bord.grenzen`.
