# Verwerking controle 2 van Codex (rapport-3-controle.md), door Claude, 30-10-2026

| Punt | Herstel | Waar |
| --- | --- | --- |
| X1 hoog | de prijs heeft een letterlijk citaat van de eigen aanbodpagina nodig, met het bedrag, en minstens een plek op de pagina zonder kostwoord (verzending, opgeld, kosten) vlak ervoor; de tegenproef 999 product en 499 verzending wordt geweigerd, ook met een citaat van alleen "499,00 euro" | `aankoop/aanbod.py` keur, zonder_kostwoord |
| X2 hoog | "ja" bij een eis telt alleen met een citaat van een gelezen pagina; bij netfrequentie en netspanning moet het citaat die waarde noemen (een citaat met 50 Hz bewijst geen 60 Hz); "nee" wordt altijd geloofd. De toelichting van het model staat niet meer in de aanbeveling, alleen begrensd (160 tekens) bij het aanbod | `aankoop/aanbod.py` compatibel, `aankoop/verslag.py` _kort |
| X3 hoog | het verslag gaat niet meer in het logboek, alleen een regel met de vingerafdruk; het staat in het klaargezette item. Het restrisico van een gewone naam zonder aanspreking leggen we als ja/nee-vraag aan Mehdi voor (zie onder) | `prijsonderzoeker.py` |
| X4 hoog | namen in de werkwijze worden "de opdrachtgever" voor ze naar het model gaan | `aankoop/onderzoek.py` NAMEN |
| X5 middel | de inhoud is leesbaar voor De Regisseur (getest); de route in de chat is het besluit van het overleg (X2). Een klikbare weergave op het bord vraagt een wijziging in de bordapp en een uitrol van de stack: als vervolgpunt genoteerd, niet in deze tak | vervolg |
| X7 middel | is een plafond bereikt (tokens, tijd, zoek- of leesbeurten), dan volgt nog een afrondbeurt met tool_choice none: geen gereedschap meer, het model geeft wat het las | `aankoop/onderzoek.py` |
| X9 middel | btw per kostenpost: verzending_btw_inbegrepen apart (onbekend volgt de prijs); 100 zonder btw plus 10 verzending met btw geeft 131 | `aankoop/aanbod.py` totaal |
| X10 middel | Mr. en Mrs. weg uit de aansprekingen: Mr. Proper gaat door | `aankoop/privacy.py` |
| X11 middel | alle soorten spaties (ook de smalle vaste spatie) worden gelijkgemaakt voor elke vergelijking | `aankoop/aanbod.py` _schoon |

Vraag aan Mehdi (X3, restrisico): een gewone naam zonder aanspreking in een prijsvraag herkent de code niet altijd. De
vraag komt van hem via De Regisseur, die dezelfde tekst al via de Anthropic-API verwerkt. Advies: aanvaarden.

Tests: `test_aankoop_prijs.py` 116 goed, `test_regisseur.py` 54, agentnorm 28, generator 27, geen echte namen 3.
