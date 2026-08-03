# Publieke websites

Statische sites die op deze server draaien, één map per site. Nginx serveert ze
via `https://<naam>.web.globaal.be` (of een eigen domein, zie hieronder).

- Gebouwd en onderhouden door de agent `website-bouwer`.
- **Geen** Authentik-login ervoor: dit zijn openbare klantsites.
- Statisch: geen PHP, geen database. Snel, veilig en licht voor de server.

## Nieuwe site
1. Map aanmaken: `websites/<naam>/` met minstens `index.html`
2. Subdomein toevoegen aan `CERT_SUBDOMAINS` in `.env` (bv. `web`)
3. `docker compose exec nginx nginx -t && docker compose exec nginx nginx -s reload`

## Eigen domein (bv. h-invest.be)
1. DNS A-record van het domein naar deze server
2. `sudo certbot certonly --webroot -w /home/ubuntu/appportal/websites/<naam> -d <domein>`
3. Eigen server-block met dat certificaat toevoegen in `nginx/templates/60-websites.conf.template`
