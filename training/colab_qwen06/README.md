# TRAIN-03 Colab Qwen3-0.6B

This package implements the free-tier Colab smoke path for issue #53. It is
separate from `training/windows_qwen06` so the Windows backend task can proceed
without overlapping files.

The notebook exports only the approved 80 train and 20 validation records,
checks their exact SHA-256 values, audits real tokenizer lengths without
truncation, and trains completion-only labels. Qwen3 thinking is disabled in the
chat template. The first Python process stops after optimizer step 1 and saves a
complete Trainer checkpoint. A second process resumes optimizer, scheduler, RNG
and model state and reaches five total steps.

Open `notebooks/TRAIN_03_Qwen3_0_6B_Colab.ipynb` in Colab, choose a GPU runtime,
and run cells in order. The run blocks if no CUDA GPU or less than 12 GiB GPU
memory is available. It never calls a billing API, pushes to Hugging Face, or
mounts Google Drive. Download the final ZIP when step 5 succeeds; copy it to the
Windows project and Data1000 only after verifying its embedded hashes.

The five-step smoke proves the data, model, LoRA and resume pipeline operates.
It does not establish administrative-domain quality.

After downloading and verifying the checkpoint, run `evaluate.py` on the same
Colab T4. It checks every file against the embedded manifest, loads the base
model and then reloads the adapter with PEFT in inference-only mode. It reports
completion-only loss and perplexity over the 20 approved validation records.
This comparison is a technical gate for a longer pilot; it is not a human
administrative-quality review and must not use the 20 smoke-test records.
