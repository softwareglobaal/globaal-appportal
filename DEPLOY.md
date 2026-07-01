# Deploy — medewerkerspagina (route A, op de VM-branch)

Deze bestanden zijn gebaseerd op de **vm-as-built-2026-06-26**-branch (wat de VM
draait), niet op main. Overschrijven via WinSCP is daarom veilig: elk bestand
matcht de VM, op de bedoelde wijziging na.

## 1. WinSCP — kopieer naar ~/appportal (paden 1-op-1)
| Lokaal (deze map) | Op de VM |
|---|---|
| docker-compose.yml | ~/appportal/docker-compose.yml |
| appportal-portal-role.sql | ~/appportal/appportal-portal-role.sql |
| portal/app.py | ~/appportal/portal/app.py |
| portal/models.py | ~/appportal/portal/models.py  (nieuw) |
| portal/requirements.txt | ~/appportal/portal/requirements.txt |
| portal/static/style.css | ~/appportal/portal/static/style.css |
| portal/templates/portal.html | ~/appportal/portal/templates/portal.html |
| portal/templates/medewerkers.html | ~/appportal/portal/templates/medewerkers.html  (nieuw) |
| portal/templates/medewerker.html | ~/appportal/portal/templates/medewerker.html  (nieuw) |

## 2. Op de VM (SSH) — committen op de branch
```bash
cd ~/appportal
git status --short          # moet EXACT deze 9 bestanden tonen (M/??), niets anders
git add docker-compose.yml appportal-portal-role.sql \
        portal/app.py portal/models.py portal/requirements.txt \
        portal/static/style.css portal/templates/portal.html \
        portal/templates/medewerkers.html portal/templates/medewerker.html
git commit -m "feat(portal): medewerkerspagina + centrale gebruikersdatabase (read-only)"
# optioneel (backup naar GitHub): git push origin vm-as-built-2026-06-26
```

## 3. Portal herbouwen — feature staat nog UIT (geen APPPORTAL_DB_URL)
```bash
docker compose up -d --build portal
docker compose ps portal          # healthy? portal werkt als vanouds, tegel nog niet zichtbaar
```

## 4. Per-app DB-rol aanmaken (kies een sterk wachtwoord, noteer het)
```bash
docker compose exec -T postgresql psql -U authentik -d appportal \
  -v pw="KIES_EEN_STERK_WACHTWOORD" -f - < appportal-portal-role.sql
```

## 5. Feature AANzetten
Zet in ~/appportal/.env (zelfde wachtwoord als stap 4):
```
APPPORTAL_DB_URL=postgresql+psycopg://portal:KIES_EEN_STERK_WACHTWOORD@postgresql:5432/appportal
```
Daarna:
```bash
docker compose up -d portal
docker compose logs --tail=20 portal
```

## 6. Bekijken
Log in op https://portal.globaal.be met een account in de groep **admin** of
**manager** -> tegel/link "Medewerkers" verschijnt -> 34 medewerkers, klik door
naar een profiel. (Geen admin/manager? Dan is dat juist de RBAC: 403 / geen tegel.)

## Terugrollen
```bash
cd ~/appportal && git revert --no-edit HEAD && docker compose up -d --build portal
# of: zet APPPORTAL_DB_URL leeg in .env + docker compose up -d portal  (feature uit)
```
