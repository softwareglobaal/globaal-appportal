**Niet klaar.** U1 is in de code opgelost. U2 is beter afgeschermd, maar nog niet volledig aan het eigen uitrolproces gebonden. Een nieuw punt van middelmatige ernst geeft bovendien een verkeerde dagtelling.

### Voor Mehdi

Als een oproep uit de bron verdwijnt, kan de dagvaststelling toch zeggen: “0 oproepen gezien”. Ze behandelt het oude bewijs dat die dag gelezen is nog als geldig, ook nadat dat bewijs vervallen is verklaard.

### Voor Claude en Shaniel

1. **V1, middel:** [dagbundelaar.py:663](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/dagbundelaar.py:663) neemt ook dekkingsrijen met `buiten:vervallen` mee. In een geheugenproef markeerde [mac_gesprekken.py:624](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:624) een verdwenen oproep én zijn dekking als vervallen, waarna de dagvaststelling “0 oproepen, 0 min gezien” gaf. Tel alleen actieve dekkingsrijen als bewijs en test deze volledige route.

2. **V2, laag, U2:** [uitrol_mac_gesprekken.sh:118](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/uitrol_mac_gesprekken.sh:118) vergelijkt met een sleutel in een bestand dat hetzelfde gebruikersaccount kan lezen. [De test](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/tests/test_mac_gesprekken.py:1042) probeert de directe aanroep zonder die sleutel. Bind de interne wissel aan een overgeërfde procesmogelijkheid en test ook een aanroep met een gekopieerde sleutel.

3. **V3, laag:** [De helper](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/mac/kopie/macgesprekken_kopie.c:98) telt overgeslagen oproepen over 62 dagen; [de runner](/Users/mehdichegini/dev/_dagvaststelling-f2/mijnagents-runner/koppelingen/mac_gesprekken.py:368) meldt dat aantal bij zijn kortere leesvenster. Beperk de melding met dagtotalen zonder persoonsgegevens.

Gedaan: laatste commit en geheel tegenover main gelezen.  
Nagekeken: U1-filter en tests; Claude meldt 33 Mac-tests goed. De geheugenproef voor V1 is hier uitgevoerd.  
Open: V1 tot V3, waarvan V1 live tegenhoudt.

live: nee