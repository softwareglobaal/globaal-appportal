# Codex-controle 36: herstel na overleg 35 (01-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Bekijk `git diff 6babd78a..8d0d5616` op de tak `aankoop-eigen-eisen`. Achtergrond: `docs/aankoop/opdracht-35-eigen-eisen.md`
en het besluit in `docs/aankoop/rapport-35-eigen-eisen.md` (A tot D, X1, X5, G3, K3, K5 aangenomen).

Les van overleg 25: grendels alleen op een gemeten en begrepen signaal. Na deze controle draait dezelfde vervolgvraag
echt op de VM; dat resultaat telt. Een hoge fout noem je alleen met een concreet scenario dat in die echte ronde een
verkeerde aanbeveling of een betaling geeft.

Keuzes om te toetsen:
- X1 dekt de modelcode die de vraag noemt (modelcode, typenummer, artikelnummer, fabrikantcode). Een kleur of variant
  zonder code in de vraag is niet bindend; het model beoordeelt die als eigen eis ("nee" sluit uit).
- G3: alleen EAN-13, met label op beide pagina's en geldig controlecijfer; elke pagina precies een EAN.
- K3: via dezelfde EAN telt niets als de modelcode van het aanbod niet op de andere pagina staat, of als een modelnaam
  uit de titel van het aanbod (V70) daar ontbreekt.

## Vragen

1. Voert de diff de aangenomen punten uit zoals besloten? Per punt: ja, of wat ontbreekt met `bestand:regel`.
2. Een nieuwe fout van ernst hoog in de gewijzigde regels?
3. Klaar om live te gaan en de vervolgvraag op de VM te draaien: ja of nee.
