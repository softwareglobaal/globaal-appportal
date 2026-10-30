# Controle door Codex: afdeling Bouw (tak bouwagents, laatste commit, na herstel)

Lees alleen; wijzig niets. Nummer je punten X1, X2, ... met een ernst (hoog, middel, laag) en een bestand:regel.

## Wat er gebouwd is

Het ontwerp uit `mijnagents-runner/docs/bouw/rapport-1-ontwerp.md` met de verwerking in
`mijnagents-runner/docs/bouw/verwerkt-1-ontwerp.md`. De tak staat op `aankoopagents` (De Prijsonderzoeker, nog niet in
main); bekijk alleen het eigen werk met `git diff origin/aankoopagents...HEAD`. Nieuw: `mijnagents-runner/bouw/`
(scheiding, mail, vraag, zoeken, eigen, offertes, mappen, verslag), `aannemerszoeker.py`, `offertevergelijker.py`, de
twee werkwijzen, `tests/test_bouw.py`, `.github/workflows/bouw-grendels.yml`, `docs/bouw/uitrol.sh`. Gewijzigd:
`regisseur.py` (toelatingslijst, INHOUD_SOORTEN, tooltekst) en `tests/test_regisseur.py`.

Harde regel van Mehdi, letterlijk: H-Architects en Harmonie Bouw zijn voor de buitenwereld volledig gescheiden; geen
stuk van de ene noemt de andere of laat een band vermoeden. Neem die regel ook in je eigen tekst over: noem geen band.

## Wat je nagaat

Eerst: zijn de tien punten van controle 4 (`docs/bouw/rapport-4-controle.md`) echt opgelost? De
verwerking staat in `docs/bouw/verwerkt-4-controle.md`. Daarna dezelfde punten als toen, op de nieuwe code:

1. De scheiding (`bouw/scheiding.py`, `bouw/mail.py`, de runners): kan een mail, een verslag of een vergelijking toch
   een kenmerk van de andere firma bevatten (naam in een andere schrijfwijze, domein, telefoon, adres, ondernemingsnummer,
   een pad of mapnaam, de naam van een gevonden kandidaat, de werkomschrijving van het model)? Kan de andere firma als
   kandidaat of als inschrijver met naam opduiken? Blokkeert de grendel gewone bouwtaal onterecht?
2. De Aannemerszoeker: kan een firma zonder gelezen site, met een ongeldig ondernemingsnummer, zonder gelezen
   KBO-pagina of buiten de straal toch bovenaan staan (`bouw/zoeken.py` keur, kbo_actief)? Klopt de modulo 97-controle?
   Gaat er ergens een naam of adres van een bouwheer of het werfadres naar het model?
3. Eigen bronnen (`bouw/eigen.py`): kan de ene firma de mappen of de boekhouding van de andere lezen? Is de SQL veilig
   tegen invoer uit het web (ondernemingsnummers)? Klopt de vorm van `files/search_v2` van Dropbox?
4. De Offertevergelijker (`bouw/offertes.py`, `bouw/mappen.py`): kan een ontbrekend totaal of een ontbrekende post als
   nul tellen? Herkent hij een scan, een raming, een rekenfout, btw verlegd, een verlopen offerte? Zijn de regexen voor
   bedragen en totalen robuust (duizendtallen, "Totaal excl. BTW", "Subtotaal", kortingsregels)? Kan offerte-inhoud
   naar het model zonder OFFERTE_NAAR_AI? Is de redactie (`redigeer`) sterk genoeg voor X5?
5. De Regisseur: botst `vraag` voor de twee nieuwe agents met de bestaande regels? Past een ronde binnen de wachttijd?
6. De Agentnorm (`mijnagents-runner/AGENTNORM.md`): halen beide agents N1 tot N14 na de generator en de eerste ronde
   (N10: geen aantal in een noodtekst; N12: de ronde in het runnerbestand)? Klopt het uitrolscript?
7. Ontbrekende tests voor wat hierboven kan breken.

Geef bovenaan een beslissing: klaar, klaar met kanttekeningen, of niet klaar. Alleen punten met bewijs.
