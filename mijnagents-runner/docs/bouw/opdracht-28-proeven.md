# Overleg 28: zijn deze 20 proeven genoeg om te bewijzen dat de twee bouwagents goed werken?

Werkmap: de repo globaal-appportal, tak bouw-proefbank. Wijzig niets. Noem nooit de namen van de twee firma's samen.

## Wat er is

Twee agents van de afdeling Bouw, elk voor precies een van twee firma's (HA of HB), die elkaar nooit noemen:

- De Aannemerszoeker (`mijnagents-runner/aannemerszoeker.py`, `bouw/zoeken.py`, `bouw/eigen.py`, `bouw/mail.py`,
  `bouw/scheiding.py`): zoekt firma's voor een werk in een gemeente, de code keurt elke kandidaat (KBO actief, eigen site
  met ondernemingsnummer en naam, afstand vanaf de KBO-zetel), en zet per kandidaat een prijsaanvraag als tekst klaar.
  Claude draait op het abonnement (`koppelingen/claude_abonnement.py`), nooit op een API-sleutel.
- De Offertevergelijker (`offertevergelijker.py`, `bouw/mappen.py`, `bouw/offertes.py`, `bouw/verslag.py`): zoekt de lotmap
  van een project, leest de PDF's, laat fiches weg, vergelijkt totalen en vraagt Claude per post pas bij twee echte offertes.

Tot nu toe getest: 359 eenheidstests (`tests/test_bouw.py`), Codex-controles 1 tot 27, en drie echte rondes.

## Nieuw: de proefbank

`mijnagents-runner/bouw/proefbank.py` laat een agent echte vragen afwerken met dezelfde code, bronnen en abonnement als op
de server, maar elke schrijfopdracht naar het bord (hartslag, klaarzet, logboek, nood, kennis, opgepakt) wordt opgevangen
in een proefmap buiten de repo. Alleen lezen gaat naar het bord. Een teller telt de vragen aan Claude. Per proef algemene
toetsen (geen fout, precies een verslag voor Mehdi, geen kenmerk van de andere firma via de grendel en via een tweede,
eenvoudige woordtoets) plus de verwachtingen uit de proef.

De proeven: `docs/bouw/proeven/aannemerszoeker.json` (A1 tot A10) en `docs/bouw/proeven/offertevergelijker.json` (V1 tot
V10). Lees ze.

## Wat ik vooraf al zag (toets dit, neem het niet over)

- F1: bij een H-A-project staan de offertes van een lot in een submap per inschrijver (lot/inschrijver/offerte.pdf).
  `mappen.offertebestanden` leest alleen PDF's direct in de lotmap, dus de vergelijker ziet 0 offertes waar er 3 of 4 zijn.
  Proef V2.
- F2: een post met 9 PDF's: `offertevergelijker.py:129` neemt er 8 en het verslag zegt niets over de negende. Proef V4.
- F3: `verslag.lotkeuze` toont de lotnamen letterlijk. Draagt een lotnaam de naam van de andere firma, dan weigert de grendel
  in `zet_klaar` het verslag met een uitzondering buiten een try, en Mehdi krijgt geen verslag maar een nood. Proef V5.

## Vragen

1. Zijn deze 20 proeven samen genoeg om te zeggen dat beide agents goed werken? Welke proef is zwak, overbodig of mist?
   Geef per agent hoogstens drie vervangingen of aanvullingen, elk met vraagtekst en verwachting.
2. Klopt elke verwachting? Noem een verwachting die fout of te los is.
3. Is de proefbank waterdicht: kan een proef toch op het bord schrijven, of iets anders dan lezen doen?
4. Wat moet ik na het draaien zelf nog met de hand narekenen (bijvoorbeeld KBO, afstand, mailadres, totalen), omdat de
   automatische keuring het niet kan zien?
5. Kloppen F1, F2 en F3, en wat is per fout de kleinste juiste oplossing?

Kort, Nederlands, punten met bewijs (`bestand:regel`).
