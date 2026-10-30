# Verwerking controle 1 van Codex (rapport-2-controle.md), door Claude, 30-10-2026

| Punt | Herstel | Waar |
| --- | --- | --- |
| X1 hoog | een pagina zonder leesbare tekst (minder dan 200 tekens) telt niet als gelezen; de prijs moet letterlijk op de gelezen pagina van het aanbod staan; opgeld, verzending en veilingkosten boven nul moeten op een gelezen pagina staan, anders is het totaal onvolledig | `aankoop/aanbod.py` keur, bedrag_op_pagina, procent_op_pagina, totaal |
| X2 hoog | de eisen over netspanning en netfrequentie haalt de code uit de vraag (Suriname wordt 60 Hz) en geeft ze het model als vaste eisen; een eis zonder oordeel is onbekend en nooit de beste; geen vrije adviestekst meer, alleen een uitleg per aanbod dat de controle doorstond | `aankoop/aanbod.py` eisen_uit_vraag, `aankoop/verslag.py` |
| X3 hoog | aansprekingen en "klant Voornaam Achternaam" houden de vraag tegen; de vraag komt nooit in het logboek (alleen een vingerafdruk), ook niet bij een fout. Een gewone naam zonder aanspreking blijft een restrisico: De Regisseur geeft alleen product, land en firma of privé door | `aankoop/privacy.py`, `prijsonderzoeker.py` |
| X4 hoog | naar het model gaan alleen de werkwijze en de productvraag; geen naam van Mehdi, geen collega's, geen lessen (die leest de ronde wel als bron voor N13 en N14) | `aankoop/onderzoek.py` opdracht |
| X5 hoog | `prijsverslag` staat bij de soorten waarvan De Regisseur de inhoud leest; test volgt het verslag tot in zijn leesweg | `regisseur.py` INHOUD_SOORTEN, `tests/test_regisseur.py` |
| X6 hoog | een deadline voor de hele ronde (480 s); een vraag begint alleen met minstens 150 s over, anders blijft ze klaarstaan; elke API-beurt krijgt de resterende tijd als timeout | `prijsonderzoeker.py`, `aankoop/onderzoek.py` |
| X7 middel | zoek- en leeslimieten tellen over alle beurten; geen nieuwe beurt boven het tokenplafond | `aankoop/onderzoek.py` |
| X8 middel | een gepauzeerde beurt gaat verder met de hele beurt tot nu toe; test met twee pauzes | `aankoop/onderzoek.py` |
| X9 middel | btw_inbegrepen per aanbod: onbekend is onvolledig, zonder btw wordt 21 procent bijgeteld; buiten de EU schat het model de douane en rekent de code de btw | `aankoop/aanbod.py` totaal |

Tests: `test_aankoop_prijs.py` 100 goed, `test_regisseur.py` 54 goed, agentnorm 28, generator 27, geen echte namen 3.
