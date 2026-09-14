import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from training.colab_qwen06 import evaluate, prepare

ROOT = Path(__file__).parents[1]
CONFIG = json.loads((ROOT / "training/colab_qwen06/config.json").read_text())
NOTEBOOK = json.loads((ROOT / "notebooks/TRAIN_03_Qwen3_0_6B_Colab.ipynb").read_text())


def test_config_locks_model_data_and_free_tier_size():
    assert CONFIG["model_id"] == "Qwen/Qwen3-0.6B"
    assert CONFIG["model_revision"] == "c1899de289a04d12100db370d81485cdf75e47ca"
    assert CONFIG["enable_thinking"] is False
    assert CONFIG["max_length"] == 4096
    assert CONFIG["maximum_steps"] == 5
    assert CONFIG["minimum_gpu_memory_gib"] >= 12
    assert (CONFIG["train_count"], CONFIG["validation_count"]) == (80, 20)


def test_notebook_has_two_process_resume_and_no_paid_or_cloud_push():
    source = "\n".join("".join(cell.get("source", [])) for cell in NOTEBOOK["cells"])
    assert "--stop-after', '1'" in source
    assert "--resume-from" in source and "checkpoint-1" in source
    assert "checkpoint-5" in source
    code = ["".join(c["source"]) for c in NOTEBOOK["cells"] if c["cell_type"] == "code"]
    assert next(i for i, c in enumerate(code) if "--resume-from" in c) < next(i for i, c in enumerate(code) if "training.colab_qwen06.evaluate" in c) < next(i for i, c in enumerate(code) if "make_archive" in c)
    for cell in NOTEBOOK["cells"]:
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), "notebook", "exec")
            assert cell["execution_count"] is None and not cell["outputs"]
    assert "training.colab_qwen06.evaluate" in source
    assert "push_to_hub" not in source and "drive.mount" not in source
    assert "files.download" in source


def test_requirements_are_exact_pins():
    lines = [line for line in (ROOT / "training/colab_qwen06/requirements-colab.txt").read_text().splitlines() if line]
    assert lines and all("==" in line and not line.startswith("-") for line in lines)


def test_verify_jsonl_checks_hash_count_and_shape(tmp_path):
    target = tmp_path / "train.jsonl"
    raw = (json.dumps({"prompt": "{}", "completion": "{}"}) + "\n").encode()
    target.write_bytes(raw)
    prepare.verify_jsonl(target, 1, hashlib.sha256(raw).hexdigest())
    with pytest.raises(RuntimeError, match="checksum"):
        prepare.verify_jsonl(target, 1, "0" * 64)
    with pytest.raises(RuntimeError, match="invalid export"):
        prepare.verify_jsonl(target, 2, hashlib.sha256(raw).hexdigest())


def test_training_source_disables_thinking_and_forbids_truncation():
    source = (ROOT / "training/colab_qwen06/train.py").read_text()
    assert "enable_thinking=False" in source
    assert '[-100] * len(prompt_ids)' in source
    assert "no truncation allowed" in source
    assert 'save_only_model=False' in source
    assert 'resume_from_checkpoint=' in source


def test_evaluation_verifies_every_manifest_file(tmp_path):
    checkpoint = tmp_path / "checkpoint-5"
    checkpoint.mkdir()
    adapter = checkpoint / "adapter_model.safetensors"
    adapter.write_bytes(b"adapter")
    (checkpoint / "adapter_config.json").write_text("{}")
    (checkpoint / "trainer_state.json").write_text('{"global_step": 5}')
    manifest = {
        "global_step": 5,
        "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in checkpoint.iterdir()},
    }
    (checkpoint / "aimarx-manifest.json").write_text(json.dumps(manifest))
    assert evaluate.verify_checkpoint(checkpoint) == manifest
    adapter.write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        evaluate.verify_checkpoint(checkpoint)


@pytest.mark.parametrize("files", [{}, {"../escape": "0" * 64}])
def test_evaluation_rejects_incomplete_manifest(tmp_path, files):
    (tmp_path / "aimarx-manifest.json").write_text(json.dumps({"global_step": 5, "files": files}))
    with pytest.raises(RuntimeError, match="missing required"):
        evaluate.verify_checkpoint(tmp_path)


def test_evaluation_rejects_changed_validation_before_checkpoint_loading(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(CONFIG))
    (tmp_path / "validation.jsonl").write_text('{"prompt":"changed","completion":"changed"}\n')
    with pytest.raises(RuntimeError, match="checksum"):
        evaluate.verify_inputs(tmp_path, tmp_path / "missing-checkpoint")


def test_evaluation_compares_base_and_reloaded_adapter_without_training():
    source = (ROOT / "training/colab_qwen06/evaluate.py").read_text()
    assert "PeftModel.from_pretrained" in source
    assert "is_trainable=False" in source
    assert "torch.inference_mode()" in source
    assert 'reduction="sum"' in source
    assert "trainer.train" not in source
