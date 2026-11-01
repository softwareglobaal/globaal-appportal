# Verwerking Codex-controle 10 (01-11-2026)

Oordeel Codex: niet klaar. Alles hersteld; 178 prijstests en 55 regisseurtests groen.

1. **Hoog, onderdeel en tegenstrijdige regels (X1).** Nieuwe `aanbod.tegenstrijdig`: een pagina die ergens een losse
   andere frequentie noemt (50 Hz naast een gevraagde 60 Hz; 50/60 Hz telt als allebei), of een losse andere
   netspanning of een smal bereik dat de gevraagde niet omvat, bewijst niets. Dat geldt voor de bewijspagina en voor de
   eigen aanbodpagina. Zo is een pagina alleen bewijs als al haar netwaarden bij de eis passen, welk onderdeel het
   citaat ook noemt. Jouw tegenproef "Robot: 220-240 V, 50/60 Hz. Basisstation: 230 V, 50 Hz" geeft nu onbekend (test).
   Een breed bereik als 100-240 V en een accuspanning als 14,4 V spreken niets tegen.
2. **Hoog, regiocode.** `modelcode_op` weigert nu ook een aanhangsel na een liggend streepje, punt of plus
   (`VX-200EU_US`, `VX-200EU+US`); spaties en hoofdletters blijven gelijk (`vx 200eu`). Tests toegevoegd.
3. **Middel, X4.** Een rij in "gezien, niet nagekeken" vraagt nu een bewezen prijs: het citaat staat in hetzelfde
   zoekresultaat, bevat het bedrag en de munt, en heeft geen kostwoord ervoor of erin (`zonder_kostwoord`; "Shipping 19
   euro" valt weg). Een rij zonder bewezen prijs valt weg, zoals het besluit zegt.
4. **X3, kost.** `kosten` telt nu 0,01 dollar per zoekopdracht mee; de nood boven 2 dollar gebruikt die kost.
