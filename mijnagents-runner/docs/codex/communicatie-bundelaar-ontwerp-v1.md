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

1. Mail per persoon alleen voor bekende mensen: een collega uit kern of iemand die ook in een Zoom-, Fathom- of
   Plaudrij voorkomt. Mehdi's keuze noemde geen termijn; de techniek neemt de laatste negentig dagen (`BEKEND_DAGEN`),
   anders blijft een vaste klant die deze week alleen mailde overige mail. Een andere termijn is Mehdi's keuze. De rest is een aantal "overige mail".
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

## Verwerking ontwerplezing Codex (26-10-2026)

| punt | ernst | verwerking |
|---|---|---|
| CB01 privé per gesprek | hoog | privé is de OF over de rijen van een gesprek (dubbel_van en sessie), zoals `regisseur._prive_sessies`; lezing tot en met vandaag; test `test_prive_geldt_voor_het_hele_gesprek` |
| CB02 sleutel prive en De Dagbundelaar | hoog | veld `prive_per_kanaal`; De Dagbundelaar slaat soort `communicatie` over (geen dossier, geen toewijsvraag) |
| CB03 volgorde | hoog | cron 06:35 (voor De Levenscoach 06:45) en 13:35 (na de keten van 13:00); de weekspiegel ziet de bijgewerkte week |
| CB04 opgepakt item blijft oud | hoog | niemand pakt het item op (De Dagbundelaar slaat het over, De Levenscoach leest alleen), dus het volgt de bron; elke dag van het venster krijgt een item, ook zonder contact |
| CB05 werkwijze op het bord | hoog | werkwijze v2 gaat met `werkwijze_naar_bord.py --zet` op het bord voor de eerste ronde |
| CB06 groepschat | middel | Zoom-chat zonder adres in de sleutel is `groepschat`: alleen een aantal, maakt niemand bekend |
| CB07 voornaam | middel | eigen herkenning: exacte naam of adres, of een losse voornaam die maar een collega draagt; Mehdi alleen als "Mehdi", "Mehdi Chegini" of zijn kernrij |
| CB08 kern | middel | kern leeg: nood en niets klaargezet; de nood "minder dan twee kanalen" is weg |
| CB09 controleerbaar | middel | elk item wordt teruggelezen op uniek; `--droog --zaad` toont de items; het privélek in `/dagen` van het bord is een ander onderdeel en staat als vervolg |

## Verwerking controle 1 (26-10-2026)

| punt | ernst | verwerking |
|---|---|---|
| CB01 keten van dubbels | hoog | `prive_gesprekken`: een gesprek is de hele groep rijen die via dubbel_van of sessie aan elkaar hangen; test `test_prive_over_een_keten_van_dubbels` |
| CB04 opgepakt item | hoog | elk item gaat met `revisie: true`: het bord werkt ook een opgepakt item bij en bewaart de oude versie in `klaarzet_revisie` |
| CB03/CB05 cron en bordtekst | middel | bij de eerste ronde: werkwijze v2 met `werkwijze_naar_bord.py --zet`, daarna `controle_agenten.py`; de cron pas na Mehdi's ja |
| CB09 teruglezing | laag | ook voor, soort en sleutel vergeleken |

## Verwerking controle 2 (26-10-2026)

| punt | ernst | verwerking |
|---|---|---|
| CB10 mail van iemand uit een privégesprek | hoog | wie ooit in een privégesprek zat, is voor mail geen bekende (een collega blijft bekend); test `test_wie_ooit_prive_was_is_geen_bekende_voor_mail` |
| CB11 correctie na zeven dagen | hoog | elke dag waarvoor ik al een item zette (`SQL_EERDER` op klaarzet), wordt elke ronde mee herzien; test `test_oudere_dag_met_item_wordt_herzien` |
| CB12 oude inhoud in klaarzet_revisie | middel | geen revisie meer: niemand pakt het item op, dus het bord werkt het bij zonder kopie; test bewaakt dat De Levenscoach niets oppakt |
| CB13 cron en bordtekst | middel | live stap: werkwijze v2 op het bord, teruggelezen, eerste ronde en `controle_agenten.py`; cron na Mehdi's ja |

## Verwerking controle 3 (26-10-2026)

| punt | ernst | verwerking |
|---|---|---|
| CB14 privé dubbel en mail | hoog | namen van dubbels (niet buiten:) tellen mee voor bekend en ooit privé; test `test_prive_dubbel_en_mail_op_dezelfde_dag` |
| CB15 termijn voor bekend | middel | geen zevendaagse keuze van Mehdi: zijn optie noemde geen termijn. Negentig dagen staat nu uitdrukkelijk bij keuze 1 en in de werkwijze; een andere termijn is zijn beslissing |
| CB16 onbekend kanaal | middel | telt als kanaal `overig`, zonder namen, met nood |
| CB04 opgepakt | middel | de teruglezing eist status klaar; een opgepakt dagitem geeft een nood. Niemand pakt het vandaag op (tests op De Dagbundelaar en De Levenscoach) |

## Verwerking controle 4 (26-10-2026): ontwerp herbekeken

Drie rondes na elkaar vonden een naam die via een leesgrens op datum ontsnapte (CB01, CB14, CB17, CB18). Stopregel
punt 4.7: de oorzaak is het venster zelf, niet het geval. Nieuw ontwerp: de runner leest de hele gesprekkentabel
(1508 rijen op 26-10-2026), zonder datumgrens.

| punt | ernst | verwerking |
|---|---|---|
| CB17 privé ouder dan negentig dagen | hoog | hele tabel gelezen: wie ooit privé was, is voor mail geen bekende |
| CB18 dubbel van de nacht ervoor | hoog | hele tabel gelezen: de keten van dubbels en sessies is altijd volledig |
| CB19 bekend buiten negentig dagen | middel | bekendheid voor mail alleen uit gesprekken vanaf vandaag min negentig dagen |
| CB04 opgepakt item | middel | nieuw veld `vervang` in `/api/klaarzet` (mijnagents/app.py): ook een opgepakt item volgt de bron, zonder kopie in klaarzet_revisie; test in mijnagents/test_klaarzet_revisie.py |
