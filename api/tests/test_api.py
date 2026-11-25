"""API tests (pytest + FastAPI TestClient). Run from the repo root: pytest api/tests -q"""
import copy

import pytest
from fastapi.testclient import TestClient

from app.main import app

CUSTOMER = {
    "customerID": "7590-VHVEG", "gender": "Female", "SeniorCitizen": 0, "Partner": "Yes",
    "Dependents": "No", "tenure": 1, "PhoneService": "No", "MultipleLines": "No phone service",
    "InternetService": "DSL", "OnlineSecurity": "No", "OnlineBackup": "Yes",
    "DeviceProtection": "No", "TechSupport": "No", "StreamingTV": "No", "StreamingMovies": "No",
    "Contract": "Month-to-month", "PaperlessBilling": "Yes", "PaymentMethod": "Electronic check",
    "MonthlyCharges": 29.85, "TotalCharges": 29.85,
}
LOYAL = {**CUSTOMER, "customerID": "LOYAL-1", "tenure": 70, "Contract": "Two year",
         "PaymentMethod": "Credit card (automatic)", "TotalCharges": 2100.0}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:          # the context manager runs the lifespan (model loading)
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["model_loaded"] is True
    assert body["model_load_time_ms"] >= 0


def test_version(client):
    body = client.get("/version").json()
    assert body["model_version"] == "1.0.0"
    assert "api_version" in body and "git_sha" in body


def test_predict_success(client):
    r = client.post("/predict", json={"customers": [CUSTOMER, LOYAL]})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2 and body["model_version"] == "1.0.0"
    p_new, p_loyal = (p["churn_probability"] for p in body["predictions"])
    assert 0.0 <= p_loyal < p_new <= 1.0          # a new month-to-month customer is riskier
    assert body["predictions"][0]["customerID"] == "7590-VHVEG"
    assert body["latency_ms"] < 1000              # requirement: inference under 1 s on CPU


def test_predict_invalid_value_returns_422(client):
    bad = {**CUSTOMER, "Contract": "Weekly"}
    assert client.post("/predict", json={"customers": [bad]}).status_code == 422


def test_predict_negative_number_returns_422(client):
    bad = {**CUSTOMER, "tenure": -3}
    assert client.post("/predict", json={"customers": [bad]}).status_code == 422


def test_predict_missing_field_returns_422(client):
    bad = copy.deepcopy(CUSTOMER)
    del bad["Contract"]
    assert client.post("/predict", json={"customers": [bad]}).status_code == 422


def test_predict_missing_body_returns_422(client):
    assert client.post("/predict").status_code == 422


def test_predict_empty_list_returns_422(client):
    assert client.post("/predict", json={"customers": []}).status_code == 422


def test_metrics_count_calls(client):
    before = client.get("/metrics").json()
    client.post("/predict", json={"customers": [CUSTOMER]})
    client.post("/predict", json={"customers": [{**CUSTOMER, "gender": "X"}]})
    after = client.get("/metrics").json()
    assert after["calls"] == before["calls"] + 2
    assert after["errors"] == before["errors"] + 1
    assert after["customers_scored"] == before["customers_scored"] + 1
    assert after["avg_latency_ms"] > 0
