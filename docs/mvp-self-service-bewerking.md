# MVP-ontwerp - Self-service app-bewerking via AI

*Laatst bijgewerkt: 2026-06-18*

## In één zin
Een niet-technische app-beheerder past z'n app aan door in een **tekstvak** te typen wat hij wil; een AI-agent maakt de wijziging op een aparte versie, toont een **preview**, en pas na **[Publiceren]** gaat het live - met volledige versiegeschiedenis op GitHub en altijd een weg terug.

## 1. Doel
- Gebruikers wijzigen hun eigen app **zonder code, terminal of GitHub** te zien.
- Elke **gepubliceerde** versie staat op GitHub `main` → versiebeheer + rollback.
- Elke **poging** komt in een branch + een auditlog → volledige "wie/wat/wanneer".
- Minder afhankelijkheid van één persoon voor het doorvoeren van wijzigingen.

## 2. Scope - pilot op één app
**Stagebeoordeling** als proof-of-concept: simpel, één bestand, géén financieel risico. Werkt het end-to-end, dán pas uitrollen naar de andere (en als laatste de financiële) apps.

## 3. Gebruikerservaring (wat de gebruiker ziet)
```
[ Pas deze app aan ]
  Beschrijf wat je wil veranderen:
  ┌─────────────────────────────────────────────┐
  │ Maak de opslaan-knop groen en voeg een      │
  │ export-naar-Excel-knop toe.                 │
  └─────────────────────────────────────────────┘
                              [ Voorstel maken ]
        ▼  (agent werkt ~10–60 sec)
  ✅ Ik heb de knop groen gemaakt en een export-knop toegevoegd.
  🔍 Bekijk je wijziging:   [ Preview openen ]
        [ Publiceren ]        [ Weggooien ]
```
- **Preview** = de aangepaste app draait op een tijdelijke link (achter SSO) - de gebruiker ziet z'n wijziging écht, vóór het live gaat.
- **Publiceren** → live + opgeslagen op GitHub. **Weggooien** → de live-app verandert niet.
- Lukt het de agent niet (of start de app niet meer op)? → vriendelijke melding, **live-app blijft ongemoeid**.
- De gebruiker raakt **nooit** GitHub, code of een terminal aan.

## 4. Architectuur (de verborgen motor)
1. **Bewerk-paneel (frontend)** - tekstvak + preview + knoppen, ín de app (zichtbaar voor de beheerder-groep van die app), achter SSO.
2. **Orchestrator (kleine service op de VM)** - ontvangt de instructie + de SSO-naam, en:
   - draait de **Claude Agent SDK** tegen een werkkopie van de app-repo, **op een nieuwe branch**, met een ingeperkte opdracht ("bewerk alleen deze app, raak geen secrets/login aan, hou 'm werkend");
   - doet een **start-test** (draait de app nog?);
   - start een **preview-instantie** (aparte poort + tijdelijk `…-preview`-subdomein);
   - bij **Publiceren**: branch → `main`, commit mét SSO-naam, **push naar GitHub**, deploy live;
   - schrijft elke aanvraag naar het **auditlog**.
3. **Git/GitHub (verborgen)** - `main` = gepubliceerd; branches = pogingen; commits op naam; push via de deploy key.

## 5. Modelkeuze (automatisch - cascade, goedkoop eerst)
De gebruiker kiest **nooit** een model; de orchestrator beslist automatisch via een **cascade** die leunt op de start-test die we toch al hebben:

```
goedkoop model probeert de wijziging
   ├─ start-test ✅  → preview tonen     (klaar, goedkoop)
   └─ start-test ❌  → automatisch opnieuw met een sterker model
```

**MVP: 2-traps cascade - Sonnet 4.6 (standaard) → Opus 4.8 (escalatie bij mislukte start-test).**

