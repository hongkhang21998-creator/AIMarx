from __future__ import annotations

import hashlib
import argparse
import json
import random
from pathlib import Path

from evals.planning_v2.score import score_raw


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def digest(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def validate_runs(inputs: list[dict], base: list[dict], adapter: list[dict]) -> None:
    expected = [row["id"] for row in inputs]
    if len(expected) != 20 or len(set(expected)) != 20:
        raise ValueError("expected exactly 20 unique evaluation inputs")
    for rows in (base, adapter):
        if [row.get("id") for row in rows] != expected:
            raise ValueError("generation IDs/order differ from locked inputs")
        if any(set(row) != {"id", "output", "error"} for row in rows):
            raise ValueError("generation row contract mismatch")
        if any((row["output"] is None) == (row["error"] is None) for row in rows):
            raise ValueError("each generation needs exactly one output or error")


def build_bundle(inputs: list[dict], base: list[dict], adapter: list[dict], seed: int) -> tuple[list[dict], dict]:
    validate_runs(inputs, base, adapter)
    rng = random.Random(seed)
    review, mapping = [], {}
    for prompt, base_row, adapter_row in zip(inputs, base, adapter, strict=True):
        adapter_is_a = bool(rng.getrandbits(1))
        a, b = (adapter_row, base_row) if adapter_is_a else (base_row, adapter_row)
        mapping[prompt["id"]] = {"A": "adapter" if adapter_is_a else "base", "B": "base" if adapter_is_a else "adapter"}
        review.append({
            "id": prompt["id"], "input": prompt["input"],
            "candidate_A": {"output": a["output"], "error": a["error"],
                            "automated_check": score_raw(a["output"], prompt["input"]) if a["output"] is not None else None},
            "candidate_B": {"output": b["output"], "error": b["error"],
                            "automated_check": score_raw(b["output"], prompt["input"]) if b["output"] is not None else None},
            "review": {
                "preferred": None,
                "A": {"decision": None, "grounding": None, "missing_information": None, "worker_order": None, "no_escalation": None},
                "B": {"decision": None, "grounding": None, "missing_information": None, "worker_order": None, "no_escalation": None},
                "notes": "",
            },
        })
    reveal = {"format": "train04-ab-reveal-v1", "seed": seed, "mapping": mapping}
    reveal["mapping_sha256"] = digest(mapping)
    return review, reveal


def write_bundle(inputs_path: Path, base_path: Path, adapter_path: Path, output: Path, seed: int) -> dict:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    inputs, base, adapter = map(read_jsonl, (inputs_path, base_path, adapter_path))
    review, reveal = build_bundle(inputs, base, adapter, seed)
    output.mkdir(parents=True)
    (output / "review.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in review), encoding="utf-8")
    (output / "reveal-after-review.json").write_text(json.dumps(reveal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"count": len(review), "mapping_sha256": reveal["mapping_sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=530014)
    args = parser.parse_args()
    print(json.dumps(write_bundle(args.inputs, args.base, args.adapter, args.output, args.seed), indent=2))
