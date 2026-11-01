Niet akkoord: API-kosten, SSRF en foutieve firma-keuring zijn nog mogelijk.

Voor Mehdi: de overstap gebruikt normaal het abonnement, maar garandeert nog niet dat er nooit extra kosten ontstaan.

Voor Claude en Shaniel:

1. **Kritiek, kosten:** `HOME` blijft beschikbaar en Claude-instellingen worden niet uitgeschakeld ([claude_abonnement.py:22](mijnagents-runner/koppelingen/claude_abonnement.py:22), [claude_abonnement.py:52](mijnagents-runner/koppelingen/claude_abonnement.py:52)). Een sleutel of provider in `~/.claude/settings.json` kan OAuth overrulen. Ook Usage credits veroorzaken na het abonnementsplafond aparte kosten. Dit bevestigen [Anthropic over verborgen instellingen](https://support.claude.com/en/articles/14128775-claude-code-on-console-to-enterprise-migration) en [Anthropic over Usage credits](https://support.claude.com/en/articles/12429409-manage-usage-credits-for-paid-claude-plans).

2. **Kritiek, SSRF:** DNS wordt gecontroleerd en daarna opnieuw opgelost bij de verbinding ([webpagina.py:24](mijnagents-runner/bouw/webpagina.py:24), [webpagina.py:56](mijnagents-runner/bouw/webpagina.py:56)). DNS-rebinding blijft dus mogelijk, ook na omleiding. Soorten en 2 MB zijn goed begrensd ([webpagina.py:57](mijnagents-runner/bouw/webpagina.py:57)); de timeout is geen totale wandklokgrens.

3. **Hoog, keuring:** pagina’s van verschillende firma’s op hetzelfde gidsdomein worden samengevoegd ([zoeken.py:394](mijnagents-runner/bouw/zoeken.py:394), [zoeken.py:260](mijnagents-runner/bouw/zoeken.py:260)). Zo kunnen naam, werk en nummer uit verschillende pagina’s samen toch groen worden. Een goede firma met een korte homepage wordt juist geweigerd ([zoeken.py:326](mijnagents-runner/bouw/zoeken.py:326)); de eerste dubbelganger verdringt bovendien de betere kandidaat ([zoeken.py:346](mijnagents-runner/bouw/zoeken.py:346)).

4. **Hoog, token:** het aanmeldscript schrijft het token tijdelijk naar een log en toont de programma-uitvoer in Terminal ([abonnement_aanmelden.command:9](mijnagents-runner/mac/abonnement_aanmelden.command:9), [abonnement_aanmelden.command:21](mijnagents-runner/mac/abonnement_aanmelden.command:21)). Op de VM wordt de bestaande bestandsmodus overgenomen, niet verplicht `0600` ([abonnement_aanmelden.command:32](mijnagents-runner/mac/abonnement_aanmelden.command:32)). Tijdens uitvoering staat het token ook in de procesomgeving ([claude_abonnement.py:108](mijnagents-runner/koppelingen/claude_abonnement.py:108)).

5. **Hoog, tijd/plafond:** 5 zoekacties en 12 leesacties zijn alleen prompttekst, geen harde grens ([zoeken.py:102](mijnagents-runner/bouw/zoeken.py:102)). Dropbox-paginering kent geen rondedeadline ([eigen.py:61](mijnagents-runner/bouw/eigen.py:61)). Daardoor kan de 480 seconden worden overschreden en beëindigt De Regisseur het proces pas op 600 seconden ([regisseur.py:551](mijnagents-runner/regisseur.py:551)).

6. **Ontbrekende tests:** instellingen met een API-sleutel, Usage credits, DNS-rebinding, gedeelde domeinen, korte homepages, harde toolgrenzen en trage antwoorden ontbreken ([test_bouw.py:748](mijnagents-runner/tests/test_bouw.py:748)). De test liep hier groen tot tijdelijke bestanden nodig waren; daarna blokkeerde de alleen-lezen omgeving.

Gedaan: commit en uitvoerpaden gecontroleerd, niets gewijzigd.  
Nagekeken: kosten, token, webveiligheid, keuring en tijd.  
Open: bovenstaande blokkades en regressietests.

NIET AKKOORD