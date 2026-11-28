"""Measure event-to-result latency using downloaded output blobs."""
import argparse
import json
import math
from datetime import datetime
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("folder", type=Path)
parser.add_argument("run_id")
args = parser.parse_args()
if not args.folder.is_dir():
    parser.error("The output download folder does not exist")
times = {}
prefix = args.run_id + "-"
for path in args.folder.rglob("*.json"):
    try:
        result = json.loads(path.read_text(encoding="utf-8-sig"))
        name = result["input"]["blobName"]
        if not name.startswith(prefix):
            continue
        entered = datetime.fromisoformat(result["input"]["timestamp"])
        scored = datetime.fromisoformat(result["metadata"]["timestamp"])
        seconds = (scored - entered).total_seconds()
        if seconds < 0:
            raise ValueError("negative latency")
        times[name] = min(seconds, times.get(name, seconds))
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        print(f"Skipped {path.name}: {error}")

values = sorted(times.values())
print(f"Scored files in {args.run_id}: {len(values)}")
if values:
    p95 = values[math.ceil(.95 * len(values)) - 1]
    print(f"Event-to-result p95: {p95:.2f} seconds")
    print(f"Slowest result: {values[-1]:.2f} seconds")
