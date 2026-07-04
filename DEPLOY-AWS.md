# AppPortal deployen naar de AWS-VM - domein: globaal.be

Een volledig uitgeschreven draaiboek. Je hoeft de blokken alleen van boven naar
beneden te kopiëren en uit te voeren. Het domein `globaal.be` is overal al
ingevuld. Vervang alleen nog `<VM-IP>` door het publieke IP-adres van je
server (dat krijg je in stap 1).

> **Twee machines, twee shells.** Commando's gemarkeerd met **(VM)** voer je uit
> in de SSH-sessie op de Ubuntu-server. Commando's met **(Windows)** in
> PowerShell op je eigen pc. Op de VM is er géén `wsl ...`-voorvoegsel -
> daar is `docker` rechtstreeks beschikbaar.

---

## 0. Wat je nodig hebt

- Een **AWS EC2-VM**, **Ubuntu 22.04 of 24.04**, minimaal type `t3.small`
  (~2 GB RAM; Authentik heeft dat nodig).
- Het domein **globaal.be**, waarvan je het **DNS kunt beheren** (records kunnen
  toevoegen bij je registrar/DNS-provider). Dit is nodig in stap 4 en 7.
- Toegang tot de VM via SSH.

---

## 1. AWS-VM klaarzetten

1. Start een Ubuntu-VM in de AWS-console. Noteer het **publieke IP-adres**
   (`<VM-IP>`).
2. Open in de **Security Group** (de firewall) inkomend verkeer:

   | Type | Poort | Bron | Waarvoor |
   |------|-------|------|----------|
   | SSH  | 22    | *jouw* IP | inloggen op de server |
   | HTTP | 80    | 0.0.0.0/0 | redirect + Let's Encrypt |
   | HTTPS| 443   | 0.0.0.0/0 | de applicaties |

3. **(Windows)** Log in op de VM:
   ```powershell
   ssh ubuntu@<VM-IP>
   ```

---

