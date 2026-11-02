# Overleg 34: eindtoets, zijn de twee bouwagents klaar voor Mehdi's echte proef?

Werkmap: repo globaal-appportal, main f186401 (PR #164). Wijzig niets. Noem nooit de namen van de twee firma's samen;
gebruik HA en HB.

## De vraag van Mehdi

"Als het werkt, is het goed en stoppen we tot ik het morgen echt test." Morgen stelt Mehdi zelf een vraag aan De
Aannemerszoeker (firma's zoeken voor een werk in een gemeente, voor HA of HB) en aan De Offertevergelijker (de offertes van
een lot naast elkaar), en leest het verslag op het bord mijnagents.globaal.be. Hij verstuurt zelf; de agents versturen niets.

Beslis per agent: KLAAR voor die proef, of NIET KLAAR. Noem alleen punten die de proef van morgen doen mislukken of Mehdi
een fout cijfer, een fout bedrijf of een naam van de andere firma tonen. Wensen voor later horen hier niet.

## Het bewijs (gemeten 01 en 02-11-2026)

- Code: `mijnagents-runner/aannemerszoeker.py`, `offertevergelijker.py`, `bouw/*.py`, `koppelingen/claude_abonnement.py`.
  Claude draait op het abonnement (`claude -p` met een setup-token, nooit een API-sleutel; stopt voor extra verbruik).
- Tests: `tests/test_bouw.py` 398 goed, lokaal en op de server na de uitrol.
- Proefbank (`bouw/proefbank.py`): de agents werken echte vragen af met dezelfde code, bronnen en het abonnement, maar
  schrijven niets op het bord. Proeven in `docs/bouw/proeven/aannemerszoeker.json` en `offertevergelijker.json` (v0.2,
  na overleg 28).
  - Ronde 1 en 2 vonden 13 fouten (submappen per inschrijver niet gelezen, stil weglaten boven acht PDF's, lotkeuzelijst
    met de naam van de andere firma, verkeerde projectmap bij HB, totalen zonder label, "50 euro te betalen" als totaal,
    "maart 2026" als btw verlegd, versies als aparte inschrijvers, Claude zonder totalen, een post in twee rijen,
    ondernemingsnummer als telefoon, een los "en" na een weggevallen woord, de zinsgrens na "excl.").
  - Na herstel: zoeker 10 van 10 geslaagd (A1, A2, A8, A9 met echt Claude; A7 en A10 met een vast modelantwoord: de
    andere firma, een gestopte firma en een site zonder het opgegeven nummer komen nooit onder "klaar"); vergelijker 10
    van 10. Op de live code na de uitrol: 16 van 16 opnieuw geslaagd.
- Hercontrole met de hand: alle 20 firma's die onder "klaar" stonden zelf opgezocht in de KBO (allemaal actief, zetel
  klopt met het verslag); bij drie het mailadres en het nummer op de eigen site gevonden. Bij vier loten de totalen van het
  verslag vergeleken met de tekst van de PDF: gelijk. In geen enkel verslag een naam of kenmerk van de andere firma.
- De weg via De Regisseur (`regisseur.py:97-150`: agent_ronde met de vraag als velden, het verslag op sleutel gelezen) is
  op 01-11-2026 live gebruikt; de proefbank toetste dezelfde agentcode met een vraag met de hand.
- Codex: controle 29 en 30 niet akkoord (vier punten, hersteld en getest), 31 akkoord, 32 niet akkoord op een nieuwe
  regel (die is teruggedraaid: een offerte wordt nooit weggezet omdat er geen decimalen staan), 33 akkoord voor live.

## Bekend en bewust zo

- OCR staat uit tot Mehdi ja zegt: een gescande offerte staat erbij als "OCR nodig", zonder bedrag.
- Een offerte met 0 procent btw en een ongewone opmaak kan "onbekend" tonen in plaats van een totaal.
- Een document zonder totaal (een aanvraag, een wensenlijst) staat erbij als inschrijver met "onbekend", nooit weggezet.
- Afstand wordt gerekend vanaf het midden van de gemeente van de KBO-zetel (in Hasselt dus 0,0 km voor elke deelgemeente).
- Een rode CI-test van een andere agent (Filewacht, tijdsafhankelijk) was al rood op main voor deze uitrol.

## Vragen

1. Per agent: KLAAR of NIET KLAAR voor Mehdi's proef van morgen, met de reden.
2. Is er iets in "Bekend en bewust zo" dat morgen een fout beeld geeft en dus toch eerst moet?
3. Wat moet Mehdi morgen klik voor klik doen om beide te proberen, in hoogstens vijf korte stappen?

Kort, Nederlands, punten met `bestand:regel` als het om code gaat.
