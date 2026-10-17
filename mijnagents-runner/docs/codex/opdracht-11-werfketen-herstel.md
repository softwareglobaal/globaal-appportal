# Opdracht 11: herstel van de werfverslag-keten na het driehoeksoverleg van 17-10-2026

Je werkt in deze worktree (tak `werf-brug`, basis van PR appportal#67) met schrijfrecht. Je wijzigt code, tests en
werkwijze-zaden; je commit niets en je pusht niets. Claude controleert en commit. Lees eerst
`docs/codex/overleg-11-werfketen-2026-10-17.md` (de gezamenlijke eindconclusie, 2-op-3 Codex + Gemini, bevestigd
door Claude) en `docs/codex/stand-11-werfketen-2026-10-17.md` (de live meting). Elke vindplaats daarin is nagelezen.

Regels: niets verzinnen; elke wijziging krijgt een test die het foutgeval dekt (pytest, map `mijnagents-runner/tests/`,
bestaande suites `test_werfverslag_verwerking.py` en `test_werfapp_brug.py` blijven groen; CI
`.github/workflows/werfverslag-grendels.yml`). Geen bestand verwijderen of verplaatsen. Geen netwerk nodig: alles met
stubs zoals de bestaande tests doen. Nederlands in commentaar en meldingen, geen emoji, geen kastlijntjes.
Werk per punt af en noteer onderaan in `docs/codex/codex-11-werfketen-herstel-verslag.md` per punt: bestand:regel,
test, en wat je bewust niet deed. Punten in volgorde van prioriteit; stop niet halverwege een punt.

## Punt 1 (blokkerend): de controleposten bewijzen wat ze beweren (`werfverslag_voorbereider.py`)
- W1 agenda: alleen een H-A-afspraak van de Agendawacht met dossiernummer, `buiten` en een geldig venster (hergebruik
  `bevestigd_fotovenster`, regel ~331); niet "een afspraak op dezelfde dag". Regel E4 (vaste afspraken v1.8, hoofdstuk E):
  foto's met GPS of een opname in het venster winnen van een ontbrekende agenda, maar dan staat W1 op "let_op: bevestigd door
  foto's/opname, niet door de agenda", nooit op "ok".
- W2 wordt **aanwezigheid**: GPS-dagboek van de Locatiewacht (klaarzet soort `locatie`, van `locatie-wacht`) binnen 300 m
  van het bouwplaatsadres in het venster, anders foto's met GPS in het venster (bak `foto` van de iCloud-wacht), anders
  opname met start in het venster. Niets daarvan: "ontbreekt". De projectmap-controle verhuist naar W3 (projectmap +
  bezoekmap).
- Nieuwe post **W12 contract**: via `koppelingen/contracten_mcp.py` (leestool `dossier` op projectnummer) of de werfapp
  (`koppelingen/werfapp.py`, project op nummer): is er een getekend contract (stand getekend) en is werfopvolging
  inbegrepen (`architectuur_scope`, `werfopvolging_keuze`)? Onbereikbaar = "onbekend", nooit "ok".
- W4 foto's: alleen "ok" als er foto's in `<bezoekmap>/fotos/` staan met een `00 fotos.md` waarvan de tijden in het
  venster vallen; losse foto's in de wortel of alleen HEIC = "let_op".
- W6 transcript: alleen "ok" als `transcript.txt` (of `transcript.docx`, `01 transcript.md`) in de bezoekmap staat;
  een transcript dat alleen in de klaarzetbak staat = "ontbreekt" met taak voor de Plaudwacht "plaats het transcript in
  de bezoekmap". De schrijver (`werfverslag_proef.py:424`) leest immers alleen de map.
- W8 verslagnummer: ijk op de werfapp (`werfbezoek_teller` of `/api/v1/projecten/<nr>/bezoeken`); staat er in de werfapp
  een hoger nummer (ArchiSnapper-historiek), dan "let_op: nummer wijkt af van de werfapp" en geen groen.
- W9 verstuurd: alleen "ok" op verzendbewijs uit de werfapp (verslag met verzonden-status); anders "onbekend".
- `stand_van`: "klaar voor verslag" vereist W1 (ok of let_op via E4), W2, W3, W4, W5, W6 en W12 niet "ontbreekt"/"fout".
  Anders "te verzamelen" met de lijst van wat ontbreekt. Voeg de ontbrekende posten als tekst toe in de rij
  (`controles`), zodat de bezoekpagina ze toont.
- Verwijder de dode vaste nood op regel ~736 (die elke ronde herhaald wordt).
Tests: per post het foutgeval (afspraak op dezelfde dag maar ander nummer; foto's in de wortel; transcript alleen in de bak;
geen GPS; werfapp onbereikbaar; nummer hoger in de werfapp; stand mag niet "klaar" zijn zonder W1/W2/W12).

## Punt 2 (blokkerend): de taken aan de bronagents dragen het venster en één eigenaar per stap
- De fototaak voor de iCloud-wacht draagt altijd `start`, `einde` (Belgische tijd), `lat`, `lon` en `straal` uit de
  afspraak; is er geen afspraak, dan het E4-terugvalvenster uit de opname- of fototijd (eerste tot laatste tijdstip plus
  15 minuten voor en 60 na). `mac/icloud_wacht.py` (regel ~398) aanvaardt dat terugvalvenster met reden "E4, geen
  afspraak" in `00 fotos.md`; zonder enig venster blijft hij weigeren. `00 fotos.md` wordt nooit overschreven: bestaat het,
  dan wordt een nieuwe versie met tijdstempel geschreven (regel ~473).
- Taaksluiting: elke taak draagt de bezoeksleutel `<dossier>:<datum>:<bezoekmap>`; de voorbereider vinkt een taak af zodra
  de bron in de map staat, en herhaalt een taak niet (bestaand `uniek`).
Tests: taak zonder afspraak krijgt het E4-venster; iCloud-wacht aanvaardt het; `00 fotos.md` blijft bewaard;
taaksluiting op één bezoeksleutel.

## Punt 3 (blokkerend): de proef en de brug naar de werfapp
- `werfverslag_proef.py` regel ~558: bij een directe "proef" zonder voorafgaande "voorbereid" worden `gegevens` en
  `bijlagen` ook bewaard (`_bewaar`), zodat Herkomst en Bijlagen op de bezoekpagina gevuld zijn.
- `koppelingen/werfapp.py` (PR #67, `_ja` rond regel 146 van de diff): "aanwezig" onbekend of "na te kijken" blijft `None`
  in de payload, nooit `False`; alleen een expliciete ja/nee wordt True/False. Test ernaast aanpassen.
- `mijnagents/templates/werfbezoek.html` regel ~63 en ~139: de tekst zegt nu dat de schrijver de map uitleest terwijl het
  systeem op Mehdi's klik wacht; herstel naar "wacht op jouw klik Voorbereiden / Proef maken" en toon de ontbrekende posten
  uit punt 1.
- CLI-pad `werfverslag_schrijver.py` regel ~104: een commandline-opdracht (`--voorbereid`, `--proef`) start betaalde
  verwerking zonder knop. Vereis een expliciete vlag `--op-vraag-van-mehdi "<reden>"` die in het werkverslag en in de
  opdracht (`bron`) komt; zonder die vlag weigert de runner met een leesbare melding. Het bord (`mijnagents/werfopdrachten.py`)
  aanvaardt `bron: commandline` alleen met die reden.
Tests: directe proef bewaart gegevens; aanwezigheid onbekend blijft None; CLI zonder vlag weigert.

## Punt 4 (belangrijk): één bron van waarheid en de norm
- `werfregistratie.py` regel ~24: koppel elke bordrij aan het werfapp-bezoek-ID vóór de nummering; bestaat het bezoek
  niet in de werfapp, dan registreert de voorbereider het daar (bestaande API uit PR #3) en bewaart hij het ID in de rij
  (`registratie`). Het werfapp-ID is de identiteit; het bord is werkvoorraad. Een verhuisde projectmap mag geen tweede
  werfapp-bezoek opleveren (test).
- Beide runners (`werfverslag_voorbereider.py` ~688, `werfverslag_schrijver.py` ~49) draaien in `with ag.ronde()`
  (`koppelingen/bord.py` ~304), zodat een fout nooit op "actief" blijft hangen en de gelezen werkwijze als kennis gemeld wordt.
- Werkwijze-zaden `werkwijze/werfverslag-voorbereider.md`, `werfverslag-schrijver.md`, `werfverslag-dashboard.md`:
  (a) bron van waarheid per gegeven (bezoek-ID, nummer N, concept, verzending = werfapp; bronnen = bezoekmap; werkvoorraad =
  bord); (b) verwijzing naar vaste afspraken v1.8 in plaats van v1.5, en "het bord en de werfapp winnen bij tegenspraak,
  de skill op de Mac is de handmatige weg"; (c) per koppeling een fiche in vijf delen (taak, waarheid, wie leest, stappen,
  als het misloopt): Agendawacht, Locatiewacht, Plaud-routine + Plaudwacht, iCloud-wacht, Dropbox, contract-dashboard,
  werfapp; (d) de lessentabel aangevuld met de punten van dit overleg (datum 17-10-2026, stap, oorzaak, fix, vindplaats);
  (e) een hoofdstuk "Mandaat" bovenaan elk zaad (één alinea: waarvoor, mag, grenzen) dat `werkwijze_naar_bord.py` ook als
  `mandaat` naar het bord zet (pas dat script aan als het dat nog niet kan).

## Wat je niet doet
Geen push, geen commit, geen verwijdering, geen wijziging in `werfverslag/` (de werfapp-repo), geen echte netwerkoproepen in
tests. Twijfel je over een bedoeling, kies de veiligste lezing (nooit groen zonder bewijs) en noteer de twijfel in het verslag.
