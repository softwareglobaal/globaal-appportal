FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir "aiohttp>=3.9,<4"
COPY stem.py .
CMD ["python", "stem.py"]
