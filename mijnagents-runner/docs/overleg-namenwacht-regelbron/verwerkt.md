# Verwerking door Claude 1, 29-10-2026

- X1, G2, K2 (aangenomen): `hoofdstukken()` negeert koppen in codeblokken (``` en ~~~, sluitende rand minstens
  even lang) en neemt elke `## `-kop buiten een codeblok als grens. Tests: voorbeeldkop in codeblok, wijzigingslog
  onder B, open codeblok en afwijkende kopvorm pauzeren. De vingerafdruk van v1.10 blijft d956de36...: het sjabloon in
  B staat al in een codeblok.
- G3, K5 (aangenomen): bij een echt gewijzigd hoofdstuk A of B gaat de nood naar `claude-code`, met de gevonden
  versie, de vastgepinde versie en beide vingerafdrukken (12 tekens). Mehdi ziet de status op het dashboard.
- K4 (aangenomen): test dat twee rondes na elkaar dezelfde noodtekst geven, dus geen nieuwe nood per kwartier.
- K3, X3 (aangenomen): test v1.9, v1.10 en v1.2 naast elkaar; v1.10 wordt gelezen.
- X2, X4, K1, G1: geen wijziging nodig, gedekt door bestaande tests.
- X5 (afgewezen 0-3): niet uitgevoerd.
