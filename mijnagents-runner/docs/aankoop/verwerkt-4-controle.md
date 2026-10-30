# Verwerking controle 3 van Codex (rapport-4-controle.md), door Claude, 30-10-2026

Stopregel (werkafspraken 4.7): elke ronde gaf vooruitgang (opgelost na ronde 3: X4, X6, X8, X11), maar de nieuwe
punten zijn randgevallen van hetzelfde ontwerp: code die tekst van het model naleest. Ontwerp herbekeken: de code
blijft de harde regels afdwingen, en het verslag toont voortaan letterlijk de citaten waarop de aanbeveling steunt
(prijs en elke "past"), zodat Mehdi bij het klikken meteen ziet waarop het berust. Kopen beslist altijd Mehdi.

| Punt | Herstel | Waar |
| --- | --- | --- |
| X1 hoog | een bedrag binnen een doorhaling (~~ ~~) of met een teken van een oude prijs vlak ervoor (adviesprijs, van, was, UVP, statt) is nooit de prijs; "gratis verzending" voor de prijs telt niet als kost; alleen de tekst na het laatste scheidingsteken telt mee | `aankoop/aanbod.py` zonder_kostwoord, OUDE_PRIJS, SCHEIDING |
| X2 hoog | netspanning en netfrequentie alleen met een citaat van de eigen aanbodpagina; noemt die pagina ook de andere frequentie (50 tegen 60 Hz) zonder 50/60 Hz, dan is de variant onzeker en blijft het onbekend; het verslag toont het citaat | `aankoop/aanbod.py` _netwaarde_bewezen, `aankoop/verslag.py` _bewijsregel |
| X3 hoog | ja/nee-vraag aan Mehdi (aanvaard door Codex als passend) | werkstand T-0037 |
| X5 middel | uitstel aanvaard door Codex | vervolgpunt |
| X7, X13 | de afrondbeurt hervat de open beurt zonder extra bericht, met tool_choice none; haar blokken blijven bewaard | `aankoop/onderzoek.py` |
| X9 hoog | is de prijs zonder btw, dan erft de verzending dat niet: zonder aparte opgave is het totaal onvolledig | `aankoop/aanbod.py` totaal |
| X10 hoog | Mr. en Mrs. met een naam worden tegengehouden, behalve productnamen (Mr. Proper, Mr. Muscle) | `aankoop/privacy.py` |
| X12 hoog | gratis verzending vraagt een verzendwoord met gratis; "gratis retourneren" bewijst niets | `aankoop/aanbod.py` GRATIS_VERZENDING |

Tests: `test_aankoop_prijs.py` 127 goed, `test_regisseur.py` 54, agentnorm 28, generator 27, geen echte namen 3.
