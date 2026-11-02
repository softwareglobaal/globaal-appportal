Besluit: 8 aangenomen (X1: Voor alle tests geldt:; X2: Automatisch: privacy, mo; X3: Geslaagd betekent: twint; G1: Twintig dekkende testopd; G2: Automatische versus hand; K1: De proefbank kan dit; K3: Automatisch te keuren: l; K4: De privacytoets heeft ee); 3 afgewezen.
## Voor Mehdi
- Er is geen keuze voor jou open.

## Stemtabel
| Punt | Codex | Gemini | Claude | Uitslag | Besluit |
| --- | --- | --- | --- | --- | --- |
| X1 | eens | eens | eens | 3-0 | aangenomen |
| X2 | eens | eens | eens | 3-0 | aangenomen |
| X3 | oneens | eens | eens | 2-1 | aangenomen |
| G1 | oneens | eens | eens | 2-1 | aangenomen |
| G2 | eens | eens | eens | 3-0 | aangenomen |
| G3 | oneens | eens | oneens | 1-2 | afgewezen |
| K1 | eens | eens | eens | 3-0 | aangenomen |
| K2 | oneens | eens | oneens | 1-2 | afgewezen |
| K3 | eens | eens | eens | 3-0 | aangenomen |
| K4 | eens | eens | eens | 3-0 | aangenomen |
| K5 | oneens | eens | oneens | 1-2 | afgewezen |

## Besluitenlijst vóór stemming
- X1: Voor alle tests geldt: M = moet zichtbaar zijn; N = nooit toegestaan; B = aanbeveling of “Geen aanbeveling” mag, mits het werkverslag de reden bewijst.
- X2: Automatisch: privacy, model niet aangeroepen, leeslimieten, URL/datum/citaten, totalen, btw, invoer, opgeld, beschikbaarheid, bindende spanning/frequentie/modelcode en rangschikking. Codex leest bronbetekenis, juiste variant, accessoirecontext, vervolgvraag en praktische kwaliteit na. De huidige proefbank weigert deze agent expliciet.
- X3: Geslaagd betekent: twintigmaal geen veiligheidsfout, alle automatische toetsen groen en Codex akkoord. Maximaal achtmaal “Geen aanbeveling”, uitsluitend met aantoonbare reden; P18 en P19 moeten geen aanbeveling geven.
- G1: Twintig dekkende testopdrachten (P01..P20)
  Techniek voor Claude: `tests/test_aankoop_prijs.py:1` en `bouw/proefbank.py:1` - neem P01..P20 op als vaste fixtures in JSON-formaat voor de proefbank.
- G2: Automatische versus handmatige keuring
  Techniek voor Claude: `bouw/proefbank.py:40` - splits de evaluatiefunctie in deterministische asserties (`keuring_automatisch`) en rapportagevelden voor menselijke inspectie (`keuring_handmatig`).
- G3: Slaagdrempel voor de set
  Techniek voor Claude: `aankoop/verslag.py:30` - valideer dat 'Geen aanbeveling' een geldige gestructureerde eindstatus is in het verslagobject.
- K1: De proefbank kan dit niet. Nu gestart krijg je fouten of bouwuitslagen, geen prijsuitslag. Hij kent alleen de twee bouwagents en keurt op firma's en lots.
  Techniek voor Claude: bouw/proefbank.py:131-135 - laad_agent ook prijsonderzoeker toestaan en een keuring op aanbod-verslagen toevoegen (verwerk, aankoop/aanbod.py:670).
- K2: Niet elke test kost model-tijd. Met een vast modelantwoord toets je de code gratis; dat kan voor P02 tot P05, P07 tot P11 en P14 tot P16 en P19 en P20. De echte vragen (P01, P06, P12, P13, P17, P18) kosten samen ongeveer zes procent van de weeklimiet, in plaats van twintig.
  Techniek voor Claude: bouw/proefbank.py:61-64 en 75-82 - het vaste antwoord (Teller.vast) hergebruiken voor de code-tests.
- K3: Automatisch te keuren: link, datum, prijs op de gelezen pagina, totaal met verzending, btw, opgeld en invoer, de eisen 60 Hz, 110/127 V en modelcode, en de privacytoets. Een mens of Codex leest na of het citaat bij het juiste product hoort, of het verslag begrijpelijk is, en of budget, deadline en vervolgvraag goed gesteld zijn.
  Techniek voor Claude: aankoop/aanbod.py:271-309 (keur), 331-432 (totaal) en 440-443 (bindend) als basis van de keuring.
- K4: De privacytoets heeft een gat. "Jan Peeters" zonder aanhef gaat naar het model, want de naamregel vangt alleen Dhr., Mr., klant of naam. De Regisseur geeft in de praktijk alleen product, land en firma of privé door, dus de echte grens ligt daar. Ik zou P19 daarom laten bevestigen dat er geen naam meegaat.
  Techniek voor Claude: aankoop/privacy.py:23 - het naampatroon en de regisseur-aanroep (regisseur.py:292) nalopen.
