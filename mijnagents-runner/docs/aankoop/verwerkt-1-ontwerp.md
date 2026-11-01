# Verwerking overleg 1 (ontwerp De Prijsonderzoeker), door Claude, 30-10-2026

Gebouwd op tak `aankoopagents`, commit e2bd408. Tests: `tests/test_aankoop_prijs.py` 71 goed, `tests/test_regisseur.py`
53 goed, agentnorm 28 goed, generator 27 goed.

| Punt | Verwerkt | Waar |
| --- | --- | --- |
| X1, G1, K1 | afdeling `aankoop`, De Prijsonderzoeker op verzoek; wacht later apart, inventaris later als register | `docs/aankoop/uitrol.sh`, werkwijze |
| X2 | verplichte vraagvelden in de werkwijze, gebundelde vervolgvraag, beste keuze en reserve, antwoord via De Regisseur, De Bode niet vanzelf (soort `prijsverslag`) | `aankoop/aanbod.py` verwerk, `aankoop/verslag.py`, `prijsonderzoeker.py` SOORT |
| X4, G4 | grenzen in de werkwijze; alleen de productvraag naar de AI | `werkwijze/prijsonderzoeker.md`, `aankoop/privacy.py` |
| X5, G5, K8 | grendels: geen gelezen pagina geen aanbod; niet compatibel nooit aanbevolen; veiling zonder opgeld of kosten nooit totaal; foto alleen als ze op de gelezen pagina staat | `aankoop/onderzoek.py` alleen_gelezen, `aankoop/aanbod.py`, tests |
| X6, G6 | vraaginvoer, zoeken, broncontrole, totaal, rangorde, bordverslag en Regisseur-koppeling gebouwd; eerste bewijs met de vloerwasser voor Suriname na de uitrol | `regisseur.py` RONDE_TOEGELATEN en `--vraag` |
| G2, K2 | velden staat, garantie, verkoper (betrouwbaarheid), foto, btw-factuur | `aankoop/onderzoek.py` VORM, `aankoop/verslag.py` |
| K3 | onbekende veilingkosten tellen als ontbrekend, niet als nul | `aankoop/aanbod.py` totaal |
| K5 | onbekende modelnaam valt een keer terug op het model van De Ontwikkelaar | `aankoop/onderzoek.py` RESERVE_MODEL |
| K7 | bouwprijzen horen niet bij deze agent | werkwijze, "Wat ik weet" |

Grenspunten (Mehdi): X3 en K4 (kosten per vraag) zijn samengevoegd tot een vraag: hoogstens 150.000 tokens,
12 zoekopdrachten, 15 pagina's en 7 minuten per vraag. De 30.000 tokens uit X3 is te laag: een enkele gelezen pagina
kan al 10.000 tokens zijn. K6 is gebouwd in de veilige richting: bij persoonsgegevens gaat er niets weg, en dat
vraagt geen nieuwe toestemming. G3 (afgewezen) is niet uitgevoerd.
