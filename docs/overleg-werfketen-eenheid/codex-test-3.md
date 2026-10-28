AKKOORD LIVE

Punt 4 is klaar voor uitrol. Ik heb de runner alleen lezend gecontroleerd en het gedrag zonder bestanden te schrijven nagebootst: HTTP 503 krijgt twee pogingen en eindigt met `NietBereikbaar (HTTP 503)`; HTTP 401 geeft direct een `HTTPError`. De gerichte pytest kon in deze alleen-lezen omgeving geen tijdelijke map aanmaken.

Commit `7db143c` staat op de werkbranch, nog niet op `main`. De livegang zelf is dus niet bevestigd.