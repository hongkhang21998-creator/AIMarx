import hashlib, json
from pathlib import Path
import pytest
from training.windows_qwen06 import checkpoints, data
from training.windows_qwen06.watchdog import Watchdog, StopTraining
from training.windows_qwen06 import preflight

def test_completion_mask_and_eos():
    assert data.completion_labels([1,2,3],2,9)==[-100,-100,3,9]
    with pytest.raises(ValueError): data.completion_labels([1],1,9)

def test_export_requires_hash_count_and_no_review_leak(tmp_path):
    p=tmp_path/"x.jsonl"; raw=(json.dumps({"prompt":json.dumps({"id":"1"}),"completion":"{}"})+"\n").encode()
    p.write_bytes(raw); assert len(data.audit_export(p,1,hashlib.sha256(raw).hexdigest()))==1
    with pytest.raises(ValueError): data.audit_export(p,2,hashlib.sha256(raw).hexdigest())

def test_checkpoint_atomic_validation_and_prune(tmp_path):
    meta={"base_revision":"abc","data_sha256":"d","config_sha256":"c"}
    def writer(path): (path/"state.bin").write_bytes(b"state")
    first=checkpoints.publish(tmp_path,1,meta,writer); checkpoints.validate(first)
    checkpoints.publish(tmp_path,2,meta,writer); checkpoints.publish(tmp_path,3,meta,writer)
    assert [p.name for p in checkpoints.prune(tmp_path,2)]==["checkpoint-1"]
    (tmp_path/"checkpoint-2"/"state.bin").write_bytes(b"bad")
    with pytest.raises(ValueError): checkpoints.validate(tmp_path/"checkpoint-2")
    assert checkpoints.prune(tmp_path,1)==[]  # only checkpoint-3 remains valid

def test_failed_writer_never_publishes_checkpoint(tmp_path):
    def writer(path):
        (path/"partial").write_text("x"); raise OSError("disk")
    with pytest.raises(OSError): checkpoints.publish(tmp_path,1,{"base_revision":"a","data_sha256":"b","config_sha256":"c"},writer)
    assert list(tmp_path.iterdir())==[]

def test_watchdog_timeout(monkeypatch,tmp_path):
    monkeypatch.setattr("training.windows_qwen06.watchdog.memory_bytes",lambda:(8*1024**3,8*1024**3))
    ticks=iter([0,31]); guard=Watchdog(tmp_path,1,0,30,clock=lambda:next(ticks))
    with pytest.raises(StopTraining,match="session_timeout"): guard.check()

def test_preflight_gates_are_independent(monkeypatch,tmp_path):
    monkeypatch.setattr(preflight,"memory_bytes",lambda:(8*1024**3,3*1024**3))
    monkeypatch.setattr(preflight,"package_version",lambda name:"1" if name!="peft" else None)
    config={"minimum_free_ram_gib":4,"minimum_free_disk_gib":0}
    result=preflight.snapshot(tmp_path,config)
    assert result["ram_gate"] is False and result["disk_gate"] is True and result["stack_gate"] is False

def test_model_lock_is_exact_qwen06_revision():
    lock=json.loads((Path(__file__).parents[1]/"training/windows_qwen06/model.lock.json").read_text())
    assert lock["model_id"]=="Qwen/Qwen3-0.6B"
    assert len(lock["revision"])==40 and lock["downloaded"] is False
