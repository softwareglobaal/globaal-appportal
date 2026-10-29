**Niet klaar.**

1. **OK — tests:** 14/14 en 27/27 geslaagd. Zie [regelbrontest](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/tests/test_regelbron_en_ha_voorrang.py:265) en [naamstructuurtest](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/tests/test_naamstructuur.py:1).
2. **OK — SHA-256:** de berekende hash van het volledige v1.10-bestand is gelijk aan de [pin](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/werkwijze/naamstructuur-regels.json:23).
3. **OK — gedrag:** een gewijzigd boek wordt ongeldig; v1.11 pauzeert zonder download. In twee proefrondes bleef de [nood aan Claude](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/naamstructuur_ronde.py:58) identiek en begon die niet met een aantal (N10). De [broncontrole](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/koppelingen/naamstructuur.py:448) is gelijk aan `origin/main`.
4. **FOUT — oude verwijzing:** de actieve werkwijzen van [Benamingenwacht](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/werkwijze/benamingen-wacht.md:3) en [Mappenwacht](/Users/mehdichegini/dev/_codex-namenwacht-test/mijnagents-runner/werkwijze/mappen-wacht.md:3) noemen v1.7 nog als bevestigd boek. Werk beide bij naar v1.10. “Welke versie geldt?” staat alleen nog als historische tekst.

Gedaan: alleen gecontroleerd.  
Nagekeken: tests, hash en gedrag.  
Open: twee werkwijzen bijwerken.

**NIET AKKOORD.**