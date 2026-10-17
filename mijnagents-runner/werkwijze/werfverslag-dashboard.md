# Werkwijze van Werfverslag dashboard (H-Architects)

## Mandaat

Ik toon Mehdi per werfbezoek de bewezen stand, ontbrekende bronnen en het gekoppelde concept, zodat hij zelf kan kiezen en nakijken. Ik mag gegevens uit bord en werfapp lezen en een bronfout melden, maar geen betaalde proef, verzending, handtekening of verwijdering starten.

Versie 1 (17-10-2026). `H-A vaste afspraken v1.9`, hoofdstuk E, geldt. Bij tegenspraak winnen bord en werfapp; de skill `werfverslag` op de Mac is de handmatige weg.

## Bron van waarheid

De werfapp bewaart bezoek-ID, verslagnummer N, concept en verzendbewijs. De bezoekmap bewaart foto's, opname, transcript en notities. Het bord bewaart werkvoorraad, controles, bronopdrachten, voorbereiding en keuzes. De bezoekpagina toont W1-W12 en de tekst `Nog te verzamelen`; zij noemt een bezoek pas klaar wanneer de vereiste posten dat toelaten. Een klik Voorbereiden of Proef maken is de betaalde start.

## Koppelfiches

| Koppeling | Taak | Waarheid | Wie leest | Stappen | Als het misloopt |
|---|---|---|---|---|---|
| Agendawacht | H-A-buitenafspraak en venster | agenda-item met dossier en bezoeksleutel | voorbereider, dashboard | toon W1 na koppeling | E4-foto/opname geeft let_op, geen agenda-groen |
| Locatiewacht | GPS-bewijs van aanwezigheid | dagboek met gedragen tracker op maximaal 300 m | voorbereider, dashboard | vergelijk tijd, adres en tracker | geen match: W2 ontbreekt |
| Plaud-routine en Plaudwacht | transcript ophalen en plaatsen | opname-start en transcript in bezoekmap | voorbereider, schrijver | routine zoekt; wacht plaatst; voorbereider controleert | alleen klaarzetbak: W6 ontbreekt |
| iCloud-wacht | foto's leveren | `fotos/` en `00 fotos.md` met tijden | voorbereider, schrijver | venster en coördinaten ontvangen; export binnen 300 m | geen venster: weigeren; oude manifestversie blijft |
| Dropbox | oorspronkelijke bronnen bewaren | bezoekmap en bestanden | voorbereider, schrijver | bronpad tonen en inhoud lezen | online-only nul bytes is geen bewijs dat het bestand leeg is |
| Contract-dashboard | contract en werfopvolging toetsen | getekend dossier via MCP `dossier` | voorbereider, dashboard | stand, scope en werfopvolging controleren | onbereikbaar: W12 onbekend |
| Werfapp | ID, nummer N, concept, verzendbewijs | gekoppeld bezoek en verslag | voorbereider, schrijver, dashboard, Mehdi | bestaand ID koppelen; zo nodig registreren; proef plaatsen; Mehdi verstuurt | hoger nummer: W8 let_op; geen verzendbewijs: W9 onbekend |

## Lessen

| Datum | Stap | Oorzaak | Fix | Vindplaats |
|---|---|---|---|---|
| 17-10-2026 | Bezoekstatus | W1-W6 telden te zwak; W12 ontbrak | Toon ontbrekende posten en bewijs per bron | `werfverslag_voorbereider.py:634`, `mijnagents/app.py:2143` |
| 17-10-2026 | Proef | Een directe proef bewaarde Herkomst en Bijlagen niet | Bewaar beide ook bij directe proef | `werfverslag_proef.py:690` |
| 17-10-2026 | Werfapp | Bordnummer en apphistorie konden uiteenlopen | App-ID en N gaan voor; bord is werkvoorraad | `werfregistratie.py:18`, `koppelingen/werfregister.py:106` |
| 17-10-2026 | Toestemming | CLI kon tokens starten zonder vastgelegde reden | Commandline vraagt expliciet Mehdi's reden | `werfverslag_schrijver.py:122`, `mijnagents/werfopdrachten.py:137` |
