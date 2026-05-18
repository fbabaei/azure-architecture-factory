FROM python:3.12-slim
WORKDIR /app
COPY ../shared/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY ../shared /app/agent_templates/shared
COPY . /app/agent_templates/ops
ENV PYTHONPATH=/app
ENV PORT=8092
EXPOSE 8092
CMD ["python", "-m", "agent_templates.ops.main"]
