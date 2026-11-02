# Controle 29: herstel na de proefbank (overleg 28)

Werkmap: repo globaal-appportal, tak bouw-proefbank. Lees `git diff origin/main...HEAD -- mijnagents-runner` en
`docs/bouw/rapport-28-proeven.md`. Wijzig niets. Noem nooit de namen van de twee firma's samen.

De proefbank (`bouw/proefbank.py`) liet beide bouwagents echte vragen afwerken zonder op het bord te schrijven. De
uitkomst, met de hand nagerekend tegen de PDF's en de KBO, gaf deze fouten; elk heeft nu een test in `tests/test_bouw.py`
(385 goed):

1. Offertes in een submap per inschrijver werden niet gelezen (`mappen.offertebestanden`, nu een map diep, zonder
   archief, oude versies en documentatie).
2. Boven acht PDF's viel de rest stil weg (nu een letter en "niet gelezen").
3. De lotkeuzelijst toonde ruwe mapnamen; de grendel weigerde dan het hele verslag (nu `lotnaam`).
4. Projectmap van de tweede firma: de zoekopdracht gaf een fotomap met de projectcode in de naam (nu: naam begint met de code,
   minst diep).
5. Totalen: "Totaal 2.069,35€" zonder label met het inclusief op een latere korte regel, "Totaal zonder B.T.W.",
   "Incl B.T.W.", "Eindbedrag" en een kolom van labels en bedragen onder elkaar werden niet gelezen. Nu telt een kaal
   bedrag alleen als de btw-som (21, 6 of 12 procent) het bewijst (`btw_paar`), of bij 0 procent of verlegd met de vraag
   het na te kijken.
6. "... kosten te betalen. Deze kosten betreffen 50 euro" werd een totaal inclusief btw van 50 euro. Nu telt alleen de
   zin met het totaalwoord, en "totale" is geen totaalwoord.
7. "29 maart 2026" gaf btw verlegd (het patroon art 20 zonder woordgrens).
8. Versies van dezelfde offerte (zelfde offertenummer in de naam) stonden als aparte inschrijvers; nu telt de nieuwste
   (versie volgens de naam, getekend gaat voor, anders de datum in Dropbox).
9. Claude werd gevraagd terwijl geen offerte een totaal exclusief btw had (keur_posten verwerpt dan toch alles).
10. Een post van een inschrijver stond in twee onderdelen van de vergelijking per post en telde twee keer.
11. Zoeker: een ondernemingsnummer stond als telefoonnummer; "hydrofoberen" viel weg en liet "gevelreiniging en" achter;
    een geluidsopname in een offertemap telde als eerdere offerte; "gemeente: Atlantis" heette persoonsgegevens.
12. Ontbrekende pypdf gaf "PDF niet te openen" voor elk bestand; nu een fout.

Vragen:
1. Klopt elke oplossing, en kan een ervan een juist totaal of een juiste offerte nu fout maken (bv. btw_paar dat een
   btw-bedrag en een totaal verwart, versies die twee verschillende inschrijvers samenvoegen, de zinsgrens die een
   echt totaal afknipt)? Geef een concreet tegenvoorbeeld met tekst.
2. Is de proefbank nu afgeschermd: kan een proef op het bord schrijven?

Kort, Nederlands, punten met `bestand:regel`. Eindig met precies een regel: AKKOORD of NIET AKKOORD.
