# TRAIN-04 post-pilot output evaluation

This package prepares the 20 public TRAIN-02 smoke cases for deterministic base
versus checkpoint-20 generation. The smoke set is repository-exposed and is not
a blind test. It is frozen as a regression gate and must not be used for later
training or tuning reported against the same cases.

`prepare.py` writes a model-input file containing only `id`, `input`,
`instruction`, and `output_schema`. Gold/reference and rubric are written to a
separate file for use only after the human review is locked. `generate.py` runs
base and adapter with the same greedy decoding configuration. `blind.py` creates
an A/B review bundle and a separate reveal map.

Final domain acceptance still requires an independently held private set of at
least 120 cases, reviewed and authorized separately by Nguyen Hong Khang.
