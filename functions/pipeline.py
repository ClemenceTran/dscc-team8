"""Shared validation, queue message and prediction logic."""
import hashlib
import json
import logging
from datetime import datetime, timezone
from time import perf_counter
from urllib.parse import unquote, urlsplit

from churn_csv import InvalidUpload, parse_customers, summarize_predictions
QUEUE_NAME = "inference-requests"
INPUT_PREFIX = "/blobServices/default/containers/input/blobs/"


class StaleUpload(Exception):
    """The event's source version cannot be read."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def job_id(name, etag):
    key = json.dumps([name, etag.strip('"')], ensure_ascii=False)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def dispatch(store, name, etag, size, timestamp):
    job = {"blobName": name, "eTag": etag, "size": size, "timestamp": timestamp}
    try:
        # Verify the event still refers to the same upload, even for invalid files.
        store.check_input(job)
        parse_customers(name, size, lambda: store.read_input(job))
    except InvalidUpload as exc:
        store.reject(job, str(exc))
        logging.info("Rejected job=%s reason=%s", job_id(name, etag), exc)
        return "rejected"

    store.enqueue(job)
    logging.info("Queued job=%s", job_id(name, etag))
    return "queued"


def dispatch_event(store, event_type, subject, data, timestamp):
    if event_type != "Microsoft.Storage.BlobCreated" or not subject.startswith(INPUT_PREFIX):
        return "ignored"
    # Event Grid provides the encoded blob URL. Use only its path-derived name
    # and always read from our configured account, never from the event URL.
    url_path = urlsplit(data.get("url", "")).path
    name = unquote(url_path.removeprefix("/input/")) if url_path.startswith("/input/") else unquote(subject[len(INPUT_PREFIX):])
    if not name:
        return "ignored"
    try:
        return dispatch(store, name, data["eTag"], data["contentLength"], timestamp)
    except StaleUpload:
        logging.warning("Skipped superseded or missing input job=%s", job_id(name, data["eTag"]))
        return "stale"


def process(store, predict, job):
    name = job["blobName"]
    identifier = job_id(name, job["eTag"])
    result = store.get_output(identifier)
    if result is None:
        start = perf_counter()
        customers = parse_customers(name, job["size"], lambda: store.read_input(job))
        prediction = predict(customers)
        summary = summarize_predictions(prediction, customers)
        metadata = {
            "id": identifier,
            "fileName": name,
            "timestamp": utc_now(),
            "durationMs": round((perf_counter() - start) * 1000, 2),
            **summary,
        }
        result = store.save_output_once(identifier, {
            "metadata": metadata, "input": job, "response": prediction,
        })
    # On retry, reuse the saved output even if the input is no longer available.
    store.upsert_metadata(result["metadata"])
    logging.info("Completed job=%s duration_ms=%s", identifier, result["metadata"]["durationMs"])
    return result["metadata"]

