# Werfverslagen: naslag Buildwise v1.0

Versie 1.0, 18 oktober 2026.

## Werking

De naslagmodule leest het lokale `naslag/bronnenregister.json`. Elk record verwijst naar één pdf in `tv`, `dimensionering`, `meetstaten` of `keuring`. Het register bevat metadata, geen beschermde pdf-tekst. Bij de voorbereiding en de proef zoekt de schrijver per bouwonderdeel hoogstens twee passende bronnen. Hij haalt gerichte tekstfragmenten met paginanummer op en houdt het promptblok onder 9000 tekens. Zonder passende leesbare bron komt er geen naslagblok.

`NASLAG_PDF` wijst standaard naar `~/appportal/mijnagents-data/naslag/pdf`. `NASLAG_CACHE` wijst standaard naar `~/appportal/mijnagents-data/naslag/tekst`. De eerste lezing van een pdf gebruikt pypdf en schrijft alle pagina's met `[p. N]` in de tekstcache. `python naslag/naslag.py index` vult de cache en meldt per pdf een leesfout. `python naslag/naslag.py zoek dakisolatie` zoekt bronnen; `python naslag/naslag.py tekst TV283` toont de gecachete tekst.

## Licentie en voorzichtigheid

Buildwise-TV's, Digests, WTCB-rapporten, meetstaten en NBN-normen zijn auteursrechtelijk beschermd. In het concept komt alleen een korte parafrase met bronnummer, uitgever, jaar en pagina. Kopieer geen alinea's en stuur geen pdf door. Bij een TV van voor 2010 vermeldt de schrijver dat een opvolger na te kijken is. Het register bevat alleen de vier lokale pdf-mappen; NBN-normen staan daar momenteel niet in.

## Nieuwe TV

Plaats de pdf op de server in `NASLAG_PDF/tv/`. Draai `python naslag/bouw_register.py` vanuit `mijnagents-runner`; het script scant de vier mappen opnieuw en gebruikt hoofdstuk 4.1 en 4.2 van `docs/kennisbank-inventaris.md` voor koppeling en status. Een nieuwe TV buiten hoofdstuk 4.1 krijgt lege fases en werfpunten en status `ongekend`. Vul de inventaris aan om haar gericht te kunnen zoeken. Draai daarna `python naslag/naslag.py index`.

## Per bezoek uitzetten

Schrijf op de bezoekpagina bij **Keuzes > Opmerking** een afzonderlijke regel `Naslag: nee`. De schrijver behandelt die als een keuze voor dit bezoek. Als de bezoekpagina later een afzonderlijk veld `naslag` krijgt, werkt `naslag = nee` eveneens. Zonder keuze staat naslag aan. De keuze geldt voor voorbereiding en proef van dat bezoek.
