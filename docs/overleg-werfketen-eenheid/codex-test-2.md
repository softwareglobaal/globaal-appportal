NIET AKKOORD

**Voor Mehdi:** Vier van de vijf eerdere punten zijn verwerkt. Bij een tijdelijke HTTP-fout van het werfdashboard krijgt de runner nog geen herkansing en verschijnt alsnog een traceback.

**Voor Claude en Shaniel:**

4. **Middel — [werfverslag_dashboard.py:78](/Users/user2025/dev/globaal-werfverslag/runner/werfverslag_dashboard.py:78):** `HTTPError` is ook een `URLError`, maar wordt hier direct hergooid. Een HTTP 503 omzeilt daardoor de herkansing en de afhandeling in `__main__`. **Kleinste fix:** laat HTTP 5xx door de herkansing lopen en geef na de tweede fout één regel met de werkelijke reden; voeg een test voor twee mislukte pogingen toe.

Gedaan: beide commits en de aanroepketen alleen lezend gecontroleerd.  
Nagekeken: 11 voorbereider-tests opnieuw geslaagd; de overige gemelde tests niet opnieuw gedraaid.  
Openstaand: runner-foutafhandeling hierboven.