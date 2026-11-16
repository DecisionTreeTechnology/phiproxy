# LiteLLM proxy with the phiproxy guardrail baked in.
# Build from the repo root:  docker build -f deploy/Dockerfile -t phiproxy-gateway .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
RUN pip install "litellm[proxy]==1.109.1" "redis>=5"

COPY pyproject.toml README.md LICENSE NOTICE /src/phiproxy/
COPY src /src/phiproxy/src
RUN pip install /src/phiproxy && rm -rf /src/phiproxy

COPY deploy/litellm.config.yaml /app/config.yaml

RUN useradd --create-home --uid 10001 phiproxy
USER phiproxy

EXPOSE 4000
CMD ["litellm", "--config", "/app/config.yaml", "--port", "4000", "--host", "0.0.0.0"]
