# Verwerking ronde 4: bewaakte borduitrol mijnagents

Door Claude, 16-10-2026. Codex: niet klaar, 0 hoog en 4 middel (BU-19 tot BU-22). BU-14, BU-15 en BU-18 volstaan,
BU-16 en BU-17 deels. Verloop hoog+middel: 8, 4, 4, 4. Twee herstelrondes na elkaar zonder daling: volgens de stopregel
(werkafspraken v1.3, punt 4.7) eerst een ontwerpronde en een keuze van Mehdi, geen derde losse herstelronde.

| Punt | Oordeel | Nameting |
|---|---|---|
| BU-19 middel | gelijk | een uitrol na een mislukt herstel overschrijft `.herstel` (`deploy.sh:375`) en zet `HERSTEL_GESCHREVEN=1` (r. 376); `afbreken` wist ze dan, ook de eerdere herstelopdracht |
| BU-20 middel | gelijk | `LATEST_VOOR` is leeg als `:latest` ontbreekt of niet te inspecteren is (r. 378); een halverwege mislukte wisseltag blijft dan staan en `.herstel` verdwijnt |
| BU-21 middel | gelijk | met dash nagemeten: na een mislukte `&&`-lijst gaat `set -e` door; `schrijf .built && schrijf .built_id` gevolgd door `rm .herstel` (r. 284-285) verliest de markering bij een schrijffout |
| BU-22 middel | gelijk | de nacontrole van het draaiende ID vervalt bij een bestaande `.herstel` (r. 369); hervatten aanvaardt hetzelfde label met een ander ID |

Gemeenschappelijke oorzaak: één overschrijfbare markering met twee rollen (een openstaand herstel uit een vorige ronde
en de lopende wissel van deze ronde), samen met de regel uit ronde 1 dat een nieuwere revisie mag bouwen terwijl een
herstel openstaat. Alle vier punten zitten in die combinatie of in de volgorde van het opruimen.

Niet hersteld in deze ronde; ontwerpronde 5 en de keuze van Mehdi volgen.
