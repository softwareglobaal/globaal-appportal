Niet akkoord: de normale uitvoerroute is goed afgeschermd (`claude_abonnement.py:65-76,205-216,308-333`).

Hoog: het aanmeldscript start zelf `claude -p` zonder controle op beheerde instellingen (`mac/abonnement_aanmelden.command:37-40`). Daardoor kan die proef alsnog een andere betaalbron gebruiken. Voeg vóór de proef dezelfde broncontrole toe.

De limiet-, tijd- en opslaggrendels uit controles 18 tot 21 blijven overeind. Geen andere nieuwe fout gevonden; de volledige 352 tests waren hier door de alleen-lezen tijdelijke map niet herhaalbaar.

NIET AKKOORD