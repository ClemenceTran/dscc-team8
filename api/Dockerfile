# syntax=docker/dockerfile:1
# Churn inference API. Build from the REPOSITORY ROOT (the image needs model/ and api/):
#   docker build -f api/Dockerfile -t churn-api:1.0.0 --build-arg GIT_SHA=$(git rev-parse --short HEAD) .

# ---------- stage 1: build the virtual environment with all dependencies ----------
FROM python:3.12-slim AS builder
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY api/requirements.txt .
RUN python -m venv /opt/venv \
 && /opt/venv/bin/pip install -r requirements.txt \
 && find /opt/venv -name "__pycache__" -type d -prune -exec rm -rf {} + \
 && find /opt/venv -path "*/tests/*" -name "*.py" -delete

# ---------- stage 2: small runtime image, non-root ----------
FROM python:3.12-slim
ARG GIT_SHA=unknown
ARG API_VERSION=1.0.0
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MODEL_PATH=/app/model/model-1.0.0.joblib \
    API_VERSION=${API_VERSION} \
    GIT_SHA=${GIT_SHA}
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY api/app ./app
COPY model/model-1.0.0.joblib ./model/model-1.0.0.joblib
USER appuser
EXPOSE 8000
# python:slim has no curl, so the health check uses the Python standard library
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
