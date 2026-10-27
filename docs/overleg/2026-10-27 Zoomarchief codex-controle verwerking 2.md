**Voor Mehdi — niet klaar.** Het herstel bewaart een verdwenen voorlopig id en houdt het groene sein uit. Toch kan een al bestaand videobestand uit dezelfde meeting ten onrechte als vervanger tellen. Mijn proef liet zien dat het systeem dan het spoor van de ontbrekende opname wist zonder verliesmelding. `SEIN_AAN = False` voorkomt een wisadvies, maar voorkomt deze gemiste melding niet.

Een teruggekeerd id kan bovendien alsnog als verdwenen worden gemeld. Bij de overgang naar deze versie kunnen ids die al in de live staat staan onterecht 24 uur blijven wachten. Punt 40 kan afzonderlijk op de VM worden gecorrigeerd; deze fouten zitten in de nieuwe code.

**Voor Claude en Shaniel**

41. **Hoog — `zoom_archief.py:634`.** De match vereist geen *nieuw* bestand en kan dezelfde kandidaat voor meerdere voorlopige ids gebruiken. Bewaar welke ids al aanwezig waren en koppel een nieuwe kandidaat aan hoogstens één voorlopig id. Test een al bewezen MP4 naast een verdwijnende MP4 van hetzelfde type en begin.

42. **Middel — `zoom_archief.py:632`.** Komt het oorspronkelijke id terug, dan blijft het wachten; na 24 uur maakt regel 641 er zelfs een verlies van. Hef het wachten op zodra datzelfde id weer in de inventaris staat. Test terugkeer tijdens verwerking én als afgerond bestand.

43. **Middel — `zoom_archief.py:635`.** Bestaande `gezien`-regels uit de vorige versie missen `soort` en `opnametype`. Een verdwenen id kan daardoor zijn echte vervanger niet herkennen. Controleer de live staat vóór uitrol en behandel oude regels expliciet; leg dit vast in een overgangstest.

Gedaan: commit `d9c5e47` alleen lezend gecontroleerd; niets gewijzigd.  
Nagekeken: drie geheugenproeven bevestigen de gevallen; Python-syntaxis en codediff zijn goed. De gemelde volledige testreeksen kon ik in deze alleen-lezen omgeving niet herhalen.  
Open: punten 41–43 herstellen en hertesten; punt 40 afzonderlijk op de VM afhandelen.

BESLISSING: niet klaar