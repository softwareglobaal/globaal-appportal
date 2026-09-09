FROM python:3.11-slim

# De dagindeling rekent met Belgische dagranden en zomertijd; zonder deze
# zone denkt de container dat alles in UTC gebeurt.
ENV TZ=Europe/Brussels

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-3031} --workers 2 --timeout 60 app:app"]
