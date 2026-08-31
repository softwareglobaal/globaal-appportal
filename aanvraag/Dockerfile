FROM python:3.12-slim
WORKDIR /srv/app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
ENV PORT=3031
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} -w 2 --timeout 30 app:app"]
