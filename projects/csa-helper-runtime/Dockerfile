# syntax=docker/dockerfile:1.6
# Stage 1 — vendor the csa-helper repo so we have agent-framework + agents +
# manifests + copilot-studio at the layout build_team.py expects
# (REPO = parent of agent-framework/).
FROM alpine/git:2.43.0 AS vendor
ARG CSA_HELPER_REF=main
WORKDIR /vendor
RUN git clone --depth 1 --branch ${CSA_HELPER_REF} https://github.com/fbabaei/csa-helper.git

# Stage 2 — runtime image.
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    CSA_HELPER_ROOT=/app/csa_helper

WORKDIR /app

# Install Python deps first for layer caching.
COPY src/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the FastAPI wrapper.
COPY src/api /app/api

# Copy only the folders build_team.py expects, preserving relative layout.
COPY --from=vendor /vendor/csa-helper/agent-framework /app/csa_helper/agent-framework
COPY --from=vendor /vendor/csa-helper/agents          /app/csa_helper/agents
COPY --from=vendor /vendor/csa-helper/manifests       /app/csa_helper/manifests
COPY --from=vendor /vendor/csa-helper/copilot-studio  /app/csa_helper/copilot-studio

# Make `agent_framework` importable as a package without modifying upstream code.
RUN echo "" > /app/csa_helper/agent-framework/__init__.py \
 && ln -s /app/csa_helper/agent-framework /app/csa_helper/agent_framework

# Drop privileges.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=3).status==200 else 1)"

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
