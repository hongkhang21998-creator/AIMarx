import copy
import json
from pathlib import Path

import pytest

from evals.training.train03 import blind, generate, prepare

ROOT = Path(__file__).parents[1]


def fake_inputs():
    return [{"id": f"case-{i}", "input": {"request": str(i)}, "instruction": "x", "output_schema": {}} for i in range(20)]


def fake_run(inputs, prefix):
    return [{"id": row["id"], "output": f"{prefix}-{row['id']}", "error": None} for row in inputs]


def test_prepare_exports_only_allowlisted_model_input(tmp_path):
    manifest = prepare.prepare(tmp_path / "bundle")
    rows = blind.read_jsonl(tmp_path / "bundle/inputs.jsonl")
    gold = blind.read_jsonl(tmp_path / "bundle/gold-after-review.jsonl")
    assert manifest["exposure"] == "repository_exposed_not_blind"
    assert manifest["training_or_tuning_allowed"] is False
    assert len(rows) == len(gold) == 20
    assert all(set(row) == prepare.ALLOWED_INPUT for row in rows)
    serialized = json.dumps(rows, ensure_ascii=False)
    for forbidden in ("reference", "rubric", "reviewer", "content_sha256", "split", "provenance"):
        assert forbidden not in serialized


def test_ab_mapping_is_deterministic_balanced_by_case_and_round_trips():
    inputs = fake_inputs()
    base, adapter = fake_run(inputs, "base"), fake_run(inputs, "adapter")
    first, reveal = blind.build_bundle(inputs, base, adapter, seed=530014)
    second, reveal_again = blind.build_bundle(inputs, base, adapter, seed=530014)
    assert first == second and reveal == reveal_again
    assert {value for mapping in reveal["mapping"].values() for value in mapping.values()} == {"base", "adapter"}
    for row in first:
        mapping = reveal["mapping"][row["id"]]
        assert row["candidate_A"]["output"].startswith(mapping["A"])
        assert row["candidate_B"]["output"].startswith(mapping["B"])
        assert "base" not in row and "adapter" not in row


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "both", "neither"])
def test_ab_bundle_rejects_incomplete_or_ambiguous_runs(mutation):
    inputs = fake_inputs()
    base, adapter = fake_run(inputs, "base"), fake_run(inputs, "adapter")
    if mutation == "missing": base.pop()
    elif mutation == "duplicate": base[-1]["id"] = base[0]["id"]
    elif mutation == "extra": base[0]["secret"] = "x"
    elif mutation == "both": base[0]["error"] = "failed"
    else: base[0]["output"] = None
    with pytest.raises(ValueError):
        blind.build_bundle(inputs, base, adapter, seed=1)


def test_generation_source_is_inference_only_and_fixed_decoding():
    source = open(generate.__file__, encoding="utf-8").read()
    assert "torch.inference_mode()" in source
    assert "is_trainable=False" in source
    assert "do_sample=False" in source
    assert "enable_thinking=False" in source
    assert "trainer.train" not in source and "push_to_hub" not in source


def test_generation_rejects_checkpoint_identity_mismatch(tmp_path):
    config = {
        "model_id": "Qwen/Qwen3-0.6B", "model_revision": "rev",
        "train_sha256": "a" * 64, "validation_sha256": "b" * 64,
    }
    manifest = dict(config)
    checkpoint = tmp_path / "checkpoint-20"
    checkpoint.mkdir()
    (checkpoint / "adapter_config.json").write_text(
        json.dumps({"base_model_name_or_path": config["model_id"]})
    )
    generate.verify_identity(manifest, config, checkpoint)
    changed = dict(manifest, train_sha256="c" * 64)
    with pytest.raises(RuntimeError, match="train_sha256"):
        generate.verify_identity(changed, config, checkpoint)


def test_colab_notebook_is_clean_pinned_and_never_trains_or_leaks_gold():
    notebook = json.loads(
        (ROOT / "notebooks/TRAIN_04_Qwen3_0_6B_AB_Eval_Colab.ipynb").read_text()
    )
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    assert "5b0f4330ac5aa3ecd9394de50c504d0fbe464147" in source
    assert source.index("train03.prepare") < source.index("--mode', 'base'")
    assert source.index("--mode', 'adapter'") < source.index("train03.blind")
    assert "gold-after-review.jsonl" in source and "open-after-review" in source
    assert "training.colab_qwen06.train" not in source
    assert "push_to_hub" not in source and "drive.mount" not in source
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code":
            compile("".join(cell["source"]), "train04-notebook", "exec")
            assert cell["execution_count"] is None and not cell["outputs"]
