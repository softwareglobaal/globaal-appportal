FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Foto-uploads vanaf de gsm kunnen traag binnenkomen, vandaar de ruimere timeout.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-3016} --workers 2 --threads 4 --timeout 120 app:app"]
