FROM python:3.12-slim

WORKDIR /app

COPY ../shared/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY ../shared /app/agent_templates/shared
COPY . /app/agent_templates/developer

ENV PYTHONPATH=/app
ENV PORT=8091

EXPOSE 8091

CMD ["python", "-m", "agent_templates.developer.main"]
