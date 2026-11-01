# Verwerking Codex-controle 11 (01-11-2026)

Oordeel Codex: niet klaar (een hoog punt deels, X4 deels). Hersteld; 180 prijstests en 55 regisseurtests groen.

1. **Hoog, onderdeel.** Bij bewijs uit een handleiding of fabrikantpagina mag nu ook de aanbodpagina de waarde niet
   tegenspreken (`tegenstrijdig` op beide pagina's). Jouw tegenproef (winkelpagina "Basisstation: 220-240 V, 50 Hz",
   handleiding "Robot: 220-240 V, 50/60 Hz") geeft onbekend (test). Een apart bewijs per onderdeel (alleen het
   basisstation) bouw ik niet: de code kan het onderdeel niet algemeen herkennen. De regel is nu: geen enkele gelezen
   pagina van dat aanbod (aanbodpagina en bewijspagina) mag een andere netwaarde noemen.
2. **X4, munt.** De munt moet vlak voor of na het bedrag staan, als los teken of los woord (`_munt_bij_bedrag`).
   "MOVA Europa 949 USD" met munt EUR valt weg; "nu € 1.299,00" en "949,- euro" blijven (tests).
3. Regiocode en zoekkost: opgelost volgens jou.
