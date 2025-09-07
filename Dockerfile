FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY weaver_ai ./weaver_ai
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip && /opt/venv/bin/pip install -e .[dev]

FROM python:3.12-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends tini && rm -rf /var/lib/apt/lists/*
RUN useradd -u 10001 -m appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY weaver_ai ./weaver_ai
ENV PATH="/opt/venv/bin:$PATH"
EXPOSE 8000
USER appuser:appuser
VOLUME ["/tmp"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health', timeout=2)"
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["uvicorn","weaver_ai.main:app","--host","0.0.0.0","--port","8000","--workers","1"]
