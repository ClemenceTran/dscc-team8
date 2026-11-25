"""Churn inference API (FastAPI) of the team 8 event-driven pipeline.

Endpoints: GET /health, GET /version, POST /predict, GET /metrics.
Configuration through environment variables only:
  MODEL_PATH                              path of the joblib model bundle
  API_VERSION                             semantic version of the API (default 1.0.0)
  GIT_SHA                                 commit of the image (set by the CI build)
  APPLICATIONINSIGHTS_CONNECTION_STRING   enables Azure Monitor OpenTelemetry (optional)
"""
from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from .schemas import PredictRequest, PredictResponse

API_VERSION = os.getenv("API_VERSION", "1.0.0")
GIT_SHA = os.getenv("GIT_SHA", "local")
DEFAULT_MODEL = Path(__file__).resolve().parents[2] / "model" / "model-1.0.0.joblib"
MODEL_PATH = Path(os.getenv("MODEL_PATH", str(DEFAULT_MODEL)))
HIGH_RISK, MEDIUM_RISK = 0.7, 0.4

log = logging.getLogger("churn-api")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# --- Telemetry: Azure Monitor OpenTelemetry distro, only when a connection string is given
TELEMETRY = bool(os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"))
if TELEMETRY:
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(logger_name="churn-api")
from opentelemetry import metrics as otel_metrics  # noqa: E402  (after configure_azure_monitor)

meter = otel_metrics.get_meter("churn-api")
m_inferences = meter.create_counter("churn_inferences", unit="1",
                                    description="Number of customers scored")
m_requests = meter.create_counter("churn_predict_requests", unit="1",
                                  description="Calls to /predict, by status")
m_latency = meter.create_histogram("churn_model_latency_ms", unit="ms",
                                   description="Model inference time per /predict call")


class Stats:
    """In-memory counters exposed by GET /metrics (per replica)."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.calls = self.errors = self.customers = 0
        self.latencies: deque[float] = deque(maxlen=1000)
        self.started = time.time()

    def ok(self, n: int, ms: float) -> None:
        with self.lock:
            self.calls += 1
            self.customers += n
            self.latencies.append(ms)

    def error(self) -> None:
        with self.lock:
            self.calls += 1
            self.errors += 1

    def snapshot(self) -> dict:
        with self.lock:
            lat = sorted(self.latencies)
            avg = sum(lat) / len(lat) if lat else 0.0
            p95 = lat[int(0.95 * (len(lat) - 1))] if lat else 0.0
            return {"calls": self.calls, "errors": self.errors,
                    "customers_scored": self.customers,
                    "avg_latency_ms": round(avg, 2), "p95_latency_ms": round(p95, 2),
                    "uptime_s": round(time.time() - self.started, 1)}


STATE: dict = {"bundle": None, "load_ms": None, "error": None}
STATS = Stats()


def load_model() -> None:
    t0 = time.perf_counter()
    try:
        STATE["bundle"] = joblib.load(MODEL_PATH)
        STATE["error"] = None
    except Exception as exc:                      # the API stays up and /health reports it
        STATE["bundle"], STATE["error"] = None, f"{type(exc).__name__}: {exc}"
        log.exception("model loading failed from %s", MODEL_PATH)
    STATE["load_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    log.info("model %s loaded in %s ms", MODEL_PATH.name, STATE["load_ms"])


@asynccontextmanager
async def lifespan(_: FastAPI):
    load_model()
    yield


app = FastAPI(title="Churn inference API", version=API_VERSION, lifespan=lifespan)


@app.middleware("http")
async def count_predict_errors(request: Request, call_next):
    response = await call_next(request)
    if request.url.path == "/predict" and response.status_code >= 400:
        STATS.error()
        m_requests.add(1, {"status": str(response.status_code)})
    return response


@app.get("/health")
def health():
    ok = STATE["bundle"] is not None
    body = {"status": "ok" if ok else "error", "model_loaded": ok,
            "model_load_time_ms": STATE["load_ms"]}
    if not ok:
        body["detail"] = STATE["error"]
    return JSONResponse(body, status_code=200 if ok else 503)


@app.get("/version")
def version():
    b = STATE["bundle"] or {}
    return {"api_version": API_VERSION, "model_version": b.get("model_version"),
            "algorithm": b.get("algorithm"), "trained_at": b.get("trained_at"),
            "git_sha": GIT_SHA}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    bundle = STATE["bundle"]
    if bundle is None:
        raise HTTPException(status_code=503, detail="model not loaded")
    t0 = time.perf_counter()
    rows = [c.model_dump() for c in req.customers]
    X = pd.DataFrame(rows)[bundle["features"]]
    proba = bundle["pipeline"].predict_proba(X)[:, 1]
    ms = (time.perf_counter() - t0) * 1000
    threshold = bundle.get("threshold", 0.5)
    preds = [{"customerID": r["customerID"], "churn_probability": round(float(p), 4),
              "churn": bool(p >= threshold),
              "risk": "high" if p >= HIGH_RISK else "medium" if p >= MEDIUM_RISK else "low"}
             for r, p in zip(rows, proba, strict=True)]
    STATS.ok(len(rows), ms)
    m_inferences.add(len(rows), {"model_version": bundle["model_version"]})
    m_latency.record(ms, {"model_version": bundle["model_version"]})
    m_requests.add(1, {"status": "200"})
    return {"model_version": bundle["model_version"], "api_version": API_VERSION,
            "count": len(preds), "churn_count": sum(p["churn"] for p in preds),
            "latency_ms": round(ms, 2), "predictions": preds}


@app.get("/metrics")
def get_metrics():
    return {**STATS.snapshot(), "model_version": (STATE["bundle"] or {}).get("model_version"),
            "telemetry_enabled": TELEMETRY}
