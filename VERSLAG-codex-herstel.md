# Herstel werfverslagketen, 21-10-2026

Beslissing: klaar als lokale codewijziging, met twee controlepunten vóór productie: de PDF-testomgeving en een echte bezoekproef. Er is niets geüpload, verstuurd of uitgerold.

| Aangenomen punt | Gedaan, met vindplaats | Aanname | Open |
|---|---|---|---|
| X1 | W4-W6 en W12 zijn alleen bij `ok` klaar; onbekende werfstart verschijnt op de rij en blokkeert klaar. `mijnagents-runner/werfverslag_voorbereider.py:900`, `:1046`. | W1 mag volgens E4 `let_op` blijven. | Live bezoekrij nakijken. |
| K1 | HEIC met jpg-kopie wordt ook in Mehdi's andere fotomappen overgeslagen. Download- en Word-plaatsingsfouten krijgen naam en reden. `mijnagents-runner/werfverslag_proef.py:139`, `:666`; `mijnagents-runner/sjabloon_werfverslag.py:557`. | Jpg/jpegs met dezelfde basisnaam zijn dezelfde opname. | Echte iCloud-map toetsen. |
| X2 | Elk niet-vast punt krijgt een toetsbare bestandsnaam; zonder bron staat de waarschuwing in het verslag. Kantoorpunten dragen expliciet hun herkomst. `mijnagents-runner/werfverslag_proef.py:575`; `mijnagents-runner/sjabloon_werfverslag.py:224`. | Een tijdstip bij `transcript.txt` duidt de passage aan. | Inhoudelijke controle blijft bij Mehdi. |
| K2 | Klantvelden verdwijnen in eigen-modus; een los `transcript.txt` zonder Plaud-id of skill-kop krijgt `herkomst onbekend`. `mijnagents-runner/werfverslag_proef.py:291`, `:408`, `:223`; `mijnagents-runner/koppelingen/werfnamen.py:32`. | De skill-kop bevat dossier plus bezoekmap of noemt de skill expliciet. | Oude transcripten zonder kop vragen herstel. |
| X3 | Naslag gaat afzonderlijk naar het model en alleen vanuit een vaststelling met bron. Gekopieerde zinnen verdwijnen. `mijnagents-runner/werfverslag_proef.py:562`, `:600`, `:819`. | Meer dan twaalf gelijke opeenvolgende woorden is een letterlijke overname. | Echte Buildwise-fragmenten testen. |
| K3 | Registersleutel, 240 tekens, licentieregel, PDF-naam en verouderde bron worden achteraf gecontroleerd. `mijnagents-runner/naslag/naslag.py:152`; `mijnagents-runner/werfverslag_proef.py:600`. | Registerstatus is leidend voor opvolgerwaarschuwing. | PDF-test geblokkeerd door ontbrekend `pypdf` in beschikbare testomgevingen. |
| X5 | Modelinvoer bevat alleen verslagfeiten en één fotolijst. Afgekapt antwoord krijgt één geregistreerde, kleinere herhaling; tokens per fase staan in `proef_info`. `mijnagents-runner/werfverslag_proef.py:779`, `:806`, `:842`. | De tweede poging mag minder onderdelen bevatten en is dus zichtbaar als concept om na te kijken. | Kosten met live gebruik meten. |
| K5 | De bezoekpagina toont fotofouten, punten zonder bron en naslagmeldingen. `mijnagents/templates/werfbezoek.html:207`. | Lijsten in `proef_info` leveren zowel redenen als aantallen. | Visueel controleren na uitrol. |

Het harde bezoekbudget uit X4 staat standaard uit. `WERF_TOKENBUDGET=ja` activeert de voorcontrole op 25.000 invoer- en 8.000 uitvoertokens, drie naslagbronnen en 3.000 naslagtekens; zie `mijnagents-runner/werfverslag_proef.py:435`, `:562`, `:779` en `mijnagents-runner/werkwijze/werfverslag-schrijver.md:97`. De werkwijzen zijn versie 10 en 5; W11 en W12 staan samen in `mijnagents-runner/werkwijze/werfverslag-voorbereider.md:55`.

Getest: 115 werfketentests geslaagd, 1 bestaande skip; 17 nummeringcontroles geslaagd; 3 naslagtests geslaagd. Twee bestaande naslagtests met echte PDF-fragmenten konden niet draaien omdat geen beschikbare testomgeving `pypdf` bevat. De nieuwe naslagprompttest is wel groen. `git diff --check` is schoon.
