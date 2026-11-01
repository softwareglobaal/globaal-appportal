# Opdracht 13: postcode bij een gemeente zonder straat (01-11-2026)

Kijk de wijziging na op tak bouw-gemeente-postcode (niet gecommit: lees de werkboom, `git diff origin/main`). Antwoord in
het Nederlands, kort: AKKOORD of NIET AKKOORD, met ernst en bewijs (bestand:regel).

Gemeten op de VM na de uitrol: elke vraag aan De Aannemerszoeker met alleen een gemeente (bv. `gemeente: 3020 Herent`)
werd geweigerd met "gemeente niet gevonden". Oorzaak: Geopunt geolocation v4 geeft bij een resultaat op gemeenteniveau
`Zipcode: null` (`koppelingen/adresregister.py`, `lokaliseer`), en `bouw/vraag.py` `officiele_gemeente` eist een postcode.
Ook "3000 Leuven" en "3020" gaven postcode None.

Herstel (kleinste):
- `koppelingen/adresregister.py` `postinfo_gemeente(postcode)`: de gemeente van een postcode uit het officiele
  postinfo-register (api.basisregisters.vlaanderen.be/v2/postinfo/<postcode>), None bij 404.
- `bouw/vraag.py` `met_postcode(punt, gevraagd, postinfo)`: alleen als Geopunt een gemeente zonder postcode geeft, telt de
  postcode vooraan in de vraag, en alleen als het register die postcode bij dezelfde gemeente zet. Anders blijft het punt
  ongewijzigd en weigert `officiele_gemeente` zoals voorheen.
- `aannemerszoeker.py`: `centrum = Q.met_postcode(lokaliseer(gemeente), gemeente, postinfo_gemeente)`.

Live gemeten (Mac): "3020 Herent" -> 3020 Herent, "3000 Leuven" -> 3000 Leuven, "3001 Leuven" -> 3001 Leuven,
"9999 Herent" -> geweigerd, "3020 Leuven" -> 3020 Herent (Geopunt kiest de gemeente van de postcode; het verslag toont de
gebruikte gemeente). Vraag: is dat laatste aanvaardbaar, of moet een naam die niet bij de postcode past geweigerd worden?

Toets vooral: gaat er ooit iets anders dan een officiele postcode met gemeente naar buiten; kan de vraag via de postcode een
gemeente opdringen die Geopunt niet kent; breekt dit andere gebruikers van adresregister.py.
Tests: `python3 mijnagents-runner/tests/test_bouw.py` (240 goed).
