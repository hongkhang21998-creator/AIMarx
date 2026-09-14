import json
from pathlib import Path

from training.colab_qwen25_3b import prepare


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "training/colab_qwen25_3b"
CONFIG = json.loads((PACKAGE / "config.json").read_text())


def test_config_pins_three_billion_parameter_qlora_trial():
    assert CONFIG["model_id"] == "Qwen/Qwen2.5-3B-Instruct"
    assert CONFIG["model_revision"] == "aa8e72537993ba99e69dfaafa59ed015b17504d1"
    assert CONFIG["max_length"] == 1024
    assert CONFIG["maximum_steps"] == 5
    assert CONFIG["micro_batch_size"] == 1
    assert CONFIG["minimum_gpu_memory_gib"] >= 14
    assert (CONFIG["train_count"], CONFIG["validation_count"]) == (80, 20)


def test_train_source_uses_guarded_nf4_qlora():
    source = (PACKAGE / "train.py").read_text()
    assert "BitsAndBytesConfig" in source
    assert "load_in_4bit=True" in source
    assert 'bnb_4bit_quant_type="nf4"' in source
    assert "bnb_4bit_use_double_quant=True" in source
    assert "prepare_model_for_kbit_training" in source
    assert "no truncation allowed" in source
    assert "push_to_hub" not in source


def test_prepare_uses_isolated_config_and_same_approved_snapshot():
    assert prepare.CONFIG == PACKAGE / "config.json"
    assert prepare.APPROVED.as_posix() == "evals/training/train02/reviews/2026-09-13-khang"


def test_requirements_pin_bitsandbytes_and_every_dependency():
    lines = (PACKAGE / "requirements-colab.txt").read_text().splitlines()
    assert "bitsandbytes==0.47.0" in lines
    assert all("==" in line for line in lines if line)


def test_evaluator_imports_only_the_three_billion_parameter_package():
    source = (PACKAGE / "evaluate.py").read_text()
    assert "training.colab_qwen25_3b" in source
    assert "training.colab_qwen06" not in source
