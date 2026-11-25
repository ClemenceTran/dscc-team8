# Contract between the pipeline (Functions) and the ML API

Written by Nishi (part 1) for Lavish (dispatcher, worker, dashboard).

## Input files dropped in `input/`

* Format: **CSV**, UTF-8, comma separator, header line, extension `.csv`, at most 1,000 rows (suggested max size 1 MB).
* Columns (order free, extra columns ignored): `customerID` (optional) + the 19 features:
  `gender, SeniorCitizen, Partner, Dependents, tenure, PhoneService, MultipleLines, InternetService, OnlineSecurity, OnlineBackup, DeviceProtection, TechSupport, StreamingTV, StreamingMovies, Contract, PaperlessBilling, PaymentMethod, MonthlyCharges, TotalCharges`
* Allowed values: see `api/app/schemas.py` (for example `Contract` in `Month-to-month | One year | Two year`).
  `TotalCharges` may be blank for a new customer: send `0`.

Suggested checks in the **dispatcher** (otherwise copy to `rejected/` with the reason): extension `.csv`, size, header contains the 19 columns, at least 1 data row.
Values are checked by the API (HTTP 422), not by the dispatcher.

## Call made by the worker

`POST {API_URL}/predict` with header `content-type: application/json` and body:
```json
{"customers": [ {"customerID": "7590-VHVEG", "gender": "Female", "SeniorCitizen": 0, "...": "...", "MonthlyCharges": 29.85, "TotalCharges": 29.85} ]}
```
(numbers as numbers: `SeniorCitizen`, `tenure` integers; `MonthlyCharges`, `TotalCharges` floats). Example: `samples/predict_request.json`.

Answers:
* **200**: `{"model_version", "api_version", "count", "churn_count", "latency_ms", "predictions": [{"customerID", "churn_probability", "churn", "risk"}]}`
  Suggested Cosmos DB document per file: `id` = blob name + ETag, `fileName`, `timestamp`, `count`, `churn_count`, average or max probability, `model_version`, `latency_ms`, `duration_ms`.
* **422**: invalid values. Retrying will not help: either copy the file to `rejected/` directly, or let the message fail 5 times and go to `inference-requests-poison` (good for the poison demo).
* **503 / timeout**: API cold start (scaled to 0) or model not loaded. Retry (the queue retries up to 5 times). Use a timeout of about 30 s for the first call after scale to zero.

## Demo files in `samples/`

| File | Expected path through the pipeline |
|---|---|
| `customers_valid.csv` | 20 customers, result in `output/` and in the dashboard |
| `not_a_csv.txt` | wrong extension, rejected by the dispatcher (`rejected/`) |
| `customers_missing_columns.csv` | header without `Contract` and `tenure`, rejected by the dispatcher |
| `customers_bad_values.csv` | valid header, but `Contract = Weekly` and `tenure = -4`: the API answers 422, which gives the poison message scenario |
