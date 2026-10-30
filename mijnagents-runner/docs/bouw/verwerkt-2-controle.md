# Verwerking controle 2 (Codex, 15 punten), 30-10-2026, Claude 1

Alle punten hersteld, met een regressietest per punt in `tests/test_bouw.py` (116 goed).

- X1: het voorbeeld in een onvolledig verslag gebruikt de eigen firmacode, of `<firmacode>` zonder firma; elk
  foutverslag met een bekende firma gaat door de toets.
- X2: de codes HA, HARC, HB en HARM zijn kenmerken (hoofdletters, zodat hectare geen code is); `kruis()` toetst nu ook
  bandwoorden en de persoon. Vrije velden van een kandidaat gaan eerst door `schoon_veld()`.
- X3: "groep" en "onafhankelijk" alleen in de zin van een band; "partner" alleen als partnerbedrijf, vaste partner en
  dergelijke. Gewone bouwtaal en een firmanaam als "Renovatie Partners" passeren.
- X4: naar het model gaat `modelwerkwijze()`: zonder het deel "Voor wie ik werk" en zonder elke regel die een firma noemt.
- X5: `vraag.naar_buiten_fouten()` toetst werk, omvang en gemeente: persoonsgegevens, een naam na bij of voor, een
  straat in de gemeente, een firmanaam, te lange velden.
- X6: KBO alleen met de exacte host, het nummer in de url en in de tekst, en de status uit de statusregel ("Niet actief"
  is niet actief). Een gelezen pagina zonder tekst bewijst niets.
- X7: De Regisseur kreeg een regel in zijn systeemtekst en in de tooltekst: elk antwoord over Bouw hoort bij een firma,
  alleen het item van die vraag, nooit beide firma's in een antwoord. Zijn vaste identiteit blijft; hij schrijft zelf
  geen mails naar buiten.
- X8: bedragen als losse tokens met de schrijfwijze uit het laatste scheidingsteken; subtotalen, tussentotalen,
  kortingen en voorschotten tellen niet als totaal; bij meer eindtotalen het grootste, met een melding.
- X9: opties en stelposten staan apart en tellen niet in de vergelijking per post; zonder bevestigd totaal geen
  vergelijking per post.
- X10: `redigeer()` haalt ook werf-, adres-, project- en referentieregels en elk straatadres met nummer weg, plus de
  werfstraat van het project. OFFERTE_NAAR_AI blijft uit tot het ja van Mehdi.
- X11: een rondedeadline van 420 seconden (`lees_bestanden`), daarna niets meer gedownload; de rest staat erbij.
- X12: `files/search/continue_v2` tot vijf pagina's.
- X13: lessen en collega's gaan naar het zoekmodel, zonder de regels die een firma noemen.
- X14: `uitrol.sh` stopt als mijnagents-runner niet schoon is.
- X15: regressietests voor alle punten hierboven.
