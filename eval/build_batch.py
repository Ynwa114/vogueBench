"""Build one analysis-ready JSON batch from separate local draft-label records.

The individual records remain the editable source. The combined file is derived so a
renamed look or corrected label cannot silently remain stale in a bulk analysis.

  python -m eval.build_batch --input runs/label_batches/2026-08-13 \
      --out runs/label_batches/2026-08-13/batch.json
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path, help="folder containing inbox_*.json")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--batch-id", default=None)
    args = parser.parse_args()

    records = [json.loads(path.read_text()) for path in sorted(args.input.glob("inbox_*.json"))]
    if not records:
        raise SystemExit("no individual label records found")
    ids = [record["image_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate image_id in batch records")

    markets = {record.get("market") for record in records}
    if len(markets) != 1 or None in markets:
        raise SystemExit(f"records must have one explicit market; got {sorted(markets, key=str)}")
    schema_version = yaml.safe_load((ROOT / "vocab.yaml").read_text())["version"]
    observations = [
        {"image_id": record["image_id"], **observation}
        for record in records for observation in record.get("schema_observations", [])
    ]
    conflicts = [
        {"image_id": record["image_id"], **conflict}
        for record in records for conflict in record.get("attribute_conflicts", [])
    ]
    batch = {
        "batch_id": args.batch_id or args.input.name,
        "status": "draft_needs_editor_review",
        "schema_version": schema_version,
        "market": markets.pop(),
        "image_count": len(records),
        "schema_observations": observations,
        "attribute_conflicts": conflicts,
        "ocr_by_image_id": {record["image_id"]: record.get("ocr", {}) for record in records},
        "items": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(batch, indent=2) + "\n")
    print(f"wrote {args.out} ({len(records)} records)")


if __name__ == "__main__":
    main()