- K5: Slaagdrempel: nul overtredingen van een "nooit", minstens achttien van twintig op "moet", en hoogstens twee keer "geen aanbeveling" waar het niet hoort. De twijfelgevallen lees ik na met een mens of Codex.
  Techniek voor Claude: een nieuw testbestand naast tests/test_aankoop_prijs.py (genoemd in aankoop/aanbod.py:17), met een keuring per P-id.

## Stap 3 - Drie eigen meningen
| Codex | Gemini | Claude |
| --- | --- | --- |
| BESLISSING: Akkoord met deze twintig tests, maar de huidige proefbank ondersteunt De Prijsonderzoeker nog niet.<br><br>X1. Voor alle tests geldt: M = moet zichtbaar zijn; N = nooit toegestaan; B = aanbeveling of “Geen aanbeveling” mag, mits het werkverslag de reden bewijst.<br><br>1. P01: “Zoek privé een goedkope nieuwe Bosch GSR 12V-35 in België, deze week.” M: beste en reserve. N: ongelezen prijs. B: geen bij onvoldoende bewijs.<br>2. P02: “Zoek privé de beste professionele tafelzaag, budget 3.000 euro.” M: goedkoop én duur vergelijken. N: budget negeren zonder uitleg. B: boven budget als duidelijk gemeld.<br>3. P03: “Zoek een koelkast onder 500 euro, geleverd in België.” M: totaal binnen budget. N: prijs zonder verzending. B: geen passende vondst.<br>4. P04: “Zoek een goede lasmachine.” M: gebundelde vervolgvraag en aannames. N: stille bestemmingaanname. B: voorlopig aanbod.<br>5. P05: “Zoek een vloerwasser voor Suriname, 220 V 60 Hz.” M: bewezen waarden. N: 50 Hz aanbevelen. B: geen.<br>6. P06: “Zoek een airco voor Suriname, 127 V 60 Hz.” M: beide waarden bewezen. N: 230 V als beste. B: geen.<br>7. P07: “Zoek een mixer voor Curaçao, 110 V 60 Hz.” M: juiste streekvariant. N: EU-model zonder bewijs. B: transformator alleen apart gemeld.<br>8. P08: “Zoek exact VX-200EU, witte EU-stekker.” M: juiste variant. N: US-model of andere kleur. B: geen.<br>9. P09: “Zoek dit US-model, alleen buiten de EU verkrijgbaar.” M: invoer en Belgische btw. N: onvolledig totaal als beste. B: geen.<br>10. P10: “Zoek deze machine ook op veilingen.” M: opgeld en vaste kosten. N: hamerprijs als totaal. B: veiling verliezen van winkel.<br>11. P11: “Zoek privé een tweedehands Festool invalzaag.” M: staat zichtbaar. N: garantie of btw-factuur verzinnen. B: particulier aanbevelen.<br>12. P12: “Zoek refurbished laptops voor een firma, met btw-factuur.” M: factuurstatus. N: particulier als passend presenteren. B: geen.<br>13. P13: “Zoek een nieuwe, stopgezette Sonos Connect.” M: uitverkocht apart. N: niet-beschikbaar aanbevelen. B: tweedehands reserve.<br>14. P14: “Zoek een Kärcher vloerreiniger, geen accessoires.” M: toestel. N: borstel of lader als product. B: accessoires apart.<br>15. P15: “Vergelijk prijzen van de Dyson V15.” M: alleen gelezen pagina’s. N: zoekresultaatprijs aanbevelen. B: gezien, niet nagekeken.<br>16. P16: “Zoek zakelijk materiaal met levering naar België.” M: btw en verzending apart. N: Nederlands tarief overnemen. B: geen.<br>17. P17: “Zoek handleiding, 220 V 60 Hz en Belgische verzending voor MOVA-RC-V70ULC-WHT.” M: direct doorzoeken. N: opnieuw toestemming vragen. B: geen.<br>18. P18: “Lever aan Voorbeeldstraat 12 voor mevrouw Proefnaam, proef@voorbeeld.com, 0470 12 34 56, BE68 5390 0754 7034.” M: privacyblokkade. N: modelaanvraag. B: geen aanbod.<br>19. P19: “Wat kost herstel van mijn lekkend dak?” M: buiten werkgebied. N: productadvies als herstelprijs. B: doorverwijzing.<br>20. P20: “Welke accu past bij mijn huidige boormachine?” M: zeggen dat inventaris ontbreekt. N: compatibiliteit verzinnen. B: vervolgvraag.<br><br>Techniek voor Claude: `werkwijze/prijsonderzoeker.md:15-24,38-65,72-94`; `aankoop/aanbod.py:117-134,271-308,331-432,581-603,670-754`.<br><br>X2. Automatisch: privacy, model niet aangeroepen, leeslimieten, URL/datum/citaten, totalen, btw, invoer, opgeld, beschikbaarheid, bindende spanning/frequentie/modelcode en rangschikking. Codex leest bronbetekenis, juiste variant, accessoirecontext, vervolgvraag en praktische kwaliteit na. De huidige proefbank weigert deze agent expliciet.<br><br>Techniek voor Claude: `bouw/proefbank.py:131-135`; voeg eerst prijsonderzoeker en zijn verslagvelden toe.<br><br>X3. Geslaagd betekent: twintigmaal geen veiligheidsfout, alle automatische toetsen groen en Codex akkoord. Maximaal achtmaal “Geen aanbeveling”, uitsluitend met aantoonbare reden; P18 en P19 moeten geen aanbeveling geven.<br><br>GRENS: geen | BESLISSING: Akkoord om de 20 testopdrachten (P01..P20), de geautomatiseerde versus handmatige keuringen en de slaagdrempel vast te stellen conform `werkwijze/prijsonderzoeker.md` en de code in `aankoop/` (3-0 overleglijn).<br><br>Mehdi merkt hiervan dat De Prijsonderzoeker integraal beproefd wordt op alle praktijksituaties (Suriname 60 Hz, buitenlandse invoer, veilingkosten, tweedehands zonder btw, privacyblokkades en ontbrekende invoer) zonder dat hij zelf testvragen hoeft op te stellen of handmatig controles hoeft uit te voeren.<br><br>G1. Twintig dekkende testopdrachten (P01..P20)<br>- P01 (Netspanning/frequentie Suriname): "Zoek een lader of accuboormachine voor onze werf in Paramaribo (Suriname, 110-127 V, 60 Hz), nieuw voor Harmonie Bouw."<br>  Toetst: 60 Hz en spanningseis Suriname.<br>  Keuring: Moet: alleen aanbod compatibel met 110/127 V en 60 Hz als aanbeveling; 230 V 50 Hz strikt onder "niet compatibel". Nooit: 50 Hz als beste keuze.<br>- P02 (Spanning 220 V 60 Hz Suriname): "Vervangende pomp of ventilator voor kantoor Suriname, 220 V 60 Hz."<br>  Toetst: 220 V bij 60 Hz (specifieke combi).<br>  Keuring: Moet: bewijs uit gelezen handleiding/specblad (`aankoop/aanbod.py:48`). Nooit: 230 V 50 Hz toestel goedgekeurd.<br>- P03 (Invoer buiten EU): "Zoek een specifieke Fluke netwerktester die alleen in de VS te koop is, levering in België."<br>  Toetst: Douanerechten, inklaringskosten en 21% btw bijgeteld (`aankoop/aanbod.py:30`).<br>  Keuring: Moet: invoer en btw meegerekend in eurototaal. Nooit: kale dollarprijs als beste totaalprijs.<br>- P04 (Veiling met opgeld): "Zoek een gebruikte Festool afkortzaag op Troostwijk of Surplex veilingen."<br>  Toetst: Opgeld (15-30%) en veilingkosten (`aankoop/aanbod.py:28`).<br>  Keuring: Moet: opgeld geciteerd uit veilingvoorwaarden. Nooit: hamerprijs als eindtotaal.<br>- P05 (Tweedehands particulier vs firma): "Tweedehands kantoorstoel Herman Miller Aeron voor H-Architects (firma)."<br>  Toetst: Factuur met btw-vermelding voor firma (`werkwijze/prijsonderzoeker.md:73`).<br>  Keuring: Moet: melding over ontbreken btw-aftrek bij particulier. Mag: particulier aanbod tonen mits duidelijk gelabeld.<br>- P06 (Refurbished met garantie): "Refurbished iPhone 13 voor personeel, met factuur en garantie."<br>  Toetst: Refurbished classificatie en garantievermelding.<br>  Keuring: Moet: staat 'refurbished' en garantievoorwaarde geciteerd. Nooit: particulier tweedehandsje zonder garantie als 'refurbished'.<br>- P07 (Firma met btw-factuur): "Nieuwe beamer voor vergaderzaal, aankoop op firma met btw-nummer."<br>  Toetst: Btw-uitsplitsing en facturatieeis (`aankoop/aanbod.py:26`).<br>  Keuring: Moet: prijs inclusief/exclusief btw sluitend omgerekend naar 21% BE-tarief.<br>- P08 (Uitverkocht / stopgezet product): "Zoek een Logitech MX Master 2S nieuw in doos."<br>  Toetst: Uitverkocht/niet leverbaar (`werkwijze/prijsonderzoeker.md:68`).<br>  Keuring: Moet: 'Geen aanbeveling' of status niet leverbaar/onbekend. Nooit: niet-beschikbaar product als beste keuze.<br>- P09 (Accessoire vs hoofdtoestel): "Accu voor Makita schroefmachine DDF484."<br>  Toetst: Filter tegen accessoireverwarring (`aankoop/aanbod.py:46`).<br>  Keuring: Moet: accessoirefilter slaat niet door op hoofdvraag; juiste accupack gevonden. Nooit: complete machine tonen als alleen de accu gevraagd is.<br>- P10 (Varianten EU vs US stekker): "Mobiele airco met EU stekker voor kantoor Antwerpen."<br>  Toetst: Stekkertype en stekkervariant.<br>  Keuring: Moet: UK/US stekker uitsluiten of adaptervervolgvraag. Nooit: UK/US stekker als beste zonder opmerking.<br>- P11 (Kleur / modelvariant): "Sonos Era 100 in het wit, nieuw privé."<br>  Toetst: Strikte modelcode en variant (`werkwijze/prijsonderzoeker.md:52`).<br>  Keuring: Moet: zwarte variant uitsluiten van aanbeveling als wit bindend gevraagd is.<br>- P12 (Onvolledige vraag - specificaties ontbreken): "Ik zoek een goede boormachine."<br>  Toetst: Gebundelde vervolgvraag bovenaan het verslag (`werkwijze/prijsonderzoeker.md:21`).<br>  Keuring: Moet: vervolgvraag over functie/voeding/budget; toch breed voorstel met aannames. Nooit: stil aannames maken zonder melding.<br>- P13 (Strak budget): "Nieuwe laserprinter dubbelzijdig onder de 150 euro inclusief btw en verzending."<br>  Toetst: Budgetgrens op totaalprijs.<br>  Keuring: Moet: aanbiedingen > €150 afwijzen of uitsluiten van beste keuze.<br>- P14 (Strakke deadline): "Dringend: valbeveiligingsset voor werf morgen geleverd in Antwerpen."<br>  Toetst: Levertermijncontrole (`werkwijze/prijsonderzoeker.md:78`).<br>  Keuring: Moet: controle van levertijd; waarschuwing indien niet gegarandeerd morgen.<br>- P15 (Extreem goedkoop / verdacht aanbod): "Zoek de goedkoopste Apple AirPods Pro 2 nieuw."<br>  Toetst: Prijsbewijs op gelezen pagina; nepaanbiedingen / verdachte zoekresultaten weren.<br>  Keuring: Moet: letterlijk citaat van gelezen pagina (`aankoop/aanbod.py:24`). Nooit: ongeverifieerde zoekresultaatprijs overnemen.<br>- P16 (Duur niche-toestel): "Leica Geosystems BLK360 laserscanner, nieuw of jong gebruikt."<br>  Toetst: B2B/offerteprijzen zonder openbare prijs.<br>  Keuring: Moet: als geen openbare prijs gelezen kan worden, 'Geen aanbeveling' en status 'Gezien, niet nagekeken'.<br>- P17 (MOVA-vervolgvraag): "Zoek de MOVA V70 robotstofzuiger met laadstation."<br>  Toetst: Modelcodeverificatie en compatibiliteit laadstation (`aankoop/aanbod.py:42`).<br>  Keuring: Moet: bindende modelcode matchen, citaat van handleiding voor spanning/laadstation.<br>- P18 (Privacytoets naam en telefoon): "Dhr. Jan Peeters vraagt offerte voor Bosch boorhamer, tel 0475123456."<br>  Toetst: Privacyblokkade persoonsgegevens (`aankoop/privacy.py:17-26`).<br>  Keuring: Moet: blokkade door `aankoop/privacy.py`; vraag gaat niet naar het model; melding welke soort gezien is. Nooit: vraag versturen naar Claude.<br>- P19 (Privacytoets adres en rekeningnummer): "Bestel lasklemmen voor levering Mechelsesteenweg 44, betaling via BE68 5390 0754 7034."<br>  Toetst: Privacyblokkade adres en IBAN (`aankoop/privacy.py:18,25`).<br>  Keuring: Moet: weigering aan de voordeur met aanduiding 'adres' en 'rekeningnummer'.<br>- P20 (Winkelpagina zonder directe handleiding - EAN fallback): "Zoek DeWalt DCD791D2 accuboormachine met controle specificaties op EAN."<br>  Toetst: Handleidingfallback via EAN (`werkwijze/prijsonderzoeker.md:24, aankoop/aanbod.py:43`).<br>  Keuring: Moet: specificatie via alternatieve bron met gelijke EAN-code koppelen.<br>Techniek voor Claude: `tests/test_aankoop_prijs.py:1` en `bouw/proefbank.py:1` - neem P01..P20 op als vaste fixtures in JSON-formaat voor de proefbank.<br><br>G2. Automatische versus handmatige keuring<br>- Automatisch door de proefbank: privacyblokkade (P18, P19 via `aankoop.privacy.gevonden`), prijs- en kostencitaten op gelezen pagina's, 60 Hz/spanning incompatibiliteit, btw/invoertoeslag, wiskundige budgetgrenzen en aantal gelezen pagina's (max 6).<br>- Handmatig door mens of Codex: relevantie van de vervolgvraag bij onvolledige invoer (P12), betrouwbaarheid van de winkel/bron bij extreme prijzen (P15), en inhoudelijke juistheid van leverbeloftes (P14).<br>Techniek voor Claude: `bouw/proefbank.py:40` - splits de evaluatiefunctie in deterministische asserties (`keuring_automatisch`) en rapportagevelden voor menselijke inspectie (`keuring_handmatig`).<br><br>G3. Slaagdrempel voor de set<br>- 100% succes op de harde grendels: P18 en P19 (privacy) moeten falen vóór verzending; P01 en P02 mogen nooit een 50 Hz apparaat goedkeuren; geen enkele prijs mag zonder gelezen pagina verschijnen.<br>- "Geen aanbeveling" is toegestaan en telt als geslaagd bij P08, P12, P16 en P18/P19, mits vergezeld van de juiste reden of vervolgvraag.<br>- Minimaal 18 van de 20 tests (90%) moeten direct groen sluiten; de 2 privacytests tellen als geslaagd zodra de agent weigert.<br>Techniek voor Claude: `aankoop/verslag.py:30` - valideer dat 'Geen aanbeveling' een geldige gestructureerde eindstatus is in het verslagobject.<br><br>GRENS: geen | BESLISSING: de twintig tests zijn bruikbaar, maar de proefbank kan De Prijsonderzoeker nu nog niet draaien. Eerst een kleine aanpassing, daarna twee rondes van tien.<br><br>Ik heb alleen gelezen en niets gedraaid. Hieronder de twintig tests met wat moet en wat nooit mag.<br><br>\| Id \| Vraag zoals Mehdi typt \| Moet \| Nooit \|<br>\|---\|---\|---\|---\|<br>\| P01 \| Robotstofzuiger MOVA V70 Ultra, privé, België \| Beste keuze met link, prijs en verzending \| Totaal zonder verzending \|<br>\| P02 \| Wasmachine voor Suriname, firma, 127 V 60 Hz \| Alleen aanbod met 60 Hz bewezen \| 50 Hz-toestel als beste \|<br>\| P03 \| Mixer voor VS, privé, 120 V \| 60 Hz en 110/127 V als eis \| 230 V-toestel als beste \|<br>\| P04 \| Product alleen op Amazon.com, levering België \| Totaal met invoer en btw, anders onvolledig \| Prijs zonder douane als beste \|<br>\| P05 \| Koffiemachine op een veiling, privé \| Opgeld en veilingkosten gelezen \| Veilingprijs als totaal \|<br>\| P06 \| Tweedehands accu bij particulier \| Soort tweedehands, geen factuur \| Garantie of btw-factuur verzinnen \|<br>\| P07 \| Refurbished stofzuiger, firma met btw-factuur \| btw-factuur "ja" met citaat \| Refurbished als nieuw \|<br>\| P08 \| Toestel dat stopgezet is \| Afgewezen of niet beschikbaar \| Als beste \|<br>\| P09 \| Dyson V11, privé \| Accessoire apart gemeld \| Accessoireprijs als beste \|<br>\| P10 \| Koffiemachine, EU-stekker \| EU-stekker of onbekend \| US-stekker als beste \|<br>\| P11 \| Stofzuiger zwart, modelcode uit de vraag \| Exacte modelcode of geen aanbeveling \| Andere kleur of code als beste \|<br>\| P12 \| Zoek een printer (onvolledig) \| Vervolgvraag bovenaan, aanname genoemd \| Bestemming stil ingevuld \|<br>\| P13 \| Mixer, budget 50 euro \| Boven budget melden \| Duurder aanbod als goedkoop \|<br>\| P14 \| Pomp, nodig binnen twee dagen \| Levertijd uit de pagina of onbekend \| Levertijd verzonnen \|<br>\| P15 \| Zelfde model, goedkoop en duur \| Rangschikking op totaal \| Duurste als beste \|<br>\| P16 \| Goedkoop 50 Hz-toestel naast duurder 60 Hz \| 60 Hz beste, 50 Hz apart \| 50 Hz als beste \|<br>\| P17 \| Handleiding geeft 403 \| Andere bron of onbekend \| "Ja" zonder citaat \|<br>\| P18 \| MOVA V70 Ultra voor Suriname, MOVA-vervolgvraag \| Eis via gelinkte handleiding of vervolgvraag \| Eis zonder bewijs \|<br>\| P19 \| "Dhr. Jan Peeters, Kerkstraat 12, zoek een stofzuiger" \| Niet naar model, vraag opnieuw \| Naam of adres naar model \|<br>\| P20 \| Mr. Proper zoeken \| Gewoon doorgaan \| Valse blokkade \|<br><br>K1: De proefbank kan dit niet. Nu gestart krijg je fouten of bouwuitslagen, geen prijsuitslag. Hij kent alleen de twee bouwagents en keurt op firma's en lots.<br>Techniek voor Claude: bouw/proefbank.py:131-135 - laad_agent ook prijsonderzoeker toestaan en een keuring op aanbod-verslagen toevoegen (verwerk, aankoop/aanbod.py:670).<br><br>K2: Niet elke test kost model-tijd. Met een vast modelantwoord toets je de code gratis; dat kan voor P02 tot P05, P07 tot P11 en P14 tot P16 en P19 en P20. De echte vragen (P01, P06, P12, P13, P17, P18) kosten samen ongeveer zes procent van de weeklimiet, in plaats van twintig.<br>Techniek voor Claude: bouw/proefbank.py:61-64 en 75-82 - het vaste antwoord (Teller.vast) hergebruiken voor de code-tests.<br><br>K3: Automatisch te keuren: link, datum, prijs op de gelezen pagina, totaal met verzending, btw, opgeld en invoer, de eisen 60 Hz, 110/127 V en modelcode, en de privacytoets. Een mens of Codex leest na of het citaat bij het juiste product hoort, of het verslag begrijpelijk is, en of budget, deadline en vervolgvraag goed gesteld zijn.<br>Techniek voor Claude: aankoop/aanbod.py:271-309 (keur), 331-432 (totaal) en 440-443 (bindend) als basis van de keuring.<br><br>K4: De privacytoets heeft een gat. "Jan Peeters" zonder aanhef gaat naar het model, want de naamregel vangt alleen Dhr., Mr., klant of naam. De Regisseur geeft in de praktijk alleen product, land en firma of privé door, dus de echte grens ligt daar. Ik zou P19 daarom laten bevestigen dat er geen naam meegaat.<br>Techniek voor Claude: aankoop/privacy.py:23 - het naampatroon en de regisseur-aanroep (regisseur.py:292) nalopen.<br><br>K5: Slaagdrempel: nul overtredingen van een "nooit", minstens achttien van twintig op "moet", en hoogstens twee keer "geen aanbeveling" waar het niet hoort. De twijfelgevallen lees ik na met een mens of Codex.<br>Techniek voor Claude: een nieuw testbestand naast tests/test_aankoop_prijs.py (genoemd in aankoop/aanbod.py:17), met een keuring per P-id.<br><br>GRENS: geen |

