FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src /app/src

ENV PYTHONPATH=/app/src
ENV AKS_DEMO_SERVICE_NAME=order-service

EXPOSE 8000

CMD ["uvicorn", "order_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
