# Controle 22: een tokenbestand voor alle agents op het abonnement

Na jouw akkoord in controle 21 kwam #152 op main: De Prijsonderzoeker leest zijn token uit
~/.config/prijsonderzoeker/claude-token (600). Lees de nieuwste commit op tak bouw-abonnement (git show HEAD). Wijzig
niets.

Wat veranderde: claude_abonnement.lees_token leest dat bestand (alleen met rechten 600), niet meer ~/appportal/.env;
controleer_bron weigert ook bij beheerde instellingen van Claude Code op de machine; mac/abonnement_aanmelden.command
schrijft het token naar dat bestand (map 700, bestand 600) via ssh-stdin. Tests: 352 goed.

Gevraagd: klopt dit, blijft alles van controle 17 tot 21 overeind, nieuwe fouten? Met bestand:regel.
Antwoord in het Nederlands, kort. Eindig met precies een regel: AKKOORD of NIET AKKOORD.
Noem in je antwoord nooit de namen van de twee firma's samen en leg geen band tussen hen.
