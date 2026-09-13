from __future__ import annotations
import hashlib, json
from pathlib import Path

FORBIDDEN = ("rubric", "reviewer", "review_status", "receipts")

def read_jsonl(path: Path) -> list[dict]:
    rows=[]
    with path.open(encoding="utf-8") as f:
        for line in f:
            row=json.loads(line); rows.append(row)
    return rows

def audit_export(path: Path, expected_count: int, expected_sha256: str) -> list[dict]:
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=expected_sha256: raise ValueError("export checksum mismatch")
    rows=read_jsonl(path)
    if len(rows)!=expected_count or any(set(r)!={"prompt","completion"} for r in rows): raise ValueError("invalid export")
    for row in rows:
        prompt=json.loads(row["prompt"]); json.loads(row["completion"])
        lowered=json.dumps(prompt, ensure_ascii=False).casefold()
        if any(key in lowered for key in FORBIDDEN): raise ValueError("review data leaked into prompt")
    return rows

def completion_labels(input_ids: list[int], prompt_length: int, eos_id: int) -> list[int]:
    if not 0 < prompt_length < len(input_ids): raise ValueError("invalid assistant boundary")
    ids=list(input_ids)
    if ids[-1] != eos_id: ids.append(eos_id)
    return [-100]*prompt_length + ids[prompt_length:]
