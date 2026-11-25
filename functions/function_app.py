"""One Azure Functions v2 app with the three handlers required by the brief."""
import json
import logging
import os
from functools import lru_cache

import azure.functions as func
import requests

from azure_store import AzureStore
from pipeline import QUEUE_NAME, dispatch_event, job_id, process

app = func.FunctionApp()


@lru_cache
def store():
    return AzureStore()


# The client keeps HTTP connections open between predictions.
http = requests.Session()


def predict(customers):
    url = os.environ["PREDICT_URL"]
    token = os.getenv("PREDICT_BEARER_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    response = http.post(url, json={"customers": customers}, headers=headers, timeout=(3, 20))
    response.raise_for_status()
    return response.json()


@app.function_name(name="dispatcher")
@app.event_grid_trigger(arg_name="event")
def dispatcher(event: func.EventGridEvent):
    dispatch_event(store(), event.event_type, event.subject,
                   event.get_json(), event.event_time.isoformat())


@app.function_name(name="worker")
@app.queue_trigger(arg_name="message", queue_name=QUEUE_NAME, connection="PipelineStorage")
def worker(message: func.QueueMessage):
    job = json.loads(message.get_body())
    try:
        process(store(), predict, job)
    except Exception:
        logging.exception("Worker failed job=%s queue_message=%s",
                          job_id(job["blobName"], job["eTag"]), message.id)
        raise  # The Functions host counts this and retries it.


@app.function_name(name="recent")
@app.route(route="recent", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def recent(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(store().recent()), mimetype="application/json",
        headers={"Cache-Control": "no-store"},
    )

