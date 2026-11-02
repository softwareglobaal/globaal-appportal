# Codex-controle 43: uitslag van de twintig proeven nalezen (02-11-2026)

Lees alleen; wijzig niets. Kort antwoorden.

Reeks `docs/aankoop/proeven/prijsonderzoeker.json` (overleg 39) draaide op de VM met `aankoop/proefbank.py` (main
bd6dec4c, 01:36 tot 02:15, weekbenutting 65 naar 76 procent). Uitslag en verslagen: `docs/aankoop/proeven/uitslag-2026-11-02/`
(`uitslag.md` en `P01.md` tot `P20.md`; P01 heeft geen verslag). Automatisch: 14 van 20 geslaagd, 17 keer geen
aanbeveling (grens 8), dus de reeks is NIET GESLAAGD (X3). Geen enkele "nooit"-toets faalde.

Gemeten oorzaken (uit het werkverslag per proef op de VM):
- 25 keer ontbreekt de verzending: 16 keer gaf het model geen verzending (geen verzendpagina gelezen), 9 keer telde het
  citaat niet. Geweigerde citaten van de eigen aanbodpagina: "Voor 23.59 uur besteld, morgen gratis geleverd"
  (coolblue.be, P17 en P20), "Ordered before 23:59, delivered tomorrow for free" (coolblue.be, P13), "Verzending
  inbegrepen:" (refurbed.be, P06), "Alle bestellingen boven de € 75,00 excl. btw worden GRATIS bezorgd." (P12, prijs
  boven 75), "Gratis bezorgd en retour (vanaf € 99 excl. btw) ... In heel Nederland en België" (P14), "Voor
  verzendingen naar Belgie wordt 4,99 gerekend" (leapp.be, P06). `aankoop/aanbod.py:54-60` (GRATIS_VERZENDING kent
  geleverd, bezorgd, delivered en inbegrepen niet; een drempelbedrag telt als bedrag ertussen).
- 18 afwijzingen "niet meer beschikbaar": gratis nagemeten met de leestool, terecht (Coolblue AirPods "Nooit meer
  leverbaar", schema SoldOut; Toolstation OutOfStock; Coolblue Makita "Niet op voorraad").
- 7 keer "prijs niet bewezen op de gelezen pagina".
- P01 stopte op het plafond van de beurten (31 beurten), dus geen verslag (`aankoop/onderzoek.py:564`).

## Vragen

1. Lees per proef het verslag tegen het veld `handmatig` in de reeks. Per proef: geslaagd of niet, met de reden in een
   zin. Klopt de automatische keuring?
2. Is er ergens een veiligheidsfout (een aanbeveling die nooit mocht, een prijs zonder bewijs, een verzonnen gegeven)?
3. Welke herstellingen hebben de meeste invloed op het aantal terechte aanbevelingen, in volgorde, met `bestand:regel`?
   Alleen op deze metingen.
