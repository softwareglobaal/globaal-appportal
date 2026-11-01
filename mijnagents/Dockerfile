FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Grendel: de uitrol weigert als de werfbezoek-rijen weer dubbel kunnen worden na een verhuis van de projectmap,
# als de schrijver de dubbel kan lezen, of als de opruiming iets wist wat nog nergens anders staat. Faalt dit,
# dan faalt `docker compose build` en blijft de vorige container draaien. Zie test_werfbezoek.py.
RUN python3 test_werfbezoek.py
# Migratie, dubbele opdrachten, claims en revisies moeten ook in de productieimage slagen.
RUN python3 test_werfverwerking.py
# Grendel op het maildashboard (/mail): alleen beheer, belangrijk bovenaan, afgehandeld komt niet terug. Zie test_mail.py.
RUN python3 test_mail.py
RUN python3 test_naamstructuur.py
# Grendel op de nummerreservering (WP2b): een open of goedgekeurd dealtitel-voorstel houdt zijn nummer vast;
# akkoord op een betwist nummer wordt geweigerd. Zie test_nummerreservering.py.
RUN python3 test_nummerreservering.py
# BORD1: beheer leest de volledige voorstelinhoud en het verschil met de huidige werkwijze vóór een besluit.
RUN python3 test_voorstel_lezen.py
# Grendel op revisies (nacontrole Plaud v1.1): een opgepakt item met een nieuwe beoordeling wordt een zichtbare
# revisie met herstelstatus, nooit stil genegeerd. Zie test_klaarzet_revisie.py.
RUN python3 test_klaarzet_revisie.py
# Grendel op de gesprekkentabel (ontwerp regie-zoom v1.2, Z10, Z11, M6): de koppelkolommen sessie en dubbel_van komen
# er ook bij een oude databank en bij twee werkers tegelijk, een upsert zonder die sleutels wist geen koppeling, koppelen
# maakt nooit een rij en weigert wat niet telt, en een andere afzender overschrijft geen klaargezet item.
# Zie test_gesprekken_api.py. P9 leest terug met mijnagents-runner/koppelingen/bordstand.py, dat niet in deze image zit;
# de CI draait P9 in de hele repo (regie-grendels.yml), hier slaat de vlag hem zichtbaar over.
RUN P9_OVERSLAAN_IN_BORDIMAGE=1 python3 test_gesprekken_api.py
# Grendel op de weekpagina (/week): alleen beheer, een week die niet bestaat geeft 404, een lege of onleesbare week laat
# de pagina niet vallen, null wordt een vraagteken, en de jaargrens 2026-W53 naar 2027-W01 klopt. Zie test_week.py.
RUN python3 test_week.py
# Grendel op /bronnen: alleen beheer, groen/oranje/rood per bron en per dag, een kapot weekoverzicht laat de pagina staan.
# Zie test_bronnen.py.
RUN python3 test_bronnen.py
# Grendel op de FelixArchief-pagina (felix.<domein>, Shelton): alleen /felix op dat domein, alleen felix of beheer,
# geen dubbele aanvragen, opslaan alleen op een klik bij een klare zoektocht met projectnummer. Zie test_felix.py.
RUN python3 test_felix.py
# Grendel op het blok Laatst klaargezet op de pagina van een agent (De Mehdi-agent): alleen beheer, de nieuwste
# takenlijst en het nieuwste verslag, ruwe HTML en markdown-links uit een bron worden tekst. Zie test_klaargezet_pagina.py.
RUN python3 test_klaargezet_pagina.py
# Grendel op de groep Dagbundelaar: elke agent van het dagboek op één plek, niets dubbel. Zie test_dagbundelaar_groep.py.
RUN python3 test_dagbundelaar_groep.py

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-3022} --workers 2 --timeout 900 app:app"]
