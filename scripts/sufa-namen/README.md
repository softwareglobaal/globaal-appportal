# Beperkt SSH-account voor Sufa (Namenlijst)

Sufa beheert alleen de Namenlijst-app (namen.globaal.be) en mag daarom niet
op de rest van de server. Zijn SSH-account kan uitsluitend vijf commando's
uitvoeren, hard vastgezet op de namen-container en het namen-schema:

    ssh sufa@54.80.98.233 status
    ssh sufa@54.80.98.233 logs [n]     # standaard 100, max 2000
    ssh sufa@54.80.98.233 restart
    ssh sufa@54.80.98.233 deploy       # draait deploy.sh direct
    ssh sufa@54.80.98.233 migrate      # migraties uit globaal-namen/db/migrations

## Hoe het slot werkt

- `authorized_keys` bevat `restrict,command="/usr/local/bin/sufa-shell"`:
  elke login draait alleen dat script; geen shell, geen sftp/scp, geen
  port-forwarding, geen agent-forwarding. Bewust NIET via een Match-blok in
  sshd_config (Include staat bovenaan de hoofdconfig, een Match-blok in
  sshd_config.d zou de rest van de config opslokken).
- `sufa-shell` whitelist-parset `SSH_ORIGINAL_COMMAND` en roept via sudo
  `namen-ctl` aan.
- `namen-ctl` (root) valideert argumenten en kent alleen de namen-container;
  `deploy` draait als ubuntu via runuser. Audit-log: /var/log/sufa-namen.log.
- `migrate` roept `namen-migrate` aan: pull van de namen-repo en daarna elke
  nieuwe `db/migrations/NNN-*.sql` daaruit, verbonden als de DB-rol
  `namen_migratie`. Die rol is alleen eigenaar van het schema `namen`
  (migratie 136); buiten dat schema weigert de database, niet het script.
  Het rolwachtwoord staat in `/etc/sufa-namen/pg.env` (root, 0600, regel
  `PGPASSWORD=...`) en gaat via `--env-file` de container in.
- sudoers: exact 1 regel, alleen `namen-ctl` als root, niets anders.
- User `sufa`: geen sudo-groep, geen docker-groep, home 750,
  `~/.ssh` root-eigendom zodat hij zijn eigen sleutelbestand niet kan wijzigen.
- Wachtwoord-login staat serverbreed uit; alleen deze ene sleutel werkt.

## Installatie (na wijziging of herinstallatie)

    sudo install -o root -g root -m 0755 namen-ctl /usr/local/sbin/namen-ctl
    sudo install -o root -g root -m 0755 namen-migrate /usr/local/sbin/namen-migrate
    sudo install -o root -g root -m 0755 sufa-shell /usr/local/bin/sufa-shell
    sudo visudo -cf sufa-namen-sudoers && \
      sudo install -o root -g root -m 0440 sufa-namen-sudoers /etc/sudoers.d/sufa-namen
    sudo useradd -m -s /bin/sh sufa   # als de user nog niet bestaat
    sudo mkdir -p /home/sufa/.ssh && sudo chown root:root /home/sufa/.ssh && sudo chmod 755 /home/sufa/.ssh
    sudo install -o root -g root -m 0644 authorized_keys /home/sufa/.ssh/authorized_keys

Eenmalig voor `migrate`: wachtwoord van de DB-rol zetten (nooit in git of
chat; genereren op de VM zelf):

    pw=$(openssl rand -base64 24)
    sudo install -d -o root -g root -m 0700 /etc/sufa-namen
    printf 'PGPASSWORD=%s\n' "$pw" | sudo tee /etc/sufa-namen/pg.env >/dev/null
    sudo chmod 600 /etc/sufa-namen/pg.env
    docker exec -i appportal-postgresql-1 psql -U authentik -d appportal \
      -c "ALTER ROLE namen_migratie PASSWORD '$pw'"
    unset pw

Nieuwe of extra sleutel voor Sufa: regel toevoegen in `authorized_keys`
(zelfde `restrict,command=`-prefix!) en opnieuw installeren.

Codewijzigingen aan de app zelf gaan NIET via dit account: push naar main
van `softwareglobaal/globaal-namen`; de cron deployt binnen 2 minuten.
