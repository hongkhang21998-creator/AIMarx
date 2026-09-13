from __future__ import annotations
import shutil, time
from pathlib import Path
from .preflight import GIB, memory_bytes

class StopTraining(RuntimeError): pass

class Watchdog:
    def __init__(self, root: Path, min_ram_gib: float, min_disk_gib: float, max_seconds: float, clock=time.monotonic):
        self.root=root; self.ram=min_ram_gib*GIB; self.disk=min_disk_gib*GIB
        self.max_seconds=max_seconds; self.clock=clock; self.started=clock()
    def check(self):
        if memory_bytes()[1] < self.ram: raise StopTraining("low_system_ram")
        if shutil.disk_usage(self.root).free < self.disk: raise StopTraining("low_disk")
        if self.clock() - self.started >= self.max_seconds: raise StopTraining("session_timeout")
