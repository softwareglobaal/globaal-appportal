Niet klaar. H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; niets van de ene mag de andere noemen of identificeren.

X1 hoog, `aannemerszoeker.py:56`: bij een onleesbare kern meldt de runner alleen een nood en werkt verder. Adres en ondernemingsnummer kunnen dan ongecontroleerd uitlekken. Hetzelfde geldt in `offertevergelijker.py:55`.

X2 hoog, `bouw/scheiding.py:18`: bekende codes zijn hoofdlettergevoelig. Tegenproef: `Harm BV` wordt niet als de andere firma herkend en kan kandidaat of inschrijver blijven.

X3 hoog, `bouw/zoeken.py:155`: een postcode ergens op de site geldt als vestigingsbewijs. Tegenproef met vestiging in Brugge en werkgebied Leuven kwam in `goed` op 0 km.

X4 hoog, `bouw/vraag.py:80`: `JAN PEETERS` en `GROTE MARKT 12` geven geen privacyfout. Dezelfde gegevens blijven via lessen staan in `bouw/zoeken.py:65` en kunnen naar het model.

X5 hoog, `regisseur.py:1384`: het modelantwoord wordt zonder scheidingsgrendel teruggegeven. De systeemtekst bevat beide firmanamen; alleen een modelinstructie voorkomt vermenging.

X6 middel, `bouw/offertes.py:142`: `redigeer()` laat inline gegevens staan. Tegenproef: “offerte voor Jan Voorbeeld, werf Grote Markt 12” bleef volledig behouden. Momenteel voorkomt `OFFERTE_NAAR_AI=False` verzending.

X7 hoog, `bouw/offertes.py:28`: “Totaal excl. btw na 10% korting 11.000” wordt als kortingsregel overgeslagen; 12.000 werd gekozen. Ook “Prijsindicatie” wordt niet als raming herkend en telt mee als laagste offerte.

X8 laag, `bouw/scheiding.py:34`: gewone bouwtaal blijft geblokkeerd. Tegenproef: “Onze groep warmtepompen wordt vervangen.”

X9 middel, `docs/bouw/uitrol.sh:15`: `git pull origin main` controleert niet dat de VM daadwerkelijk op `main` en exact op `origin/main` staat. Een lokale featuretak kan zo live gaan.

X10 middel, `tests/test_bouw.py:341`: regressietests ontbreken voor bovenstaande tegenproeven; daarom blijven alle bestaande tests groen.

Gedaan: alleen gelezen; niets gewijzigd.  
Nagekeken: volledige diff en 141 Bouw-tests, allemaal groen.  
Open: Regisseurtests niet herhaald omdat die een tijdelijke databank schrijven.