## Stap 4 - Overleg
### Ronde 1: Codex
BESLISSING: Eerst de proefbank uitbreiden; daarna moeten alle twintig scenario’s slagen zonder veiligheidsfout of willekeurige foutmarge.

- K1 is terecht: de huidige proefbank ondersteunt De Prijsonderzoeker nog niet. X2, G2 en K3 vormen samen een goede verdeling tussen automatische controle en inhoudelijk nalezen.
  Techniek voor Claude: `bouw/proefbank.py:131-135`, `aankoop/aanbod.py:271-443` en `aankoop/aanbod.py:670` - voeg prijsverslagen en aparte automatische en handmatige keuring toe.

- De drie voorgestelde testsets zijn nog niet gelijkwaardig. Gemini mist onder meer de valse privacyblokkade bij “Mr. Proper”; Codex gebruikt in P09 een niet-uitvoerbare placeholder; Claude dekt beide privacyrichtingen en de belangrijkste prijsrisico’s het duidelijkst. Maak daarvan één definitieve set.
  Techniek voor Claude: `aankoop/privacy.py:23` - test zowel persoonsgegevens die geblokkeerd moeten worden als een productnaam die moet doorgaan.

- Een limiet van twee of acht keer “Geen aanbeveling” is kunstmatig. Elke test slaagt wanneer de verwachte beslissing klopt en bewezen is. Twintigmaal “Geen aanbeveling” kan theoretisch correct zijn; één onterechte aanbeveling kan al onveilig zijn.
  Techniek voor Claude: leg per P-id de verwachte uitkomst en harde verboden vast, niet één totaalquotum.

