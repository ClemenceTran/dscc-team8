# Churn pipeline and dashboard

This part implements PROJECT.pdf sections 4.3–4.4. Upload a customer CSV and the dashboard shows the scored batch automatically.

```text
CSV in input → Event Grid → dispatcher → queue → worker → churn API
                               ↓                 ↓
                          rejected blob         output JSON and Cosmos batch summary

Dashboard → /api/recent → latest 20 batch summaries
```

- The dispatcher checks the CSV extension, UTF-8 encoding, 256 KiB file limit, required columns and customer field values. It accepts up to 1,000 customers per file and copies invalid files to `rejected/` with a reason.
- The worker sends `{"customers":[...]}` to the team's `POST /predict` endpoint. It saves the full response in a private output blob and writes one summary per file version to Cosmos DB. A repeat delivery can finish writing Cosmos metadata from the saved blob.
- The dashboard refreshes every 30 seconds. It shows the API's aggregated risk bands, predicted churn share, and newest batches. The threshold explorer filters batches by their highest customer probability. It changes the table view only. Use public-safe filenames because the anonymous results route displays those names.
- Failed worker jobs are attempted five times before they reach `inference-requests-poison`. Simultaneous first deliveries can both call the API, and the storage writes converge on one saved result per filename and ETag.

## Test locally

Run from the repository root. Python 3.12 matches the planned Azure runtime.

```powershell
python -m unittest discover -s tests -v
```

For a local walkthrough, run the mock API and dashboard in two terminals.

```powershell
python demo/mock_api.py
```

```powershell
python demo/local_demo.py
```

Open [the dashboard](http://127.0.0.1:18080/). In a third terminal, upload the team's sample.

```powershell
curl.exe -H "X-File-Name: customers_valid.csv" --data-binary "@samples/customers_valid.csv" http://127.0.0.1:18080/demo/upload
curl.exe -H "X-File-Name: customers_bad_values.csv" --data-binary "@samples/customers_bad_values.csv" http://127.0.0.1:18080/demo/upload
Invoke-RestMethod http://127.0.0.1:18080/demo/status | ConvertTo-Json -Depth 6
```

The valid sample scores 20 customers. The invalid sample has an unsupported contract value and appears in the rejected list. To intentionally trigger retries in the local mock, use a copy of the valid CSV with the first customer ID changed to `MOCK_FAIL`, then upload it under a new name. The mock returns 503, and the failure appears in `/demo/status` after five attempts.

To switch to the real team API, start it per [the API guide](../api/README.md), then start the local dashboard with `DEMO_PREDICT_URL` set to its URL.

```powershell
$env:DEMO_PREDICT_URL = "http://127.0.0.1:8000/predict"
python demo/local_demo.py
```

The local dashboard uses an in-memory queue and storage. Restarting it clears demo results.

## Azure handoff

1. Deploy `functions/` as a single Python 3.12 Azure Functions v2 app on Flex Consumption with 512 MB instance memory. Follow PROJECT.pdf section 6 for resource setup. Provision `input`, `output`, `rejected`, and `models` containers, Blob versioning, and the `inference-requests` queue.
2. Set up Cosmos DB for NoSQL Free Tier with database `pipeline`, 400 shared RU/s, and container `inferences` partitioned by `/fileName`. Give the Function App system-assigned managed identity the Blob and Queue data roles and Cosmos DB data-plane access. Configure the Functions host and deployment storage separately.
3. Set the Function App values below. Supply any credentials through app settings only.

| Setting | Value |
|---|---|
| `PipelineStorage__blobServiceUri` | `https://<account>.blob.core.windows.net` |
| `PipelineStorage__queueServiceUri` | `https://<account>.queue.core.windows.net` |
| `COSMOS_ENDPOINT` | Azure Cosmos DB HTTPS endpoint |
| `PREDICT_URL` | Team Container Apps HTTPS URL ending in `/predict` |

4. Subscribe the storage account's Event Grid system topic to the deployed `dispatcher` function. Use Event Grid schema, event type `Microsoft.Storage.BlobCreated`, and subject prefix `/blobServices/default/containers/input/`.
5. Set `window.RECENT_API_URL` in the deployed copy of `web/config.js` to the Function App's public HTTPS `/api/recent` URL. Upload `web/` to `$web`, and add only the exact static website origin in Function App CORS. Keep the input and output blobs private and use approved sample data for the demo.

For debugging, a BlobCreated event for this CSV has the subject below. The dispatcher reads the event's ETag and content length and publishes the decoded JSON shown here. Replace the sample values with values from the upload if replaying a message, and send it using Base64 queue encoding.

```text
/blobServices/default/containers/input/blobs/customers_valid.csv
```

```json
{"blobName":"customers_valid.csv","eTag":"0xEXAMPLE","size":2947,"timestamp":"2026-11-25T12:00:00Z"}
```

In Azure, capture a valid upload with its output JSON and automatically refreshed dashboard, an invalid upload with its rejected copy and reason, and a test-only API failure with five attempts and its poison queue message. Record the actual time from upload to saved result. Cloud deployment and these Azure acceptance checks still need the shared environment.


## Local verification

The five local pipeline tests passed. An end-to-end browser test used the team's actual model (version 1.0.0) on the 20-customer sample. The dashboard showed 12 low-risk, 4 medium-risk and 4 high-risk customers after its scheduled refresh. The test also confirmed rejection of the sample with invalid values and checked the probability filter at desktop and mobile widths.
