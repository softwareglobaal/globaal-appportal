Akkoord: de echte schrijfproef staat in `claude_abonnement.py:146-163` en blokkeert vóór de vraag op `:284-285`.
De drie gevallen zijn getest in `test_bouw.py:931-938`.
Mislukte opslag na de vraag wordt een limietfout op `claude_abonnement.py:305-306`, getest in `test_bouw.py:847-853`.
De resterende race is aanvaardbaar zodra extra verbruik in het account uitstaat.

AKKOORD