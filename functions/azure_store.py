"""Azure SDK calls used by the pipeline. Clients are shared across invocations."""
import json
import os
from tempfile import TemporaryFile

from azure.core import MatchConditions
from azure.core.exceptions import (
    ResourceExistsError, ResourceModifiedError, ResourceNotFoundError,
)
from azure.cosmos import CosmosClient
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.storage.queue import QueueClient, TextBase64EncodePolicy

from pipeline import QUEUE_NAME, StaleUpload, job_id

JSON_CONTENT = ContentSettings(content_type="application/json")
FIELDS = ("id", "fileName", "timestamp", "customerCount", "churnCount", "riskCounts",
          "maxChurnProbability", "modelVersion", "durationMs")


class AzureStore:
    def __init__(self):
        identity = ManagedIdentityCredential()
        connection = os.getenv("PipelineStorage")
        queue_options = {"message_encode_policy": TextBase64EncodePolicy()}
        if connection:
            self.blobs = BlobServiceClient.from_connection_string(connection)
            self.queue = QueueClient.from_connection_string(connection, QUEUE_NAME, **queue_options)
        else:
            self.blobs = BlobServiceClient(os.environ["PipelineStorage__blobServiceUri"], credential=identity)
            self.queue = QueueClient(os.environ["PipelineStorage__queueServiceUri"], QUEUE_NAME,
                                     credential=identity, **queue_options)
        cosmos = CosmosClient(os.environ["COSMOS_ENDPOINT"], os.getenv("COSMOS_KEY") or identity)
        self.inferences = cosmos.get_database_client("pipeline").get_container_client("inferences")

    def _input(self, job):
        return self.blobs.get_blob_client("input", job["blobName"])

    def _conditions(self, job):
        return {"etag": '"' + job["eTag"].strip('"') + '"',
                "match_condition": MatchConditions.IfNotModified}

    def _source_operation(self, job, operation):
        try:
            return getattr(self._input(job), operation)(**self._conditions(job))
        except (ResourceModifiedError, ResourceNotFoundError) as current_error:
            # An overwrite can happen before the event or queue message arrives.
            # With versioning enabled, recover the exact old upload by ETag.
            container = self.blobs.get_container_client("input")
            for version in container.list_blobs(
                name_starts_with=job["blobName"], include=["versions"]
            ):
                if (
                    version.name == job["blobName"] and version.version_id
                    and version.etag.strip('"') == job["eTag"].strip('"')
                ):
                    try:
                        source = container.get_blob_client(version.name, version_id=version.version_id)
                        return getattr(source, operation)(**self._conditions(job))
                    except (ResourceModifiedError, ResourceNotFoundError) as exc:
                        raise StaleUpload from exc
            raise StaleUpload from current_error

    def check_input(self, job):
        props = self._source_operation(job, "get_blob_properties")
        if props.size != job["size"]:
            raise ValueError("Blob size differs from the event")

    def _download_input(self, job):
        return self._source_operation(job, "download_blob")

    def read_input(self, job):
        return self._download_input(job).readall()

    def reject(self, job, reason):
        target = self.blobs.get_blob_client("rejected", job_id(job["blobName"], job["eTag"]))
        if target.exists():
            return
        # Use a seekable temporary file to keep memory bounded for oversized uploads.
        with TemporaryFile() as copy:
            self._download_input(job).readinto(copy)
            copy.seek(0)
            try:
                target.upload_blob(copy, overwrite=False, metadata={"reason": reason})
            except ResourceExistsError:
                pass

    def enqueue(self, job):
        self.queue.send_message(json.dumps(job))

    def _output(self, identifier):
        return self.blobs.get_blob_client("output", f"{identifier}.json")

    def get_output(self, identifier):
        try:
            return json.loads(self._output(identifier).download_blob().readall())
        except ResourceNotFoundError:
            return None

    def save_output_once(self, identifier, result):
        try:
            self._output(identifier).upload_blob(
                json.dumps(result, ensure_ascii=False).encode("utf-8"),
                overwrite=False, content_settings=JSON_CONTENT,
            )
        except ResourceExistsError:
            return self.get_output(identifier)
        return result

    def upsert_metadata(self, metadata):
        self.inferences.upsert_item(metadata)

    def recent(self):
        fields = ", ".join(f"c.{field}" for field in FIELDS)
        return list(self.inferences.query_items(
            query=f"SELECT TOP 20 {fields} FROM c WHERE IS_DEFINED(c.customerCount) ORDER BY c.timestamp DESC",
            enable_cross_partition_query=True,
        ))

