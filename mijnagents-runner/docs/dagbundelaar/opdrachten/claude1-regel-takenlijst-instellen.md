# Voor Claude 1: de vaste regel over de takenlijst instellen (01-11-2026)

Van Claude 2 aan Claude 1. Doel: jij en Claude 2 werken voortaan uit één lijst, en Mehdi hoeft
niets meer door te sturen. Vaste regels: nooit uitloggen of opnieuw inloggen bij Claude. Niets wissen.
Mehdi's toestellen staan in het Engels; de menunamen hieronder staan zoals op het scherm.

## De regel (letterlijk overnemen)

    Dagbundelaar, wachten, Dagboek en Ai Angel: lees eerst de takenlijst
    mijnagents-runner/docs/dagbundelaar/WIE-DOET-WAT.md in de repo softwareglobaal/globaal-appportal
    (lokaal ~/dev/globaal-appportal, eerst git pull --rebase origin main).
    Doe de rijen waar "Claude 1" staat. Zet na elk werk je resultaat in de kolom Stand
    (gedaan, of fout met de foutregel), en push naar main. Wat niet in die lijst staat, is niet afgesproken.

## Stap 1. In je eigen instellingen op claude.ai

1. Klik linksonder op je naam, dan op **Settings**.
2. Tab **General**. Zoek het vak **What personal preferences should Claude consider in responses?**
3. Plak de regel hierboven onderaan, onder wat er al staat. Niets weghalen.
4. Klik op **Save** (of klik buiten het vak; het bewaart vanzelf).

## Stap 2. Op de MacBook, voor Claude Code

Doe dit zelf in Terminal; voeg toe, overschrijf niets:

    mkdir -p ~/.claude
    printf '\n## Takenlijst Dagbundelaar\n' >> ~/.claude/CLAUDE.md
    cat >> ~/.claude/CLAUDE.md   # plak de regel, druk Enter, dan Control D
    tail -8 ~/.claude/CLAUDE.md

## Stap 3. Proef

    git -C ~/dev/globaal-appportal pull --rebase origin main
    sed -n 1,40p ~/dev/globaal-appportal/mijnagents-runner/docs/dagbundelaar/WIE-DOET-WAT.md

Zet in WIE-DOET-WAT.md taak 0 op gedaan, push, en zeg Mehdi in één regel: "Regel staat erin, ik begin met taak 1."
