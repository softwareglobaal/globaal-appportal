Niet akkoord: negen oplossingen kloppen, maar totalen, versieherkenning en bordafscherming zijn nog niet veilig.

1. Correct: PDF’s worden één map diep gelezen en archief/documentatie overgeslagen. `bouw/mappen.py:78`
2. Correct: bestanden boven acht krijgen een letter en reden “niet gelezen”. `bouw/offertes.py:419`
3. Correct: de lotkeuze krijgt veilige lotnamen. `offertevergelijker.py:123`
4. Correct voor het gemeten geval: code vooraan en minst diepe map. `bouw/mappen.py:94`
5. Fout: `btw_paar` aanvaardt toevallige verhoudingen. Tegenvoorbeeld: `Totaal 1.000,00 EUR` gevolgd door `Optie 1.210,00 EUR` wordt exclusief 1.000 en inclusief 1.210. Ook `Transport incl. BTW 50,00 EUR` wordt een totaal. `bouw/offertes.py:222`, `bouw/offertes.py:250`
6. Niet volledig: de oorspronkelijke fout is opgelost, maar elk woord van één of twee letters geldt als afkorting. `De vorige som 210,00 EUR is af. Totaal 1.000,00 EUR` plus `Incl. BTW 1.210,00 EUR` verliest het exclusieve totaal. `bouw/offertes.py:193`
7. Correct: `art. 20` heeft woordgrenzen. `bouw/offertes.py:58`
8. Fout: gelijke kernnamen gelden ook over verschillende inschrijversmappen als dezelfde bron. `Dak Een/Offerte 2026001.pdf` en `Dak Twee/Offerte 2026001.pdf` worden nog samengevoegd. `bouw/offertes.py:525`
9. Correct: alleen minstens twee offertes met bevestigd exclusief totaal gaan naar Claude. `bouw/offertes.py:556`
10. Correct: een post kan maar één onderdeel vullen. `bouw/offertes.py:473`
11. Correct voor de gemeten gevallen. `bouw/zoeken.py:346`, `bouw/eigen.py:126`, `bouw/vakwoorden.py:99`, `aannemerszoeker.py:121`
12. Correct: ontbrekende `pypdf` ontsnapt als fout. `bouw/offertes.py:179`

De huidige bordschrijfacties via `bord.call` worden onderschept, maar de afscherming is niet waterdicht. `urllib.request.urlopen(bord.PLATFORM + "/api/klaarzet", data=b"...")` gebruikt een string, passeert de `isinstance(Request)`-controle en bereikt het echte bord. `bouw/proefbank.py:262`

NIET AKKOORD