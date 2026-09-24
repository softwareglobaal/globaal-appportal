FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Grendel: de uitrol weigert als de werfbezoek-rijen weer dubbel kunnen worden na een verhuis van de projectmap,
# als de schrijver de dubbel kan lezen, of als de opruiming iets wist wat nog nergens anders staat. Faalt dit,
# dan faalt `docker compose build` en blijft de vorige container draaien. Zie test_werfbezoek.py.
RUN python3 test_werfbezoek.py

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-3022} --workers 2 --timeout 900 app:app"]
