from __future__ import annotations
import hashlib, json, os, shutil, uuid
from pathlib import Path

REQUIRED = {"global_step", "base_revision", "data_sha256", "config_sha256", "files"}

def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()

def validate(path: Path) -> dict:
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != REQUIRED or type(manifest["global_step"]) is not int or manifest["global_step"] < 0:
        raise ValueError("invalid checkpoint manifest")
    for name, expected in manifest["files"].items():
        target = path / name
        if not target.is_file() or file_hash(target) != expected: raise ValueError("invalid checkpoint file")
    return manifest

def publish(run_dir: Path, step: int, metadata: dict, writer) -> Path:
    run_dir.mkdir(parents=True, exist_ok=True)
    temporary = run_dir / (f".checkpoint-{step}-" + uuid.uuid4().hex)
    temporary.mkdir()
    try:
        writer(temporary)
        files = {p.relative_to(temporary).as_posix(): file_hash(p) for p in temporary.rglob("*") if p.is_file()}
        manifest = {"global_step": step, **metadata, "files": files}
        (temporary / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        destination = run_dir / f"checkpoint-{step}"
        if destination.exists(): raise FileExistsError(destination)
        os.replace(temporary, destination); validate(destination)
        return destination
    except BaseException:
        if temporary.exists(): shutil.rmtree(temporary)
        raise

def prune(run_dir: Path, keep: int = 2) -> list[Path]:
    valid = []
    for path in run_dir.glob("checkpoint-*"):
        try: valid.append((validate(path)["global_step"], path))
        except (OSError, ValueError, KeyError, json.JSONDecodeError): pass
    valid.sort()
    removed = []
    for _, path in valid[:-keep]: shutil.rmtree(path); removed.append(path)
    return removed
