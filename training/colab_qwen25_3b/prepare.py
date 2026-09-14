from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG = Path(__file__).with_name("config.json")
APPROVED = Path("evals/training/train02/reviews/2026-09-13-khang")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_jsonl(path: Path, count: int, expected_hash: str) -> None:
    if sha256(path) != expected_hash:
        raise RuntimeError(f"checksum mismatch: {path.name}")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    if len(rows) != count or any(set(row) != {"prompt", "completion"} for row in rows):
        raise RuntimeError(f"invalid export: {path.name}")


def prepare(output: Path) -> dict:
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    for split in ("train", "validation"):
        target = output / f"{split}.jsonl"
        subprocess.run(
            [sys.executable, "-m", "evals.training.train02.cli", "export", "--data", str(APPROVED),
             "--split", split, "--output", str(target)],
            check=True,
        )
        verify_jsonl(target, config[f"{split}_count"], config[f"{split}_sha256"])
    shutil.copy2(CONFIG, output / "config.json")
    manifest = {
        "status": "verified_local_export",
        "approved_snapshot": APPROVED.as_posix(),
        "model_id": config["model_id"],
        "model_revision": config["model_revision"],
        "splits": {
            split: {"count": config[f"{split}_count"], "sha256": config[f"{split}_sha256"]}
            for split in ("train", "validation")
        },
        "smoke_test_exported": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


if __name__ == "__main__":
    destination = Path(sys.argv[1]) if len(sys.argv) == 2 else Path("colab_data")
    print(json.dumps(prepare(destination), ensure_ascii=False, indent=2))

