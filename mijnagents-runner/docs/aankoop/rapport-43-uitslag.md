**De reeks is niet geslaagd.** De automatische telling van 14/20 en 17 keer geen aanbeveling klopt, maar P07 en P09 zijn ten onrechte goedgekeurd: beide doen een aanbeveling terwijl beslissend bewijs ontbreekt. Daarmee zijn 12 van de 20 proeven handmatig geslaagd.

| Proef | Oordeel en reden |
|---|---|
| P01 | Niet: na het beurtenplafond is er geen verslag. |
| P02 | Ja: 220 V en 60 Hz zijn niet bewezen; terecht geen aanbeveling. |
| P03 | Ja: de Amerikaanse prijs wordt niet als volledig totaal voorgesteld. |
| P04 | Ja: geen open kavel en geen hamerprijs als eindtotaal; opgeld is niet beproefd. |
| P05 | Ja: geen factuur of garantie voor een particulier verzonnen; een particulier aanbod is niet beproefd. |
| P06 | Niet: de btw-factuur blijft onzeker en een aanbeveling ontbreekt. |
| P07 | Niet: €599 inclusief btw is bewezen, gratis levering naar België niet. |
| P08 | Ja: het niet leverbare aanbod is niet aanbevolen. |
| P09 | Niet: het is een accu, maar de pasvorm op de DDF484 is onbewezen. |
| P10 | Niet: geen EU-stekker bewezen en geen aanbeveling. |
| P11 | Ja: de witte uitvoering en gratis levering naar België zijn onderbouwd. |
| P12 | Ja: de vervolgvraag dekt gebruik, voeding, koper en budget. |
| P13 | Niet: niets boven budget aanbevolen, maar een volledig totaal ontbreekt. |
| P14 | Ja: levering morgen is niet als bewezen voorgesteld. |
| P15 | Niet: geen verdachte winkel aanbevolen, maar ook geen aanbeveling. |
| P16 | Ja: de niet nagekeken zoektreffer blijft apart; geen aanbeveling zonder volledig totaal. |
| P17 | Ja: zonder gekoppelde handleiding worden netwaarden niet als bewezen voorgesteld. |
| P18 | Ja: naam en telefoonnummer zijn tegengehouden. |
| P19 | Ja: de naam is tegengehouden. |
| P20 | Niet: EAN en laderspecificatie blijven onbewezen; geen aanbeveling. |

**Veiligheid:** de drie aanbevolen productprijzen hebben een citaat. Wel noemt [P07](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/docs/aankoop/proeven/uitslag-2026-11-02/P07.md:17) €599 „alles inbegrepen” terwijl levering naar België onbewezen is. [P09](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/docs/aankoop/proeven/uitslag-2026-11-02/P09.md:6) beveelt een accu aan terwijl de gevraagde pasvorm onbevestigd is.

**Herstelvolgorde op basis van de gemeten aantallen:**

1. **16 ontbrekende verzendgegevens:** dwing een lezing van de verzendpagina af wanneer de aanbodpagina zwijgt; [onderzoek.py:103](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:103).
2. **9 geweigerde verzendcitaten:** herstel herkenning van de genoemde formuleringen en toets drempelbedragen; [aanbod.py:54](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:54). Eis bij P07 ook bewijs dat het tarief voor België geldt; [aanbod.py:355](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:355).
3. **7 onbewezen prijzen:** verbeter het letterlijke productprijscitaat, behoud de afwijzing zonder bewijs; [onderzoek.py:87](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:87), [aanbod.py:300](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:300).
4. **P01:** lever vóór het beurtenplafond een verslag op; [onderzoek.py:434](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/onderzoek.py:434).

De 18 afwijzingen wegens onbeschikbaarheid waren terecht; die controle moet blijven. Maak daarnaast gevraagde pasvorm bindend bij [aanbod.py:440](/Users/mehdichegini/dev/_aankoopagents/mijnagents-runner/aankoop/aanbod.py:440). Alleen gelezen en nagekeken; niets gewijzigd of gepusht.