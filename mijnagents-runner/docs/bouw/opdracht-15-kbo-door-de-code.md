# Opdracht 15: de code leest de KBO zelf (01-11-2026)

Kijk de wijziging na op tak bouw-kbo-zelf (niet gecommit: lees de werkboom, `git diff origin/main`). Antwoord in het
Nederlands, kort: AKKOORD of NIET AKKOORD, met ernst en bewijs (bestand:regel).

Gemeten op de VM (main 6eebce5): twee echte vragen gaven 4 en 5 firma's, maar alle op "na te kijken". De web_fetch van het
model opende geen enkele KBO-pagina, dus `kbo_actief` en `kbo_zetel` (`bouw/zoeken.py`) vonden nooit een gelezen
KBO-pagina en de afstand bleef onbekend. De KBO-pagina's zijn vanaf de VM en de Mac wel leesbaar (zo vult
`bouw/kern_adres.py` kern).

Herstel:
- `bouw/zoeken.py` `kbo_van_code(nummer, haal)`: leest toonondernemingps.html van precies dit nummer; telt alleen als de cel
  Ondernemingsnummer exact dit nummer toont; status uit de cel Status (Actief = True, Stopgezet en dergelijke = False,
  anders None); plaats = postcode en gemeente van "Adres van de zetel". Een natuurlijk persoon heeft geen zetel op de
  pagina: dan, alleen bij precies 1 vestigingseenheid en een actieve status, postcode en gemeente van "Adres van de
  vestigingseenheid" op toonvestigingps.html (ook daar het nummer exact). Nooit de straat.
- `lees_kbo(firmas, haal, deadline)`: per geldig nummer (modulo 97) een keer; OSError laat het nummer weg; stopt aan de deadline.
- `keur(..., kbo=None)`: wat de code las gaat voor op een pagina die het model las; de rest van de keuring blijft (site
  bewezen met nummer, naam en zin op de eigen site; afstand vanaf de KBO-plaats met Geopunt).
- `aannemerszoeker.py`: `kbo = Z.lees_kbo(firmas, kbo_haal, deadline)` voor de keuring.
- `bouw/verslag.py`: toont de KBO-plaats als die er is, anders wat het model gaf.
- VORM: het model zoekt het nummer op de eigen site en leest de KBO niet meer (spaart lees- en tokenbudget).
- `werkwijze/aannemerszoeker.md` versie 1.1 (wordt na de merge met `werkwijze_naar_bord.py aannemerszoeker --zet` op
  het bord gezet, na het verschil te bekijken).

Live gemeten (Mac): vijf nummers van vandaag gaven alle vijf actief met postcode en gemeente, ook twee natuurlijke personen.
Tests: `python3 mijnagents-runner/tests/test_bouw.py` (258 goed).

Toets vooral: kan een pagina van een andere onderneming meetellen; kan een straat of een persoonsadres naar buiten gaan
(Geopunt krijgt alleen 'postcode gemeente'); is een vestigingseenheid van een natuurlijk persoon een redelijke plaats voor de
afstand; tijd en aantal oproepen naar de KBO per vraag.
