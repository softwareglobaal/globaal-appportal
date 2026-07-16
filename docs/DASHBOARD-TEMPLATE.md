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
   records erachter; ook elke datum en elke entiteitsnaam (persoon, firma,
   leverancier) is een link naar zijn eigen plek. Een cijfer zonder
   drill-down is niet af. Bewust platte tekst (bijvoorbeeld een ruwe
   omschrijving van een bankafschrift, die geen entiteit is) markeer je
   met `class="plat"` zodat de uitzondering zichtbaar in de code staat.
   Bouw links via een linkmacro-bestand (`templates/links.html`) zodat het
   "waar klikt dit heen"-denkwerk een keer per soort waarde gebeurt, en
   dwing de regel af met een klikbaarheids-check in de CI die elke
   datum- of getalcel zonder link laat falen. Referentie-implementatie:
   `app/check_klikbaar.py` en `app/templates/links.html` in de
   globaal-kosten-repo.
2. **Rustige, zakelijke huisstijl.** Geen emoji, geen em-dash
   (gedachtestreepje), geen icoonkaarten, geen marketing-taglines of
   AI-achtige opsmuk. Functioneel en strak.
3. Firma's voluit geschreven; KPI-cijfers werken als filter op de lijst;
   Excel-export waar dat zinvol is; tabellen met veel kolommen krijgen een
   instelbare kolomkeuze.
4. **Secties zijn inklapbaar** (details/summary): de kop draagt de
   samenvatting (tellers, totalen) zodat een dichte sectie nog informatie
   geeft, de belangrijkste sectie staat standaard open en de browser
   onthoudt per gebruiker wat open stond. Zo blijft een pagina met veel
   secties navigeerbaar zonder scroll-mars.
5. **Belgische getalnotatie.** Bedragen als 6.418,10 (punt voor
   duizendtallen, komma als decimaalteken), maanden voluit ("november
   2025", niet "2025-11"). Overal dezelfde schrijfwijze.
6. **Een klik op een getal geeft zichtbaar resultaat.** Verschijnt de
   drill-down lager op de pagina, spring er dan naartoe (anker in de
   link). De gebruiker mag nooit hoeven zoeken waar het resultaat staat.
7. **De hoofdcijfers dragen de pagina.** KPI's staan groot en duidelijk
   bovenaan, niet als klein grijs tekstje; negatieve saldi kleuren rustig
   rood.
8. **Leesbaar en bedienbaar voor iedereen.** Hulptekst-grijs haalt de
   4,5:1-contrastrichtlijn, geen letters kleiner dan ongeveer 11px,
   toetsenbord-focus zichtbaar (nooit `outline: none` zonder vervanging),
   en op een smal scherm scrollen brede tabellen in hun eigen kader in
   plaats van de pagina te breken.

### De AI-tells: vermijdlijst

AI-tools produceren herkenbare standaardkeuzes die elke gegenereerde
website op elkaar doen lijken. **Loop deze lijst vóór oplevering na en
haal alles weg wat erop staat** - ook (juist) als Claude het uit zichzelf
toevoegde. Instrueer je AI-sessie er vooraf mee: "vermijd de AI-tells uit
het template-document".

**Visueel:**
- Emoji in koppen, knoppen, labels of lijstjes
- Rijen icoonkaarten (drie of vier kaarten naast elkaar met icoon, titel
  en één zin eronder)
- Paars/indigo/violet als hoofdkleur en kleurverlopen (gradients) in
  knoppen, koppen of achtergronden
- Hero-secties met een grote tagline en een "Get started"-knop - dit zijn
  interne werkinstrumenten, geen landingspagina's
- Glassmorphism, zware slagschaduwen, overal extra grote afgeronde hoeken
- Sparkle- en robot-iconen, "AI-powered"-badges, glow-effecten
- Typanimaties, confetti, fade-ins bij het scrollen
- Donkere modus als blikvanger terwijl niemand erom vroeg
- Voorbeeld- of placeholderdata die nog zichtbaar is bij oplevering

**Tekstueel:**
- Em-dashes (het lange gedachtestreepje)
- Marketingwoorden: "naadloos", "krachtig", "moeiteloos", "slim",
  "geavanceerd", "revolutionair", "alles-in-een"
- Drieslagen als "Snel. Simpel. Veilig."
- Titels met dubbele punt ("Inzicht: uw data in beeld")
- Uitroeptekens en juichende microcopy ("Gelukt! Je bent er bijna!")
- Engels-Nederlandse mix ("Save", "Dashboard overview" tussen
  Nederlandse labels) - alles in één taal, bij ons Nederlands
- Uitleg die niemand nodig heeft ("Dit dashboard geeft u een overzicht
  van...") - de app moet zichzelf uitleggen

De toets is simpel: als een schermafdruk van je app ook de demo van een
willekeurige AI-tool zou kunnen zijn, is het niet af. Kijk naar wat een
degelijke boekhoud- of bankapplicatie doet: rustig, dicht op de data,
geen versiering.

## 4. Oplevering: de checklist

- [ ] Repo met `Dockerfile`; de app start met alleen omgevingsvariabelen
- [ ] README: wat de app doet, elke omgevingsvariabele, de poort
- [ ] Geen sleutels of tokens in code, git-historie of screenshots
- [ ] Geen eigen loginpagina of gebruikersbeheer
- [ ] Namen en entiteiten in één koppelbare laag, niet hardgecodeerd
- [ ] Weergavenamen ongemoeid gelaten
- [ ] Terminologie consequent, afwijkingen gemeld
- [ ] Elk getal heeft een drill-down en de klik springt naar het resultaat
- [ ] Klikbaarheids-check in de CI (datum-/getalcellen zonder link falen;
      bewuste uitzonderingen dragen `class="plat"`)
- [ ] Bedragen en maanden in Belgische notatie
- [ ] Contrast, focus-zichtbaarheid en smal-scherm-gedrag nagelopen
- [ ] De AI-tells-vermijdlijst nagelopen, alles wat matcht verwijderd
- [ ] Opgeslagen data in één datamap

Twijfel je ergens over, vraag het vóór je bouwt - een vraag kost vijf
minuten, omzetwerk kost dagen.
