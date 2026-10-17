# Stand van de werfverslag-keten, gemeten op 17-10-2026 (door Claude, vóór het overleg)

Alles hieronder is live gemeten op de VM (bord mijnagents.globaal.be, werfapp werf.globaal.be) en op GitHub.

## De keten zoals bedoeld
agenda (Agendawacht) -> bezoek op het bord (Werfverslag voorbereider, tabel `werfbezoek`, W1-W11)
-> taken voor iCloud-wacht (foto's naar `<bezoekmap>/fotos/`) en Plaudwacht (transcript in de bezoekmap)
-> Mehdi klikt Keuzes + Proef op de bezoekpagina -> Werfverslag schrijver (claude-opus-5) schrijft
`<nr>-N werfverslag (concept).docx/.md` in de bezoekmap -> (PR #3/#67, niet live) concept in de werfapp
werf.globaal.be -> Mehdi kijkt na en verstuurt (SMTP leeg: zet alleen klaar).

## Gemeten
| Wat | Waarde |
|---|---|
| bezoeken op het bord (`werfbezoek`) | 22 levend + 5 "dubbel na verhuis; opruiming wacht op Mehdi" |
| stand | 15 klaar voor verslag, 10 te verzamelen, 1 verslag aanwezig, 4 verslag aanwezig maar bronnen onvolledig |
| proef gemaakt (`proef_pad`) | 0 van de 25 getoonde rijen |
| laatste opdracht aan de schrijver | 13-09-2026 (13 "voorbereid", 2 "proef 2309 1" vervallen) |
| werfapp | 549 verslagen = alleen ArchiSnapper-historiek, 29 bezoeken, 0 nieuwe concepten sinds livegang 24-09 |
| PR werfverslag#3 (conceptroute) en appportal#67 (brug schrijver -> werfapp) | OPEN sinds 16-10, CI groen, mergeable, niet live; Claude mag niet naar main pushen, Mehdi merget |
| iCloud-wacht | status FOUT: 5 fototaken open, reden `bezoekvenster_ontbreekt` (de taak van de voorbereider draagt geen tijdvenster) |
| Plaudwacht | 7 open zoektaken; 0 verwerkt |
| Agendawacht | "0 gekoppeld" aan deals; taken van de voorbereider (5) staan op "klaar", niet opgepakt |
| Commandocentrum | 29 impulsen naar de voorbereider opgepakt; "25 bezoeken met verslag in het venster; 0 pakket(ten) vol" |
| SMTP werfapp | leeg: versturen zet alleen klaar |
| cron | voorbereider werkdagen 7-19 elke 2 u; schrijver elke 5 min `--opdrachten`; dashboard-agent elk kwartier; iCloud-wacht op de Mac (launchd) |

## Wat dit betekent
Sinds 13-09 is er geen enkel werfverslag door de keten gekomen. Het verzamelen werkt deels
(15 bezoeken "klaar voor verslag"), maar: (1) de proef start alleen op Mehdi's klik ("geen tokens zonder
knop") en die klik is er sinds 13-09 niet geweest; (2) zelfs na de klik komt het concept alleen als Word in
de bezoekmap, niet in de werfapp, zolang PR #3/#67 niet live zijn; (3) de iCloud-wacht kan 5 fototaken niet
uitvoeren omdat het bezoekvenster ontbreekt; (4) de werkwijze van de voorbereider verwijst naar
`H-A vaste afspraken v1.5` en naar de skill op de Mac als winnaar bij tegenspraak, terwijl de agentnorm
zegt dat het bord/dashboard de bron van waarheid is; (5) de werkwijze van de schrijver (v2, 24-09) kent de
werfapp alleen als sectie onderaan, de dashboard-agent beschrijft een API (`POST /api/v1/verslagen`) die
de schrijver niet gebruikt (hij schrijft Word in Dropbox); (6) de hoofdagenda-regel E1/E4 en W2
(aanwezigheid via GPS, Locatiewacht) uit het plan van 12-09 zitten niet in W1-W11 van de voorbereider.
