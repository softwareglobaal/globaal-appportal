# Verwerking controle 6 van Codex (rapport-7-controle.md), door Claude, 30-10-2026

Opgelost volgens Codex: X1. Stopregel (4.7): de filter op "algemene winkelpagina's" via woorden in de link was
tegelijk te lek (X12, /service-kit) en te streng (X16, /bezorging). Ontwerp vereenvoudigd in plaats van verfijnd:

| Punt | Herstel | Waar |
| --- | --- | --- |
| X12, X16 hoog | een verzendkost telt alleen als ze op de aanbodpagina zelf staat; geen raden welke pagina algemeen is. Staat ze er niet, dan blijft het aanbod in de lijst zonder aanbeveling. Opgeld en veilingkosten van een pagina van hetzelfde veilinghuis | `aankoop/aanbod.py` totaal (eigen_tekst), verwerk |
| X2 hoog | een "past" met een woord als accessoire, optioneel, los verkrijgbaar, laadstation, kit of set in de 250 tekens ervoor telt niet; het verslag toont 250 tekens context | `aankoop/aanbod.py` ACCESSOIRE, _accessoire_ervoor |

Tests: `test_aankoop_prijs.py` 143 goed (waaronder de tegenproef van X16: 105 euro wint van 130), `test_regisseur.py` 54.
