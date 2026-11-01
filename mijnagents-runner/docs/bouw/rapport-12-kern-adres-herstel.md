AKKOORD.

- Hoog 1 hersteld: foutstatus bij onvolledige kern en uitrol stopt vóór de eerste ronde (`bouw/kern_adres.py:117-119`, `docs/bouw/uitrol.sh:9,28,62-63`).
- Hoog 2 hersteld: adresupdate vereist vier lege velden; koppeling gebeurt alleen bij leeg `adres_id` (`bouw/kern_adres.py:99-105`).
- Laag audit aanvaardbaar: normale volledige audit van een openbaar KBO-adres (`db/migrations/025-adres-entiteit.sql:60-62`, `db/migrations/023-audit-en-eigenaarschap.sql:55-58`).
- Test: 234 goed, 0 fout, status 0. Niets gewijzigd of gepusht.