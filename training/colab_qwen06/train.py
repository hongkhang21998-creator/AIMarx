from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def require_colab_gpu(config: dict) -> dict:
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError("BLOCKED: Colab did not allocate a CUDA GPU")
    props = torch.cuda.get_device_properties(0)
    total_gib = props.total_memory / 1024**3
    if total_gib < config["minimum_gpu_memory_gib"]:
        raise RuntimeError(f"BLOCKED: GPU has only {total_gib:.2f} GiB")
    free_gib = shutil.disk_usage(".").free / 1024**3
    if free_gib < config["minimum_free_disk_gib"]:
        raise RuntimeError(f"BLOCKED: disk has only {free_gib:.2f} GiB free")
    return {"name": props.name, "memory_gib": round(total_gib, 3), "disk_free_gib": round(free_gib, 3)}


def encode_row(tokenizer, row: dict, max_length: int) -> dict:
    user = row["prompt"]
    completion = row["completion"]
    prompt_ids = tokenizer.apply_chat_template(
        [{"role": "user", "content": user}], tokenize=True, add_generation_prompt=True,
        enable_thinking=False,
    )
    completion_ids = tokenizer.encode(completion, add_special_tokens=False) + [tokenizer.eos_token_id]
    input_ids = prompt_ids + completion_ids
    if len(input_ids) > max_length:
        raise RuntimeError(f"BLOCKED: sample needs {len(input_ids)} tokens; no truncation allowed")
    return {"input_ids": input_ids, "attention_mask": [1] * len(input_ids),
            "labels": [-100] * len(prompt_ids) + completion_ids}


class RowsDataset:
    def __init__(self, rows: list[dict]):
        self.rows = rows

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        return self.rows[index]


class CompletionCollator:
    def __init__(self, pad_token_id: int):
        self.pad_token_id = pad_token_id

    def __call__(self, rows: list[dict]):
        import torch

        width = max(len(row["input_ids"]) for row in rows)
        batch = {"input_ids": [], "attention_mask": [], "labels": []}
        for row in rows:
            padding = width - len(row["input_ids"])
            batch["input_ids"].append(row["input_ids"] + [self.pad_token_id] * padding)
            batch["attention_mask"].append(row["attention_mask"] + [0] * padding)
            batch["labels"].append(row["labels"] + [-100] * padding)
        return {key: torch.tensor(value, dtype=torch.long) for key, value in batch.items()}


def checkpoint_manifest(checkpoint: Path, config: dict) -> dict:
    required = ["adapter_config.json", "adapter_model.safetensors", "optimizer.pt", "scheduler.pt",
                "rng_state.pth", "trainer_state.json", "training_args.bin"]
    missing = [name for name in required if not (checkpoint / name).is_file()]
    if missing:
        raise RuntimeError(f"incomplete checkpoint: {missing}")
    state = json.loads((checkpoint / "trainer_state.json").read_text(encoding="utf-8"))
    files = {}
    for path in sorted(checkpoint.iterdir()):
        if path.is_file():
            files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "global_step": state["global_step"],
        "model_id": config["model_id"],
        "model_revision": config["model_revision"],
        "train_sha256": config["train_sha256"],
        "validation_sha256": config["validation_sha256"],
        "files": files,
    }
    (checkpoint / "aimarx-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, default=Path("colab_data"))
    parser.add_argument("--output", type=Path, default=Path("colab_output"))
    parser.add_argument("--resume-from", type=Path)
    parser.add_argument("--stop-after", type=int)
    args = parser.parse_args()

    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import (AutoModelForCausalLM, AutoTokenizer, Trainer, TrainerCallback,
                              TrainingArguments, set_seed)

    config = json.loads((args.data / "config.json").read_text(encoding="utf-8"))
    hardware = require_colab_gpu(config)
    set_seed(config["seed"])
    tokenizer = AutoTokenizer.from_pretrained(
        config["model_id"], revision=config["model_revision"], trust_remote_code=False
    )
    tokenizer.pad_token = tokenizer.eos_token
    train_rows = [encode_row(tokenizer, row, config["max_length"]) for row in load_rows(args.data / "train.jsonl")]
    validation_rows = [encode_row(tokenizer, row, config["max_length"]) for row in load_rows(args.data / "validation.jsonl")]
    lengths = [len(row["input_ids"]) for row in train_rows + validation_rows]
    token_audit = {"minimum": min(lengths), "maximum": max(lengths), "mean": sum(lengths) / len(lengths),
                   "over_limit": sum(length > config["max_length"] for length in lengths)}
    (args.data / "token-audit.json").write_text(json.dumps(token_audit, indent=2) + "\n", encoding="utf-8")

    major, _ = torch.cuda.get_device_capability(0)
    use_bf16 = major >= 8 and torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if use_bf16 else torch.float16
    model = AutoModelForCausalLM.from_pretrained(
        config["model_id"], revision=config["model_revision"], torch_dtype=dtype,
        trust_remote_code=False,
    )
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model = get_peft_model(model, LoraConfig(
        r=config["lora_r"], lora_alpha=config["lora_alpha"], lora_dropout=config["lora_dropout"],
        bias="none", task_type="CAUSAL_LM", target_modules="all-linear",
    ))
    trainable, total = model.get_nb_trainable_parameters()

    class StopCallback(TrainerCallback):
        def on_step_end(self, _args, state, control, **_kwargs):
            if args.stop_after is not None and state.global_step >= args.stop_after:
                control.should_save = True
                control.should_training_stop = True
            return control

    training_args = TrainingArguments(
        output_dir=str(args.output), overwrite_output_dir=False,
        per_device_train_batch_size=config["micro_batch_size"],
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        learning_rate=config["learning_rate"], max_steps=config["maximum_steps"],
        save_strategy="steps", save_steps=1, save_total_limit=config["save_total_limit"],
        logging_strategy="steps", logging_steps=1, eval_strategy="no",
        fp16=not use_bf16, bf16=use_bf16, gradient_checkpointing=True,
        dataloader_num_workers=0, report_to="none", seed=config["seed"], data_seed=config["seed"],
        remove_unused_columns=False, save_only_model=False,
    )
    trainer = Trainer(
        model=model, args=training_args, train_dataset=RowsDataset(train_rows),
        eval_dataset=RowsDataset(validation_rows), processing_class=tokenizer,
        data_collator=CompletionCollator(tokenizer.pad_token_id), callbacks=[StopCallback()],
    )
    result = trainer.train(resume_from_checkpoint=str(args.resume_from) if args.resume_from else None)
    checkpoint = args.output / f"checkpoint-{trainer.state.global_step}"
    manifest = checkpoint_manifest(checkpoint, config)
    run = {
        "status": "trained_smoke", "hardware": hardware, "dtype": str(dtype),
        "trainable_parameters": trainable, "total_parameters": total,
        "token_audit": token_audit, "metrics": result.metrics, "checkpoint": str(checkpoint),
        "checkpoint_manifest": manifest,
    }
    (args.output / f"run-step-{trainer.state.global_step}.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(run, indent=2))


if __name__ == "__main__":
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    main()
