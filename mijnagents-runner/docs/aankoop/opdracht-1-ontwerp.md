# Opdracht driehoeksoverleg: aankoopagents, eerst De Prijsonderzoeker (30-10-2026)

Lees alleen; wijzig niets. Nummer je punten zoals het script vraagt (Codex X1, Gemini G1, Claude K1).

## Wat Mehdi vroeg (samengevat uit zijn dictaat van 30-10-2026)

Mehdi wil een nieuwe groep agents: de aankoopagents. Ze draaien op de VM, op het bord mijnagents.globaal.be (achter
Authentik), zoals alle andere agents.

1. **Vandaag: een agent voor prijsonderzoek.** "Als iemand iets wil kopen, helpt die om het beste te zoeken." We weten
   wat we zoeken; de agent zoekt waar in Europa of in de wereld het best te koop is: nieuw, tweedehands of op een veiling.
2. **Later: een inventaris.** Een agent die weet wat Mehdi allemaal heeft, zodat hij betere aankopen kan doen en kan
   nagaan of iets compatibel is met wat er al is.
3. **Later: een wacht.** Een agent die "op wacht" staat en iets blijft zoeken wanneer we dat willen. Is een product te
   nieuw (nog duur, nog niet tweedehands), dan kijkt hij wanneer het wel op de markt komt.
4. De aankoopagents kunnen verschillende doelen hebben (firma's of privé).

Mehdi wil vandaag vooral de prijsagent: welke agent wat krijgt, en die agent moet weten wat hij moet doen.

## Context die je kunt nakijken (in deze werkmap, tak van GitHub main)

- De norm voor elke agent: `mijnagents-runner/AGENTNORM.md` (N1 tot N14, hoofdstuk 5 de ronde, hoofdstuk 8 een nieuwe
  agent). Een werkwijze moet de koppen "## Wat ik nooit doe" en "## Wat Mehdi beslist" hebben, met punten eronder.
- Het skelet: `mijnagents-runner/_sjabloon_agent.py`, de generator `mijnagents-runner/nieuwe-agent.py`, de gedeelde
  ronde `mijnagents-runner/koppelingen/bord.py` (`Agent.ronde`, `klaarzet`, `nood`, `collegas`).
- Een agent die al op het web zoekt met de Anthropic-API (web_search) en op verzoek een vraag beantwoordt (`--vraag`):
  `mijnagents-runner/ontwikkelaar.py`. Hoe De Regisseur een agent op verzoek start: `mijnagents-runner/regisseur.py`
  (rond regel 430 tot 500).
- Bestaande agents (geen enkele doet aankoop of prijzen): De Licentiewacht (accounts, licenties, kosten), De
  Wagenparkwacht (register van wagens), de mailwachten (lezen de postvakken), De Regisseur (praat met Mehdi via chat en
  Telegram), De Bode (Telegram, bellen).
- Wat Mehdi eerder met Claude zocht, als goede voorbeelden van zo'n vraag: een lidar-sensor (Livox Mid-360) voor een
  zelfbouwscanner; een vloerwasser (MOVA V70) die naar Suriname gaat (127/220 V, 60 Hz, ander stopcontact);
  werkstations met prijzen in Duitsland, België en India; montagetape onder een autoantenne; meetapparatuur
  (digitale waterpas, drone, scheurmeters). Lessen daaruit: Mehdi wil elke vraag letterlijk beantwoord, alle opties
  met voor- en nadelen, een klikbare link met foto bij elk product, de prijs in euro met bron, en geen bestelling of
  winkelmandje tenzij hij er zelf om vraagt.
- Er bestaat een prijzenboek van betaalde bouwmateriaalprijzen uit facturen van een eigen aannemingsfirma (1.866
  artikelprijzen, buiten deze repo) en klantaccounts bij groothandels waar de prijs pas na aanmelden zichtbaar is.

## Wat het overleg moet beslissen

Geef per punt een concreet advies met reden, en waar het kan een bestand:regel.

1. **Indeling.** Eén agent met meerdere functies, of aparte agents (Prijsonderzoeker op verzoek, Aankoopwacht met eigen
   ritme, Inventaris)? Toets aan de regel uit de skill: een nieuwe agent alleen bij een eigen mandaat, een eigen ritme
   of een eigen toegangsgrens. Is de inventaris een agent, of een register (gegevens) dat de agents lezen, en waar
   hoort dat register (bestaand kern-schema op organisatie.globaal.be, de Wagenparkwacht als model, of iets nieuws)?
   Welke afdeling (type) op het bord: een nieuwe afdeling `aankoop`?
2. **Functies van De Prijsonderzoeker.** Wat krijgt hij als vraag (product, specificaties, nieuw/tweedehands/veiling,
   land of regio, budget, waarvoor, voor welke firma of privé, deadline)? Wat doet hij in welke volgorde? Wat levert hij
   op (velden per aanbod: totale prijs met verzending, invoerkosten en btw, staat, verkoper en betrouwbaarheid, link,
   datum gezien, garantie, beschikbaarheid, compatibiliteit zoals spanning en stekker)? Welke volgende stap stelt hij
   voor? Waar ziet Mehdi het (bord, Telegram via De Bode, De Regisseur in de chat)?
3. **Bronnen en techniek.** Welke soorten bronnen (prijsvergelijkers, webwinkels in de EU en daarbuiten,
   tweedehandsplatformen, veilinghuizen, groothandels) en hoe zoekt hij (Anthropic web_search en web_fetch zoals De
   Ontwikkelaar, of iets anders)? Hoe voorkom je verzonnen prijzen en dode links (elke prijs met url en datum, pagina
   echt gelezen, verlopen aanbod weg)? Een plafond op zoekopdrachten en tokens per vraag.
4. **Grenzen.** Wat doet hij nooit (kopen, bieden, een verkoper contacteren, aanmelden op een account, persoonsgegevens
   doorgeven)? Wat beslist Mehdi altijd? Welke gegevens mogen naar de AI (alleen de productvraag)?
5. **Tests vooraf.** Twee of drie goede en foute voorbeelden die tests worden (bijvoorbeeld: een aanbod zonder link mag
   nooit in het verslag; een goedkoper aanbod met de verkeerde spanning voor Suriname moet als niet compatibel staan;
   een veilingprijs zonder opgeld en kosten is geen totaalprijs).
6. **Volgorde.** Wat bouwen we vandaag, wat later (wacht, inventaris, compatibiliteit), en wat is de eerste ronde die
   bewijst dat het werkt?

## Grenzen voor dit overleg

- Niemand bestelt, biedt of contacteert iets in dit overleg. Het gaat over het ontwerp.
- Een keuze die geld uitgeeft of een account aanmaakt is een `GRENS:` voor Mehdi (bijvoorbeeld een betaalde
  prijs-API). Zet die als eigen regel `GRENS: ...` met je advies.
- Hou het praktisch: de eerste versie moet vandaag te bouwen zijn met wat er al is.
