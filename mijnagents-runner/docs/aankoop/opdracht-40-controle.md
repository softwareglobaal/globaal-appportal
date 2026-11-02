# Codex-controle 40: proefbank en naam zonder aanhef (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff 948ceb3c..b61898c3` op de tak `aankoop-proefbank`. Achtergrond: `docs/aankoop/rapport-39-testset.md`
(aangenomen X1, X2, X3, G1, G2, K1, K3, K4; K2 afgewezen: alle twintig echt draaien).

- `aankoop/proefbank.py`: draait `prijsonderzoeker.een_vraag` met `ag.log` en `ag.klaarzet` opgevangen (na elke proef
  teruggezet), leest alleen de werkwijze van het bord, proefmap buiten de repo, stopt bij 80 procent weekbenutting.
  Keuring: altijd (aanbeveling is kandidaat met bindende eisen ja, elk aanbod van een gelezen pagina, bron none) plus
  per proef `automatisch`; `handmatig` is voor jou na de rondes.
- `docs/aankoop/proeven/prijsonderzoeker.json`: P01-P20 (vragen van Gemini, keuring M/N/B van Codex, P19 is de naam
  zonder aanhef).
- `aankoop/privacy.py` (K4): voornamenlijst plus hoofdletterwoord, merkenlijst als uitzondering.

Een hoge fout alleen met een concreet scenario: de proefbank schrijft toch op het bord, een naam lekt naar het model,
of een verkeerde keuring laat een onveilige aanbeveling als geslaagd door.

## Vragen

1. Voert de diff de aangenomen punten uit? Per punt ja, of wat ontbreekt met `bestand:regel`.
2. Een fout van ernst hoog?
3. Klaar om live te zetten en de twintig proeven op de VM te draaien: ja of nee.
