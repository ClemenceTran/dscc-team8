"""Translate a customer CSV into the team's POST /predict request."""
import csv
import io
import math
from pathlib import PurePosixPath

MAX_BYTES = 256 * 1024
MAX_CUSTOMERS = 1000
YES_NO = {"Yes", "No"}
INTERNET_OPTION = YES_NO | {"No internet service"}
CATEGORIES = {
    "gender": {"Female", "Male"},
    "Partner": YES_NO,
    "Dependents": YES_NO,
    "PhoneService": YES_NO,
    "MultipleLines": YES_NO | {"No phone service"},
    "InternetService": {"DSL", "Fiber optic", "No"},
    "OnlineSecurity": INTERNET_OPTION,
    "OnlineBackup": INTERNET_OPTION,
    "DeviceProtection": INTERNET_OPTION,
    "TechSupport": INTERNET_OPTION,
    "StreamingTV": INTERNET_OPTION,
    "StreamingMovies": INTERNET_OPTION,
    "Contract": {"Month-to-month", "One year", "Two year"},
    "PaperlessBilling": YES_NO,
    "PaymentMethod": {"Electronic check", "Mailed check", "Bank transfer (automatic)",
                      "Credit card (automatic)"},
}
NUMBERS = {
    "SeniorCitizen": (int, 1),
    "tenure": (int, 120),
    "MonthlyCharges": (float, 1000),
    "TotalCharges": (float, 100000),
}
REQUIRED = (CATEGORIES.keys() | NUMBERS.keys()) - {"TotalCharges"}


class InvalidUpload(ValueError):
    """The upload does not match the agreed CSV format."""


def parse_customers(name, size, read):
    if PurePosixPath(name).suffix.lower() != ".csv":
        raise InvalidUpload("Expected a .csv file")
    if not 1 <= size <= MAX_BYTES:
        raise InvalidUpload("Expected 1 to 262144 bytes")
    try:
        text = read().decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidUpload("Expected UTF-8 CSV") from exc
    if "\0" in text:
        raise InvalidUpload("Unexpected binary character in CSV")
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    customers = []
    try:
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not REQUIRED.issubset(headers):
            raise InvalidUpload("CSV headers are missing required fields or contain duplicates")
        for row in reader:
            line = reader.line_num
            if len(customers) >= MAX_CUSTOMERS:
                raise InvalidUpload("Expected no more than 1000 customers")
            if None in row or any(value is None for value in row.values()):
                raise InvalidUpload(f"Incorrect number of columns on line {line}")
            customer = {}
            identifier = row.get("customerID", "").strip()
            if len(identifier) > 64:
                raise InvalidUpload(f"Invalid customerID on line {line}")
            if identifier:
                customer["customerID"] = identifier
            for field, choices in CATEGORIES.items():
                value = row[field].strip()
                if value not in choices:
                    raise InvalidUpload(f"Invalid {field} on line {line}")
                customer[field] = value
            for field, (convert, maximum) in NUMBERS.items():
                if field == "TotalCharges" and field not in row:
                    continue  # The API supplies its default when the column is absent.
                raw = row[field].strip()
                if field == "TotalCharges" and not raw and customer["tenure"] == 0:
                    raw = "0"
                try:
                    value = convert(raw)
                    if not math.isfinite(value) or not 0 <= value <= maximum:
                        raise ValueError
                except (ValueError, OverflowError) as exc:
                    raise InvalidUpload(f"Invalid {field} on line {line}") from exc
                customer[field] = value
            customers.append(customer)
    except csv.Error as exc:
        raise InvalidUpload(f"Malformed CSV near line {reader.line_num}") from exc
    if not customers:
        raise InvalidUpload("Expected at least one customer")
    return customers


def summarize_predictions(response, customers):
    """Build a batch summary while leaving customer IDs in the private output."""
    if not isinstance(response, dict):
        raise ValueError("Prediction API returned an invalid response")
    version = response.get("model_version")
    predictions = response.get("predictions")
    count = len(customers)
    if (not isinstance(version, str) or not version.strip()
            or not isinstance(predictions, list) or len(predictions) != count
            or type(response.get("count")) is not int or response["count"] != count):
        raise ValueError("Prediction API returned an invalid batch")
    risk_counts = {"low": 0, "medium": 0, "high": 0}
    probabilities = []
    churn_count = 0
    for customer, prediction in zip(customers, predictions, strict=True):
        if not isinstance(prediction, dict):
            raise ValueError("Prediction API returned an invalid customer result")
        probability = prediction.get("churn_probability")
        risk = prediction.get("risk")
        churn = prediction.get("churn")
        if (type(probability) not in (int, float) or not 0 <= probability <= 1
                or not isinstance(risk, str) or risk not in risk_counts
                or type(churn) is not bool or prediction.get("customerID") != customer.get("customerID")):
            raise ValueError("Prediction API returned an invalid customer result")
        risk_counts[risk] += 1
        churn_count += churn
        probabilities.append(probability)
    if type(response.get("churn_count")) is not int or response["churn_count"] != churn_count:
        raise ValueError("Prediction API returned an inconsistent churn count")
    return {
        "modelVersion": version, "customerCount": count, "churnCount": churn_count,
        "riskCounts": risk_counts, "maxChurnProbability": max(probabilities),
    }
