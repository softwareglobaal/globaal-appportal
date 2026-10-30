# SPIL (test)

Testomgeving van SPIL op de AppPortal-VM, op https://spil-test.globaal.be. Alleen
testgegevens: geen echte mail of dossiers, want deze VM staat niet in de EU en
SPIL hoort bij ingebruikname op een eigen EU-server (ADR-003).

- Code: repo `softwareglobaal/spil`, checkout in `~/spil-test/code`. Push naar main
  rolt binnen 2 minuten uit via `deploy.sh` (cron), log in `~/deploy-spil-test.log`.
- Containers: `compose.yml` hiernaast, project `spil-test`, los van de stack, met een
  eigen Postgres op een intern netwerk. De app luistert op 172.17.0.1:8470.
- Vhost: `nginx/templates/88-spil-test.conf.template`, zonder forward-auth; SPIL is
  zelf OIDC-client van authentik (`scripts/add-spil-test-app.py`).
- Geheimen: `~/spil-test/.env` en `~/spil-test/secrets/`, aangemaakt door `setup.sh`,
  nooit in git.

**Het compose-bestand staat hier en niet in de SPIL-repo.** Wie dat bestand bepaalt,
kan de Docker-socket of de schijf van de VM aankoppelen. Wijzigingen aan poorten,
volumes of limieten lopen dus via de beheerder.

## Toegang van Ashvand

Pushen naar de repo, en een beperkt SSH-account (`root/`, patroon `scripts/sufa-namen`):
alleen `status`, `logs`, `deploylog`, `restart` en `deploy`. Geen shell, geen sftp,
geen forwarding. Audit-log: `/var/log/spil-test-ashvand.log`.

Installeren, met zijn publieke sleutel:

    cd ~/appportal/spil-test/root
    sudo sh install.sh "ssh-ed25519 AAAA... ashvand-spil"

## Grens die niet dicht is

Tijdens `docker build` draait zijn Dockerfile op het standaard Docker-netwerk, dus
niet in de ingeperkte `uit`-omgeving van de draaiende app. Voor een test met
vertrouwde code acceptabel; niet voor productie.
