# Dashboard-template - bouwgids voor apps op het Globaal-platform

> **Voor wie:** iedereen die een applicatie of dashboard bouwt dat op ons
> platform komt te draaien - ook als je verder geen toegang hebt tot onze
> systemen. Dit document is **zelfstandig**: alles wat je nodig hebt staat
> erin, en het is het enige dat je nodig hebt.
>
> **Zo gebruik je het:** geef dit document aan het begin van elke
> Claude-sessie mee als referentie ("volg dit document") en lever je app op
> volgens de checklist onderaan. Vrij experimenteren mag: een blueprint die
> hiervan afwijkt wordt niet weggegooid maar omgezet. Hoe eerder je dit
> volgt, hoe sneller je app live staat.
>
> De **integratie** op het platform (eigen subdomein, single sign-on,
> database-koppeling, deployment) doen wij. Jouw oplevering hoeft daar
> niets van te weten; hij moet er alleen klaar voor zijn.

## 1. Stack-eisen: zo draait je app bij ons

1. **Eén container.** Je app draait als één service met een `Dockerfile`
   in de repo-root. De poort komt uit de omgevingsvariabele `PORT`.
2. **Geen eigen login.** Ons platform zet een login-laag (single sign-on)
   vóór elke app. Bouw dus geen loginpagina, wachtwoorden of sessies: je
   app mag ervan uitgaan dat elke bezoeker al ingelogd en vertrouwd is.
   Heeft je app rollen nodig (bv. alleen-lezen versus beheer), maak die
   instelbaar via omgevingsvariabelen; de details stemmen we af bij
   integratie.
3. **Alle configuratie via omgevingsvariabelen.** API-sleutels, tokens en
   instellingen staan nooit in de code, nooit in git en nooit in
   screenshots - ook niet tijdelijk. De README somt elke variabele op met
   een regel uitleg.
4. **Data in één map.** Slaat je app iets op, doe dat in één datamap
   (bv. `/app/data`), zodat wij die als volume kunnen koppelen. Koppeling
   aan onze centrale database is mogelijk maar gebeurt in overleg.
5. **Geen aannames over het adres.** Geen hardgecodeerde domeinen of
   poorten in links; gebruik relatieve paden of een instelbare basis-URL.

## 2. Data-regels: alles gelinkt, niets los

1. **Personen en firma's zijn verwijzingen, geen losse tekst.** Bij ons
   bestaat elke persoon en elke firma precies één keer, centraal; apps
   verwijzen daarnaar. Hardgecodeerde namen verspreid door je code of data
   ("Joey", "Shilton") betekenen omzetwerk. Houd namen en entiteiten dus
   bij elkaar in één datalaag of configuratie, zodat ze bij integratie in
   één beweging aan onze centrale lijsten te koppelen zijn.
2. **Namen niet zelf bewerken.** De weergavenaam van een persoon wordt
   centraal bepaald. Toon wat je aangeleverd krijgt; knip geen voornamen
   af en verzin geen eigen formaat.
3. **Eén begrip, één woord.** Gebruik de terminologie die je bij de
   opdracht krijgt en houd die overal exact gelijk (dus niet "office",
   "bureau" en "kantoor" door elkaar voor hetzelfde). Ontbreekt er een
   term, kies er één, gebruik die consequent en meld het - verzin geen
   synoniemen.

## 3. Stijl en UX

1. **Elk getal is doorklikbaar.** Elke KPI, teller of totaal leidt naar de
   records erachter. Een cijfer zonder drill-down is niet af.
2. **Rustige, zakelijke huisstijl.** Geen emoji, geen em-dash
   (gedachtestreepje), geen icoonkaarten, geen marketing-taglines of
   AI-achtige opsmuk. Functioneel en strak.
3. Firma's voluit geschreven; KPI-cijfers werken als filter op de lijst;
   Excel-export waar dat zinvol is; tabellen met veel kolommen krijgen een
   instelbare kolomkeuze.

## 4. Oplevering: de checklist

- [ ] Repo met `Dockerfile`; de app start met alleen omgevingsvariabelen
- [ ] README: wat de app doet, elke omgevingsvariabele, de poort
- [ ] Geen sleutels of tokens in code, git-historie of screenshots
- [ ] Geen eigen loginpagina of gebruikersbeheer
- [ ] Namen en entiteiten in één koppelbare laag, niet hardgecodeerd
- [ ] Weergavenamen ongemoeid gelaten
- [ ] Terminologie consequent, afwijkingen gemeld
- [ ] Elk getal heeft een drill-down
- [ ] Geen emoji, geen em-dash, geen AI-opsmuk
- [ ] Opgeslagen data in één datamap

Twijfel je ergens over, vraag het vóór je bouwt - een vraag kost vijf
minuten, omzetwerk kost dagen.
