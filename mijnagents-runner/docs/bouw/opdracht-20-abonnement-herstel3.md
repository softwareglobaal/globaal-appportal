# Controle 20: herstel na controle 19 (Bouw op het Claude-abonnement)

Lees docs/bouw/rapport-19-abonnement-herstel2.md (jouw vorige oordeel) en de nieuwste commit op tak bouw-abonnement
(git show HEAD). Wijzig niets.

Wat ik per punt deed:
1. Kosten: limiet_reden stopt ook bij een onbekende status (alles behalve "allowed"). Kan de code geen limiet
   onthouden (map niet schrijfbaar), dan start er geen vraag (limiet_schrijfbaar, soort "bron"); mislukt het bewaren
   na een vraag met een limiet, dan is die vraag een limietfout. Extra verbruik uitzetten in het account zeg ik de
   eigenaar als enige volledige garantie.
2. DNS en totale tijd: webpagina.binnen() voert een stap uit in een losse daemon-draad met een harde tijdgrens; de
   DNS-opzoeking en het hele verzoek (verbinden, TLS, versturen, antwoord, lezen) lopen elk binnen de rest van de tijd;
   geen minimum van 0,1 s meer. Een trage draad loopt los verder (elke socket heeft zelf een timeout) en houdt het
   proces niet op.
5. Dropbox: elk verzoek loopt via binnen() met de rest tot de deadline, ook een antwoord dat druppelsgewijs komt.
6. Tests: trage stappen na elkaar (0,4 s elk bij een totaal van 0,6 s), druppelend Dropbox-antwoord, onbekende status,
   niet-schrijfbaar limietbestand. 347 goed. De CI van bouw volgt nu ook claude_abonnement.py en het aanmeldscript.

Gevraagd: is elk punt opgelost, met bestand:regel? Wat blijft over en is dat aanvaardbaar? Nieuwe fouten?
Antwoord in het Nederlands, kort. Eindig met precies een regel: AKKOORD of NIET AKKOORD.
Noem in je antwoord nooit de namen van de twee firma's samen en leg geen band tussen hen.
