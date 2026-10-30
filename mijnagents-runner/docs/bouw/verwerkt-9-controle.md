# Verwerking controle 9 (Codex, 8 punten: 1 hoog, 5 middel, 2 laag), 30-10-2026, Claude 1

- X1 hoog, niet gewijzigd, naar Mehdi: de vaste systeemtekst en het gereedschap van De Regisseur noemen H-Architects
  (bestaande tekst, ook de Pipedrive-tool). Bij een vraag over Harmonie Bouw ziet het taalmodel achter De Regisseur dus
  beide namen. Dat is de verwerkingslaag zelf (dezelfde API als elke agent), geen stuk naar klanten, aannemers of
  derden; het antwoord gaat door de scheiding van de firma van de vraag. De systeemtekst van De Regisseur aanpassen
  raakt al zijn gesprekken; dat beslist Mehdi. Advies: zo laten.
- X2: "h.a. bv" en varianten worden herkend; regressietest erbij.
- X3: een verlopen offerte doet niet mee aan laagste en hoogste, net als een raming.
- X4: niet gewijzigd, met reden: een "indicatieve offerte" is niet bindend en hoort dus niet tussen de bindende
  offertes in de rangschikking; ze staat erbij met de reden.
- X5: een mailadres of telefoonnummer blijft alleen staan als het op een gelezen pagina van de eigen site staat.
- X6: een huisnummer voor de straat wordt weggehaald; "Levering 3" is geen adres meer. OFFERTE_NAAR_AI blijft uit.
- X7: pypdf staat op de VM (6.18.0 in ~/agents/.venv); de uitrol stopt nu als het ontbreekt.
- X8: regressietests: 222 bouwtests, 55 regisseurtests.

Stopregel: na negen controles staat er een punt van ernst hoog open, en dat is een keuze voor Mehdi (zie X1).
