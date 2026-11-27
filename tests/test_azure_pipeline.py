import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
FUNCTIONS = ROOT / "functions"
sys.path.insert(0, str(FUNCTIONS))
sys.path.insert(0, str(ROOT / "demo"))

from churn_csv import parse_customers  # noqa: E402
from mock_api import mock_prediction  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "azure_pipeline_under_test",
    FUNCTIONS / "pipeline.py",
)
azure_pipeline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(azure_pipeline)

VALID = (ROOT / "samples" / "customers_valid.csv").read_bytes()


class FakeStore:
    def __init__(self):
        self.outputs = {}
        self.metadata = []
        self.input_data = VALID

    def read_input(self, job):
        return self.input_data

    def get_output(self, identifier):
        return self.outputs.get(identifier)

    def save_output_once(self, identifier, result):
        if identifier not in self.outputs:
            self.outputs[identifier] = result
        return self.outputs[identifier]

    def upsert_metadata(self, metadata):
        self.metadata.append(metadata)


class AzurePipelineTests(unittest.TestCase):
    def test_duplicate_job_reuses_saved_output_without_predicting_again(self):
        store = FakeStore()
        predict = Mock(side_effect=mock_prediction)

        job = {
            "blobName": "customers_valid.csv",
            "eTag": '"test-etag-1"',
            "size": len(VALID),
            "timestamp": "2026-11-27T12:00:00Z",
        }

        first_result = azure_pipeline.process(store, predict, job)

        self.assertEqual(first_result["customerCount"], 20)
        self.assertEqual(predict.call_count, 1)

        with patch.object(
            store,
            "read_input",
            side_effect=AssertionError("Retry should reuse saved output"),
        ):
            second_result = azure_pipeline.process(store, predict, job)

        self.assertEqual(second_result, first_result)
        self.assertEqual(predict.call_count, 1)
        self.assertEqual(len(store.outputs), 1)
        self.assertEqual(len(store.metadata), 2)


if __name__ == "__main__":
    unittest.main()
