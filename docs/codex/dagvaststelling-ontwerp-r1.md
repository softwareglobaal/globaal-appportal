## Voor Mehdi

**Niet klaar.** De dagvaststelling kan waardevol zijn, maar het ontwerp kan nu een onvolledig of dubbel overzicht als betrouwbaar tonen.

## Voor Claude en Shaniel

**D1, hoog.** Waar: [ontwerp:62](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:62), [ochtend.py:183](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/koppelingen/ochtend.py:183). De tweede ronde deelt de hartslag van Dagbundelaar. Na een mislukte ochtendstap kan haar `klaar` het ochtendbericht vrijgeven. Laat de vrijgave uitsluitend afhangen van de bewezen ochtendtaak. Toets N11 per taak.

**D2, hoog.** Waar: [dagbundelaar.py:98](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:98), [dagbundelaar.py:188](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/dagbundelaar.py:188). Met dag D als sleutel bundelt de oude runner de nieuwe vaststelling opnieuw en pakt haar op. Hij blijft WhatsApp en telefoon als ontbrekend melden. Pas uitsluitingen en noden in de bron aan; zijn runner mist bovendien de gedeelde ronde, N12.

**D3, hoog.** Waar: [whatsapp-wacht.md:3](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/werkwijze/whatsapp-wacht.md:3), [belwacht.md:3](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/werkwijze/belwacht.md:3), [ontwerp:67](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:67). De huidige WhatsApp-wacht verbiedt de volledige database, namen en oproepen; Belwacht beschrijft Xelion. Leg het nieuwe bronbezit en de gewijzigde mandaten eerst op het bord vast.

**D4, hoog.** Waar: [ontwerp:77](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:77), [Agentnorm:162](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/AGENTNORM.md:162). Alleen `/agent-status` dekt N4, N12, N13 en N14 niet. Een gezamenlijk script heet ook niet `belwacht.py`, dus N5 zakt. Geef elke wacht een eigen gedeelde ronde en controleer kennis en eindhartslag.

**D5, hoog.** Waar: [ontwerp:51](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:51), [organisatie.py:24](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/koppelingen/organisatie.py:24), [sync:6](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/planning/mac/data_uit_mehdi_sync.sh:6). Kern bevat medewerkers, geen klanten; een collega kan ook privé bellen. Behoud bronmarkeringen en behandel twijfel als privé. Controleer de toegang tot de Dropbox-submap met namen.

**D6, hoog.** Waar: [locatie_wacht.py:213](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/locatie_wacht.py:213), [agenda_wacht.py:394](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/agenda_wacht.py:394). Een auto ter plaatse bewijst geen gesprek; `afspraken_dag` verwijdert foutrecords uit de uitkomst. Koppel bewijs met afspraak-ID en persoon. Onderscheid geen afspraken van een ongelezen agenda; houd een falende Zoombron onbekend.

**D7, hoog.** Waar: [ontwerp:41](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:41), [app.py:1626](/Users/mehdichegini/dev/_dagvaststeller/mijnagents/app.py:1626). Alleen `buiten:` uitsluiten telt Zoom en Fathom dubbel. Een WhatsApp-oproep kan ook in iPhone-oproepen staan. Tel leidende gespreksrijen, koppel dezelfde oproep en houd chats apart.

**D8, middel.** Waar: [imapbron.py:58](/Users/mehdichegini/dev/_dagvaststeller/post/imapbron.py:58), [postvak.py:469](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/koppelingen/postvak.py:469). De nachtelijke lezer deelt geen IMAP-sessie met een ander proces. Gelijktijdige belasting, ontbrekende Sent-mappen, aliassen, leeslimieten en een oude Hotmail-kopie blijven risico’s. Toon hun telling als onvolledig en ontdubbel per bericht-ID.

**D9, hoog.** Waar: [app.py:588](/Users/mehdichegini/dev/_dagvaststeller/mijnagents/app.py:588), [sync:21](/Users/mehdichegini/dev/_dagvaststeller/mijnagents-runner/planning/mac/data_uit_mehdi_sync.sh:21). Een nog klaarstaand item wordt zonder revisiegeschiedenis overschreven. De sync haalt `dagboek` helemaal niet op. Bewaar versies, voeg de map toe en lees VM-bestand, borditem en Dropbox-kopie terug.

**D10, middel.** Waar: [ontwerp:59](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:59), [ontwerp:69](/Users/mehdichegini/dev/_dagvaststeller/docs/ontwerp-dagvaststelling.md:69). Drie herrekende dagen kunnen te kort zijn na Mac-slaap; gebruik een bronwatermerk. Test beide zomertijdwissels met Brusselse daggrenzen. Toegang tot de twee Mac-databases is nog ongemeten: proef onder de exacte launchd-app en geef alleen zo nodig een vaste helper schijftoegang, niet de algemene Python-interpreter. [Apple over appgegevens](https://developer.apple.com/documentation/security/accessing-files-from-the-macos-app-sandbox?language=objc).

**Vooraf vast te leggen tests:** mislukte keten en bezet slot; lege tegenover falende agenda; auto zonder gesprek; alle kanaaldubbels; onleesbare Sent-map en Zoom; slaap en inhalen; zomertijd; privacy per uitvoer; revisie vóór en na oppakken; teruglezing uit Dropbox.

Gedaan: ontwerp en code alleen gelezen.  
Nagekeken: normen en broncontracten; geen tests uitgevoerd.  
Open en oordeel: **bouwen nee**. Los eerst D1 tot en met D7 en D9 op, daarna de proeven voor D8 en D10.