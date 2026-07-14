# Cutover-runbook — AppPortal als voordeur op de bestaande VM (globaal.be)

Dit draaiboek is specifiek voor jouw VM `54.80.98.233`, die al een **host-nginx**
(80/443) draait die `data.globaal.be` (= de OMV-app, poort 5000) en
`n8n.globaal.be` (n8n-container, 5678) bedient. We maken AppPortal's nginx de
nieuwe voordeur en hangen OMV + n8n eronder. Je andere projecten (via de
Cloudflare-tunnel) blijven ongemoeid.

**Vangnet:** gaat er iets mis, dan zet je met `sudo systemctl start nginx` de
oude host-nginx in seconden terug.

> Doe eerst de basis uit **DEPLOY-AWS.md** (Docker installeren, project naar
> `~/appportal`, `cp .env.production .env` + secrets genereren). Kom dan hier
> terug. `OMV_UPSTREAM` staat in `.env.production` al goed.

---

## 1. DNS (one.com)

| Actie | Record |
|---|---|
| **UIT** | `AAAA *.globaal.be` (de IPv6-val) |
| **UIT** | standaard `A *.globaal.be` |
| **Toevoegen** (Personal DNS) | `A` · `*.globaal.be` · `54.80.98.233` |
| Laten staan | `data`, `n8n`, en e-mail (`MX`, `TXT`, `SRV`) |

Optioneel opschonen (niet gebruikt): het `ha-customgpt`-record + de
`cloudflared`-tunnel mogen weg — minder ruis. Niet nodig voor de cutover.

## 2. OMV: SSO-shim + nette service

```bash
cd ~/appportal
# a) de shim naast de echte app zetten:
cp omv-demo/sso_auth.py /home/ubuntu/omv_pipeline/v1/sso_auth.py
```
```bash
# b) twee regels toevoegen onderaan v1/app.py, vóór  if __name__ == '__main__':
nano /home/ubuntu/omv_pipeline/v1/app.py
```
Voeg toe (net boven de `if __name__ == '__main__':`-regel):
```python
from sso_auth import init_sso
init_sso(app)
```
```bash
# c) de oude handmatige screen-sessie stoppen (anders twee processen op :5000):
screen -S data -X quit

# d) OMV als systemd-service installeren (verifieer eerst de 2 paden erin!):
sudo cp ~/appportal/vm/omv.service /etc/systemd/system/omv.service
sudo nano /etc/systemd/system/omv.service     # WorkingDirectory + python-pad checken
sudo systemctl daemon-reload
sudo systemctl enable --now omv
systemctl status omv        # moet 'active (running)' tonen
sudo ss -tlnp | grep ':5000'  # moet nu luisteren (0.0.0.0:5000)
```

## 3. n8n aan AppPortal's netwerk koppelen

(Na de eerste `docker compose up` bestaat het netwerk; doe deze stap dan.)
```bash
docker network connect appportal_appnet n8n-n8n-1
```

## 4. n8n nginx-blok toevoegen (gewone doorsturing — n8n houdt eigen login)

```bash
cat > ~/appportal/nginx/templates/40-n8n.conf.template <<'EOF'
server {
    listen 443 ssl;
    http2 on;
    server_name n8n.${BASE_DOMAIN};
    include /etc/nginx/snippets/ssl.conf;
    resolver 127.0.0.11 valid=30s;
    location / {
        set $n8n_upstream http://n8n-n8n-1:5678;
        proxy_pass $n8n_upstream;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
    }
}
EOF
```
(De `omv.globaal.be`-tegel zit al in AppPortal en wijst via `OMV_UPSTREAM` naar
de echte app op `:5000` — geen extra blok nodig.)

## 5. AppPortal bouwen

```bash
cd ~/appportal
docker compose build
```

## 6. De cutover (de wissel — korte onderbreking)

```bash
# Host-nginx vrijgeven:
sudo systemctl stop nginx && sudo systemctl disable nginx

# AppPortal pakt 80/443 (start nog met zelf-ondertekend cert):
docker compose up -d
docker network connect appportal_appnet n8n-n8n-1   # als nog niet gedaan
docker compose ps          # alles (healthy)?
```
**Testen** (browser): `https://portal.globaal.be` (login + tegels),
`https://omv.globaal.be` (OMV opent, ingelogd via SSO, geen tweede login),
`https://n8n.globaal.be` (n8n werkt, eigen login).

**ROLLBACK indien nodig:**
```bash
docker compose down
sudo systemctl enable --now nginx     # oude situatie terug
```

## 7. Authentik configureren + echte certificaten

Volg **DEPLOY-AWS.md stap 7** (Let's Encrypt webroot — voeg `-d omv.globaal.be`,
`-d n8n.globaal.be`, `-d data.globaal.be` toe aan het certbot-commando) en
**stap 8** (Authentik-scripts + gebruikers). De OMV-tegel registreren:
```bash
sh scripts/ak-exec.sh scripts/add-omv-app.py
```

## 8. Verificatie

- `https://portal.globaal.be` → tegels, incl. **OMV Pipeline**.
- Klik OMV → het **echte** dashboard opent, ingelogd via SSO, live logs werken
  (WebSocket via SocketIO).
- `https://n8n.globaal.be` → n8n werkt (eigen login).
- `docker ps` → alleen nginx exposeert 80/443; `systemctl status omv` → running.

## Later (optioneel)
- n8n ook achter SSO brengen (zoals OMV: forward-auth + een shim voor n8n's auth).
- `data.globaal.be` → 301 redirect naar `omv.globaal.be`, of laten vervallen.
- `cloudflared` + `ha-customgpt` opruimen.
