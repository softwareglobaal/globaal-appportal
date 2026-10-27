Niet klaar. De meeste herstelpunten houden stand, maar de ochtendronde kan bij een totale mailfout toch een bestaande postvakmelding sluiten.

**Voor Claude en Shaniel**

1. **Hoog — C1 is niet volledig opgelost.** [vastleggen()](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:841) breekt terecht als het bord de open noden niet kan tonen. De [ochtendronde](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:276) vangt die fout echter op en eindigt normaal; [Ronde.__exit__](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/koppelingen/bord.py:441) stuurt dan een noodlijst zonder de oude postvakmelding. Een gerichte proef bevestigde dit pad. Behoud bij deze fout de bestaande noden of stuur geen afsluitende noodlijst; test de overgang via `main()`.

2. **Laag — fouttype blijft in het dagbestand.** Het fouttype staat nog in [‘Over deze vaststelling’](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:795). Dat blok veroorzaakt geen extra versie, maar kan na een volgende fout achterlopen. Gebruik daar vaste tekst; het logboek bevat het fouttype al.

Gedaan: beide diffs en de andere lezers nagekeken; niets gewijzigd.  
Nagekeken: vervanging tijdens lezen, klantmap, zomer en winter, Brusselse middernacht, oude kopie en kind-JSON hielden stand. Eén nieuwe versie van bestaande dagbestanden door de gewijzigde redentekst is verwacht. Van de vijf tests slaagde `test_dagvaststelling.py`; de overige liepen op tijdelijke bestanden vast in deze alleen-lezen sandbox, ook met `TMPDIR=/tmp`.  
Open: herstel punt 1 en draai de volledige tests in een schrijfbare omgeving. De opgegeven uitrolvolgorde is veilig **daarna**: VM `git pull`, `hotmail_server.py` eenmaal draaien, `vanaf` voor INBOX en Sent controleren, dan pas de volgende dagbundelaarronde.

**BESLISSING: niet klaar.**