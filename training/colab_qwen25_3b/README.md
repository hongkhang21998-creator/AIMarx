# Qwen2.5-3B guarded Colab feasibility

This package is an isolated QLoRA feasibility path for issue #68. It does not
replace or resume the Qwen3-0.6B checkpoints. The model revision, approved
80/20 exports and all training parameters are pinned in `config.json`.

The first run is limited to one optimizer step. Resume to step 5 only after the
checkpoint is complete and the T4 remains within memory limits. Do not extend
to step 20 or run domain A/B evaluation without a separate human decision.

Training uses 4-bit NF4 double quantization, LoRA rank 8, context 2,048,
microbatch 1 and gradient accumulation 4. It fails closed below 14 GiB GPU
memory or 20 GiB free disk. It never mounts Drive or pushes a model.
