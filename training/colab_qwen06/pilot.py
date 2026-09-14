from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from training.colab_qwen06.evaluate import verify_inputs
from training.colab_qwen06.prepare import verify_jsonl

PILOT_STEPS = 20


def prepare_pilot(source: Path, output: Path, resume_checkpoint: Path) -> dict:
    config, manifest = verify_inputs(source, resume_checkpoint, expected_step=5)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    output.mkdir(parents=True)
    pilot_config = dict(config)
    pilot_config["maximum_steps"] = PILOT_STEPS
    for split in ("train", "validation"):
        source_file = source / f"{split}.jsonl"
        target = output / source_file.name
        shutil.copy2(source_file, target)
        verify_jsonl(target, config[f"{split}_count"], config[f"{split}_sha256"])
    (output / "config.json").write_text(
        json.dumps(pilot_config, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    result = {
        "status": "pilot_ready",
        "resume_global_step": manifest["global_step"],
        "maximum_steps": PILOT_STEPS,
        "train_count": config["train_count"],
        "validation_count": config["validation_count"],
        "train_sha256": config["train_sha256"],
        "validation_sha256": config["validation_sha256"],
    }
    (output / "pilot-manifest.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return result


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: pilot.py SOURCE_DATA OUTPUT_DATA CHECKPOINT_5")
    print(json.dumps(prepare_pilot(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])), indent=2))