| Model | Input $/1M | Output $/1M | Rol |
|---|---|---|---|
| Haiku 4.5 | $1 | $5 | (later, optioneel) triviale tekst-/kleur-edits |
| **Sonnet 4.6** | $3 | $15 | **standaard** voor code-edits (sterk + ~40% goedkoper dan Opus) |
| **Opus 4.8** | $5 | $25 | escalatie - alleen de moeilijke gevallen |

Waarom Sonnet-eerst en niet Haiku-eerst: voor agentisch coderen is Haiku te zwak → het faalt vaak → veel escalaties → je betaalt dubbel. Sonnet-eerst is per saldo goedkoper én betrouwbaarder. Haiku kan later als extra ondergrens voor triviale edits.

## 6. Git-model
- **`main` = alleen gepubliceerde, stabiele versies.** Elke `Publiceren` = één nette commit, bijv.:
  `Angela (via bewerk-assistent): opslaan-knop groen + Excel-export - 2026-06-18 10:42`
- **Pogingen = branches** `poging/<app>/<datum>-<gebruiker>`. Gepubliceerd → samengevoegd naar `main`. Weggegooid → branch blijft bewaard (audit) en wordt na **14 dagen** opgeruimd.

## 7. Auditlog
Eén licht logbestand per app: *tijdstip · app · gebruiker (SSO) · instructie · branch · status (preview/gepubliceerd/weggegooid/mislukt) · samenvatting · commit-id.* → de volledige "wie probeerde wat, wanneer", **zonder** `main` te vervuilen.

## 8. Veiligheid & scope (ingebouwd - het maakt het bruikbaar)
- Een beheerder kan **alleen z'n eigen app-repo** raken.
- **Secrets** (`.env`) staan niet in de repo en gaan nooit naar de agent.
- De agent werkt op een **branch + preview**, nooit rechtstreeks op de live-app of de live-data.
- **Publiceren is altijd een bewuste klik** - niets gaat automatisch live.
- **Rollback altijd mogelijk** (alles is een commit).

## 9. Rollback
Omdat elke gepubliceerde versie een schone commit op `main` is, kan de beheerder terug naar elke eerdere stabiele versie. MVP: via git (door de admin). Later: een **"Vorige versies"-knop** in het paneel, zodat ook terugdraaien geen handwerk meer is.

## 10. Wat zit in de MVP - en wat (nog) niet
**Wel:** tekstvak → agent → branch → start-test → preview → publiceren/weggooien · auto-commit met SSO-naam · push branch + `main` · auditlog · automatische modelkeuze (cascade) · basis-rollback. **Eén app (Stagebeoordeling).**
**Nog niet:** uitrol naar financiële apps · uitgebreide test-suites (alleen een start-test) · gepolijste rollback-UI voor álle apps · meerdere tegelijke bewerkingen · Haiku-ondergrens.

## 11. Kosten
Token-gebaseerd. Met de cascade worden de meeste edits door **Sonnet 4.6** afgehandeld (~40% goedkoper dan Opus); alleen de moeilijke escaleren naar Opus. Ruwweg **enkele centen tot ~€1 per wijziging**. Pilot verwaarloosbaar.

## 12. Bouwstappen
1. Stagebeoordeling in een **eigen git-repo** (per-app-repo-stap).
2. **Orchestrator** bouwen (Agent SDK + branch/preview/publiceren + cascade-modelkeuze + auditlog).
3. **Bewerk-paneel** bouwen (tekstvak + preview + knoppen), achter SSO + beheerder-groep.
4. Deploy- en preview-poorten + push via de deploy key.
5. **End-to-end testen** op Stagebeoordeling.

## 13. Gekozen defaults (aanpasbaar)
- **Model:** automatisch, cascade Sonnet 4.6 → Opus 4.8.
- **Paneel:** ín elke app, zichtbaar voor de **beheerder-groep** van die app (`<app>-beheer`).
- **Wie is beheerder:** per app in te vullen in Authentik (eigen groep per app).
- **Weggegooide branches:** bewaren, na 14 dagen opruimen.
- **GitHub:** `main` = gepubliceerde versies; pogingen in branches.
