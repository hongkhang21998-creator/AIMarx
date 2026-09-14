from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from training.colab_qwen06.prepare import CONFIG, verify_jsonl
from training.colab_qwen06.train import CompletionCollator, encode_row, load_rows, require_colab_gpu


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_checkpoint(checkpoint: Path, expected_step: int = 5) -> dict:
    manifest_path = checkpoint / "aimarx-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("global_step") != expected_step:
        raise RuntimeError(f"checkpoint is not the expected step-{expected_step} artifact")
    files = manifest.get("files", {})
    if not isinstance(files, dict) or not {"adapter_config.json", "adapter_model.safetensors", "trainer_state.json"} <= files.keys():
        raise RuntimeError("checkpoint manifest missing required files")
    mismatches = []
    for name, expected in files.items():
        if not isinstance(name, str) or Path(name).name != name or "/" in name or "\\" in name or name in {".", ".."}:
            raise RuntimeError("invalid checkpoint filename")
        target = checkpoint / name
        if target.is_symlink():
            raise RuntimeError("checkpoint symlinks are not allowed")
        actual = sha256(target) if target.is_file() else None
        if actual != expected:
            mismatches.append({"file": name, "expected": expected, "actual": actual})
    if mismatches:
        raise RuntimeError(f"checkpoint hash mismatch: {mismatches}")
    state = json.loads((checkpoint / "trainer_state.json").read_text(encoding="utf-8"))
    if state.get("global_step") != manifest["global_step"]:
        raise RuntimeError("checkpoint state step mismatch")
    return manifest


def verify_inputs(data: Path, checkpoint: Path, expected_step: int = 5) -> tuple[dict, dict]:
    config = json.loads((data / "config.json").read_text(encoding="utf-8"))
    canonical = json.loads(CONFIG.read_text(encoding="utf-8"))
    normalized = dict(config)
    normalized["maximum_steps"] = canonical["maximum_steps"]
    if normalized != canonical or config.get("maximum_steps") != expected_step:
        raise RuntimeError("data config differs from pinned configuration")
    verify_jsonl(data / "validation.jsonl", config["validation_count"], config["validation_sha256"])
    manifest = verify_checkpoint(checkpoint, expected_step)
    for key in ("model_id", "model_revision", "train_sha256", "validation_sha256"):
        if manifest.get(key) != config[key]:
            raise RuntimeError(f"checkpoint identity mismatch: {key}")
    adapter_config = json.loads((checkpoint / "adapter_config.json").read_text(encoding="utf-8"))
    if adapter_config.get("base_model_name_or_path") != config["model_id"]:
        raise RuntimeError("adapter base model mismatch")
    return config, manifest


def completion_loss(model, rows: list[dict], collator) -> dict:
    import torch
    import torch.nn.functional as functional

    model.eval()
    total_nll = 0.0
    total_tokens = 0
    with torch.inference_mode():
        for row in rows:
            batch = {key: value.to(model.device) for key, value in collator([row]).items()}
            logits = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"]).logits
            labels = batch["labels"][:, 1:]
            nll = functional.cross_entropy(
                logits[:, :-1, :].float().reshape(-1, logits.shape[-1]),
                labels.reshape(-1),
                ignore_index=-100,
                reduction="sum",
            )
            tokens = int(labels.ne(-100).sum().item())
            total_nll += float(nll.item())
            total_tokens += tokens
    if total_tokens == 0 or not math.isfinite(total_nll):
        raise RuntimeError("invalid evaluation loss or empty completion tokens")
    loss = total_nll / total_tokens
    return {"loss": loss, "perplexity": math.exp(min(loss, 20)), "completion_tokens": total_tokens}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("colab_data"))
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-step", type=int, default=5)
    parser.add_argument("--output", type=Path, default=Path("evaluation.json"))
    args = parser.parse_args()

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    config, manifest = verify_inputs(args.data, args.checkpoint, args.expected_step)
    hardware = require_colab_gpu(config)

    tokenizer = AutoTokenizer.from_pretrained(
        config["model_id"], revision=config["model_revision"], trust_remote_code=False
    )
    tokenizer.pad_token = tokenizer.eos_token
    rows = [
        encode_row(tokenizer, row, config["max_length"])
        for row in load_rows(args.data / "validation.jsonl")
    ]
    collator = CompletionCollator(tokenizer.pad_token_id)
    major, _ = torch.cuda.get_device_capability(0)
    use_bf16 = major >= 8 and torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if use_bf16 else torch.float16

    base = AutoModelForCausalLM.from_pretrained(
        config["model_id"], revision=config["model_revision"], torch_dtype=dtype,
        trust_remote_code=False,
    ).to("cuda")
    base_metrics = completion_loss(base, rows, collator)
    del base
    torch.cuda.empty_cache()

    adapter_base = AutoModelForCausalLM.from_pretrained(
        config["model_id"], revision=config["model_revision"], torch_dtype=dtype,
        trust_remote_code=False,
    ).to("cuda")
    adapter = PeftModel.from_pretrained(adapter_base, args.checkpoint, is_trainable=False)
    adapter_metrics = completion_loss(adapter, rows, collator)
    delta = adapter_metrics["loss"] - base_metrics["loss"]
    result = {
        "status": "adapter_better_on_validation" if delta < 0 else "needs_review",
        "hardware": hardware,
        "dtype": str(dtype),
        "validation_count": len(rows),
        "validation_sha256": config["validation_sha256"],
        "checkpoint_global_step": manifest["global_step"],
        "adapter_sha256": manifest["files"]["adapter_model.safetensors"],
        "base": base_metrics,
        "adapter": adapter_metrics,
        "adapter_minus_base_loss": delta,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
