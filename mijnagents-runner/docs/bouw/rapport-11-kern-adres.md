NIET AKKOORD.

- Hoog: de uitrol stopt niet als KBO of kern onvolledig blijft; het script eindigt met status 0. Bewijs: `bouw/kern_adres.py:113-115`, `docs/bouw/uitrol.sh:28`.
- Hoog: een gedeelde adresrij met lege `straat` maar bestaande andere velden kan worden overschreven. Bewijs: `bouw/kern_adres.py:98-103`.
- Laag, akkoord: aanhalingstekens worden verdubbeld en `_psql` gebruikt geen shell. Bewijs: `bouw/kern_adres.py:28-29`, `koppelingen/organisatie.py:67`.
- Laag, akkoord: `zetel()` controleert exact de cijfers en weigert afwijkende adresvormen; twee SQL-opdrachten zijn terecht wegens PostgreSQL-zichtbaarheid. Bewijs: `bouw/kern_adres.py:43-55,93-103`, [PostgreSQL](https://www.postgresql.org/docs/14/queries-with.html).
- Laag: niet in gewone uitvoer, maar wel volledig in `kern.audit`. Bewijs: `bouw/kern_adres.py:104-115`, `db/migrations/025-adres-entiteit.sql:61-62`, `db/migrations/023-audit-en-eigenaarschap.sql:55-64`. Tests: 232 goed, 0 fout; niets gewijzigd of gepusht.