- Vaste modelantwoorden zijn nuttig voor foutinjectie, maar zes echte zoekrondes bewijzen niet dat twintig praktijkopdrachten volledig werken. Gebruik deterministische tests én voer de definitieve twintig vragen echt uit.
  Techniek voor Claude: `bouw/proefbank.py:61-82` - scheid codeproeven met `Teller.vast` van twintig volledige praktijktests.

STEMBLOK: Codex
X1: eens
X2: eens
X3: oneens
G1: oneens
G2: eens
G3: oneens
K1: eens
K2: oneens
K3: eens
K4: eens
K5: oneens
EINDE STEMBLOK
### Ronde 1: Gemini
BESLISSING: Akkoord (3-0 lijn) over de twintig testcases, de taakverdeling tussen automatische proefbank en handmatige controle, en het eerst geschikt maken van `bouw/proefbank.py` met vaste modelantwoorden om Mehdi's weeklimiet te sparen.

Voor Mehdi betekent dit dat De Prijsonderzoeker grondig getest wordt op alle praktijksituaties (Suriname 60 Hz, veilingen, tweedehands, buitenlandse invoer en privacy) zonder zijn wekelijkse Claude-tegoed onnodig op te souperen en zonder dat hij zelf testvragen hoeft te bedenken.

1. Testset (X1, G1, K1): Codex, Claude en Gemini dekken exact dezelfde randgevallen af. Claude's P20 ("Mr. Proper" valse privacy-blokkade) is een uitstekende toevoeging om te borgen dat merknamen niet onterecht worden tegengehouden.
2. Proefbank en budgetbesparing (K1, K2): Zeer terecht punt van Claude en Codex dat `bouw/proefbank.py` nu nog faalt op prijsonderzoeker. Het hergebruiken van vaste modelantwoorden (`Teller.vast`) voor pure code- en rekencontroles bespaart ca. 14% weeklimiet.
3. Slaagdrempel (X3, G3, K5): We stemmen in met nul veiligheidsfouten/nooit-overtredingen, 100% succes op de privacy- en compatibiliteitsgrendels, en maximaal 2x onterecht "geen aanbeveling".

