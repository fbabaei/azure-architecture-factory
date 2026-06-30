# Casewright API / worker container image.
# Build with: docker build -f src/Dockerfile -t <acr>.azurecr.io/casewright-api:latest .
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY casewright ./casewright

EXPOSE 8000

# API entrypoint. The worker image overrides the command with:
#   python -m casewright.worker.sb_worker
CMD ["uvicorn", "casewright.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
