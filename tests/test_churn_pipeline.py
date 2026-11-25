import json
import sys
import unittest
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "demo"))
from local_demo import DemoPage, DemoStore, predict, run_jobs  # noqa: E402
from mock_api import MockAPI, mock_prediction  # noqa: E402
from pipeline import process  # noqa: E402

SAMPLES = ROOT / "samples"
VALID = (SAMPLES / "customers_valid.csv").read_bytes()


class ChurnPipelineTests(unittest.TestCase):
    def setUp(self):
        self.store = DemoStore()

    def server(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_port}"

    def test_valid_batch_uses_the_team_contract(self):
        self.assertEqual(self.store.add_input("customers.csv", VALID), "queued")
        result = process(self.store, mock_prediction, self.store.pending.get_nowait())
        self.assertEqual(result["customerCount"], 20)
        self.assertEqual(sum(result["riskCounts"].values()), 20)
        self.assertEqual(result["riskCounts"]["high"], 4)
        self.assertEqual(result["maxChurnProbability"], .78)
        self.assertNotIn("customerID", result)
        output = self.store.get_output(result["id"])
        self.assertEqual(output["response"]["predictions"][0]["customerID"], "4376-KFVRS")

    def test_invalid_samples_are_rejected_without_queuing(self):
        for name in ("not_a_csv.txt", "customers_missing_columns.csv", "customers_bad_values.csv"):
            data = (SAMPLES / name).read_bytes()
            self.assertEqual(self.store.add_input(name, data), "rejected")
        self.assertEqual(len(self.store.rejected), 3)
        self.assertTrue(self.store.pending.empty())
        self.assertEqual(self.store.add_input("empty.csv", b""), "rejected")
        self.assertEqual(self.store.add_input("large.csv", b"x" * 262145), "rejected")

    def test_duplicate_repairs_metadata_without_predicting_again(self):
        self.store.add_input("customers.csv", VALID)
        job = self.store.pending.get_nowait()
        with patch.object(self.store, "upsert_metadata", side_effect=RuntimeError):
            with self.assertRaises(RuntimeError):
                process(self.store, mock_prediction, job)
        with patch.object(self.store, "read_input", side_effect=AssertionError):
            result = process(self.store, None, job)
            self.assertEqual(process(self.store, None, job), result)
        self.assertEqual(len(self.store.recent()), 1)

    def test_invalid_prediction_response_saves_no_result(self):
        self.store.add_input("customers.csv", VALID)
        job = self.store.pending.get_nowait()
        with self.assertRaises(ValueError):
            process(self.store, lambda _: {"predictions": []}, job)
        self.assertFalse(self.store.output)

    def test_http_demo_and_poison_queue(self):
        mock_url = self.server(MockAPI)
        demo_url = self.server(partial(DemoPage, store=self.store))

        def upload(name, data):
            request = Request(demo_url + "/demo/upload", data=data, headers={"X-File-Name": name})
            with urlopen(request, timeout=3) as response:
                return json.load(response)["status"]

        with patch.dict("os.environ", {"DEMO_PREDICT_URL": mock_url + "/predict"}):
            self.assertEqual(upload("customers.csv", VALID), "queued")
            failure = VALID.replace(b"4376-KFVRS", b"MOCK_FAIL", 1)
            self.assertEqual(upload("failure.csv", failure), "queued")
            self.store.pending.put(None)
            with self.assertLogs(level="WARNING") as messages:
                run_jobs(self.store, predict, retry_delay=0)
        self.assertEqual(len(messages.output), 5)
        with urlopen(demo_url + "/api/recent", timeout=3) as response:
            self.assertEqual(json.load(response)[0]["customerCount"], 20)
        with urlopen(demo_url + "/demo/status", timeout=3) as response:
            self.assertEqual(json.load(response)["poison"][0]["attempts"], 5)

