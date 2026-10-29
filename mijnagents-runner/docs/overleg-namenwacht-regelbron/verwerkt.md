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

## Na de Codex-testrondes (29-10-2026)

Ronde 1 tot 4 gaven NIET AKKOORD: telkens verborg een andere kopvorm een nieuwe B-regel buiten de
hoofdstukvingerafdruk ('  ## B.', '####### B.', '## > B.', '## **B**.'). Codex in ronde 4: een deelvingerafdruk op
ruwe Markdown blijft omzeilbaar; pin het hele boek per goedgekeurde versie. Stopregel werkafspraken 4.7 toegepast:
ontwerp herbekeken en het advies gevolgd.

Eindontwerp, de kleinste oplossing van de kernoorzaak:
- de bestaande controle blijft (C2, 17-10): hele boek vastgepind, een nieuwere versie pauzeert;
- de pin gaat van v1.7 (sinds 18-10 in archief/) naar v1.10, met de SHA-256 van het hele bestand;
- de nood bij een nieuwere versie gaat naar claude-code met een opdracht (K5), niet meer naar Mehdi met een vraag.
  Dat was de reden van elf dagen stilstand.
- hoofdstukken() en hoofdstukken_sha256 zijn geschrapt; naamstructuur.py is gelijk aan main.
