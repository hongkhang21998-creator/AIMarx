from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from evals.training.train02.core import effective_review, inference_input, load_dataset

APPROVED = Path("evals/training/train02/reviews/2026-09-13-khang")
ALLOWED_INPUT = {"id", "input", "instruction", "output_schema"}


def digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def lines(rows: list[dict]) -> bytes:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
    ).encode("utf-8")


def prepare(output: Path, data: Path = APPROVED) -> dict:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    cases = load_dataset(data)
    selected = [case for case in cases if case["split"] == "smoke-test"]
    if len(selected) != 20 or any(case["review_status"] != "approved" for case in selected):
        raise RuntimeError("smoke evaluation set is not the approved 20-case snapshot")
    inputs = [inference_input(case) for case in selected]
    if any(set(row) != ALLOWED_INPUT for row in inputs):
        raise RuntimeError("model input allowlist mismatch")
    gold = [
        {
            "id": case["id"],
            "content_sha256": case["content_sha256"],
            "reference": case["reference"],
            "rubric": case["rubric"],
            "effective_review": effective_review(case)[0],
        }
        for case in selected
    ]
    output.mkdir(parents=True)
    input_raw, gold_raw = lines(inputs), lines(gold)
    (output / "inputs.jsonl").write_bytes(input_raw)
    (output / "gold-after-review.jsonl").write_bytes(gold_raw)
    manifest = {
        "format": "train04-public-smoke-v1",
        "exposure": "repository_exposed_not_blind",
        "count": 20,
        "case_ids": [row["id"] for row in inputs],
        "inputs_sha256": digest_bytes(input_raw),
        "gold_sha256": digest_bytes(gold_raw),
        "model_input_fields": sorted(ALLOWED_INPUT),
        "gold_is_model_input": False,
        "training_or_tuning_allowed": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


if __name__ == "__main__":
    destination = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("train04-eval-data")
    print(json.dumps(prepare(destination), ensure_ascii=False, indent=2))
