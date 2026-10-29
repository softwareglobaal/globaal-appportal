**Niet akkoord met live zetten.** Een oude lijst met een UTF-8 BOM vóór de titel en geldige nieuwe tijdregels krijgt ten onrechte `ok`, zelfs wanneer de oude tabel werf 9999 en afstanden van 450 m vermeldt.

Voor Claude en Shaniel: **hoog**. De controle op de oude titel in [werfverslag_voorbereider.py](/Users/user2025/dev/_wt-w4/mijnagents-runner/werfverslag_voorbereider.py:675) mist die BOM. Daardoor tellen de nieuwe regels alsnog mee. Wijs gemengde lijsten ook bij een afwijkend opgemaakte oude titel af en voeg deze leesproef toe.

De eerdere fout met een losse afwijkende regel is bij de exacte oude titel verholpen. Ik heb niets gewijzigd of gepusht. Van de gevraagde tests slaagden er 98 en 14 subtests; twee integratietests konden in deze leesomgeving geen tijdelijke map maken. De VM-ronde heb ik niet zelf herhaald.

NIET AKKOORD: een gemengde fotolijst kan W4 nog ten onrechte goedkeuren.