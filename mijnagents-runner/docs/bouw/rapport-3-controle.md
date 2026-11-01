Niet klaar. H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; de code waarborgt dat nog niet sluitend.

Voor Claude en Shaniel:

1. **X1 hoog, `bouw/scheiding.py:17`:** De grendel mist bekende adressen en het ondernemingsnummer van de andere firma. Ook `016/79.32.96` en nummers met schuine strepen passeren. `extra_kenmerken` wordt door de runners niet ingevuld.

2. **X2 hoog, `bouw/zoeken.py:156`:** Een gelezen KBO-pagina kan tegelijk doorgaan voor de gelezen firmapagina. Een proef met alleen die pagina kwam onder `goed`.

3. **X3 hoog, `bouw/zoeken.py:176`:** Postcode en gemeente komen ongecontroleerd uit het model. Een firma buiten de straal kan bovenaan komen wanneer het model de gevraagde gemeente invult.

4. **X4 hoog, `bouw/zoeken.py:65`:** Gedeelde lessen en collega-informatie gaan naar het model zonder privacytoets. Een proef met een bouwheernaam en werfadres bleef volledig staan.

5. **X5 hoog, `regisseur.py:576`:** `klaargezet_lees()` kan twintig verslagen van dezelfde agent tegelijk teruggeven en filtert niet op firma, vraag of unieke sleutel. De scheiding berust hier alleen op modelinstructies.

6. **X6 middel, `bouw/offertes.py:132`:** `redigeer()` laat een losse volledige naam op een eigen regel staan. `OFFERTE_NAAR_AI` staat nu veilig uit, maar de redactie is niet klaar om hem aan te zetten.

7. **X7 middel, `bouw/offertes.py:106`:** Bij meerdere eindtotalen wordt altijd het grootste gebruikt. Een bruto totaal vóór verrekening kan daardoor winnen van het echte eindtotaal na korting.

8. **X8 middel, `bouw/eigen.py:29`:** Dropbox-paginering stopt na vijf pagina’s terwijl `has_more` nog waar kan zijn. De JSON-vorm klopt wel met de [officiële Dropbox-specificatie](https://dropbox.github.io/dropbox-sdk-js/global.html).

9. **X9 laag, `bouw/scheiding.py:27`:** Gewone bouwtaal zoals “Onze groep D zorgt voor ventilatie” wordt geblokkeerd.

10. **X10 middel, `docs/bouw/uitrol.sh:11`:** De schone-werkboomcontrole voorkomt geen gelijktijdige wijziging ná de controle; `git checkout --` kan die alsnog overschrijven.

11. **X11 middel, `tests/test_bouw.py:266`:** Regressietests ontbreken voor X1 tot X10, vooral firmagebonden Regisseurlezing, alleen-KBO, modelprivacy, netto eindtotaal en losse namen.

Gedaan: alleen gelezen; niets gewijzigd.  
Nagekeken: `git diff origin/aankoopagents...HEAD`; 123 Bouw-tests groen.  
Open: herstel, regressietests en daarna de live eerste rondes voor N1 tot N14.