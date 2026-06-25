FROM python:3.11-slim

# git is needed by ShellDeployer to fetch app repos on the VM.
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
# Single worker: onboarding jobs are serialized through one in-process queue,
# so the service must run as exactly one process (one shared-account mitigation).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--access-logfile", "-", "app:app"]
