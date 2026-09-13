from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import shutil
import sys
from pathlib import Path

GIB = 1024 ** 3


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


def memory_bytes() -> tuple[int, int]:
    if os.name == "nt":
        value = MEMORYSTATUSEX(); value.dwLength = ctypes.sizeof(value)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value)):
            raise OSError("GlobalMemoryStatusEx failed")
        return value.ullTotalPhys, value.ullAvailPhys
    pages = os.sysconf("SC_PHYS_PAGES"); available = os.sysconf("SC_AVPHYS_PAGES")
    size = os.sysconf("SC_PAGE_SIZE")
    return pages * size, available * size


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def package_version(name: str) -> str | None:
    try:
        from importlib.metadata import version
        return version(name)
    except Exception:
        return None


def snapshot(root: Path, config: dict) -> dict:
    total, free = memory_bytes(); disk = shutil.disk_usage(root)
    packages = {name: package_version(name) for name in ("torch", "transformers", "peft", "accelerate")}
    return {
        "platform": platform.platform(), "python": sys.version.split()[0],
        "executable": sys.executable, "total_ram_gib": round(total / GIB, 3),
        "free_ram_gib": round(free / GIB, 3), "free_disk_gib": round(disk.free / GIB, 3),
        "packages": packages,
        "ram_gate": free >= config["minimum_free_ram_gib"] * GIB,
        "disk_gate": disk.free >= config["minimum_free_disk_gib"] * GIB,
        "stack_gate": all(packages.values()),
    }


def main() -> int:
    here = Path(__file__).resolve().parent
    config = json.loads((here / "config.json").read_text(encoding="utf-8"))
    result = snapshot(Path.cwd(), config)
    result["ready_to_load_model"] = result["ram_gate"] and result["disk_gate"] and result["stack_gate"]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ready_to_load_model"] else 2


if __name__ == "__main__": raise SystemExit(main())
