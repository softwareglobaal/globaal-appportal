Niet akkoord: kosten en harde tijdgrenzen zijn nog niet gegarandeerd.

1. Kosten niet opgelost. De vraag gaat al naar stdin vóór de `init`-controle (`claude_abonnement.py:85-94,165-166`). Overage wordt pas achteraf gemeld en `allowed_warning` wordt zelfs toegelaten (`claude_abonnement.py:89-94`). Extra kosten blijven dus mogelijk.
2. SSRF opgelost: vast goedgekeurd IP, certificaatcontrole en herkeuring van omleidingen (`webpagina.py:45-50,67-78,87-89,119-147`). De totale tijd is niet hard door onbegrenste DNS en minimaal één seconde sockettijd (`webpagina.py:87,91`).
3. Keuring opgelost: pagina’s worden per kandidaat toegewezen en dubbels op bewijs gesorteerd (`zoeken.py:331-360,407-427`).
4. Token opgelost. Tijdelijk bestand, schermwissen, bestandsrechten en overdracht via stdin zijn aanvaardbaar (`abonnement_aanmelden.command:11-42`). De genoemde procesomgeving blijft een aanvaard restrisico.
5. Tijd niet opgelost. Dropbox controleert pas ná het eerste verzoek; elk verzoek kan 60 seconden duren en een tweede zoekwoord start opnieuw (`eigen.py:68-79,91-92`; `bronnen.py:105`). Ook `max(60)` kan de rondedeadline overschrijden (`zoeken.py:454`).
6. Tests onvoldoende. De nep leest eerst de volledige vraag en geeft daarna pas `init`, maar de test noemt dit toch “voor de eerste vraag” (`test_bouw.py:773-775,822-825`). De 331 groene tests bewijzen de kostengrens dus niet.

Nieuwe fout: een afwijkende sleutelbron krijgt geen `limiet`-status, waarna de mislukte vraag toch als opgepakt kan worden gemarkeerd (`claude_abonnement.py:203-204`; `aannemerszoeker.py:236-247`).

NIET AKKOORD