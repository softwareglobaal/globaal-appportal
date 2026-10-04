FROM python:3.11-slim

# De dagindeling rekent met Belgische dagranden en zomertijd; zonder deze
# zone denkt de container dat alles in UTC gebeurt.
ENV TZ=Europe/Brussels

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Grendel: de uitrol weigert als de dagindeling een eerder gevonden fout
# terugbrengt. Faalt dit, dan faalt `docker compose build` en blijft de vorige,
# werkende container gewoon draaien. Zie test_dagindeling.py voor de gevallen.
RUN LOCATIE_DB=/tmp/test.db python3 test_dagindeling.py

# Tweede grendel: de ontleder van de trackerberichten, getoetst aan echte
# voorbeeldregels uit de handleiding van de fabrikant. Zie test_atrack.py.
RUN python3 test_atrack.py

# Derde grendel: de ontvanger zelf, inclusief de tweede bron in de database.
RUN LOCATIE_DB=/tmp/proef.db python3 test_atrack_server.py

# Opdracht v1.2 (04-10-2026): het bronbeleid (startgrens, toestel, dagranden, planning),
# de schema-upgrade, de projectherkenning, de dag van de auto en de export. Eigen
# proefgegevens; geen netwerk. Faalt er een, dan blijft de vorige container draaien.
RUN python3 test_bronbeleid.py
RUN python3 test_schema.py
RUN python3 test_herkenning.py
RUN python3 test_auto.py
RUN python3 test_export.py

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-3031} --workers 2 --timeout 60 app:app"]
