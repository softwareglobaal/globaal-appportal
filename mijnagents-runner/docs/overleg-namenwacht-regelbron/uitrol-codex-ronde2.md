**Niet klaar.** De nieuwe controle stopt als Mehdi het bord al vóór de leesstap heeft bewerkt. Bewerkt hij het tussen die leesstap en de POST, dan kan zijn tekst nog als actieve werkwijze worden overschreven. Het geteste scenario C dekt dat tijdvenster niet.

**Voor Claude en Shaniel**

1. **Hoog — [commando.sh:1](commando.sh:1), [app.py:2109](mijnagents/app.py:2109):** de GET en POST staan los; de POST schrijft zonder voorwaarde. Vergelijk en schrijf op de server atomair tegen de verwachte oude tekst.
2. **Laag — [werkwijze_naar_bord.py:50](mijnagents-runner/werkwijze_naar_bord.py:50):** de vergelijking normaliseert witruimte. Punt 3 uit ronde 1 blijft dus een beperking: een bewerking aan afsluitende spaties binnen de tekst kan onopgemerkt verdwijnen.

Commit, pin en logregel worden nu wel getoetst. `bash -n` en de lokale Python-import slagen; `set -e`, `|| rc=$?`, `case`, de lege loguitkomst en de aanhalingstekens werken zoals bedoeld. De POST wijzigt volgens de route alleen de werkwijze, versiegeschiedenis en handeling; het mandaat blijft staan.

Gedaan: alleen gelezen en statisch gecontroleerd.  
Nagekeken: shell, import, bordroute en proefscenario’s.  
Open: bescherming tijdens het tijdvenster tussen GET en POST.

NIET AKKOORD: een bordbewerking tussen lezen en POST kan nog worden overschreven.