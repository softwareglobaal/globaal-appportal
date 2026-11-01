# Verwerking controle 7 (Codex, 6 punten), 30-10-2026, Claude 1

- X1: een site is pas bewezen met het ondernemingsnummer, de naam van de firma en de letterlijke zin over het werk
  (het bewijs dat het model citeert) op gelezen pagina's van die site; een nummer in een voettekst alleen volstaat niet.
- X2: alleen geldbedragen tellen (decimalen, duizendtallen of een euroteken); een bedrag krijgt het label vlak ervoor,
  en het label van de regel alleen als het het enige geldbedrag is. "30 dagen" en "6 weken" zijn geen bedrag.
- X3: H A, H B, H.A. en H.B. met spaties of punten; huisnummers met een letter (5A), voor of na de straat, ook uit kern.
  Telefoonnummers staan niet in kern.firma (geen kolom); de vaste lijst in scheiding.py blijft hun bron.
- X4: klantnaam, contact en naam als regel, en Franse adressen (rue, avenue, place ...) in de redactie.
  OFFERTE_NAAR_AI blijft uit.
- X5: zuster alleen als zusterbedrijf, zusterfirma en dergelijke of als los woord; een zusterbalk is bouwtaal.
- X6: regressietests: 202 bouwtests.
