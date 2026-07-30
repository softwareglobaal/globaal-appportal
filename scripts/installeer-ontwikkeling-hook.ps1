# Zet de ontwikkel-statistieken-hook op een Windows-machine (Claude Code).
#
# De hook meldt alleen metadata aan het organisatie-dashboard: sessie-id, repo,
# identiteit en of het een start, prompt of einde is. Nooit gespreksinhoud en
# nooit bestandsnamen.
#
# Draaien (PowerShell, in de map waar dit script staat):
#     .\installeer-ontwikkeling-hook.ps1 -Token "<het gedeelde token>" `
#         -Email "jouw.naam@globaal.be" -Naam "Jouw Naam"
#
# Het script is idempotent: nog eens draaien werkt gewoon en overschrijft
# alleen onze eigen hook-regels. Bestaande hooks van iets anders blijven staan.
#
# Waarom het e-mailadres erbij (2026-07-30): een gedeeld GitHub-account is geen
# probleem, want de auteur staat PER COMMIT in git. Maar dan moet elke machine
# wel een eigen git-identiteit hebben. Zonder die stap belandt het werk op
# software@globaal.be en valt het op niemand.
param(
    [Parameter(Mandatory = $true)][string]$Token,
    [Parameter(Mandatory = $true)][string]$Email,
    [string]$Naam = ""
)

$ErrorActionPreference = "Stop"

if ($Email -notmatch '^[^@\s]+@[^@\s]+\.[^@\s]+$') {
    Write-Host "FOUT: '$Email' ziet er niet uit als een e-mailadres." -ForegroundColor Red
    exit 1
}

# 1. Python moet aanroepbaar zijn; de vorige hook draaide op node en dat stond
#    op de betrokken machine niet op het PATH, waardoor hij stil faalde.
$py = (Get-Command python -ErrorAction SilentlyContinue)
if (-not $py) {
    Write-Host "FOUT: 'python' staat niet op het PATH. Installeer Python en probeer opnieuw." -ForegroundColor Red
    exit 1
}
Write-Host ("Python gevonden: " + $py.Source)

# 2. De hook zelf wegschrijven.
$hookDir = Join-Path $HOME ".claude\hooks"
New-Item -ItemType Directory -Force -Path $hookDir | Out-Null
$hookPad = Join-Path $hookDir "ontwikkeling-event.py"
$hook = @'
"""Claude Code-hook: meldt sessie-metadata aan het organisatie-dashboard
(ontwikkel-statistieken, tab Ontwikkeling). Alleen metadata, nooit inhoud.
De hook mag een sessie nooit blokkeren: fouten worden ingeslikt, exitcode 0."""
import json
import os
import subprocess
import sys
import urllib.request

URL = os.environ.get("ONTWIKKELING_URL",
                     "https://organisatie.globaal.be/ontwikkeling/event")


def _stil(args):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=5)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def main():
    token = os.environ.get("ONTWIKKELING_TOKEN", "").strip()
    if not token:
        return
    event = sys.argv[1] if len(sys.argv) > 1 else "prompt"
    try:
        invoer = json.loads(sys.stdin.read() or "{}")
    except Exception:
        invoer = {}
    sessie = str(invoer.get("session_id", ""))[:120]
    cwd = invoer.get("cwd") or os.getcwd()
    top = _stil(["git", "-C", cwd, "rev-parse", "--show-toplevel"]) or cwd
    repo = os.path.basename(top.rstrip("/\\")) or "onbekend"
    wie = (_stil(["git", "-C", cwd, "config", "user.email"])
           or os.environ.get("USERNAME") or "onbekend")
    body = json.dumps({"event": event, "repo": repo,
                       "gebruiker": wie, "sessie": sessie}).encode()
    req = urllib.request.Request(
        URL, data=body,
        headers={"Content-Type": "application/json",
                 "X-Ontwikkeling-Token": token})
    urllib.request.urlopen(req, timeout=4).read()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
'@
Set-Content -Path $hookPad -Value $hook -Encoding utf8
Write-Host ("Hook geschreven: " + $hookPad)

# 2b. De tijdmeter erbij (migratie 094). Dit is de bron die tijd PER APPLICATIE
#     geeft; de hook hierboven meet alleen wandkloktijd per werkmap. Zonder deze
#     stap staat een machine wel in de lijst maar levert hij geen uren per app.
$tijdBron = Join-Path $PSScriptRoot "ontwikkeling-tijd.py"
$tijdPad = Join-Path $hookDir "ontwikkeling-tijd.py"
if (Test-Path $tijdBron) {
    Copy-Item $tijdBron $tijdPad -Force
    Write-Host ("Tijdmeter geschreven: " + $tijdPad)
} else {
    Write-Host "LET OP: ontwikkeling-tijd.py niet gevonden naast dit script; tijd per applicatie wordt niet gemeten." -ForegroundColor Yellow
    $tijdPad = $null
}

