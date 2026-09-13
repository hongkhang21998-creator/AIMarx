from __future__ import annotations
import argparse, json
from pathlib import Path
from evals.planning_v2.cli import load_cases as baseline_cases
from evals.training.train02.cli import lines, write_new
from evals.training.train02.core import export_rows, load_dataset
from .data import audit_export
from .preflight import snapshot

ROOT=Path(__file__).resolve().parents[2]
REVIEWED=ROOT/"evals/training/train02/reviews/2026-09-13-khang"
EXPECTED={"train":(80,"1062862c5db0c466de2b2ac20c3f217edabfcaa84ea34304c28c46a9758e4a2b"),
          "validation":(20,"8d3c43d3d69df8c7c58cba9733e76b1619d77629a144fae946468c8c56ad1741")}

def prepare(output: Path):
    output.mkdir(parents=True,exist_ok=False)
    cases=load_dataset(REVIEWED); result={}
    try:
        for split,(count,digest) in EXPECTED.items():
            target=output/f"{split}.jsonl"
            write_new(target,lines(export_rows(cases,split,baseline_cases())))
            audit_export(target,count,digest)
            result[split]={"rows":count,"sha256":digest}
        write_new(output/"manifest.json",json.dumps(result,sort_keys=True,indent=2)+"\n")
    except BaseException:
        # Leave evidence for diagnosis; an incomplete directory is never accepted as prepared.
        raise
    return result

def main():
    p=argparse.ArgumentParser(); p.add_argument("command",choices=["preflight","prepare"]); p.add_argument("--output",type=Path)
    a=p.parse_args(); config=json.loads((Path(__file__).parent/"config.json").read_text(encoding="utf-8"))
    if a.command=="preflight":
        result=snapshot(ROOT,config); result["ready_to_load_model"]=result["ram_gate"] and result["disk_gate"] and result["stack_gate"]
        print(json.dumps(result,indent=2)); return 0 if result["ready_to_load_model"] else 2
    if not a.output: p.error("prepare requires --output")
    print(json.dumps(prepare(a.output),indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
