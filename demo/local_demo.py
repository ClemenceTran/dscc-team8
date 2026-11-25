"""Run the shared pipeline against in-memory storage and the mock API."""
import argparse
import hashlib
import json
import logging
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Queue
from threading import Thread
from time import sleep
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "functions"))
from pipeline import INPUT_PREFIX, StaleUpload, dispatch_event, job_id, process, utc_now


class DemoStore:
    def __init__(self):
        self.inputs = {}
        self.rejected = {}
        self.output = {}
        self.metadata = {}
        self.pending = Queue()
        self.poison = Queue()

    def add_input(self, name, content):
        etag = hashlib.sha256(content).hexdigest()
        self.inputs[(name, etag)] = content
        return dispatch_event(self, "Microsoft.Storage.BlobCreated", INPUT_PREFIX + quote(name),
                              {"eTag": etag, "contentLength": len(content)}, utc_now())

    def check_input(self, job):
        if len(self.read_input(job)) != job["size"]:
            raise ValueError("Blob size differs from the event")

    def read_input(self, job):
        try:
            return self.inputs[(job["blobName"], job["eTag"])]
        except KeyError as exc:
            raise StaleUpload from exc

    def reject(self, job, reason):
        self.rejected[job_id(job["blobName"], job["eTag"])] = {
            "fileName": job["blobName"], "reason": reason, "copy": self.read_input(job),
        }

    def enqueue(self, job):
        self.pending.put(job)

    def get_output(self, identifier):
        return self.output.get(identifier)

    def save_output_once(self, identifier, result):
        return self.output.setdefault(identifier, result)

    def upsert_metadata(self, metadata):
        self.metadata[metadata["id"]] = metadata

    def recent(self):
        return sorted(self.metadata.copy().values(), key=lambda item: item["timestamp"], reverse=True)[:20]

    def status(self):
        rejected = [{"fileName": item["fileName"], "reason": item["reason"]}
                    for item in self.rejected.copy().values()]
        with self.poison.mutex:
            poison = list(self.poison.queue)
        return {"queued": self.pending.qsize(), "rejected": rejected, "poison": poison}


def predict(customers):
    url = os.getenv("DEMO_PREDICT_URL", "http://127.0.0.1:18081/predict")
    request = Request(url, data=json.dumps({"customers": customers}).encode(),
                      headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def run_jobs(store, predictor, retry_delay=0.5):
    while True:
        job = store.pending.get()
        if job is None:
            store.pending.task_done()
            return
        for attempt in range(1, 6):
            try:
                process(store, predictor, job)
                break
            except Exception as exc:
                logging.warning("Attempt %s/5 failed: %s", attempt, exc)
                if attempt == 5:
                    store.poison.put({**job, "attempts": attempt})
                else:
                    sleep(retry_delay)
        store.pending.task_done()


class DemoPage(SimpleHTTPRequestHandler):
    def __init__(self, *args, store, **kwargs):
        self.store = store
        super().__init__(*args, directory=str(ROOT / "web"), **kwargs)

    def reply(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/recent":
            return self.reply(200, self.store.recent())
        if path == "/demo/status":
            return self.reply(200, self.store.status())
        super().do_GET()

    def do_POST(self):
        if self.path != "/demo/upload":
            return self.reply(404, {"error": "Use POST /demo/upload"})
        try:
            name = self.headers.get("X-File-Name", "").strip()
            length = int(self.headers.get("Content-Length", "0"))
            if not name or not 0 <= length <= 1024 * 1024:
                raise ValueError
        except ValueError:
            return self.reply(400, {"error": "Supply X-File-Name and at most 1 MiB"})
        result = self.store.add_input(name, self.rfile.read(length))
        self.reply(202 if result == "queued" else 200, {"status": result})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=18080)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    store = DemoStore()
    Thread(target=run_jobs, args=(store, predict), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(DemoPage, store=store))
    print(f"Dashboard at http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()

