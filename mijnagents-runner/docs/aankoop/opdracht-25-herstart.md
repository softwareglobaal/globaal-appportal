# Overleg 25: wat liep fout met De Prijsonderzoeker, en opnieuw beginnen? (01-11-2026)

Lees alleen; wijzig niets.

## Wat Mehdi zei (01-11-2026, letterlijk)

"wat is de probeleem warrom kan je niet een agent maken die werkt zonder de token! doe 3 hoek overleg zo dat je het
begrijpt wat fout gelopen is en evntuuel start terug op nieuwe! moet werken en mag geen geld kosten! de voorwaarde is
niet veel hoor!"

Zijn voorwaarden: (1) de agent werkt, (2) hij kost geen geld. Met "token" bedoelt hij waarschijnlijk tokenkosten, niet
de aanmeldsleutel.

## Wat er gebeurde (eerlijk, met bron)

1. 30-10: De Prijsonderzoeker gebouwd op de betaalde API (`ANTHROPIC_API_KEY`). Proef 1 kostte ongeveer 18 dollar,
   proef 3 ongeveer 3 dollar, en geen van de proeven gaf een aanbeveling.
2. 01-11: Mehdi: geen API-kost, werk met zijn account. Overleg 14 en PR #152: `claude -p` op de VM met een token uit
   `claude setup-token`, een eigen leestool (MCP) en grendels.
3. Codex-controles 15 tot 24 en overleg 19 voegden telkens een grendel toe. Het ging om beheerde en centrale
   instellingen, `auth status`, een merkteken per token, stops bij `overageStatus`, `isUsingOverage` en 90 procent,
   de broncontrole, en bordvragen die blijven staan. PR #157 is live (55ca89c), 251 tests.
4. Resultaat: de agent heeft op de VM nog geen enkele prijsvraag gedaan. Het token staat er sinds 16:18 (via het
   aanmeldscript van de bouwsessie). De abonnementsproef weigert met de melding "Usage credits staan aan op dit
   account". De stream meldt `overageStatus: "allowed"` en `isUsingOverage: false`, gemeten op de VM en eerder op de laptop.
5. We weten niet zeker wat `overageStatus: "allowed"` betekent. Twee lezingen:
   - Usage credits staan aan en kunnen dus geld kosten als het inbegrepen gebruik op is;
   - het is alleen de toestand die extra verbruik toelaat, zonder dat er credits gekocht of aangezet zijn.
   Het veld `overageResetsAt` is ook aanwezig.
6. Andere agents van Mehdi die op zijn account werken, draaien op de Mac met de gewone aanmelding van Claude Code
   (geen token nodig), of als deelagent in een Claude Code-sessie.

## Vragen

1. Wat is de kernoorzaak dat de agent na een dag nog niet werkt? Wees eerlijk en kort.
2. Wat is het eenvoudigste ontwerp dat aan beide voorwaarden voldoet: werkt, en kost geen geld? Opties om te wegen, of
   een betere:
   - **A. Houden en vereenvoudigen.** Het VM-ontwerp blijft. De weigering bij `overageStatus: "allowed"` vervalt. Wat
     blijft: stoppen bij `isUsingOverage`, boven 90 procent van een limiet, en vooraf niet starten als de laatst gemeten
     benutting boven 90 procent lag en het venster nog niet herstart is. Restkans op kosten: alleen als het
     inbegrepen gebruik al op is en credits aanstaan, en dan hoogstens voor de eerste aanvraag. Andere grendels, die de
     agent onnodig blokkeren, schrappen.
   - **B. Houden zoals het is.** Mehdi zet Usage credits uit in claude.ai (Settings > Usage). Dan is de enige
     kostenroute dicht en werkt alles meteen.
   - **C. Opnieuw beginnen.** Een eenvoudige agent, bijvoorbeeld als Claude Code-agent op de Mac met de gewone
     aanmelding. Die kent dezelfde vraag over Usage credits.
3. Moet Mehdi iets beslissen of doen? Zo ja: hoogstens een ding, in een zin.
4. Wat leren we hiervoor voor elke volgende agent, zodat dit niet opnieuw gebeurt?
