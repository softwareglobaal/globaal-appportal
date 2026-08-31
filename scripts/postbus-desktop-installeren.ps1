# Zet de Postbus als lokale MCP-server in de Claude desktop-app.
#
#   powershell -ExecutionPolicy Bypass -File postbus-desktop-installeren.ps1
#
# Draai dit op de PC van de collega, ingelogd onder ZIJN Windows-profiel. Het
# configuratiebestand staat in dat profiel, dus dat profiel is meteen de grens:
# een collega die hetzelfde Claude-account deelt maar een eigen Windows-login
# heeft, krijgt hier niets van mee.
#
# Waarom de omweg via mcp-remote: claude_desktop_config.json kent alleen
# stdio-servers (command/args) en heeft geen url-veld. Zet je er toch een url
# in, dan herschrijft de desktop-app het bestand bij het opstarten en gooit de
# hele mcpServers-sectie plus een paar preferences-sleutels weg, zonder melding.
# mcp-remote is een lokale brug die van stdio naar HTTP vertaalt en de
# OAuth-login afhandelt.
#
# Na dit script volgt de eenmalige login, zie de slotregels die het afdrukt.

$ErrorActionPreference = 'Stop'

# Vastgezette versie. Zonder pin haalt npx altijd de nieuwste op en kan een
# release de koppeling breken op een moment dat niemand erop let. Werkt deze
# versie niet, zet hem dan een stap terug op 0.8.1.
$BRUG_VERSIE = '0.8.2'
$URL = 'https://post.globaal.be/mcp'
$NAAM = 'postbus'

function Zeg($tekst) { Write-Host $tekst }
function Fout($tekst) { Write-Host "FOUT: $tekst" -ForegroundColor Red }

Zeg "== Postbus instellen in de Claude desktop-app =="
Zeg ""

# --- 1. Draait de app nog? -------------------------------------------------
# Niet afsluiten vanuit dit script: dat is de app van de gebruiker en die kan
# onbewaard werk bevatten. Alleen melden.
$app = Get-Process -Name 'Claude' -ErrorAction SilentlyContinue
if ($app) {
    Fout "Claude staat nog open. Sluit de app volledig af (ook uit het systeemvak) en draai dit script opnieuw."
    Fout "Anders overschrijft de app bij het afsluiten wat we nu wegschrijven."
    exit 1
}
Zeg "[1/5] Claude is afgesloten, goed."

# --- 2. Is Node aanwezig? --------------------------------------------------
$node = Get-Command node -ErrorAction SilentlyContinue
$npx = Get-Command npx -ErrorAction SilentlyContinue
if (-not $node -or -not $npx) {
    Fout "Node.js ontbreekt op deze PC. De brug kan niet draaien."
    Fout "Installeer de LTS-versie via https://nodejs.org en draai dit script daarna opnieuw."
    exit 1
}
Zeg "[2/5] Node gevonden: $(node --version)"

# --- 3. Is de server bereikbaar vanaf deze PC? -----------------------------
# Zonder token hoort de Postbus 401 te geven. Dat is het bewijs dat we de
# juiste server aan de lijn hebben en niet een foutpagina of een blokkade.
try {
    $r = Invoke-WebRequest -Uri $URL -Method Post -UseBasicParsing -TimeoutSec 15 `
        -ContentType 'application/json' -Body '{}'
    $code = $r.StatusCode
} catch {
    $code = $null
    if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
}
if ($code -eq 401) {
    Zeg "[3/5] Postbus bereikbaar (401 zonder token, zoals verwacht)."
} elseif ($null -eq $code) {
    Fout "Postbus niet bereikbaar vanaf deze PC. Controleer de internetverbinding."
    exit 1
} else {
    Fout "Postbus antwoordt met $code in plaats van 401. Niet doorgaan, eerst uitzoeken."
    exit 1
}

# --- 4. Configuratiebestand bijwerken --------------------------------------
$map = Join-Path $env:APPDATA 'Claude'
$pad = Join-Path $map 'claude_desktop_config.json'
if (-not (Test-Path $map)) { New-Item -ItemType Directory -Path $map | Out-Null }

if (Test-Path $pad) {
    $stempel = Get-Date -Format 'yyyyMMdd-HHmmss'
    $reserve = "$pad.$stempel.bak"
    Copy-Item $pad $reserve
    Zeg "[4/5] Reservekopie: $reserve"
    $ruw = Get-Content $pad -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($ruw)) {
        $cfg = New-Object psobject
    } else {
        try {
            $cfg = $ruw | ConvertFrom-Json
        } catch {
            Fout "Het bestaande configuratiebestand is geen geldige JSON. Niets gewijzigd."
            Fout "Bekijk het handmatig: $pad"
            exit 1
        }
    }
} else {
    Zeg "[4/5] Nog geen configuratiebestand, we maken er een."
    $cfg = New-Object psobject
}

if ($null -eq $cfg.mcpServers) {
    $cfg | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue (New-Object psobject) -Force
}
if ($null -ne $cfg.mcpServers.$NAAM) {
    Zeg "      Er stond al een '$NAAM'; die wordt vervangen."
}

$server = [pscustomobject]@{
    command = 'npx'
    args    = @('-y', "mcp-remote@$BRUG_VERSIE", $URL)
}
$cfg.mcpServers | Add-Member -NotePropertyName $NAAM -NotePropertyValue $server -Force

# UTF-8 zonder BOM: Out-File en Set-Content zetten in Windows PowerShell een
# BOM of schrijven in de ANSI-codepagina, en daar struikelt een JSON-lezer over.
$json = $cfg | ConvertTo-Json -Depth 12
[System.IO.File]::WriteAllText($pad, $json, (New-Object System.Text.UTF8Encoding($false)))

# --- 5. Terugleescontrole --------------------------------------------------
try {
    $terug = (Get-Content $pad -Raw -Encoding UTF8) | ConvertFrom-Json
} catch {
    Fout "Het weggeschreven bestand leest niet terug als JSON. Zet de reservekopie terug."
    exit 1
}
if ($null -eq $terug.mcpServers.$NAAM) {
    Fout "De vermelding '$NAAM' staat niet in het bestand. Zet de reservekopie terug."
    exit 1
}
Zeg "[5/5] Weggeschreven en teruggelezen: $pad"

Zeg ""
Zeg "== Klaar. Nu de eenmalige login, doe dit samen met de collega. =="
Zeg ""
Zeg "  1. Log eerst uit op https://globaal.be, of gebruik een privevenster."
Zeg "     Staat er nog een sessie van iemand anders open, dan koppelt hij aan"
Zeg "     die persoon en ziet hij de verkeerde mailboxen. Zonder foutmelding."
Zeg "  2. Start Claude. De eerste keer duurt het een halve minuut: de brug"
Zeg "     wordt dan opgehaald."
Zeg "  3. Er opent een browser met de inlogpagina. Laat HEM inloggen, als zichzelf."
Zeg "  4. Controle in de chat: vraag 'welke mailboxen mag ik zien'."
Zeg "     Klopt het antwoord niet met wat je verwacht, dan is stap 1 misgegaan."
Zeg ""
Zeg "Werkt het niet, dan staan de logbestanden hier:"
Zeg "  $env:APPDATA\Claude\logs\mcp.log"
Zeg "  $env:APPDATA\Claude\logs\mcp-server-$NAAM.log"
