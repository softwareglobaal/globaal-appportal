**Niet klaar.** In de door Claude geteste toestand zet het commando beide werkwijzen op 1.2. De route laat het mandaat ongemoeid en wijzigt geen cron of index. Het commando controleert echter niet opnieuw of de bordtekst sinds die proef is veranderd. Een latere bewerking wordt dan als actieve werkwijze overschreven; de vorige tekst blijft wel in de versiegeschiedenis.

**Voor Claude en Shaniel**

1. **Hoog — `commando.sh:1`, `app.py:2109-2116`:** controleer vóór de POST of beide bordteksten nog de verwachte 1.1 zijn; stop bij verschil.
2. **Middel — `commando.sh:1`:** `curl -f` stopt bij 403 en de leescontrole stopt bij verschil (exit 1). Maar `grep … | tail` kan zonder logregels toch slagen; commit en pin worden getoond, niet getoetst. Maak die controles expliciet.
3. **Laag — `app.py:2105`, `werkwijze_naar_bord.py:50-51`:** `strip()` verwijdert het slotregeleinde van beide zaden. De bevestiging bewijst genormaliseerde gelijkheid, geen exacte bytegelijkheid.

De workflow bewaart de ene invoerregel met aanhalingstekens, `$` en `%{http_code}` intact (`vm-workflow.yml:39-48`). Hij schrijft het volledige commando in het private Actions-log: dus wel namen en relatieve paden, geen sleutel uit deze opdracht. Bij verschil kan de controle ook bordtekst in dat log tonen.

Gedaan: alleen gelezen; niets uitgevoerd op de VM.  
Nagekeken: shellsyntaxis, route, vergelijking en workflow.  
Open: controle van de bestaande bordtekst vóór uitvoering.

NIET AKKOORD: het commando kan een tussentijdse bordbewerking ongezien overschrijven.