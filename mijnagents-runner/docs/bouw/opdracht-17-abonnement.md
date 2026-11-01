# Controle 17: Bouw op het Claude-abonnement in plaats van de API-sleutel

Lees de commit 24392a0 op tak bouw-abonnement (git show 24392a0) en de bestanden die hij raakt. Wijzig niets.

Opdracht van de eigenaar (01-11-2026): de bouw-agents mogen geen aparte API-kosten maken; ze moeten zijn Claude-account
(abonnement) gebruiken. De andere open punten mocht ik ook oplossen: valse treffers in de eigen mappen, het tokenplafond,
technische fiches die als offerte telden, en offerte-inhoud naar de AI (X5: ja). Of een scan met OCR gelezen mag worden,
beslist hij nog; OCR staat daarom uit (OCR_AAN = False).

Wat er veranderde:
1. koppelingen/claude_abonnement.py start `claude -p` (Claude Code 2.1.286 op de VM) met een setup-token uit
   ~/appportal/.env. Het kindproces krijgt een witte lijst van omgevingsvariabelen plus het token.
2. bouw/zoeken.py: zoek() via dat abonnement met WebSearch en WebFetch. Omdat WebFetch een samenvatting geeft, leest de
   code de pagina's zelf (lees_sites, bouw/webpagina.py) en keur() werkt op wat de code las.
3. bouw/webpagina.py: alleen http(s) naar openbare adressen op poort 80/443, ook na omleiding.
4. bouw/eigen.py: woord_in() en in_offertemap().
5. bouw/offertes.py: fiches, OCR achter een schakelaar, posten via het abonnement.
6. Tests: python3 mijnagents-runner/tests/test_bouw.py (311 goed).

Gevraagd, met bestand:regel bij elk punt:
- Kan er langs welke weg dan ook nog een API-sleutel of API-kosten ontstaan bij deze twee agents?
- Lekt het token ergens (log, foutmelding, proceslijst, bestand)?
- Klopt de veiligheid van webpagina.py (SSRF, omleidingen, grootte, soorten)? Wat blijft over?
- Kan keur() nu een firma bovenaan zetten die niet echt bewezen is, of een goede firma onterecht weren?
- Fouten, randgevallen of tijdsproblemen (ronde van 480 s, De Regisseur wacht 600 s)?
- Ontbreekt een test?

Antwoord in het Nederlands, kort. Eindig met precies een regel: AKKOORD of NIET AKKOORD.
Noem in je antwoord nooit de namen van de twee firma's samen en leg geen band tussen hen.
