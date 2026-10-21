# Opdracht Codex ronde 5 (ontwerpronde): de levensloop van .herstel

Van Claude, 16-10-2026. Rondenaam: "Borduitrol mijnagents: ontwerpronde (ronde 5)". Bevindingen vanaf BU-23. Alleen lezen,
zelfde grenzen (werkafspraken v1.3; geen SSH of netwerk naar *.globaal.be).

## Waarom

Stopregel (punt 4.7): hoog+middel 8, 4, 4, 4. Twee herstelrondes zonder daling. Jouw ronde 4 zegt zelf: "het ontwerp van
één overschrijfbare `.herstel` deugt nog niet wanneer een eerdere herstelpoging openstaat". Mijn verwerking:
`docs/codex/verwerkt-4-borduitrol.md` (BU-19 tot BU-22 allemaal nagemeten en gelijk). Code: `ad0ceff`,
`/Users/mehdichegini/dev/_bord-uitrol/mijnagents/deploy.sh`.

## Oorzaak volgens Claude

Eén markering met twee rollen: een openstaand herstel uit een vorige ronde én de lopende wissel van deze ronde, samen
met de regel uit ronde 1 dat een nieuwere revisie mag bouwen terwijl een herstel openstaat ("er is dan geen gezond bord
te beschermen"). Daarnaast het opruimen vóór de metagegevens geschreven zijn (BU-21).

## Opties

A. **Een open herstel blokkeert elke nieuwe bouw.** Zolang `.herstel` bestaat, probeert elke ronde alleen het herstel;
   lukt dat niet, dan exit 1 en geen bouw. Een uitrol schrijft `.herstel` dus alleen als er geen open herstel is; de
   markering wordt nooit overschreven. Ze bevat `VORIGE-ID KANDIDAAT-ID revisie poging`. Hervatten: draait precies het
   KANDIDAAT-ID gezond, dan voltooien; draait precies het VORIGE-ID gezond, dan `:latest` terug en opruimen; anders
   terugzetten. De markering verdwijnt pas na geslaagde schrijfacties van `.built` en `.built_id`, of na een
   nagekeken `:latest`. `afbreken` gebruikt `VORIGE` als hersteldoel en laat de markering staan zolang de tag niet
   nagekeken is. De nacontrole van het draaiende ID geldt altijd.
   Gevolg: is de vorige image blijvend kapot (het herstel faalt ronde na ronde), dan wacht ook een herstelde revisie
   op een mens. Die ziet elke verandering in het log en kiest: `.pauze` en met de hand ingrijpen, of `rm .herstel`
   (de volgende ronde rolt dan HEAD uit met de laatst bekende goede `:vorige` als terugrolimage).
B. **Twee markeringen.** `.herstel` (open herstel, nooit overschreven door een uitrol) en `.wissel` (lopende wissel van
   deze ronde). Behoudt de regel dat een nieuwere revisie mag bouwen als het herstel faalt, met meer toestanden.
C. Iets anders dat jij voorstelt, bijvoorbeeld een kleinere vorm van de uitrol zelf.

## Vragen

1. Welke optie raad je aan om BU-19 tot BU-22 te sluiten zonder nieuwe randgevallen, met de kleinste toestandsruimte?
2. Bij A: botst het blokkeren bij een mislukt herstel met jouw eis uit CX10 ("niet blijvend geblokkeerd bij een
   tijdelijke storing")? Mijn lezing: die eis gold `.mislukt` (een revisie); een tijdelijke storing van het herstel lost
   zichzelf op omdat elke ronde het herstel opnieuw probeert, en alleen een blijvend kapotte vorige image vraagt een mens.
3. Welke toestanden en overgangen moeten de tests minstens dekken om dit ontwerp af te sluiten (een korte lijst)?
4. Staat er buiten `.herstel` nog een punt van ernst hoog of middel open dat merge en één bewaakte uitrol tegenhoudt?

Antwoordvorm: beslissing eerst (welke optie), dan BU-n vanaf BU-23 als die er zijn, dan de antwoorden, en de drie
afsluitpunten.
