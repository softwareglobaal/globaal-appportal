# Claude Code Manager: de brug op de VM

`manager.globaal.be` is een MCP-server waarmee Claude in de app (ook in live
mode) Claude Code-sessies op Shaniels laptop aanstuurt. De server zelf draait
op de laptop (lokale repo `Claude\claude-manager`), niet op de VM. Deze map
bevat alleen het stuk op de VM dat het verkeer doorgeeft.

```
claude.ai -> nginx (87-claude-manager.conf.template)
          -> 172.17.0.1:8120   systemd-socket-proxyd (deze map)
          -> 127.0.0.1:8121    ingang van de SSH-tunnel, alleen loopback
          -> laptop 127.0.0.1:8120  server.py
```

Waarom een brug: een SSH-tunnel (`-R`) luistert op de VM alleen op de
loopback, en de nginx-container kan daar niet bij. `GatewayPorts` aanzetten in
sshd zou elke tunnel op elk adres laten luisteren; deze socket-proxy opent
alleen dit ene adres.

## De tunnelsleutel

De laptop verbindt met een eigen sleutel zonder passphrase (niet de
Pageant-sleutel, zodat de tunnel ook zonder Pageant opkomt). In
`~/.ssh/authorized_keys` staat die sleutel dichtgetimmerd:

```
restrict,port-forwarding,permitlisten="127.0.0.1:8121",command="/bin/false" ssh-ed25519 AAAA... claude-manager-tunnel
```

Met die sleutel kan je geen shell openen en alleen op 127.0.0.1:8121 een
tunnel laten luisteren. Weg ermee = de regel verwijderen.

## Installeren

```
sudo cp ~/appportal/claude-manager-brug/claude-manager-brug.{socket,service} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now claude-manager-brug.socket
sudo ufw allow from 172.16.0.0/12 to any port 8120 proto tcp
```

Toegang in Authentik: `sh scripts/ak-exec.sh scripts/add-claude-manager.py`
(groep `claude-manager`, alleen shaniel). De client-gegevens komen in
`/tmp/claude-manager-client.env` in de container authentik-server en gaan van
daar naar `manager.env` op de laptop, niet via de chat.

Laptop uit of tunnel weg: `/gezond` geeft 502. Dat is verwacht.
