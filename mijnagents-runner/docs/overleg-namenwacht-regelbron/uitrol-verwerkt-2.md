# Verwerking door Claude 1 (T-0030, ronde 2)

- Hoog (deels aangenomen): echte atomiciteit kan alleen in de bordroute zelf (`app.py`), dus een codewijziging plus
  een nieuwe container voor één eenmalige handeling. Dat is niet de kleinste oplossing. Wel toegevoegd: na de POST
  leest het commando de laatste rij van `werkwijze_versie` voor die agent (alleen-lezen, `mode=ro`). Was de
  vervangen tekst niet 1.1, dan "STOP: <agent> nakijken", exit 1, en de tussentijdse tekst staat bewaard in
  `werkwijze_versie`. Niets gaat dus ongemerkt of onherstelbaar verloren. Het venster is milliseconden en Mehdi
  start de run zelf.
- Laag (niet gewijzigd): de normalisatie is dezelfde als in `werkwijze_naar_bord.py`; een bewerking die alleen
  afsluitende spaties raakt, blijft ook dan bewaard in `werkwijze_versie`.
- Getest (scenario H, `nep-curl.sh`): Mehdi bewerkt mappen-wacht via de bordroute vlak voor onze POST. Uitslag:
  "vervangen tekst was niet 1.1", "STOP: mappen-wacht nakijken", exit 1; zijn tekst is de laatste rij in
  `werkwijze_versie`. A tot G gaven dezelfde uitslag als in ronde 2.
