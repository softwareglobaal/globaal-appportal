FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=3017
EXPOSE 3017
# Threads omdat een IMAP-aanroep wacht op de mailserver; workers blijven laag,
# de VM heeft maar twee vCPU's.
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 --timeout 120 --access-logfile - app:app"]
