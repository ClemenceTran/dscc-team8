"""Run a contract-compatible local endpoint for testing the pipeline."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def mock_prediction(customers):
    predictions = []
    for customer in customers:
        probability = max(0.05, min(0.95, 0.86 - customer["tenure"] / 100))
        probability = round(probability, 4)
        risk = "high" if probability >= .7 else "medium" if probability >= .4 else "low"
        predictions.append({"customerID": customer.get("customerID"), "churn_probability": probability,
                            "churn": probability >= .5, "risk": risk})
    return {
        "model_version": "mock-0.1.0", "api_version": "1.0.0", "count": len(predictions),
        "churn_count": sum(row["churn"] for row in predictions), "latency_ms": 0,
        "predictions": predictions,
    }


class MockAPI(BaseHTTPRequestHandler):
    def reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def do_POST(self):
        if self.path != "/predict":
            return self.reply(404, {"error": "Use POST /predict"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", "0"))))
            customers = body["customers"]
            if not isinstance(customers, list) or not 1 <= len(customers) <= 1000:
                raise ValueError
            if any(customer.get("customerID") == "MOCK_FAIL" for customer in customers):
                return self.reply(503, {"error": "Intentional local failure"})
            result = mock_prediction(customers)
        except (AttributeError, ValueError, KeyError, TypeError):
            return self.reply(422, {"error": "Supply a valid customers batch"})
        self.reply(200, result)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18081)
    args = parser.parse_args()
    print(f"Mock prediction API at http://127.0.0.1:{args.port}/predict", flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), MockAPI).serve_forever()

