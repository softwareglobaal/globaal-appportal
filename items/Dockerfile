FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Eén worker + meerdere threads: de taxatie draait in een achtergrond-thread met
# in-memory voortgang, dus alles moet in hetzelfde proces zitten. Ruime timeout
# want een marktprijs-taxatie kan enkele minuten duren.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-3015} --workers 1 --threads 8 --timeout 600 app:app"]
