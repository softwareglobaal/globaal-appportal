Test tak `w4-p3-fototaak` van globaal-appportal (diff tegen origin/main) als eindcontrole voor live zetten.
Besluit: `docs/overleg-w4-p3/verslag.md` (X1-X4, K1-K5). Verwerkt na het overleg (commit 6a4c968):
- X4: `mijnagents-runner/mac/icloud_wacht.py` taken(): een H-A-taak wordt pas afgevinkt als elke geleverde HEIC een
  niet-lege JPG heeft; anders blokkeer "omzetting_mislukt". Test `tests/test_icloud_status.py::test_ha_heic_zonder_jpg_wordt_niet_afgevinkt`.
- X3: `FOTOHERSTEL` bevat alleen niet_in_fotomap en lijst_ontbreekt; jpg_ontbreekt geeft voorlopig geen taak.
Live zetten betekent: alleen `werfverslag_voorbereider.py` naar de VM. De iCloud-wacht-wijziging gaat pas live na een
sudo-uitrol op de Mac (Mehdi, K3); tot dan draait daar de oude versie.
Toets: correctheid van de diff, of de tests echt falen zonder de wijziging, en of live zetten van alleen de voorbereider
veilig is zolang de oude iCloud-wacht draait (risico: een lijst_ontbreekt/niet_in_fotomap-taak wordt na mislukte
sips-omzetting afgevinkt en komt niet terug; W4 blijft dan zichtbaar let_op met reden "alleen HEIC, geen JPG").
Tests draaien: `python3 -m pytest -q mijnagents-runner/tests/test_werfketen_eenheid.py mijnagents-runner/tests/test_werfketen_controles_11.py`
en `python3 mijnagents-runner/tests/test_icloud_status.py` (pytest staat mogelijk niet in je omgeving; meld dat dan).
Antwoord in het Nederlands, kort. Eindig met precies AKKOORD LIVE of NIET AKKOORD.
