# Churn inference API (part 1, Nishi)

FastAPI (Python 3.12) serving `model/model-1.0.0.joblib`. Input validation with Pydantic: any wrong value gives HTTP 422 before the model is called.

| Endpoint | Description |
|---|---|
| `GET /health` | `{"status": "ok", "model_loaded": true, "model_load_time_ms": ...}`; HTTP 503 if the model could not be loaded (used by the probes) |
| `GET /version` | API version, model version, algorithm, training date, **git commit of the image** (proves that a deployment updated production) |
| `POST /predict` | body `{"customers": [ {19 fields}, ... ]}` (1 to 1,000 customers); answers one probability per customer |
| `GET /metrics` | calls, errors, customers scored, average and p95 latency (per replica, since start) |

## Example

```bash
curl -s https://<api-fqdn>/predict -H "content-type: application/json" -d @samples/predict_request.json
```
```json
{"model_version":"1.0.0","api_version":"1.0.0","count":3,"churn_count":1,"latency_ms":6.1,
 "predictions":[{"customerID":"4376-KFVRS","churn_probability":0.1177,"churn":false,"risk":"low"},
                {"customerID":"2754-SDJRD","churn_probability":0.8519,"churn":true,"risk":"high"},
                {"customerID":"9917-KWRBE","churn_probability":0.1463,"churn":false,"risk":"low"}]}
```
`risk` is `high` from 0.7, `medium` from 0.4, otherwise `low`.

## Configuration (environment variables only)

| Variable | Default | Role |
|---|---|---|
| `MODEL_PATH` | `/app/model/model-1.0.0.joblib` | model bundle loaded at start-up |
| `API_VERSION` | `1.0.0` | returned by `/version` |
| `GIT_SHA` | set at build time by the CI | returned by `/version` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | not set | when set (Container Apps secret or setting, never in the repo), the Azure Monitor OpenTelemetry distro sends requests, logs and the custom metrics |

Custom metrics (OpenTelemetry, table `customMetrics` in Application Insights): `churn_inferences` (customers scored), `churn_model_latency_ms` (model time per call), `churn_predict_requests` (by HTTP status, gives the error rate).

## Tests and local run

```bash
pip install -r api/requirements-dev.txt
ruff check api model
pytest api/tests -q                       # 9 tests: health, version, success, 422 (bad value, negative number, missing field, missing body, empty list), metrics
cd api && uvicorn app.main:app --reload   # http://127.0.0.1:8000/docs
```

## Image

Multi-stage `api/Dockerfile` on `python:3.12-slim`, virtual environment copied from the build stage, non-root user (uid 10001), `HEALTHCHECK` on `/health`, built **from the repository root**:
```bash
docker build -f api/Dockerfile -t churn-api:1.0.0 --build-arg GIT_SHA=$(git rev-parse --short HEAD) .
```
The workflow `.github/workflows/ci.yml` lints, tests, builds, checks the size (< 500 MB), runs a smoke test in the container and pushes
`ghcr.io/clemencetran/dscc-team8/api:1.0.0`, `:<commit sha>` and `:<short sha>` to GitHub Container Registry (only the automatic `GITHUB_TOKEN`, no secret).

## Container Apps settings (for the deployment part)

0.25 vCPU / 0.5 GiB, min replicas 0, max replicas 2, target port 8000, external ingress, liveness and readiness probes on `GET /health` port 8000
(initial delay about 10 s: the model and the telemetry load in 1 to 2 s).
After the first push, the GHCR package must be made **public** (package settings) so that Container Apps can pull it without credentials.
