import http from 'k6/http';
import { check } from 'k6';
import exec from 'k6/execution';

const container = (__ENV.INPUT_CONTAINER_URL || '').replace(/\/$/, '');
const token = (__ENV.INPUT_SAS || '').replace(/^\?/, '');
const runId = __ENV.RUN_ID || '';
const count = Number(__ENV.FILE_COUNT || 100);
if (!/^https:\/\/[^/?#]+\/input$/.test(container) || !token || !/^load-[a-zA-Z0-9-]+$/.test(runId)) {
  throw new Error('Set INPUT_CONTAINER_URL, INPUT_SAS and RUN_ID before running.');
}
if (![1, 100].includes(count)) throw new Error('FILE_COUNT must be 1 or 100.');
const csv = open(__ENV.CSV_FILE || './samples/customers_valid.csv', 'b');

export const options = {
  discardResponseBodies: true,
  scenarios: {
    burst: { executor: 'per-vu-iterations', vus: count, iterations: 1, maxDuration: '45s' },
  },
  thresholds: {
    checks: ['rate==1'],
    iterations: [`count==${count}`],
  },
};

export default function () {
  const name = `${runId}-${exec.scenario.iterationInTest + 1}.csv`;
  const response = http.put(`${container}/${name}?${token}`, csv, {
    headers: {
      'x-ms-blob-type': 'BlockBlob',
      'x-ms-version': '2023-11-03',
      'Content-Type': 'text/csv',
      'If-None-Match': '*',
    },
    tags: { name: 'Azure Blob upload' },
    redirects: 0,
    timeout: '15s',
  });
  const accepted = check(response, { 'blob created (201)': (result) => result.status === 201 });
  if (!accepted) console.warn(`Upload failed for ${name} (HTTP ${response.status})`);
}