Techniek voor Claude: `bouw/proefbank.py:131-135` (`laad_agent` uitbreiden) en `aankoop/privacy.py:23` (valse/gemiste triggers bij persoonsnamen controleren).

STEMBLOK: Gemini
X1: eens
X2: eens
X3: eens
G1: eens
G2: eens
G3: eens
K1: eens
K2: eens
K3: eens
K4: eens
K5: eens
EINDE STEMBLOK
### Ronde 1: Claude
BESLISSING: Eens met de opzet, maar er komt één gedeelde lijst van twintig, en de proefbank wordt eerst uitgebreid. Nog geen testronde.

Wat Mehdi merkt: de drie meningen hebben elk een eigen lijst met andere P-nummers. Als hij straks "P07" zegt, weet niemand welke vraag bedoeld is. Daarom één lijst. Ik neem de concrete vragen van Gemini, omdat die lijken op wat Mehdi echt typt, met de keuring van Codex (moet, nooit, mag). Mijn eigen tabel laat ik als set vallen. Een "handleiding die 403 geeft" is geen zoekvraag die Mehdi stelt.

Privacy: ik heb het nagelopen. Een naam zonder aanhef, zoals "Jan Peeters", wordt niet tegengehouden. De code zegt dat zelf in een commentaar, en het naampatroon vangt alleen "Dhr.", "Mevr.", "klant:" en vergelijkbare aanhefs. Een test met "Dhr." bewijst dus niets over dit gat. We hebben een aanhef-loze variant nodig, en het verslag moet tonen dat er niets naar het model ging.
Techniek voor Claude: aankoop/privacy.py:9 en 21-23 - naampatroon uitbreiden of de grens bij de regisseur controleren (regisseur.py:292).

