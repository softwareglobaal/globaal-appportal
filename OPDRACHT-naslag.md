# Maakopdracht: naslagmodule Buildwise voor de werfverslag-agents

Context: repo globaal-appportal, map `mijnagents-runner`. De agents `werfverslag_voorbereider.py` en
`werfverslag_schrijver.py` (module `werfverslag_proef.py`, sjabloon `sjabloon_werfverslag.py`) maken
werfverslagen voor H-Architects (architectenbureau, België). Lees eerst `werfverslag_proef.py`,
`sjabloon_werfverslag.py` en `docs/kennisbank-inventaris.md` (inventaris van de Buildwise-kennisbank,
met in hoofdstuk 4.1 de tabel fase/werfpunt/bron en in hoofdstuk 5 een json-registervoorstel).

Op de server staan de pdf's lokaal: `~/appportal/mijnagents-data/naslag/pdf/tv/` (146 Technische
Voorlichtingen, bestandsnamen zoals `TVN_283 Plaatsen van buitenschrijnwerk  Deel1 ... (Vervangt de TV 188).pdf`,
ook `Digest_*.pdf`, `TV_RECAP_*.pdf`, `31200_nl_unprotected_TVN_2xx ...pdf`), `.../dimensionering/`,
`.../meetstaten/`, `.../keuring/`. Pad via env `NASLAG_PDF` (standaard `~/appportal/mijnagents-data/naslag/pdf`),
cache via `NASLAG_CACHE` (standaard `~/appportal/mijnagents-data/naslag/tekst`). pypdf staat in de venv.

Bouw, in deze repo (alleen onder `mijnagents-runner/`):

1. `naslag/bronnenregister.json`: één record per pdf in de vier mappen, afgeleid uit de bestandsnaam
   (sleutel zoals `TV283`, `DIGEST5`, `RECAP17`, `WTCB_R20`, `MEETSTAAT_2_6`, `VLARIO_...`), titel, map,
   bestand, jaar (uit de naam of uit `docs/kennisbank-inventaris.md`, anders null), uitgever, vervangt
   (uit "(Vervangt de TV 188)"-stukken in de naam), fases, werfpunten, licentie, status. De fases en
   werfpunten neem je over uit hoofdstuk 4.1 van de inventaris; wat daar niet in staat krijgt fases []
   en werfpunten [] en status "ongekend". Status "verouderd" voor TV's uit hoofdstuk 4.2 (vervangen of ouder
   dan 2010 zonder opvolger), anders "geldig". Schrijf het register met een script `naslag/bouw_register.py`
   (herhaalbaar; leest de pdf-mappen en de inventaris) zodat een nieuwe TV er later bijkomt zonder handwerk.
2. `naslag/naslag.py` met:
   - `register()` -> lijst records; `zoek(categorie=None, trefwoorden=(), fase=None, max_n=4)` -> beste
     records (score op werfpunten, titel, fase; verouderde achteraan en alleen als er niets geldigs is).
   - `tekst(sleutel)` -> volledige tekst van de pdf, één keer uit de pdf gehaald met pypdf (alle pagina's) en
     gecachet als `<cache>/<sleutel>.txt`; pagina-markeringen `[p. N]` in de tekst.
   - `fragmenten(sleutel, trefwoorden, max_tekens=1500, max_n=3)` -> de alinea's rond de trefwoorden, elk met
     paginanummer, zodat de schrijver kan citeren als "TV 283, Buildwise 2022, p. 41".
   - `naslag_voor_punten(onderdelen, max_bronnen=6, max_tekens=9000)` -> één tekstblok "### NASLAG" voor in
     de prompt: per onderdeel (bv. "Dakwerken: dakisolatie, zinkwerk dakkapel") de 1 tot 2 best passende
     bronnen met sleutel, titel, jaar, status en 1 tot 3 fragmenten. Hard budget max_tekens: nooit meer,
     want elke proef kost tokens.
   - Een CLI: `python naslag/naslag.py zoek "dakisolatie"`, `... tekst TV283 | head`, `... index` (alle pdf's
     in cache zetten, met voortgang en foutmelding per pdf die niet leesbaar is).
3. Koppeling in `werfverslag_proef.py`: bij `voorbereid` en bij `proef` wordt na het lezen van de bezoekmap
   `naslag_voor_punten(...)` toegevoegd aan de bronnenbundel (alleen als de keuze `naslag` van Mehdi niet
   "nee" is; standaard "ja"), met de regel voor Claude in de systeemprompt: "Naslag van Buildwise en NBN is
   auteursrechtelijk beschermd: citeer kort met bron (TV-nummer, uitgever, jaar, pagina), kopieer geen
   alinea's, stuur geen pdf door; vermeld bij een TV ouder dan 2010 dat een opvolger na te kijken is."
   In het verslagschema (`VERSLAG_SCHEMA`) krijgt elk punt een optioneel veld `naslag` (string, bv.
   "TV 283, Buildwise 2022, p. 41: raamaansluiting luchtdicht afwerken"). `sjabloon_werfverslag.naar_markdown`
   en `naar_docx` tonen dat onder het punt als regel "Naslag: ...", in dezelfde stijl als "Verantwoordelijke: ...";
   `van_markdown` leest het terug.
4. Tests in `mijnagents-runner/tests/test_naslag.py` (pytest, zonder netwerk, met twee kleine
   fixture-pdf's die je zelf maakt met pypdf of reportlab als dat er is, anders met een tekstcache):
   register bouwen uit bestandsnamen, zoeken op werfpunt, fragmenten met paginanummer, budgetgrens,
   markdown rondreis met het veld naslag.
5. Documentatie: `docs/Werfverslagen - naslag Buildwise v1.0.md` (hoe het werkt, de licentieregel,
   hoe een nieuwe TV erbij komt, hoe Mehdi naslag uitzet per bezoek) en een korte sectie in
   `werkwijze/werfverslag-schrijver.md` onder een kop "Naslag (Buildwise)".

Regels: Nederlands, geen emoji, geen kastlijntjes in tekst voor Mehdi. Verander niets aan de bestaande
proef-logica buiten de koppeling. Geen netwerk nodig. Alles moet compileren (`python -m py_compile`) en
de tests moeten slagen. Schrijf tot slot `VERSLAG-codex.md` in de repo-wortel: wat je maakte, wat je
aannam, wat open blijft.
