from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.colab_qwen06.evaluate import verify_checkpoint
from training.colab_qwen06.train import require_colab_gpu


def verify_identity(manifest: dict, config: dict, checkpoint: Path) -> None:
    for key in ("model_id", "model_revision", "train_sha256", "validation_sha256"):
        if manifest.get(key) != config[key]:
            raise RuntimeError(f"checkpoint identity mismatch: {key}")
    adapter_config = json.loads((checkpoint / "adapter_config.json").read_text(encoding="utf-8"))
    if adapter_config.get("base_model_name_or_path") != config["model_id"]:
        raise RuntimeError("adapter base model mismatch")


def load_inputs(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    allowed = {"id", "input", "instruction", "output_schema"}
    if len(rows) != 20 or len({row.get("id") for row in rows}) != 20 or any(set(row) != allowed for row in rows):
        raise RuntimeError("invalid locked evaluation inputs")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("base", "adapter"), required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

    manifest = verify_checkpoint(args.checkpoint, expected_step=20)
    config = json.loads(Path("training/colab_qwen06/config.json").read_text(encoding="utf-8"))
    verify_identity(manifest, config, args.checkpoint)
    require_colab_gpu(config)
    rows = load_inputs(args.inputs)
    set_seed(config["seed"])
    tokenizer = AutoTokenizer.from_pretrained(config["model_id"], revision=config["model_revision"], trust_remote_code=False)
    tokenizer.pad_token = tokenizer.eos_token
    dtype = torch.float16
    model = AutoModelForCausalLM.from_pretrained(config["model_id"], revision=config["model_revision"], torch_dtype=dtype, trust_remote_code=False).to("cuda")
    if args.mode == "adapter":
        model = PeftModel.from_pretrained(model, args.checkpoint, is_trainable=False)
    model.eval()
    outputs = []
    with torch.inference_mode():
        for row in rows:
            prompt = json.dumps(row, ensure_ascii=False, sort_keys=True)
            encoded = tokenizer.apply_chat_template([{"role": "user", "content": prompt}], tokenize=True, add_generation_prompt=True, enable_thinking=False, return_tensors="pt").to(model.device)
            generated = model.generate(encoded, do_sample=False, max_new_tokens=1024, pad_token_id=tokenizer.eos_token_id)
            text = tokenizer.decode(generated[0, encoded.shape[1]:], skip_special_tokens=True)
            outputs.append({"id": row["id"], "output": text, "error": None})
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in outputs), encoding="utf-8")
    print(json.dumps({"mode": args.mode, "count": len(outputs), "checkpoint_step": manifest["global_step"]}))


if __name__ == "__main__":
    main()