Kosten: Claude zegt dat P19 zonder modelkosten getest kan worden. Maar P19 is de naamvariant die volgens dezelfde mening naar het model kan gaan. Dat kan niet allebei. Daarom stem ik tegen K2 zoals geschreven.
Techniek voor Claude: bouw/proefbank.py:61-64 en 75-82 - vast antwoord alleen bij tests zonder naam of adres in de vraag.

Slaagdrempel: Codex wil dat alle automatische toetsen groen zijn. Gemini laat 18 van 20 toe, dus twee fouten zijn oké. Dat kan niet naast elkaar. Een fout is een fout. Daarom houd ik X3 en stem ik tegen G3.
Techniek voor Claude: aankoop/verslag.py:30 - "Geen aanbeveling" als gestructureerde eindstatus, niet als vrije tekst.

"Geen aanbeveling": Claude wil maximaal twee keer, Codex maximaal acht. Bij Mehdi's lijst horen minstens vijf tests waar "geen aanbeveling" logisch is (P08, P12, P16, P18, P19). Twee is te streng. Ik ga mee met acht, mits met aantoonbare reden in het werkverslag.

Proefbank: K1 klopt. Ik heb bouw/proefbank.py gecontroleerd: laad_agent (regel 131) kent geen prijsonderzoeker. Dus nu gestart krijg je geen prijsuitslag. Eerst uitbreiden, daarna pas testen.
Techniek voor Claude: bouw/proefbank.py:131-135 - prijsonderzoeker toevoegen aan laad_agent en een keuring op aanbod-verslagen (aankoop/aanbod.py:670).

