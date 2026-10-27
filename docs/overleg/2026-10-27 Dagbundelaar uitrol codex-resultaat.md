**Voor Mehdi**

**Klaar met kanttekeningen:** akkoord om PR #103 met een merge-commit te mergen. Zet hem live nadat de rollback in stap c tegen de automatische herbouw is beschermd. Voeg de afgesproken controle op het live bord direct na de uitrol toe.

**Voor Claude en Shaniel**

1. **T1 — akkoord, laag.** Commit `1c5b454` zet de P9-vlag alleen op de [Docker-buildregel](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents/Dockerfile:31). [P9](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents/test_gesprekken_api.py:443) slaat uitsluitend bij waarde `1` over; [CI](/Users/mehdichegini/dev/_dagbundelaar-af/.github/workflows/regie-grendels.yml:24) zet die vlag niet. De fix staat als aparte commit op de PR-branch. Ik vond geen grendel die de oude Dockerfile-regel letterlijk vereist. `test_geen_echte_namen` gaf lokaal **3 goed, 0 fout**. De [technische referentie](/Users/mehdichegini/dev/_dagbundelaar-af/TECHNICAL-REFERENCE.md:3072) is niet onjuist, maar kan later de P9-uitzondering expliciet noemen.

2. **T2 — stap c niet akkoord, hoog.** Zonder `image:` gebruikt deze Compose-opzet normaal **`appportal-app-mijnagents:latest`**: de projectnaam staat in [docker-compose.yml](/Users/mehdichegini/dev/_dagbundelaar-af/docker-compose.yml:1), de servicenaam in de [override](/Users/mehdichegini/dev/_dagbundelaar-af/docker-compose.override.yml:5). `container_name` bepaalt de imagenaam niet. Controleer op de VM de gebruikte naam en bewaar het draaiende image-ID vóór de uitrol; `-p` of `COMPOSE_PROJECT_NAME` kan de projectnaam overschrijven. [Docker documenteert de standaard imagenaam](https://docs.docker.com/reference/cli/docker/compose/build/) en [projectnaamvoorrang](https://docs.docker.com/compose/how-tos/project-name/).  
   De terugtag werkt, maar [deploy.sh](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents/deploy.sh:16) bouwt bij een afwijkende `.built` op de volgende crontik opnieuw. Pauzeer daarom de **borddeploycron**, controleer of geen bouw meer loopt, tag het oude ID terug en gebruik `docker compose up -d --no-build --force-recreate --no-deps app-mijnagents`. Controleer daarna het werkelijk draaiende image-ID en de routes. Vier minuten zonder nieuwe `.built` bewijst op zichzelf geen mislukte bouw.

3. **T3 — akkoord mits live nacontrole, middel.** De proef met databankkopie dekt de controle vóór uitrol. Stap a–f noemt X4 **na** uitrol nog niet: lees dan `/dagen`, een echte dagpagina en de bestaande koppeling met `dubbel_van` én `ts` terug. Neem een mislukking mee als rollbackreden. De twee eerdere reviewpunten zijn in [dagbundelaar.py](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:648) en [de Dropbox-controle](/Users/mehdichegini/dev/_dagbundelaar-af/mijnagents-runner/dagbundelaar.py:875) verwerkt.

Gedaan: alleen gelezen.  
Nagekeken: git, code, overleg en namengrendel; CI- en VM-resultaten komen uit jouw metingen.  
Open: cronveilige rollback en live X4-controle.