# 3. Token, identiteit en git-configuratie. setx knipt lange waarden af en
#    meldt toch succes, daarom deze weg.
[Environment]::SetEnvironmentVariable("ONTWIKKELING_TOKEN", $Token, "User")
$env:ONTWIKKELING_TOKEN = $Token
[Environment]::SetEnvironmentVariable("ONTWIKKELING_GEBRUIKER", $Email, "User")
$env:ONTWIKKELING_GEBRUIKER = $Email
Write-Host "Token en identiteit gezet als gebruikers-omgevingsvariabelen."

# De globale git-identiteit is de hoofdsleutel: die reist mee met elke commit,
# ook als er via een gedeeld GitHub-account gepusht wordt.
& git config --global user.email $Email
if ($Naam) { & git config --global user.name $Naam }
$gitMail = (& git config --global user.email)
Write-Host ("Git-identiteit: " + $gitMail + $(if ($Naam) { " (" + $Naam + ")" } else { "" }))

# 4. De hook koppelen in settings.json, zonder andere hooks weg te gooien.
$settingsPad = Join-Path $HOME ".claude\settings.json"
if (Test-Path $settingsPad) {
    Copy-Item $settingsPad ($settingsPad + ".bak-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
    $settings = Get-Content $settingsPad -Raw | ConvertFrom-Json
} else {
    $settings = [PSCustomObject]@{}
}
if (-not $settings.PSObject.Properties.Name.Contains("hooks")) {
    $settings | Add-Member -NotePropertyName hooks -NotePropertyValue ([PSCustomObject]@{})
}

$cmd = 'python "' + $hookPad + '"'
$koppeling = @{ "SessionStart" = "start"; "UserPromptSubmit" = "prompt";
                "Stop" = "einde"; "SessionEnd" = "einde" }

foreach ($slot in $koppeling.Keys) {
    $stappen = @([PSCustomObject]@{
        type    = "command"
        command = ($cmd + " " + $koppeling[$slot])
        timeout = 10
    })
    # Bij het einde van een sessie ook de tijdmeter: die leest de transcripts en
    # stuurt alleen een optelsom per applicatie per dag.
    if ($tijdPad -and $slot -eq "SessionEnd") {
        $stappen += [PSCustomObject]@{
            type    = "command"
            command = ('python "' + $tijdPad + '"')
            timeout = 120
        }
    }
    $regel = [PSCustomObject]@{ matcher = ""; hooks = $stappen }
    # Bestaande regels van ONZE hooks eruit, andere hooks laten staan.
    $bestaand = @()
    if ($settings.hooks.PSObject.Properties.Name -contains $slot) {
        $bestaand = @($settings.hooks.$slot | Where-Object {
            -not ($_.hooks | Where-Object {
                $_.command -like "*ontwikkeling-event*" -or
                $_.command -like "*ontwikkeling-tijd*"
            })
        })
    }
    $nieuw = @($bestaand) + @($regel)
    if ($settings.hooks.PSObject.Properties.Name -contains $slot) {
        $settings.hooks.$slot = $nieuw
    } else {
        $settings.hooks | Add-Member -NotePropertyName $slot -NotePropertyValue $nieuw
    }
}
$settings | ConvertTo-Json -Depth 12 | Set-Content $settingsPad -Encoding utf8
Write-Host ("Hooks gekoppeld in: " + $settingsPad)

# 5. Proefmelding, zodat we meteen weten of het werkt en onder welke naam.
#    Via cmd en niet via een PowerShell-pipe: PowerShell levert de invoer niet
#    door aan een extern programma, waardoor de proef leeg zou aankomen.
& cmd /c ('echo {"session_id":"installatietest"} | python "' + $hookPad + '" start')
Write-Host ""
Write-Host "Klaar. Meld deze twee regels door aan AI en ICT:" -ForegroundColor Green
Write-Host ("  identiteit: " + $gitMail)
Write-Host ("  machine:    " + $env:COMPUTERNAME)
Write-Host ""
Write-Host "Die twee worden gekoppeld aan jouw persoon (ontwikkeling.gebruiker_koppeling"
Write-Host "en machine_koppeling); tot dan staat je werk op de tab Ontwikkeling onder"
Write-Host "'Nog te koppelen'."
Write-Host ""
Write-Host "Herstart Claude Code; de instellingen worden bij het opstarten gelezen."