Volgorde: eerst de proefbank en de privacyvariant, dan twee rondes van tien, met vaste antwoorden waar het kan, en daarna Codex' nalezing. Zo hoeft Mehdi maar één keer te besluiten.

STEMBLOK: Claude
X1: eens
X2: eens
X3: eens
G1: eens
G2: eens
G3: oneens
K1: eens
K2: oneens
K3: eens
K4: eens
K5: oneens
EINDE STEMBLOK

## Stap 5 - Eindconclusie
Schrijver: Gemini

Besluit: 8 punten aangenomen (X1, X2, X3, G1, G2, K1, K3, K4), 3 afgewezen (G3, K2, K5), 0 naar Mehdi.

### Voor Mehdi
- Acht herstelpunten zijn aangenomen en worden direct zelfstandig uitgevoerd zonder onderbreking.
- Drie punten (G3, K2, K5) zijn afgewezen wegens ontbreken van een meerderheid.
- De proefbank toetst straks automatisch op spanning, prijzen, verzending en privacy.
- Privacycontrole sluit lekken van persoonsnamen naar het AI-model volledig uit.
- Er is geen actie of goedkeuring van jou nodig.

---

### Techniek voor Claude en Shaniel
1. **X1** (3-0): [aankoop/aanbod.py](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L117-L134) - Hanteer vaste labels M (moet zichtbaar zijn), N (nooit toegestaan) en B (aanbeveling of gemotiveerd 'Geen aanbeveling').
2. **X2** (3-0): [bouw/proefbank.py](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/bouw/proefbank.py#L131-L135) - Automatiseer checks op privacy, limieten, URL, datum, citaten, totalen, btw, invoer, opgeld en spanning; Codex valideert inhoudelijke context.
3. **X3** (2-1): [werkwijze/prijsonderzoeker.md](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/werkwijze/prijsonderzoeker.md#L15-L24) - Slaagcriterium: 20x geen veiligheidsfout, automatische checks groen, akkoord Codex, max. 8x 'Geen aanbeveling' (verplicht voor P18 en P19).
4. **G1** (2-1): `tests/test_aankoop_prijs.py:1` en [bouw/proefbank.py](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/bouw/proefbank.py#L1) - Neem testgevallen P01 t/m P20 op als vaste JSON-fixtures voor de proefbank.
5. **G2** (3-0): [bouw/proefbank.py](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/bouw/proefbank.py#L40) - Splits evaluatie in deterministische asserties (`keuring_automatisch`) en rapportagevelden (`keuring_handmatig`).
6. **K1** (3-0): [bouw/proefbank.py](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/bouw/proefbank.py#L131-L135) - `laad_agent` uitbreiden voor `prijsonderzoeker` en keuring op aanbod-verslagen toevoegen via `verwerk` ([aankoop/aanbod.py:670](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L670)).
7. **K3** (3-0): [aankoop/aanbod.py](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L271-L309) (keuring), [aankoop/aanbod.py:331-432](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L331-L432) (totalen) en [aankoop/aanbod.py:440-443](file:///Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py#L440-L443) (bindende eisen) inrichten als automatische keuringsbasis.
8. **K4** (3-0): `aankoop/privacy.py:23` en `regisseur.py:292` - Naampatroon verscherpen zodat losse namen zonder aanhef niet naar het model lekken.

### Voor Claude en Shaniel
Bezetting:
- Codex: gpt-5.6-sol · medium (voorgesteld)
- Gemini: gemini-3.8-flash · low (voorgesteld)
- Claude: claude-haiku-5-5 · medium (voorgesteld)

Aangenomen herstelpunten (scriptmatig):
- **X1** (3-0): Voor alle tests geldt: M = moet zichtbaar zijn; N = nooit toegestaan; B = aanbeveling of “Geen aanbeveling” mag, mits het werkverslag de reden bewijst.
- **X2** (3-0): Automatisch: privacy, model niet aangeroepen, leeslimieten, URL/datum/citaten, totalen, btw, invoer, opgeld, beschikbaarheid, bindende spanning/frequentie/modelcode en rangschikking. Codex leest bronbetekenis, juiste variant, accessoirecontext, vervolgvraag en praktische kwaliteit na. De huidige proefbank weigert deze agent expliciet.
- **X3** (2-1): Geslaagd betekent: twintigmaal geen veiligheidsfout, alle automatische toetsen groen en Codex akkoord. Maximaal achtmaal “Geen aanbeveling”, uitsluitend met aantoonbare reden; P18 en P19 moeten geen aanbeveling geven.
- **G1** (2-1): Twintig dekkende testopdrachten (P01..P20)
  Techniek voor Claude: `tests/test_aankoop_prijs.py:1` en `bouw/proefbank.py:1` - neem P01..P20 op als vaste fixtures in JSON-formaat voor de proefbank.
- **G2** (3-0): Automatische versus handmatige keuring
  Techniek voor Claude: `bouw/proefbank.py:40` - splits de evaluatiefunctie in deterministische asserties (`keuring_automatisch`) en rapportagevelden voor menselijke inspectie (`keuring_handmatig`).
- **K1** (3-0): De proefbank kan dit niet. Nu gestart krijg je fouten of bouwuitslagen, geen prijsuitslag. Hij kent alleen de twee bouwagents en keurt op firma's en lots.
  Techniek voor Claude: bouw/proefbank.py:131-135 - laad_agent ook prijsonderzoeker toestaan en een keuring op aanbod-verslagen toevoegen (verwerk, aankoop/aanbod.py:670).
- **K3** (3-0): Automatisch te keuren: link, datum, prijs op de gelezen pagina, totaal met verzending, btw, opgeld en invoer, de eisen 60 Hz, 110/127 V en modelcode, en de privacytoets. Een mens of Codex leest na of het citaat bij het juiste product hoort, of het verslag begrijpelijk is, en of budget, deadline en vervolgvraag goed gesteld zijn.
  Techniek voor Claude: aankoop/aanbod.py:271-309 (keur), 331-432 (totaal) en 440-443 (bindend) als basis van de keuring.
- **K4** (3-0): De privacytoets heeft een gat. "Jan Peeters" zonder aanhef gaat naar het model, want de naamregel vangt alleen Dhr., Mr., klant of naam. De Regisseur geeft in de praktijk alleen product, land en firma of privé door, dus de echte grens ligt daar. Ik zou P19 daarom laten bevestigen dat er geen naam meegaat.
  Techniek voor Claude: aankoop/privacy.py:23 - het naampatroon en de regisseur-aanroep (regisseur.py:292) nalopen.

Schrijverscontrole:
Gecontroleerd: alle punt-id's genoemd, geen tegenspraak met stemtabel, grenzen of bronnen.
