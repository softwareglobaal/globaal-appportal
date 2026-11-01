FROM python:3.11-slim

# De dagen zijn Belgische dagen.
ENV TZ=Europe/Brussels

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Grendel: de pagina's lezen een echt dagbestand van De Dagbundelaar (proef/), privé blijft privé en onbekend blijft
# een vraagteken. Faalt dit, dan faalt de build en blijft de vorige container draaien. Zie test_dagboek.py.
RUN python3 test_dagboek.py
# T-0120 FOTO-5: de foto's per project tonen alleen werk; privé en mensen alleen geteld. Zie test_fotos.py.
RUN python3 test_fotos.py

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-3150} --workers 2 --timeout 30 app:app"]