## 2. Docker + Docker Compose installeren  **(VM)**

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
docker version && docker compose version
```
Op Ubuntu start de Docker-daemon automatisch bij elke reboot - geen handmatig
starten nodig (anders dan lokaal in WSL).

---

## 3. Het project naar de VM kopiëren

Kies één methode.

**Methode A - rechtstreeks kopiëren met scp (aanrader nu).**
**(Windows)** - voer dit uit op je eigen pc; zorg dat `~/appportal` op de VM
nog niet bestaat:
```powershell
scp -r "C:\Users\shani\OneDrive - Unabo VOF\Mehdi Chegini's files - 000 AI opzet\21. Algemene Dashboard" ubuntu@<VM-IP>:~/appportal
```

**Methode B - via een privé git-repository (netter op termijn).** **(VM)**:
```bash
git clone <jouw-repo-url> ~/appportal
```

**(VM)** Ga in de map staan en ruim lokale runtime-resten op die met scp zijn
meegekomen (op een verse server zijn deze leeg of afwezig - dit commando kan
geen kwaad):
```bash
cd ~/appportal
rm -rf certs/* logs/portal/* authentik/data
mkdir -p certbot-webroot certs logs/portal
```
Vanaf nu draai je alle **(VM)**-commando's vanuit `~/appportal`.

---

## 4. DNS instellen

Voeg bij je DNS-provider deze twee records toe (één wildcard dekt alle
subdomeinen in één keer):

| Type | Naam | Waarde |
|------|------|--------|
| A    | `*.globaal.be` | `<VM-IP>` |
| A    | `globaal.be`   | `<VM-IP>` |

Daarmee wijzen `portal.globaal.be`, `auth.globaal.be`, `omv.globaal.be`,
`factorydocs.globaal.be`, `inventory.globaal.be`, `finance.globaal.be` en
`maintenance.globaal.be` allemaal naar je server.

**(VM)** Controleer dat het werkt (moet `<VM-IP>` teruggeven):
```bash
getent hosts portal.globaal.be
```
Wacht zo nodig een paar minuten tot DNS actief is voordat je verder gaat -
stap 7 (certificaten) heeft werkende DNS nodig.

---

## 5. `.env` instellen  **(VM)**

Het productie-`.env` met `BASE_DOMAIN=globaal.be` staat al klaar in het project
(`.env.production`). Kopieer het en vul de secrets automatisch in:

```bash
cp .env.production .env

# Genereer en plaats verse secrets in één keer:
for k in PG_PASS AUTHENTIK_SECRET_KEY AUTHENTIK_BOOTSTRAP_PASSWORD PORTAL_SECRET_KEY; do
  sed -i "s|^$k=.*|$k=$(openssl rand -hex 32)|" .env
done

# Noteer het admin-wachtwoord voor Authentik (gebruiker akadmin):
grep AUTHENTIK_BOOTSTRAP_PASSWORD .env
```
Bewaar dat laatste wachtwoord; je hebt het nodig in stap 8. `BASE_DOMAIN`,
`AUTHENTIK_BOOTSTRAP_EMAIL` en `CERTGEN_DISABLE=0` staan al goed ingevuld.

---

## 6. Eerste start (zelf-ondertekend, om te testen)  **(VM)**

```bash
docker compose up -d --build      # bouwt de portal-, stub- en OMV-images op de VM
docker compose ps          # wacht tot authentik-server (healthy) toont (~2 min)
docker ps                  # check: alleen nginx publiceert 0.0.0.0:80 en :443
```
De stack draait nu met een tijdelijk zelf-ondertekend certificaat. Je browser
geeft nog een waarschuwing - die lossen we in stap 7 definitief op.

---

## 7. Echte certificaten met Let's Encrypt (gratis, auto-vernieuwend)  **(VM)**

We gebruiken de **webroot-methode**. Die werkt bij élke DNS-provider (geen
plugins nodig), vernieuwt automatisch en veroorzaakt geen downtime. nginx is
al voorbereid: het ACME-pad wordt over HTTP geserveerd, de rest gaat naar HTTPS.

### 7a. certbot installeren
```bash
sudo apt install -y certbot
```

### 7b. Het certificaat aanvragen (alle subdomeinen in één cert)
```bash
sudo certbot certonly --webroot -w ~/appportal/certbot-webroot \
  --non-interactive --agree-tos -m mch@h-architects.be \
  -d portal.globaal.be \
  -d auth.globaal.be \
  -d omv.globaal.be \
  -d factorydocs.globaal.be \
  -d inventory.globaal.be \
  -d finance.globaal.be \
  -d maintenance.globaal.be
```
Het certificaat komt in `/etc/letsencrypt/live/portal.globaal.be/`.

### 7c. Het certificaat in het project zetten
```bash
sudo cp /etc/letsencrypt/live/portal.globaal.be/fullchain.pem ~/appportal/certs/fullchain.pem
sudo cp /etc/letsencrypt/live/portal.globaal.be/privkey.pem  ~/appportal/certs/privkey.pem
sudo chown $USER:$USER ~/appportal/certs/fullchain.pem ~/appportal/certs/privkey.pem
```

### 7d. Productie-modus aanzetten
Twee aanpassingen, allebei met één commando:
```bash
# 1) Het cert-script jouw echte certs laten met rust laten:
sed -i 's|^CERTGEN_DISABLE=.*|CERTGEN_DISABLE=1|' .env

# 2) De portal de publieke CA's laten vertrouwen i.p.v. de lokale dev-CA:
sed -i 's|^\( *\)REQUESTS_CA_BUNDLE:|\1# REQUESTS_CA_BUNDLE:|' docker-compose.yml

# Herstart met de echte certificaten:
docker compose up -d
```
`https://portal.globaal.be` toont nu een geldig slotje, zonder waarschuwing.

### 7e. Automatisch vernieuwen instellen
certbot installeert zelf een timer die certificaten tijdig vernieuwt. We laten
de vernieuwde versie automatisch in het project kopiëren en nginx herladen:
```bash
sudo tee /etc/letsencrypt/renewal-hooks/deploy/appportal.sh >/dev/null <<'EOF'
#!/bin/sh
cp /etc/letsencrypt/live/portal.globaal.be/fullchain.pem /home/ubuntu/appportal/certs/fullchain.pem
cp /etc/letsencrypt/live/portal.globaal.be/privkey.pem  /home/ubuntu/appportal/certs/privkey.pem
cd /home/ubuntu/appportal && docker compose exec -T nginx nginx -s reload
EOF
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/appportal.sh
sudo certbot renew --dry-run      # test: moet zonder fouten eindigen
```

---

## 8. Authentik eenmalig configureren  **(VM)**

De applicaties (groepen, OIDC, de 4 stub-apps + OMV, TOTP) zet je in één keer
op met de scripts. Deze draaien ín de VM en hebben verder geen DNS nodig.

```bash
# Groepen, portal-OIDC-provider, 4 apps, TOTP-verplichting, 8u-sessies:
sh scripts/configure-authentik.sh
```
Dit script **print de `OIDC_CLIENT_ID` en `OIDC_CLIENT_SECRET`**. Zet die in
`.env` en herstart de portal:
```bash
nano .env          # vul OIDC_CLIENT_ID en OIDC_CLIENT_SECRET in
docker compose up -d portal
```
Registreer de OMV-tegel (apart script, zodat het de rest niet aanraakt):
```bash
sh scripts/ak-exec.sh scripts/add-omv-app.py
```

**Echte gebruikers aanmaken.** Open `https://auth.globaal.be`, log in als
`akadmin` met het wachtwoord uit stap 5, en maak per medewerker een gebruiker +
groep (`admin` of `manager`) aan. Zie `README.md` §2.2. Elke gebruiker stelt bij
de eerste login zelf TOTP-2FA in.

> De demo-gebruikers (`testadmin`/`testmanager`) bestaan niet op deze verse
> server - die waren alleen lokaal. Op productie staat TOTP gewoon aan.

---

## 9. Verificatie  **(VM + browser)**

```bash
docker compose ps          # alles (healthy)
docker ps                  # alleen nginx exposeert 80/443
```
In de browser (`https://portal.globaal.be`):
1. Login bij Authentik → TOTP → je landt op de portal met de tegels.
2. Klik een tegel → de app opent zonder tweede login (SSO).
3. Klik **OMV Pipeline** → het OMV-dashboard opent, automatisch ingelogd.
4. Auth-gebeurtenissen staan in `logs/portal/portal.log`.

---

## 10. Onderhoud  **(VM)**

- **Logs:** `docker compose logs -f portal`
- **Herstarten:** `docker compose up -d` (of `docker compose restart <service>`)
- **Updaten:** pas de image-tag in `docker-compose.yml` aan, dan
  `docker compose pull && docker compose up -d`
- **Back-up** (het belangrijkst - bevat alle gebruikers, groepen, 2FA):
  ```bash
  docker run --rm -v appportal_postgres-data:/data -v $PWD:/backup alpine \
    tar czf /backup/postgres-backup-$(date +%F).tar.gz -C /data .
  ```
  Kopieer dat bestand naar een veilige plek.
- **Stoppen** (volumes blijven behouden): `docker compose down`

---

## Bijlage A - een extra app toevoegen op productie

Zie `README.md` §3. Kort: service in `docker-compose.yml`, server-blok in
`nginx/templates/30-apps.conf.template`, entry in `apps.yaml`, en de
Authentik-provider (kopieer `scripts/add-omv-app.py` als sjabloon). Voor het
nieuwe subdomein vraag je het certificaat opnieuw aan met een extra `-d`-regel
in het commando van stap 7b (en draai je daarna 7c).

## Bijlage B - als iets niet werkt

- **Certbot faalt bij stap 7b** → DNS wijst nog niet (test met
  `getent hosts portal.globaal.be`) of poort 80 staat niet open in de Security
  Group.
- **Browser: "untrusted certificate"** → je hebt stap 7c/7d niet (volledig)
  gedaan, of nginx niet herstart (`docker compose up -d`).
- **Portal: 500 bij inloggen** → `OIDC_CLIENT_ID`/`SECRET` niet of verkeerd in
  `.env` (stap 8), of portal niet herstart.
- **`docker compose` zegt "permission denied"** → log uit en weer in op de VM
  (de docker-groep uit stap 2 wordt pas dan actief).
